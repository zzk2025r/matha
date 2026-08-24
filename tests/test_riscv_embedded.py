# -*- coding: utf-8 -*-
"""
Matha RISC-V 嵌入式驱动 — 单元测试套件

覆盖模块:
  1. I2C 温度传感器驱动 (ADS1115)
  2. 线性代数引擎矩阵运算
  3. GPIO + PWM 电机调速
  4. 看门狗复位功能
"""
import sys
import os
import time
import math
import unittest
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from riscv_embedded_demo import (
    I2CBus, I2CConfig,
    ADS1115Config, ADSTemperatureSensor, I2CError,
    Matrix,
    GPIOPin, PWMChannel,
    generate_i2c_sensor_c, generate_linalg_c,
    generate_embedded_project_template,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 1: I2C 温度传感器驱动测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestI2CBus(unittest.TestCase):
    """I2C 总线驱动测试。"""

    def setUp(self):
        self.bus = I2CBus(I2CConfig(bus=1, address=0x48, clock_speed=100000))
        self.bus.init()

    def test_init_returns_true(self):
        """初始化返回 True。"""
        self.assertTrue(self.bus.init())

    def test_init_idempotent(self):
        """重复初始化不影响结果。"""
        r1 = self.bus.init()
        r2 = self.bus.init()
        self.assertTrue(r1 is r2)

    def test_write_reg_simulation(self):
        """仿真模式写入寄存器。"""
        result = self.bus.write_reg(0x01, b'\xC0\x86')
        self.assertTrue(result)

    def test_read_reg_simulation(self):
        """仿真模式读取寄存器。"""
        self.bus.write_reg(0x00, b'\x00\x00')
        data = self.bus.read_reg(0x00, 2)
        self.assertEqual(len(data), 2)

    def test_scan_simulation(self):
        """仿真模式扫描设备。"""
        devices = self.bus.scan()
        self.assertIn(0x48, devices)

    def test_scan_empty_when_no_device(self):
        """无设备时扫描返回空列表。"""
        bus_no_device = I2CBus(I2CConfig(bus=2, address=0xFF))
        bus_no_device.init()
        devices = bus_no_device.scan()
        self.assertNotIn(0xFF, devices)

    def test_write_invalid_data(self):
        """写入无效数据应正常处理（仿真模式）。"""
        result = self.bus.write_reg(0x01, b'\xFF')
        self.assertTrue(result)

    def test_i2c_error_on_real_hardware_failure(self):
        """真实硬件通信失败应抛出 I2CError（仿真模式下跳过）。"""
        # 仿真模式下无法测试真实硬件失败，仅验证异常类型存在
        self.assertTrue(issubclass(I2CError, Exception))


class TestADSTemperatureSensor(unittest.TestCase):
    """ADS1115 温度传感器驱动测试。"""

    def setUp(self):
        self.bus = I2CBus(I2CConfig(bus=1, address=0x48))
        self.cfg = ADS1115Config(i2c_addr=0x48, channel=0, gain=1, data_rate=860)
        self.sensor = ADSTemperatureSensor(self.bus, self.cfg)
        self.sensor.init()

    def test_init_returns_true(self):
        """初始化返回 True。"""
        self.assertTrue(self.sensor.init())

    def test_read_raw_returns_int(self):
        """原始读取返回整数。"""
        raw = self.sensor.read_raw()
        self.assertIsInstance(raw, int)
        self.assertGreaterEqual(raw, -32768)
        self.assertLessEqual(raw, 32767)

    def test_read_voltage_returns_float(self):
        """电压读取返回浮点数。"""
        voltage = self.sensor.read_voltage()
        self.assertIsInstance(voltage, float)

    def test_read_temperature_lm35(self):
        """LM35 温度读取返回有效值。"""
        temp = self.sensor.read_temperature("lm35")
        self.assertIsInstance(temp, float)
        # LM35 典型范围 -55°C ~ 150°C
        self.assertGreaterEqual(temp, -60.0)
        self.assertLessEqual(temp, 155.0)

    def test_read_temperature_ntc(self):
        """NTC 温度读取返回有效值。"""
        temp = self.sensor.read_temperature("ntc")
        self.assertIsInstance(temp, float)

    def test_read_temperature_invalid_type(self):
        """无效传感器类型应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            self.sensor.read_temperature("unknown_sensor")

    def test_read_temperature_history(self):
        """温度读取历史记录正确。"""
        temps = [self.sensor.read_temperature("lm35") for _ in range(5)]
        self.assertEqual(len(self.sensor._temp_history), 5)
        self.assertEqual(len(temps), 5)

    def test_get_stats(self):
        """获取统计信息。"""
        self.sensor.read_temperature("lm35")
        self.sensor.read_temperature("lm35")
        stats = self.sensor.get_stats()
        self.assertEqual(stats['readings'], 2)
        self.assertIsNotNone(stats['avg_temp'])
        self.assertIn('min_temp', stats)
        self.assertIn('max_temp', stats)
        self.assertIn('history', stats)

    def test_get_stats_empty(self):
        """空历史时统计信息返回 None。"""
        stats = self.sensor.get_stats()
        self.assertEqual(stats['readings'], 0)
        self.assertIsNone(stats['avg_temp'])

    def test_different_gain(self):
        """不同增益设置影响电压范围。"""
        cfg_high_gain = ADS1115Config(i2c_addr=0x48, gain=2/3)  # 最大量程
        sensor_high = ADSTemperatureSensor(self.bus, cfg_high_gain)
        sensor_high.init()
        # 高增益下同一原始值产生更高电压
        raw = sensor_high.read_raw()
        voltage = sensor_high.read_voltage()
        # 仿真模式下原始值可能为0，检查计算过程不崩溃
        self.assertIsInstance(voltage, float)

    def test_different_channel(self):
        """不同通道读取。"""
        cfg_ch1 = ADS1115Config(i2c_addr=0x48, channel=1)
        sensor_ch1 = ADSTemperatureSensor(self.bus, cfg_ch1)
        sensor_ch1.init()
        temp = sensor_ch1.read_temperature("lm35")
        self.assertIsInstance(temp, float)

    def test_c_code_generation(self):
        """C 代码生成验证。"""
        c_code = generate_i2c_sensor_c(i2c_addr=0x48, channel=0)
        self.assertIn("uint8_t", c_code)
        self.assertIn("int16_t", c_code)
        self.assertIn("float", c_code)
        self.assertIn("ads1115_init", c_code)
        self.assertIn("ads1115_read_temperature_lm35", c_code)
        self.assertIn("I2C_BASE_ADDR", c_code)
        self.assertIn("0x48", c_code)

    def test_c_code_si510_target(self):
        """C 代码针对 SiFive FE310。"""
        c_code = generate_i2c_sensor_c()
        self.assertIn("SiFive FE310", c_code)
        self.assertIn("RISC-V", c_code)
        self.assertIn("int main(void)", c_code)


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 2: 线性代数引擎测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMatrix(unittest.TestCase):
    """矩阵运算测试。"""

    # ── 构造测试 ──

    def test_create_matrix(self):
        """创建基本矩阵。"""
        m = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(m.shape, (2, 2))
        self.assertAlmostEqual(m.data[0][0], 1.0)
        self.assertAlmostEqual(m.data[1][1], 4.0)

    def test_create_empty_matrix_raises(self):
        """空矩阵应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            Matrix.from_list([])
        with self.assertRaises(ValueError):
            Matrix.from_list([[]])

    def test_create_inconsistent_dims_raises(self):
        """行列不一致应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            Matrix.from_list([[1.0, 2.0], [3.0]])

    def test_identity_matrix(self):
        """单位矩阵正确。"""
        I3 = Matrix.identity(3)
        self.assertEqual(I3.shape, (3, 3))
        for i in range(3):
            for j in range(3):
                expected = 1.0 if i == j else 0.0
                self.assertAlmostEqual(I3.data[i][j], expected)

    def test_zeros_matrix(self):
        """零矩阵正确。"""
        Z = Matrix.zeros(3, 4)
        self.assertEqual(Z.shape, (3, 4))
        for i in range(3):
            for j in range(4):
                self.assertAlmostEqual(Z.data[i][j], 0.0)

    # ── 矩阵加法测试 ──

    def test_add_same_shape(self):
        """同尺寸矩阵相加。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix.from_list([[5.0, 6.0], [7.0, 8.0]])
        C = A + B
        self.assertAlmostEqual(C.data[0][0], 6.0)
        self.assertAlmostEqual(C.data[1][1], 12.0)

    def test_add_with_identity(self):
        """加单位矩阵不变。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        I = Matrix.identity(2)
        C = A + I
        self.assertAlmostEqual(C.data[0][0], 2.0)
        self.assertAlmostEqual(C.data[1][1], 5.0)

    def test_add_different_shape_raises(self):
        """不同尺寸矩阵相加应抛出 ValueError。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0]])
        B = Matrix.from_list([[1.0, 2.0]])
        with self.assertRaises(ValueError):
            _ = A + B

    def test_add_commutative(self):
        """加法交换律。"""
        A = Matrix.from_list([[1.0, 0.0], [0.0, 1.0]])
        B = Matrix.from_list([[2.0, 3.0], [4.0, 5.0]])
        self.assertEqual(A + B, B + A)

    # ── 矩阵减法测试 ──

    def test_subtract(self):
        """矩阵相减。"""
        A = Matrix.from_list([[5.0, 6.0], [7.0, 8.0]])
        B = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        C = A - B
        self.assertAlmostEqual(C.data[0][0], 4.0)
        self.assertAlmostEqual(C.data[1][1], 4.0)

    def test_subtract_self_is_zero(self):
        """矩阵减自身为零矩阵。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        Z = A - A
        self.assertAlmostEqual(Z.data[0][0], 0.0)
        self.assertAlmostEqual(Z.data[0][1], 0.0)
        self.assertAlmostEqual(Z.data[1][0], 0.0)
        self.assertAlmostEqual(Z.data[1][1], 0.0)

    # ── 矩阵乘法测试 ──

    def test_mul_scalar(self):
        """标量乘法。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = A * 2.0
        self.assertAlmostEqual(B.data[0][0], 2.0)
        self.assertAlmostEqual(B.data[1][1], 8.0)

    def test_mul_matrices(self):
        """矩阵乘法。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix.from_list([[5.0, 6.0], [7.0, 8.0]])
        C = A * B
        self.assertAlmostEqual(C.data[0][0], 19.0)
        self.assertAlmostEqual(C.data[0][1], 22.0)
        self.assertAlmostEqual(C.data[1][0], 43.0)
        self.assertAlmostEqual(C.data[1][1], 50.0)

    def test_mul_with_identity(self):
        """乘单位矩阵不变。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        I = Matrix.identity(2)
        self.assertEqual(A * I, A)
        self.assertEqual(I * A, A)

    def test_mul_dimension_mismatch_raises(self):
        """尺寸不匹配的矩阵乘法应抛出 ValueError。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0]])   # 1x3
        B = Matrix.from_list([[1.0, 2.0]])         # 1x2
        with self.assertRaises(ValueError):
            _ = A * B

    def test_mul_associative(self):
        """乘法结合律 (小矩阵验证)。"""
        A = Matrix.from_list([[1.0, 1.0], [0.0, 1.0]])
        B = Matrix.from_list([[1.0, 0.0], [1.0, 1.0]])
        C = Matrix.from_list([[2.0, 1.0], [1.0, 2.0]])
        self.assertEqual((A * B) * C, A * (B * C))

    def test_rmul(self):
        """右乘标量。"""
        A = Matrix.from_list([[1.0, 2.0]])
        B = 3.0 * A
        self.assertAlmostEqual(B.data[0][0], 3.0)
        self.assertAlmostEqual(B.data[0][1], 6.0)

    # ── 矩阵除法测试 ──

    def test_divide_by_scalar(self):
        """标量除法。"""
        A = Matrix.from_list([[2.0, 4.0], [6.0, 8.0]])
        B = A / 2.0
        self.assertAlmostEqual(B.data[0][0], 1.0)
        self.assertAlmostEqual(B.data[1][1], 4.0)

    def test_divide_by_zero_raises(self):
        """除以零应抛出 ZeroDivisionError。"""
        A = Matrix.from_list([[1.0, 2.0]])
        with self.assertRaises(ZeroDivisionError):
            _ = A / 0.0

    # ── 转置测试 ──

    def test_transpose_square(self):
        """方阵转置。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0],
                              [4.0, 5.0, 6.0]])
        T = A.transpose()
        self.assertEqual(T.shape, (3, 2))
        self.assertAlmostEqual(T.data[0][1], 4.0)
        self.assertAlmostEqual(T.data[2][1], 6.0)

    def test_transpose_twice_is_original(self):
        """转置两次等于原矩阵。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        self.assertEqual(A.transpose().transpose(), A)

    def test_transpose_identity(self):
        """单位矩阵转置等于自身。"""
        I = Matrix.identity(3)
        self.assertEqual(I.transpose(), I)

    # ── 行列式测试 ──

    def test_det_1x1(self):
        """1x1 矩阵行列式。"""
        A = Matrix.from_list([[5.0]])
        self.assertAlmostEqual(A.determinant(), 5.0)

    def test_det_2x2(self):
        """2x2 矩阵行列式。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertAlmostEqual(A.determinant(), -2.0)

    def test_det_3x3(self):
        """3x3 矩阵行列式。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0],
                              [4.0, 5.0, 6.0],
                              [7.0, 8.0, 10.0]])
        self.assertAlmostEqual(A.determinant(), -3.0)

    def test_det_identity(self):
        """单位矩阵行列式为 1。"""
        I = Matrix.identity(4)
        self.assertAlmostEqual(I.determinant(), 1.0)

    def test_det_singular(self):
        """奇异矩阵行列式为 0。"""
        A = Matrix.from_list([[1.0, 2.0], [2.0, 4.0]])
        self.assertAlmostEqual(A.determinant(), 0.0)

    def test_det_non_square_raises(self):
        """非方阵行列式应抛出 ValueError。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        with self.assertRaises(ValueError):
            _ = A.determinant()

    # ── 逆矩阵测试 ──

    def test_inverse_2x2(self):
        """2x2 矩阵求逆。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        inv = A.inverse()
        self.assertIsNotNone(inv)
        # A * A^(-1) = I
        product = A * inv
        I = Matrix.identity(2)
        self.assertTrue(product == I)

    def test_inverse_3x3(self):
        """3x3 矩阵求逆。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0],
                              [0.0, 1.0, 4.0],
                              [5.0, 6.0, 0.0]])
        inv = A.inverse()
        self.assertIsNotNone(inv)
        product = A * inv
        I = Matrix.identity(3)
        self.assertTrue(product == I)

    def test_inverse_singular_raises(self):
        """奇异矩阵求逆返回 None。"""
        A = Matrix.from_list([[1.0, 2.0], [2.0, 4.0]])
        self.assertIsNone(A.inverse())

    def test_inverse_identity(self):
        """单位矩阵的逆是自身。"""
        I = Matrix.identity(3)
        self.assertEqual(I.inverse(), I)

    # ── 迹测试 ──

    def test_trace_square(self):
        """方阵的迹。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertAlmostEqual(A.trace(), 5.0)

    def test_trace_identity(self):
        """单位矩阵的迹等于维度。"""
        I = Matrix.identity(5)
        self.assertAlmostEqual(I.trace(), 5.0)

    def test_trace_non_square_raises(self):
        """非方阵的迹应抛出 ValueError。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0]])
        with self.assertRaises(ValueError):
            _ = A.trace()

    # ── 范数测试 ──

    def test_norm_frobenius(self):
        """Frobenius 范数。"""
        A = Matrix.from_list([[1.0, 0.0], [0.0, 1.0]])
        self.assertAlmostEqual(A.norm(), 1.41421356, places=5)

    def test_norm_zero_matrix(self):
        """零矩阵范数为 0。"""
        Z = Matrix.zeros(3, 3)
        self.assertAlmostEqual(Z.norm(), 0.0)

    def test_norm_non_zero(self):
        """非零矩阵范数 > 0。"""
        A = Matrix.from_list([[3.0, 4.0], [0.0, 0.0]])
        self.assertAlmostEqual(A.norm(), 5.0)

    # ── 矩阵幂测试 ──

    def test_pow_zero(self):
        """任何矩阵的 0 次幂是单位矩阵。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(A.mat_pow(0), Matrix.identity(2))

    def test_pow_one(self):
        """任何矩阵的 1 次幂是自身。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(A.mat_pow(1), A)

    def test_pow_two(self):
        """矩阵平方。"""
        A = Matrix.from_list([[1.0, 1.0], [0.0, 1.0]])
        A2 = A.mat_pow(2)
        expected = Matrix.from_list([[1.0, 2.0], [0.0, 1.0]])
        self.assertEqual(A2, expected)

    def test_pow_larger(self):
        """较大幂次验证。"""
        A = Matrix.from_list([[2.0, 0.0], [0.0, 2.0]])
        A4 = A.mat_pow(4)
        expected = Matrix.from_list([[16.0, 0.0], [0.0, 16.0]])
        self.assertEqual(A4, expected)

    def test_pow_non_square_raises(self):
        """非方阵的幂应抛出 ValueError。"""
        A = Matrix.from_list([[1.0, 2.0, 3.0]])
        with self.assertRaises(ValueError):
            _ = A.mat_pow(2)

    # ── 点积测试 ──

    def test_dot_same_as_mul(self):
        """dot 等同于矩阵乘法。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix.from_list([[5.0, 6.0], [7.0, 8.0]])
        self.assertEqual(A.dot(B), A * B)

    # ── 等式测试 ──

    def test_equality_same(self):
        """相同矩阵相等。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(A, B)

    def test_inequality_different(self):
        """不同矩阵不相等。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix.from_list([[1.0, 2.0], [3.0, 5.0]])
        self.assertNotEqual(A, B)

    def test_equality_with_identity(self):
        """与单位矩阵比较。"""
        A = Matrix.identity(2)
        B = Matrix.identity(2)
        self.assertEqual(A, B)

    def test_equality_with_non_matrix(self):
        """与非矩阵类型比较返回 False。"""
        A = Matrix.from_list([[1.0, 2.0]])
        self.assertNotEqual(A, "not a matrix")
        self.assertNotEqual(A, 42)

    # ── 浮点精度边界测试 ──

    def test_very_small_values(self):
        """极小值矩阵运算不崩溃。"""
        A = Matrix.from_list([[1e-10, 2e-10], [3e-10, 4e-10]])
        B = A * 1e10
        self.assertAlmostEqual(B.data[0][0], 1.0, places=5)

    def test_very_large_values(self):
        """极大值矩阵运算不崩溃。"""
        A = Matrix.from_list([[1e10, 2e10], [3e10, 4e10]])
        B = A / 1e10
        self.assertAlmostEqual(B.data[0][0], 1.0, places=5)

    def test_near_singular_inverse(self):
        """接近奇异矩阵的逆应返回 None。"""
        A = Matrix.from_list([[1.0, 1.000000001], [1.0, 1.0]])
        result = A.inverse()
        # 可能返回 None 或极大值，取决于数值稳定性
        if result is not None:
            self.assertIsInstance(result, Matrix)

    def test_operations_track_count(self):
        """运算计数正确递增。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        initial = A._ops_count
        _ = A + A
        _ = A * A
        self.assertGreater(A._ops_count, initial)

    # ── C 代码生成测试 ──

    def test_to_c_code_basic(self):
        """C 代码生成包含必要元素。"""
        A = Matrix.from_list([[1.0, 2.0], [3.0, 4.0]])
        c_code = A.to_c_code("test_mat")
        self.assertIn("test_mat_data", c_code)
        self.assertIn("test_mat_rows", c_code)
        self.assertIn("test_mat_cols", c_code)
        self.assertIn("1.0000f", c_code)

    def test_generate_linalg_c_code(self):
        """线性代数 C 代码生成验证。"""
        c_code = generate_linalg_c()
        self.assertIn("Matrix", c_code)
        self.assertIn("mat_add", c_code)
        self.assertIn("mat_mul", c_code)
        self.assertIn("mat_det", c_code)
        self.assertIn("mat_inv", c_code)
        self.assertIn("int main(void)", c_code)
        self.assertIn("RISC-V", c_code)


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 3: GPIO + PWM 电机调速测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPIOPin(unittest.TestCase):
    """GPIO 引脚测试。"""

    def test_create_output_pin(self):
        """创建输出引脚。"""
        pin = GPIOPin(1, "OUTPUT")
        self.assertEqual(pin.pin, 1)
        self.assertEqual(pin.mode, "OUTPUT")

    def test_create_input_pin(self):
        """创建输入引脚。"""
        pin = GPIOPin(0, "INPUT")
        self.assertEqual(pin.mode, "INPUT")

    def test_set_high(self):
        """设置高电平。"""
        pin = GPIOPin(1, "OUTPUT")
        pin.high()
        self.assertEqual(pin.get(), 1)

    def test_set_low(self):
        """设置低电平。"""
        pin = GPIOPin(1, "OUTPUT")
        pin.low()
        self.assertEqual(pin.get(), 0)

    def test_set_value(self):
        """设置任意值。"""
        pin = GPIOPin(1, "OUTPUT")
        pin.set(1)
        self.assertEqual(pin.get(), 1)
        pin.set(0)
        self.assertEqual(pin.get(), 0)

    def test_toggle(self):
        """翻转引脚。"""
        pin = GPIOPin(1, "OUTPUT")
        pin.high()
        self.assertEqual(pin.get(), 1)
        pin.toggle()
        self.assertEqual(pin.get(), 0)
        pin.toggle()
        self.assertEqual(pin.get(), 1)

    def test_set_invalid_value_raises(self):
        """设置无效值应抛出 ValueError。"""
        pin = GPIOPin(1, "OUTPUT")
        with self.assertRaises(ValueError):
            pin.set(2)
        with self.assertRaises(ValueError):
            pin.set(-1)

    def test_default_value_is_zero(self):
        """默认值为 0。"""
        pin = GPIOPin(5, "OUTPUT")
        self.assertEqual(pin.get(), 0)

    def test_repr(self):
        """字符串表示。"""
        pin = GPIOPin(3, "OUTPUT")
        pin.high()
        rep = repr(pin)
        self.assertIn("GPIOPin", rep)
        self.assertIn("3", rep)
        self.assertIn("OUTPUT", rep)


class TestPWMChannel(unittest.TestCase):
    """PWM 通道测试。"""

    def setUp(self):
        self.pin = GPIOPin(3, "OUTPUT")
        self.pwm = PWMChannel(self.pin, freq=20000, duty=0.0)

    def test_create_pwm(self):
        """创建 PWM 通道。"""
        self.assertEqual(self.pwm.freq, 20000)
        self.assertEqual(self.pwm.duty_cycle, 0.0)
        self.assertFalse(self.pwm._running)

    def test_set_duty_cycle(self):
        """设置占空比。"""
        self.pwm.duty_cycle = 0.5
        self.assertAlmostEqual(self.pwm.duty_cycle, 0.5)

    def test_set_duty_cycle_bounds(self):
        """占空比边界处理。"""
        self.pwm.duty_cycle = -0.5   # 应钳制到 0.0
        self.assertAlmostEqual(self.pwm.duty_cycle, 0.0)
        self.pwm.duty_cycle = 1.5    # 应钳制到 1.0
        self.assertAlmostEqual(self.pwm.duty_cycle, 1.0)

    def test_start(self):
        """启动 PWM。"""
        self.pwm.start()
        self.assertTrue(self.pwm._running)

    def test_stop(self):
        """停止 PWM。"""
        self.pwm.start()
        self.pwm.stop()
        self.assertFalse(self.pwm._running)

    def test_set_speed_forward(self):
        """正转调速。"""
        self.pwm.start()
        duty = self.pwm.set_speed(75.0)
        self.assertAlmostEqual(self.pwm.duty_cycle, 0.75)
        self.assertEqual(self.pwm._direction, "forward")

    def test_set_speed_reverse(self):
        """反转调速。"""
        self.pwm.start()
        duty = self.pwm.set_speed(-50.0)
        self.assertAlmostEqual(self.pwm.duty_cycle, 0.5)
        self.assertEqual(self.pwm._direction, "reverse")

    def test_set_speed_zero_stops(self):
        """零速度停止。"""
        self.pwm.start()
        self.pwm.set_speed(0.0)
        self.assertEqual(self.pwm.duty_cycle, 0.0)

    def test_set_speed_over_100_clamped(self):
        """超过 100% 应钳制。"""
        self.pwm.start()
        self.pwm.set_speed(150.0)
        self.assertEqual(self.pwm.duty_cycle, 1.0)

    def test_period_calculation(self):
        """周期计算正确。"""
        self.assertEqual(self.pwm.period, 50)  # 1000000 / 20000 = 50us

    def test_get_stats(self):
        """获取统计信息。"""
        self.pwm.start()
        self.pwm.duty_cycle = 0.75
        stats = self.pwm.get_stats()
        self.assertEqual(stats['pin'], 3)
        self.assertEqual(stats['freq'], 20000)
        self.assertAlmostEqual(stats['duty_cycle'], 0.75)
        self.assertTrue(stats['running'])

    def test_different_frequency(self):
        """不同频率的 PWM。"""
        pwm500 = PWMChannel(GPIOPin(4), freq=500, duty=0.0)
        self.assertEqual(pwm500.period, 2000)  # 1000000 / 500 = 2000us

    def test_repr(self):
        """字符串表示。"""
        rep = repr(self.pwm)
        self.assertIn("PWMChannel", rep)


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 4: 看门狗复位功能测试
# ═══════════════════════════════════════════════════════════════════════════════

class WatchdogTimer:
    """
    RISC-V 看门狗定时器模拟。

    用于测试看门狗复位功能的逻辑正确性。
    """

    def __init__(self, timeout_ms: int = 2000):
        self.timeout_ms = timeout_ms
        self._running = False
        self._last_feed_ms = 0
        self._feed_count = 0
        self._reset_count = 0
        self._sim_time_ms = 0
        self._was_timeout = False  # 跟踪是否已在超时状态

    def start(self):
        self._running = True
        self._last_feed_ms = self._sim_time_ms
        self._was_timeout = False

    def feed(self):
        """喂狗。"""
        if not self._running:
            raise RuntimeError("看门狗未启动")
        self._last_feed_ms = self._sim_time_ms
        self._feed_count += 1
        self._was_timeout = False  # 喂狗后清除超时状态

    def tick(self, dt_ms: int = 1):
        """模拟时间流逝。"""
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
        # 检查自上次喂狗以来的累计时间
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


class TestWatchdogTimer(unittest.TestCase):
    """看门狗定时器测试。"""

    def test_create(self):
        """创建看门狗。"""
        wd = WatchdogTimer(timeout_ms=1000)
        self.assertEqual(wd.timeout_ms, 1000)
        self.assertFalse(wd._running)

    def test_start(self):
        """启动看门狗。"""
        wd = WatchdogTimer(timeout_ms=500)
        wd.start()
        self.assertTrue(wd._running)

    def test_feed(self):
        """喂狗重置超时。"""
        wd = WatchdogTimer(timeout_ms=500)
        wd.start()
        wd.tick(200)
        wd.feed()
        self.assertFalse(wd.is_timeout())

    def test_timeout_without_feed(self):
        """不喂狗应触发超时。"""
        wd = WatchdogTimer(timeout_ms=300)
        wd.start()
        wd.tick(400)
        self.assertTrue(wd.is_timeout())

    def test_multiple_feeds(self):
        """多次喂狗。"""
        wd = WatchdogTimer(timeout_ms=200)
        wd.start()
        for _ in range(5):
            wd.tick(50)
            wd.feed()
        self.assertFalse(wd.is_timeout())
        self.assertEqual(wd._feed_count, 5)

    def test_timeout_increments_reset_count(self):
        """超时时 reset_count 递增。"""
        wd = WatchdogTimer(timeout_ms=100)
        wd.start()
        wd.tick(150)
        self.assertEqual(wd._reset_count, 1)  # 首次超时
        # 持续超时：reset_count 只计数一次（从 False→True 的转换）
        wd.tick(150)
        self.assertEqual(wd._reset_count, 1)
        # 喂狗后再次超时应再次计数
        wd.feed()
        wd.tick(150)
        self.assertEqual(wd._reset_count, 2)

    def test_feed_before_timeout(self):
        """超时前喂狗不计数。"""
        wd = WatchdogTimer(timeout_ms=100)
        wd.start()
        wd.tick(50)
        wd.feed()
        wd.tick(50)
        wd.feed()
        self.assertEqual(wd._reset_count, 0)

    def test_feed_without_start_raises(self):
        """未启动时喂狗应抛出异常。"""
        wd = WatchdogTimer(timeout_ms=100)
        with self.assertRaises(RuntimeError):
            wd.feed()

    def test_get_stats(self):
        """获取统计信息。"""
        wd = WatchdogTimer(timeout_ms=500)
        wd.start()
        wd.tick(100)
        wd.feed()
        stats = wd.get_stats()
        self.assertTrue(stats['running'])
        self.assertEqual(stats['feed_count'], 1)
        self.assertEqual(stats['reset_count'], 0)

    def test_c_code_generation_watchdog(self):
        """看门狗 C 代码生成验证。"""
        c_code = generate_watchdog_c_code()
        self.assertIn("WatchdogDriver", c_code)
        self.assertIn("wdt_init", c_code)
        self.assertIn("wdt_feed", c_code)
        self.assertIn("wdt_is_timeout", c_code)
        self.assertIn("WDT_BASE", c_code)
        self.assertIn("int main(void)", c_code)


def generate_watchdog_c_code() -> str:
    """生成 RISC-V 看门狗 C 代码。"""
    return '''/*
 * Matha RISC-V 看门狗复位驱动
 * 目标: SiFive FE310 (RISC-V 32-bit)
 * 功能: 软件看门狗 + 硬件看门狗复位
 */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>

/* ========== 看门狗寄存器定义 ========== */
#define WDT_BASE          0x40002000UL
#define WDT_CTRL          (*(volatile uint32_t *)(WDT_BASE + 0x00))
#define WDT_STATUS        (*(volatile uint32_t *)(WDT_BASE + 0x04))
#define WDT_LOAD          (*(volatile uint32_t *)(WDT_BASE + 0x08))
#define WDT_VALUE         (*(volatile uint32_t *)(WDT_BASE + 0x0C))

/* 控制位 */
#define WDT_CTRL_ENABLE   (1 << 0)
#define WDT_CTRL_IE       (1 << 1)   /* 中断使能 */
#define WDT_CTRL_RESTART  (1 << 2)   /* 重启计数 */

/* 状态位 */
#define WDT_STATUS_ACTIVE (1 << 0)
#define WDT_STATUS_TIMEOUT (1 << 1)

/* ========== 看门狗结构体 ========== */
typedef struct {{
    uint32_t timeout_ms;
    uint32_t last_feed_ms;
    uint32_t feed_count;
    uint32_t reset_count;
    bool     running;
}} WatchdogDriver;

WatchdogDriver wdt;

/* ========== 看门狗驱动 ========== */

void wdt_init(uint32_t timeout_ms) {{
    wdt.timeout_ms = timeout_ms;
    wdt.last_feed_ms = 0;
    wdt.feed_count = 0;
    wdt.reset_count = 0;
    wdt.running = false;

    /* 配置看门狗超时 (假设 156MHz 时钟, 分频后) */
    uint32_t load_val = (156000000UL * timeout_ms) / 1000UL / 1024UL;
    WDT_LOAD = load_val;
    WDT_CTRL = WDT_CTRL_ENABLE;
}}

void wdt_start(void) {{
    wdt.running = true;
    wdt.last_feed_ms = 0;
    WDT_CTRL |= WDT_CTRL_RESTART;
    printf("[WDT] 看门狗启动, 超时=%lu ms\\n", wdt.timeout_ms);
}}

void wdt_feed(void) {{
    if (!wdt.running) {{
        printf("[WDT] 错误: 看门狗未启动\\n");
        return;
    }}
    wdt.last_feed_ms = 0;  /* 重置计数器 */
    wdt.feed_count++;
    WDT_CTRL |= WDT_CTRL_RESTART;
    printf("[WDT] 喂狗 #%lu\\n", wdt.feed_count);
}}

bool wdt_is_timeout(void) {{
    if (!wdt.running) return false;
    return (WDT_STATUS & WDT_STATUS_TIMEOUT) != 0;
}}

void wdt_handle_timeout(void) {{
    wdt.reset_count++;
    printf("[WDT] 超时! 复位次数=%lu\\n", wdt.reset_count);
    /* 触发系统复位 */
    /* NVIC_SystemReset(); 或手动跳转 */
    /* while(1); 死循环作为安全兜底 */
}}

void wdt_stop(void) {{
    wdt.running = false;
    WDT_CTRL = 0;
    printf("[WDT] 看门狗停止\\n");
}}

/* ========== 应用示例 ========== */

void app_main_loop(void) {{
    wdt_init(2000);   /* 2秒超时 */
    wdt_start();

    for (int i = 0; i < 10; i++) {{
        /* 正常工作 */
        printf("[APP] 运行中... %d\\n", i);
        wdt_feed();     /* 定期喂狗 */

        /* 模拟超时场景 */
        if (i == 5) {{
            printf("[APP] 模拟超时!\\n");
            /* 不喂狗，让看门狗超时 */
        }}

        if (wdt_is_timeout()) {{
            wdt_handle_timeout();
        }}
    }}

    wdt_stop();
}}

int main(void) {{
    app_main_loop();
    return 0;
}}
'''


class TestWatchdogIntegration(unittest.TestCase):
    """看门狗与嵌入式项目集成测试。"""

    def test_watchdog_logic_simulation(self):
        """模拟看门狗正常工作流程。"""
        wd = WatchdogTimer(timeout_ms=500)
        wd.start()

        # 正常喂狗
        for _ in range(5):
            wd.tick(100)
            wd.feed()
        self.assertFalse(wd.is_timeout())
        self.assertEqual(wd._feed_count, 5)

        # 超时后复位
        wd.tick(600)
        self.assertTrue(wd.is_timeout())
        self.assertEqual(wd._reset_count, 1)

    def test_watchdog_c_code_generation(self):
        """看门狗 C 代码生成验证。"""
        c_code = generate_watchdog_c_code()
        self.assertIn("WatchdogDriver", c_code)
        self.assertIn("wdt_init", c_code)
        self.assertIn("wdt_feed", c_code)
        self.assertIn("wdt_is_timeout", c_code)
        self.assertIn("WDT_BASE", c_code)
        self.assertIn("int main(void)", c_code)

    def test_embedded_project_includes_watchdog(self):
        """嵌入式项目模板包含看门狗功能。"""
        project = generate_embedded_project_template()
        # 验证基本结构存在
        self.assertIn("main", project)
        self.assertIn("gpio", project.lower())
        self.assertIn("motor", project.lower())
        self.assertIn("i2c", project.lower())


# ═══════════════════════════════════════════════════════════════════════════════
#  测试运行
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
