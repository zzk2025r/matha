"""Matha 机械领域模块：天体力学（Celestial Mechanics）。

基于力学 + 量子力学 + mathlib 数学地基，演化天体力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、万有引力与轨道力学（Gravitation & Orbital Mechanics）
  1) 万有引力：F = Gm₁m₂/r²
  2) 引力势能：U = -Gm₁m₂/r
  3) 引力加速度：g = GM/r²
  4) 第一宇宙速度（环绕速度）：v₁ = √(GM/r)
  5) 第二宇宙速度（逃逸速度）：v₂ = √(2GM/r)
  6) 第三宇宙速度：v₃ = √(2GM/r - 2GM/R_sun)
  7) 轨道周期（圆轨道）：T = 2π√(r³/(GM))
  8) 同步轨道半径：r = (GMT²/(4π²))^(1/3)

二、开普勒定律（Kepler's Laws）
  1) 开普勒第三定律：T² = (4π²/GM)·a³ → T = 2π√(a³/(GM))
  2) 半长轴由周期：a = (GMT²/(4π²))^(1/3)
  3) 椭圆轨道周长（近似）：C ≈ π[3(a+b) - √((3a+b)(a+3b))]
  4) 椭圆面积：A = πab
  5) 偏心率：e = √(1 - b²/a²)
  6) 近地点/远地点距离：r_p = a(1-e), r_a = a(1+e)

三、轨道参数与活力公式（Orbital Parameters & Vis-viva）
  1) 活力公式：v² = GM(2/r - 1/a)
  2) 轨道角动量：L = m√(GMa(1-e²))
  3) 轨道能量：E = -GMm/(2a)
  4) 偏近点角与真近点角关系（开普勒方程）
  5) 拉格朗日点（近似）
  6) 霍曼转移轨道

四、潮汐与引力场（Tides & Gravitational Fields）
  1) 潮汐力（差动力）：F_tidal = 2GMm·Δr/r³
  2) 潮汐隆起高度
  3) 洛希极限：d = R·(2ρ_M/ρ_m)^(1/3)
  4) 引力场强度：g = GM/r²
  5) 引力势：Φ = -GM/r
  6) 多体引力合力

五、相对论修正（Relativistic Corrections）
  1) 史瓦西半径：r_s = 2GM/c²
  2) 水星近日点进动：Δφ = 6πGM/(c²a(1-e²))
  3) 引力时间膨胀：t' = t·√(1 - r_s/r)
  4) 引力红移：z = √(1/(1 - r_s/r)) - 1
  5) 光线偏折角：θ = 4GM/(c²b)（b 为冲击参数）
  6) 轨道速度的相对论修正

设计原则：
  - 所有角度输入/输出均为弧度
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 引力_ / 开普勒_ / 轨道_ / 潮汐_ / 相对论_ 区分子领域
  - 天体物理常量与太阳系数据作为常量注册
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
# 万有引力常数 G = 6.674e-11 N·m²/kg²
G_GRAV = _P.G
# 光速 c = 2.998e8 m/s
C_LIGHT = _P.c
# 天文单位 AU = 1.496e11 m
AU = _P.AU
# 光年 ly = 9.461e15 m
LY = _P.LY
# 秒差距 pc = 3.086e16 m
PC = _P.PC

# 太阳系天体数据
SOLAR_SYSTEM: dict[str, dict[str, float]] = {
    "太阳": {
        "M": 1.989e30,      # 质量 kg
        "R": 6.96e8,         # 半径 m
        "T_rot": 2.19e6,     # 自转周期 s (约25.4天)
    },
    "水星": {
        "M": 3.301e23,
        "R": 2.4397e6,
        "a": 5.791e10,       # 半长轴 m
        "e": 0.2056,         # 偏心率
        "T": 7.6005e6,       # 公转周期 s
    },
    "金星": {
        "M": 4.867e24,
        "R": 6.0518e6,
        "a": 1.0821e11,
        "e": 0.0068,
        "T": 1.9414e7,
    },
    "地球": {
        "M": 5.972e24,
        "R": 6.371e6,
        "a": 1.496e11,
        "e": 0.0167,
        "T": 3.1558e7,
    },
    "火星": {
        "M": 6.417e23,
        "R": 3.3895e6,
        "a": 2.279e11,
        "e": 0.0934,
        "T": 5.935e7,
    },
    "木星": {
        "M": 1.898e27,
        "R": 6.9911e7,
        "a": 7.785e11,
        "e": 0.0489,
        "T": 3.743e8,
    },
    "土星": {
        "M": 5.683e26,
        "R": 5.8232e7,
        "a": 1.434e12,
        "e": 0.0565,
        "T": 9.296e8,
    },
    "月球": {
        "M": 7.342e22,
        "R": 1.7374e6,
        "a": 3.844e8,        # 地月距离
        "e": 0.0549,
        "T": 2.361e6,        # 公转周期
    },
}


# ============================================================
# 一、万有引力与轨道力学（Gravitation & Orbital Mechanics）
# ============================================================

# 万有引力：F = Gm₁m₂/r²
def _引力_万有引力(m1, m2, r): return G_GRAV * m1 * m2 / r ** 2
# 引力势能：U = -Gm₁m₂/r
def _引力_引力势能(m1, m2, r): return -G_GRAV * m1 * m2 / r
# 引力加速度：g = GM/r²
def _引力_引力加速度(M, r): return G_GRAV * M / r ** 2
# 第一宇宙速度（环绕速度）：v₁ = √(GM/r)
def _引力_环绕速度(M, r): return math.sqrt(G_GRAV * M / r)
# 第二宇宙速度（逃逸速度）：v₂ = √(2GM/r)
def _引力_逃逸速度(M, r): return math.sqrt(2 * G_GRAV * M / r)
# 第三宇宙速度：v₃ = √(v_esc_planet² + v_esc_sun²)
def _引力_第三宇宙速度(M_planet, r_planet, M_sun, r_orbit):
    v_esc_planet = math.sqrt(2 * G_GRAV * M_planet / r_planet)
    v_esc_sun = math.sqrt(2 * G_GRAV * M_sun / r_orbit)
    return math.sqrt(v_esc_planet ** 2 + v_esc_sun ** 2)
# 圆轨道周期：T = 2π√(r³/(GM))
def _引力_圆轨道周期(M, r): return 2 * math.pi * math.sqrt(r ** 3 / (G_GRAV * M))
# 同步轨道半径：r = (GMT²/(4π²))^(1/3)
def _引力_同步轨道半径(M, T): return (G_GRAV * M * T ** 2 / (4 * math.pi ** 2)) ** (1.0 / 3)
# 轨道角速度（圆轨道）：ω = √(GM/r³)
def _引力_轨道角速度(M, r): return math.sqrt(G_GRAV * M / r ** 3)


# ============================================================
# 二、开普勒定律（Kepler's Laws）
# ============================================================

# 开普勒第三定律：T = 2π√(a³/(GM))
def _开普勒_周期(a, M): return 2 * math.pi * math.sqrt(a ** 3 / (G_GRAV * M))
# 半长轴由周期：a = (GMT²/(4π²))^(1/3)
def _开普勒_半长轴(M, T): return (G_GRAV * M * T ** 2 / (4 * math.pi ** 2)) ** (1.0 / 3)
# 椭圆面积：A = πab
def _开普勒_椭圆面积(a, b): return math.pi * a * b
# 偏心率（由半长轴和半短轴）：e = √(1 - b²/a²)
def _开普勒_偏心率(a, b): return math.sqrt(1 - (b / a) ** 2) if a > 0 else 0.0
# 近地点距离：r_p = a(1-e)
def _开普勒_近地点(a, e): return a * (1 - e)
# 远地点距离：r_a = a(1+e)
def _开普勒_远地点(a, e): return a * (1 + e)
# 椭圆轨道周长（Ramanujan 近似）：C ≈ π[3(a+b) - √((3a+b)(a+3b))]
def _开普勒_椭圆周长(a, b):
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
# 平均运动：n = 2π/T
def _开普勒_平均运动(T): return 2 * math.pi / T


# ============================================================
# 三、轨道参数与活力公式（Orbital Parameters & Vis-viva）
# ============================================================

# 活力公式：v² = GM(2/r - 1/a)
def _轨道_活力速度(M, r, a): return math.sqrt(G_GRAV * M * (2 / r - 1 / a))
# 轨道角动量：L = m√(GMa(1-e²))
def _轨道_角动量(M, m, a, e): return m * math.sqrt(G_GRAV * M * a * (1 - e ** 2))
# 轨道总能量：E = -GMm/(2a)
def _轨道_总能量(M, m, a): return -G_GRAV * M * m / (2 * a)
# 近地点速度：v_p = √(GM(1+e)/(a(1-e)))
def _轨道_近地点速度(M, a, e): return math.sqrt(G_GRAV * M * (1 + e) / (a * (1 - e)))
# 远地点速度：v_a = √(GM(1-e)/(a(1+e)))
def _轨道_远地点速度(M, a, e): return math.sqrt(G_GRAV * M * (1 - e) / (a * (1 + e)))
# 霍曼转移轨道速度增量
def _轨道_霍曼转移(M, r1, r2):
    """从圆轨道 r1 转移到圆轨道 r2 的霍曼转移速度增量。"""
    a_transfer = (r1 + r2) / 2
    v1 = math.sqrt(G_GRAV * M / r1)
    v2 = math.sqrt(G_GRAV * M / r2)
    v_transfer_peri = math.sqrt(G_GRAV * M * (2 / r1 - 1 / a_transfer))
    v_transfer_apo = math.sqrt(G_GRAV * M * (2 / r2 - 1 / a_transfer))
    delta_v1 = abs(v_transfer_peri - v1)
    delta_v2 = abs(v2 - v_transfer_apo)
    return delta_v1 + delta_v2
# 霍曼转移时间：t = π√(a_transfer³/(GM))
def _轨道_霍曼转移时间(M, r1, r2):
    a_transfer = (r1 + r2) / 2
    return math.pi * math.sqrt(a_transfer ** 3 / (G_GRAV * M))
# 球面引力势逃逸能量
def _轨道_逃逸能量(M, m, r):
    """将质量 m 从 r 处逃逸到无穷远所需能量。"""
    return G_GRAV * M * m / r


# ============================================================
# 四、潮汐与引力场（Tides & Gravitational Fields）
# ============================================================

# 潮汐力（差动力近似）：F_tidal = 2GMm·Δr/r³
def _潮汐_潮汐力(M, m, dr, r): return 2 * G_GRAV * M * m * dr / r ** 3
# 潮汐加速度：a_tidal = 2GM·Δr/r³
def _潮汐_潮汐加速度(M, dr, r): return 2 * G_GRAV * M * dr / r ** 3
# 洛希极限（刚体）：d = R·(2ρ_M/ρ_m)^(1/3)
def _潮汐_洛希极限刚体(R, rho_M, rho_m): return R * (2 * rho_M / rho_m) ** (1.0 / 3)
# 洛希极限（流体）：d = 2.44R·(ρ_M/ρ_m)^(1/3)
def _潮汐_洛希极限流体(R, rho_M, rho_m): return 2.44 * R * (rho_M / rho_m) ** (1.0 / 3)
# 引力势：Φ = -GM/r
def _潮汐_引力势(M, r): return -G_GRAV * M / r
# 引力场强度：g = GM/r²
def _潮汐_引力场强度(M, r): return G_GRAV * M / r ** 2


# ============================================================
# 五、相对论修正（Relativistic Corrections）
# ============================================================

# 史瓦西半径：r_s = 2GM/c²
def _相对论_史瓦西半径(M): return 2 * G_GRAV * M / C_LIGHT ** 2
# 水星近日点进动（每圈弧度）：Δφ = 6πGM/(c²a(1-e²))
def _相对论_近日点进动(M, a, e): return 6 * math.pi * G_GRAV * M / (C_LIGHT ** 2 * a * (1 - e ** 2))
# 引力时间膨胀：t' = t·√(1 - r_s/r)
def _相对论_时间膨胀(t, M, r):
    r_s = 2 * G_GRAV * M / C_LIGHT ** 2
    return t * math.sqrt(max(0, 1 - r_s / r))
# 引力红移：z = 1/√(1 - r_s/r) - 1
def _相对论_引力红移(M, r):
    r_s = 2 * G_GRAV * M / C_LIGHT ** 2
    return 1.0 / math.sqrt(max(1e-30, 1 - r_s / r)) - 1
# 光线偏折角：θ = 4GM/(c²b)
def _相对论_光线偏折(M, b): return 4 * G_GRAV * M / (C_LIGHT ** 2 * b)
# 黑洞温度（霍金辐射）：T = ℏc³/(8πGMk_B)
def _相对论_黑洞温度(M):
    hbar = 1.054571817e-34
    k_B = 1.380649e-23
    return hbar * C_LIGHT ** 3 / (8 * math.pi * G_GRAV * M * k_B)


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_celestial(builtins: dict) -> None:
    """将天体力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（quantum 之后）。
    """
    # --- 万有引力与轨道力学 ---
    builtins["引力_万有引力"] = _curry3(_引力_万有引力)            # 引力_万有引力(m1)(m2)(r)
    builtins["引力_引力势能"] = _curry3(_引力_引力势能)            # 引力_引力势能(m1)(m2)(r)
    builtins["引力_引力加速度"] = _curry2(_引力_引力加速度)        # 引力_引力加速度(M)(r)
    builtins["引力_环绕速度"] = _curry2(_引力_环绕速度)            # 引力_环绕速度(M)(r)
    builtins["引力_逃逸速度"] = _curry2(_引力_逃逸速度)            # 引力_逃逸速度(M)(r)
    builtins["引力_第三宇宙速度"] = _curry4(_引力_第三宇宙速度)    # 引力_第三宇宙速度(Mp)(rp)(Ms)(ro)
    builtins["引力_圆轨道周期"] = _curry2(_引力_圆轨道周期)        # 引力_圆轨道周期(M)(r)
    builtins["引力_同步轨道半径"] = _curry2(_引力_同步轨道半径)    # 引力_同步轨道半径(M)(T)
    builtins["引力_轨道角速度"] = _curry2(_引力_轨道角速度)        # 引力_轨道角速度(M)(r)

    # --- 开普勒定律 ---
    builtins["开普勒_周期"] = _curry2(_开普勒_周期)                # 开普勒_周期(a)(M)
    builtins["开普勒_半长轴"] = _curry2(_开普勒_半长轴)            # 开普勒_半长轴(M)(T)
    builtins["开普勒_椭圆面积"] = _curry2(_开普勒_椭圆面积)        # 开普勒_椭圆面积(a)(b)
    builtins["开普勒_偏心率"] = _curry2(_开普勒_偏心率)            # 开普勒_偏心率(a)(b)
    builtins["开普勒_近地点"] = _curry2(_开普勒_近地点)            # 开普勒_近地点(a)(e)
    builtins["开普勒_远地点"] = _curry2(_开普勒_远地点)            # 开普勒_远地点(a)(e)
    builtins["开普勒_椭圆周长"] = _curry2(_开普勒_椭圆周长)        # 开普勒_椭圆周长(a)(b)
    builtins["开普勒_平均运动"] = _开普勒_平均运动                  # 开普勒_平均运动(T)

    # --- 轨道参数与活力公式 ---
    builtins["轨道_活力速度"] = _curry3(_轨道_活力速度)            # 轨道_活力速度(M)(r)(a)
    builtins["轨道_角动量"] = _curry4(_轨道_角动量)                # 轨道_角动量(M)(m)(a)(e)
    builtins["轨道_总能量"] = _curry3(_轨道_总能量)                # 轨道_总能量(M)(m)(a)
    builtins["轨道_近地点速度"] = _curry3(_轨道_近地点速度)        # 轨道_近地点速度(M)(a)(e)
    builtins["轨道_远地点速度"] = _curry3(_轨道_远地点速度)        # 轨道_远地点速度(M)(a)(e)
    builtins["轨道_霍曼转移"] = _curry3(_轨道_霍曼转移)            # 轨道_霍曼转移(M)(r1)(r2)
    builtins["轨道_霍曼转移时间"] = _curry3(_轨道_霍曼转移时间)    # 轨道_霍曼转移时间(M)(r1)(r2)
    builtins["轨道_逃逸能量"] = _curry3(_轨道_逃逸能量)            # 轨道_逃逸能量(M)(m)(r)

    # --- 潮汐与引力场 ---
    builtins["潮汐_潮汐力"] = _curry4(_潮汐_潮汐力)                # 潮汐_潮汐力(M)(m)(Δr)(r)
    builtins["潮汐_潮汐加速度"] = _curry3(_潮汐_潮汐加速度)        # 潮汐_潮汐加速度(M)(Δr)(r)
    builtins["潮汐_洛希极限刚体"] = _curry3(_潮汐_洛希极限刚体)    # 潮汐_洛希极限刚体(R)(ρM)(ρm)
    builtins["潮汐_洛希极限流体"] = _curry3(_潮汐_洛希极限流体)    # 潮汐_洛希极限流体(R)(ρM)(ρm)
    builtins["潮汐_引力势"] = _curry2(_潮汐_引力势)                # 潮汐_引力势(M)(r)
    builtins["潮汐_引力场强度"] = _curry2(_潮汐_引力场强度)        # 潮汐_引力场强度(M)(r)

    # --- 相对论修正 ---
    builtins["相对论_史瓦西半径"] = _相对论_史瓦西半径              # 相对论_史瓦西半径(M)
    builtins["相对论_近日点进动"] = _curry3(_相对论_近日点进动)    # 相对论_近日点进动(M)(a)(e)
    builtins["相对论_时间膨胀"] = _curry3(_相对论_时间膨胀)        # 相对论_时间膨胀(t)(M)(r)
    builtins["相对论_引力红移"] = _curry2(_相对论_引力红移)        # 相对论_引力红移(M)(r)
    builtins["相对论_光线偏折"] = _curry2(_相对论_光线偏折)        # 相对论_光线偏折(M)(b)
    builtins["相对论_黑洞温度"] = _相对论_黑洞温度                  # 相对论_黑洞温度(M)

    # --- 物理常量 ---
    builtins["G_引力常数"] = G_GRAV
    builtins["c_光速"] = C_LIGHT
    builtins["AU_天文单位"] = AU
    builtins["ly_光年"] = LY
    builtins["pc_秒差距"] = PC

    # --- 太阳系天体数据 ---
    for name, data in SOLAR_SYSTEM.items():
        for key, val in data.items():
            builtins[f"天体_{name}_{key}"] = val


def _celestial_symtab_names() -> list[str]:
    """返回天体力学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 万有引力
    for n in ["万有引力", "引力势能", "引力加速度", "环绕速度",
              "逃逸速度", "第三宇宙速度", "圆轨道周期",
              "同步轨道半径", "轨道角速度"]:
        names.append(f"引力_{n}")
    # 开普勒定律
    for n in ["周期", "半长轴", "椭圆面积", "偏心率",
              "近地点", "远地点", "椭圆周长", "平均运动"]:
        names.append(f"开普勒_{n}")
    # 轨道参数
    for n in ["活力速度", "角动量", "总能量", "近地点速度",
              "远地点速度", "霍曼转移", "霍曼转移时间", "逃逸能量"]:
        names.append(f"轨道_{n}")
    # 潮汐与引力场
    for n in ["潮汐力", "潮汐加速度", "洛希极限刚体",
              "洛希极限流体", "引力势", "引力场强度"]:
        names.append(f"潮汐_{n}")
    # 相对论修正
    for n in ["史瓦西半径", "近日点进动", "时间膨胀",
              "引力红移", "光线偏折", "黑洞温度"]:
        names.append(f"相对论_{n}")
    # 物理常量
    for n in ["G_引力常数", "c_光速", "AU_天文单位", "ly_光年", "pc_秒差距"]:
        names.append(n)
    # 太阳系数据
    for name, data in SOLAR_SYSTEM.items():
        for key in data:
            names.append(f"天体_{name}_{key}")
    return names
