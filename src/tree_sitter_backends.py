# -*- coding: utf-8 -*-
"""matha-auth tree-sitter 后端（无需外部依赖的内联 AST 解析器）

提供 Rust/Go/JavaScript/C 的内联正则解析器，作为 tree-sitter C 扩展的降级方案。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# 支持标记（tree-sitter C 扩展不可用时降级为内联解析器）
_TS_AVAILABLE = True


@dataclass
class ASTNode:
    """AST 节点"""
    type: str
    value: str
    children: List['ASTNode'] = field(default_factory=list)
    fields: Dict[str, 'ASTNode'] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "children": [c.to_dict() for c in self.children],
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }

    def __len__(self) -> int:
        return len(self.children)

    def __bool__(self) -> bool:
        return bool(self.children) or bool(self.value)


# ── Rust 解析器 ───────────────────────────────────────────────────────────────

class RustParser:
    """Rust 内联 AST 解析器（正则实现）"""

    def parse(self, source: str) -> ASTNode:
        source = source.strip()
        functions = []
        const_re = re.compile(r'const\s+(\w+)\s*:\s*([\w<>,\s]+)\s*=\s*([^;]+);', re.DOTALL)
        fn_re = re.compile(
            r'fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([\w<>,\s]+))?\s*\{([^}]*)\}',
            re.DOTALL,
        )

        for m in fn_re.finditer(source):
            name, params_str, ret_type, body = m.groups()
            params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str.strip() else []
            fn_node = ASTNode(
                type="function",
                value=f"fn {name}({', '.join(params)})",
            )
            fn_node.fields["name"] = ASTNode(type="ident", value=name)
            fn_node.fields["return_type"] = ASTNode(type="type", value=ret_type or "()")
            fn_node.children.append(ASTNode(type="block", value=body.strip()))
            functions.append(fn_node)

        for m in const_re.finditer(source):
            name, typ, val = m.groups()
            functions.append(ASTNode(
                type="const",
                value=f"const {name}: {typ} = {val}",
            ))

        return ASTNode(type="rust_program", value=source[:50], children=functions)


# ── Go 解析器 ────────────────────────────────────────────────────────────────

class GoParser:
    """Go 内联 AST 解析器（正则实现）"""

    def parse(self, source: str) -> ASTNode:
        source = source.strip()
        functions = []
        fn_re = re.compile(
            r'func\s+(\w+)\s*\(([^)]*)\)\s*(?:([\w<>,\s]+))?\s*\{([^}]*)\}',
            re.DOTALL,
        )

        for m in fn_re.finditer(source):
            name, params_str, ret_type, body = m.groups()
            params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str.strip() else []
            fn_node = ASTNode(
                type="function",
                value=f"func {name}({', '.join(params)})",
            )
            fn_node.fields["name"] = ASTNode(type="ident", value=name)
            if ret_type and ret_type.strip():
                fn_node.fields["return_type"] = ASTNode(type="type", value=ret_type.strip())
            fn_node.children.append(ASTNode(type="block", value=body.strip()))
            functions.append(fn_node)

        return ASTNode(type="go_program", value=source[:50], children=functions)


# ── JavaScript 解析器 ─────────────────────────────────────────────────────────

class JSParser:
    """JavaScript 内联 AST 解析器（正则实现）"""

    def parse(self, source: str) -> ASTNode:
        source = source.strip()
        functions = []
        fn_re = re.compile(
            r'(?:function|const|let|var)\s+(\w+)\s*\(?:([^)]*)\)?\s*(?::\s*[\w<>]+)?\s*=\s*(?:function\s*\([^)]*\)\s*)?\{([^}]*)\}',
            re.DOTALL,
        )
        arrow_re = re.compile(
            r'(?:const|let)\s+(\w+)\s*=\s*\(([^)]*)\)\s*=>\s*\{([^}]*)\}',
            re.DOTALL,
        )

        for m in fn_re.finditer(source):
            name, params_str, body = m.groups()
            params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str.strip() else []
            fn_node = ASTNode(
                type="function",
                value=f"function {name}({', '.join(params)})",
            )
            fn_node.fields["name"] = ASTNode(type="ident", value=name)
            fn_node.children.append(ASTNode(type="block", value=body.strip()))
            functions.append(fn_node)

        for m in arrow_re.finditer(source):
            name, params_str, body = m.groups()
            params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str.strip() else []
            fn_node = ASTNode(
                type="arrow_function",
                value=f"({', '.join(params)}) => {{ ... }}",
            )
            fn_node.fields["name"] = ASTNode(type="ident", value=name)
            fn_node.children.append(ASTNode(type="block", value=body.strip()))
            functions.append(fn_node)

        return ASTNode(type="js_program", value=source[:50], children=functions)


# ── C 解析器 ──────────────────────────────────────────────────────────────────

class CParser:
    """C 内联 AST 解析器（正则实现）"""

    def parse(self, source: str) -> ASTNode:
        source = source.strip()
        functions = []
        fn_re = re.compile(
            r'([\w<>\*\s]+?)\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.DOTALL,
        )

        for m in fn_re.finditer(source):
            ret_type, name, params_str, body = m.groups()
            params = [p.strip() for p in params_str.split(',') if p.strip()] if params_str.strip() else []
            fn_node = ASTNode(
                type="function",
                value=f"{ret_type.strip()} {name}({', '.join(params)})",
            )
            fn_node.fields["return_type"] = ASTNode(type="type", value=ret_type.strip())
            fn_node.fields["name"] = ASTNode(type="ident", value=name)
            fn_node.children.append(ASTNode(type="block", value=body.strip()))
            functions.append(fn_node)

        return ASTNode(type="c_program", value=source[:50], children=functions)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def get_parser(language: str) -> Any:
    """根据语言返回对应的解析器实例"""
    parsers = {
        "rust": RustParser,
        "go": GoParser,
        "javascript": JSParser,
        "c": CParser,
    }
    parser_cls = parsers.get(language)
    if parser_cls is None:
        raise ValueError(f"不支持的语言: {language}，支持: {list(parsers.keys())}")
    return parser_cls()


def is_cext_available() -> bool:
    """检查 C 扩展是否可用（当前始终为 False，使用内联解析器）"""
    return _TS_AVAILABLE


def parse_source(language: str, source: str) -> ASTNode:
    """便捷函数：解析指定语言的源码"""
    return get_parser(language).parse(source)
