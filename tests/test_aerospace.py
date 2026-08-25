# -*- coding: utf-8 -*-
"""Aerospace 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.aerospace import (
    _轨道速度计算, _推进剂消耗率, _结构强度系数,
    _热防护质量, _再入角估算, _比冲,
)


class TestAerospace(unittest.TestCase):
    def test_orbit_velocity(self):
        v = _轨道速度计算(400)  # 400km
        self.assertGreater(v, 0)
        self.assertLess(v, 10000)

    def test_propellant_flow(self):
        rate = _推进剂消耗率(10000, 300)  # 10kN, 300s Isp
        self.assertGreater(rate, 0)
        self.assertAlmostEqual(rate, 3.39, delta=0.1)

    def test_structural_factor(self):
        sf = _结构强度系数(1000, 500)
        self.assertGreater(sf, 0)
        self.assertLess(sf, 10)

    def test_thermal_protection(self):
        mass = _热防护质量(1000, 100, 500)
        self.assertGreater(mass, 0)

    def test_reentry_angle(self):
        angle = _再入角估算(7500, 100000)
        self.assertGreater(angle, 0)
        self.assertLess(angle, 90)

    def test_specific_impulse(self):
        Isp = _比冲(10000, 3.39)
        self.assertAlmostEqual(Isp, 300, delta=1)


if __name__ == '__main__':
    unittest.main()
