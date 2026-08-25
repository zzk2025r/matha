"""Matha 建筑学领域测试。

运行：python -m tests.test_architecture
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.architecture import (
    _architecture_symtab_names,
    THERMAL_CONDUCTIVITY, SURFACE_DENSITY, ABSORPTION_COEFF,
    BRICK_GRADE, MORTAR_GRADE, TIMBER_GRADE, FIRE_ZONE_LIMIT,
    GOLDEN_RATIO, BASIC_MODULE_MM, SABINE_K, MASS_LAW_K,
    CONCRETE_DENSITY, STEEL_DENSITY,
)


def _interp() -> Interpreter:
    i = Interpreter()
    i.run(parse(""))
    return i


def _call(src: str) -> list:
    out, _ = interpret(src)
    return out


def _semantic_ok(src: str) -> bool:
    prog = parse(src)
    ana = SemanticAnalyzer()
    ana.analyze(prog)
    return not any(e.severity == "error" for e in ana.errors)


# ===== 0. 注册性 =====
def test_ar_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _architecture_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个内建名全部注册")


def test_ar_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[建物_热阻(0.2)(1.74) + 建设_容积率(5000)(1000) + 建规_疏散宽度(200)(0.65)]"
    ok = _semantic_ok(src)
    assert ok, "内建触发语义错误"
    print("  ✓ 语义侧可直接引用")


# ===== 1. 建筑物理 =====
def test_thermal_resistance_and_transmittance():
    print("\n--- 热阻/传热系数/传热量 ---")
    i = _interp()
    R = i.call("建物_热阻", 0.24, 1.74)   # 240mm 钢筋混凝土
    assert abs(R - 0.24 / 1.74) < 1e-10
    U = i.call("建物_传热系数", 0.5)        # 总热阻 0.5
    assert abs(U - 2.0) < 1e-10
    phi = i.call("建物_传热量", 2.0, 20, 10)
    assert abs(phi - 400) < 1e-10
    print(f"  ✓ R={R:.4f}, U={U}, Φ={phi}W")


def test_sound_insulation_mass_law():
    print("\n--- 质量定律隔声 ---")
    i = _interp()
    tl_240 = i.call("建物_质量定律隔声", 432.0)   # 240 砖墙
    expected = 20 * math.log10(432.0) - 47
    assert abs(tl_240 - expected) < 1e-10
    tl_glass = i.call("建物_质量定律隔声", 25.0)
    expected2 = 20 * math.log10(25.0) - 47
    assert abs(tl_glass - expected2) < 1e-10
    assert tl_240 > tl_glass
    print(f"  ✓ 240砖墙→{tl_240:.1f}dB, 玻璃幕墙→{tl_glass:.1f}dB (墙>玻璃)")


def test_sabine_reverberation():
    print("\n--- Sabine 混响时间 ---")
    i = _interp()
    T = i.call("建物_Sabine混响时间", 200, 50)    # V=200m³, A=50
    assert abs(T - 0.161 * 200 / 50) < 1e-10
    A = i.call("建物_总吸声量", [50, 30, 20], [0.1, 0.5, 0.8])
    assert abs(A - (5 + 15 + 16)) < 1e-10
    print(f"  ✓ T={T:.4f}s, A={A}")


def test_ventilation_daylighting_dewpoint():
    print("\n--- 换气次数/采光系数/露点 ---")
    i = _interp()
    ach = i.call("建物_换气次数", 300, 100)        # Q=300m³/h, V=100m³
    assert abs(ach - 3.0) < 1e-10
    df = i.call("建物_采光系数", 500, 10000)        # 500 lux / 10000 lux
    assert abs(df - 5.0) < 1e-10
    td, cond = i.call("建物_露点判定", 20, 60)
    assert abs(td - 12.0) < 1e-10
    assert cond == False
    td2, cond2 = i.call("建物_露点判定", 20, 95)
    assert cond2 == True
    print(f"  ✓ ACH={ach}, DF={df}%, 20°C/60%RH→Td={td}°C(不结露); 20°C/95%RH→结露")


# ===== 2. 建筑材料 =====
def test_concrete_mix_and_reinforcement():
    print("\n--- 水灰比/配筋率 ---")
    i = _interp()
    wc = i.call("建材_水灰比反算", 30)              # f'c=30MPa
    expected = (22.0 / 30) ** (1.0 / 0.61)
    assert abs(wc - expected) < 1e-9
    rho = i.call("建材_配筋率", 1256, 250, 400)     # 4Φ20, b×d=250×400
    assert abs(rho - 1256 / (250 * 400)) < 1e-12
    print(f"  ✓ f'c=30MPa→w/c={wc:.4f}; ρ={rho:.5f}")


def test_mortar_and_masonry():
    print("\n--- 砂浆体积比/砖砌体强度 ---")
    i = _interp()
    c, s, w = i.call("建材_砂浆体积比", 1, 4, 0.6)
    total = 1 + 4 + 0.6
    assert abs(c - 1 / total) < 1e-12
    assert abs(s - 4 / total) < 1e-12
    assert abs(w - 0.6 / total) < 1e-12
    fm = i.call("建材_砖砌体抗压强度", 15.0, 7.5)   # MU15 + M7.5
    expected = 0.78 * math.sqrt(15 * 7.5) / 4.5
    assert abs(fm - expected) < 1e-10
    print(f"  ✓ 1:4:0.6→归一({c:.3f},{s:.3f},{w:.3f}); MU15+M7.5→f={fm:.3f}MPa")


def test_timber_and_steel_grade():
    print("\n--- 木材/钢材分级 ---")
    i = _interp()
    assert i.call("建材_木材强度分级", 18) == "TC17"
    assert i.call("建材_木材强度分级", 16) == "TC15"
    assert i.call("建材_木材强度分级", 14) == "TC13"
    assert i.call("建材_木材强度分级", 12) == "TC11"
    assert i.call("建材_木材强度分级", 10) == "不合格"
    assert i.call("建材_钢材屈服判定", 500) == "HRB500"
    assert i.call("建材_钢材屈服判定", 400) == "HRB400"
    assert i.call("建材_钢材屈服判定", 300) == "HPB300"
    assert i.call("建材_钢材屈服判定", 200) == "不合格"
    print("  ✓ 木材: 18→TC17, 12→TC11, 10→不合格; 钢材: 500→HRB500, 300→HPB300, 200→不合格")


def test_concrete_material_quantity():
    print("\n--- 混凝土材料用量 ---")
    i = _interp()
    cement, water, sand, stone = i.call("建材_混凝土材料用量", 1, 180, 0.5, 0.35)
    assert abs(cement - 360) < 1e-10            # 180/0.5
    total = 2400 - 360 - 180
    assert abs(sand - total * 0.35) < 1e-10
    assert abs(stone - total * 0.65) < 1e-10
    print(f"  ✓ 1m³ C30: 水泥{cement}kg 水{water}kg 砂{sand:.0f}kg 石{stone:.0f}kg")


def test_masonry_material_quantity():
    print("\n--- 砌体材料用量 ---")
    i = _interp()
    block, mortar = i.call("建材_砌体材料用量", 50, 0.24, 0.1)
    total = 50 * 0.24
    assert abs(block - total * 0.9) < 1e-10
    assert abs(mortar - total * 0.1) < 1e-10
    print(f"  ✓ 50m²×240mm墙: 砌块{block:.3f}m³, 砂浆{mortar:.3f}m³")


# ===== 3. 建筑设计 =====
def test_golden_ratio_and_modular():
    print("\n--- 黄金比例 & 模数协调 ---")
    i = _interp()
    phi = i.call("建设_黄金比例")
    assert abs(phi - GOLDEN_RATIO) < 1e-12
    assert abs(phi - (1 + math.sqrt(5)) / 2) < 1e-12
    dim = i.call("建设_模数协调", 12)             # 12M = 1200mm
    assert abs(dim - 1200) < 1e-10
    print(f"  ✓ φ={phi:.6f}, 12M={dim}mm")


def test_far_and_density():
    print("\n--- 容积率/建筑密度/绿地率 ---")
    i = _interp()
    far = i.call("建设_容积率", 5000, 1000)
    assert abs(far - 5.0) < 1e-10
    bd = i.call("建设_建筑密度", 500, 1000)
    assert abs(bd - 0.5) < 1e-10
    gr = i.call("建设_绿地率", 300, 1000)
    assert abs(gr - 0.3) < 1e-10
    avg = i.call("建设_人均面积", 120, 4)
    assert abs(avg - 30) < 1e-10
    print(f"  ✓ FAR={far}, 密度={bd}, 绿地率={gr}, 人均={avg}m²")


def test_height_limit_and_solar_spacing():
    print("\n--- 高度限值 & 日照间距 ---")
    i = _interp()
    h = i.call("建设_建筑高度限值", 45, 5)
    assert abs(h - 40) < 1e-10
    L = i.call("建设_日照间距系数", 30, 45)      # H=30, α=45°
    assert abs(L - 30) < 1e-10
    L2 = i.call("建设_日照间距系数", 30, 26.57)  # tan(26.57°)≈0.5
    assert abs(L2 - 60) < 0.5
    print(f"  ✓ 限高{h}m; 日照: H=30,tan45→L={L}m; tan26.57→L={L2:.0f}m")


# ===== 4. 建筑施工 =====
def test_earthwork_and_concrete_volume():
    print("\n--- 土方量/混凝土体积 ---")
    i = _interp()
    v_earth = i.call("建施_土方量棱柱法", 50, 10, 20)
    assert abs(v_earth - 50 * 30 / 2) < 1e-10
    v_conc = i.call("建施_混凝土体积", 6, 0.3, 0.4)
    assert abs(v_conc - 0.72) < 1e-10
    print(f"  ✓ 土方={v_earth}m³; 混凝土梁={v_conc}m³")


def test_rebar_and_formwork():
    print("\n--- 钢筋下料 & 模板面积 ---")
    i = _interp()
    L = i.call("建施_钢筋下料长度", 5000, 2, 12)   # 5000mm + 2×10×12
    assert abs(L - 5240) < 1e-10
    A_form = i.call("建施_模板面积", 6, 0.4)
    assert abs(A_form - 2 * (6 + 0.4) * 0.4) < 1e-10
    print(f"  ✓ 下料长={L}mm; 模板={A_form:.2f}m²")


def test_scaffold_crane_and_slope():
    print("\n--- 脚手架/塔吊/放坡 ---")
    i = _interp()
    N = i.call("建施_脚手架立杆承载力", 489, 205, 1.5)
    expected = 489 * 205 / 1.5 / 1000
    assert abs(N - expected) < 1e-9
    Q = i.call("建施_塔吊起重量", 800, 20)        # M=800kN·m, R=20m
    assert abs(Q - 40) < 1e-10
    K = i.call("建施_放坡系数", 3, 1.5)
    assert abs(K - 2.0) < 1e-10
    area = i.call("建施_抹灰面积", 5, 3, 2)        # 5×3-2
    assert abs(area - 13) < 1e-10
    print(f"  ✓ 立杆={N:.1f}kN; 塔吊={Q}kN; 放坡K={K}; 抹灰={area}m²")


# ===== 5. 建筑规范 =====
def test_egress_width_and_stair():
    print("\n--- 疏散宽度 & 楼梯宽度 ---")
    i = _interp()
    W = i.call("建规_疏散宽度", 200, 0.65)         # 200人 × 0.65/100
    assert abs(W - 1.3) < 1e-10
    assert i.call("建规_最小楼梯宽度", "居住建筑") == 1.10
    assert i.call("建规_最小楼梯宽度", "商业建筑") == 1.40
    assert i.call("建规_最小楼梯宽度", "学校") == 1.40
    print(f"  ✓ 200人→W={W}m; 居住楼梯1.1m, 商业1.4m")


def test_ventilation_fixture_parking():
    print("\n--- 通风/器具/停车 ---")
    i = _interp()
    Q = i.call("建规_通风换气量", 3, 100)          # ACH=3, V=100
    assert abs(Q - 300) < 1e-10
    fixtures = i.call("建规_卫生器具数", 200, 0.05)   # 200×0.05=10
    assert fixtures == 10
    parking = i.call("建规_停车位配建", 5000, 0.5)    # 5000×0.5/100=25
    assert parking == 25
    print(f"  ✓ 通风={Q}m³/h; 器具={fixtures}个; 停车={parking}位")


def test_travel_distance_and_fire_zone():
    print("\n--- 疏散距离 & 防火分区 ---")
    i = _interp()
    d1 = i.call("建规_疏散距离限值", "办公建筑", True)
    assert d1 == 50.0
    d2 = i.call("建规_疏散距离限值", "商业建筑", False)
    assert d2 == 25.0
    fz_office = i.call("建规_防火分区面积", "办公_多层")
    assert fz_office == 2500.0
    fz_under = i.call("建规_防火分区面积", "地下")
    assert fz_under == 500.0
    print(f"  ✓ 办公喷淋→{d1}m, 商业无喷淋→{d2}m; 办公多层={fz_office}m², 地下={fz_under}m²")


def test_window_floor_ratio():
    print("\n--- 窗地比 ---")
    i = _interp()
    assert i.call("建规_窗地比最小", "居住起居") == 0.125
    assert i.call("建规_窗地比最小", "教室") == 0.125
    assert i.call("建规_窗地比最小", "办公") == 0.10
    print("  ✓ 起居/教室=0.125, 办公=0.10")


# ===== 6. 数据库 =====
def test_databases():
    print("\n--- 数据库验证 ---")
    i = _interp()
    assert i.builtins["导热系数_钢筋混凝土"] == 1.74
    assert i.builtins["导热系数_聚苯板_EPS"] == 0.042
    assert i.builtins["导热系数_钢材"] == 58.0
    assert i.builtins["面密度_240砖墙"] == 432.0
    assert i.builtins["面密度_双层玻璃幕墙"] == 25.0
    assert i.builtins["吸声系数_吸声板_穿孔"] == 0.80
    assert i.builtins["吸声系数_观众_每人"] == 0.46
    assert i.builtins["砖等级_MU20"] == 20.0
    assert i.builtins["砂浆等级_M10"] == 10.0
    assert i.builtins["木材等级_TC17"] == 17.0
    assert i.builtins["防火分区_地下"] == 500.0
    assert i.builtins["建筑_黄金比例"] == GOLDEN_RATIO
    assert i.builtins["建筑_基本模数"] == 100.0
    assert i.builtins["建筑_Sabine常数"] == 0.161
    assert i.builtins["建筑_混凝土密度"] == 2400.0
    assert i.builtins["建筑_钢材密度"] == 7850.0
    print("  ✓ 导热/面密度/吸声/砖/砂浆/木材/防火/常量 全部正确")


# ===== 7. Matha 综合场景 =====
def test_matha_scenario_wall():
    print("\n--- 综合场景：外墙热工评估 ---")
    src = """
#：{
  d_concrete = 0.2
  lambda_concrete = 导热系数_钢筋混凝土
  R_concrete = 建物_热阻(d_concrete)(lambda_concrete)
  d_ins = 0.05
  lambda_ins = 导热系数_挤塑板_XPS
  R_ins = 建物_热阻(d_ins)(lambda_ins)
  R_total = R_concrete + R_ins
  U = 建物_传热系数(R_total)
  area = 20
  dT = 20
  heat = 建物_传热量(U)(area)(dT)
  [R_concrete]
  [R_ins]
  [U]
  [heat]
}
"""
    out = _call(src)
    R_conc, R_ins, U, heat = out
    assert abs(R_conc - 0.2 / 1.74) < 1e-9
    assert abs(R_ins - 0.05 / 0.030) < 1e-9
    R_total = 0.2 / 1.74 + 0.05 / 0.030
    assert abs(U - 1.0 / R_total) < 1e-9
    assert abs(heat - U * 20 * 20) < 1e-7
    print(f"  ✓ 200mm混凝土+50mm XPS: U={U:.3f} W/(m²·K), 20m²×20K→{heat:.1f}W")


def test_matha_scenario_office():
    print("\n--- 综合场景：办公建筑参数 ---")
    src = """
#：{
  GFA = 6000
  site = 1500
  far = 建设_容积率(GFA)(site)
  occupants = 300
  egress_W = 建规_疏散宽度(occupants)(0.65)
  stair_W = 建规_最小楼梯宽度("办公建筑")
  travel = 建规_疏散距离限值("办公建筑")(真)
  fire_zone = 建规_防火分区面积("办公_多层")
  [far]
  [egress_W]
  [stair_W]
  [travel]
  [fire_zone]
}
"""
    out = _call(src)
    far, egress_W, stair_W, travel, fire_zone = out
    assert abs(far - 4.0) < 1e-10
    assert abs(egress_W - 1.95) < 1e-10
    assert stair_W == 1.20
    assert travel == 50.0
    assert fire_zone == 2500.0
    print(f"  ✓ 6000/1500→FAR={far}; 300人疏散宽{egress_W}m; 楼梯{stair_W}m; 距离{travel}m; 防火{fire_zone}m²")


def test_matha_scenario_concrete_pour():
    print("\n--- 综合场景：混凝土浇筑计划 ---")
    src = """
#：{
  L = 6
  b = 0.3
  h = 0.5
  V = 建施_混凝土体积(L)(b)(h)
  water = 180
  wc = 0.5
  ws = 0.35
  mix = 建材_混凝土材料用量(V)(water)(wc)(ws)
  form = 建施_模板面积(L)(h)
  [V]
  [mix]
  [form]
}
"""
    out = _call(src)
    V, mix, form = out
    cement = mix[0]
    assert abs(V - 0.9) < 1e-10
    assert abs(cement - 0.9 * 360) < 1e-9
    assert abs(form - 2 * (6 + 0.5) * 0.5) < 1e-10
    print(f"  ✓ 0.9m³混凝土: 水泥{cement:.0f}kg, 模板{form:.1f}m²")


def test_matha_scenario_acoustics():
    print("\n--- 综合场景：教室声学设计 ---")
    src = """
#：{
  V_room = 200
  area_wall = 100
  area_floor = 50
  area_ceiling = 50
  alpha_wall = 吸声系数_抹灰砖墙
  alpha_floor = 吸声系数_木地板
  alpha_ceil = 吸声系数_吸声板_穿孔
  A1 = area_wall * alpha_wall + area_floor * alpha_floor + area_ceiling * alpha_ceil
  T1 = 建物_Sabine混响时间(V_room)(A1)
  [A1]
  [T1]
}
"""
    out = _call(src)
    A1, T1 = out
    expected_A = 100 * 0.03 + 50 * 0.10 + 50 * 0.80
    assert abs(A1 - expected_A) < 1e-9
    assert abs(T1 - 0.161 * 200 / A1) < 1e-9
    print(f"  ✓ A={A1}, T={T1:.3f}s")


def test_matha_scenario_residential():
    print("\n--- 综合场景：住宅规划指标 ---")
    src = """
#：{
  GFA = 8000
  footprint = 1500
  green = 2500
  site = 5000
  far = 建设_容积率(GFA)(site)
  bd = 建设_建筑密度(footprint)(site)
  gr = 建设_绿地率(green)(site)
  phi = 建筑_黄金比例
  parking = 建规_停车位配建(GFA)(0.5)
  [far]
  [bd]
  [gr]
  [phi]
  [parking]
}
"""
    out = _call(src)
    far, bd, gr, phi, parking = out
    assert abs(far - 1.6) < 1e-10
    assert abs(bd - 0.3) < 1e-10
    assert abs(gr - 0.5) < 1e-10
    assert abs(phi - GOLDEN_RATIO) < 1e-12
    assert parking == 40
    print(f"  ✓ FAR={far}, 密度={bd}, 绿地率={gr}, φ={phi:.4f}, 停车{parking}位")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_ar_registered_in_interp, test_ar_registered_in_semantic,
        test_thermal_resistance_and_transmittance,
        test_sound_insulation_mass_law, test_sabine_reverberation,
        test_ventilation_daylighting_dewpoint,
        test_concrete_mix_and_reinforcement, test_mortar_and_masonry,
        test_timber_and_steel_grade, test_concrete_material_quantity,
        test_masonry_material_quantity,
        test_golden_ratio_and_modular, test_far_and_density,
        test_height_limit_and_solar_spacing,
        test_earthwork_and_concrete_volume, test_rebar_and_formwork,
        test_scaffold_crane_and_slope,
        test_egress_width_and_stair, test_ventilation_fixture_parking,
        test_travel_distance_and_fire_zone, test_window_floor_ratio,
        test_databases,
        test_matha_scenario_wall, test_matha_scenario_office,
        test_matha_scenario_concrete_pour, test_matha_scenario_acoustics,
        test_matha_scenario_residential,
    ]
    for t in tests:
        t()
    print()
    print("✓✓✓", len(tests), "个建筑学领域测试全部通过 ✓✓✓")
