"""Matha 领域扩展模块：医疗与医药和理疗（Medical, Pharmaceutical & Physiotherapy）。

基于 Matha 数学基础与生物/物理常量体系，演化临床医学子领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、药代动力学（Pharmacokinetics）- 前缀 药代_
  1) 消除速率常数：ke = ln2 / t½
  2) 半衰期：t½ = ln2 / ke
  3) 一室模型血药浓度：C(t) = C0·exp(-ke·t)
  4) 表观分布容积：Vd = Dose / C0
  5) 清除率：CL = ke·Vd
  6) 稳态平均浓度：Css = Dose / (CL·τ)  （τ 给药间隔）
  7) 生物利用度：F = AUC_po / AUC_iv
  8) AUC 梯形法（单区间）：AUC = (c1+c2)/2 · (t2-t1)
  9) 峰浓度：Cmax = Dose·F / Vd
  10) 谷浓度：Cmin = Cmax·exp(-ke·τ)
  11) 负荷剂量：LD = Css·Vd / F

二、药效学（Pharmacodynamics）- 前缀 药效_
  1) Emax 模型：E = Emax·C / (EC50 + C)
  2) Sigmoid Emax（Hill 型）：E = Emax·C^n / (EC50^n + C^n)
  3) 治疗指数：TI = TD50 / ED50
  4) 安全范围：SR = TD1 / ED99
  5) 竞争性拮抗浓度：[I] = (dr - 1)·Ki  （dr 剂量比）
  6) 部分激动剂内在活性：α = Emax_part / Emax_full
  7) 量反应 Hill 系数：n = ln9 / ln(ED84/ED16)

三、临床检验（Clinical Laboratory）- 前缀 检验_
  1) 肌酐清除率（Cockcroft-Gault）：CCr = (140-age)·wt / (72·SCr) · (0.85 if 女)
  2) eGFR（MDRD 简化）：eGFR = 175·SCr^-1.154·age^-0.203 · (0.742 if 女) · (1.212 if 黑人)
  3) 阴离子间隙：AG = Na - (Cl + HCO3)
  4) 血浆渗透压：Osm = 2·Na + Glu/18 + BUN/2.8
  5) 平均红细胞体积 MCV = Hct(%)·10 / RBC(×10¹²/L)
  6) 平均红细胞血红蛋白 MCH = Hb(g/L)·10 / RBC
  7) 平均红细胞血红蛋白浓度 MCHC = Hb(g/L) / Hct(L/L)
  8) 白蛋白校正钙：Ca_corr = Ca + 0.8·(4 - Alb)
  9) 白蛋白校正阴离子间隙：AG_corr = AG + 2.5·(4 - Alb)
  10) 血糖校正钠：Na_corr = Na + 1.6·(Glu - 100)/100
  11) 游离水清除率：CH2O = V·(1 - Osm_u/Osm_p)
  12) 校正红细胞沉降率（年龄法）：ESR_corr = ESR - (age - 50)/2  （简化）

四、影像与放疗（Imaging & Radiotherapy）- 前缀 影像_
  1) 当量剂量：H = D·wR  （Sv）
  2) 有效剂量：E = H·wT  （Sv）
  3) 半值层：HVL = ln2 / μ
  4) 放射性活度衰变：A(t) = A0·exp(-λ·t)，λ = ln2/t½
  5) CT 值（Hounsfield）：HU = 1000·(μ - μ水)/μ水
  6) 相对生物效应 RBE ≈ 1 + LET/100（LET≤100 线性近似，>100 饱和）
  7) 生物等效剂量 BED = n·d·(1 + d/(α/β))
  8) 2Gy 等效剂量 EQD2 = total·(d + α/β)/(2 + α/β)
  9) 平方反比律：I2 = I1·(d1/d2)²
  10) 半价层衰减：剩余分数 = (1/2)^n

五、理疗与康复（Physiotherapy & Rehabilitation）- 前缀 理疗_
  1) 最大心率：HRmax = 220 - age
  2) Karvonen 心率储备：THR = (HRmax - HRrest)·intensity + HRrest
  3) METs → VO2：VO2 = 3.5·METs  (mL/kg/min)
  4) Borg 评分 → VO2max：VO2max ≈ (Borg - 4)·3.5 + 3.5（6-20 量表的简化映射）
  5) 代谢热量消耗：kcal = METs·3.5·wt(kg)·min / 200
  6) 超声强度衰减：I(d) = I0·exp(-α·d)
  7) 等长收缩力矩：τ = F·r
  8) 步态速度：v = 步长·步频
  9) 关节活动度百分比：ROM% = 当前/正常·100
  10) FIM 分级：按总分返回独立性等级字符串

数据库：
  - 常用药物半衰期库（地高辛/华法林/氨茶碱/苯妥英/锂/庆大霉素/万古霉素/对乙酰氨基酚/阿司匹林/吗啡）
  - 辐射权重因子 wR（光子/电子/中子/α/质子）
  - 组织权重因子 wT（ICRP 103：性腺/骨髓/结肠/肺/胃/乳腺/肝/食道/甲状腺/皮肤/骨表面/膀胱/唾液腺/脑/其余）
  - 常见活动 METs 表（静卧/坐/步行慢/步行快/跑步/骑车/游泳）
  - 正常检验参考值常量

设计原则：
  - 与 biology / statmech / fluid_exp 保持一致：_curryN 柯里化、前缀区分
  - 函数返回纯数值或字符串，不做语义包装
  - 除零 / 非法参数由 Python 自身抛错
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


# ========== 数据库 ==========

# 常用药物半衰期（小时，成人典型值）
DRUG_HALFLIFE_H: dict[str, float] = {
    "地高辛": 40.0,      # Digoxin
    "华法林": 40.0,      # Warfarin
    "氨茶碱": 8.0,       # Aminophylline (茶碱)
    "苯妥英": 22.0,      # Phenytoin
    "锂盐": 24.0,        # Lithium
    "庆大霉素": 2.5,     # Gentamicin
    "万古霉素": 6.0,     # Vancomycin
    "对乙酰氨基酚": 2.5, # Acetaminophen
    "阿司匹林": 0.25,    # Aspirin（水杨酸代谢更长，此处用原型）
    "吗啡": 3.0,         # Morphine
    "二甲双胍": 6.2,     # Metformin
    "阿替洛尔": 6.5,     # Atenolol
    "地西泮": 40.0,      # Diazepam
    "苯巴比妥": 90.0,    # Phenobarbital
}

# 辐射权重因子 wR（ICRP 103 简化）
W_RADIATION: dict[str, float] = {
    "光子": 1.0,    # X/γ 射线
    "电子": 1.0,    # β/电子
    "质子": 2.0,
    "中子": 2.5,    # 中子取代表值（实际 5-20 随能量变化）
    "α粒子": 20.0,
    "重离子": 20.0,
}

# 组织权重因子 wT（ICRP 103）
W_TISSUE: dict[str, float] = {
    "性腺": 0.08,
    "骨髓": 0.12,
    "结肠": 0.12,
    "肺": 0.12,
    "胃": 0.12,
    "乳腺": 0.12,
    "肝": 0.04,
    "食道": 0.04,
    "甲状腺": 0.04,
    "膀胱": 0.04,
    "皮肤": 0.01,
    "骨表面": 0.01,
    "唾液腺": 0.01,
    "脑": 0.01,
    "其余": 0.12,
}

# 常见活动 METs（代谢当量）
MET_ACTIVITY: dict[str, float] = {
    "静卧": 1.0,
    "静坐": 1.3,
    "步行慢": 3.0,     # 3.2 km/h
    "步行快": 5.0,     # 6.4 km/h
    "慢跑": 7.0,
    "跑步": 10.0,      # 10 km/h
    "骑车慢": 4.0,
    "骑车快": 8.0,
    "游泳": 8.0,
    "跳绳": 12.0,
}

# 正常检验参考值（成人）
REF_NORMAL: dict[str, float] = {
    "Na": 140.0,       # mmol/L
    "K": 4.0,
    "Cl": 102.0,
    "HCO3": 24.0,
    "Glu": 90.0,       # mg/dL
    "BUN": 14.0,       # mg/dL
    "Cr": 1.0,         # mg/dL
    "Ca": 9.5,         # mg/dL
    "Alb": 4.0,        # g/dL
    "Hb男": 150.0,     # g/L
    "Hb女": 135.0,
    "Hct男": 0.45,     # L/L
    "Hct女": 0.40,
    "RBC": 5.0,        # ×10¹²/L
    "Osm": 290.0,      # mOsm/kg
    "ESR男": 5.0,      # mm/h 上限
    "ESR女": 10.0,
}

# ========== 常量 ==========
LN2 = math.log(2.0)
# 放疗常用 α/β 比（Gy）
AB_TUMOR = 10.0      # 肿瘤/早反应组织
AB_NORMAL = 3.0      # 晚反应正常组织
AB_CNS = 2.0         # 中枢神经
# 诊断 X 线典型线性衰减系数（μ，1/cm，~60 keV 软组织近似）
MU_WATER = 0.18      # 水
MU_BONE = 0.48       # 骨
MU_LUNG = 0.05       # 肺
# 超声组织典型衰减系数（α，1/(cm·MHz)）
ALPHA_SOFT = 0.5     # 软组织
ALPHA_BONE = 20.0    # 骨


# ========== 一、药代动力学 ==========

def _药代_消除速率常数(t_half):
    """ke = ln2 / t½（t½ 单位须与 ke 一致，通常 h⁻¹）。"""
    return LN2 / t_half


def _药代_半衰期(ke):
    """t½ = ln2 / ke。"""
    return LN2 / ke


def _药代_一室浓度(C0, ke, t):
    """一室静注模型 C(t) = C0·exp(-ke·t)。"""
    return C0 * math.exp(-ke * t)


def _药代_表观分布容积(Dose, C0):
    """Vd = Dose / C0（Dose 单位与 C0 对应）。"""
    return Dose / C0


def _药代_清除率(ke, Vd):
    """CL = ke·Vd。"""
    return ke * Vd


def _药代_稳态浓度(Dose, CL, tau):
    """多次给药稳态平均浓度 Css = Dose / (CL·τ)。"""
    return Dose / (CL * tau)


def _药代_生物利用度(AUC_po, AUC_iv):
    """绝对生物利用度 F = AUC_po / AUC_iv。"""
    return AUC_po / AUC_iv


def _药代_AUC梯形(t1, c1, t2, c2):
    """单区间梯形法 AUC = (c1+c2)/2 · (t2-t1)。"""
    return (c1 + c2) / 2.0 * (t2 - t1)


def _药代_峰浓度(Dose, Vd, F):
    """Cmax = Dose·F / Vd（血管外给药达峰近似）。"""
    return Dose * F / Vd


def _药代_谷浓度(Cmax, ke, tau):
    """Cmin = Cmax·exp(-ke·τ)（稳态谷浓度）。"""
    return Cmax * math.exp(-ke * tau)


def _药代_负荷剂量(Css_target, Vd, F):
    """负荷剂量 LD = Css·Vd / F，使血药浓度迅速达到稳态。"""
    return Css_target * Vd / F


# ========== 二、药效学 ==========

def _药效_Emax模型(Emax, EC50, C):
    """Emax 模型 E = Emax·C / (EC50 + C)。"""
    denom = EC50 + C
    return Emax * C / denom if denom != 0 else 0.0


def _药效_Sigmoid_Emax(Emax, EC50, C, n):
    """Sigmoid Emax（Hill）E = Emax·C^n / (EC50^n + C^n)。"""
    if C <= 0:
        return 0.0
    Cn = C ** n
    EC50n = EC50 ** n
    denom = EC50n + Cn
    return Emax * Cn / denom if denom != 0 else 0.0


def _药效_治疗指数(TD50, ED50):
    """治疗指数 TI = TD50 / ED50。"""
    return TD50 / ED50


def _药效_安全范围(TD1, ED99):
    """安全范围 SR = TD1 / ED99。"""
    return TD1 / ED99


def _药效_竞争拮抗浓度(dr, Ki):
    """竞争性拮抗所需拮抗剂浓度 [I] = (dr - 1)·Ki。dr 为剂量比。"""
    return (dr - 1.0) * Ki


def _药效_部分激动剂活性(Emax_part, Emax_full):
    """部分激动剂内在活性 α = Emax_part / Emax_full。"""
    return Emax_part / Emax_full


def _药效_量反应斜率(ED16, ED84):
    """由 ED16/ED84 估算 Hill 系数 n = ln9 / ln(ED84/ED16)。"""
    return math.log(9.0) / math.log(ED84 / ED16) if ED84 > ED16 > 0 else 1.0


# ========== 三、临床检验 ==========

def _检验_肌酐清除率(age, weight, SCr, is_female):
    """Cockcroft-Gault：CCr = (140-age)·wt / (72·SCr) ·(0.85 if 女)。单位 mL/min。"""
    base = (140.0 - age) * weight / (72.0 * SCr)
    return base * 0.85 if is_female else base


def _检验_eGFR_MDRD(SCr, age, is_female, is_black):
    """MDRD 简化公式 eGFR = 175·SCr^-1.154·age^-0.203·(0.742 if 女)·(1.212 if 黑人)。单位 mL/min/1.73m²。"""
    val = 175.0 * (SCr ** -1.154) * (age ** -0.203)
    if is_female:
        val *= 0.742
    if is_black:
        val *= 1.212
    return val


def _检验_阴离子间隙(Na, Cl, HCO3):
    """AG = Na - (Cl + HCO3)。单位 mmol/L。"""
    return Na - (Cl + HCO3)


def _检验_渗透压(Na, Glu, BUN):
    """血浆渗透压 Osm = 2·Na + Glu/18 + BUN/2.8。Glu/BUN 单位 mg/dL。"""
    return 2.0 * Na + Glu / 18.0 + BUN / 2.8


def _检验_MCV(Hct_pct, RBC_TperL):
    """平均红细胞体积 MCV = Hct(%)·10 / RBC(×10¹²/L)。单位 fL。"""
    return Hct_pct * 10.0 / RBC_TperL


def _检验_MCH(Hb_gL, RBC_TperL):
    """平均红细胞血红蛋白 MCH = Hb(g/L) / RBC(×10¹²/L)。单位 pg。"""
    return Hb_gL / RBC_TperL


def _检验_MCHC(Hb_gL, Hct_LperL):
    """平均红细胞血红蛋白浓度 MCHC = Hb(g/L) / Hct(L/L)。单位 g/L。"""
    return Hb_gL / Hct_LperL


def _检验_校正钙(Ca, Alb):
    """白蛋白校正血钙 Ca_corr = Ca + 0.8·(4 - Alb)。单位 mg/dL。"""
    return Ca + 0.8 * (4.0 - Alb)


def _检验_白蛋白校正AG(AG, Alb):
    """白蛋白校正阴离子间隙 AG_corr = AG + 2.5·(4 - Alb)。"""
    return AG + 2.5 * (4.0 - Alb)


def _检验_Na校正血糖(Na, Glu):
    """高血糖校正血钠 Na_corr = Na + 1.6·(Glu - 100)/100。Glu 单位 mg/dL。"""
    return Na + 1.6 * (Glu - 100.0) / 100.0


def _检验_游离水清除率(V_urine, Osm_u, Osm_p):
    """游离水清除率 CH2O = V·(1 - Osm_u/Osm_p)。V 单位 mL/h。"""
    return V_urine * (1.0 - Osm_u / Osm_p)


def _检验_校正沉降率(ESR, age, is_female):
    """校正红细胞沉降率（简化年龄法）ESR_corr = ESR - (age - 50)/2（女性再加 5）。"""
    corr = ESR - (age - 50.0) / 2.0
    return corr - 5.0 if is_female else corr


# ========== 四、影像与放疗 ==========

def _影像_当量剂量(D_Gy, wR):
    """当量剂量 H = D·wR。单位 Sv。"""
    return D_Gy * wR


def _影像_有效剂量(H_Sv, wT):
    """有效剂量 E = H·wT。单位 Sv。"""
    return H_Sv * wT


def _影像_半值层(mu):
    """半值层 HVL = ln2 / μ。"""
    return LN2 / mu


def _影像_放射性活度(A0, half_life, t):
    """A(t) = A0·exp(-λ·t)，λ = ln2/t½。"""
    lam = LN2 / half_life
    return A0 * math.exp(-lam * t)


def _影像_CT值(mu, mu_water):
    """CT 值（Hounsfield）HU = 1000·(μ - μ水)/μ水。"""
    return 1000.0 * (mu - mu_water) / mu_water


def _影像_RBE(LET):
    """相对生物效应 RBE（LET≤100 线性近似 1+LET/100，>100 饱和至 2.0）。LET 单位 keV/μm。"""
    if LET <= 0:
        return 1.0
    if LET >= 100.0:
        return 2.0
    return 1.0 + LET / 100.0


def _影像_BED(n, d, alpha_beta):
    """生物等效剂量 BED = n·d·(1 + d/(α/β))。n 分次数，d 单次剂量 Gy。"""
    return n * d * (1.0 + d / alpha_beta)


def _影像_EQD2(total_dose, d, alpha_beta):
    """2Gy 等效剂量 EQD2 = total·(d + α/β)/(2 + α/β)。"""
    return total_dose * (d + alpha_beta) / (2.0 + alpha_beta)


def _影像_平方反比(I0, d1, d2):
    """平方反比律 I2 = I1·(d1/d2)²。"""
    return I0 * (d1 / d2) ** 2


def _影像_半价层衰减(n):
    """经 n 个半值层后剩余强度分数 = (1/2)^n。"""
    return 0.5 ** n


# ========== 五、理疗与康复 ==========

def _理疗_HRmax(age):
    """最大心率 HRmax = 220 - age。"""
    return 220.0 - age


def _理疗_心率储备(age, HRrest, intensity):
    """Karvonen 公式 THR = (HRmax - HRrest)·intensity + HRrest。"""
    hrmax = 220.0 - age
    return (hrmax - HRrest) * intensity + HRrest


def _理疗_METs_VO2(METs):
    """METs → VO2 = 3.5·METs（mL/kg/min）。"""
    return 3.5 * METs


def _理疗_Borg_VO2(borg):
    """Borg 6-20 量表 → VO2max 估算（简化）VO2max ≈ (Borg - 4)·3.5 + 3.5。"""
    return (borg - 4.0) * 3.5 + 3.5


def _理疗_代谢热量(METs, weight_kg, min):
    """运动热量消耗 kcal = METs·3.5·wt(kg)·min / 200。"""
    return METs * 3.5 * weight_kg * min / 200.0


def _理疗_超声衰减(I0, alpha, depth):
    """超声强度衰减 I(d) = I0·exp(-α·d)。α 单位 1/(cm·MHz)，d 单位 cm·MHz。"""
    return I0 * math.exp(-alpha * depth)


def _理疗_等长力矩(F, r):
    """等长收缩力矩 τ = F·r。F 单位 N，r 单位 m，结果 N·m。"""
    return F * r


def _理疗_步态速度(stride_length, cadence):
    """步态速度 v = 步长·步频。步长 m，步频 步/min → m/min。"""
    return stride_length * cadence


def _理疗_关节活动度(current_ROM, normal_ROM):
    """关节活动度百分比 ROM% = 当前/正常·100。"""
    return current_ROM / normal_ROM * 100.0


def _理疗_FIM分级(score):
    """FIM 总分分级（18-126）→ 独立性等级字符串。"""
    if score >= 126:
        return "完全独立"
    if score >= 108:
        return "轻度依赖"
    if score >= 90:
        return "中度依赖"
    if score >= 72:
        return "重度依赖"
    if score >= 36:
        return "极重依赖"
    return "完全依赖"


# ========== 注册 ==========

def _register_medical(builtins: dict) -> None:
    """将医疗与医药理疗子领域内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（biology 之后）。
    """

    # ===== 一、药代动力学 =====
    builtins["药代_消除速率常数"] = _药代_消除速率常数
    builtins["药代_半衰期"] = _药代_半衰期
    builtins["药代_一室浓度"] = _curry3(_药代_一室浓度)
    builtins["药代_表观分布容积"] = _curry2(_药代_表观分布容积)
    builtins["药代_清除率"] = _curry2(_药代_清除率)
    builtins["药代_稳态浓度"] = _curry3(_药代_稳态浓度)
    builtins["药代_生物利用度"] = _curry2(_药代_生物利用度)
    builtins["药代_AUC梯形"] = _curry4(_药代_AUC梯形)
    builtins["药代_峰浓度"] = _curry3(_药代_峰浓度)
    builtins["药代_谷浓度"] = _curry3(_药代_谷浓度)
    builtins["药代_负荷剂量"] = _curry3(_药代_负荷剂量)

    # ===== 二、药效学 =====
    builtins["药效_Emax模型"] = _curry3(_药效_Emax模型)
    builtins["药效_Sigmoid_Emax"] = _curry4(_药效_Sigmoid_Emax)
    builtins["药效_治疗指数"] = _curry2(_药效_治疗指数)
    builtins["药效_安全范围"] = _curry2(_药效_安全范围)
    builtins["药效_竞争拮抗浓度"] = _curry2(_药效_竞争拮抗浓度)
    builtins["药效_部分激动剂活性"] = _curry2(_药效_部分激动剂活性)
    builtins["药效_量反应斜率"] = _curry2(_药效_量反应斜率)

    # ===== 三、临床检验 =====
    builtins["检验_肌酐清除率"] = _curry4(_检验_肌酐清除率)
    builtins["检验_eGFR_MDRD"] = _curry4(_检验_eGFR_MDRD)
    builtins["检验_阴离子间隙"] = _curry3(_检验_阴离子间隙)
    builtins["检验_渗透压"] = _curry3(_检验_渗透压)
    builtins["检验_MCV"] = _curry2(_检验_MCV)
    builtins["检验_MCH"] = _curry2(_检验_MCH)
    builtins["检验_MCHC"] = _curry2(_检验_MCHC)
    builtins["检验_校正钙"] = _curry2(_检验_校正钙)
    builtins["检验_白蛋白校正AG"] = _curry2(_检验_白蛋白校正AG)
    builtins["检验_Na校正血糖"] = _curry2(_检验_Na校正血糖)
    builtins["检验_游离水清除率"] = _curry3(_检验_游离水清除率)
    builtins["检验_校正沉降率"] = _curry3(_检验_校正沉降率)

    # ===== 四、影像与放疗 =====
    builtins["影像_当量剂量"] = _curry2(_影像_当量剂量)
    builtins["影像_有效剂量"] = _curry2(_影像_有效剂量)
    builtins["影像_半值层"] = _影像_半值层
    builtins["影像_放射性活度"] = _curry3(_影像_放射性活度)
    builtins["影像_CT值"] = _curry2(_影像_CT值)
    builtins["影像_RBE"] = _影像_RBE
    builtins["影像_BED"] = _curry3(_影像_BED)
    builtins["影像_EQD2"] = _curry3(_影像_EQD2)
    builtins["影像_平方反比"] = _curry3(_影像_平方反比)
    builtins["影像_半价层衰减"] = _影像_半价层衰减

    # ===== 五、理疗与康复 =====
    builtins["理疗_HRmax"] = _理疗_HRmax
    builtins["理疗_心率储备"] = _curry3(_理疗_心率储备)
    builtins["理疗_METs_VO2"] = _理疗_METs_VO2
    builtins["理疗_Borg_VO2"] = _理疗_Borg_VO2
    builtins["理疗_代谢热量"] = _curry3(_理疗_代谢热量)
    builtins["理疗_超声衰减"] = _curry3(_理疗_超声衰减)
    builtins["理疗_等长力矩"] = _curry2(_理疗_等长力矩)
    builtins["理疗_步态速度"] = _curry2(_理疗_步态速度)
    builtins["理疗_关节活动度"] = _curry2(_理疗_关节活动度)
    builtins["理疗_FIM分级"] = _理疗_FIM分级

    # ===== 数据库：药物半衰期 =====
    for drug, th in DRUG_HALFLIFE_H.items():
        builtins[f"药物半衰期_{drug}"] = th

    # ===== 数据库：辐射权重因子 =====
    for k, v in W_RADIATION.items():
        builtins[f"辐射权重_{k}"] = v

    # ===== 数据库：组织权重因子 =====
    for k, v in W_TISSUE.items():
        builtins[f"组织权重_{k}"] = v

    # ===== 数据库：活动 METs =====
    for k, v in MET_ACTIVITY.items():
        builtins[f"METs_{k}"] = v

    # ===== 放疗 α/β 常量 =====
    builtins["ab_肿瘤"] = AB_TUMOR
    builtins["ab_正常"] = AB_NORMAL
    builtins["ab_神经"] = AB_CNS

    # ===== 诊断 X 线衰减系数 =====
    builtins["mu_水"] = MU_WATER
    builtins["mu_骨"] = MU_BONE
    builtins["mu_肺"] = MU_LUNG

    # ===== 超声衰减系数 =====
    builtins["alpha_软组织"] = ALPHA_SOFT
    builtins["alpha_骨"] = ALPHA_BONE


# ========== 语义符号表 ==========

def _medical_symtab_names() -> list[str]:
    names: list[str] = []

    for n in ["消除速率常数", "半衰期", "一室浓度", "表观分布容积", "清除率",
              "稳态浓度", "生物利用度", "AUC梯形", "峰浓度", "谷浓度", "负荷剂量"]:
        names.append(f"药代_{n}")

    for n in ["Emax模型", "Sigmoid_Emax", "治疗指数", "安全范围",
              "竞争拮抗浓度", "部分激动剂活性", "量反应斜率"]:
        names.append(f"药效_{n}")

    for n in ["肌酐清除率", "eGFR_MDRD", "阴离子间隙", "渗透压",
              "MCV", "MCH", "MCHC", "校正钙", "白蛋白校正AG",
              "Na校正血糖", "游离水清除率", "校正沉降率"]:
        names.append(f"检验_{n}")

    for n in ["当量剂量", "有效剂量", "半值层", "放射性活度", "CT值",
              "RBE", "BED", "EQD2", "平方反比", "半价层衰减"]:
        names.append(f"影像_{n}")

    for n in ["HRmax", "心率储备", "METs_VO2", "Borg_VO2", "代谢热量",
              "超声衰减", "等长力矩", "步态速度", "关节活动度", "FIM分级"]:
        names.append(f"理疗_{n}")

    # 数据库
    for drug in DRUG_HALFLIFE_H:
        names.append(f"药物半衰期_{drug}")
    for k in W_RADIATION:
        names.append(f"辐射权重_{k}")
    for k in W_TISSUE:
        names.append(f"组织权重_{k}")
    for k in MET_ACTIVITY:
        names.append(f"METs_{k}")

    # 常量
    for n in ["ab_肿瘤", "ab_正常", "ab_神经",
              "mu_水", "mu_骨", "mu_肺", "alpha_软组织", "alpha_骨"]:
        names.append(n)

    return names
