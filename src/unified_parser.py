# -*- coding: utf-8 -*-
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

# ── 主实现 ──────────────────────────────────────────────────────────────────
from src.lexer import Lexer, TokenType  # noqa: F401
from src.parser import Parser, parse, ParseError  # noqa: F401

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
            self._parser._tokens = tokens
            self._parser._pos = 0

    def parse(self):
        return self._parser.parse()


class MathaFrontend:
    """matha_cc 兼容前端。"""

    def __init__(self):
        pass

    def compile(self, source: str):
        """源码 → AST。"""
        return parse(source)

    def run(self, source: str):
        """源码 → 执行。"""
        from src.interp import Interpreter
        prog = parse(source)
        interp = Interpreter()
        return interp.run(prog)


class MathaLLVMGenerator:
    """matha_cc 兼容 LLVM 生成器（占位）。"""

    def __init__(self):
        pass

    def generate(self, ast):
        return "# LLVM generation not yet integrated"


def matha_compile(source: str, output_name: str = "out") -> str:
    """matha_cc 兼容：编译入口。"""
    prog = parse(source)
    return f"# Compiled {len(prog.decls)} declarations to {output_name}"


def matha_run(source: str) -> tuple:
    """matha_cc 兼容：运行入口。"""
    prog = parse(source)
    from src.interp import Interpreter
    interp = Interpreter()
    return interp.run(prog)


def matha_to_llvm(source: str) -> str:
    """matha_cc 兼容：Matha → LLVM IR。"""
    return "; LLVM IR not yet available"


# ── 统一导出 ────────────────────────────────────────────────────────────────
__all__ = [
    "Lexer", "TokenType",
    "Parser", "parse", "ParseError",
    "MathaLexer", "MathaParser", "MathaFrontend", "MathaLLVMGenerator",
    "matha_compile", "matha_run", "matha_to_llvm",
]
