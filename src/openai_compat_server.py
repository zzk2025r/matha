"""Matha OpenAI 兼容 API 服务

【定位标注 2026-10 / P2 降级 · 措辞 2026-11 随阶段 4 更新】仓库内未背书前端：其复用的
AI 编排链（MathaAIAssistant.chat「输入→解析→执行→结果→感知」）已由
tests/test_ai_e2e_pipeline.py 入门禁锁固定（阶段 6e）；本文件 HTTP 层冒烟契约
（OpenAI 兼容形状/SSE + [DONE]/chat 异常诚实透出）已由
tests/test_ai_servers_smoke.py 入门禁（阶段 3）；可选 Bearer 鉴权与协议化增量 SSE
（阶段 4-4）同文件入门禁——本地引擎原子生成，流式为传输层增量而非模型逐 token；
自然语言→代码/答案的**结果正确性不背书**，不作为现功能主张；
口径见 docs/KNOWN_ISSUES.md 第七节 7c。

将 Matha AI 助手封装为 OpenAI 兼容的 /v1/chat/completions 接口，
使其可作为 Trae / OpenAI 客户端的自定义模型使用。

启动：
    matha server --port 8787                  # 统一 CLI（冻结 exe 同一路径）
    python -m src.openai_compat_server --port 8787   # 模块 __main__，等价

Trae 自定义模型配置：
    接口地址: http://localhost:8787/v1
    模型名:   matha
    API Key:  默认无需鉴权（任意非空字符串）；服务端设 MATHA_OPENAI_API_KEY
              环境变量后须填该值（Authorization: Bearer <key>）
"""
from __future__ import annotations

import hmac
import json
import os
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant
from src.plugins.device_config import get_config
from src.diag_backends import new_interpreter as Interpreter

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
        """请求访问日志：仅记录非轮询（health/技术探测）请求。"""
        try:
            msg = fmt % args if args else fmt
        except TypeError:
            msg = fmt
        if "/health" not in msg and "_GSt" not in msg:
            print(f"[openai-compat] {self.address_string()} {msg}",
                  file=sys.stderr)

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

    def _auth_ok(self) -> bool:
        """可选 Bearer 鉴权（阶段 4-4）：MATHA_OPENAI_API_KEY 未设则开放。

        设置后 /v1/* 须携带 Authorization: Bearer <key>；health 保持开放。
        比较用 hmac.compare_digest 防时序侧信道。
        """
        expected = os.environ.get("MATHA_OPENAI_API_KEY", "").strip()
        if not expected:
            return True
        header = self.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        return (scheme.lower() == "bearer"
                and hmac.compare_digest(token.strip(), expected))

    def _send_auth_error(self):
        self._send_json({"error": {
            "message": "Incorrect API key provided. Expected 'Authorization: Bearer <key>'.",
            "type": "authentication_error",
            "code": "invalid_api_key",
        }}, 401)

    def do_OPTIONS(self):
        self._send_json({}, 200)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/v1/models" and not self._auth_ok():
            self._send_auth_error()
            return
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
        if parsed.path.startswith("/v1/") and not self._auth_ok():
            self._send_auth_error()
            return
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
        stream = data.get("stream", False)

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

        if stream:
            self._send_text_stream(reply, model, completion_id, created)
            return

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
    def _sse_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _send_stream(self, content: str, model: str, completion_id: str, created: int):
        # 本地引擎原子生成完整回复；以下为传输层增量切分（非模型逐 token
        # 生成），协议形状对齐 OpenAI：首个 delta 带 role，随后 content 增量，
        # 末尾 finish_reason=stop + [DONE]。口径见文件头横幅。
        self._sse_headers()

        def _chunk(delta: dict, finish_reason=None):
            obj = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }],
            }
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        self.wfile.write(_chunk({"role": "assistant"}).encode("utf-8"))
        self.wfile.flush()
        for i in range(0, len(content), 8):
            self.wfile.write(_chunk({"content": content[i:i + 8]}).encode("utf-8"))
            self.wfile.flush()

        self.wfile.write(_chunk({}, finish_reason="stop").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def _send_text_stream(self, content: str, model: str, completion_id: str, created: int):
        """/v1/completions 的流式形态（text_completion chunk，阶段 4-4 补齐）。"""
        self._sse_headers()

        def _chunk(text: str, finish_reason=None):
            obj = {
                "id": completion_id,
                "object": "text_completion",
                "created": created,
                "model": model,
                "choices": [{
                    "text": text,
                    "index": 0,
                    "finish_reason": finish_reason,
                }],
            }
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        for i in range(0, len(content), 8):
            self.wfile.write(_chunk(content[i:i + 8]).encode("utf-8"))
            self.wfile.flush()

        self.wfile.write(_chunk("", finish_reason="stop").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


# ── 端口注册表 ──────────────────────────────────────────────────────────────

_PORT_REGISTRY = Path.home() / ".matha_port.json"


def _write_port_registry(port: int, host: str) -> None:
    """写入端口注册表，供 Trae / 守护进程 / 其他工具读取当前端口。"""
    import json as _json
    from datetime import datetime as _dt
    data = {
        "port": port,
        "host": host,
        "pid": os.getpid(),
        "updated": _dt.now().isoformat(),
        "url": f"http://localhost:{port}/v1",
        "model": "matha",
    }
    try:
        _PORT_REGISTRY.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _clear_port_registry() -> None:
    """清除端口注册表。"""
    try:
        if _PORT_REGISTRY.is_file():
            _PORT_REGISTRY.unlink()
    except Exception:
        pass


def _is_port_in_use(port: int, host: str) -> bool:
    """检查端口是否被占用。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def serve(host: str = "0.0.0.0", port: int = 8787) -> int:
    """启动 OpenAI 兼容服务并阻塞至中断，返回退出码（0 正常 / 1 端口全占用）。

    阶段 43b：本函数是唯一启动面，`main()` 与 `matha server` 子命令都转发到此。
    既往服务只能由模块 `__main__` 起（`python -m src.openai_compat_server`），
    统一 CLI 入口没有命令位 ⇒ 冻结 exe 起不了服务，Windows 包装器于是指向了
    早已删除的 `src.matha_daemon`。端口占用探测与注册表口径不变。
    """
    # 端口冲突检测：如果被占用，尝试自动查找可用端口
    if _is_port_in_use(port, host):
        print(f"端口 {port} 已被占用，尝试查找可用端口...")
        for offset in range(1, 11):
            test_port = port + offset
            if not _is_port_in_use(test_port, host):
                print(f"自动切换到端口 {test_port}")
                port = test_port
                break
        else:
            print(f"错误：端口 {port}-{port+10} 均被占用，无法启动")
            print("提示：本服务已自动试过该区间；请释放端口或显式换端口"
                  "（matha server --port <端口>）")
            return 1

    # 使用 daemon 线程，进程退出时自动清理
    ThreadingHTTPServer.daemon_threads = True
    server = ThreadingHTTPServer((host, port), OpenAICompatHandler)

    # 写入端口注册表
    _write_port_registry(port, host)

    print(f"Matha OpenAI 兼容服务启动: http://{host}:{port}/v1")
    print("  模型名: matha")
    print(f"  {_DEVICE_CFG.summary()}")
    print("  说明: AI 助手调用经锁串行化（解释器非线程安全），HTTP 请求并发处理")
    print("  Trae 自定义模型配置:")
    print(f"    接口地址: http://localhost:{port}/v1")
    print("    模型名:   matha")
    print("    API Key:  任意非空字符串")
    print(f"  端口注册表: {_PORT_REGISTRY}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()
    finally:
        _clear_port_registry()
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha OpenAI 兼容 API 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8787, help="监听端口")
    args = parser.parse_args()
    sys.exit(serve(args.host, args.port))


if __name__ == "__main__":
    main()
