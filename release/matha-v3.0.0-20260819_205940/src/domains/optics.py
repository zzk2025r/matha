"""Matha 机械领域模块：光学（Optics）。

基于力学 + 电磁学 + 声学 + mathlib 数学地基，演化光学功能。
所有函数以普通 Python callable 注册到解释器 builtins，Matha 代码可直接调用。

五大子领域：

一、几何光学（Geometric Optics）
  1) 折射定律（斯涅尔定律）：n₁sinθ₁ = n₂sinθ₂
  2) 全反射临界角：sinθc = n₂/n₁
  3) 球面镜焦距：f = R/2
  4) 球面镜成像：1/v + 1/u = 1/f
  5) 薄透镜成像：1/v - 1/u = 1/f（笛卡尔符号）
  6) 透镜焦距（造焦公式）：1/f = (n-1)(1/R₁ - 1/R₂)
  7) 放大率：m = -v/u
  8) 光速与折射率：v = c/n

二、波动光学（Wave Optics）
  1) 双缝干涉条纹间距：Δy = λD/d
  2) 薄膜干涉（垂直入射）：2nd = mλ（亮纹）
  3) 单缝衍射暗纹位置：a·sinθ = mλ
  4) 光栅方程：d·sinθ = mλ
  5) 光栅分辨本领：R = mN
  6) 马吕斯定律：I = I₀cos²θ
  7) 布儒斯特角：tanθB = n₂/n₁

三、光度学（Photometry）
  1) 光通量与发光强度：Φ = 4πI（各向同性）
  2) 照度（平方反比）：E = I/r²
  3) 照度（斜入射）：E = (I/r²)cosθ
  4) 光亮度：L = I/A
  5) 光视效能：K = Φ/P

四、光学仪器（Optical Instruments）
  1) 放大镜放大率：M = 25/f + 1（正常眼）
  2) 显微镜放大率：M = (L/f_o)(25/f_e)
  3) 望远镜放大率：M = -f_o/f_e
  4) 数值孔径：NA = n·sinα
  5) 最小分辨角（瑞利判据）：θ = 1.22λ/D
  6) 眼睛近点/远点调节

五、色散与光谱（Dispersion & Spectrum）
  1) 柯西方程：n(λ) = A + B/λ²
  2) 色散率：dn/dλ = -2B/λ³
  3) 光子能量：E = hf = hc/λ
  4) 光子动量：p = h/λ
  5) 红移：z = (λ_obs - λ_emit)/λ_emit
  6) 多普勒红移速度：v = zc（非相对论）

设计原则：
  - 所有角度输入/输出均为弧度（rad）
  - 多参函数一律 _curry2/_curry3/_curry4 封装
  - 前缀 几何_ / 波动_ / 光度_ / 仪器_ / 色散_ 区分子领域
  - 常用折射率/光波长作为常量注册
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

# 真空光速 c = 2.998e8 m/s
C_LIGHT = 2.99792458e8
# 普朗克常量 h = 6.626e-34 J·s
H_PLANCK = 6.62607015e-34
# 光视效能最大值 K_m = 683 lm/W
K_MAX = 683.0


# ============================================================
# 一、几何光学（Geometric Optics）
# ============================================================

# 折射定律（斯涅尔定律）：n₁sinθ₁ = n₂sinθ₂ → θ₂ = arcsin(n₁sinθ₁/n₂)
def _几何_折射角(n1, theta1, n2): return math.asin(n1 * math.sin(theta1) / n2)
# 全反射临界角：sinθc = n₂/n₁ → θc = arcsin(n₂/n₁)（n₁ > n₂）
def _几何_全反射角(n1, n2): return math.asin(n2 / n1) if n1 > n2 else math.pi / 2
# 球面镜焦距：f = R/2
def _几何_球面镜焦距(R): return R / 2
# 球面镜/透镜成像：1/v + 1/u = 1/f → v = uf/(u-f)
def _几何_像距(u, f): return u * f / (u - f)
# 放大率：m = -v/u
def _几何_放大率(v, u): return -v / u
# 薄透镜造焦公式：1/f = (n-1)(1/R₁ - 1/R₂) → f
def _几何_透镜焦距(n, R1, R2):
    return 1.0 / ((n - 1) * (1.0 / R1 - 1.0 / R2))
# 介质中光速：v = c/n
def _几何_介质光速(n): return C_LIGHT / n
# 折射率：n = c/v
def _几何_折射率(v): return C_LIGHT / v
# 透镜组合焦距（密接）：1/f = 1/f₁ + 1/f₂ → f
def _几何_透镜组合(f1, f2): return 1.0 / (1.0 / f1 + 1.0 / f2)


# ============================================================
# 二、波动光学（Wave Optics）
# ============================================================

# 双缝干涉条纹间距：Δy = λD/d
def _波动_双缝条纹间距(wavelength, D, d): return wavelength * D / d
# 薄膜干涉光程差（垂直入射）：2nd = mλ → 垂直入射薄膜光学厚度
def _波动_薄膜光程差(n, d): return 2 * n * d
# 单缝衍射暗纹位置：a·sinθ = mλ → θ = arcsin(mλ/a)
def _波动_单缝暗纹角(wavelength, a, m): return math.asin(m * wavelength / a)
# 光栅方程：d·sinθ = mλ → θ = arcsin(mλ/d)
def _波动_光栅衍射角(wavelength, d_grating, m): return math.asin(m * wavelength / d_grating)
# 光栅分辨本领：R = mN
def _波动_光栅分辨本领(m, N): return m * N
# 马吕斯定律：I = I₀cos²θ
def _波动_马吕斯定律(I0, theta): return I0 * math.cos(theta) ** 2
# 布儒斯特角：tanθB = n₂/n₁ → θB = arctan(n₂/n₁)
def _波动_布儒斯特角(n1, n2): return math.atan(n2 / n1)
# 双缝干涉光程差：Δ = d·sinθ
def _波动_双缝光程差(d, theta): return d * math.sin(theta)


# ============================================================
# 三、光度学（Photometry）
# ============================================================

# 光通量（各向同性点光源）：Φ = 4πI
def _光度_光通量(I): return 4 * math.pi * I
# 照度（平方反比）：E = I/r²
def _光度_照度(I, r): return I / (r * r)
# 照度（斜入射）：E = (I/r²)cosθ
def _光度_斜照度(I, r, theta): return I / (r * r) * math.cos(theta)
# 光亮度：L = I/A
def _光度_亮度(I, A): return I / A
# 光视效能：K = Φ/P
def _光度_光视效能(Phi, P): return Phi / P
# 发光强度（由光通量和立体角）：I = Φ/Ω
def _光度_发光强度(Phi, Omega): return Phi / Omega


# ============================================================
# 四、光学仪器（Optical Instruments）
# ============================================================

# 放大镜放大率：M = 25/f + 1（近似 M = 25/f）
def _仪器_放大镜(f): return 0.25 / f  # 25cm/f
# 显微镜放大率：M = (L/f_o)(25/f_e)，L 为镜筒长
def _仪器_显微镜(L, f_o, f_e): return (L / f_o) * (0.25 / f_e)
# 望远镜放大率：M = -f_o/f_e
def _仪器_望远镜(f_o, f_e): return -f_o / f_e
# 数值孔径：NA = n·sinα
def _仪器_数值孔径(n, alpha): return n * math.sin(alpha)
# 最小分辨角（瑞利判据）：θ = 1.22λ/D
def _仪器_最小分辨角(wavelength, D): return 1.22 * wavelength / D
# 显微镜分辨极限：d_min = 0.61λ/NA
def _仪器_分辨极限(wavelength, NA): return 0.61 * wavelength / NA
# 眼睛最小分辨角（约1'）
def _仪器_人眼分辨角(): return math.radians(1.0 / 60.0)


# ============================================================
# 五、色散与光谱（Dispersion & Spectrum）
# ============================================================

# 柯西方程：n(λ) = A + B/λ²
def _色散_柯西折射率(A, B, wavelength): return A + B / (wavelength ** 2)
# 色散率：dn/dλ = -2B/λ³
def _色散_色散率(B, wavelength): return -2 * B / (wavelength ** 3)
# 光子能量：E = hf = hc/λ
def _色散_光子能量频率(f): return H_PLANCK * f
def _色散_光子能量波长(wavelength): return H_PLANCK * C_LIGHT / wavelength
# 光子动量：p = h/λ
def _色散_光子动量(wavelength): return H_PLANCK / wavelength
# 红移因子：z = (λ_obs - λ_emit)/λ_emit
def _色散_红移(lam_obs, lam_emit): return (lam_obs - lam_emit) / lam_emit
# 多普勒红移速度（非相对论）：v = zc
def _色散_红移速度(z): return z * C_LIGHT


# ============================================================
# 光学介质数据库
# ============================================================

# 常见介质折射率（钠 D 线 589nm, 20°C）
REFRACTIVE_INDICES: dict[str, float] = {
    "真空": 1.0,
    "空气": 1.0003,
    "水": 1.333,
    "冰": 1.31,
    "普通玻璃": 1.52,
    "冕牌玻璃": 1.50,
    "火石玻璃": 1.62,
    "石英": 1.46,
    "钻石": 2.417,
    "甘油": 1.473,
    "乙醇": 1.361,
    "蓝宝石": 1.77,
}

# 常见光波长 (nm → m)
WAVELENGTHS: dict[str, float] = {
    "红光": 700e-9,
    "橙光": 620e-9,
    "黄光": 580e-9,
    "绿光": 530e-9,
    "蓝光": 470e-9,
    "紫光": 420e-9,
    "钠D线": 589e-9,
    "HeNe激光": 632.8e-9,
    "紫外": 300e-9,
    "红外": 1000e-9,
}

# 柯西方程系数（A, B）B 单位 m²
CAUCHY_COEFFS: dict[str, tuple[float, float]] = {
    "普通玻璃": (1.5046, 4200e-18),
    "冕牌玻璃": (1.4980, 3800e-18),
    "火石玻璃": (1.6120, 8900e-18),
    "石英": (1.4580, 3250e-18),
}


# ============================================================
# 注册到解释器 builtins
# ============================================================

def _register_optics(builtins: dict) -> None:
    """将光学内建注册到解释器 builtins。

    在 Interpreter.__init__ 中调用（acoustics 之后）。
    """
    # --- 几何光学 ---
    builtins["几何_折射角"] = _curry3(_几何_折射角)                # 几何_折射角(n1)(θ1)(n2)
    builtins["几何_全反射角"] = _curry2(_几何_全反射角)            # 几何_全反射角(n1)(n2)
    builtins["几何_球面镜焦距"] = _几何_球面镜焦距                 # 几何_球面镜焦距(R)
    builtins["几何_像距"] = _curry2(_几何_像距)                    # 几何_像距(u)(f)
    builtins["几何_放大率"] = _curry2(_几何_放大率)                # 几何_放大率(v)(u)
    builtins["几何_透镜焦距"] = _curry3(_几何_透镜焦距)            # 几何_透镜焦距(n)(R1)(R2)
    builtins["几何_介质光速"] = _几何_介质光速                     # 几何_介质光速(n)
    builtins["几何_折射率"] = _几何_折射率                         # 几何_折射率(v)
    builtins["几何_透镜组合"] = _curry2(_几何_透镜组合)            # 几何_透镜组合(f1)(f2)

    # --- 波动光学 ---
    builtins["波动_双缝条纹间距"] = _curry3(_波动_双缝条纹间距)    # 波动_双缝条纹间距(λ)(D)(d)
    builtins["波动_薄膜光程差"] = _curry2(_波动_薄膜光程差)        # 波动_薄膜光程差(n)(d)
    builtins["波动_单缝暗纹角"] = _curry3(_波动_单缝暗纹角)        # 波动_单缝暗纹角(λ)(a)(m)
    builtins["波动_光栅衍射角"] = _curry3(_波动_光栅衍射角)        # 波动_光栅衍射角(λ)(d)(m)
    builtins["波动_光栅分辨本领"] = _curry2(_波动_光栅分辨本领)    # 波动_光栅分辨本领(m)(N)
    builtins["波动_马吕斯定律"] = _curry2(_波动_马吕斯定律)        # 波动_马吕斯定律(I0)(θ)
    builtins["波动_布儒斯特角"] = _curry2(_波动_布儒斯特角)        # 波动_布儒斯特角(n1)(n2)
    builtins["波动_双缝光程差"] = _curry2(_波动_双缝光程差)        # 波动_双缝光程差(d)(θ)

    # --- 光度学 ---
    builtins["光度_光通量"] = _光度_光通量                         # 光度_光通量(I)
    builtins["光度_照度"] = _curry2(_光度_照度)                    # 光度_照度(I)(r)
    builtins["光度_斜照度"] = _curry3(_光度_斜照度)                # 光度_斜照度(I)(r)(θ)
    builtins["光度_亮度"] = _curry2(_光度_亮度)                    # 光度_亮度(I)(A)
    builtins["光度_光视效能"] = _curry2(_光度_光视效能)            # 光度_光视效能(Φ)(P)
    builtins["光度_发光强度"] = _curry2(_光度_发光强度)            # 光度_发光强度(Φ)(Ω)

    # --- 光学仪器 ---
    builtins["仪器_放大镜"] = _仪器_放大镜                         # 仪器_放大镜(f)
    builtins["仪器_显微镜"] = _curry3(_仪器_显微镜)                # 仪器_显微镜(L)(fo)(fe)
    builtins["仪器_望远镜"] = _curry2(_仪器_望远镜)                # 仪器_望远镜(fo)(fe)
    builtins["仪器_数值孔径"] = _curry2(_仪器_数值孔径)            # 仪器_数值孔径(n)(α)
    builtins["仪器_最小分辨角"] = _curry2(_仪器_最小分辨角)        # 仪器_最小分辨角(λ)(D)
    builtins["仪器_分辨极限"] = _curry2(_仪器_分辨极限)            # 仪器_分辨极限(λ)(NA)
    builtins["仪器_人眼分辨角"] = _仪器_人眼分辨角                  # 仪器_人眼分辨角()

    # --- 色散与光谱 ---
    builtins["色散_柯西折射率"] = _curry3(_色散_柯西折射率)        # 色散_柯西折射率(A)(B)(λ)
    builtins["色散_色散率"] = _curry2(_色散_色散率)                # 色散_色散率(B)(λ)
    builtins["色散_光子能量频率"] = _色散_光子能量频率              # 色散_光子能量频率(f)
    builtins["色散_光子能量波长"] = _色散_光子能量波长              # 色散_光子能量波长(λ)
    builtins["色散_光子动量"] = _色散_光子动量                     # 色散_光子动量(λ)
    builtins["色散_红移"] = _curry2(_色散_红移)                    # 色散_红移(λobs)(λemit)
    builtins["色散_红移速度"] = _色散_红移速度                     # 色散_红移速度(z)

    # --- 物理常量 ---
    builtins["c_光速"] = C_LIGHT
    builtins["h_普朗克"] = H_PLANCK
    builtins["Km_最大光视效能"] = K_MAX

    # --- 折射率常量 ---
    for name, val in REFRACTIVE_INDICES.items():
        builtins[f"折射率_{name}"] = val

    # --- 光波长常量 ---
    for name, val in WAVELENGTHS.items():
        builtins[f"波长_{name}"] = val


def _optics_symtab_names() -> list[str]:
    """返回光学所有内建名（用于语义分析注册）。"""
    names: list[str] = []
    # 几何光学
    for n in ["折射角", "全反射角", "球面镜焦距", "像距", "放大率",
              "透镜焦距", "介质光速", "折射率", "透镜组合"]:
        names.append(f"几何_{n}")
    # 波动光学
    for n in ["双缝条纹间距", "薄膜光程差", "单缝暗纹角", "光栅衍射角",
              "光栅分辨本领", "马吕斯定律", "布儒斯特角", "双缝光程差"]:
        names.append(f"波动_{n}")
    # 光度学
    for n in ["光通量", "照度", "斜照度", "亮度", "光视效能", "发光强度"]:
        names.append(f"光度_{n}")
    # 光学仪器
    for n in ["放大镜", "显微镜", "望远镜", "数值孔径",
              "最小分辨角", "分辨极限", "人眼分辨角"]:
        names.append(f"仪器_{n}")
    # 色散与光谱
    for n in ["柯西折射率", "色散率", "光子能量频率", "光子能量波长",
              "光子动量", "红移", "红移速度"]:
        names.append(f"色散_{n}")
    # 物理常量
    for n in ["c_光速", "h_普朗克", "Km_最大光视效能"]:
        names.append(n)
    # 数据库常量
    for name in REFRACTIVE_INDICES:
        names.append(f"折射率_{name}")
    for name in WAVELENGTHS:
        names.append(f"波长_{name}")
    return names
