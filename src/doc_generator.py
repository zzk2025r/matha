"""Matha 文档生成器：自动生成 API 文档（类似 Sphinx）。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocType(Enum):
    """文档类型。"""
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"


@dataclass
class DocEntry:
    """文档条目。"""
    name: str
    type: DocType
    signature: str | None = None
    description: str = ""
    params: list[dict] = field(default_factory=list)
    returns: str | None = None
    example: str | None = None


@dataclass
class DocPage:
    """文档页面。"""
    title: str
    entries: list[DocEntry] = field(default_factory=list)
    content: str = ""
    markdown: str = ""


class MathaDocGenerator:
    """Matha 文档生成器。"""

    def __init__(self):
        self._entries: list[DocEntry] = []
        self._pages: list[DocPage] = []
        self._initialized = False
        self._init_doc_generator()

    def _init_doc_generator(self) -> None:
        """初始化文档生成器。"""
        self._initialized = True

    def add_entry(self, name: str, type: DocType,
                     signature: str | None = None,
                     description: str = "",
                     params: list[dict] | None = None,
                     returns: str | None = None,
                     example: str | None = None
                     ) -> DocEntry:
        """添加文档条目。"""
        entry = DocEntry(
            name=name, type=type, signature=signature,
            description=description,
            params=params or [], returns=returns, example=example
        )
        self._entries.append(entry)
        return entry

    def generate_markdown(self, title: str = "API 文档"
                            ) -> str:
        """生成 Markdown 文档。"""
        md = f"# {title}\n\n"
        md += "**生成时间**：2026-09-26\n\n"
        md += f"**条目数**：{len(self._entries)}\n\n"
        md += "---\n\n"
        for entry in self._entries:
            md += self._entry_to_markdown(entry)
        return md

    def _entry_to_markdown(self, entry: DocEntry) -> str:
        """将条目转换为 Markdown。"""
        md = f"## {entry.type.value}: `{entry.name}`\n\n"
        if entry.signature:
            md += f"**签名**：\n```\n{entry.signature}\n```\n\n"
        if entry.description:
            md += f"{entry.description}\n\n"
        if entry.params:
            md += "**参数**：\n"
            for param in entry.params:
                md += f"- `{param.get('name', '')}`: {param.get('type', '')}"
                if param.get('description'):
                    md += f" — {param['description']}"
                md += "\n"
            md += "\n"
        if entry.returns:
            md += f"**返回值**：{entry.returns}\n\n"
        if entry.example:
            md += f"**示例**：\n```\n{entry.example}\n```\n\n"
        md += "---\n\n"
        return md

    def generate_html(self, title: str = "API 文档"
                         ) -> str:
        """生成 HTML 文档。"""
        html = f"""<!DOCTYPE html>
<html><head><title>{title}</title></head>
<body>
<h1>{title}</h1>
"""
        for entry in self._entries:
            html += f"""
<h2>{entry.type.value}: {entry.name}</h2>
"""
            if entry.signature:
                html += f"<pre>{entry.signature}</pre>\n"
            if entry.description:
                html += f"<p>{entry.description}</p>\n"
            if entry.example:
                html += f"<pre>{entry.example}</pre>\n"
        html += "</body></html>"
        return html

    def generate_json(self) -> str:
        """生成 JSON 文档。"""
        entries_dict = []
        for entry in self._entries:
            entries_dict.append({
                "name": entry.name,
                "type": entry.type.value,
                "signature": entry.signature,
                "description": entry.description,
                "params": entry.params,
                "returns": entry.returns,
                "example": entry.example,
            })
        return json.dumps(entries_dict, ensure_ascii=False, indent=2)

    def scan_module(self, module: Any) -> list[DocEntry]:
        """扫描模块的文档。"""
        entries = []
        for name in dir(module):
            if name.startswith('_'):
                continue
            obj = getattr(module, name)
            doc = getattr(obj, '__doc__', '')
            entry = DocEntry(
                name=name,
                type=DocType.FUNCTION if callable(obj) else DocType.VARIABLE,
                description=doc[:200] if doc else ""
            )
            entries.append(entry)
        self._entries.extend(entries)
        return entries

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "entries": len(self._entries),
            "pages": len(self._pages),
        }


def create_doc_generator() -> MathaDocGenerator:
    """创建文档生成器。"""
    return MathaDocGenerator()


def _register_doc_generator(builtins: dict) -> None:
    """注册文档生成器内置函数。"""
    builtins["创建文档生成器"] = create_doc_generator


def _doc_generator_symtab_names() -> list[str]:
    return ["创建文档生成器"]


__all__ = [
    "DocType", "DocEntry", "DocPage", "MathaDocGenerator",
    "create_doc_generator",
    "_register_doc_generator", "_doc_generator_symtab_names",
]
