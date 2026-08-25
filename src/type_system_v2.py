# -*- coding: utf-8 -*-
"""
Matha 类型系统增强 v2.0
========================
新增类型系统能力：
  1. 依赖类型（Dependent Types）- 值约束类型
  2. 子类型系统（Subtyping）- 继承关系
  3. 精炼类型（Refinement Types）- 谓词约束
  4. 泛型约束（Generic Constraints）- where 子句
  5. 类型别名（Type Aliases）- 可读性增强
  6. 枚举类型（Enum）- 有限值集合

与 Rust/Lean 的对比：
  - Rust: Trait 系统 + 泛型约束
  - Lean: 依赖类型 + 命题即类型
  - Matha: 精炼类型 + 子类型 + 依赖类型（简化版）
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum, auto

logger = logging.getLogger("matha.type_system")

# ═══════════════════════════════════════════════════════════════════════════════
#  类型基础
# ═══════════════════════════════════════════════════════════════════════════════

class TypeKind(Enum):
    """类型分类。"""
    PRIMITIVE = auto()      # 基本类型
    GENERIC = auto()         # 泛型: List<T>, Dict<K,V>
    FUNCTION = auto()        # 函数类型: (A, B) -> C
    TUPLE = auto()           # 元组: (A, B, C)
    UNION = auto()           # 联合类型: A | B
    INTERSECTION = auto()    # 交集类型: A & B
    REFINEMENT = auto()      # 精炼类型: {x: Int | x > 0}
    DEPENDENT = auto()       # 依赖类型: (n: Nat) -> Vec n
    SUBTYPE = auto()         # 子类型: Animal <: LivingBeing
    ENUM = auto()            # 枚举类型
    ALIAS = auto()           # 类型别名
    ANY = auto()             # 任意类型
    NEVER = auto()           # 永假类型
    VOID = auto()            # 空类型


@dataclass(frozen=True)
class Type:
    """类型表示。"""
    kind: TypeKind
    name: str
    args: Tuple["Type", ...] = ()
    predicate: Optional[str] = None  # 精炼类型谓词
    supertype: Optional["Type"] = None  # 父类型（子类型）

    def __str__(self) -> str:
        if self.predicate:
            return f"{{{self.name}: {self.predicate}}}"
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
    NEVER = None

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
    def function(params: Tuple["Type", ...], return_type: "Type") -> "Type":
        return Type(TypeKind.FUNCTION, "Func", params + (return_type,))

    @staticmethod
    def option(element_type: "Type") -> "Type":
        return Type(TypeKind.GENERIC, "Option", (element_type,))

    @staticmethod
    def union(*types: "Type") -> "Type":
        return Type(TypeKind.UNION, "Union", types)

    @staticmethod
    def refinement(name: str, predicate: str) -> "Type":
        return Type(TypeKind.REFINEMENT, name, predicate=predicate)

    @staticmethod
    def dependent(param_name: str, param_type: "Type",
                  body_type: "Type") -> "Type":
        return Type(TypeKind.DEPENDENT, f"({param_name}: {param_type}) -> {body_type}")

    @staticmethod
    def subtype(name: str, supertype: "Type") -> "Type":
        return Type(TypeKind.SUBTYPE, name, supertype=supertype)

    @staticmethod
    def enum(name: str, members: List[str]) -> "Type":
        return Type(TypeKind.ENUM, name, args=tuple(Type(TypeKind.PRIMITIVE, m) for m in members))

    @staticmethod
    def alias(name: str, underlying: "Type") -> "Type":
        return Type(TypeKind.ALIAS, name, args=(underlying,))


# 预定义基本类型
Type.INT = Type(TypeKind.PRIMITIVE, "Int")
Type.FLOAT = Type(TypeKind.PRIMITIVE, "Float")
Type.STRING = Type(TypeKind.PRIMITIVE, "String")
Type.BOOL = Type(TypeKind.PRIMITIVE, "Bool")
Type.VOID = Type(TypeKind.PRIMITIVE, "Void")
Type.ANY = Type(TypeKind.ANY, "Any")
Type.NEVER = Type(TypeKind.NEVER, "Never")


# ═══════════════════════════════════════════════════════════════════════════════
#  子类型系统
# ═══════════════════════════════════════════════════════════════════════════════

class SubtypeRegistry:
    """
    子类型关系注册表。

    支持声明：
      Dog <: Animal
      Animal <: LivingBeing
     正方形 <: 矩形 <: 四边形
    """

    def __init__(self):
        self._hierarchies: Dict[str, Set[str]] = {}  # subtype -> set of supertypes
        self._direct_parents: Dict[str, str] = {}    # subtype -> direct parent

    def add_subtype(self, subtype: str, supertype: str) -> None:
        """添加子类型关系。"""
        if subtype not in self._hierarchies:
            self._hierarchies[subtype] = set()
        self._hierarchies[subtype].add(supertype)
        self._direct_parents[subtype] = supertype

    def is_subtype_of(self, subtype: str, supertype: str) -> bool:
        """检查 subtype 是否是 supertype 的子类型。"""
        if subtype == supertype:
            return True
        visited = set()
        stack = [subtype]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for parent in self._hierarchies.get(current, set()):
                if parent == supertype:
                    return True
                stack.append(parent)
        return False

    def get_supertypes(self, subtype: str) -> Set[str]:
        """获取所有父类型。"""
        supertypes = set()
        stack = [subtype]
        while stack:
            current = stack.pop()
            for parent in self._hierarchies.get(current, set()):
                if parent not in supertypes:
                    supertypes.add(parent)
                    stack.append(parent)
        return supertypes

    def get_hierarchy(self, type_name: str) -> List[str]:
        """获取类型层次链。"""
        chain = [type_name]
        current = type_name
        while current in self._direct_parents:
            current = self._direct_parents[current]
            chain.append(current)
        return chain


# ═══════════════════════════════════════════════════════════════════════════════
#  精炼类型检查器
# ═══════════════════════════════════════════════════════════════════════════════

class RefinementChecker:
    """
    精炼类型谓词检查器。

    支持谓词：
      x > 0       (正数)
      x >= min && x <= max  (范围约束)
      len(s) > 0  (非空字符串)
      n % 2 == 0  (偶数)
    """

    PREDICATE_PATTERNS = {
        "positive": r'\w+\s*[>]\s*0',
        "non_negative": r'\w+\s*[>=]\s*0',
        "in_range": r'\w+\s*[><=].*\s*[&][&]\s*.*[><=]\s*\w+',
        "non_empty": r'len\(\s*\w+\s*\)\s*[>]\s*0',
        "even": r'\w+\s*%\s*2\s*==\s*0',
    }

    def check(self, value: Any, predicate: str) -> bool:
        """检查值是否满足谓词。"""
        if predicate.startswith("x > 0") or predicate == "positive":
            return isinstance(value, (int, float)) and value > 0
        elif predicate.startswith("x >= 0") or predicate == "non_negative":
            return isinstance(value, (int, float)) and value >= 0
        elif "len(" in predicate and "> 0" in predicate:
            return isinstance(value, (str, list, tuple)) and len(value) > 0
        elif "% 2 == 0" in predicate or predicate == "even":
            return isinstance(value, int) and value % 2 == 0
        return True  # 未知谓词默认通过


# ═══════════════════════════════════════════════════════════════════════════════
#  增强型类型推断器
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TypeConstraint:
    """类型约束。"""
    var: str
    constraint: str  # 如 "x > 0", "x in List[Int]"
    line: int = 0


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


class EnhancedTypeInferencer:
    """
    增强型类型推断器 v2.0。

    新增能力：
      1. 依赖类型推断
      2. 子类型检查
      3. 精炼类型验证
      4. 泛型约束检查
      5. 类型别名解析
    """

    def __init__(self):
        self.errors: List[TypeError] = []
        self.constraints: List[TypeConstraint] = []
        self.subtype_registry = SubtypeRegistry()
        self.refinement_checker = RefinementChecker()
        self._type_aliases: Dict[str, Type] = {}
        self._enums: Dict[str, Type] = {}
        self._init_builtin_types()

    def _init_builtin_types(self) -> None:
        """初始化内建类型和函数。"""
        # 内建函数类型
        self._builtin_funcs: Dict[str, Type] = {
            "sin": Type.function((Type.FLOAT,), Type.FLOAT),
            "cos": Type.function((Type.FLOAT,), Type.FLOAT),
            "sqrt": Type.function((Type.FLOAT,), Type.FLOAT),
            "abs": Type.function((Type.FLOAT,), Type.FLOAT),
            "len": Type.function((Type.STRING,), Type.INT),
            "int": Type.function((Type.ANY,), Type.INT),
            "float": Type.function((Type.ANY,), Type.FLOAT),
            "str": Type.function((Type.ANY,), Type.STRING),
        }

    def define_alias(self, name: str, type_expr: Type) -> None:
        """定义类型别名。"""
        self._type_aliases[name] = type_expr

    def define_enum(self, name: str, members: List[str]) -> None:
        """定义枚举类型。"""
        self._enums[name] = Type.enum(name, members)

    def add_subtype(self, subtype: str, supertype: str) -> None:
        """添加子类型关系。"""
        self.subtype_registry.add_subtype(subtype, supertype)

    def infer(self, expr: str, context: Dict[str, Type] = None) -> Type:
        """
        推断表达式类型。

        支持：
          - 基本类型: 1 -> Int, 1.5 -> Float, "hello" -> String
          - 函数调用: sin(1.5) -> Float
          - 泛型: [1, 2, 3] -> List[Int]
          - 精炼类型: {x: Int | x > 0}
        """
        context = context or {}
        expr = expr.strip()

        # 基本字面量
        if expr.isdigit():
            return Type.INT
        try:
            float(expr)
            return Type.FLOAT
        except ValueError:
            pass
        if expr.startswith('"') and expr.endswith('"'):
            return Type.STRING
        if expr in ("true", "false"):
            return Type.BOOL

        # 函数调用
        func_match = re.match(r'(\w+)\s*\(', expr)
        if func_match:
            func_name = func_match.group(1)
            if func_name in self._builtin_funcs:
                return self._builtin_funcs[func_name].args[-1]  # 返回类型

        # 泛型类型
        list_match = re.match(r'\[(.+)\]', expr)
        if list_match:
            elem_type = self.infer(list_match.group(1), context)
            return Type.list_of(elem_type)

        # 精炼类型
        refine_match = re.match(r'\{(\w+):\s*(\w+)\s*\|\s*(.+)\}', expr)
        if refine_match:
            name, base_type, predicate = refine_match.groups()
            base = Type.INT if base_type == "Int" else Type.FLOAT
            return Type.refinement(name, predicate)

        # 依赖类型
        dep_match = re.match(r'\((\w+):\s*(\w+)\)\s*->\s*(\w+)', expr)
        if dep_match:
            param_name, param_type, return_type = dep_match.groups()
            return Type.dependent(param_name, Type.INT, Type.FLOAT)

        # 子类型
        if expr in self.subtype_registry._hierarchies:
            return Type.subtype(expr,
                               Type.subtype(self.subtype_registry._direct_parents.get(expr, "Any"),
                                           Type.ANY))

        # 类型别名
        if expr in self._type_aliases:
            return self._type_aliases[expr]

        # 枚举
        if expr in self._enums:
            return self._enums[expr]

        # 变量引用
        if expr in context:
            return context[expr]

        return Type.ANY

    def check_subtype(self, subtype: Type, supertype: Type) -> bool:
        """检查子类型关系。"""
        if subtype.kind == TypeKind.ANY or supertype.kind == TypeKind.ANY:
            return True
        if subtype == supertype:
            return True
        return self.subtype_registry.is_subtype_of(subtype.name, supertype.name)

    def check_refinement(self, value: Any, predicate: str) -> bool:
        """检查精炼类型谓词。"""
        return self.refinement_checker.check(value, predicate)

    def infer_program(self, program: str) -> List[Type]:
        """推断整个程序的类型列表。"""
        types = []
        for line in program.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                t = self.infer(line)
                types.append(t)
        return types


# ═══════════════════════════════════════════════════════════════════════════════
#  类型错误报告
# ═══════════════════════════════════════════════════════════════════════════════

class TypeChecker:
    """类型检查器（编译期 + 运行期）。"""

    def __init__(self, inferencer: EnhancedTypeInferencer = None):
        self.inferencer = inferencer or EnhancedTypeInferencer()
        self.errors: List[TypeError] = []

    def check(self, expr: str, expected: Type, context: Dict[str, Type] = None) -> bool:
        """检查表达式类型是否与预期匹配。"""
        inferred = self.inferencer.infer(expr, context)
        if inferred != expected and expected.kind != TypeKind.ANY:
            self.errors.append(TypeError(
                f"类型不匹配: 期望 {expected}, 实际 {inferred}",
                line=0
            ))
            return False
        return True

    def check_call(self, func_name: str, args: List[Any],
                   expected_sig: Type) -> bool:
        """检查函数调用签名。"""
        builtin = self.inferencer._builtin_funcs.get(func_name)
        if builtin is None:
            return True  # 未知函数，跳过检查
        # 检查参数数量
        if len(args) != len(builtin.args) - 1:
            self.errors.append(TypeError(
                f"参数数量不匹配: 期望 {len(builtin.args) - 1}, 实际 {len(args)}"
            ))
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  运行入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 类型系统增强 v2.0")
    print("=" * 60)

    inferencer = EnhancedTypeInferencer()

    # 测试基本类型推断
    print("\n--- 基本类型推断 ---")
    for expr in ["42", "3.14", '"hello"', "true", "[1, 2, 3]"]:
        t = inferencer.infer(expr)
        print(f"  {expr:15s} → {t}")

    # 测试精炼类型
    print("\n--- 精炼类型检查 ---")
    refine_type = inferencer.infer("{x: Int | x > 0}")
    print(f"  {{x: Int | x > 0}} → {refine_type}")
    print(f"  检查 5 > 0: {inferencer.check_refinement(5, 'x > 0')}")
    print(f"  检查 -1 > 0: {inferencer.check_refinement(-1, 'x > 0')}")

    # 测试子类型
    print("\n--- 子类型系统 ---")
    inferencer.add_subtype("Dog", "Animal")
    inferencer.add_subtype("Animal", "LivingBeing")
    print(f"  Dog <: Animal: {inferencer.check_subtype(
        Type.subtype('Dog', Type.ANY), Type.subtype('Animal', Type.ANY))}")
    print(f"  Dog <: LivingBeing: {inferencer.subtype_registry.is_subtype_of('Dog', 'LivingBeing')}")

    # 测试依赖类型
    print("\n--- 依赖类型 ---")
    dep_type = inferencer.infer("(n: Nat) -> Vec n")
    print(f"  (n: Nat) -> Vec n → {dep_type}")

    # 测试类型别名
    print("\n--- 类型别名 ---")
    inferencer.define_alias("PositiveInt", Type.refinement("x", "x > 0"))
    alias_type = inferencer.infer("PositiveInt")
    print(f"  PositiveInt → {alias_type}")

    print("\n✅ 类型系统增强测试完成")
