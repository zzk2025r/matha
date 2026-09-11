# -*- coding: utf-8 -*-
"""设备性能检测与自适应线程配置。

根据本机 CPU 核心数、内存大小、平台类型，自动计算合适的
线程数 / 进程数，避免在低端设备上过度并行导致资源争用，
或在高端设备上并行不足浪费算力。

使用方式：
    from src.device_config import DeviceConfig
    cfg = DeviceConfig.detect()
    print(cfg)                       # 查看检测结果
    n = cfg.process_workers          # 推荐进程数
    t = cfg.thread_workers           # 推荐线程数
    cfg.apply_to_environ()           # 写入环境变量供其他模块读取

环境变量覆盖（优先级高于自动检测）：
    MATHA_CPU_CORES        - 指定逻辑核心数
    MATHA_PROCESS_WORKERS  - 指定进程数
    MATHA_THREAD_WORKERS   - 指定线程数
    MATHA_MAX_WORKERS      - 指定最大工作进程数（用于进程池）
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass
class DeviceConfig:
    """设备性能配置。"""

    cpu_cores: int            # 逻辑 CPU 核心数
    physical_cores: int       # 物理核心数（若可获取）
    total_memory_mb: int      # 总内存 MB（若可获取）
    platform: str             # 操作系统
    arch: str                 # 架构

    # 推荐的并行度
    process_workers: int      # 进程池大小（绕过 GIL，用于 CPU 密集）
    thread_workers: int       # 线程池大小（用于 IO 密集）
    max_workers: int          # 综合最大工作数

    @staticmethod
    def detect() -> "DeviceConfig":
        """自动检测设备性能并计算推荐配置。"""
        cpu_cores = max(1, os.cpu_count() or 1)

        # 物理核心数检测（尽力而为）
        physical_cores = cpu_cores
        try:
            if platform.system() == "Windows":
                import subprocess
                out = subprocess.run(
                    ["wmic", "cpu", "get", "NumberOfCores"],
                    capture_output=True, text=True, timeout=5,
                ).stdout
                nums = [int(x) for x in out.split() if x.isdigit()]
                if nums:
                    physical_cores = sum(nums)
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    physical_cores = len({
                        line.split(":")[1].strip()
                        for line in f if line.startswith("physical id")
                    }) or cpu_cores
        except Exception:
            physical_cores = cpu_cores

        # 内存检测
        total_memory_mb = 0
        try:
            import psutil
            total_memory_mb = psutil.virtual_memory().total // (1024 * 1024)
        except ImportError:
            try:
                if platform.system() == "Windows":
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    total_memory_mb = stat.ullTotalPhys // (1024 * 1024)
            except Exception:
                total_memory_mb = 0

        plat = platform.system()
        arch = platform.machine()

        # —— 计算推荐并行度 ——
        # 进程数：CPU 密集型任务，建议 = 物理核心数（留 1 核给系统）
        # 低端设备（≤2 核）只开 1 个进程，避免上下文切换开销
        if physical_cores <= 2:
            process_workers = 1
        elif physical_cores <= 4:
            process_workers = max(1, physical_cores - 1)
        else:
            process_workers = max(2, physical_cores - 1)

        # 线程数：IO 密集型任务，可开更多
        # 小内存设备（< 2GB）限制线程数避免 OOM
        if total_memory_mb > 0 and total_memory_mb < 2048:
            thread_workers = max(2, cpu_cores * 2)
        else:
            thread_workers = max(4, cpu_cores * 4)

        max_workers = process_workers

        # 环境变量覆盖
        if os.environ.get("MATHA_CPU_CORES"):
            try:
                cpu_cores = max(1, int(os.environ["MATHA_CPU_CORES"]))
            except ValueError:
                pass
        if os.environ.get("MATHA_PROCESS_WORKERS"):
            try:
                process_workers = max(1, int(os.environ["MATHA_PROCESS_WORKERS"]))
            except ValueError:
                pass
        if os.environ.get("MATHA_THREAD_WORKERS"):
            try:
                thread_workers = max(1, int(os.environ["MATHA_THREAD_WORKERS"]))
            except ValueError:
                pass
        if os.environ.get("MATHA_MAX_WORKERS"):
            try:
                max_workers = max(1, int(os.environ["MATHA_MAX_WORKERS"]))
            except ValueError:
                pass

        return DeviceConfig(
            cpu_cores=cpu_cores,
            physical_cores=physical_cores,
            total_memory_mb=total_memory_mb,
            platform=plat,
            arch=arch,
            process_workers=process_workers,
            thread_workers=thread_workers,
            max_workers=max_workers,
        )

    def apply_to_environ(self) -> None:
        """将推荐配置写入环境变量，供其他模块读取。"""
        os.environ.setdefault("MATHA_CPU_CORES", str(self.cpu_cores))
        os.environ.setdefault("MATHA_PROCESS_WORKERS", str(self.process_workers))
        os.environ.setdefault("MATHA_THREAD_WORKERS", str(self.thread_workers))
        os.environ.setdefault("MATHA_MAX_WORKERS", str(self.max_workers))

    def summary(self) -> str:
        """返回人类可读的配置摘要。"""
        mem = f"{self.total_memory_mb} MB" if self.total_memory_mb else "未知"
        return (
            f"设备: {self.platform} {self.arch} | "
            f"CPU: {self.cpu_cores} 逻辑核 / {self.physical_cores} 物理核 | "
            f"内存: {mem}\n"
            f"推荐: 进程数={self.process_workers}, 线程数={self.thread_workers}, "
            f"最大工作数={self.max_workers}"
        )

    def __str__(self) -> str:
        return self.summary()


# 模块级单例：首次导入时检测一次
_CONFIG: DeviceConfig | None = None


def get_config() -> DeviceConfig:
    """获取设备配置单例（惰性初始化）。"""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = DeviceConfig.detect()
    return _CONFIG


def auto_tune() -> DeviceConfig:
    """检测设备性能并应用配置到环境变量。"""
    cfg = DeviceConfig.detect()
    cfg.apply_to_environ()
    return cfg


if __name__ == "__main__":
    cfg = DeviceConfig.detect()
    print(cfg.summary())
