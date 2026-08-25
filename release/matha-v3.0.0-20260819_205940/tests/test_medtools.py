"""Matha 中医/西医医药工具器械领域测试。

运行：python -m tests.test_medtools
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.medtools import (
    _medtools_symtab_names,
    BONE_MEASURE, ANCIENT_DOSAGE_G, TOXIC_HERB_MAX,
    SUTURE_SPEC, MERIDIAN_CLOCK, VENT_DEFAULT,
    GRAVITY, ATM_KPA,
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
def test_mt_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _medtools_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个内建名全部注册")


def test_mt_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[中医_脉率分类(75) + 中药_古今剂量(1) + 设备_输液滴速(500)(20)]"
    ok = _semantic_ok(src)
    assert ok, "内建触发语义错误"
    print("  ✓ 语义侧可直接引用")


# ===== 1. 中医诊断与针灸 =====
def test_pulse_classification():
    print("\n--- 脉率分类 ---")
    i = _interp()
    assert i.call("中医_脉率分类", 50) == "迟脉"
    assert i.call("中医_脉率分类", 75) == "平脉"
    assert i.call("中医_脉率分类", 100) == "数脉"
    assert i.call("中医_脉率分类", 130) == "疾脉"
    print("  ✓ 50→迟脉, 75→平脉, 100→数脉, 130→疾脉")


def test_bone_measure_and_acupuncture():
    print("\n--- 骨度分寸 & 针刺深度 ---")
    i = _interp()
    val = i.call("中医_骨度分寸", "肘横纹至腕横纹")
    assert val == 12.0
    depth = i.call("中医_针刺深度", 30, 0.5)
    assert abs(depth - 15.0) < 1e-12
    print(f"  ✓ 肘→腕=12寸; 30mm×0.5=15mm针刺深度")


def test_moxa_and_cupping():
    print("\n--- 艾灸温度 & 拔罐负压 ---")
    i = _interp()
    T = i.call("中医_艾灸温度", 800, 3)
    assert abs(T - 800 * (3.0/3.0)**2) < 1e-10
    T_far = i.call("中医_艾灸温度", 800, 6)
    assert abs(T_far - 800 * (3.0/6.0)**2) < 1e-10  # 200
    F = i.call("中医_拔罐负压", 101.325, 3)
    delta_P = 101.325 * 0.4
    A = math.pi * (3/100)**2
    expected = delta_P * 1000 * A
    assert abs(F - expected) < 1e-10
    print(f"  ✓ 艾灸3cm→{T:.0f}°C, 6cm→{T_far:.0f}°C; 拔罐力={F:.2f}N")


def test_meridian_clock():
    print("\n--- 子午流注 ---")
    i = _interp()
    assert "胆经" in i.call("中医_子午流注", 23)
    assert "胆经" in i.call("中医_子午流注", 0)
    assert "心经" in i.call("中医_子午流注", 12)
    assert "脾经" in i.call("中医_子午流注", 10)
    print("  ✓ 23时→胆经, 12时→心经, 10时→脾经")


def test_tcm_misc():
    print("\n--- 体质指数/经穴间距/九针/耳穴 ---")
    i = _interp()
    bmi = i.call("中医_体质指数", 22, 20)
    assert abs(bmi - 22 * 1.2) < 1e-10
    dist = i.call("中医_经穴间距", "肘横纹至腕横纹", 0.0, 0.5)
    assert abs(dist - 6.0) < 1e-10
    assert "毫针" in i.call("中医_九针选用", 5)
    assert "长针" in i.call("中医_九针选用", 15)
    assert i.call("中医_耳穴分区", "CO") == "耳甲"
    print(f"  ✓ 体质={bmi}, 经穴距={dist}, 九针5mm→毫针, 耳穴CO→耳甲")


# ===== 2. 中药药剂 =====
def test_dosage_conversion():
    print("\n--- 古今剂量 & 煎煮浓缩 ---")
    i = _interp()
    g = i.call("中药_古今剂量", 3)  # 3两 汉代
    assert abs(g - 3 * 15.625) < 1e-10
    conc = i.call("中药_煎煮浓缩", 100, 200)
    assert abs(conc - 0.5) < 1e-12
    print(f"  ✓ 3两(汉)={g:.3f}g; 浓缩比={conc}")


def test_jun_chen_zuo_shi():
    print("\n--- 君臣佐使 ---")
    i = _interp()
    ratio = i.call("中药_君臣佐使", 9, 6, 3, 3)
    assert abs(ratio - 9.0 / 21) < 1e-10
    print(f"  ✓ 君9臣6佐3使3 → 君占{ratio*100:.1f}%")


def test_pediatric_dosing():
    print("\n--- 儿童 Clark & Young ---")
    i = _interp()
    clark = i.call("中药_儿童剂量Clark", 500, 20)
    assert abs(clark - 500 * 20 / 70) < 1e-10
    young = i.call("中药_儿童剂量Young", 500, 6)
    assert abs(young - 500 * 6 / 18) < 1e-10
    print(f"  ✓ Clark(20kg)={clark:.1f}; Young(6岁)={young:.1f}")


def test_herb_prep():
    print("\n--- 煎药水量/浸泡/毒性/折干/配伍 ---")
    i = _interp()
    water = i.call("中药_煎药水量", 100, 10)
    assert abs(water - 1000) < 1e-12
    soak = i.call("中药_浸泡时间", "根茎")
    assert soak == 40
    over, maxg = i.call("中药_毒性限量", "附子", 20)
    assert over == True and maxg == 15.0
    over2, maxg2 = i.call("中药_毒性限量", "附子", 10)
    assert over2 == False
    dry = i.call("中药_折干率", 300)
    assert abs(dry - 90.0) < 1e-10
    split = i.call("中药_分次服用", 400, 2)
    assert abs(split - 200) < 1e-12
    print(f"  ✓ 水={water}mL, 浸泡={soak}min, 附子20g超限, 折干={dry}g, 分次={split}mL")


# ===== 3. 手术器械与力学 =====
def test_suture_specs():
    print("\n--- 缝合线规格 ---")
    i = _interp()
    assert i.call("手术_缝合线张力", "4-0") == 9.0
    assert i.call("手术_缝合线直径", "4-0") == 0.15
    assert i.call("手术_缝合线张力", "2-0") == 25.0
    print("  ✓ 4-0→9N/0.15mm, 2-0→25N")


def test_surgical_mechanics():
    print("\n--- 缝合针/止血带/螺钉/克氏针 ---")
    i = _interp()
    mom = i.call("手术_缝合针弯矩", 5, 12)
    assert abs(mom - 60) < 1e-12
    cuff = i.call("手术_止血带压力", 30, 120)
    expected = 120 + 50 + (30/10) * 10
    assert abs(cuff - expected) < 1e-10
    pullout = i.call("手术_螺钉拔出力", 4.5, 1.8)
    assert abs(pullout - 50 * 4.5 * 1.8) < 1e-10
    k_wire = i.call("手术_克氏针选择", "桡骨")
    assert k_wire == 2.0
    print(f"  ✓ 弯矩={mom}N·mm, 止血带={cuff:.0f}mmHg, 拔出力={pullout}N, 克氏针={k_wire}mm")


def test_amplifier_and_traction():
    print("\n--- 放大镜/牵引/钳夹/电刀 ---")
    i = _interp()
    fov = i.call("手术_放大镜视野", 4, 80)
    assert abs(fov - 20) < 1e-12
    traction = i.call("手术_牵引重量", 70, 0.1)
    assert abs(traction - 7.0) < 1e-12
    clamp = i.call("手术_钳夹力", 10, 3)
    assert abs(clamp - 30) < 1e-12
    power = i.call("手术_电刀功率", "肌肉")
    assert power == 50
    print(f"  ✓ 4x→视野{fov}mm, 牵引{traction}kg, 钳夹{clamp}N, 电刀{power}W")


# ===== 4. 医疗设备与仪器 =====
def test_iv_and_pump():
    print("\n--- 输液滴速 & 注射泵 ---")
    i = _interp()
    drops = i.call("设备_输液滴速", 120, 20)
    assert abs(drops - 40.0) < 1e-10
    rate = i.call("设备_注射泵流速", 100, 10, 4)
    assert abs(rate - 2.5) < 1e-10
    print(f"  ✓ 120mL/h→{drops}滴/min; 100mg/10mg/mL/4h→{rate}mL/h")


def test_ventilator():
    print("\n--- 呼吸机参数 ---")
    i = _interp()
    MV = i.call("设备_分钟通气量", 500, 12)
    assert abs(MV - 6000) < 1e-12
    ie = i.call("设备_IE比校验", 1.0, 2.0)
    assert ie == "1:2"
    print(f"  ✓ MV={MV}mL/min; I:E={ie}")


def test_defib_and_ultrasound():
    print("\n--- 除颤/超声/血透/心电 ---")
    i = _interp()
    J = i.call("设备_除颤能量", 70, 2.0)
    assert abs(J - 140) < 1e-12
    depth = i.call("设备_超声穿透深度", 5)
    assert abs(depth - 8.0) < 1e-10
    uf = i.call("设备_血透超滤率", 2000, 4)
    assert abs(uf - 500) < 1e-12
    sr = i.call("设备_心电采样率", "诊断")
    assert sr == 500
    print(f"  ✓ 除颤70kg→{J}J; 超声5MHz→{depth}cm; 超滤={uf}mL/h; 采样={sr}Hz")


def test_pump_pressure_and_alarms():
    print("\n--- 输液泵压力 & 心率报警 ---")
    i = _interp()
    press = i.call("设备_输液泵压力限", 3)
    assert abs(press - 190) < 1e-10
    lo, hi = i.call("设备_心率报警限", 30)
    assert lo == 50 and hi == 120
    lo2, hi2 = i.call("设备_心率报警限", 0.5)
    assert lo2 == 80 and hi2 == 180
    print(f"  ✓ 管径3mm→{press}kPa; 成人报警{lo}-{hi}; 婴儿{lo2}-{hi2}")


# ===== 5. 康复器械与假体 =====
def test_prosthesis_and_wheelchair():
    print("\n--- 接受腔压力 & 轮椅推进力 ---")
    i = _interp()
    p = i.call("康复_接受腔压力", 700, 50)
    A_m2 = 50e-4
    expected = 700 / A_m2 / 1000
    assert abs(p - expected) < 1e-6
    f = i.call("康复_轮椅推进力", 70, 5)
    expected_f = 70 * GRAVITY * math.sin(math.radians(5))
    assert abs(f - expected_f) < 1e-10
    print(f"  ✓ 接受腔={p:.1f}kPa; 轮椅5°={f:.2f}N")


def test_spring_and_exoskeleton():
    print("\n--- 弹簧常数/外骨骼/接触应力 ---")
    i = _interp()
    k = i.call("康复_弹簧常数", 200, 10)
    assert abs(k - 20) < 1e-12
    torque = i.call("康复_外骨骼力矩", 50, 0.6)
    assert abs(torque - 30) < 1e-12
    stress = i.call("康复_关节接触应力", 3000, 500)
    assert abs(stress - 6.0) < 1e-12
    print(f"  ✓ k={k}N/mm; 外骨骼={torque}N·m; 接触={stress}MPa")


def test_tendon_and_wear():
    print("\n--- 肌腱张力/假体磨损/辅助器/压缩袜/CPM ---")
    i = _interp()
    tendon = i.call("康复_肌腱张力", 10, 50, 0.25)
    assert abs(tendon - 10 * 50 * 0.25) < 1e-10
    wear = i.call("康复_假体磨损", 2000, 1000000)
    assert abs(wear - 2000 * 1e6 * 1e-9) < 1e-6
    height = i.call("康复_辅助器高度", 170, 0.6)
    assert abs(height - 102) < 1e-10
    sock = i.call("康复_压缩袜压力", 40, 0.7)
    assert abs(sock - 28) < 1e-12
    cpm = i.call("康复_CPM角度增量", 90, 7)
    assert abs(cpm - 90/7) < 1e-10
    print(f"  ✓ 肌腱={tendon}N; 磨损={wear}mm³; 辅助器={height}cm; 压缩袜={sock}mmHg; CPM={cpm:.1f}°/d")


# ===== 6. 数据库 =====
def test_databases():
    print("\n--- 数据库验证 ---")
    i = _interp()
    assert i.builtins["骨度_肘横纹至腕横纹"] == 12.0
    assert i.builtins["古方剂量_汉代"] == 15.625
    assert i.builtins["毒药极量_附子"] == 15.0
    assert i.builtins["缝合线_4-0_抗拉"] == 9.0
    assert i.builtins["缝合线_4-0_直径"] == 0.15
    assert i.builtins["流注_子"] == "胆"
    assert i.builtins["呼吸机_成人_VT"] == 6.0
    assert i.builtins["呼吸机_成人_RR"] == 12
    assert i.builtins["g_重力"] == GRAVITY
    assert i.builtins["atm_kPa"] == ATM_KPA
    print("  ✓ 骨度/古方/毒药/缝合线/流注/呼吸机/常量 全部正确")


# ===== 7. Matha 综合场景 =====
def test_matha_scenario_acupuncture():
    print("\n--- 综合场景：针灸方案 ---")
    src = """
#：{
  bpm = 75
  pulse = 中医_脉率分类(bpm)
  landmark = "肘横纹至腕横纹"
  acu_dist = 中医_经穴间距(landmark)(0.0)(0.3)
  depth = 中医_针刺深度(25)(0.4)
  needle = 中医_九针选用(depth)
  meridian = 中医_子午流注(14)
  [pulse]
  [acu_dist]
  [depth]
  [needle]
  [meridian]
}
"""
    out = _call(src)
    pulse, acu_dist, depth, needle, meridian = out
    assert pulse == "平脉"
    assert abs(acu_dist - 3.6) < 1e-10
    assert abs(depth - 10) < 1e-10
    assert "毫针" in needle or "长针" in needle
    print(f"  ✓ 脉={pulse}, 穴距={acu_dist}寸, 深度={depth}mm, 针={needle}, 14时={meridian}")


def test_matha_scenario_herbal():
    print("\n--- 综合场景：中药煎制 ---")
    src = """
#：{
  herb_g = 120
  water = 中药_煎药水量(herb_g)(10)
  soak = 中药_浸泡时间("根茎")
  conc = 中药_煎煮浓缩(herb_g)(300)
  jun_ratio = 中药_君臣佐使(12)(9)(6)(3)
  child_dose = 中药_儿童剂量Young(300)(8)
  per_serving = 中药_分次服用(300)(2)
  [water]
  [soak]
  [conc]
  [jun_ratio]
  [child_dose]
  [per_serving]
}
"""
    out = _call(src)
    water, soak, conc, jun_ratio, child_dose, per_serving = out
    assert abs(water - 1200) < 1e-10
    assert soak == 40
    assert abs(conc - 0.4) < 1e-10
    expected_jun = 12.0 / 30
    assert abs(jun_ratio - expected_jun) < 1e-10
    expected_child = 300 * 8 / 20
    assert abs(child_dose - expected_child) < 1e-10
    assert abs(per_serving - 150) < 1e-10
    print(f"  ✓ 水={water}mL, 浸泡={soak}min, 浓缩={conc}, 君占={jun_ratio*100:.0f}%, 儿童={child_dose}mg, 每次={per_serving}mL")


def test_matha_scenario_surgical():
    print("\n--- 综合场景：手术器械 ---")
    src = """
#：{
  usp = "3-0"
  tensile = 手术_缝合线张力(usp)
  diameter = 手术_缝合线直径(usp)
  cuff_p = 手术_止血带压力(28)(130)
  pullout = 手术_螺钉拔出力(4.5)(1.8)
  k_wire = 手术_克氏针选择("股骨")
  power = 手术_电刀功率("肌肉")
  [tensile]
  [diameter]
  [cuff_p]
  [pullout]
  [k_wire]
  [power]
}
"""
    out = _call(src)
    tensile, diameter, cuff_p, pullout, k_wire, power = out
    assert tensile == 16.0
    assert diameter == 0.20
    expected_cuff = 130 + 50 + (28/10) * 10
    assert abs(cuff_p - expected_cuff) < 1e-10
    expected_pullout = 50 * 4.5 * 1.8
    assert abs(pullout - expected_pullout) < 1e-10
    assert k_wire == 3.0
    assert power == 50
    print(f"  ✓ 3-0→{tensile}N/{diameter}mm; 止血带={cuff_p:.0f}mmHg; 螺钉={pullout}N; 克氏针={k_wire}mm; 电刀={power}W")


def test_matha_scenario_equipment():
    print("\n--- 综合场景：医疗设备 ---")
    src = """
#：{
  mL_per_h = 125
  drops = 设备_输液滴速(mL_per_h)(20)
  MV = 设备_分钟通气量(450)(14)
  J = 设备_除颤能量(70)(2.0)
  depth = 设备_超声穿透深度(3.5)
  uf = 设备_血透超滤率(1500)(3)
  [drops]
  [MV]
  [J]
  [depth]
  [uf]
}
"""
    out = _call(src)
    drops, MV, J, depth, uf = out
    assert abs(drops - 125 * 20 / 60) < 1e-10
    assert abs(MV - 6300) < 1e-10
    assert abs(J - 140) < 1e-10
    assert abs(depth - 40 / 3.5) < 1e-10
    assert abs(uf - 500) < 1e-10
    print(f"  ✓ 滴速={drops:.1f}/min; MV={MV}mL/min; 除颤={J}J; 超声={depth:.1f}cm; 超滤={uf}mL/h")


def test_matha_scenario_rehab():
    print("\n--- 综合场景：康复器械 ---")
    src = """
#：{
  weight_N = 700
  area = 60
  pressure = 康复_接受腔压力(weight_N)(area)
  push = 康复_轮椅推进力(65)(3)
  k = 康复_弹簧常数(150)(5)
  torque = 康复_外骨骼力矩(40)(0.5)
  height = 康复_辅助器高度(170)(0.6)
  cpm = 康复_CPM角度增量(100)(5)
  [pressure]
  [push]
  [k]
  [torque]
  [height]
  [cpm]
}
"""
    out = _call(src)
    pressure, push, k, torque, height, cpm = out
    expected_p = 700 / (60e-4) / 1000
    assert abs(pressure - expected_p) < 1e-4
    expected_push = 65 * GRAVITY * math.sin(math.radians(3))
    assert abs(push - expected_push) < 1e-10
    assert abs(k - 30) < 1e-12
    assert abs(torque - 20) < 1e-12
    assert abs(height - 102) < 1e-10
    assert abs(cpm - 20) < 1e-10
    print(f"  ✓ 接受腔={pressure:.1f}kPa; 轮椅={push:.1f}N; k={k}N/mm; 外骨骼={torque}N·m; 辅助器={height}cm; CPM={cpm}°/d")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_mt_registered_in_interp, test_mt_registered_in_semantic,
        test_pulse_classification, test_bone_measure_and_acupuncture,
        test_moxa_and_cupping, test_meridian_clock, test_tcm_misc,
        test_dosage_conversion, test_jun_chen_zuo_shi,
        test_pediatric_dosing, test_herb_prep,
        test_suture_specs, test_surgical_mechanics,
        test_amplifier_and_traction,
        test_iv_and_pump, test_ventilator,
        test_defib_and_ultrasound, test_pump_pressure_and_alarms,
        test_prosthesis_and_wheelchair, test_spring_and_exoskeleton,
        test_tendon_and_wear,
        test_databases,
        test_matha_scenario_acupuncture, test_matha_scenario_herbal,
        test_matha_scenario_surgical, test_matha_scenario_equipment,
        test_matha_scenario_rehab,
    ]
    for t in tests:
        t()
    print()
    print("✓✓✓", len(tests), "个中医/西医医药工具器械领域测试全部通过 ✓✓✓")
