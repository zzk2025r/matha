# -*- coding: utf-8 -*-
"""阶段 3 · 三个 AI server 冒烟测试 + 桌面启动接线锁（离线、毫秒级）。

被测对象与口径（KNOWN_ISSUES §7c：HTTP 层不背书 NL→答案正确性）：
  - src/ai_assistant_server.py：REST 层状态码/schema/CORS/错误下沉；
    chat 走离线正则 FriendlyIntentParser，感知腿用轻量 MathaInnerLoop
    （init_modules 置空——重型模块初始化不属本冒烟锁范围）。
  - src/openai_compat_server.py：OpenAI 兼容形状（models/completions/
    chat.completion/SSE 伪流式 + [DONE]）、chat 异常 → 200 错误透出的
    诚实降级契约。真流式/鉴权属阶段 4，不在本锁主张。
  - src/ai_assistant_desktop.py：launch_desktop 接线（假 HTTPServer/
    webbrowser/睡眠注入，不开浏览器不占 8080）。

全部在本进程起 ThreadingHTTPServer 端口 0（系统自动分配），不走 main()
（避免写 ~/.matha_port.json 注册表），网络仅 127.0.0.1 环回。
"""
from __future__ import annotations

import json
import sys
import threading
import types
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _request(server, method, path, body=None, raw_body=None):
    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    data = raw_body if raw_body is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8")


@pytest.fixture()
def assistant_server(monkeypatch):
    from src.ai_assistant_server import APIHandler
    from src.inner_loop import MathaInnerLoop
    loop = MathaInnerLoop()
    monkeypatch.setattr(loop, "init_modules", lambda: None)
    monkeypatch.setattr("src.ai_assistant_server.get_inner_loop", lambda: loop)
    server = ThreadingHTTPServer(("127.0.0.1", 0), APIHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server, loop
    server.shutdown()
    server.server_close()


@pytest.fixture()
def compat_server():
    from src.openai_compat_server import OpenAICompatHandler
    server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAICompatHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


# ============================================================
# 1. ai_assistant_server（REST 层）
# ============================================================

class TestAssistantServerSmoke:

    def test_health(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "GET", "/api/health")
        assert status == 200
        assert json.loads(body) == {"status": "ok", "version": "1.3.0"}

    def test_concepts(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "GET", "/api/concepts")
        assert status == 200
        data = json.loads(body)
        assert "加法" in data["concepts"]
        assert "加法" in data["examples"]

    def test_help_endpoint(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "GET", "/api/help")
        assert status == 200
        assert isinstance(json.loads(body)["help"], str)
        assert json.loads(body)["help"]

    def test_unknown_route_404(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "GET", "/api/nope")
        assert status == 404
        assert json.loads(body) == {"error": "Not found"}

    def test_options_cors(self, assistant_server):
        server, _ = assistant_server
        status, headers, _ = _request(server, "OPTIONS", "/api/chat")
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "*"

    def test_chat_empty_text_400(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", {"text": "   "})
        assert status == 400
        assert json.loads(body)["error"] == "输入不能为空"

    def test_chat_invalid_json_400(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", raw_body="不是 JSON".encode("utf-8"))
        assert status == 400
        assert json.loads(body)["error"] == "无效的 JSON 格式"

    def test_chat_help_command(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", {"text": "help"})
        assert status == 200
        assert json.loads(body)["type"] == "guide"

    def test_chat_quit_command(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", {"text": "quit"})
        assert status == 200
        assert json.loads(body)["type"] == "text"

    def test_chat_normal_contract_and_perception(self, assistant_server):
        server, loop = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", {"text": "计算 3 加 5"})
        assert status == 200
        data = json.loads(body)
        assert isinstance(data["reply"], str) and data["reply"]
        assert data["type"] in ("text", "result", "error", "guide")
        assert loop._state.total_interactions == 1

    def test_chat_list_text_normalized(self, assistant_server):
        server, _ = assistant_server
        status, _, body = _request(server, "POST", "/api/chat",
                                   {"text": ["计算", "3 加 5"]})
        assert status == 200
        assert json.loads(body)["type"] in ("text", "result", "error", "guide")

    def test_chat_failure_sinks_to_error_buffer(self, assistant_server):
        server, loop = assistant_server
        status, _, body = _request(server, "POST", "/api/chat", {"text": "%%%乱码@@@"})
        assert status == 200
        assert len(loop._error_buffer) == 1
        assert loop._error_buffer[0]["text"] == "%%%乱码@@@"

    def test_chat_exception_sinks_to_500(self, assistant_server, monkeypatch):
        server, _ = assistant_server
        from src.ai_assistant_server import APIHandler

        def boom(text, interp):
            raise RuntimeError("boom")
        monkeypatch.setattr(APIHandler, "assistant",
                            types.SimpleNamespace(chat=boom))
        status, _, body = _request(server, "POST", "/api/chat", {"text": "x"})
        assert status == 500
        data = json.loads(body)
        assert data["error"] == "boom"
        assert data["reply"] == "处理出错：boom"


# ============================================================
# 2. openai_compat_server（OpenAI 兼容形状 + 诚实降级）
# ============================================================

class TestOpenAICompatSmoke:

    def test_models_list(self, compat_server):
        status, _, body = _request(compat_server, "GET", "/v1/models")
        assert status == 200
        data = json.loads(body)
        assert data["object"] == "list"
        assert data["data"] == [{"id": "matha", "object": "model", "owned_by": "matha"}]

    def test_health_alias(self, compat_server):
        status, _, body = _request(compat_server, "GET", "/health")
        assert status == 200
        assert json.loads(body)["object"] == "list"

    def test_unknown_route_404(self, compat_server):
        status, _, body = _request(compat_server, "GET", "/nope")
        assert status == 404
        assert json.loads(body) == {"error": {"message": "Not found"}}

    def test_options_cors(self, compat_server):
        status, headers, _ = _request(compat_server, "OPTIONS", "/v1/chat/completions")
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "*"

    def test_chat_no_messages_400(self, compat_server):
        status, _, body = _request(compat_server, "POST", "/v1/chat/completions", {})
        assert status == 400
        assert json.loads(body)["error"]["message"] == "messages is required"

    def test_chat_completion_shape(self, compat_server):
        status, _, body = _request(compat_server, "POST", "/v1/chat/completions", {
            "model": "matha",
            "messages": [{"role": "user", "content": "计算 3 加 5"}],
        })
        assert status == 200
        data = json.loads(body)
        assert data["id"].startswith("chatcmpl-")
        assert data["object"] == "chat.completion"
        assert data["model"] == "matha"
        assert isinstance(data["created"], int)
        choice = data["choices"][0]
        assert choice["index"] == 0 and choice["finish_reason"] == "stop"
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str) and choice["message"]["content"]
        usage = data["usage"]
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    def test_chat_uses_last_user_message(self, compat_server):
        status, _, body = _request(compat_server, "POST", "/v1/chat/completions", {
            "messages": [
                {"role": "user", "content": "旧问题"},
                {"role": "assistant", "content": "旧回答"},
                {"role": "user", "content": "计算 3 加 5"},
            ],
        })
        assert status == 200
        # prompt_tokens = len(user_text)：可观测地证明取的是最后一条 user
        assert json.loads(body)["usage"]["prompt_tokens"] == len("计算 3 加 5")

    def test_chat_stream_sse_shape(self, compat_server):
        status, headers, body = _request(compat_server, "POST", "/v1/chat/completions", {
            "messages": [{"role": "user", "content": "计算 3 加 5"}],
            "stream": True,
        })
        assert status == 200
        assert "text/event-stream" in headers.get("Content-Type", "")
        lines = [l for l in body.split("\n") if l.startswith("data: ")]
        assert lines[-1] == "data: [DONE]"
        chunks = [json.loads(l[len("data: "):]) for l in lines[:-1]]
        assert all(c["object"] == "chat.completion.chunk" for c in chunks)
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        content = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
        assert content  # 伪流式拼回完整回复（真流式属阶段 4，不在本锁主张）

    def test_completions_shape(self, compat_server):
        status, _, body = _request(compat_server, "POST", "/v1/completions",
                                   {"prompt": "计算 3 加 5"})
        assert status == 200
        data = json.loads(body)
        assert data["id"].startswith("cmpl-")
        assert data["object"] == "text_completion"
        assert isinstance(data["choices"][0]["text"], str) and data["choices"][0]["text"]
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_completions_list_prompt_takes_last(self, compat_server):
        status, _, body = _request(compat_server, "POST", "/v1/completions",
                                   {"prompt": ["旧", "计算 3 加 5"]})
        assert status == 200
        assert json.loads(body)["usage"]["prompt_tokens"] == len("计算 3 加 5")

    def test_chat_exception_degrades_honestly(self, compat_server, monkeypatch):
        """契约：chat 腿异常不假成功——200 但 reply 如实透出「Matha 错误」。"""
        from src.openai_compat_server import OpenAICompatHandler

        def boom(text, interp):
            raise RuntimeError("boom")
        monkeypatch.setattr(OpenAICompatHandler, "assistant",
                            types.SimpleNamespace(chat=boom))
        status, _, body = _request(compat_server, "POST", "/v1/chat/completions", {
            "messages": [{"role": "user", "content": "x"}],
        })
        assert status == 200
        content = json.loads(body)["choices"][0]["message"]["content"]
        assert "Matha 错误" in content and "boom" in content


# ============================================================
# 3. ai_assistant_desktop（启动接线，假注入不开浏览器不占端口）
# ============================================================

class TestDesktopLaunchWiring:

    def test_launch_desktop_wiring(self, monkeypatch):
        import time
        import webbrowser

        import src.ai_assistant_server as srv

        created = {}
        served = threading.Event()

        class FakeServer:
            def __init__(self, addr, handler):
                created["addr"] = addr
                created["handler"] = handler

            def serve_forever(self):
                created["served"] = True
                served.set()

            def shutdown(self):
                created["shutdown"] = True

        monkeypatch.setattr(srv, "HTTPServer", FakeServer)
        opened = []
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 1:
                assert served.wait(5), "后端线程未启动 serve_forever"
            else:
                raise KeyboardInterrupt  # 主循环退出腿

        monkeypatch.setattr(time, "sleep", fake_sleep)
        from src.ai_assistant_desktop import launch_desktop
        launch_desktop()
        assert created["addr"] == ("127.0.0.1", 8080)
        assert created["handler"] is srv.APIHandler
        assert created.get("served") is True
        assert created.get("shutdown") is True
        assert opened == ["http://127.0.0.1:8080"]