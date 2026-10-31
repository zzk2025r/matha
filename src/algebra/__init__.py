"""Matha 代数数处理扩展层（plugin-accessible contracts）。

设计定位（风险隔离）：
    本包是「核心契约 + 外部插件」的边界层，**不属于纯内核**
    （``src/kernel/``）。纯内核（lexer/parser/ast_nodes/kernel/mbc）永不 import
    本包，本包的插件也永不 import 纯内核内部类型 —— 两侧只通过本层声明的
    **中性代数项模型**与 **AlgebraicNumberPrinter 协议**通信。

    这样做的目的：把「精确代数数打印」等高级语义关进可插拔的独立模块，
    核心层的 103 个符号锁与基础指令集保持绝对不动；不加载插件时，门面走
    原有 double 打印路径，行为逐字不变。

用法（后续集成步，本步不含）：门面把内核符号表达式转成本层的中性 ``Term``，
调用 :func:`render_with_plugin`；未加载插件时返回默认渲染，加载
:mod:`src.algebra.algebra_plugin` 后返回精确根式渲染。
"""
from __future__ import annotations

from src.algebra.interface import (
    AlgebraicNumberPrinter,
    BinOp,
    Const,
    Symbol,
    Term,
    UnaryOp,
    active_printer,
    load_plugin,
    register_printer,
    render_default,
    render_with_plugin,
    decorate_numeric,
    set_active,
    unregister_printer,
)

__all__ = [
    "AlgebraicNumberPrinter",
    "Const",
    "Symbol",
    "BinOp",
    "UnaryOp",
    "Term",
    "register_printer",
    "unregister_printer",
    "set_active",
    "active_printer",
    "load_plugin",
    "render_default",
    "render_with_plugin",
    "decorate_numeric",
]
