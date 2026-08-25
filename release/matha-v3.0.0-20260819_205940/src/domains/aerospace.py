# -*- coding: utf-8 -*-
"""Matha 航空航天领域模块：轨道力学、推进系统、结构分析、热防护。

覆盖：
  1) 轨道速度计算
  2) 推进剂消耗率
  3) 结构强度系数
  4) 热防护质量
  5) 再入角估算
  6) 比冲
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


GM_EARTH = 3.986e14   # m³/s²
R_EARTH = 6371000     # m


def _轨道速度计算(轨道高度_km):
    """圆轨道速度 v = sqrt(GM/(R+h))。"""
    r = (R_EARTH + 轨道高度_km * 1000)
    if r <= 0:
        return 0.0
    return math.sqrt(GM_EARTH / r)


def _推进剂消耗率(推力_N, 比冲_s):
    """推进剂质量流率 kg/s。"""
    if 比冲_s <= 0:
        return float('inf')
    return 推力_N / (比冲_s * 9.81)


def _结构强度系数(材料强度_MPa, 载荷_MPa):
    """结构强度安全系数。"""
    if 载荷_MPa <= 0:
        return float('inf')
    return 材料强度_MPa / 载荷_MPa


def _热防护质量(热流密度_W_m2, 面积_m2, 防护材料热容_J_kgK):
    """热防护系统质量估算。"""
    if 防护材料热容_J_kgK <= 0:
        return float('inf')
    总热量 = 热流密度_W_m2 * 面积_m2 * 30  # 30秒再入
    return 总热量 / (防护材料热容_J_kgK * 500)  # 温升500K


def _再入角估算(轨道速度_ms, 目标高度_m):
    """再入角估算（度）。"""
    if 轨道速度_ms <= 0:
        return 0.0
    速度比 = 轨道速度_ms / math.sqrt(GM_EARTH / (R_EARTH * 1000))
    return math.degrees(math.asin(1 / 速度比)) * 0.5


def _比冲(推力_N, 质量流率_kg_s):
    """比冲 Isp = F/(ṁ·g₀)。"""
    if 质量流率_kg_s <= 0:
        return 0.0
    return 推力_N / (质量流率_kg_s * 9.81)


# ============================================================
# 注册
# ============================================================

def _register_aerospace(builtins: dict) -> None:
    builtins["轨道速度计算"] = _curry1(_轨道速度计算)
    builtins["推进剂消耗率"] = _curry2(_推进剂消耗率)
    builtins["结构强度系数"] = _curry2(_结构强度系数)
    builtins["热防护质量"] = _curry3(_热防护质量)
    builtins["再入角估算"] = _curry2(_再入角估算)
    builtins["比冲"] = _curry2(_比冲)


def _aerospace_symtab_names() -> list[str]:
    return ["轨道速度计算", "推进剂消耗率", "结构强度系数",
            "热防护质量", "再入角估算", "比冲"]


__all__ = [
    "轨道速度计算", "推进剂消耗率", "结构强度系数",
    "热防护质量", "再入角估算", "比冲",
    "_register_aerospace", "_aerospace_symtab_names",
]
