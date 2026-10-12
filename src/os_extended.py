"""Matha 操作系统扩展：进程管理、信号、IPC、虚拟内存。"""
from __future__ import annotations

import os
import queue
import threading
import time
from enum import Enum
from typing import Any


class Signal(Enum):
    SIGTERM = "SIGTERM"
    SIGKILL = "SIGKILL"
    SIGINT = "SIGINT"
    SIGSEGV = "SIGSEGV"
    SIGFPE = "SIGFPE"
    SIGPIPE = "SIGPIPE"
    SIGHUP = "SIGHUP"
    SIGUSR1 = "SIGUSR1"
    SIGUSR2 = "SIGUSR2"
    SIGALRM = "SIGALRM"
    SIGCHLD = "SIGCHLD"


class IPCType(Enum):
    PIPE = "pipe"
    FIFO = "fifo"
    SHM = "shared_memory"
    SEMAPHORE = "semaphore"
    MESSAGE_QUEUE = "message_queue"
    SOCKET = "socket"


class VirtualMemory:
    """虚拟内存管理器。"""

    def __init__(self, total: int = 4 * 1024 * 1024 * 1024):
        self.total = total
        self.used = 0
        self.free = total
        self._pages: dict[int, bytes] = {}
        self._page_size = 4096
        self._tlb: dict[int, int] = {}

    def allocate(self, size: int) -> int:
        pages = (size + self._page_size - 1) // self._page_size
        addr = self.used
        for i in range(pages):
            self._pages[addr + i * self._page_size] = b"\x00" * self._page_size
        self.used += pages * self._page_size
        self.free = self.total - self.used
        return addr

    def free(self, addr: int, size: int) -> bool:
        pages = (size + self._page_size - 1) // self._page_size
        for i in range(pages):
            self._pages.pop(addr + i * self._page_size, None)
        self.used -= pages * self._page_size
        self.free = self.total - self.used
        return True

    def read(self, addr: int, size: int) -> bytes:
        result = b""
        for i in range(size):
            result += self._pages.get(addr + i, b"\x00")
        return result

    def write(self, addr: int, data: bytes) -> int:
        for i, byte in enumerate(data):
            self._pages[addr + i] = bytes([byte])
        return len(data)

    def protect(self, addr: int, size: int,
                   protection: str) -> None:
        pass

    def get_stats(self) -> dict[str, int]:
        return {"total": self.total, "used": self.used, "free": self.free}


class ProcessManager:
    """进程管理器扩展。"""

    def __init__(self):
        self._processes: dict[int, dict[str, Any]] = {}
        self._next_pid = 1000
        self._ready_queue = queue.Queue()
        self._terminated = queue.Queue()
        self._lock = threading.Lock()
        self._signals: dict[int, list[Signal]] = {}

    def fork(self, cmd: str, args: list[str] = None) -> int:
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            self._processes[pid] = {
                "cmd": cmd, "args": args or [],
                "state": "RUNNING", "pid": pid,
                "ppid": os.getpid(),
                "start_time": time.time(),
            }
            return pid

    def exec(self, path: str, args: list[str] = None) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self._processes[pid] = {
            "path": path, "args": args or [],
            "state": "RUNNING", "pid": pid,
        }
        return pid

    def waitpid(self, pid: int) -> dict[str, Any] | None:
        proc = self._processes.get(pid)
        if proc and proc["state"] == "TERMINATED":
            return proc
        return None

    def kill(self, pid: int, sig: Signal = Signal.SIGTERM) -> bool:
        proc = self._processes.get(pid)
        if proc:
            proc["state"] = "TERMINATED"
            proc["exit_code"] = -1
            proc["signal"] = sig.value
            return True
        return False

    def send_signal(self, pid: int, sig: Signal) -> bool:
        if pid in self._processes:
            if sig not in self._signals:
                self._signals[pid] = []
            self._signals[pid].append(sig)
            return True
        return False

    def get_process(self, pid: int) -> dict[str, Any] | None:
        return self._processes.get(pid)

    def list_processes(self) -> list[dict[str, Any]]:
        return list(self._processes.values())

    def get_process_tree(self) -> dict[int, list[int]]:
        tree = {}
        for pid, proc in self._processes.items():
            ppid = proc.get("ppid", 0)
            if ppid not in tree:
                tree[ppid] = []
            tree[ppid].append(pid)
        return tree

    def set_priority(self, pid: int, priority: int) -> bool:
        proc = self._processes.get(pid)
        if proc:
            proc["priority"] = priority
            return True
        return False

    def get_priority(self, pid: int) -> int | None:
        proc = self._processes.get(pid)
        return proc.get("priority", 0) if proc else None


class SharedMemory:
    """共享内存。"""

    def __init__(self):
        self._segments: dict[str, bytes] = {}
        self._locks: dict[str, threading.Lock] = {}

    def create(self, key: str, size: int) -> str:
        self._segments[key] = b"\x00" * size
        self._locks[key] = threading.Lock()
        return key

    def attach(self, key: str) -> bytes | None:
        return self._segments.get(key)

    def detach(self, key: str) -> bool:
        if key in self._segments:
            del self._segments[key]
            del self._locks[key]
            return True
        return False

    def read(self, key: str) -> bytes | None:
        return self._segments.get(key)

    def write(self, key: str, data: bytes) -> bool:
        if key in self._segments:
            self._segments[key] = data
            return True
        return False


class Semaphore:
    """信号量。"""

    def __init__(self, initial: int = 1):
        self._count = initial
        self._lock = threading.Lock()
        self._cond = threading.Condition()

    def wait(self) -> None:
        with self._cond:
            while self._count <= 0:
                self._cond.wait()
            self._count -= 1

    def signal(self) -> None:
        with self._cond:
            self._count += 1
            self._cond.notify()

    def get_value(self) -> int:
        return self._count


class MessageQueue:
    """消息队列。"""

    def __init__(self, max_size: int = 100):
        self._queue = queue.Queue(maxsize=max_size)
        self._max_size = max_size

    def send(self, msg: str) -> bool:
        try:
            self._queue.put(msg, timeout=1)
            return True
        except queue.Full:
            return False

    def recv(self) -> str | None:
        try:
            return self._queue.get(timeout=1)
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()

    def close(self) -> None:
        self._queue = queue.Queue()


class Pipe:
    """管道。"""

    def __init__(self):
        self._read_buffer = queue.Queue()
        self._write_buffer = queue.Queue()
        self._closed = False

    def write(self, data: bytes) -> int:
        if self._closed:
            return 0
        self._write_buffer.put(data)
        return len(data)

    def read(self, size: int = -1) -> bytes:
        if self._read_buffer.empty():
            return b""
        return self._read_buffer.get()

    def close(self) -> None:
        self._closed = True


def create_virtual_memory(total: int = 4 * 1024 * 1024 * 1024
                             ) -> VirtualMemory:
    return VirtualMemory(total=total)


def create_shared_memory() -> SharedMemory:
    return SharedMemory()


def create_semaphore(initial: int = 1) -> Semaphore:
    return Semaphore(initial=initial)


def create_message_queue(max_size: int = 100
                             ) -> MessageQueue:
    return MessageQueue(max_size=max_size)


def create_pipe() -> Pipe:
    return Pipe()


# ============================================================
# 内置注册
# ============================================================

def _register_os_extended(builtins: dict) -> None:
    builtins["创建虚拟内存"] = create_virtual_memory
    builtins["创建共享内存"] = create_shared_memory
    builtins["创建信号量"] = create_semaphore
    builtins["创建消息队列"] = create_message_queue
    builtins["创建管道"] = create_pipe


def _os_extended_names() -> list[str]:
    return ["创建虚拟内存", "创建共享内存",
            "创建信号量", "创建消息队列", "创建管道"]


__all__ = [
    "Signal", "IPCType",
    "VirtualMemory", "ProcessManager",
    "SharedMemory", "Semaphore",
    "MessageQueue", "Pipe",
    "create_virtual_memory", "create_shared_memory",
    "create_semaphore", "create_message_queue",
    "create_pipe",
    "_register_os_extended", "_os_extended_names",
]
