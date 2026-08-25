# -*- coding: utf-8 -*-
"""GreenTech 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.green_tech import (
    _碳足迹估算, _能源效率, _太阳能转化率,
    _风力发电系数, _电池循环寿命, _减排量计算,
)


class TestGreenTech(unittest.TestCase):
    def test_carbon_footprint(self):
        cf = _碳足迹估算(1000, 0.5)
        self.assertGreater(cf, 0)

    def test_energy_efficiency(self):
        eff = _能源效率(80, 100)
        self.assertAlmostEqual(eff, 80.0, delta=0.1)

    def test_solar_conversion(self):
        sc = _太阳能转化率(1000, 1, 0.20)
        self.assertGreater(sc, 0)

    def test_wind_capacity(self):
        wc = _风力发电系数(10, 50, 1.225)
        self.assertGreater(wc, 0)

    def test_battery_life(self):
        bl = _电池循环寿命(0.0002, 0.8)
        self.assertGreater(bl, 0)

    def test_emission_reduction(self):
        er = _减排量计算(1000, 0.5, 0.1)
        self.assertGreater(er, 0)


if __name__ == '__main__':
    unittest.main()
