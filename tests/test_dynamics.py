"""Matha 动力学测试：牛顿定律 + 动量 + 功与能 + 转动 + 振动。

覆盖：
  1) 牛顿运动定律：F=ma、摩擦力、合力
  2) 动量定理：动量、冲量、动量守恒、弹性碰撞、恢复系数
  3) 功与能：功、功率、动能、势能、动能定理、机械能守恒
  4) 转动动力学：力矩、转动惯量、转动定律、角动量、转动动能
  5) 机械振动：简谐振动、单摆、复摆、阻尼振动
  6) Matha 侧综合场景

运行：python -m tests.test_dynamics
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.dynamics import _dynamics_symtab_names


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

def test_dynamics_registered_in_interp():
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _dynamics_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册到 interp.builtins: {missing}"
    print(f"  ✓ 共 {len(names)} 个动力学内建名全部注册")


def test_dynamics_registered_in_semantic():
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[力_牛顿力(10)(2) + 能量_动能(1)(5)]"
    ok = _semantic_ok(src)
    assert ok, "引用动力学内建触发语义错误"
    print("  ✓ 动力学内建在语义侧可直接引用")


# ============================================================
# 1. 牛顿运动定律
# ============================================================

def test_newton_second_law():
    print("\n--- 牛顿第二定律 ---")
    i = _interp()
    assert i.call("力_牛顿力", 10, 2) == 20.0       # F=ma: 10kg×2m/s²=20N
    assert i.call("力_加速度", 50, 10) == 5.0       # a=F/m: 50N/10kg=5m/s²
    assert i.call("力_质量", 100, 10) == 10.0        # m=F/a: 100N/10m/s²=10kg
    # Matha 侧
    assert _call('#1：[力_牛顿力(5)(3)]') == [15.0]
    print("  ✓ F=ma / a=F/m / m=F/a 三算正确")


def test_friction():
    print("\n--- 摩擦力 ---")
    i = _interp()
    # μ=0.3, N=100N → f=30N
    assert i.call("力_滑动摩擦力", 0.3, 100) == 30.0
    assert i.call("力_最大静摩擦", 0.4, 200) == 80.0
    print("  ✓ 滑动摩擦力 f=μN / 最大静摩擦 f_max=μ_s·N 正确")


def test_resultant_force():
    print("\n--- 合力 ---")
    i = _interp()
    assert i.call("力_合力同向", 30, 40) == 70.0
    # 垂直 3N + 4N → 5N（勾股）
    assert abs(i.call("力_合力垂直", 3, 4) - 5.0) < 1e-10
    print("  ✓ 同向合力 70N / 垂直合力 5N (3-4-5) 正确")


# ============================================================
# 2. 动量定理
# ============================================================

def test_momentum():
    print("\n--- 动量与冲量 ---")
    i = _interp()
    assert i.call("动量_动量", 2, 5) == 10.0         # p=mv: 2kg×5m/s=10
    assert i.call("动量_冲量", 20, 3) == 60.0        # I=Ft: 20N×3s=60
    # 末动量 p2 = p1 + Ft = 10 + 20*3 = 70
    assert i.call("动量_末动量", 10, 20, 3) == 70.0
    print("  ✓ p=mv / I=Ft / p2=p1+Ft 正确")


def test_momentum_conservation():
    print("\n--- 动量守恒（两体碰撞） ---")
    i = _interp()
    # m1=2kg, v1=3m/s, m2=1kg, v2=0, v2'=2m/s → v1'=(2*3+1*0-1*2)/2=2
    # 动量_碰后速度1(m1)(v1)(m2)(v2)(v2') = 5参柯里化
    f = i.builtins["动量_碰后速度1"]
    v1_after = f(2)(3)(1)(0)(2)
    assert abs(v1_after - 2.0) < 1e-10
    print(f"  ✓ m1=2,v1=3,m2=1,v2=0,v2'=2 → v1'={v1_after}")


def test_elastic_collision():
    print("\n--- 完全弹性碰撞 ---")
    i = _interp()
    # 等质量正碰：m1=m2 → v1'=v2, v2'=v1（速度交换）
    m1, v1, m2, v2 = 1.0, 5.0, 1.0, 0.0
    v1a = i.call("弹性碰撞_速度1", m1, v1, m2, v2)
    v2a = i.call("弹性碰撞_速度2", m1, v1, m2, v2)
    assert abs(v1a - 0.0) < 1e-10   # 速度交换
    assert abs(v2a - 5.0) < 1e-10
    print(f"  ✓ 等质量正碰：v1={v1}→{v1a}, v2={v2}→{v2a}（速度交换）")

    # 不等质量：m1=2, v1=4, m2=1, v2=-2
    v1b = i.call("弹性碰撞_速度1", 2, 4, 1, -2)
    v2b = i.call("弹性碰撞_速度2", 2, 4, 1, -2)
    # 动量守恒验算
    p_before = 2 * 4 + 1 * (-2)
    p_after = 2 * v1b + 1 * v2b
    assert abs(p_before - p_after) < 1e-10
    # 动能守恒验算
    ke_before = 0.5 * 2 * 16 + 0.5 * 1 * 4
    ke_after = 0.5 * 2 * v1b ** 2 + 0.5 * 1 * v2b ** 2
    assert abs(ke_before - ke_after) < 1e-9
    print(f"  ✓ 不等质量碰撞：动量守恒({p_before}={p_after}), 动能守恒({ke_before}={ke_after:.4f})")


def test_restitution_coefficient():
    print("\n--- 恢复系数 ---")
    i = _interp()
    # 完全弹性 e=1: v1=5,v2=0,v1'=0,v2'=5
    e = i.call("碰撞_恢复系数", 5, 0, 0, 5)
    assert abs(e - 1.0) < 1e-10
    # 完全非弹性 e=0: v1=5,v2=0,v1'=v2'=2.5（粘在一起）
    e2 = i.call("碰撞_恢复系数", 5, 0, 2.5, 2.5)
    assert abs(e2 - 0.0) < 1e-10
    print(f"  ✓ 弹性碰撞 e=1.0, 完全非弹性 e=0.0")


# ============================================================
# 3. 功与能
# ============================================================

def test_work_and_power():
    print("\n--- 功与功率 ---")
    i = _interp()
    # W = Fs cosθ: F=10N, s=5m, θ=0° → W=50J
    assert i.call("功_功", 10, 5, 0) == 50.0
    # F=10N, s=5m, θ=60° → W=10*5*0.5=25J
    assert abs(i.call("功_功", 10, 5, math.pi / 3) - 25.0) < 1e-10
    # P = W/t: 50J/5s = 10W
    assert i.call("功_功率", 50, 5) == 10.0
    # P = Fv: 20N × 3m/s = 60W
    assert i.call("功_功率力速", 20, 3) == 60.0
    print("  ✓ W=Fscosθ / P=W/t / P=Fv 正确")


def test_kinetic_and_potential_energy():
    print("\n--- 动能与势能 ---")
    i = _interp()
    g_val = i.builtins["g"]
    # E_k = ½mv²: m=2, v=3 → 9J
    assert i.call("能量_动能", 2, 3) == 9.0
    # E_p = mgh: m=1, h=10, g → m*g*10
    assert abs(i.call("能量_重力势能", 1, 10, g_val) - 10 * g_val) < 1e-10
    # E_s = ½kx²: k=100, x=0.1 → 0.5J
    assert i.call("能量_弹性势能", 100, 0.1) == 0.5
    print("  ✓ E_k=½mv² / E_p=mgh / E_s=½kx² 正确")


def test_work_energy_theorem():
    print("\n--- 动能定理 ---")
    i = _interp()
    # m=2, v1=3, v2=5 → W = ½*2*25 - ½*2*9 = 25-9=16J
    assert i.call("能量_动能定理", 2, 3, 5) == 16.0
    print("  ✓ W = ΔE_k = ½mv₂² - ½mv₁² = 16J 正确")


def test_mechanical_energy_conservation():
    print("\n--- 机械能守恒 ---")
    i = _interp()
    g_val = i.builtins["g"]
    # v1=0, h1=10, h2=0 → v2 = √(2g*10)
    v2 = i.call("能量_守恒末速度", 0, 10, 0, g_val)
    expected = math.sqrt(2 * g_val * 10)
    assert abs(v2 - expected) < 1e-10
    print(f"  ✓ 自由下落 h=10m → v2={v2:.4f}m/s = √(2gh)={expected:.4f}")


# ============================================================
# 4. 转动动力学
# ============================================================

def test_torque():
    print("\n--- 力矩 ---")
    i = _interp()
    # M = rF sinθ: r=2, F=5, θ=90° → M=10
    assert abs(i.call("转动_力矩", 2, 5, math.pi / 2) - 10.0) < 1e-10
    # r=2, F=5, θ=0° → M=0（同向无力矩）
    assert i.call("转动_力矩", 2, 5, 0) == 0.0
    print("  ✓ M=rF sinθ: 90°→10N·m, 0°→0 正确")


def test_rotational_law():
    print("\n--- 转动定律 ---")
    i = _interp()
    # α = M/I: M=10, I=2 → α=5 rad/s²
    assert i.call("转动_角加速度", 10, 2) == 5.0
    print("  ✓ α=M/I=5 rad/s² 正确")


def test_moment_of_inertia():
    print("\n--- 转动惯量 ---")
    i = _interp()
    m, r = 1.0, 0.5
    # 质点 I=mr² = 0.25
    assert i.call("转动惯量_质点", m, r) == 0.25
    # 圆盘 I=½mr² = 0.125
    assert i.call("转动惯量_圆盘", m, r) == 0.125
    # 圆环 I=mr² = 0.25
    assert i.call("转动惯量_圆环", m, r) == 0.25
    # 实心球 I=⅖mr² = 0.1
    assert abs(i.call("转动惯量_实心球", m, r) - 2 * m * r * r / 5) < 1e-10
    # 细杆中心 I=⅟₁₂mL²: m=1, L=2 → 1/3
    assert abs(i.call("转动惯量_细杆中心", 1, 2) - 1.0 / 3) < 1e-10
    # 细杆端点 I=⅓mL²: m=1, L=2 → 4/3
    assert abs(i.call("转动惯量_细杆端点", 1, 2) - 4.0 / 3) < 1e-10
    print("  ✓ 质点/圆盘/圆环/实心球/细杆 转动惯量全部正确")


def test_parallel_axis():
    print("\n--- 平行轴定理 ---")
    i = _interp()
    # I_cm=0.125(圆盘), m=1, d=0.3 → I=0.125+1*0.09=0.215
    I_cm = 0.125
    result = i.call("转动惯量_平行轴", I_cm, 1, 0.3)
    expected = I_cm + 1 * 0.3 ** 2
    assert abs(result - expected) < 1e-10
    print(f"  ✓ I = I_cm + md² = {result}")


def test_angular_momentum():
    print("\n--- 角动量与角动量守恒 ---")
    i = _interp()
    # L = Iω: I=2, ω=3 → L=6
    assert i.call("转动_角动量", 2, 3) == 6.0
    # 角动量守恒：I1=2, ω1=3, I2=4 → ω2=6/4=1.5
    assert i.call("转动_角动量守恒", 2, 3, 4) == 1.5
    print("  ✓ L=Iω=6 / ω2=I1ω1/I2=1.5 正确")


def test_rotational_kinetic_energy():
    print("\n--- 转动动能 ---")
    i = _interp()
    # E_rot = ½Iω²: I=2, ω=3 → 9J
    assert i.call("转动_转动动能", 2, 3) == 9.0
    print("  ✓ E_rot = ½Iω² = 9J 正确")


# ============================================================
# 5. 机械振动
# ============================================================

def test_shm_period():
    print("\n--- 简谐振动周期 ---")
    i = _interp()
    # T = 2π√(m/k): m=1, k=4 → T=2π*0.5=π
    T = i.call("振动_周期", 1, 4)
    assert abs(T - math.pi) < 1e-10
    # f = 1/T
    f = i.call("振动_频率", T)
    assert abs(f - 1 / math.pi) < 1e-10
    # ω = 2π/T
    omega = i.call("振动_角频率", T)
    assert abs(omega - 2) < 1e-10  # ω = 2π/π = 2
    print(f"  ✓ m=1,k=4: T={T:.4f}s, f={f:.4f}Hz, ω={omega:.4f}rad/s")


def test_shm_displacement():
    print("\n--- 简谐振动位移与速度 ---")
    i = _interp()
    A, omega = 0.1, 2.0
    # t=0: x=A cos(0)=A, v=-Aω sin(0)=0
    assert abs(i.call("振动_位移", A, omega, 0) - A) < 1e-10
    assert i.call("振动_速度", A, omega, 0) == 0.0
    # t=π/(2ω): x=0, v=-Aω
    t_quarter = math.pi / (2 * omega)
    assert abs(i.call("振动_位移", A, omega, t_quarter)) < 1e-10
    assert abs(i.call("振动_速度", A, omega, t_quarter) - (-A * omega)) < 1e-10
    print(f"  ✓ t=0: x=A={A}, v=0; t=π/2ω: x=0, v=-Aω={-A*omega}")


def test_shm_energy():
    print("\n--- 简谐振动总能量 ---")
    i = _interp()
    # E = ½kA²: k=100, A=0.05 → 0.125J
    assert i.call("振动_总能量", 100, 0.05) == 0.125
    print("  ✓ E=½kA²=0.125J 正确")


def test_pendulum():
    print("\n--- 单摆周期 ---")
    i = _interp()
    g_val = i.builtins["g"]
    L = 1.0
    T = i.call("振动_单摆周期", L, g_val)
    expected = 2 * math.pi * math.sqrt(L / g_val)
    assert abs(T - expected) < 1e-10
    print(f"  ✓ L=1m: T={T:.4f}s = 2π√(L/g)={expected:.4f}")


def test_physical_pendulum():
    print("\n--- 复摆周期 ---")
    i = _interp()
    g_val = i.builtins["g"]
    # I=0.2, m=1, d=0.5 → T=2π√(0.2/(1*g*0.5))
    T = i.call("振动_复摆周期", 0.2, 1, g_val, 0.5)
    expected = 2 * math.pi * math.sqrt(0.2 / (1 * g_val * 0.5))
    assert abs(T - expected) < 1e-10
    print(f"  ✓ I=0.2,m=1,d=0.5: T={T:.4f}s 正确")


def test_damped_oscillation():
    print("\n--- 阻尼振动角频率 ---")
    i = _interp()
    # ω_d = √(ω₀² - β²): ω₀=5, β=3 → √(25-9)=4
    assert i.call("振动_阻尼角频率", 5, 3) == 4.0
    print("  ✓ ω_d=√(25-9)=4 rad/s 正确")


# ============================================================
# 6. Matha 侧综合场景
# ============================================================

def test_matha_scenario_collision():
    """综合场景：两球弹性碰撞，验证动量+动能守恒。"""
    print("\n--- 综合场景：弹性碰撞 ---")
    src = """
#：{
  m1 = 2
  v1 = 4
  m2 = 1
  v2 = 0
  v1a = 弹性碰撞_速度1(m1)(v1)(m2)(v2)
  v2a = 弹性碰撞_速度2(m1)(v1)(m2)(v2)
  [v1a]
  [v2a]
}
"""
    out = _call(src)
    v1a, v2a = out[0], out[1]
    # m1=2,v1=4,m2=1,v2=0 → v1'=4/3, v2'=16/3
    assert abs(v1a - 4.0 / 3) < 1e-10
    assert abs(v2a - 16.0 / 3) < 1e-10
    print(f"  ✓ v1'={v1a:.4f}, v2'={v2a:.4f}")


def test_matha_scenario_energy_slide():
    """综合场景：物体从光滑斜面滑下，用机械能守恒求末速度。"""
    print("\n--- 综合场景：机械能守恒求末速度 ---")
    src = """
#：{
  h = 5
  g0 = g
  v = 能量_守恒末速度(0)(h)(0)(g0)
  [v]
}
"""
    out = _call(src)
    v = out[0]
    expected = math.sqrt(2 * 9.80665 * 5)
    assert abs(v - expected) < 1e-6
    print(f"  ✓ h=5m, v0=0 → v={v:.4f}m/s = √(2gh)={expected:.4f}")


def test_matha_scenario_rotating_disk():
    """综合场景：圆盘转动惯量 + 角动量守恒。"""
    print("\n--- 综合场景：旋转圆盘角动量守恒 ---")
    src = """
#：{
  m = 2
  r = 0.5
  I = 转动惯量_圆盘(m)(r)
  omega1 = 10
  I2 = 转动惯量_圆盘(4)(r)
  omega2 = 转动_角动量守恒(I)(omega1)(I2)
  E1 = 转动_转动动能(I)(omega1)
  E2 = 转动_转动动能(I2)(omega2)
  [omega2]
  [E1]
  [E2]
}
"""
    out = _call(src)
    omega2, E1, E2 = out[0], out[1], out[2]
    # I1=½*2*0.25=0.25, I2=½*4*0.25=0.5
    # ω2 = 0.25*10/0.5 = 5
    assert abs(omega2 - 5.0) < 1e-10
    # E1 = ½*0.25*100 = 12.5
    assert abs(E1 - 12.5) < 1e-10
    # E2 = ½*0.5*25 = 6.25
    assert abs(E2 - 6.25) < 1e-10
    print(f"  ✓ ω2={omega2}, E1={E1}, E2={E2}（转动后动能减少，角动量守恒）")


def test_matha_scenario_spring():
    """综合场景：弹簧振子振动周期 + 总能量。"""
    print("\n--- 综合场景：弹簧振子 ---")
    src = """
#：{
  m = 0.5
  k = 50
  A = 0.1
  T = 振动_周期(m)(k)
  f = 振动_频率(T)
  E = 振动_总能量(k)(A)
  [T]
  [f]
  [E]
}
"""
    out = _call(src)
    T, f, E = out[0], out[1], out[2]
    expected_T = 2 * math.pi * math.sqrt(0.5 / 50)
    assert abs(T - expected_T) < 1e-10
    assert abs(f - 1 / expected_T) < 1e-10
    assert abs(E - 0.5 * 50 * 0.01) < 1e-10
    print(f"  ✓ m=0.5kg,k=50N/m,A=0.1m: T={T:.4f}s, f={f:.4f}Hz, E={E}J")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    tests = [
        test_dynamics_registered_in_interp,
        test_dynamics_registered_in_semantic,
        test_newton_second_law,
        test_friction,
        test_resultant_force,
        test_momentum,
        test_momentum_conservation,
        test_elastic_collision,
        test_restitution_coefficient,
        test_work_and_power,
        test_kinetic_and_potential_energy,
        test_work_energy_theorem,
        test_mechanical_energy_conservation,
        test_torque,
        test_rotational_law,
        test_moment_of_inertia,
        test_parallel_axis,
        test_angular_momentum,
        test_rotational_kinetic_energy,
        test_shm_period,
        test_shm_displacement,
        test_shm_energy,
        test_pendulum,
        test_physical_pendulum,
        test_damped_oscillation,
        test_matha_scenario_collision,
        test_matha_scenario_energy_slide,
        test_matha_scenario_rotating_disk,
        test_matha_scenario_spring,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个动力学测试全部通过 ✓✓✓")
