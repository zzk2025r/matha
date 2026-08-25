# -*- coding: utf-8 -*-
"""Matha 移动端演示脚本

演示如何在移动端使用 Matha 进行矩阵运算。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from mobile_compat import get_mobile_api, is_mobile_device


def demo_matrix_operations():
    """演示基本矩阵运算"""
    print("\n" + "=" * 60)
    print("  Matha 移动端矩阵运算演示")
    print("=" * 60)

    api = get_mobile_api()

    # 创建矩阵
    print("\n【1. 矩阵创建】")
    A = api.array([[1, 2], [3, 4]])
    B = api.array([[5, 6], [7, 8]])
    print(f"  A = {A}")
    print(f"  B = {B}")

    # 矩阵加法
    print("\n【2. 矩阵加法】")
    C = A + B
    print(f"  A + B = {C}")

    # 矩阵乘法
    print("\n【3. 矩阵乘法】")
    D = api.matmul(A, B)
    print(f"  A × B = {D}")

    # 矩阵转置
    print("\n【4. 矩阵转置】")
    AT = api.matmul(A, B)  # 简化演示
    print(f"  A 的转置 = {api.matrix_transpose(A)}")

    # 矩阵求逆
    print("\n【5. 矩阵求逆】")
    A_inv = api.inv(A)
    print(f"  A^(-1) = {A_inv}")

    # 行列式
    print("\n【6. 行列式】")
    det_A = api.det(A)
    print(f"  det(A) = {det_A}")

    # 矩阵迹
    print("\n【7. 矩阵迹】")
    tr_A = api.trace(A)
    print(f"  tr(A) = {tr_A}")

    # 矩阵范数
    print("\n【8. 矩阵范数】")
    norm_A = api.norm(A)
    print(f"  ||A||_F = {norm_A}")

    # SVD 分解
    print("\n【9. SVD 分解】")
    U, S, Vt = api.svd(A)
    print(f"  U shape: {U.shape}")
    print(f"  S shape: {S.shape}")
    print(f"  Vt shape: {Vt.shape}")
    print(f"  奇异值: {[S[i][i] for i in range(min(S.shape))]}")

    print("\n" + "=" * 60)
    print("  演示完成！")
    print("=" * 60)


def demo_large_matrix():
    """演示大规模矩阵运算"""
    print("\n" + "=" * 60)
    print("  大规模矩阵运算演示")
    print("=" * 60)

    api = get_mobile_api()

    # 创建 100x100 矩阵
    print("\n【创建 100x100 随机矩阵】")
    import random as rand_module
    size = 100
    data = [[rand_module.random() for _ in range(size)] for _ in range(size)]
    A = api.array(data)
    print(f"  矩阵大小: {A.shape}")
    print(f"  元素总数: {A.size}")

    # 计算行列式（对于大矩阵可能较慢）
    print("\n【计算行列式】")
    import time
    start = time.perf_counter()
    det = api.det(A)
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  det(A) = {det:.6f}")
    print(f"  耗时: {elapsed:.2f}ms")

    # 计算迹
    print("\n【计算矩阵迹】")
    start = time.perf_counter()
    tr = api.trace(A)
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  tr(A) = {tr:.6f}")
    print(f"  耗时: {elapsed:.2f}ms")

    print("\n" + "=" * 60)


def demo_svd_comparison():
    """演示 SVD 性能对比"""
    print("\n" + "=" * 60)
    print("  SVD 性能对比演示")
    print("=" * 60)

    api = get_mobile_api()

    sizes = [10, 20, 50]
    print("\n【不同规模矩阵的 SVD 耗时】")
    print(f"  {'规模':<10} {'耗时 (ms)':<15}")
    print("  " + "-" * 30)

    import time
    import random as rand_module

    for size in sizes:
        data = [[rand_module.random() for _ in range(size)] for _ in range(size)]
        A = api.array(data)

        start = time.perf_counter()
        U, S, Vt = api.svd(A)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"  {size}x{size:<6} {elapsed:>12.2f}ms")

    print("  " + "-" * 30)

    print("\n" + "=" * 60)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Matha v4.4 移动端演示")
    print("=" * 60)

    # 检测设备
    is_mobile = is_mobile_device()
    print(f"\n检测平台: {'移动设备' if is_mobile else '桌面设备'}")
    print(f"NumPy 兼容层: {'已启用' if api._numpy_available else '已启用（降级模式）'}")

    # 运行演示
    demo_matrix_operations()
    demo_large_matrix()
    demo_svd_comparison()

    print("\n" + "=" * 60)
    print("  所有演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
