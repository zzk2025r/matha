# -*- coding: utf-8 -*-
"""Matha NumPy 兼容层 - 纯 Python 实现

本模块提供 NumPy 核心功能的纯 Python 实现，无需外部依赖。
支持移动端和平板设备的数学计算需求。

特性：
- 纯 Python 实现，零外部依赖
- 移动端友好的内存管理
- 与 NumPy API 兼容
"""
from __future__ import annotations
import math
import logging
from typing import List, Tuple, Optional, Union, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================
# 基础类型定义
# ============================================================

class ndarray:
    """
    多维数组类（NumPy ndarray 兼容实现）

    支持：
    - 一维到三维数组
    - 基本算术运算
    - 矩阵运算
    - 广播机制
    """

    def __init__(self, data: Union[List, Tuple, 'ndarray'], dtype: type = float):
        """
        初始化 ndarray

        Args:
            data: 数组数据（嵌套列表或元组）
            dtype: 数据类型（float, int, complex）
        """
        self.dtype = dtype
        self._data = self._convert_to_array(data)
        self._shape = self._compute_shape(self._data)
        self._ndim = len(self._shape)

        logger.debug(f"创建 ndarray: shape={self.shape}, dtype={dtype.__name__}")

    def _convert_to_array(self, data: Union[List, Tuple, 'ndarray']) -> List:
        """将输入数据转换为嵌套列表"""
        if isinstance(data, ndarray):
            return data._data
        if isinstance(data, (int, float, complex)):
            return data
        if isinstance(data, (list, tuple)):
            if len(data) == 0:
                return []
            if isinstance(data[0], (list, tuple)):
                return [self._convert_to_array(item) for item in data]
            return [self._cast(item) for item in data]
        return data

    def _compute_shape(self, data: List) -> Tuple[int, ...]:
        """计算数组形状"""
        if isinstance(data, (int, float, complex)):
            return ()
        if isinstance(data, list) and len(data) > 0:
            return (len(data),) + self._compute_shape(data[0])
        return (0,)

    def _cast(self, value) -> Union[int, float, complex]:
        """类型转换"""
        if self.dtype == int:
            return int(value)
        elif self.dtype == complex:
            return complex(value)
        return float(value)

    @property
    def shape(self) -> Tuple[int, ...]:
        """数组形状"""
        return self._shape

    @property
    def size(self) -> int:
        """元素总数"""
        if not self._shape:
            return 1
        return math.prod(self._shape)

    @property
    def ndim(self) -> int:
        """维度数"""
        return self._ndim

    def reshape(self, *new_shape: int) -> 'ndarray':
        """重塑数组形状"""
        new_size = math.prod(new_shape)
        if new_size != self.size:
            raise ValueError(f"无法将 shape={self.shape} 重塑为 {new_shape}")

        flat = self.flatten()
        return ndarray(flat).reshape(*new_shape)

    def flatten(self) -> List:
        """展平为一维数组"""
        if not self._shape:
            return [self._data]
        if self.ndim == 1:
            return self._data
        result = []
        for item in self._data:
            if isinstance(item, list):
                result.extend(self._flatten_list(item))
            else:
                result.append(item)
        return result

    def _flatten_list(self, data: List) -> List:
        """递归展平列表"""
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(self._flatten_list(item))
            else:
                result.append(item)
        return result

    def __getitem__(self, index):
        """索引访问"""
        if self.ndim == 0:
            return self._data
        if isinstance(index, int):
            return self._data[index]
        if isinstance(index, tuple):
            return self._nested_get(self._data, index)
        return self._data[index]

    def _nested_get(self, data: List, indices: Tuple) -> any:
        """递归获取嵌套列表元素"""
        if len(indices) == 1:
            return data[indices[0]]
        return self._nested_get(data[indices[0]], indices[1:])

    def __setitem__(self, index, value):
        """索引赋值"""
        if self.ndim == 0:
            self._data = value
            return
        if isinstance(index, int):
            self._data[index] = value
        elif isinstance(index, tuple):
            self._nested_set(self._data, index, value)

    def _nested_set(self, data: List, indices: Tuple, value):
        """递归设置嵌套列表元素"""
        if len(indices) == 1:
            data[indices[0]] = value
        else:
            self._nested_set(data[indices[0]], indices[1:], value)

    def __repr__(self) -> str:
        """字符串表示"""
        if self.ndim == 0:
            return f"ndarray({self._data})"
        return f"ndarray(shape={self.shape}, dtype={self.dtype.__name__})"

    def __str__(self) -> str:
        """打印表示"""
        return self._format_array(self._data, 0)

    def _format_array(self, data: List, depth: int) -> str:
        """格式化数组输出"""
        indent = "  " * depth
        if isinstance(data, list):
            if len(data) == 0:
                return "[]"
            lines = [indent + "["]
            for i, item in enumerate(data):
                comma = "," if i < len(data) - 1 else ""
                if isinstance(item, list):
                    lines.append(indent + "  " + self._format_array(item, depth + 1) + comma)
                else:
                    lines.append(indent + "  " + str(item) + comma)
            lines.append(indent + "]")
            return "\n".join(lines)
        return str(data)

    # ============================================================
    # 算术运算
    # ============================================================

    def __add__(self, other: Union['ndarray', int, float]) -> 'ndarray':
        """加法"""
        if isinstance(other, (int, float)):
            return ndarray(self._broadcast_op(self._data, other, lambda x: x + other))
        return ndarray(self._element_wise_op(self._data, other._data, lambda a, b: a + b))

    def __sub__(self, other: Union['ndarray', int, float]) -> 'ndarray':
        """减法"""
        if isinstance(other, (int, float)):
            return ndarray(self._broadcast_op(self._data, other, lambda x: x - other))
        return ndarray(self._element_wise_op(self._data, other._data, lambda a, b: a - b))

    def __mul__(self, other: Union['ndarray', int, float]) -> 'ndarray':
        """乘法"""
        if isinstance(other, (int, float)):
            return ndarray(self._broadcast_op(self._data, other, lambda x: x * other))
        return ndarray(self._element_wise_op(self._data, other._data, lambda a, b: a * b))

    def __truediv__(self, other: Union['ndarray', int, float]) -> 'ndarray':
        """除法"""
        if isinstance(other, (int, float)):
            return ndarray(self._broadcast_op(self._data, other, lambda x: x / other))
        return ndarray(self._element_wise_op(self._data, other._data, lambda a, b: a / b))

    def _broadcast_op(self, data, scalar, op):
        """广播操作"""
        if isinstance(data, list):
            return [self._broadcast_op(item, scalar, op) for item in data]
        return op(data)

    def _element_wise_op(self, data1, data2, op):
        """逐元素操作"""
        if isinstance(data1, list) and isinstance(data2, list):
            return [self._element_wise_op(a, b, op) for a, b in zip(data1, data2)]
        return op(data1, data2)

    # ============================================================
    # 数学函数
    # ============================================================

    def abs(self) -> 'ndarray':
        """绝对值"""
        return ndarray(self._broadcast_op(self._data, 0, lambda x: abs(x)))

    def sqrt(self) -> 'ndarray':
        """平方根（安全处理负数）"""
        import warnings
        has_negative = any(x < 0 for x in self.flatten() if isinstance(x, (int, float)))
        if has_negative:
            warnings.warn("sqrt() 检测到负数，返回复数或 0", UserWarning)
        return ndarray(self._broadcast_op(self._data, 0, lambda x: math.sqrt(abs(x)) if x >= 0 else complex(0, math.sqrt(abs(x)))))

    def sin(self) -> 'ndarray':
        """正弦"""
        return ndarray(self._broadcast_op(self._data, 0, math.sin))

    def cos(self) -> 'ndarray':
        """余弦"""
        return ndarray(self._broadcast_op(self._data, 0, math.cos))

    def tan(self) -> 'ndarray':
        """正切"""
        return ndarray(self._broadcast_op(self._data, 0, math.tan))

    def exp(self) -> 'ndarray':
        """指数"""
        return ndarray(self._broadcast_op(self._data, 0, math.exp))

    def log(self) -> 'ndarray':
        """自然对数"""
        return ndarray(self._broadcast_op(self._data, 0, math.log))

    def dot(self, other: 'ndarray') -> 'ndarray':
        """矩阵点积"""
        if self.ndim != 2 or other.ndim != 2:
            raise ValueError("dot 仅支持二维矩阵")
        result = []
        for i in range(self.shape[0]):
            row = []
            for j in range(other.shape[1]):
                s = 0
                for k in range(self.shape[1]):
                    s += self[i][k] * other[k][j]
                row.append(s)
            result.append(row)
        return ndarray(result)

    def transpose(self) -> 'ndarray':
        """转置"""
        if self.ndim != 2:
            raise ValueError("transpose 仅支持二维矩阵")
        result = [[self[j][i] for j in range(self.shape[0])] for i in range(self.shape[1])]
        return ndarray(result)

    def sum(self, axis: Optional[int] = None) -> Union['ndarray', float]:
        """求和"""
        if axis is None:
            return self._sum_all(self._data)
        if axis == 0:
            return ndarray([sum(self[i][j] for i in range(self.shape[0])) for j in range(self.shape[1])])
        if axis == 1:
            return ndarray([sum(row) for row in self._data])
        raise ValueError(f"不支持的轴: {axis}")

    def _sum_all(self, data) -> float:
        """递归求和"""
        if isinstance(data, list):
            return sum(self._sum_all(item) for item in data)
        return data

    def mean(self) -> float:
        """均值"""
        return self.sum() / self.size

    def std(self) -> float:
        """标准差"""
        m = self.mean()
        variance = self._sum_all([(x - m) ** 2 for x in self.flatten()]) / self.size
        return math.sqrt(variance)


# ============================================================
# 工厂函数
# ============================================================

def array(data: Union[List, Tuple], dtype: type = float) -> ndarray:
    """创建数组"""
    return ndarray(data, dtype)


def zeros(shape: Tuple[int, ...], dtype: type = float) -> ndarray:
    """创建零数组"""
    if len(shape) == 1:
        return ndarray([0.0] * shape[0], dtype)
    if len(shape) == 2:
        return ndarray([[0.0] * shape[1] for _ in range(shape[0])], dtype)
    if len(shape) == 3:
        return ndarray([[[0.0] * shape[2] for _ in range(shape[1])] for _ in range(shape[0])], dtype)
    raise ValueError(f"不支持的维度: {len(shape)}")


def ones(shape: Tuple[int, ...], dtype: type = float) -> ndarray:
    """创建全一数组"""
    if len(shape) == 1:
        return ndarray([1.0] * shape[0], dtype)
    if len(shape) == 2:
        return ndarray([[1.0] * shape[1] for _ in range(shape[0])], dtype)
    if len(shape) == 3:
        return ndarray([[[1.0] * shape[2] for _ in range(shape[1])] for _ in range(shape[0])], dtype)
    raise ValueError(f"不支持的维度: {len(shape)}")


def eye(n: int, dtype: type = float) -> ndarray:
    """单位矩阵"""
    result = [[0.0] * n for _ in range(n)]
    for i in range(n):
        result[i][i] = 1.0
    return ndarray(result, dtype)


def arange(start: float, stop: Optional[float] = None, step: float = 1.0) -> ndarray:
    """生成等差数列"""
    if stop is None:
        stop = start
        start = 0.0
    result = []
    current = start
    while current < stop:
        result.append(current)
        current += step
    return ndarray(result)


def linspace(start: float, stop: float, num: int = 50) -> ndarray:
    """生成等间隔数列"""
    if num == 1:
        return ndarray([start])
    step = (stop - start) / (num - 1)
    result = [start + i * step for i in range(num)]
    return ndarray(result)


def random(size: Union[int, Tuple[int, ...]]) -> ndarray:
    """随机数组"""
    import random as rand_module
    if isinstance(size, int):
        return ndarray([rand_module.random() for _ in range(size)])
    if len(size) == 2:
        return ndarray([[rand_module.random() for _ in range(size[1])] for _ in range(size[0])])
    raise ValueError(f"不支持的维度: {len(size)}")


# ============================================================
# 线性代数函数
# ============================================================

def matrix_multiply(A: ndarray, B: ndarray) -> ndarray:
    """矩阵乘法"""
    return A.dot(B)


def matrix_transpose(A: ndarray) -> ndarray:
    """矩阵转置"""
    return A.transpose()


def matrix_inverse(A: ndarray) -> Optional[ndarray]:
    """矩阵求逆（高斯-约当消元法）"""
    n = A.shape[0]
    if A.shape[0] != A.shape[1]:
        raise ValueError("仅对方阵求逆")

    # 创建增广矩阵 [A | I]
    aug = []
    for i in range(n):
        row = [A[i][j] for j in range(n)] + [1.0 if i == j else 0.0 for j in range(n)]
        aug.append(row)

    # 高斯-约当消元
    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row
        aug[col], aug[max_row] = aug[max_row], aug[col]

        if abs(aug[col][col]) < 1e-12:
            return None  # 奇异矩阵

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
    inv_data = [[aug[i][j + n] for j in range(n)] for i in range(n)]
    return ndarray(inv_data)


def matrix_determinant(A: ndarray) -> float:
    """矩阵行列式（高斯消元法）"""
    n = A.shape[0]
    if A.shape[0] != A.shape[1]:
        raise ValueError("仅对方阵计算行列式")

    mat = [row[:] for row in A._data]
    det = 1.0

    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(mat[row][col]) > abs(mat[max_row][col]):
                max_row = row
        mat[col], mat[max_row] = mat[max_row], mat[col]
        if max_row != col:
            det = -det

        if abs(mat[col][col]) < 1e-12:
            return 0.0

        det *= mat[col][col]

        # 消元
        for row in range(col + 1, n):
            factor = mat[row][col] / mat[col][col]
            for j in range(col, n):
                mat[row][j] -= factor * mat[col][j]

    return det


def svd_decompose(A: ndarray) -> Tuple[ndarray, ndarray, ndarray]:
    """
    SVD 分解：A = U Σ V^T

    使用纯 Python 实现（QR 迭代法）
    """
    m, n = A.shape[0], A.shape[1]

    # 简化实现：对于对称矩阵，SVD = 特征值分解
    if m == n:
        # 检查对称性
        is_symmetric = all(abs(A[i][j] - A[j][i]) < 1e-10 for i in range(m) for j in range(m))
        if is_symmetric:
            return _svd_from_eigenvalues(A)

    # 通用情况：使用幂迭代法求奇异值分解
    return _svd_general(A)


def _svd_from_eigenvalues(A: ndarray) -> Tuple[ndarray, ndarray, ndarray]:
    """从特征值分解计算 SVD（对称矩阵）

    对于对称矩阵 A，SVD 可以通过特征值分解得到：
    - 奇异值 σ_i = |λ_i|（特征值的绝对值）
    - U 和 V 由特征向量矩阵决定
    """
    n = A.shape[0]

    # 使用幂迭代法计算特征值和特征向量
    eigenpairs = _eig_power_iteration(A, max_iter=200)

    # 构造奇异值矩阵（按降序排列）
    eigenvalues = [ep[0] for ep in eigenpairs]
    # 按绝对值排序
    sorted_indices = sorted(range(len(eigenvalues)), key=lambda i: abs(eigenvalues[i]), reverse=True)
    singular_values = [abs(eigenvalues[i]) for i in sorted_indices]

    # 构造 S 矩阵
    S_data = [[singular_values[i] if i == j else 0.0 for j in range(n)] for i in range(n)]
    S = ndarray(S_data)

    # 构造 U 和 Vt 矩阵（特征向量矩阵）
    # eigenvectors 是 [[x], [y], ...] 格式，需要提取标量
    eigenvectors = [eigenpairs[i][1] for i in sorted_indices]
    U_data = [[eigenvectors[i][j][0] if j < len(eigenvectors[i]) and len(eigenvectors[i][j]) > 0 else 0.0
               for j in range(n)] for i in range(n)]
    Vt_data = [[eigenvectors[i][j][0] if j < len(eigenvectors[i]) and len(eigenvectors[i][j]) > 0 else 0.0
                for j in range(n)] for i in range(n)]

    # 处理负特征值：调整 U 或 Vt 的符号
    for i in range(n):
        if eigenvalues[sorted_indices[i]] < 0:
            # 翻转 U 的对应列
            for row in range(n):
                U_data[row][i] = -U_data[row][i]

    U = ndarray(U_data)
    Vt = ndarray(Vt_data)

    return U, S, Vt


def _svd_general(A: ndarray) -> Tuple[ndarray, ndarray, ndarray]:
    """通用矩阵的 SVD 分解（幂迭代法）"""
    m, n = A.shape[0], A.shape[1]

    # 初始化
    U_data = [[1.0 if i == j else 0.0 for j in range(m)] for i in range(m)]
    S_data = [[0.0] * n for _ in range(m)]
    Vt_data = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    import random
    k = min(m, n)

    for p in range(k):
        # 随机初始化 v
        v = [random.uniform(-1, 1) for _ in range(n)]
        # 归一化
        norm = math.sqrt(sum(x**2 for x in v))
        if norm > 1e-12:
            v = [x / norm for x in v]

        # Gram-Schmidt 正交化
        for j in range(p):
            dot = sum(v[l] * Vt_data[j][l] for l in range(n))
            v = [v[l] - dot * Vt_data[j][l] for l in range(n)]
        norm = math.sqrt(sum(x**2 for x in v))
        if norm > 1e-12:
            v = [x / norm for x in v]

        # 幂迭代
        for _ in range(100):
            # Av
            Av = [sum(A[i][j] * v[j] for j in range(n)) for i in range(m)]
            # A^T Av
            ATAv = [sum(A[i][j] * Av[i] for i in range(m)) for j in range(n)]
            # 正交化
            for j in range(p):
                dot = sum(ATAv[l] * Vt_data[j][l] for l in range(n))
                ATAv = [ATAv[l] - dot * Vt_data[j][l] for l in range(n)]
            # 归一化
            norm = math.sqrt(sum(x**2 for x in ATAv))
            if norm < 1e-12:
                break
            v = [x / norm for x in ATAv]

        # 计算奇异值和 u
        Av = [sum(A[i][j] * v[j] for j in range(n)) for i in range(m)]
        sigma = math.sqrt(sum(x**2 for x in Av))
        if sigma > 1e-12:
            S_data[p][p] = sigma
            u = [x / sigma for x in Av]
            for i in range(m):
                U_data[i][p] = u[i]
            for j in range(n):
                Vt_data[p][j] = v[j]

    U = ndarray(U_data)
    S = ndarray(S_data)
    Vt = ndarray(Vt_data)
    return U, S, Vt


def _eig_power_iteration(A: ndarray, max_iter: int = 200, tol: float = 1e-10) -> list:
    """使用幂迭代法计算特征值和特征向量"""
    n = A.shape[0]
    eigenpairs = []

    for k in range(n):
        # 初始化随机向量
        import random as rand_module
        v = [[rand_module.random()] for _ in range(n)]
        # 归一化
        norm = math.sqrt(sum(x[0]**2 for x in v))
        if norm > 1e-12:
            v = [[x[0] / norm] for x in v]

        eigenvalue = 0.0
        for _ in range(max_iter):
            # 矩阵向量乘法
            Av = _mat_vec_mul(A, v)
            # 计算新特征值估计
            new_eigenvalue = sum(Av[i][0] * v[i][0] for i in range(n))
            # 归一化
            norm = math.sqrt(sum(x[0]**2 for x in Av))
            if norm < 1e-12:
                break
            v_new = [[x[0] / norm] for x in Av]

            # 检查收敛
            diff = math.sqrt(sum((v_new[i][0] - v[i][0])**2 for i in range(n)))
            v = v_new
            eigenvalue = new_eigenvalue

            if diff < tol:
                break

        # 正交化（Gram-Schmidt）以找到下一个特征向量
        for j in range(k):
            v_proj = _dot_product(v, eigenpairs[j][1])
            v = _vec_sub(v, _scale_vec(eigenpairs[j][1], v_proj))

        norm = math.sqrt(sum(x[0]**2 for x in v))
        if norm > 1e-12:
            v = [[x[0] / norm] for x in v]
            eigenpairs.append((eigenvalue, v))

    return eigenpairs


def _mat_vec_mul(A: ndarray, v: list) -> list:
    """矩阵向量乘法"""
    m = A.shape[0]
    n = A.shape[1] if A.ndim > 1 else 1
    result = []
    for i in range(m):
        s = 0.0
        for j in range(n):
            s += A[i][j] * v[j][0]
        result.append([s])
    return result


def _dot_product(v1: list, v2: list) -> float:
    """向量点积"""
    return sum(v1[i][0] * v2[i][0] for i in range(len(v1)))


def _scale_vec(v: list, scalar: float) -> list:
    """向量缩放"""
    return [[x[0] * scalar] for x in v]


def _vec_sub(v1: list, v2: list) -> list:
    """向量减法"""
    return [[v1[i][0] - v2[i][0]] for i in range(len(v1))]


def trace(A: ndarray) -> float:
    """矩阵迹"""
    if A.shape[0] != A.shape[1]:
        raise ValueError("迹仅对方阵定义")
    return sum(A[i][i] for i in range(A.shape[0]))


def norm(A: ndarray, ord: Optional[str] = None) -> float:
    """矩阵范数"""
    if ord == 'fro' or ord is None:
        # Frobenius 范数
        return math.sqrt(sum(x**2 for row in A._data for x in row))
    if ord == 'inf':
        # 无穷范数（行和最大值）
        return max(sum(abs(x) for x in row) for row in A._data)
    if ord == 1:
        # 1-范数（列和最大值）
        n = A.shape[1]
        col_sums = [sum(abs(A[i][j]) for i in range(A.shape[0])) for j in range(n)]
        return max(col_sums)
    raise ValueError(f"不支持的范数类型: {ord}")
