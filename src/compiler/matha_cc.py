# -*- coding: utf-8 -*-
"""
Matha LLVM 工具链架构

┌─────────────────────────────────────────────────────────────────────┐
│                        Matha 工具链架构                               │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │  Matha 前端   │──▶│  Matha IR   │──▶│ LLVM IR      │            │
│  │ (词法/语法)   │   │ (中间表示)   │   │ (优化/翻译)   │            │
│  └──────────────┘   └──────────────┘   └──────┬───────┘            │
│                                               │                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────▼───────┐            │
│  │  Matha REPL  │   │  matha run   │   │ LLVM 后端     │            │
│  │  (交互)      │   │  (运行)      │   │ (llc/clang)  │            │
│  └──────────────┘   └──────────────┘   └──────┬───────┘            │
│                                               │                     │
│                                       ┌───────▼───────┐            │
│                                       │  原生机器码    │            │
│                                       │  (ELF/PE)     │            │
│                                       └───────────────┘            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Matha 专属优化 Pass:                                     │      │
│  │  • MathaTailRecPass    - 尾递归消除                        │      │
│  │  • MathaLoopUnrollPass - 循环展开                          │      │
│  │  • MathaSIMDPass       - 自动向量化                        │      │
│  │  • MathaConstFoldPass  - 常量折叠                          │      │
│  │  • MathaCurryFlattenPass- 柯里化扁平化                      │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ============================================================
# 1. Matha 前端 (Frontend)
# ============================================================

class MathaToken:
    """Matha 词法 token。"""
    def __init__(self, type_: str, value: str, line: int = 0, col: int = 0):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line}:C{self.col})"


class MathaLexer:
    """Matha 词法分析器。"""

    KEYWORDS = {"func", "if", "else", "while", "for", "in", "let", "match",
                "case", "return", "import", "module", "class", "def"}

    def __init__(self, source: str):
        self._source = source
        self._pos = 0
        self._line = 1
        self._col = 1

    def tokenize(self) -> list[MathaToken]:
        tokens = []
        while self._pos < len(self._source):
            self._skip_whitespace()
            if self._pos >= len(self._source):
                break
            ch = self._source[self._pos]
            if ch == "/" and self._pos + 1 < len(self._source) and self._source[self._pos + 1] == "/":
                self._skip_line_comment()
                continue
            if ch == "(" and self._pos + 1 < len(self._source) and self._source[self._pos + 1] == "*":
                self._skip_block_comment()
                continue
            if ch.isdigit() or (ch == "." and self._pos + 1 < len(self._source) and self._source[self._pos + 1].isdigit()):
                tokens.append(self._read_number())
                continue
            if ch in ('"', "'"):
                tokens.append(self._read_string(ch))
                continue
            if ch.isalpha() or ch == "_" or self._is_unicode_id_start(ch):
                tokens.append(self._read_identifier())
                continue
            if ch in "+-*/%=!<>&|^~":
                tokens.append(self._read_operator())
                continue
            if ch in "(),;:[]{}→∈":
                tokens.append(MathaToken(ch, ch, self._line, self._col))
                self._advance()
                continue
            self._advance()
        tokens.append(MathaToken("EOF", "", self._line, self._col))
        return tokens

    def _skip_whitespace(self) -> None:
        while self._pos < len(self._source) and self._source[self._pos] in " \t\n\r":
            if self._source[self._pos] == "\n":
                self._line += 1
                self._col = 1
            else:
                self._col += 1
            self._pos += 1

    def _skip_line_comment(self) -> None:
        while self._pos < len(self._source) and self._source[self._pos] != "\n":
            self._pos += 1

    def _skip_block_comment(self) -> None:
        self._pos += 2
        while self._pos < len(self._source) - 1:
            if self._source[self._pos] == "*" and self._source[self._pos + 1] == ")":
                self._pos += 2
                break
            if self._source[self._pos] == "\n":
                self._line += 1
            self._pos += 1

    def _read_number(self) -> MathaToken:
        start = self._pos
        has_dot = False
        while self._pos < len(self._source) and (self._source[self._pos].isdigit() or self._source[self._pos] == "."):
            if self._source[self._pos] == ".":
                if has_dot:
                    break
                has_dot = True
            self._pos += 1
        return MathaToken("NUMBER", self._source[start:self._pos], self._line, self._col)

    def _read_string(self, quote: str) -> MathaToken:
        start = self._pos
        self._pos += 1
        while self._pos < len(self._source) and self._source[self._pos] != quote:
            if self._source[self._pos] == "\n":
                self._line += 1
            self._pos += 1
        self._pos += 1
        return MathaToken("STRING", self._source[start:self._pos], self._line, self._col)

    def _read_identifier(self) -> MathaToken:
        start = self._pos
        while self._pos < len(self._source) and (self._source[self._pos].isalnum() or self._source[self._pos] in "_─"):
            self._pos += 1
        word = self._source[start:self._pos]
        if word in self.KEYWORDS:
            return MathaToken("KEYWORD", word, self._line, self._col)
        return MathaToken("IDENT", word, self._line, self._col)

    def _read_operator(self) -> MathaToken:
        start = self._pos
        op_chars = "+-*/%=!<>&|^~"
        while self._pos < len(self._source) and self._source[self._pos] in op_chars:
            self._pos += 1
        op = self._source[start:self._pos]
        op_map = {
            "→": "ARROW", ">>": "RSHIFT", "++": "INCR", "--": "DECR",
            "∈": "BELONGS", "=": "ASSIGN", "==": "EQ", "!=": "NEQ",
            "<=": "LEQ", ">=": "GEQ", "**": "POW", "//": "FLOORDIV",
            "+": "PLUS", "-": "MINUS", "*": "MUL", "/": "DIV",
            "%": "MOD", "<": "LT", ">": "GT", "=>": "LAMBDA",
        }
        return MathaToken(op_map.get(op, "OP"), op, self._line, self._col)

    def _is_unicode_id_start(self, ch: str) -> bool:
        import unicodedata
        if not ch:
            return False
        cat = unicodedata.category(ch)
        return cat.startswith(("L", "N", "Mn", "Mc", "Pc")) or ord(ch) > 0x2E00

    def _advance(self) -> None:
        if self._pos < len(self._source):
            if self._source[self._pos] == "\n":
                self._line += 1
                self._col = 1
            else:
                self._col += 1
            self._pos += 1


# ============================================================
# 2. Matha 语法树 (AST) - 使用普通类避免 dataclass 字段顺序问题
# ============================================================

class ASTNode:
    """AST 节点基类。"""
    def __init__(self, line: int = 0, col: int = 0):
        self.line = line
        self.col = col


class Program(ASTNode):
    def __init__(self, decls=None, line=0, col=0):
        super().__init__(line, col)
        self.decls = decls or []


class Binding(ASTNode):
    def __init__(self, name="", value=None, ann_type=None, line=0, col=0):
        super().__init__(line, col)
        self.name = name
        self.value = value
        self.ann_type = ann_type


class FuncDef(ASTNode):
    def __init__(self, name="", params=None, return_type="Any", body=None, line=0, col=0):
        super().__init__(line, col)
        self.name = name
        self.params = params or []
        self.return_type = return_type
        self.body = body


class BinaryOp(ASTNode):
    def __init__(self, op="", left=None, right=None, line=0, col=0):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right


class UnaryOp(ASTNode):
    def __init__(self, op="", operand=None, line=0, col=0):
        super().__init__(line, col)
        self.op = op
        self.operand = operand


class FuncApp(ASTNode):
    def __init__(self, func=None, arg=None, line=0, col=0):
        super().__init__(line, col)
        self.func = func
        self.arg = arg


class Lambda(ASTNode):
    def __init__(self, params=None, body=None, line=0, col=0):
        super().__init__(line, col)
        self.params = params or []
        self.body = body


class IfExpr(ASTNode):
    def __init__(self, cond=None, then=None, else_=None, line=0, col=0):
        super().__init__(line, col)
        self.cond = cond
        self.then = then
        self.else_ = else_


class WhileStmt(ASTNode):
    def __init__(self, cond=None, body=None, line=0, col=0):
        super().__init__(line, col)
        self.cond = cond
        self.body = body


class ForStmt(ASTNode):
    def __init__(self, target="", iterable=None, body=None, line=0, col=0):
        super().__init__(line, col)
        self.target = target
        self.iterable = iterable
        self.body = body


class Literal(ASTNode):
    def __init__(self, value=None, kind="number", line=0, col=0):
        super().__init__(line, col)
        self.value = value
        self.kind = kind


class Variable(ASTNode):
    def __init__(self, name="", line=0, col=0):
        super().__init__(line, col)
        self.name = name


class ListLiteral(ASTNode):
    def __init__(self, items=None, line=0, col=0):
        super().__init__(line, col)
        self.items = items or []


class DictLiteral(ASTNode):
    def __init__(self, keys=None, values=None, line=0, col=0):
        super().__init__(line, col)
        self.keys = keys or []
        self.values = values or []


class TupleExpr(ASTNode):
    def __init__(self, elements=None, line=0, col=0):
        super().__init__(line, col)
        self.elements = elements or []


class Output(ASTNode):
    def __init__(self, expr=None, line=0, col=0):
        super().__init__(line, col)
        self.expr = expr


# ============================================================
# 3. Matha 解析器 (Parser)
# ============================================================

class MathaParser:
    def __init__(self, tokens: list[MathaToken]):
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> Program:
        decls = []
        while self._peek().type != "EOF":
            decls.append(self._parse_decl())
        return Program(decls=decls)

    def _peek(self) -> MathaToken:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else MathaToken("EOF", "")

    def _advance(self) -> MathaToken:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type_: str) -> MathaToken:
        tok = self._peek()
        expected = type_
        if expected == "=" and tok.type == "ASSIGN":
            expected = "ASSIGN"
        if tok.type != expected:
            raise SyntaxError(f"期望 {type_}, 实际 {tok.type} ({tok.value!r})")
        return self._advance()

    def _parse_decl(self) -> ASTNode:
        tok = self._peek()
        if tok.type == "KEYWORD" and tok.value == "func":
            return self._parse_func_def()
        if tok.type == "IDENT":
            return self._parse_binding()
        if tok.type == "#":
            return self._parse_output()
        raise SyntaxError(f"意外的 token: {tok.type} ({tok.value!r})")

    def _parse_func_def(self) -> FuncDef:
        self._expect("KEYWORD")
        name_tok = self._expect("IDENT")
        self._expect("(")
        params = self._parse_param_list()
        self._expect(")")
        ret_type = "Any"
        if self._peek().type == "-":
            self._advance()
            self._expect(">")
            if self._peek().type == "IDENT":
                ret_type = self._advance().value
        self._expect("=")
        self._expect("(")
        lam_params = self._parse_param_list()
        self._expect(")")
        self._expect("→")
        body = self._parse_expr()
        return FuncDef(name=name_tok.value, params=lam_params, return_type=ret_type, body=body)

    def _parse_param_list(self) -> list:
        params = []
        if self._peek().type == ")":
            return params
        while True:
            if self._peek().type == ")":
                break
            params.append(self._advance().value)
            if self._peek().type == ",":
                self._advance()
        return params

    def _parse_binding(self) -> Binding:
        name = self._advance().value
        self._expect("=")
        value = self._parse_expr()
        return Binding(name=name, value=value)

    def _parse_output(self) -> Output:
        self._expect("#")
        self._expect("：")
        self._expect("[")
        expr = self._parse_expr()
        self._expect("]")
        return Output(expr=expr)

    def _parse_expr(self) -> ASTNode:
        return self._parse_or()

    def _parse_or(self) -> ASTNode:
        left = self._parse_and()
        while self._peek().type == "IDENT" and self._peek().value == "或":
            self._advance()
            right = self._parse_and()
            left = BinaryOp(op="or", left=left, right=right)
        return left

    def _parse_and(self) -> ASTNode:
        left = self._parse_equality()
        while self._peek().type == "IDENT" and self._peek().value == "与":
            self._advance()
            right = self._parse_equality()
            left = BinaryOp(op="and", left=left, right=right)
        return left

    def _parse_equality(self) -> ASTNode:
        left = self._parse_comparison()
        while self._peek().type in ("EQ", "NEQ", "BELONGS"):
            op_tok = self._advance()
            right = self._parse_comparison()
            left = BinaryOp(op=op_tok.type, left=left, right=right)
        return left

    def _parse_comparison(self) -> ASTNode:
        left = self._parse_additive()
        while self._peek().type in ("LT", "GT", "LEQ", "GEQ"):
            op_tok = self._advance()
            right = self._parse_additive()
            left = BinaryOp(op=op_tok.type, left=left, right=right)
        return left

    def _parse_additive(self) -> ASTNode:
        left = self._parse_multiplicative()
        while self._peek().type in ("PLUS", "MINUS"):
            op_tok = self._advance()
            right = self._parse_multiplicative()
            left = BinaryOp(op=op_tok.value, left=left, right=right)
        return left

    def _parse_multiplicative(self) -> ASTNode:
        left = self._parse_unary()
        while self._peek().type in ("MUL", "DIV", "FLOORDIV", "MOD", "POW"):
            op_tok = self._advance()
            right = self._parse_unary()
            left = BinaryOp(op=op_tok.value, left=left, right=right)
        return left

    def _parse_unary(self) -> ASTNode:
        if self._peek().type == "-":
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op="-", operand=operand)
        if self._peek().type in ("INCR", "DECR"):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryOp(op=op_tok.value, operand=operand)
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()
        if tok.type == "NUMBER":
            self._advance()
            try:
                return Literal(value=int(tok.value), kind="number")
            except ValueError:
                return Literal(value=float(tok.value), kind="number")
        if tok.type == "STRING":
            self._advance()
            return Literal(value=tok.value[1:-1], kind="string")
        if tok.type == "IDENT" and tok.value in ("True", "False"):
            self._advance()
            return Literal(value=tok.value == "True", kind="bool")
        if tok.type == "IDENT":
            self._advance()
            if self._peek().type == "(":
                self._advance()  # consume (
                args = self._parse_arg_list()
                self._expect(")")  # consume )
                if len(args) == 1:
                    return FuncApp(func=Variable(name=tok.value), arg=args[0])
                return FuncApp(func=Variable(name=tok.value), arg=args)
            return Variable(name=tok.value)
        if tok.type == "(":
            self._advance()
            # 检查是否是 lambda: (params) => body
            params = []
            if self._peek().type != ")":
                while True:
                    if self._peek().type == "IDENT":
                        params.append(self._advance().value)
                        if self._peek().type == ",":
                            self._advance()
                        elif self._peek().type == ")":
                            break
                        else:
                            break
                    elif self._peek().type == ")":
                        break
                    else:
                        break
            self._expect(")")
            # 检查 => 或 →
            if self._peek().type in ("ARROW", "LAMBDA"):
                self._advance()  # consume → or =>
                body = self._parse_expr()
                return Lambda(params=params, body=body)
            # 普通括号表达式
            expr = self._parse_expr()
            self._expect(")")
            return expr
        if tok.type == "→":
            self._advance()
            body = self._parse_expr()
            return Lambda(params=[], body=body)
        if tok.type == "[":
            return self._parse_list_literal()
        if tok.type == "{":
            return self._parse_dict_literal()
        if tok.type == "ARROW":
            self._advance()
            right = self._parse_expr()
            return BinaryOp(op="→", left=Variable(name="apply"), right=right)
        raise SyntaxError(f"意外的 token: {tok.type} ({tok.value!r})")

    def _parse_arg_list(self) -> list:
        args = []
        if self._peek().type == ")":
            return args
        # 解析第一个参数 (完整表达式，包括运算符)
        args.append(self._parse_expr())
        while self._peek().type == ",":
            self._advance()  # consume comma
            if self._peek().type == ")":
                break
            args.append(self._parse_expr())
        return args

    def _parse_list_literal(self) -> ListLiteral:
        self._expect("[")
        items = []
        if self._peek().type != "]":
            while True:
                items.append(self._parse_expr())
                if self._peek().type == ",":
                    self._advance()
                elif self._peek().type == "]":
                    break
        self._expect("]")
        return ListLiteral(items=items)

    def _parse_dict_literal(self) -> DictLiteral:
        self._expect("{")
        keys, values = [], []
        if self._peek().type != "}":
            while True:
                keys.append(self._parse_expr())
                self._expect(":")
                values.append(self._parse_expr())
                if self._peek().type == ",":
                    self._advance()
                elif self._peek().type == "}":
                    break
        self._expect("}")
        return DictLiteral(keys=keys, values=values)


# ============================================================
# 4. Matha IR (中间表示)
# ============================================================

class MathaIR:
    def __init__(self) -> None:
        self._instructions: list = []
        self._labels: dict = {}
        self._temps = 0
        self._funcs: dict = {}
        self._globals: dict = {}

    def _new_temp(self) -> str:
        self._temps += 1
        return f"t{self._temps}"

    def emit(self, instr: str) -> str:
        self._instructions.append(instr)
        if "=" in instr:
            return instr.split("=")[0].strip()
        return ""

    def emit_label(self, name: str) -> None:
        self._labels[name] = len(self._instructions)
        self._instructions.append(f"{name}:")

    def emit_call(self, func: str, args: list, result: str = None) -> str:
        result = result or self._new_temp()
        args_str = ", ".join(args)
        self._instructions.append(f"{result} = call {func}({args_str})")
        return result

    def emit_binary(self, op: str, left: str, right: str, result: str = None) -> str:
        result = result or self._new_temp()
        self._instructions.append(f"{result} = {op} {left}, {right}")
        return result

    def emit_load(self, name: str, result: str = None) -> str:
        result = result or self._new_temp()
        self._instructions.append(f"{result} = load {name}")
        return result

    def emit_store(self, name: str, value: str) -> None:
        self._instructions.append(f"store {value}, {name}")

    def to_dict(self) -> dict:
        return {"instructions": self._instructions, "labels": self._labels,
                "funcs": self._funcs, "globals": self._globals}


# ============================================================
# 5. 编译器前端: AST → Matha IR
# ============================================================

class MathaFrontend:
    def __init__(self) -> None:
        self._ir = MathaIR()
        self._scopes: list = [{}]

    def compile(self, program: Program) -> MathaIR:
        for decl in program.decls:
            self._compile_decl(decl)
        return self._ir

    def _compile_decl(self, decl: ASTNode) -> None:
        if isinstance(decl, FuncDef):
            self._compile_func(decl)
        elif isinstance(decl, Binding):
            self._compile_binding(decl)
        elif isinstance(decl, Output):
            if decl.expr:
                self._ir.emit(f"print {self._compile_expr(decl.expr)}")

    def _compile_func(self, func: FuncDef) -> None:
        self._scopes.append({})
        for param in func.params:
            self._scopes[-1][param] = param
        body_ir = self._compile_expr(func.body)
        self._ir._funcs[func.name] = {"params": func.params, "return_type": func.return_type, "body": body_ir}
        self._scopes.pop()

    def _compile_binding(self, binding: Binding) -> None:
        value = self._compile_expr(binding.value)
        self._ir.emit_store(binding.name, value)
        self._scopes[-1][binding.name] = binding.name

    def _compile_expr(self, expr: ASTNode) -> str:
        if expr is None:
            return "0.0"
        if isinstance(expr, Literal):
            return self._emit_literal(expr)
        if isinstance(expr, Variable):
            return self._ir.emit_load(expr.name)
        if isinstance(expr, BinaryOp):
            return self._compile_binary(expr)
        if isinstance(expr, UnaryOp):
            return self._compile_unary(expr)
        if isinstance(expr, FuncApp):
            return self._compile_func_app(expr)
        if isinstance(expr, Lambda):
            return self._ir.emit("call __matha_lambda()")
        if isinstance(expr, IfExpr):
            return self._compile_if(expr)
        if isinstance(expr, ListLiteral):
            return self._compile_list(expr)
        if isinstance(expr, DictLiteral):
            return self._compile_dict(expr)
        return "0.0"

    def _emit_literal(self, lit: Literal) -> str:
        val = lit.value
        if lit.kind == "number":
            return str(val)
        if lit.kind == "string":
            return f'"{val}"'
        if lit.kind == "bool":
            return "1.0" if val else "0.0"
        return "0.0"

    def _compile_binary(self, expr: BinaryOp) -> str:
        left = self._compile_expr(expr.left)
        right = self._compile_expr(expr.right)
        op_map = {"+": "add", "-": "sub", "*": "mul", "/": "fdiv", "//": "fdiv", "%": "fmod",
                  "**": "call @pow", "and": "and", "or": "or", "not": "not"}
        llvm_op = op_map.get(expr.op, expr.op)
        return self._ir.emit_binary(llvm_op, left, right)

    def _compile_unary(self, expr: UnaryOp) -> str:
        operand = self._compile_expr(expr.operand)
        if expr.op == "-":
            return self._ir.emit_binary("fsub", "0.0", operand)
        if expr.op in ("++", "DECR"):
            return self._ir.emit_binary("fadd", operand, "1.0")
        if expr.op in ("--", "INCR"):
            return self._ir.emit_binary("fsub", operand, "1.0")
        return operand

    def _compile_func_app(self, expr: FuncApp) -> str:
        if isinstance(expr.func, Variable):
            func_name = expr.func.name
            arg = self._compile_expr(expr.arg) if expr.arg else ""
            return self._ir.emit_call(func_name, [arg] if arg else [])
        func_val = self._compile_expr(expr.func)
        arg = self._compile_expr(expr.arg) if expr.arg else ""
        return self._ir.emit_call(func_val, [arg] if arg else [])

    def _compile_if(self, expr: IfExpr) -> str:
        cond = self._compile_expr(expr.cond)
        then_var = self._compile_expr(expr.then)
        else_var = self._compile_expr(expr.else_) if expr.else_ else "0.0"
        result = self._ir._new_temp()
        self._ir._instructions.append(f"br i1 {cond}, label %if.then, label %if.else")
        self._ir._instructions.append("if.then:")
        self._ir._instructions.append("  br label %if.end")
        self._ir._instructions.append("if.else:")
        self._ir._instructions.append("  br label %if.end")
        self._ir._instructions.append("if.end:")
        self._ir._instructions.append(f"  {result} = phi double [{then_var}, %if.then], [{else_var}, %if.else]")
        return result

    def _compile_list(self, expr: ListLiteral) -> str:
        items = [self._compile_expr(i) for i in expr.items]
        result = self._ir._new_temp()
        self._ir._instructions.append(f"{result} = call ptr @make_list({', '.join(items)})")
        return result

    def _compile_dict(self, expr: DictLiteral) -> str:
        keys = [self._compile_expr(k) for k in expr.keys]
        values = [self._compile_expr(v) for v in expr.values]
        result = self._ir._new_temp()
        self._ir._instructions.append(f"{result} = call ptr @make_dict({keys}, {values})")
        return result

    def _compile_tuple(self, expr: TupleExpr) -> str:
        """编译元组表达式为 C 数组构造。"""
        elements = [self._compile_expr(e) for e in expr.elements]
        result = self._ir._new_temp()
        self._ir._instructions.append(
            f"{result} = call ptr @make_tuple({', '.join(elements)})"
        )
        return result


# ============================================================
# 6. Matha IR → LLVM IR 生成器
# ============================================================

class MathaLLVMGenerator:
    def __init__(self, module_name: str = "matha") -> None:
        self._module_name = module_name
        self._llvm_ir: list = []

    def generate(self, matha_ir: MathaIR) -> str:
        self._llvm_ir = [
            "; Matha LLVM IR - 由 matha-cc 自动生成",
            f"; 模块: {self._module_name}",
            'target triple = "x86_64-pc-windows-msvc"',
            '',
            '; === 数学函数声明 ===',
            'declare double @sqrt(double)',
            'declare double @pow(double, double)',
            'declare double @sin(double)',
            'declare double @cos(double)',
            'declare double @tan(double)',
            'declare double @log(double)',
            'declare double @exp(double)',
            'declare double @fabs(double)',
            'declare double @floor(double)',
            'declare double @ceil(double)',
            '',
            '; === 主函数 ===',
            'define double @main() {',
            '  entry:',
        ]
        for instr in matha_ir._instructions:
            if instr.strip():
                self._llvm_ir.append(f"  {instr}")
        self._llvm_ir.extend(['  ret double 0.0', '}'])
        for func_name, func_info in matha_ir._funcs.items():
            params_str = ", ".join(f"double %{p}" for p in func_info["params"])
            self._llvm_ir.extend([
                '',
                f'define double @{func_name}({params_str}) {{',
                '  entry:',
                f'  ret double {func_info.get("body", "0.0")}',
                '}',
            ])
        return "\n".join(self._llvm_ir)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._llvm_ir))


# ============================================================
# 7. 编译器后端: LLVM IR → 原生机器码
# ============================================================

class MathaBackend:
    def __init__(self, toolchain: str = "clang") -> None:
        self._toolchain = toolchain
        self._cache: dict = {}

    def compile(self, llvm_ir: str, output_name: str = "matha_out") -> str:
        import hashlib
        cache_key = hashlib.sha256(llvm_ir.encode()).hexdigest()[:16]
        if cache_key in self._cache:
            return self._cache[cache_key]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ll', delete=False, encoding='utf-8') as f:
            f.write(llvm_ir)
            ll_file = f.name
        obj_file = ll_file + '.o'
        exe_file = f"{output_name}.exe"
        try:
            result = subprocess.run(['llc', '-O2', ll_file, '-o', obj_file],
                                    capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                result = subprocess.run(['clang', '-O2', '-c', ll_file, '-o', obj_file],
                                        capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                os.unlink(ll_file)
                return ""
            result = subprocess.run(['clang', obj_file, '-o', exe_file],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                os.unlink(ll_file)
                os.unlink(obj_file)
                return ""
            self._cache[cache_key] = exe_file
            os.unlink(ll_file)
            if os.path.exists(obj_file):
                os.unlink(obj_file)
            return exe_file
        except FileNotFoundError:
            return ""

    def run(self, exe_path: str, args: list = None) -> subprocess.CompletedProcess:
        return subprocess.run([exe_path] + (args or []), capture_output=True, text=True)

    @property
    def cache_stats(self) -> dict:
        return {"cached": len(self._cache), "toolchain": self._toolchain}


# ============================================================
# 8. 统一编译器 (matha-cc)
# ============================================================

class MathaCompiler:
    def __init__(self, optimize: bool = True) -> None:
        self._optimize = optimize
        self._backend = MathaBackend()
        self._stats = {"compile_count": 0, "cache_hits": 0}

    def compile_file(self, matha_file: str, output_name: str = "out") -> str:
        with open(matha_file, "r", encoding="utf-8") as f:
            source = f.read()
        return self.compile_source(source, output_name)

    def compile_source(self, source: str, output_name: str = "out") -> str:
        self._stats["compile_count"] += 1
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        frontend = MathaFrontend()
        matha_ir = frontend.compile(ast)
        generator = MathaLLVMGenerator(os.path.splitext(output_name)[0])
        llvm_ir = generator.generate(matha_ir)
        if self._optimize:
            llvm_ir = self._optimize_llvm(llvm_ir)
        return self._backend.compile(llvm_ir, output_name)

    def _optimize_llvm(self, llvm_ir: str) -> str:
        import re
        def fold_const(m):
            try:
                left = float(m.group(1))
                right = float(m.group(4))
                op = m.group(2)
                if op == "add": return f"fadd double {left + right}, 0.0"
                if op == "sub": return f"fsub double {left - right}, 0.0"
                if op == "mul": return f"fmul double {left * right}, 0.0"
                if op == "fdiv": return f"fdiv double {left / right}, 0.0" if right != 0 else m.group(0)
            except (ValueError, ZeroDivisionError): pass
            return m.group(0)
        return re.sub(r'(\-?\d+\.?\d*)\s*=\s*(fadd|fsub|fmul|fdiv)\s+double\s+(\-?\d+\.?\d*),\s*(\-?\d+\.?\d*)', fold_const, llvm_ir)

    def run(self, source: str, args: list = None) -> subprocess.CompletedProcess:
        exe_path = self.compile_source(source, "__matha_tmp")
        try:
            return self._backend.run(exe_path, args)
        finally:
            if os.path.exists(exe_path):
                os.unlink(exe_path)

    @property
    def stats(self) -> dict:
        return {**self._stats, "backend_cache": self._backend.cache_stats}


# ============================================================
# 公共 API
# ============================================================

def matha_compile(source: str, output_name: str = "out", optimize: bool = True) -> str:
    compiler = MathaCompiler(optimize=optimize)
    return compiler.compile_source(source, output_name)

def matha_run(source: str, args: list = None) -> subprocess.CompletedProcess:
    compiler = MathaCompiler()
    return compiler.run(source, args)

def matha_to_llvm(source: str) -> str:
    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    parser = MathaParser(tokens)
    ast = parser.parse()
    frontend = MathaFrontend()
    matha_ir = frontend.compile(ast)
    generator = MathaLLVMGenerator("matha_module")
    return generator.generate(matha_ir)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MathaToken", "MathaLexer",
    "ASTNode", "Program", "Binding", "FuncDef", "BinaryOp", "UnaryOp",
    "FuncApp", "Lambda", "IfExpr", "WhileStmt", "ForStmt",
    "Literal", "Variable", "ListLiteral", "DictLiteral", "TupleExpr", "Output",
    "MathaParser",
    "MathaIR",
    "MathaFrontend",
    "MathaLLVMGenerator",
    "MathaBackend",
    "MathaCompiler",
    "matha_compile",
    "matha_run",
    "matha_to_llvm",
]
