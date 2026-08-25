"""Matha 建筑结构工程领域测试。

运行：python -m tests.test_building_struct
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.building_struct import (
    _building_struct_symtab_names,
    CONCRETE_GRADE, REBAR_GRADE, REBAR_XI_B, STEEL_GRADE,
    MASONRY_STRENGTH, ALLOW_SLENDERNESS, TIMBER_GRADE_STR,
    SOIL_MOD_COEFF, PILE_RESISTANCE, SEISMIC_ALPHA_MAX,
    ALPHA1_C50, GAMMA_X,
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
def test_bs_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _building_struct_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing[:5]}"
    print(f"  ✓ 共 {len(names)} 个内建名全部注册")


def test_bs_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[混凝_受弯承载力简化(360)(1256)(460) + 钢结_长细比(3000)(20) + 抗震_水平地震作用(0.08)(1000)]"
    ok = _semantic_ok(src)
    assert ok, "内建触发语义错误"
    print("  ✓ 语义侧可直接引用")


# ===== 1. 混凝土结构 =====
def test_concrete_flexure_capacity():
    print("\n--- 混凝土受弯承载力简化 ---")
    i = _interp()
    Mu = i.call("混凝_受弯承载力简化", 360, 1256, 460)   # HRB400, 4Φ20, h0=460
    expected = 0.9 * 360 * 1256 * 460 / 1e6
    assert abs(Mu - expected) < 1e-9
    print(f"  ✓ HRB400 4Φ20 h0=460 → Mu={Mu:.2f} kN·m")


def test_concrete_compression_zone_ratio():
    print("\n--- 相对受压区高度 ξ ---")
    i = _interp()
    xi = i.call("混凝_相对受压区高度", 360, 1256, 14.3, 250, 460)   # C30, b=250, h0=460
    expected = 360 * 1256 / (1.0 * 14.3 * 250 * 460)
    assert abs(xi - expected) < 1e-9
    xi_b = i.call("混凝_界限相对受压区高度", "HRB400")
    assert abs(xi_b - 0.518) < 1e-10
    ok = xi < xi_b
    print(f"  ✓ ξ={xi:.4f}, ξb={xi_b}, ξ<ξb → {'适筋' if ok else '超筋'}")


def test_concrete_reinforcement_ratio_limits():
    print("\n--- 最小/最大配筋率 ---")
    i = _interp()
    rho_min = i.call("混凝_最小配筋率", 1.43, 360)   # C30/HRB400
    expected = max(0.002, 0.45 * 1.43 / 360)
    assert abs(rho_min - expected) < 1e-9
    rho_max = i.call("混凝_最大配筋率", 0.518, 14.3, 360)
    expected2 = 0.518 * 14.3 / 360
    assert abs(rho_max - expected2) < 1e-9
    print(f"  ✓ ρmin={rho_min:.5f}, ρmax={rho_max:.4f}")


def test_concrete_shear_and_axial_capacity():
    print("\n--- 受剪承载力 & 轴压承载力 ---")
    i = _interp()
    V = i.call("混凝_受剪承载力", 1.43, 250, 460, 360, 100, 150)
    expected_v = (0.7 * 1.43 * 250 * 460 + 1.25 * 360 * 100 * 460 / 150) / 1000
    assert abs(V - expected_v) < 1e-6
    N = i.call("混凝_轴压承载力", 14.3, 250 * 250, 360, 1964)   # 250×250 柱, 4Φ25
    expected_n = 0.9 * (14.3 * 250 * 250 + 360 * 1964) / 1000
    assert abs(N - expected_n) < 1e-6
    print(f"  ✓ V={V:.2f}kN; N={N:.2f}kN")


def test_concrete_t_flange_and_crack():
    print("\n--- T 形翼缘 & 裂缝宽度 ---")
    i = _interp()
    bf = i.call("混凝_T形翼缘宽度", 200, 80, 6000)
    assert abs(bf - min(200 + 12 * 80, 6000 / 3)) < 1e-10
    w = i.call("混凝_裂缝宽度", 2.1, 0.7, 200, 200000, 25, 16, 0.02)
    expected_w = 2.1 * 0.7 * 200 / 200000 * (1.9 * 25 + 0.08 * 16 / 0.02)
    assert abs(w - expected_w) < 1e-9
    print(f"  ✓ bf'={bf}mm; wmax={w:.4f}mm")


# ===== 2. 钢结构 =====
def test_steel_flexure_and_shear():
    print("\n--- 钢结构抗弯/抗剪强度 ---")
    i = _interp()
    sigma = i.call("钢结_抗弯强度", 100, 1.05, 500)   # M=100kN·m, Wn=500cm³
    expected = 100 * 1e6 / (1.05 * 500 * 1e3)
    assert abs(sigma - expected) < 1e-6
    f = i.builtins["钢材_Q235_f"]
    ok = sigma <= f
    print(f"  ✓ σ={sigma:.2f}MPa, f={f}MPa → {'满足' if ok else '不满足'}")


def test_steel_buckling_and_slenderness():
    print("\n--- 钢结构稳定系数 & 长细比 ---")
    i = _interp()
    phi_b = i.call("钢结_整体稳定系数", 0.5)
    assert phi_b == 1.0
    phi_b2 = i.call("钢结_整体稳定系数", 1.0)
    assert abs(phi_b2 - (1.07 - 1.0 / 4400)) < 1e-9
    phi_c = i.call("钢结_轴压稳定系数", 80)
    expected = 0.9 - (80 - 60) / 600
    assert abs(phi_c - expected) < 1e-9
    lam = i.call("钢结_长细比", 3000, 20)
    assert abs(lam - 150) < 1e-10
    print(f"  ✓ φb(0.5)={phi_b}, φb(1.0)={phi_b2:.4f}; φc(λ=80)={phi_c:.4f}; λ={lam}")


def test_steel_connections():
    print("\n--- 焊缝/螺栓/高强螺栓连接 ---")
    i = _interp()
    lw = i.call("钢结_焊缝计算长度", 200000, 8, 160)   # N=200kN=200000N, he=8mm, ffw=160MPa
    assert abs(lw - 200000 / (8 * 160)) < 1e-6
    Nb_shear = i.call("钢结_螺栓抗剪承载力", 1, 20, 140)   # 单剪 d=20 fv_b=140
    expected_s = 1 * math.pi * 20 ** 2 / 4 * 140 / 1000
    assert abs(Nb_shear - expected_s) < 1e-9
    Nb_tension = i.call("钢结_螺栓抗拉承载力", 20, 170)
    expected_t = math.pi * 20 ** 2 / 4 * 170 / 1000
    assert abs(Nb_tension - expected_t) < 1e-9
    Nv_friction = i.call("钢结_高强螺栓摩擦型承载力", 0.45, 2, 125)   # μ=0.45, nf=2, P=125
    assert abs(Nv_friction - 0.45 * 2 * 125) < 1e-10
    print(f"  ✓ lw={lw:.1f}mm; 螺栓剪={Nb_shear:.2f}kN 拉={Nb_tension:.2f}kN; 高强={Nv_friction}kN")


# ===== 3. 砌体结构 =====
def test_masonry_compression():
    print("\n--- 砌体抗压/局压承载力 ---")
    i = _interp()
    N = i.call("砌体_抗压承载力", 0.8, 1.89, 240 * 1000)   # φ=0.8, MU10+M10, 240×1000
    expected = 0.8 * 1.89 * 240 * 1000 / 1000
    assert abs(N - expected) < 1e-6
    gamma = i.call("砌体_局压提高系数", 300 * 300, 100 * 100)
    expected_g = min(3.0, 1.0 + 0.35 * math.sqrt(9.0))
    assert abs(gamma - expected_g) < 1e-9
    Nl = i.call("砌体_局压承载力", gamma, 1.89, 100 * 100)
    expected_nl = gamma * 1.89 * 10000 / 1000
    assert abs(Nl - expected_nl) < 1e-6
    print(f"  ✓ N={N:.2f}kN; γ={gamma:.3f}; Nl={Nl:.2f}kN")


def test_masonry_slenderness_stability():
    print("\n--- 高厚比/稳定性判定 ---")
    i = _interp()
    beta = i.call("砌体_高厚比", 3000, 240)
    assert abs(beta - 12.5) < 1e-10
    beta_max = i.call("砌体_允许高厚比", "M5")
    assert beta_max == 24.0
    ok, b, bm = i.call("砌体_稳定性判定", 3000, 240, "M5")
    assert ok == True and abs(b - 12.5) < 1e-10 and bm == 24.0
    ok2, _, _ = i.call("砌体_稳定性判定", 6000, 240, "M2.5")
    assert ok2 == False
    print(f"  ✓ β={b}≤[β]={bm} 稳定; 6000/240+M2.5→β=25>[β]=22 不稳定")


def test_masonry_shear_and_mesh():
    print("\n--- 砌体受剪/网状配筋 ---")
    i = _interp()
    V = i.call("砌体_受剪承载力", 0.17, 0.2, 240 * 1000)
    expected = (0.17 + 0.18 * 0.2) * 240000 / 1000
    assert abs(V - expected) < 1e-6
    delta = i.call("砌体_网状配筋提高系数", 0.005, 360)
    expected_d = 2.0 * 0.005 * 360 / 100
    assert abs(delta - expected_d) < 1e-9
    print(f"  ✓ V={V:.2f}kN; 网状配筋Δf={delta:.4f}MPa")


# ===== 4. 木结构 =====
def test_timber_compression_and_bending():
    print("\n--- 木结构抗压/抗弯 ---")
    i = _interp()
    N = i.call("木结_顺纹抗压承载力", 16, 100 * 100)   # TC17 fc=16, 100×100
    expected = 16 * 10000 / 1000
    assert abs(N - expected) < 1e-6
    M = i.call("木结_抗弯承载力", 17, 100 * 100 * 100 / 6)   # Wn=bh²/6
    expected_m = 17 * (100 ** 3 / 6) / 1e6
    assert abs(M - expected_m) < 1e-9
    print(f"  ✓ TC17 100×100: N={N}kN, M={M:.2f}kN·m")


def test_timber_shear_and_connections():
    print("\n--- 木结构抗剪/齿连接/螺栓 ---")
    i = _interp()
    # 矩形截面 I/S = 2/3·h（最大剪应力），简化用 b·I/S = 2/3·b·h
    V = i.call("木结_顺纹抗剪承载力", 1.7, 100, 100 ** 4 / 12, 100 ** 3 / 8)   # 简化参数
    expected_v = 1.7 * 100 * (100 ** 4 / 12) / (100 ** 3 / 8) / 1000
    assert abs(V - expected_v) < 1e-6
    N_tooth = i.call("木结_齿连接承压承载力", 10, 5000)   # fc_α=10, Ac=5000
    assert abs(N_tooth - 10 * 5000 / 1000) < 1e-10
    N_bolt = i.call("木结_螺栓连接承载力", 140, 60, 12)
    expected_b = 140 * 12 * 12 * math.sqrt(60) / 1e5
    assert abs(N_bolt - expected_b) < 1e-9
    print(f"  ✓ V={V:.2f}kN; 齿={N_tooth}kN; 螺栓={N_bolt:.2f}kN")


def test_timber_stability():
    print("\n--- 木构件稳定系数 ---")
    i = _interp()
    phi_50 = i.call("木结_稳定系数", 50)
    assert abs(phi_50 - (1 - 0.5 ** 2)) < 1e-9
    phi_100 = i.call("木结_稳定系数", 100)
    assert abs(phi_100 - 3000 / 10000) < 1e-9
    lam = i.call("木结_长细比", 3000, 28.87)
    assert abs(lam - 3000 / 28.87) < 1e-6
    print(f"  ✓ φ(50)={phi_50:.4f}; φ(100)={phi_100:.4f}; λ={lam:.2f}")


# ===== 5. 地基与基础 =====
def test_foundation_bearing_capacity():
    print("\n--- 地基承载力修正 ---")
    i = _interp()
    # 中砂 fak=200, ηb=3, γ=18, b=4, ηd=4.4, γm=18, d=2
    f = i.call("基础_承载力修正", 200, 3.0, 18, 4, 4.4, 18, 2)
    expected = 200 + 3 * 18 * (4 - 3) + 4.4 * 18 * (2 - 0.5)
    assert abs(f - expected) < 1e-6
    print(f"  ✓ 修正后 f={f:.2f}kPa")


def test_foundation_area_and_stress():
    print("\n--- 基础底面积 & 附加应力 ---")
    i = _interp()
    f = i.call("基础_承载力修正", 200, 3.0, 18, 4, 4.4, 18, 2)
    A = i.call("基础_中心受压面积", 800, f, 20, 2)
    expected = 800 / (f - 20 * 2)
    assert abs(A - expected) < 1e-6
    p0 = i.call("基础_附加应力", 180, 18, 1.5)
    assert abs(p0 - 153) < 1e-10
    print(f"  ✓ A={A:.3f}m²; p0={p0}kPa")


def test_foundation_settlement_and_pile():
    print("\n--- Boussinesq应力/分层沉降/单桩 ---")
    i = _interp()
    sigma_z = i.call("基础_Boussinesq应力", 200, 2)    # P=200kN, z=2m
    expected = 3 * 200 / (2 * math.pi) * 2 ** 3 / 2 ** 5
    assert abs(sigma_z - expected) < 1e-6
    s = i.call("基础_分层沉降", 30, 1.0, 5.0)            # σz=30kPa, H=1m, Es=5MPa
    assert abs(s - 6) < 1e-10
    Q = i.call("基础_单桩承载力", 1.256, [65, 75], [5, 3], 1200, 0.1256)   # 周长1.256
    side = 1.256 * (65 * 5 + 75 * 3)
    tip = 1200 * 0.1256
    assert abs(Q - (side + tip)) < 1e-6
    F = i.call("基础_承台冲切承载力", 1.43, 800, 3200)    # C30
    assert abs(F - 0.7 * 1.43 * 800 * 3200 / 1000) < 1e-6
    print(f"  ✓ σz={sigma_z:.2f}kPa; s={s}mm; Q={Q:.2f}kN; F={F:.2f}kN")


# ===== 6. 抗震设计 =====
def test_seismic_force_and_coefficient():
    print("\n--- 水平地震作用 & 影响系数 ---")
    i = _interp()
    F = i.call("抗震_水平地震作用", 0.08, 1000)    # α=0.08, G=1000kN
    assert abs(F - 80) < 1e-10
    amax = i.call("抗震_地震影响系数", "8度", "多遇")
    assert amax == 0.16
    amax_rare = i.call("抗震_地震影响系数", "8度", "罕遇")
    assert amax_rare == 0.90
    G = i.call("抗震_重力荷载代表值", 800, 200)    # 恒=800, 活=200, ψ=0.5
    assert abs(G - 900) < 1e-10
    Vmin = i.call("抗震_楼层最小剪力", 0.032, G)
    assert abs(Vmin - 0.032 * 900) < 1e-10
    print(f"  ✓ F={F}kN; αmax(8度多遇)={amax}; G={G}kN; Vmin={Vmin:.2f}kN")


def test_seismic_axial_ratio_and_shear_span():
    print("\n--- 轴压比 & 剪跨比 ---")
    i = _interp()
    mu = i.call("抗震_轴压比", 1500, 14.3, 500 * 500)
    expected = 1500 * 1000 / (14.3 * 500 * 500)
    assert abs(mu - expected) < 1e-9
    ok, m, limit = i.call("抗震_轴压比判定", 1500, 14.3, 500 * 500, 0.6)
    assert ok == (m <= 0.6) and abs(m - expected) < 1e-9
    lam = i.call("抗震_剪跨比", 200, 300, 460)
    assert abs(lam - 200 / (300 * 460)) < 1e-12
    print(f"  ✓ μ={mu:.4f}, 限值0.6 → {'满足' if ok else '不满足'}; λ={lam:.6f}")


def test_seismic_grade_and_drift_limits():
    print("\n--- 抗震等级 & 层间位移角限值 ---")
    i = _interp()
    coeff = i.call("抗震_抗震等级调整系数", "框架", 8)
    assert coeff == 0.8
    theta_e = i.call("抗震_弹性层间位移角限值", "框架")
    assert abs(theta_e - 1 / 550) < 1e-9
    theta_p = i.call("抗震_弹塑性层间位移角限值", "剪力墙")
    assert abs(theta_p - 1 / 120) < 1e-9
    print(f"  ✓ 框架8度调整系数={coeff}; 框架[θe]=1/550; 剪力墙[θp]=1/120")


# ===== 7. 数据库 =====
def test_databases():
    print("\n--- 数据库验证 ---")
    i = _interp()
    assert i.builtins["混凝土_C30_fc"] == 14.3
    assert i.builtins["混凝土_C30_ft"] == 1.43
    assert i.builtins["混凝土_C30_Ec"] == 30000
    assert i.builtins["钢筋_HRB400_fy"] == 360
    assert i.builtins["钢筋_HRB400_ξb"] == 0.518
    assert i.builtins["钢材_Q345_f"] == 310
    assert i.builtins["钢材_Q345_fv"] == 180
    assert i.builtins["砌体强度_MU15_M10"] == 2.31
    assert i.builtins["允许高厚比_M5"] == 24.0
    assert i.builtins["木材_TC17_fm"] == 17
    assert i.builtins["木材_TC17_fv"] == 1.7
    assert i.builtins["地基修正_中砂_粗砂_ηb"] == 3.0
    assert i.builtins["地基修正_中砂_粗砂_ηd"] == 4.4
    assert i.builtins["桩阻力_中砂_qsik"] == 75
    assert i.builtins["桩阻力_中砂_qpk"] == 2500
    assert i.builtins["地震影响_8度_多遇"] == 0.16
    assert i.builtins["地震影响_8度_罕遇"] == 0.90
    assert i.builtins["建结_α1_C50"] == 1.0
    assert i.builtins["建结_混凝土重度"] == 25.0
    print("  ✓ 混凝土/钢筋/钢材/砌体/高厚比/木材/地基/桩/地震/常量 全部正确")


# ===== 8. Matha 综合场景 =====
def test_matha_scenario_concrete_beam():
    print("\n--- 综合场景：混凝土梁配筋验算 ---")
    src = """
#：{
  fy = 钢筋_HRB400_fy
  fc = 混凝土_C30_fc
  ft = 混凝土_C30_ft
  xi_b = 混凝_界限相对受压区高度("HRB400")
  As = 1256
  b = 250
  h0 = 460
  xi = 混凝_相对受压区高度(fy)(As)(fc)(b)(h0)
  Mu = 混凝_受弯承载力简化(fy)(As)(h0)
  rho_min = 混凝_最小配筋率(ft)(fy)
  rho = As * 1.0 / (b * h0)
  rho_max = 混凝_最大配筋率(xi_b)(fc)(fy)
  [xi]
  [Mu]
  [rho]
  [rho_min]
  [rho_max]
}
"""
    out = _call(src)
    xi, Mu, rho, rho_min, rho_max = out
    assert abs(xi - 360 * 1256 / (14.3 * 250 * 460)) < 1e-9
    assert abs(Mu - 0.9 * 360 * 1256 * 460 / 1e6) < 1e-6
    assert rho_min < rho < rho_max
    print(f"  ✓ ξ={xi:.4f}<ξb={0.518}; Mu={Mu:.2f}kN·m; ρ={rho:.4f} ∈ [{rho_min:.4f}, {rho_max:.4f}]")


def test_matha_scenario_steel_column():
    print("\n--- 综合场景：钢柱稳定验算 ---")
    src = """
#：{
  f = 钢材_Q345_f
  l0 = 6000
  i = 50
  lambda = 钢结_长细比(l0)(i)
  phi = 钢结_轴压稳定系数(lambda)
  A = 5000
  N_design = phi * f * A / 1000
  [lambda]
  [phi]
  [N_design]
}
"""
    out = _call(src)
    lam, phi, N_design = out
    assert abs(lam - 120) < 1e-10
    # λ=120 → φ = 0.9 - (120-60)/600 = 0.8
    assert abs(phi - 0.8) < 1e-9
    assert abs(N_design - 0.8 * 310 * 5000 / 1000) < 1e-6
    print(f"  ✓ λ={lam}, φ={phi}, Q345 A=5000mm² → N={N_design:.2f}kN")


def test_matha_scenario_masonry_wall():
    print("\n--- 综合场景：砌体墙稳定性 ---")
    src = """
#：{
  H0 = 3600
  h = 240
  mortar = "M5"
  beta = 砌体_高厚比(H0)(h)
  beta_max = 砌体_允许高厚比(mortar)
  ok = 砌体_稳定性判定(H0)(h)(mortar)
  brick = "MU10"
  f_mason = 砌体强度_MU10_M5
  A = 240 * 1000
  N_cap = 砌体_抗压承载力(0.8)(f_mason)(A)
  [beta]
  [beta_max]
  [f_mason]
  [N_cap]
}
"""
    out = _call(src)
    beta, beta_max, f_mason, N_cap = out
    assert abs(beta - 15) < 1e-10
    assert beta_max == 24.0
    assert f_mason == 1.50
    assert abs(N_cap - 0.8 * 1.50 * 240000 / 1000) < 1e-6
    print(f"  ✓ β={beta}≤[β]={beta_max}; MU10+M5 f={f_mason}MPa; N={N_cap:.2f}kN")


def test_matha_scenario_seismic():
    print("\n--- 综合场景：框架抗震验算 ---")
    src = """
#：{
  amax = 抗震_地震影响系数("8度")("多遇")
  dead = 800
  live = 200
  G = 抗震_重力荷载代表值(dead)(live)
  F = 抗震_水平地震作用(amax)(G)
  coeff = 抗震_抗震等级调整系数("框架")(8)
  theta_e = 抗震_弹性层间位移角限值("框架")
  [amax]
  [G]
  [F]
  [coeff]
  [theta_e]
}
"""
    out = _call(src)
    amax, G, F, coeff, theta_e = out
    assert amax == 0.16
    assert abs(G - 900) < 1e-10
    assert abs(F - 144) < 1e-10
    assert coeff == 0.8
    assert abs(theta_e - 1 / 550) < 1e-9
    print(f"  ✓ αmax={amax}, G={G}kN, F={F}kN; 框架8度调整={coeff}; [θe]=1/550")


def test_matha_scenario_pile_foundation():
    print("\n--- 综合场景：单桩承载力 ---")
    src = """
#：{
  qs1 = 桩阻力_粘性土_可塑_qsik
  qs2 = 桩阻力_中砂_qsik
  qpk = 桩阻力_中砂_qpk
  up = 1.256
  l1 = 6
  l2 = 3
  Ap = 0.1256
  Q = 基础_单桩承载力(up)([qs1, qs2])([l1, l2])(qpk)(Ap)
  [qs1]
  [qs2]
  [qpk]
  [Q]
}
"""
    # Matha 不支持列表字面量，用 i.call 直接传列表
    i = _interp()
    qs1 = i.builtins["桩阻力_粘性土_可塑_qsik"]
    qs2 = i.builtins["桩阻力_中砂_qsik"]
    qpk = i.builtins["桩阻力_中砂_qpk"]
    Q = i.call("基础_单桩承载力", 1.256, [qs1, qs2], [6, 3], qpk, 0.1256)
    expected = 1.256 * (65 * 6 + 75 * 3) + 2500 * 0.1256
    assert abs(Q - expected) < 1e-6
    print(f"  ✓ 单桩 Q={Q:.2f}kN (侧阻+端阻)")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_bs_registered_in_interp, test_bs_registered_in_semantic,
        test_concrete_flexure_capacity, test_concrete_compression_zone_ratio,
        test_concrete_reinforcement_ratio_limits, test_concrete_shear_and_axial_capacity,
        test_concrete_t_flange_and_crack,
        test_steel_flexure_and_shear, test_steel_buckling_and_slenderness,
        test_steel_connections,
        test_masonry_compression, test_masonry_slenderness_stability,
        test_masonry_shear_and_mesh,
        test_timber_compression_and_bending, test_timber_shear_and_connections,
        test_timber_stability,
        test_foundation_bearing_capacity, test_foundation_area_and_stress,
        test_foundation_settlement_and_pile,
        test_seismic_force_and_coefficient, test_seismic_axial_ratio_and_shear_span,
        test_seismic_grade_and_drift_limits,
        test_databases,
        test_matha_scenario_concrete_beam, test_matha_scenario_steel_column,
        test_matha_scenario_masonry_wall, test_matha_scenario_seismic,
        test_matha_scenario_pile_foundation,
    ]
    for t in tests:
        t()
    print()
    print("✓✓✓", len(tests), "个建筑结构工程领域测试全部通过 ✓✓✓")
