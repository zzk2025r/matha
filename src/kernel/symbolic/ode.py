"""内核符号引擎 · 常微分方程（纯标准库）。

``solve_ode(spec, func, var)`` 覆盖四类（与 sympy ``dsolve`` 的能力对照见
docs/symbolic_parity.md；不覆盖者抛 ``OdeUnsupported``，绝不返回「无法求解」这种
假成功字符串）：

1. ``y' = g(x)``：直接积分。
2. ``y' = g(x)·h(y)`` 可分离：h ∈ {1, y, y², 1/y}（其余形式如实报缺口）。
3. ``y' + p(x)·y = q(x)`` 一阶线性：积分因子 ``μ = e^{∫p}``。
4. ``a·y'' + b·y' + c·y = 0`` 二阶常系数齐次：特征方程（相异实根/重根/共轭复根）。
5. ``a·y'' + b·y' + c·y = r(x)`` 二阶常系数**非齐次**：齐次通解 + 待定系数特解，
   ``r(x)`` 限多项式 / 指数 ``e^{kx}`` / 正余弦 ``sin(ωx),cos(ωx)`` 及其多项式乘积
   （含共振：特征根与右端率重合时乘 ``x^s``）；越界右端（如 ``1/x``、``ln``、``tan``、
   分式幂）一律抛 ``OdeUnsupported``，绝不臆造特解。

输入记号兼容：``y'(x)``、``y'``、``dy/dx``、``y''``、``y(x)``，等号两侧自动移项。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math
import re

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)
from src.kernel.symbolic.diff import differentiate
from src.kernel.symbolic.integrate import integrate
from src.kernel.symbolic.latex import to_str
from src.kernel.symbolic.simplify import canonical, poly

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["solve_ode", "OdeUnsupported"]


class OdeUnsupported(ValueError):
    """内核不覆盖的 ODE 类型（如实失败）。"""


_PRE = re.compile(r"d2y/dx2|dy/dx")  # 保留：简写记号识别入口


def _normalize(spec: str, func: str, var: str) -> str:
    """把微分记号归一为普通变量名 ``y1``/``y2``/``y``（先长后短，否则
    ``y'(x)`` 会被 ``y(x)`` 的规则先吃掉剩下的撇号）。"""
    s = spec.strip()
    arg = r"\(\s*\w+\s*\)"
    s = re.sub(rf"{func}''{arg}", f"{func}2", s)
    s = re.sub(rf"{func}'{arg}", f"{func}1", s)
    s = re.sub(rf"{func}{arg}", func, s)
    s = re.sub(rf"{func}''", f"{func}2", s)
    s = re.sub(rf"{func}'", f"{func}1", s)
    s = s.replace("d2y/dx2", f"{func}2").replace("dy/dx", f"{func}1")
    return s


def solve_ode(spec: str, func_name: str = "y", var: str = "x") -> str:
    """求解 ODE，返回解表达式串（``y = ...`` 的右端，积分常量为 ``C1``/``C2``）。

    Examples:
        >>> solve_ode("y'(x) = x*y(x)", "y", "x")
        'C1*exp(x**2/2)'
    """
    y, yp, ypp = func_name, func_name + "1", func_name + "2"
    src = _normalize(spec, func_name, var)
    f = _parse_eq(src, var)
    order = 2 if ypp in f.free_vars() else (1 if yp in f.free_vars() else 0)
    if order == 2:
        return _solve_second_order(f, y, yp, ypp, var)
    if order == 0:
        raise OdeUnsupported(f"未出现导数项，不是 ODE: {spec}")
    return _solve_first_order(f, y, yp, var)


def _parse_eq(src: str, var: str) -> Expr:
    from src.kernel.symbolic.expr import symbol_expr
    if "=" in src:
        lhs, rhs = src.split("=", 1)
        return canonical(Sub(symbol_expr(lhs), symbol_expr(rhs)))
    return canonical(symbol_expr(src))


# ═══════════════════════════════════════════════════════════════════════════════
#  一阶
# ═══════════════════════════════════════════════════════════════════════════════

def _solve_first_order(f: Expr, y: str, yp: str, var: str) -> str:
    """把方程写成 ``A(x)*y' + B(x,y) = 0``，按可分离/线性/直接积分分派。"""
    a, rest = _isolate(f, yp)
    if a is None:
        raise OdeUnsupported(f"y' 未线性出现: {f}")
    g = canonical(Div(Neg(rest), a))          # y' = g(x, y)
    gpure = _without(g, y)
    if gpure is not None:
        anti = integrate(gpure, var)
        if anti is None:
            raise OdeUnsupported(f"g(x) 不可积（内核缺口）: {gpure}")
        return to_str(Add(anti, Var("C1")))
    sep = _separable(g, y, var)
    if sep is not None:
        hform, gx = sep
        sol = _solve_separable(hform, gx, y, var)
        if sol is not None:
            return sol
    lin = _linear_form(g, y, var)
    if lin is not None:
        p, q = lin
        sol = _solve_linear(p, q, y, var)
        if sol is not None:
            return sol
    raise OdeUnsupported(f"内核一阶 ODE 分类失败（非可分离/线性）: y' = {g}")


def _isolate(f: Expr, sym: str) -> tuple[Expr | None, Expr]:
    """f 中分离出 ``sym`` 的系数 A 与其余项 B（要求 f = A*sym + B，A 不含 sym）。"""
    p = poly(f)
    if p is None:
        return None, f
    a_terms: list[Expr] = []
    rest: dict = {}
    for key, coef in p.items():
        hit = [(i, e) for i, (atom, e) in enumerate(key) if atom == sym]
        if not hit:
            rest[key] = rest.get(key, 0.0) + coef
            continue
        if len(hit) > 1 or hit[0][1] != 1.0:
            return None, f            # y' 非线性
        others = tuple(kv for i, kv in enumerate(key) if i != hit[0][0])
        a_terms.append(_rebuild_monomial(others, coef))
    a = _chain(a_terms)
    b = from_poly_safe(rest)
    return a, b


def _rebuild_monomial(key: tuple, coef: float) -> Expr:
    from src.kernel.symbolic.simplify import from_poly
    out = from_poly({key: coef})
    return out if out is not None else Mul(Num(coef), Var("1"))


def from_poly_safe(p: dict) -> Expr:
    from src.kernel.symbolic.simplify import from_poly
    out = from_poly(p)
    return out if out is not None else Num(0)


def _chain(parts: list[Expr]) -> Expr:
    if not parts:
        return Num(0)
    out = parts[0]
    for p in parts[1:]:
        out = Add(out, p)
    return out


def _without(e: Expr, name: str) -> Expr | None:
    """若表达式不含变量 ``name`` 则返回自身，否则 None。"""
    return None if name in e.free_vars() else e


def _separable(g: Expr, y: str, var: str):
    """识别 ``g = gx(x) * hy(y)``，返回 (hy, gx)；不匹配返回 None。"""
    factors = _factor_list(g)
    only_y, only_x, mixed = [], [], []
    for f in factors:
        fv = f.free_vars()
        has_y, has_x = y in fv, (var in fv or not fv)
        if fv and fv <= {y}:
            only_y.append(f)
        elif fv and fv <= {var}:
            only_x.append(f)
        else:
            mixed.append(f)
    if mixed or not only_y:
        return None
    hy = _chain_prod(only_y)
    gx = _chain_prod(only_x) if only_x else Num(1)
    return hy, gx


def _factor_list(e: Expr) -> list[Expr]:
    if isinstance(e, Mul):
        return _factor_list(e.left) + _factor_list(e.right)
    return [e]


def _chain_prod(parts: list[Expr]) -> Expr:
    if not parts:
        return Num(1)
    out = parts[0]
    for p in parts[1:]:
        out = Mul(out, p)
    return canonical(out)


def _solve_separable(hy: Expr, gx: Expr, y: str, var: str) -> str | None:
    """∫dy/h(y) = ∫g(x)dx。h ∈ {1, y, y², 1/y}。"""
    anti_g = integrate(gx, var)
    if anti_g is None:
        return None
    k = _power_of_y(hy, y)
    if k is None:
        return None
    if k == 0:                                  # y' = g(x)
        return to_str(Add(anti_g, Var("C1")))
    if k == 1:                                  # y' = g y  →  y = C e^{∫g}
        return to_str(Mul(Var("C1"), FuncCall("exp", [anti_g])))
    if k == 2:                                  # y' = g y² →  y = -1/(∫g + C)
        den = Add(anti_g, Var("C1"))
        return to_str(Neg(Div(Num(1), den)))
    if k == -1:                                 # y' = g / y →  y² = 2∫g + C
        return to_str(FuncCall("sqrt", [Add(Mul(Num(2), anti_g), Var("C1"))]))
    if k < 0:
        p = -k + 1
        return to_str(FuncCall("nth_root",
                               [Add(Mul(_num(p), anti_g), Var("C1")), _num(p)]))
    return None


def _power_of_y(hy: Expr, y: str) -> float | None:
    """h(y) = y**k 的整数/分数幕指数 k（k==0 表示不依赖 y）。"""
    p = poly(hy)
    if p is None or len(p) != 1:
        return None
    key, coef = next(iter(p.items()))
    if abs(coef - 1.0) > 1e-12:
        return None
    if not key:
        return 0.0
    if len(key) == 1 and key[0][0] == y:
        return key[0][1]
    return None


def _linear_form(g: Expr, y: str, var: str):
    """y' = p(x)*y + q(x) → (-p, q)。"""
    p = poly(g)
    if p is None:
        return None
    coef_p: dict = {}
    rest: dict = {}
    for key, c in p.items():
        hit = [(i, e) for i, (a, e) in enumerate(key) if a == y]
        if not hit:
            rest[key] = rest.get(key, 0.0) + c
            continue
        if len(hit) > 1 or hit[0][1] != 1.0:
            return None
        others = tuple(kv for i, kv in enumerate(key) if i != hit[0][0])
        coef_p[others] = coef_p.get(others, 0.0) + c
    px = _chain([_rebuild_monomial(k, v) for k, v in coef_p.items()]) if coef_p else Num(0)
    qx = _chain([_rebuild_monomial(k, v) for k, v in rest.items()]) if rest else Num(0)
    return canonical(Neg(px)), canonical(qx)


def _solve_linear(p: Expr, q: Expr, y: str, var: str) -> str | None:
    """y' + p(x) y = q(x)：μ = e^{∫p}，y = (∫ μ q dx + C)/μ。"""
    ip = integrate(p, var)
    if ip is None:
        return None
    mu = FuncCall("exp", [ip])
    inner = integrate(Mul(mu, q), var)
    if inner is None:
        return None
    # y = (∫μq + C)/μ：逐项乘 μ**-1 再标准形，同幕原子才能约掉
    # （整体乘会因 poly 拒多顶负幂而退化成 `x*exp(-x)*exp(x)`）
    inv = Pow(mu, Num(-1.0))
    sol = canonical(_chain([canonical(Mul(t, inv)) for t in _add_flat(Add(inner, Var("C1")))]))
    return to_str(sol)


def _add_flat(e: Expr) -> list[Expr]:
    """Add/Sub 链摊平为带符号项列表。"""
    if isinstance(e, Add):
        return _add_flat(e.left) + _add_flat(e.right)
    if isinstance(e, Sub):
        return _add_flat(e.left) + [Neg(e.right)]
    return [e]


# ═══════════════════════════════════════════════════════════════════════════════
#  二阶常系数齐次
# ═══════════════════════════════════════════════════════════════════════════════

def _solve_second_order(f: Expr, y: str, yp: str, ypp: str, var: str) -> str:
    """``a·y'' + b·y' + c·y = r(x)``：齐次通解 + 非齐次待定系数特解。"""
    coeffs = _linear_coeffs_nonhom(f, (ypp, yp, y))
    if coeffs is None:
        raise OdeUnsupported(f"仅支持常系数线性方程（右端限多项式/指数/正余弦型）: {f}")
    a, b, c, r = coeffs
    if a == 0:
        raise OdeUnsupported(f"y'' 系数为零，退化为一阶: {f}")
    hom = _hom_solution(a, b, c, var)
    rp = canonical(r)
    if _is_zero(rp):
        return to_str(hom)
    part = _particular_second_order(a, b, c, rp, var)
    if part is None:
        raise OdeUnsupported(f"非齐次右端超出内核待定系数覆盖（多项式/指数/正余弦及其乘积）: {rp}")
    return to_str(canonical(Add(hom, part)))


def _exp_term(r: float, var: str) -> Expr:
    if r == 0:
        return Num(1)
    u = Mul(_num(r), Var(var)) if r != 1 else Var(var)
    return FuncCall("exp", [u])


def _is_zero(e: Expr) -> bool:
    """r 是否恒为零（多项式系数全 ~0）。"""
    p = poly(e)
    return p is not None and (not p or all(abs(v) < 1e-14 for v in p.values()))


def _hom_solution(a: float, b: float, c: float, var: str) -> Expr:
    """齐次通解 Expr（特征方程：相异实根 / 重根 / 共轭复根）。"""
    disc = b * b - 4 * a * c
    if abs(disc) < 1e-12:
        rr = -b / (2 * a)
        e1 = _exp_term(rr, var)
        return Add(Mul(Var("C1"), e1), Mul(Var("C2"), Mul(Var(var), e1)))
    if disc > 0:
        s = math.sqrt(disc)
        return Add(Mul(Var("C1"), _exp_term((-b + s) / (2 * a), var)),
                   Mul(Var("C2"), _exp_term((-b - s) / (2 * a), var)))
    alpha = -b / (2 * a)
    beta = abs(math.sqrt(-disc) / (2 * a))
    ea = _exp_term(alpha, var) if alpha != 0 else Num(1)
    arg = Var(var) if beta == 1 else Mul(_num(beta), Var(var))
    return Add(Mul(Var("C1"), Mul(ea, FuncCall("cos", [arg]))),
               Mul(Var("C2"), Mul(ea, FuncCall("sin", [arg]))))


def _linear_coeffs_nonhom(f: Expr, names: tuple[str, ...]):
    """f = a·y'' + b·y' + c·y − r（_parse_eq 已移项到左端），返回 (a,b,c, r_expr)。

    y''/y'/y 只允许**常数系数**（单项式仅含该导数原子且幂 1）；变系数（如 ``x*y``）
    或非线性（如 ``y**2``）→ None。其余原子（x 幕、exp/sin 原子）归入右端 r；
    r 由 ``r = -f|_(y=y'=y''=0)`` 保留超越结构地重建（不依赖 from_poly 回拼）。"""
    p = poly(f)
    if p is None:
        return None
    got = {n: 0.0 for n in names}
    for key, coef in p.items():
        fam = [(a, e) for (a, e) in key if a in names]
        if fam:
            if len(key) != 1 or fam[0][1] != 1.0:
                return None                # 变系数 / 非线性
            got[fam[0][0]] += coef
    zero = Num(0)
    fz = f.substitute(names[0], zero).substitute(names[1], zero).substitute(names[2], zero)
    r = canonical(Neg(fz))
    return tuple(got[n] for n in names) + (r,)


# ═════════════════════════════════════════════════════════════════════════════
#  非齐次待定系数特解
# ═════════════════════════════════════════════════════════════════════════════

def _particular_second_order(a: float, b: float, c: float, r: Expr, var: str) -> Expr | None:
    """对右端 r(x) 用待定系数法求特解 y_p（L[y_p]=r）；越界返回 None。

    流程：按 (率 α, 率 β, 三角, 多项式次数) 对 r 分组 → 每组用共振重数 s 乘 x^s
    生成试探基 φ_j → L[φ_j] 由内核解析求导 → 数值配点最小二乘（法方程）解出
    系数 u_j → y_p=Σ u_j φ_j → 回代自证 L[y_p]≈r，否则拒（None）。"""
    groups = _classify_forcing(r, var)
    if groups is None:
        return None
    basis: list[Expr] = []
    for (alpha, beta, trig, deg) in groups:
        s = _resonance(a, b, c, alpha, beta)
        basis += _trial_basis(alpha, beta, trig, deg, s, var)
    if not basis or len(basis) > 8:
        return None
    lphi = [_apply_l(a, b, c, phi, var) for phi in basis]
    pts = _sample_points(var, lphi, r, len(basis))
    if len(pts) < len(basis):
        return None
    W = [[_ev(e, var, t) for e in lphi] for t in pts]
    rhs = [_ev(r, var, t) for t in pts]
    if any(not _fin(row) for row in W) or not _fin(rhs):
        return None
    u = _solve_normal(W, rhs)
    if u is None:
        return None
    parts = [Mul(Num(float(uj)), phi) for uj, phi in zip(u, basis) if abs(uj) > 1e-9]
    yp = canonical(_chain(parts)) if parts else Num(0)
    if not _verify_l(a, b, c, yp, r, var, pts):
        return None
    return yp


def _fin(vals: list[float]) -> bool:
    return all(math.isfinite(v) for v in vals)


def _ev(e: Expr, var: str, t: float) -> float:
    try:
        return float(e.evaluate({var: t}))
    except Exception:
        return float("nan")


def _apply_l(a: float, b: float, c: float, phi: Expr, var: str) -> Expr:
    """L[φ] = a·φ'' + b·φ' + c·φ（解析求导）。"""
    d1 = differentiate(phi, var)
    d2 = differentiate(d1, var)
    return canonical(_chain([Mul(Num(a), d2), Mul(Num(b), d1), Mul(Num(c), phi)]))


def _resonance(a: float, b: float, c: float, alpha: float, beta: float) -> int:
    """率 λ*=α+iβ 作为特征根 aλ²+bλ+c 的重数（0/1/2；β>0 时至多 1）。"""
    lam = complex(alpha, beta)
    p = a * lam * lam + b * lam + c
    if abs(p) > 1e-8:
        return 0
    dp = 2 * a * lam + b
    if beta != 0:
        return 1
    return 1 if abs(dp) > 1e-8 else 2


def _linear_x(k: float, var: str) -> Expr:
    if k == 1:
        return Var(var)
    return canonical(Mul(Num(float(k)), Var(var)))


def _x_pow(n: int, var: str) -> Expr:
    if n == 0:
        return Num(1)
    if n == 1:
        return Var(var)
    return Pow(Var(var), Num(float(n)))


def _trial_basis(alpha: float, beta: float, trig: bool, deg: int, s: int, var: str) -> list[Expr]:
    """生成试探基：x^s·{x^m e^{αx} [·cos(βx), sin(βx)]}，m=0..deg。"""
    ef: Expr = Num(1) if alpha == 0 else FuncCall("exp", [_linear_x(alpha, var)])
    out: list[Expr] = []
    for m in range(deg + 1):
        core = canonical(Mul(_x_pow(s + m, var), ef))
        if not trig:
            out.append(core)
        else:
            arg = _linear_x(beta, var)
            out.append(canonical(Mul(core, FuncCall("cos", [arg]))))
            out.append(canonical(Mul(core, FuncCall("sin", [arg]))))
    return out


def _classify_forcing(r: Expr, var: str):
    """将 r 按 (α,β,trig) 分组，每组取最大多项式次数；越界项 → None。"""
    groups: dict[tuple, int] = {}
    for term in _add_flat(canonical(r)):
        info = _classify_term(term, var)
        if info is None:
            return None
        alpha, beta, trig, deg = info
        if deg < 0 or deg > 3:
            return None
        key = (round(alpha, 9), round(beta, 9), trig)
        groups[key] = max(groups.get(key, -1), deg)
    return [(al, be, tr, dg) for (al, be, tr), dg in groups.items()]


def _classify_term(term: Expr, var: str):
    """单项式 → (α,β,trig,deg)：x^deg · e^{αx} · {cos/sin}(βx)；越界 → None。"""
    alpha = beta = 0.0
    trig = False
    deg = 0
    for f in _factor_list(canonical(term)):
        if isinstance(f, Num):
            continue
        if isinstance(f, Var):
            if f.name != var:
                return None
            deg += 1
            continue
        if isinstance(f, Pow):
            base, expo = f.base, f.exponent
            if (isinstance(base, Var) and base.name == var and isinstance(expo, Num)
                    and float(expo.value).is_integer() and expo.value >= 0):
                deg += int(expo.value)
                continue
            return None
        if isinstance(f, FuncCall) and f.name in ("exp", "sin", "cos"):
            arg = f.args[0]
            if var not in arg.free_vars():          # e^{3}、sin(1) 等常数因子 → 吸收
                continue
            rate = _lin_rate(arg, var)
            if rate is None:
                return None
            if f.name == "exp":
                if alpha != 0.0:
                    return None
                alpha = rate
            else:
                if trig:
                    return None
                beta, trig = abs(rate), True
            continue
        return None
    return (alpha, beta, trig, deg)


def _lin_rate(arg: Expr, var: str) -> float | None:
    """arg 为纯 k·x（无常数项/高次）→ k；否则 None。"""
    arg = canonical(arg)
    if isinstance(arg, Var) and arg.name == var:
        return 1.0
    if isinstance(arg, Mul):
        fac = _factor_list(arg)
        vs = [x for x in fac if isinstance(x, Var)]
        nums = [x for x in fac if isinstance(x, Num)]
        others = [x for x in fac if not isinstance(x, (Var, Num))]
        if len(vs) != 1 or vs[0].name != var or others:
            return None
        k = 1.0
        for x in nums:
            k *= x.value
        return float(k)
    return None


def _sample_points(var: str, lphi: list[Expr], r: Expr, n: int) -> list[float]:
    """生成使 W/r 均有限的配点（多于 n 个以走最小二乘）。"""
    pts: list[float] = []
    base = [0.13, 0.41, 0.77, 1.19, 1.63, 2.07, 2.53, 2.91, 3.37, -0.29, -0.71, -1.31]
    need = max(n + 3, 2 * n)
    for t in base:
        ok = _fin([_ev(e, var, t) for e in lphi]) and _fin([_ev(r, var, t)])
        if ok:
            pts.append(t)
        if len(pts) >= need:
            break
    return pts


def _solve_normal(W: list[list[float]], rhs: list[float]) -> list[float] | None:
    """法方程 A=W^T W, b=W^T rhs 的最小二乘解（高斯消元）。"""
    n = len(W[0])
    A = [[sum(W[k][i] * W[k][j] for k in range(len(W))) for j in range(n)] for i in range(n)]
    b = [sum(W[k][i] * rhs[k] for k in range(len(W))) for i in range(n)]
    return _gauss(A, b)


def _gauss(A: list[list[float]], b: list[float]) -> list[float] | None:
    """带部分主元高斯消元；奇异 → None。"""
    m = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(m):
        piv = max(range(col, m), key=lambda rr: abs(M[rr][col]))
        if abs(M[piv][col]) < 1e-9:
            return None
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for rr in range(col + 1, m):
            fct = M[rr][col] / pv
            for cc in range(col, m + 1):
                M[rr][cc] -= fct * M[col][cc]
    x = [0.0] * m
    for rr in range(m - 1, -1, -1):
        s = M[rr][m] - sum(M[rr][cc] * x[cc] for cc in range(rr + 1, m))
        x[rr] = s / M[rr][rr]
    return x


def _verify_l(a: float, b: float, c: float, yp: Expr, r: Expr, var: str, pts: list[float]) -> bool:
    """回代自证：L[y_p] − r 在配点上须相对接近 0。"""
    lhs = _apply_l(a, b, c, yp, var)
    for t in pts:
        lv, rv = _ev(lhs, var, t), _ev(r, var, t)
        if not (math.isfinite(lv) and math.isfinite(rv)):
            return False
        if abs(lv - rv) > 1e-5 * (1.0 + abs(rv)):
            return False
    return True


def _num(v: float) -> Num:
    r = round(v)
    return Num(float(r)) if abs(v - r) < 1e-12 else Num(v)
