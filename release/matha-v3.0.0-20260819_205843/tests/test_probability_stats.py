# -*- coding: utf-8 -*-
"""Matha 概率统计学模块测试

测试概率分布：正态分布、二项分布、泊松分布、指数分布、均匀分布
测试统计量：均值、方差、标准差、相关系数
测试假设检验：Z 检验、t 检验、卡方检验
测试回归分析：线性回归、多项式回归
"""
import unittest
import math
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from stdlib.probability_stats import (
    NormalDistribution,
    BinomialDistribution,
    PoissonDistribution,
    ExponentialDistribution,
    UniformDistribution,
    mean,
    variance,
    std,
    correlation,
    z_test,
    t_test,
    chi_square_test,
    linear_regression,
)


class TestNormalDistribution(unittest.TestCase):
    """测试正态分布"""

    def test_pdf(self):
        """测试概率密度函数"""
        dist = NormalDistribution(mu=0, sigma=1)
        # 标准正态分布在 0 处的峰值
        self.assertAlmostEqual(dist.pdf(0), 1/math.sqrt(2*math.pi), places=5)

    def test_cdf(self):
        """测试累积分布函数"""
        dist = NormalDistribution(mu=0, sigma=1)
        # 正态分布的对称性
        self.assertAlmostEqual(dist.cdf(0), 0.5, places=5)
        self.assertAlmostEqual(dist.cdf(1) + dist.cdf(-1), 1.0, places=3)

    def test_ppf(self):
        """测试分位数函数"""
        dist = NormalDistribution(mu=0, sigma=1)
        # ppf(cdf(x)) ≈ x（由于数值精度）
        self.assertAlmostEqual(dist.ppf(dist.cdf(1.0)), 1.0, places=3)
        self.assertAlmostEqual(dist.ppf(dist.cdf(0.0)), 0.0, places=3)

    def test_mean_variance(self):
        """测试均值和方差"""
        dist = NormalDistribution(mu=5, sigma=2)
        self.assertAlmostEqual(dist.mean(), 5.0)
        self.assertAlmostEqual(dist.variance(), 4.0)
        self.assertAlmostEqual(dist.std(), 2.0)

    def test_invalid_sigma(self):
        """测试无效参数"""
        with self.assertRaises(ValueError):
            NormalDistribution(mu=0, sigma=0)
        with self.assertRaises(ValueError):
            NormalDistribution(mu=0, sigma=-1)


class TestBinomialDistribution(unittest.TestCase):
    """测试二项分布"""

    def test_pmf(self):
        """测试概率质量函数"""
        dist = BinomialDistribution(n=10, p=0.5)
        # P(X=5)
        self.assertAlmostEqual(dist.pmf(5), 0.24609, places=5)

    def test_cdf(self):
        """测试累积分布函数"""
        dist = BinomialDistribution(n=10, p=0.5)
        # P(X≤5) 应该大于 0.5
        self.assertGreater(dist.cdf(5), 0.5)

    def test_mean_variance(self):
        """测试均值和方差"""
        dist = BinomialDistribution(n=10, p=0.3)
        self.assertAlmostEqual(dist.mean(), 3.0)
        self.assertAlmostEqual(dist.variance(), 2.1)

    def test_invalid_params(self):
        """测试无效参数"""
        with self.assertRaises(ValueError):
            BinomialDistribution(n=0, p=0.5)
        with self.assertRaises(ValueError):
            BinomialDistribution(n=10, p=1.5)


class TestPoissonDistribution(unittest.TestCase):
    """测试泊松分布"""

    def test_pmf(self):
        """测试概率质量函数"""
        dist = PoissonDistribution(lambda_=3.0)
        # P(X=2) = 3² × e^(-3) / 2!
        expected = (3.0 ** 2) * math.exp(-3.0) / 2
        self.assertAlmostEqual(dist.pmf(2), expected, places=5)

    def test_cdf(self):
        """测试累积分布函数"""
        dist = PoissonDistribution(lambda_=3.0)
        # P(X≤2) = P(X=0) + P(X=1) + P(X=2)
        cdf = dist.cdf(2)
        self.assertGreater(cdf, 0.0)
        self.assertLess(cdf, 1.0)

    def test_mean_variance(self):
        """测试均值和方差（泊松分布的均值和方差相等）"""
        dist = PoissonDistribution(lambda_=5.0)
        self.assertAlmostEqual(dist.mean(), 5.0)
        self.assertAlmostEqual(dist.variance(), 5.0)
        self.assertAlmostEqual(dist.std(), math.sqrt(5.0))

    def test_invalid_lambda(self):
        """测试无效参数"""
        with self.assertRaises(ValueError):
            PoissonDistribution(lambda_=0)
        with self.assertRaises(ValueError):
            PoissonDistribution(lambda_=-1)

    def test_pmf_boundary(self):
        """测试边界情况"""
        dist = PoissonDistribution(lambda_=1.0)
        # k < 0 时返回 0
        self.assertEqual(dist.pmf(-1), 0.0)
        # P(X=0) = e^(-λ)
        self.assertAlmostEqual(dist.pmf(0), math.exp(-1.0), places=5)


class TestExponentialDistribution(unittest.TestCase):
    """测试指数分布"""

    def test_pdf(self):
        """测试概率密度函数"""
        dist = ExponentialDistribution(lambda_=1.0)
        # f(0) = λ = 1
        self.assertAlmostEqual(dist.pdf(0), 1.0)
        # f(x) = 0 for x < 0
        self.assertEqual(dist.pdf(-1), 0.0)

    def test_cdf(self):
        """测试累积分布函数"""
        dist = ExponentialDistribution(lambda_=1.0)
        # F(x) = 1 - e^(-x)
        self.assertAlmostEqual(dist.cdf(0), 0.0)
        self.assertAlmostEqual(dist.cdf(1), 1 - math.exp(-1), places=5)
        # F(x) = 0 for x < 0
        self.assertEqual(dist.cdf(-1), 0.0)

    def test_ppf(self):
        """测试分位数函数"""
        dist = ExponentialDistribution(lambda_=1.0)
        # ppf(0.5) = -ln(0.5) = ln(2)
        self.assertAlmostEqual(dist.ppf(0.5), math.log(2), places=5)

    def test_mean_variance(self):
        """测试均值和方差"""
        dist = ExponentialDistribution(lambda_=2.0)
        self.assertAlmostEqual(dist.mean(), 0.5)
        self.assertAlmostEqual(dist.variance(), 0.25)
        self.assertAlmostEqual(dist.std(), 0.5)

    def test_invalid_lambda(self):
        """测试无效参数"""
        with self.assertRaises(ValueError):
            ExponentialDistribution(lambda_=0)
        with self.assertRaises(ValueError):
            ExponentialDistribution(lambda_=-1)


class TestUniformDistribution(unittest.TestCase):
    """测试均匀分布"""

    def test_pdf(self):
        """测试概率密度函数"""
        dist = UniformDistribution(a=0, b=1)
        # U(0,1) 在 [0,1] 内的密度为 1
        self.assertAlmostEqual(dist.pdf(0.5), 1.0)
        # 在范围外为 0
        self.assertEqual(dist.pdf(2.0), 0.0)
        self.assertEqual(dist.pdf(-1.0), 0.0)

    def test_cdf(self):
        """测试累积分布函数"""
        dist = UniformDistribution(a=0, b=10)
        # F(x) = x/10 for 0≤x≤10
        self.assertAlmostEqual(dist.cdf(0), 0.0)
        self.assertAlmostEqual(dist.cdf(5), 0.5)
        self.assertAlmostEqual(dist.cdf(10), 1.0)
        # 范围外
        self.assertEqual(dist.cdf(-1), 0.0)
        self.assertEqual(dist.cdf(11), 1.0)

    def test_ppf(self):
        """测试分位数函数"""
        dist = UniformDistribution(a=0, b=10)
        # ppf(p) = 10p
        self.assertAlmostEqual(dist.ppf(0.0), 0.0)
        self.assertAlmostEqual(dist.ppf(0.5), 5.0)
        self.assertAlmostEqual(dist.ppf(1.0), 10.0)

    def test_mean_variance(self):
        """测试均值和方差"""
        dist = UniformDistribution(a=0, b=10)
        self.assertAlmostEqual(dist.mean(), 5.0)
        self.assertAlmostEqual(dist.variance(), 100/12, places=5)
        self.assertAlmostEqual(dist.std(), 10/math.sqrt(12), places=5)

    def test_sample(self):
        """测试采样"""
        dist = UniformDistribution(a=0, b=1)
        samples = dist.sample(100)
        self.assertEqual(len(samples), 100)
        # 所有样本应在 [0,1] 范围内
        for s in samples:
            self.assertTrue(0 <= s <= 1)

    def test_invalid_params(self):
        """测试无效参数"""
        with self.assertRaises(ValueError):
            UniformDistribution(a=1, b=0)
        with self.assertRaises(ValueError):
            UniformDistribution(a=0, b=0)


class TestStatistics(unittest.TestCase):
    """测试统计量计算"""

    def test_mean(self):
        """测试均值"""
        data = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(mean(data), 3.0)

    def test_variance(self):
        """测试方差"""
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        # 样本方差（ddof=1）
        self.assertAlmostEqual(variance(data, ddof=1), 4.571428571428571, places=5)

    def test_std(self):
        """测试标准差"""
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        self.assertAlmostEqual(std(data), math.sqrt(4.571428571428571), places=5)

    def test_correlation(self):
        """测试相关系数"""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 5, 4, 5]
        r = correlation(x, y)
        # 实际值约为 0.77
        self.assertAlmostEqual(r, 0.7746, places=4)

    def test_empty_data(self):
        """测试空数据"""
        with self.assertRaises(ValueError):
            mean([])
        with self.assertRaises(ValueError):
            variance([])


class TestHypothesisTesting(unittest.TestCase):
    """测试假设检验"""

    def test_z_test(self):
        """测试 Z 检验"""
        sample = [98, 102, 100, 99, 101]
        z, p = z_test(sample, population_mean=100, population_std=5)
        # Z 统计量接近 0（样本均值接近总体均值）
        self.assertLess(abs(z), 1)
        self.assertGreater(p, 0)
        # p 值可能在边界情况为 1.0
        self.assertLessEqual(p, 1.0)

    def test_t_test(self):
        """测试 t 检验"""
        sample = [98, 102, 100, 99, 101]
        t, p = t_test(sample, population_mean=100)
        self.assertLess(abs(t), 1)
        self.assertGreater(p, 0)

    def test_chi_square_test(self):
        """测试卡方检验"""
        observed = [20, 30, 50]
        chi2, p = chi_square_test(observed)
        self.assertGreater(chi2, 0)
        self.assertGreater(p, 0)
        self.assertLess(p, 1)


class TestRegression(unittest.TestCase):
    """测试回归分析"""

    def test_linear_regression(self):
        """测试线性回归"""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 5, 4, 5]
        result = linear_regression(x, y)
        # R² 应在 [0, 1] 范围内
        self.assertGreaterEqual(result.r_squared, 0)
        self.assertLessEqual(result.r_squared, 1)
        # 系数数量应为 2（截距 + 斜率）
        self.assertEqual(len(result.coefficients), 2)

    def test_predicted_values(self):
        """测试预测值"""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 5, 4, 5]
        result = linear_regression(x, y)
        # 预测值数量应与样本数相同
        self.assertEqual(len(result.predicted), 5)
        # 残差数量应与样本数相同
        self.assertEqual(len(result.residuals), 5)


if __name__ == '__main__':
    unittest.main()
