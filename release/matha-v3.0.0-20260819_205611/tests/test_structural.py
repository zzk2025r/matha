"""Matha 结构力学测试：应力状态 + 梁弯曲 + 压杆稳定 + 桁架结构 + 应变能冲击。

覆盖：
  1) 应力状态：莫尔圆主应力、最大剪应力、截面应力、主应力方向、von Mises/Tresca、体积应变
  2) 梁的弯曲：简支梁/悬臂梁均布/集中载荷的弯矩/挠度/转角、弯曲正应力/剪应力
  3) 压杆稳定：欧拉临界力/应力、长细比、回转半径、临界长细比、安全压力
  4) 桁架与结构：支座反力、杆件内力、超静定次数、合力
  5) 应变能与冲击：轴向/弯曲/剪切/扭转应变能、动荷系数、应变能密度
  6) Matha 侧综合场景

运行：python -m tests.test_structural
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.structural import _structural_symtab_names


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


# ============================================================
# 0. 注册性测试
# ============================================================

def test_structural_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _structural_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个结构力学内建名全部注册")


def test_structural_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[应力_主应力1(100)(50)(30) + 梁_简支均布弯矩(10)(5)]"
    ok = _semantic_ok(src)
    assert ok, "引用结构力学内建触发语义错误"
    print("  ✓ 结构力学内建在语义侧可直接引用")


# ============================================================
# 1. 应力状态分析
# ============================================================

def test_principal_stresses():
    print("\n--- 莫尔圆主应力 ---")
    i = _interp()
    # σx=80, σy=20, τxy=30 → σ1=95.4, σ2=4.6
    s1 = i.call("应力_主应力1", 80, 20, 30)
    s2 = i.call("应力_主应力2", 80, 20, 30)
    avg = (80 + 20) / 2
    r = math.sqrt(((80 - 20) / 2) ** 2 + 30 ** 2)
    assert abs(s1 - (avg + r)) < 1e-10
    assert abs(s2 - (avg - r)) < 1e-10
    print(f"  ✓ σ1={s1:.2f}MPa, σ2={s2:.2f}MPa")


def test_max_shear_stress():
    print("\n--- 最大剪应力 ---")
    i = _interp()
    tau_max = i.call("应力_最大剪应力", 80, 20, 30)
    r = math.sqrt(((80 - 20) / 2) ** 2 + 30 ** 2)
    assert abs(tau_max - r) < 1e-10
    print(f"  ✓ τmax={tau_max:.2f}MPa")


def test_principal_direction():
    print("\n--- 主应力方向 ---")
    i = _interp()
    theta_p = i.call("应力_主应力方向", 80, 20, 30)
    expected = 0.5 * math.atan2(60, 60)
    assert abs(theta_p - expected) < 1e-12
    print(f"  ✓ θp={math.degrees(theta_p):.2f}°")


def test_section_stress():
    print("\n--- 任意截面应力 ---")
    i = _interp()
    # θ=30°
    theta = math.radians(30)
    sn = i.call("应力_截面正应力", 80, 20, 30, theta)
    tn = i.call("应力_截面剪应力", 80, 20, 30, theta)
    expected_sn = 50 + 30 * math.cos(math.radians(60)) + 30 * math.sin(math.radians(60))
    expected_tn = -30 * math.sin(math.radians(60)) + 30 * math.cos(math.radians(60))
    assert abs(sn - expected_sn) < 1e-10
    assert abs(tn - expected_tn) < 1e-10
    print(f"  ✓ θ=30°: σn={sn:.2f}MPa, τn={tn:.2f}MPa")


def test_von_mises_and_tresca():
    print("\n--- von Mises 与 Tresca 等效应力 ---")
    i = _interp()
    # σ1=100, σ2=50, σ3=0
    vm = i.call("应力_vonMises", 100, 50, 0)
    expected_vm = math.sqrt(100**2 + 50**2 - 100*50)
    assert abs(vm - expected_vm) < 1e-10
    tr = i.call("应力_Tresca", 100, 50, 0)
    assert abs(tr - 100) < 1e-10  # σ1-σ3 = 100-0 = 100
    print(f"  ✓ von Mises={vm:.2f}MPa, Tresca={tr}MPa")


def test_volumetric_strain():
    print("\n--- 体积应变 ---")
    i = _interp()
    # σx=100, σy=50, σz=0, E=200GPa, ν=0.3
    theta_v = i.call("应力_体积应变", 100e6, 50e6, 0, 200e9, 0.3)
    expected = (1 - 0.6) * (100e6 + 50e6) / 200e9
    assert abs(theta_v - expected) < 1e-15
    print(f"  ✓ θ={theta_v:.6e}")


# ============================================================
# 2. 梁的弯曲
# ============================================================

def test_simply_supported_beam():
    print("\n--- 简支梁 ---")
    i = _interp()
    q, L, E_val, I_val = 10000, 6.0, 200e9, 8.33e-6
    # 均布载荷
    M_max = i.call("梁_简支均布弯矩", q, L)
    assert abs(M_max - q * L**2 / 8) < 1e-6
    delta_max = i.call("梁_简支均布挠度", q, L, E_val, I_val)
    assert abs(delta_max - 5 * q * L**4 / (384 * E_val * I_val)) < 1e-15
    theta_end = i.call("梁_简支均布转角", q, L, E_val, I_val)
    assert abs(theta_end - q * L**3 / (24 * E_val * I_val)) < 1e-15
    # 跨中集中力
    P = 20000
    M_p = i.call("梁_简支集中弯矩", P, L)
    assert abs(M_p - P * L / 4) < 1e-6
    delta_p = i.call("梁_简支集中挠度", P, L, E_val, I_val)
    assert abs(delta_p - P * L**3 / (48 * E_val * I_val)) < 1e-15
    theta_p = i.call("梁_简支集中转角", P, L, E_val, I_val)
    assert abs(theta_p - P * L**2 / (16 * E_val * I_val)) < 1e-15
    print(f"  ✓ 均布: M={M_max:.0f}N·m, δ={delta_max*1000:.4f}mm")
    print(f"  ✓ 集中: M={M_p:.0f}N·m, δ={delta_p*1000:.4f}mm")


def test_cantilever_beam():
    print("\n--- 悬臂梁 ---")
    i = _interp()
    q, L, E_val, I_val = 5000, 3.0, 200e9, 4e-6
    # 均布载荷
    M_max = i.call("梁_悬臂均布弯矩", q, L)
    assert abs(M_max - q * L**2 / 2) < 1e-6
    delta_max = i.call("梁_悬臂均布挠度", q, L, E_val, I_val)
    assert abs(delta_max - q * L**4 / (8 * E_val * I_val)) < 1e-15
    # 端部集中力
    P = 10000
    M_p = i.call("梁_悬臂集中弯矩", P, L)
    assert abs(M_p - P * L) < 1e-6
    delta_p = i.call("梁_悬臂集中挠度", P, L, E_val, I_val)
    assert abs(delta_p - P * L**3 / (3 * E_val * I_val)) < 1e-15
    theta_p = i.call("梁_悬臂集中转角", P, L, E_val, I_val)
    assert abs(theta_p - P * L**2 / (2 * E_val * I_val)) < 1e-15
    print(f"  ✓ 均布: M={M_max:.0f}N·m, δ={delta_max*1000:.4f}mm")
    print(f"  ✓ 集中: M={M_p:.0f}N·m, δ={delta_p*1000:.4f}mm")


def test_beam_stress():
    print("\n--- 梁弯曲应力 ---")
    i = _interp()
    # σ = My/I: M=1000, y=0.05, I=8.33e-6 → 6000 Pa
    sigma = i.call("梁_弯曲正应力", 1000, 0.05, 8.33e-6)
    assert abs(sigma - 1000 * 0.05 / 8.33e-6) < 1
    # τ = 3V/(2A): V=500, A=0.01 → 75000 Pa
    tau = i.call("梁_矩形剪应力", 500, 0.01)
    assert abs(tau - 75000) < 1e-6
    print(f"  ✓ σ={sigma:.0f}Pa, τ={tau:.0f}Pa")


# ============================================================
# 3. 压杆稳定
# ============================================================

def test_euler_buckling():
    print("\n--- 欧拉临界力 ---")
    i = _interp()
    # E=200GPa, I=8.33e-6, μ=1.0(两端铰支), L=3m
    E_val, I_val, mu, L = 200e9, 8.33e-6, 1.0, 3.0
    P_cr = i.call("压杆_欧拉临界力", E_val, I_val, mu, L)
    expected = math.pi**2 * E_val * I_val / (mu * L)**2
    assert abs(P_cr - expected) < 1e-3
    print(f"  ✓ Pcr={P_cr:.2f}N ({P_cr/1000:.2f}kN)")


def test_euler_critical_stress():
    print("\n--- 欧拉临界应力 ---")
    i = _interp()
    # E=200GPa, λ=100 → σcr = π²E/λ²
    E_val, lam = 200e9, 100.0
    sigma_cr = i.call("压杆_欧拉临界应力", E_val, lam)
    expected = math.pi**2 * E_val / lam**2
    assert abs(sigma_cr - expected) < 1
    print(f"  ✓ λ=100: σcr={sigma_cr/1e6:.2f}MPa")


def test_slenderness_ratio():
    print("\n--- 长细比与回转半径 ---")
    i = _interp()
    # r = √(I/A): I=8.33e-6, A=0.01 → r=0.02886m
    r = i.call("压杆_回转半径", 8.33e-6, 0.01)
    expected_r = math.sqrt(8.33e-6 / 0.01)
    assert abs(r - expected_r) < 1e-8
    # λ = μL/r: μ=1, L=3, r=0.02886 → λ≈103.95
    lam = i.call("压杆_长细比", 1.0, 3.0, r)
    expected_lam = 1.0 * 3.0 / expected_r
    assert abs(lam - expected_lam) < 1e-6
    # 长细比几何
    lam_g = i.call("压杆_长细比几何", 1.0, 3.0, 8.33e-6, 0.01)
    assert abs(lam_g - expected_lam) < 1e-6
    print(f"  ✓ r={r:.5f}m, λ={lam:.2f}")


def test_critical_slenderness():
    print("\n--- 临界长细比 ---")
    i = _interp()
    # E=200GPa, σp=200MPa → λp = π√(E/σp)
    E_val, sigma_p = 200e9, 200e6
    lam_p = i.call("压杆_临界长细比", E_val, sigma_p)
    expected = math.pi * math.sqrt(E_val / sigma_p)
    assert abs(lam_p - expected) < 1e-6
    print(f"  ✓ λp={lam_p:.2f}")


def test_safe_load():
    print("\n--- 安全工作压力 ---")
    i = _interp()
    # Pcr=100kN, n=2.5 → P_allow=40kN
    P_allow = i.call("压杆_安全压力", 100000, 2.5)
    assert abs(P_allow - 40000) < 1e-6
    print(f"  ✓ Pcr=100kN, n=2.5 → P_allow={P_allow/1000:.0f}kN")


# ============================================================
# 4. 桁架与结构
# ============================================================

def test_support_reactions():
    print("\n--- 支座反力 ---")
    i = _interp()
    # 简支梁均布: q=10kN/m, L=6m → RA=RB=30kN
    R = i.call("桁架_简支均布反力", 10000, 6)
    assert abs(R - 30000) < 1e-6
    # 简支梁集中: P=20kN → RA=RB=10kN
    R_p = i.call("桁架_简支集中反力", 20000)
    assert abs(R_p - 10000) < 1e-6
    # 悬臂梁均布: q=5kN/m, L=3m → R=15kN
    R_c = i.call("桁架_悬臂均布反力", 5000, 3)
    assert abs(R_c - 15000) < 1e-6
    # 悬臂梁集中: P=10kN → R=10kN
    R_cp = i.call("桁架_悬臂集中反力", 10000)
    assert abs(R_cp - 10000) < 1e-6
    print("  ✓ 简支/悬臂反力全部正确")


def test_truss_member_force():
    print("\n--- 桁架杆件内力 ---")
    i = _interp()
    # F=10kN, θ=30° → N = F/cos30° = 11.547kN
    N = i.call("桁架_杆件内力", 10000, math.radians(30))
    expected = 10000 / math.cos(math.radians(30))
    assert abs(N - expected) < 1e-6
    print(f"  ✓ F=10kN, θ=30° → N={N:.1f}N")


def test_static_indeterminacy():
    print("\n--- 超静定次数 ---")
    i = _interp()
    # m=7杆, r=3支座反力, j=5节点 → n=7+3-10=0（静定）
    n = i.call("桁架_超静定次数", 7, 3, 5)
    assert n == 0
    # m=10, r=3, j=6 → n=10+3-12=1（一次超静定）
    n2 = i.call("桁架_超静定次数", 10, 3, 6)
    assert n2 == 1
    print(f"  ✓ 7杆3反力5节点→静定, 10杆3反力6节点→{n2}次超静定")


def test_resultant_force():
    print("\n--- 合力 ---")
    i = _interp()
    # Fx=[3,4], Fy=[0,0] → R=7
    R = i.call("桁架_合力", [3, 4], [0, 0])
    assert abs(R - 7) < 1e-10
    # Fx=[3], Fy=[4] → R=5
    R2 = i.call("桁架_合力", [3], [4])
    assert abs(R2 - 5) < 1e-10
    print(f"  ✓ Fx=[3,4],Fy=[0] → R={R}; Fx=[3],Fy=[4] → R={R2}")


# ============================================================
# 5. 应变能与冲击
# ============================================================

def test_strain_energy():
    print("\n--- 应变能 ---")
    i = _interp()
    # 轴向: U = N²L/(2EA): N=50kN, L=2m, E=200GPa, A=0.001m²
    U_a = i.call("能量_轴向应变能", 50000, 2, 200e9, 0.001)
    expected_a = 50000**2 * 2 / (2 * 200e9 * 0.001)
    assert abs(U_a - expected_a) < 1e-6
    # 弯曲: U = M²L/(2EI): M=1000, L=3, E=200GPa, I=8e-6
    U_b = i.call("能量_弯曲应变能", 1000, 3, 200e9, 8e-6)
    expected_b = 1000**2 * 3 / (2 * 200e9 * 8e-6)
    assert abs(U_b - expected_b) < 1e-6
    # 剪切: U = V²L/(2GA): V=5000, L=2, G=80GPa, A=0.001
    U_s = i.call("能量_剪切应变能", 5000, 2, 80e9, 0.001)
    expected_s = 5000**2 * 2 / (2 * 80e9 * 0.001)
    assert abs(U_s - expected_s) < 1e-6
    # 扭转: U = T²L/(2GIp): T=500, L=1, G=80GPa, Ip=1e-7
    U_t = i.call("能量_扭转应变能", 500, 1, 80e9, 1e-7)
    expected_t = 500**2 * 1 / (2 * 80e9 * 1e-7)
    assert abs(U_t - expected_t) < 1e-6
    # 总应变能
    U_total = i.call("能量_总应变能", U_a, U_b, U_s)
    assert abs(U_total - (U_a + U_b + U_s)) < 1e-15
    print(f"  ✓ U轴向={U_a:.4f}J, U弯曲={U_b:.4f}J, U剪切={U_s:.4f}J, U扭转={U_t:.4f}J")


def test_impact_factor():
    print("\n--- 冲击动荷系数 ---")
    i = _interp()
    # Kd = 1+√(1+2h/Δst): h=0.01m, Δst=0.001m → 1+√(1+20)=1+√21
    Kd = i.call("能量_动荷系数", 0.01, 0.001)
    expected = 1 + math.sqrt(1 + 20)
    assert abs(Kd - expected) < 1e-10
    # h=0（突加荷载）→ Kd=2
    Kd_0 = i.call("能量_动荷系数", 0, 0.001)
    assert abs(Kd_0 - 2.0) < 1e-10
    print(f"  ✓ h=10mm,Δst=1mm → Kd={Kd:.4f}; 突加 Kd={Kd_0}")


def test_strain_energy_density():
    print("\n--- 应变能密度 ---")
    i = _interp()
    # u = σ²/(2E): σ=100MPa, E=200GPa → 100e6²/(2*200e9)
    u = i.call("能量_应变能密度", 100e6, 200e9)
    expected = 100e6**2 / (2 * 200e9)
    assert abs(u - expected) < 1e-6
    print(f"  ✓ u={u:.4f}J/m³")


# ============================================================
# 6. Matha 侧综合场景
# ============================================================

def test_matha_scenario_beam_design():
    """综合场景：简支钢梁设计验算。"""
    print("\n--- 综合场景：简支钢梁设计 ---")
    src = """
#：{
  q = 10000
  L = 6
  E_val = 206000000000
  I = 0.00000833
  M_max = 梁_简支均布弯矩(q)(L)
  delta_max = 梁_简支均布挠度(q)(L)(E_val)(I)
  y = 0.1
  sigma_max = 梁_弯曲正应力(M_max)(y)(I)
  [M_max]
  [delta_max]
  [sigma_max]
}
"""
    out = _call(src)
    M_max, delta_max, sigma_max = out[0], out[1], out[2]
    assert abs(M_max - 10000 * 36 / 8) < 1e-6
    assert abs(delta_max - 5 * 10000 * 6**4 / (384 * 206000000000 * 0.00000833)) < 1e-15
    assert abs(sigma_max - M_max * 0.1 / 0.00000833) < 1
    print(f"  ✓ M={M_max:.0f}N·m, δ={delta_max*1000:.2f}mm, σ={sigma_max/1e6:.2f}MPa")


def test_matha_scenario_column_buckling():
    """综合场景：钢柱稳定验算。"""
    print("\n--- 综合场景：钢柱稳定验算 ---")
    src = """
#：{
  E_val = 206000000000
  I = 0.00000417
  A = 0.003
  mu = 1.0
  L = 3.5
  r = 压杆_回转半径(I)(A)
  lam = 压杆_长细比(mu)(L)(r)
  P_cr = 压杆_欧拉临界力(E_val)(I)(mu)(L)
  n_safety = 2.5
  P_allow = 压杆_安全压力(P_cr)(n_safety)
  [r]
  [lam]
  [P_cr]
  [P_allow]
}
"""
    out = _call(src)
    r, lam, P_cr, P_allow = out[0], out[1], out[2], out[3]
    expected_r = math.sqrt(0.00000417 / 0.003)
    assert abs(r - expected_r) < 1e-8
    assert abs(lam - 3.5 / expected_r) < 1e-6
    expected_P = math.pi**2 * 206000000000 * 0.00000417 / 3.5**2
    assert abs(P_cr - expected_P) < 1
    assert abs(P_allow - P_cr / 2.5) < 1e-6
    print(f"  ✓ r={r:.5f}m, λ={lam:.1f}, Pcr={P_cr/1000:.1f}kN, P允许={P_allow/1000:.1f}kN")


def test_matha_scenario_mohr_circle():
    """综合场景：应力状态分析（莫尔圆）。"""
    print("\n--- 综合场景：莫尔圆应力分析 ---")
    src = """
#：{
  sx = 80000000
  sy = 20000000
  txy = 30000000
  s1 = 应力_主应力1(sx)(sy)(txy)
  s2 = 应力_主应力2(sx)(sy)(txy)
  tmax = 应力_最大剪应力(sx)(sy)(txy)
  vm = 应力_vonMises(s1)(s2)(0)
  [s1]
  [s2]
  [tmax]
  [vm]
}
"""
    out = _call(src)
    s1, s2, tmax, vm = out[0], out[1], out[2], out[3]
    avg = (80e6 + 20e6) / 2
    r = math.sqrt(((80e6 - 20e6) / 2)**2 + 30e6**2)
    assert abs(s1 - (avg + r)) < 1
    assert abs(s2 - (avg - r)) < 1
    assert abs(tmax - r) < 1
    expected_vm = math.sqrt(s1**2 + s2**2 - s1*s2)
    assert abs(vm - expected_vm) < 1
    print(f"  ✓ σ1={s1/1e6:.1f}MPa, σ2={s2/1e6:.1f}MPa, τmax={tmax/1e6:.1f}MPa, σeq={vm/1e6:.1f}MPa")


def test_matha_scenario_impact():
    """综合场景：冲击载荷计算。"""
    print("\n--- 综合场景：冲击载荷 ---")
    src = """
#：{
  h = 0.05
  P = 2000
  L = 2
  E_val = 206000000000
  I = 0.000004
  delta_st = 梁_悬臂集中挠度(P)(L)(E_val)(I)
  Kd = 能量_动荷系数(h)(delta_st)
  P_impact = Kd * P
  [delta_st]
  [Kd]
  [P_impact]
}
"""
    out = _call(src)
    delta_st, Kd, P_impact = out[0], out[1], out[2]
    expected_dst = 2000 * 8 / (3 * 206000000000 * 0.000004)
    assert abs(delta_st - expected_dst) < 1e-15
    expected_Kd = 1 + math.sqrt(1 + 2 * 0.05 / expected_dst)
    assert abs(Kd - expected_Kd) < 1e-10
    assert abs(P_impact - Kd * 2000) < 1e-6
    print(f"  ✓ Δst={delta_st*1000:.4f}mm, Kd={Kd:.2f}, P冲击={P_impact:.0f}N")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_structural_registered_in_interp,
        test_structural_registered_in_semantic,
        test_principal_stresses,
        test_max_shear_stress,
        test_principal_direction,
        test_section_stress,
        test_von_mises_and_tresca,
        test_volumetric_strain,
        test_simply_supported_beam,
        test_cantilever_beam,
        test_beam_stress,
        test_euler_buckling,
        test_euler_critical_stress,
        test_slenderness_ratio,
        test_critical_slenderness,
        test_safe_load,
        test_support_reactions,
        test_truss_member_force,
        test_static_indeterminacy,
        test_resultant_force,
        test_strain_energy,
        test_impact_factor,
        test_strain_energy_density,
        test_matha_scenario_beam_design,
        test_matha_scenario_column_buckling,
        test_matha_scenario_mohr_circle,
        test_matha_scenario_impact,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个结构力学测试全部通过 ✓✓✓")
