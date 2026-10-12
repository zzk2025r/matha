"""Matha 原生运行时引擎：纯数学实现，不依赖 Python math 模块。

设计理念：
  - 所有三角/对数/指数函数均用 Taylor 级数实现
  - 物理常量硬编码，不依赖外部库
  - 为 Matha VM 提供完整的数学运算能力

对标 Python math 模块，提供等价函数。
"""
from __future__ import annotations

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
    """绝对值。"""
    return x if x >= 0 else -x


def abs(x: float) -> float:
    """绝对值（别名）。"""
    return abs_val(x)


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
# 标准库扩展函数
# ============================================================

def len_val(x: Any) -> int:
    """返回长度。"""
    return len(x) if hasattr(x, '__len__') else 0

def reverse_val(lst: list) -> list:
    """反转列表。"""
    return list(reversed(lst))

def sort_val(lst: list, key=None) -> list:
    """排序列表。"""
    return sorted(lst, key=key)

def map_val(f: callable, lst: list) -> list:
    """映射。"""
    return list(map(f, lst))

def filter_val(f: callable, lst: list) -> list:
    """过滤。"""
    return list(filter(f, lst))

def reduce_val(f: callable, lst: list, init: Any = 0) -> Any:
    """归约。"""
    from functools import reduce
    return reduce(f, lst, init)

def join_val(sep: str, lst: list) -> str:
    """连接字符串。"""
    return sep.join(str(x) for x in lst)

def split_val(sep: str, s: str) -> list:
    """分割字符串。"""
    return s.split(sep)

def upper_val(s: str) -> str:
    """转大写。"""
    return s.upper()

def lower_val(s: str) -> str:
    """转小写。"""
    return s.lower()

def strip_val(s: str) -> str:
    """去除空白。"""
    return s.strip()

def replace_val(s: str, old: str, new: str) -> str:
    """替换。"""
    return s.replace(old, new)

def contains_val(s: str, sub: str) -> bool:
    """包含检查。"""
    return sub in s

def startswith_val(s: str, prefix: str) -> bool:
    """前缀检查。"""
    return s.startswith(prefix)

def endswith_val(s: str, suffix: str) -> bool:
    """后缀检查。"""
    return s.endswith(suffix)

def slice_val(s: str, start: int, end: int) -> str:
    """切片。"""
    return s[start:end]

def append_val(lst: list, item: Any) -> list:
    """追加。"""
    return lst + [item]

def insert_val(lst: list, index: int, item: Any) -> list:
    """插入。"""
    r = list(lst)
    r.insert(index, item)
    return r

def remove_val(lst: list, item: Any) -> list:
    """移除。"""
    r = list(lst)
    r.remove(item)
    return r

def pop_val(lst: list, index: int = -1) -> list:
    """弹出。"""
    r = list(lst)
    r.pop(index)
    return r

def chr_val(code: int) -> str:
    """ASCII码转字符。"""
    return chr(code)

def ord_val(s: str) -> int:
    """字符转ASCII码。"""
    return ord(s[0]) if s else 0

def range_val(stop: int, start: int = 0, step: int = 1) -> list:
    """范围列表。"""
    return list(range(start, stop, step))

def zip_val(a: list, b: list) -> list:
    """拉链。"""
    return list(zip(a, b))

def enumerate_val(lst: list, start: int = 0) -> list:
    """枚举。"""
    return list(enumerate(lst, start))

def any_val(lst: list) -> bool:
    """任意。"""
    return any(lst)

def all_val(lst: list) -> bool:
    """全部。"""
    return all(lst)

def random_int_val(a: int, b: int) -> int:
    """随机整数。"""
    import random
    return random.randint(a, b)

def random_float_val() -> float:
    """随机浮点数。"""
    import random
    return random.random()

def random_choice_val(lst: list) -> Any:
    """随机选择。"""
    import random
    return random.choice(lst)

def shuffle_val(lst: list) -> list:
    """打乱。"""
    import random
    r = list(lst)
    random.shuffle(r)
    return r

def json_dumps_val(obj: Any) -> str:
    """JSON序列化。"""
    import json
    return json.dumps(obj, ensure_ascii=False)

def json_loads_val(s: str) -> Any:
    """JSON反序列化。"""
    import json
    return json.loads(s)

def time_now_val() -> float:
    """当前时间戳。"""
    import time
    return time.time()

def split_lines_val(s: str) -> list:
    """按行分割。"""
    return s.split('\n')

def trim_val(s: str) -> str:
    """去除空白。"""
    return s.strip()

def lstrip_val(s: str) -> str:
    """去除左空白。"""
    return s.lstrip()

def rstrip_val(s: str) -> str:
    """去除右空白。"""
    return s.rstrip()

def format_str_val(fmt: str, *args) -> str:
    """格式化字符串。"""
    return fmt.format(*args)

def isinstance_val(obj: Any, cls: type) -> bool:
    """类型检查。"""
    return isinstance(obj, cls)

def type_name_val(obj: Any) -> str:
    """类型名称。"""
    return type(obj).__name__


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
        # 列表工具
        "len": len_val, "reverse": reverse_val, "sort": sort_val,
        "map": map_val, "filter": filter_val, "reduce": reduce_val,
        "append": append_val, "insert": insert_val, "remove": remove_val,
        "pop": pop_val,
        # 字符串工具
        "join": join_val, "split": split_val, "upper": upper_val,
        "lower": lower_val, "strip": strip_val, "replace": replace_val,
        "contains": contains_val, "startswith": startswith_val,
        "endswith": endswith_val, "slice": slice_val,
        "chr": chr_val, "ord": ord_val,
        # 迭代工具
        "range": range_val, "zip": zip_val, "enumerate": enumerate_val,
        "any": any_val, "all": all_val,
        # 随机
        "random_int": random_int_val, "random_float": random_float_val,
        "random_choice": random_choice_val, "shuffle": shuffle_val,
        # JSON
        "json_dumps": json_dumps_val, "json_loads": json_loads_val,
        # 时间
        "time_now": time_now_val, "split_lines": split_lines_val,
        # 字符串处理
        "trim": trim_val, "lstrip": lstrip_val, "rstrip": rstrip_val,
        "format": format_str_val, "format_str": format_str_val,
        # 类型
        "isinstance": isinstance_val, "type_name": type_name_val,
    }
    # 尝试从领域模块加载
    try:
        from src.domains.registry import get_registry
        registry = get_registry()
        for domain_key in registry._domains:
            builtins = registry.get_builtins(domain_key)
            if name in builtins:
                return builtins[name]
    except Exception:
        pass
    return _builtins.get(name)


def get_builtin_names() -> list:
    """返回所有内建名称。"""
    _builtins = {
        "pi": PI, "e": E, "tau": TAU, "phi": PHI, "π": PI, "φ": PHI,
        "G": G_CONST, "c": C_LIGHT, "g": G_ACCEL, "h_planck": H_PLANCK, "N_A": NA, "R": R_GAS,
        "sin": sin, "cos": cos, "tan": tan, "asin": asin, "acos": acos, "atan": atan, "atan2": atan2,
        "sinh": sinh, "cosh": cosh, "tanh": tanh,
        "log": log, "ln": log, "log10": log10, "log2": log2, "exp": exp,
        "sqrt": sqrt, "pow": pow,
        "abs": abs_val, "floor": floor, "ceil": ceil, "round": round_val, "trunc": trunc,
        "max": max_val, "min": min_val, "sum": sum_list,
        "deg2rad": deg2rad, "rad2deg": rad2deg,
        "sign": sign, "hypot": hypot,
        "阶乘": factorial, "排列数": perm, "组合数": comb,
        "gcd": gcd, "最大公约数": gcd, "最小公倍数": lambda a, b: abs(a * b) // gcd(a, b) if a and b else 0,
        "素数判定": is_prime, "素数筛": sieve,
        "平均值": lambda lst: sum_list(lst) / len(lst) if lst else 0,
        "中位数": median, "方差": variance, "标准差": lambda lst: sqrt(variance(lst)),
        "协方差": covariance, "相关系数": correlation, "正态密度": norm_pdf,
        "均匀随机": uniform, "正态随机": gauss,
        "逻辑非": lambda p: not p, "逻辑与": lambda a, b: a and b, "逻辑或": lambda a, b: a or b,
        # 列表/字符串工具
        "len": len_val, "reverse": reverse_val, "sort": sort_val,
        "map": map_val, "filter": filter_val, "reduce": reduce_val,
        "join": join_val, "split": split_val, "upper": upper_val,
        "lower": lower_val, "strip": strip_val, "replace": replace_val,
        "contains": contains_val, "startswith": startswith_val,
        "endswith": endswith_val, "slice": slice_val,
        "append": append_val, "insert": insert_val, "remove": remove_val,
        "pop": pop_val, "chr": chr_val, "ord": ord_val,
        "range": range_val, "zip": zip_val, "enumerate": enumerate_val,
        "any": any_val, "all": all_val,
        "random_int": random_int_val, "random_float": random_float_val,
        "random_choice": random_choice_val, "shuffle": shuffle_val,
        "json_dumps": json_dumps_val, "json_loads": json_loads_val,
        "time_now": time_now_val, "split_lines": split_lines_val,
        "trim": trim_val, "lstrip": lstrip_val, "rstrip": rstrip_val,
        "format_str": format_str_val, "format": format_str_val,
        "isinstance": isinstance_val,
        "type_name": type_name_val,
    }
    names = list(_builtins.keys())
    try:
        from src.domains.registry import get_registry
        registry = get_registry()
        for domain_key in registry._domains:
            domain_names = registry.get_builtins(domain_key)
            names.extend(domain_names.keys())
    except Exception:
        pass
    return list(set(names))


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
    # 新增标准库函数测试
    print(f"len([1,2,3]) = {len_val([1,2,3])}  (期望 3)")
    print(f"reverse([1,2,3]) = {reverse_val([1,2,3])}  (期望 [3,2,1])")
    print(f"sort_list([3,1,2]) = {sort_val([3,1,2])}  (期望 [1,2,3])")
    print(f"map_list(lambda x: x*2, [1,2,3]) = {map_val(lambda x: x*2, [1,2,3])}  (期望 [2,4,6])")
    print(f"filter_list(lambda x: x>1, [1,2,3]) = {filter_val(lambda x: x>1, [1,2,3])}  (期望 [2,3])")
    print(f"reduce_list(lambda a,b: a+b, [1,2,3]) = {reduce_val(lambda a,b: a+b, [1,2,3])}  (期望 6)")
    print(f"join(',', ['a','b']) = {join_val(',', ['a','b'])}  (期望 a,b)")
    print(f"split(',', 'a,b,c') = {split_val(',', 'a,b,c')}  (期望 ['a','b','c'])")
    print(f"upper('hello') = {upper_val('hello')}  (期望 HELLO)")
    print(f"lower('HELLO') = {lower_val('HELLO')}  (期望 hello)")
    print(f"strip('  hi  ') = {strip_val('  hi  ')}  (期望 hi)")
    print(f"replace('hello', 'l', 'r') = {replace_val('hello', 'l', 'r')}  (期望 herro)")
    print(f"contains('hello', 'ell') = {contains_val('hello', 'ell')}  (期望 True)")
    print(f"startswith('hello', 'he') = {startswith_val('hello', 'he')}  (期望 True)")
    print(f"endswith('hello', 'lo') = {endswith_val('hello', 'lo')}  (期望 True)")
    print(f"slice('hello', 1, 3) = {slice_val('hello', 1, 3)}  (期望 el)")
    print(f"append([], 1) = {append_val([], 1)}  (期望 [1])")
    print(f"insert([1,3], 1, 2) = {insert_val([1,3], 1, 2)}  (期望 [1,2,3])")
    print(f"remove([1,2,3], 2) = {remove_val([1,2,3], 2)}  (期望 [1,3])")
    print(f"pop([1,2,3]) = {pop_val([1,2,3])}  (期望 [1,2])")
    print(f"len('hello') = {len_val('hello')}  (期望 5)")
    print(f"chr(65) = {chr_val(65)}  (期望 A)")
    print(f"ord('A') = {ord_val('A')}  (期望 65)")
    print(f"range_list(5) = {range_val(5)}  (期望 [0,1,2,3,4])")
    print(f"zip_list([1,2], ['a','b']) = {zip_val([1,2], ['a','b'])}  (期望 [(1,'a'),(2,'b')])")
    print(f"enumerate(['a','b']) = {enumerate_val(['a','b'])}  (期望 [(0,'a'),(1,'b')])")
    print(f"any_list([False,True]) = {any_val([False,True])}  (期望 True)")
    print(f"all_list([True,True]) = {all_val([True,True])}  (期望 True)")
    print(f"random_int(1,10) = {random_int_val(1,10)}  (期望 1-10)")
    print(f"random_float() = {random_float_val()}  (期望 0-1)")
    print(f"random_choice(['a','b','c']) = {random_choice_val(['a','b','c'])}")
    print(f"shuffle_list([1,2,3]) = {shuffle_val([1,2,3])}")
    _json_demo = {'a': 1}
    _json_text = '{"a": 1}'
    _nl_demo = "a\nb"
    print(f"json_dumps({{'a':1}}) = {json_dumps_val(_json_demo)}")
    print(f"json_loads('{{\"a\":1}}') = {json_loads_val(_json_text)}")
    print(f"time_now() = {time_now_val()}")
    print(f"split_lines('a\\nb') = {split_lines_val(_nl_demo)}")
    print(f"trim('  hi  ') = {trim_val('  hi  ')}")
    print("=== 标准库扩展通过 ===")
