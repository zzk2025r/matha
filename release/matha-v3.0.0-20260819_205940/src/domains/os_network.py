# -*- coding: utf-8 -*-
"""Matha OS与网络领域模块：进程调度、内存管理、文件系统、网络协议。

覆盖：
  1) 进程调度等待时间
  2) 内存页表开销
  3) 文件系统碎片率
  4) TCP重传率估算
  5) DNS查询延迟
  6) 网络带宽利用率
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


def _进程调度等待时间(进程数, 时间片_ms, 优先级数):
    """FIFO/RR调度等待时间估算。"""
    if 进程数 <= 0 or 优先级数 <= 0:
        return 0.0
    return 进程数 * 时间片_ms / 优先级数


def _内存页表开销(内存大小_MB, 页面大小_kb):
    """页表内存开销（KB）。"""
    if 页面大小_kb <= 0:
        return 0.0
    页数 = 内存大小_MB * 1024 / 页面大小_kb
    return 页数 * 4  # 每页表项4字节


def _文件碎片率(已用块数, 总块数, 连续块数):
    """文件系统碎片率。"""
    if 总块数 <= 0:
        return 0.0
    return (1 - 连续块数 / 已用块数) * 100 if 已用块数 > 0 else 0.0


def _TCP重传率(丢包率, 重传阈值):
    """TCP重传率估算。"""
    if 丢包率 <= 0 or 丢包率 >= 1:
        return 0.0
    return 1 - (1 - 丢包率) ** 重传阈值


def _DNS查询延迟(服务器距离_km, 解析跳数):
    """DNS查询延迟（ms）。光速传输+每跳处理延迟。"""
    传输延迟 = 服务器距离_km / 3e5 * 2  # 往返
    处理延迟 = 解析跳数 * 5  # 每跳5ms
    return 传输延迟 + 处理延迟


def _带宽利用率(吞吐量_Mbps, 链路容量_Mbps):
    """带宽利用率（%）。"""
    if 链路容量_Mbps <= 0:
        return 0.0
    return min(100.0, 吞吐量_Mbps / 链路容量_Mbps * 100)


# ============================================================
# 注册
# ============================================================

def _register_os_network(builtins: dict) -> None:
    builtins["进程调度等待"] = _curry3(_进程调度等待时间)
    builtins["内存页表开销"] = _curry2(_内存页表开销)
    builtins["文件碎片率"] = _curry3(_文件碎片率)
    builtins["TCP重传率"] = _curry2(_TCP重传率)
    builtins["DNS查询延迟"] = _curry2(_DNS查询延迟)
    builtins["带宽利用率"] = _curry2(_带宽利用率)


def _os_network_symtab_names() -> list[str]:
    return ["进程调度等待", "内存页表开销", "文件碎片率",
            "TCP重传率", "DNS查询延迟", "带宽利用率"]


__all__ = [
    "进程调度等待时间", "内存页表开销", "文件碎片率",
    "TCP重传率", "DNS查询延迟", "带宽利用率",
    "_register_os_network", "_os_network_symtab_names",
]
