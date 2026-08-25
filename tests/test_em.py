"""Matha 电磁学测试：静电学 + 直流电路 + 磁场 + 电磁感应 + 交流电路。

覆盖：
  1) 静电学：库仑力、电场、电势、电容、储能、高斯通量
  2) 直流电路：欧姆定律、串/并联电阻、功率、焦耳热
  3) 磁场：洛伦兹力、安培力、导线/线圈/螺线管磁场、磁通量、回旋半径/频率
  4) 电磁感应：法拉第定律、动生电动势、自感、磁场能量、互感
  5) 交流电路：感抗/容抗/阻抗、谐振频率、有效值/峰值、功率因数、品质因数
  6) 电阻率/介电常数数据库
  7) Matha 侧综合场景

运行：python -m tests.test_em
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.em import (
    _em_symtab_names, EPSILON_0, K_ELECTROSTATIC, MU_0, ELEMENTARY_CHARGE,
    RESISTIVITIES, DIELECTRIC_CONSTANTS,
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

def test_em_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _em_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个电磁学内建名全部注册")


def test_em_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[电_库仑力(1e-6)(2e-6)(0.1) + 电路_电压(2)(10)]"
    ok = _semantic_ok(src)
    assert ok, "引用电磁学内建触发语义错误"
    print("  ✓ 电磁学内建在语义侧可直接引用")


# ============================================================
# 1. 静电学
# ============================================================

def test_coulomb_law():
    print("\n--- 库仑定律 ---")
    i = _interp()
    # F = kq1q2/r²: q1=1μC, q2=2μC, r=0.1m
    F = i.call("电_库仑力", 1e-6, 2e-6, 0.1)
    expected = K_ELECTROSTATIC * 1e-6 * 2e-6 / 0.01
    assert abs(F - expected) < 1e-3
    print(f"  ✓ F={F:.4f}N")


def test_electric_field_potential():
    print("\n--- 电场与电势 ---")
    i = _interp()
    Q, r = 1e-6, 0.5
    E = i.call("电_电场", Q, r)
    V = i.call("电_电势", Q, r)
    assert abs(E - K_ELECTROSTATIC * Q / r ** 2) < 1e-3
    assert abs(V - K_ELECTROSTATIC * Q / r) < 1e-3
    print(f"  ✓ E={E:.2f}N/C, V={V:.2f}V")


def test_capacitor():
    print("\n--- 平行板电容器 ---")
    i = _interp()
    # C = ε₀S/d: S=0.01m², d=0.001m → C=8.854e-11 F
    C = i.call("电_平行板电容", 0.01, 0.001)
    expected = EPSILON_0 * 0.01 / 0.001
    assert abs(C - expected) < 1e-15
    # 储能 W = ½CV²: V=12V
    W = i.call("电_电容储能", C, 12)
    assert abs(W - 0.5 * C * 144) < 1e-15
    # 电荷 Q = CV
    Q_cap = i.call("电_电容电荷", C, 12)
    assert abs(Q_cap - C * 12) < 1e-15
    print(f"  ✓ C={C:.4e}F, W={W:.4e}J, Q={Q_cap:.4e}C")


def test_gauss_flux():
    print("\n--- 高斯定律电通量 ---")
    i = _interp()
    # Φ = Q/ε₀: Q=1μC
    Phi = i.call("电_高斯通量", 1e-6)
    expected = 1e-6 / EPSILON_0
    assert abs(Phi - expected) < 1e3
    print(f"  ✓ Φ={Phi:.2e}V·m")


def test_electric_dipole():
    print("\n--- 电偶极矩 ---")
    i = _interp()
    # p = qd: q=1e-6, d=0.01 → p=1e-8
    p = i.call("电_电偶极矩", 1e-6, 0.01)
    assert abs(p - 1e-8) < 1e-20
    print(f"  ✓ p={p:.2e}C·m")


# ============================================================
# 2. 直流电路
# ============================================================

def test_ohms_law():
    print("\n--- 欧姆定律 ---")
    i = _interp()
    assert i.call("电路_电压", 2, 10) == 20.0     # V=IR
    assert i.call("电路_电流", 20, 10) == 2.0     # I=V/R
    assert i.call("电路_电阻", 20, 2) == 10.0     # R=V/I
    print("  ✓ V=IR / I=V/R / R=V/I 三算正确")


def test_series_parallel_resistance():
    print("\n--- 串/并联电阻 ---")
    i = _interp()
    # 串联: 10+20+30=60
    R_s = i.call("电路_串联电阻", [10, 20, 30])
    assert R_s == 60.0
    # 并联: 1/(1/10+1/20+1/30) = 60/11
    R_p = i.call("电路_并联电阻", [10, 20, 30])
    expected = 1 / (1/10 + 1/20 + 1/30)
    assert abs(R_p - expected) < 1e-10
    # 两并联: 10∥10 = 5
    R_p2 = i.call("电路_并联电阻", [10, 10])
    assert abs(R_p2 - 5) < 1e-10
    print(f"  ✓ 串联={R_s}Ω, 并联={R_p:.4f}Ω")


def test_power_and_joule_heat():
    print("\n--- 电功率与焦耳热 ---")
    i = _interp()
    # P=VI: V=10, I=2 → 20W
    assert i.call("电路_功率", 10, 2) == 20.0
    # P=I²R: I=2, R=5 → 20W
    assert i.call("电路_功率热", 2, 5) == 20.0
    # P=V²/R: V=10, R=5 → 20W
    assert i.call("电路_功率压", 10, 5) == 20.0
    # 焦耳热: I=2, R=5, t=10 → 200J
    assert i.call("电路_焦耳热", 2, 5, 10) == 200.0
    print("  ✓ P=VI=I²R=V²/R=20W, Q=200J")


# ============================================================
# 3. 磁场
# ============================================================

def test_lorentz_force():
    print("\n--- 洛伦兹力 ---")
    i = _interp()
    # F = qvB sinθ: q=1.6e-19, v=1e6, B=0.1, θ=90°
    F = i.call("磁_洛伦兹力", 1.6e-19, 1e6, 0.1, math.pi / 2)
    expected = 1.6e-19 * 1e6 * 0.1 * math.sin(math.pi / 2)
    assert abs(F - expected) < 1e-25
    print(f"  ✓ F={F:.2e}N")


def test_ampere_force():
    print("\n--- 安培力 ---")
    i = _interp()
    # F = BIL sinθ: B=0.5, I=10, L=0.2, θ=90°
    F = i.call("磁_安培力", 0.5, 10, 0.2, math.pi / 2)
    expected = 0.5 * 10 * 0.2 * math.sin(math.pi / 2)
    assert abs(F - expected) < 1e-10
    print(f"  ✓ F={F}N")


def test_magnetic_fields():
    print("\n--- 导线/线圈/螺线管磁场 ---")
    i = _interp()
    # 长直导线: B = μ₀I/(2πr): I=10, r=0.1
    B1 = i.call("磁_直导线磁场", 10, 0.1)
    expected1 = MU_0 * 10 / (2 * math.pi * 0.1)
    assert abs(B1 - expected1) < 1e-15
    # 圆线圈中心: B = μ₀I/(2R): I=5, R=0.1
    B2 = i.call("磁_圆线圈中心磁场", 5, 0.1)
    expected2 = MU_0 * 5 / (2 * 0.1)
    assert abs(B2 - expected2) < 1e-15
    # 螺线管: B = μ₀nI: n=1000, I=2
    B3 = i.call("磁_螺线管磁场", 1000, 2)
    expected3 = MU_0 * 1000 * 2
    assert abs(B3 - expected3) < 1e-15
    print(f"  ✓ 导线B={B1:.2e}T, 线圈B={B2:.2e}T, 螺线管B={B3:.4f}T")


def test_magnetic_flux():
    print("\n--- 磁通量 ---")
    i = _interp()
    # Φ = BA cosθ: B=0.5, A=0.02, θ=0° → 0.01 Wb
    Phi = i.call("磁_磁通量", 0.5, 0.02, 0)
    assert abs(Phi - 0.01) < 1e-12
    # θ=60° → 0.005 Wb
    Phi2 = i.call("磁_磁通量", 0.5, 0.02, math.pi / 3)
    assert abs(Phi2 - 0.5 * 0.02 * 0.5) < 1e-12
    print(f"  ✓ θ=0°: Φ={Phi}Wb, θ=60°: Φ={Phi2}Wb")


def test_cyclotron():
    print("\n--- 回旋半径与频率 ---")
    i = _interp()
    # r = mv/(qB): m=9.11e-31, v=1e7, q=1.6e-19, B=0.1
    r = i.call("磁_回旋半径", 9.11e-31, 1e7, 1.6e-19, 0.1)
    expected_r = 9.11e-31 * 1e7 / (1.6e-19 * 0.1)
    assert abs(r - expected_r) < 1e-15
    # f = qB/(2πm)
    f = i.call("磁_回旋频率", 1.6e-19, 0.1, 9.11e-31)
    expected_f = 1.6e-19 * 0.1 / (2 * math.pi * 9.11e-31)
    assert abs(f - expected_f) < 1e3
    print(f"  ✓ 电子在0.1T: r={r:.4e}m, f={f:.2e}Hz")


# ============================================================
# 4. 电磁感应
# ============================================================

def test_faraday_law():
    print("\n--- 法拉第电磁感应定律 ---")
    i = _interp()
    # ε = N·dΦ/dt: N=100, dΦ=0.01, dt=0.1 → 10V
    eps = i.call("感应_法拉第电动势", 100, 0.01, 0.1)
    assert abs(eps - 10.0) < 1e-10
    print(f"  ✓ ε={eps}V")


def test_motional_emf():
    print("\n--- 动生电动势 ---")
    i = _interp()
    # ε = BLv: B=0.5, L=0.2, v=3
    eps = i.call("感应_动生电动势", 0.5, 0.2, 3)
    assert abs(eps - 0.3) < 1e-10
    print(f"  ✓ ε={eps}V")


def test_self_inductance():
    print("\n--- 自感电动势 ---")
    i = _interp()
    # ε = L·dI/dt: L=0.1, dI=5, dt=0.01
    eps = i.call("感应_自感电动势", 0.1, 5, 0.01)
    assert abs(eps - 50.0) < 1e-10
    print(f"  ✓ ε={eps}V")


def test_magnetic_energy():
    print("\n--- 磁场能量 ---")
    i = _interp()
    # W = ½LI²: L=0.1, I=2 → 0.2J
    W = i.call("感应_磁场能量", 0.1, 2)
    assert abs(W - 0.2) < 1e-10
    print(f"  ✓ W={W}J")


def test_mutual_inductance():
    print("\n--- 互感 ---")
    i = _interp()
    # M = N₂Φ₂₁/I₁: N2=200, Φ21=0.005, I1=1
    M = i.call("感应_互感", 200, 0.005, 1)
    assert abs(M - 1.0) < 1e-10
    print(f"  ✓ M={M}H")


def test_rl_time_constant():
    print("\n--- RL时间常数 ---")
    i = _interp()
    # τ = L/R: L=0.1, R=10 → 0.01s
    tau = i.call("感应_RL时间常数", 0.1, 10)
    assert abs(tau - 0.01) < 1e-12
    print(f"  ✓ τ={tau}s")


# ============================================================
# 5. 交流电路
# ============================================================

def test_reactance():
    print("\n--- 感抗与容抗 ---")
    i = _interp()
    # X_L = 2πfL: f=50, L=0.1 → 31.416Ω
    XL = i.call("交流_感抗", 50, 0.1)
    expected_XL = 2 * math.pi * 50 * 0.1
    assert abs(XL - expected_XL) < 1e-10
    # X_C = 1/(2πfC): f=50, C=100e-6 → 31.831Ω
    XC = i.call("交流_容抗", 50, 100e-6)
    expected_XC = 1 / (2 * math.pi * 50 * 100e-6)
    assert abs(XC - expected_XC) < 1e-10
    print(f"  ✓ X_L={XL:.4f}Ω, X_C={XC:.4f}Ω")


def test_impedance():
    print("\n--- 阻抗 ---")
    i = _interp()
    # Z = √(R² + (XL-XC)²): R=100, XL=50, XC=30 → √(10000+400)=√10400
    Z = i.call("交流_阻抗", 100, 50, 30)
    expected = math.sqrt(10000 + 400)
    assert abs(Z - expected) < 1e-10
    print(f"  ✓ Z={Z:.4f}Ω")


def test_resonant_frequency():
    print("\n--- 谐振频率 ---")
    i = _interp()
    # f₀ = 1/(2π√(LC)): L=0.1, C=100e-6 → 1/(2π√(1e-5))
    f0 = i.call("交流_谐振频率", 0.1, 100e-6)
    expected = 1 / (2 * math.pi * math.sqrt(0.1 * 100e-6))
    assert abs(f0 - expected) < 1e-10
    print(f"  ✓ f₀={f0:.2f}Hz")


def test_rms_and_peak():
    print("\n--- 有效值与峰值 ---")
    i = _interp()
    # Vrms = Vmax/√2: Vmax=311.13 → Vrms=220
    Vrms = i.call("交流_有效值", 311.13)
    assert abs(Vrms - 311.13 / math.sqrt(2)) < 1e-6
    # Vmax = Vrms×√2: Vrms=220 → Vmax=311.13
    Vmax = i.call("交流_峰值", 220)
    assert abs(Vmax - 220 * math.sqrt(2)) < 1e-6
    print(f"  ✓ 311.13V→{Vrms:.2f}V(rms), 220V→{Vmax:.2f}V(max)")


def test_power_factor_and_ac_power():
    print("\n--- 功率因数与交流功率 ---")
    i = _interp()
    # cosφ = R/Z: R=80, Z=100 → 0.8
    cos_phi = i.call("交流_功率因数", 80, 100)
    assert abs(cos_phi - 0.8) < 1e-10
    # P = VI cosφ: V=220, I=5, cosφ=0.8 → 880W
    P = i.call("交流_有功功率", 220, 5, 0.8)
    assert abs(P - 880) < 1e-10
    # S = VI: 220×5=1100VA
    S = i.call("交流_视在功率", 220, 5)
    assert abs(S - 1100) < 1e-10
    # Q = VI sinφ: sinφ=0.6 → 220×5×0.6=660var
    Q_var = i.call("交流_无功功率", 220, 5, 0.8)
    assert abs(Q_var - 660) < 1e-6
    print(f"  ✓ cosφ={cos_phi}, P={P}W, S={S}VA, Q={Q_var:.1f}var")


def test_quality_factor():
    print("\n--- 品质因数 ---")
    i = _interp()
    # Q = (1/R)√(L/C): R=10, L=0.1, C=100e-6 → (1/10)√(1000)
    Q_val = i.call("交流_品质因数", 10, 0.1, 100e-6)
    expected = (1 / 10) * math.sqrt(0.1 / 100e-6)
    assert abs(Q_val - expected) < 1e-10
    print(f"  ✓ Q={Q_val:.4f}")


# ============================================================
# 6. 电阻率/介电常数数据库
# ============================================================

def test_em_database():
    print("\n--- 电阻率/介电常数数据库 ---")
    i = _interp()
    for name, val in RESISTIVITIES.items():
        key = f"电阻率_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in DIELECTRIC_CONSTANTS.items():
        key = f"介电常数_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    # 物理常量
    assert i.builtins["ε0_真空介电常数"] == EPSILON_0
    assert i.builtins["k_静电力常量"] == K_ELECTROSTATIC
    assert i.builtins["μ0_真空磁导率"] == MU_0
    assert i.builtins["e_基本电荷"] == ELEMENTARY_CHARGE
    total = len(RESISTIVITIES) + len(DIELECTRIC_CONSTANTS) + 4
    print(f"  ✓ {len(RESISTIVITIES)} 电阻率 + {len(DIELECTRIC_CONSTANTS)} 介电常数 + 4 物理常量 = {total} 常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_circuit():
    """综合场景：家用电路功率 + 焦耳热。"""
    print("\n--- 综合场景：家用电路 ---")
    src = """
#：{
  V = 220
  P_rated = 1100
  I = 电路_电流(V)(44)
  R = 电路_电阻(V)(I)
  P = 电路_功率(V)(I)
  Q_10s = 电路_焦耳热(I)(R)(10)
  [I]
  [P]
  [Q_10s]
}
"""
    out = _call(src)
    I, P, Q_10s = out[0], out[1], out[2]
    assert abs(I - 5.0) < 1e-10
    assert abs(P - 1100) < 1e-6
    assert abs(Q_10s - 11000) < 1e-6
    print(f"  ✓ 220V/44Ω → I={I}A, P={P}W, 10s焦耳热={Q_10s}J")


def test_matha_scenario_transformer():
    """综合场景：电磁感应（法拉第定律）变压器。"""
    print("\n--- 综合场景：法拉第电磁感应 ---")
    src = """
#：{
  N = 200
  dPhi = 0.02
  dt = 0.01
  eps = 感应_法拉第电动势(N)(dPhi)(dt)
  [eps]
}
"""
    out = _call(src)
    eps = out[0]
    assert abs(eps - 400.0) < 1e-6
    print(f"  ✓ N=200, dΦ=0.02Wb, dt=0.01s → ε={eps}V")


def test_matha_scenario_rlc_resonance():
    """综合场景：RLC 串联谐振电路。"""
    print("\n--- 综合场景：RLC 谐振 ---")
    src = """
#：{
  L = 0.1
  C = 0.000001
  R = 50
  f0 = 交流_谐振频率(L)(C)
  Q_factor = 交流_品质因数(R)(L)(C)
  [f0]
  [Q_factor]
}
"""
    out = _call(src)
    f0, Q_factor = out[0], out[1]
    expected_f0 = 1 / (2 * math.pi * math.sqrt(0.1 * 1e-6))
    expected_Q = (1 / 50) * math.sqrt(0.1 / 1e-6)
    assert abs(f0 - expected_f0) < 1e-6
    assert abs(Q_factor - expected_Q) < 1e-6
    print(f"  ✓ L=0.1H, C=1μF, R=50Ω → f₀={f0:.2f}Hz, Q={Q_factor:.2f}")


def test_matha_scenario_wire_resistance():
    """综合场景：铜导线电阻计算（电阻率应用）。"""
    print("\n--- 综合场景：铜导线电阻 ---")
    src = """
#：{
  rho = 电阻率_铜
  L_wire = 100
  S = 0.000001
  R = rho * L_wire / S
  [R]
}
"""
    out = _call(src)
    R = out[0]
    rho_cu = 1.68e-8
    expected = rho_cu * 100 / 1e-6
    assert abs(R - expected) < 1e-6
    print(f"  ✓ 100m铜线 S=1mm² → R={R:.4f}Ω")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_em_registered_in_interp,
        test_em_registered_in_semantic,
        test_coulomb_law,
        test_electric_field_potential,
        test_capacitor,
        test_gauss_flux,
        test_electric_dipole,
        test_ohms_law,
        test_series_parallel_resistance,
        test_power_and_joule_heat,
        test_lorentz_force,
        test_ampere_force,
        test_magnetic_fields,
        test_magnetic_flux,
        test_cyclotron,
        test_faraday_law,
        test_motional_emf,
        test_self_inductance,
        test_magnetic_energy,
        test_mutual_inductance,
        test_rl_time_constant,
        test_reactance,
        test_impedance,
        test_resonant_frequency,
        test_rms_and_peak,
        test_power_factor_and_ac_power,
        test_quality_factor,
        test_em_database,
        test_matha_scenario_circuit,
        test_matha_scenario_transformer,
        test_matha_scenario_rlc_resonance,
        test_matha_scenario_wire_resistance,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个电磁学测试全部通过 ✓✓✓")
