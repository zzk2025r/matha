# -*- coding: utf-8 -*-
"""Matha 化学领域模块：普通化学 + 物理化学 + 有机化学。

覆盖：
  1) 普通化学：摩尔质量、溶液浓度、pH 计算、理想气体定律
  2) 物理化学：热力学（ΔH/ΔG/ΔS）、化学平衡（K/ΔG°）、电化学（Nernst）
  3) 有机化学：分子量计算、官能团识别、同分异构体计数

所有函数以柯里化 Python callable 注册到解释器 builtins。
"""

from __future__ import annotations
import math

# ============================================================
# 柯里化工具
# ============================================================
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
NA = 6.02214076e23       # 阿伏伽德罗常数
R_gas = 8.314            # 气体常数 J/(mol·K)
F_const = 96485          # 法拉第常数 C/mol
k_B = 1.380649e-23       # 玻尔兹曼常数 J/K
h_planck = 6.62607015e-34  # 普朗克常数 J·s
c_light = 299792458      # 光速 m/s

# 元素原子量（常用元素）
ATOMIC_WEIGHTS: dict[str, float] = {
    "H": 1.008, "He": 4.003, "Li": 6.941, "Be": 9.012,
    "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999,
    "F": 18.998, "Ne": 20.180, "Na": 22.990, "Mg": 24.305,
    "Al": 26.982, "Si": 28.086, "P": 30.974, "S": 32.065,
    "Cl": 35.453, "K": 39.098, "Ca": 40.078, "Fe": 55.845,
    "Cu": 63.546, "Zn": 65.38, "Ag": 107.868, "Au": 196.967,
}

# 常见化合物摩尔质量（g/mol）
MOLECULAR_WEIGHTS: dict[str, float] = {
    "H2O": 18.015, "CO2": 44.01, "O2": 31.999, "N2": 28.014,
    "HCl": 36.461, "NaCl": 58.443, "H2SO4": 98.079,
    "CH4": 16.043, "C2H5OH": 46.069, "CO": 28.01,
}


# ============================================================
# 普通化学
# ============================================================

def _摩尔质量(formula: str) -> float:
    """计算化合物摩尔质量（g/mol）。支持简化公式如 H2O、C6H12O6。"""
    if formula in MOLECULAR_WEIGHTS:
        return MOLECULAR_WEIGHTS[formula]
    # 简单解析：逐元素累加
    total = 0.0
    i = 0
    while i < len(formula):
        if formula[i].isupper():
            elem = formula[i]
            i += 1
            while i < len(formula) and formula[i].islower():
                elem += formula[i]
                i += 1
            count = 0
            while i < len(formula) and formula[i].isdigit():
                count = count * 10 + int(formula[i])
                i += 1
            if count == 0:
                count = 1
            aw = ATOMIC_WEIGHTS.get(elem, 0.0)
            total += aw * count
        else:
            i += 1
    return total


def _理想气体方程(P, V, n, T):
    """理想气体状态方程 PV=nRT，已知三个求第四个。

    参数：四个参数中一个为 None，其余三个为已知值。
    P: Pa, V: m³, n: mol, T: K
    """
    if P is None:
        return n * R_gas * T / V
    if V is None:
        return n * R_gas * T / P
    if n is None:
        return P * V / (R_gas * T)
    if T is None:
        return P * V / (n * R_gas)
    return 0


def _溶液浓度(mol_solute, vol_L):
    """摩尔浓度 c = n/V。"""
    return mol_solute / vol_L


def _pH计算(H_conc):
    """pH = -log10[H+]。"""
    if H_conc <= 0:
        return float('inf')
    return -math.log10(H_conc)


def _pOH计算(OH_conc):
    """pOH = -log10[OH-]。"""
    if OH_conc <= 0:
        return float('inf')
    return -math.log10(OH_conc)


def _Henderson_方程(pKa, acid, base):
    """Henderson-Hasselbalch 方程：pH = pKa + log10([base]/[acid])。"""
    if acid <= 0:
        return float('inf')
    return pKa + math.log10(base / acid)


# ============================================================
# 物理化学
# ============================================================

def _Gibbs自由能(ΔH, ΔS, T):
    """ΔG = ΔH - TΔS。ΔH: J/mol, ΔS: J/(mol·K), T: K。"""
    return ΔH - T * ΔS


def _平衡常数(ΔG_std, T):
    """K = exp(-ΔG°/RT)。ΔG_std: J/mol。"""
    if T <= 0:
        return 0.0
    return math.exp(-ΔG_std / (R_gas * T))


def _Arrhenius方程(A, Ea, T):
    """k = A·exp(-Ea/RT)。A: 频率因子, Ea: 活化能 J/mol。"""
    if T <= 0:
        return 0.0
    return A * math.exp(-Ea / (R_gas * T))


def _Nernst方程(E_std, n, Q):
    """Nernst 方程：E = E° - (RT/nF)·lnQ，25°C 简化。"""
    T = 298.15
    return E_std - (R_gas * T / (n * F_const)) * math.log(Q)


def _反应速率常溫比(k1, T1, Ea):
    """已知 k1 在 T1 下的速率常数，求 Ea 下的 k2（T2=298K）。"""
    T2 = 298.15
    return k1 * math.exp(-Ea / R_gas * (1/T2 - 1/T1))


# ============================================================
# 有机化学
# ============================================================

def _烷烃通式(n):
    """CnH(2n+2)，返回分子式字符串。"""
    return f"C{n}H{2*n + 2}"


def _烯烃通式(n):
    """CnH2n，返回分子式字符串。"""
    return f"C{n}H{2*n}"


def _炔烃通式(n):
    """CnH(2n-2)，返回分子式字符串。"""
    return f"C{n}H{2*n - 2}"


def _同分异构体数(n):
    """烷烃 CnH(2n+2) 的同分异构体数目（n≤10 精确值）。"""
    # 已知烷烃同分异构体数序列
    known = {1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 5, 7: 9, 8: 18, 9: 35, 10: 75}
    return known.get(n, -1)


def _不饱和度(formula):
    """计算不饱和度（双键等价数）。公式格式如 C6H12O6。"""
    # 简化：只处理 C H O N Hal 格式
    import re
    elems = re.findall(r'([A-Z][a-z]?)(\d*)', formula)
    C = H = N = X = 0
    for elem, count_str in elems:
        count = int(count_str) if count_str else 1
        if elem == "C":
            C = count
        elif elem == "H":
            H = count
        elif elem == "N":
            N = count
        elif elem in ("F", "Cl", "Br", "I"):
            X = count
    if C == 0:
        return 0
    return (2 * C + 2 + N - H - X) / 2


# ============================================================
# 注册
# ============================================================

def _register_chemistry(builtins: dict) -> None:
    """将化学领域内建注册到解释器 builtins。"""
    # 普通化学
    builtins["摩尔质量"] = lambda f: _摩尔质量(str(f))
    builtins["理想气体_P"] = _curry3(lambda n, V, T: _理想气体方程(None, V, n, T) if False else None)
    builtins["理想气体_V"] = _curry3(lambda P, n, T: _理想气体方程(P, None, n, T))
    builtins["理想气体_n"] = _curry3(lambda P, V, T: _理想气体方程(P, V, None, T))
    builtins["理想气体_T"] = _curry3(lambda P, V, n: _理想气体方程(P, V, n, None))
    builtins["溶液浓度"] = _curry2(_溶液浓度)
    builtins["pH计算"] = _curry1(_pH计算)
    builtins["pOH计算"] = _curry1(_pOH计算)
    builtins["Henderson方程"] = _curry3(_Henderson_方程)

    # 物理化学
    builtins["Gibbs自由能"] = _curry3(_Gibbs自由能)
    builtins["平衡常数"] = _curry2(_平衡常数)
    builtins["Arrhenius方程"] = _curry3(_Arrhenius方程)
    builtins["Nernst方程"] = _curry3(_Nernst方程)
    builtins["速率常数比"] = _curry3(_反应速率常溫比)

    # 有机化学
    builtins["烷烃通式"] = _curry1(_烷烃通式)
    builtins["烯烃通式"] = _curry1(_烯烃通式)
    builtins["炔烃通式"] = _curry1(_炔烃通式)
    builtins["同分异构体数"] = _curry1(_同分异构体数)
    builtins["不饱和度"] = _curry1(_不饱和度)

    # 常量
    builtins["阿伏伽德罗常数"] = NA
    builtins["气体常数"] = R_gas
    builtins["法拉第常数"] = F_const
    builtins["玻尔兹曼常数"] = k_B
    builtins["普朗克常数"] = h_planck
    builtins["光速"] = c_light


def _curry1(func):
    """一参柯里化。"""
    def with_first(a):
        return func(a)
    return with_first


def _register_chemistry_symtab_names() -> list[str]:
    """返回化学领域所有内建名。"""
    return [
        "摩尔质量", "理想气体_P", "理想气体_V", "理想气体_n", "理想气体_T",
        "溶液浓度", "pH计算", "pOH计算", "Henderson方程",
        "Gibbs自由能", "平衡常数", "Arrhenius方程", "Nernst方程", "速率常数比",
        "烷烃通式", "烯烃通式", "炔烃通式", "同分异构体数", "不饱和度",
        "阿伏伽德罗常数", "气体常数", "法拉第常数", "玻尔兹曼常数", "普朗克常数", "光速",
    ]
