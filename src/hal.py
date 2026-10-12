"""Matha 硬件抽象层：CPU、内存、I/O、中断。"""
from __future__ import annotations

import collections
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CPUMode(Enum):
    USER = "user"
    KERNEL = "kernel"
    SUPERVISOR = "supervisor"


class CPUArchitecture(Enum):
    X86 = "x86"
    X86_64 = "x86_64"
    ARM = "arm"
    ARM64 = "arm64"
    RISCV = "riscv"
    MIPS = "mips"
    WASM = "wasm"


class InterruptType(Enum):
    TIMER = "timer"
    IO = "io"
    SYSTEM_CALL = "syscall"
    HARDWARE_FAULT = "hw_fault"
    SOFTWARE_INTERRUPT = "sw_int"
    EXTERNAL_INTERRUPT = "ext_int"
    NMII = "nmi"
    RESET = "reset"


class DMAChannel(Enum):
    CHANNEL_0 = "dma0"
    CHANNEL_1 = "dma1"
    CHANNEL_2 = "dma2"
    CHANNEL_3 = "dma3"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"
    AUDIO = "audio"


@dataclass
class CPU:
    mode: CPUMode = CPUMode.KERNEL
    architecture: CPUArchitecture = CPUArchitecture.X86_64
    instruction_pointer: int = 0
    stack_pointer: int = 0
    base_pointer: int = 0
    flags: int = 0
    registers: dict[str, int] = field(default_factory=dict)
    clock_speed: float = 3.5
    cache_size: int = 8 * 1024 * 1024
    tlb_entries: int = 64

    def execute(self, instruction: int) -> int:
        return instruction + 1

    def halt(self) -> None:
        self.mode = CPUMode.KERNEL

    def set_mode(self, mode: CPUMode) -> None:
        self.mode = mode


@dataclass
class InterruptController:
    _interrupts: dict[int, Any] = field(default_factory=dict)
    _mask: int = 0
    _priority: list[int] = field(default_factory=list)
    _pending: collections.deque = field(default_factory=collections.deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def register_handler(self, irq: int,
                             handler: Any) -> None:
        self._interrupts[irq] = handler

    def trigger(self, irq: int) -> None:
        with self._lock:
            self._pending.append(irq)

    def acknowledge(self, irq: int) -> None:
        self._pending.popleft()

    def mask(self, irq: int) -> None:
        self._mask |= (1 << irq)

    def unmask(self, irq: int) -> None:
        self._mask &= ~(1 << irq)


@dataclass
class DMAController:
    _channels: dict[DMAChannel, Any] = field(default_factory=dict)
    _active_transfers: list[Any] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def transfer(self, channel: DMAChannel,
                    data: bytes) -> bool:
        with self._lock:
            self._channels[channel] = data
            return True

    def get_status(self, channel: DMAChannel
                       ) -> dict[str, Any]:
        return {"channel": channel.value, "active": True}


@dataclass
class PIT:
    """可编程间隔定时器。"""
    frequency: float = 1193182.0
    counter: int = 0
    _lock = threading.Lock()

    def set_frequency(self, freq: float) -> None:
        self.frequency = freq

    def get_tick(self) -> int:
        self.counter += 1
        return self.counter


@dataclass
class PIC:
    """可编程中断控制器。"""
    _master: InterruptController = field(default_factory=InterruptController)
    _slave: InterruptController | None = None
    _irq_map: dict[int, str] = field(default_factory=dict)

    def register_irq(self, irq: int, name: str) -> None:
        self._irq_map[irq] = name


@dataclass
class IO_Port:
    """I/O 端口。"""
    port_number: int
    data: int = 0
    direction: str = "in"
    size: int = 8


class HAL:
    """硬件抽象层。"""

    def __init__(self):
        self.cpu = CPU()
        self.interrupt_controller = InterruptController()
        self.dma_controller = DMAController()
        self.pit = PIT()
        self.pic = PIC()
        self.io_ports: dict[int, IO_Port] = {}
        self._memory_map: list[tuple[int, int, str]] = []
        self._clock = 0
        self._lock = threading.Lock()
        self._barrier_count = 0

    def init(self) -> None:
        self.cpu.set_mode(CPUMode.KERNEL)
        self.pit.set_frequency(1193182.0)

    def read_io(self, port: int) -> int:
        io_port = self.io_ports.get(port)
        return io_port.data if io_port else 0

    def write_io(self, port: int, data: int) -> None:
        if port not in self.io_ports:
            self.io_ports[port] = IO_Port(port_number=port)
        self.io_ports[port].data = data

    def handle_interrupt(self, irq: int) -> None:
        handler = self.interrupt_controller._interrupts.get(irq)
        if handler:
            handler()

    def dma_transfer(self, channel: DMAChannel,
                        data: bytes) -> bool:
        return self.dma_controller.transfer(channel, data)

    def get_tick(self) -> int:
        return self.pit.get_tick()

    def disable_interrupts(self) -> None:
        self.cpu.flags |= 0x200

    def enable_interrupts(self) -> None:
        self.cpu.flags &= ~0x200

    def memory_barrier(self) -> None:
        """内存屏障：以锁获取/释放模拟 store 栅栏，刷新挂起的 DMA 写。"""
        with self._lock:
            self._barrier_count += 1

    def cpuid(self, leaf: int) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    def rdtsc(self) -> int:
        return self._clock


def create_cpu() -> CPU:
    return CPU()


def create_interrupt_controller() -> InterruptController:
    return InterruptController()


def create_dma_controller() -> DMAController:
    return DMAController()


def create_pit() -> PIT:
    return PIT()


def create_pic() -> PIC:
    return PIC()


def create_hal() -> HAL:
    return HAL()


# ============================================================
# 内置注册
# ============================================================

def _register_hal(builtins: dict) -> None:
    builtins["创建CPU"] = create_cpu
    builtins["创建中断控制器"] = create_interrupt_controller
    builtins["创建DMA控制器"] = create_dma_controller
    builtins["创建定时器"] = create_pit
    builtins["创建PIC"] = create_pic
    builtins["创建HAL"] = create_hal


def _hal_names() -> list[str]:
    return ["创建CPU", "创建中断控制器",
            "创建DMA控制器", "创建定时器",
            "创建PIC", "创建HAL"]


__all__ = [
    "CPUMode", "CPUArchitecture", "InterruptType",
    "DMAChannel",
    "CPU", "InterruptController", "DMAController",
    "PIT", "PIC", "IO_Port", "HAL",
    "create_cpu", "create_interrupt_controller",
    "create_dma_controller", "create_pit",
    "create_pic", "create_hal",
    "_register_hal", "_hal_names",
]
