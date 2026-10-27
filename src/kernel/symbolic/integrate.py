"""内核符号引擎 · 积分（纯标准库）。

``integrate(expr, var)`` 返回原函数（Expr），**无法在闭合形式内积分时返回 None**，
由调用方如实报错或转数值积分——绝不返回「假装成功」的结果。

覆盖规则（与 sympy ``integrate`` 的能力对照见 docs/symbolic_parity.md）：

1. 线性性与幂法则（含广义多项式：任意整数/分数指数）。
2. 一次内函数的换元：``sin/cos/tan/sec/csc/exp/log/ln`` 作用于 ``a*x+b``。
3. 单项式乘积中的 ``x**n * exp(a*x+b)`` / ``x**n * sin/cos(a*x+b)``（表格分部积分）。
4. ``exp``×``trig`` 乘积（欧拉公式风格的联立方程）。
5. 有理函数：分母可分解为一次因式（有理根定理）→ 部分分式；
   不可约二次因式 → ``log`` + ``atan`` 组合。
6. 上述都不匹配 → None。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var, symbol_expr,
)
from src.kernel.symbolic.diff import differentiate, poly_in
from src.kernel.symbolic.simplify import canonical, from_poly, key_degree, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["integrate", "definite", "numerical_definite"]

_TRIG_OF_LINEAR = {"sin", "cos", "tan", "sec", "csc", "cot", "exp"}


def _f(name: str, *args) -> FuncCall:
    """构造函数节点（容忍历史上误传 `[arg]` 列表的写法）。"""
    flat: list[Expr] = []
    for a in args:
        if isinstance(a, (list, tuple)):
            flat.extend(a)
        else:
            flat.append(a)
    return FuncCall(name, flat)


def integrate(expr: Expr, var: str = "x") -> Expr | None:
    """不定积分（不含积分常数 C，与 sympy ``integrate`` 口径一致）。"""
    e = canonical(expr)
    out = _int(e, var)
    return None if out is None else canonical(out)


def definite(expr: Expr, var: str, lower: float, upper: float,
             *, allow_numeric: bool = True) -> float | None:
    """定积分：先试 Newton-Leibniz，失败再退自适应 Simpson（纯标准库数值积分）。"""
    e = canonical(expr)
    anti = _int(e, var)
    if anti is not None:
        anti = canonical(anti)
        try:
            fv = _eval_at(anti, var, upper) - _eval_at(anti, var, lower)
            if math.isfinite(fv) or (math.isinf(fv) and math.isinf(_eval_at(anti, var, upper))):
                # 瑕点（无穷原函数相减得 nan）时改走数值分支
                if not math.isnan(fv):
                    return fv
        except Exception:
            pass
    if not allow_numeric:
        return None
    return numerical_definite(e, var, lower, upper)


def _eval_at(e: Expr, var: str, value: float) -> float:
    return e.substitute(var, Num(float(value))).evaluate({})


# ═══════════════════════════════════════════════════════════════════════════════
#  数值积分（自适应 Simpson）
# ═══════════════════════════════════════════════════════════════════════════════

def numerical_definite(expr: Expr, var: str, lower: float, upper: float,
                       *, tol: float = 1e-10, max_depth: int = 60) -> float | None:
    f = _callable(expr, var)
    if f is None:
        return None
    try:
        a, b = float(lower), float(upper)
        fa, fb, fm = f(a), f(b), f((a + b) / 2.0)
        whole = (b - a) / 6.0 * (fa + 4 * fm + fb)
    except Exception:
        return None

    def recurse(a: float, b: float, fa: float, fb: float, fm: float,
                base: float, depth: int) -> float | None:
        m = (a + b) / 2.0
        lm = (a + m) / 2.0
        rm = (m + b) / 2.0
        try:
            flm, frm = f(lm), f(rm)
        except Exception:
            return None
        left = (m - a) / 6.0 * (fa + 4 * flm + fm)
        right = (b - m) / 6.0 * (fm + 4 * frm + fb)
        delta = left + right - base
        if depth >= max_depth or abs(delta) <= 15 * tol:
            return left + right + delta / 15.0
        l = recurse(a, m, fa, fm, flm, left, depth + 1)
        r = recurse(m, b, fm, fb, frm, right, depth + 1)
        return None if l is None or r is None else l + r

    return recurse(a, b, fa, fb, fm, whole, 0)


def _callable(expr: Expr, var: str):
    def f(x: float) -> float:
        return expr.substitute(var, Num(float(x))).evaluate({})
    try:
        f(0.5)
    except Exception:
        return None
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  主分派
# ═══════════════════════════════════════════════════════════════════════════════

def _int(e: Expr, var: str) -> Expr | None:
    if isinstance(e, Num):
        return Mul(Num(e.value), Var(var)) if e.value != 0 else Num(0)
    if isinstance(e, Var):
        return Div(Pow(Var(var), Num(2)), Num(2)) if e.name == var else None
    if isinstance(e, Neg):
        inner = _int(e.expr, var)
        return None if inner is None else Neg(inner)
    if isinstance(e, Add):
        a, b = _int(e.left, var), _int(e.right, var)
        return None if a is None or b is None else Add(a, b)
    if isinstance(e, Sub):
        a, b = _int(e.left, var), _int(e.right, var)
        return None if a is None or b is None else Sub(a, b)
    p = poly(e)
    if p is not None:
        got = _int_poly(p, var)
        if got is not None:
            return got
        # 多项式化成功但积分未覆盖（如 exp(x)*cos(x)）：继续试结构性规则
    if isinstance(e, Mul):
        return _int_mul(e, var)
    if isinstance(e, Div):
        return _int_div(e, var)
    if isinstance(e, (FuncCall, Log, Pow)):
        return _int_single(e, var)
    return None


def _int_poly(p: dict, var: str) -> Expr | None:
    out: dict = {}
    for key, coef in p.items():
        term = _int_monomial(key, coef, var)
        if term is None:
            return None
        # term 可能不是单项式（例如 x**n*e**x 的分部结果），此时直接累加表达式
        if isinstance(term, dict):
            for k2, c2 in term.items():
                out[k2] = out.get(k2, 0.0) + c2
        else:
            merged = out.get(("__expr__",), {(): 0.0})
            _ = merged
            return _mix(out, term)
    return from_poly(out)


def _mix(done: dict, tail: Expr) -> Expr | None:
    """已积出的纯多项式部分 + 非多项式尾部。"""
    base = from_poly(done) if done else None
    rest = tail
    if base is None or (isinstance(base, Num) and base.value == 0):
        return rest
    return Add(base, rest)


def _int_monomial(key: tuple, coef: float, var: str) -> Expr | dict | None:
    if not key:
        return Mul(_num(coef), Var(var))
    # exp 原子乘积先合指数：∫exp(2x)·exp(-x) dx 只有并成 exp(x) 才能用单原子规则
    merged = _collapse_exps(key, var)
    if merged is not None:
        return _int_monomial(merged, coef, var)
    # sin^m * cos^n（含单原子偶次幂）优先走三角专用规则
    if all(_trig_atom(a) for a, _e in key):
        got = _int_trig_powers(key, coef, var)
        if got is not None:
            return got
    if len(key) == 1:
        atom, exp = key[0]
        if atom == var:
            return _power_integral(var, exp, coef)
        got = _int_single_atom(atom, exp, coef, var)
        if got is not None:
            return got
    # x**n * f(a x + b)：表格分部积分
    got = _int_parts_form(key, coef, var)
    if got is not None:
        return got
    # 一般 sin/cos 幂乘积
    return _int_trig_powers(key, coef, var)


def _trig_atom(atom: str) -> bool:
    return atom.startswith(("sin(", "cos(")) and atom.endswith(")")


def _collapse_exps(key: tuple, var: str) -> tuple | None:
    """``exp(a1*x+b1)**k1 · exp(a2*x+b2)**k2`` → 单一 ``exp(A*x+B)`` 原子。

    仅当**全部**因子都是 exp(一次式) 且个数 ≥ 2 时合指数；否则 None（不动原形）。
    """
    if len(key) < 2:
        return None
    A = B = 0.0
    for atom, exp in key:
        try:
            inner = symbol_expr(atom)
        except Exception:
            return None
        if not (isinstance(inner, FuncCall) and inner.name == "exp"
                and len(inner.args) == 1):
            return None
        lin = _linear_arg(inner.args[0], var)
        if lin is None:
            return None
        A += lin[0] * exp
        B += lin[1] * exp
    if abs(A) < 1e-15 and abs(B) < 1e-15:
        return ()                        # exp(0) = 1
    return ((_plain(_f("exp", _linear_expr(A, B, var))), 1.0),)


def _int_parts_form(key: tuple, coef: float, var: str) -> Expr | None:
    """单项式 ``P(x) * f(a*x+b)``（f ∈ {exp, sin, cos}）的表格分部积分。"""
    deg = 0.0
    fun: FuncCall | None = None
    for atom, exp in key:
        try:
            inner = symbol_expr(atom)
        except Exception:
            return None
        if isinstance(inner, Var) and inner.name == var:
            deg += exp
            continue
        if fun is not None or not isinstance(inner, FuncCall) or len(inner.args) != 1 \
                or inner.name not in ("exp", "sin", "cos") or exp != 1.0:
            return None
        if _linear_arg(inner.args[0], var) is None:
            return None
        fun = inner
    if fun is None or abs(deg - round(deg)) > 1e-12 or deg < 0:
        return None
    a, _b = _linear_arg(fun.args[0], var)
    u = _linear_expr(a, _b, var)
    return _int_xn_trig(int(round(deg)), coef, fun.name, u, a, var)


def _power_integral(var: str, exp: float, coef: float) -> Expr:
    if exp == -1:
        return Mul(_num(coef), _f("log", [Var(var)])) if coef != 1 else _f("log", [Var(var)])
    n1 = exp + 1
    c = coef / n1
    body = Pow(Var(var), _num(n1))
    return body if c == 1 else (Neg(body) if c == -1 else Mul(_num(c), body))


def _num(v: float) -> Num:
    r = round(v)
    return Num(float(r)) if abs(v - r) < 1e-12 else Num(v)


def _linear_arg(e: Expr, var: str) -> tuple[float, float] | None:
    """e == a*var + b → (a, b)；否则 None。"""
    p = poly(e)
    if p is None:
        return None
    a = b = 0.0
    for key, coef in p.items():
        if key == ():
            b += coef
        elif len(key) == 1 and key[0][0] == var and key[0][1] == 1.0:
            a += coef
        else:
            return None
    if a == 0:
        return None
    return (a, b)


def _linear_expr(a: float, b: float, var: str) -> Expr:
    head = Var(var) if a == 1 else Mul(_num(a), Var(var))
    if b == 0:
        return head
    return Add(head, _num(b)) if b > 0 else Sub(head, _num(-b))


def _int_single_atom(atom: str, exp: float, coef: float, var: str) -> Expr | None:
    """单个原子 ``f(a*x+b)**n`` 的积分。"""
    try:
        inner = symbol_expr(atom)
    except Exception:
        return None
    # sqrt(g) 等价 g**(1/2)，交给广义幂法则
    if isinstance(inner, FuncCall) and inner.name == "sqrt" and len(inner.args) == 1:
        inner, exp = inner.args[0], exp / 2.0
    if isinstance(inner, FuncCall) and inner.name in _TRIG_OF_LINEAR \
            and inner.name != "log" and len(inner.args) == 1:
        ab = _linear_arg(inner.args[0], var)
        if ab is None:
            return None
        a, b = ab
        u = inner.args[0] if ab == (1.0, 0.0) else _linear_expr(a, b, var)
        if exp == 2.0:
            got2 = _TABLE_2V.get(inner.name)
            if got2 is None:
                return None
            return _scale_expr(got2(u, var), coef / a)
        if exp != 1.0:
            return None            # 幂次交给 _int_trig_powers / _int_parts_form
        got = _TABLE_1V.get(inner.name)
        if got is None:
            return None
        res = got(_f(inner.name, u), u, var)
        if res is None:
            return None
        return _scale_expr(res, coef / a)
    if isinstance(inner, FuncCall) and inner.name in ("log", "ln") and exp == 1.0 \
            and len(inner.args) == 1:
        ab = _linear_arg(inner.args[0], var)
        if ab is None:
            return None
        a, b = ab
        u = _linear_expr(a, b, var)
        res = Sub(Div(Mul(u, _f("log", u)), _num(a)),
                  Div(u, _num(a)))
        return _scale_expr(res, coef)
    if isinstance(inner, Var) and inner.name != var:
        return None
    if exp == -1.0:
        lin = None if isinstance(inner, FuncCall) else _linear_arg(inner, var)
        if lin is None:
            return None
        a, b = lin
        res = Div(_f("log", _linear_expr(a, b, var)), _num(a))
        return _scale_expr(res, coef)
    if isinstance(inner, FuncCall):
        return None
    lin = _linear_arg(inner, var)
    if lin is not None:
        # (a x + b)**n 的广义幂法则（n 可为分数 / 负数，n != -1）
        a, b = lin
        n1 = exp + 1.0
        res = Div(Pow(_linear_expr(a, b, var), _num(n1)), _num(a * n1))
        return _scale_expr(res, coef)
    return None


_TABLE_1V = {
    "sin": lambda f, u, v: Neg(_f("cos", u)),
    "cos": lambda f, u, v: _f("sin", u),
    "exp": lambda f, u, v: _f("exp", u),
    "tan": lambda f, u, v: Neg(_f("log", [_f("cos", u)])),
    "cot": lambda f, u, v: _f("log", [_f("sin", u)]),
    "sec": lambda f, u, v: _f("log", [Add(_f("sec", u), _f("tan", u))]),
    "csc": lambda f, u, v: Neg(_f("log", [Add(_f("csc", u), _f("cot", u))])),
}

# 平方项表积分：∫sec²u du = tan u、∫csc²u du = -cot u、
# ∫tan²u du = tan u - u、∫cot²u du = -cot u - u
_TABLE_2V = {
    "sec": lambda u, v: _f("tan", u),
    "csc": lambda u, v: Neg(_f("cot", u)),
    "tan": lambda u, v: Sub(_f("tan", u), u),
    "cot": lambda u, v: Neg(Add(_f("cot", u), u)),
}


def _scale_expr(e: Expr, factor: float) -> Expr:
    if factor == 1.0:
        return e
    if factor == -1.0:
        return Neg(e)
    return Mul(_num(factor), e)


def _int_single(e: Expr, var: str) -> Expr | None:
    """非多项式入口的整体取幂 / 单函数积分。"""
    if isinstance(e, Pow):
        p = poly(e)
        if p is not None:
            return _int_poly(p, var)
        if isinstance(e.exponent, Num) and e.exponent.value == -1:
            return _int_denominator(e.base, 1.0, var)
        base_lin = _linear_arg(e.base, var)
        exp = e.exponent
        if base_lin is not None and isinstance(exp, Num) and exp.value != -1:
            a, b = base_lin
            return Div(Pow(_linear_expr(a, b, var), _num(exp.value + 1)),
                       _num(a * (exp.value + 1)))
        return None
    if isinstance(e, FuncCall) and len(e.args) == 1:
        return _int_single_atom(_plain(e), 1.0, 1.0, var)
    if isinstance(e, Log):
        return _int_single_atom(_plain(FuncCall("ln", [e.expr])), 1.0, 1.0, var)
    return None


def _plain(e: Expr) -> str:
    from src.kernel.symbolic.simplify import _plain_str
    return _plain_str(e)


def _int_mul(e: Mul, var: str) -> Expr | None:
    factors = _all_factors(e)
    coef = 1.0
    rest: list[Expr] = []
    for f in factors:
        if isinstance(f, Num):
            coef *= f.value
        elif isinstance(f, Neg):
            coef *= -1.0
            rest.append(f.expr)
        else:
            rest.append(f)
    if not rest:
        return Mul(_num(coef), Var(var))
    if len(rest) == 1:
        return _scale_expr(_int(rest[0], var), coef) if _int(rest[0], var) else None
    # exp(a x + b) * trig(c x + d)
    got = _int_exp_trig(rest, coef, var)
    if got is not None:
        return got
    # x**n * f(a x + b)
    got = _int_mul_parts(rest, coef, var)
    return got


def _all_factors(e: Expr) -> list[Expr]:
    if isinstance(e, Mul):
        return _all_factors(e.left) + _all_factors(e.right)
    return [e]


def _int_mul_parts(factors: list[Expr], coef: float, var: str) -> Expr | None:
    """P(x) * f(a*x+b) 的表格分部积分（P 为多项式，f ∈ {exp, sin, cos}）。"""
    poly_f = [f for f in factors if _is_poly_in(f, var)]
    fun_f = [f for f in factors if not _is_poly_in(f, var)]
    if len(poly_f) != 1 or len(fun_f) != 1:
        return None
    ab = None
    name = None
    f0 = fun_f[0]
    if isinstance(f0, FuncCall) and f0.name in (
            "exp", "sin", "cos", "log", "ln") and len(f0.args) == 1:
        ab = _linear_arg(f0.args[0], var)
        name = "log" if f0.name in ("log", "ln") else f0.name
    if ab is None or name is None:
        return None
    a, b = ab
    u = _linear_expr(a, b, var)
    p = poly(poly_f[0])
    if p is None:
        return None
    terms = sorted(((key_degree(k), c) for k, c in p.items()), reverse=True)
    # ∫ x^n e^{ax} 与 ∫ x^n sin/cos 用递推（对 n 逐次降幂）
    acc: list[Expr] = []
    for deg, c in terms:
        if abs(deg - round(deg)) > 1e-12 or deg < 0:
            return None
        sub = (_int_xn_log(int(round(deg)), c * coef, a, b, var)
               if name == "log" else
               _int_xn_trig(int(round(deg)), c * coef, name, u, a, var))
        if sub is None:
            return None
        acc.append(sub)
    if not acc:
        return Num(0)
    out = acc[0]
    for extra in acc[1:]:
        out = Add(out, extra)
    return out


def _is_poly_in(e: Expr, var: str) -> bool:
    p = poly(e)
    if p is None:
        return False
    return all(all(a == var for a, _ in k) for k in p)


def _int_xn_log(n: int, coef: float, a: float, b: float, var: str) -> Expr | None:
    """∫ c·x**n·log(a*x+b) dx（分部积分）：

    ``= x^(n+1)log(u)/(n+1) - a/(n+1)·∫x^(n+1)/u dx``，后者为有理函数。"""
    x = Var(var)
    u = _linear_expr(a, b, var)
    n1 = float(n + 1)
    head = Div(Mul(Pow(x, _num(n1)), _f("log", u)), _num(n1))
    rem = _int(Div(Pow(x, _num(n1)), u), var)
    if rem is None:
        return None
    return _chain_add([_scale_expr(head, coef), _scale_expr(rem, -coef * a / n1)])


def _int_xn_trig(n: int, coef: float, name: str, u: Expr, a: float, var: str) -> Expr | None:
    """∫ c*x**n*e^{u} / sin(u) / cos(u) dx，u = a*x+b（递推公式）。"""
    x = Var(var)
    fu = _f(name, u)
    if name == "exp":
        # ∫x^n e^{ax} = e^{ax} Σ_{k=0}^{n} (-1)^k n!/(n-k)! x^{n-k}/a^{k+1}
        parts: list[Expr] = []
        fact = 1.0
        for k in range(n + 1):
            fact = fact if k == 0 else fact * (n - k + 1)
            sign = -1.0 if k % 2 else 1.0
            cc = coef * sign * fact / (a ** (k + 1))
            if cc == 0:
                continue
            body = fu if n - k == 0 else Mul(fu, Pow(x, _num(float(n - k))))
            parts.append(body if cc == 1 else (Neg(body) if cc == -1 else Mul(_num(cc), body)))
        return _chain_add(parts)
    # 递推：∫x^m sin u = -x^m cos u/a + (m/a)∫x^{m-1} cos u
    #       ∫x^m cos u =  x^m sin u/a - (m/a)∫x^{m-1} sin u
    parts = []
    cur_n, cur_coef, cur_fn = n, coef, name
    while cur_n > 0:
        if cur_fn == "sin":
            lead_fn, lead_sgn, next_fn, rec_sgn = "cos", -1.0, "cos", 1.0
        else:
            lead_fn, lead_sgn, next_fn, rec_sgn = "sin", 1.0, "sin", -1.0
        body = Mul(Pow(x, _num(float(cur_n))), _f(lead_fn, u))
        parts.append(_scale_expr(body, cur_coef * lead_sgn / a))
        cur_coef = cur_coef * rec_sgn * cur_n / a
        cur_n -= 1
        cur_fn = next_fn
    base = Neg(_f("cos", u)) if cur_fn == "sin" else _f("sin", u)
    parts.append(_scale_expr(base, cur_coef / a))
    return _chain_add(parts)


def _chain_add(parts: list[Expr]) -> Expr | None:
    if not parts:
        return Num(0)
    out = parts[0]
    for p in parts[1:]:
        out = Add(out, p)
    return out


def _int_exp_trig(factors: list[Expr], coef: float, var: str) -> Expr | None:
    """∫ e^{a x+e} · sin/cos(b x+d) dx（含相位与异频率的通式）。

    ``∫e^{ax}sin(bx)dx = e^{ax}[a sin(bx) - b cos(bx)]/(a²+b²)``；
    ``∫e^{ax}cos(bx)dx = e^{ax}[a cos(bx) + b sin(bx)]/(a²+b²)``。
    """
    if len(factors) != 2:
        return None
    e1, e2 = factors
    if not (isinstance(e1, FuncCall) and isinstance(e2, FuncCall)):
        return None
    names = {e1.name, e2.name}
    if names not in ({"exp", "sin"}, {"exp", "cos"}):
        return None
    f_exp = e1 if e1.name == "exp" else e2
    f_trig = e2 if e1.name == "exp" else e1
    ab1 = _linear_arg(f_exp.args[0], var)
    ab2 = _linear_arg(f_trig.args[0], var)
    if ab1 is None or ab2 is None:
        return None
    a, _e = ab1
    b, _d = ab2
    den = a * a + b * b
    if den == 0.0:
        return None
    u = _linear_expr(a, _e, var)
    w = _linear_expr(b, _d, var)
    cos_w, sin_w = _f("cos", w), _f("sin", w)
    if f_trig.name == "sin":
        combo = Sub(Mul(_num(a), sin_w), Mul(_num(b), cos_w))
    else:
        combo = Add(Mul(_num(a), cos_w), Mul(_num(b), sin_w))
    return _scale_expr(Mul(_f("exp", u), combo), coef / den)


def _int_trig_powers(key: tuple, coef: float, var: str) -> Expr | None:
    """sin(u)**m * cos(u)**n（同一 u = a*x + b）的积分。

    - m 或 n 为奇数 → 剩一个奇因子后代换 w = 余函数，展开 (1-w²)^j
    - 两者皆偶 → 倍角幂归降（见 :func:`_even_power_integral`）
    """
    if not key or len(key) > 2:
        return None
    items: list[tuple[str, float, Expr]] = []
    for atom, exp in key:
        try:
            inner = symbol_expr(atom)
        except Exception:
            return None
        if not (isinstance(inner, FuncCall) and len(inner.args) == 1
                and inner.name in ("sin", "cos")):
            return None
        if abs(exp - round(exp)) > 1e-12 or exp <= 0:
            return None
        items.append((inner.name, exp, inner.args[0]))
    lins = [_linear_arg(it[2], var) for it in items]
    if any(l is None for l in lins):
        return None
    if len(items) == 2 and lins[0] != lins[1]:
        # 内函数不同（sin(x)*sin(2*x)、sin(3*x)*cos(2*x) 等）：积化和差
        if all(it[1] == 1 for it in items):
            return _int_trig_mixed(items, lins, coef, var)
        return None                # 不同内函数 + 高次：已登记为缺口
    funcs: dict[str, tuple[float, Expr]] = {}
    for name, exp, arg in items:
        funcs[name] = (funcs.get(name, (0.0, arg))[0] + exp, arg)
    u = next(iter(funcs.values()))[1]
    a, b = _linear_arg(u, var)
    uu = _linear_expr(a, b, var)
    m = funcs.get("sin", (0.0, u))[0]
    n = funcs.get("cos", (0.0, u))[0]
    if m % 2 == 1 or n % 2 == 1:
        if m % 2 == 1:
            base, p, keep, sign = "cos", m, n, -1.0   # w = cos u, dw = -sin u du
        else:
            base, p, keep, sign = "sin", n, m, 1.0    # w = sin u, dw = cos u du
        j = int((p - 1) // 2)
        expanded = poly(Pow(Sub(Num(1), Pow(Var("__w"), Num(2))), Num(float(j))))
        if expanded is None:
            return None
        acc: list[Expr] = []
        for pw, cc in expanded.items():
            deg = pw[0][1] if pw else 0.0
            got = _power_on_var("__w", deg + keep, sign * cc)
            if got is None:
                return None
            acc.append(got)
        inner_e = _chain_add(acc)
        if inner_e is None:
            return None
        return _scale_expr(canonical(inner_e.substitute("__w", _f(base, uu))), coef / a)
    return _int_trig_even(m, n, coef, uu, a, var)


def _int_trig_mixed(items: list, lins: list, coef: float, var: str) -> Expr | None:
    """∫ f1(a1*x+b1) * f2(a2*x+b2)，内函数不同且幂次均为 1：积化和差。

    ``sinA*cosB = [sin(A+B)+sin(A-B)]/2``；``sinA*sinB = [cos(A-B)-cos(A+B)]/2``；
    ``cosA*cosB = [cos(A+B)+cos(A-B)]/2``。其余组合返回 None（登记缺口）。
    """
    pairs = [(it[0], ab) for it, ab in zip(items, lins)]
    names = {p[0] for p in pairs}
    if names == {"sin", "cos"}:
        a_s, b_s = next(ab for n, ab in pairs if n == "sin")
        a_c, b_c = next(ab for n, ab in pairs if n == "cos")
        terms = [("sin", (a_s + a_c, b_s + b_c), 0.5),
                 ("sin", (a_s - a_c, b_s - b_c), 0.5)]
    elif names == {"sin"}:
        (a1, b1), (a2, b2) = pairs[0][1], pairs[1][1]
        terms = [("cos", (a1 - a2, b1 - b2), 0.5),
                 ("cos", (a1 + a2, b1 + b2), -0.5)]
    elif names == {"cos"}:
        (a1, b1), (a2, b2) = pairs[0][1], pairs[1][1]
        terms = [("cos", (a1 + a2, b1 + b2), 0.5),
                 ("cos", (a1 - a2, b1 - b2), 0.5)]
    else:
        return None
    # 负角归一：sin(-θ) = -sin θ、cos(-θ) = cos θ，避免输出 -sin(-x)/2 这类可读性噪声
    norm: list[tuple[str, tuple[float, float], float]] = []
    for fname, (a, b), w in terms:
        if a < 0:
            a, b = -a, -b
            if fname == "sin":
                w = -w
        norm.append((fname, (a, b), w))
    out: list[Expr] = []
    for fname, (a, b), w in norm:
        got = _int_linear_trig(fname, a, b, coef * w, var)
        if got is None:
            return None
        out.append(got)
    return _chain_add(out)


def _int_linear_trig(fname: str, a: float, b: float, coef: float, var: str) -> Expr | None:
    """∫ coef * fname(a*var + b) dvar（一次内函数的闭式项，a 可为 0）。"""
    if fname not in ("sin", "cos"):
        return None
    if abs(a) < 1e-15:
        try:
            c = math.sin(b) if fname == "sin" else math.cos(b)
        except (ValueError, OverflowError):
            return None
        if abs(c) < 1e-15:
            return Num(0)
        return _scale_expr(Var(var), coef * c)
    arg = _linear_expr(a, b, var)
    if fname == "sin":                      # ∫sin = -cos/a
        body = Div(_f("cos", arg), _num(-a))
    else:
        body = Div(_f("sin", arg), _num(a))
    return _scale_expr(body, coef)


def _power_on_var(name: str, total: float, coef: float) -> Expr | None:
    """∫ coef * w**total dw（total 为非负整数时才支持）。"""
    if coef == 0:
        return Num(0)
    if abs(total - round(total)) > 1e-12 or total < 0:
        return None
    t1 = total + 1.0
    body = Div(Pow(Var(name), _num(t1)), _num(t1)) if t1 != 1 else Var(name)
    return _scale_expr(body, coef)


def _int_trig_even(m: float, n: float, coef: float, uu: Expr, a: float,
                   var: str) -> Expr | None:
    """m、n 均为偶数的 sin^m cos^n：先化为单一偶次幂再用幂归降。"""
    if m and n:
        if m != n:
            return None                    # 不等偶次需递推，已登记为缺口
        ang = Mul(Num(2.0), uu)
        got = _even_power_integral("sin", int(m // 2), ang)
        if got is None:
            return None
        return _scale_expr(canonical(got), coef / (a * (2.0 ** int(m)) * 2.0))
    fn = "sin" if m else "cos"
    k = int((m or n) // 2)
    if k == 0:
        return _scale_expr(uu, coef / a)   # ∫1 du
    return _scale_expr(canonical(_even_power_integral(fn, k, uu)), coef / a)


def _even_power_integral(fn: str, k: int, u: Expr) -> Expr | None:
    """∫ fn(u)**(2k) du（幂归降）：

    ``cos^(2k) = 2^-2k [C(2k,k) + 2 Σ_{j<k} C(2k,j) cos(2(k-j)u)]``
    ``sin^(2k)`` 同式，但符号为 ``(-1)^(k-j)``。系数精确走整数 comb，
    只最后转 float，避免 1e-9 级尾差。
    """
    if k < 0 or fn not in ("sin", "cos"):
        return None
    nn = 2 * k
    scale = 1.0 / (1 << nn)
    out: list[Expr] = [Mul(_num(scale * math.comb(nn, k)), u)]
    for j in range(k):
        if fn == "sin":
            sgn = 1.0 if (k - j) % 2 == 0 else -1.0
        else:
            sgn = 1.0
        cc = scale * 2.0 * sgn * math.comb(nn, j)
        h = 2.0 * (k - j)
        ang = u if h == 1.0 else Mul(_num(h), u)
        got = Div(_f("sin", ang), _num(h))
        out.append(Mul(_num(cc), got) if cc != 1.0 else got)
    return _chain_add(out)


def _int_div(e: Div, var: str) -> Expr | None:
    num, den = e.numerator, e.denominator
    if isinstance(den, Num) and den.value != 0:
        got = _int(num, var)
        return None if got is None else Div(got, _num(den.value))
    return _int_rational(num, den, var)


def _int_denominator(inner: Expr, coef: float, var: str) -> Expr | None:
    return _int_rational(Num(1), inner, var)


def _int_rational(num: Expr, den: Expr, var: str) -> Expr | None:
    """有理函数积分：长除 → 一次因式部分分式 / 不可约二次。"""
    pn, pd = poly(num), poly(den)
    if pn is None or pd is None:
        return None
    if not _only_var(pd, var):
        return None
    dn = _to_dense(pn, var)
    dd = _to_dense(pd, var)
    if not dn or not dd:
        return None                    # 分子/分母不是关于 var 的多项式
    q, r = _poly_div(dn, dd)
    parts = []
    if any(abs(c) > 1e-12 for c in q):
        got = _int_poly(_from_dense(q, var), var)
        if got is None:
            return None
        parts.append(got)
    if any(abs(c) > 1e-12 for c in r):
        got = _int_proper(r, dd, var)
        if got is None:
            return None
        parts.append(got)
    return _chain_add(parts) if parts else Num(0)


def _only_var(p: dict, var: str) -> bool:
    return all(all(a == var for a, _ in k) for k in p)


def _to_dense(p: dict, var: str) -> list[float]:
    deg = int(max((key_degree(k) for k in p), default=0))
    coef = [0.0] * (deg + 1)
    for k, c in p.items():
        d = 0
        ok = True
        for a, e in k:
            if a != var or abs(e - round(e)) > 1e-12 or e < 0:
                ok = False
                break
            d += int(round(e))
        if not ok:
            return []
        coef[d] += c
    return coef[::-1]     # 高位在前


def _from_dense(c: list[float], var: str) -> dict:
    out: dict = {}
    n = len(c) - 1
    for i, v in enumerate(c):
        if abs(v) < 1e-15:
            continue
        d = n - i
        key = () if d == 0 else ((var, float(d)),)
        out[key] = out.get(key, 0.0) + v
    return out


def _poly_div(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    r = list(a)
    q = [0.0] * max(len(r) - len(b) + 1, 1)
    if len(r) < len(b):
        return [0.0], r
    db = len(b) - 1
    for i in range(len(q)):
        c = r[i] / b[0]
        q[i] = c
        for j in range(len(b)):
            r[i + j] -= c * b[j]
    while len(r) > 1 and abs(r[0]) < 1e-12:
        r.pop(0)
    return q, r


def _roots(coeffs: list[float]) -> list[float]:
    """实系数多项式的**全部**有理/简单根（≤2 次用公式；更高次用有理根定理 + 综合除法）。"""
    deg = len(coeffs) - 1
    if deg <= 0:
        return []
    if deg == 1:
        return [-coeffs[1] / coeffs[0]]
    if deg == 2:
        a, b, c = coeffs
        disc = b * b - 4 * a * c
        if disc < -1e-12:
            return []
        if abs(disc) < 1e-12:
            return [-b / (2 * a)]
        s = math.sqrt(disc)
        return [(-b + s) / (2 * a), (-b - s) / (2 * a)]
    roots: list[float] = []
    work = list(coeffs)
    for _ in range(deg):
        found = _rational_root(work)
        if found is None:
            return roots if len(work) == 3 else []
        roots.append(found)
        work = _synthetic(work, found)
        while len(work) > 1 and abs(work[0]) < 1e-12:
            work.pop(0)
        if len(work) == 3:
            roots.extend(_roots(work))
            return roots
        if len(work) == 1:
            break
    return roots


def _rational_root(coeffs: list[float]) -> float | None:
    """首一化后在整数因子中找一个实根。"""
    a0, an = coeffs[-1], coeffs[0]
    if abs(a0) < 1e-12:
        return 0.0
    lead = abs(an)
    cands: set[float] = set()
    for p in _divisors(round(abs(a0))):
        for qq in _divisors(round(abs(lead))):
            for s in (1, -1):
                cands.add(s * p / qq)
    for c in sorted(cands):
        if _horner(coeffs, c) is not None and abs(_horner(coeffs, c)) < 1e-7:
            return c
    return None


def _divisors(n: int) -> list[int]:
    if n <= 0:
        return [1]
    out = []
    i = 1
    while i * i <= n:
        if n % i == 0:
            out.append(i)
            if i * i != n:
                out.append(n // i)
        i += 1
    return out


def _horner(coeffs: list[float], x: float) -> float | None:
    try:
        v = coeffs[0]
        for c in coeffs[1:]:
            v = v * x + c
        return v
    except Exception:
        return None


def _synthetic(coeffs: list[float], r: float) -> list[float]:
    out = [coeffs[0]]
    for c in coeffs[1:]:
        out.append(out[-1] * r + c)
    return out[:-1]


def _int_proper(num: list[float], den: list[float], var: str) -> Expr | None:
    """真分式积分：一次因式 → log；二次因式按判别式分 distinct / 重根 / 不可约。

    支持「若干部一次因式 × 一个不可约二次因式」的混合分母（如 x**3+1 =
    (x+1)(x²-x+1)）：先用留数取走各单极点，再把余下分子除以一次因式之积，
    剩下的一次/二次分式交给 :func:`_int_quadratic`。
    """
    if len(den) == 2:
        a, b = den
        c = num[-1] / a
        return Mul(_num(c), _f("log", _linear_expr(a, b, var)))
    if len(den) == 3:
        return _int_quadratic(num, den, var)
    roots = _roots(den)
    if not roots or len(set(roots)) != len(roots):
        return None
    leftover = len(den) - 1 - len(roots)
    if leftover not in (0, 2):
        return None                      # 高次重根 / 三次以上不可约：已登记缺口
    dp = [den[i] * (len(den) - 1 - i) for i in range(len(den) - 1)]
    parts: list[Expr] = []
    resids: list[float] = []
    for r in roots:
        # 留数 = num(r) / den'(r)
        rv = _horner(dp, r)
        if rv is None or abs(rv) < 1e-14:
            return None
        resid = _horner(num, r) / rv
        if resid is None:
            return None
        resids.append(resid)
        parts.append(Mul(_num(resid), _f("log", _shift_expr(r, var))))
    if leftover == 2:
        quad = list(den)
        for r in roots:
            quad = _synthetic(quad, r)
        lin = [1.0]
        for r in roots:
            lin = _poly_mul(lin, [1.0, -r])
        n2 = list(num)
        for i, r in enumerate(roots):
            rest = [1.0]
            for j, s in enumerate(roots):
                if j != i:
                    rest = _poly_mul(rest, [1.0, -s])
            n2 = _poly_sub(n2, _poly_mul(_poly_mul([resids[i]], quad), rest))
        qq, rr = _poly_div(n2, lin)
        if any(abs(c) > 1e-9 for c in rr):
            return None
        got = _int_quadratic(qq, quad, var)
        if got is None:
            return None
        parts.append(got)
    return _chain_add(parts) if parts else None


def _poly_mul(a: list[float], b: list[float]) -> list[float]:
    """密集系数（高位在前）多项式乘法。"""
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x == 0.0:
            continue
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def _poly_sub(a: list[float], b: list[float]) -> list[float]:
    """密集系数（高位在前）多项式减法，按常数项右对齐。"""
    n = max(len(a), len(b))
    pa = [0.0] * (n - len(a)) + list(a)
    pb = [0.0] * (n - len(b)) + list(b)
    return [x - y for x, y in zip(pa, pb)]


def _shift_expr(r: float, var: str) -> Expr:
    """``x - r``（r 为负时自然成 x + |r|），统一走 from_poly 口径。"""
    return canonical(from_poly({((var, 1.0),): 1.0, (): -r}))


def _quad_expr(a: float, b: float, c: float, var: str) -> Expr:
    return canonical(from_poly({((var, 2.0),): a, ((var, 1.0),): b, (): c}))


def _coef_at(num: list[float], deg: int) -> float:
    """密集系数（高位在前）中取 ``var**deg`` 的系数。"""
    idx = len(num) - 1 - deg
    return num[idx] if idx >= 0 else 0.0


def _int_quadratic(num: list[float], den: list[float], var: str) -> Expr | None:
    a, b, c = den
    n1 = _coef_at(num, 1)
    n0 = _coef_at(num, 0)
    disc = b * b - 4 * a * c
    out: list[Expr] = []
    if disc > 1e-12:
        # 两个不同实根：按留数拆成两条 log
        s = math.sqrt(disc)
        for r in ((-b + s) / (2 * a), (-b - s) / (2 * a)):
            rv = 2 * a * r + b
            if abs(rv) < 1e-14:
                return None
            resid = (n1 * r + n0) / rv
            out.append(Mul(_num(resid), _f("log", _shift_expr(r, var))))
        return _chain_add(out) if out else Num(0)
    if disc > -1e-12:
        # 重根：R/a = A1*(x-r) + A2 → A1 log(x-r) - A2/(x-r)
        r = -b / (2 * a)
        a2 = (n1 * r + n0) / a
        a1 = n1 / a
        shift = _shift_expr(r, var)
        if abs(a1) > 1e-12:
            out.append(Mul(_num(a1), _f("log", shift)))
        if abs(a2) > 1e-12:
            out.append(_scale_expr(Div(Num(1), shift), -a2))
        return _chain_add(out) if out else Num(0)
    # 不可约二次：∫(n1 x + n0)/den = (n1/2a) log(den) + (n0 - n1 b/2a)·(2/√-disc) atan((x+b/2a)/h)
    k1 = n1 / a
    rest = n0 - k1 * b / 2.0
    if abs(rest) > 1e-12:
        h = math.sqrt(-disc) / (2 * abs(a))
        u = _shift_expr(-b / (2 * a), var)
        at = _f("atan", Div(u, _num(abs(h))))
        out.append(_scale_expr(at, rest * 2.0 * (1.0 if a > 0 else -1.0) / math.sqrt(-disc)))
    if abs(k1) > 1e-12:
        out.append(Mul(_num(k1 / 2.0), _f("log", _quad_expr(a, b, c, var))))
    return _chain_add(out) if out else Num(0)
