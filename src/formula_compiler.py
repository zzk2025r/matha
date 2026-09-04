# -*- coding: utf-8 -*-
"""
Matha 公式编译器集成（Formula Compiler Integration）

连接公式系统（formula_system）与 MIR 编译器，实现：
  1. Formula → MIR 编译
  2. MIR → 多语言代码生成
  3. 公式优化后重新编译
  4. 公式生长结果自动编译为可执行代码
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.symbolic import Expr, Var, Num, Mul, Div, Add, Sub, Pow, Neg, FuncCall, symbol_expr
from src.formula_system import Formula, FormulaRegistry
from src.matha.growth import FormulaGrowthEngine, GrowthRecord

logger = logging.getLogger("matha.formula_compiler")


# ============================================================
#  公式 → MIR 编译
# ============================================================

def formula_to_mir(func_name: str, formula: Formula) -> dict:
    """将 Formula 编译为 MIR 函数字典。

    返回格式：
        {
            "name": str,
            "params": list[str],
            "instructions": list[dict],
            "returns": str,
        }
    """
    expr = formula.expr
    instructions = _expr_to_mir_instructions(expr, formula.params)
    result_var = formula.params[0] if formula.params else "result"

    return {
        "name": func_name,
        "params": list(formula.params),
        "instructions": instructions,
        "returns": result_var,
        "metadata": {
            "domain": formula.domain,
            "category": formula.category,
            "notes": formula.notes,
        },
    }


def _expr_to_mir_instructions(expr: Expr, params: list[str]) -> list[dict]:
    """将符号表达式转换为 MIR 指令序列。"""
    instructions: list[dict] = []
    _expr_to_mir_recursive(expr, instructions, {})
    return instructions


def _expr_to_mir_recursive(expr: Expr, instructions: list, var_map: dict) -> str:
    """递归将表达式转换为 MIR，返回结果变量名。"""
    if isinstance(expr, Num):
        result = f"%{id(expr)}"
        instructions.append({"op": "load_const", "result": result, "value": expr.value})
        return result

    if isinstance(expr, Var):
        # 检查是否已在参数中
        if expr.name in var_map:
            return var_map[expr.name]
        return f"%{expr.name}"

    if isinstance(expr, Add):
        left = _expr_to_mir_recursive(expr.left, instructions, var_map)
        right = _expr_to_mir_recursive(expr.right, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "+", "operands": [left, right], "result": result})
        return result

    if isinstance(expr, Sub):
        left = _expr_to_mir_recursive(expr.left, instructions, var_map)
        right = _expr_to_mir_recursive(expr.right, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "-", "operands": [left, right], "result": result})
        return result

    if isinstance(expr, Mul):
        left = _expr_to_mir_recursive(expr.left, instructions, var_map)
        right = _expr_to_mir_recursive(expr.right, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "*", "operands": [left, right], "result": result})
        return result

    if isinstance(expr, Div):
        left = _expr_to_mir_recursive(expr.left, instructions, var_map)
        right = _expr_to_mir_recursive(expr.right, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "/", "operands": [left, right], "result": result})
        return result

    if isinstance(expr, Pow):
        left = _expr_to_mir_recursive(expr.left, instructions, var_map)
        right = _expr_to_mir_recursive(expr.right, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "**", "operands": [left, right], "result": result})
        return result

    if isinstance(expr, Neg):
        inner = _expr_to_mir_recursive(expr.expr, instructions, var_map)
        result = f"%{id(expr)}"
        instructions.append({"op": "neg", "operands": [inner], "result": result})
        return result

    if isinstance(expr, FuncCall):
        args = []
        for arg in expr.args:
            args.append(_expr_to_mir_recursive(arg, instructions, var_map))
        result = f"%{id(expr)}"
        instructions.append({"op": "call", "func_name": expr.name, "operands": args, "result": result})
        return result

    # 回退：直接求值
    try:
        val = expr.evaluate({})
        if isinstance(val, (int, float)):
            result = f"%{id(expr)}"
            instructions.append({"op": "load_const", "result": result, "value": val})
            return result
    except Exception:
        pass

    return f"%unknown_{id(expr)}"


# ============================================================
#  公式编译器
# ============================================================

@dataclass
class FormulaCompileResult:
    """公式编译结果。"""
    success: bool
    formula_name: str
    mir_code: Optional[dict]
    python_code: str = ""
    c_code: str = ""
    error: str = ""
    optimizations: list[str] = field(default_factory=list)


class FormulaCompiler:
    """公式编译器：Formula → MIR → 多语言代码。"""

    def __init__(self, registry: FormulaRegistry):
        self._registry = registry
        self._compile_cache: dict[str, FormulaCompileResult] = {}

    def compile_formula(self, name: str, optimize: bool = True) -> FormulaCompileResult:
        """编译单个公式。"""
        if name in self._compile_cache:
            return self._compile_cache[name]

        formula = self._registry._formulas.get(name)
        if not formula:
            result = FormulaCompileResult(success=False, formula_name=name, mir_code=None,
                                          error=f"公式不存在: {name}")
            self._compile_cache[name] = result
            return result

        try:
            mir = formula_to_mir(name, formula)
            optimizations = []
            if optimize:
                optimizations = self._apply_optimizations(mir)

            python_code = self._mir_to_python(name, mir)
            c_code = self._mir_to_c(name, mir)

            result = FormulaCompileResult(
                success=True,
                formula_name=name,
                mir_code=mir,
                python_code=python_code,
                c_code=c_code,
                optimizations=optimizations,
            )
        except Exception as e:
            result = FormulaCompileResult(success=False, formula_name=name, mir_code=None,
                                          error=str(e))

        self._compile_cache[name] = result
        return result

    def _apply_optimizations(self, mir: dict) -> list[str]:
        """对 MIR 应用公式优化。"""
        optimizations = []
        # 常量折叠
        instructions = mir.get("instructions", [])
        new_instructions = []
        for instr in instructions:
            op = instr.get("op", "")
            if op in ("+", "-", "*", "/") and instr.get("value") is not None:
                # 已经是常量，跳过
                continue
            if op in ("+", "-") and instr.get("operands"):
                try:
                    left = float(instr["operands"][0].lstrip("%")) if instr["operands"][0].startswith("%") else None
                    right = float(instr["operands"][1].lstrip("%")) if instr["operands"][1].startswith("%") else None
                    if left is not None and right is not None:
                        result = eval(f"{left} {op} {right}")
                        if isinstance(result, (int, float)):
                            new_instructions.append({"op": "load_const", "result": instr.get("result", ""), "value": result})
                            optimizations.append(f"常量折叠: {left} {op} {right} = {result}")
                            continue
                except (ValueError, ZeroDivisionError):
                    pass
            new_instructions.append(instr)
        mir["instructions"] = new_instructions
        return optimizations

    def _mir_to_python(self, name: str, mir: dict) -> str:
        """MIR → Python 代码。"""
        lines = [f"def {name}({', '.join(mir['params'])}):"]
        for instr in mir.get("instructions", []):
            op = instr.get("op", "")
            result = instr.get("result", "")
            if op == "load_const":
                lines.append(f"    {result.lstrip('%')} = {instr['value']}")
            elif op in ("+", "-", "*", "/", "**"):
                lines.append(f"    {result.lstrip('%')} = {instr['operands'][0].lstrip('%')} {op} {instr['operands'][1].lstrip('%')}")
            elif op == "call":
                args = ", ".join(a.lstrip("%") for a in instr.get("operands", []))
                lines.append(f"    {result.lstrip('%')} = {instr['func_name']}({args})")
        ret = mir.get("returns", "result")
        lines.append(f"    return {ret}")
        return "\n".join(lines)

    def _mir_to_c(self, name: str, mir: dict) -> str:
        """MIR → C 代码。"""
        params = ", ".join(f"double {p}" for p in mir["params"])
        lines = [f"double {name}({params}) {{"]
        for instr in mir.get("instructions", []):
            op = instr.get("op", "")
            result = instr.get("result", "").lstrip("%")
            if op == "load_const":
                lines.append(f"    double {result} = {instr['value']};")
            elif op in ("+", "-", "*", "/"):
                lines.append(f"    double {result} = {instr['operands'][0].lstrip('%')} {op} {instr['operands'][1].lstrip('%')};")
            elif op == "**":
                lines.append(f"    double {result} = pow({instr['operands'][0].lstrip('%')}, {instr['operands'][1].lstrip('%')});")
            elif op == "call":
                args = ", ".join(a.lstrip("%") for a in instr.get("operands", []))
                lines.append(f"    double {result} = {instr['func_name']}({args});")
        ret = mir.get("returns", "result")
        lines.append(f"    return {ret};")
        lines.append("}")
        return "\n".join(lines)

    def compile_all(self, optimize: bool = True) -> list[FormulaCompileResult]:
        """编译所有公式。"""
        return [self.compile_formula(name, optimize)
                for name in self._registry.list_formulas()]

    def clear_cache(self) -> None:
        """清除编译缓存。"""
        self._compile_cache.clear()


# ============================================================
#  公式生长 + 编译一体化
# ============================================================

class FormulaGrowthCompiler:
    """公式生长 + 编译一体化引擎。

    流程：
      1. FormulaGrowthEngine 生成新公式
      2. FormulaCompiler 编译为新公式的 MIR + 多语言代码
      3. 注册到公式库
      4. 自动执行优化
    """

    def __init__(self, registry: FormulaRegistry):
        self._registry = registry
        self._growth_engine = FormulaGrowthEngine(registry)
        self._compiler = FormulaCompiler(registry)

    def auto_grow_and_compile(self, max_combinations: int = 5,
                               max_derivatives: int = 10) -> dict:
        """自动化成长 + 编译：成长后自动编译所有新公式。

        Returns:
            {
                "growth_stats": {"compose": N, "infer": N, "generate": N},
                "compiled_count": N,
                "compile_results": [...],
            }
        """
        # 1. 自动化成长
        growth_stats = self._growth_engine.auto_grow(
            max_combinations=max_combinations,
            max_derivatives=max_derivatives,
        )
        logger.info(f"  [成长编译] 成长统计: {growth_stats}")

        # 2. 注册成长结果
        registered = self._growth_engine.register_all_grown()
        logger.info(f"  [成长编译] 注册新公式: {registered} 个")

        # 3. 编译所有公式
        results = self._compiler.compile_all(optimize=True)
        compiled = sum(1 for r in results if r.success)

        # 4. 编译成长公式
        compile_results = []
        for name in self._growth_engine._grown_formulas:
            r = self._compiler.compile_formula(name, optimize=True)
            if r.success:
                compile_results.append({
                    "name": r.formula_name,
                    "python": r.python_code,
                    "c": r.c_code,
                    "optimizations": r.optimizations,
                })

        return {
            "growth_stats": growth_stats,
            "registered": registered,
            "compiled_count": compiled,
            "compile_results": compile_results,
        }

    def grow_and_compile(self, op_type: str, **kwargs) -> dict:
        """单次操作 + 编译。"""
        if op_type == "compose":
            results = self._growth_engine.compose(kwargs.get("names", []))
        elif op_type == "infer":
            results = self._growth_engine.infer(
                kwargs.get("formula_name", ""),
                var=kwargs.get("var"),
                elim_var=kwargs.get("elim_var"),
                substitution=kwargs.get("substitution"),
            )
        elif op_type == "generate":
            results = self._growth_engine.generate(
                kwargs.get("name", "新公式"),
                kwargs.get("target", "F"),
                kwargs.get("variables", ["x", "y"]),
                constraints=kwargs.get("constraints"),
            )
        else:
            return {"error": f"未知操作类型: {op_type}"}

        # 编译结果
        compiled = []
        for r in results:
            if r.success:
                cr = self._compiler.compile_formula(r.result_name, optimize=True)
                compiled.append({
                    "name": r.result_name,
                    "success": cr.success,
                    "python": cr.python_code,
                    "optimizations": cr.optimizations,
                })
        return {"results": compiled}


# ============================================================
#  便捷函数
# ============================================================

def compile_formula(name: str, registry: FormulaRegistry = None, optimize: bool = True) -> FormulaCompileResult:
    """编译单个公式。"""
    if registry is None:
        from src.formula_system import get_formula_registry
        registry = get_formula_registry()
    compiler = FormulaCompiler(registry)
    return compiler.compile_formula(name, optimize)


def auto_grow_and_compile(registry: FormulaRegistry = None,
                           max_combinations: int = 5,
                           max_derivatives: int = 10) -> dict:
    """自动化成长 + 编译。"""
    if registry is None:
        from src.formula_system import get_formula_registry
        registry = get_formula_registry()
    fc = FormulaGrowthCompiler(registry)
    return fc.auto_grow_and_compile(max_combinations, max_derivatives)
