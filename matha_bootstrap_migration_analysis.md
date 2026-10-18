# Matha 自举迁移分析

## 当前状态（2026-09-07）

### 已自举 ✅
- **lexer.matha** — 词法器，返回正确 token 列表
- **parser.matha** — 语法器，支持函数定义、lambda、三元、算术、if-then-else、not 前缀运算符
- **parser 扩展** ✅ — `let ... in` 表达式、元组解构 `let (a, b) = expr` 已支持（interp.matha 可解析）

### 已验证通过 ✅
- `bootstrap_test_v2.matha` — 8 个测试区块，33 个输出，全部通过
- `not` 前缀运算符 — 已修复并验证
- **interp.matha 解析通过** ✅（2026-09-07：ModuleDecl 解释器 + 自测 MechUnit 均可解析）

### 语言桥 / 无中生有（2026-09-07 新增）✅
- `src/matha/language_bridge.py` — 吞噬/转化/融合其它语言：
  - 支持 rust / go / js / c（统一函数发现 + 表达式直译器）/ python（ast 提取）
  - 直译：单表达式函数体 → Matha 表达式（算术/比较/三元/调用）
  - 无中生有：无法直译的函数生成带元数据的骨架，保 API 面完整
  - 融合：Matha parser 自验证 + 写入 `matha/generated/`
- 实测：algebra.py（12 骨架）、arithmetic.py（15 直译+14 骨架）、semantic.py（4 骨架）全部融合通过
- rust/js 直译全通过（含嵌套三元）；前端 `_parse_expr` 补齐单字符运算符 `* / + - < >`
- 接入：`FormulaGrowthEngine.devour/devour_file`、`UnifiedGrowth.devour/devour_file`

---

## 近期修复记录

| 文件 | 修复内容 |
|------|---------|
| `src/interp.py` | `builtin_len` 支持 tuple；`builtin_append` 兼容 tuple；`_call_lambda` extra args 智能丢弃；`not` 一元运算符支持；ModuleDecl 闭包创建与命名空间优先级 |
| `src/parser.py` | `_parse_postfix` 末尾处理 `真/假 :` 模式；`_parse_unary` 添加 `not` 前缀支持；`let ... in` 表达式；元组解构 |
| `src/multi_lang_frontend.py` | 五个前端 `_parse_expr` 运算符表补齐 `* / + - < >`（此前链式算术丢失运算符） |
| `src/matha/language_bridge.py` | 新增：语言桥（吞噬/转化/融合 + 统一表达式直译器 + 无中生有骨架） |
| `src/matha/growth.py` | FormulaGrowthEngine 新增能力 4：语言吞噬（devour/devour_file） |
| `src/unified_growth.py` | UnifiedGrowth 新增 devour/devour_file |
| `matha/lexer.matha` | `扫描标识符续` 增加第 8 参数 `忽略: Bool` |
| `matha/parser.matha` | `解析_lambda_params_rest` 参数拼接；`reverse_helper` 列表拼接；`解析_lambda_or_group` 非 lambda 括号误判 |
| `C:\Users\Admin\Matha\matha.cmd` / `.ps1` | 修复启动闪退：入口从目录改为 `src\matha_main.py` |

---

## 文件迁移状态

### ✅ 已迁移（Matha 版可解析/可运行）
- `matha/bootstrap_test_v2.matha` — 全部测试通过
- `matha/lexer.matha` / `matha/parser.matha` — 自举路径可用
- `matha/interp.matha` — 解析通过；Matha-to-Matha 自测执行中（Python 解释执行较慢）

### ✅ 无中生有生成的 Matha 模块（matha/generated/）
- `代数库.matha` / `算术库.matha` / `语义分析.matha` — 语言桥吞噬生成，parser 验证通过
- `rust_math.matha` / `js_lib.matha` / `beam_lib.matha` — 多语言吞噬验证样本

### ⏳ 待验证
- `matha/bootstrap_test.matha` — **已惯用式重写 + 无损解析** ✅（`var` 声明、单引号
  字符串、`_` 通配符、元组解构赋值 `(a, b) = e` 均已支持，四端一致）。重写要点：
  计数器改共享列表 `状态 = [通过数, 失败数]` 经 `标准库.原地设置` 原地更新；
  `断言` 分支改单一 `let … in …`（消除多语句分支被静默丢弃）；`词法器.扫描`
  更正为柯里化 `扫描(src)(pos)(line)(col)(toks)`；补 `use 标准库`。
  **运行仍受阻于环境**（非文件）：宿主自举环境未注册 VM/原生专属内建 `调用捕获`，
  且自举词法器在宿主解释器下对本文件抛 `RecursionError`；执行需另行构建 VM 自举运行器。
  回归守护：`tests/test_bootstrap_host.py::test_bootstrap_test_matha_parses_losslessly`。

---

## 下一步

1. ~~let-in / 元组解构 parser 扩展~~ ✅ 已完成
2. ~~interp.matha 自测 MechUnit 的 Matha-to-Matha 求值结果验证~~ ✅
   （`tests/test_mbc_bootstrap.py::test_interp_selftest_math_to_math`：合并编译
   lexer/stdlib/parser/interp 后运行 VM，interp.matha 顶层 `#：{ }` 自测段输出
   尾部为 [8, 14, 200, 10, 6]）
3. 吞噬骨架的逐步补全（控制流函数体翻译）——分阶段推进：
   - [Phase 1 ✅] `SCOPED_BLOCKS` 特性开关（默认关闭）：`{ }` 代码块作为语句上下文 +
     独立子作用域，使 Python 解释器原生支持多语句函数体与 for/while 循环累加。
     `src/features.py` + `parser._parse_code_block/_parse_block_body`（开关开启时
     `_in_lambda_body=False`）+ `interp` CodeBlock-as-expr 子作用域（浅拷贝）。
     验证：`tests/test_scoped_blocks.py`（10 项）；回归（默认关闭）2547+756=3303 passed。
   - [Phase 2 ✅] 语言桥语句块直译（`SCOPED_BLOCKS` 开启时）：Python 控制流体
     （`for`/`while`/`if` 语句 + 末尾 `return`）译为 Matha 代码块 `{ ... }`，
     循环体不再退化为无中生有骨架。`src/matha/language_bridge.py`
     （`_py_body_to_block`/`_py_stmt_lines`）；`tests/test_language_bridge.py` +7。
     限制：`raise`、方法调用仍为骨架；仅 Python 路径（外部语言路径待补）。
   - [Phase 3 ✅] `return`/`break`/`continue` 语句（语法器补全）：`ReturnStmt`/
     `BreakStmt`/`ContinueStmt` 此前已被解释器与 MBC 编译器支持，但语法器从未产出；
     补上后块体内可提前返回，语言桥循环内 `return` 不再骨架。
     `src/parser.py`（`_parse_mech_stmt` 分发 + `_parse_statement`/`_parse_decl` 产生式）；
     `tests/test_scoped_blocks.py` +4、`tests/test_language_bridge.py`。
     回归全量 **3314 passed**。
   - [Phase 4 ✅] CLI 特性开关 + 灰度推进：`matha --feature NAME[=on|off]`（可重复，
     进程内覆盖优先于环境变量）、`matha features` 子命令；三个相关测试文件的隔离夹具改为
     **测试期间移除外部环境变量**（保存/恢复），模块级 `py_record` 自行固定为默认关闭，
     使「默认关闭」断言在任意环境下确定可断言。
     实测：默认关闭 **3320 passed** / `MATHA_FEATURE_SCOPED_BLOCKS=1` 强制开启 **3320 passed**
     （**零差异**）。
   - 灰度路径：默认关 → 单模块先开（`--feature` 或环境变量）→ 全量开启回归（已实测通过）→
     评估默认翻转 / 扩大范围。
   - [Phase 5 ✅] Matha 核心自定义扩展接口（解释器/编译器）—— `src/ast_ext.py`
     扩展节点注册表：`define_node(name, fields)` 动态建 dataclass 节点并注入
     `src.ast_nodes`；四张规则表 `register_eval` / `register_exec`（解释器）、
     `register_compile_expr` / `register_compile_stmt`（MBC），按节点类分派。
     钩子是**兜底而非覆盖**（内置分派先命中，扩展只能新增节点）；
     插件节点在 MBC 端降级为核心字节码 → **原生后端无需感知插件即可执行**。
     公开入口 `Interpreter.eval_expr` / `Interpreter.exec_stmt`、`Compiler.emit_expr`。
     实测 `tests/test_ast_ext.py` 30 项（含 解释器 / VM / **原生 exe** 三方结果一致），全量 **3350 passed**。
   - [Phase 6 ✅] 插件节点的**解析期语法钩子**：`ast_ext.register_syntax(name, cls, fields)` →
     `src/parser.py::_parse_postfix` 收尾处 `rewrite_call` 把 `名(a, b)` 应用链改写为插件节点
     （柯里化多参一并改写；`SYNTAX` 为空时立即返回，既有解析零影响）。
     于是**源串**也三端可达（解释器 / VM / 原生 exe 结果一致），
     `tests/test_ast_ext.py` 增至 38 项，全量 **3358 passed**。
     已知限制：输出括号 `[ … ]` 语境会把解析失败回退为字符串（既有设计），
     插件参数个数错误落在该语境同样被回退；`fields` 未定义时须显式给出。
   - [待办] MBC/VM、原生后端、自举编译器支持 `SCOPED_BLOCKS` 语义（四端一致）；
     外部语言路径语句块直译。
4. ~~bootstrap_test.matha 解析支持 + 惯用式重写~~ ✅（单引号字符串 + `var`→`Binding` +
   `_` 通配 + 元组解构赋值；文件已整体解析通过、已惯用式重写并附无损解析回归守护）。
   剩余**执行**受阻于宿主环境（`调用捕获` 未注册 + 自举词法器 `RecursionError`），
   需另行构建 VM 自举运行器（低优先级，暂缓）
