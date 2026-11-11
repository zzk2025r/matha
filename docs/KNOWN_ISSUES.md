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
  quantum grover/shor 非 AI，仍未修）；`src/unified_parser.py` 的 matha_compile 兼容假产物
  （"# Compiled N declarations" 字符串）仍在；legacy matha-cc 语法不支持现代 `#1：`
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
  quantum grover/shor 假实现与 `unified_parser.py` 假编译产物仍在（非 AI，登记同前）。
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
  假编译产物仍在（非 AI，登记同前）。
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
  假编译产物仍在（非 AI，登记同前）。
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

