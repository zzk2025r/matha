# -*- coding: utf-8 -*-
"""Matha HPC领域模块：并行计算、负载均衡、通信开销、加速比。

覆盖：
  1) Amdahl加速比
  2) 并行效率
  3) 通信延迟估算
  4) 负载均衡度
  5) 内存带宽利用率
  6) 浮点运算峰值
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


def _Amdahl加速比(串行比例, 核心数):
    """Amdahl定律加速比 S = 1/(s + p/n)。"""
    if 核心数 <= 0 or 串行比例 < 0 or 串行比例 > 1:
        return 0.0
    并行比例 = 1 - 串行比例
    return 1.0 / (串行比例 + 并行比例 / 核心数)


def _并行效率(加速比, 核心数):
    """并行效率 E = S/n。"""
    if 核心数 <= 0:
        return 0.0
    return 加速比 / 核心数 * 100


def _通信延迟估算(消息数, 消息大小_bytes, 带宽_Gbps):
    """通信总延迟（ms）。"""
    if 带宽_Gbps <= 0:
        return float('inf')
    总数据 = 消息数 * 消息大小_bytes * 8  # bits
    return 总数据 / (带宽_Gbps * 1e9) * 1000


def _负载均衡度(任务列表):
    """负载均衡度（标准差/均值）。越低越均衡。"""
    if not 任务列表:
        return 0.0
    n = len(任务列表)
    avg = sum(任务列表) / n
    if avg <= 0:
        return 0.0
    variance = sum((x - avg) ** 2 for x in 任务列表) / n
    return math.sqrt(variance) / avg * 100


def _内存带宽利用率(访问次数, 数据量_GB, 时间_s):
    """内存带宽利用率（%）。"""
    if 时间_s <= 0:
        return 0.0
    实际带宽 = 数据量_GB / 时间_s
    理论带宽 = 64.0  # GB/s DDR4
    return min(100.0, 实际带宽 / 理论带宽 * 100)


def _浮点运算峰值(核心数, 频率_GHz, FLOPS_per_cycle):
    """峰值浮点运算能力（TFLOPS）。"""
    return 核心数 * 频率_GHz * FLOPS_per_cycle / 1e12


# ============================================================
# 注册
# ============================================================

def _register_hpc(builtins: dict) -> None:
    builtins["Amdahl加速比"] = _curry2(_Amdahl加速比)
    builtins["并行效率"] = _curry2(_并行效率)
    builtins["通信延迟估算"] = _curry3(_通信延迟估算)
    builtins["负载均衡度"] = _curry1(_负载均衡度)
    builtins["内存带宽利用率"] = _curry3(_内存带宽利用率)
    builtins["浮点运算峰值"] = _curry3(_浮点运算峰值)


def _hpc_symtab_names() -> list[str]:
    return ["Amdahl加速比", "并行效率", "通信延迟估算",
            "负载均衡度", "内存带宽利用率", "浮点运算峰值"]


__all__ = [
    "Amdahl加速比", "并行效率", "通信延迟估算",
    "负载均衡度", "内存带宽利用率", "浮点运算峰值",
    "_register_hpc", "_hpc_symtab_names",
]
