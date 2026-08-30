# Matha 离线使用完整指南

## 概述

Matha 是一款自然语言数学编程语言，支持 JIT 编译、自动 Memoization、多语言代码生成等核心功能。**本指南说明如何在无网络环境下完整使用 Matha，包括独立可执行文件和 Python 包两种部署方式。**

---

## 一、快速开始（5 分钟）

### 方式 1：独立可执行文件（推荐，最简洁）

```bash
# 1. 在有网络机器上构建
pip install pyinstaller
python scripts/build_exe.py

# 2. 拷贝 dist/ 目录到离线机器
# 3. 直接运行
./matha                    # 启动 REPL
./matha eval "sin(pi)"     # 计算表达式
./matha-cc compile demo.matha -o c  # 编译到 C
```

### 方式 2：Python 包部署

```bash
# 1. 打包离线环境
python scripts/package_offline.py

# 2. 拷贝 offline_package/ 到离线机器
# 3. 运行部署
python deploy_offline.py

# 4. 验证
python scripts/verify_offline.py
```

---

## 二、离线可执行文件详解

### 2.1 构建可执行文件

**前置条件：** 在有网络的开发机上执行

```bash
# 安装 PyInstaller
pip install pyinstaller

# 方式 A: 使用脚本（推荐）
python scripts/build_exe.py              # 构建全部
python scripts/build_exe.py --matha      # 仅构建 matha REPL
python scripts/build_exe.py --matha-cc   # 仅构建 matha-cc
python scripts/build_exe.py --onefile    # 单文件模式

# 方式 B: 直接 PyInstaller
pyinstaller --onefile --console matha.spec
pyinstaller --onefile --console matha-cc.spec

# 方式 C: Windows 批处理
scripts\build.bat

# 方式 D: Linux/macOS
chmod +x scripts/build.sh && ./scripts/build.sh
```

### 2.2 构建产物

```
dist/
├── matha/
│   └── matha.exe          # Matha REPL 独立可执行文件（~50 MB）
└── matha-cc/
    └── matha-cc.exe       # Matha 编译器独立可执行文件（~30 MB）
```

> **说明**：文件大小取决于包含的模块数量。`--onefile` 模式首次启动有解包延迟。

### 2.3 使用独立可执行文件

#### matha（REPL 入口）
```bash
# 启动交互式 REPL
matha

# 计算表达式（输出 Python 代码）
matha eval "sin(3.14)"
matha eval "x = sin(pi) + cos(0)"

# 运行 .matha 源文件
matha run demo.matha

# 显示版本
matha --version

# 显示帮助
matha help

# 调试模式
matha --debug
```

#### matha-cc（编译器入口）
```bash
# 编译 Matha 源码
matha-cc compile demo.matha -o output.c

# 编译并运行
matha-cc run demo.matha

# 生成 LLVM IR
matha-cc llvm demo.matha -o output.ll

# 优化编译
matha-cc optimize demo.matha -O2

# 显示工具链信息
matha-cc info

# 运行编译器测试
matha-cc test
```

---

## 三、Python 包部署详解

### 3.1 打包离线包

在有网络的机器上执行：

```bash
# 进入 Matha 项目根目录
cd d:\trae

# 完整离线打包（源码 + pip wheel 包）
python scripts/package_offline.py

# 仅打包核心功能（最小包，不含测试和依赖）
python scripts/package_offline.py --core

# 指定输出目录
python scripts/package_offline.py --out ./my_offline_package

# 排除测试文件
python scripts/package_offline.py --no-tests

# 排除 __pycache__
python scripts/package_offline.py --no-pycache

# 不下载 wheel 包
python scripts/package_offline.py --no-wheels

# 干运行（仅查看计划）
python scripts/package_offline.py --dry-run
```

### 3.2 生成的文件

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

### 3.3 部署到离线机器

```bash
# 1. 将 offline_package/ 目录拷贝到离线机器（U 盘、内网等）

# 2. 进入离线包目录
cd offline_package

# 3. 运行部署
python deploy_offline.py

# 4. 验证部署
python deploy_offline.py --check

# 5. 运行验证
python scripts/verify_offline.py
```

### 3.4 离线验证结果

```
总计: 39/39 通过 [PASS]
  core: 10/10       optimization: 6/6       tools: 9/9
  multi_lang: 4/4   concurrency: 3/3        type_system: 3/3   offline: 4/4
```

---

## 四、离线功能清单

### 4.1 完全离线可用（无需网络）

| 功能 | 说明 |
|------|------|
| 解释器/编译器 | Lexer → Parser → MIR → 代码生成 |
| JIT 函数级编译 | `@jit_func` 装饰器，自动优化 |
| 自动 Memoization | LRU 缓存 + 尾递归转换（Fibonacci 19526x 加速） |
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

### 4.2 需要网络的功能（离线不可用）

| 功能 | 离线行为 |
|------|----------|
| 远程包安装/搜索 | 抛出 `URLError`，本地包仍可安装 |
| LLM 意图解析 | 自动降级到正则解析 |
| Growth Engine 网络搜索 | 超时后跳过，继续本地逻辑 |
| HAL 网络设备操作 | 连接失败，返回模拟数据 |
| 移动端 WebSocket 协作 | 连接失败，CRDT 冲突本地解决 |
| Pyodide WASM 运行时 | CDN 加载失败 |

---

## 五、核心 API 使用

### 5.1 代码生成

```python
from src.mir_converter import convert

# 编译到 C
c_code = convert("x = sin(3.14) + cos(1.57)", "matha", "c")

# 编译到 Python
py_code = convert("x = sin(3.14)", "matha", "python")

# 编译到 Rust
rust_code = convert("x = sin(3.14)", "matha", "rust")

# 编译到 Go
go_code = convert("x = sin(3.14)", "matha", "go")
```

### 5.2 自动 Memoization

```python
from src.compiler.memoize import get_memoize_optimizer

opt = get_memoize_optimizer()

# Fibonacci 优化：原始递归 271ms → 迭代优化 0.014ms（19526x 加速）
result = opt.optimize_fibonacci(50)
print(f"Fib(50) = {result}")  # 12586269025
```

### 5.3 JIT 编译

```python
from src.compiler.jit import jit_func, get_jit_compiler

# 使用装饰器
@jit_func
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)

print(fib(30))  # 自动缓存优化

# 或使用全局编译器
compiler = get_jit_compiler()
```

### 5.4 性能 Profiler

```python
from src.profiler import MathaProfiler

profiler = MathaProfiler()

# 上下文管理器模式
with profiler.run("my_function"):
    result = some_math_operation()

# 获取报告
report = profiler.report("markdown")
json_report = profiler.report("json")

# 生成火焰图
profiler.save_flamegraph("flamegraph.html")
```

### 5.5 LSP 语言服务器

```python
from src.lsp import MathaLSP

lsp = MathaLSP()

# 代码补全
completions = lsp.complete("x = sin", position=(0, 6))

# 悬停信息
hover = lsp.hover("x = sin(3.14)", position=(0, 8))

# 定义查找
definition = lsp.find_definition("x = sin(3.14)", position=(0, 8))

# 诊断检查
diagnostics = lsp.diagnostics("x = sin(3.14)")
```

### 5.6 多语言代码生成

```python
from src.multi_lang_codegen import MultiLangCodeGen

cg = MultiLangCodeGen()
result = cg.generate("rust", "fib", [("n", "i32")], "fib(n-1) + fib(n-2)")
print(result.code)
```

支持语言：`cpp`, `rust`, `go`, `java`, `python`, `javascript`, `c`, `matha`

### 5.7 类型系统

```python
from src.type_system_v2 import TypeChecker

tc = TypeChecker()

# 类型推断
type_info = tc.infer("x = sin(3.14)")

# 子类型检查
is_subtype = tc.check_subtype("double", "float")
```

### 5.8 CSP 并发

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

### 5.9 离线存储

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

## 六、命令行使用

### 6.1 matha 命令

```bash
# 启动 REPL
matha

# 计算表达式
matha eval "sin(pi)"
matha eval "x = 3.14; y = cos(x)"

# 运行源文件
matha run demo.matha

# 显示版本
matha --version

# 显示帮助
matha help

# 调试模式
matha --debug
```

### 6.2 matha-cc 命令

```bash
# 编译到 C
matha-cc compile demo.matha -o output.c

# 编译到 Python
matha-cc compile demo.matha -o output.py

# 编译并运行
matha-cc run demo.matha

# 生成 LLVM IR
matha-cc llvm demo.matha -o output.ll

# 优化编译
matha-cc optimize demo.matha -O2

# 显示工具链信息
matha-cc info

# 运行编译器测试
matha-cc test
```

---

## 七、测试验证

### 7.1 验证离线环境

```bash
# 快速验证（仅检查导入）
python scripts/verify_offline.py --quick

# 完整验证（导入 + 功能测试）
python scripts/verify_offline.py

# 详细输出
python scripts/verify_offline.py --verbose

# JSON 格式输出
python scripts/verify_offline.py --json
```

### 7.2 运行单元测试

```bash
# 运行全部测试
python -m unittest discover -s tests -p "test_*.py"

# 运行指定测试套件
python -m unittest tests.test_code_generator
python -m unittest tests.test_core_defects_fixed
python -m unittest tests.test_multilang_enhancement

# 运行核心测试（推荐）
python -m unittest tests.test_code_generator tests.test_core_defects_fixed tests.test_multilang_enhancement
```

---

## 八、常见问题

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

### Q6: 独立可执行文件和 Python 包部署有什么区别？
| 特性 | 独立可执行文件 | Python 包部署 |
|------|-------------|-------------|
| 安装 Python | ❌ 不需要 | ✅ 需要 Python >= 3.10 |
| 文件大小 | ~50 MB | ~14 MB |
| 启动速度 | 首次慢（解包） | 正常 |
| 适用场景 | 无 Python 环境 | 已有 Python 环境 |
| 更新方式 | 重新打包 | pip install |

---

## 九、版本信息

| 项目 | 值 |
|------|-----|
| Matha 版本 | v4.4 |
| Python 要求 | >= 3.10 |
| 离线包生成时间 | 2026-08-31 |
| 单元测试覆盖 | 128 项全部通过 |
| 离线验证 | 39 项全部通过 |
| 许可证 | BSD-2-Clause |

---

## 十、文件清单

| 文件 | 说明 |
|------|------|
| `scripts/package_offline.py` | 离线打包脚本 |
| `scripts/deploy_offline.py` | 离线部署脚本 |
| `scripts/verify_offline.py` | 离线验证脚本 |
| `scripts/build_exe.py` | 可执行文件打包脚本 |
| `scripts/build.bat` | Windows 构建脚本 |
| `scripts/build.sh` | Linux/macOS 构建脚本 |
| `matha.spec` | PyInstaller 配置（matha） |
| `matha-cc.spec` | PyInstaller 配置（matha-cc） |
| `offline_package/` | 离线包输出目录 |
| `dist/` | 可执行文件输出目录 |
| `docs/offline_usage_guide.md` | 离线使用指南（本文档） |
| `docs/BUILD_GUIDE.md` | 构建指南 |
