"""内核符号引擎 · Expr 代数层 + 文本解析器（纯标准库）。

由原 `src/symbolic.py`「A 组 Expr 代数层」/「SymbolicParser」/「统一符号接口」整体迁入，
语义逐字保留（既有 16 处 `from src.symbolic import ...` 经再导出零改动）。

本模块只提供**数据层与文本→AST**；算法在包内其他模块：
求导 `diff.py`、化简 `simplify.py`、积分 `integrate.py`、极限 `limit.py`、
级数 `series.py`、ODE `ode.py`、定义域 `domain.py`、输出与解析门面 `latex.py`。

内核红线：只用标准库，**不得** import sympy/numpy/scipy/numba/tree_sitter/ctypes。
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from functools import reduce
from typing import Any

logger = logging.getLogger("matha.kernel.symbolic")

from src.kernel.symbolic.astnodes import ASTNode, ASTNodeType  # noqa: E402,F401


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

    def simplify(self) -> Expr: return self

    def _children(self) -> list[Expr]:
        import dataclasses as _dc
        if not _dc.is_dataclass(self):
            # FuncCall/Log 不是 dataclass：按约定属性取子节点
            args = getattr(self, "args", None)
            if args is not None:
                return list(args)
            inner = getattr(self, "expr", None)
            return [inner] if isinstance(inner, Expr) else []
        out: list[Expr] = []
        for f in _dc.fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Expr):
                out.append(v)
            elif isinstance(v, tuple):
                out.extend(e for e in v if isinstance(e, Expr))
        return out

    def diff(self, var: str) -> Expr:
        name = type(self).__name__
        if name in ("Add", "Sub", "Mul", "Div", "Pow"):
            a, b = self._children()
            da, db = a.diff(var), b.diff(var)
            if name == "Add":
                return Add(da, db)
            if name == "Sub":
                return Sub(da, db)
            if name == "Mul":
                return Add(Mul(da, b), Mul(a, db))
            if name == "Div":
                return Div(Sub(Mul(da, b), Mul(a, db)), Mul(b, b))
            if name == "Pow":
                return Mul(b, Mul(Pow(a, Sub(b, Num(1))), da))
        if name == "Neg":
            return Neg(self._children()[0].diff(var))
        if isinstance(self, (Num, Var)):
            return Num(0) if isinstance(self, (Num, Var)) else self
        raise ValueError(f"表达式类型 {name} 未实现 diff()")

    def evaluate(self,
                 bindings: dict[str, float] = None) -> float:
        name = type(self).__name__
        values = [c.evaluate(bindings) for c in self._children()]
        if name == "Add":
            return values[0] + values[1]
        if name == "Sub":
            return values[0] - values[1]
        if name == "Mul":
            return values[0] * values[1]
        if name == "Div":
            return values[0] / values[1]
        if name == "Pow":
            return values[0] ** values[1]
        if name == "Neg":
            return -values[0]
        if isinstance(self, Num):
            return float(self.value)
        if isinstance(self, Var):
            if bindings and self.name in bindings:
                return float(bindings[self.name])
            raise ValueError(f"未绑定变量: {self.name}")
        raise ValueError(f"表达式类型 {name} 未实现 evaluate()")

    def substitute(self, var: str, value: Expr) -> Expr:
        import dataclasses as _dc
        if isinstance(self, Var):
            return value if self.name == var else self
        kwargs = {}
        for f in _dc.fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Expr):
                kwargs[f.name] = v.substitute(var, value)
            elif isinstance(v, tuple):
                kwargs[f.name] = tuple(
                    e.substitute(var, value) if isinstance(e, Expr) else e
                    for e in v
                )
            else:
                kwargs[f.name] = v
        return type(self)(**kwargs)

    def free_vars(self) -> set:
        result: set = set()
        for c in self._children():
            result |= c.free_vars()
        return result

    def __str__(self):
        name = type(self).__name__
        if isinstance(self, Num):
            return str(int(self.value)) if self.value == int(self.value) \
                else str(self.value)
        if isinstance(self, Var):
            return self.name
        ops = {"Add": "+", "Sub": "-", "Mul": "*",
               "Div": "/", "Pow": "**", "Neg": "-"}
        if name in ("Add", "Sub", "Mul", "Div", "Pow"):
            a, b = self._children()
            return f"({a} {ops[name]} {b})"
        if name == "Neg":
            return f"(-{self._children()[0]})"
        children = [str(c) for c in self._children()]
        return f"{name}({', '.join(children)})" if children else name

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
        # 常数项一律排在后面（sympy 口径：`x + 1`、`2*x`）
        if isinstance(a, Num) and not isinstance(b, Num): return Add(b, a)
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
        if isinstance(a, Var) and isinstance(b, Num): return Mul(b, a)
        if isinstance(b, Var) and isinstance(a, Num): return Mul(a, b)
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
    def evaluate(self, bindings): return math.log(self.expr.evaluate(bindings))
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
    # 通用函数调用：math.sqrt(...)、safe_div(...) 等（函数名允许点号限定）
    GEN_FUNC_PATTERN = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\((.*)\)$')

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
        # `**` 与 `^` 同义（Matha 用 ^，Python 习惯用 **）；统一成 ^ 后再拆运算符，
        # 避免 `x**2` 被 `*` 拆成空段而降价为 `2*x`。
        text = text.replace("**", "^")
        if not text:
            return Num(0)
        # 一元负号不在此提前取走：`-2*y + exp(-x)` 会被当成 `-(2*y + exp(-x))`，
        # 整体变号。交由 `_split_with_ops` 的一元识别处理，保证只作用于首项。
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
        text = text.strip().replace("**", "^")
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
        """解析幂运算。

        只在**括号深度 0** 处切分 `^`，且绝不先剥外层括号：否则
        `(x**2-1)/(x-1)` 会被剥括号后在 `^` 处切成 `x` 与 `2-1`，
        而指数分支 `_parse_primary("2-1")` 只取数字 `2`，静默丢掉 `-1`。
        """
        text = text.strip().replace("**", "^")
        split_pos = -1
        depth = 0
        for i, ch in enumerate(text):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == '^' and depth == 0:
                split_pos = i
                break
        if split_pos < 0:
            return self._parse_primary(text)
        base = self._parse_power(text[:split_pos])
        exp_txt = text[split_pos + 1:].strip()
        if exp_txt.startswith('-'):
            exponent = Neg(self._parse_power(exp_txt[1:]))
        else:
            exponent = self._parse_power(exp_txt)
        # `-x**2` 的幂优先于一元负号（Python/sympy 口径：-(x**2)）
        if isinstance(base, Neg):
            return Neg(Pow(base.expr, exponent))
        return Pow(base, exponent)

    def _parse_primary(self, text: str) -> Expr:
        """解析基本单元：数字、变量、函数调用、括号表达式。"""
        text = text.strip()

        # 函数调用（用配对括号取参，不用 rstrip(')')：否则
        # `cos((2*x))` 这类嵌套括号会剩不配对的内层而解析失败）
        func_match = self.FUNC_PATTERN.match(text)
        if func_match:
            func_name = func_match.group(1)
            inner, tail = self._match_paren(text[func_match.end() - 1:])
            if inner is not None and not tail.strip():
                args = self._split_top_level(inner, [','])
                parsed_args = [self._parse_expr(a.strip()) for a in args]
                return FuncCall(func_name, parsed_args)

        # 通用函数调用（含 math.sqrt / safe_div 等点号限定名或自定义函数）
        gen_func = self.GEN_FUNC_PATTERN.match(text)
        if gen_func:
            func_name = gen_func.group(1).split('.')[-1]
            rest = gen_func.group(2)
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

        # 兜底：含加减号的表达式（如 v-v0），回退到表达式解析。
        # 仅当顶层确实存在可拆分运算符时才回退，否则 _parse_expr 会以
        # 同一文本重新进入本方法造成无限递归（运算符在括号/函数内时）。
        has_add = '+' in text
        has_sub = '-' in text[1:] if text.startswith('-') else '-' in text
        if (has_add or has_sub) and len(self._split_with_ops(text, ['+', '-'])) > 1:
            return self._parse_expr(text)
        # 含乘除号的表达式（如 r*r），回退到 term 解析（同样要求顶层可拆）
        has_mul = '*' in text
        has_div = '/' in text
        if (has_mul or has_div) and len(self._split_with_ops(text, ['*', '/'])) > 1:
            return self._parse_term(text)

        raise ValueError(f"无法解析表达式: '{text}'")

    def _match_paren(self, text: str) -> tuple[str | None, str]:
        """``text`` 以 ``'('`` 开头时返回 ``(括号内内容, 剩余尾部)``。"""
        if not text.startswith('('):
            return None, text
        depth = 0
        for i, ch in enumerate(text):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return text[1:i], text[i + 1:]
        return None, text

    def _split_top_level(self, text: str, separators: list[str]) -> list[str]:
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

    def _split_with_ops(self, text: str, separators: list[str]) -> list[tuple]:
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
            elif depth == 0 and ch in separators and not (
                    ch in '+-' and self._is_unary(''.join(current))):
                # 一元 +/-：前一非空字符是运算符 / 左括号 / 行首时，符号属于操作数本身，
                # 不能在此切分——否则 `x^-2` 被拆成 `x^` 与 `2`，静默降价为 `-1`。
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

    _UNARY_PRECEDERS = ('-', '+', '*', '/', '^', '(', '[', ',')

    @classmethod
    def _is_unary(cls, prefix: str) -> bool:
        """``prefix`` 末尾（忽略空白）是否要求其后紧跟一元符号。"""
        s = prefix.rstrip()
        return not s or s[-1] in cls._UNARY_PRECEDERS

# ═══════════════════════════════════════════════════════════════════════════
#  统一符号接口（数据层部分）
# ═══════════════════════════════════════════════════════════════════════════

_parser = SymbolicParser()


def symbol_expr(text: str) -> Expr:
    """解析符号表达式字符串。"""
    return _parser.parse(text)


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
