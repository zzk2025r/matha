# -*- coding: utf-8 -*-
"""Metaverse Arch 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.metaverse_arch import (
    _渲染帧率估算, _物理模拟步长, _碰撞检测复杂度,
    _用户并发数, _资产加载延迟, _网络同步延迟,
)


class TestMetaverseArch(unittest.TestCase):
    def test_render_frame_rate(self):
        fps = _渲染帧率估算(100000, 921600, 100)
        self.assertGreater(fps, 0)

    def test_physics_step(self):
        step = _物理模拟步长(100, 50, 1000)
        self.assertGreater(step, 0)

    def test_collision_complexity(self):
        cx = _碰撞检测复杂度(100)
        self.assertGreater(cx, 0)

    def test_concurrent_users(self):
        users = _用户并发数(10, 0.5)
        self.assertGreater(users, 0)

    def test_asset_load_delay(self):
        delay = _资产加载延迟(100, 100, 0.5)
        self.assertGreater(delay, 0)

    def test_network_sync_latency(self):
        lat = _网络同步延迟(50, 10)
        self.assertGreater(lat, 0)


if __name__ == '__main__':
    unittest.main()
