"""成长系统·简单算术恒等式改写规则（阶段 7·P2-1）回归锁。

首批仅 7 条恒等元消去（`x+0/x-0/0+x/1*x/x*1/x/1/x**1 → x`），纯正则、**不泛化**。
验收三支柱：① 规则级改写形态正确；② 反例与字符串字面量**绝不误伤**；
③ 每条改写经 **P2-0 语义等价 harness**（`_semantic_equivalent` 真实 outputs 对拍）
且与 **P1 闸门**（`_is_safe_candidate` 再解析/名守恒）兼容。离线、毫秒级、不触 L1 内核。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine

# 7 条恒等式：绑定值片段 → 消去后形态
IDENTITIES = [
    ("x + 0", "x"),
    ("x - 0", "x"),
    ("0 + x", "x"),
    ("1 * x", "x"),
    ("x * 1", "x"),
    ("x / 1", "x"),
    ("x ** 1", "x"),
]

# 严格不泛化：以下均**不得**被改写（非本批 7 条 / 恒等元非裸 0/1 / 操作数越界）
NO_OVER_MATCH = [
    "y = x + 1\n",     # 1 非加法恒等元
    "y = x + 0.5\n",   # 0.5 非裸 0
    "y = 10 + x\n",    # 10 非裸 0（字界防护）
    "y = 11 * x\n",    # 11 非裸 1（字界防护）
    "y = x * 0\n",     # x*0→0 不在本批
    "y = x ** 2\n",    # 指数非 1
    "y = x // 1\n",    # 整除不碰
    "y = x - x\n",     # 消元为 0 不在本批
    "y = f(1) + 0\n",  # 左操作数是调用而非标识符（不泛化）
]


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


class TestSevenIdentitiesApply:
    @pytest.mark.parametrize("expr,expected", IDENTITIES)
    def test_identity_reduces_to_operand(self, engine, expr, expected):
        improved, n = engine._apply_arith_identities(f"y = {expr}\n")
        assert improved == f"y = {expected}\n"
        assert n == 1

    def test_wired_into_optimizations(self, engine):
        improved, applied = engine._apply_optimizations("y = x + 0\n")
        assert improved == "y = x\n"
        assert any("算术恒等式" in s for s in applied)


class TestNoOverMatch:
    @pytest.mark.parametrize("src", NO_OVER_MATCH)
    def test_untouched(self, engine, src):
        improved, n = engine._apply_arith_identities(src)
        assert improved == src, f"越界改写：{src!r} -> {improved!r}"
        assert n == 0


class TestStringLiteralGuard:
    def test_pure_string_literal_untouched(self, engine):
        src = 's = "x + 0"\n'
        improved, n = engine._apply_arith_identities(src)
        assert improved == src
        assert n == 0

    def test_code_reduced_but_string_kept(self, engine):
        src = 'y = a + 0\ns = "a + 0"\n'
        improved, _ = engine._apply_arith_identities(src)
        assert improved == 'y = a\ns = "a + 0"\n'

    def test_unterminated_quote_conservatively_kept(self, engine):
        # 引号未闭合：宁可不改，不可改错——整段保守原样
        src = 'y = "x + 0\n'
        improved, n = engine._apply_arith_identities(src)
        assert n == 0
        assert improved == src


class TestRewriteIsSafeAndEquivalent:
    @pytest.mark.parametrize("expr,expected", IDENTITIES)
    def test_each_identity_passes_harness_and_gate(self, engine, expr, expected):
        orig = f"v = 7.0\ny = {expr.replace('x', 'v')}\n#1：[y]\n"
        improved = engine._apply_arith_identities(orig)[0]
        # 改写形态：v 恒等元消去
        assert improved == f"v = 7.0\ny = v\n#1：[y]\n"
        # ① P2-0 语义等价正交判据（真实 outputs 对拍）
        assert engine._semantic_equivalent(orig, improved) is True
        # ② 与 P1 闸门兼容（可解析 + 绑定名守恒）
        assert engine._is_safe_candidate(orig, improved) is True
