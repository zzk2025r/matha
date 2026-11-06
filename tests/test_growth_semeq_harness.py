"""成长系统·语义等价对拍 harness（阶段 7·P2-0）自锁。

确立后续优化器规则的**唯一正交验证标准**：原文 vs 改写文各在一次性解释器上跑一遍、
比对可观测 `outputs`（见 `MathaGrowthEngine._semantic_equivalent`）。本片**只**落 harness
并自证其判别力（该判等价的判等价、该破的判破），**不改 `grow()` 行为**（P1 闸门照旧兜底）。
离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine

# 已确证等价的恒等式对（原文含恒等式，改写文为其右恒等元消去形态）
EQUIV_PAIRS = [
    ("x = 5.0\ny = x + 0\n#1：[y]\n", "x = 5.0\ny = x\n#1：[y]\n"),
    ("x = 7.0\ny = x * 1\n#1：[y]\n", "x = 7.0\ny = x\n#1：[y]\n"),
    ("x = 3.0\ny = x ** 1\n#1：[y]\n", "x = 3.0\ny = x\n#1：[y]\n"),
    ("x = 4.0\ny = 1 * x\n#1：[y]\n", "x = 4.0\ny = x\n#1：[y]\n"),
    ("x = 6.0\ny = x - 0\n#1：[y]\n", "x = 6.0\ny = x\n#1：[y]\n"),
    ("x = 8.0\ny = x / 1\n#1：[y]\n", "x = 8.0\ny = x\n#1：[y]\n"),
]


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


class TestHarnessAffirmsEquivalence:
    @pytest.mark.parametrize("orig,improved", EQUIV_PAIRS)
    def test_identity_pairs_are_equivalent(self, engine, orig, improved):
        assert engine._semantic_equivalent(orig, improved) is True

    def test_identical_source_is_equivalent(self, engine):
        s = "x = 2.0\ny = x * 3.0\n#1：[y]\n"
        assert engine._semantic_equivalent(s, s) is True


class TestHarnessCatchesBreakage:
    def test_value_change_is_not_equivalent(self, engine):
        # x+0 与 x+1 观测值不同 → 必须判不等价
        assert engine._semantic_equivalent(
            "x = 5.0\ny = x + 0\n#1：[y]\n",
            "x = 5.0\ny = x + 1\n#1：[y]\n",
        ) is False

    def test_const_propagation_corruption_caught(self, engine):
        # 元凶 B 形态：赋值退化为裸等式 `7.0 = 7.0`，被求值后多产出一个输出 → 不等价
        assert engine._semantic_equivalent(
            "y = 3.0 + 4.0\nz = y * 2.0\n#1：[z]\n",
            "7.0 = 7.0\nz = 7.0 * 2.0\n#1：[z]\n",
        ) is False

    def test_unparseable_improved_is_not_equivalent(self, engine):
        # 元凶 A 形态：改写文不可解析（函数名被删）→ 判不等价
        assert engine._semantic_equivalent(
            "func 加(x, y) -> Int = (x, y) => x + y\n#1：[加(2, 3)]\n",
            "func (x + y) -> Int = (x, y) => x + y\n#1：[加(2, 3)]\n",
        ) is False


class TestHarnessErrorHandling:
    def test_unparseable_original_cannot_be_baseline(self, engine):
        assert engine._semantic_equivalent("%%%乱码@@@\n", "x = 1.0\n#1：[x]\n") is False

    def test_dropped_definition_caught_fresh_interpreter(self, engine):
        # 改写文删掉了原文对被引用变量的绑定 → 运行期引用未定义 → 不等价；
        # 同时佐证每次调用是全新解释器（前一用例的 x 不会泄漏到此）。
        assert engine._semantic_equivalent(
            "x = 1.0\n#1：[x]\n", "#1：[x]\n"
        ) is False

    def test_no_state_leak_between_cases(self, engine):
        # 先跑一个定义 x 的用例，再跑一个不应继承该 x 的等价对
        engine._semantic_equivalent("x = 42.0\n#1：[x]\n", "x = 42.0\n#1：[x]\n")
        assert engine._semantic_equivalent("#1：[x]\n", "x = 42.0\n#1：[x]\n") is False


class TestHarnessDeterminism:
    def test_repeated_calls_stable(self, engine):
        a, b = EQUIV_PAIRS[0]
        assert engine._semantic_equivalent(a, b) is True
        assert engine._semantic_equivalent(a, b) is True
