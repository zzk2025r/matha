"""Matha 机械领域模块：统计力学（Statistical Mechanics）。

基于热力学 + 量子力学 + 核物理 + mathlib 数学地基，演化统计力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、麦克斯韦-玻尔兹曼分布（Maxwell-Boltzmann Distribution）
  1) 最概然速率：vp = √(2kT/m)
  2) 平均速率：v̄ = √(8kT/(πm))
  3) 方均根速率：vrms = √(3kT/m)
  4) 速率分布函数：f(v) = 4π(m/(2πkT))^(3/2)·v²·exp(-mv²/(2kT))
  5) 理想气体压强：P = nkT
  6) 理想气体状态方程：PV = NkT
  7) 分子碰撞频率
  8) 平均自由程

二、配分函数（Partition Functions）
  1) 玻尔兹曼因子：exp(-E/(kT))
  2) 单粒子配分函数：Z = Σexp(-εi/(kT))
  3) 简并能级配分函数：Z = Σgi·exp(-εi/(kT))
  4) 谐振子配分函数：Z = 1/(2sinh(ℏω/(2kT)))
  5) 配分函数→内能：U = kT²·∂lnZ/∂T
  6) 配分函数→熵：S = k(lnZ + T·∂lnZ/∂T)

三、熵与自由能（Entropy & Free Energy）
  1) 玻尔兹曼熵：S = k·lnW
  2) 配分函数→自由能：F = -kT·lnZ
  3) 吉布斯自由能：G = H - TS
  4) 焓：H = U + PV
  5) 热容（等容）：Cv = (∂U/∂T)v
  6) 热容（等压）：Cp = Cv + Nk
  7) 理想气体熵变：ΔS = Nk·ln(V2/V1) + Nk·ln(T2/T1)

四、量子统计（Quantum Statistics）
  1) 费米-狄拉克分布：f(E) = 1/(exp((E-μ)/(kT))+1)
  2) 玻色-爱因斯坦分布：f(E) = 1/(exp((E-μ)/(kT))-1)
  3) 费米能级（T=0）：EF = (ℏ²/2m)(3π²n)^(2/3)
  4) 德拜温度：θD = ℏωD/k
  5) 德拜热容（低温）：Cv ≈ (12π⁴/5)·Nk·(T/θD)³
  6) 维恩位移常数

五、涨落与关联（Fluctuations & Correlations）
  1) 能量涨落：⟨(ΔE)²⟩ = kT²·Cv
  2) 粒子数涨落：⟨(ΔN)²⟩ = kT·(∂N/∂μ)
  3) 相对涨落：√(⟨(ΔE)²⟩)/⟨E⟩
  4) 密度涨落
  5) 布朗运动（均方位移）：⟨x²⟩ = 2Dt
  6) 爱因斯坦关系：D = kT/(6πηr)

设计原则：
  - 所有温度输入均为开尔文 K
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 速率_ / 配分_ / 熵_ / 统计_ / 涨落_ 区分子领域
  - 统计力学常量作为常量注册
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

# 玻尔兹曼常数 k_B = 1.381e-23 J/K
K_B = 1.380649e-23
# 普朗克常量 h
H_PLANCK = 6.62607015e-34
# 约化普朗克常量 ℏ
HBAR = H_PLANCK / (2 * math.pi)
# 阿伏伽德罗常数 N_A
N_A = 6.02214076e23
# 气体常数 R = N_A·k_B
R_GAS = N_A * K_B
# 电子质量
M_ELECTRON = 9.1093837015e-31
# 基本电荷
E_CHARGE = 1.602176634e-19
# 斯特藩-玻尔兹曼常数 σ
SIGMA_SB = 5.670374419e-8
# 维恩位移常数 b = 2.898e-3 m·K
WIEN_B = 2.897771955e-3


# ============================================================
# 一、麦克斯韦-玻尔兹曼分布（Maxwell-Boltzmann Distribution）
# ============================================================

# 最概然速率：vp = √(2kT/m)
def _速率_最概然速率(m, T): return math.sqrt(2 * K_B * T / m)
# 平均速率：v̄ = √(8kT/(πm))
def _速率_平均速率(m, T): return math.sqrt(8 * K_B * T / (math.pi * m))
# 方均根速率：vrms = √(3kT/m)
def _速率_方均根速率(m, T): return math.sqrt(3 * K_B * T / m)
# 麦克斯韦速率分布函数：f(v) = 4π(m/(2πkT))^(3/2)·v²·exp(-mv²/(2kT))
def _速率_分布函数(m, T, v):
    factor = (m / (2 * math.pi * K_B * T)) ** 1.5
    return 4 * math.pi * factor * v ** 2 * math.exp(-m * v ** 2 / (2 * K_B * T))
# 理想气体压强：P = nkT
def _速率_理想气体压强(n, T): return n * K_B * T
# 理想气体状态方程：PV = NkT → P = NkT/V
def _速率_理想气体压力(N, T, V): return N * K_B * T / V
# 平均自由程：λ = 1/(√2·n·σ)，σ 为碰撞截面
def _速率_平均自由程(n, sigma): return 1.0 / (math.sqrt(2) * n * sigma)
# 分子碰撞频率：Z = √2·n·σ·v̄
def _速率_碰撞频率(n, sigma, v_bar): return math.sqrt(2) * n * sigma * v_bar


# ============================================================
# 二、配分函数（Partition Functions）
# ============================================================

# 玻尔兹曼因子：exp(-E/(kT))
def _配分_玻尔兹曼因子(E, T): return math.exp(-E / (K_B * T))
# 单粒子配分函数（离散能级）：Z = Σexp(-εi/(kT))
def _配分_离散配分函数(energies, T):
    """energies: 能级列表 [ε1, ε2, ...]"""
    beta = 1.0 / (K_B * T)
    return sum(math.exp(-e * beta) for e in energies)
# 简并能级配分函数：Z = Σgi·exp(-εi/(kT))
def _配分_简并配分函数(levels, T):
    """levels: [(ε1, g1), (ε2, g2), ...]"""
    beta = 1.0 / (K_B * T)
    return sum(g * math.exp(-e * beta) for e, g in levels)
# 谐振子配分函数：Z = 1/(2sinh(ℏω/(2kT)))
def _配分_谐振子配分函数(omega, T):
    x = HBAR * omega / (2 * K_B * T)
    return 1.0 / (2 * math.sinh(x))
# 转动配分函数：Z_rot = T/(σ·θ_rot)，θ_rot = ℏ²/(2Ik)
def _配分_转动配分函数(I, T, sigma=1.0):
    theta_rot = HBAR ** 2 / (2 * I * K_B)
    return T / (sigma * theta_rot)
# 配分函数→内能：U = kT²·∂lnZ/∂T ≈ kT²·(Z'/Z)（数值微分）
def _配分_内能(Z_func, T):
    """Z_func: 温度的函数（Python callable），返回 Z。"""
    dt = T * 1e-6
    Z_plus = Z_func(T + dt)
    Z_minus = Z_func(T - dt)
    dlnZ_dT = (math.log(Z_plus) - math.log(Z_minus)) / (2 * dt)
    return K_B * T ** 2 * dlnZ_dT
# 配分函数→熵：S = k(lnZ + T·∂lnZ/∂T)
def _配分_熵(Z_func, T):
    """Z_func: 温度的函数（Python callable），返回 Z。"""
    dt = T * 1e-6
    Z_plus = Z_func(T + dt)
    Z_minus = Z_func(T - dt)
    Z_T = Z_func(T)
    dlnZ_dT = (math.log(Z_plus) - math.log(Z_minus)) / (2 * dt)
    return K_B * (math.log(Z_T) + T * dlnZ_dT)
# 等温等压配分函数关系：F = -kT·lnZ
def _配分_自由能(Z, T): return -K_B * T * math.log(Z)
# 亥姆霍兹自由能→压力：P = -∂F/∂V（简化）
def _配分_自由能压力(F_func, V):
    """F_func: 体积的函数（Python callable），返回 F。"""
    dV = V * 1e-6
    return -(F_func(V + dV) - F_func(V - dV)) / (2 * dV)


# ============================================================
# 三、熵与自由能（Entropy & Free Energy）
# ============================================================

# 玻尔兹曼熵：S = k·lnW
def _熵_玻尔兹曼熵(W): return K_B * math.log(W)
# 玻尔兹曼熵（由微观态数）
def _熵_玻尔兹曼熵2(W): return K_B * math.log(W) if W > 0 else 0.0
# 吉布斯熵：S = -k·Σpi·ln(pi)
def _熵_吉布斯熵(probs):
    """probs: 概率列表 [p1, p2, ...]"""
    return -K_B * sum(p * math.log(p) for p in probs if p > 0)
# 理想气体熵（萨克尔-泰特罗德方程）：S = Nk[ln(V/N·(4πmU/(3Nh²))^(3/2)) + 5/2]
def _熵_萨克尔泰特罗德(N, V, m, U):
    """单原子理想气体熵。"""
    term1 = math.log(V / N * (4 * math.pi * m * U / (3 * N * H_PLANCK ** 2)) ** 1.5)
    return N * K_B * (term1 + 2.5)
# 理想气体熵变（等温膨胀）：ΔS = Nk·ln(V2/V1)
def _熵_等温熵变(N, V1, V2): return N * K_B * math.log(V2 / V1)
# 理想气体熵变（一般过程）：ΔS = Nk·ln(V2/V1) + (3/2)Nk·ln(T2/T1)
def _熵_理想气体熵变(N, V1, V2, T1, T2):
    return N * K_B * math.log(V2 / V1) + 1.5 * N * K_B * math.log(T2 / T1)
# 焓：H = U + PV
def _熵_焓(U, P, V): return U + P * V
# 吉布斯自由能：G = H - TS
def _熵_吉布斯自由能(H, T, S): return H - T * S
# 等容热容（单原子理想气体）：Cv = (3/2)Nk
def _熵_等容热容(N): return 1.5 * N * K_B
# 等压热容（单原子理想气体）：Cp = Cv + Nk = (5/2)Nk
def _熵_等压热容(N): return 2.5 * N * K_B
# 热容比：γ = Cp/Cv
def _熵_热容比(Cp, Cv): return Cp / Cv


# ============================================================
# 四、量子统计（Quantum Statistics）
# ============================================================

# 费米-狄拉克分布：f(E) = 1/(exp((E-μ)/(kT))+1)
def _统计_费米狄拉克(E, mu, T):
    x = (E - mu) / (K_B * T)
    if x > 500:
        return 0.0
    if x < -500:
        return 1.0
    return 1.0 / (math.exp(x) + 1)
# 玻色-爱因斯坦分布：f(E) = 1/(exp((E-μ)/(kT))-1)
def _统计_玻色爱因斯坦(E, mu, T):
    x = (E - mu) / (K_B * T)
    if x <= 0:
        return float('inf')
    if x > 500:
        return 0.0
    return 1.0 / (math.exp(x) - 1)
# 费米能级（T=0）：EF = (ℏ²/2m)(3π²n)^(2/3)
def _统计_费米能级(m, n):
    return HBAR ** 2 / (2 * m) * (3 * math.pi ** 2 * n) ** (2.0 / 3)
# 费米温度：TF = EF/k
def _统计_费米温度(EF): return EF / K_B
# 费米速度：vF = √(2EF/m)
def _统计_费米速度(EF, m): return math.sqrt(2 * EF / m)
# 德拜频率：ωD = v_s·(6π²n)^(1/3)
def _统计_德拜频率(v_s, n): return v_s * (6 * math.pi ** 2 * n) ** (1.0 / 3)
# 德拜温度：θD = ℏωD/k
def _统计_德拜温度(omega_D): return HBAR * omega_D / K_B
# 德拜热容（低温极限）：Cv ≈ (12π⁴/5)·Nk·(T/θD)³
def _统计_德拜热容低温(N, T, theta_D):
    return (12 * math.pi ** 4 / 5) * N * K_B * (T / theta_D) ** 3
# 维恩位移定律：λmax·T = b
def _统计_维恩位移(T): return WIEN_B / T
# 黑体辐射功率密度（斯特藩-玻尔兹曼）：j = σT⁴
def _统计_黑体辐射功率(T): return SIGMA_SB * T ** 4
# 光子气体内能密度：u = aT⁴，a = 4σ/c
def _统计_光子气体内能密度(T):
    c = 2.99792458e8
    a = 4 * SIGMA_SB / c
    return a * T ** 4


# ============================================================
# 五、涨落与关联（Fluctuations & Correlations）
# ============================================================

# 能量涨落：⟨(ΔE)²⟩ = kT²·Cv
def _涨落_能量涨落(T, Cv): return K_B * T ** 2 * Cv
# 粒子数涨落（巨正则）：⟨(ΔN)²⟩ = kT·(∂N/∂μ) ≈ N（理想气体）
def _涨落_粒子数涨落(T, dN_dmu): return K_B * T * dN_dmu
# 相对能量涨落：√(⟨(ΔE)²⟩)/⟨E⟩
def _涨落_相对能量涨落(T, Cv, E_avg):
    var_E = K_B * T ** 2 * Cv
    return math.sqrt(var_E) / E_avg if E_avg != 0 else float('inf')
# 布朗运动均方位移：⟨x²⟩ = 2Dt
def _涨落_布朗位移(D, t): return 2 * D * t
# 爱因斯坦关系：D = kT/(6πηr)
def _涨落_爱因斯坦扩散系数(T, eta, r): return K_B * T / (6 * math.pi * eta * r)
# 密度涨落（等温压缩率）：⟨(Δρ/ρ)²⟩ = kT·κT/V
def _涨落_密度涨落(T, kappa_T, V): return K_B * T * kappa_T / V
# 体积涨落：⟨(ΔV)²⟩ = kT·V·κT
def _涨落_体积涨落(T, V, kappa_T): return K_B * T * V * kappa_T
# 温度涨落（微正则）：⟨(ΔT)²⟩ = kT²/Cv
def _涨落_温度涨落(T, Cv): return K_B * T ** 2 / Cv


# ============================================================
# 注册到解释器 builtins
# ============================================================

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


def _register_statmech(builtins: dict) -> None:
    """将统计力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（nuclear 之后）。
    """
    # --- 麦克斯韦-玻尔兹曼分布 ---
    builtins["速率_最概然速率"] = _curry2(_速率_最概然速率)          # 速率_最概然速率(m)(T)
    builtins["速率_平均速率"] = _curry2(_速率_平均速率)              # 速率_平均速率(m)(T)
    builtins["速率_方均根速率"] = _curry2(_速率_方均根速率)          # 速率_方均根速率(m)(T)
    builtins["速率_分布函数"] = _curry3(_速率_分布函数)              # 速率_分布函数(m)(T)(v)
    builtins["速率_理想气体压强"] = _curry2(_速率_理想气体压强)      # 速率_理想气体压强(n)(T)
    builtins["速率_理想气体压力"] = _curry3(_速率_理想气体压力)      # 速率_理想气体压力(N)(T)(V)
    builtins["速率_平均自由程"] = _curry2(_速率_平均自由程)          # 速率_平均自由程(n)(σ)
    builtins["速率_碰撞频率"] = _curry3(_速率_碰撞频率)              # 速率_碰撞频率(n)(σ)(v̄)

    # --- 配分函数 ---
    builtins["配分_玻尔兹曼因子"] = _curry2(_配分_玻尔兹曼因子)      # 配分_玻尔兹曼因子(E)(T)
    builtins["配分_离散配分函数"] = _curry2(_配分_离散配分函数)      # 配分_离散配分函数(能级列表)(T)
    builtins["配分_简并配分函数"] = _curry2(_配分_简并配分函数)      # 配分_简并配分函数(能级列表)(T)
    builtins["配分_谐振子配分函数"] = _curry2(_配分_谐振子配分函数)  # 配分_谐振子配分函数(ω)(T)
    builtins["配分_转动配分函数"] = _curry3(_配分_转动配分函数)      # 配分_转动配分函数(I)(T)(σ)
    builtins["配分_自由能"] = _curry2(_配分_自由能)                  # 配分_自由能(Z)(T)

    # --- 熵与自由能 ---
    builtins["熵_玻尔兹曼熵"] = _熵_玻尔兹曼熵                       # 熵_玻尔兹曼熵(W)
    builtins["熵_吉布斯熵"] = _熵_吉布斯熵                           # 熵_吉布斯熵(概率列表)
    builtins["熵_萨克尔泰特罗德"] = _curry4(_熵_萨克尔泰特罗德)      # 熵_萨克尔泰特罗德(N)(V)(m)(U)
    builtins["熵_等温熵变"] = _curry3(_熵_等温熵变)                  # 熵_等温熵变(N)(V1)(V2)
    builtins["熵_理想气体熵变"] = _curry5(_熵_理想气体熵变)

    builtins["熵_焓"] = _curry3(_熵_焓)                             # 熵_焓(U)(P)(V)
    builtins["熵_吉布斯自由能"] = _curry3(_熵_吉布斯自由能)          # 熵_吉布斯自由能(H)(T)(S)
    builtins["熵_等容热容"] = _熵_等容热容                           # 熵_等容热容(N)
    builtins["熵_等压热容"] = _熵_等压热容                           # 熵_等压热容(N)
    builtins["熵_热容比"] = _curry2(_熵_热容比)                     # 熵_热容比(Cp)(Cv)

    # --- 量子统计 ---
    builtins["统计_费米狄拉克"] = _curry3(_统计_费米狄拉克)          # 统计_费米狄拉克(E)(μ)(T)
    builtins["统计_玻色爱因斯坦"] = _curry3(_统计_玻色爱因斯坦)      # 统计_玻色爱因斯坦(E)(μ)(T)
    builtins["统计_费米能级"] = _curry2(_统计_费米能级)              # 统计_费米能级(m)(n)
    builtins["统计_费米温度"] = _统计_费米温度                       # 统计_费米温度(EF)
    builtins["统计_费米速度"] = _curry2(_统计_费米速度)              # 统计_费米速度(EF)(m)
    builtins["统计_德拜频率"] = _curry2(_统计_德拜频率)              # 统计_德拜频率(vs)(n)
    builtins["统计_德拜温度"] = _统计_德拜温度                       # 统计_德拜温度(ωD)
    builtins["统计_德拜热容低温"] = _curry3(_统计_德拜热容低温)      # 统计_德拜热容低温(N)(T)(θD)
    builtins["统计_维恩位移"] = _统计_维恩位移                       # 统计_维恩位移(T)
    builtins["统计_黑体辐射功率"] = _统计_黑体辐射功率               # 统计_黑体辐射功率(T)
    builtins["统计_光子气体内能密度"] = _统计_光子气体内能密度       # 统计_光子气体内能密度(T)

    # --- 涨落与关联 ---
    builtins["涨落_能量涨落"] = _curry2(_涨落_能量涨落)             # 涨落_能量涨落(T)(Cv)
    builtins["涨落_粒子数涨落"] = _curry2(_涨落_粒子数涨落)         # 涨落_粒子数涨落(T)(∂N/∂μ)
    builtins["涨落_相对能量涨落"] = _curry3(_涨落_相对能量涨落)     # 涨落_相对能量涨落(T)(Cv)(E)
    builtins["涨落_布朗位移"] = _curry2(_涨落_布朗位移)             # 涨落_布朗位移(D)(t)
    builtins["涨落_爱因斯坦扩散系数"] = _curry3(_涨落_爱因斯坦扩散系数)  # 涨落_爱因斯坦扩散系数(T)(η)(r)
    builtins["涨落_密度涨落"] = _curry3(_涨落_密度涨落)             # 涨落_密度涨落(T)(κT)(V)
    builtins["涨落_体积涨落"] = _curry3(_涨落_体积涨落)             # 涨落_体积涨落(T)(V)(κT)
    builtins["涨落_温度涨落"] = _curry2(_涨落_温度涨落)             # 涨落_温度涨落(T)(Cv)

    # --- 物理常量 ---
    builtins["kB_玻尔兹曼"] = K_B
    builtins["R_气体常数统计"] = R_GAS
    builtins["sigma_斯特藩玻尔兹曼"] = SIGMA_SB
    builtins["b_维恩位移"] = WIEN_B


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



def _statmech_symtab_names() -> list[str]:
    """返回统计力学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 麦克斯韦-玻尔兹曼分布
    for n in ["最概然速率", "平均速率", "方均根速率", "分布函数",
              "理想气体压强", "理想气体压力", "平均自由程", "碰撞频率"]:
        names.append(f"速率_{n}")
    # 配分函数
    for n in ["玻尔兹曼因子", "离散配分函数", "简并配分函数",
              "谐振子配分函数", "转动配分函数", "自由能"]:
        names.append(f"配分_{n}")
    # 熵与自由能
    for n in ["玻尔兹曼熵", "吉布斯熵", "萨克尔泰特罗德",
              "等温熵变", "理想气体熵变",
              "焓", "吉布斯自由能", "等容热容", "等压热容", "热容比"]:
        names.append(f"熵_{n}")
    # 量子统计
    for n in ["费米狄拉克", "玻色爱因斯坦", "费米能级",
              "费米温度", "费米速度", "德拜频率", "德拜温度",
              "德拜热容低温", "维恩位移", "黑体辐射功率", "光子气体内能密度"]:
        names.append(f"统计_{n}")
    # 涨落与关联
    for n in ["能量涨落", "粒子数涨落", "相对能量涨落",
              "布朗位移", "爱因斯坦扩散系数",
              "密度涨落", "体积涨落", "温度涨落"]:
        names.append(f"涨落_{n}")
    # 物理常量
    for n in ["kB_玻尔兹曼", "R_气体常数统计",
              "sigma_斯特藩玻尔兹曼", "b_维恩位移"]:
        names.append(n)
    return names
