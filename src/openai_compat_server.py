# -*- coding: utf-8 -*-
"""Matha OpenAI 兼容 API 服务

将 Matha AI 助手封装为 OpenAI 兼容的 /v1/chat/completions 接口，
使其可作为 Trae / OpenAI 客户端的自定义模型使用。

启动：
    python -m src.openai_compat_server --port 8787

Trae 自定义模型配置：
    接口地址: http://localhost:8787/v1
    模型名:   matha
    API Key:  任意非空字符串（matha 本地无需鉴权）
"""
from __future__ import annotations
import json
import sys
import os
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant
from src.interp import Interpreter
from src.device_config import get_config


# 全局单例
_ASSISTANT = MathaAIAssistant()
_INTERP = Interpreter()
_INTERP_LOCK = threading.Lock()  # 解释器非线程安全，需加锁
_DEVICE_CFG = get_config()  # 设备性能配置


class OpenAICompatHandler(BaseHTTPRequestHandler):
    """OpenAI 兼容 API 处理器。"""

    assistant = _ASSISTANT
    interp = _INTERP

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self._send_json({}, 200)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/health", "/v1/models"):
            self._send_json({
                "object": "list",
                "data": [{"id": "matha", "object": "model", "owned_by": "matha"}],
            })
        else:
            self._send_json({"error": {"message": "Not found"}}, 404)

    def do_POST(self):
        # 处理 Expect: 100-continue（requests 库默认发送）
        if self.headers.get("Expect") == "100-continue":
            self.send_response(100)
            self.end_headers()

        parsed = urlparse(self.path)
        try:
            if parsed.path == "/v1/chat/completions":
                self._handle_chat_completions()
            elif parsed.path == "/v1/completions":
                self._handle_completions()
            else:
                self._send_json({"error": {"message": "Not found"}}, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": {"message": f"服务器错误: {e}"}}, 500)

    # ---------- /v1/chat/completions ----------
    def _handle_chat_completions(self):
        data = self._read_body()
        messages = data.get("messages", [])
        model = data.get("model", "matha")
        stream = data.get("stream", False)

        if not messages:
            self._send_json({"error": {"message": "messages is required"}}, 400)
            return

        # 取最后一条用户消息
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break

        # 调用 Matha AI 助手（加锁保护解释器）
        try:
            with _INTERP_LOCK:
                result = self.assistant.chat(user_text, self.interp)
        except Exception as e:
            result = {"reply": f"Matha 错误: {e}", "type": "error"}

        reply = result.get("reply", "")

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        if stream:
            self._send_stream(reply, model, completion_id, created)
        else:
            self._send_json({
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": len(user_text), "completion_tokens": len(reply), "total_tokens": len(user_text) + len(reply)},
            })

    # ---------- /v1/completions ----------
    def _handle_completions(self):
        data = self._read_body()
        prompt = data.get("prompt", "")
        model = data.get("model", "matha")

        if isinstance(prompt, list):
            prompt = prompt[-1] if prompt else ""

        try:
            with _INTERP_LOCK:
                result = self.assistant.chat(prompt, self.interp)
        except Exception as e:
            result = {"reply": f"Matha 错误: {e}", "type": "error"}

        reply = result.get("reply", "")
        completion_id = f"cmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        self._send_json({
            "id": completion_id,
            "object": "text_completion",
            "created": created,
            "model": model,
            "choices": [{
                "text": reply,
                "index": 0,
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": len(str(prompt)), "completion_tokens": len(reply), "total_tokens": len(str(prompt)) + len(reply)},
        })

    # ---------- 流式响应 ----------
    def _send_stream(self, content: str, model: str, completion_id: str, created: int):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def _chunk(delta: str, finish_reason=None):
            obj = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta} if delta else {},
                    "finish_reason": finish_reason,
                }],
            }
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        # 按片段发送（模拟流式）
        chunk_size = max(1, len(content) // 10) if content else 1
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            self.wfile.write(_chunk(chunk).encode("utf-8"))
            self.wfile.flush()

        self.wfile.write(_chunk("", finish_reason="stop").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        # 标记连接关闭
        self.close_connection = True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha OpenAI 兼容 API 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8787, help="监听端口")
    args = parser.parse_args()

    # 使用 daemon 线程，进程退出时自动清理
    ThreadingHTTPServer.daemon_threads = True
    server = ThreadingHTTPServer((args.host, args.port), OpenAICompatHandler)

    print(f"Matha OpenAI 兼容服务启动: http://{args.host}:{args.port}/v1")
    print(f"  模型名: matha")
    print(f"  {_DEVICE_CFG.summary()}")
    print(f"  说明: AI 助手调用经锁串行化（解释器非线程安全），HTTP 请求并发处理")
    print(f"  Trae 自定义模型配置:")
    print(f"    接口地址: http://localhost:{args.port}/v1")
    print(f"    模型名:   matha")
    print(f"    API Key:  任意非空字符串")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
