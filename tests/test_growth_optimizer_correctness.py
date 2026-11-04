"""成长系统·优化器输出正确性闸门（阶段 7·P1）回归锁。

口径（见 KNOWN_ISSUES.md §7c）：本锁**只**验证 `MathaGrowthEngine.grow` 的
「绝不出坏源码」底线——
  ① grow 出码恒「等于原文回退」或「可被重新解析」；
  ② 出码不丢失原文已绑定的顶层名字（Binding 变量 / FuncDef）；
  ③ 候选改写未过闸门时诚实回退（optimizations_applied 置空、记 errors、不前传坏码）。
**不背书**优化的"有效性/更快"（属 P2/P3），也**不依赖** `_verify`（其为恒 False 的 phantom）。
全程离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

import pytest

from src.matha_growth import GrowthReport, MathaGrowthEngine
from src.parser import parse

CURRY_A = "func 加(x, y) -> Int = (x, y) => x + y\n"
CONSTFOLD_B = "y = 3.0 + 4.0\nz = y * 2.0\n"
TRIG = "y = sin(x)**2 + cos(x)**2\n"
FUNC_PLAIN = "func sq(x) -> Int = x * x\n"

CORPUS = [
    CURRY_A, CONSTFOLD_B, TRIG, FUNC_PLAIN,
    "", "   ", "%%%乱码@@@\n",
    "for i in range(3):\n    s = s + i\n",
    "x = 1.0\ny = x + 2.0\n",
    "a = 2.0\nb = a * a\n",
]


def _parses(src: str) -> bool:
    try:
        parse(src)
        return True
    except Exception:
        return False


def _bound(src: str) -> set[str]:
    return MathaGrowthEngine._bound_names(parse(src))


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


class TestGrowNeverEmitsBadSource:
    @pytest.mark.parametrize("src", CORPUS)
    def test_output_is_original_or_parseable(self, engine, src):
        rep = engine.grow(src)
        assert isinstance(rep, GrowthReport)
        out = rep.improved_source
        assert out == src or _parses(out), f"出码既非原文回退又不可解析：{out!r}"

    @pytest.mark.parametrize("src", [s for s in CORPUS if _parses(s)])
    def test_bound_names_conserved(self, engine, src):
        out = engine.grow(src).improved_source
        assert _bound(src) <= _bound(out), f"丢失已绑定名字：{src!r} -> {out!r}"

    def test_function_name_not_dropped(self, engine):
        # 元凶 A：旧行为把 'func 加(...)' 改写成 'func (x + y)...' 而删函数名
        out = engine.grow(CURRY_A).improved_source
        assert "加" in out
        assert "func (x + y)" not in out
        assert _parses(out)

    def test_no_literal_assignment_degradation(self, engine):
        # 元凶 B：旧行为把 'y = 3.0 + 4.0' 腐蚀成 '7.0 = 7.0'（赋值退化为裸等式、丢绑定 y）
        out = engine.grow(CONSTFOLD_B).improved_source
        assert "7.0 = 7.0" not in out
        assert "y" in _bound(out)
        assert _parses(out)


class TestHonestFallback:
    def test_rejected_candidate_empties_applied_and_records_error(self, engine):
        rep = engine.grow(CURRY_A)
        assert rep.optimizations_applied == []
        assert rep.improved_source == CURRY_A  # 回退到上一安全版本（此处即原文）
        assert rep.errors  # 如实登记回退原因

    def test_grow_never_raises(self, engine):
        for src in CORPUS:
            assert isinstance(engine.grow(src), GrowthReport)


class TestIsSafeCandidate:
    def test_same_source_is_safe(self, engine):
        assert engine._is_safe_candidate(CURRY_A, CURRY_A) is True

    def test_unparseable_improved_rejected(self, engine):
        assert engine._is_safe_candidate(CURRY_A, "func (x + y) -> Int = x + y\n") is False

    def test_name_loss_rejected(self, engine):
        assert engine._is_safe_candidate("y = 3.0 + 4.0\n", "7.0 = 7.0\n") is False

    def test_legit_trig_fold_accepted(self, engine):
        assert engine._is_safe_candidate(TRIG, "y = 1\n") is True

    def test_unparseable_original_only_needs_parseable_improved(self, engine):
        assert engine._is_safe_candidate("%%%乱码@@@\n", "x = 1.0\n") is True


class TestBoundNamesHelper:
    def test_extracts_binding_vars_and_funcdef_names(self, engine):
        prog = parse(FUNC_PLAIN + "y = 2.0\n")
        assert MathaGrowthEngine._bound_names(prog) == {"sq", "y"}

    def test_ignores_non_name_targets(self, engine):
        # 裸等式（BinaryOp）不产生任何绑定名——正是元凶 B 退化后的形态
        assert MathaGrowthEngine._bound_names(parse("7.0 = 7.0\n")) == set()
