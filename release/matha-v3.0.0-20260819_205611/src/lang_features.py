# -*- coding: utf-8 -*-
"""Matha 语言特性扩展：with/decorator/generator/async语法支持。"""

from __future__ import annotations
import asyncio
import functools
import sys
from typing import Any, Callable, Optional


# ============================================================
# 上下文管理器支持（with 语句）
# ============================================================

class MathaContextManager:
    """Matha 上下文管理器。"""

    def __init__(self, enter_fn: Callable, exit_fn: Callable) -> None:
        self._enter = enter_fn
        self._exit = exit_fn
        self._resource = None

    def __enter__(self) -> Any:
        self._resource = self._enter()
        return self._resource

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            self._exit(exc_val)
        finally:
            self._resource = None
        return False  # 不抑制异常


def with_statement(resource_fn: Callable, body_fn: Callable) -> Any:
    """Matha with 语句实现。"""
    ctx = MathaContextManager(
        enter_fn=lambda: resource_fn(),
        exit_fn=lambda exc: body_fn(None) if exc is None else body_fn(exc)
    )
    with ctx as res:
        return body_fn(res)


# ============================================================
# 装饰器支持
# ============================================================

def decorator(decorator_fn: Callable) -> Callable:
    """Matha 装饰器语法糖。"""
    def wrapper(func: Callable) -> Callable:
        return functools.wraps(func)(decorator_fn(func))
    return wrapper


def static_method(fn: Callable) -> staticmethod:
    """Matha @staticmethod 等价物。"""
    return staticmethod(fn)


def class_method(fn: Callable) -> classmethod:
    """Matha @classmethod 等价物。"""
    return classmethod(fn)


def property_getter(fn: Callable) -> property:
    """Matha @property 等价物。"""
    return property(fn)


# ============================================================
# 生成器支持
# ============================================================

class MathaGenerator:
    """Matha 生成器对象。"""

    def __init__(self, gen_fn: Callable) -> None:
        self._gen = gen_fn()

    def __iter__(self):
        return self

    def __next__(self) -> Any:
        return next(self._gen)

    def send(self, value: Any) -> Any:
        return self._gen.send(value)

    def close(self) -> None:
        self._gen.close()


def generator(gen_fn: Callable) -> MathaGenerator:
    """创建 Matha 生成器。"""
    return MathaGenerator(gen_fn)


def yield_value(value: Any) -> Any:
    """Matha yield 语句等价物（在生成器函数内调用）。"""
    # 注意：这需要在生成器函数内部使用
    raise StopIteration(value)


# ============================================================
# async/await 语法支持
# ============================================================

class MathaAsyncFunction:
    """Matha async 函数包装。"""

    def __init__(self, async_fn: Callable) -> None:
        self._async_fn = async_fn
        functools.update_wrapper(self, async_fn)

    async def __call__(self, *args, **kwargs) -> Any:
        return await self._async_fn(*args, **kwargs)

    def __await__(self):
        return self._async_fn().__await__()


def async_function(fn: Callable) -> MathaAsyncFunction:
    """Matha async 函数装饰器。"""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await fn(*args, **kwargs)
    return MathaAsyncFunction(wrapper)


def await_expression(coro: Any) -> Any:
    """Matha await 表达式等价物。"""
    if asyncio.iscoroutine(coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    return coro


# ============================================================
# 属性访问增强
# ============================================================

class MathaProperty:
    """Matha 属性对象。"""

    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self._fget = fget
        self._fset = fset
        self._fdel = fdel
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self._fget is None:
            raise AttributeError("unreadable attribute")
        return self._fget(obj)

    def __set__(self, obj, value):
        if self._fset is None:
            raise AttributeError("can't set attribute")
        self._fset(obj, value)

    def __delete__(self, obj):
        if self._fdel is None:
            raise AttributeError("can't delete attribute")
        self._fdel(obj)

    def getter(self, fget):
        return type(self)(fget, self._fset, self._fdel, self.__doc__)

    def setter(self, fset):
        return type(self)(self._fget, fset, self._fdel, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self._fget, self._fset, fdel, self.__doc__)


def matha_property(fget=None, fset=None, fdel=None, doc=None):
    """Matha @property 语法。"""
    if fget is None:
        return MathaProperty(fset=fset, fdel=fdel, doc=doc)
    return MathaProperty(fget=fget, fset=fset, fdel=fdel, doc=doc)


# ============================================================
# 元类支持（简化）
# ============================================================

def matha_metaclass(name: str, bases: tuple, namespace: dict) -> type:
    """Matha 元类工厂。"""
    return type(name, bases, namespace)


# ============================================================
# GC 调优
# ============================================================

def gc_set_threshold(memcounts: tuple) -> None:
    """设置 GC 阈值。"""
    import gc
    gc.set_threshold(*memcounts)


def gc_get_threshold() -> tuple:
    import gc
    return gc.get_threshold()


def gc_collect() -> int:
    import gc
    return gc.collect()


# ============================================================
# 注册所有特性
# ============================================================

def register_language_features(builtins: dict) -> None:
    """将语言特性注册为 Matha 内建。"""
    builtins["with语句"] = with_statement
    builtins["装饰器"] = decorator
    builtins["静态方法"] = static_method
    builtins["类方法"] = class_method
    builtins["属性"] = property_getter
    builtins["生成器"] = generator
    builtins["yield"] = yield_value
    builtins["async函数"] = async_function
    builtins["await"] = await_expression
    builtins["属性对象"] = matha_property
    builtins["元类"] = matha_metaclass
    builtins["GC阈值"] = gc_get_threshold
    builtins["GC设置"] = gc_set_threshold
    builtins["GC收集"] = gc_collect


__all__ = [
    "register_language_features",
    "MathaContextManager", "with_statement",
    "decorator", "static_method", "class_method", "property_getter",
    "MathaGenerator", "generator", "yield_value",
    "MathaAsyncFunction", "async_function", "await_expression",
    "matha_property", "matha_metaclass",
    "gc_set_threshold", "gc_get_threshold", "gc_collect",
]
