# -*- coding: utf-8 -*-
"""Matha 空间元数据领域模块：空间索引、元数据管理、地理编码、坐标变换。

覆盖：
  1) 空间索引效率
  2) 元数据查询延迟
  3) 地理编码精度
  4) 坐标变换误差
  5) 边界框交集
  6) 缓冲区分析
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


def _空间索引效率(要素数, 索引深度):
    """空间索引查询效率估算。"""
    if 索引深度 <= 0 or 要素数 <= 0:
        return 0.0
    return math.log(要素数) / 索引深度


def _元数据查询延迟(元数据量_MB, 索引大小_MB):
    """元数据查询延迟（ms）。"""
    if 索引大小_MB <= 0:
        return float('inf')
    return 元数据量_MB / 索引大小_MB * 10


def _地理编码精度(坐标系统, 分辨率_m):
    """地理编码精度（米）。"""
    return 分辨率_m


def _坐标变换误差(源精度_m, 目标精度_m, 变换次数):
    """累积坐标变换误差。"""
    if 源精度_m <= 0 or 目标精度_m <= 0:
        return 0.0
    return math.sqrt(变换次数) * math.sqrt(源精度_m ** 2 + 目标精度_m ** 2)


def _边界框交集(bbox1_xmin, bbox1_ymin, bbox1_xmax, bbox1_ymax,
                 bbox2_xmin, bbox2_ymin, bbox2_xmax, bbox2_ymax):
    """两个边界框是否相交。"""
    return (bbox1_xmin <= bbox2_xmax and bbox1_xmax >= bbox2_xmin and
            bbox1_ymin <= bbox2_ymax and bbox1_ymax >= bbox2_ymin)


def _缓冲区分析(中心_x, 中心_y, 半径_m, 目标点_x, 目标点_y):
    """目标点是否在缓冲区内。"""
    dx = 目标点_x - 中心_x
    dy = 目标点_y - 中心_y
    return math.sqrt(dx * dx + dy * dy) <= 半径_m


# ============================================================
# 注册
# ============================================================

def _curry8(func):
    """八参数柯里化。"""
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    def w5(e):
                        def w6(f):
                            def w7(g):
                                return lambda h: func(a, b, c, d, e, f, g, h)
                            return w7
                        return w6
                    return w5
                return w4
            return w3
        return w2
    return w1


def _register_spatial_meta(builtins: dict) -> None:
    builtins["空间索引效率"] = _curry2(_空间索引效率)
    builtins["元数据查询延迟"] = _curry2(_元数据查询延迟)
    builtins["地理编码精度"] = _curry2(_地理编码精度)
    builtins["坐标变换误差"] = _curry3(_坐标变换误差)
    builtins["边界框交集"] = _curry8(_边界框交集)
    builtins["缓冲区分析"] = _curry3(_缓冲区分析)


def _spatial_meta_symtab_names() -> list[str]:
    return ["空间索引效率", "元数据查询延迟", "地理编码精度",
            "坐标变换误差", "边界框交集", "缓冲区分析"]


__all__ = [
    "空间索引效率", "元数据查询延迟", "地理编码精度",
    "坐标变换误差", "边界框交集", "缓冲区分析",
    "_register_spatial_meta", "_spatial_meta_symtab_names",
]


def _curry8(func):
    """八参数柯里化。"""
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    def w5(e):
                        def w6(f):
                            def w7(g):
                                return lambda h: func(a, b, c, d, e, f, g, h)
                            return w7
                        return w6
                    return w5
                return w4
            return w3
        return w2
    return w1