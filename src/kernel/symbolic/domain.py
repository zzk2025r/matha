"""内核符号引擎 · 定义域 / 累值界（纯标准库）。

替换原先挂在 ``sympy.calculus.util`` 上的两个名字（它们在旧代码里只被 import、
从未被真正调用，现由内核提供真实实现并作为公开 API 暴露）：

- ``continuous_domain(expr, var)``：返回使 ``expr`` 连续的区间并集（开区间列表），
  依据分母零点、``sqrt`` 非正、``log`` 非正、``asin/acos`` 越界等奇点集合求补。
- ``accumulated_bounds(expr, var)``：``x→∞`` 处的累值界 ``(liminf, limsup)``
  （对齐 sympy ``AccumulationBounds``）。

无法判定时抛 ``DomainUndetermined``，不返回「全域」这种乐观默认值。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)
from src.kernel.symbolic.limit import limit, LimitUndetermined
from src.kernel.symbolic.simplify import canonical, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["continuous_domain", "accumulated_bounds", "DomainUndetermined",
           "Interval"]


class DomainUndetermined(ValueError):
    """奇点结构超出内核判定范围（如实失败）。"""


class Interval:
    """区间 ``(< lo, hi >)`` 与开/闭标记；字符串形式对齐 sympy 的 ``Interval``。"""

    __slots__ = ("lo", "hi", "lo_open", "hi_open")

    def __init__(self, lo: float, hi: float, lo_open: bool = True, hi_open: bool = True):
        self.lo, self.hi = lo, hi
        self.lo_open, self.hi_open = lo_open, hi_open

    def __repr__(self) -> str:
        l = "(" if self.lo_open or math.isinf(self.lo) else "["
        r = ")" if self.hi_open or math.isinf(self.hi) else "]"
        lo = "-oo" if self.lo == -math.inf else _n(self.lo)
        hi = "oo" if self.hi == math.inf else _n(self.hi)
        return f"{l}{lo}, {hi}{r}"

    def contains(self, x: float) -> bool:
        if math.isinf(x):
            return False
        left = x > self.lo if self.lo_open else x >= self.lo
        right = x < self.hi if self.hi_open else x <= self.hi
        return left and right


def _n(v: float) -> str:
    r = round(v)
    return str(int(r)) if abs(v - r) < 1e-12 else repr(v)


# ═══════════════════════════════════════════════════════════════════════════════
#  连续域
# ═══════════════════════════════════════════════════════════════════════════════

def continuous_domain(expr: Expr, var: str = "x") -> list[Interval]:
    """``expr`` 关于 ``var`` 的连续区间并集（升序，补集形式由奇点构造）。

    Examples:
        >>> [str(i) for i in continuous_domain(symbol_expr("1/x"), "x")]
        ['(-oo, 0)', '(0, oo)']
    """
    e = canonical(expr)
    bad: list[float] = []
    strict: list[tuple[str, float]] = []      # ('gt'|'ge', 边界)
    _collect(e, bad, strict, var)
    for name, arg in _calls(e):
        if name in ("sqrt", "log", "ln"):
            for cond, bound in _constraint(arg, var):
                strict.append((cond, bound))
        elif name in ("asin", "acos"):
            # 定义域为闭区间 [-1, 1]：两端均为奇点边界（内部取值才连续）
            bad.append(-1.0)
            bad.append(1.0)
    points = sorted(set(bad))
    # 把 strict 约束折算为排除点：sqrt(x) 型 → x=0 为边界（开）
    for cond, bound in strict:
        if cond in ("gt", "ge") and bound not in points:
            points.append(bound)
    points = sorted(set(points))
    edges = [-math.inf] + points + [math.inf]
    out: list[Interval] = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        probe = _midpoint(lo, hi)
        if probe is None:
            continue
        if not _defined_at(e, var, probe):
            continue
        lo_open = lo == -math.inf or _excluded(e, var, lo) or _excluded(e, var, lo + 1e-9)
        hi_open = hi == math.inf or _excluded(e, var, hi) or _excluded(e, var, hi - 1e-9)
        out.append(Interval(lo, hi, lo_open, hi_open))
    if not out:
        raise DomainUndetermined(f"连续域为空/不可判定: {e}")
    return out


def _midpoint(lo: float, hi: float) -> float | None:
    if math.isinf(lo) and math.isinf(hi):
        return 0.0
    if math.isinf(lo):
        return hi - 1.0
    if math.isinf(hi):
        return lo + 1.0
    return (lo + hi) / 2.0


def _excluded(e: Expr, var: str, x: float) -> bool:
    return not _defined_at(e, var, x)


def _defined_at(e: Expr, var: str, x: float) -> bool:
    try:
        v = e.substitute(var, Num(float(x))).evaluate({})
    except Exception:
        return False
    return isinstance(v, (int, float)) and math.isfinite(v)


def _calls(e: Expr) -> list[tuple[str, Expr]]:
    out: list[tuple[str, Expr]] = []
    stack = [e]
    while stack:
        cur = stack.pop()
        if isinstance(cur, FuncCall):
            out.append((cur.name, cur.args[0]))
            stack.extend(cur.args)
        elif isinstance(cur, Log):
            out.append(("ln", cur.expr))
            stack.append(cur.expr)
        else:
            kids = cur._children()
            stack.extend(kids)
    return out


def _collect(e: Expr, bad: list[float], strict, var: str) -> None:
    """分母零点进入 ``bad``。"""
    stack = [e]
    while stack:
        cur = stack.pop()
        if isinstance(cur, Div):
            den = cur.denominator
            for r in _zeros(den, var):
                bad.append(r)
            stack.append(den)
            stack.append(cur.numerator)
        elif isinstance(cur, Pow) and isinstance(cur.exponent, Num) and cur.exponent.value < 0:
            for r in _zeros(cur.base, var):
                bad.append(r)
            stack.append(cur.base)
        else:
            stack.extend(cur._children())


def _zeros(arg: Expr, var: str) -> list[float]:
    """``arg`` 关于 ``var`` 的实零点（≤2 次精确；≥3 次用有理根 + 降次）。"""
    from src.kernel.symbolic.integrate import _roots, _to_dense
    p = poly(arg)
    if p is None:
        return []
    if not all(all(a == var for a, _ in k) for k in p):
        return []
    dense = _to_dense(p, var)
    if not dense:
        return []
    deg = len(dense) - 1
    if deg <= 0:
        return []
    roots = _roots(dense)
    return [r for r in roots if abs(r) < 1e12]


def _constraint(arg: Expr, var: str) -> list[tuple[str, float]]:
    """把 ``arg > 0`` 折算为对 var 的边界约束（仅覆盖一次/二次多项式）。"""
    zeros = _zeros(arg, var)
    if not zeros:
        return []
    return [("gt", z) for z in sorted(zeros)]


# ═══════════════════════════════════════════════════════════════════════════════
#  累值界 (liminf, limsup)
# ═══════════════════════════════════════════════════════════════════════════════

def accumulated_bounds(expr: Expr, var: str = "x") -> tuple[float, float]:
    """函数值的聚点界 ``(下界, 上界)``（全域取值范围的内包）。

    Examples:
        >>> accumulated_bounds(symbol_expr("sin(x)"), "x")
        (-1.0, 1.0)
        >>> accumulated_bounds(symbol_expr("x**2"), "x")
        (0.0, inf)
    """
    e = canonical(expr)
    # 振荡型：单个 sin/cos（可带变幅）的界为±振幅；和式/幂乘积未覆盖
    names = {n for n, _ in _calls(e)}
    if names & {"sin", "cos"}:
        factors = _fct(e)
        trig = [f for f in factors if _is_trig(f)]
        others = [f for f in factors if not _is_trig(f)]
        if len(trig) != 1:
            raise DomainUndetermined(
                f"三角和式的累值界需极值分析，内核未覆盖: {e}")
        tf = trig[0]
        if isinstance(tf, Pow):        # sin(x)**n / cos(x)**n
            if others or not _is_even_int(tf.exponent):
                raise DomainUndetermined(
                    f"三角幂乘积的累值界需极值分析，内核未覆盖: {e}")
            return _z(0.0), 1.0         # 偶次幂恒 >= 0 且 <= 1
        if not isinstance(tf, FuncCall):
            raise DomainUndetermined(f"累值界超出内核判据: {e}")
        amp = 1.0
        if others:
            try:
                lim = limit(_chain_mul(others), var, math.inf)
            except LimitUndetermined:
                raise DomainUndetermined(
                    f"累值界需振幅极限，内核未判定: {e}")
            if math.isinf(lim):
                return (-math.inf, math.inf)
            amp = abs(lim)
        return (-amp, amp)
    pv = _poly_bounds(e, var)
    if pv is not None:
        return pv
    ep = _endpoint_bounds(e, var)
    if ep is not None:
        return ep
    raise DomainUndetermined(f"累值界不可判定（内核缺口）: {e}")


def _z(v: float) -> float:
    """归一化 ``-0.0``，避免界输出出现「负零」这种伪精度。"""
    return 0.0 if v == 0 else v


def _is_even_int(exponent: Expr) -> bool:
    return (isinstance(exponent, Num) and float(exponent.value).is_integer()
            and int(exponent.value) > 0 and int(exponent.value) % 2 == 0)


def _chain_mul(parts: list[Expr]) -> Expr:
    out: Expr = parts[0]
    for f in parts[1:]:
        out = Mul(out, f)
    return out


def _poly_bounds(e: Expr, var: str) -> tuple[float, float] | None:
    """纯多项式：奇次→ (-oo, oo)；偶次→ 极值点与无穷端的组合。"""
    from src.kernel.symbolic.integrate import _roots, _to_dense
    p = poly(e)
    if p is None:
        return None
    if not all(all(a == var for a, _ in k) for k in p):
        return None
    if not all(float(ex).is_integer() and ex > 0 for k in p for _, ex in k):
        return None                       # 分数/负次幂（x**0.5、x**-1）非多项式
    dense = _to_dense(p, var)
    if not dense:                         # 含负指数（有理非多项式）→ 不在此定界
        return None
    deg = len(dense) - 1
    if deg <= 0:
        c = dense[-1]
        return (c, c)
    lead = dense[0]
    if deg % 2 == 1:
        return (-math.inf, math.inf)
    # 临界点：f' 的实零点
    dvec = [dense[i] * (deg - i) for i in range(deg)]
    crit = [r for r in _roots(dvec) if abs(r) < 1e12]
    vals = [v for v in (_eval_at(e, var, r) for r in crit) if v is not None]
    if not vals:
        return None                        # 临界点超出内核求根能力→ 不猜
    if lead > 0:
        return (_z(min(vals)), math.inf)
    return (-math.inf, _z(max(vals)))


def _endpoint_bounds(e: Expr, var: str) -> tuple[float, float] | None:
    """逐连续区间取两端点的单侧极限，min/max 即为聚点界。

    适用于单调分枝组成的函数（1/x、1/x²、log(x)、sqrt(x)、exp(±x)）；
    区间内部有极值的函数不属于此判据范围（由 `_poly_bounds` 等先接）。
    """
    try:
        dom = continuous_domain(e, var)
    except DomainUndetermined:
        return None
    lo, hi = math.inf, -math.inf
    for iv in dom:
        for edge, approach in ((iv.lo, "+"), (iv.hi, "-")):
            try:
                v = limit(e, var, edge, approach)
            except LimitUndetermined:
                return None
            except Exception:
                return None
            if v is None:
                return None
            lo = min(lo, v)
            hi = max(hi, v)
    if lo == math.inf or hi == -math.inf:
        return None
    return (_z(lo), _z(hi))


def _eval_at(e: Expr, var: str, x: float) -> float | None:
    try:
        v = e.substitute(var, Num(float(x))).evaluate({})
    except Exception:
        return None
    if isinstance(v, complex):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _strip_trig(e: Expr) -> Expr | None:
    """从 ``c*sin(u)`` 之类乘积中剥掉三角因子，返回余下部分。"""
    factors = _fct(e)
    rest = [f for f in factors if not _is_trig(f)]
    if len(rest) == len(factors):
        return None
    if not rest:
        return Num(1)
    out = rest[0]
    for f in rest[1:]:
        out = Mul(out, f)
    return out


def _is_trig(f: Expr) -> bool:
    return isinstance(f, FuncCall) and f.name in ("sin", "cos") \
        or isinstance(f, Pow) and _is_trig(f.base)


def _fct(e: Expr) -> list[Expr]:
    if isinstance(e, Mul):
        return _fct(e.left) + _fct(e.right)
    return [e]
