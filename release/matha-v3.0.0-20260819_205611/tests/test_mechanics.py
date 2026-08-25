"""Matha 机械领域测试：运动学 + 材料力学。

覆盖：
  1) 运动学：匀速/匀变速/自由落体/平抛/斜抛/圆周
  2) 材料力学：轴向拉压/剪切/梁弯曲/圆轴扭转
  3) 材料属性数据库：7 种材质的 E/G/σ_s/σ_b/ρ/ν
  4) Matha 侧直接调用：语法 + 语义无报错

运行：python -m pytest tests/test_mechanics.py -v
或  : python -m tests.test_mechanics
"""

import math
from src.parser import parse
from src.interp import Interpreter, interpret
from src.semantic import SemanticAnalyzer
from src.domains.mechanics import MATERIALS, _mechanics_symtab_names


def _interp() -> Interpreter:
    i = Interpreter()
    i.run(parse(""))
    return i


def _call(src: str) -> list:
    out, _ = interpret(src)
    return out


def _semantic_ok(src: str) -> bool:
    """运行语义分析，返回是否无错误（警告可接受）。"""
    prog = parse(src)
    ana = SemanticAnalyzer()
    ana.analyze(prog)
    return not any(e.severity == "error" for e in ana.errors)


# ============================================================
# 0. 注册性测试：确保 interp / semantic 接入成功
# ============================================================

def test_mechanics_registered_in_interp():
    """Interpreter 初始化后，机械领域内建都存在。"""
    print("\n--- 注册性：内建名注册 ---")
    i = _interp()
    names = _mechanics_symtab_names()
    missing = [n for n in names if n not in i.builtins]
    assert missing == [], f"以下内建未注册到 interp.builtins: {missing}"
    print(f"  ✓ 共 {len(names)} 个机械内建名全部注册")


def test_mechanics_registered_in_semantic():
    """SemanticAnalyzer 初始化后，机械内建符号在符号表中，
       Matha 代码引用不会报「未定义变量」。"""
    print("\n--- 注册性：语义符号表 ---")
    src = "#1：[运动_匀速位移(10)(2) + 材料_应力(1000)(0.01)]"
    ok = _semantic_ok(src)
    assert ok, "引用机械内建触发语义错误（未定义变量？）"
    print("  ✓ 机械内建在语义侧可直接引用，无未定义报错")


# ============================================================
# 1. 运动学 - 匀速直线
# ============================================================

def test_kinematics_uniform_motion():
    """匀速直线：s=vt；v=s/t；t=s/v。"""
    print("\n--- 运动学：匀速直线 ---")
    i = _interp()
    # Python 侧
    assert i.call("运动_匀速位移", 10, 5) == 50.0       # 10m/s × 5s = 50m
    assert i.call("运动_匀速速度", 100, 20) == 5.0      # 100m / 20s = 5m/s
    assert i.call("运动_匀速时间", 120, 30) == 4.0      # 120m / 30m/s = 4s
    # Matha 侧
    assert _call('#1：[运动_匀速位移(20)(3)]') == [60.0]
    print("  ✓ 匀速位移/速度/时间 三算正确")


# ============================================================
# 2. 运动学 - 匀变速直线
# ============================================================

def test_kinematics_uniform_accel():
    """匀变速：s=v0t+½at²；v=v0+at；v²-v0²=2as。"""
    print("\n--- 运动学：匀变速直线 ---")
    i = _interp()
    # v0=0, a=2m/s², t=5s: s=25m, v=10m/s
    s = i.call("运动_匀变速位移", 0, 2, 5)
    v = i.call("运动_匀变速末速度", 0, 2, 5)
    assert abs(s - 25.0) < 1e-10
    assert abs(v - 10.0) < 1e-10
    # 由速度算位移：v=10, v0=0, a=2 → s=25
    s2 = i.call("运动_匀变速位移由速度", 0, 10, 2)
    assert abs(s2 - 25.0) < 1e-10
    # Matha 侧
    assert _call('#1：[运动_匀变速末速度(0)(10)(2)]') == [20.0]
    print("  ✓ 匀变速位移/末速度/位移由速度 三公式正确")


def test_kinematics_free_fall():
    """自由落体：s=½gt²；v=gt（用标准 g=9.80665）。"""
    print("\n--- 运动学：自由落体 ---")
    i = _interp()
    g_val = i.builtins["g"]
    t = 3.0
    s = i.call("运动_自由落体位移", t, g_val)
    v = i.call("运动_自由落体末速度", t, g_val)
    assert abs(s - 0.5 * g_val * 9) < 1e-10
    assert abs(v - g_val * 3) < 1e-10
    print(f"  ✓ t=3s: s={s:.4f}m, v={v:.4f}m/s（g={g_val}）")


# ============================================================
# 3. 运动学 - 抛体
# ============================================================

def test_kinematics_projectile_horizontal():
    """平抛：落地时间 t=√(2h/g)；射程 R=v0·t。"""
    print("\n--- 运动学：平抛 ---")
    i = _interp()
    g_val = i.builtins["g"]
    h, v0 = 44.1, 20  # h=44.1m → t≈3s
    t = i.call("运动_平抛落地时间", h, g_val)
    R = i.call("运动_平抛射程", v0, h, g_val)
    # 用 t²·g = 2h 验算（避免 g=9.80665 带来的期望硬编码误差）
    assert abs(t * t * g_val - 2 * h) < 1e-6
    # R = v0 * t 等价验算
    assert abs(R - v0 * t) < 1e-10
    print(f"  ✓ h=44.1m,v0=20m/s: t={t:.3f}s, R={R:.2f}m")


def test_kinematics_projectile_angle():
    """斜抛：R=v0²sin2θ/g；H=v0²sin²θ/2g；T=2v0sinθ/g。"""
    print("\n--- 运动学：斜抛（θ=45°最大射程） ---")
    i = _interp()
    g_val = i.builtins["g"]
    v0 = 10.0
    theta45 = math.pi / 4
    R = i.call("运动_斜抛射程", v0, theta45, g_val)
    H = i.call("运动_斜抛最大高度", v0, theta45, g_val)
    T = i.call("运动_斜抛飞行时间", v0, theta45, g_val)
    # 45° 理论值
    R_expect = v0 * v0 / g_val
    H_expect = v0 * v0 * 0.5 / (2 * g_val)   # sin²45°=0.5
    T_expect = 2 * v0 * math.sin(theta45) / g_val
    assert abs(R - R_expect) < 1e-10
    assert abs(H - H_expect) < 1e-10
    assert abs(T - T_expect) < 1e-10
    print(f"  ✓ 45°最大射程 R={R:.3f}m, H={H:.3f}m, T={T:.3f}s")
    # Matha 侧斜抛射程
    out = _call('#1：[运动_斜抛射程(10)(deg2rad(30))(g)]')
    assert len(out) == 1
    print(f"  ✓ Matha 调用斜抛射程(30°) = {out[0]:.3f}m")


# ============================================================
# 4. 运动学 - 圆周
# ============================================================

def test_kinematics_circular():
    """圆周：v=ωr；ω=2π/T；a_n=v²/r=ω²r。"""
    print("\n--- 运动学：圆周 ---")
    i = _interp()
    T, r = 2.0, 1.0       # 周期2s, 半径1m
    omega = i.call("运动_圆周角速度", T)        # ω = π ≈ 3.1416 rad/s
    v = i.call("运动_圆周线速度", omega, r)     # v = ωr = π m/s
    a_v = i.call("运动_向心加速度v", v, r)      # a_n = v²/r = π²
    a_w = i.call("运动_向心加速度w", omega, r)  # a_n = ω²r = π²
    T_back = i.call("运动_圆周周期", v, r)      # T = 2πr/v = 2s
    assert abs(omega - math.pi) < 1e-10
    assert abs(v - math.pi) < 1e-10
    assert abs(a_v - math.pi * math.pi) < 1e-10
    assert abs(a_w - math.pi * math.pi) < 1e-10
    assert abs(T_back - 2.0) < 1e-10
    print(f"  ✓ T=2s,r=1m: ω={omega:.4f}, v={v:.4f}, a_n={a_v:.4f}")


# ============================================================
# 5. 材料力学 - 轴向拉压
# ============================================================

def test_materials_axial_tension():
    """轴向拉压：σ=F/A；ε=ΔL/L；σ=Eε；ΔL=FL/EA。"""
    print("\n--- 材料力学：轴向拉压（Q235钢） ---")
    i = _interp()
    F, L, A = 23500.0, 1.0, 0.0001       # F=23.5kN, L=1m, A=1cm²
    E = i.builtins["钢_Q235_E"]
    sigma = i.call("材料_应力", F, A)      # σ = 23500/1e-4 = 235MPa → 刚好屈服
    dL = i.call("材料_变形", F, L, E, A)   # ΔL = FL/EA
    epsilon = dL / L                        # 应变
    sigma_hooke = i.call("材料_胡克", E, epsilon)  # 胡克定律反算 σ
    sigma_s = i.builtins["钢_Q235_σ_s"]
    n = i.call("材料_安全系数", sigma_s, sigma)    # 安全系数 = 1.0（极限状态）
    assert abs(sigma - 2.35e8) < 1e-2
    assert abs(sigma_hooke - sigma) < 1e-6 * sigma
    assert abs(n - 1.0) < 1e-6
    print(f"  ✓ σ={sigma/1e6:.0f}MPa, ΔL={dL*1e3:.4f}mm, 安全系数 n={n:.2f}")
    # 材料_胡克 Matha 侧
    assert _call('#1：[材料_胡克(钢_Q235_E)(0.001)]') == [2.06e8]


# ============================================================
# 6. 材料力学 - 剪切
# ============================================================

def test_materials_shear():
    """剪切：τ=F/A；τ=Gγ。"""
    print("\n--- 材料力学：剪切 ---")
    i = _interp()
    G = i.builtins["钢_Q235_G"]
    tau = i.call("材料_剪应力", 79000.0, 0.0001)  # 79kN / 1cm² = 790MPa
    gamma = i.call("材料_剪应变", 0.001, 1.0)       # γ = 0.001
    tau_g = i.call("材料_剪切胡克", G, gamma)       # τ = Gγ = 79GPa*0.001 = 79MPa
    assert abs(tau - 7.9e8) < 1
    assert abs(tau_g - 7.9e7) < 1
    print(f"  ✓ τ=F/A={tau/1e6:.0f}MPa; τ=Gγ={tau_g/1e6:.0f}MPa")


# ============================================================
# 7. 材料力学 - 梁弯曲
# ============================================================

def test_beam_bending_rect():
    """梁：矩形截面 I=bh³/12；σ_max=My_max/I。"""
    print("\n--- 材料力学：梁弯曲（矩形截面） ---")
    i = _interp()
    b, h = 0.02, 0.1      # b=2cm, h=10cm
    I_expected = 0.02 * (0.1**3) / 12
    I = i.call("梁_矩形惯性矩", b, h)
    assert abs(I - I_expected) < 1e-18
    # M=100N·m, y_max=h/2=0.05m
    M, y_max = 100.0, h / 2
    sigma_max = i.call("梁_弯曲最大正应力", M, y_max, I)
    # 用抗弯截面模量 Wz=bh²/6 验算：σ_max=M/Wz
    Wz = i.call("梁_矩形抗弯模量", b, h)
    sigma_max2 = M / Wz
    assert abs(sigma_max - sigma_max2) < 1e-6 * sigma_max
    print(f"  ✓ I={I:.3e}m⁴, σ_max={sigma_max/1e6:.3f}MPa (=M/Wz 一致)")


def test_beam_bending_circle():
    """梁：圆形截面 I=πd⁴/64；Wz=πd³/32。"""
    print("\n--- 材料力学：梁弯曲（圆形截面） ---")
    i = _interp()
    d = 0.02   # 20mm
    I = i.call("梁_圆形惯性矩", d)
    Wz = i.call("梁_圆形抗弯模量", d)
    I_expect = math.pi * (d**4) / 64
    Wz_expect = math.pi * (d**3) / 32
    assert abs(I - I_expect) < 1e-22
    assert abs(Wz - Wz_expect) < 1e-18
    # σ_max = M*y_max/I, y_max=d/2, 应等于 M/Wz
    M = 50.0
    s1 = i.call("梁_弯曲最大正应力", M, d / 2, I)
    s2 = M / Wz
    assert abs(s1 - s2) < 1e-9
    print(f"  ✓ d=20mm: I={I:.3e}m⁴, Wz={Wz:.3e}m³, M=50N·m→σ={s1/1e6:.3f}MPa")


# ============================================================
# 8. 材料力学 - 圆轴扭转
# ============================================================

def test_shaft_torsion_solid():
    """圆轴扭转：实心 Ip=πd⁴/32；τ_max=Td/2Ip；φ=TL/(GIp)。"""
    print("\n--- 材料力学：实心圆轴扭转 ---")
    i = _interp()
    d = 0.04           # 40mm
    T = 1000.0         # 1kN·m
    L = 1.0            # 1m
    G = i.builtins["钢_Q235_G"]
    Ip = i.call("轴_实心极惯性矩", d)
    tau_max = i.call("轴_扭转最大剪应力", T, d, Ip)
    phi = i.call("轴_扭转角", T, L, G, Ip)
    # 解析验算
    Ip_exp = math.pi * (d**4) / 32
    tau_exp = T * (d / 2) / Ip_exp
    phi_exp = T * L / (G * Ip_exp)
    assert abs(Ip - Ip_exp) < 1e-20 * max(1, abs(Ip_exp))
    # 用 τ = T*(d/2)/Ip 等价验算（避免浮点累积的绝对值比较）
    assert abs(tau_max - T * (d / 2) / Ip) < 1e-9 * max(1, abs(tau_max))
    assert abs(phi - T * L / (G * Ip)) < 1e-12 * max(1, abs(phi))
    print(f"  ✓ d=40mm: Ip={Ip:.3e}m⁴, τ_max={tau_max/1e6:.3f}MPa, φ={phi*180/math.pi:.3f}°")


def test_shaft_torsion_hollow():
    """空心轴：Ip=π(D⁴-d⁴)/32；比同外径实心轴更省材料。"""
    print("\n--- 材料力学：空心圆轴扭转（省料验证） ---")
    i = _interp()
    D = 0.05
    d = 0.03          # 外径 50，内径 30
    Ip_hollow = i.call("轴_空心极惯性矩", D, d)
    Ip_solid = i.call("轴_实心极惯性矩", D)
    # 面积比（省料比例）
    A_hollow = math.pi * ((D/2)**2 - (d/2)**2)
    A_solid = math.pi * (D/2)**2
    material_ratio = A_hollow / A_solid   # < 1 说明省料
    Ip_ratio = Ip_hollow / Ip_solid       # Ip 仍保留相当比例
    assert 0 < material_ratio < 1.0
    assert Ip_ratio > material_ratio      # 空心保留更多抗扭能力（核心抗扭贡献低）
    print(f"  ✓ 空心轴：材料仅 {material_ratio*100:.1f}%，Ip保留 {Ip_ratio*100:.1f}%")


# ============================================================
# 9. 材料属性数据库 - 常量值
# ============================================================

def test_materials_constants_direct():
    """7 种材料常量直接在 builtins 中可查，数值符合数据库。"""
    print("\n--- 材料属性：常量直接值 ---")
    i = _interp()
    count = 0
    for mat_name, props in MATERIALS.items():
        for prop_key, val in props.items():
            const_name = f"{mat_name}_{prop_key}"
            assert const_name in i.builtins, f"缺少常量 {const_name}"
            if isinstance(val, float) and val != 0:
                assert abs(i.builtins[const_name] - val) < 1e-30 * abs(val)
            else:
                assert i.builtins[const_name] == val
            count += 1
    print(f"  ✓ 共 {len(MATERIALS)} 种材料 × {count//len(MATERIALS)} 属性 = {count} 个常量全部正确")


def test_materials_lookup_functions():
    """材料_xxx("名称") 查询函数正确返回 MATERIALS 中值。"""
    print("\n--- 材料属性：按名称查询函数 ---")
    i = _interp()
    assert i.call("材料_E", "钢_Q235") == MATERIALS["钢_Q235"]["E"]
    assert i.call("材料_G", "铝合金_6061") == MATERIALS["铝合金_6061"]["G"]
    assert i.call("材料_屈服", "钢_45号") == MATERIALS["钢_45号"]["σ_s"]
    assert i.call("材料_强度", "灰铸铁_HT200") == MATERIALS["灰铸铁_HT200"]["σ_b"]
    assert i.call("材料_密度", "混凝土_C30") == MATERIALS["混凝土_C30"]["ρ"]
    assert i.call("材料_泊松", "纯铜") == MATERIALS["纯铜"]["ν"]
    # Matha 侧
    assert _call('#1：[材料_E("钢_Q235")]') == [2.06e11]
    print("  ✓ 材料_E/G/屈服/强度/密度/泊松 查询正确")


# ============================================================
# 10. Matha 侧综合场景
# ============================================================

def test_matha_scenario_beam_design():
    """综合场景：简支木梁设计（松木），求最大弯曲应力 + 安全系数。"""
    print("\n--- 综合场景：Matha 侧木梁设计 ---")
    # 简支梁跨中集中力 P，跨度 L，弯矩 M_max=PL/4
    # 松木矩形截面 b×h=0.1×0.2m，P=2kN，L=3m
    src = """
#：{
  P = 2000
  L = 3
  M = P * L / 4
  b = 0.1
  h = 0.2
  I = 梁_矩形惯性矩(b)(h)
  y_max = h / 2
  sigma_max = 梁_弯曲最大正应力(M)(y_max)(I)
  sigma_s = 材料_屈服("木材_松木")
  n = 材料_安全系数(sigma_s)(sigma_max)
  [sigma_max]
  [n]
}
"""
    out = _call(src)
    sigma_max, n = out[0], out[1]
    # 手算：M=1500N·m；I=0.1*0.008/12=6.6667e-5；σ_max=1500*0.1/6.6667e-5 ≈ 2.25MPa
    # 松木 σ_s=40MPa，n≈17.8
    assert abs(sigma_max - 2.25e6) < 1e3
    assert n > 10.0 and n < 30.0
    print(f"  ✓ 木梁：σ_max={sigma_max/1e6:.2f}MPa, 安全系数 n={n:.2f}")


def test_matha_scenario_shaft_design():
    """综合场景：45号钢实心传动轴设计（扭转强度 + 刚度）。"""
    print("\n--- 综合场景：Matha 侧传动轴设计 ---")
    # 扭矩 T=500N·m，轴长 L=0.8m，直径 d=40mm（45号钢）
    src = """
#：{
  T = 500
  L = 0.8
  d = 0.04
  Ip = 轴_实心极惯性矩(d)
  G = 材料_G("钢_45号")
  tau_max = 轴_扭转最大剪应力(T)(d)(Ip)
  phi_deg = 轴_扭转角(T)(L)(G)(Ip) * rad2deg(1)
  [tau_max / 1000000]
  [phi_deg]
}
"""
    out = _call(src)
    tau_MPa, phi_deg = out[0], out[1]
    # 轴直径 40mm：τ_max ≈ 500*0.02 / (π*0.04⁴/32) = 10 / (π*2.56e-6/32)
    #        = 10 / (2.513e-7) ≈ 39.8 MPa
    assert 30 < tau_MPa < 50
    # 扭转角（45号钢 G=81GPa）：φ = TL/GIp rad → 度
    assert 0 < phi_deg < 2.0
    print(f"  ✓ 轴：τ_max={tau_MPa:.1f}MPa, 扭转角 φ={phi_deg:.3f}°/0.8m")


def test_matha_scenario_projectile_range_table():
    """综合场景：Matha 侧生成斜抛射程表（15°/30°/45°/60°/75°）。"""
    print("\n--- 综合场景：Matha 斜抛射程表 ---")
    src = """
#：{
  v0 = 20
  g0 = g
  R15 = 运动_斜抛射程(v0)(deg2rad(15))(g0)
  R30 = 运动_斜抛射程(v0)(deg2rad(30))(g0)
  R45 = 运动_斜抛射程(v0)(deg2rad(45))(g0)
  R60 = 运动_斜抛射程(v0)(deg2rad(60))(g0)
  R75 = 运动_斜抛射程(v0)(deg2rad(75))(g0)
  [R15]
  [R30]
  [R45]
  [R60]
  [R75]
}
"""
    out = _call(src)
    R15, R30, R45, R60, R75 = out
    # 45° 最大；15° = 75°；30° = 60°
    assert R45 == max(out)
    assert abs(R15 - R75) < 1e-8
    assert abs(R30 - R60) < 1e-8
    print(f"  ✓ 射程表: 15°={R15:.1f}m, 30°={R30:.1f}m, 45°={R45:.1f}m(max), 60°={R60:.1f}m, 75°={R75:.1f}m")
    print("    对称性：15°=75°, 30°=60°, 45°最大 ✓")


# ============================================================
# 入口：pytest 或直接运行
# ============================================================

if __name__ == "__main__":
    tests = [
        test_mechanics_registered_in_interp,
        test_mechanics_registered_in_semantic,
        test_kinematics_uniform_motion,
        test_kinematics_uniform_accel,
        test_kinematics_free_fall,
        test_kinematics_projectile_horizontal,
        test_kinematics_projectile_angle,
        test_kinematics_circular,
        test_materials_axial_tension,
        test_materials_shear,
        test_beam_bending_rect,
        test_beam_bending_circle,
        test_shaft_torsion_solid,
        test_shaft_torsion_hollow,
        test_materials_constants_direct,
        test_materials_lookup_functions,
        test_matha_scenario_beam_design,
        test_matha_scenario_shaft_design,
        test_matha_scenario_projectile_range_table,
    ]
    for t in tests:
        t()
    print(f"\n✓✓✓ {len(tests)} 个机械领域测试全部通过 ✓✓✓")