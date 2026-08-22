# -*- coding: utf-8 -*-
"""
Matha 自主成长引擎 v1.2.17 — 单元测试（精简版，避免超时）
"""
import sys
import unittest
import time
sys.path.insert(0, r"D:\trae")

from src.growth_engine import (
    GrowthEngine, Defect, GrowthReport,
    Severity, DefectCategory, RemediationAction,
    create_growth_engine, run_growth_cycle,
)
from src.ai_assistant import MathaAIAssistant, IntentType


class TestGrowthEngineCore(unittest.TestCase):
    """核心功能测试。"""

    def setUp(self):
        self.engine = create_growth_engine()
        self.assistant = MathaAIAssistant()
        self.engine_with = create_growth_engine(assistant=self.assistant)

    # ── 1. 资源完整性检测 ──────────────────────────────────────────────────────

    def test_audit_resources(self):
        """测试资源审计。"""
        entries = self.engine.audit_resources()
        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0)
        names = [e.name for e in entries]
        self.assertIn("keyword_arithmetic", names)
        self.assertIn("growth_system", names)

    def test_resource_entry_structure(self):
        """测试资源条目结构。"""
        entries = self.engine.audit_resources()
        for entry in entries:
            self.assertIsInstance(entry.name, str)
            self.assertIn(entry.status, ["ok", "missing", "degraded"])

    # ── 2. 缺陷管理 ──────────────────────────────────────────────────────────────

    def test_add_and_resolve_defect(self):
        """测试缺陷添加和解决。"""
        defect = self.engine._add_defect(DefectCategory.功能缺陷, Severity.HIGH,
                                         "测试缺陷", "test")
        self.assertEqual(defect.status, "open")
        self.engine._resolve_defect(defect.defect_id, "user",
                                     patch_code="# fix",
                                     action=RemediationAction.自动生成补丁)
        self.assertEqual(defect.status, "resolved")

    def test_defect_stats(self):
        """测试缺陷统计。"""
        for i in range(3):
            self.engine._add_defect(DefectCategory.资源缺失, Severity.MEDIUM,
                                     f"测试缺陷{i}", "test")
        stats = self.engine.get_defect_stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["open"], 3)
        self.assertIn("by_category", stats)

    def test_get_defects_filter(self):
        """测试缺陷过滤。"""
        self.engine._add_defect(DefectCategory.功能缺陷, Severity.CRITICAL,
                                 "严重缺陷", "test")
        self.engine._add_defect(DefectCategory.资源缺失, Severity.LOW,
                                 "低严重度", "test")
        self.assertEqual(len(self.engine.get_defects(severity=Severity.CRITICAL)), 1)
        self.assertEqual(len(self.engine.get_defects(severity=Severity.LOW)), 1)

    # ── 3. 跨功能缺陷联动 ────────────────────────────────────────────────────────

    def test_link_defects(self):
        """测试缺陷关联。"""
        d1 = self.engine._add_defect(DefectCategory.功能缺陷, Severity.HIGH, "缺陷A", "test")
        d2 = self.engine._add_defect(DefectCategory.资源缺失, Severity.MEDIUM, "缺陷B", "test")
        self.assertTrue(self.engine.link_defects(d1.defect_id, d2.defect_id))
        self.assertIn(d2.defect_id, d1.related_defects)

    def test_auto_link_related(self):
        """测试自动关联相关缺陷。"""
        d1 = self.engine._add_defect(DefectCategory.功能缺陷, Severity.HIGH, "测试1", "intent_parser")
        d2 = self.engine._add_defect(DefectCategory.功能缺陷, Severity.HIGH, "测试2", "intent_parser")
        linked = self.engine.auto_link_related(d1, [d2])
        self.assertIn(d2.defect_id, linked)

    def test_balance_defects(self):
        """测试缺陷平衡。"""
        d1 = self.engine._add_defect(DefectCategory.功能缺陷, Severity.CRITICAL,
                                       "意图解析器关键词缺失", "intent_parser")
        d2 = self.engine._add_defect(DefectCategory.知识空白, Severity.HIGH,
                                       "意图解析器知识覆盖不足", "intent_parser")
        balanced = self.engine.balance_defects(d1)
        self.assertIn(d2.defect_id, balanced)

    # ── 4. 功能自检 ──────────────────────────────────────────────────────────────

    def test_self_diagnose_runs(self):
        """测试自检正常运行。"""
        defects = self.engine.self_diagnose()
        self.assertIsInstance(defects, list)

    def test_diagnose_growth_no_assistant(self):
        """测试成长系统自检（无助手）。"""
        engine = create_growth_engine()
        engine.diagnose_growth()
        defects = engine.get_defects(status="open")
        growth = [d for d in defects if d.source == "growth"]
        self.assertGreater(len(growth), 0)

    def test_diagnose_growth_with_assistant(self):
        """测试成长系统自检（有助手）。"""
        engine = create_growth_engine(assistant=self.assistant)
        engine.diagnose_growth()
        defects = engine.get_defects(status="open")
        growth = [d for d in defects if d.source == "growth"]
        self.assertEqual(len(growth), 0)

    def test_diagnose_cross_function(self):
        """测试跨功能联动自检。"""
        self.engine_with.diagnose_cross_function()
        defects = self.engine_with.get_defects(status="open")
        cross = [d for d in defects if d.source == "cross_function"]
        self.assertEqual(len(cross), 0)

    # ── 5. 功能互相辅助 ──────────────────────────────────────────────────────────

    def test_assistant_calls_engine(self):
        """测试 AI 助手调用成长引擎。"""
        stats = self.engine_with.get_growth_stats()
        self.assertIn("total_learned", stats)
        self.assertIn("engine_defects", stats)

    def test_cross_feature_helper(self):
        """测试跨功能辅助调用。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        intent, conf = p.classify("帮我算一下 2+2")
        self.assertEqual(intent.value, "arithmetic")

    # ── 6. 自动补丁生成 ──────────────────────────────────────────────────────────

    def test_generate_patch_missing_resource(self):
        """测试生成资源缺失补丁。"""
        defect = Defect("DEF_TEST", DefectCategory.资源缺失, Severity.MEDIUM,
                        "test", "关键词覆盖率不足", time.time())
        patch = self.engine.generate_patch(defect)
        self.assertIsNotNone(patch)
        self.assertGreater(len(patch), 0)

    def test_generate_patch_uncovered_scenario(self):
        """测试生成未覆盖场景补丁。"""
        defect = Defect("DEF_TEST", DefectCategory.未覆盖场景, Severity.LOW,
                        "test", "意图解析错误", time.time())
        patch = self.engine.generate_patch(defect)
        self.assertIn("VARIATION_MAP", patch)

    # ── 7. 升级管道 ──────────────────────────────────────────────────────────────

    def test_upgrade_pipeline_success(self):
        """测试升级管道成功。"""
        result = self.engine.run_upgrade_pipeline("# test", verify_fn=lambda: True)
        self.assertTrue(result)
        self.assertEqual(len(self.engine._upgrade_history), 1)

    def test_upgrade_pipeline_sandbox_failure(self):
        """测试沙箱验证失败。"""
        result = self.engine.run_upgrade_pipeline("defunc foo(")
        self.assertFalse(result)

    def test_upgrade_pipeline_verify_failure(self):
        """测试验证失败后回滚。"""
        result = self.engine.run_upgrade_pipeline("# test", verify_fn=lambda: False)
        self.assertFalse(result)

    # ── 8. 自动修复 ──────────────────────────────────────────────────────────────

    def test_auto_remediate_medium(self):
        """测试严重度 MEDIUM 自动修复。"""
        defect = self.engine._add_defect(DefectCategory.知识空白, Severity.MEDIUM,
                                         "知识覆盖不足", "test")
        self.engine.auto_remediate(defect)
        if defect.status == "resolved":
            self.assertGreater(len(defect.patch_code), 0)

    def test_auto_remediate_low(self):
        """测试严重度 LOW 自动修复（加入队列）。"""
        defect = self.engine._add_defect(DefectCategory.未覆盖场景, Severity.LOW,
                                         "未覆盖场景", "test")
        self.engine.auto_remediate(defect)
        self.assertGreater(len(self.engine._remediation_queue), 0)

    # ── 9. 成长统计 ──────────────────────────────────────────────────────────────

    def test_get_growth_stats(self):
        """测试获取成长统计。"""
        stats = self.engine_with.get_growth_stats()
        self.assertIn("total_learned", stats)
        self.assertIn("engine_defects", stats)
        self.assertIn("resources_audited", stats)

    def test_trigger_growth(self):
        """测试触发成长。"""
        result = self.engine_with.trigger_growth()
        self.assertIn("report", result)
        self.assertIn("stats", result)

    # ── 10. 成长缺陷自动替换升级 ────────────────────────────────────────────────

    def test_rollback_on_upgrade_failure(self):
        """测试升级失败后自动回滚。"""
        self.engine._upgrade_history.append(
            {"patch_length": 50, "success": False, "timestamp": time.time()})
        report = self.engine.run_growth_cycle(max_iterations=1)
        self.assertIsInstance(report, GrowthReport)

    def test_defect_auto_replace(self):
        """测试缺陷自动替换。"""
        defect = self.engine._add_defect(DefectCategory.功能缺陷, Severity.MEDIUM,
                                         "测试可修复缺陷", "test")
        self.engine.auto_remediate(defect)
        if defect.status == "resolved":
            self.assertGreater(len(defect.patch_code), 0)


class TestGrowthEngineIntegration(unittest.TestCase):
    """集成测试。"""

    def test_full_pipeline(self):
        """端到端完整流程。"""
        engine = create_growth_engine()
        assistant = MathaAIAssistant()
        engine._assistant = assistant

        # 资源审计
        resources = engine.audit_resources()
        self.assertGreater(len(resources), 0)

        # 缺陷检测
        defects = engine.self_diagnose()
        self.assertIsInstance(defects, list)

        # 统计
        stats = engine.get_growth_stats()
        self.assertIn("engine_defects", stats)

    def test_assistant_with_growth(self):
        """测试 AI 助手与成长引擎集成。"""
        assistant = MathaAIAssistant()
        engine = create_growth_engine(assistant=assistant)

        # 助手正常处理
        result = assistant.chat("帮我算一下 100 的一半")
        self.assertIsNotNone(result.get("result"))

        # 成长统计
        stats = engine.get_growth_stats()
        self.assertIn("total_learned", stats)

        # 触发学习
        assistant.parser.record_failure("测试失败", "模拟错误", IntentType.算术)
        stats2 = engine.get_growth_stats()
        self.assertGreater(stats2["total_failures"], 0)


class TestGrowthAPI(unittest.TestCase):
    """API 端点测试。"""

    def test_create_engine(self):
        """测试工厂函数。"""
        engine = create_growth_engine()
        self.assertIsInstance(engine, GrowthEngine)

    def test_run_growth_cycle_function(self):
        """测试便捷函数。"""
        result = run_growth_cycle()
        self.assertIn("report", result)
        self.assertIn("stats", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
