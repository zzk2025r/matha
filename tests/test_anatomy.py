"""Matha 解剖学领域测试。

运行：python -m tests.test_anatomy
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.anatomy import (
    _anatomy_symtab_names,
    SKELETON_COUNT, ORGAN_SPEC, VESSEL_SPEC,
    SPINAL_CANAL_SAG, PEDICLE_DISTANCE, CARDIAC_CHAMBER, BRAIN_REF,
    ELLIPSOID_K, BLOOD_VOL_ML_KG_M, BLOOD_VOL_ML_KG_F,
    HEART_MASS_FRAC, LIVER_MASS_FRAC, SPLEEN_MASS_FRAC,
    KIDNEY_MASS_FRAC, BRAIN_MASS_FRAC,
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
def test_an_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _anatomy_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个内建名全部注册")


def test_an_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[系统_心胸比(150)(300) + 局部_甲状腺体积(15)(12)(8) + 临解_血容量(70)(真)]"
    ok = _semantic_ok(src)
    assert ok, "内建触发语义错误"
    print("  ✓ 语义侧可直接引用")


# ===== 1. 系统解剖 =====
def test_cardiothoracic_ratio():
    print("\n--- 心胸比 ---")
    i = _interp()
    ctr = i.call("系统_心胸比", 150, 300)
    assert abs(ctr - 0.5) < 1e-12
    big = i.call("系统_心胸比", 170, 300)
    assert abs(big - 0.5667) < 1e-3
    print(f"  ✓ 150/300→{ctr} (正常), 170/300→{big:.4f} (>0.5 增大)")


def test_femur_angles():
    print("\n--- 股骨颈干角/前倾角分类 ---")
    i = _interp()
    assert i.call("系统_股骨颈干角分类", 100) == "髋内翻"
    assert i.call("系统_股骨颈干角分类", 125) == "正常"
    assert i.call("系统_股骨颈干角分类", 150) == "髋外翻"
    assert i.call("系统_股骨前倾角分类", 0) == "后倾"
    assert i.call("系统_股骨前倾角分类", 12) == "正常"
    assert i.call("系统_股骨前倾角分类", 30) == "异常前倾"
    print("  ✓ 颈干角 100→内翻/125→正常/150→外翻; 前倾角 0→后倾/12→正常/30→异常前倾")


def test_spinal_and_pelvic_indices():
    print("\n--- 颈椎/腰椎Cobb/骨盆/脑室指数 ---")
    i = _interp()
    idx = i.call("系统_颈椎曲度指数", 3, 25)
    assert abs(idx - 0.12) < 1e-12
    cobb = i.call("系统_腰椎Cobb角正切", 10, 10)
    assert abs(cobb - 45.0) < 1e-10
    pel = i.call("系统_骨盆入口指数", 110, 130)
    assert abs(pel - 110/130) < 1e-12
    vent = i.call("系统_脑室指数", 30, 100)
    assert abs(vent - 0.3) < 1e-12
    print(f"  ✓ 颈椎={idx}, Cobb={cobb}°, 骨盆={pel:.4f}, 脑室={vent}")


def test_aortic_z_and_canal():
    print("\n--- 主动脉Z值/椎管/视神经鞘 ---")
    i = _interp()
    z = i.call("系统_主动脉Z值", 30, 1.5)
    expected = (30 - (14.4 + 1.5 * 9.5)) / 1.5
    assert abs(z - expected) < 1e-10
    narrow, ref = i.call("系统_椎管矢状径判定", "颈椎_C5", 12)
    assert narrow == True and ref == 14.0
    ok, ref2 = i.call("系统_椎管矢状径判定", "腰椎_L3", 18)
    assert ok == False and ref2 == 18.0
    res, thr = i.call("系统_视神经鞘判定", 6.0)
    assert res == "阳性"
    res2, _ = i.call("系统_视神经鞘判定", 5.0)
    assert res2 == "阴性"
    print(f"  ✓ Z值={z:.3f}; 颈椎12mm狭窄, 腰椎18mm正常; ONSD 6mm→阳性, 5mm→阴性")


# ===== 2. 局部解剖 =====
def test_thyroid_prostate_volume():
    print("\n--- 甲状腺/前列腺体积 ---")
    i = _interp()
    v1 = i.call("局部_甲状腺体积", 15, 12, 8)
    expected = ELLIPSOID_K * 15 * 12 * 8 / 1000.0
    assert abs(v1 - expected) < 1e-10
    v2 = i.call("局部_前列腺体积", 40, 30, 35)
    expected2 = ELLIPSOID_K * 40 * 30 * 35 / 1000.0
    assert abs(v2 - expected2) < 1e-10
    print(f"  ✓ 甲状腺={v1:.2f}mL; 前列腺={v2:.2f}mL")


def test_organ_volumes():
    print("\n--- 肝/脾/肾/睾丸体积 ---")
    i = _interp()
    liver = i.call("局部_肝脏体积", 150, 100, 120)
    assert abs(liver - 0.55 * 150 * 100 * 120 / 1000) < 1e-10
    spleen = i.call("局部_脾脏体积", 100, 50, 40)
    assert abs(spleen - ELLIPSOID_K * 100 * 50 * 40 / 1000) < 1e-10
    kidney = i.call("局部_肾脏体积", 100, 50, 40)
    assert abs(kidney - ELLIPSOID_K * 100 * 50 * 40 / 1000) < 1e-10
    testis = i.call("局部_睾丸体积", 40, 25, 20)
    assert abs(testis - ELLIPSOID_K * 40 * 25 * 20 / 1000) < 1e-10
    print(f"  ✓ 肝={liver:.1f}mL, 脾={spleen:.2f}mL, 肾={kidney:.2f}mL, 睾丸={testis:.2f}mL")


def test_lv_mass_and_joint():
    print("\n--- 左室质量 & 关节腔深度 ---")
    i = _interp()
    lvm = i.call("局部_左室质量", 10, 50, 10)
    sum3 = 10 + 50 + 10
    expected = (0.8 * (1.04 * (sum3 ** 3) - (50 ** 3)) + 0.6) / 1000.0
    assert abs(lvm - expected) < 1e-9
    depth = i.call("局部_关节腔深度", 30, 5)
    assert abs(depth - 25) < 1e-12
    print(f"  ✓ LVM={lvm:.2f}g; 关节腔={depth}mm")


# ===== 3. 表面解剖 =====
def test_body_surface_area():
    print("\n--- 体表面积 Mosteller & DuBois ---")
    i = _interp()
    bsa1 = i.call("表面_体表面积Mosteller", 170, 70)
    assert abs(bsa1 - math.sqrt(170 * 70 / 3600)) < 1e-12
    bsa2 = i.call("表面_体表面积DuBois", 170, 70)
    assert abs(bsa2 - 0.007184 * (70 ** 0.425) * (170 ** 0.725)) < 1e-12
    assert abs(bsa1 - bsa2) < 0.1
    print(f"  ✓ Mosteller={bsa1:.4f}m², DuBois={bsa2:.4f}m²")


def test_burn_rule_of_nines():
    print("\n--- 烧伤九分法 ---")
    i = _interp()
    assert i.call("表面_烧伤九分法", "头颈") == 9.0
    assert i.call("表面_烧伤九分法", "右上肢") == 9.0
    assert i.call("表面_烧伤九分法", "躯干前") == 18.0
    assert i.call("表面_烧伤九分法", "会阴") == 1.0
    assert i.call("表面_烧伤九分法", "右下肢") == 18.0
    print("  ✓ 头颈9, 上肢9, 躯干18, 会阴1, 下肢18")


def test_landmark_and_needle():
    print("\n--- 椎体定位/进针深度/体表标志 ---")
    i = _interp()
    seg = i.call("表面_椎体节段定位", 100, 25)
    assert seg == 4
    depth = i.call("表面_经皮进针深度", 40, 5)
    assert abs(depth - 45) < 1e-12
    dist = i.call("表面_体表标志间距", "剑突", "脐")
    assert dist == 16.0
    dist2 = i.call("表面_体表标志间距", "脐", "剑突")
    assert dist2 == 16.0
    print(f"  ✓ 节段={seg}, 进针={depth}mm, 剑突↔脐={dist}cm")


# ===== 4. 影像解剖 =====
def test_spinal_canal_ref():
    print("\n--- 椎管/椎弓根参考值 ---")
    i = _interp()
    assert i.call("影解_椎管矢状径", "颈椎_C5") == 14.0
    assert i.call("影解_椎管矢状径", "腰椎_L3") == 18.0
    assert i.call("影解_椎弓根间距", "颈椎") == 28.0
    assert i.call("影解_椎弓根间距", "腰椎下") == 30.0
    print("  ✓ C5=14mm, L3=18mm; 颈椎椎弓根28mm, 腰椎下30mm")


def test_conus_and_brain():
    print("\n--- 圆锥位置/脑沟/前角/垂体 ---")
    i = _interp()
    assert i.call("影解_脊髓圆锥位置", "L1") == "正常"
    assert i.call("影解_脊髓圆锥位置", "L3") == "圆锥低位"
    assert i.call("影解_脑沟宽度", 40, 3) == "正常"
    assert i.call("影解_脑沟宽度", 40, 6) == "脑沟增宽"
    assert i.call("影解_脑沟宽度", 70, 5) == "正常"
    assert i.call("影解_侧脑室前角宽度", 40) == 30.0
    assert i.call("影解_侧脑室前角宽度", 70) == 35.0
    res, _ = i.call("影解_垂体高度判定", 12)
    assert res == "增大"
    res2, _ = i.call("影解_垂体高度判定", 6)
    assert res2 == "正常"
    print("  ✓ L1正常/L3低位; 脑沟分龄判定; 前角30/35mm; 垂体12mm增大")


def test_evans_and_nodule():
    print("\n--- Evans指数 & 肺结节倍增时间 ---")
    i = _interp()
    ev = i.call("影解_Evans指数", 30, 150)
    assert abs(ev - 0.2) < 1e-12
    dt = i.call("影解_肺结节倍增时间", 10, 12.6, 30)
    V0 = math.pi / 6 * 10**3
    V1 = math.pi / 6 * 12.6**3
    expected = math.log(2) * 30 / math.log(V1 / V0)
    assert abs(dt - expected) < 1e-9
    print(f"  ✓ Evans={ev}; 结节10→12.6mm/30d → 倍增{dt:.1f}天")


# ===== 5. 临床解剖 =====
def test_organ_mass_pred():
    print("\n--- 脏器质量预测 ---")
    i = _interp()
    h = i.call("临解_心脏质量预测", 70)
    assert abs(h - 70 * HEART_MASS_FRAC * 1000) < 1e-10
    li = i.call("临解_肝脏质量预测", 70)
    assert abs(li - 70 * LIVER_MASS_FRAC * 1000) < 1e-10
    sp = i.call("临解_脾脏质量预测", 70)
    assert abs(sp - 70 * SPLEEN_MASS_FRAC * 1000) < 1e-10
    kd = i.call("临解_肾脏质量预测", 70)
    assert abs(kd - 70 * KIDNEY_MASS_FRAC * 1000 * 2) < 1e-10
    br = i.call("临解_脑质量预测", 70)
    assert abs(br - 70 * BRAIN_MASS_FRAC * 1000) < 1e-10
    print(f"  ✓ 70kg: 心={h:.1f}g 肝={li:.1f}g 脾={sp:.1f}g 双肾={kd:.1f}g 脑={br:.1f}g")


def test_blood_and_lung_volume():
    print("\n--- 血容量 & 肺总量预测 ---")
    i = _interp()
    bm = i.call("临解_血容量", 70, True)
    assert abs(bm - 70 * BLOOD_VOL_ML_KG_M) < 1e-10
    bf = i.call("临解_血容量", 60, False)
    assert abs(bf - 60 * BLOOD_VOL_ML_KG_F) < 1e-10
    lm = i.call("临解_肺总量预测", 175, True)
    assert abs(lm - (50 * 175 - 4500)) < 1e-10
    lf = i.call("临解_肺总量预测", 160, False)
    assert abs(lf - (45 * 160 - 4000)) < 1e-10
    print(f"  ✓ 男70kg={bm}mL, 女60kg={bf}mL; 男175cm={lm}mL, 女160cm={lf}mL")


def test_organ_to_weight_ratio():
    print("\n--- 脏器体重比 ---")
    i = _interp()
    r = i.call("临解_脏器体重比", 300, 70)
    assert abs(r - 300 / 70000) < 1e-12
    print(f"  ✓ 心300g/70kg → {r:.5f} ({r*100:.3f}%)")


# ===== 6. 数据库 =====
def test_databases():
    print("\n--- 数据库验证 ---")
    i = _interp()
    assert i.builtins["骨骼_总计"] == 206
    assert i.builtins["骨骼_颅骨"] == 29
    assert i.builtins["骨骼_躯干骨"] == 51
    assert i.builtins["骨骼_上肢骨"] == 64
    assert i.builtins["骨骼_下肢骨"] == 62
    assert i.builtins["脏器_心_质量"] == 300.0
    assert i.builtins["脏器_肝_比重"] == 1.05
    assert i.builtins["脏器_脑_比重"] == 1.04
    assert i.builtins["血管_主动脉_内径"] == 25.0
    assert i.builtins["血管_冠状动脉_壁厚"] == 0.5
    assert i.builtins["椎管矢状径_颈椎_C3"] == 14.0
    assert i.builtins["椎弓根距_颈椎"] == 28.0
    assert i.builtins["心脏_左室_LVDd_mm"] == 50.0
    assert i.builtins["心脏_室间隔_IVSd_mm"] == 10.0
    assert i.builtins["脑参考_垂体高度_mm"] == 6.0
    assert i.builtins["解剖_椭球系数"] == ELLIPSOID_K
    assert i.builtins["解剖_DuBois常量"] == 0.007184
    print("  ✓ 骨骼/脏器/血管/椎管/椎弓根/心脏/脑参考/常量 全部正确")


# ===== 7. Matha 综合场景 =====
def test_matha_scenario_cardiac():
    print("\n--- 综合场景：心脏评估 ---")
    src = """
#：{
  cardiac_TD = 150
  thoracic_TD = 300
  ctr = 系统_心胸比(cardiac_TD)(thoracic_TD)
  IVSd = 10
  LVDd = 50
  LVPWd = 10
  lvm = 局部_左室质量(IVSd)(LVDd)(LVPWd)
  bw = 70
  pred_h = 临解_心脏质量预测(bw)
  ratio = 临解_脏器体重比(pred_h)(bw)
  [ctr]
  [lvm]
  [pred_h]
  [ratio]
}
"""
    out = _call(src)
    ctr, lvm, pred_h, ratio = out
    assert abs(ctr - 0.5) < 1e-10
    sum3 = 10 + 50 + 10
    exp_lvm = (0.8 * (1.04 * (sum3 ** 3) - (50 ** 3)) + 0.6) / 1000.0
    assert abs(lvm - exp_lvm) < 1e-9
    assert abs(pred_h - 70 * 0.0045 * 1000) < 1e-10
    print(f"  ✓ CTR={ctr}; LVM={lvm:.1f}g; 预测心质量={pred_h:.1f}g; 比={ratio:.4f}")


def test_matha_scenario_thyroid():
    print("\n--- 综合场景：甲状腺影像评估 ---")
    src = """
#：{
  a = 16
  b = 12
  c = 8
  vol = 局部_甲状腺体积(a)(b)(c)
  bsa = 表面_体表面积Mosteller(165)(60)
  ref_mass = 脏器_甲状腺_质量
  [vol]
  [bsa]
  [ref_mass]
}
"""
    out = _call(src)
    vol, bsa, ref_mass = out
    assert abs(vol - ELLIPSOID_K * 16 * 12 * 8 / 1000) < 1e-10
    assert abs(bsa - math.sqrt(165 * 60 / 3600)) < 1e-12
    assert ref_mass == 25.0
    print(f"  ✓ 甲状腺={vol:.2f}mL; BSA={bsa:.3f}m²; 参考质量={ref_mass}g")


def test_matha_scenario_brain():
    print("\n--- 综合场景：脑影像测量 ---")
    src = """
#：{
  horn = 32
  cranial = 140
  evans = 影解_Evans指数(horn)(cranial)
  sulcus = 4
  age = 45
  sulcus_cls = 影解_脑沟宽度(age)(sulcus)
  pituitary = 8
  pit_cls = 影解_垂体高度判定(pituitary)
  onsd = 5.0
  onsd_cls = 系统_视神经鞘判定(onsd)
  [evans]
  [sulcus_cls]
  [pit_cls]
  [onsd_cls]
}
"""
    out = _call(src)
    evans, sulcus_cls, pit_cls, onsd_cls = out
    assert abs(evans - 32 / 140) < 1e-12
    assert sulcus_cls == "正常"
    assert pit_cls[0] == "正常"
    assert onsd_cls[0] == "阴性"
    print(f"  ✓ Evans={evans:.4f}; 脑沟4mm→{sulcus_cls}; 垂体8mm→{pit_cls[0]}; ONSD5mm→{onsd_cls[0]}")


def test_matha_scenario_burn():
    print("\n--- 综合场景：烧伤面积估算 ---")
    src = """
#：{
  head = 表面_烧伤九分法("头颈")
  r_arm = 表面_烧伤九分法("右上肢")
  torso = 表面_烧伤九分法("躯干前")
  r_leg = 表面_烧伤九分法("右下肢")
  total = head + r_arm + torso + r_leg
  bsa = 表面_体表面积Mosteller(170)(70)
  burn_area = bsa * total / 100
  [total]
  [bsa]
  [burn_area]
}
"""
    out = _call(src)
    total, bsa, burn_area = out
    assert abs(total - 54.0) < 1e-10
    assert abs(bsa - math.sqrt(170 * 70 / 3600)) < 1e-12
    assert abs(burn_area - bsa * 54 / 100) < 1e-12
    print(f"  ✓ 总%= {total}%, BSA={bsa:.3f}m², 烧伤面积={burn_area:.3f}m²")


def test_matha_scenario_skeleton():
    print("\n--- 综合场景：骨骼分类与脏器质量 ---")
    src = """
#：{
  total_bone = 骨骼_总计
  axial = 骨骼_中轴骨
  append = 骨骼_附肢骨
  sum_check = axial + append
  heart_mass = 临解_心脏质量预测(70)
  liver_mass = 临解_肝脏质量预测(70)
  brain_mass = 临解_脑质量预测(70)
  [total_bone]
  [sum_check]
  [heart_mass]
  [liver_mass]
  [brain_mass]
}
"""
    out = _call(src)
    total_bone, sum_check, heart_mass, liver_mass, brain_mass = out
    assert total_bone == 206
    assert sum_check == 206
    assert abs(heart_mass - 315) < 1e-10
    assert abs(liver_mass - 1575) < 1e-10
    assert abs(brain_mass - 1470) < 1e-10
    print(f"  ✓ 206块 = 中轴80 + 附肢126; 心={heart_mass}g 肝={liver_mass}g 脑={brain_mass}g")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_an_registered_in_interp, test_an_registered_in_semantic,
        test_cardiothoracic_ratio, test_femur_angles,
        test_spinal_and_pelvic_indices, test_aortic_z_and_canal,
        test_thyroid_prostate_volume, test_organ_volumes,
        test_lv_mass_and_joint,
        test_body_surface_area, test_burn_rule_of_nines,
        test_landmark_and_needle,
        test_spinal_canal_ref, test_conus_and_brain,
        test_evans_and_nodule,
        test_organ_mass_pred, test_blood_and_lung_volume,
        test_organ_to_weight_ratio,
        test_databases,
        test_matha_scenario_cardiac, test_matha_scenario_thyroid,
        test_matha_scenario_brain, test_matha_scenario_burn,
        test_matha_scenario_skeleton,
    ]
    for t in tests:
        t()
    print()
    print("✓✓✓", len(tests), "个解剖学领域测试全部通过 ✓✓✓")
