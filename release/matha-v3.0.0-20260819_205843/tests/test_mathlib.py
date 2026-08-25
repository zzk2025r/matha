"""数学函数库与领域演化测试。

覆盖四个层次：
  1) 数学常量：pi/e/tau/phi + 物理常量 G/c/g/h_planck/N_A/R
  2) 数学函数：三角/对数/指数/取整/极值/角度换算/符号函数
  3) 运算符扩展：% 取模、!= 不等于、逻辑内建 与/或/非
  4) 领域演化：物理（自由落体/万有引力）、天文（开普勒定律/光行时间）、
              地理（大圆距离）、化学（摩尔数/分子数）

运行：python -m tests.test_mathlib
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret


def _interp() -> Interpreter:
    """已初始化的解释器。"""
    i = Interpreter()
    i.run(parse(""))
    return i


def _call(src: str) -> list:
    """运行 Matha 源码，返回输出列表。"""
    out, _ = interpret(src)
    return out


# ============================================================
# 1) 数学常量
# ============================================================

def test_math_constants():
    """数学常量 pi/e/tau/phi 可用且值正确。"""
    print("\n--- 常量: pi/e/tau/phi ---")
    i = _interp()
    assert i.builtins["pi"] == math.pi
    assert i.builtins["e"] == math.e
    assert i.builtins["tau"] == math.tau
    assert abs(i.builtins["phi"] - 1.618033988749895) < 1e-10
    # Matha 侧可直接引用
    assert _call('#1：[pi]') == [math.pi]
    assert _call('#1：[e]') == [math.e]
    print("  ✓ pi/e/tau/phi 值正确；Matha 侧可引用")


def test_physical_constants():
    """物理常量 G/c/g/h_planck/N_A/R 可用。"""
    print("\n--- 物理常量 ---")
    i = _interp()
    assert i.builtins["G"] == 6.674e-11
    assert i.builtins["c"] == 299792458
    assert i.builtins["g"] == 9.80665
    assert i.builtins["N_A"] == 6.022e23
    assert i.builtins["R"] == 8.314
    # Matha 侧
    assert _call('#1：[c]') == [299792458]
    assert _call('#1：[g]') == [9.80665]
    print("  ✓ G/c/g/N_A/R 值正确；Matha 侧可引用")


# ============================================================
# 2) 数学函数
# ============================================================

def test_trig_functions():
    """三角函数 sin/cos/tan/asin/acos/atan。"""
    print("\n--- 三角函数 ---")
    i = _interp()
    assert i.call("sin", 0) == 0.0
    assert i.call("cos", 0) == 1.0
    assert abs(i.call("sin", math.pi / 2) - 1.0) < 1e-10
    assert abs(i.call("cos", math.pi) + 1.0) < 1e-10
    assert abs(i.call("tan", math.pi / 4) - 1.0) < 1e-10
    assert abs(i.call("asin", 1) - math.pi / 2) < 1e-10
    assert abs(i.call("acos", 1)) < 1e-10
    assert abs(i.call("atan", 1) - math.pi / 4) < 1e-10
    # Matha 侧
    assert _call('#1：[sin(0)]') == [0.0]
    assert _call('#1：[cos(0)]') == [1.0]
    print("  ✓ sin/cos/tan/asin/acos/atan 值正确")


def test_log_exp_functions():
    """对数指数 log/ln/log10/log2/exp/sqrt/pow。"""
    print("\n--- 对数指数 ---")
    i = _interp()
    assert i.call("log", 1) == 0.0
    assert i.call("ln", 1) == 0.0          # ln 别名
    assert i.call("log10", 1000) == 3.0
    assert i.call("log2", 8) == 3.0
    assert i.call("exp", 0) == 1.0
    assert abs(i.call("sqrt", 2) - 1.4142135623730951) < 1e-10
    assert i.call("pow", 2)(3) == 8.0       # 柯里化 pow(2)(3)
    # Matha 侧
    assert _call('#1：[sqrt(9)]') == [3.0]
    assert _call('#1：[log(1)]') == [0.0]
    print("  ✓ log/ln/log10/log2/exp/sqrt/pow 值正确")


def test_rounding_functions():
    """取整 abs/floor/ceil/round/trunc。"""
    print("\n--- 取整 ---")
    i = _interp()
    assert i.call("abs", -5) == 5
    assert i.call("abs", 3.14) == 3.14
    assert i.call("floor", 3.7) == 3
    assert i.call("ceil", 3.2) == 4
    assert i.call("round", 3.5) == 4
    assert i.call("trunc", 3.9) == 3
    # Matha 侧
    assert _call('#1：[abs(-5)]') == [5]
    assert _call('#1：[floor(3.7)]') == [3]
    print("  ✓ abs/floor/ceil/round/trunc 值正确")


def test_min_max_sum():
    """极值统计 min/max/sum（单列表参数，符合柯里化语义）。"""
    print("\n--- 极值统计 ---")
    i = _interp()
    assert i.call("max", [3, 7, 2]) == 7    # 单列表
    assert i.call("min", [3, 7, 2]) == 2
    assert i.call("sum", [1, 2, 3, 4]) == 10
    # Matha 侧：用 append 构造列表
    src = '''
#：{
  表 = append(append(append(空列表)(3))(7))(2)
  [max(表)]
  [min(表)]
  [sum(表)]
}
'''
    assert _call(src) == [7, 2, 12]
    print("  ✓ max/min/sum 单列表；Matha 侧 append 构造列表")


def test_angle_conversion():
    """角度弧度换算 deg2rad/rad2deg。"""
    print("\n--- 角度换算 ---")
    i = _interp()
    assert i.call("deg2rad", 180) == math.pi
    assert i.call("deg2rad", 90) == math.pi / 2
    assert i.call("rad2deg", math.pi) == 180.0
    assert i.call("rad2deg", math.pi / 2) == 90.0
    # Matha 侧
    assert _call('#1：[deg2rad(180)]') == [math.pi]
    print("  ✓ deg2rad(180)=pi; rad2deg(pi)=180")


def test_sign_function():
    """符号函数 sign：正→1, 负→-1, 零→0。"""
    print("\n--- 符号函数 ---")
    i = _interp()
    assert i.call("sign", 5) == 1
    assert i.call("sign", -3) == -1
    assert i.call("sign", 0) == 0
    print("  ✓ sign(5)=1; sign(-3)=-1; sign(0)=0")


def test_hypot_function():
    """斜边长 hypot(a)(b) 柯里化。"""
    print("\n--- 斜边长 ---")
    i = _interp()
    assert i.call("hypot", 3)(4) == 5.0
    assert i.call("hypot", 5)(12) == 13.0
    print("  ✓ hypot(3)(4)=5; hypot(5)(12)=13")


def test_hyperbolic_functions():
    """双曲函数 sinh/cosh/tanh。"""
    print("\n--- 双曲函数 ---")
    i = _interp()
    assert i.call("sinh", 0) == 0.0
    assert i.call("cosh", 0) == 1.0
    assert i.call("tanh", 0) == 0.0
    print("  ✓ sinh(0)=0; cosh(0)=1; tanh(0)=0")


# ============================================================
# 3) 运算符扩展
# ============================================================

def test_modulo_operator():
    """取模运算 % 。"""
    print("\n--- 运算符: % ---")
    assert _call('#1：[10 % 3]') == [1]
    assert _call('#1：[10 % 3]') == [1]      # 无空格
    assert _call('#1：[7 % 2]') == [1]
    assert _call('#1：[20 % 4]') == [0]
    # 浮点取模
    out = _call('#1：[5.5 % 2]')[0]
    assert abs(out - 1.5) < 1e-10
    print("  ✓ 10%3=1; 7%2=1; 20%4=0; 5.5%2=1.5")


def test_not_equal_operator():
    """不等于运算 != 。"""
    print("\n--- 运算符: != ---")
    assert _call('#1：[5 != 3]') == [True]
    assert _call('#1：[5 != 5]') == [False]
    assert _call('#1：[3 != 3.0]') == [False]   # int/float 互通
    assert _call('#1：["a" != "b"]') == [True]
    print("  ✓ 5!=3=True; 5!=5=False; 3!=3.0=False; 'a'!='b'=True")


def test_logic_builtins():
    """逻辑内建 与/或/非（柯里化）。"""
    print("\n--- 逻辑内建 ---")
    assert _call('#1：[与(真)(假)]') == [False]
    assert _call('#1：[与(真)(真)]') == [True]
    assert _call('#1：[或(真)(假)]') == [True]
    assert _call('#1：[或(假)(假)]') == [False]
    assert _call('#1：[非(假)]') == [True]
    assert _call('#1：[非(真)]') == [False]
    print("  ✓ 与(真)(假)=False; 或(真)(假)=True; 非(假)=True")


def test_logic_with_relational():
    """逻辑内建与关系运算组合。"""
    print("\n--- 逻辑+关系 ---")
    src = '''
#：{
  x = 5
  [与(x > 0)(x < 10)]
  [或(x > 10)(x < 0)]
  [非(x = 3)]
}
'''
    assert _call(src) == [True, False, True]
    print("  ✓ 与(x>0)(x<10)=True; 或(x>10)(x<0)=False; 非(x=3)=True")


# ============================================================
# 4) 单位换算
# ============================================================

def test_unit_conversion_length():
    """长度单位换算。"""
    print("\n--- 单位换算: 长度 ---")
    i = _interp()
    assert i.call("换算_千米_米", 1) == 1000
    assert i.call("换算_米_千米", 1000) == 1
    assert i.call("换算_米_厘米", 1) == 100
    assert abs(i.call("换算_英里_米", 1) - 1609.344) < 1e-3
    assert abs(i.call("换算_光年_米", 1) - 9.461e15) < 1e5
    # Matha 侧
    assert _call('#1：[换算_千米_米(1)]') == [1000]
    print("  ✓ 千米→米, 米→千米, 英里→米, 光年→米")


def test_unit_conversion_time():
    """时间单位换算。"""
    print("\n--- 单位换算: 时间 ---")
    i = _interp()
    assert i.call("换算_小时_秒", 1) == 3600
    assert i.call("换算_天_秒", 1) == 86400
    assert abs(i.call("换算_年_秒", 1) - 3.156e7) < 1e3
    print("  ✓ 小时→秒, 天→秒, 年→秒")


def test_unit_conversion_temperature():
    """温度换算（非线性）。"""
    print("\n--- 单位换算: 温度 ---")
    i = _interp()
    assert i.call("换算_摄氏_开尔文", 0) == 273.15
    assert i.call("换算_开尔文_摄氏", 273.15) == 0
    assert i.call("换算_摄氏_华氏", 100) == 212
    assert i.call("换算_华氏_摄氏", 32) == 0
    print("  ✓ 摄氏→开尔文, 开尔文→摄氏, 摄氏→华氏, 华氏→摄氏")


# ============================================================
# 5) 领域演化：物理
# ============================================================

def test_physics_free_fall():
    """物理：自由落体末速度 v = sqrt(2gh)。"""
    print("\n--- 物理: 自由落体 ---")
    src = '''
#：{
  h = 100
  v = sqrt(2 * g * h)
  [v]
}
'''
    out = _call(src)
    expected = math.sqrt(2 * 9.80665 * 100)
    assert abs(out[0] - expected) < 1e-6, out
    print(f"  ✓ v = sqrt(2*g*100) = {out[0]:.2f} m/s")


def test_physics_kinetic_energy():
    """物理：动能 E = 0.5 * m * v^2。"""
    print("\n--- 物理: 动能 ---")
    src = '''
#：{
  m = 2
  v = 10
  E = 0.5 * m * v^2
  [E]
}
'''
    assert _call(src) == [100.0]
    print("  ✓ E = 0.5 * 2 * 10^2 = 100")


def test_physics_gravitation():
    """物理：万有引力 F = G * m1 * m2 / r^2。"""
    print("\n--- 物理: 万有引力 ---")
    src = '''
#：{
  m1 = 1000
  m2 = 2000
  r = 10
  F = G * m1 * m2 / r^2
  [F]
}
'''
    out = _call(src)
    expected = 6.674e-11 * 1000 * 2000 / 100
    assert abs(out[0] - expected) < 1e-15, out
    print(f"  ✓ F = G*1000*2000/100 = {out[0]:.2e} N")


# ============================================================
# 6) 领域演化：天文
# ============================================================

def test_astronomy_kepler_law():
    """天文：开普勒第三定律 T = 2*pi*sqrt(r^3/GM)。"""
    print("\n--- 天文: 开普勒定律 ---")
    src = '''
#：{
  r = 149600000000
  M = 1989000000000000000000000000000
  T = 2 * pi * sqrt(r^3 / (G * M))
  [T]
  [换算_秒_年(T)]
}
'''
    out = _call(src)
    # 地球轨道周期应约 1 年
    assert 3.0e7 < out[0] < 3.3e7, out      # 秒数
    assert 0.95 < out[1] < 1.05, out         # 年数
    print(f"  ✓ T ≈ {out[0]:.0f} 秒 ≈ {out[1]:.2f} 年")


def test_astronomy_light_travel_time():
    """天文：光行时间 t = d / c。"""
    print("\n--- 天文: 光行时间 ---")
    src = '''
#：{
  d = 149600000000
  t = d / c
  [t]
  [换算_秒_小时(t)]
}
'''
    out = _call(src)
    expected = 149600000000 / 299792458
    assert abs(out[0] - expected) < 1, out
    assert abs(out[1] - expected / 3600) < 0.01, out
    print(f"  ✓ 太阳光行 t = {out[0]:.0f} 秒 ≈ {out[1]:.1f} 小时")


def test_astronomy_orbital_velocity():
    """天文：轨道速度 v = sqrt(GM/r)。"""
    print("\n--- 天文: 轨道速度 ---")
    src = '''
#：{
  r = 149600000000
  M = 1989000000000000000000000000000
  v = sqrt(G * M / r)
  [v]
}
'''
    out = _call(src)
    # 地球公转速度约 29.8 km/s = 29800 m/s
    assert 29000 < out[0] < 31000, out
    print(f"  ✓ 地球公转速度 v ≈ {out[0]:.0f} m/s")


# ============================================================
# 7) 领域演化：地理
# ============================================================

def test_geography_great_circle_distance():
    """地理：大圆距离（Haversine 公式）。"""
    print("\n--- 地理: 大圆距离 ---")
    src = '''
#：{
  lat1 = deg2rad(39.9)
  lon1 = deg2rad(116.4)
  lat2 = deg2rad(34.05)
  lon2 = deg2rad(-118.25)
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = sin(dlat/2)^2 + cos(lat1) * cos(lat2) * sin(dlon/2)^2
  c = 2 * atan2(sqrt(a))(sqrt(1-a))
  d = 6371 * c
  [d]
}
'''
    out = _call(src)
    # 北京↔洛杉矶 约 10000-10500 km
    assert 9500 < out[0] < 10500, out
    print(f"  ✓ 北京↔洛杉矶 大圆距离 = {out[0]:.0f} km")


def test_geography_time_zone_difference():
    """地理：时区差计算（经度/15）。"""
    print("\n--- 地理: 时区差 ---")
    src = '''
#：{
  经度_北京 = 116.4
  经度_洛杉矶 = -118.25
  时差 = (经度_北京 - 经度_洛杉矶) / 15
  [时差]
  [换算_小时_秒(时差)]
}
'''
    out = _call(src)
    expected = (116.4 - (-118.25)) / 15
    assert abs(out[0] - expected) < 1e-6, out
    assert abs(out[1] - expected * 3600) < 1e-3, out
    print(f"  ✓ 时差 = {out[0]:.1f} 小时 = {out[1]:.0f} 秒")


# ============================================================
# 8) 领域演化：化学
# ============================================================

def test_chemistry_moles():
    """化学：摩尔数 n = m / M。"""
    print("\n--- 化学: 摩尔数 ---")
    src = '''
#：{
  m = 18
  M = 18.015
  n = m / M
  [n]
}
'''
    out = _call(src)
    assert abs(out[0] - 0.99916) < 1e-3, out
    print(f"  ✓ 18g 水 n = {out[0]:.4f} mol")


def test_chemistry_molecule_count():
    """化学：分子数 = n * N_A。"""
    print("\n--- 化学: 分子数 ---")
    src = '''
#：{
  m = 36
  M = 18.015
  n = m / M
  分子数 = n * 602200000000000000000000
  [分子数]
}
'''
    out = _call(src)
    expected = 36 / 18.015 * 6.022e23
    assert abs(out[0] - expected) < 1e20, out
    print(f"  ✓ 36g 水分子数 = {out[0]:.3e}")


def test_chemistry_ideal_gas_law():
    """化学：理想气体状态方程 PV = nRT。"""
    print("\n--- 化学: 理想气体 ---")
    src = '''
#：{
  n = 1
  T = 273
  P = 101325
  V = (n * R * T) / P
  [V]
}
'''
    out = _call(src)
    expected = 1 * 8.314 * 273 / 101325
    assert abs(out[0] - expected) < 1e-6, out
    print(f"  ✓ 1mol 273K 101325Pa → V = {out[0]:.4f} m³")


# ============================================================
# 9) 领域配合：物理 + 天文 + 数学
# ============================================================

def test_cross_domain_escape_velocity():
    """跨领域：逃逸速度 v = sqrt(2GM/r)（物理+天文）。"""
    print("\n--- 跨领域: 逃逸速度 ---")
    src = '''
#：{
  M = 5972000000000000000000000
  r = 6371000
  v = sqrt(2 * G * M / r)
  [v]
}
'''
    out = _call(src)
    # 地球逃逸速度约 11186 m/s
    assert 11000 < out[0] < 11500, out
    print(f"  ✓ 地球逃逸速度 v ≈ {out[0]:.0f} m/s")


def test_cross_domain_stellar_distance():
    """跨领域：恒星距离（视差法）d = 1/parallax（天文+地理+数学）。"""
    print("\n--- 跨领域: 视差测距 ---")
    src = '''
#：{
  parallax_arcsec = 0.1
  d_parsec = 1 / parallax_arcsec
  d_ly = d_parsec * 3.262
  [d_parsec]
  [d_ly]
}
'''
    out = _call(src)
    assert out[0] == 10.0          # 10 秒差距
    assert abs(out[1] - 32.62) < 0.01  # ≈ 32.62 光年
    print(f"  ✓ 视差 0.1 角秒 → {out[0]} pc ≈ {out[1]} 光年")


# ============================================================
# runner
# ============================================================

def _run_all():
    tests = [
        # 常量
        test_math_constants,
        test_physical_constants,
        # 数学函数
        test_trig_functions,
        test_log_exp_functions,
        test_rounding_functions,
        test_min_max_sum,
        test_angle_conversion,
        test_sign_function,
        test_hypot_function,
        test_hyperbolic_functions,
        # 运算符
        test_modulo_operator,
        test_not_equal_operator,
        test_logic_builtins,
        test_logic_with_relational,
        # 单位换算
        test_unit_conversion_length,
        test_unit_conversion_time,
        test_unit_conversion_temperature,
        # 物理
        test_physics_free_fall,
        test_physics_kinetic_energy,
        test_physics_gravitation,
        # 天文
        test_astronomy_kepler_law,
        test_astronomy_light_travel_time,
        test_astronomy_orbital_velocity,
        # 地理
        test_geography_great_circle_distance,
        test_geography_time_zone_difference,
        # 化学
        test_chemistry_moles,
        test_chemistry_molecule_count,
        test_chemistry_ideal_gas_law,
        # 跨领域
        test_cross_domain_escape_velocity,
        test_cross_domain_stellar_distance,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except (AssertionError, Exception) as ex:
            failed += 1
            print(f"  ✗ {t.__name__} 失败: {type(ex).__name__}: {ex}")
            import traceback
            traceback.print_exc()
    print(f"\n{'='*52}")
    print(f"数学函数库与领域演化测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
