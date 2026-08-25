"""Matha 量子力学测试：波函数 + 不确定性原理 + 角动量自旋 + 势阱能级 + 量子隧穿。

覆盖：
  1) 波函数：德布罗意波长、概率密度、自由粒子能量、动量波数关系
  2) 不确定性原理：位置-动量、能量-时间不确定性
  3) 角动量与自旋：轨道/自旋/总角动量、磁矩、朗德g因子
  4) 势阱与能级：无限深势阱、氢原子能级、谐振子能级
  5) 量子隧穿：WKB概率、方势垒透射、光电效应、康普顿散射
  6) 物理常量数据库
  7) Matha 侧综合场景

运行：python -m tests.test_quantum
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.quantum import (
    _quantum_symtab_names, H_PLANCK, HBAR, E_CHARGE, M_ELECTRON, M_PROTON,
    A_BOHR, RY_ENERGY, MU_B, LAMBDA_C, ALPHA_FS, N_A, C_LIGHT,
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


# ============================================================
# 0. 注册性测试
# ============================================================

def test_quantum_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _quantum_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个量子力学内建名全部注册")


def test_quantum_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[波_德布罗意波长动量(1e-24) + 势阱_氢原子能级eV(1)]"
    ok = _semantic_ok(src)
    assert ok, "引用量子力学内建触发语义错误"
    print("  ✓ 量子力学内建在语义侧可直接引用")


# ============================================================
# 1. 波函数与薛定谔方程
# ============================================================

def test_de_broglie_wavelength():
    print("\n--- 德布罗意波长 ---")
    i = _interp()
    # 电子 m=9.109e-31, v=1e6 m/s → λ = h/(mv)
    lam = i.call("波_德布罗意波长", M_ELECTRON, 1e6)
    expected = H_PLANCK / (M_ELECTRON * 1e6)
    assert abs(lam - expected) < 1e-30
    # 由动量
    p = M_ELECTRON * 1e6
    lam2 = i.call("波_德布罗意波长动量", p)
    assert abs(lam2 - expected) < 1e-30
    print(f"  ✓ 电子 v=10⁶m/s: λ={lam*1e9:.4f}nm")


def test_probability_density():
    print("\n--- 概率密度 ---")
    i = _interp()
    # ψ=0.5+0.5i → |ψ|²=0.5
    import cmath
    psi = complex(0.5, 0.5)
    rho = i.call("波_概率密度", psi)
    assert abs(rho - 0.5) < 1e-15
    # 实数波函数 ψ=3 → |ψ|²=9
    rho2 = i.call("波_概率密度", 3.0)
    assert abs(rho2 - 9.0) < 1e-15
    print(f"  ✓ ψ=0.5+0.5i → ρ={rho}; ψ=3 → ρ={rho2}")


def test_free_particle_energy():
    print("\n--- 自由粒子能量 ---")
    i = _interp()
    # E = ℏ²k²/(2m): k=1e10, m=me
    k = 1e10
    E = i.call("波_自由粒子能量", k, M_ELECTRON)
    expected = HBAR ** 2 * k ** 2 / (2 * M_ELECTRON)
    assert abs(E - expected) < 1e-30
    print(f"  ✓ E={E:.4e}J")


def test_momentum_wavenumber():
    print("\n--- 动量与波数 ---")
    i = _interp()
    # p = ℏk: k=1e10 → p=ℏ·1e10
    p = i.call("波_动量由波数", 1e10)
    assert abs(p - HBAR * 1e10) < 1e-40
    # k = p/ℏ
    k_back = i.call("波_波数由动量", p)
    assert abs(k_back - 1e10) < 1e-5
    print(f"  ✓ k=1e10 → p={p:.4e}kg·m/s, 反算 k={k_back:.4e}")


def test_energy_frequency_relation():
    print("\n--- 能量-频率关系 ---")
    i = _interp()
    # E = ℏω: ω=1e15
    E = i.call("波_能量由频率", 1e15)
    assert abs(E - HBAR * 1e15) < 1e-20
    # ω = E/ℏ
    omega = i.call("波_角频率由能量", E)
    assert abs(omega - 1e15) < 1e5
    print(f"  ✓ ω=1e15 → E={E:.4e}J, 反算 ω={omega:.4e}")


def test_kinetic_energy_expectation():
    print("\n--- 动能期望值 ---")
    i = _interp()
    # <T> = p²/(2m): p=1e-24, m=me
    T = i.call("波_动能期望", 1e-24, M_ELECTRON)
    expected = 1e-48 / (2 * M_ELECTRON)
    assert abs(T - expected) < 1e-30
    print(f"  ✓ <T>={T:.4e}J")


# ============================================================
# 2. 不确定性原理
# ============================================================

def test_position_momentum_uncertainty():
    print("\n--- 位置-动量不确定性 ---")
    i = _interp()
    # Δx=1e-10 → Δp ≥ ℏ/(2Δx)
    dp = i.call("不确定_动量不确定度", 1e-10)
    expected = HBAR / (2e-10)
    assert abs(dp - expected) < 1e-40
    # 反算
    dx = i.call("不确定_位置不确定度", dp)
    assert abs(dx - 1e-10) < 1e-15
    print(f"  ✓ Δx=1Å → Δp≥{dp:.4e}kg·m/s")


def test_energy_time_uncertainty():
    print("\n--- 能量-时间不确定性 ---")
    i = _interp()
    # Δt=1e-12 → ΔE ≥ ℏ/(2Δt)
    dE = i.call("不确定_能量不确定度", 1e-12)
    expected = HBAR / (2e-12)
    assert abs(dE - expected) < 1e-30
    # 反算
    dt = i.call("不确定_时间不确定度", dE)
    assert abs(dt - 1e-12) < 1e-20
    print(f"  ✓ Δt=1ps → ΔE≥{dE:.4e}J")


def test_uncertainty_limit():
    print("\n--- 不确定性下限 ---")
    i = _interp()
    limit = i.call("不确定_下限")
    assert abs(limit - HBAR / 2) < 1e-40
    print(f"  ✓ ℏ/2={limit:.4e}J·s")


def test_uncertainty_verification():
    print("\n--- 不确定性验证 ---")
    i = _interp()
    # Δx=1e-10, Δp=1e-24 → Δx·Δp=1e-34 vs ℏ/2≈5.27e-35 → 通过
    ok = i.call("不确定_验证", 1e-10, 1e-24)
    assert ok == True
    # Δx=1e-20, Δp=1e-20 → 1e-40 < ℏ/2 → 不通过
    ok2 = i.call("不确定_验证", 1e-20, 1e-20)
    assert ok2 == False
    print(f"  ✓ Δx=1Å,Δp=1e-24 → 通过; Δx=Δp=1e-20 → 不通过")


# ============================================================
# 3. 角动量与自旋
# ============================================================

def test_orbital_angular_momentum():
    print("\n--- 轨道角动量 ---")
    i = _interp()
    # l=1 → |L| = ℏ√2
    L = i.call("角动_轨道模", 1)
    assert abs(L - HBAR * math.sqrt(2)) < 1e-40
    # l=2 → |L| = ℏ√6
    L2 = i.call("角动_轨道模", 2)
    assert abs(L2 - HBAR * math.sqrt(6)) < 1e-40
    # Lz: ml=1 → ℏ
    Lz = i.call("角动_轨道z", 1)
    assert abs(Lz - HBAR) < 1e-40
    print(f"  ✓ l=1: |L|={L:.4e}, l=2: |L|={L2:.4e}, Lz(ml=1)={Lz:.4e}")


def test_spin_angular_momentum():
    print("\n--- 自旋角动量 ---")
    i = _interp()
    # 电子 s=1/2 → |S| = ℏ√(3/4)
    S = i.call("角动_自旋模", 0.5)
    expected = HBAR * math.sqrt(0.5 * 1.5)
    assert abs(S - expected) < 1e-40
    # Sz: ms=+1/2 → ℏ/2
    Sz = i.call("角动_自旋z", 0.5)
    assert abs(Sz - HBAR / 2) < 1e-40
    print(f"  ✓ s=1/2: |S|={S:.4e}, Sz(+1/2)={Sz:.4e}")


def test_total_angular_momentum():
    print("\n--- 总角动量 ---")
    i = _interp()
    # j=3/2 → |J| = ℏ√(15/4)
    J = i.call("角动_总模", 1.5)
    expected = HBAR * math.sqrt(1.5 * 2.5)
    assert abs(J - expected) < 1e-40
    # Jz: mj=3/2 → 3ℏ/2
    Jz = i.call("角动_总z", 1.5)
    assert abs(Jz - 1.5 * HBAR) < 1e-40
    print(f"  ✓ j=3/2: |J|={J:.4e}, Jz(3/2)={Jz:.4e}")


def test_magnetic_moment():
    print("\n--- 磁矩 ---")
    i = _interp()
    # μ = -μ_B·g·m: g=2, m=1/2 → -μ_B
    mu = i.call("角动_磁矩", 2, 0.5)
    expected = -MU_B * 2 * 0.5
    assert abs(mu - expected) < 1e-35
    print(f"  ✓ g=2, m=1/2 → μ={mu:.4e}J/T")


def test_landé_g_factor():
    print("\n--- 朗德g因子 ---")
    i = _interp()
    # J=1/2, L=0, S=1/2 → g=2（纯自旋）
    g = i.call("角动_朗德g", 0.5, 0, 0.5)
    assert abs(g - 2.0) < 1e-10
    # J=1, L=1, S=0 → g=1（纯轨道）
    g2 = i.call("角动_朗德g", 1, 1, 0)
    assert abs(g2 - 1.0) < 1e-10
    print(f"  ✓ 纯自旋 g={g}, 纯轨道 g={g2}")


# ============================================================
# 4. 势阱与能级
# ============================================================

def test_infinite_well():
    print("\n--- 无限深方势阱 ---")
    i = _interp()
    # En = n²π²ℏ²/(2mL²): n=1, m=me, L=1e-9
    E1 = i.call("势阱_无限深能级", 1, M_ELECTRON, 1e-9)
    expected = math.pi ** 2 * HBAR ** 2 / (2 * M_ELECTRON * 1e-18)
    assert abs(E1 - expected) < 1e-30
    # n=2 → 4E1
    E2 = i.call("势阱_无限深能级", 2, M_ELECTRON, 1e-9)
    assert abs(E2 - 4 * expected) < 1e-30
    print(f"  ✓ L=1nm: E1={E1:.4e}J, E2={E2:.4e}J (4E1)")


def test_hydrogen_energy_levels():
    print("\n--- 氢原子能级 ---")
    i = _interp()
    # n=1 → -13.6 eV
    E1_eV = i.call("势阱_氢原子能级eV", 1)
    assert abs(E1_eV - (-13.6)) < 1e-10
    # n=2 → -3.4 eV
    E2_eV = i.call("势阱_氢原子能级eV", 2)
    assert abs(E2_eV - (-3.4)) < 1e-10
    # n=1 → -Ry (Joule)
    E1_J = i.call("势阱_氢原子能级J", 1)
    assert abs(E1_J - (-RY_ENERGY)) < 1e-30
    print(f"  ✓ n=1: {E1_eV}eV = {E1_J:.4e}J, n=2: {E2_eV}eV")


def test_harmonic_oscillator():
    print("\n--- 谐振子能级 ---")
    i = _interp()
    # En = (n+1/2)ℏω: n=0, ω=1e14
    E0 = i.call("势阱_谐振子能级", 0, 1e14)
    expected = 0.5 * HBAR * 1e14
    assert abs(E0 - expected) < 1e-20
    # n=1 → 3/2 ℏω
    E1 = i.call("势阱_谐振子能级", 1, 1e14)
    assert abs(E1 - 1.5 * HBAR * 1e14) < 1e-20
    print(f"  ✓ E0={E0:.4e}J, E1={E1:.4e}J (3E0)")


def test_oscillator_length():
    print("\n--- 谐振子特征长度 ---")
    i = _interp()
    # a = √(ℏ/(mω)): m=me, ω=1e14
    a = i.call("势阱_谐振子特征长度", M_ELECTRON, 1e14)
    expected = math.sqrt(HBAR / (M_ELECTRON * 1e14))
    assert abs(a - expected) < 1e-25
    print(f"  ✓ a={a:.4e}m")


def test_hydrogen_radius():
    print("\n--- 氢原子轨道半径 ---")
    i = _interp()
    # n=1 → a₀
    r1 = i.call("势阱_氢原子半径", 1)
    assert abs(r1 - A_BOHR) < 1e-20
    # n=2 → 4a₀
    r2 = i.call("势阱_氢原子半径", 2)
    assert abs(r2 - 4 * A_BOHR) < 1e-20
    print(f"  ✓ n=1: r={r1*1e9:.4f}nm, n=2: r={r2*1e9:.4f}nm")


def test_ionization_energy():
    print("\n--- 氢原子电离能 ---")
    i = _interp()
    E_ion = i.call("势阱_氢原子电离能")
    assert abs(E_ion - RY_ENERGY) < 1e-30
    print(f"  ✓ E_ion={E_ion:.4e}J = {E_ion/E_CHARGE:.2f}eV")


# ============================================================
# 5. 量子隧穿与散射
# ============================================================

def test_decay_constant():
    print("\n--- 衰减常数 ---")
    i = _interp()
    # κ = √(2m(V₀-E))/ℏ: m=me, V₀=2e-18, E=1e-18
    kappa = i.call("隧穿_衰减常数", M_ELECTRON, 2e-18, 1e-18)
    expected = math.sqrt(2 * M_ELECTRON * 1e-18) / HBAR
    assert abs(kappa - expected) < 1e-5
    # E ≥ V₀ → κ=0
    kappa_zero = i.call("隧穿_衰减常数", M_ELECTRON, 1e-18, 2e-18)
    assert kappa_zero == 0.0
    print(f"  ✓ κ={kappa:.4e}/m (E<V₀), κ=0 (E≥V₀)")


def test_wkb_tunneling():
    print("\n--- WKB 隧穿概率 ---")
    i = _interp()
    # T = exp(-2κa): κ=1e10, a=1e-9 → exp(-20)
    T = i.call("隧穿_WKB概率", 1e10, 1e-9)
    expected = math.exp(-20)
    assert abs(T - expected) < 1e-15
    # 直接形式
    T2 = i.call("隧穿_WKB概率直接", M_ELECTRON, 2e-18, 1e-18, 1e-9)
    kappa = math.sqrt(2 * M_ELECTRON * 1e-18) / HBAR
    expected2 = math.exp(-2 * kappa * 1e-9)
    assert abs(T2 - expected2) < 1e-15
    print(f"  ✓ T={T:.6e}, T_direct={T2:.6e}")


def test_rectangular_barrier():
    print("\n--- 方势垒透射系数 ---")
    i = _interp()
    # E < V₀: E=1e-18, V₀=2e-18, m=me, a=1e-10
    T = i.call("隧穿_方势垒透射", 1e-18, 2e-18, M_ELECTRON, 1e-10)
    kappa = math.sqrt(2 * M_ELECTRON * 1e-18) / HBAR
    sinh_term = math.sinh(kappa * 1e-10) ** 2
    expected = 1.0 / (1 + (2e-18) ** 2 * sinh_term / (4 * 1e-18 * 1e-18))
    assert abs(T - expected) < 1e-15
    print(f"  ✓ T={T:.6e}")


def test_photoelectric_effect():
    print("\n--- 光电效应 ---")
    i = _interp()
    # Kmax = hf - φ: f=1e15, φ=3e-19 (≈1.87eV, 钾)
    K = i.call("隧穿_光电效应", 1e15, 3e-19)
    expected = H_PLANCK * 1e15 - 3e-19
    assert abs(K - expected) < 1e-30
    # 截止频率: f₀ = φ/h
    f0 = i.call("隧穿_截止频率", 3e-19)
    expected_f0 = 3e-19 / H_PLANCK
    assert abs(f0 - expected_f0) < 1e-5
    print(f"  ✓ Kmax={K:.4e}J, f₀={f0:.4e}Hz")


def test_compton_wavelength():
    print("\n--- 康普顿波长 ---")
    i = _interp()
    # 电子康普顿波长: λC = h/(m_e·c)
    lam_C = i.call("隧穿_康普顿波长", M_ELECTRON)
    expected = H_PLANCK / (M_ELECTRON * C_LIGHT)
    assert abs(lam_C - expected) < 1e-20
    assert abs(lam_C - LAMBDA_C) < 1e-20
    print(f"  ✓ λC={lam_C*1e12:.4f}pm")


def test_compton_shift():
    print("\n--- 康普顿散射偏移 ---")
    i = _interp()
    # θ=90° → Δλ = λC
    dlam = i.call("隧穿_康普顿偏移", math.radians(90))
    assert abs(dlam - LAMBDA_C) < 1e-20
    # θ=0° → Δλ = 0
    dlam_0 = i.call("隧穿_康普顿偏移", 0)
    assert abs(dlam_0) < 1e-30
    # θ=180° → Δλ = 2λC
    dlam_180 = i.call("隧穿_康普顿偏移", math.pi)
    assert abs(dlam_180 - 2 * LAMBDA_C) < 1e-20
    print(f"  ✓ θ=90°: Δλ={dlam*1e12:.4f}pm, θ=180°: Δλ={dlam_180*1e12:.4f}pm")


# ============================================================
# 6. 物理常量数据库
# ============================================================

def test_quantum_constants():
    print("\n--- 物理常量数据库 ---")
    i = _interp()
    assert i.builtins["h_普朗克"] == H_PLANCK
    assert i.builtins["hbar_约化普朗克"] == HBAR
    assert i.builtins["e_电荷"] == E_CHARGE
    assert i.builtins["me_电子质量"] == M_ELECTRON
    assert i.builtins["mp_质子质量"] == M_PROTON
    assert i.builtins["a0_玻尔半径"] == A_BOHR
    assert i.builtins["Ry_里德伯能"] == RY_ENERGY
    assert i.builtins["muB_玻尔磁子"] == MU_B
    assert i.builtins["lambdaC_康普顿波长"] == LAMBDA_C
    assert i.builtins["alpha_精细结构"] == ALPHA_FS
    assert i.builtins["NA_阿伏伽德罗"] == N_A
    print(f"  ✓ 11 个物理常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_electron_diffraction():
    """综合场景：电子衍射（德布罗意波长）。"""
    print("\n--- 综合场景：电子衍射 ---")
    src = """
#：{
  m = me_电子质量
  v = 1500000
  lam = 波_德布罗意波长(m)(v)
  p = m * v
  E = 波_动能期望(p)(m)
  [lam]
  [E]
}
"""
    out = _call(src)
    lam, E = out[0], out[1]
    expected_lam = H_PLANCK / (M_ELECTRON * 1.5e6)
    expected_E = (M_ELECTRON * 1.5e6) ** 2 / (2 * M_ELECTRON)
    assert abs(lam - expected_lam) < 1e-30
    assert abs(E - expected_E) < 1e-20
    print(f"  ✓ v=1.5×10⁶m/s: λ={lam*1e9:.4f}nm, E={E:.4e}J ({E/E_CHARGE:.2f}eV)")


def test_matha_scenario_hydrogen_spectrum():
    """综合场景：氢原子光谱（能级跃迁）。"""
    print("\n--- 综合场景：氢原子光谱 ---")
    src = """
#：{
  E1 = 势阱_氢原子能级eV(1)
  E2 = 势阱_氢原子能级eV(2)
  E3 = 势阱_氢原子能级eV(3)
  dE_21 = E2 - 1 * E1
  dE_31 = E3 - 1 * E1
  [E1]
  [E2]
  [dE_21]
  [dE_31]
}
"""
    out = _call(src)
    E1, E2, dE_21, dE_31 = out[0], out[1], out[2], out[3]
    assert abs(E1 - (-13.6)) < 1e-10
    assert abs(E2 - (-3.4)) < 1e-10
    assert abs(dE_21 - 10.2) < 1e-10  # 莱曼系 α 线
    assert abs(dE_31 - 12.09) < 0.01  # 莱曼系 β 线
    print(f"  ✓ E1={E1}eV, E2={E2}eV, ΔE(2→1)={dE_21}eV (莱曼α), ΔE(3→1)={dE_31:.2f}eV (莱曼β)")


def test_matha_scenario_uncertainty():
    """综合场景：不确定性原理应用。"""
    print("\n--- 综合场景：不确定性原理 ---")
    src = """
#：{
  dx = 0.0000000001
  dp = 不确定_动量不确定度(dx)
  ok = 不确定_验证(dx)(dp)
  [dp]
  [ok]
}
"""
    out = _call(src)
    dp, ok = out[0], out[1]
    expected_dp = HBAR / (2 * 1e-10)
    assert abs(dp - expected_dp) < 1e-40
    assert ok == True
    print(f"  ✓ Δx=1Å → Δp≥{dp:.4e}kg·m/s, 验证通过")


def test_matha_scenario_tunneling():
    """综合场景：量子隧穿。"""
    print("\n--- 综合场景：量子隧穿 ---")
    src = """
#：{
  m = me_电子质量
  V0 = 0.000000000000000002
  E = 0.000000000000000001
  a = 0.0000000001
  kappa = 隧穿_衰减常数(m)(V0)(E)
  T = 隧穿_WKB概率(kappa)(a)
  [kappa]
  [T]
}
"""
    out = _call(src)
    kappa, T = out[0], out[1]
    expected_kappa = math.sqrt(2 * M_ELECTRON * 1e-18) / HBAR
    assert abs(kappa - expected_kappa) < 1e-5
    expected_T = math.exp(-2 * expected_kappa * 1e-10)
    assert abs(T - expected_T) < 1e-15
    print(f"  ✓ κ={kappa:.4e}/m, T={T:.6e}")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_quantum_registered_in_interp,
        test_quantum_registered_in_semantic,
        test_de_broglie_wavelength,
        test_probability_density,
        test_free_particle_energy,
        test_momentum_wavenumber,
        test_energy_frequency_relation,
        test_kinetic_energy_expectation,
        test_position_momentum_uncertainty,
        test_energy_time_uncertainty,
        test_uncertainty_limit,
        test_uncertainty_verification,
        test_orbital_angular_momentum,
        test_spin_angular_momentum,
        test_total_angular_momentum,
        test_magnetic_moment,
        test_landé_g_factor,
        test_infinite_well,
        test_hydrogen_energy_levels,
        test_harmonic_oscillator,
        test_oscillator_length,
        test_hydrogen_radius,
        test_ionization_energy,
        test_decay_constant,
        test_wkb_tunneling,
        test_rectangular_barrier,
        test_photoelectric_effect,
        test_compton_wavelength,
        test_compton_shift,
        test_quantum_constants,
        test_matha_scenario_electron_diffraction,
        test_matha_scenario_hydrogen_spectrum,
        test_matha_scenario_uncertainty,
        test_matha_scenario_tunneling,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个量子力学测试全部通过 ✓✓✓")
