# -*- coding: utf-8 -*-
"""电气工程专业测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.electrical import (
    _欧姆定律, _电功率, _电功率_R,
    _分压公式, _分流公式, _串联电阻, _并联电阻,
    _感抗, _容抗, _RLC阻抗, _谐振频率, _功率因数,
    _库仑力, _电场强度, _长直导线磁场, _通电导线受力,
    _RC截止频率, _RL截止频率, _傅里叶频率分辨率, _采样定理_min_rate,
)


class TestElectrical(unittest.TestCase):
    # ---- 电路分析 ----

    def test_欧姆定律(self):
        self.assertAlmostEqual(_欧姆定律(10, 5), 2.0)

    def test_欧姆定律短路(self):
        self.assertEqual(_欧姆定律(10, 0), float('inf'))

    def test_电功率(self):
        self.assertAlmostEqual(_电功率(12, 2), 24.0)

    def test_电功率_R(self):
        self.assertAlmostEqual(_电功率_R(10, 5), 20.0)

    def test_分压公式(self):
        self.assertAlmostEqual(_分压公式(10, 100, 100), 5.0)

    def test_分流公式(self):
        self.assertAlmostEqual(_分流公式(10, 100, 100), 5.0)

    def test_串联电阻(self):
        self.assertEqual(_串联电阻(10, 20, 30), 60)

    def test_并联电阻(self):
        self.assertAlmostEqual(_并联电阻(10, 10), 5.0)

    # ---- 交流电路 ----

    def test_感抗(self):
        self.assertAlmostEqual(_感抗(50, 0.1), 31.4159, places=4)

    def test_容抗(self):
        self.assertAlmostEqual(_容抗(50, 1e-6), 3183.1, places=0)

    def test_RLC阻抗(self):
        Z = _RLC阻抗(10, 0.1, 1e-6, 50)
        self.assertGreater(Z, 0)

    def test_谐振频率(self):
        f0 = _谐振频率(1e-3, 1e-6)
        self.assertAlmostEqual(f0, 5032.9, places=0)

    def test_功率因数(self):
        self.assertAlmostEqual(_功率因数(10, 6), 0.6)

    # ---- 电磁场 ----

    def test_库仑力(self):
        F = _库仑力(1e-6, 1e-6, 0.1)
        self.assertGreater(F, 0)

    def test_电场强度(self):
        E = _电场强度(1e-6, 0.1)
        self.assertGreater(E, 0)

    def test_长直导线磁场(self):
        B = _长直导线磁场(10, 0.01)
        self.assertAlmostEqual(B, 2e-4, places=6)

    def test_安培力(self):
        F = _通电导线受力(0.5, 10, 0.1, 90)
        self.assertAlmostEqual(F, 0.5)

    # ---- 信号与系统 ----

    def test_RC截止频率(self):
        self.assertAlmostEqual(_RC截止频率(1000, 1e-6), 159.15, places=2)

    def test_RL截止频率(self):
        self.assertAlmostEqual(_RL截止频率(100, 0.01), 1591.5, places=1)

    def test_频率分辨率(self):
        self.assertAlmostEqual(_傅里叶频率分辨率(1000, 1024), 0.9766, places=4)

    def test_奈奎斯特速率(self):
        self.assertEqual(_采样定理_min_rate(1000), 2000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
