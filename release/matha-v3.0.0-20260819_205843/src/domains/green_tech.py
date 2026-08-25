# -*- coding: utf-8 -*-
"""Matha 绿色技术领域模块：碳足迹、能效优化、可再生能源。

覆盖：
  1) 碳足迹估算
  2) 能源效率
  3) 太阳能转化率
  4) 风力发电系数
  5) 电池循环寿命
  6) 减排量计算
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


def _碳足迹估算(能源_kWh, 排放因子):
    """碳足迹（kg CO2）。"""
    return 能源_kWh * 排放因子


def _能源效率(输出能量, 输入能量):
    """能源效率（%）。"""
    if 输入能量 <= 0:
        return 0.0
    return 输出能量 / 输入能量 * 100


def _太阳能转化率(入射功率_W, 面积_m2, 效率):
    """太阳能转换功率（W）。"""
    标准日照 = 1000  # W/m²
    return 面积_m2 * 标准日照 * 效率


def _风力发电系数(风速_ms, 叶片半径_m, 空气密度):
    """风力发电功率（W）。P = 0.5·ρ·A·v³·Cp。"""
    A = math.pi * 叶片半径_m ** 2
    Cp = 0.35  # 贝茨极限
    return 0.5 * 空气密度 * A * 风速_ms ** 3 * Cp


def _电池循环寿命(容量衰减率_per_cycle, 目标容量保持率):
    """电池循环寿命估算。"""
    if 容量衰减率_per_cycle <= 0:
        return 0
    return int(math.log(目标容量保持率) / math.log(1 - 容量衰减率_per_cycle))


def _减排量计算(替代能源_kWh, 传统排放因子, 替代排放因子):
    """减排量（kg CO2）。"""
    return 替代能源_kWh * (传统排放因子 - 替代排放因子)


# ============================================================
# 注册
# ============================================================

def _register_green_tech(builtins: dict) -> None:
    builtins["碳足迹估算"] = _curry2(_碳足迹估算)
    builtins["能源效率"] = _curry2(_能源效率)
    builtins["太阳能转化率"] = _curry3(_太阳能转化率)
    builtins["风力发电系数"] = _curry3(_风力发电系数)
    builtins["电池循环寿命"] = _curry2(_电池循环寿命)
    builtins["减排量计算"] = _curry3(_减排量计算)


def _green_tech_symtab_names() -> list[str]:
    return ["碳足迹估算", "能源效率", "太阳能转化率",
            "风力发电系数", "电池循环寿命", "减排量计算"]


__all__ = [
    "碳足迹估算", "能源效率", "太阳能转化率",
    "风力发电系数", "电池循环寿命", "减排量计算",
    "_register_green_tech", "_green_tech_symtab_names",
]
