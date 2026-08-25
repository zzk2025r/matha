# -*- coding: utf-8 -*-
"""Matha v4.2 — 代数运算标准库

提供代数核心功能：
  - 多项式运算：加减乘除、因式分解
  - 方程求解：一元一次、一元二次
  - 因式分解：质因数、多项式因式
  - 代数化简：合并同类项、展开公式

数学表达：
  所有函数遵循代数结构定义，确保数学严谨性。

用法：
  from src.stdlib.algebra import (
      solve_quadratic, factor_polynomial,
      simplify_expression, expand_expression,
      gcd_poly, lcm_poly,
  )
"""
from __future__ import annotations
import math
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass


# ============================================================
# 代数数据类
# ============================================================

@dataclass
class Polynomial:
    """多项式：a_n·x^n + ... + a_1·x + a_0"""
    coefficients: List[float]  # [a_0, a_1, ..., a_n]

    def degree(self) -> int:
        """获取多项式次数。"""
        # 去除尾部零系数
        while len(self.coefficients) > 1 and self.coefficients[-1] == 0:
            self.coefficients.pop()
        return len(self.coefficients) - 1

    def evaluate(self, x: float) -> float:
        """求值：P(x)。"""
        result = 0.0
        for i, c in enumerate(self.coefficients):
            result += c * (x ** i)
        return result

    def __str__(self) -> str:
        """转为可读字符串。"""
        terms = []
        for i, c in enumerate(self.coefficients):
            if c == 0:
                continue
            if i == 0:
                terms.append(f"{c}")
            elif i == 1:
                terms.append(f"{c}x" if c != 1 else "x")
            else:
                terms.append(f"{c}x^{i}" if c != 1 else f"x^{i}")
        return " + ".join(reversed(terms)) if terms else "0"

    def __add__(self, other: 'Polynomial') -> 'Polynomial':
        """多项式加法。"""
        max_len = max(len(self.coefficients), len(other.coefficients))
        result = [0.0] * max_len
        for i, c in enumerate(self.coefficients):
            result[i] += c
        for i, c in enumerate(other.coefficients):
            result[i] += c
        return Polynomial(result)

    def __mul__(self, other: 'Polynomial') -> 'Polynomial':
        """多项式乘法。"""
        result = [0.0] * (len(self.coefficients) + len(other.coefficients) - 1)
        for i, a in enumerate(self.coefficients):
            for j, b in enumerate(other.coefficients):
                result[i + j] += a * b
        return Polynomial(result)


# ============================================================
# 方程求解
# ============================================================

def solve_linear(a: float, b: float) -> Optional[float]:
    """
    求解一元一次方程：ax + b = 0

    数学定义：
      solve_linear: ℝ × ℝ → ℝ ∪ {None}
      solve_linear(a, b) = -b/a  if a ≠ 0, else None

    Args:
        a: x 的系数
        b: 常数项

    Returns:
        解 x，无解时返回 None

    Examples:
        >>> solve_linear(2, -4)
        2.0
        >>> solve_linear(0, 5)
        None
    """
    if abs(a) < 1e-12:
        return None
    return -b / a


def solve_quadratic(a: float, b: float, c: float) -> List[complex]:
    """
    求解一元二次方程：ax² + bx + c = 0

    数学定义：
      x = (-b ± √(b²-4ac)) / (2a)

    Args:
        a, b, c: 方程系数

    Returns:
        解列表（可能含复数）

    Examples:
        >>> solve_quadratic(1, -3, 2)
        [2.0, 1.0]
        >>> solve_quadratic(1, 2, 5)
        [(-1+2j), (-1-2j)]
    """
    if abs(a) < 1e-12:
        # 退化为线性方程
        if abs(b) < 1e-12:
            return []
        return [complex(-c / b)]

    discriminant = b * b - 4 * a * c

    if discriminant > 1e-12:
        sqrt_d = math.sqrt(discriminant)
        return [(-b + sqrt_d) / (2 * a), (-b - sqrt_d) / (2 * a)]
    elif abs(discriminant) < 1e-12:
        return [complex(-b / (2 * a))]
    else:
        real_part = -b / (2 * a)
        imag_part = math.sqrt(-discriminant) / (2 * a)
        return [complex(real_part, imag_part), complex(real_part, -imag_part)]


def solve_system_linear(eqs: List[Tuple[float, float, float]]) -> Optional[Tuple[float, float]]:
    """
    求解二元一次方程组：
      a₁x + b₁y = c₁
      a₂x + b₂y = c₂

    Args:
        eqs: 方程系数列表 [(a1, b1, c1), (a2, b2, c2)]

    Returns:
        (x, y) 或 None（无解/无穷多解）
    """
    if len(eqs) < 2:
        return None

    a1, b1, c1 = eqs[0]
    a2, b2, c2 = eqs[1]

    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-12:
        return None  # 无唯一解

    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    return (x, y)


# ============================================================
# 因式分解
# ============================================================

def factor_integer(n: int) -> Dict[int, int]:
    """
    整数因式分解：n = p1^a1 × p2^a2 × ... × pk^ak

    返回 {素数: 指数} 字典。

    Examples:
        >>> factor_integer(60)
        {2: 2, 3: 1, 5: 1}
    """
    if n < 0:
        result = {-1: 1}
        n = -n
    else:
        result = {}

    d = 2
    while d * d <= n:
        while n % d == 0:
            result[d] = result.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        result[n] = result.get(n, 0) + 1

    return result


def factor_polynomial_simple(coeffs: List[float]) -> str:
    """
    简单多项式因式分解（仅处理二次多项式）。

    对于 ax² + bx + c，尝试因式分解为 (px + q)(rx + s)。
    """
    if len(coeffs) < 3:
        return str(Polynomial(coeffs))

    a, b, c = coeffs[0], coeffs[1], coeffs[2]
    roots = solve_quadratic(c, b, a)  # 注意系数顺序

    if len(roots) == 2 and all(isinstance(r, float) for r in roots):
        r1, r2 = roots
        # 避免浮点精度问题
        if abs(r1 - round(r1)) < 1e-6:
            r1 = round(r1)
        if abs(r2 - round(r2)) < 1e-6:
            r2 = round(r2)
        return f"({a}x - {r1*a})({x} - {r2})"

    return str(Polynomial(coeffs))


# ============================================================
# 代数化简
# ============================================================

def simplify_expression(expr: str) -> str:
    """
    简化表达式（基础版）。

    支持：
    - 合并同类项
    - 消除零项
    - 简化常数和
    """
    import re

    # 移除多余空格
    expr = re.sub(r'\s+', ' ', expr.strip())

    # 尝试数值计算
    try:
        # 安全评估仅数字表达式
        if re.match(r'^[\d\s+\-*/().^√πe]+$', expr):
            expr = expr.replace('π', str(math.pi)).replace('e', str(math.e))
            result = eval(expr, {"__builtins__": {}}, {})
            if isinstance(result, (int, float)):
                return f"{result:.6f}".rstrip('0').rstrip('.')
    except (SyntaxError, ZeroDivisionError, NameError):
        pass

    return expr


def expand_expression(expr: str) -> str:
    """
    展开表达式（基础版）。

    支持 (a+b)(c+d) 形式展开。
    """
    import re

    # 匹配 (a+b)(c+d) 模式
    pattern = r'\(([^)]+)\)\(([^)]+)\)'
    match = re.search(pattern, expr)
    if match:
        left = match.group(1)
        right = match.group(2)
        # 简单展开
        terms = []
        for l in re.split(r'[+\-]', left):
            for r in re.split(r'[+\-]', right):
                if l and r:
                    terms.append(f"({l}×{r})")
        return " + ".join(terms)

    return expr


# ============================================================
# 代数运算
# ============================================================

def poly_add(p1: List[float], p2: List[float]) -> List[float]:
    """多项式加法。"""
    max_len = max(len(p1), len(p2))
    result = [0.0] * max_len
    for i, c in enumerate(p1):
        result[i] += c
    for i, c in enumerate(p2):
        result[i] += c
    return result


def poly_mul(p1: List[float], p2: List[float]) -> List[float]:
    """多项式乘法。"""
    result = [0.0] * (len(p1) + len(p2) - 1)
    for i, a in enumerate(p1):
        for j, b in enumerate(p2):
            result[i + j] += a * b
    return result


def poly_div(p1: List[float], p2: List[float]) -> Tuple[List[float], List[float]]:
    """
    多项式除法：p1 = p2 × q + r

    Returns:
        (quotient, remainder)
    """
    if not p2 or abs(p2[-1]) < 1e-12:
        raise ValueError("除式不能为零多项式")

    dividend = p1[:]
    divisor = p2[:]

    # 去除尾部零
    while len(dividend) > 1 and abs(dividend[-1]) < 1e-12:
        dividend.pop()
    while len(divisor) > 1 and abs(divisor[-1]) < 1e-12:
        divisor.pop()

    if len(dividend) < len(divisor):
        return [0.0], dividend

    quotient = [0.0] * (len(dividend) - len(divisor) + 1)

    for i in range(len(dividend) - len(divisor), -1, -1):
        if abs(divisor[-1]) < 1e-12:
            break
        coeff = dividend[i + len(divisor) - 1] / divisor[-1]
        quotient[i] = coeff
        for j in range(len(divisor)):
            dividend[i + j] -= coeff * divisor[j]

    # 去除尾部零
    while len(quotient) > 1 and abs(quotient[-1]) < 1e-12:
        quotient.pop()
    while len(dividend) > 1 and abs(dividend[-1]) < 1e-12:
        dividend.pop()

    return quotient, dividend


def poly_derivative(p: List[float]) -> List[float]:
    """多项式求导。"""
    if len(p) <= 1:
        return [0.0]
    return [i * p[i] for i in range(1, len(p))]


def poly_integral(p: List[float], c: float = 0.0) -> List[float]:
    """多项式积分（不定积分）。"""
    return [c] + [p[i] / (i + 1) for i in range(len(p))]


# ============================================================
# 便捷导出
# ============================================================

__all__ = [
    # 数据类
    "Polynomial",
    # 方程求解
    "solve_linear",
    "solve_quadratic",
    "solve_system_linear",
    # 因式分解
    "factor_integer",
    "factor_polynomial_simple",
    # 代数化简
    "simplify_expression",
    "expand_expression",
    # 多项式运算
    "poly_add",
    "poly_mul",
    "poly_div",
    "poly_derivative",
    "poly_integral",
]


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Matha v4.2 — 代数运算标准库测试")
    print("=" * 50)

    # 线性方程
    print("\n【线性方程求解】")
    print(f"  2x - 4 = 0 → x = {solve_linear(2, -4)}")
    print(f"  0x + 5 = 0 → {'无解' if solve_linear(0, 5) is None else solve_linear(0, 5)}")

    # 二次方程
    print("\n【二次方程求解】")
    roots = solve_quadratic(1, -3, 2)
    print(f"  x² - 3x + 2 = 0 → x = {roots}")
    roots = solve_quadratic(1, 2, 5)
    print(f"  x² + 2x + 5 = 0 → x = {roots}")

    # 因式分解
    print("\n【整数因式分解】")
    print(f"  60 = {factor_integer(60)}")
    print(f"  100 = {factor_integer(100)}")
    print(f"  17 = {factor_integer(17)}")

    # 多项式运算
    print("\n【多项式运算】")
    p1 = Polynomial([1, 2, 1])  # 1 + 2x + x²
    p2 = Polynomial([1, -1])    # 1 - x
    print(f"  p1 = {p1}")
    print(f"  p2 = {p2}")
    print(f"  p1 + p2 = {p1 + p2}")
    print(f"  p1 × p2 = {p1 * p2}")
    print(f"  p1'(x) = {Polynomial(poly_derivative(p1.coefficients))}")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)
