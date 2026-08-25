# -*- coding: utf-8 -*-
"""Matha 图形学领域模块：图形变换、渲染管线、几何计算、颜色空间。

覆盖：
  1) 齐次变换矩阵
  2) 投影变换
  3) 裁剪区域
  4) 光栅化点数
  5) 颜色空间转换
  6) 抗锯齿系数
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


def _齐次变换矩阵(旋转角, 平移_x, 平移_y, 缩放):
    """生成2D齐次变换矩阵。"""
    c, s = math.cos(旋转角), math.sin(旋转角)
    return [
        [缩放 * c, -缩放 * s, 平移_x],
        [缩放 * s, 缩放 * c, 平移_y],
        [0, 0, 1]
    ]


def _投影变换(视锥_near, 视锥_far, fov_deg):
    """透视投影参数。"""
    if 视锥_near <= 0 or 视锥_far <= 0 or 视锥_near >= 视锥_far:
        return {}
    fov_rad = math.radians(fov_deg)
    f = 1.0 / math.tan(fov_rad / 2)
    return {"f": f, "near": 视锥_near, "far": 视锥_far,
            "range": 视锥_far - 视锥_near}


def _裁剪区域(边界_x_min, 边界_y_min, 边界_x_max, 边界_y_max):
    """裁剪区域面积。"""
    w = max(0, 边界_x_max - 边界_x_min)
    h = max(0, 边界_y_max - 边界_y_min)
    return w * h


def _光栅化点数(宽度_px, 高度_px, 抗锯齿等级):
    """光栅化后像素点数。"""
    if 抗锯齿等级 <= 0:
        return 宽度_px * 高度_px
    return 宽度_px * 高度_px * 抗锯齿等级 * 抗锯齿等级


def _颜色空间转换(R, G, B):
    """RGB转HSV。"""
    r, g, b = R / 255.0, G / 255.0, B / 255.0
    Cmax = max(r, g, b)
    Cmin = min(r, g, b)
    delta = Cmax - Cmin
    V = Cmax
    S = delta / Cmax if Cmax > 0 else 0
    if delta == 0:
        H = 0
    elif Cmax == r:
        H = 60 * (((g - b) / delta) % 6)
    elif Cmax == g:
        H = 60 * (((b - r) / delta) + 2)
    else:
        H = 60 * (((r - g) / delta) + 4)
    return {"H": H, "S": S, "V": V}


def _抗锯齿系数(采样数):
    """抗锯齿质量系数。"""
    if 采样数 <= 0:
        return 0.0
    return math.sqrt(采样数) / math.log(采样数 + 1)


# ============================================================
# 注册
# ============================================================

def _register_graphics(builtins: dict) -> None:
    builtins["齐次变换矩阵"] = _curry4(_齐次变换矩阵)
    builtins["投影变换"] = _curry3(_投影变换)
    builtins["裁剪区域"] = _curry4(_裁剪区域)
    builtins["光栅化点数"] = _curry3(_光栅化点数)
    builtins["颜色空间转换"] = _curry3(_颜色空间转换)
    builtins["抗锯齿系数"] = _curry1(_抗锯齿系数)


def _graphics_symtab_names() -> list[str]:
    return ["齐次变换矩阵", "投影变换", "裁剪区域",
            "光栅化点数", "颜色空间转换", "抗锯齿系数"]


__all__ = [
    "齐次变换矩阵", "投影变换", "裁剪区域",
    "光栅化点数", "颜色空间转换", "抗锯齿系数",
    "_register_graphics", "_graphics_symtab_names",
]
