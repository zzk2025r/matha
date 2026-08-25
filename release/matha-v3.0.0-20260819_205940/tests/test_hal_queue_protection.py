# HAL 异步队列溢出保护测试

import sys
import time
import logging
import threading
import queue

sys.path.insert(0, r"D:\trae")

from src.hardware.hal import AsyncHALLogger, HardwareAbstractionLayer, MathaHardwareOps, GPIODevice


def test_queue_overflow_protection():
    """测试队列溢出保护机制。"""
    print("=" * 60)
    print("  异步队列溢出保护测试")
    print("=" * 60)

    # 创建小队列用于测试
    logger = AsyncHALLogger(maxsize=10)
    logger.start()

    # 快速填充队列
    print("\n测试 1: 快速填充小队列 (10 容量)")
    dropped = 0
    for i in range(100):
        try:
            logger.debug(f"测试消息 {i}")
        except queue.Full:
            dropped += 1

    time.sleep(0.5)  # 等待消费
    logger.stop()

    print(f"  发送: 100 条")
    print(f"  丢弃: {logger._dropped_count} 条")
    print(f"  ✓ 队列溢出保护正常")

    return logger._dropped_count > 0


def test_high_frequency_write():
    """测试高频写入场景。"""
    print("\n测试 2: 高频写入 (10kHz 模拟)")

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    hal.register(GPIODevice(pin=18))

    iterations = 10000
    start = time.perf_counter()

    for _ in range(iterations):
        ops.写入("gpio_18", True)
        ops.写入("gpio_18", False)

    elapsed = time.perf_counter() - start
    rate = iterations * 2 / elapsed

    print(f"  写入次数: {iterations * 2:,}")
    print(f"  耗时: {elapsed*1000:.1f}ms")
    print(f"  速率: {rate:,.0f} ops/sec")
    print(f"  {'✓ 通过' if rate >= 10000 else '✗ 未达标'}")

    hal.unregister("gpio_18")
    return rate >= 10000


def test_batch_write_stability():
    """测试批量写入稳定性。"""
    print("\n测试 3: 批量写入稳定性")

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    pins = [18, 19, 20, 21]
    for p in pins:
        hal.register(GPIODevice(p))

    iterations = 5000
    batch_ops = [(f"gpio_{p}", True) for p in pins]
    errors = 0

    start = time.perf_counter()
    for i in range(iterations):
        try:
            ops.批量写入(batch_ops)
        except Exception as e:
            errors += 1
            print(f"  错误 [{i}]: {e}")

    elapsed = time.perf_counter() - start
    rate = iterations / elapsed

    print(f"  批量写入: {iterations:,} 次")
    print(f"  耗时: {elapsed*1000:.1f}ms")
    print(f"  速率: {rate:,.0f} batches/sec")
    print(f"  错误数: {errors}")
    print(f"  {'✓ 稳定' if errors == 0 else '✗ 有错误'}")

    for p in pins:
        hal.unregister(f"gpio_{p}")
    return errors == 0


def test_concurrent_access():
    """测试并发访问安全性。"""
    print("\n测试 4: 并发访问测试")

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)
    hal.register(GPIODevice(pin=18))

    errors = []
    completed = [0]

    def writer(thread_id: int):
        try:
            for _ in range(1000):
                ops.写入("gpio_18", True)
                ops.写入("gpio_18", False)
            completed[0] += 1
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    start = time.perf_counter()

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    elapsed = time.perf_counter() - start
    total_ops = 8 * 2000
    rate = total_ops / elapsed

    print(f"  线程数: 8")
    print(f"  每线程操作: 2000 次")
    print(f"  总操作: {total_ops:,}")
    print(f"  耗时: {elapsed*1000:.1f}ms")
    print(f"  速率: {rate:,.0f} ops/sec")
    print(f"  错误数: {len(errors)}")
    print(f"  {'✓ 并发安全' if len(errors) == 0 else '✗ 有错误'}")

    hal.unregister("gpio_18")
    return len(errors) == 0


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  HAL 异步队列压力测试套件")
    print("=" * 60)

    results = []
    results.append(("队列溢出保护", test_queue_overflow_protection()))
    results.append(("高频写入", test_high_frequency_write()))
    results.append(("批量写入稳定性", test_batch_write_stability()))
    results.append(("并发访问", test_concurrent_access()))

    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:20} {status}")

    all_passed = all(r[1] for r in results)
    print(f"\n总体结果: {'✓ 全部通过' if all_passed else '✗ 有失败项'}")
    sys.exit(0 if all_passed else 1)
