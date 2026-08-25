# -*- coding: utf-8 -*-
"""Matha 计算化学领域模块：分子模拟、量子化学、反应动力学。

覆盖：
  1) 分子轨道能量
  2) 反应活化能
  3) 键长计算
  4) 振动频率
  5) 热力学稳定性
  6) 溶剂化能
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


def _分子轨道能量(Z, n):
    """类氢原子轨道能量（eV）。E = -13.6 * Z² / n²。"""
    if n <= 0 or Z <= 0:
        return 0.0
    return -13.6 * Z * Z / (n * n)


def _反应活化能(温度, 指前因子, 速率常数):
    """Arrhenius方程反算活化能（kJ/mol）。Ea = R*T*ln(A/k)。"""
    if 温度 <= 0 or 速率常数 <= 0:
        return 0.0
    R = 8.314e-3  # kJ/(mol·K)
    return R * 温度 * math.log(指前因子 / 速率常数)


def _键长计算(原子1半径, 原子2半径, 键级):
    """共价键长估算（pm）。"""
    if 键级 <= 0:
        return 0.0
    return (原子1半径 + 原子2半径) / math.sqrt(键级)


def _振动频率(力常数_Nm, 约化质量_kg):
    """简谐振动频率（Hz）。"""
    if 力常数_Nm <= 0 or 约化质量_kg <= 0:
        return 0.0
    return (1 / (2 * math.pi)) * math.sqrt(力常数_Nm / 约化质量_kg)


def _热力学稳定性(生成焓_kJ, 熵_J_K, 温度_K):
    """吉布斯自由能判据。ΔG = ΔH - TΔS。"""
    if 温度_K <= 0:
        return float('inf')
    return 生成焓_kJ - 温度_K * 熵_J_K / 1000


def _溶剂化能(电荷, 半径_A, 介电常数):
    """Born溶剂化能（kJ/mol）。"""
    if 半径_A <= 0 or 介电常数 <= 0:
        return 0.0
    N_A = 6.022e23
    e = 1.602e-19
    eps0 = 8.854e-12
    return N_A * e * e * 电荷 * 电荷 / (8 * math.pi * eps0 * 半径_A * 1e-10 * 介电常数) / 1000


# ============================================================
# 注册
# ============================================================

def _register_comp_chem(builtins: dict) -> None:
    builtins["分子轨道能量"] = _curry2(_分子轨道能量)
    builtins["反应活化能"] = _curry3(_反应活化能)
    builtins["键长计算"] = _curry3(_键长计算)
    builtins["振动频率"] = _curry2(_振动频率)
    builtins["热力学稳定性"] = _curry3(_热力学稳定性)
    builtins["溶剂化能"] = _curry3(_溶剂化能)


def _comp_chem_symtab_names() -> list[str]:
    return ["分子轨道能量", "反应活化能", "键长计算",
            "振动频率", "热力学稳定性", "溶剂化能"]


__all__ = [
    "分子轨道能量", "反应活化能", "键长计算",
    "振动频率", "热力学稳定性", "溶剂化能",
    "_register_comp_chem", "_comp_chem_symtab_names",
]
