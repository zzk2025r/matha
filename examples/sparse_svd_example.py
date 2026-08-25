# -*- coding: utf-8 -*-
"""Matha v4.4 — SparseSVDOptimizer 使用示例

本脚本演示 SparseSVDOptimizer 类的实际使用效果。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from src.optimization.sparse_svd import SparseSVDOptimizer
from src.stdlib.linear_algebra import Matrix
import random


def main():
    """运行示例。"""
    print("\n" + "=" * 70)
    print("  Matha v4.4 SparseSVDOptimizer 使用示例")
    print("=" * 70)

    # 创建优化器
    optimizer = SparseSVDOptimizer(
        threshold=0.9,
        max_iter=50,
        cache_enabled=True
    )
    print(f"\n优化器配置: threshold={optimizer.threshold}, max_iter={optimizer.max_iter}")

    # 创建稀疏矩阵
    print("\n【1. 创建稀疏矩阵】")
    random.seed(42)
    n = 30
    data = [[0.0] * n for _ in range(n)]
    num_nonzero = int(n * n * 0.1)  # 10% 非零元素
    indices = list(range(n * n))
    random.shuffle(indices)
    for idx in indices[:num_nonzero]:
        i = idx // n
        j = idx % n
        data[i][j] = random.uniform(-1, 1)

    A = Matrix(data)
    sparsity = optimizer._get_sparsity(A)
    print(f"  矩阵规模: {n}x{n}")
    print(f"  非零元素: {num_nonzero}")
    print(f"  稀疏度: {sparsity:.2%}")
    print(f"  稀疏检测: {'稀疏' if optimizer.is_sparse(A) else '稠密'}")

    # 执行稀疏 SVD
    print("\n【2. 执行稀疏 SVD】")
    result = optimizer.svd(A, use_numpy=False)
    print(f"  算法: {result.method}")
    print(f"  耗时: {result.computation_time_ms:.2f} ms")
    print(f"  奇异值(前5): {[round(result.S.data[i][i], 4) for i in range(min(5, n))]}")

    # 缓存效果
    print("\n【3. 缓存效果】")
    result2 = optimizer.svd(A, use_numpy=False)
    print(f"  第一次耗时: {result.computation_time_ms:.2f} ms")
    print(f"  第二次耗时: {result2.computation_time_ms:.2f} ms (缓存命中)")
    print(f"  缓存大小: {len(optimizer._svd_cache)}")

    # 性能预测
    print("\n【4. 性能预测 (1000x1000)】")
    prediction = optimizer.predict_large_matrix_time(
        base_size=50,
        base_time_ms=1908.38,
        target_size=1000,
        sparsity=0.95
    )
    print(f"  基准: 50x50 矩阵, 1908.38 ms")
    print(f"  目标: 1000x1000 矩阵")
    print(f"  稀疏度: {prediction['sparsity']:.0%}")
    print(f"  稀疏加速因子: {prediction['sparse_speedup']:.1f}x")
    print(f"  预测纯 Python: {prediction['predicted_standard_time_ms']:.1f} ms ({prediction['predicted_standard_time_sec']:.1f} s)")
    print(f"  预测稀疏 SVD: {prediction['predicted_sparse_time_ms']:.1f} ms ({prediction['predicted_sparse_time_sec']:.1f} s)")
    print(f"  预测加速比: {prediction['predicted_standard_time_ms'] / prediction['predicted_sparse_time_ms']:.1f}x")

    # 批量 SVD
    print("\n【5. 批量 SVD】")
    matrices = [Matrix([[random.uniform(-1, 1) if random.random() > 0.9 else 0.0 for _ in range(20)] for _ in range(20)]) for _ in range(4)]
    results = optimizer.batch_svd(matrices, use_numpy=False)
    print(f"  处理矩阵数: {len(results)}")
    for i, r in enumerate(results):
        print(f"    矩阵 {i+1}: 方法={r.method}, 耗时={r.computation_time_ms:.2f}ms")

    # 统计信息
    print("\n【6. 优化器统计】")
    stats = optimizer.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("  示例完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
