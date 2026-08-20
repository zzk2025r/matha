"""
前端开发服务器 — 提供 React 管理界面原型。
启动: python scripts/frontend_server.py
访问: http://localhost:8765
"""
import http.server
import os
import socketserver

PORT = 8765
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "frontend")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Matha Admin 前端服务器运行中: http://localhost:{PORT}")
    httpd.serve_forever()
