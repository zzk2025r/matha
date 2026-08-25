# -*- coding: utf-8 -*-
"""Matha 算法交易领域模块：量化策略、回测引擎、风险管控、执行算法。

覆盖：
  1) 策略夏普比率
  2) 最大回撤估算
  3) 订单执行成本
  4) 滑点估算
  5) 波动率预测
  6) 相关性矩阵
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


def _策略夏普比率(策略收益_list, 无风险利率):
    """策略夏普比率。"""
    if not 策略收益_list:
        return 0.0
    avg = sum(策略收益_list) / len(策略收益_list)
    variance = sum((r - avg) ** 2 for r in 策略收益_list) / len(策略收益_list)
    std = math.sqrt(variance) if variance > 0 else 0
    if std <= 0:
        return 0.0
    return (avg - 无风险利率) / std


def _最大回撤估算(净值序列):
    """最大回撤（%）。"""
    if not 净值序列:
        return 0.0
    peak = 净值序列[0]
    max_dd = 0.0
    for v in 净值序列:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return max_dd * 100


def _订单执行成本(订单金额, 买卖价差, 市场冲击):
    """订单执行成本。"""
    spread_cost = 订单金额 * 买卖价差 / 2
    impact_cost = 订单金额 * 市场冲击
    return spread_cost + impact_cost


def _滑点估算(订单量, 市场深度, 价格波动率):
    """滑点估算（基点）。"""
    if 市场深度 <= 0:
        return 0.0
    return 订单量 / 市场深度 * 价格波动率 * 10000


def _波动率预测(历史收益率_list, 预测期):
    """波动率预测（年化）。"""
    if not 历史收益率_list or len(历史收益率_list) < 2:
        return 0.0
    avg = sum(历史收益率_list) / len(历史收益率_list)
    var = sum((r - avg) ** 2 for r in 历史收益率_list) / (len(历史收益率_list) - 1)
    daily_vol = math.sqrt(var)
    return daily_vol * math.sqrt(252) * 预测期


def _相关性矩阵(资产收益1, 资产收益2):
    """计算两资产相关系数。"""
    if not 资产收益1 or not 资产收益2 or len(资产收益1) != len(资产收益2):
        return 0.0
    n = len(资产收益1)
    avg1 = sum(资产收益1) / n
    avg2 = sum(资产收益2) / n
    cov = sum((a - avg1) * (b - avg2) for a, b in zip(资产收益1, 资产收益2)) / n
    std1 = math.sqrt(sum((a - avg1) ** 2 for a in 资产收益1) / n)
    std2 = math.sqrt(sum((b - avg2) ** 2 for b in 资产收益2) / n)
    if std1 <= 0 or std2 <= 0:
        return 0.0
    return cov / (std1 * std2)


# ============================================================
# 注册
# ============================================================

def _register_algo_trading(builtins: dict) -> None:
    builtins["策略夏普比率"] = _curry2(_策略夏普比率)
    builtins["最大回撤估算"] = _curry1(_最大回撤估算)
    builtins["订单执行成本"] = _curry3(_订单执行成本)
    builtins["滑点估算"] = _curry3(_滑点估算)
    builtins["波动率预测"] = _curry2(_波动率预测)
    builtins["相关性矩阵"] = _curry2(_相关性矩阵)


def _algo_trading_symtab_names() -> list[str]:
    return ["策略夏普比率", "最大回撤估算", "订单执行成本",
            "滑点估算", "波动率预测", "相关性矩阵"]


__all__ = [
    "策略夏普比率", "最大回撤估算", "订单执行成本",
    "滑点估算", "波动率预测", "相关性矩阵",
    "_register_algo_trading", "_algo_trading_symtab_names",
]
