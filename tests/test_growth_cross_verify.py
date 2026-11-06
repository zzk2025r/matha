# -*- coding: utf-8 -*-
"""成长引擎语义验证锁（G-1 真修复 + G-2 假阳性守卫 + G-3 防腐蚀 + G-4 出口口径）。

覆盖五件事：
  1. 接线：`_verify` 委派 `src.growth_verify` 主链后端，`_exec_outputs` 亦统一到同一真源；
  2. 判据：真实 Matha 构造（func / 中文函数名 / let / `#1：[...]` 观测形态）给出有信息量的结论；
  3. 诚实降级：不可验证就不判一致（G-2 的「空对空」与「同文捷径」都不放行）；
  4. G-3：出厂优化规则不得再产出退化赋值 / 滚雪球腐蚀（P1 闸门 + 左值守恒），
     而验证通路本身仍须能在该形态出现时判破（保守口径不因规则修好而放松）；
  5. 边界与命名：宿主执行面兜底、harness 与 `_verify` 的口径分工、误导旧名不得复活。

历史口径见 `docs/KNOWN_ISSUES.md` 第七节（阶段 7 条目）与第八节（G-1…G-5）。
"""
from __future__ import annotations

import dataclasses
import inspect

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
FUNC_BROKEN_BODY = "func f(x) -> Int =\n"                     # 改写文体不可运行

CJK = "func 加(x, y) -> Int = x + y\nprint(加(1, 2))\n"
CJK_SWAP = "func 加(x, y) -> Int = y + x\nprint(加(1, 2))\n"
CJK_BROKEN = "func 加(x, y) -> Int = x - y\nprint(加(1, 2))\n"

LET_ORIG = "let a = 3\nlet b = 4\nprint(a + b)\n"
LET_REWRITE = "let a = 3\nlet b = 4\nprint(3 + 4)\n"

# `#1：[...]` 观测形态（阶段 7 分支语料）：恒等改写判等、取值改动判破
DIALECT_ORIG = "x = 5.0\ny = x + 0\n#1：[y]\n"
DIALECT_FOLD = "x = 5.0\ny = x\n#1：[y]\n"
DIALECT_BREAK = "x = 5.0\ny = x + 1\n#1：[y]\n"

GARBAGE = "func f(x -> Int = = =\n"
ARITH_OUT = "x = 3.0 + 4.0\nprint(x)\n"
ARITH_FOLDED = "x = 7.0\nprint(7.0)\n"
# main 出厂优化规则曾产出的退化赋值（字面量当左值，输出多出一个 True）。
# 规则已由 P1 闸门 + 左值守恒修复，此处仍保留该文本用于「判据不得放松」的锁。
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
# 1. 接线与单一真源
# ============================================================

class TestMainChainWiring:
    def test_engine_has_no_cross_language_verifier(self, engine):
        """死接线已移除：引擎不再持有验证器实例。"""
        assert not hasattr(engine, "_verifier")

    def test_module_no_longer_imports_the_verifier(self):
        import src.matha_growth as mg

        assert not hasattr(mg, "CrossLanguageVerifier")

    def test_verify_delegates_to_growth_verify(self, engine, restore_backend):
        """`_verify` 的两侧参数按 (original, improved) 顺序交给后端。"""
        seen: list[tuple[str, str]] = []

        def spy(a: str, b: str) -> gv.SemanticVerdict:
            seen.append((a, b))
            return gv.SemanticVerdict(True, "consistent")

        assert gv.register_backend("spy", spy, override=True) is True
        assert gv.set_active_backend("spy") is True
        assert engine._verify(FUNC, FUNC_IDENT) is True
        assert seen == [(FUNC, FUNC_IDENT)]

    def test_verify_runs_each_side_once_on_mainchain(self, engine, monkeypatch):
        """两侧各经主链执行一次，且顺序为（原文，改写文）。"""
        seen: list[str] = []
        real = gv.run_outputs

        def spy(source: str):
            seen.append(source)
            return real(source)

        monkeypatch.setattr(gv, "run_outputs", spy)
        assert engine._verify("print(1)\n", "print(1)\n") is True
        assert seen == ["print(1)\n", "print(1)\n"]

    def test_exec_outputs_is_not_a_second_implementation(self, engine, monkeypatch):
        """`_exec_outputs`（P2-0 harness 调用面）已统一到 growth_verify.run_outputs。"""
        import src.matha_growth as mg

        monkeypatch.setattr(mg, "run_outputs", lambda s: ([42], None))
        assert engine._exec_outputs("print(7)\n") == ([42], None)

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

    def test_dialect_observation_form_is_consistent(self, engine):
        """`#1：[y]` 观测形态下 `x + 0 → x` 属等价改写（旧 Python 子集前端亦能跑的语料）。"""
        assert engine._verify(DIALECT_ORIG, DIALECT_FOLD) is True

    def test_dialect_value_change_is_inconsistent(self, engine):
        assert engine._verify(DIALECT_ORIG, DIALECT_BREAK) is False

    def test_folded_arithmetic_pair_is_consistent(self, engine):
        assert engine._verify(ARITH_OUT, ARITH_FOLDED) is True

    def test_reason_is_machine_readable(self):
        assert gv.verify(FUNC, FUNC_DIFF).reason == gv.REASON_OUTPUTS_DIFFER
        assert gv.verify(FUNC, FUNC_IDENT).reason == gv.REASON_CONSISTENT
        assert gv.verify(FUNC, FUNC_BROKEN_BODY).reason == gv.REASON_IMPROVED_ERROR


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

    def test_broken_rewrite_body_is_false(self, engine):
        assert engine._verify(FUNC, FUNC_BROKEN_BODY) is False

    def test_unrunnable_reason_is_not_conflated_with_silent(self):
        assert gv.verify(GARBAGE, FUNC).reason == gv.REASON_ORIG_ERROR
        assert gv.verify(FUNC, GARBAGE).reason == gv.REASON_IMPROVED_ERROR
        assert gv.verify(FUNC_NOOUT, FUNC_NOOUT).reason == gv.REASON_ORIG_SILENT


class TestHarnessAndVerifyHaveDifferentScopes:
    """P2-0 harness `_semantic_equivalent` 本体口径不变（各规则对拍锁依赖它）。

    分工：harness 只要求「两侧可运行且 outputs 逐项相等」；`_verify` 作为对外
    佐证字段，额外要求「两侧均有可观测输出」（G-2 保守守卫）。二者在「同语义但
    无输出」的区间上**必须**给出不同结论，否则说明其中一层的口径被误改。
    """

    def test_silent_pair_harness_true_verify_false(self, engine):
        assert engine._semantic_equivalent(FUNC_NOOUT, FUNC_NOOUT_DIFF) is True
        assert engine._verify(FUNC_NOOUT, FUNC_NOOUT_DIFF) is False

    def test_real_break_both_layers_false(self, engine):
        assert engine._semantic_equivalent(FUNC, FUNC_DIFF) is False
        assert engine._verify(FUNC, FUNC_DIFF) is False


# ============================================================
# 4. G-3：出厂优化规则不再产出退化赋值 / 滚雪球腐蚀
# ============================================================

class TestG3CorruptionPrevented:
    """main 上曾实测：`x = 3.0 + 4.0` 被改成 `7.0 = 7.0`，多轮迭代滚成 `7.7.7…`。

    修复机制：常量折叠保持左值绑定名（`x = 7.0`），且每轮候选改写必须过 P1 闸门
    `_is_safe_candidate`（可再解析 + 顶层绑定名守恒）。本类锁住结果，而不是锁运气。
    """

    def test_folding_keeps_the_binding_name(self):
        report = MathaGrowthEngine().grow(ARITH_OUT)
        assert report.improved_source == ARITH_FOLDED
        assert "7.0 = 7.0" not in report.improved_source

    def test_no_snowball_across_iterations(self):
        report = MathaGrowthEngine().grow(ARITH_OUT)
        assert "7.7.7" not in report.improved_source
        assert report.semantic_consistent is True

    def test_integer_folding_and_propagation_preserve_bindings(self):
        e = MathaGrowthEngine()
        r1 = e.grow("y = 2 + 3\nprint(y)\n")
        # 折叠后常量传播会把 print(y) 一并换成 print(5)（可观测输出不变）
        assert r1.improved_source == "y = 5\nprint(5)\n"
        assert r1.semantic_consistent is True
        r2 = e.grow("a = 7\nb = a + 1\nprint(b)\n")
        assert r2.improved_source == "a = 7\nb = 8\nprint(8)\n"
        assert r2.semantic_consistent is True

    def test_gate_rejects_degenerate_assignment(self, engine):
        """退化赋值即便再次出现，也会被 P1 闸门挡在出码之前。"""
        assert engine._is_safe_candidate(ARITH_OUT, ARITH_CORRUPT) is False

    def test_verifier_still_catches_it_if_it_appears(self, engine):
        """规则修好不放松判据：该形态若出现在验证通路上，仍须判破并可诊断。"""
        assert engine._verify(ARITH_OUT, ARITH_CORRUPT) is False
        assert gv.verify(ARITH_OUT, ARITH_CORRUPT).reason == gv.REASON_OUTPUTS_DIFFER


# ============================================================
# 5. G-4 出口口径与 G-5 已知漏报
# ============================================================

class TestGrowIntegration:
    def test_field_is_real_bool_and_informative(self):
        report = MathaGrowthEngine().grow(FUNC)
        assert isinstance(report.semantic_consistent, bool)
        # 无可优化点的输入：改写前后同文且有输出 → 应报一致（旧实现恒 False）
        assert report.semantic_consistent is True

    def test_final_report_describes_original_to_final(self):
        """字段必须描述调用方关心的「原始 → 最终」，而非最后一次迭代的两步。"""
        report = MathaGrowthEngine().grow(ARITH_OUT)
        verdict = gv.verify(ARITH_OUT, report.improved_source)
        assert verdict.consistent is True
        assert report.semantic_consistent == verdict.consistent

    def test_no_change_input_is_consistent_at_boundary(self):
        report = MathaGrowthEngine().grow(FUNC)
        assert report.improved_source == FUNC
        assert report.semantic_consistent is True

    def test_grow_safety_is_independent_of_verify_field(self, engine):
        """出码安全只靠 P1 闸门：任何 grow 产物要么未改写，要么已过闸门。"""
        for src in (ARITH_OUT, FUNC, "y = 2 + 3\nprint(y)\n"):
            report = engine.grow(src)
            assert (report.improved_source == src) or engine._is_safe_candidate(
                src, report.improved_source)

    def test_old_misleading_field_name_is_gone(self):
        names = {f.name for f in dataclasses.fields(GrowthReport)}
        assert "cross_language_consistent" not in names
        assert "semantic_consistent" in names

    def test_construct_with_old_kwarg_is_rejected(self):
        with pytest.raises(TypeError):
            GrowthReport(iteration=0, source="", cross_language_consistent=True)


class TestG5AppliedRulesUnderReported:
    """表征锁（非认可）：`optimizations_applied` 只描述最后一次空转迭代。

    实测：`grow("x = 3.0 + 4.0\\nprint(x)\\n")` 第 1 轮应用「常量折叠 + 常量传播」，
    第 2 轮空转退出，而返回的正是第 2 轮的 report → `optimizations_applied == []`，
    与 `improved_source` 已发生的事实变化自相矛盾（与 G-4 同形，只是另一个字段）。
    登记于 `docs/KNOWN_ISSUES.md` 第八节 G-5。修它时须同步更新本锁与文档。
    """

    def test_applied_rules_are_empty_although_source_changed(self):
        report = MathaGrowthEngine().grow(ARITH_OUT)
        assert report.improved_source != ARITH_OUT
        assert report.optimizations_applied == []
        assert report.semantic_consistent is True


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
