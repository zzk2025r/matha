# -*- coding: utf-8 -*-
"""B 组：任意点泰勒展开输出 (x-a)^n 中心形式（对标 SymPy，含 0 / 中心点边界）。

历史缺口（docs/symbolic_parity.md 第 5 节 / KNOWN_ISSUES 第三节）：
  内核 `series.taylor` 虽按 `Σ fⁿ(a)/n!·(x-a)ⁿ` 求系数，但最后套了 `canonical`
  把 (x-a)^n 乘开成 x 幂——`1/x` 在 a=2 展开竟显示 `-x**3/16 + x**2/2 - 3*x/2 + 2`，
  完全丢失「在 a=2 处展开」的结构，也与 sympy `series(1/x, x, 2)` 的
  `1/2 - (x-2)/4 + (x-2)^2/8 - (x-2)^3/16` 不同形。

修复：taylor 对非零点保留 (x-a)^n 中心链（不做 canonical 乘开）；渲染层新增
`expand` 开关（默认 True 不影响任何既有输出），门面对非零点以 expand=False 发射。
point=0 的麦克劳林路径完全不变（既有逐字锁定串不动）。
"""
from __future__ import annotations

import math

from src.kernel.symbolic import to_str
from src.kernel.symbolic.expr import Num, symbol_expr
from src.kernel.symbolic.series import maclaurin, taylor
from src.stdlib import calculus_symbolic as cs


def test_taylor_nonzero_point_exact_centered_string():
    # 有理系数干净的样例：逐字锁定 (x-a)^n 中心形式（对标 sympy）
    got = cs.taylor_series("1/x", "x", 2.0, 3, backend="stage0")
    assert got == "0.5 - (x - 2)/4 + (x - 2)**2/8 - (x - 2)**3/16", repr(got)


def test_taylor_nonzero_point_structure_is_centered_not_expanded():
    # 一般函数：输出须含 (x - a) 因子，且不得出现被乘开的裸 x**2 / x**3
    for expr, a in [("exp(x)", 2.0), ("sin(x)", 1.0), ("cos(x)", 1.0)]:
        s = cs.taylor_series(expr, "x", a, 4, backend="stage0")
        assert f"(x - {int(a)})" in s, (expr, s)
        assert "x**2" not in s and "x**3" not in s, f"{expr}@{a} 被乘开了: {s}"


def test_taylor_nonzero_point_reduces_to_f_at_center():
    # 边界：在展开点 a 本身，(x-a) 归零 → 多项式值 = f(a)（0 阶项）
    for expr, a in [("exp(x)", 2.0), ("1/x", 2.0), ("sin(x)", 1.0)]:
        poly = taylor(symbol_expr(expr), "x", a, 6)
        val = float(poly.substitute("x", Num(a)).evaluate({}))
        truth = float(symbol_expr(expr).substitute("x", Num(a)).evaluate({}))
        assert abs(val - truth) < 1e-9, (expr, val, truth)


def test_taylor_nonzero_point_numerically_invariant_near_center():
    # 中心形式与真函数在 a 邻域一致（数值正确性不因改写输出形式而退化）
    for expr, a, h in [("exp(x)", 2.0, 0.1), ("sin(x)", 1.0, 0.2), ("1/x", 2.0, 0.1)]:
        poly = taylor(symbol_expr(expr), "x", a, 8)
        val = float(poly.substitute("x", Num(a + h)).evaluate({}))
        truth = float(symbol_expr(expr).substitute("x", Num(a + h)).evaluate({}))
        assert abs(val - truth) < 1e-4, (expr, a, val, truth)


def test_maclaurin_point_zero_form_unchanged():
    # point=0 麦克劳林路径完全不变（既有逐字锁定）
    assert to_str(maclaurin(symbol_expr("exp(x)"), "x", 5)) == \
        "x**5/120 + x**4/24 + x**3/6 + x**2/2 + x + 1"
    # taylor 在 0 点 == maclaurin
    assert to_str(taylor(symbol_expr("exp(x)"), "x", 0.0, 5)) == \
        to_str(maclaurin(symbol_expr("exp(x)"), "x", 5))


def test_taylor_expand_false_preserves_centered_ast():
    # 渲染层 expand=False 跳过 canonical，直接发射 (x-a)^n 中心树
    expr = taylor(symbol_expr("1/x"), "x", 2.0, 3)
    assert to_str(expr, expand=False) == \
        "0.5 - (x - 2)/4 + (x - 2)**2/8 - (x - 2)**3/16"
