# -*- coding: utf-8 -*-
"""OS/Network 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.os_network import (
    _进程调度等待时间, _内存页表开销, _文件碎片率,
    _TCP重传率, _DNS查询延迟, _带宽利用率,
)


class TestOsNetwork(unittest.TestCase):
    def test_process_scheduling(self):
        t = _进程调度等待时间(10, 10, 4)
        self.assertGreater(t, 0)

    def test_page_table_overhead(self):
        oh = _内存页表开销(1024, 4)
        self.assertGreater(oh, 0)

    def test_file_fragmentation(self):
        fr = _文件碎片率(1000, 1000, 800)
        self.assertGreaterEqual(fr, 0)
        self.assertLessEqual(fr, 100)

    def test_tcp_retransmission(self):
        rate = _TCP重传率(0.01, 3)
        self.assertGreater(rate, 0)
        self.assertLess(rate, 1)

    def test_dns_latency(self):
        lat = _DNS查询延迟(100, 3)
        self.assertGreater(lat, 0)

    def test_bandwidth_utilization(self):
        util = _带宽利用率(500, 1000)
        self.assertGreaterEqual(util, 0)
        self.assertLessEqual(util, 100)


if __name__ == '__main__':
    unittest.main()
