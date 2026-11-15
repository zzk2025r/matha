"""Matha 设备驱动框架：内存虚拟设备的登记与簿记模拟。

能力边界（阶段 22a 假成功清算）：本框架是自洽的内存模拟——
DMA 分配、USB 枚举、SSD 块存储、音频参数计算等簿记面真实可查。
凡需要真实硬件后端的面一律显式拒绝，不再伪造：GPU 着色器
编译与绘制、网卡收发、SMART 传感器读数（health/温度）、
基类设备寄存器读写。
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviceClass(Enum):
    GPU = "gpu"
    AUDIO = "audio"
    USB = "usb"
    SSD = "ssd"
    NIC = "nic"
    INPUT = "input"
    DISPLAY = "display"
    CAMERA = "camera"
    SENSOR = "sensor"


class BusType(Enum):
    PCI = "pci"
    PCIE = "pcie"
    USB = "usb"
    I2C = "i2c"
    SPI = "spi"
    MMIO = "mmio"
    VIRTUAL = "virtual"


class DriverState(Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    RUNNING = "running"
    SUSPENDED = "suspended"
    ERROR = "error"


@dataclass
class DeviceId:
    vendor_id: int = 0x10DE
    device_id: int = 0x2484
    subsystem_vendor: int = 0
    subsystem_device: int = 0
    revision: int = 0x01
    bus: BusType = BusType.PCI
    slot: int = 0


@dataclass
class DeviceInfo:
    name: str = "device"
    device_class: DeviceClass = DeviceClass.GPU
    device_id: DeviceId = field(default_factory=DeviceId)
    vendor: str = "unknown"
    driver_version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)
    resources: dict[str, int] = field(default_factory=dict)


@dataclass
class DMABuffer:
    address: int = 0
    size: int = 0
    direction: str = "out"
    coherent: bool = True
    mapped: bool = False


class DeviceDriver:
    """设备驱动基类。"""

    def __init__(self, info: DeviceInfo):
        self.info = info
        self.state = DriverState.UNLOADED
        self._dma_buffers: dict[int, DMABuffer] = {}
        self._next_buffer = 0x1000
        self._interrupts: dict[int, Callable] = {}
        self._lock = threading.Lock()

    def load(self) -> bool:
        with self._lock:
            self.state = DriverState.LOADED
            return True

    def initialize(self) -> bool:
        with self._lock:
            self.state = DriverState.INITIALIZED
            return True

    def start(self) -> bool:
        with self._lock:
            self.state = DriverState.RUNNING
            return True

    def stop(self) -> bool:
        with self._lock:
            self.state = DriverState.SUSPENDED
            return True

    def unload(self) -> bool:
        with self._lock:
            self.state = DriverState.UNLOADED
            return True

    def allocate_dma(self, size: int,
                        direction: str = "out") -> DMABuffer:
        with self._lock:
            buf = DMABuffer(
                address=self._next_buffer,
                size=size, direction=direction,
            )
            self._next_buffer += size
            self._next_buffer = (self._next_buffer + 0xFFF) & ~0xFFF
            self._dma_buffers[buf.address] = buf
            return buf

    def free_dma(self, address: int) -> bool:
        with self._lock:
            if address in self._dma_buffers:
                del self._dma_buffers[address]
                return True
        return False

    def register_isr(self, irq: int,
                        handler: Callable) -> bool:
        self._interrupts[irq] = handler
        return True

    def read(self, offset: int, size: int) -> bytes:
        raise NotImplementedError("设备寄存器读取需要真实硬件，未实现")

    def write(self, offset: int, data: bytes) -> int:
        raise NotImplementedError("设备寄存器写入需要真实硬件，未实现")

    def probe(self) -> bool:
        raise NotImplementedError("设备探测需要真实总线，未实现")


class GPUDevice(DeviceDriver):
    """GPU 设备驱动。"""

    def __init__(self):
        super().__init__(DeviceInfo(
            name="虚拟GPU",
            device_class=DeviceClass.GPU,
            vendor="Matha",
            capabilities=["opengl", "vulkan", "compute",
                          "raytracing", "video"],
            resources={
                "vram_mb": 8192,
                "shading_units": 128,
                "max_texture": 16384,
            },
        ))
        self._shaders: dict[str, bytes] = {}
        self._buffers: dict[str, list[float]] = {}
        self._textures: dict[str, tuple[int, int, int]] = {}

    def compile_shader(self, stage: str,
                        source: str) -> dict[str, Any]:
        raise NotImplementedError(
            f"GPU {stage} 着色器编译需要真实驱动后端，未实现")

    def create_buffer(self, name: str,
                        data: list[float]) -> bool:
        self._buffers[name] = list(data)
        return True

    def create_texture(self, name: str,
                        width: int, height: int,
                        format: int = 0x1908) -> bool:
        self._textures[name] = (width, height, format)
        return True

    def set_uniform(self, name: str, value: float) -> bool:
        self._buffers[name] = [value]
        return True

    def draw(self, vertex_count: int = 3) -> dict[str, Any]:
        raise NotImplementedError("GPU 绘制需要真实渲染管线，未实现")

    def readback(self, name: str) -> list[float]:
        return self._buffers.get(name, [])

    def get_stats(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "shaders": len(self._shaders),
            "buffers": len(self._buffers),
            "textures": len(self._textures),
            "vram_mb": self.info.resources.get("vram_mb", 0),
        }


class AudioDevice(DeviceDriver):
    """音频设备驱动。"""

    def __init__(self, sample_rate: int = 48000,
                    channels: int = 2, bits: int = 16):
        super().__init__(DeviceInfo(
            name="虚拟声卡",
            device_class=DeviceClass.AUDIO,
            vendor="Matha",
            capabilities=["pcm", "samplerate", "volume"],
            resources={
                "sample_rate": sample_rate,
                "channels": channels,
                "bits": bits,
            },
        ))
        self.sample_rate = sample_rate
        self.channels = channels
        self.bits = bits
        self.volume = 0.8
        self.muted = False

    def set_volume(self, value: float) -> bool:
        self.volume = max(0.0, min(1.0, value))
        return True

    def set_mute(self, muted: bool) -> bool:
        self.muted = muted
        return True

    def buffer_size(self, duration_ms: float) -> int:
        frames = int(self.sample_rate * duration_ms / 1000)
        return frames * self.channels * (self.bits // 8)

    def get_stats(self) -> dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bits": self.bits,
            "volume": self.volume,
            "muted": self.muted,
        }


class USBController(DeviceDriver):
    """USB 控制器驱动。"""

    def __init__(self):
        super().__init__(DeviceInfo(
            name="USB 3.0 控制器",
            device_class=DeviceClass.USB,
            vendor="Matha",
            capabilities=["xhci", "ehci", "ohci", "type-c"],
            resources={"ports": 8, "speed_gbps": 5},
        ))
        self._devices: dict[int, dict[str, Any]] = {}
        self._next_addr = 1

    def enumerate(self) -> list[dict[str, Any]]:
        return list(self._devices.values())

    def attach(self, name: str, vid: int = 0x1234,
                pid: int = 0x5678) -> int:
        addr = self._next_addr
        self._next_addr += 1
        self._devices[addr] = {
            "address": addr, "name": name,
            "vendor_id": vid, "product_id": pid,
            "speed": "super",
        }
        return addr

    def detach(self, address: int) -> bool:
        if address in self._devices:
            del self._devices[address]
            return True
        return False

    def get_descriptor(self, address: int) -> dict[str, Any] | None:
        return self._devices.get(address)

    def reset_port(self, port: int) -> bool:
        ports = self.info.resources.get("ports", 0)
        return 0 <= port < ports


class SSDDevice(DeviceDriver):
    """SSD 设备驱动（NVMe）。"""

    def __init__(self, capacity_gb: int = 512):
        super().__init__(DeviceInfo(
            name="NVMe SSD",
            device_class=DeviceClass.SSD,
            vendor="Matha",
            capabilities=["nvme", "trim", "queues"],
            resources={"capacity_gb": capacity_gb,
                        "queues": 8, "lanes": 4},
        ))
        self.capacity_gb = capacity_gb
        self._blocks: dict[int, bytes] = {}
        self._trimmed = 0
        self._read_ops = 0
        self._write_ops = 0

    def read_blocks(self, lba: int, count: int) -> bytes:
        self._read_ops += 1
        return self._blocks.get(lba, b"\x00" * 512 * count)

    def write_blocks(self, lba: int, data: bytes) -> int:
        self._write_ops += 1
        self._blocks[lba] = data
        return len(data)

    def trim(self, lba: int, count: int) -> bool:
        for block in range(lba, lba + count):
            self._blocks.pop(block, None)
        self._trimmed += count
        return True

    def flush(self) -> bool:
        return True

    def smart(self) -> dict[str, Any]:
        return {
            "read_ops": self._read_ops,
            "write_ops": self._write_ops,
            "trimmed_blocks": self._trimmed,
        }


class NICDevice(DeviceDriver):
    """网卡驱动。"""

    def __init__(self, mac: str = "00:11:22:33:44:55"):
        super().__init__(DeviceInfo(
            name="以太网卡",
            device_class=DeviceClass.NIC,
            vendor="Matha",
            capabilities=["tcp", "udp", "offload"],
            resources={"mac": mac, "mtu": 1500},
        ))
        self.mac = mac
        self.mtu = 1500
        self._rx_packets = 0
        self._tx_packets = 0
        self._tx_bytes = 0
        self._rx_bytes = 0

    def send(self, data: bytes) -> int:
        raise NotImplementedError("网卡发送需要真实网络栈，未实现")

    def receive(self, size: int = 1500) -> bytes:
        raise NotImplementedError("网卡接收需要真实网络栈，未实现")

    def set_mtu(self, mtu: int) -> bool:
        if 68 <= mtu <= 9000:
            self.mtu = mtu
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "mac": self.mac, "mtu": self.mtu,
            "tx_packets": self._tx_packets,
            "rx_packets": self._rx_packets,
            "tx_bytes": self._tx_bytes,
            "rx_bytes": self._rx_bytes,
        }


class DriverRegistry:
    """驱动注册表。"""

    def __init__(self):
        self._drivers: dict[DeviceClass, DeviceDriver] = {}
        self._lock = threading.Lock()

    def register(self, driver: DeviceDriver) -> bool:
        with self._lock:
            cls = driver.info.device_class
            driver.load()
            driver.initialize()
            driver.start()
            self._drivers[cls] = driver
            return True

    def get(self, device_class: DeviceClass) -> DeviceDriver | None:
        return self._drivers.get(device_class)

    def list_drivers(self) -> list[str]:
        return [c.value for c in self._drivers]


def create_gpu_device() -> GPUDevice:
    return GPUDevice()


def create_audio_device(sample_rate: int = 48000,
                        channels: int = 2,
                        bits: int = 16) -> AudioDevice:
    return AudioDevice(sample_rate, channels, bits)


def create_usb_controller() -> USBController:
    return USBController()


def create_ssd_device(capacity_gb: int = 512) -> SSDDevice:
    return SSDDevice(capacity_gb)


def create_nic_device(mac: str = "00:11:22:33:44:55") -> NICDevice:
    return NICDevice(mac)


def create_driver_registry() -> DriverRegistry:
    return DriverRegistry()


# ============================================================
# 内置注册
# ============================================================

def _register_device_driver(builtins: dict) -> None:
    builtins["创建GPU设备"] = create_gpu_device
    builtins["创建音频设备"] = create_audio_device
    builtins["创建USB控制器"] = create_usb_controller
    builtins["创建固态硬盘"] = create_ssd_device
    builtins["创建网卡设备"] = create_nic_device
    builtins["创建驱动注册表"] = create_driver_registry


def _device_driver_names() -> list[str]:
    return ["创建GPU设备", "创建音频设备",
            "创建USB控制器", "创建固态硬盘",
            "创建网卡设备", "创建驱动注册表"]


__all__ = [
    "DeviceClass", "BusType", "DriverState",
    "DeviceId", "DeviceInfo", "DMABuffer",
    "DeviceDriver", "GPUDevice", "AudioDevice",
    "USBController", "SSDDevice", "NICDevice",
    "DriverRegistry",
    "create_gpu_device", "create_audio_device",
    "create_usb_controller", "create_ssd_device",
    "create_nic_device", "create_driver_registry",
    "_register_device_driver", "_device_driver_names",
]
