# API 参考：依赖层 (src.deps)

## 概览

`src.deps` 是 Matha 的依赖隔离层，提供：
- **零依赖运行**：核心功能仅依赖 Python 标准库
- **可选增强**：检测到第三方库时自动切换高性能版本
- **重依赖存根**：numpy/scipy/numba/sympy 的纯 Python fallback 实现

## 依赖分类

| 分类 | 标识 | 说明 |
|------|------|------|
| 独立 | [S] | 仅标准库，零外部依赖 |
| 可选 | [O] | 可选增强，降级为标准库 |
| 重依赖 | [H] | numpy/scipy/numba/sympy，按需延迟导入 |

## 平台检测 [S]

```python
from src.deps import get_platform, get_arch, get_python_version, is_portable_env, resolve_matha_root

get_platform()      # "windows" | "linux" | "macos"
get_arch()          # "amd64" | "arm64" | ...
get_python_version() # (3, 11, 9)
is_portable_env()   # True 如果是便携式环境
resolve_matha_root() # Path 对象
```

## 缓存 [S]

### LRUCache

```python
from src.deps import LRUCache

cache = LRUCache(maxsize=256)
cache.put("key", "value")
value = cache.get("key")
cache.invalidate("key")
cache.clear()
stats = cache.stats  # {"hits": 10, "misses": 2, "hit_rate": 0.83, "size": 5}
```

### TTLCache

```python
from src.deps import TTLCache

cache = TTLCache(default_ttl=60.0, maxsize=512)
cache.put("key", "value", ttl=30.0)  # 30秒过期
value = cache.get("key", ttl=30.0)
```

## 序列化 [S + O]

### 标准库实现

```python
from src.deps import (
    to_json, from_json, to_json_pretty,
    to_pickle, from_pickle,
    to_b64, from_b64,
    hash_obj
)

# JSON
json_str = to_json({"a": 1, "b": [1,2,3]})
obj = from_json(json_str)

# Pickle
data = to_pickle(obj)
obj = from_pickle(data)

# Base64
b64 = to_b64(obj)
obj = from_b64(b64)

# 哈希
key = hash_obj({"complex": "object"})
```

### 高性能实现 [O]

```python
from src.deps import (
    fast_json_dumps, fast_json_loads,
    fast_serialize, fast_deserialize,
    compress_data, decompress_data,
    serialize_for_storage, deserialize_from_storage
)

# 自动选择最快实现: orjson > ujson > json
json_str = fast_json_dumps(obj)
obj = fast_json_loads(json_str)

# 自动选择最快序列化: msgpack > pickle
data = fast_serialize(obj)
obj = fast_deserialize(data)

# 压缩 (lz4 > zlib)
compressed = compress_data(data)
data = decompress_data(compressed)

# 存储格式 (序列化 + 可选压缩)
stored = serialize_for_storage(obj, use_compression=True)
obj = deserialize_from_storage(stored)
```

## 结构化日志 [S]

```python
from src.deps import MathaLogger

logger = MathaLogger("my_module", level=logging.DEBUG)
logger.info("处理完成", count=42, duration=0.123)
logger.debug("调试信息", var="value")
logger.warning("警告", retry=3)
logger.error("错误", code=500)
logger.set_level(logging.INFO)
```

## IO 工具 [S]

```python
from src.deps import (
    safe_read_text, safe_write_text, safe_append_text,
    ensure_dir, list_files, file_age_seconds, atomic_write
)

content = safe_read_text("file.txt")
safe_write_text("file.txt", "content")
safe_append_text("log.txt", "new line\n")
ensure_dir("path/to/dir")
files = list_files("dir", "*.py")
age = file_age_seconds("file.txt")
atomic_write("config.json", '{"key": "value"}')
```

## 性能计时 [S]

```python
from src.deps import timing, benchmark

# 单次计时
result, elapsed = timing(lambda: sum(range(10000)))

# 基准测试
stats = benchmark(lambda: sum(range(10000)), iterations=1000)
# {"结果": 49995000, "总耗时_ms": 123.4, "平均耗时_us": 123.4, "最快_us": 98.7, "迭代次数": 1000}
```

## 重依赖检测与访问 [H]

### 检测可用性

```python
from src.deps import has_numpy, has_scipy, has_numba, has_sympy

if has_numpy():
    import numpy as np
    # 使用 numpy
```

### 安全获取

```python
from src.deps import get_numpy, get_scipy, get_numba, get_sympy

# 抛出 ImportError 如果不可用
np = get_numpy()
sp = get_scipy()
nb = get_numba()
sy = get_sympy()
```

### 子模块访问

```python
from src.deps import (
    get_numpy_linalg, get_numpy_fft,
    get_scipy_sparse, get_scipy_linalg,
    get_scipy_optimize, get_scipy_fft
)

linalg = get_numpy_linalg()
sparse = get_scipy_sparse()
optimize = get_scipy_optimize()
```

### 存根访问器（自动 fallback）

```python
from src.deps import np, sp, sy

# 返回真实模块或存根实现
np = np()      # numpy 或 _NumpyStub
sp = sp()      # scipy 或 _ScipyStub
sy = sy()      # sympy 或 _SymPyStub

# 使用示例（无论是否安装均可工作）
arr = np.array([1, 2, 3])
mat = np.matmul([[1,2],[3,4]], [[5,6],[7,8]])
inv = sp.linalg.inv([[4,7],[2,6]])
x = sy.Symbol('x')
expr = x**2 + 2*x + 1
```

### Numba 装饰器存根

```python
from src.deps import jit, njit, get_numba_jit, get_numba_njit

# 直接使用（无 numba 时为 no-op）
@jit
def fast_func(x):
    return x * 2

@njit
def faster_func(x):
    return x + 1

# 或获取装饰器
jit_decorator = get_numba_jit()
njit_decorator = get_numba_njit()
```

## 依赖状态报告

```python
from src.deps import get_dependency_status

status = get_dependency_status()
# {
#   "平台": "windows",
#   "架构": "amd64",
#   "Python": "3.11.9",
#   "便携模式": True,
#   "可选依赖": {"msgpack": "✗", "ujson": "✗", ...},
#   "重依赖": {"numpy": "✓", "scipy": "✗", "numba": "✗", "sympy": "✓"}
# }
```

## 在 Matha 代码中使用

```matha
use 依赖层

# 检查 numpy 是否可用
如果 有_numpy() 那么
  # 使用高性能路径
  结果 = numpy_计算(数据)
否则
  # 使用纯 Python 存根
  结果 = 存根_计算(数据)
```

## 设计原则

1. **导入零开销**：重依赖延迟导入，仅在首次调用 `get_*` 或 `np()` 时尝试导入
2. **类型安全**：存根实现保持相同的 API 签名
3. **透明切换**：上层代码无需修改，依赖层自动选择最佳实现
4. **明确报错**：`get_*` 系列在不可用时抛出明确的 `ImportError`
5. **可测试性**：存根实现可单独测试，确保 fallback 行为正确

## 扩展新依赖

```python
# 在 deps.py 中添加新的可选依赖
_newlib = None

def _try_import_newlib():
    global _newlib
    try:
        import newlib as _n
        _newlib = _n
    except ImportError:
        _newlib = None

def has_newlib() -> bool:
    return _newlib is not None

def get_newlib():
    if _newlib is None:
        raise ImportError("newlib 未安装")
    return _newlib
```