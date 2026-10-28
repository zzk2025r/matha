# -*- coding: utf-8 -*-
"""B 组：分段代表函数 |ax+b| 的不定/定积分（对标 SymPy，含 0 折点边界）。

历史缺口（docs/symbolic_parity.md 第 3 节「缺口」表）：
  `abs(x)` → 内核无对应原函数规则 → `None`；跨折点的定积分只能退自适应 Simpson
  （数值近似，如 ∫_{-2}^{3}|x| = 6.499999999793039 而非精确 6.5）。

SymPy 口径：``integrate(Abs(x), x) = x*Abs(x)/2``；更一般地
  ``∫|a x + b| dx = (a x + b)·|a x + b| / (2a)``（a≠0）。
本文件用「求导回代 == 被积函数」「跨 0 折点定积分取精确值」「非初等内函数仍显式
失败」三条锁定，其中折点 0 与积分区间跨 0 是必须通过的边界。
"""
from __future__ import annotations

import math

import pytest

from src.kernel.symbolic.diff import differentiate
from src.kernel.symbolic.expr import Num, symbol_expr
from src.kernel.symbolic.integrate import definite, integrate
from src.stdlib import calculus_symbolic as cs


def test_indefinite_abs_x_is_not_none():
    # 修复前内核直接返回 None
    assert integrate(symbol_expr("abs(x)"), "x") is not None


def test_indefinite_abs_antiderivative_roundtrip():
    # d/dx F == |·| 在折点两侧若干点成立（0 边界左右都要验）
    for src, pts in [("abs(x)", (-2.5, -1.0, 0.7, 3.0)),
                     ("abs(2*x+1)", (-3.0, -0.2, 0.5, 2.0)),
                     ("abs(1-x)", (-1.0, 0.5, 2.5))]:
        F = integrate(symbol_expr(src), "x")
        assert F is not None, src
        d = differentiate(F, "x")
        for x in pts:
            if abs(x) < 1e-12:
                continue          # 折点处 |·| 不可导，跳过
            got = float(d.substitute("x", Num(x)).evaluate({}))
            want = abs(float(symbol_expr(src.replace("abs", "abs"))
                              .substitute("x", Num(x)).evaluate({})))
            assert abs(got - want) < 1e-9, (src, x, got, want)


def test_indefinite_abs_exact_string():
    # 干净形逐字锁定（对标 sympy x*Abs(x)/2）
    from src.kernel.symbolic import to_str
    assert to_str(integrate(symbol_expr("abs(x)"), "x")) == "x*abs(x)/2"
    # 线性移位：integrate 外层 canonical 会把 (2x+1)·|2x+1|/4 分配成
    # x*abs(2*x + 1)/2 + abs(2*x + 1)/4（代数等价，已由求导回代测试证明正确）；
    # 不强制因式形，只锁「含 abs(2*x + 1) 且与 sympy 原函数数值相等」。
    got = integrate(symbol_expr("abs(2*x+1)"), "x")
    s = to_str(got)
    assert "abs(2*x + 1)" in s, s
    for x in (-2.0, -0.3, 0.4, 1.7):
        v = float(got.substitute("x", Num(x)).evaluate({}))
        # 原函数允许相差常数：以差商（斜率）对齐，验证与 sympy 同导
        h = 1e-6
        dv = (float(got.substitute("x", Num(x + h)).evaluate({})) - v) / h
        assert abs(dv - (math.copysign(1, 2 * x + 1) * (2 * x + 1))) < 1e-3, (x, v, dv)


def test_definite_abs_across_zero_is_exact():
    # 跨折点 0 的定积分走 Newton–Leibniz 取精确值（不再是 Simpson 近似）
    assert definite(symbol_expr("abs(x)"), "x", -1.0, 1.0) == 1.0
    assert definite(symbol_expr("abs(x)"), "x", -2.0, 3.0) == 6.5
    # 单侧（不含折点）也正确
    assert definite(symbol_expr("abs(x)"), "x", 0.0, 2.0) == 2.0


def test_facade_symbolic_integral_abs_no_longer_raises():
    # 门面此前抛「内核无对应闭合规则」，修复后应给出原函数文本
    s = cs.symbolic_integral("abs(x)", "x")
    assert isinstance(s, str) and "abs" in s


def test_abs_nonlinear_inner_still_fails_loudly():
    # 内函数非线性：不在覆盖范围，仍显式返回 None（不静默造值）
    assert integrate(symbol_expr("abs(x**2)"), "x") is None
    assert integrate(symbol_expr("abs(sin(x))"), "x") is None
