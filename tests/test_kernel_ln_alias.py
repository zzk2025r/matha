# -*- coding: utf-8 -*-
"""B 组：`ln` 作为自然对数别名应处处可用（对标 SymPy）。

历史缺口（docs/KNOWN_ISSUES.md 第三节「stage0 已知不准」）：
  `evaluate` 不认识 `ln`。符号解析器的 FUNC_NAMES/FUNC_PATTERN **已**登记 `ln`，
  但 FuncCall.evaluate / diff 只处理 `log`，导致 `ln(x)` 求值/求导抛
  「未知函数: ln」。`ln` 与 `log` 在 Matha 内核同指自然对数（log 以 e 为底）。
"""
from __future__ import annotations

import math

from src.kernel.symbolic.expr import symbol_expr
from src.kernel.symbolic.diff import differentiate
from src.kernel.symbolic.limit import limit


def test_ln_evaluate_basic():
    assert symbol_expr("ln(x)").evaluate({"x": math.e}) == 1.0
    assert abs(symbol_expr("ln(100)").evaluate({}) - math.log(100)) < 1e-12
    assert abs(symbol_expr("ln(1)").evaluate({}) - 0.0) < 1e-12


def test_ln_equals_log_semantics():
    # ln 与 log 同底（自然对数），边界值一致
    for v in (0.5, 1.0, 2.0, math.e, 10.0):
        assert abs(symbol_expr("ln(x)").evaluate({"x": v})
                   - symbol_expr("log(x)").evaluate({"x": v})) < 1e-12


def test_ln_boundary_and_infinity():
    # ln(x) 在 x→0+ 为 -∞；x→+∞ 为 +∞（0 / ∞ 边界）
    assert limit(symbol_expr("ln(x)"), "x", 0.0, "+") == -math.inf
    assert limit(symbol_expr("ln(x)"), "x", math.inf) == math.inf
    # ln(x)/x 在 +∞ → 0（log 慢于任意正幂）
    assert limit(symbol_expr("ln(x)/x"), "x", math.inf) == 0.0


def test_ln_derivative_matches_log():
    d = differentiate(symbol_expr("ln(x)"), "x")
    for v in (0.7, 1.0, 2.5, 8.0):
        assert abs(d.evaluate({"x": v}) - 1.0 / v) < 1e-9
