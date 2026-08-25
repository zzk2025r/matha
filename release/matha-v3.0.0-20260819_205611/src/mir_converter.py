# -*- coding: utf-8 -*-
"""
Matha MIR → Matha 代码生成器

将 MIR 中间表示转换回 Matha 源语言，实现三向互转。
"""

from __future__ import annotations
import re
from typing import Optional


class MIRToMathaGenerator:
    """将 MIR 转换为 Matha 源语言。"""

    MATH_FUNCS = {
        "sin": "sin", "cos": "cos", "tan": "tan",
        "asin": "arcsin", "acos": "arccos", "atan": "arctan",
        "atan2": "arctan2", "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
        "sqrt": "sqrt", "cbrt": "cbrt", "pow": "pow",
        "exp": "exp", "exp2": "exp2", "expm1": "expm1",
        "log": "log", "log10": "log10", "log2": "log2", "log1p": "log1p",
        "fabs": "fabs", "floor": "floor", "ceil": "ceil",
        "round": "round", "trunc": "trunc",
        "signbit": "signbit", "hypot": "hypot", "fmod": "fmod",
    }

    MATH_CONSTS = {
        "pi": "π", "tau": "τ", "e": "e",
        "sqrt2": "√2", "sqrt3": "√3",
        "ln2": "ln2", "ln10": "ln10",
    }

    def __init__(self, indent: int = 4) -> None:
        self._indent = indent
        self._var_counter = 0
        self._var_map: dict = {}  # MIR temp → Matha var name

    def generate(self, mir_program: any) -> str:
        """生成 Matha 源码。"""
        lines = [
            "# -*- coding: utf-8 -*-",
            "# Matha MIR → Matha 代码生成",
            "# 由 matha-cc 自动生成",
            "",
            "# Matha 源语言常量定义",
            "π = 3.141592653589793",
            "τ = 6.283185307179586",
            "e = 2.718281828459045",
            "√2 = 1.4142135623730951",
            "√3 = 1.7320508075688772",
            "",
        ]

        for name, func in mir_program.functions.items():
            if name == "main":
                lines.extend(self._generate_main(func))
            else:
                lines.extend(self._generate_function(name, func))

        return "\n".join(lines)

    def _generate_main(self, func: any) -> list[str]:
        """生成 main 函数体。"""
        lines = []
        self._var_map = {}
        self._var_counter = 0

        for instr in func.instructions:
            code = self._generate_instr_code(instr)
            if code:
                lines.append(code)

        return lines

    def _generate_function(self, name: str, func: any) -> list[str]:
        """生成 Matha 函数定义。"""
        lines = [
            f"{name} = ({', '.join(func.params)}) →",
        ]
        self._var_map = {param: param for param in func.params}
        self._var_counter = len(func.params)

        for instr in func.instructions:
            code = self._generate_instr_code(instr)
            if code:
                lines.append(f"    {code}")

        return lines

    def _generate_instr_code(self, instr: any) -> Optional[str]:
        """生成单条指令的 Matha 代码。"""
        result = getattr(instr, "result", "").lstrip("%")

        # 常量
        if hasattr(instr, "value") and instr.value is not None:
            self._var_map[result] = result
            return f"{result} = {instr.value}"

        # 函数调用
        c_func = getattr(instr, "c_func", "")
        func_name = getattr(instr, "func_name", "")
        if c_func or func_name:
            actual_func = c_func or func_name
            matha_func = self.MATH_FUNCS.get(actual_func, actual_func)
            args = ", ".join(self._resolve_var(a) for a in instr.operands) if instr.operands else ""
            self._var_map[result] = result
            return f"{result} = {matha_func}({args})"

        # 算术运算
        if hasattr(instr, "op") and instr.op:
            left = self._resolve_var(instr.operands[0]) if instr.operands else "0"
            right = self._resolve_var(instr.operands[1]) if len(instr.operands) > 1 else "0"
            op_map = {"+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "**": "**"}
            matha_op = op_map.get(instr.op, instr.op)
            self._var_map[result] = result
            return f"{result} = {left} {matha_op} {right}"

        # 比较运算
        if hasattr(instr, "op") and instr.op in ("<", ">", "<=", ">=", "==", "!="):
            left = self._resolve_var(instr.operands[0]) if instr.operands else "0"
            right = self._resolve_var(instr.operands[1]) if len(instr.operands) > 1 else "0"
            self._var_map[result] = result
            return f"{result} = {left} {instr.op} {right}"

        # 逻辑运算
        if hasattr(instr, "op") and instr.op in ("and", "or", "not"):
            if instr.op == "not":
                arg = self._resolve_var(instr.operands[0]) if instr.operands else "0"
                self._var_map[result] = result
                return f"{result} = not {arg}"
            left = self._resolve_var(instr.operands[0])
            right = self._resolve_var(instr.operands[1])
            matha_op = "与" if instr.op == "and" else "或"
            self._var_map[result] = result
            return f"{result} = {left} {matha_op} {right}"

        # 返回
        if hasattr(instr, "value") and instr.value:
            return f"return {self._resolve_var(instr.value)}"

        # 存储
        if hasattr(instr, "target") and instr.target:
            val = self._resolve_var(instr.operands[0]) if instr.operands else "0"
            return f"{instr.target.lstrip('%')} = {val}"

        return None

    def _resolve_var(self, var: str) -> str:
        """解析变量，替换为 Matha 变量名。"""
        var = var.lstrip("%")
        return self._var_map.get(var, var)

    def _new_var(self) -> str:
        """生成新变量名。"""
        self._var_counter += 1
        return f"x{self._var_counter}"


class MathaToMIRGenerator:
    """将 Matha 源码转换回 MIR（反向生成器）。"""

    def __init__(self) -> None:
        self._var_counter = 0

    def _new_temp(self) -> str:
        self._var_counter += 1
        return f"t{self._var_counter}"

    def generate_from_matha(self, matha_source: str) -> str:
        """从 Matha 源码生成 MIR 文本表示。"""
        from src.mir import MIRGenerator
        from src.compiler.matha_cc import MathaLexer, MathaParser

        lexer = MathaLexer(matha_source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()

        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        lines = ["; Matha MIR 表示", "; " + "=" * 50]
        for name, func in mir.functions.items():
            lines.append(f"; 函数: {name}")
            lines.append(f"; 参数: {func.params}")
            lines.append(f"; 返回类型: {func.return_type}")
            lines.append(f"; 指令数: {len(func.instructions)}")
            for instr in func.instructions:
                lines.append(f";   {instr}")
            lines.append("")

        return "\n".join(lines)


class MathaConverter:
    """Matha 三向转换器：Matha ↔ C ↔ Python。"""

    TARGETS = ["matha", "c", "python"]

    def __init__(self) -> None:
        from src.mir import MIRGenerator
        self._mir_gen = MIRGenerator()
        self._matha_to_mir = MIRToMathaGenerator()
        self._matha_from_mir = MathaToMIRGenerator()

    def convert(self, source: str, source_lang: str, target_lang: str) -> str:
        """
        将 source 从 source_lang 转换为 target_lang。
        """
        if source_lang == target_lang:
            return source

        mir_program = self._to_mir(source, source_lang)
        return self._from_mir(mir_program, target_lang)

    def _to_mir(self, source: str, lang: str) -> any:
        """将源语言转换为 MIR。"""
        if lang == "matha":
            from src.compiler.matha_cc import MathaLexer, MathaParser
            lexer = MathaLexer(source)
            tokens = lexer.tokenize()
            parser = MathaParser(tokens)
            ast = parser.parse()
            return self._mir_gen.generate(ast)
        elif lang == "c":
            return self._c_to_mir(source)
        elif lang == "python":
            return self._python_to_mir(source)
        else:
            raise ValueError(f"不支持的语言: {lang}")

    def _from_mir(self, mir_program: any, lang: str) -> str:
        """从 MIR 转换为目标语言。"""
        if lang == "matha":
            return self._matha_to_mir.generate(mir_program)
        elif lang == "c":
            from src.mir_codegen import MIRToCGenerator
            return MIRToCGenerator().generate(mir_program)
        elif lang == "python":
            from src.mir_codegen import MIRToPythonGenerator
            return MIRToPythonGenerator().generate(mir_program)
        else:
            raise ValueError(f"不支持的目标语言: {lang}")

    def _c_to_mir(self, c_code: str) -> any:
        """将 C 代码解析为 MIR。"""
        import re
        from src.mir import MIRProgram, MIRFunction, MIRCallInstr, MIRInstrType, MIRArithInstr, MIRConstInstr

        program = MIRProgram()
        func_pattern = re.compile(r'double\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*)\}', re.DOTALL)

        for match in func_pattern.finditer(c_code):
            name = match.group(1)
            params_str = match.group(2).strip()
            body = match.group(3)

            params = [p.strip().split()[-1] for p in params_str.split(",") if p.strip()] if params_str else []

            func = MIRFunction(name=name, params=params, param_types=["double"] * len(params), return_type="double")

            for line in body.strip().split("\n"):
                line = line.strip().rstrip(";").strip()
                if not line or line.startswith("//") or line.startswith("/*"):
                    continue

                # 函数调用: double x = sin(y);
                call_match = re.match(r'double\s+(\w+)\s*=\s*(\w+)\(([^)]*)\);', line)
                if call_match:
                    result = call_match.group(1)
                    func_name = call_match.group(2)
                    args = [a.strip() for a in call_match.group(3).split(",")] if call_match.group(3) else []
                    func.instructions.append(
                        MIRCallInstr(result, MIRInstrType.CALL, args,
                                   {"func_name": func_name, "c_func": func_name, "lib": "math"})
                    )
                    continue

                # 算术运算: double x = a + b;
                arith_match = re.match(r'double\s+(\w+)\s*=\s*([^;]+);', line)
                if arith_match:
                    result = arith_match.group(1)
                    expr = arith_match.group(2).strip()
                    parts = re.split(r'([+\-*/%])', expr, maxsplit=1)
                    if len(parts) == 3:
                        left, op, right = parts
                        func.instructions.append(
                            MIRArithInstr(result, MIRInstrType.ADD, [left.strip(), right.strip()], {"op": op})
                        )
                    continue

            program.functions[name] = func

        return program

    def _python_to_mir(self, py_code: str) -> any:
        """将 Python 代码解析为 MIR。"""
        import re
        from src.mir import MIRProgram, MIRFunction, MIRCallInstr, MIRInstrType, MIRArithInstr, MIRConstInstr

        program = MIRProgram()
        func_pattern = re.compile(r'def\s+(\w+)\s*\(([^)]*)\):\s*\n((?:    .+\n)*)', re.MULTILINE)

        for match in func_pattern.finditer(py_code):
            name = match.group(1)
            params_str = match.group(2).strip()
            body = match.group(3)

            params = [p.strip() for p in params_str.split(",") if p.strip()] if params_str else []

            func = MIRFunction(name=name, params=params, param_types=["double"] * len(params), return_type="double")

            for line in body.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 函数调用: x = sin(y)
                call_match = re.match(r'(\w+)\s*=\s*math\.(\w+)\(([^)]*)\)', line)
                if call_match:
                    result = call_match.group(1)
                    func_name = call_match.group(2)
                    args = [a.strip() for a in call_match.group(3).split(",")] if call_match.group(3) else []
                    func.instructions.append(
                        MIRCallInstr(result, MIRInstrType.CALL, args,
                                   {"func_name": func_name, "c_func": func_name, "lib": "math"})
                    )
                    continue

                # 算术运算: x = a + b
                arith_match = re.match(r'(\w+)\s*=\s*([^=]+)', line)
                if arith_match:
                    result = arith_match.group(1)
                    expr = arith_match.group(2).strip()
                    parts = re.split(r'([+\-*/%])', expr, maxsplit=1)
                    if len(parts) == 3:
                        left, op, right = parts
                        func.instructions.append(
                            MIRArithInstr(result, MIRInstrType.ADD, [left.strip(), right.strip()], {"op": op})
                        )
                    continue

            program.functions[name] = func

        return program

    def batch_convert(self, source: str, target_langs: list) -> dict:
        """批量转换为多种目标语言。"""
        results = {}
        for lang in target_langs:
            try:
                results[lang] = self.convert(source, "matha", lang)
            except Exception as e:
                results[lang] = f"错误: {e}"
        return results


# ============================================================
# 公共 API
# ============================================================

def matha_to_mir(matha_source: str) -> str:
    """将 Matha 源码转换为 MIR 文本表示。"""
    gen = MathaToMIRGenerator()
    return gen.generate_from_matha(matha_source)


def convert(source: str, source_lang: str, target_lang: str) -> str:
    """通用转换器。"""
    converter = MathaConverter()
    return converter.convert(source, source_lang, target_lang)


def convert_all(source: str, source_lang: str = "matha") -> dict:
    """转换为所有支持的语言。"""
    converter = MathaConverter()
    return converter.batch_convert(source, converter.TARGETS)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MIRToMathaGenerator",
    "MathaToMIRGenerator",
    "MathaConverter",
    "matha_to_mir",
    "convert",
    "convert_all",
]
