# -*- coding: utf-8 -*-
"""Matha 增强异步运行时：async/await + Channel + Actor + goroutine 调度器。"""

from __future__ import annotations
import asyncio
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Optional


# ============================================================
# Goroutine 调度器
# ============================================================

class GState(Enum):
    READY = auto()
    RUNNING = auto()
    WAITING = auto()
    DONE = auto()
    TERMINATED = auto()


@dataclass
class Goroutine:
    """类 goroutine 协程。"""
    id: int
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    state: GState = GState.READY
    result: Any = None
    error: Optional[Exception] = None


class GoroutineScheduler:
    """M:N goroutine 调度器。"""

    def __init__(self, num_workers: int = 4) -> None:
        self._workers = num_workers
        self._ready: deque[Goroutine] = deque()
        self._running: dict[int, Goroutine] = {}
        self._done: list[Goroutine] = []
        self._next_id = 0
        self._lock = threading.Lock()
        self._running_threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def spawn(self, fn: Callable, *args, **kwargs) -> int:
        """启动一个 goroutine。"""
        with self._lock:
            gid = self._next_id
            self._next_id += 1
            g = Goroutine(id=gid, fn=fn, args=args, kwargs=kwargs)
            self._ready.append(g)
        self._wakeup()
        return gid

    def spawn_channel(self, fn: Callable, *args, **kwargs) -> "Channel":
        """启动 goroutine 并返回结果 channel。"""
        ch = Channel()
        gid = self.spawn(self._channel_producer, ch, fn, *args, **kwargs)
        return ch

    def _channel_producer(self, ch: "Channel", fn: Callable, *args, **kwargs) -> None:
        try:
            result = fn(*args, **kwargs)
            ch.send(result)
        except Exception as e:
            ch.send_error(e)

    def _wakeup(self) -> None:
        if not self._running_threads or not all(t.is_alive() for t in self._running_threads):
            self._running_threads = []
            for _ in range(self._workers):
                t = threading.Thread(target=self._run_loop, daemon=True)
                t.start()
                self._running_threads.append(t)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            g = None
            with self._lock:
                if self._ready:
                    g = self._ready.popleft()
                    g.state = GState.RUNNING
                    self._running[g.id] = g
            if g is None:
                time.sleep(0.001)
                continue
            try:
                g.result = g.fn(*g.args, **g.kwargs)
                g.state = GState.DONE
                with self._lock:
                    self._done.append(g)
            except Exception as e:
                g.error = e
                g.state = GState.TERMINATED
                with self._lock:
                    self._done.append(g)
            finally:
                with self._lock:
                    self._running.pop(g.id, None)

    def wait(self, gid: int, timeout: float = 5.0) -> Any:
        """等待 goroutine 完成。"""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._lock:
                g = self._running.get(gid)
                if g and g.state == GState.DONE:
                    if g.error:
                        raise g.error
                    return g.result
                g = next((d for d in self._done if d.id == gid), None)
                if g:
                    if g.error:
                        raise g.error
                    return g.result
            time.sleep(0.01)
        raise TimeoutError(f"goroutine {gid} 超时")

    def wait_all(self, gids: list[int], timeout: float = 10.0) -> list[Any]:
        """等待所有 goroutine。"""
        results = [None] * len(gids)
        for i, gid in enumerate(gids):
            results[i] = self.wait(gid, timeout)
        return results

    def shutdown(self, wait: bool = True) -> None:
        self._stop_event.set()
        if wait:
            for t in self._running_threads:
                t.join(timeout=5.0)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._ready) + len(self._running)


# ============================================================
# Channel（Go 风格）
# ============================================================

class Channel:
    """类 Go channel 的同步通道。"""

    def __init__(self, capacity: int = 0) -> None:
        self._capacity = capacity
        self._queue: deque = deque()
        self._closed = False
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock) if capacity > 0 else None

    def send(self, value: Any) -> None:
        """发送值。阻塞如果通道满。"""
        with self._not_empty:
            if self._capacity > 0:
                while len(self._queue) >= self._capacity and not self._closed:
                    self._not_full.wait()
            if self._closed:
                raise RuntimeError("channel closed")
            self._queue.append(value)
            self._not_empty.notify()

    def recv(self, timeout: float = None) -> Any:
        """接收值。阻塞如果通道空。"""
        with self._not_empty:
            while len(self._queue) == 0:
                if self._closed:
                    raise StopIteration("channel closed")
                if timeout:
                    if not self._not_empty.wait(timeout=timeout):
                        raise TimeoutError("channel recv timeout")
                else:
                    self._not_empty.wait()
            if self._capacity > 0:
                self._not_full.notify()
            return self._queue.popleft()

    def close(self) -> None:
        with self._not_empty:
            self._closed = True
            self._not_empty.notify_all()

    def send_error(self, error: Exception) -> None:
        self.send(("_error_", error))

    @property
    def closed(self) -> bool:
        return self._closed

    def __iter__(self):
        return self

    def __next__(self) -> Any:
        try:
            return self.recv()
        except StopIteration:
            raise StopIteration

    def drain(self) -> list:
        """ drain all values。"""
        results = []
        with self._lock:
            while self._queue:
                results.append(self._queue.popleft())
        return results


# ============================================================
# Actor 模型
# ================================================= =========

class Actor:
    """类 Erlang actor 的 Actor。"""

    def __init__(self, name: str, handler: Callable) -> None:
        self.name = name
        self._handler = handler
        self._mailbox: deque = deque()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._pid = None
        self._alive = True

    def start(self) -> int:
        """启动 actor。"""
        def _run() -> None:
            while self._alive:
                msg = None
                with self._condition:
                    while len(self._mailbox) == 0 and self._alive:
                        self._condition.wait(timeout=0.1)
                    if not self._alive:
                        return
                    msg = self._mailbox.popleft()
                try:
                    self._handler(msg)
                except Exception as e:
                    pass  # actor 崩溃隔离
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._pid = t.ident
        return self._pid

    def tell(self, message: Any) -> None:
        """异步发送消息。"""
        with self._condition:
            self._mailbox.append(message)
            self._condition.notify()

    def ask(self, message: Any, timeout: float = 5.0) -> Any:
        """发送消息并等待响应。"""
        response_ch = Channel()
        self.tell((message, response_ch))
        try:
            return response_ch.recv(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"actor {self.name} 响应超时")

    def stop(self) -> None:
        self._alive = False
        with self._condition:
            self._condition.notify_all()

    @property
    def is_alive(self) -> bool:
        return self._alive


# ============================================================
# async/await 语法糖
# ============================================================

class AsyncSyntax:
    """Matha async/await 语法支持。"""

    @staticmethod
    def is_coroutine(obj: Any) -> bool:
        return asyncio.iscoroutinefunction(obj) or asyncio.iscoroutine(obj)

    @staticmethod
    def await_func(func: Callable, *args) -> Any:
        """等待 async 函数完成。"""
        if asyncio.iscoroutinefunction(func):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(func(*args))
        if asyncio.iscoroutine(func):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(func)
        return func(*args)

    @staticmethod
    def async_map(func: Callable, items: list) -> list:
        """并行 map。"""
        loop = asyncio.get_event_loop()
        coros = [func(item) for item in items]
        return loop.run_until_complete(asyncio.gather(*coros))

    @staticmethod
    def async_filter(func: Callable, items: list) -> list:
        """并行 filter。"""
        loop = asyncio.get_event_loop()
        async def _filter():
            results = []
            for item in items:
                if await func(item):
                    results.append(item)
            return results
        return loop.run_until_complete(_filter())


# ============================================================
# 统一异步运行时
# ============================================================

class AsyncRuntime:
    """统一异步运行时。"""

    def __init__(self, goroutines: int = 4) -> None:
        self.scheduler = GoroutineScheduler(num_workers=goroutines)
        self.syntax = AsyncSyntax()
        self._actors: dict[str, Actor] = {}

    def spawn(self, fn: Callable, *args, **kwargs) -> int:
        return self.scheduler.spawn(fn, *args, **kwargs)

    def spawn_channel(self, fn: Callable, *args, **kwargs) -> Channel:
        return self.scheduler.spawn_channel(fn, *args, **kwargs)

    def wait(self, gid: int, timeout: float = 5.0) -> Any:
        return self.scheduler.wait(gid, timeout)

    def wait_all(self, gids: list[int], timeout: float = 10.0) -> list:
        return self.scheduler.wait_all(gids, timeout)

    def create_actor(self, name: str, handler: Callable) -> Actor:
        actor = Actor(name, handler)
        actor.start()
        self._actors[name] = actor
        return actor

    def get_actor(self, name: str) -> Optional[Actor]:
        return self._actors.get(name)

    def shutdown(self) -> None:
        self.scheduler.shutdown()
        for actor in self._actors.values():
            actor.stop()

    @property
    def pending(self) -> int:
        return self.scheduler.pending_count


# 全局实例
_async_runtime = AsyncRuntime()


def async_spawn(fn: Callable, *args, **kwargs) -> int:
    """便捷函数：启动 goroutine。"""
    return _async_runtime.spawn(fn, *args, **kwargs)


def async_wait(gid: int, timeout: float = 5.0) -> Any:
    """便捷函数：等待 goroutine。"""
    return _async_runtime.wait(gid, timeout)


def new_channel(capacity: int = 0) -> Channel:
    """创建 channel。"""
    return Channel(capacity)


def create_actor(name: str, handler: Callable) -> Actor:
    """创建 actor。"""
    return _async_runtime.create_actor(name, handler)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "GoroutineScheduler", "Goroutine", "GState",
    "Channel",
    "Actor",
    "AsyncSyntax",
    "AsyncRuntime",
    "async_spawn", "async_wait", "new_channel", "create_actor",
    "_async_runtime",
]
