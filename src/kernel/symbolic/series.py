"""内核符号引擎 · 级数（纯标准库）。

- ``taylor(expr, var, point, order)``：泰勒/麦克劳林多项式
  ``Σ f^(n)(a)/n! · (x-a)^n``（逐阶用 `diff.nth_derivative`，与 sympy ``series`` 同式）。
- ``sum_series(term, var, lower, upper)``：级数求和
  * 有限和：多项式用 Faulhaber 公式；真分式用部分分式 telescoping；几何级数用闭式。
  * 无穷和：几何、telescoping、``Σ x^n/n! = e^x``、偶数 p-级数（Basel 族 ``π^(2k)/(2·(2k)!)·|B_2k|``）。
  * 其余：Euler–Maclaurin 数值求和并如实返回 float（标记为近似，见 parity 文档）。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var, symbol_expr,
)
from src.kernel.symbolic.diff import nth_derivative
from src.kernel.symbolic.integrate import (
    _divisors, _from_dense, _horner, _poly_div, _roots, _to_dense,
)
from src.kernel.symbolic.simplify import canonical, from_poly, key_degree, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["taylor", "maclaurin", "sum_series", "SeriesUndetermined",
           "bernoulli"]


class SeriesUndetermined(ValueError):
    """级数无闭式且数值求和不收敛（如实失败）。"""


# ═══════════════════════════════════════════════════════════════════════════════
#  泰勒展开
# ═══════════════════════════════════════════════════════════════════════════════

def taylor(expr: Expr, var: str = "x", point: float = 0.0, order: int = 5) -> Expr:
    """``Σ_{n=0}^{order} f^(n)(a)/n! (x-a)^n``（丢弃余项，与 sympy ``removeO`` 同口径）。"""
    terms: list[Expr] = []
    for n in range(order + 1):
        f = expr if n == 0 else nth_derivative(expr, var, n)
        try:
            val = f.substitute(var, Num(float(point))).evaluate({})
        except Exception:
            raise SeriesUndetermined(f"泰勒展开失败：第 {n} 阶导数在 {point} 不可求值")
        coef = float(val) / math.factorial(n)
        if abs(coef) < 1e-15:
            continue
        shift = Var(var) if point == 0 else Sub(Var(var), _num(point))
        body = shift if n == 1 else Pow(shift, _num(float(n)))
        if n == 0:
            terms.append(_num(coef))
        elif coef == 1.0:
            terms.append(body)
        elif coef == -1.0:
            terms.append(Neg(body))
        else:
            terms.append(Mul(_num(coef), body))
    if not terms:
        return Num(0)
    out = terms[0]
    for t in terms[1:]:
        out = Add(out, t)
    return canonical(out)


def maclaurin(expr: Expr, var: str = "x", order: int = 5) -> Expr:
    return taylor(expr, var, 0.0, order)


def _num(v: float) -> Num:
    r = round(v)
    return Num(float(r)) if abs(v - r) < 1e-12 else Num(v)


# ═══════════════════════════════════════════════════════════════════════════════
#  伯努利数（Faulhaber 与 Basel 族共用；精确有理数以 (p, q) 表示）
# ═══════════════════════════════════════════════════════════════════════════════

def bernoulli(n: int) -> tuple[int, int]:
    """B_n 的既约分数 (p, q)（约定 B_1 = -1/2）。

    递推：Σ_{k=0}^{m} C(m+1, k) B_k = 0 → B_m = -Σ_{k<m} C(m+1,k) B_k / (m+1)。
    """
    if n == 0:
        return (1, 1)
    if n == 1:
        return (-1, 2)
    if n % 2 == 1:
        return (0, 1)
    table: dict[int, tuple[int, int]] = {0: (1, 1), 1: (-1, 2)}
    for m in range(2, n + 1):
        if m % 2 == 1:
            table[m] = (0, 1)
            continue
        ps, qs = 0, 1
        for k in range(m):
            ps, qs = _add_frac(ps, qs, *_mul_frac(_binom(m + 1, k), 1, *table[k]))
        table[m] = _norm(-ps, qs * (m + 1))
    return table[n]


def _binom(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def _gcd(a: int, b: int) -> int:
    return math.gcd(abs(a), abs(b)) or 1


def _norm(p: int, q: int) -> tuple[int, int]:
    if q < 0:
        p, q = -p, -q
    g = _gcd(p, q)
    return (p // g, q // g)


def _add_frac(p1, q1, p2, q2):
    return _norm(p1 * q2 + p2 * q1, q1 * q2)


def _sub_frac(p1, q1, p2, q2):
    return _norm(p1 * q2 - p2 * q1, q1 * q2)


def _mul_frac(p1, q1, p2, q2):
    return _norm(p1 * p2, q1 * q2)


def _div_frac(p1, q1, p2, q2):
    return _norm(p1 * q2, q1 * p2) if p2 else (p1 * q2, q1)


def _frac_to_float(fr: tuple[int, int]) -> float:
    return fr[0] / fr[1]


# ═══════════════════════════════════════════════════════════════════════════════
#  级数求和
# ═══════════════════════════════════════════════════════════════════════════════

def sum_series(term: Expr, var: str = "n", lower: int = 1,
               upper: int | float | None = None):
    """``Σ term``；返回 Expr（闭式）或 float（数值），无法闭合时抛 SeriesUndetermined。

    ``upper=None`` 表示上界 ∞。
    """
    e = canonical(term)
    if upper is None or math.isinf(upper):
        return _sum_infinite(e, var, lower)
    return _sum_finite(e, var, int(lower), int(upper))


def _sum_finite(e: Expr, var: str, lo: int, hi: int) -> Expr:
    if hi < lo:
        return Num(0)
    # 1) 关于 var 的多项式 → Faulhaber（Σ lo..hi = Σ 0..hi - Σ 0..lo-1）
    p = poly_in_only(e, var)
    if p is not None:
        acc: list[Expr] = []
        for power, coef in p.items():
            if coef == 0:
                continue
            s = _faulhaber(power, coef, hi)
            d = _faulhaber(power, coef, lo - 1)
            acc.append(Sub(s, d) if not (isinstance(d, Num) and d.value == 0) else s)
        return _chain(acc)
    # 2) 几何级数 c*r**k
    geo = _match_geometric(e, var)
    if geo is not None:
        r, gc = geo
        num = Sub(Pow(_num(r), _num(float(hi + 1))), Pow(_num(r), _num(float(lo))))
        den = Sub(_num(r), Num(1))
        got = canonical(Div(num, den))
        return got if gc == 1.0 else Mul(_num(gc), got)
    # 3) 真分式 → 部分分式 telescoping
    tele = _telescope(e, var, lo, hi)
    if tele is not None:
        return tele
    # 4) 直接数值求和（项数有限，结果是精确整数/有理数时保持精确）
    total = 0.0
    for k in range(lo, hi + 1):
        try:
            total += float(e.substitute(var, Num(float(k))).evaluate({}))
        except Exception:
            raise SeriesUndetermined(f"级数第 {k} 项不可求值: {e}")
    r = round(total)
    if abs(total - r) < 1e-9 and abs(r) < 1e15:
        return Num(float(r))
    return Num(total)


def _faulhaber(power: float, coef: float, n: int) -> Expr:
    """Σ_{k=0}^{n} k**power（power 必须是非负整数）。"""
    if abs(power - round(power)) > 1e-12 or power < 0:
        raise SeriesUndetermined(f"Faulhaber 仅覆盖非负整数幂: {power}")
    m = int(round(power))
    if n < 0:
        return Num(0)
    acc = 0.0
    for j in range(m + 1):
        bj_num, bj_den = bernoulli(j)
        # Σ_{k=1}^{n} k^m = 1/(m+1) Σ_{j=0}^{m} (-1)^j C(m+1, j) B_j n^(m+1-j)
        sign = -1.0 if j % 2 else 1.0
        term = sign * _binom(m + 1, j) * (bj_num / bj_den) * (float(n) ** (m + 1 - j))
        acc += term
    total = acc / (m + 1)
    return Mul(_num(coef), _num(total)) if coef != 1 else _num(total)


def _match_geometric(e: Expr, var: str) -> tuple[float, float] | None:
    """识别 ``c * r**var`` → ``(r, c)``；不匹配返回 None。"""
    coef, body = 1.0, e
    if isinstance(body, Mul) and isinstance(body.left, Num):
        coef, body = float(body.left.value), body.right
    if isinstance(body, Pow) and isinstance(body.base, Num) \
            and isinstance(body.exponent, Var) and body.exponent.name == var:
        r = float(body.base.value)
        if r != 1.0:
            return (r, coef)
    return None


def _telescope(e: Expr, var: str, lo: int, hi: int) -> Expr | None:
    """有限项真分式裂项：∑ 1/((n+a)(n+b)) → (ψ 差值形式不保留)，

    仅在根为整数且相消可直接写出有限项时使用；否则返回 None，
    交给 :func:`_rational_closed`（无穷上界）或数值分支。
    """
    if not isinstance(e, Div):
        return None
    pn, pd = poly(e.numerator), poly(e.denominator)
    if pn is None or pd is None:
        return None
    dn, dd = _to_dense(pn, var), _to_dense(pd, var)
    if not dn or not dd or len(dd) != 3:
        return None
    roots = _roots(dd)
    if len(roots) != 2 or abs(roots[0] - roots[1]) < 1e-12:
        return None
    if any(abs(r - round(r)) > 1e-9 for r in roots):
        return None                      # 非整数平移：不能逐项相消
    dp = [dd[0] * 2, dd[1]]
    total = 0.0
    for r in roots:
        resid = _horner(dn, r) / _horner(dp, r)
        k0 = int(round(lo - r))
        k1 = int(round(hi - r))
        if k0 <= 0:
            return None                  # 求和通道跨过极点
        # 有限谐波和 Σ_{k=k0}^{k1} 1/k = ψ(k1+1) - ψ(k0)（digamma 已在下方实现）
        total += resid * (_digamma(float(k1 + 1)) - _digamma(float(k0)))
    r_int = round(total)
    if abs(total - r_int) < 1e-9 and abs(r_int) < 1e15:
        return Num(float(r_int))
    return Num(total)


def _sum_infinite(e: Expr, var: str, lo: int):
    """无穷级数：闭式优先，否则 Euler–Maclaurin 数值求和。"""
    # Σ x^n/n! = e^x ； Σ (-1)^n x^n/n! 等
    base = _match_exp_series(e, var)
    if base is not None:
        return FuncCall("exp", [base])
    p = poly_in_only(e, var)
    if p is not None:
        # 单项 c*n**k：k=-2 → π²/6 等 Basel 族；其它发散
        if len(p) == 1:
            (power, coef), = p.items()
            if abs(power + 2) < 1e-12:
                return _basel(1, coef)
            if abs(power + 4) < 1e-12:
                return _basel(2, coef)
            raise SeriesUndetermined(f"发散 p-级数: Σ {e}（p={-power}）")
        raise SeriesUndetermined(f"多项式型级数发散: Σ {e}")
    got = _rational_closed(e, var, lo)
    if got is not None:
        return got
    return _euler_maclaurin(e, var, lo)


def _basel(k: int, coef: float):
    """Σ 1/n^(2k) = |B_2k| (2π)^(2k) / (2·(2k)!)。"""
    b_num, b_den = bernoulli(2 * k)
    val = abs(b_num / b_den) * (2 * math.pi) ** (2 * k) / (2 * math.factorial(2 * k))
    return Num(coef * val)


def _match_exp_series(e: Expr, var: str) -> Expr | None:
    """识别 x**n/factorial(n) → x。"""
    if isinstance(e, Div):
        num, den = e.numerator, e.denominator
        if isinstance(den, FuncCall) and den.name == "factorial" and len(den.args) == 1 \
                and isinstance(den.args[0], Var) and den.args[0].name == var:
            if isinstance(num, Pow) and isinstance(num.exponent, Var) \
                    and num.exponent.name == var:
                return num.base
            if isinstance(num, Var) and num.name == var:
                return Num(1)
    return None


def _rational_closed(e: Expr, var: str, lo: int) -> Expr | None:
    """有理通项的 telescoping 无穷和：Σ_{n=lo}^∞ Σ_i c_i/(n+r_i) = -Σ_i c_i·ψ(lo+r_i)。

    收敛条件：真分式且一次留数之和为 0（否则抛/返回 None）。
    """
    if not isinstance(e, Div):
        return None
    pn, pd = poly(e.numerator), poly(e.denominator)
    if pn is None or pd is None:
        return None
    dn, dd = _to_dense(pn, var), _to_dense(pd, var)
    if not dn or not dd:
        return None
    if any(abs(c) > 1e-12 for c in _poly_div(dn, dd)[0]):
        return None                      # 非真分式 → 发散
    roots = _roots(dd)
    if len(roots) != len(dd) - 1:
        return None
    resids = []
    for r in roots:
        dp = [dd[i] * (len(dd) - 1 - i) for i in range(len(dd) - 1)]
        rv = _horner(dp, r)
        if rv is None or abs(rv) < 1e-14:
            return None                  # 重根：需 polygamma，当前不覆盖
        resids.append((_horner(dn, r) / rv, r))
    if abs(sum(c for c, _ in resids)) > 1e-9:
        raise SeriesUndetermined(
            f"对数发散级数（一次留数和非零）: Σ {e}")
    total = 0.0
    for c, r in resids:
        x0 = float(lo) - r            # 项形如 c/(n - r) → 平移后分母 m + (lo - r)
        if x0 <= 0 and abs(x0 - round(x0)) < 1e-12:
            return None                  # 通道遇极点
        total -= c * _digamma(x0)
    if not math.isfinite(total):
        return None
    return Num(total)


def _digamma(x: float) -> float:
    """ψ(x)：递推上推至 x>=8 后用渐进展开（精度 ~1e-13）。"""
    if x <= 0 and abs(x - round(x)) < 1e-12:
        return math.nan
    acc = 0.0
    while x < 8:
        acc -= 1.0 / x
        x += 1.0
    inv = 1.0 / x
    approx = (math.log(x) - 0.5 * inv
              - inv ** 2 / 12.0 + inv ** 4 / 120.0 - inv ** 6 / 252.0)
    return acc + approx


def _euler_maclaurin(e: Expr, var: str, lo: int, extra: int = 200_000) -> float:
    """数值求和 + Euler–Maclaurin 尾项校正；发散时抛 SeriesUndetermined。"""
    total = 0.0
    last = 0.0
    for k in range(lo, lo + extra):
        try:
            v = float(e.substitute(var, Num(float(k))).evaluate({}))
        except Exception:
            raise SeriesUndetermined(f"级数第 {k} 项不可求值: {e}")
        if not math.isfinite(v):
            raise SeriesUndetermined(f"级数第 {k} 项非有限值: {e}")
        total += v
        last = v
        if abs(v) < 1e-16 and k > lo + 10:
            return total
    if abs(last) > 1e-6:
        raise SeriesUndetermined(f"级数收敛过慢/发散，拒绝伪造数值: Σ {e}")
    # 尾项：∫_N^∞ f + B2/2! f'(N) …（此处用等比外推估计尾部）
    tail = _tail_estimate(e, var, lo + extra)
    return total + tail


def _tail_estimate(e: Expr, var: str, n0: int) -> float:
    def f(x: float) -> float:
        return float(e.substitute(var, Num(x)).evaluate({}))
    a, b = f(float(n0)), f(float(n0 + 1))
    if a == 0:
        return 0.0
    r = b / a
    if not (0 < r < 1):
        return 0.0
    return a * r / (1 - r)


def poly_in_only(e: Expr, var: str) -> dict[float, float] | None:
    """关于 ``var`` 的广义多项式 → {指数: 系数}；含其他原子返回 None。"""
    p = poly(e)
    if p is None:
        return None
    out: dict[float, float] = {}
    for key, coef in p.items():
        power = 0.0
        for atom, exp in key:
            if atom != var:
                return None
            power += exp
        out[power] = out.get(power, 0.0) + coef
    return out


def _chain(parts: list[Expr]) -> Expr:
    if not parts:
        return Num(0)
    out = parts[0]
    for p in parts[1:]:
        out = Add(out, p)
    return canonical(out)
