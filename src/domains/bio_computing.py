# -*- coding: utf-8 -*-
"""Matha 生物计算领域模块：生物信息学、基因组学、蛋白质结构、系统生物学。

覆盖：
  1) GC含量计算
  2) 分子质量估算
  3) 蛋白折叠能量
  4) 序列比对得分
  5) 系统稳定性
  6) 代谢通量
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

def _curry5(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d): return lambda e: func(a, b, c, d, e)
                return w4
            return w3
        return w2
    return w1


def _GC含量计算(序列):
    """DNA序列GC含量（%）。"""
    if not 序列:
        return 0.0
    gc = sum(1 for c in 序列.upper() if c in 'GC')
    return gc / len(序列) * 100


def _分子质量估算(氨基酸序列):
    """蛋白质分子质量估算（Da）。"""
    avg_aa_mass = 110  # 平均氨基酸残基质量
    return len(氨基酸序列) * avg_aa_mass


def _蛋白折叠能量(序列长度, 疏水比例):
    """简化蛋白折叠自由能估算（kcal/mol）。"""
    if 序列长度 <= 0:
        return 0.0
    return -1.5 * 序列长度 * 疏水比例


def _序列比对得分(序列1, 序列2, 匹配奖, 错配罚, 空位罚):
    """序列比对打分（简化版）。"""
    if not 序列1 or not 序列2:
        return 0
    匹配数 = sum(1 for a, b in zip(序列1, 序列2) if a == b)
    长度 = max(len(序列1), len(序列2))
    return 匹配数 * 匹配奖 - (长度 - 匹配数) * 错配罚


def _系统稳定性(反馈强度, 延迟, 阻尼):
    """控制理论系统稳定性判据。"""
    if 延迟 <= 0 or 阻尼 <= 0:
        return 0.0
    相位裕度 = math.atan(阻尼 / (反馈强度 * 延迟))
    return max(0.0, 相位裕度 / (math.pi / 2)) * 100


def _代谢通量(酶浓度, Km, Vmax, 底物浓度):
    """Michaelis-Menten代谢通量。"""
    if Km <= 0:
        return 0.0
    return Vmax * 底物浓度 / (Km + 底物浓度)


# ============================================================
# 注册
# ============================================================

def _register_bio_computing(builtins: dict) -> None:
    builtins["GC含量计算"] = _curry1(_GC含量计算)
    builtins["分子质量估算"] = _curry1(_分子质量估算)
    builtins["蛋白折叠能量"] = _curry2(_蛋白折叠能量)
    builtins["序列比对得分"] = _curry5(_序列比对得分)
    builtins["系统稳定性"] = _curry3(_系统稳定性)
    builtins["代谢通量"] = _curry4(_代谢通量)


def _bio_computing_symtab_names() -> list[str]:
    return ["GC含量计算", "分子质量估算", "蛋白折叠能量",
            "序列比对得分", "系统稳定性", "代谢通量"]


__all__ = [
    "GC含量计算", "分子质量估算", "蛋白折叠能量",
    "序列比对得分", "系统稳定性", "代谢通量",
    "_register_bio_computing", "_bio_computing_symtab_names",
]
