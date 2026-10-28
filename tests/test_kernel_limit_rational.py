# -*- coding: utf-8 -*-
"""B 组：∞ 处有理函数极限的精确主部比较（对标 SymPy，含 0 / ±∞ 边界）。

历史缺口（docs/KNOWN_ISSUES.md 第三节「stage0 已知不准」）：
  - `(2x+1)/(3x-1)` 在 x→±∞ 用 t=1/x 数值归约读数，末位错
    （得 0.6666666666722222，应为逐位精确的 2/3）；
  - `x**2/(3x-1)` 在 x→-∞ 主部落在 +∞ 而非 -∞（en>ed 分支未做负无穷奇次变号，
    与同文件 poly_in 分支不一致）。

SymPy 口径：有理函数 P/Q 在 ±∞ 的极限由首项比精确决定——
  deg(P)<deg(Q) → 0；deg(P)==deg(Q) → cn/cd（精确有理比）；
  deg(P)>deg(Q) → ±∞，其号由 (cn/cd) 与 (deg(P)-deg(Q)) 在 -∞ 的奇偶共同决定。
本文件用逐位相等（==）锁定，杜绝「1e-9 容差恰好放过末位错」。
"""
from __future__ import annotations

import math

import pytest

from src.kernel.symbolic.expr import symbol_expr
from src.kernel.symbolic.limit import limit


# (表达式, 趋近点, 期望值) —— 期望均为 SymPy 1.14 口径，且可用位精确 float 表达
RATIONAL_AT_INFINITY = [
    ("(2*x+1)/(3*x-1)", math.inf, 2 / 3),
    ("(2*x+1)/(3*x-1)", -math.inf, 2 / 3),
    ("(3*x**2-x+1)/(x**2+5)", math.inf, 3.0),
    ("(3*x**2-x+1)/(x**2+5)", -math.inf, 3.0),
    ("(1-2*x)/(4*x+7)", math.inf, -0.5),
    ("(x+1)/(x**2-1)", math.inf, 0.0),          # deg(num)<deg(den) → 0
    ("(x+1)/(x**2-1)", -math.inf, 0.0),
    # deg(num)>deg(den)：±∞，符号随次差奇偶（负无穷处）
    ("x**2/(3*x-1)", math.inf, math.inf),
    ("x**2/(3*x-1)", -math.inf, -math.inf),     # 次差=1（奇）→ 负无穷翻号
    ("(x**3+1)/(x-1)", math.inf, math.inf),
    ("(x**3+1)/(x-1)", -math.inf, math.inf),    # 次差=2（偶）→ 负无穷不翻号，~x² → +∞
    ("(-x**2+1)/(3*x-1)", math.inf, -math.inf),
]


@pytest.mark.parametrize("src,pt,expect", RATIONAL_AT_INFINITY)
def test_rational_limit_at_infinity_is_exact(src, pt, expect):
    got = limit(symbol_expr(src), "x", pt)
    if math.isinf(expect):
        assert got == expect, f"{src} @ {pt}: got {got!r}, want {expect!r}"
    else:
        # 位精确：同次首项比 cn/cd 必须是最近 double，而非数值读数
        assert got == expect, f"{src} @ {pt}: got {got!r}, want exactly {expect!r}"


def test_rational_limit_matches_between_plus_and_minus_infinity_when_even():
    # 同次的有理函数在 +∞ 与 -∞ 结果相同（如 2/3），末位也须一致
    f = symbol_expr("(2*x+1)/(3*x-1)")
    assert limit(f, "x", math.inf) == limit(f, "x", -math.inf)


# ---- 边界：有限点直接代入（不得被 ∞ 分支改动波及） ----

def test_rational_limit_finite_point_direct_substitution():
    assert limit(symbol_expr("(2*x+1)/(3*x-1)"), "x", 0.0) == -1.0
    assert limit(symbol_expr("(2*x+1)/(3*x-1)"), "x", 1.0) == 1.5


def test_rational_pole_boundary_returns_signed_infinity():
    # x→(1/3)+ 分母趋 0+，分子约 1.667 → +∞；x→(1/3)- → -∞（符号须相反）
    pos = limit(symbol_expr("(2*x+1)/(3*x-1)"), "x", 1 / 3, "+")
    neg = limit(symbol_expr("(2*x+1)/(3*x-1)"), "x", 1 / 3, "-")
    assert pos == math.inf and neg == -math.inf
