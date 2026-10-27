"""Matha v4.4 — 矩阵运算标准库

提供线性代数核心功能：
  - 矩阵创建与操作
  - 矩阵乘法、转置、逆矩阵
  - 行列式、迹、秩
  - 特征值与特征向量
  - SVD 分解
  - 矩阵范数

数学表达：
  所有函数遵循线性代数定义，确保数学严谨性。

用法：
  from src.stdlib.linear_algebra import (
      Matrix,
      matrix_multiply,
      matrix_transpose,
      matrix_inverse,
      matrix_determinant,
      matrix_eigenvalues,
      svd_decompose,
  )
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 缓存设置
# ============================================================

# 求逆缓存
_inverse_cache: dict = {}
_MAX_CACHE_SIZE = 1000

# SVD 缓存
_svd_cache: dict = {}

# 特征值缓存
_eigenvalue_cache: dict = {}


def _make_cache_key(A: Matrix) -> tuple:
    """创建缓存键。"""
    return tuple(tuple(row) for row in A.data)


def _evict_cache(cache: dict, max_size: int = _MAX_CACHE_SIZE):
    """缓存淘汰：当缓存过大时，移除最早插入的条目。"""
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))


# ============================================================
# 矩阵类
# ============================================================

@dataclass
class Matrix:
    """
    矩阵类：支持基本线性代数运算。

    数学表示：
      A = [a_ij] ∈ R^(m×n)

    用法：
      mat = Matrix([[1, 2], [3, 4]])
      result = mat.multiply(Matrix([[5, 6], [7, 8]]))
    """

    data: list[list[float]] = field(default_factory=list)
    _rows: int = 0
    _cols: int = 0

    def __post_init__(self):
        """初始化矩阵属性。"""
        if self.data:
            self._rows = len(self.data)
            self._cols = len(self.data[0]) if self._rows > 0 else 0
            # 验证矩形矩阵
            for row in self.data:
                if len(row) != self._cols:
                    raise ValueError("矩阵行数不一致")

    @classmethod
    def zeros(cls, rows: int, cols: int) -> Matrix:
        """创建零矩阵。"""
        return cls([[0.0] * cols for _ in range(rows)])

    @classmethod
    def ones(cls, rows: int, cols: int) -> Matrix:
        """创建全一矩阵。"""
        return cls([[1.0] * cols for _ in range(rows)])

    @classmethod
    def identity(cls, n: int) -> Matrix:
        """创建单位矩阵。"""
        data = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        return cls(data)

    @classmethod
    def random(cls, rows: int, cols: int, scale: float = 1.0) -> Matrix:
        """创建随机矩阵。"""
        import random
        data = [[random.uniform(-scale, scale) for _ in range(cols)] for _ in range(rows)]
        return cls(data)

    @property
    def rows(self) -> int:
        """返回行数。"""
        return self._rows

    @property
    def cols(self) -> int:
        """返回列数。"""
        return self._cols

    @property
    def shape(self) -> tuple[int, int]:
        """返回矩阵形状。"""
        return (self._rows, self._cols)

    def __repr__(self) -> str:
        """返回矩阵的字符串表示。"""
        return f"Matrix({self.data})"

    def __str__(self) -> str:
        """返回矩阵的可读字符串。"""
        lines = []
        for row in self.data:
            lines.append("  [" + ", ".join(f"{v:8.4f}" for v in row) + "]")
        return "\n".join(lines)

    def __add__(self, other: Matrix) -> Matrix:
        """矩阵加法。"""
        if self.shape != other.shape:
            raise ValueError("矩阵维度不匹配")
        data = [[self.data[i][j] + other.data[i][j] for j in range(self._cols)] for i in range(self._rows)]
        return Matrix(data)

    def __sub__(self, other: Matrix) -> Matrix:
        """矩阵减法。"""
        if self.shape != other.shape:
            raise ValueError("矩阵维度不匹配")
        data = [[self.data[i][j] - other.data[i][j] for j in range(self._cols)] for i in range(self._rows)]
        return Matrix(data)

    def __mul__(self, other: Matrix | float) -> Matrix:
        """矩阵乘法或数乘。"""
        if isinstance(other, (int, float)):
            data = [[self.data[i][j] * other for j in range(self._cols)] for i in range(self._rows)]
            return Matrix(data)
        elif isinstance(other, Matrix):
            return matrix_multiply(self, other)
        else:
            raise TypeError("只能与 Matrix 或标量相乘")

    def __rmul__(self, other: float) -> Matrix:
        """标量左乘。"""
        return self.__mul__(other)

    def __eq__(self, other: object) -> bool:
        """矩阵相等比较。"""
        if not isinstance(other, Matrix):
            return False
        if self.shape != other.shape:
            return False
        return all(abs(self.data[i][j] - other.data[i][j]) < 1e-10
                   for i in range(self._rows) for j in range(self._cols))


# ============================================================
# 基本矩阵运算
# ============================================================

def matrix_multiply(A: Matrix, B: Matrix) -> Matrix:
    """
    矩阵乘法：C = A × B

    数学定义：
      c_ij = Σ_k a_ik * b_kj

    Args:
        A: m×n 矩阵
        B: n×p 矩阵

    Returns:
        C: m×p 矩阵

    Raises:
        ValueError: 维度不匹配
    """
    if A.cols != B.rows:
        raise ValueError(f"矩阵维度不匹配: {A.shape} × {B.shape}")

    logger.info(f"开始矩阵乘法: {A.shape} × {B.shape}")
    start_time = time.perf_counter()

    result = [[0.0] * B.cols for _ in range(A.rows)]
    for i in range(A.rows):
        for j in range(B.cols):
            for k in range(A.cols):
                result[i][j] += A.data[i][k] * B.data[k][j]

    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(f"矩阵乘法完成: {A.shape} × {B.shape} → {A.rows}×{B.cols}, 耗时={elapsed:.2f}ms")
    return Matrix(result)


def matrix_transpose(A: Matrix) -> Matrix:
    """
    矩阵转置：A^T

    数学定义：
      (A^T)_ij = A_ji

    Args:
        A: m×n 矩阵

    Returns:
        A^T: n×m 矩阵
    """
    data = [[A.data[j][i] for j in range(A.rows)] for i in range(A.cols)]
    return Matrix(data)


def matrix_scale(A: Matrix, scalar: float) -> Matrix:
    """
    矩阵数乘：c × A

    Args:
        A: 矩阵
        scalar: 标量

    Returns:
        c × A
    """
    data = [[A.data[i][j] * scalar for j in range(A.cols)] for i in range(A.rows)]
    return Matrix(data)


def matrix_add(A: Matrix, B: Matrix) -> Matrix:
    """
    矩阵加法：A + B

    Args:
        A: m×n 矩阵
        B: m×n 矩阵

    Returns:
        A + B
    """
    return A + B


def matrix_subtract(A: Matrix, B: Matrix) -> Matrix:
    """
    矩阵减法：A - B

    Args:
        A: m×n 矩阵
        B: m×n 矩阵

    Returns:
        A - B
    """
    return A - B


# ============================================================
# 矩阵性质
# ============================================================

def matrix_determinant(A: Matrix) -> float:
    """
    矩阵行列式：det(A)

    数学定义：
      det(A) = Σ (-1)^(i+j) * a_ij * M_ij

    Args:
        A: n×n 方阵

    Returns:
        行列式值

    Raises:
        ValueError: 非方阵
    """
    if A.rows != A.cols:
        logger.error(f"行列式仅对方阵定义，当前矩阵形状: {A.shape}")
        raise ValueError("行列式仅对方阵定义")

    logger.debug(f"开始计算行列式: A={A.shape}")
    n = A.rows

    # 使用递归展开（适用于小矩阵）
    if n == 1:
        result = A.data[0][0]
        logger.debug(f"1x1 矩阵行列式: {result}")
        return result
    if n == 2:
        result = A.data[0][0] * A.data[1][1] - A.data[0][1] * A.data[1][0]
        logger.debug(f"2x2 矩阵行列式: {result}")
        return result

    # 高斯消元法计算行列式
    mat = [row[:] for row in A.data]
    det = 1.0
    logger.debug(f"使用高斯消元法计算 {n}x{n} 矩阵行列式")

    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(mat[row][col]) > abs(mat[max_row][col]):
                max_row = row

        if abs(mat[max_row][col]) < 1e-12:
            logger.warning(f"矩阵在第 {col} 列奇异，行列式为 0")
            return 0.0

        # 交换行
        if max_row != col:
            mat[col], mat[max_row] = mat[max_row], mat[col]
            det *= -1

        det *= mat[col][col]

        # 消元
        for row in range(col + 1, n):
            factor = mat[row][col] / mat[col][col]
            for j in range(col, n):
                mat[row][j] -= factor * mat[col][j]

    logger.info(f"行列式计算完成: det(A) = {det}")
    return det


def matrix_trace(A: Matrix) -> float:
    """
    矩阵迹：tr(A) = Σ a_ii

    Args:
        A: n×n 方阵

    Returns:
        迹
    """
    if A.rows != A.cols:
        raise ValueError("迹仅对方阵定义")

    return sum(A.data[i][i] for i in range(A.rows))


def matrix_rank(A: Matrix) -> int:
    """
    矩阵秩：rank(A)

    数学定义：
      rank(A) = 最大线性无关行（列）数

    Args:
        A: m×n 矩阵

    Returns:
        秩
    """
    # 高斯消元求秩
    mat = [row[:] for row in A.data]
    rows, cols = A.rows, A.cols
    rank = 0

    for col in range(cols):
        # 找主元
        max_row = rank
        for row in range(rank + 1, rows):
            if abs(mat[row][col]) > abs(mat[max_row][col]):
                max_row = row

        if abs(mat[max_row][col]) < 1e-12:
            continue

        # 交换行
        mat[rank], mat[max_row] = mat[max_row], mat[rank]

        # 消元
        pivot = mat[rank][col]
        for j in range(cols):
            mat[rank][j] /= pivot

        for row in range(rows):
            if row != rank:
                factor = mat[row][col]
                for j in range(cols):
                    mat[row][j] -= factor * mat[rank][j]

        rank += 1

    return rank


def matrix_norm(A: Matrix, ord: str | None = None) -> float:
    """
    矩阵范数

    支持的范数：
      - 'fro': Frobenius 范数
      - 'inf': 无穷范数（行和最大值）
      - '1': 1-范数（列和最大值）
      - None: Frobenius 范数（默认）

    Args:
        A: m×n 矩阵
        ord: 范数类型

    Returns:
        范数值
    """
    if ord == 'fro' or ord is None:
        # Frobenius 范数
        return math.sqrt(sum(v**2 for row in A.data for v in row))
    elif ord == 'inf':
        # 无穷范数
        return max(sum(abs(v) for v in row) for row in A.data)
    elif ord == 1:
        # 1-范数
        col_sums = [sum(abs(A.data[i][j]) for i in range(A.rows)) for j in range(A.cols)]
        return max(col_sums)
    else:
        raise ValueError(f"不支持的范数类型: {ord}")


# ============================================================
# 逆矩阵（带缓存）
# ============================================================

def matrix_inverse(A: Matrix) -> Matrix | None:
    """
    矩阵求逆：A^(-1)

    数学定义：
      A × A^(-1) = I

    Args:
        A: n×n 可逆方阵

    Returns:
        A^(-1)，不可逆时返回 None
    """
    if A.rows != A.cols:
        raise ValueError("逆矩阵仅对方阵定义")

    # 检查缓存
    cache_key = _make_cache_key(A)
    if cache_key in _inverse_cache:
        logger.debug(f"使用缓存的逆矩阵: {A.shape}")
        return _inverse_cache[cache_key]

    n = A.rows
    # 增广矩阵 [A | I]
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A.data)]

    # 高斯-约当消元
    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row

        if abs(aug[max_row][col]) < 1e-12:
            return None  # 矩阵奇异

        # 交换行
        aug[col], aug[max_row] = aug[max_row], aug[col]

        # 归一化
        pivot = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= pivot

        # 消元
        for row in range(n):
            if row != col:
                factor = aug[row][col]
                for j in range(2 * n):
                    aug[row][j] -= factor * aug[col][j]

    # 提取逆矩阵
    inv_data = [row[n:] for row in aug]
    result = Matrix(inv_data)

    # 存入缓存
    _inverse_cache[cache_key] = result
    _evict_cache(_inverse_cache)

    logger.info(f"逆矩阵计算完成: A^(-1) for {A.shape}")
    return result


# ============================================================
# 特征值与特征向量（带缓存）
# ============================================================

def matrix_eigenvalues(A: Matrix) -> list[complex]:
    """
    矩阵特征值：det(A - λI) = 0

    数学定义：
      A × v = λ × v

    Args:
        A: n×n 方阵

    Returns:
        特征值列表

    Note:
        使用 QR 算法近似计算，适用于中小型矩阵。
    """
    if A.rows != A.cols:
        raise ValueError("特征值仅对方阵定义")

    n = A.rows

    # 检查缓存
    cache_key = _make_cache_key(A)
    if cache_key in _eigenvalue_cache:
        logger.debug(f"使用缓存的特征值: {A.shape}")
        return _eigenvalue_cache[cache_key]

    # 使用幂迭代法求主特征值
    # 完整特征值分解由本模块 `_eigenvectors_with_values`（纯 Python  deflation）提供

    # 简化实现：特征多项式系数
    # 2x2 矩阵精确解
    if n == 2:
        a, b = A.data[0][0], A.data[0][1]
        c, d = A.data[1][0], A.data[1][1]
        trace = a + d
        det = a * d - b * c
        discriminant = trace**2 - 4 * det

        if discriminant >= 0:
            λ1 = (trace + math.sqrt(discriminant)) / 2
            λ2 = (trace - math.sqrt(discriminant)) / 2
            result = [λ1, λ2]
        else:
            real_part = trace / 2
            imag_part = math.sqrt(-discriminant) / 2
            result = [complex(real_part, imag_part), complex(real_part, -imag_part)]

        _eigenvalue_cache[cache_key] = result
        _evict_cache(_eigenvalue_cache)
        return result

    # 对于更大矩阵，使用 QR 算法
    result = _qr_eigenvalues(A)
    _eigenvalue_cache[cache_key] = result
    _evict_cache(_eigenvalue_cache)
    return result


def _qr_eigenvalues(A: Matrix) -> list[complex]:
    """
    QR 算法求特征值（简化版）。

    使用 Iterated QR 分解逼近特征值。
    """
    n = A.rows
    # 复制矩阵
    B = [row[:] for row in A.data]

    # QR 迭代
    for _ in range(100):  # 迭代次数
        # QR 分解（简化：Householder 反射）
        Q, R = _qr_decomposition(B)

        # 反乘
        B = [[sum(Q[i][k] * R[k][j] for k in range(n)) for j in range(n)] for i in range(n)]

    # 上三角矩阵的对角线元素即为特征值
    eigenvalues = [complex(B[i][i]) for i in range(n)]
    return eigenvalues


def _qr_decomposition(A: list[list[float]]) -> tuple[list[list[float]], list[list[float]]]:
    """
    QR 分解：A = QR

    使用 Gram-Schmidt 正交化。
    """
    n = len(A)
    # 复制矩阵
    Q = [[0.0] * n for _ in range(n)]
    R = [[0.0] * n for _ in range(n)]

    for j in range(n):
        # 复制第 j 列
        v = [A[i][j] for i in range(n)]

        # Gram-Schmidt 正交化
        for i in range(j):
            # 计算投影系数
            dot_product = sum(v[k] * Q[k][i] for k in range(n))
            R[i][j] = dot_product

            # 减去投影
            for k in range(n):
                v[k] -= dot_product * Q[k][i]

        # 归一化
        norm = math.sqrt(sum(x**2 for x in v))
        if norm > 1e-12:
            for i in range(n):
                Q[i][j] = v[i] / norm
            R[j][j] = norm
        else:
            R[j][j] = 0.0

    return Q, R


# ============================================================
# SVD 分解（带缓存，纯 Python 实现）
# ============================================================

def svd_decompose(A: Matrix) -> tuple[Matrix, Matrix, Matrix]:
    """
    SVD 分解：A = U Σ V^T

    数学定义：
      A = U × Σ × V^T

    Args:
        A: m×n 矩阵

    Returns:
        U: m×m 左奇异向量矩阵
        S: m×n 奇异值矩阵（对角线为奇异值）
        Vt: n×n V 的转置矩阵

    Note:
        实现为单侧 Jacobi（one-sided Jacobi）旋转，纯标准库、**确定性**
        （不依赖随机初值）；曾有的 NumPy 分支已移除（阶段 3：核心零第三方依赖）。
    """
    m, n = A.rows, A.cols

    # 检查缓存
    cache_key = _make_cache_key(A)
    if cache_key in _svd_cache:
        logger.debug(f"使用缓存的 SVD: {A.shape}")
        return _svd_cache[cache_key]

    result = _svd_jacobi(A)
    _svd_cache[cache_key] = result
    _evict_cache(_svd_cache)
    return result


def _is_sparse_matrix(A: Matrix, threshold: float = 0.9) -> bool:
    """
    检测矩阵是否为稀疏矩阵。

    Args:
        A: m×n 矩阵
        threshold: 稀疏度阈值（默认 0.9，即 90% 元素为零）

    Returns:
        如果是稀疏矩阵返回 True
    """
    total = A.rows * A.cols
    zero_count = sum(1 for row in A.data for v in row if abs(v) < 1e-10)
    sparsity = zero_count / total if total > 0 else 0
    return sparsity >= threshold


def svd_decompose_sparse(A: Matrix, max_iter: int = 100) -> tuple[Matrix, Matrix, Matrix]:
    """
    稀疏矩阵 SVD 分解（基于迭代法）。

    使用 Lanczos 迭代或幂迭代法，适用于稀疏矩阵。

    Args:
        A: m×n 稀疏矩阵
        max_iter: 最大迭代次数

    Returns:
        U: m×m 左奇异向量矩阵
        S: m×n 奇异值矩阵
        Vt: n×n V 的转置矩阵
    """
    m, n = A.rows, A.cols
    logger.debug(f"开始稀疏矩阵 SVD: {A.shape}, max_iter={max_iter}")

    # 使用改进的幂迭代法（Lanczos 风格）
    U = Matrix.zeros(m, m)
    Vt = Matrix.zeros(n, n)
    S = Matrix.zeros(m, n)

    # 预计算非零元素的行列索引（加速矩阵向量乘法）
    nonzero_elements = []
    for i in range(m):
        for j in range(n):
            if abs(A.data[i][j]) > 1e-10:
                nonzero_elements.append((i, j, A.data[i][j]))

    logger.debug(f"稀疏矩阵非零元素数: {len(nonzero_elements)}")

    # 幂迭代求前 k 个奇异值
    k = min(m, n, 10)  # 计算前 10 个奇异值
    phi = (math.sqrt(5.0) - 1.0) / 2.0

    def _seed_vector(offset: int) -> list[float]:
        """确定性初值（黄金比低差异序列），保证结果可重复对拍。"""
        return [(((j + 1 + offset * n) * phi) % 1.0) * 2.0 - 1.0 for j in range(n)]

    for p in range(k):
        v = _seed_vector(p)

        # 正交化（避免与已求得的奇异向量重复）
        for q in range(p):
            # v = v - (v^T * V_q) * V_q
            dot = sum(v[j] * Vt.data[q][j] for j in range(n))
            for j in range(n):
                v[j] -= dot * Vt.data[q][j]

        # 归一化
        norm = math.sqrt(sum(x**2 for x in v))
        if norm < 1e-12:
            v = _seed_vector(p + k)
            norm = math.sqrt(sum(x**2 for x in v))
        v = [x / norm for x in v]

        # 幂迭代：v <- 归一化(AᵗA v)，并对已求得的右奇异向量做 deflation
        for iteration in range(max_iter):
            # 稀疏矩阵向量乘法: Av
            Av = [0.0] * m
            for i, j, val in nonzero_elements:
                Av[i] += val * v[j]

            # A^T Av
            ATAv = [0.0] * n
            for i, j, val in nonzero_elements:
                ATAv[j] += val * Av[i]

            # 正交化
            for q in range(p):
                dot = sum(ATAv[j] * Vt.data[q][j] for j in range(n))
                for j in range(n):
                    ATAv[j] -= dot * Vt.data[q][j]

            # 归一化
            norm = math.sqrt(sum(x**2 for x in ATAv))
            if norm < 1e-12:
                break
            v = [x / norm for x in ATAv]

        # 收敛后重放一次 A·v：σ = ‖Av‖，u = Av/σ。
        # 旧实现在循环内把 u 归一化成单位向量、循环外又取 ‖u‖ 当 σ，于是
        # 每个奇异值恒等于 1.0 —— 那是实现 bug（不是迭代法的固有误差），
        # 会让 `svd_decompose_sparse` 的结果与主路完全不可比。
        Av = [0.0] * m
        for i, j, val in nonzero_elements:
            Av[i] += val * v[j]
        sigma = math.sqrt(sum(x * x for x in Av))
        if sigma > 1e-12:
            u = [x / sigma for x in Av]
            S.data[p][p] = sigma
            for i in range(m):
                U.data[i][p] = u[i]
            for j in range(n):
                Vt.data[p][j] = v[j]

    logger.info(f"稀疏矩阵 SVD 完成: {A.shape}, 计算了 {k} 个奇异值")
    return U, S, Vt


def _svd_jacobi(A: Matrix, *, max_sweeps: int = 60,
                tol: float = 1e-13) -> tuple[Matrix, Matrix, Matrix]:
    """单侧 Jacobi SVD：纯标准库、确定性、对任意 m×n 成立。

    算法：对 A 的列两两作 Givens 旋转（``B = A·V``），直到列彼此正交；此时

    - ``σ_k = ‖B[:,k]‖``，``U[:,k] = B[:,k]/σ_k``，``V[:,k]`` 已含在累计正交阵 V 中；
    - 收敛判据为非对角能量 ``Σ_{i<j}(b_i·b_j)²`` 落到 ``tol·‖B‖_F⁴`` 以下（量纲齐次）；
    - 零奇异值对应缺失的左奇异向量，由标准基 Gram-Schmidt 补全为正交完备基。

    因此 ``U·S·Vᵗ = A`` 与奇异值降序排列同时成立（不依赖随机初值）。
    """
    m, n = A.rows, A.cols
    B = [[float(A.data[r][c]) for c in range(n)] for r in range(m)]
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for _ in range(max_sweeps):
        fro2 = sum(x * x for row in B for x in row)
        off = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                alpha = sum(B[r][i] * B[r][i] for r in range(m))
                beta = sum(B[r][j] * B[r][j] for r in range(m))
                gamma = sum(B[r][i] * B[r][j] for r in range(m))
                off += gamma * gamma
                if abs(gamma) <= 1e-15 * alpha * beta or alpha * beta == 0.0:
                    continue
                zeta = (beta - alpha) / (2.0 * gamma)
                t = math.copysign(1.0, zeta) / (abs(zeta) + math.sqrt(1.0 + zeta * zeta))
                c = 1.0 / math.sqrt(1.0 + t * t)
                s = c * t
                for r in range(m):
                    bi, bj = B[r][i], B[r][j]
                    B[r][i] = c * bi - s * bj
                    B[r][j] = s * bi + c * bj
                for r in range(n):
                    vi, vj = V[r][i], V[r][j]
                    V[r][i] = c * vi - s * vj
                    V[r][j] = s * vi + c * vj
        if off <= tol * fro2 * fro2:
            break

    sigma = [math.sqrt(sum(B[r][k] * B[r][k] for r in range(m))) for k in range(n)]
    order = sorted(range(n), key=lambda k: -sigma[k])
    tiny = 1e-12 * max(sigma or [1.0])

    u_cols: list[list[float]] = []
    v_rows: list[list[float]] = []
    s_sorted: list[float] = []
    for k in order:
        if sigma[k] > tiny:
            u_cols.append([B[r][k] / sigma[k] for r in range(m)])
        else:
            u_cols.append(None)          # 占位，后续补全
        s_sorted.append(sigma[k])
        v_rows.append([V[r][k] for r in range(n)])
    # U 必须是 m 列正交完备基：秩 ≤ min(m,n)，不足则补、超出则截（奇异值已降序）
    while len(u_cols) < m:
        u_cols.append(None)
    u_cols = _complete_basis(u_cols[:m], m)

    U_data = [[u_cols[c][r] for c in range(m)] for r in range(m)]
    S_data = [[s_sorted[j] if i == j and j < n else 0.0
               for j in range(n)] for i in range(m)]
    Vt_data = [[v_rows[k][j] if k < n else (1.0 if j == k - n else 0.0)
                for j in range(n)] for k in range(n)]
    return Matrix(U_data), Matrix(S_data), Matrix(Vt_data)


def _complete_basis(cols: list, m: int) -> list[list[float]]:
    """把缺失/不足的左奇异向量用标准基补成 R^m 的正交完备基。"""
    out: list[list[float]] = [None] * len(cols)
    kept: list[list[float]] = []
    for idx, c in enumerate(cols):
        if c is not None:
            out[idx] = list(c)
            kept.append(out[idx])
    for idx, c in enumerate(cols):
        if c is not None:
            continue
        for e in range(m):
            v = [1.0 if q == e else 0.0 for q in range(m)]
            for u in kept:
                dot = sum(u[q] * v[q] for q in range(m))
                v = [v[q] - dot * u[q] for q in range(m)]
            norm = math.sqrt(sum(x * x for x in v))
            if norm > 1e-9:
                v = [x / norm for x in v]
                out[idx] = v
                kept.append(v)
                break
        if out[idx] is None:             # 兜底：方向均被占（理论上不会发生）
            out[idx] = [0.0] * m
    return out


def _svd_from_eigenvalues(A: Matrix) -> tuple[Matrix, Matrix, Matrix]:
    """从特征值分解推导 SVD（仅适用于对称阵，作为 Jacobi 主路的对比参考）。

    对于对称矩阵 A：
    - 奇异值 σ_i = |λ_i|（特征值的绝对值）
    - U 和 Vt 由特征向量矩阵决定
    """
    n = A.rows
    # 计算特征值和特征向量
    eigenpairs = _eigenvectors_with_values(A)

    # 按特征值绝对值降序排列
    sorted_pairs = sorted(eigenpairs, key=lambda x: abs(x[0]), reverse=True)
    singular_values = [abs(ep[0]) for ep in sorted_pairs]

    # 构造 S 矩阵
    S_data = [[singular_values[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    S = Matrix(S_data)

    # 构造 U 和 Vt 矩阵（特征向量矩阵）
    eigenvectors = [ep[1] for ep in sorted_pairs]
    U_data = [[eigenvectors[i][j] if j < len(eigenvectors[i]) else 0.0
               for j in range(n)] for i in range(n)]
    Vt_data = [[eigenvectors[i][j] if j < len(eigenvectors[i]) else 0.0
                for j in range(n)] for i in range(n)]

    # 处理负特征值：调整 U 的符号
    for i in range(n):
        if sorted_pairs[i][0] < 0:
            for row in range(n):
                U_data[row][i] = -U_data[row][i]

    U = Matrix(U_data)
    Vt = Matrix(Vt_data)

    return U, S, Vt


def _eigenvectors_with_values(A: Matrix) -> list:
    """
    使用幂迭代法计算特征值和特征向量。

    Returns:
        list of (eigenvalue, eigenvector) tuples
    """
    n = A.rows
    eigenpairs = []
    phi = (math.sqrt(5.0) - 1.0) / 2.0

    for k in range(n):
        # 确定性初值（黄金比低差异序列）：旧版 random 使特征向量符号随运行漂移
        v = [((j + 1) * phi % 1.0) * 2.0 - 1.0 for j in range(n)]
        # 归一化
        norm = math.sqrt(sum(x**2 for x in v))
        if norm > 1e-12:
            v = [x / norm for x in v]

        eigenvalue = 0.0
        for _ in range(200):
            # 矩阵向量乘法
            Av = [sum(A.data[i][j] * v[j] for j in range(n)) for i in range(n)]
            # 计算特征值估计
            new_eigenvalue = sum(Av[i] * v[i] for i in range(n))
            # 归一化
            norm = math.sqrt(sum(x**2 for x in Av))
            if norm < 1e-12:
                break
            v_new = [x / norm for x in Av]
            # 检查收敛
            diff = math.sqrt(sum((v_new[i] - v[i])**2 for i in range(n)))
            v = v_new
            eigenvalue = new_eigenvalue
            if diff < 1e-10:
                break

        # Gram-Schmidt 正交化
        for j in range(k):
            proj = sum(v[i] * eigenpairs[j][1][i] for i in range(n))
            v = [v[i] - proj * eigenpairs[j][1][i] for i in range(n)]
        norm = math.sqrt(sum(x**2 for x in v))
        if norm > 1e-12:
            v = [x / norm for x in v]
            eigenpairs.append((eigenvalue, v))

    return eigenpairs


def _svd_power_iteration(A: Matrix, *, sweeps: int = 200) -> tuple[Matrix, Matrix, Matrix]:
    """幂迭代 SVD（带 deflation 与确定性初值）。

    主路已改为 :func:`_svd_jacobi`；本实现保留给只要前 k 个奇异对的截断需求。
    两点加固（旧版在这两处会给出不可信结果）：

    1. 初值用黄金比低差异序列代替 ``random.uniform``——旧版结果随运行漂移，
       golden 对拍与 VM↔native 对拍都无法稳定；
    2. 每收敛一个奇异三元组后做 deflation（A ← A − σ·u·vᵗ），并将迭代向量
       对已得右奇异向量正交化——旧版不降阶，第 2、3… 个奇异值会重复同一个。
    """
    m, n = A.rows, A.cols

    # 初始化
    U = Matrix.zeros(m, m)
    Vt = Matrix.zeros(n, n)
    S = Matrix.zeros(m, n)

    res = [[float(A.data[i][j]) for j in range(n)] for i in range(m)]
    found_v: list[list[float]] = []
    phi = (math.sqrt(5.0) - 1.0) / 2.0

    for k in range(min(m, n)):
        v = [((j + 1) * phi % 1.0) * 2.0 - 1.0 for j in range(n)]
        v = _orthogonalize(v, found_v)
        norm = math.sqrt(sum(x * x for x in v))
        if norm <= 1e-14:
            break
        v = [x / norm for x in v]

        for _ in range(sweeps):
            Av = [sum(res[i][j] * v[j] for j in range(n)) for i in range(m)]
            ATAv = _orthogonalize([sum(res[i][j] * Av[i] for i in range(m))
                                   for j in range(n)], found_v)
            norm = math.sqrt(sum(x * x for x in ATAv))
            if norm <= 1e-14:
                break
            v_new = [x / norm for x in ATAv]
            diff = math.sqrt(sum((v_new[j] - v[j]) ** 2 for j in range(n)))
            v = v_new
            if diff < 1e-12:
                break

        Av = [sum(res[i][j] * v[j] for j in range(n)) for i in range(m)]
        sigma = math.sqrt(sum(x * x for x in Av))
        if sigma <= 1e-12:
            break
        u = [x / sigma for x in Av]

        S.data[k][k] = sigma
        for i in range(m):
            U.data[i][k] = u[i]
        for j in range(n):
            Vt.data[k][j] = v[j]
        found_v.append(v)
        for i in range(m):
            for j in range(n):
                res[i][j] -= sigma * u[i] * v[j]

    return U, S, Vt


def _orthogonalize(vec: list[float], basis: list[list[float]]) -> list[float]:
    """把 ``vec`` 对 ``basis`` 中各向量正交化（修正两轮以抑制舍入漂移）。"""
    v = list(vec)
    for _ in range(2):
        for b in basis:
            dot = sum(b[q] * v[q] for q in range(len(v)))
            v = [v[q] - dot * b[q] for q in range(len(v))]
    return v


# ============================================================
# LU 分解
# ============================================================

def lu_decompose(A: Matrix) -> tuple[Matrix, Matrix]:
    """
    LU 分解：A = L × U

    Args:
        A: n×n 方阵

    Returns:
        L: 下三角矩阵
        U: 上三角矩阵
    """
    n = A.rows
    L = Matrix.zeros(n, n)
    U = Matrix.zeros(n, n)

    # Doolittle 算法
    for i in range(n):
        L.data[i][i] = 1.0

    for j in range(n):
        # U 的第 j 行
        for k in range(j, n):
            s = sum(L.data[j][m] * U.data[m][k] for m in range(j))
            U.data[j][k] = A.data[j][k] - s

        # L 的第 j 列
        for i in range(j, n):
            s = sum(L.data[i][m] * U.data[m][j] for m in range(j))
            if abs(U.data[j][j]) < 1e-12:
                L.data[i][j] = 0.0
            else:
                L.data[i][j] = (A.data[i][j] - s) / U.data[j][j]

    return L, U


# ============================================================
# Cholesky 分解
# ============================================================

def cholesky_decompose(A: Matrix) -> Matrix | None:
    """
    Cholesky 分解：A = L × L^T

    Args:
        A: n×n 对称正定矩阵

    Returns:
        L: 下三角矩阵
    """
    n = A.rows
    L = Matrix.zeros(n, n)

    for i in range(n):
        for j in range(i + 1):
            s = sum(L.data[i][k] * L.data[j][k] for k in range(j))

            if i == j:
                val = A.data[i][i] - s
                if val < 0:
                    logger.warning(f"矩阵不是正定的，元素 {i},{i} 为负")
                    return None
                L.data[i][j] = math.sqrt(val)
            else:
                if abs(L.data[j][j]) < 1e-12:
                    L.data[i][j] = 0.0
                else:
                    L.data[i][j] = (A.data[i][j] - s) / L.data[j][j]

    return L


# ============================================================
# 线性方程组求解
# ============================================================

def solve_linear_system(A: Matrix, b: list[float]) -> list[float] | None:
    """
    求解线性方程组 Ax = b

    使用高斯消元法。

    Args:
        A: n×n 系数矩阵
        b: n×1 常数向量

    Returns:
        x: n×1 解向量
    """
    n = A.rows
    # 增广矩阵 [A | b]
    aug = [row[:] + [b[i]] for i, row in enumerate(A.data)]

    # 高斯消元
    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row

        if abs(aug[max_row][col]) < 1e-12:
            return None  # 奇异矩阵

        # 交换行
        aug[col], aug[max_row] = aug[max_row], aug[col]

        # 归一化
        pivot = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= pivot

        # 消元
        for row in range(col + 1, n):
            factor = aug[row][col]
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]

    # 回代
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = aug[i][n]
        for j in range(i + 1, n):
            x[i] -= aug[i][j] * x[j]

    return x
