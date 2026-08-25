# -*- coding: utf-8 -*-
"""Matha v4.2 — 算术运算标准库

提供数学计算核心功能：
  - 基本运算：加减乘除、幂、开方
  - 取整运算：向上/向下取整、四舍五入
  - 数学常数：π, e, φ 等
  - 高级函数：最大公约数、最小公倍数、阶乘、素数判断

数学表达：
  所有函数都遵循集合论定义，确保数学严谨性。

用法：
  from src.stdlib.arithmetic import (
      add, subtract, multiply, divide,
      power, sqrt, abs, round, floor, ceil,
      gcd, lcm, factorial, is_prime,
      PI, E, PHI,
  )
"""
from __future__ import annotations
import math
from typing import List, Optional, Union
from dataclasses import dataclass


# ============================================================
# 数学常数
# ============================================================

class MathConstants:
    """数学常数集合。"""

    # 基本常数
    PI: float = math.pi           # π ≈ 3.14159...
    E: float = math.e             # e ≈ 2.71828...
    PHI: float = (1 + math.sqrt(5)) / 2  # 黄金比例 φ ≈ 1.61803...
    SQRT2: float = math.sqrt(2)   # √2 ≈ 1.41421...
    SQRT3: float = math.sqrt(3)   # √3 ≈ 1.73205...
    LN2: float = math.log(2)      # ln(2) ≈ 0.69315...
    LN10: float = math.log(10)    # ln(10) ≈ 2.30259...

    # 角度常数
    DEG_TO_RAD: float = math.pi / 180   # 度转弧度
    RAD_TO_DEG: float = 180 / math.pi   # 弧度转度

    @classmethod
    def list_all(cls) -> dict:
        """列出所有常数。"""
        return {
            name: getattr(cls, name)
            for name in dir(cls)
            if not name.startswith("_")
        }


# 便捷导入
PI = MathConstants.PI
E = MathConstants.E
PHI = MathConstants.PHI


# ============================================================
# 基本运算
# ============================================================

def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    加法运算：a + b

    数学定义：
      add: ℝ × ℝ → ℝ
      add(a, b) = a + b

    Args:
        a: 被加数
        b: 加数

    Returns:
        和

    Examples:
        >>> add(3, 5)
        8
        >>> add(2.5, 3.7)
        6.2
    """
    return a + b


def subtract(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    减法运算：a - b

    数学定义：
      subtract: ℝ × ℝ → ℝ
      subtract(a, b) = a - b

    Args:
        a: 被减数
        b: 减数

    Returns:
        差

    Examples:
        >>> subtract(10, 3)
        7
    """
    return a - b


def multiply(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    乘法运算：a × b

    数学定义：
      multiply: ℝ × ℝ → ℝ
      multiply(a, b) = a × b

    Args:
        a: 乘数
        b: 被乘数

    Returns:
        积

    Examples:
        >>> multiply(3, 5)
        15
    """
    return a * b


def divide(a: Union[int, float], b: Union[int, float]) -> Optional[float]:
    """
    除法运算：a ÷ b

    数学定义：
      divide: ℝ × (ℝ \\ {0}) → ℝ
      divide(a, b) = a / b

    Args:
        a: 被除数
        b: 除数（不能为 0）

    Returns:
        商，除数为 0 时返回 None

    Examples:
        >>> divide(10, 3)
        3.333...
        >>> divide(10, 0)
        None
    """
    if b == 0:
        return None
    return a / b


def power(base: Union[int, float], exp: Union[int, float]) -> Union[int, float]:
    """
    幂运算：base^exp

    数学定义：
      power: ℝ × ℤ → ℝ
      power(base, exp) = base^exp

    Args:
        base: 底数
        exp: 指数

    Returns:
        幂

    Examples:
        >>> power(2, 3)
        8
        >>> power(9, 0.5)
        3.0
    """
    return base ** exp


def sqrt(x: Union[int, float]) -> Optional[float]:
    """
    平方根运算：√x

    数学定义：
      sqrt: ℝ⁺ → ℝ
      sqrt(x) = x^(1/2)

    Args:
        x: 被开方数（必须 ≥ 0）

    Returns:
        平方根，x < 0 时返回 None

    Examples:
        >>> sqrt(16)
        4.0
        >>> sqrt(-1)
        None
    """
    if x < 0:
        return None
    return math.sqrt(x)


def abs_value(x: Union[int, float]) -> Union[int, float]:
    """
    绝对值运算：|x|

    数学定义：
      abs: ℝ → ℝ⁺
      abs(x) = |x|

    Args:
        x: 输入值

    Returns:
        绝对值

    Examples:
        >>> abs_value(-5)
        5
        >>> abs_value(3)
        3
    """
    return abs(x)


# ============================================================
# 取整运算
# ============================================================

def floor(x: Union[int, float]) -> int:
    """
    向下取整：⌊x⌋

    数学定义：
      floor: ℝ → ℤ
      floor(x) = max{n ∈ ℤ | n ≤ x}

    Args:
        x: 输入值

    Returns:
        向下取整结果

    Examples:
        >>> floor(3.7)
        3
        >>> floor(-2.3)
        -3
    """
    return math.floor(x)


def ceil(x: Union[int, float]) -> int:
    """
    向上取整：⌈x⌉

    数学定义：
      ceil: ℝ → ℤ
      ceil(x) = min{n ∈ ℤ | n ≥ x}

    Args:
        x: 输入值

    Returns:
        向上取整结果

    Examples:
        >>> ceil(3.2)
        4
        >>> ceil(-2.7)
        -2
    """
    return math.ceil(x)


def round_value(x: Union[int, float], ndigits: int = 0) -> Union[int, float]:
    """
    四舍五入：round(x, ndigits)

    数学定义：
      round: ℝ × ℕ → ℝ
      round(x, n) = ⌊x × 10^n + 0.5⌋ / 10^n

    Args:
        x: 输入值
        ndigits: 小数位数（默认 0）

    Returns:
        四舍五入结果

    Examples:
        >>> round_value(3.7)
        4
        >>> round_value(3.14159, 2)
        3.14
    """
    return round(x, ndigits)


def trunc(x: Union[int, float]) -> Union[int, float]:
    """
    截断取整：向零取整

    数学定义：
      trunc: ℝ → ℤ
      trunc(x) = sign(x) × ⌊|x|⌋

    Args:
        x: 输入值

    Returns:
        截断结果

    Examples:
        >>> trunc(3.7)
        3
        >>> trunc(-2.3)
        -2
    """
    return math.trunc(x)


# ============================================================
# 数论函数
# ============================================================

def gcd(a: int, b: int) -> int:
    """
    最大公约数：gcd(a, b)

    数学定义：
      gcd: ℤ × ℤ → ℕ
      gcd(a, b) = max{n ∈ ℕ | n|a ∧ n|b}

    Args:
        a: 第一个整数
        b: 第二个整数

    Returns:
        最大公约数

    Examples:
        >>> gcd(12, 18)
        6
        >>> gcd(7, 13)
        1
    """
    return math.gcd(abs(a), abs(b))


def lcm(a: int, b: int) -> int:
    """
    最小公倍数：lcm(a, b)

    数学定义：
      lcm: ℤ × ℤ → ℕ
      lcm(a, b) = min{n ∈ ℕ | a|n ∧ b|n}

    Args:
        a: 第一个整数
        b: 第二个整数

    Returns:
        最小公倍数

    Examples:
        >>> lcm(4, 6)
        12
        >>> lcm(3, 5)
        15
    """
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // gcd(a, b)


def factorial(n: int) -> int:
    """
    阶乘：n!

    数学定义：
      factorial: ℕ → ℕ
      factorial(n) = n! = ∏_{i=1}^{n} i
      factorial(0) = 1

    Args:
        n: 非负整数

    Returns:
        n 的阶乘

    Examples:
        >>> factorial(5)
        120
        >>> factorial(0)
        1
    """
    if n < 0:
        raise ValueError(f"阶乘未定义负数: {n}")
    return math.factorial(n)


def is_prime(n: int) -> bool:
    """
    素数判断：is_prime(n)

    数学定义：
      is_prime: ℕ → {True, False}
      is_prime(n) = True ⟺ n > 1 ∧ ∀d∈ℕ, d|n → d=1 ∨ d=n

    Args:
        n: 待判断的整数

    Returns:
        是否为素数

    Examples:
        >>> is_prime(7)
        True
        >>> is_prime(10)
        False
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, math.isqrt(n) + 1, 2):
        if n % i == 0:
            return False
    return True


def prime_factors(n: int) -> List[int]:
    """
    素因数分解：n = p1^a1 × p2^a2 × ... × pk^ak

    数学定义：
      prime_factors: ℕ → ℤ*
      prime_factors(n) = [p1, p2, ..., pk] 其中 pi 是 n 的素因数

    Args:
        n: 待分解的正整数

    Returns:
        素因数列表（含重复）

    Examples:
        >>> prime_factors(12)
        [2, 2, 3]
        >>> prime_factors(60)
        [2, 2, 3, 5]
    """
    if n < 2:
        return []

    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def sieve_of_eratosthenes(limit: int) -> List[int]:
    """
    埃拉托斯特尼筛法：找出 2 到 limit 之间的所有素数

    数学定义：
      sieve: ℕ → ℤ*
      sieve(n) = {p ∈ ℤ | 2 ≤ p ≤ n ∧ is_prime(p)}

    Args:
        limit: 上界

    Returns:
        素数列表

    Examples:
        >>> sieve_of_eratosthenes(20)
        [2, 3, 5, 7, 11, 13, 17, 19]
    """
    if limit < 2:
        return []

    is_prime_arr = [True] * (limit + 1)
    is_prime_arr[0] = is_prime_arr[1] = False

    for p in range(2, math.isqrt(limit) + 1):
        if is_prime_arr[p]:
            for multiple in range(p * p, limit + 1, p):
                is_prime_arr[multiple] = False

    return [i for i, prime in enumerate(is_prime_arr) if prime]


# ============================================================
# 三角函数
# ============================================================

def sin(rad: float) -> float:
    """正弦函数：sin(x)"""
    return math.sin(rad)


def cos(rad: float) -> float:
    """余弦函数：cos(x)"""
    return math.cos(rad)


def tan(rad: float) -> float:
    """正切函数：tan(x)"""
    return math.tan(rad)


def asin(x: float) -> Optional[float]:
    """反正弦函数：arcsin(x)，x ∈ [-1, 1]"""
    if -1 <= x <= 1:
        return math.asin(x)
    return None


def acos(x: float) -> Optional[float]:
    """反余弦函数：arccos(x)，x ∈ [-1, 1]"""
    if -1 <= x <= 1:
        return math.acos(x)
    return None


def atan(x: float) -> float:
    """反正切函数：arctan(x)"""
    return math.atan(x)


def atan2(y: float, x: float) -> float:
    """二参数反正切：arctan(y/x)"""
    return math.atan2(y, x)


# ============================================================
# 对数函数
# ============================================================

def log(x: float, base: float = math.e) -> Optional[float]:
    """对数函数：log_base(x)"""
    if x > 0 and base > 0 and base != 1:
        return math.log(x) / math.log(base)
    return None


def log2(x: float) -> Optional[float]:
    """以 2 为底的对数：log2(x)"""
    if x > 0:
        return math.log2(x)
    return None


def log10(x: float) -> Optional[float]:
    """以 10 为底的对数：log10(x)"""
    if x > 0:
        return math.log10(x)
    return None


# ============================================================
# 组合数学
# ============================================================

def combination(n: int, k: int) -> Optional[int]:
    """
    组合数：C(n, k) = n! / (k! × (n-k)!)

    数学定义：
      C: ℕ × ℕ → ℕ
      C(n, k) = n! / (k! × (n-k)!)

    Args:
        n: 总数
        k: 选取数

    Returns:
        组合数，k > n 时返回 None
    """
    if k < 0 or k > n:
        return None
    return math.comb(n, k)


def permutation(n: int, k: int) -> Optional[int]:
    """
    排列数：P(n, k) = n! / (n-k)!

    数学定义：
      P: ℕ × ℕ → ℕ
      P(n, k) = n! / (n-k)!

    Args:
        n: 总数
        k: 选取数

    Returns:
        排列数，k > n 时返回 None
    """
    if k < 0 or k > n:
        return None
    return math.perm(n, k)


# ============================================================
# 便捷导出
# ============================================================

__all__ = [
    # 常数
    "PI", "E", "PHI", "MathConstants",
    # 基本运算
    "add", "subtract", "multiply", "divide", "power", "sqrt", "abs_value",
    # 取整运算
    "floor", "ceil", "round_value", "trunc",
    # 数论函数
    "gcd", "lcm", "factorial", "is_prime", "prime_factors", "sieve_of_eratosthenes",
    # 三角函数
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    # 对数函数
    "log", "log2", "log10",
    # 组合数学
    "combination", "permutation",
]


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Matha v4.2 — 算术运算标准库测试")
    print("=" * 50)

    # 基本运算
    print("\n【基本运算】")
    print(f"  add(3, 5) = {add(3, 5)}")
    print(f"  subtract(10, 3) = {subtract(10, 3)}")
    print(f"  multiply(4, 5) = {multiply(4, 5)}")
    print(f"  divide(10, 3) = {divide(10, 3):.4f}")
    print(f"  power(2, 10) = {power(2, 10)}")
    print(f"  sqrt(16) = {sqrt(16)}")

    # 取整运算
    print("\n【取整运算】")
    print(f"  floor(3.7) = {floor(3.7)}")
    print(f"  ceil(3.2) = {ceil(3.2)}")
    print(f"  round(3.5) = {round_value(3.5)}")
    print(f"  trunc(3.7) = {trunc(3.7)}")

    # 数论函数
    print("\n【数论函数】")
    print(f"  gcd(12, 18) = {gcd(12, 18)}")
    print(f"  lcm(4, 6) = {lcm(4, 6)}")
    print(f"  factorial(5) = {factorial(5)}")
    print(f"  is_prime(7) = {is_prime(7)}")
    print(f"  prime_factors(60) = {prime_factors(60)}")
    print(f"  sieve(20) = {sieve_of_eratosthenes(20)}")

    # 三角函数
    print("\n【三角函数】")
    print(f"  sin(π/2) = {sin(PI/2):.4f}")
    print(f"  cos(0) = {cos(0):.4f}")
    print(f"  tan(π/4) = {tan(PI/4):.4f}")

    # 数学常数
    print("\n【数学常数】")
    for name, value in MathConstants.list_all().items():
        print(f"  {name} = {value}")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)
