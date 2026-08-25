# -*- coding: utf-8 -*-
"""扩展建模领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.extended_modeling import (
    _梁弯曲正应力, _梁弯曲挠度, _轴应力,
    _管道沿程损失, _雷诺数, _伯努利方程,
    _热传导, _对流换热, _辐射换热,
    _三相功率线电压, _变压器变比, _电机扭矩,
    _PID输出, _一阶惯性环节, _二阶系统参数,
    _胡克定律, _疲劳寿命,
)


class TestExtendedModeling(unittest.TestCase):
    # ---- 结构工程 ----

    def test_梁弯曲应力(self):
        sigma = _梁弯曲正应力(1000, 0.05, 1e-6)
        self.assertAlmostEqual(sigma, 50e6, places=0)

    def test_梁挠度_简支(self):
        d = _梁弯曲挠度(1000, 1, 200e9, 1e-6, 支座="简支")
        self.assertAlmostEqual(d, 6.51e-5, places=7)

    def test_轴扭转应力(self):
        tau = _轴应力(100, 0.02)
        self.assertAlmostEqual(tau, 63.66e6, delta=1e5)

    # ---- 流体力学 ----

    def test_雷诺数(self):
        Re = _雷诺数(1.0, 0.05)
        self.assertAlmostEqual(Re, 49800.8, places=0)

    def test_伯努利(self):
        p2 = _伯努利方程(0, 100000, 2, 0, rho=1000)
        self.assertAlmostEqual(p2, 100000 + 2000)

    # ---- 热力学 ----

    def test_热传导(self):
        k = _热传导(500, 1, 10, 0.1)
        self.assertAlmostEqual(k, 5.0)

    def test_对流换热(self):
        Q = _对流换热(10, 1, 100, 20)
        self.assertEqual(Q, 800)

    def test_辐射换热(self):
        Q = _辐射换热(0.9, 1, 400, 300)
        self.assertGreater(Q, 0)

    # ---- 电气工程 ----

    def test_三相功率(self):
        P = _三相功率线电压(380, 10, 0.8)
        self.assertAlmostEqual(P, 5265.4, places=1)

    def test_变压器变比(self):
        self.assertAlmostEqual(_变压器变比(200, 100), 2.0)

    def test_电机扭矩(self):
        T = _电机扭矩(0, 1500, 10)
        self.assertAlmostEqual(T, 63.67, places=2)

    # ---- 控制理论 ----

    def test_PID输出(self):
        u = _PID输出(1.0, 0.1, 0.01, 1.0, 0.5, -0.1)
        self.assertAlmostEqual(u, 1.049, places=3)

    def test_一阶响应(self):
        y = _一阶惯性环节(1.0, 1.0)
        self.assertAlmostEqual(y, 0.6321, places=4)

    def test_二阶指标(self):
        result = _二阶系统参数(0.5, 10)
        self.assertIn("超调量", result)
        self.assertIn("调节时间", result)
        self.assertGreater(result["超调量"], 0)

    # ---- 材料科学 ----

    def test_胡克定律(self):
        eps = _胡克定律(100e6, 200e9)
        self.assertAlmostEqual(eps, 0.0005)

    def test_疲劳寿命_high_stress(self):
        life = _疲劳寿命(200, 100)
        self.assertLess(life, 1000000)

    def test_疲劳寿命_low_stress(self):
        life = _疲劳寿命(50, 100)
        self.assertGreater(life, 1000000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
