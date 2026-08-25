"""Matha 数学函数库：各领域演化的公共地基。

理念：物理/化学/机械/天文/地理等领域本质是数学分支，用数学统一演化。
本模块提供各领域共享的数学基础：
  - 常量：pi、e、tau、phi（黄金比）
  - 三角函数：sin/cos/tan/asin/acos/atan/atan2（弧度制）
  - 双曲函数：sinh/cosh/tanh
  - 对数指数：log（自然对数）/log10/log2/exp/sqrt/pow
  - 取整绝对值：abs/floor/ceil/round/trunc
  - 极值统计：min/max/sum
  - 角度弧度换算：deg2rad/rad2deg
  - 物理常量：G（引力常数）/c（光速）/g（重力加速度）

所有函数以普通 Python callable 形式注册到解释器 BUILTINS，
Matha 代码可直接调用（如 sin(0)=0、sqrt(2)≈1.414）。

领域应用示例（用数学演化）：
  - 物理：v = sqrt(2 * g * h)        （自由落体末速度）
  - 天文：T = 2 * pi * sqrt(r^3/GM)  （开普勒第三定律）
  - 地理：d = r * acos(sin(a)*sin(b)+cos(a)*cos(b)*cos(da-db))（大圆距离）
  - 化学：n = m / M                   （摩尔数 = 质量/摩尔质量）
"""

from __future__ import annotations
import math
from typing import Any


# ============================================================
# 数学常量
# ============================================================

CONSTANTS: dict[str, float] = {
    "pi": math.pi,           # 圆周率 ≈ 3.14159
    "e": math.e,             # 自然对数底 ≈ 2.71828
    "tau": math.tau,         # 2π ≈ 6.28318
    "phi": (1 + math.sqrt(5)) / 2,  # 黄金比例 ≈ 1.61803
}

# 物理常量（SI 单位）
PHYSICAL_CONSTANTS: dict[str, float] = {
    "G": 6.674e-11,          # 万有引力常数 m³/(kg·s²)
    "c": 299792458,          # 光速 m/s
    "g": 9.80665,            # 标准重力加速度 m/s²
    "h_planck": 6.626e-34,   # 普朗克常数 J·s
    "N_A": 6.022e23,         # 阿伏伽德罗常数 mol⁻¹
    "R": 8.314,              # 气体常数 J/(mol·K)
}


# ============================================================
# 数学函数（注册为 Matha 内建）
# 每个函数返回普通 Python 值，柯里化由解释器侧处理。
# ============================================================

def _curry3(func):
    """将三参 Python 函数转为柯里化：f(a)(b)(c)。"""
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1


def _register_math_builtins(builtins: dict) -> None:
    """将数学函数与常量注册到解释器 builtins 字典。

    在 Interpreter.__init__ 中调用：
        from src.mathlib import _register_math_builtins
        _register_math_builtins(self.builtins)

    常量直接作为值注册（非 callable），函数作为 callable 注册。
    """
    # --- 常量（直接值，非 callable）---
    for name, val in CONSTANTS.items():
        builtins[name] = val
    for name, val in PHYSICAL_CONSTANTS.items():
        builtins[name] = val

    # --- 三角函数（弧度制）---
    builtins["sin"] = math.sin
    builtins["cos"] = math.cos
    builtins["tan"] = math.tan
    builtins["asin"] = math.asin
    builtins["acos"] = math.acos
    builtins["atan"] = math.atan
    builtins["atan2"] = _curry2(math.atan2)  # atan2(y)(x) 柯里化

    # --- 双曲函数 ---
    builtins["sinh"] = math.sinh
    builtins["cosh"] = math.cosh
    builtins["tanh"] = math.tanh

    # --- 对数与指数 ---
    builtins["log"] = math.log       # 自然对数 ln
    builtins["ln"] = math.log        # 别名
    builtins["log10"] = math.log10   # 常用对数
    builtins["log2"] = math.log2     # 二进制对数
    builtins["exp"] = math.exp       # e^x
    builtins["sqrt"] = math.sqrt     # 平方根
    builtins["pow"] = _curry2(math.pow)  # pow(base)(exp) 柯里化

    # --- 取整与绝对值 ---
    builtins["abs"] = abs
    builtins["floor"] = math.floor
    builtins["ceil"] = math.ceil
    builtins["round"] = round
    builtins["trunc"] = math.trunc

    # --- 极值与统计 ---
    # max/min 接受单个列表（符合 Matha 柯里化语义：max(列表)）
    builtins["max"] = lambda lst: max(lst) if isinstance(lst, (list, tuple)) else lst
    builtins["min"] = lambda lst: min(lst) if isinstance(lst, (list, tuple)) else lst
    builtins["sum"] = sum            # 对列表求和

    # --- 角度弧度换算 ---
    builtins["deg2rad"] = math.radians   # 度→弧度
    builtins["rad2deg"] = math.degrees   # 弧度→度

    # --- 符号与特殊函数 ---
    builtins["sign"] = _sign           # 符号函数：-1/0/1
    builtins["hypot"] = _curry2(math.hypot)  # 斜边长 hypot(a)(b)

    # ===== 文科辅助数学：逻辑运算 =====
    builtins["逻辑非"] = lambda p: not p
    builtins["逻辑与"] = _curry2(lambda a, b: a and b)
    builtins["逻辑或"] = _curry2(lambda a, b: a or b)
    builtins["逻辑蕴含"] = _curry2(lambda p, q: (not p) or q)
    builtins["逻辑异或"] = _curry2(lambda p, q: (p or q) and not (p and q))
    builtins["逻辑双蕴含"] = _curry2(lambda p, q: (p == q))

    # ===== 文科辅助数学：集合运算 =====
    builtins["集合并"] = _curry2(lambda a, b: sorted(set(a) | set(b)))
    builtins["集合交"] = _curry2(lambda a, b: sorted(set(a) & set(b)))
    builtins["集合差"] = _curry2(lambda a, b: sorted(set(a) - set(b)))
    builtins["集合补"] = _curry2(lambda universe, subset: sorted(set(universe) - set(subset)))
    builtins["集合子集"] = _curry2(lambda a, b: set(a).issubset(set(b)))
    builtins["集合幂集"] = lambda s: _power_set(list(s))
    builtins["集合基数"] = lambda s: len(set(s))

    # ===== 文科辅助数学：统计函数 =====
    builtins["平均值"] = lambda lst: sum(lst) / len(lst) if lst else 0
    builtins["中位数"] = lambda lst: _median(list(lst))
    builtins["方差"] = lambda lst: _variance(list(lst))
    builtins["标准差"] = lambda lst: math.sqrt(_variance(list(lst)))
    builtins["协方差"] = _curry2(lambda x, y: _covariance(list(x), list(y)))
    builtins["相关系数"] = _curry2(lambda x, y: _correlation(list(x), list(y)))

    # ===== 文科辅助数学：组合数学 =====
    builtins["阶乘"] = math.factorial
    builtins["排列数"] = _curry2(lambda n, r: math.perm(n, r) if n >= r else 0)
    builtins["组合数"] = _curry2(lambda n, r: math.comb(n, r) if n >= r else 0)
    builtins["杨辉三角"] = lambda n: _pascal_triangle(n)

    # ===== 文科辅助数学：数论 =====
    builtins["最大公约数"] = _curry2(lambda a, b: math.gcd(a, b))
    builtins["最小公倍数"] = _curry2(lambda a, b: abs(a * b) // math.gcd(a, b) if a and b else 0)
    builtins["素数判定"] = lambda n: _is_prime(n)
    builtins["素数筛"] = lambda n: _sieve_of_eratosthenes(n)

    # ===== 文科辅助数学：概率分布 =====
    builtins["正态密度"] = _curry3(lambda x, mu, sigma: _norm_pdf(x, mu, sigma))
    builtins["均匀随机"] = _curry2(lambda a, b: random.uniform(a, b))
    builtins["正态随机"] = _curry2(lambda mu, sigma: random.gauss(mu, sigma))


def _curry2(func):
    """将两参 Python 函数转为柯里化：f(a)(b)。"""
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def _max_variadic(*args):
    """max 支持多参或单列表。"""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return max(args[0])
    return max(args)


def _min_variadic(*args):
    """min 支持多参或单列表。"""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return min(args[0])
    return min(args)


def _sign(x):
    """符号函数：x>0 返回 1，x<0 返回 -1，x==0 返回 0。"""
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


# ============================================================
# 单位换算（物理/地理领域常用）
# ============================================================

UNIT_CONVERSIONS: dict[str, float] = {
    # 长度
    "千米_米": 1000, "米_千米": 0.001,
    "米_厘米": 100, "厘米_米": 0.01,
    "米_毫米": 1000, "毫米_米": 0.001,
    "英里_米": 1609.344, "米_英里": 1 / 1609.344,
    "英尺_米": 0.3048, "米_英尺": 1 / 0.3048,
    "光年_米": 9.461e15, "米_光年": 1 / 9.461e15,
    "天文单位_米": 1.496e11, "米_天文单位": 1 / 1.496e11,
    # 时间
    "小时_秒": 3600, "秒_小时": 1 / 3600,
    "天_秒": 86400, "秒_天": 1 / 86400,
    "年_秒": 3.156e7, "秒_年": 1 / 3.156e7,
    # 角度
    "度_弧度": math.pi / 180, "弧度_度": 180 / math.pi,
    # 质量
    "千克_克": 1000, "克_千克": 0.001,
    "磅_千克": 0.453592, "千克_磅": 1 / 0.453592,
    # 温度（特殊处理，见 _temp_convert）
}

TEMP_CONVERSIONS = {
    "摄氏_开尔文": lambda c: c + 273.15,
    "开尔文_摄氏": lambda k: k - 273.15,
    "摄氏_华氏": lambda c: c * 9 / 5 + 32,
    "华氏_摄氏": lambda f: (f - 32) * 5 / 9,
}


def _register_unit_builtins(builtins: dict) -> None:
    """注册单位换算内建。

    每个换算注册为 换算名(值) -> 转换值 的单参函数。
    温度换算因非线性，单独注册为 lambda。
    """
    for name, factor in UNIT_CONVERSIONS.items():
        builtins[f"换算_{name}"] = (lambda f=factor: lambda v: v * f)()
    for name, func in TEMP_CONVERSIONS.items():
        builtins[f"换算_{name}"] = func


# ============================================================
# 辅助函数（文科辅助数学）
# ============================================================

def _median(lst):
    """计算中位数。"""
    s = sorted(lst)
    n = len(s)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _variance(lst):
    """计算方差（总体方差）。"""
    if not lst:
        return 0
    mean = sum(lst) / len(lst)
    return sum((x - mean) ** 2 for x in lst) / len(lst)


def _covariance(x, y):
    """计算协方差。"""
    if len(x) != len(y) or not x:
        return 0
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / len(x)


def _correlation(x, y):
    """计算皮尔逊相关系数。"""
    cx = _covariance(x, y)
    sx = math.sqrt(_variance(x))
    sy = math.sqrt(_variance(y))
    if sx == 0 or sy == 0:
        return 0
    return cx / (sx * sy)


def _power_set(s):
    """生成幂集（所有子集）。"""
    result = [[]]
    for item in s:
        result = result + [r + [item] for r in result]
    return result


def _pascal_triangle(n):
    """生成杨辉三角前 n 行。"""
    row = [1]
    result = [row]
    for _ in range(n - 1):
        newRow = [1]
        for i in range(len(row) - 1):
            newRow.append(row[i] + row[i + 1])
        newRow.append(1)
        result.append(newRow)
        row = newRow
    return result


def _is_prime(n):
    """素数判定。"""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def _sieve_of_eratosthenes(n):
    """埃氏筛，返回 n 以内的所有素数。"""
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(math.sqrt(n)) + 1):
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
    return [i for i, v in enumerate(sieve) if v]


def _norm_pdf(x, mu, sigma):
    """正态分布概率密度函数。"""
    if sigma <= 0:
        return 0
    return (1 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-((x - mu) ** 2) / (2 * sigma ** 2))


def _curry2(func):
    """两参柯里化。"""
    def w1(a):
        return lambda b: func(a, b)
    return w1


def _curry3(func):
    """三参柯里化。"""
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1
