"""Matha 语言核心的运行时特性开关（Feature Flags）。

设计目标：为「新语义」提供渐进式灰度能力——**默认全部关闭**，现有行为保持不变；
可通过环境变量或进程内 API 显式开启，用于小范围验证后再逐步全量放开。

约定：
  - 环境变量 ``MATHA_FEATURE_<NAME>``：取值 1/true/yes/on（大小写不敏感）= 开启；
    0/false/no/off/空 = 关闭。
  - 环境变量 ``MATHA_FEATURES``：逗号分隔的开关名清单（追加开启项）。
  - 进程内可用 ``set_feature`` / ``clear_feature`` 覆盖（供测试与 CLI 使用），
    覆盖优先于环境变量。

已知开关：
  - ``SCOPED_BLOCKS``：`{ }` 代码块作为**语句上下文**——块内 `名 = 值` 解析为绑定，
    且块（作为 lambda 体时）拥有独立子作用域，从而原生支持多语句函数体与循环。
"""
from __future__ import annotations

import os

_TRUE = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE = frozenset({"0", "false", "no", "off", "n", "f", ""})

_overrides: dict[str, bool] = {}


def _env_key(name: str) -> str:
    return "MATHA_FEATURE_" + name.upper().replace("-", "_")


def _norm(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _parse_bool(raw: object) -> bool | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None


def is_enabled(name: str, default: bool = False) -> bool:
    """查询开关状态：进程内覆盖 > 专用环境变量 > MATHA_FEATURES 清单 > default。"""
    if name in _overrides:
        return _overrides[name]
    v = _parse_bool(os.environ.get(_env_key(name)))
    if v is not None:
        return v
    listing = os.environ.get("MATHA_FEATURES", "")
    if listing:
        items = {_norm(x) for x in listing.split(",") if x.strip()}
        if _norm(name) in items:
            return True
    return default


def set_feature(name: str, enabled: bool = True) -> None:
    """进程内强制开启/关闭某开关。"""
    _overrides[name] = bool(enabled)


def clear_feature(name: str | None = None) -> None:
    """清除进程内覆盖（name=None 时清除全部）。"""
    if name is None:
        _overrides.clear()
    else:
        _overrides.pop(name, None)


def scoped_blocks() -> bool:
    """SCOPED_BLOCKS：`{ }` 代码块 = 语句上下文 + 独立子作用域（默认关闭）。"""
    return is_enabled("SCOPED_BLOCKS", default=False)


def stack_engine() -> bool:
    """STACK_ENGINE：表达式求值走显式帧栈（Strangler Fig 绞杀中间态，默认关闭）。

    开启后 ``Interpreter._eval`` 转调 ``StackEngine``（trampoline，宿主栈 O(1)），
    尚未迁移的节点回退解释器递归实现。默认关闭以保持现有行为不变。
    """
    return is_enabled("STACK_ENGINE", default=False)


__all__ = ["is_enabled", "set_feature", "clear_feature", "scoped_blocks", "stack_engine"]
