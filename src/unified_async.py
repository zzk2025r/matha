# -*- coding: utf-8 -*-
"""
Matha Async Runtime 统一层（Unified Async Runtime）

合并 async_runtime.py 和 async_runtime_v2.py：
  - async_runtime.py: 基础异步运行时（ThreadPool, EventLoop, Mutex, Semaphore, Condition）
  - async_runtime_v2.py: 增强版（GoroutineScheduler, Channel, Actor, AsyncRuntime）

统一后：async_runtime_v2 完全覆盖 async_runtime，作为主实现。
"""
from __future__ import annotations

# ── 从 async_runtime_v2 导入增强实现 ────────────────────────────────────────
try:
    from src.async_runtime_v2 import (  # noqa: F401
        GState,
        Goroutine,
        GoroutineScheduler,
        Channel,
        Actor,
        AsyncSyntax,
        AsyncRuntime,
        async_spawn,
        async_wait,
        new_channel,
        create_actor,
    )
except ImportError:
    GState = None
    Goroutine = None
    GoroutineScheduler = None
    Channel = None
    Actor = None
    AsyncSyntax = None
    AsyncRuntime = None
    async_spawn = None
    async_wait = None
    new_channel = None
    create_actor = None

# ── 从 async_runtime 导入基础实现（向后兼容）────────────────────────────────
try:
    from src.async_runtime import (  # noqa: F401
        ThreadPool,
        EventLoop,
        Mutex,
        Semaphore,
        Condition,
        AsyncSupport,
        get_thread_pool,
        get_event_loop,
    )
except ImportError:
    ThreadPool = None
    EventLoop = None
    Mutex = None
    Semaphore = None
    Condition = None
    AsyncSupport = None
    get_thread_pool = None
    get_event_loop = None

# ── 统一别名 ────────────────────────────────────────────────────────────────
# v2 的 AsyncRuntime 就是 v1 的 AsyncSupport（功能等价）
# 让两种命名都可用
AsyncRuntimeV1 = AsyncRuntime  # noqa: F811

__all__ = [
    # v2 增强
    "GState", "Goroutine", "GoroutineScheduler",
    "Channel", "Actor", "AsyncSyntax", "AsyncRuntime",
    "async_spawn", "async_wait", "new_channel", "create_actor",
    # v1 基础（兼容别名）
    "ThreadPool", "EventLoop", "Mutex", "Semaphore", "Condition",
    "AsyncSupport", "get_thread_pool", "get_event_loop",
]
