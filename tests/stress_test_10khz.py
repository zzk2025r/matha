# -*- coding: utf-8 -*-
"""HAL 10kHz 频率压力测试

模拟 10kHz GPIO 写入频率，验证异步队列稳定性。

用法：
  python tests/stress_test_10khz.py
  python tests/stress_test_10khz.py --frequency 10000
  python tests/stress_test_10khz.py --duration 5
  python tests/stress_test_10khz.py --channels 4
"""
import sys
import time
import logging
import argparse
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


class PerformanceMonitor:
    """性能监控器，实时统计写入速率和延迟。"""

    def __init__(self, window_size: int = 1000):
        self._timestamps: deque = deque(maxlen=window_size)
        self._total_writes = 0
        self._start_time = None
        self._errors = 0

    def record_write(self):
        """记录一次写入操作。"""
        now = time.perf_counter()
        self._timestamps.append(now)
        self._total_writes += 1

    def get_current_rate(self) -> float:
        """获取当前写入速率（ops/sec）。"""
        if len(self._timestamps) < 2:
            return 0.0
        window = self._timestamps[-1] - self._timestamps[0]
        if window <= 0:
            return float('inf')
        return len(self._timestamps) / window

    def get_avg_rate(self) -> float:
        """获取平均写入速率。"""
        if self._start_time is None:
            return 0.0
        elapsed = time.perf_counter() - self._start_time
        if elapsed <= 0:
            return 0.0
        return self._total_writes / elapsed

    def get_latency_stats(self) -> dict:
        """获取延迟统计。"""
        if len(self._timestamps) < 2:
            return {"min": 0, "max": 0, "avg": 0}
        # 计算连续写入的时间间隔
        intervals = []
        ts_list = list(self._timestamps)
        for i in range(1, len(ts_list)):
            intervals.append(ts_list[i] - ts_list[i-1])
        if not intervals:
            return {"min": 0, "max": 0, "avg": 0}
        return {
            "min": min(intervals) * 1e6,  # μs
            "max": max(intervals) * 1e6,
            "avg": sum(intervals) / len(intervals) * 1e6,
        }

    def start(self):
        """开始监控。"""
        self._start_time = time.perf_counter()

    def report(self) -> str:
        """生成性能报告。"""
        latency = self.get_latency_stats()
        return f"""
性能统计:
  总写入次数:    {self._total_writes:,}
  平均速率:      {self.get_avg_rate():,.0f} ops/sec
  当前速率:      {self.get_current_rate():,.0f} ops/sec
  最小延迟:      {latency['min']:.1f} μs
  最大延迟:      {latency['max']:.1f} μs
  平均延迟:      {latency['avg']:.1f} μs
  错误次数:      {self._errors}
"""


def stress_test_10khz(
    channels: int = 4,
    target_frequency: int = 10000,
    duration: float = 5.0,
    batch_size: int = 4,
):
    """
    10kHz 频率压力测试。

    Args:
        channels: GPIO 通道数
        target_frequency: 目标频率 (Hz)
        duration: 测试时长 (秒)
        batch_size: 每次批量写入的通道数
    """
    print("=" * 60)
    print(f"  HAL 10kHz 压力测试")
    print(f"  通道数: {channels}, 目标频率: {target_frequency}Hz, 时长: {duration}s")
    print("=" * 60)

    # 初始化
    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    # 注册 GPIO 设备
    pins = list(range(18, 18 + channels))
    for p in pins:
        hal.register(GPIODevice(pin=p))

    print(f"\n✓ 已注册 {channels} 个 GPIO: {pins}")

    # 计算批次操作
    period_us = 1e6 / target_frequency  # 目标周期 (μs)
    writes_per_batch = min(batch_size, channels)

    print(f"\n目标周期: {period_us:.1f} μs ({target_frequency} Hz)")
    print(f"每批次写入: {writes_per_batch} 通道")

    # 准备操作列表
    batch_ops = [(f"gpio_{p}", True) for p in pins[:writes_per_batch]]
    batch_ops_off = [(f"gpio_{p}", False) for p in pins[:writes_per_batch]]

    # 性能监控
    monitor = PerformanceMonitor()
    monitor.start()

    # 计算总迭代次数
    total_ops = int(target_frequency * duration)
    iterations = total_ops // (writes_per_batch * 2)  # ON + OFF

    print(f"\n开始压力测试...")
    print(f"  总操作数: {total_ops:,}")
    print(f"  迭代次数: {iterations:,}")
    print("-" * 40)

    start_time = time.perf_counter()
    error_count = 0

    try:
        for i in range(iterations):
            # 批量写入 ON
            try:
                ops.批量写入(batch_ops)
                monitor.record_write()
            except Exception as e:
                error_count += 1
                monitor._errors += 1

            # 批量写入 OFF
            try:
                ops.批量写入(batch_ops_off)
                monitor.record_write()
            except Exception as e:
                error_count += 1
                monitor._errors += 1

            # 每 1000 次打印进度
            if (i + 1) % 1000 == 0:
                elapsed = time.perf_counter() - start_time
                rate = monitor.get_current_rate()
                print(f"  进度: {i+1:,}/{iterations:,} ({(i+1)/iterations*100:.1f}%) | "
                      f"速率: {rate:,.0f} ops/sec | 错误: {error_count}")

    except KeyboardInterrupt:
        print("\n  测试被中断")

    # 计算结果
    elapsed = time.perf_counter() - start_time
    avg_rate = monitor.get_avg_rate()
    latency = monitor.get_latency_stats()

    # 性能评估
    print("\n" + "=" * 60)
    print("  测试结果")
    print("=" * 60)
    print(f"""
测试统计:
  总时长:       {elapsed:.2f}秒
  总写入次数:    {monitor._total_writes:,}
  平均速率:      {avg_rate:,.0f} ops/sec
  目标速率:      {target_frequency * writes_per_batch:,} ops/sec
  达成率:        {avg_rate/max(target_frequency*writes_per_batch,1)*100:.1f}%
  错误次数:      {error_count}

延迟统计:
  最小延迟:      {latency['min']:.1f} μs
  最大延迟:      {latency['max']:.1f} μs
  平均延迟:      {latency['avg']:.1f} μs
  目标周期:      {period_us:.1f} μs

稳定性评估:
  {'✓ 稳定' if error_count == 0 and latency['max'] < period_us * 2 else '✗ 不稳定'}
  {'✓ 满足 10kHz 要求' if avg_rate >= target_frequency * writes_per_batch * 0.8 else '✗ 未达标'}
""")

    # 清理
    for p in pins:
        hal.unregister(f"gpio_{p}")

    # 异步队列建议
    print("=" * 60)
    print("  异步队列建议")
    print("=" * 60)
    peak_rate = monitor.get_current_rate()
    recommended_size = int(peak_rate * 0.1 * 2)  # 2秒缓冲
    print(f"""
  当前队列大小:     1000
  峰值速率:         {peak_rate:,.0f} ops/sec
  推荐队列大小:     {max(1000, recommended_size)} (2秒缓冲)
  结论:             {'队列充足' if 1000 > recommended_size else '建议扩大队列'}
""")


def stress_test_burst(target_frequency: int = 10000, burst_count: int = 100):
    """
    突发写入测试，验证队列在突发流量下的表现。

    Args:
        target_frequency: 目标频率
        burst_count: 突发写入次数
    """
    print("\n" + "=" * 60)
    print(f"  突发写入测试")
    print(f"  目标频率: {target_frequency}Hz, 突发次数: {burst_count}")
    print("=" * 60)

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    hal.register(GPIODevice(pin=18))

    # 突发写入
    print(f"\n发送 {burst_count} 次突发写入...")
    start = time.perf_counter()
    for _ in range(burst_count):
        ops.写入("gpio_18", True)
        ops.写入("gpio_18", False)
    elapsed = (time.perf_counter() - start) * 1000

    rate = burst_count * 2 / (elapsed / 1000)
    print(f"  耗时: {elapsed:.1f}ms")
    print(f"  平均速率: {rate:,.0f} ops/sec")
    print(f"  目标速率: {target_frequency * 2:,} ops/sec")
    print(f"  达成率: {rate/max(target_frequency*2,1)*100:.1f}%")

    hal.unregister("gpio_18")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HAL 10kHz 压力测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tests/stress_test_10khz.py                     # 默认测试
  python tests/stress_test_10khz.py --frequency 10000   # 10kHz
  python tests/stress_test_10khz.py --duration 10       # 测试 10 秒
  python tests/stress_test_10khz.py --channels 8        # 8 通道
  python tests/stress_test_10khz.py --burst             # 突发测试
        """
    )
    parser.add_argument("--frequency", type=int, default=10000,
                       help="目标频率 Hz（默认 10000）")
    parser.add_argument("--duration", type=float, default=5.0,
                       help="测试时长秒（默认 5）")
    parser.add_argument("--channels", type=int, default=4,
                       help="GPIO 通道数（默认 4）")
    parser.add_argument("--batch-size", type=int, default=4,
                       help="批量写入大小（默认 4）")
    parser.add_argument("--burst", action="store_true",
                       help="运行突发写入测试")
    parser.add_argument("--burst-count", type=int, default=1000,
                       help="突发写入次数（默认 1000）")

    args = parser.parse_args()

    if args.burst:
        stress_test_burst(args.frequency, args.burst_count)
    else:
        stress_test_10khz(
            channels=args.channels,
            target_frequency=args.frequency,
            duration=args.duration,
            batch_size=args.batch_size,
        )
