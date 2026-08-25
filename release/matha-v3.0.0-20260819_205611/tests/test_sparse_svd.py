# -*- coding: utf-8 -*-
"""Matha v4.4 — 稀疏矩阵 SVD 测试

本脚本测试稀疏矩阵 SVD 分解功能。

用法：
  python tests/test_sparse_svd.py
  python tests/test_sparse_svd.py --verbose
"""
import sys
import unittest
import logging
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

logger = logging.getLogger(__name__)


class TestSparseSVD(unittest.TestCase):
    """稀疏矩阵 SVD 测试。"""

    def setUp(self):
        """设置测试环境。"""
        from src.stdlib.linear_algebra import Matrix
        self.Matrix = Matrix

    def test_is_sparse_matrix_dense(self):
        """测试稠密矩阵检测。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix
        A = self.Matrix([[1.0, 2.0], [3.0, 4.0]])
        self.assertFalse(_is_sparse_matrix(A, threshold=0.9))

    def test_is_sparse_matrix_sparse(self):
        """测试稀疏矩阵检测。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix
        # 90% 为零的矩阵
        A = self.Matrix([
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0]
        ])
        self.assertTrue(_is_sparse_matrix(A, threshold=0.9))

    def test_svd_sparse_10x10(self):
        """测试 10x10 稀疏矩阵 SVD。"""
        from src.stdlib.linear_algebra import svd_decompose
        import random
        random.seed(42)

        # 创建 90% 稀疏的矩阵
        data = [[0.0] * 10 for _ in range(10)]
        for i in range(10):
            for j in range(10):
                if random.random() > 0.9:
                    data[i][j] = random.uniform(-1, 1)

        A = self.Matrix(data)
        U, S, Vt = svd_decompose(A)

        self.assertEqual(U.rows, 10)
        self.assertEqual(U.cols, 10)
        self.assertEqual(S.rows, 10)
        self.assertEqual(S.cols, 10)
        self.assertEqual(Vt.rows, 10)
        self.assertEqual(Vt.cols, 10)

        # 验证奇异值非负
        for i in range(10):
            self.assertGreaterEqual(S.data[i][i], 0)

    def test_svd_sparse_20x20(self):
        """测试 20x20 稀疏矩阵 SVD。"""
        from src.stdlib.linear_algebra import svd_decompose
        import random
        random.seed(42)

        # 创建 95% 稀疏的矩阵
        data = [[0.0] * 20 for _ in range(20)]
        for i in range(20):
            for j in range(20):
                if random.random() > 0.95:
                    data[i][j] = random.uniform(-1, 1)

        A = self.Matrix(data)
        U, S, Vt = svd_decompose(A)

        self.assertEqual(U.rows, 20)
        self.assertEqual(S.rows, 20)
        self.assertEqual(Vt.rows, 20)

    def test_svd_sparse_vs_dense(self):
        """测试稀疏和稠密矩阵 SVD 结果一致性。"""
        from src.stdlib.linear_algebra import svd_decompose

        # 创建相同的矩阵（一个稀疏，一个稠密）
        import random
        random.seed(42)

        data_sparse = [[0.0] * 10 for _ in range(10)]
        data_dense = [[0.0] * 10 for _ in range(10)]
        for i in range(10):
            for j in range(10):
                if random.random() > 0.9:
                    val = random.uniform(-1, 1)
                    data_sparse[i][j] = val
                    data_dense[i][j] = val

        A_sparse = self.Matrix(data_sparse)
        A_dense = self.Matrix(data_dense)

        U1, S1, Vt1 = svd_decompose(A_sparse)
        U2, S2, Vt2 = svd_decompose(A_dense)

        # 比较奇异值（允许一定误差）
        for i in range(10):
            self.assertAlmostEqual(S1.data[i][i], S2.data[i][i], places=5,
                                 msg=f"奇异值 {i} 不匹配: {S1.data[i][i]} vs {S2.data[i][i]}")

    def test_svd_sparse_reconstruction(self):
        """测试稀疏矩阵 SVD 重建。"""
        from src.stdlib.linear_algebra import svd_decompose, matrix_multiply
        import random
        random.seed(42)

        # 创建稀疏矩阵
        data = [[0.0] * 10 for _ in range(10)]
        for i in range(10):
            for j in range(10):
                if random.random() > 0.9:
                    data[i][j] = random.uniform(-1, 1)

        A = self.Matrix(data)
        U, S, Vt = svd_decompose(A)

        # 重建矩阵
        AS = matrix_multiply(A, Vt)
        UTS = matrix_multiply(U, S)

        # 验证重建误差
        max_error = 0.0
        for i in range(10):
            for j in range(10):
                error = abs(A.data[i][j] - sum(UTS.data[i][k] * AS.data[k][j] for k in range(10)))
                max_error = max(max_error, error)

        logger.info(f"SVD 重建最大误差: {max_error:.6f}")
        self.assertLess(max_error, 1.0, msg=f"SVD 重建误差过大: {max_error}")


def run_tests(verbose: bool = False):
    """运行测试。"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestSparseSVD)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 稀疏矩阵 SVD 测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    success = run_tests(args.verbose)
    sys.exit(0 if success else 1)
