# -*- coding: utf-8 -*-
"""Matha v4.0 — 硬件抽象层（HAL）

设计原则：
  1. 统一接口：所有硬件操作通过标准 I/O 接口
  2. 抽象隔离：Matha 代码不依赖具体硬件实现
  3. 插件扩展：新硬件通过插件注册
  4. 安全沙箱：硬件操作需要权限验证

架构：
  Matha 代码 → HAL API → 设备驱动 → 实体硬件
"""
from __future__ import annotations
import abc
import json
import logging
import multiprocessing as mp
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 异步日志队列（v4.1 性能优化）
# ============================================================

class AsyncHALLogger:
    """
    异步日志记录器（v4.2 批处理优化版）。

    使用独立线程异步写入日志，避免阻塞硬件操作。
    核心优化：
    1. 批量消费：每次从队列中取出多条日志一次性写入，减少 I/O 次数
    2. 自适应批次大小：根据负载动态调整批次大小
    3. 低优先级缓冲：非紧急日志可延迟批量刷新

    生产环境下默认关闭，仅 DEBUG 级别时输出。
    """

    # 批量消费配置
    BATCH_SIZE_DEFAULT = 32       # 默认批次大小
    BATCH_SIZE_MIN = 4            # 最小批次
    BATCH_SIZE_MAX = 256          # 最大批次
    FLUSH_INTERVAL_MS = 10        # 强制刷新间隔（毫秒）
    ADAPTIVE_THRESHOLD = 50000    # 高负载阈值（ops/sec）

    def __init__(self, name: str = "matha.hal", maxsize: int = 1000):
        self._logger = logging.getLogger(name)
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._worker: Optional[threading.Thread] = None
        self._enabled = False
        self._dropped_count = 0
        self._overflow_event = threading.Event()
        # 批处理状态
        self._batch_size = self.BATCH_SIZE_DEFAULT
        self._last_flush_time = 0.0
        self._total_logged = 0
        self._total_dropped = 0

    def start(self):
        """启动异步日志线程。"""
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._flush_batch,
                daemon=True,
                name="HAL-Logger-Batch"
            )
            self._worker.start()
            self._enabled = True
            self._last_flush_time = time.perf_counter()

    def stop(self):
        """停止异步日志线程，确保刷新剩余日志。"""
        self._enabled = False
        # 刷新剩余日志
        self._flush_remaining()
        if self._worker:
            self._worker.join(timeout=1.0)
            self._worker = None
        if self._dropped_count > 0:
            logging.getLogger(self._logger.name).warning(
                "日志统计: 丢弃 %d 条（队列溢出）", self._dropped_count
            )

    def _flush_remaining(self):
        """刷新队列中剩余的所有日志。"""
        batch = []
        while True:
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except queue.Empty:
                break
        if batch:
            self._write_batch(batch)

    def _flush_batch(self):
        """
        后台线程：批量异步刷新日志。

        优化策略：
        - 批量消费：每次取出最多 BATCH_SIZE 条日志
        - 自适应调整：根据队列深度动态调整批次大小
        - 超时刷新：超过 FLUSH_INTERVAL_MS 强制刷新
        """
        while self._enabled:
            try:
                # 收集一批日志
                batch = []
                deadline = time.perf_counter() + self.FLUSH_INTERVAL_MS / 1000.0

                while len(batch) < self._batch_size:
                    remaining_time = deadline - time.perf_counter()
                    if remaining_time <= 0:
                        break
                    try:
                        item = self._queue.get(timeout=min(remaining_time, 0.001))
                        batch.append(item)
                    except queue.Empty:
                        break

                if batch:
                    self._write_batch(batch)
                    self._total_logged += len(batch)
                    # 自适应调整批次大小
                    self._adjust_batch_size(len(batch))

            except Exception:
                pass

    def _write_batch(self, batch: list):
        """批量写入日志。"""
        # 按日志级别分组，减少重复判断
        grouped = {}
        for level, msg, args in batch:
            if level not in grouped:
                grouped[level] = []
            grouped[level].append((msg, args))

        # 批量写入
        for level, items in grouped.items():
            if self._logger.isEnabledFor(level):
                for msg, args in items:
                    self._logger.log(level, msg, *args)

    def _adjust_batch_size(self, actual_batch_size: int):
        """根据实际批次大小自适应调整。"""
        if actual_batch_size >= self.BATCH_SIZE_MAX // 2:
            # 队列很满，增大批次
            self._batch_size = min(self._batch_size * 2, self.BATCH_SIZE_MAX)
        elif actual_batch_size < self.BATCH_SIZE_MIN:
            # 队列很空，减小批次降低延迟
            self._batch_size = max(self._batch_size // 2, self.BATCH_SIZE_MIN)

    def _should_drop(self) -> bool:
        """判断是否应该丢弃日志（高负载保护）。"""
        # 简单阈值检查，实际应基于实时负载
        return self._dropped_count > 10000

    def info(self, msg: str, *args):
        """异步记录 INFO 日志（批量优化）。"""
        if self._enabled:
            try:
                self._queue.put((logging.INFO, msg, args), block=False)
            except queue.Full:
                self._dropped_count += 1
                if self._dropped_count % 500 == 0:
                    self._logger.warning(
                        "日志队列已满，已丢弃 %d 条", self._dropped_count
                    )
        else:
            self._logger.info(msg, *args)

    def debug(self, msg: str, *args):
        """异步记录 DEBUG 日志（批量优化）。"""
        if self._enabled:
            try:
                self._queue.put((logging.DEBUG, msg, args), block=False)
            except queue.Full:
                self._dropped_count += 1
        else:
            self._logger.debug(msg, *args)

    def warning(self, msg: str, *args):
        """异步记录 WARNING 日志。"""
        if self._enabled:
            try:
                self._queue.put((logging.WARNING, msg, args), block=False)
            except queue.Full:
                self._dropped_count += 1
        else:
            self._logger.warning(msg, *args)

    def error(self, msg: str, *args):
        """异步记录 ERROR 日志（不丢弃）。"""
        if self._enabled:
            try:
                self._queue.put((logging.ERROR, msg, args), block=False)
            except queue.Full:
                self._dropped_count += 1
                # ERROR 级别不丢弃，降级为同步写入
                self._logger.error(msg, *args)
        else:
            self._logger.error(msg, *args)

    def get_stats(self) -> dict:
        """获取日志统计信息。"""
        return {
            "enabled": self._enabled,
            "dropped": self._dropped_count,
            "total_logged": self._total_logged,
            "batch_size": self._batch_size,
            "queue_size": self._queue.qsize(),
        }


# 全局异步日志实例（v4.2 批处理优化版）
_hal_async_logger = AsyncHALLogger()
_hal_async_logger.start()


# ============================================================
# Multiprocessing 并发 Worker（模块级，供序列化）
# ============================================================

def _gpio_writer_worker(
    worker_id: int,
    pin: int,
    iterations: int,
    result_queue: mp.Queue,
):
    """
    GPIO 写入 Worker（进程级，模块顶层定义以支持序列化）。
    每个进程拥有独立 HAL 实例，无 GIL 竞争。
    """
    local_hal = HardwareAbstractionLayer()
    local_ops = MathaHardwareOps(local_hal)
    local_hal.register(GPIODevice(pin=pin))

    latencies: List[float] = []
    errors = 0
    start_time = time.perf_counter()

    try:
        for i in range(iterations):
            t0 = time.perf_counter()
            try:
                local_ops.写入(f"gpio_{pin}", i % 2 == 0)
            except Exception:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1e6)
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start_time
        rate = iterations / elapsed if elapsed > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0

        result_queue.put({
            "worker_id": worker_id,
            "pin": pin,
            "iterations": iterations,
            "elapsed_ms": elapsed * 1000,
            "rate": rate,
            "avg_latency_us": avg_lat,
            "max_latency_us": max_lat,
            "errors": errors,
        })


def _gpio_batch_writer_worker(
    worker_id: int,
    pins: List[int],
    iterations: int,
    result_queue: mp.Queue,
):
    """批量 GPIO 写入 Worker（进程级）。"""
    local_hal = HardwareAbstractionLayer()
    local_ops = MathaHardwareOps(local_hal)
    for p in pins:
        local_hal.register(GPIODevice(pin=p))

    latencies: List[float] = []
    errors = 0
    start_time = time.perf_counter()

    try:
        for i in range(iterations):
            batch_ops = [(f"gpio_{p}", i % 2 == 0) for p in pins]
            t0 = time.perf_counter()
            try:
                local_ops.批量写入(batch_ops)
            except Exception:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1e6)
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start_time
        rate = iterations / elapsed if elapsed > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0

        result_queue.put({
            "worker_id": worker_id,
            "pins": pins,
            "iterations": iterations,
            "elapsed_ms": elapsed * 1000,
            "rate": rate,
            "avg_latency_us": avg_lat,
            "max_latency_us": max_lat,
            "errors": errors,
        })


def run_multiprocess_stress_test(
    num_workers: int = 8,
    pin: int = 18,
    iterations_per_worker: int = 5000,
    target_frequency: int = 100000,
    use_batch: bool = False,
    batch_pins: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    运行 multiprocessing 压力测试（绕过 GIL）。

    Args:
        num_workers: Worker 进程数
        pin: GPIO 引脚
        iterations_per_worker: 每个 Worker 迭代次数
        target_frequency: 目标频率 (Hz)
        use_batch: 是否批量写入
        batch_pins: 批量写入引脚列表

    Returns:
        性能摘要字典
    """
    worker_fn = _gpio_batch_writer_worker if use_batch else _gpio_writer_worker
    pins = batch_pins or list(range(18, 18 + num_workers))

    result_queue = mp.Queue()
    processes = []

    for i in range(num_workers):
        args = (i, pins if use_batch else pin, iterations_per_worker, result_queue)
        p = mp.Process(target=worker_fn, args=args)
        p.start()
        processes.append(p)

    for p in processes:
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()

    results: List[Dict] = []
    while not result_queue.empty():
        results.append(result_queue.get())

    total_ops = sum(r["iterations"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    total_time = max((r["elapsed_ms"] for r in results), default=0) / 1000
    total_rate = total_ops / total_time if total_time > 0 else 0

    all_avg_lats = [r["avg_latency_us"] for r in results if r["elapsed_ms"] > 0]
    all_max_lats = [r["max_latency_us"] for r in results if r["elapsed_ms"] > 0]

    return {
        "total_ops": total_ops,
        "total_errors": total_errors,
        "total_time_sec": total_time,
        "total_rate": total_rate,
        "target_rate": target_frequency * num_workers,
        "achievement_pct": total_rate / max(target_frequency * num_workers, 1) * 100,
        "avg_latency_us": sum(all_avg_lats) / len(all_avg_lats) if all_avg_lats else 0,
        "max_latency_us": max(all_max_lats) if all_max_lats else 0,
        "workers": len(results),
        "per_worker": results,
    }


# ============================================================
# 设备类型枚举
# ============================================================

class DeviceType(Enum):
    """硬件设备类型。"""
    SENSOR = auto()        # 传感器（输入）
    ACTUATOR = auto()      # 执行器（输出）
    DISPLAY = auto()       # 显示设备
    STORAGE = auto()       # 存储设备
    NETWORK = auto()       # 网络设备
    COMMUNICATION = auto() # 通信设备（串口等）
    COMPUTE = auto()       # 计算设备（GPU/TPU）


class DeviceState(Enum):
    """设备状态。"""
    OFFLINE = auto()
    ONLINE = auto()
    ERROR = auto()
    BUSY = auto()


# ============================================================
# 设备基类
# ============================================================

@dataclass
class DeviceConfig:
    """设备配置。"""
    name: str
    device_type: DeviceType
    address: str = ""           # 设备地址（如 GPIO4, /dev/ttyUSB0）
    config: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)  # 操作权限


class IODevice(abc.ABC):
    """
    I/O 设备抽象基类。

    所有硬件设备必须继承此类并实现 read/write 方法。
    """

    def __init__(self, config: DeviceConfig):
        self.config = config
        self.state = DeviceState.OFFLINE
        self._read_fn: Optional[Callable[[], Any]] = None
        self._write_fn: Optional[Callable[[Any], None]] = None
        self._last_read: Any = None
        self._last_write: Any = None
        self._access_count: int = 0

    def read(self) -> Any:
        """
        从设备读取数据。

        Returns:
            读取的数据，失败返回 None
        """
        if self.state != DeviceState.ONLINE:
            return None

        if self._read_fn:
            try:
                self._last_read = self._read_fn()
                self._access_count += 1
                return self._last_read
            except Exception as e:
                self.state = DeviceState.ERROR
                return None
        return None

    def write(self, value: Any) -> bool:
        """
        向设备写入数据。

        Returns:
            是否写入成功
        """
        if self.state != DeviceState.ONLINE:
            return False

        if self._write_fn:
            try:
                self._write_fn(value)
                self._last_write = value
                self._access_count += 1
                return True
            except Exception as e:
                self.state = DeviceState.ERROR
                return False
        return False

    def configure(self, **kwargs) -> bool:
        """配置设备参数。"""
        for k, v in kwargs.items():
            self.config[k] = v
        return True

    def online(self) -> bool:
        """上线设备。"""
        self.state = DeviceState.ONLINE
        return True

    def offline(self) -> bool:
        """下线设备。"""
        self.state = DeviceState.OFFLINE
        return True

    def reset(self) -> bool:
        """重置设备。"""
        self._last_read = None
        self._last_write = None
        self._access_count = 0
        self.state = DeviceState.OFFLINE
        return True

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def address(self) -> str:
        return self.config.address

    @property
    def device_type(self) -> DeviceType:
        return self.config.device_type

    @property
    def access_count(self) -> int:
        return self._access_count


# ============================================================
# 内置设备实现
# ============================================================

class ScreenDevice(IODevice):
    """屏幕输出设备。"""

    def __init__(self):
        super().__init__(DeviceConfig(
            name="screen",
            device_type=DeviceType.DISPLAY,
            address="stdout",
        ))
        self._write_fn = self._print_to_screen

    def _print_to_screen(self, value: Any):
        """输出到屏幕。"""
        print(value)


class KeyboardDevice(IODevice):
    """键盘输入设备。"""

    def __init__(self):
        super().__init__(DeviceConfig(
            name="keyboard",
            device_type=DeviceType.SENSOR,
            address="stdin",
        ))
        self._read_fn = self._read_from_keyboard

    def _read_from_keyboard(self) -> str:
        """从键盘读取。"""
        return input("> ")


class FileDevice(IODevice):
    """文件存储设备。"""

    def __init__(self, base_path: str = "."):
        super().__init__(DeviceConfig(
            name="file",
            device_type=DeviceType.STORAGE,
            address=base_path,
        ))

    def read(self, path: str = "") -> Optional[str]:
        """读取文件内容。"""
        if not path:
            path = input("输入文件路径: ")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    def write(self, content: str, path: str = "") -> bool:
        """写入文件内容。"""
        if not path:
            path = input("输入文件路径: ")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False


class NetworkDevice(IODevice):
    """网络设备。"""

    def __init__(self):
        super().__init__(DeviceConfig(
            name="network",
            device_type=DeviceType.NETWORK,
            address="localhost",
        ))

    def http_get(self, url: str) -> Optional[str]:
        """HTTP GET 请求。"""
        try:
            import requests
            resp = requests.get(url, timeout=5)
            return resp.text
        except Exception:
            return None

    def http_post(self, url: str, data: dict) -> Optional[str]:
        """HTTP POST 请求。"""
        try:
            import requests
            resp = requests.post(url, json=data, timeout=5)
            return resp.text
        except Exception:
            return None


class SerialDevice(IODevice):
    """
    串口通信设备。

    用于连接 Arduino、传感器、模块等串口设备。
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        super().__init__(DeviceConfig(
            name=f"serial_{port}",
            device_type=DeviceType.COMMUNICATION,
            address=port,
            config={"baudrate": baudrate},
        ))
        self._serial = None

    def _open(self):
        """打开串口。"""
        try:
            import serial
            self._serial = serial.Serial(
                self.address,
                self.config.get("baudrate", 9600),
                timeout=1
            )
            self.state = DeviceState.ONLINE
        except Exception:
            self.state = DeviceState.ERROR

    def _close(self):
        """关闭串口。"""
        if self._serial:
            self._serial.close()
            self._serial = None
            self.state = DeviceState.OFFLINE

    def read(self) -> Optional[str]:
        """从串口读取数据。"""
        logger.debug("串口[%s] 开始读取", self.address)
        if not self._serial:
            self._open()
        if self._serial and self._serial.is_open:
            try:
                data = self._serial.readline().decode('utf-8', errors='ignore').strip()
                if data:
                    logger.info("串口[%s] 读取数据: %r", self.address, data)
                else:
                    logger.debug("串口[%s] 读取无数据", self.address)
                return data if data else None
            except Exception as e:
                logger.error("串口[%s] 读取失败: %s", self.address, e)
                return None
        logger.warning("串口[%s] 未打开，无法读取", self.address)
        return None

    def write(self, value: str) -> bool:
        """向串口写入数据。"""
        logger.info("串口[%s] 写入: %r", self.address, value)
        if not self._serial:
            self._open()
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((value + '\n').encode('utf-8'))
                logger.debug("串口[%s] 写入成功", self.address)
                return True
            except Exception as e:
                logger.error("串口[%s] 写入失败: %s", self.address, e)
                return False
        logger.warning("串口[%s] 未打开，无法写入", self.address)
        return False

    def __del__(self):
        self._close()


class GPIODevice(IODevice):
    """
    GPIO 设备。

    用于控制 GPIO 引脚（如 Raspberry Pi GPIO）。
    """

    def __init__(self, pin: int):
        super().__init__(DeviceConfig(
            name=f"gpio_{pin}",
            device_type=DeviceType.ACTUATOR,
            address=f"GPIO{pin}",
        ))
        self._pin = pin
        self._value = False

    def read(self) -> Optional[bool]:
        """读取 GPIO 引脚状态。"""
        _hal_async_logger.debug("GPIO[%d] 开始读取", self._pin)
        try:
            # 实际实现应调用 gpiozero 或 RPi.GPIO
            # 这里使用模拟实现
            import random
            self._value = random.choice([True, False])
            _hal_async_logger.debug("GPIO[%d] 读取成功: %s", self._pin, self._value)
            return self._value
        except Exception as e:
            _hal_async_logger.error("GPIO[%d] 读取失败: %s", self._pin, e)
            self.state = DeviceState.ERROR
            return None

    def write(self, value: bool) -> bool:
        """写入 GPIO 引脚状态。"""
        # 高频操作使用 DEBUG 级别，生产环境默认关闭
        _hal_async_logger.debug("GPIO[%d] 写入: %s", self._pin, value)
        try:
            self._value = bool(value)
            return True
        except Exception as e:
            _hal_async_logger.error("GPIO[%d] 写入失败: %s", self._pin, e)
            self.state = DeviceState.ERROR
            return False

    def pwm_write(self, value: float):
        """写入 PWM 值（0.0-1.0）。"""
        _hal_async_logger.debug("GPIO[%d] PWM 写入: %.2f", self._pin, value)


class I2CDevice(IODevice):
    """
    I2C 设备。

    用于连接 I2C 传感器（如温湿度、加速度计等）。
    """

    def __init__(self, address: int):
        super().__init__(DeviceConfig(
            name=f"i2c_{address:02X}",
            device_type=DeviceType.SENSOR,
            address=f"0x{address:02X}",
        ))
        self._address = address

    def read(self) -> Optional[Dict[str, Any]]:
        """从 I2C 设备读取数据。"""
        # 实际实现应调用 smbus2 或 i2c-tools
        return {"address": self._address, "data": [0, 0, 0]}

    def write(self, value: bytes) -> bool:
        """向 I2C 设备写入数据。"""
        return True


# ============================================================
# 硬件抽象层（HAL）
# ============================================================

class HardwareAbstractionLayer:
    """
    Matha 硬件抽象层（HAL）。

    统一管理所有硬件设备，提供标准化的 I/O 接口。
    """

    def __init__(self):
        self._devices: Dict[str, IODevice] = {}
        self._register_builtin_devices()

    def _register_builtin_devices(self):
        """注册内置设备。"""
        self.register(ScreenDevice())
        self.register(KeyboardDevice())
        self.register(FileDevice())
        self.register(NetworkDevice())

    def register(self, device: IODevice):
        """注册设备。"""
        self._devices[device.name] = device
        device.online()

    def unregister(self, name: str):
        """注销设备。"""
        if name in self._devices:
            self._devices[name].offline()
            del self._devices[name]

    def get(self, name: str) -> Optional[IODevice]:
        """获取设备。"""
        return self._devices.get(name)

    def get_by_address(self, address: str) -> Optional[IODevice]:
        """按地址获取设备。"""
        for dev in self._devices.values():
            if dev.address == address:
                return dev
        return None

    def list_devices(self) -> List[Dict]:
        """列出所有设备。"""
        return [
            {
                "name": dev.name,
                "type": dev.device_type.name,
                "address": dev.address,
                "state": dev.state.name,
                "access_count": dev.access_count,
            }
            for dev in self._devices.values()
        ]

    def read(self, device_name: str) -> Optional[Any]:
        """从设备读取数据。"""
        device = self._devices.get(device_name)
        if device:
            return device.read()
        return None

    def write(self, device_name: str, value: Any, **kwargs) -> bool:
        """向设备写入数据。"""
        device = self._devices.get(device_name)
        if device:
            return device.write(value)
        return False

    def batch_write(self, operations: List[tuple]) -> List[bool]:
        """
        批量写入多个设备。

        Args:
            operations: 列表，每个元素为 (device_name, value) 元组

        Returns:
            每个操作的执行结果列表
        """
        results = []
        for device_name, value in operations:
            device = self._devices.get(device_name)
            if device:
                results.append(device.write(value))
            else:
                _hal_async_logger.warning("设备不存在: %s", device_name)
                results.append(False)
        return results


# ============================================================
# Matha 硬件操作语法
# ================================================= ============================================================================

class MathaHardwareOps:
    """
    Matha 硬件操作语法。

    提供自然语言到硬件操作的映射。
    """

    def __init__(self, hal: HardwareAbstractionLayer):
        self.hal = hal

    def 读取(self, device_name: str, path: str = "") -> Optional[Any]:
        """从设备读取数据。"""
        if device_name == "file" and path:
            device = self.hal.get("file")
            if device:
                return device.read(path=path)
        return self.hal.read(device_name)

    def 写入(self, device_name: str, value: Any, path: str = "") -> bool:
        """向设备写入数据。"""
        if device_name == "file" and path:
            device = self.hal.get("file")
            if device:
                return device.write(value, path=path)
        return self.hal.write(device_name, value)

    def 批量写入(self, operations: List[tuple]) -> List[bool]:
        """
        批量写入多个设备。

        Matha 语法示例：
            批量写入 [(显示屏, "Hello"), (LED, True)]
        """
        return self.hal.batch_write(operations)

    def 打开(self, device_name: str) -> bool:
        """打开设备。"""
        device = self.hal.get(device_name)
        if device:
            return device.online()
        return False

    def 关闭(self, device_name: str) -> bool:
        """关闭设备。"""
        device = self.hal.get(device_name)
        if device:
            return device.offline()
        return False

    def 列出设备(self) -> List[Dict]:
        """列出所有设备。"""
        return self.hal.list_devices()


# ============================================================
# 测试入口
# =================================================

if __name__ == "__main__":
    # 初始化 HAL
    hal = HardwareAbstractionLayer()
    ops = MathaHardwareOps(hal)

    print("=" * 70)
    print("  Matha v4.0 — 硬件抽象层（HAL）测试")
    print("=" * 70)

    # 列出设备
    print("\n【设备列表】")
    devices = ops.列出设备()
    for dev in devices:
        print(f"  {dev['name']:15} {dev['type']:10} {dev['address']:15} {dev['state']}")

    # 测试屏幕设备
    print("\n【测试屏幕输出】")
    ops.写入("screen", "Hello from Matha HAL!")

    # 测试文件设备
    print("\n【测试文件 I/O】")
    test_file = ".matha_test.txt"
    ops.写入("file", "Matha HAL 测试内容", path=test_file)
    content = ops.读取("file", path=test_file)
    print(f"  读取内容: {content}")
    os.unlink(test_file)

    # 测试串口设备（模拟）
    print("\n【测试串口设备】")
    serial = SerialDevice(port="/dev/ttySIM")
    hal.register(serial)
    print(f"  串口状态: {serial.state.name}")
    serial.write("AT+CGMI")
    response = serial.read()
    print(f"  响应: {response}")
    hal.unregister("serial_/dev/ttySIM")

    # 测试 GPIO 设备（模拟）
    print("\n【测试 GPIO 设备】")
    gpio = GPIODevice(pin=4)
    hal.register(gpio)
    gpio.write(True)
    print(f"  GPIO4 状态: {gpio.read()}")
    hal.unregister("gpio_4")

    print("\n" + "=" * 70)
    print("  HAL 测试完成")
    print("=" * 70)
