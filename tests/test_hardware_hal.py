# -*- coding: utf-8 -*-
"""Matha v4.0 — 硬件抽象层（HAL）单元测试"""
import sys
import unittest

sys.path.insert(0, r"D:\trae")

from src.hardware.hal import (
    HardwareAbstractionLayer,
    MathaHardwareOps,
    IODevice,
    DeviceConfig,
    DeviceType,
    DeviceState,
    ScreenDevice,
    KeyboardDevice,
    FileDevice,
    NetworkDevice,
    SerialDevice,
    GPIODevice,
    I2CDevice,
)


class TestIODeviceBase(unittest.TestCase):
    """IODevice 基类测试。"""

    def test_device_lifecycle(self):
        """测试设备生命周期。"""
        config = DeviceConfig(
            name="test_device",
            device_type=DeviceType.SENSOR,
            address="test_addr",
        )
        device = IODevice(config)

        # 初始状态应为 OFFLINE
        self.assertEqual(device.state, DeviceState.OFFLINE)

        # 上线
        self.assertTrue(device.online())
        self.assertEqual(device.state, DeviceState.ONLINE)

        # 下线
        self.assertTrue(device.offline())
        self.assertEqual(device.state, DeviceState.OFFLINE)

        # 重置
        self.assertTrue(device.reset())
        self.assertEqual(device.state, DeviceState.OFFLINE)
        self.assertEqual(device.access_count, 0)

    def test_read_while_offline(self):
        """测试下线时读取返回 None。"""
        config = DeviceConfig(
            name="test",
            device_type=DeviceType.SENSOR,
        )
        device = IODevice(config)
        result = device.read()
        self.assertIsNone(result)

    def test_write_while_offline(self):
        """测试下线时写入返回 False。"""
        config = DeviceConfig(
            name="test",
            device_type=DeviceType.ACTUATOR,
        )
        device = IODevice(config)
        result = device.write("data")
        self.assertFalse(result)


class TestScreenDevice(unittest.TestCase):
    """屏幕设备测试。"""

    def test_write_to_screen(self):
        """测试屏幕写入。"""
        device = ScreenDevice()
        device.online()

        # 写入应该不会抛出异常
        result = device.write("Hello Matha")
        self.assertTrue(result)

    def test_access_count(self):
        """测试访问计数。"""
        device = ScreenDevice()
        device.online()
        device.write("test1")
        device.write("test2")
        self.assertEqual(device.access_count, 2)


class TestFileDevice(unittest.TestCase):
    """文件设备测试。"""

    def setUp(self):
        self.device = FileDevice()
        self.test_file = ".matha_hal_test.txt"

    def tearDown(self):
        import os
        if os.path.exists(self.test_file):
            os.unlink(self.test_file)

    def test_write_and_read(self):
        """测试文件读写。"""
        self.device.online()

        # 写入
        success = self.device.write("Matha HAL Test", path=self.test_file)
        self.assertTrue(success)

        # 读取
        content = self.device.read(path=self.test_file)
        self.assertEqual(content, "Matha HAL Test")

    def test_read_nonexistent(self):
        """测试读取不存在的文件。"""
        content = self.device.read(path=".nonexistent_file")
        self.assertIsNone(content)


class TestSerialDevice(unittest.TestCase):
    """串口设备测试。"""

    def test_create_serial_device(self):
        """测试创建串口设备。"""
        device = SerialDevice(port="/dev/ttySIM", baudrate=9600)
        self.assertEqual(device.address, "/dev/ttySIM")
        self.assertEqual(device.config.config["baudrate"], 9600)

    def test_serial_lifecycle(self):
        """测试串口设备生命周期。"""
        device = SerialDevice(port="/dev/ttySIM")
        self.assertEqual(device.state, DeviceState.OFFLINE)

        device.online()
        self.assertEqual(device.state, DeviceState.ONLINE)

        device.offline()
        self.assertEqual(device.state, DeviceState.OFFLINE)


class TestGPIODevice(unittest.TestCase):
    """GPIO 设备测试。"""

    def test_create_gpio(self):
        """测试创建 GPIO 设备。"""
        device = GPIODevice(pin=4)
        self.assertEqual(device.address, "GPIO4")

    def test_gpio_write_read(self):
        """测试 GPIO 读写。"""
        device = GPIODevice(pin=18)
        device.online()

        device.write(True)
        self.assertTrue(device.write(True))

        # 读取应返回布尔值
        value = device.read()
        self.assertIsInstance(value, bool)


class TestHardwareAbstractionLayer(unittest.TestCase):
    """HAL 测试。"""

    def setUp(self):
        self.hal = HardwareAbstractionLayer()
        self.ops = MathaHardwareOps(self.hal)

    def test_list_devices(self):
        """测试列出设备。"""
        devices = self.ops.列出设备()
        self.assertGreaterEqual(len(devices), 3)  # screen, keyboard, file

        # 验证设备结构
        for dev in devices:
            self.assertIn("name", dev)
            self.assertIn("type", dev)
            self.assertIn("address", dev)
            self.assertIn("state", dev)

    def test_read_write_screen(self):
        """测试屏幕读写。"""
        # 写入
        result = self.ops.写入("screen", "Hello HAL")
        self.assertTrue(result)

    def test_read_write_file(self):
        """测试文件读写。"""
        test_file = ".matha_hal_test.txt"

        # 写入
        result = self.ops.写入("file", "HAL Test", path=test_file)
        self.assertTrue(result)

        # 读取
        content = self.ops.读取("file", path=test_file)
        self.assertEqual(content, "HAL Test")

        # 清理
        import os
        if os.path.exists(test_file):
            os.unlink(test_file)

    def test_register_unregister(self):
        """测试设备注册/注销。"""
        gpio = GPIODevice(pin=21)
        self.hal.register(gpio)

        # 验证已注册
        dev = self.hal.get("gpio_21")
        self.assertIsNotNone(dev)
        self.assertEqual(dev.name, "gpio_21")

        # 注销
        self.hal.unregister("gpio_21")
        dev = self.hal.get("gpio_21")
        self.assertIsNone(dev)

    def test_get_by_address(self):
        """测试按地址获取设备。"""
        serial = SerialDevice(port="/dev/ttyUSB0")
        self.hal.register(serial)

        dev = self.hal.get_by_address("/dev/ttyUSB0")
        self.assertIsNotNone(dev)
        self.assertEqual(dev.name, "serial_/dev/ttyUSB0")

        self.hal.unregister("serial_/dev/ttyUSB0")


class TestHALIntegration(unittest.TestCase):
    """HAL 集成测试。"""

    def test_full_io_workflow(self):
        """测试完整 I/O 工作流。"""
        hal = HardwareAbstractionLayer()
        ops = MathaHardwareOps(hal)

        # 1. 列出设备
        devices = ops.列出设备()
        self.assertGreater(len(devices), 0)

        # 2. 屏幕输出
        ops.写入("screen", "Matha HAL 测试开始")

        # 3. 文件读写
        test_content = "Matha v4.0 HAL 测试"
        ops.写入("file", test_content, path=".matha_integration_test.txt")
        read_back = ops.读取("file", path=".matha_integration_test.txt")
        self.assertEqual(read_back, test_content)

        # 4. 清理
        import os
        if os.path.exists(".matha_integration_test.txt"):
            os.unlink(".matha_integration_test.txt")

        ops.写入("screen", "Matha HAL 测试完成")


if __name__ == "__main__":
    unittest.main(verbosity=2)
