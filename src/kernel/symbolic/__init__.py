"""Matha 内核符号微积分引擎（纯标准库，阶段 3 下沉）。

替代原先挂在 sympy 上的全部符号微积分能力。模块划分：

==================  ==================================================
``expr.py``         Expr 代数层（Num/Var/Neg/Add/Sub/Mul/Div/Pow/Log/FuncCall）
                    + 文本→AST 的 SymbolicParser（原 src/symbolic.py A 组迁入）
``astnodes.py``     ASTNode / ASTNodeType 通用树形表示
``simplify.py``     展开 / 合并同类项 / 约简 / 标准形（内部稀疏多项式表示）
``diff.py``         求导（链式法则函数表、n 阶、偏导）
``integrate.py``    积分（幂/换元/分部/有理式；定积分含自适应 Simpson 兜底）
``limit.py``        极限（代入 / 主部 / 洛必达 / Richardson 外推）
``series.py``       泰勒与级数求和（Faulhaber / telescoping / Basel / e^x）
``ode.py``          常微分方程（直接积分 / 可分离 / 一阶线性 / 二阶常系数齐次）
``domain.py``       连续域与累值界（替 sympy.calculus.util 的两个入口）
``latex.py``        文本解析 + 标准串 / LaTeX / Unicode 美观发射
==================  ==================================================

**不允许静默降级**：算法覆盖不到的表达式一律抛各自模块的
``UnsupportedExpression`` / ``LimitUndetermined`` / ``SeriesUndetermined`` /
``OdeUnsupported`` / ``DomainUndetermined``，由 ``src.stdlib.calculus_symbolic``
门面转成显式错误。能力对照与缺口清单见 ``docs/symbolic_parity.md``。

本包按需惰性加载（``import src.kernel.symbolic`` 不付出全部模块的导入成本）。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = [
    # 数据层
    "Expr", "Num", "Var", "Neg", "Add", "Sub", "Mul", "Div", "Pow", "Log",
    "FuncCall", "SymbolicParser", "to_expr", "symbolic", "symbol_expr",
    "ASTNode", "ASTNodeType", "ast_to_dict",
    # 算法层
    "simplify_expr", "diff_expr", "eval_expr",
    "expand", "collect", "cancel", "canonical",
    "differentiate", "nth_derivative", "partial_derivative",
    "integrate", "definite", "numerical_definite",
    "limit", "taylor", "maclaurin", "sum_series",
    "solve_ode", "continuous_domain", "accumulated_bounds",
    # 输出 / 解析
    "parse", "parse_equation", "to_str", "to_latex", "to_pretty",
    # 异常
    "UnsupportedExpression", "LimitUndetermined", "SeriesUndetermined",
    "OdeUnsupported", "DomainUndetermined",
]

# 名字 → (模块名, 模块内属性名)
_LAZY: dict[str, tuple[str, str]] = {
    "Expr": ("expr", "Expr"), "Num": ("expr", "Num"), "Var": ("expr", "Var"),
    "Neg": ("expr", "Neg"), "Add": ("expr", "Add"), "Sub": ("expr", "Sub"),
    "Mul": ("expr", "Mul"), "Div": ("expr", "Div"), "Pow": ("expr", "Pow"),
    "Log": ("expr", "Log"), "FuncCall": ("expr", "FuncCall"),
    "SymbolicParser": ("expr", "SymbolicParser"), "to_expr": ("expr", "to_expr"),
    "symbolic": ("expr", "symbolic"), "symbol_expr": ("expr", "symbol_expr"),
    "eval_expr": ("expr", "eval_expr"), "ast_to_dict": ("expr", "ast_to_dict"),
    "ASTNode": ("astnodes", "ASTNode"), "ASTNodeType": ("astnodes", "ASTNodeType"),
    "simplify_expr": ("simplify", "simplify_expr"),
    "expand": ("simplify", "expand"), "collect": ("simplify", "collect"),
    "cancel": ("simplify", "cancel"), "canonical": ("simplify", "canonical"),
    "diff_expr": ("diff", "diff_expr"),
    "differentiate": ("diff", "differentiate"),
    "nth_derivative": ("diff", "nth_derivative"),
    "partial_derivative": ("diff", "partial_derivative"),
    "integrate": ("integrate", "integrate"),
    "definite": ("integrate", "definite"),
    "numerical_definite": ("integrate", "numerical_definite"),
    "limit": ("limit", "limit"),
    "taylor": ("series", "taylor"), "maclaurin": ("series", "maclaurin"),
    "sum_series": ("series", "sum_series"),
    "solve_ode": ("ode", "solve_ode"),
    "continuous_domain": ("domain", "continuous_domain"),
    "accumulated_bounds": ("domain", "accumulated_bounds"),
    "parse": ("latex", "parse"), "parse_equation": ("latex", "parse_equation"),
    "to_str": ("latex", "to_str"), "to_latex": ("latex", "to_latex"),
    "to_pretty": ("latex", "to_pretty"),
    "UnsupportedExpression": ("diff", "UnsupportedExpression"),
    "LimitUndetermined": ("limit", "LimitUndetermined"),
    "SeriesUndetermined": ("series", "SeriesUndetermined"),
    "OdeUnsupported": ("ode", "OdeUnsupported"),
    "DomainUndetermined": ("domain", "DomainUndetermined"),
}


def __getattr__(name: str):
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module
    mod = import_module(f"{__name__}.{target[0]}")
    value = getattr(mod, target[1])
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(list(globals()) + list(_LAZY)))


# 子模块名与函数名同名（``integrate`` / ``limit``）时，import 机制会把包属性
# 覆盖成模块对象，导致 `from src.kernel.symbolic import limit` 拿到模块还是函数
# 取决于导入顺序。这两个子模块本就被 domain/ode 无条件依赖，故在此显式绑回函数，
# 让包级名字确定下来（调用方仍建议直接 `from src.kernel.symbolic.limit import limit`）。
from src.kernel.symbolic.integrate import integrate as _integrate_fn  # noqa: E402
from src.kernel.symbolic.limit import limit as _limit_fn  # noqa: E402

globals()["integrate"] = _integrate_fn
globals()["limit"] = _limit_fn
del _integrate_fn, _limit_fn
