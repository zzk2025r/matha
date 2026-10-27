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
| 指令码总数 / VM 已分派 / native 已发射 | 33 / 33 / 33 |
| **native 对拍风隙（VM 有、native 无）** | **0** |
| 语料文件（解析成功） | 159 |
| 无法解析的语料文件 | 19 |

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
| `BasicType` | noop | no | 119 |
| `Belongs` | emits | yes | 1 |
| `BinaryOp` | emits | yes | 128 |
| `Binding` | emits | yes | 39 |
| `BoolLit` | emits | yes | 25 |
| `BreakStmt` | emits | yes | 1 |
| `ChainStmt` | emits | yes | 16 |
| `ChanExpr` | emits | no | 0 |
| `CodeBlock` | emits | yes | 49 |
| `CommandLiteral` | noop | yes | 28 |
| `ConstructorPat` | emits | yes | 0 |
| `ContinueStmt` | emits | yes | 1 |
| `DefineOp` | noop | no | 0 |
| `DictLiteral` | emits | yes | 10 |
| `EnumDef` | emits | yes | 1 |
| `FileMarker` | noop | yes | 0 |
| `FloatLit` | emits | yes | 75 |
| `ForStmt` | emits | yes | 2 |
| `ForeignDecl` | noop | yes | 4 |
| `FuncApp` | emits | yes | 113 |
| `FuncDef` | emits | yes | 119 |
| `FuncType` | noop | no | 119 |
| `GenStmt` | emits | yes | 31 |
| `Generate` | noop | no | 43 |
| `GlobalIdStmt` | noop | yes | 15 |
| `GlobalLoopSuffix` | noop | no | 1 |
| `GoStmt` | emits | yes | 0 |
| `IfElseStmt` | emits | yes | 0 |
| `IfExpr` | emits | yes | 56 |
| `IfStmt` | emits | yes | 6 |
| `ImportDecl` | emits | yes | 10 |
| `IndexExpr` | emits | yes | 37 |
| `IntegerLit` | emits | yes | 135 |
| `IsExpr` | emits | yes | 1 |
| `Iteration` | emits | no | 0 |
| `Lambda` | emits | yes | 120 |
| `LetBinding` | emits | yes | 58 |
| `LetTupleBinding` | emits | yes | 9 |
| `ListComp` | emits | yes | 0 |
| `ListLiteral` | emits | yes | 39 |
| `LoopFraction` | noop | no | 10 |
| `LoopStep` | emits | no | 0 |
| `LoopWhile` | emits | no | 0 |
| `MatchStmt` | emits | yes | 6 |
| `MechUnit` | emits | yes | 43 |
| `ModuleDecl` | emits | yes | 88 |
| `NLBlock` | noop | no | 0 |
| `Output` | emits | yes | 45 |
| `OutputTrail` | emits | yes | 41 |
| `PathExpr` | emits | yes | 12 |
| `Program` | emits | no | 159 |
| `RaiseExpr` | emits | yes | 5 |
| `ReadBlock` | noop | yes | 23 |
| `ReturnStmt` | emits | yes | 6 |
| `SafePathExpr` | emits | yes | 0 |
| `SegLoopSuffix` | noop | no | 10 |
| `SelectStmt` | emits | no | 0 |
| `SendExpr` | emits | no | 0 |
| `SetConstruct` | emits | yes | 1 |
| `SetType` | noop | no | 0 |
| `SetUp` | emits | yes | 25 |
| `SetUpItem` | noop | no | 25 |
| `SliceExpr` | emits | yes | 16 |
| `StringLit` | emits | yes | 78 |
| `StructDef` | emits | yes | 2 |
| `SwitchStmt` | emits | yes | 0 |
| `ThrowStmt` | emits | yes | 0 |
| `TryStmt` | emits | yes | 4 |
| `TupleExpr` | emits | yes | 15 |
| `TupleType` | noop | no | 97 |
| `TypeOfExpr` | emits | yes | 2 |
| `UnaryOp` | emits | yes | 39 |
| `Variable` | emits | yes | 156 |
| `WhileStmt` | emits | yes | 3 |

## 六、指令码 × VM / native

指令码共 33 条：VM 已分派 33，native 已发射 33，**VM 有而 native 无 = 0 条**（对拍风隙）。

无：两端指令码表面一致。

## 七、全量指令码表

| 指令码 | VM | native |
|---|---|---|
| `BINOP` | yes | yes |
| `BUILD_DICT` | yes | yes |
| `BUILD_LIST` | yes | yes |
| `BUILD_SLICE` | yes | yes |
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
| `RET` | yes | yes |
| `STORE_BOX` | yes | yes |
| `STORE_GLOBAL` | yes | yes |
| `STORE_LOCAL` | yes | yes |
| `UNARYOP` | yes | yes |
| `UNPACK_SEQ` | yes | yes |

## 八、无法解析的语料

这些 `.matha` 连 parser 都过不了，属语法层缺口（与 VM 无关）：

| 文件 | 错误 |
|---|---|
| `matha/knowledge/cs/algorithms.matha` | ParseError: ParseError at L11:20: 期望表达式 (got OP_COLON ':') |
| `matha/knowledge/cs/data_structures.matha` | ParseError: ParseError at L10:5: 期望类型表达式 (got NEWLINE '\\n') |
| `matha/resource/cs/algorithms.matha` | ParseError: ParseError at L11:20: 期望表达式 (got OP_COLON ':') |
| `matha/resource/cs/game_algorithms.matha` | ParseError: ParseError at L43:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(') |
| `matha/resource/cs/game_apps_math.matha` | ParseError: ParseError at L68:11: 期望 ( (got IDENTIFIER 'best_first') |
| `matha/resource/cs/os_concepts.matha` | ParseError: ParseError at L11:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(') |
| `matha/resource/hardware/embedded_math.matha` | ParseError: ParseError at L13:21: 期望 ) (got OP_COLON ':') |
| `matha/resource/hardware/system_math.matha` | ParseError: ParseError at L13:17: 期望表达式 (got OP_ARROW '->') |
| `matha/resource/logic/advanced_math.matha` | ParseError: ParseError at L65:8: 期望 函数名 (got LIT_INTEGER '01背包') |
| `matha/resource/math/3d_transform.matha` | ParseError: ParseError at L73:43: 期望 属性名 (got LIT_INTEGER '1') |
| `matha/resource/os/kernel_memory.matha` | ParseError: ParseError at L64:52: 期望 ) (got OP_PLUS '+') |
| `matha/resource/os/kernel_syscall.matha` | ParseError: ParseError at L120:1: 期望 } (got EOF '') |
| `matha/resource/os/os_concepts_math.matha` | ParseError: ParseError at L11:10: 期望 ) (got KW_IN 'in') |
| `matha/resource/os/process_math.matha` | ParseError: ParseError at L52:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(') |
| `matha/resource/security/crypto_math.matha` | ParseError: ParseError at L97:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(') |
| `matha/resource/statistics/analysis.matha` | ParseError: ParseError at L47:20: 期望表达式 (got OP_COLON ':') |
| `matha/resource/tools/utility_math.matha` | ParseError: ParseError at L15:10: 期望 => (got PUNCT_COMMA ',') |
| `matha/resource/web/network_math.matha` | ParseError: ParseError at L76:13: 期望 ( (got IDENTIFIER 'Token长度') |
| `matha/vm/matha_vm.matha` | ParseError: ParseError at L88:11: 期望 ( (got IDENTIFIER 'Peek') |

## 九、写 `.matha` 标准库时踩到的语言口径

本节是「VM 能发射」与「人能写对」之间的缝：阶段 4 把符号微积分
重写成 `matha/library/*.matha` 时实测得到的词法/语法口径。它们不是
缺陷（除第二条外都有对应回归用例），但写库时违反就会拿到错的输出：

| 口径 | 实例 | 库内做法 |
|---|---|---|
| **单元素列表 `[x]` 出现在语句位会被当作「打印括号」**：`return [x]` 编译成 `ReturnStmt(Output(x))`，既打印又返回裸值 | `func 包(x) -> List = [x]` | 库内统一用 `包(...)` 造单元素列表；两元素及以上 `return [a, b]` 是正常字面量 |
| `return []` 同样不安 | `func 空表() -> List = []` | 用 `包(0)[1:]` 切出空表 |
| 三元条件 / `or` 里的 `==` 误析 | `if a == b ? … : …` | 走返回 Bool 的辅助函数 `等/零值/双零/或值` |
| `func` 缺 `-> 类型` 直接 ParseError | `func f(x) = …` | 一律写 `func f(x) -> Any = …` |
| `if` 不能当表达式用 | `let y = if c {1} else {2}` | 先算再绑定 |
| `#：{…}` 记录面 mbc 不发射 | — | 标准库不用该语法 |
| 无 `sorted/map/filter/join/gcd/split` 等内建 | — | 手写升序插入排序 + 欧几里得 `gcd` |
| 无科学计数法字面量 | `1e-15` 不可写 | `微小() = 1 / 1000000000000000`（与双精度 1e-15 同值） |

前三条属语法层语义易错点，已在 `tests/test_matha_stdlib_symbolic.py` 与 `matha/library/` 的实际使用中验证；本表随 `--write` 重生。

