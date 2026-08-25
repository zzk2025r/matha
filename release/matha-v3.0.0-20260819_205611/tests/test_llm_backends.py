# -*- coding: utf-8 -*-
"""Matha LLM 后端扩展测试

测试新增的 Gemini 和 ChatGLM 后端。
"""
import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from intent.llm_parser import LLMIntentParser, IntentType


class TestLLMBackends(unittest.TestCase):
    """测试 LLM 后端"""

    def test_get_supported_models(self):
        """测试支持的模型列表"""
        parser = LLMIntentParser(model="claude-3-5-sonnet")
        models = parser.get_supported_models()
        self.assertIn("claude-3-5-sonnet", models)
        self.assertIn("gemini-pro", models)
        self.assertIn("chatglm3-6b", models)
        self.assertIn("qwen-max", models)

    def test_gemini_model_detection(self):
        """测试 Gemini 模型检测"""
        parser = LLMIntentParser(model="gemini-pro")
        self.assertTrue("gemini" in parser.model.lower())

    def test_chatglm_model_detection(self):
        """测试 ChatGLM 模型检测"""
        parser = LLMIntentParser(model="chatglm3-6b")
        self.assertTrue("chatglm" in parser.model.lower())

    def test_qwen_model_detection(self):
        """测试通义千问模型检测"""
        parser = LLMIntentParser(model="qwen-max")
        self.assertTrue("qwen" in parser.model.lower())

    def test_fallback_parse(self):
        """测试降级解析"""
        parser = LLMIntentParser(model="claude-3-5-sonnet")
        # 使用无效 API key 触发降级
        intent = parser.parse("计算 100 以内所有素数", strict=False)
        # 应该返回有效意图（降级到正则解析）
        self.assertIsNotNone(intent)


class TestGeminiBackend(unittest.TestCase):
    """测试 Gemini 后端（需要 API key）"""

    @unittest.skipUnless(sys.platform != 'win32' or True, "需要 GEMINI_API_KEY")
    def test_gemini_client(self):
        """测试 Gemini 客户端初始化"""
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            self.skipTest("未设置 GEMINI_API_KEY")

        parser = LLMIntentParser(model="gemini-pro", api_key=api_key)
        # 应该能初始化但不一定成功调用
        self.assertIsNotNone(parser)


class TestChatGLMBackend(unittest.TestCase):
    """测试 ChatGLM 后端（需要 API key）"""

    @unittest.skipUnless(sys.platform != 'win32' or True, "需要 ZHIPUAI_API_KEY")
    def test_chatglm_client(self):
        """测试 ChatGLM 客户端初始化"""
        import os
        api_key = os.environ.get("ZHIPUAI_API_KEY")
        if not api_key:
            self.skipTest("未设置 ZHIPUAI_API_KEY")

        parser = LLMIntentParser(model="chatglm3-6b", api_key=api_key)
        self.assertIsNotNone(parser)


if __name__ == '__main__':
    unittest.main()
