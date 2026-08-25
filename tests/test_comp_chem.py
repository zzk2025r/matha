# -*- coding: utf-8 -*-
"""CompChem 计算化学领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.comp_chem import (
    _分子轨道能量, _反应活化能, _键长计算,
    _振动频率, _热力学稳定性, _溶剂化能,
)


class TestCompChem(unittest.TestCase):
    def test_molecular_orbital_energy(self):
        e = _分子轨道能量(1, 1)
        self.assertLess(e, 0)

    def test_reaction_activation(self):
        ea = _反应活化能(300, 1e12, 1e-3)
        self.assertGreater(ea, 0)

    def test_bond_length(self):
        bl = _键长计算(0.7, 0.7, 1)
        self.assertGreater(bl, 0)

    def test_vibration_frequency(self):
        vf = _振动频率(500, 1e-26)
        self.assertGreater(vf, 0)

    def test_thermodynamic_stability(self):
        ts = _热力学稳定性(-200, 100, 298)
        self.assertIsInstance(ts, float)

    def test_solvation_energy(self):
        se = _溶剂化能(-1, 1.5, 80)
        self.assertIsInstance(se, float)


if __name__ == '__main__':
    unittest.main()
