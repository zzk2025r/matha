# -*- coding: utf-8 -*-
"""Matha AST 序列化器：把 Matha 程序的 AST 导出为 JSON。

让任何编程语言（Python/JavaScript/Rust/Go/Java...）都能识别解读 Matha 程序结构。

设计：
  - ast_to_dict(node)   → 把任意 AST 节点转为 dict
  - ast_to_json(node)   → 把任意 AST 节点转为 JSON 字符串
  - program_to_dict(src) → 把 Matha 源码解析为 dict 形式的 AST
  - program_to_json(src) → 把 Matha 源码解析为 JSON 字符串

JSON 格式规范：
  每个节点 = {"node": <类型名>, <字段名>: <字段值>, ...}
  列表字段保持列表，嵌套节点递归序列化。
  字面量值直接存储（int/float/str/bool/None）。

示例：
  Matha 源码  #：{ x = 3 + 4  #：[x] }
  → JSON:
  {
    "node": "Program",
    "decls": [{
      "node": "MechUnit",
      "generate": {"node": "Generate", "seg_id": 1, "form": "seg"},
      "body": {"node": "CodeBlock", "stmts": [
        {"node": "Binding",
         "target": {"node": "Variable", "name": "x"},
         "value": {"node": "BinaryOp", "op": "+",
                   "left": {"node": "IntegerLit", "value": 3},
                   "right": {"node": "IntegerLit", "value": 4}}
        },
        {"node": "Output", "expr": {"node": "Variable", "name": "x"}}
      ]}
    }]
  }
"""

from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass, fields
from typing import Any

from src.parser import Parser
from src import ast_nodes as ast


def _node_to_dict(node: Any) -> Any:
    """递归把 AST 节点（或普通值）转为可 JSON 序列化的结构。"""
    # None / bool / int / float / str → 原样
    if node is None or isinstance(node, (bool, int, float, str)):
        return node

    # 列表/元组 → 递归
    if isinstance(node, (list, tuple)):
        return [_node_to_dict(item) for item in node]

    # dict → 递归值
    if isinstance(node, dict):
        return {k: _node_to_dict(v) for k, v in node.items()}

    # dataclass AST 节点 → {"node": 类型名, 字段...}
    if is_dataclass(node):
        result: dict[str, Any] = {"node": type(node).__name__}
        for f in fields(node):
            val = getattr(node, f.name)
            result[f.name] = _node_to_dict(val)
        return result

    # 其它对象 → 字符串兜底
    return str(node)


def ast_to_dict(node: Any) -> dict | list | Any:
    """把任意 AST 节点转为 dict/list/基础值。"""
    return _node_to_dict(node)


def ast_to_json(node: Any, indent: int = 2) -> str:
    """把任意 AST 节点转为 JSON 字符串。"""
    return json.dumps(_node_to_dict(node), ensure_ascii=False, indent=indent)


def program_to_dict(source: str) -> dict:
    """把 Matha 源码解析为 dict 形式的 AST。"""
    program = Parser(source).parse()
    return _node_to_dict(program)


def program_to_json(source: str, indent: int = 2) -> str:
    """把 Matha 源码解析为 JSON 字符串形式的 AST。"""
    return json.dumps(program_to_dict(source), ensure_ascii=False, indent=indent)


def tokens_to_dict(source: str) -> list[dict]:
    """把 Matha 源码的 Token 流导出为 dict 列表（供其它语言做词法分析）。"""
    from src.lexer import Lexer
    toks = []
    for t in Lexer(source).tokenize():
        toks.append({
            "type": t.type.name,
            "value": t.value,
            "line": t.line,
            "col": t.col,
        })
    return toks


def tokens_to_json(source: str, indent: int = 2) -> str:
    """把 Token 流导出为 JSON。"""
    return json.dumps(tokens_to_dict(source), ensure_ascii=False, indent=indent)
