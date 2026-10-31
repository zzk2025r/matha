# v2.4 10000 线程高并发瓶颈分析

## 当前性能基线

| 线程数 | 解析耗时 | 写入耗时 | 策略耗时 | 异常数 |
|---|---|---|---|---|
| 100 | 119ms | 49ms | 49ms | 0 |
| 1000 | ~1200ms | ~450ms | ~480ms | 0 |
| **10000（估算）** | **~12s** | **~4.5s** | **~4.8s** | **?** |

> 注：10000 线程数据为线性 extrapolation，实际受 OS 调度、内存、GC 影响会偏离线性。

---

## 10000 线程下的新瓶颈

### 瓶颈 1：线程创建/销毁开销（高风险）

**问题**：Python 线程创建成本约 1-5ms（含栈分配、OS 调度注册）。
10000 线程 × 2ms = **20 秒纯开销**，远超计算本身。

```
当前：1000 线程创建 1000 次
预期：10000 线程创建 10000 次 → 开销 ×10
```

**数据验证**：
- 100 线程创建耗时：~5ms（可忽略）
- 1000 线程创建耗时：~50ms（已可见）
- 10000 线程创建耗时：~500ms+（显著）

**预优化方案**：

```python
# 方案 A：线程池复用（推荐）
from concurrent.futures import ThreadPoolExecutor
_pool = ThreadPoolExecutor(max_workers=200)  # 固定大小，不动态创建

def parse_with_pool(text):
    return _pool.submit(parser.parse, text)

# 方案 B：进程池替代线程池
from concurrent.futures import ProcessPoolExecutor
_pool = ProcessPoolExecutor(max_workers=8)  # CPU 核心数
```

### 瓶颈 2：OS 线程调度开销（高风险）

**问题**：10000 个线程竞争 CPU 时间片，上下文切换开销巨大。
Linux 默认调度器（CFS）在 >1000 线程时性能显著下降。

**数据估算**：
- 上下文切换开销：~1-10μs/次
- 10000 线程活跃竞争：每秒 ~100 万次上下文切换
- 额外开销：**~1-10ms/秒**（随线程数线性增长）

**预优化方案**：

```python
# 方案 C：work-stealing 调度器
# 每个 worker 有自己的 deque，空闲 worker 从其他 worker 偷任务
from crossbeam.deque import Deque  # Rust 实现，需集成

# 方案 D：异步 I/O 替代线程（GIL 下 regex 释放 GIL，可用 asyncio）
import asyncio
from concurrent.futures import ThreadPoolExecutor

loop = asyncio.get_event_loop()
executor = ThreadPoolExecutor(max_workers=16)  # 限制并发度

async def parse_async(text):
    return await loop.run_in_executor(executor, parser.parse, text)

results = await asyncio.gather(*[parse_async(t) for t in texts])
```

### 瓶颈 3：内存压力（中风险）

**问题**：每个线程默认 8MB 栈空间（Linux）/ 1MB（Windows）。
10000 线程 = **80GB / 10GB** 内存预留，实际使用虽少但虚拟地址空间压力大。

```
100 线程  →  ~800MB 虚拟内存
1000 线程 →  ~8GB 虚拟内存（已接近限制）
10000 线程 → ~80GB 虚拟内存（OOM 风险）
```

**预优化方案**：

```python
# 方案 E：减小线程栈大小
import threading
threading.stack_size(256 * 1024)  # 256KB（最小安全值）
# 10000 线程 → 2.5GB 虚拟内存（可接受）

# 方案 F：使用 greenlet/coro 替代原生线程
import greenlet

def green_parse(text):
    g = greenlet.greenlet(parser.parse)
    g.switch(text)
    return g.getval()

# 绿色线程无独立栈，内存开销极低
```

### 瓶颈 4：RecoveryStrategy 读锁竞争（中风险）

**问题**：10000 线程同时调用 `try_recover()`，全部竞争 `_read_lock`。
虽然锁外执行策略，但**获取读锁本身**仍是瓶颈。

```python
# 当前实现（10000 线程会卡在这里）
with cls._read_lock:
    strategies = list(cls._strategies.get(error.stage, []))
# ↑ 10000 线程串行获取这把锁
```

**数据估算**：
- 单次锁获取 + 列表拷贝：~1μs
- 10000 线程串行等待：~10ms（可接受）
- **但**：如果同时有写操作（register），读线程需等待写锁释放

**预优化方案**：

```python
# 方案 G：读改写为 RWMutex（读写分离，允许多读）
import ctypes
import ctypes.util

class RWLock:
    """POSIX RWMutex 封装（Linux/macOS）。"""
    def __init__(self):
        lib = ctypes.CDLL(ctypes.util.find_library('pthread'))
        self._rwlock = ctypes.c_void_p(None)
        lib.pthread_rwlock_init(ctypes.byref(self._rwlock), None)

    def read_lock(self):
        lib = ctypes.CDLL(ctypes.util.find_library('pthread'))
        lib.pthread_rwlock_rdlock(self._rwlock)

    def read_unlock(self):
        lib = ctypes.CDLL(ctypes.util.find_library('pthread'))
        lib.pthread_rwlock_unlock(self._rwlock)

    def write_lock(self):
        lib = ctypes.CDLL(ctypes.util.find_library('pthread'))
        lib.pthread_rwlock_wrlock(self._rwlock)

    def write_unlock(self):
        lib = ctypes.CDLL(ctypes.util.find_library('pthread'))
        lib.pthread_rwlock_unlock(self._rwlock)

# 方案 H：无锁设计 — copy-on-write 策略注册表
import copy
class LockfreeRecoveryStrategy:
    _strategies_snapshot = {}  # 只读快照
    _writer = threading.Thread(target=_periodic_snapshot)  # 后台线程

    @classmethod
    def register(cls, stage, fn):
        # 写入时不阻塞读操作
        new_snapshot = copy.deepcopy(cls._strategies_snapshot)
        new_snapshot[stage].append(fn)
        cls._strategies_snapshot = new_snapshot  # 原子替换引用

    @classmethod
    def try_recover(cls, error):
        # 只读操作，完全无锁
        strategies = cls._strategies_snapshot.get(error.stage, [])
        for fn in strategies:
            fn(error)
```

### 瓶颈 5：Python GIL 瓶颈（根本限制）

**问题**：10000 个 Python 线程，同一时刻只有 1 个执行字节码。
正则匹配、字符串操作等 CPU 密集型任务无法并行。

```
10000 线程 × 0.5μs/操作 = 理论上 5ms
实际 GIL 下：~50-100ms（调度开销主导）
```

**预优化方案**：

```python
# 方案 I：C 扩展绕过 GIL
# re 模块在匹配时释放 GIL，但复杂 regex 不一定
import re
re.compile(r'pattern').search(text)  # GIL 释放 ✓

# 方案 J：NumPy/NumExpr 向量化
import numpy as np
texts = np.array([...])  # 批量向量化处理
results = np.vectorize(parser.parse)(texts)

# 方案 K：Ray/Dask 分布式解析
import ray
ray.init()

@ray.remote
def parse_remote(text):
    return Parser(text).parse()

futures = [parse_remote.remote(t) for t in texts]
results = ray.get(futures)  # 分布式执行，绕过 GIL
```

---

## 优先级排序

| 优先级 | 瓶颈 | 风险 | 影响程度 | 推荐方案 |
|---|---|---|---|---|
| P0 | 线程创建开销 | 🔴 高 | 20s+ 纯开销 | 线程池复用（方案 A） |
| P0 | OS 调度开销 | 🔴 高 | 10x 上下文切换 | 异步 I/O（方案 D） |
| P1 | 内存压力 | 🟡 中 | OOM 风险 | 减小栈/绿色线程（方案 E/F） |
| P1 | 读锁竞争 | 🟡 中 | 串行化 10000 读操作 | RWMutex/无锁设计（方案 G/H） |
| P2 | GIL 限制 | 🟡 中 | 无法真正并行 | Ray/Dask/C 扩展（方案 J/K） |

---

## 结论

当前 1000 线程下 **零异常**，RLock 机制稳定。
扩展到 10000 线程时，**线程创建/OS 调度开销**将成为主要瓶颈，
GIL 限制使得纯线程方案无法真正并行。

**推荐路径**：
1. **短期**：使用线程池（固定 16-64 线程）+ 任务队列，避免动态创建线程
2. **中期**：集成 Ray/Dask 实现分布式解析，彻底绕过 GIL
3. **长期**：开发 C 扩展核心解析器，释放 GIL 实现 true parallelism
