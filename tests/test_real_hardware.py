# -*- coding: utf-8 -*-
"""真实硬件驱动领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.real_hardware import (
    HardwareDriverRegistry, GPIOHardware, TemperatureSensor,
    DistanceSensor, StepperMotor, ServoMotor, OLEDDisplay,
)


class TestRealHardware(unittest.TestCase):
    def test_gpio_setup_and_write(self):
        gpio = HardwareDriverRegistry.create("gpio")
        gpio.setup(17, "OUT")
        gpio.output(17, 1)
        self.assertEqual(gpio.input(17), 1)
        gpio.cleanup()

    def test_gpio_read_input(self):
        gpio = HardwareDriverRegistry.create("gpio")
        gpio.setup(18, "IN")
        gpio.output(18, 1)
        self.assertEqual(gpio.input(18), 1)
        gpio.cleanup()

    def test_temperature_sensor(self):
        sensor = HardwareDriverRegistry.create("temperature")
        result = sensor.read()
        self.assertIn("temperature", result)
        self.assertIn("humidity", result)
        self.assertIsInstance(result["temperature"], float)

    def test_distance_sensor(self):
        sensor = HardwareDriverRegistry.create("distance")
        d = sensor.read()
        self.assertIsInstance(d, float)
        self.assertGreaterEqual(d, 0.0)
        self.assertLess(d, 5.0)

    def test_stepper_motor(self):
        motor = HardwareDriverRegistry.create("stepper")
        motor.step(200, speed=0.001)
        motor.rotate_degrees(90, speed=0.001)

    def test_servo_motor(self):
        motor = HardwareDriverRegistry.create("servo")
        motor.set_angle(90)
        motor.set_angle(0)
        motor.set_angle(180)

    def test_oled_display(self):
        disp = HardwareDriverRegistry.create("oled")
        disp.clear()
        disp.text(0, 0, "Hello")
        disp.pixel(0, 0, True)

    def test_driver_list(self):
        drivers = HardwareDriverRegistry.list_drivers()
        self.assertIn("gpio", drivers)
        self.assertIn("stepper", drivers)
        self.assertIn("oled", drivers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
