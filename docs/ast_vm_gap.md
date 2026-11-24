# AST × VM 覆盖矩阵

> 本文件由 `python scripts/ast_vm_matrix.py --write` 生成，请勿手改。
> 机器可读快照见 `docs/ast_vm_gap.json`，守门测试见 `tests/test_ast_vm_gap.py`。

## 一、为什么需要它

主执行链归一到 mbc（删掉 `convert(...)+exec()` 转译路径）之前，必须先证明
VM 覆盖旧程序真实用到的全部 AST 构造。这张表就是那份证据：

- **节点宇宙**：`src/ast_nodes.py` 的全部 `@dataclass` 节点。
- **语料**：`matha/**/*.matha`、`examples/**/*.matha`、`golden_tests/**/*.matha`、`tests/**/*.matha`、`stdlib/**/*.matha`。
- **vm 列**：`src/mbc/compiler.py` 的静态分派判定（`emits` 发射字节码 / `noop` 有意不产码 / `missing` 不认识）。
- **interp 列**：遗留诊断后端是否处理该节点（用于判断补齐前的回退能力）。

VM↔native 的平价面不是 AST 而是**指令码**：`native.py` 从已编译的 mbc 模块
发射机器码，因此另有一张指令码表（见第五节）。

## 二、统计

| 指标 | 数值 |
|---|---|
| AST 节点总数 | 78 |
| VM 发射字节码 | 59 |
| VM 有意无码 | 19 |
| VM 不认识 | 0 |
| **阻塞缺口（不认识 ∧ 语料用到）** | **0** |
| 指令码总数 / VM 已分派 / native 已发射 | 36 / 36 / 36 |
| **native 对拍风隙（VM 有、native 无）** | **0** |
| 语料文件（解析成功） | 231 |
| 无法解析的语料文件 | 0 |

## 三、阻塞缺口（必须先补）

无。VM 覆盖了语料用到的全部 AST 构造，可以移除转译执行路径。

## 四、未被语料使用的缺口（低优先）

无。

## 五、全表

| 节点 | VM | interp | 语料文件数 |
|---|---|---|---|
| `AliasDef` | noop | no | 0 |
| `AngleExpr` | emits | no | 0 |
| `AnnotatedType` | noop | no | 0 |
| `Annotation` | noop | no | 0 |
| `BasicType` | noop | no | 172 |
| `Belongs` | emits | yes | 1 |
| `BinaryOp` | emits | yes | 183 |
| `Binding` | emits | yes | 50 |
| `BoolLit` | emits | yes | 50 |
| `BreakStmt` | emits | yes | 1 |
| `ChainStmt` | emits | yes | 16 |
| `ChanExpr` | emits | yes | 0 |
| `CodeBlock` | emits | yes | 110 |
| `CommandLiteral` | noop | yes | 28 |
| `ConstructorPat` | emits | yes | 0 |
| `ContinueStmt` | emits | yes | 1 |
| `DefineOp` | noop | no | 0 |
| `DictLiteral` | emits | yes | 23 |
| `EnumDef` | emits | yes | 2 |
| `FileMarker` | noop | yes | 0 |
| `FloatLit` | emits | yes | 90 |
| `ForStmt` | emits | yes | 2 |
| `ForeignDecl` | noop | yes | 12 |
| `FuncApp` | emits | yes | 182 |
| `FuncDef` | emits | yes | 172 |
| `FuncType` | noop | no | 172 |
| `GenStmt` | emits | yes | 35 |
| `Generate` | noop | no | 56 |
| `GlobalIdStmt` | noop | yes | 16 |
| `GlobalLoopSuffix` | noop | no | 1 |
| `GoStmt` | emits | yes | 0 |
| `IfElseStmt` | emits | yes | 0 |
| `IfExpr` | emits | yes | 102 |
| `IfStmt` | emits | yes | 10 |
| `ImportDecl` | emits | yes | 29 |
| `IndexExpr` | emits | yes | 86 |
| `IntegerLit` | emits | yes | 206 |
| `IsExpr` | emits | yes | 1 |
| `Iteration` | emits | no | 0 |
| `Lambda` | emits | yes | 175 |
| `LetBinding` | emits | yes | 106 |
| `LetTupleBinding` | emits | yes | 13 |
| `ListComp` | emits | yes | 1 |
| `ListLiteral` | emits | yes | 93 |
| `LoopFraction` | noop | no | 10 |
| `LoopStep` | emits | no | 0 |
| `LoopWhile` | emits | no | 0 |
| `MatchStmt` | emits | yes | 13 |
| `MechUnit` | emits | yes | 56 |
| `ModuleDecl` | emits | yes | 148 |
| `NLBlock` | noop | no | 0 |
| `Output` | emits | yes | 63 |
| `OutputTrail` | emits | yes | 45 |
| `PathExpr` | emits | yes | 14 |
| `Program` | emits | no | 231 |
| `RaiseExpr` | emits | yes | 7 |
| `ReadBlock` | noop | yes | 23 |
| `ReturnStmt` | emits | yes | 8 |
| `SafePathExpr` | emits | yes | 0 |
| `SegLoopSuffix` | noop | no | 10 |
| `SelectStmt` | emits | no | 0 |
| `SendExpr` | emits | yes | 0 |
| `SetConstruct` | emits | yes | 2 |
| `SetType` | noop | no | 0 |
| `SetUp` | emits | yes | 29 |
| `SetUpItem` | noop | no | 29 |
| `SliceExpr` | emits | yes | 32 |
| `StringLit` | emits | yes | 130 |
| `StructDef` | emits | yes | 3 |
| `SwitchStmt` | emits | yes | 0 |
| `ThrowStmt` | emits | yes | 0 |
| `TryStmt` | emits | yes | 6 |
| `TupleExpr` | emits | yes | 26 |
| `TupleType` | noop | no | 141 |
| `TypeOfExpr` | emits | yes | 3 |
| `UnaryOp` | emits | yes | 64 |
| `Variable` | emits | yes | 223 |
| `WhileStmt` | emits | yes | 9 |

## 六、指令码 × VM / native

指令码共 36 条：VM 已分派 36，native 已发射 36，**VM 有而 native 无 = 0 条**（对拍风隙）。

无：两端指令码表面一致。

## 七、全量指令码表

| 指令码 | VM | native |
|---|---|---|
| `BINOP` | yes | yes |
| `BUILD_DICT` | yes | yes |
| `BUILD_LIST` | yes | yes |
| `BUILD_SLICE` | yes | yes |
| `BUILD_TUPLE` | yes | yes |
| `CALL` | yes | yes |
| `DUP` | yes | yes |
| `FORMULA_SCHEMA` | yes | yes |
| `GET_ATTR` | yes | yes |
| `HALT` | yes | yes |
| `INDEX_GET` | yes | yes |
| `JMP` | yes | yes |
| `JNZ` | yes | yes |
| `JZ` | yes | yes |
| `LOAD_BOX` | yes | yes |
| `LOAD_GLOBAL` | yes | yes |
| `LOAD_LOCAL` | yes | yes |
| `LOAD_OUTER` | yes | yes |
| `LOAD_OUTER_BOX` | yes | yes |
| `MAKE_BOX` | yes | yes |
| `MAKE_CLOSURE` | yes | yes |
| `OUTPUT` | yes | yes |
| `POP` | yes | yes |
| `PUSH_CONST` | yes | yes |
| `PUSH_FALSE` | yes | yes |
| `PUSH_NULL` | yes | yes |
| `PUSH_TRUE` | yes | yes |
| `RAISE` | yes | yes |
| `RAISE_MATCH` | yes | yes |
| `RET` | yes | yes |
| `STORE_BOX` | yes | yes |
| `STORE_GLOBAL` | yes | yes |
| `STORE_LOCAL` | yes | yes |
| `STORE_SUBSCRIPT` | yes | yes |
| `UNARYOP` | yes | yes |
| `UNPACK_SEQ` | yes | yes |

## 九、写 `.matha` 标准库时踩到的语言口径

本节是「VM 能发射」与「人能写对」之间的缝：阶段 4 把符号微积分
重写成 `matha/library/*.matha` 时实测得到的词法/语法口径。它们不是
缺陷（都有对应回归用例），但写库时违反就会拿到错的输出：

| 口径 | 实例 | 库内做法 |
|---|---|---|
| **裸 `[x]` 出现在语句位仍当作「打印括号」**（输出单元）；但 `return` 紧邻操作数位的 `[x]` 已归一为**列表字面量**（不再既打印又返裸值）| `func 包(x) -> List = (x) => { return [x] }` | `return [x]`→`[x]`、`return []`→`[]`、`return [a, b]` 均为正常列表（黄金用例 `34_return_list_literal` 三端锁定）；裸块尾 `[x]` 仍单次输出 |
| `func` 缺 `-> 类型` 直接 ParseError | `func f(x) = …` | 一律写 `func f(x) -> Any = …` |
| `if` 不能当表达式用 | `let y = if c {1} else {2}` | 先算再绑定 |
| **列表推导 `[expr for x in iter if c ...]` VM 已编译**（旧版曾静默编译成空列表 `[]`）| `[x * x for x in nums]` | 下沉为与 `for` 同构的下标循环 + `append` 累加（零新 opcode/新内建）；多 `if` 取 AND；**仅单个 `for` 生成子句**（parser 语法即如此，非 Python 多 for 嵌套）；三端逐字节对齐 interp（`tests/test_listcomp_vm.py` + 黄金用例 `35_list_comp` 锁定） |
| `#：{…}` 记录面 mbc 不发射 | — | 标准库不用该语法 |
| ~~无 `sorted/map/filter/join/gcd/split` 等内建~~ **已由纯 Matha 标准库提供** | `matha/library/collections_core.matha` | `map/filter/reduce/sorted(稳定插入排序)/join/split/gcd` 七函数零新 opcode/零新宿主内建实现（先例同 `35_list_comp`）；黄金用例 `36-39` 三端逐字节锁，行为另由 `tests/test_matha_library_basics.py` 对拍 Python 真相。注意：同名不同 arity 重载会被后定义覆盖，故 `sorted` 只有 `sorted(xs, lt)` 双参形式 |

（历史上本表还列有「三元/or 里 `==` 误析」与「无科学计数法字面量」两条：前者已于语句位归一为 `(a==b)?x:y`（黄金用例 `32_ternary_eq_precedence` 三端锁定），后者 `1e-15` 早已被 lexer/parser 支持（黄金用例 `33_sci_notation` 三端锁定），均已删除不复发。）

前两条属语法层语义易错点，已在 `tests/test_matha_stdlib_symbolic.py` 与 `matha/library/` 的实际使用中验证；本表随 `--write` 重生。

