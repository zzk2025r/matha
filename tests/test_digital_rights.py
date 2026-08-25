# -*- coding: utf-8 -*-
"""Digital Rights 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.digital_rights import (
    _水印嵌入强度, _版权保护指数, _访问控制粒度,
    _哈希碰撞概率, _密钥轮换周期, _数字指纹,
)


class TestDigitalRights(unittest.TestCase):
    def test_watermark_strength(self):
        s = _水印嵌入强度(1024, 100, 0.1)
        self.assertGreater(s, 0)

    def test_copyright_index(self):
        idx = _版权保护指数(10, 0.95, 1)
        self.assertGreater(idx, 0)

    def test_access_control_granularity(self):
        g = _访问控制粒度(5, 10, 3)
        self.assertGreater(g, 0)

    def test_hash_collision_prob(self):
        p = _哈希碰撞概率(256, 1000)
        self.assertGreaterEqual(p, 0)
        self.assertLess(p, 1)

    def test_key_rotation_period(self):
        period = _密钥轮换周期(256, 1e12)
        self.assertGreater(period, 0)

    def test_digital_fingerprint(self):
        fp = _数字指纹(b'test data')
        self.assertIsInstance(fp, str)


if __name__ == '__main__':
    unittest.main()
