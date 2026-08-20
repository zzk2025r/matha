# -*- coding: utf-8 -*-
"""
matha-treesitter — 高性能树形解析器 Python 包

提供 Rust/Go/JavaScript/C 的 tree-sitter 绑定解析器。
支持 C 扩展加速（可选）和纯 Python 回退。

安装:
  pip install matha-treesitter
  # 或带 C 扩展:
  pip install matha-treesitter[cext]

使用:
  from matha_treesitter import RustParser, GoParser, JSParser, CParser

  parser = RustParser()
  tree = parser.parse("fn add(a: f64, b: f64) -> f64 { a + b }")
  for fn in tree.children:
      print(f"Function: {fn.value}")
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, Any

__version__ = "1.0.0"
__author__ = "Matha Team"
__email__ = "matha@example.com"

# ── 尝试加载 C 扩展 ─────────────────────────────────────────────────────────

_CEXT_AVAILABLE = False
try:
    from matha_treesitter._cext import parse as _c_parse  # type: ignore
    _CEXT_AVAILABLE = True
except ImportError:
    pass

# ── 内联后端（自包含，无需 src 目录）────────────────────────────────────────

from ._backends import (
    RustParser as _InlineRustParser,
    GoParser as _InlineGoParser,
    JSParser as _InlineJSParser,
    CParser as _InlineCParser,
    ASTNode,
    get_parser as _get_parser,
    parse_source as _parse_source,
    is_cext_available as _is_cext_available,
)

# ── 公共 API ──────────────────────────────────────────────────────────────────

class RustParser:
    """Rust 树形解析器（支持 C 扩展加速）。"""

    def __init__(self):
        self._use_cext = _CEXT_AVAILABLE

    def parse(self, source: str) -> ASTNode:
        """解析 Rust 源码为 AST。"""
        if self._use_cext:
            try:
                result = _c_parse("rust", source)
                return ASTNode(type="rust_program", value=result.get("type", ""),
                             children=[], fields=result)
            except Exception:
                pass  # fallback to inline
        return _InlineRustParser().parse(source)


class GoParser:
    """Go 树形解析器（支持 C 扩展加速）。"""

    def __init__(self):
        self._use_cext = _CEXT_AVAILABLE

    def parse(self, source: str) -> ASTNode:
        if self._use_cext:
            try:
                result = _c_parse("go", source)
                return ASTNode(type="go_program", value=result.get("type", ""),
                             children=[], fields=result)
            except Exception:
                pass
        return _InlineGoParser().parse(source)


class JSParser:
    """JavaScript 树形解析器（支持 C 扩展加速）。"""

    def __init__(self):
        self._use_cext = _CEXT_AVAILABLE

    def parse(self, source: str) -> ASTNode:
        if self._use_cext:
            try:
                result = _c_parse("javascript", source)
                return ASTNode(type="js_program", value=result.get("type", ""),
                             children=[], fields=result)
            except Exception:
                pass
        return _InlineJSParser().parse(source)


class CParser:
    """C 树形解析器（支持 C 扩展加速）。"""

    def __init__(self):
        self._use_cext = _CEXT_AVAILABLE

    def parse(self, source: str) -> ASTNode:
        if self._use_cext:
            try:
                result = _c_parse("c", source)
                return ASTNode(type="c_program", value=result.get("type", ""),
                             children=[], fields=result)
            except Exception:
                pass
        return _InlineCParser().parse(source)


def get_parser(language: str) -> Any:
    """根据语言返回对应的解析器实例。"""
    return _get_parser(language)


def is_cext_available() -> bool:
    """检查 C 扩展是否可用。"""
    return _CEXT_AVAILABLE or _is_cext_available()


def parse_source(language: str, source: str) -> ASTNode:
    """便捷函数：解析指定语言的源码。"""
    return _parse_source(language, source)


# ── 兼容性导出 ───────────────────────────────────────────────────────────────

__all__ = [
    "RustParser",
    "GoParser",
    "JSParser",
    "CParser",
    "get_parser",
    "parse_source",
    "is_cext_available",
    "ASTNode",
    "__version__",
]
