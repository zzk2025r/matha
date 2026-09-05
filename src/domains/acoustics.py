"""Matha 机械领域模块：声学（Acoustics）。

基于力学 + 电磁学 + mathlib 数学地基，演化声学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、声波基础（Sound Wave Basics）
  1) 声速（空气中）：c = 331.3 + 0.6T（T 为摄氏温度）
  2) 波长-频率-波速关系：c = fλ → λ = c/f, f = c/λ
  3) 声波周期：T = 1/f
  4) 角频率：ω = 2πf
  5) 波数：k = 2π/λ = ω/c
  6) 声速（一般介质）：c = √(E/ρ)（纵波）/ c = √(G/ρ)（横波）

二、声强与声压级（Sound Intensity & SPL）
  1) 声强：I = p²/(ρc)（p 为声压有效值）
  2) 声强级：L_I = 10·lg(I/I₀)，I₀ = 10⁻¹² W/m²
  3) 声压级：L_p = 20·lg(p/p₀)，p₀ = 20μPa
  4) 声功率级：L_W = 10·lg(W/W₀)，W₀ = 10⁻¹² W
  5) 声强（由功率和面积）：I = W/A
  6) 多声源叠加（分贝相加）：L_total = 10·lg(Σ10^(L_i/10))

三、多普勒效应（Doppler Effect）
  1) 声源不动、观察者运动：f' = f(c±v_o)/c
  2) 观察者不动、声源运动：f' = fc/(c∓v_s)
  3) 通用多普勒：f' = f(c±v_o)/(c∓v_s)
  4) 马赫数：Ma = v/c
  5) 马赫角：sinθ = c/v = 1/Ma

四、声学现象（Acoustic Phenomena）
  1) 拍频：f_beat = |f₁ - f₂|
  2) 驻波波长（两端固定）：λ_n = 2L/n
  3) 驻波频率（两端固定）：f_n = nv/(2L)
  4) 管道共鸣频率（开管/闭管）
  5) 空气吸收衰减：A = α·d（α 为吸收系数）
  6) 反平方律衰减：I₂ = I₁(r₁/r₂)²

五、管道与弦振动（Pipe & String Vibration）
  1) 弦振动频率（横波）：f = (1/2L)√(T/μ)，T 为张力，μ 为线密度
  2) 弦上波速：v = √(T/μ)
  3) 开管基频：f₁ = c/(2L)
  4) 闭管基频：f₁ = c/(4L)
  5) 开管谐波：f_n = nc/(2L)（n=1,2,3...）
  6) 闭管谐波：f_n = (2n-1)c/(4L)（n=1,2,3...）

设计原则：
  - 所有函数返回纯数值（float/int）
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 声_ / 强级_ / 多普勒_ / 现象_ / 弦管_ 区分子领域
  - 声学参考常量作为常量注册
"""

from __future__ import annotations
import math
from src.stdlib.safe_ops import safe_div


# ============================================================
# 柯里化工具
# ============================================================

def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def _curry3(func):
    def with_first(a):
        def with_second(b):
            return lambda c: func(a, b, c)
        return with_second
    return with_first


def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1


# ============================================================
# 物理常量
# ============================================================

# 声学参考声压 p₀ = 20 μPa
P_REF = 2.0e-5
# 声学参考声强 I₀ = 10⁻¹² W/m²
I_REF = 1.0e-12
# 声学参考声功率 W₀ = 10⁻¹² W
W_REF = 1.0e-12
# 0°C 空气中声速 c₀ = 331.3 m/s
C_AIR_0C = 331.3
# 空气温度系数 0.6 m/s/°C
C_AIR_COEFF = 0.6


# ============================================================
# 一、声波基础（Sound Wave Basics）
# ============================================================

# 空气中声速（温度修正）：c = 331.3 + 0.6T
def _声_空气声速(T_C): return C_AIR_0C + C_AIR_COEFF * T_C
# 波长 λ = c/f
def _声_波长(c, f): return safe_div(c, f)
def _声_频率(c, wavelength): return safe_div(c, wavelength)
def _声_周期(f): return safe_div(1.0, f)
def _声_角频率(f): return 2 * math.pi * f
def _声_波数(wavelength): return safe_div(2 * math.pi, wavelength)
# 声速（一般介质纵波）：c = √(E/ρ)
def _声_介质声速(E, rho): return math.sqrt(E / rho)
# 声速（一般介质横波）：c = √(G/ρ）
def _声_横波声速(G, rho): return math.sqrt(G / rho)


# ============================================================
# 二、声强与声压级（Sound Intensity & SPL）
# ============================================================

# 声强（由声压）：I = p²/(ρc)
def _强级_声强由声压(p, rho, c): return p * p / safe_div(rho, c) if rho != 0 and c != 0 else float('inf')
# 声强级：L_I = 10·lg(I/I₀)
def _强级_声强级(I): return 10 * math.log10(I / I_REF)
# 声压级：L_p = 20·lg(p/p₀)
def _强级_声压级(p): return 20 * math.log10(p / P_REF)
# 声功率级：L_W = 10·lg(W/W₀)
def _强级_声功率级(W): return 10 * math.log10(W / W_REF)
# 声强（由功率和面积）：I = W/A
def _强级_声强由功率(W, A): return W / A
# 由声强级反算声强：I = I₀·10^(L/10)
def _强级_声强由级(L_I): return I_REF * 10 ** (L_I / 10)
# 由声压级反算声压：p = p₀·10^(L/20)
def _强级_声压由级(L_p): return P_REF * 10 ** (L_p / 20)
# 多声源分贝叠加：L_total = 10·lg(Σ10^(L_i/10))
def _强级_分贝叠加(L_list):
    if isinstance(L_list, list):
        return 10 * math.log10(sum(10 ** (li / 10) for li in L_list))
    return L_list


# ============================================================
# 三、多普勒效应（Doppler Effect）
# ============================================================

# 声源不动、观察者运动：f' = f(c + v_o)/c（接近为正）
def _多普勒_观察者运动(f, c, v_o): return safe_div(f * (c + v_o), c)
# 观察者不动、声源运动：f' = fc/(c - v_s)（接近为正）
def _多普勒_声源运动(f, c, v_s): return safe_div(f * c, c - v_s)
# 通用多普勒：f' = f(c + v_o)/(c - v_s)（接近为正）
def _多普勒_通用(f, c, v_o, v_s): return safe_div(f * (c + v_o), c - v_s)
# 马赫数：Ma = v/c
def _多普勒_马赫数(v, c): return safe_div(v, c)
# 马赫角：θ = arcsin(c/v) = arcsin(1/Ma)（返回弧度）
def _多普勒_马赫角(v, c): return math.asin(c / v) if v > c else math.pi / 2


# ============================================================
# 四、声学现象（Acoustic Phenomena）
# ============================================================

# 拍频：f_beat = |f₁ - f₂|
def _现象_拍频(f1, f2): return abs(f1 - f2)
# 驻波波长（两端固定）：λ_n = 2L/n
def _现象_驻波波长(L, n): return safe_div(2 * L, n)
# 驻波频率（两端固定）：f_n = nv/(2L)
def _现象_驻波频率(n, v, L): return safe_div(n * v, 2 * L)
# 反平方律衰减：I₂ = I₁(r₁/r₂)²
def _现象_反平方衰减(I1, r1, r2):
    r = safe_div(r1, r2) if r2 != 0 else float('inf')
    return I1 * r * r
# 声压随距离衰减（球面波）：p₂ = p₁(r₁/r₂)
def _现象_声压衰减(p1, r1, r2): return p1 * safe_div(r1, r2) if r2 != 0 else float('inf')
# 空气吸收衰减：I₂ = I₁·e^(-αd)（α 为吸收系数）
def _现象_吸收衰减(I1, alpha, d): return I1 * math.exp(-alpha * d)


# ============================================================
# 五、管道与弦振动（Pipe & String Vibration）
# ============================================================

# 弦上波速：v = √(T/μ)
def _弦管_弦上波速(T, mu): return math.sqrt(T / mu)
# 弦振动频率（基频）：f = (1/2L)√(T/μ)
def _弦管_弦频率(T, mu, L): return (1.0 / (2 * L)) * math.sqrt(T / mu)
# 弦振动泛音：f_n = n/(2L)·√(T/μ)
def _弦管_弦泛音(T, mu, L, n): return n / (2 * L) * math.sqrt(T / mu)
# 开管基频：f₁ = c/(2L)
def _弦管_开管基频(c, L): return c / (2 * L)
# 闭管基频：f₁ = c/(4L)
def _弦管_闭管基频(c, L): return c / (4 * L)
# 开管谐波：f_n = nc/(2L)（n=1,2,3...）
def _弦管_开管谐波(c, L, n): return n * c / (2 * L)
# 闭管谐波：f_n = (2n-1)c/(4L)（n=1,2,3...）
def _弦管_闭管谐波(c, L, n): return (2 * n - 1) * c / (4 * L)


# ============================================================
# 声学材料数据库
# ============================================================

# 常见介质中声速 (m/s)
SOUND_SPEEDS: dict[str, float] = {
    "空气_0C": 331.3,
    "空气_20C": 343.2,
    "水_20C": 1482.0,
    "海水_20C": 1520.0,
    "钢": 5960.0,
    "铝": 6420.0,
    "铜": 4760.0,
    "铁": 5130.0,
    "玻璃": 5640.0,
    "木材_松木": 3300.0,
    "混凝土": 3400.0,
    "橡胶": 1600.0,
}

# 常见介质密度 (kg/m³)（与声速配套使用）
MEDIUM_DENSITIES: dict[str, float] = {
    "空气_20C": 1.205,
    "水_20C": 1000.0,
    "海水_20C": 1025.0,
    "钢": 7850.0,
    "铝": 2700.0,
    "铜": 8960.0,
    "铁": 7870.0,
    "玻璃": 2500.0,
    "木材_松木": 500.0,
    "混凝土": 2400.0,
    "橡胶": 1100.0,
}

# 声学吸收系数 (Np/m, 常温空气中近似值)
ABSORPTION_COEFFS: dict[str, float] = {
    "空气_1kHz": 0.005,
    "空气_2kHz": 0.01,
    "空气_4kHz": 0.03,
    "空气_8kHz": 0.10,
    "水_1kHz": 0.00005,
}


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_acoustics(builtins: dict) -> None:
    """将声学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（em 之后）。
    """
    # --- 声波基础 ---
    builtins["声_空气声速"] = _声_空气声速                     # 声_空气声速(T°C)
    builtins["声_波长"] = _curry2(_声_波长)                    # 声_波长(c)(f)
    builtins["声_频率"] = _curry2(_声_频率)                    # 声_频率(c)(λ)
    builtins["声_周期"] = _声_周期                             # 声_周期(f)
    builtins["声_角频率"] = _声_角频率                          # 声_角频率(f)
    builtins["声_波数"] = _声_波数                             # 声_波数(λ)
    builtins["声_介质声速"] = _curry2(_声_介质声速)            # 声_介质声速(E)(ρ)
    builtins["声_横波声速"] = _curry2(_声_横波声速)            # 声_横波声速(G)(ρ)

    # --- 声强与声压级 ---
    builtins["强级_声强由声压"] = _curry3(_强级_声强由声压)    # 强级_声强由声压(p)(ρ)(c)
    builtins["强级_声强级"] = _强级_声强级                     # 强级_声强级(I)
    builtins["强级_声压级"] = _强级_声压级                     # 强级_声压级(p)
    builtins["强级_声功率级"] = _强级_声功率级                  # 强级_声功率级(W)
    builtins["强级_声强由功率"] = _curry2(_强级_声强由功率)    # 强级_声强由功率(W)(A)
    builtins["强级_声强由级"] = _强级_声强由级                  # 强级_声强由级(L_I)
    builtins["强级_声压由级"] = _强级_声压由级                  # 强级_声压由级(L_p)
    builtins["强级_分贝叠加"] = _强级_分贝叠加                  # 强级_分贝叠加(列表)

    # --- 多普勒效应 ---
    builtins["多普勒_观察者运动"] = _curry3(_多普勒_观察者运动)  # 多普勒_观察者运动(f)(c)(v_o)
    builtins["多普勒_声源运动"] = _curry3(_多普勒_声源运动)    # 多普勒_声源运动(f)(c)(v_s)
    builtins["多普勒_通用"] = _curry4(_多普勒_通用)            # 多普勒_通用(f)(c)(v_o)(v_s)
    builtins["多普勒_马赫数"] = _curry2(_多普勒_马赫数)        # 多普勒_马赫数(v)(c)
    builtins["多普勒_马赫角"] = _curry2(_多普勒_马赫角)        # 多普勒_马赫角(v)(c)

    # --- 声学现象 ---
    builtins["现象_拍频"] = _curry2(_现象_拍频)                # 现象_拍频(f1)(f2)
    builtins["现象_驻波波长"] = _curry2(_现象_驻波波长)        # 现象_驻波波长(L)(n)
    builtins["现象_驻波频率"] = _curry3(_现象_驻波频率)        # 现象_驻波频率(n)(v)(L)
    builtins["现象_反平方衰减"] = _curry3(_现象_反平方衰减)    # 现象_反平方衰减(I1)(r1)(r2)
    builtins["现象_吸收衰减"] = _curry3(_现象_吸收衰减)        # 现象_吸收衰减(I1)(α)(d)
    builtins["现象_声压衰减"] = _curry3(_现象_声压衰减)        # 现象_声压衰减(p1)(r1)(r2)

    # --- 管道与弦振动 ---
    builtins["弦管_弦上波速"] = _curry2(_弦管_弦上波速)        # 弦管_弦上波速(T)(μ)
    builtins["弦管_弦频率"] = _curry3(_弦管_弦频率)            # 弦管_弦频率(T)(μ)(L)
    builtins["弦管_弦泛音"] = _curry4(_弦管_弦泛音)            # 弦管_弦泛音(T)(μ)(L)(n)
    builtins["弦管_开管基频"] = _curry2(_弦管_开管基频)        # 弦管_开管基频(c)(L)
    builtins["弦管_闭管基频"] = _curry2(_弦管_闭管基频)        # 弦管_闭管基频(c)(L)
    builtins["弦管_开管谐波"] = _curry3(_弦管_开管谐波)        # 弦管_开管谐波(c)(L)(n)
    builtins["弦管_闭管谐波"] = _curry3(_弦管_闭管谐波)        # 弦管_闭管谐波(c)(L)(n)

    # --- 物理常量 ---
    builtins["p0_参考声压"] = P_REF
    builtins["I0_参考声强"] = I_REF
    builtins["W0_参考声功率"] = W_REF

    # --- 介质声速常量 ---
    for name, val in SOUND_SPEEDS.items():
        builtins[f"声速_{name}"] = val

    # --- 介质密度常量 ---
    for name, val in MEDIUM_DENSITIES.items():
        builtins[f"声学密度_{name}"] = val

    # --- 吸收系数常量 ---
    for name, val in ABSORPTION_COEFFS.items():
        builtins[f"吸收系数_{name}"] = val


def _acoustics_symtab_names() -> list[str]:
    """返回声学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 声波基础
    for n in ["空气声速", "波长", "频率", "周期", "角频率",
              "波数", "介质声速", "横波声速"]:
        names.append(f"声_{n}")
    # 声强与声压级
    for n in ["声强由声压", "声强级", "声压级", "声功率级",
              "声强由功率", "声强由级", "声压由级", "分贝叠加"]:
        names.append(f"强级_{n}")
    # 多普勒
    for n in ["观察者运动", "声源运动", "通用", "马赫数", "马赫角"]:
        names.append(f"多普勒_{n}")
    # 声学现象
    for n in ["拍频", "驻波波长", "驻波频率",
              "反平方衰减", "吸收衰减", "声压衰减"]:
        names.append(f"现象_{n}")
    # 管道与弦振动
    for n in ["弦上波速", "弦频率", "弦泛音",
              "开管基频", "闭管基频", "开管谐波", "闭管谐波"]:
        names.append(f"弦管_{n}")
    # 物理常量
    for n in ["p0_参考声压", "I0_参考声强", "W0_参考声功率"]:
        names.append(n)
    # 数据库常量
    for name in SOUND_SPEEDS:
        names.append(f"声速_{name}")
    for name in MEDIUM_DENSITIES:
        names.append(f"声学密度_{name}")
    for name in ABSORPTION_COEFFS:
        names.append(f"吸收系数_{name}")
    return names
