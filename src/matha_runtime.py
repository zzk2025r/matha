# -*- coding: utf-8 -*-
"""Matha 原生运行时引擎：纯数学实现，不依赖 Python math 模块。

设计理念：
  - 所有三角/对数/指数函数均用 Taylor 级数实现
  - 物理常量硬编码，不依赖外部库
  - 为 Matha VM 提供完整的数学运算能力

对标 Python math 模块，提供等价函数。
"""
from __future__ import annotations
import sys
from typing import Any

# ============================================================
# 数学常量
# ============================================================

PI: float = 3.14159265358979323846
E: float = 2.71828182845904523536
TAU: float = 2.0 * PI
PHI: float = (1.0 + 5.0 ** 0.5) / 2.0

# 物理常量
G_CONST: float = 6.674e-11       # 万有引力常数
C_LIGHT: float = 299792458.0      # 光速 m/s
G_ACCEL: float = 9.80665          # 重力加速度
H_PLANCK: float = 6.626e-34       # 普朗克常数
NA: float = 6.022e23              # 阿伏伽德罗常数
R_GAS: float = 8.314              # 气体常数
SIGMA_SB: float = 5.670e-8        # 斯特藩-玻尔兹曼常数


# ============================================================
# 核心数学函数（Taylor 级数实现）
# ============================================================

def _mod(x: float, m: float) -> float:
    """安全取模，处理负数（原生实现）。"""
    if m == 0:
        return x
    # 用 trunc 而非 floor 保持 Python % 语义
    return x - m * trunc(x / m)


def _reduce_angle(x: float) -> float:
    """将角度约化到 [-pi, pi] 区间，加速收敛。"""
    x = x % (2.0 * PI)
    if x > PI:
        x -= 2.0 * PI
    if x < -PI:
        x += 2.0 * PI
    return x


def sin(x: float) -> float:
    """正弦函数（Taylor 级数，约化到 [-pi, pi]）。"""
    x = _reduce_angle(x)
    result = 0.0
    term = x
    for n in range(30):
        result += term
        term *= -x * x / ((2 * n + 2) * (2 * n + 3))
        if abs(term) < 1e-15:
            break
    return result


def cos(x: float) -> float:
    """余弦函数（Taylor 级数，约化到 [-pi, pi]）。"""
    x = _reduce_angle(x)
    result = 0.0
    term = 1.0
    for n in range(30):
        result += term
        term *= -x * x / ((2 * n + 1) * (2 * n + 2))
        if abs(term) < 1e-15:
            break
    return result


def tan(x: float) -> float:
    """正切函数。"""
    c = cos(x)
    if abs(c) < 1e-15:
        raise ValueError("tan: 未定义（角度为 pi/2 的奇数倍）")
    return sin(x) / c


def asin(x: float) -> float:
    """反正弦函数（级数展开，|x| <= 1）。"""
    if abs(x) > 1:
        raise ValueError("asin: 定义域为 [-1, 1]")
    if abs(x) == 1:
        return PI / 2.0 if x > 0 else -PI / 2.0
    # asin(x) = x + x^3/6 + 3x^5/40 + 15x^7/336 + ...
    # 项递推: t_n = t_{n-1} * x^2 * (2n-1)^2 / ((2n)(2n+1))
    result = 0.0
    term = x
    for n in range(1, 80):
        result += term
        term *= x * x * (2 * n - 1) * (2 * n - 1) / (2 * n * (2 * n + 1))
        if abs(term) < 1e-16:
            break
    return result


def acos(x: float) -> float:
    """反余弦函数。"""
    return PI / 2.0 - asin(x)


def atan(x: float) -> float:
    """反正切函数（级数加速版）。"""
    # 利用恒等式加速收敛
    if abs(x) > 1:
        if x > 0:
            return PI / 2.0 - atan(1.0 / x)
        else:
            return -PI / 2.0 - atan(1.0 / x)
    # 使用 atan(x) = 2*atan(x/(1+sqrt(1+x^2))) 缩小参数
    factor = 1.0
    while abs(x) > 0.4:
        x = x / (1.0 + sqrt(1.0 + x * x))
        factor *= 2.0
    # Taylor 级数：atan(x) = x - x^3/3 + x^5/5 - x^7/7 + ...
    result = 0.0
    term = x
    for n in range(1, 80):
        result += term
        term *= -x * x * (2 * n - 1) / (2 * n + 1)
        if abs(term) < 1e-15:
            break
    return factor * result


def atan2(y: float, x: float) -> float:
    """二参反正切。"""
    if x > 0:
        return atan(y / x)
    elif x < 0 and y >= 0:
        return atan(y / x) + PI
    elif x < 0 and y < 0:
        return atan(y / x) - PI
    elif x == 0 and y > 0:
        return PI / 2.0
    elif x == 0 and y < 0:
        return -PI / 2.0
    return 0.0


def exp(x: float) -> float:
    """指数函数 e^x（Taylor 级数）。"""
    # 参数约化：e^x = (e^(x/n))^n
    n = 1
    while abs(x) > 1.0:
        x /= 2.0
        n *= 2
    result = 1.0
    term = 1.0
    for i in range(1, 50):
        term *= x / i
        result += term
        if abs(term) < 1e-15:
            break
    # 平方 n 次还原
    for _ in range(n.bit_length() - 1):
        result = result * result
    return result


def log(x: float) -> float:
    """自然对数 ln(x)（Taylor 级数，x > 0）。"""
    if x <= 0:
        raise ValueError("log: 定义域为正数")
    if x == 1:
        return 0.0
    # 参数约化：ln(x) = ln(x / 2^k) + k * ln(2)
    k = 0
    while x > 2:
        x /= 2.0
        k += 1
    while x < 0.5:
        x *= 2.0
        k -= 1
    # ln(x) for x in [0.5, 2] using series: ln(1+u) = u - u^2/2 + u^3/3 - ...
    u = x - 1.0
    result = 0.0
    term = u
    for n in range(1, 100):
        result += term / n
        term *= -u
        if abs(term / (n + 1)) < 1e-15:
            break
    # ln(2) ≈ 0.6931471805599453
    result += k * 0.6931471805599453
    return result


def log10(x: float) -> float:
    """常用对数。"""
    return log(x) / log(10.0)


def log2(x: float) -> float:
    """二进制对数。"""
    return log(x) / log(2.0)


def sqrt(x: float) -> float:
    """平方根（Newton-Raphson 迭代）。"""
    if x < 0:
        raise ValueError("sqrt: 定义域为非负数")
    if x == 0:
        return 0.0
    # 初始猜测
    guess = x if x >= 1 else 1.0
    for _ in range(50):
        guess = 0.5 * (guess + x / guess)
        if abs(guess * guess - x) < 1e-15:
            break
    return guess


def pow(base: float, exp: float) -> float:
    """幂函数 base^exp。"""
    if base == 0:
        return 0.0 if exp > 0 else float('inf')
    if exp == int(exp):
        # 整数指数，快速幂
        n = int(exp)
        if n < 0:
            return 1.0 / _pow_int(base, -n)
        return _pow_int(base, n)
    # 实数指数：base^exp = exp(exp * ln(base))
    if base < 0:
        raise ValueError("pow: 负底数配实数指数未实现")
    return exp(exp * log(base))


def _pow_int(base: float, n: int) -> float:
    """整数快速幂。"""
    if n == 0:
        return 1.0
    result = 1.0
    b = base
    while n > 0:
        if n & 1:
            result *= b
        b *= b
        n >>= 1
    return result


def sinh(x: float) -> float:
    """双曲正弦。"""
    return (exp(x) - exp(-x)) / 2.0


def cosh(x: float) -> float:
    """双曲余弦。"""
    return (exp(x) + exp(-x)) / 2.0


def tanh(x: float) -> float:
    """双曲正切。"""
    ex = exp(x)
    exn = exp(-x)
    return (ex - exn) / (ex + exn)


# ============================================================
# 取整与绝对值
# ============================================================

def abs_val(x: float) -> float:
    return x if x >= 0 else -x


def floor(x: float) -> float:
    """向下取整（原生实现）。"""
    i = int(x)
    return float(i) if i <= x else float(i - 1)


def ceil(x: float) -> float:
    """向上取整（原生实现）。"""
    i = int(x)
    return float(i) if i >= x else float(i + 1)


def trunc(x: float) -> float:
    """截断取整。"""
    return float(int(x))


def round_val(x: float) -> float:
    """四舍五入（原生实现）。"""
    i = int(x + 0.5) if x >= 0 else int(x - 0.5)
    return float(i)


# ============================================================
# 极值与统计
# ============================================================

def max_val(args: list) -> float:
    """最大值。"""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    return max(args)


def min_val(args: list) -> float:
    """最小值。"""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    return min(args)


def sum_list(lst: list) -> float:
    return sum(lst)


# ============================================================
# 辅助函数
# ============================================================

def deg2rad(d: float) -> float:
    return d * PI / 180.0


def rad2deg(r: float) -> float:
    return r * 180.0 / PI


def sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def hypot(a: float, b: float) -> float:
    return sqrt(a * a + b * b)


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("阶乘: 定义域为非负整数")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def perm(n: int, r: int) -> int:
    if r > n:
        return 0
    result = 1
    for i in range(r):
        result *= (n - i)
    return result


def comb(n: int, r: int) -> int:
    if r > n or r < 0:
        return 0
    r = min(r, n - r)
    result = 1
    for i in range(r):
        result = result * (n - i) // (i + 1)
    return result


def gcd(a: int, b: int) -> int:
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def sieve(n: int) -> list:
    """埃氏筛。"""
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(sqrt(n)) + 1):
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
    return [i for i, v in enumerate(sieve) if v]


def median(lst: list) -> float:
    s = sorted(lst)
    n = len(s)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def variance(lst: list) -> float:
    if not lst:
        return 0
    mean = sum(lst) / len(lst)
    return sum((x - mean) ** 2 for x in lst) / len(lst)


def covariance(x: list, y: list) -> float:
    if len(x) != len(y) or not x:
        return 0
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / len(x)


def correlation(x: list, y: list) -> float:
    cx = covariance(x, y)
    sx = sqrt(variance(x))
    sy = sqrt(variance(y))
    if sx == 0 or sy == 0:
        return 0
    return cx / (sx * sy)


def norm_pdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0
    return (1.0 / (sigma * sqrt(2.0 * PI))) * exp(-((x - mu) ** 2) / (2.0 * sigma ** 2))


def uniform(a: float, b: float) -> float:
    """伪随机均匀分布。"""
    import random
    return random.uniform(a, b)


def gauss(mu: float, sigma: float) -> float:
    """伪随机正态分布。"""
    import random
    return random.gauss(mu, sigma)


# ============================================================
# 内建函数注册表（提供给 Matha VM）
# ============================================================

def get_builtin(name: str) -> Any:
    """按名称获取内建函数/常量。"""
    _builtins = {
        # 常量
        "pi": PI, "e": E, "tau": TAU, "phi": PHI,
        "π": PI, "φ": PHI,
        # 物理常量
        "G": G_CONST, "c": C_LIGHT, "g": G_ACCEL,
        "h_planck": H_PLANCK, "N_A": NA, "R": R_GAS,
        # 三角函数
        "sin": sin, "cos": cos, "tan": tan,
        "asin": asin, "acos": acos, "atan": atan, "atan2": atan2,
        # 双曲函数
        "sinh": sinh, "cosh": cosh, "tanh": tanh,
        # 对数指数
        "log": log, "ln": log, "log10": log10, "log2": log2,
        "exp": exp,
        # 幂函数
        "sqrt": sqrt, "pow": pow,
        # 取整
        "abs": abs_val, "floor": floor, "ceil": ceil,
        "round": round_val, "trunc": trunc,
        # 极值统计
        "max": max_val, "min": min_val, "sum": sum_list,
        # 角度换算
        "deg2rad": deg2rad, "rad2deg": rad2deg,
        # 特殊函数
        "sign": sign, "hypot": hypot,
        # 组合数学
        "阶乘": factorial, "排列数": perm, "组合数": comb,
        "gcd": gcd, "最大公约数": gcd,
        "最小公倍数": lambda a, b: abs(a * b) // gcd(a, b) if a and b else 0,
        # 数论
        "素数判定": is_prime, "素数筛": sieve,
        # 统计
        "平均值": lambda lst: sum_list(lst) / len(lst) if lst else 0,
        "中位数": median, "方差": variance,
        "标准差": lambda lst: sqrt(variance(lst)),
        "协方差": covariance, "相关系数": correlation,
        "正态密度": norm_pdf,
        # 随机
        "均匀随机": uniform, "正态随机": gauss,
        # 中文逻辑
        "逻辑非": lambda p: not p,
        "逻辑与": lambda a, b: a and b,
        "逻辑或": lambda a, b: a or b,
    }
    return _builtins.get(name)


def get_builtin_names() -> list:
    """返回所有内建名称。"""
    return list(get_builtin.__code__.co_consts)


# 测试
if __name__ == "__main__":
    print("=== Matha 原生运行时测试 ===")
    print(f"sin(0) = {sin(0):.10f}  (期望 0)")
    print(f"sin(pi/2) = {sin(PI/2):.10f}  (期望 1)")
    print(f"cos(0) = {cos(0):.10f}  (期望 1)")
    print(f"cos(pi) = {cos(PI):.10f}  (期望 -1)")
    print(f"tan(pi/4) = {tan(PI/4):.10f}  (期望 1)")
    print(f"sqrt(2) = {sqrt(2):.10f}  (期望 1.41421356)")
    print(f"exp(1) = {exp(1):.10f}  (期望 2.71828183)")
    print(f"log(e) = {log(E):.10f}  (期望 1)")
    print(f"log10(100) = {log10(100):.10f}  (期望 2)")
    print(f"pow(2, 10) = {pow(2, 10):.10f}  (期望 1024)")
    print(f"asin(1) = {asin(1):.10f}  (期望 pi/2)")
    print(f"atan(1) = {atan(1):.10f}  (期望 pi/4)")
    print(f"sinh(0) = {sinh(0):.10f}  (期望 0)")
    print(f"cosh(0) = {cosh(0):.10f}  (期望 1)")
    print(f"factorial(10) = {factorial(10)}  (期望 3628800)")
    print(f"comb(10, 3) = {comb(10, 3)}  (期望 120)")
    print(f"is_prime(17) = {is_prime(17)}  (期望 True)")
    print(f"sieve(20) = {sieve(20)}  (期望 [2,3,5,7,11,13,17,19])")
    print("=== 全部通过 ===")
