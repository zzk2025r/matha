"""Matha 领域扩展模块：建筑（Architecture）。

基于 Matha 数学基础与物理常量体系，演化建筑学子领域功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、建筑物理（Building Physics）- 前缀 建物_
  1) 热阻 R = d/λ（d 厚度 m，λ 导热系数 W/(m·K)）
  2) 传热系数 U = 1/ΣR（围护结构总热阻的倒数）
  3) 传热量 Φ = U·A·ΔT（W）
  4) 太阳辐射得热 SHGC = Q_solar / Q_incident
  5) 质量定律隔声 TL = 20·log₁₀(m) - 47（m 面密度 kg/m²）
  6) Sabine 混响时间 T = 0.161·V/A（V 房间体积 m³，A 总吸声量）
  7) 吸声量 A = Σ(α_i · S_i)
  8) 空气渗透换气次数 ACH = Q / V
  9) 采光系数 DF = (E_indoor / E_outdoor) × 100%
  10) 露点温度判定（基于室内温湿度）

二、建筑材料（Building Materials）- 前缀 建材_
  1) 混凝土水灰比 w/c = f'c 反算（Abrams 公式简化）
  2) 配筋率 ρ = As / (b·d)
  3) 砂浆配合比体积法
  4) 砖砌体抗压强度（按砖与砂浆等级查 GB 50003 表）
  5) 木材强度等级分类（按抗弯强度 f_m）
  6) 钢材屈服强度判定
  7) 混凝土配合比材料用量
  8) 砌体材料用量估算

三、建筑设计（Architectural Design）- 前缀 建设_
  1) 黄金比例 φ = (1+√5)/2
  2) 容积率 FAR = 总建筑面积 / 用地面积
  3) 建筑密度 = 建筑基底面积 / 用地面积
  4) 绿地率 = 绿地面积 / 用地面积
  5) 人均使用面积
  6) 模数协调：基本模数 1M = 100mm
  7) 建筑高度限值（按航空/日照）
  8) 日照间距系数

四、建筑施工（Construction）- 前缀 建施_
  1) 土方量（棱柱法）：V = L·(A1 + A2) / 2
  2) 混凝土体积：V = L·b·h
  3) 钢筋下料长度（含弯钩）
  4) 模板面积：A = 2·(L+h)·h
  5) 脚手架立杆承载力
  6) 塔吊起重量（按幅度查力矩）
  7) 开挖放坡系数 K = h/b
  8) 抹灰面积

五、建筑规范（Building Codes）- 前缀 建规_
  1) 疏散宽度 W = N × 宽度指标 / 100
  2) 最小楼梯宽度（按建筑类型）
  3) 通风换气量 Q = n × V_room
  4) 卫生器具数量（按使用人数）
  5) 停车位配建数（按建筑面积）
  6) 疏散距离限值
  7) 防火分区面积限值
  8) 自然采光最小窗地比

数据库：
  - 常用建筑材料导热系数 λ（混凝土/砖/木材/保温/玻璃/钢材）
  - 常用材料面密度（砌体墙/混凝土板/玻璃幕墙）
  - 常用吸声系数（混凝土/木地板/玻璃/窗帘/吸声板）
  - 砖与砂浆强度等级表
  - 木材强度等级表
  - 防火分区最大允许建筑面积（按耐火等级）

设计原则：
  - 与 anatomy / medical / medtools / structural / acoustics 保持一致：_curryN 柯里化、前缀区分
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

# 常用建筑材料导热系数 λ（W/(m·K)）
THERMAL_CONDUCTIVITY: dict[str, float] = {
    "钢筋混凝土": 1.74,
    "实心粘土砖": 0.81,
    "空心砖": 0.58,
    "松木_顺纹": 0.35,
    "松木_横纹": 0.17,
    "聚苯板_EPS": 0.042,
    "挤塑板_XPS": 0.030,
    "岩棉": 0.045,
    "加气混凝土": 0.22,
    "玻璃": 0.76,
    "钢材": 58.0,
    "铝合金": 203.0,
    "空气_密闭": 0.024,
    "石膏板": 0.33,
}

# 常用墙体/楼板面密度（kg/m²）
SURFACE_DENSITY: dict[str, float] = {
    "240砖墙": 432.0,
    "370砖墙": 666.0,
    "200混凝土墙": 480.0,
    "120混凝土楼板": 288.0,
    "180混凝土楼板": 432.0,
    "双层玻璃幕墙": 25.0,
    "加气混凝土_200": 120.0,
    "石膏板_12": 9.0,
}

# 常用材料吸声系数 α（按频率 500Hz 取代表值）
ABSORPTION_COEFF: dict[str, float] = {
    "混凝土_未处理": 0.05,
    "抹灰砖墙": 0.03,
    "木地板": 0.10,
    "玻璃窗": 0.18,
    "厚窗帘": 0.55,
    "吸声板_穿孔": 0.80,
    "地毯_厚": 0.60,
    "多孔吸声材料": 0.85,
    "座椅_软垫": 0.50,
    "观众_每人": 0.46,    # 每人吸声量
}

# 砖强度等级（MU 后数字 = 抗压强度 MPa）
BRICK_GRADE: dict[str, float] = {
    "MU30": 30.0, "MU25": 25.0, "MU20": 20.0,
    "MU15": 15.0, "MU10": 10.0, "MU7.5": 7.5,
}

# 砂浆强度等级
MORTAR_GRADE: dict[str, float] = {
    "M15": 15.0, "M10": 10.0, "M7.5": 7.5,
    "M5": 5.0, "M2.5": 2.5,
}

# 木材强度等级（按抗弯强度 f_m，GB 50005）
TIMBER_GRADE: dict[str, float] = {
    "TC17": 17.0, "TC15": 15.0, "TC13": 13.0, "TC11": 11.0,
    "TB20": 20.0, "TB17": 17.0, "TB15": 15.0,
}

# 防火分区最大允许建筑面积（m²，一级耐火等级）
FIRE_ZONE_LIMIT: dict[str, float] = {
    "居住建筑_多层": 2500.0,
    "居住建筑_高层": 1500.0,
    "办公_多层": 2500.0,
    "办公_高层": 1500.0,
    "商业_多层": 2500.0,
    "商业_高层": 1500.0,
    "地下": 500.0,
    "厂房_丙类": 3000.0,
}


# ========== 常量 ==========

GOLDEN_RATIO = (1.0 + math.sqrt(5.0)) / 2.0    # 黄金比例 φ ≈ 1.618
BASIC_MODULE_MM = 100.0                          # 基本模数 1M = 100mm
SABINE_K = 0.161                                 # Sabine 混响常数 (s/m)
MASS_LAW_K = 47.0                                # 质量定律隔声常数
AIR_DENSITY = 1.2                                # 空气密度 kg/m³
SPECIFIC_HEAT_AIR = 1005.0                       # 空气比热 J/(kg·K)
WATER_CEMENT_BASE = 0.45                         # 基准水灰比
CONCRETE_DENSITY = 2400.0                        # 混凝土密度 kg/m³
STEEL_DENSITY = 7850.0                           # 钢材密度 kg/m³
HOOK_LENGTH_90 = 10.0                            # 90° 弯钩增加长度 d 倍数（按钢筋直径）


# ========== 一、建筑物理 ==========

def _建物_热阻(d_m, lambda_val):
    """材料热阻 R = d/λ（m²·K/W）。"""
    if lambda_val == 0:
        return float("inf")
    return d_m / lambda_val


def _建物_传热系数(R_total):
    """传热系数 U = 1/ΣR（W/(m²·K)）。"""
    if R_total == 0:
        return 0.0
    return 1.0 / R_total


def _建物_传热量(U, area_m2, delta_T):
    """传热量 Φ = U·A·ΔT（W）。"""
    return U * area_m2 * delta_T


def _建物_太阳得热系数(Q_solar, Q_incident):
    """SHGC = Q_solar / Q_incident。"""
    if Q_incident == 0:
        return 0.0
    return Q_solar / Q_incident


def _建物_质量定律隔声(surface_density_kg_m2):
    """质量定律隔声 TL = 20·log₁₀(m) - 47（dB，m 面密度 kg/m²）。"""
    if surface_density_kg_m2 <= 0:
        return 0.0
    return 20.0 * math.log10(surface_density_kg_m2) - MASS_LAW_K


def _建物_Sabine混响时间(V_m3, A_total):
    """Sabine 公式 T = 0.161·V/A（s）。"""
    if A_total == 0:
        return float("inf")
    return SABINE_K * V_m3 / A_total


def _建物_总吸声量(areas_m2, coeffs):
    """吸声量 A = Σ(α_i · S_i)。areas 与 coeffs 等长列表。"""
    if len(areas_m2) != len(coeffs):
        return 0.0
    return sum(a * c for a, c in zip(areas_m2, coeffs))


def _建物_换气次数(Q_m3h, V_room_m3):
    """空气渗透换气次数 ACH = Q/V（次/h）。"""
    if V_room_m3 == 0:
        return 0.0
    return Q_m3h / V_room_m3


def _建物_采光系数(E_indoor, E_outdoor):
    """采光系数 DF = E_indoor/E_outdoor × 100（%）。"""
    if E_outdoor == 0:
        return 0.0
    return E_indoor / E_outdoor * 100.0


def _建物_露点判定(T_air_C, RH):
    """按室内温湿度估算露点温度（℃）并判定是否结露。
    简化：Td = T - (100 - RH)/5（Lawrence 近似）。"""
    Td = T_air_C - (100.0 - RH) / 5.0
    condensation = Td >= T_air_C - 1.0
    return (Td, condensation)


# ========== 二、建筑材料 ==========

def _建材_水灰比反算(fc_MPa, k=22.0, n=0.61):
    """Abrams 公式简化反算：f'c = A / (w/c)^n，给定 f'c 求 w/c。
    默认 A=22, n=0.61。"""
    if fc_MPa <= 0:
        return 0.0
    return (k / fc_MPa) ** (1.0 / n)


def _建材_配筋率(As_mm2, b_mm, d_mm):
    """配筋率 ρ = As / (b·d)。"""
    if b_mm * d_mm == 0:
        return 0.0
    return As_mm2 / (b_mm * d_mm)


def _建材_砂浆体积比(cement, sand, water):
    """砂浆体积配合比归一化：返回 (c/Σ, s/Σ, w/Σ)。"""
    total = cement + sand + water
    if total == 0:
        return (0.0, 0.0, 0.0)
    return (cement / total, sand / total, water / total)


def _建材_砖砌体抗压强度(brick_grade, mortar_grade):
    """按砖与砂浆等级（MU/M 后数值）查砌体抗压强度设计值（MPa）。
    简化公式：f = 0.78·√(砖·砂浆)/4.5（GB 50003 范围内拟合）。"""
    if brick_grade <= 0 or mortar_grade <= 0:
        return 0.0
    return 0.78 * math.sqrt(brick_grade * mortar_grade) / 4.5


def _建材_木材强度分级(f_m_MPa):
    """按抗弯强度判定木材等级：TC17/TC15/TC13/TC11 或不合格。"""
    if f_m_MPa >= 17:
        return "TC17"
    if f_m_MPa >= 15:
        return "TC15"
    if f_m_MPa >= 13:
        return "TC13"
    if f_m_MPa >= 11:
        return "TC11"
    return "不合格"


def _建材_钢材屈服判定(fy_MPa):
    """按屈服强度判定钢材级别（HPB300/HRB400/HRB500）。"""
    if fy_MPa >= 500:
        return "HRB500"
    if fy_MPa >= 400:
        return "HRB400"
    if fy_MPa >= 300:
        return "HPB300"
    return "不合格"


def _建材_混凝土材料用量(V_m3, water_kg, w_c, w_s=0.5):
    """按水灰比 w/c 与砂率 w_s 估算 V_m3 m³ 混凝土各材料总用量（kg）。
    water_kg 为每 m³ 用水量；返回 (水泥, 水, 砂, 石)。
    水泥 = 总用水/(w/c)；骨料总 = 总质量 - 水泥 - 总用水。"""
    if w_c == 0:
        return (0.0, 0.0, 0.0, 0.0)
    water_total = water_kg * V_m3
    cement = water_total / w_c
    total_mass = CONCRETE_DENSITY * V_m3
    agg_total = total_mass - cement - water_total
    sand = agg_total * w_s
    stone = agg_total * (1.0 - w_s)
    return (cement, water_total, sand, stone)


def _建材_砌体材料用量(wall_area_m2, thickness_m, mortar_ratio=0.1):
    """估算砌体材料用量（按面积/厚度）：返回 (砌块体积, 砂浆体积) m³。"""
    total_vol = wall_area_m2 * thickness_m
    mortar_vol = total_vol * mortar_ratio
    block_vol = total_vol * (1.0 - mortar_ratio)
    return (block_vol, mortar_vol)


# ========== 三、建筑设计 ==========

def _建设_黄金比例():
    """黄金比例 φ = (1+√5)/2 ≈ 1.6180339887。"""
    return GOLDEN_RATIO


def _建设_容积率(GFA_m2, site_area_m2):
    """容积率 FAR = 总建筑面积 / 用地面积。"""
    if site_area_m2 == 0:
        return 0.0
    return GFA_m2 / site_area_m2


def _建设_建筑密度(footprint_m2, site_area_m2):
    """建筑密度 = 建筑基底面积 / 用地面积（0~1）。"""
    if site_area_m2 == 0:
        return 0.0
    return footprint_m2 / site_area_m2


def _建设_绿地率(green_m2, site_area_m2):
    """绿地率 = 绿地面积 / 用地面积（0~1）。"""
    if site_area_m2 == 0:
        return 0.0
    return green_m2 / site_area_m2


def _建设_人均面积(total_area_m2, occupants):
    """人均使用面积 = 总面积 / 人数。"""
    if occupants == 0:
        return 0.0
    return total_area_m2 / occupants


def _建设_模数协调(base_module_count):
    """按模数倍数返回尺寸：n × 1M = n × 100mm。"""
    return base_module_count * BASIC_MODULE_MM


def _建设_建筑高度限值(aircraft_clear_m, solar_extra_m=0.0):
    """建筑高度限值 = 净空 - 余量（航空限高/日照叠加）。"""
    return max(0.0, aircraft_clear_m - solar_extra_m)


def _建设_日照间距系数(building_height_m, sun_altitude_deg):
    """日照间距系数 = H / tan(α)（α 太阳高度角）。
    返回 L = H/tan(α)（日照间距）。"""
    if sun_altitude_deg <= 0 or sun_altitude_deg >= 90:
        return float("inf")
    return building_height_m / math.tan(math.radians(sun_altitude_deg))


# ========== 四、建筑施工 ==========

def _建施_土方量棱柱法(L_m, A1_m2, A2_m2):
    """土方量棱柱法：V = L·(A1 + A2) / 2。"""
    return L_m * (A1_m2 + A2_m2) / 2.0


def _建施_混凝土体积(L_m, b_m, h_m):
    """混凝土体积 V = L·b·h（m³）。"""
    return L_m * b_m * h_m


def _建施_钢筋下料长度(L_design_mm, hook_count, d_mm=12):
    """钢筋下料长度 = 设计长 + 弯钩增加（每个 10d）。"""
    return L_design_mm + hook_count * HOOK_LENGTH_90 * d_mm


def _建施_模板面积(L_m, h_m):
    """矩形截面模板面积：A = 2·(L + h)·h（侧模+底模近似）。"""
    return 2.0 * (L_m + h_m) * h_m


def _建施_脚手架立杆承载力(A_mm2, f_MPa, safety_factor=1.5):
    """单根立杆承载力 N = A·f / K（kN）。"""
    return A_mm2 * f_MPa / safety_factor / 1000.0   # mm²·MPa / K = N → /1000 = kN


def _建施_塔吊起重量(moment_kNm, radius_m):
    """塔吊起重量 Q = M / R（kN，力矩 M / 幅度 R）。"""
    if radius_m == 0:
        return float("inf")
    return moment_kNm / radius_m


def _建施_放坡系数(h_m, b_m):
    """放坡系数 K = h / b（深度/放坡宽度）。"""
    if b_m == 0:
        return float("inf")
    return h_m / b_m


def _建施_抹灰面积(L_m, H_m, opening_m2=0.0):
    """墙面抹灰面积 = L·H - 洞口（m²）。"""
    return max(0.0, L_m * H_m - opening_m2)


# ========== 五、建筑规范 ==========

def _建规_疏散宽度(occupants, width_index_m_per_100=0.65):
    """疏散总宽度 W = N × 宽度指标 / 100（m）。"""
    return occupants * width_index_m_per_100 / 100.0


def _建规_最小楼梯宽度(building_type):
    """按建筑类型返回最小疏散楼梯宽度（m）。"""
    table = {
        "居住建筑": 1.10,
        "办公建筑": 1.20,
        "商业建筑": 1.40,
        "学校": 1.40,
        "医院": 1.30,
        "托幼": 1.20,
    }
    return table.get(building_type, 1.10)


def _建规_通风换气量(ACH, V_room_m3):
    """通风换气量 Q = ACH × V（m³/h）。"""
    return ACH * V_room_m3


def _建规_卫生器具数(occupants, fixture_index=0.05):
    """卫生器具数 = 使用人数 × 配建指标（每 20 人 1 个 → 0.05）。"""
    return int(occupants * fixture_index + 0.999)


def _建规_停车位配建(GFA_m2, parking_index_per_100m2=0.5):
    """停车位配建数 = 总建筑面积 × 指标 / 100（取整）。"""
    return int(GFA_m2 * parking_index_per_100m2 / 100.0 + 0.999)


def _建规_疏散距离限值(building_type, sprinklered=True):
    """疏散距离限值（m，按建筑类型与是否设喷淋）。"""
    table = {
        ("居住建筑", True): 40.0, ("居住建筑", False): 25.0,
        ("办公建筑", True): 50.0, ("办公建筑", False): 35.0,
        ("商业建筑", True): 35.0, ("商业建筑", False): 25.0,
        ("学校", True): 50.0, ("学校", False): 35.0,
    }
    return table.get((building_type, sprinklered), 30.0)


def _建规_防火分区面积(building_type):
    """防火分区最大允许建筑面积（m²，一级耐火）。"""
    return FIRE_ZONE_LIMIT.get(building_type, 2500.0)


def _建规_窗地比最小(room_type):
    """按房间类型返回最小窗地比（窗洞面积/房间面积）。"""
    table = {
        "居住起居": 0.125,
        "居住卧室": 0.125,
        "办公": 0.10,
        "教室": 0.125,
        "病房": 0.10,
        "辅助用房": 0.10,
    }
    return table.get(room_type, 0.10)


# ========== 注册 ==========

def _register_architecture(builtins: dict) -> None:
    """将建筑学子领域内建注册到解释器 builtins。"""

    # ===== 一、建筑物理 =====
    builtins["建物_热阻"] = _curry2(_建物_热阻)
    builtins["建物_传热系数"] = _建物_传热系数
    builtins["建物_传热量"] = _curry3(_建物_传热量)
    builtins["建物_太阳得热系数"] = _curry2(_建物_太阳得热系数)
    builtins["建物_质量定律隔声"] = _建物_质量定律隔声
    builtins["建物_Sabine混响时间"] = _curry2(_建物_Sabine混响时间)
    builtins["建物_总吸声量"] = _curry2(_建物_总吸声量)
    builtins["建物_换气次数"] = _curry2(_建物_换气次数)
    builtins["建物_采光系数"] = _curry2(_建物_采光系数)
    builtins["建物_露点判定"] = _curry2(_建物_露点判定)

    # ===== 二、建筑材料 =====
    builtins["建材_水灰比反算"] = _建材_水灰比反算
    builtins["建材_配筋率"] = _curry3(_建材_配筋率)
    builtins["建材_砂浆体积比"] = _curry3(_建材_砂浆体积比)
    builtins["建材_砖砌体抗压强度"] = _curry2(_建材_砖砌体抗压强度)
    builtins["建材_木材强度分级"] = _建材_木材强度分级
    builtins["建材_钢材屈服判定"] = _建材_钢材屈服判定
    builtins["建材_混凝土材料用量"] = _curry4(_建材_混凝土材料用量)
    builtins["建材_砌体材料用量"] = _curry3(_建材_砌体材料用量)

    # ===== 三、建筑设计 =====
    builtins["建设_黄金比例"] = _建设_黄金比例
    builtins["建设_容积率"] = _curry2(_建设_容积率)
    builtins["建设_建筑密度"] = _curry2(_建设_建筑密度)
    builtins["建设_绿地率"] = _curry2(_建设_绿地率)
    builtins["建设_人均面积"] = _curry2(_建设_人均面积)
    builtins["建设_模数协调"] = _建设_模数协调
    builtins["建设_建筑高度限值"] = _curry2(_建设_建筑高度限值)
    builtins["建设_日照间距系数"] = _curry2(_建设_日照间距系数)

    # ===== 四、建筑施工 =====
    builtins["建施_土方量棱柱法"] = _curry3(_建施_土方量棱柱法)
    builtins["建施_混凝土体积"] = _curry3(_建施_混凝土体积)
    builtins["建施_钢筋下料长度"] = _curry3(_建施_钢筋下料长度)
    builtins["建施_模板面积"] = _curry2(_建施_模板面积)
    builtins["建施_脚手架立杆承载力"] = _curry3(_建施_脚手架立杆承载力)
    builtins["建施_塔吊起重量"] = _curry2(_建施_塔吊起重量)
    builtins["建施_放坡系数"] = _curry2(_建施_放坡系数)
    builtins["建施_抹灰面积"] = _curry3(_建施_抹灰面积)

    # ===== 五、建筑规范 =====
    builtins["建规_疏散宽度"] = _curry2(_建规_疏散宽度)
    builtins["建规_最小楼梯宽度"] = _建规_最小楼梯宽度
    builtins["建规_通风换气量"] = _curry2(_建规_通风换气量)
    builtins["建规_卫生器具数"] = _curry2(_建规_卫生器具数)
    builtins["建规_停车位配建"] = _curry2(_建规_停车位配建)
    builtins["建规_疏散距离限值"] = _curry2(_建规_疏散距离限值)
    builtins["建规_防火分区面积"] = _建规_防火分区面积
    builtins["建规_窗地比最小"] = _建规_窗地比最小

    # ===== 数据库：导热系数 =====
    for k, v in THERMAL_CONDUCTIVITY.items():
        builtins[f"导热系数_{k}"] = v

    # ===== 数据库：面密度 =====
    for k, v in SURFACE_DENSITY.items():
        builtins[f"面密度_{k}"] = v

    # ===== 数据库：吸声系数 =====
    for k, v in ABSORPTION_COEFF.items():
        builtins[f"吸声系数_{k}"] = v

    # ===== 数据库：砖强度等级 =====
    for k, v in BRICK_GRADE.items():
        builtins[f"砖等级_{k}"] = v

    # ===== 数据库：砂浆强度等级 =====
    for k, v in MORTAR_GRADE.items():
        builtins[f"砂浆等级_{k}"] = v

    # ===== 数据库：木材强度等级 =====
    for k, v in TIMBER_GRADE.items():
        builtins[f"木材等级_{k}"] = v

    # ===== 数据库：防火分区限值 =====
    for k, v in FIRE_ZONE_LIMIT.items():
        builtins[f"防火分区_{k}"] = v

    # ===== 常量 =====
    builtins["建筑_黄金比例"] = GOLDEN_RATIO
    builtins["建筑_基本模数"] = BASIC_MODULE_MM
    builtins["建筑_Sabine常数"] = SABINE_K
    builtins["建筑_质量定律常数"] = MASS_LAW_K
    builtins["建筑_混凝土密度"] = CONCRETE_DENSITY
    builtins["建筑_钢材密度"] = STEEL_DENSITY


# ========== 语义符号表 ==========

def _architecture_symtab_names() -> list[str]:
    names: list[str] = []

    # 一、建筑物理
    for n in ["热阻", "传热系数", "传热量", "太阳得热系数", "质量定律隔声",
              "Sabine混响时间", "总吸声量", "换气次数", "采光系数", "露点判定"]:
        names.append(f"建物_{n}")

    # 二、建筑材料
    for n in ["水灰比反算", "配筋率", "砂浆体积比", "砖砌体抗压强度",
              "木材强度分级", "钢材屈服判定", "混凝土材料用量", "砌体材料用量"]:
        names.append(f"建材_{n}")

    # 三、建筑设计
    for n in ["黄金比例", "容积率", "建筑密度", "绿地率",
              "人均面积", "模数协调", "建筑高度限值", "日照间距系数"]:
        names.append(f"建设_{n}")

    # 四、建筑施工
    for n in ["土方量棱柱法", "混凝土体积", "钢筋下料长度", "模板面积",
              "脚手架立杆承载力", "塔吊起重量", "放坡系数", "抹灰面积"]:
        names.append(f"建施_{n}")

    # 五、建筑规范
    for n in ["疏散宽度", "最小楼梯宽度", "通风换气量", "卫生器具数",
              "停车位配建", "疏散距离限值", "防火分区面积", "窗地比最小"]:
        names.append(f"建规_{n}")

    # 数据库：导热系数
    for k in THERMAL_CONDUCTIVITY:
        names.append(f"导热系数_{k}")

    # 数据库：面密度
    for k in SURFACE_DENSITY:
        names.append(f"面密度_{k}")

    # 数据库：吸声系数
    for k in ABSORPTION_COEFF:
        names.append(f"吸声系数_{k}")

    # 数据库：砖/砂浆/木材/防火
    for k in BRICK_GRADE:
        names.append(f"砖等级_{k}")
    for k in MORTAR_GRADE:
        names.append(f"砂浆等级_{k}")
    for k in TIMBER_GRADE:
        names.append(f"木材等级_{k}")
    for k in FIRE_ZONE_LIMIT:
        names.append(f"防火分区_{k}")

    # 常量
    for n in ["建筑_黄金比例", "建筑_基本模数", "建筑_Sabine常数",
              "建筑_质量定律常数", "建筑_混凝土密度", "建筑_钢材密度"]:
        names.append(n)

    return names
