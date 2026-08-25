# -*- coding: utf-8 -*-
"""Matha 自动驾驶领域模块：碰撞预测、路径规划、感知融合、决策控制。

覆盖：
  1) 碰撞时间估算
  2) 路径规划复杂度
  3) 传感器融合误差
  4) 决策响应时间
  5) 定位精度
  6) 油耗估算
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


def _碰撞时间估算(距离_m, 相对速度_ms):
    """碰撞时间 TTC = d/v。"""
    if 相对速度_ms <= 0:
        return float('inf')
    return 距离_m / 相对速度_ms


def _路径规划复杂度(网格数, 分支因子):
    """A*路径规划最坏情况复杂度。"""
    if 网格数 <= 0 or 分支因子 <= 0:
        return 0
    return 网格数 * math.log(分支因子)


def _传感器融合误差(传感器误差_list):
    """多传感器融合后误差（协方差近似）。"""
    if not 传感器误差_list:
        return 0.0
    n = len(传感器误差_list)
    harmonic_mean = n / sum(1/e for e in 传感器误差_list if e > 0)
    return harmonic_mean / math.sqrt(n) if n > 0 else 0.0


def _决策响应时间(感知延迟_ms, 计算延迟_ms, 执行延迟_ms):
    """决策总响应时间。"""
    return 感知延迟_ms + 计算延迟_ms + 执行延迟_ms


def _定位精度(卫星数, PDOP):
    """GNSS定位精度估算（米）。"""
    if 卫星数 < 4 or PDOP <= 0:
        return float('inf')
    return PDOP * 2.5  # 单点定位误差约2.5m


def _油耗估算(车重_kg, 风阻系数, 速度_kmh, 路况):
    """油耗估算（L/100km）。"""
    滚动阻力 = 车重_kg * 9.81 * 0.015
    空气阻力 = 0.5 * 1.225 * 风阻系数 * 0.25 * (速度_kmh / 3.6) ** 2
    总阻力 = 滚动阻力 + 空气阻力
    路况系数 = {"平坦": 1.0, "上坡": 1.3, "拥堵": 1.5}.get(路况, 1.0)
    return 总阻力 * 速度_kmh * 路况系数 / 1000 * 0.08


# ============================================================
# 注册
# ============================================================

def _register_autonomous(builtins: dict) -> None:
    builtins["碰撞时间估算"] = _curry2(_碰撞时间估算)
    builtins["路径规划复杂度"] = _curry2(_路径规划复杂度)
    builtins["传感器融合误差"] = _curry1(_传感器融合误差)
    builtins["决策响应时间"] = _curry3(_决策响应时间)
    builtins["定位精度"] = _curry2(_定位精度)
    builtins["油耗估算"] = _curry4(_油耗估算)


def _autonomous_symtab_names() -> list[str]:
    return ["碰撞时间估算", "路径规划复杂度", "传感器融合误差",
            "决策响应时间", "定位精度", "油耗估算"]


__all__ = [
    "碰撞时间估算", "路径规划复杂度", "传感器融合误差",
    "决策响应时间", "定位精度", "油耗估算",
    "_register_autonomous", "_autonomous_symtab_names",
]
