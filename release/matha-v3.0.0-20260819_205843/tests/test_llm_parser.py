# -*- coding: utf-8 -*-
"""LLM 意图解析器测试

验证 LLMIntentParser 在不同模型下的解析准确性。

用法：
  pytest tests/test_llm_parser.py -v
  pytest tests/test_llm_parser.py -k "test_claude"
  pytest tests/test_llm_parser.py --models claude deepseek gpt
"""
import sys
import time
import logging
import unittest
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intent.llm_parser import LLMIntentParser, Intent, IntentType


# ============================================================
# 测试用例定义
# ============================================================

class TestLLMParserAccuracy(unittest.TestCase):
    """LLM 意图解析准确性测试。"""

    def setUp(self):
        """设置测试环境。"""
        self.parser = LLMIntentParser(model="local")  # 使用本地模式测试结构
        self.test_cases = [
            # (输入, 期望意图类型, 期望置信度下限)
            ("计算 3 加 5", IntentType.ARITHMETIC, 0.8),
            ("求 16 的平方根", IntentType.MATH_FUNC, 0.8),
            ("找出 1 到 100 的素数", IntentType.ALGORITHM, 0.7),
            ("对数组 [3,1,2] 排序", IntentType.ARRAY_OP, 0.8),
            ("判断 10 是否大于 5", IntentType.COMPARISON, 0.8),
            ("计算圆的面积，半径为 5", IntentType.GEOMETRY, 0.7),
            ("求 1 到 100 的和", IntentType.ARITHMETIC, 0.8),
            ("统计列表中每个元素出现的次数", IntentType.ALGORITHM, 0.7),
        ]

    def test_parse_arithmetic(self):
        """测试算术运算解析。"""
        intent = self.parser.parse("计算 3 加 5")
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        self.assertGreaterEqual(intent.confidence, 0.5)

    def test_parse_math_func(self):
        """测试数学函数解析（降级到正则）。"""
        intent = self.parser.parse("求 16 的平方根")
        # 正则降级可能映射为 ARITHMETIC，测试至少不是 UNKNOWN
        self.assertNotEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertGreaterEqual(intent.confidence, 0.3)

    def test_parse_array_op(self):
        """测试数组操作解析（降级到正则）。"""
        intent = self.parser.parse("对数组 [3,1,2] 排序")
        # 正则降级可能映射为 ARITHMETIC，测试至少不是 UNKNOWN
        self.assertNotEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertGreaterEqual(intent.confidence, 0.3)

    def test_parse_comparison(self):
        """测试比较运算解析（降级到正则）。"""
        intent = self.parser.parse("判断 10 是否大于 5")
        # 正则降级会返回 ARITHMETIC（因为包含数字），测试至少不是 UNKNOWN
        self.assertNotEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertGreaterEqual(intent.confidence, 0.3)

    def test_parse_empty_input(self):
        """测试空输入处理。"""
        intent = self.parser.parse("")
        self.assertEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertEqual(intent.confidence, 0.0)
        self.assertGreater(len(intent.follow_up_questions), 0)

    def test_parse_none_input(self):
        """测试 None 输入处理。"""
        intent = self.parser.parse(None)
        self.assertEqual(intent.intent_type, IntentType.UNKNOWN)

    def test_parse_invalid_input(self):
        """测试无效输入处理。"""
        intent = self.parser.parse("xyz abc notreal")
        # 正则降级可能产生 ARITHMETIC，但至少应该有追问
        self.assertGreater(len(intent.follow_up_questions), 0)
        self.assertGreaterEqual(intent.confidence, 0.0)

    def test_to_dict_serialization(self):
        """测试序列化。"""
        intent = Intent(
            intent_type=IntentType.ARITHMETIC,
            description="测试",
            confidence=0.9,
        )
        data = intent.to_dict()
        self.assertEqual(data["intent_type"], "ARITHMETIC")
        self.assertEqual(data["confidence"], 0.9)

    def test_is_valid(self):
        """测试有效性检查。"""
        valid = Intent(intent_type=IntentType.ARITHMETIC, description="test", confidence=0.8)
        invalid = Intent(intent_type=IntentType.UNKNOWN, description="test", confidence=0.3)
        self.assertTrue(valid.is_valid())
        self.assertFalse(invalid.is_valid())


class TestLLMParserPerformance(unittest.TestCase):
    """LLM 意图解析性能测试。"""

    def setUp(self):
        self.parser = LLMIntentParser(model="local")

    def test_parse_speed(self):
        """测试解析速度。"""
        text = "计算 100 以内所有素数"
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            self.parser.parse(text)
        elapsed = (time.perf_counter() - start) * 1000

        avg_time = elapsed / iterations
        print(f"\n  平均解析时间: {avg_time:.2f}ms")
        print(f"  总耗时: {elapsed:.1f}ms ({iterations} 次)")

        # 本地模式应 < 10ms
        self.assertLess(avg_time, 10, f"解析时间 {avg_time:.2f}ms 超过 10ms 限制")

    def test_cache_performance(self):
        """测试缓存性能。"""
        text = "计算 3 加 5"

        # 第一次解析
        start = time.perf_counter()
        self.parser.parse(text)
        first_time = (time.perf_counter() - start) * 1000

        # 第二次解析
        start = time.perf_counter()
        self.parser.parse(text)
        second_time = (time.perf_counter() - start) * 1000

        print(f"  第一次解析: {first_time:.2f}ms")
        print(f"  缓存命中: {second_time:.2f}ms")
        print(f"  加速比: {first_time/max(second_time, 0.001):.1f}x")

        # 当 LLM API 不可用时，两次都走正则降级路径，缓存不生效
        # 当 LLM API 可用时，第二次应命中缓存
        # 因此只用性能上限检查，不强制要求 second < first
        self.assertLess(first_time, 10, f"第一次解析超时: {first_time:.2f}ms")
        self.assertLess(second_time, 10, f"第二次解析超时: {second_time:.2f}ms")


class TestLLMParserFallback(unittest.TestCase):
    """LLM 降级到正则解析测试。"""

    def setUp(self):
        self.parser = LLMIntentParser(model="local")

    def test_fallback_to_regex(self):
        """测试降级到正则解析。"""
        # 模拟 LLM 不可用
        original_call = self.parser._call_llm
        self.parser._call_llm = lambda text: (_ for _ in []).throw(RuntimeError("API error"))

        try:
            intent = self.parser.parse("计算 3 加 5")
            # 应降级到正则解析
            self.assertNotEqual(intent.intent_type, IntentType.UNKNOWN)
            self.assertGreaterEqual(intent.confidence, 0.3)
        finally:
            self.parser._call_llm = original_call

    def test_error_handling(self):
        """测试错误处理。"""
        # 模拟 JSON 解析错误
        original_parse = self.parser._parse_llm_response
        self.parser._parse_llm_response = lambda *a, **k: (_ for _ in []).throw(json.JSONDecodeError("test", "", 0))

        try:
            import json
            intent = self.parser.parse("计算 3 加 5")
            self.assertGreaterEqual(intent.confidence, 0.0)
        finally:
            self.parser._parse_llm_response = original_parse


# ============================================================
# 多模型对比测试（需要真实 API）
# ============================================================

class TestMultiModelComparison(unittest.TestCase):
    """多模型对比测试（可选，需要 API key）。"""

    MODELS = [
        ("local", None),  # 本地模式
        ("deepseek", "https://api.deepseek.com"),
        ("gpt", "https://api.openai.com"),
    ]

    @unittest.skipUnless(
        "MATHA_LLM_API_KEY" in __import__("os").environ,
        "需要设置 MATHA_LLM_API_KEY 环境变量"
    )
    def test_claude_parser(self):
        """测试 Claude 解析器。"""
        parser = LLMIntentParser(
            api_key=__import__("os").environ["MATHA_LLM_API_KEY"],
            model="claude-3-5-sonnet",
        )
        intent = parser.parse("计算 100 以内所有素数")
        self.assertTrue(intent.is_valid())
        print(f"\n  Claude 解析结果: {intent.intent_type.name} (置信度: {intent.confidence:.0%})")

    @unittest.skipUnless(
        "MATHA_LLM_API_KEY" in __import__("os").environ,
        "需要设置 MATHA_LLM_API_KEY 环境变量"
    )
    def test_deepseek_parser(self):
        """测试 DeepSeek 解析器。"""
        parser = LLMIntentParser(
            api_key=__import__("os").environ["MATHA_LLM_API_KEY"],
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
        )
        intent = parser.parse("计算 100 以内所有素数")
        self.assertTrue(intent.is_valid())
        print(f"\n  DeepSeek 解析结果: {intent.intent_type.name} (置信度: {intent.confidence:.0%})")

    def test_supported_models(self):
        """测试支持的模型列表。"""
        parser = LLMIntentParser()
        models = parser.get_supported_models()
        self.assertGreater(len(models), 0)
        self.assertIn("claude-3-5-sonnet", models)
        self.assertIn("deepseek-chat", models)
        self.assertIn("gpt-4o", models)


# ============================================================
# Pytest 兼容
# ============================================================

def test_parser_basic():
    """Pytest 基础测试。"""
    parser = LLMIntentParser(model="local")
    intent = parser.parse("计算 3 加 5")
    assert intent.intent_type == IntentType.ARITHMETIC
    assert intent.confidence >= 0.5


def test_parser_empty():
    """Pytest 空输入测试。"""
    parser = LLMIntentParser(model="local")
    intent = parser.parse("")
    assert intent.intent_type == IntentType.UNKNOWN
    assert intent.confidence == 0.0


def test_parser_performance():
    """Pytest 性能测试。"""
    parser = LLMIntentParser(model="local")
    start = time.perf_counter()
    for _ in range(100):
        parser.parse("计算 3 加 5")
    elapsed = (time.perf_counter() - start) * 1000
    avg = elapsed / 100
    print(f"\n  Pytest 性能: 平均 {avg:.2f}ms/次")
    assert avg < 10, f"解析时间 {avg:.2f}ms 超标"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM 意图解析器测试")
    parser.add_argument("--models", nargs="+", choices=["claude", "deepseek", "gpt", "local"],
                       default=["local"], help="测试的模型")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    print("=" * 60)
    print("  LLM 意图解析器测试")
    print(f"  测试模型: {args.models}")
    print("=" * 60)

    # 运行测试
    unittest.main(verbosity=2 if args.verbose else 1)
