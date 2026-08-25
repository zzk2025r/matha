# -*- coding: utf-8 -*-
"""BackendGenerator：把 Matha 规格编译为 Python HTTP 服务成品。

输出文件：
  - server.py  可直接 `python server.py` 启动的 HTTP 服务

接口规格（["接口", 方法, 路径, 处理]）映射为路由：
  GET /api/hello  → 返回 JSON {"msg": "..."}
  POST /api/echo  → 回显请求体
  处理字段可以是返回 JSON 的 Python 表达式，或简单文本。
"""

from __future__ import annotations
from src.codegen.base import Generator, CodegenResult


class BackendGenerator(Generator):
    """后端服务生成器：AppSpec → Python http.server 脚本。"""

    def generate(self) -> CodegenResult:
        try:
            py = self._build_python()
            path = self._write("server.py", py)
        except Exception as e:
            return CodegenResult(成功=False, 类型="服务", 名称=self.app.name,
                                 错误=str(e))
        return CodegenResult(
            成功=True, 类型="服务", 名称=self.app.name,
            文件=[path], 入口=path,
        )

    def _build_python(self) -> str:
        title = self.app.title or self.app.name
        routes = self._build_routes()

        return (
            "# -*- coding: utf-8 -*-\n"
            f"# 由 Matha codegen 生成：{title}\n"
            "# 运行：python server.py  （默认 8080 端口）\n"
            "import json\n"
            "from http.server import HTTPServer, BaseHTTPRequestHandler\n"
            "from urllib.parse import urlparse\n\n\n"
            f"class {self._class_name()}Handler(BaseHTTPRequestHandler):\n"
            f'    """{title} — Matha 生成的 HTTP 服务。"""\n\n'
            "    def _send_json(self, code, data):\n"
            "        body = json.dumps(data, ensure_ascii=False).encode('utf-8')\n"
            "        self.send_response(code)\n"
            "        self.send_header('Content-Type', 'application/json; charset=utf-8')\n"
            "        self.send_header('Content-Length', len(body))\n"
            "        self.end_headers()\n"
            "        self.wfile.write(body)\n\n"
            f"{routes}\n\n\n"
            "def main():\n"
            "    port = 8080\n"
            f'    print(f"{{__file__}} 服务启动: http://localhost:{{port}}")\n'
            f"    server = HTTPServer(('0.0.0.0', port), {self._class_name()}Handler)\n"
            "    try:\n"
            "        server.serve_forever()\n"
            "    except KeyboardInterrupt:\n"
            "        print('\\\\n服务停止')\n"
            "    finally:\n"
            "        server.server_close()\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )

    def _build_routes(self) -> str:
        """构建路由处理代码。"""
        if not self.app.endpoints:
            return ("    def do_GET(self):\n"
                    '        self._send_json(200, {"msg": "服务运行中"})')

        lines = []
        get_paths = [ep for ep in self.app.endpoints if ep.method.upper() == "GET"]
        post_paths = [ep for ep in self.app.endpoints if ep.method.upper() == "POST"]

        if get_paths:
            lines.append("    def do_GET(self):")
            lines.append("        path = urlparse(self.path).path")
            for i, ep in enumerate(get_paths):
                kw = "if" if i == 0 else "elif"
                lines.append(f'        {kw} path == "{ep.path}":')
                lines.append(f'            self._send_json(200, {self._handler_body(ep)})')
            lines.append("        else:")
            lines.append('            self._send_json(404, {"error": "未找到"})')

        if post_paths:
            if get_paths:
                lines.append("")
            lines.append("    def do_POST(self):")
            lines.append("        path = urlparse(self.path).path")
            lines.append("        length = int(self.headers.get('Content-Length', 0))")
            lines.append("        body = self.rfile.read(length).decode('utf-8') if length else ''")
            for i, ep in enumerate(post_paths):
                kw = "if" if i == 0 else "elif"
                lines.append(f'        {kw} path == "{ep.path}":')
                lines.append(f'            self._send_json(200, {self._handler_body(ep, "body")})')
            lines.append("        else:")
            lines.append('            self._send_json(404, {"error": "未找到"})')

        return "\n".join(lines)

    def _handler_body(self, ep, body_var: str = None) -> str:
        """生成处理函数体（返回 JSON 可序列化的表达式）。"""
        handler = ep.handler.strip()
        # 若 handler 是合法的 JSON 表达式（dict/list/字符串），直接用
        if handler.startswith("{") or handler.startswith("["):
            return handler
        if body_var and handler == "echo":
            return '{"echo": ' + body_var + '}'
        # 默认：把 handler 作为 msg 返回
        import json
        return json.dumps({"msg": handler})

    def _class_name(self) -> str:
        name = self.app.name
        result = ""
        for ch in name:
            if ch.isalnum():
                result += ch
            elif ch in ("_", "-"):
                result += "_"
        return result or "App"

    @staticmethod
    def _escape_py(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')
