"""Matha 机械领域模块：量子力学（Quantum Mechanics）。

基于电磁学 + 光学 + mathlib 数学地基，演化量子力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、波函数与薛定谔方程（Wave Function & Schrödinger Equation）
  1) 德布罗意波长：λ = h/p = h/(mv)
  2) 概率密度：ρ = |ψ|²
  3) 波函数归一化检查：∫|ψ|²dx = 1
  4) 动能算符期望值（简化）：<T> = p²/(2m)
  5) 含时薛定谔方程能量：E = ℏω
  6) 定态薛定谔方程（自由粒子）：E = ℏ²k²/(2m)
  7) 波数与动量：p = ℏk

二、不确定性原理（Uncertainty Principle）
  1) 位置-动量不确定性：Δx·Δp ≥ ℏ/2
  2) 能量-时间不确定性：ΔE·Δt ≥ ℏ/2
  3) 最小不确定性波包：Δx·Δp = ℏ/2
  4) 由位置不确定度求动量不确定度：Δp = ℏ/(2Δx)

三、角动量与自旋（Angular Momentum & Spin）
  1) 轨道角动量模：|L| = ℏ√(l(l+1))
  2) 角动量z分量：Lz = m_l·ℏ
  3) 自旋角动量模：|S| = ℏ√(s(s+1))
  4) 自旋z分量：Sz = m_s·ℏ
  5) 总角动量模：|J| = ℏ√(j(j+1))
  6) 磁矩：μ = -g·(e/2m)·J

四、势阱与能级（Potential Well & Energy Levels）
  1) 无限深方势阱能级：En = n²π²ℏ²/(2mL²)
  2) 氢原子能级：En = -13.6/n² eV
  3) 一维谐振子能级：En = (n+1/2)ℏω
  4) 谐振子基态波函数宽度：a = √(ℏ/(mω))
  5) 势垒高度与穿透深度
  6) 有限深势阱束缚态数

五、量子隧穿与散射（Quantum Tunneling & Scattering）
  1) 隧穿概率（WKB近似）：T ≈ exp(-2κa)
  2) 衰减常数：κ = √(2m(V₀-E))/ℏ
  3) 势垒透射系数（方势垒）：T = [1 + V₀²sinh²(κa)/(4E(V₀-E))]⁻¹
  4) 光电效应：Kmax = hf - φ
  5) 康普顿波长：λC = h/(mc)
  6) 康普顿散射波长偏移：Δλ = (h/mc)(1-cosθ)

设计原则：
  - 所有角度输入/输出均为弧度
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 波_ / 不确定_ / 角动_ / 势阱_ / 隧穿_ 区分子领域
  - 量子力学常量作为常量注册
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
# 物理常量（统一来源）
# ============================================================
from src.stdlib.physics_constants import C as _P

# 普朗克常量 h = 6.626e-34 J·s
H_PLANCK = _P.h_planck
# 约化普朗克常量 ℏ = h/(2π) = 1.055e-34 J·s
HBAR = _P.hbar
# 基本电荷 e = 1.602e-19 C
E_CHARGE = _P.e_charge
# 电子静止质量 m_e = 9.109e-31 kg
M_ELECTRON = 9.1093837015e-31
# 质子静止质量 m_p = 1.673e-27 kg
M_PROTON = 1.67262192369e-27
# 玻尔半径 a₀ = 5.292e-11 m
A_BOHR = 5.29177210903e-11
# 里德伯能量 Ry = 13.6 eV = 2.180e-18 J
RY_ENERGY = 2.1798723611035e-18
# 玻尔磁子 μ_B = 9.274e-24 J/T
MU_B = 9.2740100783e-24
# 电子康普顿波长 λ_C = 2.426e-12 m
LAMBDA_C = 2.42631023867e-12
# 精细结构常数 α ≈ 1/137
ALPHA_FS = 7.2973525693e-3
# 阿伏伽德罗常数 N_A
N_A = _P.N_A


# ============================================================
# 一、波函数与薛定谔方程（Wave Function & Schrödinger Equation）
# ============================================================

# 德布罗意波长：λ = h/p = h/(mv)
def _波_德布罗意波长(m, v): return H_PLANCK / (m * v)
# 德布罗意波长（由动量）：λ = h/p
def _波_德布罗意波长动量(p): return H_PLANCK / p
# 概率密度：ρ = |ψ|²（对实数波函数即 ψ²）
def _波_概率密度(psi): return abs(psi) ** 2
# 含时薛定谔方程能量：E = ℏω
def _波_能量由频率(omega): return HBAR * omega
# 定态薛定谔方程（自由粒子）：E = ℏ²k²/(2m)
def _波_自由粒子能量(k, m): return HBAR ** 2 * k ** 2 / (2 * m)
# 动量与波数：p = ℏk
def _波_动量由波数(k): return HBAR * k
# 波数由动量：k = p/ℏ
def _波_波数由动量(p): return p / HBAR
# 动能期望值：<T> = p²/(2m)
def _波_动能期望(p, m): return p ** 2 / (2 * m)
# 角频率由能量：ω = E/ℏ
def _波_角频率由能量(E): return E / HBAR


# ============================================================
# 二、不确定性原理（Uncertainty Principle）
# ============================================================

# 位置-动量不确定性：Δx·Δp ≥ ℏ/2 → 给定 Δx 求 Δp 最小值
def _不确定_动量不确定度(dx): return HBAR / (2 * dx)
# 位置-动量不确定性：给定 Δp 求 Δx 最小值
def _不确定_位置不确定度(dp): return HBAR / (2 * dp)
# 能量-时间不确定性：ΔE·Δt ≥ ℏ/2 → 给定 Δt 求 ΔE 最小值
def _不确定_能量不确定度(dt): return HBAR / (2 * dt)
# 能量-时间不确定性：给定 ΔE 求 Δt 最小值
def _不确定_时间不确定度(dE): return HBAR / (2 * dE)
# 不确定性乘积下限：ℏ/2
def _不确定_下限(): return HBAR / 2
# 验证不确定性原理：返回 Δx·Δp 是否 ≥ ℏ/2
def _不确定_验证(dx, dp): return dx * dp >= HBAR / 2 - 1e-50


# ============================================================
# 三、角动量与自旋（Angular Momentum & Spin）
# ============================================================

# 轨道角动量模：|L| = ℏ√(l(l+1))
def _角动_轨道模(l): return HBAR * math.sqrt(l * (l + 1))
# 角动量z分量：Lz = m_l·ℏ
def _角动_轨道z(ml): return ml * HBAR
# 自旋角动量模：|S| = ℏ√(s(s+1))
def _角动_自旋模(s): return HBAR * math.sqrt(s * (s + 1))
# 自旋z分量：Sz = m_s·ℏ
def _角动_自旋z(ms): return ms * HBAR
# 总角动量模：|J| = ℏ√(j(j+1))
def _角动_总模(j): return HBAR * math.sqrt(j * (j + 1))
# 总角动量z分量：Jz = m_j·ℏ
def _角动_总z(mj): return mj * HBAR
# 玻尔磁子磁矩：μ = -μ_B·g·m（m 为磁量子数）
def _角动_磁矩(g, m): return -MU_B * g * m
# 朗德g因子（LS耦合）：g = 1 + [J(J+1)+S(S+1)-L(L+1)]/(2J(J+1))
def _角动_朗德g(J, L, S):
    if J == 0:
        return 0.0
    return 1 + (J*(J+1) + S*(S+1) - L*(L+1)) / (2*J*(J+1))


# ============================================================
# 四、势阱与能级（Potential Well & Energy Levels）
# ============================================================

# 无限深方势阱能级：En = n²π²ℏ²/(2mL²)
def _势阱_无限深能级(n, m, L): return n ** 2 * math.pi ** 2 * HBAR ** 2 / (2 * m * L ** 2)
# 氢原子能级（Joule）：En = -Ry/n²
def _势阱_氢原子能级J(n): return -RY_ENERGY / n ** 2
# 氢原子能级（eV）：En = -13.6/n²
def _势阱_氢原子能级eV(n): return -13.6 / n ** 2
# 一维谐振子能级：En = (n+1/2)ℏω
def _势阱_谐振子能级(n, omega): return (n + 0.5) * HBAR * omega
# 谐振子基态波函数宽度：a = √(ℏ/(mω))
def _势阱_谐振子特征长度(m, omega): return math.sqrt(HBAR / (m * omega))
# 谐振子经典振幅：A = √(2E/(mω²))
def _势阱_谐振子振幅(E, m, omega): return math.sqrt(2 * E / (m * omega ** 2))
# 玻尔半径（由基本常数）：a₀ = 4πε₀ℏ²/(m_e·e²)
def _势阱_玻尔半径(): return A_BOHR
# 氢原子轨道半径（第n能级）：r_n = n²·a₀
def _势阱_氢原子半径(n): return n ** 2 * A_BOHR
# 氢原子电离能（基态）：E₁ = 13.6 eV
def _势阱_氢原子电离能(): return RY_ENERGY


# ============================================================
# 五、量子隧穿与散射（Quantum Tunneling & Scattering）
# ============================================================

# 衰减常数：κ = √(2m(V₀-E))/ℏ
def _隧穿_衰减常数(m, V0, E):
    if V0 <= E:
        return 0.0
    return math.sqrt(2 * m * (V0 - E)) / HBAR

# 隧穿概率（WKB近似）：T ≈ exp(-2κa)
def _隧穿_WKB概率(kappa, a): return math.exp(-2 * kappa * a)
# WKB隧穿概率（直接由参数）：T = exp(-2a√(2m(V₀-E))/ℏ)
def _隧穿_WKB概率直接(m, V0, E, a):
    kappa = math.sqrt(2 * m * (V0 - E)) / HBAR if V0 > E else 0.0
    return math.exp(-2 * kappa * a)

# 方势垒透射系数（E < V₀）：T = [1 + V₀²sinh²(κa)/(4E(V₀-E))]⁻¹
def _隧穿_方势垒透射(E, V0, m, a):
    if E >= V0:
        # E > V₀ 的情况：T = [1 + V₀²sin²(k'a)/(4E(V₀-E))]⁻¹, k'=√(2m(E-V₀))/ℏ
        k_prime = math.sqrt(2 * m * (E - V0)) / HBAR
        sin_term = math.sin(k_prime * a) ** 2
        return 1.0 / (1 + V0 ** 2 * sin_term / (4 * E * (E - V0)))
    kappa = math.sqrt(2 * m * (V0 - E)) / HBAR
    sinh_term = math.sinh(kappa * a) ** 2
    return 1.0 / (1 + V0 ** 2 * sinh_term / (4 * E * (V0 - E)))

# 光电效应：Kmax = hf - φ
def _隧穿_光电效应(f, phi): return H_PLANCK * f - phi
# 光电效应截止频率：f₀ = φ/h
def _隧穿_截止频率(phi): return phi / H_PLANCK
# 康普顿波长：λC = h/(mc)
def _隧穿_康普顿波长(m): return H_PLANCK / (m * C_LIGHT) 
# 康普顿散射波长偏移：Δλ = (h/mc)(1-cosθ)
def _隧穿_康普顿偏移(theta): return LAMBDA_C * (1 - math.cos(theta))


# 光速常量（供康普顿波长函数使用）
C_LIGHT = _P.c


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_quantum(builtins: dict) -> None:
    """将量子力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（structural 之后）。
    """
    # --- 波函数与薛定谔方程 ---
    builtins["波_德布罗意波长"] = _curry2(_波_德布罗意波长)          # 波_德布罗意波长(m)(v)
    builtins["波_德布罗意波长动量"] = _波_德布罗意波长动量            # 波_德布罗意波长动量(p)
    builtins["波_概率密度"] = _波_概率密度                           # 波_概率密度(ψ)
    builtins["波_能量由频率"] = _波_能量由频率                        # 波_能量由频率(ω)
    builtins["波_自由粒子能量"] = _curry2(_波_自由粒子能量)          # 波_自由粒子能量(k)(m)
    builtins["波_动量由波数"] = _波_动量由波数                       # 波_动量由波数(k)
    builtins["波_波数由动量"] = _波_波数由动量                       # 波_波数由动量(p)
    builtins["波_动能期望"] = _curry2(_波_动能期望)                  # 波_动能期望(p)(m)
    builtins["波_角频率由能量"] = _波_角频率由能量                    # 波_角频率由能量(E)

    # --- 不确定性原理 ---
    builtins["不确定_动量不确定度"] = _不确定_动量不确定度            # 不确定_动量不确定度(Δx)
    builtins["不确定_位置不确定度"] = _不确定_位置不确定度            # 不确定_位置不确定度(Δp)
    builtins["不确定_能量不确定度"] = _不确定_能量不确定度            # 不确定_能量不确定度(Δt)
    builtins["不确定_时间不确定度"] = _不确定_时间不确定度            # 不确定_时间不确定度(ΔE)
    builtins["不确定_下限"] = _不确定_下限                           # 不确定_下限()
    builtins["不确定_验证"] = _curry2(_不确定_验证)                  # 不确定_验证(Δx)(Δp)

    # --- 角动量与自旋 ---
    builtins["角动_轨道模"] = _角动_轨道模                           # 角动_轨道模(l)
    builtins["角动_轨道z"] = _角动_轨道z                             # 角动_轨道z(ml)
    builtins["角动_自旋模"] = _角动_自旋模                           # 角动_自旋模(s)
    builtins["角动_自旋z"] = _角动_自旋z                             # 角动_自旋z(ms)
    builtins["角动_总模"] = _角动_总模                               # 角动_总模(j)
    builtins["角动_总z"] = _角动_总z                                 # 角动_总z(mj)
    builtins["角动_磁矩"] = _curry2(_角动_磁矩)                      # 角动_磁矩(g)(m)
    builtins["角动_朗德g"] = _curry3(_角动_朗德g)                    # 角动_朗德g(J)(L)(S)

    # --- 势阱与能级 ---
    builtins["势阱_无限深能级"] = _curry3(_势阱_无限深能级)          # 势阱_无限深能级(n)(m)(L)
    builtins["势阱_氢原子能级J"] = _势阱_氢原子能级J                 # 势阱_氢原子能级J(n)
    builtins["势阱_氢原子能级eV"] = _势阱_氢原子能级eV               # 势阱_氢原子能级eV(n)
    builtins["势阱_谐振子能级"] = _curry2(_势阱_谐振子能级)          # 势阱_谐振子能级(n)(ω)
    builtins["势阱_谐振子特征长度"] = _curry2(_势阱_谐振子特征长度)   # 势阱_谐振子特征长度(m)(ω)
    builtins["势阱_谐振子振幅"] = _curry3(_势阱_谐振子振幅)          # 势阱_谐振子振幅(E)(m)(ω)
    builtins["势阱_玻尔半径"] = _势阱_玻尔半径                       # 势阱_玻尔半径()
    builtins["势阱_氢原子半径"] = _势阱_氢原子半径                   # 势阱_氢原子半径(n)
    builtins["势阱_氢原子电离能"] = _势阱_氢原子电离能               # 势阱_氢原子电离能()

    # --- 量子隧穿与散射 ---
    builtins["隧穿_衰减常数"] = _curry3(_隧穿_衰减常数)              # 隧穿_衰减常数(m)(V0)(E)
    builtins["隧穿_WKB概率"] = _curry2(_隧穿_WKB概率)               # 隧穿_WKB概率(κ)(a)
    builtins["隧穿_WKB概率直接"] = _curry4(_隧穿_WKB概率直接)       # 隧穿_WKB概率直接(m)(V0)(E)(a)
    builtins["隧穿_方势垒透射"] = _curry4(_隧穿_方势垒透射)          # 隧穿_方势垒透射(E)(V0)(m)(a)
    builtins["隧穿_光电效应"] = _curry2(_隧穿_光电效应)              # 隧穿_光电效应(f)(φ)
    builtins["隧穿_截止频率"] = _隧穿_截止频率                       # 隧穿_截止频率(φ)
    builtins["隧穿_康普顿波长"] = _隧穿_康普顿波长                   # 隧穿_康普顿波长(m)
    builtins["隧穿_康普顿偏移"] = _隧穿_康普顿偏移                   # 隧穿_康普顿偏移(θ)

    # --- 物理常量 ---
    builtins["h_普朗克"] = H_PLANCK
    builtins["hbar_约化普朗克"] = HBAR
    builtins["e_电荷"] = E_CHARGE
    builtins["me_电子质量"] = M_ELECTRON
    builtins["mp_质子质量"] = M_PROTON
    builtins["a0_玻尔半径"] = A_BOHR
    builtins["Ry_里德伯能"] = RY_ENERGY
    builtins["muB_玻尔磁子"] = MU_B
    builtins["lambdaC_康普顿波长"] = LAMBDA_C
    builtins["alpha_精细结构"] = ALPHA_FS
    builtins["NA_阿伏伽德罗"] = N_A


def _quantum_symtab_names() -> list[str]:
    """返回量子力学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 波函数与薛定谔方程
    for n in ["德布罗意波长", "德布罗意波长动量", "概率密度", "能量由频率",
              "自由粒子能量", "动量由波数", "波数由动量", "动能期望", "角频率由能量"]:
        names.append(f"波_{n}")
    # 不确定性原理
    for n in ["动量不确定度", "位置不确定度", "能量不确定度",
              "时间不确定度", "下限", "验证"]:
        names.append(f"不确定_{n}")
    # 角动量与自旋
    for n in ["轨道模", "轨道z", "自旋模", "自旋z",
              "总模", "总z", "磁矩", "朗德g"]:
        names.append(f"角动_{n}")
    # 势阱与能级
    for n in ["无限深能级", "氢原子能级J", "氢原子能级eV",
              "谐振子能级", "谐振子特征长度", "谐振子振幅",
              "玻尔半径", "氢原子半径", "氢原子电离能"]:
        names.append(f"势阱_{n}")
    # 量子隧穿与散射
    for n in ["衰减常数", "WKB概率", "WKB概率直接",
              "方势垒透射", "光电效应", "截止频率",
              "康普顿波长", "康普顿偏移"]:
        names.append(f"隧穿_{n}")
    # 物理常量
    for n in ["h_普朗克", "hbar_约化普朗克", "e_电荷", "me_电子质量",
              "mp_质子质量", "a0_玻尔半径", "Ry_里德伯能",
              "muB_玻尔磁子", "lambdaC_康普顿波长",
              "alpha_精细结构", "NA_阿伏伽德罗"]:
        names.append(n)
    return names
