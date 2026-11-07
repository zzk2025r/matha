# -*- coding: utf-8 -*-
"""MathaSystem AI/LSP/MCP 接口死接线修复锁（阶段 1 · AI 修复）。

背景：`src/matha_system.py` 三个接口方法历史上调用不存在的方法——
  - `ai_eval` → `ai_assistant.eval()`（真实入口是 `chat() -> dict`）；
  - `lsp_start` → `MathaLSP.start()`（MathaLSP 只有进程内分析 API，
    仓库从无 LSP 协议线服务）；
  - `mcp_start` → `mcp_server.start()`（真实入口是 create_server() +
    run_stdio_async()）。
审计原登记「两处」，本轮核实为三处（lsp_start 同形）。

本文件锁：ai_eval 真接 chat 并取 reply；lsp_start 显式拒绝不伪装启动；
mcp_start 真接 stdio 服务且缺 SDK 诚实 ImportError。
用 __new__ 轻量构造避开全量子系统初始化（被测方法只读三个属性）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.matha_system import MathaSystem  # noqa: E402


def _bare_system() -> MathaSystem:
    s = MathaSystem.__new__(MathaSystem)
    s.ai_assistant = None
    s.lsp_server = None
    s.mcp_server = None
    return s


# ============================================================
# 1. ai_eval → chat()["reply"]
# ============================================================

class TestAiEval:

    def test_wires_to_chat_and_extracts_reply(self):
        s = _bare_system()
        calls = []
        class FakeAssistant:
            def chat(self, text):
                calls.append(text)
                return {"reply": "回复正文", "type": "text"}
        s.ai_assistant = FakeAssistant()
        assert s.ai_eval("计算 3 加 5") == "回复正文"
        assert calls == ["计算 3 加 5"]

    def test_real_assistant_returns_str_not_attributeerror(self):
        from src.ai_assistant import MathaAIAssistant
        s = _bare_system()
        s.ai_assistant = MathaAIAssistant()
        out = s.ai_eval("计算 3 加 5")  # 修复前：AttributeError: eval
        assert isinstance(out, str) and out
        # 输出正确性不背书（§7c），此处只锁接线契约

    def test_no_assistant_falls_back_to_eval(self):
        s = _bare_system()
        s.eval = lambda text: f"eval:{text}"
        assert s.ai_eval("1+1") == "eval:1+1"


# ============================================================
# 2. lsp_start 显式拒绝（无协议线服务，不伪装启动）
# ============================================================

class TestLspStart:

    def test_rejects_even_when_lsp_object_present(self):
        s = _bare_system()
        started = []
        class FakeLSP:
            def start(self):
                started.append(True)
        s.lsp_server = FakeLSP()
        with pytest.raises(NotImplementedError, match="LSP"):
            s.lsp_start()
        assert started == []  # 不得再调不存在/无背书的方法

    def test_rejects_when_absent(self):
        s = _bare_system()
        with pytest.raises(NotImplementedError):
            s.lsp_start()


# ============================================================
# 3. mcp_start → create_server() + run_stdio_async()
# ============================================================

class TestMcpStart:

    def test_wires_to_real_stdio_entry(self, monkeypatch):
        import src.mcp_server as ms
        ran = []
        class FakeServer:
            async def run_stdio_async(self):
                ran.append(True)
        monkeypatch.setattr(ms, "create_server", lambda: FakeServer())
        s = _bare_system()
        s.mcp_start()  # 修复前：AttributeError: start
        assert ran == [True]

    def test_missing_sdk_propagates_importerror(self, monkeypatch):
        import src.mcp_server as ms
        monkeypatch.setattr(ms, "MCP_AVAILABLE", False)
        s = _bare_system()
        with pytest.raises(ImportError, match="pip install mcp"):
            s.mcp_start()