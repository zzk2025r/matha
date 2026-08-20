# -*- coding: utf-8 -*-
"""Matha 可视化编程器 - 主模块

提供完整的节点式可视化编程体验：
  - 节点注册表（60+ 节点类型）
  - 拓扑执行引擎（循环检测 + 拓扑排序）
  - 图序列化/反序列化
  - 增量执行
"""
from __future__ import annotations

from src.visual_editor.node_types import (
    NodeType,
    Node,
    NodeDefinition,
    PortDefinition,
    NodeRegistry,
    register_all_nodes,
)
from src.visual_editor.node_executor import (
    NodeExecutor,
    NodeExecutionResult,
    ExecutionStatus,
    GraphMetrics,
    ExecutionError,
    get_executor,
)

__all__ = [
    # 节点类型
    "NodeType",
    "Node",
    "NodeDefinition",
    "PortDefinition",
    "NodeRegistry",
    "register_all_nodes",
    # 执行引擎
    "NodeExecutor",
    "NodeExecutionResult",
    "ExecutionStatus",
    "GraphMetrics",
    "ExecutionError",
    "get_executor",
]

__version__ = "1.0.0"
