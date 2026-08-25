"""Matha 机械领域模块：流体力学（Fluid Mechanics）。

基于运动学 + 动力学 + mathlib 数学地基，演化流体力学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

四大子领域：

一、流体静力学（Fluid Statics）
  1) 静水压强：p = ρgh
  2) 帕斯卡定律：F2/F1 = A2/A1（液压机原理）
  3) 浮力（阿基米德原理）：F_b = ρgV
  4) 浮力稳定性判断（密度比较）
  5) 壁面静水压力（矩形壁）：F = ½ρgh²·b

二、流体运动学（Fluid Kinematics）
  1) 体积流量：Q = A·v
  2) 质量流量：ṁ = ρ·Q = ρ·A·v
  3) 连续性方程：A1·v1 = A2·v2
  4) 管道截面面积（圆管/矩形管）

三、流体动力学（Fluid Dynamics）
  1) 伯努利方程：p₁ + ½ρv₁² + ρgh₁ = p₂ + ½ρv₂² + ρgh₂
  2) 托里拆利定理：v = √(2gh)（小孔出流）
  3) 文丘里流量计：由压差求流速
  4) 皮托管测速：v = √(2Δp/ρ)
  5) 雷诺数：Re = ρvD/μ = vD/ν（层流/湍流判据）

四、粘性流动（Viscous Flow）
  1) 牛顿粘性定律：τ = μ·du/dy
  2) 泊肃叶定律（层流管流）：Q = πr⁴Δp/(8μL)
  3) 斯托克斯定律（小球沉降）：F_d = 6πηrv
  4) 终端速度：v_t = 2r²g(ρ_s-ρ_f)/(9η)
  5) 达西-韦斯巴赫方程（沿程水头损失）：h_f = f·(L/D)·v²/(2g)

设计原则：
  - 所有函数返回纯数值（float/int），不抛语义错（除以零等 Python 自身抛）
  - 多参函数一律 _curry2/_curry3/_curry4 封装，与 Matha 柯里化语义一致
  - 前缀 流体_ / 流_ / 粘_ 区分子领域
  - 与运动学/动力学共享 mathlib 的 sin/cos/sqrt/pi/g 等
"""

from __future__ import annotations
import math


# ============================================================
# 柯里化工具（与 mechanics.py / dynamics.py 语义一致）
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
# 一、流体静力学（Fluid Statics）
# ============================================================

# 静水压强 p = ρgh
def _静水_压强(rho, h, g_val): return rho * g_val * h          # p = ρgh  Pa
# 液体深度（由压强反求）：h = p/(ρg)
def _静水_深度(p, rho, g_val): return p / (rho * g_val)
# 帕斯卡定律（液压机）：F2 = F1 * A2/A1
def _帕斯卡_液压力(F1, A1, A2): return F1 * A2 / A1
# 浮力（阿基米德原理）：F_b = ρgV
def _浮力_浮力(rho, V, g_val): return rho * g_val * V           # F_b = ρgV  N
# 浮力判断：ρ物体 vs ρ液体 → 沉/浮/悬浮
def _浮力_漂浮判断(rho_obj, rho_fluid): return rho_obj < rho_fluid  # True=浮, False=沉
# 矩形壁面静水总压力：F = ½ρgh²·b（h 为水深，b 为壁宽）
def _静水_壁面总压力(rho, h, b, g_val): return 0.5 * rho * g_val * h * h * b


# ============================================================
# 二、流体运动学（Fluid Kinematics）
# ============================================================

# 圆管截面积 A = πr² = πD²/4
def _管道_圆管面积(d): return math.pi * d * d / 4               # A = πD²/4  m²
# 矩形管截面积 A = w × h
def _管道_矩形面积(w, h): return w * h                           # A = w·h  m²
# 体积流量 Q = A·v
def _流量_体积流量(A, v): return A * v                           # Q = Av  m³/s
# 质量流量 ṁ = ρ·A·v
def _流量_质量流量(rho, A, v): return rho * A * v                # ṁ = ρAv  kg/s
# 连续性方程：A1·v1 = A2·v2 → v2 = A1·v1/A2
def _流量_连续性速度(A1, v1, A2): return A1 * v1 / A2
# 由流量求流速：v = Q/A
def _流量_流速(Q, A): return Q / A


# ============================================================
# 三、流体动力学（Fluid Dynamics）
# ============================================================

# 伯努利方程：p₁ + ½ρv₁² + ρgh₁ = p₂ + ½ρv₂² + ρgh₂
#   → p₂ = p₁ + ½ρ(v₁² - v₂²) + ρg(h₁ - h₂)
def _伯努利_压强2(p1, rho, v1, h1, v2, h2, g_val):
    return p1 + 0.5 * rho * (v1 * v1 - v2 * v2) + rho * g_val * (h1 - h2)

# 托里拆利定理：v = √(2gh)（小孔出流速度）
def _伯努利_小孔流速(h, g_val): return math.sqrt(2 * g_val * h)

# 文丘里流量计：由压差求流速 v1 = √(2Δp / (ρ(A1²/A2² - 1)))
def _伯努利_文丘里流速(dp, rho, A1, A2):
    return math.sqrt(2 * dp / (rho * (A1 * A1 / (A2 * A2) - 1)))

# 皮托管测速：v = √(2Δp/ρ)
def _伯努利_皮托管(dp, rho): return math.sqrt(2 * dp / rho)

# 雷诺数：Re = ρvD/μ
def _流_雷诺数(rho, v, D, mu): return rho * v * D / mu         # Re（无量纲）
# 雷诺数（运动粘度形式）：Re = vD/ν
def _流_雷诺数运动(v, D, nu): return v * D / nu
# 流态判断：Re < 2300 层流，Re > 4000 湍流，之间过渡
def _流_流态判断(Re):
    if Re < 2300:
        return "层流"
    elif Re > 4000:
        return "湍流"
    else:
        return "过渡"


# ============================================================
# 四、粘性流动（Viscous Flow）
# ============================================================

# 牛顿粘性定律：τ = μ·du/dy
def _粘_粘性切应力(mu, du, dy): return mu * du / dy             # τ = μ·du/dy  Pa
# 泊肃叶定律（层流圆管流量）：Q = πr⁴Δp/(8μL)
def _粘_泊肃叶流量(r, dp, mu, L):
    return math.pi * r ** 4 * dp / (8 * mu * L)                 # Q  m³/s
# 泊肃叶流速（平均）：v_avg = Q/A = r²Δp/(8μL)
def _粘_泊肃叶流速(r, dp, mu, L):
    return r * r * dp / (8 * mu * L)                            # v  m/s
# 斯托克斯阻力（小球在粘性流体中低速运动）：F_d = 6πηrv
def _粘_斯托克斯阻力(eta, r, v): return 6 * math.pi * eta * r * v  # F_d  N
# 终端沉降速度（重力 + 浮力 + 斯托克斯阻力平衡）
#   v_t = 2r²g(ρ_s - ρ_f) / (9η)
def _粘_终端速度(r, g_val, rho_s, rho_f, eta):
    return 2 * r * r * g_val * (rho_s - rho_f) / (9 * eta)      # v_t  m/s
# 达西-韦斯巴赫沿程水头损失：h_f = f·(L/D)·v²/(2g)
def _粘_达西水头损失(f, L, D, v, g_val):
    return f * (L / D) * v * v / (2 * g_val)                    # h_f  m


# ============================================================
# 常用流体密度数据库（标准值，SI 单位 kg/m³）
# ============================================================

FLUID_DENSITIES: dict[str, float] = {
    "水": 1000.0,
    "海水": 1025.0,
    "空气_20C": 1.205,
    "甘油": 1260.0,
    "乙醇": 789.0,
    "汞": 13546.0,
    "汽油": 730.0,
    "机油": 900.0,
}

# 常用流体动力粘度（Pa·s，20°C 标准值）
FLUID_VISCOSITIES: dict[str, float] = {
    "水_20C": 1.002e-3,
    "空气_20C": 1.81e-5,
    "甘油_20C": 1.412,
    "乙醇_20C": 1.20e-3,
    "机油_20C": 0.8,
    "汞_20C": 1.55e-3,
}


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_fluid(builtins: dict) -> None:
    """将流体力学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（dynamics 之后）。
    命名规则：
      - 流体静力学：前缀 流体_ / 前缀 浮力_
      - 流体运动学：前缀 流量_ / 前缀 管道_
      - 流体动力学：前缀 伯努利_ / 前缀 流_
      - 粘性流动：前缀 粘_
    """
    # --- 流体静力学 ---
    builtins["流体_静水压强"] = _curry3(_静水_压强)              # 流体_静水压强(ρ)(h)(g)
    builtins["流体_静水深度"] = _curry3(_静水_深度)              # 流体_静水深度(p)(ρ)(g)
    builtins["流体_液压力"] = _curry3(_帕斯卡_液压力)            # 流体_液压力(F1)(A1)(A2)
    builtins["浮力_浮力"] = _curry3(_浮力_浮力)                  # 浮力_浮力(ρ)(V)(g)
    builtins["浮力_漂浮判断"] = _curry2(_浮力_漂浮判断)          # 浮力_漂浮判断(ρ物)(ρ液)
    builtins["流体_壁面总压力"] = _curry4(_静水_壁面总压力)      # 流体_壁面总压力(ρ)(h)(b)(g)

    # --- 流体运动学 ---
    builtins["管道_圆管面积"] = _管道_圆管面积                   # 管道_圆管面积(D)
    builtins["管道_矩形面积"] = _curry2(_管道_矩形面积)          # 管道_矩形面积(w)(h)
    builtins["流量_体积流量"] = _curry2(_流量_体积流量)          # 流量_体积流量(A)(v)
    builtins["流量_质量流量"] = _curry3(_流量_质量流量)          # 流量_质量流量(ρ)(A)(v)
    builtins["流量_连续性速度"] = _curry3(_流量_连续性速度)      # 流量_连续性速度(A1)(v1)(A2)
    builtins["流量_流速"] = _curry2(_流量_流速)                  # 流量_流速(Q)(A)

    # --- 流体动力学 ---
    # 伯努利_压强2 是 7 参函数，用 curry4 + curry3 组合
    builtins["伯努利_压强2"] = _curry4(
        lambda p1, rho, v1, h1: _curry3(
            lambda v2, h2, g_val: _伯努利_压强2(p1, rho, v1, h1, v2, h2, g_val)
        )
    )
    builtins["伯努利_小孔流速"] = _curry2(_伯努利_小孔流速)      # 伯努利_小孔流速(h)(g)
    builtins["伯努利_文丘里流速"] = _curry4(_伯努利_文丘里流速)  # (Δp)(ρ)(A1)(A2)
    builtins["伯努利_皮托管"] = _curry2(_伯努利_皮托管)          # 伯努利_皮托管(Δp)(ρ)
    builtins["流_雷诺数"] = _curry4(_流_雷诺数)                  # 流_雷诺数(ρ)(v)(D)(μ)
    builtins["流_雷诺数运动"] = _curry3(_流_雷诺数运动)          # 流_雷诺数运动(v)(D)(ν)
    builtins["流_流态判断"] = _流_流态判断                       # 流_流态判断(Re)

    # --- 粘性流动 ---
    builtins["粘_粘性切应力"] = _curry3(_粘_粘性切应力)          # 粘_粘性切应力(μ)(du)(dy)
    builtins["粘_泊肃叶流量"] = _curry4(_粘_泊肃叶流量)          # 粘_泊肃叶流量(r)(Δp)(μ)(L)
    builtins["粘_泊肃叶流速"] = _curry4(_粘_泊肃叶流速)          # 粘_泊肃叶流速(r)(Δp)(μ)(L)
    builtins["粘_斯托克斯阻力"] = _curry3(_粘_斯托克斯阻力)      # 粘_斯托克斯阻力(η)(r)(v)
    builtins["粘_终端速度"] = _curry5(_粘_终端速度)              # 粘_终端速度(r)(g)(ρs)(ρf)(η)
    builtins["粘_达西水头损失"] = _curry5(_粘_达西水头损失)      # 粘_达西水头损失(f)(L)(D)(v)(g)

    # --- 流体密度常量 ---
    for name, val in FLUID_DENSITIES.items():
        builtins[f"密度_{name}"] = val

    # --- 流体粘度常量 ---
    for name, val in FLUID_VISCOSITIES.items():
        builtins[f"粘度_{name}"] = val


def _curry5(func):
    """五参 → 柯里化 f(a)(b)(c)(d)(e)。"""
    def w1(a):
        def w2(b):
            def w3(c):
                def w4(d):
                    return lambda e: func(a, b, c, d, e)
                return w4
            return w3
        return w2
    return w1


def _fluid_symtab_names() -> list[str]:
    """返回流体力学所有内建名（用于语义分析注册，避免报未定义）。"""
    names: list[str] = []
    # 流体静力学
    for n in ["静水压强", "静水深度", "液压力", "壁面总压力"]:
        names.append(f"流体_{n}")
    for n in ["浮力", "漂浮判断"]:
        names.append(f"浮力_{n}")
    # 流体运动学
    for n in ["圆管面积", "矩形面积"]:
        names.append(f"管道_{n}")
    for n in ["体积流量", "质量流量", "连续性速度", "流速"]:
        names.append(f"流量_{n}")
    # 流体动力学
    for n in ["压强2", "小孔流速", "文丘里流速", "皮托管"]:
        names.append(f"伯努利_{n}")
    for n in ["雷诺数", "雷诺数运动", "流态判断"]:
        names.append(f"流_{n}")
    # 粘性流动
    for n in ["粘性切应力", "泊肃叶流量", "泊肃叶流速", "斯托克斯阻力", "终端速度", "达西水头损失"]:
        names.append(f"粘_{n}")
    # 流体密度常量
    for name in FLUID_DENSITIES:
        names.append(f"密度_{name}")
    # 流体粘度常量
    for name in FLUID_VISCOSITIES:
        names.append(f"粘度_{name}")
    return names
