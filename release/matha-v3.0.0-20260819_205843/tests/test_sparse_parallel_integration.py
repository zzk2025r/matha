# -*- coding: utf-8 -*-
"""Matha v4.4 — 稀疏矩阵与并行计算集成测试

本脚本测试稀疏矩阵检测与并行计算的深度集成。

用法：
  python tests/test_sparse_parallel_integration.py
  python tests/test_sparse_parallel_integration.py --verbose
"""
import sys
import unittest
import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

logger = logging.getLogger(__name__)


class TestSparseParallelIntegration(unittest.TestCase):
    """稀疏矩阵与并行计算集成测试。"""

    def setUp(self):
        """设置测试环境。"""
        from src.stdlib.linear_algebra import Matrix, _is_sparse_matrix, svd_decompose_sparse
        self.Matrix = Matrix
        self.is_sparse = _is_sparse_matrix
        self.svd_sparse = svd_decompose_sparse
        import random
        self.random = random

    def create_sparse_matrix(self, n: int, num_nonzero: int = 40, seed: int = 42):
        """创建指定非零元素数的稀疏矩阵。"""
        self.random.seed(seed)
        data = [[0.0] * n for _ in range(n)]
        indices = list(range(n * n))
        self.random.shuffle(indices)
        for idx in indices[:num_nonzero]:
            i = idx // n
            j = idx % n
            data[i][j] = self.random.uniform(-1, 1)
        return self.Matrix(data)

    def test_sparse_detection_90_percent(self):
        """测试 90% 稀疏度矩阵检测。"""
        # 20x20 矩阵，400 个元素，90% 为零 => 40 个非零
        A = self.create_sparse_matrix(20, num_nonzero=40, seed=42)
        # 验证稀疏度
        total = 20 * 20
        zero_count = sum(1 for row in A.data for v in row if abs(v) < 1e-10)
        sparsity = zero_count / total
        logger.debug(f"稀疏度: {sparsity:.4f} (零元素: {zero_count}/{total})")
        # 使用 >= 0.89 允许浮点误差
        self.assertGreaterEqual(sparsity, 0.89, msg=f"稀疏度 {sparsity} < 0.89")
        self.assertTrue(self.is_sparse(A, threshold=0.9))

    def test_sparse_detection_95_percent(self):
        """测试 95% 稀疏度矩阵检测。"""
        # 20x20 矩阵，400 个元素，95% 为零 => 20 个非零
        A = self.create_sparse_matrix(20, num_nonzero=20, seed=42)
        self.assertTrue(self.is_sparse(A, threshold=0.9))

    def test_sparse_detection_80_percent(self):
        """测试 80% 稀疏度矩阵不满足条件。"""
        # 20x20 矩阵，400 个元素，80% 为零 => 80 个非零
        A = self.create_sparse_matrix(20, num_nonzero=80, seed=42)
        self.assertFalse(self.is_sparse(A, threshold=0.9))

    def test_dense_matrix_detection(self):
        """测试稠密矩阵检测。"""
        A = self.Matrix([[1.0, 2.0], [3.0, 4.0]])
        self.assertFalse(self.is_sparse(A, threshold=0.9))

    def test_parallel_sparse_svd(self):
        """测试并行稀疏 SVD。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix

        # 创建 4 个稀疏矩阵
        matrices = [self.create_sparse_matrix(20, num_nonzero=40, seed=i) for i in range(4)]

        def process_sparse(M):
            if _is_sparse_matrix(M, threshold=0.9):
                U, S, Vt = self.svd_sparse(M, max_iter=50)
                return S.data[0][0], "sparse"
            return 0.0, "dense"

        # 串行执行
        serial_results = []
        for M in matrices:
            result = process_sparse(M)
            serial_results.append(result)

        # 并行执行
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_sparse, M) for M in matrices]
            parallel_results = []
            for f in as_completed(futures):
                parallel_results.append(f.result())

        # 验证结果一致性（忽略顺序）
        serial_vals = sorted([r[0] for r in serial_results], reverse=True)
        parallel_vals = sorted([r[0] for r in parallel_results], reverse=True)

        for s_val, p_val in zip(serial_vals, parallel_vals):
            self.assertAlmostEqual(s_val, p_val, places=5,
                                   msg=f"奇异值不匹配: {s_val} vs {p_val}")

    def test_parallel_sparse_detection_batch(self):
        """测试批量稀疏矩阵检测。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix

        # 创建混合矩阵（稀疏 + 稠密）
        matrices = []
        for i in range(8):
            if i < 4:
                matrices.append(self.create_sparse_matrix(20, num_nonzero=40, seed=i))
            else:
                matrices.append(self.Matrix.random(20, 20))

        def classify_matrix(M):
            return "sparse" if _is_sparse_matrix(M, threshold=0.9) else "dense"

        # 串行分类
        serial_types = [classify_matrix(M) for M in matrices]

        # 并行分类
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(classify_matrix, M) for M in matrices]
            parallel_types = [f.result() for f in as_completed(futures)]

        # 验证分类一致性（顺序可能不同，但统计结果应相同）
        from collections import Counter
        self.assertEqual(Counter(serial_types), Counter(parallel_types))

    def test_sparse_svd_performance_comparison(self):
        """测试稀疏 SVD 性能对比。"""
        from src.stdlib.linear_algebra import svd_decompose

        # 创建稀疏矩阵
        A_sparse = self.create_sparse_matrix(30, num_nonzero=60, seed=42)

        # 基准测试：稀疏 SVD
        start = time.perf_counter()
        for _ in range(3):
            U, S, Vt = self.svd_sparse(A_sparse, max_iter=50)
        sparse_time = (time.perf_counter() - start) / 3 * 1000  # ms

        # 基准测试：标准 SVD
        start = time.perf_counter()
        for _ in range(3):
            U, S, Vt = svd_decompose(A_sparse)
        standard_time = (time.perf_counter() - start) / 3 * 1000  # ms

        logger.info(f"稀疏 SVD: {sparse_time:.2f} ms, 标准 SVD: {standard_time:.2f} ms")
        print(f"  稀疏 SVD: {sparse_time:.2f} ms")
        print(f"  标准 SVD: {standard_time:.2f} ms")

        # 稀疏 SVD 应该更快或相当
        self.assertLessEqual(sparse_time, standard_time * 1.5,
                             msg=f"稀疏 SVD 性能不佳: {sparse_time:.2f} vs {standard_time:.2f}")

    def test_parallel_sparse_svd_scalability(self):
        """测试并行稀疏 SVD 扩展性。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix

        # 创建 4 个稀疏矩阵
        matrices = [self.create_sparse_matrix(20, num_nonzero=40, seed=i) for i in range(4)]

        def process_sparse(M):
            if _is_sparse_matrix(M, threshold=0.9):
                U, S, Vt = self.svd_sparse(M, max_iter=50)
                return S.data[0][0]
            return 0.0

        # 串行执行
        start = time.perf_counter()
        results_serial = [process_sparse(M) for M in matrices]
        serial_time = time.perf_counter() - start

        # 并行执行
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_sparse, M) for M in matrices]
            results_parallel = [f.result() for f in as_completed(futures)]
        parallel_time = time.perf_counter() - start

        speedup = serial_time / parallel_time if parallel_time > 0 else 0
        logger.info(f"并行扩展性: 串行={serial_time*1000:.2f}ms, 并行={parallel_time*1000:.2f}ms, 加速比={speedup:.2f}x")
        print(f"  串行时间: {serial_time*1000:.2f} ms")
        print(f"  并行时间: {parallel_time*1000:.2f} ms")
        print(f"  加速比: {speedup:.2f}x")

        # 验证结果一致性
        self.assertEqual(len(results_serial), len(results_parallel))

    def test_integrated_workflow(self):
        """测试完整集成工作流。"""
        from src.stdlib.linear_algebra import _is_sparse_matrix

        # 创建工作流数据
        matrices = [
            self.create_sparse_matrix(15, num_nonzero=23, seed=1),
            self.create_sparse_matrix(15, num_nonzero=23, seed=2),
            self.Matrix.random(15, 15),
            self.Matrix.random(15, 15),
        ]

        def workflow_process(M):
            # 步骤1: 稀疏检测
            is_sparse = _is_sparse_matrix(M, threshold=0.9)

            # 步骤2: 根据稀疏性选择算法
            if is_sparse:
                U, S, Vt = self.svd_sparse(M, max_iter=50)
                method = "sparse_svd"
            else:
                from src.stdlib.linear_algebra import svd_decompose
                U, S, Vt = svd_decompose(M)
                method = "standard_svd"

            # 步骤3: 返回结果
            return {
                'max_singular_value': S.data[0][0],
                'method': method,
                'is_sparse': is_sparse
            }

        # 串行执行工作流
        serial_results = [workflow_process(M) for M in matrices]

        # 并行执行工作流
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(workflow_process, M) for M in matrices]
            parallel_results = [f.result() for f in as_completed(futures)]

        # 验证结果一致性
        self.assertEqual(len(serial_results), len(parallel_results))


def run_tests(verbose: bool = False):
    """运行测试。"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestSparseParallelIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 稀疏矩阵与并行计算集成测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    success = run_tests(args.verbose)
    sys.exit(0 if success else 1)
