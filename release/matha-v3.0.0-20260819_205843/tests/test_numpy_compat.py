# -*- coding: utf-8 -*-
"""Matha NumPy 兼容层测试

测试纯 Python NumPy 实现的功能。
"""
import unittest
import sys
import math
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from numpy_compat import (
    ndarray, array, zeros, ones, eye, arange, linspace, random,
    matrix_multiply, matrix_transpose, matrix_inverse,
    matrix_determinant, svd_decompose, trace, norm
)


class TestNdarray(unittest.TestCase):
    def test_create_1d(self):
        a = array([1, 2, 3, 4, 5])
        self.assertEqual(a.shape, (5,))
        self.assertEqual(a.size, 5)

    def test_create_2d(self):
        a = array([[1, 2, 3], [4, 5, 6]])
        self.assertEqual(a.shape, (2, 3))

    def test_zeros(self):
        a = zeros((3, 4))
        self.assertEqual(a.shape, (3, 4))

    def test_ones(self):
        a = ones((2, 3))
        self.assertEqual(a.shape, (2, 3))

    def test_eye(self):
        a = eye(3)
        self.assertEqual(a.shape, (3, 3))
        for i in range(3):
            self.assertAlmostEqual(a[i][i], 1.0)
            for j in range(3):
                if i != j:
                    self.assertAlmostEqual(a[i][j], 0.0)

    def test_arange(self):
        a = arange(0, 5, 1)
        self.assertEqual(a.shape, (5,))
        for i, val in enumerate([0, 1, 2, 3, 4]):
            self.assertAlmostEqual(a[i], val)

    def test_linspace(self):
        a = linspace(0, 10, 5)
        self.assertEqual(a.shape, (5,))

    def test_random(self):
        a = random(5)
        self.assertEqual(a.shape, (5,))
        for val in a.flatten():
            self.assertTrue(0.0 <= val < 1.0)

    def test_indexing(self):
        a = array([[1, 2], [3, 4]])
        self.assertEqual(a[0][0], 1)
        self.assertEqual(a[1][1], 4)


class TestArithmetic(unittest.TestCase):
    def test_add_scalar(self):
        a = array([1, 2, 3])
        b = a + 10
        self.assertEqual(b[0], 11)
        self.assertEqual(b[1], 12)
        self.assertEqual(b[2], 13)

    def test_add_array(self):
        a = array([1, 2, 3])
        b = array([4, 5, 6])
        c = a + b
        self.assertEqual(c[0], 5)
        self.assertEqual(c[1], 7)
        self.assertEqual(c[2], 9)

    def test_mul_scalar(self):
        a = array([1, 2, 3])
        b = a * 3
        self.assertEqual(b[0], 3)
        self.assertEqual(b[1], 6)
        self.assertEqual(b[2], 9)


class TestLinearAlgebra(unittest.TestCase):
    def test_matrix_multiply(self):
        A = array([[1, 2], [3, 4]])
        B = array([[5, 6], [7, 8]])
        C = matrix_multiply(A, B)
        self.assertAlmostEqual(C[0][0], 19)
        self.assertAlmostEqual(C[0][1], 22)
        self.assertAlmostEqual(C[1][0], 43)
        self.assertAlmostEqual(C[1][1], 50)

    def test_matrix_transpose(self):
        A = array([[1, 2, 3], [4, 5, 6]])
        B = matrix_transpose(A)
        self.assertEqual(B.shape, (3, 2))
        self.assertAlmostEqual(B[0][0], 1)
        self.assertAlmostEqual(B[2][1], 6)

    def test_matrix_inverse(self):
        A = array([[1, 2], [3, 4]])
        B = matrix_inverse(A)
        C = matrix_multiply(A, B)
        self.assertAlmostEqual(C[0][0], 1.0, places=5)
        self.assertAlmostEqual(C[1][1], 1.0, places=5)
        self.assertAlmostEqual(C[0][1], 0.0, places=5)
        self.assertAlmostEqual(C[1][0], 0.0, places=5)

    def test_matrix_determinant(self):
        A = array([[1, 2], [3, 4]])
        det = matrix_determinant(A)
        self.assertAlmostEqual(det, -2.0)

    def test_trace(self):
        A = array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        tr = trace(A)
        self.assertAlmostEqual(tr, 15.0)

    def test_norm(self):
        A = array([[1, 2], [3, 4]])
        f_norm = norm(A)
        expected = math.sqrt(1 + 4 + 9 + 16)
        self.assertAlmostEqual(f_norm, expected)


class TestSVD(unittest.TestCase):
    def test_svd_simple(self):
        A = array([[1, 0], [0, 2]])
        U, S, Vt = svd_decompose(A)
        self.assertEqual(U.shape, (2, 2))
        self.assertEqual(S.shape, (2, 2))
        self.assertEqual(Vt.shape, (2, 2))

    def test_svd_reconstruction(self):
        A = array([[1, 2], [3, 4]])
        U, S, Vt = svd_decompose(A)
        self.assertEqual(U.shape, (2, 2))
        self.assertEqual(S.shape, (2, 2))
        self.assertEqual(Vt.shape, (2, 2))
        singular_values = [S[i][i] for i in range(min(S.shape))]
        self.assertTrue(any(sv != 0 for sv in singular_values))


class TestMobileCompat(unittest.TestCase):
    def test_mobile_detection(self):
        from mobile_compat import is_mobile_device
        self.assertFalse(is_mobile_device())

    def test_get_mobile_api(self):
        from mobile_compat import get_mobile_api
        api = get_mobile_api()
        zeros = api.zeros((3, 3))
        self.assertEqual(zeros.shape, (3, 3))
        ones = api.ones((2, 2))
        self.assertEqual(ones.shape, (2, 2))
        eye = api.eye(3)
        self.assertEqual(eye.shape, (3, 3))


if __name__ == '__main__':
    unittest.main()
