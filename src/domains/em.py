"""Matha 机械领域模块：电磁学（Electromagnetism）。

基于动力学 + 热力学 + mathlib 数学地基，演化电磁学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、静电学（Electrostatics）
  1) 库仑定律：F = kq1q2/r²
  2) 电场强度：E = F/q = kQ/r²
  3) 电势：V = kQ/r
  4) 电势能：U = kq1q2/r
  5) 平行板电容器：C = ε₀S/d
  6) 电容器能量：W = ½CV²
  7) 高斯定律：Φ = Q/ε₀

二、直流电路（DC Circuits）
  1) 欧姆定律：V = IR
  2) 电阻串联：R = ΣR_i
  3) 电阻并联：1/R = Σ(1/R_i)
  4) 电功率：P = VI = I²R = V²/R
  5) 焦耳热：Q = I²Rt

三、磁场（Magnetism）
  1) 洛伦兹力：F = qvB sinθ
  2) 安培力：F = BIL sinθ
  3) 长直导线磁场：B = μ₀I/(2πr)
  4) 圆形线圈中心磁场：B = μ₀I/(2R)
  5) 螺线管磁场：B = μ₀nI
  6) 磁通量：Φ = BA cosθ

四、电磁感应（Electromagnetic Induction）
  1) 法拉第定律：ε = -N·dΦ/dt
  2) 动生电动势：ε = BLv
  3) 自感电动势：ε = -L·dI/dt
  4) 磁场能量：W = ½LI²
  5) 互感：M = N₂Φ₂₁/I₁

五、交流电路（AC Circuits）
  1) 感抗：X_L = ωL = 2πfL
  2) 容抗：X_C = 1/(ωC) = 1/(2πfC)
  3) 阻抗（串联RLC）：Z = √(R² + (X_L - X_C)²)
  4) 谐振频率：f₀ = 1/(2π√(LC))
  5) 有效值：V_rms = V_max/√2
  6) 功率因数：cosφ = R/Z
  7) 交流功率：P = V_rms·I_rms·cosφ

设计原则：
  - 所有函数返回纯数值（float/int），不抛语义错（除以零等 Python 自身抛）
  - 多参函数一律 _curry2/_curry3/_curry4/_curry5 封装
  - 前缀 电_ / 电路_ / 磁_ / 感应_ / 交流_ 区分子领域
  - 常用介电常数/电阻率作为常量注册
"""

from __future__ import annotations
import math

from src.stdlib.safe_ops import safe_div


# ============================================================
# 柯里化工具
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


def _curry5(func):
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    return lambda e: func(a, b, c, d, e)
                return w4
            return w3
        return w2
    return w1


# ============================================================
# 物理常量（SI 单位）
# ============================================================

# 真空介电常数 ε₀ = 8.854e-12 F/m
EPSILON_0 = 8.854187817e-12
# 静电力常量 k = 1/(4πε₀) ≈ 8.988e9 N·m²/C²
K_ELECTROSTATIC = 8.9875517873681764e9  # 1/(4π·ε₀)
# 真空磁导率 μ₀ = 4π×10⁻⁷ T·m/A
MU_0 = 4 * math.pi * 1e-7
# 基本电荷 e = 1.602e-19 C
ELEMENTARY_CHARGE = 1.602176634e-19


# ============================================================
# 一、静电学（Electrostatics）
# ============================================================

# 库仑定律：F = k·q1·q2/r²
def _电_库仑力(q1, q2, r): return safe_div(K_ELECTROSTATIC * q1 * q2, r * r)
# 电场强度（点电荷）：E = kQ/r²
def _电_电场(Q, r): return safe_div(K_ELECTROSTATIC * Q, r * r)
# 电势（点电荷）：V = kQ/r
def _电_电势(Q, r): return safe_div(K_ELECTROSTATIC * Q, r)
# 电势能：U = kq1q2/r
def _电_电势能(q1, q2, r): return safe_div(K_ELECTROSTATIC * q1 * q2, r)
# 平行板电容器电容：C = ε₀S/d
def _电_平行板电容(S, d): return safe_div(EPSILON_0 * S, d)
# 电容器储能：W = ½CV²
def _电_电容储能(C, V): return 0.5 * C * V * V
# 电容器电荷：Q = CV
def _电_电容电荷(C, V): return C * V
# 高斯定律电通量：Φ = Q/ε₀
def _电_高斯通量(Q): return Q / EPSILON_0
# 电偶极矩：p = qd
def _电_电偶极矩(q, d): return q * d


# ============================================================
# 二、直流电路（DC Circuits）
# ============================================================

# 欧姆定律：V = IR
def _电路_电压(I, R): return I * R
# 电流：I = V/R
def _电路_电流(V, R): return V / R
# 电阻：R = V/I
def _电路_电阻(V, I): return V / I
# 电阻串联：R = ΣR_i
def _电路_串联电阻(R_list):
    return sum(R_list) if isinstance(R_list, list) else R_list
# 电阻并联：1/R = Σ(1/R_i)
def _电路_并联电阻(R_list):
    if isinstance(R_list, list):
        inv_sum = sum(1.0 / r for r in R_list)
        return 1.0 / inv_sum
    return R_list
# 电功率：P = VI
def _电路_功率(V, I): return V * I
# 电功率（焦耳热形式）：P = I²R
def _电路_功率热(I, R): return I * I * R
# 电功率（电压形式）：P = V²/R
def _电路_功率压(V, R): return safe_div(V * V, R)
# 焦耳热：Q = I²Rt
def _电路_焦耳热(I, R, t): return I * I * R * t


# ============================================================
# 三、磁场（Magnetism）
# ============================================================

# 洛伦兹力：F = qvB sinθ
def _磁_洛伦兹力(q, v, B, theta_rad): return abs(q) * v * B * math.sin(theta_rad)
# 安培力（载流导线）：F = BIL sinθ
def _磁_安培力(B, I, L, theta_rad): return B * I * L * math.sin(theta_rad)
# 长直导线磁场：B = μ₀I/(2πr)
def _磁_直导线磁场(I, r): return MU_0 * I / (2 * math.pi * r)
# 圆形线圈中心磁场：B = μ₀I/(2R)
def _磁_圆线圈中心磁场(I, R): return MU_0 * I / (2 * R)
# 螺线管磁场：B = μ₀nI（n 为单位长度匝数）
def _磁_螺线管磁场(n, I): return MU_0 * n * I
# 磁通量：Φ = BA cosθ
def _磁_磁通量(B, A, theta_rad): return B * A * math.cos(theta_rad)
# 带电粒子圆周运动半径：r = mv/(qB)
def _磁_回旋半径(m, v, q, B): return m * v / (abs(q) * B)
# 回旋频率：f = qB/(2πm)
def _磁_回旋频率(q, B, m): return abs(q) * B / (2 * math.pi * m)


# ============================================================
# 四、电磁感应（Electromagnetic Induction）
# ============================================================

# 法拉第定律：ε = -N·dΦ/dt（取绝对值）
def _感应_法拉第电动势(N, dPhi, dt): return abs(safe_div(N * dPhi, dt))
# 动生电动势：ε = BLv
def _感应_动生电动势(B, L, v): return B * L * v
# 自感电动势：ε = L·dI/dt（取绝对值）
def _感应_自感电动势(L, dI, dt): return abs(safe_div(L * dI, dt))
# 磁场能量（电感储能）：W = ½LI²
def _感应_磁场能量(L, I): return 0.5 * L * I * I
# 互感：M = N₂·Φ₂₁/I₁
def _感应_互感(N2, Phi21, I1): return N2 * Phi21 / I1
# RL电路时间常数：τ = L/R
def _感应_RL时间常数(L, R): return L / R


# ============================================================
# 五、交流电路（AC Circuits）
# ============================================================

# 感抗：X_L = ωL = 2πfL
def _交流_感抗(f, L): return 2 * math.pi * f * L
# 容抗：X_C = 1/(ωC) = 1/(2πfC)
def _交流_容抗(f, C): return safe_div(1.0, 2 * math.pi * f * C)
# 阻抗（串联RLC）：Z = √(R² + (X_L - X_C)²)
def _交流_阻抗(R, XL, XC): return math.sqrt(R * R + (XL - XC) ** 2)
# 谐振频率：f₀ = 1/(2π√(LC))
def _交流_谐振频率(L, C): return safe_div(1.0, 2 * math.pi * math.sqrt(L * C))
# 有效值（峰值/√2）
def _交流_有效值(V_max): return V_max / math.sqrt(2)
# 峰值（有效值×√2）
def _交流_峰值(V_rms): return V_rms * math.sqrt(2)
# 功率因数：cosφ = R/Z
def _交流_功率因数(R, Z): return safe_div(R, Z)
# 交流有功功率：P = V·I·cosφ
def _交流_有功功率(V, I, cos_phi): return V * I * cos_phi
# 视在功率：S = VI
def _交流_视在功率(V, I): return V * I
# 无功功率：Q = VI sinφ
def _交流_无功功率(V, I, cos_phi): return V * I * math.sqrt(1 - cos_phi ** 2)
# 品质因数（RLC谐振）：Q = (1/R)√(L/C)
def _交流_品质因数(R, L, C): return (1 / R) * math.sqrt(L / C)


# ============================================================
# 电阻率数据库（ρ, 单位 Ω·m, 20°C）
# ============================================================

RESISTIVITIES: dict[str, float] = {
    "银": 1.59e-8,
    "铜": 1.68e-8,
    "金": 2.44e-8,
    "铝": 2.65e-8,
    "钨": 5.6e-8,
    "铁": 9.71e-8,
    "钢": 7.2e-7,
    "铅": 2.2e-7,
    "镍铬合金": 1.1e-6,
    "碳": 3.5e-5,
}

# 相对介电常数（无量纲）
DIELECTRIC_CONSTANTS: dict[str, float] = {
    "真空": 1.0,
    "空气": 1.0006,
    "水": 80.0,
    "玻璃": 5.0,
    "云母": 6.0,
    "陶瓷": 6.5,
    "纸": 3.5,
    "聚乙烯": 2.3,
    "变压器油": 4.5,
    "钛酸钡": 1200.0,
}


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_em(builtins: dict) -> None:
    """将电磁学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（thermo 之后）。
    """
    # --- 静电学 ---
    builtins["电_库仑力"] = _curry3(_电_库仑力)                # 电_库仑力(q1)(q2)(r)
    builtins["电_电场"] = _curry2(_电_电场)                    # 电_电场(Q)(r)
    builtins["电_电势"] = _curry2(_电_电势)                    # 电_电势(Q)(r)
    builtins["电_电势能"] = _curry3(_电_电势能)                # 电_电势能(q1)(q2)(r)
    builtins["电_平行板电容"] = _curry2(_电_平行板电容)        # 电_平行板电容(S)(d)
    builtins["电_电容储能"] = _curry2(_电_电容储能)            # 电_电容储能(C)(V)
    builtins["电_电容电荷"] = _curry2(_电_电容电荷)            # 电_电容电荷(C)(V)
    builtins["电_高斯通量"] = _电_高斯通量                     # 电_高斯通量(Q)
    builtins["电_电偶极矩"] = _curry2(_电_电偶极矩)            # 电_电偶极矩(q)(d)

    # --- 直流电路 ---
    builtins["电路_电压"] = _curry2(_电路_电压)                # 电路_电压(I)(R)
    builtins["电路_电流"] = _curry2(_电路_电流)                # 电路_电流(V)(R)
    builtins["电路_电阻"] = _curry2(_电路_电阻)                # 电路_电阻(V)(I)
    builtins["电路_串联电阻"] = _电路_串联电阻                  # 电路_串联电阻(列表)
    builtins["电路_并联电阻"] = _电路_并联电阻                  # 电路_并联电阻(列表)
    builtins["电路_功率"] = _curry2(_电路_功率)                # 电路_功率(V)(I)
    builtins["电路_功率热"] = _curry2(_电路_功率热)            # 电路_功率热(I)(R)
    builtins["电路_功率压"] = _curry2(_电路_功率压)            # 电路_功率压(V)(R)
    builtins["电路_焦耳热"] = _curry3(_电路_焦耳热)            # 电路_焦耳热(I)(R)(t)

    # --- 磁场 ---
    builtins["磁_洛伦兹力"] = _curry4(_磁_洛伦兹力)            # 磁_洛伦兹力(q)(v)(B)(θ)
    builtins["磁_安培力"] = _curry4(_磁_安培力)                # 磁_安培力(B)(I)(L)(θ)
    builtins["磁_直导线磁场"] = _curry2(_磁_直导线磁场)        # 磁_直导线磁场(I)(r)
    builtins["磁_圆线圈中心磁场"] = _curry2(_磁_圆线圈中心磁场)  # 磁_圆线圈中心磁场(I)(R)
    builtins["磁_螺线管磁场"] = _curry2(_磁_螺线管磁场)        # 磁_螺线管磁场(n)(I)
    builtins["磁_磁通量"] = _curry3(_磁_磁通量)                # 磁_磁通量(B)(A)(θ)
    builtins["磁_回旋半径"] = _curry4(_磁_回旋半径)            # 磁_回旋半径(m)(v)(q)(B)
    builtins["磁_回旋频率"] = _curry3(_磁_回旋频率)            # 磁_回旋频率(q)(B)(m)

    # --- 电磁感应 ---
    builtins["感应_法拉第电动势"] = _curry3(_感应_法拉第电动势)  # 感应_法拉第电动势(N)(dΦ)(dt)
    builtins["感应_动生电动势"] = _curry3(_感应_动生电动势)    # 感应_动生电动势(B)(L)(v)
    builtins["感应_自感电动势"] = _curry3(_感应_自感电动势)    # 感应_自感电动势(L)(dI)(dt)
    builtins["感应_磁场能量"] = _curry2(_感应_磁场能量)        # 感应_磁场能量(L)(I)
    builtins["感应_互感"] = _curry3(_感应_互感)                # 感应_互感(N2)(Φ21)(I1)
    builtins["感应_RL时间常数"] = _curry2(_感应_RL时间常数)    # 感应_RL时间常数(L)(R)

    # --- 交流电路 ---
    builtins["交流_感抗"] = _curry2(_交流_感抗)                # 交流_感抗(f)(L)
    builtins["交流_容抗"] = _curry2(_交流_容抗)                # 交流_容抗(f)(C)
    builtins["交流_阻抗"] = _curry3(_交流_阻抗)                # 交流_阻抗(R)(XL)(XC)
    builtins["交流_谐振频率"] = _curry2(_交流_谐振频率)        # 交流_谐振频率(L)(C)
    builtins["交流_有效值"] = _交流_有效值                     # 交流_有效值(Vmax)
    builtins["交流_峰值"] = _交流_峰值                         # 交流_峰值(Vrms)
    builtins["交流_功率因数"] = _curry2(_交流_功率因数)        # 交流_功率因数(R)(Z)
    builtins["交流_有功功率"] = _curry3(_交流_有功功率)        # 交流_有功功率(V)(I)(cosφ)
    builtins["交流_视在功率"] = _curry2(_交流_视在功率)        # 交流_视在功率(V)(I)
    builtins["交流_无功功率"] = _curry3(_交流_无功功率)        # 交流_无功功率(V)(I)(cosφ)
    builtins["交流_品质因数"] = _curry3(_交流_品质因数)        # 交流_品质因数(R)(L)(C)

    # --- 物理常量 ---
    builtins["ε0_真空介电常数"] = EPSILON_0
    builtins["k_静电力常量"] = K_ELECTROSTATIC
    builtins["μ0_真空磁导率"] = MU_0
    builtins["e_基本电荷"] = ELEMENTARY_CHARGE

    # --- 电阻率常量 ---
    for name, val in RESISTIVITIES.items():
        builtins[f"电阻率_{name}"] = val

    # --- 介电常数常量 ---
    for name, val in DIELECTRIC_CONSTANTS.items():
        builtins[f"介电常数_{name}"] = val


def _em_symtab_names() -> list[str]:
    """返回电磁学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 静电学
    for n in ["库仑力", "电场", "电势", "电势能", "平行板电容",
              "电容储能", "电容电荷", "高斯通量", "电偶极矩"]:
        names.append(f"电_{n}")
    # 直流电路
    for n in ["电压", "电流", "电阻", "串联电阻", "并联电阻",
              "功率", "功率热", "功率压", "焦耳热"]:
        names.append(f"电路_{n}")
    # 磁场
    for n in ["洛伦兹力", "安培力", "直导线磁场", "圆线圈中心磁场",
              "螺线管磁场", "磁通量", "回旋半径", "回旋频率"]:
        names.append(f"磁_{n}")
    # 电磁感应
    for n in ["法拉第电动势", "动生电动势", "自感电动势",
              "磁场能量", "互感", "RL时间常数"]:
        names.append(f"感应_{n}")
    # 交流电路
    for n in ["感抗", "容抗", "阻抗", "谐振频率", "有效值",
              "峰值", "功率因数", "有功功率", "视在功率",
              "无功功率", "品质因数"]:
        names.append(f"交流_{n}")
    # 物理常量
    for n in ["ε0_真空介电常数", "k_静电力常量", "μ0_真空磁导率", "e_基本电荷"]:
        names.append(n)
    # 数据库常量
    for name in RESISTIVITIES:
        names.append(f"电阻率_{name}")
    for name in DIELECTRIC_CONSTANTS:
        names.append(f"介电常数_{name}")
    return names
