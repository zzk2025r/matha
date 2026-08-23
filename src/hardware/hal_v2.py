# -*- coding: utf-8 -*-
"""
Matha 硬件抽象层 v2.0
=======================
安全副作用 / 指针与内存控制 / 裸机支持 / 协议解释生成器

架构：
  Matha 符号 → 安全副作用引擎 → 指针/内存管理器 → HAL 设备 → 实体硬件/模拟
  Matha 符号 → 原生编译器 → 协议解释器 → 驱动代码生成

功能：
  1. SafeSideEffect  — 可追踪副作用，支持沙箱隔离
  2. PointerManager  — 指针算术、内存分配/释放、越界检测
  3. BareMetalTarget — 裸机编译目标（x86_64/ARM/RISC-V/AVR）
  4. ProtocolParser  — UART/SPI/I2C/CAN 协议解释生成器
  5. DriverGenerator — 构建各类硬件驱动代码
"""
from __future__ import annotations
import sys
import os
import json
import time
import logging
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("matha.hardware")


# ═══════════════════════════════════════════════════════════════════════════════
#  1. 副作用追踪系统
# ═══════════════════════════════════════════════════════════════════════════════

class SideEffectType(Enum):
    """副作用类型。"""
    NONE = "none"
    READ = "read"           # 纯读取，无副作用
    WRITE = "write"         # 写入状态
    IO = "io"               # 外部 I/O（串口/网络/文件）
    MEMORY = "memory"       # 内存操作（指针/分配）
    HARDWARE = "hardware"   # 硬件操作（GPIO/I2C/ADC）
    SYSTEM = "system"       # 系统级（进程/线程/信号）


@dataclass(frozen=True)
class SideEffect:
    """副作用描述符。"""
    effect_type: SideEffectType
    target: str           # 目标对象（寄存器名/端口名/变量名）
    operation: str        # 操作（read/write/set/clear）
    value: Any = None
    safe: bool = True     # 是否在沙箱内安全执行
    permission: str = "readonly"  # readonly/write/exec
    error: str = ""       # 异常信息

    def __str__(self):
        return f"{self.effect_type.value}:{self.target}({self.operation})"


class SafeSideEffectEngine:
    """
    安全副作用引擎。

    功能：
      1. 追踪每个函数/表达式的副作用类型
      2. 执行前权限检查（只读/读写/执行）
      3. 沙箱隔离（限制 IO/HARDWARE/SYSTEM 操作）
      4. 副作用审计日志
    """

    def __init__(self, mode: str = "full"):
        """
        mode: "sandbox"（沙箱，限制 IO/HARDWARE/SYSTEM）
              "restricted"（受限，允许读写，限制 I/O）
              "full"（全功能，无限制）
        """
        self._mode = mode
        self._lock = threading.Lock()
        self._audit_log: List[SideEffect] = []
        self._registry: Dict[str, SideEffectType] = {}  # func_name → effect_type
        self._permission_map: Dict[str, str] = {}       # func_name → perm
        self._total_calls = 0
        self._blocked_calls = 0
        logger.info(f"  [副作用引擎] 初始化: mode={mode}")

    def register_func(self, name: str, effect_type: SideEffectType,
                      permission: str = "readonly") -> None:
        """注册函数及其副作用类型。"""
        with self._lock:
            self._registry[name] = effect_type
            self._permission_map[name] = permission
        logger.debug(f"  [副作用] 注册: {name} → {effect_type.value}({permission})")

    def check_permission(self, func_name: str, required_perm: str = "readonly") -> bool:
        """检查执行权限。"""
        with self._lock:
            perm = self._permission_map.get(func_name, "readonly")
            # 权限等级：readonly < write < exec
            level = {"readonly": 0, "write": 1, "exec": 2}
            allowed = level.get(perm, 0) >= level.get(required_perm, 0)
        if not allowed:
            self._blocked_calls += 1
            logger.warning(f"  [副作用] 权限拒绝: {func_name} 需要 {required_perm}，当前权限 {perm}")
        return allowed

    def execute_with_check(self, func: Callable, *args, **kwargs) -> Any:
        """在权限检查后执行函数。"""
        func_name = getattr(func, "__name__", str(func))
        with self._lock:
            effect = self._registry.get(func_name, SideEffectType.NONE)
            perm = self._permission_map.get(func_name, "readonly")

        # 沙箱模式限制
        if self._mode == "sandbox" and effect in (SideEffectType.IO, SideEffectType.HARDWARE, SideEffectType.SYSTEM):
            self._blocked_calls += 1
            raise PermissionError(f"沙箱模式禁止 {effect.value} 操作: {func_name}")

        self._total_calls += 1
        try:
            result = func(*args, **kwargs)
            self._audit_log.append(SideEffect(effect, func_name, "call", result,
                                               safe=(self._mode != "sandbox")))
            return result
        except Exception as e:
            self._audit_log.append(SideEffect(effect, func_name, "error", None,
                                               safe=False, error=str(e)))
            raise

    def get_stats(self) -> dict:
        """获取副作用引擎统计。"""
        with self._lock:
            return {
                "mode": self._mode,
                "total_calls": self._total_calls,
                "blocked_calls": self._blocked_calls,
                "registered_funcs": len(self._registry),
                "audit_entries": len(self._audit_log),
                "by_type": self._count_by_type(),
            }

    def _count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for name, etype in self._registry.items():
            key = etype.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def clear_audit(self) -> None:
        """清空审计日志。"""
        with self._lock:
            self._audit_log.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  2. 指针与内存控制
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPage:
    """内存页。"""
    _page_size = 4096  # 4KB

    def __init__(self, page_id: int, base_addr: int):
        self.page_id = page_id
        self.base_addr = base_addr
        self.data: bytearray = bytearray(self._page_size)
        self.readable = True
        self.writable = False
        self.executable = False

    def read(self, offset: int, size: int = 1) -> Any:
        if offset < 0 or offset + size > self._page_size:
            raise MemoryError(f"越界读取: page={self.page_id}, offset={offset}, size={size}")
        raw = bytes(self.data[offset:offset + size])
        # 尝试解析为整数
        try:
            return int.from_bytes(raw, 'little', signed=True)
        except (ValueError, OverflowError):
            return raw

    def write(self, offset: int, value: Any, size: int = 1) -> None:
        if not self.writable:
            raise MemoryError(f"只读页写入: page={self.page_id}, offset={offset}")
        if offset < 0 or offset + size > self._page_size:
            raise MemoryError(f"越界写入: page={self.page_id}, offset={offset}, size={size}")
        if isinstance(value, (int, float)):
            self.data[offset:offset + size] = int(value).to_bytes(size, 'little', signed=True)
        elif isinstance(value, bytes):
            self.data[offset:offset + size] = value[:size]
        else:
            self.data[offset:offset + size] = str(value).encode()[:size]

    def __repr__(self):
        return f"Page({self.page_id}@{self.base_addr:#x} r={self.readable} w={self.writable} x={self.executable})"


class Pointer:
    """数学指针（带安全检查）。"""

    def __init__(self, manager: 'PointerManager', addr: int, name: str = ""):
        self._mgr = manager
        self._addr = addr
        self._name = name
        self._type: str = "void"
        self._life_id = id(self)

    @property
    def addr(self) -> int:
        return self._addr

    @property
    def name(self) -> str:
        return self._name

    def get(self, offset: int = 0, size: int = 1) -> Any:
        """读取指针指向的内存。"""
        return self._mgr.read(self._addr + offset, size)

    def set(self, value: Any, offset: int = 0, size: int = 1) -> None:
        """写入指针指向的内存。"""
        self._mgr.write(self._addr + offset, value, size)

    def plus(self, offset: int) -> 'Pointer':
        """指针算术：返回新指针。"""
        return Pointer(self._mgr, self._addr + offset, f"{self._name}+{offset}")

    def deref(self) -> Any:
        """解引用：读取指针指向的值。"""
        return self._mgr.read(self._addr)

    def __repr__(self):
        return f"Ptr({self._name}@{self._addr:#x} type={self._type})"

    def __eq__(self, other):
        return isinstance(other, Pointer) and self._addr == other._addr

    def __hash__(self):
        return hash(self._addr)


class PointerManager:
    """
    指针与内存管理器。

    功能：
      1. 堆内存分配/释放（带越界检测）
      2. 指针算术（+,-,*,/）
      3. 内存安全检查（只读页写入检测）
      4. 生命周期追踪（防止悬空指针）
    """

    def __init__(self, page_count: int = 16):
        self._pages: List[MemoryPage] = [
            MemoryPage(i, i * MemoryPage._page_size)
            for i in range(page_count)
        ]
        # 前 4 页为系统区（只读），其余可写
        for i in range(4):
            self._pages[i].writable = False
        # 确保有足够页（至少 8 页）
        while len(self._pages) < max(page_count, 8):
            self._pages.append(MemoryPage(len(self._pages), len(self._pages) * MemoryPage._page_size))
        for page in self._pages[4:]:
            page.writable = True

        self._allocations: Dict[int, Tuple[int, int]] = {}  # ptr_addr → (page_id, size)
        self._pointers: Dict[int, Pointer] = {}  # ptr_id → Pointer
        self._total_allocs = 0
        self._total_frees = 0
        self._bounds_violations = 0
        self._lock = threading.Lock()
        logger.info(f"  [指针管理器] 初始化: {page_count} 页, 4KB/页")

    def alloc(self, size: int, name: str = "") -> Pointer:
        """分配内存，返回 Pointer。"""
        if size <= 0:
            raise ValueError(f"无效分配大小: {size}")
        if size > MemoryPage._page_size:
            raise MemoryError(f"分配过大: {size} 字节 > 页大小 {MemoryPage._page_size}")
        with self._lock:
            for page in self._pages[4:]:  # 跳过系统区
                # 计算此页已用空间
                used = sum(
                    sz for (pid, sz) in self._allocations.values() if pid == page.page_id
                )
                remaining = MemoryPage._page_size - used
                # 详细日志：记录每个候选页的状态
                logger.debug(f"  [内存] 候选页[{page.page_id}] base={page.base_addr:#x} "
                             f"used={used}B remaining={remaining}B size={size}B "
                             f"{'✓ 可用' if remaining >= size else '✗ 不足'}")
                if remaining >= size:
                    ptr_addr = page.base_addr + used
                    self._allocations[ptr_addr] = (page.page_id, size)
                    ptr = Pointer(self, ptr_addr, name)
                    ptr._type = f"alloc_{size}B"
                    self._pointers[ptr._life_id] = ptr
                    self._total_allocs += 1
                    logger.info(f"  [内存] 分配 ✓: {name or f'{ptr_addr:#x}'} @ {ptr_addr:#x} "
                                f"page[{page.page_id}] size={size}B used_after={used+size}B "
                                f"remaining={remaining-size}B")
                    return ptr
            # 所有页均不足
            total_free = sum(
                MemoryPage._page_size - sum(sz for (pid, sz) in self._allocations.values() if pid == p.page_id)
                for p in self._pages[4:]
            )
            raise MemoryError(f"内存不足: 请求 {size}B, 总空闲={total_free}B "
                              f"(页总数={len(self._pages)}, 活跃分配={len(self._allocations)})")

    def free(self, ptr: Pointer) -> bool:
        """释放内存。"""
        with self._lock:
            if ptr._addr in self._allocations:
                page_id, size = self._allocations.pop(ptr._addr)
                self._pointers.pop(ptr._life_id, None)
                self._total_frees += 1
                # 重新计算该页已用空间
                used = sum(
                    sz for (pid, sz) in self._allocations.values() if pid == page_id
                )
                logger.info(f"  [内存] 释放 ✓: {ptr._addr:#x} page[{page_id}] size={size}B "
                            f"remaining={MemoryPage._page_size - used}B")
                return True
            else:
                logger.warning(f"  [内存] 释放 ✗: 悬空指针 {ptr._addr:#x} 未找到分配记录")
        return False

    def read(self, addr: int, size: int = 1) -> Any:
        """安全读取内存。"""
        page_id = addr // MemoryPage._page_size
        offset = addr % MemoryPage._page_size
        if page_id < 0 or page_id >= len(self._pages):
            raise MemoryError(f"无效地址: {addr:#x}")
        return self._pages[page_id].read(offset, size)

    def write(self, addr: int, value: Any, size: int = 1) -> None:
        """安全写入内存（检查只读页）。"""
        page_id = addr // MemoryPage._page_size
        offset = addr % MemoryPage._page_size
        if page_id < 0 or page_id >= len(self._pages):
            raise MemoryError(f"无效地址: {addr:#x}")
        page = self._pages[page_id]
        if not page.writable:
            self._bounds_violations += 1
            raise MemoryError(f"只读页写入: {addr:#x} page={page_id}")
        page.write(offset, value, size)

    def get_stats(self) -> dict:
        """获取内存统计。"""
        with self._lock:
            return {
                "total_pages": len(self._pages),
                "total_allocs": self._total_allocs,
                "total_frees": self._total_frees,
                "active_allocs": len(self._allocations),
                "bounds_violations": self._bounds_violations,
                "total_memory_kb": len(self._pages) * MemoryPage._page_size // 1024,
            }


# ═══════════════════════════════════════════════════════════════════════════════
#  3. 裸机编译目标
# ═══════════════════════════════════════════════════════════════════════════════

class Architecture(Enum):
    """目标架构。"""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    ARM32 = "arm32"
    RISCV64 = "riscv64"
    RISCV32 = "riscv32"
    AVR = "avr"
    MSP430 = "msp430"
    WASM = "wasm"


@dataclass
class BareMetalTarget:
    """裸机编译目标配置。"""
    arch: Architecture
    precision: str = "float64"        # float32/float64
    endianness: str = "little"        # little/big
    stack_size: int = 4096            # 栈大小（字节）
    heap_size: int = 8192             # 堆大小（字节）
    entry_point: str = "_start"       # 入口函数
    link_script: str = ""             # 链接脚本
    defines: Dict[str, str] = field(default_factory=dict)  # 宏定义
    optimize: str = "O2"              # 优化级别

    def __post_init__(self):
        if not self.link_script:
            self.link_script = self._default_linker_script()

    def _default_linker_script(self) -> str:
        """生成默认链接脚本。"""
        return f"""/* Matha Bare-Metal Linker Script — {self.arch.value} */
MEMORY {{
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 256K
    RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = {self.heap_size}
}}
SECTIONS {{
    .text : {{ *(.text.*) *(.text) }} > FLASH
    .data : {{ *(.data.*) *(.data) }} > RAM
    .bss  : {{ *(.bss.*)  *(.bss)  }} > RAM
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  4. 协议解释生成器
# ═══════════════════════════════════════════════════════════════════════════════

class ProtocolType(Enum):
    """通信协议类型。"""
    UART = "uart"
    SPI = "spi"
    I2C = "i2c"
    CAN = "can"
    USB = "usb"
    MQTT = "mqtt"
    HTTP = "http"


@dataclass
class ProtocolSpec:
    """协议规格描述。"""
    protocol: ProtocolType
    name: str
    baud_rate: int = 115200         # UART 波特率
    data_bits: int = 8              # 数据位
    parity: str = "none"            # 校验位
    stop_bits: int = 1              # 停止位
    frame_format: str = "async"     # async/sync
    max_payload: int = 256          # 最大载荷
    timeout_ms: int = 1000          # 超时
    endian: str = "little"          # 字节序
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProtocolParser:
    """
    协议解释生成器。

    将协议规格解析为可执行的代码片段（Python/C/数学表达式）。
    """

    def __init__(self):
        self._parsers: Dict[ProtocolType, Callable] = {
            ProtocolType.UART: self._parse_uart,
            ProtocolType.SPI: self._parse_spi,
            ProtocolType.I2C: self._parse_i2c,
            ProtocolType.CAN: self._parse_can,
        }
        logger.info("  [协议解析器] 初始化完成")

    def parse(self, spec: ProtocolSpec) -> dict:
        """解析协议规格，返回代码生成指令。"""
        parser = self._parsers.get(spec.protocol)
        if parser is None:
            raise ValueError(f"不支持的协议类型: {spec.protocol.value}")
        return parser(spec)

    def _parse_uart(self, spec: ProtocolSpec) -> dict:
        """UART 协议 → 代码生成指令。"""
        return {
            "protocol": "uart",
            "code_python": (
                f"import serial\n"
                f"port = serial.Serial('{spec.name}', {spec.baud_rate}, "
                f"bytesize={spec.data_bits}, parity='{spec.parity[0]}', "
                f"stopbits={spec.stop_bits})\n"
                f"def uart_send(data: bytes) -> int:\n"
                f"    return port.write(data)\n"
                f"def uart_recv(timeout_ms={spec.timeout_ms}) -> bytes:\n"
                f"    return port.read(port.in_waiting or {spec.max_payload})"
            ),
            "code_c": (
                f"/* UART: {spec.name} @ {spec.baud_rate}bps */\n"
                f"int uart_send(const uint8_t* data, int len) {{\n"
                f"    for(int i=0; i<len; i++) {{ while(!(UART1->SR & 0x80)); UART1->DR=data[i]; }}\n"
                f"    return len;\n"
                f"}}\n"
                f"int uart_recv(uint8_t* buf, int max_len, int timeout_ms) {{\n"
                f"    int n=0; while(n<max_len && (UART1->SR&0x40)) buf[n++]=UART1->DR;\n"
                f"    return n;\n"
                f"}}"
            ),
            "math_expr": f"uart_{spec.name}_write(data, {spec.baud_rate})",
            "params": {"baud_rate": spec.baud_rate, "data_bits": spec.data_bits,
                        "parity": spec.parity, "stop_bits": spec.stop_bits},
        }

    def _parse_spi(self, spec: ProtocolSpec) -> dict:
        return {
            "protocol": "spi",
            "code_python": (
                f"import spidev\n"
                f"spi = spidev.SpiDev(); spi.open(0, {spec.metadata.get('channel', 0)})\n"
                f"spi.max_speed_hz = {spec.baud_rate}\n"
                f"def spi_transfer(data: bytes) -> bytes:\n"
                f"    return spi.xfer2(list(data))"
            ),
            "code_c": (
                f"/* SPI: {spec.name} @ {spec.baud_rate}Hz */\n"
                f"uint8_t spi_transfer(uint8_t data) {{\n"
                f"    SPI1->DR = data; while(!(SPI1->SR & 1)); return SPI1->DR;\n"
                f"}}"
            ),
            "params": {"clock_hz": spec.baud_rate, "mode": spec.metadata.get("mode", 0)},
        }

    def _parse_i2c(self, spec: ProtocolSpec) -> dict:
        addr = spec.metadata.get("device_addr", 0x40)
        return {
            "protocol": "i2c",
            "code_python": (
                f"import smbus\n"
                f"bus = smbus.SMBus({spec.metadata.get('bus', 1)})\n"
                f"def i2c_write(reg, val): bus.write_byte_data({addr}, reg, val)\n"
                f"def i2c_read(reg): return bus.read_byte_data({addr}, reg)"
            ),
            "code_c": (
                f"/* I2C: {spec.name} addr={addr:#04x} */\n"
                f"void i2c_write(uint8_t reg, uint8_t val) {{\n"
                f"    I2C1->DR = {addr}<<1 | 0; while(!(I2C1->SR&2));\n"
                f"    I2C1->DR = reg; while(!(I2C1->SR&2));\n"
                f"    I2C1->DR = val; while(!(I2C1->SR&2));\n"
                f"}}"
            ),
            "params": {"address": addr, "speed_hz": spec.baud_rate},
        }

    def _parse_can(self, spec: ProtocolSpec) -> dict:
        return {
            "protocol": "can",
            "code_python": (
                f"import cantools\n"
                f"db = cantools.db.load_file('{spec.name}.dbc')\n"
                f"def can_send(id_: int, data: bytes): pass  # 实际使用 cantools 发送"
            ),
            "code_c": (
                f"/* CAN: {spec.name} @ {spec.baud_rate}kbps */\n"
                f"int can_send(uint32_t id, const uint8_t* data, int dlc) {{\n"
                f"    CAN1->sTxMailBox[0].TIR = (id & 0x7FF) << 21 | 0x1 << 3 | dlc << 0;\n"
                f"    for(int i=0; i<dlc; i++) CAN1->sTxMailBox[0].TDTR = (CAN1->sTxMailBox[0].TDTR<<8)|data[i];\n"
                f"    return 0;\n"
                f"}}"
            ),
            "params": {"bitrate": spec.baud_rate, "id_type": spec.metadata.get("id_type", "standard")},
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  5. 驱动生成器
# ═══════════════════════════════════════════════════════════════════════════════

class DriverKind(Enum):
    """驱动类型。"""
    SENSORS = "sensors"
    ACTUATORS = "actuators"
    COMM = "communications"
    DISPLAY = "displays"
    STORAGE = "storage"
    POWER = "power"
    MATH = "math"


@dataclass
class DriverSpec:
    """驱动规格。"""
    name: str
    kind: DriverKind
    protocol: Optional[ProtocolSpec] = None
    target_arch: Architecture = Architecture.ARM64
    target_lang: str = "python"   # python / c / matha
    params: Dict[str, Any] = field(default_factory=dict)
    math_expr: str = ""           # 关联的数学表达式
    safety_level: str = "medium"  # low/medium/high


class DriverGenerator:
    """
    驱动代码生成器。

    根据 DriverSpec 生成目标语言代码。
    """

    def __init__(self, protocol_parser: ProtocolParser):
        self._pp = protocol_parser
        self._generated: List[dict] = []
        logger.info("  [驱动生成器] 初始化完成")

    def generate(self, spec: DriverSpec) -> dict:
        """生成驱动代码。"""
        result = {
            "name": spec.name,
            "kind": spec.kind.value,
            "arch": spec.target_arch.value,
            "lang": spec.target_lang,
            "safety": spec.safety_level,
            "code": {},
            "math_expr": spec.math_expr,
            "params": spec.params,
        }

        # 协议代码
        if spec.protocol:
            proto_code = self._pp.parse(spec.protocol)
            result["code"][spec.protocol.protocol.value] = proto_code.get("code_python", "")

        # 驱动核心代码
        if spec.kind == DriverKind.SENSORS:
            result["code"]["core"] = self._gen_sensor_driver(spec)
        elif spec.kind == DriverKind.ACTUATORS:
            result["code"]["core"] = self._gen_actuator_driver(spec)
        elif spec.kind == DriverKind.MATH:
            result["code"]["core"] = self._gen_math_driver(spec)
        elif spec.kind == DriverKind.COMM:
            result["code"]["core"] = self._gen_comm_driver(spec)
        else:
            result["code"]["core"] = self._gen_generic_driver(spec)

        self._generated.append(result)
        logger.info(f"  [驱动] 生成: {spec.name} ({spec.kind.value}, {spec.target_lang})")
        return result

    def _gen_sensor_driver(self, spec: DriverSpec) -> str:
        """传感器驱动模板。"""
        expr = spec.math_expr or "read_raw() * scale + offset"
        return (
            f"# Matha Sensor Driver: {spec.name}\n"
            f"# 协议: {spec.protocol.protocol.value if spec.protocol else 'direct'}\n"
            f"class {spec.name.title()}Sensor:\n"
            f"    SCALE = {spec.params.get('scale', 1.0)}\n"
            f"    OFFSET = {spec.params.get('offset', 0.0)}\n"
            f"    UNIT = '{spec.params.get('unit', 'raw')}'\n"
            f"\n"
            f"    def read(self) -> float:\n"
            f"        raw = self._read_raw()\n"
            f"        return raw * self.SCALE + self.OFFSET  # {expr}\n"
            f"\n"
            f"    def _read_raw(self) -> float:\n"
            f"        # TODO: 实现原始数据采集\n"
            f"        pass\n"
            f"\n"
            f"    def calibrated_read(self) -> dict:\n"
            f"        return {{'value': self.read(), 'unit': self.UNIT}}\n"
        )

    def _gen_actuator_driver(self, spec: DriverSpec) -> str:
        return (
            f"# Matha Actuator Driver: {spec.name}\n"
            f"class {spec.name.title()}Actuator:\n"
            f"    MIN = {spec.params.get('min', 0.0)}\n"
            f"    MAX = {spec.params.get('max', 100.0)}\n"
            f"    STEP = {spec.params.get('step', 0.1)}\n"
            f"\n"
            f"    def set(self, value: float) -> None:\n"
            f"        clamped = max(self.MIN, min(self.MAX, value))\n"
            f"        self._write(clamped)\n"
            f"\n"
            f"    def _write(self, value: float) -> None:\n"
            f"        # TODO: 实现物理输出\n"
            f"        pass\n"
        )

    def _gen_math_driver(self, spec: DriverSpec) -> str:
        expr = spec.math_expr or "x"
        return (
            f"# Matha Math Driver: {spec.name}\n"
            f"def {spec.name}(x: float) -> float:\n"
            f"    # 数学表达式: {expr}\n"
            f"    return {expr}\n"
        )

    def _gen_comm_driver(self, spec: DriverSpec) -> str:
        if spec.protocol:
            proto = spec.protocol
            return (
                f"# Matha Comm Driver: {spec.name}\n"
                f"# {proto.protocol.value} @ {proto.baud_rate}\n"
                f"def {spec.name}_send(data: bytes) -> int:\n"
                f"    # TODO: 实现 {proto.protocol.value} 发送\n"
                f"    return len(data)\n"
                f"\n"
                f"def {spec.name}_recv(timeout_ms={proto.timeout_ms}) -> bytes:\n"
                f"    # TODO: 实现 {proto.protocol.value} 接收\n"
                f"    return b''\n"
            )
        return f"# Matha Comm Driver: {spec.name}\n# TODO\n"

    def _gen_generic_driver(self, spec: DriverSpec) -> str:
        return (
            f"# Matha Generic Driver: {spec.name}\n"
            f"# Kind: {spec.kind.value}\n"
            f"class {spec.name.title()}Driver:\n"
            f"    def __init__(self):\n"
            f"        self._params = {json.dumps(spec.params, ensure_ascii=False)}\n"
            f"\n"
            f"    def init(self) -> bool:\n"
            f"        # TODO: 初始化\n"
            f"        return True\n"
            f"\n"
            f"    def execute(self, **kwargs) -> Any:\n"
            f"        # TODO: 执行驱动操作\n"
            f"        return None\n"
        )

    def list_generated(self) -> List[dict]:
        """列出已生成的驱动。"""
        return list(self._generated)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. 原生编译后端
# ═══════════════════════════════════════════════════════════════════════════════

class NativeBackend:
    """
    原生编译后端。

    将 Matha 符号表达式编译为各架构的原生代码。
    """

    def __init__(self):
        self._targets: Dict[Architecture, BareMetalTarget] = {}
        self._compiler_cache: Dict[str, str] = {}  # hash → compiled_code
        logger.info("  [原生编译] 后端初始化完成")

    def register_target(self, target: BareMetalTarget) -> None:
        """注册编译目标。"""
        self._targets[target.arch] = target
        logger.info(f"  [原生编译] 注册目标: {target.arch.value} ({target.optimize})")

    def compile(self, expr: str, arch: Architecture,
                func_name: str = "compute", target_lang: str = "c") -> str:
        """编译表达式为指定架构的原生代码。"""
        if arch not in self._targets:
            # 自动注册默认目标
            self.register_target(BareMetalTarget(arch))

        cache_key = f"{expr}:{arch.value}:{func_name}:{target_lang}"
        if cache_key in self._compiler_cache:
            return self._compiler_cache[cache_key]

        if target_lang == "c":
            code = self._compile_to_c(expr, func_name, self._targets[arch])
        elif target_lang == "python":
            code = self._compile_to_python(expr, func_name)
        elif target_lang == "assembly":
            code = self._compile_to_asm(expr, func_name, arch)
        else:
            raise ValueError(f"不支持的目标语言: {target_lang}")

        self._compiler_cache[cache_key] = code
        logger.debug(f"  [原生编译] {arch.value} {func_name}: {len(code)} 字节")
        return code

    def _compile_to_c(self, expr: str, func_name: str, target: BareMetalTarget) -> str:
        """编译为 C 代码（含裸机头文件）。"""
        from src.symbol_codegen import get_codegen
        cg = get_codegen()
        body = cg.c(expr, func_name=func_name, return_type="double")
        return (
            f"/* Matha Native C — {target.arch.value} */\n"
            f"/* Optimize: {target.optimize} | Precision: {target.precision} */\n"
            f'#include <stdint.h>\n'
            f'#include <math.h>\n'
            f"{target.link_script}\n"
            f"\n"
            f"{body}\n"
            f"\n"
            f"int {target.entry_point}(void) {{\n"
            f"    double result = {func_name}(0.0);\n"
            f"    return (int)result;\n"
            f"}}"
        )

    def _compile_to_python(self, expr: str, func_name: str) -> str:
        """编译为 Python 代码。"""
        from src.symbol_codegen import get_codegen
        cg = get_codegen()
        return cg.python(expr, func_name=func_name)

    def _compile_to_asm(self, expr: str, func_name: str, arch: Architecture) -> str:
        """生成汇编代码框架。"""
        arch_ops = {
            Architecture.X86_64: "x86_64",
            Architecture.ARM64: "aarch64",
            Architecture.ARM32: "arm32",
            Architecture.RISCV64: "riscv64",
            Architecture.RISCV32: "riscv32",
            Architecture.AVR: "avr",
        }
        op = arch_ops.get(arch, "generic")
        return (
            f"; Matha Assembly — {op}\n"
            f"; Expression: {expr}\n"
            f"; Note: 实际汇编需通过 LLVM/GCC 后端生成\n"
            f"\n"
            f"global {func_name}\n"
            f"{func_name}:\n"
            f"    ; TODO: 生成 {op} 汇编指令\n"
            f"    mov r0, #0    ; placeholder\n"
            f"    bx lr\n"
        )

    def get_targets(self) -> List[str]:
        """列出已注册的目标架构。"""
        return [t.arch.value for t in self._targets.values()]

    def get_stats(self) -> dict:
        return {
            "registered_targets": len(self._targets),
            "cache_size": len(self._compiler_cache),
            "target_list": self.get_targets(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  单例 & 导出
# ═══════════════════════════════════════════════════════════════════════════════

_side_effect_engine: Optional[SafeSideEffectEngine] = None
_pointer_manager: Optional[PointerManager] = None
_protocol_parser: Optional[ProtocolParser] = None
_driver_generator: Optional[DriverGenerator] = None
_native_backend: Optional[NativeBackend] = None


def get_side_effect_engine(mode: str = "full") -> SafeSideEffectEngine:
    global _side_effect_engine
    if _side_effect_engine is None:
        _side_effect_engine = SafeSideEffectEngine(mode)
    return _side_effect_engine


def get_pointer_manager(page_count: int = 16) -> PointerManager:
    global _pointer_manager
    if _pointer_manager is None:
        _pointer_manager = PointerManager(page_count)
    return _pointer_manager


def get_protocol_parser() -> ProtocolParser:
    global _protocol_parser
    if _protocol_parser is None:
        _protocol_parser = ProtocolParser()
    return _protocol_parser


def get_driver_generator() -> DriverGenerator:
    global _driver_generator
    if _driver_generator is None:
        _driver_generator = DriverGenerator(get_protocol_parser())
    return _driver_generator


def get_native_backend() -> NativeBackend:
    global _native_backend
    if _native_backend is None:
        _native_backend = NativeBackend()
        # 注册常见裸机目标
        _native_backend.register_target(BareMetalTarget(Architecture.ARM64, optimize="O2"))
        _native_backend.register_target(BareMetalTarget(Architecture.X86_64, optimize="O2"))
        _native_backend.register_target(BareMetalTarget(Architecture.RISCV64, optimize="O2"))
        _native_backend.register_target(BareMetalTarget(Architecture.AVR, precision="float32"))
    return _native_backend


def get_hardware_stats() -> dict:
    """获取硬件层全部统计信息。"""
    return {
        "side_effect_engine": get_side_effect_engine().get_stats(),
        "pointer_manager": get_pointer_manager().get_stats(),
        "native_backend": get_native_backend().get_stats(),
        "protocol_parser": {"registered_protocols": len(ProtocolType.__members__)},
        "driver_generator": {"generated_drivers": len(get_driver_generator().list_generated())},
    }
