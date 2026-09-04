# -*- coding: utf-8 -*-
"""
Matha 符号引擎 v1.3.0
========================
统一的符号表达式系统，支持 AST 解析、代数运算、微积分、自动简化。

功能：
  • Symbol       — 符号变量
  • Expr         — 表达式基类（Add/Mul/Pow/Func/Num/Var）
  • Parser       — 符号表达式解析器
  • simplify/diff/integrate/evaluate — 核心运算
  • ASTNode      — AST 节点（跨平台代码生成用）
  • LISP/Scheme  — 函数式语言互操作层
"""
from __future__ import annotations
import re
import sys
import os
import logging
import math
from dataclasses import dataclass, field
from functools import reduce
from typing import Optional, Any, Callable, Dict, List, Tuple
from enum import Enum

logger = logging.getLogger("matha.symbolic")


# ═══════════════════════════════════════════════════════════════════════════════
#  AST 节点体系
# ═══════════════════════════════════════════════════════════════════════════════

class ASTNodeType(str, Enum):
    NUM = "num"
    VAR = "var"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    POW = "pow"
    NEG = "neg"
    FUNC = "func"       # 函数调用 f(x)
    LAMBDA = "lambda"   # λx → expr
    APP = "app"         # 函数应用 f(x,y)
    LET = "let"         # 绑定 let x = expr
    IF = "if"           # 条件表达式
    SEQ = "seq"         # 顺序表达式
    ASSIGN = "assign"   # 赋值
    LIST = "list"       # 列表
    MAP = "map"         # 映射
    REDUCE = "reduce"   # 归约
    FILTER = "filter"   # 过滤


@dataclass
class ASTNode:
    """AST 节点：统一表示所有表达式和操作。"""
    node_type: ASTNodeType
    value: Any = None           # 数值字面量或变量名
    children: List['ASTNode'] = field(default_factory=list)
    label: str = ""             # 标签（函数名等）
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.node_type.value,
            "value": self.value,
            "label": self.label,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        if self.node_type == ASTNodeType.NUM:
            return str(self.value)
        elif self.node_type == ASTNodeType.VAR:
            return str(self.value)
        elif self.node_type == ASTNodeType.NEG:
            return f"(-{self.children[0]})"
        elif self.node_type in (ASTNodeType.ADD, ASTNodeType.SUB, ASTNodeType.MUL, ASTNodeType.DIV):
            ops = [str(c) for c in self.children]
            op = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/'}[self.node_type.value]
            return f"({ops[0]} {op} {ops[1]})"
        elif self.node_type == ASTNodeType.POW:
            return f"({self.children[0]} ^ {self.children[1]})"
        elif self.node_type == ASTNodeType.FUNC:
            args = ', '.join(str(c) for c in self.children)
            return f"{self.label}({args})"
        elif self.node_type == ASTNodeType.LAMBDA:
            param = self.label or "x"
            body = self.children[0] if self.children else "0"
            return f"λ{param}→{body}"
        elif self.node_type == ASTNodeType.LET:
            return f"let {self.label} = {self.children[0] if self.children else '?'}"
        elif self.node_type == ASTNodeType.IF:
            return f"if ({self.children[0]}) then {self.children[1]} else {self.children[2] if len(self.children) > 2 else '0'}"
        elif self.node_type == ASTNodeType.SEQ:
            return '; '.join(str(c) for c in self.children)
        elif self.node_type == ASTNodeType.LIST:
            return f"[{', '.join(str(c) for c in self.children)}]"
        return f"<{self.node_type.value}>"

    def __repr__(self):
        return f"ASTNode({self.node_type.value}, {self.value!r})"


# ═══════════════════════════════════════════════════════════════════════════════
#  符号表达式体系
# ═══════════════════════════════════════════════════════════════════════════════

class Expr:
    """符号表达式基类 — 代数运算的核心抽象。"""
    __slots__ = ()

    def __add__(self, other): return Add(self, to_expr(other))
    def __radd__(self, other): return Add(to_expr(other), self)
    def __sub__(self, other): return Sub(self, to_expr(other))
    def __rsub__(self, other): return Sub(to_expr(other), self)
    def __mul__(self, other): return Mul(self, to_expr(other))
    def __rmul__(self, other): return Mul(to_expr(other), self)
    def __truediv__(self, other): return Div(self, to_expr(other))
    def __rtruediv__(self, other): return Div(to_expr(other), self)
    def __pow__(self, other): return Pow(self, to_expr(other))
    def __rpow__(self, other): return Pow(to_expr(other), self)
    def __neg__(self): return Neg(self)

    def simplify(self) -> 'Expr': return self
    def diff(self, var: str) -> 'Expr': raise NotImplementedError
    def evaluate(self, bindings: Dict[str, float] = None) -> float: raise NotImplementedError
    def substitute(self, var: str, value: 'Expr') -> 'Expr': raise NotImplementedError
    def free_vars(self) -> set: raise NotImplementedError

    def __str__(self): raise NotImplementedError
    def __repr__(self): return f"Expr({self})"


@dataclass(frozen=True)
class Num(Expr):
    value: float
    def simplify(self):
        # 对极小值或极大值保留原始精度，避免 round(value,10) 造成灾难性精度损失
        if abs(self.value) < 1e-10 or abs(self.value) >= 1e10 or self.value == 0:
            return self
        return Num(round(self.value, 10))
    def evaluate(self, _bindings=None): return self.value
    def substitute(self, *a): return self
    def diff(self, var): return Num(0)
    def free_vars(self) -> set: return set()
    def __str__(self): return str(int(self.value)) if self.value == int(self.value) else str(self.value)

@dataclass(frozen=True)
class Var(Expr):
    name: str
    def evaluate(self, bindings):
        v = bindings.get(self.name) if bindings else None
        if v is None: raise ValueError(f"未绑定变量: {self.name}")
        return float(v)
    def substitute(self, var, value):
        return value if self.name == var else self
    def diff(self, var):
        return Num(1) if self.name == var else Num(0)
    def free_vars(self) -> set: return {self.name}
    def __str__(self): return self.name

@dataclass(frozen=True)
class Neg(Expr):
    expr: Expr
    def simplify(self):
        e = self.expr.simplify()
        if isinstance(e, Num): return Num(-e.value)
        return Neg(e)
    def evaluate(self, bindings): return -self.expr.evaluate(bindings)
    def substitute(self, var, value): return Neg(self.expr.substitute(var, value))
    def diff(self, var): return Neg(self.expr.diff(var))
    def free_vars(self) -> set: return self.expr.free_vars()
    def __str__(self): return f"(-{self.expr})"

@dataclass(frozen=True)
class Add(Expr):
    left: Expr
    right: Expr
    def simplify(self):
        a, b = self.left.simplify(), self.right.simplify()
        if isinstance(a, Num) and isinstance(b, Num): return Num(a.value + b.value)
        if isinstance(a, Num) and a.value == 0: return b
        if isinstance(b, Num) and b.value == 0: return a
        # 合并同类项
        if isinstance(a, Var) and isinstance(b, Var) and a.name == b.name: return Mul(Num(2), a)
        if isinstance(a, Var) and isinstance(b, Num): return Add(b, a)
        if isinstance(b, Var) and isinstance(a, Num): return Add(a, b)
        return Add(a, b)
    def evaluate(self, bindings): return self.left.evaluate(bindings) + self.right.evaluate(bindings)
    def substitute(self, var, value):
        return Add(self.left.substitute(var, value), self.right.substitute(var, value))
    def diff(self, var): return Add(self.left.diff(var), self.right.diff(var))
    def free_vars(self) -> set: return self.left.free_vars() | self.right.free_vars()
    def __str__(self): return f"({self.left} + {self.right})"

@dataclass(frozen=True)
class Sub(Expr):
    left: Expr
    right: Expr
    def simplify(self):
        a, b = self.left.simplify(), self.right.simplify()
        if isinstance(a, Num) and isinstance(b, Num): return Num(a.value - b.value)
        if isinstance(b, Num) and b.value == 0: return a
        if a == b: return Num(0)  # x - x = 0
        return Sub(a, b)
    def evaluate(self, bindings): return self.left.evaluate(bindings) - self.right.evaluate(bindings)
    def substitute(self, var, value):
        return Sub(self.left.substitute(var, value), self.right.substitute(var, value))
    def diff(self, var): return Sub(self.left.diff(var), self.right.diff(var))
    def free_vars(self) -> set: return self.left.free_vars() | self.right.free_vars()
    def __str__(self): return f"({self.left} - {self.right})"

@dataclass(frozen=True)
class Mul(Expr):
    left: Expr
    right: Expr
    def simplify(self):
        a, b = self.left.simplify(), self.right.simplify()
        if isinstance(a, Num) and isinstance(b, Num): return Num(a.value * b.value)
        if isinstance(a, Num) and a.value == 0: return Num(0)
        if isinstance(b, Num) and b.value == 0: return Num(0)
        if isinstance(a, Num) and a.value == 1: return b
        if isinstance(b, Num) and b.value == 1: return a
        if isinstance(a, Num) and isinstance(b, Var): return Mul(b, a)
        if isinstance(a, Var) and isinstance(b, Num): return Mul(a, b)
        # 同类项合并
        if isinstance(a, Var) and isinstance(b, Var) and a.name == b.name: return Pow(a, Num(2))
        if isinstance(a, Pow) and isinstance(b, Var):
            if isinstance(a.exponent, Num) and a.base.name == b.name:
                return Pow(a.base, Num(a.exponent.value + 1))
        if isinstance(b, Pow) and isinstance(a, Var):
            if isinstance(b.exponent, Num) and b.base.name == a.name:
                return Pow(b.base, Num(b.exponent.value + 1))
        return Mul(a, b)
    def evaluate(self, bindings): return self.left.evaluate(bindings) * self.right.evaluate(bindings)
    def substitute(self, var, value):
        return Mul(self.left.substitute(var, value), self.right.substitute(var, value))
    def diff(self, var):
        # 乘积法则
        return Add(Mul(self.left, self.right.diff(var)), Mul(self.left.diff(var), self.right))
    def free_vars(self) -> set: return self.left.free_vars() | self.right.free_vars()
    def __str__(self): return f"({self.left} * {self.right})"

@dataclass(frozen=True)
class Div(Expr):
    numerator: Expr
    denominator: Expr
    def simplify(self):
        a, b = self.numerator.simplify(), self.denominator.simplify()
        if isinstance(a, Num) and isinstance(b, Num):
            if b.value == 0: return Div(a, b)  # 保留除零表达式，延迟到求值时报错
            return Num(a.value / b.value)
        if isinstance(a, Num) and a.value == 0: return Num(0)
        if isinstance(b, Num) and b.value == 1: return a
        return Div(a, b)
    def evaluate(self, bindings):
        d = self.denominator.evaluate(bindings)
        if d == 0: raise ZeroDivisionError(f"除零: {self} at bindings={bindings}")
        return self.numerator.evaluate(bindings) / d
    def substitute(self, var, value):
        return Div(self.numerator.substitute(var, value), self.denominator.substitute(var, value))
    def diff(self, var):
        # 商法则
        n, d = self.numerator, self.denominator
        return Div(
            Sub(Mul(n.diff(var), d), Mul(n, d.diff(var))),
            Pow(d, Num(2))
        )
    def free_vars(self) -> set: return self.numerator.free_vars() | self.denominator.free_vars()
    def __str__(self): return f"({self.numerator} / {self.denominator})"

@dataclass(frozen=True)
class Pow(Expr):
    base: Expr
    exponent: Expr
    def simplify(self):
        a, b = self.base.simplify(), self.exponent.simplify()
        if isinstance(b, Num):
            if b.value == 0: return Num(1)
            if b.value == 1: return a
            if isinstance(a, Num): return Num(a.value ** b.value)
        return Pow(a, b)
    def evaluate(self, bindings):
        return self.base.evaluate(bindings) ** self.exponent.evaluate(bindings)
    def substitute(self, var, value):
        return Pow(self.base.substitute(var, value), self.exponent.substitute(var, value))
    def diff(self, var):
        # 通用幂法则: d/dx(f^g) = f^g * (g'*ln(f) + g*f'/f)
        if isinstance(self.exponent, Num) and self.exponent.value == 2:
            # x^2: 2x
            return Mul(Num(2), self.base)
        if isinstance(self.base, Var) and isinstance(self.exponent, Num):
            # x^n: n*x^(n-1)
            return Mul(self.exponent, Pow(self.base, Num(self.exponent.value - 1)))
        # 通用公式
        return Mul(
            self,
            Add(
                Mul(self.exponent.diff(var), Log(self.base)),
                Mul(self.exponent, Div(self.base.diff(var), self.base))
            )
        )
    def free_vars(self) -> set: return self.base.free_vars() | self.exponent.free_vars()
    def __str__(self): return f"({self.base} ^ {self.exponent})"


# 特殊函数
class Log(Expr):
    def __init__(self, expr): self.expr = expr
    def simplify(self): return Log(self.expr.simplify())
    def evaluate(self, bindings): import math; return math.log(self.expr.evaluate(bindings))
    def substitute(self, var, value): return Log(self.expr.substitute(var, value))
    def diff(self, var): return Div(self.expr.diff(var), self.expr)
    def free_vars(self) -> set: return self.expr.free_vars()
    def __str__(self): return f"ln({self.expr})"


class FuncCall(Expr):
    def __init__(self, name, args): self.name = name; self.args = args
    def simplify(self):
        return FuncCall(self.name, [a.simplify() for a in self.args])
    def evaluate(self, bindings):
        args = [a.evaluate(bindings) for a in self.args]
        if self.name == "sin": return math.sin(args[0])
        if self.name == "cos": return math.cos(args[0])
        if self.name == "tan": return math.tan(args[0])
        if self.name == "sqrt": return math.sqrt(args[0])
        if self.name == "abs": return abs(args[0])
        if self.name == "exp": return math.exp(args[0])
        if self.name == "log": return math.log(args[0]) if len(args) < 2 else math.log(args[0], args[1])
        if self.name == "floor": return math.floor(args[0])
        if self.name == "ceil": return math.ceil(args[0])
        if self.name == "factorial":
            v = int(args[0])
            return math.factorial(v) if 0 <= v <= 170 else float('inf')
        if self.name == "asin": return math.asin(args[0])
        if self.name == "acos": return math.acos(args[0])
        if self.name == "atan": return math.atan(args[0])
        raise ValueError(f"未知函数: {self.name}")
    def substitute(self, var, value):
        return FuncCall(self.name, [a.substitute(var, value) for a in self.args])
    def diff(self, var):
        if self.name == "sin": return Mul(FuncCall("cos", self.args), self.args[0].diff(var))
        if self.name == "cos": return Neg(Mul(FuncCall("sin", self.args), self.args[0].diff(var)))
        if self.name == "exp": return self
        if self.name == "log": return Div(Num(1), self.args[0])  # d/dx ln(x) = 1/x
        if self.name == "sqrt": return Div(Num(1), Mul(Num(2), FuncCall("sqrt", self.args)))  # d/dx sqrt(x) = 1/(2sqrt(x))
        if self.name == "abs": return Div(self.args[0], FuncCall("abs", self.args))  # d/dx |x| = x/|x|
        if self.name == "asin": return Div(self.args[0].diff(var), FuncCall("sqrt", [Sub(Num(1), Pow(self.args[0], Num(2)))]))
        if self.name == "acos": return Neg(Div(self.args[0].diff(var), FuncCall("sqrt", [Sub(Num(1), Pow(self.args[0], Num(2)))])))
        if self.name == "atan": return Div(self.args[0].diff(var), Add(Num(1), Pow(self.args[0], Num(2))))
        return FuncCall(f"d({self.name})", [a.diff(var) for a in self.args])
    def free_vars(self) -> set:
        result = set()
        for a in self.args: result.update(a.free_vars())
        return result
    def __str__(self):
        args_str = ', '.join(str(a) for a in self.args)
        return f"{self.name}({args_str})"


# ═══════════════════════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def to_expr(obj) -> Expr:
    """将 Python 值转换为 Expr 对象。"""
    if isinstance(obj, Expr): return obj
    if isinstance(obj, (int, float)): return Num(float(obj))
    if isinstance(obj, str):
        # 数字字符串 → Num，否则 → Var
        try: return Num(float(obj))
        except ValueError: return Var(obj)
    raise TypeError(f"无法转换 {type(obj).__name__} 为 Expr")


def symbolic(var: str = 'x') -> Var:
    """快捷创建符号变量。"""
    return Var(var)

x = symbolic('x')
y = symbolic('y')
z = symbolic('z')


# ═══════════════════════════════════════════════════════════════════════════════
#  符号表达式解析器
# ═══════════════════════════════════════════════════════════════════════════════

class SymbolicParser:
    """解析数学表达式字符串 → Expr AST。

    支持: x^2 + 3*x - 5, sin(x), sqrt(x), log(x, 10), 3!
    """

    FUNC_NAMES = {'sin', 'cos', 'tan', 'sqrt', 'abs', 'exp', 'log',
                  'floor', 'ceil', 'factorial', 'ln', 'asin', 'acos', 'atan'}
    # 识别变量名（字母开头，不含特殊字符）
    VAR_PATTERN = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')
    NUM_PATTERN = re.compile(r'[\d.]+')
    FUNC_PATTERN = re.compile(r'(sin|cos|tan|sqrt|abs|exp|log|ln|floor|ceil|factorial|asin|acos|atan)\(')

    def parse(self, text: str) -> Expr:
        """解析表达式字符串。"""
        text = text.strip()
        # 支持全角括号
        text = text.replace('（', '(').replace('）', ')')
        logger.info(f"  [符号解析] 解析: '{text}'")
        expr = self._parse_expr(text)
        simplified = expr.simplify()
        logger.info(f"  [符号解析] 结果: {simplified}")
        return simplified

    def _parse_expr(self, text: str) -> Expr:
        """解析加减表达式。"""
        text = text.strip()
        if not text:
            return Num(0)
        # 处理一元 + / - 前缀
        if text.startswith('-') and len(text) > 1:
            inner = self._parse_expr(text[1:])
            return Neg(inner)
        if text.startswith('+') and len(text) > 1:
            return self._parse_expr(text[1:])
        # 处理加法/减法
        segments = self._split_with_ops(text, ['+', '-'])
        if len(segments) > 1:
            left = self._parse_term(segments[0][0])
            result = left
            for part, op in segments[1:]:
                p = part.strip()
                if op == '-':
                    result = Sub(result, self._parse_term(p))
                else:
                    result = Add(result, self._parse_term(p))
            return result
        return self._parse_term(text)

    def _parse_term(self, text: str) -> Expr:
        """解析乘除表达式。"""
        text = text.strip()
        parts = self._split_with_ops(text, ['*', '/'])
        if len(parts) > 1:
            left = self._parse_term(parts[0][0])
            result = left
            for part, op in parts[1:]:
                p = part.strip()
                if op == '/':
                    result = Div(result, self._parse_term(p))
                else:
                    result = Mul(result, self._parse_term(p))
            return result
        return self._parse_power(text)

    def _parse_power(self, text: str) -> Expr:
        """解析幂运算。"""
        text = text.strip()
        # 去掉外层括号
        if text.startswith('(') and text.endswith(')'):
            text = text[1:-1]
        # 处理函数调用中的 ^ (如 sin(x^2))
        if '^' in text:
            depth = 0
            split_pos = -1
            for i, ch in enumerate(text):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                elif ch == '^' and depth == 0:
                    split_pos = i
                    break
            if split_pos >= 0:
                return Pow(self._parse_power(text[:split_pos]), self._parse_power(text[split_pos+1:]))
        return self._parse_primary(text)

    def _parse_primary(self, text: str) -> Expr:
        """解析基本单元：数字、变量、函数调用、括号表达式。"""
        text = text.strip()

        # 函数调用
        func_match = self.FUNC_PATTERN.match(text)
        if func_match:
            func_name = func_match.group(1)
            rest = text[func_match.end():].rstrip(')')
            args = self._split_top_level(rest, [','])
            parsed_args = [self._parse_expr(a.strip()) for a in args]
            return FuncCall(func_name, parsed_args)

        # 阶乘
        if text.endswith('!'):
            inner = self._parse_primary(text[:-1])
            return FuncCall("factorial", [inner])

        # 括号表达式（支持全角括号）
        text = text.replace('（', '(').replace('）', ')')
        if text.startswith('(') and text.endswith(')'):
            return self._parse_expr(text[1:-1])

        # 负号
        if text.startswith('-'):
            inner_text = text[1:]
            if not inner_text.strip():
                return Num(0)  # 负号后为空 → 0
            inner = self._parse_primary(inner_text)
            return Neg(inner)

        # 空字符串 → 0
        if not text.strip():
            return Num(0)

        # 数字
        if self.NUM_PATTERN.fullmatch(text):
            return Num(float(text))

        # 特殊常量 π
        if text == 'π':
            return Num(math.pi)

        # 变量
        if self.VAR_PATTERN.fullmatch(text):
            return Var(text)

        # 带变量的表达式（如 3x → 3*x，支持中文变量如 质量×加速度）
        match = re.match(r'^([+\-]?\d*\.?\d*)([a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*)$', text)
        if match:
            coeff = match.group(1)
            var_name = match.group(2)
            if coeff == '' or coeff == '+':
                return Var(var_name)
            elif coeff == '-':
                return Neg(Var(var_name))
            else:
                return Mul(Num(float(coeff)), Var(var_name))

        # 兜底：含加减号的表达式（如 v-v0），回退到表达式解析
        has_add = '+' in text
        has_sub = '-' in text[1:] if text.startswith('-') else '-' in text
        if has_add or has_sub:
            return self._parse_expr(text)
        # 含乘除号的表达式（如 r*r），回退到 term 解析
        has_mul = '*' in text
        has_div = '/' in text
        if has_mul or has_div:
            return self._parse_term(text)

        raise ValueError(f"无法解析表达式: '{text}'")

    def _split_top_level(self, text: str, separators: List[str]) -> List[str]:
        """在括号外按分隔符分割。"""
        parts = []
        depth = 0
        current = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif depth == 0 and ch in separators:
                parts.append(''.join(current))
                current = []
                # 跳过连续分隔符间的空格
                while i + 1 < len(text) and text[i+1] in separators:
                    i += 1
            else:
                current.append(ch)
            i += 1
        if current:
            parts.append(''.join(current))
        return parts

    def _split_with_ops(self, text: str, separators: List[str]) -> List[tuple]:
        """在括号外按分隔符分割，同时记录每个分隔符。
        返回 [(part0, op0), (part1, op1), ...]，part0 的 op 为 None。"""
        result = []
        depth = 0
        current = []
        i = 0
        last_sep = None  # 上一个分隔符，供当前片段使用
        while i < len(text):
            ch = text[i]
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif depth == 0 and ch in separators:
                # 当前片段结束，带上最后一个分隔符
                result.append((''.join(current), last_sep))
                current = []
                last_sep = ch  # 记录此分隔符供下一片段使用
                # 跳过连续分隔符
                while i + 1 < len(text) and text[i+1] in separators:
                    i += 1
                    last_sep = text[i]
            else:
                current.append(ch)
            i += 1
        # 最后一个片段
        result.append((''.join(current), last_sep))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  统一符号接口
# ═══════════════════════════════════════════════════════════════════════════════

_parser = SymbolicParser()

def symbol_expr(text: str) -> Expr:
    """解析符号表达式字符串。"""
    return _parser.parse(text)

def simplify_expr(expr: Expr) -> Expr:
    """简化表达式。"""
    return expr.simplify()

def diff_expr(expr: Expr, var: str = 'x') -> Expr:
    """对变量求导。"""
    return expr.diff(var)

def eval_expr(expr: Expr, **bindings) -> float:
    """数值求值。"""
    return expr.evaluate(bindings)

def ast_to_dict(expr: Expr) -> dict:
    """表达式转 AST 字典（用于代码生成）。"""
    return _expr_to_ast(expr).to_dict()

def _expr_to_ast(expr: Expr) -> ASTNode:
    """Expr → ASTNode 转换。"""
    if isinstance(expr, Num):
        return ASTNode(ASTNodeType.NUM, value=expr.value)
    elif isinstance(expr, Var):
        return ASTNode(ASTNodeType.VAR, value=expr.name)
    elif isinstance(expr, Neg):
        return ASTNode(ASTNodeType.NEG, children=[_expr_to_ast(expr.expr)])
    elif isinstance(expr, Add):
        return ASTNode(ASTNodeType.ADD, children=[_expr_to_ast(expr.left), _expr_to_ast(expr.right)])
    elif isinstance(expr, Sub):
        return ASTNode(ASTNodeType.SUB, children=[_expr_to_ast(expr.left), _expr_to_ast(expr.right)])
    elif isinstance(expr, Mul):
        return ASTNode(ASTNodeType.MUL, children=[_expr_to_ast(expr.left), _expr_to_ast(expr.right)])
    elif isinstance(expr, Div):
        return ASTNode(ASTNodeType.DIV, children=[_expr_to_ast(expr.numerator), _expr_to_ast(expr.denominator)])
    elif isinstance(expr, Pow):
        return ASTNode(ASTNodeType.POW, children=[_expr_to_ast(expr.base), _expr_to_ast(expr.exponent)])
    elif isinstance(expr, FuncCall):
        return ASTNode(ASTNodeType.FUNC, label=expr.name,
                       children=[_expr_to_ast(a) for a in expr.args])
    return ASTNode(ASTNodeType.VAR, value=str(expr))


# ═══════════════════════════════════════════════════════════════════════════════
#  LISP/Scheme 互操作
# ═══════════════════════════════════════════════════════════════════════════════

class LISPExpr:
    """LISP/Scheme 风格表达式，支持函数式编程互操作。"""

    @staticmethod
    def parse(s: str):
        """解析 LISP S-表达式。"""
        tokens = LISPExpr._tokenize(s)
        return LISPExpr._parse_tokens(tokens, 0)[0]

    @staticmethod
    def _tokenize(s: str) -> List[str]:
        tokens = []
        i = 0
        while i < len(s):
            if s[i].isspace():
                i += 1
                continue
            if s[i] == ';':
                while i < len(s) and s[i] != '\n': i += 1
                continue
            if s[i] in '()':
                tokens.append(s[i])
                i += 1
                continue
            # 字符串
            if s[i] == '"':
                j = i + 1
                while j < len(s) and s[j] != '"':
                    if s[j] == '\\': j += 1
                    j += 1
                tokens.append(s[i:j+1])
                i = j + 1
                continue
            # 数字
            if s[i].isdigit() or (s[i] == '-' and i+1 < len(s) and s[i+1].isdigit()):
                j = i
                while j < len(s) and (s[j].isdigit() or s[j] in '.-'): j += 1
                tokens.append(s[i:j])
                i = j
                continue
            # 符号
            j = i
            while j < len(s) and not s[j].isspace() and s[j] not in '()': j += 1
            tokens.append(s[i:j])
            i = j
        return tokens

    @staticmethod
    def _parse_tokens(tokens, pos):
        if pos >= len(tokens):
            raise ValueError("意外的结束")
        token = tokens[pos]
        if token == '(':
            items = []
            pos += 1
            while pos < len(tokens) and tokens[pos] != ')':
                item, pos = LISPExpr._parse_tokens(tokens, pos)
                items.append(item)
            if pos < len(tokens): pos += 1  # 跳过 ')'
            if items and isinstance(items[0], str) and items[0] in ('lambda', 'λ'):
                params = items[1]
                if not isinstance(params, list):
                    params = [params]
                body = items[2] if len(items) > 2 else Num(0)
                return ("lambda", params, body), pos
            return ("apply", items[0], items[1:]), pos
        elif token == ')':
            raise ValueError("意外的 ')'")
        # 字面量
        try:
            if '.' in token: return float(token), pos + 1
            return int(token), pos + 1
        except ValueError:
            return token, pos + 1

    @staticmethod
    def eval(expr, env: dict = None) -> Any:
        """求值 LISP 表达式。"""
        if env is None: env = {}
        if isinstance(expr, (int, float)): return expr
        if isinstance(expr, str) and not expr.startswith('('):
            return env.get(expr, expr)
        if isinstance(expr, list):
            op = expr[0]
            if op == 'lambda':
                return ("lambda", expr[1], expr[2], env)
            if op == 'apply':
                func = LISPExpr.eval(expr[1], env)
                args = [LISPExpr.eval(a, env) for a in expr[2:]]
                if isinstance(func, tuple) and func[0] == 'lambda':
                    new_env = dict(func[3])
                    for p, a in zip(func[1], args):
                        new_env[p] = a
                    return LISPExpr.eval(func[2], new_env)
                # 内建函数
                builtin = {'+': lambda *a: sum(a), '-': lambda a, b: a - b,
                           '*': lambda *a: eval('*'.join(str(x) for x in a)) if a else 1,
                           '/': lambda a, b: a / b,
                           'sqrt': lambda a: __import__('math').sqrt(a),
                           'sin': lambda a: __import__('math').sin(a),
                           'cos': lambda a: __import__('math').cos(a),
                           'abs': lambda a: abs(a),
                           'not': lambda a: not a,
                           'if': lambda cond, t, f: t if cond else f,
                           'cons': lambda h, t: [h] + t if isinstance(t, list) else [h, t],
                           'car': lambda l: l[0] if l else None,
                           'cdr': lambda l: l[1:] if l else [],
                           'length': lambda l: len(l) if isinstance(l, list) else 0,
                           'map': lambda f, l: [LISPExpr.eval(f, {'x': x}) for x in l] if isinstance(l, list) else [],
                           'reduce': lambda f, init, l: reduce(f, l, init) if isinstance(l, list) else init,
                           'let': lambda bindings, body: LISPExpr.eval(body, {**env, **bindings}),
                }
                if op in builtin:
                    return builtin[op](*args)
                raise ValueError(f"未知函数: {op}")
        return expr

    def __init__(self, *args):
        self.tokens = args
    def __call__(self, *args):
        return LISPExpr.eval(self.tokens[0] if self.tokens else 0, {})

    def __str__(self):
        if isinstance(self.tokens, (int, float)): return str(self.tokens)
        if isinstance(self.tokens, str): return self.tokens
        return '(' + ' '.join(str(t) for t in self.tokens) + ')'


# ═══════════════════════════════════════════════════════════════════════════════
#  便捷 API
# ═══════════════════════════════════════════════════════════════════════════════

def symbolic_calc(expression: str, **bindings) -> dict:
    """统一符号计算接口。"""
    parser = SymbolicParser()
    expr = parser.parse(expression)
    simplified = expr.simplify()
    try:
        value = expr.evaluate(bindings)
    except:
        value = None
    return {
        "expression": expression,
        "simplified": str(simplified),
        "derivative": str(expr.diff(list(bindings.keys())[0] if bindings else 'x')),
        "value": value,
        "bindings": bindings,
    }


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha 符号引擎 v1.3.0")
    print("=" * 60)

    # 基本运算
    print("\n[基本符号运算]")
    expr = symbol_expr("x^2 + 3*x - 5")
    print(f"  表达式: {expr}")
    print(f"  简化:   {expr.simplify()}")
    print(f"  导数:   {expr.diff('x')}")
    print(f"  求值(x=2): {expr.evaluate({'x': 2})}")

    # 函数
    print("\n[函数运算]")
    sin_expr = symbol_expr("sin(x)")
    print(f"  sin(x) 导数: {sin_expr.diff('x')}")
    print(f"  sin(π/2)   = {sin_expr.evaluate({'x': 3.14159/2})}")

    # 链式法则
    print("\n[链式法则]")
    chain = symbol_expr("sin(x^2)")
    print(f"  sin(x^2) 导数: {chain.diff('x')}")

    # LISP
    print("\n[LISP/Scheme 互操作]")
    lisp = LISPExpr.parse("(+ (* 2 3) (- 10 4))")
    print(f"  (+ (* 2 3) (- 10 4)) = {lisp}")

    print("\n完成。")
