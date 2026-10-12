"""Matha 科学计算：数组运算、矩阵操作、数值分析。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ArrayShape(Enum):
    """数组形状。"""
    ONE_D = "1d"
    TWO_D = "2d"
    THREE_D = "3d"


@dataclass
class Array:
    """多维数组（类似 NumPy 的 ndarray）。"""
    data: list[Any]
    shape: tuple = (0,)
    dtype: str = "float64"

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value

    def reshape(self, *shape) -> Array:
        """重塑形状。"""
        return Array(data=self.data, shape=shape, dtype=self.dtype)

    def transpose(self) -> Array:
        """转置。"""
        return Array(data=self.data, shape=reversed(self.shape),
                      dtype=self.dtype)

    def sum(self) -> float:
        """求和。"""
        return sum(self.data) if self.data else 0.0

    def mean(self) -> float:
        """均值。"""
        return self.sum() / len(self.data) if self.data else 0.0

    def std(self) -> float:
        """标准差。"""
        m = self.mean()
        return math.sqrt(sum((x - m) ** 2 for x in self.data) / len(self.data))

    def max(self) -> Any:
        """最大值。"""
        return max(self.data) if self.data else None

    def min(self) -> Any:
        """最小值。"""
        return min(self.data) if self.data else None

    def __add__(self, other: Array) -> Array:
        """加法。"""
        return Array(data=[a + b for a, b in zip(self.data, other.data)],
                      shape=self.shape, dtype=self.dtype)

    def __mul__(self, other: Array) -> Array:
        """乘法。"""
        return Array(data=[a * b for a, b in zip(self.data, other.data)],
                      shape=self.shape, dtype=self.dtype)


@dataclass
class Matrix:
    """矩阵（类似 NumPy 的 matrix）。"""
    data: list[list[float]]
    rows: int = 0
    cols: int = 0

    def __init__(self, data: list[list[float]]):
        self.data = data
        self.rows = len(data)
        self.cols = len(data[0]) if data else 0

    def transpose(self) -> Matrix:
        """转置。"""
        return Matrix([[self.data[j][i] for j in range(self.rows)]
                        for i in range(self.cols)])

    def __mul__(self, other: Matrix) -> Matrix:
        """矩阵乘法。"""
        result = [[0.0] * other.cols for _ in range(self.rows)]
        for i in range(self.rows):
            for j in range(other.cols):
                for k in range(self.cols):
                    result[i][j] += self.data[i][k] * other.data[k][j]
        return Matrix(result)

    def determinant(self) -> float:
        """行列式。"""
        if self.rows != self.cols:
            raise ValueError("行列式需要方阵")
        if self.rows == 1:
            return self.data[0][0]
        if self.rows == 2:
            return self.data[0][0] * self.data[1][1] - \
                   self.data[0][1] * self.data[1][0]
        # 递归计算
        det = 0.0
        for j in range(self.cols):
            minor = [[self.data[i][k] for k in range(self.cols)
                       if k != j] for i in range(1, self.rows)]
            det += ((-1) ** j) * self.data[0][j] * Matrix(minor).determinant()
        return det

    def inv(self) -> Matrix:
        """逆矩阵。"""
        det = self.determinant()
        if det == 0:
            raise ValueError("奇异矩阵，不可逆")
        if self.rows == 2:
            return Matrix([
                [self.data[1][1]/det, -self.data[0][1]/det],
                [-self.data[1][0]/det, self.data[0][0]/det]
            ])
        # 通用逆矩阵
        adj = self.adjugate()
        return Matrix([[adj.data[i][j] / det for j in range(self.cols)]
                        for i in range(self.rows)])

    def adjugate(self) -> Matrix:
        """伴随矩阵。"""
        cofactors = []
        for i in range(self.rows):
            row = []
            for j in range(self.cols):
                minor = [[self.data[r][c] for c in range(self.cols)
                           if c != j] for r in range(self.rows) if r != i]
                cofactor = ((-1) ** (i + j)) * Matrix(minor).determinant()
                row.append(cofactor)
            cofactors.append(row)
        return Matrix(cofactors).transpose()

    def solve(self, b: list[float]) -> list[float]:
        """求解线性方程组 Ax = b。"""
        A_inv = self.inv()
        x = A_inv * Matrix([b])
        return x.data[0]

    def eigenvalues(self) -> list[float]:
        """特征值（简单实现）。"""
        if self.rows != self.cols:
            raise ValueError("特征值需要方阵")
        if self.rows == 2:
            trace = self.data[0][0] + self.data[1][1]
            det = self.determinant()
            discriminant = trace ** 2 - 4 * det
            if discriminant >= 0:
                return [(trace + math.sqrt(discriminant)) / 2,
                        (trace - math.sqrt(discriminant)) / 2]
        return []


@dataclass
class Dataset:
    """数据集（类似 Pandas 的 DataFrame）。"""
    columns: list[str] = field(default_factory=list)
    data: list[list[Any]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, col: str) -> list[Any]:
        """按列名获取数据。"""
        if col not in self.columns:
            raise KeyError(f"列 '{col}' 不存在")
        idx = self.columns.index(col)
        return [row[idx] for row in self.data]

    def describe(self) -> dict:
        """统计描述。"""
        stats = {}
        for col in self.columns:
            values = self[col]
            if values and isinstance(values[0], (int, float)):
                nums = [v for v in values if isinstance(v, (int, float))]
                if nums:
                    stats[col] = {
                        "count": len(nums),
                        "mean": sum(nums) / len(nums),
                        "std": math.sqrt(sum((x - sum(nums)/len(nums)) ** 2
                                             for x in nums) / len(nums)),
                        "min": min(nums),
                        "max": max(nums),
                    }
        return stats

    def filter(self, condition: callable) -> Dataset:
        """过滤数据。"""
        filtered = Dataset(columns=self.columns)
        for row in self.data:
            if condition(row):
                filtered.data.append(row)
        return filtered


# ============================================================
# 内置注册
# ============================================================

def create_array(data: list[Any], dtype: str = "float64"
                    ) -> Array:
    """创建数组。"""
    return Array(data=data, dtype=dtype)


def create_matrix(data: list[list[float]]) -> Matrix:
    """创建矩阵。"""
    return Matrix(data)


def create_dataset(columns: list[str],
                     data: list[list[Any]]) -> Dataset:
    """创建数据集。"""
    return Dataset(columns=columns, data=data)


def dot(a: Matrix, b: Matrix) -> Matrix:
    """矩阵点积。"""
    return a * b


def mean(values: list[float]) -> float:
    """均值。"""
    return sum(values) / len(values) if values else 0.0


def std(values: list[float]) -> float:
    """标准差。"""
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def var(values: list[float]) -> float:
    """方差。"""
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / len(values)


def linspace(start: float, stop: float,
                num: int = 50) -> list[float]:
    """线性空间。"""
    step = (stop - start) / (num - 1)
    return [start + i * step for i in range(num)]


def _register_science(builtins: dict) -> None:
    """注册科学计算内置函数。"""
    builtins["创建数组"] = create_array
    builtins["创建矩阵"] = create_matrix
    builtins["创建数据集"] = create_dataset
    builtins["矩阵乘法"] = lambda a, b: dot(a, b)
    builtins["均值"] = mean
    builtins["标准差"] = std
    builtins["方差"] = var
    builtins["线性空间"] = linspace


def _science_symtab_names() -> list[str]:
    return [
        "创建数组", "创建矩阵", "创建数据集",
        "矩阵乘法", "均值", "标准差", "方差", "线性空间",
    ]


__all__ = [
    "Array", "Matrix", "Dataset",
    "ArrayShape",
    "create_array", "create_matrix", "create_dataset",
    "dot", "mean", "std", "var", "linspace",
    "_register_science", "_science_symtab_names",
]
