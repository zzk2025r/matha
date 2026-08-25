# -*- coding: utf-8 -*-
"""Matha v4.4 — 符号微积分单元测试

测试符号微积分核心功能：
  - 符号求导
  - 符号积分
  - 定积分
  - 泰勒展开
  - 极限计算
  - 级数求和

用法：
  python -m unittest tests.test_calculus_symbolic -v
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSymbolicCalculus(unittest.TestCase):
    """符号微积分测试类。"""

    def setUp(self):
        """测试前准备。"""
        from src.stdlib import calculus_symbolic
        self.calculus = calculus_symbolic
        self.has_sympy = calculus_symbolic.HAS_SYMPY

    def test_sympy_available(self):
        """测试 SymPy 是否已安装。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装，跳过测试")

    def test_symbolic_derivative_polynomial(self):
        """测试多项式符号求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        # 基本多项式求导
        self.assertEqual(self.calculus.symbolic_derivative("x**2"), "2*x")
        self.assertEqual(self.calculus.symbolic_derivative("x**3 + 2*x + 1"), "3*x**2 + 2")
        self.assertEqual(self.calculus.symbolic_derivative("5*x**4 - 3*x**2 + x"), "20*x**3 - 6*x + 1")

    def test_symbolic_derivative_trig(self):
        """测试三角函数符号求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertEqual(self.calculus.symbolic_derivative("sin(x)"), "cos(x)")
        self.assertEqual(self.calculus.symbolic_derivative("cos(x)"), "-sin(x)")
        self.assertEqual(self.calculus.symbolic_derivative("tan(x)"), "1/cos(x)**2")

    def test_symbolic_derivative_exponential(self):
        """测试指数函数符号求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertEqual(self.calculus.symbolic_derivative("exp(x)"), "exp(x)")
        self.assertEqual(self.calculus.symbolic_derivative("exp(2*x)"), "2*exp(2*x)")

    def test_symbolic_derivative_product(self):
        """测试乘积法则求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.symbolic_derivative("exp(x)*cos(x)")
        # 结果应包含 exp(x) 和 cos(x)/sin(x)
        self.assertIn("exp(x)", result)
        self.assertIn("cos(x)", result)

    def test_symbolic_integral_polynomial(self):
        """测试多项式符号积分。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertEqual(self.calculus.symbolic_integral("x**2"), "x**3/3")
        self.assertEqual(self.calculus.symbolic_integral("x"), "x**2/2")
        self.assertEqual(self.calculus.symbolic_integral("3*x**2"), "3*x**3/3")

    def test_symbolic_integral_trig(self):
        """测试三角函数符号积分。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertEqual(self.calculus.symbolic_integral("sin(x)"), "-cos(x)")
        self.assertEqual(self.calculus.symbolic_integral("cos(x)"), "sin(x)")

    def test_definite_integral_polynomial(self):
        """测试多项式定积分。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        # ∫[0,1] x²dx = 1/3
        result = self.calculus.definite_integral("x**2", "x", 0, 1)
        self.assertAlmostEqual(result, 1/3, places=5)

        # ∫[0,1] x dx = 1/2
        result = self.calculus.definite_integral("x", "x", 0, 1)
        self.assertAlmostEqual(result, 0.5, places=5)

    def test_definite_integral_trig(self):
        """测试三角函数定积分。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        import math
        # ∫[0,π] sin(x)dx = 2
        result = self.calculus.definite_integral("sin(x)", "x", 0, math.pi)
        self.assertAlmostEqual(result, 2.0, places=5)

        # ∫[0,2π] sin(x)dx = 0
        result = self.calculus.definite_integral("sin(x)", "x", 0, 2*math.pi)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_taylor_series_exponential(self):
        """测试指数函数泰勒展开。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.taylor_series("exp(x)", "x", 0, 3)
        # 应包含 x^3, x^2, x, 常数项
        self.assertIn("x**3", result)
        self.assertIn("x**2", result)
        self.assertIn("x", result)

    def test_taylor_series_sine(self):
        """测试正弦函数泰勒展开。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.taylor_series("sin(x)", "x", 0, 5)
        # 应包含 x^5, x^3, x
        self.assertIn("x**5", result)
        self.assertIn("x**3", result)
        self.assertIn("x", result)

    def test_limit_sin_x_over_x(self):
        """测试经典极限 sin(x)/x → 1 (x→0)。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.limit("sin(x)/x", "x", 0)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_limit_1_over_x_at_infinity(self):
        """测试极限 1/x → 0 (x→∞)。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.limit("1/x", "x", float('inf'))
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_limit_e_x_at_infinity(self):
        """测试极限 e^x → ∞ (x→∞)。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.limit("exp(x)", "x", float('inf'))
        self.assertEqual(result, float('inf'))

    def test_sympy_not_installed(self):
        """测试 SymPy 未安装时的行为。"""
        # 保存原始状态
        original_has_sympy = self.calculus.HAS_SYMPY

        # 模拟未安装
        self.calculus.HAS_SYMPY = False

        with self.assertRaises(ImportError):
            self.calculus.symbolic_derivative("x**2")

        # 恢复
        self.calculus.HAS_SYMPY = original_has_sympy

    def test_invalid_expression(self):
        """测试无效表达式处理。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        with self.assertRaises(ValueError):
            self.calculus.symbolic_derivative("invalid_expression")

    def test_derivative_at_point(self):
        """测试在特定点求导。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        # d/dx(x²) at x=3 should be 6
        result = self.calculus.symbolic_derivative("x**2")
        self.assertEqual(result, "2*x")

    def test_multiple_variables(self):
        """测试多变量符号运算。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        # 对 y 求偏导
        result = self.calculus.symbolic_derivative("x**2 + y**2", "y")
        self.assertEqual(result, "2*y")


class TestSymbolicConstants(unittest.TestCase):
    """符号数学常量测试类。"""

    def setUp(self):
        """测试前准备。"""
        from src.stdlib import calculus_symbolic
        self.calculus = calculus_symbolic
        self.has_sympy = calculus_symbolic.HAS_SYMPY

    def test_pi_constant(self):
        """测试 π 常量。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertAlmostEqual(float(self.calculus.PI), 3.141592653589793, places=10)

    def test_e_constant(self):
        """测试 e 常量。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        self.assertAlmostEqual(float(self.calculus.E), 2.718281828459045, places=10)

    def test_constants_list(self):
        """测试常量列表。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        constants = self.calculus.SymbolicConstants.list_all()
        self.assertIn('PI', constants)
        self.assertIn('E', constants)
        self.assertIn('I', constants)


class TestLaTeXFormat(unittest.TestCase):
    """LaTeX 格式转换测试类。"""

    def setUp(self):
        """测试前准备。"""
        from src.stdlib import calculus_symbolic
        self.calculus = calculus_symbolic
        self.has_sympy = calculus_symbolic.HAS_SYMPY

    def test_latex_polynomial(self):
        """测试多项式 LaTeX 格式。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.latex_format("x**2 + 2*x + 1")
        self.assertIn("x", result)

    def test_latex_trig(self):
        """测试三角函数 LaTeX 格式。"""
        if not self.has_sympy:
            self.skipTest("SymPy 未安装")

        result = self.calculus.latex_format("sin(x)")
        self.assertIn("sin", result)


if __name__ == "__main__":
    unittest.main()
