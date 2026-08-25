# -*- coding: utf-8 -*-
"""Matha HAL v4.1 性能基准测试

测试异步日志队列 + DEBUG 级别优化 + 批量写入接口的性能提升。
"""
import time
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


def benchmark_single_write(iterations: int = 1000):
    """测试单次写入性能。"""
    hal = HardwareAbstractionLayer()
    gpio = GPIODevice(pin=18)
    hal.register(gpio)

    # 关闭异步日志（模拟生产环境）
    AsyncHALLogger._enabled = False

    start = time.perf_counter()
    for _ in range(iterations):
        gpio.write(True)
    single_time = (time.perf_counter() - start) * 1000

    print(f"【单次写入】{iterations} 次: {single_time:.1f}ms ({single_time/iterations:.4f}ms/次)")

    return single_time / iterations


def benchmark_batch_write(iterations: int = 1000):
    """测试批量写入性能。"""
    hal = HardwareAbstractionLayer()
    gpio1 = GPIODevice(pin=18)
    gpio2 = GPIODevice(pin=19)
    hal.register(gpio1)
    hal.register(gpio2)

    operations = [(f"gpio_{i % 2 + 18}", True) for i in range(iterations)]

    start = time.perf_counter()
    for _ in range(iterations):
        hal.batch_write(operations)
    batch_time = (time.perf_counter() - start) * 1000

    ops_per_sec = iterations * 2 / (batch_time / 1000)
    print(f"【批量写入】{iterations} 次 × 2 设备: {batch_time:.1f}ms ({ops_per_sec:.0f} ops/sec)")

    return batch_time / iterations


def benchmark_with_async_logger(iterations: int = 1000):
    """测试异步日志下的性能。"""
    hal = HardwareAbstractionLayer()
    gpio = GPIODevice(pin=18)
    hal.register(gpio)

    # 启用异步日志
    AsyncHALLogger._enabled = True
    logger = AsyncHALLogger()
    logger.start()

    start = time.perf_counter()
    for _ in range(iterations):
        gpio.write(True)
    async_time = (time.perf_counter() - start) * 1000

    logger.stop()

    print(f"【异步日志】{iterations} 次: {async_time:.1f}ms ({async_time/iterations:.4f}ms/次)")

    return async_time / iterations


def benchmark_matha_ops(iterations: int = 1000):
    """测试 MathaHardwareOps 性能。"""
    hal = HardwareAbstractionLayer()
    gpio = GPIODevice(pin=18)
    hal.register(gpio)
    ops = MathaHardwareOps(hal)

    start = time.perf_counter()
    for _ in range(iterations):
        ops.写入("gpio_18", True)
        ops.写入("gpio_18", False)
    ops_time = (time.perf_counter() - start) * 1000

    print(f"【MathaOps】{iterations} 次: {ops_time:.1f}ms ({ops_time/iterations:.4f}ms/次)")

    return ops_time / iterations


def main():
    print("=" * 60)
    print("  Matha HAL v4.1 性能基准测试")
    print("=" * 60)
    print()

    iterations = 1000

    # 测试 1: 单次写入（无日志）
    t1 = benchmark_single_write(iterations)

    # 测试 2: 批量写入
    t2 = benchmark_batch_write(iterations)

    # 测试 3: 异步日志
    t3 = benchmark_with_async_logger(iterations)

    # 测试 4: MathaOps
    t4 = benchmark_matha_ops(iterations)

    print()
    print("=" * 60)
    print("  性能对比")
    print("=" * 60)
    print(f"""
  单次写入（无日志）:  {t1*1000:.4f}ms/次
  批量写入（2设备）:   {t2*1000:.4f}ms/次
  异步日志:           {t3*1000:.4f}ms/次
  MathaOps:           {t4*1000:.4f}ms/次

  性能提升:
    - 批量写入 vs 单次: {t1/max(t2/2, 0.0001):.2f}x
    - 无日志 vs 异步日志: {t3/max(t1, 0.0001):.2f}x
""")


if __name__ == "__main__":
    main()
