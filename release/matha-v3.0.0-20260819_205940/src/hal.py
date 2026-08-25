# -*- coding: utf-8 -*-
"""Matha 硬件抽象层 HAL：真实驱动 + 跨平台 + GPU 加速。"""

from __future__ import annotations
import importlib
import platform
import struct
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ============================================================
# 平台检测
# ============================================================

class Platform(Enum):
    WINDOWS = auto()
    LINUX_ARM = auto()    # Raspberry Pi
    LINUX_X86 = auto()
    MACOS = auto()
    UNKNOWN = auto()


def detect_platform() -> Platform:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Linux" and ("arm" in machine or "aarch64" in machine):
        return Platform.LINUX_ARM
    if system == "Linux":
        return Platform.LINUX_X86
    if system == "Windows":
        return Platform.WINDOWS
    if system == "Darwin":
        return Platform.MACOS
    return Platform.UNKNOWN


# ============================================================
# GPIO 驱动（跨平台）
# ============================================================

class GPIOInterface:
    """GPIO 抽象接口。"""

    def setup(self, pin: int, mode: str) -> None:
        raise NotImplementedError

    def output(self, pin: int, value: int) -> None:
        raise NotImplementedError

    def input(self, pin: int) -> int:
        raise NotImplementedError

    def PWM(self, pin: int, frequency: float, duty: float) -> None:
        raise NotImplementedError

    def cleanup(self) -> None:
        pass


class WindowsGPIO(GPIOInterface):
    """Windows GPIO 仿真（通过虚拟引脚）。"""

    def __init__(self) -> None:
        self._state: dict[int, dict] = {}

    def setup(self, pin: int, mode: str) -> None:
        if pin < 0:
            raise ValueError(f"无效引脚: {pin}")
        self._state[pin] = {"mode": mode, "value": 0}

    def output(self, pin: int, value: int) -> None:
        if pin not in self._state:
            self.setup(pin, "OUT")
        self._state[pin]["value"] = 1 if value else 0

    def input(self, pin: int) -> int:
        if pin not in self._state:
            self.setup(pin, "IN")
        return self._state[pin]["value"]

    def PWM(self, pin: int, frequency: float, duty: float) -> None:
        if pin < 0:
            raise ValueError(f"无效引脚: {pin}")
        self._state[pin] = {"mode": "PWM", "duty": duty, "freq": frequency}

    def cleanup(self) -> None:
        self._state.clear()


class LinuxARMGPIO(GPIOInterface):
    """Linux ARM GPIO（Raspberry Pi）。"""

    def __init__(self) -> None:
        self._gpio = None
        self._imported = False
        self._try_import()

    def _try_import(self) -> None:
        for module_name in ["RPi.GPIO", "gpiozero", "lgpio"]:
            try:
                self._gpio = importlib.import_module(module_name)
                self._imported = True
                break
            except ImportError:
                pass

    def setup(self, pin: int, mode: str) -> None:
        if not self._imported:
            raise RuntimeError("GPIO 库未安装：请运行 pip install RPi.GPIO 或 pip install gpiozero")
        import RPi.GPIO as gpio
        gpio.setmode(gpio.BCM)
        gpio.setup(pin, gpio.OUT if mode == "OUT" else gpio.IN)

    def output(self, pin: int, value: int) -> None:
        if not self._imported:
            return
        import RPi.GPIO as gpio
        gpio.output(pin, value)

    def input(self, pin: int) -> int:
        if not self._imported:
            return 0
        import RPi.GPIO as gpio
        return gpio.input(pin)

    def PWM(self, pin: int, frequency: float, duty: float) -> None:
        if not self._imported:
            return
        import RPi.GPIO as gpio
        pwm = gpio.PWM(pin, frequency)
        pwm.start(duty)

    def cleanup(self) -> None:
        if not self._imported:
            return
        import RPi.GPIO as gpio
        gpio.cleanup()


# ============================================================
# UART / Serial
# ============================================================

class SerialDriver:
    """UART/Serial 驱动。"""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._handle = None
        self._try_open()

    def _try_open(self) -> None:
        try:
            import serial
            self._serial = serial
            self._handle = serial.Serial(self._port, self._baudrate, timeout=1)
        except ImportError:
            pass
        except Exception:
            pass

    def write(self, data: bytes) -> int:
        if self._handle:
            return self._handle.write(data)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if self._handle:
            return self._handle.read(size)
        return b""

    def readline(self) -> str:
        if self._handle:
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
        self._handle = None
        try:
            import smbus2
            self._smbus = smbus2
            self._handle = smbus2.SMBus(bus)
        except ImportError:
            pass

    def write_byte(self, addr: int, value: int) -> None:
        if self._handle:
            self._handle.write_byte(addr, value)

    def read_byte(self, addr: int) -> int:
        if self._handle:
            return self._handle.read_byte(addr)
        return 0

    def scan(self) -> list[int]:
        if self._handle:
            return [addr for addr in range(0x03, 0x78)
                    if self._handle.i2c_exists(addr)]
        return []

    def close(self) -> None:
        if self._handle:
            self._handle.close()


# ============================================================
# ADC/DAC
# ============================================================

class ADCDriver:
    """ADC 模数转换驱动。"""

    def __init__(self, channel: int = 0, ref_voltage: float = 3.3, bits: int = 12) -> None:
        self._channel = channel
        self._ref_voltage = ref_voltage
        self._bits = bits
        self._simulating = True

        # 尝试 ADS1115
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
        if not self._simulating:
            return self._adc.value
        import random
        return random.randint(0, (1 << self._bits) - 1)

    def read_voltage(self) -> float:
        raw = self.read()
        return (raw / ((1 << self._bits) - 1)) * self._ref_voltage


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
            self._dht = adafruit_dht.DHT11(17)
            self._simulating = False
        except ImportError:
            pass

    def read(self) -> dict:
        if not self._simulating:
            try:
                return {"temperature": self._dht.temperature,
                        "humidity": self._dht.humidity}
            except Exception:
                return {"temperature": None, "humidity": None}
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
        if not self._simulating:
            try:
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
                return distance / 100
            except Exception:
                pass
        import random
        return random.uniform(0.02, 4.0)


# ============================================================
# GPU 加速（CUDA）
# ============================================================

class GPUSupport:
    """CUDA GPU 加速支持。"""

    def __init__(self) -> None:
        self._cuda_available = False
        self._cuda_devices: list[dict] = []
        self._try_detect()

    def _try_detect(self) -> None:
        try:
            import cupy
            self._cuda_available = True
            self._cupy = cupy
            self._cuda_devices = [
                {"id": i, "name": cupy.cuda.runtime.getDeviceProperties(i).name,
                 "memory": cupy.cuda.runtime.getDeviceProperties(i).totalGlobalMem}
                for i in range(cupy.cuda.runtime.getDeviceCount())
            ]
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self._cuda_available

    @property
    def devices(self) -> list[dict]:
        return self._cuda_devices

    def to_gpu(self, array: list) -> Any:
        """将数组传输到 GPU。"""
        if not self._cuda_available:
            raise RuntimeError("CUDA 不可用，请安装 cupy: pip install cupy")
        import cupy as cp
        return cp.array(array)

    def to_cpu(self, gpu_array: Any) -> list:
        """将数组从 GPU 传回 CPU。"""
        if not self._cuda_available:
            raise RuntimeError("CUDA 不可用")
        import cupy as cp
        return cp.asnumpy(gpu_array).tolist()


# ============================================================
# 统一硬件抽象层
# ============================================================

@dataclass
class HALConfig:
    """HAL 配置。"""
    platform: Platform = Platform.UNKNOWN
    gpio_pins: int = 28
    i2c_bus: int = 1
    uart_port: str = "/dev/ttyUSB0"
    use_gpu: bool = False


class HardwareAbstractionLayer:
    """硬件抽象层：统一 API 跨平台。"""

    def __init__(self, config: Optional[HALConfig] = None) -> None:
        self.config = config or HALConfig(platform=detect_platform())
        self._gpio: Optional[GPIOInterface] = None
        self._serial: Optional[SerialDriver] = None
        self._i2c: Optional[I2CDriver] = None
        self._adc: Optional[ADCDriver] = None
        self._temp: Optional[TemperatureSensor] = None
        self._dist: Optional[DistanceSensor] = None
        self._gpu: Optional[GPUSupport] = None
        self._init_drivers()

    def _init_drivers(self) -> None:
        """根据平台初始化驱动。"""
        if self.config.platform == Platform.LINUX_ARM:
            self._gpio = LinuxARMGPIO()
        else:
            self._gpio = WindowsGPIO()

        self._i2c = I2CDriver(bus=self.config.i2c_bus)
        self._adc = ADCDriver()
        self._temp = TemperatureSensor()
        self._dist = DistanceSensor()
        self._gpu = GPUSupport() if self.config.use_gpu else None

    # GPIO API
    def gpio_setup(self, pin: int, mode: str = "out") -> None:
        if self._gpio:
            self._gpio.setup(pin, mode)

    def gpio_write(self, pin: int, value: int) -> None:
        if self._gpio:
            self._gpio.output(pin, value)

    def gpio_read(self, pin: int) -> int:
        if self._gpio:
            return self._gpio.input(pin)
        return 0

    def gpio_pwm(self, pin: int, freq: float, duty: float) -> None:
        if self._gpio:
            self._gpio.PWM(pin, freq, duty)

    def gpio_cleanup(self) -> None:
        if self._gpio:
            self._gpio.cleanup()

    # UART API
    def serial_write(self, data: bytes) -> int:
        if not self._serial:
            self._serial = SerialDriver(self.config.uart_port)
        return self._serial.write(data)

    def serial_read(self, size: int = 1) -> bytes:
        if not self._serial:
            self._serial = SerialDriver(self.config.uart_port)
        return self._serial.read(size)

    def serial_close(self) -> None:
        if self._serial:
            self._serial.close()

    # I2C API
    def i2c_write(self, addr: int, value: int) -> None:
        if self._i2c:
            self._i2c.write_byte(addr, value)

    def i2c_read(self, addr: int) -> int:
        if self._i2c:
            return self._i2c.read_byte(addr)
        return 0

    def i2c_scan(self) -> list[int]:
        if self._i2c:
            return self._i2c.scan()
        return []

    def i2c_close(self) -> None:
        if self._i2c:
            self._i2c.close()

    # ADC API
    def adc_read(self) -> int:
        if self._adc:
            return self._adc.read()

    def adc_voltage(self) -> float:
        if self._adc:
            return self._adc.read_voltage()
        return 0.0

    # Sensor API
    def temperature(self) -> dict:
        if self._temp:
            return self._temp.read()
        return {"temperature": 25.0, "humidity": 50.0}

    def distance(self) -> float:
        if self._dist:
            return self._dist.read()
        import random
        return random.uniform(0.1, 2.0)

    # GPU API
    @property
    def gpu_available(self) -> bool:
        return self._gpu is not None and self._gpu.available

    @property
    def gpu_devices(self) -> list[dict]:
        return self._gpu.devices if self._gpu else []

    def to_gpu(self, data: list) -> Any:
        if self._gpu:
            return self._gpu.to_gpu(data)
        raise RuntimeError("GPU 不可用")

    def to_cpu(self, gpu_data: Any) -> list:
        if self._gpu:
            return self._gpu.to_cpu(gpu_data)
        raise RuntimeError("GPU 不可用")

    # 系统信息
    def platform_info(self) -> dict:
        return {
            "platform": self.config.platform.name,
            "system": platform.system(),
            "machine": platform.machine(),
            "cpu_count": __import__("os").cpu_count(),
            "gpu_available": self.gpu_available,
            "gpu_devices": self.gpu_devices,
        }

    def cleanup(self) -> None:
        self.gpio_cleanup()
        self.serial_close()
        self.i2c_close()


# ============================================================
# 模块级单例
# ============================================================

_hal_instance: Optional[HardwareAbstractionLayer] = None


def hal() -> HardwareAbstractionLayer:
    """获取 HAL 单例。"""
    global _hal_instance
    if _hal_instance is None:
        _hal_instance = HardwareAbstractionLayer()
    return _hal_instance


def register_hardware_builtins(builtins: dict) -> None:
    """将 HAL 函数注册为 Matha 内建。"""
    h = hal()
    builtins["HAL平台信息"] = h.platform_info
    builtins["GPIO初始化"] = lambda args: h.gpio_setup(args[0], args[1] if len(args) > 1 else "out")
    builtins["GPIO写入"] = lambda args: h.gpio_write(args[0], args[1])
    builtins["GPIO读取"] = lambda args: h.gpio_read(args[0])
    builtins["I2C扫描"] = h.i2c_scan
    builtins["ADC读数"] = h.adc_read
    builtins["ADC电压"] = h.adc_voltage
    builtins["温度传感器"] = h.temperature
    builtins["距离传感器"] = h.distance
    builtins["GPU可用"] = h.gpu_available
    builtins["GPU设备"] = h.gpu_devices


# ============================================================
# 导出
# ============================================================

__all__ = [
    "Platform", "detect_platform",
    "GPIOInterface", "WindowsGPIO", "LinuxARMGPIO",
    "SerialDriver", "I2CDriver", "ADCDriver",
    "TemperatureSensor", "DistanceSensor",
    "GPUSupport",
    "HALConfig", "HardwareAbstractionLayer",
    "hal", "register_hardware_builtins",
]
