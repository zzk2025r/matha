"""Matha 领域扩展模块：机械设计（Mechanical Design / Machine Design）。

基于 Matha 数学基础 + mechanics.py（运动学/材料力学）+ dynamics.py（动力学）+ structural.py（结构力学），
演化机械设计通用零部件设计与验算功能。所有函数以普通 Python callable 注册到解释器 builtins。

六大子领域：

一、轴与连接件（Shaft & Connection）- 前缀 轴设_
  1) 轴的扭转强度校核 τ = T/(Wt) = 16T/(πd³)
  2) 轴的弯曲强度校核 σ = M/W = 32M/(πd³)
  3) 弯扭组合当量弯矩 Me = √(M² + (αT)²)
  4) 按扭转初估轴径 d ≥ ∛(9.55×10⁶P/(0.2·τ·n)) 简化
  5) 平键挤压强度校核 σp = 4T/(d·h·L)
  6) 平键剪切强度校核 τ = 2T/(d·b·L)
  7) 花键挤压强度简化 σp = 8T/(z·h·L·Dm)
  8) 过盈配合传递扭矩简化（摩擦式）T = π·p·d·L·μ·d/2

二、滚动轴承（Rolling Bearing）- 前缀 轴承_
  1) 基本额定寿命 L10 = (C/P)^ε × 10⁶ 转（ε=3 球/10/3 滚子）
  2) 寿命小时值 Lh = (10⁶/60n)·(C/P)^ε
  3) 当量动载荷 P = X·Fr + Y·Fa（X,Y 为系数简化默认 1）
  4) 静载荷额定寿命 C0 校核 P0 ≤ C0/S0
  5) 角接触轴承附加轴向力简化 Fa = e·Fr
  6) 寿命系数 fn = (33.3/n)^(1/ε) 或 (1000060/n)^(1/ε)

三、齿轮传动（Gear Drive）- 前缀 齿轮_
  1) 直齿圆柱齿轮接触疲劳 σH = ZE·ZH·√(2KT1·(u+1)/(φd·b·d1²·u))
  2) 直齿圆柱齿轮弯曲疲劳 σF = 2KT1/(φd·b·m²·z1)·YFa·YSa
  3) 齿轮中心距 a = m(z1+z2)/2
  4) 分度圆直径 d = m·z
  5) 齿宽 b = φd·d1
  6) 传动比 i = n1/n2 = z2/z1
  7) 齿轮圆周速度 v = π·d1·n1/(60×1000) m/s
  8) 许用接触应力 σHP = σHlim·Zn/S_Hmin（简化）

四、弹簧设计（Spring Design）- 前缀 弹簧_
  1) 圆柱螺旋压缩弹簧刚度 k = G·d⁴/(8·D³·n)
  2) 弹簧最大切应力 τmax = 8·K·D·Fmax/(π·d³)
  3) 曲度系数 K = (4C-1)/(4C-4) + 0.615/C（C=D/d）
  4) 弹簧变形量 λ = 8·F·D³·n/(G·d⁴)
  5) 弹簧总圈数 n1 = n + 2（两端圈各一圈，Y 型端部）
  6) 弹簧自由高度 H0 = n·p + 1.5·d（Y 型端部）
  7) 螺旋角 α = arctan(p/(π·D))

五、紧固件与连接件（Fasteners）- 前缀 联接_
  1) 受拉螺栓强度校核 σ = 1.3·F'/ (π·d1²/4)（预紧+静载）
  2) 受剪螺栓强度校核 τ = F/(m·π·d0²/4)
  3) 螺栓挤压强度校核 σp = F/(d0·Σt)
  4) 残余预紧力 F'' = χ·F（变载 χ=0.6~1.0，静载 χ=0.2~0.6）
  5) 螺栓总拉力 F' = F + F''（受轴向变载）
  6) 键类型查用：平键规格 b×h 按轴径 d
  7) 销的剪切强度 τ = 4F/(π·d²·z)

六、公差配合与可靠性（Tolerance & Reliability）- 前缀 公差_
  1) IT 标准公差值（IT01-IT18 简化公式 i = 0.45·∛D + 0.001·D，按公差等级系数）
  2) 基本偏差查询（简化：轴 h/H 基孔制/基轴制常用值）
  3) 配合间隙/过盈 Xmin/Ymax（间隙/过渡/过盈配合）
  4) 尺寸链极值法封闭环：封闭环 = Σ(增环) - Σ(减环)
  5) 尺寸链极值法公差：T0 = ΣTi（所有组成环公差和）
  6) 表面粗糙度 Ra 查用（加工方法典型值）
  7) 可靠度计算 R(t) = exp(-(t/η)^β)（威布尔分布）

数据库：
  - 常用轴用材料（45/40Cr/35CrMo 的 σ-1/σb）
  - 深沟球轴承额定动载荷 C（6200~6312 典型值）
  - 齿轮材料接触/弯曲疲劳极限（45/40Cr/20CrMnTi）
  - 弹簧材料许用切应力与切变模量（碳素/弹簧钢/不锈钢）
  - 螺栓强度等级（4.6~12.9 级的 σs/σb）
  - 键规格标准（轴径 d 对应平键 b×h）
  - IT 标准公差等级系数（IT5~IT12）
  - 表面粗糙度典型 Ra 值（加工方法对应）

设计原则：
  - 与现有领域保持一致：_curryN 柯里化、前缀区分子领域
  - 公式基于中国机械设计通用规范（GB/T）简化
  - 参数单位：长度 mm, 力 N, 应力 MPa, 功率 kW, 转速 r/min
  - 返回纯数值，除零等异常由 Python 自行抛错
"""

from __future__ import annotations
import math


# ========== 柯里化工具 ==========

def _curry1(func):
    return lambda a: func(a)


def _curry2(func):
    def w1(a):
        return lambda b: func(a, b)
    return w1


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


# ========== 数据库 ==========

# 常用轴的材料力学性能（σ-1 对称弯曲疲劳/σb 抗拉强度，MPa，正火/调质态）
SHAFT_MATERIAL: dict[str, dict[str, float]] = {
    "45_正火":      {"sigma_1": 250, "sigma_b": 600, "sigma_s": 355},
    "45_调质":      {"sigma_1": 275, "sigma_b": 650, "sigma_s": 380},
    "40Cr_调质":    {"sigma_1": 355, "sigma_b": 735, "sigma_s": 540},
    "35CrMo_调质":  {"sigma_1": 380, "sigma_b": 835, "sigma_s": 540},
    "42CrMo_调质":  {"sigma_1": 410, "sigma_b": 900, "sigma_s": 650},
    "20CrMnTi_渗碳":{"sigma_1": 430, "sigma_b": 1080, "sigma_s": 835},
}

# 深沟球轴承 62xx/63xx 系列基本额定动载荷 C（kN）与 C0（kN）
# 来源 GB/T 276 简化典型值
BALL_BEARING_62XX: dict[str, dict[str, float]] = {
    "6200": {"C": 7.65,  "C0": 3.72,  "d": 10, "D": 30, "B": 9},
    "6201": {"C": 9.56,  "C0": 4.78,  "d": 12, "D": 32, "B": 10},
    "6202": {"C": 11.4,  "C0": 6.08,  "d": 15, "D": 35, "B": 11},
    "6203": {"C": 14.2,  "C0": 7.88,  "d": 17, "D": 40, "B": 12},
    "6204": {"C": 19.8,  "C0": 11.4,  "d": 20, "D": 47, "B": 14},
    "6205": {"C": 25.5,  "C0": 15.2,  "d": 25, "D": 52, "B": 15},
    "6206": {"C": 30.8,  "C0": 19.8,  "d": 30, "D": 62, "B": 16},
    "6207": {"C": 36.8,  "C0": 25.5,  "d": 35, "D": 72, "B": 17},
    "6208": {"C": 42.8,  "C0": 31.2,  "d": 40, "D": 80, "B": 18},
    "6210": {"C": 53.0,  "C0": 40.8,  "d": 50, "D": 90, "B": 20},
    "6212": {"C": 67.8,  "C0": 54.2,  "d": 60, "D": 110, "B": 22},
}

BALL_BEARING_63XX: dict[str, dict[str, float]] = {
    "6304": {"C": 30.8,  "C0": 18.0,  "d": 20, "D": 52, "B": 15},
    "6305": {"C": 42.2,  "C0": 25.5,  "d": 25, "D": 62, "B": 17},
    "6306": {"C": 50.8,  "C0": 31.8,  "d": 30, "D": 72, "B": 19},
    "6308": {"C": 68.2,  "C0": 44.8,  "d": 40, "D": 90, "B": 23},
    "6310": {"C": 87.0,  "C0": 61.8,  "d": 50, "D": 110, "B": 27},
    "6312": {"C": 118,   "C0": 89.8,  "d": 60, "D": 130, "B": 31},
}

# 圆柱滚子轴承 N 系列：额定动载荷 C（kN）—— 取少数
ROLLER_BEARING: dict[str, dict[str, float]] = {
    "N205": {"C": 32.5,  "C0": 32.0,  "d": 25, "D": 52, "B": 15},
    "N206": {"C": 42.5,  "C0": 44.0,  "d": 30, "D": 62, "B": 16},
    "N208": {"C": 60.8,  "C0": 65.8,  "d": 40, "D": 80, "B": 18},
    "N210": {"C": 82.2,  "C0": 93.0,  "d": 50, "D": 90, "B": 20},
}

# 齿轮材料疲劳极限（简化值）：σHlim 接触/σFlim 弯曲，MPa
GEAR_MATERIAL: dict[str, dict[str, float]] = {
    "45_调质":      {"Hlim": 580, "Flim": 210},
    "40Cr_调质":    {"Hlim": 730, "Flim": 280},
    "35CrMo_调质":  {"Hlim": 780, "Flim": 300},
    "42CrMo_调质":  {"Hlim": 830, "Flim": 320},
    "20Cr_渗碳淬火": {"Hlim": 1150, "Flim": 450},
    "20CrMnTi_渗碳": {"Hlim": 1500, "Flim": 500},
    "40CrMnMo_调质":{"Hlim": 880, "Flim": 340},
}

# 齿轮材料弹性系数 ZE（MPa^0.5）—— 钢-钢配对
ZE_STEEL_STEEL = 189.8
# 节点区域系数 ZH（标准 α=20° 直齿）
ZH_STANDARD = 2.5

# 弹簧材料：许用切应力 τ许（MPa）, 切变模量 G（MPa）, 弹性模量 E
SPRING_MATERIAL: dict[str, dict[str, float]] = {
    "碳素弹簧钢丝B类": {"tau_p": 440, "tau_s": 0.5, "G": 80000, "E": 206000},
    "碳素弹簧钢丝C类": {"tau_p": 470, "tau_s": 0.5, "G": 80000, "E": 206000},
    "65Mn":           {"tau_p": 445, "tau_s": 0.5, "G": 80000, "E": 206000},
    "60Si2Mn":        {"tau_p": 590, "tau_s": 0.5, "G": 80000, "E": 196000},
    "50CrVA":         {"tau_p": 550, "tau_s": 0.5, "G": 80000, "E": 206000},
    "1Cr18Ni9":       {"tau_p": 320, "tau_s": 0.4, "G": 71000, "E": 193000},
}

# 螺栓强度等级（σs 屈服/σb 抗拉强度，MPa，GB/T 3098.1）
BOLT_GRADE: dict[str, dict[str, float]] = {
    "4.6":  {"sigma_s": 240, "sigma_b": 400},
    "4.8":  {"sigma_s": 320, "sigma_b": 400},
    "5.6":  {"sigma_s": 300, "sigma_b": 500},
    "5.8":  {"sigma_s": 400, "sigma_b": 500},
    "6.8":  {"sigma_s": 480, "sigma_b": 600},
    "8.8":  {"sigma_s": 640, "sigma_b": 800},
    "9.8":  {"sigma_s": 720, "sigma_b": 900},
    "10.9": {"sigma_s": 900, "sigma_b": 1000},
    "12.9": {"sigma_s": 1080, "sigma_b": 1200},
}

# 螺栓小径 d1（mm），GB/T 196 简化常用值
BOLT_THREAD: dict[str, dict[str, float]] = {
    "M6":   {"d": 6,  "d1": 4.917, "d0": 5.0, "p": 1.0},
    "M8":   {"d": 8,  "d1": 6.647, "d0": 6.8, "p": 1.25},
    "M10":  {"d": 10, "d1": 8.376, "d0": 8.5, "p": 1.5},
    "M12":  {"d": 12, "d1": 10.106, "d0": 10.3, "p": 1.75},
    "M16":  {"d": 16, "d1": 13.835, "d0": 14.0, "p": 2.0},
    "M20":  {"d": 20, "d1": 17.294, "d0": 17.5, "p": 2.5},
    "M24":  {"d": 24, "d1": 20.752, "d0": 21.0, "p": 3.0},
    "M30":  {"d": 30, "d1": 26.211, "d0": 26.5, "p": 3.5},
}

# 平键规格（轴径 d 对应 b×h，GB/T 1095 简化）
# 格式：轴径范围 (dmin, dmax] → (b, h, t1, t2)
FLAT_KEY_SPEC: list[tuple[float, float, float, float, float, float]] = [
    # dmin, dmax, b, h, t1(轴深), t2(毂深)
    (6,   8,   2,  2,  1.2, 1.0),
    (8,   10,  3,  3,  1.8, 1.4),
    (10,  12,  4,  4,  2.5, 1.8),
    (12,  17,  5,  5,  3.0, 2.3),
    (17,  22,  6,  6,  3.5, 2.8),
    (22,  30,  8,  7,  4.0, 3.3),
    (30,  38, 10,  8,  5.0, 3.3),
    (38,  44, 12,  8,  5.0, 3.3),
    (44,  50, 14,  9,  5.5, 3.8),
    (50,  58, 16, 10,  6.0, 4.3),
    (58,  65, 18, 11,  7.0, 4.4),
    (65,  75, 20, 12,  7.5, 4.9),
    (75,  85, 22, 14,  9.0, 5.4),
    (85,  95, 25, 14,  9.0, 5.4),
    (95, 110, 28, 16, 10.0, 6.4),
]

# IT 标准公差等级系数 a（IT = a·i，单位 μm，i 为公差单位）
# GB/T 1800.1 简化 IT5~IT12
IT_GRADE_COEFF: dict[str, float] = {
    "IT5": 7.0, "IT6": 10.0, "IT7": 16.0, "IT8": 25.0,
    "IT9": 40.0, "IT10": 64.0, "IT11": 100.0, "IT12": 160.0,
    "IT01": 0.3, "IT0": 0.5, "IT1": 0.8, "IT2": 1.25,
    "IT3": 2.0, "IT4": 3.0, "IT13": 250, "IT14": 400,
    "IT15": 640, "IT16": 1000, "IT17": 1600, "IT18": 2500,
}

# 表面粗糙度 Ra（μm）典型加工方法值（范围上限）
SURFACE_RA: dict[str, float] = {
    "粗车_外圆": 12.5, "半精车_外圆": 3.2, "精车_外圆": 0.8,
    "粗铣_平面": 12.5, "精铣_平面": 3.2, "粗刨": 12.5,
    "粗镗_孔": 12.5, "精镗_孔": 1.6, "钻_孔": 12.5,
    "铰_孔": 0.8, "粗磨_外圆": 0.8, "精磨_外圆": 0.2,
    "研磨_外圆": 0.05, "抛光": 0.1, "镗_孔": 1.6,
    "拉削": 0.8, "滚压": 0.2,
}


# ========== 常量 ==========

PI = math.pi
G_STEEL_DESIGN = 80000.0   # 钢材切变模量 MPa（常用简化）
E_STEEL_DESIGN = 206000.0  # 钢材弹性模量 MPa
ZETA_TORSION = 0.6         # 弯扭折合系数 α（不变应力轴取 0.3，脉动用 0.6）
TAU_T_ALLOW_45 = 35.0      # 45 钢许用扭转切应力 MPa（初估轴径）
ALPHA_FRICTION = 0.08      # 过盈配合摩擦系数（钢-钢简化）
COEF_SPRING_K = 1.25       # 弹簧曲度系数近似（C=5~8 时 K≈1.2~1.3）
S0_BEARING_STATIC = 1.0     # 轴承静强度安全系数（正常工况）
K_LOAD_BEARING = 1.0       # 轴承载荷系数（平稳运转默认 1）
SHMIN_GEAR = 1.1           # 齿轮接触最小安全系数（通用）
SFMIN_GEAR = 1.5           # 齿轮弯曲最小安全系数（通用）
CHI_PRELOAD_VAR = 0.6      # 螺栓残余预紧比（变载轴向）
CHI_PRELOAD_STATIC = 0.2   # 螺栓残余预紧比（静载）


# ========== 一、轴与连接件 ==========

def _轴设_扭转切应力(T, d):
    """τ = T / Wt = 16T / (πd³)，T 单位 N·mm，d mm，返回 MPa。"""
    if d == 0:
        return 0.0
    return 16 * T / (PI * d ** 3)


def _轴设_弯曲正应力(M, d):
    """σ = M / W = 32M / (πd³)，M 单位 N·mm，d mm，返回 MPa。"""
    if d == 0:
        return 0.0
    return 32 * M / (PI * d ** 3)


def _轴设_弯扭当量弯矩(M, T, alpha=ZETA_TORSION):
    """Me = √(M² + (α·T)²)，α 为折合系数（不变 0.3，脉动 0.6）。"""
    return math.sqrt(M ** 2 + (alpha * T) ** 2)


def _轴设_按扭转初估直径(P, n, tau_allow=TAU_T_ALLOW_45):
    """按扭转强度初估轴径：d ≥ ∛(9.55e6·P / (0.2·τ·n))。
    P kW，n r/min，tau_allow MPa → 返回 d mm。"""
    if tau_allow == 0 or n == 0:
        return 0.0
    # [τ] 单位 MPa, T = 9.55e6 P/n N·mm, d ≥ ∛(16T / (π·[τ]/0.2)) 简化
    # 工程近似: d ≥ ∛(9.55e6·P / (0.2·[τ]·n))
    return (9.55e6 * P / (0.2 * tau_allow * n)) ** (1 / 3.0)


def _轴设_平键挤压强度(T, d, h, L):
    """σp = 4T / (d·h·L)，T N·mm，d,h,L mm → 返回 MPa。"""
    denom = d * h * L
    if denom == 0:
        return 0.0
    return 4 * T / denom


def _轴设_平键剪切强度(T, d, b, L):
    """τ = 2T / (d·b·L)，T N·mm，d,b,L mm → 返回 MPa。"""
    denom = d * b * L
    if denom == 0:
        return 0.0
    return 2 * T / denom


def _轴设_查平键规格(d):
    """按轴径 d（mm）查平键规格 b×h（GB/T 1095 简化）。
    返回 (b, h, t1, t2)，未匹配时返回 (0,0,0,0)。"""
    for dmin, dmax, b, h, t1, t2 in FLAT_KEY_SPEC:
        if dmin < d <= dmax:
            return (b, h, t1, t2)
    return (0.0, 0.0, 0.0, 0.0)


def _轴设_花键挤压强度(T, z, h, L, Dm):
    """矩形花键挤压强度（简化）：σp = 8T / (z·h·L·Dm)，T N·mm，其他 mm，返回 MPa。"""
    denom = z * h * L * Dm
    if denom == 0:
        return 0.0
    return 8 * T / denom


def _轴设_过盈配合扭矩(p, d, L, mu=ALPHA_FRICTION):
    """过盈配合传递摩擦扭矩 T = π·p·d·L·μ·d/2。
    p 配合压强 MPa，d 配合直径 mm，L 配合长度 mm，μ 摩擦系数 → T N·mm。"""
    return PI * p * d * L * mu * d / 2


# ========== 二、滚动轴承 ==========

def _轴承_额定寿命_转(C, P, epsilon=3.0):
    """L10 = (C/P)^ε × 10⁶ 转，C P 同单位（kN 或 N），ε=3球/10/3滚子。"""
    if P == 0:
        return float("inf")
    return (C / P) ** epsilon * 1e6


def _轴承_额定寿命_小时(C, P, n, epsilon=3.0):
    """Lh = (10⁶ / (60n)) × (C/P)^ε（小时），n r/min。"""
    if P == 0 or n == 0:
        return float("inf")
    return (1e6 / (60 * n)) * (C / P) ** epsilon


def _轴承_当量动载荷(Fr, Fa, X=1.0, Y=0.0, fp=K_LOAD_BEARING):
    """P = fp·(X·Fr + Y·Fa)，fp 载荷系数（平稳1/中冲击1.2/重冲击1.5）。"""
    return fp * (X * Fr + Y * Fa)


def _轴承_静载校核(P0, C0, S0=S0_BEARING_STATIC):
    """静强度判定：P0 ≤ C0/S0 时返回 True 满足，否则 False。"""
    if C0 == 0:
        return False
    return P0 <= C0 / S0


def _轴承_附加轴向力(Fr, e=0.68):
    """角接触轴承附加轴向力简化 Fa = e·Fr（e 查简化值，7000C 取 0.68）。"""
    return e * Fr


def _轴承_寿命系数(n, epsilon=3.0):
    """fn = (33.3 / n)^(1/ε)，n r/min，对应 C 单位 kN 时寿命速度系数。"""
    if n == 0:
        return float("inf")
    return (33.3 / n) ** (1 / epsilon)


def _轴承_查深沟球_62xx(model):
    """查 62xx 深沟球轴承参数 (C, C0, d, D, B)，不存在返回 (0,0,0,0,0)。"""
    m = BALL_BEARING_62XX.get(model)
    if m is None:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    return (m["C"], m["C0"], m["d"], m["D"], m["B"])


def _轴承_查深沟球_63xx(model):
    """查 63xx 深沟球轴承参数 (C, C0, d, D, B)。"""
    m = BALL_BEARING_63XX.get(model)
    if m is None:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    return (m["C"], m["C0"], m["d"], m["D"], m["B"])


# ========== 三、齿轮传动 ==========

def _齿轮_分度圆直径(m, z):
    """d = m·z，模数 m mm，齿数 z → 直径 mm。"""
    return m * z


def _齿轮_中心距(m, z1, z2):
    """a = m(z1+z2)/2。"""
    return m * (z1 + z2) / 2.0


def _齿轮_传动比_齿数(z1, z2):
    """i = z2/z1（n1/n2）。"""
    if z1 == 0:
        return 0.0
    return z2 / z1


def _齿轮_齿宽(phi_d, d1):
    """b = φd·d1，φd 齿宽系数（0.3~1.2 常用），d1 小轮分度圆 mm → b mm。"""
    return phi_d * d1


def _齿轮_圆周速度(d1_mm, n1):
    """v = π·d1·n1 / (60×1000)，d1 mm，n1 r/min → v m/s。"""
    return PI * d1_mm * n1 / (60 * 1000.0)


def _齿轮_转矩_Pn(P_kW, n1):
    """T1 = 9.55e6·P/n1，P kW，n r/min → T1 N·mm。"""
    if n1 == 0:
        return 0.0
    return 9.55e6 * P_kW / n1


def _齿轮_弯曲应力(T1, phi_d, m, z1, YFa=2.5, YSa=1.65, K=1.5):
    """直齿圆柱齿轮弯曲疲劳 σF = 2KT1·YFa·YSa / (φd·b·m²·z1)
    简化：b = φd·d1 = φd·m·z1 代入 → σF = 2KT1·YFa·YSa / (φd·φd·m·z1·m²·z1)
    这里按原式：b=φd·d1，用户给的是 φd（齿宽系数）。返回 MPa。"""
    b = phi_d * m * z1  # d1 = m·z1
    denom = phi_d * b * m ** 2 * z1
    if denom == 0:
        return 0.0
    return 2 * K * T1 * YFa * YSa / denom


def _齿轮_许用接触应力(Hlim, Zn=1.0, S_Hmin=SHMIN_GEAR):
    """σHP = Hlim·Zn/S_Hmin，Zn 寿命系数。返回 MPa。"""
    return Hlim * Zn / S_Hmin


def _齿轮_许用弯曲应力(Flim, Yn=1.0, S_Fmin=SFMIN_GEAR, Yx=1.0):
    """σFP = Flim·Yn·Yx / S_Fmin，Yn 寿命系数、Yx 尺寸系数。返回 MPa。"""
    return Flim * Yn * Yx / S_Fmin


# ========== 四、弹簧设计 ==========

def _弹簧_旋绕比(D, d):
    """C = D/d（旋绕比/弹簧指数），推荐 4~16。"""
    if d == 0:
        return 0.0
    return D / d


def _弹簧_曲度系数(C):
    """K = (4C-1)/(4C-4) + 0.615/C（Wahl 系数）。"""
    if C <= 1.0:
        return float("inf")
    return (4 * C - 1) / (4 * C - 4) + 0.615 / C


def _弹簧_切应力(F, D, d, K=1.25):
    """τ = 8·K·D·F / (π·d³)。F N, D mm, d mm, K 曲度系数 → τ MPa。"""
    if d == 0:
        return 0.0
    return 8 * K * D * F / (PI * d ** 3)


def _弹簧_变形量(F, D, d, n, G=G_STEEL_DESIGN):
    """λ = 8·F·D³·n / (G·d⁴)，n 有效圈数，G 切变模量 MPa。返回 mm。"""
    denom = G * d ** 4
    if denom == 0:
        return 0.0
    return 8 * F * D ** 3 * n / denom


def _弹簧_刚度(D, d, n, G=G_STEEL_DESIGN):
    """k = G·d⁴ / (8·D³·n) N/mm。"""
    denom = 8 * D ** 3 * n
    if denom == 0:
        return 0.0
    return G * d ** 4 / denom


def _弹簧_总圈数(n, end_type="YI型"):
    """n1 = n + 2（YI型/Y型两端各磨平一圈），n1=n+1.5（YII型）。"""
    if end_type == "YII型":
        return n + 1.5
    return n + 2.0  # 含 Y 型 / YI 型


def _弹簧_自由高度(n, p, d, end_type="YI型"):
    """H0 = n·p + 2·d（Y 型端部不磨）；
    H0 = n·p + 1.5·d（YI 型两端磨平）。"""
    if end_type == "YI型":
        return n * p + 1.5 * d
    return n * p + 2.0 * d


def _弹簧_螺旋角(p, D):
    """α = arctan(p / (π·D))，返回弧度。"""
    denom = PI * D
    if denom == 0:
        return 0.0
    return math.atan(p / denom)


# ========== 五、紧固件与连接件 ==========

def _联接_受拉螺栓强度(F_pre, A_s, sigma_s, S=1.5):
    """受拉预紧螺栓：σ = 1.3·F_pre / A_s ≤ σs/S。
    F_pre N，A_s 应力面积 mm²，σs MPa；False 不满足。
    返回应力 MPa（调用者再比较 sigma_s/S）。"""
    if A_s == 0:
        return 0.0
    return 1.3 * F_pre / A_s


def _联接_受剪螺栓强度(F, m, d0):
    """τ = 4F / (m·π·d0²)，m 剪切面数，d0 螺栓杆 mm，F N → τ MPa。"""
    denom = m * PI * d0 ** 2
    if denom == 0:
        return 0.0
    return 4 * F / denom


def _联接_螺栓挤压强度(F, d0, sum_t):
    """σp = F / (d0·Σt)，Σt 同方向被连接件最小厚度和 mm → σp MPa。"""
    denom = d0 * sum_t
    if denom == 0:
        return 0.0
    return F / denom


def _联接_螺栓总拉力(F_work, F_double_prime):
    """F' = F_work + F''，轴向工作载荷 F_work + 残余预紧 F'' → 总拉力 N。"""
    return F_work + F_double_prime


def _联接_残余预紧力(F_work, chi=CHI_PRELOAD_VAR):
    """F'' = χ·F_work，χ 变载 0.6~1.0 / 静载 0.2~0.6。"""
    return chi * F_work


def _联接_查螺栓强度(grade):
    """查螺栓强度等级：(σs, σb) MPa。"""
    g = BOLT_GRADE.get(grade)
    if g is None:
        return (0.0, 0.0)
    return (g["sigma_s"], g["sigma_b"])


def _联接_查螺栓规格(spec):
    """查螺栓规格 (d, d1, d0, p) mm，spec 如 "M12"。"""
    g = BOLT_THREAD.get(spec)
    if g is None:
        return (0.0, 0.0, 0.0, 0.0)
    return (g["d"], g["d1"], g["d0"], g["p"])


def _联接_销剪切强度(F, d, z=1.0):
    """τ = 4F / (π·d²·z)，d mm, z 剪切面数 → τ MPa。"""
    denom = PI * d ** 2 * z
    if denom == 0:
        return 0.0
    return 4 * F / denom


# ========== 六、公差配合与可靠性 ==========

def _公差_IT值(grade_str, D_mm):
    """IT 标准公差值（μm）：i = 0.45·∛D + 0.001·D，IT = a·i，
    a 为等级系数；D_mm 为公称尺寸 mm。返回 μm。"""
    a = IT_GRADE_COEFF.get(grade_str)
    if a is None:
        return 0.0
    i = 0.45 * (abs(D_mm)) ** (1 / 3.0) + 0.001 * abs(D_mm)
    return a * i


def _公差_基孔制配合(IT_grade, fit_type, D_mm):
    """基孔制配合（简化）：返回 (ES, EI, es, ei) μm。
    fit_type:
      "H7h6" → 间隙（常用高精度）
      "H7g6" → 间隙（定心间隙配合）
      "H7js6" → 过渡
      "H7k6" → 过渡
      "H7n6" → 过渡偏紧
      "H7p6" → 过盈
      "H7s6" → 过盈
    简化：孔 H，下偏差 EI=0；上偏差 ES = +IT_hole。
    轴的偏差按基准简化。仅返回公差带上下限（μm），非完整 GB 值。"""
    # 从 grade 解析 IT 等级
    hole_grade = "H7"
    shaft_grade = "h6"
    # fit_type 中的数字解析（简化默认 H7/h6）
    hole_IT_val = _公差_IT值("IT7", D_mm)
    shaft_IT_val = _公差_IT值("IT6", D_mm)
    # 轴的基本偏差（常用）（μm，简化）
    # 小写字母：h→0, g→-5, js→±IT/2, k→+IT/2（>3mm）, n→+12, p→+22, s→+44
    # 统一按 D_mm 范围平均值近似
    basic_shaft = {
        "h": 0, "g": -5, "js": 0, "k": 2, "n": 12, "p": 22, "s": 44,
    }
    # 解析 fit_type
    shaft_letter = "h"
    import re
    m = re.search(r"H\d([a-z]+)\d", fit_type)
    if m:
        shaft_letter = m.group(1)
    EI = 0  # 基孔：孔下偏差
    ES = hole_IT_val  # 孔上偏差 = EI + IT7
    # 轴偏差
    es_basic = basic_shaft.get(shaft_letter, 0)
    if shaft_letter == "js":
        ei = - shaft_IT_val / 2.0
        es = + shaft_IT_val / 2.0
    elif shaft_letter == "h":
        es = 0
        ei = - shaft_IT_val
    elif shaft_letter == "g":
        es = es_basic
        ei = es_basic - shaft_IT_val
    elif shaft_letter == "k":
        ei = es_basic
        es = ei + shaft_IT_val
    else:  # n, p, s
        ei = es_basic
        es = ei + shaft_IT_val
    return (ES, EI, es, ei)


def _公差_尺寸链封闭环(plus_rings, minus_rings):
    """极值法：A0 = Σ(增环) - Σ(减环)。
    plus_rings/minus_rings 为 list 或单值。"""
    p = sum(plus_rings) if isinstance(plus_rings, list) else plus_rings
    m = sum(minus_rings) if isinstance(minus_rings, list) else minus_rings
    return p - m


def _公差_尺寸链封闭环公差(tolerances):
    """极值法：T0 = ΣTi。tolerances 为组成环公差 list。"""
    return sum(tolerances) if isinstance(tolerances, list) else tolerances


def _公差_查表面粗糙度(method):
    """按加工方法查典型 Ra（μm）。"""
    return SURFACE_RA.get(method, 6.3)


def _公差_威布尔可靠度(t, eta, beta):
    """R(t) = exp(-(t/η)^β)，η 特征寿命，β 形状参数。"""
    if eta == 0:
        return 0.0
    return math.exp(- (t / eta) ** beta)


# ========== 注册到解释器 ==========

def _register_mech_design(builtins: dict) -> None:
    """将机械设计内建注册到解释器 builtins。"""

    # ===== 一、轴与连接件 =====
    builtins["轴设_扭转切应力"] = _curry2(_轴设_扭转切应力)
    builtins["轴设_弯曲正应力"] = _curry2(_轴设_弯曲正应力)
    builtins["轴设_弯扭当量弯矩"] = _curry3(_轴设_弯扭当量弯矩)
    builtins["轴设_按扭转初估直径"] = _curry3(_轴设_按扭转初估直径)
    builtins["轴设_平键挤压强度"] = _curry4(_轴设_平键挤压强度)
    builtins["轴设_平键剪切强度"] = _curry4(_轴设_平键剪切强度)
    builtins["轴设_查平键规格"] = _轴设_查平键规格
    builtins["轴设_花键挤压强度"] = _curry5(_轴设_花键挤压强度)
    builtins["轴设_过盈配合扭矩"] = _curry4(_轴设_过盈配合扭矩)
    # ===== 二、滚动轴承 =====
    builtins["轴承_额定寿命_转"] = _curry3(_轴承_额定寿命_转)
    builtins["轴承_额定寿命_小时"] = _curry4(_轴承_额定寿命_小时)
    builtins["轴承_当量动载荷"] = _curry5(_轴承_当量动载荷)
    builtins["轴承_静载校核"] = _curry3(_轴承_静载校核)
    builtins["轴承_附加轴向力"] = _curry2(_轴承_附加轴向力)
    builtins["轴承_寿命系数"] = _curry2(_轴承_寿命系数)
    builtins["轴承_查深沟球_62xx"] = _轴承_查深沟球_62xx
    builtins["轴承_查深沟球_63xx"] = _轴承_查深沟球_63xx
    # ===== 三、齿轮传动 =====
    builtins["齿轮_分度圆直径"] = _curry2(_齿轮_分度圆直径)
    builtins["齿轮_中心距"] = _curry3(_齿轮_中心距)
    builtins["齿轮_传动比_齿数"] = _curry2(_齿轮_传动比_齿数)
    builtins["齿轮_齿宽"] = _curry2(_齿轮_齿宽)
    builtins["齿轮_圆周速度"] = _curry2(_齿轮_圆周速度)
    builtins["齿轮_转矩_Pn"] = _curry2(_齿轮_转矩_Pn)
    builtins["齿轮_弯曲应力"] = _curry7(_齿轮_弯曲应力)
    builtins["齿轮_许用接触应力"] = _curry3(_齿轮_许用接触应力)
    builtins["齿轮_许用弯曲应力"] = _curry4(_齿轮_许用弯曲应力)
    # ===== 四、弹簧设计 =====
    builtins["弹簧_旋绕比"] = _curry2(_弹簧_旋绕比)
    builtins["弹簧_曲度系数"] = _弹簧_曲度系数
    builtins["弹簧_切应力"] = _curry4(_弹簧_切应力)
    builtins["弹簧_变形量"] = _curry5(_弹簧_变形量)
    builtins["弹簧_刚度"] = _curry4(_弹簧_刚度)
    builtins["弹簧_总圈数"] = _curry2(_弹簧_总圈数)
    builtins["弹簧_自由高度"] = _curry4(_弹簧_自由高度)
    builtins["弹簧_螺旋角"] = _curry2(_弹簧_螺旋角)

    # ===== 五、紧固件与连接件 =====
    builtins["联接_受拉螺栓强度"] = _curry4(_联接_受拉螺栓强度)
    builtins["联接_受剪螺栓强度"] = _curry3(_联接_受剪螺栓强度)
    builtins["联接_螺栓挤压强度"] = _curry3(_联接_螺栓挤压强度)
    builtins["联接_螺栓总拉力"] = _curry2(_联接_螺栓总拉力)
    builtins["联接_残余预紧力"] = _curry2(_联接_残余预紧力)
    builtins["联接_查螺栓强度"] = _联接_查螺栓强度
    builtins["联接_查螺栓规格"] = _联接_查螺栓规格
    builtins["联接_销剪切强度"] = _curry3(_联接_销剪切强度)
    # ===== 六、公差配合与可靠性 =====
    builtins["公差_IT值"] = _curry2(_公差_IT值)
    builtins["公差_基孔制配合"] = _curry3(_公差_基孔制配合)
    builtins["公差_尺寸链封闭环"] = _curry2(_公差_尺寸链封闭环)
    builtins["公差_尺寸链封闭环公差"] = _公差_尺寸链封闭环公差
    builtins["公差_查表面粗糙度"] = _公差_查表面粗糙度
    builtins["公差_威布尔可靠度"] = _curry3(_公差_威布尔可靠度)

    # ===== 数据库：轴用材料 =====
    for grade, spec in SHAFT_MATERIAL.items():
        for k, v in spec.items():
            builtins[f"轴材料_{grade}_{k}"] = v

    # ===== 数据库：深沟球轴承 =====
    for model, spec in BALL_BEARING_62XX.items():
        for k, v in spec.items():
            builtins[f"轴承_62_{model}_{k}"] = v
    for model, spec in BALL_BEARING_63XX.items():
        for k, v in spec.items():
            builtins[f"轴承_63_{model}_{k}"] = v
    for model, spec in ROLLER_BEARING.items():
        for k, v in spec.items():
            builtins[f"轴承_N_{model}_{k}"] = v

    # ===== 数据库：齿轮材料 =====
    for grade, spec in GEAR_MATERIAL.items():
        for k, v in spec.items():
            builtins[f"齿轮材料_{grade}_{k}"] = v
    builtins["齿轮_ZE_钢钢"] = ZE_STEEL_STEEL
    builtins["齿轮_ZH_标准"] = ZH_STANDARD

    # ===== 数据库：弹簧材料 =====
    for grade, spec in SPRING_MATERIAL.items():
        for k, v in spec.items():
            builtins[f"弹簧材料_{grade}_{k}"] = v

    # ===== 数据库：螺栓 =====
    for grade, spec in BOLT_GRADE.items():
        for k, v in spec.items():
            builtins[f"螺栓强度_{grade}_{k}"] = v
    for spec, vals in BOLT_THREAD.items():
        for k, v in vals.items():
            builtins[f"螺栓规格_{spec}_{k}"] = v

    # ===== 数据库：公差等级系数 =====
    for g, v in IT_GRADE_COEFF.items():
        builtins[f"公差系数_{g}"] = v

    # ===== 数据库：表面粗糙度 =====
    for m, v in SURFACE_RA.items():
        builtins[f"表面Ra_{m}"] = v

    # ===== 常量 =====
    builtins["机设_G_钢"] = G_STEEL_DESIGN
    builtins["机设_E_钢"] = E_STEEL_DESIGN
    builtins["机设_弯扭折合α"] = ZETA_TORSION
    builtins["机设_45钢许用τ"] = TAU_T_ALLOW_45
    builtins["机设_过盈摩擦μ"] = ALPHA_FRICTION
    builtins["机设_齿轮SHmin"] = SHMIN_GEAR
    builtins["机设_齿轮SFmin"] = SFMIN_GEAR


def _curry6(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    def w5(e):
                        return lambda f: func(a, b, c, d, e, f)
                    return w5
                return w4
            return w3
        return w2
    return w1


def _curry7(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    def w5(e):
                        def w6(f):
                            return lambda g: func(a, b, c, d, e, f, g)
                        return w6
                    return w5
                return w4
            return w3
        return w2
    return w1


# ========== 语义符号表 ==========

def _mech_design_symtab_names() -> list[str]:
    names: list[str] = []

    # 一、轴与连接件
    for n in ["扭转切应力", "弯曲正应力", "弯扭当量弯矩", "按扭转初估直径",
              "平键挤压强度", "平键剪切强度", "查平键规格",
              "花键挤压强度", "过盈配合扭矩"]:
        names.append(f"轴设_{n}")

    # 二、滚动轴承
    for n in ["额定寿命_转", "额定寿命_小时", "当量动载荷", "静载校核",
              "附加轴向力", "寿命系数", "查深沟球_62xx", "查深沟球_63xx"]:
        names.append(f"轴承_{n}")

    # 三、齿轮传动
    for n in ["分度圆直径", "中心距", "传动比_齿数", "齿宽", "圆周速度",
              "转矩_Pn", "弯曲应力", "许用接触应力", "许用弯曲应力"]:
        names.append(f"齿轮_{n}")

    # 四、弹簧设计
    for n in ["旋绕比", "曲度系数", "切应力", "变形量", "刚度",
              "总圈数", "自由高度", "螺旋角"]:
        names.append(f"弹簧_{n}")

    # 五、紧固件与连接件
    for n in ["受拉螺栓强度", "受剪螺栓强度", "螺栓挤压强度",
              "螺栓总拉力", "残余预紧力", "查螺栓强度",
              "查螺栓规格", "销剪切强度"]:
        names.append(f"联接_{n}")

    # 六、公差配合与可靠性
    for n in ["IT值", "基孔制配合", "尺寸链封闭环", "尺寸链封闭环公差",
              "查表面粗糙度", "威布尔可靠度"]:
        names.append(f"公差_{n}")

    # 数据库：轴用材料
    for grade in SHAFT_MATERIAL:
        for k in SHAFT_MATERIAL[grade]:
            names.append(f"轴材料_{grade}_{k}")

    # 数据库：轴承
    for model in BALL_BEARING_62XX:
        for k in BALL_BEARING_62XX[model]:
            names.append(f"轴承_62_{model}_{k}")
    for model in BALL_BEARING_63XX:
        for k in BALL_BEARING_63XX[model]:
            names.append(f"轴承_63_{model}_{k}")
    for model in ROLLER_BEARING:
        for k in ROLLER_BEARING[model]:
            names.append(f"轴承_N_{model}_{k}")

    # 数据库：齿轮材料
    for grade in GEAR_MATERIAL:
        for k in GEAR_MATERIAL[grade]:
            names.append(f"齿轮材料_{grade}_{k}")
    names.extend(["齿轮_ZE_钢钢", "齿轮_ZH_标准"])

    # 数据库：弹簧材料
    for grade in SPRING_MATERIAL:
        for k in SPRING_MATERIAL[grade]:
            names.append(f"弹簧材料_{grade}_{k}")

    # 数据库：螺栓
    for grade in BOLT_GRADE:
        for k in BOLT_GRADE[grade]:
            names.append(f"螺栓强度_{grade}_{k}")
    for spec in BOLT_THREAD:
        for k in BOLT_THREAD[spec]:
            names.append(f"螺栓规格_{spec}_{k}")

    # 数据库：公差等级系数
    for g in IT_GRADE_COEFF:
        names.append(f"公差系数_{g}")

    # 数据库：表面粗糙度
    for m in SURFACE_RA:
        names.append(f"表面Ra_{m}")

    # 常量
    for n in ["机设_G_钢", "机设_E_钢", "机设_弯扭折合α",
              "机设_45钢许用τ", "机设_过盈摩擦μ",
              "机设_齿轮SHmin", "机设_齿轮SFmin"]:
        names.append(n)

    return names
