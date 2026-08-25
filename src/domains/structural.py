"""Matha 机械领域模块：结构力学（Structural Mechanics）。

基于材料力学 + 动力学 + mathlib 数学地基，演化结构力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、应力状态分析（Stress State Analysis）
  1) 莫尔圆主应力：σ₁,₂ = (σx+σy)/2 ± √[((σx-σy)/2)² + τxy²]
  2) 莫尔圆最大剪应力：τmax = (σ₁-σ₂)/2
  3) 任意截面应力：σn = (σx+σy)/2 + (σx-σy)/2·cos2θ + τxy·sin2θ
  4) 主应力方向：tan2θp = 2τxy/(σx-σy)
  5) 广义胡克定律（三向）：εx = (σx-ν(σy+σz))/E
  6) 第四强度理论（von Mises）：σeq = √(σ₁²+σ₂²+σ₃²-σ₁σ₂-σ₂σ₃-σ₃σ₁)
  7) 第三强度理论（Tresca）：σeq = σ₁-σ₃
  8) 体积应变：θ = εx+εy+εz = (1-2ν)(σx+σy+σz)/E

二、梁的弯曲（Beam Bending）
  1) 简支梁均布载荷：Mmax = qL²/8, δmax = 5qL⁴/(384EI)
  2) 简支梁跨中集中力：Mmax = PL/4, δmax = PL³/(48EI)
  3) 悬臂梁均布载荷：Mmax = qL²/2, δmax = qL⁴/(8EI)
  4) 悬臂梁端部集中力：Mmax = PL, δmax = PL³/(3EI)
  5) 梁端转角
  6) 弯曲正应力：σ = M·y/I

三、压杆稳定（Column Buckling）
  1) 欧拉临界力：Pcr = π²EI/(μL)²
  2) 欧拉临界应力：σcr = π²E/λ²
  3) 长细比：λ = μL/r
  4) 回转半径：r = √(I/A)
  5) 临界长细比：λp = π√(E/σp)
  6) 安全工作压力：P_allow = Pcr/n

四、桁架与结构（Truss & Structures）
  1) 桁架杆件内力（给定角度）
  2) 简支梁支座反力（均布载荷）：RA = RB = qL/2
  3) 简支梁支座反力（跨中集中力）：RA = RB = P/2
  4) 悬臂梁固定端反力
  5) 超静定次数：n = m + r - 2j（m 杆数, r 支座反力数, j 节点数）

五、应变能与冲击（Strain Energy & Impact）
  1) 轴向应变能：U = N²L/(2EA)
  2) 弯曲应变能：U = M²L/(2EI)
  3) 剪切应变能：U = V²L/(2GA)
  4) 冲击动荷系数：Kd = 1+√(1+2h/Δst)
  5) 卡氏定理位移：δ = ∂U/∂P（简化形式）
  6) 应变能密度：u = σ²/(2E)

设计原则：
  - 所有角度输入/输出均为弧度
  - 多参函数一律 _curry2/_curry3/_curry4/_curry5 封装
  - 前缀 应力_ / 梁_ / 压杆_ / 桁架_ / 能量_ 区分子领域
  - 截面几何性质在 mechanics.py 已有，此处引用
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
# 一、应力状态分析（Stress State Analysis）
# ============================================================

# 莫尔圆主应力 σ₁（大主应力）
def _应力_主应力1(sigma_x, sigma_y, tau_xy):
    avg = (sigma_x + sigma_y) / 2
    r = math.sqrt(((sigma_x - sigma_y) / 2) ** 2 + tau_xy ** 2)
    return avg + r

# 莫尔圆主应力 σ₂（小主应力）
def _应力_主应力2(sigma_x, sigma_y, tau_xy):
    avg = (sigma_x + sigma_y) / 2
    r = math.sqrt(((sigma_x - sigma_y) / 2) ** 2 + tau_xy ** 2)
    return avg - r

# 最大剪应力 τmax = (σ₁-σ₂)/2
def _应力_最大剪应力(sigma_x, sigma_y, tau_xy):
    r = math.sqrt(((sigma_x - sigma_y) / 2) ** 2 + tau_xy ** 2)
    return r

# 主应力方向 θp = 0.5·arctan(2τxy/(σx-σy))
def _应力_主应力方向(sigma_x, sigma_y, tau_xy):
    if abs(sigma_x - sigma_y) < 1e-30:
        return math.pi / 4
    return 0.5 * math.atan2(2 * tau_xy, sigma_x - sigma_y)

# 任意截面正应力：σn = (σx+σy)/2 + (σx-σy)/2·cos2θ + τxy·sin2θ
def _应力_截面正应力(sigma_x, sigma_y, tau_xy, theta):
    avg = (sigma_x + sigma_y) / 2
    return avg + (sigma_x - sigma_y) / 2 * math.cos(2 * theta) + tau_xy * math.sin(2 * theta)

# 任意截面剪应力：τn = -(σx-σy)/2·sin2θ + τxy·cos2θ
def _应力_截面剪应力(sigma_x, sigma_y, tau_xy, theta):
    return -(sigma_x - sigma_y) / 2 * math.sin(2 * theta) + tau_xy * math.cos(2 * theta)

# 广义胡克定律（三向）：εx = (σx-ν(σy+σz))/E
def _应力_广义胡克应变(sigma_x, sigma_y, sigma_z, E, nu, axis):
    """axis: 'x'=0, 'y'=1, 'z'=2"""
    s = [sigma_x, sigma_y, sigma_z]
    other = [s[i] for i in range(3) if i != axis]
    return (s[axis] - nu * (other[0] + other[1])) / E

# von Mises 等效应力（第四强度理论）
def _应力_vonMises(s1, s2, s3):
    return math.sqrt(s1**2 + s2**2 + s3**2 - s1*s2 - s2*s3 - s3*s1)

# Tresca 等效应力（第三强度理论）
def _应力_Tresca(s1, s2, s3):
    return max(abs(s1-s2), abs(s2-s3), abs(s3-s1))

# 体积应变 θ = (1-2ν)(σx+σy+σz)/E
def _应力_体积应变(sigma_x, sigma_y, sigma_z, E, nu):
    return (1 - 2 * nu) * (sigma_x + sigma_y + sigma_z) / E


# ============================================================
# 二、梁的弯曲（Beam Bending）
# ============================================================

# --- 简支梁（Simply Supported Beam） ---
# 简支梁均布载荷最大弯矩：Mmax = qL²/8
def _梁_简支均布弯矩(q, L): return q * L ** 2 / 8
# 简支梁均布载荷最大挠度：δmax = 5qL⁴/(384EI)
def _梁_简支均布挠度(q, L, E, I): return 5 * q * L ** 4 / (384 * E * I)
# 简支梁均布载荷端部转角：θ = qL³/(24EI)
def _梁_简支均布转角(q, L, E, I): return q * L ** 3 / (24 * E * I)
# 简支梁跨中集中力最大弯矩：Mmax = PL/4
def _梁_简支集中弯矩(P, L): return P * L / 4
# 简支梁跨中集中力最大挠度：δmax = PL³/(48EI)
def _梁_简支集中挠度(P, L, E, I): return P * L ** 3 / (48 * E * I)
# 简支梁跨中集中力端部转角：θ = PL²/(16EI)
def _梁_简支集中转角(P, L, E, I): return P * L ** 2 / (16 * E * I)

# --- 悬臂梁（Cantilever Beam） ---
# 悬臂梁均布载荷最大弯矩（固定端）：Mmax = qL²/2
def _梁_悬臂均布弯矩(q, L): return q * L ** 2 / 2
# 悬臂梁均布载荷最大挠度（自由端）：δmax = qL⁴/(8EI)
def _梁_悬臂均布挠度(q, L, E, I): return q * L ** 4 / (8 * E * I)
# 悬臂梁端部集中力最大弯矩（固定端）：Mmax = PL
def _梁_悬臂集中弯矩(P, L): return P * L
# 悬臂梁端部集中力最大挠度（自由端）：δmax = PL³/(3EI)
def _梁_悬臂集中挠度(P, L, E, I): return P * L ** 3 / (3 * E * I)
# 悬臂梁端部集中力端部转角：θ = PL²/(2EI)
def _梁_悬臂集中转角(P, L, E, I): return P * L ** 2 / (2 * E * I)

# 弯曲正应力：σ = M·y/I
def _梁_弯曲正应力(M, y, I): return M * y / I
# 弯曲剪应力（矩形截面）：τ = 3V/(2A)
def _梁_矩形剪应力(V, A): return 1.5 * V / A


# ============================================================
# 三、压杆稳定（Column Buckling）
# ============================================================

# 欧拉临界力：Pcr = π²EI/(μL)²
def _压杆_欧拉临界力(E, I, mu, L): return math.pi ** 2 * E * I / (mu * L) ** 2
# 欧拉临界应力：σcr = π²E/λ²
def _压杆_欧拉临界应力(E, lam): return math.pi ** 2 * E / lam ** 2
# 长细比：λ = μL/r
def _压杆_长细比(mu, L, r): return mu * L / r
# 回转半径：r = √(I/A)
def _压杆_回转半径(I, A): return math.sqrt(I / A)
# 临界长细比：λp = π√(E/σp)
def _压杆_临界长细比(E, sigma_p): return math.pi * math.sqrt(E / sigma_p)
# 安全工作压力：P_allow = Pcr/n
def _压杆_安全压力(P_cr, n): return P_cr / n
# 长细比（由几何直接计算）：λ = μL/√(I/A)
def _压杆_长细比几何(mu, L, I, A):
    r = math.sqrt(I / A)
    return mu * L / r


# ============================================================
# 四、桁架与结构（Truss & Structures）
# ============================================================

# 简支梁均布载荷支座反力：RA = RB = qL/2
def _桁架_简支均布反力(q, L): return q * L / 2
# 简支梁跨中集中力支座反力：RA = RB = P/2
def _桁架_简支集中反力(P): return P / 2
# 悬臂梁均布载荷固定端反力：R = qL
def _桁架_悬臂均布反力(q, L): return q * L
# 悬臂梁端部集中力固定端反力：R = P
def _桁架_悬臂集中反力(P): return P
# 桁架杆件内力（给定角度和节点力）
def _桁架_杆件内力(F, theta): return F / math.cos(theta) if abs(math.cos(theta)) > 1e-15 else F / math.sin(theta)
# 超静定次数：n = m + r - 2j
def _桁架_超静定次数(m, r, j): return m + r - 2 * j
# 桁架节点平衡（二维）→ 汇交力系合力
def _桁架_合力(Fx_list, Fy_list):
    Fx = sum(Fx_list) if isinstance(Fx_list, list) else Fx_list
    Fy = sum(Fy_list) if isinstance(Fy_list, list) else Fy_list
    return math.sqrt(Fx ** 2 + Fy ** 2)


# ============================================================
# 五、应变能与冲击（Strain Energy & Impact）
# ============================================================

# 轴向拉压应变能：U = N²L/(2EA)
def _能量_轴向应变能(N, L, E, A): return N ** 2 * L / (2 * E * A)
# 弯曲应变能（均布弯矩简化）：U = M²L/(2EI)
def _能量_弯曲应变能(M, L, E, I): return M ** 2 * L / (2 * E * I)
# 剪切应变能：U = V²L/(2GA)
def _能量_剪切应变能(V, L, G, A): return V ** 2 * L / (2 * G * A)
# 冲击动荷系数：Kd = 1+√(1+2h/Δst)
def _能量_动荷系数(h, delta_st): return 1 + math.sqrt(1 + 2 * h / delta_st)
# 应变能密度：u = σ²/(2E)
def _能量_应变能密度(sigma, E): return sigma ** 2 / (2 * E)
# 扭转应变能：U = T²L/(2GIp)
def _能量_扭转应变能(T, L, G, Ip): return T ** 2 * L / (2 * G * Ip)
# 总应变能（拉压+弯曲+剪切）：U_total
def _能量_总应变能(U_axial, U_bending, U_shear):
    return U_axial + U_bending + U_shear


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_structural(builtins: dict) -> None:
    """将结构力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（optics 之后）。
    """
    # --- 应力状态分析 ---
    builtins["应力_主应力1"] = _curry3(_应力_主应力1)          # 应力_主应力1(σx)(σy)(τxy)
    builtins["应力_主应力2"] = _curry3(_应力_主应力2)          # 应力_主应力2(σx)(σy)(τxy)
    builtins["应力_最大剪应力"] = _curry3(_应力_最大剪应力)    # 应力_最大剪应力(σx)(σy)(τxy)
    builtins["应力_主应力方向"] = _curry3(_应力_主应力方向)    # 应力_主应力方向(σx)(σy)(τxy)
    builtins["应力_截面正应力"] = _curry4(_应力_截面正应力)    # 应力_截面正应力(σx)(σy)(τxy)(θ)
    builtins["应力_截面剪应力"] = _curry4(_应力_截面剪应力)    # 应力_截面剪应力(σx)(σy)(τxy)(θ)
    builtins["应力_vonMises"] = _curry3(_应力_vonMises)        # 应力_vonMises(σ1)(σ2)(σ3)
    builtins["应力_Tresca"] = _curry3(_应力_Tresca)            # 应力_Tresca(σ1)(σ2)(σ3)
    builtins["应力_体积应变"] = _curry5(_应力_体积应变)        # 应力_体积应变(σx)(σy)(σz)(E)(ν)

    # --- 梁的弯曲：简支梁 ---
    builtins["梁_简支均布弯矩"] = _curry2(_梁_简支均布弯矩)    # 梁_简支均布弯矩(q)(L)
    builtins["梁_简支均布挠度"] = _curry4(_梁_简支均布挠度)    # 梁_简支均布挠度(q)(L)(E)(I)
    builtins["梁_简支均布转角"] = _curry4(_梁_简支均布转角)    # 梁_简支均布转角(q)(L)(E)(I)
    builtins["梁_简支集中弯矩"] = _curry2(_梁_简支集中弯矩)    # 梁_简支集中弯矩(P)(L)
    builtins["梁_简支集中挠度"] = _curry4(_梁_简支集中挠度)    # 梁_简支集中挠度(P)(L)(E)(I)
    builtins["梁_简支集中转角"] = _curry4(_梁_简支集中转角)    # 梁_简支集中转角(P)(L)(E)(I)

    # --- 梁的弯曲：悬臂梁 ---
    builtins["梁_悬臂均布弯矩"] = _curry2(_梁_悬臂均布弯矩)    # 梁_悬臂均布弯矩(q)(L)
    builtins["梁_悬臂均布挠度"] = _curry4(_梁_悬臂均布挠度)    # 梁_悬臂均布挠度(q)(L)(E)(I)
    builtins["梁_悬臂集中弯矩"] = _curry2(_梁_悬臂集中弯矩)    # 梁_悬臂集中弯矩(P)(L)
    builtins["梁_悬臂集中挠度"] = _curry4(_梁_悬臂集中挠度)    # 梁_悬臂集中挠度(P)(L)(E)(I)
    builtins["梁_悬臂集中转角"] = _curry4(_梁_悬臂集中转角)    # 梁_悬臂集中转角(P)(L)(E)(I)

    # --- 梁的弯曲：应力 ---
    builtins["梁_弯曲正应力"] = _curry3(_梁_弯曲正应力)        # 梁_弯曲正应力(M)(y)(I)
    builtins["梁_矩形剪应力"] = _curry2(_梁_矩形剪应力)        # 梁_矩形剪应力(V)(A)

    # --- 压杆稳定 ---
    builtins["压杆_欧拉临界力"] = _curry4(_压杆_欧拉临界力)    # 压杆_欧拉临界力(E)(I)(μ)(L)
    builtins["压杆_欧拉临界应力"] = _curry2(_压杆_欧拉临界应力)  # 压杆_欧拉临界应力(E)(λ)
    builtins["压杆_长细比"] = _curry3(_压杆_长细比)            # 压杆_长细比(μ)(L)(r)
    builtins["压杆_回转半径"] = _curry2(_压杆_回转半径)        # 压杆_回转半径(I)(A)
    builtins["压杆_临界长细比"] = _curry2(_压杆_临界长细比)    # 压杆_临界长细比(E)(σp)
    builtins["压杆_安全压力"] = _curry2(_压杆_安全压力)        # 压杆_安全压力(Pcr)(n)
    builtins["压杆_长细比几何"] = _curry4(_压杆_长细比几何)    # 压杆_长细比几何(μ)(L)(I)(A)

    # --- 桁架与结构 ---
    builtins["桁架_简支均布反力"] = _curry2(_桁架_简支均布反力)  # 桁架_简支均布反力(q)(L)
    builtins["桁架_简支集中反力"] = _桁架_简支集中反力          # 桁架_简支集中反力(P)
    builtins["桁架_悬臂均布反力"] = _curry2(_桁架_悬臂均布反力)  # 桁架_悬臂均布反力(q)(L)
    builtins["桁架_悬臂集中反力"] = _桁架_悬臂集中反力          # 桁架_悬臂集中反力(P)
    builtins["桁架_杆件内力"] = _curry2(_桁架_杆件内力)        # 桁架_杆件内力(F)(θ)
    builtins["桁架_超静定次数"] = _curry3(_桁架_超静定次数)    # 桁架_超静定次数(m)(r)(j)
    builtins["桁架_合力"] = _curry2(_桁架_合力)                  # 桁架_合力(Fx列表)(Fy列表)

    # --- 应变能与冲击 ---
    builtins["能量_轴向应变能"] = _curry4(_能量_轴向应变能)    # 能量_轴向应变能(N)(L)(E)(A)
    builtins["能量_弯曲应变能"] = _curry4(_能量_弯曲应变能)    # 能量_弯曲应变能(M)(L)(E)(I)
    builtins["能量_剪切应变能"] = _curry4(_能量_剪切应变能)    # 能量_剪切应变能(V)(L)(G)(A)
    builtins["能量_动荷系数"] = _curry2(_能量_动荷系数)        # 能量_动荷系数(h)(Δst)
    builtins["能量_应变能密度"] = _curry2(_能量_应变能密度)    # 能量_应变能密度(σ)(E)
    builtins["能量_扭转应变能"] = _curry4(_能量_扭转应变能)    # 能量_扭转应变能(T)(L)(G)(Ip)
    builtins["能量_总应变能"] = _curry3(_能量_总应变能)        # 能量_总应变能(U拉)(U弯)(U剪)


def _structural_symtab_names() -> list[str]:
    """返回结构力学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 应力状态分析
    for n in ["主应力1", "主应力2", "最大剪应力", "主应力方向",
              "截面正应力", "截面剪应力", "vonMises", "Tresca", "体积应变"]:
        names.append(f"应力_{n}")
    # 梁的弯曲
    for n in ["简支均布弯矩", "简支均布挠度", "简支均布转角",
              "简支集中弯矩", "简支集中挠度", "简支集中转角",
              "悬臂均布弯矩", "悬臂均布挠度",
              "悬臂集中弯矩", "悬臂集中挠度", "悬臂集中转角",
              "弯曲正应力", "矩形剪应力"]:
        names.append(f"梁_{n}")
    # 压杆稳定
    for n in ["欧拉临界力", "欧拉临界应力", "长细比",
              "回转半径", "临界长细比", "安全压力", "长细比几何"]:
        names.append(f"压杆_{n}")
    # 桁架与结构
    for n in ["简支均布反力", "简支集中反力", "悬臂均布反力",
              "悬臂集中反力", "杆件内力", "超静定次数", "合力"]:
        names.append(f"桁架_{n}")
    # 应变能与冲击
    for n in ["轴向应变能", "弯曲应变能", "剪切应变能",
              "动荷系数", "应变能密度", "扭转应变能", "总应变能"]:
        names.append(f"能量_{n}")
    return names
