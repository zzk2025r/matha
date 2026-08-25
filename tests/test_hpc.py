# -*- coding: utf-8 -*-
"""HPC 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.hpc import (
    _Amdahl加速比, _并行效率, _通信延迟估算,
    _负载均衡度, _内存带宽利用率, _浮点运算峰值,
)


class TestHPC(unittest.TestCase):
    def test_amdahl_speedup(self):
        s = _Amdahl加速比(0.9, 4)
        self.assertGreater(s, 1)
        self.assertLess(s, 10)

    def test_parallel_efficiency(self):
        eff = _并行效率(3.5, 4)
        self.assertGreater(eff, 0)
        self.assertLess(eff, 100)

    def test_communication_latency(self):
        lat = _通信延迟估算(100, 1024, 10)
        self.assertGreater(lat, 0)

    def test_load_balance(self):
        lb = _负载均衡度([10, 20, 30, 40])
        self.assertGreater(lb, 0)

    def test_memory_bandwidth_util(self):
        util = _内存带宽利用率(1000, 1, 0.1)
        self.assertGreater(util, 0)

    def test_peak_flops(self):
        flops = _浮点运算峰值(8, 3.5, 16)
        self.assertGreater(flops, 0)


if __name__ == '__main__':
    unittest.main()
