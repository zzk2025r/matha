# -*- coding: utf-8 -*-
"""Hardware Reverse 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.hardware_reverse import (
    _信号频率分析, _协议解析率, _固件完整性校验,
    _逆向复杂度, _时钟频率估算, _功耗分析,
)


class TestHardwareReverse(unittest.TestCase):
    def test_signal_frequency(self):
        result = _信号频率分析(1000, 100)
        self.assertGreater(result, 0)

    def test_protocol_parse_rate(self):
        rate = _协议解析率(100, 95)
        self.assertAlmostEqual(rate, 95.0, delta=0.1)

    def test_firmware_integrity(self):
        ok = _固件完整性校验(10, True)
        self.assertTrue(ok)

    def test_reverse_complexity(self):
        cx = _逆向复杂度(10000, 500, 2000)
        self.assertGreater(cx, 0)

    def test_clock_frequency(self):
        freq = _时钟频率估算(1)
        self.assertAlmostEqual(freq, 1000000.0, delta=10000)

    def test_power_analysis(self):
        power = _功耗分析(3.3, 100, 0.5)
        self.assertGreater(power, 0)


if __name__ == '__main__':
    unittest.main()
