# -*- coding: utf-8 -*-
"""HAL 并发压力测试 — multiprocessing 版（GIL 绕过）

使用 multiprocessing 替代 threading，绕过 Python GIL 限制，
实现真正的并行 GPIO 写入，验证 100kHz+ 级性能。

用法：
  python tests/test_hal_multiprocessing.py
  python tests/test_hal_multiprocessing.py --workers 16
  python tests/test_hal_multiprocessing.py --frequency 100000
"""
import sys
import time
import unittest
import multiprocessing as mp
import logging
from pathlib import Path
from collections import deque
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


# ============================================================
# Worker 函数（必须在模块顶层定义，供 multiprocessing 序列化）
# ============================================================

def _gpio_writer_worker(
    worker_id: int,
    pin: int,
    iterations: int,
    result_queue: mp.Queue,
    enabled: mp.Value,
):
    """
    GPIO 写入 Worker 函数。

    Args:
        worker_id: Worker ID
        pin: GPIO 引脚
        iterations: 写入次数
        result_queue: 结果队列
        enabled: 共享标志（用于优雅退出）
    """
    local_ops = MathaHardwareOps(HardwareAbstractionLayer())
    local_ops.hal.register(GPIODevice(pin=pin))

    latencies = deque(maxlen=1000)
    errors = 0
    start_time = time.perf_counter()

    try:
        for i in range(iterations):
            t0 = time.perf_counter()
            try:
                local_ops.写入(f"gpio_{pin}", i % 2 == 0)
            except Exception as e:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1e6)  # μs
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start_time
        rate = iterations / elapsed if elapsed > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        max_lat = max(latencies) if latencies else 0

        result_queue.put({
            "worker_id": worker_id,
            "pin": pin,
            "iterations": iterations,
            "elapsed_ms": elapsed * 1000,
            "rate": rate,
            "avg_latency_us": avg_lat,
            "max_latency_us": max_lat,
            "errors": errors,
        })


def _batch_writer_worker(
    worker_id: int,
    pins: List[int],
    iterations: int,
    result_queue: mp.Queue,
):
    """批量写入 Worker。"""
    local_ops = MathaHardwareOps(HardwareAbstractionLayer())
    for p in pins:
        local_ops.hal.register(GPIODevice(pin=p))

    latencies = deque(maxlen=1000)
    errors = 0
    start_time = time.perf_counter()

    try:
        for i in range(iterations):
            batch_ops = [(f"gpio_{p}", i % 2 == 0) for p in pins]
            t0 = time.perf_counter()
            try:
                local_ops.批量写入(batch_ops)
            except Exception as e:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1e6)
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start_time
        rate = iterations / elapsed if elapsed > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        max_lat = max(latencies) if latencies else 0

        result_queue.put({
            "worker_id": worker_id,
            "pins": pins,
            "iterations": iterations,
            "elapsed_ms": elapsed * 1000,
            "rate": rate,
            "avg_latency_us": avg_lat,
            "max_latency_us": max_lat,
            "errors": errors,
        })


# ============================================================
# 性能监控器（multiprocessing 安全版本）
# ============================================================

class PerformanceMonitor:
    """性能监控器，统计总体性能指标。"""

    def __init__(self):
        self._results: List[dict] = []
        self._total_ops = 0
        self._total_errors = 0

    def add_result(self, result: dict):
        """添加 Worker 结果。"""
        self._results.append(result)
        self._total_ops += result["iterations"]
        self._total_errors += result["errors"]

    def get_summary(self) -> dict:
        """获取性能摘要。"""
        if not self._results:
            return {}

        total_time = max(r["elapsed_ms"] for r in self._results) / 1000
        total_rate = self._total_ops / total_time if total_time > 0 else 0

        all_latencies = []
        for r in self._results:
            # 从 iterations 和 elapsed 推算平均延迟
            if r["elapsed_ms"] > 0:
                avg_lat = (r["elapsed_ms"] / r["iterations"]) * 1000
                all_latencies.append(avg_lat)

        return {
            "total_ops": self._total_ops,
            "total_errors": self._total_errors,
            "total_time_sec": total_time,
            "total_rate": total_rate,
            "avg_latency_us": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            "max_latency_us": max(all_latencies) if all_latencies else 0,
            "workers": len(self._results),
        }


# ============================================================
# 测试函数（供 unittest 和 pytest 调用）
# ============================================================

def run_multiprocessing_stress_test(
    num_workers: int = 8,
    pin: int = 18,
    iterations_per_worker: int = 5000,
    target_frequency: int = 100000,
) -> dict:
    """
    运行 multiprocessing 压力测试。

    Args:
        num_workers: Worker 数量
        pin: GPIO 引脚
        iterations_per_worker: 每个 Worker 的迭代次数
        target_frequency: 目标频率 (Hz)

    Returns:
        性能摘要字典
    """
    print("=" * 60)
    print(f"  HAL Multiprocessing 压力测试")
    print(f"  Workers: {num_workers}, Pin: {pin}, Iterations: {iterations_per_worker}")
    print(f"  目标频率: {target_frequency} Hz")
    print("=" * 60)

    result_queue = mp.Queue()
    processes = []

    # 启动 Workers
    for i in range(num_workers):
        p = mp.Process(
            target=_gpio_writer_worker,
            args=(i, pin, iterations_per_worker, result_queue, mp.Value('i', 1))
        )
        p.start()
        processes.append(p)

    # 等待完成
    for p in processes:
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()

    # 收集结果
    monitor = PerformanceMonitor()
    while not result_queue.empty():
        monitor.add_result(result_queue.get())

    summary = monitor.get_summary()

    print(f"""
测试结果:
  总操作数:      {summary['total_ops']:,}
  总耗时:        {summary['total_time_sec']:.3f} 秒
  总速率:        {summary['total_rate']:,.0f} ops/sec
  目标速率:      {target_frequency * num_workers:,} ops/sec
  达成率:        {summary['total_rate'] / max(target_frequency * num_workers, 1) * 100:.1f}%
  错误数:        {summary['total_errors']}
  平均延迟:      {summary['avg_latency_us']:.2f} μs
  最大延迟:      {summary['max_latency_us']:.2f} μs
""")

    return summary


def run_batch_multiprocessing_test(
    num_workers: int = 4,
    pins: List[int] = None,
    iterations_per_worker: int = 2000,
) -> dict:
    """
    运行批量写入 multiprocessing 测试。

    Args:
        num_workers: Worker 数量
        pins: GPIO 引脚列表
        iterations_per_worker: 每个 Worker 的迭代次数

    Returns:
        性能摘要字典
    """
    if pins is None:
        pins = list(range(18, 18 + num_workers))

    print("=" * 60)
    print(f"  HAL 批量写入 Multiprocessing 测试")
    print(f"  Workers: {num_workers}, Pins: {pins}")
    print("=" * 60)

    result_queue = mp.Queue()
    processes = []

    for i in range(num_workers):
        p = mp.Process(
            target=_batch_writer_worker,
            args=(i, pins, iterations_per_worker, result_queue)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()

    monitor = PerformanceMonitor()
    while not result_queue.empty():
        monitor.add_result(result_queue.get())

    summary = monitor.get_summary()

    print(f"""
测试结果:
  总操作数:      {summary['total_ops']:,}
  总耗时:        {summary['total_time_sec']:.3f} 秒
  总速率:        {summary['total_rate']:,.0f} ops/sec
  平均延迟:      {summary['avg_latency_us']:.2f} μs
  错误数:        {summary['total_errors']}
""")

    return summary


# ============================================================
# unittest 测试类
# ============================================================

class TestMultiprocessingStress(unittest.TestCase):
    """Multiprocessing 压力测试。"""

    def test_multiprocessing_single_pin(self):
        """测试单引脚 multiprocessing 写入。"""
        summary = run_multiprocessing_stress_test(
            num_workers=4,
            pin=18,
            iterations_per_worker=2000,
            target_frequency=50000,
        )
        self.assertGreater(summary["total_rate"], 50000 * 4 * 0.5,
            f"多进程速率 {summary['total_rate']:.0f} 低于预期")
        self.assertEqual(summary["total_errors"], 0)

    def test_multiprocessing_batch_write(self):
        """测试批量写入 multiprocessing。"""
        summary = run_batch_multiprocessing_test(
            num_workers=4,
            pins=[18, 19, 20, 21],
            iterations_per_worker=1000,
        )
        self.assertGreater(summary["total_rate"], 10000)
        self.assertEqual(summary["total_errors"], 0)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HAL Multiprocessing 压力测试")
    parser.add_argument("--workers", type=int, default=8, help="Worker 数量")
    parser.add_argument("--pin", type=int, default=18, help="GPIO 引脚")
    parser.add_argument("--iterations", type=int, default=5000, help="每个 Worker 迭代次数")
    parser.add_argument("--frequency", type=int, default=100000, help="目标频率")
    parser.add_argument("--batch", action="store_true", help="批量写入测试")
    parser.add_argument("--pins", nargs="+", type=int, help="批量写入引脚")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    print("=" * 60)
    print("  Matha v4.2 — HAL Multiprocessing 压力测试")
    print(f"  Workers: {args.workers}, Pin: {args.pin}")
    print("=" * 60)

    if args.batch:
        run_batch_multiprocessing_test(
            num_workers=args.workers,
            pins=args.pins or list(range(18, 18 + args.workers)),
            iterations_per_worker=args.iterations,
        )
    else:
        run_multiprocessing_stress_test(
            num_workers=args.workers,
            pin=args.pin,
            iterations_per_worker=args.iterations,
            target_frequency=args.frequency,
        )

    if args.verbose:
        import unittest
        unittest.main(verbosity=2)
