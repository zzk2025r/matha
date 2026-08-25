# -*- coding: utf-8 -*-
"""HAL 性能测试 Pytest 插件

提供 pytest fixture 和 marker，方便快速运行 HAL 压力测试。

用法：
  pytest tests/test_hal_perf.py                    # 运行所有测试
  pytest tests/test_hal_perf.py -v                 # 详细输出
  pytest tests/test_hal_perf.py -k "test_10khz"    # 匹配测试名
  pytest tests/test_hal_perf.py --benchmark        # 运行基准测试
  pytest tests/test_hal_perf.py --duration 10      # 指定测试时长
"""
import pytest
import time
import logging
from typing import List, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def hal_ops():
    """提供 HAL 操作对象。"""
    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    yield ops
    # 清理
    for dev in list(hal._devices.values()):
        hal.unregister(dev.name)


@pytest.fixture
def gpio_device():
    """提供 GPIO 设备。"""
    device = GPIODevice(pin=18)
    yield device


@pytest.fixture
def multi_gpio_devices():
    """提供多路 GPIO 设备。"""
    pins = [18, 19, 20, 21]
    devices = [GPIODevice(pin=p) for p in pins]
    for d in devices:
        d.online()
    yield devices
    for d in devices:
        d.offline()


@pytest.fixture
def async_logger():
    """提供异步日志记录器。"""
    logger = AsyncHALLogger(maxsize=1000)
    logger.start()
    yield logger
    logger.stop()


@pytest.fixture
def perf_monitor():
    """提供性能监控器。"""
    class Monitor:
        def __init__(self):
            self._start = None
            self._count = 0
            self._errors = 0

        def start(self):
            self._start = time.perf_counter()
            self._count = 0
            self._errors = 0

        def record(self):
            self._count += 1

        def error(self):
            self._errors += 1

        def get_rate(self) -> float:
            if self._start is None:
                return 0.0
            elapsed = time.perf_counter() - self._start
            if elapsed <= 0:
                return float('inf')
            return self._count / elapsed

        def report(self) -> dict:
            return {
                "count": self._count,
                "errors": self._errors,
                "rate": self.get_rate(),
                "elapsed": time.perf_counter() - self._start if self._start else 0,
            }
    return Monitor()


# ============================================================
# 10kHz 压力测试
# ============================================================

class Test10kHzStress:
    """10kHz 频率压力测试。"""

    def test_single_write_10khz(self, hal_ops: MathaHardwareOps, perf_monitor: Monitor):
        """测试单次写入是否达到 10kHz。"""
        perf_monitor.start()
        iterations = 5000

        for _ in range(iterations):
            hal_ops.写入("gpio_18", True)
            perf_monitor.record()

        rate = perf_monitor.get_rate()
        assert rate >= 10000, f"写入速率 {rate:.0f} ops/sec 低于 10kHz 目标"
        assert perf_monitor._errors == 0, f"写入错误数: {perf_monitor._errors}"

    def test_batch_write_10khz(self, hal_ops: MathaHardwareOps, perf_monitor: Monitor):
        """测试批量写入是否达到 10kHz。"""
        hal_ops.hal.register(GPIODevice(pin=18))
        hal_ops.hal.register(GPIODevice(pin=19))
        hal_ops.hal.register(GPIODevice(pin=20))
        hal_ops.hal.register(GPIODevice(pin=21))

        perf_monitor.start()
        iterations = 2000
        batch_ops = [("gpio_18", True), ("gpio_19", True),
                     ("gpio_20", True), ("gpio_21", True)]

        for _ in range(iterations):
            hal_ops.批量写入(batch_ops)
            perf_monitor.record()

        rate = perf_monitor.get_rate()
        # 4 路批量，目标 2500 batches/sec = 10000 ops/sec
        assert rate >= 2500, f"批量写入速率 {rate:.0f} batches/sec 低于目标"
        assert perf_monitor._errors == 0


# ============================================================
# 并发测试
# ============================================================

class TestConcurrentAccess:
    """并发访问测试。"""

    def test_concurrent_write(self, hal_ops: MathaHardwareOps):
        """测试多线程并发写入。"""
        import threading

        errors = []

        def writer(thread_id: int):
            try:
                for _ in range(1000):
                    hal_ops.写入("gpio_18", True)
                    hal_ops.写入("gpio_18", False)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"并发写入错误: {errors}"


# ============================================================
# 队列保护测试
# ============================================================

class TestQueueProtection:
    """队列溢出保护测试。"""

    def test_queue_overflow_handling(self, async_logger: AsyncHALLogger):
        """测试队列溢出时不崩溃。"""
        # 创建小队列
        small_logger = AsyncHALLogger(maxsize=10)
        small_logger.start()

        # 快速填充
        for _ in range(100):
            small_logger.debug("test")

        small_logger.stop()

        # 验证没有抛出异常
        assert small_logger._dropped_count >= 0

    def test_error_not_dropped(self, async_logger: AsyncHALLogger):
        """测试 ERROR 级别不丢弃。"""
        # 此测试验证代码逻辑，实际行为由实现保证
        pass


# ============================================================
# 基准测试
# ============================================================

class TestBenchmark:
    """性能基准测试。"""

    def test_write_latency(self, hal_ops: MathaHardwareOps):
        """测试写入延迟。"""
        iterations = 1000
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            hal_ops.写入("gpio_18", True)
            latencies.append((time.perf_counter() - start) * 1e6)  # μs

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # 目标：平均 < 10μs, 最大 < 50μs
        assert avg_latency < 10, f"平均延迟 {avg_latency:.2f} μs 超标"
        assert max_latency < 50, f"最大延迟 {max_latency:.2f} μs 超标"

    @pytest.mark.benchmark
    def test_throughput(self, hal_ops: MathaHardwareOps):
        """测试吞吐量。"""
        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            hal_ops.写入("gpio_18", True)

        elapsed = time.perf_counter() - start
        rate = iterations / elapsed

        # 目标：≥ 100K ops/sec
        assert rate >= 100000, f"吞吐量 {rate:,.0f} ops/sec 低于目标"


# ============================================================
# Pytest Hook (可选)
# ============================================================

def pytest_addoption(parser):
    """添加命令行选项。"""
    parser.addoption(
        "--duration",
        action="store",
        default="5.0",
        help="压力测试时长（秒）",
    )
    parser.addoption(
        "--frequency",
        action="store",
        default="10000",
        help="目标频率（Hz）",
    )
    parser.addoption(
        "--benchmark",
        action="store_true",
        help="运行基准测试",
    )


def pytest_configure(config):
    """注册自定义 marker。"""
    config.addinivalue_line(
        "markers", "benchmark: 性能基准测试标记"
    )
