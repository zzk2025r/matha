# -*- coding: utf-8 -*-
"""Matha v4.4 — 稀疏矩阵 SVD 优化模块

本模块提供稀疏矩阵 SVD 分解的优化实现，包括：
  - 稀疏矩阵检测
  - 稀疏 SVD 分解（Lanczos 迭代法）
  - 性能优化与缓存

数学背景：
  对于稀疏矩阵 A（稀疏度 > 90%），使用 Lanczos 迭代法
  可以显著减少计算量，避免遍历零元素。

用法：
  from src.optimization.sparse_svd import SparseSVDOptimizer

  optimizer = SparseSVDOptimizer(threshold=0.9, max_iter=100)

  # 检测稀疏矩阵
  is_sparse = optimizer.is_sparse(matrix)

  # 执行稀疏 SVD
  U, S, Vt = optimizer.svd(matrix)

  # 性能对比
  speedup = optimizer.compare_performance(matrix)
"""
from __future__ import annotations
import logging
import time
import random
import functools
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SVDResult:
    """SVD 分解结果。"""
    U: 'Matrix'          # 左奇异向量
    S: 'Matrix'          # 奇异值矩阵
    Vt: 'Matrix'         # 右奇异向量转置
    method: str          # 使用的算法 ('numpy', 'sparse', 'standard')
    computation_time_ms: float = 0.0
    sparsity: float = 0.0


@dataclass
class PerformanceStats:
    """性能统计。"""
    python_time_ms: float = 0.0
    numpy_time_ms: float = 0.0
    sparse_time_ms: float = 0.0
    speedup_vs_python: float = 0.0
    speedup_vs_numpy: float = 0.0


class SparseSVDOptimizer:
    """
    稀疏矩阵 SVD 优化器。

    该优化器提供：
    1. 稀疏矩阵检测
    2. 稀疏 SVD 分解（Lanczos 迭代法）
    3. 性能对比与缓存

    用法：
        optimizer = SparseSVDOptimizer(threshold=0.9, max_iter=100)
        result = optimizer.svd(matrix)
    """

    def __init__(
        self,
        threshold: float = 0.9,
        max_iter: int = 100,
        max_singular_values: int = 10,
        cache_enabled: bool = True,
        cache_max_size: int = 1000
    ):
        """
        初始化优化器。

        Args:
            threshold: 稀疏度阈值（默认 0.9，即 90% 元素为零）
            max_iter: 最大迭代次数
            max_singular_values: 最大计算的奇异值数量
            cache_enabled: 是否启用缓存
            cache_max_size: 缓存最大条目数
        """
        self.threshold = threshold
        self.max_iter = max_iter
        self.max_singular_values = max_singular_values
        self.cache_enabled = cache_enabled
        self.cache_max_size = cache_max_size

        # 缓存
        self._svd_cache: Dict[tuple, SVDResult] = {}
        self._counters = {'sparse_svd': 0, 'numpy_svd': 0, 'standard_svd': 0}

        logger.info(f"稀疏 SVD 优化器初始化: threshold={threshold}, max_iter={max_iter}")

    def is_sparse(self, A: 'Matrix') -> bool:
        """
        检测矩阵是否为稀疏矩阵。

        Args:
            A: m×n 矩阵

        Returns:
            如果是稀疏矩阵返回 True
        """
        from src.stdlib.linear_algebra import Matrix as MathaMatrix
        if not isinstance(A, MathaMatrix):
            A = MathaMatrix(A)

        total = A.rows * A.cols
        zero_count = sum(1 for row in A.data for v in row if abs(v) < 1e-10)
        sparsity = zero_count / total if total > 0 else 0

        is_sparse_result = sparsity >= self.threshold
        logger.debug(f"稀疏度检测: {sparsity:.4f} ({'稀疏' if is_sparse_result else '稠密'})")
        return is_sparse_result

    def _get_sparsity(self, A: 'Matrix') -> float:
        """计算矩阵稀疏度。"""
        from src.stdlib.linear_algebra import Matrix as MathaMatrix
        if not isinstance(A, MathaMatrix):
            A = MathaMatrix(A)

        total = A.rows * A.cols
        zero_count = sum(1 for row in A.data for v in row if abs(v) < 1e-10)
        return zero_count / total if total > 0 else 0.0

    def _make_cache_key(self, A: 'Matrix') -> tuple:
        """创建缓存键。"""
        return tuple(tuple(row) for row in A.data)

    def _evict_cache(self):
        """缓存淘汰。"""
        if len(self._svd_cache) > self.cache_max_size:
            # 移除最早插入的条目
            oldest_key = next(iter(self._svd_cache))
            del self._svd_cache[oldest_key]
            logger.debug(f"缓存淘汰: 当前大小 {len(self._svd_cache)}")

    def svd(
        self,
        A: 'Matrix',
        use_numpy: bool = True,
        force_sparse: bool = False
    ) -> SVDResult:
        """
        执行 SVD 分解，自动选择最优算法。

        Args:
            A: m×n 矩阵
            use_numpy: 是否优先使用 NumPy
            force_sparse: 强制使用稀疏算法

        Returns:
            SVDResult: 包含 U, S, Vt 和性能统计
        """
        from src.stdlib.linear_algebra import Matrix as MathaMatrix, svd_decompose, svd_decompose_sparse, _is_sparse_matrix

        if not isinstance(A, MathaMatrix):
            A = MathaMatrix(A)

        start_time = time.perf_counter()

        # 检查缓存
        cache_key = self._make_cache_key(A)
        if self.cache_enabled and cache_key in self._svd_cache:
            result = self._svd_cache[cache_key]
            result.computation_time_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"使用缓存的 SVD: {A.shape}")
            return result

        # 检测稀疏性
        is_sparse_matrix = _is_sparse_matrix(A, threshold=self.threshold)
        sparsity = self._get_sparsity(A)

        # 选择算法
        if force_sparse or is_sparse_matrix:
            logger.info(f"使用稀疏 SVD: 稀疏度={sparsity:.4f}, 形状={A.shape}")
            U, S, Vt = svd_decompose_sparse(A, max_iter=self.max_iter)
            method = 'sparse'
            self._counters['sparse_svd'] += 1
        elif use_numpy:
            try:
                import numpy as np
                A_np = np.array(A.data, dtype=float)
                U_np, s_np, Vt_np = np.linalg.svd(A_np)

                from src.stdlib.linear_algebra import Matrix
                U = Matrix(U_np.tolist())
                S = Matrix(np.diag(s_np).tolist())
                Vt = Matrix(Vt_np.tolist())

                method = 'numpy'
                self._counters['numpy_svd'] += 1
                logger.info(f"使用 NumPy SVD: 形状={A.shape}")
            except ImportError:
                logger.warning("NumPy 未安装，使用标准 SVD")
                U, S, Vt = svd_decompose(A)
                method = 'standard'
                self._counters['standard_svd'] += 1
        else:
            U, S, Vt = svd_decompose(A)
            method = 'standard'
            self._counters['standard_svd'] += 1

        computation_time = (time.perf_counter() - start_time) * 1000

        result = SVDResult(
            U=U,
            S=S,
            Vt=Vt,
            method=method,
            computation_time_ms=computation_time,
            sparsity=sparsity
        )

        # 存入缓存
        if self.cache_enabled:
            self._svd_cache[cache_key] = result
            self._evict_cache()

        logger.info(f"SVD 完成: 方法={method}, 时间={computation_time:.2f}ms, 稀疏度={sparsity:.4f}")
        return result

    def compare_performance(
        self,
        A: 'Matrix',
        iterations: int = 5
    ) -> PerformanceStats:
        """
        对比不同算法的性能。

        Args:
            A: 测试矩阵
            iterations: 测试迭代次数

        Returns:
            PerformanceStats: 性能统计
        """
        from src.stdlib.linear_algebra import Matrix, svd_decompose, svd_decompose_sparse
        import statistics

        stats = PerformanceStats()

        # 纯 Python 标准 SVD
        def standard_svd():
            return svd_decompose(A)

        times_standard = []
        for _ in range(iterations):
            start = time.perf_counter()
            standard_svd()
            times_standard.append((time.perf_counter() - start) * 1000)
        stats.python_time_ms = statistics.mean(times_standard)

        # 稀疏 SVD
        def sparse_svd():
            return svd_decompose_sparse(A, max_iter=self.max_iter)

        times_sparse = []
        for _ in range(iterations):
            start = time.perf_counter()
            sparse_svd()
            times_sparse.append((time.perf_counter() - start) * 1000)
        stats.sparse_time_ms = statistics.mean(times_sparse)

        # 计算加速比
        if stats.python_time_ms > 0:
            stats.speedup_vs_python = stats.python_time_ms / stats.sparse_time_ms

        logger.info(f"性能对比: 标准 SVD={stats.python_time_ms:.2f}ms, 稀疏 SVD={stats.sparse_time_ms:.2f}ms, 加速比={stats.speedup_vs_python:.2f}x")

        return stats

    def batch_svd(
        self,
        matrices: List['Matrix'],
        use_numpy: bool = True,
        parallel: bool = False,
        n_workers: int = 4
    ) -> List[SVDResult]:
        """
        批量 SVD 分解。

        Args:
            matrices: 矩阵列表
            use_numpy: 是否优先使用 NumPy
            parallel: 是否启用并行计算
            n_workers: 工作线程数

        Returns:
            SVDResult 列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []

        if parallel:
            logger.info(f"并行批量 SVD: {len(matrices)} 个矩阵, {n_workers} 线程")

            def process_matrix(M):
                return self.svd(M, use_numpy=use_numpy)

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = {executor.submit(process_matrix, M): i for i, M in enumerate(matrices)}
                for future in as_completed(futures):
                    idx = futures[future]
                    results.append((idx, future.result()))

            # 按顺序排序
            results.sort(key=lambda x: x[0])
            results = [r[1] for r in results]
        else:
            logger.info(f"串行批量 SVD: {len(matrices)} 个矩阵")
            for i, M in enumerate(matrices):
                result = self.svd(M, use_numpy=use_numpy)
                results.append(result)
                if (i + 1) % 10 == 0:
                    logger.info(f"  进度: {i + 1}/{len(matrices)}")

        logger.info(f"批量 SVD 完成: {len(results)} 个矩阵")
        return results

    def predict_large_matrix_time(
        self,
        base_size: int,
        base_time_ms: float,
        target_size: int,
        sparsity: float = 0.9
    ) -> Dict[str, float]:
        """
        预测大规模矩阵的 SVD 耗时。

        基于 O(n³) 复杂度模型进行预测。

        Args:
            base_size: 基准矩阵规模
            base_time_ms: 基准耗时（ms）
            target_size: 目标矩阵规模
            sparsity: 稀疏度（0-1）

        Returns:
            预测耗时字典
        """
        # O(n³) 复杂度模型
        size_ratio = (target_size / base_size) ** 3

        # 稀疏矩阵加速因子（经验值）
        sparse_speedup = 1.0
        if sparsity >= 0.9:
            sparse_speedup = 2.0  # 90%+ 稀疏度，加速 2x
        if sparsity >= 0.95:
            sparse_speedup = 5.0  # 95%+ 稀疏度，加速 5x
        if sparsity >= 0.99:
            sparse_speedup = 10.0  # 99%+ 稀疏度，加速 10x

        # 预测耗时
        predicted_standard_time = base_time_ms * size_ratio
        predicted_sparse_time = predicted_standard_time / sparse_speedup

        return {
            'base_size': base_size,
            'target_size': target_size,
            'sparsity': sparsity,
            'sparse_speedup': sparse_speedup,
            'predicted_standard_time_ms': predicted_standard_time,
            'predicted_sparse_time_ms': predicted_sparse_time,
            'predicted_standard_time_sec': predicted_standard_time / 1000,
            'predicted_sparse_time_sec': predicted_sparse_time / 1000,
        }

    def get_statistics(self) -> Dict:
        """获取优化器统计信息。"""
        return {
            'threshold': self.threshold,
            'max_iter': self.max_iter,
            'max_singular_values': self.max_singular_values,
            'cache_enabled': self.cache_enabled,
            'cache_size': len(self._svd_cache),
            'cache_max_size': self.cache_max_size,
            'counters': self._counters.copy(),
        }

    def clear_cache(self):
        """清空缓存。"""
        self._svd_cache.clear()
        logger.info("SVD 缓存已清空")


# ============================================================
# 便捷函数
# ============================================================

def create_optimizer(
    threshold: float = 0.9,
    max_iter: int = 100,
    cache_enabled: bool = True
) -> SparseSVDOptimizer:
    """
    创建稀疏 SVD 优化器实例。

    Args:
        threshold: 稀疏度阈值
        max_iter: 最大迭代次数
        cache_enabled: 是否启用缓存

    Returns:
        SparseSVDOptimizer 实例
    """
    return SparseSVDOptimizer(
        threshold=threshold,
        max_iter=max_iter,
        cache_enabled=cache_enabled
    )


def quick_svd(
    A: 'Matrix',
    threshold: float = 0.9,
    max_iter: int = 100
) -> Tuple['Matrix', 'Matrix', 'Matrix']:
    """
    快速 SVD 分解（便捷函数）。

    Args:
        A: 输入矩阵
        threshold: 稀疏度阈值
        max_iter: 最大迭代次数

    Returns:
        (U, S, Vt) 元组
    """
    optimizer = SparseSVDOptimizer(threshold=threshold, max_iter=max_iter)
    result = optimizer.svd(A)
    return result.U, result.S, result.Vt
