# -*- coding: utf-8 -*-
"""Algorithmic Trading 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.algo_trading import (
    _策略夏普比率, _最大回撤估算, _订单执行成本,
    _滑点估算, _波动率预测, _相关性矩阵,
)


class TestAlgoTrading(unittest.TestCase):
    def test_sharpe_ratio(self):
        returns = [0.01, -0.02, 0.03, 0.01, -0.01]
        sr = _策略夏普比率(returns, 0.02 / 252)
        self.assertIsInstance(sr, float)

    def test_max_drawdown(self):
        nav = [100, 110, 105, 120, 110, 130]
        dd = _最大回撤估算(nav)
        self.assertGreaterEqual(dd, 0)
        self.assertLessEqual(dd, 100)

    def test_order_cost(self):
        cost = _订单执行成本(10000, 0.001, 0.05)
        self.assertGreater(cost, 0)

    def test_slippage_estimate(self):
        slip = _滑点估算(1000000, 50000000, 0.02)
        self.assertGreaterEqual(slip, 0)

    def test_volatility_forecast(self):
        returns = [0.01, -0.01, 0.02, -0.02, 0.01]
        vol = _波动率预测(returns, 20)
        self.assertGreater(vol, 0)

    def test_correlation_matrix(self):
        cov = _相关性矩阵([1, 2, 3], [4, 5, 6])
        self.assertIsInstance(cov, float)


if __name__ == '__main__':
    unittest.main()
