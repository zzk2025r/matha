# -*- coding: utf-8 -*-
"""HAL 10kHz 压力测试套件

封装 stress_test_10khz.py 的测试用例，同时支持 unittest 和 pytest。

用法：
  # unittest 模式
  python -m unittest tests.test_hal_stress -v

  # pytest 模式
  pytest tests/test_hal_stress.py -v
  pytest tests/test_hal_stress.py -v -k "10khz"
  pytest tests/test_hal_stress.py -v --benchmark
"""
import unittest
import time
import threading
import sys
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


# ============================================================
# 性能监控器
# ============================================================

class PerformanceMonitor:
    """性能监控器。"""

    def __init__(self, window_size: int = 1000):
        self._timestamps: deque = deque(maxlen=window_size)
        self._total_writes = 0
        self._start_time = None
        self._errors = 0

    def record_write(self):
        now = time.perf_counter()
        self._timestamps.append(now)
        self._total_writes += 1

    def get_current_rate(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0
        window = self._timestamps[-1] - self._timestamps[0]
        if window <= 0:
            return float('inf')
        return len(self._timestamps) / window

    def get_avg_rate(self) -> float:
        if self._start_time is None:
            return 0.0
        elapsed = time.perf_counter() - self._start_time
        if elapsed <= 0:
            return 0.0
        return self._total_writes / elapsed

    def start(self):
        self._start_time = time.perf_counter()

    def get_latency_stats(self) -> dict:
        if len(self._timestamps) < 2:
            return {"min": 0, "max": 0, "avg": 0}
        intervals = []
        ts_list = list(self._timestamps)
        for i in range(1, len(ts_list)):
            intervals.append(ts_list[i] - ts_list[i-1])
        if not intervals:
            return {"min": 0, "max": 0, "avg": 0}
        return {
            "min": min(intervals) * 1e6,
            "max": max(intervals) * 1e6,
            "avg": sum(intervals) / len(intervals) * 1e6,
        }


# ============================================================
# 基础 fixture
# ============================================================

def create_hal_ops():
    """创建 HAL 操作对象。"""
    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    hal.register(GPIODevice(pin=18))
    return ops, hal


def create_multi_channel_ops():
    """创建多通道 HAL 操作对象。"""
    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    for p in [18, 19, 20, 21]:
        hal.register(GPIODevice(pin=p))
    return ops, hal


# ============================================================
# unittest 测试类
# ============================================================

class Test10kHzStress(unittest.TestCase):
    """10kHz 压力测试。"""

    def test_single_write_10khz(self):
        """测试单次写入是否达到 10kHz。"""
        ops, hal = create_hal_ops()
        monitor = PerformanceMonitor()
        monitor.start()
        iterations = 5000

        for _ in range(iterations):
            ops.写入("gpio_18", True)
            monitor.record_write()

        rate = monitor.get_avg_rate()
        latency = monitor.get_latency_stats()
        hal.unregister("gpio_18")

        self.assertGreaterEqual(rate, 10000,
            f"写入速率 {rate:.0f} ops/sec 低于 10kHz 目标")
        self.assertLess(latency["max"], 100e3,
            f"最大延迟 {latency['max']:.0f}μs 超标")
        print(f"\n  单次写入: {rate:,.0f} ops/sec, 延迟: {latency['avg']:.1f}μs")

    def test_batch_write_10khz(self):
        """测试批量写入是否达到 10kHz。"""
        ops, hal = create_multi_channel_ops()
        monitor = PerformanceMonitor()
        monitor.start()
        iterations = 2000
        batch_ops = [("gpio_18", True), ("gpio_19", True),
                     ("gpio_20", True), ("gpio_21", True)]

        for _ in range(iterations):
            ops.批量写入(batch_ops)
            monitor.record_write()

        rate = monitor.get_avg_rate()

        self.assertGreaterEqual(rate, 2500,
            f"批量写入速率 {rate:.0f} batches/sec 低于目标")
        print(f"\n  批量写入: {rate:,.0f} batches/sec")

    def test_write_latency(self):
        """测试写入延迟。"""
        ops, hal = create_hal_ops()
        iterations = 1000
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            ops.写入("gpio_18", True)
            latencies.append((time.perf_counter() - start) * 1e6)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        self.assertLess(avg_latency, 10,
            f"平均延迟 {avg_latency:.2f} μs 超标")
        self.assertLess(max_latency, 500,
            f"最大延迟 {max_latency:.2f} μs 超标")
        print(f"\n  延迟: avg={avg_latency:.2f}μs, max={max_latency:.2f}μs")

    def test_throughput(self):
        """测试吞吐量。"""
        ops, hal = create_hal_ops()
        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            ops.写入("gpio_18", True)

        elapsed = time.perf_counter() - start
        rate = iterations / elapsed

        self.assertGreaterEqual(rate, 100000,
            f"吞吐量 {rate:,.0f} ops/sec 低于目标")
        print(f"\n  吞吐量: {rate:,.0f} ops/sec")


class TestConcurrentAccess(unittest.TestCase):
    """并发访问测试。"""

    def test_concurrent_write(self):
        """测试多线程并发写入。"""
        ops, hal = create_hal_ops()
        errors = []

        def writer(thread_id: int):
            try:
                for _ in range(1000):
                    ops.写入("gpio_18", True)
                    ops.写入("gpio_18", False)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"并发写入错误: {errors}")
        print(f"\n  并发写入: 8 线程 × 2000 次 = 16000 次，零错误")

    def test_concurrent_multiprocessing(self):
        """测试多进程并发写入（GIL 绕过）。"""
        from src.hardware.hal_multiprocessing import run_multiprocess_stress_test

        result = run_multiprocess_stress_test(
            num_workers=4,
            pin=18,
            iterations_per_worker=1000,
            target_frequency=50000,
        )
        self.assertGreater(result["total_rate"], 50000 * 4 * 0.5,
            f"多进程速率 {result['total_rate']:.0f} 低于预期")
        self.assertEqual(result["total_errors"], 0)
        print(f"\n  多进程写入: {result['workers']} workers × 1000 次 = {result['total_ops']} 次")
        print(f"  速率: {result['total_rate']:,.0f} ops/sec")
        print(f"  错误数: {result['total_errors']}")


class TestQueueProtection(unittest.TestCase):
    """队列溢出保护测试。"""

    def test_queue_overflow_handling(self):
        """测试队列溢出时不崩溃。"""
        small_logger = AsyncHALLogger(maxsize=10)
        small_logger.start()

        for _ in range(100):
            small_logger.debug("test")

        small_logger.stop()
        self.assertGreaterEqual(small_logger._dropped_count, 0)
        print(f"\n  队列溢出: 丢弃 {small_logger._dropped_count} 条日志")

    def test_queue_normal_no_drop(self):
        """测试正常队列不丢弃。"""
        logger = AsyncHALLogger(maxsize=1000)
        logger.start()
        for _ in range(10):
            logger.info("test")
        logger.stop()
        self.assertEqual(logger._dropped_count, 0)
        print(f"\n  正常队列: 丢弃 0 条日志")


class TestBurstWrite(unittest.TestCase):
    """突发写入测试。"""

    def test_burst_write(self):
        """测试突发写入稳定性。"""
        ops, hal = create_hal_ops()
        burst_count = 1000
        start = time.perf_counter()

        for _ in range(burst_count):
            ops.写入("gpio_18", True)
            ops.写入("gpio_18", False)

        elapsed = (time.perf_counter() - start) * 1000
        rate = burst_count * 2 / (elapsed / 1000)

        self.assertLess(elapsed, 1000, f"突发写入耗时 {elapsed:.0f}ms 超时")
        print(f"\n  突发写入: {burst_count * 2} 次, {elapsed:.1f}ms, {rate:,.0f} ops/sec")


# ============================================================
# pytest 兼容类（供 pytest 运行）
# ============================================================

try:
    import pytest

    @pytest.mark.stress
    class Test10kHzStressPytest:
        """10kHz 压力测试（pytest 版本）。"""

        def test_single_write_10khz(self):
            ops, hal = create_hal_ops()
            monitor = PerformanceMonitor()
            monitor.start()
            for _ in range(5000):
                ops.写入("gpio_18", True)
                monitor.record_write()
            rate = monitor.get_avg_rate()
            assert rate >= 10000
            hal.unregister("gpio_18")

        def test_batch_write_10khz(self):
            ops, hal = create_multi_channel_ops()
            monitor = PerformanceMonitor()
            monitor.start()
            batch_ops = [("gpio_18", True), ("gpio_19", True),
                         ("gpio_20", True), ("gpio_21", True)]
            for _ in range(2000):
                ops.批量写入(batch_ops)
                monitor.record_write()
            rate = monitor.get_avg_rate()
            assert rate >= 2500

    @pytest.mark.stress
    class TestConcurrentAccessPytest:
        def test_concurrent_write(self):
            ops, hal = create_hal_ops()
            errors = []
            def writer(tid):
                try:
                    for _ in range(1000):
                        ops.写入("gpio_18", True)
                        ops.写入("gpio_18", False)
                except Exception as e:
                    errors.append(str(e))
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
            for t in threads: t.start()
            for t in threads: t.join(timeout=10)
            assert len(errors) == 0

    @pytest.mark.stress
    class TestQueueProtectionPytest:
        def test_queue_overflow(self):
            small_logger = AsyncHALLogger(maxsize=10)
            small_logger.start()
            for _ in range(100):
                small_logger.debug("test")
            small_logger.stop()
            assert small_logger._dropped_count >= 0

    @pytest.mark.stress
    class TestBurstWritePytest:
        def test_burst_write(self):
            ops, hal = create_hal_ops()
            start = time.perf_counter()
            for _ in range(1000):
                ops.写入("gpio_18", True)
                ops.写入("gpio_18", False)
            elapsed = (time.perf_counter() - start) * 1000
            assert elapsed < 1000

    def pytest_addoption(parser):
        parser.addoption("--channels", action="store", default="4")
        parser.addoption("--duration", action="store", default="5.0")
        parser.addoption("--benchmark", action="store_true")

    def pytest_configure(config):
        config.addinivalue_line("markers", "stress: 压力测试标记")

except ImportError:
    pass  # pytest 未安装时跳过


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HAL 10kHz 压力测试")
    parser.add_argument("--pytest", action="store_true", help="使用 pytest 模式")
    parser.add_argument("--benchmark", action="store_true", help="基准测试")
    args = parser.parse_args()

    print("=" * 60)
    print("  HAL 10kHz 压力测试套件")
    print("=" * 60)

    if args.pytest:
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        unittest.main(verbosity=2)
