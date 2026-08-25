"""Matha 机械领域模块：动力学（Dynamics）。

基于运动学 + mathlib 数学地基，演化动力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、牛顿运动定律（Newton's Laws）
  1) 牛顿第二定律：F = ma；加速度 a = F/m
  2) 滑动摩擦力：f = μN；最大静摩擦 f_max = μ_s·N
  3) 牛顿第三定律：作用力与反作用力等大反向
  4) 合力（同向/垂直分量分解）

二、动量定理（Momentum & Impulse）
  1) 动量 p = mv
  2) 冲量 I = Ft
  3) 动量定理：Δp = Ft → 末动量 p₂ = p₁ + Ft
  4) 动量守恒（两体正碰）：m₁v₁ + m₂v₂ = m₁v₁' + m₂v₂'
  5) 完全弹性碰撞恢复系数 e = (v₂'-v₁')/(v₁-v₂)

三、功与能（Work & Energy）
  1) 功 W = Fs cosθ；功率 P = W/t = Fv
  2) 动能 E_k = ½mv²
  3) 重力势能 E_p = mgh
  4) 弹性势能 E_s = ½kx²
  5) 动能定理：W合 = ΔE_k = ½mv₂² - ½mv₁²
  6) 机械能守恒：E_k + E_p = const（无摩擦）

四、转动动力学（Rotational Dynamics）
  1) 力矩 M = r×F = rF sinθ
  2) 转动惯量：质点 I=mr²；细杆 I=⅓mL²；圆盘 I=½mr²；圆环 I=mr²；实心球 I=⅖mr²
  3) 转动定律 M = Iα（类比 F=ma）
  4) 角动量 L = Iω；角动量守恒
  5) 转动动能 E_rot = ½Iω²
  6) 平行轴定理 I = I_cm + md²

五、机械振动（Oscillations）
  1) 简谐振动周期：T = 2π√(m/k)；频率 f = 1/T；角频率 ω = 2π/T
  2) 弹簧振子：位移 x(t) = A cos(ωt)
  3) 单摆周期：T = 2π√(L/g)
  4) 复摆周期：T = 2π√(I/(mgd))
  5) 简谐振动总能量：E = ½kA²
  6) 阻尼振动角频率：ω_d = √(ω₀² - β²)

设计原则：
  - 所有函数返回纯数值（float/int），不抛语义错（除以零等 Python 自身抛）
  - 多参函数一律 _curry2/_curry3 封装，与 Matha 柯里化语义一致
  - 前缀 力_ / 动量_ / 功_ / 转动_ / 振动_ 区分子领域
  - 与运动学共享 mathlib 的 sin/cos/sqrt/pi/g 等
"""

from __future__ import annotations
import math


# ============================================================
# 柯里化工具（与 mechanics.py 语义一致）
# ============================================================

def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def _curry3(func):
    def with_first(a):
        def with_second(b):
            return lambda c: func(a, b, c)
        return with_second
    return with_first


def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1


# ============================================================
# 一、牛顿运动定律（Newton's Laws）
# ============================================================

# 牛顿第二定律：F = ma → 力 / 加速度 / 质量
def _牛顿_力(m, a): return m * a                     # F = ma  N
def _牛顿_加速度(F, m): return F / m                  # a = F/m  m/s²
def _牛顿_质量(F, a): return F / a                    # m = F/a  kg

# 滑动摩擦力：f = μN
def _摩擦_滑动摩擦力(mu, N): return mu * N            # f = μN  N
def _摩擦_最大静摩擦(mu_s, N): return mu_s * N        # f_max = μ_s·N  N

# 合力（同向代数和 / 垂直分量用勾股）
def _合力_同向(F1, F2): return F1 + F2               # 同向合力
def _合力_垂直(F1, F2): return math.sqrt(F1*F1 + F2*F2)  # 垂直合力大小


# ============================================================
# 二、动量定理（Momentum & Impulse）
# ============================================================

# 动量 p = mv
def _动量_动量(m, v): return m * v                    # p = mv  kg·m/s
# 冲量 I = Ft
def _动量_冲量(F, t): return F * t                    # I = Ft  N·s
# 动量定理：末动量 p2 = p1 + Ft
def _动量_末动量(p1, F, t): return p1 + F * t
# 动量守恒（两体正碰）：已知 m1,v1,m2,v2 和 v2' 求 v1'
#   m1*v1 + m2*v2 = m1*v1' + m2*v2'
#   → v1' = (m1*v1 + m2*v2 - m2*v2') / m1
def _动量_碰后速度1(m1, v1, m2, v2, v2_after):
    return (m1 * v1 + m2 * v2 - m2 * v2_after) / m1
# 完全弹性碰撞（两体）：动量+动能均守恒
#   v1' = ((m1-m2)*v1 + 2*m2*v2) / (m1+m2)
#   v2' = ((m2-m1)*v2 + 2*m1*v1) / (m1+m2)
def _弹性碰撞_速度1(m1, v1, m2, v2):
    return ((m1 - m2) * v1 + 2 * m2 * v2) / (m1 + m2)
def _弹性碰撞_速度2(m1, v1, m2, v2):
    return ((m2 - m1) * v2 + 2 * m1 * v1) / (m1 + m2)
# 恢复系数 e = (v2' - v1') / (v1 - v2)
def _碰撞_恢复系数(v1, v2, v1_after, v2_after):
    return (v2_after - v1_after) / (v1 - v2)


# ============================================================
# 三、功与能（Work & Energy）
# ============================================================

# 功 W = Fs cosθ
def _功_功(F, s, theta_rad): return F * s * math.cos(theta_rad)  # W = Fs cosθ  J
# 功率 P = W/t
def _功_功率(W, t): return W / t                      # P = W/t  W
# 功率 P = Fv
def _功_功率力速(F, v): return F * v                  # P = Fv  W
# 动能 E_k = ½mv²
def _能量_动能(m, v): return 0.5 * m * v * v          # E_k = ½mv²  J
# 重力势能 E_p = mgh
def _能量_重力势能(m, h, g_val): return m * g_val * h  # E_p = mgh  J
# 弹性势能 E_s = ½kx²
def _能量_弹性势能(k, x): return 0.5 * k * x * x      # E_s = ½kx²  J
# 动能定理：合外力做功 = ΔE_k = ½mv2² - ½mv1²
def _能量_动能定理(m, v1, v2):
    return 0.5 * m * v2 * v2 - 0.5 * m * v1 * v1
# 机械能守恒：高处 → 低处（无摩擦）
#   ½mv₁² + mgh₁ = ½mv₂² + mgh₂
#   → v₂ = √(v₁² + 2g(h₁-h₂))
def _能量_守恒末速度(v1, h1, h2, g_val):
    return math.sqrt(v1 * v1 + 2 * g_val * (h1 - h2))


# ============================================================
# 四、转动动力学（Rotational Dynamics）
# ============================================================

# 力矩 M = rF sinθ
def _转动_力矩(r, F, theta_rad): return r * F * math.sin(theta_rad)  # M = rF sinθ  N·m
# 转动定律：M = Iα → 角加速度 α = M/I
def _转动_角加速度(M, I): return M / I               # α = M/I  rad/s²

# 转动惯量（常见刚体）
def _转动惯量_质点(m, r): return m * r * r            # I = mr²
def _转动惯量_细杆端点(m, L): return m * L * L / 3     # I = ⅓mL²（绕端点）
def _转动惯量_细杆中心(m, L): return m * L * L / 12    # I = ⅟₁₂mL²（绕中心）
def _转动惯量_圆盘(m, r): return 0.5 * m * r * r      # I = ½mr²
def _转动惯量_圆环(m, r): return m * r * r            # I = mr²
def _转动惯量_实心球(m, r): return 2.0 * m * r * r / 5  # I = ⅖mr²
def _转动惯量_空心球(m, r): return 2.0 * m * r * r / 3  # I = ⅔mr²
def _转动惯量_圆柱(m, r): return 0.5 * m * r * r      # I = ½mr²（绕轴线）

# 平行轴定理：I = I_cm + md²
def _转动惯量_平行轴(I_cm, m, d): return I_cm + m * d * d

# 角动量 L = Iω
def _转动_角动量(I, omega): return I * omega          # L = Iω  kg·m²/s
# 角动量守恒：I₁ω₁ = I₂ω₂ → ω₂ = I₁ω₁/I₂
def _转动_角动量守恒(I1, omega1, I2): return I1 * omega1 / I2
# 转动动能 E_rot = ½Iω²
def _转动_转动动能(I, omega): return 0.5 * I * omega * omega  # E = ½Iω²  J


# ============================================================
# 五、机械振动（Oscillations）
# ============================================================

# 简谐振动（弹簧振子）：T = 2π√(m/k)
def _振动_周期(m, k): return 2 * math.pi * math.sqrt(m / k)  # T = 2π√(m/k)  s
# 频率 f = 1/T
def _振动_频率(T): return 1 / T                       # f = 1/T  Hz
# 角频率 ω = 2π/T = √(k/m)
def _振动_角频率(T): return 2 * math.pi / T           # ω = 2π/T  rad/s
# 简谐振动位移 x(t) = A cos(ωt)
def _振动_位移(A, omega, t): return A * math.cos(omega * t)
# 简谐振动速度 v(t) = -Aω sin(ωt)
def _振动_速度(A, omega, t): return -A * omega * math.sin(omega * t)
# 简谐振动总能量 E = ½kA²
def _振动_总能量(k, A): return 0.5 * k * A * A       # E = ½kA²  J

# 单摆周期 T = 2π√(L/g)
def _振动_单摆周期(L, g_val): return 2 * math.pi * math.sqrt(L / g_val)
# 复摆周期 T = 2π√(I/(mgd))  （d 为质心到转轴距离）
def _振动_复摆周期(I, m, g_val, d): return 2 * math.pi * math.sqrt(I / (m * g_val * d))
# 阻尼振动角频率 ω_d = √(ω₀² - β²)  （β 为阻尼系数）
def _振动_阻尼角频率(omega0, beta): return math.sqrt(omega0 * omega0 - beta * beta)


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_dynamics(builtins: dict) -> None:
    """将动力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（mechanics 之后）。
    命名规则：
      - 牛顿定律：前缀 力_
      - 动量定理：前缀 动量_
      - 功与能：前缀 功_ / 前缀 能量_
      - 转动动力学：前缀 转动_ / 前缀 转动惯量_
      - 机械振动：前缀 振动_
    """
    # --- 牛顿运动定律 ---
    builtins["力_牛顿力"] = _curry2(_牛顿_力)           # 力_牛顿力(m)(a)
    builtins["力_加速度"] = _curry2(_牛顿_加速度)       # 力_加速度(F)(m)
    builtins["力_质量"] = _curry2(_牛顿_质量)           # 力_质量(F)(a)
    builtins["力_滑动摩擦力"] = _curry2(_摩擦_滑动摩擦力)  # 力_滑动摩擦力(μ)(N)
    builtins["力_最大静摩擦"] = _curry2(_摩擦_最大静摩擦)
    builtins["力_合力同向"] = _curry2(_合力_同向)
    builtins["力_合力垂直"] = _curry2(_合力_垂直)

    # --- 动量定理 ---
    builtins["动量_动量"] = _curry2(_动量_动量)         # 动量_动量(m)(v)
    builtins["动量_冲量"] = _curry2(_动量_冲量)         # 动量_冲量(F)(t)
    builtins["动量_末动量"] = _curry3(_动量_末动量)     # 动量_末动量(p1)(F)(t)
    # _动量_碰后速度1 是 5 参函数，拆成 curry3 + curry2：动量_碰后速度1(m1)(v1)(m2)(v2)(v2')
    builtins["动量_碰后速度1"] = _curry3(
        lambda m1, v1, m2: _curry2(
            lambda v2, v2a: _动量_碰后速度1(m1, v1, m2, v2, v2a)
        )
    )
    builtins["弹性碰撞_速度1"] = _curry4(_弹性碰撞_速度1)
    builtins["弹性碰撞_速度2"] = _curry4(_弹性碰撞_速度2)
    builtins["碰撞_恢复系数"] = _curry4(_碰撞_恢复系数)

    # --- 功与能 ---
    builtins["功_功"] = _curry3(_功_功)                 # 功_功(F)(s)(θ)
    builtins["功_功率"] = _curry2(_功_功率)             # 功_功率(W)(t)
    builtins["功_功率力速"] = _curry2(_功_功率力速)     # 功_功率力速(F)(v)
    builtins["能量_动能"] = _curry2(_能量_动能)         # 能量_动能(m)(v)
    builtins["能量_重力势能"] = _curry3(_能量_重力势能)  # 能量_重力势能(m)(h)(g)
    builtins["能量_弹性势能"] = _curry2(_能量_弹性势能)  # 能量_弹性势能(k)(x)
    builtins["能量_动能定理"] = _curry3(_能量_动能定理)  # 能量_动能定理(m)(v1)(v2)
    builtins["能量_守恒末速度"] = _curry4(_能量_守恒末速度)  # 能量_守恒末速度(v1)(h1)(h2)(g)

    # --- 转动动力学 ---
    builtins["转动_力矩"] = _curry3(_转动_力矩)         # 转动_力矩(r)(F)(θ)
    builtins["转动_角加速度"] = _curry2(_转动_角加速度)  # 转动_角加速度(M)(I)
    builtins["转动_角动量"] = _curry2(_转动_角动量)     # 转动_角动量(I)(ω)
    builtins["转动_角动量守恒"] = _curry3(_转动_角动量守恒)  # 转动_角动量守恒(I1)(ω1)(I2)
    builtins["转动_转动动能"] = _curry2(_转动_转动动能)  # 转动_转动动能(I)(ω)

    # 转动惯量（单参或双参）
    builtins["转动惯量_质点"] = _curry2(_转动惯量_质点)
    builtins["转动惯量_细杆端点"] = _curry2(_转动惯量_细杆端点)
    builtins["转动惯量_细杆中心"] = _curry2(_转动惯量_细杆中心)
    builtins["转动惯量_圆盘"] = _curry2(_转动惯量_圆盘)
    builtins["转动惯量_圆环"] = _curry2(_转动惯量_圆环)
    builtins["转动惯量_实心球"] = _curry2(_转动惯量_实心球)
    builtins["转动惯量_空心球"] = _curry2(_转动惯量_空心球)
    builtins["转动惯量_圆柱"] = _curry2(_转动惯量_圆柱)
    builtins["转动惯量_平行轴"] = _curry3(_转动惯量_平行轴)  # 转动惯量_平行轴(I_cm)(m)(d)

    # --- 机械振动 ---
    builtins["振动_周期"] = _curry2(_振动_周期)         # 振动_周期(m)(k)
    builtins["振动_频率"] = _振动_频率                  # 振动_频率(T)
    builtins["振动_角频率"] = _振动_角频率              # 振动_角频率(T)
    builtins["振动_位移"] = _curry3(_振动_位移)         # 振动_位移(A)(ω)(t)
    builtins["振动_速度"] = _curry3(_振动_速度)         # 振动_速度(A)(ω)(t)
    builtins["振动_总能量"] = _curry2(_振动_总能量)     # 振动_总能量(k)(A)
    builtins["振动_单摆周期"] = _curry2(_振动_单摆周期)  # 振动_单摆周期(L)(g)
    builtins["振动_复摆周期"] = _curry4(_振动_复摆周期)  # 振动_复摆周期(I)(m)(g)(d)
    builtins["振动_阻尼角频率"] = _curry2(_振动_阻尼角频率)  # 振动_阻尼角频率(ω0)(β)


def _dynamics_symtab_names() -> list[str]:
    """返回动力学所有内建名（用于语义分析注册，避免报未定义）。"""
    names: list[str] = []
    # 牛顿定律
    for n in ["牛顿力","加速度","质量","滑动摩擦力","最大静摩擦","合力同向","合力垂直"]:
        names.append(f"力_{n}")
    # 动量
    for n in ["动量","冲量","末动量","碰后速度1"]:
        names.append(f"动量_{n}")
    for n in ["速度1","速度2"]:
        names.append(f"弹性碰撞_{n}")
    names.append("碰撞_恢复系数")
    # 功与能
    for n in ["功","功率","功率力速"]:
        names.append(f"功_{n}")
    for n in ["动能","重力势能","弹性势能","动能定理","守恒末速度"]:
        names.append(f"能量_{n}")
    # 转动
    for n in ["力矩","角加速度","角动量","角动量守恒","转动动能"]:
        names.append(f"转动_{n}")
    for n in ["质点","细杆端点","细杆中心","圆盘","圆环","实心球","空心球","圆柱","平行轴"]:
        names.append(f"转动惯量_{n}")
    # 振动
    for n in ["周期","频率","角频率","位移","速度","总能量","单摆周期","复摆周期","阻尼角频率"]:
        names.append(f"振动_{n}")
    return names
