"""Matha 声学测试：声波基础 + 声强声压级 + 多普勒效应 + 声学现象 + 管道弦振动。

覆盖：
  1) 声波基础：空气声速、波长频率关系、周期、角频率、波数、介质声速
  2) 声强与声压级：声强、声强级、声压级、声功率级、分贝叠加
  3) 多普勒效应：观察者运动、声源运动、通用公式、马赫数、马赫角
  4) 声学现象：拍频、驻波、反平方衰减、吸收衰减、声压衰减
  5) 管道与弦振动：弦频率、开管/闭管基频与谐波
  6) 介质声速/密度/吸收系数数据库
  7) Matha 侧综合场景

运行：python -m tests.test_acoustics
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.acoustics import (
    _acoustics_symtab_names, P_REF, I_REF, W_REF,
    SOUND_SPEEDS, MEDIUM_DENSITIES, ABSORPTION_COEFFS,
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

def test_acoustics_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _acoustics_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个声学内建名全部注册")


def test_acoustics_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[声_空气声速(20) + 声_波长(343)(440)]"
    ok = _semantic_ok(src)
    assert ok, "引用声学内建触发语义错误"
    print("  ✓ 声学内建在语义侧可直接引用")


# ============================================================
# 1. 声波基础
# ============================================================

def test_air_sound_speed():
    print("\n--- 空气声速 ---")
    i = _interp()
    # 0°C → 331.3 m/s
    assert abs(i.call("声_空气声速", 0) - 331.3) < 1e-10
    # 20°C → 331.3 + 0.6*20 = 343.3 m/s
    assert abs(i.call("声_空气声速", 20) - 343.3) < 1e-10
    print("  ✓ 0°C→331.3m/s, 20°C→343.3m/s")


def test_wavelength_frequency():
    print("\n--- 波长与频率 ---")
    i = _interp()
    c = 343.0  # 声速
    f = 440.0  # A4 音符
    lam = i.call("声_波长", c, f)       # λ = c/f = 343/440 ≈ 0.7795m
    assert abs(lam - c / f) < 1e-10
    f_back = i.call("声_频率", c, lam)  # 反算
    assert abs(f_back - f) < 1e-10
    print(f"  ✓ 440Hz: λ={lam:.4f}m, 反算 f={f_back:.1f}Hz")


def test_period_angular_freq_wavenumber():
    print("\n--- 周期/角频率/波数 ---")
    i = _interp()
    f = 440.0
    T = i.call("声_周期", f)            # T = 1/440
    assert abs(T - 1 / f) < 1e-12
    omega = i.call("声_角频率", f)      # ω = 2πf
    assert abs(omega - 2 * math.pi * f) < 1e-10
    lam = 343.0 / f
    k = i.call("声_波数", lam)          # k = 2π/λ
    assert abs(k - 2 * math.pi / lam) < 1e-10
    print(f"  ✓ f=440: T={T:.6f}s, ω={omega:.2f}rad/s, k={k:.2f}/m")


def test_medium_sound_speed():
    print("\n--- 介质声速 ---")
    i = _interp()
    # 钢中纵波: c = √(E/ρ), E=2.06e11, ρ=7850
    E_steel = 2.06e11
    rho_steel = 7850.0
    c = i.call("声_介质声速", E_steel, rho_steel)
    expected = math.sqrt(E_steel / rho_steel)
    assert abs(c - expected) < 1e-6
    # 横波: c = √(G/ρ), G=7.9e10
    G_steel = 7.9e10
    c_t = i.call("声_横波声速", G_steel, rho_steel)
    expected_t = math.sqrt(G_steel / rho_steel)
    assert abs(c_t - expected_t) < 1e-6
    print(f"  ✓ 钢纵波 c={c:.1f}m/s, 横波 c={c_t:.1f}m/s")


# ============================================================
# 2. 声强与声压级
# ============================================================

def test_sound_intensity_from_pressure():
    print("\n--- 声强（由声压） ---")
    i = _interp()
    # I = p²/(ρc): p=0.1Pa, ρ=1.205, c=343
    I = i.call("强级_声强由声压", 0.1, 1.205, 343)
    expected = 0.1**2 / (1.205 * 343)
    assert abs(I - expected) < 1e-15
    print(f"  ✓ p=0.1Pa → I={I:.6e}W/m²")


def test_sound_intensity_level():
    print("\n--- 声强级 ---")
    i = _interp()
    # I = 10⁻⁴ W/m² → L_I = 10·lg(10⁻⁴/10⁻¹²) = 80 dB
    L_I = i.call("强级_声强级", 1e-4)
    assert abs(L_I - 80.0) < 1e-10
    # 反算
    I_back = i.call("强级_声强由级", 80.0)
    assert abs(I_back - 1e-4) < 1e-15
    print(f"  ✓ I=10⁻⁴ → L={L_I}dB, 反算 I={I_back:.2e}W/m²")


def test_sound_pressure_level():
    print("\n--- 声压级 ---")
    i = _interp()
    # p = 0.1Pa → L_p = 20·lg(0.1/2e-5) = 20·lg(5000) ≈ 74 dB
    L_p = i.call("强级_声压级", 0.1)
    expected = 20 * math.log10(0.1 / P_REF)
    assert abs(L_p - expected) < 1e-10
    # 反算
    p_back = i.call("强级_声压由级", L_p)
    assert abs(p_back - 0.1) < 1e-15
    print(f"  ✓ p=0.1Pa → L_p={L_p:.2f}dB, 反算 p={p_back:.4f}Pa")


def test_sound_power_level():
    print("\n--- 声功率级 ---")
    i = _interp()
    # W = 0.001W → L_W = 10·lg(0.001/10⁻¹²) = 90 dB
    L_W = i.call("强级_声功率级", 0.001)
    assert abs(L_W - 90.0) < 1e-10
    print(f"  ✓ W=0.001W → L_W={L_W}dB")


def test_intensity_from_power():
    print("\n--- 声强（由功率和面积） ---")
    i = _interp()
    # I = W/A: W=0.01W, A=10m² → 0.001 W/m²
    I = i.call("强级_声强由功率", 0.01, 10)
    assert abs(I - 0.001) < 1e-12
    print(f"  ✓ I={I}W/m²")


def test_decibel_addition():
    print("\n--- 分贝叠加 ---")
    i = _interp()
    # 两个 80dB 声源 → 83.01 dB
    L_total = i.call("强级_分贝叠加", [80, 80])
    expected = 10 * math.log10(2 * 10 ** 8)
    assert abs(L_total - expected) < 1e-6
    # 80dB + 0dB → 80dB（近似）
    L_total2 = i.call("强级_分贝叠加", [80, 0])
    assert abs(L_total2 - 10 * math.log10(10 ** 8 + 1)) < 1e-6
    print(f"  ✓ 80+80dB → {L_total:.2f}dB")


# ============================================================
# 3. 多普勒效应
# ============================================================

def test_doppler_observer_moving():
    print("\n--- 多普勒：观察者运动 ---")
    i = _interp()
    # f'=f(c+v_o)/c: f=440, c=343, v_o=30 → 440*373/343
    f_prime = i.call("多普勒_观察者运动", 440, 343, 30)
    expected = 440 * (343 + 30) / 343
    assert abs(f_prime - expected) < 1e-6
    print(f"  ✓ 接近: f'={f_prime:.2f}Hz (原440Hz)")


def test_doppler_source_moving():
    print("\n--- 多普勒：声源运动 ---")
    i = _interp()
    # f'=fc/(c-v_s): f=440, c=343, v_s=30 → 440*343/313
    f_prime = i.call("多普勒_声源运动", 440, 343, 30)
    expected = 440 * 343 / (343 - 30)
    assert abs(f_prime - expected) < 1e-6
    print(f"  ✓ 声源接近: f'={f_prime:.2f}Hz (原440Hz)")


def test_doppler_general():
    print("\n--- 多普勒：通用公式 ---")
    i = _interp()
    # f'=f(c+v_o)/(c-v_s): f=440, c=343, v_o=20, v_s=30
    f_prime = i.call("多普勒_通用", 440, 343, 20, 30)
    expected = 440 * (343 + 20) / (343 - 30)
    assert abs(f_prime - expected) < 1e-6
    print(f"  ✓ 双方运动: f'={f_prime:.2f}Hz")


def test_mach_number_and_angle():
    print("\n--- 马赫数与马赫角 ---")
    i = _interp()
    # Ma = v/c: v=680, c=340 → Ma=2
    Ma = i.call("多普勒_马赫数", 680, 340)
    assert abs(Ma - 2.0) < 1e-10
    # 马赫角: θ = arcsin(c/v) = arcsin(0.5) = 30°
    theta = i.call("多普勒_马赫角", 680, 340)
    assert abs(theta - math.pi / 6) < 1e-10
    print(f"  ✓ Ma={Ma}, θ={math.degrees(theta):.1f}°")


# ============================================================
# 4. 声学现象
# ============================================================

def test_beat_frequency():
    print("\n--- 拍频 ---")
    i = _interp()
    # f_beat = |f1-f2|: 440, 444 → 4Hz
    f_beat = i.call("现象_拍频", 440, 444)
    assert abs(f_beat - 4.0) < 1e-10
    print(f"  ✓ 440Hz & 444Hz → 拍频={f_beat}Hz")


def test_standing_wave():
    print("\n--- 驻波 ---")
    i = _interp()
    # λ_n = 2L/n: L=1m, n=1 → 2m
    lam = i.call("现象_驻波波长", 1, 1)
    assert abs(lam - 2.0) < 1e-10
    # f_n = nv/(2L): n=2, v=343, L=1 → 343Hz
    f = i.call("现象_驻波频率", 2, 343, 1)
    assert abs(f - 343.0) < 1e-10
    print(f"  ✓ n=1: λ={lam}m; n=2: f={f}Hz")


def test_inverse_square_attenuation():
    print("\n--- 反平方衰减 ---")
    i = _interp()
    # I2 = I1*(r1/r2)²: I1=1, r1=1, r2=10 → 0.01
    I2 = i.call("现象_反平方衰减", 1, 1, 10)
    assert abs(I2 - 0.01) < 1e-12
    print(f"  ✓ 1m→10m: I={I2} (衰减100倍)")


def test_absorption_attenuation():
    print("\n--- 吸收衰减 ---")
    i = _interp()
    # I2 = I1*e^(-αd): I1=1, α=0.01, d=100 → e⁻¹
    I2 = i.call("现象_吸收衰减", 1, 0.01, 100)
    expected = math.exp(-1)
    assert abs(I2 - expected) < 1e-10
    print(f"  ✓ α=0.01, d=100m → I={I2:.4f} (={expected:.4f})")


def test_pressure_attenuation():
    print("\n--- 声压衰减 ---")
    i = _interp()
    # p2 = p1*(r1/r2): p1=1, r1=1, r2=10 → 0.1
    p2 = i.call("现象_声压衰减", 1, 1, 10)
    assert abs(p2 - 0.1) < 1e-12
    print(f"  ✓ 1m→10m: p={p2} (衰减10倍)")


# ============================================================
# 5. 管道与弦振动
# ============================================================

def test_string_vibration():
    print("\n--- 弦振动 ---")
    i = _interp()
    # 弦上波速: v = √(T/μ): T=100, μ=0.01 → 100 m/s
    v = i.call("弦管_弦上波速", 100, 0.01)
    assert abs(v - 100.0) < 1e-10
    # 基频: f = (1/2L)√(T/μ): T=100, μ=0.01, L=0.5 → (1/1)*100 = 100 Hz
    f = i.call("弦管_弦频率", 100, 0.01, 0.5)
    assert abs(f - 100.0) < 1e-10
    # 泛音: f_n = n*100: n=3 → 300 Hz
    f3 = i.call("弦管_弦泛音", 100, 0.01, 0.5, 3)
    assert abs(f3 - 300.0) < 1e-10
    print(f"  ✓ 弦: v={v}m/s, f₁={f}Hz, f₃={f3}Hz")


def test_open_pipe():
    print("\n--- 开管共鸣 ---")
    i = _interp()
    c = 343.0
    L = 0.5
    # 基频: f₁ = c/(2L) = 343
    f1 = i.call("弦管_开管基频", c, L)
    assert abs(f1 - 343.0) < 1e-10
    # 谐波: f_n = nc/(2L): n=2 → 686
    f2 = i.call("弦管_开管谐波", c, L, 2)
    assert abs(f2 - 686.0) < 1e-10
    print(f"  ✓ 开管 L=0.5m: f₁={f1}Hz, f₂={f2}Hz")


def test_closed_pipe():
    print("\n--- 闭管共鸣 ---")
    i = _interp()
    c = 343.0
    L = 0.5
    # 基频: f₁ = c/(4L) = 171.5
    f1 = i.call("弦管_闭管基频", c, L)
    assert abs(f1 - 171.5) < 1e-10
    # 谐波: f_n = (2n-1)c/(4L): n=2 → 3*171.5=514.5
    f2 = i.call("弦管_闭管谐波", c, L, 2)
    assert abs(f2 - 514.5) < 1e-10
    print(f"  ✓ 闭管 L=0.5m: f₁={f1}Hz, f₃={f2}Hz (只有奇次谐波)")


# ============================================================
# 6. 数据库
# ============================================================

def test_acoustics_database():
    print("\n--- 介质声速/密度/吸收系数数据库 ---")
    i = _interp()
    for name, val in SOUND_SPEEDS.items():
        key = f"声速_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in MEDIUM_DENSITIES.items():
        key = f"声学密度_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in ABSORPTION_COEFFS.items():
        key = f"吸收系数_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    # 物理常量
    assert i.builtins["p0_参考声压"] == P_REF
    assert i.builtins["I0_参考声强"] == I_REF
    assert i.builtins["W0_参考声功率"] == W_REF
    total = len(SOUND_SPEEDS) + len(MEDIUM_DENSITIES) + len(ABSORPTION_COEFFS) + 3
    print(f"  ✓ {len(SOUND_SPEEDS)} 声速 + {len(MEDIUM_DENSITIES)} 密度 + {len(ABSORPTION_COEFFS)} 吸收系数 + 3 参考常量 = {total} 常量全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_concert_pitch():
    """综合场景：A4 音符波长与周期。"""
    print("\n--- 综合场景：A4 音符参数 ---")
    src = """
#：{
  c = 声速_空气_20C
  f = 440
  lam = 声_波长(c)(f)
  T = 声_周期(f)
  omega = 声_角频率(f)
  [lam]
  [T]
  [omega]
}
"""
    out = _call(src)
    lam, T, omega = out[0], out[1], out[2]
    c = 343.2
    assert abs(lam - c / 440) < 1e-6
    assert abs(T - 1 / 440) < 1e-10
    assert abs(omega - 2 * math.pi * 440) < 1e-6
    print(f"  ✓ A4=440Hz: λ={lam:.4f}m, T={T:.6f}s, ω={omega:.2f}rad/s")


def test_matha_scenario_noise_level():
    """综合场景：声压级计算（噪声评估）。"""
    print("\n--- 综合场景：噪声声压级 ---")
    src = """
#：{
  p = 0.5
  rho = 声学密度_空气_20C
  c = 声速_空气_20C
  I = 强级_声强由声压(p)(rho)(c)
  L_I = 强级_声强级(I)
  L_p = 强级_声压级(p)
  [I]
  [L_I]
  [L_p]
}
"""
    out = _call(src)
    I, L_I, L_p = out[0], out[1], out[2]
    rho = 1.205
    c = 343.2
    expected_I = 0.5**2 / (rho * c)
    expected_L_I = 10 * math.log10(expected_I / I_REF)
    expected_L_p = 20 * math.log10(0.5 / P_REF)
    assert abs(I - expected_I) < 1e-8
    assert abs(L_I - expected_L_I) < 1e-6
    assert abs(L_p - expected_L_p) < 1e-6
    print(f"  ✓ p=0.5Pa → I={I:.4e}W/m², L_I={L_I:.1f}dB, L_p={L_p:.1f}dB")


def test_matha_scenario_ambulance_doppler():
    """综合场景：救护车多普勒效应。"""
    print("\n--- 综合场景：多普勒效应 ---")
    src = """
#：{
  f = 700
  c = 声速_空气_20C
  v_s = 30
  f_approach = 多普勒_声源运动(f)(c)(v_s)
  f_recede = 多普勒_声源运动(f)(c)(0 - v_s)
  [f_approach]
  [f_recede]
}
"""
    out = _call(src)
    f_approach, f_recede = out[0], out[1]
    c = 343.2
    expected_approach = 700 * c / (c - 30)
    expected_recede = 700 * c / (c + 30)
    assert abs(f_approach - expected_approach) < 1e-6
    assert abs(f_recede - expected_recede) < 1e-6
    print(f"  ✓ 救护车: 接近={f_approach:.1f}Hz, 远离={f_recede:.1f}Hz (原700Hz)")


def test_matha_scenario_guitar_string():
    """综合场景：吉他弦振动频率。"""
    print("\n--- 综合场景：吉他弦振动 ---")
    src = """
#：{
  T = 80
  mu = 0.006
  L = 0.65
  f1 = 弦管_弦频率(T)(mu)(L)
  f2 = 弦管_弦泛音(T)(mu)(L)(2)
  f3 = 弦管_弦泛音(T)(mu)(L)(3)
  [f1]
  [f2]
  [f3]
}
"""
    out = _call(src)
    f1, f2, f3 = out[0], out[1], out[2]
    v = math.sqrt(80 / 0.006)
    expected_f1 = v / (2 * 0.65)
    assert abs(f1 - expected_f1) < 1e-6
    assert abs(f2 - 2 * expected_f1) < 1e-6
    assert abs(f3 - 3 * expected_f1) < 1e-6
    print(f"  ✓ 吉他弦: f₁={f1:.2f}Hz, f₂={f2:.2f}Hz, f₃={f3:.2f}Hz")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_acoustics_registered_in_interp,
        test_acoustics_registered_in_semantic,
        test_air_sound_speed,
        test_wavelength_frequency,
        test_period_angular_freq_wavenumber,
        test_medium_sound_speed,
        test_sound_intensity_from_pressure,
        test_sound_intensity_level,
        test_sound_pressure_level,
        test_sound_power_level,
        test_intensity_from_power,
        test_decibel_addition,
        test_doppler_observer_moving,
        test_doppler_source_moving,
        test_doppler_general,
        test_mach_number_and_angle,
        test_beat_frequency,
        test_standing_wave,
        test_inverse_square_attenuation,
        test_absorption_attenuation,
        test_pressure_attenuation,
        test_string_vibration,
        test_open_pipe,
        test_closed_pipe,
        test_acoustics_database,
        test_matha_scenario_concert_pitch,
        test_matha_scenario_noise_level,
        test_matha_scenario_ambulance_doppler,
        test_matha_scenario_guitar_string,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个声学测试全部通过 ✓✓✓")
