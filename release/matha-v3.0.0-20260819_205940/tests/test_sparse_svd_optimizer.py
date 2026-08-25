# -*- coding: utf-8 -*-
"""Matha v4.4 — 稀疏 SVD 优化器单元测试

本脚本测试 SparseSVDOptimizer 类的功能。

用法：
  python tests/test_sparse_svd_optimizer.py
  python tests/test_sparse_svd_optimizer.py --verbose
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


class TestSparseSVDOptimizer(unittest.TestCase):
    """稀疏 SVD 优化器测试。"""

    def setUp(self):
        """设置测试环境。"""
        from src.optimization.sparse_svd import SparseSVDOptimizer
        from src.stdlib.linear_algebra import Matrix
        import random

        self.Optimizer = SparseSVDOptimizer
        self.Matrix = Matrix
        self.random = random

    def create_sparse_matrix(self, n: int, sparsity: float = 0.9, seed: int = 42):
        """创建稀疏矩阵。"""
        self.random.seed(seed)
        data = [[0.0] * n for _ in range(n)]
        num_nonzero = int(n * n * (1 - sparsity))
        indices = list(range(n * n))
        self.random.shuffle(indices)
        for idx in indices[:num_nonzero]:
            i = idx // n
            j = idx % n
            data[i][j] = self.random.uniform(-1, 1)
        return self.Matrix(data)

    def test_initialization(self):
        """测试初始化。"""
        optimizer = self.Optimizer(threshold=0.9, max_iter=100, cache_enabled=True)
        self.assertEqual(optimizer.threshold, 0.9)
        self.assertEqual(optimizer.max_iter, 100)
        self.assertTrue(optimizer.cache_enabled)

    def test_is_sparse_true(self):
        """测试稀疏矩阵检测（返回 True）。"""
        optimizer = self.Optimizer(threshold=0.9)
        A = self.create_sparse_matrix(20, sparsity=0.95)
        self.assertTrue(optimizer.is_sparse(A))

    def test_is_sparse_false(self):
        """测试稀疏矩阵检测（返回 False）。"""
        optimizer = self.Optimizer(threshold=0.9)
        A = self.Matrix.random(20, 20)
        self.assertFalse(optimizer.is_sparse(A))

    def test_is_sparse_boundary(self):
        """测试稀疏矩阵检测边界情况。"""
        # 90% 稀疏度
        optimizer = self.Optimizer(threshold=0.9)
        A = self.create_sparse_matrix(20, sparsity=0.90)
        self.assertTrue(optimizer.is_sparse(A))

        # 89% 稀疏度
        A = self.create_sparse_matrix(20, sparsity=0.89)
        self.assertFalse(optimizer.is_sparse(A))

    def test_svd_sparse_matrix(self):
        """测试稀疏矩阵 SVD。"""
        optimizer = self.Optimizer(threshold=0.9, max_iter=50)
        A = self.create_sparse_matrix(20, sparsity=0.95)

        result = optimizer.svd(A, use_numpy=False)

        self.assertEqual(result.U.rows, 20)
        self.assertEqual(result.U.cols, 20)
        self.assertEqual(result.S.rows, 20)
        self.assertEqual(result.S.cols, 20)
        self.assertEqual(result.Vt.rows, 20)
        self.assertEqual(result.Vt.cols, 20)
        self.assertEqual(result.method, 'sparse')
        self.assertGreater(result.computation_time_ms, 0)

    def test_svd_cache(self):
        """测试 SVD 缓存。"""
        optimizer = self.Optimizer(threshold=0.9, cache_enabled=True)
        A = self.create_sparse_matrix(20, sparsity=0.95)

        # 第一次调用
        result1 = optimizer.svd(A, use_numpy=False)
        time1 = result1.computation_time_ms

        # 第二次调用（应使用缓存）
        result2 = optimizer.svd(A, use_numpy=False)
        time2 = result2.computation_time_ms

        # 缓存命中时应该更快
        self.assertLess(time2, time1 * 0.5, msg="缓存未生效")

    def test_clear_cache(self):
        """测试清空缓存。"""
        optimizer = self.Optimizer(threshold=0.9, cache_enabled=True)
        A = self.create_sparse_matrix(20, sparsity=0.95)

        # 填充缓存
        optimizer.svd(A, use_numpy=False)
        self.assertEqual(len(optimizer._svd_cache), 1)

        # 清空缓存
        optimizer.clear_cache()
        self.assertEqual(len(optimizer._svd_cache), 0)

    def test_predict_large_matrix(self):
        """测试大规模矩阵预测。"""
        optimizer = self.Optimizer(threshold=0.9)

        # 基于 50x50 数据预测 1000x1000
        base_size = 50
        base_time = 1908.38  # ms

        prediction = optimizer.predict_large_matrix_time(
            base_size=base_size,
            base_time_ms=base_time,
            target_size=1000,
            sparsity=0.95
        )

        logger.info(f"预测结果: {prediction}")

        # 验证预测值合理
        self.assertGreater(prediction['predicted_standard_time_ms'], 0)
        self.assertGreater(prediction['predicted_sparse_time_ms'], 0)
        self.assertLess(prediction['predicted_sparse_time_ms'], prediction['predicted_standard_time_ms'])

    def test_batch_svd(self):
        """测试批量 SVD。"""
        optimizer = self.Optimizer(threshold=0.9, max_iter=50)

        matrices = [self.create_sparse_matrix(20, sparsity=0.95, seed=i) for i in range(4)]

        results = optimizer.batch_svd(matrices, use_numpy=False)

        self.assertEqual(len(results), 4)
        for result in results:
            self.assertEqual(result.method, 'sparse')
            self.assertEqual(result.U.rows, 20)

    def test_batch_svd_parallel(self):
        """测试并行批量 SVD。"""
        optimizer = self.Optimizer(threshold=0.9, max_iter=50)

        matrices = [self.create_sparse_matrix(20, sparsity=0.95, seed=i) for i in range(4)]

        results = optimizer.batch_svd(matrices, use_numpy=False, parallel=True, n_workers=2)

        self.assertEqual(len(results), 4)

    def test_get_statistics(self):
        """测试统计信息获取。"""
        optimizer = self.Optimizer(threshold=0.9, max_iter=100)

        stats = optimizer.get_statistics()

        self.assertEqual(stats['threshold'], 0.9)
        self.assertEqual(stats['max_iter'], 100)
        self.assertEqual(stats['cache_enabled'], True)
        self.assertIn('counters', stats)

    def test_quick_svd(self):
        """测试便捷函数 quick_svd。"""
        from src.optimization.sparse_svd import quick_svd

        A = self.create_sparse_matrix(20, sparsity=0.95)
        U, S, Vt = quick_svd(A, threshold=0.9, max_iter=50)

        self.assertEqual(U.rows, 20)
        self.assertEqual(S.rows, 20)
        self.assertEqual(Vt.rows, 20)


def run_tests(verbose: bool = False):
    """运行测试。"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestSparseSVDOptimizer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 稀疏 SVD 优化器测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    success = run_tests(args.verbose)
    sys.exit(0 if success else 1)
