# -*- coding: utf-8 -*-
"""Chemistry 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.chemistry import (
    _理想气体方程, _pH计算, _摩尔质量,
    _平衡常数, _Arrhenius方程, _不饱和度,
)


class TestChemistry(unittest.TestCase):
    def test_ideal_gas_law(self):
        # P in Pa: n=1, V=0.0224 m3, T=273.15K -> P = 1*8.314*273.15/0.0224 ≈ 101325 Pa ≈ 1 atm
        P = _理想气体方程(None, 0.0224, 1, 273.15)
        self.assertAlmostEqual(P, 101325, delta=5000)

    def test_ph_calc(self):
        ph = _pH计算(1e-7)
        self.assertAlmostEqual(ph, 7.0, delta=0.1)

    def test_molar_mass(self):
        mw = _摩尔质量('H2O')
        self.assertAlmostEqual(mw, 18.015, delta=1)

    def test_equilibrium_const(self):
        k = _平衡常数(-90000, 298)
        self.assertGreater(k, 0)

    def test_arrhenius(self):
        k = _Arrhenius方程(1e12, 50000, 300)
        self.assertGreater(k, 0)

    def test_degree_of_unsaturation(self):
        du = _不饱和度('C6H6')
        self.assertEqual(du, 4.0)


if __name__ == '__main__':
    unittest.main()
