# -*- coding: utf-8 -*-
"""Matha MCP Server — 通过 Model Context Protocol 暴露 Matha 工具
用法: python -m src.mcp_server
"""
from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

# 确保 src 在 PATH
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def _safe_eval(expr: str) -> str:
    """安全计算 Matha 表达式，返回字符串结果。"""
    from src.interp import interpret
    wrapped = f"result = {expr}\n#1：[result]"
    out, _ = interpret(wrapped)
    return "\n".join(str(item) for item in out) if out else ""


def _safe_run(file_path: str) -> str:
    """运行 .matha 文件，返回输出。"""
    path = Path(file_path)
    if not path.exists():
        return f"错误: 文件不存在: {file_path}"
    from src.interp import interpret
    source = path.read_text(encoding="utf-8")
    out, _ = interpret(source)
    return "\n".join(str(item) for item in out) if out else ""


def _safe_compile(source: str, output: Optional[str] = None) -> str:
    """编译 Matha 源码到 C。"""
    from src.compiler.matha_cc import matha_compile
    try:
        result = matha_compile(source, output or "out.c", optimize=True)
        return f"编译成功: {result}"
    except Exception as e:
        return f"编译失败: {e}"


def _safe_diagnose(source: str) -> list[dict]:
    """诊断 Matha 源码。"""
    from src.diagnostics import DiagnosticCollector
    collector = DiagnosticCollector()
    collector._parse_diagnostics(source)
    return [d.to_lsp() for d in collector._diagnostics]


def _safe_parse(text: str) -> dict:
    """解析自然语言意图。"""
    from src.ai_assistant import FriendlyIntentParser
    parser = FriendlyIntentParser()
    return parser.explain_intent(text)


def _create_server() -> "Server":
    server = Server("matha")

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
    async def compile_source(source: str, output: Optional[str] = None) -> list[TextContent]:
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
        from src.matha_main import VERSION
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


def main():
    if not MCP_AVAILABLE:
        print("Matha MCP: mcp 包未安装，运行: pip install mcp", file=sys.stderr)
        sys.exit(1)

    from mcp.server.stdio import stdio_server
    server = _create_server()

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)

    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
