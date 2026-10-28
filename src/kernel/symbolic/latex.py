"""内核符号引擎 · 解析与输出（纯标准库，手写 AST 发射）。

替换原先挂在 sympy 上的三件事：

- ``parse(text, namespace)``：手写文本→Expr（替 ``sympy.parse_expr``）。
- ``to_str(expr)``：机器可读标准串，口径对齐 sympy ``str()``（``2*x``、``x**3/3``）。
- ``to_latex(expr)`` / ``to_pretty(expr)``：手写 AST 发射（替 ``sympy.latex``/``pretty``）。

项序由 ``simplify.from_poly`` 的「总次数降序、同次按原子键升序」唯一决定；
因子序由本模块 ``_split_coeff`` 的 ``_factor_rank`` 分档决定（与 sympy 将
``exp(x)`` 视为 ``E**x`` 的排序一致）。两者均与输入树形无关，因此输出确定。
与 sympy 不逐字相同之处已在 docs/symbolic_parity.md 逐项登记。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic.expr import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var, symbol_expr,
)
from src.kernel.symbolic.simplify import canonical, rational_of, _plain_str

logger = logging.getLogger("matha.kernel.symbolic")

__all__ = ["parse", "parse_equation", "to_str", "to_latex", "to_pretty",
           "CONSTANTS", "MINUS", "Infinity"]

#: 数学常量。`pi`/`e` 以浮点近似进入表达式树（sympy 为精确符号 → 见 parity 文档）
CONSTANTS: dict[str, float] = {
    "pi": math.pi, "π": math.pi, "E": math.e, "tau": math.tau,
    "inf": math.inf, "oo": math.inf, "infinity": math.inf, "nan": math.nan,
}

MINUS = math.inf
NAN = math.nan


class Infinity:
    """正无穷常量（对齐 sympy ``oo`` 的用法位）。"""

    @staticmethod
    def is_instance(v) -> bool:
        return isinstance(v, float) and v == math.inf


_SUPER = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
          "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻"}

_ADD, _MUL, _POW, _ATOM = 1, 2, 3, 4

_TRIG = frozenset({"sin", "cos", "tan", "cot", "sec", "csc",
                   "sinh", "cosh", "tanh", "asin", "acos", "atan", "ln", "log"})


# ═══════════════════════════════════════════════════════════════════════════════
#  文本 → Expr
# ═══════════════════════════════════════════════════════════════════════════════

def parse(text: str, namespace: dict | None = None) -> Expr:
    """数学表达式字符串 → 内核 Expr（替 ``sympy_parse``）。

    支持 ``^``/``**`` 幂、全角括号、``pi``/``E``/``oo`` 常量、函数调用。
    ``namespace`` 兼容 sympy_parse 的形参：数值与 Expr 值都会被代入。

    Examples:
        >>> str(parse("x^2 + 2*x + 1"))
        'x**2 + 2*x + 1'
    """
    if isinstance(text, Expr):
        return canonical(text)
    if not isinstance(text, str):
        raise TypeError(f"parse 需要字符串，收到 {type(text).__name__}")
    src = text.strip()
    if not src:
        raise ValueError("空表达式")
    if "=" in src and not src.startswith(("==", "!=", "<", ">")):
        lhs, rhs = src.split("=", 1)
        src = f"({lhs})-({rhs})"
    e = symbol_expr(src)
    ns = dict(CONSTANTS) if namespace is None else {}
    if namespace:
        ns.update(namespace)
    for name, value in ns.items():
        if isinstance(value, Expr):
            e = e.substitute(name, value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            e = e.substitute(name, Num(float(value)))
    return canonical(e)


def parse_equation(text: str) -> Expr:
    """``lhs = rhs`` → ``lhs - rhs``（ODE/方程求值的统一入口）。"""
    if "=" not in text:
        return parse(text)
    lhs, rhs = text.split("=", 1)
    return parse(f"({lhs})-({rhs})")


# ═══════════════════════════════════════════════════════════════════════════════
#  Expr → 字符串
# ═══════════════════════════════════════════════════════════════════════════════

def to_str(expr: Expr, expand: bool = True) -> str:
    """机器可读标准串（先过 ``canonical``：合并同类项 + 稳定项序）。

    ``expand=False`` 跳过 canonical，按原树发射（用于保留泰勒 (x-a)^n 中心形式）。
    """
    return _emit(expr if not expand else canonical(expr), _ADD, "str")


def to_pretty(expr: Expr, expand: bool = True) -> str:
    """Unicode 美观串：``x² + 2x + 1``。``expand=False`` 时不乘开幂。"""
    return _emit(expr if not expand else canonical(expr), _ADD, "pretty")


def to_latex(expr: Expr, expand: bool = True) -> str:
    """LaTeX 发射：``x^{2} + 2 x + 1``。``expand=False`` 时不乘开幂。"""
    return _emit(expr if not expand else canonical(expr), _ADD, "latex")


def _numeral(v: float) -> str:
    r = round(v)
    if abs(v - r) < 1e-12 and abs(r) < 1e15:
        return str(int(r))
    if v == math.inf:
        return "oo"
    if v == -math.inf:
        return "-oo"
    if math.isnan(v):
        return "nan"
    return repr(v)


def _prec(e: Expr) -> int:
    if isinstance(e, (Add, Sub)):
        return _ADD
    if isinstance(e, (Mul, Div)):
        return _MUL
    if isinstance(e, Neg):
        return _MUL
    if isinstance(e, Pow):
        return _POW
    return _ATOM


def _emit(e: Expr, need: int, mode: str) -> str:
    s = _emit_raw(e, mode)
    if _prec(e) < need and not (mode == "latex" and isinstance(e, Div)):
        return f"({s})" if mode != "latex" else f"\\left({s}\\right)"
    return s


def _emit_raw(e: Expr, mode: str) -> str:
    if isinstance(e, Num):
        return _numeral(e.value)
    if isinstance(e, Var):
        return e.name
    if isinstance(e, Neg):
        return "-" + _emit(e.expr, _POW if isinstance(e.expr, (Add, Sub)) else _MUL, mode)
    if isinstance(e, (Add, Sub)):
        return _emit_sum(e, mode)
    if isinstance(e, Mul):
        return _emit_mul(e, mode)
    if isinstance(e, Div):
        return _emit_div(e, mode)
    if isinstance(e, Pow):
        return _emit_pow(e, mode)
    if isinstance(e, Log):
        return _emit_call("ln" if mode == "pretty" else "log", [e.expr], mode)
    if isinstance(e, FuncCall):
        return _emit_call(e.name, e.args, mode)
    return str(e)


# ── 加法链 ─────────────────────────────────────────────────────────────────────

def _signed_terms(e: Expr) -> list[tuple[int, Expr]]:
    """Add/Sub 链摊平为 [(符号, 非负项)]，保持原顺序（即 canonical 给出的项序）。

    项内部的前导负号（`Num(-1)`、`Neg(...)`、负系数 `Mul`）一律上提为项级符号，
    否则 `x**2 - 1` 会被拼成 `x**2 + 1`。
    """
    if isinstance(e, Add):
        return _signed_terms(e.left) + _signed_terms(e.right)
    if isinstance(e, Sub):
        return _signed_terms(e.left) + [(-s, t) for s, t in _signed_terms(e.right)]
    return _peel(1, e)


def _peel(sign: int, t: Expr) -> list[tuple[int, Expr]]:
    """把项 ``t`` 的前导负号折到 ``sign`` 上，返回单元素项列表。"""
    if isinstance(t, Neg):
        return _peel(-sign, t.expr)
    if isinstance(t, Num):
        if t.value < 0:
            return [(-sign, Num(-t.value))]
        return [(sign, t)]
    if isinstance(t, Mul):
        coef, factors = _split_coeff(t)
        if coef < 0:
            return [(-sign, _mul_from(-coef, factors))]
    return [(sign, t)]


def _mul_from(coef: float, factors: list[Expr]) -> Expr:
    body = factors[0]
    for f in factors[1:]:
        body = Mul(body, f)
    return body if coef == 1.0 else Mul(Num(coef), body)


def _emit_sum(e: Expr, mode: str) -> str:
    terms = _signed_terms(e)
    out: list[str] = []
    for sign, t in terms:
        body = _abs_emit(t, mode)
        if not out:
            out.append(("-" if sign < 0 else "") + body)
        elif mode == "latex":
            out.append((" - " if sign < 0 else " + ") + body)
        else:
            out.append((" - " if sign < 0 else " + ") + body)
    return "".join(out)


def _abs_emit(t: Expr, mode: str) -> str:
    """打印一个加法项的绝对值（把项内部的前导负号提出来）。"""
    if isinstance(t, Neg):
        t = t.expr
    if isinstance(t, Mul):
        coef, rest = _split_coeff(t)
        if coef < 0:
            return _mul_body(-coef, rest, mode)
    if isinstance(t, Num) and t.value < 0:
        return _numeral(-t.value)
    return _emit(t, _MUL, mode)


# ── 乘法链 ─────────────────────────────────────────────────────────────────────

def _split_coeff(e: Expr) -> tuple[float, list[Expr]]:
    """Mul 链 → (数值系数, 非数值因子列表)。

    因子按 sympy 口径排序：变量 → 一般幂（exp 在 sympy 内部是 E**x，故归入此类）→
    其他函数 → 括号型表达式；同档按名字典序，保证输出确定且与 sympy 一致。
    """
    coef = 1.0
    factors: list[Expr] = []
    for f in _factors(e):
        if isinstance(f, Num):
            coef *= f.value
        elif isinstance(f, Neg):
            coef *= -1.0
            inner = f.expr
            if isinstance(inner, Num):
                coef *= inner.value
            else:
                factors.append(inner)
        else:
            factors.append(f)
    factors.sort(key=lambda f: (_factor_rank(f), _plain_str(f)))
    return coef, factors


def _factor_rank(f: Expr) -> int:
    if isinstance(f, Var):
        return 0
    if isinstance(f, Pow):
        return 1
    if isinstance(f, FuncCall):
        return 2 if f.name == "exp" else 3
    if isinstance(f, Log):
        return 3
    return 4


def _factors(e: Expr) -> list[Expr]:
    if isinstance(e, Mul):
        return _factors(e.left) + _factors(e.right)
    return [e]


def _pow_parts(f: Expr) -> tuple[Expr, float]:
    """因子 → ``(底, 指数)``：``Pow(b, k)`` → (b, k)；``1/b`` → (b, -1)。"""
    if isinstance(f, Pow) and isinstance(f.exponent, Num):
        return f.base, f.exponent.value
    if isinstance(f, Div) and isinstance(f.numerator, Num) and f.numerator.value == 1.0:
        return f.denominator, -1.0
    return f, 1.0


def _product(factors: list[Expr], mode: str) -> str:
    if len(factors) == 1:
        return _emit(factors[0], _MUL, mode)
    parts = [_emit(f, _POW, mode) for f in factors]
    if mode == "latex":
        return "\\cdot ".join(parts) if _needs_cdot(parts) else " ".join(parts)
    if mode == "str":
        return "*".join(parts)
    return "".join(p if i == 0 else ("*" if not (p[0].isalpha()
                 and parts[i - 1][-1:].isdigit()) else "") + p
                   for i, p in enumerate(parts))


def _mul_body(coef: float, factors: list[Expr], mode: str) -> str:
    if not factors:
        return _numeral(coef)
    pos: list[Expr] = []
    den: list[Expr] = []
    for f in factors:
        head, exp = _pow_parts(f)
        if exp < 0:
            den.append(head if exp == -1.0 else Pow(head, _num_lit(-exp)))
        else:
            pos.append(f)
    if not den:
        body = _product(pos, mode) if pos else _numeral(coef)
        if coef == -1.0 and pos:
            return "-" + body
        if coef == 1.0 or not pos:
            return body
        if mode == "pretty":
            return f"{_numeral(coef)}{body}"
        if mode == "latex":
            return f"{_numeral(coef)} {body}"
        return f"{_numeral(coef)}*{body}"
    # 全部因子都是倒幂 → `2/(x + 1)`（与 sympy 一致），而非 `2*(1/(x + 1))`
    #
    # 系数的符号必须单独提成分数线前的 `-`：旧写法用 `_numeral(abs(coef))` 做分子，
    # 于是 `Mul(-1, (x+1)^-2)` 被发成 `1/(x + 1)**2` —— 树求值为负、文本却为正。
    neg = coef < 0
    if pos:
        numer = _product(pos, mode)
        if coef not in (1.0, -1.0):
            cs = _numeral(abs(coef))
            numer = (f"{cs}*{numer}" if mode == "str"
                     else f"{cs} {numer}" if mode == "latex"
                     else f"{cs}{numer}")
    else:
        numer = "1" if abs(coef) == 1.0 else _numeral(abs(coef))
    if len(den) == 1:
        dens = _emit(den[0], _POW, mode)
    else:
        dens = "(" + _product(den, mode) + ")"
    if mode == "latex":
        body = f"\\frac{{{numer}}}{{{dens}}}"
    else:
        body = f"{numer}/{dens}"
    return ("-" + body) if neg else body


def _num_lit(v: float) -> Num:
    return Num(float(v))


def _needs_cdot(parts: list[str]) -> bool:
    return any(p.startswith("\\") or "{" in p for p in parts)


def _emit_mul(e: Expr, mode: str) -> str:
    coef, factors = _split_coeff(e)
    if coef == 0:
        return "0"
    rat = rational_of(abs(coef))
    if rat is not None and rat[1] != 1 and factors:
        # 分数系数 → `x**3/3`（|p|==1）或 `2*x**3/3`
        p, q = rat
        num = _mul_body(float(abs(p)), factors, mode)
        body = (f"{num}/{_numeral(float(q))}" if mode != "latex"
                else f"\\frac{{{num}}}{{{q}}}")
        return body if p > 0 else ("-" + body)
    return _mul_body(coef, factors, mode)


def _emit_div(e: Expr, mode: str) -> str:
    num, den = e.numerator, e.denominator
    if isinstance(num, Div) and isinstance(num.numerator, Num) \
            and num.numerator.value == 1.0:
        # `1/a/b` → `1/(a*b)`（sympy 口径：`1/(2*sqrt(x))`）
        den = Mul(num.denominator, den)
        num = Num(1)
    if mode == "latex":
        return f"\\frac{{{_emit(num, _ADD, mode)}}}{{{_emit(den, _ADD, mode)}}}"
    ds = _emit(den, _MUL, mode)
    if isinstance(den, (Add, Sub, Mul, Div)) and not ds.startswith("("):
        ds = f"({ds})"
    return f"{_emit(num, _MUL, mode)}/{ds}"


def _emit_pow(e: Expr, mode: str) -> str:
    base, exp = e.base, e.exponent
    if mode == "latex" and isinstance(base, FuncCall) and base.name == "exp":
        return f"e^{{{_emit(exp, _ADD, mode)}}}"
    bs = _emit(base, _POW, mode)
    if mode == "latex":
        if isinstance(exp, Num) and not float(exp.value).is_integer():
            rat = rational_of(exp.value)
            if rat is not None:
                return f"{bs}^{{\\frac{{{rat[0]}}}{{{rat[1]}}}}}"
        return f"{bs}^{{{_emit(exp, _ADD, mode)}}}"
    if mode == "pretty" and isinstance(exp, Num) and float(exp.value).is_integer() \
            and abs(exp.value) <= 9:
        return bs + "".join(_SUPER[c] for c in str(int(exp.value)))
    if isinstance(exp, Num) and not float(exp.value).is_integer():
        # 分数指数：`x**(3/2)`（与 sympy 一致），否则 `x**1.5` 与 sympy 不同口径
        rat = rational_of(exp.value)
        if rat is not None:
            return f"{bs}**({rat[0]}/{rat[1]})"
    return f"{bs}**{_emit(exp, _POW, mode)}"


def _emit_call(name: str, args: list[Expr], mode: str) -> str:
    if mode == "latex":
        inner = ", ".join(_emit(a, _ADD, mode) for a in args)
        if name == "sqrt":
            return f"\\sqrt{{{inner}}}"
        if name == "abs":
            return f"\\left|{inner}\\right|"
        if name in ("exp", "e"):
            return f"e^{{{inner}}}"
        if name in _TRIG:
            return f"\\{name}{{\\left({inner}\\right)}}"
        return f"{name}{{\\left({inner}\\right)}}"
    # 函数参数内部不需要括号（sympy 口径：`log(x + 1)`、`exp(x**2)`）
    inner = ", ".join(_emit(a, _ADD, mode) for a in args)
    return f"{name}({inner})"
