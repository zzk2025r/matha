# -*- coding: utf-8 -*-
"""Fintech 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.fintech import (
    _BlackScholes期权定价, _VaR风险价值, _夏普比率,
    _信用评分, _流动性覆盖率, _杠杆率,
)


class TestFinTech(unittest.TestCase):
    def test_black_scholes(self):
        price = _BlackScholes期权定价(100, 105, 0.2, 0.05, 0.5)
        self.assertGreater(price, 0)

    def test_var(self):
        var = _VaR风险价值(1000000, 0.02, 0.95, 1)
        self.assertGreater(var, 0)

    def test_sharpe_ratio(self):
        sr = _夏普比率(0.05, 0.1)
        self.assertGreater(sr, 0)

    def test_credit_score(self):
        score = _信用评分(0.4, 0.8, 0, 5)
        self.assertGreater(score, 0)

    def test_liquidity_ratio(self):
        ratio = _流动性覆盖率(100, 80)
        self.assertGreater(ratio, 0)

    def test_leverage_ratio(self):
        ratio = _杠杆率(1000, 400)
        self.assertGreater(ratio, 0)
        self.assertLess(ratio, 100)


if __name__ == '__main__':
    unittest.main()
