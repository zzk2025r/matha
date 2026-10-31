"""Matha 动态语义扩展层（plugin-accessible contracts，与 src/algebra 同构）。

设计定位（风险隔离）：
    与代数数层一致，本包是「核心契约 + 外部插件」的边界层，**不属于纯内核**。
    内核 / 执行器（如 SPIKE 的 RV32 模拟器、mbc VM）永不 import 本包；插件也
    永不 import 执行器内部类型 —— 两侧只通过本层声明的中性 ``DecodedInstr`` 与
    ``MachineView`` 协议通信。

用途（P1-4 预埋）：
    把「全动态 RV32IM 语义执行」关进可插拔的独立模块。当前本包只提供**接口 +
    空壳**（见 :mod:`src.dynamics.dynamic_semantics_plugin`），执行器默认走自身
    原有路径（未实现指令即显式报错），加载并接线后才启用插件语义。未加载时
    核心保持极简、极速、零风险。
"""
from __future__ import annotations

from src.dynamics.interface import (
    DecodedInstr,
    DynamicSemanticsBackend,
    DynamicSemanticsNotWired,
    MachineView,
    active_backend,
    execute_or_default,
    load_plugin,
    register_backend,
    set_active,
    unregister_backend,
)

__all__ = [
    "DecodedInstr",
    "MachineView",
    "DynamicSemanticsBackend",
    "DynamicSemanticsNotWired",
    "register_backend",
    "unregister_backend",
    "set_active",
    "active_backend",
    "load_plugin",
    "execute_or_default",
]
