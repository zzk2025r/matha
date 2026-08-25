"""Matha 机械领域扩展模块：流体力学进阶（Advanced Fluid Mechanics）。

基于已有 fluid.py 静力学/运动学/动力学/粘性流动基础，扩展五大进阶子领域。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、边界层理论（Boundary Layer Theory）- 前缀 边界_
  1) 层流边界层厚度（Blasius 解）：δ = 5.0·x/√Re_x
  2) 层流位移厚度：δ* = 1.721·x/√Re_x
  3) 层流动量厚度：θ = 0.664·x/√Re_x
  4) 层流壁面切应力：τ_w = 0.332·ρU²/√Re_x
  5) 层流平板摩擦阻力系数：C_f = 1.328/√Re_L
  6) 湍流边界层厚度（1/7 幂律）：δ = 0.37·x/(Re_x)^(1/5)
  7) 湍流平板摩擦阻力系数（Prandtl）：C_f = 0.074/(Re_L)^(1/5)
  8) 过渡混合摩擦系数（Schlichting）：C_f = 0.074/(Re_L)^(1/5) - 1742/Re_L
  9) 边界层形状因子：H = δ*/θ
  10) 局部雷诺数：Re_x = ρUx/μ = Ux/ν

二、可压缩流动（Compressible Flow）- 前缀 可压缩_
  1) 声速：c = √(γRT)
  2) 马赫数：Ma = v/c
  3) 等熵温度比：T0/T = 1 + (γ-1)/2·Ma²
  4) 等熵压强比：p0/p = [1 + (γ-1)/2·Ma²]^(γ/(γ-1))
  5) 等熵密度比：ρ0/ρ = [1 + (γ-1)/2·Ma²]^(1/(γ-1))
  6) 正激波压强比：p2/p1 = (2γMa₁²-(γ-1))/(γ+1)
  7) 正激波密度比：ρ2/ρ1 = ((γ+1)Ma₁²)/(2+(γ-1)Ma₁²)
  8) 正激波温度比：T2/T1 = (2γMa₁²-(γ-1))(2+(γ-1)Ma₁²)/((γ+1)²·Ma₁²)
  9) 正激波后马赫数：Ma₂ = √((Ma₁²(γ-1)+2)/(2γMa₁²-(γ-1)))
  10) 临界压强比（喉部）：p*/p0 = (2/(γ+1))^(γ/(γ-1))
  11) 临界温度比：T*/T0 = 2/(γ+1)
  12) 拉瓦尔喷管面积比：A/A* = (1/Ma)[(2/(γ+1))(1+(γ-1)/2·Ma²)]^((γ+1)/(2(γ-1)))
  13) 普朗特-迈耶函数：ν = √((γ+1)/(γ-1))·arctan(√((γ-1)/(γ+1)(Ma²-1))) - arctan(√(Ma²-1))

三、明渠水力学（Open Channel Hydraulics）- 前缀 明渠_
  1) 谢才公式：v = C·√(R·S)
  2) 曼宁公式（SI）：v = (1/n)·R^(2/3)·S^(1/2)
  3) 曼宁公式（英制）：v = 1.486/n · R^(2/3)·S^(1/2)
  4) 水力半径（矩形渠）：R = b·h/(b+2h)
  5) 水力半径（梯形渠）：R = (b·h+m·h²)/(b+2h√(1+m²))
  6) 弗劳德数：Fr = v/√(g·h)
  7) 流态判断（缓/临界/急流）
  8) 临界水深（矩形渠）：h_c = (q²/g)^(1/3)
  9) 临界流速：v_c = √(g·h_c)
  10) 水跃共轭水深（矩形渠）：y2/y1 = (1/2)[-1 + √(1+8·Fr₁²)]
  11) 水跃能量损失：ΔE = (y2-y1)³/(4·y1·y2)
  12) 比能：E = h + v²/(2g)

四、泵与风机（Pumps & Fans）- 前缀 泵_
  1) 泵扬程：H = (p2-p1)/ρg + (v2²-v1²)/(2g) + Δz
  2) 泵有效功率：P_w = ρ·g·Q·H
  3) 泵轴功率：P_shaft = ρ·g·Q·H / η
  4) 泵效率：η = P_w / P_shaft
  5) 风机全压功率：P_t = p_t · Q
  6) 比转速：n_s = n·√Q / H^(3/4)
  7) 相似律-流量：Q2/Q1 = (n2/n1)·(D2/D1)³
  8) 相似律-扬程：H2/H1 = (n2/n1)²·(D2/D1)²
  9) 相似律-功率：P2/P1 = (n2/n1)³·(D2/D1)^5
  10) 风机静压升：p_s = p_t - ½ρv²

五、局部损失与管网（Minor Losses & Pipe Networks）- 前缀 管损_
  1) 局部水头损失：h_m = ζ·v²/(2g)
  2) 当量长度法：L_eq = ζ·D / f
  3) 总水头损失：h_total = (fL/D + Σζ)·v²/(2g)
  4) 突扩局部阻力系数：ζ = (1-A1/A2)²
  5) 突缩局部阻力系数：ζ ≈ 0.5·(1-A2/A1)
  6) 管道比阻：S = 8·λ·L/(g·π²·D^5)
  7) 串联管道比阻：S_eq = S1+S2
  8) 并联管道比阻：1/√S_eq = 1/√S1 + 1/√S2
  9) 锐缘入口 ζ = 0.5
  10) 出口损失 ζ = 1.0
  11) 局部阻力查询（弯头、闸阀、蝶阀等）
"""

from __future__ import annotations
import math


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


# ========== 通用物理常量 ==========
G_STANDARD = 9.80665
GAMMA_AIR = 1.4
R_AIR = 287.0
GAMMA_MONO = 5.0 / 3.0
GAMMA_DI = 1.4
GAMMA_POLY = 1.33

MANNING_N = {
    "玻璃_钢": 0.009, "塑料管": 0.010, "混凝土_光滑": 0.011,
    "混凝土_普通": 0.013, "砖砌": 0.015, "块石浆砌": 0.020,
    "河床_砂土": 0.025, "河床_砾石": 0.035, "土渠_平整": 0.022,
    "土渠_杂草": 0.035, "草地_浅流": 0.050, "岩石渠道": 0.040,
}

K_MINOR = {
    "90度弯头_常规": 0.30, "90度弯头_长半径": 0.20, "45度弯头": 0.15,
    "三通_直通": 0.10, "三通_支路": 1.30, "闸阀_全开": 0.17,
    "闸阀_半开": 4.5, "闸阀_1_4开": 20.0, "蝶阀_全开": 0.20,
    "蝶阀_半开": 5.0, "止回阀_旋启式": 2.0, "止回阀_球式": 70.0,
    "截止阀_全开": 6.0, "滤水器": 2.5, "孔板流量计": 7.0,
}


# ========== 一、边界层理论 ==========
def _边界_局部雷诺数(U, x, nu): return U * x / nu

def _边界_层流厚度(U, x, nu):
    Re_x = U * x / nu
    return 5.0 * x / math.sqrt(Re_x)

def _边界_层流位移厚度(U, x, nu):
    Re_x = U * x / nu
    return 1.721 * x / math.sqrt(Re_x)

def _边界_层流动量厚度(U, x, nu):
    Re_x = U * x / nu
    return 0.664 * x / math.sqrt(Re_x)

def _边界_层流壁面切应力(rho, U, x, nu):
    Re_x = U * x / nu
    return 0.332 * rho * U * U / math.sqrt(Re_x)

def _边界_层流平板阻力系数(Re_L):
    if Re_L <= 0:
        return float("inf")
    return 1.328 / math.sqrt(Re_L)

def _边界_湍流厚度(U, x, nu):
    Re_x = U * x / nu
    return 0.37 * x / (Re_x ** (1.0 / 5.0))

def _边界_湍流平板阻力系数(Re_L):
    if Re_L <= 0:
        return float("inf")
    return 0.074 / (Re_L ** (1.0 / 5.0))

def _边界_混合平板阻力系数(Re_L):
    if Re_L <= 5e5:
        return 1.328 / math.sqrt(Re_L)
    if Re_L >= 1e7:
        return 0.074 / (Re_L ** (1.0 / 5.0))
    return 0.074 / (Re_L ** (1.0 / 5.0)) - 1742.0 / Re_L

def _边界_形状因子(delta_star, theta):
    if theta <= 0:
        return float("inf")
    return delta_star / theta


# ========== 二、可压缩流动 ==========
def _可压缩_声速(gamma, R_gas, T): return math.sqrt(gamma * R_gas * T)
def _可压缩_马赫数(v, c): return v / c

def _可压缩_等熵温度比(gamma, Ma):
    return 1.0 + 0.5 * (gamma - 1.0) * Ma * Ma

def _可压缩_等熵压强比(gamma, Ma):
    ratio = 1.0 + 0.5 * (gamma - 1.0) * Ma * Ma
    return ratio ** (gamma / (gamma - 1.0))

def _可压缩_等熵密度比(gamma, Ma):
    ratio = 1.0 + 0.5 * (gamma - 1.0) * Ma * Ma
    return ratio ** (1.0 / (gamma - 1.0))

def _可压缩_激波压强比(gamma, Ma1):
    return (2.0 * gamma * Ma1 * Ma1 - (gamma - 1.0)) / (gamma + 1.0)

def _可压缩_激波密度比(gamma, Ma1):
    return ((gamma + 1.0) * Ma1 * Ma1) / (2.0 + (gamma - 1.0) * Ma1 * Ma1)

def _可压缩_激波温度比(gamma, Ma1):
    p_r = (2.0 * gamma * Ma1 * Ma1 - (gamma - 1.0)) / (gamma + 1.0)
    rho_r = ((gamma + 1.0) * Ma1 * Ma1) / (2.0 + (gamma - 1.0) * Ma1 * Ma1)
    return p_r / rho_r

def _可压缩_激波后马赫数(gamma, Ma1):
    numer = Ma1 * Ma1 * (gamma - 1.0) + 2.0
    denom = 2.0 * gamma * Ma1 * Ma1 - (gamma - 1.0)
    return math.sqrt(numer / denom)

def _可压缩_临界压强比(gamma):
    return (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))

def _可压缩_临界温度比(gamma):
    return 2.0 / (gamma + 1.0)

def _可压缩_喷管面积比(gamma, Ma):
    if Ma <= 0:
        return float("inf")
    term = (2.0 / (gamma + 1.0)) * (1.0 + 0.5 * (gamma - 1.0) * Ma * Ma)
    exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
    return (1.0 / Ma) * (term ** exponent)

def _可压缩_普朗特迈耶角(gamma, Ma):
    if Ma <= 1.0:
        return 0.0
    term1 = math.sqrt((gamma + 1.0) / (gamma - 1.0))
    term2 = math.sqrt((gamma - 1.0) / (gamma + 1.0) * (Ma * Ma - 1.0))
    return term1 * math.atan(term2) - math.atan(math.sqrt(Ma * Ma - 1.0))


# ========== 三、明渠水力学 ==========
def _明渠_谢才流速(C, R, S): return C * math.sqrt(R * S)

def _明渠_曼宁流速_SI(n, R, S):
    return (1.0 / n) * (R ** (2.0 / 3.0)) * (S ** 0.5)

def _明渠_曼宁流速_英制(n, R, S):
    return 1.486 / n * (R ** (2.0 / 3.0)) * (S ** 0.5)

def _明渠_矩形水力半径(b, h):
    return b * h / (b + 2.0 * h)

def _明渠_梯形水力半径(b, h, m):
    A = b * h + m * h * h
    P = b + 2.0 * h * math.sqrt(1.0 + m * m)
    return A / P

def _明渠_弗劳德数(v, h, g_val):
    return v / math.sqrt(g_val * h)

def _明渠_流态判断(Fr):
    if abs(Fr - 1.0) < 1e-6:
        return "临界流"
    elif Fr < 1.0:
        return "缓流"
    else:
        return "急流"

def _明渠_临界水深(q, g_val):
    return (q * q / g_val) ** (1.0 / 3.0)

def _明渠_临界流速(h_c, g_val):
    return math.sqrt(g_val * h_c)

def _明渠_水跃共轭水深(y1, Fr1):
    return 0.5 * y1 * (-1.0 + math.sqrt(1.0 + 8.0 * Fr1 * Fr1))

def _明渠_水跃能量损失(y1, y2):
    return (y2 - y1) ** 3 / (4.0 * y1 * y2)

def _明渠_比能(h, v, g_val):
    return h + v * v / (2.0 * g_val)


# ========== 四、泵与风机 ==========
def _泵_扬程(p1, p2, rho, v1, v2, dz, g_val):
    return (p2 - p1) / (rho * g_val) + (v2 * v2 - v1 * v1) / (2.0 * g_val) + dz

def _泵_有效功率(rho, g_val, Q, H):
    return rho * g_val * Q * H

def _泵_轴功率(rho, g_val, Q, H, eta):
    return rho * g_val * Q * H / eta

def _泵_效率(P_w, P_shaft):
    if P_shaft <= 0:
        return 0.0
    return P_w / P_shaft

def _泵_风机全压功率(p_t, Q): return p_t * Q

def _泵_比转速(n_rpm, Q, H):
    if H <= 0:
        return float("inf")
    return n_rpm * math.sqrt(Q) / (H ** 0.75)

def _泵_相似律流量(n1, n2, D1, D2, Q1):
    return Q1 * (n2 / n1) * ((D2 / D1) ** 3)

def _泵_相似律扬程(n1, n2, D1, D2, H1):
    return H1 * ((n2 / n1) ** 2) * ((D2 / D1) ** 2)

def _泵_相似律功率(n1, n2, D1, D2, P1):
    return P1 * ((n2 / n1) ** 3) * ((D2 / D1) ** 5)

def _泵_风机静压升(p_t, rho, v):
    return p_t - 0.5 * rho * v * v


# ========== 五、局部损失与管网 ==========
def _管损_局部水头损失(zeta, v, g_val):
    return zeta * v * v / (2.0 * g_val)

def _管损_当量长度(zeta, D, f):
    if f <= 0:
        return float("inf")
    return zeta * D / f

def _管损_总水头损失(f, L, D, v, sum_zeta, g_val):
    return (f * L / D + sum_zeta) * v * v / (2.0 * g_val)

def _管损_突扩阻力系数(A1, A2):
    return (1.0 - A1 / A2) ** 2

def _管损_突缩阻力系数(A1, A2):
    return 0.5 * (1.0 - A2 / A1)

def _管损_比阻(f, L, D, g_val):
    if D <= 0:
        return float("inf")
    return 8.0 * f * L / (g_val * math.pi * math.pi * (D ** 5))

def _管损_串联比阻(S1, S2): return S1 + S2

def _管损_并联比阻(S1, S2):
    term = 1.0 / math.sqrt(S1) + 1.0 / math.sqrt(S2)
    return 1.0 / (term * term)

def _管损_锐缘入口系数(): return 0.5
def _管损_出口损失系数(): return 1.0
def _管损_阻力系数查询(name_key):
    return K_MINOR.get(name_key, 0.0)


# ========== 注册 ==========
def _register_fluid_exp(builtins: dict) -> None:
    # --- 边界层 ---
    builtins["边界_局部雷诺数"] = _curry3(_边界_局部雷诺数)
    builtins["边界_层流厚度"] = _curry3(_边界_层流厚度)
    builtins["边界_层流位移厚度"] = _curry3(_边界_层流位移厚度)
    builtins["边界_层流动量厚度"] = _curry3(_边界_层流动量厚度)
    builtins["边界_层流壁面切应力"] = _curry4(_边界_层流壁面切应力)
    builtins["边界_层流平板阻力系数"] = _边界_层流平板阻力系数
    builtins["边界_湍流厚度"] = _curry3(_边界_湍流厚度)
    builtins["边界_湍流平板阻力系数"] = _边界_湍流平板阻力系数
    builtins["边界_混合平板阻力系数"] = _边界_混合平板阻力系数
    builtins["边界_形状因子"] = _curry2(_边界_形状因子)

    # --- 可压缩流动 ---
    builtins["可压缩_声速"] = _curry3(_可压缩_声速)
    builtins["可压缩_马赫数"] = _curry2(_可压缩_马赫数)
    builtins["可压缩_等熵温度比"] = _curry2(_可压缩_等熵温度比)
    builtins["可压缩_等熵压强比"] = _curry2(_可压缩_等熵压强比)
    builtins["可压缩_等熵密度比"] = _curry2(_可压缩_等熵密度比)
    builtins["可压缩_激波压强比"] = _curry2(_可压缩_激波压强比)
    builtins["可压缩_激波密度比"] = _curry2(_可压缩_激波密度比)
    builtins["可压缩_激波温度比"] = _curry2(_可压缩_激波温度比)
    builtins["可压缩_激波后马赫数"] = _curry2(_可压缩_激波后马赫数)
    builtins["可压缩_临界压强比"] = _可压缩_临界压强比
    builtins["可压缩_临界温度比"] = _可压缩_临界温度比
    builtins["可压缩_喷管面积比"] = _curry2(_可压缩_喷管面积比)
    builtins["可压缩_普朗特迈耶角"] = _curry2(_可压缩_普朗特迈耶角)

    # --- 明渠水力学 ---
    builtins["明渠_谢才流速"] = _curry3(_明渠_谢才流速)
    builtins["明渠_曼宁流速_SI"] = _curry3(_明渠_曼宁流速_SI)
    builtins["明渠_曼宁流速_英制"] = _curry3(_明渠_曼宁流速_英制)
    builtins["明渠_矩形水力半径"] = _curry2(_明渠_矩形水力半径)
    builtins["明渠_梯形水力半径"] = _curry3(_明渠_梯形水力半径)
    builtins["明渠_弗劳德数"] = _curry3(_明渠_弗劳德数)
    builtins["明渠_流态判断"] = _明渠_流态判断
    builtins["明渠_临界水深"] = _curry2(_明渠_临界水深)
    builtins["明渠_临界流速"] = _curry2(_明渠_临界流速)
    builtins["明渠_水跃共轭水深"] = _curry2(_明渠_水跃共轭水深)
    builtins["明渠_水跃能量损失"] = _curry2(_明渠_水跃能量损失)
    builtins["明渠_比能"] = _curry3(_明渠_比能)

    # --- 泵与风机 ---
    builtins["泵_扬程"] = _curry4(
        lambda p1, p2, rho, v1: _curry3(
            lambda v2, dz, g_val: _泵_扬程(p1, p2, rho, v1, v2, dz, g_val)
        )
    )
    builtins["泵_有效功率"] = _curry4(_泵_有效功率)
    builtins["泵_轴功率"] = _curry5(_泵_轴功率)
    builtins["泵_效率"] = _curry2(_泵_效率)
    builtins["泵_风机全压功率"] = _curry2(_泵_风机全压功率)
    builtins["泵_比转速"] = _curry3(_泵_比转速)
    builtins["泵_相似律流量"] = _curry5(_泵_相似律流量)
    builtins["泵_相似律扬程"] = _curry5(_泵_相似律扬程)
    builtins["泵_相似律功率"] = _curry5(_泵_相似律功率)
    builtins["泵_风机静压升"] = _curry3(_泵_风机静压升)

    # --- 局部损失与管网 ---
    builtins["管损_局部水头损失"] = _curry3(_管损_局部水头损失)
    builtins["管损_当量长度"] = _curry3(_管损_当量长度)
    builtins["管损_总水头损失"] = (lambda f: (lambda L: (lambda D: (lambda v: (lambda sz: (lambda gv: _管损_总水头损失(f, L, D, v, sz, gv)))))))
    builtins["管损_突扩阻力系数"] = _curry2(_管损_突扩阻力系数)
    builtins["管损_突缩阻力系数"] = _curry2(_管损_突缩阻力系数)
    builtins["管损_比阻"] = _curry4(_管损_比阻)
    builtins["管损_串联比阻"] = _curry2(_管损_串联比阻)
    builtins["管损_并联比阻"] = _curry2(_管损_并联比阻)
    builtins["管损_锐缘入口系数"] = _管损_锐缘入口系数
    builtins["管损_出口损失系数"] = _管损_出口损失系数
    builtins["管损_阻力系数查询"] = _管损_阻力系数查询

    # --- 通用物理常量 ---
    builtins["g_标准"] = G_STANDARD
    builtins["gamma_空气"] = GAMMA_AIR
    builtins["gamma_单原子"] = GAMMA_MONO
    builtins["gamma_双原子"] = GAMMA_DI
    builtins["gamma_多原子"] = GAMMA_POLY
    builtins["R_空气气体常数"] = R_AIR

    # --- 曼宁糙率系数 ---
    for name, val in MANNING_N.items():
        builtins[f"糙率_{name}"] = val

    # --- 局部阻力系数 ---
    for name, val in K_MINOR.items():
        builtins[f"K局_{name}"] = val


# ========== 语义符号表 ==========
def _fluid_exp_symtab_names() -> list[str]:
    names: list[str] = []

    for n in ["局部雷诺数", "层流厚度", "层流位移厚度", "层流动量厚度",
              "层流壁面切应力", "层流平板阻力系数", "湍流厚度",
              "湍流平板阻力系数", "混合平板阻力系数", "形状因子"]:
        names.append(f"边界_{n}")

    for n in ["声速", "马赫数", "等熵温度比", "等熵压强比", "等熵密度比",
              "激波压强比", "激波密度比", "激波温度比", "激波后马赫数",
              "临界压强比", "临界温度比", "喷管面积比", "普朗特迈耶角"]:
        names.append(f"可压缩_{n}")

    for n in ["谢才流速", "曼宁流速_SI", "曼宁流速_英制", "矩形水力半径",
              "梯形水力半径", "弗劳德数", "流态判断", "临界水深",
              "临界流速", "水跃共轭水深", "水跃能量损失", "比能"]:
        names.append(f"明渠_{n}")

    for n in ["扬程", "有效功率", "轴功率", "效率", "风机全压功率",
              "比转速", "相似律流量", "相似律扬程", "相似律功率", "风机静压升"]:
        names.append(f"泵_{n}")

    for n in ["局部水头损失", "当量长度", "总水头损失",
              "突扩阻力系数", "突缩阻力系数", "比阻",
              "串联比阻", "并联比阻",
              "锐缘入口系数", "出口损失系数", "阻力系数查询"]:
        names.append(f"管损_{n}")

    for n in ["g_标准", "gamma_空气", "gamma_单原子",
              "gamma_双原子", "gamma_多原子", "R_空气气体常数"]:
        names.append(n)

    for name in MANNING_N:
        names.append(f"糙率_{name}")

    for name in K_MINOR:
        names.append(f"K局_{name}")

    return names
