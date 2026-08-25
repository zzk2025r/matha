"""Matha 机械领域模块：核物理（Nuclear Physics）。

基于量子力学 + 天体力学 + 电磁学 + mathlib 数学地基，演化核物理功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、核结合能与质量亏损（Nuclear Binding Energy & Mass Defect）
  1) 质量亏损：Δm = Z·mp + N·mn - M_nucleus
  2) 结合能：B = Δm·c²
  3) 比结合能：B/A
  4) 半经验质量公式（Weizsäcker）：B = aV·A - aS·A^(2/3) - aC·Z²/A^(1/3) - aA·(A-2Z)²/A + δ
  5) 结合能曲线分析

二、放射性衰变（Radioactive Decay）
  1) 衰变定律：N(t) = N₀·e^(-λt)
  2) 半衰期：T₁/₂ = ln2/λ
  3) 平均寿命：τ = 1/λ
  4) 活度：A = λN
  5) 碳-14年代测定
  6) 衰变链

三、核反应（Nuclear Reactions）
  1) Q值：Q = (m_initial - m_final)·c²
  2) 阈能：E_th = Q·(1 + m_a/m_A)（吸热反应）
  3) 反应能阈
  4) 裂变能量释放
  5) 聚变能量释放

四、粒子物理（Particle Physics）
  1) 粒子动能（相对论）：K = (γ-1)mc²
  2) 洛伦兹因子：γ = 1/√(1-β²)
  3) 相对论动量：p = γmv
  4) 质能等价：E = mc²
  5) 德布罗意波长（相对论）
  6) 粒子相互作用截面

五、核能与反应堆（Nuclear Energy & Reactors）
  1) 反应堆功率
  2) 临界条件
  3) 增殖系数
  4) 中子慢化
  5) 辐射剂量
  6) 屏蔽计算

设计原则：
  - 所有角度输入/输出均为弧度
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 核_ / 衰变_ / 反应_ / 粒子_ / 反应堆_ 区分子领域
  - 核物理常量与同位素数据作为常量注册
"""

from __future__ import annotations
import math


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


# ============================================================
# 物理常量
# ============================================================

# 光速 c = 2.998e8 m/s
C_LIGHT = 2.99792458e8
# 质子质量 mp = 1.6726e-27 kg
M_PROTON = 1.67262192369e-27
# 中子质量 mn = 1.6749e-27 kg
M_NEUTRON = 1.67492749804e-27
# 电子质量 me = 9.109e-31 kg
M_ELECTRON = 9.1093837015e-31
# 原子质量单位 u = 1.6605e-27 kg
U_ATOMIC = 1.66053906660e-27
# 基本电荷 e = 1.602e-19 C
E_CHARGE = 1.602176634e-19
# 阿伏伽德罗常数 N_A
N_A = 6.02214076e23
# 玻尔兹曼常数 k_B = 1.381e-23 J/K
K_B = 1.380649e-23
# 普朗克常量 h
H_PLANCK = 6.62607015e-34
# 约化普朗克常量 ℏ
HBAR = H_PLANCK / (2 * math.pi)

# u → MeV/c² 换算: 1 u = 931.494 MeV/c²
U_TO_MEV = 931.494
# 1 eV = 1.602e-19 J
EV_TO_J = E_CHARGE
# 1 MeV = 1.602e-13 J
MEV_TO_J = E_CHARGE * 1e6

# 原子质量单位能量当量
U_C2 = U_ATOMIC * C_LIGHT ** 2  # J


# ============================================================
# 一、核结合能与质量亏损（Nuclear Binding Energy & Mass Defect）
# ============================================================

# 质量亏损：Δm = Z·mp + N·mn - M_nucleus（kg）
def _核_质量亏损(Z, N, M_nucleus):
    return Z * M_PROTON + N * M_NEUTRON - M_nucleus

# 结合能：B = Δm·c²（Joule）
def _核_结合能J(delta_m): return delta_m * C_LIGHT ** 2
# 结合能（MeV）：B = Δm·c² / (1.602e-13)
def _核_结合能MeV(delta_m): return delta_m * C_LIGHT ** 2 / MEV_TO_J
# 比结合能：B/A（MeV/核子）
def _核_比结合能(delta_m, A): return delta_m * C_LIGHT ** 2 / (MEV_TO_J * A)
# 质量亏损（由原子质量单位 u）：Δm(u) → 结合能(MeV)
def _核_结合能由U(delta_m_u): return delta_m_u * U_TO_MEV

# 半经验质量公式（Weizsäcker）：B(MeV) = aV·A - aS·A^(2/3) - aC·Z²/A^(1/3) - aA·(A-2Z)²/A + δ
def _核_半经验结合能(A, Z):
    """Weizsäcker 半经验质量公式，返回结合能（MeV）。"""
    aV = 15.75   # 体积能系数
    aS = 17.8    # 表面能系数
    aC = 0.711   # 库仑能系数
    aA = 23.7    # 对称能系数
    N = A - Z
    # 体积能
    B_vol = aV * A
    # 表面能
    B_surf = aS * A ** (2.0 / 3)
    # 库仑能
    B_coul = aC * Z ** 2 / A ** (1.0 / 3)
    # 对称能
    B_sym = aA * (A - 2 * Z) ** 2 / A
    # 配对能
    if A % 2 == 0:
        if Z % 2 == 0:
            delta = 11.18 / A ** 0.5  # 偶-偶
        else:
            delta = -11.18 / A ** 0.5  # 偶-奇
    else:
        delta = 0.0  # 奇A
    return B_vol - B_surf - B_coul - B_sym + delta

# 比结合能（Weizsäcker）：B/A
def _核_半经验比结合能(A, Z): return _核_半经验结合能(A, Z) / A

# α衰变 Q 值：Q = (M_parent - M_daughter - M_alpha)·c²
def _核_α衰变Q(M_parent, M_daughter, M_alpha):
    return (M_parent - M_daughter - M_alpha) * C_LIGHT ** 2 / MEV_TO_J

# β衰变 Q 值（β⁻）：Q = (M_parent - M_daughter)·c²
def _核_β衰变Q(M_parent, M_daughter):
    return (M_parent - M_daughter) * C_LIGHT ** 2 / MEV_TO_J


# ============================================================
# 二、放射性衰变（Radioactive Decay）
# ============================================================

# 衰变定律：N(t) = N₀·e^(-λt)
def _衰变_剩余核数(N0, lam, t): return N0 * math.exp(-lam * t)
# 衰变率/活度：A = λN
def _衰变_活度(lam, N): return lam * N
# 半衰期：T₁/₂ = ln2/λ
def _衰变_半衰期(lam): return math.log(2) / lam
# 衰变常数由半衰期：λ = ln2/T₁/₂
def _衰变_衰变常数(T_half): return math.log(2) / T_half
# 平均寿命：τ = 1/λ
def _衰变_平均寿命(lam): return 1.0 / lam
# 已衰变核数：N_decayed = N₀ - N(t) = N₀(1 - e^(-λt))
def _衰变_已衰变数(N0, lam, t): return N0 * (1 - math.exp(-lam * t))
# 双衰变（两个子体同时衰变）
def _衰变_双衰变剩余(N0, lam1, lam2, t):
    return N0 * math.exp(-lam1 * t) * math.exp(-lam2 * t)

# 碳-14年代测定：t = (1/λ)·ln(N₀/N)
def _衰变_碳14测年(N0, N_now):
    """碳-14年代测定，半衰期 5730 年。返回年代（年）。"""
    T_half_C14 = 5730 * 3.156e7  # 秒
    lam = math.log(2) / T_half_C14
    return math.log(N0 / N_now) / lam / 3.156e7  # 返回年

# 放射性活度单位转换：1 Ci = 3.7e10 Bq
def _衰变_Ci转Bq(Ci): return Ci * 3.7e10
def _衰变_Bq转Ci(Bq): return Bq / 3.7e10


# ============================================================
# 三、核反应（Nuclear Reactions）
# ============================================================

# Q值（由质量差，kg → MeV）：Q = (m_initial - m_final)·c²
def _反应_Q值(m_initial, m_final):
    return (m_initial - m_final) * C_LIGHT ** 2 / MEV_TO_J

# Q值（由原子质量单位 u）：Q = Δm(u) × 931.494 MeV
def _反应_Q值U(m_initial_u, m_final_u):
    return (m_initial_u - m_final_u) * U_TO_MEV

# 阈能（吸热反应）：E_th = -Q·(1 + m_a/m_A)（Q<0时）
def _反应_阈能(Q_MeV, m_a, m_A):
    """Q < 0 时的反应阈能（MeV）。"""
    if Q_MeV >= 0:
        return 0.0
    return -Q_MeV * (1 + m_a / m_A)

# 裂变能量释放（每个U-235裂变约200 MeV）
def _反应_裂变能(n, E_per_fission_MeV=200.0):
    """n 次裂变释放的能量（MeV）。"""
    return n * E_per_fission_MeV

# 聚变能量释放（D-T反应约17.6 MeV/次）
def _反应_聚变能(n, E_per_fusion_MeV=17.6):
    """n 次聚变释放的能量（MeV）。"""
    return n * E_per_fusion_MeV

# 裂变功率：P = n·E/Δt（W）
def _反应_裂变功率(rate, E_per_fission_MeV=200.0):
    """rate = 裂变率（次/秒），返回功率（W）。"""
    return rate * E_per_fission_MeV * MEV_TO_J

# 临界质量
def _反应_临界质量估算(rho, sigma_f, nu, v_th):
    """简化的临界质量估算（kg），rho密度, sigma_f裂变截面, nu每次裂变中子数, v_th热中子速度。"""
    # 极简化模型，仅量级估计
    M_critical = 4.0 / 3.0 * math.pi * rho * (1.0 / (sigma_f * nu * rho / M_PROTON)) ** 3
    return M_critical


# ============================================================
# 四、粒子物理（Particle Physics）
# ============================================================

# 洛伦兹因子：γ = 1/√(1-β²)，β = v/c
def _粒子_洛伦兹因子(v): return 1.0 / math.sqrt(1 - (v / C_LIGHT) ** 2)
# 相对论总能量：E = γmc²
def _粒子_相对论总能量(m, v): return _粒子_洛伦兹因子(v) * m * C_LIGHT ** 2
# 相对论动能：K = (γ-1)mc²
def _粒子_相对论动能(m, v):
    gamma = _粒子_洛伦兹因子(v)
    return (gamma - 1) * m * C_LIGHT ** 2
# 相对论动量：p = γmv
def _粒子_相对论动量(m, v):
    gamma = _粒子_洛伦兹因子(v)
    return gamma * m * v
# 质能等价：E = mc²
def _粒子_质能等价(m): return m * C_LIGHT ** 2
# 质能等价（MeV）
def _粒子_质能等价MeV(m): return m * C_LIGHT ** 2 / MEV_TO_J
# 德布罗意波长（相对论）：λ = h/p
def _粒子_德布罗意波长相对论(m, v):
    p = _粒子_相对论动量(m, v)
    return H_PLANCK / p
# 相对论速度（由动能）：v = c√(1 - 1/(1+K/(mc²))²)
def _粒子_速度由动能(K, m):
    ratio = 1 + K / (m * C_LIGHT ** 2)
    return C_LIGHT * math.sqrt(1 - 1 / ratio ** 2)
# 相对论动量（由总能量和静质量）：p = √(E² - (mc²)²)/c
def _粒子_动量由能量(E_total, m):
    return math.sqrt(E_total ** 2 - (m * C_LIGHT ** 2) ** 2) / C_LIGHT


# ============================================================
# 五、核能与反应堆（Nuclear Energy & Reactors）
# ============================================================

# 有效增殖系数：k_eff = k_∞ / (1 + L²B²)
def _反应堆_有效增殖系数(k_inf, L2, B2): return k_inf / (1 + L2 * B2)
# 临界条件：k_eff = 1
def _反应堆_临界判断(k_eff): return abs(k_eff - 1.0) < 1e-10
# 反应性：ρ = (k_eff - 1) / k_eff
def _反应堆_反应性(k_eff): return (k_eff - 1) / k_eff
# 反应堆周期：T = l / ρ（l 为中子寿命）
def _反应堆_周期(l_neutron, rho): return l_neutron / rho if rho != 0 else float('inf')
# 中子慢化比：ξ = 1 + ((A-1)²/(2A))·ln((A-1)/(A+1))
def _反应堆_慢化比(A):
    if A == 1:
        return 1.0
    return 1 + ((A - 1) ** 2 / (2 * A)) * math.log((A - 1) / (A + 1))
# 慢化到热能所需碰撞次数：n = ln(E0/Eth)/ξ
def _反应堆_慢化碰撞数(E0, E_th, A):
    xi = _反应堆_慢化比(A)
    return math.log(E0 / E_th) / xi
# 辐射剂量（吸收剂量）：D = E/m（Gy = J/kg）
def _反应堆_吸收剂量(energy, mass): return energy / mass
# 当量剂量：H = D·w_R（Sv），w_R 为辐射权重因子
def _反应堆_当量剂量(D, w_R): return D * w_R
# 半减弱层（HVL）：d = ln2/μ
def _反应堆_半减弱层(mu): return math.log(2) / mu
# 辐射屏蔽后强度：I = I₀·e^(-μx)
def _反应堆_屏蔽强度(I0, mu, x): return I0 * math.exp(-mu * x)


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_nuclear(builtins: dict) -> None:
    """将核物理内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（celestial 之后）。
    """
    # --- 核结合能与质量亏损 ---
    builtins["核_质量亏损"] = _curry3(_核_质量亏损)                # 核_质量亏损(Z)(N)(M核)
    builtins["核_结合能J"] = _核_结合能J                           # 核_结合能J(Δm)
    builtins["核_结合能MeV"] = _核_结合能MeV                       # 核_结合能MeV(Δm)
    builtins["核_比结合能"] = _curry2(_核_比结合能)                # 核_比结合能(Δm)(A)
    builtins["核_结合能由U"] = _核_结合能由U                       # 核_结合能由U(Δm_u)
    builtins["核_半经验结合能"] = _curry2(_核_半经验结合能)        # 核_半经验结合能(A)(Z)
    builtins["核_半经验比结合能"] = _curry2(_核_半经验比结合能)    # 核_半经验比结合能(A)(Z)
    builtins["核_α衰变Q"] = _curry3(_核_α衰变Q)                   # 核_α衰变Q(M母)(M子)(Mα)
    builtins["核_β衰变Q"] = _curry2(_核_β衰变Q)                   # 核_β衰变Q(M母)(M子)

    # --- 放射性衰变 ---
    builtins["衰变_剩余核数"] = _curry3(_衰变_剩余核数)            # 衰变_剩余核数(N0)(λ)(t)
    builtins["衰变_活度"] = _curry2(_衰变_活度)                    # 衰变_活度(λ)(N)
    builtins["衰变_半衰期"] = _衰变_半衰期                         # 衰变_半衰期(λ)
    builtins["衰变_衰变常数"] = _衰变_衰变常数                     # 衰变_衰变常数(T½)
    builtins["衰变_平均寿命"] = _衰变_平均寿命                     # 衰变_平均寿命(λ)
    builtins["衰变_已衰变数"] = _curry3(_衰变_已衰变数)            # 衰变_已衰变数(N0)(λ)(t)
    builtins["衰变_双衰变剩余"] = _curry4(_衰变_双衰变剩余)        # 衰变_双衰变剩余(N0)(λ1)(λ2)(t)
    builtins["衰变_碳14测年"] = _curry2(_衰变_碳14测年)            # 衰变_碳14测年(N0)(N_now)
    builtins["衰变_Ci转Bq"] = _衰变_Ci转Bq                         # 衰变_Ci转Bq(Ci)
    builtins["衰变_Bq转Ci"] = _衰变_Bq转Ci                         # 衰变_Bq转Ci(Bq)

    # --- 核反应 ---
    builtins["反应_Q值"] = _curry2(_反应_Q值)                     # 反应_Q值(m初)(m末)
    builtins["反应_Q值U"] = _curry2(_反应_Q值U)                   # 反应_Q值U(m初_u)(m末_u)
    builtins["反应_阈能"] = _curry3(_反应_阈能)                    # 反应_阈能(Q_MeV)(ma)(mA)
    builtins["反应_裂变能"] = _curry2(_反应_裂变能)                # 反应_裂变能(n)(E每次MeV)
    builtins["反应_聚变能"] = _curry2(_反应_聚变能)                # 反应_聚变能(n)(E每次MeV)
    builtins["反应_裂变功率"] = _curry2(_反应_裂变功率)            # 反应_裂变功率(裂变率)(E每次MeV)

    # --- 粒子物理 ---
    builtins["粒子_洛伦兹因子"] = _粒子_洛伦兹因子                  # 粒子_洛伦兹因子(v)
    builtins["粒子_相对论总能量"] = _curry2(_粒子_相对论总能量)    # 粒子_相对论总能量(m)(v)
    builtins["粒子_相对论动能"] = _curry2(_粒子_相对论动能)        # 粒子_相对论动能(m)(v)
    builtins["粒子_相对论动量"] = _curry2(_粒子_相对论动量)        # 粒子_相对论动量(m)(v)
    builtins["粒子_质能等价"] = _粒子_质能等价                     # 粒子_质能等价(m)
    builtins["粒子_质能等价MeV"] = _粒子_质能等价MeV               # 粒子_质能等价MeV(m)
    builtins["粒子_德布罗意波长相对论"] = _curry2(_粒子_德布罗意波长相对论)  # 粒子_德布罗意波长相对论(m)(v)
    builtins["粒子_速度由动能"] = _curry2(_粒子_速度由动能)        # 粒子_速度由动能(K)(m)
    builtins["粒子_动量由能量"] = _curry2(_粒子_动量由能量)        # 粒子_动量由能量(E)(m)

    # --- 核能与反应堆 ---
    builtins["反应堆_有效增殖系数"] = _curry3(_反应堆_有效增殖系数)  # 反应堆_有效增殖系数(k∞)(L²)(B²)
    builtins["反应堆_临界判断"] = _反应堆_临界判断                 # 反应堆_临界判断(k_eff)
    builtins["反应堆_反应性"] = _反应堆_反应性                     # 反应堆_反应性(k_eff)
    builtins["反应堆_周期"] = _curry2(_反应堆_周期)                # 反应堆_周期(l中子)(ρ)
    builtins["反应堆_慢化比"] = _反应堆_慢化比                     # 反应堆_慢化比(A)
    builtins["反应堆_慢化碰撞数"] = _curry3(_反应堆_慢化碰撞数)    # 反应堆_慢化碰撞数(E0)(Eth)(A)
    builtins["反应堆_吸收剂量"] = _curry2(_反应堆_吸收剂量)        # 反应堆_吸收剂量(E)(m)
    builtins["反应堆_当量剂量"] = _curry2(_反应堆_当量剂量)        # 反应堆_当量剂量(D)(wR)
    builtins["反应堆_半减弱层"] = _反应堆_半减弱层                 # 反应堆_半减弱层(μ)
    builtins["反应堆_屏蔽强度"] = _curry3(_反应堆_屏蔽强度)        # 反应堆_屏蔽强度(I0)(μ)(x)

    # --- 物理常量 ---
    builtins["mp_质子质量"] = M_PROTON
    builtins["mn_中子质量"] = M_NEUTRON
    builtins["me_电子质量"] = M_ELECTRON
    builtins["u_原子质量单位"] = U_ATOMIC
    builtins["eV_电子伏特"] = EV_TO_J
    builtins["MeV_兆电子伏特"] = MEV_TO_J
    builtins["u_MeV换算"] = U_TO_MEV


def _nuclear_symtab_names() -> list[str]:
    """返回核物理所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 核结合能与质量亏损
    for n in ["质量亏损", "结合能J", "结合能MeV", "比结合能",
              "结合能由U", "半经验结合能", "半经验比结合能",
              "α衰变Q", "β衰变Q"]:
        names.append(f"核_{n}")
    # 放射性衰变
    for n in ["剩余核数", "活度", "半衰期", "衰变常数",
              "平均寿命", "已衰变数", "双衰变剩余",
              "碳14测年", "Ci转Bq", "Bq转Ci"]:
        names.append(f"衰变_{n}")
    # 核反应
    for n in ["Q值", "Q值U", "阈能", "裂变能",
              "聚变能", "裂变功率"]:
        names.append(f"反应_{n}")
    # 粒子物理
    for n in ["洛伦兹因子", "相对论总能量", "相对论动能",
              "相对论动量", "质能等价", "质能等价MeV",
              "德布罗意波长相对论", "速度由动能", "动量由能量"]:
        names.append(f"粒子_{n}")
    # 核能与反应堆
    for n in ["有效增殖系数", "临界判断", "反应性", "周期",
              "慢化比", "慢化碰撞数", "吸收剂量",
              "当量剂量", "半减弱层", "屏蔽强度"]:
        names.append(f"反应堆_{n}")
    # 物理常量
    for n in ["mp_质子质量", "mn_中子质量", "me_电子质量",
              "u_原子质量单位", "eV_电子伏特",
              "MeV_兆电子伏特", "u_MeV换算"]:
        names.append(n)
    return names
