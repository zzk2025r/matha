"""Matha 核物理测试：核结合能 + 放射性衰变 + 核反应 + 粒子物理 + 核能反应堆。

覆盖：
  1) 核结合能：质量亏损、结合能、比结合能、Weizsäcker半经验公式、α/β衰变Q值
  2) 放射性衰变：衰变定律、半衰期、活度、碳14测年、单位转换
  3) 核反应：Q值、阈能、裂变/聚变能量、裂变功率
  4) 粒子物理：洛伦兹因子、相对论能量/动量/动能、质能等价
  5) 核能与反应堆：增殖系数、反应性、慢化、辐射剂量、屏蔽
  6) 物理常量
  7) Matha 侧综合场景

运行：python -m tests.test_nuclear
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.nuclear import (
    _nuclear_symtab_names, C_LIGHT, M_PROTON, M_NEUTRON, M_ELECTRON,
    U_ATOMIC, E_CHARGE, MEV_TO_J, U_TO_MEV, H_PLANCK,
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

def test_nuclear_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _nuclear_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个核物理内建名全部注册")


def test_nuclear_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[核_结合能MeV(1e-29) + 衰变_半衰期(0.01)]"
    ok = _semantic_ok(src)
    assert ok, "引用核物理内建触发语义错误"
    print("  ✓ 核物理内建在语义侧可直接引用")


# ============================================================
# 1. 核结合能与质量亏损
# ============================================================

def test_mass_defect_and_binding_energy():
    print("\n--- 质量亏损与结合能 ---")
    i = _interp()
    # 氦-4核: Z=2, N=2, M=6.6447e-27 kg
    Z, N, M_He = 2, 2, 6.6447e-27
    dm = i.call("核_质量亏损", Z, N, M_He)
    expected_dm = Z * M_PROTON + N * M_NEUTRON - M_He
    assert abs(dm - expected_dm) < 1e-40
    # 结合能 (Joule)
    B_J = i.call("核_结合能J", dm)
    assert abs(B_J - dm * C_LIGHT ** 2) < 1e-40
    # 结合能 (MeV)
    B_MeV = i.call("核_结合能MeV", dm)
    expected_MeV = dm * C_LIGHT ** 2 / MEV_TO_J
    assert abs(B_MeV - expected_MeV) < 1e-10
    print(f"  ✓ He-4: Δm={dm:.4e}kg, B={B_MeV:.2f}MeV")


def test_specific_binding_energy():
    print("\n--- 比结合能 ---")
    i = _interp()
    # He-4: B/A ≈ 7.07 MeV/核子
    dm = 2 * M_PROTON + 2 * M_NEUTRON - 6.6447e-27
    BA = i.call("核_比结合能", dm, 4)
    expected = dm * C_LIGHT ** 2 / (MEV_TO_J * 4)
    assert abs(BA - expected) < 1e-10
    print(f"  ✓ He-4: B/A={BA:.2f}MeV/核子")


def test_binding_energy_from_u():
    print("\n--- 由原子质量单位求结合能 ---")
    i = _interp()
    # Δm = 0.0304 u → B = 0.0304 × 931.494 MeV
    B = i.call("核_结合能由U", 0.0304)
    expected = 0.0304 * U_TO_MEV
    assert abs(B - expected) < 1e-6
    print(f"  ✓ Δm=0.0304u → B={B:.2f}MeV")


def test_semiempirical_mass_formula():
    print("\n--- Weizsäcker 半经验质量公式 ---")
    i = _interp()
    # Fe-56: A=56, Z=26 → B/A ≈ 8.79 MeV（实验值约8.49）
    B = i.call("核_半经验结合能", 56, 26)
    BA = i.call("核_半经验比结合能", 56, 26)
    assert B > 400  # Fe-56 结合能约 490 MeV
    assert BA > 8.0  # B/A > 8
    print(f"  ✓ Fe-56: B={B:.1f}MeV, B/A={BA:.2f}MeV/核子")


def test_alpha_beta_decay_Q():
    print("\n--- α/β 衰变 Q 值 ---")
    i = _interp()
    # α衰变: M_parent=238u, M_daughter=234u, M_alpha=4u → Q=(238-234-4)×931.494
    # 用简化质量测试
    Q_alpha = i.call("核_α衰变Q", 238 * U_ATOMIC, 234 * U_ATOMIC, 4 * U_ATOMIC)
    # 实际有质量亏损，这里用原子质量单位整数近似 → Q≈0（需要精确质量才有意义）
    # 用真实值测试: U-238 → Th-234 + α
    # M(U-238)=238.0508u, M(Th-234)=234.0436u, M(α)=4.0026u
    Q_alpha_real = i.call("核_α衰变Q", 238.0508 * U_ATOMIC, 234.0436 * U_ATOMIC, 4.0026 * U_ATOMIC)
    expected_Q = (238.0508 - 234.0436 - 4.0026) * U_TO_MEV
    assert abs(Q_alpha_real - expected_Q) < 0.1
    # β衰变: Q = (M_parent - M_daughter)·c²
    Q_beta = i.call("核_β衰变Q", 14.003241 * U_ATOMIC, 14.003074 * U_ATOMIC)
    expected_Qb = (14.003241 - 14.003074) * U_TO_MEV
    assert abs(Q_beta - expected_Qb) < 0.01
    print(f"  ✓ α衰变U-238: Q={Q_alpha_real:.2f}MeV, β衰变C-14: Q={Q_beta:.4f}MeV")


# ============================================================
# 2. 放射性衰变
# ============================================================

def test_decay_law():
    print("\n--- 衰变定律 ---")
    i = _interp()
    # N0=1e6, λ=0.01/s, t=100s → N=1e6·e^(-1)
    N = i.call("衰变_剩余核数", 1e6, 0.01, 100)
    expected = 1e6 * math.exp(-1)
    assert abs(N - expected) < 1
    print(f"  ✓ N={N:.0f} (N0=1e6, λ=0.01, t=100s)")


def test_half_life():
    print("\n--- 半衰期与衰变常数 ---")
    i = _interp()
    # λ=0.01 → T½ = ln2/0.01 = 69.31s
    T_half = i.call("衰变_半衰期", 0.01)
    expected = math.log(2) / 0.01
    assert abs(T_half - expected) < 1e-10
    # 反算
    lam = i.call("衰变_衰变常数", T_half)
    assert abs(lam - 0.01) < 1e-12
    print(f"  ✓ T½={T_half:.2f}s, 反算 λ={lam:.6f}/s")


def test_mean_life():
    print("\n--- 平均寿命 ---")
    i = _interp()
    tau = i.call("衰变_平均寿命", 0.01)
    expected = 100.0
    assert abs(tau - expected) < 1e-10
    print(f"  ✓ τ={tau:.2f}s")


def test_activity():
    print("\n--- 放射性活度 ---")
    i = _interp()
    A = i.call("衰变_活度", 0.01, 1e6)
    expected = 0.01 * 1e6
    assert abs(A - expected) < 1
    print(f"  ✓ A={A:.0f}Bq")


def test_decayed_count():
    print("\n--- 已衰变核数 ---")
    i = _interp()
    N_dec = i.call("衰变_已衰变数", 1e6, 0.01, 100)
    expected = 1e6 * (1 - math.exp(-1))
    assert abs(N_dec - expected) < 1
    print(f"  ✓ N_decayed={N_dec:.0f}")


def test_carbon14_dating():
    print("\n--- 碳-14年代测定 ---")
    i = _interp()
    # N0/N = 2 → t = T½ = 5730年
    t = i.call("衰变_碳14测年", 2.0, 1.0)
    assert abs(t - 5730) < 1
    # N0/N = 4 → t = 2·T½ = 11460年
    t2 = i.call("衰变_碳14测年", 4.0, 1.0)
    assert abs(t2 - 11460) < 2
    print(f"  ✓ N0/N=2 → t={t:.0f}年, N0/N=4 → t={t2:.0f}年")


def test_activity_units():
    print("\n--- 活度单位转换 ---")
    i = _interp()
    # 1 Ci = 3.7e10 Bq
    Bq = i.call("衰变_Ci转Bq", 1.0)
    assert abs(Bq - 3.7e10) < 1
    Ci = i.call("衰变_Bq转Ci", 3.7e10)
    assert abs(Ci - 1.0) < 1e-15
    print(f"  ✓ 1Ci={Bq:.2e}Bq, 3.7e10Bq={Ci}Ci")


# ============================================================
# 3. 核反应
# ============================================================

def test_Q_value():
    print("\n--- 核反应 Q 值 ---")
    i = _interp()
    # D+T → He-4 + n: Q = (m_D + m_T - m_He - m_n)·c²
    # m_D=2.0141u, m_T=3.0160u, m_He=4.0026u, m_n=1.0087u
    Q = i.call("反应_Q值U", 2.0141 + 3.0160, 4.0026 + 1.0087)
    expected = (5.0301 - 5.0113) * U_TO_MEV
    assert abs(Q - expected) < 0.1
    print(f"  ✓ D-T聚变: Q={Q:.2f}MeV")


def test_threshold_energy():
    print("\n--- 反应阈能 ---")
    i = _interp()
    # 吸热反应 Q=-5MeV, ma=1, mA=14 → E_th = 5*(1+1/14)
    E_th = i.call("反应_阈能", -5.0, 1, 14)
    expected = 5.0 * (1 + 1.0 / 14)
    assert abs(E_th - expected) < 1e-10
    # 放热反应 Q>0 → E_th=0
    E_th_exo = i.call("反应_阈能", 5.0, 1, 14)
    assert E_th_exo == 0.0
    print(f"  ✓ Q=-5MeV: E_th={E_th:.4f}MeV, Q=+5MeV: E_th=0")


def test_fission_energy():
    print("\n--- 裂变能量释放 ---")
    i = _interp()
    # 1次U-235裂变 ≈ 200 MeV
    E = i.call("反应_裂变能", 1, 200.0)
    assert abs(E - 200.0) < 1e-10
    # 1摩尔裂变
    E_mol = i.call("反应_裂变能", 6.022e23, 200.0)
    # 1摩尔 × 200 MeV × 1.602e-13 J/MeV
    E_mol_J = E_mol * MEV_TO_J
    expected_J = 6.022e23 * 200 * MEV_TO_J
    assert abs(E_mol_J - expected_J) < 1e5
    print(f"  ✓ 1摩尔U-235裂变: E={E_mol_J/1e12:.2f}TJ")


def test_fusion_energy():
    print("\n--- 聚变能量释放 ---")
    i = _interp()
    # 1次D-T聚变 ≈ 17.6 MeV
    E = i.call("反应_聚变能", 1, 17.6)
    assert abs(E - 17.6) < 1e-10
    print(f"  ✓ 1次D-T聚变: E={E}MeV")


def test_fission_power():
    print("\n--- 裂变功率 ---")
    i = _interp()
    # 3.12e16 裂变/秒 → 1GW
    rate = 1e9 / (200 * MEV_TO_J)  # 1GW所需的裂变率
    P = i.call("反应_裂变功率", rate, 200.0)
    assert abs(P - 1e9) < 1e3
    print(f"  ✓ 裂变率={rate:.2e}/s → P={P/1e9:.2f}GW")


# ============================================================
# 4. 粒子物理
# ============================================================

def test_lorentz_factor():
    print("\n--- 洛伦兹因子 ---")
    i = _interp()
    # v=0.6c → γ=1.25
    gamma = i.call("粒子_洛伦兹因子", 0.6 * C_LIGHT)
    expected = 1.0 / math.sqrt(1 - 0.36)
    assert abs(gamma - expected) < 1e-15
    print(f"  ✓ v=0.6c → γ={gamma:.4f}")


def test_relativistic_energy():
    print("\n--- 相对论总能量与动能 ---")
    i = _interp()
    m = M_ELECTRON
    v = 0.8 * C_LIGHT
    E_total = i.call("粒子_相对论总能量", m, v)
    gamma = 1.0 / math.sqrt(1 - 0.64)
    expected_E = gamma * m * C_LIGHT ** 2
    assert abs(E_total - expected_E) < 1e-20
    K = i.call("粒子_相对论动能", m, v)
    expected_K = (gamma - 1) * m * C_LIGHT ** 2
    assert abs(K - expected_K) < 1e-20
    print(f"  ✓ v=0.8c: E={E_total:.4e}J, K={K:.4e}J")


def test_relativistic_momentum():
    print("\n--- 相对论动量 ---")
    i = _interp()
    m = M_ELECTRON
    v = 0.6 * C_LIGHT
    p = i.call("粒子_相对论动量", m, v)
    gamma = 1.0 / math.sqrt(1 - 0.36)
    expected_p = gamma * m * v
    assert abs(p - expected_p) < 1e-30
    print(f"  ✓ v=0.6c: p={p:.4e}kg·m/s")


def test_mass_energy_equivalence():
    print("\n--- 质能等价 ---")
    i = _interp()
    E = i.call("粒子_质能等价", M_ELECTRON)
    expected = M_ELECTRON * C_LIGHT ** 2
    assert abs(E - expected) < 1e-20
    E_MeV = i.call("粒子_质能等价MeV", M_ELECTRON)
    expected_MeV = M_ELECTRON * C_LIGHT ** 2 / MEV_TO_J
    assert abs(E_MeV - expected_MeV) < 1e-6
    # 电子静质量能 ≈ 0.511 MeV
    assert abs(E_MeV - 0.511) < 0.01
    print(f"  ✓ 电子: E={E_MeV:.3f}MeV")


def test_velocity_from_kinetic_energy():
    print("\n--- 由动能求速度 ---")
    i = _interp()
    # 电子 K=0.511MeV → v ≈ 0.866c
    K = 0.511 * MEV_TO_J
    v = i.call("粒子_速度由动能", K, M_ELECTRON)
    ratio = 1 + K / (M_ELECTRON * C_LIGHT ** 2)
    expected_v = C_LIGHT * math.sqrt(1 - 1 / ratio ** 2)
    assert abs(v - expected_v) < 1e-6
    print(f"  ✓ K=0.511MeV → v={v/C_LIGHT:.4f}c")


def test_momentum_from_energy():
    print("\n--- 由总能量求动量 ---")
    i = _interp()
    m = M_ELECTRON
    E_total = 2 * m * C_LIGHT ** 2  # 总能量 = 2倍静能
    p = i.call("粒子_动量由能量", E_total, m)
    expected = math.sqrt(E_total ** 2 - (m * C_LIGHT ** 2) ** 2) / C_LIGHT
    assert abs(p - expected) < 1e-30
    print(f"  ✓ E=2mc² → p={p:.4e}kg·m/s")


# ============================================================
# 5. 核能与反应堆
# ============================================================

def test_effective_multiplication_factor():
    print("\n--- 有效增殖系数 ---")
    i = _interp()
    k_eff = i.call("反应堆_有效增殖系数", 1.2, 100, 0.001)
    expected = 1.2 / (1 + 100 * 0.001)
    assert abs(k_eff - expected) < 1e-15
    print(f"  ✓ k_eff={k_eff:.6f}")


def test_criticality():
    print("\n--- 临界判断 ---")
    i = _interp()
    assert i.call("反应堆_临界判断", 1.0) == True
    assert i.call("反应堆_临界判断", 1.001) == False
    print("  ✓ k_eff=1.0 → 临界, k_eff=1.001 → 非临界")


def test_reactivity():
    print("\n--- 反应性 ---")
    i = _interp()
    rho = i.call("反应堆_反应性", 1.005)
    expected = 0.005 / 1.005
    assert abs(rho - expected) < 1e-15
    print(f"  ✓ k_eff=1.005 → ρ={rho:.6f}")


def test_reactor_period():
    print("\n--- 反应堆周期 ---")
    i = _interp()
    T = i.call("反应堆_周期", 1e-4, 0.005)
    expected = 1e-4 / 0.005
    assert abs(T - expected) < 1e-15
    print(f"  ✓ T={T:.4f}s")


def test_moderation_ratio():
    print("\n--- 中子慢化比 ---")
    i = _interp()
    # 氢 A=1 → ξ=1（完全弹性碰撞）
    xi_H = i.call("反应堆_慢化比", 1)
    assert abs(xi_H - 1.0) < 1e-10
    # 碳 A=12
    xi_C = i.call("反应堆_慢化比", 12)
    expected_C = 1 + ((12 - 1) ** 2 / (2 * 12)) * math.log((12 - 1) / (12 + 1))
    assert abs(xi_C - expected_C) < 1e-15
    print(f"  ✓ H: ξ={xi_H}, C: ξ={xi_C:.4f}")


def test_moderation_collisions():
    print("\n--- 慢化碰撞次数 ---")
    i = _interp()
    # 从2MeV慢化到0.025eV，碳A=12
    n = i.call("反应堆_慢化碰撞数", 2e6, 0.025, 12)
    xi = 1 + (11 ** 2 / 24) * math.log(11 / 13)
    expected = math.log(2e6 / 0.025) / xi
    assert abs(n - expected) < 1e-10
    print(f"  ✓ 2MeV→0.025eV (C): n={n:.1f}次")


def test_radiation_dose():
    print("\n--- 辐射剂量 ---")
    i = _interp()
    D = i.call("反应堆_吸收剂量", 1.0, 1.0)  # 1J/1kg = 1Gy
    assert abs(D - 1.0) < 1e-15
    H = i.call("反应堆_当量剂量", 0.01, 20)  # 0.01Gy × 20(α) = 0.2Sv
    assert abs(H - 0.2) < 1e-15
    print(f"  ✓ D={D}Gy, H={H}Sv (α辐射)")


def test_shielding():
    print("\n--- 辐射屏蔽 ---")
    i = _interp()
    # 半减弱层
    HVL = i.call("反应堆_半减弱层", 0.1)
    expected_HVL = math.log(2) / 0.1
    assert abs(HVL - expected_HVL) < 1e-15
    # 屏蔽后强度
    I = i.call("反应堆_屏蔽强度", 1000, 0.1, 6.93)  # ≈ 10个HVL
    expected_I = 1000 * math.exp(-0.1 * 6.93)
    assert abs(I - expected_I) < 1e-10
    print(f"  ✓ HVL={HVL:.4f}m, I={I:.2f} (10个HVL后)")


# ============================================================
# 6. 物理常量
# ============================================================

def test_nuclear_constants():
    print("\n--- 物理常量 ---")
    i = _interp()
    assert i.builtins["mp_质子质量"] == M_PROTON
    assert i.builtins["mn_中子质量"] == M_NEUTRON
    assert i.builtins["me_电子质量"] == M_ELECTRON
    assert i.builtins["u_原子质量单位"] == U_ATOMIC
    assert i.builtins["eV_电子伏特"] == E_CHARGE
    assert i.builtins["MeV_兆电子伏特"] == MEV_TO_J
    assert i.builtins["u_MeV换算"] == U_TO_MEV
    print("  ✓ 7 个核物理常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_binding_energy():
    """综合场景：铁-56结合能分析。"""
    print("\n--- 综合场景：Fe-56 结合能 ---")
    src = """
#：{
  A = 56
  Z = 26
  B = 核_半经验结合能(A)(Z)
  BA = 核_半经验比结合能(A)(Z)
  [B]
  [BA]
}
"""
    out = _call(src)
    B, BA = out
    assert B > 400  # ~490 MeV
    assert BA > 8.0  # ~8.7 MeV/核子
    print(f"  ✓ Fe-56: B={B:.1f}MeV, B/A={BA:.2f}MeV/核子")


def test_matha_scenario_carbon14():
    """综合场景：碳-14考古测年。"""
    print("\n--- 综合场景：碳-14测年 ---")
    src = """
#：{
  N0 = 1000
  N_now = 350
  age = 衰变_碳14测年(N0)(N_now)
  [age]
}
"""
    out = _call(src)
    age = out[0]
    expected = math.log(1000 / 350) / (math.log(2) / 5730)
    assert abs(age - expected) < 1
    print(f"  ✓ N0/N=1000/350 → 年代={age:.0f}年")


def test_matha_scenario_relativistic_particle():
    """综合场景：相对论粒子加速。"""
    print("\n--- 综合场景：相对论粒子 ---")
    src = """
#：{
  m = me_电子质量
  v = 250000000
  gamma = 粒子_洛伦兹因子(v)
  K = 粒子_相对论动能(m)(v)
  p = 粒子_相对论动量(m)(v)
  E_rest = 粒子_质能等价MeV(m)
  [gamma]
  [K]
  [p]
  [E_rest]
}
"""
    out = _call(src)
    gamma, K, p, E_rest = out
    v = 2.5e8
    expected_gamma = 1.0 / math.sqrt(1 - (v / C_LIGHT) ** 2)
    assert abs(gamma - expected_gamma) < 1e-10
    expected_K = (expected_gamma - 1) * M_ELECTRON * C_LIGHT ** 2
    assert abs(K - expected_K) < 1e-15
    assert abs(E_rest - 0.511) < 0.01
    print(f"  ✓ v=2.5e8m/s: γ={gamma:.4f}, K={K/MEV_TO_J:.3f}MeV, E₀={E_rest:.3f}MeV")


def test_matha_scenario_reactor():
    """综合场景：核反应堆功率。"""
    print("\n--- 综合场景：核反应堆 ---")
    src = """
#：{
  rate = 31200000000000000000
  P = 反应_裂变功率(rate)(200)
  [P]
}
"""
    out = _call(src)
    P = out[0]
    assert abs(P - 1e9) < 1e6
    print(f"  ✓ 裂变率=3.12e19/s → P={P/1e9:.2f}GW")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_nuclear_registered_in_interp,
        test_nuclear_registered_in_semantic,
        test_mass_defect_and_binding_energy,
        test_specific_binding_energy,
        test_binding_energy_from_u,
        test_semiempirical_mass_formula,
        test_alpha_beta_decay_Q,
        test_decay_law,
        test_half_life,
        test_mean_life,
        test_activity,
        test_decayed_count,
        test_carbon14_dating,
        test_activity_units,
        test_Q_value,
        test_threshold_energy,
        test_fission_energy,
        test_fusion_energy,
        test_fission_power,
        test_lorentz_factor,
        test_relativistic_energy,
        test_relativistic_momentum,
        test_mass_energy_equivalence,
        test_velocity_from_kinetic_energy,
        test_momentum_from_energy,
        test_effective_multiplication_factor,
        test_criticality,
        test_reactivity,
        test_reactor_period,
        test_moderation_ratio,
        test_moderation_collisions,
        test_radiation_dose,
        test_shielding,
        test_nuclear_constants,
        test_matha_scenario_binding_energy,
        test_matha_scenario_carbon14,
        test_matha_scenario_relativistic_particle,
        test_matha_scenario_reactor,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个核物理测试全部通过 ✓✓✓")
