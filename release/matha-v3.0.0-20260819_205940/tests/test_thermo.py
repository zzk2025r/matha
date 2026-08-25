"""Matha 热力学测试：气体状态 + 热力学过程 + 热传递 + 热机效率 + 相变热物性。

覆盖：
  1) 气体状态方程：理想气体 pV=nRT、玻意耳、查理、盖-吕萨克、道尔顿分压
  2) 热力学过程：等温功、等压功、等容功、绝热功/压强/温度、第一定律、内能变化
  3) 热传递：傅里叶热传导、牛顿冷却热对流、斯特藩辐射、热阻、串/并联
  4) 热机效率：卡诺、奥托、一般热机、制冷系数、热泵系数
  5) 相变热物性：显热、潜热、线/体膨胀、热容、比热容比、理想气体内能、迈耶关系
  6) 热物性数据库：比热容/热导率/潜热/线膨胀/摩尔质量/γ值
  7) Matha 侧综合场景

运行：python -m tests.test_thermo
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.thermo import (
    _thermo_symtab_names, R_GAS, SIGMA_SB, T_ZERO_C,
    SPECIFIC_HEATS, THERMAL_CONDUCTIVITIES, LATENT_HEATS,
    THERMAL_EXPANSIONS, MOLAR_MASSES, GAMMA_VALUES,
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

def test_thermo_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _thermo_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个热力学内建名全部注册")


def test_thermo_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[热_气压(1)(300)(0.024)]"
    ok = _semantic_ok(src)
    assert ok, "引用热力学内建触发语义错误"
    print("  ✓ 热力学内建在语义侧可直接引用")


# ============================================================
# 1. 气体状态方程
# ============================================================

def test_temperature_conversion():
    print("\n--- 温度转换 ---")
    i = _interp()
    assert i.call("热_摄氏转开尔文", 0) == 273.15
    assert i.call("热_摄氏转开尔文", 100) == 373.15
    assert abs(i.call("热_开尔文转摄氏", 300) - 26.85) < 1e-10
    print("  ✓ 0°C=273.15K, 100°C=373.15K, 300K=26.85°C")


def test_ideal_gas_law():
    print("\n--- 理想气体状态方程 ---")
    i = _interp()
    # 1 mol 理想气体, 300K, 0.0246 m³ → p = nRT/V
    n, T, V = 1.0, 300.0, 0.0246
    p = i.call("热_气压", n, T, V)
    expected = n * R_GAS * T / V
    assert abs(p - expected) < 1e-6
    # 反算摩尔数
    n_back = i.call("热_摩尔数", p, V, T)
    assert abs(n_back - n) < 1e-6
    print(f"  ✓ p={p:.2f}Pa, n={n_back:.6f}mol")


def test_boyle_charles_gaylussac():
    print("\n--- 玻意耳/查理/盖-吕萨克 ---")
    i = _interp()
    # 玻意耳(等温): p1=100kPa, V1=1m³, V2=2m³ → p2=50kPa
    p2 = i.call("热_玻意耳压强", 100000, 1, 2)
    assert abs(p2 - 50000) < 1e-6
    # 查理(等压): V1=1, T1=300K, T2=600K → V2=2
    V2 = i.call("热_查理体积", 1, 300, 600)
    assert abs(V2 - 2) < 1e-6
    # 盖-吕萨克(等容): p1=100kPa, T1=300K, T2=600K → p2=200kPa
    p2_g = i.call("热_盖吕萨克压强", 100000, 300, 600)
    assert abs(p2_g - 200000) < 1e-6
    print(f"  ✓ 玻意耳 p2=50kPa, 查理 V2=2m³, 盖-吕萨克 p2=200kPa")


def test_mass_to_mole():
    print("\n--- 质量→摩尔数 ---")
    i = _interp()
    # 32g O2 (M=0.032kg/mol) → n=1 mol
    n = i.call("热_质量转摩尔", 0.032, 0.032)
    assert abs(n - 1.0) < 1e-10
    print(f"  ✓ 32g O2 → n={n}mol")


# ============================================================
# 2. 热力学过程
# ============================================================

def test_isothermal_work():
    print("\n--- 等温过程做功 ---")
    i = _interp()
    # W = nRT ln(V2/V1): n=1, T=300, V1=1, V2=2 → W=8.314*300*ln2
    W = i.call("过程_等温功", 1, 300, 1, 2)
    expected = 1 * R_GAS * 300 * math.log(2)
    assert abs(W - expected) < 1e-6
    print(f"  ✓ W={W:.4f}J")


def test_isobaric_isochoric_work():
    print("\n--- 等压/等容做功 ---")
    i = _interp()
    # 等压: W = p(V2-V1) = 100000*(2-1) = 100000J
    W_p = i.call("过程_等压功", 100000, 1, 2)
    assert abs(W_p - 100000) < 1e-6
    # 等容: W = 0
    W_v = i.builtins["过程_等容功"]()
    assert W_v == 0.0
    print(f"  ✓ 等压 W={W_p}J, 等容 W=0")


def test_adiabatic_process():
    print("\n--- 绝热过程 ---")
    i = _interp()
    gamma = 1.4
    # 绝热压缩: p1=100kPa, V1=1, V2=0.5 → p2 = 100000 * (1/0.5)^1.4
    p2 = i.call("过程_绝热压强", 100000, 1, 0.5, gamma)
    expected_p = 100000 * (1 / 0.5) ** gamma
    assert abs(p2 - expected_p) < 1e-3
    # 绝热温度: T1=300, V1=1, V2=0.5 → T2 = 300*(1/0.5)^0.4
    T2 = i.call("过程_绝热温度", 300, 1, 0.5, gamma)
    expected_T = 300 * (1 / 0.5) ** (gamma - 1)
    assert abs(T2 - expected_T) < 1e-3
    # 绝热做功
    p1, V1, V2_val = 100000.0, 1.0, 0.5
    W = i.call("过程_绝热功", p1, V1, p2, V2_val, gamma)
    expected_W = (p1 * V1 - p2 * V2_val) / (gamma - 1)
    assert abs(W - expected_W) < 1e-3
    print(f"  ✓ 压缩比2: p2={p2:.1f}Pa, T2={T2:.2f}K, W={W:.2f}J")


def test_first_law():
    print("\n--- 热力学第一定律 ---")
    i = _interp()
    # ΔU = Q - W: Q=500J, W=200J → ΔU=300J
    dU = i.call("过程_第一定律", 500, 200)
    assert dU == 300.0
    print(f"  ✓ Q=500J, W=200J → ΔU={dU}J")


def test_internal_energy():
    print("\n--- 内能变化 ---")
    i = _interp()
    # ΔU = nCvΔT: n=2, Cv=20.8, ΔT=50 → 2080J
    dU = i.call("过程_内能变化", 2, 20.8, 50)
    assert abs(dU - 2080.0) < 1e-6
    print(f"  ✓ ΔU={dU}J")


# ============================================================
# 3. 热传递
# ============================================================

def test_conduction():
    print("\n--- 热传导（傅里叶定律） ---")
    i = _interp()
    # P = kA(T2-T1)/d: k=401(铜), A=0.01, T2=100, T1=20, d=0.1
    P = i.call("传热_热传导", 401, 0.01, 100, 20, 0.1)
    expected = 401 * 0.01 * 80 / 0.1
    assert abs(P - expected) < 1e-6
    print(f"  ✓ 铜棒 P={P:.2f}W")


def test_convection():
    print("\n--- 热对流（牛顿冷却） ---")
    i = _interp()
    # P = hA(Ts-Tf): h=10, A=1, Ts=80, Tf=20
    P = i.call("传热_热对流", 10, 1, 80, 20)
    assert abs(P - 600) < 1e-6
    print(f"  ✓ P={P}W")


def test_radiation():
    print("\n--- 热辐射（斯特藩-玻尔兹曼） ---")
    i = _interp()
    # P = σεA(Thot^4 - Tcold^4): ε=0.9, A=1, Thot=400K, Tcold=300K
    P = i.call("传热_热辐射", 0.9, 1, 400, 300)
    expected = SIGMA_SB * 0.9 * 1 * (400**4 - 300**4)
    assert abs(P - expected) < 1e-6
    print(f"  ✓ P={P:.2f}W")


def test_thermal_resistance():
    print("\n--- 热阻 ---")
    i = _interp()
    # R = d/(kA): d=0.1, k=401, A=0.01 → R=0.1/(401*0.01)
    R = i.call("传热_热阻", 0.1, 401, 0.01)
    expected = 0.1 / (401 * 0.01)
    assert abs(R - expected) < 1e-8
    print(f"  ✓ R={R:.6f}K/W")


# ============================================================
# 4. 热机效率
# ============================================================

def test_carnot_efficiency():
    print("\n--- 卡诺效率 ---")
    i = _interp()
    # η = 1 - Tc/Th: Th=500K, Tc=300K → η=0.4
    eta = i.call("热机_卡诺效率", 500, 300)
    assert abs(eta - 0.4) < 1e-10
    # 卡诺功: Qh=1000J → W=400J
    W = i.call("热机_卡诺功", 1000, 500, 300)
    assert abs(W - 400) < 1e-6
    print(f"  ✓ η={eta} (40%), W={W}J")


def test_otto_efficiency():
    print("\n--- 奥托循环效率 ---")
    i = _interp()
    # η = 1 - 1/r^(γ-1): r=8, γ=1.4 → η=1-1/8^0.4
    eta = i.call("热机_奥托效率", 8, 1.4)
    expected = 1 - 1 / 8 ** 0.4
    assert abs(eta - expected) < 1e-10
    print(f"  ✓ 压缩比8: η={eta:.4f} ({eta*100:.1f}%)")


def test_engine_and_cop():
    print("\n--- 热机效率/制冷系数/热泵系数 ---")
    i = _interp()
    # 一般热机: Qh=2500J, Qc=1000J → η=0.6
    eta = i.call("热机_效率", 2500, 1000)
    assert abs(eta - 0.6) < 1e-10
    # 制冷系数: Tc=260K, Th=300K → COP=260/40=6.5
    cop_r = i.call("热机_制冷系数", 260, 300)
    assert abs(cop_r - 6.5) < 1e-10
    # 热泵系数: Th=300K, Tc=260K → COP=300/40=7.5
    cop_h = i.call("热机_热泵系数", 300, 260)
    assert abs(cop_h - 7.5) < 1e-10
    print(f"  ✓ η={eta}, COP_ref={cop_r}, COP_hp={cop_h}")


# ============================================================
# 5. 相变与热物性
# ============================================================

def test_sensible_latent_heat():
    print("\n--- 显热与潜热 ---")
    i = _interp()
    # 显热: Q = mcΔT: m=1kg, c=4186(水), ΔT=80 → 334880J
    Q_s = i.call("相变_显热", 1, 4186, 80)
    assert abs(Q_s - 334880) < 1e-3
    # 潜热: Q = mL: m=1kg, L=334000(冰熔化) → 334000J
    Q_l = i.call("相变_潜热", 1, 334000)
    assert abs(Q_l - 334000) < 1e-3
    print(f"  ✓ 显热 Q={Q_s}J, 潜热 Q={Q_l}J")


def test_thermal_expansion():
    print("\n--- 热膨胀 ---")
    i = _interp()
    # 线膨胀: ΔL = αL0ΔT: α=2.3e-5(铝), L0=1, ΔT=100 → 0.0023m
    dL = i.call("相变_线膨胀", 2.3e-5, 1, 100)
    assert abs(dL - 0.0023) < 1e-8
    # 体膨胀: ΔV = βV0ΔT: β=6.9e-5, V0=1, ΔT=100 → 0.0069
    dV = i.call("相变_体膨胀", 6.9e-5, 1, 100)
    assert abs(dV - 0.0069) < 1e-8
    print(f"  ✓ 线膨胀 ΔL={dL}m, 体膨胀 ΔV={dV}m³")


def test_heat_capacity_and_gamma():
    print("\n--- 热容/比热容比/迈耶关系 ---")
    i = _interp()
    # C = mc: m=2, c=4186 → 8372 J/K
    C = i.call("相变_热容", 2, 4186)
    assert C == 8372.0
    # γ = cp/cv: 1005/718
    gamma = i.call("相变_比热容比", 1005, 718)
    assert abs(gamma - 1005.0 / 718) < 1e-10
    # 迈耶关系: cp - cv = R → 1005-718=287 J/(mol·K)（空气摩尔热容近似）
    mayer = i.call("相变_迈耶关系", 1005, 718)
    assert abs(mayer - 287) < 1e-6
    print(f"  ✓ C={C}J/K, γ={gamma:.4f}, cp-cv={mayer}J/(mol·K)")


def test_ideal_gas_internal_energy():
    print("\n--- 理想气体内能 ---")
    i = _interp()
    # U = (f/2)nRT: f=3(单原子), n=1, T=300 → 1.5*8.314*300=3741.3J
    U = i.call("相变_理想气体内能", 3, 1, 300)
    expected = 1.5 * R_GAS * 300
    assert abs(U - expected) < 1e-6
    print(f"  ✓ U={U:.2f}J")


# ============================================================
# 6. 热物性数据库
# ============================================================

def test_thermo_database():
    print("\n--- 热物性数据库 ---")
    i = _interp()
    for name, val in SPECIFIC_HEATS.items():
        key = f"比热_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in THERMAL_CONDUCTIVITIES.items():
        key = f"热导率_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in LATENT_HEATS.items():
        key = f"潜热_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in THERMAL_EXPANSIONS.items():
        key = f"线膨胀_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in MOLAR_MASSES.items():
        key = f"摩尔质量_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in GAMMA_VALUES.items():
        key = f"γ_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    # 物理常量
    assert i.builtins["R_气体常数"] == R_GAS
    assert i.builtins["σ_斯特藩玻尔兹曼"] == SIGMA_SB
    assert i.builtins["T_零度"] == T_ZERO_C
    total = (len(SPECIFIC_HEATS) + len(THERMAL_CONDUCTIVITIES) +
             len(LATENT_HEATS) + len(THERMAL_EXPANSIONS) +
             len(MOLAR_MASSES) + len(GAMMA_VALUES) + 3)
    print(f"  ✓ 共 {total} 个热物性常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_water_heating():
    """综合场景：烧水过程（显热+潜热合计）。"""
    print("\n--- 综合场景：0°C冰→100°C水蒸气 总热量 ---")
    src = """
#：{
  m = 1
  c_ice = 比热_冰
  c_water = 比热_水
  L_melt = 潜热_水_熔化
  L_vap = 潜热_水_汽化
  Q1 = 相变_显热(m)(c_ice)(10)
  Q2 = 相变_潜热(m)(L_melt)
  Q3 = 相变_显热(m)(c_water)(100)
  Q4 = 相变_潜热(m)(L_vap)
  total = Q1 + Q2 + Q3 + Q4
  [total]
}
"""
    out = _call(src)
    total = out[0]
    expected = (1 * 2090 * 10 + 1 * 334000 + 1 * 4186 * 100 + 1 * 2260000)
    assert abs(total - expected) < 1e-3
    print(f"  ✓ 总热量 Q={total:.0f}J ({total/1e6:.2f}MJ)")


def test_matha_scenario_carnot_engine():
    """综合场景：卡诺热机输出功 + 效率。"""
    print("\n--- 综合场景：卡诺热机 ---")
    src = """
#：{
  Th = 热_摄氏转开尔文(500)
  Tc = 热_摄氏转开尔文(20)
  Qh = 5000
  eta = 热机_卡诺效率(Th)(Tc)
  W = 热机_卡诺功(Qh)(Th)(Tc)
  [eta]
  [W]
}
"""
    out = _call(src)
    eta, W = out[0], out[1]
    Th = 500 + 273.15
    Tc = 20 + 273.15
    expected_eta = 1 - Tc / Th
    assert abs(eta - expected_eta) < 1e-6
    assert abs(W - expected_eta * 5000) < 1e-3
    print(f"  ✓ Th=773K, Tc=293K → η={eta:.4f}({eta*100:.1f}%), W={W:.1f}J")


def test_matha_scenario_wall_insulation():
    """综合场景：墙壁热传导损失。"""
    print("\n--- 综合场景：墙壁热传导 ---")
    src = """
#：{
  k = 热导率_混凝土
  A = 20
  T_in = 热_摄氏转开尔文(20)
  T_out = 热_摄氏转开尔文(-5)
  d = 0.2
  P = 传热_热传导(k)(A)(T_in)(T_out)(d)
  [P]
}
"""
    out = _call(src)
    P = out[0]
    k = 1.74  # 混凝土热导率
    expected = k * 20 * (293.15 - 268.15) / 0.2
    assert abs(P - expected) < 1e-3
    print(f"  ✓ 混凝土墙 20m², ΔT=25K → P={P:.1f}W")


def test_matha_scenario_gas_expansion():
    """综合场景：气体等温膨胀做功。"""
    print("\n--- 综合场景：等温膨胀 ---")
    src = """
#：{
  n = 2
  T = 热_摄氏转开尔文(27)
  V1 = 0.01
  V2 = 0.02
  W = 过程_等温功(n)(T)(V1)(V2)
  [W]
}
"""
    out = _call(src)
    W = out[0]
    T = 300.15
    expected = 2 * R_GAS * T * math.log(2)
    assert abs(W - expected) < 1e-3
    print(f"  ✓ 2mol, 300K, V1→V2(×2) → W={W:.2f}J")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_thermo_registered_in_interp,
        test_thermo_registered_in_semantic,
        test_temperature_conversion,
        test_ideal_gas_law,
        test_boyle_charles_gaylussac,
        test_mass_to_mole,
        test_isothermal_work,
        test_isobaric_isochoric_work,
        test_adiabatic_process,
        test_first_law,
        test_internal_energy,
        test_conduction,
        test_convection,
        test_radiation,
        test_thermal_resistance,
        test_carnot_efficiency,
        test_otto_efficiency,
        test_engine_and_cop,
        test_sensible_latent_heat,
        test_thermal_expansion,
        test_heat_capacity_and_gamma,
        test_ideal_gas_internal_energy,
        test_thermo_database,
        test_matha_scenario_water_heating,
        test_matha_scenario_carnot_engine,
        test_matha_scenario_wall_insulation,
        test_matha_scenario_gas_expansion,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个热力学测试全部通过 ✓✓✓")
