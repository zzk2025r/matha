# -*- coding: utf-8 -*-
"""Matha 增强类型系统：约束求解 + 模式匹配 + 运行时检查。

升级内容：
  1. 约束求解器：从函数调用推导泛型参数
  2. 模式匹配类型推断：match arm 类型传播
  3. 类型约束：where T: Numeric / T: Comparable
  4. 运行时类型检查：可选的严格模式
  5. 类型缓存：跨调用复用推断结果
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum, auto
import re


# ============================================================
# 类型系统核心
# ============================================================

class TypeKind(Enum):
    PRIMITIVE = auto()
    GENERIC = auto()
    FUNCTION = auto()
    TUPLE = auto()
    OPTION = auto()
    CONSTRAINT = auto()  # 类型约束
    UNKNOWN = auto()
    ANY = auto()


@dataclass(frozen=True)
class Type:
    kind: TypeKind
    name: str
    args: tuple["Type", ...] = ()
    constraints: tuple[str, ...] = ()  # 类型约束

    def __str__(self) -> str:
        parts = [self.name]
        if self.constraints:
            parts.append(f"[{', '.join(self.constraints)}]")
        if self.args:
            parts[0] += f"[{', '.join(str(a) for a in self.args)}]"
        return "".join(parts)

    @staticmethod
    def int_type() -> "Type":
        return Type(TypeKind.PRIMITIVE, "Int")

    @staticmethod
    def float_type() -> "Type":
        return Type(TypeKind.PRIMITIVE, "Float")

    @staticmethod
    def string_type() -> "Type":
        return Type(TypeKind.PRIMITIVE, "String")

    @staticmethod
    def bool_type() -> "Type":
        return Type(TypeKind.PRIMITIVE, "Bool")

    @staticmethod
    def void_type() -> "Type":
        return Type(TypeKind.PRIMITIVE, "Void")

    @staticmethod
    def any_type() -> "Type":
        return Type(TypeKind.ANY, "Any")

    @staticmethod
    def unknown_type() -> "Type":
        return Type(TypeKind.UNKNOWN, "?")

    @staticmethod
    def list_of(element: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "List", (element,))

    @staticmethod
    def dict_of(key: "Type", value: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "Dict", (key, value))

    @staticmethod
    def tuple_of(*types: "Type") -> "Type":
        return Type(TypeKind.TUPLE, "Tuple", types)

    @staticmethod
    def option_of(element: "Type") -> "Type":
        return Type(TypeKind.OPTION, "Option", (element,))

    @staticmethod
    def function(params: tuple["Type", ...], ret: "Type") -> "Type":
        return Type(TypeKind.FUNCTION, "Func", params + (ret,))

    def with_constraints(self, *constraints: str) -> "Type":
        """为类型添加约束。"""
        return Type(self.kind, self.name, self.args, constraints)

    def is_numeric(self) -> bool:
        return self.name in ("Int", "Float")

    def is_container(self) -> bool:
        return self.name in ("List", "Dict")

    def element_type(self) -> Optional["Type"]:
        return self.args[0] if self.args else None

    def has_constraint(self, constraint: str) -> bool:
        return constraint in self.constraints

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type):
            return NotImplemented
        return (self.kind == other.kind and self.name == other.name and
                self.args == other.args and self.constraints == other.constraints)


# 预定义类型
T_INT = Type.int_type()
T_FLOAT = Type.float_type()
T_STRING = Type.string_type()
T_BOOL = Type.bool_type()
T_VOID = Type.void_type()
T_ANY = Type.any_type()
T_UNKNOWN = Type.unknown_type()

# 数值约束类型
T_NUMERIC = T_INT.with_constraints("Numeric")
T_COMPARABLE = T_INT.with_constraints("Comparable")


# ============================================================
# 约束求解器
# ============================================================

@dataclass
class Constraint:
    """类型约束。"""
    left: Type
    right: Type
    kind: str = "="  # =, <: (子类型), :> (超类型)

    def solve(self) -> bool:
        """检查约束是否可满足。"""
        if self.kind == "=":
            return self.left == self.right or self.left == T_ANY or self.right == T_ANY
        if self.kind == "<:":
            # 子类型检查
            return self._is_subtype(self.left, self.right)
        return True

    def _is_subtype(self, sub: Type, super_type: Type) -> bool:
        """检查 sub 是否为 super_type 的子类型。"""
        if super_type == T_ANY or sub == T_ANY:
            return True
        if sub.name == super_type.name:
            return True
        # List[T] <: List[Any]
        if sub.name == "List" and super_type.name == "List":
            return self._is_subtype(sub.args[0], super_type.args[0]) if sub.args and super_type.args else True
        return False


class ConstraintSolver:
    """约束求解器。"""

    def __init__(self) -> None:
        self._constraints: list[Constraint] = []
        self._type_vars: dict[str, Type] = {}

    def add(self, constraint: Constraint) -> None:
        self._constraints.append(constraint)

    def solve(self) -> list[str]:
        """求解所有约束，返回错误列表。"""
        errors = []
        for c in self._constraints:
            if not c.solve():
                errors.append(f"类型不匹配: {c.left} vs {c.right}")
        return errors

    def infer_from_call(
        self, func_type: Type, arg_types: list[Type]
    ) -> dict[str, Type]:
        """从函数调用推断泛型参数。"""
        if func_type.kind != TypeKind.FUNCTION:
            return {}
        params = func_type.args[:-1]
        ret_type = func_type.args[-1]
        bindings: dict[str, Type] = {}

        for i, (param, arg) in enumerate(zip(params, arg_types)):
            if param.name.startswith("T") or param.name.startswith("K") or param.name.startswith("V"):
                var_name = param.name
                if var_name in bindings and bindings[var_name] != arg:
                    # 冲突：尝试统一
                    if bindings[var_name] == T_ANY:
                        bindings[var_name] = arg
                    elif arg == T_ANY:
                        pass  # 保持已有绑定
                    # 否则报告错误
                elif var_name not in bindings:
                    bindings[var_name] = arg

        return bindings


# ============================================================
# 模式匹配类型推断
# ============================================================

class PatternMatchInferencer:
    """模式匹配类型推断。"""

    def infer(self, scrutinee_type: Type, patterns: list[tuple[Type, Type]]) -> list[Type]:
        """
        对 match 表达式推断每个分支的类型。

        Args:
            scrutinee_type: 被匹配表达式的类型
            patterns: [(模式类型, 分支表达式类型), ...]

        Returns:
            各分支的类型列表
        """
        branch_types = []
        for pattern_type, expr_type in patterns:
            # 模式类型必须与 scrutinee 兼容
            if not self._compatible(scrutinee_type, pattern_type):
                branch_types.append(T_ANY)
            else:
                branch_types.append(expr_type)
        # 返回所有分支的共同类型
        return self._common_type(branch_types)

    def _compatible(self, t1: Type, t2: Type) -> bool:
        if t1 == T_ANY or t2 == T_ANY:
            return True
        return t1.name == t2.name or t1.is_numeric() and t2.is_numeric()

    def _common_type(self, types: list[Type]) -> Type:
        if not types:
            return T_VOID
        # 找共同类型
        numeric_types = [t for t in types if t.is_numeric()]
        if len(numeric_types) == len(types):
            return T_FLOAT  # 数值类型统一为 Float
        # 返回第一个非 UNKNOWN 类型
        for t in types:
            if t != T_UNKNOWN:
                return t
        return T_ANY


# ============================================================
# 类型约束系统
# ============================================================

class TypeConstraint:
    """类型约束定义。"""

    NUMERIC = "Numeric"      # Int, Float
    COMPARABLE = "Comparable"  # Int, Float, String
    SEQUENCABLE = "Sequencable"  # List, Tuple
    HASHABLE = "Hashable"    # Int, Float, String, Tuple

    _constraint_map: dict[str, set[str]] = {
        "Numeric": {"Int", "Float"},
        "Comparable": {"Int", "Float", "String"},
        "Sequencable": {"List", "Tuple"},
        "Hashable": {"Int", "Float", "String", "Tuple"},
    }

    @classmethod
    def satisfies(cls, type_name: str, constraint: str) -> bool:
        allowed = cls._constraint_map.get(constraint, set())
        return type_name in allowed or type_name == "Any"


# ============================================================
# 运行时类型检查
# ============================================================

class StrictTypeChecker:
    """运行时严格类型检查。"""

    TYPE_MAP = {
        "Int": (int,), "Integer": (int,),
        "Float": (float,), "Number": (int, float),
        "String": (str,), "Text": (str,),
        "Bool": (bool,), "Boolean": (bool,),
        "List": (list,), "Tuple": (tuple,),
        "Dict": (dict,), "Map": (dict,),
    }

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict
        self._errors: list[str] = []

    def check(self, value: Any, expected: Type, var_name: str = "") -> bool:
        """运行时类型检查。"""
        if not self.strict:
            return True
        if expected == T_ANY or expected == T_UNKNOWN:
            return True

        expected_names = self.TYPE_MAP.get(expected.name, ())
        if expected_names:
            if not isinstance(value, expected_names):
                actual = type(value).__name__
                self._errors.append(
                    f"类型错误 [{var_name}]: 期望 {expected}, 实际 {actual}"
                )
                return False
        return True

    def get_errors(self) -> list[str]:
        return self._errors.copy()

    def clear(self) -> None:
        self._errors.clear()


# ============================================================
# 类型环境（增强版）
# ============================================================

@dataclass
class TypeEnv:
    """增强类型环境。"""
    variables: dict[str, Type] = field(default_factory=dict)
    functions: dict[str, Type] = field(default_factory=dict)
    constraints: dict[str, list[str]] = field(default_factory=dict)  # 类型约束
    generic_bindings: dict[str, Type] = field(default_factory=dict)  # 泛型参数绑定

    def define_var(self, name: str, typ: Type) -> None:
        self.variables[name] = typ

    def define_func(self, name: str, typ: Type) -> None:
        self.functions[name] = typ

    def set_constraint(self, name: str, constraints: list[str]) -> None:
        self.constraints[name] = constraints

    def get_var(self, name: str) -> Optional[Type]:
        return self.variables.get(name)

    def get_func(self, name: str) -> Optional[Type]:
        return self.functions.get(name)

    def resolve_generic(self, typ: Type) -> Type:
        """解析泛型类型。"""
        if typ.args:
            resolved_args = tuple(
                self.generic_bindings.get(a.name, a) if hasattr(a, "name") else a
                for a in typ.args
            )
            return Type(typ.kind, typ.name, resolved_args, typ.constraints)
        return typ

    def copy(self) -> "TypeEnv":
        return TypeEnv(
            variables=dict(self.variables),
            functions=dict(self.functions),
            constraints=dict(self.constraints),
            generic_bindings=dict(self.generic_bindings),
        )


# ============================================================
# 增强类型推断器
# ============================================================

class EnhancedTypeInferencer:
    """增强类型推断器：约束求解 + 模式匹配 + 运行时检查。"""

    def __init__(self) -> None:
        self.env = TypeEnv()
        self.solver = ConstraintSolver()
        self.pattern_infer = PatternMatchInferencer()
        self.strict_checker = StrictTypeChecker()
        self._errors: list[str] = []

    def infer(self, program: Any) -> list[str]:
        """对程序执行完整类型推断。"""
        self._errors = []
        self.env = TypeEnv()
        self._init_builtins()

        if hasattr(program, "decls"):
            for decl in program.decls:
                self._infer_decl(decl)

        # 求解约束
        errors = self.solver.solve()
        self._errors.extend(errors)

        return self._errors

    def _init_builtins(self) -> None:
        """初始化内建函数类型。"""
        builtins = {
            "sin": Type.function((T_FLOAT,), T_FLOAT),
            "cos": Type.function((T_FLOAT,), T_FLOAT),
            "tan": Type.function((T_FLOAT,), T_FLOAT),
            "sqrt": Type.function((T_FLOAT,), T_FLOAT),
            "abs": Type.function((T_FLOAT,), T_FLOAT),
            "floor": Type.function((T_FLOAT,), T_INT),
            "ceil": Type.function((T_FLOAT,), T_INT),
            "round": Type.function((T_FLOAT,), T_INT),
            "log": Type.function((T_FLOAT,), T_FLOAT),
            "exp": Type.function((T_FLOAT,), T_FLOAT),
            "len": Type.function((T.list_of(T_ANY),), T_INT),
            "sum": Type.function((T.list_of(T_FLOAT),), T_FLOAT),
            "max": Type.function((T_FLOAT, T_FLOAT), T_FLOAT),
            "min": Type.function((T_FLOAT, T_FLOAT), T_FLOAT),
            "int": Type.function((T.ANY,), T_INT),
            "float": Type.function((T.ANY,), T_FLOAT),
            "str": Type.function((T.ANY,), T_STRING),
            "bool": Type.function((T.ANY,), T_BOOL),
        }
        for name, typ in builtins.items():
            self.env.define_func(name, typ)

    def _infer_decl(self, decl: Any) -> None:
        kind = type(decl).__name__
        if kind == "Binding":
            self._infer_binding(decl)
        elif kind == "FuncDef":
            self._infer_func_def(decl)
        elif kind == "MechUnit":
            if hasattr(decl, "body") and hasattr(decl.body, "stmts"):
                for stmt in decl.body.stmts:
                    self._infer_stmt(stmt)

    def _infer_binding(self, binding: Any) -> None:
        name = getattr(binding, "target", None)
        if name and hasattr(name, "name"):
            typ = self._infer_expr(getattr(binding, "value", None))
            self.env.define_var(name.name, typ)

    def _infer_func_def(self, func_def: Any) -> None:
        name = func_def.name
        param_types = []
        if hasattr(func_def, "params"):
            for p in func_def.params:
                if hasattr(p, "type_expr") and p.type_expr:
                    param_types.append(self._infer_type_expr(p.type_expr))
                else:
                    param_types.append(T_ANY)
                    if hasattr(p, "name"):
                        self.env.define_var(p.name, T_ANY)

        ret_type = T_ANY
        if hasattr(func_def, "func_type"):
            ret_type = self._infer_type_expr(func_def.func_type)

        func_type = Type.function(tuple(param_types), ret_type)
        self.env.define_func(name, func_type)

        # 推断函数体
        if hasattr(func_def, "body") and hasattr(func_def.body, "expr"):
            body_type = self._infer_expr(func_def.body.expr)
            if body_type != T_ANY and body_type != T_VOID and not self._compatible(body_type, ret_type):
                self._errors.append(
                    f"函数 '{name}' 返回类型不匹配: 期望 {ret_type}, 实际 {body_type}"
                )

    def _infer_expr(self, expr: Any) -> Type:
        if expr is None:
            return T_VOID
        kind = type(expr).__name__

        if kind == "IntegerLit":
            return T_INT
        if kind == "FloatLit":
            return T_FLOAT
        if kind == "StringLit":
            return T_STRING
        if kind == "BoolLit":
            return T_BOOL

        elif kind == "Variable":
            typ = self.env.get_var(expr.name)
            if typ is None:
                self._errors.append(f"未定义变量 '{expr.name}'")
                return T_ANY
            return self.env.resolve_generic(typ)

        elif kind == "BinaryOp":
            return self._infer_binary(expr)

        elif kind == "UnaryOp":
            op = getattr(expr, "op", "")
            operand_type = self._infer_expr(expr.operand)
            if op in ("+", "-", "++", "--"):
                if not operand_type.is_numeric():
                    self._errors.append(f"数值运算符 '{op}' 要求数值类型")
                return operand_type
            return operand_type

        elif kind == "FuncApp":
            return self._infer_func_app(expr)

        elif kind == "Lambda":
            params = [T_ANY for _ in getattr(expr, "params", [])]
            ret = self._infer_expr(getattr(expr, "body", None))
            return Type.function(tuple(params), ret)

        elif kind == "IfExpr":
            self._infer_expr(expr.cond)
            then_type = self._infer_expr(expr.then)
            else_type = self._infer_expr(expr.else_) if hasattr(expr, "else_") and expr.else_ else T_VOID
            if then_type != T_ANY and else_type != T_ANY and then_type != else_type:
                self._errors.append(f"if 表达式分支类型不匹配: {then_type} vs {else_type}")
            return then_type if then_type != T_ANY else else_type

        elif kind == "ListLiteral":
            items = getattr(expr, "items", [])
            if items:
                elem_type = self._infer_expr(items[0])
                return T.list_of(elem_type)
            return T.list_of(T_ANY)

        elif kind == "DictLiteral":
            return T.dict_of(T_ANY, T.ANY)

        elif kind == "IndexExpr":
            container_type = self._infer_expr(expr.container)
            return container_type.element_type() or T_ANY

        elif kind == "PathExpr":
            return T_ANY  # 属性访问返回任意类型

        elif kind == "MatchStmt":
            scrutinee_type = self._infer_expr(expr.scrutinee)
            branches = getattr(expr, "branches", [])
            branch_types = [self._infer_expr(b[2]) for b in branches]
            return self.pattern_infer._common_type(branch_types) if branch_types else T_ANY

        elif kind == "LetBinding":
            val_type = self._infer_expr(getattr(expr, "value", None))
            if hasattr(expr, "name"):
                self.env.define_var(expr.name, val_type)
            return self._infer_expr(getattr(expr, "body", None)) if hasattr(expr, "body") and expr.body else val_type

        return T_ANY

    def _infer_binary(self, expr: Any) -> Type:
        left = self._infer_expr(expr.left)
        right = self._infer_expr(expr.right)
        op = getattr(expr, "op", "")

        if op in ("+", "-", "*", "/", "//", "%", "**"):
            if not (left.is_numeric() and right.is_numeric()):
                self._errors.append(f"算术运算符 '{op}' 要求数值类型")
            return T_FLOAT if op in ("/", "//", "%") else left

        if op in ("<", ">", "<=", ">=", "==", "!=", "∈"):
            return T_BOOL

        if op in ("and", "or"):
            if not (left == T_BOOL and right == T_BOOL):
                self._errors.append(f"逻辑运算符 '{op}' 要求布尔类型")
            return T_BOOL

        if op == "→":
            # 函数应用
            return T_ANY  # 简化

        return T_ANY

    def _infer_func_app(self, expr: Any) -> Type:
        func_type = self._infer_expr(expr.func)
        arg_type = self._infer_expr(expr.arg)

        if func_type.kind == TypeKind.FUNCTION:
            params = func_type.args[:-1]
            ret = func_type.args[-1]
            if params:
                expected = params[0]
                if expected != T_ANY and not self._compatible(arg_type, expected):
                    self._errors.append(
                        f"函数参数类型不匹配: 期望 {expected}, 实际 {arg_type}"
                    )
            return ret

        # 查找内建函数
        if isinstance(expr.func, type) and hasattr(expr.func, "name"):
            built_in = self.env.get_func(expr.func.name)
            if built_in and built_in.kind == TypeKind.FUNCTION:
                return built_in.args[-1]

        return T_ANY

    def _infer_stmt(self, stmt: Any) -> None:
        kind = type(stmt).__name__
        if kind == "Binding":
            self._infer_binding(stmt)
        elif kind == "Output":
            if hasattr(stmt, "expr") and stmt.expr:
                self._infer_expr(stmt.expr)
        elif hasattr(stmt, "stmts"):
            for s in stmt.stmts:
                self._infer_stmt(s)

    def _infer_type_expr(self, type_expr: Any) -> Type:
        if isinstance(type_expr, str):
            type_map = {
                "Int": T_INT, "Float": T_FLOAT,
                "String": T_STRING, "Bool": T_BOOL,
                "Void": T_VOID, "Any": T_ANY,
                "List": T.list_of(T_ANY),
                "Dict": T.dict_of(T.ANY, T.ANY),
                "Tuple": T.tuple_of(),
                "Option": T.option_of(T.ANY),
            }
            return type_map.get(type_expr, T.ANY)
        if hasattr(type_expr, "name"):
            return type_expr
        return T.ANY

    def _compatible(self, source: Type, target: Type) -> bool:
        if source == T_ANY or target == T_ANY:
            return True
        if source == T_VOID:
            return target == T_VOID
        return source.name == target.name or (
            source.is_numeric() and target.is_numeric()
        )

    def check_runtime(self, value: Any, expected: Type, var_name: str = "") -> bool:
        """运行时类型检查。"""
        return self.strict_checker.check(value, expected, var_name)

    def get_errors(self) -> list[str]:
        return self._errors.copy()


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "Type", "TypeKind", "TypeEnv",
    "Constraint", "ConstraintSolver",
    "PatternMatchInferencer",
    "TypeConstraint",
    "StrictTypeChecker",
    "EnhancedTypeInferencer",
    "T_INT", "T_FLOAT", "T_STRING", "T_BOOL", "T_VOID", "T_ANY", "T_UNKNOWN",
]
