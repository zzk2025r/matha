# -*- coding: utf-8 -*-
"""Matha Result 类型与异常处理 — v2.2

提供 Rust 风格的 Result<T, E> 和 Option<T> 类型，
支持函数式错误传播（? 运算符语义）。
"""
from __future__ import annotations
import traceback
from typing import Any, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum, auto


# ============================================================
# 结果类型
# ============================================================

T = TypeVar('T')
E = TypeVar('E')


class ResultState(Enum):
    """Result 状态。"""
    OK = "ok"
    ERR = "err"


@dataclass
class Ok:
    """成功结果。"""
    value: T
    state: ResultState = ResultState.OK
    label: str = ""

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def expect(self, msg: str) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value

    def map(self, fn) -> "Result":
        return Ok(fn(self.value), label=self.label)

    def map_err(self, _fn) -> "Result":
        return self

    def and_then(self, fn) -> "Result":
        return fn(self.value)

    def or_else(self, _fn) -> "Result":
        return self

    def unwrap_or_else(self, fn) -> T:
        return self.value

    def err(self) -> None:
        return None

    def ok(self) -> Optional[T]:
        return self.value

    def as_ref(self) -> "Ok":
        return self

    def iter(self) -> Any:
        return iter([self.value])

    def label(self) -> str:
        return self.label


@dataclass
class Err:
    """错误结果。"""
    error: E
    state: ResultState = ResultState.ERR
    label: str = ""
    trace: str = ""

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise MathaResultError(f"unwrap() called on Err: {self.error}", self.trace)

    def expect(self, msg: str) -> T:
        raise MathaResultError(f"{msg}: {self.error}", self.trace)

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, _fn) -> "Result":
        return self

    def map_err(self, fn) -> "Result":
        return Err(fn(self.error), label=self.label, trace=self.trace)

    def and_then(self, _fn) -> "Result":
        return self

    def or_else(self, fn) -> "Result":
        return fn(self.error)

    def unwrap_or_else(self, fn) -> T:
        return fn(self.error)

    def err(self) -> Optional[E]:
        return self.error

    def ok(self) -> None:
        return None

    def as_ref(self) -> "Err":
        return self

    def iter(self) -> Any:
        return iter([])

    def label(self) -> str:
        return self.label

    def context(self, msg: str) -> "Err":
        """添加错误上下文。"""
        return Err(self.error, label=self.label,
                   trace=f"{msg}\n{self.trace}" if self.trace else msg)


# ============================================================
# Option 类型
# ============================================================

@dataclass
class Some:
    """有值。"""
    value: T

    def is_some(self) -> bool:
        return True

    def is_none(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value

    def unwrap_or_else(self, fn) -> T:
        return self.value

    def map(self, fn) -> "Option":
        return Some(fn(self.value))

    def and_then(self, fn) -> "Option":
        return fn(self.value)

    def filter(self, pred) -> "Option":
        return self if pred(self.value) else None

    def ok_or(self, err: E) -> "Result":
        return Ok(self.value)

    def ok_or_else(self, err_fn) -> "Result":
        return Ok(self.value)

    def iter(self) -> Any:
        return iter([self.value])

    def label(self) -> str:
        return str(self.value)


@dataclass
class None_:
    """无值。"""

    def is_some(self) -> bool:
        return False

    def is_none(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise MathaResultError("unwrap() called on None")

    def expect(self, msg: str) -> T:
        raise MathaResultError(f"{msg}: None")

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, fn) -> T:
        return fn()

    def map(self, _fn) -> "Option":
        return None_()

    def and_then(self, _fn) -> "Option":
        return None_()

    def filter(self, _pred) -> "Option":
        return None_()

    def ok_or(self, err: E) -> "Result":
        return Err(err)

    def ok_or_else(self, err_fn) -> "Result":
        return Err(err_fn())

    def iter(self) -> Any:
        return iter([])

    def label(self) -> str:
        return "None"


# Option 别名
Option = Any  # 运行时动态解析

# ============================================================
# 自定义异常
# ============================================================

class MathaResultError(Exception):
    """Matha Result 类型错误。"""
    def __init__(self, message: str, trace: str = ""):
        self.message = message
        self.trace = trace
        super().__init__(self.message)


class MathaOptionError(MathaResultError):
    """Option 类型错误。"""
    pass


class MathaTypeError(MathaResultError):
    """类型转换错误。"""
    pass


# ============================================================
# 辅助函数
# ============================================================

def ok(value: T) -> Result:
    """创建成功结果。"""
    return Ok(value)


def err(error: E) -> Result:
    """创建错误结果。"""
    return Err(error)


def some(value: T) -> Option:
    """创建 Some。"""
    return Some(value)


def none() -> Option:
    """创建 None。"""
    return None_()


def result(fn, *args, **kwargs) -> Result:
    """执行函数并捕获异常，返回 Result。"""
    try:
        return Ok(fn(*args, **kwargs))
    except Exception as e:
        return Err(f"{type(e).__name__}: {e}", trace=traceback.format_exc())


def try_unwrap(result: Result) -> Any:
    """安全解包 Result。"""
    if isinstance(result, Ok):
        return result.value
    elif isinstance(result, Err):
        return None


def try_unwrap_or(result: Result, default: Any) -> Any:
    """安全解包 Result，失败时返回默认值。"""
    if isinstance(result, Ok):
        return result.value
    return default


# ============================================================
# 类型注册
# ============================================================

def register_result_builtins(builtins: dict) -> None:
    """注册 Result/Option 类型到 Matha 内建函数表。"""
    builtins["Ok"] = ok
    builtins["Err"] = err
    builtins["Some"] = some
    builtins["None"] = none
    builtins["Try"] = result
    builtins["UnwrapOr"] = try_unwrap_or
