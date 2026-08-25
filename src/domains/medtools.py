"""Matha 领域扩展模块：中医/西医器械与设备（TCM / Western Medicine Tools & Equipment）。

基于 Matha 数学基础与物理常量体系，演化中医与西医器械、设备子领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、中医诊断与针灸（TCM Diagnosis & Acupuncture）- 前缀 中医_
  1) 脉率分类：按 bpm 判定迟/平/数/疾脉
  2) 骨度分寸：按体表标志查同身寸折算长度
  3) 针刺深度：按总深度与比例计算进针深度
  4) 艾灸温度：按距离平方反比估算施灸温度
  5) 拔罐负压：按大气压与罐口半径估算负压吸力
  6) 子午流注：按时辰映射十二经气血流注
  7) 体质指数：按 BMI 与偏倚评分校正
  8) 经穴间距：按骨度分寸与比例计算两穴间距
  9) 九针选用：按针刺深度选用九针针具
  10) 耳穴分区：按分区代码查耳穴区域

二、中药药剂（Herbal Pharmacy）- 前缀 中药_
  1) 古今剂量：按朝代折算两→克
  2) 煎煮浓缩：按药量与终体积计算浓度
  3) 君臣佐使：按四组药量计算君药占比
  4) 儿童剂量Clark：按体重折算儿童剂量
  5) 儿童剂量Young：按年龄折算儿童剂量
  6) 煎药水量：按药量与比例计算加水体积
  7) 浸泡时间：按药材类型查浸泡时间
  8) 毒性限量：按毒性药材判定是否超限
  9) 折干率：按鲜重与折干比计算干重
  10) 配伍七情：按两药类型查配伍关系
  11) 分次服用：按总量与每日次数计算单次量

三、手术器械与力学（Surgical Instruments & Mechanics）- 前缀 手术_
  1) 缝合线张力：按 USP 号查抗拉张力
  2) 缝合线直径：按 USP 号查直径
  3) 缝合针弯矩：按力与针半径计算弯矩
  4) 止血带压力：按肢体周径与收缩压估算
  5) 螺钉拔出力：按直径与骨密度估算
  6) 克氏针选择：按骨类型选直径
  7) 放大镜视野：按放大倍数计算视野
  8) 牵引重量：按体重与比例计算
  9) 钳夹力：按握力与杠杆比计算
  10) 电刀功率：按组织类型查功率

四、医疗设备与仪器（Medical Equipment & Instruments）- 前缀 设备_
  1) 输液滴速：按 mL/h 与滴系数计算滴/分
  2) 注射泵流速：按剂量、浓度、时长计算 mL/h
  3) 分钟通气量：按潮气量与频率计算
  4) I:E 比校验：按吸呼时间化简比值
  5) 除颤能量：按体重与 J/kg 计算
  6) 超声穿透深度：按频率估算
  7) 血透超滤率：按目标量与时长计算
  8) 心电采样率：按诊断类型查采样率
  9) 输液泵压力限：按管内径估算
  10) 心率报警限：按年龄查上下限

五、康复器械与假体（Rehabilitation Devices & Prosthetics）- 前缀 康复_
  1) 接受腔压力：按体重与接触面积计算
  2) 轮椅推进力：按体重与坡度计算
  3) 弹簧常数：按载荷与变形量计算
  4) 外骨骼力矩：按所需力矩与辅助比计算
  5) 关节接触应力：按载荷与接触面积计算
  6) 肌腱张力：按截面积与安全系数计算
  7) 假体磨损：按载荷与循环次数估算
  8) 辅助器高度：按身高与比例计算
  9) 压缩袜压力：按踝部压力与梯度比计算
  10) CPM 角度增量：按目标 ROM 与天数计算

数据库：
  - 骨度分寸表（常用体表标志同身寸折算）
  - 古今剂量折算表（汉/唐/宋/明/清/现代）
  - 毒性药材极量表（附子/川乌/草乌/马钱子等）
  - 缝合线规格表（USP 2-0 ~ 7-0）
  - 子午流注十二经时辰表
  - 呼吸机默认参数表（成人/儿童/新生儿）

设计原则：
  - 与 medical / biology 保持一致：_curryN 柯里化、前缀区分
  - 函数返回纯数值或字符串/元组，不做语义包装
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

# 骨度分寸（同身寸折算，单位寸）
BONE_MEASURE: dict[str, float] = {
    "前发际至后发际": 12.0,
    "眉心至大椎": 18.0,
    "天突至歧骨": 9.0,
    "歧骨至脐": 8.0,
    "脐至耻骨联合上缘": 5.0,
    "腋横纹至十一肋": 12.0,
    "肩峰至腕横纹": 12.0,
    "腋横纹至肘横纹": 9.0,
    "肘横纹至腕横纹": 12.0,
    "耻骨联合上缘至髌底": 18.0,
    "髌底至踝尖": 16.0,
    "臀横纹至膝中": 14.0,
}

# 古今剂量折算（一两 = ? 克）
ANCIENT_DOSAGE_G: dict[str, float] = {
    "汉代": 15.625,
    "唐代": 15.0,
    "宋代": 40.0,
    "明代": 37.3,
    "清代": 37.3,
    "现代": 15.625,
}

# 毒性药材极量（克/日）
TOXIC_HERB_MAX: dict[str, float] = {
    "附子": 15.0,
    "川乌": 3.0,
    "草乌": 3.0,
    "马钱子": 0.6,
    "巴豆": 0.3,
    "斑蝥": 0.05,
    "细辛": 3.0,
    "半夏": 9.0,
    "天南星": 9.0,
    "洋金花": 0.6,
}

# 缝合线规格（USP 号 → 直径 mm / 抗拉 N）
SUTURE_SPEC: dict[str, dict[str, float]] = {
    "2-0": {"diameter_mm": 0.30, "tensile_N": 25.0},
    "3-0": {"diameter_mm": 0.20, "tensile_N": 16.0},
    "4-0": {"diameter_mm": 0.15, "tensile_N": 9.0},
    "5-0": {"diameter_mm": 0.10, "tensile_N": 5.0},
    "6-0": {"diameter_mm": 0.07, "tensile_N": 2.5},
    "7-0": {"diameter_mm": 0.05, "tensile_N": 1.5},
}

# 子午流注十二经时辰表（地支 → 经脉）
MERIDIAN_CLOCK: dict[str, str] = {
    "子": "胆", "丑": "肝", "寅": "肺", "卯": "大肠",
    "辰": "胃", "巳": "脾", "午": "心", "未": "小肠",
    "申": "膀胱", "酉": "肾", "戌": "心包", "亥": "三焦",
}

# 呼吸机默认参数（按患者类型）
VENT_DEFAULT: dict[str, dict] = {
    "成人": {"VT_mLkg": 6.0, "RR": 12, "I:E": "1:2"},
    "儿童": {"VT_mLkg": 7.0, "RR": 20, "I:E": "1:2"},
    "新生儿": {"VT_mLkg": 8.0, "RR": 40, "I:E": "1:1.5"},
}


# ========== 常量 ==========

GRAVITY = 9.80665          # 标准重力加速度 m/s^2
ATM_KPA = 101.325          # 标准大气压 kPa
G_TO_LIANG_MODERN = 50.0   # 现代 1 两 = 50 g
G_TO_QIAN = 3.125          # 1 钱 = 3.125 g（现代 1 两=10 钱=50 g）


# ========== 一、中医诊断与针灸 ==========

def _中医_脉率分类(bpm):
    """按脉率（次/分）分类：<60 迟脉，<=90 平脉，<=120 数脉，>120 疾脉。"""
    if bpm < 60:
        return "迟脉"
    if bpm <= 90:
        return "平脉"
    if bpm <= 120:
        return "数脉"
    return "疾脉"


def _中医_骨度分寸(landmark):
    """按体表标志查骨度分寸（同身寸），未收录返回 0.0。"""
    return BONE_MEASURE.get(landmark, 0.0)


def _中医_针刺深度(depth_total, ratio):
    """按总深度与比例计算进针深度 = depth_total * ratio。"""
    return depth_total * ratio


def _中医_艾灸温度(T_source, d, d_ref=3.0):
    """艾灸温度按距离平方反比估算 T = T_source * (d_ref/d)^2，d<=0 时返回源温。"""
    if d <= 0:
        return T_source
    return T_source * (d_ref / d) ** 2


def _中医_拔罐负压(P_atm, r_inner_cm):
    """拔罐负压吸力：delta_P=P_atm*0.4, A=pi*(r/100)^2, F=delta_P*1000*A。"""
    delta_P = P_atm * 0.4
    A = math.pi * (r_inner_cm / 100.0) ** 2
    return delta_P * 1000.0 * A


# 十二地支（子午流注时辰）
_EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]


def _中医_子午流注(hour):
    """按时辰（24h）映射子午流注经脉，返回 'X时·Y经'。"""
    idx = ((hour + 1) // 2) % 12
    branch = _EARTHLY_BRANCHES[idx]
    return f"{branch}时·{MERIDIAN_CLOCK[branch]}经"


def _中医_体质指数(BMI, bias_score):
    """校正体质指数 = BMI * (1 + bias_score/100)。"""
    return BMI * (1.0 + bias_score / 100.0)


def _中医_经穴间距(landmark, frac1, frac2):
    """按骨度分寸与两穴比例计算间距 = |frac1-frac2| * total。"""
    total = BONE_MEASURE.get(landmark, 0.0)
    return abs(frac1 - frac2) * total


def _中医_九针选用(depth_mm):
    """按针刺深度选用九针：<3 鍉针，<10 毫针，<20 长针，否则大针。"""
    if depth_mm < 3:
        return "鍉针（浅刺皮部）"
    if depth_mm < 10:
        return "毫针（常规针刺）"
    if depth_mm < 20:
        return "长针（深刺肌层）"
    return "大针（深部刺络）"


def _中医_耳穴分区(zone_code):
    """按耳穴分区代码查区域名称。"""
    table = {
        "HX": "耳轮", "AH": "耳舟", "SF": "对耳轮上脚", "NF": "对耳轮下脚",
        "CO": "耳甲", "TG": "耳屏", "AT": "对耳屏", "LO": "耳垂",
        "IL": "耳轮脚", "ST": "耳壳背",
    }
    return table.get(zone_code, "未知分区")


# ========== 二、中药药剂 ==========

def _中药_古今剂量(liang, dynasty="汉代"):
    """按朝代折算两→克 = liang * factor。"""
    factor = ANCIENT_DOSAGE_G.get(dynasty, 15.625)
    return liang * factor


def _中药_煎煮浓缩(herb_g, final_mL):
    """煎煮后浓度 = herb_g / final_mL。"""
    return herb_g / final_mL if final_mL > 0 else 0.0


def _中药_君臣佐使(jun, chen, zuo, shi):
    """君药占比 = jun / (jun+chen+zuo+shi)。"""
    total = jun + chen + zuo + shi
    return jun / total if total > 0 else 0.0


def _中药_儿童剂量Clark(adult_dose, child_kg, adult_kg=70):
    """Clark 公式：儿童剂量 = adult_dose * child_kg / adult_kg。"""
    return adult_dose * child_kg / adult_kg


def _中药_儿童剂量Young(adult_dose, age):
    """Young 公式：儿童剂量 = adult_dose * age / (age + 12)。"""
    return adult_dose * age / (age + 12.0)


def _中药_煎药水量(herb_g, ratio):
    """煎药加水体积 = herb_g * ratio。"""
    return herb_g * ratio


def _中药_浸泡时间(herb_type):
    """按药材类型查浸泡时间（分钟）。"""
    table = {
        "花叶": 20, "全草": 30, "根茎": 40,
        "矿物": 60, "贝壳": 60, "角甲": 90,
    }
    return table.get(herb_type, 30)


def _中药_毒性限量(herb, dose_g):
    """判定毒性药材是否超限，返回 (是否超限, 极量)。"""
    max_g = TOXIC_HERB_MAX.get(herb, float('inf'))
    return (dose_g > max_g, max_g)


def _中药_折干率(fresh_g, dry_ratio=0.3):
    """折干重 = fresh_g * dry_ratio。"""
    return fresh_g * dry_ratio


# 配伍七情对照表
_COMPATIBILITY_PAIRS = {
    ("相须", "相须"): "相须（协同增效）",
    ("相使", "相使"): "相使（辅药助主）",
    ("相畏", "相杀"): "相畏（受彼抑制毒副作用）",
    ("相杀", "相畏"): "相杀（消除彼之毒副作用）",
    ("相恶", "相恶"): "相恶（相互减效）",
    ("相反", "相反"): "相反（产生毒副作用，禁忌）",
}


def _中药_配伍七情(herb1_type, herb2_type):
    """按两药配伍类型查七情关系，未匹配返回单行。"""
    return _COMPATIBILITY_PAIRS.get((herb1_type, herb2_type), "单行（无特殊相互作用）")


def _中药_分次服用(total_mL, times_per_day):
    """单次服用量 = total_mL / times_per_day。"""
    return total_mL / times_per_day if times_per_day > 0 else 0.0


# ========== 三、手术器械与力学 ==========

def _手术_缝合线张力(usp):
    """按 USP 号查缝合线抗拉张力（N）。"""
    spec = SUTURE_SPEC.get(usp)
    return spec["tensile_N"] if spec else 0.0


def _手术_缝合线直径(usp):
    """按 USP 号查缝合线直径（mm）。"""
    spec = SUTURE_SPEC.get(usp)
    return spec["diameter_mm"] if spec else 0.0


def _手术_缝合针弯矩(F, r_needle_mm):
    """缝合针弯矩 = F * r_needle_mm。"""
    return F * r_needle_mm


def _手术_止血带压力(limb_circumference_cm, SBP_mmHg):
    """止血带压力 = SBP + 50 + (周径/10)*10。"""
    factor = limb_circumference_cm / 10.0
    return SBP_mmHg + 50.0 + factor * 10.0


def _手术_螺钉拔出力(d_mm, bone_density_gcm3=1.8):
    """螺钉拔出力 = 50 * d * 骨密度。"""
    k = 50.0
    return k * d_mm * bone_density_gcm3


def _手术_克氏针选择(bone_type):
    """按骨类型选克氏针直径（mm）。"""
    table = {
        "指骨": 1.0, "掌骨": 1.5, "桡骨": 2.0, "肱骨": 2.5,
        "股骨": 3.0, "胫骨": 3.0,
    }
    return table.get(bone_type, 2.0)


def _手术_放大镜视野(magnification, FOV_at_1x_mm=80):
    """放大镜视野 = FOV_at_1x / magnification。"""
    return FOV_at_1x_mm / magnification


def _手术_牵引重量(body_kg, fraction=0.1):
    """牵引重量 = body_kg * fraction。"""
    return body_kg * fraction


def _手术_钳夹力(F_handle, lever_ratio):
    """钳夹力 = F_handle * lever_ratio。"""
    return F_handle * lever_ratio


def _手术_电刀功率(tissue_type):
    """按组织类型查电刀功率（W）。"""
    table = {
        "皮肤": 30, "皮下": 40, "肌肉": 50, "脂肪": 35, "脏器": 25,
    }
    return table.get(tissue_type, 35)


# ========== 四、医疗设备与仪器 ==========

def _设备_输液滴速(mL_per_h, drop_factor=20):
    """输液滴速（滴/分）= mL_per_h * drop_factor / 60。"""
    return mL_per_h * drop_factor / 60.0


def _设备_注射泵流速(dose_mg, conc_mg_per_mL, duration_h):
    """注射泵流速（mL/h）= dose / (conc * duration)。"""
    return dose_mg / (conc_mg_per_mL * duration_h)


def _设备_分钟通气量(VT_mL, RR):
    """分钟通气量（mL/min）= VT * RR。"""
    return VT_mL * RR


def _设备_IE比校验(I_time, E_time):
    """I:E 比化简：对吸呼时间各 ×10 取整后用 gcd 化简。"""
    i10 = int(I_time * 10)
    e10 = int(E_time * 10)
    g = math.gcd(i10, e10)
    i_s = i10 // g
    e_s = e10 // g
    return f"{i_s}:{e_s}"


def _设备_除颤能量(body_kg, J_per_kg=2.0):
    """除颤能量（J）= body_kg * J_per_kg。"""
    return body_kg * J_per_kg


def _设备_超声穿透深度(freq_MHz):
    """超声穿透深度（cm）≈ 40 / freq_MHz。"""
    return 40.0 / freq_MHz if freq_MHz > 0 else 0.0


def _设备_血透超滤率(target_mL, duration_h):
    """血透超滤率（mL/h）= target / duration。"""
    return target_mL / duration_h if duration_h > 0 else 0.0


def _设备_心电采样率(diagnostic_type):
    """按诊断类型查心电采样率（Hz）。"""
    table = {
        "常规": 250, "诊断": 500, "心律分析": 150, "运动负荷": 1000,
    }
    return table.get(diagnostic_type, 250)


def _设备_输液泵压力限(tube_ID_mm):
    """输液泵压力限 = 100 + tube_ID * 30。"""
    return 100.0 + tube_ID_mm * 30.0


def _设备_心率报警限(age):
    """按年龄查心率报警上下限，返回 (下限, 上限)。"""
    if age < 1:
        return (80, 180)
    if age < 6:
        return (70, 150)
    if age < 12:
        return (60, 130)
    return (50, 120)


# ========== 五、康复器械与假体 ==========

def _康复_接受腔压力(weight_N, contact_area_cm2):
    """接受腔压力（kPa）= weight / (area*1e-4) / 1000。"""
    A_m2 = contact_area_cm2 * 1e-4
    return weight_N / A_m2 / 1000.0


def _康复_轮椅推进力(weight_kg, slope_deg):
    """轮椅推进力（N）= weight * g * sin(slope)。"""
    return weight_kg * GRAVITY * math.sin(math.radians(slope_deg))


def _康复_弹簧常数(load_N, deformation_mm):
    """弹簧常数（N/mm）= load / deformation。"""
    return load_N / deformation_mm if deformation_mm != 0 else 0.0


def _康复_外骨骼力矩(torque_needed, assist_ratio):
    """外骨骼力矩 = torque_needed * assist_ratio。"""
    return torque_needed * assist_ratio


def _康复_关节接触应力(load_N, contact_area_mm2):
    """关节接触应力（MPa）= load / area。"""
    return load_N / contact_area_mm2 if contact_area_mm2 > 0 else 0.0


def _康复_肌腱张力(area_mm2, UTS_MPa=50, safety=0.25):
    """肌腱张力（N）= area * UTS * safety。"""
    return area_mm2 * UTS_MPa * safety


def _康复_假体磨损(load_N, cycles, wear_coeff=1e-9):
    """假体磨损量 = load * cycles * wear_coeff。"""
    return load_N * cycles * wear_coeff


def _康复_辅助器高度(height_cm, ratio=0.6):
    """辅助器高度 = height * ratio。"""
    return height_cm * ratio


def _康复_压缩袜压力(ankle_pressure, gradient=0.7):
    """压缩袜梯度压力 = ankle_pressure * gradient。"""
    return ankle_pressure * gradient


def _康复_CPM角度增量(target_ROM, days):
    """CPM 每日角度增量 = target_ROM / days。"""
    return target_ROM / days if days > 0 else 0.0


# ========== 注册 ==========

def _register_medtools(builtins: dict) -> None:
    """将中医/西医器械与设备子领域内建注册到解释器 builtins。"""

    # ===== 一、中医诊断与针灸 =====
    builtins["中医_脉率分类"] = _中医_脉率分类
    builtins["中医_骨度分寸"] = _中医_骨度分寸
    builtins["中医_针刺深度"] = _curry2(_中医_针刺深度)
    builtins["中医_艾灸温度"] = _curry2(_中医_艾灸温度)
    builtins["中医_拔罐负压"] = _curry2(_中医_拔罐负压)
    builtins["中医_子午流注"] = _中医_子午流注
    builtins["中医_体质指数"] = _curry2(_中医_体质指数)
    builtins["中医_经穴间距"] = _curry3(_中医_经穴间距)
    builtins["中医_九针选用"] = _中医_九针选用
    builtins["中医_耳穴分区"] = _中医_耳穴分区

    # ===== 二、中药药剂 =====
    builtins["中药_古今剂量"] = _中药_古今剂量
    builtins["中药_煎煮浓缩"] = _curry2(_中药_煎煮浓缩)
    builtins["中药_君臣佐使"] = _curry4(_中药_君臣佐使)
    builtins["中药_儿童剂量Clark"] = _curry2(_中药_儿童剂量Clark)
    builtins["中药_儿童剂量Young"] = _curry2(_中药_儿童剂量Young)
    builtins["中药_煎药水量"] = _curry2(_中药_煎药水量)
    builtins["中药_浸泡时间"] = _中药_浸泡时间
    builtins["中药_毒性限量"] = _curry2(_中药_毒性限量)
    builtins["中药_折干率"] = _中药_折干率
    builtins["中药_配伍七情"] = _curry2(_中药_配伍七情)
    builtins["中药_分次服用"] = _curry2(_中药_分次服用)

    # ===== 三、手术器械与力学 =====
    builtins["手术_缝合线张力"] = _手术_缝合线张力
    builtins["手术_缝合线直径"] = _手术_缝合线直径
    builtins["手术_缝合针弯矩"] = _curry2(_手术_缝合针弯矩)
    builtins["手术_止血带压力"] = _curry2(_手术_止血带压力)
    builtins["手术_螺钉拔出力"] = _curry2(_手术_螺钉拔出力)
    builtins["手术_克氏针选择"] = _手术_克氏针选择
    builtins["手术_放大镜视野"] = _curry2(_手术_放大镜视野)
    builtins["手术_牵引重量"] = _curry2(_手术_牵引重量)
    builtins["手术_钳夹力"] = _curry2(_手术_钳夹力)
    builtins["手术_电刀功率"] = _手术_电刀功率

    # ===== 四、医疗设备与仪器 =====
    builtins["设备_输液滴速"] = _curry2(_设备_输液滴速)
    builtins["设备_注射泵流速"] = _curry3(_设备_注射泵流速)
    builtins["设备_分钟通气量"] = _curry2(_设备_分钟通气量)
    builtins["设备_IE比校验"] = _curry2(_设备_IE比校验)
    builtins["设备_除颤能量"] = _curry2(_设备_除颤能量)
    builtins["设备_超声穿透深度"] = _设备_超声穿透深度
    builtins["设备_血透超滤率"] = _curry2(_设备_血透超滤率)
    builtins["设备_心电采样率"] = _设备_心电采样率
    builtins["设备_输液泵压力限"] = _设备_输液泵压力限
    builtins["设备_心率报警限"] = _设备_心率报警限

    # ===== 五、康复器械与假体 =====
    builtins["康复_接受腔压力"] = _curry2(_康复_接受腔压力)
    builtins["康复_轮椅推进力"] = _curry2(_康复_轮椅推进力)
    builtins["康复_弹簧常数"] = _curry2(_康复_弹簧常数)
    builtins["康复_外骨骼力矩"] = _curry2(_康复_外骨骼力矩)
    builtins["康复_关节接触应力"] = _curry2(_康复_关节接触应力)
    builtins["康复_肌腱张力"] = _curry3(_康复_肌腱张力)
    builtins["康复_假体磨损"] = _curry2(_康复_假体磨损)
    builtins["康复_辅助器高度"] = _curry2(_康复_辅助器高度)
    builtins["康复_压缩袜压力"] = _curry2(_康复_压缩袜压力)
    builtins["康复_CPM角度增量"] = _curry2(_康复_CPM角度增量)

    # ===== 数据库：骨度分寸 =====
    for k, v in BONE_MEASURE.items():
        builtins[f"骨度_{k}"] = v

    # ===== 数据库：古今剂量 =====
    for k, v in ANCIENT_DOSAGE_G.items():
        builtins[f"古方剂量_{k}"] = v

    # ===== 数据库：毒性药材极量 =====
    for k, v in TOXIC_HERB_MAX.items():
        builtins[f"毒药极量_{k}"] = v

    # ===== 数据库：缝合线规格 =====
    for k, v in SUTURE_SPEC.items():
        builtins[f"缝合线_{k}_直径"] = v["diameter_mm"]
        builtins[f"缝合线_{k}_抗拉"] = v["tensile_N"]

    # ===== 数据库：子午流注 =====
    for k, v in MERIDIAN_CLOCK.items():
        builtins[f"流注_{k}"] = v

    # ===== 数据库：呼吸机默认参数 =====
    for k, v in VENT_DEFAULT.items():
        builtins[f"呼吸机_{k}_VT"] = v["VT_mLkg"]
        builtins[f"呼吸机_{k}_RR"] = v["RR"]

    # ===== 常量 =====
    builtins["g_重力"] = GRAVITY
    builtins["atm_kPa"] = ATM_KPA


# ========== 语义符号表 ==========

def _medtools_symtab_names() -> list[str]:
    names: list[str] = []

    # 一、中医诊断与针灸
    for n in ["脉率分类", "骨度分寸", "针刺深度", "艾灸温度", "拔罐负压",
              "子午流注", "体质指数", "经穴间距", "九针选用", "耳穴分区"]:
        names.append(f"中医_{n}")

    # 二、中药药剂
    for n in ["古今剂量", "煎煮浓缩", "君臣佐使", "儿童剂量Clark", "儿童剂量Young",
              "煎药水量", "浸泡时间", "毒性限量", "折干率", "配伍七情", "分次服用"]:
        names.append(f"中药_{n}")

    # 三、手术器械与力学
    for n in ["缝合线张力", "缝合线直径", "缝合针弯矩", "止血带压力", "螺钉拔出力",
              "克氏针选择", "放大镜视野", "牵引重量", "钳夹力", "电刀功率"]:
        names.append(f"手术_{n}")

    # 四、医疗设备与仪器
    for n in ["输液滴速", "注射泵流速", "分钟通气量", "IE比校验", "除颤能量",
              "超声穿透深度", "血透超滤率", "心电采样率", "输液泵压力限", "心率报警限"]:
        names.append(f"设备_{n}")

    # 五、康复器械与假体
    for n in ["接受腔压力", "轮椅推进力", "弹簧常数", "外骨骼力矩", "关节接触应力",
              "肌腱张力", "假体磨损", "辅助器高度", "压缩袜压力", "CPM角度增量"]:
        names.append(f"康复_{n}")

    # 数据库：骨度分寸
    for k in BONE_MEASURE:
        names.append(f"骨度_{k}")

    # 数据库：古今剂量
    for k in ANCIENT_DOSAGE_G:
        names.append(f"古方剂量_{k}")

    # 数据库：毒性药材极量
    for k in TOXIC_HERB_MAX:
        names.append(f"毒药极量_{k}")

    # 数据库：缝合线规格
    for k in SUTURE_SPEC:
        names.append(f"缝合线_{k}_直径")
        names.append(f"缝合线_{k}_抗拉")

    # 数据库：子午流注
    for k in MERIDIAN_CLOCK:
        names.append(f"流注_{k}")

    # 数据库：呼吸机默认参数
    for k in VENT_DEFAULT:
        names.append(f"呼吸机_{k}_VT")
        names.append(f"呼吸机_{k}_RR")

    # 常量
    for n in ["g_重力", "atm_kPa"]:
        names.append(n)

    return names
