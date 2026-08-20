# -*- coding: utf-8 -*-
"""matha-treesitter CLI 入口：python -m matha_treesitter"""
from __future__ import annotations
import argparse
import sys

from ._backends import (
    ASTNode, RustParser, GoParser, JSParser, CParser,
    get_parser, parse_source, is_cext_available,
)
from . import __version__


def _cli(args=None):
    parser = argparse.ArgumentParser(
        prog="matha-treesitter",
        description="Matha 高性能树形解析器 CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "language", choices=["rust", "go", "javascript", "c"],
        help="要解析的编程语言",
    )
    parser.add_argument("source", nargs="?", help="要解析的源代码（默认从 stdin 读取）")
    parser.add_argument("-o", "--output", choices=["dict", "tree"], default="tree",
                        help="输出格式（默认: tree）")

    ns = parser.parse_args(args)

    # 读取源码
    source = ns.source if ns.source else sys.stdin.read()
    if not source.strip():
        print("错误: 未提供源码（请通过参数或 stdin 传入）", file=sys.stderr)
        sys.exit(1)

    # 解析
    result = parse_source(ns.language, source)

    if ns.output == "dict":
        import json
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"# {ns.language} AST")
        print(f"root: {result.type} ({len(result.children)} children)")
        for child in result.children:
            print(f"  {child.type}: {child.value}")
            for key, val in child.fields.items():
                print(f"    .{key} = {val.value}")


def main():
    _cli()


if __name__ == "__main__":
    main()
