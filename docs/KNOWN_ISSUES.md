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
  产物，需随后补跑对应 spec（或用 `--all`）。另：它的中间目录用 `dist_build/`，早期
  `.gitignore` 只忽略了 `build/` 与 `dist/`，所以跑完会在 `git status` 里留下一个未跟踪的
  `dist_build/`；已于 2026-11-06 在 `.gitignore` 的“发行/构建产物”段补上 `dist_build/` 一行
  消除该噪声（`git check-ignore dist_build/` 实测命中）。
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

- README 亦无 AI 助手功能主张——属仓库内未背书代码，保留不删；口径统一为
  **编排已由 6e 门禁锁（`tests/test_ai_e2e_pipeline.py`）固定、结果正确性不背书**（详见下条）。
  本条 2026-10 初登记的「实测零 `tests/` 引用」措辞已过时，特此更正登记；
  `src/openai_compat_server.py`、`src/ai_assistant_server.py`、`src/ai_assistant_desktop.py`
  三个复用 chat 编排链的文件横幅已于 2026-11 同步改为该口径；`src/ai_assistant.py` 横幅本就
  是该口径；`src/ai_framework.py` 横幅已随 2026-11 数值地基坐实更新（见下方新条目）。
- **2026-11 数值地基坐实（`src/ai_framework.py`）**：历史上该模块是 API 壳——`Linear.forward`
  对 bias 标量做下标即崩（实测 TypeError）、Softmax 返均匀 1/n、损失/`train_step` 恒返 0.0、
  `evaluate` 硬编码、`jacobian` 恒等透传。本轮以**矩阵乘法 `matmul` 为地基**重写整条数值腿
  （Linear/激活/损失/逐层反向/优化器/训练/序列化/Conv2D 前向），三类锁已由
  `tests/test_ai_framework_numerics.py`（39 条）入门禁：手算对拍（含与 `domains.ai_data_science`
  跨引擎子进程互证）、收敛闭环（线性回归找回闭式解 + XOR 证明反传链真接线）、显式拒绝
  （形状不合/未实现反向的 BatchNorm・Conv2D backward/未 compile 一律抛错，封死静默零占位回退）。
  同日追加**严格测试背书层**（同文件扩至 57 条）：代数性质律（结合律/分配律/转置律，seeded
  随机阵）、边界值（±1e308 饱和、零方差列、大 padding、退化/空输入拒绝、零梯度 no-op）、
  全模型中心差分**梯度神谕**（两层 MLP 逐参数 22 元素逐个对拍，封死反传链接线级造假）、
  **SymPy 符号对拍**（MSE/softmax-CE 梯度、matmul、sigmoid 导数，本机实跑零 skip）与训练
  健壮性（随机目标记忆、同种子逐位确定性、save/load 推理不变）；据此背书升级经全量门禁
  **5238/5238 通过**（基线：主工作树 `pytest tests`，23m50s，零失败零跳过）。
- **2026-11 BN/Conv2D backward 攻坚（显式拒绝边界坐实）**：继数值地基后的剩余拒绝锁已攻下——
  `BatchNorm.backward` 实现闭式归一化梯度（dγ=Σ dout·x̂、dβ=Σ dout、dx 含 mean/var 依赖项），
  `Conv2D.backward` 实现与朴素前向逐路对应的 dW/db/dIn（含 stride/padding 窗位回流）；
  旧「backward 未实现」拒绝锁替换为误用拒绝锁（未前向先反向→RuntimeError、梯度形状不合→ValueError）。
  严格锁同文件追加至 **65 条**：闭式小整数现场手算对拍（BN 4×2 含投影不变量、Conv 3×3×k2 含
  9 元素 dIn）、任意深度逐参数中心差分神谕（BN-MLP 全 19 元素、Conv 含输入梯度回流 9+16 元素、
  stride2 多通道几何 10+16 元素）、训练链落地（BN 记忆线性可表示目标 loss→0、Conv 单层 train_step
  降两个数量级）。攻坚持证：神谕侧曾因非对称扰动（+ε/−2ε 除 2ε）带 1.5× 系统误差，经导数
  定义法（单侧小步长）仲裁坐实**实现正确**、测试构造修正为对称 ±ε；另如实登记：2 维输入经
  Linear+BN 的特征张成空间有限，任意 Y 不可全记忆（残余 0.070025 是真约束极小非 bug）。
  重跑全量门禁 **5246/5246 通过**（基线：主工作树 `pytest tests`，18m59s，零失败零跳过零 error）。
- **2026-11 A1+A2：save/load 覆盖 BN・Conv 与 eval/训练态翻转坐实**：继 backward 攻坚后收掉两条
  登记边界——`save/load` 现逐字段往返 BN（γ/β/running EMA 态/momentum/eps）与 Conv（4D 权重/
  几何参数），并封死新发现的半截病理（未知层 save 静默写缺 spec、load 才崩→现为 save 即
  ValueError 显式拒绝）；新增 **Model.eval()/train() 级联**（此前只有 Layer 级，模型层名实不符）。
  严格锁同文件追加至 **71 条**：逐位往返+加载后推理不变+加载后 train_step 真接可训练环（反传
  落梯+残差归零）、running EMA 两步手算（含 var 初值 1.0 混入项）、训后 eval 记忆不漂移
  （全批下 running→batch，loss<1e-4）。据此重跑全量门禁：
  **5252/5252 通过**（基线：主工作树 `pytest tests`，23m32s，零失败零跳过零 error）。
- **2026-11 A3：Dropout 训练链实战坐实**：随机性契约明确化——`seed` 非 None → 掩码逐次
  forward 冻结（可复现现场，梯度神谕可用）；`seed=None` → 掩码逐步推进且改由**全局
  random.seed 控制**（旧实现实例内 `Random(None)` 不可复现，已纠）；未前向先 backward →
  RuntimeError 误用拒绝（与 BN/Conv 并列）。严格锁追加至 **76 条**：冻结掩码下含 Dropout
  两层链全 13 参数元素中心差分对拍、keep 率统计健康（n=40000，拦固定假掩码）、seed=None
  逐步变掩码实战收敛锁。如实登记：训练期 loss 含掩码 forward 噪声地板（探针实测尾窗均值
  ~1e-3 量级而权重已近优，p=0 基线可至≈0），故收敛锁口径为尾窗均值降一个数量级以上而非
  绝对阈值。据此重跑全量门禁：**5257/5257 通过**（基线：主工作树 `pytest tests`，24m09s，
  零失败零跳过零 error）。
  **仍未背书**：训练有效性主张（泛化/收敛速度的现功能级宣称，收敛锁只证明链路正确性）、
  先进深度能力（ComputationGraph 属演示级、多样本 batch Conv 未锁、
  save/load 不覆盖 Dropout 种子）——横幅保留 P2 降级定位，
  口径为「数值腿（含 BN/Conv 反向、Dropout 链、序列化与态翻转）已经严格测试背书、深度能力不背书」。
- **2026-11 阶段 1 AI 修复：ml.py 崩溃与假神经网络插件坐实**：两处历史病理已直修——
  ① `src/ml.py`：`ModelResult` 缺 `bias` 字段致 Linear/Logistic `fit` 必崩（实测 TypeError）；
  `create_model` 对 6 种未实现 ModelType 静默回退线性回归、`train` 假 hasattr 回退、
  `predict` 未创建静默返 `[]`、KMeans `k>n` 潜藏 IndexError。现补 `bias` 字段，未实现类型/
  空数据/样本标签数不合/`k<1`/`k>n`/未知评估指标一律显式抛错；`tests/test_ml_models.py`
  **31 条**行为锁（闭式解对拍 y=2x+1、逻辑回归可分数据全对、KMeans 手算 inertia、拒绝矩阵）。
  ② `src/domains/neural_network.py`：历史上 forward/predict 恒等透传输入、train 恒 loss=0、
  CNN/RNN 构建方法返回假 dict，属假实现。本轮委托已背书的 `ai_framework` 数值腿重写前馈链
  （Linear+激活/MSE/Adam），CNN/RNN 在仓库内无背书实现、构建方法一律 `NotImplementedError`；
  注册形态修复为**柯里化 lambda 链**（Matha `f(a,b)` 在 VM 与 interp 两侧均编译为 `f(a)(b)`，
  平铺多参 lambda 被首参提前求值——历史「创建神经网络(2,4) 报不可调用的值」之根因）。
  `tests/test_neural_network_plugin.py` **38 条**行为锁：前向手算对拍（1e-12）、XOR 真收敛
  （seed 7 / lr 0.05 / 4000 轮，loss<0.02、acc=1.0）、显式拒绝矩阵、manifest 符号面不漂移、
  干净子进程经 exec_api 懒加载端到端；manifest 符号面保持不变。
  据此重跑全量门禁 **5404/5404 通过**（`make check`：tests 5301 + kernel_purity 14
  + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，零失败；native 1 例
  已知未实现跳过不计入；tests 项 18m24s）。
  **仍未背书/未修**：训练有效性主张（泛化/收敛速度，口径同上文）；CNN/RNN 执行链与
  ml.py 其余 6 种 ModelType 仍在显式拒绝中。（本条原记「阶段 1 余项未开工——
  data_science 仍是假实现、llm_parser 的 Claude/Gemini 分支缺陷未触及」，措辞已过时，
  特此更正登记：余项已修复并入门禁，见下条。）
- **2026-11 阶段 1 余项收官：data_science 真实现、llm_parser 双链修复、可选依赖诚实面、
  死接线清理**：
  ① `src/domains/data_science.py` 假实现全部重写为手算可验证的真实现：`load_csv` 真读
  CSV（等宽校验、坏单元格带行列号抛错、标签列保留字符串、文件不存在如实抛错）；
  `split_train_test` 校验比例与切分点、返回拷贝切片的两个新数据集；`normalize` 逐列
  min-max（常量列显式抛错）；`one_hot_encode` 按标签首现顺序编码；precision/recall/f1/
  confusion_matrix 按二分类 {0,1} 真计数（零除约定 0.0，口径同 sklearn zero_division=0；
  accuracy 保持多分类通用）；`select_k_best` 无背书算法、显式 `NotImplementedError`。
  注册形态为柯里化 lambda 链，manifest 8 符号面不漂移。
  `tests/test_data_science_plugin.py` **59 条**锁（手算对拍、拒绝矩阵、注册契约、
  2 条干净子进程 exec_api 端到端）。
  ② `src/intent/llm_parser.py`：Claude 分支去除 Anthropic SDK 不支持的
  `response_format`（原必降级）；Gemini 分支先 `_get_client()` 再取 `_gemini_client`
  （原 AttributeError 必崩）。`tests/test_llm_parser_backends.py` **16 条**离线 mock 锁：
  各后端请求形状、response_format 按模型分发与不兼容重试、可重试错误重试后成功、
  不可重试/坏 JSON 降级正则兜底、缓存与空输入短路（零网络、零真实 SDK 依赖、密钥全假）。
  ③ `src/mcp_server.py`：mcp SDK 懒导入——缺包时 import 不崩、`create_server()` 诚实
  `ImportError`；`MathaMCPServer` 改纯同步门面（真委托 `_safe_*` 助手），删除
  `_register_matha_tools` pass 占位；版本号改 `src.__version__` 单源（去硬编码 "4.4"）。
  `src/tools/llm_config.py`：cryptography 改 `_fernet_class()` 懒导入（缺包诚实报错），
  `pyproject.toml` 新增 `llm` extra 正式声明。`tests/test_mcp_server_facade.py` **10 条**
  + `tests/test_llm_config.py` **12 条**（缺包干净子进程 Blocker 锁、加密往返磁盘无明文、
  密钥管理、env 优先、假 SDK 注入锁六工具名）。
  ④ 顺带坐实并修复 `src/compiler/matha_cc.py` 词法死循环：id-start 谓词
  （`ord>0x2E00` 兜底接受 ：【， 等全角标点）与续符谓词（isalnum/"_─"）不一致 →
  零宽 token 使 tokenize 永不前进（实测 `#1：[1+1]` 挂死 >300s）。首字符无条件消费后
  全角标点不再挂死；legacy 语法不支持的现代 `#1：` 写法诚实报「编译失败」而非挂死。
  ⑤ `src/matha_system.py` 三处死接线（审计原记两处，实测三处）：`ai_eval` 改调真实
  `chat(text)["reply"]`（原调用不存在的 `eval()`）；`lsp_start` 显式
  `NotImplementedError`（仓库仅有进程内分析 API，无 LSP 协议线服务，原调用不存在的
  `start()`）；`mcp_start` 接真 `create_server().run_stdio_async()`。
  `tests/test_matha_system_ai_wiring.py` **7 条**锁。
  本轮新增 **104 条**测试，据此重跑全量门禁 **5508/5508 通过**（`make check`：
  tests 5405 + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，零失败零跳过；native 1 例已知未实现跳过不计入；tests 项 19m54s）。
  **仍未背书/未修**：LLM 后端只锁请求形状与降级路径，真实 API 的回答正确性不背书
  （口径同本节）；`matha_system.py` 其余假门面（create_convnet/create_rnn 假 dict、
  load_csv 恒 True、normalize_data 透传、quantum grover/shor 假实现等）本轮未触及
  （**2026-11 更正**：其中 AI/ML/数据门面已于阶段 5 修复，见上方阶段 5 条目；
  quantum grover/shor 非 AI，仍未修（**已于阶段 9 真化清除**，见下方阶段 9 条目））；
  `src/unified_parser.py` 的 matha_compile 兼容假产物
  （"# Compiled N declarations" 字符串）仍在（**已于阶段 9 清除**：真编译计数摘要 +
  LLVM 假产物显式拒绝，见下方阶段 9 条目）；legacy matha-cc 语法不支持现代 `#1：`
  输出写法（诚实拒绝，非缺陷）；CNN/RNN 仍在显式拒绝中（ml.py 其余 6 种 ModelType
  已于阶段 4 真实现，见上方阶段 4 条目）。
- **2026-11 阶段 2 AI 修复：ai_framework 入主链、意图 Matha 代码生成、nl_pipeline 执行段、
  Jupyter magic 断点修复**：
  ① `src/ai_framework.py` 接入插件主链：`scripts/gen_domain_manifest.py` 新增
  `EXTRA_PLUGIN_MODULES` 域外插件通道（追加在全部 domains 模块之后，重名符号按「后者覆盖」
  规则归 domains 插件），manifest 增第 83 条目（82 域插件 + 1 域外；README「82」仍是
  `src/domains/` 目录覆盖口径）；注册形态改柯里化 lambda 链（Matha `f(a,b)` 两侧均编译为
  `f(a)(b)`，数值锁同步改柯里化调用），`创建神经网络` 移出 ai_framework、由 neural_network
  插件唯一持有（`owners_of` 锁）。`tests/test_ai_framework_manifest.py` **13 条**四向一致性锁
  （钩子 ↔ `_ai_framework_names` ↔ registry 模板 ↔ manifest，14 符号）+ 2 条干净子进程
  exec_api 端到端（auto 懒加载零 domains 泄漏、显式 `@：【加载领域】，AI框架`）；
  `--check` 往返回归一致。
  ② `src/intent_parser.py` 增 Matha 代码生成轨（`target_lang="matha"`）：只映射内核 builtin
  （sin/cos/sqrt/阶乘/素数判定/max/min/sum/平均值/最大公约数/最小公倍数等）与纯算术；
  混合运算、范围语义（N到M）、无映射函数、整数-only 约束、参数数不合、多函数歧义一律
  显式拒绝并留痕；`src/repl.py` 与 `src/repl_v23.py` 的 nl 模式改产 Matha 并经 exec_api
  端到端真算；`src/enhanced_intent.py` 的 `execute_and_verify` 显式拒绝非 python 目标；
  python 旧轨（main.py/parser_pool）不动且已锁。`tests/test_intent_parser_matha.py`
  **59 条**（精确代码锁 + 主链数值锁 + 拒绝矩阵 + 双 REPL 子进程端到端）。
  ③ `src/nl_pipeline.py` 补阶段 4 执行段：**纯算术等式**保守翻译为
  `func 名(自由参数) -> Float = 右式`（`^`→`**`；func 直expr体以 `(` 开头会被解析为
  lambda 参数列，前置乘法单位元 `1.0 *` 规避），附全参数=1.0 单位探针经
  exec_api.run_checked 验证可执行性——**探针不是用户语义的答案**；集合运算/含函数调用/
  仅声明/非 ASCII 符号一律跳过并记入 execution_notes；执行错误沉入 execution_error，
  不抛穿 run()。`tests/test_nl_pipeline_execution.py` **24 条**（真算锁、诚实跳过、
  拒绝矩阵、错误下沉、多时代稳定、注释卫生）。
  ④ `src/jupyter/matha_magic.py` 历史断点修复：旧链把 MIRNode 对象传给只接受 str 的
  execute_mir（必 AttributeError），回退 interpret 同样吃不下 MIRNode，%matha 从未算出过
  结果；现改为 `intent.suggested_code` 经 `exec_api.run_checked` 真算，result 绑定且无输出
  指令时补 `#1：[result]`；MIR 降为预览展示（`mir_generator.py` RETURN 序列化不再丢 value），
  execute_mir 不再被消费；分解器裸 `#` 兜底标记显式拒绝（Matha 中裸 `#` 是外来声明前缀，
  主链会静默 NOOP）；错误下沉并保留错误前已产生的输出；IPython 缺席时注册静默跳过、
  展示降级 print。`tests/test_jupyter_magic.py` **18 条**（含 fake-IPython 干净子进程注入锁：
  注册 + line/cell 魔法 + Markdown 展示，零 skip）。
  本轮新增 **114 条**测试，据此重跑全量门禁 **5622/5622 通过**（`make check`：
  tests 5519 + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，零失败零跳过；native 1 例已知未实现跳过不计入分母；tests 项 17m01s）。
  **仍未背书/未修**：开放域自然语言理解（正则兜底仅覆盖算术/平方根等窄路径，LLM 真实 API
  的回答正确性不背书，口径同本节）；`nl_to_formula.py` 预览源码（`let …`/`^`/裸 `#`）仍是
  非执行形态（执行段只翻译纯算术等式）；magic 输出正确性限于分解器可映射窄路径；
  `src/compiler/ir.py` 的 execute_mir/compile_mir 保留为 legacy IR 演示（magic 不再消费）；
  阶段 3（ml/genetic_algo/servers 测试口径升级）已于 2026-11 完成（见下条）；阶段 4
  （LLM 接 REPL/CLI、密钥统一 llm_config、MCP 工具注册、openai_compat 鉴权流式、
  其余 ModelType 算法、examples/ai 重写）已于 2026-11 完成（见下下条）。
- **2026-11 阶段 3 AI 修复：ml/genetic_algo/data_science 行为级三锁、三 server 冒烟、
  LLM 降级契约**：
  ① `src/domains/genetic_algo.py` 全入口参数校验（正整数/概率区间/适应度须 Python 可调用
  且返回值非负有限/种群非空齐宽 0-1 位串，bool 一律拒绝）；两处真实缺陷修复——全零适应度
  原静默偏向末位个体改均匀选择，len≤1 染色体交叉原 `randint(1,0)` 必崩改诚实无操作；
  注册改柯里化 lambda 链（Matha `f(a,b)` 两侧均编译为 `f(a)(b)`），符号面不变（7 符号，
  manifest `--check` 往返一致）；Matha 闭包（VM Closure / interp 元组均非 Python 可调用）
  作适应度回调显式拒绝并留痕，不假装支持跨语言回调。`tests/test_genetic_algo_plugin.py`
  **105 条**：手算对拍（退化轮盘/早停/单点交叉语义/变异边界抽签/精英排序与平局/NESMA
  数值/代码生成替换与未匹配留痕/超参最优）、收敛闭环（seed 42 全 ones、seed 123 全 zeros
  出发、神经进化、超参搜索）、显式拒绝矩阵、注册契约（manifest 对拍/柯里化形状/偏应用
  可调用/回调拒绝）+ 3 条干净子进程 exec_api 端到端。
  ② `src/ml.py` 三锁口径升级：训练参数与矩阵形状入口校验（ragged/空特征/宽度漂移拒绝），
  未训练 predict 显式拒绝（三模型 + 管理器层）；逻辑回归改稳定 sigmoid（原 `exp(5000)`
  溢出必崩，±1000 饱和与极端特征拟合锁）、标签 0/1 校验、阈值 [0,1] 校验；KMeans trained
  生命周期；evaluate 样本数不一致显式拒绝；注册改柯里化（legacy registry 通道，符号面
  不变）。`tests/test_ml_models.py` 31→**96 条**（+65：未训练拒绝/维度边界/sigmoid 饱和/
  超参与逻辑回归边界矩阵/收敛闭环——多特征 `y=3x1-2x2+0.5` 权重 1e-6 对拍、loss<1e-10、
  k=1 手算质心与 inertia）。
  ③ `src/domains/data_science.py` 管线闭环：`tests/test_data_science_plugin.py` 59→**62 条**
  （+3：CSV→split→normalize→one_hot→训练评估全链手算对拍——accuracy 2/3、precision 1.0、
  recall 0.5、f1 2/3、混淆矩阵 [[1,0],[1,1]]；split 切片独立副本锁；管理器管线链）。
  ④ 三 server 冒烟 + LLM 降级契约：`tests/test_ai_servers_smoke.py` **25 条**
  （ai_assistant_server 13：health/concepts/help/404/CORS/空消息与坏 JSON 400/正常契约
  与感知计数/异常 500 诚实下沉；openai_compat 11：models/health/404 形状/CORS/缺 messages
  400/chat.completion 形状与 usage/最后一条用户消息/SSE 形状与 [DONE]/text_completion/
  异常 200 诚实降级；desktop 启动接线 1：FakeServer 锁监听地址/Handler/浏览器打开）；
  `tests/test_llm_parser_backends.py` 16→**19 条**（+3 降级契约：外层 catchall 兜底留痕、
  重试耗尽恰好 3 次后兜底、降级意图类型来自分解器非 UNKNOWN）。五个前端横幅口径同步
  （HTTP 层/启动接线冒烟已入门禁，「未背书 / P2 降级」标记保留，结果正确性仍不背书）。
  本轮新增 **201 条**测试，据此重跑全量门禁 **5823/5823 通过**（`make check`：
  tests 5720 + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，零失败零跳过；native 1 例已知未实现跳过不计入分母；tests 项 17m46s）。
  **仍未背书/未修**：LLM 真实 API 的回答正确性不背书（口径同本节）；三 server 的结果
  正确性不背书（冒烟只锁 HTTP 层/启动接线/降级形状）；阶段 4（LLM 接 REPL/CLI、密钥统一
  llm_config、MCP 门面 parse_intent 缺口、openai_compat 鉴权与真流式、其余 6 种 ModelType、
  examples/ai 重写）已于 2026-11 完成（见下条）。
- **2026-11 阶段 4 收官（AI 链最后一公里：LLM 进 REPL/CLI、密钥统一、MCP 补全、openai 兼容加固、ml.py 九算法齐、examples/ai 真可跑）**：
  ① **LLM 链落地两个活 REPL/CLI**：`LLMIntentParser` 新增 `target_lang="matha"` 可执行轨
  （生成 `result = 表达式\n#1：[result]`），默认仍为 "mir"（旧行为不变）；`src/repl.py`
  （matha_main 入口）与 `src/repl_v23.py`（根 main.py 入口）接入，`MATHA_REPL_LLM ∈ {1,on,true,yes}`
  显式开启、默认关闭，LLM 不可用时诚实降级回正则解析器（打印降级原因，不静默）；
  新 `tests/test_repl_llm_link.py` **35 条**（fake 后端驱动，含降级契约与开关语义）。
  ② **密钥管理统一**：llm_parser 四处 env 读取改为统一优先级链 **显式参数 > 环境变量 >
  llm_config 加密 store > None**（env 优先不变，store 读取失败诚实返回 None 不抛）；
  CLI 新增 `llm-config` 子命令（set/get/list/delete，密钥不回显）；
  新 `tests/test_llm_key_unification.py` **17 条**（仅用假密钥）。
  ③ **MCP 门面补齐**：`parse_intent` 注册为第六工具，五方法 vs 六工具缺口关闭，
  `tests/test_mcp_server_facade.py` 10→**12 条**。
  ④ **openai_compat_server 加固**：可选 Bearer 鉴权（`MATHA_OPENAI_API_KEY` 设置即启用，
  `hmac.compare_digest` 恒定时间比较，/health 恒开放，401 形状
  `{"error":{"message","type":"authentication_error","code":"invalid_api_key"}}`）；
  SSE 改协议正确增量（首帧 role delta + 8 字符增量 + `{}`+finish_reason=stop + `[DONE]`；
  **传输层增量、引擎原子**——横幅如实声明非 token 级）；`tests/test_ai_servers_smoke.py`
  25→**39 条**。
  ⑤ **ml.py 其余六算法纯 Python 真实现**：decision_tree（CART gini、零增益诚实停分——
  **XOR 首刀零增益故根叶 acc=0.5 是标准 CART 行为**，深度闭环改用交错标签：stump 0.75
  vs 深树 1.0）、random_forest（bootstrap+每树特征子空间，**非每节点采样变体**）、
  neural_network（单隐层 tanh+sigmoid 输出，**仅 0/1 二分类**，MSE+SGD，XOR 收敛
  loss<0.01）、knn（平方欧氏、票数平手取最近类）、svm（线性 hinge+L2，标签 0/1→±1）、
  naive_bayes（总体方差/n+var_smoothing）；分类平手一律**先见标签序**；
  `MathaML.create_model` 九类型全部分派，旧「未实现」拒绝锁改为分派正确锁；旧注册表
  ML 域符号 3→**9**（`src/domains/registry.py` 同步，eager 路径实跑验证）；
  新 `tests/test_ml_models_phase4.py` **160 条**三锁（手算对拍/收敛闭环/显式拒绝矩阵+
  管理器九分派+注册契约）。
  ⑥ **examples/ai 重写为真可运行**：旧 README 六个虚构 API 示例块全废，新 4 个 `.matha`
  （neural_network/data_pipeline/genetic_algo/ai_framework）+ data.csv，逐一经真实 CLI
  `python -m src.matha_main run` 跑通；新 `tests/test_examples_ai.py` **5 条**（干净子进程
  exec_api 端到端+手算期望输出+文件漂移锁）；examples/README 与 examples/ai/README 同步重写
  （game/web 虚构块如实标注未重写）；新增示例使 `used_in` 计数漂移，`docs/ast_vm_gap.json/md`
  按断言指示以 `scripts/ast_vm_matrix.py --write` 重生成，ast_vm_gap **11/11** 复绿。
  **如实登记的 Matha 语言边界**（示例与测试均绕开并注释）：Python 对象点访问编译为下标
  （`tensor.shape` 不可用）、Matha 闭包不是 Python 可调用对象（GA 适应度回调显式
  ValueError 拒绝）。
  本轮新增测试 **233 条**（35+17+2+14+160+5），全量门禁 **6056/6056 通过**
  （基线：`python scripts/check.py`，tests 项 5953 过 17m19s + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现
  不计入分母；零失败零跳过）。
  **仍未背书/未修**：LLM 真实 API 的回答正确性（fake 后端锁只证编排与降级契约）；
  SSE 非 token 级流式；六算法变体限制如上（RF 非逐节点采样、MLP 仅二分类、SVM 仅线性）；
  neural_network 示例默认 100 epochs 是演示配置、XOR 未收敛（loss≈0.25，示例内已注释）；
  Matha 闭包跨语言回调不支持；examples 的 game/web 虚构示例未重写（不在本阶段范围）。
- **2026-11 阶段 5 收官（完成度核查清缺口：matha_system 假门面、资源_成长恒零占位）**：
  阶段 4 后全面核查（AI 测试子集 861/861 实跑复绿）发现两类残留，经批准本轮清除——
  ① **`src/matha_system.py` AI/ML/数据门面**（阶段 1 余项登记「未修」在案）：
  `create_convnet`/`create_rnn` 假 dict → 显式 `NotImplementedError`（与 neural_network
  插件同口径）；`create_neural_network` 真接路径坐实必崩（layers/hidden_size kwargs 与
  `NeuralNetwork(config)` 签名不合）→ 改 `ModelConfig` 构造（与插件工厂逐字段对拍）；
  `load_csv` 恒 True → 真委托数据科学域 `Dataset.load_csv`（真读真校验、失败如实抛错、
  成功留置 `self.dataset`，失败不换数据集）；`normalize_data` 透传 → 真逐列 min-max
  返回新矩阵（契约同 `Dataset.normalize`：常量列/空/不齐宽/非数值/bool 显式拒绝，
  seeded 随机阵与已背书实现逐值对拍）；`train_model` 无 fit 假 dict 兜底 → 显式
  `TypeError`（fit 非可调用同拒），真路径委托 fit 返回真实 `ModelResult`；
  **顺带坐实 `_init_ml` 从未被调用**（四个 ML 工厂在已初始化系统上 AttributeError
  死接线）→ 接入 `_init_domains`；四个 ML 工厂与 `create_data_science` 的模块缺席
  假 dict 兜底一律改 `RuntimeError` 显式拒绝。
  新 `tests/test_matha_system_facades.py` **38 条**（真接手算/闭环/插件对拍、
  缺席与误用拒绝矩阵、_init_ml 接线锁）。
  ② **`src/library.py` 资源_成长恒零占位**（本轮核查新发现，原未登记）：
  `_generate_candidate` 对未匹配需求静默生成 `(x) => 0` 且 grow 返回 成功=True
  （探针实测「计算黑洞熵」成功入库恒零函数）→ 删除默认分支，未匹配返回 None
  走既有诚实失败路径（成功=False、不落盘、不注册、解释器零污染）；
  活内建 `资源_成长`（柯里化三应用）与 `资源_加载`（两应用）同步锁。
  新 `tests/test_library_grow.py` **19 条**（六关键词模板公式手算对拍——圆/矩形面积、
  球/圆柱体积、牛顿力、动能；grow→加载→新解释器调用闭环；保护隔离不覆盖；
  未匹配拒绝矩阵；内建接线锁，monkeypatch 库根到 tmp 零仓库副作用）。
  本轮新增测试 **57 条**，全量门禁 **6113/6113 通过**（基线：`python scripts/check.py`，
  tests 项 6010 过 19m23s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **仍未背书/未修**：资源_成长关键词模板为窄路径，近缘需求会误匹配（如「圆环面积」
  匹配圆面积模板产出 πr²）——语义级需求理解不背书，未匹配才诚实失败
  （**已于阶段 6 精确场景化清除**，见下方阶段 6 条目）；
  `matha_system.py` 的 `_init_science`/`_init_visualization` 同样从未被调用
  （create_dataset 等科学/可视化门面 AttributeError 死接线，非 AI 范围，未触及）
  （**已于阶段 6 连同同类共十处全部接入主链**，见下方阶段 6 条目）；
  quantum grover/shor 假实现与 `unified_parser.py` 假编译产物仍在（非 AI，登记同前）
  （**已于阶段 9 真化清除**，见下方阶段 9 条目）。
- **2026-11 阶段 6 收官（模板关键词误匹配清除 + 死接线全量修复）**：
  阶段 5 登记的两项边界经批准本轮清除——
  ① **`src/library.py` 模板精确场景化**：旧关键词子串匹配把「圆环面积/圆柱面积」
  误套圆面积 πr²、「势能/能量」误套动能（阶段 5 登记在案）→ 改六个规范名精确匹配
  （圆/矩形面积、球/圆柱体积、牛顿力、动能，可带「请/帮我/计算/求」前缀与任意空白），
  近缘名与其余需求一律 None → grow 诚实失败（成功=False、不落盘不注册）；
  「牛顿第二定律」这类真别名也不再宽匹配（窄路径精确化，语义理解仍不背书）。
  ② **`src/matha_system.py` 十处死接线**：`_init_package`/`_init_type_checker`/
  `_init_test`/`_init_formatter`/`_init_doc`/`_init_async`/`_init_science`/
  `_init_visualization`/`_init_symbolic`/`_init_security2` 从未被 `_init_domains`
  调用——类属性从未赋值，门面方法 AttributeError（假 dict 回退不可达）；其中
  `install_package`/`run_test`/`generate_docs` 为纯假返回，`hash_password` 回退
  明文密码（安全隐患）。本轮十处 init 全部接入主链（复枚举 0 处未调用），
  门面真委托（install→pm.install 真实结果、resolve→DependencyResolver 真拓扑、
  run_test→测试框架真跑（失败用例 passed=False 带 traceback）、generate_docs→
  scan_module+generate_markdown 真扫描出文、run_async→AsyncManager.run_async 真跑），
  全部假回退改 `RuntimeError` 显式拒绝，假对象误用显式 `TypeError`；
  `_init_science`/`_init_security2`/`_init_package` 失败分支属性全置 None。
  **顺带根治两个被真接线暴露的目标模块崩溃**：`type_checker.check_type` 调
  不存在的 `_infer_type` → `infer_type`；`symbolic._evaluate` 对 parse 产出的
  裸数节点取 `.value` → 兼容裸数与 Symbol 值节点（solve x-2=0 手算 [2.0] 坐实）。
  新 `tests/test_matha_system_wiring.py` **107 条**（十处接线防漂移 + 16 类属性身份
  对拍 + init 失败分支、包/类型/测试/格式化/文档/异步/科学/可视化/符号/安全手算
  对拍与真委托对拍、25 例缺席拒绝矩阵）；`tests/test_library_grow.py` 增
  **16 条**（10 近缘名误匹配清除锁 + 6 前缀/空白容忍锁）。
  本轮新增测试 **123 条**，全量门禁 **6236/6236 通过**（基线：`python scripts/check.py`，
  tests 项 6133 过 18m54s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **仍未背书/未修**：资源_成长仅背书六规范名精确场景，语义级需求理解不背书；
  `security_enhanced.verify_password` 恒真（len(hashed)>0）假验证仍在（探针实测
  错误密码也通过；非门面消费，本轮未触及）（**已于阶段 7 真验证清除**，见下方阶段 7 条目）；
  `symbolic.simplify` 对裸数节点取
  `.value` 的同类崩溃仍在（探针实测 simplify(parse('1+2')) AttributeError；
  非门面消费，本轮未触及）（**已于阶段 7 根治**，见下方阶段 7 条目）；
  quantum grover/shor 假实现与 `unified_parser.py`
  假编译产物仍在（非 AI，登记同前）（**已于阶段 9 真化清除**，见下方阶段 9 条目）。
- **2026-11 阶段 7 收官（两项新登记缺口清除：verify_password 假验证、simplify 崩溃）**：
  阶段 6 登记的两项「未触及」经批准本轮清除——
  ① **`src/security_enhanced.py` 密码验证**：`verify_password` 恒真
  （len(hashed)>0，探针实测错误密码通过），且 `hash_password` 随机盐不嵌入输出
  （盐被丢弃，真验证无从重算）→ 哈希格式改 `hex(salt)$hex(pbkdf2_dk)`（盐嵌入），
  `verify_password` 重算 PBKDF2-HMAC-SHA256（100000 轮）+ `hmac.compare_digest`
  恒定时间比较；格式非法（无分隔/非 hex/长度不符/多段）一律 False 不裸抛，
  口径同 `src/auth/password.py` 既有真实现。哈希格式属有意行为变更：旧裸摘要
  格式本就无法验证（盐已丢弃），阶段 6 的 64 位裸摘要锁已同步升级为嵌盐格式锁。
  ② **`src/symbolic.py` simplify 崩溃**：数字折叠与 `_is_zero` 对 parse 产出的
  裸数节点取 `.value`（探针实测 simplify(parse('1+2')) AttributeError）→
  新增 `_number_value` 兼容裸数与 Symbol 值节点，两处取值统一走它；
  只修崩溃不扩简化规则（仍仅 '+' 折叠与消零）。
  新 `tests/test_verify_password_simplify.py` **29 条**（摘要与独立 hashlib
  重算逐值对拍、hash→verify 闭环（正确/错误/空密码/跨实例/双盐）、篡改盐/摘要
  拒绝、9 例非法格式矩阵不裸抛、内建 `哈希密码` 注册接线与 matha_system 门面闭环；
  simplify 折叠/消零手算、Symbol 值节点兼容、非 '+' 透传不过度简化、幂等再入）。
  本轮新增测试 **29 条**，全量门禁 **6265/6265 通过**（基线：`python scripts/check.py`，
  tests 项 6162 过 17m26s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **仍未背书/未修**：simplify 仅 '+' 数字折叠与消零两条规则（其余运算不简化，
  规则覆盖不背书）；quantum grover/shor 假实现与 `unified_parser.py`
  假编译产物仍在（非 AI，登记同前）（**已于阶段 9 真化清除**，见下方阶段 9 条目）。
- **2026-11 阶段 8a 收官（自然语言编译器前置：Matha 自举能力真实升级）**：
  阶段 8（AI 自然语言编译器/解释器 + 混合执行引擎，全部以 Matha 自身构建）的
  第一子阶段——先把自举链的三项能力缺口真实补齐：
  ① **stdlib ord/chr Unicode 占位清除**：`matha/stdlib.matha` 的 ord_matha/chr_matha
  原为 ASCII 查表占位（探针实测 ord_matha("中") 静默返回 -1）→ 删除查表，委托
  宿主/VM/原生三端共有的真实 ord/chr 原语（110 万码点无法纯 Matha 查表，
  与 _dict_keys 等 VM 原语同例）；len 本为三端真实 Unicode 长度原语，注释明示
  不可 Matha 重定义（函数体内 len(s) 自引同名定义造成无限递归）。
  ② **纯 Matha list_map/list_fold**：let rec 累加器实现，不委托宿主 映射 内建
  （自举链可用），入 内建 导出表；空表边界 []/init 原样返回。
  ③ **两条自举解释器链 match 求值补齐**：自举 parser 早已完整解析 match
  （做Match/做构造子模式），但 interp.matha 与 interp_matha.matha 的求值 dispatch
  均落「未知表达式类型」；mb.interpret 的静默 Python 回退
  （src/matha_bootstrap.py:126-129）曾掩盖此缺口。本轮两链同补
  求值match/求值match分支/匹配模式/匹配构造子/匹配字段列表：守卫先于模式在
  外层 env 求值（模式绑定对守卫不可见）、通配符 _ 延迟兜底、变量绑定经新 env
  不泄漏、构造子列表 [名, 字段...] 与字典 {名: 字段列表} 两形态、无匹配显式抛错。
  字典形态以 安全索引（三端内建）做缺键拒绝——自举 parser 无 in 二元运算符层
  （仅 let 终止符），用 in 会破坏 test_m7 自编译（期望 then）。
  新 `tests/test_bootstrap_upgrade_phase8a.py` **46 条**三锁（手算对拍/闭环/显式拒绝，
  mb/fresh/M3V VM 三链）：ord/chr 中文与 emoji 往返、多字符/越界拒绝、
  map/fold 对拍与组合闭环（平方和 14）及左折叠顺序锁（123）、match 源码级 8 例
  （字面量/兜底/绑定/守卫/假守卫跳过/Unicode 串/浮点/布尔）×两链、构造子 AST 级
  7 例×两链、无匹配拒绝与绑定不泄漏×两链、VM 字面量/绑定/列表与字典构造子/拒绝。
  本轮新增测试 **46 条**，全量门禁 **6311/6311 通过**（基线：`python scripts/check.py`，
  tests 项 6208 过 17m55s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **预先存在缺口（本轮探针取证登记；已于缺口修复轮全部清除，见下方条目）**：
  ① interp_matha 顶层 let 绑定 env 丢失——mb 链 `let n = 5` 换行 `n + 1` 抛
  「未定义变量 'n'」（执行声明 else 分支丢弃 求值let绑定 返回的新 env）；
  fresh 链（interp.matha）同源码正常得 6。
  ② 两自举解释器均不支持列表/字典字面量求值（`[1,2,3]` / `{"a":1}` 均抛
  「未知表达式类型: 列表/字典」）——match 构造子源码级用例因此走 AST 级预绑定 env。
  ③ mb 链 parse_JSON 独立调用抛「不可调用的值: <?>」（与 match 无关，探针复现）。
  ④ 自举构造子匹配不支持元组形态 scrutinee（宿主支持；type_of 三端均无
  "Tuple" 判别）——代码注释登记。
  ⑤ 守卫真值口径：自举 if 约定（非 0.0 且非 假）vs 宿主 Python truthiness——
  代码注释登记。
  **仍未背书/未修**：无（8b/8c/8d 均已于下方条目背书；
  上述五缺口已于缺口修复轮清除，见下方条目）。
- **2026-11 缺口修复轮收官（阶段 8a 登记五缺口清除，8b 前置）**：
  按「先修复已登记缺口，再进行 8b」批准口径，上条五项预先存在缺口逐一根治：
  ① **顶层 let env 丢失**：interp_matha.matha 增 绑定求值let（返回 (值, 新环境)，
  递归路径占位→求值→更新绑定值），执行语句/执行声明 的 let绑定 分支改走它
  （原 else 丢弃新 env）；顶层多 let 链与 let-in 两形态均对拍宿主。
  ② **列表/字典字面量求值**：两链 求值 dispatch 补 列表/元组/字典 三类；
  求值列表 纯 Matha 累加器保序构建，求值字典 逐对求值后经 stdlib dict_from_pairs
  （折叠 _dict_put/_empty_dict 原语）产真实 dict（非键值对列表占位）；
  元组经新增 _to_tuple 原语构造。宿主 BUILTINS 补齐 _dict_keys/_dict_values/
  _dict_has/_dict_put/_dict_remove（原仅 VM 端有）与 _to_tuple；宿主/VM type_of
  增 "Tuple" 判别。
  ③ **mb 内建元组分发**：注册内建 绑 ("__builtin__", 名) 元组而 应用函数/
  应用多参数函数 只认 Dict 形态 → 补元组形态分支；ord/str/strip/int/parse_JSON
  独立调用真实可用。
  ④ **元组构造子**：两链 匹配构造子 的 scrutinee 与字典参数位均接受 List/Tuple
  （对齐宿主 isinstance(value, (tuple, list))）。
  ⑤ **守卫真值**：两链新增 真值 辅助（null/假/0/""/空容器皆假），守卫单独走它
  对齐宿主 Python truthiness（自举 if 约定不变，只改 match 守卫口径）。
  **同源缺陷一并修复（验证中发现）**：fresh 链 func 定义参数为字符串而 应用函数
  只认 Variable.名 → 用户 func 全崩，改双形态口径（fact(5)=120 两链坐实）；
  mb 链闭包统一为列表形态（与 fresh 链对齐，柯里化 f(3)(4)=7 两链坐实）；
  两链 注册内建 显式绑定 null/None/Null（宿主 parser 以 null 为关键字，
  自举 parser 解析为变量，守卫真值/缺省判定依赖其可求值）。
  新 `tests/test_bootstrap_gapfix_phase8pre.py` **86 条**三锁（手算对拍/闭环/
  显式拒绝，mb/fresh/M3V VM 三链）：let 4 例×三链+未定义拒绝、字面量 6 例×三链
  +真实 dict 判别+VM 构造、内建分发 6 例+非法 JSON/不可调用拒绝、元组构造子
  3 例×三链+type_of Tuple/_to_tuple 拒绝矩阵、守卫 6 例×三链+VM 空容器守卫、
  func 4 例×两链+func×match 端到端闭环（unwrap(("Some",41))=42）。
  本轮新增测试 **86 条**，全量门禁 **6397/6397 通过**（基线：`python scripts/check.py`，
  tests 项 6294 过 20m22s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **剩余边界（如实登记，未修）**：两自举链无下标表达式求值（用户源码 `xs[0]`
  抛「未知表达式类型: 下标」；解释器内部经宿主/VM 层下标不受影响）；内建部分应用
  （get/slice 柯里化二次调用）两链均未支持（本轮只修单参直调分发）；自举 parser
  语义 `[]`=空输出、`{}`=集合构造（空字典走 _empty_dict 原语）；stdlib parse_JSON
  紧凑口径（冒号后不跳空白）；原生端无元组类型（自举解释器不以原生为目标，
  native 对拍仅黄金用例口径）。
  **仍未背书/未修**：上述边界（8b/8c/8d 均已于下方条目背书）。
- **2026-11 阶段 8b 收官（Matha 写的 NL 词法器+句法器，中文控制子集）**：
  阶段 8 第二子阶段——自然语言编译器的词法/句法两层全部以 Matha 自身构建，
  宿主仅增一行模块名映射（`src/interp.py` `_CN2FILE`：自然语言句法器→nl_parser.matha）：
  ① **NL 词法器**（`matha/nl_lexer.matha`，模块 自然语言词法器）：中文数字转阿拉伯数字
  以 total/section/num 三累加器 `let rec` 实现个/十/百/千/万 组合（十五→15、二百→200、
  三十五→35、一万→10000，十 前省略 digit 按 1）；NL词法分析 按空白分词 + 词类标注
  （动词/介词/助词/量词/名词/数词），量词名词粘连（个苹果）拆成两 token，
  未知词/空句显式 `错误` 拒绝。
  ② **NL 句法器**（`matha/nl_parser.matha`，模块 自然语言句法器）：NL句法分析 把 token
  序列经 语法器 构造子（做BinaryOp/做IntLit）产语义框架（Matha 表达式 AST Dict）；
  控制子集＝单一二元算术（加/减/乘/除 及 加上/减去/乘以/除以）/数量短语/纯数词，
  把字句与命令前导（计算/算/求/把）跳过；NL程序 包成 程序[输出(表达式)] 供执行。
  连续数词/缺数词/多运算符链/未知词类一律显式拒绝。
  ③ **三锁**（`tests/test_nl_three_lock.py`，宿主加载 ↔ M3V VM 两路）：对拍（同一句子
  token/语义框架逐值一致 vm=host）、闭环（句子→词法→句法→自举解释器 `求值`→手算值，
  两路均等：3+5=8、5-3=2、3*4=12、6/2=3.0、三十个苹果=30、15+20=35）、显式拒绝
  （两路同抛 MathaRuntimeError 同文本，永不静默回退）。
  新增测试 **75 条**（test_nl_lexer 8 + test_nl_parser 17 + test_nl_three_lock 50），
  全量门禁 **6472/6472 通过**（基线：`python scripts/check.py`，tests 项 6369 过 18m44s
  + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，
  native 1 例已知未实现不计入分母；零失败零跳过）。
  **控制子集边界（如实登记，设计内拒绝）**：仅单一二元运算（多运算符链拒绝，无优先级
  解析）；中文数字仅 个/十/百/千/万 组合（无亿级/零位复杂数字）；量词仅 个/次、名词仅
  苹果/结果/数；词法按空白切分（无连续中文分词歧义消解）。这些边界外句子均显式 `错误` 拒绝。
  **仍未背书/未修**：无（8c/8d 均已于下方条目背书）。
- **2026-11 阶段 8c 收官（语义转换+执行引擎纯 Matha 化，混合引擎零冲突集成）**：
  阶段 8 第三子阶段——8b 产的语义框架（Matha 表达式 AST Dict）接通自举执行链并
  以独立命名内建暴露，既有 混合编译/混合诊断/混合执行/转译语言 接口**一字未动**：
  ① **NL 执行引擎**（`matha/nl_engine.matha`，模块 自然语言执行器，新增 1 个 .matha
  语料）：NL执行(句子) ＝ NL编译（语义转换，句子→框架）→ 注册内建(空环境) → 自举
  求值（执行引擎），纯 Matha 闭环；歧义/超控制子集句子经 NL编译 显式 `错误` 拒绝，
  永不静默回退。宿主仅增一行模块映射（`src/interp.py` `_CN2FILE`：自然语言执行器
  →nl_engine.matha）。
  ② **独立命名内建**（零冲突集成）：宿主 `自然语言执行(句子)`（`_b_nl_run`，懒加载
  委托，加载失败显式 RuntimeError）；VM 同名 per-VM 内建（`_make_nl_run`，
  `invoke_value` 回调保帧栈整洁，链未编译显式拒绝）。内建名（自然语言执行）≠
  Matha 函数名（NL执行），VM 单全局表无遮蔽（对齐既有 匹配/_bmatch 教训）；
  全仓 grep 证两名零既有占用。
  ③ **三锁 + 零冲突锁**（`tests/test_nl_engine_phase8c.py` 77 条，宿主加载 ↔
  M3V VM 两路 × 直接/内建四链）：对拍 16（vm=host 逐值一致）、闭环 19（含
  Matha 源码层 输出(自然语言执行(...)) 两路产出结果值；内建懒加载自装模块链）、
  显式拒绝 22（四链同抛 MathaRuntimeError 同文本 + VM 未编译 RuntimeError）、
  零冲突 4（NL 调用后 混合编译/混合诊断/转译语言 行为不变；双表无遮蔽；
  引擎调用零散输出；无状态无环境泄漏）。
  本轮新增测试 **77 条**，全量门禁 **6549/6549 通过**（基线：`python scripts/check.py`，
  tests 项 6446 过 20m42s + kernel_purity 14 + ast_vm_gap 11 + golden 39
  + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **边界（如实登记）**：控制子集仍同 8b 口径（单一二元运算/个十百千万/量词名词白名单，
  边界外显式拒绝）；引擎当前执行表达式框架求值（NL程序 包装的输出语句求值未接线，
  8b 的 NL程序 仅供下游消费）；宿主顶层裸 FuncApp 语句不产输出为既有语义
  （源码层用 输出(...) 形态锁定）。
  **仍未背书/未修**：阶段 8d（英语子集+用户词典+LLM 可选路径）已于下方条目收官背书。
- **2026-11 阶段 8d 收官（英语控制子集 + 用户词典 + LLM 可选路径边界）**：
  阶段 8 第四子阶段——NL 链扩展英语控制子集并接通用户词典显式映射，LLM 路径
  维持阶段 4 契约一字未改：
  ① **英语词法器**（`matha/nl_lexer_en.matha`，模块 自然语言英语词法器）：前导
  compute/calculate/what/is（跳过）、运算 plus|add→+ minus|subtract→- times→*
  divided-by→/、数词三形态（数字串 / 单词 zero..ninety+hundred/thousand / 连字复合
  twenty-one、three-thousand-five-hundred，复合序列经状态机校验，twenty-hundred 等
  不合法序列显式拒绝）；token 形态与中文词法器一致（["词",文本,词类] /
  ["数字",str,"数词"]），输入小写化；未知词显式 `错误` 拒绝。
  ② **英语句法器**（`matha/nl_parser_en.matha`，模块 自然语言英语句法器）：镜像中文
  句法器，跳过英语前导后仅接受 数词 [运算 数词]，经 语法器 构造子产语义框架；
  连续数词/缺数词/多运算符链显式拒绝。
  ③ **用户词典**（`matha/nl_dict.matha`，模块 用户词典）：显式映射（键=分词后单词
  英小写化/中文原样，值=控制子集词），替换发生在分词后、分类前；**单层**不递归
  （替换值不再查典，值仍未知则词法器拒绝，永不静默回退）；默认空词典＝行为与
  8b/8c 完全一致；两词法器增 带词典 入口（NL词法分析带词典 / NL英语词法分析带词典），
  原入口默认走空词典。
  ④ **英语执行链**（`matha/nl_engine_en.matha`，模块 自然语言英语执行器）：复用 8c
  执行链（NL英语编译 → 注册内建(空环境) → 自举 求值）纯 Matha 闭环；独立命名内建
  自然语言执行英语（宿主 `_b_nl_run_en` 懒加载委托、加载失败显式 RuntimeError；VM
  `_make_nl_run_en`，未编译显式拒绝）；内建名 ≠ Matha 函数名（NL英语执行），VM 单
  全局表无遮蔽；全仓 grep 证两名零既有占用。
  ⑤ **LLM 边界锁**：确定性 NL 链（中文/英语）零 LLM 依赖——LLMIntentParser.parse
  monkeypatch 必炸后成功/拒绝路径均不触达；LLM 可选路径维持阶段 4 契约
  （MATHA_REPL_LLM 默认关 + 诚实降级），本阶段一字未改。
  ⑥ **三锁 + 词典锁 + 零冲突锁**（`tests/test_nl_phase8d.py` 95 条，宿主加载 ↔ M3V
  VM 两路 × 直接/内建四链）：对拍 16（引擎/内建 vm=host 逐值一致）、闭环 37（手算
  8 句 × 4 路、token 形态 3、源码层 输出(自然语言执行英语(...)) 两路）、显式拒绝 28
  （四链同抛 MathaRuntimeError 同文本，含 "twenty five" 空格复合边界 + VM 未编译）、
  词典锁 7（默认空回归 / 中英替换 / 框架对齐 / 单层不递归双语言）、LLM 边界 1、
  零冲突 6（中英双内建同宿主/同 VM 共存、双表无遮蔽、混合接口不变、零散输出、无状态）。
  **夹具连带修复**：nl_lexer.matha 增 用户词典 依赖后，8b/8c 测试的 VM 编译列表同步
  补 `matha/nl_dict.matha`（否则 VM 路 `MathaUndefinedNameError '默认词典'`，首轮门禁
  tests 项 86 失败已修复并复跑确认 127/127）。
  本轮新增测试 **95 条**，全量门禁 **6644/6644 通过**（基线：`python scripts/check.py`，
  tests 项 6541 过 47m53s + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1
  + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **边界（如实登记）**：英语控制子集＝单一二元运算 + zero..ninety/hundred/thousand
  及连字复合（数字串亦收）；空格分隔复合数词（"twenty five"）显式拒绝（连字复合才
  合法，不做静默猜测）；复合序列语法受限（twenty-hundred、five-twenty 拒绝）；词典
  键为分词后单词、值为控制子集词、单层不递归；两链无自动语言检测（中文/英语独立
  入口、词典各自注入）；引擎执行表达式框架（NL英语程序 包装的输出语句求值未接线，
  同 8c 口径）。
  **仍未背书/未修**：阶段 8 计划内四子阶段（8a/8b/8c/8d）均已收官背书；后续无已批准阶段。
- **2026-11 阶段 9 收官（假实现清算：quantum / quantum_compute / unified_parser / matha_system 量子门面）**：
  阶段 3-7 反复登记的「quantum grover/shor 假实现与 unified_parser.py 假编译产物仍在」经批准本轮全部清除：
  ① **`src/domains/quantum.py` 真化**：apply_gate/measure/entanglement/grover_search/shor_factor/
  run_algorithm 从「恒 True/恒 0/恒 [3,5]/只记账」真化为纯 Python 状态向量模拟器（上限 20 比特，
  2^n 振幅）：H/X/Y/Z/S/T 单比特矩阵 + CNOT/CZ/SWAP 两比特真置换作用于态向量、测量按 |振幅|²
  采样并坍缩归一化、纠缠 = H+CNOT 真制备 Bell 对、bell/ghz 真制备（GHZ 任意 2..20 比特）、
  qft 委托 quantum_compute（算法比特数与机器比特数不一致显式拒绝）、Grover 真迭代（均匀叠加 →
  相位 oracle → 扩散 D=2|s><s|−I，迭代 floor(π/(4θ))，d=4 精确命中，d<2/标记越界显式拒绝）、
  Shor 经典部分真实现（偶数/试除/乘法阶 gcd 提取，素数与 <4 显式拒绝）；RX/RY/RZ/TOFFOLI 与
  未知门从假占位改显式拒绝；注册层改柯里化 lambda 链（旧平面多参签名对 Matha f(a,b)→f(a)(b)
  编译约定必碎，9 符号面不变）；Matha 四参链中单比特门占位目标只验界不参与运算。
  ② **`src/domains/quantum_compute.py` 补真**：gate_decompose 从无视输入的固定 7 门假产物真化为
  矩阵级数值验证的 Toffoli→Clifford+T 15 门精确分解（1×H + 7×T/Tdg + 6×CNOT，乘积逐位等于
  Toffoli 真值矩阵；恰好 6 CNOT，其余计数显式拒绝）；grover_iterate 补 oracle 输出长度/零向量/
  负迭代/空态校验 + 迭代后归一化；shor_period_finding 周期起点 2→1（ord_a(N)=1 不再漏判
  None）；`registry.py` QuantumComputing 模板清除 3 个幻影符号（quantum_fourier/grover_iter/
  quantum_teleport 模块中根本不存在），functions 面与模块 15 符号对齐。
  ③ **`src/unified_parser.py` 假编译产物清除**：matha_compile 从「# Compiled N declarations」
  假摘要真化为 parse + mbc compile_program 真编译（摘要携带真实 声明数/函数数/主代码 ops 数，
  测试以独立复算对拍）；matha_to_llvm 与 MathaLLVMGenerator.generate 从假 IR 字符串改
  NotImplementedError 显式拒绝（`src/compiler/matha_cc.py` 的同名独立管线不在本轮范围，未动）。
  ④ **`src/matha_system.py` 量子门面 6 处假值清除**（阶段 4 登记「quantum grover/shor 假实现」
  的另一半）：apply_quantum_gate 恒 True / quantum_measure 恒 0 / grover_search 恒 0 /
  shor_factor 恒 [1,n] / create_quantum_circuit·run_quantum_algorithm 假 dict → 全部真委托
  domains.quantum（创建的机器登记跟踪，最近创建者优先），无机器/未初始化 RuntimeError 显式
  拒绝（不再假 dict 兜底），grover_search 标记项必须显式给出（缺省 None 拒绝，不再默认假 0）。
  新 `tests/test_quantum_fake_purge_phase9.py` **74 条**三锁：
  手算对拍（Bell 振幅精确、X/H/Z/S/T 相位、CNOT/SWAP/CZ 真置换、GHZ3、QFT δ↔均匀、Grover d=4
  逐标记精确 + 填充位恒零、Shor 九数因子表、乘法阶表、Toffoli 15 门矩阵乘积逐位验证、
  circuit_depth 约定）；闭环（种子化 Bell 20 次关联 + 坍缩归一 + 复测不变、Grover d=8 命中率
  >0.85（理论 sin²(5θ)≈0.945）、N=2 理论恰 50% 对拍、比特生长振幅连续性、matha_compile 独立
  复算对拍、matha_run 真值、Matha 干净子进程 exec_api 端到端真算 + TOFFOLI/素数 Shor 真拒绝）；
  显式拒绝（RX/RY/RZ/TOFFOLI/未知门/缺 target/同索引两比特门/越界与非法占位/连续索引破坏/
  20 比特上限/Grover 与 Shor 与 GHZ 与 QFT 边界/grover·shor 独立入口重定向/bool 索引/oracle
  长度不符/零向量/负迭代/空态/非 6 CNOT/LLVM 假产物/门面无机器与未初始化与缺 marked）；
  符号面（quantum 9 / quantum_compute 15：manifest↔symtab↔registry↔注册字典四方一致 +
  幻影符号防回潮 + 柯里化逐级 arity 对拍 + 零参 f() 传 0 约定）。
  `tests/test_unified_layers.py` 同步升级 3 条（matha_compile 真计数精确断言、LLVM 两入口改
  NotImplementedError）。本轮新增测试 **74 条**，全量门禁 **6718/6718 通过**（基线：
  `python scripts/check.py`，tests 项 6615 过 39m51s + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母；零失败零跳过）。
  **边界（如实登记）**：状态向量模拟是经典模拟器，不背书量子加速；20 比特上限（2^20 振幅）；
  Grover/Shor 为教科书式实现（Shor 直接经典乘法阶，无量子周期寻找）；仅 d=4 的 Grover 精确
  （d=2 理论恰 50%，d=8 理论 sin²(5θ)≈0.945，按种子化统计对拍不按精确值）；`matha_cc.py` 同名
  matha_to_llvm/MathaLLVMGenerator 独立管线未动（其真伪属另一轨道）；顶层旧模块 `src/quantum.py`
  不在本轮范围。
  **仍未背书/未修**：阶段 3-7 登记的 quantum grover/shor 假实现与 unified_parser 假编译产物
  已全部清除；本阶段无新增未修项。
- **2026-11 阶段 10 收官（matha_cc 清算 + 死代码删除）**：经批准本轮范围 = `src/compiler/matha_cc.py`
  委托化/诚实化 + 调用方逐一同步 + 删除零消费死代码 `src/quantum.py`：
  ① **`matha_cc.py` 977→235 行整体委托化**（unified_parser 先例的延伸）：MathaLexer→`src.lexer.Lexer`
  （主 tokenize 是生成器，包装成 list 保旧契约）、MathaParser→`src.parser.Parser`（token 注入按主实现
  真实字段 `tokens/pos`——历史写法误设 `_tokens/_pos`，注入静默不生效产空 Program，该 bug 在
  unified_parser.MathaParser 同在、两处同修）、MathaFrontend→`src.parser.parse`、MathaCompiler→真
  matha_compile/matha_run、matha2c→`bootstrap_compile(target="c")`、matha_bootstrap_compile→同名真实现。
  ② **假产物显式拒绝**：matha_to_llvm/MathaLLVMGenerator 从「三地址码贴 LLVM 模板产无效 IR」改
  NotImplementedError（llvm_hybrid 与 bootstrap target="llvm" 同步委托；compile_and_benchmark 的
  llvm_ms 恒空假基准改 `"skipped"` 如实跳过；benchmark_compiler/run_full_test/matha_cc_cli cmd_info
  相应诚实化）；**MathaSelfCompiler.compile** 从 hasattr 静默返回空字节串改真 MBC1
  （parse+compile_program+serialize_mbc）；`src/mbc/serial.py` 补 serialize_mbc/deserialize_mbc
  内存孪生（write_mbc/read_mbc 重构共用）。
  ③ **`matha_system.py` 同名 `_init_compiler` 遮蔽修复**（第二定义 compiler_backend 版覆盖第一定义
  matha_cc 接线版 → matha_compile/compiler 从未绑定，整段接线全死，Phase 5 `_init_ml` 同类；第二定义
  更名 `_init_compiler_backends`）：matha_compile/matha_to_llvm/compiler 自此真绑定；两处
  `_eval_with_compiler` 假值改真 matha_run（MathaEngine 版保留 None 回退）。
  ④ **CLI path-as-source 修复**：matha_cc_cli（compile/run/llvm/optimize）与 matha_main
  （compile/matha2c/llvm/optimize）八处此前把文件路径字符串当源码送编译——旧 lexer 下路径恰好解析
  失败算「诚实报错」，主 lexer 委托后路径「可解析」产假成功（实测 2 声明文件报 8 声明假摘要）；全部改
  先读文件再编译；matha_main `_cmd_build` 从假产物改真 MBC1 工件（write_mbc，实测 149 字节可 read_mbc
  读回）；`_cmd_debug` 的 `len(MIRProgram)` 崩溃改函数/指令计数。
  ⑤ **死代码删除**：`src/quantum.py`（338 行，全仓零消费、2Q 门物理错误）git rm；`src/__init__.py`
  移除指向已删 MathaIR 的幻影懒加载导出。
  新 `tests/test_matha_cc_phase10.py` **31 条**三锁：
  parity（matha_cc.MathaLexer/MathaParser 与主实现同源 token 逐项/AST 形状对拍、token 注入真解析
  回归锁、matha_compile 摘要与 unified_parser 独立复算精确一致、MathaSelfCompiler 真字节码
  deserialize_mbc 全等对拍（arity/nlocals/params/code/main_code/constants）、serialize_mbc 与
  write_mbc 文件字节等值）；闭环（matha_run 真执行 [3]/柯里化 [30]/func 递归 [120]、MathaCompiler
  run+stats、CLI 子进程 compile/run/test 4 通过 0 失败/build MBC1 工件可读回、MathaSystem 全初始化
  接线锁（matha_compile 精确摘要 + compiler_class + "compile" 内建 + eval 7——同名遮蔽回归锁）、
  MathaSystem 定向 _init_compiler、MathaEngine eval 42、mir_converter 双入口、bootstrap c/python
  双 target 非平凡）；显式拒绝（matha_to_llvm/generate/llvm_hybrid/bootstrap-llvm 四入口
  NotImplementedError、CLI llvm rc1 诚实失败、破损源 ParseError、MathaBackend 无效 IR
  ToolchainUnavailable、src/quantum.py 缺席 + import 拒绝、matha_cc 17 个旧 IR/AST 类名清除、
  src.MathaIR AttributeError、缺文件 rc1）。
  既有锁同步：`test_unified_layers.py` matha_parser compat 加 AST 形状断言（防 `_tokens/_pos` 回潮）、
  `test_mcp_server_facade.py` 编译摘要/全角标点/EOF 枚举比较 3 条按新契约升级。
  **登记未修（本轮发现，超出范围，另立轨道）**：`src/bootstrap.py`
  MathaBytecodeCompiler `_generate_bytecode` 对 target=matha/binary/trinary/decimal 抛 TypeError
  （'MIRConstInstr' 不可解释为整数，字节码链断裂）；MathaEngine.vm_run 编译路径暂眠回退 None
  属注释性假值。ffi_sdk 一项（本条目原写作 `src/mcp/ffi_sdk.py:221` 引用不存在的
  `src.compiler.mir_codegen.MathaLLVMGenerator`，路径与模块名笔误——实为 `src/plugins/ffi_sdk.py:221`
  引用不存在的 `src.mir_codegen.MathaLLVMGenerator`）已于同日补充修复，见下方条目。
  全量门禁 **6749/6749 通过**（基线：`python scripts/check.py`，tests 项 6646 过 41m21s +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知
  未实现不计入分母；零失败零跳过。首轮 6748/6749 唯一失败为 `test_ai_servers_smoke.py` 鉴权 401
  参数化一例，单跑与整文件复跑 39/39 均过，判定为长跑偶发连接时序，与本轮改动面无关）。
- **2026-11 阶段 10 补充（ffi_sdk compile 分派诚实化）**：修复阶段 10 登记的
  `src/plugins/ffi_sdk.py:221` 死分支，顺带清算该文件 compile 分派面：
  ① **llvm 死分支**（import 不存在的 `src.mir_codegen.MathaLLVMGenerator` → 恒 ImportError）→
  NotImplementedError 显式拒绝；② **python/c 改委托真生成器**：从 src/codegen 原型后端
  （PythonGenerator 等对常量指令 IndexError——MIRConstInstr 的 instr_type 误标 ADD 且 operands
  为空）改为 `src.mir_codegen.MIRToPythonGenerator/MIRToCGenerator`（func 形态真编译，
  生成 Python 代码 exec 可跑：加一(3)=4；test_mir_pipeline 既有锁覆盖该生成器）；③
  **rust/cpp/go/java/js 显式拒绝**（rust 后端输出源码无关固定模板——两份不同源码逐字节相同，
  与阶段 9/10 清算的假产物同类）；④ **compile_and_execute 假成功 dict 清除**：非 VM 目标
  `{"compiled": True}` 假回显改为返回编译工件本身（mir/optimized_mir 仍走 MIR VM）；⑤
  **matha_eval 双执行修复**（同一表达式原执行两次）+ **execute 共享单例累积 outputs 修复**
  （Interpreter.run 返回实例级累积列表，此前第二次 execute 返回全部历史输出、matha_eval
  取 [0] 拿陈旧值——现按调用前基线取增量）；⑥ 模块 docstring 诚实化（不再声称 Rust FFI/
  Go CGO/NAPI/JNI/WASM 绑定；libmatha 本仓不产出，`MathaLibrary.load` 缺失如实 False）。
  新 `tests/test_ffi_sdk_honest.py` **21 条**三锁：真实面（execute/matha_eval 真值、单次执行
  计数锁、ast/mir/optimized_mir 真产物类型、python 目标生成代码 exec 对拍 加一(3)=4、
  c 目标函数签名存在、matha_run_file 真值）；闭环（cae mir 纯输出源返回空 = MIR 原型层不表示
  顶层 Output 的登记边界、cae python/ast 返回编译工件本身、run_pipeline 逐目标诚实报告）；
  显式拒绝（llvm+五原型目标 NotImplementedError、未知目标 ValueError、坏源 ParseError、
  库缺失 load() False、源码面不再路由 src/codegen 七后端）。
  **登记未修（本轮发现，另立轨道）**：`src/codegen/` 七个语言后端
  （python/rust/c/cpp/go/java/js_backend）零消费者原型（rust 固定模板/其余常量 IndexError）；
  `src/mir.py` MIRGenerator 对顶层 Binding 丢名（MIRStoreInstr result='' → C 生成器发射非法 C
  ` = 2.0;`、Python 生成器对纯绑定源输出空 main）；`src/mir.py` 不表示顶层 Output
  （compile_and_execute 纯输出源返回空）；`src/plugins/legacy_mir_vm.py` func 调用形态
  ValueError 崩溃（float('t2')）；MathaBytecodeCompiler 字节码链与 vm_run 仍登记未修。
  全量门禁 **6770/6770 通过**（基线：`python scripts/check.py`，tests 项 6667 过 42m43s +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知
  未实现不计入分母；零失败零跳过）。
- **2026-11 阶段 11 收官（全面清算：崩溃/未诚实化/假成功/未修理项 #14-#21）**：用户指令
  「门禁跑完后，检测整个 matha 所有的崩溃/未诚实化/假成功/未修理项进行修复」，按 P0→P3 清算：
  ① **[P0] `src/symbolic.py` 数学错误修复**：diff() 补 '-' 规则 + '/' 商法则 (u'v−uv')/v² +
  '**' 链式因子（旧对 sin/exp/log 恒等返回）；integrate() 幂规则补 ÷(n+1)（旧 ∫x² 产 x³）；
  除零诚实（1/0 求值抛 ZeroDivisionError「符号求值除数为零」，`symbolic_calc` value=None
  不冒充数值）。② **[P0] `src/interp.py` enumerate/zip 真化**：柯里化两参内建（与 MBC-VM
  enumerate_val/zip_val 同语义；不可迭代/非整数下标显式拒绝），删除死 _enum_c/_enumerate_curried/
  _zip_curried。③ **[P0] `src/mir.py` 顶层 Binding 丢名 + Output 不表示**：_compile_binding
  真名入 scope/MIRStoreInstr.target（旧 result='' → C 生成器发射非法 ` = 2.0;`）；
  _compile_mech_unit 处理 GenStmt/CodeBlock 体 + Output 真发射（旧顶层 Output 整段丢弃）。
  ④ **[P0] `src/plugins/legacy_mir_vm.py` 四 bug 真化**：指令按类分派（旧 payload 形态碰撞——
  Return.value 被误当 const 值）、函数注册 _state.globals、params 按名绑定（旧按索引错位）、
  frame.pc 跳转真读写；跨语言验证 outputs 恒空 → `[]==[]` 恒假通过的假阳性清除（空输出如实报
  不可验证）。⑤ **[P0] `src/bootstrap.py` MathaBytecodeCompiler + `src/matha_engine.py`**：
  binary/trinary/decimal 旧产文本冒充字节码清算 → 真 MBC1 委托；vm_run/eval_vm 暂眠回退 None
  显式化。⑥ **[P1] domains 假值真化**：concurrent（任务静默丢弃→真执行）、security（明文当密文
  +verify 恒 True→真 HMAC-SHA256 校验；AES 非 stdlib 显式拒绝）、blockchain（区块校验真 hash
  重算）、robotics（传感器恒 0→无硬件显式拒绝；plan_path 真直线插值手算对拍；control_arm 真写
  关节+越界/数量不符拒绝）、hardware（_wait 真等待：psutil/ctypes 双路）、web_framework
  （WebSocket 假连接→RFC6455 未实现显式拒绝）、matha_system 门面九类假返回清算（并发/web/
  database 门面未初始化或无连接时显式拒绝 + 真对象/真执行）。⑦ **[P1] `src/database_engine.py`
  真 sqlite3 重写**：QueryExecutor.execute 真执行 SQL（cursor.description 列名 + dict 行、受影响
  行数、lastrowid、CREATE TABLE 自动登记、事务内抑制隐式 commit）、TransactionManager 真
  commit/rollback（旧空转）、create_table 真 DDL、insert 参数化、select 真查询；matha_system
  双 `_init_database` 遮蔽同名（database_class 实为 src.database_engine.Database 路径型 API）据实
  接线。⑧ **[P2] 多语言链诚实化**：multi_lang_frontend 删除坏 _TS_*Adapter 层（检查后端从不发射
  的节点类型），真前端无条件注册；Go 前端 `:?=`/无分号 return 解析修复；transpiler 裸常量
  pi/e/tau + 双 fallback 显式拒绝（旧产 'None  # 未转译'）；hybrid_compiler C/Rust/Go 空壳
  NotImplementedError + from_language 反向假转译 ValueError；multi_lang_codegen Rust 假测试架
  （伪造 assert!/预期值）删除；unified_multilang 幻影 MultiLangVerifierV2 如实点名 +
  generate_code 异常传播（旧吞成空串）+ full_workflow 真路径。⑨ **[P3] 其余诚实化**：
  unified_growth 插件市场 8 包装吞错假空清除（管理器损坏如实抛出、get_package_rating 不再伪造
  0 分统计；未知包/非法分值锁定降级契约保持）；intent_decomposer `_llm_decompose` 显式拒绝
  （旧返回关键词模拟结果冒充 LLM 输出）+ 删除死 `_simulate_llm_decomposition`；llm_parser
  sk-placeholder 占位密钥仅限本地 base_url、远程无密钥显式拒绝；mobile_sdk NetworkClient.get
  真 HTTP（旧 _fake_response 伪造响应）；mir_codegen MIR 清洗管线吞错清除（旧双层
  try/except-pass）；domains/registry fire/_dispatch_register 吞错清除。⑩ **锁定契约核实不修**
  （登记口径复核）：time_builtin parse_time 失败 0.0 / 未知时区 0 / 注册任务回调不触发——
  三后端对拍既有锁；openai_compat chat 腿异常 200 透出「Matha 错误」——诚实契约锁。
  新 `tests/test_phase11_honest_purge.py` **46 条**三锁：parity（symbolic 结构手算对拍
  ∫x²=x³/3 + symbolic_calc (x²)'=2x/值 9.0 + unknown 括号边界；robotics 11 点插值逐点对拍/
  真写关节；_wait 真等待时长锁；db 真 sqlite 行读回/事务回滚提交/dict 与 SQL 同库；并发
  submit_task 真执行 await_all=1；前端四语言真 IR 节点 + i64→T_INT；Rust 生成器真函数体）；
  闭环（db create_table→insert→select→drop_table 全链、full_workflow python 真产物）；显式拒绝
  （除零、robotics 越界/无传感器、WebSocket RFC6455、门面未初始化×9、hybrid 三空壳 + 反向、
  转译未知节点、市场损坏传播×8、LLM 模拟冒充、远程无密钥、registry 回调/钩子）。
  全量门禁 **6816/6816 通过**（基线：`python scripts/check.py`，tests 项 6713 过 +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知
  未实现不计入分母；零失败零跳过；增量 +46 = 新测试文件条数）。
- **2026-11 阶段 11 孤儿清单登记（零消费文件，待批准删除）**：transitive 零消费扫描
  （无任何 src/tests/scripts/extensions 消费者；动态 importlib 字符串引用已计入；src 总
  180,938 行）+ **非 Python 数据引用复核**（manifest.json / docs / spec 全量核对）实测
  **30 文件 14,068 行（7.8%）**：纯库模块 17（adapters/language_adapters、binary_codec、
  compiler_matha、cross_language_verifier、debug_interp29、exceptions、matha_formula、
  matha_service、numpy_compat、os_module、symbol_compat、web_framework、
  hardware/hal.py（仅被孤儿 benchmark 与孤儿 hal_multiprocessing 消费）、
  hardware/hal_multiprocessing、jupyter/notebook_example、offline/storage（OFFLINE_GUIDE
  有文档示例但零代码接线）、optimization/sparse_svd）+ 含 `__main__` 独立入口 13
  （base3_matha、lexer_matha、matha_daemon、demos/demo_calculus_matrix、
  hardware/benchmark、tools/flame_graph、mbc/native_elf、language_adapters、binary_codec、
  compiler_matha、cross_language_verifier、offline/storage、stdlib/probability_stats，
  与前组有交叠）；其中 mbc/native_elf.py（2,653 行）为 docs/spec/NATIVE_* 五份文档锚定的
  原型（无代码消费）。
  **复核更正两轮**：① 早前 54 文件估算中的 `src/codegen/` 与 `src/auth/` 经实查有活引用
  （autonomous.py:464 `from src.codegen import codegen`；matha_system.py:402 AuthManager），
  移出删除候选；② 首轮 34 文件清单中的 `src/domains/{extended_modeling,real_hardware,kernel}.py`
  经 manifest.json 复核为**已接线的懒加载领域插件**（PluginResolver 按需动态加载，无静态
  import 属设计状态），移出删除候选；`src/symbol_registry.py` 与
  `src/plugins/toolchain_signature.py` 经 parent-package import 形态复核有真实消费者
  （tests/test_symbol_registry.py、pkg_manager_v2.py:55 PEP 562 惰性转发），同样移出。
  **删除已于 2026-11-12 经用户逐类审批后执行**（选项：全删 30 个；git 历史可恢复）：
  29 个 `git rm` + debug_interp29.py 为未跟踪文件直接删除；空目录 adapters/、demos/、
  optimization/ 一并移除（tools/ 保留其余 4 个活文件、hardware/ 保留 hal_v2、jupyter/
  保留 matha_magic）。doc 面同步：README 内核外工具插件 14→9、ARCHITECTURE
  core_py_lines 34,260→31,608（repo_facts 实测一致）。
- **2026-11 阶段 12a 收官（Matha 终端 · 纯 Matha 词法/句法层；12b-12e 未开工）**：用户指令
  「为 Matha 制作真实专属诚实化/显示型终端，完全由 Matha 自身编译器/解释器构建…以 CMD 为模板」，
  三项设计决策经 AskUserQuestion 审批（①未知命令=CMD 式透传系统执行；②管道/重定向=解析预留+
  显式拒绝；③调试=轨迹+快照，交互式单步另立片）。本片落地**终端核心前两层（纯 Matha）**：
  `matha/term_lexer.matha`（终端词法器，119 行：字符级扫描状态机——CMD 兼容引号合并
  `a"b c"d`→一词、引号内管道/重定向不分隔、`>`/`>>` 相邻字符区分、空行返 `[]` 终端无操作、
  引号未闭合显式拒绝；递归深度随行长线性增长，调用方须随行长抬高递归上限——与
  `matha/lexer.matha` 扫描 同先例）+ `matha/term_parser.matha`（终端句法器，105 行：命令帧
  `{命令, 参数, 管道链, 重定向, 重定向目标}`，文法 `命令行 := 段 (管道 段)* [重定向 目标]`，
  缺命令名/管道残缺/重定向残缺·重复·不在末尾全部显式拒绝）+ 宿主 `_CN2FILE` 两行接线。
  管道与重定向本层只**忠实成帧**，真执行属 12c 执行器（未实现时执行器显式拒绝）。
  三锁 50 条（`tests/test_matha_term_12a.py`：token/帧对拍 vm=host 30 + 帧结构语义 4 +
  双端同文本拒绝矩阵 16），0.91s 全绿。doc 同步：README 语料 166→168、测试文件 128→129；
  ast_vm_gap 快照重生成（阻塞缺口 0）。
  全量门禁 **6865/6865 通过**（基线：`python scripts/check.py`，tests 项 6762 过 46m47s +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知
  未实现不计入分母；零失败零跳过；增量 +50 = 本片三锁条数，6815+50 算术闭合）。
  **诚实边界（登记，不粉饰）**：终端的 OS 级能力（stdin/子进程/网络）纯 Matha 无法实现，
  12b 起以最小内建胶水提供（stdlib.matha 既有先例注释「OS 级能力，纯 Matha 无法实现」）；
  Matha 宿主实现本身是 Python 自举，终端进程入口（12d）为薄壳——「完全由 Matha 构建」的
  口径 = **终端全部命令逻辑（词法/句法/分发/执行）为纯 Matha 模块，跑在 Matha 自身
  解释器/VM 上**，Python 层只保留 IO 原语与进程入口，不做任何命令逻辑。
- **2026-11 阶段 12b 收官（终端 OS 胶水内建：stdin/文件系统/执行Matha/调试Matha/网络；12c-12e 未开工）**：
  终端的 OS 级能力以最小内建胶水落位（12a 已登记的口径）。`src/kernel/terminal_builtin.py`（内核终端
  原语，~150 行，纯 stdlib os/shutil，无 rmtree——**递归删除永不支持**为安全边界，非空目录删除显式拒绝
  且目录原样保留）：输入行(EOF→空串)/列目录(排序，[名,是目录,字节数])/建目录/删除路径/复制文件/改名/
  当前目录/换目录/路径存在/执行Matha(经 exec_api 进程内真执行，错误如实上抛)。宿主 `src/interp.py`
  接线 11 名（复制文件/改名经 _curry_module 柯里化），VM `src/mbc/vm.py` 同名注册（_curry2 柯里化）；
  **调试Matha 仅宿主**（逐节点轨迹捕获 "matha.interp" DEBUG 流 + 运行后变量快照 + 错误如实入账不裸抛），
  VM 注册同名实现但**显式拒绝**（无逐节点轨迹能力，非静默降级）。网络侧 `src/domains/networking.py`
  增 取网址( urllib 真 GET→字符串)/下载文件(柯里化，字节落盘)，manifest 重生成。三锁 19 条
  （`tests/test_matha_term_12b.py`：fs/执行Matha/输入行/网络 对拍 vm=host + 调试Matha 轨迹快照闭环 +
  安全边界拒绝矩阵；网络用 file:// 走真 urllib 零外网零 mock）。doc 同步：README 测试文件 129→130、
  ARCHITECTURE core_py_lines 31,608→31,749（+141 = terminal_builtin.py + vm.py 内建注册；interp.py
  不计入 core_py_lines）。
  全量门禁 **6885/6885 通过**（基线 `python scripts/check.py`：tests 6782 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6815（阶段11）+ 50（12a）+ 19（12b 三锁）+ 1（`test_core_never_imports_plugin_contracts`
  对新增 `src/kernel/terminal_builtin.py` 的参数化用例，经临时 worktree 节点级 diff 定位核实）= 6885。
  **首轮门禁如实记录（已修）**：v1 唯一失败 `test_debug_matha_trace_and_snapshot` 为**确定性顺序依赖**
  而非环境抖动——两个既有测试文件在 pytest 收集期执行模块级 `logging.disable(logging.CRITICAL)`
  抑制全进程日志，令轨迹捕获收不到记录；修复为 `builtin_debug_matha` 捕获期间临时解除全局
  `logging.disable` 并在 finally 原样恢复（复现组合「抑制文件+12b 同进程」24/24 绿验证），v2 全绿。
- **2026-11 阶段 12c 收官（纯 Matha 终端执行器：命令注册表/CMD 命令集/CMD 式透传/显式拒绝；12d-12e 未开工）**：
  `matha/term_engine.matha`（终端执行器，纯 Matha，~300 行）：命令帧 → 结果帧 `{"输出": [行], "退出": Bool}`。
  **命令注册表** = 纯 Matha 字典 + 闭包注册（`命令表()`），CMD 模板命令集中英别名（dir/ls/cd/type/cat/copy/
  del/rm/mkdir/md/ren/rename/echo/cls/run/load/write/debug/help/exit/quit），英文别名大小写不敏感；
  **CMD 命令集**：目录（列目录渲染 `名\t<目录>|\t字节数`）/换目录（进程级真 cwd）/显示文件（去尾空行）/
  复制/删除/建目录/改名/回显/清屏（ANSI `\x1b[2J\x1b[H`）/帮助/退出；**Matha 代码命令**：运行（引号包裹
  源码 → 执行Matha）/加载（读 .matha → 执行Matha）/编写（手写代码块落盘）/调试（轨迹+快照全链渲染，
  VM 显式拒绝如实穿透）；自写 `显示值` 递归渲染任意 Matha 值（null/List/Dict/元组/函数分别如实呈现，
  stdlib str 只覆盖数字/布尔）。**未知命令 = CMD 式透传**（经领域内建 执行命令 真 subprocess，原行保真
  传参，失败如实追加 `命令退出码: N` 行不伪装成功）；**管道/重定向 = 12a 解析预留特性，执行器显式拒绝**
  （错误如实上抛，真实现另立阶段）；文件 I/O 走 stdlib read_file/write_file（两端同名）。语法面踩界如实
  登记：Matha 解析器不支持 行首运算符续行/`then` 独立成行/调用参数跨行（`[` 字典/列表括号内跨行除外），
  引擎已按此约束改写为 let 分段。三锁 72 条（`tests/test_matha_term_12c.py`：命令行对拍 vm=host 15 +
  显示值渲染对拍 9 + 文件系统镜像对拍 3 + 透传对拍/退出码/帧重建 3 + 编写→加载→运行/换目录→列目录/
  调试全链闭环 4 + 管道/重定向/参数个数 19 例×双端 + 非空目录删除保留/文件缺失/VM 调试穿透 3），
  7.3s 全绿。doc 同步：README 语料 168→169、测试文件 130→131；ast_vm_gap 快照重生成（阻塞缺口 0；
  interp.py 仅 _CN2FILE +1 行不计 core_py_lines）。
  全量门禁 **6957/6957 通过**（基线 `python scripts/check.py`：tests 6854 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6885（12b）+ 72（12c 三锁）= 6957。
- **2026-11 阶段 12d 收官（独立入口 matha_term.py + .msh 批处理 + matha_main 集成 + 端到端；12e 未开工）**：
  `src/matha_term.py`（终端进程入口，**薄壳**——零命令逻辑，符合 12a 拍板口径「Python 层只保留 IO 原语
  与进程入口」）：横幅 + `Matha>` 提示符；三种形态 ①无参 REPL（逐行 runner，RuntimeError → `错误: ...`
  继续不退出、KeyboardInterrupt 继续、EOF 退出 0、`退出` 标志结束 0）②`-c "命令"` 单命令（退出码 0/1
  如实：成功 0、命令错误/透传失败 1，不伪装成功）③位置参数 .msh 批处理（`#` 注释与空行跳过、单行错误
  `错误(第 N 行): ...` 打印后**继续执行**（CMD 批处理语义）、有错退出 1、`退出` 标志提前结束 0）；
  `python -m src.matha_term` 与 `python -m src.matha_main 终端/term` 同一入口（matha_main 仅 subparser
  + `set_defaults(func=_cmd_term)` 三行委托）；`sys.setrecursionlimit(max(30000, 行长))` 随行长抬高
  （12a 词法器递归扫描同先例）。`src/matha_main.py` epilog 补终端行；`src/interp.py` `_CN2FILE` +1 行
  接线（不计 core_py_lines）。三锁 20 条（`tests/test_matha_term_12d.py`：subprocess 端到端——
  `-c` 成功/退出/错误退出码/透传/透传退出码 5 + 运行/调试/管道拒绝经入口 3 + 批处理 干净/错误继续/
  退出提前/编写→加载循环 4 + 缺脚本拒绝/-c 缺参 2 + REPL 会话（横幅/提示符/错误继续/退出停止/不可达
  行断言）/REPL EOF 2 + matha_main 终端与 term 别名/批处理/--help 4），14.6s 全绿。doc 同步：
  README 测试文件 131→132（matha_term.py 不计入 core_py_lines——只统计 kernel/mbc 内核面）。
  全量门禁 **6977/6977 通过**（基线 `python scripts/check.py`：tests 6874 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6957（12c）+ 20（12d 三锁）= 6977。
- **2026-11 阶段 12e 收官（扩展命令注册 + 启动自动加载 + 升级命令；阶段 12 五片全落）**：
  **① 扩展命令注册（纯 Matha，term_engine.matha ⑦b 段）**：`注册命令 名字 路径`（别名 regcmd）/
  `注销命令 名字`（unregcmd）；注册表 = 当前目录 `matha_term_registry.txt` 行式文本（行格式
  `名字 路径` 单空格——名字/路径含空格或换行注册时显式拒绝；手改坏行在派发时显式拒绝，不静默跳过
  用户数据）；派发顺序 **内建命令表 → 注册表 → CMD 透传**，注册名 to_lower 存储（与内建英文别名
  大小写不敏感同口径），**不可覆盖内建**（注册时显式拒绝冲突名，含英文别名 dir/help/升级 等）；重注册
  = 幂等更新路径（不产生重复行）；注销未注册显式拒绝；**注册表 = 共享磁盘事实**（宿主注销对 VM
  同样生效——跨后端再注销显式拒绝，已入锁）。调用扩展 = 处理器源码 + 拼接 `处理([参数们])` 经
  执行Matha 进程内执行；处理器契约：导出 `处理(参数们)` 并自行 输出 结果行（注册只校验路径存在；
  缺 处理 导出在调用时如实上抛）。**参数安全嵌入限制**：含引号/反斜杠/换行显式拒绝（防拼接改写为
  任意代码）——注：含引号参数在 12a 终端词法层已被剥除/拒绝（引号未闭合显式拒绝），引擎防线属纵深
  防御，经 `_安全参` 双端直锁。
  **② 启动自动加载（CMD AutoRun 同族）**：`src/matha_term.py` repl() 横幅后自动执行当前目录
  `matha_term_extensions.msh`（`#` 注释/空行跳过；行错误如实打印 `自启动(第 N 行) 错误: ...` 后继续；
  其中的 `退出` 标志**不**结束会话——自启动用于注册命令等准备，不允许隐式杀掉用户会话）；仅 REPL
  触发，`-c` 与 .msh 批处理不触发。
  **③ 升级命令**：域内建 `检查包更新()`（`src/domains/os_module.py` `_register_os` 注册 +
  `manifest.json` os_module 符号声明 + `_os_symtab_names`/`__all__` 同步）——**内核纯度约束实录**：
  初版误放 `src/kernel/terminal_builtin.py` 被 kernel_purity ratchet 拒绝（pkg_manager 系属 legacy
  面，内核不得依赖），按 `执行命令` 先例迁移至 os 域后 14/14 恢复绿；`检查包更新` 从当前目录
  `.matha_packages/*/manifest.json`（install() 的落盘形态）真实还原已安装集合（pkg_manager_v2 的
  `installed` 只存进程内存，不还原则检查恒空），manifest 缺 name/version 如实上抛不静默跳过；版本
  统一转 str 供纯 Matha 引擎直接渲染。**顺手修复 pkg_manager_v2 既有 bug**：`check_updates` 对
  `installed`（install() 填充的是 Version 实例）调 `Version.parse` 直接 TypeError——即 upgrade_all/
  upgrade_package 对真实已安装集合恒崩的潜伏缺陷；`Version.parse` 加 isinstance 守卫（与该类
  `__eq__`/`__lt__` 既有 str|Version 双容忍一致），pkg 面既有测试 165 条回归全绿。纯 Matha `_升级`
  （term_engine ⑦c 段）：无参 → 渲染 `可用更新（本地检查，不下载不安装）` + 逐行
  `包名: 当前 -> 最新 (类型)` 或 `无可用更新`；`升级 <包名>` 过滤（大小写不敏感）；`升级 解释器`
  （matha/interpreter 同拒）→ **显式拒绝**（自举核心不可终端自升级）；诚实边界：本片只检查不安装
  （真安装另立片）。
  三锁 39 条（`tests/test_matha_term_12e.py`：对拍 注册/调用/注销+跨后端共享/重注册/升级四形态×双端/
  帮助 12e 行 + 闭环 全链落盘逐步断言/注册表跨解释器实例/宿主写 VM 读 + 拒绝矩阵 内建冲突×4×双端/
  8 行拒绝×双端/注入参数/`_安全参` 直锁/坏注册表行/缺导出/坏 manifest + 端到端 自启动注册并调用/
  错误继续/退出标志忽略/缺席静默/-c 不触发），25.7s 全绿。doc 同步：README 测试文件 132→133 +
  **命令行工具节新增 `matha 终端` 小节（阶段 12 首次入 README 功能面）**；core_py_lines 31749 不变
  （检查包更新 内建落 os 域不计、matha_term.py 自启动不计——只统计 kernel/mbc）；语料 169 不变
  （term_engine.matha 增段不改文件数）。
  全量门禁 **7016/7016 通过**（基线 `python scripts/check.py`：tests 6913 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6977（12d）+ 39（12e 三锁）= 7016。
- **阶段 12 总收官（诚实化/显示型终端五片 12a–12e 全落，口径与边界汇总）**：用户指令「为 Matha
  制作真实专属诚实化/显示型终端，完全由 Matha 自身编译器/解释器构建，可以独立运行，也可以在其它
  系统终端中运行，整个终端必须可以运行/调试/编写/手写代码与运行/加载/下载/使用网址/文件，以 CMD
  为模板，必须可扩展与升级，集成至 Matha 中」——三项设计决策经 AskUserQuestion 审批（①未知命令=
  CMD 式透传系统执行；②管道/重定向=解析预留+显式拒绝；③调试=轨迹+快照）。**落地口径**：终端全部
  命令逻辑（词法/句法/分发/执行/扩展/升级渲染/透传决策）为纯 Matha 模块（matha/term_lexer 119 行 +
  term_parser 105 行 + term_engine ~430 行），跑在 Matha 自身解释器/VM 上；Python 层只保留 IO 原语
  （12b 内核胶水：stdin/文件系统/进程内 Matha 执行/调试快照）与进程入口（12d 薄壳 matha_term.py），
  不做任何命令逻辑；领域内建 执行命令/检查包更新 走 os 域插件（内核纯度 ratchet 全程绿）。
  **能力覆盖**：CMD 模板命令集 + Matha 代码命令（运行/加载/编写/调试）+ CMD 式透传（退出码如实）+
  扩展注册（注册表持久化/跨后端共享）+ REPL 自启动 + 包更新本地检查；下载/使用网址 经 12b 胶水
  下载内建与透传覆盖。**如实边界（不粉饰）**：管道 | 与重定向 > >> = 12a 解析预留特性，执行时显式
  拒绝（真实现另立片）；升级只检查不安装；OS 级能力（stdin/子进程/网络）纯 Matha 无法实现，以最小
  胶水内建提供；`完全由 Matha 构建` 的口径 = 命令逻辑纯 Matha + 跑在自身解释器上，Python 层无命令
  逻辑。累计三锁 50+19+1+72+20+39 = **201 条终端专项**，全量门禁 7016/7016。
- **2026-11 阶段 13a 收官（终端管道真执行：CMD 式 stdin 注入；13b/13c 未开工）**：用户拍板
  范围「终端补全片」+ 设计决策「stdin 注入」（AskUserQuestion）。**① 引擎消费者**（term_engine
  ⑦d 段，纯 Matha）：`查找 子串`（别名 findstr/find）逐行 `find` 过滤；`排序`（别名 sort）码点序
  稳定插入排序（宿主与 VM 字符串比较语义一致）——命令表接线，`回显 hi | 查找 h | 排序` 对拍锁定。
  **② 机制**：管道载荷 = 左段**显示行**（终端所见即右段所得）；`_执行链` 段间经胶水 管道输入(行们)
  预置 / 输入行() 消费优先 / 耗尽即 EOF 空串（不回落交互 stdin）/ 管道结束() 清态；段前 set、段后
  clear，`终端执行` 入口先清陈旧态（外部手工 管道输入 的残留不漏进命令执行）；Matha 代码段经
  输入行() 真消费、透传段经新 os 域内建 `执行命令输入`（subprocess.run input= 真 stdin 注入，
  柯里化 执行命令输入(行)(输入)）消费、扩展处理器同享注册表管道面。**③ 边界（登记）**：透传段
  载荷含 stderr/退出码行（与 CMD 仅 stdout 有差异）；管道段透传按段帧重建命令行（12a 词法已剥
  引号）；管道行中空行与 EOF 不可区分（CMD stdin 语义）；行们 = 末段输出（CMD 正确口径）；退出
  标志中断链并跳过后续段；段内 RuntimeError 跳过 管道结束() 致管道态泄漏至下一入口清除（Matha
  无 try/finally，登记不粉饰）。胶水落位纪律：管道输入/管道结束 入 `src/kernel/terminal_builtin.py`
  （内核级 stdin 原语，kernel_purity 14/14 绿），执行命令输入 入 `src/domains/os_module.py`（os 域，
  四处同步：_register_os/_os_symtab_names/__all__/manifest.json）。三锁 19 条
  （`tests/test_matha_term_13a.py`：对拍 查找/排序/透传/Matha 代码消费/退出中断 ×双端 + 闭环 胶水
  状态机/入口清陈旧/段错泄漏兜底/扩展消费/执行命令输入 直锁 + 拒绝 管道输入 非 List）；12c
  管道拒绝行 ×2 条升级为真执行锁（双端）。
- **2026-11 阶段 13b 收官（终端重定向真执行：> 截断 / >> 追加 + 管道组合；13c 未开工）**：
  term_engine ⑧ 段（纯 Matha）：`_重定向写(目标, 行们, 追加)`——`>` write_file 覆盖 / `>>`
  append_file 追加（stdlib 薄包装落 `_append_file` 内建），每行 \n 结尾（CMD `echo x>f` 末行带
  换行语义）、空输出写空文件；`终端执行` 改序：执行链先行 → 退出标志跳过落盘 → 成功后按
  `帧["重定向"]/["重定向目标"]` 落盘（段内错误不落盘——执行链先于写盘求值自然成立）。CMD 式
  静默：落盘不回显（输出 []）。**边界（与 CMD 差异，登记）**：接管末段**显示行**——透传段
  stderr/命令退出码行同样落盘（同管道载荷口径）。12c/12d/13a 三处重定向显式拒绝锁升级为真
  执行锁（12d e2e 升级为 真落盘+静默+内容核实，tmp 目录隔离——matha/ 引导经 `__file__` 定位
  与 cwd 无关）。三锁 15 条（`tests/test_matha_term_13b.py`：对拍 截断/追加/管道组合/空输出/
  透传段边界 双端文件逐字节一致 + 闭环 文件状态机/退出跳过/错误保原样 + 拒绝 12a 句法三形 +
  write_file 目录目标如实上抛）。
- **2026-11 阶段 13c 收官（升级带名真安装：os 域 升级包 + 引擎接线；阶段 13 三片全落）**：
  os 域新内建 `升级包(包名)`（`upgrade_package_named`，os_module 四处同步）：还原已安装
  （`_restore_installed` 抽取共用，manifest 损坏/缺字段如实上抛）→ pkg_manager_v2.upgrade_package
  真盘安装（install 重写 `.matha_packages/<包>/manifest.json`）→ **盘上 manifest 版本复核**
  （≠ 预期即 RuntimeError）；返回 [包名, 旧版本, 新版本]。无命中（未安装/已最新）→ RuntimeError
  如实拒绝（**升级 ≠ 全新安装**，全新安装不走终端升级面）；边界 = 本地目录升级不联网下载
  （RemotePackageClient 目标为虚构端点）。引擎 `_升级` 带名分支：命中后以更新条目真名（大小写
  保真）调 升级包 → 渲染 `包名: 旧 -> 新 (已真安装)`；无参升级维持 12e 只检查口径；`升级 解释器`
  显式拒绝不放宽。12e 带名锁升级为真安装合同（盘上 manifest 重写 + 再检查无更新；盘面共享
  事实——双端各用独立目录跑同一合同，同目录续跑见「无该包」不静默重装）。三锁 9 条
  （`tests/test_matha_term_13c.py`：胶水合同/双端同合同 + 全链闭环/盘面共享 + 拒绝 未安装/
  损坏 manifest/解释器自升级 + 真 subprocess e2e）。
- **阶段 13 总收官（终端补全片：管道/重定向/升级真安装三片全落，口径与边界汇总）**：用户
  拍板范围「终端补全片」= 阶段 12 显式预留的三个「真实现另立片」；两项设计决策经
  AskUserQuestion 审批（① 管道机制 = CMD 式 stdin 注入；② 升级语义 = 带名真安装）。
  **累计口径**：阶段 13 三片三锁 19+15+9 = 43 条（`tests/test_matha_term_13a/13b/13c.py`），
  终端专项累计 201+43 = **244 条**；12c/12d/12e/13a 共四处旧拒绝锁升级为真执行/真安装锁
  （锁不退役、只换合同）。**如实边界（登记，与 CMD 差异）**：管道/重定向载荷 = **显示行**
  （透传段 stderr/退出码行同入管道与文件，CMD 仅 stdout）；管道行空行与 EOF 不可区分；段内
  错误管道态泄漏至下一入口清除（无 try/finally）；升级 = 本地目录真安装不联网。
  **doc 同步**：README 测试文件 133→136 + 终端小节 13 补全改写（管道/重定向/升级状态实时化）；
  ARCHITECTURE core_py_lines 31,749→31,778（+29 = os 域 升级包/执行命令输入 胶水）；
  ast_vm_gap 矩阵随 term_engine 增段重生（语料 used_in 计数漂移，0 缺口面不变）。
  全量门禁 **7051/7051 通过**（基线 `python scripts/check.py`：tests 6948 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6913（12e）−8（12c 管道/重定向拒绝行 2+2 条 ×双端退役）+19+15+9（13a/13b/13c
  三锁）= 6948 tests。
- **阶段 6e 更新**：按下方判据「先入门禁」，AI 前端「输入→解析→执行→结果→感知」的**编排
  契约与诚实降级**（永不裸抛、schema 稳定、失败如实下沉）已由 `tests/test_ai_e2e_pipeline.py`
  入门禁锁定；但自然语言→代码/答案的**输出正确性仍不背书**、README 亦无 AI 助手功能主张。
  故五个前端文件的「未背书 / P2 降级」横幅保留（其中四个复用 chat 编排链的文件的
  「零测试」旧措辞已于 2026-11 按本条口径更正，见上；`src/ai_framework.py` 的「零专项测试」
  措辞已随其数值地基坐实更新，见上方新条目）——本通道属「接线已锁、结果不背书」。
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
  作为叠加保险；`Test executables` 转绿靠的是产品侧兜底。**已经第五次 dispatch 现场确认**：
  run 42217545003 上 `Build Executables` job 的 `Test executables` 步骤已转 **success**（整个
  `Matha CI` 权威门 9 个 job 全绿）。`matha` 主入口的同类中文输出已一并覆盖（同一 helper）。
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

