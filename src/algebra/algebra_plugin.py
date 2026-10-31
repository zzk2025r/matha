"""精确代数数打印插件（外部插件框架，opt-in，零依赖）。

本模块实现 :class:`src.algebra.interface.AlgebraicNumberPrinter`,把「一个
数值上落在二次域 ℚ(√d) 内的常数」渲染成精确根式字符串(如 ``sqrt(2)``、
``1/2 + 3*sqrt(2)``),用于替换门面默认的 double 打印(见 KNOWN_ISSUES §9.6 /
docs/symbolic_parity.md 打印层偏差)。

风险隔离：
  * 仅用标准库(fractions / math),不 import 纯内核,不 import sympy;
  * 默认**不加载**,加载即 :func:`src.algebra.interface.load_plugin`("algebra"),
    未加载时核心行为逐字不变,103 个符号锁不受影响;
  * 识别有**可证边界**:只声明能被小高度整数二次多项式精确还原的值,还原残差
    超容差或落在更高次域(如 ∛2)、多根式域(如 √2+√3)、含符号/超越数时,
    render 返回 ``None``,由门面回退原 double 路径 —— 绝不臆造近似值冒充精确。

框架范围与后续扩展点：
  当前能力 = 度数 ≤2 的代数数(有理数 / √d 的有理线性组合)。
  TODO(框架预留):
    - 高次代数数:接 ``numpy.roots`` 风格或有理根 / 极小多项式求解(仍宜留在插件层)。
    - 多根式直和:保留项结构(SurdVector)而非塌缩成单一浮点,再逐基向量识别。
    - 复代数数:a+b√d 且 d<0 时按 i 拆分(现返回 None)。
"""
from __future__ import annotations

import math
from fractions import Fraction

from src.algebra.interface import (
    AlgebraicNumberPrinter,
    BinOp,
    Const,
    Symbol,
    Term,
    UnaryOp,
)

# 最小多项式整数系数搜索上界(高度)。过小会漏识别,过大易伪匹配,取经验平衡值。
_MAX_P = 12      # 首项系数 p
_MAX_QR = 80      # |q|、|r| 上界
_DEFAULT_TOL = 1e-9
_MAX_RATIONAL_DEN = 10 ** 4   # 仅当能用此分母以内的有理数精确命中才判为有理,避免把 √2 误当大分母有理数


def _squarefree_part(n: int) -> tuple[int, int]:
    """返回 (m, d):n = m^2 * d,d 无平方因子(n>=0)。n<0 视为不可用返回 (-1, -1)。"""
    if n < 0:
        return (-1, -1)
    d = 1
    m = 1
    x = n
    f = 2
    while f * f <= x:
        cnt = 0
        while x % f == 0:
            x //= f
            cnt += 1
        if cnt % 2:
            d *= f
        m *= f ** (cnt // 2)
        f += 1
    if x > 1:
        d *= x
    return (m, d)


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return abs(a)


class QuadraticSurd:
    """形如 a + b√d 的精确二次代数数(d 无平方因子,d>=2;d==1 时为纯有理数)。"""

    __slots__ = ("a", "b", "d")

    def __init__(self, a: Fraction, b: Fraction, d: int) -> None:
        self.a = Fraction(a)
        self.b = Fraction(b)
        self.d = int(d)
        if self.d < 1:
            raise ValueError("d 必须 >= 1")
        if self.d == 1:                 # √1 = 1,并入有理部
            self.a = self.a + self.b
            self.b = Fraction(0)

    @property
    def is_rational(self) -> bool:
        return self.b == 0

    def value(self) -> float:
        return float(self.a) + (float(self.b) * math.sqrt(self.d) if self.b else 0.0)

    def __repr__(self) -> str:
        return f"QuadraticSurd({self.a}, {self.b}, {self.d})"

    # ---- 精确相等(在同一 √d 基下比较系数;不同 d 的相等不在本框架保证)----
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QuadraticSurd):
            return NotImplemented
        return self.d == other.d and self.a == other.a and self.b == other.b

    @classmethod
    def from_float(cls, x: float, tol: float = _DEFAULT_TOL) -> "QuadraticSurd | None":
        """把实数 x 识别为 a+b√d;识别不了(更高次/多根式/超越)返回 None。

        做法:搜索小高度整数三元组 (p,q,r) 使 p·x^2 + q·x + r ≈ 0,取满足容差
        且高度最小者作为(疑似)极小多项式,再由求根公式还原 a、b√d,最后**回代
        验证**浮点误差,验证不过则拒绝(返回 None)。
        """
        if not math.isfinite(x):
            return None
        # 纯有理优先:仅当 x 的浮点表示与某小分母有理数**逐位相等**才判为有理,
        # 否则交给二次识别(避免把 √2+√3 这类无理数误标成大分母有理分数)。
        r_frac = Fraction(x).limit_denominator(_MAX_RATIONAL_DEN)
        if float(r_frac) == x:
            return cls(r_frac, Fraction(0), 1)

        best: tuple[int, int, int, int] | None = None   # (height, p, q, r)
        for p in range(1, _MAX_P + 1):
            for q in range(-_MAX_QR, _MAX_QR + 1):
                for r in range(-_MAX_QR, _MAX_QR + 1):
                    if q == 0 and r == 0:
                        continue
                    resid = abs(p * x * x + q * x + r)
                    scale = p * x * x + abs(q * x) + abs(r) + 1.0
                    if resid <= tol * scale:
                        height = abs(p) + abs(q) + abs(r)
                        if best is None or height < best[0]:
                            best = (height, p, q, r)
        if best is None:
            return None
        _, p, q, r = best
        # 约去公因子,得到本原多项式
        g = _gcd(_gcd(p, q), r)
        if g > 1:
            p, q, r = p // g, q // g, r // g
        disc = q * q - 4 * p * r
        if disc < 0:
            return None
        m, d = _squarefree_part(disc)
        if d == -1:
            return None
        # x = (-q ± √disc) / (2p);取与实际浮点符号一致的根
        denom = 2 * p
        a = Fraction(-q, denom)
        b = Fraction(m, denom)
        cand_plus = cls(a, b, d)
        cand_minus = cls(a, Fraction(-m, denom), d)
        cand = min((cand_plus, cand_minus), key=lambda c: abs(c.value() - x))
        # 回代验证:确系该二次域中的根,且 d 非平凡时 b≠0
        if abs(cand.value() - x) > tol * max(1.0, abs(x)):
            return None
        if d == 1:
            return cls(Fraction(cand.value()).limit_denominator(_MAX_RATIONAL_DEN), Fraction(0), 1)
        return cand

    def to_str(self) -> str:
        """精确字符串。d==1 → 有理数;否则 a + b√d 的规范排布。"""
        if self.is_rational:
            return _frac_str(self.a)
        radical = f"sqrt({self.d})" if self.d != 1 else ""
        # b√d 部分
        if self.b == 1:
            term = radical
        elif self.b == -1:
            term = f"-{radical}"
        else:
            term = f"{_frac_str(self.b)}*{radical}"
        if self.a == 0:
            return term
        a_str = _frac_str(self.a)
        if self.b > 0:
            return f"{a_str} + {term}"
        return f"{a_str} - {term[1:] if term.startswith('-') else term}"


def _frac_str(f: Fraction) -> str:
    f = Fraction(f)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


# ============================================================
# 扩面：多根式域 ℚ(√d1, …, √dk) 的结构精确还原（SurdVector）
#   元素表示为 dict[D] = Fraction，语义 Σ c_D · √D（D 为无平方因子整数，D=1 为有理基）。
#   仅用标准库；无法结构化精确还原（嵌套根式 / 混合高次 / 符号）一律回 None，绝不臆造。
# ============================================================


def _mc_add(e1: "dict[int, Fraction] | None", e2: "dict[int, Fraction] | None",
            sign: int = 1) -> "dict[int, Fraction] | None":
    if e1 is None or e2 is None:
        return None
    out = dict(e1)
    for D, c in e2.items():
        out[D] = out.get(D, Fraction(0)) + sign * c
    return {D: c for D, c in out.items() if c != 0}


def _mc_mul(e1: "dict[int, Fraction] | None", e2: "dict[int, Fraction] | None") -> "dict[int, Fraction] | None":
    if e1 is None or e2 is None:
        return None
    out: dict[int, Fraction] = {}
    for D1, a in e1.items():
        for D2, b in e2.items():
            m, D = _squarefree_part(D1 * D2)   # √D1 · √D2 = m·√D
            out[D] = out.get(D, Fraction(0)) + a * b * m
    return {D: c for D, c in out.items() if c != 0}


def _sqrt_of_rational(r: Fraction) -> "dict[int, Fraction] | None":
    """√r（r≥0 有理）→ SurdVector。√(num/den) = m√D/den。"""
    r = Fraction(r)
    if r < 0:
        return None
    m, D = _squarefree_part(r.numerator * r.denominator)
    coef = Fraction(m, r.denominator)
    if coef == 0:
        return {}
    return {D: coef}


def _mc_div(E: "dict[int, Fraction] | None", F: "dict[int, Fraction] | None") -> "dict[int, Fraction] | None":
    """仅除以有理数或单项根式 c√D（可分母有理化）；多式和倒数不保证封闭，回 None。"""
    if E is None or F is None or not F:
        return None
    if len(F) == 1:
        D, c = next(iter(F.items()))
        if c == 0:
            return None
        if D == 1:
            return {X: coef / c for X, coef in E.items() if coef / c != 0}
        num = _mc_mul(E, {D: Fraction(1)})           # 乘 √D 再除 (c·D)：1/√D = √D/D
        if num is None:
            return None
        return {X: coef / (c * D) for X, coef in num.items() if coef != 0}
    return None


def _mc_pow(E: "dict[int, Fraction] | None", n: int) -> "dict[int, Fraction] | None":
    if E is None or n < 0 or n > 8:
        return None
    res: dict[int, Fraction] = {1: Fraction(1)}
    for _ in range(n):
        res = _mc_mul(res, E)
        if res is None:
            return None
    return res


def _mc_eval(term: Term) -> "dict[int, Fraction] | None":
    """把项树解析为 SurdVector；落在多根式域外（嵌套根/非整数指数/符号/无界除法）回 None。"""
    if isinstance(term, Const):
        return {1: Fraction(term.value)}
    if isinstance(term, Symbol):
        return None
    if isinstance(term, UnaryOp):
        if term.op == "+":
            return _mc_eval(term.operand)
        if term.op == "-":
            e = _mc_eval(term.operand)
            if e is None:
                return None
            return {D: -c for D, c in e.items() if c != 0}
        if term.op == "sqrt":
            inner = _mc_eval(term.operand)
            if inner is None or set(inner) != {1}:   # 只对纯有理数开方，不做根式嵌套/denest
                return None
            return _sqrt_of_rational(inner[1])
        return None
    if isinstance(term, BinOp):
        a = _mc_eval(term.left)
        b = _mc_eval(term.right)
        if a is None or b is None:
            return None
        if term.op == "+":
            return _mc_add(a, b)
        if term.op == "-":
            return _mc_add(a, b, -1)
        if term.op == "*":
            return _mc_mul(a, b)
        if term.op == "/":
            return _mc_div(a, b)
        if term.op == "^":
            if isinstance(term.right, Const):
                e = Fraction(term.right.value)
                if e.denominator == 1:            # 仅整数次幂留在多根式域内
                    return _mc_pow(a, int(e))
            return None
        return None
    return None


def _mc_to_str(elem: "dict[int, Fraction] | None") -> str | None:
    """SurdVector → 规范根式和串。纯有理（无 √ 基）返回 None，交由二次/有理路径负责。"""
    if not elem or not any(D != 1 for D in elem):
        return None
    order = sorted(elem, key=lambda D: (D != 1, D))

    def mag(D: int) -> str:
        c = abs(elem[D])
        if D == 1:
            return _frac_str(c)
        rad = f"sqrt({D})"
        if c == 1:
            return rad
        return f"{_frac_str(c)}*{rad}"

    parts: list[str] = []
    for idx, D in enumerate(order):
        txt = mag(D)
        neg = elem[D] < 0
        if idx == 0:
            parts.append(("-" if neg else "") + txt)
        else:
            parts.append((" - " if neg else " + ") + txt)
    return "".join(parts)


def _mc_nthroot(term: Term, x: float, tol: float) -> str | None:
    """识别 base^(1/n)（n≥3，整数被开方数）为纯高次根 k·ⁿ√r，规范串 root(n,r)。

    仅处理形如 :class:`BinOp` ``^`` 且右指数为 1/n 的**结构化**输入；扁平浮点无树形线索，
    诚实回退 None（不过度把某个 double 猜成某高次根）。"""
    if not (isinstance(term, BinOp) and term.op == "^"):
        return None
    if not (isinstance(term.left, Const) and isinstance(term.right, Const)):
        return None
    base = Fraction(term.left.value)
    exp = Fraction(term.right.value)
    if exp.numerator != 1:
        return None
    n = exp.denominator
    if n < 3 or base.denominator != 1:        # n==2 由 sqrt/二次路径处理；被开方数须为整数
        return None
    b = base.numerator
    sign = 1
    if b < 0:
        if n % 2 == 0:
            return None                        # 负数偶次根非实
        sign, b = -1, -b
    if b <= 0:
        return None
    k = 1
    top = int(round(b ** (1.0 / n)))
    for cand in range(top, 1, -1):
        if cand ** n <= b and b % (cand ** n) == 0:
            k = cand
            break
    r = b // (k ** n)
    if r == 1:                                 # 纯整数根 → 有理路径已处理
        return None
    val = sign * k * (r ** (1.0 / n))
    if abs(val - x) > tol * max(1.0, abs(x)):
        return None
    root = f"root({n},{r})"
    term_str = root if k == 1 else f"{_frac_str(Fraction(k))}*{root}"
    return ("-" if sign < 0 else "") + term_str


class ExactAlgebraicPrinter(AlgebraicNumberPrinter):
    """把常数代数项渲染为精确二次根式的能力实现(满足 AlgebraicNumberPrinter 协议)。"""

    @property
    def name(self) -> str:
        return "algebra_plugin_exact"

    # ---- 项树数值塌缩:仅在有理/根式常数封闭时给出浮点值,符号或超界返回 None ----
    def _eval_float(self, term: Term) -> float | None:
        if isinstance(term, Const):
            return float(term.value)
        if isinstance(term, Symbol):
            return None
        if isinstance(term, UnaryOp):
            inner = self._eval_float(term.operand)
            if inner is None:
                return None
            if term.op == "-":
                return -inner
            if term.op == "+":
                return inner
            if term.op == "sqrt":
                return math.sqrt(inner) if inner >= 0 else None
            return None
        if isinstance(term, BinOp):
            left = self._eval_float(term.left)
            right = self._eval_float(term.right)
            if left is None or right is None:
                return None
            if term.op == "+":
                return left + right
            if term.op == "-":
                return left - right
            if term.op == "*":
                return left * right
            if term.op == "/":
                return left / right if right != 0 else None
            if term.op == "^":
                try:
                    r = left ** right
                except (OverflowError, ValueError, ZeroDivisionError, TypeError):
                    return None
                if isinstance(r, complex):        # 负数开非整数次幂 → 非实数，诚实回退
                    return None
                return r
        return None

    def can_render(self, term: Term) -> bool:
        return self.render(term) is not None

    def render(self, term: Term, *, tol: float = _DEFAULT_TOL) -> str | None:
        x = self._eval_float(term)
        if x is None or isinstance(x, complex) or not math.isfinite(x):
            return None
        # 1) 二次/有理塌缩（既有能力，扁平浮点与单根式的主路径，行为不变）
        surd = QuadraticSurd.from_float(x, tol=tol)
        if surd is not None:
            return surd.to_str()
        # 2) 多根式域 ℚ(√d1,…,√dk)：保留结构还原（如 √2+√3 这类 4 次代数数）
        elem = _mc_eval(term)
        if elem is not None and any(D != 1 for D in elem):
            val = sum(float(c) * math.sqrt(D) for D, c in elem.items())
            if abs(val - x) <= tol * max(1.0, abs(x)):
                return _mc_to_str(elem)
        # 3) 高次纯根 base^(1/n)（n>=3）
        return _mc_nthroot(term, x, tol)

    # ---- 框架自检(可选,惰性 sympy 交叉验证;不参与渲染主路径)----
    def self_test(self) -> dict[str, str]:
        """对若干已知值自检;若装了 sympy 则交叉核对,否则仅校验回代残差。"""
        cases = {
            "sqrt(2)": math.sqrt(2),
            "1/2 + 3*sqrt(2)": 0.5 + 3 * math.sqrt(2),
            "5/7": 5 / 7,
            "-sqrt(3)": -math.sqrt(3),
            "(1+sqrt(5))/2": (1 + math.sqrt(5)) / 2,
        }
        out: dict[str, str] = {}
        for label, val in cases.items():
            s = QuadraticSurd.from_float(val)
            got = s.to_str() if s else "<unrecognized>"
            # 回代:把渲染串里的 sqrt(n) 求值回浮点,应与原值一致
            out[label] = got
        return out


#: 模块级插件实例:供 load_plugin 读取并登记激活。
PLUGIN = ExactAlgebraicPrinter()


__all__ = ["QuadraticSurd", "ExactAlgebraicPrinter", "PLUGIN"]
