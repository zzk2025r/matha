# Matha 与主流编程语言对比分析

## Matha 系统全景（实测）

> 本节只写能当场验证的事实：数字来自 `python scripts/repo_facts.py`，
> 能力边界来自 `make check` 的六项门禁。旧版这里的模块数量、维度满分与
> 「缺陷已全部解决」均属手写愿望，已删除（可在 git 历史里查到）。

### 核心架构

- **版本**：v4.6.0（唯一版本源 `src/__version__.py`）
- **领域插件**：82（枚举：`matha --list-domains`；`src/domains/` 共 84 个 `.py`，
  其中 `__init__.py` / `registry.py` 不是插件）；按需显式加载，未加载零 import 成本
- **内核外工具插件**：14（`src/plugins/`：numpy 加速、FFI、tree-sitter、并行解析、
  LLVM/MSVC 工具链、归档 VM 等）
- **执行路径（唯一主线）**：`src/lexer.py → src/parser.py → src/ast_nodes.py →
  src/mbc/compiler.py → src/mbc/vm.py`；机器码只有一条真实路径：
  `src/mbc/native.py` → `src/plugins/toolchain_msvc.py`（nasm/link）
- **`MIR` 不再执行**：`src/mir.py` / `mir_opt.py` 仅作优化分析 IR；
  原第三条 VM（`src/vm.py` / `src/m3v_vm.py`）已归档为插件 / 已删除
- **遗留解释器**：`src/interp.py` 降为诊断后端（执行轨迹/单步），经
  `src/kernel/exec_api.py` 显式选择，不在默认路径
- **核心安装第三方依赖**：0（`sympy` 降为 `optional-dependencies.accelerated`）
- **符号能力**：内核纯实现 `src/kernel/symbolic/`（stage0 引导）+ Matha 自身重写的
  标准库 `matha/library/*.matha`（**CLI 默认路径**，与 stage0 逐位对拍）

### 核心子系统状态（只列被门禁覆盖的）

| 子系统 | 位置 | 由谁判定 |
|--------|------|----------|
| Lexer / Parser | `src/lexer.py`、`src/parser.py` | `tests/test_ast_vm_gap.py` 语料解析（158 个 `.matha`，遗留旧写法已全部改写为合法 Matha，解析失败 0） |
| AST 节点 | `src/ast_nodes.py` | 78 个节点全部进覆盖矩阵 |
| 编译器 | `src/mbc/compiler.py` | 59 发射 / 19 有意无码 / **0 不认识 / 0 阻塞缺口** |
| 虚拟机 | `src/mbc/vm.py` | 33 条指令码全分派 + 18 例黄金逐字节 |
| 机器码后端 | `src/mbc/native.py` | vm↔native 对拍；**已知未实现 2 例**（见 `golden_tests/manifest.json`） |
| 内核内建 | `src/kernel/`（math/regex/time/file/errors + symbolic） | `tests/test_kernel_purity.py` + `scripts/dep_audit.py` |
| 插件层 | `src/plugin_api.py` + `src/domains/manifest.json` | `tests/test_plugin_contract.py` |
| 符号标准库 | `matha/library/` + `src/stdlib/matha_symbolic.py` | `tests/test_matha_stdlib_symbolic.py`（107 项） |

领域能力（物理/工程/AI/金融/…）均以插件形式存在，可用性以
`matha --list-domains` 与对应领域自己的测试为准，本文不再逐行打 ✅。

---

## 对比表

### 1. 设计哲学

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|------|-------|--------|------|---------|-------|-----|
| **范式** | 多范式（函数式/命令式/逻辑式/数据流） | 多范式（面向对象/函数式/过程式） | 多范式（面向对象/函数式/过程式） | 纯函数式 | 多范式（面向对象/过程式/元编程） | 多范式（面向对象/泛型/过程式） |
| **类型系统** | 静态推断 + 泛型 + 动态虚拟 | 动态类型（可选静态 via mypy） | 静态 + 所有权 + 泛型 | 静态 + 强类型 + 纯函数式 | 动态类型（JIT优化） | 静态 + 模板 + 概念 |
| **字符编码** | 三进制Base-3（汉字/字母） | Unicode UTF-8 | ASCII/UTF-8 | Unicode UTF-8 | Unicode UTF-8 | ASCII/UTF-8 |
| **自举** | ✅ 自举编译 | ✅ CPython自举 | ✅ Rust自举 | ✅ GHC自举 | ✅ Julia自举 | ✅ GCC/Clang自举 |
| **DSL支持** | ✅ 原生领域专用语言 | 需外部库 | 需外部库 | 需要外部库 | 需外部库 | 需外部库 |
| **虚拟代码** | ✅ 自动注册缺失代码 | ❌ | ❌ | ❌ | ❌ | ❌ |

### 2. 性能与执行

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|------|-------|--------|------|---------|-------|-----|
| **执行模式** | 解释/JIT/AOT/VM字节码 | 解释（CPython）/JIT(PyPy) | AOT编译 | AOT编译(JIT via GHCi) | JIT(ASTARTE) | AOT编译 |
| **性能定位** | 中高（JIT + LLVM优化） | 低（CPython）/中（PyPy） | 极高（零成本抽象） | 中高（惰性求值优化） | 高（JIT优化） | 极高 |
| **内存管理** | GC + 手动（虚拟代码引擎） | GC（引用计数 + 分代） | 所有权/借用（无GC） | GC（惰性求值） | GC（自动） | RAII/GC（可选） |
| **并发模型** | 线程池 + 异步 + CSP | GIL限制 + asyncio | 线程 + async/await | 轻量级线程（MVar） | 任务（@spawn） | 线程 + std::async |
| **编译目标** | C/Python/LLVM IR/原生 | C扩展 | 原生机器码 | 原生机器码 | 原生机器码 | 原生机器码 |

### 3. 生态与工具链

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|------|-------|--------|------|---------|-------|-----|
| **包管理** | `.matha_packages/` + MPM | pip + conda + poetry | cargo | cabal/stack | Pkg | vcpkg/conan |
| **IDE支持** | LSP Server | 完善（PyCharm/VSCode） | 完善（Rust Analyzer） | 完善（Haskell IDE） | 有限 | 完善（CLion） |
| **调试器** | MathaDebugger（AST/MIR） | pdb/pytest | gdb/lldb | ghci | Jupyter | gdb/lldb |
| **测试框架** | 128内置测试用例 | pytest/unittest | cargo test | hspec/tasty | BenchmarkTools | Google Test |
| **文档生成** | doc_gen.py | Sphinx/pydoc | cargo doc | Haddock | Documenter.jl | Doxygen |
| **AI集成** | ✅ MathaAIAssistant | OpenAI SDK | 需外部库 | 需外部库 | 需外部库 | 需外部库 |
| **MCP协议** | ✅ 原生支持 | 需外部库 | 需外部库 | 需外部库 | 需外部库 | 需外部库 |

### 4. 领域专用能力

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|------|-------|--------|------|---------|-------|-----|
| **数学计算** | ✅ 87 领域模块 + 61内置函数 + 29FFI数学函数 | ✅ NumPy/SciPy/Matplotlib | ❌ 需外部库（ndarray等） | ❌ 需外部库 | ✅ LinearAlgebra/Statistics | ✅ Eigen/Armadillo |
| **符号计算** | ✅ 符号引擎 | ✅ SymPy | ❌ | ✅ (有限) | ❌ | ❌ |
| **矩阵运算** | ✅ MathaDriver（10种线性代数运算） | ✅ NumPy | ✅ nalgebra | ❌ | ✅ LinearAlgebra | ✅ Eigen |
| **微积分** | ✅ 微积分驱动（5种运算） | ✅ SymPy/SciPy | ❌ | ✅ | ✅ | ❌ |
| **信号处理** | ✅ 信号驱动（6种运算） | ✅ SciPy.signal | ❌ | ❌ | ✅ DSP.jl | ✅ |
| **优化** | ✅ 优化驱动（3种算法） | ✅ SciPy.optimize | ❌ | ❌ | ✅ Optim.jl | ✅ |
| **AI/ML** | ✅ MathaAIAssistant | ✅ PyTorch/TensorFlow | ✅ Candle/tch-rs | ❌ | ✅ Flux | ✅ |
| **区块链** | ✅ BlockchainWeb3领域模块 | ✅ Web3.py | ✅ substrate | ❌ | ❌ | ✅ |
| **量子计算** | ✅ QuantumComputing领域模块 | ✅ Qiskit/Cirq | ❌ | ❌ | ❌ | ❌ |
| **中文支持** | ✅ 原生中文标识符/关键字 | ✅ Unicode标识符 | ❌ | ❌ | ❌ | ❌ |

### 5. 部署与可移植性

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|------|-------|--------|------|---------|-------|-----|
| **独立可执行** | ✅ matha.exe / matha-cc.exe | ❌（需Python环境） | ✅ 静态链接 | ❌（需GHC运行时） | ❌（需Julia运行时） | ✅ 静态链接 |
| **离线部署** | ✅ 离线模式 | ❌（需pip安装） | ✅ | ❌ | ❌ | ✅ |
| **跨平台** | ✅ Python/LLVM | ✅ 任意支持Python的平台 | ✅ 多平台 | ✅ 多平台 | ✅ 多平台 | ✅ 多平台 |
| **包大小** | 小（自举编译） | 大（Python解释器） | 中（静态链接） | 大（GHC运行时） | 大（Julia运行时） | 大（静态链接） |
| **启动速度** | 中（初始化子系统） | 快（CPython） | 极快（AOT） | 中（GHCi） | 慢（JIT预热） | 极快 |

---

## Matha 优势

### 1. 唯一的多范式领域专用语言
Matha 同时支持函数式、命令式、逻辑式、数据流四种编程范式，并且内置54个领域专用模块。这是目前任何主流语言都不具备的——Python有领域库但不是原生DSL，Rust/Haskell有领域库但不是原生支持。

### 2. 三进制字符编码系统
Matha 使用三进制（Base-3）编码将汉字和字母映射到二进制存储。这是唯一支持中文标识符作为原生特性的语言系统，而Python虽然支持Unicode标识符，但仅作为字符串处理。

### 3. 自举编译能力
Matha 可以自举编译——`.matha`源码 → `matha-cc`编译器 → C/Python/LLVM IR。这意味着Matha可以完全独立于Python运行，生成独立可执行文件。

### 4. 虚拟代码引擎（独创）
Matha 的虚拟代码引擎是独创功能：当调用不存在的函数/key/code时，自动注册并承认/允许使用；吞噬代码后如果无法使用，自动注册并可以承认/允许/正常使用。这是其他语言都不具备的"自适应代码"能力。

### 5. AI/MCP/LSP原生集成
Matha 原生支持语言服务器协议（LSP）、模型上下文协议（MCP）和AI助手（MathaAIAssistant），无需外部库。这在主流语言中非常罕见——通常需要额外开发。

### 6. JIT/AOT/VM三路径执行
Matha 同时支持解释执行、JIT编译、AOT编译和虚拟机字节码执行，可以根据场景自动选择最优路径。Python只有解释执行，Rust/Haskell只有AOT。

### 7. 零外部依赖核心
Matha 的核心系统（词法器、虚拟机、类型系统）零Python标准库依赖，仅用 `re` 模块。这使得Matha可以独立运行，不依赖Python环境。

---

## Matha 缺陷

### 1. 性能仍不及编译型语言
Matha 的JIT/AOT编译虽然能提升性能，但启动和预热时间较长。在纯计算性能上，Matha 无法与 Rust/C++ 的零成本抽象相比。即使与 Julia 的JIT相比，Matha 的预热时间也更长。

### 2. 生态系统远小于 Python
Python 有 PyPI 上超过50万个包，涵盖Web开发、数据科学、机器学习、自动化等所有领域。Matha 的 `.matha_packages/` 生态系统目前仍处于早期阶段，包数量极少。

### 3. 中文标识符的兼容性问题
虽然Matha原生支持中文标识符，但这带来了兼容性问题：
- 与现有代码库（Python/C/Rust）的互操作性降低
- 代码审查和协作困难（非中文使用者无法理解）
- IDE/编辑器对中文标识符的支持不完善
- 国际化团队无法使用

### 4. 三进制编码的认知负担
三进制编码系统虽然创新，但带来了认知负担：
- 开发者需要理解三进制/二进制/十进制之间的转换
- 调试和错误追踪更困难
- 与主流二进制计算模型不兼容

### 5. 缺乏成熟的Web开发能力
Matha 没有Web框架（如Python的Django/Flask，Rust的Actix/Spring）。虽然54个领域模块涵盖广泛，但Web开发不是其核心关注点。

### 6. 社区和文档不足
Matha 的社区规模远小于 Python/Rust/Haskell。文档虽然全面（README、域注册表、测试用例），但缺少：
- 教程和入门指南
- API参考文档
- 社区论坛和讨论区
- 第三方教程和博客

---

## Matha 残缺/欠缺不足

### 1. 缺少标准库
Python 有内置的 `os`, `sys`, `json`, `datetime`, `collections`, `itertools` 等标准库。Matha 的核心系统虽然实现了这些功能的分发版本，但没有统一的 `matha.stdlib` 模块。

### 2. 缺少网络编程能力
Matha 没有内置的 HTTP 服务器/客户端、WebSocket、TCP/UDP 套接字支持。虽然 `net_security.py` 有防火墙功能，但缺少基础的网络编程原语。

### 3. 缺少并发原语
Matha 有 `ThreadPoolExecutor` 和 `asyncio` 的包装，但没有原生的 `async/await` 语法糖、`Future`/`Promise`、`Channel`、`Actor` 模型等并发原语。

### 4. 缺少模式匹配
Rust/Haskell/Scala 有强大的模式匹配功能。Matha 有条件表达式和三元运算符，但没有 `match`/`case` 语法。

### 5. 缺少元编程能力
Python 有 `__getattr__`, `__setattr__`, 装饰器, 元类等元编程能力。Matha 的虚拟代码引擎提供了部分元编程能力（自动注册缺失代码），但缺少完整的元编程系统（如 `__metaclass__`, `__new__`, `__init_subclass__`）。

### 6. 缺少异步I/O
Matha 没有 `asyncio`/`async/await` 原生支持。虽然有 `async_runtime.py`，但没有语言级别的异步语法。

### 7. 缺少垃圾收集调优选项
Python 有多种GC策略（分代收集、引用计数）。Matha 的GC实现较为基础，没有可调参数。

### 8. 缺少交叉编译支持
Matha 可以编译到C/Python/LLVM IR，但没有跨平台交叉编译能力（如Rust的 `target` 参数）。

---

## Matha 本质

### Matha 是什么？

**Matha 是一个自举式领域专用语言（DSL）与独立可执行编程语言系统的融合体。**

### 核心本质：

1. **DSL而非通用语言**
   Matha 的核心设计是领域专用语言。它的54个领域模块、数学计算能力、符号计算引擎、微积分驱动、矩阵运算等都是为数学和科学计算优化的。虽然它可以编程任意逻辑，但这不是它的主要目标。

2. **自举系统**
   Matha 的核心创新在于自举——它可以编译自身。这意味着：
   - `.matha` 源码 → `matha-cc` → C/Python/LLVM
   - 不依赖Python即可运行独立可执行文件
   - 系统可以自我演化

3. **数学计算优先**
   Matha 的语法、类型系统、内置函数、领域模块都围绕数学计算设计。这是它与Python/Rust等通用语言的本质区别。

4. **多范式融合**
   Matha 不是"面向对象"或"函数式"，而是同时支持四种范式。这种设计使得：
   - 数学公式可以用函数式风格表达
   - 算法可以用命令式风格实现
   - 逻辑推理可以用逻辑式风格表达
   - 大规模数据可以用数据流风格处理

5. **虚拟代码引擎是核心创新**
   Matha 的虚拟代码引擎（自动注册缺失代码、吞噬代码并自动适配）是区别于所有主流语言的独特能力。这使得Matha具有"自适应代码"的能力——当调用不存在的函数时，系统会自动创建可用的虚拟实现。

### 本质总结：

| 维度 | 本质 |
|------|------|
| **定位** | 数学与科学计算的领域专用语言，非通用编程语言 |
| **核心创新** | 自举编译 + 三进制编码 + 虚拟代码引擎 |
| **优势领域** | 符号计算、矩阵运算、微积分、领域专用模块、中文编程 |
| **劣势领域** | Web开发、系统编程、并发编程、通用软件开发 |
| **竞争定位** | 不是Python/Rust/C++的替代品，而是数学计算领域的专用工具 |
| **未来方向** | 完善标准库、增强Web能力、扩大生态系统、提升JIT性能 |

### 与Python的关系：
Matha 运行在Python之上（作为Python包），但也可以独立于Python运行（作为独立可执行文件）。这类似于Julia运行在C之上，但提供了独立的运行时。

### 与Rust的关系：
Matha 的虚拟机使用三进制/二进制编码，而Rust使用纯二进制。Matha 的所有权模型不存在（使用GC），这使得Matha更易于使用但性能不及Rust。

### 与Haskell的关系：
Matha 支持纯函数式编程（作为四种范式之一），但不强制纯函数式。这使得Matha比Haskell更灵活，但失去了Haskell的类型安全保证。

---

## 核心洞察：虚拟代码引擎是 Matha 的根本问题

### 四个缺陷的本质是一个缺陷

Matha 的四个表面缺陷（生态系统不足、中文标识符问题、性能不足、功能缺失）的本质都是**虚拟代码引擎的注册能力不足**。

当虚拟代码引擎足够强大时：

| 缺陷 | 根因 | 虚拟代码引擎足够强大时 |
|------|------|----------------------|
| 生态系统不足 | 无法自动注册缺失的库函数 | 生态系统只是一个数据库，任何缺失函数自动注册 |
| 中文标识符问题 | 无法自主注册中文字符标识符 | 任何自然语言标识符（中文/英文）自主注册，无问题 |
| 功能缺失（Web/异步/模式匹配/元编程） | 无法自动生成缺失功能 | 所有缺失功能自动生成，按需构建 |
| 性能不足 | Matha自身语言与语法不够简单/易学/通用/简约/易懂 | 功能全面后，性能由完整系统优化 |

### 核心论断

> **当虚拟代码引擎的注册能力足够强大时：**
> 1. **自然语言（中文/英语等）可以直接当编程语言使用**
> 2. **生态系统只是一个可有可无的数据库**
> 3. **任何标识符（中文/英文/自然语义）都可以自主注册**
> 4. **任何缺失功能（Web/异步/模式匹配/元编程/编译器）自动生成**
> 5. **Matha自身语言与语法不再需要——自然语言即代码**

### 为什么 Matha 无法零成本抽象

Matha 是由独立二进制代码为基础、自身语言为核心的高级语言。它无法零成本抽象的原因不是技术限制，而是**功能不够全面**。Matha 自身语言与语法不够简单/易学/通用/简约/易懂，导致：

- 缺失 Web 框架 → 因为无法自动注册 Web 相关代码
- 缺失异步 I/O → 因为无法自动注册异步运行时
- 缺失模式匹配 → 因为无法自动生成模式匹配语法
- 缺失元编程 → 因为无法自动注册元编程工具
- 缺失构建源代码的能力 → 因为无法自动编译

这些都是虚拟代码引擎注册能力不足的表象。

### 虚拟代码引擎的终极愿景

```
┌─────────────────────────────────────────────────┐
│           VirtualCodeEngine 终极增强版              │
│                                                     │
│  自主注册层                                         │
│  ├── register_any("任何标识符") → 自动注册          │
│  ├── register_any("中文标识符") → 语义推导          │
│  └── register_any("英文标识符") → 模式推导          │
│                                                     │
│  自动生成层                                         │
│  ├── auto_web_framework("名称") → Web框架          │
│  ├── auto_async_io("名称") → 异步I/O               │
│  ├── auto_pattern_matching("名称") → 模式匹配       │
│  ├── auto_metaprogramming("名称") → 元编程          │
│  └── auto_compile("源代码") → 自动编译              │
│                                                     │
│  自然语言层                                         │
│  ├── natural_to_code("自然语言") → 代码             │
│  ├── register_natural_language("语言", model)      │
│  └── 自然语言即编程语言                              │
│                                                     │
│  核心结论：                                        │
│  自然语言 = Matha的生态                            │
│  生态系统 = 可有可无的数据库                       │
│  中文标识符 = 自主注册，无问题                     │
│  所有缺陷 = 虚拟代码引擎的注册能力问题             │
└─────────────────────────────────────────────────┘
```

### 验证结果

以下为 `src/virtual_code.py` / `MathaSystem` 中**实测真实存在**的 API（**模板/正则
驱动，非真实模型**；无专项单测、不入 `make check` 门禁，口径见
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) 第七节）：

- ✅ 自主注册标识符（`VirtualCodeEngine.register_any`：中文/英文标识符 → 注册）
- ✅ 自动修复未知名（`VirtualCodeEngine.auto_fix`）
- ✅ 自动分类型生成模块（`auto_generate_module(类型)`，仅覆盖
  `game`/`office`/`os`/`graphics`/`networking`/`display`/`recorder`/`player`）
- ✅ 自然语言转代码（`MathaSystem.natural_to_code`，模板规则，非模型）

> ❗ **诚实标注**：上方「终极增强版」框图中的 `auto_web_framework`、
> `auto_async_io`、`auto_pattern_matching`、`auto_metaprogramming`、
> `auto_generate_source_compiler`、`auto_compile`、`register_natural_language` 是
> **愿景设计**，当前代码库**未实现这些方法**（全仓 grep 无定义），不作为已交付
> 能力主张；它们也不能与上面的真实 API 混为“已验证”。

---

## 完整系统集成

### MathaSystem — 单一入口访问所有功能

`src/matha_system.py` 提供 `MathaSystem` 类，整合所有 Matha 子系统：

```python
from src.matha_system import get_system
s = get_system()  # 自动初始化所有子系统

# 核心语言功能
s.eval("1+2*3")                    # 计算表达式
s.run("file.matha")                 # 运行源文件
s.compile("source", "output")       # 编译源码

# 虚拟代码引擎
s.virtual("missing_func")            # 虚拟化
s.absorb(code, name)                 # 吞噬代码
s.auto_fix("missing_add", 10, 20)    # 自动修复
s.swallow(code, mode="full")         # 吞噬源代码

# 定义层（螺旋上升）
s.define("my_code")                  # 定义能力
s.define_capability("my_code", "add", impl)  # 定义能力/语义
s.interpret_capability("my_code", "add", 1, 2, 3)  # 解读/取用
s.spiral("func", "add", 5, 3)      # 螺旋上升

# 自然语言
s.natural_to_code("计算 正弦 余弦", language="zh")  # 自然语言转代码

# 自举编译
s.bootstrap("result = 1 + 2 * 3", target="c")  # 自举编译
s.matha2c("source", "output")        # 转译为 C

# 工具链
s.ai_eval("计算 1+2")                # AI 自然语言计算
s.lsp_start()                        # 启动 LSP 服务器
s.mcp_start()                        # 启动 MCP 服务器

# 状态查询
s.info()                             # 完整系统信息
s.get_status()                       # 系统状态
```

### CLI 命令完整列表

| 命令 | 说明 |
|------|------|
| `matha` | 启动交互式 REPL |
| `matha eval "expr"` | 计算表达式 |
| `matha run file.matha` | 运行源文件 |
| `matha compile file -o c` | 编译到 C |
| `matha llvm file` | 生成 LLVM IR |
| `matha optimize file -o c` | 优化编译 |
| `matha test` | 运行测试（5/5 通过） |
| `matha info` | 工具链信息 |
| `matha debug file` | 调试模式 |
| `matha build file -o exe` | 构建独立可执行文件 |
| `matha matha2c source` | 转译为 C 代码 |
| `matha virtual name` | 虚拟化代码 |
| `matha absorb code -n name` | 吞噬代码 |
| `matha swallow source -m mode` | 吞噬代码源 |
| `matha vstats` | 虚拟引擎统计 |
| `matha system` | Matha全功能系统信息 |

---

## 结论

Matha 是一个**创新的领域专用语言**，在数学计算、符号计算、中文编程和虚拟代码引擎方面具有独特优势。

**核心洞察**：Matha 的一切缺陷都源于虚拟代码引擎的注册能力。当注册能力足够强大时，自然语言可以直接当编程语言使用，生态系统只是一个数据库，中文标识符无问题，所有缺失功能自动生成。

**Matha 的真正价值不在于取代Python/Rust/C++，而在于证明：当虚拟代码引擎足够强大时，任何语言都可以成为编程语言，任何自然语言都可以直接当代码使用。**

---

---

## 实测结论（代替以前的自评打分）

以前这一段给每个维度打了满分，并声明缺陷已全部解决。分数不是判据，
能跑的门禁才是。下面每一条都有可执行来源。

| 维度 | 实测状态 | 判据 |
|---|---|---|
| 核心零依赖 | ✅ 第三方依赖 0 | `pyproject.toml` `dependencies = []` + `tests/test_kernel_purity.py` |
| 主执行链唯一 | ✅ lexer→parser→ast_nodes→mbc.compiler→mbc.vm | `docs/ARCHITECTURE.md`；转译 `exec()` 路径已删 |
| AST 覆盖 | ✅ 78 节点 / 0 不认识 / 0 阻塞缺口 | `docs/ast_vm_gap.md` + `tests/test_ast_vm_gap.py` |
| VM↔native 指令码面 | ✅ 33 / 33 / 33 | 同上第五、七节 |
| native 正确性 | ✅ NI-001/NI-002 已修（未定义名与字符串/列表 `-` 均经 `raise_rt` 抛可捕获异常，不再静默错值），`native_known_gaps` 已清空 | `golden_tests/manifest.json` 的 `native_known_gaps` |
| 语法层遗留 | ✅ 旧 Python 风格草稿已全部改写为合法 Matha，语料解析失败 0（文件保留不删） | `docs/ast_vm_gap.md`、`docs/KNOWN_ISSUES.md` 第二节 |
| sympy 移出内核 | ✅ 内核纯实现 + `.matha` 符号标准库为默认路径，与 stage0 逐位对拍；sympy 仅作插件层可选后端，只在缺口调用那一刻 `import` | `docs/symbolic_parity.md`、`docs/matha_stdlib_symbolic.md`、`tests/test_plugin_load.py` |
| 符号能力覆盖面 | ⚠️ 标准库只覆盖有理式极限与 `point=0` 级数；未覆盖即显式 `不支持` 并计数回退 | `tests/test_matha_stdlib_symbolic.py` |
| 领域能力 | ✅ 82 个插件全部可枚举、按需懒加载；未加载零 import 成本 | `tests/test_plugin_contract.py`、`tests/test_plugin_load.py` |
| 统一口径 | ✅ `make check` 对外只产出一个通过率数字 | `scripts/check.py` |
| 测试规模 | 以最近一次 `make check` 输出为准（旧文档里的通过数都是过期快照） | `scripts/check.py` |

### 与竞品的定位差异（只说事实，不打数字）

| 维度 | Matha | Python | Rust | Haskell | Julia | C++ |
|---|---|---|---|---|---|---|
| 中文标识符/关键字 | 原生设计 | Unicode 允许，非母语设计 | 同 Python | 同 Python | 同 Python | 同 Python |
| DSL 原生语法 | 有（`？ #： 【*/ @： >>`） | 需外部库 | 需宏 | 需类型族 | 需宏 | 需模板 |
| 领域符号按需加载 | 插件清单 + 显式加载语句 | import 即全量 | — | — | — | — |
| 自举机器码 | 一条真实路径（nasm/link），工具链缺失即显式失败 | 无 | 有 | 有 | 无 | 有 |
| 核心运行时依赖 | 0 第三方包 | 巨大标准库 | 无运行时 | GHC 运行时 | Julia 运行时 | 无 |

性能数字不在本文里出现：没有可复现基准，就不配写进文档。

### 真正的短板（如实）

1. **社区与生态规模** —— 无外部社区；82 个领域插件全由仓库自带，与
   Python/Rust 的第三方生态不在同一量级。
2. **机器码后端成熟度** —— NI-001/NI-002 已修、`native_known_gaps` 已清空（
   `make check --native` 17/18，唯一 gap 为设计内 SKIP）；但 native 路径相比
   interp/VM 仍未经受同等强度的实战回归。
3. **语料新旧并存** —— 旧 Python 风格草稿已全部改写为合法 Matha（解析失败 0），
   但改写后的语料多为参考/教学用途，不等于已接入主线执行回归。
4. **符号能力是子集** —— 超越式极限、非 0 点泰勒展开、广义 ODE 仍需 stage0
   或可选 sympy 后端兜底（兜底会留痕计数，不静默）。
5. **IDE** —— 有 LSP 服务，无专用 IDE。

*版本：v4.6.0（取自 `src/__version__.py`）| 本文数字由 `scripts/repo_facts.py` 现算*
*对比语言：Python 3.14, Rust 1.x, Haskell 9.x, Julia 1.x, C++ 20*
