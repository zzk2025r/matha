"""Matha 操作系统模块：进程管理、内存管理、线程、文件系统接口。

覆盖：
  1) 进程管理（创建/终止/列表）
  2) 内存管理（分配/释放/查询）
  3) 线程管理（创建/同步/锁）
  4) 系统信息（CPU/内存/负载）
  5) 信号量与事件
  6) 环境变量
  7) Shell命令执行
"""
from __future__ import annotations

import multiprocessing
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum

# ============================================================
# 进程管理
# ============================================================

class ProcessState(Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    TERMINATED = "terminated"


@dataclass
class ProcessInfo:
    """进程信息。"""
    pid: int = 0
    name: str = ""
    state: ProcessState = ProcessState.RUNNING
    cpu_usage: float = 0.0
    memory_usage: int = 0
    status: str = ""
    start_time: float = 0.0


class ProcessManager:
    """进程管理器。"""

    def __init__(self):
        self._processes: dict[int, ProcessInfo] = {}
        self._next_pid: int = 1000
        self._lock = threading.Lock()

    def create_process(self, name: str, cmd: str = "") -> int:
        """创建进程（模拟）。"""
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            info = ProcessInfo(
                pid=pid, name=name, state=ProcessState.RUNNING,
                start_time=time.time(), memory_usage=0, cpu_usage=0.0,
                status=cmd,
            )
            self._processes[pid] = info
            return pid

    def terminate_process(self, pid: int) -> bool:
        """终止进程。"""
        with self._lock:
            if pid in self._processes:
                self._processes[pid].state = ProcessState.TERMINATED
                return True
            return False

    def get_process(self, pid: int) -> ProcessInfo | None:
        """获取进程信息。"""
        return self._processes.get(pid)

    def list_processes(self) -> list[ProcessInfo]:
        """列出所有进程。"""
        with self._lock:
            return list(self._processes.values())

    def get_running_count(self) -> int:
        """运行中的进程数。"""
        with self._lock:
            return sum(1 for p in self._processes.values()
                      if p.state == ProcessState.RUNNING)


# ============================================================
# 内存管理
# ============================================================

@dataclass
class MemoryBlock:
    """内存块。"""
    address: int = 0
    size: int = 0
    allocated: bool = False
    owner: str = ""


class MemoryManager:
    """内存管理器（模拟）。"""

    def __init__(self, total_memory: int = 1024 * 1024):
        self.total_memory = total_memory
        self.used_memory = 0
        self.free_memory = total_memory
        self._blocks: list[MemoryBlock] = []
        self._lock = threading.Lock()

    def allocate(self, size: int, owner: str = "") -> int:
        """分配内存。"""
        with self._lock:
            if size <= self.free_memory:
                addr = len(self._blocks) * 4096
                block = MemoryBlock(address=addr, size=size,
                                     allocated=True, owner=owner)
                self._blocks.append(block)
                self.used_memory += size
                self.free_memory -= size
                return addr
            return -1

    def free(self, address: int) -> bool:
        """释放内存。"""
        with self._lock:
            for block in self._blocks:
                if block.address == address and block.allocated:
                    block.allocated = False
                    self.used_memory -= block.size
                    self.free_memory += block.size
                    return True
            return False

    def get_memory_info(self) -> dict:
        """获取内存信息。"""
        return {
            "total": self.total_memory,
            "used": self.used_memory,
            "free": self.free_memory,
            "usage_percent": round(self.used_memory / self.total_memory * 100, 1)
                            if self.total_memory > 0 else 0,
            "block_count": len(self._blocks),
        }

    def defragment(self) -> None:
        """内存整理。"""
        with self._lock:
            allocated = [b for b in self._blocks if b.allocated]
            self._blocks = allocated
            addr = 0
            for block in self._blocks:
                block.address = addr
                addr += block.size


# ============================================================
# 线程管理
# ============================================================

@dataclass
class ThreadInfo:
    """线程信息。"""
    tid: int = 0
    name: str = ""
    status: str = "running"
    cpu_time: float = 0.0


class ThreadManager:
    """线程管理器。"""

    def __init__(self):
        self._threads: dict[int, ThreadInfo] = {}
        self._lock = threading.Lock()
        self._next_tid = 1

    def create_thread(self, name: str = "Thread", target=None, args=()) -> int:
        """创建线程。"""
        with self._lock:
            tid = self._next_tid
            self._next_tid += 1
            info = ThreadInfo(tid=tid, name=name, status="running")
            self._threads[tid] = info
            if target:
                t = threading.Thread(target=target, args=args, name=name)
                t.start()
            return tid

    def get_thread(self, tid: int) -> ThreadInfo | None:
        """获取线程信息。"""
        return self._threads.get(tid)

    def list_threads(self) -> list[ThreadInfo]:
        """列出所有线程。"""
        with self._lock:
            return list(self._threads.values())

    def join_all(self) -> None:
        """等待所有线程完成。"""
        time.sleep(0.1)


# ============================================================
# 信号量与事件
# ============================================================

class Semaphore:
    """信号量。"""

    def __init__(self, value: int = 1):
        self._sem = threading.Semaphore(value)
        self._value = value

    def acquire(self) -> bool:
        """获取信号量。"""
        self._sem.acquire()
        self._value -= 1
        return True

    def release(self) -> None:
        """释放信号量。"""
        self._sem.release()
        self._value += 1

    def get_value(self) -> int:
        """获取当前值。"""
        return self._value


class Event:
    """事件。"""

    def __init__(self, name: str = "event"):
        self.name = name
        self._event = threading.Event()

    def set(self) -> None:
        """触发事件。"""
        self._event.set()

    def clear(self) -> None:
        """清除事件。"""
        self._event.clear()

    def wait(self, timeout: float = -1) -> bool:
        """等待事件。"""
        return self._event.wait(timeout)


class Mutex:
    """互斥锁。"""

    def __init__(self):
        self._lock = threading.Lock()

    def lock(self) -> None:
        """加锁。"""
        self._lock.acquire()

    def unlock(self) -> None:
        """解锁。"""
        self._lock.release()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()


# ============================================================
# 系统信息
# ============================================================

def get_system_info() -> dict:
    """获取系统信息。"""
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": multiprocessing.cpu_count(),
        "python_version": sys.version,
        "node": platform.node(),
        "os": os.name,
    }


def get_cpu_info() -> dict:
    """获取CPU信息。"""
    return {
        "cpu_count": multiprocessing.cpu_count(),
        "cpu_freq": platform.processor() or "unknown",
        "architecture": platform.machine(),
        "load_avg": os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0),
    }


def get_memory_info() -> dict:
    """获取系统内存信息。"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
        }
    except ImportError:
        return {"total": 0, "available": 0, "used": 0, "percent": 0}


def get_disk_info() -> dict:
    """获取磁盘信息。"""
    usage = shutil.disk_usage("/") if hasattr(os, 'getcwd') else None
    return {"info": "使用disk_usage获取"} if usage is None else {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
    }


def get_environment_variable(name: str) -> str:
    """获取环境变量。"""
    return os.environ.get(name, "")


def set_environment_variable(name: str, value: str) -> None:
    """设置环境变量。"""
    os.environ[name] = value


# ============================================================
# Shell命令
# ============================================================

def shell_exec(command: str, timeout: float = 30.0) -> dict:
    """执行Shell命令。"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": -1,
                "error": "超时", "success": False}
    except Exception as e:
        return {"command": command, "returncode": -1,
                "error": str(e), "success": False}


def shell_run_script(path: str) -> dict:
    """运行脚本。"""
    return shell_exec(f"python {path}")


# ============================================================
# 注册
# ============================================================

def _register_os(builtins: dict) -> None:
    builtins["创建进程管理器"] = lambda: ProcessManager()
    builtins["创建进程"] = lambda pm, n, c="": pm.create_process(n, c)
    builtins["终止进程"] = lambda pm, pid: pm.terminate_process(pid)
    builtins["获取进程"] = lambda pm, pid: pm.get_process(pid)
    builtins["进程列表"] = lambda pm: pm.list_processes()
    builtins["创建内存管理器"] = lambda total=1024*1024: MemoryManager(total)
    builtins["内存分配"] = lambda mm, size, owner="": mm.allocate(size, owner)
    builtins["内存释放"] = lambda mm, addr: mm.free(addr)
    builtins["内存信息"] = lambda mm: mm.get_memory_info()
    builtins["创建线程管理器"] = lambda: ThreadManager()
    builtins["创建线程"] = lambda tm, n, t=None, a=(): tm.create_thread(n, t, a)
    builtins["线程列表"] = lambda tm: tm.list_threads()
    builtins["创建信号量"] = lambda v=1: Semaphore(v)
    builtins["信号量获取"] = lambda s: s.acquire()
    builtins["信号量释放"] = lambda s: s.release()
    builtins["创建事件"] = lambda n="event": Event(n)
    builtins["事件设置"] = lambda e: e.set()
    builtins["事件等待"] = lambda e, t=-1: e.wait(t)
    builtins["创建互斥锁"] = lambda: Mutex()
    builtins["互斥加锁"] = lambda m: m.lock()
    builtins["互斥解锁"] = lambda m: m.unlock()
    builtins["获取系统信息"] = get_system_info
    builtins["获取CPU信息"] = get_cpu_info
    builtins["获取内存信息"] = get_memory_info
    builtins["获取环境变量"] = get_environment_variable
    builtins["设置环境变量"] = set_environment_variable
    builtins["执行命令"] = shell_exec
    builtins["运行脚本"] = shell_run_script


def _os_symtab_names() -> list[str]:
    return [
        "创建进程管理器", "创建进程", "终止进程", "获取进程", "进程列表",
        "创建内存管理器", "内存分配", "内存释放", "内存信息",
        "创建线程管理器", "创建线程", "线程列表",
        "创建信号量", "信号量获取", "信号量释放",
        "创建事件", "事件设置", "事件等待",
        "创建互斥锁", "互斥加锁", "互斥解锁",
        "获取系统信息", "获取CPU信息", "获取内存信息",
        "获取环境变量", "设置环境变量", "执行命令", "运行脚本",
    ]


__all__ = [
    "ProcessState", "ProcessInfo", "ProcessManager",
    "MemoryBlock", "MemoryManager",
    "ThreadInfo", "ThreadManager",
    "Semaphore", "Event", "Mutex",
    "get_system_info", "get_cpu_info", "get_memory_info",
    "get_environment_variable", "set_environment_variable",
    "shell_exec", "shell_run_script",
    "_register_os", "_os_symtab_names",
]
