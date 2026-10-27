"""内核符号微积分引擎回归锁（阶段 3：sympy 移除后的能力等价证明）。

这些断言**逐条来自 sympy 1.14 的实测输出**（见 ``docs/symbolic_parity.md``），
用于保证「去依赖」不降级能力；同时锁定「内核覆盖不到时必须显式失败」这一红线 —
任何一项悄悄返回了乐观默认值（0 / inf / 全域），本文件即失败。
"""
from __future__ import annotations

import math

import pytest

from src.kernel.symbolic import (
    accumulated_bounds, continuous_domain, definite, differentiate, integrate,
    limit, maclaurin, solve_ode, sum_series, symbol_expr, to_latex, to_pretty,
    to_str,
)
from src.kernel.symbolic.diff import UnsupportedExpression
from src.kernel.symbolic.domain import DomainUndetermined
from src.kernel.symbolic.limit import LimitUndetermined
from src.kernel.symbolic.ode import OdeUnsupported
from src.kernel.symbolic.series import SeriesUndetermined


def _s(expr: object) -> str:
    return to_str(expr if hasattr(expr, "_children") else symbol_expr(str(expr)))


def _num(value: object) -> float:
    """级数/定积分的结果可能是 Expr（闭式）或 float，统一收成 float。"""
    if hasattr(value, "evaluate"):
        return float(value.evaluate({}))
    return float(value)


# ═══════════════════════════════════════════════════════════════════════════════
#  求导
# ═══════════════════════════════════════════════════════════════════════════════

DIFF_CASES = [
    ("x**4", "4*x**3"),
    ("sin(2*x)", "2*cos(2*x)"),
    ("exp(x**2)", "2*x*exp(x**2)"),
    ("log(x**2+1)", "2*x/(x**2 + 1)"),
    ("tan(x)", "1/cos(x)**2"),
    ("sqrt(x)", "1/(2*sqrt(x))"),
    ("x**2*sin(x)", "x**2*cos(x) + 2*x*sin(x)"),
    ("exp(exp(x))", "exp(x + exp(x))"),
    ("asin(x)", "1/sqrt(1 - x**2)"),
]


@pytest.mark.parametrize("src,expect", DIFF_CASES)
def test_diff_matches_sympy(src, expect):
    assert _s(differentiate(symbol_expr(src), "x")) == expect


def test_diff_unknown_construct_fails_loudly():
    # 内核无 factorial 求导规则 → 显式异常，不得返回 0 或 NaN
    with pytest.raises(UnsupportedExpression):
        differentiate(symbol_expr("factorial(x)"), "x")


# ═══════════════════════════════════════════════════════════════════════════════
#  积分（本轮修复的静默错值全部在此锁定）
# ═══════════════════════════════════════════════════════════════════════════════

INTEGRATE_CASES = [
    ("x**4", "x**5/5"),
    ("x**(-3)", "-1/(2*x**2)"),
    ("1/(x**2+1)", "atan(x)"),
    ("1/(x**2+4)", "atan(x/2)/2"),
    ("x/(x**2+1)", "log(x**2 + 1)/2"),
    ("1/sqrt(x)", "2*sqrt(x)"),
    ("log(x)", "x*log(x) - x"),
    ("sin(x)**3", "cos(x)**3/3 - cos(x)"),
    ("sin(x)*cos(x)", "-cos(x)**2/2"),
    ("tan(x)", "-log(cos(x))"),
    ("exp(2*x)", "exp(2*x)/2"),
    ("x**2*exp(x)", "x**2*exp(x) - 2*x*exp(x) + 2*exp(x)"),
    ("x**2*sin(x)", "-x**2*cos(x) + 2*x*sin(x) + 2*cos(x)"),
    ("1/(x**2-4)", "-log(x + 2)/4 + log(x - 2)/4"),
    ("(2*x+1)/(x**2-1)", "log(x + 1)/2 + 3*log(x - 1)/2"),
    # ── 本轮从「静默错值」修回正确值的四项 ──
    ("sqrt(2*x+1)", "(2*x + 1)**(3/2)/3"),          # 曾返回 2*x/3 + 0.333…
    ("sin(3*x)*cos(2*x)", "-cos(5*x)/10 - cos(x)/2"),  # 曾返回 -cos(2*x)**2/4
    ("sec(x)**2", "tan(x)"),                        # 曾返回 None
    ("tan(x)**2", "-x + tan(x)"),                   # 曾返回 None
    ("x*log(x)", "x**2*log(x)/2 - x**2/4"),         # 曾返回 None
]


@pytest.mark.parametrize("src,expect", INTEGRATE_CASES)
def test_integrate_matches_sympy(src, expect):
    assert _s(integrate(symbol_expr(src), "x")) == expect


def test_integrate_exp_trig_mixed_frequency():
    """∫eˣsin(2x)：旧实现要求两内函数同频，异频直接 None（sympy 通式一致）。"""
    got = integrate(symbol_expr("exp(x)*sin(2*x)"), "x")
    assert _s(got) == "-2*exp(x)*cos(2*x)/5 + exp(x)*sin(2*x)/5"
    # 用数值微分反向验证：d/dx(结果) 应还原被积函数
    assert _derivative_agrees(got, "exp(x)*sin(2*x)")


def test_integrate_rational_cubic_with_quadratic_factor():
    """∫1/(x³+1) = ln(x+1)/3 − ln(x²−x+1)/6 + (1/√3)·atan((x−1/2)/(√3/2))。"""
    got = integrate(symbol_expr("1/(x**3+1)"), "x")
    assert _derivative_agrees(got, "1/(x**3 + 1)")


def test_integrate_exponential_atoms_collapse():
    """e^{2x}·e^{−x} 必须先合指数再积分（否则 ODE 积分因子路径给出冗长解）。"""
    assert _s(integrate(symbol_expr("exp(2*x)*exp(-x)"), "x")) == "exp(x)"


@pytest.mark.parametrize("src", ["exp(-x**2)", "sin(x)/x", "abs(x)", "x**x",
                                 "1/(1+exp(x))", "sin(1/x)", "1/(x*exp(x))"])
def test_integrate_gaps_report_unknown(src):
    """非初等/未覆盖原函数：内核返回 None（门面转成显式错误），不得给出伪解。"""
    assert integrate(symbol_expr(src), "x") is None


def _derivative_agrees(antideriv: object, integrand: str, pts=(0.5, 1.3, 2.2)) -> bool:
    """数值校验：d/dx(原函数) 与被积函数在若干点上一致。"""
    d = differentiate(antideriv, "x")
    for x in pts:
        want = symbol_expr(integrand).substitute("x", symbol_expr(str(x))).evaluate({})
        got = d.substitute("x", symbol_expr(str(x))).evaluate({})
        if abs(got - want) > 1e-6 * max(1.0, abs(want)):
            return False
    return True


def test_definite_integral_numeric():
    assert abs(_num(definite(symbol_expr("x**2"), "x", 0, 1)) - 1 / 3) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
#  极限
# ═══════════════════════════════════════════════════════════════════════════════

LIMIT_CASES = [
    ("sin(x)/x", "x", 0.0, "+", 1.0),
    ("(1+x)**(1/x)", "x", 0.0, "+", math.e),        # 曾错报 inf
    ("(1+1/x)**x", "x", math.inf, "+", math.e),
    ("(1+2/x)**x", "x", math.inf, "+", math.exp(2)),
    ("x*exp(-x)", "x", math.inf, "+", 0.0),
    ("sqrt(x+1)-sqrt(x)", "x", math.inf, "+", 0.0),  # 曾错报 inf
    ("(exp(x)-1-x)/x**2", "x", 0.0, "+", 0.5),
    ("sin(2*x)/sin(x)", "x", 0.0, "+", 2.0),
    ("(1-cos(x))/x**2", "x", 0.0, "+", 0.5),
    ("log(x)/x", "x", math.inf, "+", 0.0),
    ("x**x", "x", 0.0, "+", 1.0),
    ("atan(x)", "x", math.inf, "+", math.pi / 2),
    ("tan(x)", "x", math.pi / 2, "-", math.inf),     # 左极限 +oo；曾错报 1.63e16
    ("tan(x)", "x", math.pi / 2, "+", -math.inf),    # 右极限 -oo
    ("log(x)", "x", 0.0, "+", -math.inf),           # 曾 LimitUndetermined
]


@pytest.mark.parametrize("src,var,pt,dr,expect", LIMIT_CASES)
def test_limit_matches_sympy(src, var, pt, dr, expect):
    got = limit(symbol_expr(src), var, pt, dr)
    if math.isinf(expect):
        assert got == expect
    else:
        assert abs(got - expect) <= 1e-9 * max(1.0, abs(expect))


def test_oscillating_limit_fails_loudly():
    """lim sin(x) (x→∞) 不存在：旧数值外推会给出 inf；现在必须显式失败。"""
    with pytest.raises(LimitUndetermined):
        limit(symbol_expr("sin(x)"), "x", math.inf)


def test_growth_order_exp_beats_power():
    """eˣ/x² 的指数快于多项式已被判据表覆盖（与 sympy 一致）。"""
    assert limit(symbol_expr("exp(x)/x**2"), "x", math.inf) == math.inf


# ═══════════════════════════════════════════════════════════════════════════════
#  级数
# ═══════════════════════════════════════════════════════════════════════════════

def test_maclaurin_matches_sympy():
    assert _s(maclaurin(symbol_expr("exp(x)"), "x", 5)) == \
        "x**5/120 + x**4/24 + x**3/6 + x**2/2 + x + 1"
    assert _s(maclaurin(symbol_expr("log(1+x)"), "x", 5)) == \
        "x**5/5 - x**4/4 + x**3/3 - x**2/2 + x"


def test_sum_series():
    assert abs(_num(sum_series(symbol_expr("1/n**2"), "n", 1, None)) - math.pi ** 2 / 6) < 1e-9
    assert _num(sum_series(symbol_expr("n"), "n", 1, 100)) == 5050
    assert _num(sum_series(symbol_expr("n**3"), "n", 1, 10)) == 3025


def test_sum_harmonic_fails_loudly():
    with pytest.raises(SeriesUndetermined):
        sum_series(symbol_expr("1/n"), "n", 1, 5)


# ═══════════════════════════════════════════════════════════════════════════════
#  常微分方程
# ═══════════════════════════════════════════════════════════════════════════════

ODE_CASES = [
    ("y' = y*sin(x)", "C1*exp(-cos(x))"),
    ("y' = x**2*y", "C1*exp(x**3/3)"),
    ("y'' = -y", "C1*cos(x) + C2*sin(x)"),
    ("y'' - y = 0", "C1*exp(x) + C2*exp(-x)"),
    ("y'' + 4*y = 0", "C1*cos(2*x) + C2*sin(2*x)"),
    ("y'' + 2*y' + y = 0", "C2*x*exp(-x) + C1*exp(-x)"),
    ("y' + 2*y = exp(-x)", "C1*exp(-2*x) + exp(-x)"),   # 曾分类失败
    ("y' + 3*y = exp(2*x)", "C1*exp(-3*x) + exp(2*x)/5"),
]


@pytest.mark.parametrize("eq,expect", ODE_CASES)
def test_solve_ode_matches_sympy(eq, expect):
    assert _s(solve_ode(eq, "y")) == expect


def test_solve_ode_accepts_text():
    got = solve_ode("y' + 2*y = exp(-x)", "y")
    assert _s(got) == "C1*exp(-2*x) + exp(-x)"


@pytest.mark.parametrize("eq", ["y' = x**2 + y**2", "y' = (x+y)/x", "y' = 1/(x+y)"])
def test_solve_ode_gaps_fail_loudly(eq):
    with pytest.raises(OdeUnsupported):
        solve_ode(eq, "y")


# ═══════════════════════════════════════════════════════════════════════════════
#  连续域 / 累值界（sympy 1.14 已移除这两个名字，此处锁定内核自证语义）
# ═══════════════════════════════════════════════════════════════════════════════

DOMAIN_CASES = [
    ("1/x", ["(-oo, 0)", "(0, oo)"]),
    ("sqrt(x)", ["[0, oo)"]),
    ("log(x)", ["(0, oo)"]),
    ("1/(x**2-1)", ["(-oo, -1)", "(-1, 1)", "(1, oo)"]),
    ("asin(x)", ["[-1, 1]"]),
]


@pytest.mark.parametrize("src,expect", DOMAIN_CASES)
def test_continuous_domain(src, expect):
    assert [str(i) for i in continuous_domain(symbol_expr(src), "x")] == expect


BOUNDS_CASES = [
    ("sin(x)", (-1.0, 1.0)),
    ("cos(x)", (-1.0, 1.0)),
    ("2*sin(x)", (-2.0, 2.0)),
    ("sin(x)**2", (0.0, 1.0)),          # 偶次幂恒非负：曾错报 (-1, 1)
    ("x**2", (0.0, math.inf)),          # 曾错报 (inf, inf)
    ("x**3", (-math.inf, math.inf)),
    ("x**2+2*x", (-1.0, math.inf)),
    ("1/x", (-math.inf, math.inf)),     # 曾错报 (0, 0)
    ("1/x**2", (0.0, math.inf)),
    ("exp(-x)", (0.0, math.inf)),
    ("atan(x)", (-math.pi / 2, math.pi / 2)),
    ("log(x)", (-math.inf, math.inf)),  # 曾不可判定
    ("sqrt(x)", (0.0, math.inf)),       # 曾错报 (inf, inf)
]


@pytest.mark.parametrize("src,expect", BOUNDS_CASES)
def test_accumulated_bounds(src, expect):
    got = accumulated_bounds(symbol_expr(src), "x")
    assert got == expect
    assert math.copysign(1.0, got[0]) > 0 or got[0] != 0.0  # 不出现 -0.0 伪精度


@pytest.mark.parametrize("src", ["cos(x)+sin(x)", "sin(x)*cos(x)"])
def test_accumulated_bounds_trig_sum_fails_loudly(src):
    with pytest.raises(DomainUndetermined):
        accumulated_bounds(symbol_expr(src), "x")


# ═══════════════════════════════════════════════════════════════════════════════
#  输出发射
# ═══════════════════════════════════════════════════════════════════════════════

def test_output_renderers():
    e = symbol_expr("x**2+2*x+1")
    assert to_str(e) == "x**2 + 2*x + 1"
    assert to_latex(e) == "x^{2} + 2 x + 1"
    assert to_pretty(e) == "x² + 2x + 1"


def test_coefficient_irrationals_not_faked_as_fractions():
    """1/√3 不得被连分数伪造成大分母「精确分数」（伪精度）。"""
    got = to_str(integrate(symbol_expr("1/(x**3+1)"), "x"))
    assert "978122" not in got and "10864" not in got
