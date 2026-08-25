# -*- coding: utf-8 -*-
"""Matha 多语言转译器：把 Matha 程序转译为其它编程语言源码。

让其它语言能直接运行 Matha 编写的程序/应用/系统。

支持目标语言：
  - Python：转译为可执行的 Python 脚本
  - JavaScript：转译为可运行的 JS 脚本
  - JSON IR：转译为中间表示（任何语言可解析后执行）

转译策略：
  - func 定义 → 目标语言函数定义
  - 绑定（Binding）→ 变量赋值
  - 表达式 → 目标语言等价表达式
  - 输出（Output）→ print / console.log
  - if/match/loop → 目标语言控制流
  - Matha 内建函数 → 目标语言等价函数映射

符号映射表（Matha → 目标语言）：
  Matha 内建     → Python              → JavaScript
  ─────────────────────────────────────────────────
  sin/cos/tan    → math.sin/cos/tan    → Math.sin/cos/tan
  sqrt           → math.sqrt           → Math.sqrt
  ln             → math.log            → Math.log
  log10          → math.log10          → Math.log10
  abs            → abs                 → Math.abs
  max/min        → max/min             → Math.max/min
  len            → len                 → .length
  ord/chr        → ord/chr             → .charCodeAt(0)/String.fromCharCode
  + - * / % ^    → + - * / % **        → + - * / % **
  真/假          → True/False          → true/false
"""

from __future__ import annotations
from typing import Any

from src.parser import Parser
from src import ast_nodes as ast


class TranspileError(Exception):
    """转译错误。"""


# ============================================================
# 符号映射表
# ============================================================

# Matha 内建函数 → Python 等价
MATHA_TO_PYTHON: dict[str, str] = {
    "sin": "math.sin", "cos": "math.cos", "tan": "math.tan",
    "asin": "math.asin", "acos": "math.acos", "atan": "math.atan",
    "sinh": "math.sinh", "cosh": "math.cosh", "tanh": "math.tanh",
    "sqrt": "math.sqrt", "ln": "math.log", "log10": "math.log10",
    "log2": "math.log2", "exp": "math.exp", "abs": "abs",
    "floor": "math.floor", "ceil": "math.ceil", "round": "round",
    "max": "max", "min": "min", "sum": "sum",
    "len": "len", "ord": "ord", "chr": "chr",
    "pi": "math.pi", "e": "math.e", "tau": "math.tau",
}

# Matha 内建函数 → JavaScript 等价
MATHA_TO_JS: dict[str, str] = {
    "sin": "Math.sin", "cos": "Math.cos", "tan": "Math.tan",
    "asin": "Math.asin", "acos": "Math.acos", "atan": "Math.atan",
    "sqrt": "Math.sqrt", "ln": "Math.log", "log10": "Math.log10",
    "log2": "Math.log2", "exp": "Math.exp", "abs": "Math.abs",
    "floor": "Math.floor", "ceil": "Math.ceil", "round": "Math.round",
    "max": "Math.max", "min": "Math.min",
    "len": "len", "ord": "charCodeAt", "chr": "String.fromCharCode",
    "pi": "Math.PI", "e": "Math.E", "tau": "(2 * Math.PI)",
}


# ============================================================
# Python 转译器
# ============================================================

class PythonTranspiler:
    """把 Matha AST 转译为 Python 源码。"""

    def __init__(self):
        self.indent = 0
        self.lines: list[str] = []
        self._seen_funcs: set[str] = set()

    def transpile(self, source: str) -> str:
        """转译 Matha 源码为 Python 源码。"""
        program = Parser(source).parse()
        self.lines = [
            "# -*- coding: utf-8 -*-",
            "# 由 Matha transpiler 自动生成",
            "import math",
            "",
        ]
        for decl in program.decls:
            self._transpile_decl(decl)
        return "\n".join(self.lines) + "\n"

    def _pad(self) -> str:
        return "    " * self.indent

    def _transpile_decl(self, decl) -> None:
        if isinstance(decl, ast.FuncDef):
            self._transpile_func(decl)
        elif isinstance(decl, ast.Binding):
            # 顶层绑定
            target = self._transpile_expr(decl.target)
            value = self._transpile_expr(decl.value) if decl.value else "None"
            self.lines.append(f"{target} = {value}")
        elif isinstance(decl, ast.MechUnit):
            # 机械单元：转译体内的语句
            if decl.body and isinstance(decl.body, ast.CodeBlock):
                for stmt in decl.body.stmts:
                    self._transpile_stmt(stmt)
        elif isinstance(decl, ast.ModuleDecl):
            # 模块：递归转译内部声明
            for inner in decl.decls:
                self._transpile_decl(inner)

    def _transpile_func(self, fn: ast.FuncDef) -> None:
        name = fn.name
        # FuncDef 参数在 body（Lambda）中
        params = ""
        if fn.body and isinstance(fn.body, ast.Lambda) and fn.body.params:
            params = ", ".join(p.name for p in fn.body.params)
        self.lines.append(f"def {name}({params}):")
        self.indent += 1
        if fn.body and isinstance(fn.body, ast.Lambda):
            expr = self._transpile_expr(fn.body.body)
            self.lines.append(f"{self._pad()}return {expr}")
        elif fn.body and isinstance(fn.body, ast.CodeBlock):
            for stmt in fn.body.stmts:
                self._transpile_stmt(stmt)
        else:
            self.lines.append(f"{self._pad()}pass")
        self.indent -= 1
        self.lines.append("")
        self._seen_funcs.add(name)

    def _transpile_stmt(self, stmt) -> None:
        pad = self._pad()
        if isinstance(stmt, ast.Binding):
            target = self._transpile_expr(stmt.target)
            value = self._transpile_expr(stmt.value) if stmt.value else "None"
            self.lines.append(f"{pad}{target} = {value}")
        elif isinstance(stmt, ast.GenStmt):
            # GenStmt 包裹 OutputTrail 或 FileMarker
            if hasattr(stmt, 'content') and stmt.content:
                content = stmt.content
                if isinstance(content, ast.OutputTrail):
                    if content.output:
                        expr = self._transpile_expr(content.output.expr)
                        self.lines.append(f"{pad}print({expr})")
                elif isinstance(content, ast.FileMarker):
                    pass  # #：【文件】 无 Python 等价
        elif isinstance(stmt, ast.Output):
            expr = self._transpile_expr(stmt.expr)
            self.lines.append(f"{pad}print({expr})")
        elif isinstance(stmt, ast.IfStmt):
            cond = self._transpile_expr(stmt.cond)
            self.lines.append(f"{pad}if {cond}:")
            self.indent += 1
            if stmt.then_block and isinstance(stmt.then_block, ast.CodeBlock):
                for s in stmt.then_block.stmts:
                    self._transpile_stmt(s)
            else:
                self.lines.append(f"{self._pad()}pass")
            self.indent -= 1
            if stmt.else_block:
                self.lines.append(f"{pad}else:")
                self.indent += 1
                if isinstance(stmt.else_block, ast.CodeBlock):
                    for s in stmt.else_block.stmts:
                        self._transpile_stmt(s)
                else:
                    self.lines.append(f"{self._pad()}pass")
                self.indent -= 1
        elif isinstance(stmt, ast.LoopWhile):
            cond = self._transpile_expr(stmt.cond)
            self.lines.append(f"{pad}while {cond}:")
            self.indent += 1
            if stmt.body and isinstance(stmt.body, ast.CodeBlock):
                for s in stmt.body.stmts:
                    self._transpile_stmt(s)
            else:
                self.lines.append(f"{self._pad()}pass")
            self.indent -= 1
        elif isinstance(stmt, ast.CodeBlock):
            for s in stmt.stmts:
                self._transpile_stmt(s)

    def _transpile_expr(self, expr) -> str:
        if expr is None:
            return "None"

        if isinstance(expr, ast.IntegerLit):
            return str(expr.value)
        if isinstance(expr, ast.FloatLit):
            return str(expr.value)
        if isinstance(expr, ast.StringLit):
            return repr(expr.value)
        if isinstance(expr, ast.BoolLit):
            return "True" if expr.value else "False"
        if isinstance(expr, ast.Variable):
            name = expr.name
            if name == "真":
                return "True"
            if name == "假":
                return "False"
            return name
        if isinstance(expr, ast.BinaryOp):
            left = self._transpile_expr(expr.left)
            right = self._transpile_expr(expr.right)
            op = self._map_op(expr.op)
            return f"({left} {op} {right})"
        if isinstance(expr, ast.UnaryOp):
            operand = self._transpile_expr(expr.operand)
            if expr.op == "-":
                return f"(-{operand})"
            if expr.op == "^":
                return f"math.sqrt({operand})"
            return f"({expr.op}{operand})"
        if isinstance(expr, ast.Lambda):
            params = ", ".join(p.name for p in expr.params) if expr.params else ""
            body = self._transpile_expr(expr.body)
            return f"(lambda {params}: {body})"
        if isinstance(expr, ast.FuncApp):
            fn = self._transpile_expr(expr.func)
            arg = self._transpile_expr(expr.arg)
            # Matha 内建函数映射
            if isinstance(expr.func, ast.Variable):
                name = expr.func.name
                if name in MATHA_TO_PYTHON:
                    return f"{MATHA_TO_PYTHON[name]}({arg})"
            return f"{fn}({arg})"
        if isinstance(expr, ast.IfExpr):
            cond = self._transpile_expr(expr.cond)
            then = self._transpile_expr(expr.then)
            els = self._transpile_expr(expr.else_)
            return f"({then} if {cond} else {els})"
        if isinstance(expr, ast.CodeBlock):
            # 内联代码块：转为一组语句
            parts = []
            for s in expr.stmts:
                if isinstance(s, ast.Binding):
                    target = self._transpile_expr(s.target)
                    value = self._transpile_expr(s.value) if s.value else "None"
                    parts.append(f"{target} = {value}")
            return "; ".join(parts) if parts else "None"

        # 兜底
        return f"None  # 未转译: {type(expr).__name__}"

    @staticmethod
    def _map_op(op: str) -> str:
        """Matha 运算符 → Python 运算符。"""
        mapping = {
            "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
            "^": "**", "=": "==", "!=": "!=",
            "<": "<", ">": ">", "<=": "<=", ">=": ">=",
            "&&": "and", "||": "or", "!": "not",
        }
        return mapping.get(op, op)


# ============================================================
# JavaScript 转译器
# ============================================================

class JavaScriptTranspiler:
    """把 Matha AST 转译为 JavaScript 源码。"""

    def __init__(self):
        self.indent = 0
        self.lines: list[str] = []

    def transpile(self, source: str) -> str:
        """转译 Matha 源码为 JavaScript 源码。"""
        program = Parser(source).parse()
        self.lines = [
            "// 由 Matha transpiler 自动生成",
            '"use strict";',
            "",
        ]
        for decl in program.decls:
            self._transpile_decl(decl)
        return "\n".join(self.lines) + "\n"

    def _pad(self) -> str:
        return "  " * self.indent

    def _transpile_decl(self, decl) -> None:
        if isinstance(decl, ast.FuncDef):
            self._transpile_func(decl)
        elif isinstance(decl, ast.Binding):
            target = self._transpile_expr(decl.target)
            value = self._transpile_expr(decl.value) if decl.value else "null"
            self.lines.append(f"const {target} = {value};")
        elif isinstance(decl, ast.MechUnit):
            if decl.body and isinstance(decl.body, ast.CodeBlock):
                for stmt in decl.body.stmts:
                    self._transpile_stmt(stmt)
        elif isinstance(decl, ast.ModuleDecl):
            for inner in decl.decls:
                self._transpile_decl(inner)

    def _transpile_func(self, fn: ast.FuncDef) -> None:
        name = fn.name
        params = ""
        if fn.body and isinstance(fn.body, ast.Lambda) and fn.body.params:
            params = ", ".join(p.name for p in fn.body.params)
        self.lines.append(f"function {name}({params}) {{")
        self.indent += 1
        if fn.body and isinstance(fn.body, ast.Lambda):
            expr = self._transpile_expr(fn.body.body)
            self.lines.append(f"{self._pad()}return {expr};")
        elif fn.body and isinstance(fn.body, ast.CodeBlock):
            for stmt in fn.body.stmts:
                self._transpile_stmt(stmt)
        else:
            self.lines.append(f"{self._pad()}// empty")
        self.indent -= 1
        self.lines.append("}")
        self.lines.append("")

    def _transpile_stmt(self, stmt) -> None:
        pad = self._pad()
        if isinstance(stmt, ast.Binding):
            target = self._transpile_expr(stmt.target)
            value = self._transpile_expr(stmt.value) if stmt.value else "null"
            self.lines.append(f"{pad}let {target} = {value};")
        elif isinstance(stmt, ast.GenStmt):
            if hasattr(stmt, 'content') and stmt.content:
                content = stmt.content
                if isinstance(content, ast.OutputTrail):
                    if content.output:
                        expr = self._transpile_expr(content.output.expr)
                        self.lines.append(f"{pad}console.log({expr});")
                elif isinstance(content, ast.FileMarker):
                    pass
        elif isinstance(stmt, ast.Output):
            expr = self._transpile_expr(stmt.expr)
            self.lines.append(f"{pad}console.log({expr});")
        elif isinstance(stmt, ast.IfStmt):
            cond = self._transpile_expr(stmt.cond)
            self.lines.append(f"{pad}if ({cond}) {{")
            self.indent += 1
            if stmt.then_block and isinstance(stmt.then_block, ast.CodeBlock):
                for s in stmt.then_block.stmts:
                    self._transpile_stmt(s)
            self.indent -= 1
            if stmt.else_block:
                self.lines.append(f"{pad}}} else {{")
                self.indent += 1
                if isinstance(stmt.else_block, ast.CodeBlock):
                    for s in stmt.else_block.stmts:
                        self._transpile_stmt(s)
                self.indent -= 1
            self.lines.append(f"{pad}}}")
        elif isinstance(stmt, ast.LoopWhile):
            cond = self._transpile_expr(stmt.cond)
            self.lines.append(f"{pad}while ({cond}) {{")
            self.indent += 1
            if stmt.body and isinstance(stmt.body, ast.CodeBlock):
                for s in stmt.body.stmts:
                    self._transpile_stmt(s)
            self.indent -= 1
            self.lines.append(f"{pad}}}")
        elif isinstance(stmt, ast.CodeBlock):
            for s in stmt.stmts:
                self._transpile_stmt(s)

    def _transpile_expr(self, expr) -> str:
        if expr is None:
            return "null"
        if isinstance(expr, ast.IntegerLit):
            return str(expr.value)
        if isinstance(expr, ast.FloatLit):
            return str(expr.value)
        if isinstance(expr, ast.StringLit):
            return json_repr(expr.value)
        if isinstance(expr, ast.BoolLit):
            return "true" if expr.value else "false"
        if isinstance(expr, ast.Variable):
            name = expr.name
            if name == "真":
                return "true"
            if name == "假":
                return "false"
            if name in MATHA_TO_JS:
                return MATHA_TO_JS[name]
            return name
        if isinstance(expr, ast.BinaryOp):
            left = self._transpile_expr(expr.left)
            right = self._transpile_expr(expr.right)
            op = self._map_op(expr.op)
            return f"({left} {op} {right})"
        if isinstance(expr, ast.UnaryOp):
            operand = self._transpile_expr(expr.operand)
            if expr.op == "-":
                return f"(-{operand})"
            if expr.op == "^":
                return f"Math.sqrt({operand})"
            return f"({expr.op}{operand})"
        if isinstance(expr, ast.Lambda):
            params = ", ".join(p.name for p in expr.params) if expr.params else ""
            body = self._transpile_expr(expr.body)
            return f"(({params}) => {body})"
        if isinstance(expr, ast.FuncApp):
            arg = self._transpile_expr(expr.arg)
            if isinstance(expr.func, ast.Variable):
                name = expr.func.name
                if name in MATHA_TO_JS:
                    mapped = MATHA_TO_JS[name]
                    if name == "len":
                        return f"({arg}).length"
                    if name == "ord":
                        return f"({arg}).charCodeAt(0)"
                    return f"{mapped}({arg})"
            fn = self._transpile_expr(expr.func)
            return f"{fn}({arg})"
        if isinstance(expr, ast.IfExpr):
            cond = self._transpile_expr(expr.cond)
            then = self._transpile_expr(expr.then)
            els = self._transpile_expr(expr.else_)
            return f"({cond} ? {then} : {els})"
        return f"null /* 未转译: {type(expr).__name__} */"

    @staticmethod
    def _map_op(op: str) -> str:
        mapping = {
            "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
            "^": "**", "=": "===", "!=": "!==",
            "<": "<", ">": ">", "<=": "<=", ">=": ">=",
            "&&": "&&", "||": "||",
        }
        return mapping.get(op, op)


def json_repr(s: str) -> str:
    """把字符串转为 JSON 字符串表示（JS 兼容）。"""
    import json
    return json.dumps(s, ensure_ascii=False)


# ============================================================
# 统一入口
# ============================================================

def transpile(source: str, target: str = "python") -> str:
    """把 Matha 源码转译为目标语言源码。

    Args:
        source: Matha 源码
        target: "python" | "javascript" | "json"

    Returns:
        目标语言源码字符串
    """
    target = target.lower()
    if target in ("python", "py"):
        return PythonTranspiler().transpile(source)
    if target in ("javascript", "js"):
        return JavaScriptTranspiler().transpile(source)
    if target == "json":
        from src.ast_serializer import program_to_json
        return program_to_json(source)
    raise TranspileError(f"不支持的转译目标: {target}")
