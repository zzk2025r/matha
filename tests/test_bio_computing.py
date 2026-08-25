# -*- coding: utf-8 -*-
"""Bio Computing 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.bio_computing import (
    _GC含量计算, _分子质量估算, _蛋白折叠能量,
    _序列比对得分, _系统稳定性, _代谢通量,
)


class TestBioComputing(unittest.TestCase):
    def test_gc_content(self):
        gc = _GC含量计算('ATCGATCG')
        self.assertAlmostEqual(gc, 50.0, delta=0.1)

    def test_molecular_mass(self):
        mm = _分子质量估算('ACDEFGHIK')
        self.assertGreater(mm, 0)

    def test_protein_folding_energy(self):
        e = _蛋白折叠能量(100, 0.5)
        self.assertLess(e, 0)

    def test_sequence_alignment(self):
        score = _序列比对得分('ACGT', 'ACGT', 2, -1, -2)
        self.assertGreaterEqual(score, 0)

    def test_system_stability(self):
        stab = _系统稳定性(1.0, 0.1, 0.5)
        self.assertGreater(stab, 0)

    def test_metabolic_flux(self):
        flux = _代谢通量(1.0, 0.1, 10, 1.0)
        self.assertGreater(flux, 0)


if __name__ == '__main__':
    unittest.main()
