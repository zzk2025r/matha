# -*- coding: utf-8 -*-
"""Matha 静态类型推断系统。

支持：
  - 基本类型推断：Int, Float, String, Bool, List[T], Dict[K,V]
  - 泛型类型：List<T>, Dict<K,V>, Option<T>
  - 函数类型推断：(A, B) -> C
  - 类型检查：编译期/运行期双重校验
  - 类型注解语法：x: Int = 1, func f(x: Float) -> String

使用方式：
  from src.type_system import TypeInferencer, TypeEnv
  inferencer = TypeInferencer()
  errors = inferencer.infer(program)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum, auto
import re


# ============================================================
# 类型定义
# ============================================================

class TypeKind(Enum):
    """类型分类。"""
    PRIMATIVE = auto()       # 基本类型: Int, Float, String, Bool
    GENERIC = auto()          # 泛型: List<T>, Dict<K,V>
    FUNCTION = auto()         # 函数类型: (A, B) -> C
    TUPLE = auto()            # 元组: (A, B, C)
    UNKNOWN = auto()          # 未推断
    ANY = auto()              # 任意类型（动态）


@dataclass(frozen=True)
class Type:
    """类型表示。"""
    kind: TypeKind
    name: str
    args: tuple["Type", ...] = ()  # 泛型参数

    def __str__(self) -> str:
        if self.args:
            return f"{self.name}[{', '.join(str(a) for a in self.args)}]"
        return self.name

    def __repr__(self) -> str:
        return f"Type({self})"

    # 基本类型工厂
    INT = None
    FLOAT = None
    STRING = None
    BOOL = None
    VOID = None
    ANY = None

    @staticmethod
    def list_of(element_type: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "List", (element_type,))

    @staticmethod
    def dict_of(key_type: "Type", value_type: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "Dict", (key_type, value_type))

    @staticmethod
    def tuple_of(*types: "Type") -> "Type":
        return Type(TypeKind.TUPLE, "Tuple", types)

    @staticmethod
    def function(params: tuple["Type", ...], return_type: "Type") -> "Type":
        return Type(TypeKind.FUNCTION, "Func", params + (return_type,))

    @staticmethod
    def option(element_type: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "Option", (element_type,))

    def is_numeric(self) -> bool:
        return self.name in ("Int", "Float")

    def is_container(self) -> bool:
        return self.name in ("List", "Dict")

    def element_type(self) -> Optional["Type"]:
        """获取泛型第一个参数（用于 List）。"""
        return self.args[0] if self.args else None

    def value_type(self) -> Optional["Type"]:
        """获取 Dict 的值类型。"""
        return self.args[1] if len(self.args) >= 2 else None


# 预定义基本类型
Type.INT = Type(TypeKind.PRIMATIVE, "Int")
Type.FLOAT = Type(TypeKind.PRIMATIVE, "Float")
Type.STRING = Type(TypeKind.PRIMATIVE, "String")
Type.BOOL = Type(TypeKind.PRIMATIVE, "Bool")
Type.VOID = Type(TypeKind.PRIMATIVE, "Void")
Type.ANY = Type(TypeKind.ANY, "Any")


# ============================================================
# 类型环境
# ============================================================

@dataclass
class TypeEnv:
    """类型环境：变量名 → 类型，函数名 → 函数类型。"""
    variables: dict[str, Type] = field(default_factory=dict)
    functions: dict[str, Type] = field(default_factory=dict)
    generics: dict[str, Type] = field(default_factory=dict)

    def define_var(self, name: str, typ: Type) -> None:
        self.variables[name] = typ

    def define_func(self, name: str, typ: Type) -> None:
        self.functions[name] = typ

    def get_var(self, name: str) -> Optional[Type]:
        return self.variables.get(name)

    def get_func(self, name: str) -> Optional[Type]:
        return self.functions.get(name)

    def merge(self, other: "TypeEnv") -> None:
        self.variables.update(other.variables)
        self.functions.update(other.functions)
        self.generics.update(other.generics)

    def copy(self) -> "TypeEnv":
        return TypeEnv(
            variables=dict(self.variables),
            functions=dict(self.functions),
            generics=dict(self.generics),
        )


# ============================================================
# 类型错误
# ============================================================

@dataclass
class TypeError:
    """类型错误。"""
    message: str
    line: int = 0
    col: int = 0
    severity: str = "error"  # "error" | "warning" | "hint"

    def __str__(self) -> str:
        loc = f"L{self.line}:C{self.col}: " if self.line else ""
        return f"[{self.severity.upper()}] {loc}{self.message}"


# ============================================================
# 类型推断器
# ============================================================

class TypeInferencer:
    """Matha 静态类型推断器。

    对 AST 执行类型推断，返回类型错误列表。
    """

    def __init__(self) -> None:
        self.errors: list[TypeError] = []
        self.env = TypeEnv()
        # 内建函数类型表
        self._init_builtin_types()

    def _init_builtin_types(self) -> None:
        """初始化内建函数类型。"""
        # 数学函数
        math_funcs = {
            "sin": Type.function((Type.FLOAT,), Type.FLOAT),
            "cos": Type.function((Type.FLOAT,), Type.FLOAT),
            "tan": Type.function((Type.FLOAT,), Type.FLOAT),
            "sqrt": Type.function((Type.FLOAT,), Type.FLOAT),
            "abs": Type.function((Type.FLOAT,), Type.FLOAT),
            "floor": Type.function((Type.FLOAT,), Type.INT),
            "ceil": Type.function((Type.FLOAT,), Type.INT),
            "round": Type.function((Type.FLOAT,), Type.INT),
            "log": Type.function((Type.FLOAT,), Type.FLOAT),
            "exp": Type.function((Type.FLOAT,), Type.FLOAT),
            "max": Type.function((Type.FLOAT, Type.FLOAT), Type.FLOAT),
            "min": Type.function((Type.FLOAT, Type.FLOAT), Type.FLOAT),
            "len": Type.function((Type.STRING,), Type.INT),
            "int": Type.function((Type.ANY,), Type.INT),
            "float": Type.function((Type.ANY,), Type.FLOAT),
            "str": Type.function((Type.ANY,), Type.STRING),
            "bool": Type.function((Type.ANY,), Type.BOOL),
        }
        for name, typ in math_funcs.items():
            self.env.define_func(name, typ)

        # 硬件内建
        hw_funcs = {
            "cpu核数": Type.function((Type.INT,), Type.INT),
            "平台": Type.function((Type.INT,), Type.STRING),
            "架构": Type.function((Type.INT,), Type.STRING),
            "ADC值": Type.function((Type.FLOAT, Type.FLOAT, Type.INT), Type.INT),
            "PWM占空比": Type.function((Type.FLOAT, Type.FLOAT), Type.FLOAT),
            "GPIO初始化": Type.function((Type.INT, Type.STRING), Type.VOID),
            "GPIO写入": Type.function((Type.INT, Type.INT), Type.VOID),
            "GPIO读取": Type.function((Type.INT,), Type.INT),
            "执行命令": Type.function((Type.STRING,), Type.ANY),
            "DNS解析": Type.function((Type.STRING,), Type.list_of(Type.STRING)),
        }
        for name, typ in hw_funcs.items():
            self.env.define_func(name, typ)

    def infer(self, program: Any) -> list[TypeError]:
        """对程序 AST 执行类型推断。

        Args:
            program: ast.Program 或其他 AST 节点

        Returns:
            类型错误列表
        """
        self.errors = []
        self.env = TypeEnv()
        self._init_builtin_types()

        if hasattr(program, "decls"):
            for decl in program.decls:
                self._infer_decl(decl)
        else:
            self.errors.append(TypeError(
                "类型推断：无效的 program 结构", severity="error"
            ))

        return self.errors

    def _infer_decl(self, decl: Any) -> None:
        """推断声明的类型。"""
        kind = type(decl).__name__

        if kind == "Binding":
            self._infer_binding(decl)
        elif kind == "FuncDef":
            self._infer_func_def(decl)
        elif kind == "MechUnit":
            if hasattr(decl, "body") and hasattr(decl.body, "stmts"):
                for stmt in decl.body.stmts:
                    self._infer_stmt(stmt)
        elif kind in ("Output", "OutputTrail"):
            if hasattr(decl, "expr") and decl.expr is not None:
                self._infer_expr(decl.expr)

    def _infer_binding(self, binding: Any) -> None:
        """推断变量绑定类型。"""
        name = self._get_var_name(binding.target)
        if name is None:
            return
        if hasattr(binding, "value"):
            typ = self._infer_expr(binding.value)
            self.env.define_var(name, typ)

    def _infer_func_def(self, func_def: Any) -> None:
        """推断函数定义类型。"""
        name = func_def.name
        param_types = []
        if hasattr(func_def, "params"):
            for param in func_def.params:
                if hasattr(param, "name"):
                    self.env.define_var(param.name, Type.ANY)
                    param_types.append(Type.ANY)
                elif isinstance(param, tuple):
                    param_types.append(self._infer_type_expr(param[1]) if len(param) > 1 else Type.ANY)

        return_type = Type.ANY
        if hasattr(func_def, "func_type"):
            return_type = self._infer_type_expr(func_def.func_type)

        func_type = Type.function(tuple(param_types), return_type)
        self.env.define_func(name, func_type)

        # 推断函数体
        if hasattr(func_def, "body") and hasattr(func_def.body, "expr"):
            body_type = self._infer_expr(func_def.body.expr)
            if body_type is not Type.ANY and not self._type_compatible(body_type, return_type):
                self.errors.append(TypeError(
                    f"函数 '{name}' 返回类型不匹配: "
                    f"期望 {return_type}, 实际 {body_type}",
                    line=getattr(func_def.body, "line", 0),
                ))

    def _infer_expr(self, expr: Any) -> Type:
        """推断表达式类型。"""
        if expr is None:
            return Type.VOID

        kind = type(expr).__name__

        if kind == "IntegerLit":
            return Type.INT
        if kind == "FloatLit":
            return Type.FLOAT
        if kind == "StringLit":
            return Type.STRING
        if kind == "BoolLit":
            return Type.BOOL

        elif kind == "Variable":
            name = expr.name
            typ = self.env.get_var(name)
            if typ is None:
                self.errors.append(TypeError(
                    f"未定义变量 '{name}'", line=getattr(expr, "line", 0)
                ))
                return Type.ANY
            return typ

        elif kind == "BinaryOp":
            return self._infer_binary_op(expr)

        elif kind == "UnaryOp":
            operand_type = self._infer_expr(expr.operand)
            if expr.op in ("+", "-", "~"):
                if not operand_type.is_numeric():
                    self.errors.append(TypeError(
                        f"一元运算符 {expr.op} 仅适用于数值类型，实际 {operand_type}",
                        line=getattr(expr, "line", 0)
                    ))
                return operand_type
            return operand_type

        elif kind == "FuncApp":
            return self._infer_func_app(expr)

        elif kind == "ListLiteral":
            if hasattr(expr, "items") and expr.items:
                first_type = self._infer_expr(expr.items[0])
                return Type.list_of(first_type)
            return Type.list_of(Type.ANY)

        elif kind == "IndexExpr":
            container_type = self._infer_expr(expr.container)
            if container_type.is_container() and container_type.name == "List":
                return container_type.element_type() or Type.ANY
            return Type.ANY

        elif kind == "SliceExpr":
            container_type = self._infer_expr(expr.container)
            if container_type.is_container():
                return Type.list_of(Type.ANY)
            return Type.ANY

        elif kind == "PathExpr":
            left_type = self._infer_expr(expr.left)
            if hasattr(expr, "right") and isinstance(expr.right, str):
                # 属性访问：返回 ANY（简化处理）
                return Type.ANY
            return left_type

        elif kind == "Lambda":
            param_types = [Type.ANY for _ in (expr.params or [])]
            return_type = Type.ANY
            if hasattr(expr, "body"):
                return_type = self._infer_expr(expr.body)
            return Type.function(tuple(param_types), return_type)

        elif kind in ("IfExpr", "IfStmt"):
            self._infer_expr(expr.cond)
            then_type = self._infer_expr(expr.then) if hasattr(expr, "then") else Type.ANY
            else_type = self._infer_expr(expr.else_) if hasattr(expr, "else_") else Type.ANY
            if not self._type_compatible(then_type, else_type):
                self.errors.append(TypeError(
                    f"if 表达式分支类型不匹配: {then_type} vs {else_type}",
                    line=getattr(expr, "line", 0)
                ))
            return then_type if then_type is not Type.ANY else else_type

        elif kind == "MatchStmt":
            return Type.VOID

        elif kind == "WhileStmt":
            self._infer_expr(expr.cond)
            return Type.VOID

        elif kind == "ForStmt":
            return Type.VOID

        else:
            return Type.ANY

    def _infer_binary_op(self, expr: Any) -> Type:
        """推断二元运算符类型。"""
        left_type = self._infer_expr(expr.left)
        right_type = self._infer_expr(expr.right)
        op = getattr(expr, "op", "")

        if op in ("+", "-", "*", "/", "%", "//"):
            if not (left_type.is_numeric() and right_type.is_numeric()):
                self.errors.append(TypeError(
                    f"算术运算符 '{op}' 要求数值类型，实际: {left_type} {op} {right_type}",
                    line=getattr(expr, "line", 0)
                ))
            return Type.FLOAT if op in ("/", "//", "%") else left_type

        elif op in ("=", "→"):
            # 赋值/等于比较
            return Type.BOOL

        elif op in ("<", ">", "<=", ">=", "!=", "∈"):
            return Type.BOOL

        elif op in ("and", "or"):
            if not (left_type == Type.BOOL and right_type == Type.BOOL):
                self.errors.append(TypeError(
                    f"逻辑运算符 '{op}' 要求布尔类型，实际: {left_type} {op} {right_type}",
                    line=getattr(expr, "line", 0)
                ))
            return Type.BOOL

        elif op == ">>":
            # Belongs 或位移
            return Type.BOOL if op == ">>" else Type.ANY

        elif op == " in ":
            return Type.BOOL

        else:
            return Type.ANY

    def _infer_func_app(self, expr: Any) -> Type:
        """推断函数调用类型。"""
        func_type = self._infer_expr(expr.func)
        arg_type = self._infer_expr(expr.arg)

        if func_type.kind == TypeKind.FUNCTION:
            params = func_type.args[:-1]
            return_type = func_type.args[-1]
            if len(params) == 1:
                if not self._type_compatible(arg_type, params[0]):
                    self.errors.append(TypeError(
                        f"函数参数类型不匹配: 期望 {params[0]}, 实际 {arg_type}",
                        line=getattr(expr, "line", 0)
                    ))
            return return_type

        # 内建函数类型查找
        if isinstance(expr.func, type) and hasattr(expr.func, "name"):
            name = expr.func.name
            built_in = self.env.get_func(name)
            if built_in and built_in.kind == TypeKind.FUNCTION:
                return built_in.args[-1]

        return Type.ANY

    def _infer_stmt(self, stmt: Any) -> None:
        """推断语句。"""
        kind = type(stmt).__name__
        if kind == "Binding":
            self._infer_binding(stmt)
        elif kind == "Output":
            if hasattr(stmt, "expr") and stmt.expr is not None:
                self._infer_expr(stmt.expr)
        elif kind == "LetBinding":
            if hasattr(stmt, "value"):
                typ = self._infer_expr(stmt.value)
                self.env.define_var(stmt.name, typ)
            if hasattr(stmt, "body") and stmt.body is not None:
                self._infer_stmt(stmt.body)
        elif hasattr(stmt, "stmts"):
            for s in stmt.stmts:
                self._infer_stmt(s)

    def _get_var_name(self, target: Any) -> Optional[str]:
        """获取变量名。"""
        if hasattr(target, "name"):
            return target.name
        return None

    def _type_compatible(self, source: Type, target: Type) -> bool:
        """检查类型兼容性。"""
        if source == Type.ANY or target == Type.ANY:
            return True
        if source == Type.VOID:
            return target == Type.VOID
        return source.name == target.name

    def _infer_type_expr(self, type_expr: Any) -> Type:
        """推断类型表达式。"""
        if isinstance(type_expr, str):
            type_map = {
                "Int": Type.INT, "Float": Type.FLOAT,
                "String": Type.STRING, "Bool": Type.BOOL,
                "Void": Type.VOID, "Any": Type.ANY,
                "List": Type.list_of(Type.ANY),
                "Dict": Type.dict_of(Type.ANY, Type.ANY),
            }
            return type_map.get(type_expr, Type.ANY)
        if hasattr(type_expr, "name"):
            return type_expr
        return Type.ANY


# ============================================================
# 类型检查器（运行期）
# ============================================================

class TypeChecker:
    """运行期类型检查器。"""

    TYPE_MAP = {
        "Int": (int,), "Integer": (int,),
        "Float": (float,), "Number": (int, float),
        "String": (str,), "Text": (str,),
        "Bool": (bool,), "Boolean": (bool,),
        "List": (list,), "Tuple": (tuple,),
        "Dict": (dict,), "Map": (dict,),
    }

    @classmethod
    def check(cls, value: Any, expected_type_name: str, var_name: str = "") -> bool:
        """运行期类型检查。"""
        expected = cls.TYPE_MAP.get(expected_type_name)
        if expected is None:
            return True  # 未知类型，跳过检查
        if not isinstance(value, expected):
            actual = type(value).__name__
            raise TypeError(
                f"类型错误 [{var_name}]: 期望 {expected_type_name}, "
                f"实际 {actual} ({value!r})"
            )
        return True

    @classmethod
    def check_numeric(cls, value: Any, var_name: str = "") -> bool:
        """检查数值类型。"""
        if not isinstance(value, (int, float)):
            raise TypeError(f"数值错误 [{var_name}]: 期望数字, 实际 {type(value).__name__}")
        return True

    @classmethod
    def coerce(cls, value: Any, target_type: str) -> Any:
        """类型转换。"""
        coerce_map = {
            "Int": int, "Integer": int,
            "Float": float, "Number": float,
            "String": str, "Text": str,
            "Bool": bool, "Boolean": bool,
        }
        fn = coerce_map.get(target_type)
        if fn is None:
            return value
        return fn(value)


# ============================================================
# 泛型支持
# ============================================================

class GenericType:
    """泛型类型支持。"""

    # 泛型参数映射
    _type_vars: dict[str, Type] = {}

    @classmethod
    def bind(cls, type_var: str, concrete_type: Type) -> None:
        """绑定泛型参数。"""
        cls._type_vars[type_var] = concrete_type

    @classmethod
    def resolve(cls, type_expr: Type) -> Type:
        """解析泛型类型。"""
        if type_expr.kind == TypeKind.GENERIC and type_expr.args:
            resolved_args = tuple(cls.resolve(arg) for arg in type_expr.args)
            return Type(type_expr.kind, type_expr.name, resolved_args)
        return type_expr

    @classmethod
    def infer_generic(cls, func_name: str, arg_types: tuple[Type, ...]) -> dict[str, Type]:
        """从函数调用推断泛型参数。"""
        # 简化实现：返回空映射
        return {}


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "Type", "TypeKind", "TypeEnv", "TypeError",
    "TypeInferencer", "TypeChecker", "GenericType",
]
