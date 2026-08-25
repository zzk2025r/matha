# -*- coding: utf-8 -*-
"""经济学领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.economics import (
    _复利终值, _复利现值, _年金终值, _年金现值, _NPV, _IRR估算,
    _单利终值, _实际利率,
    _需求价格弹性, _供给价格弹性, _消费者剩余, _生产者剩余,
    _边际成本, _总成本,
    _GDP支出法, _GDP收入法, _乘数效应,
    _物价指数, _通货膨胀率, _人均GDP,
)


class TestEconomics(unittest.TestCase):
    # ---- 金融数学 ----

    def test_复利终值(self):
        self.assertAlmostEqual(_复利终值(1000, 0.05, 2), 1102.5)

    def test_复利现值(self):
        self.assertAlmostEqual(_复利现值(1102.5, 0.05, 2), 1000.0, places=5)

    def test_单利终值(self):
        self.assertEqual(_单利终值(1000, 0.05, 2), 1100.0)

    def test_年金终值(self):
        self.assertAlmostEqual(_年金终值(100, 0.05, 3), 315.25, places=2)

    def test_年金现值(self):
        self.assertAlmostEqual(_年金现值(100, 0.05, 3), 272.32, places=2)

    def test_NPV(self):
        self.assertAlmostEqual(_NPV([-100, 50, 60], 0.1), -4.96, places=2)

    def test_IRR(self):
        irr = _IRR估算([-100, 50, 60])
        self.assertGreater(irr, 0.06)
        self.assertLess(irr, 0.07)

    def test_实际利率(self):
        self.assertAlmostEqual(_实际利率(0.10, 0.03), 0.0680, places=4)

    # ---- 微观经济学 ----

    def test_需求价格弹性(self):
        self.assertAlmostEqual(_需求价格弹性(10, 100, -2), -0.2)

    def test_供给价格弹性(self):
        self.assertAlmostEqual(_供给价格弹性(10, 80, 3), 0.375)

    def test_消费者剩余(self):
        cs = _消费者剩余([100, 1], 50)
        self.assertAlmostEqual(cs, 1250.0)

    def test_生产者剩余(self):
        ps = _生产者剩余([0, 1], 50)
        self.assertAlmostEqual(ps, 1250.0)

    def test_边际成本(self):
        self.assertEqual(_边际成本(100, 500, 5), 5)

    def test_总成本(self):
        self.assertEqual(_总成本(100, 500, 5), 1000)

    # ---- 宏观经济学 ----

    def test_GDP支出法(self):
        self.assertEqual(_GDP支出法(500, 200, 100, 50, 30), 820)

    def test_GDP收入法(self):
        self.assertEqual(_GDP收入法(300, 100, 50, 50), 500)

    def test_乘数效应(self):
        self.assertAlmostEqual(_乘数效应(0.8), 5.0)

    def test_物价指数(self):
        self.assertAlmostEqual(_物价指数(100, 105), 105.0)

    def test_通货膨胀率(self):
        self.assertAlmostEqual(_通货膨胀率(100, 105), 5.0)

    def test_人均GDP(self):
        self.assertAlmostEqual(_人均GDP(50000, 10000), 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
