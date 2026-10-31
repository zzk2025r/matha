"""内核符号引擎 · 极限（纯标准库）。

``limit(expr, var, point, direction)`` 的求解顺序（每步失败才进下一步）：

1. **直接代入**：内核对连续闭包（+−×÷、幂、已知初等函数）直接求值。
2. **∞ 主部比较**：``x→±∞`` 时用广义多项式主部 (系数, 次数) 判定 0 / 常数 / ±∞。
3. **0/0 型洛必达**：分子分母同求导，最多 ``MAX_LOPITAL`` 轮。
4. **0·∞ / ∞−∞ 归约**：把乘积改写为商、差改写为通分后再回到 2/3。
5. **两侧单值**：``direction`` 为 ``'+'``/``'-'`` 时按瑕点邻域符号判定 ±∞。

不能判定时抛 ``LimitUndetermined``（由门面如实报告），**不返回猜测值**。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)
from src.kernel.symbolic.diff import differentiate, leading_term, poly_in
from src.kernel.symbolic.simplify import canonical, key_degree, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["limit", "LimitUndetermined", "MAX_LOPITAL"]

MAX_LOPITAL = 12


class LimitUndetermined(ValueError):
    """内核无法在该表达式类上给出极限（如实失败，不伪造）。"""


def limit(expr: Expr, var: str = "x", point: float = 0,
          direction: str = "+") -> float:
    """``lim(var→point) expr``，返回 float（无穷为 ``±math.inf``）。

    Examples:
        >>> limit(symbol_expr("sin(x)/x"), "x", 0)
        1.0
        >>> limit(symbol_expr("1/x"), "x", 0, "+")
        inf
    """
    e = canonical(expr)
    d = 1.0 if direction not in ("-", "-+" ) else -1.0
    if math.isinf(point):
        return _limit_infinity(e, var, point, d)
    # 1) 直接代入
    v = _try_eval(e, var, point)
    if v is not None and math.isfinite(v):
        if abs(v) > 1e8 and _is_pole(e, var, point, d):
            # 瑕点的浮点邻域读数（如 tan(pi/2) 的 cos 残差 6e-17）不是极限值
            sgn = _side_sign_expr(e, var, point, d)
            return math.copysign(math.inf, sgn if sgn else 1.0)
        return v
    # 1b) 1^oo 型：L = exp(lim exponent * log(base))
    r = _one_infinity(e, var, point, d)
    if r is not None:
        return r
    # 1c) 初等函数自身的有限瑕点（log 在 0、sqrt 在 0、反三角在定义域端点）
    fs = _func_singularity(e, var, point, d)
    if fs is not None:
        return fs
    # 2) 瑕点：分子/分母分离
    num, den = _split_fraction(e)
    if den is not None:
        return _limit_quotient(num, den, var, point, d, e)
    # 2b) 0·∞ 型：把趋于 0 的因子下传到分母，得到可洛必达的商
    zi = _zero_inf_product(e, var, point)
    if zi is not None:
        return _limit_quotient(zi[0], zi[1], var, point, d, e)
    if v is not None:               # ±inf 直读
        return _conjugate_or(e, var, point, d, v)
    raise LimitUndetermined(f"极限未定: lim({var}→{point}) {e}")


def _one_infinity(e: Expr, var: str, point: float, side: float) -> float | None:
    """``1^oo`` 不定型的标准处理：``lim f^g = exp(lim g*ln f)``。"""
    if not isinstance(e, Pow):
        return None
    bv = _try_eval(e.base, var, point)
    ev = _try_eval(e.exponent, var, point)
    if bv is None or ev is None:
        return None
    if abs(bv - 1.0) > 1e-9 or not math.isinf(ev) or e.base == e.exponent:
        return None
    inner = Mul(e.exponent, FuncCall("log", [e.base]))
    try:
        lg = limit(inner, var, point, "+" if side >= 0 else "-")
    except LimitUndetermined:
        return None
    if not math.isfinite(lg):
        return math.inf if lg > 0 else 0.0
    return math.exp(lg)


def _is_pole(e: Expr, var: str, point: float, side: float) -> bool:
    """真极点判定：邻域读数随 eps 缩小而持续放大。

    eps 每缩小 1000 倍，极点函数读数应至少增长 1000 倍（严格极点为 10^6）；
    阈值取 10^3 而不是 10^6，是因为 tan(pi/2) 这类**已经处于浮点残留量级**的
    瑕点（cos(pi/2) = 6e-17）在 eps 很小时读数会提前饱和，严格阀门会漏判。
    """
    vals: list[float] = []
    for k in (4, 7, 10):
        vv = _try_eval(e, var, point + 10.0 ** (-k) * (side or 1.0))
        if vv is None:
            return False
        vals.append(abs(vv) if math.isfinite(vv) else math.inf)
    return vals[0] < vals[1] < vals[2] and vals[2] > 1e3 * max(vals[0], 1e-30)


def _side_sign_expr(e: Expr, var: str, point: float, side: float) -> float:
    for k in (6, 9, 12):
        vv = _try_eval(e, var, point + 10.0 ** (-k) * (side or 1.0))
        if vv is not None and vv != 0:
            return 1.0 if vv > 0 else -1.0
    return 0.0


def _conjugate_or(e: Expr, var: str, point: float, side: float,
                  direct: float) -> float:
    """直读得 ±inf 前，先排 ∞−∞ 型（共轭有理化），否则采用直读值。"""
    got = _conjugate_rewrite(e, var, point, side)
    return direct if got is None else got


_PI = math.pi

# 有限瑕点处「函数自身」的确定取值：内层极限 → 外层结果
_SINGULAR_VALUE: dict[str, dict[str, float | tuple[float, float]]] = {
    # 内层趋于 0+ 时 log 趋于 -oo；趋于 +oo 时趋于 +oo
    "log": {"zero": -math.inf, "pinf": math.inf},
    "ln": {"zero": -math.inf, "pinf": math.inf},
    "sqrt": {"zero": 0.0},
    "asin": {(1.0, "finite"): _PI / 2, (-1.0, "finite"): -_PI / 2},
    "acos": {(1.0, "finite"): 0.0, (-1.0, "finite"): _PI},
}


def _func_singularity(e: Expr, var: str, point: float, side: float) -> float | None:
    """``log(0+)``、``sqrt(0+)``、``asin(±1)`` 等函数端点的确定极限。

    内层极限必须**已存在**（否则 None 交回上层），避免在此猜值。
    """
    if not isinstance(e, FuncCall) or len(e.args) != 1:
        return None
    table = _SINGULAR_VALUE.get(e.name)
    if table is None:
        return None
    try:
        iv = limit(e.args[0], var, point, "+" if side >= 0 else "-")
    except LimitUndetermined:
        return None
    except Exception:
        return None
    if iv == 0:                          # 内层趋于 0（含 -0.0）
        return table.get("zero")
    if iv == math.inf:
        return table.get("pinf")
    if isinstance(iv, float) and math.isfinite(iv):
        got = table.get((iv, "finite"))
        return got if isinstance(got, float) else None
    return None


def _zero_inf_product(e: Expr, var: str, point: float) -> tuple[Expr, Expr] | None:
    """0·∞ 型乘积：``f*g``（f→0、g→∞）改写为 ``g / (1/f)`` 以便洛必达。"""
    if not isinstance(e, Mul):
        return None
    factors = _flat_mul(e)
    zeros: list[Expr] = []
    infns: list[Expr] = []
    others: list[Expr] = []
    for f in factors:
        v = _try_eval(f, var, point)
        if v is None:
            return None
        if v == 0:
            zeros.append(f)
        elif math.isinf(v):
            infns.append(f)
        else:
            others.append(f)
    if not zeros or not infns:
        return None
    num = _chain_mul(others + infns)
    den = _chain_mul([Pow(z, Num(-1.0)) for z in zeros])
    if num is None or den is None:
        return None
    return num, den


def _flat_mul(e: Expr) -> list[Expr]:
    out: list[Expr] = []
    for side in (e.left, e.right):
        out.extend(_flat_mul(side) if isinstance(side, Mul) else [side])
    return out


def _chain_mul(parts: list[Expr]) -> Expr | None:
    if not parts:
        return Num(1)
    out: Expr = parts[0]
    for q in parts[1:]:
        out = Mul(out, q)
    return out


def _sqrt_of(e: Expr) -> Expr | None:
    """识别 ``sqrt(u)`` / ``u**(1/2)`` → 返回 u。"""
    if isinstance(e, FuncCall) and e.name == "sqrt" and len(e.args) == 1:
        return e.args[0]
    if isinstance(e, Pow) and isinstance(e.exponent, Num) and e.exponent.value == 0.5:
        return e.base
    return None


def _conjugate_rewrite(e: Expr, var: str, point: float, side: float) -> float | None:
    """√a − √b 型 ∞−∞：改写为 ``(a-b)/(√a+√b)`` 后重新求极限。

    只覆盖两项均为平方根的情形（教科书主因）；其余 ∞−∞ 仍交给上层如实失败。
    """
    a = b = None
    sign = 1.0
    if isinstance(e, Sub):
        a, b = e.left, e.right
    elif isinstance(e, Add) and isinstance(e.right, Neg):
        a, b = e.left, e.right.expr
    elif isinstance(e, Add) and isinstance(e.left, Neg):
        a, b = e.right, e.left.expr
    elif isinstance(e, Neg) and isinstance(e.expr, Sub):
        a, b, sign = e.expr.right, e.expr.left, -1.0
    if a is None or b is None:
        return None
    ua, ub = _sqrt_of(a), _sqrt_of(b)
    if ua is None or ub is None:
        return None
    num = canonical(Sub(ua, ub))
    den = Add(a, b)
    try:
        got = limit(Div(num, den), var, point, "+" if side >= 0 else "-")
    except LimitUndetermined:
        return None
    return sign * got


# ═══════════════════════════════════════════════════════════════════════════════

def _try_eval(e: Expr, var: str, value: float, side: float = 0.0) -> float | None:
    """在 ``value``（或邻域 ``value + side*eps``）求值，异常/未绑定 → None。"""
    target = value if side == 0.0 else value + side * 1e-9
    try:
        out = e.substitute(var, Num(float(target))).evaluate({})
    except ZeroDivisionError:
        return math.inf if _sign_near(e, var, value, side) >= 0 else -math.inf
    except Exception:
        return None
    if isinstance(out, complex):
        return None
    try:
        return float(out)
    except (TypeError, ValueError):
        return None


def _sign_near(e: Expr, var: str, value: float, side: float) -> float:
    v = _try_eval(e, var, value, side if side else 1e-9)
    return 1.0 if (v is None or v >= 0) else -1.0


def _split_fraction(e: Expr) -> tuple[Expr, Expr | None]:
    """把表达式规约为 (分子, 分母)；不是商形式时返回 (e, None)。"""
    if isinstance(e, Div):
        return e.numerator, e.denominator
    if isinstance(e, Mul):
        n1, d1 = _split_fraction(e.left)
        n2, d2 = _split_fraction(e.right)
        if d1 is None and d2 is None:
            return e, None
        num = Mul(n1, n2)
        dens = [d for d in (d1, d2) if d is not None]
        den = dens[0] if len(dens) == 1 else Mul(dens[0], dens[1])
        return num, den
    if isinstance(e, Pow) and isinstance(e.exponent, Num) and e.exponent.value < 0:
        return Num(1), Pow(e.base, Num(-e.exponent.value))
    if isinstance(e, Neg):
        n, d = _split_fraction(e.expr)
        return Neg(n), d
    return e, None


def _limit_quotient(num: Expr, den: Expr, var: str, point: float,
                    side: float, original: Expr) -> float:
    nv = _try_eval(num, var, point)
    dv = _try_eval(den, var, point)
    if nv is not None and dv is not None:
        if math.isinf(nv) and math.isinf(dv):
            # ∞/∞ 型：数值商无意义（inf/inf = nan），直接洛必达
            return _lopital(num, den, var, point, side, original)
        if dv != 0:
            return nv / dv
        if nv != 0:
            # 非 0/0 型瑕点：符号由邻域决定
            s_num = 1.0 if nv > 0 else -1.0
            s_den = _side_sign(den, var, point, side)
            if s_den == 0:
                raise LimitUndetermined(f"极限振荡: {original}")
            return math.copysign(math.inf, s_num * s_den)
        # 0/0 → 洛必达
        return _lopital(num, den, var, point, side, original)
    # ∞/∞ 或不定形 → 主部比较 / 洛必达
    lt_n = leading_term(num, var, at_infinity=math.isinf(point))
    lt_d = leading_term(den, var, at_infinity=math.isinf(point))
    if lt_n is not None and lt_d is not None:
        cn, en = lt_n
        cd, ed = lt_d
        if en == ed:
            return cn / cd
        if en > ed and not math.isinf(point):
            return _lopital(num, den, var, point, side, original)
    raise LimitUndetermined(f"极限未定: lim({var}→{point}) {original}")


def _side_sign(den: Expr, var: str, point: float, side: float) -> float:
    eps = 1e-9 * (side if side else 1.0)
    v = _try_eval(den, var, point + eps)
    if v is None or v == 0:
        v = _try_eval(den, var, point - eps)
        return 0.0 if v is None or v == 0 else (-1.0 if v < 0 else 1.0)
    return -1.0 if v < 0 else 1.0


def _lopital(num: Expr, den: Expr, var: str, point: float,
             side: float, original: Expr, depth: int = 0) -> float:
    n, d = num, den
    for i in range(MAX_LOPITAL if depth == 0 else depth):
        n = differentiate(n, var)
        d = differentiate(d, var)
        nv = _try_eval(n, var, point)
        dv = _try_eval(d, var, point)
        if nv is None or dv is None:
            break
        if dv != 0:
            out = nv / dv
            if math.isnan(out):
                break                    # inf/inf 等未定商：不当结论，转外推兜底
            return out
        if nv == 0:
            continue
        # 0/0 → 非零：极限为无穷
        s = _side_sign(d, var, point, side)
        if s == 0:
            break
        return math.copysign(math.inf, (1 if nv > 0 else -1) * s)
    # 级数兜底：邻域数值外推
    v = _numeric_extrapolate(original, var, point, side)
    if v is not None:
        return v
    raise LimitUndetermined(f"洛必达/级数均失败: lim({var}→{point}) {original}")


def _numeric_extrapolate(e: Expr, var: str, point: float, side: float) -> float | None:
    """Richardson 外推：在 point ± 10^-k 处求值并收敛加速。

    这是**判定性**的数值方法（不是「猜一个数」）：只有当两阶差分收敛到
    ``TOL_EXTRAP`` 内才采纳，否则返回 None 交给上层如实失败。
    """
    seq: list[float] = []
    for k in range(3, 12):
        eps = 10.0 ** (-k) * (side if side else 1.0)
        v = _try_eval(e, var, point + eps)
        if v is None or not math.isfinite(v):
            continue
        seq.append(v)
        if len(seq) >= 4:
            a, b, c, d = seq[-4:]
            if max(abs(b - a), abs(c - b), abs(d - c)) < TOL_EXTRAP:
                return d
    if len(seq) >= 2 and abs(seq[-1] - seq[-2]) < TOL_EXTRAP:
        return seq[-1]
    return None


TOL_EXTRAP = 1e-9


def _limit_infinity(e: Expr, var: str, point: float, side: float) -> float:
    at_pos = point > 0
    # 1^oo 型（如 (1+1/x)**x → e）
    r = _one_infinity(e, var, point, side)
    if r is not None:
        return r
    # √a − √b 型 ∞−∞
    got = _conjugate_rewrite(e, var, point, side)
    if got is not None:
        return got
    # 有理函数 P/Q 在 ±∞ 的极限**先**由首项比精确判定（对标 sympy.limit 主导项法），
    # 早于下面的 t=1/x 数值归约——后者在大数邻域读数会带来末位浮点误差（如
    # (2x+1)/(3x-1)→0.66666666667 而非精确 2/3）。仅当 P/Q 不能定阶（含 exp/log/
    # 三角/根式）时才退回数值归约。
    num, den = _split_fraction(e)
    if den is not None:
        ln = leading_term(num, var, at_infinity=True)
        ld = leading_term(den, var, at_infinity=True)
        if ln is not None and ld is not None:
            cn, en = ln
            cd, ed = ld
            if en < ed:
                return 0.0
            if en == ed:
                return cn / cd
            # deg(num)>deg(den) → ±∞：号由 (cn/cd) 与次差 (en-ed) 在 -∞ 的奇偶
            # 共同决定（奇次翻号、偶次保号），与下方 poly_in 分支同口径。
            sgn = cn / cd
            dd = en - ed
            if point < 0 and abs(dd - round(dd)) <= 1e-12 and int(round(dd)) % 2 == 1:
                sgn = -sgn
            cand = math.copysign(math.inf, sgn)
            if _probe_agrees(e, var, point, cand):
                return cand
    # t = 1/x 归约：把非有理式的无穷远极限换成 t→0± 上的 0/0 型（洛必达/共轭
    # 有理化可用），避免 (1+1e-12) 这类浮点抵消误差；结论需邻域大数读数佐证。
    g0 = _reciprocal_sub(e, var, point)
    if g0 is not None and _probe_agrees(e, var, point, g0):
        return g0
    p = poly_in(e, var)
    if p is not None:
        terms = [(d, c) for d, c in p.items() if c != 0]
        if not terms:
            return 0.0
        d, c = max(terms)
        if d == 0:
            return c
        if d < 0:
            return 0.0
        # 正次幂 → ±∞：但「原子当正次幂」会把趋 0 因子（如 log(1+1/x)）误判为增长，
        # 故必须有邻域增长佐证才采纳。
        cand: float | None = None
        if at_pos:
            cand = math.copysign(math.inf, c)
        elif abs(d - round(d)) > 1e-12:
            cand = None     # 非整数次幂在 -∞ 无定义（如实落入后续判据）
        else:
            # x→-∞：偶次保留正号，奇次取反（与系数 c 合成）
            cand = math.copysign(math.inf, c if int(round(d)) % 2 == 0 else -c)
        if cand is not None and _probe_agrees(e, var, point, cand):
            return cand
    # 初等函数在 ∞ 的已知行为（避开数值溢出误判）
    guess = _infinity_behavior(e, var, point)
    if guess is not None:
        return guess
    # log 增长严格慢于任一正次幂：log(x)/x**k → 0
    slow = _log_beats_power(num, den, var)
    if slow is not None:
        return slow
    fast = _exp_beats_power(num, den, var, point)
    if fast is not None:
        return fast
    # 其余情形用邻域大数外推（仅当两个量级结果一致才采纳）
    v = _try_eval(e, var, math.copysign(1e12, point))
    if v is not None and math.isfinite(v):
        v2 = _try_eval(e, var, math.copysign(1e13, point))
        if v2 is not None and abs(v2 - v) < TOL_EXTRAP * max(1.0, abs(v)):
            # 量级已降到外推容差以下：真实极限为 0（不报 1e-12 这类假精度）
            return 0.0 if abs(v2) < TOL_EXTRAP else v2
    raise LimitUndetermined(f"无穷远处极限未定: lim({var}→{point}) {e}")


def _probe_agrees(e: Expr, var: str, point: float, got: float) -> bool:
    """邻域大数读数与候选结论是否同势（读数缺失时不阻断，但绝不允许反证）。"""
    v1 = _try_eval(e, var, math.copysign(1e12, point))
    v2 = _try_eval(e, var, math.copysign(1e13, point))
    if v1 is None or v2 is None or not (math.isfinite(v1) and math.isfinite(v2)):
        return True
    if math.isinf(got):
        return abs(v2) > 3.0 * max(abs(v1), 1e-12) and abs(v2) > 1e6
    if abs(v1 - v2) < TOL_EXTRAP * max(1.0, abs(v2)):
        return abs(got - v2) <= 1e-6 * max(1.0, abs(got))
    return abs(v2 - got) <= 1e-3 * max(1.0, abs(got))


def _reciprocal_sub(e: Expr, var: str, point: float) -> float | None:
    """``x→±∞`` 改写为 ``t→0±``（x = 1/t）后重新求极限；失败时 None。

    仅对「不能广义多项式定阶」的表达式启用，避免把振荡型（如 sin(x)）
    误当可极限处理；内层 LimitUndetermined 被拦下，由上层如实报错。
    """
    t = "__t"
    try:
        sub = e.substitute(var, Div(Num(1), Var(t)))
    except Exception:
        return None
    if sub is None:
        return None
    try:
        return limit(sub, t, 0.0, "+" if point > 0 else "-")
    except LimitUndetermined:
        return None
    except Exception:
        return None


def _log_beats_power(num: Expr, den: Expr | None, var: str) -> float | None:
    """``log(p(x)) / q(x)``（q 为正次广义多项式）→ 0：log 增长慢于任意正幕。"""
    if den is None:
        return None
    ld = leading_term(den, var, at_infinity=True)
    if ld is None or ld[1] <= 1e-12:
        return None
    ln_ = leading_term(num, var, at_infinity=True)
    if ln_ is None or abs(ln_[1]) > 1e-12:
        return None
    if not _has_log(num):
        return None
    return 0.0


def _exp_beats_power(num: Expr, den: Expr | None, var: str,
                     point: float) -> float | None:
    """``exp(a*x)``（a>0）除任意多项式→ ∞：指数增长快于任何次幂。

    只在 x→+∞ 方向启用（x→-∞ 时 exp 趋于 0，由其他判据处理）。"""
    if den is None or point < 0:
        return None
    ld = leading_term(den, var, at_infinity=True)
    if ld is None:
        return None
    for k in _walk(num):
        if isinstance(k, FuncCall) and k.name == "exp" and len(k.args) == 1:
            sl = _slope(k.args[0], var)
            if sl is not None and sl > 0:
                return math.inf
    return None


def _has_log(e: Expr) -> bool:
    return any(isinstance(k, (FuncCall,)) and k.name in ("log", "ln")
               for k in _walk(e))


def _walk(e: Expr):
    yield e
    for c in e._children():
        yield from _walk(c)


def _slope(e: Expr, var: str) -> float | None:
    """一次式主部的斜率（不是严格一次式时返回 None）。"""
    lt = leading_term(e, var, at_infinity=True)
    if lt is None:
        return None
    coef, power = lt
    return coef if abs(power - 1.0) < 1e-12 else None


def _infinity_behavior(e: Expr, var: str, point: float) -> float | None:
    """exp / log / 幂函数在 ±∞ 的确定行为（不能判定时 None）。"""
    s = 1.0 if point > 0 else -1.0
    if isinstance(e, FuncCall) and len(e.args) == 1:
        if e.name == "exp":
            lin = _slope(e.args[0], var)
            if lin is not None:
                return math.inf if lin * s > 0 else 0.0
        if e.name in ("log", "ln"):
            lin = _slope(e.args[0], var)
            if lin is not None and lin * s > 0:
                return math.inf
        if e.name == "atan" and isinstance(e.args[0], Var):
            # atan(±oo) = ±pi/2（精确值，不让数值外推给出 12 位近似）
            return _PI / 2 if s > 0 else -_PI / 2
        if e.name in ("log", "ln") and isinstance(e.args[0], Var) and s > 0:
            return math.inf
        return None
    if isinstance(e, Pow) and isinstance(e.exponent, Num):
        ex = e.exponent.value
        if _slope(e.base, var) is not None:
            # 底趋于 ∞（正负由上层 poly_in 分支判定），指数定阶
            return math.inf if ex > 0 else 0.0
    return None
