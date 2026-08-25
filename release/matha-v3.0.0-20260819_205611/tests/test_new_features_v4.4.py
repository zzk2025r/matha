# Matha v4.4 新功能测试

> 测试文件：tests/test_new_features_v4.4.py
> 生成时间：2025-07-26

```python
# -*- coding: utf-8 -*-
"""Matha v4.4 新功能测试

测试新增功能：
  1. 符号微积分（SymPy 集成）
  2. 矩阵运算标准库
  3. 概率统计模块

用法：
  python -m unittest tests.test_new_features_v4.4 -v
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSymbolicCalculus(unittest.TestCase):
    """符号微积分测试。"""

    def test_symbolic_derivative(self):
        """测试符号求导。"""
        from src.stdlib.calculus_symbolic import symbolic_derivative

        # 多项式求导
        self.assertEqual(symbolic_derivative("x**2"), "2*x")
        self.assertEqual(symbolic_derivative("x**3 + 2*x + 1"), "3*x**2 + 2")

        # 三角函数求导
        self.assertEqual(symbolic_derivative("sin(x)"), "cos(x)")
        self.assertEqual(symbolic_derivative("cos(x)"), "-sin(x)")

        # 指数函数求导
        self.assertEqual(symbolic_derivative("exp(x)"), "exp(x)")

    def test_symbolic_integral(self):
        """测试符号积分。"""
        from src.stdlib.calculus_symbolic import symbolic_integral

        # 多项式积分
        self.assertEqual(symbolic_integral("x**2"), "x**3/3")
        self.assertEqual(symbolic_integral("x"), "x**2/2")

        # 三角函数积分
        self.assertEqual(symbolic_integral("sin(x)"), "-cos(x)")
        self.assertEqual(symbolic_integral("cos(x)"), "sin(x)")

    def test_definite_integral(self):
        """测试定积分。"""
        from src.stdlib.calculus_symbolic import definite_integral
        import math

        # ∫[0,1] x²dx = 1/3
        result = definite_integral("x**2", "x", 0, 1)
        self.assertAlmostEqual(result, 1/3, places=5)

        # ∫[0,π] sin(x)dx = 2
        result = definite_integral("sin(x)", "x", 0, math.pi)
        self.assertAlmostEqual(result, 2.0, places=5)

    def test_taylor_series(self):
        """测试泰勒展开。"""
        from src.stdlib.calculus_symbolic import taylor_series

        # e^x 的泰勒展开
        result = taylor_series("exp(x)", "x", 0, 3)
        self.assertIn("x**3", result)
        self.assertIn("x**2", result)
        self.assertIn("x", result)

        # sin(x) 的泰勒展开
        result = taylor_series("sin(x)", "x", 0, 5)
        self.assertIn("x**5", result)
        self.assertIn("x**3", result)
        self.assertIn("x", result)

    def test_limit(self):
        """测试极限计算。"""
        from src.stdlib.calculus_symbolic import limit

        # lim(x→0) sin(x)/x = 1
        result = limit("sin(x)/x", "x", 0)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_skip_if_no_sympy(self):
        """测试 SymPy 未安装时的行为。"""
        from src.stdlib import calculus_symbolic
        if not calculus_symbolic.HAS_SYMPY:
            with self.assertRaises(ImportError):
                calculus_symbolic.symbolic_derivative("x**2")


class TestLinearAlgebra(unittest.TestCase):
    """矩阵运算测试。"""

    def test_matrix_creation(self):
        """测试矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        # 零矩阵
        zeros = Matrix.zeros(3, 3)
        self.assertEqual(zeros.shape, (3, 3))
        self.assertTrue(all(v == 0.0 for row in zeros.data for v in row))

        # 单位矩阵
        identity = Matrix.identity(3)
        self.assertEqual(identity.shape, (3, 3))
        for i in range(3):
            for j in range(3):
                if i == j:
                    self.assertEqual(identity.data[i][j], 1.0)
                else:
                    self.assertEqual(identity.data[i][j], 0.0)

    def test_matrix_operations(self):
        """测试矩阵运算。"""
        from src.stdlib.linear_algebra import Matrix, matrix_transpose

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])

        # 加法
        C = A + B
        self.assertEqual(C.data, [[6, 8], [10, 12]])

        # 乘法
        C = A * B
        self.assertEqual(C.data, [[19, 22], [43, 50]])

        # 转置
        T = matrix_transpose(A)
        self.assertEqual(T.data, [[1, 3], [2, 4]])

    def test_matrix_properties(self):
        """测试矩阵性质。"""
        from src.stdlib.linear_algebra import (
            Matrix, matrix_determinant, matrix_trace, matrix_rank
        )

        A = Matrix([[1, 2], [3, 4]])

        # 行列式
        self.assertEqual(matrix_determinant(A), -2.0)

        # 迹
        self.assertEqual(matrix_trace(A), 5.0)

        # 秩
        self.assertEqual(matrix_rank(A), 2)

    def test_matrix_inverse(self):
        """测试逆矩阵。"""
        from src.stdlib.linear_algebra import Matrix, matrix_inverse

        A = Matrix([[1, 2], [3, 4]])
        inv_A = matrix_inverse(A)

        # 验证 A × A^(-1) = I
        I = A * inv_A
        self.assertAlmostEqual(I.data[0][0], 1.0, places=5)
        self.assertAlmostEqual(I.data[0][1], 0.0, places=5)
        self.assertAlmostEqual(I.data[1][0], 0.0, places=5)
        self.assertAlmostEqual(I.data[1][1], 1.0, places=5)

    def test_eigenvalues(self):
        """测试特征值。"""
        from src.stdlib.linear_algebra import Matrix, matrix_eigenvalues

        # 2x2 矩阵的精确特征值
        A = Matrix([[2, 1], [1, 2]])
        eigenvalues = matrix_eigenvalues(A)

        # 特征值应为 3 和 1
        eigenvalues.sort()
        self.assertAlmostEqual(eigenvalues[0], 1.0, places=5)
        self.assertAlmostEqual(eigenvalues[1], 3.0, places=5)

    def test_solve_linear_system(self):
        """测试线性方程组求解。"""
        from src.stdlib.linear_algebra import Matrix, solve_linear_system

        # 求解 x + y = 3, 2x - y = 0
        A = Matrix([[1, 1], [2, -1]])
        b = [3, 0]
        solution = solve_linear_system(A, b)

        self.assertAlmostEqual(solution[0], 1.0, places=5)
        self.assertAlmostEqual(solution[1], 2.0, places=5)


class TestProbabilityStats(unittest.TestCase):
    """概率统计测试。"""

    def test_normal_distribution(self):
        """测试正态分布。"""
        from src.stdlib.probability_stats import NormalDistribution

        dist = NormalDistribution(mu=0, sigma=1)

        # 概率密度
        pdf = dist.pdf(0)
        self.assertAlmostEqual(pdf, 0.3989, places=4)

        # 累积分布
        cdf = dist.cdf(0)
        self.assertAlmostEqual(cdf, 0.5, places=4)

        # 分位数
        ppf = dist.ppf(0.975)
        self.assertAlmostEqual(ppf, 1.96, places=2)

    def test_binomial_distribution(self):
        """测试二项分布。"""
        from src.stdlib.probability_stats import BinomialDistribution

        binom = BinomialDistribution(n=10, p=0.5)

        # P(X=5)
        pmf = binom.pmf(5)
        self.assertAlmostEqual(pmf, 0.2461, places=4)

        # P(X≤5)
        cdf = binom.cdf(5)
        self.assertAlmostEqual(cdf, 0.6230, places=4)

    def test_statistics(self):
        """测试统计量。"""
        from src.stdlib.probability_stats import mean, variance, std, correlation

        data = [1, 2, 3, 4, 5]

        # 均值
        self.assertEqual(mean(data), 3.0)

        # 方差
        self.assertAlmostEqual(variance(data), 2.5, places=5)

        # 标准差
        self.assertAlmostEqual(std(data), 1.5811, places=4)

        # 相关系数
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        self.assertAlmostEqual(correlation(x, y), 1.0, places=5)

    def test_z_test(self):
        """测试 Z 检验。"""
        from src.stdlib.probability_stats import z_test

        sample = [98, 102, 100, 99, 101]
        z_stat, z_p = z_test(sample, population_mean=100, population_std=3)

        # Z 统计量应在合理范围内
        self.assertLessEqual(abs(z_stat), 2.0)
        # p 值应在 (0, 1) 范围内
        self.assertLess(z_p, 1.0)
        self.assertGreater(z_p, 0.0)

    def test_t_test(self):
        """测试 t 检验。"""
        from src.stdlib.probability_stats import t_test

        sample = [98, 102, 100, 99, 101]
        t_stat, t_p = t_test(sample, population_mean=100)

        # t 统计量应在合理范围内
        self.assertLessEqual(abs(t_stat), 2.0)
        # p 值应在 (0, 1) 范围内
        self.assertLess(t_p, 1.0)
        self.assertGreater(t_p, 0.0)

    def test_linear_regression(self):
        """测试线性回归。"""
        from src.stdlib.probability_stats import linear_regression

        x = [1, 2, 3, 4, 5]
        y = [2.1, 3.9, 6.2, 8.1, 9.8]

        result = linear_regression(x, y)

        # 斜率应接近 2
        self.assertAlmostEqual(result.coefficients[1], 2.0, places=1)

        # 截距应接近 0
        self.assertAlmostEqual(result.coefficients[0], 0.0, places=1)

        # R² 应接近 1（强线性关系）
        self.assertGreater(result.r_squared, 0.99)

    def test_polynomial_regression(self):
        """测试多项式回归。"""
        from src.stdlib.probability_stats import polynomial_regression

        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]  # y = x²

        result = polynomial_regression(x, y, degree=2)

        # 二次项系数应接近 1
        self.assertAlmostEqual(result.coefficients[2], 1.0, places=1)

        # 一次项和常数项应接近 0
        self.assertAlmostEqual(result.coefficients[1], 0.0, places=1)
        self.assertAlmostEqual(result.coefficients[0], 0.0, places=1)


if __name__ == "__main__":
    unittest.main()
```
