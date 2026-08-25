"""Matha 流体力学测试：静力学 + 运动学 + 动力学 + 粘性流动。

覆盖：
  1) 流体静力学：静水压强、帕斯卡、浮力、壁面总压力
  2) 流体运动学：圆管面积、体积/质量流量、连续性方程
  3) 流体动力学：伯努利方程、托里拆利、文丘里、皮托管、雷诺数
  4) 粘性流动：牛顿粘性定律、泊肃叶、斯托克斯、终端速度、达西
  5) 流体密度/粘度数据库
  6) Matha 侧综合场景

运行：python -m tests.test_fluid
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.fluid import (
    _fluid_symtab_names, FLUID_DENSITIES, FLUID_VISCOSITIES,
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

def test_fluid_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _fluid_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册: {missing}"
    print(f"  ✓ 共 {len(names)} 个流体力学内建名全部注册")


def test_fluid_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[流体_静水压强(密度_水)(10)(g) + 浮力_浮力(密度_水)(0.001)(g)]"
    ok = _semantic_ok(src)
    assert ok, "引用流体力学内建触发语义错误"
    print("  ✓ 流体力学内建在语义侧可直接引用")


# ============================================================
# 1. 流体静力学
# ============================================================

def test_hydrostatic_pressure():
    print("\n--- 静水压强 ---")
    i = _interp()
    g_val = i.builtins["g"]
    rho_water = i.builtins["密度_水"]
    # p = ρgh: 1000 * 9.8 * 10 = 98000 Pa
    p = i.call("流体_静水压强", rho_water, 10, g_val)
    expected = rho_water * g_val * 10
    assert abs(p - expected) < 1e-6
    # 反求深度
    h_back = i.call("流体_静水深度", p, rho_water, g_val)
    assert abs(h_back - 10) < 1e-6
    print(f"  ✓ p={p:.1f}Pa, h={h_back:.6f}m")


def test_pascal_law():
    print("\n--- 帕斯卡定律（液压机） ---")
    i = _interp()
    # F1=100N, A1=0.001m², A2=0.01m² → F2=1000N（放大10倍）
    F2 = i.call("流体_液压力", 100, 0.001, 0.01)
    assert abs(F2 - 1000) < 1e-6
    print(f"  ✓ F1=100N → F2={F2}N（放大10倍）")


def test_buoyancy():
    print("\n--- 浮力（阿基米德原理） ---")
    i = _interp()
    g_val = i.builtins["g"]
    rho_water = i.builtins["密度_水"]
    # V=0.001m³(1升) 水中 → F_b = 1000*9.8*0.001 = 9.8N
    F_b = i.call("浮力_浮力", rho_water, 0.001, g_val)
    expected = rho_water * g_val * 0.001
    assert abs(F_b - expected) < 1e-6
    # 漂浮判断：木块 500 < 水 1000 → 浮
    assert i.call("浮力_漂浮判断", 500, 1000) == True
    # 铁块 7800 > 水 1000 → 沉
    assert i.call("浮力_漂浮判断", 7800, 1000) == False
    print(f"  ✓ F_b={F_b:.2f}N; 木浮铁沉")


def test_wall_force():
    print("\n--- 矩形壁面静水总压力 ---")
    i = _interp()
    g_val = i.builtins["g"]
    rho_water = i.builtins["密度_水"]
    # h=5m, b=2m → F = ½*1000*9.8*25*2 = 245000N
    F = i.call("流体_壁面总压力", rho_water, 5, 2, g_val)
    expected = 0.5 * rho_water * g_val * 25 * 2
    assert abs(F - expected) < 1e-3
    print(f"  ✓ F={F:.1f}N")


# ============================================================
# 2. 流体运动学
# ============================================================

def test_pipe_area():
    print("\n--- 管道截面积 ---")
    i = _interp()
    # 圆管 D=0.1m → A = π*0.01/4 = 0.007854
    A = i.call("管道_圆管面积", 0.1)
    expected = math.pi * 0.01 / 4
    assert abs(A - expected) < 1e-12
    # 矩形 0.2×0.3 = 0.06
    assert i.call("管道_矩形面积", 0.2, 0.3) == 0.06
    print(f"  ✓ 圆管A={A:.6f}m², 矩形A=0.06m²")


def test_flow_rate():
    print("\n--- 体积/质量流量 ---")
    i = _interp()
    rho_water = i.builtins["密度_水"]
    A, v = 0.01, 2.0
    Q = i.call("流量_体积流量", A, v)         # 0.02 m³/s
    mdot = i.call("流量_质量流量", rho_water, A, v)  # 20 kg/s
    assert abs(Q - 0.02) < 1e-12
    assert abs(mdot - rho_water * 0.02) < 1e-6
    print(f"  ✓ Q={Q}m³/s, ṁ={mdot}kg/s")


def test_continuity():
    print("\n--- 连续性方程 ---")
    i = _interp()
    # A1=0.01, v1=5, A2=0.02 → v2 = 0.01*5/0.02 = 2.5
    v2 = i.call("流量_连续性速度", 0.01, 5, 0.02)
    assert abs(v2 - 2.5) < 1e-12
    # 由流量求流速：Q=0.1, A=0.02 → v=5
    v = i.call("流量_流速", 0.1, 0.02)
    assert abs(v - 5) < 1e-12
    print(f"  ✓ v2={v2}m/s, v={v}m/s")


# ============================================================
# 3. 流体动力学
# ============================================================

def test_torricelli():
    print("\n--- 托里拆利定理（小孔出流） ---")
    i = _interp()
    g_val = i.builtins["g"]
    # v = √(2gh): h=5 → √(2*9.8*5)
    v = i.call("伯努利_小孔流速", 5, g_val)
    expected = math.sqrt(2 * g_val * 5)
    assert abs(v - expected) < 1e-10
    print(f"  ✓ h=5m → v={v:.4f}m/s")


def test_pitot_tube():
    print("\n--- 皮托管测速 ---")
    i = _interp()
    rho_air = i.builtins["密度_空气_20C"]
    # Δp=100Pa, ρ=1.205 → v=√(200/1.205)
    v = i.call("伯努利_皮托管", 100, rho_air)
    expected = math.sqrt(200 / rho_air)
    assert abs(v - expected) < 1e-10
    print(f"  ✓ Δp=100Pa → v={v:.4f}m/s")


def test_venturi():
    print("\n--- 文丘里流量计 ---")
    i = _interp()
    rho_water = i.builtins["密度_水"]
    A1, A2 = 0.01, 0.005
    dp = 5000  # 5kPa 压差
    v1 = i.call("伯努利_文丘里流速", dp, rho_water, A1, A2)
    expected = math.sqrt(2 * dp / (rho_water * (A1**2 / A2**2 - 1)))
    assert abs(v1 - expected) < 1e-10
    print(f"  ✓ Δp=5kPa → v1={v1:.4f}m/s")


def test_reynolds_number():
    print("\n--- 雷诺数与流态 ---")
    i = _interp()
    rho_water = i.builtins["密度_水"]
    mu_water = i.builtins["粘度_水_20C"]
    # 水在 D=0.05m, v=1m/s: Re = 1000*1*0.05/0.001 = 50000 → 湍流
    Re = i.call("流_雷诺数", rho_water, 1, 0.05, mu_water)
    expected = rho_water * 1 * 0.05 / mu_water
    assert abs(Re - expected) < 1e-3
    assert i.call("流_流态判断", Re) == "湍流"
    # 低速层流：v=0.001 → Re≈50
    Re2 = i.call("流_雷诺数", rho_water, 0.001, 0.05, mu_water)
    assert i.call("流_流态判断", Re2) == "层流"
    # 运动粘度形式：ν=1e-6, v=1, D=0.05 → Re=50000
    Re3 = i.call("流_雷诺数运动", 1, 0.05, 1e-6)
    assert abs(Re3 - 50000) < 1e-3
    print(f"  ✓ Re={Re:.0f}(湍流), Re={Re2:.1f}(层流), Re_运动={Re3:.0f}")


def test_bernoulli_pressure():
    print("\n--- 伯努利方程（压强求解） ---")
    i = _interp()
    g_val = i.builtins["g"]
    rho_water = i.builtins["密度_水"]
    # 水平管同一高度，v1=1, v2=4, p1=200000
    # p2 = p1 + ½ρ(v1²-v2²) = 200000 + 500*(1-16) = 192500
    f = i.builtins["伯努利_压强2"]
    p2 = f(200000)(rho_water)(1)(0)(4)(0)(g_val)
    expected = 200000 + 0.5 * rho_water * (1 - 16) + rho_water * g_val * 0
    assert abs(p2 - expected) < 1e-3
    print(f"  ✓ p1=200kPa, v1=1→v2=4 → p2={p2:.1f}Pa（流速增大压强降低）")


# ============================================================
# 4. 粘性流动
# ============================================================

def test_viscous_shear():
    print("\n--- 牛顿粘性定律 ---")
    i = _interp()
    mu = i.builtins["粘度_水_20C"]
    # τ = μ·du/dy: du=0.1, dy=0.001 → τ = μ*100
    tau = i.call("粘_粘性切应力", mu, 0.1, 0.001)
    expected = mu * 100
    assert abs(tau - expected) < 1e-12
    print(f"  ✓ τ={tau:.4f}Pa")


def test_poiseuille():
    print("\n--- 泊肃叶定律（层流管流） ---")
    i = _interp()
    mu = i.builtins["粘度_水_20C"]
    # r=0.01, Δp=1000, L=1 → Q = π*r⁴*Δp/(8*μ*L)
    r, dp, L = 0.01, 1000.0, 1.0
    Q = i.call("粘_泊肃叶流量", r, dp, mu, L)
    expected = math.pi * r**4 * dp / (8 * mu * L)
    assert abs(Q - expected) < 1e-15
    v_avg = i.call("粘_泊肃叶流速", r, dp, mu, L)
    expected_v = r * r * dp / (8 * mu * L)
    assert abs(v_avg - expected_v) < 1e-15
    print(f"  ✓ Q={Q:.6e}m³/s, v_avg={v_avg:.6e}m/s")


def test_stokes_drag():
    print("\n--- 斯托克斯阻力 ---")
    i = _interp()
    eta = i.builtins["粘度_水_20C"]
    # F = 6πηrv: r=0.001, v=0.01
    F = i.call("粘_斯托克斯阻力", eta, 0.001, 0.01)
    expected = 6 * math.pi * eta * 0.001 * 0.01
    assert abs(F - expected) < 1e-15
    print(f"  ✓ F={F:.6e}N")


def test_terminal_velocity():
    print("\n--- 终端沉降速度 ---")
    i = _interp()
    g_val = i.builtins["g"]
    eta = i.builtins["粘度_水_20C"]
    rho_water = i.builtins["密度_水"]
    # 钢球 r=0.001m 在水中：ρs=7850, ρf=1000
    # v_t = 2*r²*g*(7850-1000)/(9*η)
    r, rho_s = 0.001, 7850.0
    v_t = i.call("粘_终端速度", r, g_val, rho_s, rho_water, eta)
    expected = 2 * r * r * g_val * (rho_s - rho_water) / (9 * eta)
    assert abs(v_t - expected) < 1e-10
    print(f"  ✓ 钢球在水中 v_t={v_t:.4f}m/s")


def test_darcy_weisbach():
    print("\n--- 达西-韦斯巴赫水头损失 ---")
    i = _interp()
    g_val = i.builtins["g"]
    # f=0.02, L=100, D=0.1, v=2 → h_f = 0.02*1000*4/(2*9.8)
    h_f = i.call("粘_达西水头损失", 0.02, 100, 0.1, 2, g_val)
    expected = 0.02 * (100 / 0.1) * 4 / (2 * g_val)
    assert abs(h_f - expected) < 1e-10
    print(f"  ✓ h_f={h_f:.4f}m")


# ============================================================
# 5. 流体密度/粘度数据库
# ============================================================

def test_fluid_database():
    print("\n--- 流体密度/粘度数据库 ---")
    i = _interp()
    for name, val in FLUID_DENSITIES.items():
        key = f"密度_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    for name, val in FLUID_VISCOSITIES.items():
        key = f"粘度_{name}"
        assert key in i.builtins
        assert i.builtins[key] == val
    total = len(FLUID_DENSITIES) + len(FLUID_VISCOSITIES)
    print(f"  ✓ {len(FLUID_DENSITIES)} 种密度 + {len(FLUID_VISCOSITIES)} 种粘度 = {total} 个常量全部正确")


# ============================================================
# 6. Matha 侧综合场景
# ============================================================

def test_matha_scenario_tank_drain():
    """综合场景：水箱侧壁小孔出流（托里拆利定理）。"""
    print("\n--- 综合场景：水箱小孔出流 ---")
    src = """
#：{
  h = 5
  g0 = g
  v = 伯努利_小孔流速(h)(g0)
  A = 管道_圆管面积(0.02)
  Q = 流量_体积流量(A)(v)
  [v]
  [Q]
}
"""
    out = _call(src)
    v, Q = out[0], out[1]
    g_val = 9.80665
    expected_v = math.sqrt(2 * g_val * 5)
    expected_Q = math.pi * 0.02**2 / 4 * expected_v
    assert abs(v - expected_v) < 1e-6
    assert abs(Q - expected_Q) < 1e-6
    print(f"  ✓ h=5m, D=2cm → v={v:.4f}m/s, Q={Q:.6f}m³/s")


def test_matha_scenario_pipe_flow():
    """综合场景：圆管水流雷诺数判流态。"""
    print("\n--- 综合场景：圆管水流流态判断 ---")
    src = """
#：{
  rho = 密度_水
  mu = 粘度_水_20C
  D = 0.05
  v = 2
  Re = 流_雷诺数(rho)(v)(D)(mu)
  state = 流_流态判断(Re)
  [Re]
  [state]
}
"""
    out = _call(src)
    Re, state = out[0], out[1]
    assert state == "湍流"
    print(f"  ✓ 水管 D=50mm, v=2m/s → Re={Re:.0f} → {state}")


def test_matha_scenario_buoyancy_ship():
    """综合场景：船的浮力平衡（排水体积计算）。"""
    print("\n--- 综合场景：船的浮力平衡 ---")
    src = """
#：{
  m_ship = 10000
  rho_sea = 密度_海水
  g0 = g
  F_b = 浮力_浮力(rho_sea)(0)(g0)
  V_needed = m_ship / rho_sea
  [V_needed]
}
"""
    out = _call(src)
    V_needed = out[0]
    rho_sea = 1025.0
    expected = 10000 / rho_sea
    assert abs(V_needed - expected) < 1e-6
    print(f"  ✓ 万吨轮 → 需排水 V={V_needed:.2f}m³")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_fluid_registered_in_interp,
        test_fluid_registered_in_semantic,
        test_hydrostatic_pressure,
        test_pascal_law,
        test_buoyancy,
        test_wall_force,
        test_pipe_area,
        test_flow_rate,
        test_continuity,
        test_torricelli,
        test_pitot_tube,
        test_venturi,
        test_reynolds_number,
        test_bernoulli_pressure,
        test_viscous_shear,
        test_poiseuille,
        test_stokes_drag,
        test_terminal_velocity,
        test_darcy_weisbach,
        test_fluid_database,
        test_matha_scenario_tank_drain,
        test_matha_scenario_pipe_flow,
        test_matha_scenario_buoyancy_ship,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个流体力学测试全部通过 ✓✓✓")
