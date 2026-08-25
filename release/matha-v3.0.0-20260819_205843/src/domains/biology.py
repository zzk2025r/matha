"""Matha 机械领域扩展模块：生物学（Biology）。

基于 Matha 数学基础与物理常量体系，演化生物学子领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、分子生物学（Molecular Biology）- 前缀 分子_
  1) 碱基互补配对规则（A↔T/U, C↔G）
  2) DNA 转录成 mRNA（T→U，反向读取简化保留顺序）
  3) DNA 互补链生成（5\'-3\' 写出互补）
  4) GC 含量计算（GC 比例）
  5) 熔解温度 Tm（Wallace 公式简化：T=2(A+T)+4(G+C) °C，或 近邻近似本模块用简化版）
  6) DNA/RNA 摩尔质量估算（每个核苷酸残基平均 ~325 Da（单链 DNA）/330（RNA），双链 ×2）
  7) PCR 扩增倍数：2^n（n 循环数）
  8) 质量 → 摩尔数：moles = mass / M（bp 数 × 650 Da 双链）
  9) 密码子查找（单个密码子查表返回单字母 AA / * 表示终止）
  10) mRNA 翻译（从起始 AUG 开始按三联体翻译成蛋白质序列）

二、细胞生物学（Cell Biology）- 前缀 细胞_
  1) 球体细胞体积：V = 4πr³/3
  2) 球体表面积：S = 4πr²
  3) 表面积/体积比 S/V（新陈代谢 / 物质交换判据）
  4) 倍增时间：t_d = ln2 / k（k 生长速率常数 1/s）
  5) 生长速率常数：k = ln2 / t_d
  6) 指数生长后细胞数：N = N0·exp(k·t) = N0·2^(t/t_d)
  7) 一维扩散特征时间：t ≈ x² / (2D)（D 扩散系数 m²/s）
  8) 细胞膜总电容估算：C_total = Cm·A，Cm≈1μF/cm²
  9) 倍增代数：n = log2(N/N0)

三、生物化学（Biochemistry）- 前缀 生化_
  1) 米氏方程：v = Vmax·[S] / (Km + [S])
  2) Lineweaver-Burk 双倒数：1/v = (Km/Vmax)(1/[S]) + 1/Vmax
  3) Henderson-Hasselbalch：pH = pKa + log([A⁻]/[HA])
  4) 缓冲容量 β = 2.303·C·Ka·[H⁺] / (Ka + [H⁺])²（C 总浓度）
  5) 能斯特方程（298K 常温）：E = E° + (0.05916/z)·log([Ox]/[Red]) 或用 RT/zF
  6) Arrhenius 方程：k = A·exp(-Ea/(RT))
  7) Hill 方程（协同性）：θ = [L]^n / (Kd^n + [L]^n) 或 (1 + Kd^n/[L]^n)⁻¹
  8) 竞争性抑制表观 Km：Km_app = Km·(1 + [I]/Ki)
  9) 非竞争性抑制表观 Vmax：Vmax_app = Vmax/(1 + [I]/Ki)

四、生理学与种群生态学（Physiology & Population）- 前缀 生理_ / 种群_
  1) BMI 指数：kg/m²
  2) 心脏输出量 CO = HR（次/分）× SV（每搏量 mL）
  3) 肺泡通气量 VA = (TV - VD) × f（每分钟）
  4) 动脉血氧含量：CaO2 = 1.34·Hb·SaO2 + 0.003·PaO2（mL O2/100mL 血）
  5) 基础代谢率（Mifflin-St Jeor）：男 10m+6.25h-5a+5；女 10m+6.25h-5a-161
  6) 种群指数增长：N(t) = N0·exp(r·t)
  7) 种群倍增时间：t_d = ln2/r
  8) 逻辑斯蒂增长：N(t) = K / (1 + (K/N0 - 1)·exp(-r·t))
  9) 世代净繁殖率 R0 与内禀增长率关系：r ≈ ln(R0)/T（T 世代时间）

五、微生物与免疫（Microbiology & Immunology）- 前缀 微生_ / 免疫_
  1) CFU 每毫升：CFU/mL = 平板计数 × 稀释倍数 / 接种体积 mL
  2) 杀菌对数减少值 LR = log10(N0/N)
  3) D 值（90% 杀死所需时间 / 温度）：D → N = N0·10^(-t/D)
  4) Z 值（使 D 值变化 10 倍的温度变化）：log10(D1/D2)=(T2-T1)/z
  5) 世代时间 g：由 N=N0·2^(t/g) → g = t / log2(N/N0)
  6) MOI（感染复数）：噬菌体 / 细菌颗粒数
  7) 杀菌存活率：S = N/N0 = 10^(-LR)
  8) 抗体效价估算（血清稀释几何平均）
  9) OD600 估算大肠杆菌浓度：个/mL ≈ 1 OD600 × 8e8

数据库：
  - 标准遗传密码表（64 个密码子 → 单字母氨基酸，终止 *）
  - 20 种氨基酸残基分子量（Da，精确到 2 位小数）
  - 4 种 dNTP 分子量 & 4 种 NTP 分子量（合成用）
  - 生理/生物物理常量（法拉第常数 F、摩尔气体 R、体温 K=310.15、25℃=298.15K、Cm 膜电容 1 μF/cm² 等）

设计原则：
  - 与 fluid_exp / statmech 保持一致：_curryN 柯里化、前缀区分
  - 函数返回纯数值或字符串，不做语义包装
  - 除零 / 非法序列由 Python 自身抛错
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


# ========== 数据库：遗传密码表（标准密码子表） ==========
# 单字母氨基酸表示，终止密码用 "*"
CODON_TABLE: dict[str, str] = {}
_codon_bases = ("U", "C", "A", "G")
_aa_map = {
    "Phe": "F", "Leu": "L", "Ile": "I", "Met": "M", "Val": "V",
    "Ser": "S", "Pro": "P", "Thr": "T", "Ala": "A", "Tyr": "Y",
    "His": "H", "Gln": "Q", "Asn": "N", "Lys": "K", "Asp": "D",
    "Glu": "E", "Cys": "C", "Trp": "W", "Arg": "R", "Gly": "G",
    "Ter": "*",
}
# 按标准遗传密码规则手工填入
_standard = {
    "UUU": "F", "UUC": "F", "UUA": "L", "UUG": "L",
    "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",
    "UAU": "Y", "UAC": "Y", "UAA": "*", "UAG": "*",
    "UGU": "C", "UGC": "C", "UGA": "*", "UGG": "W",

    "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",
    "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAU": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",

    "AUU": "I", "AUC": "I", "AUA": "I", "AUG": "M",
    "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAU": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGU": "S", "AGC": "S", "AGA": "R", "AGG": "R",

    "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",
    "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAU": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}
CODON_TABLE = _standard

# 20 种 L-氨基酸残基分子量（脱水缩合残基质量，Da ≈ g/mol）
# 数据来自标准氨基酸表（残基 = 游离 - 18 H2O）
AA_MASS_DA: dict[str, float] = {
    "A":  71.08, "R": 156.19, "N": 114.10, "D": 115.09,
    "C": 103.14, "E": 129.12, "Q": 128.13, "G":  57.05,
    "H": 137.14, "I": 113.16, "L": 113.16, "K": 128.17,
    "M": 131.20, "F": 147.18, "P":  97.12, "S":  87.08,
    "T": 101.10, "W": 186.21, "Y": 163.18, "V":  99.13,
}

# 三字母 → 单字母
AA_THREE_TO_ONE: dict[str, str] = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
}

# 脱氧核苷酸残基分子量（dsDNA 一对平均约 650 Da ≡ 617.96 + H2O ... 这里给精确单链残基）
DNTP_MASS_DA: dict[str, float] = {
    "dA": 313.21, "dT": 304.20, "dC": 289.18, "dG": 329.21,
}
NTP_MASS_DA: dict[str, float] = {
    "A": 329.21, "U": 306.17, "C": 305.18, "G": 345.21,
}

# ========== 生物物理常量 ==========
R_GAS_SI = 8.314462618       # J/(mol·K) = Pa·m³/(mol·K)
R_GAS_MM = 0.082057          # L·atm/(mol·K)
F_FARADAY = 96485.33212      # C/mol（法拉第常数）
AVOGADRO = 6.02214076e23     # mol⁻¹
T_BODY_K = 310.15            # 37°C（体温 K）
T_ROOM_K = 298.15            # 25°C（室温 K）
T_0C_K = 273.15              # 0°C
MEMBRANE_CM_uF = 1.0         # 典型细胞膜比电容 μF/cm²

# DNA/RNA 典型数值（估算用）
DSDNA_BP_MASS_DA = 650.0     # 每对脱氧核苷酸残基平均 Da（双链 bp 质量）
SSDNA_NT_MASS_DA = 325.0     # 单链 DNA 每 nt 平均 Da
SSRNA_NT_MASS_DA = 330.0     # RNA 每 nt 平均 Da
ECOLI_CELL_MASS_pg = 1.0     # 大肠杆菌典型湿重 pg（近似）

# ========== 一、分子生物学 ==========

_BASE_COMPL_DNA = {"A": "T", "T": "A", "C": "G", "G": "C", "a": "t", "t": "a", "c": "g", "g": "c"}
_BASE_COMPL_RNA = {"A": "U", "T": "A", "U": "A", "C": "G", "G": "C", "a": "u", "t": "a", "u": "a", "c": "g", "g": "c"}


def _分子_DNA互补链(seq):
    """返回 DNA 互补链（同方向 5'-3'：互补后反转）。"""
    tab = _BASE_COMPL_DNA
    # 互补
    comp = "".join(tab.get(ch, ch) for ch in seq)
    # 3'-5' → 5'-3' 反转
    return comp[::-1]


def _分子_DNA转录(seq):
    """DNA 模板链 → mRNA（T→U，保留顺序，互补反义做了反转后再取 T→U）。
    这里简单实现：输入编码链（5'-3'），直接 T→U 即 mRNA。"""
    return seq.replace("T", "U").replace("t", "u")


def _分子_GC含量(seq):
    """返回 GC 碱基比例 (0~1)。"""
    if not seq:
        return 0.0
    s = seq.upper()
    gc = sum(1 for ch in s if ch in ("G", "C"))
    return gc / len(s)


def _分子_Tm_Wallace(seq):
    """Wallace 公式：Tm(°C) = 2(A+T) + 4(G+C)（≤20 bp 探针近似）。"""
    s = seq.upper()
    at = sum(1 for ch in s if ch in ("A", "T", "U"))
    gc = sum(1 for ch in s if ch in ("G", "C"))
    return 2 * at + 4 * gc


def _分子_dsDNA质量(bp):
    """双链 DNA 质量 Da ≈ bp × 650 Da/bp。"""
    return bp * DSDNA_BP_MASS_DA


def _分子_ssDNA质量(nt): return nt * SSDNA_NT_MASS_DA
def _分子_ssRNA质量(nt): return nt * SSRNA_NT_MASS_DA


def _分子_PCR扩增(n_cycle): return 2 ** n_cycle  # 理论值（100% 效率）


def _分子_PCR扩增效率(n_cycle, eff):
    """实际扩增倍数：(1+eff)^n，eff∈[0,1]。"""
    return (1.0 + eff) ** n_cycle


def _分子_质量转摩尔(mass_g, M_Da):
    """摩尔数 mol = mass_g / (M_Da × g/mol 当量)。Da 单位即 g/mol，直接除。"""
    return mass_g / M_Da


def _分子_密码子查找(codon):
    """传入 3 字母密码子（U 为 RNA 形式），返回单字母 AA 或 *。"""
    if len(codon) != 3:
        return ""
    key = codon.upper().replace("T", "U")
    return CODON_TABLE.get(key, "")


def _分子_mRNA翻译(mRNA, from_start=True):
    """从 mRNA 翻译为蛋白质序列（单字母，终止符 *）。
    from_start=True 则从第一个 AUG 开始按 3 读数；否则从头。"""
    if not mRNA:
        return ""
    s = mRNA.upper().replace("T", "U")
    start = s.find("AUG") if from_start else 0
    if start < 0:
        return ""
    out = []
    for j in range(start, len(s) - 2, 3):
        aa = CODON_TABLE.get(s[j:j+3], "")
        if aa == "*":
            break
        if aa:
            out.append(aa)
    return "".join(out)


def _分子_蛋白分子量(seq):
    """按单字母序列计算残基分子量（Da，不含水和修饰）。"""
    return sum(AA_MASS_DA.get(ch, 0.0) for ch in seq.upper())


def _分子_等电点简化():  # 占位（完整 pI 需要 pKa 表；返回 0）
    return 0.0


# ========== 二、细胞生物学 ==========

def _细胞_球体体积(r): return 4.0 / 3.0 * math.pi * (r ** 3)  # m³
def _细胞_球体表面积(r): return 4.0 * math.pi * (r ** 2)
def _细胞_表面积体积比(r):
    if r <= 0:
        return float("inf")
    return 3.0 / r  # 球体 S/V = 3/r


def _细胞_生长速率(t_d):
    """k = ln2 / t_d，t_d 与 k 时间单位一致（1/时间）。"""
    return math.log(2) / t_d if t_d > 0 else float("inf")


def _细胞_倍增时间(k): return math.log(2) / k if k > 0 else float("inf")


def _细胞_指数生长(N0, k, t): return N0 * math.exp(k * t)


def _细胞_倍增代数(N0, N):
    """从 N0 到 N 共经历几代倍增：n = log2(N/N0)。"""
    if N0 <= 0 or N <= 0:
        return 0.0
    return math.log2(N / N0)


def _细胞_特征扩散时间(x, D):
    """x 特征距离（m），D 扩散系数 m²/s → t(s) ≈ x²/(2D)。"""
    if D <= 0:
        return float("inf")
    return x * x / (2.0 * D)


def _细胞_膜电容(A_cm2):
    """细胞膜总电容（μF）：典型 Cm=1 μF/cm² × 面积 cm²。"""
    return MEMBRANE_CM_uF * A_cm2


def _细胞_椭球体积(a, b, c): return 4.0 / 3.0 * math.pi * a * b * c  # 三半轴


# ========== 三、生物化学 ==========

def _生化_米氏方程(Vmax, Km, S):
    """v = Vmax·[S] / (Km + [S])。"""
    return Vmax * S / (Km + S) if (Km + S) > 0 else 0.0


def _生化_Lineweaver斜率(Vmax, Km): return Km / Vmax
def _生化_Lineweaver截距(Vmax): return 1.0 / Vmax if Vmax > 0 else float("inf")


def _生化_HH(pKa, ratio_Aminus_over_HA):
    """Henderson-Hasselbalch：pH = pKa + log([A⁻]/[HA])。"""
    if ratio_Aminus_over_HA <= 0:
        return float("-inf")
    return pKa + math.log10(ratio_Aminus_over_HA)


def _生化_缓冲容量(C, Ka, pH):
    """β = 2.303·C·Ka·[H⁺]/(Ka+[H⁺])²；[H⁺] = 10^-pH。"""
    H = 10 ** (-pH)
    d = Ka + H
    return 2.303 * C * Ka * H / (d * d)


def _生化_能斯特(E0, z, ratio_Ox_Red, T_K):
    """E = E° + (RT/zF)·ln(Ox/Red)。"""
    return E0 + (R_GAS_SI * T_K / (z * F_FARADAY)) * math.log(max(ratio_Ox_Red, 1e-300))


def _生化_阿伦尼乌斯(A_pre, Ea_Jmol, T_K):
    """k = A·exp(-Ea/(RT))。"""
    return A_pre * math.exp(-Ea_Jmol / (R_GAS_SI * T_K))


def _生化_Hill方程(n_Hill, Kd, L):
    """θ = [L]^n / (Kd^n + [L]^n)。"""
    if Kd <= 0:
        return 0.0
    return (L ** n_Hill) / (Kd ** n_Hill + L ** n_Hill)


def _生化_竞争抑制Km(Km, I, Ki):
    """Km_app = Km·(1 + [I]/Ki)。"""
    return Km * (1.0 + I / Ki) if Ki > 0 else float("inf")


def _生化_非竞争抑制Vmax(Vmax, I, Ki):
    """Vmax_app = Vmax/(1 + [I]/Ki)。"""
    return Vmax / (1.0 + I / Ki) if Ki > 0 else 0.0


# ========== 四、生理学与种群生态学 ==========

def _生理_BMI(kg, m):
    """体重指数 kg/m²。"""
    if m <= 0:
        return 0.0
    return kg / (m * m)


def _生理_心输出量(HR_bpm, SV_mL):
    """CO = HR × SV（mL/min）。"""
    return HR_bpm * SV_mL


def _生理_肺泡通气量(TV_mL, VD_mL, f_bpm):
    """VA = (TV - VD) × f（mL/min）。"""
    return (TV_mL - VD_mL) * f_bpm


def _生理_血氧含量(Hb_g_dL, SaO2, PaO2_mmHg):
    """CaO2 = 1.34·Hb·SaO2 + 0.003·PaO2（mL O2/100mL 血）。"""
    return 1.34 * Hb_g_dL * SaO2 + 0.003 * PaO2_mmHg


def _生理_基础代谢(m_kg, h_cm, age, is_male):
    """Mifflin-St Jeor：男 10m + 6.25h - 5a + 5；女 同 -161。单位 kcal/日。"""
    base = 10.0 * m_kg + 6.25 * h_cm - 5.0 * age
    return base + (5.0 if is_male else -161.0)


def _种群_指数增长(N0, r, t): return N0 * math.exp(r * t)


def _种群_倍增时间(r): return math.log(2) / r if r > 0 else float("inf")


def _种群_逻辑斯蒂(N0, r, K, t):
    """N(t) = K / (1 + (K/N0 - 1)·exp(-rt))。"""
    if K <= 0:
        return N0
    denom = 1.0 + (K / N0 - 1.0) * math.exp(-r * t)
    return K / denom if denom > 0 else 0.0


def _种群_内禀增长率(R0, T_generation):
    """r ≈ ln(R0)/T（离散世代近似）。"""
    if R0 <= 0 or T_generation <= 0:
        return 0.0
    return math.log(R0) / T_generation


def _种群_世代总数(r, t): return math.exp(r * t)  # 简化（相对比例）


# ========== 五、微生物与免疫 ==========

def _微生_CFU(plate_count, dilution_factor, volume_mL):
    """CFU/mL = plate_count × dilution_factor / volume_mL。"""
    if volume_mL <= 0:
        return 0.0
    return plate_count * dilution_factor / volume_mL


def _微生_对数减少(N0, N):
    """LR = log10(N0/N)。"""
    if N0 <= 0 or N <= 0:
        return 0.0
    return math.log10(N0 / N)


def _微生_杀菌存活率(LR):
    """S = N/N0 = 10^(-LR)。"""
    return 10 ** (-LR)


def _微生_D值存活(N0, t_min, D_min):
    """N = N0·10^(-t/D)。"""
    return N0 * (10 ** (-t_min / D_min)) if D_min > 0 else N0


def _微生_Z值(logD_ratio, delta_T):
    """由 log(D1/D2) = (T2-T1)/z → z = ΔT / log(D1/D2)。"""
    if abs(logD_ratio) < 1e-30:
        return float("inf")
    return delta_T / logD_ratio


def _微生_世代时间(N0, N, t_h):
    """g = t / log2(N/N0)。"""
    if N0 <= 0 or N <= N0:
        return float("inf")
    return t_h / math.log2(N / N0)


def _微生_MOI(phage_count, host_count):
    """感染复数 = 噬菌体颗粒 / 宿主细菌数。"""
    if host_count <= 0:
        return float("inf")
    return phage_count / host_count


def _微生_OD600转细胞数(OD600):
    """经验：大肠杆菌 OD600=1 ≈ 8e8 CFU/mL。"""
    return OD600 * 8.0e8


def _免疫_效价稀释(initial_dilution, titer_positive):
    """简化：titer = 初始稀释倍数 × 终点阳性管几何平均。返回单一 positive 稀释下倒数。"""
    if titer_positive <= 0:
        return 0.0
    return initial_dilution * titer_positive


# ========== 注册到解释器 builtins ==========

def _register_biology(builtins: dict) -> None:
    """将生物学子领域内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（fluid_exp 之后、statmech 之前或之后任意位置）。
    """

    # ===== 一、分子生物学 =====
    builtins["分子_DNA互补链"] = _分子_DNA互补链
    builtins["分子_DNA转录"] = _分子_DNA转录
    builtins["分子_GC含量"] = _分子_GC含量
    builtins["分子_Tm_Wallace"] = _分子_Tm_Wallace
    builtins["分子_dsDNA质量"] = _分子_dsDNA质量
    builtins["分子_ssDNA质量"] = _分子_ssDNA质量
    builtins["分子_ssRNA质量"] = _分子_ssRNA质量
    builtins["分子_PCR扩增"] = _分子_PCR扩增
    builtins["分子_PCR扩增效率"] = _curry2(_分子_PCR扩增效率)
    builtins["分子_质量转摩尔"] = _curry2(_分子_质量转摩尔)
    builtins["分子_密码子查找"] = _分子_密码子查找
    builtins["分子_mRNA翻译"] = _curry2(_分子_mRNA翻译) if False else _分子_mRNA翻译  # 单参版本 1 个调用
    builtins["分子_蛋白分子量"] = _分子_蛋白分子量

    # ===== 二、细胞生物学 =====
    builtins["细胞_球体体积"] = _细胞_球体体积
    builtins["细胞_球体表面积"] = _细胞_球体表面积
    builtins["细胞_表面积体积比"] = _细胞_表面积体积比
    builtins["细胞_生长速率"] = _细胞_生长速率
    builtins["细胞_倍增时间"] = _细胞_倍增时间
    builtins["细胞_指数生长"] = _curry3(_细胞_指数生长)
    builtins["细胞_倍增代数"] = _curry2(_细胞_倍增代数)
    builtins["细胞_特征扩散时间"] = _curry2(_细胞_特征扩散时间)
    builtins["细胞_膜电容"] = _细胞_膜电容
    builtins["细胞_椭球体积"] = _curry3(_细胞_椭球体积)

    # ===== 三、生物化学 =====
    builtins["生化_米氏方程"] = _curry3(_生化_米氏方程)
    builtins["生化_Lineweaver斜率"] = _curry2(_生化_Lineweaver斜率)
    builtins["生化_Lineweaver截距"] = _生化_Lineweaver截距
    builtins["生化_HH"] = _curry2(_生化_HH)
    builtins["生化_缓冲容量"] = _curry3(_生化_缓冲容量)
    builtins["生化_能斯特"] = _curry4(_生化_能斯特)
    builtins["生化_阿伦尼乌斯"] = _curry3(_生化_阿伦尼乌斯)
    builtins["生化_Hill方程"] = _curry3(_生化_Hill方程)
    builtins["生化_竞争抑制Km"] = _curry3(_生化_竞争抑制Km)
    builtins["生化_非竞争抑制Vmax"] = _curry3(_生化_非竞争抑制Vmax)

    # ===== 四、生理学与种群 =====
    builtins["生理_BMI"] = _curry2(_生理_BMI)
    builtins["生理_心输出量"] = _curry2(_生理_心输出量)
    builtins["生理_肺泡通气量"] = _curry3(_生理_肺泡通气量)
    builtins["生理_血氧含量"] = _curry3(_生理_血氧含量)
    builtins["生理_基础代谢"] = _curry4(_生理_基础代谢)
    builtins["种群_指数增长"] = _curry3(_种群_指数增长)
    builtins["种群_倍增时间"] = _种群_倍增时间
    builtins["种群_逻辑斯蒂"] = _curry4(_种群_逻辑斯蒂)
    builtins["种群_内禀增长率"] = _curry2(_种群_内禀增长率)

    # ===== 五、微生物与免疫 =====
    builtins["微生_CFU"] = _curry3(_微生_CFU)
    builtins["微生_对数减少"] = _curry2(_微生_对数减少)
    builtins["微生_杀菌存活率"] = _微生_杀菌存活率
    builtins["微生_D值存活"] = _curry3(_微生_D值存活)
    builtins["微生_Z值"] = _curry2(_微生_Z值)
    builtins["微生_世代时间"] = _curry3(_微生_世代时间)
    builtins["微生_MOI"] = _curry2(_微生_MOI)
    builtins["微生_OD600转细胞数"] = _微生_OD600转细胞数
    builtins["免疫_效价稀释"] = _curry2(_免疫_效价稀释)

    # ===== 数据库 =====
    for c, aa in CODON_TABLE.items():
        builtins[f"密码子_{c}"] = aa
    for one, mass in AA_MASS_DA.items():
        builtins[f"AA质量_{one}"] = mass
    for three, one in AA_THREE_TO_ONE.items():
        builtins[f"AA三转一_{three}"] = one
    for k, v in DNTP_MASS_DA.items():
        builtins[f"dNTP质量_{k}"] = v
    for k, v in NTP_MASS_DA.items():
        builtins[f"NTP质量_{k}"] = v

    # ===== 生物物理常量 =====
    builtins["R_气体SI"] = R_GAS_SI
    builtins["R_气体MM"] = R_GAS_MM
    builtins["F_法拉第"] = F_FARADAY
    builtins["NA_阿伏伽德罗2"] = AVOGADRO
    builtins["T_体温K"] = T_BODY_K
    builtins["T_室温K"] = T_ROOM_K
    builtins["T_0C_K"] = T_0C_K
    builtins["Cm_膜电容"] = MEMBRANE_CM_uF
    builtins["BP_dsDNA质量"] = DSDNA_BP_MASS_DA
    builtins["NT_ssDNA质量"] = SSDNA_NT_MASS_DA
    builtins["NT_ssRNA质量"] = SSRNA_NT_MASS_DA
    builtins["ECOLI湿重_pg"] = ECOLI_CELL_MASS_pg


# ========== 语义符号表 ==========

def _biology_symtab_names() -> list[str]:
    names: list[str] = []

    for n in ["DNA互补链", "DNA转录", "GC含量", "Tm_Wallace",
              "dsDNA质量", "ssDNA质量", "ssRNA质量",
              "PCR扩增", "PCR扩增效率", "质量转摩尔",
              "密码子查找", "mRNA翻译", "蛋白分子量"]:
        names.append(f"分子_{n}")

    for n in ["球体体积", "球体表面积", "表面积体积比",
              "生长速率", "倍增时间", "指数生长", "倍增代数",
              "特征扩散时间", "膜电容", "椭球体积"]:
        names.append(f"细胞_{n}")

    for n in ["米氏方程", "Lineweaver斜率", "Lineweaver截距", "HH",
              "缓冲容量", "能斯特", "阿伦尼乌斯", "Hill方程",
              "竞争抑制Km", "非竞争抑制Vmax"]:
        names.append(f"生化_{n}")

    for n in ["BMI", "心输出量", "肺泡通气量", "血氧含量", "基础代谢"]:
        names.append(f"生理_{n}")
    for n in ["指数增长", "倍增时间", "逻辑斯蒂", "内禀增长率"]:
        names.append(f"种群_{n}")

    for n in ["CFU", "对数减少", "杀菌存活率", "D值存活", "Z值",
              "世代时间", "MOI", "OD600转细胞数"]:
        names.append(f"微生_{n}")
    for n in ["效价稀释"]:
        names.append(f"免疫_{n}")

    # 数据库：密码子
    for c in CODON_TABLE:
        names.append(f"密码子_{c}")
    # 数据库：AA 质量 & 三转一
    for one in AA_MASS_DA:
        names.append(f"AA质量_{one}")
    for three in AA_THREE_TO_ONE:
        names.append(f"AA三转一_{three}")
    # 数据库：dNTP/NTP 质量
    for k in DNTP_MASS_DA:
        names.append(f"dNTP质量_{k}")
    for k in NTP_MASS_DA:
        names.append(f"NTP质量_{k}")

    # 物理常量
    for n in ["R_气体SI", "R_气体MM", "F_法拉第", "NA_阿伏伽德罗2",
              "T_体温K", "T_室温K", "T_0C_K", "Cm_膜电容",
              "BP_dsDNA质量", "NT_ssDNA质量", "NT_ssRNA质量",
              "ECOLI湿重_pg"]:
        names.append(n)

    return names
