# -*- coding: utf-8 -*-
"""
Matha MIR → C/Python 代码生成器

生成高效 C 代码，可直接编译为原生机器码。
生成优化 Python 代码，可直接解释执行。

优化策略：
  1. 内联数学函数调用
  2. 消除冗余计算
  3. 寄存器分配
  4. 常量折叠
  5. 死代码消除
"""

from __future__ import annotations
import math
import re
from typing import Optional


class MIRToCGenerator:
    """将 Matha MIR 转换为 C 代码。"""

    TYPE_MAP = {
        "double": "double", "i64": "int64_t", "i32": "int32_t",
        "i1": "int", "ptr": "void*", "void": "void",
    }

    MATH_FUNCS = {
        "sin": "sin", "cos": "cos", "tan": "tan",
        "asin": "asin", "acos": "acos", "atan": "atan",
        "atan2": "atan2", "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
        "sqrt": "sqrt", "cbrt": "cbrt", "pow": "pow",
        "exp": "exp", "exp2": "exp2", "expm1": "expm1",
        "log": "log", "log10": "log10", "log2": "log2", "log1p": "log1p",
        "fabs": "fabs", "floor": "floor", "ceil": "ceil",
        "round": "round", "trunc": "trunc",
        "signbit": "signbit", "hypot": "hypot", "fmod": "fmod",
    }

    C_CONSTS = {
        "pi": "M_PI", "tau": "(M_PI * 2)", "e": "M_E",
        "sqrt2": "M_SQRT2", "sqrt3": "M_SQRT3",
        "ln2": "M_LN2", "ln10": "M_LN10",
    }

    def __init__(self, optimize: bool = True) -> None:
        self._optimize = optimize
        self._includes: set = set()
        self._c_imports: list = []

    def generate(self, mir_program: any) -> str:
        """生成完整 C 代码。"""
        lines = [
            "/* Matha MIR → C 代码生成 */",
            "/* 由 matha-cc 自动生成 */",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <math.h>",
            "#include <string.h>",
            "",
            "#ifndef M_PI",
            "#define M_PI 3.14159265358979323846",
            "#endif",
            "",
        ]

        for name, func in mir_program.functions.items():
            lines.extend(self._generate_function(name, func))

        return "\n".join(lines)

    def _generate_function(self, name: str, func: any) -> list[str]:
        """生成函数定义。"""
        lines = []
        params = ", ".join(f"double {p}" for p in func.params)
        lines.append(f"static double {name}({params}) {{")

        # 收集所有需要声明的变量
        all_results = set()
        for instr in func.instructions:
            result = getattr(instr, "result", "").lstrip("%")
            if result and not (hasattr(instr, "value") and instr.value is not None):
                all_results.add(result)

        # 生成常量初始化（必须在其他变量之前）
        for instr in func.instructions:
            result = getattr(instr, "result", "").lstrip("%")
            if result and hasattr(instr, "value") and instr.value is not None:
                lines.append(f"    double {result} = {instr.value};")

        # 生成本地变量声明
        for result in all_results:
            lines.append(f"    double {result};")

        # 生成指令代码
        instructions = self._generate_instructions(func.instructions)
        lines.extend(instructions)

        # 返回值
        return_val = None
        for instr in reversed(func.instructions):
            result = getattr(instr, "result", "").lstrip("%")
            if result and result != "":
                return_val = result
                break
        if return_val:
            lines.append(f"    return {return_val};")
        else:
            lines.append("    return 0.0;")

        lines.append("}")
        lines.append("")
        return lines

    def _generate_locals(self, func: any) -> tuple[list[str], list[str]]:
        """生成本地变量声明和初始化。"""
        decl_lines = []
        init_lines = []
        seen = set()
        for instr in func.instructions:
            result = getattr(instr, "result", "").lstrip("%")
            if result and result not in seen:
                if hasattr(instr, "value") and instr.value is not None:
                    init_lines.append(f"    double {result} = {instr.value};")
                else:
                    decl_lines.append(f"    double {result};")
                seen.add(result)
        return decl_lines, init_lines

    def _generate_instructions(self, instructions: list) -> list[str]:
        """生成指令代码。"""
        lines = []
        for instr in instructions:
            code = self._generate_instr_code(instr)
            if code:
                lines.append(code)
        return lines

    def _generate_instr_code(self, instr: any) -> Optional[str]:
        """生成单条指令的 C 代码。"""
        result = getattr(instr, "result", "").lstrip("%")

        # 常量
        if hasattr(instr, "value") and instr.value is not None:
            return None  # 已在初始化时处理

        # 算术运算
        if hasattr(instr, "op") and instr.op:
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            op_map = {"+": "+", "-": "-", "*": "*", "/": "/", "%": "%"}
            c_op = op_map.get(instr.op, instr.op)
            if c_op == "**":
                return f"    double {result} = pow({left}, {right});"
            return f"    double {result} = {left} {c_op} {right};"

        # 函数调用
        c_func = getattr(instr, "c_func", "")
        func_name = getattr(instr, "func_name", "")
        if c_func or func_name:
            actual_func = c_func or func_name
            args = ", ".join(a.lstrip("%") for a in instr.operands) if instr.operands else ""
            return f"    double {result} = {actual_func}({args});"

        # 比较运算
        if hasattr(instr, "op") and instr.op in ("<", ">", "<=", ">=", "==", "!="):
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            return f"    int {result} = ({left} {instr.op} {right});"

        # 逻辑运算
        if hasattr(instr, "op") and instr.op in ("and", "or", "not"):
            if instr.op == "not":
                arg = instr.operands[0].lstrip("%") if instr.operands else "0"
                return f"    int {result} = (!{arg});"
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            c_op = "&&" if instr.op == "and" else "||"
            return f"    int {result} = ({left} {c_op} {right});"

        # 返回
        if hasattr(instr, "value") and instr.value:
            return f"    return {instr.value.lstrip('%')};"

        # 存储
        if hasattr(instr, "target") and instr.target:
            return f"    {instr.target.lstrip('%')} = {instr.operands[0].lstrip('%')};"

        # 标签和分支（简化处理）
        if hasattr(instr, "label"):
            return None  # C 不需要显式标签

        return None

    def _optimize(self, source: str) -> str:
        """优化 C 代码。"""
        def fold_const(m):
            try:
                left = float(m.group(1))
                right = float(m.group(3))
                op = m.group(2)
                if op == "+": return str(left + right)
                if op == "-": return str(left - right)
                if op == "*": return str(left * right)
                if op == "/": return str(left / right) if right != 0 else m.group(0)
            except (ValueError, ZeroDivisionError):
                pass
            return m.group(0)
        return re.sub(r'(-?\d+\.?\d*)\s*([+\-*/])\s*(-?\d+\.?\d*)', fold_const, source)


class MIRToPythonGenerator:
    """将 Matha MIR 转换为优化的 Python 代码。"""

    def __init__(self, optimize: bool = True) -> None:
        self._optimize = optimize

    def generate(self, mir_program: any) -> str:
        """生成 Python 代码。"""
        lines = [
            "# -*- coding: utf-8 -*-",
            "# Matha MIR → Python 代码生成",
            "# 由 matha-cc 自动生成",
            "",
            "import math",
            "from typing import Optional",
            "",
        ]

        for name, func in mir_program.functions.items():
            lines.extend(self._generate_function(name, func))

        return "\n".join(lines)

    def _generate_function(self, name: str, func: any) -> list[str]:
        """生成 Python 函数。"""
        lines = [
            f"def {name}({', '.join(func.params)}):",
            '    """Auto-generated from Matha MIR."""',
        ]

        for instr in func.instructions:
            code = self._generate_instr_code(instr)
            if code:
                lines.append(f"    {code}")

        # 找到返回值（最后一个有 result 的指令）
        return_val = None
        for instr in reversed(func.instructions):
            result = getattr(instr, "result", "").lstrip("%")
            if result and result != "":
                return_val = result
                break
        if return_val:
            lines.append(f"    return {return_val}")
        else:
            lines.append("    return 0.0")

        lines.append("")
        return lines

    def _generate_instr_code(self, instr: any) -> str:
        """生成单条指令的 Python 代码。"""
        result = getattr(instr, "result", "").lstrip("%")
        if not result:
            result = "result"

        # 常量
        if hasattr(instr, "value") and instr.value is not None:
            return f"{result} = {instr.value}"

        # 函数调用
        c_func = getattr(instr, "c_func", "")
        func_name = getattr(instr, "func_name", "")
        if c_func or func_name:
            actual_func = c_func or func_name
            # 检查是否是 math 函数
            if actual_func in dir(math):
                args = ", ".join(a.lstrip("%") for a in instr.operands) if instr.operands else ""
                return f"{result} = math.{actual_func}({args})"
            else:
                args = ", ".join(a.lstrip("%") for a in instr.operands) if instr.operands else ""
                return f"{result} = {actual_func}({args})"

        # 算术运算
        if hasattr(instr, "op") and instr.op:
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            op_map = {"+": "+", "-": "-", "*": "*", "/": "/", "**": "**", "%": "%"}
            c_op = op_map.get(instr.op, instr.op)
            if c_op == "**":
                return f"{result} = math.pow({left}, {right})"
            return f"{result} = {left} {c_op} {right}"

        # 比较运算
        if hasattr(instr, "op") and instr.op in ("<", ">", "<=", ">=", "==", "!="):
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            return f"{result} = {left} {instr.op} {right}"

        # 逻辑运算
        if hasattr(instr, "op") and instr.op in ("and", "or", "not"):
            if instr.op == "not":
                arg = instr.operands[0].lstrip("%") if instr.operands else "0"
                return f"{result} = not {arg}"
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            py_op = "and" if instr.op == "and" else "or"
            return f"{result} = {left} {py_op} {right}"

        # 返回
        if hasattr(instr, "value") and instr.value:
            return f"return {instr.value.lstrip('%')}"

        # 存储
        if hasattr(instr, "target") and instr.target:
            return f"{instr.target.lstrip('%')} = {instr.operands[0].lstrip('%')}"

        return ""


# ============================================================
# 统一编译器
# ============================================================

class MathaCodeGenerator:
    """Matha 统一代码生成器。"""

    def __init__(self, target: str = "c", optimize: bool = True) -> None:
        self._target = target
        self._optimize = optimize
        self._c_gen = MIRToCGenerator(optimize=optimize)
        self._py_gen = MIRToPythonGenerator(optimize=optimize)

    def generate(self, mir_program: any) -> str:
        """生成目标代码。"""
        if self._target == "c":
            return self._c_gen.generate(mir_program)
        elif self._target == "python":
            return self._py_gen.generate(mir_program)
        else:
            raise ValueError(f"不支持的目标: {self._target}")

    def compile_and_run(self, mir_program: any, args: list = None) -> tuple:
        """编译并运行生成的代码。"""
        code = self.generate(mir_program)
        if self._target == "c":
            import tempfile, subprocess
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False, encoding='utf-8') as f:
                f.write(code)
                c_file = f.name
            exe_file = c_file.replace('.c', '.exe')
            result = subprocess.run(['gcc', '-O2', c_file, '-o', exe_file, '-lm'], capture_output=True, text=True)
            if result.returncode != 0:
                return f"编译失败: {result.stderr}", 1
            run_result = subprocess.run([exe_file] + (args or []), capture_output=True, text=True)
            return run_result.stdout.strip(), run_result.returncode
        elif self._target == "python":
            code_obj = compile(code, "<matha>", "exec")
            namespace = {}
            exec(code_obj, namespace)  # noqa: S102
            return namespace.get("result", "0.0"), 0
        return "", 0


# ============================================================
# 公共 API
# ============================================================

def generate_c_code(mir_program: any) -> str:
    """生成 C 代码。"""
    if not hasattr(mir_program, "functions"):
        from src.mir import MIRGenerator
        mir_program = MIRGenerator().generate(mir_program)
    return MIRToCGenerator().generate(mir_program)


def generate_python_code(mir_program: any) -> str:
    """生成 Python 代码。"""
    if not hasattr(mir_program, "functions"):
        from src.mir import MIRGenerator
        mir_program = MIRGenerator().generate(mir_program)
    return MIRToPythonGenerator().generate(mir_program)


def compile_to_c(ast_or_mir: any) -> str:
    """编译 MIR 为 C 代码。"""
    return generate_c_code(ast_or_mir)


def compile_to_python(ast_or_mir: any) -> str:
    """编译 MIR 为 Python 代码。"""
    return generate_python_code(ast_or_mir)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MIRToCGenerator",
    "MIRToPythonGenerator",
    "MathaCodeGenerator",
    "generate_c_code",
    "generate_python_code",
    "compile_to_c",
    "compile_to_python",
]
