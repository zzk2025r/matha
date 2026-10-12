"""Matha 类型检查器：静态类型推断、类型验证、类型错误检测。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TypeKind(Enum):
    """类型种类。"""
    INT = "int"
    FLOAT = "float"
    STRING = "str"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    FUNCTION = "function"
    NONE = "None"
    UNKNOWN = "unknown"
    ANY = "any"


@dataclass
class TypeAnnotation:
    """类型注解。"""
    name: str
    kind: TypeKind
    generic: str | None = None
    nullable: bool = False

    def __str__(self) -> str:
        base = self.name
        if self.nullable:
            base += "?"
        return base


@dataclass
class TypeCheckResult:
    """类型检查结果。"""
    passed: bool
    errors: list[str]
    warnings: list[str]
    checked_count: int = 0


@dataclass
class TypeInference:
    """类型推断结果。"""
    variable: str
    inferred_type: str
    confidence: float = 1.0
    context: str = ""


class TypeChecker:
    """类型检查器：静态类型推断和验证。"""

    def __init__(self):
        self._type_defs: dict[str, TypeAnnotation] = {}
        self._errors: list[str] = []
        self._warnings: list[str] = []
        self._checked_count: int = 0
        self._initialized = False
        self._init_type_checker()

    def _init_type_checker(self) -> None:
        """初始化类型检查器。"""
        self._initialized = True
        # 预定义基本类型
        self._type_defs = {
            "int": TypeAnnotation("int", TypeKind.INT),
            "float": TypeAnnotation("float", TypeKind.FLOAT),
            "str": TypeAnnotation("str", TypeKind.STRING),
            "bool": TypeAnnotation("bool", TypeKind.BOOL),
            "list": TypeAnnotation("list", TypeKind.LIST),
            "dict": TypeAnnotation("dict", TypeKind.DICT),
            "None": TypeAnnotation("None", TypeKind.NONE),
            "any": TypeAnnotation("any", TypeKind.ANY),
        }

    def check_type(self, value: Any, expected_type: str) -> bool:
        """检查值是否符合类型。"""
        self._checked_count += 1
        actual = self._infer_type(value)
        if actual == expected_type or expected_type == "any":
            return True
        if expected_type == "int" and actual == "float":
            return True  # int 兼容 float
        self._errors.append(
            f"类型错误: 期望 {expected_type}, 实际 {actual}"
        )
        return False

    def infer_type(self, value: Any) -> str:
        """推断值的类型。"""
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "dict"
        if isinstance(value, tuple):
            return "tuple"
        if callable(value):
            return "function"
        return "unknown"

    def define_type(self, name: str, kind: TypeKind,
                     generic: str | None = None,
                     nullable: bool = False) -> None:
        """定义新类型。"""
        self._type_defs[name] = TypeAnnotation(
            name, kind, generic, nullable
        )

    def check_function_signature(self, func_name: str,
                                  arg_types: list[str],
                                  param_types: list[str],
                                  return_type: str
                                  ) -> tuple[bool, list[str]]:
        """检查函数签名。"""
        errors: list[str] = []
        # 检查参数数量
        if len(arg_types) != len(param_types):
            errors.append(
                f"参数数量不匹配: 函数 {func_name} 需要 {len(param_types)} 个参数, 提供了 {len(arg_types)} 个"
            )
            return False, errors
        # 检查参数类型
        for i, (arg_type, param_type) in enumerate(zip(arg_types, param_types)):
            if not self.check_type_by_name(arg_type, param_type):
                errors.append(
                    f"参数 {i} 类型不匹配: 期望 {param_type}, 实际 {arg_type}"
                )
        return len(errors) == 0, errors

    def check_type_by_name(self, actual: str, expected: str) -> bool:
        """通过名称检查类型兼容性。"""
        if expected == "any":
            return True
        if actual == expected:
            return True
        # 基本类型兼容
        compat = {
            ("int", "float"): True,
            ("float", "int"): True,
            ("int", "real"): True,
            ("float", "real"): True,
        }
        return compat.get((actual, expected), False)

    def validate_code(self, code: str) -> TypeCheckResult:
        """验证代码中的类型。"""
        # 简单的类型检查：查找类型注解并验证
        type_pattern = r'(\w+)\s*:\s*(\w+)'
        matches = re.findall(type_pattern, code)
        for var_name, type_name in matches:
            if type_name not in self._type_defs:
                self._warnings.append(
                    f"未知类型: {type_name} 用于变量 {var_name}"
                )
        return TypeCheckResult(
            len(self._errors) == 0,
            self._errors.copy(),
            self._warnings.copy(),
            self._checked_count
        )

    def get_type(self, name: str) -> TypeAnnotation | None:
        """获取类型定义。"""
        return self._type_defs.get(name)

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "types_defined": len(self._type_defs),
            "errors": len(self._errors),
            "warnings": len(self._warnings),
            "checked_count": self._checked_count,
        }


def check_type(value: Any, expected_type: str) -> bool:
    """检查值类型。"""
    tc = TypeChecker()
    return tc.check_type(value, expected_type)


def infer_type(value: Any) -> str:
    """推断类型。"""
    tc = TypeChecker()
    return tc.infer_type(value)


def define_type(name: str, kind: str, generic: str | None = None,
                nullable: bool = False) -> None:
    """定义类型。"""
    tc = TypeChecker()
    tc.define_type(name, TypeKind(kind), generic, nullable)


def _register_type_checker(builtins: dict) -> None:
    """注册类型检查内置函数。"""
    builtins["检查类型"] = check_type
    builtins["推断类型"] = infer_type
    builtins["定义类型"] = lambda n, k, g=None, nb=False: define_type(n, k, g, nb)


def _typechecker_symtab_names() -> list[str]:
    return ["检查类型", "推断类型", "定义类型"]


__all__ = [
    "TypeKind", "TypeAnnotation", "TypeCheckResult", "TypeInference",
    "TypeChecker",
    "check_type", "infer_type", "define_type",
    "_register_type_checker", "_typechecker_symtab_names",
]
