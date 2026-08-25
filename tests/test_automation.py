# -*- coding: utf-8 -*-
"""Automation 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.automation import (
    _PLC扫描周期估算, _传感器采样率, _执行器响应时间,
    _时序约束满足, _自动化流程执行效率, _异常检测率,
)


class TestAutomation(unittest.TestCase):
    def test_plc_scan(self):
        result = _PLC扫描周期估算(32, 1000, 100)
        self.assertGreater(result, 0)

    def test_sensor_sample_rate(self):
        rate = _传感器采样率(1e-6, 10000, 16)
        self.assertGreater(rate, 0)

    def test_actuator_response(self):
        t = _执行器响应时间('servo', 5, 100)
        self.assertGreater(t, 0)

    def test_timing_constraint(self):
        ok = _时序约束满足(10, 5, 1)
        self.assertTrue(ok)

    def test_efficiency(self):
        eff = _自动化流程执行效率(10, 100, 2)
        self.assertGreater(eff, 0)

    def test_error_detection(self):
        rate = _异常检测率(0.01, 0.05, 1000)
        self.assertGreater(rate, 0)


if __name__ == '__main__':
    unittest.main()
