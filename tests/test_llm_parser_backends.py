# -*- coding: utf-8 -*-
"""LLM 意图解析器后端契约锁（阶段 1 · AI 修复，离线 mock，不触网）。

背景：`src/intent/llm_parser.py` 两处历史缺陷使两条后端链从未真通过——
  1. Claude 分支向 Anthropic SDK 传 `response_format`（不支持，必
     TypeError；重试环只清 OpenAI 兼容分支的标志，Claude 分支无条件
     再传，三次全崩后静默降级正则）；
  2. Gemini 分支 `_call_gemini` 直读 `self._gemini_client`，而该属性
     只在 `_get_client()` 里初始化，调用方未经 `_get_client()` →
     必 AttributeError → 静默降级正则。

本文件锁（全部注入假客户端，零网络/零真实 SDK 依赖）：
  - 各后端**请求形状**（Claude 无 response_format、system/messages 正确；
    OpenAI 兼容系 response_format 按模型能力开关；Gemini 走懒初始化）；
  - **重试路径**（response_format 不兼容去参重试、可重试错误指数退避）；
  - **降级契约**（不可重试错误 → 正则兜底，永不裸抛，follow_up 如实标注）；
  - **缓存**（高置信度结果二次调用不再触客户端）。
口径：输出正确性不背书（KNOWN_ISSUES §7c），本锁只固定编排/请求契约。
阶段 3 补锁（第 5 节）：parse() 外层 catch-all 兜底、可重试错误耗尽降级、
兜底意图类型来自分解器映射。
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intent.llm_parser import (  # noqa: E402
    Intent,
    IntentType,
    LLMIntentParser,
)

VALID_JSON = json.dumps({
    "intent_type": "ARITHMETIC",
    "description": "计算 1+2",
    "params": {"a": 1, "b": 2},
    "confidence": 0.9,
    "mir_code": "1 + 2",
})


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """屏蔽 .env 读取（防真实密钥渗入）、重试零等待。"""
    monkeypatch.setattr(LLMIntentParser, "_load_dotenv", staticmethod(lambda: None))
    monkeypatch.setenv("MATHA_LLM_RETRY_DELAY", "0")
    monkeypatch.setenv("MATHA_LLM_MAX_RETRIES", "3")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _parser(tmp_path, model):
    return LLMIntentParser(api_key="test-key", model=model,
                           cache_dir=str(tmp_path / "cache"))


def _anthropic_client(record):
    def create(**kwargs):
        record.append(kwargs)
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=VALID_JSON)])
    return types.SimpleNamespace(
        messages=types.SimpleNamespace(create=create))


def _openai_client(record, fail_first=None):
    def create(**kwargs):
        record.append(kwargs)
        if fail_first is not None and len(record) <= fail_first[0]:
            raise fail_first[1]
        return types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=VALID_JSON))])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)))


def _gemini_fake(record):
    def generate_content(prompt, generation_config=None):
        record.append({"prompt": prompt, "config": generation_config})
        return types.SimpleNamespace(text=VALID_JSON)
    model = types.SimpleNamespace(generate_content=generate_content)
    return types.SimpleNamespace(GenerativeModel=lambda name: model)


# ============================================================
# 1. Claude 请求形状（封死 response_format 必崩）
# ============================================================

class TestClaudeBackend:

    def test_no_response_format_and_correct_shape(self, tmp_path):
        p = _parser(tmp_path, "claude-3-5-sonnet")
        record = []
        p._api_client = _anthropic_client(record)
        intent = p.parse("计算 1+2")
        assert len(record) == 1  # 历史缺陷：TypeError 重试三次全崩
        kw = record[0]
        assert "response_format" not in kw  # Anthropic SDK 不支持
        assert kw["model"] == "claude-3-5-sonnet"
        assert kw["system"] == LLMIntentParser.SYSTEM_PROMPT
        assert kw["messages"] == [{"role": "user", "content":
            LLMIntentParser.USER_PROMPT_TEMPLATE.format(text="计算 1+2")}]
        assert kw["max_tokens"] == 1024
        assert intent.intent_type == IntentType.ARITHMETIC
        assert intent.suggested_code == "1 + 2"
        assert intent.confidence == 0.9
        assert intent.follow_up_questions == []  # 非降级路径


# ============================================================
# 2. Gemini 懒初始化（封死 AttributeError 必崩）
# ============================================================

class TestGeminiBackend:

    def test_call_gemini_initializes_client_lazily(self, tmp_path):
        p = _parser(tmp_path, "gemini-1.5-pro")
        record = []
        p._get_gemini_client = lambda: _gemini_fake(record)
        # 直调 _call_gemini：修复前此处 AttributeError（_gemini_client 未初始化）
        raw = p._call_gemini("用户输入：计算 1+2")
        assert json.loads(raw)["intent_type"] == "ARITHMETIC"
        assert len(record) == 1
        assert LLMIntentParser.SYSTEM_PROMPT in record[0]["prompt"]
        assert record[0]["config"] == {"response_mime_type": "application/json"}

    def test_full_parse_path_via_llm(self, tmp_path):
        p = _parser(tmp_path, "gemini-1.5-flash")
        record = []
        p._get_gemini_client = lambda: _gemini_fake(record)
        intent = p.parse("计算 1+2")
        assert intent.intent_type == IntentType.ARITHMETIC
        assert intent.follow_up_questions == []  # 非降级
        assert len(record) == 1

    def test_missing_sdk_degrades_honestly(self, tmp_path, monkeypatch):
        p = _parser(tmp_path, "gemini-1.5-pro")
        def no_sdk():
            raise ImportError("请安装 google-generativeai")
        monkeypatch.setattr(p, "_get_gemini_client", no_sdk)
        intent = p.parse("计算 1+2")  # 永不裸抛
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions

    def test_missing_key_raises_value_error(self, tmp_path, monkeypatch):
        # 注入假 SDK 模块使 import 成功，才能到达密钥检查分支（本机无真 SDK）
        fake = types.ModuleType("google.generativeai")
        fake.configure = lambda **kw: None
        monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
        monkeypatch.setitem(sys.modules, "google.generativeai", fake)
        p = _parser(tmp_path, "gemini-1.5-pro")
        p._api_key = None
        with pytest.raises(ValueError, match="密钥"):
            p._get_gemini_client()


# ============================================================
# 3. OpenAI 兼容系请求形状与重试
# ============================================================

class TestOpenAICompatible:

    @pytest.mark.parametrize("model,has_format", [
        ("deepseek-chat", True),
        ("gpt-4o", True),
        ("glm-4-flash", True),
        ("chatglm3-6b", False),  # 老版不支持 json_object
    ])
    def test_response_format_by_model_capability(self, tmp_path, model, has_format):
        p = _parser(tmp_path, model)
        record = []
        p._api_client = _openai_client(record)
        intent = p.parse("计算 1+2")
        assert intent.intent_type == IntentType.ARITHMETIC
        kw = record[0]
        assert ("response_format" in kw) is has_format
        if has_format:
            assert kw["response_format"] == {"type": "json_object"}
        assert kw["messages"][0] == {"role": "system",
                                     "content": LLMIntentParser.SYSTEM_PROMPT}
        assert kw["model"] == model

    def test_response_format_incompatible_retries_without_it(self, tmp_path):
        p = _parser(tmp_path, "deepseek-chat")
        record = []
        def create(**kwargs):
            record.append(kwargs)
            if "response_format" in kwargs:
                raise TypeError("unsupported parameter: response_format")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=VALID_JSON))])
        p._api_client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create)))
        intent = p.parse("计算 1+2")
        assert intent.intent_type == IntentType.ARITHMETIC
        assert len(record) == 2
        assert "response_format" in record[0]
        assert "response_format" not in record[1]

    def test_retryable_error_then_success(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(record, fail_first=(1, ConnectionError("connection reset")))
        intent = p.parse("计算 1+2")
        assert intent.intent_type == IntentType.ARITHMETIC
        assert len(record) == 2

    def test_non_retryable_error_degrades_to_regex(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(record, fail_first=(99, ValueError("invalid api key")))
        intent = p.parse("计算 1加2")  # 永不裸抛
        assert len(record) == 1  # 不可重试错误不重试
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions

    def test_invalid_json_response_degrades(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        def create(**kwargs):
            return types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="不是 JSON"))])
        p._api_client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create)))
        intent = p.parse("计算 1加2")
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions


# ============================================================
# 4. 缓存与输入契约
# ============================================================

class TestCacheAndInput:

    def test_high_confidence_cached(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(record)
        first = p.parse("计算 1+2")
        second = p.parse("计算 1+2")
        assert len(record) == 1  # 第二次走缓存
        assert second.intent_type == first.intent_type
        assert second.parse_time_ms == 0.0
        p.clear_cache()
        p.parse("计算 1+2")
        assert len(record) == 2

    def test_empty_input_short_circuits(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(record)
        intent = p.parse("   ")
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0
        assert len(record) == 0  # 空输入不触客户端

    def test_list_input_normalized(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(record)
        intent = p.parse(["计算", "1+2"])
        assert isinstance(intent, Intent)
        assert "计算 1+2" in record[0]["messages"][1]["content"]


# ============================================================
# 5. 阶段 3 · 降级路径契约补锁（外层兜底 + 重试耗尽）
# ============================================================

class TestDegradationContract:
    """第 3 节已锁不可重试错误/无效 JSON 降级；本节补两条未覆盖路径：
    parse() 外层 catch-all（_call_llm 整体意外爆炸）与可重试错误耗尽。
    契约：永不裸抛、兜底标记如实、suggested_code 来自分解器。"""

    def test_outer_catchall_falls_back(self, tmp_path, monkeypatch):
        p = _parser(tmp_path, "gpt-4o")

        def boom(text):
            raise RuntimeError("意外爆炸")
        monkeypatch.setattr(p, "_call_llm", boom)
        intent = p.parse("计算 1加2")  # 外层 catch-all 兜底，永不裸抛
        assert isinstance(intent, Intent)
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions
        assert intent.description == "计算 1加2"
        assert isinstance(intent.suggested_code, str)

    def test_retry_exhaustion_falls_back(self, tmp_path):
        p = _parser(tmp_path, "gpt-4o")
        record = []
        p._api_client = _openai_client(
            record, fail_first=(99, ConnectionError("connection reset")))
        intent = p.parse("计算 1加2")
        assert len(record) == 3  # 可重试错误打满 MATHA_LLM_MAX_RETRIES=3
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions
        assert isinstance(intent.suggested_code, str)

    def test_degraded_intent_type_maps_from_decomposer(self, tmp_path, monkeypatch):
        # 兜底意图类型来自 IntentDecomposer 节点映射，而非恒 UNKNOWN
        p = _parser(tmp_path, "gpt-4o")

        def down(text):
            raise RuntimeError("down")
        monkeypatch.setattr(p, "_call_llm", down)
        intent = p.parse("计算 1加2")
        assert intent.intent_type == IntentType.ARITHMETIC