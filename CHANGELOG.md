# Matha 变更摘要

## 提交：`9a31a0c` — x86-64 原生发射器 + M3V 自举闭环 + 自然语言管线

**日期**：2026-09-10
**远程仓库**：`git@github.com:zzk2025r/matha.git`
**使用端**：`C:\Users\Admin\Matha`

---

## 一、变更范围

| 维度 | 新增 | 修改 | 删除 |
|------|------|------|------|
| 源码文件 | 28 | 10 | 5 |
| 测试文件 | 7 | 2 | 0 |
| Matha 源码 | 5 | 3 | 0 |
| 净代码行 | +12,111 | -1,133 | — |

---

## 二、新增模块

### 2.1 M3V 字节码编译器 (`src/mbc/`)

| 文件 | 职责 |
|------|------|
| `opcodes.py` | M3V 操作码定义（PUSH/CALL/RET/JMP/BINOP/OUTPUT/HALT 等 30+ 指令） |
| `compiler.py` | Matha AST → M3V 字节码（函数定义、递归、柯里化、控制流） |
| `vm.py` | M3V 虚拟机（栈式帧、闭包、偏应用、内建函数） |
| `serial.py` | 字节码序列化/反序列化（.mbc 文件格式） |
| `cli.py` | 命令行工具：`compile`/`run`/`eval`/`native` 子命令 |
| `native.py` | **x86-64 机器码发射器**（M3V → 机器码 → PE64 .exe） |

### 2.2 x86-64 原生发射器 (`src/mbc/native.py`, 650 行)

**完整管线**：Matha 源码 → AST → M3V 字节码 → x86-64 机器码 → PE64 可执行文件

- **PEB 遍历自解析 kernel32 导出**（不依赖 PE 导入表，加载器兼容性最大化）
- 支持的运行时能力：
  - 整数算术：`+ - * // %`
  - 比较运算：`== != < > <= >=`
  - 一元运算：`neg not`
  - 控制流：`JMP JZ JNZ`
  - 单参数递归函数：`func fib(n: Int) -> Int = (n) => ...`
  - 整数十进制输出（`print_int`：GetStdHandle + WriteFile）
  - 进程退出（ExitProcess）
- 手写 PE64 链接器：2 节（.text EXEC/.data RW），无数据目录

### 2.3 自然语言管线 (`src/nl_*.py`)

| 文件 | 职责 |
|------|------|
| `nl_semantic.py` | 时代语义词典 — 中文/英文词汇的语义理解 |
| `nl_definition.py` | 定义构建器 — 列明条目 + 赋予时代定义 |
| `nl_to_formula.py` | 公式转换器 — 定义 → Matha 公式代码 |
| `nl_pipeline.py` | 统一管线 — NL 输入 → 语义 → 定义 → 公式 → 编译 → 执行 |

### 2.4 Matha 自举源码 (`matha/*.matha`)

| 文件 | 内容 |
|------|------|
| `stdlib.matha` | 纯 Matha 标准库（字符串/列表/JSON/文件IO/数学函数，542 行） |
| `interp.matha` | 用 Matha 实现的 Matha 解释器（eval/闭包/控制流） |
| `lexer.matha` | 用 Matha 实现的词法器 |
| `parser.matha` | 用 Matha 实现的语法器 |
| `bootstrap_matha.matha` | 自举测试套件 |
| `compiler_matha.matha` | 用 Matha 实现的编译器 |
| `interp_matha.matha` | 用 Matha 实现的完整解释器 |

### 2.5 其他新增模块

| 文件 | 职责 |
|------|------|
| `src/matha_vm.py` | 三进制原生虚拟机（Base2/Base3/Base10 底层数制） |
| `src/m3v_vm.py` | M3V 独立虚拟机实现 |
| `src/compiler_matha.py` | Matha → M3V 编译器 v2 |
| `src/lexer_matha.py` | Matha 词法器独立实现 |
| `src/matha_formula.py` | 公式系统 |
| `src/matha_runtime.py` | 运行时引擎 |
| `src/matha_service.py` | 集成服务层（eval/run/compile_to_c/compile_to_llvm/generate_code） |
| `src/matha/language_bridge.py` | 语言桥（吞噬 Rust/Go/JS/C/Python → Matha） |
| `src/matha/growth.py` | 成长引擎（组合/推导/生成/吞噬） |
| `src/base3_matha.py` | 三进制基础库 |

---

## 三、关键 Bug 修复

### 3.1 x86-64 机器码编码（附 7 项字节级单元测试）

| Bug | 位置 | 现象 | 修复 |
|-----|------|------|------|
| 尾声 ModRM 方向反 | `native.py:192` | `0xE4`(mov rbp,rsp) 导致 ret 跳 0 崩溃 | → `0xEC`(mov rsp,rbp) |
| 序言 REX.X 误置 | `native.py:174` | `0x4F` 使 SIB 无索引变 r12+r12 | → `0x4D`(REX.X=0) |
| CALL 栈不平衡 | `native.py:211-214` | 返回值未覆盖函数槽 → BINOP 读到指针 | mov [r12-16],rax + sub r12,8 |

### 3.2 语法解析

- 修复函数体内 `let f(带参类型标注) = ...` 被误归为 FuncDef 的问题

---

## 四、测试覆盖

| 测试文件 | 测试数 | 内容 |
|----------|--------|------|
| `test_native.py` | 15 | 端到端：编译 exe → 运行 → 校验 stdout/rc |
| `test_native_encoding.py` | 7 | 字节级：验证三处 Bug 修复的机器码序列 |
| `test_mbc_bootstrap.py` | 6 | M3V 自举闭环测试 |
| `test_mbc_bytecode.py` | 12 | M3V 字节码执行（递归/数论/字符串） |
| `test_new_features.py` | 10 | 新功能测试 |
| `test_nl_pipeline.py` | 18 | 自然语言管线测试 |

**全量回归**：1089 项通过（原 1067 + 新增 22）

---

## 五、Matha 能力版图

```
自然语言输入（中文/英文）
    │
    ▼
┌─────────────────────────────────┐
│ NL 语义层                       │
│ nl_semantic → nl_definition     │
│ → nl_to_formula                 │
│ （中文的语义精确性 +             │
│  英文的结构表达力）              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ Matha 源码（.matha）             │
│ func fib(n: Int) -> Int =       │
│   (n) => if n<2 then n          │
│   else fib(n-1)+fib(n-2)        │
│ #1：[fib(20)]                   │
└────────────┬────────────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐   ┌──────────────┐
│ 解释器   │   │ 编译器        │
│ interp.py│   │ compiler.py  │
│ (Python) │   │ → M3V 字节码  │
└─────────┘   └──────┬───────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌────────────┐      ┌──────────────┐
   │ M3V 虚拟机 │      │ x86-64 发射器 │
   │ vm.py      │      │ native.py    │
   │ (栈式帧)   │      │ → PE64 .exe  │
   └────────────┘      └──────────────┘
                              │
                              ▼
                      Windows 原生进程
                      fib(20) = 6765
```

### 中英互补设计

| 层次 | 中文角色 | 英文角色 |
|------|----------|----------|
| 语义层 | 时代语义词典（不可遗失的定义精确性） | 结构化表达（无限组合能力） |
| 源码层 | `#1：[...]` 输出标注、`真/假` 布尔值 | `func/if/then/else` 关键字 |
| 自举层 | `matha/stdlib.matha` 纯 Matha 标准库 | `matha/parser.matha` 语法器 |
| 底层 | 三进制（Base-3）映射汉字编码 | 二进制（Base-2）物理存储 |

### AI 编程能力

| 能力 | 实现 | 状态 |
|------|------|------|
| 虚构（从无到有生成公式） | `growth.py: generate()` | ✅ |
| 创造（组合已有公式导出新公式） | `growth.py: compose()` | ✅ |
| 解释（符号微分/代数变形） | `growth.py: infer()` | ✅ |
| 定义（时代语义→Matha 定义） | `nl_definition.py` | ✅ |
| 编程（NL → 公式代码 → 执行） | `nl_pipeline.py` | ✅ |
| 运行（解释器/VM/原生 exe） | `interp.py` / `vm.py` / `native.py` | ✅ |
| 改造（吞噬外部语言→融合） | `language_bridge.py: devour()` | ✅ |
| 代码生成（NL → Matha/Python/Rust/JS） | `matha_service.py: generate_code()` | ✅ |
| C/LLVM 编译 | `matha_service.py: compile_to_c/llvm()` | ✅ |
| x86-64 原生编译 | `native.py: compile_to_exe()` | ✅ |
| 自举（Matha 用 Matha 实现） | `matha/interp.matha` 等 | ✅ |

### 绝对底层

```
Base-2（二进制）  ← 物理存储（最终表示）
Base-3（三进制）  ← 字符编码（汉字/字母映射）
Base-10（十进制） ← 数值运算（Int/Float）
     ↑
  MathaVM（src/matha_vm.py）
  零 Python/C 依赖，所有类型基于原生数制
```

---

## 六、使用端同步

已将以下文件同步至 `C:\Users\Admin\Matha`：

- `src/` 下 22 个核心 .py 文件（含 `src/mbc/` 全目录 7 个文件）
- `matha/` 下 9 个 .matha 源文件（含自举标准库）
- 验证通过：`compile_to_exe('#1：[42]')` 生成 67584 字节 exe，`fib(20)=6765` 正确
