# Matha 已知问题与未达成项（v4.6.0）

> 这份文件只列**当前可复现**的问题，每条都给出可执行判据。
> 旧版的清单已整份移入 [`history/KNOWN_ISSUES.md`](history/KNOWN_ISSUES.md)。
> 规矩：不允许写「已全部解决」；解决一条就删一条，删不掉就留在这里。

## 一、机器码后端（`src/mbc/native.py`）

> NI-001、NI-002 已修复：未定义变量与字符串/列表参与 `-` 均经 `raise_rt` 抛
> 可捕获异常，不再静默读成裸 0 / 拿对象指针做假减。已从 `manifest.json` 的
> `native_known_gaps` 清空，`make check`（`--native`）30/31 通过（唯一 gap 为
> `18_domain_lazy_load`：native 不承载领域插件符号，属设计内 SKIP）。

### 1a. 领域插件符号的设计边界（已上锁，非缺陷）

机器码 exe 是**独立**产物，运行时没有 Python 宿主、没有懒加载全局表，因此
`@：【加载领域】` 引入的符号（如 `公差系数_IT10`）在 native 侧不存在。已确证的
真实行为：带或不带加载指令，native 均把该符号当作未定义变量 → 运行期 `raise_rt`
以非零码干净退出、**不产出任何伪造值**（而非静默读成裸 0）。此边界由
`tests/test_native_domain_contract.py` 锁定：一旦退化回「静默造值」即红。工具链
缺失时该测试优雅 SKIP（只约束真实机器码路径）。

### 1b. NI-009（已修复）：块内不捕获外层的 `let rec` 令 native 访问违例

- **Bug 类**：合法程序在 native 编译成功却运行期崩溃（`rc=0xC0000005` 访问违例）、
  静默无任何输出——属 NI-001/002 同类「无声失败」。
- **真因（修正旧误判）**：与「递减/递增」**无关**。根因是闭包 env 快照的**寻址口径不一致**：
  `_emit_make_closure` 按**稠密序号**写入捕获槽（`off=24+8*i`），而读侧 `_emit_load_outer`
  与 GC `gos_env` 按**原始帧槽号**取（`off=24+8*slot`、`size=(ncap+3)*8`）。二者仅当被捕获
  槽号是从 0 起的连续段时吻合。函数块内的 `let rec` 只需捕获「递归盒」这一个**非 0 槽**
  （槽 0 为形参、槽 1 为盒），捕获集不连续 → 读侧按原始槽号越界取到相邻堆内存、再当 Box
  解引用 → 访问违例。（递增/捕获外层形参者槽号连续，故此前用例 19 恰好正常。）
- **修复**：`_emit_make_closure` 改为按**原始槽号**打包（`off=24+8*slot`），`ncap`/`env_size`
  按 `max(slot)+1` 跨度计算，与读侧、GC 三方同口径。捕获槽连续时新偏移与旧的稠密写法
  **逐字节相同**（既有通过用例基线不变）；仅此前必崩的不连续路径被修正。
- **回归锁**：黄金用例 `30_corpus_nested_rec_nocap`（函数块内**不捕获外层**的 `let rec` 递减
  累加器）vm ↔ interp ↔ native 三端逐字节一致；`19_corpus_recursion`（捕获外层、槽号连续）保留。
- **代价**：高槽号少量捕获时 env 留空洞、体积偏大（仅内存浪费，不影响正确性；空洞被保守 GC
  扫描，`gc_mark_candidate` 的区间 + 起点位双重校验保证不误标非对象地址）。

### 1c. native 的并发边界（设计口径，已上锁，非缺陷）

机器码 exe 是**单线程**产物，而且这个约束是三重的：

- 运行期自行解析的 kernel32 API 面是**封闭小集合**（`GetStdHandle`/`WriteFile`/
  `ExitProcess`/`LoadLibraryA`/`GetProcAddress`/`VirtualAlloc`），不含线程、纤程、
  临界区、原子操作或 TLS 中任何一个；
- 运行态（`heap_ptr`/`heap_limit`/`vstack`/`hstack_ptr`/`handler_top`/`raise_msg`/
  `sweep_start` 与 `bclo:*` 内建闭包）全部是镜像内的**进程级单例静态区**，以 rip
  相对寻址直接读写，没有 per-thread 隔离；
- 并发域（registry `Concurrent`、显示名「并发编程」：`创建线程池`/`提交任务`/`等待所有`
  等）**只经宿主的懒加载领域层进入语言**，VM 内建表里不存在这些名字，native 更没有。

实测的真实行为（与 1a 同一红线）：把带并发符号的程序交给 native，运行到该符号时
`rc=1`、stderr「未定义变量」、**stdout 一个字节都不出**——干净失败，不伪造值。
VM 直连路径同样显式失败（未加载领域 → `未定义变量 '创建线程池'`；带 `加载领域` →
`加载领域「并发编程」失败：本次运行未接入插件层`）；只有宿主入口（`src.kernel.exec_api.run`
经 interp）能真正加载并跑起并发域。

因此**唯一的 scale-out 路径是进程级并行**：多个 exe 各跑各的，实测同一枚 exe 并发跑
K 个进程的输出逐字节一致（数出自 `scripts/bench.py --native --parallel K`）。要在
native 内做线程级并行，需同时改 API 面、静态运行态与 GC 根口径，属未启动的工程项，
不是一个可开关的特性。另需区分：时间域的 `注册任务`/`执行待办`/`待办列表` 是**协作式
调度表**（既有口径：回调从不触发、执行待办恒返回 `[]`），三端一致，不是线程原语。

判据：`tests/test_native_concurrency_contract.py`——API 面基线被隐性扩大、线程 API 混入、
`src/mbc/` 引入并发模块、并发符号被硬编进内建表、native 对并发源码静默产值，任一发生即红；
工具链缺失时涉及真跑 exe 的用例优雅 SKIP。

## 二、语法层历史债务

曾经有 19 个 `.matha` 语料文件连 parser 都过不了（`matha/knowledge/`、`matha/resource/`、
`matha/vm/` 下的 Python 风格草稿：`？` 占位符误用、记录面 `#：{}`、`->` 位置错误、
`X if COND else Y` 后缀式、`(OP,)` 单元组尾逗号、空格标识符等）。本轮已把它们**改写为合法
Matha**（仅动语料内容，未改 parser/VM），文件**保留不删**（兼容承诺）并已进入主线解析。
当前「语料解析失败」计数为 **0**。

判据：`python scripts/ast_vm_matrix.py --write` 输出的「语料解析失败」计数应为 0；
[`ast_vm_gap.md`](ast_vm_gap.md) 与 `ast_vm_gap.json` 的 `unparseable` 字段为空。

## 三、符号能力覆盖面

| 范围 | 现状 | 行为 |
|---|---|---|
| 极限 | `.matha` 标准库只覆盖有理式（多项式商）+ 洛必达≤8 层 | 超越式（如 `sin(x)/x` 在 0）时标准库路径显式 `不支持: …`，`backend="auto"` **回退内核引擎 stage0 求解**并计入 `BACKEND_STATS["fallback"]`（非“不能算”：内核给与 sympy 一致的正确值，见 parity 第 4 节） |
| 泰勒/级数 | `.matha` 标准库只覆盖 `point=0` 的 Maclaurin | 非 0 点时标准库路径显式 `不支持`，**回退内核 stage0：`src/kernel/symbolic/series.taylor` 已覆盖任意点**；输出已改为 sympy 的 `(x-a)ⁿ` 中心形式（B 组不再乘开成 `x` 幂），`tests/test_kernel_taylor_centered.py` 逐字锁定（见 parity 第 5 节） |
| ODE | 一阶可分离 + 一阶线性积分因子 + 二阶常系数齐次特征方程 + 二阶常系数**非齐次**待定系数（右端限多项式/指数/正余弦及其乘积，含共振） | 越界右端（`1/x`/`ln`/`tan`/分式幂/三角积）与高阶/变系数抛 `OdeUnsupported`，不返回「无法求解」这种假成功；与 sympy `dsolve` 残差对拍锁入 `tests/test_kernel_symbolic.py`（见 parity 第 6 节） |
| 傅里叶级数 | 新增**仅内核引擎层**能力 `src/kernel/symbolic/series.fourier_series`（截断级数，系数经 `integrate` 精确回代）；尚未接入 `.matha` DSL 标准库门面 | 与 sympy `fourier_series` 同约定（`T=right−left`，基 `cos/sin(2πn(x−left)/T)`）；被积式无闭合原函数（`abs`/跨 0 的 `1/x`/双频三角积/`exp(x²)`/`log`×三角）抛 `SeriesUndetermined`，不数值伪造系数；采样点与 sympy 系数积分对拍锁入 `tests/test_kernel_symbolic.py`（见 parity 第 5 节） |
| 与 sympy 对照 | 内核纯实现为**子集** | 逐函数标注见 [`symbolic_parity.md`](symbolic_parity.md) |
| stage0 已知不准（已修） | ~~±∞ 极限用采样逼近、末位错~~、~~`evaluate` 不认识 `ln`~~ 两项均已修复：内核 `_limit_infinity` 把有理式**精确主部比**提到 t=1/x 数值归约之前（并补齐 ±∞ 奇偶变号，对标 sympy 主导项法）；符号解析器将 `ln` 归一为自然对数 `log` | stage0 与标准库两侧现在**逐位一致**，原偏差锁已转为平价锁（`tests/test_matha_stdlib_symbolic.py`）；另由 `tests/test_kernel_limit_rational.py`（±∞ 有理式精确值 + 0/∞ 边界）与 `tests/test_kernel_ln_alias.py`（ln 求值/求导/极限）锁定 |

## 四、跨后端差异（如实登记，不抹平）

运行时错误主体已大幅归一，并由 10 例错误黄金用例锁定（vm ↔ interp ↔ native）：
除零 / 取模除零 / 整除除零 / 类型不匹配 / 列表越界 / 字符串越界 / 不可调用 /
对不可下标对象取索引 / 调用未定义函数名——两端抛**同一异常类**且消息主体逐字一致。

本轮修掉了 VM 两处「漏出 Python 原生异常」的跨后端分歧，归一到解释器的领域消息：

- 调用非函数值：VM 原报 `RuntimeError: VM：不可调用的值 5` → 现 `MathaRuntimeError: 不可调用的值: 5`（与 interp 逐字一致）；
- 对不可下标对象取索引（如 `5[0]`）：VM 原漏 `TypeError: 'int' object is not subscriptable` → 现 `MathaRuntimeError: 索引操作不支持: int[0]`。
（越界索引的 `IndexError` 两端本就一致，保持透传，不在改写列。）

未定义变量类名分歧（interp 抛基类 `MathaRuntimeError`、VM 抛更精确的
`MathaUndefinedNameError`）也已闭合——interp 现也抛 `MathaUndefinedNameError`（它是
`MathaRuntimeError` 子类，`except MathaRuntimeError` 与宿主 `except KeyError` 均不变）。

**未定义函数名调用已归一**：此前解释器把未定义 callee 报为「未定义函数 'foo'」，VM/native
均报「未定义变量 'foo'」（VM 字节码里「读变量」与「调函数」共用 `LOAD_GLOBAL`，未命中即报
未定义变量）。本轮将解释器 `_eval_func_app` 的文案改写删除，与主线 VM/native 同口径上抛
「未定义变量 'foo'」，入错误黄金用例 `31_error_undef_func`。连带修正 `AutoDebugger`（`src/autonomous.py`）：
因其原依赖「未定义函数」文案区分调用位，现改为从**源码**判定（名字以 `name(` 出现即补恒零
函数，否则补默认变量），自动修复行为不变（`tests/test_integration/test_auto_debug_e2e.py` 9 例全过）。

判据：`python golden_tests/run_golden_tests.py` 末尾「跨后端 stderr 类名差异」报告为空。
黄金运行器仍保留 stderr **异常类名**白名单与消息主体逐字比对，防止未来重新引入差异。

## 五、治理与工程噪声

| 编号 | 问题 | 说明 |
|---|---|---|
| NI-007 | `import src.kernel` 本身零成本，但 `src/matha_system.py` 等聚合入口仍会拉起大量模块 | 内核纯净性由 `test_kernel_purity.py` 限定在 `lexer/parser/ast_nodes/kernel/mbc`；聚合入口不属内核 |
| NI-008 | 仓库根与 `scripts/` 历史遗留的一次性调试脚本 | 已集中移入 `scripts/scratch/`；不再作为现状依据 |

## 六、性能声明的口径

本文档集**不写**没有方法学的性能数字。可复现量具已落地：

- 量具 `scripts/bench.py`（语料 `scripts/bench_cases/`，`{N}` 参数化规模）；
  `--selftest` 做小规模确定性校验，`--json` 落 `docs/bench_baseline.json`
  （含版本/Python/平台/CPU/repeats/每段 min-median-max）。
- 允许写的数字必须同时给：①命令与语料 ②同机**相邻两轮** A/B（`git stash` 改动
  文件跑 A、恢复跑 B）③min 与 median 两个统计量 ④原始 JSON。缺任一项只准写「未测」。
  跨时段对比无效：本机实测漂移可达 ±25%（曾据此误判过一次收益）。
- 禁止：跨机对比、对未测路径外推、以及「加速 N 倍」式单数字营销表述。
  CHANGELOG 不写性能数字，只指向本节。
- 基准是**量具不是门禁**：`make check` 不设耗时判据（否则四道门禁会变成机器相关）；
  `--selftest` 可作为正确性烟雾测挂 CI。

按此口径的实测（同机 Windows/x86-64、CPython 3.14.3、repeats=5、只取 VM 单段；
命令 `python scripts/bench.py --only b06 --repeats 5`）：

| 场景 | 优化前 min/median | 优化后 min/median | 差 |
|---|---|---|---|
| b06 `get(xs)(i)` × 50000 | 1023.7 / 1035.6 ms | 788.6 / 791.3 ms | **-23.6%** |
| b04 `append` 构造 × 3000 | 63.9 / 64.1 ms | 57.0 / 57.7 ms | **-10.0%** |
| b09 `for` 语法糖 × 50000 | 879.4 / 880.7 ms | 901.9 / 906.6 ms | +2.9%（未受益） |

优化共两段缺一不可：编译器把完全应用的柯里化内建调用融成单条 `CALL N`（宿主
`_CURRIED_BUILTIN_ARITY` 与自举 `_预扫元数` 逐项同值），VM `_invoke` 对 `_Curried`
齐 arity 时直调 `fn(*args)`。融合的**安全前提**是：`get`/`append`/`slice`/`range`
不得在任一模块里被 `let`/形参/元组目标重绑（同名 `func` 声明合法，由元数表覆盖
机制以用户 arity 为准）。此前提不靠人记忆，由 `tests/test_curried_builtin_paths.py`
全仓库 `.matha` AST 扫描锁定（现扫 208 份语料，唯一命中为 `stdlib.matha` 的
`func range(...)`）。**b09 已转正**：`for` 的下标读取由发射器手写、不经元数表，
故正式修复必须**宿主与自举两侧同时改**并保证定点一致——本轮已两侧同步（宿主
`_emit_curried_builtin` 恒融合、自举 `_for循环码` 经 `_get齐参`/`_get逐步` 同判据分
支融成 `CALL 2`），原默认关闭的休眠开关已退役并入主门禁（下节 6a）。

**已试但未采纳**：把 VM 柯里化偏应用的中间值换成 `__slots__` 轻对象（`_CurriedPart`），
紧邻 A/B 下无收益（b06 反而 +8%：tuple 拼接与 `__call__` 分发比闭包更贵），已回退。

进程级并行（native 的唯一 scale-out 路径，见 1c）实测：命令
`python scripts/bench.py --json --repeats 5 --native --parallel 3`（已落
`docs/bench_baseline.json`，九场景均能编译成 exe 并 `rc=0`）。同一枚 exe 跑
3 次串行 vs 3 进程并发，speedup 实测区间 **2.4–4.13**（最低 b08 字符串拼接
串行 708.3ms → 并发 294.8ms；最高 b03 while 累加 104.6ms → 25.4ms），退出码全 0。
这是本机单机的实测值，不外推到其他硬件，也不构成「线性扩展」结论。

### 6a. 两枚发射器开关已退役转正（b09 双侧同步入门禁；sys_env 宿主恒开，属宿主独有能力）

原先两枚「默认关闭、开启仅供实测」的环境变量开关（`MATHA_B09_FUSE`、
`MATHA_SYSENV_FOLD`）本轮已**全部退役**——从 `src/mbc/compiler.py` 删除开关分支，
把转正后的**发射形状**与**安全边界**锁进 `tests/test_curried_builtin_paths.py`，确保
它们以后不会再破坏主线（b09 融合真双侧同步、逐字节定点；sys_env 属宿主独有、
靠防呆守卫兜底）。转正前各自的等价性参照（b09 用 HEAD worktree 导出语料对照；
sys_env 因 worktree 一次 `cd` 失败改为 `git show` + importlib 同包加载旧修订对照）见报告 §7：

- **b09 语法糖融合（真双侧同步转正）**：`for`/列表推导里手写的 `get(xs)(i)`、
  `append(res)(e)` 两步 `CALL 1` 融成单条 `CALL N`——宿主 `_emit_curried_builtin` 与
  自举 `_for循环码`（`_get齐参`/`_get逐步`）**两侧同判据**（`_fn_arities.get(name)==实参数`
  ⇔ `_查元数(元数表,name)==len`）、同入池顺序（get→xs→i，中间 CALL 不入池）。遮蔽安全闸
  保留：用户把同名 `func get` 定义成 arity≠2 时判据为假，退回历史逐步 `CALL 1`。`len(xs)`
  **不融合**（原生变参内建，`CALL 2` 会调错函数）。转正后定点真实读数：
  `tests/test_mbc_bootstrap.py` + `tests/test_mbc_vm_matha.py` 共 870 例**全绿**（原 ON 态
  唯一的红项 `test_m2_stage2_equals_stage3[for_loop]` 已随双侧同步转绿）；形状锁见
  `test_b09_for_sugar_fuses_get_append`（for→`[1,2,1]`、列表推导→`[1,2,2,1]`）与
  `test_b09_shadowed_arity_mismatch_keeps_stepwise`（遮蔽→`[1,1,1,1]`）。紧邻 A/B 收益保留
  （OFF min 858.8/863.0ms → ON min 724.5/724.3ms，约 -16%）。
- **sys_env 编译期折叠（宿主恒开，不可能双侧同步）**：`sys_env("KEY", "默认")` 遇字面量
  键→读宿主环境→`PUSH_CONST`，整调用折成字符串常量；恒定条件剪枝**仅折叠驱动**
  （比较至少一侧来自折叠才剪，纯字面量比较不剪），从而不含 sys_env 的源码与从不剪枝的
  自举侧逐字节一致。键非字面量时**编译期报错**，不退化成运行期未定义变量。因纯 Matha
  自举编译器无 OS 环境入口，折叠**无法双侧同步**——防呆靠守卫：`test_sysenv_never_appears_in_
  bootstrap_or_corpus` 断言定点/自举语料禁出现 sys_env，`test_sysenv_host_fold_shape` 锁宿主
  折叠形状（常量池无 sys_env 名、剪枝后 JZ 为 0、只剩 `输出` 一条 CALL）。

**为何不做成运行期内建**（设计边界，非偷懒）：VM 本身就是 Python 进程里的解释器，
运行期查环境变量必然经宿主 `os.environ` 中介；而把 `sys_env` 注册成 VM 内建会进
`_default_builtins` 全局表，改变自举编译器可见的符号面 → 定点与并发契约锁一起红。
编译期折叠把运行期查询彻底消灭，因此 **native 也无需 `GetEnvironmentVariableW`**，
`_APIS` 封闭基线（1c 节）可以一动不动。代价是该能力只认字面量键、且属编译期而非
运行期语义；「同一份字节码在运行期按环境自选快/慢路径」在本架构下不成立——指令
形状由发射器在编译期决定，运行期没有可切换的第二套形状，这也是它**只能宿主恒开、
无法与自举侧同步**的根本定论。取证工件与逐项读数见 `.trae/p4_b09_preview/B09_VERIFY_REPORT.md`。

## 七、多端交付与 AI 前端的定位（降级，非上锁）

P2 定位决策（2026-10）：以下通道**一律不入 `make check` 门禁**，README/文档不再
将它们作为现功能主张；各自保留在仓库内，但只按本节登记的实测口径背书。

### 7a. 独立可执行文件（`dist/` + `scripts/build_exe.py`）

- 构建脚本历史上带 4 处致命 bug（`global` 声明晚于使用、`args.matha-cc` 非法属性名、
  `--specpath` 与 `.spec` 互斥、汇总解包元数不符），从未端到端跑通过；本轮已全部修复。
- 修复后当场实测（Python 3.14 + PyInstaller 6.22）：`matha.spec` 构建成功，产物
  `--version` 报 v4.6.0（与 `src/__version__.py` 一致）、`eval "21+21"` 得 42、
  `run` 源文件正常——**构建链可复现，但不进门禁**，下次重建仍须当场验证。
- `matha-cc`：模块 `src/compiler/matha_cc_cli.py` 真实存在可用，但 pip 只注册了 `matha`
  入口点；README 已改口径为 `python -m src.compiler.matha_cc_cli` 或自建 exe。
  2026-11 补记：旧 `matha-cc.spec` 的 `EXE(exclude_binaries=True)` 无配套 `COLLECT`，所以
  「用 `matha-cc.spec` 自建独立可执行文件」这句 README 主张当时**做不到**（产物只落在
  `build/` 且启动即缺 Python DLL）。已改为 onefile 写法并实测跑通（见 9c）。
- `scripts/build_exe.py` 开头会**清空整个 `dist/`**（日志行 `[build] 清理: dist/`），所以只跑
  `--matha-cc` 也会把 `dist/matha.exe` 与历史离线包目录一并删掉。重建单个组件后想保留其它
  产物，需随后补跑对应 spec（或用 `--all`）。另：它的中间目录用 `dist_build/`，而
  `.gitignore` 只忽略了 `build/` 与 `dist/`，所以跑完会在 `git status` 里留下一个未跟踪的
  `dist_build/`（本轮未动 `.gitignore`，待单独确认后再加一行）。
- 工作目录里残留的 `dist/*.exe` 为主线收官前的旧构建，`dist/` 本就在 `.gitignore` 内、
  不受 git 跟踪，无定位效力（2026-11-06 已被上述 `build_exe.py` 清理逻辑重生成：
  `dist/matha.exe` 与 `dist/matha-cc/matha-cc.exe` 均为当日新建）。

### 7b. 其它交付端

- `mobile/`（Flutter）：仓库内实验性前端，零门禁；其 `assets/pyodide/build_wasm.{bat,sh}`
  与 `assets/deploy.{bat,sh}` 曾硬编码旧版本号 4.4.16（漂移于主线 v4.6.0），本轮已改为
  构建时从唯一版本源 `src/__version__.py` 读取（读不到即报错退出，拒绝以硬编版本继续），
  不再各说各话；仍零门禁，仅作实验性交付保留。
- `matha_wasm/`：整目录在 `.gitignore` 内、git 零跟踪（实测 `git ls-files matha_wasm` = 0），
  磁盘内容为旧快照副本；README 原「Pyodide WASM 运行时」主张已删除。
- `extensions/vscode-matha`：仅语法高亮小插件，不受门禁，不作功能背书。

### 7c. AI 前端（`src/ai_assistant*.py`、`src/openai_compat_server.py`、`src/ai_framework.py`）

- 实测零 `tests/` 引用（grep 无命中），README 亦无 AI 助手功能主张——属仓库内
  未背书代码，保留不删；其**输出正确性不入门禁**（编排/诚实锁见下条）。
- **阶段 6e 更新**：按下方判据「先入门禁」，AI 前端「输入→解析→执行→结果→感知」的**编排
  契约与诚实降级**（永不裸抛、schema 稳定、失败如实下沉）已由 `tests/test_ai_e2e_pipeline.py`
  入门禁锁定；但自然语言→代码/答案的**输出正确性仍不背书**、README 亦无 AI 助手功能主张。
  故五个前端文件的「未背书 / P2 降级」横幅保留不变——本通道属「接线已锁、结果不背书」。
- **未达成（6f-D 如实登记）**：`src/matha_growth.py` 的 `MathaGrowthEngine.grow` 对 `func`
  定义源码做常量折叠/死代码消除时，会将源码改写到语义破损（实测 `func 加(x, y) -> Int = …`
  被改写为 `func (x + y) -> Int`，丢失函数名）。这属未背书优化器的**输出正确性**缺陷（本
  节降级范围，不入门禁背书）；6f-D 仅锁其经 `UnifiedGrowth.self_grow` 的**四属性交接契约与不
  裸抛**（见 `tests/test_growth_subsystems_lock.py`），不背书改写结果。正确性修复另立轨道。
- **阶段 7·P1 更新（坏码底线已打死）**：为 `MathaGrowthEngine.grow` 加装不可绕过的**正确性闸门**
  （`_is_safe_candidate`：出码须 ①能被重新解析、②守恒原文已绑定的顶层名字 `Binding`/`FuncDef`）；
  未过闸门的候选**诚实回退**上一安全版本（`optimizations_applied` 置空、记 `errors`、不前传）。
  由此上条 `func` 丢名（元凶 A）与 `y = 3.0 + 4.0 → 7.0 = 7.0` 赋值退化为裸等式（元凶 B）两类
  **坏源码**已由 `tests/test_growth_optimizer_correctness.py` 入门禁封死——**只保证「绝不出坏码」，
  仍不背书优化的有效性/更快**（P2 修规则、P3 逐规则语义对拍，各自另立片）。合法三角折叠（`sin²+cos²
  → 1`，绑定名不变）经闸门照常放行。
- **阶段 7·P2/P3 更新（算术规则语义对拍背书 · 三角政策 A）**：常量折叠（P3-1 全行锚定，修优先级
  腐蚀）、常量传播（P2-2 纯字面量右端 + P3-2 逐行位置感知，修前向引用/重绑定腐蚀）、函数内联（P2-3
  保守正确）、算术恒等式（P2-1）四条**算术**改写，现每条同时经 P1 闸门 `_is_safe_candidate` 与 P2-0
  harness `_semantic_equivalent`（两侧各在一次性解释器独立跑一遍、比对可观测 `outputs`）**双验收**，
  分片锁入 `tests/test_growth_const_folding.py`、`tests/test_growth_const_propagation.py`、
  `tests/test_growth_const_propagation_forward.py`、`tests/test_growth_function_inlining.py`。
- **政策 A（三角恒等式分级背书 · 如实登记）**：`_apply_trig_identities`（如 `sin²+cos² → 1`、
  `tan → sin/cos`）为浮点近似、结果不逐位相等，`_semantic_equivalent` 的精确 `outputs` 比对会判「不等价」，
  故三角改写**不纳入**语义等价背书口径，维持 **P1/schema 级**背书（出码可再解析 + 守恒顶层绑定名，由
  `tests/test_matha_growth_engine.py` 锁定）——与上述算术规则的「双验收」分级不同，不粉饰为已语义背书。
  另注：`_apply_trig_identities` 现为 `MathaGrowthEngine` **核心方法**（非可选插件），「迁出为可选插件」
  是另一需单独批准的重构片，本轨道未做。grow 的 P1 坏码底线仍兜底全部规则；仍未背书：优化的有效性/更快。
- **phantom 已修（Tier 1·S4 落地；本条如实更正旧「阶段 7 新发现 phantom」登记）**：`MathaGrowthEngine._verify` 历史上曾把 `improved`(str) 误当 `CrossLanguageVerifier.verify` 的 `sources` 参数传入（`sources.items()` 抛异常被 `except` 吞 → `cross_language_consistent` 恒 False）。现按真实契约以 `{'python': <源码>}` 调用、只取两侧 `.success`/`.vm_outputs` 判据、不读默认 True 的 `result.consistent`（单语言场景假阳性），已由 `tests/test_growth_cross_verify.py` 入门禁锁定（该锁现随下方 G-1 真修复一并更新为主链口径）。`grow` 出码安全仍**只**依赖 P1 `_is_safe_candidate`，不依赖此字段。
- **阶段 7·G-1（已修：本条登记通道错配与真修复落地；旧「阶段 7 新发现 phantom」登记由本条继续推进）**：`_verify` 当时走的是 `CrossLanguageVerifier` 的 `"python"` 通道，而该前端
  （`src/mir2_frontend.py::PythonFrontend`）的 `compile` 实为 `ast.parse(source)`——即 **Python 子集**前端，只吃
  `x = 3.0 + 4.0` + `#1：[x]` 这类写法；`grow` 的输入域却是 **Matha 源码**（其 P1 闸门 `_is_safe_candidate` 用
  `src.parser.parse`）。实测（`.trae/verify_dialect_probe.py`）：`func f(x) -> Int = x + 1`、`func 加(x, y) -> Int`、
  `let a = 3` 在该前端均 `SyntaxError` → 两侧不可运行 → 当时返回的 `cross_language_consistent=False`。
  **定性**：不是 phantom（异常收敛为诚实 False，不误报一致），也不影响出码安全（P1 兜底）；但该字段对真实
  Matha 程序**结构性恒 False、不携带信息**，且旧 docstring 称该通道为「python（Matha）前端」属不准确措辞。
  **已修（真修复切片）**：`_verify` 改走 `grow` 输入域真正的主链——`src.parser.parse` + `src.interp.Interpreter`
  （P2-0 已拍板的一次性解释器通路；该执行体现统一落在 `src/growth_verify.run_outputs`，
  分支侧的 `_exec_outputs` 已薄转发至同一入口，见第八节）：合法改写能真判等、破坏输出的改写能真判破。
  同时移除已成死接线的 `self._verifier` 与模块级 `CrossLanguageVerifier` 导入（核心成长模块不再拖归档 MIR
  后端依赖），并将名不副实的 `GrowthReport.cross_language_consistent` 如实改名为 `semantic_consistent`（该判据
  比的是同语言改写前/后，不是跨语言）。已由 `tests/test_growth_cross_verify.py` + `tests/test_growth_report_fields.py`
  入门禁锁定（含旧误导名不得复活）。出码安全仍**只**靠 P1 `_is_safe_candidate`，不依赖此字段。
  **安全边界（已实测，.trae/host_exec_risk_probe2.py）**：`_verify` 现在走完整解释器执行源码，而 Matha 有
  `#：` 全能前缀可路由外语执行（`interp.foreign_eval` → ForeignRunner，含宿主内嵌/subprocess）。实测：
  `#：{ import os; open(...).write(...) }` 在主链上直接 ParseError，`#：{ P = 5.0 }` 与裸 `# import os`
  均被解析为 `MechUnit` 而**未执行**（哨兵文件未生成），故当前不引入宿主执行面。若将来 `ForeignDecl`
  路由到 ForeignRunner 真正落地，`_verify`（以及 `_exec_outputs`）必须补加拒绝守卫：含外来执行的源码
  一律不执行、诚实 False。
- **阶段 7·G-2（已处置，harness 的空输出假阳性）**：`_semantic_equivalent` 以「两侧 `outputs` 逐项相等」为判据，
  当两侧都**无可观测输出**时 `[] == []` 直接成立。实测（`.trae/vacuous_true_probe.py`）：
  `func f(x) -> Int = x + 1` 与 `func f(x) -> Int = x + 99`（语义不同、都无 print）被判 **True**——即「未验证≠一致」
  陷阱的另一实例。**已处置**：不改 harness 本体（P2-0 各规则对拍锁依赖其现有口径，且那些用例本身带输出；
  实测它们两侧均有可见输出，不落在空对空区间）；而在 `_verify` 采信前额外要求「两侧均有可观测输出」，
  无输出即诚实 False（保守方向，只收紧不放松），且**不设 `original == improved` 同文捷径**——同文垃圾或
  同文但无可见输出也不报一致；并由 `tests/test_growth_cross_verify.py::TestHonestDegradation`
  锁死（`test_vacuous_no_output_pair_is_false` / `test_one_side_silent_is_false`）。
- 已上锁的只有内核侧自动修复契约：`src/autonomous.py` 的 `AutoDebugger`/优化/自生长
  由 `tests/test_integration/test_auto_debug_e2e.py` 等 3 个 e2e 文件覆盖，不属本节降级范围。

判据：本节的实测命令（`python scripts/build_exe.py --matha --output <临时目录>`、
`git ls-files matha_wasm`）可随时复跑；若未来某通道要「上锁」，必须先入门禁再进 README。

## 八、成长引擎验证通路（G-1 / G-2 / G-3 / G-4 已修，G-5 已坐实不修）

对象：`src/matha_growth.py` 的 `MathaGrowthEngine._verify` 与 `GrowthReport` 的
语义佐证字段。以下五条均为**实测坐实**（探针与输出留在会话工件目录，不入库）。

### G-1（已修）：验证通路与输入域错配，且异常被静默吞掉

- 原实现 `self._verifier.verify(original, improved)` 借 `CrossLanguageVerifier`，
  但该方法的真实签名是 `verify(algorithm: str, sources: dict[str, str])`：把源码
  字符串当 `sources` 传入，每次抛 `AttributeError: 'str' object has no attribute 'items'`，
  再被 `except Exception: return False` 压平。
- 即便修好调用形态，通道本身也不匹配：该验证器的 `"python"` 前端是
  `src.mir2_frontend.PythonFrontend`，其 `compile` 实为 `ast.parse(source)`（Python 子集
  前端）；已注册前端集合仅 `python / rust / go / javascript / c`，**不含 matha**。而
  `grow()` 的输入域是 Matha 源码（`func` / `let` / 中文函数名）。
- 实测后果：`_verify` 对**任何**输入恒为 False，连「同一份等价源码自比」也报不一致
  ——字段不携带任何信息，且无法与真实的不一致区分。
- 处置：新增 `src/growth_verify.py`，用 Matha 主链（`src.parser` + `src.interp`）执行
  两份源码并比对可观测 `outputs`；`_verify` 委派给它；移除死接线 `self._verifier`；
  误导字段 `cross_language_consistent` 如实改名 `semantic_consistent`（旧名以 kwargs
  构造须 `TypeError`，已上锁）。异常不再被压平，改由 `SemanticVerdict.reason` 给出
  机器可读口径。
- 与阶段 7 分支实现的关系（合并后的单一真源）：分支曾把主链执行体落在
  `MathaGrowthEngine._exec_outputs`，main 侧落在 `src.growth_verify.run_outputs`。合并后
  前者退化为对后者的薄转发（只保留既有 P2-0 harness 的调用面），仓库内不再有第二套
  解释器执行代码；由 `test_exec_outputs_is_not_a_second_implementation` 锁定。

### G-2（已处置）：空对空假阳性

两侧都无可观测输出时，比对 `[] == []` 会判「一致」——语义不同的两个无输出程序被
误报等价（典型「未验证 ≠ 一致」）。处置：判据保守化，两侧须**运行成功且有可观测
输出且逐项相等**才判一致；并且**不设「同文即一致」捷径**（同文垃圾、同文无输出一律
不判一致）。由 `TestHonestDegradation` 锁死。

### G-3（已修）：出厂优化规则在多轮迭代下滚雪球式腐蚀

- 曾在 main 上实测：对两行源码 `x = 3.0 + 4.0` / `print(x)` 跑 `grow()`，产出
  `7.7.7.7.7.7.7.7.0 = 7.7.7.7.7.7.7.7.0` 一类文本——字面量被当作左值并逐轮重复
  展开（单轮产物即为退化赋值 `7.0 = 7.0`，输出多出 `True`）；`y = 2 + 3` 与
  `a = 7 / b = a + 1` 同样退化为 `5 = 5` / `7 = 7`、`8 = 8`。
- **修复机制（属优化器正确性轨道，阶段 7 P1/P2/P3）**：常量折叠保持左值绑定名
  （`x = 3.0 + 4.0` → `x = 7.0`），常量传播位置感知，且每轮候选改写必须过 P1 闸门
  `_is_safe_candidate`（出码可再解析 + 顶层绑定名守恒）。合并后实测读数：
  `x = 7.0`/`print(7.0)`、`y = 5`/`print(5)`、`a = 7`/`b = 8`/`print(8)`，三者
  `semantic_consistent` 均为 True，`7.7.7` 不再出现。
- 已上锁：`TestG3CorruptionPrevented`（产物等于预期、退化赋值被 P1 闸门拒绝、
  滚雪球串不出现）。同时保留「判据不因规则修好而放松」的锁：`_verify(ARITH_OUT,
  "7.0 = 7.0\\nprint(7.0)\\n")` 仍必须判 False 且原因为 `outputs_differ`。

### G-4（已修）：最终报告的佐证口径错位

`grow()` 返回的是最后一次迭代的 report，故字段原只描述「上一步 → 这一步」；多轮
滚雪球腐蚀会在中间步互相「一致」而溜过。现于出口处补
`report.semantic_consistent = self._verify(source, current)`，使字段描述调用方关心的
「原始输入 → 最终产物」，并由 `test_final_report_describes_original_to_final` 锁定。

### G-5（已坐实，不修）：`optimizations_applied` 与 G-4 同形的漏报

- 实测（`.trae/g5_probe.py`）：`grow("x = 3.0 + 4.0\\nprint(x)\\n")` 第 1 轮应用
  「常量折叠 × 1、常量传播 × 1」，第 2 轮空转退出；返回的正是第 2 轮的 report，
  于是 `optimizations_applied == []` 而 `improved_source` 已发生变化——三个用例全部
  自相矛盾（`y = 2 + 3`、`a = 7 / b = a + 1` 同样如此）。
- 与 G-4 区别：G-4 是**安全口径**错位（会把腐蚀说成一致），必须修；G-5 只使报告
  少报已应用的规则，不会把坏码说成好码，方向偏保守，故登记不修。
- 已上表征锁：`TestG5AppliedRulesUnderReported`——修它时该锁会先红，必须同步更新
  本条与锁，不得静默改口径。

### 安全边界（实测 + 结构兜底）

本片把 `_verify` 从「编译归档」换成「解释器执行」，属新增执行面，故：

- 实测：`#：{ import os; ... }` 与 `#：python：{ ... }` 均抛 `ParseError`；
  `#：符号 P = 5.0` 退化为 `MechUnit` 并抛未定义名；哨兵文件在所有形态下**均未生成**。
- 结构兜底：`run_outputs` 构造解释器一律传 `foreign_routing=False`（`src/interp.py` 中
  该开关为 False 时 `#：` 走「惰性防呆，不执行」分支），使宿主执行面不依赖一次实测
  结论。由 `test_interpreter_is_built_with_foreign_routing_off` 与哨兵锁共同固定。
  合并后 P2-0 harness 的 `_exec_outputs` 也已转发至同一入口，因此该兜底覆盖**全部**
  成长侧执行面（含各规则对拍锁走的那条），而非只覆盖 `_verify`。
- 口径提醒：安全断言是「不执行宿主代码」，而非「一律报不一致」——注释形态的
  `# import os` 同文且有输出时判一致是**正确**行为。
- 若将来 `ForeignDecl` 路由到 ForeignRunner 真正落地，除上述结构兜底外仍须补显式
  拒绝守卫：含外来执行的源码一律不执行、诚实 False。

### 仍未背书（本片不覆盖）

- 优化器输出的「有效性 / 更快」一律不背书；`_verify` 不是 `grow()` 的安全闸门。
  出码安全只依赖 P1 `_is_safe_candidate`（已由 `test_grow_safety_is_independent_of_verify_field` 固定）。
- 三角恒等式按政策 A 维持 P1/schema 级，不纳入逐位等价背书（见第七节）。
- 幻影字段 `performance_before_ms` / `performance_after_ms` / `languages_analyzed` 已在
  Tier 1·S5 从 `GrowthReport` 删除（本节旧版曾记为「待清理」，现已落实，锁在
  `tests/test_growth_report_fields.py`）。

## 九、CI 面（GitHub Actions）的实测口径与遗留

本轮（2026-11）把 main 上的红逐个定性后再动手，结论先说清楚：**main 上有红不等于
本次合并引入的回归**。判回归必须按 workflow + job + step 粒度与「上一个 main 出厂
点」同名对比；check-run 名称集合的差异会因 `cancel-in-progress` 漂移而误导。

### 9a. 权威回归门（只有这两份工作流允许自动触发）

- `.github/workflows/matha-ci.yml`：`lint` + `test`（Python 3.11/3.12 矩阵，零依赖核心
  执行链冒烟）+ `native-elf-gate`（x86-64 实跑逐字节对拍）。
- `.github/workflows/ci.yml`：`packages/**` 的 matha-auth 冒烟（带 paths 过滤，最近一次
  main 触发为 success）。
- 全量通过率唯一口径仍是本地 `python scripts/check.py`（`make check`）；GH ubuntu
  runner 环境不等价，不承载全量门禁。

### 9b. 三类「整文件被 GitHub 拒绝」的形态（已修，已上锁）

共同表征：Actions 列表里显示名回退成文件路径、`jobs=0`、历史连续 failure——比
「某一步失败」更隐蔽。取证与修复：

| 文件 | 根因（实测） | 处置 |
| --- | --- | --- |
| `cd-full.yml` | `run:` 写成多行纯量，值里 `echo "::error::…: black …"` 的 `: ` 让 YAML 报 `mapping values are not allowed here` | 改块纯量 `run: \|` |
| `stress_test.yml` | `strategy:` 挂在工作流**顶层**（只允许在 job 下），且 workflow 级 `env` 引用了 job 级 `matrix` 上下文 | 下放到各 job；`needs['stress-test']` |
| `release.yml` | 步骤同时写 `uses:` 与 `run:`（GH：一个步骤只能有其一）；`MATHA_DRY_RUN: \|\| false` 给 env 塞布尔值 | 拆成两步；默认值改字符串 |

由 `tests/test_ci_hygiene.py` 六条锁固定。反向对照实测：把改动前的 10 份工作流放进
临时目录逐条跑这些锁，每条都精确命中上表对应的那一处（顶层 `strategy`、
release.yml 的 uses+run、cd-full.yml 的多行纯量），不存在「无牙齿」的锁。

### 9c. 参数名 / 产物路径 / shell / spec 结构直修（`matha-ci.yml` + `matha-cc.spec`，已用 dispatch 实测）

验证方式：对分支头跑 `gh workflow run matha-ci.yml --ref chore/ci-hygiene`（本文引用三次
实测：run 42195342421 / 42198963200 / 42208252282），因为 `build-exe` / `offline-verify` 的
`if` 只放行 main、tag 或 dispatch，PR 上永远是 skipped，只有 dispatch 能真正跑到这两段。

- `offline-verify`：`package_offline.py` 只认 `--out`（CI 原传 `--output-dir` → argparse
  `unrecognized arguments`，exit 2，本地复现一致）；`verify_offline.py` 只认
  `--quick/--verbose/--json`（CI 原传 `--package-dir`）。**实测已转绿**：run 42195342421 的
  `Create offline package` / `Verify offline package` / `Upload offline package` 三步均 success。
  **口径提醒**：该脚本验证的是当前环境可导入性，不校验包目录内容，步骤名「Verify offline
  package」略强于实际。
- `build-exe` 的 shell：PyInstaller 本身**构建成功**（日志有 `Building EXE from EXE-00/01.toc
  completed successfully`、`Copying bootloader EXE to …\dist\matha.exe`），但旧写法在构建后紧跟
  `ls -la dist/matha-offline/matha.exe`：目录名是照历史上手工 `--distpath` 留下的
  `dist/matha-offline/` 想象写的，而仓库内 spec 并不往那里产出（见下条）。`ls` / 自检 /
  上传 / `publish` 的 Release 附件四处已统一改为 `dist/matha.exe`、`dist/matha-cc.exe`。
  **但路径改对仍不够**：`runs-on: windows-latest` 默认 shell 是 PowerShell，`ls -la` 直接报
  `A parameter cannot be found that matches parameter name 'la'`（run 42195342421 里
  `Build matha.exe` 确实挂在这一行）。已给两个构建步骤显式加 `shell: bash`；下一轮 run
  42198963200 实测 `Build matha.exe` **已转绿**。
- `matha-cc.spec` 不产出可运行产物（run 42198963200 里 `Build matha-cc.exe` 报
  `ls: cannot access 'dist/matha-cc.exe': No such file or directory`）。根因**不在 CI 配置里**，
  而在打包定义：它只有一个 `EXE(…, exclude_binaries=True, name='matha-cc')` 而**没有配套的
  `COLLECT`**（也没有 onefile 变体），所以 EXE 只落在 `build/matha-cc/matha-cc.exe`（本地实测
  3.9 MB），既不携带 Python DLL 也不进 `dist/`；直接跑它会报
  `Failed to load Python DLL '…\build\matha-cc\_internal\python314.dll'`。对比 `matha.spec`：
  它除了同样的 `exclude_binaries=True` EXE 外，还有一段标着「# 打包为单文件」、把
  `a_onedir.binaries` / `a_onedir.datas` 直接入 EXE 的写法，所以 `dist/matha.exe` 确实存在于
  本地（当日重建产物 29,969,600 字节≈ 30 MB，`--version` 报 `Matha v4.6.0`、exit 0）。
  已按同一口径修正 `matha-cc.spec`
  （并入 `a.binaries` / `a.datas`、去掉 `exclude_binaries`，与该文件头部本就声明的
  `pyinstaller --onefile matha-cc.spec` 一致）；本地实测：重建 exit 0、
  `dist/matha-cc.exe` 11,307,345 字节≈ 11.3 MB、`dist\matha-cc.exe info` **exit 0**（打印工具链信息）。
  未做过的事：CI `windows-latest` + Python 3.11 下的同一次构建仍需看合并后现场（本地为 3.14）。
  run 42208252282 实测两个构建步骤均已 success，且 `dist\matha.exe --version` 在 CI 上正常
  输出 `Matha v4.6.0`。
- **中文输出在非 UTF-8 控制台会裸抛**（run 42208252282 里 `Test executables` 的失败点）：
  `dist\matha-cc.exe info` 在 CI windows runner 上报
  `UnicodeEncodeError: 'charmap' codec can't encode characters in position 11-13`，栈顶是
  `src/compiler/matha_cc_cli.py:87`（`print("Matha LLVM 工具链 (matha-cc)")`）。这是**产品侧
  缺陷**：CLI 假定 stdout 能编码中文，而 Windows 默认控制台编码取当前 locale（英文镜像是
  cp1252）。本仓库 `src/` 里原本没有任何 `sys.stdout.reconfigure` / 编码兜底约定（全库仅
  `src/codegen/system.py` 在生成的 .bat 里写 `chcp 65001`；`src/matha_main.py` 的
  `_print_utf8` 名字带 UTF-8，实现却只是 `sys.stdout.write`）。
  **CI 侧 env 兜门已实测无效**：先试过把步骤切成 UTF-8（`shell: pwsh` + `PYTHONUTF8=1` /
  `PYTHONIOENCODING=utf-8` + `chcp 65001` + `[Console]::OutputEncoding`），run 42208958450 里
  这两个变量已在步骤 env 中给出，冻结 exe 仍按 cp1252 崩。本地 A/B 对照已证实机制：
  **冻结 exe 完全无视 `PYTHONIOENCODING`**（无 harden 的 exe 在 `cp1252:strict` 与 `utf-8` 下
  都输出相同的 UTF-8 字节、rc=0），而源码运行会尊重它（同一 env 下 rc=1 报 UnicodeEncodeError）；
  即 stdio 编码在打包时固定，运行时 env 改不了——本地（3.14）构建恰好固定成 UTF-8，以至于
  本地无法复现崩溃，CI（3.11）构建则落成 cp1252。**真修法已按批准落到产品侧**：
  `src/compiler/matha_cc_cli.py` 与 `src/matha_main.py` 各自内联 `_harden_std_streams()`
  （对 stdout/stderr 做 `reconfigure(errors="replace")`，保留原编码、只把不可编码字符降级为
  占位符，异常静默跳过），在两个 `main()` 顶部调用。未新增 `src/` 模块，因为 `core_py_lines`
  被 `docs/ARCHITECTURE.md` 锁定。本地双向实测：去掉兜底调用后 `python -m
  src.compiler.matha_cc_cli info`（`PYTHONIOENCODING=cp1252:strict`）抛出的异常与 CI 日志
  逐字相同（同为 `position 11-13`）；加回后 rc=0（中文降为 `?`）。回归锁见
  `tests/test_cli_encoding_fallback.py`（3 例，含上述反向对照）。CI 的 UTF-8 步骤保留，
  作为叠加保险；但按已证实的 env 无效机制，`Test executables` 转绿只能靠产品侧兜底，
  需第五次 dispatch 现场确认。`matha` 主入口的同类中文输出已一并覆盖（同一 helper）。
- lint 里 `mypy src/deps.py` 指向 082218c 已删除的模块（靠 `|| true` 才没红），改指
  其后继 `scripts/dep_audit.py`。run 42195342421 的 `Lint & Format Check` 已实测 success。

### 9d. 休眠清单（只改触发器，不改语义；均带 `ci-hygiene` 证据头）

以下工作流不再被 push / pull_request / schedule 自动触发，只能手动 dispatch（
`release.yml`、`publish_matha_auth.yml` 另保留 tag 触发）。休眠的理由逐条已实测：

- `benchmark.yml`：钉钉通知步骤因空 webhook 让 `curl` 报 `option : blank argument`（exit 2）；
  另已把它的 4 行 shell `echo … >> $GITHUB_OUTPUT` 写进 `python -c "…"` 字符串内的真 bug
  改为在 Python 内写输出。
- `multilang_benchmark.yml`：`tests/test_multilang_enhancement.py` 与 `scripts/benchmark_rust.py`
  均不在仓库（自 run#56（2026-10-05）起每次 main 都 failure）。
- `riscv_baremetal.yml`：`tests/test_hal_v2.py`、`tests/test_growth_engine.py`、
  `tests/test_lisp_ffi_mixed.py`、`tests/test_v130_unit_report.py`、`scripts/baremetal_riscv_demo.py`
  已全部在 5cce13b 删除（`git log --diff-filter=D` 逐个核实），历史 10/10 failure；它的
  `paths` 过滤含 `src/inner_loop.py`，所以主线任何执行器改动都会把它拉起来跑红。
- `stress_test.yml`：`tests/stress_test_10khz.py`、`tests/test_hal_perf.py`、
  `tests/test_hal_multiprocessing.py` 均不存在；每日 cron 只会制造无意义红。
- `docker_build_push.yml`：`docker/login-action` 报 `Username and password required`。
- `cd-full.yml` / `release.yml` / `publish_matha_auth.yml`：除 9b 的结构修复外，仍引用
  仓库中不存在的 `scripts/k8s_failover_drill.py`、`docs/release_report.json`、`check_files.py`、
  `check_git.py`、`tests/test_jupyter_magic.py`、`tests/test_pkg_manager_dependency.py`、
  `extensions/vscode-matha/package-lock.json`。

### 9e. 登记但不修（诚实面，不在本 PR 范围）

- **仓库 secrets / variables 均为 0**（`gh api …/actions/secrets` 实测）。被引用但不存在的
  有 11 个：`DINGTALK_WEBHOOK`、`DINGTALK_SECRET`、`DOCKER_USERNAME`、`DOCKER_PASSWORD`、
  `PYPI_TOKEN`、`OVSX_PAT`、`VSCE_PAT`、`PROD_KUBECONFIG`、`STAGING_KUBECONFIG`、
  `JWT_SECRET` 等。凭据不就绪，全部通知/镜像/发布类步骤不可能成功——这是基础设施缺失，
  不是代码缺陷，也不该靠 mock 刷绿。
- 两份 spec 里 3 处死 `hiddenimports`（`matha.spec` 的 `src.tree_sitter_backends` 与
  `src.domains.hal`、`matha-cc.spec` 的 `src.domains.hal`）仍会让 PyInstaller 打
  `ERROR: Hidden import … not found`，但实测**不阻断构建**（修完 `matha-cc.spec` 后本地重跑
  仍只有这一行 ERROR、exit 0）。这几行本身仍属登记不修：经批准修的只是 9c 里的 EXE 结构
  缺陷，没有顺手动 `hiddenimports`，因为它们需要单独的清理与全量产物实测。
- `matha-ci.yml` 的 `benchmark` job 主体依赖已删除的 `src/vm.py`（`git ls-files src/vm.py`
  无输出）。首版改造降为仅 dispatch，但 run 42195342421 实测：一旦 dispatch 就会以
  `ModuleNotFoundError: No module named 'src.vm'` 失败，把整个验证 run 染红，反而失去「用
  dispatch 单独验 build 链路」的手段。故改为 `if: false`（保留定义、任何事件都不跑），要么
  重建基准入口、要么删除——本 PR 不背书本机不能跑的那一段。
- 上述休眠工作流内部仍有可能的 GH 侧拒绝原因未逐个穷举（本地只能复现 YAML/结构层）；
  真正的判据是推分支后看 Actions 现场：休眠文件不应再产生任何 run。

