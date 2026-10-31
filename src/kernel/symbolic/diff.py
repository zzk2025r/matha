"""内核符号引擎 · 求导（纯标准库）。

在 `expr.py` 数据层之上提供**比 `Expr.diff()` 更完整**的微分算法：

- ``diff_expr``：兼容原 ``src/symbolic.py`` 的薄封装（语义不变）。
- ``differentiate``：内核主求导器，带链式法则的函数表
  （sin/cos/tan/cot/sec/csc、sinh/cosh/tanh、exp/log/ln/sqrt/abs、asin/acos/atan），
  结果统一过 ``simplify.canonical`` 标准形。
- ``nth_derivative``：n 阶导数。
- ``partial_derivative``：偏导数（多元，按变量顺序依次求导）。
- ``leading_term`` / ``poly_in``：主部提取，供 `limit.py`、`series.py` 复用。

未知函数**不做静默猜测**：抛 ``UnsupportedExpression``，由调用方如实报告缺口。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)
from src.kernel.symbolic.simplify import canonical, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = [
    "diff_expr", "differentiate", "nth_derivative", "partial_derivative",
    "Derivative", "UnsupportedExpression", "leading_term", "poly_in",
]


class UnsupportedExpression(ValueError):
    """内核符号引擎有意不覆盖的能力（如实暴露，不伪造结果）。"""


def diff_expr(expr: Expr, var: str = 'x') -> Expr:
    """兼容原 ``src/symbolic.py`` 的求导入口（语义逐字保留）。"""
    return expr.diff(var)


# ═══════════════════════════════════════════════════════════════════════════════
#  一元函数导数表：f(u) → df/du
# ═══════════════════════════════════════════════════════════════════════════════

def _f(name: str, arg: Expr) -> FuncCall:
    return FuncCall(name, [arg])


DERIV_RULES = {
    "sin": lambda u: _f("cos", u),
    "cos": lambda u: Neg(_f("sin", u)),
    "tan": lambda u: Div(Num(1), Pow(_f("cos", u), Num(2))),
    "cot": lambda u: Neg(Div(Num(1), Pow(_f("sin", u), Num(2)))),
    "sec": lambda u: Mul(_f("sec", u), _f("tan", u)),
    "csc": lambda u: Neg(Mul(_f("csc", u), _f("cot", u))),
    "exp": lambda u: _f("exp", u),
    "log": lambda u: Div(Num(1), u),
    "ln": lambda u: Div(Num(1), u),
    "sqrt": lambda u: Div(Num(1), Mul(Num(2), _f("sqrt", u))),
    "abs": lambda u: Div(u, _f("abs", u)),
    "sinh": lambda u: _f("cosh", u),
    "cosh": lambda u: _f("sinh", u),
    "tanh": lambda u: Sub(Num(1), Pow(_f("tanh", u), Num(2))),
    "asin": lambda u: Div(Num(1), _f("sqrt", Sub(Num(1), Pow(u, Num(2))))),
    "acos": lambda u: Neg(Div(Num(1), _f("sqrt", Sub(Num(1), Pow(u, Num(2)))))),
    "atan": lambda u: Div(Num(1), Add(Num(1), Pow(u, Num(2)))),
}


class Derivative:
    """导数的结构化表示（供 `ode.py` 与阶段 4 逐规则对拍使用）。"""

    __slots__ = ("expr", "var", "order")

    def __init__(self, expr: Expr, var: str, order: int = 1):
        self.expr = expr
        self.var = var
        self.order = order

    def doit(self) -> Expr:
        return nth_derivative(self.expr, self.var, self.order)

    def __str__(self) -> str:
        sup = f"^{self.order}" if self.order > 1 else ""
        return f"d{sup}/d{self.var}{sup}({self.expr})"


def differentiate(expr: Expr, var: str = "x", *, do_simplify: bool = True) -> Expr:
    """对 ``var`` 求导并过标准形。

    Examples:
        >>> str(differentiate(symbol_expr("x**2")))
        '2*x'
        >>> str(differentiate(symbol_expr("sin(x)")))
        'cos(x)'
    """
    out = _diff_raw(_wrap_log(expr), var)
    return canonical(out) if do_simplify else out


def nth_derivative(expr: Expr, var: str, order: int) -> Expr:
    if order < 0:
        raise UnsupportedExpression(f"负阶导数不支持: order={order}")
    out = expr
    for _ in range(order):
        out = differentiate(out, var)
    return out


def partial_derivative(expr: Expr, *vars: str) -> Expr:
    """依次对多个变量求偏导（混合偏导按给定顺序）。"""
    out = expr
    for v in vars:
        out = differentiate(out, v)
    return out


def _wrap_log(e: Expr) -> Expr:
    """`log(u)`/`ln(u)` 归一为 `Log` 节点；`log(u, base)` 保持 FuncCall 原样。"""
    if isinstance(e, FuncCall):
        if e.name in ("log", "ln") and len(e.args) == 1:
            return Log(_wrap_log(e.args[0]))
        return FuncCall(e.name, [_wrap_log(a) for a in e.args])
    if isinstance(e, Log):
        return Log(_wrap_log(e.expr))
    if isinstance(e, Neg):
        return Neg(_wrap_log(e.expr))
    if isinstance(e, Pow):
        return Pow(_wrap_log(e.base), _wrap_log(e.exponent))
    if isinstance(e, (Add, Sub, Mul, Div)):
        return type(e)(*[_wrap_log(k) for k in e._children()])
    return e


def _diff_raw(e: Expr, var: str) -> Expr:
    if isinstance(e, Num):
        return Num(0)
    if isinstance(e, Var):
        return Num(1) if e.name == var else Num(0)
    if isinstance(e, Neg):
        return Neg(_diff_raw(e.expr, var))
    if isinstance(e, Add):
        return Add(_diff_raw(e.left, var), _diff_raw(e.right, var))
    if isinstance(e, Sub):
        return Sub(_diff_raw(e.left, var), _diff_raw(e.right, var))
    if isinstance(e, Mul):
        a, b = e.left, e.right
        return Add(Mul(_diff_raw(a, var), b), Mul(a, _diff_raw(b, var)))
    if isinstance(e, Div):
        n, d = e.numerator, e.denominator
        return Div(Sub(Mul(_diff_raw(n, var), d), Mul(n, _diff_raw(d, var))),
                   Pow(d, Num(2)))
    if isinstance(e, Pow):
        return _diff_pow(e, var)
    if isinstance(e, Log):
        return Div(_diff_raw(e.expr, var), e.expr)
    if isinstance(e, FuncCall):
        return _diff_func(e, var)
    raise UnsupportedExpression(f"未实现的表达式类型: {type(e).__name__}")


def _diff_pow(e: Pow, var: str) -> Expr:
    base, exponent = e.base, e.exponent
    db, de = _diff_raw(base, var), _diff_raw(exponent, var)
    if isinstance(exponent, Num):
        n = exponent.value
        # 幂法则 + 链式法则：d/dx u^n = n*u^(n-1)*u'
        return Mul(Mul(Num(n), Pow(base, Num(n - 1))), db)
    if not e.free_vars() or var not in e.free_vars():
        return Num(0)
    # 一般情形 f^g：f^g * (g' ln f + g f'/f)
    return Mul(e, Add(Mul(de, Log(base)), Mul(exponent, Div(db, base))))


def _diff_func(e: FuncCall, var: str) -> Expr:
    if len(e.args) != 1:
        raise UnsupportedExpression(f"仅一元函数支持求导: {e.name}({len(e.args)} 参)")
    u = e.args[0]
    rule = DERIV_RULES.get(e.name)
    if rule is None:
        raise UnsupportedExpression(
            f"内核无 {e.name}(u) 的求导规则（缺口见 docs/symbolic_parity.md）")
    return Mul(rule(u), _diff_raw(u, var))


# ═══════════════════════════════════════════════════════════════════════════════
#  主部提取：供 limit.py / series.py / integrate.py 复用
# ═══════════════════════════════════════════════════════════════════════════════

def poly_in(expr: Expr, var: str) -> dict[float, float] | None:
    """把表达式压成 {指数: 系数}（要求是关于 ``var`` 的广义多项式）。

    含其他原子（如 ``y``、``sin(x)``）时返回 None，由调用方换策略。
    """
    p = poly(canonical(expr))
    if p is None:
        return None
    out: dict[float, float] = {}
    for key, coef in p.items():
        power = 0.0
        other = 0.0
        for atom, exp in key:
            if atom == var:
                power += exp
            else:
                other += abs(exp)
        if other != 0.0:
            return None
        out[power] = out.get(power, 0.0) + coef
    return out


def leading_term(expr: Expr, var: str, at_infinity: bool = False) -> tuple[float, float] | None:
    """主部 (系数, 指数)：``x→a`` 取最低次项，``x→∞`` 取最高次项。"""
    p = poly_in(expr, var)
    if p is None:
        return None
    items = [(e, c) for e, c in p.items() if c != 0]
    if not items:
        return None
    e, c = max(items) if at_infinity else min(items)
    return (c, e)
