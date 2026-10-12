"""Matha 异步编程：async/await 支持、协程、事件循环。"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AsyncStatus(Enum):
    """异步状态。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Coroutine:
    """协程。"""
    name: str
    coroutine: Any | None = None
    status: str = "pending"
    result: Any = None
    error: Exception | None = None

    def __await__(self):
        return self._await_impl()

    async def _await_impl(self) -> Any:
        """实现 await。"""
        if self.coroutine and hasattr(self.coroutine, '__await__'):
            return await self.coroutine
        return self.result


@dataclass
class Future:
    """异步 Future（增强版）。"""
    _result: Any = None
    _exception: Exception | None = None
    _done: bool = False
    _callbacks: list[Callable] = field(default_factory=list)

    def set_result(self, result: Any) -> None:
        self._result = result
        self._done = True
        for cb in self._callbacks:
            cb(result)

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc
        self._done = True
        for cb in self._callbacks:
            cb(exc)

    @property
    def result(self) -> Any:
        return self._result

    @property
    def is_done(self) -> bool:
        return self._done


class AsyncManager:
    """异步管理器：协程、事件循环、异步任务。"""

    def __init__(self):
        self._coroutines: list[Coroutine] = []
        self._futures: list[Future] = []
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._initialized = False
        self._init_async()

    def _init_async(self) -> None:
        """初始化异步管理器。"""
        self._initialized = True

    async def run_async(self, coro: Any, name: str = "task"
                           ) -> Any:
        """运行异步任务。"""
        if not self._event_loop:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        try:
            result = await coro
            return result
        except Exception:
            raise

    def create_coroutine(self, name: str,
                              func: Callable, *args
                              ) -> Coroutine:
        """创建协程。"""
        coro = Coroutine(name=name)
        coro.coroutine = func(*args) if callable(func) else func
        self._coroutines.append(coro)
        return coro

    def async_map(self, func: Callable, items: list
                      ) -> list[Future]:
        """异步映射。"""
        futures = []
        for item in items:
            future = Future()
            futures.append(future)
        return futures

    def async_filter(self, func: Callable, items: list
                        ) -> list[Future]:
        """异步过滤。"""
        futures = []
        for item in items:
            if func(item):
                future = Future()
                futures.append(future)
        return futures

    async def gather(self, coroutines: list
                         ) -> list[Any]:
        """并行运行协程。"""
        if self._event_loop:
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            return results
        return []

    def create_event_loop(self) -> asyncio.AbstractEventLoop:
        """创建事件循环。"""
        if not self._event_loop:
            self._event_loop = asyncio.new_event_loop()
        return self._event_loop

    async def sleep(self, delay: float) -> None:
        """异步等待。"""
        await asyncio.sleep(delay)

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "coroutines": len(self._coroutines),
            "futures": len(self._futures),
            "event_loop_active": self._event_loop is not None,
        }


# ============================================================
# 异步内置注册
# ============================================================

def create_async_manager() -> AsyncManager:
    """创建异步管理器。"""
    return AsyncManager()


async def async_run(coro: Any, name: str = "task") -> Any:
    """运行异步任务。"""
    am = AsyncManager()
    return await am.run_async(coro, name)


async def async_gather(coroutines: list) -> list[Any]:
    """并行运行协程。"""
    am = AsyncManager()
    return await am.gather(coroutines)


async def async_sleep(delay: float) -> None:
    """异步等待。"""
    await asyncio.sleep(delay)


def _register_async(builtins: dict) -> None:
    """注册异步内置函数。"""
    builtins["创建异步管理器"] = create_async_manager
    builtins["运行异步"] = async_run
    builtins["并行运行"] = async_gather
    builtins["异步等待"] = async_sleep


def _async_symtab_names() -> list[str]:
    return [
        "创建异步管理器", "运行异步", "并行运行", "异步等待",
    ]


__all__ = [
    "AsyncStatus", "Coroutine", "Future", "AsyncManager",
    "create_async_manager", "async_run", "async_gather", "async_sleep",
    "_register_async", "_async_symtab_names",
]
