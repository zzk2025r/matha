"""Matha 流体力学进阶测试：边界层 + 可压缩流 + 明渠水力学 + 泵与风机 + 局部损失与管网。

覆盖：
  1) 注册性测试（内建名 + 语义符号表）
  2) 边界层理论：层流/湍流厚度、阻力系数、形状因子
  3) 可压缩流动：声速/马赫数、等熵关系、正激波、临界比、喷管、普朗特迈耶
  4) 明渠水力学：谢才/曼宁、弗劳德、临界水深、水跃
  5) 泵与风机：扬程/功率/效率、比转速、相似律
  6) 局部损失与管网：局部水头损失、突扩突缩、串联并联比阻
  7) 物理常量 + 曼宁糙率 + 局部阻力系数查询
  8) Matha 侧综合场景

运行：python -m tests.test_fluid_expanded
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.fluid_exp import (
    _fluid_exp_symtab_names, G_STANDARD, GAMMA_AIR, GAMMA_MONO,
    GAMMA_DI, GAMMA_POLY, R_AIR, MANNING_N, K_MINOR,
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


# ===== 0. 注册性测试 =====
def test_fluid_exp_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _fluid_exp_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个流体力学进阶内建名全部注册")


def test_fluid_exp_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[边界_层流厚度(10)(1)(1.5e-5) + 可压缩_声速(1.4)(287)(300)]"
    ok = _semantic_ok(src)
    assert ok, "流体进阶内建触发语义错误"
    print("  ✓ 流体进阶内建在语义侧可直接引用")


# ===== 1. 边界层理论 =====
def test_laminar_boundary_layer():
    print("\n--- 层流边界层 ---")
    i = _interp()
    U, x, nu = 10.0, 1.0, 1.5e-5  # 空气
    Re_x = i.call("边界_局部雷诺数", U, x, nu)
    assert abs(Re_x - U * x / nu) < 1e-10
    d = i.call("边界_层流厚度", U, x, nu)
    expected = 5.0 * x / math.sqrt(Re_x)
    assert abs(d - expected) < 1e-10
    # 位移厚度 ~ 1.721/5.0 = 34.4% 厚度
    d_star = i.call("边界_层流位移厚度", U, x, nu)
    theta = i.call("边界_层流动量厚度", U, x, nu)
    assert 0.3 * d < d_star < 0.35 * d
    H = i.call("边界_形状因子", d_star, theta)
    assert abs(H - 2.59) < 0.05  # 层流 Blasius H ≈ 2.59
    print(f"  ✓ Re_x={Re_x:.2e}, δ={d*1000:.2f}mm, H={H:.2f}")


def test_plate_friction_coefficient():
    print("\n--- 平板摩擦阻力系数 ---")
    i = _interp()
    # 层流 Re_L = 1e5
    Cf_lam = i.call("边界_层流平板阻力系数", 1e5)
    expected = 1.328 / math.sqrt(1e5)
    assert abs(Cf_lam - expected) < 1e-10
    # 湍流 Re_L = 1e6
    Cf_turb = i.call("边界_湍流平板阻力系数", 1e6)
    expected = 0.074 / (1e6 ** (1.0/5))
    assert abs(Cf_turb - expected) < 1e-10
    # 混合 Re_L = 1e6 (介于 5e5 和 1e7 之间)
    Cf_mix = i.call("边界_混合平板阻力系数", 1e6)
    expected = 0.074 / (1e6 ** (1.0/5)) - 1742 / 1e6
    assert abs(Cf_mix - expected) < 1e-10
    print(f"  ✓ 层流 Cf={Cf_lam:.5f}, 湍流 Cf={Cf_turb:.5f}, 混合 Cf={Cf_mix:.5f}")


def test_turbulent_boundary_layer():
    print("\n--- 湍流边界层 ---")
    i = _interp()
    U, x, nu = 20.0, 5.0, 1e-6  # 水
    d_turb = i.call("边界_湍流厚度", U, x, nu)
    Re_x = U * x / nu
    expected = 0.37 * x / (Re_x ** (1.0/5))
    assert abs(d_turb - expected) < 1e-10
    print(f"  ✓ δ={d_turb*1000:.2f}mm (水 Re_x={Re_x:.2e})")


# ===== 2. 可压缩流动 =====
def test_speed_of_sound_and_mach():
    print("\n--- 声速与马赫数 ---")
    i = _interp()
    # 空气 300K: c = sqrt(1.4*287*300) ≈ 347.2 m/s
    c = i.call("可压缩_声速", 1.4, 287, 300)
    expected = math.sqrt(1.4 * 287 * 300)
    assert abs(c - expected) < 1e-10
    # v = 250 m/s → Ma ≈ 0.72
    Ma = i.call("可压缩_马赫数", 250, c)
    assert abs(Ma - 250 / c) < 1e-15
    print(f"  ✓ c={c:.1f}m/s, Ma(250m/s)={Ma:.3f}")


def test_isentropic_relations():
    print("\n--- 等熵关系 ---")
    i = _interp()
    g, Ma = 1.4, 0.8
    T_ratio = i.call("可压缩_等熵温度比", g, Ma)
    expected_T = 1 + 0.2 * 0.8 * 0.8  # (1.4-1)/2=0.2
    assert abs(T_ratio - expected_T) < 1e-15
    p_ratio = i.call("可压缩_等熵压强比", g, Ma)
    expected_p = expected_T ** (1.4 / 0.4)
    assert abs(p_ratio - expected_p) < 1e-12
    rho_ratio = i.call("可压缩_等熵密度比", g, Ma)
    expected_rho = expected_T ** (1 / 0.4)
    assert abs(rho_ratio - expected_rho) < 1e-12
    print(f"  ✓ T0/T={T_ratio:.4f}, p0/p={p_ratio:.4f}, ρ0/ρ={rho_ratio:.4f}")


def test_normal_shock():
    print("\n--- 正激波关系 ---")
    i = _interp()
    g, Ma1 = 1.4, 2.0
    pr = i.call("可压缩_激波压强比", g, Ma1)
    expected = (2 * 1.4 * 4 - 0.4) / 2.4  # = 4.5
    assert abs(pr - expected) < 1e-10
    Ma2 = i.call("可压缩_激波后马赫数", g, Ma1)
    # 正激波 Ma1=2 → Ma2 ≈ 0.5774（亚声速）
    numer = 4 * 0.4 + 2  # = 3.6
    denom = 2 * 1.4 * 4 - 0.4  # = 10.8
    expected_Ma2 = math.sqrt(numer / denom)
    assert abs(Ma2 - expected_Ma2) < 1e-10
    assert Ma2 < 1.0  # 正激波后必为亚声速
    print(f"  ✓ p2/p1={pr:.2f}, Ma2={Ma2:.4f} (<1 亚声速)")


def test_critical_and_nozzle():
    print("\n--- 临界比与喷管面积比 ---")
    i = _interp()
    g = 1.4
    p_star_p0 = i.call("可压缩_临界压强比", g)
    expected = (2.0 / 2.4) ** (1.4 / 0.4)  # (2/(γ+1))^(γ/(γ-1))
    assert abs(p_star_p0 - expected) < 1e-10
    T_star_T0 = i.call("可压缩_临界温度比", g)
    assert abs(T_star_T0 - 2.0 / 2.4) < 1e-15
    # 喉部 Ma=1 时 A/A*=1 应为 1
    A_ratio = i.call("可压缩_喷管面积比", g, 1.0)
    assert abs(A_ratio - 1.0) < 1e-10
    # Ma=2 > 1 时 A/A* > 1
    A_ratio2 = i.call("可压缩_喷管面积比", g, 2.0)
    assert A_ratio2 > 1.5
    print(f"  ✓ p*/p0={p_star_p0:.4f}, A/A*(Ma=1)=1, A/A*(Ma=2)={A_ratio2:.3f}")


def test_prandtl_meyer():
    print("\n--- 普朗特-迈耶膨胀角 ---")
    i = _interp()
    # Ma=1 时 ν=0
    nu_1 = i.call("可压缩_普朗特迈耶角", 1.4, 1.0)
    assert nu_1 == 0.0
    # Ma 增大 ν 增大
    nu_2 = i.call("可压缩_普朗特迈耶角", 1.4, 2.0)
    nu_3 = i.call("可压缩_普朗特迈耶角", 1.4, 3.0)
    assert nu_2 > 0.3  # ~26.4°=0.46 rad
    assert nu_3 > nu_2
    print(f"  ✓ ν(Ma=2)={nu_2:.3f}rad, ν(Ma=3)={nu_3:.3f}rad")


# ===== 3. 明渠水力学 =====
def test_chezy_and_manning():
    print("\n--- 谢才与曼宁公式 ---")
    i = _interp()
    g = G_STANDARD
    # 矩形渠 b=5m, h=2m → 水力半径
    R = i.call("明渠_矩形水力半径", 5, 2)
    expected = 5 * 2 / (5 + 4)  # 10/9 ≈ 1.111
    assert abs(R - expected) < 1e-10
    # 曼宁 SI 公式：n=0.013, R=1, S=1e-4 → v = (1/0.013)*1*0.01 = 0.769
    v_manning = i.call("明渠_曼宁流速_SI", 0.013, 1.0, 1e-4)
    expected_v = (1.0 / 0.013) * 1.0 ** (2.0/3) * (1e-4) ** 0.5
    assert abs(v_manning - expected_v) < 1e-12
    # 谢才公式：C = n^{-1} R^{1/6} 对曼宁等价，取 C=60, R=1, S=0.0001 → v=60*sqrt(0.0001)=0.6
    v_chezy = i.call("明渠_谢才流速", 60, 1.0, 1e-4)
    assert abs(v_chezy - 0.6) < 1e-12
    print(f"  ✓ R(5x2矩形)={R:.3f}m, 曼宁v={v_manning:.3f}m/s, 谢才v={v_chezy:.2f}m/s")


def test_trapezoidal_and_froude():
    print("\n--- 梯形渠水力半径 + 弗劳德数 ---")
    i = _interp()
    # 梯形 b=2, h=1.5, m=1.5 (边坡 1:1.5)
    R_t = i.call("明渠_梯形水力半径", 2.0, 1.5, 1.5)
    A = 2 * 1.5 + 1.5 * 1.5 * 1.5  # = 3 + 3.375 = 6.375
    P = 2 + 2 * 1.5 * math.sqrt(1 + 2.25)
    expected_R = A / P
    assert abs(R_t - expected_R) < 1e-10
    # 弗劳德数：v=3, h=1, g=9.81 → Fr=3/sqrt(9.81)=0.958
    Fr = i.call("明渠_弗劳德数", 3.0, 1.0, 9.81)
    expected_Fr = 3 / math.sqrt(9.81)
    assert abs(Fr - expected_Fr) < 1e-12
    # 流态
    state_sub = i.call("明渠_流态判断", 0.8)
    state_crit = i.call("明渠_流态判断", 1.0)
    state_super = i.call("明渠_流态判断", 1.5)
    assert state_sub == "缓流"
    assert state_crit == "临界流"
    assert state_super == "急流"
    print(f"  ✓ R梯形={R_t:.3f}m, Fr={Fr:.3f} (流态: 缓/临界/急)")


def test_critical_depth_and_hydraulic_jump():
    print("\n--- 临界水深与水跃 ---")
    i = _interp()
    g = G_STANDARD
    q = 5.0  # 单宽流量 m²/s
    h_c = i.call("明渠_临界水深", q, g)
    expected = (q * q / g) ** (1.0/3)
    assert abs(h_c - expected) < 1e-10
    v_c = i.call("明渠_临界流速", h_c, g)
    assert abs(v_c - math.sqrt(g * h_c)) < 1e-12
    # 比能 E = h + v²/(2g), q=v*h → v = q/h
    h = 1.0
    v = q / h
    E = i.call("明渠_比能", h, v, g)
    assert abs(E - (h + v * v / (2 * g))) < 1e-12
    # 水跃 Fr1=3
    y1 = 0.3
    Fr1 = 3.0
    y2 = i.call("明渠_水跃共轭水深", y1, Fr1)
    expected_y2 = 0.5 * y1 * (-1 + math.sqrt(1 + 8 * 9))  # 8*Fr^2=72
    assert abs(y2 - expected_y2) < 1e-10
    assert y2 > y1  # 共轭水深后加深
    dE = i.call("明渠_水跃能量损失", y1, y2)
    expected_dE = (y2 - y1) ** 3 / (4 * y1 * y2)
    assert abs(dE - expected_dE) < 1e-12
    print(f"  ✓ h_c={h_c:.3f}m, y1={y1}m(Fr=3)→y2={y2:.3f}m, 能量损失={dE:.3f}m")


# ===== 4. 泵与风机 =====
def test_pump_head_power_efficiency():
    print("\n--- 泵扬程/功率/效率 ---")
    i = _interp()
    rho, g = 1000, G_STANDARD
    # 扬程 计算：p1=1e5, p2=5e5 Pa, v1=v2=2 m/s, dz=20 m
    H = i.call("泵_扬程", 1e5, 5e5, rho, 2, 2, 20, g)
    expected = (5e5 - 1e5) / (1000 * g) + 0 + 20  # 400/9.81 + 20 = 60.77
    assert abs(H - expected) < 1e-8
    # 有效功率 P_w = ρgQH, Q=0.1 m³/s
    P_w = i.call("泵_有效功率", rho, g, 0.1, H)
    assert abs(P_w - rho * g * 0.1 * H) < 1e-6
    # 轴功率 η=0.8
    P_shaft = i.call("泵_轴功率", rho, g, 0.1, H, 0.8)
    assert abs(P_shaft - P_w / 0.8) < 1e-6
    eta = i.call("泵_效率", P_w, P_shaft)
    assert abs(eta - 0.8) < 1e-10
    print(f"  ✓ H={H:.2f}m, P_w={P_w/1000:.2f}kW, P_shaft={P_shaft/1000:.2f}kW, η={eta:.2%}")


def test_specific_speed_and_similarity():
    print("\n--- 比转速与相似律 ---")
    i = _interp()
    # 比转速：n=1450 rpm, Q=0.05 m³/s, H=30 m → n_s ≈ 1450*sqrt(0.05)/30^0.75
    n_s = i.call("泵_比转速", 1450, 0.05, 30)
    expected = 1450 * math.sqrt(0.05) / (30 ** 0.75)
    assert abs(n_s - expected) < 1e-6
    # 相似律：n 不变，D2=1.2D1 → Q2=1.2³·Q1 = 1.728Q1
    Q2 = i.call("泵_相似律流量", 1450, 1450, 1.0, 1.2, 0.1)
    assert abs(Q2 - 0.1 * 1.2 ** 3) < 1e-10
    # 转速加倍 D 不变 → H2 = 4H1, P2 = 8P1
    H2 = i.call("泵_相似律扬程", 1450, 2900, 0.5, 0.5, 20)
    assert abs(H2 - 20 * 4) < 1e-10
    P2 = i.call("泵_相似律功率", 1450, 2900, 0.5, 0.5, 10)
    assert abs(P2 - 10 * 8) < 1e-10
    print(f"  ✓ n_s={n_s:.1f}, Q2={Q2:.4f}, H2(2倍转速)={H2:.1f}m, P2(2倍转速)={P2:.1f}kW")


def test_fan_power():
    print("\n--- 风机功率与静压 ---")
    i = _interp()
    # 全压升 500 Pa, Q=1 m³/s → P_t = 500*1 = 500 W
    P_t = i.call("泵_风机全压功率", 500, 1.0)
    assert abs(P_t - 500) < 1e-10
    # 静压升：总压 500Pa, ρ=1.2, v=10 m/s → p_s = 500 - 0.5*1.2*100 = 440
    p_s = i.call("泵_风机静压升", 500, 1.2, 10)
    assert abs(p_s - 440) < 1e-10
    print(f"  ✓ P_t={P_t}W, p_s={p_s}Pa")


# ===== 5. 局部损失与管网 =====
def test_minor_loss_and_equivalent_length():
    print("\n--- 局部水头损失 + 当量长度 ---")
    i = _interp()
    g = G_STANDARD
    # 闸阀全开 ζ=0.17, v=3 m/s → h_m = 0.17*9/2g ≈ 0.078 m
    h_m = i.call("管损_局部水头损失", 0.17, 3.0, g)
    expected = 0.17 * 9 / (2 * g)
    assert abs(h_m - expected) < 1e-10
    # 当量长度：D=0.2m, f=0.02 → L_eq = 0.17*0.2/0.02 = 1.7 m
    L_eq = i.call("管损_当量长度", 0.17, 0.2, 0.02)
    assert abs(L_eq - 1.7) < 1e-10
    # 总水头损失 f=0.02, L=100, D=0.2, v=3, sum_zeta=0.5, g=9.81
    h_tot = i.call("管损_总水头损失", 0.02, 100, 0.2, 3.0, 0.5, g)
    expected_h = (0.02 * 100 / 0.2 + 0.5) * 9 / (2 * g)
    assert abs(h_tot - expected_h) < 1e-10
    print(f"  ✓ h_m={h_m:.4f}m, L_eq={L_eq:.1f}m, h_tot={h_tot:.3f}m")


def test_abrupt_expansion_contraction():
    print("\n--- 突扩突缩阻力系数 ---")
    i = _interp()
    # 突扩 A1=0.01m² → 大容器 A2→∞: ζ = (1-0)² = 1
    zeta_exp = i.call("管损_突扩阻力系数", 0.01, 1e9)
    assert abs(zeta_exp - 1.0) < 1e-5
    # 突缩 A1→∞ → A2: ζ = 0.5*(1-0) = 0.5（当 A2<<A1）
    zeta_cont = i.call("管损_突缩阻力系数", 1e9, 0.01)
    assert abs(zeta_cont - 0.5) < 1e-5
    print(f"  ✓ 突扩至大容器 ζ={zeta_exp:.4f}, 大容器突缩 ζ={zeta_cont:.4f}")


def test_pipe_impedance_series_parallel():
    print("\n--- 管道比阻 + 串/并联 ---")
    i = _interp()
    g = G_STANDARD
    # S = 8fL/(gπ²D^5), f=0.02, L=100, D=0.2
    S1 = i.call("管损_比阻", 0.02, 100, 0.2, g)
    expected_S = 8 * 0.02 * 100 / (g * math.pi * math.pi * (0.2 ** 5))
    assert abs(S1 - expected_S) < 1e-6
    # 串联 S_eq = S1 + S2
    S_series = i.call("管损_串联比阻", S1, S1)
    assert abs(S_series - 2 * S1) < 1e-12
    # 并联 1/√S_eq = 2/√S1 → S_eq = S1 / 4
    S_parallel = i.call("管损_并联比阻", S1, S1)
    expected_p = S1 / 4.0
    assert abs(S_parallel - expected_p) < 1e-6 * expected_p
    print(f"  ✓ S1={S1:.3f}, 串联=2S1={S_series:.2f}, 两相同支管并联=S1/4={S_parallel:.3f}")


def test_entry_exit_and_lookup():
    print("\n--- 入口/出口损失 + 阻力查询 ---")
    i = _interp()
    z_in = i.call("管损_锐缘入口系数")
    z_out = i.call("管损_出口损失系数")
    assert abs(z_in - 0.5) < 1e-15
    assert abs(z_out - 1.0) < 1e-15
    z_gate = i.call("管损_阻力系数查询", "闸阀_全开")
    z_elbow = i.call("管损_阻力系数查询", "90度弯头_常规")
    assert z_gate == K_MINOR["闸阀_全开"]
    assert z_elbow == K_MINOR["90度弯头_常规"]
    # 不存在的键 → 0
    z_none = i.call("管损_阻力系数查询", "不存在的键")
    assert z_none == 0.0
    print(f"  ✓ 入口 ζ={z_in}, 出口 ζ={z_out}, 闸阀全开 ζ={z_gate}, 90°弯头 ζ={z_elbow}")


# ===== 6. 物理常量与数据库 =====
def test_physical_constants():
    print("\n--- 物理常量 + 数据库 ---")
    i = _interp()
    assert i.builtins["g_标准"] == G_STANDARD
    assert i.builtins["gamma_空气"] == GAMMA_AIR
    assert i.builtins["R_空气气体常数"] == R_AIR
    assert i.builtins["糙率_塑料管"] == MANNING_N["塑料管"]
    assert i.builtins["K局_截止阀_全开"] == K_MINOR["截止阀_全开"]
    n_const = 6 + len(MANNING_N) + len(K_MINOR)
    print(f"  ✓ 6 通用常量 + {len(MANNING_N)} 曼宁糙率 + {len(K_MINOR)} 局部阻力系数 全部正确")


# ===== 7. Matha 侧综合场景 =====
def test_matha_scenario_boundary_layer():
    print("\n--- 综合场景：边界层沿程增长 ---")
    src = """
#：{
  U = 30
  nu = 0.000015
  Cf = 边界_层流平板阻力系数(500000)
  d1 = 边界_层流厚度(U)(1)(nu)
  d2 = 边界_层流厚度(U)(5)(nu)
  [Cf]
  [d1]
  [d2]
}
"""
    out = _call(src)
    Cf, d1, d2 = out
    expected_Cf = 1.328 / math.sqrt(5e5)
    assert abs(Cf - expected_Cf) < 1e-8
    assert d2 > d1
    print(f"  ✓ Cf(5e5)={Cf:.5f}, δ(x=1m)={d1*1000:.2f}mm, δ(x=5m)={d2*1000:.2f}mm")


def test_matha_scenario_shock_wave():
    print("\n--- 综合场景：Ma=2 正激波参量 ---")
    src = """
#：{
  g = gamma_空气
  Ma1 = 2
  p2p1 = 可压缩_激波压强比(g)(Ma1)
  Ma2 = 可压缩_激波后马赫数(g)(Ma1)
  p_starp0 = 可压缩_临界压强比(g)
  [p2p1]
  [Ma2]
  [p_starp0]
}
"""
    out = _call(src)
    p2p1, Ma2, psp0 = out
    expected_pr = (2 * 1.4 * 4 - 0.4) / 2.4
    assert abs(p2p1 - expected_pr) < 1e-8
    assert Ma2 < 1.0  # 亚声速
    expected_psp0 = (2.0 / 2.4) ** (1.4 / 0.4)
    assert abs(psp0 - expected_psp0) < 1e-8
    print(f"  ✓ p2/p1={p2p1:.2f}, Ma2={Ma2:.4f}(亚声), p*/p0={psp0:.4f}")


def test_matha_scenario_open_channel():
    print("\n--- 综合场景：矩形渠水力学 ---")
    src = """
#：{
  g = g_标准
  b = 3
  h = 1.2
  Q = 4.5
  R = 明渠_矩形水力半径(b)(h)
  n = 糙率_混凝土_光滑
  v = Q / (b * h)
  Fr = 明渠_弗劳德数(v)(h)(g)
  流态 = 明渠_流态判断(Fr)
  S = 0.0005
  v_manning = 明渠_曼宁流速_SI(n)(R)(S)
  [R]
  [Fr]
  [v_manning]
}
"""
    out = _call(src)
    R, Fr, v_man = out
    expected_R = 3 * 1.2 / (3 + 2 * 1.2)
    assert abs(R - expected_R) < 1e-6
    v = 4.5 / (3 * 1.2)
    expected_Fr = v / math.sqrt(G_STANDARD * 1.2)
    assert abs(Fr - expected_Fr) < 1e-6
    print(f"  ✓ R={R:.3f}m, Fr={Fr:.3f}, 曼宁流速={v_man:.3f}m/s")


def test_matha_scenario_pipe_network():
    print("\n--- 综合场景：突扩水头损失与串联比阻 ---")
    src = """
#：{
  g = g_标准
  D1 = 0.1
  D2 = 0.2
  v1 = 2
  A1 = D1*D1*0.7854
  A2 = D2*D2*0.7854
  zeta = 管损_突扩阻力系数(A1)(A2)
  h_m = 管损_局部水头损失(zeta)(v1)(g)
  f = 0.02
  L1 = 50
  L2 = 30
  S1 = 管损_比阻(f)(L1)(D1)(g)
  S2 = 管损_比阻(f)(L2)(D2)(g)
  S_eq = 管损_串联比阻(S1)(S2)
  [zeta]
  [h_m]
  [S_eq]
}
"""
    out = _call(src)
    zeta, h_m, S_eq = out
    # A1 = 0.007854, A2 = 0.031416 → A1/A2 = 0.25, ζ=(1-0.25)²=0.5625
    A1, A2 = 0.01 * 0.7854, 0.04 * 0.7854
    expected_zeta = (1 - A1 / A2) ** 2
    assert abs(zeta - expected_zeta) < 1e-4
    print(f"  ✓ 突扩 ζ={zeta:.4f}, h_m={h_m:.4f}m, 串联比阻 S_eq={S_eq:.2f}")


# ===== 入口 =====
if __name__ == "__main__":
    tests = [
        test_fluid_exp_registered_in_interp,
        test_fluid_exp_registered_in_semantic,
        test_laminar_boundary_layer,
        test_plate_friction_coefficient,
        test_turbulent_boundary_layer,
        test_speed_of_sound_and_mach,
        test_isentropic_relations,
        test_normal_shock,
        test_critical_and_nozzle,
        test_prandtl_meyer,
        test_chezy_and_manning,
        test_trapezoidal_and_froude,
        test_critical_depth_and_hydraulic_jump,
        test_pump_head_power_efficiency,
        test_specific_speed_and_similarity,
        test_fan_power,
        test_minor_loss_and_equivalent_length,
        test_abrupt_expansion_contraction,
        test_pipe_impedance_series_parallel,
        test_entry_exit_and_lookup,
        test_physical_constants,
        test_matha_scenario_boundary_layer,
        test_matha_scenario_shock_wave,
        test_matha_scenario_open_channel,
        test_matha_scenario_pipe_network,
    ]
    pass_cnt = 0
    for t in tests:
        t()
        pass_cnt += 1
    print()
    print("✓✓✓", pass_cnt, "个流体力学进阶测试全部通过 ✓✓✓")
