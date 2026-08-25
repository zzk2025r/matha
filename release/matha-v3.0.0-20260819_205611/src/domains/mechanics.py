"""Matha 机械领域模块：运动学 + 材料力学。

基于 mathlib 数学地基演化的机械领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

两大子领域：

一、运动学（Kinematics）
  1) 匀速直线：位移 / 时间 / 速度互算
  2) 匀变速直线：位移、末速度、末速度²-初速度² 三大公式
  3) 抛体运动：平抛 / 斜抛 射程 / 最大高度 / 落地时间
  4) 圆周运动：线速度 / 角速度 / 向心加速度 / 周期

二、材料力学（Mechanics of Materials）
  1) 轴向拉压：应力 σ=F/A、应变 ε=ΔL/L、胡克定律 σ=Eε、变形 ΔL=FL/EA
  2) 剪切：剪应力 τ=F/A、剪切胡克 τ=Gγ
  3) 梁弯曲：截面惯性矩（矩形/圆形/圆环）、最大弯曲正应力 σ_max=My_max/I
  4) 圆轴扭转：极惯性矩 Ip、最大扭转剪应力 τ_max=Tr/Ip、扭转角 φ=TL/(GIp)
  5) 材料属性数据库：钢/铝/铜/铸铁/木材/混凝土 的 E/G/σ_s/σ_b/ρ

设计原则：
  - 所有函数返回纯数值（float/int），不抛语义错（除以零等 Python 自身抛）
  - 多参函数一律 _curry2 封装（f(a)(b) 柯里化），与 Matha 语义一致
  - 材料属性作为常量值直接注册（如 钢_E=2.06e11 Pa）
  - 与物理/地理/天文领域共享 mathlib 的数学能力（g、pi、sin/cos/sqrt 等）
"""

from __future__ import annotations
import math


# ============================================================
# 柯里化工具（与 mathlib._curry2 语义一致）
# ============================================================

def _curry2(func):
    """两参 Python 函数 → 柯里化 f(a)(b)。"""
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def _curry3(func):
    """三参 → 柯里化 f(a)(b)(c)。"""
    def with_first(a):
        def with_second(b):
            return lambda c: func(a, b, c)
        return with_second
    return with_first


def _curry4(func):
    """四参 → 柯里化 f(a)(b)(c)(d)。"""
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1


# ============================================================
# 一、运动学（Kinematics）
# ============================================================

# ----- 匀速直线运动 -----
# s = v * t
def _匀速_位移(v, t): return v * t                # 位移 = 速度×时间
def _匀速_速度(s, t): return s / t                # 速度 = 位移/时间
def _匀速_时间(s, v): return s / v                # 时间 = 位移/速度

# ----- 匀变速直线运动 -----
def _匀变速_位移(v0, a, t): return v0 * t + 0.5 * a * t * t
def _匀变速_末速度(v0, a, t): return v0 + a * t
# v² - v0² = 2as → s = (v² - v0²)/(2a)
def _匀变速_位移由速度(v0, v, a): return (v * v - v0 * v0) / (2 * a)
# 自由落体（等价 v0=0, a=g）：s = ½gt², v = gt
def _自由落体_位移(t, g_val): return 0.5 * g_val * t * t
def _自由落体_末速度(t, g_val): return g_val * t

# ----- 抛体运动 -----
# 平抛：水平射程 R = v0*t = v0*sqrt(2h/g)；落地时间 t = sqrt(2h/g)
def _平抛_落地时间(h, g_val): return math.sqrt(2 * h / g_val)
def _平抛_射程(v0, h, g_val): return v0 * math.sqrt(2 * h / g_val)

# 斜抛（仰角 θ）：
#   射程 R = v0²*sin(2θ)/g
#   最大高度 H = v0²*sin²(θ)/(2g)
#   飞行时间 T = 2*v0*sin(θ)/g
def _斜抛_射程(v0, theta_rad, g_val):
    return v0 * v0 * math.sin(2 * theta_rad) / g_val

def _斜抛_最大高度(v0, theta_rad, g_val):
    s = math.sin(theta_rad)
    return v0 * v0 * s * s / (2 * g_val)

def _斜抛_飞行时间(v0, theta_rad, g_val):
    return 2 * v0 * math.sin(theta_rad) / g_val

# ----- 圆周运动 -----
# 线速度 v = ω * r
def _圆周_线速度(omega, r): return omega * r
# 角速度 ω = 2π / T
def _圆周_角速度(T): return 2 * math.pi / T
# 向心加速度 a_n = v²/r = ω²r
def _圆周_向心加速度_v(v, r): return v * v / r
def _圆周_向心加速度_w(omega, r): return omega * omega * r
# 周期 T = 2πr / v = 2π / ω
def _圆周_周期(v, r): return 2 * math.pi * r / v


# ============================================================
# 二、材料力学（Mechanics of Materials）
# ============================================================

# ----- 轴向拉压 -----
def _拉压_应力(F, A): return F / A                       # σ = F/A  Pa
def _拉压_应变(dL, L): return dL / L                      # ε = ΔL/L
def _拉压_胡克(E, epsilon): return E * epsilon             # σ = E·ε  Pa
def _拉压_变形(F, L, E, A): return F * L / (E * A)        # ΔL = FL/EA  m
# 安全系数 n = σ_s / σ（σ_s 屈服应力）
def _安全系数(sigma_s, sigma): return sigma_s / sigma

# ----- 剪切 -----
def _剪切_剪应力(F, A): return F / A                       # τ = F/A  Pa
def _剪切_剪应变(delta, L): return delta / L               # γ ≈ δ/L（小变形）
def _剪切_胡克(G, gamma): return G * gamma                 # τ = G·γ  Pa

# ----- 梁弯曲：截面惯性矩 + 弯曲正应力 -----
def _截面_矩形惯性矩(b, h): return b * h * h * h / 12      # I = bh³/12  m⁴
def _截面_圆形惯性矩(d): return math.pi * d * d * d * d / 64  # I = πd⁴/64  m⁴
def _截面_圆环惯性矩(D, d):
    return math.pi * (D**4 - d**4) / 64                    # I = π(D⁴-d⁴)/64
def _弯曲_正应力(M, y, I): return M * y / I                # σ = My/I  Pa
def _弯曲_最大正应力(M, y_max, I): return abs(M) * y_max / I

# ----- 圆轴扭转：极惯性矩 + 扭转剪应力 + 扭转角 -----
def _扭转_极惯性矩(d): return math.pi * d * d * d * d / 32  # Ip = πd⁴/32  m⁴
def _扭转_空心极惯性矩(D, d):
    return math.pi * (D**4 - d**4) / 32                    # Ip = π(D⁴-d⁴)/32
def _扭转_剪应力(T, r, Ip): return T * r / Ip               # τ = Tr/Ip  Pa
def _扭转_最大剪应力(T, d, Ip):
    return abs(T) * d / (2 * Ip)                            # r_max = d/2
def _扭转_扭转角(T, L, G, Ip): return T * L / (G * Ip)       # φ = TL/(GIp)  rad

# ----- 圆截面抗弯截面模量（简化） -----
def _抗弯截面模量_圆形(d): return math.pi * d * d * d / 32   # Wz = πd³/32
def _抗弯截面模量_矩形(b, h): return b * h * h / 6          # Wz = bh²/6


# ============================================================
# 材料属性数据库（标准值，SI 单位）
#   E  : 弹性模量（杨氏模量） Pa
#   G  : 剪切模量              Pa
#   σ_s: 屈服强度              Pa（屈服材料）
#   σ_b: 强度极限              Pa（脆性材料直接用 σ_b）
#   ρ  : 密度                 kg/m³
#   ν  : 泊松比              （无量纲）
# ============================================================

MATERIALS: dict[str, dict[str, float]] = {
    "钢_Q235": {
        "E": 2.06e11, "G": 7.9e10,
        "σ_s": 2.35e8, "σ_b": 3.75e8,
        "ρ": 7850, "ν": 0.3,
    },
    "钢_45号": {
        "E": 2.10e11, "G": 8.1e10,
        "σ_s": 3.55e8, "σ_b": 6.00e8,
        "ρ": 7850, "ν": 0.3,
    },
    "铝合金_6061": {
        "E": 6.90e10, "G": 2.60e10,
        "σ_s": 2.76e8, "σ_b": 3.10e8,
        "ρ": 2700, "ν": 0.33,
    },
    "纯铜": {
        "E": 1.10e11, "G": 4.10e10,
        "σ_s": 7.00e7, "σ_b": 2.20e8,
        "ρ": 8960, "ν": 0.34,
    },
    "灰铸铁_HT200": {
        "E": 1.20e11, "G": 4.50e10,
        "σ_s": 0.0,          # 铸铁为脆性材料，无明显屈服
        "σ_b": 2.00e8,       # 抗压强度更高，这里给拉伸强度
        "ρ": 7200, "ν": 0.25,
    },
    "木材_松木": {
        "E": 1.00e10, "G": 0.55e10,
        "σ_s": 4.00e7,
        "σ_b": 8.00e7,
        "ρ": 500, "ν": 0.0,
    },
    "混凝土_C30": {
        "E": 3.00e10, "G": 1.25e10,
        "σ_s": 0.0,          # 脆性
        "σ_b": 1.43e7,       # 抗压 σ_c=20.1MPa，拉伸很低
        "ρ": 2400, "ν": 0.2,
    },
}


def _材料_属性(mat_name: str, prop_key: str) -> float:
    """读取材料属性。未命中抛 KeyError 转 MathaRuntimeError（注册侧处理）。"""
    return MATERIALS[mat_name][prop_key]


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_mechanics(builtins: dict) -> None:
    """将机械领域内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（mathlib 之后）。
    命名规则：
      - 运动学：前缀 运动_
      - 材料力学：前缀 材料_ / 前缀 梁_ / 前缀 轴_
      - 材料常量：材质_E / 材质_G / 材质_s（屈服）/ 材质_b（强度）/ 材质_rho / 材质_nu
    """
    # --- 运动学 ---
    builtins["运动_匀速位移"] = _curry2(_匀速_位移)
    builtins["运动_匀速速度"] = _curry2(_匀速_速度)
    builtins["运动_匀速时间"] = _curry2(_匀速_时间)
    builtins["运动_匀变速位移"] = _curry3(_匀变速_位移)
    builtins["运动_匀变速末速度"] = _curry3(_匀变速_末速度)
    builtins["运动_匀变速位移由速度"] = _curry3(_匀变速_位移由速度)
    builtins["运动_自由落体位移"] = _curry2(_自由落体_位移)
    builtins["运动_自由落体末速度"] = _curry2(_自由落体_末速度)
    builtins["运动_平抛落地时间"] = _curry2(_平抛_落地时间)
    builtins["运动_平抛射程"] = _curry3(_平抛_射程)
    builtins["运动_斜抛射程"] = _curry3(_斜抛_射程)
    builtins["运动_斜抛最大高度"] = _curry3(_斜抛_最大高度)
    builtins["运动_斜抛飞行时间"] = _curry3(_斜抛_飞行时间)
    builtins["运动_圆周线速度"] = _curry2(_圆周_线速度)
    builtins["运动_圆周角速度"] = _圆周_角速度
    builtins["运动_向心加速度v"] = _curry2(_圆周_向心加速度_v)
    builtins["运动_向心加速度w"] = _curry2(_圆周_向心加速度_w)
    builtins["运动_圆周周期"] = _curry2(_圆周_周期)

    # --- 材料力学：轴向拉压 ---
    builtins["材料_应力"] = _curry2(_拉压_应力)                # 材料_应力(F)(A)
    builtins["材料_应变"] = _curry2(_拉压_应变)                # 材料_应变(ΔL)(L)
    builtins["材料_胡克"] = _curry2(_拉压_胡克)                # 材料_胡克(E)(ε)
    builtins["材料_变形"] = _curry4(_拉压_变形)                # 材料_变形(F)(L)(E)(A)
    builtins["材料_安全系数"] = _curry2(_安全系数)             # 材料_安全系数(σ_s)(σ)

    # --- 材料力学：剪切 ---
    builtins["材料_剪应力"] = _curry2(_剪切_剪应力)
    builtins["材料_剪应变"] = _curry2(_剪切_剪应变)
    builtins["材料_剪切胡克"] = _curry2(_剪切_胡克)

    # --- 材料力学：梁弯曲 ---
    builtins["梁_矩形惯性矩"] = _curry2(_截面_矩形惯性矩)      # 梁_矩形惯性矩(b)(h)
    builtins["梁_圆形惯性矩"] = _截面_圆形惯性矩
    builtins["梁_圆环惯性矩"] = _curry2(_截面_圆环惯性矩)
    builtins["梁_弯曲正应力"] = _curry3(_弯曲_正应力)          # 梁_弯曲正应力(M)(y)(I)
    builtins["梁_弯曲最大正应力"] = _curry3(_弯曲_最大正应力)
    builtins["梁_圆形抗弯模量"] = _抗弯截面模量_圆形
    builtins["梁_矩形抗弯模量"] = _curry2(_抗弯截面模量_矩形)

    # --- 材料力学：圆轴扭转 ---
    builtins["轴_实心极惯性矩"] = _扭转_极惯性矩
    builtins["轴_空心极惯性矩"] = _curry2(_扭转_空心极惯性矩)
    builtins["轴_扭转剪应力"] = _curry3(_扭转_剪应力)          # 轴_扭转剪应力(T)(r)(Ip)
    builtins["轴_扭转最大剪应力"] = _curry3(_扭转_最大剪应力)
    builtins["轴_扭转角"] = _curry4(_扭转_扭转角)              # 轴_扭转角(T)(L)(G)(Ip)

    # --- 材料常量（直接值，非 callable）---
    for mat_name, props in MATERIALS.items():
        # mat_name 形如 "钢_Q235"，注册为：钢_Q235_E / 钢_Q235_G / ...
        for prop_key, val in props.items():
            const_name = f"{mat_name}_{prop_key}"
            builtins[const_name] = val

    # --- 材料属性查询函数（按名称读取）---
    def _材料_E(name): return MATERIALS[name]["E"]
    def _材料_G(name): return MATERIALS[name]["G"]
    def _材料_屈服(name): return MATERIALS[name]["σ_s"]
    def _材料_强度(name): return MATERIALS[name]["σ_b"]
    def _材料_密度(name): return MATERIALS[name]["ρ"]
    def _材料_泊松(name): return MATERIALS[name]["ν"]
    builtins["材料_E"] = _材料_E
    builtins["材料_G"] = _材料_G
    builtins["材料_屈服"] = _材料_屈服
    builtins["材料_强度"] = _材料_强度
    builtins["材料_密度"] = _材料_密度
    builtins["材料_泊松"] = _材料_泊松


def _mechanics_symtab_names() -> list[str]:
    """返回机械领域所有内建名（用于语义分析注册，避免报未定义）。"""
    names: list[str] = []
    # 运动学
    for n in ["匀速位移","匀速速度","匀速时间",
              "匀变速位移","匀变速末速度","匀变速位移由速度",
              "自由落体位移","自由落体末速度",
              "平抛落地时间","平抛射程",
              "斜抛射程","斜抛最大高度","斜抛飞行时间",
              "圆周线速度","圆周角速度",
              "向心加速度v","向心加速度w","圆周周期"]:
        names.append(f"运动_{n}")
    # 材料力学
    for n in ["应力","应变","胡克","变形","安全系数",
              "剪应力","剪应变","剪切胡克",
              "E","G","屈服","强度","密度","泊松"]:
        names.append(f"材料_{n}")
    for n in ["矩形惯性矩","圆形惯性矩","圆环惯性矩",
              "弯曲正应力","弯曲最大正应力",
              "圆形抗弯模量","矩形抗弯模量"]:
        names.append(f"梁_{n}")
    for n in ["实心极惯性矩","空心极惯性矩",
              "扭转剪应力","扭转最大剪应力","扭转角"]:
        names.append(f"轴_{n}")
    # 材料常量
    for mat_name, props in MATERIALS.items():
        for prop_key in props:
            names.append(f"{mat_name}_{prop_key}")
    return names
