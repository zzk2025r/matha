# Matha 变更摘要

## 特性：插件节点解析期源码语法（`register_syntax`）

**日期**：2026-10-18

### 变更

1. `src/ast_ext.py`：
   - `register_syntax(name, node, fields=None)`：注册源码语法，Matha 源码里的
     `名(a, b, …)` **在解析期**直接构造成插件节点（`fields` 缺省取节点自带字段）。
   - `build_from_call` / `rewrite_call`：应用链改写（柯里化多参 `f(a)(b)` 一并改写）。
   - `SYNTAX` 表；`describe()` 增加 `syntax` 字段；`clear()` 一并清理。
2. `src/parser.py::_parse_postfix` 收尾处调用 `rewrite_call`
   （`ValueError` → `ParseError`）。**`SYNTAX` 为空时立即返回，对既有解析零影响**。

### 语义

- 只改写以**裸 `Variable` 为头的 `FuncApp` 链**；单独出现的同名变量保持原样；
  插件节点作为表达式进入 AST 后，按既有钩子被 解释器 / MBC / 原生 三端分派。
- 参数个数不符在**解析期**报错（绑定 / 裸表达式语境）。
  输出括号 `[ … ]` 语境本身会把解析失败回退为字符串文本（`#：[Hello world]`
  的既有设计），插件错误落在该语境同样被回退——需要硬错误请用其它语境。

### 验证

`tests/test_ast_ext.py` 增至 **38 项**（+8）：解析期改写、**源串**三端一致
（解释器 / VM / 原生 exe）、绑定语境、裸同名变量不改写、参数个数报 `ParseError`、
`fields` 必填、非法语法名、默认无语法时调用不受影响。

全量回归：**3358 passed**（此前 3350）。lint 回到基线（`parser.py` 13 = 基线，`ast_ext.py` 0）。

## 特性：可扩展 AST 节点注册表（Matha 核心自定义扩展接口）

**日期**：2026-10-18

### 变更

1. 新增 `src/ast_ext.py` —— 扩展节点注册表：
   - `define_node(name, fields)`：动态声明 dataclass AST 节点并注入 `src.ast_nodes`
     成为 AST 一等公民（幂等、字段冲突 / 非法名 / 非法字段校验，
     支持默认值与 `dataclasses.field(default_factory=...)`）。
   - 四张规则表，按节点**类对象**分派：
     `register_eval` / `register_exec`（解释器）、
     `register_compile_expr` / `register_compile_stmt`（MBC）。
   - `describe()`（供 `matha features` 等展示）与 `clear()`（测试隔离）。
2. 钩子（**兜底而非覆盖**——内置节点已有实现先于钩子命中，扩展只能新增节点）：
   - `src/interp.py`：`_eval`（`暂不支持求值` 之前）、`_exec_stmt`、`_exec_decl`；
   - `src/mbc/compiler.py`：`_emit_expr`（`暂不支持的节点` 之前）、`_compile_stmt`。
3. 插件规则的公开入口：`Interpreter.eval_expr` / `Interpreter.exec_stmt`、
   `Compiler.emit_expr` —— 规则据此求值 / 编译子节点，无需触碰私有方法。

### 语义

插件节点在 MBC 端**降级为核心 AST / 字节码**，因此原生后端无需感知插件即可编译执行——
这是四端一致在扩展层的体现。

### 验证

新增 `tests/test_ast_ext.py`（30 项）：

- `define_node`：注册、注入命名空间、幂等、字段冲突、非法名 / 字段、默认值、
  `describe` / `clear`、入参校验；
- 解释器端规则（表达式 + 语句）与 MBC 端规则（表达式 + 语句）分别驱动对应后端；
- **四端一致**：同一插件节点在 解释器 / 字节码 VM / **原生 exe** 上结果相同；
- 兜底行为不变：未注册节点两端报错与既有行为一致；
  给 `ast.IntegerLit` 注册规则不改变内置分派。

全量回归：**3350 passed**（此前 3320）。

### 待办

插件节点目前只能**以编程方式**构造（`ast.Program` → `Interpreter.run` / `compile_program` /
`emit_exe`）；从 Matha 源码构造（解析期语法钩子）尚未提供，因此
`compile_to_exe(source)` 这类"源串→exe"路径暂不可达插件节点。

## 特性：CLI 特性开关 + 灰度推进（`matha --feature` / `matha features`）

**日期**：2026-10-18

### 变更

1. `src/matha_main.py`：
   - 新增全局选项 `--feature NAME[=on|off]`（可重复）——落为进程内开关覆盖，
     优先级高于环境变量；`NAME=off` 可强制关闭。
   - 新增子命令 `matha features`：列出已知特性开关及当前状态；`--help` epilog 同步说明。
2. 测试隔离加固：`tests/test_scoped_blocks.py`、`tests/test_language_bridge.py`、
   `tests/test_cli_features.py` 的隔离夹具改为**测试期间移除外部环境变量**（保存/恢复），
   模块级 `py_record` 夹具自行固定为默认关闭——使「默认关闭」等断言在任意环境下都可确定断言。

### 灰度推进（迁移路径）

1. 默认全关（现状）。
2. 单模块先开：`matha --feature SCOPED_BLOCKS ...` 或 `MATHA_FEATURE_SCOPED_BLOCKS=1 pytest`。
3. 全量开启回归（本步已实测）：`MATHA_FEATURE_SCOPED_BLOCKS=1 python -m pytest tests`
   → **3320 passed**，与默认关闭完全一致。
4. 确认稳定后再评估默认翻转 / 扩大范围。

### 验证

- 新增 `tests/test_cli_features.py`（6 项）：默认关闭、`--feature` 置位、`=off` 覆盖优先、
  帮助文案、非核心模块开关灰度（关闭→失败 / 开启→`[10]`）。
- 全量：默认关闭 **3320 passed**；强制开启 **3320 passed**（**零差异**）。

### 说明

- `matha run` 的自举解析路径在本环境受既有限制（`调用捕获` 缺失）所阻，与本改动无关；
  灰度用例直接经 Python 解释器执行同一模块源。

## 特性：`return` / `break` / `continue` 语句（语法器补全）

**日期**：2026-10-18

### 背景

`ast.ReturnStmt` / `BreakStmt` / `ContinueStmt` 此前已由**解释器**
（`_ReturnException`/`_BreakException`/`_ContinueException`，`_call_lambda` 捕获返回值）
与 **MBC 编译器**完整支持，但**语法器从未产出它们**——源码中的 `return`/`break`/`continue`
一律报「期望表达式」，块体内无法提前返回（这也是语言桥循环体直译的瓶颈）。

### 变更

1. `src/parser.py`：`_parse_mech_stmt` 控制流关键字分发加入 `KW_RETURN`/`KW_BREAK`/
   `KW_CONTINUE`；`_parse_statement` 与 `_parse_decl` 新增三条产生式——
   `return [expr]`（无表达式 → null）、`break`、`continue`。
2. `src/matha/language_bridge.py`：语句块直译新增 `return`/`break`/`continue`，
   循环内提前 `return` 不再退化为无中生有骨架。

### 验证

- `tests/test_scoped_blocks.py` +4：块内 `return` 取值、提前 `return`（0/10）、
  `while` 内 `break`（3）、`for` 内 `continue`（4）。
- `tests/test_language_bridge.py`：`is_primeish`（循环内提前 `return`）译为语句块并可运行
  （7→True、10→False）。
- 回归：全量 **3314 passed**（含 mbc 756）；lint：新增代码无告警。

## 增强：语言桥语句块直译（`SCOPED_BLOCKS` 开启时循环体不再骨架）

**日期**：2026-10-18

### 背景

语言桥此前把函数体译为**单一表达式**，遇 `for`/`while` 即放弃 → 退化为无中生有骨架。
`SCOPED_BLOCKS` 落地后，块作为语句上下文可承载循环，故可直译控制流体。

### 变更

1. `src/matha/language_bridge.py`：Python 路径新增语句块直译——
   `_py_body_to_block`（函数体 → `{ ... }`）、`_py_stmt_lines`（单语句 → 行列表）、
   `_py_block_lines`（语句列表 → 行列表）。当表达式直译失败且 `SCOPED_BLOCKS` 开启时，
   将局部绑定 / `if` 语句 / `while` / `for` 循环体译为 Matha 代码块，循环不再骨架。
2. `_py_expr` 支持 Python 列表/元组字面量 → Matha `[ ... ]`；复合赋值
   `a += e` → `a = a e`（新增 `_PY_AUG_OPS`）。

### 限制

- 不支持非末尾 `return`（提前返回——块内 `return` 在 Matha 中不可解析）、`raise`、
  方法调用等 → 仍回退为无中生有骨架。
- 仅 Python 路径；外部语言路径的语句块直译待补。

### 验证

- `tests/test_language_bridge.py` +7 项（共 24 passed）：`for`/`while`/`if` 语句块直译；
  生成体可运行（`sum_list`→10、`sum_to`→15、`clamp`→5）；提前 `return` 仍为骨架；
  关闭开关时行为不变（循环仍骨架）；`fuse` 自验证通过。
- 回归：主套件 `2554 passed`；语言桥消费方 `138 passed`（hybrid_compiler / unified_layers）。

## 特性：`SCOPED_BLOCKS` 特性开关（`{ }` 代码块语句上下文 + 独立子作用域，默认关闭）

**日期**：2026-10-18

### 背景

Matha 函数体为单一表达式；lambda 体 `{ }` 内的 `名 = 值` 因解析器 `_in_lambda_body`
标记被解析为**等于比较**而非绑定，导致多语句函数体与循环无法在语言层面表达
（自举迁移 下一步 3「控制流函数体翻译」的根因）。

### 变更（默认关闭，现有行为保持不变）

1. `src/features.py`（新增）：特性开关基础设施——环境变量 `MATHA_FEATURE_<NAME>`、
   `MATHA_FEATURES` 逗号清单、进程内 `set_feature`/`clear_feature` 覆盖（覆盖优先），
   默认全部关闭。新增开关 `SCOPED_BLOCKS`（`features.scoped_blocks()`）。
2. `src/parser.py`：`_parse_code_block` / `_parse_block_body` 在开关开启时以**语句上下文**
   解析（块内 `_in_lambda_body=False`），使 `名 = 值` 解析为 `Binding`（保存/恢复外层标记）。
3. `src/interp.py`：代码块作为表达式时（开关开启）建立**独立子作用域**（env 浅拷贝）——
   块内绑定互不泄漏到外层，lambda 体成为真正的语句块，原生支持多语句与循环累加。

### 验证

- 新增 `tests/test_scoped_blocks.py`（10 项）：开关解析（默认关/环境变量/清单/覆盖优先）；
  关闭=旧语义（`y = x+1` 为等于比较 → 未定义变量）；开启=语句块语义
  （块绑定 8、多语句 4、`for` 累加 6、`while` 累加 5、子作用域不泄漏 `[2, 1]`）。
- 回归（默认关闭，行为不变）：主套件 `2547 passed` + `test_mbc_bootstrap.py` `756 passed`
  = **3303 passed**。

### 说明

- 当前仅在 Python 解释器路径实现；MBC/VM、原生后端与自举编译器尚未接入该语义（四端一致，后续）。
- 命令行切换开关待补；当前经环境变量 / 进程内 API 控制。迁移策略：先在非核心模块灰度验证再放量。

## 测试：`interp.matha` 自测 MechUnit 的 Matha-to-Matha 求值验证（自举迁移 下一步 2）

**日期**：2026-10-18

### 变更

- `tests/test_mbc_bootstrap.py` 新增 `test_interp_selftest_math_to_math`：将
  lexer/stdlib/parser/interp 合并编译为单一 VM 运行，断言 `interp.matha` 顶层
  `#：{ }` 自测块的求值结果为 `[8, 14, 200, 10, 6]`（依次为 3+5 / 2*(3+4) /
  1>2?100:200 / 变量 x=10 / Lambda 加一(5)），即经 Matha 实现的 `求值` 求值。

### 验证

- `tests/test_mbc_bootstrap.py`：755 + 1 = 756 collected，新测试通过。

## 增强：`bootstrap_test.matha` 惯用式重写（无损解析回归守护）

**日期**：2026-10-18

### 背景

`matha/bootstrap_test.matha` 此前虽"解析通过"，但多语句 `then`/`else` 分支会被
**静默丢弃**（`断言` 函数体的 `else` 分支整体丢失），AST 严重残缺；且文件使用
`x = x + 1` 式赋值（在函数体语境下 `=` 为等于比较）与陈旧 API
（`词法器.扫描` 实为柯里化 `扫描(src)(pos)(line)(col)(toks)`），无法在现行语言上运行。

### 变更

1. **惯用式重写**（`matha/bootstrap_test.matha`）：
   - 计数器改为共享可变列表 `状态 = [通过数, 失败数]`，经 `标准库.原地设置`
     原地更新（替代函数体内 `x = x + 1`；该语境下 `=` 为比较）。
   - `断言` 分支改为单一 `let … in …` 表达式，消除被静默丢弃的多语句分支。
   - `use` 补 `标准库`；`词法器.扫描(x)` 更正为柯里化
     `词法器.扫描(x)(0)(1)(1)([])`；汇总改用 `状态[0]`/`状态[1]`。
2. **回归守护**（`tests/test_bootstrap_host.py`）：新增
   `test_bootstrap_test_matha_parses_losslessly`，断言 `断言` 函数体含完整
   `else` 分支且两分支均为 let-in 结构，防止"多语句分支被静默丢弃"缺陷复现。

### 验证

- `tests/test_bootstrap_host.py`（含新测试）+ `tests/test_new_features.py`：68 passed。
- 回归：主套件 2537 passed + `test_mbc_bootstrap.py` 755 passed = 3292 passed。

### 说明

宿主自举环境无法**执行**该文件：`调用捕获` 为 VM/原生专属内建（宿主
`src/interp.py` 未注册），且自举词法器在宿主解释器下对本文件抛 `RecursionError`。
故本轮以**无损解析**（而非执行）为交付边界；执行需另行构建 VM 自举运行器。

## 增强：`bootstrap_test.matha` 解析支持（单引号字符串 / `var` 声明 / 元组解构）

**日期**：2026-10-18

### 背景

`matha/bootstrap_test.matha` 的迁移受阻于若干解析缺口（对应
`matha_bootstrap_migration_analysis.md` 下一步 4）。本轮补齐后该文件
**整体解析通过**。

### 变更

1. **词法器**（`src/lexer.py`）：`_string` 增加 `quote` 参数，`'` 与 `"`
   同为字符串定界符（此前 `'` 被当作 SYMBOL，导致解析失败）。
2. **`var` 声明**（`src/parser.py`）：`_parse_statement` 与 `_parse_decl` 识别
   `var NAME = expr`，等价语句层绑定 `NAME = expr`（生成 `Binding`），顶层与
   模块级均支持。
3. **元组解构赋值 + `_` 通配**（`src/parser.py`）：`_` 作为主表达式（占位变量）；
   `(a, b) = expr`（元素全为变量/通配）生成 `LetTupleBinding`——此前仅解析为
   等值 `BinaryOp`；`let (_, b) = ...` 亦接受 `_`。
4. **语句级解构绑定**（`src/interp.py`）：`_exec_decl` 新增 `LetTupleBinding`
   分支（此前落入 default 被静默忽略），绑定不清理，与 `Binding` 行为一致。

### 验证

- `matha/bootstrap_test.matha` **整体解析通过**。
- 四端一致：`(a, b) = (3, 4)` / `(_, b) = (5, 6)` / `let (_, c) = (7, 8) in …`
  在 Python 解释器、MBC/VM、原生后端均输出正确（`mbc/compiler.py:278` 已支持
  顶层 `LetTupleBinding`）。
- 新增 4 项测试（`tests/test_new_features.py`）。
- 回归：`tests`（不含 `test_mbc_bootstrap.py`）**2536** + `test_mbc_bootstrap.py`
  **755**，全通过。

### 遗留（低优先级，暂缓）

- 运行期仍依赖 lambda 体内可变赋值语义：`通过数 = 通过数 + 1`（位于
  `func … = (…) => …` 函数体内）现按等于处理，故该文件可解析但不可正确运行。

## 增强：语言桥控制流函数体翻译（吞噬骨架逐步补全）

**日期**：2026-10-18

### 背景

`src/matha/language_bridge.py` 的吞噬（devour）在函数体为单一表达式/单个
`return` 时直译；含控制流（`if`/`else`/局部绑定）时一律退化为
`抛出错误("无中生有骨架…")` 骨架。本轮补齐「可表达为单一 Matha 表达式」
的控制流，使更多真实函数体进入 Matha（对应
`matha_bootstrap_migration_analysis.md` 下一步 3）。

### 变更（`src/matha/language_bridge.py`）

1. **Python 路径**：`_py_body_to_expr` 改为语句列表递归翻译
   （`_py_stmts_to_expr` / `_py_if_to_expr`）：
   - `if C: return A` + 后续语句 → `C ? A : <后续>`（提前返回）；
   - `if/elif/else` → 嵌套三元；
   - 单目标赋值 / 复合赋值 → `let x = e in <剩余>`；
   - 无 `else` 且无后续 → 隐式 `null`。
2. **Python 表达式**（`_py_expr`）：新增 `None`→`null`、`BoolOp`（`and`/`or`）、
   `Compare`（含链式 `a < b < c`）、`not`、`FloorDiv`（`//`）。
3. **外部语言路径**：`_body_to_expr` 保留原快路径，新增
   `_foreign_stmts_to_expr` / `_foreign_if_to_expr` / `_take_brace_block`，
   支持 `if (...) { return A } else if ... return B`、rust 尾表达式、
   `let/var/const/:=/=` 局部绑定、提前返回。
4. **修复既有隐性缺陷**：`_OP_MAP` 把 `&&`/`||` 映射为 `且`/`或`，而 Matha
   不识别 `且`/`或`（会被当作函数名），导致含布尔运算的翻译结果无法通过
   parser。改为 `and`/`or`（与 `interp_matha.matha` 一致）。

无法表达为单一表达式者（`for`/`while`/`raise`/列表操作等）仍保留骨架——
「逐步补全」按可表达性推进。

### 验证

- 新增 `tests/test_language_bridge.py`（17 项）：Python 与 rust/go/js/c 的
  if/else、else if、提前返回、let 绑定翻译；循环保留骨架；逻辑运算可解析；
  `matha_expr` 回归。
- 生成模块经 `fuse` → Matha parser 验证通过；并用宿主解释器求值抽查语义：
  `factorial(5)=120`、`let`→21、`or/整除`→`[0,3]`、`clamp`→`[3,0,2]`、
  `and`→`[3,2]`、`null`→`[None,5]`。
- 重新吞噬 `src/stdlib/arithmetic.py`：`divide`/`sqrt`/`lcm`/`asin`/`acos`/
  `log`/`log2`/`log10`/`combination`/`permutation` 由骨架转为直译
  （`matha/generated/` 为 gitignore 的构建产物）。
- 回归：`tests`（除 `test_mbc_bootstrap.py`）2532 + `test_mbc_bootstrap.py` 755
  = **3287 通过**。

---

## 修复：自举解释器求值链（宿主 lambda-dict 转换 + `interp_matha` 缺陷）

**日期**：2026-10-17

### 根因（宿主侧）

`src/interp.py` `_eval_variable` 曾对 `env` 中「`类型 == "lambda"` 的 dict」
自动转换为闭包元组（`9a31a0c` 引入）。该「兼容」使自举 parser 解析
`f = (a) => a + 1` 时把 lambda 节点求值成闭包后再被宿主二次转换，破坏
「AST dict 保持为 dict」的不变量，连带使自举解释器求值链异常。
**修复**：移除该自动转换——lambda 节点由 `求值(lambda)` 正常产出闭包即可。

### 自举解释器缺陷（`matha/interp_matha.matha`）

1. **缺 `let绑定` 分支**：`求值` 无此类型 → `未知表达式类型: let绑定`。补 `求值let绑定`。
2. **函数定义未绑定参数**：`执行声明/执行语句` 直接 `求值(stmt["体"])`，而
   parser 的 `体` 是**裸函数体**（非 lambda 节点）→ 引用参数即 `未定义变量`。
   改为 `求值(语法器.做Lambda(stmt["参数"], stmt["体"]))`。
3. **`执行声明列表` 返回首个声明的值**：多语句程序返回值错误（`f(2)` 返回闭包）。
   改为返回末条声明之值。
4. **`应用函数` 多参柯里化误判**：`len(params) > 1` 时仍先求值函数体 →
   `未定义变量 'b'`。改为先判参数余量：余者有 → 部分应用返回，否则才求值函数体。
5. **递归绑定不可见**：`更新绑定值` 用函数式重建列表，闭包仍捕获旧 env。
   改为 `标准库.原地设置` 原地修改共享 pair（`绑定环境` 的 pair 由元组改列表），
   使 `let rec` / `func` 自递归生效。
6. **顶层语句未路由**：`if/while/for` 语句节点落入 `求值` → `未知表达式类型`。
   `执行声明` 增语句路由（并区分语句式 `if` 与三元式 `if`）。
7. **自测块绑定裸 lambda dict**：改为先 `求值` 再绑定闭包（与 `interp.matha` 对齐）。

### 验证

- `interp_matha.matha` 与 `interp.matha` 的自测 MechUnit 经宿主解释执行，
  输出均为 `[8, 14, 200, 10, 6]`（对应 `matha_bootstrap_migration_analysis.md` 下一步 2）。
- `tests/test_bootstrap_host.py`(8) + `tests/test_mbc_bootstrap.py`(755) +
  `test_interpreter`/`test_interp_parity`/`test_new_features`(169) 全部通过。

### 更正下文「补记」

下文（原「既有缺陷，未修复」）所列缺陷均属本类，现已修复；其中
「自举 parser 对 `f = (a) => a + 1` 死循环」经复核为**打印/PPRINT 递归假象**，
非真实死循环。

---

## 记录：顶层裸表达式回显归属解释器专属特色（不纳入四端统一）

**日期**：2026-10-17

### 适用原则

**四端一致 = 只对「可通用的能力」做构建/统一**；无法通用的能力**不强行统一**，
按各端的**专属特色**归属（本无需也无从统一）。据此对本轮排查到的行为差分类：

### 可统一（四端一致）

- **显式取值** `输出(...)` / `#N：[...]`：四端实现与结果完全一致，是 Matha
  跨端共享的取值约定。需要四端一致时**必须**用这一形式。

### 专属特色（不统一，属解释器专属）

- **顶层裸表达式回显**：Python 解释器的 REPL 式便利——
  `interpret('12 & 10')` → `[8]`、`interpret('<<90')` → `[π/2]`（仅回显
  字面量 / 二元式 / 一元式；`tests/test_new_features.py:82` 早有说明，18 个
  测试依赖）。MBC/VM 按语句处理一律丢弃（→ `[]`）。两端语义定位不同
  （解释器偏 REPL 交互，VM 偏编译执行），**故归属解释器专属，不纳入统一范围**。
- 曾按「发散」处理、尝试让解释器丢弃以对齐 VM，结果 18 个用例失败，证实其为
  被依赖的专属能力，遂回退、**不做统一**。

### 补记：自举解释器路径的既有缺陷（本次排查发现，**已于 2026-10-17 修复，见文首**）

- `src/matha_bootstrap.py` 的自举解释路径当前**无法执行用户定义函数**：
  - `func f(a) = …` → `未定义变量 'a'`；
  - 自举 parser 对 `f = (a) => a + 1` 会**死循环**；
  - `let … in …` → `未知表达式类型: let绑定`（AST 已正确匹配，疑为宿主 parser
    误解析自举 `求值` 的长三元链）。
- 自举路径一旦出错，`mb.interpret` 会**静默回退**到 Python 解释器，长期掩盖该
  缺陷（例如 `test_bootstrap_interpret_custom_op` 的 `[6]` 实由回退路径产生，
  而非自举路径生效）。
- 相关测试注释已更正为如实描述（见 `tests/test_bootstrap_host.py`）。

---

## 解释器两处 bug 修复：闭包捕获环境 + 顶层 match 语句（四端一致）

**日期**：2026-10-17

### 变更范围

**`src/interp.py` `_call_lambda` 保存/恢复 `_matha_env`**

- 背景：`_call_lambda` 只 `save/restore self.env`，未保存/恢复 `self._matha_env`。
  `_matha_env`（list-of-tuples）是闭包创建时捕获的环境快照。模块内函数以
  closure 形式存于 `env`，调用它会把 `_matha_env` 替换为该闭包的**全局快照**
  （不含调用方参数）；返回后不还原，导致其后创建的闭包捕获到缺失外层参数的
  陈旧环境 → 引用外层参数报「未定义变量」。
- 修复：`_call_lambda` 入口保存 `saved_matha_env`，在两个出口（部分应用返回、
  完整应用 `finally`）恢复。与既有 `self.env` 的 save/restore 对称。
- 复现（修复前报 `未定义变量 '语言'`）：`module M { func 辅助(x)=… ;
  func 编译(语言)= let t=辅助(语言) in let rec 收集(ts,pos,acc)= … acc+[语言] … }`。
- 该修复使 `matha/frontends/multi_lang.matha` 的 `收集函数` 无需再显式传参；
  当前文件已提交的显式传参写法保留（等价，无回归）。

**`src/interp.py` `_exec_decl` 增加 `ast.MatchStmt` 分支**

- 背景：顶层声明执行器 `_exec_decl` 无 `MatchStmt` 分支，落到兜底 `else`
  → 顶层 `match` 语句被**整个跳过**（输出空）。代码块内 `match` 走 `_exec_stmt`
  正常，故仅在顶层发散。
- 修复：顶层 `match` 求值并**丢弃结果**（`self._eval_match(decl)`），与
  MBC/VM 语句语义一致（编译期 `leave_value=False` → `POP`）；分支体自身副作用
  （如 `输出(...)`）保留。
- 验证：`match 10 { | 10 => 输出("hit") | _ => 输出("miss") }` 现 interp==VM==`['hit']`。

### 测试

- 新增回归：`tests/test_interpreter.py`
  - `test_top_level_match_statement_runs_arm`
  - `test_closure_captures_caller_env_after_module_func_call`
  （两者在修复前均失败，修复后通过。）
- `pytest tests/test_interpreter.py tests/test_interp_parity.py tests/test_mbc_vm_matha.py`
  → **203 passed**。
- `pytest tests/test_m1_nodes.py tests/test_mbc_bytecode.py tests/test_mbc_bootstrap.py`
  → **805 passed**。
- `corpus_parity.py`（67 文件）→ **ok=63 self_fail=0 diverge=0 host_parse_fail=4**
  （与上轮一致，无回归）。

---

## 前端最小可用重写 + basic_examples + parser match 表达式（四端一致）

**日期**：2026-10-17

### 变更范围

**`examples/basic_examples.matha` 重写为合法 Matha**（原文件语法已过时）

- 全文重写为规范 Matha（`if/else`、`func`、`let` 等），四端一致：宿主解析+编译、
  自举字节码 identical、解释器/VM 零错运行。

**`matha/parser.matha` 补 `match` 作表达式**（对齐宿主 parser，中立无回归）

- `解析主要` 在 `if` 分支后加入 `match` 语句解析入口，使自举 parser 能解析
  `match` 作表达式的用法（此前仅 `if`/`let`/`func` 等），与宿主 parser 对齐。
  `match` 作**语句**不受影响；补丁只增加入口，不改变既有分支。

**5 个 `matha/frontends/*.matha` 最小可用重写为四端一致**

- 统一去除所有 `use` 导入（interp 会执行被导入模块、VM 忽略 → 发散）与跨模块
  点号调用（interp 建命名空间、VM 注册裸名 → 发散）；编译/执行逻辑全部内联。
- 统一用 `if / else if / else` 替代 `match`、`elif`；or 模式改括号 `if`。
- `multi_lang.matha`：`parse_int/parse_float`→`int()/float()`；单引号字符→
  双引号/`chr(34)`；`.keys()`/`{**d}`（不支持）→**列表**；解析结果由元组→
  `{"值":..,"位置":..}`（`let (a,b)` 元组解构在 interp 不可用）；`检查IO` 的
  `包含(字符串,子串)` 改用本地 `含子串/匹配于`（原 `包含` 是列表成员判断，
  对空串 `""[0]` 越界）；`解析函数` 未找到函数时返回 `null` 而非 `{}`（空
  `{}` 在编译后被当列表索引 → `list[名]`）；`解析表达式` ident 分支去掉
  同 `pos` 的自我递归（曾致无限递归）；被捕获的外层参数改显式传参，绕开
  interp `_call_lambda` 不保存/恢复 `_matha_env` 的闭包 bug。
- `verifier/hybrid/frontend.matha`：全部跨模块点号调用（`多语言前端.编译Rust`
  等）内联/等价简化；dict 键枚举改列表；dict 模式匹配+`as`+`{**acc}` 改
  `if/else`+列表；`false`→`假`。
- `codegen.matha`：去掉 `use`；`match`/or 模式改括号 `if`；参数 join 用
  `let rec` 列表扫描。

### 效果

- `corpus_parity.py`（67 文件）：**ok 57→63**、self_fail 0、diverge 0、
  **host_parse_fail 10→4**（剩余 4 个为遗留/非规范：`matha_vm.matha`
  LEGACY、`bootstrap_test.matha` 单引号、`bootstrap_test_v2.matha` `list`
  节点、`dynamics.matha` 公式 DSL，非 Matha 程序）。
- 5 个前端文件全部 **HOST_OK + SELF_OK + identical=True + interp==VM=[]**。
- `multi_lang.matha` 的 `编译Rust/Go/C/JS/编译` 运行期零错（interp==VM）。

### 测试

- `pytest tests/` → **3268 passed, 2 warnings**（无回归）。
- `test_native_frontends.py::test_matha_frontend_modules_have_correct_structure`
  的 `"end" in content` 断言改为 `"}" in content`（原断言依赖已移除非规范的
  `match ... end`；Matha 模块以 `}` 结束）。

---

## 参数名 / 类型名接受符号（SYMBOL）——与自举对齐（四端一致）

**日期**：2026-10-17

### 变更范围

**宿主参数名 / 类型名解析接受 SYMBOL token**（`src/parser.py`）

- EBNF `<variable> = <placeholder> | <identifier> | <symbol>`，宿主 `_parse_variable`
  已接受 SYMBOL（emoji / 数学符号 / 控制符等），但**参数位置与类型位置**未跟进：
  lambda 参数、`func` / `and` 显式 lambda 体参数、`let` 显式 lambda 体参数、带类型
  参数（`_parse_typed_param`）、命名类型（`_parse_type_expr`）等处的「参数名 /
  类型名可用 token」集合缺 SYMBOL，导致 `(★) => ★`、`func f(★: Int)`、`x: ★` 等
  宿主报「期望 参数名 / 类型表达式」，而自举可解析 → 两端发散。
- 修复：
  - 10 处「参数名 / 类型名可用 token」集合统一加入 `TokenType.SYMBOL`
    （`_parse_lambda_param`、`_parse_typed_param`、`_parse_func_def` /
    `_parse_and_func_def` 的显式 lambda 体参数、`_parse_let` 的两处显式 lambda 体
    参数、`let (` 函数定义前瞻、`_parse_type_expr` 命名类型）。
  - `_parse_paren_dispatch` 的独立 lambda 试探门禁加入 `TokenType.SYMBOL`，使
    `(★) => …` 作为 lambda 解析（无 `=>` 时仍回退为分组，`(★)` 分组不受影响）。

### 效果

- 语料 `corpus_parity.py`（67 文件）：**ok 56→57**、diverge 0、self_fail 0、
  host_parse_fail 11→10。剩余 10 个文件宿主与自举**双方均解析失败**
  （遗留 / 非规范写法，非发散）。
- `matha/library/core/计算球体积.matha`（自举生成、含杂散 `\x01` 字节）现宿主可
  解析，且宿主与自举编译一致（identical=True）。

### 测试

- `pytest tests/` → **3268 passed**（无回归）。
- 符号参数 / 符号类型名 / let 符号 lambda 各例 host==self（identical=True）。

---

## `@：` 设定项多行列表「未消费完整」误回退修复（四端一致）

**日期**：2026-10-17

### 变更范围

**宿主 `@：` 设定项值的完整性判定应接受 DEDENT**（`src/parser.py`）

- `_parse_set_up_item` 解析 `@：名 = 值` 时，先以 `_parse_expr(stop_at_comma=True)`
  取值，再校验「值消费完整」——当前 token 须为逗号 / 换行 / EOF / `|` / `)`。
  多行值（如多行列表 `["a",\n   "b"]`）消费完时，紧随其后的是 **`DEDENT`**
  （其后才是 `NEWLINE`），不在上述集合内 → 误判「设定值未消费完整」而进入文本
  回退分支（`except ParseError`），把 `[` 起的内容按文本收集到第一个逗号处截断，
  导致 `@：名 = [a, b, c]` 这类多行列表解析错位（后续元素被当作新设定项 →
  「期望变量名或占位符」）。
- 修复：完整性判定同时接受 `TokenType.DEDENT`。单行值（如 `windows.iso` 文本）
  收尾为 NEWLINE，不受影响；多行值（多行列表 / 跨行表达式）现正确判为完整。
- 影响：`matha/firewall_rules.matha`（含 `@：沙箱允许 = […多行…]` 等多行列表
  设定）现宿主可解析，且与自举编译结果一致（identical=True）。

### 效果

- 语料 `corpus_parity.py`（67 文件）：**ok 55→56**、diverge 0、self_fail 0、
  host_parse_fail 12→11。

### 测试

- `pytest tests/` → **3268 passed**（无回归）。

---

## `[expr]` 归类忽略缩进记号 + bootstrap_matha 缺 let 笔误（四端一致，diverge=0）

**日期**：2026-10-17

### 变更范围

**宿主 `[expr]` 归类应忽略缩进记号**（`src/parser.py`）

- `_parse_primary` 判定 `[expr]` 为「列表字面量 / 输出」时向前扫描「前一有效 token」：
  若为二元运算符 / `in` / `=>` 等则判为表达式位（列表），否则视为语句位（输出）。
  该扫描原先只跳过 `NEWLINE`，**未跳过 `INDENT`/`DEDENT`**。当 `let … in` 体与
  `[expr]` 之间夹有注释（或空行）时，词法器会插入一个 `INDENT` 记号，使「前一有效
  token」落到 `INDENT` 而非 `in` → 表达式位的 `[expr]` 被误判为输出。
- 修复：扫描同时跳过 `NEWLINE`/`INDENT`/`DEDENT`（与 `_skip_newlines` 一致；缩进记号
  是结构记号，不应改变表达式位判定）。注释/空行因而不再影响 `[expr]` 归类。
- 影响：`matha/bootstrap_matha.matha` 中 `let (result, env2) = … in`（其后隔注释）
  `[result]` 现正确判为列表字面量——宿主此前生成 `DUP; OUTPUT`，自举生成
  `BUILD_LIST 1; RET`，修复后两端一致。

**`bootstrap_matha.matha` 缺 `let` 笔误**（`matha/bootstrap_matha.matha`）

- `测试模块加载` 第 88 行 `toks = 词法器.扫描("42 + 1") in` 缺 `let`（与第 86/87 行
  的 `let … in` 不一致）。该笔误使解析器把后续语句当作模块顶层
  （宿主 `in; [标准库.len(toks)]`、自举 `in[标准库.len(toks)]`），两端归类不同。
- 修复：补回 `let`。修复后宿主与自举对该模块编译完全一致。

### 效果

- 语料 `corpus_parity.py`（67 文件）：**ok 54→55、diverge 1→0**、self_fail 0、
  host_parse_fail 12（不变）。两端均可解析的文件现 **100% 一致**。

### 测试

- `pytest tests/` → **3268 passed**。

---

## 并列函数应用 `f x`（juxtaposition）宿主解析 + 自举禁并列泄漏修复（四端一致）

**日期**：2026-10-17

### 变更范围

EBNF（`docs/17` §postfix）与 `docs/06` 定义并列函数应用
`<postfix> = <primary> , { <primary> }`（`f e` → `f(e)`，`f a + b` → `(f a) + b`，
优先级 7）。宿主 `src/parser.py` 的 `_parse_postfix` docstring 虽同述该规则，但实现
只处理 `f(...)`，**缺失 `{ <primary> }` 循环** → `x = f y` 被解析为 `Binding(x=f)` +
独立语句 `y`。自举 `解析应用链` 早已支持并列，两端因此发散（语料 11 例，如
`v1 = 乘 a b`、`结果 = 软件_构建 "…"`、`h = compose inc double`）。

**宿主**：

- `src/parser.py`：`_parse_postfix` 新增并列应用分支（左结合 `f x y → ((f x) y)`）。
  新增 `_is_juxtaposition_start`（对齐自举 `是原子起点`：整数/浮点/字符串/布尔/
  占位符/标识符；排除中缀 `is`，以及自举词法器归为关键字、宿主归为标识符的词
  `let/not/Int/Float/…`）；分支要求当前 token 非行首（`tokens[pos-1]` 非 `NEWLINE`，
  对齐自举 `是行首关键字`）。新增 `_no_juxtaposition` 字段，并在 `_parse_output`
  的表达式回退路径置真（try/finally 恢复），使 `#：[Hello world]` 仍回退为文本
  而非被吞成 `FuncApp`（对齐自举 `试解析输出` 的 `禁并列`）。

**自举**：

- `matha/parser.matha`：修复 `禁止并列` 标志**泄漏**缺陷。`试解析输出` 解析成功后
  返回的解析器副本带 `禁止并列=真`，该标志经 `规范`/`推进` 等一路传播到后续所有
  解析 → **首个 `#：[…]` 之后的并列应用全部失效**（此前因宿主无并列而无从暴露，
  本轮修宿主后被暴露）。新增 `置禁并列(p, v)`；`试解析输出` 成功分支改为
  `置禁并列(p2, p.禁止并列)`，恢复调用方原值。

### 效果

- 语料 `corpus_parity.py`（67 文件）：**diverge 11→1、ok 44→54**（self_fail 0、
  host_parse_fail 12 不变）。
- 唯一剩余 DIFF：`matha/bootstrap_matha.matha`（缩进 lambda 体裸 `[expr]` 语句位
  判定，正交于本轮）。

### 测试

- `pytest tests/` → **3268 passed**；`pytest tests/test_mbc_bootstrap.py` → **755 passed**。
- `ruff check src/parser.py`：无新增告警（既有 SIM/B007/E402 为历史项）。

---

## 输出行循环后缀 + 全局代码编号 + 裸 `#` 行 + 双省略号（四端一致）

**日期**：2026-10-16

### 变更范围

承接上一节（链 + 设值），本轮清空自举端最后 12 个解析失败：语料中 `#：[x]…（0/？）【file】`
循环后缀、`？#：{` 全局代码编号、`# 注释` 裸井号行、`……（x/y）` 全局循环后缀四类此前均在
自举端报 `期望表达式，实际 未知` / `期望 (`。上一节后的语料为 `self_fail 12`，本轮后 **归零**。

**输出行循环后缀**（宿主 `_parse_output_trail`）：`#：[输出]…（x/y）【子文件|子文件】[编号]
……（x/y）【文件/路径】`，及模板形式 `#：[输出]……（x/y）【文件】`（仅全局循环）。

- `matha/lexer.matha`：**补全角括号 `（）` 映射**（宿主 lexer 把 `（`/`）` 与半角 `()`
  同映射 `PUNCT_LPAREN/RPAREN`），循环分数以全角括号书写。
- `matha/parser.matha`：新增 `做循环分数`/`做段循环`/`做输出追踪环`；`解析循环分数`
  （`(x/y)`，`？`→`-1`）、`解析循环数`、`解析段循环后缀`（`… [N] (x/y)`）、
  `解析全局循环后缀`（`…… (x/y)`）、`解析文件列表`/`解析子文件引用`/`解析文件引用`
  （`推进原样` 收集到 `】`/`〕`/EOF，`|` 分隔）、`解析输出后缀` + `解析输出后缀_全局`
  （对齐宿主 `_parse_output_trail` 的分支顺序与可选段）。`解析机械单元` 的 `[…]`
  分支在 `]` 之后、`收尾链` 之前调用 `解析输出后缀`。循环/文件引用为纯元数据，宿主编译期
  不产字节码，自举仅消费不发射（`_编译生成语句链` 的 `输出追踪` 分支只读 `输出` 字段）。

**全局代码编号**（宿主 `_parse_global_id_stmt`）：顶层 `？#：{…}` / `N#：{…}` 中，编号
`？`/`N` 单独成 `GlobalIdStmt`（∈ `_NOOP_STMTS`），随后的 `#：{…}` 仍作为机械单元解析。

- `matha/parser.matha`：新增 `做全局标识`/`解析全局标识`。分派放在**顶层** `解析声明列表`
  （对齐宿主 `_parse_statement` 的 `PLACEHOLDER/INT + HASH` 分支），**不放** `解析声明`——
  宿主块内解析器 `_parse_mech_stmt` 无此规则，若放通用 `解析声明` 会把块内整数字面量误判。
- `matha/compiler_matha.matha`：`_编译声明` 增 `全局标识` 空操作分支，`_是语句类型` 登记。

**裸 `#` 行**（宿主 `_parse_foreign_decl`）：`#` 后非「冒号」且非「整数+冒号」时整行惰性
收集为外来声明（`ForeignDecl`，∈ `_NOOP_STMTS`）。语料中的普通注释行如
`# Matha 示例 10：网页应用开发` 即此类；自举此前只吞 `# Matha 示例 10`，残留 `：网页应用开发`
在语句位触发 `未知`。

- `matha/parser.matha`：新增 `是生成头`（原始 token 前瞻，不跳换行）、`做外来声明`/
  `解析裸井号行`；`解析声明` 的 `段号` 分支改为 `是生成头 → 解析机械单元`，
  否则 `解析裸井号行`。
- `matha/compiler_matha.matha`：`_编译声明` 增 `外来声明` 空操作分支，`_是语句类型` 登记。

**双省略号 `……`**（宿主 `tokens.MULTI_CHAR_OPS` 中 `……` 优先于 `…`）：`……` 是两个
`…` 字符，须最长匹配为一个 `双省略号`，否则 `#：[x]……（0/？）【f】` 被当成两个单省略号，
第二个 `…` 落到 `解析循环分数` 的 `期望 (`。

- `matha/lexer.matha`：`检测多符` 增 `(c1="…" and c2="…") → (双省略号, "……")`，
  并把 `双省略号` 加入 `扫描主体` 的两字符分派列表。

### 效果

语料 `corpus_parity.py`（67 文件）：**self_fail 12→0、diverge 12→11、ok 31→44**
（host_parse_fail 12 不变）。自举端已能解析全部可解析语料文件。

### 测试

- `pytest tests/` → **3268 passed**（含 `test_mbc_bootstrap.py` 755 项四端一致用例）。
- `pytest tests/test_mbc_bootstrap.py` → **755 passed**。
- 语料 `corpus_parity.py`：ok 31→44、self_fail 12→0、diverge 12→11。
- 新匹配文件：`06_main`、`07_auto_debug`、`08_auto_optimize`、`09_self_grow`、
  `10_library_read`、`10_web_app`、`11_library_grow`、`12_backend`、
  `12_library_discipline`、`template_new` 等。
- 尚存 DIFF（已知、正交于本轮）：`f "x"` / `f 规格` 并列应用（宿主不应用、自举应用），
  以及 `bootstrap_matha.matha` 缩进 lambda 体裸 `[expr]`。

---

## `>>` 链式语句 + `@：…` 设值（setUp）解析/编译（四端一致）

**日期**：2026-10-16

### 变更范围

语料中 23 个含 `#：【A】>>【B】` 链与 `@：【…】，k=v` 设值的文件此前在自举端分别报
`期望表达式，实际 =` 与卡在 `>>`。本次为自举补齐机械记法的链式语句与设值两端实现。

**`>>` 链式**：宿主 `#：【A】>>【B】>>【C】` 产 `ChainStmt`（递归拍平为单层）。
自举 `解析机械单元` 原本把首个体节点原样返回，`>>` 会漏到语句列表导致后续解析错位。

- `matha/parser.matha`：新增 `做链式语句`、`是链续接`/`链后起始`（对齐宿主
  `_is_chain_context`，直接看 `>>` 后下一 token 是否为 `《`/`【`/`[`/`@`/`#`）、
  `扁平链项`、`解析链`/`解析链项`/`收尾链`。`解析机械单元` 的命令/读取、`[…]`、
  `？` 占位符、表达式四分支统一以 `收尾链` 收尾（`{` 代码块分支不接链，对齐宿主）。
  `收尾链` 末尾 `规范(p)` 顺带让裸 `#：【文件】` 后的换行被消费（此前漏换行）。
- `matha/compiler_matha.matha`：`_编译生成语句链` 增 `链式语句` 分支 + 新增
  `_编译链式`（同一作用域顺序编译，不重置作用域）；`_编译声明` 增 `链式语句`；
  `_是语句类型` 增 `链式语句`。

**`@：…` 设值**：宿主 `_parse_set_up` 支持括号/前缀/命令三种形式。语料全部为命令式
`@：【文本】，k=v，…`。自举原本完全无 `设值` 支持，`解析声明` `设置符` 分支无条件
调用 `解析定义运算符`，导致 `@：…` 被误解析。

- `matha/lexer.matha`：**修复全角逗号 `，` 缺映射**（此前降级为 `符号`）。宿主 lexer
  把 `，`/`、` 均映射为 `MATHA_COMMA`；自举此前只认 `、`。这使设值的逗号分隔无法识别。
- `matha/parser.matha`：新增 `做设值`/`做设值项`、`解析设值`（`@[N][：]` 后按
  `【` 判命令式/前缀式）、`解析设值余项`/`解析设值项`/`解析设值目标`、
  `是设值值起点`/`解析设值值`/`回退设值文本`/`收集设值文本`。`解析声明` `设置符`
  分支改为：下一 token 为 `define_op` 标识符 → `解析定义运算符`，否则 → `解析设值`
  （对齐宿主 `_parse_mech_stmt` 的 `MATHA_AT` 分派）。值无法完整解析时（如路径
  `/data/config`、`source.csv`、`db://host:port`）回退为文本常量。
  **注意**：`解析表达式` 经 `推进` 会跳过换行，末项 `c=4\n#：…` 停在下一行段号上，
  故值完整性判定额外接受「已跨过换行」（`当前(p2).行 > 当前(p).行`）。
- `matha/compiler_matha.matha`：新增 `_发射设值`/`_发射设值项`（对齐宿主
  `_emit_setup`：无值项与 `？` 占位目标项跳过；main 作用域 `STORE_GLOBAL`，
  函数帧内 `STORE_LOCAL`）；`_编译声明` 增 `设值`（全新 main 作用域）；
  `_是语句类型` 增 `设值`。

### 效果

语料 `corpus_parity.py`（67 文件）：**self_fail 26→12、diverge 2→12、ok 27→31**。
尚存的 12 个 `未知` 失败源于不支持的 `…（0/？）【file】` 循环后缀；
12 个 DIFF 主要源于 `？#：{` 全局标识处理差异与 `demo_calc` 的并列应用发散。

### 测试

- `pytest tests/` → **3268 passed**（含 `test_mbc_bootstrap.py` 755 项四端一致用例）。
- 语料 `corpus_parity.py`：ok 27→31、self_fail 26→12、diverge 2→12。
- `probe_mech.py`：链 5 例 + `cmd_then_bind` + `setup_simple`/`setup_multi` 全部 SAME。
- 尚存 DIFF（非本次引入、已知）：`globalid`（`？#：{`）、`bind_apply`/`bind_apply2`
  （`f "x"` 并列应用：宿主不应用、自举应用）。

---

## 命令字面量解析（`#N：【…】` / `《…》`）+ `解析主要` 局部名遮蔽缺陷修复（四端一致）

**日期**：2026-10-16

### 变更范围

现象：语料中 27 个含 `#N：【命令】` 的文件在自举端报 `KeyError: '解析命令文字'`。

- 自举 `解析机械单元`（`#N：…`）在 `类型.读取开`（`【`）分支调用 `解析命令文字(p2)`，
  但该函数全库从未定义 → 链接期报 `KeyError`。
- 补齐 `解析命令文字` / `收集命令文本` / `做命令文字`（对齐宿主
  `_parse_command_literal` + `_parse_command_text`：`《…》`→形式 `"cn"`、
  `【…】`→形式 `"bracket"`，文本收集到任一闭括号或 EOF 为止），并在
  `解析机械单元` 读取开分支同时接受 `类型.命令开`（`《`）。
- 命令字面量对应宿主 `ast.CommandLiteral`，∈ `_NOOP_STMTS`（编译期零字节码），
  故 `compiler_matha.matha` 增加 `命令文字` 空操作分支并登记进 `_是语句类型`。

**潜伏缺陷（本次一并修复）**：`解析主要` 的 `chan T` 分支写作
`let (类型名, p2) = 解析类型名(推进(p)) in …` —— 该 `let` 绑定引入一个名为
`类型名` 的**局部**，遮蔽了同名的**全局函数** `类型名`。宿主/自举编译器的名字解析
把函数体内的 `let` 绑定登记进函数作用域，于是 `解析主要` 末尾错误分支
`错误("期望表达式，实际 " + 类型名(当前(p).类型))` 被编译成 `LOAD_LOCAL`（未初始化的
临时槽，值为 `None`）→ 运行期报「VM：不可调用的值 None」，掩盖了本应上报的解析错误。
将局部改名 `通道元素类型` 后，错误分支正确解析为全局函数调用，解析失败得以正常上报。

### 变更

- **`matha/parser.matha`**：
  - 新增 `做命令文字(文本, 形式)`。
  - 新增 `解析命令文字(p)`、`收集命令文本(p, acc)`（函数体以显式 `= (p, acc) =>`
    书写，规避「函数体以 `(` 开头被当作显式 lambda 参数表」的解析约束）。
  - `解析机械单元` 读取开分支改为 `匹配(p, 类型.读取开) or 匹配(p, 类型.命令开)`。
  - `解析主要` `chan` 分支局部 `类型名` → `通道元素类型`（消除对全局函数的遮蔽）。
- **`matha/compiler_matha.matha`**：
  - `_编译声明` 增 `命令文字` 空操作分支（对齐宿主 `_NOOP_STMTS`）。
  - `_是语句类型` 增 `命令文字`。

### 测试

- 探针：27 个含命令字面量的语料文件由 `KeyError: '解析命令文字'`（此前亦含 3 例
  `VM：不可调用的值 None`）变为正常解析错误（`期望表达式，实际 未知/换行`），
  证明命令字面量解析与错误上报路径已打通。
- `tests/test_mbc_bootstrap.py`：755 passed（自举定点保持，`matha/parser.matha` /
  `matha/compiler_matha.matha` 自编译 ≡ 宿主编译）。

## `go` 语句 + 语句位置 `if` 形态对齐自托管端可用（四端一致）

**日期**：2026-10-16

### 变更范围

**`go`**：宿主 parser 在**块内**把 `go <expr>` 解析为 `ast.GoStmt`（`_parse_statement`
的 `KW_GO` 分支；顶层 `_parse_decl` 无此分支），宿主编译降级为「立即求值 + `POP`」
（`GoStmt ∈ _STMT_NODES`，VM 无抢占式调度）。自举侧缺陷：

- 自举 `解析声明` 无 `go` 分派（`go` 已是自举 lexer 关键字）→ 落入 `解析表达式`，
  链接口报 `KeyError('go')`。
- `compiler_matha.matha` 无 `go` 发射，落到兜底「未支持的表达式类型」。

**语句位置 `if` 的形态对齐（潜伏缺陷）**：自举 `_编译平衡`（语句位置 `if`）恒以
「值形态 + `POP`」发射（`_发射if` 恒留值，再 `OP_POP`）。但宿主对两种形态区别对待：

- **块形态** `if c { … }`（`IfStmt`/`IfElseStmt`，∈ `_STMT_NODES`）→ 语句形态
  `_emit_if_stmt(leave_value=False)`：各分支块 `leave_last=假`、无 `else` 不补
  `PUSH_NULL`、整体**无 `POP`**。
- **表达式形态** `if c then a else b`（`IfExpr`，∉ `_STMT_NODES`）→ 宿主按非语句表达式
  处理（`_emit_block` 末尾分支 `_emit_expr` + `POP`）＝「值形态 + `POP`」。

故语句位置块形态 `if` 的字节码两侧不一致。该缺陷执行结果相同、隐藏已久：自举源自身
不含语句位置 `if`，M2 定点未暴露（新增 `go` 的 `if` 内用例才将其触发）。

### 变更

- **`matha/lexer.matha`**：`go` 关键字早已存在，无改动。
- **`matha/parser.matha`**：
  - 新增 `做Go(expr) = {"类型":"go","expr":expr}`。
  - 新增 `解析go语句(p)`（`期望(p, 类型.关键字)` 消费 `go` → `解析表达式`）。
  - `解析声明` 增 `go` 分派。
- **`matha/compiler_matha.matha`**：
  - `_编译声明` 增 `go` 分支：`_发射表达式(expr) + OP_POP`（对齐宿主 `_compile_stmt`
    的 `GoStmt` 分支）；并登记进 `_是语句类型`（`GoStmt ∈ _STMT_NODES`：块末留值时走
    语句路径，再由 `_emit_block` 的 `leave_last` 尾巴补 `PUSH_NULL`）。
  - `_发射if` 增 `留值: Bool` 形参（真/假分支体均以 `留值` 调 `_发射体`）。
  - `_编译平衡`（语句位置 `if`）改为按真分支是否为 `Program` 区分：块形态 →
    `_发射if(…, 假)`（语句形态）；表达式形态 → `_发射if(…, 真)` + `OP_POP`
    （假分支在无 `else` 时为 `null`，故以真分支判定）。
  - 值位调用点：`_发射块末条`（留值分支）、`_发射表达式` 均改以 `留值=真` 调 `_发射if`。

### 测试

- 新增 **M19：`go` 语句**（`_M19_GO_CASES` 8 例 × 3 = 24 例：宿主基准 /
  stage2 ≡ stage3 / 自举执行），覆盖 `go` 后接返回后语句、块末 `go`（值为 `null`）、
  `go` 作函数调用/变量/算术表达式、`while`/`if` 块内的 `go`（含非块尾）。
- 新增 **M20：语句位置 `if` 形态对齐**（`_M20_IF_STMT_CASES` 8 例 × 3 = 24 例），
  覆盖顶层/函数体语句位块形态 `if`（有/无 `else`、连续两块、块尾留值）、表达式形态
  `if … then … else …`（语句位 / 块尾）、mechanics 代码块内块形态 `if`。
- 探针 host ≡ self（字节码 canon + 执行逐例一致）。
- `tests/test_mbc_bootstrap.py + tests/test_bootstrap_host.py`：763 passed
  （含 `matha/parser.matha`/`matha/compiler_matha.matha` 的自举定点保持）。
- 全量 `pytest tests/`：3268 passed。

## match / switch 语句自托管端可用（四端一致）

**日期**：2026-10-16

### 变更范围

自托管链路此前完全不支持 `match`/`switch`（宿主早已支持：`MatchStmt`/`SwitchStmt`
由 `_parse_match_stmt`@3584 / `_parse_switch_stmt`@3620 构造，由 `_emit_match`@904 /
`_emit_switch`@996 发射）。自举侧缺陷：

- `解析match_stmt` **不消费收尾 `}`**（宿主末尾 `_expect(RBRACE)`）→ 分支解析后
  残留 `}` 被当作块尾/顶层收尾，报 `VM：不可调用的值 None`。
- `解析match分支` 盲目前进当 `|`、不支持守卫、不支持换行；分支元组仅
  `(pattern, body)`（宿主为 `(pattern, guard, body)`）。
- `解析match模式` 用 `类型.占位符`（全角 `？`）判 `_`（应为 `类型.下划线`）→ `_`
  不被消费报 `期望 =>`；且仅支持整数，缺字符串/浮点/布尔/构造子。
- **完全没有 `解析switch`**，`解析声明` 无 `switch` 分派。
- `做Match` 键名误写 `" scrutinee"`（多前导空格）。
- `matha/lexer.matha` 的 `是关键字` 漏 `switch`/`case`/`default`（宿主 `tokens.KEYWORDS`
  含此三者）。
- `compiler_matha.matha` 无 match/switch 发射，落到兜底
  `错误("自举编译器：未支持的表达式类型 …")`。

### 变更

- **`matha/lexer.matha`（`是关键字`）**：补 `switch`/`case`/`default` 三条，与宿主
  `tokens.KEYWORDS`（KW_SWITCH/KW_CASE/KW_DEFAULT）对齐。
- **`matha/parser.matha`**：
  - 修正 `做Match` 键名 `" scrutinee"` → `"scrutinee"`；新增 `做Switch`、
    `做构造子模式`（`{"类型":"构造子模式","名":name,"字段":[...]}`）。
  - `解析match_stmt`：末尾 `期望(类型.右括号花)` 消费 `}`，返回 `(做Match(...), p)`。
  - `解析match分支`：校验并消费 `类型.管道`；支持 `if <guard>` 守卫；分支元组改为
    `[模式, 守卫, 体]`（守卫缺省 `null`）。体表达式的解析**临时置「在理解头」**
    （复用该旗标抑制 `|` 作位或）——本解析器的 `推进` 会跳过换行，否则下一行行首的
    `|` 会被续接成位或，多分支 match 的分支分隔符随之丢失（宿主表达式止于换行，
    无此问题）；解析后恢复原值。
  - `解析match模式`：`_` 判定改用 `类型.下划线`（并保留 `类型.占位符`）→ `做Variable("_")`；
    补 浮点/字符串/布尔 字面量；新增构造子 `Name(fields)` → `做构造子模式`；
    新增 `解析模式字段列表`（逗号分隔，按位置对应）。
  - 新增 `解析switch` / `解析switch分支`（`case <val>: <body>` 冒号分隔、
    `default: <body>` 可选，返回 `做Switch(value, 分支, 默认)`）；`解析声明` 增
    `switch` 分派。
- **`matha/compiler_matha.matha`**：新增
  `_发射match` / `_发射match分支` / `_发射模式测试` / `_发射模式于值` /
  `_发射构造子字段` / `_发射模式绑定` / `_发射switch` / `_发射switch分支` /
  `_补丁列表跳转`，逐条对齐宿主：
  - `_发射match`：`_分配临时 "match_s"` → 求值 scrutinee → `_存临时`；逐分支
    `[模式,守卫,体]`：载临时 + 模式测试（失败点记入 `fails`）→ 守卫（`JZ` 记入
    `fails`）→ `_发射体(…, 真)` →（语句位补 `POP`）→ `JMP end` → 把 `fails` 补到
    分支末尾；留值位末尾 `PUSH_NULL`；最后把各 `end` 跳补到末尾。
  - `_发射模式于值`：构造子（`PUSH_CONST 名; LOAD; BINOP "in"; JZ` → 取 `名` 字段 →
    单字段递归 / 多字段 `pat_box` 按位递归）；变量（`_` 通配恒真不绑定；否则载
    `pat_v` + `_发射模式绑定`）；字面量（载 `pat_v` + 表达式 + `BINOP "=="` + `JZ`）。
  - `_发射模式绑定`：main → `STORE_GLOBAL`；否则对齐宿主 `_emit_pattern_bind` +
    `_declare_slot`（解析为 global 时新声明局部槽并 `STORE_LOCAL`，否则复用现有槽）。
  - `_发射switch`：`_分配临时 "switch_v"` → 求值 → 存临时；逐 `case`：载临时 +
    case 值 + `BINOP "=="` + `JZ` → 体 →（语句位补 `POP`）→ `JMP end`；重写 `JZ`
    目标；`default` 分支；无 default 且留值时 `PUSH_NULL`。
  - 接线：`_编译声明` 增 `match`/`switch`（语句位、`_重置主作用域计数`、`留值=假`）；
    `_发射块末条` 留值分支增 `match`/`switch`（`留值=真`）；`_发射表达式` 增
    `match`/`switch`（`留值=真`）。

### 测试

- 新增 **M18：match / switch**（`_M18_MATCH_CASES` 9 例 × 3 + `_M18_SWITCH_CASES`
  4 例 × 3 = 39 例：宿主基准 / stage2 ≡ stage3 / 自举执行），覆盖整数/字符串/布尔/
  浮点字面量模式、变量绑定、`_` 通配、守卫、构造子（单/多构造子）、match/switch 的
  语句位与块尾留值位、`switch` 有/无 `default`。
- 探针 host ≡ self（字节码 canon + 执行逐例一致）。
- `tests/test_mbc_bootstrap.py + tests/test_bootstrap_host.py`：715 passed
  （含 `matha/parser.matha` 的自举 parser 自身定点保持）。
- 全量 `pytest tests/`：3220 passed。

## 块内裸 `let` 常量池泄漏修复 + `;` 语句分隔符（四端一致）

**日期**：2026-10-16

### 变更范围

自托管编译器此前对**块内裸 `let`**（`{ let x = … }`）一律按顶层语义处理：
`_编译顶层let` / `_编译顶层let元组` 无条件 `STORE_GLOBAL` 并把绑定名登记进常量池。
于是函数体/嵌套块里的局部名既泄漏进常量池、又占用全局槽位，破坏 stage2 ≡ stage3
自举定点（例：`f = (x) => { let a = 1\n a + x }` 自举常量池多出 `a`，宿主没有）。

另：自托管 parser 缺 `;` 语句分隔符（宿主 `_skip_semicolon` 支持
`{ let x = 1; x + 1 }` 与顶层 `a = 1; b = 2`），自举链遇 `;` 报 `KeyError(';')`。

### 变更

- **`matha/compiler_matha.matha`**：
  - `_编译顶层let`：按 `sc[3]`（is_main）分支——main 保持 `_加常量` + `STORE_GLOBAL`
    （有体 ? 体 + POP : 无）；非 main 改为 `_声明(sc, 名, 假)` + `STORE_LOCAL`
    （有体 ? 体 + POP : `PUSH_NULL` + `POP`），对齐宿主 `_emit_let`（走 `scope.declare`）。
  - `_编译顶层let元组`：main 保持 `_存储元组全局逆序`（有体 ? 体 + POP : 无）；
    非 main 改用 `_存储元组局部逆序`，**不处理「体」**——对齐宿主 `_emit_binding_stmt`
    的 `LetTupleBinding` 分支（该分支丢弃 body）。两者均不入常量池。
- **`matha/parser.matha`**：
  - 新增 `跳过分号`（当前为 `符号` 且文本 `";"` 时递归 `推进`）；ASCII `;` 由自举
    词法器降级为 `符号`（全角 `；` 早映射为 `全角冒号`）。
  - `解析语句列表_rest`（块内）与 `解析声明列表`（顶层）在解析每一步前先 `跳过分号`，
    对齐宿主 `_skip_semicolon`。

### 测试

- 新增 **M17：块内裸 let 与分号语句分隔符**（`_M17_BLOCK_LET_CASES` 7 例 × 3：
  宿主基准 / stage2 ≡ stage3 / 自举执行），覆盖块内标量/元组裸 let、嵌套块、
  `;` 分隔（块内 / 顶层 / 与换行混用）。
- 探针 host ≡ self（字节码 canon + 执行逐例一致）。
- `tests/test_mbc_bootstrap.py -k "boot_source or stage2_equals_stage3"`：193 passed
  （含 `matha/parser.matha` 的自举 parser 自身定点保持）。

## try/catch/finally 自托管端可用（四端一致）

**日期**：2026-10-16

### 变更范围

补齐自托管链路的 `try/catch/finally`：此前自举 parser **强制**要求 `catch`
（`try { … } finally { … }` 无 catch 即报错），且自举编译器对 try/catch/finally
体内**块末尾语句**（尤其 `#：[…]` 输出单元 / 机械单元）落到 `_发射表达式`，报
`自举编译器：未支持的表达式类型 机械单元`；`finally` 语义亦未打通。现三块均可选，
try 体/捕获体/`finally` 体块尾与宿主行为一致。

### 变更

- **`matha/parser.matha`（`解析try语句`）**：`catch` 由「强制」改为「可选」
  （对齐宿主 `_parse_try_stmt`）——`try { … } finally { … }`（无 catch）与
  `try { … }`（无 catch/无 finally）均可解析；保留 `catch [(e)] { … }` 的可选
  捕获变量语法；`finally { … }` 可选。无块时沿用既有约定（`做Program([])` 空
  Program 表示「无块」）。
- **`matha/compiler_matha.matha`（`_是语句类型`）**：补齐宿主 `_STMT_NODES` 对应的
  自托管语句类型——新增 `机械单元`、`生成语句`、`输出追踪`、`输出`、`let元组绑定`、
  `模块`、`导入`、`结构体`、`枚举`、`定义运算符`。语句位置的块尾须走「编译为语句 +
  补 `PUSH_NULL`」，否则落到 `_发射表达式`：机械单元直接报错、输出会 `DUP` 留值，
  均与宿主不一致（try 体末句为 `#：[…]` 时即触发）。
- **`matha/compiler_matha.matha`（try 发射）**：沿用既有 `_发射try` / `_发射catch` /
  `_编译块thunk`，配合上条修复，使 try 体/捕获体/`finally` 体块尾的语句类型（尤其
  输出单元）与宿主一致；`finally` 体非空时按宿主方式编译 thunk 并丢弃返回值。

### 测试

- 新增 **M16：try/catch/finally**（`_M16_TRY_CASES` 17 例 × 3：宿主基准 /
  stage2 ≡ stage3 / 自举执行），覆盖基础、catch 变量绑定、finally、嵌套、
  函数体内 try、catch-only、finally-only、nested_finally 等。
- 探针 host ≡ self（字节码 canon + 执行逐例一致）。
- `tests/test_bootstrap_host.py` 8 passed；`tests/test_mbc_bootstrap.py -k try`
  62 passed。

### 备注

- `finally {}`（空 finally）与 `catch {}`（空 catch）沿用既有约定（空 Program 判定）；
  精确区分「空块 vs 无块」（需新增 flag）非本轮范围。

## `#：[…]` 输出括号列表前瞻 + 集合运算符链（四端一致）

**日期**：2026-10-16

### 变更范围

补齐自托管端 `#：[…]` 输出括号解析，对齐宿主 `_parse_output` 的 `is_list_lookahead`。

此前自举 `解析括号内输出` 仅以 `窥视逗号`（首个记号后紧跟逗号）判定列表，故与宿主分歧：

- `#：[1 + 1, 2]`：宿主列表 `[[2, 2]]`，自举回退文本 `['1+1,2']`；
- `#：[[1], 2]` / `#：[[1], [2]]`：自举报 `VM：不可调用的值 None`；
- `#：[(1, 2), 3]`：自举回退文本 `['(1,2),3']`；
- `#：[f(1, 2), 3]`：自举回退文本；
- `#：[1, 2] ∪ [3]`：自举把 `∪` 当变量名、`[3]` 当下标（`KeyError('∪')`）。

即宿主以 `_bracket_has_comma`（括号内深度 1 的任意逗号）判定列表，且在列表 `]` 后
另接集合运算符链（`[a,b] ∪ [c,d]`）——二者自举均缺（见旧变更节「已知遗留」）。

### 变更

- **自托管解析器 `matha/parser.matha`**：
  - `解析括号内输出` 列表判定由 `窥视逗号(p)` 改为 `有列表前瞻(p)`；列表路径在
    `解析列表元素`（已消费 `]`）后接 `解析输出集合_续`，左结合解析 `∪ ∩ ⊖ × ⊆` 链
    （右操作数用 `解析加减`，避免经 `解析集合` 右结合——对齐宿主 `_parse_output` 列表分支）。
  - 新增 `是表达式起始`（对齐宿主 `_is_primary_start`）、`是输出集合运算符文本` /
    `是输出集合运算符`、`输出集合运算符前瞻`、`括号有逗号`（对齐宿主 `_bracket_has_comma`：
    从 `[` 之后起以深度 1 扫描配对 `]` 前的顶层逗号）、`有列表前瞻`
    （`是表达式起始 and（窥视逗号 or 输出集合运算符前瞻 or 括号有逗号）`）、
    `解析输出集合_续`。

### 测试

- 新增 `_M4_OUTPUT_LIST_CASES` 13 例 × 3（宿主基准 / stage2 ≡ stage3 / 自举执行）。
- `tests/test_mbc_bootstrap.py + tests/test_bootstrap_host.py` 604 passed（无回归）；
  `-k boot_source` 5 passed（自举 parser 自身 stage2 ≡ stage3 不动点保持）。

## 集合理解 `{输出 | v >> S | 条件}`：自托管端可用（四端一致）

**日期**：2026-10-16

### 变更范围

补齐**自托管端**集合理解。宿主早已支持集合构造
`{输出 | 生成子句|条件 | …}`（含 `v >> S` 生成子句、过滤条件、映射输出，以及由
`1 <= v <= n` 链式比较推断有界整数域），而自举链路此前把整个 `{…}` 回退为输出文本
（`StringLit('{x|x>>s}')`）。现自举 parser 产 `comprehension` 节点、自举 compiler 降级为
嵌套循环 + 过滤 + append，产物与宿主逐项一致。至此**四端**（解释器 / 宿主 VM / 原生 /
自托管）集合理解一致，测试套件**最后一个 xfail 消除**。

### 变更

- **自托管解析器 `matha/parser.matha`**：
  - `解析器` struct 增 `在理解头: Bool`（各 record 重建点同步；`窥视走` 故意未加）；
    新增 `置在理解头`；`解析移位_续` 的 `是位或` 分支加 `not p.在理解头` 守卫——理解头内
    `|` 作子句分隔符而非位或（对齐宿主 `_parse_bit_expr` 的 `_in_comp_head` 抑制）。
  - 检测：`是理解头` / `有顶层理解管道` / `存在生成子句` / `首管道后有条件` / `首个管道` /
    `是条件运算符`（对齐宿主 `_is_comprehension_head` / `_has_top_level_comprehension_pipe`）。
  - `解析集合构造` 改为：`}`→枚举空、`是理解头 或 有顶层理解管道`→`解析集合理解`、否则枚举
    + `解析集合元素_rest`；`做集合构造` 改 5 参 `(form, variables, conditions, literals, output)`。
  - 新增 `解析集合理解` / `解析理解子句循环` / `解析理解子句`（`v >> S`→gen，否则 cond）/
    `必须推断` / `推断理解生成` 及界推断辅助：`_收集界` `_收集条件界` `_收集合取` `_合取子句`
    `_是比较` `_变量名` `_常量整` `_取负` `_镜像` `_记录比较` `_记界` `_界索引` `_界更新`
    `_收上界` `_收下界` `_替换` `_候选界` `_展开域` `_整数序列`（对齐宿主
    `_parse_set_comprehension` / `_parse_comprehension_clause` / `_infer_comprehension_generator`，
    含 100000 跨度上限、非整数/无界返回 null→抛错）。
  - **链式比较**：`解析比较_续` 增关系运算符链式分支——`a <= b <= c` 解析为
    `and(a<=b, b<=c)`（`解析关系链_续` 右嵌套 and 累积、中间项复用），对齐宿主
    `_parse_rel_expr`；此前自举侧把 `1 <= x <= 5` 误作 `(1<=x)<=5`，致有界域推断失效、
    理解回退文本。
  - **两处宿主-自举解析差异修正**（自举源须同时满足宿主解析器）：`_合取子句` 由
    `if/then/else … else [c]` 改写为**无括号三元** `cond ? … : [c]`——宿主把函数体 if/else
    分支当**语句**解析，`else [c]` 会被当成输出单元（`OutputStmt(expr=c, target="printf")`）；
    且函数体不能以 `(` 开头（被当 lambda 形参表），故条件不加括号。
- **自托管编译器 `matha/compiler_matha.matha`**：
  - `_发射集合构造` 增 `e["form"]="comprehension"` → `_发射集合理解` 路由。
  - 新增 `_发射集合理解`（`BUILD_LIST 0` → 存 acc 临时 → 逐层循环 → `LOAD_GLOBAL 构造集合`
    + `"enumeration"` + `BUILD_LIST 0` + acc + `CALL 3`）、`_发射理解层级`（递归嵌套循环，
    复刻宿主 `_emit_comp_level`：iterable→存 xs/i→`len(xs)`/`<` 判断→`get(xs,i)`→存循环变量
    →递归→i+1→`JMP`）、`_发射理解产出`（逐条件 `JZ` 记跳过点 + `append(acc, output)`）、
    `_发射理解条件`、`_补丁列表`。仅用既有操作码，常量池/字节码次序与宿主一致。

### 测试

- `pytest tests/test_mbc_bootstrap.py -k comprehension`：**8 passed**——`test_m10_comprehension_host_runs`
  + `test_m10_comprehension` 各 4 例：`gen_clause`（`{x|x>>s}`）、`ident_head`（`{a|b}`→文本回退）、
  `top_pipe_gen`（`{1+1|x>>s}`）、`bounded`（`{x|1<=x<=5}`，链式比较 + 有界域推断）；自举链路
  产物与宿主逐项一致。
- `pytest tests/test_mbc_bootstrap.py tests/test_bootstrap_host.py`：**565 passed**。
- `pytest -k boot_source`（自举不动点）：**5 passed**（宿主编译 ≡ 自举编译）。
- 全量 `pytest tests/ -m "not slow"`：**3067 passed** + 3 deselected（原最后一个 xfail 消除）。
- 全量 `pytest tests/ -m "slow"`：**3 passed**（自举不动点保持）。
- ruff：改动测试文件**仅存量债**，本次新增行无新告警。

### 备注

- 集合理解节点仅走**编译器路径**（自举 compiler 降级 → host VM 执行），两个自托管解释器
  （`interp.matha` / `interp_matha.matha`）无需改动。
- 自举 parser 现支持链式比较，与宿主一致；此为集合理解有界域推断的前提。


## 用户自定义运算符 `@define_op`：原生端 + 自托管端可用（四端一致）

**日期**：2026-10-15

### 变更范围

把 `@define_op`（运算符绑定具名函数：`a <符号> b` ⇒ `fn(a, b)`）从宿主端补齐到
**原生端**与**自托管端**，达成**四端一致**：

- **原生端**（`src/mbc/native.py`）：编译器既发 `LOAD_GLOBAL handler + CALL 2`，
  native **零改动**即复用既有闭包调用路径（多参 CALL + `LOAD_GLOBAL` 闭包记录）。
- **自托管端**：`matha/parser.matha`（产节点）+ `matha/compiler_matha.matha`（发码）+
  `matha/interp.matha` / `matha/interp_matha.matha`（求值）。

设计：把 handler 放在**节点**上（`{"类型":"自定义二元",…,"实现":<函数名>}`），
后端无需注册表——解析器产带 `实现` 的节点；解释器查具名函数调用；编译器发
`LOAD_GLOBAL + CALL 2`；VM 零改动。

### 变更

- **原生端（`c69a73a`）**：仅补 `tests/test_custom_ops.py` 原生端到端测试
  （编译为 PE64 exe 运行，校验 stdout：`2 ≈ 3 → 5`、变量参与、与 VM 结果一致）。
- **自托管解析器 `matha/parser.matha`**：
  - `解析器` struct 增 `自定义: List` 字段（`@define_op` 绑定：符号/优先级/结合性/
    处理函数），各 record 重建点同步该字段。
  - `解析定义运算符` 增可选 `=> <函数名>`（兼容 `-> <函数名>`）后缀，把绑定累积进
    `自定义` 表；声明节点仍为 `做定义运算符()`（编译期 NOOP）。
  - 新增 `查自定义/过滤自定义` 与 `解析自定义/解析自定义_续`（优先级爬升，镜像宿主
    `_parse_custom_op_rest`：left→`prec+1`、right→`prec`）；新增 `做自定义二元` 产
    **`自定义二元`** 节点；`解析三元` 接入 `解析自定义`。
- **自托管编译器 `matha/compiler_matha.matha`**：`_发射表达式` 增 `自定义二元` 分支 →
  `_发射自定义二元`（`LOAD_GLOBAL <实现>; <左>; <右>; CALL 2`，常量池次序与宿主一致）。
- **自托管解释器 `matha/interp.matha`**：`求值` 增 `自定义二元` 分支 → `求值自定义二元`
  （查具名实现，柯里化 `f(l)(r)` 调用）；`执行语句` 增 `定义运算符` NOOP。顺带修复
  `应用函数` 柯里化缺陷：多参函数在**最后一个参数**绑定前不提前求值体（原实现首参处
  即求值体 → `未定义变量`）。
- **`matha/interp_matha.matha`（`matha_bootstrap` 路径）**：`求值` 增 `自定义二元` 分支 →
  `求值自定义二元`（`应用多参数函数(f, [l, r], env)`）；`执行声明` 增 `定义运算符` NOOP；
  修复 `应用多参数函数` 形参名解析（形参为 Variable 节点时取其 `.名`）。

### 测试

- `pytest tests/test_mbc_bootstrap.py`：**550 passed + 2 xfailed**——含 `dop_use_left`
  （`@define_op … => 孪加` + `2 ∝ 3`）的 host / stage2≡stage3 / stage3 三态；
  `test_interp_custom_op_eval`（自举解释器求值 → 6）、`test_interp_custom_op_ast_has_impl`
  （AST 为 `自定义二元` 且携带 `实现`）。
- `pytest tests/test_bootstrap_host.py`：**8 passed**——含 `test_bootstrap_interpret_custom_op`
  （`matha_bootstrap` 走自举解释器，`2 ∝ 3 → [6]`）。
- 全量 `pytest tests/ -m "not slow"`：**3060 passed** + 3 deselected + 2 xfailed。
- 全量 `pytest tests/ -m "slow"`：**3 passed**（自举不动点保持）。
- 自举定点：`test_m2_boot_source_stage2_equals_stage3` 对
  `lexer/stdlib/parser/interp/compiler_matha` 全通过（宿主编译 ≡ 自举编译）。
- ruff：改动测试文件**仅存量债**，本次新增行无新告警。

### 备注

- 运算符语义仅绑定**全局具名函数**；未绑定（无 `=>`）时使用该符号，宿主在编译期报
  `未绑定实现`，自举端落到运行期报未定义。


## 用户自定义运算符 `@define_op` 可用（宿主解析器 + 解释器 + 字节码/VM）

**日期**：2026-10-15

### 变更范围

让 `@define_op` 声明**真正可用**。运算符语义 = **绑定到具名函数**：
`@define_op: <符号> = <优先级> | <结合性>  [ => <函数名> ]`，之后 `a <符号> b`
求值时调用该全局函数（左右操作数作实参）。**起步范围**：宿主解析器 + 解释器 +
字节码编译器/VM；native / 自托管后续跟进。

关键决策：**不改词法器**。`≈` 等非内置符号在词法层仍是 `SYMBOL`；解析器在
**二元运算符位置**检查当前 `SYMBOL` 是否为已注册自定义运算符，若是则按注册的
优先级/结合性做**优先级爬升**，产出 `ast.BinaryOp(op=<符号>)`。

### 变更

- 新增 `src/custom_ops.py`：注册表（`CustomOp(symbol, precedence, assoc, handler)`
  + `REGISTRY` + `register/get/is_custom_op/clear`）。**进程级全局**，`parse()` 会写入，
  测试须用 fixture `clear()` 隔离。
- `src/parser.py`：
  - `_parse_define_op` 增**可选 handler 后缀** `=> <函数名>`（`OP_FATARROW`；兼容 `->`），
    解析后 `custom_ops.register(...)`。
  - 新增 `_parse_custom_op_expr` / `_parse_custom_op_rest`：优先级爬升
    （left→`prec+1`、right→`prec`），包住 `_parse_or_expr`；`_parse_expr` 两处入口
    改为调用它（空注册表时是零开销透传）。
- `src/interp.py`：`_eval_binary` 顶部增自定义运算符分支 → `_eval_custom_op`
  （求值左右操作数 → 查全局函数 funcs/builtins/env → `_call_func_or_closure`）。
  未绑定实现 → `MathaRuntimeError("运算符 … 未绑定实现…")`；实现函数不存在 →
  `MathaRuntimeError("… 实现函数未定义: …")`。
- `src/mbc/compiler.py`：`_emit_expr` 的 `BinaryOp` 兜底分支（`_BIN_OPS` 未命中时）
  增自定义运算符发射：`LOAD_GLOBAL <handler>` + 求值左右 + `CALL 2`；未绑定 →
  `RuntimeError("字节码编译：运算符 … 未绑定实现…")`。**VM 路径与解释器结果一致**。
- 新增 `tests/test_custom_ops.py`（16 项，ruff-clean）：注册、解释器求值（真/假、
  优先级、left/right 结合性）、报错（未绑定/缺实现/编译期未绑定）、字节码/VM
  与解释器一致性、注册表工具。

### 测试

- `pytest tests/test_custom_ops.py`：**16 passed**。
- 全量 `pytest tests/ -m "not slow"`：**3051 passed** + 3 deselected + 2 xfailed
  （较 Phase ③ 的 3035 增 16）。
- 全量 `pytest tests/ -m "slow"`：**3 passed**（自举不动点保持）。
- ruff：`src/custom_ops.py` 与 `tests/test_custom_ops.py` **All checks passed**；
  `interp.py`/`compiler.py` 中本次新增块无新增告警（存量 E741/E702/B905 等为既有债）。

### 备注 / 后续

- 仅对**词法层为 `SYMBOL`** 的符号生效（已是原生 token 的如 `⊕` 不能再注册）。
- `custom_ops.REGISTRY` 是进程级全局：跨 `interpret()` 调用会残留，同进程多程序须 `clear()`。
- 后续跟进：native 发射器与自托管 `matha/parser.matha`——**均已在后续提交落地**，
  见顶部「原生端 + 自托管端可用（四端一致）」章节。


## 全符号资源库（Matha 源 + 宿主查询接入）

**日期**：2026-10-15

### 变更范围

Phase ③：新增**数据驱动**的全符号资源库。单一数据来源为 Matha 源文件
`matha/stdlib_symbols.matha`：分类登记 Matha 可用 / 可识别符号的
码位、中英文名、别名、类别与语义；运算符另带 **优先级 / 结合性**，可生成
`@define_op` 声明。宿主 `src/symbol_registry.py` **编译并运行同一文件**读取
其全局 `符号表`，再以 Python API 提供等价查询。**不改变词法器行为**，不注册运算符。

- 主类别（7 类）：`中文标点 / 全角 / ASCII / 运算符 / 数学 / 希腊 / 学科`。
- 一个符号只登记一次；跨类别归属用 `标签` 表达（如 `π` 主类=数学、标签含 `希腊`）。
- `按类别` 同时匹配 `类别` 与 `标签`，因此 `按类别("希腊")` 也会返回 `π`/`τ`/`φ`。
- 条目字段：`符号 / 码位 / 中文名 / 英文名 / 别名 / 类别 / 标签 / 语义 / 优先级 / 结合性`。
- 当前登记 **200** 条；其中带优先级（可经 `@define_op` 表达）的运算符 **65** 个。

### 变更

- 新增 `matha/stdlib_symbols.matha`：
  - 构造器 `码位`（`ord` 取各字符 Unicode 码点）、`符号(...)`（普通符号，优先级 0）、
    `运算符号(...)`（主类别=运算符，带优先级 / 结合性）。
  - 数据 `符号表`（200 条，按类别分组标注）。
  - 查询函数：`类别列表 / 全部符号 / 符号数目 / 按类别 / 按码位 / 按符号 / 按名 /
    取语义 / 运算符声明 / 可定义运算符`。
- 新增 `src/symbol_registry.py`：加载（`compile_source` + `VM` 运行，读 `符号表`）、
  进程内缓存（`clear_cache`）与 Python 查询 API（`all_symbols / count / categories /
  by_category / by_symbol / by_codepoint / by_name / semantics / operator_declaration /
  definable_operators`），只读取、不改变词法器。
- 新增 `tests/test_symbol_registry.py`（8 项）。

### 测试

- `pytest tests/test_symbol_registry.py`：**8 passed**。
- 全量 `pytest tests/ -m "not slow"`：**3035 passed** + 3 deselected + 2 xfailed
  （较 Phase ② 的 3027 增 8）。
- 全量 `pytest tests/ -m "slow"`：**3 passed**（自举不动点保持）。
- ruff：`src/symbol_registry.py` 与 `tests/test_symbol_registry.py` **All checks passed**。

### 备注

- Matha 源写法约束：布尔条件的续行**不能以 `or`/`and` 等二元运算符开头**
  （宿主解析器不识别行首运算符续行，会报 `期望 =`）——条件须写在同一行。
- 非内置的数学 / 逻辑 / 集合关系符号（如 `≈ ≠ ≡ ≤ ≥ ∝ ∈ ∉ ⊂ ⊃ ⊇ ⊄ ∧ ∨ ¬ ⇒ ⇔ ∘ ⊗ ⊙ ⊥ ∥`）
  以「运算符」登记并带优先级，供 `@define_op` 参考。**宿主解析器 + 解释器 +
  字节码/VM 现已支持**用 `@define_op: <符号> = … | … => <函数名>` 绑定并使用
  （见顶部「用户自定义运算符」节）；native 与自托管仍为登记数据、未启用。

## 聚合前缀 ∑ ∏（列表求和 / 求积，四端一致）

**日期**：2026-10-15

### 变更范围

Phase ② 收尾：补齐**聚合前缀** `∑`（列表求和）与 `∏`（列表求积），
（解释器 / 宿主 VM / native / 自托管链）四端一致。二者实现为**前缀一元运算符**
（op 名 `"sum"`/`"prod"`，与既有 `√`/`∛` 同模式）：

- 语义：操作数须为 list/tuple；`∑`=求和（空表 → `0`）、`∏`=求积（空表 → `1`）。
- 非列表操作数 → 抛**可捕获**异常（`求和() 需要列表` / `求积() 需要列表`）。
- 整数列表保持整数结果；出现浮点则整体转浮点（与内建 `sum` 一致）。

### 变更

- `src/interp.py`：新增 `builtin_列表求积`（`math.prod`，空表→1，非列表报错）；
  `builtin_列表求和` 文档补充 `∑`；`_eval_unary` 增 `sum`/`prod` 分支。
- `src/parser.py`：`_parse_unary`/`_parse_unary_operand` 前缀号集合由 `√ ∛` 扩为
  `√ ∛ ∑ ∏`（→`UnaryOp("sum"/"prod")`）。
- `src/mbc/compiler.py`：`_UNARY_OPS` 增 `sum`/`∑`/`prod`/`∏`（列表操作数不折叠）。
- `src/mbc/vm.py`：新增 `_builtin_list_sum`/`_builtin_list_prod`，`_UNARYOPS` 增
  `sum`/`prod`；默认内建新增 `_list_sum`/`_list_prod`（供自举 vm.matha 委托）。
- `src/mbc/native.py`：新增发射器 `imul_rr`（`imul r64,r/m64`，注意 reg 字段是**目标**，
  REX.R 由 dst 决定，与 `add_rr` 相反）；UNARYOP 增 `sum`/`prod` 分派；新增叶例程
  `f_list_sum`/`f_list_prod`（镜像 `_emit_builtin_sum` 循环体：整数 `add`/`imul` 保持
  整数、遇浮点转 `f_add`/`f_mul`，r8-r11 跨调用保留）；错误串增 `err_sum`/`err_prod`。
- 自托管第四端：
  - `matha/parser.matha`：新增 `是求和号`/`是求积号`，`解析一元`/`解析一元操作数`
    增 `∑`/`∏` 分支。
  - `matha/compiler_matha.matha`：`一元运算表` 增 `sum`/`∑`/`prod`/`∏`。
  - `matha/vm.matha`：`应用一元` 增 `sum`/`prod`，委托宿主原语 `_list_sum`/`_list_prod`。
- 测试：`tests/test_new_features.py` 新增 `test_aggregate_prefix_symbols`（11 断言）；
  `tests/test_native.py` `_PARITY_CASES` 新增 `phase2_aggregate`/`phase2_aggregate_var`；
  `tests/test_mbc_vm_matha.py` `_CASES` 新增 3 例；`tests/test_mbc_bootstrap.py` 新增
  M15 段（12 例 × {宿主运行 / stage2≡stage3 / 自举运行}，共 36）。

### 测试

- `test_mbc_bootstrap.py -k m15`：**36 passed**（含 `stage2 ≡ stage3`）。
- `test_mbc_vm_matha.py`：**91 passed**（含 slow 完全自举不动点）。
- 全量 `pytest tests/ -m "not slow"`：**3027 passed** + 2 xfailed（较 Phase ② 的 2985 增 42）。
- 全量 `pytest tests/ -m "slow"`：**3 passed**（自举不动点保持）。
- ruff：`test_mbc_bootstrap.py` 维持基线 21；本次改动在 native.py / compiler.py / vm.py /
  测试新增行 **无新增告警**（interp 新增 `builtin_列表求积` 的 N802 与既有
  `builtin_列表*` 家族一致）。

### 备注

- 单元素列表字面量 `[7]` 在本语言中被解析为 `Output` 节点（非列表），故
  `∑[7]` 非「单元素列表求和」；写作 `∑[7,]`（尾逗号）方为列表。测试用尾逗号形式。
- `∑`/`∏` 作为前缀运算符，仅接受单个操作数；多元素需列表字面量 `∑[a, b, c]`。

### 已知遗留（Phase ③）

- 全符号资源库 `matha/stdlib_symbols.matha` + 宿主接入 `src/symbol_registry.py`。
  **本条目发布时未做，后已实现，见顶部「全符号资源库」节。**

## 符号常量 / 前缀 √∛ / 中缀 ÷ / 单位后缀 °℃℉（四端一致）

**日期**：2026-10-15

### 变更范围

Phase ②：为「源码出现中文/运算/学科符号即报错」补齐**符号常量与符号运算符**，
（解释器 / 宿主 VM / native / 自托管链）四端一致：

- 符号常量：`π`=pi、`τ`=tau、`φ`=(1+√5)/2、`∞`=inf，以及空集字面量 `∅`=[]。
- 前缀一元：`√`=平方根（`√9`=3）、`∛`=立方根（`∛27`=3、`∛-8`=-2）。
- 中缀：`÷`=除（`6÷2`=3）。
- 单位后缀：`° ℃ ℉` 与既有 CJK 汉字一致，作**纯字符串标签**并入数值字面量
  （`90°`→数值 90 + 标签 `"°"`；运行期丢弃单位、仅取值，不做量纲/角度换算）。

### 变更

- `src/mathlib.py`：`CONSTANTS` 增 `π τ φ ∞`。
- `src/lexer.py`：`_SINGLE_CHAR_MAP` 加 `"÷"→OP_SLASH`；新增 `_UNIT_SYMBOLS={"°","℃","℉"}`，
  `_number()` 单位循环由「仅 is_cjk」扩为「is_cjk 或 _UNIT_SYMBOLS」。
- `src/parser.py`：`_parse_unary`/`_parse_unary_operand` 增前缀 `√`/`∛`（→`UnaryOp("sqrt"/"cbrt")`）；
  `_parse_primary` 增 `∅`→空列表字面量；`_parse_mul_expr` 把 `÷` 归一为 `/`。
- `src/interp.py`：`_eval_unary` 增 `cbrt`。
- `src/mbc/compiler.py`：`_UNARY_OPS` 增 `cbrt`/`∛`；`_fold_unary` 增 `cbrt` 折叠
  （整数完全立方回退 int）。
- `src/mbc/vm.py`：新增 `_builtin_cbrt`，`_UNARYOPS` 增 `cbrt`。
- `src/mbc/native.py`：新增 `cvtsd2si`、`cbrt` UNARYOP 分支、`f_cbrt` 标签块；修
  `∛2` 误输出 `2.0`（`box_float` 覆盖 xmm0，须先恢复结果位模式）。
- 自托管第四端：
  - `matha/lexer.matha`：`映射单符` 加 `÷→除`；新增 `是单位码`（CJK 与 `° ℃ ℉`），
    `扫描数字续` 在最终 emit 前折入单位码。
  - `matha/parser.matha`：新增 `去单位`（`整数值`/`浮点值` 剥离单位后缀）、
    `是开方号`/`是立方根号`，`解析一元`/`解析一元操作数` 增 `√`/`∛`，`解析主要` 增
    `符号` 分支（`∅`→空列表，余→变量）。
  - `matha/compiler_matha.matha`：`一元运算表` 增 `cbrt`；新增 `_折叠立方根`/`_立方回退`。
  - `matha/vm.matha`：`应用一元` 增 `cbrt`；新增 `立方根完美`；`引导` 注册
    `π τ φ ∞`（`∞` 用 `_to_float("inf")`，因自举 `float` 实现不解析 `"inf"`）。
- 测试：`tests/test_new_features.py` 新增 6 例；`tests/test_native.py` `_PARITY_CASES`
  新增 6 例（VM/AOT 逐行一致）；`tests/test_mbc_vm_matha.py` `_CASES` 新增 9 例；
  `tests/test_mbc_bootstrap.py` 新增 M14 段（23 例 × {宿主运行 / stage2≡stage3 /
  自举运行}，共 69）。

### 测试

- `test_new_features.py` 54 passed；`test_native.py -k phase2` 6 passed。
- M14：69 passed；`test_mbc_bootstrap.py` 全量 **509 passed + 2 xfailed**。
- `test_mbc_vm_matha.py` **88 passed**（含 slow 完全自举不动点）。
- 全量 `pytest tests/ -m "not slow"`：**2985 passed** + 2 xfailed。
- 四端一致：`π τ φ ∞ ∅ √9 √16 ∛27 ∛8 ∛64 ∛-8 ∛2 6÷2 90° 30℃ 98℉ 100米` 值全等，
  `stage2 ≡ stage3` 保持。
- ruff：`test_mbc_bootstrap.py` 维持基线 21；本次改动无新增告警。

### 修复

- 自举 `是单位码` 的 `℉` 码位写错（`8459`=ℋ → 正确 `8457`=U+2109），曾致
  `98℉` 的 stage2≠stage3。

### 已知遗留（本次未处理）

- 聚合 `∑`/`∏` 尚未实现；**全符号资源库**（Phase ③）未做。
- native 集合运算符假定操作数为 list（标量操作数读越界，与集合内建同限）。

## 集合运算符自托管第四端（∪∩⊖~×⊆）+ 宿主集合链结合性修复（四端一致）

**日期**：2026-10-15

### 变更范围

上一提交补齐了集合运算符 `∪ ∩ ⊖ ~ × ⊆` 的**三端**（解释器 / 宿主 VM / native），
遗留「自托管链」第四端。本次补齐自托管端，过程中发现并修复一处**宿主集合运算符链
的结合性不一致**：

- 宿主 `_parse_set_expr`（`src/parser.py:1602`）为**左结合**（while 循环），但
  `_parse_list_literal` / `_parse_output` 在列表字面量后另有自持尾链，右操作数用
  `_parse_expr()`（会再次进入 `_parse_set_expr`），故当**左操作数为列表字面量**时
  呈**右结合**。结果 `[1,2] ∪ b ∪ [4]` 解析为 `[1,2] ∪ (b ∪ [4])`，而 `a ∪ b ∪ c`
  解析为 `(a ∪ b) ∪ c` —— 前后不一致，并令 `[1,2,3] ⊖ [3] ⊖ [1]` 的 stage2 ≠ stage3。

### 变更

- `src/parser.py`（宿主，四端共享）：
  - `_parse_list_literal` 移除冗余的集合运算符尾链（`right=_parse_expr()`），让唯一
    链点回归 `_parse_set_expr`（左结合）。修前左操作数为列表字面量时右结合、否则左
    结合；修后四端一致左结合。
  - `_parse_output` 两处尾链 `right=_parse_expr()` → `_parse_add_expr()`（同理避免右结合）。
- `src/mbc/vm.py`：暴露集合原语 `_set_union/_set_inter/_set_diff/_set_comp/_set_prod/
  _set_subset`（语义复用 `_BINOPS` 的 `_set_*`，有序去重列表），供自举 `vm.matha`
  委托调用，避免自引用。
- `matha/parser.matha`：新增 `集合运算文本`/`是集合运算符`/`解析集合`/`解析集合_续`
  （插在 `解析比较` 与 `解析加减` 之间，对齐宿主 `rel → set → add`；操作数用
  `解析加减`）；`解析比较`/`解析比较_续` 改调 `解析集合`。词法器无专属类型，集合
  符号落「符号」，按文本判定：`∪∩`、`⊖/＼`、`×/＄`、`⊆`、`～/〜/¬` 归一为
  `∪∩⊖×⊆~`；**ASCII `~` 不列入**（它仍是前缀位取反，见 `是位取反`）。
- `matha/compiler_matha.matha`：`二元运算表` 增补 `∪ ∩ ⊖ ~ × ⊆`。
- `matha/vm.matha`：`应用运算` 增补六个集合分支，委托宿主 `_set_*`。
- 测试：
  - `tests/test_mbc_bootstrap.py` 新增 M13 段（15 例 × {宿主运行 / stage2≡stage3 /
    自举运行}，另含 ASCII `~` 一元判定 1 例，共 46）。
  - `tests/test_mbc_vm_matha.py` 新增集合运算符用例（自举编译 7 例 + 宿主编译 3 例），
    覆盖自托管 `vm.matha` 的 `应用运算`。

### 测试

- M13：46 passed；`test_mbc_bootstrap.py` 全量 440 passed + 2 xfailed。
- `test_mbc_vm_matha.py` 79 passed（含 slow 完全自举不动点）。
- 全量 `pytest tests/ -m "not slow"`：**2885 passed** + 2 xfailed；`-m slow`：3 passed。
- 四端（解释器 / 宿主 VM / native / 自托管链）集合运算符语义一致；`stage2 ≡ stage3`
  保持（`[1,2,3] ⊖ [3] ⊖ [1]` → `[2]`，左结合）。
- ruff：本次改动无新增告警（存量为既有 baseline）。

### 已知遗留（本次未处理）

- native 集合运算符假定操作数为 list（标量操作数读越界，与集合内建同限）。
- **符号常量/函数**（`√ π ∞ e ° ℃ ∑ …`）仍会 `KeyError`（Phase ②）；**全符号资源库**
  （Phase ③）未做。

## 集合运算符 ∪∩⊖~×⊆ 支持 + 运算符右值 `[x]` 解析修复（三端一致）

**日期**：2026-10-15

### 变更范围

用户反馈：源码出现中文/运算/学科符号即报错。定位到集合运算符 `∪ ∩ ⊖ ~ × ⊆` 原本
**仅解释器**支持——VM/native 在编译期直接拒绝（`src/mbc/compiler.py:1209`
`raise RuntimeError("字节码编译：不支持的二元运算符 …")`）。同时发现一处**四端共享的
解析器 bug**：集合运算符右值为单元素列表 `[x]` 时被误判为输出语句。

### 变更

- `src/parser.py`（四端共享）：`_parse_primary` 的「运算符右值」token 集合
  （`src/parser.py:2238-2254`）补入 `OP_SET_UNION/INTER/DIFF/COMP/PROD/SUBSET`。
  此前 `A ∪ [5]` 会解析成 `BinaryOp(op='∪', left=A, right=Output(5))`，四端结果错乱
  （native 端 `Output` 被当作表达式值 → 访问违例崩溃）。
- `src/interp.py`（参考语义）：集合运算符统一返回**有序去重列表**（与集合字面量一致，
  非升序）；新增模块级 `_set_seq`；`∪` 去重保序拼接、`∩`/`⊖` 保左序、
  `~` = `B \ A`（右操作数作全集，对齐 `docs/06-表达式与运算符.md`「补集（相对全集）」）、
  `×` 保序笛卡尔积（list of tuple）、`⊆` 布尔。
- `src/mbc/vm.py`：新增 `_set_seq/_dedup_ordered/_set_union/_set_inter/_set_diff/
  _set_comp/_set_prod/_set_subset`，并在 `_BINOPS` 挂载 `∪∩⊖~×⊆`。
- `src/mbc/compiler.py`：`_BIN_OPS` 增加集合运算符（透传，交由 VM/native）。
- `src/mbc/native.py`：新增 `_emit_setop_runtime`（`set_union/set_inter/set_diff/
  set_comp/set_prod/set_subset` 六个 x86-64 运行时子程序，复用
  `list_dedup`/`list_append`/`seq_contains`，语义=保序去重列表）、`_SET_BINOPS`
  分派（`OP.BINOP` 内，与 `in` 同形）、尾段 `_emit_setop_runtime(ec)` 注册。
- 测试：`tests/test_new_features.py` 新增「集合运算符右值单元素列表（解析器回归）」；
  `tests/test_native.py` 新增 `test_native_set_operators`（10 例）。

### 测试

- interp↔VM↔native 三端 8 例集合表达式逐例一致（含 `[3,1] ∪ [2]`→`[3,1,2]` 保序）。
- `test_new_features.py` 48 passed；`test_native.py` 568 passed（含 10 新增）。
- 全量 `pytest tests/ -m "not slow"` 2828 passed + 2 xfailed。
- ruff：`src/parser.py` 等改动无新增告警。

### 已知遗留（本次未处理）

- **自托管链**（`matha/lexer.matha` / `parser.matha` / `compiler_matha.matha` /
  `vm.matha`）尚不支持集合运算符与本次解析修复（第四端），待后续补齐。
- **符号常量/函数**（`√ π ∞ e ° ℃ ∑ …`）仍会 `KeyError`（Phase ②）；**全符号资源库**
  （Phase ③）未做。

## `#：` 输出括号内文本回退（四端一致修复）

**日期**：2026-10-14

### 变更范围

`#：[…]` 输出括号内的内容，宿主 `_parse_output`（`src/parser.py:2524`）在无法
解析为「恰好填满到 `]` 的单个表达式」时回退：把 `]` 之前的原始记号文本
（含换行 `"\n"`、不跳空白）拼成一个字符串字面量。自举 parser 无此回退，遇到
`#：[Hello world]` 等非表达式内容即报错（`probe2` 暴露）：

- `#：[Hello world]`：宿主 `['Helloworld']`，自举报错。
- `#：[你好，世界]`：宿主 `['你好，世界']`。
- `#：[  Hello   world  ]`：宿主 `['Helloworld']`（空白非记号）。
- `#：[1 + +2]`：宿主 `['1++2']`（`+ +2` 不能解析，回退拼记号）。

### 变更

- `matha/parser.matha`：
  - `解析器` struct 新增 `禁止并列` 字段，`规范`/`推进`/`推进原样` 透传。
    自举 parser 有并列应用（`f x`），宿主无；输出括号内须禁用并列，否则
    `[Hello world]` 被吞成 `FuncApp` 而非回退文本。
  - `解析应用链` 并列分支加 `and not p.禁止并列` 守卫。
  - `解析括号内输出` 重排：`]` → 空输出；`窥视逗号` → 列表字面量；否则
    `尝试输出表达式`。
  - 新增 `尝试输出表达式`/`试解析输出`/`处理输出`：经 VM 内建 `调用捕获`
    受保护地尝试解析（等价宿主 try/catch 的 ParseError 回退）；成功且正好停在
    `]` 用其结果，否则 `做文本回退`。
  - 新增 `禁并列`/`做文本回退`/`收集原始文本`：`收集原始文本` 以 `推进原样`
    逐记号拼 `当前(p).文本`（含换行），与宿主回退的 `_advance().value` 拼接
    逐字节一致；`做文本回退` 返回 `(做StringLit(文本), 停在 ] 的解析器)`，
    供调用方随后消费 `]`。
  - **实现约束（关键）**：不使用 `try` 节点，也不使用块内裸 `let`。自举编译器
    `compiler_matha` 尚不支持 `try` 的字节码生成（宿主把 try/catch/finally 各编
    为 thunk），且对块内裸 `let`（`{ let x = … in …; 后续语句 }`）会把局部名泄漏
    进常量池——二者都会破坏 stage2 ≡ stage3 自举定点。故 fallback 改用
    `调用捕获(() => 试解析输出(p))([])` + 纯 `let … in` 链实现。
    （**后续已修复**：`try` 自托管支持见「try/catch/finally 自托管端可用」节；
    块内裸 `let` 泄漏与 `;` 分隔符见顶部「块内裸 `let` 常量池泄漏修复 + `;`
    语句分隔符」节。）
- `tests/test_mbc_bootstrap.py`：
  - 新增 M12 段 `_M12_FALLBACK_CASES`（15 例 × 3：宿主运行 / stage2≡stage3 /
    stage3 运行）。
  - `test_set_rejects_identifier_leading_comma`：`#1：[{x, 2}]` 现与宿主一致
    （输出文本 `['{x,2}']`，非集合），断言随之更新。
  - `test_m10_comprehension_unsupported`：`#：[{…}]` 集合理解形式经文本回退不再
    报错；`ident_head` 与宿主一致，`gen_clause`/`top_pipe_gen`（宿主产集合结果）
    标注为集合理解遗留缺口（xfail）。

### 测试

- 探针 `fallback_parity.py`：16 例宿主/自举逐例对照，16/16 一致。
- `test_m2_boot_source_stage2_equals_stage3`（含 `matha/parser.matha`）通过——
  自举 parser 自身 stage2 ≡ stage3 复归（此前因引入 try/裸 let 而告负）。
- 全量 `pytest tests/ -m "not slow"` 2828 passed + 2 xfailed；slow 完全自举
  不动点单测通过。ruff `tests/test_mbc_bootstrap.py` 无新增告警。

### 已知遗留（本次未处理）

- `#：[…]` 的**列表前瞻**：宿主 `is_list_lookahead` 除「首个记号后紧跟逗号」外，
  还用 `_bracket_has_comma`（括号内深度 1 任意逗号）判定，故 `#：[1 + 1, 2]`
  宿主为列表 `[[2, 2]]`；自举 `窥视逗号` 仅看紧邻下一记号，此例回退为文本
  `['1+1,2']`。该差异先于本次（列表路径未改动），属独立缺口。
  （**后续已修复**：见顶部「`#：[…]` 输出括号列表前瞻 + 集合运算符链」节。）

## 自举前缀一元运算符 ~ ^ ** << ++ --（四端一致修复）

**日期**：2026-10-14

### 变更范围

自举链路缺前缀一元运算符，宿主可运行而自举崩溃。`probe2` 差分用例暴露五处：

- `#：[^9]`（前缀开方）→ self `KeyError: '^'`。
- `#：[~5]`（位取反）→ self `VM：不可调用的值 None`。
- `#：[++3]`（前缀自增）→ self 崩。
- `#：[--3]`（前缀自减）→ self 得 `3`（**错值**）：自举 lexer 把 `--` 拆成两个
  `减` 记号，被解析为 `-(-3)`。
- `#：[<<90]`（前缀角度）→ self 崩。

根因三处：

1. **自举 lexer** 把 `++`/`--` 拆成两个 `加`/`减` 记号，缺 `加加`/`减减` 类型
   （宿主 `tokens.py` 产出 `OP_INCR`/`OP_DECR`）。
2. **自举 parser** `解析一元` 只处理 `-`/`^`/`not`/`typeof`，缺 `~`/`**`/`<<`/
   `++`/`--`，且 `^` 未映射到开方（宿主 `_parse_unary` 对齐）。
3. **自举 compiler** `一元运算表` 缺 `sqrt`/`~`/`angle`/`++`/`--`，`_折叠一元`
   缺对应折叠。

### 变更

- `matha/lexer.matha`：
  - `类型` 枚举新增 `加加` / `减减`。
  - `检测多符` 新增 `++` / `--` 分支（对应宿主 `MULTI_CHAR_OPS` 的
    `OP_INCR` / `OP_DECR`）；`扫描主体` 的双字符白名单同步放行。
- `matha/parser.matha`：
  - 新增 `是位取反`（`~` 词法归 `符号`，按文本判定）。
  - 新增 `解析一元操作数`（对齐宿主 `_parse_unary_operand`：覆盖 `<<`/`^`/`**`/
    `-`/`~` 任意层前缀组合，如 `-<<30` = `-(<<30)`、`<<-90` = `<<(-90)`）。
  - `解析一元` 对齐宿主 `_parse_unary`：补齐 `<<`（前缀角度）、`^`/`**`（前缀
    开方）、`-`、`~`、`++`/`--`，操作数走 `解析一元操作数`；`not`/`typeof` 的
    操作数退回 `解析应用`（对应宿主 `_parse_postfix`）。
- `matha/compiler_matha.matha`：
  - `一元运算表` 增 `sqrt`/`^`/`~`/`angle`/`++`/`--`。
  - `_折叠一元` 增 `++`（`v+1`）/`--`（`v-1`）折叠；新增 `_折叠开方`——
    整数字面量完全平方折叠为整型（`^9 → 3`），否则折叠为浮点，与宿主
    `_fold_unary` 一致；`~`/`angle` 不折叠（发射 `OP_UNARYOP`）。
- `tests/test_mbc_bootstrap.py`：新增 M11 段 `_M11_PREFIX_CASES`（16 例：位取反
  及其链、开方（整数完全平方/非平方/浮点/`**`/表达式内）、角度（正/负/负角度）、
  自增自减（整数/浮点/变量））× 3 = 48 用例。

### 测试

- 全量 `pytest tests/` 2740 passed（含 slow 完全自举不动点）；ruff 无新增告警
  （`tests/test_mbc_bootstrap.py` 基线 22）。

## 自举位运算符 & | ⊕（含集合语境守卫，四端一致修复）

**日期**：2026-10-14

### 变更范围

自举链路缺位运算符，宿主可运行而自举崩溃（`corpus_probe` 用例 `bitops`：
`VM：不可调用的值 None`）。根因两处：

1. **自举 parser** `解析移位_续`（对应宿主 `_parse_bit_expr`）只处理
   `<<`/`>>`/`is`，缺 `&`/`|`/`⊕`。`&`/`⊕` 词法为 `符号`、`|` 为 `管道`，
   须按记号文本判别。宿主在 bit 层同层左结合处理此五者。
2. **自举 compiler** `二元运算表`（`compiler_matha.matha`）亦缺此三算子，
   补上后方可发射 `BINOP`。（`_折叠二元` 仅折叠 `+ - * **`，与宿主
   `_fold_bin` 一致，故补表**不**引入常量折叠分歧。）

**`|` 与集合语境陷阱**：宿主 `_parse_bit_expr` 在集合理解头部（`_in_comp_head`）
把 `|` 当子句分隔符而非位或；`{1 | 2}` 因非理解头仍是位或（得 `[3]`）。
自举 parser 不支持理解形式，故引入 `是理解头` / `有顶层理解管道`（对齐宿主
`_is_comprehension_head` / `_has_top_level_comprehension_pipe`）守卫：命中即
报错（`集合理解暂不支持`），避免 `{x | cond}` 被静默误解析为位或枚举；
`{1 | 2}` 非理解头，仍按位或，与宿主 `[3]` 一致。

### 变更

- `matha/parser.matha`：
  - `解析移位_续` 新增 `&`/`＆`（位与）、`|`/`｜`（位或）、`⊕`（异或）分支，
    操作数取 `解析乘除`，与宿主 `_parse_bit_expr` 同层左结合一致；新增
    `是位与` / `是位或` / `是异或` 判定。
  - 新增集合理解守卫 `是理解头` / `配对括号后续` / `配对括号走` /
    `有顶层理解管道` / `顶层记号` / `存在生成子句` / `首管道后有条件` /
    `首个管道` / `区间有条件` / `是条件运算符`；`解析集合构造` 命中即报错。
- `matha/compiler_matha.matha`：`二元运算表` 增 `&` / `|` / `⊕`。
- `tests/test_mbc_bootstrap.py`：新增 M10 段 `_M10_BITOPS_CASES`（10 例：
  顶层三算子、全角 `＆`/`｜`、混合优先级、集合位或/位与/异或、枚举混合）
  × 3（宿主运行 / stage2 ≡ stage3 / 自举运行）+ `test_m10_comprehension_unsupported`
  （3 例：生成子句、标识符头、顶层管道生成）= 33 用例。

### 测试

- `corpus_probe` 分歧数 8 → 7（`bitops` 转 OK）。
- 全量 `pytest tests/` 2740 passed（含 slow 完全自举不动点）；ruff 无新增告警
  （`tests/test_mbc_bootstrap.py` 基线 22）。

## 自举让函数显式 lambda 与顶层常量次序（四端一致修复）

**日期**：2026-10-14

### 变更范围

自举链路（`matha/parser.matha` + `matha/compiler_matha.matha`）与宿主在两个
用例上不一致，均通过 `corpus_probe` 扫描发现：

1. **`let [rec] f(params) -> T = (params) => body` 双层 lambda**：自举 parser
   的 `解析let表达式` 在函数式绑定分支里，把 `=` 之后的显式 lambda 又用签名
   参数包了一层，得到 `(params) => ((params) => body)`——值成了「返回函数的
   函数」。于是 `let rec f ... = (n) => …` 产出的是闭包而非计算结果（宿主
   产出正确值，例如 `f(3)` 得 `2`，自举得一个 `Closure`）。
2. **顶层常量池次序**：自举 compiler 的 `_编译程序` 先「一遍编译**全部**函数
   定义」再编译主码；而宿主 `compile_program` 是**按源码顺序单遍**编译
   （`for decl in program.decls: _compile_top_decl(...)`）。因此当带常量的顶层
   `let` 出现在 `func` 之前时，两者的常量池栈次序不同（如
   `let f = (n) => n + 1` 先于 `func g`，宿主常量 `[1,'+','f', 2,'*','f'…]`，
   自举为 `[2,'*', 1,'+','f','f'…]`），stage2 ≢ stage3。

修复：与 `解析函数定义` / 宿主 `compile_program` 对齐。函数间互引（含前向
引用）经 `LOAD_GLOBAL` 在运行期解析，故编译顺序无关。修复后上述用例
宿主 / 自举产物逐位一致（stage2 ≡ stage3）且运行结果一致。

### 变更

- `matha/parser.matha`：`解析let表达式` 函数式绑定分支——`=` 后若为显式
  lambda `(params) => body`，则直接采用该 lambda（其参数即函数参数），不再
  用签名参数包一层；否则维持原签名参数路径。
- `matha/compiler_matha.matha`：
  - `_编译程序` 去掉「一遍编译全部函数」预扫，顶层声明**按源码顺序单遍**编译。
  - `_编译声明`：`函数定义` 分支就地编译（`_编译函数`）；`模块` 分支改走
    新 `_编译模块`。
  - 原 `_编译全部函数` 替换为 `_编译直接函数`（仅直接子函数，不再递归嵌套
    模块，对齐宿主 `ModuleDecl` 分支），新增 `_编译模块` / `_编译非函数列表`。

### 测试

- `tests/test_mbc_bootstrap.py`：新增 M9 段 `_M9_LET_LAMBDA_CASES`
  （4 例：`let rec … and …` 显式 lambda 互递归、非递归 `let f(params)=(p)=>…`、
  `let` 先于 `func` 的常量次序、`let rec fact`）× 3（宿主运行 /
  stage2 ≡ stage3 / 自举运行）= 12 用例。
- `corpus_probe` 分歧数 9 → 8（`letrec_and` 转 OK）。
- 已验证 `test_mbc_vm_matha.py`（含 slow 完全自举不动点）与
  `test_mbc_bootstrap.py` 全通过；ruff 无新增告警。

## 宿主解析器：三元分支中的单元素列表字面量（四端一致修复）

**日期**：2026-10-14

### 变更范围

宿主解析器 `src/parser.py` 的 `_parse_primary` 在遇到 `[` 时，依据**前一个
token** 判定其为列表字面量还是输出命令，但遗漏了三元 `?` / `:` 语境。于是
`cond ? [x] : [y]`（**单元素**）被误判为 Output：condition 两侧各自输出一次，
宿主产出 `[x, x]`；而多元素 `[x, y]` 与自举解析器都按列表字面量。宿主自身
语义即不一致，且 `matha/vm.matha` 的 `补空`（`n>0 ? [null]+… : []` 的变体）
在宿主上崩溃（`None + list`）。

修复：新增语境标记 `_in_ternary_branch`，在三元 `?` / `:` 两处解析点
（`_parse_expr`、`_parse_paren_dispatch`）经新方法 `_parse_ternary_branch`
包裹分支解析；`_parse_primary` 在 `[` 判定时将该标记并入列表字面量语境。
修复后 `cond ? [x] : [y]` 在宿主 / 自举解析器上语义一致（列表），
stage2 ≡ stage3。

### 变更

- `src/parser.py`：
  - `__init__` 增 `self._in_ternary_branch = False`。
  - 新增 `_parse_ternary_branch()`：置标记后调用 `_parse_expr()`，`finally`
    恢复（支持嵌套三元）。
  - `_parse_expr`（三元 `?`/`:`，含裸 `else` 值与 `LIT_BOOL` 分支）与
    `_parse_paren_dispatch`（`(cond) ? a : b`）的 then/else 分支改用
    `_parse_ternary_branch()`。
  - `_parse_primary` 的 `[` 列表判定增补 `self._in_ternary_branch`。

### 测试

- `tests/test_mbc_bootstrap.py`：新增 M8 段 `_M8_TERNARY_LIST_CASES`
  （8 例：then/else 单元素、变量、布尔、多元素对照、递归 `补空`、括号三元点、
  嵌套三元）× 3（宿主运行 / stage2 ≡ stage3 / 自举运行）= 24 用例。
- 全量 `pytest`：2695 passed（含 slow 不动点用例）；ruff 无新增告警。

## 完全自举不动点：自编译编译器产物逐位一致（stage-2）

**日期**：2026-10-14

### 变更范围

在「自举编译器可编译 `vm.matha`」的基础上，验证**完全自举不动点**：用自举
编译器编译**整条引导链**（`lexer`/`stdlib`/`parser`/`interp`/`compiler_matha`
五文件拼接，488 个函数），得到由自举产物构建的 **stage-2 编译器**；再用它编译
`matha/vm.matha`，产物与 stage-1（宿主编译的编译器）及宿主编译 gold **逐位
一致**（函数字节码、主码、常量池）。证明编译器自编译后行为不变，自举闭环成立。

同时核对：六个自举源文件（含 lexer/stdlib/parser/interp/compiler_matha/vm）
各自经自举编译器编译的产物，函数集合、主码、常量池均与宿主编译逐位一致。

### 变更

- `tests/test_mbc_vm_matha.py`：新增 `test_bootstrap_self_hosting_fixpoint`
  （标 `@pytest.mark.slow`，代价约 265s，源于自举编译器解释执行 143KB 引导
  源码）；断言 `stage2 == stage1 == gold`。

### 测试

- `pytest tests/test_mbc_vm_matha.py -k fixpoint`：1 passed（约 265s）。
- 全量 `pytest`：2671 passed（约 577s，含本 slow 用例）。

## 自举闭环：自举编译器可编译 `vm.matha`（逐位一致）

**日期**：2026-10-14

### 变更范围

自举编译器（`matha/compiler_matha.matha`）此前无法编译自托管 VM
`matha/vm.matha`（报「期望 )」）。修复语言/编译器侧的三处缺口后，
自举编译器可编译 `vm.matha` 自身，且产物与宿主编译**逐位一致**：
98/98 函数字节码、主码、常量池（2031 项）全部相等。

### 变更

- `matha/vm.matha`：
  - `应用运算` / `应用内建` 中的成员判断由关键字 `in` 改为符号 `∈`——自举
    parser 的 `解析属于`（`matha/parser.matha:315`）仅识别符号形式，`in`
    关键字会导致解析到函数体时「期望 )」。
  - `补空` 由三元 `n>0 ? [null]+补空(n-1) : []` 改写为 `if/then/else`：宿主
    parser 把三元**分支起始位**的 `[expr]` 当作 Output（`_parse_output`），
    生成 `PUSH_NULL; DUP; OUTPUT`，运行时 `None + list` 崩溃。
- `matha/lexer.matha`：`扫描数字续` 增补科学计数法（`e`/`E` + 可选正负号 +
  数字），新增 `是科学尾` / `扫描尾数指数` / `扫描指数符号` / `扫描指数数字`，
  与宿主 `src/lexer.py:_lex_number` 同构。此前 `6.674e-11` 被拆成
  `6.674` `e` `-` `11`，自举产物把 `6.674` 当函数调用而崩溃。
- `matha/parser.matha`：`字符串转浮点` 改为委托 `float(s)`，删除重复的手写
  尾数解析（`找指数位`/`尾数转浮点`/`字符串转整数带符号`）。
- `matha/stdlib.matha`：`float(String)` 增补科学计数法，采用**大整数缩放**
  实现正确舍入：全部有效数字拼成整数 `digits`，按 `k = 指数 - 小数位` 施加；
  `k ≥ 0` 用 `_to_float(digits * 10**k)`（精确大整数一次舍入），`k < 0` 用
  `digits / 10**(-k)`（整数真除法一次舍入）。不再用 `pow(10.0, n)`（对
  `|n| > 22` 不精确，曾使 `6.022e23` 偏差 1 ULP）。新增 `_指数位置` /
  `_指数值` / `_十进制转浮点`。

### 测试

- `tests/test_mbc_vm_matha.py`：新增
  `test_bootstrap_compiles_vm_matha_identically`——断言自举编译器编译
  `matha/vm.matha` 的产物与宿主编译在模块名/主码/常量池/每个函数字节码上
  完全相等。
- 全量 `pytest`：2670 passed。

## 自托管 VM：内建与运算符覆盖扩展（四端一致）

**日期**：2026-10-14

### 变更范围

`matha/vm.matha`（自托管 M3V 虚拟机）补齐此前缺失的内建与运算符，使自托管
VM 与宿主 VM 在同一字节码上输出一致：

- **内建**：新增 60 余个宿主同名内建委托（数学反三角/双曲、数论、统计、
  组合、逻辑、集合、正则、日期时间、`list_push`、安全索引/取属性、`构造集合`、
  `正态密度` 等），并补齐数学常量 `tau`/`phi` 与物理常量 `G`/`c`/`g`/
  `h_planck`/`N_A`/`R`。
- **运算符**：补 `BINOP` 的 `&`/`|`/`⊕` 与 `UNARYOP` 的 `~`/`++`/`--`/`angle`。
- 至此自托管 VM 覆盖全部操作码（`FORMULA_SCHEMA` 除外，自举编译器不发射）。

### 变更

- 自举 `matha/vm.matha`：
  - `内建名表()` 增补全部新内建名；`应用内建` 分派改用 `三元名表()` /
    `二元名表()` 列表成员判定，`内建一元/二元/三元` 增补对应委托分支。
  - `应用运算` 增补 `&`/`|`/`⊕`；`应用一元` 增补 `~`/`++`/`--`/`angle`
    （位运算委托宿主原语，`++`/`--` 用算术，`angle` 用 `v*pi/180`，避免
    `vm.matha` 自引用）。
  - `注册内建全局()` 增补 `tau`/`phi`/`G`/`c`/`g`/`h_planck`/`N_A`/`R`。
- VM `src/mbc/vm.py`：
  - 新原生语 `_bit_and`/`_bit_or`/`_bit_xor`/`_bit_not`（复用 `_BINOPS`/
    `_UNARYOPS` 语义），供自举 VM 委托位运算。
  - 别名 `_bmatch = 匹配`：引导文件 `matha/parser.matha` 顶层 `func 匹配`
    会遮蔽同名正则内建，故以不冲突别名供 `vm.matha` 委托。

### 测试

- `tests/test_mbc_vm_matha.py`：`_CASES` 增补数学/集合/逻辑/正则/日期时间/
  安全访问等 parity 用例；新增 `test_operator_parity_host_compiled`（宿主编译
  路径覆盖 `&`/`|`/`⊕`/`~`/`++`/`--`/`<<`/常量）。
- 全量 `pytest`：2669 passed；ruff 无新增告警。

## 原生后端：MathaIOError（三端统一为列表表示）

**日期**：2026-10-14

### 变更范围

`MathaIOError(msg)` 由 VM 的 Python 元组 `("MathaIOError", str(m))` 统一为
2 元素列表 `["MathaIOError", msg]`，使解释器 / VM / 原生（并含自举 vm.matha）
表示一致，并补上原本缺失的原生实现（此前引用该名字在编译期抛
`NativeNotSupported`）。负载保留实参原值（不再做 `str` 归一），与自举
vm.matha 的列表表示对齐。

### 变更

- 解释器 `src/interp.py`：注册 `MathaIOError` → `["MathaIOError", m]`。
- VM `src/mbc/vm.py`：`MathaIOError` 由元组改为返回列表 `["MathaIOError", m]`。
- 原生 `src/mbc/native.py`：
  - 新增发射器 `_emit_builtin_matha_io_error`（arity 1）：自空列表经
    `list_append` 追加 `"MathaIOError"` 静态字符串与实参，返回 2 元素列表；
    中间列表入操作数栈作 GC 根。
  - 注册进 `NATIVE_BUILTINS` / `_BUILTIN_ARITY`(1) / `_BUILTIN_EMITTERS`，
    并自 `_UNRESOLVED_GLOBALS` 移除。
  - 数据段新增静态字符串 `tag_ioerror = "MathaIOError"`。
- 自举 `matha/vm.matha`：`MathaIOError` 标签由 `"__MathaIOError__"` 统一为
  `"MathaIOError"`。
- 现状：`_UNRESOLVED_GLOBALS` 已无真正可达的未实现名字；该编译期拒绝分支
  转为纯防御性（由测试以 monkeypatch 注入探针名验证）。

### 测试

- `tests/test_native.py`：新增 parity 用例 `ioerror_list` 与
  `test_matha_io_error_is_two_element_list`；未实现全局拒绝测试改用
  monkeypatch 探针名。
- `tests/test_interp_parity.py`：新增 `ioerror_direct` / `ioerror_structural`
  （解释器 / VM 一致）。
- `tests/test_native_regex.py`：`test_unresolved_global_rejected` 改用
  monkeypatch 探针名。
- 全量 `pytest`：2638 passed。

## 原生后端：list_push（收尾剩余未实现全局名）

**日期**：2026-10-14

### 变更范围

补齐原生后端唯一仍可实现的 VM-only 全局 `list_push`（自举编译器 `_发`
使用的线性列表构建器）。原生列表为不可变定长对象（无容量位），故返回
新列表，**语义等价 `append`**：调用方保证列表由单一线性链持有、不与其它
绑定别名共享，故与 VM 的原地 `list.append` 可观察结果一致。

### 变更细节

- `src/mbc/native.py`：新增 `_emit_builtin_list_push`（arity 2，复用
  `list_append`，标签 `fn:list_push`）；`list_push` 注册进 `NATIVE_BUILTINS`/
  `_BUILTIN_ARITY`（2）/`_BUILTIN_EMITTERS`。
- 收尾后 `_UNRESOLVED_GLOBALS` 中**唯一真正可达**的未实现名仅剩
  `MathaIOError`：VM 端返回 Python 元组 `("MathaIOError", msg)`，原生后端
  无元组类型，保留为文档化的结构性限制（编译期报 `NativeNotSupported`）；
  其余名字（`真/假/null/None`、数学常量）已在 `LOAD_GLOBAL` 前特殊处理。

### 测试

- `tests/test_native.py`：新增 parity 用例 `b16s_list_push`、
  `test_list_push_builder_matches_append`。
- `tests/test_native_regex.py`：`test_unresolved_global_rejected` 改用
  `MathaIOError`（`list_push` 已实现）。
- 全量 `pytest`：2634 passed。

## 原生后端：调度三内建（注册任务/执行待办/待办列表）

**日期**：2026-10-13

### 变更范围

为原生后端补齐 `注册任务`/`执行待办`/`待办列表`，**严格对齐解释器/VM 现状**：
宿主 `_scheduled_tasks` 为模块级全局，且回调值（解释器为元组
`('__closure__', Lambda, [])`，VM 为 `Closure` 对象）**不可调用**，故
`task["callback"]()` 恒抛 `TypeError` 被吞——`执行待办` **恒返回空列表**，
到期任务仍被移出待办表。原生端逐字复现该语义（不引入可调用回调）。

### 变更内容

- `src/mbc/native_time.py`：
  - 局部类型常量补 `TYPE_LIST = 2`（`_emit_new_empty_list` 需要）。
  - `_emit_sched_runtime`：`tm_now_sec`（`GetSystemTimeAsFileTime`×100ns
    → 秒 − `tm_c_unix_epoch`=11644473600.0），供 next_run 比较。
  - 任务对象 = 五键字典 `interval/name/callback/next_run/id`（键经 `val_eq`
    与源码 `sob:` 串匹配）；`注册任务` = 柯里三参内建，分配 id = 当前任务数
    （追加前），构造字典后 `list_append` 写回 BSS 根 `gc_extra_root`。
  - `执行待办`（arity 1，忽略占位）：遍历到期项（`float_cmp2` `jae` now≥next）
    前移 `next_run = now + interval`，并**不逐个移出**（复现宿主吞异常路径），
    最终返回空列表。
  - `待办列表`（arity 1，忽略占位）：返回未到期任务字典组成的列表。
  - 调度标签统一以 `tsk_` 前缀，避免与堆运行时的 `pl_loop` 等标签冲突。
- `src/mbc/native.py`：新增 GC 根槽 `gc_extra_root`（BSS）并纳入 GC 标记；
  `注册任务`/`执行待办`/`待办列表` 注册进 `NATIVE_BUILTINS`/`_BUILTIN_ARITY`
  （3/1/1）/`_BUILTIN_EMITTERS`，并从 `_UNRESOLVED_GLOBALS` 移除。

### 测试

- `tests/test_native_time.py`：新增 5 例（确定性三端 parity：顺序 id 0/1、
  到期任务被移除后 `执行待办=[]` 且 `len(待办列表())=1`；顺序 id；执行待办
  恒 `[]`；待办列表类型/长度；3000 次注册触发 GC 后根集合仍完整）。
- 全量 `pytest`：2632 passed。

## 原生后端：计时器内建（极简对象/方法模型）

**日期**：2026-10-13

### 变更范围

为原生后端补齐 `创建计时器`，并据此引入「**极简对象/方法模型**」：
**对象 = 字典**（键=方法名，值=闭包），**方法 = 共享同一状态盒的单参闭包**。
三端（解释器/VM/原生）表示一致，故解释器与 VM 无需改动即可通过
`t.start()`（`dict.get` + 可调用值）调用方法；原生端复用既有的 dict、
闭包记录与 `apply_rt`，无需新增属性/方法分派指令。方法名保持英文，
与既有 `Timer` API 一致：`start`/`stop`/`reset`/`elapsed`。

### 变更内容

- `src/domains/time_module.py`：新增工厂 `make_timer()`，返回
  `{"start":…,"stop":…,"reset":…,"elapsed":…}`，四个闭包共享可变状态盒
  `[start, elapsed, running]`，签名均为 `(_unit=None)` 以容忍 `t.m()` 被解析
  为 `m(0)` 的占位实参；`创建计时器` 由 `Timer` 类改为
  `_ignore_unit(make_timer)`。保留 `Timer` 类供宿主 Python 直接使用。
- `src/mbc/native_time.py`：
  - 状态盒 `[TYPE_TIMER][start(FILETIME 100ns)][elapsed(double)][running]`
    （32 字节）。
  - 方法函数 `tm_method_start/stop/reset/elapsed`：从环境槽 `[rbp-16]` 取盒；
    `start` 记 `GetSystemTimeAsFileTime` 并置运营标志；`stop` 若在运行则累加
    `(now-start)/1e7` 后清零标志并返回累计秒；`elapsed` 运行中返回
    `elapsed+(now-start)/1e7`，否则返回 `elapsed`；`reset` 清空三项。返回值
    经 `box_float` 装箱（`stop`/`elapsed`）或 `null_obj`。
  - `_emit_builtin_create_timer`：分配状态盒 → 四个闭包记录
    （`[TYPE_CLOSURE][fn][env=盒][arity=1]`）→ 字典 `[TYPE_DICT][4][(键,值)×4]`。
  - `emit_time_data` 追加 `tm_c_1e7` 常量与四个方法名 STR 对象
    （`tm_key_start/stop/reset/elapsed`）；键经 `val_eq` 按内容比较，故与源码
    `t.start` 的 `sob:` 串匹配。
- `src/mbc/native.py`：新增 `TYPE_TIMER=12`；`创建计时器` 注册进 `NATIVE_BUILTINS`
  /`_BUILTIN_ARITY`（1）/`_BUILTIN_EMITTERS`，并从 `_UNRESOLVED_GLOBALS` 移除；
  GC 对象尺寸表增 `TYPE_TIMER → 32`（盒内 `+8..+24` 均为标量/整数，不指向堆）。

### 测试

- `tests/test_native_time.py`：新增 5 例（确定性三端 parity：reset 后
  `elapsed`/`stop` 精确 `0.0`、`typeof=字典`；非负性断言；双实例互不影响；
  20000 次创建/丢弃触发 GC 后仍可用）。
- 全量 `pytest`：2627 passed。

## 原生后端：日期时间内建（非纯时钟采集族 + 解析时间）

**日期**：2026-10-13

### 变更范围

为原生后端补齐 `time_module` 中**非纯**时钟采集族，与解释器/VM 逐字节对齐：
`获取时间戳`（Unix 秒含微秒的浮点）/`获取日期`/`当前日期`（本地 `YYYY-MM-DD`）/
`当前时间`（`HH:MM:SS`）/`获取日期时间`（本地 `…T..:..:..ffffff`）/
`获取UTC时间`（UTC，`Z` 结尾）/`格式化时间`（任意时间戳 + `strftime` 格式串）/
`解析时间`（日期串 + 格式串 → 时间戳）。`创建计时器`/`注册任务`/`执行待办`/
`待办列表` 依赖对象/全局状态，原生暂未实现（列入 `_UNRESOLVED_GLOBALS`）。

### 变更内容

- `src/mbc/native_time.py`：
  - `tm_gsftaf`：`kernel32!GetSystemTimeAsFileTime` → `FILETIME`（100ns），
    经引导期写入的 `k32_base` 惰性 `GetProcAddress` 解析。
  - `tm_now_tm`（本地/UTC 分解）、`tm_strftime`、`tm_newstr`、`tm_build_dt`
    （ISO 秒 + 微秒 + 可选 `Z`）。
  - `解析时间`：Windows CRT 无 `strptime`，故自实现格式串解析子集
    （`%Y/%y/%m/%d/%H/%M/%S/%f`、字面量与 `%%`），把结果填入 `struct tm`
    后交 CRT `_mktime64` 按**本地时区**换算；字段越界/格式不符/多余输入
    返回 `0.0`（对齐宿主捕获 `ValueError` 的行为）。辅助例程 `tm_pf_digits`
    （数字段）与 `tm_parse_fmt`（格式驱动，自建帧保存中间字段）。
  - 8 个内建发射器；`emit_time_bss` 预留 `k32_base`/`tm_filetime`/`tm_timeval`/
    `tm_frac`/`tm_tm`/`tm_strbuf`；`emit_time_data` 追加 CRT 格式串/导出名/
    `1e-6` 常量。
- `src/mbc/native.py`：`_CRT_FUNCS` 增 `_time64`/`_localtime64_s`/`_gmtime64_s`/
  `_mktime64`/`strftime`；API 解析完成后保存 `k32_base`；注册 8 个内建
  （arity 见下）；新增 `_Emitter.mov_mem_r32`（32 位存储，写 struct tm 字段）。
- `src/domains/time_module.py`：新增 `_ignore_unit`——Matha 的 `f()` 被解析为
  对占位整数 0 的应用（`parser.py` 空括号 → `FuncApp(func, IntegerLit(0))`），
  故零参内建须以「忽略一个占位实参」的单参形式暴露；`获取时间戳`/`获取日期`/
  `当前日期`/`当前时间`/`获取日期时间`/`获取UTC时间`/`创建计时器`/`执行待办`/
  `待办列表` 均据此包装。原生端对应内建 arity 设为 1（`格式化时间`/`解析时间`
  为 2）。

### 关键修复

- **x64 影子空间**：`tm_gsftaf` 调用 WinAPI、`格式化时间`/`解析时间` 调用
  CRT 前未预留 32 字节影子空间，CRT 覆写已被压栈保存的寄存器（`_save` 区域
  与影子空间重叠）；`_localtime64_s` 在较大时间戳上走会写影子的慢路径，故
  表现为按时间戳阈值触发的 `0xC0000005`。助手帧统一放大到 `0x40`
  （`tm_strftime` 为 `0x28`），相关内建在调用 CRT 前额外 `sub rsp,0x20`。
- **SSE 强前缀序**：`_Emitter._sse_rm` 把 REX 放在强制前缀 `F2` 之前，
  当 `REX.B` 置位（基址 `r8..r15`）时被解码器丢弃，基址退化为低 3 位寄存器
  （如 `r11→rbx`）导致误访存；改为 `F2 REX 0F xx`。
- **`_imul` 的 REX 位**：两操作数 `imul r64, r/m64` 中 `dst` 走 REX.R（0x04）、
  `src` 走 REX.B（0x01），此前判据写反。旧调用点 dst/src 均 < r8 故未显形，
  新增 `_imul(_RAX, _R11)`（十进制权重）时暴露为 `imul r8, rbx`——累加器恒为
  0，导致 `解析时间` 把所有字段读成 0。

### 测试覆盖

- `tests/test_native_time.py` 扩到 72 项：确定性 `格式化时间` 三端 parity
  （含触发影子空间路径的 `262144`）、`解析时间` 定值 + 三端 parity（含格式
  不符、字段越界、多余输入、`%y`/`%f`/`%%`）、取当前时刻者的格式/时钟一致性
  断言、零参内建的解释器/VM 求值。
- 全量 `pytest`：2622 passed。

## 原生后端：日期时间内建（纯函数）

**日期**：2026-10-13

### 变更范围

为原生后端补齐 `time_module` 中**纯函数**的机器码实现，与解释器
（`src/domains/time_module.py`）逐字节对齐：`闰年判断`/`月份天数`/`时区偏移`/
`时区转换`/`日期差`/`星期几`/`日期加减`。日期用 Howard Hinnant 的
`days_from_civil`/`civil_from_days` 算法在儒略日序列号上运算，避免闰年与
月末分支；时区名与中文星期名以静态 STR 对象随数据区发射。非纯函数
（获取时间戳/当前日期/格式化时间/解析时间/计时器/任务调度等）依赖系统时钟
与全局状态，仍只由解释器与 VM 提供，原生后续补齐。

### 变更内容

- 新增 `src/mbc/native_time.py`：
  - 运行时助手 `tm_is_leap`/`tm_days_in_month`/`tm_parse_date`（ISO 文本
    → 儒略日序列号）/`tm_streq`/`tm_tz_offset`（时区名查表 → 小时偏移）/
    `tm_format_date`（序列号 → ISO 文本，堆分配 26 字节）。
  - `_emit_days_from_civil`/`_emit_civil_from_days`：Hinnant 日历算法。
  - 7 个内建发射器（纯函数，整数未装箱返回，布尔用 `bool_true`/`bool_false`）。
  - `emit_time_data`：12 个时区名 + 7 个中文星期名 STR 对象。
  - `configure()` 注入 `_emit_prologue/_emit_epilogue`，避免循环导入。
- `src/mbc/native.py`：注册 7 个内建；`_emit_time_runtime` 追加到运行时段，
  `emit_time_data` 随静态数据区发射。

### 关键修复

- `days_from_civil` 的纪元除数误用 146097（天/400 年）除以**年**，应为 400；
  导致解析出的序列号恒少 4～5 天（`星期几` 偏移、`日期加减` 结果偏差）。

### 测试覆盖

- 新增 `tests/test_native_time.py`（39 项）：纯函数定值用例 + 与解释器/VM 的
  联合 parity（含 1970 前日期、世纪闰年、未知时区、跨世纪日期加减）。
- 全量 `pytest`：2589 passed。

## 原生后端：正则内建（阶段 B：解析器 + 回溯 VM + 捕获组与 5 内建）

**日期**：2026-10-13

### 变更范围

在阶段 A（字面量）基础上，为原生后端补齐完整正则引擎：模式解析器、回溯
VM（`re_search`/`re_bt_try`，含回溯栈与循环头）、UTF-8 编解码助手、捕获
组切片与结果构造，并实现 5 个内建 `查找正则`/`查找全部`/`命名组`/`分割
正则`/`替换正则` 的机器码发射。语义以 `src/regexlib.py` 为单一事实源，
原生输出与解释器/VM 逐字节对齐。

### 变更内容

- `src/mbc/native_regex.py`
  - 模式解析器 `re_compile`：字面量、字符类、预定义类、量词 `* + ? {m,n}`
    （含非贪婪）、分组（捕获/非捕获/命名 `(?P<name>...)`）、选择 `|`、
    锚点 `^ $ \A \Z \z \b \B`、转义（含 `\d` 等）；编译为 OP 程序数组。
  - 回溯 VM：`re_search`（起点扫描 + 可选 require_end）、`re_bt_try`
    （`OP_MATCH/CHAR/ANY/CLASS/JMP/SPLIT/BOL/EOL/BOS/EOS/WORDB/NWORDB/
    SAVE/LOOPHEAD/PLUSHEAD/LOOPEND`，回溯栈 `BT_MAX`、循环上限 `UNDO_MAX`）。
  - 运行时助手：`re_enc_cp`/`re_utf8_decode`/`re_check_str`/`re_cp_slice`/
    `re_cap_slice`/`re_mk_match_list`/`re_join`/`re_append_cp`。
  - `_emit_re_prelude`/`_emit_new_list`：内建进入时解码模式与主语、编译程序、
    构造空列表；`_emit_re_expand_into`：替换模板展开（`\1..\9 \0`、
    `\g<name>`/`\k<name>`/`\g'name'`、`$n`，simple 转义，未知项按 regexlib
    语义丢弃反斜杠）。
  - 5 个内建发射器：`_emit_builtin_regex_find/findall/named/split/sub`。
  - 新增 BSS/数据区（`emit_regex_bss`/`emit_regex_data`）与 `_SCALARS` 中的
    正则状态格；`TYPE_LIST=2`/`TYPE_DICT=3` 常量。
- `src/mbc/native.py`：注册 5 个内建（`NATIVE_BUILTINS`/`_BUILTIN_ARITY`/
  `_BUILTIN_EMITTERS`），从 `_UNRESOLVED_GLOBALS` 移除对应名字；追加
  `_emit_re_runtime` 到 `_build_emitters`。

### 关键修复

- 回溯 VM 将 `OP_BOS`（`\A`）误当作结束锚点（`pos==slen`），导致
  `全匹配("\\Aab\\Z")` 误判为假；改为要求 `pos==0`。
- 替换模板 `\g<name>`/`\k<name>`：起始定界符分支与「是否消费闭符」判断
  取反，导致命名组取值错误、闭符偶被当成字面量。修正为 `<`→`>`、`{`→`}`
  正确配对，并仅在读到闭符时前移索引。
- 新内建标签（`fa_loop`/`bt_loop`/`rs_fail` 等）与 `native.py` 全局标签
  冲突（`标签重复`）；统一加 `rg_` 前缀消除。

### 测试覆盖

- `tests/test_native_regex.py` 扩充至 101 项：元字符匹配/全匹配 parity、
  5 内建与解释器/VM 的联合 parity、非支持构造的可捕获异常。
- 全量 `pytest`：2550 passed。

## 原生后端：正则内建（阶段 A：字面量）

**日期**：2026-02-14

### 变更范围

原生后端（`src/mbc/native.py`）新增正则内建 `匹配`/`全匹配` 的机器码发射，
由新模块 `src/mbc/native_regex.py` 提供。阶段 A 仅实现**纯字面量模式**的
子串/全串匹配（按 UTF-8 字节比较），模式串含元字符
（`. ^ $ * + ? { } [ ] ( ) | \`）时于运行期抛出**可捕获**异常
（「暂不支持元字符模式」），避免给出静默的错误答案。此为「完整 PCRE 风格
原生引擎」的第一阶段，解析器 + 回溯 VM（阶段 B）后续补齐。

### 变更内容

- 新增 `src/mbc/native_regex.py`：`re_check_str`/`re_has_meta`/
  `re_lit_match_at`/`re_lit_search` 运行时助手，`匹配`/`全匹配` 内建发射器，
  `_emit_re_runtime`（追加到 `_build_emitters` 的运行时段）、`emit_regex_data`
  （元字符查表 + 两条错误消息串，随静态数据区发射）。`configure()` 注入
  `_emit_prologue/_emit_epilogue`，避免与 `native.py` 循环导入。
- `native.py`：`NATIVE_BUILTINS`/`_BUILTIN_ARITY`/`_BUILTIN_EMITTERS` 注册两个
  内建；`_UNRESOLVED_GLOBALS` 增加 `查找正则/查找全部/命名组/替换正则/分割正则`
  （编译期明确报错，避免静默读到空 cell）；调用 `_emit_re_runtime`/`emit_regex_data`。
- 阶段 A 不做任何堆分配（静态 scratch cell 非 GC 根），空模式/错误路径均安全。

### 关键修复

- 字面量循环此前以「模式长度」为基址读 haystack（漏加 haystack 指针），
  运行期访问违例（0xC0000005）。修复为 `hay_ptr + idx + k`。
- `raise_rt` 改为 `and rsp,-16` 自对齐：此前依赖入口 `rsp≡8`，任何在奇数个
  寄存器入栈后直接 `call raise_rt` 的调用点都会破坏 SSE 对齐而崩溃。现兼容
  任意入口对齐。

### 验证

- 新增 `tests/test_native_regex.py`（29 项）：字面量子串/精确、空模式、
  UTF-8 多字节、元字符/非字符串的可捕获错误与未捕获退出码（=1）、
  未实现内建的编译期拒绝、与解释器/VM 的 parity。
- 全量：`2515 passed`（净增 29）。

## 正则表达式库：解释器与 VM 双端内建（`src/regexlib.py`）

**日期**：2026-10-12

### 变更范围

新增可移植回溯正则引擎 `src/regexlib.py` 作为**单一语义源**：解释器
（`src/interp.py`）与 M3V VM（`src/mbc/vm.py`）复用同一 `_register_regex_builtins`
注册函数，保证两端语义一致（原生后端后续将复用同一「模式 → 节点」编译结果与
匹配算法）。

支持 PCRE 风格语法：字面量/转义、`.`、字符类 `[...]`（含范围/取反/内嵌
`\d\w\s`）、简写类、锚点 `^ $ \A \Z \z \b \B`、量词（贪婪/惰性/占有）、
捕获/非捕获/命名组、反向引用（`\1`、`\k<名>`、`\g<名>`、`(?P=名)`）、
环绕断言（`(?=) (?! ) (?<=) (?<!)`）、内联标志 `(?imsx)` 与作用域 `(?i:…)`。

### 内建（柯里化，`查找` 加「正则」后缀以不遮蔽字符串内建 `查找(文本,子串)->索引`）

- `匹配(re)(s)` → 布尔（search）
- `全匹配(re)(s)` → 布尔（fullmatch）
- `查找正则(re)(s)` → `[整体, 组1, …]`（未参与组为 null），无匹配为 null
- `查找全部(re)(s)` → 列表，每项同上
- `命名组(re)(s)` → `{组名: 文本}`，无匹配为 null
- `替换正则(re)(新)(s)` → 文本（`新` 可含 `\1..\9`、`$1`、`\g<名>`）
- `分割正则(re)(s)` → 列表（含捕获组）

### 变更内容

- 新增 `src/regexlib.py`：`_Parser`（模式 → 节点 AST）、`Pattern`/`Match`
  （CPS 回溯匹配器）、`_expand_repl`、`compile_regex`、`_register_regex_builtins`。
- `src/interp.py::_build_domain_builtins` 与 `src/mbc/vm.py::_default_builtins`
  调用 `_register_regex_builtins`。

### 验证

- 新增 `tests/test_regex.py`（37 项）：引擎单元（回溯/字符类/分组/环视/
  反向引用/贪婪惰性/标志/替换/分割）+ 解释器↔VM parity（含一等值调用）。
- 全量：`2486 passed`（净增 37）。

## 原生后端：修复顶层 `func` 值不支持偏应用/柯里化的崩溃

**日期**：2026-10-12

### 变更范围

顶层 `func` 名在值位置（`let f = g`、放入列表、作为实参传递）此前被发射为
`.text` 中的**纯代码地址**。`apply_rt` 对落在堆区间之外的值走 `ar_plain`：
`xor r13d,r13d; jmp rax`，**完全忽略实参数**。因此任何非「实参数 == 形参数」
的调用都会跳入函数序言并按 arity 弹参数，而栈上并无那么多实参：

- `func g(a,b,c) = …` 时 `g(1)(2)` → 访问违例 `0xC0000005`；
- `let h = g(1)` 后再 `h(2)` → 崩；
- `let fns = [g]` 后 `fns[0](1)(2)(3)` → 崩。

直接写 `g(1)(2)(3)` 之所以正常，是因为编译器把**完全应用**的调用融成了单条
`CALL 3`（`compiler.py:_flatten_call` + `_scan_fn_arities`），绕开了偏应用路径，
从而长期掩盖了该缺陷。VM 侧无此问题（始终用闭包/Partial）。

### 变更内容

- 新增 `_user_closure_arities`：静态扫描所有 `LOAD_GLOBAL`，凡引用到「顶层
  `func`、未被同名全局变量遮蔽、且无捕获」的函数，收集 `name → arity`。
- 启动期 `_start` 为这些函数各分配一条 `[TYPE_CLOSURE][fn][env=0][arity]`
  记录，指针写入数据槽 `bclo:{name}`（复用 arity>1 内建的柯里化机制）。
- `LOAD_GLOBAL` 对上述函数名改为载入 `bclo:{name}`（而非裸代码地址），使其
  调用经 `apply_rt → ar_close` 按 arity 决定「直调 / 偏应用 / 重建调用」。
- 数据节为这些名字补发 `bclo:` 槽位。

捕获型函数不受影响：它们在运行期经 `MAKE_CLOSURE` 实例化，绝不按名加载。

### 测试

- 新增 `test_func_declaration_value_is_curriable` 与
  `test_func_declaration_first_class_in_list`（`tests/test_native.py`）：
  覆盖偏应用、绑定后再调用、经列表一等调用；修复前确定性崩溃，修复后通过
  且与 VM 输出一致。
- 新增 `test_gc_survives_many_cycles_small_heap`（`tests/test_native_heap.py`）：
  把 `HEAP_SIZE` 调小到 `0x200000`（2MB）使程序反复穿越数十轮 GC，验证
  2000 结点的多层存活图在大量回收后仍完整。原生四套件 **810 passed**，
  全量 **2449 passed**。

## 原生后端：修复标记栈扩容的保存槽覆写（`mark_stack_grow`）

**日期**：2026-10-12

### 变更范围

`mark_stack_grow`（标记栈跨越单个 16MB chunk 时扩容）把 `rax..r11` 等易失
寄存器保存到 `[rsp-8..]`（base=4=rsp），随后内部的 `call VirtualAlloc` 会用
返回地址/被调栈帧覆盖这些槽位；恢复出的 `rax`（即越界那次入栈的对象指针）
是 `call` 的返回地址（`.text` 地址），写入标记栈槽后该对象被标记却**从不扫
描**，其后代被后续 GC 误回收。此缺陷与上一轮修复的 `heap_extend` 同源，但更
隐蔽：`gc_scan_object` 把 `.text` 地址当作未知类型（size 0）而静默跳过，
故常规用例不崩、不报错。

### 关键实现

- 保存/恢复槽位由 base 4（rsp）改为 base 5（rbp），即 `[rbp-8]`..`[rbp-56]`，
  与 `heap_extend` 一致。函数已 `and rsp,-16; sub rsp,0x60`，`[rbp-0x38]` 以上
  均在已分配帧内。

### 测试

- 新增 `test_mark_stack_growth_preserves_live_graph`：把 `MARK_CHUNK` 调小到
  `0x1000`（512 槽）以在轻量程序中触达扩容，构造「外层列表 → 900 个子列表
  → 各含一个字符串」的存活图并触发 GC（分配 >1GB），断言 900 个后代全部存活
  （无 `None`）。经 A/B 校验：修复前该用例确定性失败，修复后通过。原生四套件
  合计 **810 passed**，全量 **2446 passed**。

## 原生后端：1GB 固定堆 + 16GB 动态竞技场（无界增长）

**日期**：2026-10-12

### 变更范围

固定的 1GB 镜像内堆之上，新增启动期预留的 **16GB 连续动态竞技场**，单个存活
分配与存活集总量均可越过 1GB；固定区与动态区**地址连续、协同工作**（固定区
服务常规分配，动态区按 16MB chunk 按需提交）。此前单个 >1GB 的分配确定性
OOM（如 `range(0, 140000000)` 约 1.12GB）。

### 关键实现

- **三节布局**：`.text` / `.bss`（GC 位图、异常栈、兜底标记栈，纯零不物化）/
  `.data`（标量 + 静态对象 + 末尾 1GB 固定堆）。`.data` 为末节，其**绝对末梢**
  向上取整到 64KB 即 `SizeOfImage`，也就是动态区预留起点（`dyn_base`）。
- **`heap_init`**（`_start` 调用）：`VirtualAlloc(dyn_base, 16GB, MEM_RESERVE)`
  预留连续竞技场；再预留标记栈区并提交首个 16MB chunk。
- **`heap_extend`**：`alloc_slow` 在 bump 越界时逐 chunk `MEM_COMMIT`（每次
  16MB，夹到 `dyn_end`），返回成功/耗尽；`alloc_slow` **循环扩展**直至当前块
  容纳得下——故单个超过一个 chunk 的大分配也能满足。
- **判据用 `heap_used = heap_ptr - heap_base`**（分配时更新），把「是否堆指针」
  的位图边界限制在实际已用量内；因无 imm32 符号扩展，大 span 比较一律走内存
  操作数 `cmp r64,[rip+heap_used]`。
- `_APIS` 经 PEB 名解析新增 `VirtualAlloc`；`_start` 先设
  `heap_limit = heap_free + HEAP_SIZE`，`heap_init` 成功后再前移到 `dyn_base`。

### 修过的坑（均为本轮定位）

- **禁用了 ASLR**：镜像无重定位表却带 `DYNAMIC_BASE|HIGH_ENTROPY`，Windows 会把
  镜像加载到**非 64KB 对齐**的随机基址，使运行时按绝对地址 64KB 对齐算出的
  `dyn_base` 落回镜像内部，`VirtualAlloc` 预留失败。清掉这两个位（仅留
  `NX_COMPAT`）后固定加载到 `0x140000000`，`dyn_base` 恰等于 `SizeOfImage`。
- `heap_extend` 曾把「新末端」存到 `[rsp-8]`，被紧接着的 `call` 压入的返回地址
  覆盖；改用 `[rbp-8]`。
- `alloc_slow` 的 bump 路径曾把 `heap_used` 设为**旧**堆顶（`rdx` 被
  `lea heap_base` 覆盖），使刚分配的大对象被判为「非堆指针」（`len` 误得 0）。
  改为从 `[heap_ptr]` 重取新堆顶。

### 测试

- 新增 `test_single_allocation_beyond_1gb_uses_dynamic_arena`（1.12GB 列表）、
  `test_multiple_allocations_span_fixed_and_dynamic_regions`（两个 1.2GB 列表，
  合计 >2GB，地址连续）。
- OOM 用例改为超过「1GB + 16GB」总跨度（`range(0, 2500000000)`），仍确定性
  终止（stderr 诊断 + 退出码 1）。原生四套件合计 **809 passed**。

## 原生后端：堆上限 8MB → 1GB（虚拟零尾 + 按需提交页）

**日期**：2026-10-12

### 变更范围

此前原生后端的堆是 `.data` 段里固定的 **8MB** BSS，存活集略超 8MB 即确定性
OOM。本变更把保留区放大到 **1GB（128×）**，并让巨大的零区不再写进文件、
也不在编译期物化进 Python 内存。

### 关键实现

- **虚拟零尾**：`_Emitter` 新增 `emit_virtual(n)` / `virtual_len`：`.data` 尾部的
  恒零运行时状态（堆 free 区、64KB 异常栈、两片 GC 位图、标记栈）只记尺寸，
  不追加字节；`align`/`label_here`/`patch` 均按「实字节 + 虚拟尾」计算 RVA。
- `_build_pe` 用独立 `data_vsize` 填节表 VirtualSize 与 SizeOfImage；
  SizeOfRawData 仍截到首个尾零之前，加载器按规范补零。RVA 布局逐字节不变，
  故 ~65 处 `(v - heap_base) < HEAP_SIZE` 指针判据与 ~65 处 `lea heap_base`
  引用**无需改动**。
- 常量随手放大：`HEAP_SIZE = 0x40000000`；`GC_BITMAP_BYTES = HEAP_SIZE//64`
  （各 16MB）；`GC_MARK_STACK_ENTRIES = HEAP_SIZE//16`；OOM 文案随 `HEAP_SIZE`
  动态生成。

### 依据 / 代价

- 实测（`GetProcessMemoryInfo`）：1GB 保留堆的空转进程 commit 仅 ~0.1MB ——
  Windows **不预提交**镜像未初始化尾段，物理页按需分页。故放大保留区运行时
  几乎零成本，仅镜像 VirtualSize 增长，文件仍 ~104KB。
- **加载器 2GB 上限（本轮新发现）**：Windows 拒绝 SizeOfImage ≥ ~2GB 的 PE
  镜像（`OSError: [WinError 193] …不是有效的 Win32 应用程序`；实测 1979.9MB
  可加载、2013.4MB 失败）。故标记栈容量不能取 2× 余量：每对象至多入栈一次
  （`mark_bits` 保证幂等），`HEAP_SIZE/16` 已是精确上界，取 `HEAP_SIZE//16`
  即可，镜像停在 ~1.6GB。

### 测试

- 新增 `test_heap_grows_beyond_old_8mb_limit`（16MB 存活列表）、
  `test_gc_collects_cumulative_allocation_over_1gb`（累计分配 >1GB 靠 GC 回收）；
  OOM 用例改为 1.12GB 请求。既有 GC/复用用例仍通过（堆变大后不再必然触发 GC，
  由上述新用例补足）。


## 原生后端：任意精度整数（BigInt 运行期对象）

**日期**：2026-10-12

### 变更范围

PE64 原生后端（`src/mbc/native.py`）新增运行期任意精度整数，消除「原生整数
恒为 int64」的溢出局限。VM 本就是任意精度 Python int，本改为向 VM 靠拢。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `a**b`（如 `a=2;b=100`） | int64 回绕/错误 | 任意精度 BigInt，打印/比较/负数/`str`/`type_of` 均正确 |
| `x*x`、`x+1`（超 int64） | 回绕 | 溢出时自动提升为 BigInt（`jo` → 提升路径） |
| 源码中的超 int64 **字面量常量**（如 `12345678901234567890`） | 编译期回绕为 int64 | 数据节生成静态 BigInt 对象，按任意精度使用 |
| BigInt 参与 `== != < <= > >=` | 崩溃（0xC0000005）或错值 | `bi_cmp` + `setCC` 正确比较 |
| 容器内 BigInt（`[a**b, ...]`、字典值）、GC | — | 纳入 `value_to_str`/`gc_obj_size`，反复分配触发 GC 不崩溃 |

### 表示与算法

- 对象布局：`[0]=TYPE_BIGINT(11) [8]=nlimbs [16]=sign(0/1) [24+i*8]=limb i`，
  基 `10^9`，低位在前，符号-绝对值。规范形：无前导零 limb；能装进 int64 的
  值一律降级为裸 int64，故「堆上的 BigInt」必然超出 int64。
- 例程：`bi_alloc/bi_from_i64/bi_trim/bi_normalize/bi_to_str/bi_neg/bi_mag_cmp/
  bi_add/bi_sub/bi_mul/bi_cmp/bi_pow_i`。`bi_trim` 在每次 `bi_mul` 后裁剪高零
  limb，避免指数级 limb 膨胀（原 OOM 根因）。
- 常量：`_bigint_static_limbs()` 把超 int64 的 Python 常量拆为 `bob:{i}` 静态
  对象写入数据节；`PUSH_CONST` 据此 `lea` 而非 `mov imm64`。

### 本轮修复的编码/逻辑缺陷

1. `bi_to_str` 序言 `sub rsp` 误用 imm8（`48 83 EC 80` 被符号扩展为 `-128`）→ 改 imm32 `48 81 EC 80 00 00 00`。
2. `bi_to_str` 的 `signlen` 局部（`[rbp-48]`）对正数未初始化 → 读到栈垃圾致巨大分配；改为先清零。
3. `bi_to_str` 总位数计算遗漏 `mov rax, r8`（`imul rax, rax, 9` 前）。
4. `bi_cmp` 负数翻转误写 `neg rcx` → `neg rax`。
5. `+` 的 int64 溢出路径未复原 `rax`（提升前应等于左操作数）→ 新增 `laddovf` 标签复原。
6. `**`：`_emit_bigint_binop` 已把底数提升为 BigInt，`bi_pow_i` 内又 `bi_from_i64` 二次转换（对对象指针取垃圾）→ `bi_pow_i` 直接接收 BigInt 底数。
7. BigInt 比较分支误用 **Jcc** 操作码（`0F 8x`）当 `setCC`（`0F 9x`），产生 `je rel32` 越界跳转 → 改用 `_CC`（`setCC`）表。

### 语义边界（本轮不扩展）

- `// %` 及位运算/移位遇 BigInt 仍抛可捕获错误 `大整数不支持该运算`（`err_bigintop`，退出码 1）；`**` 遇 BigInt 指数或负指数+BigInt 底同理。原生 int64 路径不变。
- 已知遗留（非本改）：`函数(x) … 结束` 表面语法对**任意**参数（含普通 int）均崩溃，属前端解析问题，与本 BigInt 增量无关。

### 验证

`tests/test_native.py`（新增 31 项 BigInt 用例：算术/比较/容器+GC/拒绝路径，及 5 条 VM↔AOT parity）+ `test_native_heap.py` + `test_interp_parity.py` 共 **782 passed**。

## 原生后端语义对齐 —— 深层相等、可捕获的越界/属性错误、补齐内建（含 `?.` 可选链）

**日期**：2026-10-12

### 变更范围

PE64 原生后端（`src/mbc/native.py`）向 VM 语义靠拢的三组修复：

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `[1,3] == [1,4]` | 原生按对象长度（元素个数）逐字节比 → 误判为 `真` | `val_eq` 深层结构相等 → `假` |
| `[[1,3]] == [[1,3]]` | 误判为 `假` | `真`（列表/字典/字符串逐元素递归；整数↔浮点↔布尔按数值比较，NaN≠NaN） |
| 列表/字符串下标越界 | 静默返回 `None` | 经 `raise_rt` 抛 `list/string index out of range`，可被 `try…catch` 捕获；未捕获写 stderr、退出码 1 |
| 非字典属性访问 `3.z` | 静默返回 `None` | 抛 `属性访问失败: 非字典对象`，可捕获 |
| `print(...)` | 未实现 → 调用崩溃 | `输出` 的别名（LOAD_GLOBAL 期改写） |
| `去重(xs)` | 未实现 → 调用崩溃 | 按 `==` 去重保序；非列表抛可捕获异常 |
| `安全索引(c)(k)` | 未实现 → 调用崩溃 | 越界/缺键/不可下标返回 `None` |
| `安全取属性(o)(name)` | 未实现 → 调用崩溃 | 非字典/`None` 返回 `None`；字典缺键返回 `None` |
| `a?.b` / `a?.[i]` 可选链 | 脱糖到未实现的 `安全索引`/`安全取属性` → **原生端整段崩溃** | 正常工作 |

### 语义决定

1. **深层相等只用于 `==`/`!=`**：`val_eq` 为自包含递归例程，浮点比较用
   `setnp`+`sete` 排除 NaN。集合去重（`list_dedup`）本就经 `val_eq`，故
   `{([1,3]), ([1,3])}` 现按结构去重。
2. **「越界/属性错」改为抛异常而非 `None`**，与 VM 一致；`安全索引`/`安全取属性`
   则保留「不抛、返回 `None`」语义（VM `_builtin_safe_index`/`_builtin_safe_attr`），
   二者分工不重叠——`_emit_getitem` 新增 `raise_oob` 开关复用同一取值核心。
3. **字典缺键索引仍返回 `None`**（VM 抛 `KeyError`），登记于
   `tests/test_native_heap.py::test_dict_missing_index_returns_none`，本轮不动。

### 验证

`tests/test_native.py` 521 + `tests/test_native_heap.py` 136 + 编码/前端/brick19/
多语言/集合理解 288 + `test_interp_parity.py` 94 全绿；新增
`test_native_print_alias` / `test_native_dedup_raises_on_non_list` /
`test_native_safe_index_and_attr_never_raise` / `test_native_optional_chaining` /
`test_native_deep_equality` / `test_native_nested_set_dedup` /
`test_list_index_oob_raises_catchable` / `test_string_index_oob_raises_catchable` /
`test_uncaught_index_oob_exits_one` / `test_non_dict_attr_raises_catchable` 及
VM↔AOT 对拍用例 `new_builtins`。文档同步：`docs/matha-vs-mainstream.md`、
`docs/04-数学核心（机械语言）.md` §3.1。

---

## 提交：`50b0267` 后续 — `@(...)` 括号式设定此前完全无法解析

**日期**：2026-10-06

### 变更范围

EBNF §2.4 的 `@(...)`（`|` 分格）**整条形式此前都无法通过解析**，而 `@:` 前缀形式
一直是好的——两条等价形式只有半条可用。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `@(x=1)` | `期望 ) (got EOF)` — 值的「消费完整性」检查只认逗号/换行/EOF/`|`，**漏了 `)`**，于是回退分支把 `)` 一并吞进字符串值 | 解析成功，绑定 `x=1` |
| `@(x=1\|y=2)` | `未定义变量 'y'` — `_parse_bit_expr` 把顶层 `\|` 当**位或**吃进第一项的值（`1\|y=2`），第二项从未创建 | `|` 作项分隔符，两项都绑定 |
| `@(m=(6\|1))` | 同上连带 | 嵌套分组内 `\|` **仍是位或**（恢复原语义），`m=7` |
| `*/文字*公式/*` | 不解析公式部分 | **维持不变**（见下） |

### 语义决定

1. **`@()` 顶层 `|` 是分隔符，嵌套分组内 `|` 是位或**。二者由**括号层级**消解：
   进入 `( ... )` 分组时清掉「正解析 `@()` 项」标志，退出时恢复。这样
   `@(a=1|b=2)` 分两项，`@(m=(6|1))` 的组内仍是位或，无需在两种读法间二选一。
2. **`*/文字*公式/*` 维持自由文本、`formula=None`**——不是待补的缺口。原文法的
   `[ "*" , <expr> ]` 公式形态与自由文本冲突（文本里的 `*` 会被误当公式起点，如
   `【*/计算 2*3 的和/*】`），仓库内无任何公式形态用例，且 `Annotation` 是编译期
   NOOP（不参与字节码），故此处**刻意不区分公式**。

### 验证

新增 `test_interpreter.py` 2 例（括号式四形态 + 嵌套 `|` 保留位或）。全量：
`1705 passed`（非原生）+ `510 passed`（原生）= `2215 passed`，无回归。

---

## 提交：`50b0267` 后续 — `？` 公式模式库：按「格式」统一同形公式

**日期**：2026-10-06

### 变更范围

`？` 不是运算符，而是「此处为一个变量」的**槽**。按用户确认的语义：`**#：？公式`
登记为模式进公式库（不可执行）**，具体公式与库中模式按**格式**合一。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `#：？+？=？` | 求值 → `未定义变量 '？'` | 登记为模式（公式模式库） |
| VM 执行 `#：？公式` | **`KeyError '？'`** | 登记进 VM 公式库 |
| AOT 编译 `#：？公式` | `NativeNotSupported` | 空实现（无运行期效果） |
| 表达式中的 `？name` | 被读成「万能占位符**当作函数**作用于 name」 | 具名模式槽，跨出现强制一致 |
| 具体公式命中模式 | 解释器记录合一；**VM `KeyError '单价'`**、AOT 撞未定义全局 | 三端一致：不发求值代码 |
| 槽遍历 | `FuncApp` 漏收集；列表/元组/索引字段名写错致静默跳过 | 覆盖全部表达式形态 |

### 语义决定

1. **格式即身份**。归一化形状相同的公式即**同一条公式**，登记时归并、不重复堆积。
   运算符与结合结构属于格式，槽名不属于——故 `单价+运费=总价` 与 `？+？=？` 统一，
   而 `单价*数量=总价` 不统一。
2. **裸 `？` 是匿名槽**，每次出现彼此独立；**`？name` 是具名槽**，跨出现**强制一致**
   （Prolog 变量 / Python `{name}`）。这正是 `？name` 存在的意义：它给形状加上
   等式约束，故 `？a + ？a = ？b` 接受 `面积 + 面积 = 周长` 而拒绝 `x + y = z`。
   （此前解析器只在**绑定**位置遵守「`？` 可被字母替代」，表达式位置把 `？sum`
   误读成对 `sum` 施加万能占位符，报「未定义函数 FuncApp」。）
3. **两个方向的效果**：
   - *多公式一用途意图*：格式相同的任意多个具体公式合一到同一模式。
   - *一公式多用途意图*：同一模式换基础定义（换绑定）即换用途——`？+？=？`
     绑成 `收入+支出=结余` / `长+宽=周长` / `速度+时间=距离` 是同一条公式的三个实例。
4. **匿名槽无需改 AST**：`ast_nodes.Variable` 只有 `name` 与 `is_placeholder`，
   每个裸 `？` 都是同一个 `Variable('？', True)`。这里用**左到右遍历次序**充当
   匿名槽序号（1、2、3……），序号可序列化、可用于实例化。

### 关键修复

`docs/02-词法结构.md` 原文把 `#：？+？=？` 列为「运行：执行公式」，与槽语义冲突
（槽没有可求值的值，无法执行），已更正为「登记」并补上完整语义表。

### 三端分工

合一是 **AST 级**操作，故在解释器完成。编译器把模式整体常量化成
`(段号, 文本, 形状, 槽位表)` 并发新指令 `FORMULA_SCHEMA`(0x62)；VM 据此登记进
公式库；原生后端发空实现。

**具体公式命不命中模式也在编译期判定**：编译器与解释器按**同源同序**建同一套
公式库，故静态判定结果与解释器运行期判定必然一致。命中的具体公式**不发求值
代码**——否则 VM 会把 `单价 + 运费 = 总价` 当表达式求值而 `KeyError '单价'`，
AOT 同样撞未定义全局；编译期判掉之后三端 stdout 一致，且原生后端无需运行期
匹配、无需跳转指令。三端**可观察行为（stdout）一致**，模式本身对程序输出无影响。

### 测试

新增解释器 9 例（登记/不求值、同形统一、运算符属格式、具名槽一致、同形归并、
匿名独立、一公式多用途、遍历覆盖、函数与索引合一）+ VM/AOT 19 例（含三端
「命中模式的具体公式不求值」回归）。全量：`1705 passed`（非原生）+
`510 passed`（原生）= `2215 passed`，无回归。
新增模块 `src/formula_schema.py` 通过 mypy 零告警。

---

## 提交：`50b0267` 后续 — 前缀 `++`/`--` 三端补齐 + `？` 占位符等价于具名变量

**日期**：2026-10-06

### 变更范围

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| 前缀 `++`/`--` | 解释器支持，**编译器报「不支持的一元运算符」** | 三端一致 |
| AOT 运行期浮点自减 | `subsd` 结果留在 `xmm1`，而 `box_float` 只读 `xmm0`，恒得 `1.0` | 正确 |
| 表达式中的 `？name` | 被读成「万能占位符**当作函数**作用于 name」，报「未定义函数 FuncApp」 | 与绑定位置一致，等价于具名变量 |

### 语义决定

1. **`++`/`--` 是非原地运算**，语义为 `v + 1` / `v - 1`，**不修改变量绑定**：
   `let x = 5; 输出(++x); 输出(x)` 得 `6` 与 `5`（两个后端一致）。沿用解释器既有
   行为，未改造成自增/自减赋值号。
2. **`？` 不是运算符**，而是「此处为一个变量」的占位符。按 `docs/02-词法结构.md`
   占位符条与 `docs/00-前言与概述.md` L135，它**可被任意字母替代**
   （`？ = a = g1 = c3 = m1 = Z`），且 `？sum` **等价于**具名变量 `sum`。
   故不存在「与 `？` 等价的另一个符号」——`？` 的含义就等于普通标识符。

### 关键修复

1. **AOT 浮点自减恒为 `1.0`**：SSE 标量指令（`movsd`/`addsd`/`subsd`）的
   `ModRM.reg` 是**目的**操作数，与 GPR 指令的直觉相反。原写法
   `subsd xmm1, xmm0`（ModRM `C8`）把结果留在 `xmm1`，而 `box_float` 只读
   `xmm0`，于是 `2.5` 被当成 `1.0` 装箱。现改为把 `1.0` 放入 `xmm1`、让
   `xmm0` 作被运算数并保留结果（`addsd/subsd xmm0, xmm1`，ModRM `C1`）。
2. **`？name` 在表达式位置不生效**：解析器此前只在**绑定**位置按「`？` 可被字母
   替代」处理（`？sum = 0` 一直绑定 `sum`），表达式位置则把 `？sum` 读成对 `sum`
   施加万能占位符。新增 `_parse_placeholder_var`，`？` 后紧跟标识符时合成一个
   **以该名字为名**的占位变量，两条路径一致。

### 已知限制

裸 `？`（不带名字）在表达式中仍无定义：它表示公式模板上的「洞」，没有可求值的
值，报「未定义变量 '？'」。`docs/02` 的既有约定是在需要数字处（如循环分数
`(？/？)`）把 `？` 记为「待定」`-1`；`#：？+？=？` 这类**模板求值**语义待定，
本次未擅自实现。

### 测试

新增解释器 / VM / AOT 三端对拍用例（`++`/`--` 共 11 例含运行期浮点与嵌套角度、
`？` 占位符 5 例）。该步提交时全量 `1696 + 491 = 2187 passed`，无回归；
（后续 `？` 模式库并入同一批改动，最终全量见本文件首条目）

---

## 提交：`50b0267` 后续 — `<<` 角度前缀三端补齐 + AOT 浮点取反/`~bool` 修复

**日期**：2026-10-06

### 变更范围

补齐 `docs/06` 级 6 的 `<<` 角度前缀在**解释器 / MBC VM / 原生 AOT** 三端的缺失。
排查过程中发现并修复了两个**先前存在**的原生 AOT 算术 bug（浮点取反、`~bool`）。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `<<n` 角度前缀 | 仅文档描述，三端均不支持 | 三端一致，度数 → 弧度 |
| `<<-90` 等前缀叠加 | 解析器报「期望表达式」 | 任意层 `<<`/`-`/`~`/`^` 叠加可用 |
| AOT 运行期浮点取反 | **静默算错**（`-1.5` → `-1.0`） | 正确 |
| AOT `~bool` | **输出堆指针**（`~真` → `-140699650725569`） | `-2`（对齐 `~int(v)`） |
| AOT `<<` 非法类型 | 静默返回 `null` | 抛可捕获异常 |

### 语义决定

`<<n` 归一化为**弧度数值**而非独立 `Angle` 类型。依据是 docs/06 的示例
`sin(<<30)`：三角内建只吃弧度，故 `<<30` 必须先除以 180 再乘 π 才能得 0.5。
因此 `输出(<<90)` 为 `1.5707963267948966` 而非 `90`。

### 关键修复

1. **`f_deg` 尾部指令错误导致 `0xC0000005`**：新 helper 曾以 `pop rbp; ret`（`5D C3`）
   收尾，在 `box_float` 返回后使进程崩溃。本文件其余 helper（`f_sqrt` / `f_neg` /
   `f_pow`）一律用 `mov rsp,rbp; pop rbp; ret`（`48 89 EC 5D C3`）。修正后 `<<90`
   正常输出 `1.5707963267948966`。
2. **`movsd` 操作数写反**：`F2 0F 10 C1` 的 ModRM `C1` 是「`xmm0 = xmm1`」，会把
   刚算出的度数丢掉、拿未初始化寄存器去乘。应为 `C8`（`xmm1 = xmm0`），与本文件
   `bin_to_xmm2` 的写法一致。
3. **原生浮点取反全错**（先前存在）：`neg` 分支 `read_top_to(0)` 后调 `is_float`，
   而 `is_float` 以 `mov eax,1` / `xor eax,eax` 返回，**rax 被整个清掉**；浮点路径
   再调 `f_neg` 时操作数已成 0/1，于是 `f_neg(1)` = `-1.0`。字面量 `-1.5` 因常量
   折叠不受影响，故长期未被发现。现于浮点路径从栈槽重新读回。文件内其余
   `is_float` 调用点（`_emit_builtin_math_round`/`abs`/`sign`/`int`/`float`、
   `sum`/`max` 循环、`is_float2` 内部、`f_sqrt`）均已核查为安全。
4. **`~bool` 把堆指针当整数**（先前存在）：bool 在原生端是 `bool_true` /
   `bool_false` 两个内部对象的指针，`not rax` 得到 `-(ptr+1)`。现按指针还原成
   0/1 再取反，与解释器/VM 的 `~int(v)` 对齐。
5. **前缀操作数解析**：新增 `_parse_unary_operand()` 递归处理 `<<` / `-` / `~` /
   `^`，使 `-<<90`、`<<-90`、`^<<16` 均可解析；中缀 `<<` 位移不受影响。
6. **AOT 判浮点不用 `is_float`**：`<<` 分支改为自判「是否落在堆区间」+ 查
   `TYPE_FLOAT` 标签，避免上述 rax 被清空问题。

### 测试

新增 69 项回归：`test_new_features.py` 角度语义 7 项、`test_interp_parity.py`
解释器/VM 对拍 19 项、`test_native.py` AOT 角度 13×2 + 角度报错 3×2 +
运行期浮点取反 5×2 + `~bool` 3 项。
全量 pytest **2133 passed**（此前 2064）。

---

## 提交：`50b0267` 后续 — 位运算族三端补齐 + 中缀 `^` 回归规范

**日期**：2026-10-06

### 变更范围

以 `docs/17-完整语法EBNF.md` 与 `docs/06-表达式与运算符.md` 为基准，补齐位运算
`&` `|` `⊕` `~` 在**解释器 / MBC VM / 原生 AOT** 三端的缺失，并修正中缀 `^` 的
语义与优先级。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `&` 位与 | 仅解释器 | 三端一致 |
| `\|` 位或 | 仅解释器 | 三端一致 |
| `⊕` 位异或 | 仅解释器，且与 `^` 混用同一 token | 三端一致，独立 `TokenType.OP_XOR` |
| `~` 位取反 | 仅解释器 | 三端一致 |
| 中缀 `^` | 解释器当异或、VM/原生当次方 | **三端统一为次方**（EBNF 2.1 `<power> = "^"`） |
| `^` 结合性 | 左结合 | **右结合**（docs/06 级 5） |
| `^` 优先级 | 低于 `*` | **高于 `*`**（级 5 > 级 4） |
| `~` 作用于 bool | 依赖 `~True`，Python 3.16 将移除 | 显式 `~int(v)`，无弃用告警 |

### 关键修复

1. **`^` 双后端语义冲突**：`src/mbc/compiler.py::_BIN_OPS` 早已把 AST `^` 归约为
   `**`，而 `src/interp.py` 按位异或处理，同一段 `2 ^ 3` 解释器得 1、VM/原生得 8。
   现按规范统一为次方；异或改用专用符号 `⊕`（新增 `TokenType.OP_XOR`，此前
   `⊕` 与 `^` 共用 `OP_BIT_XOR` token，故 `^` 改动会连带影响 `⊕`）。
2. **`^` 结合性与优先级**：`^` 原留在 `_parse_bit_expr`（位运算层），导致
   `2 ^ 3 ^ 2 = 64`（应 512）、`2 ^ 3 * 2 = 64`（应 16）。现移至
   `_parse_pow_expr` 与 `**` 同层，右结合且优先于 `*`。
   docs/06 的示例 `2^2^3 = 2^(2^3) = 256` 现已成立（此前为 64）。
3. **原生 AOT 位运算**：`& | ⊕` 用 `and/or/xor rax,rcx`（`21 C8` / `09 C8` /
   `31 C8`）；`~` 用 `not rax`（`48 F7 D0`）。两侧非整数时走 `raise_rt` 抛可捕获
   异常，而不是把堆地址当整数按位算出垃圾值，也不返回 `null_obj`（后者会把类型
   错误伪装成「无值」）。
   注意原生后端的整数是**裸 int64 而非堆对象**，故判据必须用
   `(rax - heap_base) < HEAP_SIZE`，不能按类型标签解引用 `rax`——早期误用
   `mov edi,[rax]` 直接触发 `0xC0000005` 访问违例。
4. **VM 侧新增** `_bitop()` 校验与 `~` 一元表项，错误类型沿用本模块惯例
   （`RuntimeError`），消息与解释器对齐。

### 语法变更（面向用户）

- 异或请用 `⊕`，不要用 `^`。旧的 `a ^ b`（原意异或）需改写为 `a ⊕ b`。
- `^` 前有操作数为次方（右结合、优先于 `*`），前无操作数仍为开方。

### 测试

新增 57 项回归：位运算族三端对拍 15 项、`^` 规范用例、docs/06 示例核对、
原生 AOT 位运算 26 项、非整数操作数报错与可捕获性 14 项。
全量 pytest **2064 passed**（此前 2007）。

---

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

### 2.2 x86-64 原生发射器 (`src/mbc/native.py`, 约 1610 行)

**完整管线**：Matha 源码 → AST → M3V 字节码 → x86-64 机器码 → PE64 可执行文件

- **PEB 遍历自解析 kernel32 导出**（不依赖 PE 导入表，加载器兼容性最大化）
- 已支持的运行时能力（按「砖块」推进，每块有 `tests/test_native*.py` 覆盖）：
  - 砖块 0 基线：整数算术 `+ - * // %`、比较 `== != < > <= >=`、一元 `neg not`、
    控制流 `JMP JZ JNZ`（及 `and`/`or` 短路改写）、单参递归、整数十进制输出、进程退出
  - 砖块 1 多参数函数：序言按 arity 搬移入参（上限 `MAX_NATIVE_ARITY=8`）
  - 砖块 2 偏应用/柯里化：`apply_rt` 运行时 + `TYPE_PARTIAL` 记录
  - 砖块 3 堆与字符串：8MB bump 堆、对象头 `[type][len][payload]`、
    字符串拼接/比较/输出/repr、静态串对象
  - 砖块 4 列表：`BUILD_LIST` / `INDEX_GET` / `print_list` / `len`
  - 砖块 5 字典：`BUILD_DICT` / `dict_get` / `GET_ATTR` / `print_dict`
  - 砖块 6 整数幂 `**`（负指数提升为浮点幂，详见 3.5.4）
  - 砖块 7 闭包/盒/外域：`MAKE_CLOSURE` + 环境链、捕获静态分析、
    `LOAD_OUTER(_BOX)`、`MAKE/STORE/LOAD_BOX`、`R13` 环境寄存器
- 砖块 8 切片 `BUILD_SLICE`：`y[1:3]` / `y[2:]` / `y[:2]`，负下标归一化后钳到
  `[0, len]`，列表浅拷贝、字符串按字节切；非序列容器返回 `None`
- 砖块 9 解构 `UNPACK_SEQ`：`let (a, b) = …` 与 `for (i, j) in …`，
  缺项补 `None`，非序列全为 `None`
- 砖块 10 异常：`raise` / `错误(msg)` / `try-catch-finally`。处理器链存于
  `.data` 的 `hstack`，`raise_rt` 恢复 `rsp/rbp/r12/r13` 后长跳转回落地标签；
  `调用捕获` 为柯里化内建（arity 2），返回 `["__正常__", 值]` /
  `["__异常__", 消息]`；未捕获异常把 `str(值)` 写 stderr 并以退出码 1 结束
- 砖块 11 浮点：真除 `/` 恒返回 float，浮点 `+ - * / // % **`、比较
  `== != < > <= >=`、一元 `neg`。装箱 24 字节 `[TYPE_FLOAT][8][double@+16]`；
  `is_float`/`as_double`/`box_float` 复用「指针落在堆区间」判别。**浮点打印
  与 CPython `repr` 逐位一致**：`load_crt` 经 `LoadLibraryA`/`GetProcAddress`
  解析 `ucrtbase.dll`（回退 `msvcrt.dll`）的 `_ecvt`/`strtod`，`_ecvt` 取
  24 位精确十进制后按 p=1..17 做 round-half-even 舍入 + `strtod` 往返比较，
  首个可往返的 p 即最短表示，再按 `decpt<=-4 || decpt>16` 科学计数、
  `decpt<=0`、`decpt>=n`、中间四种规则拼串（指数恒 2 位且带 `+`/`-`）。
  特殊值 `inf`/`-inf`/`nan`/`0.0`/`-0.0` 单独处理
- 砖块 12 成员判断 `in` / `∈`：列表（线性扫描）、字符串（子串匹配）、
  字典（键存在性）；运行时 `seq_contains` 按对象类型分派
- 砖块 13 位移 `<<` / `>>`：整数移位
- 砖块 14 一元开方 `sqrt`（前缀 `^` / `**`）：运行时 `f_sqrt` 用 CRT
  `pow(x, 0.5)`，与 VM 的 `a ** 0.5` 逐位一致；整数且结果恰为整数时回退为
  整数（`^9 → 3`、`^16 → 4`），否则装箱浮点（`^2 → 1.4142135623730951`）；
  浮点输入恒返回浮点。负值经 `pow` 得 NaN（VM 侧为复数，属已知偏差）
- 砖块 15 浮点常量：mathlib 的 `CONSTANTS`（pi/e/tau/phi）与
  `PHYSICAL_CONSTANTS`（G/c/g/h_planck/N_A/R）发射为静态 `TYPE_FLOAT` 对象
  （`int` 值如 `c` 走裸整数），`LOAD_GLOBAL` 解析；此前单字母常量会静默读成 0
- 砖块 16 阶段一 数值 + 转换核心：
  - 一元数学 `sin/cos/tan/asin/acos/atan/sinh/cosh/tanh/exp/log/ln/log10/log2/sqrt`
    （恒浮点，复用 CRT、对齐 mathlib 的 `math.*`；可调用 `sqrt` 恒浮点，
    与一元 `^` 的整数完全平方回退不同）
  - 取整 `floor/ceil/trunc`、`round`（CRT `rint`，对齐 Python 半偶舍入）
  - `abs`/`sign`/`deg2rad`/`rad2deg`，二元柯里化 `pow`/`atan2`/`hypot`
  - 转换 `int`/`_to_int`/`float`/`_to_float`/`str`/`bool`
  - 类型 `type_of`（英文名）/`typeof`（中文名）；修复 `typeof` 关键字此前
    经 `LOAD_GLOBAL` 读 0 后调用即崩的潜在 bug
- 砖块 16 阶段二 序列 + 字典原语（不可变语义，浅拷贝）：
  - `slice(容器)(start)(stop)`（复用 `build_slice`，越界钳制、负下标归一）、
    `append(xs)(elem)`（新列表，非列表视作空列表 `[elem]`）、
    `mut_set_at(lst)(idx)(val)`（原地改列表，越界/类型错返回 `null`）
  - `_dict_keys`/`_dict_values`（新列表，按 VM 逻辑顺序 = 物理 pair 逆序）、
    `_dict_has`（布尔对象）、`_dict_put`（新字典：已有键原位更新，新键物理
    首位 ↔ VM 逻辑末尾）、`_dict_remove`（过滤生成新字典）、
    `_empty_dict`（静态空字典对象，值而非可调用）
- 砖块 16 阶段三 基础原语 / 序列构造 / 文件 I/O / 进制编解码：
  - `ord`/`chr`（UTF-8 首码点解码 / 码点编码，对齐 VM 的 Unicode 码点）；
    `list`（列表浅拷贝 / 文本→单字节列表 / 字典→键列表 / 其余→`null`）；
    `range(start)(end)`（stdlib 2 参闭开区间；VM 纯源码 2 参调用报错，
    故仅原生端定点断言，无法与 VM 对拍）
  - 文件 I/O `_read_file`/`_write_file`/`_append_file`（CRT `fopen`/`fread`/
    `fwrite`/`fseek`/`ftell`/`fclose`，字节 utf-8，失败静默返回 `null`）
  - 进制编解码 `encode_`/`decode_binary`·`ternary`·`decimal`（逐 Unicode
    码点，空格连接 / 空白切分）
- 砖块 17 阶段一 mathlib 数论 / 聚合：
  - 数论 `阶乘`（i64，`n>20` 溢出；`n<0 → 0`）、`最大公约数(a)(b)`、
    `最小公倍数(a)(b)`、`排列数(n)(r)`、`组合数(n)(r)`（`n<r → 0`）、
    `素数判定(n)`、`素数筛(n)`（素数字列表）、`杨辉三角(n)`（前 `max(n,1)` 行，
    `n<=1 → [[1]]`）
  - 聚合 `max`/`min`（列表→极值元素并保留类型；非列表→原值）、`sum`
    （整数累加保持整数，出现浮点则整体浮点，对齐 Python `sum`）
- 砖块 17 阶段二 mathlib 逻辑 / 集合：
  - 逻辑 `逻辑非(p)`；`逻辑与`/`逻辑或(a)(b)`（短路返回操作数，对齐 Python）、
    `逻辑蕴含(p)(q)=(not p) or q`、`逻辑异或(p)(q)=(p or q) and not(p and q)`、
    `逻辑双蕴含(p)(q)=(p==q)`（`val_eq`）
  - 集合 `集合并`/`集合交`/`集合差`/`集合补(a)(b)`（`ml_setify` 去重 +
    有符号整数升序，对齐 `set()`+`sorted`；集合补=集合差(全集)(子集)）、
    `集合子集(a)(b)`、`集合基数(s)=len(set(s))`、`集合幂集(s)`
    （第 `k` 项含元素 `i` 当且仅当 `k` 的第 `i` 位为 1，对齐 `_power_set`）
- 砖块 17 阶段三 mathlib 统计 / 随机：
  - 统计（确定性，与 VM 逐行对拍）`平均值(lst)`（空→int 0，否则 float）、
    `中位数(lst)`（数值插入排序，奇数→原元素、偶数→`(a+b)/2`，空→0）、
    `方差(lst)`（空→int 0）、`标准差(lst)`（恒 float，空→0.0）、
    `协方差(a)(b)`（长度不等/空→int 0）、`相关系数(a)(b)`（`sx==0` 或
    `sy==0`→int 0）、`正态密度(x)(mu)(sigma)`（`sigma<=0`→int 0，CRT
    `sqrt`/`exp`）。连续求和用 `ml_neumaier_add` 复刻 CPython 3.12+ `sum()`
    的补偿求和，浮点结果与 VM 逐位一致
  - 随机（非确定性，仅原生定点断言）`均匀随机(a)(b)=a+(b−a)·rand`、
    `正态随机(mu)(sigma)=mu+sigma·z`（Box-Muller）；`ml_rand` 为 xorshift64，
    首次以 `rdtsc` 播种（CRT 无 rand/srand）
- 砖块 18 堆 GC（保守式非移动 mark-sweep）：
  - 触发点：`alloc` 快路径发现空闲表非空或 bump 越界时跳 `alloc_slow`；
    冷路径「查空闲表 → 回收 → 再查 → bump」。快/冷路径均维持 `alloc` 调用
    契约（除 rax 返回值外不破坏调用者寄存器）
  - `start_bits`/`mark_bits` 各 1 bit/8 字节（128KB），显式标记栈
    `mark_stack`（1M 槽）；对象尺寸按类型标签精确推导，对象体
    `[obj+8,obj+size)` 逐字保守扫描
  - 根集：操作数栈 `[vstack,r12)`、CPU 栈 `[rsp,stack_top)`（含 `alloc_slow`
    保存的全部 GP 寄存器）、`raise_msg`、全局变量单元
    `[cells_begin,cells_end)`、异常处理器栈 `[hstack,hstack_ptr)`；
    `stack_top` 于 `_start` 记录
  - `sweep_start` 在 `main_entry` 内建闭包初始化后设置，令 `bclo:*`（永久
    全局闭包）与堆内静态对象（字符串/浮点/布尔/空字典）从不回收
  - sweep 仅遍历 `[sweep_start,heap_ptr)`：存活标记者保留，其余死亡对象按地址
    连续者合并为单块后挂入空闲表（块头 `[size][next]`）；空闲表始终按地址升序，
    回收时借单调游标把新块与前/后相邻空闲块再做地址级合并，分配时 first-fit
    并切分剩余块（split + coalesce）
  - 堆耗尽（GC 后仍无可用块且 bump 越界）时经 `print_uncaught` 写 stderr
    诊断「内存不足」并以退出码 1 终止；不再越过 `heap_limit` 覆写
    `start_bits`/`mark_bits`（旧行为会静默损坏，随后 GC 崩溃）
  - 已在 >8MB 累计分配场景经 100 万次非恒定分配、全局列表/字典/闭包跨
    GC 存活验证
- 砖块 19 嵌套文本 repr 对齐 CPython：
  - 新增运行时 `str_repr_body`（`rax`=STR 对象）：按 CPython `repr` 规则打印引号
    包裹的字符串 —— 引号选择（串内含 `'` 且不含 `"` → 用 `"`，否则用 `'`）、转义
    （当前引号字符与反斜杠前加 `\`；`\n`/`\r`/`\t` → `\\n`/`\\r`/`\\t`；其余
    `<0x20` 或 `0x7F` 字节 → `\xNN` 小写十六进制；`≥0x80` 字节原样透传以覆盖
    UTF-8 多字节/CJK/emoji）；连续普通字节按 run 批量写出
  - `print_list` 元素与 `print_dict` 值改经 `print_repr`（键原已如此）；顶层
    字符串输出仍走 `print_value`（= Python `str()`，无引号），与 VM 一致
  - 新增 `write_span(rdx=ptr,r8=len)` 低层写原语（保留 `r10`/`r11`）供 repr 逐段输出
  - `str(列表/字典)`：两遍渲染对齐 CPython 的 `str == repr` —— 新增输出汇全局
    `out_mode`/`out_count`/`out_buf_ptr`，`write_span`/`print_raw`/`print_int` 统一
    路由到汇：先计数（`out_mode=1`）得到精确字节数、分配目标 STR，再填充
    （`out_mode=2`）；容器与结果对象存帧局部作 GC 根（非移动 GC 下缓冲游标稳定）
  - `list(文本)`：改为按 Unicode 码点（UTF-8 前导字节定宽：1/2/3/4 字节）切分，
    对齐 VM（此前按单字节切分，非 ASCII 上输出错误）
  - 集合字面量 `{}` / `{1,2,3}`：新增 arity-3 内建 `构造集合(form)(variables)(elements)`
    与运行时 `list_dedup`（按 `val_eq` 去重、保序），对齐 VM `_builtin_make_set`
    （忽略 form/variables）。此前 `{}` 未在原生内建表注册，`LOAD_GLOBAL` 取到未初始化
    全局单元后以空地址 `CALL 3`，直接访问违例（0xC0000005）
    - 刻意分歧：`elements` 非列表时原生降级为空列表，VM 抛 `TypeError`（原生运行时无
      语言级异常机制，同 `len`/`append`；编译器恒传列表）
  - **集合理解 `{x | cond}` 仍整体未实现（三后端一致，非本次回归）**：解析器把 `|`
    归约为位或、链式比较 `1 <= x <= 10` 与生成子 `x >> S` 均解析报错、VM `_BINOPS`
    无 `|`、`_builtin_make_set` 无变量绑定/过滤。现报编译错误「不支持的二进制运算符
    '|'」属显式失败；仅修解析会令 `{x | x > 5}` 静默返回 `[False]`，故不修
- 尚未支持（编译期抛 `NativeNotSupported`）：`MathaIOError` 等非原生名字
  （mathlib 全部函数已实现）
- 结构性限制：操作数栈固定 64KB、8MB 堆（保守式 mark-sweep GC，非移动，
  空闲块可切分/相邻合并）、索引越界静默返回 0、
  仅生成 Windows PE64（无 ELF64/Mach-O）
- 手写 PE64 链接器：2 节（.text EXEC/.data RW），无数据目录；
  `.data` RVA 按 `.text` 实际大小动态对齐（固定值会在代码 >4KB 时与 `.text` 重叠）

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

### 3.1 x86-64 机器码编码

| Bug | 位置 | 现象 | 修复 |
|-----|------|------|------|
| 尾声 ModRM 方向反 | `native.py` `_emit_epilogue`（约 258 行） | `0xE4`(mov rbp,rsp) 导致 ret 跳 0 崩溃 | → `0xEC`(mov rsp,rbp) |
| 序言 REX.X 误置 | `native.py` `_emit_prologue`（约 235 行） | `0x4F` 使 SIB 无索引变 r12+r12 | → `0x4D`(REX.X=0) |
| CALL 栈不平衡 | `native.py` `_emit_call`（约 267 行） | 返回值未覆盖函数槽 → BINOP 读到指针 | mov [r12-16],rax + sub r12,8 |
| PE 节区重叠 | `native.py` `_build_pe` | `DATA_RVA` 为固定常量 0x2000，代码 >4KB 时 `.text` 与 `.data` 重叠，`CreateProcess` 报 WinError 193 | `.data` RVA 按 `.text` 实际大小动态对齐到 SectionAlignment |
| 成员判断跳转错编码 | `native.py` `_emit_in_rt` | `jcc_rel32(0x77)` 发出 `0F 77`(EMMS) 而非近 `ja`，字符串 `in` 执行到垃圾指令 → `0xC0000005`（payload `0xC55`） | 两处 `0x77` → `0x87` |
| 成员判断取址基址错 | `native.py` `_emit_in_rt` | `48 8B 7F D8` 以 `rdi` 为基址取针，读到越界地址 → `0xC0000005`（payload `0xC70`） | → `48 8B 7D D8`（`[rbp-0x28]`） |
| 成员判断寄存器方向反 | `native.py` `_emit_in_rt` | `4C 89 C9` 是 `mov rcx,r9`，剩余长度寄存器未就绪 → 恒返回 `False` | → `49 89 C9`（`mov r9,rcx`） |
| try/catch 静默段错误 | `native.py` `_UNRESOLVED_GLOBALS` | try 脱糖先 `LOAD_GLOBAL "调用捕获"`，未拒绝该名 → 载入 0 值后调用 → `0xC0000005` | 将 `调用捕获` 加入 `_UNRESOLVED_GLOBALS`，编译期抛 `NativeNotSupported`（砖块 10 实现后已移出） |
| 处理器栈泄漏（try 循环崩溃） | `native.py` `_emit_builtin_guard` / `raise_rt` | 弹出处理器记录时误把 `hstack_ptr` 设为 `record+40`（等于当前值），指针每次调用只增不减 → 约 1638 次调用后溢出 64KB `hstack` → `0xC0000005` | 改为 `hstack_ptr = record`（`mov rdx,rcx`），栈顶真正回退，LIFO 平衡 |

### 3.2 语法解析与字节码编译

- 修复函数体内 `let f(带参类型标注) = ...` 被误归为 FuncDef 的问题
- 修复 `let` 体边界：`_parse_let` 解析完绑定值后把 `_in_let_value` 无条件置 `False`，
  嵌套 let 会清掉外层「in 是边界」标记，导致外层 `in` 被当作成员运算符
  （生成 `BINOP 'in'` 并把后续调用错误编进 lambda 内部）。
  同构问题另修 `func`/`and` 顶层 lambda 体漏设 `_in_let_value`
- 修复顶层同级多个 `let rec` 越界：`_emit_let` 的 rec 分支无条件申请局部槽并发射
  `MAKE_BOX`/`STORE_BOX`，但 main 帧无槽数组 → `IndexError`。
  补 `scope.is_main` 分支，main 下退化为 `STORE_GLOBAL`
- 修复 `in` 运算符在受限语境被误判为 let 边界：
  `_parse_if` / `_parse_if_expr_impl` 解析条件时、`_parse_paren_dispatch` 的
  分组与元组试探解析元素时，均暂置 `_in_let_value = False`（条件与括号内的
  `in` 必为成员运算符），使 `if x in [1, 2] then …`、
  `let b = (1 in [1]) in 输出(b)` 等正确解析。注意不可整体包裹
  `_parse_paren_dispatch`，否则与既有试探-回退叠加成指数级回溯
  （`test_let_in_and_mutual_rec.py` 会挂起）

### 3.3 VM 引擎修复引发的解释器回退（启动性能 + 后端能力差异）

VM 侧补齐能力时，`src/__init__.py` 被改写成 1182 行的 eager-import hub（导出
339 个名字），同时一批新内建只加进了 VM 而没同步解释器。两者叠加，使解释器在
**启动速度**和**可用能力**上都明显退化。

#### 3.3.1 启动性能：包初始化拖入 MCP SDK

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| `import src.interp` | 9.84s | 1.83s（**5.4×**，且优于 HEAD 基线 2.14s） |
| `import src` | 9.71s | 0.17s |

- **根因**：`src/__init__.py:110` 在包初始化时 eager `import src.mcp_server`，
  连带拖入 MCP SDK（`mcp_types`/pydantic/uvicorn/asyncio/ssl），`-X importtime`
  显示该子树累计约 **5.74s**（占启动 ~59%）。而包初始化是任何 `import src.*`
  的必经之路，于是解释器、编译器、原生后端与全部测试被一起拖慢。
- **修复**：改为惰性导出——`_LAZY` 映射表（name → module/attr/模式），
  首次访问才 `importlib.import_module` 并写入 `globals()` 缓存。
  - 用**模块类覆写 `__getattribute__`**（`_LazyExportModule`）而非 PEP 562 的
    `__getattr__`：`__getattr__` 只在正常查找失败时触发，而 `importlib` 导入
    子模块时会自动把 `src.matha_main` 这类**子模块**写进父包 `__dict__`，
    从而盖住同名导出（`src.matha_main` 应为 `main` 函数）。惰性解析必须主动覆写，
    这正是原先 eager `from ... import main as matha_main` 提供的效果。
  - 忠实保留原语义：try/except ImportError 的 `soft` 模式（模块缺失时该名字为
    `None`）；历史上列在 `__all__` 却从未绑定的 53 个名字继续抛 `AttributeError`
    （`from src import *` 仍因此报错，与改动前一致）。
  - **等价性验证**：对 `__all__` 全部 327 个名字快照 `getattr` 结果的
    `模块:限定名`，改动前后**零差异**。

#### 3.3.2 `interpret` 被意外遮蔽

`src/__init__.py` 先 `from src.interp import ... interpret ...`，后又
`from src.virtual_code import ... interpret ...` 覆盖了它，
`from src import interpret` 拿到的是 virtual_code 的实现而非解释器的。
它在导出表中与 `Interpreter`/`MathaRuntimeError` 同组，主入口 `matha_main`
也确实使用 `src.interp.interpret`，故改为绑定解释器；virtual_code 的版本仍可经
`src.virtual_code.interpret` 访问。

#### 3.3.3 解释器未同步 VM 新增能力

对拍（`tests/test_interp_parity.py`，34 项值级用例）逐项对齐解释器与 VM：

| 能力 | 解释器修复前 | 修复后 |
|------|-------------|--------|
| 前缀 `^` 开方 | 解析器记为 `UnaryOp(op='sqrt')`，解释器只认 `'^'` → 「未知一元运算符 'sqrt'」 | 同时接受 `'sqrt'`/`'^'`，并对齐完全平方回退整数（`^9` → `3` 而非 `3.0`） |
| 集合字面量 `{}` / `{1,2,2}` | 返回 Python `set`（无序），`len()`/索引/`去重()` 全部失效 | 去重保序的 `list`，与 VM `list_dedup` 一致 |
| `输出(v)` / `print(v)` | 未定义函数（只有 `Output` 语句） | 绑定实例输出流，记录并返回原值（可链式），对齐 VM `_make_output` |
| `安全索引(c)(k)` / `安全取属性(o)(n)` | 未定义函数 | 按 VM 语义：容器/对象为 `None` 或键缺失返回 `None`，不抛错 |
| `构造集合(form)(vars)(els)` | 未定义函数 | 去重保序 `list`（form/variables 为编译器降级路径保留） |
| `_empty_dict` | 未定义变量 | 提供空字典常量（`{}` 在语法中是空集合） |
| `typeof` / `n` 关键字 | 返回 Python 类型名（`'int'`/`'NoneType'`） | 统一到中文类型名表，与 VM `_builtin_typeof`、原生 `_TYPEOF_ZH` 一致 |
| `len()` | 只收 str/list/tuple，`len(_empty_dict)` 报错 | 追加 dict/set（VM 直接用 Python `len`） |

- 反向补齐：VM 缺 `去重` 内建（解释器有），新增 `_builtin_dedup`，
  并让 `_builtin_make_set` 复用它。
- 对拍结论：修复前 **13/21**（行为级）/ **25/34**（值级）一致，
  修复后 **34/34** 全部一致。
- 注：`输出`/`print`/`安全索引`/`安全取属性`/`_empty_dict` 在 HEAD 的解释器中
  也未发现，故属 VM 补齐后解释器未跟上的**能力差异**，而非被删除的功能。

---

### 3.4 砖块 19：文本语义三后端统一（转义 / repr / len / 索引 / 列表化 / 列表 `+`）

三后端 = 宿主 VM+原生 AOT（`src/mbc/*`）、解释器（`src/interp.py`）、
自举 Matha 实现（`matha/*.matha`）。本轮把字符串相关的CPython 语义补齐并加对拍。

| Bug | 位置 | 现象 | 修复 |
|-----|------|------|------|
| 转义集不完整且静默吞反斜杠 | `src/lexer.py` `_string` / `_ESCAPE_MAP` | 只认 `\n\t\"\\`；`"a\rb"` → `"arb"`；`"a\qb"` → `"aqb"`（无声改写源码字面量） | 新增 `_decode_escape`：补 `\r\b\f\v\a\'`、八进制 `\0~\777`、`\xNN`/`\uNNNN`/`\UNNNNNNNN`（含代理区与 >0x10FFFF 校验）；未知转义**保留反斜杠** |
| 指数浮点解析失败 | `src/parser.py` 数字字面量 | `1e20`/`1e-7`/`2E5` 退化为整数或报错 | 补指数部分（小数点后无数字也合法） |
| 原生 repr 未冲刷前置 run | `src/mbc/native.py` `str_repr_body` | `"ab\x01" > "ab"` 前缀丢字 | 遇转义/高位字节先 flush 已有 run |
| `movzx ecx,[r15+1]` SIB 用错索引 | 同上 | SIB `0x07` 以 RAX 为索引，读到垃圾字节，`\xNN` 完全错乱 | → `0x27`（无索引，基址 r15） |
| C1 控制码未按 CPython 转义 | 同上 | U+0080–U+009F 原样输出，且含 NBSP 的字符串比对失败 | 区间判定 `cmp cl,0x80` / `cmp cl,0xA1`，即转义 U+0080–U+00A0；U+00A1 起可打印透传 |
| 原生 `len()` 按字节计数 | `_emit_builtin_len` | `len("你好")` = 6 | 按 UTF-8 非续位字节统计码点 |
| 原生索引切出半个字符 | `_emit_getitem` / `_emit_utf8_width` | `s[1]` 返回半个 UTF-8 字符 | 按码点定位，返回整字符 |
| 解释器 `list(文本)` 按字节拆分 | `src/interp.py` `builtin_list` | `list("你好")` → 字节碎片 | 按码点拆分 |
| 原生列表 `+` 吐对象字节 | `_emit_in_rt` BINOP `+` | 只判「左值是否落堆区间」，`[1]+[2]` 走字符串拼接，把两个列表对象粘成假字符串 | 按两侧类型标签分派（str/list/int），新增 `list_concat`；不支持的组合返回 `null_obj`（与本后端 `str()`/`not` 既有约定一致） |
| 自举 lexer 转义与宿主不同构 | `matha/lexer.matha` `转义字符` | 只认 `\n\t`、其余 `\X` 丢弃反斜杠 → 自举编译器把 `" \t\n\r"` 编译成 `" \t\nr"`，**自举定点 stage2 ≡ stage3 失败** | 重写为 `解转义`（多返回 `(String, Int)`）+ `扫描十六进制转义续`/`扫描八进制转义续`，与宿主 `_decode_escape` 逐条同构 |
| 浮点分派只判右操作数 | `src/mbc/native.py` `is_float2` | 判右值容器时 `mov rax,r9` 后未改回 `r8` 就 `call is_float` → 「左浮右整」被判非浮点，`1.5 + 2` 走整数路径把堆指针当整数相加（输出 `None` 或指针样大数） | 补 `mov rax,r8`；左/右两侧各自先排容器再判浮点 |

- 新增 `tests/test_brick19_text.py`（41 项：三后端转义/ repr / len / 索引 / 列表化 / 列表 `+` 对拍）、
  `tests/test_native_encoding.py` 追加 3 项字节级编码断言（SIB `0x27`、`cmp cl`、`cmp al`）。
- `tests/test_mbc_bootstrap.py` 的 `test_m7_compiled_lexer_matches_host` 与
  `test_m7_double_bootstrap_lexer_chain` 各追加 15 条转义字面量，锁死宿主/自举同构。
- `tests/test_native.py` 新增 `float_left_operand` parity 用例（11 条浮点二元运算）。
- 对拍结论：repr 对 CPython **29/29**（AOT/VM/解释器三方一致）；
  全量回归 **1910 项通过**（此前 1865 项基线 + 本轮新增）。

---

### 3.5 AOT 算术语义与内存安全修复（除法 / 下标 / 幂 / 序列重复）

本轮针对 `src/mbc/native.py` 做 VM↔AOT 对拍定位的 5 类缺陷。全部经 Capstone
反汇编核对机器码，回归测试落在 `tests/test_native.py`。

### 3.5.1 整数除零崩溃 + 整除语义错误

| 现象 | 位置 | 修复 |
|------|------|------|
| `1 // 0` 直接 `0xC0000094`（#DE 整数除零） | BINOP `//` 直接发 `idiv` | 新增 `int_floordiv`：先查除数 0 → `raise_rt`（`err_divzero = "division by zero"`）；`rcx == -1` 短路返回 `-rax`，避开 `INT64_MIN / -1` 溢出 |
| `-7 // 2` 得 `-3`（x86 `idiv` 向零截断，Python 向下取整应为 `-4`） | 同上 | 整除后按符号修正（`rem != 0 && sign(r) != sign(divisor)` 则 `-1`） |
| `7 % -2` 得 `1`（`idiv` 余数取**被除数**符号，Python `%` 取**除数**符号） | BINOP `%` 直接用 `idiv` 余数 | 新增 `int_mod`：`r = a - floor(a/b)*b`，符号随除数 |

### 3.5.2 浮点 `//` / `%` 除零静默产出 `inf` / `nan`

`divsd` 除零不触发异常，原生侧会静默输出 `inf`、`nan`（浮点 `-7.5 % 2.0` 更得到 `-0.5`）。

- 新增 `f_floordiv` / `f_mod`：`crt_floor` + `a - floor(a/b)*b`。
- **除零判定必须与全零寄存器比较**：`ucomisd xmm1,xmm1` 只反映自相等，所有正常
  非 NaN 值都置 ZF=1（曾导致 `7.0 // 2.0` 一律抛 division by zero）。正确写法是
  先 `xorpd xmm2,xmm2` 再 `ucomisd xmm1,xmm2`，并以 `JP`（近端 `0x0F 0x8A`）
  排除 NaN、`JZ` 判零。条件码须落在**近端**表：`0x7A` 是短端 `jnp`，`0x0F 0xBA`
  则是 `btc`——两者都会错位指令流。
- 除零路径与整除共用 `fdivz` 抛出点。

### 3.5.3 列表下标越界读相邻堆字节

`_emit_getitem` 的列表分支直接 `mov rax,[rax+rcx*8+16]`，**不查界**：
`[1,2][9]` 静默返回 `0`（读到对象头之后的相邻堆字节），既与文本/字典路径
「越界返回 `null_obj`」的既有约定不一致，也是一处内存安全越界读。同时原生端
**完全不支持负下标**（`[1,2,3][-1]` 同样越界）。

- 补 `mov r8,[rax+8]` 取长度 + 符号分派：`rcx >= 0` 走 `cmp rcx,r8` / `jae`；
  `rcx < 0` 先 `neg rcx`，再 `cmp rcx,r8` / `jbe`（**含端点**：`-n` 合法且等于
  `a[0]`），随后 `base + (n-idx)*8` 取值。
- 越界（含 `-n-1`、空列表、`None` 容器）统一返回 `None`。

### 3.5.4 整数幂负指数静默返回 0

`2 ** -1` 在原生端得 `0`（整数幂连乘循环遇负指数只能给 0），Python 为 `0.5`。

- 负指数改走浮点幂 `f_pow`（`crt_pow`，与 VM 的 `float.__pow__` 逐位一致），
  `2 ** -100` 亦得逐位相同的 `7.888609052210118e-31`。
- `0 ** -1`：VM 抛 `ZeroDivisionError: zero to a negative power`，原生新增
  `err_powzero` 静态串走异常运行时（`pow(0.0,-1.0)` 只会给 `inf`）。

### 3.5.5 序列重复的两处编码缺陷

- `seq_repeat` 里两处奇偶测试发出 `49 F7 C4`（`test r12,1`），应为
  `49 F7 C6`（`test r14,1`）。奇偶判断错位导致 `seq * 1`、`1 * seq` 走倍增
  分支后返回垃圾。
- 交换操作数路径把整数当堆指针解引用：`3 * "xy"` 读 `[rcx+16]` 取类型标签，
  而此时该字段是整数 `3` 本身。应取右操作数 `r9`。

---

## 四、测试覆盖

| 测试文件 | 测试数 | 内容 |
|----------|--------|------|
| `test_native.py` | 371 | 端到端：编译 exe → 运行 → 校验 stdout/rc；含 VM/AOT parity 用例（含 `float_left_operand`、整除/取模 floor 语义、除零异常、列表负下标与越界、幂负指数） |
| `test_native_heap.py` | 132 | 字符串/列表/字典/与 VM 奇偶（含序列重复、交换操作数、不支持组合返回 `None`） |
| `test_native_encoding.py` | 23 | 字节级编码断言 + PE 节区布局（含 SIB/`cmp cl`/`cmp al` 回归、零填充尾段不得占文件体积） |
| `test_native_frontends.py` | 64 | 多前端一致性 |
| `test_brick19_text.py` | 41 | 砖块 19 三后端文本语义（转义/repr/len/索引/列表化/列表 `+`） |
| `test_let_in_and_mutual_rec.py` | 17 | `let … in` 体边界 + 同级/互递归 `let rec` 回归 |
| `test_mbc_bootstrap.py` | 236 | M3V 自举闭环测试（含自举/宿主 lexer 转义同构） |
| `test_mbc_bytecode.py` | 27 | M3V 字节码执行（递归/数论/字符串） |
| `test_new_features.py` | 24 | 新功能测试 |
| `test_nl_pipeline.py` | 39 | 自然语言管线测试 |
| `test_interp_parity.py` | 48 | 解释器/VM 值级对拍（34）+ 惰性导出契约（8）+ 导入性能守卫（2） |

**全量回归**：
- 砖块 19 轮次：1910 项通过（1817 基线 + 本轮砖块 19 新增回归；
  含自举定点 `matha/stdlib.matha` 恢复 stage2 ≡ stage3）
- 3.5 轮次：**2007 项通过**（1910 基线 + 97 项新增回归）。
  其中原生四套件 `test_native.py` / `test_native_heap.py` /
  `test_native_encoding.py` / `test_native_frontends.py` 共 **594 项通过**，
  用时 1557s。
- 性能基线未回退：VM 200,000 次循环约 5.9s，原生约 30–50ms。

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
