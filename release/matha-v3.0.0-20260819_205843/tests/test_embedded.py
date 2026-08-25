# -*- coding: utf-8 -*-
"""嵌入式系统领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.embedded import (
    _adc_value, _adc_voltage, _pwm_duty_cycle, _pwm_period,
    _thermistor_temperature_celsius, _photocell_light,
    _ultrasonic_distance, _stepper_steps_to_degrees,
    _servo_angle, _servo_pulse,
    _dc_motor_rpm, _battery_voltage,
    _uart_baud_error, _i2c_pullup_resistor,
)


class TestEmbedded(unittest.TestCase):
    # ---- ADC/DAC ----

    def test_adc_value(self):
        val = _adc_value(1.65, ref_voltage=3.3, bits=12)
        self.assertEqual(val, 2047)

    def test_adc_voltage(self):
        vol = _adc_voltage(2047, ref_voltage=3.3, bits=12)
        self.assertAlmostEqual(vol, 1.65, places=2)

    # ---- PWM ----

    def test_pwm_duty_cycle(self):
        self.assertAlmostEqual(_pwm_duty_cycle(5, 10), 50.0)

    def test_pwm_period(self):
        self.assertAlmostEqual(_pwm_period(1000), 0.001)

    # ---- 传感器 ----

    def test_热敏温度(self):
        t = _thermistor_temperature_celsius(10000, R0=10000, T0=298.15, B=3950)
        self.assertAlmostEqual(t, 25.0, places=1)

    def test_超声波距离(self):
        d = _ultrasonic_distance(10000)
        self.assertAlmostEqual(d, 1.715, places=3)

    def test_光照估算(self):
        light = _photocell_light(100000, 10000, 50000)
        self.assertAlmostEqual(light, 44.44, places=2)

    # ---- 电机控制 ----

    def test_步进角度(self):
        deg = _stepper_steps_to_degrees(200, steps_per_rev=200)
        self.assertAlmostEqual(deg, 360.0)

    def test_舵机角度(self):
        angle = _servo_angle(1500, min_pulse=500, max_pulse=2500)
        self.assertAlmostEqual(angle, 90.0)

    def test_舵机脉冲(self):
        pulse = _servo_pulse(90, min_pulse=500, max_pulse=2500)
        self.assertAlmostEqual(pulse, 1500.0)

    def test_直流转速(self):
        rpm = _dc_motor_rpm(12, k_v=1000)
        self.assertEqual(rpm, 12000)

    # ---- 通信 ----

    def test_uart_baud_error(self):
        err = _uart_baud_error(9600, crystal=11059200, divider=16)
        self.assertAlmostEqual(err, 0.0, places=1)

    def test_i2c_pullup(self):
        R = _i2c_pullup_resistor(vcc=3.3, i2c_current=3e-3)
        self.assertAlmostEqual(R, 1100.0)

    # ---- 电源 ----

    def test_battery_voltage(self):
        self.assertAlmostEqual(_battery_voltage(3, "liion"), 11.1)
        self.assertAlmostEqual(_battery_voltage(2, "nimh"), 2.4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
