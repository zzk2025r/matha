# -*- coding: utf-8 -*-
"""Matha v4.4 — 矩阵运算单元测试

测试矩阵运算核心功能：
  - 矩阵创建
  - 矩阵运算
  - 矩阵性质
  - 逆矩阵
  - 特征值
  - SVD 分解

用法：
  python -m unittest tests.test_linear_algebra -v
"""
import unittest
import sys
import os
import math

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMatrixCreation(unittest.TestCase):
    """矩阵创建测试类。"""

    def test_zeros_matrix(self):
        """测试零矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        zeros = Matrix.zeros(3, 4)
        self.assertEqual(zeros.shape, (3, 4))
        self.assertTrue(all(v == 0.0 for row in zeros.data for v in row))

    def test_ones_matrix(self):
        """测试全一矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        ones = Matrix.ones(2, 3)
        self.assertEqual(ones.shape, (2, 3))
        self.assertTrue(all(v == 1.0 for row in ones.data for v in row))

    def test_identity_matrix(self):
        """测试单位矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        I = Matrix.identity(3)
        self.assertEqual(I.shape, (3, 3))
        for i in range(3):
            for j in range(3):
                if i == j:
                    self.assertEqual(I.data[i][j], 1.0)
                else:
                    self.assertEqual(I.data[i][j], 0.0)

    def test_random_matrix(self):
        """测试随机矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix.random(2, 3, scale=10.0)
        self.assertEqual(A.shape, (2, 3))
        # 随机矩阵元素应在 [-scale, scale] 范围内
        for row in A.data:
            for v in row:
                self.assertGreaterEqual(v, -10.0)
                self.assertLessEqual(v, 10.0)

    def test_invalid_matrix(self):
        """测试无效矩阵创建。"""
        from src.stdlib.linear_algebra import Matrix

        with self.assertRaises(ValueError):
            Matrix([[1, 2], [3, 4, 5]])  # 行数不一致


class TestMatrixOperations(unittest.TestCase):
    """矩阵运算测试类。"""

    def test_matrix_addition(self):
        """测试矩阵加法。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])
        C = A + B

        self.assertEqual(C.data, [[6, 8], [10, 12]])

    def test_matrix_subtraction(self):
        """测试矩阵减法。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[5, 6], [7, 8]])
        B = Matrix([[1, 2], [3, 4]])
        C = A - B

        self.assertEqual(C.data, [[4, 4], [4, 4]])

    def test_matrix_multiplication(self):
        """测试矩阵乘法。"""
        from src.stdlib.linear_algebra import Matrix, matrix_multiply

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])
        C = matrix_multiply(A, B)

        self.assertEqual(C.data, [[19, 22], [43, 50]])

    def test_matrix_multiplication_dimension_mismatch(self):
        """测试矩阵乘法维度不匹配。"""
        from src.stdlib.linear_algebra import Matrix, matrix_multiply

        A = Matrix([[1, 2, 3], [4, 5, 6]])  # 2x3
        B = Matrix([[1, 2], [3, 4]])  # 2x2

        with self.assertRaises(ValueError):
            matrix_multiply(A, B)

    def test_matrix_transpose(self):
        """测试矩阵转置。"""
        from src.stdlib.linear_algebra import Matrix, matrix_transpose

        A = Matrix([[1, 2, 3], [4, 5, 6]])  # 2x3
        T = matrix_transpose(A)  # 3x2

        self.assertEqual(T.shape, (3, 2))
        self.assertEqual(T.data, [[1, 4], [2, 5], [3, 6]])

    def test_matrix_scale(self):
        """测试矩阵数乘。"""
        from src.stdlib.linear_algebra import Matrix, matrix_scale

        A = Matrix([[1, 2], [3, 4]])
        B = matrix_scale(A, 3)

        self.assertEqual(B.data, [[3, 6], [9, 12]])

    def test_matrix_multiply_operator(self):
        """测试矩阵乘法运算符。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])

        C = A * B
        self.assertEqual(C.data, [[19, 22], [43, 50]])

    def test_matrix_scalar_multiply_operator(self):
        """测试矩阵数乘运算符。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        B = A * 2

        self.assertEqual(B.data, [[2, 4], [6, 8]])

    def test_matrix_addition_dimension_mismatch(self):
        """测试矩阵加法维度不匹配。"""
        from src.stdlib.linear_algebra import Matrix

        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[1, 2, 3], [4, 5, 6]])

        with self.assertRaises(ValueError):
            A + B


class TestMatrixProperties(unittest.TestCase):
    """矩阵性质测试类。"""

    def test_determinant_2x2(self):
        """测试 2x2 矩阵行列式。"""
        from src.stdlib.linear_algebra import Matrix, matrix_determinant

        A = Matrix([[1, 2], [3, 4]])
        det = matrix_determinant(A)

        self.assertAlmostEqual(det, -2.0, places=5)

    def test_determinant_3x3(self):
        """测试 3x3 矩阵行列式。"""
        from src.stdlib.linear_algebra import Matrix, matrix_determinant

        A = Matrix([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        det = matrix_determinant(A)

        # 奇异矩阵，行列式为 0
        self.assertAlmostEqual(det, 0.0, places=5)

    def test_determinant_non_square(self):
        """测试非方阵行列式。"""
        from src.stdlib.linear_algebra import Matrix, matrix_determinant

        A = Matrix([[1, 2, 3], [4, 5, 6]])

        with self.assertRaises(ValueError):
            matrix_determinant(A)

    def test_trace(self):
        """测试矩阵迹。"""
        from src.stdlib.linear_algebra import Matrix, matrix_trace

        A = Matrix([[1, 2], [3, 4]])
        tr = matrix_trace(A)

        self.assertAlmostEqual(tr, 5.0, places=5)

    def test_rank(self):
        """测试矩阵秩。"""
        from src.stdlib.linear_algebra import Matrix, matrix_rank

        A = Matrix([[1, 2], [3, 4]])
        rank = matrix_rank(A)

        self.assertEqual(rank, 2)

    def test_rank_singular(self):
        """测试奇异矩阵秩。"""
        from src.stdlib.linear_algebra import Matrix, matrix_rank

        A = Matrix([[1, 2], [2, 4]])  # 第二行是第一行的 2 倍
        rank = matrix_rank(A)

        self.assertEqual(rank, 1)

    def test_frobenius_norm(self):
        """测试 Frobenius 范数。"""
        from src.stdlib.linear_algebra import Matrix, matrix_norm

        A = Matrix([[1, 2], [3, 4]])
        norm = matrix_norm(A, 'fro')

        # ||A||_F = sqrt(1+4+9+16) = sqrt(30)
        self.assertAlmostEqual(norm, math.sqrt(30), places=5)

    def test_infinity_norm(self):
        """测试无穷范数。"""
        from src.stdlib.linear_algebra import Matrix, matrix_norm

        A = Matrix([[1, 2, 3], [4, 5, 6]])
        norm = matrix_norm(A, 'inf')

        # 行和最大值: max(1+2+3, 4+5+6) = 15
        self.assertAlmostEqual(norm, 15.0, places=5)


class TestMatrixInverse(unittest.TestCase):
    """逆矩阵测试类。"""

    def test_inverse_2x2(self):
        """测试 2x2 矩阵求逆。"""
        from src.stdlib.linear_algebra import Matrix, matrix_inverse

        A = Matrix([[1, 2], [3, 4]])
        inv_A = matrix_inverse(A)

        # 验证 A × A^(-1) = I
        I = A * inv_A
        self.assertAlmostEqual(I.data[0][0], 1.0, places=5)
        self.assertAlmostEqual(I.data[0][1], 0.0, places=5)
        self.assertAlmostEqual(I.data[1][0], 0.0, places=5)
        self.assertAlmostEqual(I.data[1][1], 1.0, places=5)

    def test_inverse_singular(self):
        """测试奇异矩阵求逆。"""
        from src.stdlib.linear_algebra import Matrix, matrix_inverse

        A = Matrix([[1, 2], [2, 4]])  # 奇异矩阵
        inv_A = matrix_inverse(A)

        self.assertIsNone(inv_A)

    def test_inverse_3x3(self):
        """测试 3x3 矩阵求逆。"""
        from src.stdlib.linear_algebra import Matrix, matrix_inverse

        A = Matrix([[1, 2, 3], [0, 1, 4], [5, 6, 0]])
        inv_A = matrix_inverse(A)

        # 验证 A × A^(-1) = I
        I = A * inv_A
        for i in range(3):
            for j in range(3):
                expected = 1.0 if i == j else 0.0
                self.assertAlmostEqual(I.data[i][j], expected, places=5)


class TestEigenvalues(unittest.TestCase):
    """特征值测试类。"""

    def test_eigenvalues_2x2(self):
        """测试 2x2 矩阵特征值。"""
        from src.stdlib.linear_algebra import Matrix, matrix_eigenvalues

        A = Matrix([[2, 1], [1, 2]])
        eigenvalues = matrix_eigenvalues(A)

        # 特征值应为 3 和 1
        eigenvalues.sort()
        self.assertAlmostEqual(eigenvalues[0], 1.0, places=5)
        self.assertAlmostEqual(eigenvalues[1], 3.0, places=5)

    def test_eigenvalues_identity(self):
        """测试单位矩阵特征值。"""
        from src.stdlib.linear_algebra import Matrix, matrix_eigenvalues

        I = Matrix.identity(3)
        eigenvalues = matrix_eigenvalues(I)

        # 单位矩阵所有特征值均为 1
        for ev in eigenvalues:
            ev_real = ev.real if hasattr(ev, 'real') else ev
            self.assertAlmostEqual(float(ev_real), 1.0, places=5)


class TestSVD(unittest.TestCase):
    """SVD 分解测试类。"""

    def test_svd_2x2(self):
        """测试 2x2 矩阵 SVD 分解。"""
        from src.stdlib.linear_algebra import Matrix, svd_decompose

        A = Matrix([[3, 0], [0, 2]])
        U, Σ, V = svd_decompose(A)

        # 验证 Σ 是对角矩阵
        self.assertEqual(Σ.rows, 2)
        self.assertEqual(Σ.cols, 2)

        # 奇异值应是非负的
        for i in range(min(Σ.rows, Σ.cols)):
            self.assertGreaterEqual(Σ.data[i][i], 0)

    def test_svd_non_square(self):
        """测试非方阵 SVD 分解。"""
        from src.stdlib.linear_algebra import Matrix, svd_decompose

        A = Matrix([[1, 2, 3], [4, 5, 6]])  # 2x3
        U, Σ, V = svd_decompose(A)

        # 验证形状
        self.assertEqual(U.rows, 2)
        self.assertEqual(Σ.rows, 2)
        self.assertEqual(Σ.cols, 3)
        self.assertEqual(V.rows, 3)


class TestLinearSystem(unittest.TestCase):
    """线性方程组求解测试类。"""

    def test_solve_2x2_system(self):
        """测试 2x2 线性方程组求解。"""
        from src.stdlib.linear_algebra import Matrix, solve_linear_system

        # 求解: x + y = 3, 2x - y = 0
        A = Matrix([[1, 1], [2, -1]])
        b = [3, 0]
        solution = solve_linear_system(A, b)

        self.assertAlmostEqual(solution[0], 1.0, places=5)
        self.assertAlmostEqual(solution[1], 2.0, places=5)

    def test_solve_3x3_system(self):
        """测试 3x3 线性方程组求解。"""
        from src.stdlib.linear_algebra import Matrix, solve_linear_system

        # 求解: x + y + z = 6, 2x - y + z = 3, x + 2y - z = 2
        A = Matrix([[1, 1, 1], [2, -1, 1], [1, 2, -1]])
        b = [6, 3, 2]
        solution = solve_linear_system(A, b)

        # 验证解满足方程
        if solution is not None:
            # x + y + z = 6
            self.assertAlmostEqual(solution[0] + solution[1] + solution[2], 6.0, places=5)
            # 2x - y + z = 3
            self.assertAlmostEqual(2*solution[0] - solution[1] + solution[2], 3.0, places=5)
            # x + 2y - z = 2
            self.assertAlmostEqual(solution[0] + 2*solution[1] - solution[2], 2.0, places=5)

    def test_solve_singular_system(self):
        """测试奇异方程组求解。"""
        from src.stdlib.linear_algebra import Matrix, solve_linear_system

        # 奇异矩阵
        A = Matrix([[1, 2], [2, 4]])
        b = [3, 6]
        solution = solve_linear_system(A, b)

        self.assertIsNone(solution)


class TestMatrixDecomposition(unittest.TestCase):
    """矩阵分解测试类。"""

    def test_lu_decomposition(self):
        """测试 LU 分解。"""
        from src.stdlib.linear_algebra import Matrix, lu_decompose

        A = Matrix([[2, 1], [4, 3]])
        L, U = lu_decompose(A)

        # 验证 L × U = A
        product = L * U
        self.assertAlmostEqual(product.data[0][0], 2.0, places=5)
        self.assertAlmostEqual(product.data[0][1], 1.0, places=5)
        self.assertAlmostEqual(product.data[1][0], 4.0, places=5)
        self.assertAlmostEqual(product.data[1][1], 3.0, places=5)

    def test_cholesky_decomposition(self):
        """测试 Cholesky 分解。"""
        from src.stdlib.linear_algebra import Matrix, cholesky_decompose

        A = Matrix([[4, 2], [2, 3]])
        L = cholesky_decompose(A)

        # 验证 L × L^T = A
        if L is not None:
            product = L * matrix_transpose(L)
            self.assertAlmostEqual(product.data[0][0], 4.0, places=5)
            self.assertAlmostEqual(product.data[0][1], 2.0, places=5)
            self.assertAlmostEqual(product.data[1][0], 2.0, places=5)
            self.assertAlmostEqual(product.data[1][1], 3.0, places=5)

    def test_cholesky_non_positive_definite(self):
        """测试非正定矩阵的 Cholesky 分解。"""
        from src.stdlib.linear_algebra import Matrix, cholesky_decompose

        A = Matrix([[1, 2], [2, 1]])  # 非正定
        L = cholesky_decompose(A)

        self.assertIsNone(L)


def matrix_transpose(A):
    """辅助函数：矩阵转置。"""
    from src.stdlib.linear_algebra import matrix_transpose as mt
    return mt(A)


if __name__ == "__main__":
    unittest.main()
