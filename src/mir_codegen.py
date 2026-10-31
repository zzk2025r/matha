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

from src import mir_opt
from src.mir import (
    MIRArithInstr,
    MIRBranchInstr,
    MIRCallInstr,
    MIRCImportInstr,
    MIRCompareInstr,
    MIRCondBranchInstr,
    MIRConstInstr,
    MIRLabelInstr,
    MIRLoadInstr,
    MIRLogicalInstr,
    MIRReturnInstr,
    MIRStoreInstr,
    MIRUnaryInstr,
)


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
        # 在生成前对 MIR 进行清洗（优化管线）
        try:
            pipeline = mir_opt.MIRPassPipeline.create_default()
            mir_program = pipeline.run(mir_program)
        except Exception:
            try:
                mir_program = mir_opt.MIRPassPipeline().run(mir_program, mir_opt.MIRPassPipeline.default_pipeline())
            except Exception:
                pass

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
            lines.append(self._signature(name, func) + ";")
        if mir_program.functions:
            lines.append("")

        for name, func in mir_program.functions.items():
            lines.extend(self._generate_function(name, func))

        return "\n".join(lines)

    @staticmethod
    def _c_name(value: any) -> str:
        return str(value).lstrip("%")

    @classmethod
    def _defines_value(cls, instr: any) -> bool:
        if not getattr(instr, "result", ""):
            return False
        return isinstance(instr, (
            MIRArithInstr,
            MIRCallInstr,
            MIRCompareInstr,
            MIRConstInstr,
            MIRLoadInstr,
            MIRLogicalInstr,
            MIRUnaryInstr,
        ))

    def _signature(self, name: str, func: any) -> str:
        if name == "main":
            return "int main(void)"
        return_type = self.TYPE_MAP.get(func.return_type, "double")
        param_types = list(getattr(func, "param_types", []) or [])
        params = []
        for index, param in enumerate(func.params):
            param_type = param_types[index] if index < len(param_types) else "double"
            params.append(f"{self.TYPE_MAP.get(param_type, 'double')} {param}")
        return f"static {return_type} {name}({', '.join(params)})"

    def _generate_function(self, name: str, func: any) -> list[str]:
        """生成函数定义。"""
        lines = [self._signature(name, func) + " {"]

        declared = set()
        for instr in func.instructions:
            if not self._defines_value(instr):
                continue
            result = self._c_name(instr.result)
            if result and result not in declared:
                lines.append(f"    double {result};")
                declared.add(result)

        lines.extend(self._generate_instructions(func.instructions))

        if not any(isinstance(instr, MIRReturnInstr) for instr in func.instructions):
            return_val = None
            for instr in reversed(func.instructions):
                if self._defines_value(instr):
                    return_val = self._c_name(instr.result)
                    break
            lines.append(f"    return {return_val or '0.0'};")

        lines.append("}")
        lines.append("")
        return lines

    def _generate_locals(self, func: any) -> tuple[list[str], list[str]]:
        """生成本地变量声明和初始化。"""
        decl_lines = []
        init_lines = []
        seen = set()
        for instr in func.instructions:
            if not self._defines_value(instr):
                continue
            result = self._c_name(instr.result)
            if result in seen:
                continue
            decl_lines.append(f"    double {result};")
            if getattr(instr, "value", None) is not None and isinstance(instr, MIRConstInstr):
                init_lines.append(f"    {result} = {instr.value};")
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

    def _generate_instr_code(self, instr: any) -> str | None:
        """生成单条指令的 C 代码。"""
        result = self._c_name(getattr(instr, "result", ""))
        operands = [self._c_name(op) for op in getattr(instr, "operands", [])]
        left = operands[0] if operands else "0.0"
        right = operands[1] if len(operands) > 1 else "0.0"

        if isinstance(instr, MIRConstInstr):
            return f"    {result} = {instr.value};" if result else None

        if isinstance(instr, MIRArithInstr):
            op = instr.op
            if op == "=":
                return f"    {result} = {left};"
            if op == "**":
                return f"    {result} = pow({left}, {right});"
            if op == "//":
                return f"    {result} = floor({left} / {right});"
            if op == "%":
                return f"    {result} = fmod({left}, {right});"
            return f"    {result} = {left} {op} {right};"

        if isinstance(instr, MIRUnaryInstr):
            return f"    {result} = {instr.op}{left};"

        if isinstance(instr, MIRCompareInstr):
            return f"    {result} = ({left} {instr.op} {right});"

        if isinstance(instr, MIRLogicalInstr):
            if instr.op == "not":
                return f"    {result} = (!{left});"
            op = "&&" if instr.op == "and" else "||"
            return f"    {result} = ({left} {op} {right});"

        if isinstance(instr, MIRCallInstr):
            actual_func = instr.c_func or instr.func_name
            args = ", ".join(operands)
            if actual_func == "printf":
                value = operands[0] if operands else "0.0"
                return f'    printf("%g\\n", {value});'
            call = f"{actual_func}({args})"
            return f"    {result} = {call};" if result else f"    {call};"

        if isinstance(instr, MIRLoadInstr):
            return f"    {result} = {self._c_name(instr.source)};"

        if isinstance(instr, MIRStoreInstr):
            return f"    {self._c_name(instr.target)} = {left};"

        if isinstance(instr, MIRReturnInstr):
            value = left or self._c_name(instr.value) or "0.0"
            return f"    return {value};"

        if isinstance(instr, MIRLabelInstr):
            return f"    {instr.label}:;"

        if isinstance(instr, MIRBranchInstr):
            return f"    goto {instr.label};"

        if isinstance(instr, MIRCondBranchInstr):
            cond = self._c_name(instr.cond) if instr.cond else left
            return f"    if ({cond}) goto {instr.true_label}; else goto {instr.false_label};"

        if isinstance(instr, MIRCImportInstr):
            return None

        if getattr(instr, "value", None) is not None and result:
            return f"    {result} = {instr.value};"

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
        try:
            pipeline = mir_opt.MIRPassPipeline.create_default()
            mir_program = pipeline.run(mir_program)
        except Exception:
            try:
                mir_program = mir_opt.MIRPassPipeline().run(mir_program, mir_opt.MIRPassPipeline.default_pipeline())
            except Exception:
                pass
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

        if not any(isinstance(instr, MIRReturnInstr) for instr in func.instructions):
            return_val = None
            for instr in reversed(func.instructions):
                result = getattr(instr, "result", "").lstrip("%")
                if result and result != "":
                    return_val = result
                    break
            lines.append(f"    return {return_val or '0.0'}")

        lines.append("")
        return lines

    def _generate_instr_code(self, instr: any) -> str:
        """生成单条指令的 Python 代码。"""
        result = getattr(instr, "result", "").lstrip("%")
        if not result:
            result = "result"

        if isinstance(instr, MIRConstInstr):
            return f"{result} = {instr.value}"

        if isinstance(instr, MIRReturnInstr):
            value = (instr.operands[0] if instr.operands else instr.value) or "0.0"
            return f"return {str(value).lstrip('%')}"

        # 函数调用
        c_func = getattr(instr, "c_func", "")
        func_name = getattr(instr, "func_name", "")
        if c_func or func_name:
            actual_func = c_func or func_name
            args = ", ".join(a.lstrip("%") for a in instr.operands) if instr.operands else ""
            if actual_func == "printf":
                return f"print({args})" if args else "print()"
            # 检查是否是 math 函数
            if actual_func in dir(math):
                return f"{result} = math.{actual_func}({args})"
            return f"{result} = {actual_func}({args})"

        # 算术运算
        if hasattr(instr, "op") and instr.op:
            left = instr.operands[0].lstrip("%") if instr.operands else "0"
            right = instr.operands[1].lstrip("%") if len(instr.operands) > 1 else "0"
            if instr.op == "=":
                return f"{result} = {left}"
            if instr.op == "//":
                return f"{result} = {left} // {right}"
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
            import subprocess
            import tempfile
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
