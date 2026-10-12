"""Matha 数学基座：大数、FFT、矩阵、特殊函数、数值分析。"""
from __future__ import annotations

import cmath
import math
import statistics
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any


class NumberType(Enum):
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT16 = "float16"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    FLOAT128 = "float128"
    BFLOAT16 = "bfloat16"
    BIGINT = "bigint"
    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"
    QUATERNION = "quaternion"
    FIXED_POINT = "fixed_point"


class RoundingMode(Enum):
    NEAREST_EVEN = "nearest_even"
    NEAREST_AWAY = "nearest_away"
    FLOOR = "floor"
    CEIL = "ceil"
    TRUNC = "trunc"
    ROUND_UP = "round_up"


class BigNum:
    """任意精度整数。"""

    def __init__(self, value: int = 0):
        self.value = int(value)

    def __add__(self, o: Any) -> BigNum:
        return BigNum(self.value + int(o))

    def __sub__(self, o: Any) -> BigNum:
        return BigNum(self.value - int(o))

    def __mul__(self, o: Any) -> BigNum:
        return BigNum(self.value * int(o))

    def __floordiv__(self, o: Any) -> BigNum:
        return BigNum(self.value // int(o))

    def __mod__(self, o: Any) -> BigNum:
        return BigNum(self.value % int(o))

    def __pow__(self, o: int) -> BigNum:
        return BigNum(self.value ** int(o))

    def __lt__(self, o: Any) -> bool:
        return self.value < int(o)

    def __gt__(self, o: Any) -> bool:
        return self.value > int(o)

    def __eq__(self, o: Any) -> bool:
        return self.value == int(o)

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"BigNum({self.value})"

    def __str__(self) -> str:
        return str(self.value)

    def to_bytes(self, length: int,
                 byteorder: str = "big") -> bytes:
        return self.value.to_bytes(length, byteorder)

    @staticmethod
    def from_bytes(b: bytes,
                   byteorder: str = "big") -> BigNum:
        return BigNum(int.from_bytes(b, byteorder))

    @staticmethod
    def from_string(s: str) -> BigNum:
        if s.startswith(("0x", "0X")):
            return BigNum(int(s, 16))
        if s.startswith(("0b", "0B")):
            return BigNum(int(s, 2))
        if s.startswith(("0o", "0O")):
            return BigNum(int(s, 8))
        return BigNum(int(s))

    def bit_length(self) -> int:
        return self.value.bit_length()

    def is_prime(self) -> bool:
        if self.value < 2:
            return False
        if self.value < 4:
            return True
        if self.value % 2 == 0:
            return False
        for p in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if self.value % p == 0:
                return False
        d = self.value - 1
        r = 0
        while d % 2 == 0:
            d //= 2
            r += 1
        for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            x = pow(a, d, self.value)
            if x in (1, self.value - 1):
                continue
            for _ in range(r - 1):
                x = x * x % self.value
                if x == self.value - 1:
                    break
            else:
                return False
        return True

    def gcd(self, o: Any) -> BigNum:
        return BigNum(math.gcd(self.value, int(o)))

    def lcm(self, o: Any) -> BigNum:
        a, b = self.value, int(o)
        return BigNum(a * b // math.gcd(a, b))

    def mod_inverse(self, m: Any) -> BigNum | None:
        return BigNum(pow(self.value, -1, int(m)))

    def mod_pow(self, e: Any, m: Any) -> BigNum:
        return BigNum(pow(self.value, int(e), int(m)))

    def factorial(self) -> BigNum:
        return BigNum(math.factorial(self.value))

    def fibonacci(self) -> BigNum:
        a, b = 0, 1
        for _ in range(self.value):
            a, b = b, a + b
        return BigNum(a)

    def to_float(self) -> float:
        return float(self.value)

    def digits(self) -> int:
        return len(str(abs(self.value)))


class BigFloat:
    """任意精度浮点。"""

    def __init__(self, value: float = 0.0,
                 precision: int = 50):
        self.value = float(value)
        self.precision = precision

    def __add__(self, o: Any) -> BigFloat:
        return BigFloat(self.value + float(o), self.precision)

    def __sub__(self, o: Any) -> BigFloat:
        return BigFloat(self.value - float(o), self.precision)

    def __mul__(self, o: Any) -> BigFloat:
        return BigFloat(self.value * float(o), self.precision)

    def __truediv__(self, o: Any) -> BigFloat:
        return BigFloat(self.value / float(o), self.precision)

    def sqrt(self) -> BigFloat:
        return BigFloat(math.sqrt(self.value), self.precision)

    def exp(self) -> BigFloat:
        return BigFloat(math.exp(self.value), self.precision)

    def ln(self) -> BigFloat:
        return BigFloat(math.log(self.value), self.precision)

    def sin(self) -> BigFloat:
        return BigFloat(math.sin(self.value), self.precision)

    def __repr__(self) -> str:
        return f"BigFloat({self.value}, p={self.precision})"


class Quaternion:
    """四元数。"""

    def __init__(self, w: float = 1.0, x: float = 0.0,
                 y: float = 0.0, z: float = 0.0):
        self.w, self.x, self.y, self.z = w, x, y, z

    def __mul__(self, o: Quaternion) -> Quaternion:
        return Quaternion(
            self.w * o.w - self.x * o.x - self.y * o.y - self.z * o.z,
            self.w * o.x + self.x * o.w + self.y * o.z - self.z * o.y,
            self.w * o.y - self.x * o.z + self.y * o.w + self.z * o.x,
            self.w * o.z + self.x * o.y - self.y * o.x + self.z * o.w,
        )

    def conjugate(self) -> Quaternion:
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def norm(self) -> float:
        return math.sqrt(self.w ** 2 + self.x ** 2
                         + self.y ** 2 + self.z ** 2)

    def normalize(self) -> Quaternion:
        n = self.norm()
        if n == 0:
            return Quaternion()
        return Quaternion(self.w / n, self.x / n,
                          self.y / n, self.z / n)

    def rotate(self, v: tuple[float, float, float]
               ) -> tuple[float, float, float]:
        q = self.normalize() * Quaternion(0, *v) * self.conjugate()
        return (q.x, q.y, q.z)

    @staticmethod
    def from_axis_angle(axis: tuple[float, float, float],
                        angle: float) -> Quaternion:
        n = math.sqrt(sum(a ** 2 for a in axis)) or 1.0
        ax = tuple(a / n for a in axis)
        s = math.sin(angle / 2)
        return Quaternion(math.cos(angle / 2),
                          ax[0] * s, ax[1] * s, ax[2] * s)

    def to_matrix(self) -> list[list[float]]:
        n = self.norm() ** 2
        if n == 0:
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        w, x, y, z = self.w, self.x, self.y, self.z
        return [
            [1 - 2 * (y * y + z * z) / n,
             2 * (x * y - w * z) / n,
             2 * (x * z + w * y) / n],
            [2 * (x * y + w * z) / n,
             1 - 2 * (x * x + z * z) / n,
             2 * (y * z - w * x) / n],
            [2 * (x * z - w * y) / n,
             2 * (y * z + w * x) / n,
             1 - 2 * (x * x + y * y) / n],
        ]


class FFT:
    """快速傅里叶变换。"""

    @staticmethod
    def fft(signal: Sequence[complex]) -> list[complex]:
        n = len(signal)
        if n <= 1:
            return list(signal)
        padded = list(signal)
        if n & (n - 1):
            target = 1
            while target < n:
                target <<= 1
            padded += [0j] * (target - n)
            n = target
        even = FFT.fft(padded[0::2])
        odd = FFT.fft(padded[1::2])
        t = [cmath.exp(-2j * cmath.pi * k / n) * odd[k]
             for k in range(n // 2)]
        return [even[k] + t[k] for k in range(n // 2)] + \
               [even[k] - t[k] for k in range(n // 2)]

    @staticmethod
    def ifft(spectrum: Sequence[complex]) -> list[complex]:
        n = len(spectrum)
        conj = [c.conjugate() for c in spectrum]
        res = FFT.fft(conj)
        return [c.conjugate() / n for c in res]

    @staticmethod
    def fft2(matrix: list[list[float]]) -> list[list[complex]]:
        rows = [FFT.fft([complex(v, 0) for v in row])
                for row in matrix]
        cols = list(zip(*rows))
        cols2 = [FFT.fft(list(col)) for col in cols]
        return [list(r) for r in zip(*cols2)]

    @staticmethod
    def dft(signal: Sequence[complex]) -> list[complex]:
        n = len(signal)
        return [sum(signal[k] * cmath.exp(-2j * cmath.pi * k * j / n)
                    for k in range(n)) for j in range(n)]

    @staticmethod
    def power_spectrum(signal: Sequence[float]
                       ) -> list[float]:
        spec = FFT.fft([complex(v, 0) for v in signal])
        return [abs(c) ** 2 for c in spec]

    @staticmethod
    def convolution(a: Sequence[float],
                    b: Sequence[float]) -> list[float]:
        fa = FFT.fft([complex(v, 0) for v in a])
        fb = FFT.fft([complex(v, 0) for v in b])
        fc = [x * y for x, y in zip(fa, fb)]
        return [c.real for c in FFT.ifft(fc)]

    @staticmethod
    def correlate(a: Sequence[float],
                  b: Sequence[float]) -> list[float]:
        return FFT.convolution(a, list(reversed(b)))


class LinearAlgebra:
    """线性代数。"""

    @staticmethod
    def zeros(rows: int, cols: int) -> list[list[float]]:
        return [[0.0] * cols for _ in range(rows)]

    @staticmethod
    def identity(n: int) -> list[list[float]]:
        m = LinearAlgebra.zeros(n, n)
        for i in range(n):
            m[i][i] = 1.0
        return m

    @staticmethod
    def transpose(m: list[list[float]]) -> list[list[float]]:
        return [list(r) for r in zip(*m)]

    @staticmethod
    def matmul(a: list[list[float]],
               b: list[list[float]]) -> list[list[float]]:
        bt = LinearAlgebra.transpose(b)
        return [[sum(x * y for x, y in zip(row, col))
                 for col in bt] for row in a]

    @staticmethod
    def matvec(a: list[list[float]],
               v: Sequence[float]) -> list[float]:
        return [sum(x * y for x, y in zip(row, v)) for row in a]

    @staticmethod
    def det(m: list[list[float]]) -> float:
        n = len(m)
        if n == 1:
            return m[0][0]
        if n == 2:
            return m[0][0] * m[1][1] - m[0][1] * m[1][0]
        total = 0.0
        for j in range(n):
            minor = [row[:j] + row[j + 1:]
                     for row in m[1:]]
            total += ((-1) ** j) * m[0][j] * LinearAlgebra.det(minor)
        return total

    @staticmethod
    def inverse(m: list[list[float]]) -> list[list[float]]:
        n = len(m)
        d = LinearAlgebra.det(m)
        if abs(d) < 1e-12:
            raise ValueError("矩阵奇异")
        adj = LinearAlgebra.zeros(n, n)
        for i in range(n):
            for j in range(n):
                minor = [row[:i] + row[i + 1:]
                         for row in m[:j] + m[j + 1:]]
                adj[j][i] = ((-1) ** (i + j)
                             * LinearAlgebra.det(minor)) / d
        return adj

    @staticmethod
    def rank(m: list[list[float]],
             tol: float = 1e-10) -> int:
        a = [row[:] for row in m]
        rows, cols = len(a), len(a[0]) if a else 0
        rank = 0
        for c in range(cols):
            piv = max((r for r in range(rank, rows)),
                      key=lambda r: abs(a[r][c]),
                      default=rank)
            if piv >= rows or abs(a[piv][c]) < tol:
                continue
            a[rank], a[piv] = a[piv], a[rank]
            pv = a[rank][c]
            a[rank] = [x / pv for x in a[rank]]
            for r in range(rows):
                if r != rank and a[r][c] != 0:
                    f = a[r][c]
                    a[r] = [x - f * y
                            for x, y in zip(a[r], a[rank])]
            rank += 1
        return rank

    @staticmethod
    def trace(m: list[list[float]]) -> float:
        return sum(m[i][i] for i in range(len(m)))

    @staticmethod
    def norm(m: list[list[float]]) -> float:
        return math.sqrt(sum(x * x for row in m for x in row))

    @staticmethod
    def solve(a: list[list[float]],
              b: list[float]) -> list[float]:
        n = len(a)
        aug = [a[i][:] + [b[i]] for i in range(n)]
        for c in range(n):
            piv = max(range(c, n), key=lambda r: abs(aug[r][c]))
            aug[c], aug[piv] = aug[piv], aug[c]
            pv = aug[c][c]
            if abs(pv) < 1e-12:
                raise ValueError("奇异矩阵")
            aug[c] = [x / pv for x in aug[c]]
            for r in range(n):
                if r != c and aug[r][c] != 0:
                    f = aug[r][c]
                    aug[r] = [x - f * y
                              for x, y in zip(aug[r], aug[c])]
        return [aug[i][n] for i in range(n)]

    @staticmethod
    def eigenvalues_jacobi(a: list[list[float]],
                           iters: int = 100
                           ) -> tuple[list[float], list[list[float]]]:
        n = len(a)
        m = [row[:] for row in a]
        v = LinearAlgebra.identity(n)
        for _ in range(iters):
            p, q = 0, 1
            best = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    if abs(m[i][j]) > best:
                        best, p, q = abs(m[i][j]), i, j
            if best < 1e-12:
                break
            app, aqq, apq = m[p][p], m[q][q], m[p][q]
            theta = 0.5 * math.atan2(2 * apq, aqq - app)
            c, s = math.cos(theta), math.sin(theta)
            for k in range(n):
                mkp, mkq = c * m[k][p] - s * m[k][q], \
                    s * m[k][p] + c * m[k][q]
                m[k][p], m[k][q] = mkp, mkq
            for k in range(n):
                mpk, mqk = c * m[p][k] - s * m[q][k], \
                    s * m[p][k] + c * m[q][k]
                m[p][k], m[q][k] = mpk, mqk
            for k in range(n):
                vkp, vkq = c * v[k][p] - s * v[k][q], \
                    s * v[k][p] + c * v[k][q]
                v[k][p], v[k][q] = vkp, vkq
        eig = [m[i][i] for i in range(n)]
        return eig, v


class SpecialFunctions:
    """特殊函数。"""

    @staticmethod
    def gamma(x: float) -> float:
        return math.gamma(x)

    @staticmethod
    def beta(a: float, b: float) -> float:
        return math.beta(a, b)

    @staticmethod
    def erf(x: float) -> float:
        return math.erf(x)

    @staticmethod
    def erfc(x: float) -> float:
        return math.erfc(x)

    @staticmethod
    def bessel_j(n: int, x: float) -> float:
        return _bessel_j(n, x)

    @staticmethod
    def legendre(n: int, x: float) -> float:
        if n == 0:
            return 1.0
        p0, p1 = 1.0, x
        for k in range(2, n + 1):
            p0, p1 = p1, ((2 * k - 1) * x * p1
                          - (k - 1) * p0) / k
        return p1

    @staticmethod
    def hermite(n: int, x: float) -> float:
        if n == 0:
            return 1.0
        h0, h1 = 1.0, 2 * x
        for k in range(2, n + 1):
            h0, h1 = h1, 2 * x * h1 - 2 * (k - 1) * h0
        return h1

    @staticmethod
    def zeta(s: float) -> float:
        if s == 1:
            return float("inf")
        if s > 1:
            return sum(1.0 / (k ** s) for k in range(1, 100000))
        # eta function -> zeta via reflection
        eta = sum(((-1) ** (k - 1)) / (k ** s)
                  for k in range(1, 1000))
        return eta / (1 - 2 ** (1 - s))

    @staticmethod
    def dilogarithm(x: float) -> float:
        return sum(x ** k / (k * k) for k in range(1, 200))


def _bessel_j(n: int, x: float) -> float:
    return sum((-1) ** k / (math.factorial(k)
                            * math.gamma(k + n + 1))
               * (x / 2) ** (2 * k + n) for k in range(30))


class NumericalAnalysis:
    """数值分析。"""

    @staticmethod
    def bisection(f: Callable[[float], float],
                  a: float, b: float,
                  tol: float = 1e-12,
                  max_iter: int = 200) -> float:
        fa = f(a)
        for _ in range(max_iter):
            m = (a + b) / 2
            fm = f(m)
            if fa * fm <= 0:
                b = m
            else:
                a, fa = m, fm
            if abs(b - a) < tol:
                break
        return (a + b) / 2

    @staticmethod
    def newton(f: Callable[[float], float],
               df: Callable[[float], float],
               x0: float, tol: float = 1e-12,
               max_iter: int = 100) -> float:
        x = x0
        for _ in range(max_iter):
            fx = f(x)
            if abs(fx) < tol:
                break
            d = df(x)
            if abs(d) < 1e-15:
                break
            x -= fx / d
        return x

    @staticmethod
    def rk4(f: Callable[[float, float], float],
            y0: float, t0: float, t1: float,
            steps: int = 100) -> list[tuple[float, float]]:
        h = (t1 - t0) / steps
        y, t = y0, t0
        out = [(t, y)]
        for _ in range(steps):
            k1 = f(t, y)
            k2 = f(t + h / 2, y + h * k1 / 2)
            k3 = f(t + h / 2, y + h * k2 / 2)
            k4 = f(t + h, y + h * k3)
            y += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            t += h
            out.append((t, y))
        return out

    @staticmethod
    def gradient(f: Callable[..., float],
                 x: Sequence[float],
                 h: float = 1e-6) -> list[float]:
        g = []
        for i in range(len(x)):
            xp = list(x)
            xm = list(x)
            xp[i] += h
            xm[i] -= h
            g.append((f(*xp) - f(*xm)) / (2 * h))
        return g

    @staticmethod
    def hessian(f: Callable[..., float],
                x: Sequence[float],
                h: float = 1e-5) -> list[list[float]]:
        n = len(x)
        H = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                xpp = list(x); xpp[i] += h; xpp[j] += h
                xpm = list(x); xpm[i] += h; xpm[j] -= h
                xmp = list(x); xmp[i] -= h; xmp[j] += h
                xmm = list(x); xmm[i] -= h; xmm[j] -= h
                H[i][j] = (f(*xpp) - f(*xpm)
                           - f(*xmp) + f(*xmm)) / (4 * h * h)
        return H

    @staticmethod
    def trapezoid(f: Callable[[float], float],
                  a: float, b: float,
                  n: int = 1000) -> float:
        h = (b - a) / n
        s = f(a) + f(b)
        for i in range(1, n):
            s += f(a + i * h)
        return s * h / 2

    @staticmethod
    def simpson(f: Callable[[float], float],
                a: float, b: float,
                n: int = 1000) -> float:
        if n % 2:
            n += 1
        h = (b - a) / n
        s = f(a) + f(b)
        for i in range(1, n):
            s += (4 if i % 2 else 2) * f(a + i * h)
        return s * h / 3


class MathaMath:
    """数学基座统一入口。"""

    def __init__(self):
        self.la = LinearAlgebra()
        self.fft = FFT()
        self.special = SpecialFunctions()
        self.numerical = NumericalAnalysis()

    def fib(self, n: int) -> int:
        return BigNum(n).fibonacci().value

    def prime(self, n: int) -> bool:
        return BigNum(n).is_prime()

    def gcd(self, a: int, b: int) -> int:
        return BigNum(a).gcd(b).value

    def matrix_inverse(self, m: list[list[float]]
                       ) -> list[list[float]]:
        return self.la.inverse(m)

    def solve(self, a: list[list[float]],
              b: list[float]) -> list[float]:
        return self.la.solve(a, b)

    def fft_mag(self, sig: Sequence[float]) -> list[float]:
        return [abs(c) for c in FFT.fft(
            [complex(v, 0) for v in sig])]

    def stats(self, data: Sequence[float]) -> dict[str, float]:
        return {
            "mean": statistics.fmean(data),
            "median": statistics.median(data),
            "stdev": statistics.pstdev(data),
            "var": statistics.pvariance(data),
            "min": min(data), "max": max(data),
        }


def create_math_foundation() -> MathaMath:
    return MathaMath()


def create_big_num(value: int = 0) -> BigNum:
    return BigNum(value)


def create_big_float(value: float = 0.0,
                     precision: int = 50) -> BigFloat:
    return BigFloat(value, precision)


def create_quaternion(w: float = 1.0, x: float = 0.0,
                      y: float = 0.0, z: float = 0.0) -> Quaternion:
    return Quaternion(w, x, y, z)


def create_fft() -> FFT:
    return FFT()


def create_linear_algebra() -> LinearAlgebra:
    return LinearAlgebra()


def create_numerical() -> NumericalAnalysis:
    return NumericalAnalysis()


# ============================================================
# 内置注册
# ============================================================

def _register_math_foundation(builtins: dict) -> None:
    builtins["创建数学基座"] = create_math_foundation
    builtins["创建大整数"] = create_big_num
    builtins["创建高精度浮点"] = create_big_float
    builtins["创建四元数"] = create_quaternion
    builtins["创建快速傅里叶变换"] = create_fft
    builtins["创建线性代数"] = create_linear_algebra
    builtins["创建数值分析"] = create_numerical


def _math_foundation_names() -> list[str]:
    return ["创建数学基座", "创建大整数", "创建高精度浮点",
            "创建四元数", "创建快速傅里叶变换",
            "创建线性代数", "创建数值分析"]


__all__ = [
    "NumberType", "RoundingMode",
    "BigNum", "BigFloat", "Quaternion",
    "FFT", "LinearAlgebra", "SpecialFunctions",
    "NumericalAnalysis", "MathaMath",
    "create_math_foundation", "create_big_num",
    "create_big_float", "create_quaternion",
    "create_fft", "create_linear_algebra",
    "create_numerical",
    "_register_math_foundation", "_math_foundation_names",
]
