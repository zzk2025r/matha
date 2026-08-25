# -*- coding: utf-8 -*-
"""Matha 异步运行时与线程池。

支持：
  1. async/await 语法（通过 _parse_expr 中的 async 关键字）
  2. 线程池：用于并行计算密集型任务
  3. 事件循环：用于 I/O 密集型任务
  4. 并发原语：Mutex, Semaphore, Condition
"""

from __future__ import annotations
import asyncio
import concurrent.futures
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional


# ============================================================
# 线程池
# ============================================================

class ThreadPool:
    """Matha 线程池。

    用于并行执行计算密集型任务。
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._max_workers = max_workers
        self._lock = threading.Lock()

    def _get_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._lock:
            if self._pool is None or self._pool._shutdown:
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._max_workers
                )
            return self._pool

    def submit(self, fn: Callable, *args, **kwargs) -> concurrent.futures.Future:
        """提交任务到线程池。"""
        return self._get_pool().submit(fn, *args, **kwargs)

    def map(self, fn: Callable, *iterables, timeout=None):
        """并行映射。"""
        return self._get_pool().map(fn, *iterables, timeout=timeout)

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池。"""
        with self._lock:
            if self._pool is not None:
                self._pool.shutdown(wait=wait)
                self._pool = None

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        self._max_workers = value
        self.shutdown(wait=False)


# ============================================================
# 事件循环
# ============================================================

class EventLoop:
    """Matha 事件循环封装。"""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def run(self, coro: Coroutine) -> Any:
        """运行协程。"""
        return self._get_loop().run_until_complete(coro)

    def run_async(self, coro: Coroutine) -> None:
        """异步运行协程（不阻塞）。"""
        loop = self._get_loop()
        if not loop.is_running():
            loop.run_forever()
        loop.create_task(coro)

    def close(self) -> None:
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()


# ============================================================
# 并发原语
# ============================================================

class Mutex:
    """互斥锁。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        return self._lock.acquire(blocking=True, timeout=5.0)

    def release(self) -> None:
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class Semaphore:
    """信号量。"""

    def __init__(self, value: int = 1) -> None:
        self._sem = threading.Semaphore(value)

    def acquire(self) -> bool:
        return self._sem.acquire(blocking=True, timeout=5.0)

    def release(self) -> None:
        self._sem.release()


class Condition:
    """条件变量。"""

    def __init__(self, mutex: Optional[Mutex] = None) -> None:
        self._cond = threading.Condition(mutex._lock if mutex else threading.Lock())

    def wait(self) -> None:
        self._cond.wait()

    def notify(self) -> None:
        self._cond.notify()

    def notify_all(self) -> None:
        self._cond.notify_all()

    def __enter__(self):
        self._cond.acquire()
        return self

    def __exit__(self, *args):
        self._cond.release()


# ============================================================
# async/await 支持
# ============================================================

class AsyncSupport:
    """Matha async/await 语法支持。"""

    @staticmethod
    def is_async_func(func: Callable) -> bool:
        """检查函数是否为 async。"""
        return asyncio.iscoroutinefunction(func)

    @staticmethod
    def await_func(func: Callable, *args) -> Any:
        """等待 async 函数完成。"""
        if asyncio.iscoroutinefunction(func):
            loop = EventLoop()._get_loop()
            return loop.run_until_complete(func(*args))
        return func(*args)

    @staticmethod
    def parallel_await(coros: list[Coroutine]) -> list[Any]:
        """并行等待多个协程。"""
        loop = EventLoop()._get_loop()
        return loop.run_until_complete(asyncio.gather(*coros))


# ============================================================
# 模块级全局
# ============================================================

# 默认线程池（4 核）
_default_pool = ThreadPool(max_workers=4)

# 默认事件循环
_default_loop = EventLoop()


def get_thread_pool() -> ThreadPool:
    return _default_pool


def get_event_loop() -> EventLoop:
    return _default_loop


# ============================================================
# 导出
# ============================================================

__all__ = [
    "ThreadPool", "EventLoop", "Mutex", "Semaphore", "Condition",
    "AsyncSupport", "get_thread_pool", "get_event_loop",
]
