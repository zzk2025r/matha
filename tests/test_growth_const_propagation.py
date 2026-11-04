r"""成长系统·常量传播规则修正（阶段 7·P2-2）回归锁。

修复元凶 B：旧 `_apply_const_propagation` ① 把 `y = 3.0 + 4.0` 误读为常量 `3.0`、
② `re.sub` 连赋值左端一起改写为 `7.0 = 7.0`（丢绑定名）。新实现严格只做两件事（拍板）：
  ① 仅认「整行右端恰为单一数字字面量 `\d+(\.\d*)?`」的绑定；
  ② 仅替换「名字后不跟 =」的使用点、绝不碰左端（并经 `_sub_outside_strings` 字符串守卫）。
不引入循环/重绑定守卫（严格贴合字面）。每条改写经 P1 闸门 `_is_safe_candidate` 与
P2-0 harness `_semantic_equivalent` 双验收。离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine
from src.parser import parse


def _bound(src: str) -> set[str]:
    return MathaGrowthEngine._bound_names(parse(src))


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


# 正例：原文（纯字面量绑定 + 使用点）→ 期望改写；outvar 用于追加输出标记做等价对拍
PROPAGATES = [
    ("a = 10.0\nb = a + 1\n", "a = 10.0\nb = 10.0 + 1\n", "b"),
    ("a = 3.0\nz = a * a\n", "a = 3.0\nz = 3.0 * 3.0\n", "z"),
    ("n = 5\nm = n + 1\n", "n = 5\nm = 5 + 1\n", "m"),
    # CONSTFOLD_B 经常量折叠后的形态：只传播使用点、左端 y 保留
    ("y = 7.0\nz = y * 2.0\n", "y = 7.0\nz = 7.0 * 2.0\n", "z"),
]


class TestPropagatesPureLiteralBindings:
    @pytest.mark.parametrize("code,expected,outvar", PROPAGATES)
    def test_rule_output_matches(self, engine, code, expected, outvar):
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == expected
        assert cnt >= 1

    @pytest.mark.parametrize("code,expected,outvar", PROPAGATES)
    def test_safe_candidate_gate(self, engine, code, expected, outvar):
        assert engine._is_safe_candidate(code, expected) is True

    @pytest.mark.parametrize("code,expected,outvar", PROPAGATES)
    def test_semantic_equivalence_gate(self, engine, code, expected, outvar):
        o = code + f"#1：[{outvar}]\n"
        i = expected + f"#1：[{outvar}]\n"
        assert engine._semantic_equivalent(o, i) is True


class TestNeverTouchesLeftHandSide:
    def test_binding_lhs_preserved_no_literal_equation(self, engine):
        # 元凶 B②：绝不把 `y = 7.0` 退化为 `7.0 = 7.0`
        improved, _ = engine._apply_const_propagation("y = 7.0\nz = y * 2.0\n")
        assert "y = 7.0" in improved
        assert "7.0 = 7.0" not in improved
        assert "y" in _bound(improved)


class TestRejectsNonPureRhs:
    def test_expression_rhs_not_propagated(self, engine):
        # 元凶 B①：`y = 3.0 + 4.0` 右端非纯字面量 → 完全不识别为常量、原文不动
        code = "y = 3.0 + 4.0\nz = y * 2.0\n"
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == code
        assert cnt == 0

    def test_identifier_rhs_not_propagated(self, engine):
        code = "a = b\nz = a + 1\n"
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == code
        assert cnt == 0


class TestConservativeNumberForms:
    @pytest.mark.parametrize("code", [
        "x = -3.0\ny = x + 1\n",   # 负号不认
        "x = .5\ny = x + 1\n",     # 前导点不认
        "x = 1e3\ny = x + 1\n",    # 科学计数不认
    ])
    def test_nonstandard_literals_not_propagated(self, engine, code):
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == code
        assert cnt == 0

    def test_comparison_not_treated_as_def(self, engine):
        code = "a == 3.0\ny = a + 1\n"
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == code
        assert cnt == 0


class TestStringAndUseGuards:
    def test_string_literal_not_corrupted(self, engine):
        code = 'a = 2.0\ns = "a a"\n'
        improved, cnt = engine._apply_const_propagation(code)
        assert 's = "a a"' in improved  # 字符串内 a 未被替换
        assert improved == code
        assert cnt == 0

    def test_unused_const_zero_substitutions(self, engine):
        code = "a = 1.0\nb = 2.0\n"
        improved, cnt = engine._apply_const_propagation(code)
        assert improved == code
        assert cnt == 0

    def test_counts_each_use_site(self, engine):
        _, cnt = engine._apply_const_propagation("a = 3.0\nz = a + a\n")
        assert cnt == 2

    def test_idempotent(self, engine):
        once, _ = engine._apply_const_propagation("a = 2.0\nb = a + 1\n")
        twice, cnt2 = engine._apply_const_propagation(once)
        assert twice == once
        assert cnt2 == 0
