# Matha 离线使用指南

## 概述

Matha 是一款自然语言数学编程语言，支持 JIT 编译、自动 Memoization、多语言代码生成等核心功能。**本指南说明如何在无网络环境下完整使用 Matha。**

---

## 一、离线安装包

### 1.1 打包（在有网络机器上执行）

```bash
# 进入 Matha 项目根目录
cd d:\trae

# 完整离线打包（源码 + pip wheel 包）
python scripts/package_offline.py

# 仅打包核心功能（最小包，不含测试和依赖）
python scripts/package_offline.py --core

# 指定输出目录
python scripts/package_offline.py --out ./my_offline_package

# 干运行（仅查看计划，不执行）
python scripts/package_offline.py --dry-run
```

### 1.2 生成的文件

```
offline_package/
├── matha-source-20260831.tar.gz      # Matha 完整源码（~8.5 MB）
├── matha-pip-packages-20260831.tar.gz # pip 依赖 wheel 包（~5.9 MB）
├── offline_requirements.txt          # 离线依赖清单
├── deploy_offline.py                 # 目标机器部署脚本
├── verify_offline.py                 # 环境验证脚本
├── README.md                         # 使用说明
└── checksums.sha256                  # SHA256 校验文件
```

### 1.3 传输到离线机器

将整个 `offline_package/` 目录通过 U 盘、内网共享、SCP 等方式拷贝到目标机器。

---

## 二、离线部署

### 2.1 一键部署

```bash
# 进入离线包目录
cd offline_package

# 完整部署（安装依赖 + 设置项目 + 运行测试）
python deploy_offline.py

# 跳过测试（加快部署）
python deploy_offline.py --skip-tests

# 验证当前环境（不安装）
python deploy_offline.py --check

# 指定 wheel 目录
python deploy_offline.py --wheels /path/to/wheels
```

### 2.2 验证安装

```bash
# 快速验证（仅检查导入）
python scripts/verify_offline.py --quick

# 完整验证（导入 + 功能测试）
python scripts/verify_offline.py

# 详细输出
python scripts/verify_offline.py --verbose

# JSON 格式输出（适合 CI/CD）
python scripts/verify_offline.py --json
```

---

## 三、离线使用

### 3.1 使用 Python 直接调用

```python
import sys
sys.path.insert(0, '/path/to/matha')

# 导入核心模块
from src.compiler.matha_cc import MathaLexer, MathaParser
from src.mir import MIRGenerator
from src.mir_converter import convert

# 编译 Matha 表达式
code = convert("x = sin(3.14) + cos(1.57)", "matha", "c")
print(code)
```

### 3.2 核心功能使用

#### 3.2.1 解释执行

```python
from src.math_driver import MathDriver
driver = MathDriver()
result = driver.run("x = sin(pi)")
print(result)
```

#### 3.2.2 C 代码生成

```python
from src.mir_converter import convert
c_code = convert("x = sin(3.14) + cos(1.57)", "matha", "c")
with open("output.c", "w") as f:
    f.write(c_code)
```

#### 3.2.3 Python 代码生成

```python
from src.mir_converter import convert
py_code = convert("x = sin(3.14)", "matha", "python")
with open("output.py", "w") as f:
    f.write(py_code)
```

#### 3.2.4 多语言代码生成

```python
from src.multi_lang_codegen import MultiLangCodeGen

cg = MultiLangCodeGen()
result = cg.generate("rust", "fib", [("n", "i32")], "fib(n-1) + fib(n-2)")
print(result.code)
```

支持语言：`cpp`, `rust`, `go`, `java`, `python`, `javascript`, `c`, `matha`

#### 3.2.5 自动 Memoization

```python
from src.compiler.memoize import get_memoize_optimizer

opt = get_memoize_optimizer()
# Fibonacci 优化：原始递归 271ms → 迭代优化 0.014ms（19526x 加速）
result = opt.optimize_fibonacci(50)
print(f"Fib(50) = {result}")
```

#### 3.2.6 JIT 编译

```python
from src.compiler.jit import jit_func, get_jit_compiler

# 使用装饰器
@jit_func
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)

print(fib(30))  # 自动缓存优化

# 或使用全局编译器
compiler = get_jit_compiler()
compiled = compiler.compile("fib(n-1) + fib(n-2)")
```

#### 3.2.7 性能 Profiler

```python
from src.profiler import MathaProfiler

profiler = MathaProfiler()

# 上下文管理器模式
with profiler.run("my_function"):
    # 被测试的代码
    result = some_math_operation()

# 获取 Markdown 报告
report = profiler.report("markdown")
print(report)

# 获取 JSON 报告
json_report = profiler.report("json")

# 生成火焰图
profiler.save_flamegraph("flamegraph.html")
```

#### 3.2.8 LSP 语言服务器

```python
from src.lsp import MathaLSP

lsp = MathaLSP()

# 代码补全
completions = lsp.complete("x = sin", position=(0, 6))
for item in completions:
    print(f"  {item.label}")

# 悬停信息
hover = lsp.hover("x = sin(3.14)", position=(0, 8))
print(hover)

# 定义查找
definition = lsp.find_definition("x = sin(3.14)", position=(0, 8))
print(definition)

# 诊断检查
diagnostics = lsp.diagnostics("x = sin(3.14)")
for diag in diagnostics:
    print(f"  {diag.message}")
```

#### 3.2.9 文档生成

```python
from src.doc_gen import DocGenerator

gen = DocGenerator()
docs = gen.generate_all()

# Markdown 文档
with open("api_reference.md", "w") as f:
    f.write(docs["markdown"])

# HTML 文档
with open("api_reference.html", "w") as f:
    f.write(docs["html"])

# JSON 文档
with open("api_reference.json", "w") as f:
    f.write(docs["json"])
```

#### 3.2.10 类型系统

```python
from src.type_system_v2 import TypeChecker

tc = TypeChecker()

# 类型推断
type_info = tc.infer("x = sin(3.14)")
print(type_info)

# 子类型检查
is_subtype = tc.check_subtype("double", "float")
print(is_subtype)
```

#### 3.2.11 CSP 并发

```python
from src.csp_os_thread import CSPRuntime

runtime = CSPRuntime()

# 启动 goroutine
runtime.go(lambda: print("hello from goroutine"))

# Channel 通信
ch = runtime.channel()
ch.send(42)
value = ch.recv()
```

#### 3.2.12 离线存储

```python
from src.offline.sqlite_storage import SQLiteStorage
from src.offline.sync import OfflineSyncManager

# SQLite 存储
storage = SQLiteStorage()
storage.save_history("x = sin(3.14)", result=0.00159)
history = storage.get_history(limit=10)

# 离线同步管理
sync = OfflineSyncManager()
sync.enqueue({"type": "calculation", "data": {...}})
```

---

## 四、离线可用功能清单

### 完全离线可用（无需网络）

| 功能 | 说明 |
|------|------|
| 解释器/编译器 | Lexer → Parser → MIR → 代码生成 |
| JIT 函数级编译 | `@jit_func` 装饰器，自动优化 |
| 自动 Memoization | LRU 缓存 + 尾递归转换 |
| C/Python/Matha 代码生成 | 三语言输出 |
| C++/Rust/Go/Java 代码生成 | 八语言转译 |
| 性能 Profiler | 火焰图 + Markdown/JSON 报告 |
| LSP 语言服务器 | 补全/悬停/定义跳转/诊断 |
| API 文档生成 | Markdown/HTML/JSON 三格式 |
| 包管理器（本地） | `matha install ./local_pkg` |
| 类型系统 | 依赖类型/泛型/子类型/精炼类型 |
| CSP 进程级并发 | OS 线程绕过 Python GIL |
| SQLite 离线存储 | 历史记录/偏好设置/计算缓存 |
| 多语言交叉验证 | 静态验证引擎 |
| 符号兼容 | `SymbolCompat` 简化 `>>` 语义 |

### 需要网络的功能（离线不可用）

| 功能 | 离线行为 |
|------|----------|
| 远程包安装/搜索 | 抛出 `URLError`，本地包仍可安装 |
| LLM 意图解析 | 自动降级到正则解析 |
| Growth Engine 网络搜索 | 超时后跳过，继续本地逻辑 |
| HAL 网络设备操作 | 连接失败，返回模拟数据 |
| 移动端 WebSocket 协作 | 连接失败，CRDT 冲突本地解决 |
| Pyodide WASM 运行时 | CDN 加载失败 |

---

## 五、常见问题

### Q1: 离线环境下 `matha` 命令不可用？

```bash
# 确保在项目根目录运行
cd /path/to/matha

# 或直接使用 Python 运行
python -m src.repl
```

### Q2: 离线环境下无法安装依赖？

```bash
# 使用离线 wheel 包安装
pip install --no-index --find-links=./wheels -r offline_requirements.txt

# 或手动安装核心依赖
pip install sympy numpy scipy numba
```

### Q3: 离线环境下 LLM 功能不可用？

Matha 的 LLM 意图解析会自动降级到正则解析，不影响核心功能使用。

### Q4: 如何验证离线环境完整性？

```bash
# 运行完整验证（39 项检查）
python scripts/verify_offline.py

# 或 JSON 格式输出
python scripts/verify_offline.py --json
```

### Q5: 如何打包完整的离线环境？

```bash
# 在有网络机器上打包
python scripts/package_offline.py --out ./matha-offline-v1.0

# 输出目录包含：
# - matha-source-*.tar.gz  (源码)
# - matha-pip-packages-*.tar.gz  (pip wheel)
# - offline_requirements.txt  (依赖清单)
# - deploy_offline.py  (部署脚本)
# - verify_offline.py  (验证脚本)
# - README.md  (使用说明)
```

---

## 六、快速开始

```bash
# 1. 部署
python deploy_offline.py

# 2. 验证
python scripts/verify_offline.py

# 3. 运行示例
python -c "
from src.mir_converter import convert
print(convert('x = sin(pi)', 'matha', 'c'))
"

# 4. 运行测试
python -m unittest discover -s tests -p 'test_*.py'
```

---

## 七、版本信息

- Matha 版本：v4.4
- Python 要求：>= 3.10
- 离线包生成时间：2026-08-31
- 测试覆盖：128 项单元测试全部通过
