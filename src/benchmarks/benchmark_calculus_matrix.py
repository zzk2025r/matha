# -*- coding: utf-8 -*-
"""Matha v4.4 — 符号微积分与矩阵运算性能基准测试

本脚本测试符号微积分和矩阵运算模块的性能。

功能：
  1. 符号求导性能基准
  2. 符号积分性能基准
  3. 矩阵乘法性能基准
  4. 矩阵分解性能基准
  5. 综合性能报告

用法：
  python src/benchmarks/benchmark_calculus_matrix.py
  python src/benchmarks/benchmark_calculus_matrix.py --verbose
"""
import time
import sys
import logging
import statistics
import importlib
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent  # src/benchmarks -> src -> project root
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

# 设置日志
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """设置日志级别。"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )


def print_section(title: str):
    """打印章节标题。"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def benchmark(func, iterations: int = 10, warmup: int = 3) -> dict:
    """性能基准测试。"""
    # 预热
    for _ in range(warmup):
        func()

    # 正式测试
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times),
        'std': statistics.stdev(times) if len(times) > 1 else 0,
        'total': sum(times),
        'iterations': iterations
    }


# ============================================================
# 符号微积分性能测试
# ============================================================

def benchmark_symbolic_derivative():
    """符号求导性能测试。"""
    from src.stdlib.calculus_symbolic import symbolic_derivative

    test_cases = [
        ("x**2", "x"),
        ("x**3 + 2*x**2 + 3*x + 1", "x"),
        ("sin(x)", "x"),
        ("cos(x)", "x"),
        ("exp(x)", "x"),
        ("exp(x)*cos(x)", "x"),
        ("log(x)", "x"),
        ("sqrt(x)", "x"),
    ]

    results = {}
    for expr, var in test_cases:
        func = lambda e=expr, v=var: symbolic_derivative(e, v)
        result = benchmark(func, iterations=20, warmup=5)
        results[expr] = result
        print(f"  {expr:30s}: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_symbolic_integral():
    """符号积分性能测试。"""
    from src.stdlib.calculus_symbolic import symbolic_integral

    test_cases = [
        ("x**2", "x"),
        ("x**3", "x"),
        ("sin(x)", "x"),
        ("cos(x)", "x"),
        ("exp(x)", "x"),
        ("1/x", "x"),
    ]

    results = {}
    for expr, var in test_cases:
        func = lambda e=expr, v=var: symbolic_integral(e, v)
        result = benchmark(func, iterations=20, warmup=5)
        results[expr] = result
        print(f"  {expr:30s}: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_definite_integral():
    """定积分性能测试。"""
    from src.stdlib.calculus_symbolic import definite_integral

    test_cases = [
        ("x**2", "x", 0, 1),
        ("sin(x)", "x", 0, 3.14159265),
        ("exp(x)", "x", 0, 1),
    ]

    results = {}
    for expr, var, lower, upper in test_cases:
        func = lambda e=expr, v=var, l=lower, u=upper: definite_integral(e, v, l, u)
        result = benchmark(func, iterations=20, warmup=5)
        results[expr] = result
        print(f"  {expr:30s}: {result['mean']*1000:.4f} ms (mean)")

    return results


# ============================================================
# 矩阵运算性能测试
# ============================================================

def benchmark_matrix_multiply():
    """矩阵乘法性能测试。"""
    from src.stdlib.linear_algebra import Matrix, matrix_multiply

    sizes = [(10, 10), (50, 50), (100, 100)]
    results = {}

    for n, m in sizes:
        A = Matrix.random(n, m)
        B = Matrix.random(m, n)
        func = lambda a=A, b=B: matrix_multiply(a, b)
        result = benchmark(func, iterations=50, warmup=10)
        results[f"{n}x{m}"] = result
        print(f"  {n}x{m} 矩阵乘法: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_matrix_determinant():
    """矩阵行列式性能测试。"""
    from src.stdlib.linear_algebra import Matrix, matrix_determinant

    sizes = [(10, 10), (50, 50), (100, 100)]
    results = {}

    for n, _ in sizes:
        A = Matrix.random(n, n)
        func = lambda a=A: matrix_determinant(a)
        result = benchmark(func, iterations=20, warmup=5)
        results[f"{n}x{n}"] = result
        print(f"  {n}x{n} 行列式: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_matrix_inverse():
    """矩阵求逆性能测试。"""
    from src.stdlib.linear_algebra import Matrix, matrix_inverse

    sizes = [(10, 10), (50, 50), (100, 100)]
    results = {}

    for n, _ in sizes:
        A = Matrix.random(n, n)
        # 确保矩阵非奇异
        A.data[0][0] += n  # 增加对角线元素
        func = lambda a=A: matrix_inverse(a)
        result = benchmark(func, iterations=20, warmup=5)
        results[f"{n}x{n}"] = result
        print(f"  {n}x{n} 求逆: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_matrix_eigenvalues():
    """特征值计算性能测试。"""
    from src.stdlib.linear_algebra import Matrix, matrix_eigenvalues

    sizes = [(10, 10), (50, 50)]
    results = {}

    for n, _ in sizes:
        A = Matrix.random(n, n)
        # 确保对称矩阵以获得实特征值
        for i in range(n):
            for j in range(i + 1, n):
                avg = (A.data[i][j] + A.data[j][i]) / 2
                A.data[i][j] = avg
                A.data[j][i] = avg
        func = lambda a=A: matrix_eigenvalues(a)
        result = benchmark(func, iterations=20, warmup=5)
        results[f"{n}x{n}"] = result
        print(f"  {n}x{n} 特征值: {result['mean']*1000:.4f} ms (mean)")

    return results


def benchmark_svd():
    """SVD 分解性能测试。"""
    from src.stdlib.linear_algebra import Matrix, svd_decompose

    sizes = [(10, 10), (50, 50)]
    results = {}

    for n, m in sizes:
        A = Matrix.random(n, m)
        func = lambda a=A: svd_decompose(a)
        result = benchmark(func, iterations=10, warmup=3)
        results[f"{n}x{m}"] = result
        print(f"  {n}x{m} SVD: {result['mean']*1000:.4f} ms (mean)")

    return results


# ============================================================
# 综合性能测试
# ============================================================

def benchmark_combined():
    """综合性能测试（符号微积分 + 矩阵运算）。"""
    from src.stdlib.calculus_symbolic import symbolic_derivative
    from src.stdlib.linear_algebra import Matrix, matrix_multiply

    def combined_task():
        # 符号求导
        derivative = symbolic_derivative("x**3 + 2*x**2 + 3*x + 1")
        # 矩阵运算
        A = Matrix([[1, 2], [3, 4]])
        B = Matrix([[5, 6], [7, 8]])
        C = matrix_multiply(A, B)
        return derivative, C

    result = benchmark(combined_task, iterations=20, warmup=5)
    print(f"  综合任务: {result['mean']*1000:.4f} ms (mean)")
    return result


# ============================================================
# 主程序
# ============================================================

def main():
    """主函数。"""
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 性能基准测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("  Matha v4.4 性能基准测试")
    print("=" * 60)

    # 检查 SymPy 可用性
    try:
        calculus_symbolic = importlib.import_module('src.stdlib.calculus_symbolic')
        sympy_available = calculus_symbolic.HAS_SYMPY
    except ImportError:
        sympy_available = False

    print(f"\nPython: {sys.version.split()[0]}")
    print(f"SymPy:  {'可用' if sympy_available else '不可用'}")

    all_results = {}

    # 符号微积分性能测试
    print_section("1. 符号微积分性能测试")
    if sympy_available:
        all_results['symbolic_derivative'] = benchmark_symbolic_derivative()
        all_results['symbolic_integral'] = benchmark_symbolic_integral()
        all_results['definite_integral'] = benchmark_definite_integral()
    else:
        print("  ⚠️  SymPy 未安装，跳过符号微积分测试")

    # 矩阵运算性能测试
    print_section("2. 矩阵运算性能测试")
    all_results['matrix_multiply'] = benchmark_matrix_multiply()
    all_results['matrix_determinant'] = benchmark_matrix_determinant()
    all_results['matrix_inverse'] = benchmark_matrix_inverse()
    all_results['matrix_eigenvalues'] = benchmark_matrix_eigenvalues()
    all_results['svd'] = benchmark_svd()

    # 综合性能测试
    print_section("3. 综合性能测试")
    all_results['combined'] = benchmark_combined()

    # 性能报告
    print_section("4. 性能报告")
    print("\n  符号微积分:")
    if 'symbolic_derivative' in all_results:
        for expr, result in all_results['symbolic_derivative'].items():
            print(f"    {expr:30s}: {result['mean']*1000:.4f} ms")

    print("\n  矩阵运算:")
    for name, result in all_results.get('matrix_multiply', {}).items():
        print(f"    {name:30s}: {result['mean']*1000:.4f} ms")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
