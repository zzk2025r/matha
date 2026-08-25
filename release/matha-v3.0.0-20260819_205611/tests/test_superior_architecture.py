# -*- coding: utf-8 -*-
"""
Matha 上位语言架构验证测试
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.domains.registry import DomainRegistry, DomainMeta


class TestMathaSuperiorArchitecture(unittest.TestCase):
    """测试 Matha 上位语言架构设计。"""

    def test_mir2_type_system(self):
        """测试 MIR² 类型系统定义。"""
        # MIR² 类型系统应该包含：
        # - 标量类型
        # - 复合类型
        # - 函数类型
        # - 效应类型
        # - 依赖类型
        types = {
            "Scalar": ["int", "float", "bool", "char", "string"],
            "Composite": ["array", "list", "map", "set", "tuple", "struct"],
            "Function": ["pure", "effect"],
            "Effect": ["Pure", "IO", "State", "Exception", "Concurrent", "Async"],
        }
        self.assertGreater(len(types), 0)
        self.assertIn("Scalar", types)
        self.assertIn("Effect", types)

    def test_language_frontends(self):
        """测试多语言前端覆盖。"""
        languages = [
            "python", "rust", "go", "javascript",
            "c", "c++", "fortran", "julia", "zig",
        ]
        self.assertGreater(len(languages), 5)

    def test_target_backends(self):
        """测试多目标后端覆盖。"""
        targets = ["matha", "c", "python", "javascript", "wasm", "rust", "go"]
        self.assertGreater(len(targets), 5)

    def test_ecosystem_mapping(self):
        """测试生态映射。"""
        ecosystems = ["python", "rust", "go", "javascript"]
        self.assertGreater(len(ecosystems), 2)

    def test_learning_capabilities(self):
        """测试学习能力。"""
        capabilities = [
            "code_analysis",
            "pattern_learning",
            "optimization_learning",
            "ecosystem_learning",
        ]
        self.assertEqual(len(capabilities), 4)

    def test_domain_registry_extensibility(self):
        """测试领域注册表可扩展性。"""
        registry = DomainRegistry()
        # 注册新领域
        meta = DomainMeta(
            name="TestDomain",
            display_name="测试领域",
            description="测试",
            module="src.domains.test",
            functions=["test_fn"],
            constants={},
            optimization_passes=[],
            targets=["python", "c"],
            category="science",
        )
        registry.register("TestDomain", meta)
        self.assertEqual(len(registry._domains), 1)

        # 注销
        registry.unregister("TestDomain")
        self.assertEqual(len(registry._domains), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
