# -*- coding: utf-8 -*-
"""Matha 经济学领域模块：微观经济学 + 宏观经济学 + 金融数学。

覆盖：
  1) 微观经济学：供需均衡、弹性、边际分析、消费者剩余
  2) 宏观经济学：GDP 计算、乘数效应、通货膨胀
  3) 金融数学：复利、现值、年金、NPV、IRR 估算
"""

from __future__ import annotations
import math

# ============================================================
# 柯里化工具
# ============================================================
def _curry1(func):
    def with_first(a):
        return func(a)
    return with_first

def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1

def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1

def _curry5(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    return lambda e: func(a, b, c, d, e)
                return w4
            return w3
        return w2
    return w1


# ============================================================
# 金融数学
# ============================================================

def _复利终值(P, r, n):
    """复利终值 FV = P(1+r)^n。P: 本金, r: 年利率, n: 年数。"""
    return P * (1 + r) ** n


def _复利现值(FV, r, n):
    """复利现值 PV = FV/(1+r)^n。"""
    if n <= 0:
        return FV
    return FV / (1 + r) ** n


def _年金终值(PMT, r, n):
    """普通年金终值 FV = PMT · [(1+r)^n - 1] / r。"""
    if r == 0:
        return PMT * n
    return PMT * ((1 + r) ** n - 1) / r


def _年金现值(PMT, r, n):
    """普通年金现值 PV = PMT · [1 - (1+r)^(-n)] / r。"""
    if r == 0:
        return PMT * n
    return PMT * (1 - (1 + r) ** (-n)) / r


def _NPV(cash_flows, rate):
    """净现值 NPV = Σ CFt/(1+r)^t。cash_flows: [CF0, CF1, ...]。"""
    npv = 0.0
    for t, cf in enumerate(cash_flows):
        npv += cf / (1 + rate) ** t
    return npv


def _IRR估算(cash_flows, guess=0.1):
    """IRR 估算（牛顿法，最多 100 次迭代）。"""
    rate = guess
    for _ in range(100):
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        # 数值导数
        dpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows) if t > 0)
        if abs(dpv) < 1e-15:
            break
        new_rate = rate - npv / dpv
        if abs(new_rate - rate) < 1e-10:
            break
        rate = new_rate
    return rate


def _单利终值(P, r, t):
    """单利终值 FV = P(1 + r·t)。"""
    return P * (1 + r * t)


def _实际利率(名义利率, 通胀率):
    """费雪方程：r_real ≈ r_nominal - inflation。"""
    if 1 + 通胀率 == 0:
        return 0.0
    return (1 + 名义利率) / (1 + 通胀率) - 1


# ============================================================
# 微观经济学
# ============================================================

def _需求价格弹性(价格, 需求量, dQ_dP):
    """点弹性 Ed = (dQ/dP) · (P/Q)。"""
    if 需求量 == 0:
        return float('inf')
    return dQ_dP * (价格 / 需求量)


def _供给价格弹性(价格, 供给量, dQ_dP):
    """供给点弹性 Es = (dQ/dP) · (P/Q)。"""
    if 供给量 == 0:
        return float('inf')
    return dQ_dP * (价格 / 供给量)


def _消费者剩余(需求函数系数, 均衡价格):
    """线性需求 Q = a - bP，消费者剩余 CS = (a - b·Pe)²/(2b)。"""
    a = 需求函数系数[0]
    b = 需求函数系数[1]
    Pe = 均衡价格
    if b == 0:
        return 0.0
    Qe = a - b * Pe
    return Qe * Qe / (2 * b)


def _生产者剩余(供给函数系数, 均衡价格):
    """线性供给 Q = c + dP，生产者剩余 PS = (Pe - c/d)²·d/2。"""
    c = 供给函数系数[0]
    d = 供给函数系数[1]
    Pe = 均衡价格
    if d == 0:
        return 0.0
    Qe = c + d * Pe
    return Qe * (Pe - c / d) / 2 if d != 0 else 0.0


def _边际成本(Q, C_fixed, C_variable_per_unit):
    """边际成本 MC = dC/dQ = C_variable（线性成本）。"""
    return C_variable_per_unit


def _总成本(Q, C_fixed, C_variable_per_unit):
    """总成本 TC = FC + VC·Q。"""
    return C_fixed + C_variable_per_unit * Q


# ============================================================
# 宏观经济学
# ============================================================

def _GDP支出法(C, I, G, X, M):
    """GDP = C + I + G + (X - M)。消费+投资+政府+净出口。"""
    return C + I + G + X - M


def _GDP收入法(W, R, I_prof, Pi):
    """GDP = 工资 + 租金 + 利息 + 利润（简化版）。"""
    return W + R + I_prof + Pi


def _乘数效应(边际消费倾向):
    """投资乘数 k = 1/(1-MPC)。"""
    if 边际消费倾向 >= 1:
        return float('inf')
    return 1 / (1 - 边际消费倾向)


def _物价指数(基期价格, 报告期价格):
    """CPI = (报告期价格/基期价格) × 100。"""
    if 基期价格 == 0:
        return 0.0
    return 报告期价格 / 基期价格 * 100


def _通货膨胀率(基期CPI, 本期CPI):
    """通胀率 = (CPI_t - CPI_0) / CPI_0 × 100%。"""
    if 基期CPI == 0:
        return 0.0
    return (本期CPI - 基期CPI) / 基期CPI * 100


def _人均GDP(GDP, 人口):
    """人均 GDP = GDP / 人口。"""
    if 人口 == 0:
        return 0.0
    return GDP / 人口


# ============================================================
# 注册
# ============================================================

def _register_economics(builtins: dict) -> None:
    """将经济学领域内建注册到解释器 builtins。"""
    # 金融数学
    builtins["复利终值"] = _curry3(_复利终值)
    builtins["复利现值"] = _curry3(_复利现值)
    builtins["年金终值"] = _curry3(_年金终值)
    builtins["年金现值"] = _curry3(_年金现值)
    builtins["NPV"] = _curry2(_NPV)
    builtins["IRR"] = _curry2(_IRR估算)
    builtins["单利终值"] = _curry3(_单利终值)
    builtins["实际利率"] = _curry2(_实际利率)

    # 微观经济学
    builtins["需求价格弹性"] = _curry3(_需求价格弹性)
    builtins["供给价格弹性"] = _curry3(_供给价格弹性)
    builtins["消费者剩余"] = _curry2(_消费者剩余)
    builtins["生产者剩余"] = _curry2(_生产者剩余)
    builtins["边际成本"] = _curry3(_边际成本)
    builtins["总成本"] = _curry3(_总成本)

    # 宏观经济学
    builtins["GDP支出法"] = _curry5(_GDP支出法)
    builtins["GDP收入法"] = _curry4(_GDP收入法)
    builtins["乘数效应"] = _curry1(_乘数效应)
    builtins["物价指数"] = _curry2(_物价指数)
    builtins["通货膨胀率"] = _curry2(_通货膨胀率)
    builtins["人均GDP"] = _curry2(_人均GDP)


def _register_economics_symtab_names() -> list[str]:
    """返回经济学领域所有内建名。"""
    return [
        "复利终值", "复利现值", "年金终值", "年金现值",
        "NPV", "IRR", "单利终值", "实际利率",
        "需求价格弹性", "供给价格弹性", "消费者剩余", "生产者剩余",
        "边际成本", "总成本",
        "GDP支出法", "GDP收入法", "乘数效应",
        "物价指数", "通货膨胀率", "人均GDP",
    ]
