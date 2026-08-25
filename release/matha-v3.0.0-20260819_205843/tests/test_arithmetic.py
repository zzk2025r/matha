# -*- coding: utf-8 -*-
"""算术运算标准库单元测试

提供算术运算模块的完整测试用例，使用 unittest 框架。

用法：
  python -m unittest tests.test_arithmetic -v
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stdlib.arithmetic import (
    # 常数
    PI, E, PHI, MathConstants,
    # 基本运算
    add, subtract, multiply, divide, power, sqrt, abs_value,
    # 取整运算
    floor, ceil, round_value, trunc,
    # 数论函数
    gcd, lcm, factorial, is_prime, prime_factors, sieve_of_eratosthenes,
    # 三角函数
    sin, cos, tan, asin, acos, atan, atan2,
    # 对数函数
    log, log2, log10,
    # 组合数学
    combination, permutation,
)


# ============================================================
# 基本运算测试
# ============================================================

class TestBasicOperations(unittest.TestCase):
    """基本运算测试。"""

    def test_add(self):
        """测试加法。"""
        self.assertEqual(add(3, 5), 8)
        self.assertEqual(add(-1, 1), 0)
        self.assertAlmostEqual(add(2.5, 3.7), 6.2)

    def test_subtract(self):
        """测试减法。"""
        self.assertEqual(subtract(10, 3), 7)
        self.assertEqual(subtract(5, 10), -5)
        self.assertAlmostEqual(subtract(2.5, 1.5), 1.0)

    def test_multiply(self):
        """测试乘法。"""
        self.assertEqual(multiply(4, 5), 20)
        self.assertEqual(multiply(-2, 3), -6)
        self.assertAlmostEqual(multiply(2.5, 4), 10.0)

    def test_divide(self):
        """测试除法。"""
        self.assertAlmostEqual(divide(10, 3), 3.3333, places=3)
        self.assertIsNone(divide(10, 0))
        self.assertEqual(divide(0, 5), 0)

    def test_power(self):
        """测试幂运算。"""
        self.assertEqual(power(2, 3), 8)
        self.assertAlmostEqual(power(9, 0.5), 3.0)
        self.assertAlmostEqual(power(2, -1), 0.5)

    def test_sqrt(self):
        """测试平方根。"""
        self.assertAlmostEqual(sqrt(16), 4.0)
        self.assertEqual(sqrt(0), 0)
        self.assertIsNone(sqrt(-1))
        self.assertAlmostEqual(sqrt(2), 1.41421356, places=6)

    def test_abs_value(self):
        """测试绝对值。"""
        self.assertEqual(abs_value(-5), 5)
        self.assertEqual(abs_value(3), 3)
        self.assertEqual(abs_value(0), 0)


# ============================================================
# 取整运算测试
# ============================================================

class TestRoundingOperations(unittest.TestCase):
    """取整运算测试。"""

    def test_floor(self):
        """测试向下取整。"""
        self.assertEqual(floor(3.7), 3)
        self.assertEqual(floor(-2.3), -3)
        self.assertEqual(floor(5.0), 5)

    def test_ceil(self):
        """测试向上取整。"""
        self.assertEqual(ceil(3.2), 4)
        self.assertEqual(ceil(-2.7), -2)
        self.assertEqual(ceil(5.0), 5)

    def test_round(self):
        """测试四舍五入。"""
        self.assertEqual(round_value(3.5), 4)
        self.assertEqual(round_value(3.4), 3)
        self.assertAlmostEqual(round_value(3.14159, 2), 3.14)

    def test_trunc(self):
        """测试截断取整。"""
        self.assertEqual(trunc(3.7), 3)
        self.assertEqual(trunc(-2.3), -2)
        self.assertEqual(trunc(5.0), 5)


# ============================================================
# 数论函数测试
# ============================================================

class TestNumberTheory(unittest.TestCase):
    """数论函数测试。"""

    def test_gcd(self):
        """测试最大公约数。"""
        self.assertEqual(gcd(12, 18), 6)
        self.assertEqual(gcd(7, 13), 1)
        self.assertEqual(gcd(0, 5), 5)
        self.assertEqual(gcd(-6, 9), 3)

    def test_lcm(self):
        """测试最小公倍数。"""
        self.assertEqual(lcm(4, 6), 12)
        self.assertEqual(lcm(3, 5), 15)
        self.assertEqual(lcm(0, 5), 0)

    def test_factorial(self):
        """测试阶乘。"""
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        """测试负数阶乘抛出异常。"""
        with self.assertRaises(ValueError):
            factorial(-1)

    def test_is_prime(self):
        """测试素数判断。"""
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(7))
        self.assertFalse(is_prime(10))
        self.assertFalse(is_prime(1))
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(-5))

    def test_prime_factors(self):
        """测试素因数分解。"""
        self.assertEqual(prime_factors(12), [2, 2, 3])
        self.assertEqual(prime_factors(60), [2, 2, 3, 5])
        self.assertEqual(prime_factors(7), [7])
        self.assertEqual(prime_factors(1), [])

    def test_sieve_of_eratosthenes(self):
        """测试埃拉托斯特尼筛法。"""
        self.assertEqual(sieve_of_eratosthenes(20), [2, 3, 5, 7, 11, 13, 17, 19])
        self.assertEqual(sieve_of_eratosthenes(10), [2, 3, 5, 7])
        self.assertEqual(sieve_of_eratosthenes(1), [])
        self.assertEqual(sieve_of_eratosthenes(0), [])


# ============================================================
# 三角函数测试
# ============================================================

class TestTrigonometry(unittest.TestCase):
    """三角函数测试。"""

    def test_sin(self):
        """测试正弦函数。"""
        self.assertAlmostEqual(sin(0), 0.0)
        self.assertAlmostEqual(sin(PI / 2), 1.0)
        self.assertAlmostEqual(sin(PI), 0.0, places=10)

    def test_cos(self):
        """测试余弦函数。"""
        self.assertAlmostEqual(cos(0), 1.0)
        self.assertAlmostEqual(cos(PI / 2), 0.0, places=10)
        self.assertAlmostEqual(cos(PI), -1.0)

    def test_tan(self):
        """测试正切函数。"""
        self.assertAlmostEqual(tan(0), 0.0)
        self.assertAlmostEqual(tan(PI / 4), 1.0)

    def test_asin(self):
        """测试反正弦函数。"""
        self.assertAlmostEqual(asin(0), 0.0)
        self.assertAlmostEqual(asin(1), PI / 2)
        self.assertIsNone(asin(2))

    def test_acos(self):
        """测试反余弦函数。"""
        self.assertAlmostEqual(acos(1), 0.0)
        self.assertAlmostEqual(acos(0), PI / 2)
        self.assertIsNone(acos(2))

    def test_atan(self):
        """测试反正切函数。"""
        self.assertAlmostEqual(atan(0), 0.0)
        self.assertAlmostEqual(atan(1), PI / 4)

    def test_atan2(self):
        """测试二参数反正切。"""
        self.assertAlmostEqual(atan2(1, 1), PI / 4)
        self.assertAlmostEqual(atan2(0, 1), 0.0)


# ============================================================
# 对数函数测试
# ============================================================

class TestLogarithms(unittest.TestCase):
    """对数函数测试。"""

    def test_log(self):
        """测试对数函数。"""
        self.assertAlmostEqual(log(1), 0.0)
        self.assertAlmostEqual(log(E), 1.0)
        self.assertAlmostEqual(log(100, 10), 2.0)
        self.assertIsNone(log(0))
        self.assertIsNone(log(-1))

    def test_log2(self):
        """测试以 2 为底的对数。"""
        self.assertAlmostEqual(log2(1), 0.0)
        self.assertAlmostEqual(log2(8), 3.0)
        self.assertIsNone(log2(0))

    def test_log10(self):
        """测试以 10 为底的对数。"""
        self.assertAlmostEqual(log10(1), 0.0)
        self.assertAlmostEqual(log10(100), 2.0)
        self.assertIsNone(log10(0))


# ============================================================
# 组合数学测试
# ============================================================

class TestCombinatorics(unittest.TestCase):
    """组合数学测试。"""

    def test_combination(self):
        """测试组合数。"""
        self.assertEqual(combination(5, 2), 10)
        self.assertEqual(combination(5, 5), 1)
        self.assertEqual(combination(5, 0), 1)
        self.assertIsNone(combination(5, 6))

    def test_permutation(self):
        """测试排列数。"""
        self.assertEqual(permutation(5, 2), 20)
        self.assertEqual(permutation(5, 5), 120)
        self.assertEqual(permutation(5, 0), 1)
        self.assertIsNone(permutation(5, 6))


# ============================================================
# 数学常数测试
# ============================================================

class TestMathConstants(unittest.TestCase):
    """数学常数测试。"""

    def test_pi(self):
        """测试 π 值。"""
        self.assertAlmostEqual(PI, 3.141592653589793)

    def test_e(self):
        """测试 e 值。"""
        self.assertAlmostEqual(E, 2.718281828459045)

    def test_phi(self):
        """测试黄金比例。"""
        self.assertAlmostEqual(PHI, 1.618033988749895)

    def test_list_all(self):
        """测试列出所有常数。"""
        constants = MathConstants.list_all()
        self.assertIn("PI", constants)
        self.assertIn("E", constants)
        self.assertIn("PHI", constants)
        self.assertGreater(len(constants), 5)


# ============================================================
# 性能测试
# ============================================================

class TestPerformance(unittest.TestCase):
    """性能测试。"""

    def test_factorial_performance(self):
        """测试阶乘性能。"""
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            factorial(20)
        elapsed = (time.perf_counter() - start) * 1000
        avg = elapsed / iterations
        print(f"\n  阶乘性能: {avg:.3f}ms/次 ({iterations} 次)")
        self.assertLess(avg, 1.0, f"阶乘性能 {avg:.3f}ms 超标")

    def test_prime_sieve_performance(self):
        """测试筛法性能。"""
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            sieve_of_eratosthenes(10000)
        elapsed = (time.perf_counter() - start) * 1000
        avg = elapsed / iterations
        print(f"\n  筛法性能: {avg:.2f}ms/次 ({iterations} 次)")
        self.assertLess(avg, 10.0, f"筛法性能 {avg:.2f}ms 超标")


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="算术运算标准库测试")
    parser.add_argument("--benchmark", action="store_true", help="运行性能测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    print("=" * 60)
    print("  Matha v4.2 — 算术运算标准库测试")
    print("=" * 60)

    unittest.main(verbosity=2 if args.verbose else 1)
