# -*- coding: utf-8 -*-
"""Matha v4.4 — 概率统计模块示例

提供概率论与数理统计核心功能：
  - 概率分布：正态分布、二项分布、泊松分布、指数分布
  - 假设检验：Z 检验、t 检验、卡方检验
  - 回归分析：线性回归、多项式回归
  - 统计量：均值、方差、标准差、相关系数

数学表达：
  所有函数遵循概率论与数理统计定义。

用法：
  from src.stdlib.probability_stats import (
      NormalDistribution,
      z_test, t_test, chi_square_test,
      linear_regression,
      correlation,
  )
"""
from __future__ import annotations
import math
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum, auto


# ============================================================
# 概率分布
# ============================================================

class Distribution(Enum):
    """概率分布类型。"""
    NORMAL = auto()           # 正态分布
    BINOMIAL = auto()         # 二项分布
    POISSON = auto()          # 泊松分布
    EXPONENTIAL = auto()      # 指数分布
    UNIFORM = auto()          # 均匀分布


@dataclass
class NormalDistribution:
    """
    正态分布：N(μ, σ²)

    概率密度函数：
      f(x) = (1/σ√(2π)) × exp(-(x-μ)²/(2σ²))

    用法：
      dist = NormalDistribution(mu=0, sigma=1)
      pdf = dist.pdf(1.0)       # 概率密度
      cdf = dist.cdf(1.0)       # 累积分布
      ppf = dist.ppf(0.95)      # 分位数
    """

    mu: float = 0.0           # 均值
    sigma: float = 1.0        # 标准差

    def __post_init__(self):
        """验证参数。"""
        if self.sigma <= 0:
            raise ValueError("标准差必须为正数")

    def pdf(self, x: float) -> float:
        """
        概率密度函数：P(X = x)

        数学定义：
          f(x) = (1/σ√(2π)) × exp(-(x-μ)²/(2σ²))
        """
        return (1 / (self.sigma * math.sqrt(2 * math.pi))) * \
               math.exp(-((x - self.mu) ** 2) / (2 * self.sigma ** 2))

    def cdf(self, x: float) -> float:
        """
        累积分布函数：P(X ≤ x)

        使用误差函数近似计算。
        """
        z = (x - self.mu) / (self.sigma * math.sqrt(2))
        return 0.5 * (1 + math.erf(z))

    def ppf(self, p: float) -> float:
        """
        分位数函数：F^(-1)(p)

        找到 x 使得 P(X ≤ x) = p

        Args:
            p: 概率值 (0, 1)

        Returns:
            分位数
        """
        # 使用近似公式
        if p <= 0 or p >= 1:
            raise ValueError("概率必须在 (0, 1) 范围内")

        # Rational approximation for inverse normal CDF
        # Abramowitz and Stegun approximation 26.2.23
        if p < 0.5:
            t = math.sqrt(-2 * math.log(p))
            x = t - (2.515517 + 0.802853 * t + 0.010328 * t**2) / \
                      (1 + 1.432788 * t + 0.189269 * t**2 + 0.001308 * t**3)
        else:
            t = math.sqrt(-2 * math.log(1 - p))
            x = t - (2.515517 + 0.802853 * t + 0.010328 * t**2) / \
                      (1 + 1.432788 * t + 0.189269 * t**2 + 0.001308 * t**3)

        return self.mu + self.sigma * x

    def mean(self) -> float:
        """期望：E[X] = μ"""
        return self.mu

    def variance(self) -> float:
        """方差：Var(X) = σ²"""
        return self.sigma ** 2

    def std(self) -> float:
        """标准差：σ"""
        return self.sigma


@dataclass
class BinomialDistribution:
    """
    二项分布：B(n, p)

    概率质量函数：
      P(X = k) = C(n,k) × p^k × (1-p)^(n-k)

    用法：
      dist = BinomialDistribution(n=10, p=0.5)
      pmf = dist.pmf(5)      # P(X = 5)
      cdf = dist.cdf(5)       # P(X ≤ 5)
    """

    n: int = 10             # 试验次数
    p: float = 0.5          # 成功概率

    def __post_init__(self):
        """验证参数。"""
        if self.n <= 0:
            raise ValueError("试验次数必须为正整数")
        if not 0 <= self.p <= 1:
            raise ValueError("概率必须在 [0, 1] 范围内")

    def pmf(self, k: int) -> float:
        """
        概率质量函数：P(X = k)
        """
        if k < 0 or k > self.n:
            return 0.0
        return math.comb(self.n, k) * (self.p ** k) * ((1 - self.p) ** (self.n - k))

    def cdf(self, k: int) -> float:
        """
        累积分布函数：P(X ≤ k)
        """
        return sum(self.pmf(i) for i in range(k + 1))

    def mean(self) -> float:
        """期望：E[X] = np"""
        return self.n * self.p

    def variance(self) -> float:
        """方差：Var(X) = np(1-p)"""
        return self.n * self.p * (1 - self.p)


# ============================================================
# 泊松分布
# ============================================================

@dataclass
class PoissonDistribution:
    """
    泊松分布：Poisson(λ)

    概率质量函数：
      P(X = k) = (λ^k × e^(-λ)) / k!

    用法：
      dist = PoissonDistribution(lambda_=3.0)
      pmf = dist.pmf(2)      # P(X = 2)
      cdf = dist.cdf(2)       # P(X ≤ 2)
    """

    lambda_: float = 1.0      # 率参数 λ > 0

    def __post_init__(self):
        """验证参数。"""
        if self.lambda_ <= 0:
            raise ValueError("率参数 λ 必须为正数")

    def pmf(self, k: int) -> float:
        """
        概率质量函数：P(X = k)

        数学定义：
          P(X = k) = (λ^k × e^(-λ)) / k!
        """
        if k < 0:
            return 0.0
        return (self.lambda_ ** k) * math.exp(-self.lambda_) / math.factorial(k)

    def cdf(self, k: int) -> float:
        """
        累积分布函数：P(X ≤ k)
        """
        return sum(self.pmf(i) for i in range(k + 1))

    def mean(self) -> float:
        """期望：E[X] = λ"""
        return self.lambda_

    def variance(self) -> float:
        """方差：Var(X) = λ"""
        return self.lambda_

    def std(self) -> float:
        """标准差：σ = √λ"""
        return math.sqrt(self.lambda_)


# ============================================================
# 指数分布
# ============================================================

@dataclass
class ExponentialDistribution:
    """
    指数分布：Exp(λ)

    概率密度函数：
      f(x) = λ × e^(-λx), x ≥ 0

    用法：
      dist = ExponentialDistribution(lambda_=1.0)
      pdf = dist.pdf(1.0)       # 概率密度
      cdf = dist.cdf(1.0)       # 累积分布
    """

    lambda_: float = 1.0      # 率参数 λ > 0

    def __post_init__(self):
        """验证参数。"""
        if self.lambda_ <= 0:
            raise ValueError("率参数 λ 必须为正数")

    def pdf(self, x: float) -> float:
        """
        概率密度函数：f(x) = λ × e^(-λx), x ≥ 0
        """
        if x < 0:
            return 0.0
        return self.lambda_ * math.exp(-self.lambda_ * x)

    def cdf(self, x: float) -> float:
        """
        累积分布函数：F(x) = 1 - e^(-λx), x ≥ 0
        """
        if x < 0:
            return 0.0
        return 1.0 - math.exp(-self.lambda_ * x)

    def ppf(self, p: float) -> float:
        """
        分位数函数：F^(-1)(p) = -ln(1-p) / λ

        Args:
            p: 概率值 (0, 1)

        Returns:
            分位数
        """
        if p <= 0 or p >= 1:
            raise ValueError("概率必须在 (0, 1) 范围内")
        return -math.log(1 - p) / self.lambda_

    def mean(self) -> float:
        """期望：E[X] = 1/λ"""
        return 1.0 / self.lambda_

    def variance(self) -> float:
        """方差：Var(X) = 1/λ²"""
        return 1.0 / (self.lambda_ ** 2)

    def std(self) -> float:
        """标准差：σ = 1/λ"""
        return 1.0 / self.lambda_


# ============================================================
# 均匀分布
# ============================================================

@dataclass
class UniformDistribution:
    """
    连续均匀分布：U(a, b)

    概率密度函数：
      f(x) = 1/(b-a), a ≤ x ≤ b

    用法：
      dist = UniformDistribution(a=0, b=1)
      pdf = dist.pdf(0.5)       # 概率密度
      cdf = dist.cdf(0.5)       # 累积分布
    """

    a: float = 0.0            # 下界
    b: float = 1.0            # 上界

    def __post_init__(self):
        """验证参数。"""
        if self.a >= self.b:
            raise ValueError("下界 a 必须小于上界 b")

    def pdf(self, x: float) -> float:
        """
        概率密度函数：f(x) = 1/(b-a), a ≤ x ≤ b
        """
        if x < self.a or x > self.b:
            return 0.0
        return 1.0 / (self.b - self.a)

    def cdf(self, x: float) -> float:
        """
        累积分布函数：F(x) = (x-a)/(b-a), a ≤ x ≤ b
        """
        if x < self.a:
            return 0.0
        if x > self.b:
            return 1.0
        return (x - self.a) / (self.b - self.a)

    def ppf(self, p: float) -> float:
        """
        分位数函数：F^(-1)(p) = a + p(b-a)

        Args:
            p: 概率值 [0, 1]

        Returns:
            分位数
        """
        if p < 0 or p > 1:
            raise ValueError("概率必须在 [0, 1] 范围内")
        return self.a + p * (self.b - self.a)

    def mean(self) -> float:
        """期望：E[X] = (a+b)/2"""
        return (self.a + self.b) / 2.0

    def variance(self) -> float:
        """方差：Var(X) = (b-a)²/12"""
        return ((self.b - self.a) ** 2) / 12.0

    def std(self) -> float:
        """标准差：σ = (b-a)/√12"""
        return (self.b - self.a) / math.sqrt(12)

    def sample(self, n: int = 1) -> List[float]:
        """
        生成随机样本

        Args:
            n: 样本数量

        Returns:
            样本列表
        """
        import random
        return [random.uniform(self.a, self.b) for _ in range(n)]


# ============================================================
# 统计量计算
# ============================================================

def mean(data: List[float]) -> float:
    """
    样本均值：x̄ = (1/n)Σx_i

    Args:
        data: 样本数据

    Returns:
        均值
    """
    if not data:
        raise ValueError("数据不能为空")
    return sum(data) / len(data)


def variance(data: List[float], ddof: int = 1) -> float:
    """
    样本方差：s² = Σ(x_i - x̄)² / (n - ddof)

    Args:
        data: 样本数据
        ddof: 自由度修正（默认 1，样本方差）

    Returns:
        方差
    """
    if len(data) <= ddof:
        raise ValueError("样本量必须大于自由度修正")
    m = mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - ddof)


def std(data: List[float], ddof: int = 1) -> float:
    """
    样本标准差：s = √s²

    Args:
        data: 样本数据
        ddof: 自由度修正

    Returns:
        标准差
    """
    return math.sqrt(variance(data, ddof))


def correlation(x: List[float], y: List[float]) -> float:
    """
    皮尔逊相关系数：r = cov(X,Y) / (σ_X × σ_Y)

    数学定义：
      r = Σ(x_i - x̄)(y_i - ȳ) / √(Σ(x_i - x̄)² × Σ(y_i - ȳ)²)

    Args:
        x: 变量 X 的数据
        y: 变量 Y 的数据

    Returns:
        相关系数 (-1 到 1)
    """
    if len(x) != len(y):
        raise ValueError("两个变量长度必须相同")
    if len(x) < 2:
        raise ValueError("样本量必须至少为 2")

    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = math.sqrt(sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y))

    if den == 0:
        return 0.0
    return num / den


# ============================================================
# 假设检验
# ============================================================

def z_test(sample: List[float], population_mean: float,
           population_std: Optional[float] = None,
           sample_std: Optional[float] = None) -> Tuple[float, float]:
    """
    Z 检验：检验样本均值与总体均值的差异

    数学定义：
      Z = (x̄ - μ) / (σ/√n)

    当总体标准差已知时使用。

    Args:
        sample: 样本数据
        population_mean: 总体均值 μ
        population_std: 总体标准差 σ（可选）
        sample_std: 样本标准差 s（当 population_std 未知时使用）

    Returns:
        (z_statistic, p_value)

    Examples:
        # 检验样本均值是否等于 100
        sample = [98, 102, 100, 99, 101]
        z, p = z_test(sample, population_mean=100, population_std=5)
    """
    n = len(sample)
    if n < 1:
        raise ValueError("样本不能为空")

    sample_mean = mean(sample)

    # 确定标准差
    if population_std is not None:
        std = population_std
    elif sample_std is not None:
        std = sample_std
    else:
        std = std(sample, ddof=0)

    # 计算 Z 统计量
    z = (sample_mean - population_mean) / (std / math.sqrt(n))

    # 计算 p 值（双尾检验）
    p_value = 2 * (1 - NormalDistribution(0, 1).cdf(abs(z)))

    return z, p_value


def t_test(sample: List[float], population_mean: float = 0) -> Tuple[float, float]:
    """
    t 检验：检验样本均值与假设均值的差异

    数学定义：
      t = (x̄ - μ) / (s/√n)

    当总体标准差未知时使用。

    Args:
        sample: 样本数据
        population_mean: 假设的总体均值（默认 0）

    Returns:
        (t_statistic, p_value)
    """
    n = len(sample)
    if n < 2:
        raise ValueError("样本量必须至少为 2")

    sample_mean = mean(sample)
    sample_std = std(sample)

    # 计算 t 统计量
    t = (sample_mean - population_mean) / (sample_std / math.sqrt(n))

    # 计算 p 值（双尾检验，使用正态近似）
    # 精确计算需要 t 分布，这里用正态近似
    p_value = 2 * (1 - NormalDistribution(0, 1).cdf(abs(t)))

    return t, p_value


def chi_square_test(observed: List[int], expected: Optional[List[float]] = None) -> Tuple[float, float]:
    """
    卡方检验：检验观测频数与期望频数的差异

    数学定义：
      χ² = Σ(O_i - E_i)² / E_i

    Args:
        observed: 观测频数
        expected: 期望频数（可选，默认等概率）

    Returns:
        (chi_square_statistic, p_value)
    """
    n = len(observed)
    if n < 2:
        raise ValueError("类别数必须至少为 2")

    # 计算期望频数（默认等概率）
    if expected is None:
        total = sum(observed)
        expected = [total / n] * n
    elif len(expected) != n:
        raise ValueError("期望频数长度必须与观测频数相同")

    # 计算卡方统计量
    chi_square = sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)

    # 自由度
    df = n - 1

    # 计算 p 值（使用卡方分布近似）
    # 这里使用正态近似，精确计算需要卡方分布
    p_value = 1 - _chi_square_cdf(chi_square, df)

    return chi_square, p_value


def _chi_square_cdf(x: float, k: int) -> float:
    """
    卡方分布累积分布函数（近似）。
    """
    if x <= 0:
        return 0.0

    # 使用正则化下不完全伽马函数近似
    # P(k/2, x/2)
    a = k / 2.0
    z = x / 2.0

    # 连分数展开
    if z < a + 1:
        return _lower_incomplete_gamma(a, z) / math.gamma(a)
    else:
        return 1.0 - _upper_incomplete_gamma(a, z) / math.gamma(a)


def _lower_incomplete_gamma(a: float, x: float) -> float:
    """下不完全伽马函数（连分数展开）。"""
    if x < 0:
        return 0.0
    if x == 0:
        return 0.0

    # 连分数展开
    ap = a
    denom = 1.0
    num = 1.0
    result = 1.0

    for _ in range(100):
        ap += 1.0
        denom += x
        num *= x / ap
        term = num / denom
        result += term
        if abs(term) < 1e-10:
            break

    return result * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _upper_incomplete_gamma(a: float, x: float) -> float:
    """上不完全伽马函数（连分数展开）。"""
    if x <= 0:
        return math.gamma(a)

    # 连分数展开（改进的 Lentz 算法）
    f = 1.0
    c = 1.0
    d = 0.0

    for i in range(1, 100):
        if i % 2 == 0:
            an = (i // 2) - a + 1.0
        else:
            an = -x
            bn = i - a + 1.0

        d = bn + an * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = bn + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        f *= delta
        if abs(delta - 1.0) < 1e-10:
            break

    return math.exp(-x + a * math.log(x) - math.lgamma(a)) / f


# ============================================================
# 回归分析
# ============================================================

@dataclass
class RegressionResult:
    """回归分析结果。"""
    coefficients: List[float]           # 回归系数
    r_squared: float                    # R² 决定系数
    standard_error: float               # 标准误差
    predicted: List[float]              # 预测值
    residuals: List[float]              # 残差


def linear_regression(x: List[float], y: List[float]) -> RegressionResult:
    """
    一元线性回归：y = β₀ + β₁x + ε

    数学定义：
      β₁ = Σ(x_i - x̄)(y_i - ȳ) / Σ(x_i - x̄)²
      β₀ = ȳ - β₁x̄

    Args:
        x: 自变量数据
        y: 因变量数据

    Returns:
        回归结果

    Examples:
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 5, 4, 5]
        result = linear_regression(x, y)
        print(f"y = {result.coefficients[1]:.4f}x + {result.coefficients[0]:.4f}")
        print(f"R² = {result.r_squared:.4f}")
    """
    n = len(x)
    if n != len(y):
        raise ValueError("x 和 y 长度必须相同")
    if n < 2:
        raise ValueError("样本量必须至少为 2")

    mx, my = mean(x), mean(y)

    # 计算回归系数
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = sum((xi - mx) ** 2 for xi in x)

    if den == 0:
        beta1 = 0
    else:
        beta1 = num / den

    beta0 = my - beta1 * mx

    # 预测值和残差
    predicted = [beta0 + beta1 * xi for xi in x]
    residuals = [yi - pi for yi, pi in zip(y, predicted)]

    # 计算 R²
    ss_res = sum(r ** 2 for r in residuals)
    ss_tot = sum((yi - my) ** 2 for yi in y)

    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # 标准误差
    std_error = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0

    return RegressionResult(
        coefficients=[beta0, beta1],
        r_squared=r_squared,
        standard_error=std_error,
        predicted=predicted,
        residuals=residuals
    )


def polynomial_regression(x: List[float], y: List[float], degree: int = 2) -> RegressionResult:
    """
    多项式回归：y = β₀ + β₁x + β₂x² + ... + β_dx^d

    数学定义：
      通过最小二乘法求解回归系数

    Args:
        x: 自变量数据
        y: 因变量数据
        degree: 多项式次数

    Returns:
        回归结果
    """
    n = len(x)
    if n != len(y):
        raise ValueError("x 和 y 长度必须相同")
    if degree < 1:
        raise ValueError("多项式次数必须至少为 1")
    if n <= degree:
        raise ValueError("样本量必须大于多项式次数")

    # 构建设计矩阵
    X = [[xi ** j for j in range(degree + 1)] for xi in x]

    # 求解正规方程：(X^T X) β = X^T y
    XtX = _matrix_transpose_multiply(X)
    Xty = _matrix_vector_multiply_transpose(X, y)

    # 高斯消元求解
    coefficients = _solve_linear_system(XtX, Xty)

    # 预测值和残差
    predicted = [_matrix_vector_multiply(X, coefficients, i) for i in range(n)]
    residuals = [y[i] - predicted[i] for i in range(n)]

    # 计算 R²
    my = mean(y)
    ss_res = sum(r ** 2 for r in residuals)
    ss_tot = sum((yi - my) ** 2 for yi in y)

    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # 标准误差
    std_error = math.sqrt(ss_res / (n - degree - 1)) if n > degree + 1 else 0.0

    return RegressionResult(
        coefficients=coefficients,
        r_squared=r_squared,
        standard_error=std_error,
        predicted=predicted,
        residuals=residuals
    )


def _matrix_transpose_multiply(A: List[List[float]]) -> List[List[float]]:
    """矩阵转置乘矩阵。"""
    m, n = len(A), len(A[0])
    result = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(m):
                result[i][j] += A[k][i] * A[k][j]
    return result


def _matrix_vector_multiply_transpose(A: List[List[float]], v: List[float]) -> List[float]:
    """矩阵转置乘向量。"""
    n = len(A[0])
    result = [0.0] * n
    for i in range(n):
        for k in range(len(A)):
            result[i] += A[k][i] * v[k]
    return result


def _solve_linear_system(A: List[List[float]], b: List[float]) -> List[float]:
    """高斯消元求解线性方程组。"""
    n = len(b)
    # 增广矩阵
    aug = [A[i][:] + [b[i]] for i in range(n)]

    # 消元
    for col in range(n):
        # 找主元
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row
        aug[col], aug[max_row] = aug[max_row], aug[col]

        # 归一化
        pivot = aug[col][col]
        for j in range(n + 1):
            aug[col][j] /= pivot

        # 消元
        for row in range(n):
            if row != col:
                factor = aug[row][col]
                for j in range(n + 1):
                    aug[row][j] -= factor * aug[col][j]

    return [aug[i][n] for i in range(n)]


def _matrix_vector_multiply(A: List[List[float]], v: List[float], row_idx: int) -> float:
    """矩阵乘向量（指定行）。"""
    return sum(A[row_idx][j] * v[j] for j in range(len(v)))


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 概率统计模块示例")
    print("=" * 60)

    # 1. 正态分布
    print("\n【正态分布】")
    dist = NormalDistribution(mu=0, sigma=1)
    print(f"  N(0, 1) 在 x=1 处的概率密度: {dist.pdf(1.0):.6f}")
    print(f"  N(0, 1) 在 x=1 处的累积概率: {dist.cdf(1.0):.6f}")
    print(f"  N(0, 1) 的 95% 分位数: {dist.ppf(0.95):.6f}")

    # 2. 二项分布
    print("\n【二项分布】")
    binom = BinomialDistribution(n=10, p=0.5)
    print(f"  B(10, 0.5) 的 P(X=5) = {binom.pmf(5):.6f}")
    print(f"  B(10, 0.5) 的 P(X≤5) = {binom.cdf(5):.6f}")

    # 3. 假设检验
    print("\n【假设检验】")
    sample = [98, 102, 100, 99, 101, 103, 97, 100]
    z_stat, z_p = z_test(sample, population_mean=100, population_std=3)
    print(f"  Z 检验: Z = {z_stat:.4f}, p = {z_p:.6f}")

    t_stat, t_p = t_test(sample, population_mean=100)
    print(f"  t 检验: t = {t_stat:.4f}, p = {t_p:.6f}")

    # 4. 回归分析
    print("\n【回归分析】")
    x_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y_data = [2.1, 3.9, 6.2, 8.1, 9.8, 12.1, 14.2, 15.9, 18.1, 20.0]

    result = linear_regression(x_data, y_data)
    print(f"  线性回归: y = {result.coefficients[1]:.4f}x + {result.coefficients[0]:.4f}")
    print(f"  R² = {result.r_squared:.6f}")
    print(f"  标准误差 = {result.standard_error:.6f}")

    # 5. 多项式回归
    print("\n【多项式回归】")
    result_poly = polynomial_regression(x_data, y_data, degree=2)
    coeffs = result_poly.coefficients
    print(f"  二次回归: y = {coeffs[2]:.4f}x² + {coeffs[1]:.4f}x + {coeffs[0]:.4f}")
    print(f"  R² = {result_poly.r_squared:.6f}")

    # 6. 相关系数
    print("\n【相关系数】")
    r = correlation(x_data, y_data)
    print(f"  相关系数 r = {r:.6f}")

    print("\n" + "=" * 60)
    print("  概率统计模块测试完成")
    print("=" * 60)
