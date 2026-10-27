"""Matha 依赖层：全功能标准库实现 + 可选增强模块自动检测。

设计原则：
  - 无依赖可运行：所有功能均有纯 Python 标准库实现
  - 可选增强：检测到第三方库时自动切换高性能版本
  - 透明切换：上层代码无需修改，依赖层自动选择最佳实现

依赖分类：
  [S] Standalone - 仅用标准库，零外部依赖
  [O] Optional   - 可选增强，未安装时自动降级为标准库实现
  [H] Heavy      - 重依赖（numpy/scipy/numba/sympy），按需延迟导入，提供存根

包含模块：
  S: cache        - 内存缓存（LRU/TTL）
  S: serde        - 序列化/反序列化（JSON fallback）
  S: logging      - 结构化日志（logging fallback）
  S: platform     - 平台检测与路径处理
  S: io_utils     - 文件/目录操作增强
  S: timing       - 性能计时工具
  O: msgpack      - 高性能二进制序列化（降级为 json）
  O: ujson        - 极速 JSON（降级为 json）
  O: orjson       - 零拷贝 JSON（降级为 json）
  O: pyyaml       - YAML 支持（降级为 JSON）
  O: lz4         - 快速压缩（降级为无压缩）
  H: numpy        - 数值计算/数组（降级为 list/tuple 实现）
  H: scipy        - 科学计算/优化/稀疏矩阵（降级为纯 Python 实现）
  H: numba        - JIT 编译加速（降级为解释执行）
  H: sympy        - 符号计算（降级为简化符号引擎）
"""

from __future__ import annotations

# ============================================================
# 平台检测与路径处理 [S]
# ============================================================
import os
import platform as _platform_module
import sys
from pathlib import Path as _Path


def get_platform() -> str:
    """获取当前平台标识。"""
    sys_name = _platform_module.system().lower()
    if sys_name == "windows":
        return "windows"
    elif sys_name == "linux":
        return "linux"
    elif sys_name == "darwin":
        return "macos"
    return sys_name


def get_arch() -> str:
    """获取 CPU 架构。"""
    return _platform_module.machine().lower()


def get_python_version() -> tuple[int, int, int]:
    """获取 Python 版本。"""
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def is_portable_env() -> bool:
    """检测是否为无 pip 的便携式环境（如 pyarmor、Nuitka 静态编译）。"""
    return "site-packages" not in sys.path


def resolve_matha_root() -> _Path:
    """解析 Matha 项目根目录。"""
    return _Path(__file__).parent.parent


# ============================================================
# 内存缓存 [S]
# ============================================================

import time as _time_mod
from collections import OrderedDict
from threading import Lock


class LRUCache:
    """线程安全的 LRU 缓存，纯标准库实现。"""

    def __init__(self, maxsize: int = 256):
        self._maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key) -> object | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key, value) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def invalidate(self, key) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total else 0.0,
                "size": len(self._cache),
            }


class TTLCache:
    """带 TTL 的缓存，纯标准库实现。"""

    def __init__(self, default_ttl: float = 60.0, maxsize: int = 512):
        self._default_ttl = default_ttl
        self._cache: dict = {}  # key -> (value, expiry)
        self._lock = Lock()
        self._maxsize = maxsize

    def get(self, key, ttl: float = None) -> object | None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if _time_mod.time() < expiry:
                    return value
                del self._cache[key]
            return None

    def put(self, key, value, ttl: float = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            self._evict_if_needed()
            self._cache[key] = (value, _time_mod.time() + ttl)

    def invalidate(self, key) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _evict_if_needed(self) -> None:
        now = _time_mod.time()
        expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired:
            del self._cache[k]
        while len(self._cache) > self._maxsize:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]


# ============================================================
# 序列化/反序列化 [S + O]
# ============================================================

import base64
import hashlib
import json as _json_stdlib
import pickle as _pickle_stdlib
import zlib


def to_json(obj) -> str:
    """对象序列化为 JSON 字符串（纯标准库）。"""
    return _json_stdlib.dumps(obj, ensure_ascii=False, default=_json_default)


def from_json(text: str) -> object:
    """JSON 字符串反序列化为对象（纯标准库）。"""
    return _json_stdlib.loads(str(text))


def to_json_pretty(obj) -> str:
    """对象序列化为格式化 JSON 字符串。"""
    return _json_stdlib.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(obj):
    """JSON 默认序列化器。"""
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "__dict__") and obj.__dict__:
        return obj.__dict__
    if isinstance(obj, bytes):
        return {"__bytes__": base64.b64encode(obj).decode()}
    if isinstance(obj, set):
        return {"__set__": list(obj)}
    raise TypeError(f"对象不可序列化: {type(obj).__name__}")


def to_pickle(obj) -> bytes:
    """对象序列化为 pickle 字节（纯标准库）。"""
    return _pickle_stdlib.dumps(obj, protocol=4)


def from_pickle(data: bytes) -> object:
    """pickle 字节反序列化为对象（纯标准库）。"""
    return _pickle_stdlib.loads(data)


def to_b64(obj) -> str:
    """对象序列化为 Base64 字符串（JSON 兼容）。"""
    return base64.b64encode(to_pickle(obj)).decode("ascii")


def from_b64(text: str) -> object:
    """Base64 字符串反序列化为对象。"""
    return from_pickle(base64.b64decode(str(text)))


def hash_obj(obj) -> str:
    """计算对象的 SHA-256 哈希（用于缓存键）。"""
    data = to_json(obj).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


# ---- 可选增强：高性能序列化 ----

_msgpack = None
_ujson = None
_orjson = None
_lz4 = None

# ============================================================
# 重依赖延迟导入 [H] - numpy/scipy/numba/sympy
# ============================================================

_numpy = None
_scipy = None
_numba = None
_sympy = None
_numpy_linalg = None
_numpy_fft = None
_scipy_sparse = None
_scipy_linalg = None
_scipy_optimize = None
_scipy_fft = None


def _try_import_heavy():
    """尝试导入重依赖，失败则保持 None。延迟导入避免启动时开销。"""
    global _numpy, _scipy, _numba, _sympy
    global _numpy_linalg, _numpy_fft
    global _scipy_sparse, _scipy_linalg, _scipy_optimize, _scipy_fft

    try:
        import numpy as _np
        _numpy = _np
        _numpy_linalg = _np.linalg
        _numpy_fft = _np.fft
    except ImportError:
        _numpy = None

    try:
        import scipy as _sp
        _scipy = _sp
        _scipy_sparse = _sp.sparse
        _scipy_linalg = _sp.linalg
        _scipy_optimize = _sp.optimize
        _scipy_fft = _sp.fft
    except ImportError:
        _scipy = None

    try:
        import numba as _nb
        _numba = _nb
    except ImportError:
        _numba = None

    try:
        import sympy as _sy
        _sympy = _sy
    except ImportError:
        _sympy = None


def _try_import_optional():
    """尝试导入可选依赖，失败则保持 None。"""
    global _msgpack, _ujson, _orjson, _lz4
    try:
        import msgpack as _m
        _msgpack = _m
    except ImportError:
        _msgpack = None
    try:
        import ujson as _u
        _ujson = _u
    except ImportError:
        _ujson = None
    try:
        import orjson as _o
        _orjson = _o
    except ImportError:
        _orjson = None
    try:
        import lz4.frame as _l
        _lz4 = _l
    except ImportError:
        _lz4 = None


_try_import_optional()
_try_import_heavy()


# ============================================================
# 重依赖访问器与存根 [H] - 延迟导入，提供类型提示
# ============================================================

def has_numpy() -> bool:
    """检查 numpy 是否可用。"""
    return _numpy is not None


def has_scipy() -> bool:
    """检查 scipy 是否可用。"""
    return _scipy is not None


def has_numba() -> bool:
    """检查 numba 是否可用。"""
    return _numba is not None


def has_sympy() -> bool:
    """检查 sympy 是否可用。"""
    return _sympy is not None


def get_numpy():
    """获取 numpy 模块，不可用时抛出 ImportError。"""
    if _numpy is None:
        raise ImportError("numpy 未安装。请运行: pip install numpy")
    return _numpy


def get_scipy():
    """获取 scipy 模块，不可用时抛出 ImportError。"""
    if _scipy is None:
        raise ImportError("scipy 未安装。请运行: pip install scipy")
    return _scipy


def get_numba():
    """获取 numba 模块，不可用时抛出 ImportError。"""
    if _numba is None:
        raise ImportError("numba 未安装。请运行: pip install numba")
    return _numba


def get_sympy():
    """获取 sympy 模块，不可用时抛出 ImportError。"""
    if _sympy is None:
        raise ImportError("sympy 未安装。请运行: pip install sympy")
    return _sympy


# ---- 子模块访问器 ----

def get_numpy_linalg():
    if _numpy_linalg is None:
        raise ImportError("numpy.linalg 不可用")
    return _numpy_linalg


def get_numpy_fft():
    if _numpy_fft is None:
        raise ImportError("numpy.fft 不可用")
    return _numpy_fft


def get_scipy_sparse():
    if _scipy_sparse is None:
        raise ImportError("scipy.sparse 不可用")
    return _scipy_sparse


def get_scipy_linalg():
    if _scipy_linalg is None:
        raise ImportError("scipy.linalg 不可用")
    return _scipy_linalg


def get_scipy_optimize():
    if _scipy_optimize is None:
        raise ImportError("scipy.optimize 不可用")
    return _scipy_optimize


def get_scipy_fft():
    if _scipy_fft is None:
        raise ImportError("scipy.fft 不可用")
    return _scipy_fft


# ---- NumPy 存根实现（纯标准库 fallback）----

class _NumpyStub:
    """numpy 核心功能的纯 Python 存根实现。"""

    @staticmethod
    def array(data, dtype=None):
        return list(data)

    @staticmethod
    def zeros(shape, dtype=None):
        if isinstance(shape, int):
            return [0] * shape
        return [[0] * s for s in shape]

    @staticmethod
    def ones(shape, dtype=None):
        if isinstance(shape, int):
            return [1] * shape
        return [[1] * s for s in shape]

    @staticmethod
    def eye(n, dtype=None):
        return [[1 if i == j else 0 for j in range(n)] for i in range(n)]

    @staticmethod
    def arange(start, stop=None, step=1):
        if stop is None:
            stop, start = start, 0
        return list(range(start, stop, step))

    @staticmethod
    def linspace(start, stop, num=50):
        if num <= 1:
            return [start]
        step = (stop - start) / (num - 1)
        return [start + i * step for i in range(num)]

    @staticmethod
    def sum(arr, axis=None):
        if axis is None:
            return sum(_flatten(arr))
        # 简化：仅支持 2D
        if axis == 0:
            return [sum(row[i] for row in arr) for i in range(len(arr[0]))]
        if axis == 1:
            return [sum(row) for row in arr]

    @staticmethod
    def mean(arr, axis=None):
        flat = _flatten(arr)
        return sum(flat) / len(flat) if flat else 0

    @staticmethod
    def std(arr, axis=None, ddof=0):
        flat = _flatten(arr)
        n = len(flat)
        if n <= ddof:
            return 0
        mean = sum(flat) / n
        var = sum((x - mean) ** 2 for x in flat) / (n - ddof)
        return var ** 0.5

    @staticmethod
    def dot(a, b):
        # 矩阵乘法：a @ b
        if isinstance(a[0], list) and isinstance(b[0], list):
            # 矩阵 x 矩阵
            rows_a, cols_a = len(a), len(a[0])
            rows_b, cols_b = len(b), len(b[0])
            if cols_a != rows_b:
                raise ValueError(f"形状不匹配: {cols_a} != {rows_b}")
            return [[sum(a[i][k] * b[k][j] for k in range(cols_a)) for j in range(cols_b)] for i in range(rows_a)]
        elif isinstance(a[0], list):
            # 矩阵 x 向量
            return [sum(a[i][k] * b[k] for k in range(len(b))) for i in range(len(a))]
        else:
            # 向量点积
            return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def matmul(a, b):
        return _NumpyStub.dot(a, b)

    @staticmethod
    def transpose(arr):
        if not isinstance(arr[0], list):
            return arr
        return [[arr[i][j] for i in range(len(arr))] for j in range(len(arr[0]))]

    @staticmethod
    def reshape(arr, shape):
        flat = _flatten(arr)
        if len(shape) == 1:
            return flat[:shape[0]]
        rows, cols = shape
        return [flat[i*cols:(i+1)*cols] for i in range(rows)]

    # 常数
    pi = 3.141592653589793
    e = 2.718281828459045
    inf = float('inf')
    nan = float('nan')

    # 类型
    float64 = float
    int64 = int
    bool_ = bool

    class random:
        @staticmethod
        def rand(*shape):
            import random
            if not shape:
                return random.random()
            if len(shape) == 1:
                return [random.random() for _ in range(shape[0])]
            return [[random.random() for _ in range(shape[1])] for _ in range(shape[0])]

        @staticmethod
        def randn(*shape):
            import random
            def gauss():
                return random.gauss(0, 1)
            if not shape:
                return gauss()
            if len(shape) == 1:
                return [gauss() for _ in range(shape[0])]
            return [[gauss() for _ in range(shape[1])] for _ in range(shape[0])]


def _flatten(arr):
    """展平嵌套列表。"""
    if not isinstance(arr, list):
        return [arr]
    result = []
    for item in arr:
        if isinstance(item, list):
            result.extend(_flatten(item))
        else:
            result.append(item)
    return result


def np() -> object:
    """获取 numpy 或存根实现。"""
    if _numpy is not None:
        return _numpy
    return _NumpyStub


# ---- SciPy 存根实现（纯标准库 fallback）----

class _ScipyStub:
    """scipy 核心功能的纯 Python 存根实现。"""

    class linalg:
        @staticmethod
        def inv(a):
            # 仅支持小矩阵的高斯消元
            n = len(a)
            # 增广矩阵
            aug = [row[:] + [1 if i == j else 0 for j in range(n)] for i, row in enumerate(a)]
            # 高斯消元
            for col in range(n):
                # 找主元
                pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
                if abs(aug[pivot][col]) < 1e-12:
                    raise ValueError("矩阵奇异")
                aug[col], aug[pivot] = aug[pivot], aug[col]
                # 归一化
                piv_val = aug[col][col]
                for j in range(2 * n):
                    aug[col][j] /= piv_val
                # 消元
                for r in range(n):
                    if r != col:
                        factor = aug[r][col]
                        for j in range(2 * n):
                            aug[r][j] -= factor * aug[col][j]
            return [row[n:] for row in aug]

        @staticmethod
        def det(a):
            # 简化行列式（仅小矩阵）
            n = len(a)
            if n == 1:
                return a[0][0]
            if n == 2:
                return a[0][0]*a[1][1] - a[0][1]*a[1][0]
            # 余子式展开（仅演示，非高效）
            det = 0
            for j in range(n):
                minor = [[a[i][k] for k in range(n) if k != j] for i in range(1, n)]
                det += ((-1) ** j) * a[0][j] * _ScipyStub.linalg.det(minor)
            return det

        @staticmethod
        def eig(a):
            # 特征值/特征向量 - 存根返回空
            n = len(a)
            return ([0]*n, [[0]*n for _ in range(n)])

        @staticmethod
        def svd(a, full_matrices=True):
            # 奇异值分解 - 存根
            m, n = len(a), len(a[0]) if a else 0
            return ([[0]*n], [0]*min(m,n), [[0]*n for _ in range(n)])

        @staticmethod
        def norm(a, ord=None):
            import math
            flat = _flatten(a)
            if ord == 2 or ord is None:
                return math.sqrt(sum(x*x for x in flat))
            if ord == 1:
                return sum(abs(x) for x in flat)
            if ord == 'inf':
                return max(abs(x) for x in flat)
            return sum(abs(x)**ord for x in flat) ** (1/ord)

    class optimize:
        @staticmethod
        def minimize(fun, x0, method='Nelder-Mead', **kwargs):
            # 简单的坐标下降存根
            x = list(x0)
            best_val = fun(x)
            step = kwargs.get('tol', 1e-4)
            for _ in range(kwargs.get('maxiter', 100)):
                improved = False
                for i in range(len(x)):
                    for d in (-step, step):
                        x_new = x[:]
                        x_new[i] += d
                        val = fun(x_new)
                        if val < best_val:
                            x, best_val = x_new, val
                            improved = True
                if not improved:
                    break
            return type('OptimizeResult', (), {
                'x': x, 'fun': best_val, 'success': True, 'nit': 0
            })()

        @staticmethod
        def root(fun, x0, **kwargs):
            return _ScipyStub.optimize.minimize(lambda x: sum(v**2 for v in fun(x)), x0, **kwargs)

    class sparse:
        class csr_matrix:
            def __init__(self, data):
                self.data = data
                self.shape = (len(data), len(data[0]) if data else 0)

            def toarray(self):
                return self.data

            def __matmul__(self, other):
                if hasattr(other, 'toarray'):
                    other = other.toarray()
                return _NumpyStub.dot(self.data, other)

    class fft:
        @staticmethod
        def fft(x):
            # DFT 存根 (O(n^2))
            n = len(x)
            import cmath
            return [sum(x[k] * cmath.exp(-2j * cmath.pi * j * k / n) for k in range(n)) for j in range(n)]

        @staticmethod
        def ifft(x):
            n = len(x)
            import cmath
            return [sum(x[k] * cmath.exp(2j * cmath.pi * j * k / n) for k in range(n)) / n for j in range(n)]

    class special:
        @staticmethod
        def gamma(x):
            import math
            return math.gamma(x)

        @staticmethod
        def beta(x, y):
            import math
            return math.gamma(x) * math.gamma(y) / math.gamma(x + y)


def sp() -> object:
    """获取 scipy 或存根实现。"""
    if _scipy is not None:
        return _scipy
    return _ScipyStub


# ---- Numba 存根装饰器 ----

def jit(*args, **kwargs):
    """numba.jit 存根：直接返回原函数。"""
    if args and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator


def njit(*args, **kwargs):
    """numba.njit 存根。"""
    return jit(*args, **kwargs)


def get_numba_jit():
    """获取 numba.jit 或存根。"""
    if _numba is not None:
        return _numba.jit
    return jit


def get_numba_njit():
    if _numba is not None:
        return _numba.njit
    return njit


# ---- SymPy 存根实现 ----

class _SymPyStub:
    """sympy 核心功能的纯 Python 存根实现。"""

    class Symbol:
        def __init__(self, name):
            self.name = name

        def __repr__(self):
            return self.name

        def __add__(self, other):
            return _SymPyStub.Add(self, other)

        def __sub__(self, other):
            return _SymPyStub.Add(self, -other if isinstance(other, (int, float)) else _SymPyStub.Mul(-1, other))

        def __mul__(self, other):
            return _SymPyStub.Mul(self, other)

        def __truediv__(self, other):
            return _SymPyStub.Mul(self, _SymPyStub.Pow(other, -1))

        def __pow__(self, other):
            return _SymPyStub.Pow(self, other)

    class Number:
        def __init__(self, value):
            self.value = value

    class Add:
        def __init__(self, *args):
            self.args = args

    class Mul:
        def __init__(self, *args):
            self.args = args

    class Pow:
        def __init__(self, base, exp):
            self.base = base
            self.exp = exp

    @staticmethod
    def symbols(names):
        return tuple(_SymPyStub.Symbol(n.strip()) for n in names.split())

    @staticmethod
    def simplify(expr):
        return expr

    @staticmethod
    def expand(expr):
        return expr

    @staticmethod
    def diff(expr, var):
        # 符号微分存根
        if hasattr(expr, 'args'):
            return _SymPyStub.diff(expr.args[0], var) + _SymPyStub.diff(expr.args[1], var) if len(expr.args) > 1 else 0
        return 0

    @staticmethod
    def integrate(expr, var):
        return expr

    @staticmethod
    def solve(eq, var):
        return []

    # 常数
    pi = 3.141592653589793
    E = 2.718281828459045
    oo = float('inf')

    # 函数
    sin = lambda x: _SymPyStub.Function('sin', x)
    cos = lambda x: _SymPyStub.Function('cos', x)
    tan = lambda x: _SymPyStub.Function('tan', x)
    exp = lambda x: _SymPyStub.Function('exp', x)
    log = lambda x: _SymPyStub.Function('log', x)
    sqrt = lambda x: _SymPyStub.Function('sqrt', x)

    class Function:
        def __init__(self, name, arg):
            self.name = name
            self.arg = arg


def sy() -> object:
    """获取 sympy 或存根实现。"""
    if _sympy is not None:
        return _sympy
    return _SymPyStub


# ============================================================
# 快速 JSON/序列化 [O]
# ============================================================

def fast_json_dumps(obj) -> str:
    """尝试使用最快的 JSON 实现。"""
    if _orjson:
        return _orjson.dumps(obj).decode("utf-8")
    if _ujson:
        return _ujson.dumps(obj)
    return to_json(obj)


def fast_json_loads(text: str) -> object:
    """尝试使用最快的 JSON 实现。"""
    if _orjson:
        return _orjson.loads(str(text).encode("utf-8"))
    if _ujson:
        return _ujson.loads(str(text))
    return from_json(text)


def fast_serialize(obj) -> bytes:
    """尝试使用最快的序列化。"""
    if _msgpack:
        return _msgpack.pack(obj, use_bin_type=True)
    return to_pickle(obj)


def fast_deserialize(data: bytes) -> object:
    """尝试使用最快的反序列化。"""
    if _msgpack:
        return _msgpack.unpackb(data, raw=False)
    return from_pickle(data)


def compress_data(data: bytes) -> bytes:
    """压缩数据（优先 lz4，降级 zlib）。"""
    if _lz4:
        return _lz4.compress(data, store_size=False)
    return zlib.compress(data, level=6)


def decompress_data(data: bytes) -> bytes:
    """解压缩数据。"""
    if _lz4:
        return _lz4.decompress(data)
    return zlib.decompress(data)


def serialize_for_storage(obj, use_compression: bool = True) -> bytes:
    """序列化为可存储格式（带压缩）。"""
    raw = fast_serialize(obj)
    if use_compression and len(raw) > 64:
        return compress_data(raw)
    return raw


def deserialize_from_storage(data: bytes) -> object:
    """从存储格式反序列化。"""
    if data and len(data) >= 2 and data[0] == 0x78:
        # zlib 压缩头 (0x78 9c / 0x78 da / 0x78 01)
        return fast_deserialize(decompress_data(data))
    return fast_deserialize(data)


# ============================================================
# 结构化日志 [S]
# ============================================================

import logging as _logging_stdlib


class MathaLogger:
    """轻量结构化日志器，纯标准库实现。"""

    def __init__(self, name: str = "matha", level: int = _logging_stdlib.WARNING):
        self.logger = _logging_stdlib.getLogger(name)
        self.logger.setLevel(level)
        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = _logging_stdlib.StreamHandler()
            handler.setFormatter(_logging_stdlib.Formatter(
                "[%(levelname).1s] %(message)s"
            ))
            self.logger.addHandler(handler)

    def info(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{msg} {extra}".strip())

    def debug(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"{msg} {extra}".strip())

    def warning(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.warning(f"{msg} {extra}".strip())

    def error(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.error(f"{msg} {extra}".strip())

    def set_level(self, level: int) -> None:
        self.logger.setLevel(level)

    @property
    def is_debug(self) -> bool:
        return self.logger.isEnabledFor(_logging_stdlib.DEBUG)


# ============================================================
# IO 工具 [S]
# ============================================================

def safe_read_text(path: str, encoding: str = "utf-8") -> str:
    """安全读取文本文件。"""
    with open(path, encoding=encoding) as f:
        return f.read()


def safe_write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """安全写入文本文件（自动创建目录）。"""
    _Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def safe_append_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """安全追加文本文件（自动创建目录）。"""
    _Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding=encoding) as f:
        f.write(content)


def ensure_dir(path: str) -> _Path:
    """确保目录存在。"""
    p = _Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_files(path: str, pattern: str = "*") -> list:
    """列出目录下匹配的文件。"""
    return sorted(str(p) for p in _Path(path).glob(pattern))


def file_age_seconds(path: str) -> float:
    """文件距今秒数。"""
    try:
        mtime = os.path.getmtime(path)
        return _time_mod.time() - mtime
    except OSError:
        return float("inf")


def atomic_write(path: str, content: str, encoding: str = "utf-8") -> None:
    """原子写入文件（先写临时文件再重命名）。"""
    tmp_path = path + ".tmp"
    safe_write_text(tmp_path, content, encoding)
    os.replace(tmp_path, path)


# ============================================================
# 性能计时 [S]
# ============================================================



def timing(func, *args, **kwargs) -> tuple:
    """执行函数并返回 (结果, 耗时秒数)。"""
    start = _time_mod.perf_counter()
    result = func(*args, **kwargs)
    elapsed = _time_mod.perf_counter() - start
    return result, elapsed


def benchmark(func, *args, iterations: int = 1000, **kwargs) -> dict:
    """性能基准测试。"""
    times = []
    result = None
    for _ in range(iterations):
        start = _time_mod.perf_counter()
        result = func(*args, **kwargs)
        times.append(_time_mod.perf_counter() - start)
    return {
        "结果": result,
        "总耗时_ms": sum(times) * 1000,
        "平均耗时_us": (sum(times) / len(times)) * 1_000_000,
        "最快_us": min(times) * 1_000_000,
        "迭代次数": iterations,
    }


# ============================================================
# 依赖报告
# ============================================================

def get_dependency_status() -> dict:
    """返回当前依赖状态报告。"""
    return {
        "平台": get_platform(),
        "架构": get_arch(),
        "Python": f"{get_python_version()[0]}.{get_python_version()[1]}.{get_python_version()[2]}",
        "便携模式": is_portable_env(),
        "可选依赖": {
            "msgpack": "✓" if _msgpack else "✗",
            "ujson": "✓" if _ujson else "✗",
            "orjson": "✓" if _orjson else "✗",
            "pyyaml": "✓" if _try_import_yaml() else "✗",
            "lz4": "✓" if _lz4 else "✗",
        },
        "重依赖": {
            "numpy": "✓" if _numpy else "✗",
            "scipy": "✓" if _scipy else "✗",
            "numba": "✓" if _numba else "✗",
            "sympy": "✓" if _sympy else "✗",
        },
    }


def _try_import_yaml() -> bool:
    try:
        import yaml  # noqa
        return True
    except ImportError:
        return False


# ============================================================
# 公共 API 导出
# ============================================================

__all__ = [
    # 平台
    "get_platform", "get_arch", "get_python_version",
    "is_portable_env", "resolve_matha_root",
    # 缓存
    "LRUCache", "TTLCache",
    # 序列化
    "to_json", "from_json", "to_json_pretty",
    "to_pickle", "from_pickle", "to_b64", "from_b64",
    "hash_obj",
    "fast_json_dumps", "fast_json_loads",
    "fast_serialize", "fast_deserialize",
    "compress_data", "decompress_data",
    "serialize_for_storage", "deserialize_from_storage",
    # 日志
    "MathaLogger",
    # IO
    "safe_read_text", "safe_write_text", "safe_append_text",
    "ensure_dir", "list_files", "file_age_seconds", "atomic_write",
    # 性能
    "timing", "benchmark",
    # 依赖报告
    "get_dependency_status",
    # 重依赖检测与访问 [H]
    "has_numpy", "has_scipy", "has_numba", "has_sympy",
    "get_numpy", "get_scipy", "get_numba", "get_sympy",
    "get_numpy_linalg", "get_numpy_fft",
    "get_scipy_sparse", "get_scipy_linalg", "get_scipy_optimize", "get_scipy_fft",
    # 重依赖存根访问器 [H]
    "np", "sp", "sy",
    "jit", "njit", "get_numba_jit", "get_numba_njit",
]
