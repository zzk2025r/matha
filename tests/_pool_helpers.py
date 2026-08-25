# -*- coding: utf-8 -*-
"""Matha ProcessPool 并行计算测试专用模块。
用于解决 multiprocessing 无法 pickle 局部函数的问题。"""
from __future__ import annotations


def _compute_double(x: int) -> int:
    """并行计算：乘以2。"""
    return x * 2


def _compute_square(x: int) -> int:
    """并行计算：平方。"""
    return x * x


def _computeheavy(x: int) -> int:
    """并行计算：重计算。"""
    total = 0
    for i in range(100000):
        total += i * x
    return total
