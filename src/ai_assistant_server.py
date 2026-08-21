# -*- coding: utf-8 -*-
"""
Matha AI Assistant — Web 后端 API 服务
提供 RESTful API 供前端调用，零依赖轻量服务
"""
from __future__ import annotations
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant
from src.interp import Interpreter


# ── API 处理器 ──────────────────────────────────────────────────

class APIHandler(BaseHTTPRequestHandler):
    """HTTP API 处理器。"""

    assistant = MathaAIAssistant()
    interp = Interpreter()

    def log_message(self, format, *args):
        """静默日志。"""
        pass

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        """处理 CORS 预检。"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/' or parsed.path == '/index.html':
            self._serve_file('web/index.html', 'text/html; charset=utf-8')
        elif parsed.path == '/api/health':
            self._send_json({"status": "ok", "version": "1.2.10"})
        elif parsed.path == '/api/concepts':
            from src.ai_assistant import FriendlyIntentParser
            p = FriendlyIntentParser()
            self._send_json({
                "concepts": list(p.MATH_CONCEPTS.keys()),
                "examples": {
                    "加法": "计算 3 加 5",
                    "素数": "找出 1 到 100 的素数",
                    "平均值": "求 [1,2,3,4,5] 的平均值",
                    "物理": "自由落体 3 秒",
                }
            })
        elif parsed.path == '/api/help':
            self._send_json({"help": self.assistant.help()})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/chat':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                text = data.get('text', '').strip()
                if not text:
                    self._send_json({"error": "输入不能为空"}, 400)
                    return

                # 检查特殊命令
                if text.lower() in ('help', '帮助'):
                    self._send_json({
                        "reply": self.assistant.help(),
                        "type": "guide"
                    })
                    return

                if text.lower() in ('quit', 'exit', '退出'):
                    self._send_json({"reply": "再见！👋", "type": "text"})
                    return

                # 调用 AI 助手
                result = self.assistant.chat(text, self.interp)
                self._send_json(result)

            except json.JSONDecodeError:
                self._send_json({"error": "无效的 JSON 格式"}, 400)
            except Exception as e:
                self._send_json({"error": str(e), "reply": f"处理出错：{e}"}, 500)

        else:
            self._send_json({"error": "Not found"}, 404)

    def _serve_file(self, path: str, content_type: str):
        # web/ 在 src/ 的上一级，从项目根目录拼接路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(project_root, path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self._send_json({"error": "File not found"}, 404)


# ── 启动服务器 ──────────────────────────────────────────────────

def run(host: str = '127.0.0.1', port: int = 8080):
    """启动 Web 服务。"""
    server = HTTPServer((host, port), APIHandler)
    print(f"\n{'='*50}")
    print(f"  🧮 Matha AI Assistant 已启动")
    print(f"  📍 访问地址: http://{host}:{port}")
    print(f"  📱 手机/平板访问: 在同一 WiFi 下输入本机 IP:{port}")
    print(f"  💡 提示: 无需安装任何软件，浏览器即可使用")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
        server.server_close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Matha AI Assistant')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址（0.0.0.0=所有网卡，手机可访问）')
    parser.add_argument('--port', type=int, default=8080, help='监听端口')
    args = parser.parse_args()
    run(args.host, args.port)
