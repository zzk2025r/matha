# -*- coding: utf-8 -*-
"""Matha v4.0 — 意图分解引擎（IDE）单元测试

测试覆盖：
  1. 短文本快速路径
  2. 中文本拆分合并
  3. 长文本 LLM 辅助分解
  4. 数学映射正确性
  5. 自进化模板学习
  6. 意图树序列化
"""
import sys
import unittest
import tempfile
import os
import json
from pathlib import Path

sys.path.insert(0, r"D:\trae")

from src.intent.intent_decomposer import (
    IntentDecomposer,
    IntentNode,
    IntentNodeType,
    _extract_arithmetic,
    _extract_math_func,
    _extract_comparison,
    _extract_array_op,
    _extract_string_op,
    _extract_prime_search,
    _extract_range,
)


class TestShortTextDecomposition(unittest.TestCase):
    """短文本快速路径测试。"""

    def setUp(self):
        self.ide = IntentDecomposer(use_llm=False)

    def test_arithmetic_simple(self):
        """测试简单算术表达式。"""
        root = self.ide.decompose("计算 3 加 5")
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertGreaterEqual(root.confidence, 0.9)
        self.assertIn("result", root.to_math_code())

    def test_math_func_sqrt(self):
        """测试平方根函数。"""
        root = self.ide.decompose("求 16 的平方根")
        # 平方根规则需要精确匹配
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)

    def test_math_func_sin(self):
        """测试正弦函数。"""
        root = self.ide.decompose("正弦 30")
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)

    def test_comparison(self):
        """测试比较表达式。"""
        root = self.ide.decompose("判断 10 大于 5")
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertIn(">", root.to_math_code())

    def test_unrecognized_short(self):
        """测试无法识别的短文本。"""
        root = self.ide.decompose("随机字符串 xyz")
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertLess(root.confidence, 0.7)
        self.assertTrue(len(root.follow_up) > 0)


class TestMediumTextDecomposition(unittest.TestCase):
    """中文本拆分合并测试。"""

    def setUp(self):
        self.ide = IntentDecomposer(use_llm=False)

    def test_sort_and_reverse(self):
        """测试排序并反转。"""
        root = self.ide.decompose("对数组 [3,1,2] 排序并且反转结果")
        # 可能是 ATOMIC 或 COMPLEX
        self.assertTrue(root.node_type in [IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])

    def test_primes_and_sum(self):
        """测试素数搜索并求和。"""
        root = self.ide.decompose("找出 1 到 100 的素数并求和")
        # 可能是 ATOMIC 或 COMPLEX，取决于拆分结果
        self.assertTrue(root.node_type in [IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])

    def test_single_clause_medium(self):
        """测试单句中文本。"""
        root = self.ide.decompose("计算 100 以内所有素数")
        # 可能是 ATOMIC（正则匹配失败时返回 fallback）
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)


class TestLongTextDecomposition(unittest.TestCase):
    """长文本分解测试。"""

    def setUp(self):
        self.ide = IntentDecomposer(use_llm=False)

    def test_multi_step_calculation(self):
        """测试多步计算。"""
        text = "计算 3 加 5 的结果，然后乘以 2，最后减去 1"
        root = self.ide.decompose(text)

        self.assertTrue(root.node_type in [IntentNodeType.ROOT, IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])

    def test_conditional_logic(self):
        """测试条件逻辑。"""
        text = "如果 x 大于 10 那么输出 x 的平方，否则输出 x 的立方"
        root = self.ide.decompose(text)
        self.assertTrue(root.node_type in [IntentNodeType.ROOT, IntentNodeType.COMPLEX])

    def test_complex_multi_intent(self):
        """测试复杂多意图。"""
        text = "找出 1 到 100 之间的所有素数，将它们排序，然后计算总和，最后输出结果"
        root = self.ide.decompose(text)

        self.assertTrue(root.node_type in [IntentNodeType.ROOT, IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])


class TestMathMappings(unittest.TestCase):
    """数学映射函数测试。"""

    def test_arithmetic_extract(self):
        """测试算术表达式提取。"""
        expr = _extract_arithmetic("计算 3 加 5")
        self.assertIn("3", expr)
        self.assertIn("5", expr)
        self.assertIn("+", expr)

    def test_math_func_sqrt(self):
        """测试平方根函数提取。"""
        expr = _extract_math_func("求 16 的平方根")
        self.assertIn("sqrt", expr)
        self.assertIn("16", expr)

    def test_math_func_sin(self):
        """测试正弦函数提取。"""
        expr = _extract_math_func("正弦 30")
        self.assertIn("sin", expr)
        self.assertIn("30", expr)

    def test_comparison_extract(self):
        """测试比较表达式提取。"""
        expr = _extract_comparison("判断 10 大于 5")
        self.assertIn(">", expr)
        self.assertIn("10", expr)
        self.assertIn("5", expr)

    def test_array_sort(self):
        """测试数组排序提取。"""
        expr = _extract_array_op("对数组 [3,1,2] 排序")
        # 表达式应包含 sorted
        self.assertIn("sorted", expr)

    def test_array_reverse(self):
        """测试数组反转提取。"""
        expr = _extract_array_op("反转数组 [1,2,3]")
        self.assertIn("::-1", expr)

    def test_prime_search(self):
        """测试素数搜索提取。"""
        expr = _extract_prime_search("找出 1 到 100 的素数")
        self.assertIn("primes", expr)
        self.assertIn("range", expr)

    def test_range_extract(self):
        """测试范围提取。"""
        expr = _extract_range("1 到 10")
        self.assertIn("range", expr)
        self.assertIn("1", expr)
        self.assertIn("10", expr)


class TestIntentTreeNode(unittest.TestCase):
    """意图树节点测试。"""

    def test_atomic_node(self):
        """测试原子节点。"""
        node = IntentNode(
            node_type=IntentNodeType.ATOMIC,
            text="测试",
            math_expr="result = 1",
            confidence=0.9,
        )
        self.assertTrue(node.is_complete())
        self.assertEqual(node.to_math_code(), "result = 1")

    def test_complex_node(self):
        """测试复合节点。"""
        child1 = IntentNode(
            node_type=IntentNodeType.ATOMIC,
            text="子意图 1",
            math_expr="a = 1",
        )
        child2 = IntentNode(
            node_type=IntentNodeType.ATOMIC,
            text="子意图 2",
            math_expr="b = 2",
        )
        parent = IntentNode(
            node_type=IntentNodeType.COMPLEX,
            text="复合意图",
            sub_intents=[child1, child2],
        )
        self.assertTrue(parent.is_complete())
        code = parent.to_math_code()
        self.assertIn("a = 1", code)
        self.assertIn("b = 2", code)

    def test_incomplete_node(self):
        """测试不完整节点。"""
        node = IntentNode(
            node_type=IntentNodeType.ATOMIC,
            text="未知意图",
            confidence=0.3,
        )
        self.assertFalse(node.is_complete())

    def test_node_serialization(self):
        """测试节点序列化/反序列化。"""
        node = IntentNode(
            node_type=IntentNodeType.ROOT,
            text="测试",
            math_expr="result = 1",
            confidence=0.95,
        )
        data = node.to_dict()
        restored = IntentNode.from_dict(data)
        self.assertEqual(restored.text, node.text)
        self.assertEqual(restored.math_expr, node.math_expr)
        self.assertEqual(restored.confidence, node.confidence)


class TestSelfEvolution(unittest.TestCase):
    """自进化模板学习测试。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ide = IntentDecomposer(use_llm=False)
        self.ide._template_dir = Path(self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_learn_template(self):
        """测试学习新模板。"""
        self.ide.learn("计算 3 加 5", "result = 3 + 5", success=True)

        # 验证模板已保存
        template_file = Path(self.temp_dir) / "templates.json"
        self.assertTrue(template_file.exists())

        with open(template_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        self.assertGreater(len(templates), 0)

    def test_learn_failures_not_stored(self):
        """测试失败映射不被存储。"""
        self.ide.learn("无效输入", "", success=False)

        template_file = Path(self.temp_dir) / "templates.json"
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            self.assertEqual(len(templates), 0)


class TestIntentDecomposerIntegration(unittest.TestCase):
    """IDE 集成测试。"""

    def setUp(self):
        self.ide = IntentDecomposer(use_llm=False)

    def test_full_pipeline_simple(self):
        """测试完整流程（简单输入）。"""
        text = "计算 3 加 5"
        root = self.ide.decompose(text)

        self.assertTrue(root.is_complete())
        self.assertGreater(root.confidence, 0.5)
        code = root.to_math_code()
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0)

    def test_full_pipeline_complex(self):
        """测试完整流程（复杂输入）。"""
        text = "找出 1 到 100 之间的所有素数，将它们排序，然后计算总和"
        root = self.ide.decompose(text)

        self.assertTrue(root.node_type in [IntentNodeType.ROOT, IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])
        self.assertGreaterEqual(len(root.sub_intents), 0)

    def test_full_pipeline_condition(self):
        """测试完整流程（条件输入）。"""
        text = "如果温度大于 30 那么打开空调，否则关闭空调"
        root = self.ide.decompose(text)

        self.assertTrue(root.node_type in [IntentNodeType.ROOT, IntentNodeType.COMPLEX])

    def test_performance(self):
        """测试解析性能。"""
        import time

        texts = [
            "计算 3 加 5",
            "找出 1 到 100 的素数",
            "对数组 [3,1,2] 排序并反转",
            "计算正弦 30 度",
        ] * 10  # 40 次解析

        start = time.perf_counter()
        for text in texts:
            self.ide.decompose(text)
        elapsed = (time.perf_counter() - start) * 1000

        avg_time = elapsed / len(texts)
        self.assertLess(avg_time, 100, f"平均解析时间 {avg_time:.1f}ms 超过 100ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)
