"""内核符号引擎 · AST 节点体系（纯标准库）。

由原 `src/symbolic.py`「AST 节点体系」小节整体迁入，语义逐字保留。
`ASTNode` 是符号表达式的通用树形表示：`ast_to_dict` 与 LaTeX 发射都以它为中间层。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("matha.kernel.symbolic")


# ═══════════════════════════════════════════════════════════════════════════════
#  AST 节点体系
# ═══════════════════════════════════════════════════════════════════════════════

class ASTNodeType(str, Enum):
    NUM = "num"
    VAR = "var"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    POW = "pow"
    NEG = "neg"
    FUNC = "func"       # 函数调用 f(x)
    LAMBDA = "lambda"   # λx → expr
    APP = "app"         # 函数应用 f(x,y)
    LET = "let"         # 绑定 let x = expr
    IF = "if"           # 条件表达式
    SEQ = "seq"         # 顺序表达式
    ASSIGN = "assign"   # 赋值
    LIST = "list"       # 列表
    MAP = "map"         # 映射
    REDUCE = "reduce"   # 归约
    FILTER = "filter"   # 过滤


@dataclass
class ASTNode:
    """AST 节点：统一表示所有表达式和操作。"""
    node_type: ASTNodeType
    value: Any = None           # 数值字面量或变量名
    children: list[ASTNode] = field(default_factory=list)
    label: str = ""             # 标签（函数名等）
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.node_type.value,
            "value": self.value,
            "label": self.label,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        if self.node_type == ASTNodeType.NUM or self.node_type == ASTNodeType.VAR:
            return str(self.value)
        elif self.node_type == ASTNodeType.NEG:
            return f"(-{self.children[0]})"
        elif self.node_type in (ASTNodeType.ADD, ASTNodeType.SUB, ASTNodeType.MUL, ASTNodeType.DIV):
            ops = [str(c) for c in self.children]
            op = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/'}[self.node_type.value]
            return f"({ops[0]} {op} {ops[1]})"
        elif self.node_type == ASTNodeType.POW:
            return f"({self.children[0]} ^ {self.children[1]})"
        elif self.node_type == ASTNodeType.FUNC:
            args = ', '.join(str(c) for c in self.children)
            return f"{self.label}({args})"
        elif self.node_type == ASTNodeType.LAMBDA:
            param = self.label or "x"
            body = self.children[0] if self.children else "0"
            return f"λ{param}→{body}"
        elif self.node_type == ASTNodeType.LET:
            return f"let {self.label} = {self.children[0] if self.children else '?'}"
        elif self.node_type == ASTNodeType.IF:
            return f"if ({self.children[0]}) then {self.children[1]} else {self.children[2] if len(self.children) > 2 else '0'}"
        elif self.node_type == ASTNodeType.SEQ:
            return '; '.join(str(c) for c in self.children)
        elif self.node_type == ASTNodeType.LIST:
            return f"[{', '.join(str(c) for c in self.children)}]"
        return f"<{self.node_type.value}>"

    def __repr__(self):
        return f"ASTNode({self.node_type.value}, {self.value!r})"
