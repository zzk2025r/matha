"""Matha 统计力学测试：麦克斯韦分布 + 配分函数 + 熵与自由能 + 量子统计 + 涨落关联。

覆盖：
  1) 麦克斯韦-玻尔兹曼分布：最概然/平均/方均根速率、分布函数、理想气体
  2) 配分函数：玻尔兹曼因子、离散/简并/谐振子/转动配分函数、自由能
  3) 熵与自由能：玻尔兹曼熵、吉布斯熵、萨克尔-泰特罗德、熵变、焓、热容
  4) 量子统计：费米-狄拉克/玻色-爱因斯坦分布、费米能级、德拜温度、维恩位移
  5) 涨落与关联：能量/粒子数/温度涨落、布朗运动、爱因斯坦扩散
  6) 物理常量
  7) Matha 侧综合场景

运行：python -m tests.test_statmech
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.statmech import (
    _statmech_symtab_names, K_B, H_PLANCK, HBAR, N_A, R_GAS,
    SIGMA_SB, WIEN_B, M_ELECTRON,
)
from src.domains.nuclear import E_CHARGE


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

def test_statmech_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _statmech_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个统计力学内建名全部注册")


def test_statmech_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[速率_最概然速率(1)(300) + 熵_玻尔兹曼熵(100)]"
    ok = _semantic_ok(src)
    assert ok, "引用统计力学内建触发语义错误"
    print("  ✓ 统计力学内建在语义侧可直接引用")


# ============================================================
# 1. 麦克斯韦-玻尔兹曼分布
# ============================================================

def test_maxwell_speeds():
    print("\n--- 麦克斯韦速率 ---")
    i = _interp()
    m = 4.65e-26  # N2 分子质量
    T = 300
    vp = i.call("速率_最概然速率", m, T)
    v_bar = i.call("速率_平均速率", m, T)
    vrms = i.call("速率_方均根速率", m, T)
    expected_vp = math.sqrt(2 * K_B * T / m)
    expected_vb = math.sqrt(8 * K_B * T / (math.pi * m))
    expected_vr = math.sqrt(3 * K_B * T / m)
    assert abs(vp - expected_vp) < 1e-10
    assert abs(v_bar - expected_vb) < 1e-10
    assert abs(vrms - expected_vr) < 1e-10
    # vp < v_bar < vrms
    assert vp < v_bar < vrms
    print(f"  ✓ N2@300K: vp={vp:.0f}m/s, v̄={v_bar:.0f}m/s, vrms={vrms:.0f}m/s")


def test_maxwell_distribution():
    print("\n--- 麦克斯韦分布函数 ---")
    i = _interp()
    m = 4.65e-26
    T = 300
    # 在最概然速率处，分布函数应有峰值
    vp = math.sqrt(2 * K_B * T / m)
    f_vp = i.call("速率_分布函数", m, T, vp)
    # 分布函数在 v=0 和 v=∞ 时为 0
    f_0 = i.call("速率_分布函数", m, T, 0.0)
    assert f_0 < 1e-30
    assert f_vp > f_0
    print(f"  ✓ f(vp)={f_vp:.4e}, f(0)={f_0:.2e}")


def test_ideal_gas():
    print("\n--- 理想气体 ---")
    i = _interp()
    # P = nkT: n=2.5e25/m³, T=300K
    P = i.call("速率_理想气体压强", 2.5e25, 300)
    expected = 2.5e25 * K_B * 300
    assert abs(P - expected) < 1e-3
    # PV = NkT
    P2 = i.call("速率_理想气体压力", 1e23, 300, 0.001)
    expected2 = 1e23 * K_B * 300 / 0.001
    assert abs(P2 - expected2) < 1e-3
    print(f"  ✓ P={P:.0f}Pa, PV=NkT: P={P2:.0f}Pa")


def test_mean_free_path():
    print("\n--- 平均自由程与碰撞频率 ---")
    i = _interp()
    n = 2.5e25
    sigma = 1e-19  # 碰撞截面
    lam = i.call("速率_平均自由程", n, sigma)
    expected_lam = 1.0 / (math.sqrt(2) * n * sigma)
    assert abs(lam - expected_lam) < 1e-20
    v_bar = 500
    Z = i.call("速率_碰撞频率", n, sigma, v_bar)
    expected_Z = math.sqrt(2) * n * sigma * v_bar
    assert abs(Z - expected_Z) < 1e-15
    print(f"  ✓ λ={lam:.2e}m, Z={Z:.2e}/s")


# ============================================================
# 2. 配分函数
# ============================================================

def test_boltzmann_factor():
    print("\n--- 玻尔兹曼因子 ---")
    i = _interp()
    # 函数期望 E 为焦耳；0.025eV ≈ kT@300K
    E_J = 0.025 * E_CHARGE
    f = i.call("配分_玻尔兹曼因子", E_J, 300)
    expected = math.exp(-E_J / (K_B * 300))
    assert abs(f - expected) < 1e-15
    print(f"  ✓ E=kT → f={f:.6f}")


def test_discrete_partition_function():
    print("\n--- 离散配分函数 ---")
    i = _interp()
    # 两能级: ε1=0, ε2=kT → Z = 1 + e^(-1) = 1.3679
    energies = [0, K_B * 300]
    Z = i.call("配分_离散配分函数", energies, 300)
    expected = 1 + math.exp(-1)
    assert abs(Z - expected) < 1e-10
    print(f"  ✓ Z={Z:.6f}")


def test_degenerate_partition_function():
    print("\n--- 简并配分函数 ---")
    i = _interp()
    # [(0, 1), (kT, 3)] → Z = 1 + 3·e^(-1)
    levels = [(0, 1), (K_B * 300, 3)]
    Z = i.call("配分_简并配分函数", levels, 300)
    expected = 1 + 3 * math.exp(-1)
    assert abs(Z - expected) < 1e-10
    print(f"  ✓ Z={Z:.6f}")


def test_harmonic_oscillator_partition():
    print("\n--- 谐振子配分函数 ---")
    i = _interp()
    omega = 1e14
    T = 300
    Z = i.call("配分_谐振子配分函数", omega, T)
    x = HBAR * omega / (2 * K_B * T)
    expected = 1.0 / (2 * math.sinh(x))
    assert abs(Z - expected) < 1e-20
    print(f"  ✓ Z={Z:.6e}")


def test_rotational_partition():
    print("\n--- 转动配分函数 ---")
    i = _interp()
    I = 1e-46  # 转动惯量
    T = 300
    Z = i.call("配分_转动配分函数", I, T, 1.0)
    theta_rot = HBAR ** 2 / (2 * I * K_B)
    expected = T / theta_rot
    assert abs(Z - expected) < 1e-10
    print(f"  ✓ Z={Z:.2f}")


def test_helmholtz_free_energy():
    print("\n--- 亥姆霍兹自由能 ---")
    i = _interp()
    Z = 2.0
    T = 300
    F = i.call("配分_自由能", Z, T)
    expected = -K_B * T * math.log(Z)
    assert abs(F - expected) < 1e-20
    print(f"  ✓ F={F:.4e}J")


# ============================================================
# 3. 熵与自由能
# ============================================================

def test_boltzmann_entropy():
    print("\n--- 玻尔兹曼熵 ---")
    i = _interp()
    S = i.call("熵_玻尔兹曼熵", 1e6)
    expected = K_B * math.log(1e6)
    assert abs(S - expected) < 1e-30
    print(f"  ✓ W=1e6 → S={S:.4e}J/K")


def test_gibbs_entropy():
    print("\n--- 吉布斯熵 ---")
    i = _interp()
    # 等概率 p=[0.5, 0.5] → S = k·ln2
    S = i.call("熵_吉布斯熵", [0.5, 0.5])
    expected = K_B * math.log(2)
    assert abs(S - expected) < 1e-30
    print(f"  ✓ S={S:.4e}J/K = k·ln2")


def test_isothermal_entropy_change():
    print("\n--- 等温熵变 ---")
    i = _interp()
    dS = i.call("熵_等温熵变", N_A, 0.001, 0.002)  # 1mol, V翻倍
    expected = N_A * K_B * math.log(2)
    assert abs(dS - expected) < 1e-10
    print(f"  ✓ ΔS={dS:.4f}J/K (= R·ln2)")


def test_enthalpy_and_gibbs():
    print("\n--- 焓与吉布斯自由能 ---")
    i = _interp()
    H = i.call("熵_焓", 1000, 1e5, 0.01)
    expected_H = 1000 + 1e5 * 0.01
    assert abs(H - expected_H) < 1e-10
    G = i.call("熵_吉布斯自由能", H, 300, 10)
    expected_G = H - 300 * 10
    assert abs(G - expected_G) < 1e-10
    print(f"  ✓ H={H}J, G={G}J")


def test_heat_capacities():
    print("\n--- 热容 ---")
    i = _interp()
    N = N_A
    Cv = i.call("熵_等容热容", N)
    expected_Cv = 1.5 * N * K_B
    assert abs(Cv - expected_Cv) < 1e-10
    Cp = i.call("熵_等压热容", N)
    expected_Cp = 2.5 * N * K_B
    assert abs(Cp - expected_Cp) < 1e-10
    gamma = i.call("熵_热容比", Cp, Cv)
    expected_gamma = Cp / Cv
    assert abs(gamma - expected_gamma) < 1e-15
    # 单原子理想气体 γ = 5/3
    assert abs(gamma - 5.0/3.0) < 1e-10
    print(f"  ✓ Cv={Cv:.4f}J/K, Cp={Cp:.4f}J/K, γ={gamma:.4f} (=5/3)")


# ============================================================
# 4. 量子统计
# ============================================================

def test_fermi_dirac():
    print("\n--- 费米-狄拉克分布 ---")
    i = _interp()
    # E=μ → f=0.5
    f = i.call("统计_费米狄拉克", 5.0, 5.0, 300)
    assert abs(f - 0.5) < 1e-15
    # E>>μ → f≈0
    f_high = i.call("统计_费米狄拉克", 10.0, 5.0, 300)
    assert f_high < 0.01
    # E<<μ → f≈1
    f_low = i.call("统计_费米狄拉克", 0.0, 5.0, 300)
    assert f_low > 0.99
    print(f"  ✓ E=μ: f={f}, E>>μ: f={f_high:.4f}, E<<μ: f={f_low:.4f}")


def test_bose_einstein():
    print("\n--- 玻色-爱因斯坦分布 ---")
    i = _interp()
    # 取 E = kT（即 x=(E-μ)/(kT)=1），物理合理且不溢出
    E = K_B * 300
    f = i.call("统计_玻色爱因斯坦", E, 0.0, 300)
    expected = 1.0 / (math.exp(1.0) - 1)
    assert abs(f - expected) < 1e-15
    # x>500 时函数应返回 0.0（大能量保护）
    f_big = i.call("统计_玻色爱因斯坦", 5.0, 0.0, 300)
    assert f_big == 0.0
    # x<=0（E<=μ）应返回 inf
    f_inf = i.call("统计_玻色爱因斯坦", 0.0, 0.0, 300)
    assert f_inf == float('inf')
    print(f"  ✓ E=kT: f={f:.6f}, E=5J(保护): f=0, E=μ: f=inf")


def test_fermi_energy():
    print("\n--- 费米能级 ---")
    i = _interp()
    # 铜电子气: n=8.5e28/m³, m=me
    n_Cu = 8.5e28
    EF = i.call("统计_费米能级", M_ELECTRON, n_Cu)
    expected = HBAR ** 2 / (2 * M_ELECTRON) * (3 * math.pi ** 2 * n_Cu) ** (2.0/3)
    assert abs(EF - expected) < 1e-10
    print(f"  ✓ 铜 EF={EF/E_CHARGE:.2f}eV")


def test_fermi_temperature_and_velocity():
    print("\n--- 费米温度与速度 ---")
    i = _interp()
    EF = 1e-18  # ~6.24eV
    TF = i.call("统计_费米温度", EF)
    expected_TF = EF / K_B
    assert abs(TF - expected_TF) < 1e-5
    vF = i.call("统计_费米速度", EF, M_ELECTRON)
    expected_vF = math.sqrt(2 * EF / M_ELECTRON)
    assert abs(vF - expected_vF) < 1e-10
    print(f"  ✓ TF={TF:.0f}K, vF={vF:.0f}m/s")


def test_debye():
    print("\n--- 德拜温度与热容 ---")
    i = _interp()
    v_s = 5000  # 声速
    n = 8.5e28
    omega_D = i.call("统计_德拜频率", v_s, n)
    expected_omegaD = v_s * (6 * math.pi ** 2 * n) ** (1.0/3)
    assert abs(omega_D - expected_omegaD) < 1e-5
    theta_D = i.call("统计_德拜温度", omega_D)
    expected_thetaD = HBAR * expected_omegaD / K_B
    assert abs(theta_D - expected_thetaD) < 1e-5
    # 低温热容
    Cv = i.call("统计_德拜热容低温", N_A, 10, theta_D)
    expected_Cv = (12 * math.pi**4 / 5) * N_A * K_B * (10 / expected_thetaD) ** 3
    assert abs(Cv - expected_Cv) < 1e-20
    print(f"  ✓ θD={theta_D:.0f}K, Cv(10K)={Cv:.4e}J/K")


def test_wien_displacement():
    print("\n--- 维恩位移定律 ---")
    i = _interp()
    # T=5800K (太阳表面) → λmax ≈ 500nm
    lam = i.call("统计_维恩位移", 5800)
    expected = WIEN_B / 5800
    assert abs(lam - expected) < 1e-15
    print(f"  ✓ T=5800K: λmax={lam*1e9:.0f}nm")


def test_blackbody_radiation():
    print("\n--- 黑体辐射功率 ---")
    i = _interp()
    j = i.call("统计_黑体辐射功率", 5800)
    expected = SIGMA_SB * 5800 ** 4
    assert abs(j - expected) < 1e-5
    print(f"  ✓ T=5800K: j={j:.2e}W/m²")


# ============================================================
# 5. 涨落与关联
# ============================================================

def test_energy_fluctuation():
    print("\n--- 能量涨落 ---")
    i = _interp()
    Cv = 1.5 * N_A * K_B
    var_E = i.call("涨落_能量涨落", 300, Cv)
    expected = K_B * 300 ** 2 * Cv
    assert abs(var_E - expected) < 1e-10
    print(f"  ✓ ⟨(ΔE)²⟩={var_E:.4e}J²")


def test_relative_fluctuation():
    print("\n--- 相对涨落 ---")
    i = _interp()
    N = N_A
    Cv = 1.5 * N * K_B
    E_avg = 1.5 * N * K_B * 300
    rel = i.call("涨落_相对能量涨落", 300, Cv, E_avg)
    var_E = K_B * 300 ** 2 * Cv
    expected = math.sqrt(var_E) / E_avg
    assert abs(rel - expected) < 1e-15
    # 相对涨落 ~ 1/√N → 极小
    assert rel < 1e-10
    print(f"  ✓ 相对涨落={rel:.2e} (~1/√N)")


def test_brownian_motion():
    print("\n--- 布朗运动 ---")
    i = _interp()
    D = 1e-9  # 扩散系数
    t = 1.0
    msd = i.call("涨落_布朗位移", D, t)
    expected = 2 * D * t
    assert abs(msd - expected) < 1e-20
    print(f"  ✓ ⟨x²⟩={msd:.2e}m²")


def test_einstein_diffusion():
    print("\n--- 爱因斯坦扩散系数 ---")
    i = _interp()
    eta = 1e-3  # 水粘度
    r = 1e-6    # 1μm粒子
    D = i.call("涨落_爱因斯坦扩散系数", 300, eta, r)
    expected = K_B * 300 / (6 * math.pi * eta * r)
    assert abs(D - expected) < 1e-20
    print(f"  ✓ D={D:.4e}m²/s")


def test_temperature_fluctuation():
    print("\n--- 温度涨落 ---")
    i = _interp()
    Cv = 1.5 * N_A * K_B
    var_T = i.call("涨落_温度涨落", 300, Cv)
    expected = K_B * 300 ** 2 / Cv
    assert abs(var_T - expected) < 1e-10
    print(f"  ✓ ⟨(ΔT)²⟩={var_T:.4e}K²")


# ============================================================
# 6. 物理常量
# ============================================================

def test_statmech_constants():
    print("\n--- 物理常量 ---")
    i = _interp()
    assert i.builtins["kB_玻尔兹曼"] == K_B
    assert i.builtins["R_气体常数统计"] == R_GAS
    assert i.builtins["sigma_斯特藩玻尔兹曼"] == SIGMA_SB
    assert i.builtins["b_维恩位移"] == WIEN_B
    print("  ✓ 4 个统计力学常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_gas_speeds():
    """综合场景：氮气分子速率。"""
    print("\n--- 综合场景：N2 分子速率 ---")
    src = """
#：{
  m = 0.0000000000000000000000000465
  T = 300
  vp = 速率_最概然速率(m)(T)
  vb = 速率_平均速率(m)(T)
  vr = 速率_方均根速率(m)(T)
  [vp]
  [vb]
  [vr]
}
"""
    out = _call(src)
    vp, vb, vr = out
    m = 4.65e-26
    expected_vp = math.sqrt(2 * K_B * 300 / m)
    assert abs(vp - expected_vp) < 1e-6
    assert vp < vb < vr
    print(f"  ✓ N2@300K: vp={vp:.0f}m/s, v̄={vb:.0f}m/s, vrms={vr:.0f}m/s")


def test_matha_scenario_fermi_dirac():
    """综合场景：费米-狄拉克分布。"""
    print("\n--- 综合场景：费米-狄拉克分布 ---")
    src = """
#：{
  EF = 0.000000000000000001
  T = 1000
  f_at_EF = 统计_费米狄拉克(EF)(EF)(T)
  f_above = 统计_费米狄拉克(EF)(EF)(T)
  [f_at_EF]
}
"""
    out = _call(src)
    f = out[0]
    assert abs(f - 0.5) < 1e-10
    print(f"  ✓ E=μ=EF: f={f} (T=1000K)")


def test_matha_scenario_entropy():
    """综合场景：玻尔兹曼熵。"""
    print("\n--- 综合场景：玻尔兹曼熵 ---")
    src = """
#：{
  W = 1000000000000
  S = 熵_玻尔兹曼熵(W)
  [S]
}
"""
    out = _call(src)
    S = out[0]
    expected = K_B * math.log(1e12)
    assert abs(S - expected) < 1e-30
    print(f"  ✓ W=1e12 → S={S:.4e}J/K")


def test_matha_scenario_heat_capacity():
    """综合场景：单原子理想气体热容。"""
    print("\n--- 综合场景：热容 ---")
    src = """
#：{
  Cv = 熵_等容热容(NA_阿伏伽德罗)
  Cp = 熵_等压热容(NA_阿伏伽德罗)
  gamma = 熵_热容比(Cp)(Cv)
  [Cv]
  [Cp]
  [gamma]
}
"""
    out = _call(src)
    Cv, Cp, gamma = out
    expected_Cv = 1.5 * N_A * K_B
    expected_Cp = 2.5 * N_A * K_B
    assert abs(Cv - expected_Cv) < 1e-5
    assert abs(Cp - expected_Cp) < 1e-5
    assert abs(gamma - 5.0/3.0) < 1e-10
    print(f"  ✓ Cv={Cv:.4f}J/K, Cp={Cp:.4f}J/K, γ={gamma:.4f}")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_statmech_registered_in_interp,
        test_statmech_registered_in_semantic,
        test_maxwell_speeds,
        test_maxwell_distribution,
        test_ideal_gas,
        test_mean_free_path,
        test_boltzmann_factor,
        test_discrete_partition_function,
        test_degenerate_partition_function,
        test_harmonic_oscillator_partition,
        test_rotational_partition,
        test_helmholtz_free_energy,
        test_boltzmann_entropy,
        test_gibbs_entropy,
        test_isothermal_entropy_change,
        test_enthalpy_and_gibbs,
        test_heat_capacities,
        test_fermi_dirac,
        test_bose_einstein,
        test_fermi_energy,
        test_fermi_temperature_and_velocity,
        test_debye,
        test_wien_displacement,
        test_blackbody_radiation,
        test_energy_fluctuation,
        test_relative_fluctuation,
        test_brownian_motion,
        test_einstein_diffusion,
        test_temperature_fluctuation,
        test_statmech_constants,
        test_matha_scenario_gas_speeds,
        test_matha_scenario_fermi_dirac,
        test_matha_scenario_entropy,
        test_matha_scenario_heat_capacity,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个统计力学测试全部通过 ✓✓✓")
