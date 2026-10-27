"""Matha 符号引擎：Expr 代数层 + MathaSymbolic 引擎（两套 API 并存）。

A 组 Expr 代数层：Expr/Num/Var/Neg/Add/Sub/Mul/Div/Pow/Log/FuncCall、
    to_expr、symbolic、SymbolicParser、symbol_expr、simplify_expr、
    diff_expr、eval_expr、ast_to_dict、LISPExpr、symbolic_calc。
B 组 MathaSymbolic 引擎：SymbolType、Symbol、Expression、Equation、
    MathaSymbolic、create_symbol、parse_expression、differentiate、
    solve_equation、_register_symbolic、_symbolic_symtab_names。

A 组的 to_expr/symbol_expr/simplify_expr/diff_expr/eval_expr/ast_to_dict
以 A 组签名为准，B 组不重复定义这些名字。
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import reduce
from typing import Any

logger = logging.getLogger("matha.symbolic")
# ═══════════════════════════════════════════════════════════════════════════
#  统一符号接口（已迁入内核，此处再导出）
# ═══════════════════════════════════════════════════════════════════════════

# A 组（AST 节点体系 + Expr 代数层 + SymbolicParser + 统一符号接口）已迁入内核
# （阶段 3：核心零第三方依赖）。本模块只做再导出，既有引用零改动。
from src.kernel.symbolic.astnodes import ASTNode, ASTNodeType  # noqa: E402,F401
from src.kernel.symbolic.expr import (  # noqa: E402,F401
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
    SymbolicParser, _expr_to_ast, _parser, ast_to_dict, eval_expr,
    symbol_expr, symbolic, to_expr, x, y, z,
)
from src.kernel.symbolic.simplify import simplify_expr  # noqa: E402,F401
from src.kernel.symbolic.diff import diff_expr  # noqa: E402,F401


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
    def _tokenize(s: str) -> list[str]:
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
    except Exception:
        value = None
    return {
        "expression": expression,
        "simplified": str(simplified),
        "derivative": str(expr.diff(list(bindings.keys())[0] if bindings else 'x')),
        "value": value,
        "bindings": bindings,
    }


class SymbolType(Enum):
    """符号类型。"""
    VARIABLE = "variable"
    CONSTANT = "constant"
    FUNCTION = "function"
    OPERATOR = "operator"
    EXPRESSION = "expression"


@dataclass
class Symbol:
    """符号。"""
    name: str
    type: SymbolType = SymbolType.VARIABLE
    value: Any = None

    def __repr__(self) -> str:
        return f"Symbol({self.name})"


@dataclass
class Expression:
    """数学表达式。"""
    operator: str = ""
    operands: list[Any] = field(default_factory=list)
    simplified: bool = False

    def __repr__(self) -> str:
        return f"Expr({self.operator}, {self.operands})"


@dataclass
class Equation:
    """方程。"""
    left: Expression = field(default_factory=Expression)
    right: Expression = field(default_factory=Expression)
    variable: str = "x"

    def __repr__(self) -> str:
        return f"Eq({self.left} = {self.right})"


class MathaSymbolic:
    """Matha 符号计算引擎。"""

    def __init__(self):
        self._symbols: dict[str, Symbol] = {}
        self._expressions: list[Expression] = []
        self._initialized = False
        self._init_symbolic()

    def _init_symbolic(self) -> None:
        """初始化符号计算。"""
        self._initialized = True
        # 预定义常量
        self._symbols["pi"] = Symbol("pi", SymbolType.CONSTANT, 3.141592653589793)
        self._symbols["e"] = Symbol("e", SymbolType.CONSTANT, 2.718281828459045)
        self._symbols["inf"] = Symbol("inf", SymbolType.CONSTANT, float('inf'))

    def symbol(self, name: str, value: Any = None
                    ) -> Symbol:
        """创建符号变量。"""
        sym = Symbol(name=name, type=SymbolType.VARIABLE, value=value)
        self._symbols[name] = sym
        return sym

    def parse(self, expression: str) -> Expression:
        """解析表达式字符串。"""
        # 简单的表达式解析
        expr = Expression()
        # 查找运算符
        if '+' in expression:
            parts = expression.split('+', 1)
            expr = Expression(operator='+', operands=[
                self.parse(parts[0].strip()),
                self.parse(parts[1].strip())
            ])
        elif '-' in expression and expression[0] != '-':
            parts = expression.split('-', 1)
            expr = Expression(operator='-', operands=[
                self.parse(parts[0].strip()),
                self.parse(parts[1].strip())
            ])
        elif '*' in expression:
            parts = expression.split('*', 1)
            expr = Expression(operator='*', operands=[
                self.parse(parts[0].strip()),
                self.parse(parts[1].strip())
            ])
        elif '/' in expression:
            parts = expression.split('/', 1)
            expr = Expression(operator='/', operands=[
                self.parse(parts[0].strip()),
                self.parse(parts[1].strip())
            ])
        elif '^' in expression:
            parts = expression.split('^', 1)
            expr = Expression(operator='**', operands=[
                self.parse(parts[0].strip()),
                self.parse(parts[1].strip())
            ])
        elif re.match(r'^[a-zA-Z_]\w*$', expression):
            # 变量名
            sym = self._symbols.get(expression)
            if sym:
                expr = Expression(operator='symbol', operands=[sym])
            else:
                expr = Expression(operator='symbol', operands=[
                    Symbol(name=expression)
                ])
        elif expression.replace('.', '').replace('-', '').isdigit():
            # 数字
            expr = Expression(operator='number', operands=[float(expression)])
        else:
            expr = Expression(operator='unknown', operands=[expression])

        self._expressions.append(expr)
        return expr

    def simplify(self, expr: Expression) -> Expression:
        """简化表达式。"""
        if expr.operator == '+':
            left = self.simplify(expr.operands[0])
            right = self.simplify(expr.operands[1])
            # 数字相加
            if self._is_number(left) and self._is_number(right):
                return Expression(operator='number',
                                    operands=[left.operands[0].value + right.operands[0].value])
            # 0 + x = x
            if self._is_zero(left):
                return right
            if self._is_zero(right):
                return left
        return expr

    def _is_number(self, expr: Expression) -> bool:
        return expr.operator == 'number'

    def _is_zero(self, expr: Expression) -> bool:
        return expr.operator == 'number' and expr.operands and expr.operands[0].value == 0

    def diff(self, expr: Expression, var: str = "x"
                 ) -> Expression:
        """求导。"""
        if expr.operator == 'number':
            return Expression(operator='number', operands=[0])
        if expr.operator == 'symbol':
            sym = expr.operands[0] if expr.operands else Symbol(var)
            if sym.name == var:
                return Expression(operator='number', operands=[1])
            return Expression(operator='number', operands=[0])
        if expr.operator == '+':
            return Expression(operator='+', operands=[
                self.diff(expr.operands[0], var),
                self.diff(expr.operands[1], var)
            ])
        if expr.operator == '*':
            # 乘积法则
            u = expr.operands[0]
            v = expr.operands[1]
            return Expression(operator='+', operands=[
                Expression(operator='*', operands=[
                    self.diff(u, var), v
                ]),
                Expression(operator='*', operands=[
                    u, self.diff(v, var)
                ])
            ])
        if expr.operator == '**':
            # 幂法则
            base = expr.operands[0]
            exp = expr.operands[1]
            return Expression(operator='*', operands=[
                Expression(operator='*', operands=[
                    exp, base
                ]),
                Expression(operator='**', operands=[
                    base, Expression(operator='-', operands=[
                        exp, Expression(operator='number', operands=[1])
                    ])
                ])
            ])
        return expr

    def solve(self, equation: Equation
                 ) -> list[float]:
        """求解方程。"""
        var = equation.variable
        # 简单一元一次方程求解
        expr = equation.left
        if expr.operator == '=':
            return []
        if expr.operator == '+':
            # ax + b = 0
            pass
        # 数值求解
        return self._numerical_solve(equation, var)

    def _numerical_solve(self, equation: Equation,
                           var: str) -> list[float]:
        """数值求解。"""
        solutions = []
        # 牛顿法简单实现
        x = 0.0
        for _ in range(100):
            val = self._evaluate(equation.left, {var: x})
            deriv = self._derivative(equation.left, var)
            if abs(deriv) < 1e-10:
                break
            x_new = x - val / deriv
            if abs(x_new - x) < 1e-6:
                solutions.append(x_new)
                break
            x = x_new
        return solutions

    def _evaluate(self, expr: Expression,
                     vars_dict: dict[str, float]) -> float:
        """求值。"""
        if expr.operator == 'number':
            return expr.operands[0].value if expr.operands else 0
        if expr.operator == 'symbol':
            sym = expr.operands[0] if expr.operands else Symbol("")
            return vars_dict.get(sym.name, 0)
        if expr.operator == '+':
            return self._evaluate(expr.operands[0], vars_dict) + \
                   self._evaluate(expr.operands[1], vars_dict)
        if expr.operator == '-':
            return self._evaluate(expr.operands[0], vars_dict) - \
                   self._evaluate(expr.operands[1], vars_dict)
        if expr.operator == '*':
            return self._evaluate(expr.operands[0], vars_dict) * \
                   self._evaluate(expr.operands[1], vars_dict)
        if expr.operator == '/':
            return self._evaluate(expr.operands[0], vars_dict) / \
                   (self._evaluate(expr.operands[1], vars_dict) or 1)
        if expr.operator == '**':
            return self._evaluate(expr.operands[0], vars_dict) ** \
                   self._evaluate(expr.operands[1], vars_dict)
        return 0.0

    def _derivative(self, expr: Expression,
                       var: str) -> float:
        """数值求导。"""
        h = 1e-7
        return (self._evaluate(expr, {var: h}) -
                self._evaluate(expr, {var: -h})) / (2 * h)

    def integrate(self, expr: Expression, var: str = "x"
                      ) -> Expression:
        """积分（符号）。"""
        # 幂函数积分
        if expr.operator == '**':
            base = expr.operands[0]
            exp = expr.operands[1]
            return Expression(operator='**', operands=[
                base,
                Expression(operator='+', operands=[
                    exp, Expression(operator='number', operands=[1])
                ])
            ])
        return expr

    def limit(self, expr: Expression, var: str,
                 approach: float = 0.0) -> float:
        """极限。"""
        return self._evaluate(expr, {var: approach})

    def series(self, expr: Expression, var: str,
                  order: int = 5) -> list[float]:
        """泰勒展开。"""
        coeffs = []
        for n in range(order):
            deriv = self._nth_derivative(expr, var, n)
            coeffs.append(deriv / math.factorial(n))
        return coeffs

    def _nth_derivative(self, expr: Expression, var: str,
                           n: int) -> float:
        """n阶导数。"""
        result = expr
        for _ in range(n):
            result = self.diff(result, var)
        return self._evaluate(result, {var: 0})

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "symbols": len(self._symbols),
            "expressions": len(self._expressions),
        }


# ============================================================
# 内置注册
# ============================================================

def create_symbol(name: str, value: Any = None) -> Symbol:
    """创建符号。"""
    ms = MathaSymbolic()
    return ms.symbol(name, value)


def parse_expression(expr: str) -> Expression:
    """解析表达式。"""
    ms = MathaSymbolic()
    return ms.parse(expr)


def differentiate(expr: Expression, var: str = "x"
                      ) -> Expression:
    """求导。"""
    ms = MathaSymbolic()
    return ms.diff(expr, var)


def solve_equation(eq: Equation) -> list[float]:
    """求解方程。"""
    ms = MathaSymbolic()
    return ms.solve(eq)


def _register_symbolic(builtins: dict) -> None:
    """注册符号计算内置函数。"""
    builtins["创建符号"] = create_symbol
    builtins["解析表达式"] = parse_expression
    builtins["求导"] = differentiate
    builtins["求解方程"] = solve_equation


def _symbolic_symtab_names() -> list[str]:
    return [
        "创建符号", "解析表达式", "求导", "求解方程",
    ]


__all__ = [
    # A 组：Expr 代数层
    "ASTNodeType", "ASTNode", "Expr", "Num", "Var", "Neg", "Add", "Sub",
    "Mul", "Div", "Pow", "Log", "FuncCall", "to_expr", "symbolic",
    "SymbolicParser", "symbol_expr", "simplify_expr", "diff_expr",
    "eval_expr", "ast_to_dict", "LISPExpr", "symbolic_calc",
    # B 组：MathaSymbolic 引擎
    "SymbolType", "Symbol", "Expression", "Equation", "MathaSymbolic",
    "create_symbol", "parse_expression", "differentiate", "solve_equation",
    "_register_symbolic", "_symbolic_symtab_names",
]