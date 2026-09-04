# Matha v4.4 完整架构文档

> **版本：** v4.4.57  
> **日期：** 2026-09-05  
> **状态：** 生产就绪  
> **测试通过率：** 344/344 (100%)

---

## 一、系统概述

Matha 是一门自举式领域专用编程语言与独立可执行系统。核心理念：将编程过程显式划分为三层——

```
【*/意图/*】  →  #：机械语言  →  [] 可读命令
自然语言        数学核心          人可检验的输出
```

### 1.1 核心特征

| 特性 | 说明 |
|------|------|
| **自举式** | 编译器自身可用 Matha 编写 |
| **多语言代码生成** | C/Python/Rust/Go/Java/C++/JS/Matha |
| **离线部署** | 完整功能可离线运行 |
| **成长引擎** | 公式生长 + 系统生长融合闭环 |
| **多前端** | REPL / Web IDE / 移动 Flutter / VSCode 插件 |
| **54个领域模块** | 覆盖物理/工程/AI/金融/生物/化学等 |
| **128项测试** | 全部通过 |

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 核心语言 | Python 3.10+ | 主要实现语言 |
| 移动前端 | Flutter + Dart | 跨平台移动端 |
| Web前端 | React + TypeScript | 管理后台与 Web IDE |
| 编译器后端 | LLVM + C | 原生机器码生成 |
| 运行时 | 自实现 VM + Python | 两种执行模式 |
| 数据库 | SQLite | 离线存储 |
| 并发模型 | CSP + OS线程 | 绕过 Python GIL |
| LLM集成 | Claude/DeepSeek/GPT | 自然语言意图解析 |

---

## 二、五层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Matha 五层架构总览                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  L5: 自我成长层 (Growth)                                             │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  • UnifiedGrowth   统一增长接口                                       │    │
│  │  • InnerLoop       闭环自改进循环 (感知→认知→执行→验证→持久化)        │    │
│  │  • GrowthEngine    生产级成长引擎 v1.2.18                             │    │
│  │  • MathaGrowth     自成长系统 v2 (递归内联/循环展开)                   │    │
│  │  • FormulaGrowth   公式生长引擎 (组合/推导/生成)                       │    │
│  │  • DomainFormula   领域公式注册表 (8大领域 112公式)                    │    │
│  │  • formula_compiler 公式→MIR→多语言编译                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ▲                                        │
│                                    │ 反馈闭环                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  L4: 资源库层 (Resources)                                             │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  • matha/resource/   扩展资源 (20+ 子目录, .matha文件)               │    │
│  │  • matha/library/    核心库 (arithmetic/geometry/calculus)           │    │
│  │  • matha/knowledge/  学科知识库 (math/physics/chemistry/biology)     │    │
│  │  • FormulaRegistry  公式注册表 (几何+领域公式)                        │    │
│  │  • CapabilityRegistry 能力标注注册表                                   │    │
│  │  • 资源审计: 13项检查 (关键词/变体/规则/概念/公式/安全/成长)           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ▲                                        │
│                                    │ 公式编译                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  L3: 后端层 (Domains & Execution)                                     │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  • src/domains/      54个领域模块 (registry.py 统一管理)              │    │
│  │  • src/stdlib/       标准库 (core/arithmetic/algebra/calculus/logic) │    │
│  │  • src/mathlib.py    数学库 (常量/三角/对数/物理常量)                  │    │
│  │  • src/hardware/     HAL层 (hal_v2.py + multiprocessing)             │    │
│  │  • src/intent/       意图层 (decomposer/llm_parser/MIR_generator)    │    │
│  │  • src/formula_system.py  公式互转系统 (Formula/Registry/Derivation)  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ▲                                        │
│                                    │ MIR编译                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  L2: 中端层 (Compiler & IR)                                           │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  • src/mir.py          MIR类型系统 (VOID/BOOL/INT/FLOAT/PTR/FUNC)   │    │
│  │  • src/mir_opt.py      12个优化Pass (含MathaFormulaOptPass)          │    │
│  │  • src/compiler/       LLVM后端 (matha_cc.py + llvm_hybrid.py)      │    │
│  │  • src/vm.py           VM解释器 (MIR级栈式执行)                       │    │
│  │  • src/symbolic.py     符号引擎 (Expr AST + diff/integrate)          │    │
│  │  • src/formula_compiler.py  Formula→MIR→Python/C 编译器              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ▲                                        │
│                                    │ Token/AST                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  L1: 前端层 (Frontend)                                                │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  • src/lexer.py      词法分析器 (支持Unicode/CJK/Matha专属符号)       │    │
│  │  • src/parser.py     递归下降语法分析器 (EBNF §17 完整语法)          │    │
│  │  • src/interp.py     解释器 (AST级 + 命令绑定)                        │    │
│  │  • src/ai_assistant.py  意图解析器 (FriendlyIntentParser + 公式推导)   │    │
│  │  • src/repl.py       REPL交互层 (三模式: 数学/自然语言/意图)          │    │
│  │  • src/lsp.py        Tree-sitter LSP (补全/跳转/悬停/诊断)            │    │
│  │  • mobile/           Flutter移动端 (Pyodide WASM运行时)               │    │
│  │  • web/              Web IDE (React+TypeScript)                       │    │
│  │  • extensions/       VSCode扩展 (TypeScript)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  横向横切关注点:                                                      │    │
│  │  • src/unified_*.py    统一接口层 (multi-lang/growth/async/diag/repl) │    │
│  │  • src/diagnostics.py  诊断系统 (LSP兼容格式)                          │    │
│  │  • src/ffi.py          FFI桥接 (C/Python互操作)                        │    │
│  │  • src/net_security.py 网络安全引擎                                    │    │
│  │  • src/firewall.py     三层防火墙                                      │    │
│  │  • src/csp_os_thread.py CSP并发模型                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、组件交互流程

### 3.1 核心处理流水线

```
用户输入 (自然语言 / Matha源码 / 表达式)
    │
    ▼
┌─────────────────┐
│  L1: 词法分析    │  lexer.py
│  Token 流       │  ──→ 支持 CJK/Unicode/Matha专属符号 (？【】〔〕《》#：………)
└────────┬────────┘
         │ Token 流
         ▼
┌─────────────────┐
│  L1: 语法分析    │  parser.py
│  AST 生成       │  ──→ 递归下降, EBNF §17 完整语法
└────────┬────────┘
         │ AST
         ├──────────────────────────────────────────────────────┐
         │                                                      │
         ▼                                                      ▼
┌─────────────────────┐                          ┌─────────────────────────┐
│  L1: 意图解析        │                          │  L1: 直接Matha源码       │
│  ai_assistant.py    │                          │  (已编译的 .matha 文件)  │
│  • 关键词匹配        │                          │                         │
│  • 变体表达匹配      │                          │                         │
│  • 常识规则推理      │                          │                         │
│  • 公式推导意图      │                          │                         │
└──────────┬──────────┘                          │                         │
           │ Matha 代码片段                        │                         │
           ▼                                      │                         │
┌─────────────────────┐                          │                         │
│  L2: 解释器执行      │◄─────────────────────────┘                         │
│  interp.py          │                                                      │
│  • func定义→闭包    │                                                      │
│  • 表达式求值       │                                                      │
│  • 标准库内建       │                                                      │
│  • 命令字面量绑定   │                                                      │
└──────────┬──────────┘                                                      │
           │ 执行结果                                                         │
           ▼                                                                  │
┌─────────────────────┐                                                      │
│  L1: 输出层          │                                                      │
│  REPL / Web / Mobile│                                                      │
│  • 人类可读输出     │                                                      │
│  • 分步追踪         │                                                      │
└─────────────────────┘                                                      │
                                                                             │
┌──────────────────────────────────────────────────────────────────────────┐
│                        可选: 编译路径 (AOT/JIT)                           │
│                                                                          │
│  AST → L2: MIR生成 (mir.py) → L2: 优化Pass (mir_opt.py)                  │
│       → L2: LLVM IR (compiler/llvm_backend.py)                           │
│       → 原生机器码 (llc/clang)                                            │
│                                                                          │
│  优化Pass列表:                                                            │
│  1. MathaConstFoldPass    常量折叠                                        │
│  2. MathaSimplifyPass     代数简化                                        │
│  3. MathaFormulaOptPass   公式MIR优化 (新增v4.4.57)                       │
│  4. MathaTailRecPass      尾递归消除                                      │
│  5. MathaLoopUnrollPass   循环展开                                        │
│  6. MathaSIMDPass         自动向量化                                      │
│  7. MathaCurryFlattenPass 柯里化扁平化                                    │
│  8. MathaCommonSubexprElimPass  公共子表达式消除                           │
│  9. MathaCopyPropagationPass    复制传播                                  │
│  10. MathaStrengthReductionPass 强度削弱                                  │
│  11. MathaDeadCodeElimPass    死代码消除                                  │
│  12. MathaInlinePass          函数内联                                    │
│  13. MathaPeepholeOptimizer   窥孔优化                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 意图解析流程（自然语言→Matha代码）

```
用户输入: "帮我算一下 100 以内所有素数"
    │
    ├─→ Strategy 1: KEYWORD_MAP 关键词匹配
    │     "素数" → IntentType.素数因数 (+3.0分)
    │
    ├─→ Strategy 2: VARIATION_MAP 变体匹配
    │     "找出" + "素数" → 未匹配
    │
    ├─→ Strategy 3: COMMONSENSE_RULES 常识规则
    │     r"(素数|质数|因数|因子)\s*(找出|列出|计算)" → IntentType.素数因数 (+5.0分)
    │
    ├─→ Strategy 4: 数字特征推断
    │     100 → 范围推断
    │
    └─→ Strategy 5: 用户学习记忆 (_learned_patterns)
          历史学习模式匹配

结果: (IntentType.素数因数, confidence=0.85)
    │
    ▼
decompose() → 步骤分解
    ├─→ _decompose_number_theory()
    │     步骤1: "找出 1 到 100 的素数"
    │     matha_code: "#1：[素数筛(100)]"
    │
    └─→ LLM 辅助（可选）→ 更精确的数学代码生成

    │
    ▼
生成 Matha 代码 → 执行 → 返回结果
```

### 3.3 公式生长流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FormulaGrowthEngine 核心流程                      │
│                                                                     │
│  输入: FormulaRegistry (112个公式)                                   │
│                                                                     │
│  Phase 1: 组合 (Compose)                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  遍历所有公式对 (O(n²))                                      │   │
│  │  公式A: 动能 Ek = 0.5*m*v²  vars={m,v}                     │   │
│  │  公式B: 动量 p = m*v        vars={m,v}                     │   │
│  │  共享变量: {m,v} → 可消元                                   │   │
│  │  结果: Ek = p²/(2m)  ✓ 新公式生成                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  Phase 2: 推导 (Infer)                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  符号微分: d(Ek)/dv = m*v = 动量 ✓                          │   │
│  │  代入简化: W = F*s → F=ma → W = m*a*s ✓                    │   │
│  │  批量求导: 对所有公式的所有变量求导                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  Phase 3: 生成 (Generate)                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  约束满足: 给定目标变量+变量列表+领域约束                      │   │
│  │  模板匹配: 乘积/商/幂/线性组合/二次型                         │   │
│  │  自检: 求值验证 → 注册新公式                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  Phase 4: 编译 (Compile) ← 新增 v4.4.57                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  FormulaCompiler:                                          │   │
│  │  新公式 → MIR → Python代码 / C代码 / JavaScript            │   │
│  │  自动应用 MathaFormulaOptPass 优化                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  注册回 FormulaRegistry → 下一轮成长基于新公式库                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 内循环成长流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MathaInnerLoop 闭环成长                           │
│                                                                         │
│   ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐            │
│   │感知层 │───▶│认知层 │───▶│执行层 │───▶│验证层 │───▶│持久化 │            │
│   └──────┘    └──────┘    └──────┘    └──────┘    └──────┘            │
│       ▲                                                         │      │
│       │                                                         │      │
│       └──────────────── 反馈循环 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←┘      │
│                                                                         │
│  Phase 1: 感知 (Perception)                                            │
│  • collect_resource_snapshot()   资源快照                              │
│  • collect_interaction_summary() 交互摘要 (成功率/失败模式)               │
│                                                                         │
│  Phase 2: 认知 (Cognition)                                             │
│  • cognitive_diagnose()                                          │
│    └─ self_diagnose()  全面自检 (意图解析器/解释器/防火墙/安全/成长)      │
│    └─ 计算健康分数 = 缺陷分×0.4 + 资源分×0.3 + 交互分×0.3              │
│                                                                         │
│  Phase 3: 执行 (Execution)                                             │
│  • execute_remediation()                                              │
│    └─ auto_remediate()  自动修复缺陷 (按严重度选择策略)                   │
│    └─ self_extend_concepts()  自扩展: 从失败交互派生新概念                  │
│    └─ self_extend_intents()   自扩展: 从失败模式发现新意图                  │
│    └─ _cross_module_collaboration()  跨模块协作验证                      │
│    └─ _handle_error_buffer()  处理错误缓冲区                           │
│                                                                         │
│  Phase 4.5: 公式生长 (新增 v4.4.57)                                      │
│  • formula_grow(op_type="auto")  自动化公式生长                          │
│    └─ 组合/推导/生成 → 注册 → 编译                                    │
│                                                                         │
│  Phase 4.6: 自升级检查                                                  │
│  • self_upgrade_check()   检测版本状态和待处理高危补丁                    │
│  • self_upgrade_apply()   自动应用补丁                                   │
│                                                                         │
│  Phase 4.7: 自优化                                                      │
│  • self_optimize_performance()  性能分析与优化                            │
│    └─ 自适应轮询间隔调整                                                │
│    └─ 缓冲区过期清理                                                    │
│    └─ 成长日志压缩                                                      │
│    └─ 搜索缓存优化                                                      │
│                                                                         │
│  Phase 5: 持久化                                                        │
│  • save_state()   保存内循环状态到 .matha_cache/inner_loop_state.json   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 四、数据流图

### 4.1 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Matha 数据流架构                                  │
│                                                                             │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐       │
│  │ 自然语言  │─────▶│ 意图解析  │─────▶│ Matha代码 │─────▶│ 解释器    │       │
│  │ 输入     │      │ (策略5)   │      │ 片段     │      │ (AST级)  │       │
│  └──────────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘       │
│                         │                 │                 │              │
│                         │                 │                 │              │
│                         ▼                 ▼                 ▼              │
│              ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐     │
│              │ 关键词/变体/规则  │  │ 步骤分解     │  │ 公式生长引擎  │     │
│              │ 5策略分类       │  │ 生成代码     │  │ 组合/推导/生成 │     │
│              └─────────────────┘  └──────────────┘  └──────┬─────┘     │
│                                                           │            │
│                                                           ▼            │
│                                               ┌───────────────┐       │
│                                               │ FormulaRegistry│       │
│                                               │ (112公式)     │       │
│                                               └───────┬───────┘       │
│                                                       │               │
│                                                       ▼               │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐ │
│  │ Matha源码 │─────▶│ 词法分析  │─────▶│ 语法分析  │─────▶│ MIR生成   │ │
│  │ (.matha) │      │ Token流  │      │ AST      │      │ IR       │ │
│  └──────────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘ │
│                         │                 │                 │         │
│                         │                 │                 ▼         │
│                         │                 │      ┌────────────────┐   │
│                         │                 │      │ 13个优化Pass    │   │
│                         │                 │      │ (含公式优化)    │   │
│                         │                 │      └────────┬───────┘   │
│                         │                 │               │           │
│                         │                 │               ▼           │
│                         │                 │      ┌──────────────┐     │
│                         │                 │      │ LLVM IR      │     │
│                         │                 │      │  (可选)       │     │
│                         │                 │      └──────┬───────┘     │
│                         │                 │             │            │
│                         │                 │             ▼            │
│                         │                 │    ┌──────────────┐      │
│                         │                 │    │ 原生机器码    │      │
│                         │                 │    │ (C/Python/JS) │      │
│                         │                 │    └──────────────┘      │
│                         │                 │                          │
│                         │                 └──────────────────────────┘
│                         │
│                         ▼
│              ┌─────────────────┐
│              │ 诊断/修复建议    │
│              │ LSP格式输出     │
│              └─────────────────┘
│
│  ┌──────────────────────────────────────────────────────────────────┐
│  │                        持久化存储                                  │
│  │  • .matha_cache/inner_loop_state.json  (内循环状态)               │
│  │  • .matha_cache/jit_*.json           (JIT缓存)                   │
│  │  • .matha_cache/python/*.json        (Python编译缓存)             │
│  │  • SQLite (离线存储, mobile)                                       │
│  └──────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 领域模块数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        领域模块注册与调用流程                                  │
│                                                                             │
│  DomainRegistry (registry.py)                                              │
│  ├── 预定义模板: 24个领域 (AI_DataScience / SoftwareAppDev / GameImmersion │
│  │              / Automation / IoTHardware / OSNetwork / BlockchainWeb3    │
│  │              / ... / CustomDomain)                                       │
│  │                                                                          │
│  ├── 自动发现: scan_module_capabilities()                                   │
│  │     扫描 src/domains/*.py 中所有 _xxx_yyy 格式的函数                       │
│  │     提取 domain/capability/params/expr                                   │
│  │                                                                          │
│  └── 公式同步: DomainFormulaRegistry.register_all_domains()                 │
│        ├─ mechanics (8公式)    → 牛顿定律/动能/动量/重力/功/功率/自由落体/平抛│
│        ├─ geometry (6公式)     → 圆面积/圆周长/球体积/球表面积/圆柱/圆锥     │
│        ├─ electromagnetism (4) → 欧姆定律/电功率/焦耳热/库仑力               │
│        ├─ thermodynamics (3)   → 理想气体/热传递/热机效率                     │
│        ├─ wave_optics (2)      → 波长频率/折射定律                           │
│        ├─ nuclear (2)          → 质能方程/半衰期                             │
│        ├─ celestial (3)        → 开普勒第三定律/万有引力/第一宇宙速度         │
│        ├─ chemistry (3)        → 摩尔数/浓度/理想气体状态                     │
│        └─ geometry_defaults (75+) → 长方形/三角形/梯形/菱形/椭圆等            │
│                                                                             │
│  调用路径:                                                                   │
│  用户输入 "计算动能" ──▶ 意图分类(物理) ──▶ 查找领域模块                       │
│  ──▶ 匹配 src/domains/dynamics.py _牛顿_力() / _动能_公式()                   │
│  ──▶ 执行 → 返回结果                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五、系统边界定义

### 5.1 系统边界

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Matha 系统边界                                        │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║                     Matha 核心系统 (内部)                              ║  │
│  ║                                                                       ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │  L1 前端层                                                       │ ║  │
│  ║  │  • lexer.py    • parser.py    • interp.py                       │ ║  │
│  ║  │  • ai_assistant.py • repl.py   • lsp.py                         │ ║  │
│  ║  │  • tokens.py   • ast_nodes.py                                 │ ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │  L2 中端层                                                       │ ║  │
│  ║  │  • mir.py      • mir_opt.py   • vm.py                          │ ║  │
│  ║  │  • symbolic.py • formula_system.py                              │ ║  │
│  ║  │  • compiler/   • formula_compiler.py                            │ ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │  L3 后端层                                                       │ ║  │
│  ║  │  • domains/    (54个领域模块)                                    │ ║  │
│  ║  │  • stdlib/     (core/arithmetic/algebra/calculus/logic)          │ ║  │
│  ║  │  • intent/     (decomposer/llm_parser/mir_generator)             │ ║  │
│  ║  │  • hardware/   (HAL v2.0)                                      │ ║  │
│  ║  │  • domain_formula.py  (领域公式注册表)                             │ ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │  L4 资源层                                                       │ ║  │
│  ║  │  • matha/resource/  (扩展资源)                                   │ ║  │
│  ║  │  • matha/library/   (核心库)                                     │ ║  │
│  ║  │  • matha/knowledge/ (学科知识)                                    │ ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │  L5 成长层                                                       │ ║  │
│  ║  │  • growth_engine.py  • unified_growth.py                        │ ║  │
│  ║  │  • inner_loop.py     • selfupgrade.py                           │ ║  │
│  ║  │  • growth.py         • matha_growth.py                          │ ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║                                                                       ║  │
│  ║  ── 统一接口层 (横切) ───────────────────────────────────────────────  ║  │
│  ║  • unified.py  unified_multilang.py  unified_async.py                ║  │
│  ║  • unified_growth.py  unified_diagnostics.py  unified_repl.py        ║  │
│  ║  • unified_parser.py                                               ║  │
│  ║                                                                       ║  │
│  ║  ── 诊断系统 (横切) ────────────────────────────────────────────────  ║  │
│  ║  • diagnostics.py    (基础 IDE 诊断)                                  ║  │
│  ║  • diagnostics_v2.py  (增强诊断 + 上下文分析)                          ║  │
│  ║  • unified_diagnostics.py (统一层)                                    ║  │
│  ║  • lsp.py             (Tree-sitter LSP)                              ║  │
│  ║  • hybrid_compiler.py (混合编译缺陷报告)                               ║  │
│  ║                                                                       ║  │
│  ║  ── 安全系统 (横切) ────────────────────────────────────────────────  ║  │
│  ║  • net_security.py  (网络安全引擎)                                    ║  │
│  ║  • firewall.py      (三层防火墙)                                      ║  │
│  ║  • ffi.py          (FFI 桥接)                                        ║  │
│  ║  • windows_mp_check.py (Windows spawn 检测)                           ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                             │
│  ════════════════════════════════════════════════════════════════════════  ═│
│  外部接口 (对外暴露)                                                          │
│  ════════════════════════════════════════════════════════════════════════  ═│
│  • CLI:    matha [command] [args]                                          │
│  • REPL:   matha (交互式)                                                  │
│  • Web:    web/index.html (React+TypeScript IDE)                           │
│  • Mobile: Flutter app (mobile/)                                           │
│  • VSCode: extensions/vscode-matha/                                        │
│  • Jupyter: %load_ext matha.jupyter  %matha ...                            │
│  • Python API: from src.unified import *                                   │
│  • LSP:    4000端口 (标准LSP协议)                                           │
│  • REST:   :8080 (认证/用户/服务等API)                                      │
│  ════════════════════════════════════════════════════════════════════════  ═│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 模块依赖关系

```
                    ┌──────────────────┐
                    │  src/__init__.py  │
                    │  (统一入口)       │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  解析层        │  │  执行层          │  │  编译层          │
│  lexer.py     │  │  interp.py      │  │  compiler/      │
│  parser.py    │──▶│  vm.py          │  │  matha_cc.py    │
│  tokens.py    │  │  ai_assistant.py│  │  llvm_backend.py│
└───────┬───────┘  └────────┬────────┘  └────────┬────────┘
        │                   │                    │
        │                   ▼                    │
        │          ┌─────────────────┐           │
        │          │  领域/标准库      │           │
        │          │  domains/       │           │
        │          │  stdlib/        │           │
        │          │  mathlib.py     │           │
        │          │  formula_*.py   │           │
        │          └────────┬────────┘           │
        │                   │                    │
        └───────────────────┼────────────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │  成长/诊断层       │
                    │  growth_*.py     │
                    │  unified_*.py    │
                    │  diagnostics*.py │
                    │  inner_loop.py   │
                    └──────────────────┘
```

---

## 六、关键接口

### 6.1 统一入口（推荐用法）

```python
# 方式1: 统一生长接口
from src.unified_growth import get_unified_growth
ug = get_unified_growth()
ug.formula_grow(op_type="auto")        # 公式生长
ug.domain_formula_summary()            # 领域公式总览
ug.compile_formula("牛顿第二定律")       # 公式编译

# 方式2: 统一诊断接口
from src.unified_diagnostics import get_diagnostics, diagnose_source
diagnostics = get_diagnostics(source_code)

# 方式3: 统一多语言接口
from src.unified_multilang import get_unified_multilang
ml = get_unified_multilang()

# 方式4: 统一REPL接口
from src.unified_repl import run_repl
run_repl()
```

### 6.2 公式生长 API

```python
from src.unified_growth import get_unified_growth
ug = get_unified_growth()

# 自动化成长（组合+推导+生成）
result = ug.formula_grow(
    op_type="auto",
    max_combinations=5,
    max_derivatives=10,
    generate_constraints=[
        {"name": "新公式A", "target": "F", "variables": ["m", "a"],
         "constraints": {"domain": "动力学"}}
    ]
)
# result: {"success": True, "stats": {"compose": N, "infer": N, "generate": N},
#          "registered": N}

# 领域公式总览
summary = ug.domain_formula_summary()
# summary: {"loaded_domains": 8, "total_formulas": 112, "summary": "..."}

# 公式编译
result = ug.compile_formula("牛顿第二定律", optimize=True)
# result: {"success": True, "name": "牛顿第二定律",
#          "python": "def 牛顿第二定律(F, m, a): ...",
#          "c": "double 牛顿第二定律(double F, double m, double a) { ... }",
#          "optimizations": [...]}
```

### 6.3 诊断 API

```python
from src.unified_diagnostics import get_diagnostics
from src.diagnostics_v2 import EnhancedDiagnosticCollector, Severity

# 统一接口
diagnostics = get_diagnostics("x = 1 + ;  # 语法错误")
for d in diagnostics:
    print(f"[{d.severity.value}] L{d.line}: {d.message}")
    print(f"  建议: {d.fix}")

# 增强接口
collector = EnhancedDiagnosticCollector()
collector.add_error("未定义变量 'abc'", line=3, code="UNDEFINED_VAR",
                    fix="检查变量名拼写，或添加绑定: abc = ?")
collector.add_warning("函数未使用", line=10, code="UNUSED_FUNC")
print(collector.summary())
print(collector.to_json())  # LSP格式
```

### 6.4 公式系统 API

```python
from src.formula_system import FormulaRegistry, Formula
from src.symbolic import Var, Mul, Num

reg = FormulaRegistry()
reg.register_geometric_defaults()  # 注册75+几何公式

# 查询公式
f = reg.get("圆面积")
print(f.evaluate({"半径": 5}))  # 78.5398...

# 参数等价
reg.add_equivalence(ParamEquivalence("长", "底", "长方形面积", "平行四边形面积"))

# 推导
result = reg.derive("平行四边形面积", "底", "长")
# result: DerivedResult(成功=True, 推导公式="长方形面积")

# 交叉语言验证
reg.cross_language_verify()
```

---

## 七、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v4.4.50 | 2026-08 | 初始发布，核心解释器+编译器 |
| v4.4.55 | 2026-09 | 成长引擎升级（公式生长+系统生长融合） |
| v4.4.56 | 2026-09 | Parser规范化 (case...of→match...{}) |
| v4.4.57 | 2026-09 | **当前版本**: 解决KNP-001~010全部已知问题 |

---

## 八、系统约束与已知限制

### 8.1 已解决（v4.4.57）

| 编号 | 问题 | 解决方式 |
|------|------|---------|
| KNP-001 | LLM需API Key | 正则引擎为默认，LLM可选 |
| KNP-003 | Jupyter需IPython | try/except容错，未安装时静默跳过 |
| KNP-004 | 缓存内存占用 | 新增 clear_pkg_cache()/get_pkg_cache_size() |
| KNP-005 | 长文本分解准确率 | 降低阈值+关键词分块+多句拆分 |
| KNP-006 | 命名不一致 | stdlib新增17个中英双语别名 |
| KNP-007 | Windows spawn限制 | 新增 windows_mp_check.py 检测工具 |
| KNP-008 | 置信度固定0.50 | 改为动态计算 0.3~0.9 |
| KNP-009 | Unicode变量解析失败 | VAR_PATTERN支持中文Unicode |
| KNP-010 | 成长系统需手动传助手 | create_growth_engine()自动初始化 |

### 8.2 固有约束

| 约束 | 说明 |
|------|------|
| Windows spawn | Worker函数必须定义在模块顶层，不能是lambda/局部函数 |
| LLM可选 | 无API Key时自动降级，功能完整但不使用LLM增强 |
| 离线模式 | 所有核心功能离线可用；LLM和网络搜索为可选增强 |
| 公式Unicode | VAR_PATTERN支持中文变量，但部分正则表达式引擎可能不支持全量CJK |
| 非默认语言 | Rust/Go/JS/C 前端默认不加载，按需懒加载（try/except ImportError） |

### 8.3 语言处理配置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     多语言前端懒加载架构                                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  默认激活（Matha 核心）                                                │   │
│  │  • Matha 词法/语法/解释器/编译器 — 无需外部依赖                        │   │
│  │  • Python 代码生成 — 内置                                            │   │
│  │  • 正则意图解析 — 内置                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  可选加载（按需激活，非默认）                                           │   │
│  │                                                                      │   │
│  │  try:                                                                │   │
│  │      from src.tree_sitter_backends import RustParser, GoParser...    │   │
│  │      _USE_TS = True   ← 仅当 tree-sitter 已安装时激活                  │   │
│  │  except ImportError:                                                 │   │
│  │      _USE_TS = False   ← 降级到正则前端                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│              ┌───────────────┼───────────────┐                              │
│              ▼               ▼               ▼                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ RustFrontend │  │ GoFrontend   │  │ JS/C Frontend│                      │
│  │ (tree-sitter)│  │ (tree-sitter)│  │ (可选)       │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│              │               │               │                              │
│              └───────────────┼───────────────┘                              │
│                              ▼                                               │
│                    ┌──────────────────┐                                      │
│                    │  统一 Matha MIR  │                                      │
│                    │  (语言无关IR)    │                                      │
│                    └──────────────────┘                                      │
│                              │                                               │
│                              ▼                                               │
│                    ┌──────────────────┐                                      │
│                    │  Matha 原生执行   │                                      │
│                    │  (解释器/VM/编译) │                                      │
│                    └──────────────────┘                                      │
│                                                                             │
│  ── 设计原则 ─────────────────────────────────────────────────────────────  │
│  1. 非默认语言模块默认不加载，不占用内存/启动时间                             │
│  2. 系统启动时不自动初始化外部语言处理器                                      │
│  3. Matha 在任何生态/平台/环境下独立安装使用                                  │
│  4. 降级策略：tree-sitter 不可用时自动回退到正则解析                           │
│  5. 用户显式调用时按需加载（Lazy Loading）                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.4 平台兼容性

| 平台 | 支持状态 | 说明 |
|------|---------|------|
| Windows | ✅ 完整支持 | multiprocessing spawn 兼容检测 |
| Linux | ✅ 完整支持 | 原生多线程 + spawn |
| macOS | ✅ 完整支持 | 原生支持 |
| WASM | ✅ 部分支持 | matha_wasm/ 子项目 |
| Mobile (Android/iOS) | ✅ 完整支持 | Flutter + Pyodide |
| 缓存清理 | 大型项目需手动调用 clear_cache() |
