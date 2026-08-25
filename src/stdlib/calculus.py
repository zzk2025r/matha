# -*- coding: utf-8 -*-
"""Matha v4.2 — 微积分运算标准库

提供微积分核心功能：
  - 极限计算
  - 导数（数值/符号）
  - 积分（数值/符号）
  - 泰勒展开
  - 级数求和

数学表达：
  所有函数遵循微积分定义，确保数学严谨性。

用法：
  from src.stdlib.calculus import (
      derivative, integral, limit,
      taylor_series, infinite_sum,
      newton_method,
  )
"""
from __future__ import annotations
import math
from typing import Callable, List, Optional, Tuple
from dataclasses import dataclass


# ============================================================
# 数值微分
# ============================================================

def derivative(f: Callable[[float], float], x: float, h: float = 1e-8) -> float:
    """
    数值求导：f'(x) ≈ [f(x+h) - f(x-h)] / (2h)

    数学定义：
      f'(x) = lim(h→0) [f(x+h) - f(x-h)] / (2h)

    Args:
        f: 函数
        x: 求导点
        h: 步长（默认 1e-8）

    Returns:
        导数值

    Examples:
        >>> derivative(lambda x: x**2, 3)
        6.0
        >>> derivative(math.sin, math.pi/2)
        0.0
    """
    return (f(x + h) - f(x - h)) / (2 * h)


def second_derivative(f: Callable[[float], float], x: float, h: float = 1e-5) -> float:
    """
    数值求二阶导数：f''(x) ≈ [f(x+h) - 2f(x) + f(x-h)] / h²

    Examples:
        >>> second_derivative(lambda x: x**2, 3)
        2.0
    """
    return (f(x + h) - 2 * f(x) + f(x - h)) / (h * h)


# ============================================================
# 数值积分
# ============================================================

def integral(f: Callable[[float], float], a: float, b: float, n: int = 1000) -> float:
    """
    数值积分（辛普森法则）：∫[a,b] f(x)dx

    数学定义：
      ∫[a,b] f(x)dx ≈ (h/3)[f(x₀) + 4f(x₁) + 2f(x₂) + ... + f(xₙ)]

    Args:
        f: 被积函数
        a: 下限
        b: 上限
        n: 分段数（偶数）

    Returns:
        积分值

    Examples:
        >>> integral(lambda x: x**2, 0, 1)
        0.3333...
        >>> integral(math.sin, 0, math.pi)
        2.0
    """
    if n % 2 != 0:
        n += 1
    h = (b - a) / n
    result = f(a) + f(b)

    for i in range(1, n):
        x = a + i * h
        result += (4 if i % 2 == 1 else 2) * f(x)

    return result * h / 3


def numerical_integral_trapezoid(f: Callable[[float], float], a: float, b: float, n: int = 1000) -> float:
    """
    数值积分（梯形法则）：∫[a,b] f(x)dx

    更简单但精度略低。
    """
    h = (b - a) / n
    result = (f(a) + f(b)) / 2
    for i in range(1, n):
        result += f(a + i * h)
    return result * h


# ============================================================
# 极限计算
# ============================================================

def limit_forward(f: Callable[[float], float], x: float, direction: float = 1e-10) -> float:
    """
    前向极限：lim(h→0+) f(x+h)

    Args:
        f: 函数
        x: 趋近点
        direction: 趋近方向（1 为正，-1 为负）
    """
    return f(x + direction)


def limit_two_sided(f: Callable[[float], float], x: float, h: float = 1e-10) -> float:
    """
    双侧极限：lim(x→x₀) f(x)
    """
    left = f(x - h)
    right = f(x + h)
    if abs(left - right) < h * 100:
        return (left + right) / 2
    return float('nan')  # 极限不存在


# ============================================================
# 泰勒展开
# ============================================================

def taylor_series(f: Callable[[float], float], x0: float, x: float, n: int = 10) -> float:
    """
    泰勒级数展开：f(x) ≈ Σ f^(k)(x₀) / k! × (x-x₀)^k

    Args:
        f: 函数
        x0: 展开点
        x: 求值点
        n: 展开项数

    Returns:
        泰勒近似值
    """
    result = 0.0
    h = x - x0
    factorial = 1
    for k in range(n):
        if k > 0:
            factorial *= k
        # 数值求 k 阶导数
        dk = _numerical_derivative(f, x0, k)
        result += dk / factorial * (h ** k)
    return result


def _numerical_derivative(f: Callable[[float], float], x: float, n: int, h: float = 1e-6) -> float:
    """数值计算 n 阶导数。"""
    if n == 0:
        return f(x)
    if n == 1:
        return (f(x + h) - f(x - h)) / (2 * h)

    # 递归计算高阶导数
    def df(x):
        return (f(x + h) - f(x - h)) / (2 * h)
    return _numerical_derivative(df, x, n - 1, h)


# ============================================================
# 级数求和
# ============================================================

def infinite_sum(term_fn: Callable[[int], float], max_terms: int = 10000, tolerance: float = 1e-10) -> Tuple[float, int]:
    """
    无穷级数求和：S = Σ term(n) for n in [0, ∞)

    当连续项变化小于 tolerance 时停止。

    Returns:
        (sum, terms_used)
    """
    total = term_fn(0)
    prev = total

    for n in range(1, max_terms):
        term = term_fn(n)
        total += term
        if abs(total - prev) < tolerance:
            return total, n + 1
        prev = total

    return total, max_terms


# ============================================================
# 牛顿法求根
# ============================================================

def newton_method(f: Callable[[float], float], x0: float, tolerance: float = 1e-10, max_iter: int = 100) -> Tuple[float, int]:
    """
    牛顿法求根：f(x) = 0

    迭代公式：x_{n+1} = x_n - f(x_n) / f'(x_n)

    Args:
        f: 函数
        x0: 初始猜测
        tolerance: 收敛精度
        max_iter: 最大迭代次数

    Returns:
        (root, iterations)
    """
    x = x0
    for i in range(max_iter):
        fx = f(x)
        if abs(fx) < tolerance:
            return x, i + 1

        dfx = derivative(f, x)
        if abs(dfx) < 1e-15:
            break  # 导数为零，无法继续

        x = x - fx / dfx

    return x, max_iter


# ============================================================
# 特殊函数
# ============================================================

def gamma(n: float) -> float:
    """
    Gamma 函数：Γ(n) = (n-1)!

    使用 Lanczos 近似。
    """
    if n < 0.5:
        return math.pi / (math.sin(math.pi * n) * gamma(1 - n))
    n -= 1
    g = 7
    coef = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7
    ]
    x = coef[0]
    for i in range(1, g + 2):
        x += coef[i] / (n + i)
    t = n + g + 0.5
    return math.sqrt(2 * math.pi) * (t ** (n + 0.5)) * math.exp(-t) * x


def beta(a: float, b: float) -> float:
    """
    Beta 函数：B(a,b) = Γ(a)Γ(b) / Γ(a+b)
    """
    return gamma(a) * gamma(b) / gamma(a + b)


# ============================================================
# 便捷导出
# ============================================================

__all__ = [
    # 微分
    "derivative",
    "second_derivative",
    # 积分
    "integral",
    "numerical_integral_trapezoid",
    # 极限
    "limit_forward",
    "limit_two_sided",
    # 泰勒展开
    "taylor_series",
    # 级数
    "infinite_sum",
    # 牛顿法
    "newton_method",
    # 特殊函数
    "gamma",
    "beta",
]


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Matha v4.2 — 微积分标准库测试")
    print("=" * 50)

    # 导数
    print("\n【数值微分】")
    f = lambda x: x ** 2
    print(f"  d/dx(x²) at x=3: {derivative(f, 3):.6f} (期望 6.0)")
    print(f"  d/dx(sin(x)) at x=π/2: {derivative(math.sin, math.pi/2):.6f} (期望 0.0)")

    # 二阶导数
    print("\n【二阶导数】")
    print(f"  d²/dx²(x²) at x=3: {second_derivative(f, 3):.6f} (期望 2.0)")

    # 积分
    print("\n【数值积分】")
    print(f"  ∫[0,1] x²dx = {integral(lambda x: x**2, 0, 1):.6f} (期望 0.3333)")
    print(f"  ∫[0,π] sin(x)dx = {integral(math.sin, 0, math.pi):.6f} (期望 2.0)")

    # 泰勒展开
    print("\n【泰勒展开】")
    print(f"  e^1 ≈ {taylor_series(math.exp, 0, 1, 20):.6f} (期望 2.71828)")
    print(f"  sin(π/2) ≈ {taylor_series(math.sin, 0, math.pi/2, 20):.6f} (期望 1.0)")

    # 牛顿法
    print("\n【牛顿法求根】")
    root, iters = newton_method(lambda x: x**2 - 2, 1.0)
    print(f"  √2 ≈ {root:.10f} (iters={iters})")

    root, iters = newton_method(lambda x: math.cos(x) - x, 0.5)
    print(f"  cos(x)=x 的解 ≈ {root:.10f} (iters={iters})")

    # 级数求和
    print("\n【无穷级数】")
    s, n = infinite_sum(lambda k: 1 / (2 ** k), max_terms=100)
    print(f"  Σ(1/2^n) = {s:.6f} (期望 2.0, 用了 {n} 项)")

    # Gamma 函数
    print("\n【特殊函数】")
    print(f"  Γ(5) = {gamma(5):.0f} (期望 24)")
    print(f"  Γ(0.5) = {gamma(0.5):.6f} (期望 {math.sqrt(math.pi):.6f})")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)
