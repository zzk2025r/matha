# -*- coding: utf-8 -*-
"""Matha 硬件逆向工程领域模块：信号分析、协议解析、固件提取、功耗分析。

覆盖：
  1) 信号频率分析
  2) 协议解析率
  3) 固件完整性校验
  4) 逆向复杂度
  5) 时钟频率估算
  6) 功耗分析
"""

from __future__ import annotations
import math
import hashlib


def _curry1(func):
    def with_first(a): return func(a)
    return with_first

def _curry2(func):
    def with_first(a): return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b): return lambda c: func(a, b, c)
        return w2
    return w1


def _信号频率分析(采样率, 窗口长度_ms):
    """FFT频率分辨率（Hz）。"""
    if 窗口长度_ms <= 0 or 采样率 <= 0:
        return 0.0
    N = int(采样率 * 窗口长度_ms / 1000)
    return 采样率 / N if N > 0 else 0.0


def _协议解析率(总消息数, 成功解析数):
    """协议消息解析成功率。"""
    if 总消息数 <= 0:
        return 0.0
    return 成功解析数 / 总消息数 * 100


def _固件完整性校验(固件大小_MB, 校验和匹配):
    """固件完整性评估。"""
    if 固件大小_MB <= 0:
        return 0.0
    return 100.0 if 校验和匹配 else 0.0


def _逆向复杂度(代码行数, 函数数, 调用图复杂度):
    """逆向工程复杂度估算。"""
    if 函数数 <= 0:
        return 0.0
    return (代码行数 / 函数数) * math.log(调用图复杂度 + 1)


def _时钟频率估算(周期_ns):
    """从周期估算时钟频率（MHz）。"""
    if 周期_ns <= 0:
        return 0.0
    return 1e6 / 周期_ns


def _功耗分析(电压_V, 电流_mA, 占空比):
    """平均功耗（mW）。"""
    return 电压_V * 电流_mA * max(0.0, min(1.0, 占空比))


# ============================================================
# 注册
# ============================================================

def _register_hardware_reverse(builtins: dict) -> None:
    builtins["信号频率分析"] = _curry2(_信号频率分析)
    builtins["协议解析率"] = _curry2(_协议解析率)
    builtins["固件完整性校验"] = _curry2(_固件完整性校验)
    builtins["逆向复杂度"] = _curry3(_逆向复杂度)
    builtins["时钟频率估算"] = _curry1(_时钟频率估算)
    builtins["功耗分析"] = _curry3(_功耗分析)


def _hardware_reverse_symtab_names() -> list[str]:
    return ["信号频率分析", "协议解析率", "固件完整性校验",
            "逆向复杂度", "时钟频率估算", "功耗分析"]


__all__ = [
    "信号频率分析", "协议解析率", "固件完整性校验",
    "逆向复杂度", "时钟频率估算", "功耗分析",
    "_register_hardware_reverse", "_hardware_reverse_symtab_names",
]
