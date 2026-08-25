"""Matha 领域扩展模块：解剖学（Anatomy）。

基于 Matha 数学基础与物理/生物常量体系，演化解剖学子领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、系统解剖（Systemic Anatomy）- 前缀 系统_
  1) 心胸比 CTR = 心脏横径 / 胸廓横径
  2) 股骨颈干角分类（外翻/正常/内翻）
  3) 股骨前倾角分类
  4) 颈椎曲度指数（前凸深度/椎体长度）
  5) 腰椎前凸 Cobb 角正切估算
  6) 骨盆入口指数：纵径/横径
  7) 脑室指数：侧脑室宽/脑横径
  8) 主动脉根部 Z 值（简化，按 BSA）
  9) 椎管矢状径临界判定（颈/腰段）
  10) 视神经鞘直径判定（颅高压筛查）

二、局部解剖（Regional Anatomy）- 前缀 局部_
  1) 甲状腺体积（椭球公式 π/6·a·b·c）
  2) 前列腺体积（椭球公式）
  3) 肝脏体积估算（径线乘积 × 系数）
  4) 脾脏体积（椭球公式）
  5) 肾脏体积（椭球公式）
  6) 睾丸体积（椭球公式 π/6·L·W·H）
  7) 心室壁质量估测
  8) 关节腔深度估算

三、表面解剖（Surface Anatomy）- 前缀 表面_
  1) 体表面积 Mosteller 公式 sqrt(H·W/3600)
  2) 体表面积 DuBois 公式 0.007184·W^0.425·H^0.725
  3) 烧伤九分法面积（按部位）
  4) 椎体节段定位（C2-T12 比例）
  5) 经皮进针深度估算
  6) 体表标志间距（解剖坐标）

四、影像解剖（Imaging Anatomy）- 前缀 影解_
  1) CT 椎管矢状径（按节段查参考值）
  2) 椎弓根间距参考值
  3) 脊髓圆锥位置判定
  4) 脑沟宽度参考值（按年龄）
  5) 侧脑室前角宽度参考值
  6) 垂体高度判定
  7) Evans 指数（侧脑室前角/颅横径）
  8) 肺结节体积倍增时间

五、临床解剖（Clinical Anatomy）- 前缀 临解_
  1) 心脏质量预测（按体重）
  2) 肝脏质量预测（按体重）
  3) 脾脏质量预测（按体重）
  4) 肾脏质量预测（按体重）
  5) 脑质量预测（按体重）
  6) 血容量估算（按体重与性别）
  7) 肺总量估算（按身高与性别）
  8) 脏器质量/体重比

数据库：
  - 人体骨骼分类计数表（206 块分类）
  - 主要脏器成人平均质量与比重（g 与 g/cm³）
  - 血管典型参数（主动脉/肺动脉/冠状动脉/颈动脉/股动脉）
  - 椎体节段参考数据（颈/胸/腰椎矢状径、椎弓根距）
  - 心脏腔室正常参考值

设计原则：
  - 与 medical / medtools / biology 保持一致：_curryN 柯里化、前缀区分
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

# 人体骨骼分类计数（成人 206 块）
SKELETON_COUNT: dict[str, int] = {
    "颅骨": 29,        # 脑颅 8 + 面颅 15 + 听小骨 6
    "躯干骨": 51,      # 椎骨 26 + 肋骨 24 + 胸骨 1
    "上肢骨": 64,      # 肩带 4 + 自由上肢 60
    "下肢骨": 62,      # 盆带 2 + 自由下肢 60
    "中轴骨": 80,      # 颅 29 + 躯干 51
    "附肢骨": 126,     # 上肢 64 + 下肢 62
    "总计": 206,
}

# 主要脏器成人平均质量（g）与比重（g/cm³）
ORGAN_SPEC: dict[str, dict[str, float]] = {
    "心":     {"mass_g": 300.0, "density": 1.05},
    "肝":     {"mass_g": 1500.0, "density": 1.05},
    "脾":     {"mass_g": 150.0, "density": 1.05},
    "肾":     {"mass_g": 140.0, "density": 1.05},
    "脑":     {"mass_g": 1400.0, "density": 1.04},
    "肺":     {"mass_g": 450.0, "density": 0.30},   # 含气
    "胰":     {"mass_g": 90.0, "density": 1.05},
    "甲状腺": {"mass_g": 25.0, "density": 1.05},
    "前列腺": {"mass_g": 20.0, "density": 1.05},
    "肾上腺": {"mass_g": 6.0, "density": 1.05},
}

# 血管典型参数（成人，内径 mm，壁厚 mm，弹性模量 MPa 近似）
VESSEL_SPEC: dict[str, dict[str, float]] = {
    "主动脉":     {"ID_mm": 25.0, "wall_mm": 2.0, "E_MPa": 0.5},
    "肺动脉":     {"ID_mm": 25.0, "wall_mm": 1.0, "E_MPa": 0.3},
    "颈动脉":     {"ID_mm": 6.0,  "wall_mm": 0.8, "E_MPa": 0.8},
    "股动脉":     {"ID_mm": 7.0,  "wall_mm": 0.7, "E_MPa": 0.8},
    "冠状动脉":   {"ID_mm": 3.0,  "wall_mm": 0.5, "E_MPa": 1.0},
    "桡动脉":     {"ID_mm": 2.5,  "wall_mm": 0.4, "E_MPa": 1.0},
    "下腔静脉":   {"ID_mm": 20.0, "wall_mm": 1.5, "E_MPa": 0.1},
}

# 椎管矢状径参考值（mm，成人，前后径）
SPINAL_CANAL_SAG: dict[str, float] = {
    "颈椎_C3": 14.0, "颈椎_C4": 14.0, "颈椎_C5": 14.0, "颈椎_C6": 14.5, "颈椎_C7": 15.0,
    "胸椎_T1": 16.0, "胸椎_T6": 16.0, "胸椎_T12": 16.0,
    "腰椎_L1": 18.0, "腰椎_L2": 18.0, "腰椎_L3": 18.0, "腰椎_L4": 18.0, "腰椎_L5": 17.0,
}

# 椎弓根间距参考值（mm，成人，最大值）
PEDICLE_DISTANCE: dict[str, float] = {
    "颈椎": 28.0, "胸椎上": 22.0, "胸椎中": 20.0, "胸椎下": 22.0,
    "腰椎上": 25.0, "腰椎中": 28.0, "腰椎下": 30.0,
}

# 心脏腔室正常参考值（成人，超声心动图，舒张末期）
CARDIAC_CHAMBER: dict[str, dict[str, float]] = {
    "左房":     {"LA_mm": 38.0, "LA_A_cm2": 20.0},
    "左室":     {"LVDd_mm": 50.0, "LVSd_mm": 32.0, "LV_vol_mL": 120.0},
    "右房":     {"RA_mm": 40.0},
    "右室":     {"RVD_mm": 30.0},
    "室间隔":   {"IVSd_mm": 10.0},
    "左室后壁": {"LVPWd_mm": 10.0},
}

# 脑解剖参考值（成人，CT/MRI）
BRAIN_REF: dict[str, float] = {
    "侧脑室前角_mm": 30.0,
    "第三脑室_mm": 5.0,
    "脑沟_mm_青年": 3.0,
    "脑沟_mm_老年": 5.0,
    "垂体高度_mm": 6.0,
    "视神经鞘_mm": 4.5,
}


# ========== 常量 ==========

ELLIPSOID_K = math.pi / 6.0           # 椭球体积系数 π/6
BLOOD_VOL_ML_KG_M = 70.0              # 男性血容量 mL/kg
BLOOD_VOL_ML_KG_F = 65.0              # 女性血容量 mL/kg
BSA_MOSTELLER_K = 3600.0              # Mosteller 常量
BSA_DUBOIS_K = 0.007184               # DuBois 常量
HEART_MASS_FRAC = 0.0045              # 心脏质量/体重 ≈ 0.45%
LIVER_MASS_FRAC = 0.0225              # 肝脏质量/体重 ≈ 2.25%
SPLEEN_MASS_FRAC = 0.0023             # 脾脏质量/体重 ≈ 0.23%
KIDNEY_MASS_FRAC = 0.0021             # 单肾/体重 ≈ 0.21%
BRAIN_MASS_FRAC = 0.021               # 脑/体重 ≈ 2.1%


# ========== 一、系统解剖 ==========

def _系统_心胸比(cardiac_TD_mm, thoracic_TD_mm):
    """心胸比 CTR = 心脏横径 / 胸廓横径。>0.5 提示心脏增大。"""
    if thoracic_TD_mm <= 0:
        return 0.0
    return cardiac_TD_mm / thoracic_TD_mm


def _系统_股骨颈干角分类(angle_deg):
    """股骨颈干角分类：<110 内翻，110-140 正常，>140 外翻。"""
    if angle_deg < 110:
        return "髋内翻"
    if angle_deg <= 140:
        return "正常"
    return "髋外翻"


def _系统_股骨前倾角分类(angle_deg):
    """股骨前倾角分类（成人典型 12°）：<5 后倾，5-25 正常，>25 异常前倾。"""
    if angle_deg < 5:
        return "后倾"
    if angle_deg <= 25:
        return "正常"
    return "异常前倾"


def _系统_颈椎曲度指数(posterior_depth_mm, vertebral_length_mm):
    """颈椎曲度指数 = 后缘深度 / 椎体长度。0.1-0.3 正常，<0.1 变直。"""
    if vertebral_length_mm <= 0:
        return 0.0
    return posterior_depth_mm / vertebral_length_mm


def _系统_腰椎Cobb角正切(delta_y_mm, delta_x_mm):
    """由 Cobb 角端点垂足差估算正切角 = atan(Δy/Δx)（度）。"""
    if delta_x_mm == 0:
        return 90.0
    return math.degrees(math.atan(delta_y_mm / delta_x_mm))


def _系统_骨盆入口指数(AP_diameter_mm, transverse_diameter_mm):
    """骨盆入口指数 = 入口前后径 / 横径。男<1 女>1（产科）。"""
    if transverse_diameter_mm <= 0:
        return 0.0
    return AP_diameter_mm / transverse_diameter_mm


def _系统_脑室指数(ventricle_width_mm, brain_width_mm):
    """脑室指数 = 侧脑室宽度 / 脑横径。>0.5 提示脑积水。"""
    if brain_width_mm <= 0:
        return 0.0
    return ventricle_width_mm / brain_width_mm


def _系统_主动脉Z值(aortic_root_mm, BSA):
    """主动脉根部 Z 值简化估算（基于 BSA 标化，非临床精确公式）：
    预期 D = 14.4 + BSA*9.5，Z = (实测 - 预期) / 1.5。"""
    expected = 14.4 + BSA * 9.5
    return (aortic_root_mm - expected) / 1.5


def _系统_椎管矢状径判定(level, sagittal_mm):
    """按节段判定椎管矢状径是否狭窄（颈<13 / 腰<15 提示狭窄），返回 (是否狭窄, 参考值)。"""
    ref = SPINAL_CANAL_SAG.get(level, 0.0)
    threshold = 13.0 if level.startswith("颈椎") else 15.0
    return (sagittal_mm < threshold, ref)


def _系统_视神经鞘判定(ONSD_mm):
    """视神经鞘直径判定：>5.4mm 提示颅内压升高。"""
    if ONSD_mm > 5.4:
        return ("阳性", 5.4)
    return ("阴性", 5.4)


# ========== 二、局部解剖 ==========

def _局部_甲状腺体积(a_mm, b_mm, c_mm):
    """甲状腺体积（mL）= π/6 · a · b · c（椭球公式，mm³ → mL）。"""
    return ELLIPSOID_K * a_mm * b_mm * c_mm / 1000.0


def _局部_前列腺体积(a_mm, b_mm, c_mm):
    """前列腺体积（mL）= π/6 · a · b · c。"""
    return ELLIPSOID_K * a_mm * b_mm * c_mm / 1000.0


def _局部_肝脏体积(L_mm, W_mm, H_mm, k=0.55):
    """肝脏体积（mL）= k · L · W · H / 1000，k ≈ 0.55。"""
    return k * L_mm * W_mm * H_mm / 1000.0


def _局部_脾脏体积(a_mm, b_mm, c_mm):
    """脾脏体积（mL）= π/6 · a · b · c。"""
    return ELLIPSOID_K * a_mm * b_mm * c_mm / 1000.0


def _局部_肾脏体积(L_mm, W_mm, H_mm):
    """肾脏体积（mL）= π/6 · L · W · H。"""
    return ELLIPSOID_K * L_mm * W_mm * H_mm / 1000.0


def _局部_睾丸体积(L_mm, W_mm, H_mm):
    """睾丸体积（mL）= π/6 · L · W · H。"""
    return ELLIPSOID_K * L_mm * W_mm * H_mm / 1000.0


def _局部_左室质量(IVSd_mm, LVDd_mm, LVPWd_mm):
    """左室质量估测（Devereux 校正版）：LVM(g) = 0.8·[1.04·(IVSd+LVDd+LVPWd)³ - LVDd³] + 0.6。"""
    sum3 = IVSd_mm + LVDd_mm + LVPWd_mm
    lvm = 0.8 * (1.04 * (sum3 ** 3) - (LVDd_mm ** 3)) + 0.6
    return lvm / 1000.0  # mm³ → cm³ (≈g)


def _局部_关节腔深度(depth_to_bone_mm, needle_advance_mm):
    """关节腔深度估算 = depth_to_bone - safety_margin（安全余量）。"""
    return depth_to_bone_mm - needle_advance_mm


# ========== 三、表面解剖 ==========

def _表面_体表面积Mosteller(height_cm, weight_kg):
    """Mosteller 公式：BSA(m²) = sqrt(H·W/3600)，H=cm, W=kg。"""
    return math.sqrt(height_cm * weight_kg / BSA_MOSTELLER_K)


def _表面_体表面积DuBois(height_cm, weight_kg):
    """DuBois 公式：BSA(m²) = 0.007184·W^0.425·H^0.725。"""
    return BSA_DUBOIS_K * (weight_kg ** 0.425) * (height_cm ** 0.725)


def _表面_烧伤九分法(body_part):
    """成人烧伤九分法（按部位查体表面积百分比）。"""
    table = {
        "头颈": 9.0,
        "右上肢": 9.0,
        "左上肢": 9.0,
        "躯干前": 18.0,
        "躯干后": 18.0,
        "会阴": 1.0,
        "右下肢": 18.0,
        "左下肢": 18.0,
    }
    return table.get(body_part, 0.0)


def _表面_椎体节段定位(distance_from_C2_mm, segment_length_mm):
    """椎体节段定位 = 距 C2 距离 / 平均节段长（向下取整）→ 节段序号。"""
    if segment_length_mm <= 0:
        return 0
    return int(distance_from_C2_mm / segment_length_mm)


def _表面_经皮进针深度(depth_to_target_mm, compression_mm=0.0):
    """经皮进针深度 = 目标深度 + 压缩补偿。"""
    return depth_to_target_mm + compression_mm


def _表面_体表标志间距(landmark1, landmark2):
    """按标志对查标准间距（cm）。未收录返回 0.0。"""
    table = {
        ("胸骨上切迹", "剑突"): 20.0,
        ("剑突", "脐"): 16.0,
        ("脐", "耻骨联合"): 15.0,
        ("肩峰", "桡骨茎突"): 60.0,
        ("髂前上棘", "内踝"): 80.0,
        ("第7颈椎", "第12胸椎"): 25.0,
    }
    return table.get((landmark1, landmark2), table.get((landmark2, landmark1), 0.0))


# ========== 四、影像解剖 ==========

def _影解_椎管矢状径(level):
    """按椎体节段查椎管矢状径参考值（mm）。"""
    return SPINAL_CANAL_SAG.get(level, 0.0)


def _影解_椎弓根间距(region):
    """按脊柱区段查椎弓根间距参考最大值（mm）。"""
    return PEDICLE_DISTANCE.get(region, 0.0)


def _影解_脊髓圆锥位置(vertebral_level):
    """脊髓圆锥位置判定：L1-L2 正常，L3 以下提示低位。"""
    level = vertebral_level.upper()
    if level in ("T12", "L1", "L2"):
        return "正常"
    if level in ("L3", "L4", "L5"):
        return "圆锥低位"
    return "异常"


def _影解_脑沟宽度(age_years, sulcus_mm):
    """按年龄判定脑沟宽度：青壮年<5mm 正常；老年>6mm 异常。"""
    if age_years < 60:
        return "正常" if sulcus_mm < 5.0 else "脑沟增宽"
    return "正常" if sulcus_mm < 6.0 else "脑沟增宽"


def _影解_侧脑室前角宽度(age_years):
    """按年龄返回侧脑室前角宽度参考上限（mm）。"""
    if age_years < 60:
        return 30.0
    return 35.0


def _影解_垂体高度判定(height_mm):
    """垂体高度判定：>10mm 提示垂体增大。"""
    if height_mm > 10.0:
        return ("增大", 10.0)
    return ("正常", 10.0)


def _影解_Evans指数(frontal_horn_mm, cranial_width_mm):
    """Evans 指数 = 侧脑室前角宽/颅最大内径。>0.3 提示脑积水。"""
    if cranial_width_mm <= 0:
        return 0.0
    return frontal_horn_mm / cranial_width_mm


def _影解_肺结节倍增时间(D0_mm, D1_mm, days):
    """肺结节体积倍增时间（天）：V = π/6·D³；DT = ln2·Δt / ln(V1/V0)。"""
    V0 = math.pi / 6.0 * (D0_mm ** 3)
    V1 = math.pi / 6.0 * (D1_mm ** 3)
    if V0 <= 0 or V1 <= 0 or V1 <= V0:
        return float("inf")
    return math.log(2) * days / math.log(V1 / V0)


# ========== 五、临床解剖 ==========

def _临解_心脏质量预测(body_weight_kg):
    """心脏质量预测 = body_weight × 0.0045（g）。"""
    return body_weight_kg * HEART_MASS_FRAC * 1000.0


def _临解_肝脏质量预测(body_weight_kg):
    """肝脏质量预测 = body_weight × 0.0225（g）。"""
    return body_weight_kg * LIVER_MASS_FRAC * 1000.0


def _临解_脾脏质量预测(body_weight_kg):
    """脾脏质量预测 = body_weight × 0.0023（g）。"""
    return body_weight_kg * SPLEEN_MASS_FRAC * 1000.0


def _临解_肾脏质量预测(body_weight_kg):
    """双肾质量预测 = body_weight × 0.0021 × 2（g，含双侧）。"""
    return body_weight_kg * KIDNEY_MASS_FRAC * 1000.0 * 2.0


def _临解_脑质量预测(body_weight_kg):
    """脑质量预测 = body_weight × 0.021（g）。"""
    return body_weight_kg * BRAIN_MASS_FRAC * 1000.0


def _临解_血容量(body_weight_kg, is_male):
    """血容量估算（mL）= body_weight × (70 if 男 else 65)。"""
    factor = BLOOD_VOL_ML_KG_M if is_male else BLOOD_VOL_ML_KG_F
    return body_weight_kg * factor


def _临解_肺总量预测(height_cm, is_male):
    """肺总量估算（mL）：男 50·H - 4500；女 45·H - 4000（H=cm）。"""
    if is_male:
        return max(0.0, 50.0 * height_cm - 4500.0)
    return max(0.0, 45.0 * height_cm - 4000.0)


def _临解_脏器体重比(organ_mass_g, body_weight_kg):
    """脏器质量/体重比 = organ_mass / (body_weight × 1000)。"""
    if body_weight_kg <= 0:
        return 0.0
    return organ_mass_g / (body_weight_kg * 1000.0)


# ========== 注册 ==========

def _register_anatomy(builtins: dict) -> None:
    """将解剖学子领域内建注册到解释器 builtins。"""

    # ===== 一、系统解剖 =====
    builtins["系统_心胸比"] = _curry2(_系统_心胸比)
    builtins["系统_股骨颈干角分类"] = _系统_股骨颈干角分类
    builtins["系统_股骨前倾角分类"] = _系统_股骨前倾角分类
    builtins["系统_颈椎曲度指数"] = _curry2(_系统_颈椎曲度指数)
    builtins["系统_腰椎Cobb角正切"] = _curry2(_系统_腰椎Cobb角正切)
    builtins["系统_骨盆入口指数"] = _curry2(_系统_骨盆入口指数)
    builtins["系统_脑室指数"] = _curry2(_系统_脑室指数)
    builtins["系统_主动脉Z值"] = _curry2(_系统_主动脉Z值)
    builtins["系统_椎管矢状径判定"] = _curry2(_系统_椎管矢状径判定)
    builtins["系统_视神经鞘判定"] = _系统_视神经鞘判定

    # ===== 二、局部解剖 =====
    builtins["局部_甲状腺体积"] = _curry3(_局部_甲状腺体积)
    builtins["局部_前列腺体积"] = _curry3(_局部_前列腺体积)
    builtins["局部_肝脏体积"] = _curry3(_局部_肝脏体积)
    builtins["局部_脾脏体积"] = _curry3(_局部_脾脏体积)
    builtins["局部_肾脏体积"] = _curry3(_局部_肾脏体积)
    builtins["局部_睾丸体积"] = _curry3(_局部_睾丸体积)
    builtins["局部_左室质量"] = _curry3(_局部_左室质量)
    builtins["局部_关节腔深度"] = _curry2(_局部_关节腔深度)

    # ===== 三、表面解剖 =====
    builtins["表面_体表面积Mosteller"] = _curry2(_表面_体表面积Mosteller)
    builtins["表面_体表面积DuBois"] = _curry2(_表面_体表面积DuBois)
    builtins["表面_烧伤九分法"] = _表面_烧伤九分法
    builtins["表面_椎体节段定位"] = _curry2(_表面_椎体节段定位)
    builtins["表面_经皮进针深度"] = _curry2(_表面_经皮进针深度)
    builtins["表面_体表标志间距"] = _curry2(_表面_体表标志间距)

    # ===== 四、影像解剖 =====
    builtins["影解_椎管矢状径"] = _影解_椎管矢状径
    builtins["影解_椎弓根间距"] = _影解_椎弓根间距
    builtins["影解_脊髓圆锥位置"] = _影解_脊髓圆锥位置
    builtins["影解_脑沟宽度"] = _curry2(_影解_脑沟宽度)
    builtins["影解_侧脑室前角宽度"] = _影解_侧脑室前角宽度
    builtins["影解_垂体高度判定"] = _影解_垂体高度判定
    builtins["影解_Evans指数"] = _curry2(_影解_Evans指数)
    builtins["影解_肺结节倍增时间"] = _curry3(_影解_肺结节倍增时间)

    # ===== 五、临床解剖 =====
    builtins["临解_心脏质量预测"] = _临解_心脏质量预测
    builtins["临解_肝脏质量预测"] = _临解_肝脏质量预测
    builtins["临解_脾脏质量预测"] = _临解_脾脏质量预测
    builtins["临解_肾脏质量预测"] = _临解_肾脏质量预测
    builtins["临解_脑质量预测"] = _临解_脑质量预测
    builtins["临解_血容量"] = _curry2(_临解_血容量)
    builtins["临解_肺总量预测"] = _curry2(_临解_肺总量预测)
    builtins["临解_脏器体重比"] = _curry2(_临解_脏器体重比)

    # ===== 数据库：骨骼分类 =====
    for k, v in SKELETON_COUNT.items():
        builtins[f"骨骼_{k}"] = v

    # ===== 数据库：脏器质量与比重 =====
    for k, spec in ORGAN_SPEC.items():
        builtins[f"脏器_{k}_质量"] = spec["mass_g"]
        builtins[f"脏器_{k}_比重"] = spec["density"]

    # ===== 数据库：血管参数 =====
    for k, spec in VESSEL_SPEC.items():
        builtins[f"血管_{k}_内径"] = spec["ID_mm"]
        builtins[f"血管_{k}_壁厚"] = spec["wall_mm"]
        builtins[f"血管_{k}_弹性"] = spec["E_MPa"]

    # ===== 数据库：椎管矢状径 =====
    for k, v in SPINAL_CANAL_SAG.items():
        builtins[f"椎管矢状径_{k}"] = v

    # ===== 数据库：椎弓根间距 =====
    for k, v in PEDICLE_DISTANCE.items():
        builtins[f"椎弓根距_{k}"] = v

    # ===== 数据库：心脏腔室 =====
    for chamber, spec in CARDIAC_CHAMBER.items():
        for param, val in spec.items():
            builtins[f"心脏_{chamber}_{param}"] = val

    # ===== 数据库：脑解剖参考值 =====
    for k, v in BRAIN_REF.items():
        builtins[f"脑参考_{k}"] = v

    # ===== 常量 =====
    builtins["解剖_椭球系数"] = ELLIPSOID_K
    builtins["解剖_男性血容量系数"] = BLOOD_VOL_ML_KG_M
    builtins["解剖_女性血容量系数"] = BLOOD_VOL_ML_KG_F
    builtins["解剖_DuBois常量"] = BSA_DUBOIS_K


# ========== 语义符号表 ==========

def _anatomy_symtab_names() -> list[str]:
    names: list[str] = []

    # 一、系统解剖
    for n in ["心胸比", "股骨颈干角分类", "股骨前倾角分类", "颈椎曲度指数",
              "腰椎Cobb角正切", "骨盆入口指数", "脑室指数", "主动脉Z值",
              "椎管矢状径判定", "视神经鞘判定"]:
        names.append(f"系统_{n}")

    # 二、局部解剖
    for n in ["甲状腺体积", "前列腺体积", "肝脏体积", "脾脏体积",
              "肾脏体积", "睾丸体积", "左室质量", "关节腔深度"]:
        names.append(f"局部_{n}")

    # 三、表面解剖
    for n in ["体表面积Mosteller", "体表面积DuBois", "烧伤九分法",
              "椎体节段定位", "经皮进针深度", "体表标志间距"]:
        names.append(f"表面_{n}")

    # 四、影像解剖
    for n in ["椎管矢状径", "椎弓根间距", "脊髓圆锥位置", "脑沟宽度",
              "侧脑室前角宽度", "垂体高度判定", "Evans指数", "肺结节倍增时间"]:
        names.append(f"影解_{n}")

    # 五、临床解剖
    for n in ["心脏质量预测", "肝脏质量预测", "脾脏质量预测", "肾脏质量预测",
              "脑质量预测", "血容量", "肺总量预测", "脏器体重比"]:
        names.append(f"临解_{n}")

    # 数据库：骨骼分类
    for k in SKELETON_COUNT:
        names.append(f"骨骼_{k}")

    # 数据库：脏器质量与比重
    for k in ORGAN_SPEC:
        names.append(f"脏器_{k}_质量")
        names.append(f"脏器_{k}_比重")

    # 数据库：血管参数
    for k in VESSEL_SPEC:
        names.append(f"血管_{k}_内径")
        names.append(f"血管_{k}_壁厚")
        names.append(f"血管_{k}_弹性")

    # 数据库：椎管矢状径
    for k in SPINAL_CANAL_SAG:
        names.append(f"椎管矢状径_{k}")

    # 数据库：椎弓根间距
    for k in PEDICLE_DISTANCE:
        names.append(f"椎弓根距_{k}")

    # 数据库：心脏腔室
    for chamber, spec in CARDIAC_CHAMBER.items():
        for param in spec:
            names.append(f"心脏_{chamber}_{param}")

    # 数据库：脑解剖参考值
    for k in BRAIN_REF:
        names.append(f"脑参考_{k}")

    # 常量
    for n in ["解剖_椭球系数", "解剖_男性血容量系数", "解剖_女性血容量系数", "解剖_DuBois常量"]:
        names.append(n)

    return names
