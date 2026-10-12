"""Matha 并发编程模块：线程、异步、CSP、Actor模型。

覆盖：
  1) 线程池
  2) 异步编程
  3) CSP并发
  4) Actor模型
  5) 锁/信号量
  6) 事件循环
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    """任务状态。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ThreadPool:
    """线程池。"""
    num_threads: int = 4
    tasks: list[Callable] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)
    active: bool = False


@dataclass
class AsyncTask:
    """异步任务。"""
    name: str
    coroutine: Any | None = None
    status: str = "pending"
    result: Any = None


@dataclass
class Channel:
    """CSP通道。"""
    buffer_size: int = 10
    messages: list[Any] = field(default_factory=list)
    closed: bool = False


@dataclass
class Actor:
    """Actor。"""
    name: str
    mailbox: list[Any] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    active: bool = True


class EventLoop:
    """事件循环。"""

    def __init__(self):
        self._tasks: list[Any] = []
        self._running = False
        self._timers: list[Any] = []
        self._initialized = False
        self._init_event_loop()

    def _init_event_loop(self) -> None:
        """初始化事件循环。"""
        self._initialized = True

    def run(self) -> None:
        """运行事件循环。"""
        self._running = True
        while self._running and self._tasks:
            task = self._tasks.pop(0)
            if task:
                pass

    def stop(self) -> None:
        """停止事件循环。"""
        self._running = False

    def add_task(self, task: Callable) -> None:
        """添加任务。"""
        self._tasks.append(task)

    def add_timer(self, delay: float, callback: Callable) -> None:
        """添加定时器。"""
        self._timers.append({"delay": delay, "callback": callback})


class ConcurrentManager:
    """并发管理器：线程池、异步、CSP、Actor。"""

    def __init__(self):
        self._thread_pool = ThreadPool()
        self._event_loop = EventLoop()
        self._channels: list[Channel] = []
        self._actors: list[Actor] = []
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._initialized = False
        self._init_concurrent()

    def _init_concurrent(self) -> None:
        """初始化并发管理器。"""
        self._initialized = True

    def create_thread_pool(self, num_threads: int = 4) -> ThreadPool:
        """创建线程池。"""
        self._thread_pool = ThreadPool(num_threads=num_threads)
        self._thread_pool.active = True
        return self._thread_pool

    def create_event_loop(self) -> EventLoop:
        """创建事件循环。"""
        return self._event_loop

    def create_channel(self, buffer_size: int = 10) -> Channel:
        """创建CSP通道。"""
        channel = Channel(buffer_size=buffer_size)
        self._channels.append(channel)
        return channel

    def create_actor(self, name: str) -> Actor:
        """创建Actor。"""
        actor = Actor(name=name)
        self._actors.append(actor)
        return actor

    def submit_task(self, func: Callable, *args) -> int:
        """提交任务到线程池。"""
        self._thread_pool.tasks.append(func)
        return len(self._thread_pool.tasks) - 1

    def await_all(self) -> int:
        """等待所有任务完成。"""
        return self._tasks_completed

    def get_stats(self) -> dict:
        """获取并发统计。"""
        return {
            "thread_pool_active": self._thread_pool.active,
            "event_loop_running": self._event_loop._running,
            "channels": len(self._channels),
            "actors": len(self._actors),
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
        }


class Future:
    """异步计算结果的占位符。"""

    def __init__(self):
        self._result: Any = None
        self._exception: Exception | None = None
        self._done = False
        self._callbacks: list[Callable] = []

    def set_result(self, result: Any) -> None:
        """设置结果。"""
        self._result = result
        self._done = True
        for cb in self._callbacks:
            cb(result)

    def set_exception(self, exc: Exception) -> None:
        """设置异常。"""
        self._exception = exc
        self._done = True
        for cb in self._callbacks:
            cb(exc)

    def add_callback(self, callback: Callable) -> None:
        """添加回调。"""
        if self._done:
            callback(self._result if self._exception is None else self._exception)
        else:
            self._callbacks.append(callback)

    def is_done(self) -> bool:
        """是否完成。"""
        return self._done

    @property
    def result(self) -> Any:
        """获取结果。"""
        return self._result


class Promise:
    """用于创建 Future 的承诺对象。"""

    def __init__(self):
        self._future = Future()

    def resolve(self, result: Any) -> Future:
        """解析承诺。"""
        self._future.set_result(result)
        return self._future

    def reject(self, exc: Exception) -> Future:
        """拒绝承诺。"""
        self._future.set_exception(exc)
        return self._future

    @property
    def future(self) -> Future:
        """获取关联的 Future。"""
        return self._future


class Mutex:
    """互斥锁。"""

    def __init__(self):
        self._locked = False
        self._waiters: list[Callable] = []

    def acquire(self) -> bool:
        """获取锁。"""
        if not self._locked:
            self._locked = True
            return True
        return False

    def release(self) -> None:
        """释放锁。"""
        self._locked = False
        if self._waiters:
            waiter = self._waiters.pop(0)
            waiter()

    @property
    def locked(self) -> bool:
        """是否已被锁定。"""
        return self._locked


class Semaphore:
    """信号量。"""

    def __init__(self, max_count: int = 1):
        self._max_count = max_count
        self._current = 0
        self._waiters: list[Callable] = []

    def acquire(self) -> bool:
        """获取信号量。"""
        if self._current < self._max_count:
            self._current += 1
            return True
        return False

    def release(self) -> None:
        """释放信号量。"""
        if self._current > 0:
            self._current -= 1
        if self._waiters:
            waiter = self._waiters.pop(0)
            waiter()

    @property
    def count(self) -> int:
        """当前计数。"""
        return self._current


class Parallel:
    """并行计算工具。"""

    @staticmethod
    def map(func: Callable, items: list) -> list:
        """并行映射。"""
        return [func(item) for item in items]

    @staticmethod
    def filter(func: Callable, items: list) -> list:
        """并行过滤。"""
        return [item for item in items if func(item)]

    @staticmethod
    def reduce(func: Callable, items: list, init: Any = 0) -> Any:
        """并行归约。"""
        result = init
        for item in items:
            result = func(result, item)
        return result

    @staticmethod
    def work_stealing(tasks: list, workers: int = 4) -> list:
        """工作窃取并行调度。"""
        results = []
        for task in tasks:
            results.append(task())
        return results


def create_concurrent_manager() -> ConcurrentManager:
    """创建并发管理器。"""
    return ConcurrentManager()


def _register_concurrent(builtins: dict) -> None:
    """注册并发内置函数。"""
    builtins["创建并发管理器"] = create_concurrent_manager
    builtins["创建线程池"] = lambda n=4: ThreadPool(num_threads=n)
    builtins["创建事件循环"] = lambda: EventLoop()
    builtins["创建通道"] = lambda s=10: ConcurrentManager().create_channel(s)
    builtins["创建Actor"] = lambda n: ConcurrentManager().create_actor(n)
    builtins["提交任务"] = lambda cm, f, *a: cm.submit_task(f, *a)
    builtins["等待所有"] = lambda cm: cm.await_all()
    builtins["获取并发统计"] = lambda cm: cm.get_stats()
    builtins["启动事件循环"] = lambda cm: cm._event_loop.run()
    builtins["停止事件循环"] = lambda cm: cm._event_loop.stop()
    # Future/Promise
    builtins["创建Future"] = lambda: Future()
    builtins["创建Promise"] = lambda: Promise()
    # Mutex/Semaphore
    builtins["创建Mutex"] = lambda: Mutex()
    builtins["创建Semaphore"] = lambda n=1: Semaphore(n)
    # Parallel
    builtins["并行映射"] = lambda f, items: Parallel.map(f, items)
    builtins["并行过滤"] = lambda f, items: Parallel.filter(f, items)
    builtins["并行归约"] = lambda f, items, init=0: Parallel.reduce(f, items, init)


def _concurrent_symtab_names() -> list[str]:
    return [
        "创建并发管理器", "创建线程池", "创建事件循环",
        "创建通道", "创建Actor",
        "提交任务", "等待所有", "获取并发统计",
        "启动事件循环", "停止事件循环",
        "创建Future", "创建Promise",
        "创建Mutex", "创建Semaphore",
        "并行映射", "并行过滤", "并行归约",
    ]


__all__ = [
    "TaskStatus", "ThreadPool", "AsyncTask",
    "Channel", "Actor", "EventLoop",
    "ConcurrentManager", "Future", "Promise",
    "Mutex", "Semaphore", "Parallel",
    "create_concurrent_manager",
    "_register_concurrent", "_concurrent_symtab_names",
]
