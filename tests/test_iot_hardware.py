# -*- coding: utf-8 -*-
"""IoT Hardware 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.iot_hardware import (
    _MQTT消息大小估算, _传感器覆盖半径, _边缘延迟计算,
    _设备在线率, _数据聚合效率, _功耗预算,
)


class TestIotHardware(unittest.TestCase):
    def test_mqtt_message_size(self):
        size = _MQTT消息大小估算('test/topic', 100, 1)
        self.assertGreater(size, 0)

    def test_sensor_coverage_radius(self):
        r = _传感器覆盖半径(20, -90, 2.4)
        self.assertGreater(r, 0)

    def test_edge_latency(self):
        lat = _边缘延迟计算(10, 5, 20)
        self.assertGreater(lat, 0)

    def test_device_online_rate(self):
        rate = _设备在线率(100, 5, 24)
        self.assertGreaterEqual(rate, 0)
        self.assertLessEqual(rate, 1)

    def test_data_aggregation_efficiency(self):
        eff = _数据聚合效率(100, 10, 'gzip')
        self.assertGreater(eff, 0)

    def test_power_budget(self):
        budget = _功耗预算([(100, 0.5), (50, 0.8)])
        self.assertGreater(budget, 0)


if __name__ == '__main__':
    unittest.main()
