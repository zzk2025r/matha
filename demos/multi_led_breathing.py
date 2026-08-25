# -*- coding: utf-8 -*-
"""Matha v4.1 — 多路 LED 同步呼吸灯 Demo

演示通过批量写入接口控制多路 LED 实现同步呼吸效果。

功能：
  1. 多路 LED 同步渐亮/渐暗
  2. 交替闪烁模式
  3. 跑马灯效果
  4. 性能基准测试（10kHz 频率模拟）

用法：
  python demos/multi_led_breathing.py
  python demos/multi_led_breathing.py --mode sync    # 同步呼吸
  python demos/multi_led_breathing.py --mode chase   # 跑马灯
  python demos/multi_led_breathing.py --benchmark    # 性能测试
"""
import sys
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    GPIODevice,
    AsyncHALLogger,
)


# ============================================================
# 同步呼吸灯
# ============================================================

def sync_breathing_demo(pins: list = None, duration: float = 3.0):
    """
    多路 LED 同步呼吸灯。

    所有 LED 同时渐亮、渐暗，形成呼吸效果。

    Args:
        pins: GPIO 引脚列表，默认 [18, 19, 20, 21]
        duration: 一个完整呼吸周期时长（秒）
    """
    if pins is None:
        pins = [18, 19, 20, 21]

    print("=" * 60)
    print(f"  Matha v4.1 — 多路 LED 同步呼吸灯")
    print(f"  引脚: {pins}, 周期: {duration}s")
    print("=" * 60)

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    # 注册所有 LED
    leds = [GPIODevice(pin=p) for p in pins]
    for led in leds:
        hal.register(led)

    print(f"\n✓ 已注册 {len(pins)} 个 LED: {pins}")

    # 计算步进
    steps = 40  # 40 级亮度
    step_time = duration / (steps * 2)  # 渐亮 + 渐暗

    print(f"\n【同步呼吸】渐亮 → 渐暗，每级 {step_time*1000:.1f}ms")
    print("-" * 40)

    try:
        # 渐亮
        for brightness in range(0, 101, 3):
            values = [(f"gpio_{p}", brightness / 100.0) for p in pins]
            ops.批量写入(values)
            bar = "█" * (brightness // 10) + "░" * (10 - brightness // 10)
            print(f"  亮度: {brightness:3d}% {bar}", end="\r")
            time.sleep(step_time)

        # 渐暗
        for brightness in range(100, -1, -3):
            values = [(f"gpio_{p}", brightness / 100.0) for p in pins]
            ops.批量写入(values)
            bar = "█" * (brightness // 10) + "░" * (10 - brightness // 10)
            print(f"  亮度: {brightness:3d}% {bar}", end="\r")
            time.sleep(step_time)

    except KeyboardInterrupt:
        print("\n  中断呼吸循环")

    print("\n" + "-" * 40)
    print("✓ 同步呼吸完成")

    # 关闭所有 LED
    ops.批量写入([(f"gpio_{p}", False) for p in pins])

    # 清理
    for led in leds:
        hal.unregister(led.name)


# ============================================================
# 交替闪烁
# ============================================================

def alternating_flashing_demo(pins: list = None, interval: float = 0.2, rounds: int = 5):
    """
    多路 LED 交替闪烁。

    奇偶引脚交替亮灭，形成追逐效果。

    Args:
        pins: GPIO 引脚列表
        interval: 切换间隔（秒）
        rounds: 交替轮数
    """
    if pins is None:
        pins = [18, 19, 20, 21]

    print("\n" + "=" * 60)
    print(f"  Matha v4.1 — 多路 LED 交替闪烁")
    print(f"  引脚: {pins}, 间隔: {interval}s, 轮数: {rounds}")
    print("=" * 60)

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    leds = [GPIODevice(pin=p) for p in pins]
    for led in leds:
        hal.register(led)

    print(f"\n✓ 已注册 {len(pins)} 个 LED")
    print(f"\n【交替闪烁】奇偶引脚交替亮灭")
    print("-" * 40)

    for round_num in range(1, rounds + 1):
        for i, pin in enumerate(pins):
            # 奇偶交替
            values = [(f"gpio_{p}", i % 2 == p % 2) for p in pins]
            ops.批量写入(values)
            states = "".join("█" if v else "░" for v in [x[1] for x in values])
            print(f"  轮 {round_num}: {states}  ({[v[1] for v in values]})")
            time.sleep(interval)

    # 全部关闭
    ops.批量写入([(f"gpio_{p}", False) for p in pins])
    print("-" * 40)
    print("✓ 交替闪烁完成")

    for led in leds:
        hal.unregister(led.name)


# ============================================================
# 跑马灯
# ============================================================

def chase_light_demo(pins: list = None, speed: float = 0.1, loops: int = 3):
    """
    跑马灯效果。

    单个 LED 依次亮灭，形成追逐效果。

    Args:
        pins: GPIO 引脚列表
        speed: 切换速度（秒）
        loops: 循环次数
    """
    if pins is None:
        pins = [18, 19, 20, 21]

    print("\n" + "=" * 60)
    print(f"  Matha v4.1 — 跑马灯效果")
    print(f"  引脚: {pins}, 速度: {speed}s, 循环: {loops}")
    print("=" * 60)

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    leds = [GPIODevice(pin=p) for p in pins]
    for led in leds:
        hal.register(led)

    print(f"\n✓ 已注册 {len(pins)} 个 LED")
    print(f"\n【跑马灯】单个 LED 依次亮灭")
    print("-" * 40)

    for loop in range(loops):
        for i, pin in enumerate(pins):
            # 只有当前引脚亮
            values = [(f"gpio_{p}", p == pin) for p in pins]
            ops.批量写入(values)
            states = "".join("█" if v else "░" for v in [x[1] for x in values])
            arrow = " " * (i * 2) + "^"
            print(f"  循环 {loop+1}: {states}  {arrow}")
            time.sleep(speed)

    # 全部关闭
    ops.批量写入([(f"gpio_{p}", False) for p in pins])
    print("-" * 40)
    print("✓ 跑马灯完成")

    for led in leds:
        hal.unregister(led.name)


# ============================================================
# 性能基准测试
# ============================================================

def benchmark_test(iterations: int = 10000):
    """
    批量写入性能基准测试。

    模拟 10kHz GPIO 操作频率下的性能表现。
    """
    print("\n" + "=" * 60)
    print(f"  Matha v4.1 — 批量写入性能基准测试")
    print(f"  迭代次数: {iterations:,}")
    print("=" * 60)

    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    # 注册 4 个 LED
    pins = [18, 19, 20, 21]
    leds = [GPIODevice(pin=p) for p in pins]
    for led in leds:
        hal.register(led)

    # 测试 1: 单次批量写入（4 路同时）
    print(f"\n【测试 1】单次批量写入（4 路同时）")
    batch_ops = [(f"gpio_{p}", True) for p in pins]
    start = time.perf_counter()
    for _ in range(iterations):
        ops.批量写入(batch_ops)
    batch_time = (time.perf_counter() - start) * 1000
    batch_rate = iterations / (batch_time / 1000)

    print(f"  总耗时:   {batch_time:.1f}ms")
    print(f"  单次耗时: {batch_time/iterations:.4f}ms")
    print(f"  吞吐量:   {batch_rate:,.0f} batches/sec")
    print(f"  等效 GPIO: {batch_rate * len(pins):,.0f} ops/sec")

    # 测试 2: 交替批量写入（模拟呼吸灯）
    print(f"\n【测试 2】交替批量写入（模拟呼吸灯）")
    start = time.perf_counter()
    for _ in range(iterations):
        # 全亮
        ops.批量写入([(f"gpio_{p}", True) for p in pins])
        # 全灭
        ops.批量写入([(f"gpio_{p}", False) for p in pins])
    toggle_time = (time.perf_counter() - start) * 1000
    toggle_rate = (iterations * 2) / (toggle_time / 1000)

    print(f"  总耗时:   {toggle_time:.1f}ms")
    print(f"  单次耗时: {toggle_time/(iterations*2):.4f}ms")
    print(f"  吞吐量:   {toggle_rate:,.0f} ops/sec")

    # 测试 3: PWM 模拟（40 级亮度）
    print(f"\n【测试 3】PWM 模拟（40 级亮度渐变）")
    pwm_steps = 40
    start = time.perf_counter()
    for _ in range(iterations):
        for brightness in range(0, 101, 3):
            values = [(f"gpio_{p}", brightness / 100.0) for p in pins]
            ops.批量写入(values)
    pwm_time = (time.perf_counter() - start) * 1000
    total_ops = iterations * (100 // 3)
    pwm_rate = total_ops / (pwm_time / 1000)

    print(f"  总耗时:   {pwm_time:.1f}ms")
    print(f"  总操作数: {total_ops:,}")
    print(f"  吞吐量:   {pwm_rate:,.0f} ops/sec")

    # 性能分析
    print(f"\n{'=' * 60}")
    print(f"  10kHz 频率可行性分析")
    print(f"{'=' * 60}")
    target_period_us = 100  # 10kHz = 100μs
    actual_period_us = (batch_time / iterations) * 1000  # ms → μs

    print(f"""
  目标频率:     10 kHz (周期 100μs)
  实际周期:     {actual_period_us:.1f} μs
  实际频率:     {1e6/max(actual_period_us, 0.001):.0f} Hz

  结论:
    {'✓ 满足 10kHz 要求' if actual_period_us < target_period_us else '✗ 不满足 10kHz 要求'}

  异步队列分析:
    - 当前队列大小: 1000
    - 当前消费速度: ~{batch_rate*len(pins):,.0f} ops/sec
    - 10kHz 需求: 10,000 ops/sec
    - 队列深度需求: ~{(10000/batch_rate)*1.5:.0f} (1.5x 安全系数)
    - 当前队列: {'充足' if 1000 > (10000/batch_rate)*1.5 else '需要扩大'}
""")

    # 清理
    for led in leds:
        hal.unregister(led.name)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Matha v4.1 — 多路 LED 同步呼吸灯 Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python demos/multi_led_breathing.py              # 同步呼吸灯
  python demos/multi_led_breathing.py --mode chase # 跑马灯
  python demos/multi_led_breathing.py --benchmark  # 性能测试
  python demos/multi_led_breathing.py --pins 18,19 # 自定义引脚
        """
    )
    parser.add_argument("--mode", choices=["sync", "chase", "flash", "benchmark"],
                       default="sync", help="演示模式（默认 sync）")
    parser.add_argument("--pins", type=str, default="18,19,20,21",
                       help="GPIO 引脚列表（逗号分隔，默认 18,19,20,21）")
    parser.add_argument("--duration", type=float, default=3.0,
                       help="呼吸周期时长（秒，默认 3.0）")
    parser.add_argument("--speed", type=float, default=0.1,
                       help="跑马灯速度（秒，默认 0.1）")
    parser.add_argument("--iterations", type=int, default=10000,
                       help="基准测试迭代次数")

    args = parser.parse_args()

    # 解析引脚
    pins = [int(p.strip()) for p in args.pins.split(",")]

    # 运行演示
    if args.mode == "sync":
        sync_breathing_demo(pins=pins, duration=args.duration)
    elif args.mode == "chase":
        chase_light_demo(pins=pins, speed=args.speed)
    elif args.mode == "flash":
        alternating_flashing_demo(pins=pins)
    elif args.mode == "benchmark":
        benchmark_test(args.iterations)
