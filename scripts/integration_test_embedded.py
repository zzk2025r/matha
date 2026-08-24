# -*- coding: utf-8 -*-
"""
Matha RISC-V 嵌入式硬件集成测试

测试范围:
  1. I2C 总线通信 (ADS1115 温度传感器)
  2. 线性代数矩阵运算 (RISC-V 嵌入式场景)
  3. GPIO 控制 (LED/按钮)
  4. PWM 电机调速
  5. 看门狗复位功能
  6. 端到端集成 (完整嵌入式项目流程)

运行方式:
  python scripts/integration_test_embedded.py
  pytest scripts/integration_test_embedded.py -v
"""
from __future__ import annotations
import sys
import os
import time
import math
import unittest
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from riscv_embedded_demo import (
    I2CBus, I2CConfig,
    ADS1115Config, ADSTemperatureSensor, I2CError,
    Matrix,
    GPIOPin, PWMChannel,
    generate_i2c_sensor_c, generate_linalg_c,
    generate_embedded_project_template,
)


# 内联 WatchdogTimer (与 tests/test_riscv_embedded.py 保持一致)
class WatchdogTimer:
    """RISC-V 看门狗定时器模拟。"""
    def __init__(self, timeout_ms: int = 2000):
        self.timeout_ms = timeout_ms
        self._running = False
        self._last_feed_ms = 0
        self._feed_count = 0
        self._reset_count = 0
        self._sim_time_ms = 0
        self._was_timeout = False

    def start(self):
        self._running = True
        self._last_feed_ms = self._sim_time_ms
        self._was_timeout = False

    def feed(self):
        if not self._running:
            raise RuntimeError("看门狗未启动")
        self._last_feed_ms = self._sim_time_ms
        self._feed_count += 1
        self._was_timeout = False

    def tick(self, dt_ms: int = 1):
        self._sim_time_ms += dt_ms
        if self._running:
            elapsed = self._sim_time_ms - self._last_feed_ms
            is_now_timeout = elapsed > self.timeout_ms
            if is_now_timeout and not self._was_timeout:
                self._reset_count += 1
            self._was_timeout = is_now_timeout

    def is_timeout(self) -> bool:
        if not self._running:
            return False
        elapsed = self._sim_time_ms - self._last_feed_ms
        return elapsed > self.timeout_ms

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "timeout_ms": self.timeout_ms,
            "feed_count": self._feed_count,
            "reset_count": self._reset_count,
            "elapsed_since_feed_ms": self._sim_time_ms - self._last_feed_ms,
        }


def generate_watchdog_c_code() -> str:
    """生成 RISC-V 看门狗 C 代码。"""
    return '''/*
 * Matha RISC-V 看门狗复位驱动
 * 目标: SiFive FE310 (RISC-V 32-bit)
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>

#define WDT_BASE          0x40002000UL
#define WDT_CTRL          (*(volatile uint32_t *)(WDT_BASE + 0x00))
#define WDT_STATUS        (*(volatile uint32_t *)(WDT_BASE + 0x04))
#define WDT_LOAD          (*(volatile uint32_t *)(WDT_BASE + 0x08))
#define WDT_VALUE         (*(volatile uint32_t *)(WDT_BASE + 0x0C))

typedef struct {
    uint32_t timeout_ms;
    uint32_t last_feed_ms;
    uint32_t feed_count;
    uint32_t reset_count;
    bool     running;
} WatchdogDriver;

WatchdogDriver wdt;

void wdt_init(uint32_t timeout_ms) {
    wdt.timeout_ms = timeout_ms;
    wdt.last_feed_ms = 0;
    wdt.feed_count = 0;
    wdt.reset_count = 0;
    wdt.running = false;
    uint32_t load_val = (156000000UL * timeout_ms) / 1000UL / 1024UL;
    WDT_LOAD = load_val;
    WDT_CTRL = 0x10;
}

void wdt_start(void) {
    wdt.running = true;
    wdt.last_feed_ms = 0;
    WDT_CTRL |= 0x04;
    printf("[WDT] 看门狗启动, 超时=%lu ms\\n", wdt.timeout_ms);
}

void wdt_feed(void) {
    if (!wdt.running) { printf("[WDT] 错误: 看门狗未启动\\n"); return; }
    wdt.last_feed_ms = 0;
    wdt.feed_count++;
    WDT_CTRL |= 0x04;
    printf("[WDT] 喂狗 #%lu\\n", wdt.feed_count);
}

bool wdt_is_timeout(void) {
    if (!wdt.running) return false;
    return (WDT_STATUS & 0x02) != 0;
}

void wdt_handle_timeout(void) {
    wdt.reset_count++;
    printf("[WDT] 超时! 复位次数=%lu\\n", wdt.reset_count);
}

void wdt_stop(void) {
    wdt.running = false;
    WDT_CTRL = 0;
    printf("[WDT] 看门狗停止\\n");
}

int main(void) {
    wdt_init(2000);
    wdt_start();
    while (1) {
        wdt_feed();
        if (wdt_is_timeout()) wdt_handle_timeout();
    }
    return 0;
}
'''


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 1: I2C 总线端到端集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestI2CIntegration(unittest.TestCase):
    """I2C 总线端到端集成测试。"""

    def setUp(self):
        """设置测试环境。"""
        self.bus = I2CBus(I2CConfig(bus=1, address=0x48, clock_speed=100000))
        self.sensor_cfg = ADS1115Config(
            i2c_addr=0x48,
            channel=0,
            gain=1,
            data_rate=860,
        )
        self.sensor = ADSTemperatureSensor(self.bus, self.sensor_cfg)

    def test_full_init_sequence(self):
        """完整初始化序列。"""
        # 1. 初始化 I2C 总线
        self.assertTrue(self.bus.init())
        # 2. 扫描设备
        devices = self.bus.scan()
        self.assertIn(0x48, devices, "ADS1115 should be detected on I2C bus")
        # 3. 初始化传感器
        self.assertTrue(self.sensor.init())
        # 4. 验证配置写入
        self.bus.write_reg(0x01, b'\xC0\x86')
        val = self.bus._sim_regs.get(0x01, 0)
        self.assertEqual(val, 0xC086)

    def test_read_temperature_loop(self):
        """温度读取循环测试 (模拟实时采集)。"""
        self.sensor.init()
        temps = []
        for i in range(10):
            temp = self.sensor.read_temperature("lm35")
            temps.append(temp)
            time.sleep(0.01)  # 模拟采样间隔

        self.assertEqual(len(temps), 10)
        self.assertEqual(len(self.sensor._temp_history), 10)

    def test_multiple_sensors_same_bus(self):
        """同一 I2C 总线上连接多个传感器。"""
        sensor1 = ADSTemperatureSensor(self.bus, ADS1115Config(i2c_addr=0x48, channel=0))
        sensor2 = ADSTemperatureSensor(self.bus, ADS1115Config(i2c_addr=0x49, channel=1))

        sensor1.init()
        sensor2.init()

        # 两个传感器可以独立读取
        temp1 = sensor1.read_temperature("lm35")
        temp2 = sensor2.read_temperature("lm35")
        self.assertIsInstance(temp1, float)
        self.assertIsInstance(temp2, float)

    def test_i2c_protocol_c_code_valid(self):
        """生成的 I2C C 代码语法正确性。"""
        c_code = generate_i2c_sensor_c()
        # 检查关键函数都存在
        self.assertIn("void i2c_init", c_code)
        self.assertIn("bool i2c_write_reg", c_code)
        self.assertIn("bool i2c_read_reg", c_code)
        self.assertIn("void ads1115_init", c_code)
        self.assertIn("int16_t ads1115_read_raw", c_code)
        self.assertIn("float ads1115_read_temperature_lm35", c_code)
        self.assertIn("int main(void)", c_code)

    def test_i2c_c_code_compilable_structure(self):
        """生成的 I2C C 代码结构可编译。"""
        c_code = generate_i2c_sensor_c()
        # 检查必要的头文件
        self.assertIn("#include <stdint.h>", c_code)
        self.assertIn("#include <stdbool.h>", c_code)
        # 检查寄存器定义
        self.assertIn("I2C_BASE_ADDR", c_code)
        self.assertIn("ADS1115_REG_CONVERT", c_code)
        self.assertIn("ADS1115_REG_CONFIG", c_code)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 2: 线性代数嵌入式场景集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestLinalgEmbedded(unittest.TestCase):
    """线性代数嵌入式场景测试。"""

    def test_matrix_filter_3x3(self):
        """3x3 矩阵滤波器 (嵌入式常用)。"""
        # 简单的移动平均滤波器系数矩阵
        kernel = Matrix.from_list([
            [1.0/9, 1.0/9, 1.0/9],
            [1.0/9, 1.0/9, 1.0/9],
            [1.0/9, 1.0/9, 1.0/9],
        ])
        # 验证核矩阵的行列式接近 0 (秩为 1)
        det = kernel.determinant()
        self.assertAlmostEqual(det, 0.0, places=5)

    def test_transformation_matrix(self):
        """坐标变换矩阵 (嵌入式导航)。"""
        # 旋转矩阵 (45度)
        angle = math.pi / 4
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        rot = Matrix.from_list([
            [cos_a, -sin_a],
            [sin_a,  cos_a],
        ])
        # 旋转矩阵的行列式应为 1
        self.assertAlmostEqual(rot.determinant(), 1.0, places=5)
        # 旋转矩阵的逆应等于转置
        rot_T = rot.transpose()
        rot_inv = rot.inverse()
        self.assertTrue(rot_T == rot_inv)

    def test_control_matrix(self):
        """控制系统状态空间矩阵。"""
        # 离散化控制系统矩阵
        A = Matrix.from_list([
            [1.0, 0.1],
            [0.0, 1.0],
        ])
        B = Matrix.from_list([
            [0.0],
            [0.1],
        ])
        # A 的特征值应接近 1 (单位反馈)
        # det(A - λI) = (1-λ)(1-λ) = 0 → λ = 1
        I = Matrix.identity(2)
        diff = A - (I * 1.0)
        self.assertAlmostEqual(diff.determinant(), 0.0, places=5)

    def test_matrix_power_motor_control(self):
        """矩阵幂用于电机控制预测。"""
        # 简单的二阶系统矩阵
        F = Matrix.from_list([
            [1.0, 0.1],
            [0.0, 0.9],
        ])
        # F^10 应收敛 (因为特征值 < 1)
        F10 = F.mat_pow(10)
        # 检查矩阵元素不发散
        for i in range(2):
            for j in range(2):
                self.assertLessEqual(abs(F10.data[i][j]), 2.0)

    def test_c_code_include_all_functions(self):
        """C 代码包含所有必要的矩阵函数。"""
        c_code = generate_linalg_c()
        functions = [
            "mat_init", "mat_identity", "mat_copy",
            "mat_add", "mat_mul", "mat_det", "mat_inv",
            "example_matrix_operations", "int main(void)",
        ]
        for func in functions:
            self.assertIn(func, c_code, f"Missing function: {func}")

    def test_c_code_includes_riscv_definitions(self):
        """C 代码包含 RISC-V 相关定义。"""
        c_code = generate_linalg_c()
        self.assertIn("RISC-V", c_code)
        self.assertIn("SiFive FE310", c_code)
        self.assertIn("float", c_code)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 3: GPIO + PWM 电机控制集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPIOIntegrated(unittest.TestCase):
    """GPIO 控制集成测试。"""

    def test_button_led_interaction(self):
        """按钮控制 LED 的完整交互。"""
        button = GPIOPin(0, "INPUT")
        led = GPIOPin(1, "OUTPUT")

        # 初始状态: LED 灭
        self.assertEqual(led.get(), 0)

        # 模拟按钮按下
        for _ in range(3):
            button.set(1)  # 按钮按下
            led.toggle()   # LED 翻转
            button.set(0)  # 按钮释放

        self.assertEqual(led.get(), 1)  # 3次翻转后为高

    def test_multiple_gpio_pins(self):
        """多 GPIO 引脚同时操作。"""
        pins = [GPIOPin(i, "OUTPUT") for i in range(4)]
        # 同时设置所有引脚
        for pin in pins:
            pin.high()
        # 验证所有引脚状态
        for i, pin in enumerate(pins):
            self.assertEqual(pin.get(), 1, f"Pin {i} should be high")

    def test_gpio_input_reading(self):
        """GPIO 输入读取。"""
        btn = GPIOPin(0, "INPUT")
        # 默认值为 0 (无上拉)
        self.assertEqual(btn.get(), 0)
        # 模拟外部信号
        btn.set(1)
        self.assertEqual(btn.get(), 1)

    def test_gpio_edge_case_invalid_mode(self):
        """GPIO 无效模式处理。"""
        # 允许任意字符串作为 mode，不强制枚举
        pin = GPIOPin(5, "ANALOG")
        self.assertEqual(pin.mode, "ANALOG")

    def test_gpio_repr_format(self):
        """GPIO 字符串表示格式。"""
        pin = GPIOPin(3, "OUTPUT")
        pin.high()
        rep = repr(pin)
        self.assertIn("GPIOPin", rep)
        self.assertIn("3", rep)
        self.assertIn("OUTPUT", rep)
        self.assertIn("val=1", rep)


class TestPWMIntegrated(unittest.TestCase):
    """PWM 电机控制集成测试。"""

    def test_motor_speed_profile(self):
        """电机速度曲线测试 (加速→匀速→减速→停止)。"""
        motor = PWMChannel(GPIOPin(3), freq=20000)
        motor.start()

        # 加速阶段
        for speed in [0, 20, 40, 60, 80, 100]:
            motor.set_speed(speed)
            self.assertAlmostEqual(motor.duty_cycle, speed / 100.0)

        # 减速阶段
        for speed in [80, 60, 40, 20, 0]:
            motor.set_speed(speed)
            self.assertAlmostEqual(motor.duty_cycle, speed / 100.0)

        motor.stop()
        self.assertFalse(motor._running)

    def test_motor_direction_change(self):
        """电机方向切换测试。"""
        motor = PWMChannel(GPIOPin(3), freq=10000)
        motor.start()

        # 正转
        motor.set_speed(50.0)
        self.assertEqual(motor._direction, "forward")

        # 停止
        motor.set_speed(0.0)
        self.assertEqual(motor.duty_cycle, 0.0)

        # 反转
        motor.set_speed(-50.0)
        self.assertEqual(motor._direction, "reverse")
        self.assertAlmostEqual(motor.duty_cycle, 0.5)

        motor.stop()

    def test_pwm_frequency_variations(self):
        """不同 PWM 频率测试。"""
        freqs = [1000, 5000, 20000, 50000]
        for freq in freqs:
            pwm = PWMChannel(GPIOPin(0), freq=freq)
            expected_period = 1000000 // freq
            self.assertEqual(pwm.period, expected_period,
                           f"Frequency {freq}Hz should have period {expected_period}us")

    def test_pwm_stats_comprehensive(self):
        """PWM 统计信息完整性。"""
        motor = PWMChannel(GPIOPin(5), freq=15000)
        motor.start()
        motor.duty_cycle = 0.6
        stats = motor.get_stats()

        self.assertEqual(stats['pin'], 5)
        self.assertEqual(stats['freq'], 15000)
        self.assertAlmostEqual(stats['duty_cycle'], 0.6)
        self.assertTrue(stats['running'])
        self.assertEqual(stats['period_us'], 1000000 // 15000)

    def test_pwm_brake_sequence(self):
        """电机刹车序列。"""
        motor = PWMChannel(GPIOPin(2), freq=20000)
        motor.start()
        motor.set_speed(100.0)  # 全速
        self.assertTrue(motor._running)

        motor.stop()  # 刹车
        self.assertFalse(motor._running)
        # stop() 不修改 duty_cycle，仅停止输出
        # 先设置 0 速度再停止，验证完整刹车流程
        motor.set_speed(0.0)
        self.assertEqual(motor.duty_cycle, 0.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 4: 看门狗系统级集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestWatchdogSystemIntegration(unittest.TestCase):
    """看门狗系统级集成测试。"""

    def test_normal_operation_cycle(self):
        """正常操作循环 (持续喂狗)。"""
        wd = WatchdogTimer(timeout_ms=1000)
        wd.start()

        # 模拟 10 秒正常运行
        for _ in range(100):
            wd.tick(100)  # 每 100ms
            wd.feed()     # 每 100ms 喂狗
            self.assertFalse(wd.is_timeout())

        self.assertEqual(wd._feed_count, 100)
        self.assertEqual(wd._reset_count, 0)

    def test_timeout_recovery_cycle(self):
        """超时恢复循环。"""
        wd = WatchdogTimer(timeout_ms=500)
        wd.start()

        # 正常工作 2 秒
        for _ in range(20):
            wd.tick(100)
            wd.feed()
        self.assertFalse(wd.is_timeout())

        # 模拟故障：停止喂狗
        wd.tick(600)
        self.assertTrue(wd.is_timeout())
        self.assertEqual(wd._reset_count, 1)

        # 喂狗恢复
        wd.feed()
        self.assertFalse(wd.is_timeout())

        # 再次超时
        wd.tick(600)
        self.assertTrue(wd.is_timeout())
        self.assertEqual(wd._reset_count, 2)

    def test_power_on_reset_sequence(self):
        """上电复位序列。"""
        wd = WatchdogTimer(timeout_ms=2000)

        # 上电未启动
        self.assertFalse(wd._running)
        self.assertFalse(wd.is_timeout())

        # 系统启动后初始化看门狗
        wd.start()
        self.assertTrue(wd._running)

        # 快速喂狗确认系统正常
        wd.feed()
        self.assertEqual(wd._feed_count, 1)

    def test_cascading_timeout(self):
        """级联超时测试 (多个看门狗实例)。"""
        wd1 = WatchdogTimer(timeout_ms=500)
        wd2 = WatchdogTimer(timeout_ms=1000)
        wd1.start()
        wd2.start()

        # 两个看门狗独立运行
        for i in range(30):
            wd1.tick(50)
            wd2.tick(50)
            if i % 5 == 0:
                wd1.feed()
            if i % 10 == 0:
                wd2.feed()

        # wd1 多次喂狗，wd2 偶尔喂狗
        self.assertEqual(wd1._feed_count, 6)
        self.assertGreater(wd2._feed_count, 0)

    def test_embedded_project_c_code_complete(self):
        """嵌入式项目 C 代码完整性检查。"""
        c_code = generate_embedded_project_template()
        # 必需的函数
        required_functions = [
            "gpio_init", "gpio_read", "gpio_set", "gpio_toggle",
            "motor_init", "motor_set_speed", "motor_stop",
            "i2c_init", "i2c_write_reg", "i2c_read_reg",
            "read_temperature",
            "uart_init", "uart_send_byte", "uart_send_string",
            "int main(void)",
        ]
        for func in required_functions:
            self.assertIn(func, c_code, f"Missing required function: {func}")


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 5: 端到端嵌入式项目集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmbeddedProjectE2E(unittest.TestCase):
    """端到端嵌入式项目集成测试。"""

    def test_full_system_initialization(self):
        """完整系统初始化序列。"""
        # 1. 初始化 I2C 总线
        bus = I2CBus(I2CConfig(bus=1, address=0x48))
        self.assertTrue(bus.init())

        # 2. 初始化温度传感器
        sensor_cfg = ADS1115Config(i2c_addr=0x48, channel=0, gain=1, data_rate=860)
        sensor = ADSTemperatureSensor(bus, sensor_cfg)
        self.assertTrue(sensor.init())

        # 3. 初始化 GPIO
        btn = GPIOPin(0, "INPUT")
        led = GPIOPin(1, "OUTPUT")
        motor_en = GPIOPin(2, "OUTPUT")
        self.assertEqual(btn.get(), 0)
        self.assertEqual(led.get(), 0)
        self.assertEqual(motor_en.get(), 0)

        # 4. 初始化 PWM 电机
        motor = PWMChannel(led, freq=20000)
        motor.start()

        # 5. 初始化看门狗
        wd = WatchdogTimer(timeout_ms=2000)
        wd.start()

        # 6. 模拟系统运行循环
        for cycle in range(5):
            # 读取温度
            temp = sensor.read_temperature("lm35")
            self.assertIsInstance(temp, float)

            # 喂狗
            wd.feed()
            self.assertFalse(wd.is_timeout())

            # 读取按钮状态
            btn_val = btn.get()
            self.assertIn(btn_val, [0, 1])

        # 7. 停止所有外设
        motor.stop()
        self.assertFalse(motor._running)

    def test_memory_bounds_checking(self):
        """内存边界检查 (PointerManager 模拟)。"""
        # 模拟嵌入式系统的内存操作边界
        buffer_size = 256
        buffer = [0] * buffer_size

        # 写入操作边界测试
        for i in range(buffer_size):
            buffer[i] = i % 256

        # 越界写入应被捕获 (在真实硬件中由 PointerManager 处理)
        # Python list 本身会抛 IndexError
        try:
            _ = buffer[buffer_size]
            self.fail("Expected IndexError for buffer[256]")
        except IndexError:
            pass

        try:
            _ = buffer[-1]  # -1 是合法的 (最后一个元素)
            # Python 中 -1 是合法的索引，不是越界
        except IndexError:
            self.fail("Expected -1 to be valid index")

    def test_concurrent_operations(self):
        """并发操作测试 (模拟多任务嵌入式环境)。"""
        bus = I2CBus(I2CConfig(bus=1, address=0x48))
        bus.init()

        sensor = ADSTemperatureSensor(bus, ADS1115Config())
        sensor.init()

        motor = PWMChannel(GPIOPin(3), freq=20000)
        motor.start()

        wd = WatchdogTimer(timeout_ms=1000)
        wd.start()

        # 模拟并发操作
        results = []
        for i in range(10):
            # I2C 读取
            temp = sensor.read_temperature("lm35")
            # PWM 调速
            motor.set_speed(50.0 if i % 2 == 0 else 75.0)
            # 看门狗喂狗
            wd.tick(100)
            wd.feed()
            # 收集结果
            results.append({
                'temp': temp,
                'duty': motor.duty_cycle,
                'timeout': wd.is_timeout(),
            })

        # 验证所有操作正常完成
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertIsInstance(r['temp'], float)
            self.assertIn(r['duty'], [0.5, 0.75])
            self.assertFalse(r['timeout'])

        motor.stop()

    def test_error_recovery_sequence(self):
        """错误恢复序列测试。"""
        bus = I2CBus(I2CConfig(bus=1, address=0xFF))  # 不存在的设备
        bus.init()

        sensor = ADSTemperatureSensor(bus, ADS1115Config(i2c_addr=0xFF))
        sensor.init()

        # 传感器应能正常初始化 (仿真模式)
        temp = sensor.read_temperature("lm35")
        self.assertIsInstance(temp, float)

        # 仿真模式下不抛出 I2CError，但真实硬件模式下会
        # 此处仅验证传感器能持续读取而不会崩溃
        for _ in range(3):
            temp = sensor.read_temperature("lm35")
            self.assertIsInstance(temp, float)

    def test_all_generated_c_code_valid(self):
        """所有生成的 C 代码语法完整性。"""
        c_modules = [
            ("I2C Sensor", generate_i2c_sensor_c()),
            ("Linear Algebra", generate_linalg_c()),
            ("Embedded Project", generate_embedded_project_template()),
            ("Watchdog", generate_watchdog_c_code()),
        ]

        for name, code in c_modules:
            # 检查基本结构
            self.assertIn("#include", code, f"{name}: missing #include")
            self.assertIn("void", code, f"{name}: missing function declarations")
            # 检查括号平衡
            self.assertEqual(code.count('{'), code.count('}'),
                           f"{name}: unbalanced braces")
            self.assertEqual(code.count('('), code.count(')'),
                           f"{name}: unbalanced parentheses")

    def test_makefile_targets_exist(self):
        """Makefile 目标存在性检查。"""
        makefile_path = os.path.join(os.path.dirname(__file__), '..', 'Makefile')
        self.assertTrue(os.path.exists(makefile_path), "Makefile not found")

        with open(makefile_path, 'r') as f:
            content = f.read()

        required_targets = [
            'all:', 'clean:', 'test:', 'generate:',
            'check_toolchain:', 'syntax-check:', 'logs:',
        ]
        for target in required_targets:
            self.assertIn(target, content, f"Missing Makefile target: {target}")

    def test_linker_script_structure(self):
        """链接脚本结构验证。"""
        link_script_path = os.path.join(os.path.dirname(__file__), '..', 'link.ld')
        self.assertTrue(os.path.exists(link_script_path), "link.ld not found")

        with open(link_script_path, 'r') as f:
            content = f.read()

        self.assertIn("MEMORY", content)
        self.assertIn("FLASH", content)
        self.assertIn("RAM", content)
        self.assertIn(".text", content)
        self.assertIn(".bss", content)
        self.assertIn(".data", content)

    def test_entry_point_assembly(self):
        """入口点汇编代码验证。"""
        entry_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'entry.S')
        self.assertTrue(os.path.exists(entry_path), "entry.S not found")

        with open(entry_path, 'r') as f:
            content = f.read()

        self.assertIn("_start:", content)
        self.assertIn("la sp", content)  # 初始化栈指针
        self.assertIn("call main", content)  # 调用 main
        self.assertIn("wfi", content)  # 等待中断
        self.assertIn(".section .entry", content)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试运行入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  Matha RISC-V 嵌入式硬件集成测试")
    print("=" * 70)
    print()

    # 运行测试
    unittest.main(verbosity=2)
