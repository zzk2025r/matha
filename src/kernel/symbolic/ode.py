"""内核符号引擎 · 常微分方程（纯标准库）。

``solve_ode(spec, func, var)`` 覆盖四类（与 sympy ``dsolve`` 的能力对照见
docs/symbolic_parity.md；不覆盖者抛 ``OdeUnsupported``，绝不返回「无法求解」这种
假成功字符串）：

1. ``y' = g(x)``：直接积分。
2. ``y' = g(x)·h(y)`` 可分离：h ∈ {1, y, y², 1/y}（其余形式如实报缺口）。
3. ``y' + p(x)·y = q(x)`` 一阶线性：积分因子 ``μ = e^{∫p}``。
4. ``a·y'' + b·y' + c·y = 0`` 二阶常系数齐次：特征方程（相异实根/重根/共轭复根）。

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
    coeffs = _linear_coeffs(f, (ypp, yp, y))
    if coeffs is None:
        raise OdeUnsupported(f"仅支持常系数线性齐次方程: {f}")
    a, b, c = coeffs
    if a == 0:
        raise OdeUnsupported(f"y'' 系数为零，退化为一阶: {f}")
    disc = b * b - 4 * a * c
    tol = 1e-12
    if abs(disc) < tol:
        r = -b / (2 * a)
        e1 = _exp_term(r, var)
        return to_str(Add(Mul(Var("C1"), e1),
                          Mul(Var("C2"), Mul(Var(var), e1))))
    if disc > 0:
        s = math.sqrt(disc)
        r1 = (-b + s) / (2 * a)
        r2 = (-b - s) / (2 * a)
        return to_str(Add(Mul(Var("C1"), _exp_term(r1, var)),
                          Mul(Var("C2"), _exp_term(r2, var))))
    alpha = -b / (2 * a)
    beta = abs(math.sqrt(-disc) / (2 * a))
    ea = _exp_term(alpha, var) if alpha != 0 else Num(1)
    arg = Var(var) if beta == 1 else Mul(_num(beta), Var(var))
    sol = Add(Mul(Var("C1"), Mul(ea, FuncCall("cos", [arg]))),
              Mul(Var("C2"), Mul(ea, FuncCall("sin", [arg]))))
    return to_str(sol)


def _exp_term(r: float, var: str) -> Expr:
    if r == 0:
        return Num(1)
    u = Mul(_num(r), Var(var)) if r != 1 else Var(var)
    return FuncCall("exp", [u])


def _linear_coeffs(f: Expr, names: tuple[str, ...]) -> tuple[float, ...] | None:
    """f = a·y'' + b·y' + c·y，返回 (a, b, c)；含任何非常数因子则 None。"""
    p = poly(f)
    if p is None:
        return None
    got = {n: 0.0 for n in names}
    for key, coef in p.items():
        if not key:
            return None                      # 非齐次项 → 不覆盖
        if len(key) != 1 or key[0][1] != 1.0:
            return None
        if key[0][0] not in got:
            return None
        got[key[0][0]] += coef
    return tuple(got[n] for n in names)


def _num(v: float) -> Num:
    r = round(v)
    return Num(float(r)) if abs(v - r) < 1e-12 else Num(v)
