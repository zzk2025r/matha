# -*- coding: utf-8 -*-
"""成长引擎语义验证（G-1 真修复 + G-2 假阳性守卫）锁。

覆盖四件事：
  1. 接线：`_verify` 走 `src.growth_verify` 主链后端，不再借 CrossLanguageVerifier；
  2. 判据：真实 Matha 构造（func / 中文函数名 / let）能给出有信息量的结论；
  3. 诚实降级：不可验证就不判一致（G-2 的「空对空」与「同文捷径」都不放行）；
  4. 边界与命名：宿主执行面兜底、旧误导字段名不得复活。
"""
from __future__ import annotations

import dataclasses

import pytest

import src.growth_verify as gv
from src.matha_growth import GrowthReport, MathaGrowthEngine

# ============================================================
# 语料
# ============================================================

FUNC = "func f(x) -> Int = x + 1\nprint(f(2))\n"
FUNC_IDENT = "func f(x) -> Int = x + 1 + 0\nprint(f(2))\n"     # 语义不变的恒等元改写
FUNC_DIFF = "func f(x) -> Int = x + 99\nprint(f(2))\n"        # 语义被破坏
FUNC_NOOUT = "func f(x) -> Int = x + 1\n"                     # 无可观测输出
FUNC_NOOUT_DIFF = "func f(x) -> Int = x + 99\n"

CJK = "func 加(x, y) -> Int = x + y\nprint(加(1, 2))\n"
CJK_SWAP = "func 加(x, y) -> Int = y + x\nprint(加(1, 2))\n"
CJK_BROKEN = "func 加(x, y) -> Int = x - y\nprint(加(1, 2))\n"

LET_ORIG = "let a = 3\nlet b = 4\nprint(a + b)\n"
LET_REWRITE = "let a = 3\nlet b = 4\nprint(3 + 4)\n"

GARBAGE = "func f(x -> Int = = =\n"
ARITH_OUT = "x = 3.0 + 4.0\nprint(x)\n"
# main 出厂优化规则对该输入的真实产物：字面量做左值的退化赋值（腐蚀类，
# 其修复属另一轨道，见 docs/KNOWN_ISSUES.md 第八节；此处只做表征锁）。
ARITH_CORRUPT = "7.0 = 7.0\nprint(7.0)\n"


@pytest.fixture
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


@pytest.fixture
def restore_backend():
    """注册表是模块级全局，用例后必须还原默认后端。"""
    yield
    gv.set_active_backend("mainchain")


# ============================================================
# 1. 接线
# ============================================================

class TestMainChainWiring:
    def test_engine_has_no_cross_language_verifier(self, engine):
        """死接线已移除：引擎不再持有验证器实例。"""
        assert not hasattr(engine, "_verifier")

    def test_module_no_longer_imports_the_verifier(self):
        import src.matha_growth as mg

        assert not hasattr(mg, "CrossLanguageVerifier")

    def test_verify_delegates_to_growth_verify(self, engine, monkeypatch, restore_backend):
        """`_verify` 的两侧参数按 (original, improved) 顺序交给后端。"""
        seen: list[tuple[str, str]] = []

        def spy(a: str, b: str) -> gv.SemanticVerdict:
            seen.append((a, b))
            return gv.SemanticVerdict(True, "consistent")

        assert gv.register_backend("spy", spy, override=True) is True
        assert gv.set_active_backend("spy") is True
        assert engine._verify(FUNC, FUNC_IDENT) is True
        assert seen == [(FUNC, FUNC_IDENT)]

    def test_default_backend_is_mainchain_only(self):
        assert gv.active_backend() == "mainchain"
        assert "mainchain" in gv.available_backends()


# ============================================================
# 2. 判据：真实 Matha 构造
# ============================================================

class TestRealMathaEquivalence:
    def test_identical_with_output_is_consistent(self, engine):
        assert engine._verify(FUNC, FUNC) is True

    def test_identity_rewrite_is_consistent(self, engine):
        assert engine._verify(FUNC, FUNC_IDENT) is True

    def test_semantic_break_is_inconsistent(self, engine):
        assert engine._verify(FUNC, FUNC_DIFF) is False

    def test_cjk_commutation_is_consistent(self, engine):
        """中文函数名走主链同样可验证（旧通路在此必挂）。"""
        assert engine._verify(CJK, CJK_SWAP) is True

    def test_cjk_break_is_inconsistent(self, engine):
        assert engine._verify(CJK, CJK_BROKEN) is False

    def test_let_rewrite_is_consistent(self, engine):
        assert engine._verify(LET_ORIG, LET_REWRITE) is True

    def test_reason_is_machine_readable(self):
        assert gv.verify(FUNC, FUNC_DIFF).reason == gv.REASON_OUTPUTS_DIFFER
        assert gv.verify(FUNC, FUNC_IDENT).reason == gv.REASON_CONSISTENT


# ============================================================
# 3. 诚实降级 + G-2 不变量
# ============================================================

class TestHonestDegradation:
    def test_both_unparseable_is_false(self, engine):
        assert engine._verify(GARBAGE, GARBAGE) is False

    def test_identical_but_unobservable_is_false(self, engine):
        """不设「同文即一致」捷径：同文但无输出，无从验证就不报一致。"""
        assert engine._verify(FUNC_NOOUT, FUNC_NOOUT) is False

    def test_vacuous_no_output_pair_is_false(self, engine):
        """G-2 核心：两侧都无输出时 `[] == []` 不得判一致。"""
        assert engine._verify(FUNC_NOOUT, FUNC_NOOUT_DIFF) is False

    def test_one_side_silent_is_false(self, engine):
        assert engine._verify(FUNC_NOOUT, FUNC) is False

    def test_unrunnable_reason_is_not_conflated_with_silent(self):
        assert gv.verify(GARBAGE, FUNC).reason == gv.REASON_ORIG_ERROR
        assert gv.verify(FUNC, GARBAGE).reason == gv.REASON_IMPROVED_ERROR
        assert gv.verify(FUNC_NOOUT, FUNC_NOOUT).reason == gv.REASON_ORIG_SILENT


# ============================================================
# 4. 表征锁：main 上真实存在的优化腐蚀现在可见
# ============================================================

class TestCorruptionNowVisible:
    def test_degenerate_assignment_is_flagged(self, engine):
        """`x = 3.0 + 4.0` 被改成 `7.0 = 7.0`（输出多出一个 True）→ 必须报不一致。

        旧通路对该输入恒 False（且理由是签名错配），信号被噪声淹没；
        现在它给出可诊断的 outputs_differ。
        """
        assert engine._verify(ARITH_OUT, ARITH_CORRUPT) is False
        assert gv.verify(ARITH_OUT, ARITH_CORRUPT).reason == gv.REASON_OUTPUTS_DIFFER

    def test_grow_marks_real_rewrite_inconsistent(self):
        report = MathaGrowthEngine().grow(ARITH_OUT)
        assert report.optimizations_applied
        assert report.improved_source != ARITH_OUT
        assert report.semantic_consistent is False


class TestRunawayIsObservable:
    """G-3 表征锁：main 出厂优化规则在多轮迭代下滚雪球式腐蚀。

    本 PR 不修优化规则（属另一轨道），只坐实它不再被验证通路掩盖；
    口径见 docs/KNOWN_ISSUES.md 第八节。
    """

    def test_multi_iteration_rewrite_runs_away_and_is_reported(self):
        report = MathaGrowthEngine().grow(ARITH_OUT)
        # 滚雪球：字面量被反复展开成非法文本
        assert "7.7.7" in report.improved_source
        # 且出口验证拒绝给出“一致”
        assert report.semantic_consistent is False

    def test_final_report_describes_original_to_final(self):
        """字段必须描述调用方关心的「原始 → 最终」，而非最后一次迭代的两步。"""
        report = MathaGrowthEngine().grow(ARITH_OUT)
        verdict = gv.verify(ARITH_OUT, report.improved_source)
        assert verdict.consistent is False
        assert report.semantic_consistent == verdict.consistent

    def test_no_change_input_is_consistent_at_boundary(self):
        report = MathaGrowthEngine().grow(FUNC)
        assert report.improved_source == FUNC
        assert report.semantic_consistent is True


# ============================================================
# 5. grow() 集成与字段命名
# ============================================================

class TestGrowIntegration:
    def test_field_is_real_bool_and_informative(self):
        report = MathaGrowthEngine().grow(FUNC)
        assert isinstance(report.semantic_consistent, bool)
        # 无可优化点的输入：改写前后同文且有输出 → 应报一致（旧实现恒 False）
        assert report.semantic_consistent is True

    def test_old_misleading_field_name_is_gone(self):
        names = {f.name for f in dataclasses.fields(GrowthReport)}
        assert "cross_language_consistent" not in names
        assert "semantic_consistent" in names

    def test_construct_with_old_kwarg_is_rejected(self):
        with pytest.raises(TypeError):
            GrowthReport(iteration=0, source="", cross_language_consistent=True)


# ============================================================
# 6. 安全边界与注册表纪律
# ============================================================

class TestSafetyBoundary:
    def test_foreign_forms_cannot_reach_host(self, tmp_path):
        """`#：` 外来声明在验证通路上不得产生宿主副作用（哨兵文件）。"""
        sentinel = tmp_path / "gv_sentinel.txt"
        hostile = [
            f'#：{{ import os; open(r"{sentinel}", "w").write("x") }}\nprint(1)\n',
            f'#：python：{{ open(r"{sentinel}", "w").write("x") }}\nprint(1)\n',
        ]
        for src in hostile:
            # 这些形式本身不可执行：要么解析失败，要么退化为无副作用节点
            gv.verify(src, src)
        assert not sentinel.exists()

    def test_comment_shaped_python_is_inert_yet_still_verifiable(self):
        """`# import os` 在 Matha 里是注释/惰性节点，不会被宿主执行。

        安全口径是「不执行宿主代码」，不是「一律报不一致」：同文且有输出的
        平凡情形必须仍然判一致，否则验证通路会连同正常输入一起变成噪声。
        """
        src = "# import os\nprint(1)\n"
        verdict = gv.verify(src, src)
        assert verdict.consistent is True
        assert verdict.original_outputs == [1]

    def test_interpreter_is_built_with_foreign_routing_off(self):
        """结构性兜底：验证通路构造解释器时显式关闭外部语言路由。"""
        import inspect

        assert "foreign_routing=False" in inspect.getsource(gv.run_outputs)


class TestBackendRegistry:
    def test_duplicate_registration_is_refused(self, restore_backend):
        assert gv.register_backend("mainchain", gv.verify_mainchain) is False

    def test_unknown_backend_cannot_be_activated(self, restore_backend):
        assert gv.set_active_backend("not-registered") is False
        assert gv.active_backend() == "mainchain"

    def test_registered_backend_can_be_swapped_in(self, restore_backend):
        def always_true(a: str, b: str) -> gv.SemanticVerdict:
            return gv.SemanticVerdict(True, "consistent")

        assert gv.register_backend("dummy", always_true, override=True) is True
        assert gv.set_active_backend("dummy") is True
        assert gv.is_semantically_consistent(FUNC, FUNC_DIFF) is True
