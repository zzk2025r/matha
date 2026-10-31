"""内核符号引擎 · 化简 / 展开 / 合并同类项（纯标准库）。

本模块在内核 `expr.py` 的 Expr 数据层之上提供**算法层**能力：

- ``simplify_expr``：兼容原 ``src/symbolic.py`` 的薄封装（语义不变）。
- ``poly``：把表达式规范化为「单项式 → 系数」的稀疏多项式表示（内部核心）。
- ``expand``：乘法对加法的分配展开。
- ``collect``：合并同类项（含 sin(x)/exp(x) 等**不可分解原子**作为独立变量）。
- ``cancel``：有理式的公因子/数值 gcd 约简。
- ``canonical``：expand + collect + cancel 的标准形（所有输出与对拍的唯一口径）。
- ``trig_simplify``：sin²+cos²=1 等三角恒等式（有限子集，见 docs/symbolic_parity.md）。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math
from typing import Any

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = [
    "simplify_expr", "poly", "from_poly", "expand", "collect", "cancel",
    "canonical", "trig_simplify", "is_zero", "total_degree",
    "rational_of", "monomial_degree",
]

# 浮点系数视作精确值的容差
TOL = 1e-9
# 允许的一元函数原子（在多项式化简中作为「不可分解变量」处理）
ATOM_FUNCS = frozenset({
    "sin", "cos", "tan", "cot", "sec", "csc",
    "sinh", "cosh", "tanh", "exp", "log", "ln", "sqrt", "abs",
    "asin", "acos", "atan",
})

# (x+y)**n 展开的最大 n（防止项数爆炸）
_MAX_EXPAND_POW = 16


def simplify_expr(expr: Expr) -> Expr:
    """兼容原 ``src/symbolic.py`` 的化简入口（语义逐字保留）。"""
    return expr.simplify()


# ═══════════════════════════════════════════════════════════════════════════════
#  有理系数：以 (p, q) 整数对表示，避免 1/3 → 0.3333333333 的打印失真
# ═══════════════════════════════════════════════════════════════════════════════

def rational_of(value: float, max_den: int = 10_000) -> tuple[int, int] | None:
    """把浮点系数还原为既约 (p, q)；找不到小分母有理数则返回 None。

    用连分数渐近展开。接受准度要求 **相对 1e-12**（而不是 TOL=1e-9）：
    像 1/3、5/128 这类由小整数除法得到的系数在 double 下与真值完全相等，
    而 1/√3 = 0.5773502692 会被 1e-9 容差误匹为 10864/18817（差 1e-9），
    给打印引入本不存在的精度损失——宁显示小数也不假称分数。

    ``max_den`` 收到 1e4：连分数总能找到分母上百万的渐近分数以 1e-12 精度
    贴住无理解（如 1/√3 ≈ 564719/978122），那类「分数」是伪精度而非结构。
    """
    rel = 1e-12
    if not math.isfinite(value):
        return None
    if value == 0:
        return (0, 1)
    sign = 1 if value > 0 else -1
    v = abs(value)
    # 平凡整数
    if abs(v - round(v)) < TOL * max(1.0, v) and round(v) <= max_den:
        return (sign * int(round(v)), 1)
    h1, h0, k1, k0 = 1, 0, 0, 1
    x = v
    for _ in range(32):
        a = int(math.floor(x))
        h2 = a * h1 + h0
        k2 = a * k1 + k0
        if k2 > max_den:
            break
        h0, h1, k0, k1 = h1, h2, k1, k2
        frac = x - a
        if frac < 1e-12:
            break
        x = 1.0 / frac
        if abs(h1 / k1 - v) <= rel * max(1.0, v):
            return (sign * h1, k1)
    if k1 and abs(h1 / k1 - v) <= rel * max(1.0, v):
        return (sign * h1, k1)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  单项式 / 稀疏多项式表示
# ═══════════════════════════════════════════════════════════════════════════════

Monomial = tuple  # ((atom_key, exponent), ...) 已按 atom_key 排序
Poly = dict       # {Monomial: float 系数}


def _is_atom_repr(e: Expr) -> bool:
    """可作为「不可分解原子」的表达式：变量、一元函数作用于整体。"""
    if isinstance(e, Var):
        return True
    if isinstance(e, FuncCall):
        return e.name in ATOM_FUNCS and len(e.args) >= 1
    if isinstance(e, Log):
        return True
    return False


def monom_key(e: Expr) -> str:
    """原子的稳定字符串键（用结构化打印，不受括号噪声影响）。"""
    return _plain_str(e)


def _plain_str(e: Expr) -> str:
    """无空格、最简括号的稳定字符串（仅用于生成键，不作为对外输出）。"""
    if isinstance(e, Num):
        return repr(round(e.value, 12))
    if isinstance(e, Var):
        return e.name
    if isinstance(e, Neg):
        return f"-{_plain_str(e.expr)}"
    if isinstance(e, (Add, Sub)):
        op = "+" if isinstance(e, Add) else "-"
        return f"({_plain_str(e.left)}{op}{_plain_str(e.right)})"
    if isinstance(e, Mul):
        return f"({_plain_str(e.left)}*{_plain_str(e.right)})"
    if isinstance(e, Div):
        return f"({_plain_str(e.numerator)}/{_plain_str(e.denominator)})"
    if isinstance(e, Pow):
        return f"({_plain_str(e.base)}**{_plain_str(e.exponent)})"
    if isinstance(e, Log):
        return f"ln({_plain_str(e.expr)})"
    if isinstance(e, FuncCall):
        return f"{e.name}({','.join(_plain_str(a) for a in e.args)})"
    return str(e)


def _clean_exp(v: float) -> float:
    r = round(v)
    return float(r) if abs(v - r) < TOL else v


def key_degree(key: Monomial) -> float:
    return sum(p for _, p in key)


def total_degree(e: Expr) -> float:
    p = poly(e)
    if p is None:
        return 0.0
    return max((key_degree(k) for k in p if p[k] != 0), default=0.0)


def monomial_degree(e: Expr) -> float:
    return total_degree(e)


def poly(e: Expr) -> Poly | None:
    """表达式 → 稀疏多项式 {单项式: 系数}；不可表示返回 None。

    可表示的范围：+ - * /（除数不含加法结构）、整数/分数指数的幂、
    以及把 sin(x)、exp(x) 之类整体当作原子。
    """
    if isinstance(e, Num):
        return {(): e.value}
    if isinstance(e, Var):
        return {((monom_key(e), 1.0),): 1.0}
    if isinstance(e, Neg):
        p = poly(e.expr)
        return None if p is None else _scale(p, -1.0)
    if isinstance(e, Add):
        a, b = poly(e.left), poly(e.right)
        return None if a is None or b is None else _add(a, b)
    if isinstance(e, Sub):
        a, b = poly(e.left), poly(e.right)
        return None if a is None or b is None else _add(a, _scale(b, -1.0))
    if isinstance(e, Mul):
        a, b = poly(e.left), poly(e.right)
        if a is None or b is None:
            return None
        out = _mul(a, b)
        if _spread_negative(out):
            return None
        return out
    if isinstance(e, Div):
        a, b = poly(e.numerator), poly(e.denominator)
        if a is None or b is None or len(b) != 1:
            return None  # 分母含加法结构：不做多项式除法
        out = _div_monomial(a, b)
        # 商结构对 limit / domain 至关重要：只有**单项式**结果才允许负指数，
        # 否则 (1-cos x)/x**2 会被摊成 x**-2 - x**-2*cos(x)，除法外壳消失。
        return None if _spread_negative(out) else out
    if isinstance(e, Pow):
        base = poly(e.base)
        if base is None:
            return None
        if len(base) != 1:
            # (x+y)**n：仅**非负整数**指数走重复乘开分支。
            # 分数/负指数（如 (2*x+1)**1.5）必须返回 None 保留原结构，
            # 否则 int(1.5)==1 会把幂次静默降为 1，得出错误原函数。
            if isinstance(e.exponent, Num) and float(e.exponent.value).is_integer():
                n = int(e.exponent.value)
                if 0 <= n <= _MAX_EXPAND_POW:
                    acc: Poly = {(): 1.0}
                    for _ in range(n):
                        acc = _mul(acc, base)
                    return acc
            return None
        if isinstance(e.exponent, Num):
            return _pow_key(base, _clean_exp(e.exponent.value))
        return None
    if _is_atom_repr(e):
        return {((monom_key(e), 1.0),): 1.0}
    return None


def _spread_negative(p: Poly) -> bool:
    """多项式化后是否「负幂 + 和式」并存（会摧毁外层商/积结构）。"""
    if len(p) <= 1:
        return False
    return any(min((ex for _a, ex in k), default=0.0) < 0 for k in p)


def _pow_key(p: Poly, exponent: float) -> Poly:
    """单项式多项式整体取幂。"""
    if len(p) != 1:
        return {}
    k, coef = next(iter(p.items()))
    if exponent == 0:
        return {(): 1.0}
    nk = tuple(sorted((a, _clean_exp(pe * exponent))
                      for a, pe in k if pe * exponent != 0))
    try:
        new_coef = coef ** exponent
    except (OverflowError, ValueError, ZeroDivisionError):
        return {}
    return {nk: float(new_coef)}


def _scale(p: Poly, f: float) -> Poly:
    return {k: v * f for k, v in p.items() if v != 0}


def _add(a: Poly, b: Poly) -> Poly:
    out: Poly = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v
    return out


def _mul(a: Poly, b: Poly) -> Poly:
    out: Poly = {}
    for k1, c1 in a.items():
        for k2, c2 in b.items():
            k = _merge_key(k1, k2)
            out[k] = out.get(k, 0.0) + c1 * c2
    return out


def _merge_key(k1: Monomial, k2: Monomial) -> Monomial:
    acc: dict[str, float] = {a: e for a, e in k1}
    for a, e in k2:
        acc[a] = _clean_exp(acc.get(a, 0.0) + e)
    return _fuse_exps(tuple(sorted((a, e) for a, e in acc.items() if e != 0)))


def _fuse_exps(key: Monomial) -> Monomial:
    """同底幂合并：``exp(a)^i · exp(b)^j → exp(i*a + j*b)``。

    ODE 积分因子法必然产生这种乘积（μ · q 与 μ⁻¹ 相抵），不合并就会
    输出 `exp(-2*x)*exp(x)` 这类未化简项（sympy 给 `exp(-x)`）。
    """
    if sum(1 for a, _ in key if a.startswith("exp(")) < 2:
        return key
    inner: Expr | None = None
    rest: list[tuple[str, float]] = []
    for atom, exp in key:
        if not atom.startswith("exp("):
            rest.append((atom, exp))
            continue
        e = _parse_atom(atom)
        if not (isinstance(e, FuncCall) and e.name == "exp" and len(e.args) == 1):
            return key
        term = e.args[0] if exp == 1.0 else Mul(_num_expr(exp), e.args[0])
        inner = term if inner is None else Add(inner, term)
    if inner is None:
        return key
    p = poly(inner)
    fused = from_poly(p) if p is not None else None
    if fused is None:
        return key
    rest.append((_plain_str(FuncCall("exp", [fused])), 1.0))
    return tuple(sorted(rest, key=lambda kv: kv[0]))


def from_poly(p: Poly, var_hint: str = "") -> Expr | None:
    """稀疏多项式 → Expr 树（按总次数降序、同次按键升序，与 sympy 打印口径一致）。"""
    terms = [(k, c) for k, c in p.items() if c != 0 and math.isfinite(c)]
    if not terms:
        return Num(0)
    terms.sort(key=lambda kv: (-key_degree(kv[0]), _key_rank(kv[0]), kv[0]))
    out: Expr | None = None
    for k, c in terms:
        t = _term_expr(k, c)
        if t is None:
            return None
        out = t if out is None else _combine_add(out, t)
    return out


def _key_rank(key: Monomial) -> int:
    """同次项的次要序：纯变量项优先于函数项（与 sympy `x/2 - sin(2*x)/4` 一致）。"""
    return sum(1 for a, _ in key if "(" in a)


def _combine_add(a: Expr, b: Expr) -> Expr:
    """把下一项并入和式：负项要折成减号（Sub），不能写成 Sub(a, Neg(b))。"""
    if isinstance(b, Neg):
        return Sub(a, b.expr)
    if isinstance(b, Num) and b.value < 0:
        return Sub(a, Num(-b.value))
    if isinstance(b, Mul) and isinstance(b.left, Num) and b.left.value < 0:
        return Sub(a, Mul(_num_expr(-b.left.value), b.right))
    return Add(a, b)


def _term_expr(key: Monomial, coef: float) -> Expr | None:
    body: Expr | None = None
    for atom, exp in key:
        e = _atom_from_key(atom, exp)
        if e is None:
            return None
        body = e if body is None else Mul(body, e)
    if body is None:
        return Num(coef)
    if coef == 1.0:
        return body
    if coef == -1.0:
        return Neg(body)
    rat = rational_of(coef)
    if rat is not None and rat[1] != 1:
        p, q = rat
        num = body if abs(p) == 1 else Mul(_num_expr(abs(p)), body)
        den = _num_expr(q)
        core = Div(num, den)
        return core if p > 0 else Neg(core)
    return Mul(_num_expr(coef), body)


def _num_expr(v: float) -> Expr:
    r = round(v)
    return Num(float(r)) if abs(v - r) < TOL else Num(v)


def _atom_from_key(atom: str, exp: float) -> Expr | None:
    base = _parse_atom(atom)
    if base is None:
        return None
    if exp == 1.0:
        return base
    # exp(u)**n → exp(n*u)（n 为整数时），与 sympy 口径一致：
    # exp(x)**(-1) 打印为 exp(-x) 而非 1/exp(x)。
    if atom.startswith("exp(") and abs(exp - round(exp)) < TOL:
        inner = _parse_atom(atom)
        if isinstance(inner, FuncCall) and len(inner.args) == 1:
            # 参数再过一次标准形：`exp(-1*x)` 应得 `exp(-x)`
            arg = _structural(Mul(_num_expr(exp), inner.args[0]), True)
            return FuncCall("exp", [arg])
    if exp == 0.5:
        return FuncCall("sqrt", [base])
    if exp == -0.5:
        return Div(Num(1), FuncCall("sqrt", [base]))
    if exp == -1.0:
        return Div(Num(1), base)
    if exp < 0:
        return Div(Num(1), Pow(base, _num_expr(-exp)))
    return Pow(base, _num_expr(exp))


_ATOM_CACHE: dict[str, Expr] = {}


def _parse_atom(atom: str) -> Expr | None:
    """由原子键还原 Expr（原子键由 `_plain_str` 生成，形式受限）。"""
    cached = _ATOM_CACHE.get(atom)
    if cached is not None:
        return cached
    from src.kernel.symbolic.expr import symbol_expr  # 局部导入避免环
    try:
        e = symbol_expr(atom)
    except Exception:  # pragma: no cover - 原子键总是可解析
        return None
    if not _is_atom_repr(e):
        return None
    _ATOM_CACHE[atom] = e
    return e


# ═══════════════════════════════════════════════════════════════════════════════
#  对外算法
# ═══════════════════════════════════════════════════════════════════════════════

def expand(expr: Expr) -> Expr:
    """分配展开 + 合并同类项；不可多项式化时递归展开子树。"""
    return _structural(expr, want_poly=True)


def collect(expr: Expr, *vars: str) -> Expr:
    """合并同类项（``vars`` 省略时对全部自由变量合并）。"""
    return _structural(expr, want_poly=True)


def cancel(expr: Expr) -> Expr:
    """有理式约简：分母为单项式时直接吸收进多项式；含加法分母时逐项约数值 gcd。"""
    if isinstance(expr, Div):
        num, den = expr.numerator, expr.denominator
        pn, pd = poly(num), poly(den)
        if pn is not None and pd is not None and len(pd) == 1:
            rebuilt = from_poly(_div_monomial(pn, pd))
            if rebuilt is not None:
                return rebuilt.simplify()
    p = poly(expr)
    if p is not None:
        rebuilt = from_poly(p)
        if rebuilt is not None:
            return rebuilt.simplify()
    return expr.simplify()


def _div_monomial(pn: Poly, pd: Poly) -> Poly:
    """多项式除以单项式（除数必须是单项式）。"""
    k, c = next(iter(pd.items()))
    if c == 0:
        return {}
    neg = tuple((a, -pe) for a, pe in k)
    out: Poly = {}
    for kk, cc in pn.items():
        merged = _merge_key(kk, neg)
        out[merged] = out.get(merged, 0.0) + cc / c
    return out


def canonical(expr: Expr) -> Expr:
    """标准形：expand + collect + 三角恒等式，用于所有对拍与输出。"""
    out = _structural(trig_simplify(expr), want_poly=True)
    return out


def is_zero(expr: Expr) -> bool:
    """恒等于零的判定（多项式全系数为零 / 数值为零）。"""
    p = poly(expr)
    if p is not None:
        return all(abs(v) < TOL for v in p.values())
    try:
        return abs(expr.evaluate({})) < TOL
    except Exception:
        return False


def trig_simplify(expr: Expr) -> Expr:
    """三角恒等式子集：sin(u)² + cos(u)² = 1（同系数配对消去）。

    与 sympy ``trigsimp`` 不等价（sympy 覆盖倍角/和差化积等），
    偏差已在 docs/symbolic_parity.md 如实登记。
    """
    if isinstance(expr, (Neg, Log)):
        return type(expr)(trig_simplify(expr.expr))
    if isinstance(expr, (Add, Sub)):
        return _trig_pythagoras(type(expr)(trig_simplify(expr.left),
                                            trig_simplify(expr.right)))
    if isinstance(expr, Mul):
        return Mul(trig_simplify(expr.left), trig_simplify(expr.right))
    if isinstance(expr, Div):
        return Div(trig_simplify(expr.numerator), trig_simplify(expr.denominator))
    if isinstance(expr, Pow):
        return Pow(trig_simplify(expr.base), trig_simplify(expr.exponent))
    if isinstance(expr, FuncCall):
        return FuncCall(expr.name, [trig_simplify(a) for a in expr.args])
    return expr


def _trig_pythagoras(e: Expr) -> Expr:
    """把 sin(u)² 与 cos(u)² 的同系数对替换为常数（sin²+cos²=1）。"""
    p = poly(e)
    if p is None:
        return e
    paired: set[str] = set()
    const_extra = 0.0
    for key, coef in p.items():
        if len(key) != 1 or key[0][1] != 2.0:
            continue
        atom = key[0][0]
        if not (atom.startswith("sin(") and atom.endswith(")")):
            continue
        u = atom[4:-1]
        cos_key = ((f"cos({u})", 2.0),)
        if cos_key in p and abs(p[cos_key] - coef) < TOL and u not in paired:
            paired.add(u)
            const_extra += coef
    if not paired:
        return e
    out: Poly = {}
    for key, coef in p.items():
        if len(key) == 1 and key[0][1] == 2.0 and key[0][0][4:-1] in paired \
                and key[0][0].startswith(("sin(", "cos(")):
            continue
        out[key] = out.get(key, 0.0) + coef
    out[()] = out.get((), 0.0) + const_extra
    rebuilt = from_poly(out)
    return rebuilt if rebuilt is not None else e


def _structural(expr: Expr, want_poly: bool) -> Expr:
    # 函数参数自底向上先标准形：否则 `log(1 + x)` 这类嵌在原子键里的子式
    # 永远保留构造时的顺序。**不**对 Pow/Div 做同样的下钻：先把
    # `exp(x)**-1` 改写成 `exp(-x)` 会让父式展开时同幕原子无法合并。
    if isinstance(expr, (FuncCall, Log)):
        kids = expr._children()
        if kids:
            expr = _rebuild(expr, [_structural(k, want_poly) for k in kids])
    if want_poly:
        p = poly(trig_simplify(expr))
        if p is not None:
            rebuilt = from_poly(p)
            if rebuilt is not None:
                # 不再调用 `.simplify()`：旧的 Add.simplify 会把 Num 提到前面
                # （`x + 1` 变成 `1 + x`），与 sympy / from_poly 的次数降序相左。
                return rebuilt
    kids = expr._children()
    if not kids:
        return expr.simplify()
    return _rebuild(expr, [_structural(k, want_poly) for k in kids]).simplify()


def _rebuild(e: Expr, kids: list[Expr]) -> Expr:
    import dataclasses as _dc
    if isinstance(e, FuncCall):
        return FuncCall(e.name, kids)
    if isinstance(e, Log):
        return Log(kids[0])
    if _dc.is_dataclass(e):
        kwargs = {}
        it = iter(kids)
        for f in _dc.fields(e):
            v = getattr(e, f.name)
            kwargs[f.name] = next(it) if isinstance(v, Expr) else v
        return type(e)(**kwargs)
    return e
