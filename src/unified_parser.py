"""
Matha Lexer/Parser 统一层（Unified Lexer/Parser）

统一 src/lexer.py + src/parser.py 和 src/compiler/matha_cc.py 的接口：
  - 主实现：lexer.py + parser.py（Unicode-aware，完整 EBNF）
  - matha_cc：简化实现，用于编译链路

统一后：
  - matha_cc.py 的 MathaLexer/MathaParser 委托给主实现
  - 所有 import 路径仍然有效
"""
from __future__ import annotations

from typing import Any

# ── 主实现 ──────────────────────────────────────────────────────────────────
from src.lexer import Lexer, TokenType  # noqa: F401
from src.parser import ParseError, Parser, parse  # noqa: F401

# ── matha_cc 兼容性层 ───────────────────────────────────────────────────────
# 让 from src.compiler.matha_cc import MathaLexer, MathaParser 仍然有效

class MathaLexer:
    """matha_cc 兼容：委托给主 Lexer。"""

    def __init__(self, source: str = ""):
        self._lexer = Lexer(source)

    def tokenize(self):
        return self._lexer.tokenize()

    def next_token(self):
        return self._lexer.next_token()


class MathaParser:
    """matha_cc 兼容：委托给主 Parser。"""

    def __init__(self, tokens=None):
        self._parser = Parser("")
        if tokens:
            # 主 Parser 的 token 序列/游标字段是 tokens/pos（历史写法误设
            # _tokens/_pos，注入实际不生效——此处按真实字段注入）
            self._parser.tokens = list(tokens)
            self._parser.pos = 0

    def parse(self):
        return self._parser.parse()


class MathaFrontend:
    """matha_cc 兼容前端。"""

    def __init__(self):
        self._parser: Parser | None = None
        self._last_ast: Any = None
        self._ctx: dict[str, Any] = {}
        self._modules: dict[str, Any] = {}

    def compile(self, source: str):
        """源码 → AST。"""
        self._last_ast = parse(source)
        return self._last_ast

    def run(self, source: str):
        """源码 → 执行。"""
        from src.diag_backends import new_interpreter as Interpreter
        prog = parse(source)
        interp = Interpreter()
        return interp.run(prog)


class MathaLLVMGenerator:
    """matha_cc 兼容 LLVM 生成器（LLVM 后端未实现，显式拒绝而非假产物）。"""

    def __init__(self):
        self._modules: list[Any] = []
        self._symbols: dict[str, Any] = {}
        self._ir_stack: list[str] = []
        self._llvm_available = False

    def generate(self, ast):
        raise NotImplementedError(
            "LLVM 生成器未实现（此前返回假 IR 字符串，现显式拒绝）")


def matha_compile(source: str, output_name: str = "out") -> str:
    """matha_cc 兼容：编译入口（真编译：parse + mbc compile_program）。

    返回携带真实计数的摘要：声明数 / 函数数 / 主代码 ops 数。
    """
    from src.mbc.compiler import compile_program
    prog = parse(source)
    mod = compile_program(prog)
    return (f"# Compiled {len(prog.decls)} declarations to {output_name}: "
            f"{len(mod.functions)} functions, {len(mod.main_code)} ops")


def matha_run(source: str) -> tuple:
    """matha_cc 兼容：运行入口。"""
    prog = parse(source)
    from src.diag_backends import new_interpreter as Interpreter
    interp = Interpreter()
    return interp.run(prog)


def matha_to_llvm(source: str) -> str:
    """matha_cc 兼容：Matha → LLVM IR（未实现，显式拒绝）。"""
    raise NotImplementedError(
        "Matha → LLVM IR 未实现（此前返回假 IR 字符串，现显式拒绝）")


# ── 统一导出 ────────────────────────────────────────────────────────────────
__all__ = [
    "Lexer", "TokenType",
    "Parser", "parse", "ParseError",
    "MathaLexer", "MathaParser", "MathaFrontend", "MathaLLVMGenerator",
    "matha_compile", "matha_run", "matha_to_llvm",
]
