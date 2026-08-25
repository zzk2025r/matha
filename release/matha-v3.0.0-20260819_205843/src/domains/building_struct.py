"""Matha 领域扩展模块：建筑结构工程（Building Structural Engineering）。

基于 Matha 数学基础与 structural.py（结构力学）+ architecture.py（建筑学）+ mechanics.py，
演化建筑结构设计子领域功能。所有函数以普通 Python callable 注册到解释器 builtins。

五大子领域（与 structural.py 结构力学互补，聚焦规范设计与构件验算）：

一、混凝土结构（Concrete Structures）- 前缀 混凝_
  1) 单筋矩形梁受弯承载力 M = α1·fc·b·x·(h0-0.4x) / 简化 Mu = 0.9·fy·As·h0
  2) 相对受压区高度 ξ = x/h0 = (fy·As)/(α1·fc·b·h0)
  3) 最小配筋率 ρmin = max(0.2%, 0.45·ft/fy)
  4) 最大配筋率 ρmax = ξb·fc/fy
  5) 界限相对受压区高度 ξb（按钢筋级别）
  6) 偏心受压构件偏心距增大系数 η = 1+ζ1·ζ2·(l0/h)²
  7) T 形截面翼缘有效宽度 bf'
  8) 受剪承载力 V = 0.7·ft·b·h0 + 1.25·fyv·Asv·h0/s
  9) 轴心受压承载力 N = 0.9·φ·(fc·A + fy·As')
  10) 裂缝宽度验算 wmax = αcr·ψ·σsk/Es·(1.9c+0.08·deq/ρte)

二、钢结构（Steel Structures）- 前缀 钢结_
  1) 抗弯强度 σ = M/(γx·Wn) ≤ f
  2) 抗剪强度 τ = V·S/(I·tw) ≤ fv
  3) 整体稳定 φb（典型值）
  4) 轴心受压稳定系数 φ（按 λ 查表近似）
  5) 局部稳定宽厚比限值
  6) 焊缝计算长度 lw = N/(he·ffw)
  7) 螺栓抗剪承载力 Nb = ns·πd²/4 · fv_b
  8) 螺栓抗拉承载力 Nt = πd²/4 · ft_b
  9) 高强螺栓摩擦型承载力 Nv = μ·nf·P
  10) 长细比 λ = l0/i

三、砌体结构（Masonry Structures）- 前缀 砌体_
  1) 抗压承载力 N ≤ φ·f·A
  2) 局压承载力 N ≤ γ·f·Al
  3) 局压强度提高系数 γ = 1 + 0.35·√(Al/Aln)
  4) 高厚比 β = H0/h
  5) 允许高厚比 [β]（按砂浆等级）
  6) 墙柱稳定性判定
  7) 受剪承载力 V ≤ (fv + 0.18σ0)·A
  8) 网状配筋砌体抗压强度提高系数

四、木结构（Timber Structures）- 前缀 木结_
  1) 顺纹抗压承载力 N = fc·An
  2) 抗弯承载力 M = fm·Wn
  3) 顺纹抗剪承载力 V = fv·b·I/S
  4) 齿连接承压承载力
  5) 螺栓连接承载力（单剪/双剪）
  6) 木构件稳定系数 φ（按 λ）
  7) 长细比 λ = l0/i

五、地基与基础（Foundation）- 前缀 基础_
  1) 地基承载力修正 f = fak + ηb·γ·(b-3) + ηd·γm·(d-0.5)
  2) 中心受压基础底面积 A ≥ N/(f - γm·d)
  3) 偏心受压基础底面积（初步）
  4) 基底附加应力 p0 = p - γm·d
  5) 集中力布辛奈斯克解 σz = 3P/(2π)·z³/R⁵
  6) 分层总和法沉降（单层）s = σz·H/Es
  7) 单桩承载力 Q = up·Σqsik·li + qpk·Ap
  8) 桩基承台冲切承载力

六、抗震设计（Seismic Design）- 前缀 抗震_
  1) 水平地震作用 F = α·G（底部剪力法等效）
  2) 地震影响系数 α（按烈度与场地特征周期查表）
  3) 重力荷载代表值 G = 恒载 + 0.5·活载
  4) 楼层最小地震剪力 λ·G
  5) 轴压比 μ = N/(fc·A) 限值判定
  6) 剪跨比 λ = M/(V·h0)
  7) 抗震等级调整系数（按烈度/结构类型）
  8) 弹性层间位移角限值 θe
  9) 弹塑性层间位移角限值 θp

数据库：
  - 混凝土强度等级（fc/ft/ftk/Ec，C15-C80）
  - 钢筋强度等级（HPB300/HRB400/HRB500 的 fy/fyk/Es）
  - 钢材强度等级（Q235/Q345/Q390/Q420 的 f/fv/E）
  - 砌体抗压强度（按砖与砂浆等级组合查 GB 50003）
  - 砂浆等级允许高厚比
  - 木材强度等级（TC/TB 系列）
  - 地基承载力修正系数 ηb/ηd
  - 桩侧/桩端阻力参考值
  - 地震影响系数最大值（按烈度 6-9 度）

设计原则：
  - 与 structural / architecture / mechanics 保持一致：_curryN 柯里化、前缀区分
  - 函数返回纯数值或字符串/元组，不做语义包装
  - 除零 / 非法参数由 Python 自身抛错
  - 公式基于中国规范 GB 50010/50017/50003/50005/50007/50011
"""

from __future__ import annotations
import math


# ========== 柯里化工具 ==========

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

# 混凝土强度等级（轴心抗压 fc / 轴心抗拉 ft / 立方体抗压 fck / 弹性模量 Ec，MPa）
# GB 50010 设计值（按规范常用值简化）
CONCRETE_GRADE: dict[str, dict[str, float]] = {
    "C15":  {"fc": 7.2,  "ft": 0.91, "fck": 10.0,  "Ec": 22000},
    "C20":  {"fc": 9.6,  "ft": 1.10, "fck": 13.4,  "Ec": 25500},
    "C25":  {"fc": 11.9, "ft": 1.27, "fck": 16.7,  "Ec": 28000},
    "C30":  {"fc": 14.3, "ft": 1.43, "fck": 20.1,  "Ec": 30000},
    "C35":  {"fc": 16.7, "ft": 1.57, "fck": 23.4,  "Ec": 31500},
    "C40":  {"fc": 19.1, "ft": 1.71, "fck": 26.8,  "Ec": 32500},
    "C45":  {"fc": 21.1, "ft": 1.80, "fck": 29.6,  "Ec": 33500},
    "C50":  {"fc": 23.1, "ft": 1.89, "fck": 32.4,  "Ec": 34500},
    "C55":  {"fc": 25.3, "ft": 1.96, "fck": 35.5,  "Ec": 35500},
    "C60":  {"fc": 27.5, "ft": 2.04, "fck": 38.5,  "Ec": 36000},
    "C70":  {"fc": 31.8, "ft": 2.14, "fck": 44.5,  "Ec": 37000},
    "C80":  {"fc": 35.9, "ft": 2.22, "fck": 50.2,  "Ec": 38000},
}

# 钢筋强度等级（屈服 fy / 标准值 fyk / 弹性模量 Es，MPa）
REBAR_GRADE: dict[str, dict[str, float]] = {
    "HPB300":  {"fy": 270, "fyk": 300, "Es": 210000},
    "HRB400":  {"fy": 360, "fyk": 400, "Es": 200000},
    "HRB500":  {"fy": 435, "fyk": 500, "Es": 200000},
    "HRBF400": {"fy": 360, "fyk": 400, "Es": 200000},
    "HRBF500": {"fy": 435, "fyk": 500, "Es": 200000},
    "RRB400":  {"fy": 360, "fyk": 400, "Es": 200000},
}

# 界限相对受压区高度 ξb（按钢筋级别，C50 及以下）
REBAR_XI_B: dict[str, float] = {
    "HPB300": 0.576,
    "HRB400": 0.518,
    "HRB500": 0.482,
    "HRBF400": 0.518,
    "HRBF500": 0.482,
    "RRB400": 0.499,
}

# 结构钢材强度等级（抗拉/抗压/抗弯 f / 抗剪 fv / 弹性模量 E，MPa）
# GB 50017 设计值
STEEL_GRADE: dict[str, dict[str, float]] = {
    "Q235": {"f": 215, "fv": 125, "E": 206000},
    "Q345": {"f": 310, "fv": 180, "E": 206000},
    "Q390": {"f": 350, "fv": 205, "E": 206000},
    "Q420": {"f": 380, "fv": 220, "E": 206000},
}

# 砌体抗压强度设计值 f（MPa），按砖等级 MU 与砂浆等级 M 组合查 GB 50003 表 3.2.1-1
# 简化：用拟合公式 f = 0.78·√(砖·砂浆)/4.5（与 architecture.py 一致）
# 这里用数据库保存典型组合
MASONRY_STRENGTH: dict[str, dict[str, float]] = {
    "MU10": {"M5": 1.50, "M7.5": 1.69, "M10": 1.89},
    "MU15": {"M5": 1.83, "M7.5": 2.07, "M10": 2.31},
    "MU20": {"M5": 2.12, "M7.5": 2.39, "M10": 2.67},
    "MU25": {"M5": 2.37, "M7.5": 2.67, "M10": 2.98},
    "MU30": {"M5": 2.59, "M7.5": 2.92, "M10": 3.26},
}

# 砂浆等级对应允许高厚比 [β]（墙，无门窗洞口）
ALLOW_SLENDERNESS: dict[str, float] = {
    "M2.5": 22.0, "M5": 24.0, "M7.5": 26.0, "M10": 26.0, "M15": 26.0,
}

# 木材强度等级（抗弯 fm / 顺纹抗压 fc / 顺纹抗拉 ft / 顺纹抗剪 fv，MPa）
# GB 50005 设计值
TIMBER_GRADE_STR: dict[str, dict[str, float]] = {
    "TC17": {"fm": 17, "fc": 16, "ft": 10, "fv": 1.7},
    "TC15": {"fm": 15, "fc": 14, "ft": 9.0, "fv": 1.6},
    "TC13": {"fm": 13, "fc": 12, "ft": 8.5, "fv": 1.5},
    "TC11": {"fm": 11, "fc": 10, "ft": 7.5, "fv": 1.4},
    "TB20": {"fm": 20, "fc": 18, "ft": 12, "fv": 2.0},
    "TB17": {"fm": 17, "fc": 16, "ft": 11, "fv": 1.8},
    "TB15": {"fm": 15, "fc": 14, "ft": 9.5, "fv": 1.6},
}

# 地基承载力修正系数 ηb（宽）与 ηd（深），按土类
SOIL_MOD_COEFF: dict[str, dict[str, float]] = {
    "中砂_粗砂":     {"eta_b": 3.0, "eta_d": 4.4},
    "粉砂_细砂":     {"eta_b": 2.0, "eta_d": 3.0},
    "粉土":           {"eta_b": 0.5, "eta_d": 2.2},
    "粘性土_孔隙<0.85": {"eta_b": 0.3, "eta_d": 1.6},
    "粘性土_孔隙>0.85": {"eta_b": 0.0, "eta_d": 1.0},
    "人工填土":       {"eta_b": 0.0, "eta_d": 1.0},
}

# 桩侧/桩端阻力参考值（kPa，按土类典型值）
PILE_RESISTANCE: dict[str, dict[str, float]] = {
    "粘性土_软塑": {"qsik": 25, "qpk": 400},
    "粘性土_可塑": {"qsik": 65, "qpk": 1200},
    "粉土":          {"qsik": 50, "qpk": 1000},
    "粉砂":          {"qsik": 60, "qpk": 1500},
    "中砂":          {"qsik": 75, "qpk": 2500},
    "粗砂":          {"qsik": 95, "qpk": 3500},
}

# 地震影响系数最大值 αmax（按烈度，多遇/罕遇）
SEISMIC_ALPHA_MAX: dict[str, dict[str, float]] = {
    "6度":  {"多遇": 0.04, "罕遇": 0.28},
    "7度":  {"多遇": 0.08, "罕遇": 0.50},
    "8度":  {"多遇": 0.16, "罕遇": 0.90},
    "9度":  {"多遇": 0.32, "罕遇": 1.40},
}


# ========== 常量 ==========

ALPHA1_C50 = 1.0      # 矩形应力图系数 α1（C50 及以下）
ALPHA1_C80 = 0.94
GAMMA_X = 1.05         # 截面塑性发展系数（一般梁）
GAMMA_X_SHEAR = 1.20   # 剪切塑性发展系数
SEISMIC_LOAD_FACTOR = 1.0   # 重力荷载代表值系数
G_CONCRETE = 25.0      # 钢筋混凝土重度 kN/m³
G_STEEL = 78.5         # 钢材重度 kN/m³
G_MASONRY = 19.0       # 砌体重度 kN/m³
G_TIMBER = 5.0         # 木材重度 kN/m³
G_SOIL = 20.0          # 一般土重度 kN/m³


# ========== 一、混凝土结构 ==========

def _混凝_受弯承载力简化(fy, As, h0):
    """单筋矩形梁受弯承载力简化：Mu = 0.9·fy·As·h0（kN·m，按规范简化估算）。"""
    return 0.9 * fy * As * h0 / 1e6   # fy(MPa)·As(mm²)·h0(mm) → N·mm → /1e6 kN·m


def _混凝_相对受压区高度(fy, As, fc, b, h0):
    """ξ = x/h0 = (fy·As)/(α1·fc·b·h0)，α1=1.0（C50 及以下）。"""
    denom = ALPHA1_C50 * fc * b * h0
    if denom == 0:
        return 0.0
    return fy * As / denom


def _混凝_最小配筋率(ft, fy):
    """ρmin = max(0.2%, 0.45·ft/fy)。返回比值（非百分比）。"""
    return max(0.002, 0.45 * ft / fy)


def _混凝_最大配筋率(xi_b, fc, fy):
    """ρmax = ξb·fc/fy（单筋矩形截面最大配筋率）。"""
    if fy == 0:
        return 0.0
    return xi_b * fc / fy


def _混凝_界限相对受压区高度(rebar_grade):
    """ξb 按钢筋级别查表（C50 及以下）。"""
    return REBAR_XI_B.get(rebar_grade, 0.518)


def _混凝_偏心距增大系数(l0, h, zeta1=1.0, zeta2=1.0):
    """η = 1 + ζ1·ζ2·(l0/h)² / 1400·e0/h（简化默认 e0=h/2，分母=1400·0.5=700）。
    此处输入 l0, h, ζ1, ζ2 → η = 1 + ζ1·ζ2·(l0/h)²/1400。"""
    if h == 0:
        return 1.0
    return 1.0 + zeta1 * zeta2 * (l0 / h) ** 2 / 1400.0


def _混凝_T形翼缘宽度(b, hf, l0):
    """T 形截面翼缘有效宽度 bf' 简化：min(b + 12·hf, l0/3, b + S_n)。
    返回 min(b + 12·hf, l0/3)（无横肋情况）。"""
    return min(b + 12 * hf, l0 / 3)


def _混凝_受剪承载力(ft, b, h0, fyv, Asv, s):
    """V = 0.7·ft·b·h0 + 1.25·fyv·Asv·h0/s（kN，GB 50010 简化）。"""
    v = 0.7 * ft * b * h0 + 1.25 * fyv * Asv * h0 / s
    return v / 1000.0   # N → kN


def _混凝_轴压承载力(fc, A, fy, As_prime, phi=0.9):
    """N = 0.9·φ·(fc·A + fy·As')（kN）。"""
    return phi * (fc * A + fy * As_prime) / 1000.0


def _混凝_裂缝宽度(alpha_cr, psi, sigma_sk, Es, c, deq, rho_te):
    """wmax = αcr·ψ·σsk/Es·(1.9c + 0.08·deq/ρte)（mm，GB 50007 公式）。"""
    if rho_te == 0 or Es == 0:
        return 0.0
    return alpha_cr * psi * sigma_sk / Es * (1.9 * c + 0.08 * deq / rho_te)


# ========== 二、钢结构 ==========

def _钢结_抗弯强度(M, gamma_x, Wn):
    """σ = M/(γx·Wn) ≤ f（MPa）。M 单位 kN·m，Wn 单位 cm³ → 转换。"""
    if Wn == 0:
        return 0.0
    return M * 1e6 / (gamma_x * Wn * 1e3)  # kN·m → N·mm, cm³ → mm³


def _钢结_抗剪强度(V, S, I, tw):
    """τ = V·S/(I·tw) ≤ fv（MPa）。V 单位 kN，S/I 单位 mm → 转换。"""
    if I == 0 or tw == 0:
        return 0.0
    return V * 1e3 * S / (I * tw)


def _钢结_整体稳定系数(lambda_b):
    """梁整体稳定系数 φb 简化估算（λb 简化长细比）：
    λb ≤ 0.6 → 1.0；> 0.6 → 用 1.07 - λb²/4400 折减。"""
    if lambda_b <= 0.6:
        return 1.0
    return max(0.0, 1.07 - lambda_b * lambda_b / 4400.0)


def _钢结_轴压稳定系数(slenderness):
    """轴心受压稳定系数 φ 按长细比 λ 查 a 类截面近似公式：
    λ ≤ 0.215 → φ = 1 - α·λ²；> 0.215 → φ = (1+ε+λ²)/(2λ²)·[1-√(1-(2+ε+λ²)/(λ²·(1+ε+λ²))²)]。
    简化：λ ≤ 60 → 0.9; 60-120 → 0.9 - (λ-60)/600; > 120 → 0.8 - (λ-120)/800。"""
    if slenderness <= 60:
        return 0.9
    if slenderness <= 120:
        return 0.9 - (slenderness - 60) / 600.0
    return max(0.1, 0.8 - (slenderness - 120) / 800.0)


def _钢结_宽厚比限值(level="一般"):
    """局部稳定宽厚比限值。level: 一般/严格。"""
    table = {"一般": 15.0, "严格": 9.0, "塑性设计": 8.0}
    return table.get(level, 15.0)


def _钢结_焊缝计算长度(N, he, ffw):
    """角焊缝计算长度 lw = N/(he·ffw·0.7)（mm，正面角焊缝强度增大系数 βf=1.22 已忽略）。"""
    if he == 0 or ffw == 0:
        return 0.0
    return N / (he * ffw)


def _钢结_螺栓抗剪承载力(ns, d, fv_b):
    """单个普通螺栓抗剪承载力 Nb = ns·πd²/4·fv_b（kN）。"""
    return ns * math.pi * d * d / 4 * fv_b / 1000.0


def _钢结_螺栓抗拉承载力(d, ft_b):
    """单个普通螺栓抗拉承载力 Nt = πd²/4·ft_b（kN）。"""
    return math.pi * d * d / 4 * ft_b / 1000.0


def _钢结_高强螺栓摩擦型承载力(mu, nf, P):
    """单个高强螺栓摩擦型抗剪 Nv = μ·nf·P / 1.0（kN，承载力设计值）。"""
    return mu * nf * P


def _钢结_长细比(l0, i):
    """λ = l0/i。"""
    if i == 0:
        return float("inf")
    return l0 / i


# ========== 三、砌体结构 ==========

def _砌体_抗压承载力(phi, f, A):
    """N ≤ φ·f·A（kN）。f MPa, A mm²。"""
    return phi * f * A / 1000.0


def _砌体_局压承载力(gamma, f, Al):
    """Nl ≤ γ·f·Al（kN）。"""
    return gamma * f * Al / 1000.0


def _砌体_局压提高系数(Al, Aln):
    """γ = 1 + 0.35·√(Al/Aln)，≤ 3。"""
    if Aln == 0:
        return 1.0
    return min(3.0, 1.0 + 0.35 * math.sqrt(Al / Aln))


def _砌体_高厚比(H0, h):
    """β = H0/h（计算高厚比）。"""
    if h == 0:
        return float("inf")
    return H0 / h


def _砌体_允许高厚比(mortar_grade):
    """[β] 按砂浆等级查表（无门窗洞口墙）。"""
    return ALLOW_SLENDERNESS.get(mortar_grade, 24.0)


def _砌体_稳定性判定(H0, h, mortar_grade):
    """墙柱稳定性判定：β ≤ [β]。返回 (是否稳定, β, [β])。"""
    beta = _砌体_高厚比(H0, h)
    beta_max = _砌体_允许高厚比(mortar_grade)
    return (beta <= beta_max, beta, beta_max)


def _砌体_受剪承载力(fv, sigma0, A):
    """V ≤ (fv + 0.18·σ0)·A（kN，GB 50003）。"""
    return (fv + 0.18 * sigma0) * A / 1000.0


def _砌体_网状配筋提高系数(rho_s, fyv):
    """网状配筋砌体抗压强度提高系数 Δf ≈ 2·ρ·fyv/100（简化估算，MPa）。"""
    return 2.0 * rho_s * fyv / 100.0


# ========== 四、木结构 ==========

def _木结_顺纹抗压承载力(fc, An):
    """N = fc·An（kN）。fc MPa, An mm²。"""
    return fc * An / 1000.0


def _木结_抗弯承载力(fm, Wn):
    """M = fm·Wn（kN·m）。fm MPa, Wn mm³。"""
    return fm * Wn / 1e6


def _木结_顺纹抗剪承载力(fv, b, I, S):
    """V = fv·b·I/S（kN）。"""
    if S == 0:
        return 0.0
    return fv * b * I / S / 1000.0


def _木结_齿连接承压(fc_alpha, Ac):
    """齿连接承压承载力 N = fc_α·Ac（kN）。"""
    return fc_alpha * Ac / 1000.0


def _木结_螺栓连接承载力(fv_bolt, a, d):
    """木结构螺栓单剪承载力 Nv = kv·d²·√a/10（简化估算，kN）。
    fv_bolt 为螺栓钢材抗剪（MPa），a 为板厚 mm，d 为直径 mm。"""
    return fv_bolt * d * d * math.sqrt(a) / 1e5


def _木结_稳定系数(slenderness):
    """木构件稳定系数 φ（按长细比）：
    λ ≤ 75 → φ = 1 - (λ/100)²；> 75 → φ = 3000/λ²。"""
    if slenderness <= 0:
        return 1.0
    if slenderness <= 75:
        return 1.0 - (slenderness / 100.0) ** 2
    return min(1.0, 3000.0 / (slenderness ** 2))


def _木结_长细比(l0, i):
    """λ = l0/i（与钢结构公式一致）。"""
    if i == 0:
        return float("inf")
    return l0 / i


# ========== 五、地基与基础 ==========

def _基础_承载力修正(fak, eta_b, gamma, b, eta_d, gamma_m, d):
    """地基承载力修正 f = fak + ηb·γ·(b-3) + ηd·γm·(d-0.5)（kPa）。
    b<3 取 3；b>6 取 6；d<0.5 取 0.5。"""
    b_use = max(3.0, min(6.0, b))
    d_use = max(0.5, d)
    return fak + eta_b * gamma * (b_use - 3.0) + eta_d * gamma_m * (d_use - 0.5)


def _基础_中心受压面积(N, f, gamma_m, d):
    """中心受压基础底面积 A ≥ N/(f - γm·d)（m²）。"""
    denom = f - gamma_m * d
    if denom <= 0:
        return float("inf")
    return N / denom


def _基础_附加应力(p, gamma_m, d):
    """基底附加应力 p0 = p - γm·d（kPa）。"""
    return p - gamma_m * d


def _基础_Boussinesq应力(P, z, R=None):
    """集中力 P 在深度 z 处的附加应力 σz = 3P/(2π)·z³/R⁵（kPa）。
    若未给 R（计算点到 P 的距离），用 z 计算（即 R=z，正下方）。"""
    if R is None:
        R = z
    if R == 0:
        return 0.0
    return 3.0 * P / (2 * math.pi) * z ** 3 / R ** 5


def _基础_分层沉降(sigma_z, H, Es):
    """单层压缩量 s = σz·H/Es（mm）。sigma_z kPa, H m, Es MPa。"""
    if Es == 0:
        return float("inf")
    return sigma_z * H / Es


def _基础_单桩承载力(up, qsik_list, li_list, qpk, Ap):
    """单桩竖向承载力 Q = up·Σqsik·li + qpk·Ap（kN）。
    up 周长 m，qsik_list 侧阻力 kPa 列表，li_list 段长 m 列表，qpk 端阻 kPa，Ap 截面积 m²。"""
    if len(qsik_list) != len(li_list):
        return 0.0
    side = up * sum(q * l for q, l in zip(qsik_list, li_list))
    tip = qpk * Ap
    return side + tip


def _基础_承台冲切承载力(ft, h0, um):
    """承台冲切承载力 F = 0.7·ft·h0·um（kN）。ft MPa, h0 mm, um mm。"""
    return 0.7 * ft * h0 * um / 1000.0


# ========== 六、抗震设计 ==========

def _抗震_水平地震作用(alpha, G):
    """F = α·G（kN，底部剪力法等效单质点）。"""
    return alpha * G


def _抗震_地震影响系数(intensity, level="多遇"):
    """αmax 按烈度与水准查表（直接返回 αmax，Tg/α 需按场地与周期进一步计算）。"""
    return SEISMIC_ALPHA_MAX.get(intensity, {}).get(level, 0.08)


def _抗震_重力荷载代表值(dead_load, live_load, live_factor=0.5):
    """G = 恒载 + ψ·活载（ψ 通常 0.5）。"""
    return dead_load + live_factor * live_load


def _抗震_楼层最小剪力(lambda_factor, G):
    """Vmin = λ·G（kN）。"""
    return lambda_factor * G


def _抗震_轴压比(N, fc, A):
    """μ = N/(fc·A)（无量纲）。N kN, fc MPa, A mm²。"""
    if fc == 0 or A == 0:
        return 0.0
    return N * 1000 / (fc * A)


def _抗震_轴压比判定(N, fc, A, limit=0.5):
    """轴压比限值判定，返回 (是否满足, μ, 限值)。"""
    mu = _抗震_轴压比(N, fc, A)
    return (mu <= limit, mu, limit)


def _抗震_剪跨比(M, V, h0):
    """λ = M/(V·h0)（无量纲）。"""
    if V == 0 or h0 == 0:
        return float("inf")
    return M / (V * h0)


def _抗震_抗震等级调整系数(structure_type, intensity):
    """按结构类型与烈度返回抗震等级调整系数（简化，1/2/3/4 级 → 1.0/0.8/0.75/0.7）。"""
    table = {
        ("框架", 6): 4, ("框架", 7): 3, ("框架", 8): 2, ("框架", 9): 1,
        ("剪力墙", 6): 4, ("剪力墙", 7): 3, ("剪力墙", 8): 2, ("剪力墙", 9): 1,
        ("框架-剪力墙", 6): 4, ("框架-剪力墙", 7): 3, ("框架-剪力墙", 8): 2, ("框架-剪力墙", 9): 1,
    }
    grade = table.get((structure_type, intensity), 3)
    coeffs = {1: 1.0, 2: 0.8, 3: 0.75, 4: 0.7}
    return coeffs.get(grade, 0.75)


def _抗震_弹性层间位移角限值(structure_type):
    """弹性层间位移角限值 [θe]（GB 50011）。"""
    table = {
        "框架": 1/550.0,
        "框架-剪力墙": 1/800.0,
        "剪力墙": 1/1000.0,
        "筒中筒": 1/1000.0,
        "板柱-剪力墙": 1/800.0,
    }
    return table.get(structure_type, 1/800.0)


def _抗震_弹塑性层间位移角限值(structure_type):
    """弹塑性层间位移角限值 [θp]（GB 50011）。"""
    table = {
        "框架": 1/50.0,
        "框架-剪力墙": 1/100.0,
        "剪力墙": 1/120.0,
        "筒中筒": 1/120.0,
    }
    return table.get(structure_type, 1/100.0)


# ========== 注册 ==========

def _register_building_struct(builtins: dict) -> None:
    """将建筑结构工程子领域内建注册到解释器 builtins。"""

    # ===== 一、混凝土结构 =====
    builtins["混凝_受弯承载力简化"] = _curry3(_混凝_受弯承载力简化)
    builtins["混凝_相对受压区高度"] = _curry5(_混凝_相对受压区高度)
    builtins["混凝_最小配筋率"] = _curry2(_混凝_最小配筋率)
    builtins["混凝_最大配筋率"] = _curry3(_混凝_最大配筋率)
    builtins["混凝_界限相对受压区高度"] = _混凝_界限相对受压区高度
    builtins["混凝_偏心距增大系数"] = _curry2(_混凝_偏心距增大系数)
    builtins["混凝_T形翼缘宽度"] = _curry3(_混凝_T形翼缘宽度)
    builtins["混凝_受剪承载力"] = _curry6(_混凝_受剪承载力)
    builtins["混凝_轴压承载力"] = _curry4(_混凝_轴压承载力)
    builtins["混凝_裂缝宽度"] = _curry7(_混凝_裂缝宽度)

    # ===== 二、钢结构 =====
    builtins["钢结_抗弯强度"] = _curry3(_钢结_抗弯强度)
    builtins["钢结_抗剪强度"] = _curry4(_钢结_抗剪强度)
    builtins["钢结_整体稳定系数"] = _钢结_整体稳定系数
    builtins["钢结_轴压稳定系数"] = _钢结_轴压稳定系数
    builtins["钢结_宽厚比限值"] = _钢结_宽厚比限值
    builtins["钢结_焊缝计算长度"] = _curry3(_钢结_焊缝计算长度)
    builtins["钢结_螺栓抗剪承载力"] = _curry3(_钢结_螺栓抗剪承载力)
    builtins["钢结_螺栓抗拉承载力"] = _curry2(_钢结_螺栓抗拉承载力)
    builtins["钢结_高强螺栓摩擦型承载力"] = _curry3(_钢结_高强螺栓摩擦型承载力)
    builtins["钢结_长细比"] = _curry2(_钢结_长细比)

    # ===== 三、砌体结构 =====
    builtins["砌体_抗压承载力"] = _curry3(_砌体_抗压承载力)
    builtins["砌体_局压承载力"] = _curry3(_砌体_局压承载力)
    builtins["砌体_局压提高系数"] = _curry2(_砌体_局压提高系数)
    builtins["砌体_高厚比"] = _curry2(_砌体_高厚比)
    builtins["砌体_允许高厚比"] = _砌体_允许高厚比
    builtins["砌体_稳定性判定"] = _curry3(_砌体_稳定性判定)
    builtins["砌体_受剪承载力"] = _curry3(_砌体_受剪承载力)
    builtins["砌体_网状配筋提高系数"] = _curry2(_砌体_网状配筋提高系数)

    # ===== 四、木结构 =====
    builtins["木结_顺纹抗压承载力"] = _curry2(_木结_顺纹抗压承载力)
    builtins["木结_抗弯承载力"] = _curry2(_木结_抗弯承载力)
    builtins["木结_顺纹抗剪承载力"] = _curry4(_木结_顺纹抗剪承载力)
    builtins["木结_齿连接承压承载力"] = _curry2(_木结_齿连接承压)
    builtins["木结_螺栓连接承载力"] = _curry3(_木结_螺栓连接承载力)
    builtins["木结_稳定系数"] = _木结_稳定系数
    builtins["木结_长细比"] = _curry2(_木结_长细比)

    # ===== 五、地基与基础 =====
    builtins["基础_承载力修正"] = _curry7(_基础_承载力修正)
    builtins["基础_中心受压面积"] = _curry4(_基础_中心受压面积)
    builtins["基础_附加应力"] = _curry3(_基础_附加应力)
    builtins["基础_Boussinesq应力"] = _curry2(_基础_Boussinesq应力)
    builtins["基础_分层沉降"] = _curry3(_基础_分层沉降)
    builtins["基础_单桩承载力"] = _curry5(_基础_单桩承载力)
    builtins["基础_承台冲切承载力"] = _curry3(_基础_承台冲切承载力)

    # ===== 六、抗震设计 =====
    builtins["抗震_水平地震作用"] = _curry2(_抗震_水平地震作用)
    builtins["抗震_地震影响系数"] = _curry2(_抗震_地震影响系数)
    builtins["抗震_重力荷载代表值"] = _curry2(_抗震_重力荷载代表值)
    builtins["抗震_楼层最小剪力"] = _curry2(_抗震_楼层最小剪力)
    builtins["抗震_轴压比"] = _curry3(_抗震_轴压比)
    builtins["抗震_轴压比判定"] = _curry4(_抗震_轴压比判定)
    builtins["抗震_剪跨比"] = _curry3(_抗震_剪跨比)
    builtins["抗震_抗震等级调整系数"] = _curry2(_抗震_抗震等级调整系数)
    builtins["抗震_弹性层间位移角限值"] = _抗震_弹性层间位移角限值
    builtins["抗震_弹塑性层间位移角限值"] = _抗震_弹塑性层间位移角限值

    # ===== 数据库：混凝土等级 =====
    for grade, spec in CONCRETE_GRADE.items():
        for k, v in spec.items():
            builtins[f"混凝土_{grade}_{k}"] = v

    # ===== 数据库：钢筋等级 =====
    for grade, spec in REBAR_GRADE.items():
        for k, v in spec.items():
            builtins[f"钢筋_{grade}_{k}"] = v
    for grade, v in REBAR_XI_B.items():
        builtins[f"钢筋_{grade}_ξb"] = v

    # ===== 数据库：钢材等级 =====
    for grade, spec in STEEL_GRADE.items():
        for k, v in spec.items():
            builtins[f"钢材_{grade}_{k}"] = v

    # ===== 数据库：砌体抗压 =====
    for brick, mortar_dict in MASONRY_STRENGTH.items():
        for mortar, val in mortar_dict.items():
            builtins[f"砌体强度_{brick}_{mortar}"] = val

    # ===== 数据库：允许高厚比 =====
    for k, v in ALLOW_SLENDERNESS.items():
        builtins[f"允许高厚比_{k}"] = v

    # ===== 数据库：木材等级 =====
    for grade, spec in TIMBER_GRADE_STR.items():
        for k, v in spec.items():
            builtins[f"木材_{grade}_{k}"] = v

    # ===== 数据库：地基修正系数 =====
    for soil, spec in SOIL_MOD_COEFF.items():
        builtins[f"地基修正_{soil}_ηb"] = spec["eta_b"]
        builtins[f"地基修正_{soil}_ηd"] = spec["eta_d"]

    # ===== 数据库：桩阻力 =====
    for soil, spec in PILE_RESISTANCE.items():
        builtins[f"桩阻力_{soil}_qsik"] = spec["qsik"]
        builtins[f"桩阻力_{soil}_qpk"] = spec["qpk"]

    # ===== 数据库：地震影响系数 =====
    for intensity, spec in SEISMIC_ALPHA_MAX.items():
        builtins[f"地震影响_{intensity}_多遇"] = spec["多遇"]
        builtins[f"地震影响_{intensity}_罕遇"] = spec["罕遇"]

    # ===== 常量 =====
    builtins["建结_α1_C50"] = ALPHA1_C50
    builtins["建结_塑性发展系数"] = GAMMA_X
    builtins["建结_混凝土重度"] = G_CONCRETE
    builtins["建结_钢材重度"] = G_STEEL
    builtins["建结_砌体重度"] = G_MASONRY
    builtins["建结_木材重度"] = G_TIMBER
    builtins["建结_土重度"] = G_SOIL


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

def _building_struct_symtab_names() -> list[str]:
    names: list[str] = []

    # 一、混凝土结构
    for n in ["受弯承载力简化", "相对受压区高度", "最小配筋率", "最大配筋率",
              "界限相对受压区高度", "偏心距增大系数", "T形翼缘宽度",
              "受剪承载力", "轴压承载力", "裂缝宽度"]:
        names.append(f"混凝_{n}")

    # 二、钢结构
    for n in ["抗弯强度", "抗剪强度", "整体稳定系数", "轴压稳定系数",
              "宽厚比限值", "焊缝计算长度", "螺栓抗剪承载力",
              "螺栓抗拉承载力", "高强螺栓摩擦型承载力", "长细比"]:
        names.append(f"钢结_{n}")

    # 三、砌体结构
    for n in ["抗压承载力", "局压承载力", "局压提高系数", "高厚比",
              "允许高厚比", "稳定性判定", "受剪承载力", "网状配筋提高系数"]:
        names.append(f"砌体_{n}")

    # 四、木结构
    for n in ["顺纹抗压承载力", "抗弯承载力", "顺纹抗剪承载力",
              "齿连接承压承载力", "螺栓连接承载力", "稳定系数", "长细比"]:
        names.append(f"木结_{n}")

    # 五、地基与基础
    for n in ["承载力修正", "中心受压面积", "附加应力", "Boussinesq应力",
              "分层沉降", "单桩承载力", "承台冲切承载力"]:
        names.append(f"基础_{n}")

    # 六、抗震设计
    for n in ["水平地震作用", "地震影响系数", "重力荷载代表值", "楼层最小剪力",
              "轴压比", "轴压比判定", "剪跨比", "抗震等级调整系数",
              "弹性层间位移角限值", "弹塑性层间位移角限值"]:
        names.append(f"抗震_{n}")

    # 数据库：混凝土
    for grade in CONCRETE_GRADE:
        for k in CONCRETE_GRADE[grade]:
            names.append(f"混凝土_{grade}_{k}")

    # 数据库：钢筋
    for grade in REBAR_GRADE:
        for k in REBAR_GRADE[grade]:
            names.append(f"钢筋_{grade}_{k}")
    for grade in REBAR_XI_B:
        names.append(f"钢筋_{grade}_ξb")

    # 数据库：钢材
    for grade in STEEL_GRADE:
        for k in STEEL_GRADE[grade]:
            names.append(f"钢材_{grade}_{k}")

    # 数据库：砌体强度
    for brick in MASONRY_STRENGTH:
        for mortar in MASONRY_STRENGTH[brick]:
            names.append(f"砌体强度_{brick}_{mortar}")

    # 数据库：允许高厚比
    for k in ALLOW_SLENDERNESS:
        names.append(f"允许高厚比_{k}")

    # 数据库：木材等级
    for grade in TIMBER_GRADE_STR:
        for k in TIMBER_GRADE_STR[grade]:
            names.append(f"木材_{grade}_{k}")

    # 数据库：地基修正
    for soil in SOIL_MOD_COEFF:
        names.append(f"地基修正_{soil}_ηb")
        names.append(f"地基修正_{soil}_ηd")

    # 数据库：桩阻力
    for soil in PILE_RESISTANCE:
        names.append(f"桩阻力_{soil}_qsik")
        names.append(f"桩阻力_{soil}_qpk")

    # 数据库：地震影响
    for intensity in SEISMIC_ALPHA_MAX:
        names.append(f"地震影响_{intensity}_多遇")
        names.append(f"地震影响_{intensity}_罕遇")

    # 常量
    for n in ["建结_α1_C50", "建结_塑性发展系数", "建结_混凝土重度",
              "建结_钢材重度", "建结_砌体重度", "建结_木材重度", "建结_土重度"]:
        names.append(n)

    return names
