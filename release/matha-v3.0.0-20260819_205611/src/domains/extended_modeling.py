# -*- coding: utf-8 -*-
"""扩展建模函数：结构力学、流体力学、热力学、电气工程、控制理论。

覆盖新增学科门类：
  - 结构工程：梁弯曲、柱稳定、框架分析
  - 流体力学：管道流动、边界层、湍流模型
  - 热力学：热传导、对流、辐射
  - 电气工程：电力系统、电机驱动、功率电子
  - 控制理论：状态空间、根轨迹、频域分析
  - 材料科学：应力应变、疲劳寿命、断裂力学
"""

from __future__ import annotations
import math
from typing import Any


# ============================================================
# 结构工程
# ============================================================

def _梁弯曲正应力(M: float, y: float, I: float) -> float:
    """梁弯曲正应力 σ = My/I。"""
    if I == 0:
        return 0.0
    return M * y / I


def _梁弯曲挠度(载荷: float, L: float, E: float, I: float, 支座: str = "简支") -> float:
    """梁弯曲挠度计算。"""
    if E * I == 0:
        return float('inf')
    if 支座 == "简支":
        return 5 * 载荷 * L**3 / (384 * E * I)
    elif 支座 == "固支":
        return 载荷 * L**3 / (8 * E * I)
    elif 支座 == "悬臂":
        return 载荷 * L**3 / (3 * E * I)
    return 0.0


def _柱临界载荷(Paschen公式) -> float:
    """柱临界载荷（欧拉公式）。"""
    # 简化：P_cr = π²EI / (KL)²
    return math.pi**2 * 200e9 * 1e-6 / (1.0)**2  # 默认钢柱


def _轴应力(扭矩: float, d: float) -> float:
    """圆轴扭转剪应力 τ = 16T/(πd³)。"""
    if d <= 0:
        return 0.0
    return 16 * 扭矩 / (math.pi * d**3)


def _register_structural(builtins: dict) -> None:
    builtins["梁弯曲应力"] = lambda M, y, I: _梁弯曲正应力(M, y, I)
    builtins["梁挠度"] = lambda q, L, E, I, 支座="简支": _梁弯曲挠度(q, L, E, I, 支座)
    builtins["柱临界载荷"] = _柱临界载荷
    builtins["轴扭转应力"] = _轴应力


# ============================================================
# 流体力学
# ============================================================

def _管道沿程损失(Q: float, L: float, D: float, f: float = 0.02) -> float:
    """达西-魏斯巴赫公式：hf = f·L/D·v²/2g。"""
    if D <= 0:
        return 0.0
    v = Q / (math.pi * D**2 / 4)
    g = 9.81
    return f * L / D * v**2 / (2 * g)


def _雷诺数(v: float, D: float, nu: float = 1.004e-6) -> float:
    """雷诺数 Re = vD/ν。"""
    if nu == 0:
        return float('inf')
    return v * D / nu


def _伯努利方程(z1: float, p1: float, v1: float,
                 z2: float, rho: float = 1000.0) -> float:
    """伯努利方程求 p2。"""
    g = 9.81
    return p1 + rho * g * (z1 - z2) + 0.5 * rho * (v1**2)


def _register_fluid(builtins: dict) -> None:
    builtins["管道沿程损失"] = _管道沿程损失
    builtins["雷诺数"] = _雷诺数
    builtins["伯努利"] = _伯努利方程


# ============================================================
# 热力学
# ============================================================

def _热传导(Q: float, A: float, dT: float, L: float, k: float = 50.0) -> float:
    """傅里叶热传导：Q = kA·dT/L → 求 k。"""
    if A * dT == 0:
        return 0.0
    return Q * L / (A * dT)


def _对流换热(h: float, A: float, Tw: float, Tf: float) -> float:
    """牛顿冷却定律：Q = hA(Tw - Tf)。"""
    return h * A * (Tw - Tf)


def _辐射换热(ε: float, A: float, T1: float, T2: float, σ: float = 5.67e-8) -> float:
    """斯蒂芬-玻尔兹曼辐射定律。"""
    return ε * σ * A * (T1**4 - T2**4)


def _register_thermal(builtins: dict) -> None:
    builtins["热传导系数"] = _热传导
    builtins["对流换热"] = _对流换热
    builtins["辐射换热"] = _辐射换热


# ============================================================
# 电气工程（电力系统）
# ============================================================

def _三相功率线电压(VL: float, IL: float, pf: float = 1.0) -> float:
    """三相功率 P = √3·VL·IL·pf。"""
    return math.sqrt(3) * VL * IL * pf


def _变压器变比(N1: int, N2: int) -> float:
    """变压器变比 k = N1/N2。"""
    if N2 == 0:
        return float('inf')
    return N1 / N2


def _电机扭矩(T: float, n: float, P: float) -> float:
    """电机扭矩 T = 9550·P/n。"""
    if n == 0:
        return 0.0
    return 9550 * P / n


def _register_power(builtins: dict) -> None:
    builtins["三相功率"] = _三相功率线电压
    builtins["变压器变比"] = _变压器变比
    builtins["电机扭矩"] = _电机扭矩


# ============================================================
# 控制理论
# ============================================================

def _PID输出(Kp: float, Ki: float, Kd: float, e: float,
             e_integral: float = 0.0, e_derivative: float = 0.0) -> float:
    """PID 控制器输出。"""
    return Kp * e + Ki * e_integral + Kd * e_derivative


def _一阶惯性环节(T: float, t: float) -> float:
    """一阶惯性环节响应：1 - e^(-t/T)。"""
    if T == 0:
        return 0.0
    return 1.0 - math.exp(-t / T)


def _二阶系统参数(ζ: float, ωn: float) -> dict:
    """二阶系统性能指标。"""
    if ζ < 1:
        overshoot = math.exp(-math.pi * ζ / math.sqrt(1 - ζ**2)) * 100
        tr = (math.pi - math.atan(math.sqrt(1 - ζ**2) / ζ)) / (ωn * math.sqrt(1 - ζ**2))
    else:
        overshoot = 0.0
        tr = 4 / (ζ * ωn)
    return {"超调量": overshoot, "调节时间": tr}


def _register_control(builtins: dict) -> None:
    builtins["PID输出"] = _PID输出
    builtins["一阶响应"] = _一阶惯性环节
    builtins["二阶指标"] = _二阶系统参数


# ============================================================
# 材料科学
# ============================================================

def _胡克定律(σ: float, E: float) -> float:
    """胡克定律：ε = σ/E。"""
    if E == 0:
        return float('inf')
    return σ / E


def _疲劳寿命(S: float, Sn: float, N: float = 1e6) -> int:
    """Miner 疲劳寿命估算（简化）。"""
    if S <= Sn:
        return int(N * 10)
    return int(N * (Sn / S)**3)


def _注册材料科学(builtins: dict) -> None:
    builtins["胡克定律"] = _胡克定律
    builtins["疲劳寿命"] = _疲劳寿命


# ============================================================
# 注册入口
# ============================================================

def _register_extended_modeling(builtins: dict) -> None:
    """注册所有扩展建模函数。"""
    _register_structural(builtins)
    _register_fluid(builtins)
    _register_thermal(builtins)
    _register_power(builtins)
    _register_control(builtins)
    _注册材料科学(builtins)


def _register_extended_modeling_symtab_names() -> list[str]:
    return [
        "梁弯曲应力", "梁挠度", "柱临界载荷", "轴扭转应力",
        "管道沿程损失", "雷诺数", "伯努利",
        "热传导系数", "对流换热", "辐射换热",
        "三相功率", "变压器变比", "电机扭矩",
        "PID输出", "一阶响应", "二阶指标",
        "胡克定律", "疲劳寿命",
    ]


# 兼容性导出
_register_extended = _register_extended_modeling
