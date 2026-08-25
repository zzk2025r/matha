# -*- coding: utf-8 -*-
"""
Matha 多语言前端实现 - 将其他语言源码转换为 Matha MIR

当前实现：
  - Python → Matha MIR (基于 AST 模块)
  - 预留接口：Rust/Go/JS/C → Matha MIR

设计原则：
  1. 每门语言有独立的前端模块
  2. 统一输出 MIR²（二级中间表示）
  3. 类型推断 + 效应分析
  4. 错误恢复 + 渐进式解析
"""
from __future__ import annotations
import ast
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.typesystem_v2_fixed import T_FLOAT, T_INT, T_BOOL, T_STRING, T_ANY


class Effect(Enum):
    """效应类型。"""
    PURE = "pure"          # 无副作用
    IO = "io"              # 输入输出
    STATE = "state"        # 可变状态
    EXCEPTION = "exception"  # 异常抛出
    CONCURRENT = "concurrent"  # 并发
    ASYNC = "async"        # 异步


class TypeInfo(Enum):
    """类型信息。"""
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    LIST = "list"
    DICT = "dict"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass
class MIR2Expr:
    """MIR² 表达式。"""
    kind: str
    value: Any = None
    op: Optional[str] = None
    operands: list = field(default_factory=list)
    result_var: str = ""
    effect: Effect = Effect.PURE
    typ: TypeInfo = TypeInfo.UNKNOWN

    def __repr__(self):
        return f"MIR2Expr({self.kind}, op={self.op}, typ={self.typ}, effect={self.effect})"


@dataclass
class MIR2Function:
    """MIR² 函数。"""
    name: str
    params: list = field(default_factory=list)
    param_types: list = field(default_factory=list)
    return_type: TypeInfo = TypeInfo.UNKNOWN
    effect: Effect = Effect.PURE
    body: list = field(default_factory=list)
    locals: dict = field(default_factory=dict)


@dataclass
class MIR2Program:
    """MIR² 程序。"""
    functions: dict = field(default_factory=dict)
    globals: dict = field(default_factory=dict)
    imports: list = field(default_factory=list)
    effects: dict = field(default_factory=dict)


# ============================================================
# Python 前端
# ============================================================

class PythonFrontend:
    """Python → MIR² 前端。"""

    def __init__(self):
        self._scope_depth = 0
        self._current_func: Optional[MIR2Function] = None
        self._vars: dict = {}

    def compile(self, source: str) -> Any:
        """编译 Python 源码为 CompileResult（兼容多语言前端接口）。"""
        from src.multi_lang_frontend import CompileResult, IRNode, IRKind
        tree = ast.parse(source)
        result = CompileResult(language="python", source=source)
        result.functions = {}

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                func = self._compile_function(node)
                result.functions[func.name] = [
                    IRNode(IRKind.VAR, value=p, result=p) for p in func.params
                ] + func.body
                for p in func.params:
                    result.types[p] = T_FLOAT
            elif isinstance(node, ast.Assign):
                self._compile_assignment(node, result)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    result.imports.append(f"{node.module}.{alias.name}")

        return result

    def _compile_function(self, node: ast.FunctionDef) -> MIR2Function:
        """编译函数定义。"""
        func = MIR2Function(
            name=node.name,
            params=[arg.arg for arg in node.args.args],
            effect=self._infer_effect(node),
        )

        self._current_func = func
        self._scope_depth += 1

        for stmt in node.body:
            self._compile_stmt(stmt, func)

        self._scope_depth -= 1
        self._current_func = None
        return func

    def _compile_stmt(self, stmt: ast.stmt, func: MIR2Function) -> None:
        """编译语句。"""
        if isinstance(stmt, ast.Assign):
            self._compile_assignment(stmt, func)
        elif isinstance(stmt, ast.Return):
            self._compile_return(stmt, func)
        elif isinstance(stmt, ast.If):
            self._compile_if(stmt, func)
        elif isinstance(stmt, ast.While):
            self._compile_while(stmt, func)
        elif isinstance(stmt, ast.For):
            self._compile_for(stmt, func)
        elif isinstance(stmt, ast.Expr):
            self._compile_expr_stmt(stmt, func)

    def _compile_assignment(self, node: ast.Assign, context: Any) -> None:
        """编译赋值。"""
        from src.multi_lang_frontend import CompileResult
        target = node.targets[0]
        is_program = isinstance(context, MIR2Program)
        is_compile_result = isinstance(context, CompileResult)
        func = self._current_func if is_program else None

        value = self._compile_expr(node.value, func if func else MIR2Function("global"))
        target_name = self._get_name(target)

        if isinstance(target, ast.Name):
            if func:
                func.locals[target_name] = value
            elif is_compile_result:
                # CompileResult: store in globals and IR nodes
                # Extract numeric value if available, otherwise store the expression
                num_val = None
                if hasattr(value, 'value') and value.value is not None:
                    try:
                        num_val = float(value.value)
                    except (TypeError, ValueError):
                        num_val = 0.0
                else:
                    num_val = 0.0
                context.ir_nodes.append(MIR2Expr(kind="const", value=num_val, result_var=target_name))
                context.globals[target_name] = num_val
                if hasattr(value, 'typ'):
                    context.types[target_name] = value.typ
            elif is_program:
                context.globals[target_name] = value
        elif isinstance(target, ast.Subscript):
            container = self._compile_expr(target.value, func if func else MIR2Function("global"))
            index = self._compile_expr(target.slice, func if func else MIR2Function("global"))
            if func:
                func.body.append(MIR2Expr(
                    kind="store_subscript",
                    operands=[container, index, value],
                    effect=Effect.STATE,
                ))

    def _compile_expr(self, node: ast.expr, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译表达式。"""
        if func is None:
            func = MIR2Function("global")
        if isinstance(node, ast.Constant):
            return self._compile_constant(node)
        elif isinstance(node, ast.Name):
            return self._compile_name(node, func)
        elif isinstance(node, ast.BinOp):
            return self._compile_binop(node, func)
        elif isinstance(node, ast.UnaryOp):
            return self._compile_unaryop(node, func)
        elif isinstance(node, ast.Call):
            return self._compile_call(node, func)
        elif isinstance(node, ast.BoolOp):
            return self._compile_boolop(node, func)
        elif isinstance(node, ast.Compare):
            return self._compile_compare(node, func)
        elif isinstance(node, ast.List):
            return self._compile_list(node, func)
        elif isinstance(node, ast.Dict):
            return self._compile_dict(node, func)
        elif isinstance(node, ast.Subscript):
            return self._compile_subscript(node, func)
        elif isinstance(node, ast.Attribute):
            return self._compile_attribute(node, func)
        else:
            return MIR2Expr(kind="unknown", effect=Effect.UNKNOWN)

    def _compile_constant(self, node: ast.Constant) -> MIR2Expr:
        """编译常量。"""
        if isinstance(node.value, int):
            return MIR2Expr(kind="const", value=node.value, typ=TypeInfo.INT)
        elif isinstance(node.value, float):
            return MIR2Expr(kind="const", value=node.value, typ=TypeInfo.FLOAT)
        elif isinstance(node.value, bool):
            return MIR2Expr(kind="const", value=node.value, typ=TypeInfo.BOOL)
        elif isinstance(node.value, str):
            return MIR2Expr(kind="const", value=node.value, typ=TypeInfo.STRING)
        elif node.value is None:
            return MIR2Expr(kind="const", typ=TypeInfo.NONE)
        return MIR2Expr(kind="const", value=node.value)

    def _compile_name(self, node: ast.Name, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译名称引用。"""
        if func is None:
            return MIR2Expr(kind="load", value=node.id)
        if node.id in func.locals:
            return MIR2Expr(kind="load", value=node.id, typ=TypeInfo.UNKNOWN)
        return MIR2Expr(kind="load", value=node.id, effect=Effect.IO)

    def _compile_binop(self, node: ast.BinOp, func: MIR2Function) -> MIR2Expr:
        """编译二元运算。"""
        left = self._compile_expr(node.left, func)
        right = self._compile_expr(node.right, func)
        op = self._map_binop(type(node.op).__name__)
        return MIR2Expr(kind="binop", op=op, operands=[left, right])

    def _compile_unaryop(self, node: ast.UnaryOp, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译一元运算。"""
        if func is None:
            func = MIR2Function("global")
        operand = self._compile_expr(node.operand, func)
        op = self._map_unaryop(type(node.op).__name__)
        return MIR2Expr(kind="unaryop", op=op, operands=[operand])

    def _compile_call(self, node: ast.Call, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译函数调用。"""
        if func is None:
            func = MIR2Function("global")
        callee = self._compile_expr(node.func, func)
        args = [self._compile_expr(arg, func) for arg in node.args]
        return MIR2Expr(
            kind="call",
            value=callee,
            operands=args,
            effect=Effect.IO,
        )

    def _compile_if(self, node: ast.If, func: MIR2Function) -> None:
        """编译 if 语句。"""
        cond = self._compile_expr(node.test, func)
        func.body.append(MIR2Expr(kind="if", operands=[cond]))
        for stmt in node.body:
            self._compile_stmt(stmt, func)
        if node.orelse:
            for stmt in node.orelse:
                self._compile_stmt(stmt, func)

    def _compile_while(self, node: ast.While, func: Optional[MIR2Function] = None) -> None:
        """编译 while 语句。"""
        if func is None:
            return
        cond = self._compile_expr(node.test, func)
        func.body.append(MIR2Expr(kind="loop", operands=[cond]))
        for stmt in node.body:
            self._compile_stmt(stmt, func)

    def _compile_for(self, node: ast.For, func: Optional[MIR2Function] = None) -> None:
        """编译 for 语句。"""
        if func is None:
            return
        iter_expr = self._compile_expr(node.iter, func)
        target = self._get_name(node.target)
        func.body.append(MIR2Expr(kind="for", operands=[iter_expr], value=target))
        for stmt in node.body:
            self._compile_stmt(stmt, func)

    def _compile_return(self, node: ast.Return, func: MIR2Function) -> None:
        """编译 return 语句。"""
        if node.value:
            value = self._compile_expr(node.value, func)
            func.body.append(MIR2Expr(kind="return", operands=[value]))

    def _compile_import(self, node: ast.Import, program: MIR2Program) -> None:
        """编译 import 语句。"""
        for alias in node.names:
            program.imports.append(alias.name)

    def _compile_import_from(self, node: ast.ImportFrom, program: MIR2Program) -> None:
        """编译 from ... import 语句。"""
        for alias in node.names:
            program.imports.append(f"{node.module}.{alias.name}")

    # ── 辅助方法 ──

    def _map_binop(self, op_name: str) -> str:
        """映射二元运算符。"""
        mapping = {
            "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
            "FloorDiv": "//", "Mod": "%", "Pow": "**",
            "BitOr": "|", "BitAnd": "&", "BitXor": "^",
            "LShift": "<<", "RShift": ">>",
        }
        return mapping.get(op_name, op_name)

    def _map_unaryop(self, op_name: str) -> str:
        """映射一元运算符。"""
        mapping = {"UAdd": "+", "USub": "-", "Not": "not", "Invert": "~"}
        return mapping.get(op_name, op_name)

    def _infer_effect(self, node: ast.FunctionDef) -> Effect:
        """推断函数效应。"""
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Call):
                if isinstance(stmt.func, ast.Attribute):
                    if stmt.func.attr in ("print", "input", "open"):
                        return Effect.IO
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.targets[0], ast.Subscript):
                    return Effect.STATE
        return Effect.PURE

    def _get_name(self, node: ast.AST) -> str:
        """提取名称。"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return ""

    def _compile_boolop(self, node: ast.BoolOp, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译布尔运算。"""
        if func is None:
            func = MIR2Function("global")
        op = "and" if isinstance(node.op, ast.And) else "or"
        values = [self._compile_expr(v, func) for v in node.values]
        return MIR2Expr(kind="boolop", op=op, operands=values)

    def _compile_compare(self, node: ast.Compare, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译比较运算。"""
        if func is None:
            func = MIR2Function("global")
        left = self._compile_expr(node.left, func)
        ops = [self._map_cmpop(type(c).__name__) for c in node.ops]
        rights = [self._compile_expr(r, func) for r in node.comparators]
        return MIR2Expr(kind="compare", op=ops[0] if ops else "", operands=[left] + rights)

    def _compile_list(self, node: ast.List, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译列表。"""
        if func is None:
            func = MIR2Function("global")
        elements = [self._compile_expr(e, func) for e in node.elts]
        return MIR2Expr(kind="list", operands=elements, typ=TypeInfo.LIST)

    def _compile_dict(self, node: ast.Dict, func: Optional[MIR2Function] = None) -> MIR2Expr:
        """编译字典。"""
        if func is None:
            func = MIR2Function("global")
        keys = [self._compile_expr(k, func) for k in node.keys]
        values = [self._compile_expr(v, func) for v in node.values]
        return MIR2Expr(kind="dict", operands=list(zip(keys, values)), typ=TypeInfo.DICT)

    def _compile_subscript(self, node: ast.Subscript, func: MIR2Expr) -> MIR2Expr:
        """编译下标访问。"""
        container = self._compile_expr(node.value, func)
        index = self._compile_expr(node.slice, func)
        return MIR2Expr(kind="subscript", operands=[container, index])

    def _compile_attribute(self, node: ast.Attribute, func: MIR2Expr) -> MIR2Expr:
        """编译属性访问。"""
        obj = self._compile_expr(node.value, func)
        return MIR2Expr(kind="attribute", value=node.attr, operands=[obj])

    def _map_cmpop(self, op_name: str) -> str:
        """映射比较运算符。"""
        mapping = {
            "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
            "Gt": ">", "GtE": ">=", "Is": "is", "IsNot": "is not",
            "In": "in", "NotIn": "not in",
        }
        return mapping.get(op_name, op_name)


# ============================================================
# 统一前端入口
# ============================================================

class MultiLanguageFrontend:
    """多语言前端统一入口。"""

    def __init__(self):
        self._frontends: dict[str, Any] = {
            "python": PythonFrontend(),
        }

    def register(self, lang: str, frontend: Any) -> None:
        """注册语言前端。"""
        self._frontends[lang] = frontend

    def compile(self, source: str, language: str = "python") -> MIR2Program:
        """编译源码为 MIR²。"""
        frontend = self._frontends.get(language)
        if frontend is None:
            raise ValueError(f"不支持的语言前端: {language}")
        return frontend.compile(source)

    def supported_languages(self) -> list[str]:
        """返回支持的语言列表。"""
        return list(self._frontends.keys())


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MIR2Expr",
    "MIR2Function",
    "MIR2Program",
    "Effect",
    "TypeInfo",
    "PythonFrontend",
    "MultiLanguageFrontend",
]
