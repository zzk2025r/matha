# -*- coding: utf-8 -*-
"""Hardware 领域测试。"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.hardware import (
    _cpu_count, _memory_info, _platform_info,
    _exec_cmd, _ps, _socket_send,
    _http_get, _dns_resolve, _ping,
    _gpio_init, _gpio_set, _gpio_get, _gpio_cleanup,
    _file_exists, _file_size, _env_get,
)


class TestHardware(unittest.TestCase):
    def test_cpu_count(self):
        n = _cpu_count()
        self.assertGreater(n, 0)

    def test_memory_info(self):
        info = _memory_info()
        self.assertIsInstance(info, dict)

    def test_platform_info(self):
        info = _platform_info()
        self.assertIsInstance(info, str)

    def test_exec_cmd(self):
        result = _exec_cmd('echo hello', timeout=5)
        self.assertIsInstance(result, dict)

    def test_ps(self):
        procs = _ps()
        self.assertIsInstance(procs, list)

    def test_socket_send(self):
        result = _socket_send('127.0.0.1', 80, 'test', timeout=1)
        self.assertIsInstance(result, dict)

    def test_http_get(self):
        result = _http_get('http://localhost', timeout=1)
        self.assertIsInstance(result, dict)

    def test_dns_resolve(self):
        result = _dns_resolve('localhost')
        self.assertIsInstance(result, list)

    def test_ping(self):
        result = _ping('127.0.0.1', count=1)
        self.assertIsInstance(result, dict)

    def test_gpio_init_set(self):
        _gpio_init(17, 'out')
        _gpio_set(17, 1)
        _gpio_cleanup(17)

    def test_gpio_read_input(self):
        _gpio_init(18, 'in')
        val = _gpio_get(18)
        self.assertIsInstance(val, int)
        _gpio_cleanup(18)

    def test_file_exists(self):
        self.assertTrue(_file_exists('.'))

    def test_env_get(self):
        val = _env_get('PATH')
        self.assertIsInstance(val, str)


if __name__ == '__main__':
    unittest.main()
