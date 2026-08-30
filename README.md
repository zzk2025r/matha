# Matha

自举式领域专用语言与独立可执行编程语言系统。

## 系统状态

- **版本：** v4.4
- **领域模块：** 54
- **测试用例：** 128
- **通过率：** 100%
- **部署方式：** 独立可执行文件 / Python 包 / 离线部署

---

## 快速开始

### 方式 1：独立可执行文件（推荐，无需安装 Python）

```bash
# 下载 matha.exe 和 matha-cc.exe
# 直接运行，无需任何环境

# 启动交互式 REPL
matha

# 计算表达式
matha eval "sin(3.14)"

# 运行 Matha 源文件
matha run demo.matha

# 编译到 C
matha-cc compile demo.matha -o output.c

# 编译到 Python
matha-cc compile demo.matha -o output.py
```

### 方式 2：Python 包安装

```bash
# 安装依赖
pip install sympy numpy scipy numba

# 安装 Matha
pip install -e .

# 使用
matha                          # 启动 REPL
matha eval "sin(pi)"           # 计算表达式
matha run demo.matha           # 运行源文件
matha-cc compile demo.matha    # 编译
```

### 方式 3：离线部署（无网络环境）

```bash
# 在有网络机器上打包
python scripts/package_offline.py

# 拷贝到离线机器
# 运行部署
python deploy_offline.py

# 验证
python scripts/verify_offline.py
```

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **JIT 编译** | 函数级即时编译 + 自动 Memoization |
| **自动缓存优化** | LRU 缓存 + 尾递归转换（Fibonacci 19526x 加速） |
| **多语言代码生成** | C/Python/Rust/Go/Java/C++/JS/Matha 八语言转译 |
| **性能 Profiler** | cProfile 集成 + 火焰图 + Markdown/JSON 报告 |
| **LSP 语言服务器** | 补全/悬停/定义跳转/诊断 |
| **类型系统** | 依赖类型/泛型/子类型/精炼类型 |
| **CSP 并发** | 进程级并发绕过 Python GIL |
| **离线存储** | SQLite 持久化 + 同步管理 |
| **54 领域模块** | 物理/工程/AI/金融/生物/化学等全覆盖 |

---

## 命令行工具

### matha（REPL 入口）
```bash
matha                          # 启动交互式 REPL
matha eval "sin(pi)"           # 计算单行表达式
matha run demo.matha           # 运行源文件
matha --version                # 显示版本
matha --debug                  # 调试模式
```

### matha-cc（编译器工具链）
```bash
matha-cc compile demo.matha -o c        # 编译到 C
matha-cc compile demo.matha -o python   # 编译到 Python
matha-cc run demo.matha                 # 编译并运行
matha-cc llvm demo.matha -o out.ll      # 生成 LLVM IR
matha-cc optimize demo.matha -O2        # 优化编译
matha-cc info                           # 工具链信息
matha-cc test                           # 运行测试
```

---

## 项目结构

```
matha/
├── src/                    # 核心源代码
│   ├── domains/           # 54个领域模块
│   ├── compiler/          # JIT/AOT/LLVM 编译器
│   ├── mir.py             # MIR 中间表示
│   ├── mir_codegen.py     # 代码生成器
│   ├── repl.py            # REPL 入口（含 main() CLI）
│   └── ...
├── tests/                  # 测试套件 (128 项)
├── dist/                   # 可执行文件输出
│   ├── matha-offline/
│   │   └── matha.exe      # 独立可执行文件 (18.5 MB)
│   └── matha-cc-offline/
│       └── matha-cc.exe   # 编译器独立可执行文件
├── offline_package/        # 离线安装包
├── scripts/               # 工具脚本
│   ├── package_offline.py # 离线打包
│   ├── deploy_offline.py  # 离线部署
│   ├── verify_offline.py  # 环境验证
│   ├── build_exe.py       # 可执行文件构建
│   ├── build.bat          # Windows 构建脚本
│   └── build.sh           # Linux/macOS 构建脚本
├── matha.spec             # PyInstaller 配置（matha）
├── matha-cc.spec          # PyInstaller 配置（matha-cc）
├── docs/
│   ├── OFFLINE_GUIDE.md   # 离线使用完整指南
│   └── BUILD_GUIDE.md     # 可执行文件构建指南
└── pyproject.toml         # 包配置
```

---

## 离线可用功能

### ✅ 完全离线可用（无需网络）
- 解释器/编译器（Lexer → Parser → MIR → CodeGen）
- JIT 函数级编译 + 自动 Memoization
- C/Python/Rust/Go/Java/C++/JS/Matha 代码生成
- 性能 Profiler（火焰图 + 报告）
- LSP 语言服务器
- API 文档生成
- 类型系统
- CSP 并发
- SQLite 离线存储
- 所有 54 个领域模块

### ⚠️ 需要网络（离线不可用）
- 远程包安装/搜索
- LLM 意图解析（自动降级到正则）
- Growth Engine 网络搜索
- 移动端 WebSocket 协作
- Pyodide WASM 运行时

---

## 文档

| 文档 | 说明 |
|------|------|
| [离线使用完整指南](docs/OFFLINE_GUIDE.md) | 离线包部署 + 可执行文件使用 |
| [构建指南](docs/BUILD_GUIDE.md) | PyInstaller 独立可执行文件构建 |
| [Matha vs 语言对比](docs/matha_vs_languages_analysis.md) | 多语言对比分析 |
| [性能差距分析](docs/performance_gap_analysis.md) | Matha vs Rust 性能对比 |
| [基准测试报告](docs/benchmark_rust_report.md) | Rust 基准测试报告 |
| [多语言转译技术文档](docs/multilang_translator_technical_doc.md) | 技术实现细节 |

---

## 测试

```bash
# 运行全部测试
python -m unittest discover -s tests -p "test_*.py"

# 验证离线环境
python scripts/verify_offline.py

# 快速验证
python scripts/verify_offline.py --quick
```

**测试结果：** 128/128 通过 ✅ | 离线验证：39/39 通过 ✅

---

## 构建独立可执行文件

```bash
# 安装 PyInstaller
pip install pyinstaller

# 构建 matha REPL
python -m PyInstaller --noconfirm matha.spec

# 构建 matha-cc 编译器
python -m PyInstaller --noconfirm matha-cc.spec

# 或使用脚本
python scripts/build_exe.py
```

生成的独立可执行文件：
- `dist/matha-offline/matha.exe` — Matha REPL（18.5 MB）
- `dist/matha-cc-offline/matha-cc.exe` — 编译器

---

## 版本信息

| 项目 | 值 |
|------|-----|
| 版本 | v4.4 |
| Python 要求 | >= 3.10 |
| 许可证 | BSD-2-Clause |
| GitHub | https://github.com/zzk2025r/matha |
| 独立可执行文件 | ✅ 支持（无需 Python 环境） |
| 离线部署 | ✅ 支持（完整功能离线可用） |
