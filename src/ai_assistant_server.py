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
from src.inner_loop import get_inner_loop
from src.symbolic import symbol_expr, diff_expr, eval_expr, ast_to_dict
from src.ffi import get_ffi
from src.symbol_codegen import get_codegen
from src.math_driver import get_driver_manager
from src.multi_paradigm import get_paradigm_engine


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

    def _read_body(self) -> str:
        """读取请求体。"""
        length = int(self.headers.get('Content-Length', 0))
        if length > 0:
            return self.rfile.read(length).decode('utf-8')
        return '{}'

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
            self._send_json({"status": "ok", "version": "1.3.0"})
        elif parsed.path == '/api/growth/stats':
            from src.growth_engine import create_growth_engine
            engine = create_growth_engine(assistant=self.assistant)
            self._send_json(engine.get_growth_stats())
        elif parsed.path == '/api/growth/audit':
            from src.growth_engine import create_growth_engine
            engine = create_growth_engine(assistant=self.assistant)
            resources = engine.audit_resources()
            self._send_json({
                "resources": [
                    {"name": e.name, "kind": e.kind, "status": e.status}
                    for e in resources
                ],
                "total": len(resources),
                "missing": sum(1 for e in resources if e.status != "ok"),
            })
        elif parsed.path == '/api/growth/defects':
            from src.growth_engine import create_growth_engine
            engine = create_growth_engine(assistant=self.assistant)
            self._send_json(engine.get_defect_stats())
        elif parsed.path == '/api/growth/diagnose':
            from src.growth_engine import create_growth_engine
            engine = create_growth_engine(assistant=self.assistant)
            defects = engine.self_diagnose()
            self._send_json({
                "new_defects": len(defects),
                "defects": [
                    {"id": d.defect_id, "severity": d.severity.value,
                     "category": d.category.value, "message": d.message}
                    for d in defects
                ]
            })
        elif parsed.path == '/api/growth/trigger':
            from src.growth_engine import create_growth_engine
            engine = create_growth_engine(assistant=self.assistant)
            report = engine.trigger_growth()
            self._send_json(report)
        # ── 内循环 API ──────────────────────────────────────────────────────────
        elif parsed.path == '/api/inner_loop/status':
            loop = get_inner_loop()
            self._send_json(loop.get_state())
        elif parsed.path == '/api/inner_loop/trigger':
            loop = get_inner_loop()
            if not loop._engine:
                loop.init_modules()
            result = loop.run_cycle(verbose=False)
            self._send_json(result)
        elif parsed.path == '/api/inner_loop/start':
            loop = get_inner_loop()
            loop.start_loop(interval=30.0)
            self._send_json({"status": "started", "message": "内循环持续模式已启动"})
        elif parsed.path == '/api/inner_loop/stop':
            loop = get_inner_loop()
            loop.stop_loop()
            self._send_json({"status": "stopped", "message": "内循环持续模式已停止"})
        # ── 自扩展 API ─────────────────────────────────────────────────────────
        elif parsed.path == '/api/inner_loop/extend':
            loop = get_inner_loop()
            if not loop._engine:
                loop.init_modules()
            concepts = loop.self_extend_concepts()
            intents = loop.self_extend_intents()
            self._send_json({
                "status": "extended",
                "concepts_added": concepts,
                "intents_added": intents,
                "total_concepts": len(loop._assistant.parser.MATH_CONCEPTS) if loop._assistant else 0,
            })
        # ── 自升级 API ─────────────────────────────────────────────────────────
        elif parsed.path == '/api/inner_loop/upgrade/check':
            loop = get_inner_loop()
            if not loop._engine:
                loop.init_modules()
            self._send_json(loop.self_upgrade_check())
        elif parsed.path == '/api/inner_loop/upgrade/apply':
            loop = get_inner_loop()
            if not loop._engine:
                loop.init_modules()
            result = loop.self_upgrade_apply()
            self._send_json(result)
        elif parsed.path == '/api/inner_loop/upgrade/rollback':
            loop = get_inner_loop()
            result = loop.self_upgrade_rollback()
            self._send_json({"status": "rolled_back" if result else "no_engine"})
        # ── 自优化 API ─────────────────────────────────────────────────────────
        elif parsed.path == '/api/inner_loop/optimize':
            loop = get_inner_loop()
            if not loop._engine:
                loop.init_modules()
            result = loop.self_optimize_performance()
            self._send_json(result)
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
        # ── 符号引擎 API ─────────────────────────────────────────────────────
        elif parsed.path == '/api/symbolic/parse':
            data = json.loads(self._read_body())
            expr_str = data.get("expression", "")
            try:
                expr = symbol_expr(expr_str)
                simp = expr.simplify()
                deriv = expr.diff(list(data.get("params", {}).keys())[0] if data.get("params") else 'x')
                try:
                    val = expr.evaluate(data.get("params", {}))
                except:
                    val = None
                self._send_json({
                    "expression": expr_str,
                    "simplified": str(simp),
                    "derivative": str(deriv),
                    "value": val,
                    "ast": ast_to_dict(expr),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
        # ── FFI API ──────────────────────────────────────────────────────────
        elif parsed.path == '/api/ffi/list':
            ffi = get_ffi()
            self._send_json(ffi.list_functions())
        elif parsed.path == '/api/ffi/call':
            data = json.loads(self._read_body())
            ffi = get_ffi()
            result = ffi.call(data.get("name", ""), *data.get("args", []))
            self._send_json({"name": data.get("name"), "result": result})
        # ── 多范式 API ───────────────────────────────────────────────────────
        elif parsed.path == '/api/paradigm/compute':
            data = json.loads(self._read_body())
            engine = get_paradigm_engine()
            result = engine.compute(data)
            self._send_json(result)
        # ── 代码生成 API ─────────────────────────────────────────────────────
        elif parsed.path == '/api/codegen/python':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.python(data.get("expr", ""), data.get("func_name", "compute"))})
        elif parsed.path == '/api/codegen/javascript':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.javascript(data.get("expr", ""), data.get("func_name", "compute"))})
        elif parsed.path == '/api/codegen/c':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.c(data.get("expr", ""), data.get("func_name", "compute"))})
        # ── 驱动 API ─────────────────────────────────────────────────────────
        elif parsed.path == '/api/drivers/list':
            mgr = get_driver_manager()
            self._send_json(mgr.list_drivers())
        elif parsed.path == '/api/drivers/execute':
            try:
                data = json.loads(self._read_body())
                mgr = get_driver_manager()
                driver_name = data.get("driver", "")
                op_name = data.get("op", "")
                args = data.get("args", [])
                # 矩阵类操作：整个二维列表作为单个矩阵参数（不拆包行）
                matrix_ops = {'mat_det', 'mat_mul', 'mat_add', 'mat_transpose', 'mat_inv',
                              'eigenvalues', 'norm', 'matrix_power'}
                if op_name in matrix_ops and len(args) >= 1 and isinstance(args[0], list):
                    result = mgr.execute(driver_name, op_name, args)
                else:
                    result = mgr.execute(driver_name, op_name, *args)
                self._send_json({"result": result})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        # v1.3.0 新端点（支持 POST）
        if parsed.path == '/api/symbolic/parse':
            data = json.loads(self._read_body())
            expr_str = data.get("expression", data.get("expr", ""))
            try:
                expr = symbol_expr(expr_str)
                simp = expr.simplify()
                params = data.get("params", {})
                deriv = expr.diff(list(params.keys())[0] if params else 'x')
                try:
                    val = expr.evaluate(params)
                except Exception:
                    val = None
                self._send_json({
                    "expression": expr_str,
                    "simplified": str(simp),
                    "derivative": str(deriv),
                    "value": val,
                    "ast": ast_to_dict(expr),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
        elif parsed.path == '/api/ffi/call':
            data = json.loads(self._read_body())
            ffi = get_ffi()
            result = ffi.call(data.get("name", ""), *data.get("args", []))
            self._send_json({"name": data.get("name"), "result": result})
        elif parsed.path == '/api/paradigm/compute':
            data = json.loads(self._read_body())
            engine = get_paradigm_engine()
            result = engine.compute(data)
            self._send_json(result)
        elif parsed.path == '/api/codegen/python':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.python(data.get("expr", ""), data.get("func_name", "compute"))})
        elif parsed.path == '/api/codegen/javascript':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.javascript(data.get("expr", ""), data.get("func_name", "compute"))})
        elif parsed.path == '/api/codegen/c':
            data = json.loads(self._read_body())
            cg = get_codegen()
            self._send_json({"code": cg.c(data.get("expr", ""), data.get("func_name", "compute"))})
        elif parsed.path == '/api/drivers/execute':
            try:
                data = json.loads(self._read_body())
                mgr = get_driver_manager()
                driver_name = data.get("driver", "")
                op_name = data.get("op", "")
                args = data.get("args", [])
                # 矩阵类操作：整个二维列表作为单个矩阵参数（不拆包行）
                matrix_ops = {'mat_det', 'mat_mul', 'mat_add', 'mat_transpose', 'mat_inv',
                              'eigenvalues', 'norm', 'matrix_power'}
                if op_name in matrix_ops and len(args) >= 1 and isinstance(args[0], list):
                    result = mgr.execute(driver_name, op_name, args)
                else:
                    result = mgr.execute(driver_name, op_name, *args)
                self._send_json({"result": result})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif parsed.path == '/api/chat':
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

                # 内循环感知：记录交互，触发轻量诊断
                try:
                    loop = get_inner_loop()
                    if not loop._engine:
                        loop.init_modules()
                    loop.on_interaction(text, result)
                    # 如果交互失败，异步触发一轮内循环修复
                    if not result.get("result") and result.get("type") != "guide":
                        loop.cognitive_diagnose()
                except Exception:
                    pass

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
