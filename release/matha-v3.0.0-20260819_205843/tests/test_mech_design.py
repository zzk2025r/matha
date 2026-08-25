"""Matha 机械设计领域测试。

运行：python -m tests.test_mech_design
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.mech_design import (
    _mech_design_symtab_names,
    SHAFT_MATERIAL, BALL_BEARING_62XX, BALL_BEARING_63XX, ROLLER_BEARING,
    GEAR_MATERIAL, SPRING_MATERIAL, BOLT_GRADE, BOLT_THREAD,
    IT_GRADE_COEFF, SURFACE_RA,
    G_STEEL_DESIGN, E_STEEL_DESIGN, ZETA_TORSION, TAU_T_ALLOW_45,
    ZE_STEEL_STEEL, ZH_STANDARD,
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
def test_md_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _mech_design_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个内建名全部注册")


def test_md_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[轴设_扭转切应力(10000)(30) + 轴承_额定寿命_小时(19.8)(5.0)(1500)(3.0) + 齿轮_中心距(2)(20)(60)]"
    ok = _semantic_ok(src)
    assert ok, "语义侧未注册机械设计符号"
    print("  ✓ 语义侧可直接引用")


# ===== 1. 轴与连接件 =====
def test_shaft_torsion_bending():
    print("\n--- 轴的扭转切应力 & 弯曲正应力 ---")
    i = _interp()
    T = 200000  # N·mm
    d = 30
    tau = i.call("轴设_扭转切应力", T, d)
    expected_tau = 16 * T / (math.pi * d ** 3)
    assert abs(tau - expected_tau) < 1e-6

    M = 300000  # N·mm
    sigma = i.call("轴设_弯曲正应力", M, d)
    expected_s = 32 * M / (math.pi * d ** 3)
    assert abs(sigma - expected_s) < 1e-6

    Me = i.call("轴设_弯扭当量弯矩", M, T, 0.6)
    expected_Me = math.sqrt(M ** 2 + (0.6 * T) ** 2)
    assert abs(Me - expected_Me) < 1e-6
    print(f"  ✓ τ={tau:.1f}MPa; σ={sigma:.1f}MPa; Me={Me:.0f}N·mm")


def test_shaft_estimate_diameter():
    print("\n--- 按扭转初估轴径 ---")
    i = _interp()
    d = i.call("轴设_按扭转初估直径", 5.0, 1440, 35.0)  # P=5kW, n=1440rpm
    expected = (9.55e6 * 5.0 / (0.2 * 35 * 1440)) ** (1 / 3.0)
    assert abs(d - expected) < 1e-6
    print(f"  ✓ 5kW/1440rpm → d≥{d:.2f}mm")


def test_flat_key_and_spec():
    print("\n--- 平键强度 & 规格 ---")
    i = _interp()
    spec = i.call("轴设_查平键规格", 35)
    assert len(spec) == 4
    b, h, _, _ = spec
    assert b == 10 and h == 8, f"轴径35对应b={b},h={h}，期望10×8"

    T = 300000  # N·mm
    d = 35
    L = 60
    sigma_p = i.call("轴设_平键挤压强度", T, d, h, L)
    tau = i.call("轴设_平键剪切强度", T, d, b, L)
    assert abs(sigma_p - 4 * T / (d * h * L)) < 1e-6
    assert abs(tau - 2 * T / (d * b * L)) < 1e-6
    print(f"  ✓ d=35mm → b×h={b}×{h}; σp={sigma_p:.1f}MPa; τ={tau:.1f}MPa")


def test_spline_and_interference():
    print("\n--- 花键挤压 & 过盈配合扭矩 ---")
    i = _interp()
    sigma_p = i.call("轴设_花键挤压强度", 500000, 10, 3, 60, 40)
    expected = 8 * 500000 / (10 * 3 * 60 * 40)
    assert abs(sigma_p - expected) < 1e-6

    T = i.call("轴设_过盈配合扭矩", 50, 40, 50, 0.08)  # p=50MPa, d=40, L=50
    expected_T = math.pi * 50 * 40 * 50 * 0.08 * 40 / 2
    assert abs(T - expected_T) < 1e-6
    print(f"  ✓ 花键σp={sigma_p:.1f}MPa; 过盈配合T={T:.0f}N·mm")


# ===== 2. 滚动轴承 =====
def test_bearing_life():
    print("\n--- 轴承额定寿命 ---")
    i = _interp()
    # 6205 C=25.5kN, P=5kN, n=1500rpm, ε=3 球轴承
    L10 = i.call("轴承_额定寿命_转", 25.5, 5.0, 3.0)
    expected_L10 = (25.5 / 5.0) ** 3 * 1e6
    assert abs(L10 - expected_L10) < 1e-3

    Lh = i.call("轴承_额定寿命_小时", 25.5, 5.0, 1500, 3.0)
    expected_Lh = (1e6 / (60 * 1500)) * (25.5 / 5.0) ** 3
    assert abs(Lh - expected_Lh) < 1e-3
    print(f"  ✓ L10={L10/1e6:.1f}M转; Lh={Lh:.0f}h")


def test_bearing_equivalent_and_check():
    print("\n--- 当量动载荷 & 静载校核 ---")
    i = _interp()
    P = i.call("轴承_当量动载荷", 4.0, 1.5, 1.0, 0.0, 1.0)
    assert abs(P - 1.0 * (1.0 * 4 + 0.0 * 1.5)) < 1e-9

    ok = i.call("轴承_静载校核", 3.0, 15.2, 1.0)
    assert ok is True
    ok_bad = i.call("轴承_静载校核", 30.0, 15.2, 1.0)
    assert ok_bad is False
    print(f"  ✓ 当量动载荷P={P:.1f}kN; 静载校核 OK/Fail 通过")


def test_bearing_query():
    print("\n--- 查轴承规格 ---")
    i = _interp()
    b6205 = i.call("轴承_查深沟球_62xx", "6205")
    C, C0, d, D, B = b6205
    assert abs(C - 25.5) < 1e-6 and abs(d - 25) < 1e-6 and abs(D - 52) < 1e-6

    b6308 = i.call("轴承_查深沟球_63xx", "6308")
    _, _, d3, _, _ = b6308
    assert abs(d3 - 40) < 1e-6
    print(f"  ✓ 6205 C={C}kN d={d}D={D}B={B}; 6308 内径={d3}mm")


# ===== 3. 齿轮传动 =====
def test_gear_geometry():
    print("\n--- 齿轮几何参数 ---")
    i = _interp()
    m, z1, z2 = 2.0, 20, 60
    d1 = i.call("齿轮_分度圆直径", m, z1)
    a = i.call("齿轮_中心距", m, z1, z2)
    i_ratio = i.call("齿轮_传动比_齿数", z1, z2)
    b = i.call("齿轮_齿宽", 1.0, d1)
    assert abs(d1 - 40) < 1e-9
    assert abs(a - 80) < 1e-9
    assert abs(i_ratio - 3.0) < 1e-9
    assert abs(b - 40) < 1e-9
    print(f"  ✓ d1={d1}; a={a}; i={i_ratio}; b={b}mm")


def test_gear_speed_torque():
    print("\n--- 齿轮速度 & 转矩 ---")
    i = _interp()
    v = i.call("齿轮_圆周速度", 40, 1440)
    expected_v = math.pi * 40 * 1440 / (60 * 1000.0)
    assert abs(v - expected_v) < 1e-6

    T1 = i.call("齿轮_转矩_Pn", 5.0, 1440)
    assert abs(T1 - 9.55e6 * 5 / 1440) < 1e-3
    print(f"  ✓ v={v:.2f}m/s; T1={T1:.0f}N·mm")


def test_gear_stress():
    print("\n--- 齿轮弯曲应力 & 许用 ---")
    i = _interp()
    T1 = 9.55e6 * 5 / 1440
    sigmaF = i.call("齿轮_弯曲应力", T1, 1.0, 2.0, 20, 2.5, 1.65, 1.5)
    # b = φd·m·z1 = 1.0*2*20=40
    b = 40
    denom = 1.0 * b * (2 ** 2) * 20
    expected = 2 * 1.5 * T1 * 2.5 * 1.65 / denom
    assert abs(sigmaF - expected) < 1e-3

    sigmaHP = i.call("齿轮_许用接触应力", 1150, 1.0, 1.1)
    assert abs(sigmaHP - 1150 * 1.0 / 1.1) < 1e-6

    sigmaFP = i.call("齿轮_许用弯曲应力", 450, 1.0, 1.5, 1.0)
    assert abs(sigmaFP - 450 * 1.0 / 1.5) < 1e-6
    print(f"  ✓ σF={sigmaF:.1f}MPa; σHP={sigmaHP:.0f}MPa; σFP={sigmaFP:.0f}MPa")


# ===== 4. 弹簧设计 =====
def test_spring_index_and_stress():
    print("\n--- 旋绕比 & 曲度系数 & 切应力 ---")
    i = _interp()
    C = i.call("弹簧_旋绕比", 25, 4)  # D=25 d=4
    assert abs(C - 6.25) < 1e-9

    K = i.call("弹簧_曲度系数", 6.25)
    expected_K = (4 * 6.25 - 1) / (4 * 6.25 - 4) + 0.615 / 6.25
    assert abs(K - expected_K) < 1e-9

    tau = i.call("弹簧_切应力", 200, 25, 4, 1.25)
    expected_tau = 8 * 1.25 * 25 * 200 / (math.pi * 4 ** 3)
    assert abs(tau - expected_tau) < 1e-6
    print(f"  ✓ C={C}; K={K:.3f}; τ={tau:.1f}MPa")


def test_spring_deflection_and_stiffness():
    print("\n--- 弹簧变形 & 刚度 & 圈数高度 ---")
    i = _interp()
    # 4mm 钢丝 D=25mm 有效圈 n=8，碳素钢 G=80000
    lam = i.call("弹簧_变形量", 200, 25, 4, 8, 80000.0)
    k = i.call("弹簧_刚度", 25, 4, 8, 80000.0)
    expected_k = 80000 * 4 ** 4 / (8 * 25 ** 3 * 8)
    assert abs(k - expected_k) < 1e-9
    assert abs(lam - 200 / expected_k) < 1e-3  # λ=F/k

    n1 = i.call("弹簧_总圈数", 8, "YI型")
    assert abs(n1 - 10) < 1e-9

    H0 = i.call("弹簧_自由高度", 8, 8, 4, "YI型")
    H0_val = 8 * 8 + 1.5 * 4
    assert abs(H0 - H0_val) < 1e-9
    H0_check = i.call("弹簧_自由高度", 8, 8, 4, "YI型")
    assert abs(H0_check - H0_val) < 1e-9

    alpha = i.call("弹簧_螺旋角", 8, 25)
    expected_alpha = math.atan(8 / (math.pi * 25))
    assert abs(alpha - expected_alpha) < 1e-9
    print(f"  ✓ k={k:.2f}N/mm; λ={lam:.2f}mm; n1={n1}; H0={H0_check}mm; α={math.degrees(alpha):.1f}°")


# ===== 5. 紧固件与连接件 =====
def test_bolt_strength():
    print("\n--- 受拉/受剪螺栓 & 挤压 ---")
    i = _interp()
    # M12 8.8级：d1=10.106
    A_s = math.pi * 10.106 ** 2 / 4
    sigma = i.call("联接_受拉螺栓强度", 15000, A_s, 640, 1.5)
    expected = 1.3 * 15000 / A_s
    assert abs(sigma - expected) < 1e-6

    tau = i.call("联接_受剪螺栓强度", 8000, 1, 12.0)  # F=8kN 单剪 d0=12
    expected_tau = 4 * 8000 / (1 * math.pi * 12 ** 2)
    assert abs(tau - expected_tau) < 1e-6

    sigma_p = i.call("联接_螺栓挤压强度", 8000, 12, 10)  # Σt=10mm
    assert abs(sigma_p - 8000 / (12 * 10)) < 1e-9
    print(f"  ✓ 拉σ={sigma:.1f}MPa; 剪τ={tau:.1f}MPa; 挤压σp={sigma_p:.1f}MPa")


def test_bolt_total_and_query():
    print("\n--- 螺栓拉力 & 查规格 ---")
    i = _interp()
    # 轴向工作载荷 F=10kN, 变载残余预紧
    F_res = i.call("联接_残余预紧力", 10000, 0.6)
    F_total = i.call("联接_螺栓总拉力", 10000, F_res)
    assert abs(F_res - 6000) < 1e-6
    assert abs(F_total - 16000) < 1e-6

    grade_spec = i.call("联接_查螺栓强度", "8.8")
    sigma_s, sigma_b = grade_spec
    assert abs(sigma_s - 640) < 1e-6 and abs(sigma_b - 800) < 1e-6

    bolt_spec = i.call("联接_查螺栓规格", "M16")
    d, d1, d0, p = bolt_spec
    assert abs(d - 16) < 1e-6 and abs(d1 - 13.835) < 1e-3
    print(f"  ✓ F''={F_res:.0f}N, F'={F_total:.0f}N; 8.8级 σs/σb={sigma_s}/{sigma_b}; M16 d1={d1}mm")


def test_pin_shear():
    print("\n--- 销剪切强度 ---")
    i = _interp()
    tau = i.call("联接_销剪切强度", 5000, 10, 1.0)
    expected = 4 * 5000 / (math.pi * 10 ** 2)
    assert abs(tau - expected) < 1e-6
    print(f"  ✓ 单销τ={tau:.1f}MPa")


# ===== 6. 公差配合与可靠性 =====
def test_tolerance_it_and_fit():
    print("\n--- IT值 & 基孔制配合 ---")
    i = _interp()
    IT7 = i.call("公差_IT值", "IT7", 50)  # 50mm IT7
    i_val = 0.45 * 50 ** (1 / 3.0) + 0.001 * 50
    assert abs(IT7 - 16.0 * i_val) < 1e-6

    fit = i.call("公差_基孔制配合", "IT7", "H7h6", 50)
    ES, EI, es, ei = fit
    assert EI == 0 and ES > 0  # 基孔
    assert es == 0  # h 轴上偏差
    assert ei < 0  # h6 下偏差
    print(f"  ✓ IT7(D=50)={IT7:.1f}μm; H7/h6:孔[+{ES:.0f},0] 轴[0,{ei:.0f}] μm")


def test_dimension_chain_and_weibull():
    print("\n--- 尺寸链 & 威布尔可靠度 ---")
    i = _interp()
    # 尺寸链：封闭环 A0 = A1(50) + A2(30) - A3(20) - A4(55) = 5
    A0 = i.call("公差_尺寸链封闭环", [50, 30], [20, 55])
    assert abs(A0 - 5) < 1e-9

    T0 = i.call("公差_尺寸链封闭环公差", [0.05, 0.04, 0.03, 0.06])
    assert abs(T0 - 0.18) < 1e-9

    Ra = i.call("公差_查表面粗糙度", "精车_外圆")
    assert Ra == 0.8

    R = i.call("公差_威布尔可靠度", 5000, 10000, 2.0)
    expected_R = math.exp(- (5000 / 10000) ** 2)
    assert abs(R - expected_R) < 1e-9
    print(f"  ✓ 封闭环A0={A0}; T0={T0}; 精车Ra={Ra}μm; R(5000h)={R:.3f}")


# ===== 7. 数据库验证 =====
def test_database_values():
    print("\n--- 数据库验证 ---")
    i = _interp()
    # 轴材料
    assert i.builtins["轴材料_45_调质_sigma_1"] == 275
    assert i.builtins["轴材料_40Cr_调质_sigma_b"] == 735
    # 轴承
    assert i.builtins["轴承_62_6205_C"] == 25.5
    assert i.builtins["轴承_63_6310_D"] == 110
    assert i.builtins["轴承_N_N208_C"] == 60.8
    # 齿轮材料
    assert i.builtins["齿轮材料_20CrMnTi_渗碳_Hlim"] == 1500
    assert i.builtins["齿轮_ZE_钢钢"] == 189.8
    # 弹簧
    assert i.builtins["弹簧材料_60Si2Mn_tau_p"] == 590
    # 螺栓
    assert i.builtins["螺栓强度_10.9_sigma_s"] == 900
    assert i.builtins["螺栓规格_M20_d1"] == 17.294
    # 公差
    assert i.builtins["公差系数_IT7"] == 16.0
    assert i.builtins["表面Ra_精磨_外圆"] == 0.2
    # 常量
    assert i.builtins["机设_E_钢"] == 206000
    assert i.builtins["机设_45钢许用τ"] == 35.0
    print("  ✓ 轴/轴承/齿轮/弹簧/螺栓/公差/Ra/常量 全部正确")


# ===== 8. Matha 综合场景 =====
def test_matha_scenario_shaft_design():
    print("\n--- 综合场景：轴的设计验算 ---")
    src = """
#：{
  P = 5.0
  n = 1440
  d_min = 轴设_按扭转初估直径(P)(n)(35.0)
  d = 30
  T = 齿轮_转矩_Pn(P)(n)
  M = T * 0.6
  tau = 轴设_扭转切应力(T)(d)
  sigma = 轴设_弯曲正应力(M)(d)
  Me = 轴设_弯扭当量弯矩(M)(T)(0.6)
  [d_min]
  [tau]
  [sigma]
  [Me]
}
"""
    out = _call(src)
    d_min, tau, sigma, Me = out
    T_val = 9.55e6 * 5.0 / 1440
    M_val = T_val * 0.6
    assert tau > 0
    assert abs(d_min - (9.55e6 * 5.0 / (0.2 * 35 * 1440)) ** (1 / 3.0)) < 1e-4
    print(f"  ✓ d_min≥{d_min:.1f}取d=30; τ={tau:.1f}MPa; σ={sigma:.1f}MPa; Me={Me:.0f}N·mm")


def test_matha_scenario_bearing_life():
    print("\n--- 综合场景：轴承寿命 ---")
    src = """
#：{
  C = 轴承_62_6205_C
  C0 = 轴承_62_6205_C0
  Fr = 4.0
  Fa = 1.2
  P = 轴承_当量动载荷(Fr)(Fa)(0.6)(1.7)(1.0)
  Lh = 轴承_额定寿命_小时(C)(P)(1440)(3.0)
  [P]
  [Lh]
}
"""
    out = _call(src)
    P, Lh = out
    expected_P = 1.0 * (0.6 * 4 + 1.7 * 1.2)
    assert abs(P - expected_P) < 1e-9
    assert Lh > 0
    print(f"  ✓ 6205: P={P:.2f}kN, Lh={Lh:.0f}h")


def test_matha_scenario_gear_and_bolt():
    print("\n--- 综合场景：齿轮强度 + 螺栓校核 ---")
    src = """
#：{
  m = 2.0
  z1 = 20
  z2 = 60
  P = 3.0
  n1 = 960
  d1 = 齿轮_分度圆直径(m)(z1)
  a = 齿轮_中心距(m)(z1)(z2)
  T1 = 齿轮_转矩_Pn(P)(n1)
  sigmaF = 齿轮_弯曲应力(T1)(1.0)(m)(z1)(2.8)(1.55)(1.4)

  d0 = 12
  F_shear = 10000
  tau_b = 联接_受剪螺栓强度(F_shear)(1)(d0)
  sp = 联接_螺栓挤压强度(F_shear)(d0)(8)

  [a]
  [sigmaF]
  [tau_b]
  [sp]
}
"""
    out = _call(src)
    a, sigmaF, tau_b, sp = out
    assert abs(a - 80) < 1e-9
    assert sigmaF > 0
    assert abs(tau_b - 4 * 10000 / (math.pi * 12 ** 2)) < 1e-6
    assert abs(sp - 10000 / (12 * 8)) < 1e-9
    print(f"  ✓ 齿轮a={a}mm σF={sigmaF:.1f}MPa; 螺栓τ={tau_b:.1f}MPa 挤压={sp:.1f}MPa")


def test_matha_scenario_spring_and_tolerance():
    print("\n--- 综合场景：弹簧设计 + 尺寸链 ---")
    src = """
#：{
  d = 4
  D = 25
  n = 10
  F = 300
  C = 弹簧_旋绕比(D)(d)
  K = 弹簧_曲度系数(C)
  tau = 弹簧_切应力(F)(D)(d)(K)
  lam = 弹簧_变形量(F)(D)(d)(n)(80000)
  k_spring = 弹簧_刚度(D)(d)(n)(80000)

  A0 = 公差_尺寸链封闭环([80.0, 30.0])([50.0, 45.0])
  T0 = 公差_尺寸链封闭环公差([0.05, 0.04, 0.06, 0.03])
  R_10k = 公差_威布尔可靠度(10000)(20000)(2.0)

  [tau]
  [lam]
  [k_spring]
  [A0]
  [T0]
  [R_10k]
}
"""
    out = _call(src)
    tau, lam, k, A0, T0, R = out
    C_val = 25 / 4
    K_val = (4 * C_val - 1) / (4 * C_val - 4) + 0.615 / C_val
    expected_tau = 8 * K_val * 25 * 300 / (math.pi * 4 ** 3)
    expected_k = 80000 * 4 ** 4 / (8 * 25 ** 3 * 10)
    assert abs(tau - expected_tau) < 1e-3
    assert abs(k - expected_k) < 1e-9
    assert abs(A0 - 15) < 1e-9
    assert abs(T0 - 0.18) < 1e-9
    assert abs(R - math.exp(-(10000 / 20000) ** 2)) < 1e-6
    print(f"  ✓ τ={tau:.1f}MPa, k={k:.2f}N/mm, λ={lam:.2f}mm; 尺寸链A0={A0} T0={T0}; R(10k)={R:.3f}")


# ===== 主函数 =====
TESTS = [
    test_md_registered_in_interp,
    test_md_registered_in_semantic,
    test_shaft_torsion_bending,
    test_shaft_estimate_diameter,
    test_flat_key_and_spec,
    test_spline_and_interference,
    test_bearing_life,
    test_bearing_equivalent_and_check,
    test_bearing_query,
    test_gear_geometry,
    test_gear_speed_torque,
    test_gear_stress,
    test_spring_index_and_stress,
    test_spring_deflection_and_stiffness,
    test_bolt_strength,
    test_bolt_total_and_query,
    test_pin_shear,
    test_tolerance_it_and_fit,
    test_dimension_chain_and_weibull,
    test_database_values,
    test_matha_scenario_shaft_design,
    test_matha_scenario_bearing_life,
    test_matha_scenario_gear_and_bolt,
    test_matha_scenario_spring_and_tolerance,
]

if __name__ == "__main__":
    _passed = 0
    for t in TESTS:
        try:
            t()
            _passed += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ✗ {t.__name__}: {e!r}")
    print(f"\n✓✓✓ {_passed} 个机械设计领域测试全部通过 ✓✓✓" if _passed == len(TESTS)
          else f"\n✗✗✗ {len(TESTS) - _passed}/{len(TESTS)} 测试失败 ✗✗✗")
