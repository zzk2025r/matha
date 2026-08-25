"""Matha 医疗与医药理疗领域测试：药代 + 药效 + 检验 + 影像放疗 + 理疗康复。

运行：python -m tests.test_medical
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.medical import (
    _medical_symtab_names,
    DRUG_HALFLIFE_H, W_RADIATION, W_TISSUE, MET_ACTIVITY,
    AB_TUMOR, AB_NORMAL, AB_CNS,
    MU_WATER, MU_BONE, MU_LUNG,
    ALPHA_SOFT, ALPHA_BONE,
    LN2,
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
def test_med_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _medical_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个医疗子领域内建名全部注册")


def test_med_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[药代_半衰期(0.1) + 检验_阴离子间隙(140)(102)(24) + 理疗_HRmax(30)]"
    ok = _semantic_ok(src)
    assert ok, "医疗内建触发语义错误"
    print("  ✓ 医疗内建在语义侧可直接引用")


# ===== 1. 药代动力学 =====
def test_ke_and_halflife():
    print("\n--- 消除速率常数 & 半衰期 ---")
    i = _interp()
    ke = i.call("药代_消除速率常数", 8)
    assert abs(ke - LN2 / 8) < 1e-15
    th_back = i.call("药代_半衰期", ke)
    assert abs(th_back - 8) < 1e-10
    print(f"  ✓ t½=8h → ke={ke:.5f}/h; 反推 t½={th_back:.4f}h")


def test_one_compartment_and_vd():
    print("\n--- 一室浓度 & 表观分布容积 ---")
    i = _interp()
    C0 = 20.0
    ke = 0.1
    t = 10
    C = i.call("药代_一室浓度", C0, ke, t)
    expected = C0 * math.exp(-ke * t)
    assert abs(C - expected) < 1e-12
    Vd = i.call("药代_表观分布容积", 500, 20)
    assert abs(Vd - 25) < 1e-12
    print(f"  ✓ C(10)={C:.4f} mg/L; Vd={Vd:.0f} L")


def test_clearance_and_steady_state():
    print("\n--- 清除率 & 稳态浓度 ---")
    i = _interp()
    CL = i.call("药代_清除率", 0.1, 25)
    assert abs(CL - 2.5) < 1e-12
    Css = i.call("药代_稳态浓度", 500, CL, 12)
    expected = 500 / (CL * 12)
    assert abs(Css - expected) < 1e-12
    print(f"  ✓ CL={CL:.1f}L/h; Css={Css:.2f} mg/L")


def test_bioavailability_auc_peak_trough():
    print("\n--- 生物利用度 & AUC & 峰谷浓度 ---")
    i = _interp()
    F = i.call("药代_生物利用度", 60, 100)
    assert abs(F - 0.6) < 1e-12
    auc = i.call("药代_AUC梯形", 0, 10, 4, 6)
    assert abs(auc - 32) < 1e-12
    Cmax = i.call("药代_峰浓度", 500, 25, 0.6)
    assert abs(Cmax - 12) < 1e-12
    Cmin = i.call("药代_谷浓度", 12, 0.1, 12)
    expected_min = 12 * math.exp(-0.1 * 12)
    assert abs(Cmin - expected_min) < 1e-12
    print(f"  ✓ F={F}; AUC={auc}; Cmax={Cmax}; Cmin={Cmin:.2f}")


def test_loading_dose():
    print("\n--- 负荷剂量 ---")
    i = _interp()
    LD = i.call("药代_负荷剂量", 10, 25, 1.0)
    assert abs(LD - 250) < 1e-12
    LD_po = i.call("药代_负荷剂量", 10, 25, 0.6)
    assert abs(LD_po - 10 * 25 / 0.6) < 1e-10
    print(f"  ✓ 静注 LD={LD}; 口服(F=0.6) LD={LD_po:.1f}")


# ===== 2. 药效学 =====
def test_emax_and_sigmoid():
    print("\n--- Emax & Sigmoid Emax ---")
    i = _interp()
    e_half = i.call("药效_Emax模型", 100, 10, 10)
    assert abs(e_half - 50) < 1e-12
    e_sat = i.call("药效_Emax模型", 100, 10, 10000)
    assert abs(e_sat - 100) < 0.1
    e_sig = i.call("药效_Sigmoid_Emax", 100, 10, 10, 2)
    assert abs(e_sig - 50) < 1e-10
    print(f"  ✓ Emax: C=EC50→{e_half}, C>>EC50→{e_sat:.1f}; Sigmoid(n=2): {e_sig}")


def test_therapeutic_index_and_safety():
    print("\n--- 治疗指数 & 安全范围 ---")
    i = _interp()
    TI = i.call("药效_治疗指数", 500, 50)
    assert abs(TI - 10) < 1e-12
    SR = i.call("药效_安全范围", 200, 50)
    assert abs(SR - 4) < 1e-12
    print(f"  ✓ TI={TI}; SR={SR}")


def test_antagonist_partial_agonist():
    print("\n--- 竞争拮抗 & 部分激动剂 & Hill 系数 ---")
    i = _interp()
    I_conc = i.call("药效_竞争拮抗浓度", 4, 2)
    assert abs(I_conc - 6) < 1e-12
    alpha = i.call("药效_部分激动剂活性", 50, 100)
    assert abs(alpha - 0.5) < 1e-12
    n = i.call("药效_量反应斜率", 1, 9)
    assert abs(n - 1.0) < 1e-10
    print(f"  ✓ [I]={I_conc}; α={alpha}; Hill n(ED16=1,ED84=9)={n}")


# ===== 3. 临床检验 =====
def test_creatinine_clearance_and_egfr():
    print("\n--- 肌酐清除率 & eGFR ---")
    i = _interp()
    cc_male = i.call("检验_肌酐清除率", 60, 70, 1.0, False)
    assert abs(cc_male - (80 * 70 / 72)) < 1e-10
    cc_female = i.call("检验_肌酐清除率", 60, 70, 1.0, True)
    assert abs(cc_female - cc_male * 0.85) < 1e-10
    egfr = i.call("检验_eGFR_MDRD", 1.0, 60, False, False)
    expected = 175 * (1.0 ** -1.154) * (60 ** -0.203)
    assert abs(egfr - expected) < 1e-6
    print(f"  ✓ 男CCr={cc_male:.1f}, 女CCr={cc_female:.1f}; eGFR={egfr:.1f}")


def test_anion_gap_and_osmolality():
    print("\n--- 阴离子间隙 & 渗透压 ---")
    i = _interp()
    AG = i.call("检验_阴离子间隙", 140, 102, 24)
    assert abs(AG - 14) < 1e-12
    Osm = i.call("检验_渗透压", 140, 90, 14)
    expected = 2 * 140 + 90 / 18 + 14 / 2.8
    assert abs(Osm - expected) < 1e-10
    print(f"  ✓ AG={AG}; Osm={Osm:.1f}")


def test_rbc_indices():
    print("\n--- 红细胞指数 MCV/MCH/MCHC ---")
    i = _interp()
    MCV = i.call("检验_MCV", 45, 5.0)
    assert abs(MCV - 90) < 1e-10
    MCH = i.call("检验_MCH", 150, 5.0)
    assert abs(MCH - 30) < 1e-10
    MCHC = i.call("检验_MCHC", 150, 0.45)
    assert abs(MCHC - 333.33) < 0.1
    print(f"  ✓ MCV={MCV:.0f}fL, MCH={MCH:.0f}pg, MCHC={MCHC:.0f}g/L")


def test_corrected_calcium_ag_na():
    print("\n--- 校正钙 & 校正AG & 校正钠 ---")
    i = _interp()
    Ca_c = i.call("检验_校正钙", 7.5, 2.0)
    assert abs(Ca_c - 9.1) < 1e-10
    AG_c = i.call("检验_白蛋白校正AG", 10, 2.0)
    assert abs(AG_c - 15) < 1e-10
    Na_c = i.call("检验_Na校正血糖", 130, 300)
    expected = 130 + 1.6 * (300 - 100) / 100
    assert abs(Na_c - expected) < 1e-10
    print(f"  ✓ Ca_corr={Ca_c}; AG_corr={AG_c}; Na_corr={Na_c}")


def test_free_water_and_esr():
    print("\n--- 游离水清除率 & 校正沉降率 ---")
    i = _interp()
    CH2O_iso = i.call("检验_游离水清除率", 100, 300, 300)
    assert abs(CH2O_iso - 0) < 1e-10
    CH2O_conc = i.call("检验_游离水清除率", 100, 600, 300)
    assert abs(CH2O_conc - (-100)) < 1e-10
    ESR_c = i.call("检验_校正沉降率", 20, 70, False)
    assert abs(ESR_c - 10) < 1e-10
    print(f"  ✓ 等渗CH2O={CH2O_iso}; 浓缩CH2O={CH2O_conc}; 校正ESR={ESR_c}")


# ===== 4. 影像与放疗 =====
def test_equivalent_and_effective_dose():
    print("\n--- 当量剂量 & 有效剂量 ---")
    i = _interp()
    H = i.call("影像_当量剂量", 0.01, 20)
    assert abs(H - 0.2) < 1e-12
    E = i.call("影像_有效剂量", 0.2, 0.12)
    assert abs(E - 0.024) < 1e-14
    print(f"  ✓ H(α)={H} Sv; E(肺)={E} Sv")


def test_hvl_and_activity_decay():
    print("\n--- 半值层 & 放射性活度衰变 ---")
    i = _interp()
    HVL = i.call("影像_半值层", 0.18)
    assert abs(HVL - LN2 / 0.18) < 1e-12
    A = i.call("影像_放射性活度", 100, 6, 6)
    assert abs(A - 50) < 1e-6
    print(f"  ✓ HVL(μ=0.18)={HVL:.3f}cm; 6h后活度={A:.1f}")


def test_ct_value_and_rbe():
    print("\n--- CT 值 & RBE ---")
    i = _interp()
    HU_water = i.call("影像_CT值", 0.18, 0.18)
    assert abs(HU_water - 0) < 1e-10
    HU_bone = i.call("影像_CT值", 0.48, 0.18)
    expected = 1000 * (0.48 - 0.18) / 0.18
    assert abs(HU_bone - expected) < 1e-6
    assert abs(i.call("影像_RBE", 0) - 1.0) < 1e-12
    assert abs(i.call("影像_RBE", 50) - 1.5) < 1e-12
    assert abs(i.call("影像_RBE", 100) - 2.0) < 1e-12
    print(f"  ✓ 水HU=0, 骨HU={HU_bone:.0f}; RBE(LET=0/50/100)=1.0/1.5/2.0")


def test_bed_eqd2_and_inverse_square():
    print("\n--- BED & EQD2 & 平方反比 ---")
    i = _interp()
    BED = i.call("影像_BED", 30, 2, 10)
    assert abs(BED - 30 * 2 * 1.2) < 1e-10
    EQD2 = i.call("影像_EQD2", 60, 3, 10)
    expected = 60 * (3 + 10) / (2 + 10)
    assert abs(EQD2 - expected) < 1e-10
    I2 = i.call("影像_平方反比", 100, 1, 2)
    assert abs(I2 - 25) < 1e-12
    print(f"  ✓ BED={BED}; EQD2={EQD2}; I2={I2}")


def test_hvl_attenuation():
    print("\n--- 半价层衰减分数 ---")
    i = _interp()
    assert abs(i.call("影像_半价层衰减", 0) - 1.0) < 1e-12
    assert abs(i.call("影像_半价层衰减", 1) - 0.5) < 1e-12
    assert abs(i.call("影像_半价层衰减", 3) - 0.125) < 1e-12
    print("  ✓ n=0→1, n=1→0.5, n=3→0.125")


# ===== 5. 理疗与康复 =====
def test_hrmax_and_karvonen():
    print("\n--- HRmax & Karvonen 心率储备 ---")
    i = _interp()
    HRmax = i.call("理疗_HRmax", 30)
    assert abs(HRmax - 190) < 1e-12
    THR = i.call("理疗_心率储备", 30, 70, 0.6)
    assert abs(THR - 142) < 1e-10
    THR_hi = i.call("理疗_心率储备", 30, 70, 0.8)
    assert abs(THR_hi - 166) < 1e-10
    print(f"  ✓ HRmax={HRmax}; 60%强度THR={THR}, 80%强度THR={THR_hi}")


def test_mets_vo2_and_borg():
    print("\n--- METs→VO2 & Borg→VO2max ---")
    i = _interp()
    VO2 = i.call("理疗_METs_VO2", 5)
    assert abs(VO2 - 17.5) < 1e-12
    VO2max = i.call("理疗_Borg_VO2", 12)
    expected = (12 - 4) * 3.5 + 3.5
    assert abs(VO2max - expected) < 1e-10
    print(f"  ✓ 5METs→VO2={VO2} mL/kg/min; Borg12→VO2max={VO2max}")


def test_calories_and_ultrasound():
    print("\n--- 代谢热量 & 超声衰减 ---")
    i = _interp()
    kcal = i.call("理疗_代谢热量", 5, 70, 30)
    expected = 5 * 3.5 * 70 * 30 / 200
    assert abs(kcal - expected) < 1e-10
    I = i.call("理疗_超声衰减", 1.0, 0.5, 2)
    expected_I = math.exp(-1.0)
    assert abs(I - expected_I) < 1e-12
    print(f"  ✓ 5METs/70kg/30min={kcal:.1f}kcal; 超声衰减I={I:.4f}")


def test_torque_gait_rom_fim():
    print("\n--- 力矩 & 步态 & ROM & FIM ---")
    i = _interp()
    tau = i.call("理疗_等长力矩", 100, 0.3)
    assert abs(tau - 30) < 1e-12
    v = i.call("理疗_步态速度", 0.7, 110)
    assert abs(v - 77) < 1e-10
    rom = i.call("理疗_关节活动度", 90, 120)
    assert abs(rom - 75) < 1e-10
    assert i.call("理疗_FIM分级", 126) == "完全独立"
    assert i.call("理疗_FIM分级", 110) == "轻度依赖"
    assert i.call("理疗_FIM分级", 100) == "中度依赖"
    assert i.call("理疗_FIM分级", 80) == "重度依赖"
    assert i.call("理疗_FIM分级", 50) == "极重依赖"
    assert i.call("理疗_FIM分级", 18) == "完全依赖"
    print(f"  ✓ τ={tau}N·m; v={v}m/min; ROM={rom}%; FIM全部分级正确")


# ===== 6. 数据库 & 常量 =====
def test_databases_and_constants():
    print("\n--- 数据库 & 常量 ---")
    i = _interp()
    assert i.builtins["药物半衰期_地高辛"] == DRUG_HALFLIFE_H["地高辛"]
    assert i.builtins["药物半衰期_万古霉素"] == DRUG_HALFLIFE_H["万古霉素"]
    assert i.builtins["辐射权重_光子"] == W_RADIATION["光子"]
    assert i.builtins["辐射权重_α粒子"] == W_RADIATION["α粒子"]
    assert i.builtins["组织权重_性腺"] == W_TISSUE["性腺"]
    assert i.builtins["组织权重_肺"] == W_TISSUE["肺"]
    assert i.builtins["METs_静坐"] == MET_ACTIVITY["静坐"]
    assert i.builtins["METs_跑步"] == MET_ACTIVITY["跑步"]
    assert i.builtins["ab_肿瘤"] == AB_TUMOR
    assert i.builtins["ab_正常"] == AB_NORMAL
    assert i.builtins["mu_水"] == MU_WATER
    assert i.builtins["alpha_软组织"] == ALPHA_SOFT
    print("  ✓ 14 药物半衰期 + 6 辐射权重 + 15 组织权重 + 10 METs + 3 α/β + 5 衰减系数 全部正确")


# ===== 7. Matha 侧综合场景 =====
def test_matha_scenario_dosing():
    print("\n--- 综合场景：药代给药方案 ---")
    src = """
#：{
  Dose = 500
  t_half = 药物半衰期_氨茶碱
  ke = 药代_消除速率常数(t_half)
  Vd = 25
  F = 0.9
  Cmax = 药代_峰浓度(Dose)(Vd)(F)
  tau = 8
  Cmin = 药代_谷浓度(Cmax)(ke)(tau)
  CL = 药代_清除率(ke)(Vd)
  Css = 药代_稳态浓度(Dose)(CL)(tau)
  [t_half]
  [ke]
  [Cmax]
  [Cmin]
  [Css]
}
"""
    out = _call(src)
    t_half, ke, Cmax, Cmin, Css = out
    assert abs(t_half - 8) < 1e-10
    expected_ke = math.log(2) / 8
    assert abs(ke - expected_ke) < 1e-12
    expected_Cmax = 500 * 0.9 / 25
    assert abs(Cmax - expected_Cmax) < 1e-10
    expected_Cmin = expected_Cmax * math.exp(-expected_ke * 8)
    assert abs(Cmin - expected_Cmin) < 1e-10
    print(f"  ✓ 氨茶碱 t½={t_half}h, ke={ke:.4f}; Cmax={Cmax:.1f}, Cmin={Cmin:.2f}, Css={Css:.2f}")


def test_matha_scenario_renal_assessment():
    print("\n--- 综合场景：肾功能评估 ---")
    src = """
#：{
  age = 65
  wt = 60
  SCr = 1.2
  is_f = false
  CCr = 检验_肌酐清除率(age)(wt)(SCr)(is_f)
  Na = 135
  Cl = 100
  HCO3 = 18
  AG = 检验_阴离子间隙(Na)(Cl)(HCO3)
  Alb = 3.0
  AG_corr = 检验_白蛋白校正AG(AG)(Alb)
  [CCr]
  [AG]
  [AG_corr]
}
"""
    out = _call(src)
    CCr, AG, AG_corr = out
    expected_ccr = (140 - 65) * 60 / (72 * 1.2)
    assert abs(CCr - expected_ccr) < 1e-6
    expected_ag = 135 - (100 + 18)
    assert abs(AG - expected_ag) < 1e-10
    expected_ag_corr = expected_ag + 2.5 * (4 - 3.0)
    assert abs(AG_corr - expected_ag_corr) < 1e-10
    print(f"  ✓ CCr={CCr:.1f}mL/min; AG={AG}; 白蛋白校正AG={AG_corr}")


def test_matha_scenario_radiotherapy():
    print("\n--- 综合场景：放疗方案 BED/EQD2 ---")
    src = """
#：{
  ab = ab_肿瘤
  n1 = 30
  d1 = 2
  BED1 = 影像_BED(n1)(d1)(ab)
  n2 = 20
  d2 = 3
  total2 = n2 * d2
  BED2 = 影像_BED(n2)(d2)(ab)
  EQD2_2 = 影像_EQD2(total2)(d2)(ab)
  [BED1]
  [BED2]
  [EQD2_2]
}
"""
    out = _call(src)
    BED1, BED2, EQD2_2 = out
    assert abs(BED1 - 30 * 2 * (1 + 2 / 10)) < 1e-10
    assert abs(BED2 - 20 * 3 * (1 + 3 / 10)) < 1e-10
    expected_eqd2 = 60 * (3 + 10) / (2 + 10)
    assert abs(EQD2_2 - expected_eqd2) < 1e-10
    print(f"  ✓ 30×2Gy BED={BED1}; 20×3Gy BED={BED2}, EQD2={EQD2_2}")


def test_matha_scenario_exercise_prescription():
    print("\n--- 综合场景：运动处方 ---")
    src = """
#：{
  age = 50
  HRrest = 70
  HRmax = 理疗_HRmax(age)
  THR_m = 理疗_心率储备(age)(HRrest)(0.6)
  THR_v = 理疗_心率储备(age)(HRrest)(0.85)
  METs = METs_跑步
  VO2 = 理疗_METs_VO2(METs)
  wt = 75
  t_min = 30
  kcal = 理疗_代谢热量(METs)(wt)(t_min)
  [HRmax]
  [THR_m]
  [THR_v]
  [VO2]
  [kcal]
}
"""
    out = _call(src)
    HRmax, THR_m, THR_v, VO2, kcal = out
    assert abs(HRmax - 170) < 1e-10
    assert abs(THR_m - (170 - 70) * 0.6 - 70) < 1e-10
    assert abs(THR_v - (170 - 70) * 0.85 - 70) < 1e-10
    assert abs(VO2 - 3.5 * 10) < 1e-10
    expected_kcal = 10 * 3.5 * 75 * 30 / 200
    assert abs(kcal - expected_kcal) < 1e-10
    print(f"  ✓ 50岁: HRmax={HRmax}, 中强度THR={THR_m:.0f}, 高强度THR={THR_v:.0f}")
    print(f"    跑步10METs→VO2={VO2}; 30min消耗={kcal:.0f}kcal")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_med_registered_in_interp, test_med_registered_in_semantic,
        test_ke_and_halflife, test_one_compartment_and_vd,
        test_clearance_and_steady_state, test_bioavailability_auc_peak_trough,
        test_loading_dose,
        test_emax_and_sigmoid, test_therapeutic_index_and_safety,
        test_antagonist_partial_agonist,
        test_creatinine_clearance_and_egfr, test_anion_gap_and_osmolality,
        test_rbc_indices, test_corrected_calcium_ag_na, test_free_water_and_esr,
        test_equivalent_and_effective_dose, test_hvl_and_activity_decay,
        test_ct_value_and_rbe, test_bed_eqd2_and_inverse_square, test_hvl_attenuation,
        test_hrmax_and_karvonen, test_mets_vo2_and_borg,
        test_calories_and_ultrasound, test_torque_gait_rom_fim,
        test_databases_and_constants,
        test_matha_scenario_dosing, test_matha_scenario_renal_assessment,
        test_matha_scenario_radiotherapy, test_matha_scenario_exercise_prescription,
    ]
    for t in tests:
        t()
    print()
    print("✓✓✓", len(tests), "个医疗与医药理疗领域测试全部通过 ✓✓✓")
