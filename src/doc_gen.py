# -*- coding: utf-8 -*-
"""Matha API 文档自动生成器

从源码中提取函数签名、类型注解、docstring，生成 Markdown 和 HTML 文档。

功能：
  1. 自动扫描 src/ 目录下的所有模块
  2. 提取类、函数、方法的签名和文档
  3. 生成 Markdown 格式 API 文档
  4. 生成 HTML 格式 API 文档（带导航）
  5. 生成 JSON 格式索引（供 IDE/工具使用）

用法：
  from src.doc_gen import DocGenerator
  gen = DocGenerator(src_dir="src", output_dir="docs")
  gen.generate_all()
"""
from __future__ import annotations
import ast
import importlib
import inspect
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# AST 节点提取
# ============================================================

@dataclass
class DocEntry:
    """文档条目。"""
    name: str
    kind: str  # "module", "class", "function", "method", "constant"
    module: str
    file: str
    line: int
    signature: str = ""
    docstring: str = ""
    params: List[Dict] = field(default_factory=list)
    returns: str = ""
    decorators: List[str] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)
    parent: Optional[str] = None
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "module": self.module,
            "file": self.file,
            "line": self.line,
            "signature": self.signature,
            "docstring": self.docstring[:200] if self.docstring else "",
            "params": self.params,
            "returns": self.returns,
            "decorators": self.decorators,
            "parent": self.parent,
        }


class DocExtractor(ast.NodeVisitor):
    """从 AST 中提取文档信息。"""

    def __init__(self, source_file: str, module_name: str):
        self._source_file = source_file
        self._module_name = module_name
        self._entries: List[DocEntry] = []
        self._current_class: Optional[str] = None
        self._indent_level = 0

    def visit_Module(self, node: ast.Module) -> None:
        """提取模块级文档。"""
        # 模块 docstring
        module_doc = ast.get_docstring(node)
        if module_doc:
            self._entries.append(DocEntry(
                name=self._module_name,
                kind="module",
                module=self._module_name,
                file=self._source_file,
                line=1,
                docstring=module_doc,
            ))

        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """提取类定义。"""
        docstring = ast.get_docstring(node)
        decorators = [self._decode_decorator(d) for d in node.decorator_list]

        # 构造签名
        bases = ", ".join(
            self._ast_to_str(base) for base in node.bases
        )
        sig = f"class {node.name}"
        if bases:
            sig += f"({bases})"

        entry = DocEntry(
            name=node.name,
            kind="class",
            module=self._module_name,
            file=self._source_file,
            line=node.lineno,
            signature=sig,
            docstring=docstring or "",
            decorators=decorators,
            parent=self._current_class,
        )
        self._entries.append(entry)

        # 保存当前类上下文
        old_class = self._current_class
        self._current_class = node.name

        for child in node.body:
            self.visit(child)

        self._current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """提取函数/方法定义。"""
        docstring = ast.get_docstring(node)
        decorators = [self._decode_decorator(d) for d in node.decorator_list]

        # 构造签名
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._ast_to_str(arg.annotation)}"
            args.append(arg_str)

        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        ret_type = ""
        if node.returns:
            ret_type = f" -> {self._ast_to_str(node.returns)}"

        sig = f"def {node.name}({', '.join(args)}){ret_type}"

        # 提取参数信息
        params = []
        for arg in node.args.args:
            param_info = {"name": arg.arg}
            if arg.annotation:
                param_info["type"] = self._ast_to_str(arg.annotation)
            if arg.arg in ('self', 'cls'):
                param_info["is_self"] = True
            params.append(param_info)

        entry = DocEntry(
            name=node.name,
            kind="method" if self._current_class else "function",
            module=self._module_name,
            file=self._source_file,
            line=node.lineno,
            signature=sig,
            docstring=docstring or "",
            params=params,
            returns=ret_type.replace(" -> ", ""),
            decorators=decorators,
            parent=self._current_class,
        )
        self._entries.append(entry)

        # 提取示例（从 docstring 中查找）
        if docstring:
            example_lines = []
            for line in docstring.split('\n'):
                if line.strip().startswith('>>>'):
                    example_lines.append(line.strip())
                elif example_lines and not line.strip().startswith(' '):
                    break
                elif example_lines:
                    example_lines.append(line.strip())
            if example_lines:
                entry.examples = example_lines[:5]

    def visit_Import(self, node: ast.Import) -> None:
        """记录导入。"""
        for alias in node.names:
            name = alias.asname or alias.name
            # 不记录标准库导入
            if not any(x in name for x in ['os', 'sys', 'json', 'math', 'typing']):
                pass

    def _decode_decorator(self, node: ast.expr) -> str:
        """将装饰器 AST 节点转换为字符串。"""
        try:
            return self._ast_to_str(node)
        except Exception:
            return "decorator"

    def _ast_to_str(self, node: ast.AST) -> str:
        """将 AST 节点转换为源码字符串。"""
        return ast.unparse(node)

    def get_entries(self) -> List[DocEntry]:
        """获取所有文档条目。"""
        return self._entries


# ============================================================
# 文档生成器
# ============================================================

class DocGenerator:
    """
    Matha API 文档自动生成器。

    生成格式：
      - Markdown (.md) — 适合 GitHub/文档站点
      - HTML (.html) — 适合浏览器查看
      - JSON (.json) — 适合 IDE/工具集成
    """

    def __init__(self, src_dir: str = "src", output_dir: str = "docs",
                 project_name: str = "Matha", project_version: str = "v3.0"):
        self._src_dir = Path(src_dir)
        self._output_dir = Path(output_dir)
        self._project_name = project_name
        self._project_version = project_version
        self._entries: List[DocEntry] = []
        self._modules: Dict[str, List[DocEntry]] = {}

    def generate_all(self) -> Dict[str, str]:
        """生成所有格式的文档。"""
        # 1. 扫描并提取
        self._scan_and_extract()

        # 2. 生成文档
        results = {}
        results["markdown"] = self._generate_markdown()
        results["html"] = self._generate_html()
        results["json"] = self._generate_json()

        return results

    def _scan_and_extract(self) -> None:
        """扫描源码目录并提取文档信息。"""
        self._entries = []
        self._modules = {}

        # 跳过私有文件和测试文件
        skip_prefixes = ('__', 'test_', 'conftest')

        for py_file in sorted(self._src_dir.glob("**/*.py")):
            # 跳过 __pycache__ 和 .pyc
            if '__pycache__' in str(py_file):
                continue
            if py_file.suffix != '.py':
                continue

            # 跳过测试文件
            if any(py_file.name.startswith(p) for p in skip_prefixes):
                continue

            module_name = self._get_module_name(py_file)
            if not module_name:
                continue

            try:
                source = py_file.read_text(encoding='utf-8')
                tree = ast.parse(source, filename=str(py_file))

                extractor = DocExtractor(str(py_file), module_name)
                extractor.visit(tree)

                file_entries = extractor.get_entries()
                self._entries.extend(file_entries)

                if module_name not in self._modules:
                    self._modules[module_name] = []
                self._modules[module_name].extend(file_entries)

            except SyntaxError as e:
                print(f"  [跳过] {py_file.name}: 语法错误 {e}")
            except Exception as e:
                print(f"  [跳过] {py_file.name}: {e}")

    def _get_module_name(self, path: Path) -> Optional[str]:
        """从文件路径推导模块名。"""
        try:
            rel = path.relative_to(self._src_dir)
            parts = list(rel.parts)
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]  # 移除 .py
            return ".".join(parts)
        except ValueError:
            return None

    def _generate_markdown(self) -> str:
        """生成 Markdown 文档。"""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "api_reference.md"

        lines = [
            f"# {self._project_name} API 参考文档",
            f"",
            f"> 自动生成于 {__import__('datetime').date.today()} | 版本 {self._project_version}",
            f"> 共 {len(self._entries)} 个文档条目",
            f"",
            f"## 目录",
            f"",
        ]

        # 目录
        for module_name in sorted(self._modules.keys()):
            module_entries = self._modules[module_name]
            classes = [e for e in module_entries if e.kind == "class"]
            functions = [e for e in module_entries if e.kind == "function"]
            methods = [e for e in module_entries if e.kind == "method"]

            if classes:
                lines.append(f"### {module_name}")
                lines.append("")
                for cls in classes:
                    lines.append(f"- [{cls.name}](`#class-{cls.name.lower()}`)")
                lines.append("")

            if functions:
                lines.append(f"**函数**")
                for fn in functions:
                    lines.append(f"- `{fn.signature}` — {fn.docstring[:60] if fn.docstring else ''}")
                lines.append("")

            if methods:
                lines.append(f"**方法**")
                for meth in methods:
                    lines.append(f"- `{meth.signature}`")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## 详细文档",
            "",
        ])

        # 详细条目
        for entry in sorted(self._entries, key=lambda e: (e.module, e.line)):
            lines.extend(self._entry_to_markdown(entry))

        content = "\n".join(lines)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(output_path)

    def _entry_to_markdown(self, entry: DocEntry) -> List[str]:
        """将单个条目转换为 Markdown。"""
        lines = []
        kind_prefix = {"class": "##", "function": "##", "method": "###", "module": "#"}
        prefix = kind_prefix.get(entry.kind, "##")

        lines.append(f"{prefix} `{entry.name}`")
        lines.append("")
        lines.append(f"```matha")
        lines.append(entry.signature)
        lines.append("```")
        lines.append("")

        if entry.docstring:
            lines.append(f"**描述**: {entry.docstring}")
            lines.append("")

        if entry.params:
            lines.append("| 参数 | 类型 | 说明 |")
            lines.append("|------|------|------|")
            for p in entry.params:
                ptype = p.get("type", "")
                lines.append(f"| `{p['name']}` | `{ptype}` | |")
            lines.append("")

        if entry.returns:
            lines.append(f"**返回**: `{entry.returns}`")
            lines.append("")

        if entry.decorators:
            lines.append(f"**装饰器**: {', '.join(entry.decorators)}")
            lines.append("")

        if entry.examples:
            lines.append("**示例**:")
            lines.append("```")
            for ex in entry.examples:
                lines.append(ex)
            lines.append("```")
            lines.append("")

        lines.append(f"Source: `{entry.file}:{entry.line}`")
        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _generate_html(self) -> str:
        """生成 HTML 文档。"""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "api_reference.html"

        html_parts = [
            f'<!DOCTYPE html>',
            f'<html lang="zh-CN">',
            f'<head>',
            f'  <meta charset="UTF-8">',
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'  <title>{self._project_name} API 参考</title>',
            f'  <style>',
            f'    * {{ box-sizing: border-box; }}',
            f'    body {{ font-family: "Segoe UI", sans-serif; margin: 0; padding: 0;',
            f'           background: #0f0f23; color: #e0e0e0; }}',
            f'    .sidebar {{ width: 280px; position: fixed; height: 100vh;',
            f'                overflow-y: auto; background: #16213e; padding: 20px; }}',
            f'    .sidebar h2 {{ color: #00d4ff; font-size: 16px; margin-top: 0; }}',
            f'    .sidebar a {{ color: #aaa; text-decoration: none; display: block;',
            f'                  padding: 4px 8px; border-radius: 4px; font-size: 13px; }}',
            f'    .sidebar a:hover {{ background: #1a1a3e; color: #fff; }}',
            f'    .content {{ margin-left: 300px; padding: 30px; }}',
            f'    h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}',
            f'    h2 {{ color: #00b4d8; margin-top: 40px; }}',
            f'    h3 {{ color: #48cae4; }}',
            f'    pre {{ background: #1a1a2e; padding: 15px; border-radius: 8px;',
            f'           overflow-x: auto; font-size: 13px; }}',
            f'    code {{ color: #90e0ef; font-family: "Consolas", monospace; }}',
            f'    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}',
            f'    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }}',
            f'    th {{ background: #16213e; color: #00d4ff; }}',
            f'    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;',
            f'               font-size: 11px; margin-right: 5px; }}',
            f'    .badge-class {{ background: #e94560; color: white; }}',
            f'    .badge-func {{ background: #0f3460; color: #00d4ff; }}',
            f'    .badge-method {{ background: #1a5276; color: #5dade2; }}',
            f'    .meta {{ color: #666; font-size: 12px; }}',
            f'  </style>',
            f'</head>',
            f'<body>',
        ]

        # Sidebar
        html_parts.append('<div class="sidebar">')
        html_parts.append('<h2>📚 导航</h2>')
        for module_name in sorted(self._modules.keys()):
            html_parts.append(f'<div style="margin-top:10px;color:#888;font-size:11px">{module_name}</div>')
            for entry in self._modules[module_name]:
                badge = "class" if entry.kind == "class" else "func" if entry.kind == "function" else "method"
                html_parts.append(
                    f'<a href="#{entry.kind}-{entry.name.lower()}">'
                    f'<span class="badge badge-{badge}">{entry.kind}</span> {entry.name}</a>'
                )
        html_parts.append('</div>')

        # Content
        html_parts.append('<div class="content">')
        html_parts.append(f'<h1>{self._project_name} API 参考</h1>')
        html_parts.append(f'<p class="meta">自动生成 | {self._project_version} | {len(self._entries)} 个条目</p>')

        for entry in sorted(self._entries, key=lambda e: (e.module, e.line)):
            html_parts.append(f'<h2 id="{entry.kind}-{entry.name.lower()}">')
            badge = f'<span class="badge badge-{entry.kind}">{entry.kind}</span>'
            html_parts.append(f'{badge} <code>{entry.name}</code>')
            html_parts.append(f'</h2>')

            html_parts.append('<pre><code>' + entry.signature + '</code></pre>')

            if entry.docstring:
                html_parts.append(f'<p><strong>描述</strong>: {entry.docstring}</p>')

            if entry.params:
                html_parts.append('<table><tr><th>参数</th><th>类型</th><th>说明</th></tr>')
                for p in entry.params:
                    ptype = p.get("type", "")
                    html_parts.append(f'<tr><td><code>{p["name"]}</code></td><td><code>{ptype}</code></td><td></td></tr>')
                html_parts.append('</table>')

            if entry.returns:
                html_parts.append(f'<p><strong>返回</strong>: <code>{entry.returns}</code></p>')

            html_parts.append(f'<p class="meta">来源: {entry.file}:{entry.line}</p>')
            html_parts.append('<hr>')

        html_parts.extend([
            '</div>',
            '</body>',
            '</html>',
        ])

        content = "\n".join(html_parts)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(output_path)

    def _generate_json(self) -> str:
        """生成 JSON 索引。"""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "api_index.json"

        index = {
            "project": self._project_name,
            "version": self._project_version,
            "generated": __import__('datetime').date.today().isoformat(),
            "total_entries": len(self._entries),
            "modules": {
                name: [e.to_dict() for e in entries]
                for name, entries in self._modules.items()
            },
            "summary": {
                "classes": len([e for e in self._entries if e.kind == "class"]),
                "functions": len([e for e in self._entries if e.kind == "function"]),
                "methods": len([e for e in self._entries if e.kind == "method"]),
                "modules": len(self._modules),
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        return str(output_path)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha API 文档生成器测试")
    print("=" * 60)

    gen = DocGenerator(src_dir="src", output_dir="docs",
                       project_name="Matha", project_version="v3.0")

    print("\n扫描源码目录...")
    gen._scan_and_extract()
    print(f"  发现 {len(gen._entries)} 个文档条目")
    print(f"  覆盖 {len(gen._modules)} 个模块")

    print("\n生成 Markdown 文档...")
    md_path = gen._generate_markdown()
    print(f"  ✓ {md_path}")

    print("\n生成 HTML 文档...")
    html_path = gen._generate_html()
    print(f"  ✓ {html_path}")

    print("\n生成 JSON 索引...")
    json_path = gen._generate_json()
    print(f"  ✓ {json_path}")

    # 统计
    classes = len([e for e in gen._entries if e.kind == "class"])
    functions = len([e for e in gen._entries if e.kind == "function"])
    methods = len([e for e in gen._entries if e.kind == "method"])
    print(f"\n统计: {classes} 个类, {functions} 个函数, {methods} 个方法")

    print("\n" + "=" * 60)
    print("  文档生成完成")
    print("=" * 60)
