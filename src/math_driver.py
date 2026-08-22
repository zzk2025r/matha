# -*- coding: utf-8 -*-
"""
Matha 数学驱动层 v1.3.0
========================
数学抽象封装硬件功能 — 将数学运算抽象为可执行的硬件驱动接口。

功能：
  • MathDriver     — 硬件级数学驱动（线性代数/微积分/信号处理）
  • HardwareBridge — 硬件抽象层（模拟/数字 I/O 映射）
  • MathLibrary    — 数学库管理器
  • MathHardware   — 硬件功能封装
  • 吞噬/同化：通过 FFI 和 CodeGen 将其他语言的能力纳入 Matha

吞噬策略：
  1. Python → FFI 直接调用
  2. JavaScript → CodeGen 翻译为 JS → 浏览器执行
  3. C → CodeGen 翻译为 C → 编译执行
  4. 数学公式 → CodeGen 翻译为任意语言
"""
from __future__ import annotations
import sys
import os
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List, Tuple
from enum import Enum

logger = logging.getLogger("matha.driver")


# ═══════════════════════════════════════════════════════════════════════════════
#  硬件抽象
# ═══════════════════════════════════════════════════════════════════════════════

class HardwareType(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    FPGA = "fpga"
    DSP = "dsp"
    ASIC = "asic"
    GENERIC = "generic"


@dataclass
class HardwareSpec:
    """硬件规格描述。"""
    name: str
    hw_type: HardwareType
    precision: str = "float64"
    max_ops: int = 1000000
    latency_ms: float = 0.1
    memory_mb: int = 256


@dataclass
class MathDriver:
    """
    数学驱动 — 封装硬件级数学运算。

    每个驱动对应一类数学运算：
      • LinearAlgebraDriver — 矩阵运算
      • CalculusDriver       — 微积分运算
      • SignalDriver         — 信号处理
      • GeometryDriver       — 几何计算
      • OptimizationDriver   — 优化求解
    """
    name: str
    hw_type: HardwareType
    math_ops: Dict[str, Callable] = field(default_factory=dict)
    hardware: Optional[HardwareSpec] = None
    _op_count: int = 0
    _total_latency_ms: float = 0.0

    def register_op(self, name: str, func: Callable):
        """注册数学运算。"""
        self.math_ops[name] = func
        logger.info(f"  [驱动] 注册运算: {self.name}.{name}")

    def execute(self, op_name: str, *args, **kwargs) -> Any:
        """执行数学运算。"""
        func = self.math_ops.get(op_name)
        if func is None:
            raise ValueError(f"未找到运算: {op_name}")
        start = time.time()
        result = func(*args, **kwargs)
        latency = (time.time() - start) * 1000
        self._op_count += 1
        self._total_latency_ms += latency
        logger.debug(f"  [驱动] {self.name}.{op_name}({args}) → {result} ({latency:.3f}ms)")
        return result

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "ops_executed": self._op_count,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": self._total_latency_ms / max(self._op_count, 1),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  线性代数驱动
# ═══════════════════════════════════════════════════════════════════════════════

class LinearAlgebraDriver(MathDriver):
    """线性代数驱动 — 矩阵/向量运算。"""

    def __init__(self):
        super().__init__("linear_algebra", HardwareType.CPU)
        self._register_builtin_ops()

    def _register_builtin_ops(self):
        """注册内置线性代数运算。"""
        self.register_op("dot", self._dot)
        self.register_op("cross", self._cross)
        self.register_op("mat_mul", self._mat_mul)
        self.register_op("mat_add", self._mat_add)
        self.register_op("mat_transpose", self._mat_transpose)
        self.register_op("mat_det", self._mat_det)
        self.register_op("mat_inv", self._mat_inv)
        self.register_op("eigenvalues", self._eigenvalues)
        self.register_op("norm", self._norm)
        self.register_op("matrix_power", self._mat_power)
        logger.info(f"  [线性代数驱动] 注册 {len(self.math_ops)} 个运算")

    @staticmethod
    def _dot(a: list, b: list) -> float:
        return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def _cross(a: list, b: list) -> List[float]:
        return [
            a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0]
        ]

    @staticmethod
    def _mat_mul(a: list, b: list) -> List[List[float]]:
        rows_a, cols_a = len(a), len(a[0])
        rows_b, cols_b = len(b), len(b[0])
        result = [[0.0]*cols_b for _ in range(rows_a)]
        for i in range(rows_a):
            for j in range(cols_b):
                for k in range(cols_a):
                    result[i][j] += a[i][k] * b[k][j]
        return result

    @staticmethod
    def _mat_add(a: list, b: list) -> List[List[float]]:
        return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

    @staticmethod
    def _mat_transpose(m: list) -> List[List[float]]:
        return [[m[j][i] for j in range(len(m))] for i in range(len(m[0]))]

    @staticmethod
    def _mat_det(m: list) -> float:
        n = len(m)
        if n == 1: return m[0][0]
        if n == 2: return m[0][0]*m[1][1] - m[0][1]*m[1][0]
        det = 0
        for j in range(n):
            sub = [row[:j] + row[j+1:] for row in m[1:]]
            det += ((-1) ** j) * m[0][j] * LinearAlgebraDriver._mat_det(sub)
        return det

    @staticmethod
    def _mat_inv(m: list) -> Optional[List[List[float]]]:
        """高斯-若尔当消元法求逆矩阵。"""
        n = len(m)
        aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
        for col in range(n):
            max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
            aug[col], aug[max_row] = aug[max_row], aug[col]
            pivot = aug[col][col]
            if abs(pivot) < 1e-12:
                return None
            for j in range(2 * n):
                aug[col][j] /= pivot
            for row in range(n):
                if row != col:
                    factor = aug[row][col]
                    for j in range(2 * n):
                        aug[row][j] -= factor * aug[col][j]
        return [row[n:] for row in aug]

    @staticmethod
    def _eigenvalues(m: list) -> List[float]:
        """2x2 矩阵的特征值。"""
        n = len(m)
        if n == 1: return [m[0][0]]
        if n == 2:
            tr = m[0][0] + m[1][1]
            det = m[0][0]*m[1][1] - m[0][1]*m[1][0]
            disc = tr*tr - 4*det
            if disc < 0: return []
            sq = math.sqrt(disc)
            return [(tr + sq) / 2, (tr - sq) / 2]
        return []

    @staticmethod
    def _norm(v: list, p: int = 2) -> float:
        return sum(abs(x) ** p for x in v) ** (1.0 / p)

    @staticmethod
    def _mat_power(m: list, n: int) -> List[List[float]]:
        result = [[1.0 if i == j else 0.0 for j in range(len(m))] for i in range(len(m))]
        base = [row[:] for row in m]
        while n > 0:
            if n % 2 == 1:
                result = LinearAlgebraDriver._mat_mul(result, base)
            base = LinearAlgebraDriver._mat_mul(base, base)
            n //= 2
        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  微积分驱动
# ═══════════════════════════════════════════════════════════════════════════════

class CalculusDriver(MathDriver):
    """微积分驱动 — 数值微积分运算。"""

    def __init__(self):
        super().__init__("calculus", HardwareType.CPU)
        self._register_builtin_ops()

    def _register_builtin_ops(self):
        self.register_op("derivative", self._derivative)
        self.register_op("integral", self._integral)
        self.register_op("taylor", self._taylor)
        self.register_op("limit", self._limit)
        self.register_op("newton", self._newton)
        logger.info(f"  [微积分驱动] 注册 {len(self.math_ops)} 个运算")

    @staticmethod
    def _derivative(func: Callable, x: float, h: float = 1e-8) -> float:
        return (func(x + h) - func(x - h)) / (2 * h)

    @staticmethod
    def _integral(func: Callable, a: float, b: float, n: int = 10000) -> float:
        """Simpson 积分。"""
        h = (b - a) / n
        result = func(a) + func(b)
        for i in range(1, n):
            x = a + i * h
            result += (4 if i % 2 else 2) * func(x)
        return result * h / 3

    @staticmethod
    def _taylor(func: Callable, x: float, x0: float, n: int = 5) -> float:
        """泰勒展开数值近似。"""
        h = x - x0
        result = func(x0)
        fact = 1
        for k in range(1, n + 1):
            fact *= k
            # 数值导数
            dh = 1e-8
            dk = (func(x0 + dh) - func(x0 - dh)) / (2 * dh)
            result += dk * (h ** k) / fact
            # 复用导数
            for _ in range(k - 1):
                new_dk = (dk(x0 + dh) - dk(x0 - dh)) / (2 * dh)
                dk = new_dk
        return result

    @staticmethod
    def _limit(func: Callable, x: float, direction: str = "both") -> float:
        """数值极限。"""
        eps = 1e-10
        if direction in ("both", "left"):
            left = func(x - eps)
        if direction in ("both", "right"):
            right = func(x + eps)
        if direction == "both":
            return (left + right) / 2
        return left if direction == "left" else right

    @staticmethod
    def _newton(func: Callable, x0: float, tol: float = 1e-10, max_iter: int = 100) -> float:
        """牛顿法求根。"""
        x = x0
        for _ in range(max_iter):
            fx = func(x)
            dfx = (func(x + 1e-8) - func(x - 1e-8)) / (2e-8)
            if abs(dfx) < 1e-15:
                break
            x_new = x - fx / dfx
            if abs(x_new - x) < tol:
                return x_new
            x = x_new
        return x


# ═══════════════════════════════════════════════════════════════════════════════
#  信号处理驱动
# ═══════════════════════════════════════════════════════════════════════════════

class SignalDriver(MathDriver):
    """信号处理驱动 — FFT、滤波、调制等。"""

    def __init__(self):
        super().__init__("signal", HardwareType.DSP)
        self._register_builtin_ops()

    def _register_builtin_ops(self):
        self.register_op("fft", self._fft)
        self.register_op("ifft", self._ifft)
        self.register_op("convolve", self._convolve)
        self.register_op("lowpass", self._lowpass)
        self.register_op("highpass", self._highpass)
        self.register_op("magnitude", self._magnitude)
        logger.info(f"  [信号驱动] 注册 {len(self.math_ops)} 个运算")

    @staticmethod
    def _fft(signal: List[complex]) -> List[complex]:
        """朴素 FFT（O(n²)）。"""
        n = len(signal)
        if n <= 1: return list(signal)
        even = SignalDriver._fft(signal[0::2])
        odd = SignalDriver._fft(signal[1::2])
        result = [0] * n
        for k in range(n // 2):
            w = complex(math.cos(-2*math.pi*k/n), math.sin(-2*math.pi*k/n))
            result[k] = even[k] + w * odd[k]
            result[k + n//2] = even[k] - w * odd[k]
        return result

    @staticmethod
    def _ifft(signal: List[complex]) -> List[complex]:
        conj = [x.conjugate() for x in signal]
        result = SignalDriver._fft(conj)
        return [x.conjugate() / len(signal) for x in result]

    @staticmethod
    def _convolve(a: List[float], b: List[float]) -> List[float]:
        n, m = len(a), len(b)
        result = [0.0] * (n + m - 1)
        for i in range(n):
            for j in range(m):
                result[i + j] += a[i] * b[j]
        return result

    @staticmethod
    def _lowpass(signal: List[float], cutoff: float) -> List[float]:
        """简单移动平均低通滤波。"""
        n = max(2, int(1.0 / cutoff)) if cutoff > 0 else len(signal)
        return [sum(signal[max(0,i-n//2):min(len(signal),i+n//2+1)]) / n
                for i in range(len(signal))]

    @staticmethod
    def _highpass(signal: List[float], cutoff: float) -> List[float]:
        """高通滤波 = 原始 - 低通。"""
        lp = SignalDriver._lowpass(signal, cutoff)
        return [s - l for s, l in zip(signal, lp)]

    @staticmethod
    def _magnitude(signal: List[complex]) -> List[float]:
        return [abs(x) for x in signal]


# ═══════════════════════════════════════════════════════════════════════════════
#  几何驱动
# ═══════════════════════════════════════════════════════════════════════════════

class GeometryDriver(MathDriver):
    """几何计算驱动。"""

    def __init__(self):
        super().__init__("geometry", HardwareType.GPU)
        self._register_builtin_ops()

    def _register_builtin_ops(self):
        self.register_op("circle_area", lambda r: math.pi * r * r)
        self.register_op("sphere_volume", lambda r: 4/3 * math.pi * r**3)
        self.register_op("cylinder_volume", lambda r, h: math.pi * r**2 * h)
        self.register_op("triangle_area", lambda b, h: 0.5 * b * h)
        self.register_op("distance", lambda x1, y1, x2, y2: math.sqrt((x2-x1)**2 + (y2-y1)**2))
        self.register_op("polygon_area", self._polygon_area)
        logger.info(f"  [几何驱动] 注册 {len(self.math_ops)} 个运算")

    @staticmethod
    def _polygon_area(points: List[Tuple[float, float]]) -> float:
        """鞋带公式。"""
        n = len(points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2


# ═══════════════════════════════════════════════════════════════════════════════
#  优化驱动
# ═══════════════════════════════════════════════════════════════════════════════

class OptimizationDriver(MathDriver):
    """优化求解驱动。"""

    def __init__(self):
        super().__init__("optimization", HardwareType.CPU)
        self._register_builtin_ops()

    def _register_builtin_ops(self):
        self.register_op("gradient_descent", self._gradient_descent)
        self.register_op("binary_search", self._binary_search)
        self.register_op("golden_section", self._golden_section)
        logger.info(f"  [优化驱动] 注册 {len(self.math_ops)} 个运算")

    @staticmethod
    def _gradient_descent(func: Callable, x0: float, lr: float = 0.01,
                          tol: float = 1e-8, max_iter: int = 1000) -> float:
        x = x0
        for _ in range(max_iter):
            grad = (func(x + 1e-8) - func(x - 1e-8)) / (2e-8)
            x_new = x - lr * grad
            if abs(x_new - x) < tol:
                return x_new
            x = x_new
        return x

    @staticmethod
    def _binary_search(func: Callable, lo: float, hi: float,
                       tol: float = 1e-8) -> float:
        for _ in range(100):
            mid = (lo + hi) / 2
            if func(mid) * func(lo) < 0:
                hi = mid
            else:
                lo = mid
            if hi - lo < tol:
                return (lo + hi) / 2
        return (lo + hi) / 2

    @staticmethod
    def _golden_section(func: Callable, lo: float, hi: float,
                        tol: float = 1e-8) -> float:
        golden = (math.sqrt(5) - 1) / 2
        a, b = lo, hi
        fa, fb = func(a), func(b)
        while b - a > tol:
            c = b - golden * (b - a)
            fc = func(c)
            if fc < fa:
                b, fb = c, fc
            else:
                a, fa = c, fc
        return (a + b) / 2


# ═══════════════════════════════════════════════════════════════════════════════
#  数学驱动管理器
# ═══════════════════════════════════════════════════════════════════════════════

class MathDriverManager:
    """
    数学驱动管理器 — 统一调度所有硬件级数学驱动。

    吞噬/同化策略：
      1. 新语言函数 → 注册为 MathDriver 运算
      2. 数学公式 → 翻译为目标语言代码
      3. 硬件抽象 → 统一 API 调用
    """

    def __init__(self):
        self.drivers: Dict[str, MathDriver] = {}
        self._hardware_map: Dict[str, HardwareSpec] = {}
        self._init_drivers()
        logger.info("  [驱动管理器] 初始化完成")

    def _init_drivers(self):
        """初始化所有标准驱动。"""
        drivers = [
            LinearAlgebraDriver(),
            CalculusDriver(),
            SignalDriver(),
            GeometryDriver(),
            OptimizationDriver(),
        ]
        for drv in drivers:
            self.register_driver(drv)

    def register_driver(self, driver: MathDriver):
        """注册驱动。"""
        self.drivers[driver.name] = driver
        logger.info(f"  [驱动管理器] 注册驱动: {driver.name} ({driver.hw_type.value})")

    def execute(self, driver_name: str, op_name: str, *args, **kwargs) -> Any:
        """执行驱动运算。"""
        driver = self.drivers.get(driver_name)
        if driver is None:
            raise ValueError(f"未找到驱动: {driver_name}")
        return driver.execute(op_name, *args, **kwargs)

    def list_drivers(self) -> List[dict]:
        """列出所有驱动。"""
        return [
            {"name": d.name, "type": d.hw_type.value, "ops": len(d.math_ops),
             "stats": d.get_stats()}
            for d in self.drivers.values()
        ]

    def get_stats(self) -> dict:
        """获取所有驱动统计。"""
        return {
            "total_drivers": len(self.drivers),
            "total_ops": sum(len(d.math_ops) for d in self.drivers.values()),
            "drivers": {name: d.get_stats() for name, d in self.drivers.items()},
        }

    def consume(self, lang: str, functions: List[dict]):
        """
        吞噬/同化其他语言的函数。

        lang: "python" / "javascript" / "c"
        functions: [{"name": "func_name", "params": ["a","b"], "expr": "a+b"}]
        """
        logger.info(f"  [吞噬] 同化 {lang} 语言函数: {len(functions)} 个")
        for func_info in functions:
            # 创建一个包装函数
            wrapped = self._wrap_function(lang, func_info)
            # 注册到线性代数驱动（作为通用数学运算）
            drv = self.drivers.get("linear_algebra", LinearAlgebraDriver())
            drv.register_op(func_info["name"], wrapped)
            logger.info(f"  [吞噬] 已同化: {lang}.{func_info['name']}")

    def _wrap_function(self, lang: str, func_info: dict) -> Callable:
        """将外部语言函数包装为可调用 Python 函数。"""
        def wrapper(*args, **kwargs):
            if lang == "python":
                # 直接调用 Python 函数
                return func_info.get("raw_func", lambda *a, **kw: None)(*args, **kwargs)
            elif lang == "javascript":
                # JS 函数通过 CodeGen 翻译为 Python
                try:
                    from src.symbol_codegen import MathaCodeGen
                except ImportError:
                    from .symbol_codegen import MathaCodeGen
                cg = MathaCodeGen()
                code = cg.python(func_info.get("expr", "0"))
                exec(code, globals())
                return eval(f"{func_info['name']}(*args, **kwargs)")
            elif lang == "c":
                # C 函数通过 CodeGen 翻译
                try:
                    from src.symbol_codegen import MathaCodeGen
                except ImportError:
                    from .symbol_codegen import MathaCodeGen
                cg = MathaCodeGen()
                code = cg.c(func_info.get("expr", "0"))
                exec(code, globals())
                return eval(f"{func_info['name']}(*args, **kwargs)")
            return None
        return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
#  单例
# ═══════════════════════════════════════════════════════════════════════════════

_manager_instance: Optional[MathDriverManager] = None


def get_driver_manager() -> MathDriverManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MathDriverManager()
    return _manager_instance


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha 数学驱动层 v1.3.0")
    print("=" * 60)

    mgr = MathDriverManager()
    print(f"\n[驱动列表]")
    for d in mgr.list_drivers():
        print(f"  {d['name']} ({d['type']}): {d['ops']} 个运算")

    print(f"\n[线性代数]")
    r = mgr.execute("linear_algebra", "mat_mul",
                    [[1,2],[3,4]], [[5,6],[7,8]])
    print(f"  [[1,2],[3,4]] × [[5,6],[7,8]] = {r}")

    print(f"\n[微积分]")
    f = lambda x: x**2
    r = mgr.execute("calculus", "derivative", f, 2.0)
    print(f"  d/dx(x²) at x=2 = {r:.4f}")

    r = mgr.execute("calculus", "integral", f, 0, 1)
    print(f"  ∫₀¹ x² dx = {r:.4f}")

    print(f"\n[信号处理]")
    sig = [1+0j, 1j, -1+0j, -1j]
    r = mgr.execute("signal", "fft", sig)
    print(f"  FFT([1, i, -1, -i]) = {[f'{x.real:.2f}+{x.imag:.2f}i' for x in r]}")

    print(f"\n完成。")
