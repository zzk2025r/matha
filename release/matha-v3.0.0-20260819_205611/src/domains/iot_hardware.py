# -*- coding: utf-8 -*-
"""Matha IoT硬件领域模块：MQTT通信、传感器网络、边缘计算、设备管理。

覆盖：
  1) MQTT消息大小估算
  2) 传感器网络覆盖半径
  3) 边缘计算延迟
  4) 设备在线率估算
  5) 数据聚合效率
  6) 功耗预算分析
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


def _MQTT消息大小估算(主题长度, 载荷字节, QoS等级):
    """MQTT消息总大小（字节）。"""
    header = 2 + 2 + len(主题长度.encode()) + 1
    payload = 载荷字节
    qos_overhead = {"none": 0, "at_least_once": 2, "exactly_once": 4}.get(
        "none" if QoS等级 == 0 else "at_least_once" if QoS等级 == 1 else "exactly_once", 0)
    return header + payload + qos_overhead


def _传感器覆盖半径(发射功率_dBm, 灵敏度_dBm, 频率_GHz):
    """自由空间路径损耗模型估算覆盖半径（米）。"""
    if 频率_GHz <= 0:
        return 0.0
    Pt = 10 ** (发射功率_dBm / 10)
    Pr = 10 ** (灵敏度_dBm / 10)
    freq = 频率_GHz * 1e9
    # FSPL = (4πd/λ)² → d = λ/(4π) * 10^((Pt_Pr)/20)
    wavelength = 3e8 / freq
    if Pr <= 0:
        return 0.0
    return wavelength / (4 * math.pi) * (10 ** ((math.log10(Pt) - math.log10(max(Pr, 1e-20))) / 20))


def _边缘延迟计算(任务数, 每任务计算_ms, 网络延迟_ms):
    """边缘计算总延迟。"""
    return 任务数 * 每任务计算_ms + 网络延迟_ms


def _设备在线率(总设备数, 离线设备数, 监控周期_h):
    """设备在线率估算。"""
    if 总设备数 <= 0:
        return 0.0
    return (总设备数 - 离线设备数) / 总设备数


def _数据聚合效率(源数据量_MB, 聚合后量_MB, 压缩算法):
    """数据聚合效率。"""
    if 源数据量_MB <= 0:
        return 0.0
    return (1 - 聚合后量_MB / 源数据量_MB) * 100


def _功耗预算(组件列表):
    """功耗预算计算（W）。组件列表: [(功耗_W, 占空比), ...]。"""
    total = 0.0
    for 功耗, 占空比 in 组件列表:
        total += 功耗 * max(0.0, min(1.0, 占空比))
    return total


# ============================================================
# 注册
# ============================================================

def _register_iot_hardware(builtins: dict) -> None:
    builtins["MQTT消息大小"] = _curry3(_MQTT消息大小估算)
    builtins["传感器覆盖半径"] = _curry3(_传感器覆盖半径)
    builtins["边缘延迟"] = _curry3(_边缘延迟计算)
    builtins["设备在线率"] = _curry3(_设备在线率)
    builtins["数据聚合效率"] = _curry3(_数据聚合效率)
    builtins["功耗预算"] = _功耗预算


def _iot_hardware_symtab_names() -> list[str]:
    return ["MQTT消息大小", "传感器覆盖半径", "边缘延迟",
            "设备在线率", "数据聚合效率", "功耗预算"]


__all__ = [
    "MQTT消息大小估算", "传感器覆盖半径", "边缘延迟计算",
    "设备在线率", "数据聚合效率", "功耗预算",
    "_register_iot_hardware", "_iot_hardware_symtab_names",
]
