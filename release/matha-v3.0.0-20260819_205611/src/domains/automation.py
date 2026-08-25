# -*- coding: utf-8 -*-
"""Matha 自动化领域模块：PLC控制、传感器采集、执行器驱动、时序控制。

覆盖：
  1) PLC扫描周期估算
  2) 传感器采样率与精度
  3) 执行器响应时间
  4) 时序约束满足分析
  5) 自动化流程执行效率
  6) 异常检测率估算
"""

from __future__ import annotations
import math


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

def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c): return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1

def _curry5(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d): return lambda e: func(a, b, c, d, e)
                return w4
            return w3
        return w2
    return w1


# ============================================================
# 核心函数
# ============================================================

def _PLC扫描周期估算(iO点数, 扫描指令数, 指令周期_ns):
    """PLC扫描周期 T = I/O耗时 + 指令执行耗时。"""
    io_time = iO点数 * 50e3   # 每点50μs
    instr_time = 扫描指令数 * 指令周期_ns * 1e-3
    return io_time + instr_time


def _传感器采样率(噪声密度, 带宽, 分辨率_bit):
    """根据噪声和带宽估算有效采样率。"""
    if 带宽 <= 0 or 分辨率_bit <= 0:
        return 0.0
    snr = 6.02 * 分辨率_bit + 1.76
    return 带宽 * (snr / 100.0)


def _执行器响应时间(类型, 负载_kg, 行程_mm):
    """执行器响应时间估算（ms）。"""
    base = {"气动": 50, "电动": 20, "液压": 100}.get(类型, 50)
    return base * (1 + 负载_kg / 100) * (1 + 行程_mm / 1000)


def _时序约束满足(周期_ms, 执行时间_ms, 开销_ms):
    """判断时序约束是否满足。"""
    return 执行时间_ms + 开销_ms <= 周期_ms


def _自动化流程执行效率(步骤数, 平均步时长_ms, 并行度):
    """自动化流程执行效率（吞吐率）。"""
    if 并行度 <= 0:
        return 0.0
    串行时间 = 步骤数 * 平均步时长_ms
    并行时间 = 串行时间 / 并行度
    return 步骤数 / (并行时间 * 1e-3) if 并行时间 > 0 else 0.0


def _异常检测率(误报率, 漏报率, 样本数):
    """异常检测综合率。"""
    if 样本数 <= 0:
        return 0.0
    正确率 = 1 - 误报率 - 漏报率
    return max(0.0, min(1.0, 正确率))


# ============================================================
# 注册
# ============================================================

def _register_automation(builtins: dict) -> None:
    builtins["PLC扫描周期"] = _curry3(_PLC扫描周期估算)
    builtins["传感器采样率"] = _curry3(_传感器采样率)
    builtins["执行器响应时间"] = _curry3(_执行器响应时间)
    builtins["时序约束满足"] = _curry3(_时序约束满足)
    builtins["自动化流程效率"] = _curry3(_自动化流程执行效率)
    builtins["异常检测率"] = _curry3(_异常检测率)


def _automation_symtab_names() -> list[str]:
    return ["PLC扫描周期", "传感器采样率", "执行器响应时间",
            "时序约束满足", "自动化流程效率", "异常检测率"]


__all__ = [
    "PLC扫描周期估算", "传感器采样率", "执行器响应时间",
    "时序约束满足", "自动化流程效率", "异常检测率",
    "_register_automation", "_automation_symtab_names",
]
