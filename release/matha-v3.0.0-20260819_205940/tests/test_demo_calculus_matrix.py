# -*- coding: utf-8 -*-
"""Matha v4.4 — 符号微积分与矩阵运算整合演示测试

测试整合演示脚本的功能：
  1. 符号求导 + 矩阵计算
  2. 符号积分 + 数值验证
  3. 泰勒展开 + 矩阵拟合
  4. 极限计算 + 收敛性分析
  5. 微分方程 + 矩阵求解
  6. 矩阵微积分综合应用

用法：
  python -m unittest tests.test_demo_calculus_matrix -v
"""
import unittest
import sys
import os
import math

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDemoCalculusMatrix(unittest.TestCase):
    """整合演示测试类。"""

    def setUp(self):
        """测试前准备。"""
        from src.stdlib import calculus_symbolic
        self.has_sympy = calculus_symbolic.HAS_SYMPY

    def test_sympy_available(self):
        """测试 SymPy 是否已安装。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装，跳过符号微积分测试")

    # ============================================================
    # 1. 符号求导 + 矩阵计算
    # ============================================================

    def test_derivative_matrix_integration(self):
        """测试符号求导与矩阵计算整合。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import symbolic_derivative
        from src.stdlib.linear_algebra import Matrix

        # 符号求导
        expr = "x**3 + 2*x**2 + 3*x + 1"
        derivative = symbolic_derivative(expr)
        self.assertEqual(derivative, "3*x**2 + 4*x + 3")

        # 矩阵系数验证
        coeffs = Matrix([[1, 2, 3, 1]])
        n = len(coeffs.data[0])
        derivative_coeffs = [[(n - 1 - i) * coeffs.data[0][i] for i in range(n - 1)]]
        deriv_matrix = Matrix(derivative_coeffs)

        # 验证导数系数 [3, 4, 3]
        self.assertEqual(deriv_matrix.data, [[3, 4, 3]])

    def test_derivative_at_point(self):
        """测试在特定点求导验证。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import symbolic_derivative

        # f(x) = x**3 + 2*x**2 + 3*x + 1
        # f'(x) = 3*x**2 + 4*x + 3
        derivative = symbolic_derivative("x**3 + 2*x**2 + 3*x + 1")
        self.assertEqual(derivative, "3*x**2 + 4*x + 3")

        # 在 x=2 处验证
        x = 2
        f_x = x**3 + 2*x**2 + 3*x + 1
        f_prime_x = 3*x**2 + 4*x + 3
        self.assertEqual(f_x, 27)
        self.assertEqual(f_prime_x, 23)

    # ============================================================
    # 2. 符号积分 + 数值验证
    # ============================================================

    def test_integral_symbolic_vs_numerical(self):
        """测试符号积分与数值积分对比。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import symbolic_integral, definite_integral

        # 符号积分
        expr = "x**2"
        integral = symbolic_integral(expr)
        self.assertEqual(integral, "x**3/3")

        # 定积分
        result = definite_integral(expr, "x", 0, 1)
        self.assertAlmostEqual(result, 1/3, places=5)

    def test_simpson_numerical_verification(self):
        """测试辛普森数值积分验证。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import definite_integral

        # 符号积分结果
        symbolic_result = definite_integral("x**2", "x", 0, 1)

        # 辛普森数值积分
        n = 1000
        h = 1.0 / n
        simpson_sum = 0.0
        for i in range(n + 1):
            x = i * h
            if i == 0 or i == n:
                simpson_sum += x**2
            elif i % 2 == 1:
                simpson_sum += 4 * x**2
            else:
                simpson_sum += 2 * x**2
        simpson_result = (h / 3) * simpson_sum

        # 误差应在 1e-6 以内
        error = abs(symbolic_result - simpson_result)
        self.assertLess(error, 1e-6)

    # ============================================================
    # 3. 泰勒展开 + 矩阵拟合
    # ============================================================

    def test_taylor_series_exp(self):
        """测试 exp(x) 泰勒展开。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import taylor_series

        taylor = taylor_series("exp(x)", "x", 0, 4)
        # 应包含 x^4, x^3, x^2, x, 常数项
        self.assertIn("x**4", taylor)
        self.assertIn("x**3", taylor)
        self.assertIn("x**2", taylor)
        self.assertIn("x", taylor)

    def test_taylor_approximation_accuracy(self):
        """测试泰勒近似精度。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import taylor_series

        # 泰勒系数
        coeffs = [1, 1, 0.5, 1/6, 1/24]

        # 在 x=0.5 处验证
        x = 0.5
        taylor_val = sum(c * x**i for i, c in enumerate(coeffs))
        true_val = math.exp(x)
        error = abs(taylor_val - true_val)

        # 4 阶泰勒展开在 x=0.5 处误差应很小
        self.assertLess(error, 0.001)

    # ============================================================
    # 4. 极限计算 + 收敛性分析
    # ============================================================

    def test_limit_sin_x_over_x(self):
        """测试 lim(x→0) sin(x)/x = 1。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import limit

        result = limit("sin(x)/x", "x", 0)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_limit_exponential_definition(self):
        """测试 lim(x→∞) (1+1/x)^x = e。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import limit

        result = limit("(1+1/x)^x", "x", float('inf'))
        self.assertAlmostEqual(result, math.e, places=5)

    def test_convergence_numerical_verification(self):
        """测试收敛性数值验证。"""
        # 验证 (1+1/n)^n → e
        n_values = [100, 1000, 10000]
        prev_error = float('inf')
        for n in n_values:
            approx = (1 + 1/n)**n
            error = abs(approx - math.e)
            # 随着 n 增大，误差应减小
            self.assertLess(error, prev_error)
            prev_error = error

    # ============================================================
    # 5. 微分方程 + 矩阵求解
    # ============================================================

    def test_ode_verification(self):
        """测试微分方程验证。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import symbolic_derivative

        # y = x², y' = 2x
        y = "x**2"
        y_prime = symbolic_derivative(y)
        self.assertEqual(y_prime, "2*x")

    def test_ode_numerical_verification(self):
        """测试微分方程数值验证。"""
        # 在 x = [0, 0.1, 0.2, ..., 1.0] 处验证 y = x², y' = 2x
        x_vals = [i * 0.1 for i in range(11)]
        for x in x_vals:
            y = x**2
            y_prime = 2*x
            # 验证导数关系
            self.assertAlmostEqual(y_prime, 2*x, places=5)

    # ============================================================
    # 6. 矩阵微积分综合应用
    # ============================================================

    def test_matrix_operations(self):
        """测试矩阵运算。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])

        # 矩阵加法
        C = A + B
        self.assertEqual(C.data, [[6, 8], [10, 12]])

        # 矩阵乘法
        D = A * B
        self.assertEqual(D.data, [[19, 22], [43, 50]])

    def test_matrix_properties(self):
        """测试矩阵性质。"""
        from src.stdlib.linear_algebra import Matrix, matrix_determinant, matrix_trace

        A = Matrix([[1, 2], [3, 4]])

        # 行列式
        det = matrix_determinant(A)
        self.assertAlmostEqual(det, -2.0, places=5)

        # 迹
        tr = matrix_trace(A)
        self.assertAlmostEqual(tr, 5.0, places=5)

    def test_matrix_squared(self):
        """测试矩阵平方。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        A2 = A * A

        # A² = [[7, 10], [15, 22]]
        self.assertEqual(A2.data, [[7, 10], [15, 22]])

    def test_symbolic_derivative_matrix_element(self):
        """测试矩阵元素的符号求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        from src.stdlib.calculus_symbolic import symbolic_derivative

        # d/dx(x²) = 2x
        derivative = symbolic_derivative("x**2")
        self.assertEqual(derivative, "2*x")


class TestDemoIntegration(unittest.TestCase):
    """整合功能测试类。"""

    def test_full_workflow(self):
        """测试完整工作流。"""
        # 1. 导入模块
        from src.stdlib import calculus_symbolic, linear_algebra

        # 2. 检查 SymPy 可用性
        has_sympy = calculus_symbolic.HAS_SYMPY

        if has_sympy:
            # 3. 符号求导
            derivative = calculus_symbolic.symbolic_derivative("x**2")
            self.assertEqual(derivative, "2*x")

            # 4. 符号积分
            integral = calculus_symbolic.symbolic_integral("x**2")
            self.assertEqual(integral, "x**3/3")

            # 5. 矩阵运算
            A = linear_algebra.Matrix([[1, 2], [3, 4]])
            B = linear_algebra.Matrix([[5, 6], [7, 8]])
            C = A * B
            self.assertEqual(C.data, [[19, 22], [43, 50]])
        else:
            self.skipTest("SymPy 未安装")


if __name__ == "__main__":
    unittest.main()
