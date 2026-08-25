# -*- coding: utf-8 -*-
"""Matha 元宇宙架构领域模块：渲染引擎、物理模拟、用户交互。

覆盖：
  1) 渲染帧率估算
  2) 物理模拟步长
  3) 碰撞检测复杂度
  4) 用户并发数
  5) 资产加载延迟
  6) 网络同步延迟
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


def _渲染帧率估算(三角形数, 像素数, 每三角形耗时_ns):
    """渲染帧率估算（FPS）。"""
    总耗时_ns = 三角形数 * 像素数 / 1e6 * 每三角形耗时_ns
    if 总耗时_ns <= 0:
        return 0
    return min(240, int(1e9 / 总耗时_ns))


def _物理模拟步长(物体数, 约束数, 可用算力_MFlops):
    """物理模拟最大稳定步长（ms）。"""
    if 可用算力_MFlops <= 0:
        return 0.0
    计算量 = (物体数 * 1000 + 约束数 * 500) / 可用算力_MFlops  # ms
    return min(33.3, max(1.0, 计算量))


def _碰撞检测复杂度(物体数):
    """O(n²)碰撞检测复杂度估算。"""
    return 物体数 * (物体数 - 1) / 2


def _用户并发数(服务器带宽_Gbps, 每用户带宽_Mbps):
    """最大并发用户数估算。"""
    if 每用户带宽_Mbps <= 0:
        return 0
    return int(服务器带宽_Gbps * 1000 / 每用户带宽_Mbps)


def _资产加载延迟(资产大小_MB, 网络带宽_Mbps, 压缩率):
    """资产加载延迟（ms）。"""
    有效大小 = 资产大小_MB * (1 - 压缩率)
    if 网络带宽_Mbps <= 0:
        return float('inf')
    return 有效大小 * 8 / 网络带宽_Mbps * 1000


def _网络同步延迟(往返时间_ms, 插值窗口_ms):
    """网络同步后延迟（ms）。"""
    return 往返时间_ms + 插值窗口_ms


# ============================================================
# 注册
# ============================================================

def _register_metaverse_arch(builtins: dict) -> None:
    builtins["渲染帧率估算"] = _curry3(_渲染帧率估算)
    builtins["物理模拟步长"] = _curry3(_物理模拟步长)
    builtins["碰撞检测复杂度"] = _curry1(_碰撞检测复杂度)
    builtins["用户并发数"] = _curry2(_用户并发数)
    builtins["资产加载延迟"] = _curry3(_资产加载延迟)
    builtins["网络同步延迟"] = _curry2(_网络同步延迟)


def _metaverse_arch_symtab_names() -> list[str]:
    return ["渲染帧率估算", "物理模拟步长", "碰撞检测复杂度",
            "用户并发数", "资产加载延迟", "网络同步延迟"]


__all__ = [
    "渲染帧率估算", "物理模拟步长", "碰撞检测复杂度",
    "用户并发数", "资产加载延迟", "网络同步延迟",
    "_register_metaverse_arch", "_metaverse_arch_symtab_names",
]
