# -*- coding: utf-8 -*-
"""Matha 金融科技领域模块：期权定价、风险管理、量化交易、信用评级。

覆盖：
  1) Black-Scholes期权定价
  2) VaR风险价值
  3) 夏普比率
  4) 信用评分
  5) 流动性覆盖率
  6) 杠杆率
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


def _BlackScholes期权定价(S, K, T, r, sigma):
    """Black-Scholes欧式看涨期权定价。"""
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    from math import erf
    Nd1 = 0.5 * (1 + erf(d1 / math.sqrt(2)))
    Nd2 = 0.5 * (1 + erf(d2 / math.sqrt(2)))
    return S * Nd1 - K * math.exp(-r * T) * Nd2


def _VaR风险价值(组合价值, 日收益率标准差, 置信水平, 持有期天):
    """VaR风险价值估算。"""
    z_scores = {0.90: 1.28, 0.95: 1.645, 0.99: 2.326}
    z = z_scores.get(置信水平, 1.645)
    return 组合价值 * z * 日收益率标准差 * math.sqrt(持有期天)


def _夏普比率(超额收益, 波动率):
    """夏普比率 = (R-Rf)/σ。"""
    if 波动率 <= 0:
        return 0.0
    return 超额收益 / 波动率


def _信用评分(负债率, 收入稳定性, 逾期次数, 信用历史年限):
    """简化信用评分（0-100）。"""
    if 信用历史年限 <= 0:
        return 0
    基础分 = 70
    负债惩罚 = 负债率 * 30
    逾期惩罚 = 逾期次数 * 10
    历史奖励 = min(20, 信用历史年限 * 2)
    稳定奖励 = 收入稳定性 * 10
    return max(0, min(100, 基础分 - 负债惩罚 - 逾期惩罚 + 历史奖励 + 稳定奖励))


def _流动性覆盖率(优质流动资产, 净现金流出):
    """LCR = HQLA / 净现金流出。"""
    if 净现金流出 <= 0:
        return float('inf')
    return 优质流动资产 / 净现金流出 * 100


def _杠杆率(总资产, 权益资本):
    """杠杆率 = 权益资本 / 总资产。"""
    if 总资产 <= 0:
        return 0.0
    return 权益资本 / 总资产 * 100


# ============================================================
# 注册
# ============================================================

def _register_fintech(builtins: dict) -> None:
    builtins["BlackScholes期权定价"] = _curry5(_BlackScholes期权定价)
    builtins["VaR风险价值"] = _curry4(_VaR风险价值)
    builtins["夏普比率"] = _curry2(_夏普比率)
    builtins["信用评分"] = _curry4(_信用评分)
    builtins["流动性覆盖率"] = _curry2(_流动性覆盖率)
    builtins["杠杆率"] = _curry2(_杠杆率)


def _fintech_symtab_names() -> list[str]:
    return ["BlackScholes期权定价", "VaR风险价值", "夏普比率",
            "信用评分", "流动性覆盖率", "杠杆率"]


__all__ = [
    "BlackScholes期权定价", "VaR风险价值", "夏普比率",
    "信用评分", "流动性覆盖率", "杠杆率",
    "_register_fintech", "_fintech_symtab_names",
]
