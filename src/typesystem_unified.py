# -*- coding: utf-8 -*-
"""
Matha 类型系统统一层（Unified Type System）

合并 type_system_v2.py 和 typesystem_v2_fixed.py 的功能：
  - typesystem_v2_fixed: 约束求解器 + 生产版本（multi_lang_frontend/mir2_frontend 使用）
  - type_system_v2: 增强版本（依赖类型、子类型、精炼类型、EnhancedTypeInferencer）

统一后：
  - 所有 import 路径均有效（向后兼容）
  - typesystem_v2_fixed 作为底层实现
  - type_system_v2 作为增强层（继承/扩展）
"""
from __future__ import annotations

# ── 从 typesystem_v2_fixed 导入生产级实现 ──────────────────────────────────
from src.typesystem_v2_fixed import (  # noqa: F401
    Type,
    Constraint,
    ConstraintSolver,
    T_INT,
    T_FLOAT,
    T_STRING,
    T_BOOL,
    T_VOID,
    T_ANY,
    T_UNKNOWN,
    T_NUMERIC,
    T_COMPARABLE,
)

# ── 从 type_system_v2 导入增强功能 ──────────────────────────────────────────
from src.type_system_v2 import (  # noqa: F401
    TypeKind,
    SubtypeRegistry,
    RefinementChecker,
    EnhancedTypeInferencer,
    TypeConstraint,
    # 基本类型别名（与 typesystem_v2_fixed 一致）
    Type as TypeBase,
)

# ── 兼容性重命名：让两种 API 都能工作 ───────────────────────────────────────
# typesystem_v2_fixed 的 Type 是 dataclass，type_system_v2 的 Type 是 frozen dataclass
# 统一：使用 typesystem_v2_fixed 的 Type 作为主实现，添加增强方法

def UnifiedType(
    kind: str = "basic",
    name: str = "Any",
    args: list = None,
    constraints: list = None,
) -> Type:
    """统一类型工厂：兼容两种 API。"""
    if args is None:
        args = []
    if constraints is None:
        constraints = []
    return Type(kind=kind, name=name, args=args, constraints=constraints)


# ── 导出所有公共接口 ────────────────────────────────────────────────────────
__all__ = [
    # 核心类型
    "Type",
    "TypeKind",
    "UnifiedType",
    # 约束求解
    "Constraint",
    "ConstraintSolver",
    # 预定义类型
    "T_INT", "T_FLOAT", "T_STRING", "T_BOOL", "T_VOID", "T_ANY", "T_UNKNOWN",
    "T_NUMERIC", "T_COMPARABLE",
    # 增强功能
    "SubtypeRegistry",
    "RefinementChecker",
    "EnhancedTypeInferencer",
    "TypeConstraint",
    # 兼容性
    "TypeBase",
]
