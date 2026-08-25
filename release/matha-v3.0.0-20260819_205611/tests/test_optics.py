"""Matha 光学测试：几何光学 + 波动光学 + 光度学 + 光学仪器 + 色散与光谱。

覆盖：
  1) 几何光学：折射定律、全反射、球面镜、透镜成像、放大率、造焦公式
  2) 波动光学：双缝干涉、薄膜干涉、单缝衍射、光栅、马吕斯定律、布儒斯特角
  3) 光度学：光通量、照度、亮度、光视效能
  4) 光学仪器：放大镜、显微镜、望远镜、数值孔径、瑞利判据
  5) 色散与光谱：柯西方程、光子能量、红移
  6) 折射率/光波长数据库
  7) Matha 侧综合场景

运行：python -m tests.test_optics
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.optics import (
    _optics_symtab_names, C_LIGHT, H_PLANCK, K_MAX,
    REFRACTIVE_INDICES, WAVELENGTHS,
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

def test_optics_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _optics_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个光学内建名全部注册")


def test_optics_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[几何_折射角(1.0)(0.5)(1.5) + 波动_马吕斯定律(100)(0.3)]"
    ok = _semantic_ok(src)
    assert ok, "引用光学内建触发语义错误"
    print("  ✓ 光学内建在语义侧可直接引用")


# ============================================================
# 1. 几何光学
# ============================================================

def test_snell_law():
    print("\n--- 折射定律 ---")
    i = _interp()
    # n1=1.0(空气), θ1=30°, n2=1.5(玻璃) → θ2 = arcsin(sin30/1.5)
    theta1 = math.radians(30)
    theta2 = i.call("几何_折射角", 1.0, theta1, 1.5)
    expected = math.asin(1.0 * math.sin(theta1) / 1.5)
    assert abs(theta2 - expected) < 1e-12
    print(f"  ✓ 空气→玻璃 30°→{math.degrees(theta2):.2f}°")


def test_total_internal_reflection():
    print("\n--- 全反射临界角 ---")
    i = _interp()
    # n1=1.5(玻璃), n2=1.0(空气) → θc = arcsin(1/1.5)
    theta_c = i.call("几何_全反射角", 1.5, 1.0)
    expected = math.asin(1.0 / 1.5)
    assert abs(theta_c - expected) < 1e-12
    print(f"  ✓ 玻璃→空气 θc={math.degrees(theta_c):.2f}°")


def test_mirror_focal_length():
    print("\n--- 球面镜焦距 ---")
    i = _interp()
    # f = R/2: R=20cm → f=10cm
    f = i.call("几何_球面镜焦距", 0.2)
    assert abs(f - 0.1) < 1e-12
    print(f"  ✓ R=20cm → f={f*100:.0f}cm")


def test_lens_imaging():
    print("\n--- 透镜成像 ---")
    i = _interp()
    # 1/v + 1/u = 1/f: u=0.3m, f=0.1m → v=0.15m
    v = i.call("几何_像距", 0.3, 0.1)
    expected = 0.3 * 0.1 / (0.3 - 0.1)
    assert abs(v - expected) < 1e-12
    # 放大率 m = -v/u = -0.15/0.3 = -0.5
    m = i.call("几何_放大率", v, 0.3)
    assert abs(m - (-0.5)) < 1e-10
    print(f"  ✓ u=30cm, f=10cm → v={v*100:.0f}cm, m={m}")


def test_lensmaker_equation():
    print("\n--- 造焦公式 ---")
    i = _interp()
    # 1/f = (n-1)(1/R1 - 1/R2): n=1.5, R1=0.2, R2=-0.2
    # → 1/f = 0.5*(5+5) = 5 → f=0.2m
    f = i.call("几何_透镜焦距", 1.5, 0.2, -0.2)
    expected = 1.0 / (0.5 * (1.0/0.2 - 1.0/(-0.2)))
    assert abs(f - expected) < 1e-12
    print(f"  ✓ 双凸透镜 n=1.5 → f={f*100:.1f}cm")


def test_medium_light_speed():
    print("\n--- 介质中光速 ---")
    i = _interp()
    # v = c/n: n=1.5(玻璃) → v = c/1.5
    v = i.call("几何_介质光速", 1.5)
    assert abs(v - C_LIGHT / 1.5) < 1e-3
    print(f"  ✓ 玻璃中光速 v={v:.4e}m/s (={C_LIGHT/1.5:.4e})")


def test_lens_combination():
    print("\n--- 透镜组合 ---")
    i = _interp()
    # 1/f = 1/f1 + 1/f2: f1=0.1, f2=0.2 → f=1/15
    f = i.call("几何_透镜组合", 0.1, 0.2)
    expected = 1.0 / (10 + 5)
    assert abs(f - expected) < 1e-12
    print(f"  ✓ f1=10cm, f2=20cm → f={f*100:.2f}cm")


# ============================================================
# 2. 波动光学
# ============================================================

def test_double_slit_interference():
    print("\n--- 双缝干涉 ---")
    i = _interp()
    # Δy = λD/d: λ=632.8nm, D=2m, d=0.5mm
    lam = 632.8e-9
    D = 2.0
    d = 0.5e-3
    dy = i.call("波动_双缝条纹间距", lam, D, d)
    expected = lam * D / d
    assert abs(dy - expected) < 1e-15
    print(f"  ✓ Δy={dy*1000:.4f}mm")


def test_thin_film_interference():
    print("\n--- 薄膜干涉 ---")
    i = _interp()
    # 2nd = mλ: n=1.33, d=200nm → 2*1.33*200=532nm
    opd = i.call("波动_薄膜光程差", 1.33, 200e-9)
    assert abs(opd - 2 * 1.33 * 200e-9) < 1e-15
    print(f"  ✓ 光程差={opd*1e9:.1f}nm")


def test_single_slit_diffraction():
    print("\n--- 单缝衍射 ---")
    i = _interp()
    # a·sinθ = mλ: λ=500nm, a=0.01mm, m=1
    lam = 500e-9
    a = 0.01e-3
    theta = i.call("波动_单缝暗纹角", lam, a, 1)
    expected = math.asin(lam / a)
    assert abs(theta - expected) < 1e-15
    print(f"  ✓ 第一暗纹 θ={math.degrees(theta):.4f}°")


def test_grating():
    print("\n--- 光栅衍射 ---")
    i = _interp()
    # d·sinθ = mλ: λ=589nm, d=1/600mm, m=1
    lam = 589e-9
    d_grating = 1e-3 / 600
    theta = i.call("波动_光栅衍射角", lam, d_grating, 1)
    expected = math.asin(lam / d_grating)
    assert abs(theta - expected) < 1e-15
    # 分辨本领 R = mN: m=2, N=10000
    R = i.call("波动_光栅分辨本领", 2, 10000)
    assert R == 20000
    print(f"  ✓ 一级衍射 θ={math.degrees(theta):.2f}°, R={R}")


def test_malus_law():
    print("\n--- 马吕斯定律 ---")
    i = _interp()
    # I = I₀cos²θ: I0=100, θ=30°
    I = i.call("波动_马吕斯定律", 100, math.radians(30))
    expected = 100 * math.cos(math.radians(30)) ** 2
    assert abs(I - expected) < 1e-10
    # θ=0° → I=I₀
    I0 = i.call("波动_马吕斯定律", 100, 0)
    assert abs(I0 - 100) < 1e-10
    print(f"  ✓ I0=100, θ=30° → I={I:.2f}")


def test_brewster_angle():
    print("\n--- 布儒斯特角 ---")
    i = _interp()
    # tanθB = n2/n1: n1=1.0, n2=1.5 → θB=arctan(1.5)
    theta_B = i.call("波动_布儒斯特角", 1.0, 1.5)
    expected = math.atan(1.5 / 1.0)
    assert abs(theta_B - expected) < 1e-12
    print(f"  ✓ 空气→玻璃 θB={math.degrees(theta_B):.2f}°")


# ============================================================
# 3. 光度学
# ============================================================

def test_luminous_flux():
    print("\n--- 光通量 ---")
    i = _interp()
    # Φ = 4πI: I=100cd → Φ=400π lm
    Phi = i.call("光度_光通量", 100)
    assert abs(Phi - 400 * math.pi) < 1e-10
    print(f"  ✓ I=100cd → Φ={Phi:.2f}lm")


def test_illuminance():
    print("\n--- 照度 ---")
    i = _interp()
    # E = I/r²: I=100cd, r=2m → 25 lux
    E = i.call("光度_照度", 100, 2)
    assert abs(E - 25) < 1e-10
    # 斜入射 E = (I/r²)cosθ: θ=60° → 25*0.5=12.5
    E_slant = i.call("光度_斜照度", 100, 2, math.radians(60))
    assert abs(E_slant - 12.5) < 1e-10
    print(f"  ✓ 正射 E={E}lux, 斜60° E={E_slant}lux")


def test_luminance():
    print("\n--- 光亮度 ---")
    i = _interp()
    # L = I/A: I=50cd, A=0.01m² → 5000 cd/m²
    L = i.call("光度_亮度", 50, 0.01)
    assert abs(L - 5000) < 1e-6
    print(f"  ✓ L={L}cd/m²")


def test_luminous_efficacy():
    print("\n--- 光视效能 ---")
    i = _interp()
    # K = Φ/P: Φ=800lm, P=10W → 80 lm/W
    K = i.call("光度_光视效能", 800, 10)
    assert abs(K - 80) < 1e-10
    print(f"  ✓ K={K}lm/W")


# ============================================================
# 4. 光学仪器
# ============================================================

def test_magnifier():
    print("\n--- 放大镜 ---")
    i = _interp()
    # M = 25/f: f=5cm=0.05m → M=5
    M = i.call("仪器_放大镜", 0.05)
    assert abs(M - 5.0) < 1e-10
    print(f"  ✓ f=5cm → M={M}×")


def test_microscope():
    print("\n--- 显微镜 ---")
    i = _interp()
    # M = (L/fo)(25/fe): L=0.16, fo=0.004, fe=0.025 → 40*10=400
    M = i.call("仪器_显微镜", 0.16, 0.004, 0.025)
    expected = (0.16 / 0.004) * (0.25 / 0.025)
    assert abs(M - expected) < 1e-10
    print(f"  ✓ M={M:.0f}×")


def test_telescope():
    print("\n--- 望远镜 ---")
    i = _interp()
    # M = -fo/fe: fo=0.8, fe=0.025 → -32
    M = i.call("仪器_望远镜", 0.8, 0.025)
    assert abs(M - (-32.0)) < 1e-10
    print(f"  ✓ M={M}×")


def test_numerical_aperture():
    print("\n--- 数值孔径 ---")
    i = _interp()
    # NA = n·sinα: n=1.5, α=60°
    NA = i.call("仪器_数值孔径", 1.5, math.radians(60))
    expected = 1.5 * math.sin(math.radians(60))
    assert abs(NA - expected) < 1e-10
    print(f"  ✓ NA={NA:.4f}")


def test_rayleigh_criterion():
    print("\n--- 瑞利判据 ---")
    i = _interp()
    # θ = 1.22λ/D: λ=550nm, D=0.05m
    theta = i.call("仪器_最小分辨角", 550e-9, 0.05)
    expected = 1.22 * 550e-9 / 0.05
    assert abs(theta - expected) < 1e-15
    # 分辨极限: d = 0.61λ/NA
    d_min = i.call("仪器_分辨极限", 550e-9, 0.8)
    expected_d = 0.61 * 550e-9 / 0.8
    assert abs(d_min - expected_d) < 1e-15
    print(f"  ✓ θ={theta:.4e}rad, d_min={d_min*1e9:.2f}nm")


# ============================================================
# 5. 色散与光谱
# ============================================================

def test_cauchy_equation():
    print("\n--- 柯西方程 ---")
    i = _interp()
    # n = A + B/λ²: A=1.5046, B=4200e-18, λ=589nm
    A, B, lam = 1.5046, 4200e-18, 589e-9
    n = i.call("色散_柯西折射率", A, B, lam)
    expected = A + B / lam**2
    assert abs(n - expected) < 1e-12
    # 色散率 dn/dλ = -2B/λ³
    dn = i.call("色散_色散率", B, lam)
    expected_dn = -2 * B / lam**3
    assert abs(dn - expected_dn) < 1e-20
    print(f"  ✓ λ=589nm: n={n:.6f}, dn/dλ={dn:.2e}/m")


def test_photon_energy():
    print("\n--- 光子能量 ---")
    i = _interp()
    # E = hf: f=5e14 Hz (可见光)
    E1 = i.call("色散_光子能量频率", 5e14)
    assert abs(E1 - H_PLANCK * 5e14) < 1e-20
    # E = hc/λ: λ=500nm
    E2 = i.call("色散_光子能量波长", 500e-9)
    expected = H_PLANCK * C_LIGHT / 500e-9
    assert abs(E2 - expected) < 1e-25
    print(f"  ✓ E(f=5e14Hz)={E1:.4e}J, E(λ=500nm)={E2:.4e}J")


def test_photon_momentum():
    print("\n--- 光子动量 ---")
    i = _interp()
    # p = h/λ: λ=500nm
    p = i.call("色散_光子动量", 500e-9)
    expected = H_PLANCK / 500e-9
    assert abs(p - expected) < 1e-30
    print(f"  ✓ p={p:.4e}kg·m/s")


def test_redshift():
    print("\n--- 红移 ---")
    i = _interp()
    # z = (λobs-λemit)/λemit: λobs=700nm, λemit=656nm → z≈0.067
    z = i.call("色散_红移", 700e-9, 656e-9)
    expected = (700e-9 - 656e-9) / 656e-9
    assert abs(z - expected) < 1e-10
    # v = zc
    v = i.call("色散_红移速度", z)
    assert abs(v - z * C_LIGHT) < 1
    print(f"  ✓ z={z:.6f}, v={v:.0f}m/s")


# ============================================================
# 6. 数据库
# ============================================================

def test_optics_database():
    print("\n--- 折射率/光波长数据库 ---")
    i = _interp()
    for name, val in REFRACTIVE_INDICES.items():
        key = f"折射率_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in WAVELENGTHS.items():
        key = f"波长_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    # 物理常量
    assert i.builtins["c_光速"] == C_LIGHT
    assert i.builtins["h_普朗克"] == H_PLANCK
    assert i.builtins["Km_最大光视效能"] == K_MAX
    total = len(REFRACTIVE_INDICES) + len(WAVELENGTHS) + 3
    print(f"  ✓ {len(REFRACTIVE_INDICES)} 折射率 + {len(WAVELENGTHS)} 光波长 + 3 物理常量 = {total} 常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_prism_refraction():
    """综合场景：棱镜折射。"""
    print("\n--- 综合场景：棱镜折射 ---")
    src = """
#：{
  n_glass = 折射率_普通玻璃
  theta1 = 0.5235987755982988
  theta2 = 几何_折射角(1.0)(theta1)(n_glass)
  v_glass = 几何_介质光速(n_glass)
  [theta2]
  [v_glass]
}
"""
    out = _call(src)
    theta2, v_glass = out[0], out[1]
    n = 1.52
    expected_theta2 = math.asin(math.sin(math.radians(30)) / n)
    assert abs(theta2 - expected_theta2) < 1e-10
    assert abs(v_glass - C_LIGHT / n) < 1e-3
    print(f"  ✓ 空气→玻璃 30°→{math.degrees(theta2):.2f}°, v={v_glass:.4e}m/s")


def test_matha_scenario_double_slit():
    """综合场景：双缝干涉实验。"""
    print("\n--- 综合场景：双缝干涉 ---")
    src = """
#：{
  lam = 波长_HeNe激光
  D = 1.5
  d = 0.0004
  dy = 波动_双缝条纹间距(lam)(D)(d)
  [dy]
}
"""
    out = _call(src)
    dy = out[0]
    lam = 632.8e-9
    expected = lam * 1.5 / 0.0004
    assert abs(dy - expected) < 1e-15
    print(f"  ✓ HeNe激光 Δy={dy*1000:.4f}mm")


def test_matha_scenario_photon():
    """综合场景：光子能量与动量。"""
    print("\n--- 综合场景：光子能量与动量 ---")
    src = """
#：{
  lam = 波长_绿光
  E = 色散_光子能量波长(lam)
  p = 色散_光子动量(lam)
  [E]
  [p]
}
"""
    out = _call(src)
    E, p = out[0], out[1]
    lam = 530e-9
    assert abs(E - H_PLANCK * C_LIGHT / lam) < 1e-25
    assert abs(p - H_PLANCK / lam) < 1e-30
    print(f"  ✓ 绿光: E={E:.4e}J, p={p:.4e}kg·m/s")


def test_matha_scenario_microscope_resolution():
    """综合场景：显微镜分辨极限。"""
    print("\n--- 综合场景：显微镜分辨极限 ---")
    src = """
#：{
  lam = 波长_绿光
  NA = 仪器_数值孔径(1.5)(0.7853981633974483)
  d_min = 仪器_分辨极限(lam)(NA)
  [NA]
  [d_min]
}
"""
    out = _call(src)
    NA, d_min = out[0], out[1]
    expected_NA = 1.5 * math.sin(math.radians(45))
    assert abs(NA - expected_NA) < 1e-10
    lam = 530e-9
    expected_d = 0.61 * lam / expected_NA
    assert abs(d_min - expected_d) < 1e-15
    print(f"  ✓ NA={NA:.4f}, d_min={d_min*1e9:.1f}nm")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_optics_registered_in_interp,
        test_optics_registered_in_semantic,
        test_snell_law,
        test_total_internal_reflection,
        test_mirror_focal_length,
        test_lens_imaging,
        test_lensmaker_equation,
        test_medium_light_speed,
        test_lens_combination,
        test_double_slit_interference,
        test_thin_film_interference,
        test_single_slit_diffraction,
        test_grating,
        test_malus_law,
        test_brewster_angle,
        test_luminous_flux,
        test_illuminance,
        test_luminance,
        test_luminous_efficacy,
        test_magnifier,
        test_microscope,
        test_telescope,
        test_numerical_aperture,
        test_rayleigh_criterion,
        test_cauchy_equation,
        test_photon_energy,
        test_photon_momentum,
        test_redshift,
        test_optics_database,
        test_matha_scenario_prism_refraction,
        test_matha_scenario_double_slit,
        test_matha_scenario_photon,
        test_matha_scenario_microscope_resolution,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个光学测试全部通过 ✓✓✓")
