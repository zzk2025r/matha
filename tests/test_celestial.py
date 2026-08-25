"""Matha 天体力学测试：万有引力 + 开普勒定律 + 轨道参数 + 潮汐引力场 + 相对论修正。

覆盖：
  1) 万有引力：引力、势能、加速度、环绕/逃逸速度、第三宇宙速度、圆轨道周期、同步轨道
  2) 开普勒定律：周期、半长轴、椭圆面积/周长、偏心率、近/远地点
  3) 轨道参数：活力公式、角动量、总能量、近/远地点速度、霍曼转移
  4) 潮汐与引力场：潮汐力/加速度、洛希极限、引力势/场强
  5) 相对论修正：史瓦西半径、近日点进动、时间膨胀、引力红移、光线偏折、黑洞温度
  6) 物理常量与太阳系数据库
  7) Matha 侧综合场景

运行：python -m tests.test_celestial
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.celestial import (
    _celestial_symtab_names, G_GRAV, C_LIGHT, AU, LY, PC, SOLAR_SYSTEM,
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

def test_celestial_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _celestial_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个天体力学内建名全部注册")


def test_celestial_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[引力_万有引力(1)(1)(1) + 开普勒_周期(1)(1)]"
    ok = _semantic_ok(src)
    assert ok, "引用天体力学内建触发语义错误"
    print("  ✓ 天体力学内建在语义侧可直接引用")


# ============================================================
# 1. 万有引力与轨道力学
# ============================================================

def test_gravitational_force():
    print("\n--- 万有引力 ---")
    i = _interp()
    F = i.call("引力_万有引力", 5.972e24, 7.342e22, 3.844e8)
    expected = G_GRAV * 5.972e24 * 7.342e22 / 3.844e8 ** 2
    assert abs(F - expected) < 1e10
    print(f"  ✓ 地月引力 F={F:.4e}N")


def test_gravitational_potential_energy():
    print("\n--- 引力势能 ---")
    i = _interp()
    U = i.call("引力_引力势能", 5.972e24, 7.342e22, 3.844e8)
    expected = -G_GRAV * 5.972e24 * 7.342e22 / 3.844e8
    assert abs(U - expected) < 1e10
    print(f"  ✓ 地月引力势能 U={U:.4e}J")


def test_gravitational_acceleration():
    print("\n--- 引力加速度 ---")
    i = _interp()
    g = i.call("引力_引力加速度", 5.972e24, 6.371e6)
    expected = G_GRAV * 5.972e24 / 6.371e6 ** 2
    assert abs(g - expected) < 1e-6
    print(f"  ✓ 地表重力 g={g:.4f}m/s²")


def test_circular_orbital_velocity():
    print("\n--- 环绕速度（第一宇宙速度） ---")
    i = _interp()
    v1 = i.call("引力_环绕速度", 5.972e24, 6.371e6)
    expected = math.sqrt(G_GRAV * 5.972e24 / 6.371e6)
    assert abs(v1 - expected) < 1e-6
    print(f"  ✓ v1={v1:.0f}m/s ({v1/1000:.2f}km/s)")


def test_escape_velocity():
    print("\n--- 逃逸速度（第二宇宙速度） ---")
    i = _interp()
    v2 = i.call("引力_逃逸速度", 5.972e24, 6.371e6)
    expected = math.sqrt(2 * G_GRAV * 5.972e24 / 6.371e6)
    assert abs(v2 - expected) < 1e-6
    print(f"  ✓ v2={v2:.0f}m/s ({v2/1000:.2f}km/s)")


def test_third_cosmic_velocity():
    print("\n--- 第三宇宙速度 ---")
    i = _interp()
    v3 = i.call("引力_第三宇宙速度", 5.972e24, 6.371e6, 1.989e30, 1.496e11)
    v_esc_planet = math.sqrt(2 * G_GRAV * 5.972e24 / 6.371e6)
    v_esc_sun = math.sqrt(2 * G_GRAV * 1.989e30 / 1.496e11)
    expected = math.sqrt(v_esc_planet ** 2 + v_esc_sun ** 2)
    assert abs(v3 - expected) < 1e-3
    print(f"  ✓ v3={v3:.0f}m/s ({v3/1000:.2f}km/s)")


def test_circular_orbit_period():
    print("\n--- 圆轨道周期 ---")
    i = _interp()
    T = i.call("引力_圆轨道周期", 5.972e24, 7e6)  # 600km高度
    expected = 2 * math.pi * math.sqrt(7e6 ** 3 / (G_GRAV * 5.972e24))
    assert abs(T - expected) < 1e-3
    print(f"  ✓ h=600km: T={T:.0f}s ({T/60:.1f}min)")


def test_geosync_radius():
    print("\n--- 同步轨道半径 ---")
    i = _interp()
    T_earth = 86400  # 24h
    r = i.call("引力_同步轨道半径", 5.972e24, T_earth)
    expected = (G_GRAV * 5.972e24 * T_earth ** 2 / (4 * math.pi ** 2)) ** (1.0 / 3)
    assert abs(r - expected) < 1e-3
    print(f"  ✓ 地球同步轨道 r={r/1000:.0f}km")


# ============================================================
# 2. 开普勒定律
# ============================================================

def test_kepler_third_law():
    print("\n--- 开普勒第三定律 ---")
    i = _interp()
    M_sun = 1.989e30
    a_earth = 1.496e11
    T = i.call("开普勒_周期", a_earth, M_sun)
    expected = 2 * math.pi * math.sqrt(a_earth ** 3 / (G_GRAV * M_sun))
    assert abs(T - expected) < 1
    print(f"  ✓ 地球公转 T={T/86400:.1f}天 ({T/3.156e7:.2f}年)")


def test_semi_major_axis_from_period():
    print("\n--- 由周期求半长轴 ---")
    i = _interp()
    M_sun = 1.989e30
    T_earth = 3.156e7
    a = i.call("开普勒_半长轴", M_sun, T_earth)
    expected = (G_GRAV * M_sun * T_earth ** 2 / (4 * math.pi ** 2)) ** (1.0 / 3)
    assert abs(a - expected) < 1e3
    print(f"  ✓ a={a/1e11:.4f}AU")


def test_ellipse_geometry():
    print("\n--- 椭圆几何 ---")
    i = _interp()
    a, b = 1.496e11, 1.495e11
    area = i.call("开普勒_椭圆面积", a, b)
    assert abs(area - math.pi * a * b) < 1e15
    e = i.call("开普勒_偏心率", a, b)
    expected_e = math.sqrt(1 - (b / a) ** 2)
    assert abs(e - expected_e) < 1e-15
    r_p = i.call("开普勒_近地点", a, 0.0167)
    r_a = i.call("开普勒_远地点", a, 0.0167)
    assert abs(r_p - a * (1 - 0.0167)) < 1e-6
    assert abs(r_a - a * (1 + 0.0167)) < 1e-6
    print(f"  ✓ 地球轨道: e={e:.6f}, r_p={r_p/1e9:.2f}Gm, r_a={r_a/1e9:.2f}Gm")


def test_mean_motion():
    print("\n--- 平均运动 ---")
    i = _interp()
    n = i.call("开普勒_平均运动", 3.156e7)
    expected = 2 * math.pi / 3.156e7
    assert abs(n - expected) < 1e-20
    print(f"  ✓ n={n:.4e}rad/s")


# ============================================================
# 3. 轨道参数与活力公式
# ============================================================

def test_vis_viva_equation():
    print("\n--- 活力公式 ---")
    i = _interp()
    M_sun = 1.989e30
    r = 1.471e11  # 地球近日点
    a = 1.496e11  # 半长轴
    v = i.call("轨道_活力速度", M_sun, r, a)
    expected = math.sqrt(G_GRAV * M_sun * (2 / r - 1 / a))
    assert abs(v - expected) < 1e-6
    print(f"  ✓ 地球近日点 v={v:.0f}m/s ({v/1000:.2f}km/s)")


def test_orbital_angular_momentum():
    print("\n--- 轨道角动量 ---")
    i = _interp()
    M_sun = 1.989e30
    m_earth = 5.972e24
    a = 1.496e11
    e = 0.0167
    L = i.call("轨道_角动量", M_sun, m_earth, a, e)
    expected = m_earth * math.sqrt(G_GRAV * M_sun * a * (1 - e ** 2))
    assert abs(L - expected) < 1e15
    print(f"  ✓ 地球轨道角动量 L={L:.4e}kg·m²/s")


def test_orbital_energy():
    print("\n--- 轨道总能量 ---")
    i = _interp()
    E = i.call("轨道_总能量", 1.989e30, 5.972e24, 1.496e11)
    expected = -G_GRAV * 1.989e30 * 5.972e24 / (2 * 1.496e11)
    assert abs(E - expected) < 1e15
    print(f"  ✓ 地球轨道能量 E={E:.4e}J")


def test_periapsis_apoapsis_velocity():
    print("\n--- 近/远地点速度 ---")
    i = _interp()
    M_sun = 1.989e30
    a = 1.496e11
    e = 0.0167
    v_p = i.call("轨道_近地点速度", M_sun, a, e)
    v_a = i.call("轨道_远地点速度", M_sun, a, e)
    expected_vp = math.sqrt(G_GRAV * M_sun * (1 + e) / (a * (1 - e)))
    expected_va = math.sqrt(G_GRAV * M_sun * (1 - e) / (a * (1 + e)))
    assert abs(v_p - expected_vp) < 1e-6
    assert abs(v_a - expected_va) < 1e-6
    print(f"  ✓ v_p={v_p/1000:.2f}km/s, v_a={v_a/1000:.2f}km/s")


def test_hohmann_transfer():
    print("\n--- 霍曼转移 ---")
    i = _interp()
    M_earth = 5.972e24
    r1 = 6.371e6 + 400e3  # 400km LEO
    r2 = 6.371e6 + 35786e3  # GEO
    dv = i.call("轨道_霍曼转移", M_earth, r1, r2)
    a_t = (r1 + r2) / 2
    v1 = math.sqrt(G_GRAV * M_earth / r1)
    v2 = math.sqrt(G_GRAV * M_earth / r2)
    v_tp = math.sqrt(G_GRAV * M_earth * (2 / r1 - 1 / a_t))
    v_ta = math.sqrt(G_GRAV * M_earth * (2 / r2 - 1 / a_t))
    expected_dv = abs(v_tp - v1) + abs(v2 - v_ta)
    assert abs(dv - expected_dv) < 1e-6
    t_transfer = i.call("轨道_霍曼转移时间", M_earth, r1, r2)
    expected_t = math.pi * math.sqrt(a_t ** 3 / (G_GRAV * M_earth))
    assert abs(t_transfer - expected_t) < 1e-3
    print(f"  ✓ LEO→GEO: Δv={dv/1000:.2f}km/s, t={t_transfer/3600:.1f}h")


# ============================================================
# 4. 潮汐与引力场
# ============================================================

def test_tidal_force():
    print("\n--- 潮汐力 ---")
    i = _interp()
    # 月球对地球海洋的潮汐力
    F = i.call("潮汐_潮汐力", 7.342e22, 1000, 1e6, 3.844e8)
    expected = 2 * G_GRAV * 7.342e22 * 1000 * 1e6 / 3.844e8 ** 3
    assert abs(F - expected) < 1e-15
    a_tidal = i.call("潮汐_潮汐加速度", 7.342e22, 1e6, 3.844e8)
    expected_a = 2 * G_GRAV * 7.342e22 * 1e6 / 3.844e8 ** 3
    assert abs(a_tidal - expected_a) < 1e-20
    print(f"  ✓ F={F:.4e}N, a={a_tidal:.4e}m/s²")


def test_roche_limit():
    print("\n--- 洛希极限 ---")
    i = _interp()
    R_earth = 6.371e6
    rho_earth = 5515  # kg/m³
    rho_moon = 3340   # kg/m³
    d_rigid = i.call("潮汐_洛希极限刚体", R_earth, rho_earth, rho_moon)
    expected_rigid = R_earth * (2 * rho_earth / rho_moon) ** (1.0 / 3)
    assert abs(d_rigid - expected_rigid) < 1e-6
    d_fluid = i.call("潮汐_洛希极限流体", R_earth, rho_earth, rho_moon)
    expected_fluid = 2.44 * R_earth * (rho_earth / rho_moon) ** (1.0 / 3)
    assert abs(d_fluid - expected_fluid) < 1e-6
    print(f"  ✓ 刚体: d={d_rigid/1000:.0f}km, 流体: d={d_fluid/1000:.0f}km")


def test_gravitational_potential_field():
    print("\n--- 引力势与引力场强度 ---")
    i = _interp()
    Phi = i.call("潮汐_引力势", 5.972e24, 6.371e6)
    expected_Phi = -G_GRAV * 5.972e24 / 6.371e6
    assert abs(Phi - expected_Phi) < 1
    g = i.call("潮汐_引力场强度", 5.972e24, 6.371e6)
    expected_g = G_GRAV * 5.972e24 / 6.371e6 ** 2
    assert abs(g - expected_g) < 1e-6
    print(f"  ✓ Φ={Phi:.4e}J/kg, g={g:.4f}m/s²")


# ============================================================
# 5. 相对论修正
# ============================================================

def test_schwarzschild_radius():
    print("\n--- 史瓦西半径 ---")
    i = _interp()
    r_s = i.call("相对论_史瓦西半径", 1.989e30)
    expected = 2 * G_GRAV * 1.989e30 / C_LIGHT ** 2
    assert abs(r_s - expected) < 1e-3
    print(f"  ✓ 太阳: r_s={r_s:.1f}m")


def test_mercury_precession():
    print("\n--- 水星近日点进动 ---")
    i = _interp()
    M_sun = 1.989e30
    a_mercury = 5.791e10
    e_mercury = 0.2056
    dphi = i.call("相对论_近日点进动", M_sun, a_mercury, e_mercury)
    expected = 6 * math.pi * G_GRAV * M_sun / (C_LIGHT ** 2 * a_mercury * (1 - e_mercury ** 2))
    assert abs(dphi - expected) < 1e-20
    # 每世纪进动（水星每年约415圈）
    per_century = dphi * 415 * 100
    print(f"  ✓ 每圈 Δφ={dphi:.4e}rad, 每世纪≈{math.degrees(per_century)*3600:.1f}\"")


def test_time_dilation():
    print("\n--- 引力时间膨胀 ---")
    i = _interp()
    # GPS 卫星高度 20200km
    M_earth = 5.972e24
    r_gps = 6.371e6 + 20200e3
    t_prime = i.call("相对论_时间膨胀", 86400, M_earth, r_gps)
    r_s = 2 * G_GRAV * M_earth / C_LIGHT ** 2
    expected = 86400 * math.sqrt(1 - r_s / r_gps)
    assert abs(t_prime - expected) < 1e-15
    print(f"  ✓ GPS高度: 1天→{t_prime:.10f}s (差{86400-t_prime:.2e}s)")


def test_gravitational_redshift():
    print("\n--- 引力红移 ---")
    i = _interp()
    z = i.call("相对论_引力红移", 5.972e24, 6.371e6)
    r_s = 2 * G_GRAV * 5.972e24 / C_LIGHT ** 2
    expected = 1.0 / math.sqrt(1 - r_s / 6.371e6) - 1
    assert abs(z - expected) < 1e-20
    print(f"  ✓ 地表 z={z:.4e}")


def test_light_deflection():
    print("\n--- 光线偏折 ---")
    i = _interp()
    theta = i.call("相对论_光线偏折", 1.989e30, 6.96e8)
    expected = 4 * G_GRAV * 1.989e30 / (C_LIGHT ** 2 * 6.96e8)
    assert abs(theta - expected) < 1e-20
    print(f"  ✓ 太阳边缘 θ={theta:.4e}rad ({math.degrees(theta)*3600:.2f}\")")


def test_black_hole_temperature():
    print("\n--- 黑洞温度（霍金辐射） ---")
    i = _interp()
    T = i.call("相对论_黑洞温度", 1.989e30)
    hbar = 1.054571817e-34
    k_B = 1.380649e-23
    expected = hbar * C_LIGHT ** 3 / (8 * math.pi * G_GRAV * 1.989e30 * k_B)
    assert abs(T - expected) < 1e-30
    print(f"  ✓ 太阳质量黑洞 T={T:.4e}K")


# ============================================================
# 6. 物理常量与太阳系数据库
# ============================================================

def test_celestial_constants():
    print("\n--- 物理常量 ---")
    i = _interp()
    assert i.builtins["G_引力常数"] == G_GRAV
    assert i.builtins["c_光速"] == C_LIGHT
    assert i.builtins["AU_天文单位"] == AU
    assert i.builtins["ly_光年"] == LY
    assert i.builtins["pc_秒差距"] == PC
    print("  ✓ 5 个物理常量全部正确")


def test_solar_system_database():
    print("\n--- 太阳系数据库 ---")
    i = _interp()
    for name, data in SOLAR_SYSTEM.items():
        for key, val in data.items():
            key_name = f"天体_{name}_{key}"
            assert key_name in i.builtins
            assert i.builtins[key_name] == val
    total = sum(len(data) for data in SOLAR_SYSTEM.values())
    print(f"  ✓ {len(SOLAR_SYSTEM)} 个天体 × {total} 个属性全部正确")


# ============================================================
# 7. Matha 侧综合场景
# ============================================================

def test_matha_scenario_earth_orbit():
    """综合场景：地球轨道参数。"""
    print("\n--- 综合场景：地球轨道 ---")
    src = """
#：{
  Msun = 天体_太阳_M
  Mearth = 天体_地球_M
  a = 天体_地球_a
  e = 天体_地球_e
  T = 开普勒_周期(a)(Msun)
  r_p = 开普勒_近地点(a)(e)
  r_a = 开普勒_远地点(a)(e)
  v_p = 轨道_近地点速度(Msun)(a)(e)
  v_a = 轨道_远地点速度(Msun)(a)(e)
  E = 轨道_总能量(Msun)(Mearth)(a)
  [T]
  [r_p]
  [r_a]
  [v_p]
  [v_a]
  [E]
}
"""
    out = _call(src)
    T, r_p, r_a, v_p, v_a, E = out
    M_sun = 1.989e30
    a_earth = 1.496e11
    e_earth = 0.0167
    expected_T = 2 * math.pi * math.sqrt(a_earth ** 3 / (G_GRAV * M_sun))
    assert abs(T - expected_T) < 1
    assert abs(r_p - a_earth * (1 - e_earth)) < 1e-6
    assert abs(r_a - a_earth * (1 + e_earth)) < 1e-6
    expected_vp = math.sqrt(G_GRAV * M_sun * (1 + e_earth) / (a_earth * (1 - e_earth)))
    expected_va = math.sqrt(G_GRAV * M_sun * (1 - e_earth) / (a_earth * (1 + e_earth)))
    assert abs(v_p - expected_vp) < 1e-6
    assert abs(v_a - expected_va) < 1e-6
    expected_E = -G_GRAV * M_sun * 5.972e24 / (2 * a_earth)
    assert abs(E - expected_E) < 1e15
    print(f"  ✓ T={T/3.156e7:.2f}年, v_p={v_p/1000:.2f}km/s, v_a={v_a/1000:.2f}km/s")


def test_matha_scenario_escape_velocity():
    """综合场景：地球与太阳的逃逸速度。"""
    print("\n--- 综合场景：逃逸速度 ---")
    src = """
#：{
  Mearth = 天体_地球_M
  Rearth = 天体_地球_R
  Msun = 天体_太阳_M
  Rorbit = 天体_地球_a
  v1 = 引力_环绕速度(Mearth)(Rearth)
  v2 = 引力_逃逸速度(Mearth)(Rearth)
  v3 = 引力_逃逸速度(Msun)(Rorbit)
  [v1]
  [v2]
  [v3]
}
"""
    out = _call(src)
    v1, v2, v3 = out
    assert abs(v1 - math.sqrt(G_GRAV * 5.972e24 / 6.371e6)) < 1e-6
    assert abs(v2 - math.sqrt(2 * G_GRAV * 5.972e24 / 6.371e6)) < 1e-6
    assert abs(v3 - math.sqrt(2 * G_GRAV * 1.989e30 / 1.496e11)) < 1e-6
    print(f"  ✓ v1={v1/1000:.2f}km/s, v2={v2/1000:.2f}km/s, v3(太阳)={v3/1000:.2f}km/s")


def test_matha_scenario_schwarzschild():
    """综合场景：太阳与地球的史瓦西半径。"""
    print("\n--- 综合场景：史瓦西半径 ---")
    src = """
#：{
  Msun = 天体_太阳_M
  Mearth = 天体_地球_M
  rs_sun = 相对论_史瓦西半径(Msun)
  rs_earth = 相对论_史瓦西半径(Mearth)
  [rs_sun]
  [rs_earth]
}
"""
    out = _call(src)
    rs_sun, rs_earth = out
    expected_sun = 2 * G_GRAV * 1.989e30 / C_LIGHT ** 2
    expected_earth = 2 * G_GRAV * 5.972e24 / C_LIGHT ** 2
    assert abs(rs_sun - expected_sun) < 1e-3
    assert abs(rs_earth - expected_earth) < 1e-6
    print(f"  ✓ 太阳 r_s={rs_sun:.1f}m, 地球 r_s={rs_earth:.3f}m")


def test_matha_scenario_moon_tide():
    """综合场景：月球潮汐力。"""
    print("\n--- 综合场景：月球潮汐 ---")
    src = """
#：{
  Mmoon = 天体_月球_M
  Mearth = 天体_地球_M
  Rearth = 天体_地球_R
  d_moon = 天体_月球_a
  a_tide = 潮汐_潮汐加速度(Mmoon)(Rearth)(d_moon)
  g_earth = 引力_引力加速度(Mearth)(Rearth)
  ratio = a_tide / g_earth
  [a_tide]
  [g_earth]
  [ratio]
}
"""
    out = _call(src)
    a_tide, g_earth, ratio = out
    expected_a = 2 * G_GRAV * 7.342e22 * 6.371e6 / 3.844e8 ** 3
    expected_g = G_GRAV * 5.972e24 / 6.371e6 ** 2
    assert abs(a_tide - expected_a) < 1e-20
    assert abs(g_earth - expected_g) < 1e-6
    assert abs(ratio - expected_a / expected_g) < 1e-15
    print(f"  ✓ a_tide={a_tide:.4e}m/s², g={g_earth:.2f}m/s², 比值={ratio:.2e}")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_celestial_registered_in_interp,
        test_celestial_registered_in_semantic,
        test_gravitational_force,
        test_gravitational_potential_energy,
        test_gravitational_acceleration,
        test_circular_orbital_velocity,
        test_escape_velocity,
        test_third_cosmic_velocity,
        test_circular_orbit_period,
        test_geosync_radius,
        test_kepler_third_law,
        test_semi_major_axis_from_period,
        test_ellipse_geometry,
        test_mean_motion,
        test_vis_viva_equation,
        test_orbital_angular_momentum,
        test_orbital_energy,
        test_periapsis_apoapsis_velocity,
        test_hohmann_transfer,
        test_tidal_force,
        test_roche_limit,
        test_gravitational_potential_field,
        test_schwarzschild_radius,
        test_mercury_precession,
        test_time_dilation,
        test_gravitational_redshift,
        test_light_deflection,
        test_black_hole_temperature,
        test_celestial_constants,
        test_solar_system_database,
        test_matha_scenario_earth_orbit,
        test_matha_scenario_escape_velocity,
        test_matha_scenario_schwarzschild,
        test_matha_scenario_moon_tide,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个天体力学测试全部通过 ✓✓✓")
