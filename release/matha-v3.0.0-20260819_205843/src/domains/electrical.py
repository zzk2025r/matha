# -*- coding: utf-8 -*-
"""Matha 电气工程专业模块：电路分析、电磁场、信号与系统。

覆盖：
  1) 电路分析：欧姆定律、基尔霍夫定律、分压分流、功率计算
  2) 交流电路：阻抗、功率因数、RLC 谐振
  3) 电磁场：库仑定律、电场强度、磁感应强度
  4) 信号与系统：傅里叶变换基础、滤波器截止频率
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


# ============================================================
# 常量
# ============================================================
EPSILON_0 = 8.854e-12      # 真空介电常数 F/m
MU_0 = 4 * math.pi * 1e-7  # 真空磁导率 H/m
Q_e = 1.602e-19            # 元电荷 C


# ============================================================
# 电路分析
# ============================================================

def _欧姆定律(V, R):
    """欧姆定律：I = V/R。V: V, R: Ω, 返回 I: A。"""
    if R == 0:
        return float('inf')
    return V / R


def _电功率(V, I):
    """电功率 P = V·I。"""
    return V * I


def _电功率_R(V, R):
    """P = V²/R。"""
    if R == 0:
        return float('inf')
    return V * V / R


def _分压公式(V_in, R1, R2):
    """串联分压：V_out = V_in · R2/(R1+R2)。"""
    total = R1 + R2
    if total == 0:
        return 0.0
    return V_in * R2 / total


def _分流公式(I_total, R1, R2):
    """并联分流：I1 = I_total · R2/(R1+R2)。"""
    total = R1 + R2
    if total == 0:
        return 0.0
    return I_total * R2 / total


def _串联电阻(*resistors):
    """串联总电阻 R = R1 + R2 + ..."""
    return sum(resistors)


def _并联电阻(*resistors):
    """并联总电阻 1/R = 1/R1 + 1/R2 + ..."""
    if not resistors:
        return 0.0
    inv_sum = sum(1/r for r in resistors if r != 0)
    if inv_sum == 0:
        return float('inf')
    return 1 / inv_sum


# ============================================================
# 交流电路
# ============================================================

def _感抗(f, L):
    """感抗 X_L = 2πfL。f: Hz, L: H。"""
    return 2 * math.pi * f * L


def _容抗(f, C):
    """容抗 X_C = 1/(2πfC)。f: Hz, C: F。"""
    if f == 0 or C == 0:
        return float('inf')
    return 1 / (2 * math.pi * f * C)


def _RLC阻抗(R, L, C, f):
    """RLC 串联阻抗 Z = sqrt(R² + (XL - XC)²)。"""
    XL = _感抗(f, L)
    XC = _容抗(f, C)
    return math.sqrt(R * R + (XL - XC) * (XL - XC))


def _谐振频率(L, C):
    """RLC 谐振频率 f₀ = 1/(2π√(LC))。"""
    if L <= 0 or C <= 0:
        return 0.0
    return 1 / (2 * math.pi * math.sqrt(L * C))


def _功率因数(Z, R):
    """功率因数 cosφ = R/Z。"""
    if Z == 0:
        return 0.0
    return R / Z


# ============================================================
# 电磁场
# ============================================================

def _库仑力(q1, q2, r):
    """库仑定律 F = k·q1·q2/r²。k = 1/(4πε₀)。"""
    k = 1 / (4 * math.pi * EPSILON_0)
    if r == 0:
        return float('inf')
    return k * abs(q1) * abs(q2) / (r * r)


def _电场强度(Q, r):
    """点电荷电场 E = Q/(4πε₀r²)。"""
    k = 1 / (4 * math.pi * EPSILON_0)
    if r == 0:
        return float('inf')
    return k * abs(Q) / (r * r)


def _长直导线磁场(I, r):
    """无限长直导线磁场 B = μ₀I/(2πr)。"""
    if r == 0:
        return float('inf')
    return MU_0 * I / (2 * math.pi * r)


def _通电导线受力(B, I, L, angle=90):
    """安培力 F = BIL·sinθ。"""
    return B * I * L * math.sin(math.radians(angle))


# ============================================================
# 信号与系统
# ============================================================

def _RC截止频率(R, C):
    """RC 低通滤波器截止频率 fc = 1/(2πRC)。"""
    if R <= 0 or C <= 0:
        return 0.0
    return 1 / (2 * math.pi * R * C)


def _RL截止频率(R, L):
    """RL 低通滤波器截止频率 fc = R/(2πL)。"""
    if L == 0:
        return 0.0
    return R / (2 * math.pi * L)


def _傅里叶频率分辨率(sample_rate, N):
    """DFT 频率分辨率 Δf = fs/N。"""
    if N <= 0:
        return 0.0
    return sample_rate / N


def _采样定理_min_rate(f_max):
    """奈奎斯特最低采样率 fs ≥ 2·f_max。"""
    return 2 * f_max


# ============================================================
# 注册
# ============================================================

def _register_electrical(builtins: dict) -> None:
    """将电气工程领域内建注册到解释器 builtins。"""
    # 电路分析
    builtins["欧姆定律"] = _curry2(_欧姆定律)
    builtins["电功率"] = _curry2(_电功率)
    builtins["电功率_R"] = _curry2(_电功率_R)
    builtins["分压公式"] = _curry3(_分压公式)
    builtins["分流公式"] = _curry3(_分流公式)
    builtins["串联电阻"] = lambda *r: _串联电阻(*r)
    builtins["并联电阻"] = lambda *r: _并联电阻(*r)

    # 交流电路
    builtins["感抗"] = _curry2(_感抗)
    builtins["容抗"] = _curry2(_容抗)
    builtins["RLC阻抗"] = _curry4(_RLC阻抗)
    builtins["谐振频率"] = _curry2(_谐振频率)
    builtins["功率因数"] = _curry2(_功率因数)

    # 电磁场
    builtins["库仑力"] = _curry3(_库仑力)
    builtins["电场强度"] = _curry2(_电场强度)
    builtins["长直导线磁场"] = _curry2(_长直导线磁场)
    builtins["安培力"] = _curry4(_通电导线受力)

    # 信号与系统
    builtins["RC截止频率"] = _curry2(_RC截止频率)
    builtins["RL截止频率"] = _curry2(_RL截止频率)
    builtins["频率分辨率"] = _curry2(_傅里叶频率分辨率)
    builtins["奈奎斯特速率"] = _curry1(_采样定理_min_rate)

    # 常量
    builtins["eps0"] = EPSILON_0
    builtins["mu0"] = MU_0
    builtins["元电荷"] = Q_e


def _register_electrical_symtab_names() -> list[str]:
    """返回电气工程领域所有内建名。"""
    return [
        "欧姆定律", "电功率", "电功率_R", "分压公式", "分流公式",
        "串联电阻", "并联电阻",
        "感抗", "容抗", "RLC阻抗", "谐振频率", "功率因数",
        "库仑力", "电场强度", "长直导线磁场", "安培力",
        "RC截止频率", "RL截止频率", "频率分辨率", "奈奎斯特速率",
        "eps0", "mu0", "元电荷",
    ]
