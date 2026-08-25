"""Matha 机械领域模块：热力学（Thermodynamics）。

基于流体力学 + 动力学 + mathlib 数学地基，演化热力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、气体状态方程（Gas Laws）
  1) 理想气体状态方程：pV = nRT = (m/M)RT
  2) 玻意耳定律（等温）：p1V1 = p2V2
  3) 查理定律（等压）：V1/T1 = V2/T2
  4) 盖-吕萨克定律（等容）：p1/T1 = p2/T2
  5) 混合气体分压（道尔顿）：p_total = Σp_i
  6) 摩尔数 / 密度由状态方程反算

二、热力学过程（Thermodynamic Processes）
  1) 等温过程做功：W = nRT ln(V2/V1)
  2) 等压过程做功：W = pΔV
  3) 等容过程：W = 0
  4) 绝热过程：pV^γ = const；绝热做功 W = (p1V1 - p2V2)/(γ-1)
  5) 多方过程：pV^n = const
  6) 热力学第一定律：ΔU = Q - W（或 Q = ΔU + W）

三、热传递（Heat Transfer）
  1) 热传导（傅里叶定律）：Q/t = kA(T2-T1)/d
  2) 热对流（牛顿冷却定律）：Q/t = hA(T_s - T_f)
  3) 热辐射（斯特藩-玻尔兹曼）：Q/t = σεA(T⁴)
  4) 热阻：R = d/(kA)
  5) 传热速率（串联热阻）

四、热机与效率（Heat Engines）
  1) 卡诺效率：η = 1 - T_c/T_h
  2) 奥托循环效率：η = 1 - 1/r^(γ-1)（r 为压缩比）
  3) 热机效率：η = W/Q_h = (Q_h - Q_c)/Q_h
  4) 制冷系数：COP = Q_c/W = T_c/(T_h - T_c)
  5) 热泵系数：COP_hp = Q_h/W = T_h/(T_h - T_c)

五、相变与热物性（Phase Change & Properties）
  1) 显热：Q = mcΔT
  2) 潜热：Q = mL（L 为熔化热/汽化热）
  3) 线膨胀：ΔL = αL₀ΔT
  4) 体膨胀：ΔV = βV₀ΔT
  5) 热容：C = mc（热容）；比热容比值 γ = c_p/c_v
  6) 理想气体内能：U = nC_v T = (f/2)nRT（f 为自由度）

设计原则：
  - 所有温度输入/输出均为开尔文 K（SI 标准）
  - 摄氏↔开尔文转换函数提供
  - 多参函数一律 _curry2/_curry3/_curry4/_curry5 封装
  - 前缀 热_ / 过程_ / 传热_ / 热机_ / 相变_ 区分子领域
  - 常用气体比热/热导率作为常量注册
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
# 物理常量
# ============================================================

# 普适气体常数 R = 8.314 J/(mol·K)
R_GAS = 8.314462618
# 斯特藩-玻尔兹曼常数 σ = 5.67e-8 W/(m²·K⁴)
SIGMA_SB = 5.670374419e-8
# 绝对零度 0K = -273.15°C
T_ZERO_C = 273.15


# ============================================================
# 一、气体状态方程（Gas Laws）
# ============================================================

# 摄氏→开尔文
def _热_c2k(T_C): return T_C + T_ZERO_C
# 开尔文→摄氏
def _热_k2c(T_K): return T_K - T_ZERO_C

# 理想气体状态方程：pV = nRT → p = nRT/V
def _热_气压(n, T, V): return n * R_GAS * T / V              # p = nRT/V  Pa
# 理想气体状态方程 → V = nRT/p
def _热_气体体积(n, T, p): return n * R_GAS * T / p           # V = nRT/p  m³
# 理想气体状态方程 → n = pV/(RT)
def _热_摩尔数(p, V, T): return p * V / (R_GAS * T)          # n  mol
# 由质量求摩尔数：n = m/M
def _热_质量转摩尔(m, M): return m / M                         # n = m/M

# 玻意耳定律（等温）：p1V1 = p2V2 → p2 = p1V1/V2
def _热_玻意耳压强(p1, V1, V2): return p1 * V1 / V2
# 查理定律（等压）：V1/T1 = V2/T2 → V2 = V1*T2/T1
def _热_查理体积(V1, T1, T2): return V1 * T2 / T1
# 盖-吕萨克定律（等容）：p1/T1 = p2/T2 → p2 = p1*T2/T1
def _热_盖吕萨克压强(p1, T1, T2): return p1 * T2 / T1

# 道尔顿分压定律：p_total = Σp_i（列表求和）
def _热_道尔顿分压(p_list): return sum(p_list) if isinstance(p_list, list) else p_list


# ============================================================
# 二、热力学过程（Thermodynamic Processes）
# ============================================================

# 等温过程做功：W = nRT ln(V2/V1)
def _过程_等温功(n, T, V1, V2): return n * R_GAS * T * math.log(V2 / V1)
# 等压过程做功：W = p(V2 - V1) = pΔV
def _过程_等压功(p, V1, V2): return p * (V2 - V1)
# 等容过程做功 = 0（常量函数，接受任意参数返回0）
def _过程_等容功(*_): return 0.0
# 绝热过程做功：W = (p1V1 - p2V2)/(γ-1)
def _过程_绝热功(p1, V1, p2, V2, gamma): return (p1 * V1 - p2 * V2) / (gamma - 1)
# 绝热过程关系：p1*V1^γ = p2*V2^γ → p2 = p1*(V1/V2)^γ
def _过程_绝热压强(p1, V1, V2, gamma): return p1 * (V1 / V2) ** gamma
# 绝热过程关系：T1*V1^(γ-1) = T2*V2^(γ-1) → T2 = T1*(V1/V2)^(γ-1)
def _过程_绝热温度(T1, V1, V2, gamma): return T1 * (V1 / V2) ** (gamma - 1)

# 热力学第一定律：ΔU = Q - W（Q 为吸热，W 为对外做功）
def _过程_第一定律(Q, W): return Q - W                        # ΔU = Q - W  J
# 内能变化（理想气体）：ΔU = nC_vΔT
def _过程_内能变化(n, Cv, dT): return n * Cv * dT              # ΔU = nCvΔT  J


# ============================================================
# 三、热传递（Heat Transfer）
# ============================================================

# 热传导（傅里叶定律）：Q/t = kA(T2-T1)/d → 传热速率
def _传热_热传导(k, A, T2, T1, d): return k * A * (T2 - T1) / d  # P = kAΔT/d  W
# 热对流（牛顿冷却定律）：Q/t = hA(T_s - T_f)
def _传热_热对流(h, A, T_s, T_f): return h * A * (T_s - T_f)   # P = hAΔT  W
# 热辐射（斯特藩-玻尔兹曼）：P = σεA(T⁴)
#   T_hot, T_cold 均为开尔文；净辐射 = σεA(T_hot⁴ - T_cold⁴)
def _传热_热辐射(epsilon, A, T_hot, T_cold):
    return SIGMA_SB * epsilon * A * (T_hot**4 - T_cold**4)
# 热阻：R = d/(kA)
def _传热_热阻(d, k, A): return d / (k * A)                    # R  K/W
# 传热速率（串联热阻）：P = ΔT / R_total
def _传热_串联传热(dT, R_list):
    R_total = sum(R_list) if isinstance(R_list, list) else R_list
    return dT / R_total
# 热阻串联：R_total = ΣR_i
def _传热_串联热阻(R_list):
    return sum(R_list) if isinstance(R_list, list) else R_list
# 热阻并联：1/R_total = Σ(1/R_i)
def _传热_并联热阻(R_list):
    if isinstance(R_list, list):
        inv_sum = sum(1.0 / r for r in R_list)
        return 1.0 / inv_sum
    return R_list


# ============================================================
# 四、热机与效率（Heat Engines）
# ============================================================

# 卡诺效率：η = 1 - T_c/T_h
def _热机_卡诺效率(T_h, T_c): return 1 - T_c / T_h            # η（无量纲）
# 奥托循环效率：η = 1 - 1/r^(γ-1)
def _热机_奥托效率(r, gamma): return 1 - 1 / r ** (gamma - 1)
# 热机效率（一般）：η = (Q_h - Q_c)/Q_h = W/Q_h
def _热机_效率(Q_h, Q_c): return (Q_h - Q_c) / Q_h            # η
# 制冷系数：COP_ref = Q_c/W = T_c/(T_h - T_c)
def _热机_制冷系数(T_c, T_h): return T_c / (T_h - T_c)
# 热泵系数：COP_hp = Q_h/W = T_h/(T_h - T_c)
def _热机_热泵系数(T_h, T_c): return T_h / (T_h - T_c)
# 卡诺循环净功：W = Q_h - Q_c = η * Q_h
def _热机_卡诺功(Q_h, T_h, T_c): return _热机_卡诺效率(T_h, T_c) * Q_h


# ============================================================
# 五、相变与热物性（Phase Change & Properties）
# ============================================================

# 显热：Q = mcΔT
def _相变_显热(m, c, dT): return m * c * dT                   # Q = mcΔT  J
# 潜热：Q = mL
def _相变_潜热(m, L): return m * L                             # Q = mL  J
# 线膨胀：ΔL = αL₀ΔT
def _相变_线膨胀(alpha, L0, dT): return alpha * L0 * dT       # ΔL  m
# 体膨胀：ΔV = βV₀ΔT
def _相变_体膨胀(beta, V0, dT): return beta * V0 * dT         # ΔV  m³
# 热容：C = mc
def _相变_热容(m, c): return m * c                             # C  J/K
# 比热容比：γ = c_p/c_v
def _相变_比热容比(cp, cv): return cp / cv                     # γ
# 理想气体内能：U = (f/2)nRT（f 为自由度）
def _相变_理想气体内能(f, n, T): return f / 2 * n * R_GAS * T  # U  J
# 迈耶关系：c_p - c_v = R（摩尔热容）
def _相变_迈耶关系(cp, cv): return cp - cv                     # 应等于 R


# ============================================================
# 常用热物性数据库（标准值，SI 单位）
# ============================================================

# 比热容 c (J/(kg·K)) — 常压 20°C
SPECIFIC_HEATS: dict[str, float] = {
    "水": 4186.0,
    "冰": 2090.0,
    "水蒸气": 2010.0,
    "铝": 900.0,
    "铜": 385.0,
    "铁": 450.0,
    "空气_定压": 1005.0,       # c_p
    "空气_定容": 718.0,        # c_v
}

# 热导率 k (W/(m·K)) — 常温
THERMAL_CONDUCTIVITIES: dict[str, float] = {
    "铜": 401.0,
    "铝": 237.0,
    "铁": 80.0,
    "水": 0.598,
    "空气": 0.026,
    "玻璃": 1.05,
    "木材": 0.15,
    "泡沫塑料": 0.035,
    "混凝土": 1.74,
}

# 潜热 L (J/kg) — 标准大气压
LATENT_HEATS: dict[str, float] = {
    "水_熔化": 334000.0,       # 冰→水
    "水_汽化": 2260000.0,     # 水→蒸汽
    "铝_熔化": 397000.0,
    "铁_熔化": 247000.0,
    "铜_熔化": 206000.0,
}

# 线膨胀系数 α (1/K) — 常温
THERMAL_EXPANSIONS: dict[str, float] = {
    "铝": 2.3e-5,
    "铜": 1.7e-5,
    "铁": 1.2e-5,
    "钢": 1.3e-5,
    "玻璃": 9.0e-6,
    "混凝土": 1.2e-5,
}

# 摩尔质量 M (kg/mol)
MOLAR_MASSES: dict[str, float] = {
    "空气": 0.02897,
    "氧气": 0.032,
    "氮气": 0.028,
    "氢气": 0.002,
    "二氧化碳": 0.044,
    "水蒸气": 0.018,
}

# 常用 γ（比热容比，理想气体）
GAMMA_VALUES: dict[str, float] = {
    "单原子": 5.0 / 3,       # He, Ar 等
    "双原子": 1.4,           # 空气, O2, N2
    "多原子": 4.0 / 3,       # CO2, CH4 等
}


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_thermo(builtins: dict) -> None:
    """将热力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（fluid 之后）。
    命名规则：
      - 气体状态：前缀 热_
      - 热力学过程：前缀 过程_
      - 热传递：前缀 传热_
      - 热机效率：前缀 热机_
      - 相变热物性：前缀 相变_
    """
    # --- 气体状态方程 ---
    builtins["热_摄氏转开尔文"] = _热_c2k
    builtins["热_开尔文转摄氏"] = _热_k2c
    builtins["热_气压"] = _curry3(_热_气压)                    # 热_气压(n)(T)(V)
    builtins["热_气体体积"] = _curry3(_热_气体体积)            # 热_气体体积(n)(T)(p)
    builtins["热_摩尔数"] = _curry3(_热_摩尔数)                # 热_摩尔数(p)(V)(T)
    builtins["热_质量转摩尔"] = _curry2(_热_质量转摩尔)        # 热_质量转摩尔(m)(M)
    builtins["热_玻意耳压强"] = _curry3(_热_玻意耳压强)        # 热_玻意耳压强(p1)(V1)(V2)
    builtins["热_查理体积"] = _curry3(_热_查理体积)            # 热_查理体积(V1)(T1)(T2)
    builtins["热_盖吕萨克压强"] = _curry3(_热_盖吕萨克压强)    # 热_盖吕萨克压强(p1)(T1)(T2)
    builtins["热_道尔顿分压"] = _热_道尔顿分压                 # 热_道尔顿分压(列表)

    # --- 热力学过程 ---
    builtins["过程_等温功"] = _curry4(_过程_等温功)            # 过程_等温功(n)(T)(V1)(V2)
    builtins["过程_等压功"] = _curry3(_过程_等压功)            # 过程_等压功(p)(V1)(V2)
    builtins["过程_等容功"] = lambda *_: 0.0                  # 过程_等容功 → 0
    builtins["过程_绝热功"] = _curry5(_过程_绝热功)            # 过程_绝热功(p1)(V1)(p2)(V2)(γ)
    builtins["过程_绝热压强"] = _curry4(_过程_绝热压强)        # 过程_绝热压强(p1)(V1)(V2)(γ)
    builtins["过程_绝热温度"] = _curry4(_过程_绝热温度)        # 过程_绝热温度(T1)(V1)(V2)(γ)
    builtins["过程_第一定律"] = _curry2(_过程_第一定律)        # 过程_第一定律(Q)(W)
    builtins["过程_内能变化"] = _curry3(_过程_内能变化)        # 过程_内能变化(n)(Cv)(ΔT)

    # --- 热传递 ---
    builtins["传热_热传导"] = _curry5(_传热_热传导)            # 传热_热传导(k)(A)(T2)(T1)(d)
    builtins["传热_热对流"] = _curry4(_传热_热对流)            # 传热_热对流(h)(A)(Ts)(Tf)
    # 传热_热辐射 是 4 参，用 curry4
    builtins["传热_热辐射"] = _curry4(_传热_热辐射)            # 传热_热辐射(ε)(A)(T热)(T冷)
    builtins["传热_热阻"] = _curry3(_传热_热阻)                # 传热_热阻(d)(k)(A)
    builtins["传热_串联传热"] = _curry2(_传热_串联传热)        # 传热_串联传热(ΔT)(R列表)
    builtins["传热_串联热阻"] = _传热_串联热阻                  # 传热_串联热阻(R列表)
    builtins["传热_并联热阻"] = _传热_并联热阻                  # 传热_并联热阻(R列表)

    # --- 热机效率 ---
    builtins["热机_卡诺效率"] = _curry2(_热机_卡诺效率)        # 热机_卡诺效率(Th)(Tc)
    builtins["热机_奥托效率"] = _curry2(_热机_奥托效率)        # 热机_奥托效率(r)(γ)
    builtins["热机_效率"] = _curry2(_热机_效率)                # 热机_效率(Qh)(Qc)
    builtins["热机_制冷系数"] = _curry2(_热机_制冷系数)        # 热机_制冷系数(Tc)(Th)
    builtins["热机_热泵系数"] = _curry2(_热机_热泵系数)        # 热机_热泵系数(Th)(Tc)
    builtins["热机_卡诺功"] = _curry3(_热机_卡诺功)            # 热机_卡诺功(Qh)(Th)(Tc)

    # --- 相变与热物性 ---
    builtins["相变_显热"] = _curry3(_相变_显热)                # 相变_显热(m)(c)(ΔT)
    builtins["相变_潜热"] = _curry2(_相变_潜热)                # 相变_潜热(m)(L)
    builtins["相变_线膨胀"] = _curry3(_相变_线膨胀)            # 相变_线膨胀(α)(L0)(ΔT)
    builtins["相变_体膨胀"] = _curry3(_相变_体膨胀)            # 相变_体膨胀(β)(V0)(ΔT)
    builtins["相变_热容"] = _curry2(_相变_热容)                # 相变_热容(m)(c)
    builtins["相变_比热容比"] = _curry2(_相变_比热容比)        # 相变_比热容比(cp)(cv)
    builtins["相变_理想气体内能"] = _curry3(_相变_理想气体内能)  # 相变_理想气体内能(f)(n)(T)
    builtins["相变_迈耶关系"] = _curry2(_相变_迈耶关系)        # 相变_迈耶关系(cp)(cv)

    # --- 物理常量 ---
    builtins["R_气体常数"] = R_GAS
    builtins["σ_斯特藩玻尔兹曼"] = SIGMA_SB
    builtins["T_零度"] = T_ZERO_C

    # --- 比热容常量 ---
    for name, val in SPECIFIC_HEATS.items():
        builtins[f"比热_{name}"] = val

    # --- 热导率常量 ---
    for name, val in THERMAL_CONDUCTIVITIES.items():
        builtins[f"热导率_{name}"] = val

    # --- 潜热常量 ---
    for name, val in LATENT_HEATS.items():
        builtins[f"潜热_{name}"] = val

    # --- 线膨胀系数常量 ---
    for name, val in THERMAL_EXPANSIONS.items():
        builtins[f"线膨胀_{name}"] = val

    # --- 摩尔质量常量 ---
    for name, val in MOLAR_MASSES.items():
        builtins[f"摩尔质量_{name}"] = val

    # --- γ 值常量 ---
    for name, val in GAMMA_VALUES.items():
        builtins[f"γ_{name}"] = val


def _thermo_symtab_names() -> list[str]:
    """返回热力学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 气体状态
    for n in ["摄氏转开尔文", "开尔文转摄氏", "气压", "气体体积", "摩尔数",
              "质量转摩尔", "玻意耳压强", "查理体积", "盖吕萨克压强", "道尔顿分压"]:
        names.append(f"热_{n}")
    # 热力学过程
    for n in ["等温功", "等压功", "等容功", "绝热功", "绝热压强", "绝热温度",
              "第一定律", "内能变化"]:
        names.append(f"过程_{n}")
    # 热传递
    for n in ["热传导", "热对流", "热辐射", "热阻", "串联传热", "串联热阻", "并联热阻"]:
        names.append(f"传热_{n}")
    # 热机
    for n in ["卡诺效率", "奥托效率", "效率", "制冷系数", "热泵系数", "卡诺功"]:
        names.append(f"热机_{n}")
    # 相变
    for n in ["显热", "潜热", "线膨胀", "体膨胀", "热容", "比热容比",
              "理想气体内能", "迈耶关系"]:
        names.append(f"相变_{n}")
    # 物理常量
    for n in ["R_气体常数", "σ_斯特藩玻尔兹曼", "T_零度"]:
        names.append(n)
    # 数据库常量
    for name in SPECIFIC_HEATS:
        names.append(f"比热_{name}")
    for name in THERMAL_CONDUCTIVITIES:
        names.append(f"热导率_{name}")
    for name in LATENT_HEATS:
        names.append(f"潜热_{name}")
    for name in THERMAL_EXPANSIONS:
        names.append(f"线膨胀_{name}")
    for name in MOLAR_MASSES:
        names.append(f"摩尔质量_{name}")
    for name in GAMMA_VALUES:
        names.append(f"γ_{name}")
    return names
