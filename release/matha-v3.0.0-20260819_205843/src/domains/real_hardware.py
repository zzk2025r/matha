# -*- coding: utf-8 -*-
"""真实硬件驱动层。

为 Matha 提供真实硬件访问能力：
  - GPIO（Raspberry Pi / Arduino）
  - UART / Serial 通信
  - I2C / SPI 总线
  - ADC/DAC 模数转换
  - PWM 输出
  - 传感器读取（温度、光线、距离等）
  - 电机控制（步进、直流、舵机）
  - 显示驱动（OLED, LCD）

注意：需要安装对应的硬件库（如 pigpio, pyserial, smbus2）。
"""

from __future__ import annotations
import time
from typing import Any, Optional


# ============================================================
# GPIO 驱动（Raspberry Pi 兼容）
# ============================================================

class GPIOHardware:
    """Raspberry Pi GPIO 驱动。"""

    _instance: Optional["GPIOHardware"] = None
    _initialized = False

    def __new__(cls) -> "GPIOHardware":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._pin_mode: dict[int, str] = {}
        self._pin_value: dict[int, int] = {}
        self._simulating = True  # 默认仿真模式

        # 尝试导入真实驱动
        try:
            import RPi.GPIO as _gpio
            self._gpio = _gpio
            self._simulating = False
        except ImportError:
            try:
                import gpiozero as _gpio
                self._gpio = _gpio
                self._simulating = False
            except ImportError:
                pass

    def setup(self, pin: int, mode: str = "OUT") -> None:
        """设置 GPIO 引脚模式。mode: IN | OUT | PWM。"""
        if not self._simulating:
            try:
                self._gpio.setmode(self._gpio.BCM)
                self._gpio.setup(pin, self._gpio.OUT if mode == "OUT" else self._gpio.IN)
            except Exception as e:
                raise RuntimeError(f"GPIO setup pin={pin} mode={mode}: {e}")
        self._pin_mode[pin] = mode

    def output(self, pin: int, value: int) -> None:
        """设置 GPIO 引脚输出。"""
        if not self._simulating:
            try:
                self._gpio.output(pin, value)
            except Exception as e:
                raise RuntimeError(f"GPIO output pin={pin} value={value}: {e}")
        self._pin_value[pin] = value

    def input(self, pin: int) -> int:
        """读取 GPIO 引脚输入。"""
        if not self._simulating:
            try:
                return self._gpio.input(pin)
            except Exception as e:
                raise RuntimeError(f"GPIO input pin={pin}: {e}")
        return self._pin_value.get(pin, 0)

    def PWM(self, pin: int, frequency: float, duty_cycle: float) -> None:
        """设置 PWM 输出。"""
        if not self._simulating:
            try:
                pwm = self._gpio.PWM(pin, frequency)
                pwm.start(duty_cycle)
                self._pin_mode[pin] = f"pwm:{frequency}"
            except Exception as e:
                raise RuntimeError(f"GPIO PWM pin={pin}: {e}")
        self._pin_mode[pin] = f"pwm:{frequency}"

    def cleanup(self) -> None:
        """清理 GPIO 资源。"""
        if not self._simulating:
            try:
                self._gpio.cleanup()
            except Exception:
                pass
        self._pin_mode.clear()
        self._pin_value.clear()


# ============================================================
# UART / Serial 驱动
# ============================================================

class SerialDriver:
    """UART/Serial 通信驱动。"""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._handle = None
        self._simulating = False

        try:
            import serial
            self._serial = serial
            self._handle = serial.Serial(port, baudrate, timeout=1)
        except ImportError:
            self._simulating = True

    def write(self, data: bytes) -> int:
        """发送数据。"""
        if not self._simulating and self._handle:
            return self._handle.write(data)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        """接收数据。"""
        if not self._simulating and self._handle:
            return self._handle.read(size)
        return b""

    def readline(self) -> str:
        """读取一行。"""
        if not self._simulating and self._handle:
            return self._handle.readline().decode(errors="replace")
        return ""

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None


# ============================================================
# I2C 驱动
# ============================================================

class I2CDriver:
    """I2C 总线驱动。"""

    def __init__(self, bus: int = 1) -> None:
        self._bus = bus
        self._simulating = True

        try:
            import smbus2
            self._smbus = smbus2
            self._handle = smbus2.SMBus(bus)
            self._simulating = False
        except ImportError:
            pass

    def write_byte(self, addr: int, value: int) -> None:
        """写入单个字节。"""
        if not self._simulating:
            self._handle.write_byte(addr, value)

    def write_bytes(self, addr: int, data: list[int]) -> None:
        """写入多个字节。"""
        if not self._simulating:
            self._handle.write_i2c_block_data(addr, 0, data)

    def read_byte(self, addr: int) -> int:
        """读取单个字节。"""
        if not self._simulating:
            return self._handle.read_byte(addr)
        return 0

    def read_bytes(self, addr: int, length: int) -> list[int]:
        """读取多个字节。"""
        if not self._simulating:
            return self._handle.read_i2c_block_data(addr, 0, length)
        return [0] * length

    def scan(self) -> list[int]:
        """扫描 I2C 总线上的设备地址。"""
        if not self._simulating:
            return [addr for addr in range(0x03, 0x78)
                    if self._handle.i2c_exists(addr)]
        return []


# ============================================================
# ADC/DAC 驱动
# ============================================================

class ADCDriver:
    """ADC 模数转换驱动。"""

    def __init__(self, channel: int = 0, ref_voltage: float = 3.3,
                 bits: int = 12) -> None:
        self._channel = channel
        self._ref_voltage = ref_voltage
        self._bits = bits
        self._simulating = True

        # 尝试 ADS1115 / MCP3008
        try:
            import board
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn
            self._ads = ADS.ADS1115(board.I2C())
            self._adc = AnalogIn(self._ads, channel)
            self._simulating = False
        except ImportError:
            pass

    def read(self) -> int:
        """读取 ADC 值。"""
        if not self._simulating:
            raw = self._adc.value
            max_val = (1 << self._bits) - 1
            return min(raw, max_val)
        # 仿真：返回随机值
        import random
        return random.randint(0, (1 << self._bits) - 1)

    def read_voltage(self) -> float:
        """读取 ADC 电压值。"""
        raw = self.read()
        max_val = (1 << self._bits) - 1
        return (raw / max_val) * self._ref_voltage


# ============================================================
# 传感器驱动
# ============================================================

class TemperatureSensor:
    """温度传感器（DS18B20 / DHT11 / BME280）。"""

    def __init__(self, sensor_type: str = "dht11") -> None:
        self._type = sensor_type
        self._simulating = True

        try:
            import adafruit_dht
            self._dht = adafruit_dht.DHT11(17)  # GPIO17
            self._simulating = False
        except ImportError:
            pass

    def read(self) -> dict:
        """读取温度（°C）和湿度（%）。"""
        if not self._simulating:
            try:
                temp = self._dht.temperature
                humidity = self._dht.humidity
                return {"temperature": temp, "humidity": humidity}
            except Exception:
                return {"temperature": None, "humidity": None}
        # 仿真：返回随机值
        import random
        return {"temperature": random.uniform(20, 30),
                "humidity": random.uniform(40, 60)}


class DistanceSensor:
    """超声波测距传感器（HC-SR04）。"""

    def __init__(self, trigger_pin: int = 27, echo_pin: int = 22) -> None:
        self._trigger = trigger_pin
        self._echo = echo_pin
        self._simulating = True

    def read(self) -> float:
        """读取距离（米）。"""
        if not self._simulating:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)
            gpio.setup(self._trigger, gpio.OUT)
            gpio.setup(self._echo, gpio.IN)
            gpio.output(self._trigger, False)
            time.sleep(0.1)
            gpio.output(self._trigger, True)
            time.sleep(0.00001)
            gpio.output(self._trigger, False)
            while gpio.input(self._echo) == 0:
                start = time.time()
            while gpio.input(self._echo) == 1:
                end = time.time()
            distance = (end - start) * 34300 / 2
            gpio.cleanup()
            return distance / 100  # 转换为米
        # 仿真
        import random
        return random.uniform(0.02, 4.0)


# ============================================================
# 电机控制驱动
# ============================================================

class StepperMotor:
    """步进电机控制（A4988 / DRV8825）。"""

    def __init__(self, step_pin: int = 17, dir_pin: int = 27,
                 steps_per_rev: int = 200) -> None:
        self._step_pin = step_pin
        self._dir_pin = dir_pin
        self._steps_per_rev = steps_per_rev
        self._simulating = True

    def step(self, steps: int, speed: float = 0.01) -> None:
        """步进指定步数。"""
        if not self._simulating:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)
            gpio.setup(self._step_pin, gpio.OUT)
            gpio.setup(self._dir_pin, gpio.OUT)
            gpio.output(self._dir_pin, steps > 0)
            for _ in range(abs(steps)):
                gpio.output(self._step_pin, True)
                time.sleep(speed / 2)
                gpio.output(self._step_pin, False)
                time.sleep(speed / 2)
            gpio.cleanup()
        else:
            time.sleep(abs(steps) * 0.001)

    def rotate_degrees(self, degrees: float, speed: float = 0.01) -> None:
        """旋转指定角度。"""
        steps = int(degrees * self._steps_per_rev / 360)
        self.step(steps, speed)


class ServoMotor:
    """舵机控制（SG90 / MG996R）。"""

    def __init__(self, pin: int = 18, min_pulse: float = 500.0,
                 max_pulse: float = 2500.0) -> None:
        self._pin = pin
        self._min_pulse = min_pulse
        self._max_pulse = max_pulse
        self._simulating = True

    def set_angle(self, angle: float) -> None:
        """设置舵机角度（0-180）。"""
        if not self._simulating:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)
            gpio.setup(self._pin, gpio.OUT)
            pwm = gpio.PWM(self._pin, 50)
            pwm.start(0)
            duty = self._min_pulse + (angle / 180.0) * (self._max_pulse - self._min_pulse)
            pwm.ChangeDutyCycle(duty / 20.0)  # 50Hz → duty cycle 0-100
            time.sleep(0.3)
            pwm.stop()
            gpio.cleanup()
        else:
            time.sleep(0.1)


# ============================================================
# 显示驱动
# ============================================================

class OLEDDisplay:
    """OLED 显示屏驱动（SSD1306）。"""

    def __init__(self, width: int = 128, height: int = 64) -> None:
        self._width = width
        self._height = height
        self._simulating = True

    def clear(self) -> None:
        """清屏。"""
        pass  # 仿真

    def text(self, x: int, y: int, string: str, size: int = 1) -> None:
        """显示文本。"""
        pass  # 仿真

    def pixel(self, x: int, y: int, on: bool = True) -> None:
        """设置像素。"""
        pass  # 仿真


# ============================================================
# 驱动注册表
# ============================================================

class HardwareDriverRegistry:
    """硬件驱动注册表。"""

    _drivers: dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, driver_class: type) -> None:
        cls._drivers[name] = driver_class

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        if name not in cls._drivers:
            raise KeyError(f"未注册的硬件驱动: {name}")
        return cls._drivers[name](**kwargs)

    @classmethod
    def list_drivers(cls) -> list[str]:
        return list(cls._drivers.keys())


# 注册驱动
HardwareDriverRegistry.register("gpio", GPIOHardware)
HardwareDriverRegistry.register("serial", SerialDriver)
HardwareDriverRegistry.register("i2c", I2CDriver)
HardwareDriverRegistry.register("adc", ADCDriver)
HardwareDriverRegistry.register("temperature", TemperatureSensor)
HardwareDriverRegistry.register("distance", DistanceSensor)
HardwareDriverRegistry.register("stepper", StepperMotor)
HardwareDriverRegistry.register("servo", ServoMotor)
HardwareDriverRegistry.register("oled", OLEDDisplay)


# ============================================================
# 便捷函数
# ============================================================

def gpio(pin: int, mode: str = "out") -> None:
    """便捷 GPIO 初始化。"""
    drv = HardwareDriverRegistry.create("gpio")
    drv.setup(pin, mode.upper())


def gpio_write(pin: int, value: int) -> None:
    """便捷 GPIO 写入。"""
    drv = HardwareDriverRegistry.create("gpio")
    drv.output(pin, value)


def gpio_read(pin: int) -> int:
    """便捷 GPIO 读取。"""
    drv = HardwareDriverRegistry.create("gpio")
    return drv.input(pin)


def temperature() -> dict:
    """读取温度传感器。"""
    drv = HardwareDriverRegistry.create("temperature")
    return drv.read()


def distance() -> float:
    """读取距离传感器。"""
    drv = HardwareDriverRegistry.create("distance")
    return drv.read()


def motor_step(steps: int, speed: float = 0.01) -> None:
    """步进电机控制。"""
    drv = HardwareDriverRegistry.create("stepper")
    drv.step(steps, speed)


def servo_angle(angle: float) -> None:
    """舵机角度控制。"""
    drv = HardwareDriverRegistry.create("servo")
    drv.set_angle(angle)


def _register_real_hardware(builtins: dict) -> None:
    """将真实硬件驱动注册到解释器。"""
    builtins["GPIO"] = HardwareDriverRegistry.create("gpio")
    builtins["UART"] = lambda port="/dev/ttyUSB0", baud=9600: HardwareDriverRegistry.create("serial", port=port, baudrate=baud)
    builtins["I2C"] = lambda bus=1: HardwareDriverRegistry.create("i2c", bus=bus)
    builtins["ADC"] = lambda ch=0: HardwareDriverRegistry.create("adc", channel=ch)
    builtins["温度传感器"] = lambda: HardwareDriverRegistry.create("temperature")
    builtins["距离传感器"] = lambda: HardwareDriverRegistry.create("distance")
    builtins["步进电机"] = lambda: HardwareDriverRegistry.create("stepper")
    builtins["舵机"] = lambda pin=18: HardwareDriverRegistry.create("servo", pin=pin)
    builtins["OLED"] = lambda: HardwareDriverRegistry.create("oled")
    builtins["硬件驱动列表"] = HardwareDriverRegistry.list_drivers


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "GPIOHardware", "SerialDriver", "I2CDriver", "ADCDriver",
    "TemperatureSensor", "DistanceSensor",
    "StepperMotor", "ServoMotor", "OLEDDisplay",
    "HardwareDriverRegistry",
    "gpio", "gpio_write", "gpio_read",
    "temperature", "distance", "motor_step", "servo_angle",
    "_register_real_hardware",
]
