"""Matha MCP Server — 通过 Model Context Protocol 暴露 Matha 工具
用法: python -m src.mcp_server

【定位 2026-11 · 阶段 1 AI 修复】mcp SDK 为可选依赖：缺包时 import 本模块
不再 NameError（MathaMCPServer 历史上继承 MCPServer，类定义即崩），
进程内门面 MathaMCPServer 不依赖 SDK 可直接用；create_server() 缺 SDK 时
显式 ImportError。契约锁见 tests/test_mcp_server_facade.py。
版本取自唯一版本源 src.__version__（原硬编 "4.4" 已漂移）。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 确保 src 在 PATH
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.__version__ import VERSION

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.types import TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def _safe_eval(expr: str) -> str:
    """安全计算 Matha 表达式，返回字符串结果。"""
    from src.diag_backends import run_legacy as interpret
    wrapped = f"result = {expr}\n#1：[result]"
    out, _ = interpret(wrapped)
    return "\n".join(str(item) for item in out) if out else ""


def _safe_run(file_path: str) -> str:
    """运行 .matha 文件，返回输出。"""
    path = Path(file_path)
    if not path.exists():
        return f"错误: 文件不存在: {file_path}"
    from src.diag_backends import run_legacy as interpret
    source = path.read_text(encoding="utf-8")
    out, _ = interpret(source)
    return "\n".join(str(item) for item in out) if out else ""


def _safe_compile(source: str, output: str | None = None) -> str:
    """编译 Matha 源码到 C。"""
    from src.compiler.matha_cc import matha_compile
    try:
        result = matha_compile(source, output or "out.c", optimize=True)
        return f"编译成功: {result}"
    except Exception as e:
        return f"编译失败: {e}"


def _safe_diagnose(source: str) -> list[dict]:
    """诊断 Matha 源码。"""
    from src.diagnostics import LSPServer
    server = LSPServer()
    try:
        results = server.analyze(source)
        return results if results else [{"message": "无诊断问题", "severity": "hint"}]
    except Exception as e:
        return [{"message": f"诊断错误: {e}", "severity": "error"}]


def _safe_parse(text: str) -> dict:
    """解析自然语言意图。"""
    from src.ai_assistant import FriendlyIntentParser
    parser = FriendlyIntentParser()
    return parser.explain_intent(text)


def create_server() -> MCPServer:
    if not MCP_AVAILABLE:
        raise ImportError("请安装 mcp: pip install mcp")
    server = MCPServer(name="matha", version=VERSION)

    @server.tool()
    async def eval_expression(expr: str) -> list[TextContent]:
        """计算 Matha 表达式。输入数学表达式或自然语言，返回计算结果。"""
        try:
            result = _safe_eval(expr)
            return [TextContent(type="text", text=result or "(无输出)")]
        except Exception as e:
            return [TextContent(type="text", text=f"计算错误: {e}")]

    @server.tool()
    async def run_file(file_path: str) -> list[TextContent]:
        """运行 .matha 源文件并返回输出。"""
        try:
            result = _safe_run(file_path)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"运行错误: {e}")]

    @server.tool()
    async def compile_source(source: str, output: str | None = None) -> list[TextContent]:
        """将 Matha 源码编译为 C 代码。source 为 Matha 源码字符串。"""
        try:
            result = _safe_compile(source, output)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"编译错误: {e}")]

    @server.tool()
    async def diagnose_source(source: str) -> list[TextContent]:
        """分析 Matha 源码，返回语法/语义诊断（LSP 格式）。"""
        try:
            diagnostics = _safe_diagnose(source)
            if not diagnostics:
                return [TextContent(type="text", text="无诊断问题")]
            return [TextContent(type="text", text=json.dumps(diagnostics, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"诊断错误: {e}")]

    @server.tool()
    async def parse_intent(text: str) -> list[TextContent]:
        """解析自然语言数学意图（素数/物理/几何/代数等）。"""
        try:
            result = _safe_parse(text)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"解析错误: {e}")]

    @server.tool()
    async def get_info() -> list[TextContent]:
        """获取 Matha 系统信息（版本、工具链、配置）。"""
        info = {
            "name": "Matha",
            "version": VERSION,
            "project_root": str(PROJECT_ROOT),
            "src_path": str(PROJECT_ROOT / "src"),
            "python": sys.version.split()[0],
            "mcp": "available" if MCP_AVAILABLE else "not installed",
        }
        return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]

    return server


class MathaMCPServer:
    """Matha 工具的进程内同步门面（不依赖 mcp SDK）。

    历史上继承 MCPServer：缺 SDK 时类定义即 NameError，且
    _register_matha_tools 是 pass 占位（从未注册任何工具）。现改为
    纯门面——五个方法全部直调真实 _safe_* 实现；对外协议服务由
    create_server()/main() 承担（缺 SDK 显式 ImportError）。
    """

    def eval_expr(self, expr: str) -> str:
        return _safe_eval(expr)

    def run_file(self, file_path: str) -> str:
        return _safe_run(file_path)

    def compile_source(self, source: str, output=None) -> str:
        return _safe_compile(source, output)

    def diagnose(self, source: str) -> list[dict]:
        return _safe_diagnose(source)

    def get_info(self) -> dict:
        return {"name": "Matha", "version": VERSION, "python": sys.version.split()[0]}


def main():
    if not MCP_AVAILABLE:
        print("Matha MCP: mcp 包未安装，运行: pip install mcp", file=sys.stderr)
        sys.exit(1)

    server = create_server()
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
