# -*- coding: utf-8 -*-
"""阶段 4 门禁：Matha 标准库（`.matha` + mbc VM）与 stage0 引导实现对拍。

计划原文：「每迁一模块，VM 输出与 Python 引导实现逐位对拍通过才切默认」，
且「缺口项如实列出，禁止静默降级为假成功」。本文件把这两条落成可机器判定：

  1. **逐位（bit-for-bit）相等**：求导 / 高阶导 / 化简 / 极限 / 级数 的公开文本，
     `backend="matha"` 与 `backend="stage0"` 两侧必须一字不差；
  2. **偏差表双向锁定**：已知偏差逐条记录两侧的确切文本，
     任何一侧变化（含「偏差自己消失了」）都会失败，防止口径漂移；
  3. **未覆盖必须显式**：库判定不覆盖的输入，强制 `backend="matha"` 时
     必须抛 `不支持: …`；默认 `auto` 时必须能在 `BACKEND_STATS` 里看到回退计数；
  4. **默认路径确实是 Matha**：默认调用只增加 `matha` 计数，不增加 `stage0`，
     且执行体是 `src.mbc.vm.VM`（不是 Python 侧的符号引擎）。

数值一律用**精确相等**（`==`），不引入任何容差 —— 两侧都是同一条 IEEE-754
序列上的运算，出现尾差就说明结构不同，属于要被抓出来的事。
"""
from __future__ import annotations

import math

import pytest

from src.kernel.symbolic import symbol_expr
from src.stdlib import calculus_symbolic as cs
from src.stdlib import matha_symbolic as ms

# ═══════════════════════════════════════════════════════════════════════════
#  一、装载：标准库由核心主线编译执行
# ═══════════════════════════════════════════════════════════════════════════

LIB_ENTRIES = ("规范", "规范文本", "导数文本", "n阶导", "化简", "展开",
               "极限节点", "极限文本", "系数对", "泰勒系数对")


def test_library_files_exist_in_dependency_order():
    assert ms.LIB_FILES == ("calculus_diff.matha", "algebra_simplify.matha",
                            "calculus_limit.matha", "calculus_series.matha")
    for p in ms.LIB_PATHS:
        assert p.is_file(), f"缺少标准库文件 {p}"
        assert ms.LIB_DIR in p.parents


def test_vm_backends_are_the_mbc_line():
    """执行体必须是 `mbc.compiler → mbc.vm`，不是 Python 侧符号引擎。"""
    from src.mbc.vm import VM
    vm = ms.vm()
    assert isinstance(vm, VM)
    for name in LIB_ENTRIES:
        assert name in vm.globals, f"标准库未提供 {name}"


def test_conversion_roundtrip_is_lossless():
    for text in ("x**3", "sin(x)", "exp(x)*cos(x)", "ln(x)", "1/x", "(x+1)**3"):
        e = symbol_expr(text)
        back = ms.from_tagged(ms.to_tagged(e))
        assert repr(back) == repr(ms.from_tagged(ms.to_tagged(back)))


# ═══════════════════════════════════════════════════════════════════════════
#  二、逐位对拍：两侧文本一字不差
# ═══════════════════════════════════════════════════════════════════════════

DERIV_PARITY = [
    "x**3", "x**2 + 3*x + 1", "sin(x)", "cos(x)", "exp(x)", "ln(x)", "1/x",
    "x*sin(x)", "x**2*sin(x)", "sin(x)*cos(x)", "exp(x)*cos(x)", "tan(x)",
    "(x+1)**3", "x**4 - 2*x**2 + 1", "exp(3*x)", "ln(1+x)", "sqrt(x)",
    "1/(1-x)", "sin(x)/x", "x**2/(x-1)", "atan(x)", "sinh(x)", "cosh(x)",
    "tanh(x)", "x**3 + x**3", "2*x + 3*x", "x*x",
    "x**2/x", "(2*x**2)/(4*x)", "(x+1)*(x+2)", "x**5", "1/(x+1)",
    "(x**2 + 1)*sin(x)", "exp(-x)", "ln(x**2)", "sqrt(1 + x)",
]

NTH_PARITY = [("sin(x)", 2), ("sin(x)", 4), ("cos(x)", 3), ("exp(x)", 4),
              ("x**5", 2), ("x**4", 3), ("x*exp(x)", 2), ("ln(x)", 3)]

SIMPLIFY_PARITY = ["x + x", "x*x", "2*x + 3*x", "x**2*x**3", "(x+1)**2",
                   "(x+1)*(x+2)", "x**3 + 2*x**2 + 3*x + 4 - 4",
                   "sin(x) + sin(x)", "3*x - 3*x", "-(x)", "x**2/x",
                   "(2*x**2)/(4*x)", "x**2 + x**2 + x**2", "(x-1)*(x+1)"]

LIMIT_PARITY = [
    ("1/x", "x", 0, "+"), ("1/x", "x", 0, "-"), ("1/x**2", "x", 0, "+"),
    ("(x**2-1)/(x-1)", "x", 1, "+"), ("x**2/(x-1)", "x", 1, "+"),
    ("1/(x**2+1)", "x", 0, "+"), ("x**3 - 2*x", "x", 2, "+"),
    ("(x**2-4)/(x-2)", "x", 2, "+"), ("(1-x**3)/(1-x)", "x", 1, "+"),
    ("(3*x**2 + 2*x)/(x**2 - 5)", "x", 0, "+"),
    ("x**2 - 1", "x", float("-inf"), "+"), ("(x+1)/(x-1)", "x", 3, "-"),
]

SERIES_PARITY = ["sin(x)", "cos(x)", "exp(x)", "1/(1-x)", "x**2+3*x+1",
                 "tan(x)", "x**3", "x**5", "(1+x)**3"]


@pytest.mark.parametrize("expr", DERIV_PARITY)
def test_derivative_bit_for_bit(expr):
    a = cs.symbolic_derivative(expr, "x", backend="stage0")
    b = cs.symbolic_derivative(expr, "x", backend="matha")
    assert a == b, f"求导两侧文本不同: {expr}: stage0={a!r} matha={b!r}"


@pytest.mark.parametrize("expr,n", NTH_PARITY)
def test_nth_derivative_bit_for_bit(expr, n):
    a = cs.nth_derivative(expr, "x", n, backend="stage0")
    b = cs.nth_derivative(expr, "x", n, backend="matha")
    assert a == b, f"{n} 阶导两侧不同: {expr}: stage0={a!r} matha={b!r}"


@pytest.mark.parametrize("expr", SIMPLIFY_PARITY)
def test_simplify_bit_for_bit(expr):
    a = cs.simplify_format(expr, backend="stage0")
    b = cs.simplify_format(expr, backend="matha")
    assert a == b, f"化简两侧文本不同: {expr}: stage0={a!r} matha={b!r}"


@pytest.mark.parametrize("expr,var,point,direction", LIMIT_PARITY)
def test_limit_bit_for_bit(expr, var, point, direction):
    a = cs.limit(expr, var, point, direction, backend="stage0")
    b = cs.limit(expr, var, point, direction, backend="matha")
    assert a == b, f"极限两侧不同: {expr}: stage0={a!r} matha={b!r}"


@pytest.mark.parametrize("expr", SERIES_PARITY)
def test_series_bit_for_bit(expr):
    a = cs.taylor_series(expr, "x", 0, 5, backend="stage0")
    b = cs.taylor_series(expr, "x", 0, 5, backend="matha")
    assert a == b, f"级数两侧文本不同: {expr}: stage0={a!r} matha={b!r}"


@pytest.mark.parametrize("expr", SERIES_PARITY)
def test_series_coefficients_are_exactly_equal(expr):
    """系数表逐位对拍：`(次数, 系数)` 两侧完全相同（无容差）。

    Python 侧自己走 stage0 的导数与求值（与标准库的 VM 求值是两个实现），
    只在 `|c| < 1e-15` 丢弃与 `float/factorial` 两步上保持同规格。
    """
    from src.kernel.symbolic import canonical
    from src.kernel.symbolic.diff import nth_derivative
    e = symbol_expr(expr)
    stage0 = []
    for n in range(6):
        f = canonical(nth_derivative(e, "x", n))
        val = float(f.substitute("x", _numf(0.0)).evaluate({}))
        coef = val / math.factorial(n)
        if abs(coef) < 1e-15:
            continue
        stage0.append((n, coef))
    assert ms.maclaurin_terms(e, "x", 5) == stage0, expr


# ═══════════════════════════════════════════════════════════════════════════
#  三、已知偏差：双向锁定文本 + 数值一致性（不是「差不多就行」）
# ═══════════════════════════════════════════════════════════════════════════

#: 规范形书写差异：库内 add 一律按键升序、常数最后，负号提到整体之前，
#: `x*x` 合成 `x**2`；stage0 保留求导规则手写的 `Sub(1, x**2)` 与展开形态。
#: 两侧文本不同，但把文本回读成表达式后逐点求值必须**完全相等**（`==`）。
#: 表达式 → (stage0 文本, matha 文本, 采样点)
DEVIATION_DERIV = {
    "asin(x)": ("1/sqrt(1 - x**2)", "1/sqrt(-x**2 + 1)",
                (0.5, 0.25, 0.125, 0.9375, 0.75, -0.5)),
    "acos(x)": ("-1/sqrt(1 - x**2)", "-1/sqrt(-x**2 + 1)",
                (0.5, 0.25, 0.125, 0.9375, 0.75, -0.5)),
    "asin(x)*atan(x)": ("atan(x)/sqrt(1 - x**2) + asin(x)/(x**2 + 1)",
                        "asin(x)/(x**2 + 1) + atan(x)/sqrt(-x**2 + 1)",
                        (0.5, 0.25, 0.125, 0.9375, 0.75, -0.5)),
    "1/(x**2 + 2*x + 1)": (
        "(-2*x - 2)/(x**4 + 4*x**3 + 6*x**2 + 4*x + 1)",
        "-(2*x + 2)/(x**4 + 4*x**3 + 6*x**2 + 4*x + 1)",
        (0.5, 0.25, 0.125, 0.9375, 0.75, 2.0, -0.5, 1.0, 3.0)),
    "exp(-x*x)": ("-2*x*exp(-x*x)", "-2*x*exp(-x**2)",
                  (0.5, 0.25, 0.125, 0.9375, 0.75, 2.0, -0.5, 1.0, 3.0)),
}

#: 标准库会合并同类分式，stage0 的化简不会 —— 记录为「库强于引导实现」，
#: 而不是「库和引导实现不一样所以谁都对」。两侧数值必须逐位相同。
DEVIATION_SIMPLIFY = {
    "1/(x+1) + 1/(x+1)": ("1/(x + 1) + 1/(x + 1)", "2/(x + 1)"),
}

#: 【B 组已修】stage0 之前在 ±∞ 用 t=1/x 数值采样逼近，末位就不对；现内核
#: `_limit_infinity` 已把「有理式精确主部比」提到数值归约之前（对标 sympy 主导项法），
#: stage0 与库两侧逐位一致。下表转为**平价锁**：(表达式, 侧) → 精确值，
#: 断言 stage0 == matha == 精确值；若某天 stage0 又偏离，本用例即失败。
#: （历史 stage0 旧值：2/3→0.6666666666722222、(x+1)/(x**2+1)→1.00000000001e-11）
PARITY_LIMIT = {
    ("(2*x+1)/(3*x-1)", "+"): 2.0 / 3.0,
    ("(x+1)/(x**2+1)", "+"): 0.0,
}

#: 【B 组已修】stage0 的 `evaluate` 曾不认识 ln（无对应内建），泰勒展开直接抛
#: SeriesUndetermined；现符号解析器把 `ln` 归一为自然对数 `log`，stage0 与库两侧
#: 结果一致。下表转为**平价锁**：表达式 → 期望级数文本。
PARITY_SERIES = {
    "ln(1+x)": "x**5/5 - x**4/4 + x**3/3 - x**2/2 + x",
}


def test_derivative_deviation_text_is_locked():
    for expr, (want0, want1, _pts) in DEVIATION_DERIV.items():
        a = cs.symbolic_derivative(expr, "x", backend="stage0")
        b = cs.symbolic_derivative(expr, "x", backend="matha")
        assert (a, b) == (want0, want1), (expr, a, b, want0, want1)
        assert a != b, f"偏差表已过时：{expr} 两侧现在一致，请删除该条"


@pytest.mark.parametrize("expr", sorted(DEVIATION_DERIV))
def test_derivative_deviation_is_numerically_identical(expr):
    """文本不同但值必须**逐位相同**：把两侧打印文本回读成表达式再逐点求值。"""
    _w0, _w1, pts = DEVIATION_DERIV[expr]
    a = symbol_expr(cs.symbolic_derivative(expr, "x", backend="stage0"))
    b = symbol_expr(cs.symbolic_derivative(expr, "x", backend="matha"))
    for x in pts:
        va = a.substitute("x", _numf(x)).evaluate({})
        vb = b.substitute("x", _numf(x)).evaluate({})
        assert va == vb, (expr, x, repr(va), repr(vb))


def test_simplify_deviation_library_is_stronger():
    for expr, (want0, want1) in DEVIATION_SIMPLIFY.items():
        a = cs.simplify_format(expr, backend="stage0")
        b = cs.simplify_format(expr, backend="matha")
        assert (a, b) == (want0, want1), (expr, a, b, want0, want1)
        ta, tb = symbol_expr(a), symbol_expr(b)
        for x in (0.5, 0.25, 2.0, -0.5, 3.0):
            va = ta.substitute("x", _numf(x)).evaluate({})
            vb = tb.substitute("x", _numf(x)).evaluate({})
            assert va == vb, (expr, x, repr(va), repr(vb))


def _numf(v: float):
    from src.kernel.symbolic.expr import Num
    return Num(v)


def test_limit_stage0_now_matches_library_exact():
    # 【B 组已修】±∞ 有理式极限：stage0 现走精确主部比，与库两侧逐位一致。
    for (expr, direction), exact in PARITY_LIMIT.items():
        a = cs.limit(expr, "x", math.inf, direction, backend="stage0")
        b = cs.limit(expr, "x", math.inf, direction, backend="matha")
        assert a == exact, (expr, repr(a), exact)
        assert b == exact, (expr, repr(b), exact)
        assert a == b, (expr, repr(a), repr(b))


def test_series_ln_stage0_now_matches_library():
    # 【B 组已修】`ln` 归一为自然对数后，stage0 能算 ln(1+x) 的泰勒展开，与库一致。
    for expr, want in PARITY_SERIES.items():
        s0 = cs.taylor_series(expr, "x", 0, 5, backend="stage0")
        s1 = cs.taylor_series(expr, "x", 0, 5, backend="matha")
        assert s0 == want, (expr, s0, want)
        assert s1 == want, (expr, s1, want)


# ═══════════════════════════════════════════════════════════════════════════
#  四、未覆盖必须显式失败，回退必须留痕
# ═══════════════════════════════════════════════════════════════════════════

def test_limit_outside_scope_raises_matha_unsupported():
    e = symbol_expr("sin(x)/x")
    with pytest.raises(ms.MathaUnsupported, match="^不支持: "):
        ms.limit_value(e, "x", 0.0, "+")


def test_facade_forced_matha_errors_instead_of_falling_back():
    with pytest.raises(ValueError, match="不支持"):
        cs.limit("sin(x)/x", "x", 0, "+", backend="matha")


def test_auto_backend_fallback_is_counted_not_silent():
    cs.reset_backend_stats()
    got = cs.limit("sin(x)/x", "x", 0, "+")          # 默认 auto
    assert got == 1.0
    st = cs.backend_stats()
    assert st["fallback"] == 1 and st["stage0"] == 1 and st["matha"] == 0, st


def test_series_nonzero_point_is_declared_unsupported():
    """库口径：非 0 点显式 `不支持`，而不是偷偷按 0 点糊过去。"""
    with pytest.raises(RuntimeError, match="不支持: 级数库只覆盖 point=0"):
        ms.vm().call("泰勒系数对", ms.to_tagged(symbol_expr("sin(x)")), "x", 1.0, 3)


def test_auto_backend_nonzero_point_falls_back_with_count():
    cs.reset_backend_stats()
    got = cs.taylor_series("sin(x)", "x", 1, 3)
    assert isinstance(got, str) and got
    st = cs.backend_stats()
    assert st["fallback"] == 1 and st["stage0"] == 1, st


# ═══════════════════════════════════════════════════════════════════════════
#  五、默认路径就是 Matha 标准库
# ═══════════════════════════════════════════════════════════════════════════

def test_default_backend_is_the_matha_library():
    cs.reset_backend_stats()
    for expr in DERIV_PARITY:
        cs.symbolic_derivative(expr, "x")
    for expr in SIMPLIFY_PARITY:
        cs.simplify_format(expr)
    for expr, var, p, d in LIMIT_PARITY:
        cs.limit(expr, var, p, d)
    for expr in SERIES_PARITY:
        cs.taylor_series(expr, "x", 0, 5)
    st = cs.backend_stats()
    assert st["stage0"] == 0 and st["fallback"] == 0, st
    assert st["matha"] == (len(DERIV_PARITY) + len(SIMPLIFY_PARITY)
                           + len(LIMIT_PARITY) + len(SERIES_PARITY)), st


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="backend"):
        cs.symbolic_derivative("x**2", "x", backend="numpy")
