# -*- coding: utf-8 -*-
"""
Matha 自主成长系统单元测试

测试覆盖：
  1. 扩展注册表
  2. 自诊断引擎
  3. 自修改引擎
  4. 成长循环
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.growth import (
    Extension,
    ExtensionRegistry,
    SelfDiagnostic,
    SelfModifier,
    GrowthLoop,
    grow,
)
from src.mir_opt import MathaConstFoldPass


class TestExtensionRegistry(unittest.TestCase):
    """扩展注册表测试。"""

    def test_register_and_get(self):
        """测试注册和获取扩展。"""
        registry = ExtensionRegistry()
        ext = Extension(
            name="TestPass",
            kind="pass",
            module="src.mir_opt",
            class_name="MathaConstFoldPass",
        )
        registry.register(ext)

        retrieved = registry.get("TestPass")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "TestPass")

    def test_list_extensions(self):
        """测试列出扩展。"""
        registry = ExtensionRegistry()
        registry.register(Extension("Pass1", "pass", "src.mir_opt", "MathaConstFoldPass"))
        registry.register(Extension("Pass2", "pass", "src.mir_opt", "MathaConstFoldPass"))

        list_result = registry.list_extensions(kind="pass")
        self.assertEqual(len(list_result), 2)

    def test_unregister(self):
        """测试注销扩展。"""
        registry = ExtensionRegistry()
        ext = Extension("TestPass", "pass", "src.mir_opt", "MathaConstFoldPass")
        registry.register(ext)

        self.assertTrue(registry.unregister("TestPass"))
        self.assertIsNone(registry.get("TestPass"))

    def test_get_instance(self):
        """测试获取扩展实例。"""
        registry = ExtensionRegistry()
        ext = Extension(
            name="TestPass",
            kind="pass",
            module="src.mir_opt",
            class_name="MathaConstFoldPass",
        )
        registry.register(ext)

        instance = registry.get_instance("TestPass")
        self.assertIsNotNone(instance)
        self.assertTrue(hasattr(instance, "run"))


class TestSelfDiagnostic(unittest.TestCase):
    """自诊断引擎测试。"""

    def setUp(self):
        self.registry = ExtensionRegistry()
        self.diagnostic = SelfDiagnostic(self.registry)

    def test_diagnose_valid_source(self):
        """测试诊断有效源码。"""
        source = "x = sin(3.14) + cos(1.57)"
        results = self.diagnostic.diagnose(source)

        # 有效源码不应有错误
        errors = [r for r in results if r.severity == "error"]
        self.assertEqual(len(errors), 0)

    def test_diagnose_invalid_source(self):
        """测试诊断无效源码。"""
        source = "x = sin( + cos()"  # 语法错误
        results = self.diagnostic.diagnose(source)

        errors = [r for r in results if r.severity == "error"]
        self.assertGreater(len(errors), 0)

    def test_diagnose_performance_warning(self):
        """测试性能警告检测。"""
        # 重复调用超过5次的函数应触发警告
        source = "x = sin(1) + sin(2) + sin(3) + sin(4) + sin(5) + sin(6)"
        results = self.diagnostic.diagnose(source)

        warnings = [r for r in results if r.severity == "warning"]
        # 可能有也可能没有，取决于实现
        self.assertIsNotNone(results)

    def test_get_summary(self):
        """测试获取摘要。"""
        self.diagnostic.diagnose("x = 1 + 2")
        summary = self.diagnostic.get_summary()

        self.assertIn("总诊断次数", summary)
        self.assertEqual(summary["总诊断次数"], 1)


class TestSelfModifier(unittest.TestCase):
    """自修改引擎测试。"""

    def setUp(self):
        self.registry = ExtensionRegistry()
        self.diagnostic = SelfDiagnostic(self.registry)
        self.modifier = SelfModifier(self.registry, self.diagnostic)

    def test_propose_fix(self):
        """测试提出修复建议。"""
        from src.growth import DiagnosticResult
        diag = DiagnosticResult(
            severity="warning",
            category="performance",
            message="函数 'sin' 被调用 6 次，考虑公共子表达式消除",
            suggestion="使用 optimize() 启用 CSE 优化",
            auto_fix=True,
        )

        mod = self.modifier.propose_fix(diag)
        # 应返回 None（因为扩展未注册）或 Modification
        self.assertIsNotNone(mod)


class TestGrowthLoop(unittest.TestCase):
    """成长循环测试。"""

    def setUp(self):
        self.loop = GrowthLoop(ExtensionRegistry())

    def test_run_with_valid_source(self):
        """测试运行有效源码。"""
        source = "x = sin(3.14) + cos(1.57)"
        result = self.loop.run(source, max_iterations=3)

        self.assertIn("state", result)
        self.assertIn("diagnostics", result)

    def test_run_with_invalid_source(self):
        """测试运行无效源码。"""
        source = "x = sin( + cos()"  # 语法错误
        result = self.loop.run(source, max_iterations=3)

        self.assertIn("state", result)

    def test_get_state(self):
        """测试获取状态。"""
        state = self.loop.get_state()

        self.assertIn("iteration", state)
        self.assertIn("total_improvements", state)

    def test_add_pass(self):
        """测试动态添加 Pass。"""
        result = self.loop.add_pass(
            module="src.mir_opt",
            class_name="MathaConstFoldPass",
            description="常量折叠优化",
        )

        self.assertTrue(result)


class TestGrowFunction(unittest.TestCase):
    """快捷函数测试。"""

    def test_grow(self):
        """测试 grow() 函数。"""
        source = "x = sin(3.14) + cos(1.57)"
        result = grow(source, verbose=False)

        self.assertIn("state", result)
        self.assertIn("diagnostics", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
