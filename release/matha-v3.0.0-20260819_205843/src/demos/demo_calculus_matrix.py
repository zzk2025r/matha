# -*- coding: utf-8 -*-
"""Matha v4.4 — 符号微积分与矩阵运算整合演示

本脚本演示如何同时使用符号微积分和矩阵运算模块。

功能：
  1. 符号求导 + 矩阵计算
  2. 符号积分 + 数值积分验证
  3. 泰勒展开 + 多项式拟合
  4. 极限计算 + 收敛性分析
  5. 微分方程 + 数值解验证
  6. 综合应用：矩阵微积分

用法：
  python src/demos/demo_calculus_matrix.py                          # 运行全部
  python src/demos/demo_calculus_matrix.py --mode derivative        # 仅求导
  python src/demos/demo_calculus_matrix.py --mode integral          # 仅积分
  python src/demos/demo_calculus_matrix.py --mode matrix            # 仅矩阵
  python src/demos/demo_calculus_matrix.py --verbose                # 详细日志（DEBUG 级别）
  python src/demos/demo_calculus_matrix.py --expr "x**2"            # 自定义表达式
  python src/demos/demo_calculus_matrix.py --parallel               # 并行计算
"""
import math
import sys
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent  # src/demos -> src -> project root
sys.path.insert(0, str(_project_root))

# 设置日志（INFO 级别，--verbose 时启用 DEBUG）
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """设置日志级别。默认 INFO，--verbose 时启用 DEBUG。"""
    level = logging.DEBUG if verbose else logging.INFO
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


def print_result(label: str, value):
    """打印结果。"""
    if isinstance(value, float):
        print(f"  {label}: {value:.6f}")
    else:
        print(f"  {label}: {value}")


# ============================================================
# 并行计算工具
# ============================================================

def parallel_map(func, items, max_workers: int = 4):
    """并行映射。"""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func, item): item for item in items}
        for future in as_completed(futures):
            results.append(future.result())
    return results


# ============================================================
# 1. 符号求导 + 矩阵计算
# ============================================================

def demo1_derivative_matrix(expr: str = "x**3 + 2*x**2 + 3*x + 1"):
    """演示1：符号求导与矩阵运算结合。"""
    print_section("1. 符号求导 + 矩阵计算")

    # 符号求导
    from src.stdlib.calculus_symbolic import symbolic_derivative

    logger.debug(f"[求导] 开始符号求导: expr={expr}")
    derivative = symbolic_derivative(expr)
    logger.info(f"[求导] 符号求导完成: f'(x) = {derivative}")
    print(f"\n  原函数: f(x) = {expr}")
    print(f"  导数:   f'(x) = {derivative}")

    # 矩阵计算：用矩阵形式表示多项式系数
    from src.stdlib.linear_algebra import Matrix

    # 系数矩阵 [a_n, a_{n-1}, ..., a_1, a_0]
    coeffs = Matrix([[1, 2, 3, 1]])  # x^3 + 2x^2 + 3x + 1
    logger.debug(f"[求导] 系数矩阵创建: {coeffs}")
    print(f"\n  系数矩阵: {coeffs}")

    # 对系数进行矩阵运算（微分算子）
    n = len(coeffs.data[0])
    logger.debug(f"[求导] 计算导数系数: n={n}")
    derivative_coeffs = [[(n - 1 - i) * coeffs.data[0][i] for i in range(n - 1)]]
    deriv_matrix = Matrix(derivative_coeffs)
    logger.info(f"[求导] 导数系数矩阵: {deriv_matrix}")
    print(f"  导数系数: {deriv_matrix}")

    # 验证：在 x=2 处求值
    x = 2
    f_x = x**3 + 2*x**2 + 3*x + 1
    f_prime_x = 3*x**2 + 4*x + 3
    logger.debug(f"[求导] 验证求值: x={x}, f(x)={f_x}, f'(x)={f_prime_x}")
    print(f"\n  验证:")
    print(f"    f(2) = {f_x}")
    print(f"    f'(2) = {f_prime_x}")


# ============================================================
# 2. 符号积分 + 数值验证
# ============================================================

def demo2_integral_verification(expr: str = "x**2"):
    """演示2：符号积分与数值验证。"""
    print_section("2. 符号积分 + 数值验证")

    from src.stdlib.calculus_symbolic import symbolic_integral, definite_integral

    # 符号积分
    logger.debug(f"[积分] 开始符号积分: expr={expr}")
    integral = symbolic_integral(expr)
    logger.info(f"[积分] 符号积分完成: F(x) = {integral}")
    print(f"\n  原函数: f(x) = {expr}")
    print(f"  不定积分: F(x) = {integral}")

    # 定积分
    logger.debug(f"[积分] 开始定积分计算: ∫[0,1] {expr}dx")
    result = definite_integral(expr, "x", 0, 1)
    logger.info(f"[积分] 定积分计算完成: ∫[0,1] {expr}dx = {result:.6f}")
    print(f"  定积分: ∫[0,1] {expr}dx = {result:.6f}")

    # 数值验证（辛普森法则）
    n = 1000
    h = 1.0 / n
    simpson_sum = 0.0
    for i in range(n + 1):
        x = i * h
        if i == 0 or i == n:
            simpson_sum += x**2
        elif i % 2 == 1:
            simpson_sum += 4 * x**2
        else:
            simpson_sum += 2 * x**2
    simpson_result = (h / 3) * simpson_sum
    logger.debug(f"[积分] 辛普森数值积分: n={n}, 结果={simpson_result:.6f}")
    print(f"  数值验证（辛普森）: {simpson_result:.6f}")

    # 误差分析
    error = abs(result - simpson_result)
    logger.info(f"[积分] 误差分析: 符号积分={result:.6f}, 数值积分={simpson_result:.6f}, 误差={error:.2e}")
    print(f"  误差: {error:.2e}")


# ============================================================
# 3. 泰勒展开 + 矩阵拟合
# ============================================================

def demo3_taylor_matrix():
    """演示3：泰勒展开与矩阵拟合。"""
    print_section("3. 泰勒展开 + 矩阵拟合")

    from src.stdlib.calculus_symbolic import taylor_series

    # 泰勒展开
    expr = "exp(x)"
    logger.debug(f"[泰勒] 开始泰勒展开: expr={expr}, order=4")
    taylor = taylor_series(expr, "x", 0, 4)
    logger.info(f"[泰勒] 泰勒展开完成: T₄(x) = {taylor}")
    print(f"\n  原函数: f(x) = {expr}")
    print(f"  泰勒展开: T₄(x) = {taylor}")

    # 用矩阵形式表示泰勒系数
    # T₄(x) = 1 + x + x²/2 + x³/6 + x⁴/24
    coeffs = [1, 1, 0.5, 1/6, 1/24]
    logger.debug(f"[泰勒] 泰勒系数: {coeffs}")
    print(f"  泰勒系数: {coeffs}")

    # 用 Vandermonde 矩阵验证在特定点的值
    x_vals = [0.0, 0.5, 1.0]
    print(f"\n  数值验证:")
    for x in x_vals:
        # 泰勒近似
        taylor_val = sum(c * x**i for i, c in enumerate(coeffs))
        # 真实值
        true_val = math.exp(x)
        error = abs(taylor_val - true_val)
        logger.debug(f"[泰勒] 泰勒近似验证: x={x}, T₄({x})={taylor_val:.6f}, e^x={true_val:.6f}, 误差={error:.2e}")
        print(f"    x={x:.1f}: T₄({x})={taylor_val:.6f}, e^x={true_val:.6f}, 误差={error:.2e}")


# ============================================================
# 4. 极限计算 + 收敛性分析
# ============================================================

def demo4_limit_convergence():
    """演示4：极限计算与收敛性分析。"""
    print_section("4. 极限计算 + 收敛性分析")

    from src.stdlib.calculus_symbolic import limit

    # 经典极限
    print("\n  经典极限验证:")

    logger.debug("[极限] 计算 lim(x→0) sin(x)/x")
    result1 = limit('sin(x)/x', 'x', 0)
    logger.info(f"[极限] 极限计算完成: lim(x→0) sin(x)/x = {result1:.6f}")
    print(f"    lim(x→0) sin(x)/x = {result1:.6f}")

    logger.debug("[极限] 计算 lim(x→0) (1-cos(x))/x")
    result2 = limit('(1-cos(x))/x', 'x', 0)
    logger.info(f"[极限] 极限计算完成: lim(x→0) (1-cos(x))/x = {result2:.6f}")
    print(f"    lim(x→0) (1-cos(x))/x = {result2:.6f}")

    logger.debug("[极限] 计算 lim(x→∞) (1+1/x)^x")
    result3 = limit('(1+1/x)^x', 'x', float('inf'))
    logger.info(f"[极限] 极限计算完成: lim(x→∞) (1+1/x)^x = {result3:.6f}")
    print(f"    lim(x→∞) (1+1/x)^x = {result3:.6f}")

    # 数值验证收敛性
    print("\n  数值验证: (1+1/n)^n → e")
    n_values = [10, 100, 1000, 10000]
    for n in n_values:
        approx = (1 + 1/n)**n
        error = abs(approx - math.e)
        logger.debug(f"[极限] 收敛性验证: n={n}, (1+1/n)^n={approx:.10f}, 误差={error:.2e}")
        print(f"    n={n:5d}: (1+1/{n})^{n} = {approx:.10f}, 误差={error:.2e}")


# ============================================================
# 5. 微分方程 + 矩阵求解
# ============================================================

def demo5_ode_matrix():
    """演示5：微分方程与矩阵求解。"""
    print_section("5. 微分方程 + 矩阵求解")

    from src.stdlib.calculus_symbolic import symbolic_derivative
    from src.stdlib.linear_algebra import Matrix, matrix_inverse

    # 微分方程: y' = 2x, y(0) = 0
    # 解析解: y = x²
    print("\n  微分方程: y' = 2x, y(0) = 0")

    # 符号验证
    y = "x**2"
    logger.debug(f"[ODE] 符号验证: 解析解 y = {y}")
    y_prime = symbolic_derivative(y)
    logger.info(f"[ODE] 符号验证完成: y' = {y_prime}")
    print(f"  解析解: y = {y}")
    print(f"  导数:   y' = {y_prime}")

    # 用矩阵方法验证：将微分方程离散化
    # 在 x = [0, 0.1, 0.2, ..., 1.0] 处验证
    x_vals = [i * 0.1 for i in range(11)]
    y_vals = [x**2 for x in x_vals]

    print(f"\n  数值验证:")
    print(f"    {'x':>6s} | {'y=x²':>10s} | {'y\'=2x':>10s}")
    print(f"    {'-'*6}-+{'-'*10}-+{'-'*10}")
    for x in x_vals:
        y = x**2
        y_prime = 2*x
        logger.debug(f"[ODE] 数值验证: x={x:.2f}, y={y:.6f}, y'={y_prime:.6f}")
        print(f"    {x:6.2f} | {y:10.6f} | {y_prime:10.6f}")


# ============================================================
# 6. 综合应用：矩阵微积分
# ============================================================

def demo6_matrix_calculus(use_numpy: bool = True, parallel: bool = False, n_workers: int = 4, use_sparse: bool = False):
    """演示6：矩阵微积分综合应用。"""
    print_section("6. 矩阵微积分综合应用")

    from src.stdlib.calculus_symbolic import symbolic_derivative, symbolic_integral
    from src.stdlib.linear_algebra import Matrix, matrix_determinant, matrix_trace, svd_decompose

    # 矩阵函数求导
    print("\n  矩阵函数性质:")

    # 创建矩阵
    A = Matrix([[1, 2], [3, 4]])
    B = Matrix([[5, 6], [7, 8]])

    logger.debug(f"[矩阵] 创建矩阵 A: {A}")
    logger.debug(f"[矩阵] 创建矩阵 B: {B}")
    print(f"\n  矩阵 A =\n{A}")
    print(f"\n  矩阵 B =\n{B}")

    # 矩阵运算
    C = A + B
    D = A * B
    logger.info(f"[矩阵] 矩阵加法完成: A + B =\n{C}")
    logger.info(f"[矩阵] 矩阵乘法完成: A × B =\n{D}")
    print(f"\n  A + B =\n{C}")
    print(f"\n  A × B =\n{D}")

    # 矩阵性质
    det_A = matrix_determinant(A)
    tr_A = matrix_trace(A)
    logger.info(f"[矩阵] 矩阵性质: det(A) = {det_A}, tr(A) = {tr_A}")
    print(f"\n  det(A) = {det_A}")
    print(f"  tr(A) = {tr_A}")

    # 符号微积分与矩阵结合：矩阵元素的函数求导
    print(f"\n  矩阵函数 f(A) = A² 的导数:")
    A2 = A * A
    logger.debug(f"[矩阵] A² =\n{A2}")
    print(f"    A² =\n{A2}")

    # 使用符号微积分验证：d/dx(x²) = 2x
    derivative = symbolic_derivative("x**2")
    logger.info(f"[矩阵] 符号验证: d/dx(x²) = {derivative}")
    print(f"\n  符号验证: d/dx(x²) = {derivative}")

    # SVD 分解（优先使用 NumPy）
    print(f"\n  SVD 分解:")
    if use_numpy:
        try:
            import numpy as np
            A_np = np.array(A.data, dtype=float)
            U_np, s_np, Vt_np = np.linalg.svd(A_np)
            logger.info(f"[SVD] NumPy SVD: U={U_np.shape}, s={s_np.shape}, Vt={Vt_np.shape}")
            print(f"    NumPy SVD:")
            print(f"      奇异值: {s_np}")
            print(f"      U =\n{U_np}")
            print(f"      Vt =\n{Vt_np}")
        except ImportError:
            logger.warning("NumPy 未安装，使用 Matha SVD")
            U, S, Vt = svd_decompose(A)
            logger.info(f"[SVD] Matha SVD 完成: {A.shape}")
            print(f"    Matha SVD:")
            print(f"      S =\n{S}")
            print(f"      U =\n{U}")
            print(f"      Vt =\n{Vt}")
    else:
        U, S, Vt = svd_decompose(A)
        logger.info(f"[SVD] Matha SVD 完成: {A.shape}")
        print(f"    Matha SVD:")
        print(f"      S =\n{S}")
        print(f"      U =\n{U}")
        print(f"      Vt =\n{Vt}")

    # 并行计算演示：大规模矩阵运算
    if parallel:
        print(f"\n  并行计算演示:")
        matrices = [Matrix.random(50, 50) for _ in range(8)]
        logger.debug(f"[并行] 创建 {len(matrices)} 个 50x50 随机矩阵")

        # 检测稀疏矩阵并分类
        from src.stdlib.linear_algebra import _is_sparse_matrix
        sparse_count = sum(1 for M in matrices if _is_sparse_matrix(M, threshold=0.9))
        dense_count = len(matrices) - sparse_count
        logger.info(f"[并行] 矩阵分类: {sparse_count} 个稀疏, {dense_count} 个稠密")
        print(f"    矩阵分类: {sparse_count} 个稀疏, {dense_count} 个稠密")

        def process_matrix(M):
            # 根据稀疏性选择优化方法
            is_sparse = _is_sparse_matrix(M, threshold=0.9)
            if is_sparse:
                det = matrix_determinant(M)
                tr = matrix_trace(M)
                return det, tr, "sparse"
            else:
                det = matrix_determinant(M)
                tr = matrix_trace(M)
                return det, tr, "dense"

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = [executor.submit(process_matrix, M) for M in matrices]
            results = [f.result() for f in as_completed(futures)]

        logger.info(f"[并行] 并行计算完成: {len(results)} 个矩阵")
        print(f"    并行处理 {len(matrices)} 个 50x50 矩阵:")
        for i, (det, tr, mat_type) in enumerate(results[:4]):
            logger.debug(f"[并行] 矩阵 {i+1}: det={det:.4f}, tr={tr:.4f}, 类型={mat_type}")
            print(f"      矩阵 {i+1}: det={det:.4f}, tr={tr:.4f} ({mat_type})")

    # 稀疏矩阵 SVD 演示
    if use_sparse:
        print(f"\n  稀疏矩阵 SVD 演示:")
        import random
        random.seed(42)

        # 创建高稀疏度矩阵（90% 为零）
        sparse_data = [[0.0] * 20 for _ in range(20)]
        non_zero_count = 0
        for i in range(20):
            for j in range(20):
                if non_zero_count < 40:  # 40/400 = 10% 非零，90% 零
                    sparse_data[i][j] = random.uniform(-1, 1)
                    non_zero_count += 1

        A_sparse = Matrix(sparse_data)
        from src.stdlib.linear_algebra import _is_sparse_matrix, svd_decompose_sparse

        is_sparse = _is_sparse_matrix(A_sparse, threshold=0.9)
        logger.info(f"[稀疏] 矩阵稀疏度检测: {is_sparse}")
        print(f"    矩阵稀疏度: {'是' if is_sparse else '否'}（90% 元素为零）")

        if is_sparse:
            logger.info("[稀疏] 使用稀疏 SVD 优化")
            U, S, Vt = svd_decompose_sparse(A_sparse, max_iter=100)
            logger.info(f"[稀疏] 稀疏 SVD 完成: {A_sparse.shape}")
            print(f"    奇异值（前5）: {[round(S.data[i][i], 6) for i in range(min(5, A_sparse.rows))]}")
        else:
            logger.warning("[稀疏] 矩阵不够稀疏，使用标准 SVD")
            U, S, Vt = svd_decompose(A_sparse)
            logger.info(f"[稀疏] 标准 SVD 完成: {A_sparse.shape}")
            print(f"    奇异值（前5）: {[round(S.data[i][i], 6) for i in range(min(5, A_sparse.rows))]}")

        # 并行稀疏 SVD 演示
        if parallel:
            print(f"\n  并行稀疏 SVD 演示:")
            sparse_matrices_batch = []
            for k in range(4):
                random.seed(42 + k)
                data = [[0.0] * 20 for _ in range(20)]
                nz_count = 0
                for i in range(20):
                    for j in range(20):
                        if nz_count < 40:
                            data[i][j] = random.uniform(-1, 1)
                            nz_count += 1
                sparse_matrices_batch.append(Matrix(data))

            logger.debug(f"[并行稀疏] 创建 {len(sparse_matrices_batch)} 个稀疏矩阵")

            def process_sparse_svd(M):
                if _is_sparse_matrix(M, threshold=0.9):
                    U, S, Vt = svd_decompose_sparse(M, max_iter=100)
                    return S.data[0][0], "sparse"
                else:
                    U, S, Vt = svd_decompose(M)
                    return S.data[0][0], "dense"

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = [executor.submit(process_sparse_svd, M) for M in sparse_matrices_batch]
                results = [f.result() for f in as_completed(futures)]

            logger.info(f"[并行稀疏] 并行稀疏 SVD 完成: {len(results)} 个矩阵")
            print(f"    并行稀疏 SVD 结果:")
            for i, (sigma, mat_type) in enumerate(results):
                print(f"      矩阵 {i+1}: σ₁={sigma:.6f} ({mat_type})")

def main():
    """主函数。"""
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 符号微积分与矩阵运算整合演示")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出（DEBUG 级别）")
    parser.add_argument("--mode", "-m",
                       choices=["all", "derivative", "integral", "taylor", "limit", "ode", "matrix"],
                       default="all",
                       help="计算模式选择（默认: all）")
    parser.add_argument("--expr", "-e", default="x**3 + 2*x**2 + 3*x + 1",
                       help="表达式参数（默认: x**3 + 2*x**2 + 3*x + 1）")
    parser.add_argument("--no-numpy", action="store_true", help="禁用 NumPy（使用纯 Python 实现）")
    parser.add_argument("--parallel", action="store_true", help="启用并行计算")
    parser.add_argument("--workers", "-w", type=int, default=4, help="并行工作线程数（默认: 4）")
    parser.add_argument("--sparse", action="store_true", help="启用稀疏矩阵 SVD 优化")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("  Matha v4.4 符号微积分与矩阵运算整合演示")
    print("=" * 60)

    # 检查 SymPy 可用性
    try:
        from src.stdlib import calculus_symbolic
        sympy_available = calculus_symbolic.HAS_SYMPY
    except ImportError as e:
        sympy_available = False
        logger.warning(f"导入 calculus_symbolic 失败: {e}")

    # 检查 NumPy 可用性
    try:
        import numpy as np
        numpy_available = not args.no_numpy
    except ImportError:
        numpy_available = False
        logger.warning("NumPy 未安装，将使用纯 Python 实现")

    print(f"\nPython: {sys.version.split()[0]}")
    print(f"SymPy:  {'可用' if sympy_available else '不可用'}")
    print(f"NumPy:  {'可用' if numpy_available else '不可用'}")
    print(f"模式:   {args.mode}")
    print(f"表达式: {args.expr}")
    print(f"并行:   {'启用' if args.parallel else '禁用'} (workers={args.workers})")
    print(f"稀疏优化: {'启用' if args.sparse else '禁用'}")

    if not sympy_available:
        print("\n  ⚠️  SymPy 未安装，部分功能将跳过")
        print("  请运行: python install_dependencies.py --sympy")
        # 仅运行矩阵运算部分
        if args.mode in ("all", "matrix"):
            demo6_matrix_calculus(use_numpy=numpy_available,
                                 parallel=args.parallel, n_workers=args.workers)
        print("\n" + "=" * 60)
        print("  演示完成（仅矩阵部分）")
        print("=" * 60)
        return

    # 根据模式运行演示
    if args.mode in ("all", "derivative"):
        demo1_derivative_matrix(args.expr)
    if args.mode in ("all", "integral"):
        demo2_integral_verification(args.expr)
    if args.mode in ("all", "taylor"):
        demo3_taylor_matrix()
    if args.mode in ("all", "limit"):
        demo4_limit_convergence()
    if args.mode in ("all", "ode"):
        demo5_ode_matrix()
    if args.mode in ("all", "matrix"):
        demo6_matrix_calculus(use_numpy=numpy_available,
                             parallel=args.parallel, n_workers=args.workers,
                             use_sparse=args.sparse)

    print("\n" + "=" * 60)
    print("  演示完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
