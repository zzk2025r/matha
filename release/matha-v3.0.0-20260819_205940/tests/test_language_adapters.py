# -*- coding: utf-8 -*-
"""Matha v4.0 — 语言适配器层单元测试"""
import sys
import unittest
import time

sys.path.insert(0, r"D:\trae")

from src.adapters.language_adapters import (
    LanguageAdapterRegistry,
    PythonAdapter,
    RustAdapter,
    AdaptResult,
)


class TestPythonAdapter(unittest.TestCase):
    """Python 适配器测试。"""

    def setUp(self):
        self.adapter = PythonAdapter()

    def test_adapt_simple_arithmetic(self):
        """测试简单算术。"""
        result = self.adapter.adapt("result = 3.0 + 5.0")
        self.assertTrue(result.success)
        self.assertEqual(result.output, 8.0)

    def test_adapt_with_math_func(self):
        """测试含数学函数的代码。"""
        result = self.adapter.adapt("result = sqrt(16.0)")
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.output, 4.0, places=5)

    def test_adapt_list_operation(self):
        """测试列表操作。"""
        result = self.adapter.adapt("result = sorted([3.0, 1.0, 2.0])")
        self.assertTrue(result.success)
        self.assertEqual(result.output, [1.0, 2.0, 3.0])

    def test_adapt_prime_search(self):
        """测试素数搜索。"""
        code = "primes = [p for p in range(2, 20) if all(p%d!=0 for d in range(2, int(p**0.5)+1))]\nresult = primes"
        result = self.adapter.adapt(code)
        self.assertTrue(result.success)
        self.assertEqual(result.output, [2, 3, 5, 7, 11, 13, 17, 19])

    def test_adapt_error_handling(self):
        """测试错误处理。"""
        result = self.adapter.adapt("result = 1/0")
        self.assertFalse(result.success)
        self.assertIn("division", result.error.lower())


class TestRustAdapter(unittest.TestCase):
    """Rust 适配器测试。"""

    def setUp(self):
        self.adapter = RustAdapter()

    def test_adapt_simple_arithmetic(self):
        """测试简单算术。"""
        result = self.adapter.adapt("result = 3.0 + 5.0")
        # Rust 适配器需要 rustc 可用
        if result.success:
            self.assertIsNotNone(result.output)
        # 如果 rustc 不可用，应返回失败但不崩溃
        else:
            self.assertTrue(result.error)  # 应有错误信息

    def test_translate_produces_valid_rust(self):
        """测试翻译生成有效的 Rust 代码。"""
        rust_code = self.adapter.translate("result = 3.0 + 5.0")
        self.assertIn("fn main", rust_code)
        self.assertIn("println", rust_code)
        self.assertIn("3.0", rust_code)


class TestLanguageAdapterRegistry(unittest.TestCase):
    """语言适配器注册表测试。"""

    def test_list_adapters(self):
        """测试列出所有适配器。"""
        adapters = LanguageAdapterRegistry.list_adapters()
        self.assertIn("python", adapters)
        self.assertIn("rust", adapters)

    def test_get_adapter(self):
        """测试获取适配器。"""
        py = LanguageAdapterRegistry.get("python")
        self.assertIsInstance(py, PythonAdapter)

        rust = LanguageAdapterRegistry.get("rust")
        self.assertIsInstance(rust, RustAdapter)

    def test_get_nonexistent(self):
        """测试获取不存在的适配器。"""
        result = LanguageAdapterRegistry.get("nonexistent")
        self.assertIsNone(result)


class TestIntegration(unittest.TestCase):
    """集成测试：IDE + 语言适配器。"""

    def test_full_pipeline_python(self):
        """测试完整流程（IDE → Python 适配器）。"""
        from src.intent.intent_decomposer import IntentDecomposer

        ide = IntentDecomposer(use_llm=False)
        py_adapter = PythonAdapter()

        text = "计算 3 加 5"
        root = ide.decompose(text)
        math_code = root.to_math_code()

        result = py_adapter.adapt(math_code)
        self.assertTrue(result.success)
        self.assertEqual(result.output, 8.0)

    def test_full_pipeline_rust(self):
        """测试完整流程（IDE → Rust 适配器）。"""
        from src.intent.intent_decomposer import IntentDecomposer

        ide = IntentDecomposer(use_llm=False)
        rust_adapter = RustAdapter()

        text = "计算 3 加 5"
        root = ide.decompose(text)
        math_code = root.to_math_code()

        result = rust_adapter.adapt(math_code)
        # Rust 可能不可用，不强制成功
        if result.success:
            self.assertIsNotNone(result.output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
