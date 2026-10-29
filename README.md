# Matha

自举式领域专用语言与独立可执行编程语言系统。

## 系统状态（实测，非自评）

下表每个数字都由 `python scripts/repo_facts.py` 从仓库现场数出来，
`tests/test_doc_facts.py` 会核对文档与代码是否漂移（漂移即红）。

- **版本：** v4.6.0（唯一版本源 [`src/__version__.py`](src/__version__.py)）
- **领域插件：** 82（`src/domains/` 共 84 个 `.py`，其中 `__init__.py` / `registry.py` 不是插件）
- **内核外工具插件：** 14（`src/plugins/`）
- **黄金用例：** 34（`golden_tests/cases/`，vm ↔ interp ↔ native 逐字节）
- **`.matha` 语料：** 158（历史遗留的旧写法已全部改写为合法 Matha，当前 0 个属语法层遗留，见 `docs/ast_vm_gap.md`）
- **测试文件：** 66（`tests/`）
- **核心安装第三方依赖：** 0（`pyproject.toml` `dependencies = []`）
- **通过率：** 见下一节「质量门禁」，唯一数字来自 `make check`
- **已知未达成项：** 如实列在 [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md)

**阶段结论（本轮重构）：** 内核纯净化 + 插件化重构完成 —— 核心安装零第三方依赖
（`dependencies = []`，sympy/numpy 已降为 `optional-dependencies.accelerated`），
第三方重后端只在插件函数体内按需 `import`（样板：`src/domains/symbolic_calculus.py`，
配套命名卫生门禁：插件不得导出裸单字母符号、也不得与 `.matha` 顶层声明同名）；
核心测试 100% 通过（唯一口径见下方「质量门禁」，数字随用例增减以 `make check` 实时输出为准）。

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
# 核心零依赖：不装任何第三方包也能跑主执行链
pip install -e .

# 可选扩展（按需，不影响内核）
pip install -e ".[accelerated]"   # sympy 兼容后端
pip install -e ".[performance]"   # numpy/scipy/numba 数值后端

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
| **82 领域插件** | 物理/工程/AI/金融/生物/化学等；按需显式加载，不加载零 import 成本 |

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
│   ├── domains/           # 82 个领域插件（+ 包初始化/注册表）
│   ├── kernel/            # L1 纯净内核（纯标准库）
│   ├── plugins/           # 内核外工具插件
│   ├── compiler/          # JIT/AOT 编译器（LLVM 子过进程属可选插件）
│   ├── mbc/               # 主执行链：compiler → vm →（可选）native
│   ├── repl.py            # REPL 入口
│   └── ...
├── tests/                  # 测试套件（61 个文件）
├── golden_tests/           # 34 例逐字节黄金用例（vm/interp/native）
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
- 所有 82 个领域插件

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
| [权威文档索引](docs/index.md) | 只有 10 份现状文档，其余已归档 |
| [架构现状](docs/ARCHITECTURE.md) | 主执行链、内核白名单、插件层 |
| [依赖基线](docs/DEP_BASELINE.md) | `scripts/dep_audit.py` 产出 |
| [AST × VM 覆盖矩阵](docs/ast_vm_gap.md) | 删转译路径的前置件 + 语言口径 |
| [符号能力对照](docs/symbolic_parity.md) | 内核纯实现 vs sympy |
| [Matha 符号标准库](docs/matha_stdlib_symbolic.md) | 阶段 4：`.matha` 重写 + 逐位对拍 |
| [已知问题](docs/KNOWN_ISSUES.md) | 未达成项如实列表 |
| [离线使用指南](docs/OFFLINE_GUIDE.md) | 离线包部署 + 可执行文件 |
| [构建指南](docs/BUILD_GUIDE.md) | PyInstaller 独立可执行文件 |
| [语言规格](docs/spec/) | 词法/语法/语义/EBNF（00–21 共 22 份） |

---

## 质量门禁

对外只有一个口径、**一个通过率数字**：

```bash
make check          # = python scripts/check.py（含 vm↔native 机器码对拍）
make check-lite     # 同上，不跑需要 nasm/link 的机器码对拍
```

它把六项串成一条链：`tests/` + `kernel_purity` + `ast_vm_gap` +
`golden`（逐字节）+ `dep_audit` + `native_parity`。口径纪律：跑不成
一律记失败，不记跳过；跳过项从分母剔除但显式打印台数，绝不把「没跑」
算成「跑通」。

```bash
# 离线环境验证
python scripts/verify_offline.py
```

**实测结果（最近一次 `make check`）：** 通过 3957 / 计入 3957，失败 0，**通过率 100.00%**
（含 `kernel_purity` 14 / `ast_vm_gap` 11 / `golden` 18 逐字节 / `dep_audit` 违规 0 条；
`native_parity` 17 过 + 1 例不计入分母（`18_domain_lazy_load`：native 不承载领域插件符号）；
原 2 个类型校验静默错值缺口 NI-001/NI-002 已修复（未定义名与字符串参与 `-` 均抛可捕获异常），
详见 `docs/KNOWN_ISSUES.md`。本轮全量跑零 DeprecationWarning。旧快照的绝对数字
会随用例增减漂移，以 `make check` 实时输出为准。）

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
| 版本 | v4.6.0（单一来源 `src/__version__.py`） |
| 内核协议 | 1（`KERNEL_PROTOCOL`，与插件契约同步演进） |
| Python 要求 | >= 3.10 |
| 核心第三方依赖 | 0 |
| 许可证 | BSD-2-Clause |
| GitHub | https://github.com/zzk2025r/matha |
| 独立可执行文件 | ✅ 支持（无需 Python 环境） |
| 领域插件 | 82（按需加载） |

历史文档（118 份一次性报告）已归档到 [`docs/history/`](docs/history/)，
不再作为现状依据；权威文档只有一张索引页：[`docs/index.md`](docs/index.md)。

---

## 社区

我们欢迎所有贡献者！

### 参与方式

- **报告问题** - [GitHub Issues](https://github.com/zzk2025r/matha/issues)
- **提交 PR** - Fork 并创建 Pull Request
- **文档改进** - 修复错别字、添加示例、翻译
- **领域模块** - 添加新的领域模块
- **测试贡献** - 添加测试用例

### 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

### 行为准则

详见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

---

*版本：v4.6.0（取自 `src/__version__.py`）*
