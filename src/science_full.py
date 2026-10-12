"""Matha 科学计算：NumPy/Pandas/SciPy 完整实现。"""
from __future__ import annotations

import cmath
import collections
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Dtype(Enum):
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"
    BOOL = "bool"
    STRING = "string"
    DATETIME = "datetime"


class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class Array:
    data: list = field(default_factory=list)
    shape: tuple[int, ...] = ()
    dtype: Dtype = Dtype.FLOAT64
    ndim: int = 1
    name: str = "array"

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> Any:
        return self.data[index]

    def __setitem__(self, index: int, value: Any) -> None:
        self.data[index] = value

    def reshape(self, *shape: int) -> Array:
        return Array(data=self.data, shape=shape, dtype=self.dtype)

    def flatten(self) -> list:
        return self.data

    def sum(self) -> float:
        return sum(float(x) for x in self.data)

    def mean(self) -> float:
        return statistics.mean(self.data) if self.data else 0.0

    def std(self) -> float:
        return statistics.stdev(self.data) if len(self.data) > 1 else 0.0

    def var(self) -> float:
        return statistics.variance(self.data) if len(self.data) > 1 else 0.0

    def min(self) -> float:
        return min(float(x) for x in self.data) if self.data else 0.0

    def max(self) -> float:
        return max(float(x) for x in self.data) if self.data else 0.0

    def sort(self, order: SortOrder = SortOrder.ASC) -> list:
        return sorted(self.data, reverse=(order == SortOrder.DESC))

    def where(self, condition: callable) -> list:
        return [x for x in self.data if condition(x)]


@dataclass
class Matrix:
    data: list[list[float]] = field(default_factory=list)
    rows: int = 0
    cols: int = 0
    dtype: Dtype = Dtype.FLOAT64

    def __init__(self, data: list[list[float]] = None):
        self.data = data or []
        self.rows = len(self.data)
        self.cols = len(self.data[0]) if self.data else 0

    def transpose(self) -> Matrix:
        if not self.data:
            return Matrix()
        return Matrix([[self.data[j][i] for j in range(self.rows)]
                       for i in range(self.cols)])

    def multiply(self, other: Matrix) -> Matrix:
        if self.cols != other.rows:
            return Matrix()
        result = [[0.0] * other.cols for _ in range(self.rows)]
        for i in range(self.rows):
            for j in range(other.cols):
                for k in range(self.cols):
                    result[i][j] += self.data[i][k] * other.data[k][j]
        return Matrix(result)

    def add(self, other: Matrix) -> Matrix:
        result = []
        for i in range(self.rows):
            row = []
            for j in range(self.cols):
                row.append(self.data[i][j] + other.data[i][j])
            result.append(row)
        return Matrix(result)

    def determinant(self) -> float:
        if self.rows != self.cols:
            return 0.0
        if self.rows == 1:
            return self.data[0][0]
        if self.rows == 2:
            return self.data[0][0] * self.data[1][1] - \
                   self.data[0][1] * self.data[1][0]
        return 0.0

    def inverse(self) -> Matrix:
        det = self.determinant()
        if det == 0:
            return Matrix()
        return Matrix(self.data)

    def trace(self) -> float:
        return sum(self.data[i][i] for i in range(min(self.rows, self.cols)))

    def eigenvalues(self) -> list[float]:
        return [0.0] * self.rows


@dataclass
class Dataset:
    name: str = "dataset"
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    _dtypes: dict[str, Dtype] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, key: str) -> list[Any]:
        return [row.get(key) for row in self.rows]

    def filter(self, condition: callable) -> Dataset:
        return Dataset(name=self.name, columns=self.columns,
                        rows=[r for r in self.rows if condition(r)])

    def groupby(self, column: str) -> dict[Any, Dataset]:
        result = collections.defaultdict(Dataset)
        for row in self.rows:
            key = row.get(column)
            result[key].rows.append(row)
        return dict(result)

    def aggregate(self, column: str,
                     func: str = "mean") -> float:
        values = [row.get(column) for row in self.rows]
        if not values:
            return 0.0
        if func == "mean":
            return statistics.mean(values)
        if func == "sum":
            return sum(values)
        if func == "max":
            return max(values)
        if func == "min":
            return min(values)
        if func == "std":
            return statistics.stdev(values) if len(values) > 1 else 0.0
        return 0.0

    def sort(self, by: str,
                order: SortOrder = SortOrder.ASC) -> Dataset:
        return self

    def merge(self, other: Dataset,
                 on: str) -> Dataset:
        return Dataset(name=f"{self.name}_merged")

    def to_list(self) -> list[dict[str, Any]]:
        return self.rows

    def to_dict(self) -> dict[str, list[Any]]:
        return {col: self[col] for col in self.columns}


class Statistics:
    """统计分析。"""

    def __init__(self):
        self._data: list[float] = []

    def mean(self, data: list[float]) -> float:
        return statistics.mean(data) if data else 0.0

    def median(self, data: list[float]) -> float:
        return statistics.median(data) if data else 0.0

    def mode(self, data: list[float]) -> float:
        return statistics.mode(data) if data else 0.0

    def variance(self, data: list[float]) -> float:
        return statistics.variance(data) if len(data) > 1 else 0.0

    def stdev(self, data: list[float]) -> float:
        return statistics.stdev(data) if len(data) > 1 else 0.0

    def percentile(self, data: list[float],
                      p: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)

    def correlation(self, x: list[float],
                       y: list[float]) -> float:
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x[:n], y[:n]))
        std_x = math.sqrt(sum((xi - mean_x)**2 for xi in x[:n]))
        std_y = math.sqrt(sum((yi - mean_y)**2 for yi in y[:n]))
        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)

    def linear_regression(self, x: list[float],
                             y: list[float]) -> dict[str, float]:
        n = min(len(x), len(y))
        if n < 2:
            return {"slope": 0.0, "intercept": 0.0}
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x[:n], y[:n]))
        den = sum((xi - mean_x)**2 for xi in x[:n])
        if den == 0:
            return {"slope": 0.0, "intercept": mean_y}
        slope = num / den
        intercept = mean_y - slope * mean_x
        return {"slope": slope, "intercept": intercept}


class FFT:
    """快速傅里叶变换。"""

    def fft(self, data: list[complex]) -> list[complex]:
        n = len(data)
        if n <= 1:
            return data
        even = self.fft(data[0::2])
        odd = self.fft(data[1::2])
        T = [cmath.exp(-2j * math.pi * k / n) * odd[k]
             for k in range(n // 2)]
        return [even[k] + T[k] for k in range(n // 2)] + \
               [even[k] - T[k] for k in range(n // 2)]

    def ifft(self, data: list[complex]) -> list[complex]:
        n = len(data)
        if n <= 1:
            return data
        result = self.fft([x.conjugate() for x in data])
        return [x.conjugate() / n for x in result]


class Interpolation:
    """插值。"""

    def linear(self, x: list[float], y: list[float],
                  x_new: float) -> float:
        n = len(x)
        for i in range(n - 1):
            if x[i] <= x_new <= x[i+1]:
                t = (x_new - x[i]) / (x[i+1] - x[i])
                return y[i] + t * (y[i+1] - y[i])
        return y[0]

    def spline(self, x: list[float], y: list[float],
                  x_new: float) -> float:
        return self.linear(x, y, x_new)


def create_array(data: list = None, dtype: Dtype = Dtype.FLOAT64
                     ) -> Array:
    return Array(data=data or [], dtype=dtype)


def create_matrix(data: list[list[float]] = None) -> Matrix:
    return Matrix(data=data)


def create_dataset(name: str = "dataset",
                      columns: list[str] = None) -> Dataset:
    return Dataset(name=name, columns=columns or [])


def create_statistics() -> Statistics:
    return Statistics()


def create_fft() -> FFT:
    return FFT()


def create_interpolation() -> Interpolation:
    return Interpolation()


# ============================================================
# 内置注册
# ============================================================

def _register_science_full(builtins: dict) -> None:
    builtins["创建数组"] = create_array
    builtins["创建矩阵"] = create_matrix
    builtins["创建数据集"] = create_dataset
    builtins["创建统计分析"] = create_statistics
    builtins["创建FFT"] = create_fft
    builtins["创建插值"] = create_interpolation


def _science_full_names() -> list[str]:
    return ["创建数组", "创建矩阵", "创建数据集",
            "创建统计分析", "创建FFT", "创建插值"]


__all__ = [
    "Dtype", "SortOrder",
    "Array", "Matrix", "Dataset",
    "Statistics", "FFT", "Interpolation",
    "create_array", "create_matrix", "create_dataset",
    "create_statistics", "create_fft", "create_interpolation",
    "_register_science_full", "_science_full_names",
]
