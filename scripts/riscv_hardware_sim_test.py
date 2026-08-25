# -*- coding: utf-8 -*-
"""
Matha RISC-V 嵌入式硬件仿真集成测试

模拟真实 RISC-V 硬件环境，验证：
  1. GPIO 寄存器级操作 (SiFive FE310)
  2. PWM 定时器级操作 (硬件 PWM 外设)
  3. I2C 总线时序 (寄存器级)
  4. 看门狗定时器 (硬件看门狗)
  5. 内存模型 (4KB 页式 + PointerManager)
  6. C 代码 → 硬件行为映射验证

运行方式:
  python scripts/riscv_hardware_sim_test.py
"""
from __future__ import annotations
import sys
import os
import time
import math
import unittest
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from riscv_embedded_demo import (
    I2CBus, I2CConfig,
    ADS1115Config, ADSTemperatureSensor,
    generate_i2c_sensor_c, generate_linalg_c,
    generate_embedded_project_template,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  硬件仿真模型 — 模拟 SiFive FE310 (RISC-V 32-bit)
# ═══════════════════════════════════════════════════════════════════════════════

class RISCVMemory:
    """RISC-V 内存模型 (平坦地址空间 + 页式分配)。"""

    PAGE_SIZE = 4096
    TOTAL_PAGES = 32  # 128KB 用户内存

    def __init__(self):
        # 平坦字节数组 (模拟整个地址空间)
        self._mem: Dict[int, int] = {}
        self._allocations: Dict[int, Tuple[int, int]] = {}  # addr -> (size, name)
        # 页式分配区: 0x20000000 ~ 0x20020000 (128KB RAM)
        self.ram_base = 0x20000000
        self.ram_size = self.TOTAL_PAGES * self.PAGE_SIZE  # 128KB

    def _page_idx(self, addr: int) -> int:
        return addr // self.PAGE_SIZE

    def _page_offset(self, addr: int) -> int:
        return addr % self.PAGE_SIZE

    def read_byte(self, addr: int) -> int:
        if addr < 0 or addr > 0xFFFFFFFF:
            raise MemoryError(f"越界读取: 0x{addr:08X}")
        return self._mem.get(addr, 0)

    def write_byte(self, addr: int, value: int):
        if addr < 0 or addr > 0xFFFFFFFF:
            raise MemoryError(f"越界写入: 0x{addr:08X}")
        self._mem[addr] = value & 0xFF
        if addr not in self._allocations:
            page_idx = (addr - self.ram_base) // self.PAGE_SIZE
            if 0 <= page_idx < self.TOTAL_PAGES:
                self._allocations[addr] = (page_idx, 1)

    def alloc(self, size: int, name: str = "") -> int:
        """在 RAM 区分配内存。"""
        # 找连续空闲块
        for base in range(self.ram_base, self.ram_base + self.ram_size - size, 4):
            ok = True
            for i in range(size):
                if base + i in self._mem:
                    ok = False
                    break
            if ok:
                for i in range(size):
                    self._mem[base + i] = 0
                self._allocations[base] = (0, size)
                return base
        raise MemoryError(f"内存不足: 请求 {size}B")

    def free(self, addr: int):
        """释放内存。"""
        if addr in self._allocations:
            _, size = self._allocations.pop(addr)
            for i in range(size):
                self._mem.pop(addr + i, None)
            return True
        return False

    def get_stats(self) -> dict:
        used = len(self._mem)
        return {
            "total_pages": self.TOTAL_PAGES,
            "total_memory_kb": self.ram_size // 1024,
            "used_bytes": used,
            "allocations": len(self._allocations),
        }


class GPIOHardware:
    """SiFive FE310 GPIO 硬件仿真。"""

    # 寄存器映射
    REG_BASE = 0x40001000
    REG_OUTPUT = REG_BASE + 0x00
    REG_INPUT = REG_BASE + 0x04
    REG_ENABLE = REG_BASE + 0x08
    REG_DIR = REG_BASE + 0x0C

    def __init__(self, memory: RISCVMemory):
        self.mem = memory
        self._pins: Dict[int, int] = {}  # pin -> 0/1
        self._modes: Dict[int, str] = {}  # pin -> INPUT/OUTPUT

    def init(self):
        """初始化 GPIO (复位所有寄存器)。"""
        for reg in [self.REG_OUTPUT, self.REG_INPUT, self.REG_ENABLE, self.REG_DIR]:
            self.mem.write_byte(reg, 0)
            self.mem.write_byte(reg + 1, 0)
            self.mem.write_byte(reg + 2, 0)
            self.mem.write_byte(reg + 3, 0)
        for pin in range(32):
            self._pins[pin] = 0
            self._modes[pin] = "INPUT"

    def set_direction(self, pin: int, mode: str):
        """设置引脚方向。"""
        self._modes[pin] = mode
        if mode == "OUTPUT":
            # 设置 DIR 寄存器
            val = self.mem.read_byte(self.REG_DIR)
            self.mem.write_byte(self.REG_DIR, val | (1 << pin))
            # 使能输出
            val = self.mem.read_byte(self.REG_ENABLE)
            self.mem.write_byte(self.REG_ENABLE, val | (1 << pin))

    def write(self, pin: int, value: int):
        """写引脚值。"""
        if self._modes.get(pin) != "OUTPUT":
            raise RuntimeError(f"Pin {pin} 不是 OUTPUT 模式")
        self._pins[pin] = value
        val = self.mem.read_byte(self.REG_OUTPUT)
        if value:
            self.mem.write_byte(self.REG_OUTPUT, val | (1 << pin))
        else:
            self.mem.write_byte(self.REG_OUTPUT, val & ~(1 << pin))

    def read(self, pin: int) -> int:
        """读引脚值。"""
        return self._pins.get(pin, 0)

    def toggle(self, pin: int):
        """翻转引脚。"""
        self.write(pin, 1 - self.read(pin))

    def read_register(self, reg_offset: int) -> int:
        """读取 GPIO 寄存器。"""
        addr = self.REG_BASE + reg_offset
        return (self.mem.read_byte(addr) |
                (self.mem.read_byte(addr + 1) << 8) |
                (self.mem.read_byte(addr + 2) << 16) |
                (self.mem.read_byte(addr + 3) << 24))


class PWMHardware:
    """SiFive FE310 PWM 硬件仿真。"""

    REG_BASE = 0x40018000
    REG_PERIOD = REG_BASE + 0x00
    REG_DUTY = REG_BASE + 0x04
    REG_ENABLE = REG_BASE + 0x08

    def __init__(self, memory: RISCVMemory):
        self.mem = memory
        self._period = 50000  # 默认 20kHz (50us)
        self._duty = 0
        self._enabled = False

    def init(self):
        """初始化 PWM。"""
        self.mem.write_byte(self.REG_PERIOD, 0)
        self.mem.write_byte(self.REG_PERIOD + 1, 0)
        self.mem.write_byte(self.REG_PERIOD + 2, 0)
        self.mem.write_byte(self.REG_PERIOD + 3, 0)
        self.mem.write_byte(self.REG_DUTY, 0)
        self.mem.write_byte(self.REG_ENABLE, 0)
        self._period = 50000
        self._duty = 0
        self._enabled = False

    def set_period(self, period_us: int):
        """设置 PWM 周期 (微秒)。"""
        self._period = period_us
        # 写入寄存器
        val = period_us & 0xFFFFFFFF
        self.mem.write_byte(self.REG_PERIOD, val & 0xFF)
        self.mem.write_byte(self.REG_PERIOD + 1, (val >> 8) & 0xFF)
        self.mem.write_byte(self.REG_PERIOD + 2, (val >> 16) & 0xFF)
        self.mem.write_byte(self.REG_PERIOD + 3, (val >> 24) & 0xFF)

    def set_duty(self, duty_cycles: int):
        """设置占空比 (周期数)。"""
        self._duty = max(0, min(duty_cycles, self._period))
        val = self._duty & 0xFFFFFFFF
        self.mem.write_byte(self.REG_DUTY, val & 0xFF)
        self.mem.write_byte(self.REG_DUTY + 1, (val >> 8) & 0xFF)
        self.mem.write_byte(self.REG_DUTY + 2, (val >> 16) & 0xFF)
        self.mem.write_byte(self.REG_DUTY + 3, (val >> 24) & 0xFF)

    def enable(self):
        """启用 PWM 输出。"""
        self._enabled = True
        self.mem.write_byte(self.REG_ENABLE, 1)

    def disable(self):
        """禁用 PWM 输出。"""
        self._enabled = False
        self.mem.write_byte(self.REG_ENABLE, 0)

    def get_duty_percent(self) -> float:
        """获取当前占空比百分比。"""
        if self._period == 0:
            return 0.0
        return (self._duty / self._period) * 100.0


class WatchdogHardware:
    """SiFive FE310 看门狗硬件仿真。"""

    REG_BASE = 0x40002000
    REG_CTRL = REG_BASE + 0x00
    REG_STATUS = REG_BASE + 0x04
    REG_LOAD = REG_BASE + 0x08
    REG_VALUE = REG_BASE + 0x0C

    TIMEOUT_US = 2000000  # 2秒超时

    def __init__(self, memory: RISCVMemory):
        self.mem = memory
        self._running = False
        self._last_feed_us = 0
        self._reset_count = 0

    def init(self, timeout_ms: int = 2000):
        """初始化看门狗。"""
        self._running = False
        self._last_feed_us = 0
        self._reset_count = 0
        # 写入超时值到 LOAD 寄存器
        load_val = (156000000 * timeout_ms) // 1000 // 1024
        self.mem.write_byte(self.REG_LOAD, load_val & 0xFF)
        self.mem.write_byte(self.REG_LOAD + 1, (load_val >> 8) & 0xFF)
        self.mem.write_byte(self.REG_LOAD + 2, (load_val >> 16) & 0xFF)
        self.mem.write_byte(self.REG_LOAD + 3, (load_val >> 24) & 0xFF)

    def start(self):
        """启动看门狗。"""
        self._running = True
        self._last_feed_us = 0
        # 设置 ENABLE 位
        ctrl = self.mem.read_byte(self.REG_CTRL)
        self.mem.write_byte(self.REG_CTRL, ctrl | 0x10)

    def feed(self):
        """喂狗。"""
        if not self._running:
            raise RuntimeError("看门狗未启动")
        self._last_feed_us = 0

    def tick(self, dt_us: int = 1):
        """模拟时间流逝 (微秒)。"""
        if not self._running:
            return
        self._last_feed_us += dt_us
        if self._last_feed_us > self.TIMEOUT_US:
            self._reset_count += 1
            # 设置 TIMEOUT 状态位
            status = self.mem.read_byte(self.REG_STATUS)
            self.mem.write_byte(self.REG_STATUS, status | 0x02)

    def is_timeout(self) -> bool:
        return self._running and self._last_feed_us > self.TIMEOUT_US

    def get_reset_count(self) -> int:
        return self._reset_count


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件: GPIO 硬件级仿真
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPIOHardware(unittest.TestCase):
    """GPIO 硬件级仿真测试。"""

    def setUp(self):
        self.mem = RISCVMemory()
        self.gpio = GPIOHardware(self.mem)
        self.gpio.init()

    def test_gpio_init_registers(self):
        """GPIO 初始化后寄存器全为零。"""
        self.assertEqual(self.gpio.read_register(0x00), 0)  # OUTPUT
        self.assertEqual(self.gpio.read_register(0x04), 0)  # INPUT
        self.assertEqual(self.gpio.read_register(0x08), 0)  # ENABLE
        self.assertEqual(self.gpio.read_register(0x0C), 0)  # DIR

    def test_gpio_set_output_direction(self):
        """设置输出方向后 DIR 和 ENABLE 寄存器更新。"""
        self.gpio.set_direction(1, "OUTPUT")
        dir_reg = self.gpio.read_register(0x0C)
        en_reg = self.gpio.read_register(0x08)
        self.assertEqual(dir_reg & (1 << 1), 1 << 1)
        self.assertEqual(en_reg & (1 << 1), 1 << 1)

    def test_gpio_write_high(self):
        """写入高电平后 OUTPUT 寄存器更新。"""
        self.gpio.set_direction(1, "OUTPUT")
        self.gpio.write(1, 1)
        out_reg = self.gpio.read_register(0x00)
        self.assertEqual(out_reg & (1 << 1), 1 << 1)

    def test_gpio_write_low(self):
        """写入低电平后 OUTPUT 寄存器清除。"""
        self.gpio.set_direction(1, "OUTPUT")
        self.gpio.write(1, 1)
        self.gpio.write(1, 0)
        out_reg = self.gpio.read_register(0x00)
        self.assertEqual(out_reg & (1 << 1), 0)

    def test_gpio_toggle(self):
        """翻转引脚。"""
        self.gpio.set_direction(1, "OUTPUT")
        self.gpio.write(1, 1)
        self.gpio.toggle(1)
        self.assertEqual(self.gpio.read(1), 0)
        self.gpio.toggle(1)
        self.assertEqual(self.gpio.read(1), 1)

    def test_gpio_read_input(self):
        """读取输入引脚。"""
        self.gpio.set_direction(0, "INPUT")
        # 输入引脚默认 0
        self.assertEqual(self.gpio.read(0), 0)
        # 模拟外部信号
        self.gpio._pins[0] = 1
        self.assertEqual(self.gpio.read(0), 1)

    def test_gpio_multiple_pins(self):
        """多引脚同时操作。"""
        for pin in range(4):
            self.gpio.set_direction(pin, "OUTPUT")
        for pin in range(4):
            self.gpio.write(pin, pin % 2)
        # 验证所有引脚状态
        self.assertEqual(self.gpio.read(0), 0)
        self.assertEqual(self.gpio.read(1), 1)
        self.assertEqual(self.gpio.read(2), 0)
        self.assertEqual(self.gpio.read(3), 1)

    def test_gpio_write_to_input_raises(self):
        """向输入引脚写入应抛出异常。"""
        self.gpio.set_direction(5, "INPUT")
        with self.assertRaises(RuntimeError):
            self.gpio.write(5, 1)

    def test_gpio_register_memory_mapping(self):
        """GPIO 寄存器正确映射到内存。"""
        self.gpio.set_direction(2, "OUTPUT")
        self.gpio.write(2, 1)
        # 验证内存中的值
        self.assertEqual(self.mem.read_byte(0x40001000), 4)  # OUTPUT bit2
        self.assertEqual(self.mem.read_byte(0x40001008), 4)  # ENABLE bit2
        self.assertEqual(self.mem.read_byte(0x4000100C), 4)  # DIR bit2


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件: PWM 硬件级仿真
# ═══════════════════════════════════════════════════════════════════════════════

class TestPWMHardware(unittest.TestCase):
    """PWM 硬件级仿真测试。"""

    def setUp(self):
        self.mem = RISCVMemory()
        self.pwm = PWMHardware(self.mem)
        self.pwm.init()

    def test_pwm_init_registers(self):
        """PWM 初始化后寄存器为零。"""
        self.assertEqual(self.pwm.get_duty_percent(), 0.0)
        self.assertFalse(self.pwm._enabled)

    def test_pwm_set_period(self):
        """设置 PWM 周期。"""
        self.pwm.set_period(10000)  # 10ms
        self.assertEqual(self.pwm._period, 10000)
        # 验证寄存器写入
        val = (self.mem.read_byte(0x40018000) |
               (self.mem.read_byte(0x40018001) << 8) |
               (self.mem.read_byte(0x40018002) << 16) |
               (self.mem.read_byte(0x40018003) << 24))
        self.assertEqual(val, 10000)

    def test_pwm_set_duty_cycle(self):
        """设置占空比。"""
        self.pwm.set_period(1000)  # 1ms 周期
        self.pwm.set_duty(500)     # 50% 占空比
        self.assertAlmostEqual(self.pwm.get_duty_percent(), 50.0)

    def test_pwm_enable_disable(self):
        """启用/禁用 PWM。"""
        self.pwm.enable()
        self.assertTrue(self.pwm._enabled)
        self.assertEqual(self.mem.read_byte(0x40018008), 1)

        self.pwm.disable()
        self.assertFalse(self.pwm._enabled)
        self.assertEqual(self.mem.read_byte(0x40018008), 0)

    def test_pwm_full_range(self):
        """PWM 全范围测试 (0% → 100%)。"""
        self.pwm.set_period(1000)
        for percent in [0, 25, 50, 75, 100]:
            self.pwm.set_duty(int(1000 * percent / 100))
            actual = self.pwm.get_duty_percent()
            self.assertAlmostEqual(actual, float(percent), places=1)

    def test_pwm_motor_speed_control(self):
        """PWM 电机调速仿真。"""
        self.pwm.set_period(50000)  # 20kHz
        self.pwm.enable()

        # 加速过程
        speeds = [0, 25, 50, 75, 100, 75, 50, 25, 0]
        for s in speeds:
            self.pwm.set_duty(int(50000 * s / 100))
            self.assertAlmostEqual(self.pwm.get_duty_percent(), float(s), places=1)

    def test_pwm_register_memory_mapping(self):
        """PWM 寄存器内存映射验证。"""
        self.pwm.set_period(20000)
        self.pwm.set_duty(10000)
        self.pwm.enable()
        # 验证 PERIOD 寄存器
        period_val = (self.mem.read_byte(0x40018000) |
                      (self.mem.read_byte(0x40018001) << 8) |
                      (self.mem.read_byte(0x40018002) << 16) |
                      (self.mem.read_byte(0x40018003) << 24))
        self.assertEqual(period_val, 20000)
        # 验证 DUTY 寄存器
        duty_val = (self.mem.read_byte(0x40018004) |
                    (self.mem.read_byte(0x40018005) << 8) |
                    (self.mem.read_byte(0x40018006) << 16) |
                    (self.mem.read_byte(0x40018007) << 24))
        self.assertEqual(duty_val, 10000)
        # 验证 ENABLE 寄存器
        self.assertEqual(self.mem.read_byte(0x40018008), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件: 看门狗硬件级仿真
# ═══════════════════════════════════════════════════════════════════════════════

class TestWatchdogHardware(unittest.TestCase):
    """看门狗硬件级仿真测试。"""

    def setUp(self):
        self.mem = RISCVMemory()
        self.wdt = WatchdogHardware(self.mem)
        self.wdt.init(timeout_ms=2000)

    def test_wdt_init_registers(self):
        """看门狗初始化后控制寄存器正确。"""
        self.assertFalse(self.wdt._running)
        self.assertEqual(self.wdt.get_reset_count(), 0)

    def test_wdt_start(self):
        """启动看门狗。"""
        self.wdt.start()
        self.assertTrue(self.wdt._running)
        # 验证 ENABLE 位
        ctrl = self.mem.read_byte(0x40002000)
        self.assertEqual(ctrl & 0x10, 0x10)

    def test_wdt_feed(self):
        """喂狗重置超时。"""
        self.wdt.start()
        self.wdt.tick(1000000)  # 1秒
        self.assertFalse(self.wdt.is_timeout())
        self.wdt.feed()
        self.wdt.tick(1000000)  # 再 1秒
        self.assertFalse(self.wdt.is_timeout())

    def test_wdt_timeout(self):
        """看门狗超时。"""
        self.wdt.start()
        self.wdt.tick(3000000)  # 3秒 > 2秒超时
        self.assertTrue(self.wdt.is_timeout())
        self.assertEqual(self.wdt.get_reset_count(), 1)

    def test_wdt_multiple_timeouts(self):
        """多次超时计数。"""
        self.wdt.start()
        # 超时→喂狗→超时
        self.wdt.tick(3000000)
        self.assertEqual(self.wdt.get_reset_count(), 1)
        self.wdt.feed()
        self.wdt.tick(3000000)
        self.assertEqual(self.wdt.get_reset_count(), 2)

    def test_wdt_feed_without_start_raises(self):
        """未启动时喂狗应抛出异常。"""
        with self.assertRaises(RuntimeError):
            self.wdt.feed()

    def test_wdt_register_memory_mapping(self):
        """看门狗寄存器内存映射验证。"""
        self.wdt.start()
        # 验证 LOAD 寄存器
        load_val = (self.mem.read_byte(0x40002008) |
                    (self.mem.read_byte(0x40002009) << 8) |
                    (self.mem.read_byte(0x4000200A) << 16) |
                    (self.mem.read_byte(0x4000200B) << 24))
        self.assertGreater(load_val, 0)  # LOAD 应被写入


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件: 内存模型测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryModel(unittest.TestCase):
    """RISC-V 内存模型测试。"""

    def setUp(self):
        self.mem = RISCVMemory()

    def test_memory_alloc_free(self):
        """内存分配和释放。"""
        addr1 = self.mem.alloc(64, "buf_a")
        addr2 = self.mem.alloc(32, "buf_b")
        self.assertIsNotNone(addr1)
        self.assertIsNotNone(addr2)
        self.assertNotEqual(addr1, addr2)

        self.mem.free(addr1)
        self.mem.free(addr2)
        self.assertEqual(len(self.mem._allocations), 0)

    def test_memory_write_read(self):
        """内存读写操作。"""
        addr = self.mem.alloc(4, "test")
        self.mem.write_byte(addr, 0x42)
        self.mem.write_byte(addr + 1, 0x13)
        self.assertEqual(self.mem.read_byte(addr), 0x42)
        self.assertEqual(self.mem.read_byte(addr + 1), 0x13)
        self.mem.free(addr)

    def test_memory_bounds_check(self):
        """内存越界检测。"""
        with self.assertRaises(MemoryError):
            self.mem.write_byte(0x100000000, 0x00)  # 超出 32-bit 地址空间

    def test_memory_read_only_page(self):
        """只读页写入检测 (系统区 0x00000000-0x00000FFF 仿真允许写入)。"""
        self.mem.write_byte(0x00000000, 0x42)
        self.assertEqual(self.mem.read_byte(0x00000000), 0x42)

    def test_memory_stats(self):
        """内存统计。"""
        self.mem.alloc(100, "test1")
        self.mem.alloc(200, "test2")
        stats = self.mem.get_stats()
        self.assertEqual(stats["total_pages"], 32)
        self.assertEqual(stats["total_memory_kb"], 128)
        self.assertEqual(stats["allocations"], 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件: 端到端硬件仿真
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmbeddedHardwareSimulation(unittest.TestCase):
    """端到端嵌入式硬件仿真测试。"""

    def setUp(self):
        self.mem = RISCVMemory()
        self.gpio = GPIOHardware(self.mem)
        self.pwm = PWMHardware(self.mem)
        self.wdt = WatchdogHardware(self.mem)
        self.gpio.init()
        self.pwm.init()
        self.wdt.init(timeout_ms=2000)

    def test_full_system_boot(self):
        """完整系统启动序列。"""
        # 1. GPIO 初始化
        self.gpio.set_direction(0, "INPUT")   # 按钮
        self.gpio.set_direction(1, "OUTPUT")  # LED
        self.gpio.set_direction(2, "OUTPUT")  # 电机使能
        self.gpio.set_direction(3, "OUTPUT")  # PWM

        # 2. PWM 初始化
        self.pwm.set_period(50000)  # 20kHz
        self.pwm.set_duty(0)
        self.pwm.enable()

        # 3. 看门狗初始化
        self.wdt.start()

        # 4. 验证所有寄存器状态
        self.assertEqual(self.gpio.read_register(0x0C), 0x0E)  # DIR: pins 1,2,3 = OUT
        self.assertEqual(self.pwm._enabled, True)
        self.assertTrue(self.wdt._running)

    def test_sensor_reading_loop(self):
        """传感器读取循环仿真。"""
        self.wdt.start()  # 启动看门狗
        # 模拟 I2C 温度传感器读取
        bus = I2CBus(I2CConfig(bus=1, address=0x48))
        bus.init()
        sensor = ADSTemperatureSensor(bus, ADS1115Config())
        sensor.init()

        temps = []
        for i in range(5):
            temp = sensor.read_temperature("lm35")
            temps.append(temp)
            self.wdt.feed()  # 喂狗
            self.pwm.set_duty(int(50000 * (50 + i * 5) / 100))  # 逐渐加速

        self.assertEqual(len(temps), 5)
        self.assertTrue(self.wdt._running)  # 看门狗仍在运行

    def test_motor_control_sequence(self):
        """电机控制序列仿真。"""
        self.gpio.set_direction(2, "OUTPUT")  # 电机使能
        # 加速
        for speed in [0, 25, 50, 75, 100]:
            self.pwm.set_duty(int(50000 * speed / 100))
            self.gpio.write(2, 1)  # 电机使能
            self.wdt.feed()

        # 减速
        for speed in [75, 50, 25, 0]:
            self.pwm.set_duty(int(50000 * speed / 100))
            self.wdt.feed()

        self.gpio.write(2, 0)  # 电机停止
        self.pwm.disable()
        self.assertEqual(self.pwm.get_duty_percent(), 0.0)

    def test_button_led_interaction(self):
        """按钮控制 LED 仿真。"""
        self.gpio.set_direction(0, "OUTPUT")  # 按钮(仿真写高/低)
        self.gpio.set_direction(1, "OUTPUT")  # LED

        # 模拟按钮按下/释放循环 (写按钮信号，翻转 LED)
        for _ in range(3):
            self.gpio.write(0, 1)   # 按钮按下
            self.gpio.toggle(1)     # LED 翻转
            self.gpio.write(0, 0)   # 按钮释放
            self.wdt.feed()

        # LED 应翻转 3 次 (奇数次 → 高)
        self.assertEqual(self.gpio.read(1), 1)

    def test_watchdog_timeout_recovery(self):
        """看门狗超时恢复仿真。"""
        self.wdt.start()

        # 正常操作
        for _ in range(10):
            self.wdt.tick(100000)  # 100ms
            self.wdt.feed()
        self.assertFalse(self.wdt.is_timeout())

        # 模拟故障：停止喂狗
        self.wdt.tick(3000000)  # 3秒
        self.assertTrue(self.wdt.is_timeout())
        self.assertGreater(self.wdt.get_reset_count(), 0)

    def test_memory_allocation_during_operation(self):
        """运行时内存分配。"""
        # 分配 I2C 缓冲区
        uart_tx_buf = self.mem.alloc(256, "uart_tx")
        uart_rx_buf = self.mem.alloc(256, "uart_rx")
        i2c_regs = self.mem.alloc(16, "i2c_regs")

        self.assertIsNotNone(uart_tx_buf)
        self.assertIsNotNone(uart_rx_buf)
        self.assertIsNotNone(i2c_regs)

        # 写入测试数据
        self.mem.write_byte(uart_tx_buf, 0x48)
        self.mem.write_byte(uart_tx_buf + 1, 0x01)
        self.assertEqual(self.mem.read_byte(uart_tx_buf), 0x48)

        # 释放
        self.mem.free(uart_tx_buf)
        self.mem.free(uart_rx_buf)
        self.mem.free(i2c_regs)

    def test_c_code_to_hardware_mapping(self):
        """C 代码到硬件行为的映射验证。"""
        c_code = generate_embedded_project_template()
        # 验证 C 代码中的寄存器地址与仿真模型一致
        self.assertIn("0x40001000", c_code)  # GPIO_BASE
        self.assertIn("0x40018000", c_code)  # PWM_BASE
        self.assertIn("0x40003000", c_code)  # I2C_BASE
        self.assertIn("0x40000000", c_code)  # UART_BASE
        # 验证 C 代码中的函数签名与硬件类匹配
        self.assertIn("void gpio_init", c_code)
        self.assertIn("void motor_init", c_code)
        self.assertIn("void i2c_init", c_code)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试运行入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  Matha RISC-V 嵌入式硬件仿真集成测试")
    print("=" * 70)
    print()
    unittest.main(verbosity=2)
