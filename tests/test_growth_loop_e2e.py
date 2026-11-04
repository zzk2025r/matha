# -*- coding: utf-8 -*-
"""阶段 6f-A · 成长闭环端到端（UnifiedGrowth 编排链）回归锁。

UnifiedGrowth 是把 selfupgrade / growth / matha_growth / inner_loop / formula / domain
等子系统串成一条「感知→生长→升级→自改进」闭环的顶层编排器。6e 的 phantom 教训是：各包装
只测过 fallback、没跑过真实委派，接线错配漏网。6f-A 在**单实例上顺序驱动整条链**，锁定每一步
的编排契约（返回形态稳定、绝不裸抛、子系统缺席时如实降级）。

纪律（遵 KNOWN_ISSUES §7c）：
- 只锁**编排契约与诚实降级**，**不背书**任何一步的"输出是否更优/正确"——故不断言
  `improved_source` 语义有效、不比较 self_grow 前后质量（A4）。
- `chat → MathaInnerLoop.on_interaction` 感知闭环已由 `tests/test_ai_e2e_pipeline.py`（6e）锁定，
  本文件不重复；此处专注 UnifiedGrowth 内部生长链。
- `get_growth_status` / `run_growth_pipeline` 委派的是**必需**引擎 `_growth_engine`
  （_ensure_initialized 无条件构建，非可选子系统）；引擎构建失败属真实环境故障，允许上抛，
  不在"可选子系统诚实降级"锁范围内——本文件不对二者编造降级断言。
- 全离线、无文件副作用、不触网。
"""
import sys
sys.path.insert(0, r'D:\trae')

import pytest

from src.unified_growth import UnifiedGrowth

VALID = "func 加(x, y) -> Int = (x, y) => x + y\n"


@pytest.fixture(scope="module")
def ug():
    """整条链共用一个已初始化实例（预热 import/引擎，避免重复构建领域公式注册表）。"""
    return UnifiedGrowth()


# ============================================================
# A1：单实例顺序驱动整条链，锁定每一步编排契约
# ============================================================

class TestGrowthChainContract:
    def test_chain_runs_in_sequence_without_raising(self, ug):
        # 每一步都必须在真实委派下返回稳定形态，任一环节裸抛即编排断裂
        status = ug.get_growth_status()
        assert isinstance(status, dict)
        assert {"total_learned", "total_failures", "known_expressions"} <= set(status)

        grown = ug.self_grow(VALID)
        assert isinstance(grown, dict)
        assert {"success", "improved_source", "optimizations_applied",
                "diagnostics", "iteration"} <= set(grown)
        # A4：只锁形态，绝不断言 improved_source 更优/有效（self_grow 可用时应 success）
        if grown["success"]:
            assert isinstance(grown["optimizations_applied"], list)
            assert isinstance(grown["iteration"], int)

        formed = ug.formula_grow("compose", names=[])
        assert isinstance(formed, dict) and "success" in formed
        if formed["success"]:
            assert "results" in formed

        piped = ug.run_growth_pipeline(VALID)
        assert isinstance(piped, bool)          # 契约：委派布尔，不裸抛、不断言升级"成功"

        looped = ug.run_inner_loop("验证 加(2, 3)")
        assert isinstance(looped, dict)
        assert {"success", "task", "rounds_run", "results"} <= set(looped)
        assert isinstance(looped["rounds_run"], int)

    def test_domain_formula_summary_shape(self, ug):
        s = ug.domain_formula_summary()
        assert isinstance(s, dict)
        assert {"loaded_domains", "total_formulas", "summary"} <= set(s)
        assert isinstance(s["total_formulas"], int)


# ============================================================
# A3：可选子系统缺席 → 整链如实降级，绝不裸抛
# ============================================================

class TestHonestDegradation:
    """_ensure_initialized 会在每次调用时按工厂重建子系统，故须经 monkeypatch 让
    模块级 `_get_*` 工厂返回 None，才能真正触发缺席分支。"""

    def test_self_grow_degrades(self, monkeypatch):
        monkeypatch.setattr("src.unified_growth._get_matha_growth", lambda: None)
        r = UnifiedGrowth().self_grow(VALID)
        assert r["success"] is False and r.get("error")        # 不裸抛、如实报告不可用

    def test_formula_grow_degrades(self, monkeypatch):
        monkeypatch.setattr("src.unified_growth._get_formula_growth", lambda: None)
        r = UnifiedGrowth().formula_grow("compose", names=[])
        assert r["success"] is False and r.get("error")

    def test_run_inner_loop_degrades(self, monkeypatch):
        monkeypatch.setattr("src.unified_growth._get_inner_loop", lambda: None)
        r = UnifiedGrowth().run_inner_loop("x")
        assert r["success"] is False and r.get("error")

    def test_domain_formula_summary_degrades(self, monkeypatch):
        monkeypatch.setattr("src.unified_growth._get_domain_formula", lambda: None)
        r = UnifiedGrowth().domain_formula_summary()
        assert isinstance(r, dict) and r.get("error")           # 缺席 → 带 error、非抛


# ============================================================
# A3/边界：畸形输入下整链仍不裸抛（编排鲁棒性）
# ============================================================

class TestChainNeverRaises:
    @pytest.mark.parametrize("src_input", ["", "   ", "%%%乱码@@@", "func 坏(x -> Int = ==="])
    def test_growth_steps_tolerate_bad_source(self, ug, src_input):
        # 空/畸形/语法错误源码：self_grow / run_growth_pipeline / sandbox_run 均须返回而非抛
        assert isinstance(ug.self_grow(src_input), dict)
        assert isinstance(ug.run_growth_pipeline(src_input), bool)
        assert isinstance(ug.sandbox_run(src_input), dict)

    def test_run_inner_loop_empty_task_returns_dict(self, ug):
        assert isinstance(ug.run_inner_loop(""), dict)


# ============================================================
# 6f-B：弱契约 → 强契约（断真实委派发生，而非仅断返回类型）
# ============================================================

class TestRealDelegationStrengthening:
    """6e phantom 教训的反面：仅断 `isinstance(x, bool)` 无法区分“真委派”与
    “碰巧返回同型”。本类用桩引擎坐实：包装确实把调用透传给子系统的对应方法、
    参数原样到达、结果原样透出。仍只锁**接线**，不背书子系统输出正确性。"""

    def test_run_growth_pipeline_delegates_to_engine(self):
        """B2：run_growth_pipeline 必须委派 _growth_engine.run_upgrade_pipeline(source)
        并透传其返回值（旧弱契约仅断 bool，无法证明委派真实发生）。"""
        calls = []

        class _StubEngine:
            def run_upgrade_pipeline(self, patch_code):
                calls.append(patch_code)
                return "SENTINEL_FROM_ENGINE"
            def get_growth_stats(self):
                return {}

        u = UnifiedGrowth()
        u._ensure_initialized()            # 先建真实引擎，再换成桩（_growth_engine 非 None 则不重建）
        u._growth_engine = _StubEngine()
        assert u.run_growth_pipeline(VALID) == "SENTINEL_FROM_ENGINE"  # 结果透传
        assert calls == [VALID]                                          # 真实委派发生、参数原样到达

    def test_get_growth_status_delegates_to_engine(self):
        """B2 同族：get_growth_status 必须透传 _growth_engine.get_growth_stats()。"""
        sentinel = {"total_learned": 7, "total_failures": 2, "known_expressions": []}

        class _StubEngine:
            def get_growth_stats(self):
                return sentinel
            def run_upgrade_pipeline(self, patch_code):
                return True

        u = UnifiedGrowth()
        u._ensure_initialized()
        u._growth_engine = _StubEngine()
        assert u.get_growth_status() is sentinel          # 直接委派、结果原样透出

    def test_self_grow_success_schema_exact(self, ug):
        """B3：self_grow 可用时返回**恰好 6 键**（与 unified_growth 定义对齐），不可用时 2 键。"""
        r = ug.self_grow(VALID)
        if r.get("success"):
            assert set(r) == {"success", "report", "improved_source",
                              "optimizations_applied", "diagnostics", "iteration"}
        else:                                             # 降级分支也必须 schema 稳定
            assert set(r) == {"success", "error"}

    def test_self_grow_degraded_schema_exact(self, monkeypatch):
        monkeypatch.setattr("src.unified_growth._get_matha_growth", lambda: None)
        r = UnifiedGrowth().self_grow(VALID)
        assert set(r) == {"success", "error"} and r["success"] is False
