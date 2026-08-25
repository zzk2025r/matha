# -*- coding: utf-8 -*-
"""Matha 并发扩展：进程池 + select + supervision tree。"""

from __future__ import annotations
import concurrent.futures
import multiprocessing
import select
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


# ============================================================
# 进程池
# ============================================================

class ProcessPool:
    """Matha 进程池（跨进程并行计算）。"""

    def __init__(self, max_workers: int = 4) -> None:
        self._pool: Optional[multiprocessing.Pool] = None
        self._max_workers = max_workers
        self._lock = threading.Lock()

    def _get_pool(self) -> multiprocessing.Pool:
        with self._lock:
            if self._pool is None or self._pool._state != multiprocessing.RUNNING:
                self._pool = multiprocessing.Pool(processes=self._max_workers)
            return self._pool

    def map(self, fn: Callable, items: list, chunksize: int = 1) -> list:
        return self._get_pool().map(fn, items, chunksize)

    def apply(self, fn: Callable, args: tuple = ()) -> Any:
        return self._get_pool().apply(fn, args)

    def apply_async(self, fn: Callable, args: tuple = ()) -> multiprocessing.pool.ApplyResult:
        return self._get_pool().apply_async(fn, args)

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.terminate()
                self._pool.join()
                self._pool = None

    @property
    def max_workers(self) -> int:
        return self._max_workers


# ============================================================
# Select 多路复用
# ============================================================

class SelectMonitor:
    """类 Linux select 的多路复用监听。"""

    def __init__(self) -> None:
        self._readers: list = []
        self._writers: list = []
        self._errors: list = []

    def add_reader(self, fd, callback: Callable) -> None:
        self._readers.append((fd, callback))

    def add_writer(self, fd, callback: Callable) -> None:
        self._writers.append((fd, callback))

    def remove(self, fd) -> None:
        self._readers = [(f, c) for f, c in self._readers if f != fd]
        self._writers = [(f, c) for f, c in self._writers if f != fd]

    def poll(self, timeout: float = 1.0) -> list[tuple]:
        """轮询就绪的 fd。"""
        ready = []
        for fd, callback in self._readers:
            if self._is_readable(fd):
                ready.append(("read", fd, callback))
        for fd, callback in self._writers:
            if self._is_writable(fd):
                ready.append(("write", fd, callback))
        return ready

    def _is_readable(self, fd) -> bool:
        try:
            if hasattr(fd, 'fileno'):
                r, _, _ = select.select([fd], [], [], 0)
                return bool(r)
            return False
        except (OSError, ValueError):
            return False

    def _is_writable(self, fd) -> bool:
        try:
            if hasattr(fd, 'fileno'):
                _, w, _ = select.select([], [fd], [], 0)
                return bool(w)
            return False
        except (OSError, ValueError):
            return False


# ============================================================
# Supervisor 监督树
# ============================================================

class WorkerState(Enum):
    IDLE = auto()
    RUNNING = auto()
    FAILED = auto()
    DEAD = auto()


@dataclass
class Worker:
    name: str
    state: WorkerState = WorkerState.IDLE
    restart_count: int = 0
    max_restarts: int = 5
    last_error: Optional[str] = None


class Supervisor:
    """Actor 监督树。"""

    def __init__(self, name: str = "root") -> None:
        self.name = name
        self._workers: dict[str, Worker] = {}
        self._children: dict[str, list[str]] = {}
        self._restart_strategy = "one_for_one"  # one_for_one / one_for_all / rest_for_one

    def supervise(self, name: str, max_restarts: int = 5) -> Worker:
        """监督一个 worker。"""
        worker = Worker(name=name, max_restarts=max_restarts)
        self._workers[name] = worker
        self._children.setdefault("root", []).append(name)
        return worker

    def start_worker(self, name: str, fn: Callable, *args) -> threading.Thread:
        """启动 worker 线程。"""
        worker = self._workers.get(name)
        if worker is None:
            raise KeyError(f"未注册的 worker: {name}")

        def _run() -> None:
            worker.state = WorkerState.RUNNING
            try:
                fn(*args)
            except Exception as e:
                worker.state = WorkerState.FAILED
                worker.last_error = str(e)
                worker.restart_count += 1
                if worker.restart_count < worker.max_restarts:
                    self._restart(name, fn, args)
                else:
                    worker.state = WorkerState.DEAD

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    def _restart(self, name: str, fn: Callable, args: tuple) -> None:
        time.sleep(0.1)  # 退避
        self.start_worker(name, fn, *args)

    def get_state(self, name: str) -> Optional[WorkerState]:
        worker = self._workers.get(name)
        return worker.state if worker else None

    def get_all_states(self) -> dict[str, str]:
        return {name: worker.state.name for name, worker in self._workers.items()}


# ============================================================
# 分布式锁 stub
# ============================================================

class DistributedLock:
    """简化分布式锁（基于文件）。"""

    def __init__(self, lock_name: str, timeout: float = 10.0) -> None:
        self._lock_name = lock_name
        self._timeout = timeout
        self._lock_file = f"/tmp/.matha_lock_{lock_name}"

    def acquire(self) -> bool:
        import os
        import time
        start = time.perf_counter()
        while time.perf_counter() - start < self._timeout:
            try:
                fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
            except FileExistsError:
                time.sleep(0.01)
        return False

    def release(self) -> None:
        import os
        try:
            os.unlink(self._lock_file)
        except FileNotFoundError:
            pass

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"无法获取锁: {self._lock_name}")
        return self

    def __exit__(self, *args):
        self.release()


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "ProcessPool",
    "SelectMonitor",
    "Supervisor", "WorkerState", "Worker",
    "DistributedLock",
]
