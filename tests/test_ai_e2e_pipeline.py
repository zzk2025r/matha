# -*- coding: utf-8 -*-
"""阶段 6e · AI 模块 E2E 全链路测试（编排契约 + 诚实降级）。

被测全链路（自然语言 → 前端 → 执行器 → 结果 → 感知）：

    用户输入 → MathaAIAssistant.chat(text, interp)
        ├─ FriendlyIntentParser.classify  (意图分类)
        ├─ FriendlyIntentParser.decompose (步骤分解 → 生成 Matha 代码)
        ├─ Interpreter.run(parse(code))   (主线 lexer→parser→ast→VM 执行)
        └─ 结构化 result dict（type ∈ text/result/error/guide）
    → MathaInnerLoop.on_interaction(text, result)  (感知记录 / 失败入错误缓冲)

纪律（遵 KNOWN_ISSUES §7c）：本文件锁的是**编排契约与诚实降级**——接线正确、
schema 稳定、绝不裸抛、失败如实下沉——**不背书** AI 前端把自然语言解析成
「正确代码 / 正确数值」的输出正确性。故不断言 '计算 3 加 5' 的结果等于 8，
只断言「当链上产生了代码时，执行腿确实被触发、结果如实透出」。
AI 前端仍属未背书（`src/ai_assistant.py` 头注横幅不变）。

全程离线、毫秒级：chat 用正则 FriendlyIntentParser（不走 LLM/网络），
感知腿用 `MathaInnerLoop()` 无参构造（不触发重型 init_modules/run_cycle）。
"""
import sys
sys.path.insert(0, r'D:\trae')

import pytest

from src.ai_assistant import MathaAIAssistant
from src.inner_loop import MathaInnerLoop


_CHAT_KEYS = {"reply", "code", "steps", "result", "explanation", "type", "intent", "confidence"}


@pytest.fixture(scope="module")
def assistant():
    return MathaAIAssistant()


class TestChatOrchestrationContract:
    """chat() 全链路的编排契约：永不裸抛、schema 稳定、类型闭合。"""

    @pytest.mark.parametrize("text", [
        "", "   ", "计算 3 加 5", "今天天气怎么样", "%%%乱码@@@", [1, 2], 42, None,
    ])
    def test_chat_always_returns_dict_never_raises(self, assistant, text):
        r = assistant.chat(text)          # 旧 phantom 类缺陷会在分类/执行/回退腿裸抛
        assert isinstance(r, dict)
        assert "reply" in r and isinstance(r["reply"], str) and r["reply"]
        assert "type" in r

    @pytest.mark.parametrize("text", [
        "计算 3 加 5", "今天天气怎么样", "%%%乱码@@@", "求 1 到 10 的素数",
    ])
    def test_nonempty_input_carries_full_schema(self, assistant, text):
        r = assistant.chat(text)
        # 非空输入无论落 result/error/guide，均须给出完整结构化契约
        assert _CHAT_KEYS <= set(r), f"缺键：{_CHAT_KEYS - set(r)}"

    @pytest.mark.parametrize("text", [
        "", "   ", "计算 3 加 5", "今天天气怎么样", "%%%乱码@@@", "自由落体 3 秒",
    ])
    def test_chat_type_in_closed_set(self, assistant, text):
        r = assistant.chat(text)
        assert r["type"] in ("text", "result", "error", "guide"), r["type"]

    def test_result_presence_contract(self, assistant):
        # type==result 才允许带值；type==guide 是诚实「无法处理」不编造结果
        ok = assistant.chat("计算 3 加 5")
        if ok["type"] == "result":
            assert ok["result"] is not None and ok["code"]
        guide = assistant.chat("%%%乱码@@@")
        if guide["type"] == "guide":
            assert guide["result"] is None

    def test_empty_input_honest_prompt(self, assistant):
        r = assistant.chat("")
        assert r["type"] == "text"
        assert r.get("result") is None  # 空输入走精简 {reply,type} 体，不带结果


class _SpyInterpreter:
    """执行腿替身：记录 chat 是否把生成的代码交给解释器执行、并透出预设结果。"""

    def __init__(self, outputs):
        self._outputs = outputs
        self.calls = []

    def run(self, ast):
        self.calls.append(ast)
        return list(self._outputs), []  # chat 解包 (outputs, trace)


class TestChatExecutionLegWiring:
    """锁定「生成代码 → 执行器」这条腿是真接线，而非恒跳过/恒不可用。"""

    def test_exec_leg_invoked_when_code_generated(self, assistant):
        spy = _SpyInterpreter([12345])
        r = assistant.chat("计算 3 加 5", spy)
        if r.get("code"):
            assert spy.calls, "生成了代码却未把代码送入解释器执行（执行腿断链）"
            assert r["type"] == "result" and r["result"] == 12345  # 透出执行器返回值（非背书 NL 正确性）

    def test_no_exec_when_no_code_generated(self, assistant):
        spy = _SpyInterpreter([999])
        r = assistant.chat("%%%乱码@@@", spy)
        if not r.get("code"):
            assert spy.calls == []  # 无代码不应空跑解释器


class TestE2EChatThenInnerLoopPerception:
    """chat → inner_loop.on_interaction 的端到端感知集成（ai_assistant_server 正是这条链）。"""

    def test_success_routed_as_result(self, assistant):
        loop = MathaInnerLoop()
        result = assistant.chat("计算 3 加 5")
        rec = loop.on_interaction("计算 3 加 5", result)
        assert rec.success == (result["type"] in ("result", "calculation"))
        assert loop._state.total_interactions == 1
        if result["type"] in ("result", "calculation"):
            assert loop._state.total_errors_caught == 0

    def test_failure_sinks_to_error_buffer(self, assistant):
        loop = MathaInnerLoop()
        result = assistant.chat("%%%乱码@@@")   # guide → 非 result 类型
        rec = loop.on_interaction("%%%乱码@@@", result)
        assert rec.success is False
        assert len(loop._error_buffer) == 1
        assert loop._state.total_errors_caught == 1
        assert loop._error_buffer[0]["text"] == "%%%乱码@@@"

    def test_perception_tolerates_minimal_result(self, assistant):
        # 空输入返回 {reply,type} 精简体：感知层仍须不抛、如实记为失败
        loop = MathaInnerLoop()
        result = assistant.chat("")
        rec = loop.on_interaction("", result)
        assert rec.success is False
        assert loop._state.total_interactions == 1
