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
| NI-010 | 架构框架模块为**框架级实现，未接入 Matha 编译/执行主线**：`src/compiler/` 的 pass 管理器（注册/依赖拓扑/启停，框架本体无具体优化 pass）、backend 管理器（Cranelift/WASM/EVM/Native 四后端为诚实 NotImplementedError stub，LLVM 面委托既有 `matha_to_llvm_ir`）、自适应优化器（ML 路径 sklearn 可选、默认规则路径；无函数程序除零崩溃已修）、分布式编译器（HTTP 面可选 aiohttp、依赖图纯标准库 `_DiGraph`）、增量编译器（哈希+mtime 变更检测，`_compile_file` 为模拟桩）。 | 2026-11 修复盘活批次：修复语法损坏 + 重依赖惰性化（pyproject 第三方依赖保持 0），import 面经 `src/compiler/__init__.py` 直接导出（无 try/except 静默吞错）。判据：`tests/test_framework_modules.py`（37 条）锁框架级行为与登记边界；接入 MBC 主线为独立工程项，不属现状承诺。勘误（2026-11 融合轮）：旧条目引用的「8 个优化 pass」与 `src/hal_drivers/`、`src/conflict_resolution/`、`src/security/`、`src/pkg_manager_v3.py` 均不在场（历史方案残留引用，两轮全仓核对零命中），按现树事实清除 |

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
  【阶段 17 勘误：本条两项均已于阶段 11 ⑤ 真修并经阶段 17 探针复核——MathaBytecodeCompiler
  改为 compile 需源码、真 MBC1 委托（探针 170 字节 MBC1 反序列化成功），`_generate_bytecode`
  旧方法已不存在；MathaEngine.vm_run 真执行（探针 `输出(1+2)` → [3]）。】
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
  【阶段 17 勘误：mir.py Binding/Output 与 legacy_mir_vm 已于阶段 11 ③④ 修复；
  MathaBytecodeCompiler 字节码链与 vm_run 已于阶段 11 ⑤ 修复（见上条勘误）；
  src/codegen 七后端经阶段 17 复核比登记更死——唯一工厂入口 `codegen()` 的
  parse_app_spec 按 kind 先行拒绝语言类（「未知应用类型」），静态消费者 0，属不可达
  死代码，已于阶段 17b 经用户批准删除（七文件 2,277 行 + base.py 懒导入与工厂条目，
  git 历史可恢复）。】
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
  标志中断链并跳过后续段。〔勘误 2026-11 阶段 19c〕段内泄漏已修（见阶段 19 收官条目：
  `_执行段` catch-清态-重抛；旧泄漏锁改锁新形态 test_loop_segment_error_cleans_pipe_state）；
  原登记「Matha 无 try/finally」措辞不实——Matha 有 try/catch/finally 语法，弃用 finally
  真因 = VM finally 在无 catch 重抛路径不执行 finally thunk（见阶段 19 收官条目 finally
  分歧登记）。胶水落位纪律：管道输入/管道结束 入 `src/kernel/terminal_builtin.py`
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
  错误管道态泄漏至下一入口清除（阶段 19c 已修 + 措辞勘误，见 13a 条勘误）；升级 = 本地目录真安装不联网。
  **doc 同步**：README 测试文件 133→136 + 终端小节 13 补全改写（管道/重定向/升级状态实时化）；
  ARCHITECTURE core_py_lines 31,749→31,778（+29 = os 域 升级包/执行命令输入 胶水）；
  ast_vm_gap 矩阵随 term_engine 增段重生（语料 used_in 计数漂移，0 缺口面不变）。
  全量门禁 **7051/7051 通过**（基线 `python scripts/check.py`：tests 6948 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6913（12e）−8（12c 管道/重定向拒绝行 2+2 条 ×双端退役）+19+15+9（13a/13b/13c
  三锁）= 6948 tests。
- **2026-11 阶段 14 收官（解析器踩界真化：行首运算符续行 / then 独立成行 / 参数跨行——主解析器 only，
  12c 登记三项全落）**：用户拍板范围 = 12c 登记三项 + E3；两项设计决策经 AskUserQuestion 审批
  （① 主解析器 only，bootstrap `matha/lexer.matha`·`matha/parser.matha` 维持登记边界不动；
  ② 排除 `-`；③ 纳入 E3）。**14a 词法器逻辑行续行**（`src/lexer.py`）：行首 infix-only 运算符
  （`+ * / % < > <= >= == !=`）或行尾算术/比较运算符的**紧邻**换行 → 不发 INDENT/DEDENT/NEWLINE
  （并入上一逻辑行；空行/注释行断开；续行缩进不进缩进栈，后续边界相对原层级计算）。**两项排除如实
  登记**：排除 `-`（行首 `-` 今天是一元负号语句，纳入会静默改义）；**排除 `and`/`or` 行首**——探测
  当场抓获真冲突：解析器中缀环遇 NEWLINE 退出，行首 `and` 落到语句层是**互递归函数声明的延续**
  （`func 体换行 + and 新行` 两 FuncDef，pre-14a AST 对拍证实），纳入会把它并入布尔表达式并毁掉该
  既有合法形态；行尾 `and`/`or` 续行本就合法（布尔环运算符后 skip），能力无损。首版行尾集曾含
  `=`/`and`/`or`，token 流对拍逐轮揪出（`=` 行尾换行接体、布尔环行尾换行均已合法）后收窄。
  **14b then/else 独立成行**（`src/parser.py` 三处 if 站点 2099/3492/3591）：未命中回退位置，
  修复「else 行首已合法、then 行首报错」的不对称；`{` 块形式 `if cond\n{` 保持显式拒绝。
  **14c 参数跨行**（14 处 skip，统一 LPAREN 后/逗号后/RPAREN 前三跳）：func 声明 + and 声明 +
  let rec 声明参数 + func/let rec lambda 体参数 + 独立 lambda 试探（分组/元组无害）+ E3（`-> T`
  与 `=` 之间换行）+ let rec `)` 与 `->` 之间换行；`=>` 独立成行、lambda 体参数带类型标注保持
  既有拒绝（单行同错）。**12c 登记口径修正**：「调用参数跨行」实测早已合法（真缺口 = 声明/lambda
  参数括号内换行）；`matha/term_engine.matha` 的 let-in 链为惯用形态非补丁残留，不动（72 锁语料
  零扰动）。**零扰动证明**：286 语料文件 token 流 HEAD↔新 逐 token 一致；求值用例 host ↔ vm
  输出一致。**探测中如实登记（不修）**：顶层裸表达式语句（UnaryOp/BinaryOp 形态）host 发输出、
  VM 不发（裸 变量/字面量 两端都不发）——既有双端分歧，与本阶段无关。三锁 40 条
  （`tests/test_parser_multiline_phase14.py`：续行 token 流=单行源 6 + 双端对拍 10 + 行首/行尾
  运算符全集 19 + then 矩阵/嵌套/调用内 5 + 参数跨行全形态 10 + 互递归 and 回归 2 + 边界
  拒绝 9：`-` token 锁/`and` 语句层锁/or decl 数锁/空行/注释断开/块形式/`=>` 独立行/类型标注/
  续行缩进不进栈）。
  **doc 同步**：README 测试文件 136→137；ARCHITECTURE core_py_lines 31,778→31,891（+113 =
  词法器续行判定 + 主解析器 14b/14c skip）；ast_vm_gap 无语料变更不重生成。
  全量门禁 **7091/7091 通过**（基线 `python scripts/check.py`：tests 6988 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7051（13 总收官）+ 40（阶段 14 三锁）= 7091。
- **2026-11 阶段 15 收官（双端语义对齐：语句级发射语义 host↔VM 逐项对齐——D1/D2 修复 + 自举编译器
  镜像同构；D3/D4/D5 拍板登记不修）**：摸底五分歧矩阵（探针逐项复现）——**D1** 顶层裸二元/一元运算
  （host 解释器发射其值 / VM 兜底 POP 吞掉：`matha run` 文件面 `1+2` host 出 3、VM 静默）；
  **D2** 顶层 if 表达式（host `_exec_decl` 末尾 else 整体静默跳过——代码不跑、分支内 输出(...) 丢失 /
  VM 照常执行）；**D3** `let x=1 in [x+2]`（host 发首元素〔自测块兼容行为〕 / VM POP）；
  **D4** 顶层裸变量/字面量（host 静默 / VM `MathaUndefinedNameError`）；**D5** `===`（host 支持
  但语义可疑：`1===1.0`→False、`"甲"==="甲"`→False、`[1]===[1]` 解析拒绝 / VM RuntimeError
  不支持的二元运算符）。**用户拍板**：D1 修（VM 侧加发射）、D2 修（host 侧加 IfExpr 分支）、
  D3/D4/D5 登记不修（D3 是自测块兼容契约、D4 变量名引用属语义错误面非发射面、D5 修任一端都是
  语义变更另立片）。**15a**（`src/mbc/compiler.py` `_compile_top_decl` 新分支）：UnaryOp 或
  BinaryOp(op≠"=") → `_emit_expr` + OP.OUTPUT；`=` 赋值形态（顶层下标赋值 `s[0] = 9` 解析为
  BinaryOp("=")）保持双端 no-op POP 契约不动（误纳入时 test_set_index_and_mutate 当场揪出）。
  **15b**（`src/interp.py` `_exec_decl` 新 IfExpr 分支）：`_eval` 真执行（分支副作用生效、值丢弃、
  错误传播），与 VM 语句语义一致。**15c 自举编译器镜像**（`matha/compiler_matha.matha` 新增
  `_编译顶层声明` 包装层，仅 `_编译声明列表`/`_编译非函数列表` 两个顶层入口接线）：块尾
  （`_发射块末条`）/生成语句链复用的 `_编译声明` 兜底保持 POP 不动（宿主块层仍 POP，
  test_brace_still_dispatches 两轮揪出）；包装层条件先 let 绑定再取用（func-def 解析器把
  `= (a, b) =>` 贪婪当 lambda 参数表），`_发射表达式` 只在 发输出 真分支内调用（机械单元/输出/
  while 等非表达式节点必须走 `_编译声明`，无条件调用时 test_brace 当场揪出）；test_mbc_bootstrap
  主码断言同步 [0x01,0]+[0x60]（OUTPUT）并登记镜像同构口径。**零扰动面**：语料求值对拍仅
  kernel_memory.matha/statistics.matha 两处命中且双端一致报错，其余全语料零扰动；golden 39 零
  命中；bootstrap 链零命中；ast_vm_gap 无 used_in 漂移不重生成（11/11 绿）。三锁 31 条
  （`tests/test_semantic_parity_phase15.py`：顶层表达式双端对拍 12〔1+2/5-3/2*3/7/2/7%3/1<2/
  2>=2/1==2/-3/~5/-(2+3)/`甲=3` 续行/`输出(1)+2`→[1,3]〕+ if 表达式 3〔then 发射/else 发射/
  值丢弃+错误传播〕+ e2e 8〔matha run 子进程 binop/IfExpr、eval 回归与 wrap 契约、while、
  MechUnit、GlobalIdStmt〕+ 登记边界 11〔D3 host[3]/vm[]、D4 裸变量 host 静默/vm 报错、
  D5 host True/vm RuntimeError "==="、D5 数值/字符串语义锁〕）。
  **doc 同步**：README 测试文件 137→138；ARCHITECTURE core_py_lines 31,891→31,899（+8 =
  VM 顶层发射分支 + host IfExpr 分支）。
  全量门禁 **7122/7122 通过**（首跑 1 红 = doc_facts 读到修正前 ARCHITECTURE 数字〔doc 修正与
  门禁起跑竞速〕，单测复核绿后全量重跑干净：tests 7019 + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7091（14 收官）+ 31（阶段 15 三锁）= 7122。
- **2026-11 阶段 16 收官（双端语义第二片真化：阶段 15 拍板「登记不修」的 D3/D4/D5 全部修复；
  自举镜像同步）**：**用户拍板**（AskUserQuestion 三项全选推荐）：D3=host 删死兼容、
  D4=对齐求值丢弃+BOM 根修、D5=三端真化严格值相等。**D3**（`src/interp.py`）：删除
  `_exec_stmt` ListLiteral 首元素分支（「兼容自测块 [1] → 输出 1」死兼容）+
  `_exec_stmt_or_expr` 去掉 ListLiteral 语句归类——let-in 列表体路由 `_eval` 求值丢弃
  （副作用保留、值不发射），与 VM「求值+POP」同构；**语料对拍收益**：lexer.matha 从
  「双端 OK 但输出不同」转为双端一致 []（回归锁 `test_run_lexer_matha` 同步改锁新形态
  ——旧锁 `assert 1 in outputs` 锁的正是死兼容漏发值）。**D4**（`src/interp.py`
  `_exec_decl` 新裸表达式分支）：Variable/IntegerLit/FloatLit/StringLit/BoolLit/IsExpr/
  IndexExpr/SliceExpr/TypeOfExpr 语句 → `_eval` 求值丢弃（未定义名随之报错，两端一致）；
  SendExpr/ChanExpr 通道收发有副作用，维持既有静默跳过（登记不修）。**BOM 根修**
  （`src/lexer.py` `__init__`）：文件首 `\ufeff` 在进 token 流前剥掉——此前被标识符规则
  吞成名为 `\ufeff` 的裸未定义变量语句（host 静默容忍、VM DCE），D4 对齐后 5 个带 BOM
  语料文件（matha/runtime/simple_test/test2/test_dbg/test_dbg2/test_orig.matha）会误报。
  **D5 三端严格值相等**：`===`/`!==` = `(type(l) is type(r)) and (l == r)`（旧身份语义
  废除——`"甲"==="甲"` 因两个独立字面量对象恒 False）：host interp BinaryOp eval +
  interp_ic `_strict_eq/_strict_neq`（内联缓存特化路径）+ VM `_BINOPS` 同名键 +
  compiler `_BIN_OPS` 归约表 + 自举镜像 matha/compiler_matha.matha 二元运算表
  （stage2↔stage3 定点同构）；token 语义注释「=== 严格相等」本位落地。
  **零扰动证明**（HEAD 工作树基线对拍：`git worktree add` 到 38732e2 跑同一 174 语料
  host/vm sweep 再 diff）：全部跟踪语料 VM 状态/输出与基线逐位相同；host 无类别迁移
  （4 文件首个报错名前移 = D4 求值更早的裸未定义名，同 ERR 类别）；唯一新增错误项 =
  未跟踪生成文件 matha/generated/算术库.matha（VM 拒 `≠`，存量缺口）。
  【阶段 17 勘误：① matha/generated/ 实为 `.gitignore` 忽略目录（129 行），非「未跟踪」；
  ② `≠` 经探针复核为**双端全拒**（host「未知运算符 '≠'」/ VM「不支持的二元运算符
  '≠'」——host 整文件跑通不报错系函数体惰性求值、该函数从未被调用；VM 编译期对
  函数体 eager 编译故先炸），本条目原措辞只点名 VM 侧不完整；缺口已由阶段 17a
  解析器归一化真化（`≤`/`≥` 同批）。】
  **残留登记（存量分歧、与死兼容无关，与基线同文件同 vm 值）**：parser.matha 的
  `[1]` 自测 MechUnit→CodeBlock→OutputTrail→Output(printf,1) host 全发射/VM 欠发射
  （parser.matha vm [1] vs host [1,1]；compiler_matha/nl_* vm [] vs host [1,1]；
  runtime/test_compile·test_math 浮点精度型差异）；`[1]===[1]` 语句位置 ParseError
  （列表语句解析形态，与 D5 值语义正交，两端同源解析器同报错）。
  【阶段 18 勘误：本块残留登记 10 文件分歧已全部真化——parser.matha/test_compile/test_math
  host 双跑系 `_exec_with_deferreds` 对 ModuleDecl 的递归与内层循环**双执行**（18a 删递归根修，
  「浮点精度型差异」措辞勘误：值逐位相同、仅发射次数 ×2）；compiler_matha/nl_*/interp.matha
  host 多出的 [1,1] 系 `use` 加载嵌套 run 把被载模块自测块输出**泄进载入方**（18b
  _loading_module 标志跳过，matha_bootstrap.py:59 同款边界）；`[1]===[1]` 语句位 ParseError
  已由 18d 全中缀回退真化为双端发射 True。含 host 单侧多发的 parser.matha 在内，10 文件
  双端逐值一致（tests/test_semantic_parity_phase18.py 封死）。】
  【阶段 21 勘误：上块 compiler_matha/nl_* 的 vm [] 半边系 use 编译期 no-op 时代的影子
  形态——21b 编译面 use 解析真化后，VM 面经 加载模块 胶水真执行被载模块（自测块照旧不进
  输出，双端输出仍逐值一致）；裸 VM（无加载器注入）遇 use 由静默 no-op 改为诚实拒绝
  「未定义变量 '加载模块'」（tests/test_semantic_parity_phase18.py 四条旧 vm 断言已按
  旧锁改锁新形态协议改锁）。】
  三锁 44 条（`tests/test_semantic_parity_phase16.py`：D3 对拍 8〔值丢弃/副作用保留
  `let 甲=1 in [输出(9)]`→[9] 双端/表达式位 `输出(let 甲=2 in 甲*3)`→[6] 双端〕+
  D4 裸表达式矩阵 13〔8 形态求值丢弃 + 3 未定义名 + BOM 双端 2 + 词法器 token 锁〕+
  D5 严格相等矩阵 13〔跨数值类型/同值同型独立字面量/布尔整数分型/变量绑定值〕+
  闭环 e2e 5〔matha run 文件面：D3 丢弃不吐值/D4 退出码 1/D5 真吐 True/BOM 文件正常〕+
  边界 4〔`[1]===[1]` ParseError、VM `_BINOPS`/compiler `_BIN_OPS` 静态锁、自举镜像
  表登记〕）；阶段 15 文件 6 条登记边界锁重写为真化后一致性轻锁（防旧分歧形态回潮）。
  **doc 同步**：README 测试文件 138→139；ARCHITECTURE core_py_lines 31,899→31,909
  （+10 = D3 删分支 + D4 裸表达式分支 + D5 三端登记 + BOM 剥除）；ast_vm_gap 快照
  重生成（运算符表登记 → used_in 漂移，`scripts/ast_vm_matrix.py --write`，11/11 绿）。
  全量门禁 **7166/7166 通过**（首跑 1 红 = `test_run_lexer_matha` 旧锁
  `assert 1 in outputs` 锁死兼容漏发值——预期行为变更非 flake，改锁新形态后整文件
  18/18 复跑绿，按协议全量重跑干净：tests 7063 + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7122（15 收官）+ 44（阶段 16 三锁）= 7166。
- **2026-11 阶段 17 收官（全面清算 sweep：登记不修清单逐项复核——四项拍板全落：运算符缺口
  真化 ≠/≤/≥ + codegen 七后端删除 + CI/spec 死件清理 + 登记勘误）**：用户拍板范围
  「全面清算 sweep」（阶段 11 同款），对 KNOWN_ISSUES 全部「登记不修/坐实不修」条目逐项
  探针复核现状（崩溃/假成功/未诚实化/登记过期），候选清单经 AskUserQuestion 四项全选。
  **摸底结论**：登记项三类——①登记过期（bootstrap 字节码链/vm_run 暂眠已于阶段 11 真修、
  mir.py/legacy_mir_vm 已于阶段 11 修复、「未跟踪」实为 .gitignore）；②真缺口
  （≠/≤/≥ 双端全拒、codegen 七后端不可达死代码 2,277 行、CI/spec 死件）；③良性边界
  （parser.matha MechUnit 分歧、自举链下标、symbolic 覆盖、SendExpr/ChanExpr、
  `[1]===[1]`、time_builtin/openai_compat 锁定契约、G-5、AI 不背书、CI secrets/休眠
  工作流——维持登记不动）。
  **17a 运算符缺口真化（≠/≤/≥）**：lexer 早已映射（OP_NEQ/OP_LE/OP_GE）、
  stdlib_symbols.matha 早已注册为官方运算符（不等于/小于等于/大于等于），但三处求值面
  全拒（host「未知运算符」/ VM「不支持的二元运算符」）——语言表面声明了不存在的运算符；
  唯一真实踩中点 = gitignore 的 matha/generated/算术库.matha:85 函数守卫 `base ≠ 1`
  （host 函数体惰性求值整文件跑通不报错、VM 编译期 eager 先炸）。修复 = 解析器三处
  op 取值位点归一化（`src/parser.py` 类常量 `_CMP_ALIASES` {≤→<=, ≥→>=, ≠→!=}，
  应用于 1746 比较环/1755 链式比较/1765 等值环——`_parse_set_expr` 集合运算符 type→op
  字典与 ∧/∨ 类型归一化同先例），host interp / interp_ic / MBC VM / compiler /
  自举镜像五面共用 ASCII op 字符串集；词法器与 token 流不动（语料仅注释/元数据使用，
  零扰动）。**`<>` 死键双面删除**（`src/mbc/compiler.py` _BIN_OPS + 自举镜像
  matha/compiler_matha.matha 同名行——词法器无 `<>` token、三端求值面也无 `<>`，
  镜像同构纪律同步）。验证矩阵 25 例（输出/let 绑定/链式比较/布尔组合/算术库同型
  函数守卫/ASCII 回归/集合∪∩⊆/∧/∨/⊕）双端逐值一致。
  **17b codegen 七语言后端删除**：python/rust/c/cpp/go/java/js_backend 共 2,277 行——
  比阶段 10 登记「零消费者原型」更死：唯一工厂入口 `codegen()` 的 parse_app_spec 按
  kind 先行拒绝语言类（「未知应用类型: …（应为 网页/桌面/服务/系统/内核/游戏/建模）」），
  静态消费者 0（grep src/tests/scripts/extensions 全负），属不可达死代码；经用户批准
  `git rm` 七文件 + `src/codegen/base.py` 懒导入（7 行）与工厂条目（9 项）清理；
  应用类 kind 真产物回归（网页/桌面冒烟 成功=True）、语言类拒绝契约不变（9 kind ×
  未知应用类型）。`tests/test_ffi_sdk_honest.py` 不路由锁不受影响（锁的是 ffi_sdk 源码
  文本）。
  **17c CI/spec 死件清理**：`matha-ci.yml` benchmark 死 job 删除（`if: false` + 主体
  引用已删除的 src/vm.py，9e 登记口径「要么重建、要么删除」按删除拍板；YAML 解析实测
  通过、test_ci_hygiene 6/6）；`matha.spec` 2 处 + `matha-cc.spec` 1 处死 hiddenimports
  删除（`src.tree_sitter_backends`、`src.domains.hal` ×2，`ls` 坐实模块不存在；活条目
  `src.domains.hardware` 等保留）。
  **17d 登记勘误（本文件内，括注式）**：阶段 10 条目（bootstrap 链/vm_run → 阶段 11 已修
  探针复核：MBC1 170 字节反序列化成功、vm_run `输出(1+2)`→[3]）；阶段 10 补充条目
  （mir.py/legacy_mir_vm → 阶段 11 已修；codegen 七后端 → 不可达并已删）；阶段 16 条目
  （「未跟踪」→ .gitignore 忽略；「VM 拒 ≠」→ 双端全拒、host 侧被函数体惰性求值掩盖）；
  9e 两条（spec hiddenimports/benchmark job → 已删）。
  三锁 56 条（`tests/test_phase17_sweep.py`：对拍 28〔≠/≤/≥ 输出/let/链式/布尔组合/
  算术库同型函数守卫 15 + ASCII 回归 6 + 集合∪∩⊆/∧/∨/⊕ 6 + AST op 字符串归一化 1〕+
  闭环 13〔matha run 真子进程 ≠/≤/≥ 3 + codegen 应用类真产物 1 + 语言类 9 kind 拒绝〕+
  防回潮 14〔七后端文件缺席 7 + import 拒绝 + base.py 文本锁 + compiler/镜像 `<>`
  双面缺席 + ci workflow 无 benchmark + spec 死条目缺席 + 非空洞活条目 +
  stdlib_symbols 注册面不动〕+ 登记边界 1〔自举链下标维持〕）。
  doc 同步：README 测试文件 139→140；ARCHITECTURE core_py_lines 31,909→31,918（+9 =
  解析器 _CMP_ALIASES 常量与三处归一化位点；codegen 不计入 core_py_lines 统计面）；
  ast_vm_gap 镜像删行无语料节点面变化（11/11 复核绿，不重生成）。
  全量门禁 7222/7222（tests 7119 + kernel_purity 14 + ast_vm_gap 11 + golden 39 +
  dep_audit 1 + native_parity 38〔native 1 例已知未实现未计入〕，失败 0，一次跑绿）。
  算术闭合：7166（16 收官）+ 56（阶段 17 三锁）= 7222。
- **2026-11 阶段 18 收官（双端语义第三片 + 通道收发 + `[1]===[1]` 真化：阶段 16 残留登记
  10 文件分歧全部根修，用户拍板三项全选、四设计全推荐）**：摸底把四形态分歧归约为两根因
  + 两独立缺口（logging.Handler 执行轨迹逐行坐实），AskUserQuestion 范围三项全选
  （双端语义第三片 / SendExpr·ChanExpr 通道收发 / `[1]===[1]` 语句位）、设计四项全推荐
  （删递归保内层循环 / 跳过被载模块自测块 / 全中缀回退 / host 镜像 VM 语义）。
  **18a 双执行根修**：`src/interp.py` `_exec_with_deferreds` 删 ModuleDecl 递归分支——
  模块内部声明此前被「`_exec_decl(ModuleDecl)` 内层循环 + 延迟递归」双跑（非 FuncDef
  声明：自测块 [1]→[1,1]、绑定副作用 ×2；FuncDef 因递归路径 `continue` 跳过幸免）；
  VM 编译模块内声明仅一次，host 对齐单次。影响：parser.matha host [1,1]→[1]、
  runtime/test_compile·test_math 值 ×2→×1（勘误阶段 16「浮点精度型差异」措辞——值逐位
  相同、仅发射次数）、interp.matha/interp_matha.matha 的 [1,1] 系 18b 泄漏叠加（见下）。
  **18b use 加载泄漏根修**：`load_matha_module` 嵌套 `self.run(prog)` 以
  `_loading_module` 标志（save/restore 支持嵌套 use）跳过被载模块自测块——
  `_exec_decl` MechUnit 分支载入中早退（`#：{ }`/`#N：{ }` 一并跳过，
  matha_bootstrap.py:59 同款边界）；VM 编译 use 模块从不执行其自测代码，此为双端一致化。
  影响：compiler_matha/nl_lexer·nl_parser·nl_engine（×en）host [1,1]→[]、
  interp.matha/interp_matha.matha [1,1,8,14,200,10,6]→[8,14,200,10,6]（[1,1] 全部为
  加载 语法器 时泄漏的双跑自测值，主文件自身无 [1] 自测块）。
  **18c 通道收发 host 真化**：`_eval` 新增 ChanExpr（降级三键 dict
  `{"缓冲": [], "容量": buffer_size or 0, "关闭": False}`）与 SendExpr（append 产新
  列表 + `_dict_put` 产新 dict + **具名变量写回**（env + _sync_matha_env）、无名通道
  写回退化值丢弃、求值 True）——与 VM ChanExpr BUILD_DICT / SendExpr append+_dict_put
  +具名 STORE_NAME/无名 POP 逐语义同构（阶段 16 D4 登记的「通道收发静默跳过」随之
  勘误为求值丢弃）；块位收发经 `_exec_stmt_or_expr` 自动路由 `_eval` 生效。
  矩阵：`chan Int` 容量 0/关闭 False 双端、`乙 = 甲 <- 5`→True、双发缓冲 [5,7]、
  无名发送 `(chan Int) <- 5`→True、顶层裸收发副作用静默 []、发送列表值缓冲 [[[1]]]。
  **18d `[1]===[1]` 语句位真化（全中缀回退）**：顶层命令单元（`_parse_command_unit`）
  与表达式位（`_parse_primary` `[` 分支）新增 `_bracket_followed_by_infix`——配对 `]`
  后紧跟中缀运算符且同逻辑行 → 判为列表字面量表达式；模块级常量 `_BRACKET_INFIX_TOKENS`
  （算术/比较/严格相等/逻辑 and·or·&&·||·??/?/位/集合全 infix；**刻意排除** `=`（关系
  相等，`[1] = [1]` 保持诚实 ParseError）、`<-`、`>>`（OP_NEXT/OP_BIT_RSHIFT 链式自有
  处理）、复合赋值、箭头、`|` 管道）；同时补齐 `_parse_primary` 前驱右值集缺失的
  ===/!==/and/or/&&/||/??/?/^、//——此前 `x === [1]` 的 RHS 落入输出行 Output，
  VM 表达式位对其 DUP+OUTPUT 发射而 host 静默（隐性双端分歧），回退后两侧对称 ListLiteral。
  自测块内与跨行 `===` 维持 ParseError（生成代码面与同逻辑行限定，登记边界不动）。
  **自举镜像面**：本轮未触及 VM/compiler/自举镜像（ ChanExpr/SendExpr 早已三端实现、
  解析面修复仅主解析器，matha/lexer·parser·interp·compiler_matha.matha 维持 14a 登记
  边界不动）。**零扰动证明**（HEAD 74aef4b worktree 基线对拍：169 文件语料 host/vm
  sweep 逐文件 diff）——**新增分歧 0**；host 侧变化恰为 13 文件 = 18a/18b 修复面
  （全部向 VM 值收敛）；基线 41 项双端分歧收敛至 31 项（消失的 10 项 = 本轮修复面；
  余 31 项为既有登记缺口：MatchStmt 未编译、领域插件 host 专属符号、bootstrap 链登记
  边界，与基线同集）；4 文件 diff 系环境工件（对象 repr 地址 / worktree 绝对路径）非行为。
  三锁 35 条（`tests/test_semantic_parity_phase18.py`：对拍 24〔18a 模块内自测/绑定
  单次 + 语料 parser.matha [1]/test_compile ×1 共 5 + 18b use 零泄漏/加载 API/嵌套
  标志恢复/语料 compiler_matha [] 共 4 + 18c 通道矩阵 8 + 18d 语句位矩阵 4 + 表达式/
  变量位不动/AST 两侧 ListLiteral 共 7〕+
  闭环 e2e 5〔matha run 真子进程：`[1] === [1]` 吐 True/`!==`/通道缓冲 [5]/use 零泄漏/
  输出行 `[1]` 不受影响〕+ 边界 6〔`=`、自测块内、跨行、`|` 四 ParseError 锁 +
  发送列表值双端 + lexer.matha D3 轻锁〕）；阶段 16 文件
  边界锁 1 条旧形态改锁（`test_list_statement_strict_eq_parse_error` ParseError 锁 →
  双端发射 True 锁，旧锁改锁新形态协议）。
  doc 同步：README 测试文件 140→141；ARCHITECTURE core_py_lines 31,918→31,974
  （+56 = 解释器删递归/标志/通道求值 + 解析器全中缀回退常量与 helper）；
  ast_vm_gap 快照重生成（18c host 新增 ChanExpr/SendExpr 求值 → 矩阵 interp 列
  no→yes 漂移，棘轮复核「阻塞缺口未增加」，`scripts/ast_vm_matrix.py --write`，
  11/11 绿）。
  全量门禁 7257/7257（首跑 1 红项 = ast_vm_gap 快照漂移〔18c host 新增
  ChanExpr/SendExpr 求值 → 矩阵 interp 列 no→yes，预期覆盖提升非回归〕→
  `scripts/ast_vm_matrix.py --write` 重生成、单文件 11/11 绿 → 按协议全量重跑干净：
  tests 7154 + kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 +
  native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7222（17 收官）+ 35（阶段 18 三锁）= 7257。
- **2026-11 阶段 19 收官（双端语义第四片：match/switch 表达式位 + 裸 list body 真化；终端管道态修复；G-5 漏报修复）**：用户拍板
  范围三件全选（AskUserQuestion；**域符号 VM 面未选** = 维持登记不修），设计拍板 match+switch
  一并、裸 list body VM 补链循环（推荐项全采）。
  **19a match/switch 表达式位**（src/mbc/compiler.py `_emit_expr` 补 MatchStmt/SwitchStmt
  分支 → leave_value=True 委托既有语句编译）：语料 13 文件收敛（grammar.matha +
  lifestyle_math/molecular/game_algorithms/game_apps_math/os_concepts/civil/kernel_syscall/
  process_math/emerging_math/crypto_math/utility_math/web_math）；自举镜像
  matha/compiler_matha.matha 早已同构（镜像先行，host 编译器本轮补齐）；语句位 match 本就
  双端支持（_STMT_NODES 回归锁）。
  **19b MechUnit 裸 list body**（`_compile_stmt` list 分支：逐元素编译 + OP.OUTPUT 逐段
  发射链）：`#N：【段】{ }` 组合 body / `#：{ [8] }` 纯块双端一致（MechUnit body 裸 list
  [GenStmt, CodeBlock] 形态锁）；bootstrap_test/v2 vm 侧由「编译拒绝 暂不支持的节点
  list」转为真编译执行——残留分歧 = C 类自举链符号面（use 运行时引擎/词法器，独立 VM
  编译看不见被载模块符号，登记边界）。
  **19c 终端管道态**（matha/term_engine.matha `_执行段` 重写为多语句块 try）：旧形态 =
  else 分支 let 链，段内炸 → 管道结束() 不执行 → 管道态泄漏至下一入口清除兜底；新形态 =
  裸 管道输入(管入) 语句 + try{ let r = _派发段(...) in 管道结束() \n r } catch(e){
  管道结束() \n throw e }——段内出错 catch 清态后重抛，管道态即时回收（13a 旧泄漏锁
  改锁新形态 test_loop_segment_error_cleans_pipe_state）。**块体形态约束（本轮踩界，登记）**：
  ① try 只能落块尾语句位——let 链尾接 try / let 值位 try 双端 ParseError；② 块尾若是
  let-in Binding 整体被 D4 语义当语句丢弃（值 None），「清理 + 返回」必须拆成裸
  管道结束() 语句 + 块尾裸 r；③ 不用 finally = VM finally 无 catch 重抛路径不执行
  thunk（见下）。〔勘误 2026-11 阶段 20：③已修，见阶段 20 收官条目 20e〕
  **finally 双端相反分歧（新登记不修 + 现状锁）〔勘误 2026-11 阶段 20：已修，见阶段 20
  收官条目 20e；下文为修复前形态存档〕**：try-finally 无 catch 时 host **吞错
  继续**（src/interp.py `_exec_try` catch_var None → catch_block None → `_exec_stmt(None)`
  静默 no-op——错误不传播、finally 副作用照跑、执行继续），VM **重抛但跳过 finally
  thunk**（compiler OP.RAISE 先于 finally thunk 发射）。两形态相反、语料零命中（finally
  仅自举镜像 try 语义实现内部使用）；现状锁 `test_try_finally_no_catch_divergence` +
  正常/caught 路径 parity 锁（finally 在无异常/有 catch 路径双端一致）。
  **19d G-5 真修**（src/matha_growth.py grow()）：`applied_total` 累加器——闸门通过后
  extend（回退轮改写未前传不计入）、空转轮如实不加条目，返回报告聚合全部迭代规则；
  第八节 G-5 条目勘误为已修，锁改 `TestG5AppliedRulesAggregated`。
  **零扰动证明**（HEAD 46d727e worktree 基线对拍：169 文件语料 host/vm sweep 逐文件
  diff）：基线 31 项分歧 → 18 项；收敛 13 = 恰好 19a 修复面集；**新增分歧 0**；6 项值
  变化全良性（bootstrap_test/v2 = 19b 报错形态变化；4 examples 文件 = worktree 路径/
  对象地址工件）。余 18 项为既有登记缺口（域符号 VM 面〔本轮拍板不修〕、自举链 C 类
  符号面、match 无匹配/守卫绑定名求值序分歧、host 专属域符号、compiler_matha/nl_*/
  parser 自测块存量等）。
  三锁 30 条净增（`tests/test_semantic_parity_phase19.py` 新档 29：19a match 8 + switch 3 +
  19b 4 + e2e 3 + 边界/登记锁 5 + 19c 管道态 4 + finally 2；growth `TestG5` 净 +1；13a
  旧泄漏锁 1:1 改锁新形态）。**登记分歧现状锁（防回潮面不放松）〔勘误 2026-11 阶段 20：
  match 两分歧已修（无匹配 RAISE_MATCH 真化 + 守卫序 guard-first 同构），见阶段 20 收官
  条目 20a/20c；switch 表达式位解析拒绝维持登记〕**：match 无匹配表达式位
  host 报「match 无匹配分支」/VM 表达式位求值 None、语句位 VM 静默继续；守卫绑定名求值序
  host 先守卫（绑定名不可见 → 未定义变量）/VM 先模式绑定（守卫可引用）；switch 表达式位
  ParseError（VM `_emit_expr` SwitchStmt 分支为与 host 对称的防御支持）。
  【阶段 21 勘误：switch 表达式位解析拒绝已由 21c 真化——宿主 `_parse_primary` 与镜像
  `解析主要` 均接受 switch（语句位分派不受影响），表达式位双端求值一致
  （tests/test_semantic_parity_phase21.py）。】
  doc 同步：README 测试文件 141→142；ARCHITECTURE core_py_lines 31,974→31,990（+16 =
  compiler match/switch/list body + growth 聚合）；ast_vm_gap 快照重生成（term_engine try
  形态进语料 → used_in 漂移，`scripts/ast_vm_matrix.py --write`，11/11 绿）。
  全量门禁 7287/7287（首跑 7285/7287，2 红 = ast_vm_gap 快照漂移〔预期语料 used_in 漂移
  非回归〕→ 重生成 → 按协议全量重跑干净：tests 7184 + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7257（18 收官）+ 30（phase19 新档 29 + growth 净 +1）= 7287。
- **2026-11 阶段 20 收官（match 分歧收口五面同构 + finally 双端分歧全链真修）**：用户拍板
  范围两件（match 分歧收口 + finally 双端分歧真修），设计拍板三项推荐全采：对齐方向 =
  编译面→解释面（解释器为基准不动语义面）、VM 无匹配消息 = 新 opcode 值渲染、finally
  修复面 = 全族全链。
  **20a 守卫求值序收口（编译面→解释面）**：host compiler `_emit_match` 与自举镜像
  `_发射match尾部` 由「先模式绑定后守卫」改为 guard-first——守卫先于模式绑定求值，守卫
  引用绑定名双端一致报「未定义变量 'x'」（对齐 interp `_eval_match`；旧 VM 面
  bind-then-guard 守卫可引用绑定名输出「大」的错误形态除名）；镜像 `_发射match尾部` bc
  线程 typo 同修（`bc3` 自引用未绑定 → 改 `bc3` 前值）。旧锁改锁新形态两处：m18
  [guard]（test_mbc_bootstrap.py，守卫改引外层参数 n，路由覆盖保留）+ M1
  `test_match_guard_filters_branch`（test_m1_nodes.py 同款）；「守卫引用绑定名 → 双端
  同错」形态由 phase20 专项锁 + phase19 收口后轻锁封死。
  **20b 通配兜底动态化**：通配 `_` 分支不再编译期静态化——守卫通过的通配动态记录兜底
  tag（marker 槽 match_d/default_t record-if-unset），循环内后续显式分支照测（后显式
  分支优先于先记录通配，对齐解释面 default_branch「循环结束后才生效」语义），循环尾
  tag 分派链统一出口；语料型多守卫通配矩阵锁（lifestyle_math 分档形态）。
  **20c 无匹配真化（新 opcode RAISE_MATCH 0x63）**：主/镜像编译器 match 尾部统一发射
  `load scrutinee; RAISE_MATCH`，VM 处理器按 interp._fmt 渲染被匹配值（字符串带引号截
  60 / >4 列表 [list len=N] / >6 字典 {dict keys=[...]} 原始键）后抛「match 无匹配分支:
  <值>」——VM 表达式位求值 None / 语句位静默继续两形态除名，双端三形态（表达式位/
  语句位/catch 接获含完整前缀消息）逐字一致。
  **20d 原生 RAISE_MATCH（opcode-surface 硬门禁合规）**：src/mbc/native.py err_match_nomsg
  静态串 + opcode 分派 + match_render 运行时（堆指针判定 + STR/LIST/DICT 两遍 print_repr
  repr 渲染 / 标量 value_to_str → str_concat 前缀 → raise_rt）；未捕获路径 stderr
  「match 无匹配分支: <值>」+ exit 1。**登记差异（现状锁）**：原生渲染无 60 字符截断与
  >4/>6 缩略形（完整 [1, 2, 3, 4, 5, 6]）、字典键走 repr、闭包值原样——
  `test_native_render_delta_long_list` 显式登记防静默收敛/漂移。
  **20e finally 全链真修（19 收官条目「登记不修」勘误为已修）**：host `_exec_try` 无
  catch 不再吞错（catch_block None → 重抛，finally 先执行）；VM `_emit_try_stmt` 无
  catch 路径 fin thunk 先执行后重抛、catch 再抛路径同构；自举镜像 interp.matha `执行try`
  两路径「先 finally 后重抛」（catch 体经 调用捕获 受保护）+ compiler_matha.matha
  `_发射try` 同构（无变量 catch CALL 1 = 宿主 `_invoke` 丢参契约）。19c 引擎弃 finally
  改 catch-清态-重抛的形态保留（保守设计不动），其理由③勘误为已修。镜像 parser
  `catch{}` 歧义（无 catch ≡ 显式空 catch 同形态 → 镜像面按重抛，与宿主 catch_block
  None/空 CodeBlock 区分不同源）维持登记边界不修。
  【阶段 21 勘误：该歧义已由 21c 消解——镜像 parser `解析try语句` 无 catch 产出哨兵
  捕获体=null（显式空 catch 仍为 `做Program([])`，二者可区分），镜像 interp `执行try`
  null→重抛/空 catch→吞错继续，镜像 compiler `_发射try` 同构（null→先 finally 后
  RAISE、空 catch→空体 thunk 走捕获路径），stage2≡stage3 字节级同构锁
  （tests/test_semantic_parity_phase21.py）。】
  **20f 镜像 try 缺口形态锁（M21）**：M16 全部用例带 catch 变量，无变量 catch 与无
  catch+finally 重抛两形态此前自举链路无锁——新增三面锁（host 基准 / stage2≡stage3
  字节级 / stage3 执行）：无变量 catch 函数体、无变量 catch 顶层输出、嵌套 finally 重抛
  外层接获 [9, "1"]。
  **零扰动证明**（HEAD b8238bd worktree 基线对拍：163 跟踪语料 host/vm sweep 逐文件
  diff）：语义面零变化，唯一 4 处差异全为良性工件（08_auto_optimize 对象地址 +
  10/11/12 examples worktree 绝对路径，与阶段 19 同批）；matha/generated/ 6 个未跟踪
  生成文件不入 worktree 不参与对拍；语料守卫均不引用绑定名、finally 语料零命中（仅
  自举镜像 try 语义实现内部使用）——两收口对语料零扰动。
  三锁 38 条净增（`tests/test_semantic_parity_phase20.py` 新档 31：守卫序 4 + 动态兜底
  4 + 无匹配消息 8 + finally parity 7 + e2e 3 + 原生 3 + 边界 2；`test_mbc_bootstrap.py`
  M21 +9；phase19 文件 2 条移交专项锁 −2；m18/m1 旧锁改锁 ±0）。门禁 7327/7327（首跑
  7326/7327，1 红 = M1 test_match_guard_filters_branch 旧锁编码 bind-then-guard 形态 →
  按旧锁改锁新形态协议改锁 → 按协议全量重跑干净：tests 7224 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入
  分母）。算术闭合：7287（19 收官）+ 31 + 9 − 2 = 7327。
  doc 同步：README 测试文件 142→143；ARCHITECTURE core_py_lines 31,990→32,166（+176 =
  编译器 match 动态兜底/守卫先求值/try 三路径重抛 + VM RAISE_MATCH 处理器 + 原生
  match_render 渲染运行时 + 解释器无 catch 重抛 + opcode 登记）；ast_vm_gap 快照重生成
  （RAISE_MATCH 进 opcode surface，指令码 34 VM 34 / native 34）。
- **2026-11 阶段 21 收官（插件符号 VM 面真化 + 编译面 use 解析 + 镜像 catch{} 歧义消解与
  switch 表达式位）**：用户拍板范围三件全选（21a 插件符号 VM 面真化 / 21b 编译面 use 解析
  / 21c 镜像 parser catch{} 歧义 + switch 表达式位），设计拍板四项推荐全采。
  **摸底勘误**：21 摸底「生成_×6 语料零使用」不成立——examples/10_web_app.matha 用
  生成_网页、11_desktop.matha 用 生成_桌面，capability 插件按门面对拍标准扩至 12 符号
  （自主_调试/自主_优化/自主_成长/资源_加载/资源_成长/软件_构建 + 生成_网页/桌面/服务/
  系统/游戏/建模）；资源_列表/资源_读取 仍语料零使用，保持登记边界（插件面未覆盖）。
  **21a 插件符号 VM 面真化**：`src/domains/capability.py` 能力插件（清单注册 12 符号）；
  宿主面仍由 src.interp 内建表直挂（直挂优先，宿主面零改动）；VM 面官方入口
  `exec_api._wire_plugin_runtime` 注入领域解析器（resolver 物化面）+ 效果面胶水
  `plugin_api.make_capability_runtime` → `capability.make_runtime`（资源_加载/资源_成长
  把资源函数编译进**同一个运行中 VM**，与宿主面「合并进运行中的解释器」同构；setdefault
  不覆盖程序自定义同名函数）；跨模块常量池：VM 分派按帧取常量池（`Frame.consts` /
  `MFunction.consts`，None=与模块共享）——运行期插件合并进运行中 VM 的函数帧携带来源
  模块池，常量下标不再读到宿主模块的错位值；解析_JSON 双面单一实现
  （`src/kernel/json_builtin.py`，宿主 BUILTINS 与 VM `_default_builtins` 同源）。
  两工厂均为**惰性跳板**（构造零 import，首次调用才经解析器动态装入插件；
  plugin_api.py 静态 `src.domains` 导入零容忍，AST 扫描锁在场）——eval/auto 的
  「零领域急切加载」语义不因注入面破坏（首跑门禁 5 红真修：plugin_contract×3 +
  ai_framework/library_basics 急切加载×2）；柯里化定点：`资源_成长("计算动能")("core")("")`
  首调经跳板物化、链式后续命中真 curry3 Partial（跳板转发 *args），生成
  matha/library/core/计算动能.matha 与既有生成件同类（已随本片纳入版本控制）。
  **21b 编译面 use 解析（自举链收口）**：编译器 use 发射 `CALL 加载模块`（宿主注入的
  插件层胶水把被 use 模块函数/枚举/模块级 let **平铺合并**进同一个运行中 VM + 命名空间
  绑定，幂等）；被 use 模块已内联在同一程序（自举链多文件合并编译：宿主 `_inline_modules`
  预扫 + 镜像 `_收集模块名/_名单含/_清内联导入` 三件）时不发射——符号就在本模块全局域，
  加载调用多余且会二次合并；`GET_ATTR` 补宿主 PathExpr「dict 缺失成员退回内建表」同构
  回退（标准库.len 一类内建透传）；自举镜像 compiler_matha.matha 同构（use 编译双端
  一致）；裸 VM（不经官方入口）遇 use 诚实报错「未定义变量 '加载模块'」——错误名由
  「首个 use 符号」前移到「加载器名」，use 编译期 no-op 时代的裸 VM 拒绝边界就此除名，
  官方门面（exec_api 注入加载器）真跑到收敛。
  **21c 镜像 catch{} 歧义消解 + switch 表达式位**：镜像 parser `解析try语句` 无 catch
  产出哨兵 捕获体=null（显式空 catch 仍为 `做Program([])`，二者可区分）；镜像 interp
  `执行try`：null → 重抛（对齐宿主无 catch 路径）、空 catch → 吞错继续（对齐宿主 catch
  空体语义）；镜像 compiler_matha.matha `_发射try`：null → 先 finally 后 RAISE、
  空 catch → 空体 thunk 照常编译走捕获路径；stage2≡stage3 字节级同构锁。switch 表达式位：
  宿主 `_parse_primary` 与镜像 `解析主要` 接受 switch（语句位分派不受影响）——interp
  `_eval_switch_expr` 与编译器 `_emit_expr` SwitchStmt 分支（阶段 19a）早已就绪，本轮只补
  双端解析。
  **登记不修五条（现状锁）**：①裸 VM 不承载插件符号（自主_* 等未定义名）与
  plugins="off" 官方入口不注入——与原生 exe「不承载插件符号」同一架构哲学；
  ②@：【加载领域】 的 require() 语义按清单顺序覆盖 target（会以解析器物化面覆盖注入的
  效果面胶水；宿主内建表直挂同理被插件表覆盖；语料零命中，登记现状）；③镜像解释器重抛
  路径丢弃环境链（immutable env 经 错误 通道不可携带）+ finally 内建调用（原地设置 等）
  在镜像解释器面的协议缺口；④host-ERR 链三文件双面失败形态（bootstrap_full_test：host
  未定义变量 '不折叠' 挂更早不变、VM 面 HEAD err 未定义变量 'tokenize' → 真化后跑通到底
  21 输出越过宿主面；bootstrap_matha：host 属性访问失败 str.类型 不变、VM 面 HEAD err
  未定义变量 '自举加载器' → TypeError len(Partial)；bootstrap_test：host 不可调用的值
  不变、VM 面 HEAD err 未定义变量 '词法器' → KeyError: 0——VM 面新形态为更深处的链内
  分歧，与 use 编译面正交）；⑤match 表达式位：宿主被字典花括号歧义劫持 ParseError
  「期望 }」、镜像 `解析主要` 接受 match——双解析器潜分歧维持登记。
  **零扰动证明**（HEAD 9803068 worktree 基线对拍：222 语料 host/vm 双面 sweep）：201
  文件逐字节相同；21 差异全归因——13 文件插件符号收敛（12 examples + .trae/demo_calc：
  VM 面 HEAD err 未定义变量 自主_*/资源_*/软件_构建 → ok，21a 面）；4 文件 use 解析收敛
  （bootstrap_full_test、bootstrap_test_v2、matha/interp.matha、matha/interp_matha.matha：
  VM 面 HEAD err 未定义变量 首 use 符号 → ok，21b 面）；2 文件 err→err 更深（
  bootstrap_matha/bootstrap_test，登记边界④）；2 文件已知非确定性（examples/ai/
  data_pipeline 对象 repr 地址、neural_network 随机初始化，同树双跑复验即漂移，与本片
  正交）。host 面 222 语料零变化。
  **旧锁改锁新形态七处（均带勘误注明）**：phase18 四条（parser.matha/use 零泄漏/嵌套
  use/compiler_matha 的旧 vm 断言是 use 编译期 no-op 时代影子形态 → pytest.raises 锁
  裸 VM「未定义变量 '加载模块'」诚实拒绝边界，host 面语义全保留）+ phase19 三条（switch
  表达式位「解析拒绝」登记锁 → 匹配形态双端 [10] 真化锁，无匹配无 default → None 形态
  仍由 phase21 SW_SRC 锁定；两 bootstrap 文件旧 vm 断言 运行时引擎/词法器 → 未定义变量
  '加载模块'）。
  三锁 69 条净增（`tests/test_capability_vm_phase21.py` 新档 28〔门面对拍 + 注入面
  闭环 + resolver 物化面 + 边界〕；`tests/test_use_compile_phase21.py` 新档 17〔发射/
  内联抑制 + 胶水真加载/幂等/命名空间/枚举/let 物化 + 裸 VM 拒绝 + 链文件边界〕；
  `tests/test_semantic_parity_phase21.py` 新档 24〔catch 形状二分 + interp/compiler
  双面同构 + stage2≡stage3 + switch 表达式位 + match 登记〕）+ json_builtin 内核化使
  `test_core_never_imports_plugin_contracts` 参数化 +1。门禁 7397/7397（首跑 7380/7397，
  17 红三类全落定：旧锁改锁 7〔phase18×4 + phase19×3〕+ plugin_api 懒跳板真修 5
  〔plugin_contract×3 + ai_framework/library_basics 急切加载×2——静态 src.domains 导入
  改 resolver 惰性物化〕+ doc 数字漂移 5〔领域插件 82→83、语料 169→170、core_py_lines、
  CHANGELOG token〕→ 按协议全量重跑干净：tests 7294 + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7327（20 收官）+ 69 + 1 = 7397。ast_vm_gap 快照重生成（计算动能.matha 进
  语料，corpus_files 216→217，used_in 漂移按协议 `scripts/ast_vm_matrix.py --write`）。
  doc 同步：README 测试文件 143→146、领域插件 82→83（src/domains/ 84→85 个 .py）、
  语料 169→170；ARCHITECTURE core_py_lines 32,166→32,285（+119 = VM Frame functions 表
  与 MAKE_CLOSURE 逐帧函数表解析、GET_ATTR 内建名回退、解析器 switch 表达式位、
  capability/json_builtin 插件移植胶水与 exec_api use 加载器注入面）；CHANGELOG 领域
  插件 82→83；勘误三处：阶段 16 收官条目 use no-op 影子形态（21b）、阶段 19 收官条目
  switch 解析拒绝（21c 已真化）、阶段 20 收官条目 catch{} 歧义维持登记（21c 已消解）。
- **2026-11 阶段 22 收官（全面清算：假成功清算 + 孤儿删除/注册面清理 + 语料崩溃与裸赋值
  分歧真化）**：用户拍板范围三件全选（① 假成功清算 ② 孤儿删除 + 注册面死条目清理
  ③ 语料崩溃 + 裸赋值分歧真化），「只登记不修」候选被否。
  **22a 假成功清算**：门面/引擎能力边界诚实化——database_sql（SQL 文本解析仅表名 +
  WHERE 子句；UPDATE/DELETE 文本执行、savepoint、真实事务隔离未实现一律显式拒绝，
  不再返回假 affected_rows=1 或假传感器数据）、device_driver（GPU 着色器编译绘制/
  网卡收发/SMART 传感器读数/基类寄存器读写显式拒绝，簿记面保留）、robotics_full/
  game_engine_extended/geospatial_full/audio_video(+full)/compiler_backend/
  offline/mobile_api_client 同批（能力边界写入模块 docstring，未实现面 raise）；
  吞错日志清算：`src/kernel/time_builtin.py` run_pending_tasks except→stderr 全量
  记录不再静默吞、`src/matha_main.py` _cmd_absorb except→打印失败、_load_domain 删
  adapt_module try 静默回退（计数走 `__all__`/vars 如实）、_cmd_device_driver 演示
  面假读数（SMART 假健康度、无结果 nic.send 打印）清除。
  **22b 孤儿删除（用户批准两轮复核）**：20 个 src 孤儿文件 ≈8.4k 行
  （ai_assistant_desktop/server、ast_nodes.py.broken、collaboration、compiler/ir、
  dynamics 三件、linkage、nl_definition/nl_pipeline/nl_semantic/nl_to_formula、
  parser_pool、plugins/ffi_sdk、plugins/legacy_mir_vm、symbol_registry、
  tools/perf_profiler、typesystem_v2——全仓零消费或不可达）；5 个孤儿测试档删除
  （collab_enhanced 23 + ffi_sdk_honest 21 + nl_pipeline 39 + nl_pipeline_execution
  24 + symbol_registry 8 = 115 条）+ 6 个在档测试退役 571 条
  （plugin_algebra_dynamics −521〔被删插件契约面〕、formula_system −23〔dynamics
  假语义〕、ai_servers_smoke −14、rust_python_features −7〔typesystem_v2〕、
  tools_enhanced −5、unified_layers −1）——**退役合计 686 条**。
  **22b-2 注册面死条目清理**：`src/domains/registry.py` 清掉模块未实际导出的函数名
  死清单（178 行，模块真实 `__all__` 对齐）；`src/__init__.py` MiroptPass 死软项
  除名；matha.spec `src.stdlib.probability_stats` 死 hiddenimport 除名；dep_audit
  LEGACY_PREFIXES 除名 src.vm/m3v_vm（11/22b 已删，附注在案）；
  matha/stdlib_symbols.matha 数据来源注释对齐（专属宿主工具已删）。
  **22c 裸赋值分歧真化**：`src/interp.py` _exec_stmt 补语句位
  `BinaryOp("=")` + 左值 Variable → 求值右值绑定 env + _sync_matha_env（对齐 VM
  _emit_block is_assign 面；块尾值位不覆盖，仍比较，与 VM
  `is_assign and not (last and leave_last)` 一致）；双镜像同步
  matha/interp.matha + matha/interp_matha.matha 各加 语句位赋值或表达式
  helper（if/then/else 外层形态——镜像解析器函数体首 `(ident.` 落 lambda 参数
  前瞻，双重括号同样不可用）；35 语料修复（examples/04_pipeline + 34 个
  knowledge/resource 文件）宿主/VM 双面 err→ok。
  **旧锁改锁三处（均为 22c 直接面，勘误注明）**：phase19 os_concepts
  「双端同错同消息（未定义变量 'else'）」→ 双端干净同值 []（语料修复后前提消失）；
  test_scoped_blocks test_off_block_binding_is_equality「关闭态块语句 `y = x + 1`
  为等于比较 → y 未定义报错」→ 双端绑定 [8]；test_cli_features
  test_noncore_module_gated_by_flag「开关关时遗留解释器把 `s = 0` 当比较报
  未定义变量」→ 两开关下解释器面均 [10]。后两处旧锁锁的正是裸赋值宿主/VM 分歧的
  宿主半边（旧 docstring 自认「解释器把它当比较，主线编译器把它当赋值」），22c
  真化消解分歧后按勘误协议改锁新形态；SCOPED_BLOCKS 开关对裸赋值形态不再构成
  行为差异，仅存解析层形状差（Binding vs BinaryOp，原形状锁保留在场）。
  三锁 59 条（`tests/test_semantic_parity_phase22.py`：_ASSIGN_CASES 4 形态
  参数化 ×host/vm〔try 块/lambda 块/while/if〕+ 重绑定 + 块尾值位比较边界双面 +
  AST 形态锁〔顶层 try=Binding、lambda 体 try=BinaryOp〕+ 双镜像锁
  （预绑定函数 标记区分两解释器镜像 + 语句位赋值或表达式 在场断言）+
  公式 DSL 边界（dynamics.matha parse 干净、运行时公式面 MathaRuntimeError 登记）+
  _REPAIRED 36 文件 parse-clean 参数化 + pipeline 引号指令值）。
  **零扰动证明**（HEAD 78535f1 worktree 基线对拍：223 语料 host/vm 双面 sweep）：
  35 修复面 err→ok（04_pipeline + 34 knowledge/resource）+ 4 个 SCOPED_BLOCKS
  黄金 host err→ok〔探针无旗标伪影——黄金 runner 按 manifest features 施旗标，
  权威面黄金 39/39 在场〕+ dynamics.matha err→err 深层（ParseError L365 →
  未定义变量 '公式'，公式系统运行时解释面缺位，登记不修）+ 6 项良性工件
  （对象地址 ×3、随机浮点、worktree 绝对路径 ×2）+ 6 个基线缺失未跟踪生成件
  （matha/generated，21 收官同批）；tracked 语料 170/217 逐位相同，VM 面零回归。
  **登记不修六条（现状锁）**：①dynamics.matha 公式 DSL 运行时面（解析已修，
  运行时 公式 未定义——公式系统解释面缺位，语料资源面非主线）；②
  bootstrap_full_test 宿主面闭包作用域首错名 '不折叠'（VM 面已跑通全程，宿主面
  闭包绑定序更深分歧维持登记）；③se_native sys_env 预览 scratch 面；④SCOPED_BLOCKS
  黄金用例（06/08/11/17）依赖 manifest features 施旗标，无旗标直跑 host 面报错
  为探针伪影、非产品路径；⑤interp_matha 镜像无 try 支持（顶层 try 沉默回退
  Python 解释器，既有缺口）；⑥interp.matha 镜像无块表达式求值（未知表达式类型：
  程序，既有缺口）。
  **门禁 6770/6770**（三跑：首跑 6767/6770 三红 = 上述旧锁改锁三处〔22c 真化翻转
  三处旧锁前提〕→ 改锁 → 三跑干净：tests 6667 + kernel_purity 14 + ast_vm_gap 11 +
  golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：7294（21 收官 tests）− 686（22b 退役）+ 59（22 三锁）= 6667。
  doc 同步：README 测试文件 146→142（22b 删 5 孤儿测试档 + 22 新增三锁档）；
  ARCHITECTURE core_py_lines 32,285→32,287（+2 = time_builtin 吞错日志诚实化，
  src/interp.py 不计入 core 体量定义）；CHANGELOG 内核外工具插件 9→7
  （ffi_sdk/legacy_mir_vm 删除）；ast_vm_gap 快照重生成（语料修复 used_in 漂移
  按协议 `scripts/ast_vm_matrix.py --write`）；KNOWN_ISSUES 本条目 + 测试退役明细。
- **2026-11 阶段 23 收官（臃肿/性能清算 + 结构收敛 + 统一扩展/升级系统；不删功能不删插件
  硬约束下）**：用户拍板范围三件全选（性能：内建惰性化 + CLI 启动瘦身 + 解析缓存 opt-in；
  结构：matha_main 命令表化；扩展：统一扩展协议 + `matha ext` CLI + 四面接入 + 用户扩展包）。
  **23a 内建惰性化（Interpreter 构造瘦身）**：`src/kernel/lazy_kernel.py` 新增 LazyKernelFn
  惰性跳板（注册即薄对象、首次调用才 import 对应 kernel 模块物化真实现），`src/interp.py`
  模块级 BUILTINS 与 `src/mbc/vm.py::_default_builtins()` 的 终端/时间/JSON 三段内核内建改
  lazy_section 注册（宿主面 BUILTINS 常驻段收缩——time 段仅存于 VM defaults 所用的
  register_kernel_builtins，双面各自 lazy 全集不同属既定架构分工）；`callable()` 是双面唯一
  的函数性判定位（自检/内建表扫描不改）。import 权重探针（`python -X importtime -c "import
  src.interp"`，单轮）：全链 261ms→199ms。行为面零变化：惰性物化真值锁（VM 获取时间戳 /
  宿主 解析_JSON）+ 旧锁 test_parse_json_single_source_both_faces 改锁 LazyKernelFn 形态 +
  单参行为同值（勘误：23a 靶向跑时未察觉该旧锁，23d 回归面揪出，属惰性化的合法影子形态）。
  **23b features 单源诚实化 + CLI 命令表化**：`src/features.py` DEFAULTS 单源
  （SCOPED_BLOCKS/STACK_ENGINE/INLINE_CACHE/PARSE_CACHE——INLINE_CACHE 文档面与实际一致，
  默认开，不再两处漂移），known_states() 单一读取口 + state_tuple()/parse_cache() 派生；
  `src/custom_ops.py` 版本计数 version()（register/clear 递增）；`src/matha_main.py` 30 个
  工具子命令收敛为 _tool_cmds 命令表循环注册 + 抽出 _build_parser()（main 只解析分发，
  注册点单点；`tests/test_extension_system_phase23.py` 命令表 parity 锁）。
  **23c 解析缓存 opt-in**：`src/parser.py::parse()` 加 PARSE_CACHE 特性开关（默认关），
  LRU 32 条，键 = (source, features.state_tuple(), custom_ops.version())——AST 只读消费
  （grep 证实无节点改写）故命中共享树安全；两个真实输入面（features 翻转 / custom_ops
  注册）精确失效；默认路径零影响（开关关不进缓存分支）。探针级实测（单轮，非第六节量具
  口径、不构成性能背书）：stdlib.matha 全文冷解析 112ms → 命中 0.05ms。
  **23d 统一扩展/升级系统**：新模块 `src/extensions.py`（~340 行）单一协议——四类扩展
  domain/feature/package/terminal 统一 ExtensionInfo（version/enabled/source/installed_at），
  状态文件 `.matha/extensions.json`（protocol_version 1；损坏/降版本/无 state 键诚实拒绝）；
  CLI `matha ext list/enable/disable/install/upgrade`（enable/disable 对 package 关闭——包
  启停经自身 manifest 单源，见下）；apply_state 在 _cmd_run/_cmd_eval/_cmd_repl 执行前应用
  （无状态文件零开销）。四面真启停（非表面）：①domain = PluginResolver.unregister / 公开
  reload()（unregister 掉的插件经 reload 从清单找回）+ 幂等门 _manifest_has_plugin（清单内
  但未注册 = 幂等跳过；清单外 = 诚实拒绝；exec_api 实测热力学停用后 输出(R_气体常数)
  未定义）；②feature = set_feature 直通；③package = 写入包自身 manifest.json "enabled"
  字段（单源），内核 use 回退 `_package_module_source` 读包 manifest（cwd + 仓库根
  `.matha_packages/`，entry 取清单 "entry" 否则 `<名>.matha`）——停用包 use 诚实失败，
  内核只读包内元数据不读 CLI 状态；④terminal = 状态文件 .msh 条目 REPL 启动自动执行
  （`_autorun_extensions`，跳过 legacy 文件名，缺文件如实打印）+ legacy
  matha_term_extensions.msh 原路径保留（_run_msh_lines 共享执行器）。install：目录（≥1
  .matha，清单含 enabled/source/installed_at）或注册表包名（MathaPackage().install）；
  upgrade：本地源重装按源版本判「已最新/old→new」。三锁 31 条
  （`tests/test_extension_system_phase23.py`：features 单源 / LazyKernelFn 物化 / import
  权重子进程锁（heavy: []）/ 缓存开关·命中·双输入面失效·LRU 上限·共享树 / 协议形状 /
  状态校验 / apply_state 四面 / domain 真启停+幂等+未知拒绝 / package 真盘安装·use→42·
  停用·内建优先·升级 / terminal 执行面 / CLI ext 全动作 / 命令表 parity / matha features
  4 开关）。
  **零扰动证明**（23c+23d 前后 164 语料 host/vm 双面 sweep）：1 差异 =
  08_auto_optimize 对象地址（已登记良性工件）。
  **登记不修两条（现状锁）**：①CLI 启动地板——python 启动 ~89ms + stdlib（logging
  113ms，Python 3.14 固定成本）+ argparse + 子进程 spawn，探针实测 `matha features`
  ~288ms / `run stdlib.matha` ~514ms / `eval` ~405ms，≤200ms 目标在当前解释器架构不可达
  （native exe 是唯一出口，另立片；探针级实测非量具口径）；②终端 注册命令
  matha_term_registry.txt（12e 引擎内注册表，matha/term_engine.matha 自读）不在 ext
  统一面——引擎自身读 txt，ext 状态文件不拦截；登记范围边界，如需统一另立片。
  **门禁 6801/6801**（首跑即净：tests 6698 + kernel_purity 14 + ast_vm_gap 11 + golden 39 +
  dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。算术闭合：6770（22
  收官）+ 31（23 三锁）= 6801。doc 同步：README 测试文件 142→143 + 新增 `matha ext`
  用法节；ARCHITECTURE core_py_lines 32,287→32,439（+152 = 23a lazy_kernel 惰性面 +
  interp/vm 注册改造 + 23b features 派生 + 23c parser 缓存 + custom_ops 版本 + 23d
  extensions 协议模块 + matha_main 命令表化 + matha_term autorun 面）；KNOWN_ISSUES 本条目。
- **2026-11 阶段 24 收官（缺陷修复：资源库代码化 + 十项新能力域双面真化）**：用户拍板
  范围四件全选（① 资源库代码化=全量代码化 ② 动态解析=语言级动态求值 ③ 媒体=
  PNG+SVG+GIF ④ 单片机=工具链检测真烧录）；硬性缺陷「Matha 资源库必须可以当代码
  使用/调用/编程」由 24a 落地。
  **24a 资源库全量代码化（缺陷修复）**：matha/library/ 资源文件全量补 module 声明
  可 use 可调用（宿主 _library_module_source 三级解析 matha/ → 安装包
  → 资源库 + src/library.py 资源索引 _CN2FILE 映射；VM 编译器 +3 行——
  模块同名冲突（module X { func X }）命名空间绑定不发射，平面函数可调用面优先，
  与宿主 env 同规则）；.matha_packages/arithmetic 落真模块 arithmetic.matha +
  manifest 启用；tests/test_library_as_code_phase24.py 43 条（use 可达/调用/编程
  双面 + 资源索引计数锁 19 条起步后随 24h 增至 21）。
  **24b 画布域 + 图片生成输出**：src/domains/graphics_engine.py 画布域真化——
  PNG（纯标准库 zlib+CRC 真编码）/SVG/PPM 三格式生成与 文本真落盘 输出；
  tests/test_graphics_canvas_phase24.py 28 条（字节级编码对拍 + 落盘闭环）。
  **24c 视频生成输出**：GIF89a 纯标准库真编码（帧序列 → 逻辑屏/色表/LZW 压缩
  块级字节真产物）；tests/test_gif_video_phase24.py 21 条（GIF 头/块结构/LZW
  字节对拍）。
  **24d 动态解析（语言级动态求值双面）**：host interp `_b_dynamic_eval`
  （parse→decls 依 run() 同序注册执行、尾值 `_eval`，绑定持久落共享 env）+ VM
  `_make_dynamic_eval`（尾值包装哨兵零参 FuncDef 编译进嵌套 VM、
  nested.globals = vm.globals 对象共享、跨模块 fn.consts/fn.functions 钉池、
  尾值经 globals.pop 哨兵 invoke_value 取回零污染）+68 行；tests/
  test_dynamic_eval_phase24.py 27 条（双面对拍 + 绑定持久 + 跨模块钉池）。
  **24e 建模仿真**：src/domains/simulation.py 仿真_欧拉/仿真_龙格库塔 数值积分
  （导函数回调绑定运行本体 invoke_value，双面同名协议；exec_api
  make_simulation_runtime 惰性注入 +4 行）；tests/test_simulation_phase24.py
  29 条（RK4 y'=-y n=1000 收敛 exp(-2) 1e-9 / Euler 5e-3 手算对拍 + 回调面）。
  **24f 单片机面**：src/domains/mcu.py 六符号——图纸（SVG 电路图真渲染）、
  编程（Arduino C 真代码生成：pinMode/digitalWrite/analogWrite/delay）、
  控制（载荷归一化 matha-mcu-ctl/1 + 串口实时收发显式拒绝）、烧录（工具链真
  检测 shutil.which：avrdude/st-flash/esptool/openocd 按板族路由 uno/nano/
  mega/stm32/esp32/rp2040 → 真 subprocess；工具缺失/hex 缺失/退出码非零均
  显式拒绝）、驱动（GPIO-UART-I2C-SPI-PWM 五类模板）、写入（文本真落盘）；
  tests/test_mcu_phase24.py 41 条（C 代码形态对拍 + 可注入 argv 工具链测试面 +
  显式拒绝矩阵）。
  **24g 热启动与运行（mtime 热重载双面）**：host _b_hot_start/_b_hot_reload
  （热启动=装载+mtime 快照 self._hot_mtimes；热重载=变更检测重装载，覆盖既有
  定义；未热启动/源文件被删/纯文本面均显式拒绝；被载模块自测块不执行）+ VM
  capability make_hotreload_runtime 惰性注入 +5 行（消息常量与宿主同源）；
  tests/test_hotreload_phase24.py 16 条（双面对拍 + 单运行内自改自重载 + 诚实
  拒绝 + 装配面快照）。
  **24h 资源库新能力模块（纯 Matha 组合层）**：matha/library/simulation/
  建模仿真.matha（双法对比/步长扫描/轨迹抽样——函数体块尾禁止裸列表字面量约束
  写入 docstring）+ matha/library/mcu/单片机.matha（闪灯程序/闪灯图纸/呼吸灯
  斜坡/控制载荷）并入资源索引（19→21 条）；tests/test_library_capability_
  phase24.py 16 条（库函数双面对拍 + 非_PWM 引脚双面诚实拒绝）。
  **登记不修六条（现状锁）**：①VM 面热重载快照生命周期=单次运行（跨运行如实报
  「尚未热启动」——宿主面才跨 run() 持久，test_vm_snapshot_lifecycle_is_per_run
  锁双面相反形态）；②VM 面文件 I/O 内建名不对称（_write_file 有、读文件缺——
  单运行内自改自重载 VM 面走 _write_file，读侧缺口登记）；③单片机串口实时收发
  显式拒绝（纯标准库无串口传输，ctypes 为内核红线——串口开始/打印 仅进 C 代码
  生成与控制载荷，不假收发）；④.hex 编译需外部工具链 arduino-cli，域边界外
  （代码生成产物是 C 源码文本，编译链显式不在域内）；⑤烧录真执行面不背书——
  装了工具链接了板即真写芯片（真 subprocess），测试经可注入 argv 面验证调用形态，
  真硬件结果不背书；⑥裸 VM plugins="off" 无插件符号——与原生 exe 同一架构哲学
  （21 收官已登记维持）。
  **门禁三跑**：首跑 7019/7022——3 红 test_doc_facts = 收官 doc 同步编辑与门禁
  运行并发（README/ARCHITECTURE 数字中跑漂移），自伤伪影非代码缺陷，单文件复跑
  18/18 绿；重跑 7021/7022——1 红 tests/test_hotreload_phase24.py::
  test_reload_picks_up_change_in_run 仅全量序下显现：Windows 同刻度两写 mtime
  量化竞态（热启动快照与运行内 写文件 覆写落入同一时间戳刻度 → mtime 未变 →
  重载=False）——产品 mtime 检测语义正确（双面 `cur == old_mtime`），测试面加固：
  初版 mtime os.utime 回拨（now−10s）保证覆写严格更新，单跑 5/5 绿；三跑干净
  **7022/7022**（tests 6919 + kernel_purity 14 + ast_vm_gap 11 + golden 39 +
  dep_audit 1 + native_parity 38，native 1 例已知未实现不计入分母）。
  算术闭合：6801（23 收官）+ 221（24a-24h 三锁 43+28+21+27+29+41+16+16）= 7022。
  doc 同步：README 测试文件 143→151（+8 新档 test_*_phase24.py 八件）、语料
  170→173（.matha_packages/arithmetic/arithmetic.matha + 建模仿真.matha +
  单片机.matha）、领域插件 83→85（src/domains/ 85→87 个 .py：新增 mcu.py/
  simulation.py）；ARCHITECTURE core_py_lines 32,439→32,519（+80 = 24a VM 编译器
  同名冲突绑定 +3、24d 动态求值双面 +68、24e 仿真注入面 +4、24g 热重载注入面
  +5）；CHANGELOG 领域插件 83→85；ast_vm_gap 快照重生成（corpus_files 217→220，
  解析失败 0）；KNOWN_ISSUES 本条目。
- **2026-11 阶段 25 收官（自生凭据与应用中心：商店/CLI/CI 去外部凭据五片全落）**：用户拍板
  「外部凭据无法获得 → 直接为 Matha 创造自身凭据与环境」，范围三面：全自生凭据面 +
  内部软件分发中心 + 成为 Matha 的应用中心/商店；商店形态 = 纯 Matha 自举（Python 只出
  socket 驱动）；凭据 = 商店自签发 HMAC 令牌；CI 集成 = Release 附件 + 商店导入；休眠
  CI 家族 = 删 cd-full 三件、其余保留。
  **25a socket 服务端域胶水**：src/domains/networking.py 网络_服务/接受/收/发/关闭
  （真监听器句柄，端口 0 = 系统分配测试面，接受超时面 {"超时": True}）替换旧无句柄
  假面（网络连接/网络绑定/网络监听/Socket发送/Socket接收，22a 同类清算）；
  tests/test_socket_server_phase25.py 11 条 + 1 平台 skip（Windows SO_REUSEADDR 强制
  复用语义，绑定失败 ValueError 路径 POSIX 可复现）。
  **25b 商店 HMAC 令牌**：src/domains/store.py 三符号 商店_签发令牌/校验令牌/
  吊销令牌（HMAC-SHA256，header.payload.sig 三段式 + jti 8 字节随机；密钥首启
  secrets.token_bytes(32) 自生成落 <root>/.matha/store/secret.key——无外部凭据；
  吊销表 <root>/.matha/store/revoked.json jti→exp 持久化 + 过期条目回收；篡改/过期/
  吊销/形态错均诚实拒绝）；tests/test_store_token_phase25.py 15 条。
  **25c 纯 Matha 应用中心引擎**：matha/store_engine.matha——HTTP/1.1 文本面解析 +
  路由（GET /apps、GET /apps/<名>、GET /search?q=、POST /token、POST /publish、
  POST /revoke）+ 索引持久化 .matha/store/index.json，Python 仅 socket 驱动。引擎
  实现踩中并真化两处深层缺陷：① stdlib 截取/find 逐字符递归宿主面 ~140 字符即撞
  RecursionError → 分块真化（块内 ≤24/64 字符浅递归、块间推进，语义与旧实现逐字节
  一致；残余深递归项维持第二节登记）；② 解释器柯里化共享捕获表缺陷——模块 FuncDef
  闭包的 captured 列表被同函数全部调用链共享，部分应用路径原地 extend 让交错链
  （外层柯里调用挂起期间嵌套同名函数的另一条链）的绑定经 dict(captured) 末值优先
  互相覆盖（发布落盘索引形状错位根因）→ src/interp.py _call_lambda 改拷贝追加
  （+11 行，debug 轨迹取证）；tests/test_store_engine_phase25.py 17 条（路由/持久化/
  错误面/socket e2e/VM 面发布回环）。
  **25d matha app CLI**：src/app_cli.py 八子命令 serve/token/publish/upgrade/list/
  search/install/import-release——本地面在进程内直驱引擎 处理请求；远程面 raw socket
  HTTP/1.1 客户端（Connection: close 定界）；import-release 走 urllib HTTPS 拉
  GitHub Release 附件（URL 段 quote、repo 段 safe='/' 保形）；安装落
  .matha/apps/<应用>/<入口> + manifest.json（入口名单段校验）；matha_main app 命令族
  接线；tests/test_app_cli_phase25.py 14 条（真 socket serve 子进程 e2e 全回环 +
  诚实拒绝矩阵：缺令牌/版本不符/应用不存在/商店不可达/404）。
  **25e CI 去外部凭据**：休眠 CD 家族删除（cd-full.yml / docker_build_push.yml /
  multilang_benchmark.yml + .github/configs/ 钉钉共享配置两件，git rm）；ci.yml PyPI
  上传（PYPI_TOKEN）→ upload-artifact；matha-ci.yml publish → GitHub Release 附件
  （whl/tar.gz + exe，contents: write）；publish_matha_auth.yml → gh release upload；
  release.yml VSIX（VSCE_PAT/OVSX_PAT）→ Release 附件、钉钉通知 →
  $GITHUB_STEP_SUMMARY；benchmark.yml / stress_test.yml 同改 Step Summary；卫生锁
  tests/test_ci_hygiene_phase25.py 7 条（secrets 白名单 = {GITHUB_TOKEN}、
  your-company == 0、dingtalk == 0、删除负存在、无 id-token/twine upload、
  Step Summary 在位、CI→商店闭环 import-release 存在）。
  **登记不修八条（现状锁）**：①商店引擎查询参数原样匹配（无 URL 百分号解码）——
  非 ASCII 查询经 CLI 本地面可用，HTTP 线上面由调用方编码、引擎不解码；②响应定界
  走 Connection: close（无 Content-Length，RFC 7230 §3.3.3 规则 7），serve 单线程
  串行（每连接顺序处理，无并发面）；③远程商店客户端仅 http:// 明文（无 TLS——纯
  标准库 socket 面不背书 TLS）；④import-release 仅公开 Release 附件可导（urllib
  HTTPS 真 github.com 无凭据，私有仓库 404 诚实失败）；⑤令牌无密钥轮换面（
  secret.key 一次生成永用；删除重生成即全体旧令牌失效，中途撤销由吊销表按 jti
  补足）；⑥matha-ci.yml publish job 的 Release 附件清单含 dist/matha.exe /
  dist/matha-cc.exe，但 exe 由 windows build-exe job 产出且仅上传为 artifact——
  publish（ubuntu）工作区无 dist/*.exe，tag 发布前须补 download-artifact 步骤
  （维持原状登记，25e 未扩面）；⑦休眠工作流（benchmark/stress_test/riscv_baremetal/
  release/publish_matha_auth）引用不存在测试文件的死路径维持 9d 登记（仅手动触发
  不产生自动 run）；⑧release.yml 引用 install_tools.py/check_files.py 等死路径维持
  9d 登记。
  **门禁两跑**：首跑 7085/7086——1 红 tests/test_single_version = README matha app
  节示例 `--tag` 带了版本记号形态（v数字.数字）撞版本记号锁（doc 编辑自伤伪影非
  代码缺陷，同阶段 24 类），改占位符复跑；二跑干净 **7086/7086 通过率 100%**（tests 6983 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现
  与 socket 1 例平台 skip 不计入分母）。算术闭合：7022（24 收官）+ 65（25a-25e 三锁
  12+15+17+14+7）= 7087 条件 = 7086 通过 + 1 平台 skip。doc 同步：README 领域插件
  85→86、语料 173→174、测试文件 151→156 + 新增 `matha app` 用法节；ARCHITECTURE
  85→86 插件、清单 87、测试文件 156、指令码 33→34/34/34（陈旧勘误）、语料 174 +
  阶段 25 台账注记 + 应用中心段；CHANGELOG 领域插件 85→86 + 阶段 25 条目 + 指令码
  34；ast_vm_gap 快照重生成（corpus_files 220→221，解析失败 0）；KNOWN_ISSUES 本
  条目 + 9d/9e 勘误。
- **2026-11 阶段 26 收官（类插件化收官：运行时注册表泛化 + 编译器框架域 + 插件兼容/
  冲突面 + 设备/任务管理器四片全落）**：用户拍板五面：①提交（.zcode 融合变更集先行
  落盘 acce660）；②五个框架模块插件化并跟踪与消费（拍板「域化暴露」）；③Matha 所有
  功能类插件化——拆分/融合/互相调用/替换/扩展/升级含解释器/编译器（拍板「运行时
  注册表泛化 + 工厂收敛」）；④插件调用兼容/同步运行/冲突解决；⑤设备/任务管理器
  （拍板「CLI 子命令族 + 域双面」+「纯标准库 + 只读 subprocess」——pyproject
  dependencies=0 约束不变）。
  **26a 运行时注册表泛化**：src/kernel/exec_api.py 后端注册表条目化（_BackendEntry：
  description/enabled/factory）+ unregister_backend/set_backend_enabled（未登记诚实
  拒绝）+ backend_info（只列已登记项）+ make_vm 工厂（4 处 VM 构造收敛）+
  _wire_plugin_runtime 增 make_compiler_framework_runtime 注入面；主线 vm/native
  维持不在注册表（available_modes() 描述面权威、native 只产 exe 不可 run 诚实拒绝）；
  register→run→unregister 回环 + 停用后 run 诚实拒绝 + 主线零扰动锁
  tests/test_runtime_registry_phase26.py 11 条。
  **26b 编译器框架域（87th 插件）**：src/domains/compiler_framework.py——五框架模块
  （pass_manager/program_analyzer/strategy_selector/incremental_compiler/
  distributed_compiler，acce660 进主线）消费面 12 符号：程序_分析/策略_推荐/
  内置遍_安装/优化遍_列表/优化遍_启停/优化遍_执行/优化遍_注册/后端_列表/后端_执行/
  增量_编译/任务_提交/任务_清单 + 内置遍两件真实现（常量折叠遍 add/sub/mul/div
  数值字面量→load_const、除零不折叠诚实保留；死代码消除遍纯运算无后继使用者删除）+
  Matha 回调遍双面（清单物化面共享语境解释器回调、VM 闭包直注诚实拒绝；官方入口
  make_runtime 绑定运行本体 invoke_value，VM/宿主同名协议逐参柯里化）；踩中并修复
  PassManager 真缺陷——run() 只遍历 _pass_order、_ensure_order 序空才全量拓扑，内置
  遍装完后注册的回调遍永不执行（统计恒空）→ _attach_order（序空全量拓扑/非空追加尾）；
  跨运行时对拍锁（后端_执行 legacy-interp/vm 双面同值 + native「只产 exe」诚实拒绝）
  tests/test_compiler_framework_domain_phase26.py 24 条。
  **26c 插件兼容面**：src/plugin_api.py register() requires 依赖校验（缺依赖诚实拒绝
  LEVEL_ERROR「注册被拒」诊断 + _rejected 记录，依赖须已注册且注册序在前）+ 事后依赖
  缺失报告（unregister 后 report()「依赖缺失」如实列出、不自动注销）+ conflicts()
  多属主符号冲突面（语义维持清单最后声明者覆盖，报告只如实列出）+ report() 八键汇总
  （插件总数/已加载/符号总数/可加载符号/冲突/注册被拒/依赖缺失/诊断数）+ plugin_usage()
  全清单 [{名, 已加载, 物化时刻}]；tests/test_plugin_compat_phase26.py 14 条（拒绝/
  依赖序/事后缺失/冲突三面/八键形状 + 真注册表健康锁新鲜构造零耦合）。
  **26d 设备/任务管理器（88th 插件）**：src/system_inventory.py 信息层——
  hardware_info（静态平台面/内存面 + GPU nvidia-smi 只读查询：缺席·退出码·异常三路
  诚实降级 + MCU 工具链 shutil.which 四工具按板族路由 uno/nano/mega/stm32/esp32/
  rp2040，which/run 可注入测试面）；self_status（版本/工作目录/插件 report()/运行时
  后端/features/扩展状态/状态目录盘点/进程内存）；software_inventory（.matha/apps +
  .matha_packages 清单真解析，损坏条目跳过不伪造）；modules_inventory（自定义运算符
  REGISTRY/终端注册命令/优化遍/插件使用 四节）；src/domains/system_monitor.py 五符号
  （硬件_信息/自身_状况/软件_清单/模块_清单/插件_冲突）+ matha sys CLI 六节 hardware/
  self/plugins/software/modules/all（--root 隔离、JSON default=str、缺节 exit 2）；
  tests/test_system_inventory_phase26.py 27 条（可注入诚实降级矩阵 + 域双面对拍 +
  CLI 六节 e2e）。
  **登记不修八条（现状锁）**：①IncrementalCompiler._compile_file 模拟桩（不产真目标
  码 success=False 如实——增量面只报告受影响集，真编译走 mbc 主线）；②
  DistributedCompiler 任务执行需事件循环（域只提交/清单/状态查询，不调度执行）；
  ③插件使用口径=物化时刻（逐符号调用计数需包住每次内建调用，性能面负担）；④进程
  内存 psutil/resource 缺席诚实降级（Windows 无 resource 面，内存字段可空）；⑤GPU
  检测仅 nvidia-smi 只读查询（不设状态不管理——设备管理动作与 mcu 域真烧录分工，
  本面只盘点）；⑥PassManager 全局统计跨跑累积（全局单例进程级，重启即清零）；⑦全局
  注册表共享态——扩展启停测试的生命周期态对同进程后续读者可见（本阶段门禁首跑 4 红
  根因，见门禁段）；⑧matha sys 只读盘点（检测/加载软件=清单面读取，不安装不管理）。
  **门禁两跑**：首跑 7092/7096——4 红全落登记⑦（测试套件全局态污染，非产品缺陷）：
  tests/test_plugin_compat_phase26.py TestReportAndRealRegistry 真注册表两处 ≥89
  计数断言 + tests/test_system_inventory_phase26.py TestSelfStatus::
  test_shape_and_identity + TestModulesInventory::test_four_sections_present 同类；
  根因 tests/test_extension_system_phase23.py test_disabled_domain_symbols_unavailable
  停用 thermo 无回位 → 全局注册表 88 插件（e23+system_inventory 两档 58 条稳定复现
  2 红）；修复三处不改任何锁定语义——①e23 补 thermo 卫生回位（回位路径本来就有，
  quantum 同款断言）；②compat 真注册表三测试改 PluginResolver() 新鲜构造（同一真实
  清单，健康锁以清单单源为准，消除套件顺序耦合）；③system_inventory 两处计数断言
  降为形态锁（≥1，健康计数锁归 compat 新鲜构造面）；修复后 e23+compat+system_inventory
  72 条绿，二跑干净 **7199/7199 通过率 100%**（tests 7096 + kernel_purity 14 +
  ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，native 1 例已知未实现
  与 socket 1 例平台 skip 不计入分母）。算术闭合：7124（融合收官条件：7123 通过 +
  1 平台 skip）+ 76（26a-26d 三锁 11+24+14+27）= 7200 条件 = 7199 通过 + 1 平台
  skip。doc 同步：README 领域插件 86→88（src/domains/ 88→90 个 .py，表格/树/导语
  多处）+ 测试文件 157→161 + 新增 `matha sys` 用法节；ARCHITECTURE 88 插件/清单 89/
  测试文件 161/本体量 32,519→32,562（+43 = 26a 注册表条目化 + 工厂收敛）+ 阶段 26a
  台账注记；CHANGELOG 插件联邦节 86→88 + 阶段 26 条目；ast_vm_gap 快照预检无漂移
  （78 节点/59 发射/19 无码/指令码 34/0 解析失败，无重生成）。
- **2026-11 阶段 27 收官（共生体：Matha 既是桌面/移动软件又是操作系统——stage-4 脱宿主
  闭环 + 纯 Matha OS 内核 + 单元管理器五形态统一 + TUI 桌面 + 资源库三分支全落）**：
  用户拍板四项：①自举深度=先通过 Matha 编译器解释器编译 stage-4，再以此为跳板完成
  其它目的；②桌面=纯 Matha TUI 桌面；③单元管理器=五形态统一；④资源库=os+desktop+
  compat 三分支。全部本体为纯 Matha 模块跑在 Matha 自身解释器/VM 上，Python 层只留
  IO/进程原语薄桥。
  **27b stage-4 脱宿主闭环**：tests/test_stage4_closure_phase27.py 9 项（tier C
  joined 逐位一致/tier A 编译产物实例化对拍/tier B 全脱宿主 VM²——单档 ~10.5 min，
  跑前留足超时）；脱宿主真化：stdlib/vm.matha _to_float 依赖消除 + 运行M3V __抛错__
  真抛出（对齐宿主 MathaRuntimeError 面）+ 输出() 改名 输出码() 防内建劫持 + 三处
  vm.matha 模拟器缺陷修复（建盒 1 槽盒→[null,null] 双槽、解包栈逆序压栈→顺序、
  写局部/写盒缺换栈——连续 STORE 弹同一栈顶；主码级解包走写全局有换栈，故简单语料
  侥幸全绿，取证链在测试档 docstring）；tier C 扩证 joined+driver 新形态 Matha 编译器
  ≡ 宿主编译 0 函数差异。27b 发现的字典值误析（{"k": [...]} 值位双端同源误析）登记
  27g，已在 27f 窄化修复中修复。
  **27c 纯 Matha OS 内核**：matha/os/kernel.matha（module 内核）进程/服务/单元生命周期
  （装载/启动/停止/卸载/升级/回滚）+ requires 兼容协商（26c 语义的 Matha 镜像）；
  探针踩中即修内核 4 缺陷：空转轮步数翻倍→非就绪增量 [事件,0]、_卸载落地记录表破坏
  →_滤记、_步进第二元素继续旗标→步数增量恒 1、服务占用协商失效→对偶感知 _占用名；
  test_os_kernel_phase27.py 11 项。
  **27d 单元管理器五形态统一**：src/os_runtime.py 桥（app←25d manifest/包←24a/域插件
  ←PluginResolver/终端命令←12e registry/服务←register_service 五形态统一 + 外部单元
  subprocess spawn/poll/stop + 升级/回滚/卸载 + inspect 健康桥）；test_os_runtime_
  phase27.py 12 项。
  **27e TUI 桌面**：matha/os/desktop.matha（纯 Matha，use 标准库 {len|str} + use 内核；
  演示桌面预装载三单元 时钟/回声/便签；按键 j/k 焦点环绕、s 启动、t 停止、u 卸载、
  p 进程、d 步进、q 退出，全部动作经 OS 内核协商面，拒绝如实回传消息行）+ term_engine
  ⑤b `桌面` 命令（一次性确定性键序脚本，别名 desktop，≤16 键，缺省
  [d s p d d d d t u q]）；test_desktop_phase27.py 13 项。
  **27f 资源库三分支 + 解析器字典值语境窄化修复**：matha/library/{os,desktop,compat}/
  六模块（进程管理/单元清单/单元工厂/桌面组件/包适配器/命令适配器）+ 资源索引 21→27
  条；test_library_os_phase27.py 18 项。解析器修复：src/parser.py 新增 _parse_dict_
  value + _in_dict_value 旗标三处（init/括号消解链/字典字面量值位包装）——{"k": [x]}
  值位 [x] 为列表字面量而非输出命令，与三元分支/return 操作数同口径。**首稿宽面
  OP_COLON 加入运算符右值 token 表被回退**（与门禁挂起疑云的因果未证实，见复盘段），
  窄化修复以 AST 探针兜底（_probe_ast_dump.py：182 语料 pickle+sha256 双跑确定性）：
  boot 链六文件零扰动、唯一差异面 matha/vm/matha_vm.matha:66 帧栈构造
  {"帧栈": [新帧("<主>")]} host 面此前误析 Output→真列表（12b 19 + mbc_vm_matha 114 +
  library_os 18 = 151 项复跑全绿）——27b 登记的双端同源误析就此修复。
  **门禁两跑**：首跑 7263/7268 99.93%——5 红全为 doc 漂移+目录锁计数（test_doc_facts
  4 + test_library_as_code_phase24 资源目录 21→27 计数锁 1），doc 同步 + 改锁后
  doc 子集 73 项绿，二跑干净 **7268/7268 通过率 100%**（pytest 7165 过 2201.0s +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，
  native 1 例已知未实现与 socket 1 例平台 skip 不计入分母）。算术闭合：7200（26 收官
  条件）+ 69（5 新档 63 = stage4 9+kernel 11+os_runtime 12+desktop 13+library_os 18，
  加 test_library_as_code_phase24 _library_stems() 资源库动态参数化随 21→27 面 +6）
  = 7269 条件 = 7268 通过 + 1 平台 skip。
  **门禁挂起疑云复盘**（经验登记）：27f 期间一次全量门禁被误判「挂起」中止——事后
  证实 stage4_closure 与 mbc_vm_matha 两档各 ~10.5 min 固有成本（7 分钟前台超时判
  「挂起」是伪影，revert 后 stage4 638.97s 绿跑自然收尾）+ tail 管道缓冲 11 分钟零
  输出加重误判；宽面 OP_COLON 与该挂起的因果未证实。经验：VM²/自举重档单档预算
  >12 min 再判挂起；后台长跑勿经 tail 管道读中途输出。
  doc 同步：README `.matha` 语料 174→182（matha/os/ ×2 + matha/library/ ×6）+ 测试
  文件 161→166 + 树 166 + 新增 `matha 桌面` 用法节；ARCHITECTURE 本体量
  32,562→32,578（+16 = 27f 解析器字典值语境三处）+ 阶段 27f 台账注记 + 测试文件 166 +
  语料 182 + 新增共生体 OS 面节；CHANGELOG 阶段 27 共生体条目 + stage-4 自举注记；
  ast_vm_gap 快照 27f 重生成（scripts/ast_vm_matrix.py --write：corpus_files 221→229
  对应 +8 新语料；78 节点/59 发射/19 无码/指令码 34/0 解析失败不变，门禁 --check 绿）。资源库参数化面：test_library_as_code_
  phase24 _library_stems() 随 27f 六新模块 +6 项（目录计数锁 21→27 同步）。
  登记不修六条：①lambda/柯里块体内语句位条件赋值 `var = cond ? a : b` 折损为比较
  （语言形态，双端同源）；②缺失字典键 host=None/vm=KeyError（语义分歧，双端同源
  登记待统一）；③str() 数字专用（非数字入参诚实拒绝）；④semver 0.x 预发布包升级面
  诚实拒绝；⑤桌面为一次性确定性脚本形态（真交互逐键会话超出本阶段范围）；⑥VM²
  重档门禁预算与观测口径（见复盘段——非产品缺陷，操作经验）。
- **2026-11 阶段 28 收官（全工具链自举重建 + 统一五动作端口协议——全语料三重公式判据
  全落）**：用户拍板三项（均选推荐）：①全语料三重公式判据——AST 对拍（28b）+ 字节码
  _canon 对拍（28c）收口，VM 执行面维持阶段 27 stage-4 闭环锁；②统一五动作端口协议
  （注册/启停/升级/回滚/依赖协商）工具链六层贯穿（28e）；③全链贯穿。
  **28b parser/lexer 语法完备性 + AST 全语料对拍**：tests/test_parser_parity_
  phase28.py 22 项（13 固定 + 9 语料参数化）——自举解析器（lexer/stdlib/parser.matha
  编译入 host MBC 跑 VM）与宿主 src/parser.py 对同一源码 AST 逐节点一致：块体/顶层
  双轨分派（`#：`/`#N：`/【…】链内读取块恒等）、占位符 ？/？名 → is_placeholder
  Variable、typeof 关键字、值结尾 token 集；全语料 Matha dict-AST → 宿主 dataclass
  AST 逐字段相等（先前分歧回归文件 + 自举链自文件）。
  **28c 编译完备性 + 字节码全语料对拍**：tests/test_compiler_parity_phase28.py
  188 项（5 固定 + matha/**/*.matha 全语料动态参数化）——自举编译器（compiler_matha
  .matha，stage3）编译产物与宿主编译器 stage2 _canon 逐位一致。修复五类根因（每类
  最小源回归锁，语料面参数化全覆盖）：R1 module X { func X } 同名冲突不发射命名空间
  绑定；R2 函数体内语句位 let rec 盒协议（MAKE_BOX→值→STORE_BOX，lambda 自引用
  LOAD_OUTER_BOX 沿父链解析）；R3 return 语句（有值求值+RET / 无值 PUSH_NULL+RET）；
  R4 `#N：…` 合并 { } body 裸 list 逐条编译；R5 lambda 体内 if 下一行 else 不挂链
  ——三承接位对齐宿主。0x62 FORMULA_SCHEMA 登记宿主编译器专有（全语料经宿主 parser
  扫描 0 个 GenStmt 含槽，2026-11-18 实测；语料出现该形态前不阻塞三重判据）。
  **28d 四运行时开放插口**：vm.matha 内建插口 / 宿主 VM（src/mbc/vm.py
  register_builtin/unregister_builtin，保留名/模块函数/非可调用诚实拒绝）/ interp
  .matha 解释器插口（注册内建 尾部 经 并插口 并入环境——绑定环境前插序使注册项先于
  静态内建，重注册同名=覆盖升级，注销回落静态内建诚实未定义）/ 宿主 interp（src/
  interp.py 注册注销面）四面同构协议——注册/注销（仅还原经注册名）/回落（诚实未定义
  变量）/优先级（模块函数·用户函数胜过注册内建）/还原面；tests/test_open_ports_
  phase28.py 26 项双面对拍。
  **28e 统一五动作端口协议**：宿主适配层 src/extension_port.py make_port(层名, 运行
  时对象) + 纯 Matha 协议 matha/library/os/端口协议.matha（use os/端口协议）同一状态
  形状 {"层","条目","审计"}（条目六槽 [名,版本,启用,实现,历史,依赖名们]）同文案审计
  行；五动作返回 (结果,端口,原因)，诚实拒绝状态原样不动；六层后端实效 parser（自定义
  算子被源码真消费）/interp_host/vm/compiler（PassManager 启停实况）/kernel（features
  真翻转）/interp_boot（自举解释器插口 63→84→63 升级回滚回环）+ 诚实拒绝矩阵（保留
  名/非可调用/模块函数冲突/未知内核特性/非法结合性/未知层——全部 (假,状态原样,原因)）；
  src/custom_ops.py + src/compiler/pass_manager.py unregister 注销面；src/os_runtime
  .py register_toolchain_units 六层装载为内核服务单元 工具链-<层名>（装载=注册、
  启停=启停）+ 跨 VM 24d 钉池纪律（fn.consts/functions 钉池跨 VM 共享）登记；
  tests/test_port_protocol_phase28.py 17 项三面同判（A 协议双面对拍逐值一致 / B 六层
  后端实效 / C 诚实拒绝矩阵）。
  **门禁三跑**：run1（check.py）tests 项 3600s 上限击穿 TimeoutExpired——非死循环：
  Windows 击杀子进程不收孙进程、孙进程握住 stdout 管道致 communicate() 阻塞（item
  .seconds 13841.4s 伪影），其余 5 项绿 103/104 通过率 99.04%，进程清单干净无残留；
  run2（直接 pytest -v 全量，3064.26s）7413 过 / 6 败 / 1 skip——6 红全部单档复现
  （非套件序污染）且全为 28 真回归/锁漂移，三处修复：①matha/interp_matha.matha
  执行声明 分发表补 输出追踪 路由（28b 语句位裸列表发射 输出追踪 与自举解释器声明
  分发表错位——落裸表达式兜底走 求值 报「未知表达式类型」；镜像 interp.matha 全量
  委托 执行语句 的参照语义，test_bootstrap_gapfix_phase8pre test_literals_mb 3 红）；
  ②src/domains/capability.py _merge_module_source 补 ast.Binding 物化（28d interp
  .matha 首个模块级裸赋值 解释器插口 = [[]] 被 use 合并面静默丢弃——只合并 函数/
  枚举/LetBinding——VM 面 LOAD_GLOBAL 未定义名，test_use_compile_phase21 boundary
  2 红；修复后两把 boundary 锁精确回到阶段 27 形状 ok / KeyError: 0）；③test_library
  _as_code_phase24 资源目录计数锁 27→28（28e os/端口协议 条目同源）。修复面复跑
  103+111 全绿；run3 干净 **7522/7522 通过率 100%**（tests 7419 过 3026.3s +
  kernel_purity 14 + ast_vm_gap 11 + golden 39 + dep_audit 1 + native_parity 38，
  native 1 例已知未实现与 socket 1 例平台 skip 不计入分母）。
  算术闭合：7268（27 收官）+ 254（四新档 22+188+26+17 = 253 + test_library_as_code
  _phase24 _library_stems() 资源索引动态参数化随 27→28 面 +1）= 7522 通过 + 1 平台
  skip = 7523 条件。
  doc 同步：README `.matha` 语料 182→183（os/端口协议）+ 测试文件 166→170 + 树 170 +
  资源索引 21→28 注记 + 新增「自定义扩展插口（五动作端口协议）」用法节 + 自举重建
  判据段；ARCHITECTURE 本体量 32,578→32,618（+40 = 28d src/mbc/vm.py 注册注销面；
  28 其余宿主面 extension_port/custom_ops/pass_manager/interp/os_runtime 均不在
  core_py_lines 口径——src/ 五件之外）+ 新增「全工具链自举重建 + 五动作端口协议」节
  + 测试文件 170；CHANGELOG 阶段 28 条目；ast_vm_gap 快照重生成（scripts/ast_vm_matrix
  .py --write：corpus_files 229→230 对应 +1 新语料，解析失败 0，78 节点/59 发射/
  19 无码/指令码 34 不变，门禁 --check 绿）。
  登记不修九条（2026-11-18 探针逐项实测，双端形态注明）：①语句位下标赋值 a[i]=v
  静默 no-op（函数体位+顶层位双端同源；顶层位宿主打印比较归一 False、VM 静默——
  双端分歧形态）；②lambda 字面量立即调用 ((a)=>a*2)(21) 不应用 → '<function>'
  （双端同源），链式 ((a,b)=>a+b)(1)(2) → 不可调用的值： 1（双端同源）；对照：
  具名部分应用 f(1)(2)→3 与下标调用 表[0](21)→42 真可用（已验证语言形态）；③自举
  func 定义必须 ->（parser.matha 期望 箭头）——语言形态；④0x62 FORMULA_SCHEMA
  宿主编译器专有（见 28c 登记证据）；⑤自举 VM 错误文案分歧 vm.matha「变量未被
  定义： 」vs src/mbc/vm.py「未定义变量 '...'」；⑥lambda 体内 let rec 解析失败
  （期望 参数名 got PUNCT_LPAREN）；对照：func 体直接表达式位与块位 let rec 双端
  真可用（120 值对拍一致）；⑦语句位 `[` 路由输出追踪双端一致（27f 字典值窄化为
  唯一例外）——已验证语言形态非缺陷；⑧Dijkstra距离 = 桩（resource/logic/advanced
  _math.matha:68 简化注释，返回初始化距离表）；⑨stdlib str(n) 数字专用（stdlib
  .matha:416；str_safe:456 兜底）。
- **2026-11 阶段 29 收官（执行面双轨判据 + 自举链语言级缺陷真化 + 0x62 公式模式自举
  贯穿 + 编译器框架接入 MBC 主线）**：四项拍板全走推荐项（①自举执行面全语料判据
  ②自举链语言级缺陷真化 ③0x62 自举贯穿 ④框架接入 MBC 主线），缺失字典键语义
  另拍板 vm→host 对齐（缺键返 null）。
  **29b 自举链语言级缺陷真化（自举链三镜像双端对齐）**：①语句位下标赋值
  `xs[i] = v` 真化——新指令码 0x64 STORE_SUBSCRIPT（指令码 34→35），宿主链
  parser→mbc compiler→VM（原位变异/越界透传 IndexError/字典命中键原位更新）→
  native（setitem_rt 五路错误）四执行体 + 自举链三镜像（parser.matha 解析 /
  compiler_matha.matha 发射 / interp_matha.matha 执行语句设值 + stdlib.matha
  原地设值 helper 族）；负下标回绕/嵌套容器/别名原位可见双面一致；28-①「语句位
  下标赋值静默 no-op + 顶层位宿主比较归一 vs VM 静默分歧」整体退役
  （test_mbc_bootstrap set_index_and_mutate 锁值 no-op→真变异 [[9,4],9]）。
  ②lambda 字面量立即调用/链式 `((x)=>x*2)(21)`/`((a,b)=>a+b)(1)(2)` 自举面真
  应用，分组非 lambda `(1+2)(3)` 双面诚实报错（28-② 退役；具名部分应用 f(1)(2)
  与下标调用 表[0](21) 真可用形态维持对照锁）。③let 函数简写 `->` 可选（rec
  简写/带类型简写/显式 lambda 体三支，宿主 3471 简写分支镜像入自举 parser）+
  参数类型标注 `(y: Int) => …` 自举面 + 单 `=` 右值悬空关系运算符回退；带箭头
  显式 lambda 体特例双端一致报未定义变量 'x'（值侧 lambda 只有自己的参数——
  语言形态对照锁）。④零参闭包 `f()` 自举面 IndexError 真修（解析器 IntLit(0)
  占位 arg，宿主/VM 忽略占位，自举 应用函数 补空参守卫）。⑤缺失字典键索引
  vm→host 对齐（用户拍板）：`d["缺键"]` 返 null，VM KeyError 显式偏差解除，
  host/VM/native 三执行体同语义（test_native_heap 注记勘误 +
  test_os_kernel_phase27 头注 C 组缺失字典键分歧条目勘误 +
  test_use_compile_phase21 boundary 锁双面文案逐字一致）。⑥错误文案归一：
  MathaUndefinedNameError「未定义变量 'x'」vm.matha 与宿主一致（28-⑤ 退役）。
  附带：lambda 体内单函数 let rec 双端真化（宿主+boot 120 值对拍，语句位 `[ ]`
  输出追踪双记录语义正确——28-⑥ 单函数面退役；互相递归前向引用仍登记见下②）
  + boot parser AST 对拍转换面补 跳出语句/继续语句 节点（test_parser_parity_
  phase28 conv 面）。
  **29c 0x62 公式模式自举贯穿**：宿主 ？占位符公式语法（`#1：？单价 * ？数量 =
  ？总价` GenStmt + src/formula_schema 形状/渲染/槽位收集）贯穿自举四面——
  parser.matha 占位符解析 → interp_matha.matha 生成语句支（env `__公式库__`
  登记、命中不求值、异形诚实错）→ compiler_matha.matha 0x62 发射 → vm.matha
  公式库槽（形状即身份归并、运行M3V 入口清零跨运行不污染、宿主 VM 每实例新库
  同构）；test_selfhost_formula_phase29 17 项（L1 双面 helper 对拍/L2
  stage2↔stage3 字节码对拍〔同形命中零码〕/L3 vm.matha 库面/L4 interp 面/L5
  跨运行时公式库对拍——28-④「0x62 宿主编译器专有」退役）。
  **29d 执行面双轨判据（拍板双轨制）**：A 轨 pytest 轻中档锁——test_selfhost_
  exec_phase29 31 项（主码 P1-P13 boot↔host 逐值对拍：多输出/内建链式/空输出/
  裸 Trail/for/while/函数值归一/嵌套内建）+ test_selfhost_language_phase29 14 项
  （29b 六缺陷组 boot↔host↔VM² 三面同判）+ test_selfhost_matrix_phase29 3 项
  （快照锁）+ 29c 17 项入常规门禁；B 轨重档 sweep——scripts/selfhost_matrix.py
  225 语料 × 双运行时（boot 复用单解释器 + 宿主）多进程 workers=4 timeout=120
  拒绝 --filter/--limit（可复现性），快照 docs/selfhost_matrix.json --check
  门禁化。快照 225：双面一致 147 / boot_err_host_ok 61 / both_err 17 / timeout 0 /
  双面 differ 0。61 分类：读取块 23 + 未找到模块 13 + 未定义变量 12 + 设值 6 +
  try 4 + IndexError 3；both_err 17 = 错误测试语料双端如实报错 + boot 未支持
  节点（结构体/枚举/属性/跳出/返回语句）+ Token 跨模块未找到 3 + parser 缺口 1；
  matha/generated 六文件全 ok（登记不修见下⑤）。
  **29e 编译器框架接入 MBC 主线（opt-in 默认关）**：方向反转——框架泛 IR 遍维持
  不碰 MBC 主线，MBC 字节码遍经 src/compiler/mbc_adapter.py 反向注册内核 exec_api
  编译后钩子接入主线：exec_api 纯钩子槽 set_compile_hook/get_compile_hook/
  _apply_compile_hook（本体量 +32 行唯一增量），compile_module 为单一接线点
  （run_checked/_run_mbc 经 compile_module 不重复施加；build_exe = compile_module
  (source) + emit_exe(mod)，native.py 零改动）；双 Pass——字节码常量折叠
  （PUSH_CONST+PUSH_CONST+BINOP 模式、跳转目标排除、池索引守卫、类型严格、定点
  迭代；调用 VM 同一 _BINOPS/_UNARYOPS 求值故与运行期逐位一致，报错诚实保留
  运行期路径）+ 字节码死代码消除（JMP/JZ/JNZ/RET/RAISE/RAISE_MATCH/HALT 可达性
  BFS + 跳转重映射）；opt-in 默认关双保险（不 import mbc_adapter = 无钩子；
  features MBC_PASSES 默认 False = 钩子自查直通）；五开关入册
  （test_extension_system_phase23 known_states 4→5 键）；test_mbc_passes_phase29
  30 项（A 组 subprocess 无钩子取证/B 组单遍单元/C 组 15 参数化 on/off 等价 +
  全输出稳定）。
  **29f 收官锁面**：四项旧锁诚实更新（零 src 改动）——test_bootstrap_host 三项
  （29d 输出列表语义统一后 mb.interpret 返回 输出 语句行与宿主/VM 面同口径，
  顶层裸表达式不再回显；算术/自定义算子经 输出() 通道 + strict=True 断言，空输入
  诚实 []；旧「自举面无法执行用户函数/静默回退产生 [6]」注记为过时措辞勘误——
  boot 面用户函数与 @define_op 求值早已落地）+ test_phase17_sweep 语句位下标读
  边界锁随 29b 真化退役（boot 面不再抛「下标」错，与宿主表达式语句求值丢弃同形
  ——双面静默一致新锁）。
  **门禁**：run1 tests lane 4 红/7531 过 3428.76s——4 红全为锁漂移非产品缺陷（三
  bootstrap_host 旧契约锁 + phase17 边界锁），锁面修复后两档复跑 65/65 + 9/9 绿；
  quick lanes：kernel_purity 14 绿 + ast_vm_gap 11 绿（快照重生成：语料 230 不变、
  78 节点/59 发射/19 无码/不认识 0/阻塞缺口 0/指令码 34→35 对应 0x64、解析失败
  0）+ golden 39/39 + dep_audit 39 内核文件 189 import 边 0 违规；run2 全量 tests
  lane **7535 过 + 1 skip 3398.32s** + native_parity 38/39（0 失败，native 已知
  未实现 1 例不计分母）+ Track B selfhost_matrix --check 一致——全绿收官。
  算术闭合：7638 过 = 7522（28 收官）+ 95（五新档 exec 31 + language 14 + formula
  17 + mbc_passes 30 + matrix 3）+ 21（test_native 29b-① STORE_SUBSCRIPT 双面
  2×8 参数化 + 5 固定）；7639 条件 = 7638 过 + 1 skip（平台 skip 承继）。
  doc 同步：README（五开关 MBC_PASSES 注记 + 执行面双轨判据段 + 编译器框架接入段
  + 测试文件 175）；ARCHITECTURE 本体量 32,827→32,859（+32 = 29e exec_api 钩子
  槽；29b/29c 的 src/parser、src/interp、src/mbc/*、matha/*.matha 镜像与 scripts/
  selfhost_matrix.py 不在 core_py_lines 口径的 src/ 五件之外——src/ 改动行均在
  口径内见 numstat）+ 阶段 29 节 + 测试文件 175；CHANGELOG 阶段 29 条目；
  ast_vm_gap 快照重生成（scripts/ast_vm_matrix.py --write 实跑）；
  selfhost_matrix 快照生成 + --check 绿（scripts/selfhost_matrix.py --write）。
  登记不修八条（2026-11-19 实测）：①原生端字典缺键写入诚实报错（dict_put 函数式
  不可扩容；命中键原位更新可用——test_native docstring 登记）；②boot 面互相递归
  let rec 前向引用（偶调奇）报未定义变量 '奇'——单函数 let rec 已真化（120 值
  对拍），互相递归待函级提升；③boot 面跨文件 use 边界：模块 '词法器' 中未找到
  'Token'（bootstrap_test/interp/nl_lexer 三语料）——boot 装载单模块不入跨模块
  符号合并；④boot 面未支持节点：结构体/枚举/属性/跳出语句/返回语句（未知表达式
  类型形态——data_structures/process_math/bootstrap_matha 等）；⑤B 轨登记不扩面：
  读取块 23/未找到模块 13/设值 6/try 4/IndexError 3（明细见 docs/selfhost_matrix
  .json——A 轨锁内窄化修复逐阶段推进，B 轨只锁快照一致）；⑥29e opt-in 边界：
  MBC_PASSES 开启时跳入 BINOP 模式中段的跳转诚实跳过不折叠（保守正确优先）；
  mbc_adapter 未 import 时零钩子零扰动（subprocess 取证锁）；⑦mb.interpret 输出
  列表语义统一为 breaking 变更注记（旧「返回末语句值」契约退役；matha_engine
  回退面随新口径，matha_main 主线早在 26a 前已改走 exec_api 不受影响）；⑧自举
  func 定义仍必须 `->`（parser.matha 期望箭头——语言形态，与 28-③ 同源未变）；
  28-⑦⑧⑨（语句位 `[` 路由一致性/Dijkstra 距离桩/stdlib str 数字专用）维持原
  登记不修。

- **2026-11 阶段 40 收官（真缺陷批：三引号多行字符串双端词法器真化——39-①
  退役 + differ 3 语料收口——31-⑨ 退役，Track B both_ok_differ 3 → 0）**：
  方向拍板走推荐项「A：真缺陷批——三引号 + differ 3」；40b 形态拍板走推荐项
  「A：产品侧真修（`__eq__`/`__repr__` + 播种内建）」；未闭合字符串分歧拍板
  走推荐项「同批真修」；节奏拍板「先摸底后实现」。
  **40a 三引号多行字符串双端真化（39-① 退役）**：宿主 src/lexer.py 新
  `_string_triple`（三态扫描：闭合三连 / 转义续行 / EOF 未闭合诚实报错）+
  `"`/`'` 首字符三连判定分派位（+30−2——本体量 33,452 → 33,480）；boot 镜像
  matha/lexer.matha `是三连`/`扫描三引号续`（+37−5）——`""""""` 空串、
  `"""li1\nli2"""` 跨行、`"""a\tb"""` 转义、`'''…'''` 单引号三连同形；词法
  token 值/行/列双端逐位 parity（NEWLINE 约定除外，登记②）；多行值 vm/hi/
  mb/VM² 四面 + M3V 六文件链同判。matha/bootstrap_test.matha 测试 4（三引号
  多行串）由诚实拒绝真化为跑通（−10+4），39c 根因锁相应改锁。未闭合串四形
  态（单/双/三引号 + 三连尾随引号）双端诚实报错同文案「字符串未闭合」——
  225 语料零含未闭合串，判定面零漂移。
  **40b differ 3 语料收口（31-⑨ 退役）**：按登记根因（宿主对象无 `__eq__`
  故跨运行实例身份不等 / 神经网络无种子）产品侧真修，而非放宽
  `selfhost_matrix._norm`。宿主值语义：src/autonomous.py `_OptResult`/
  `_GrowResult` + src/domains/data_science.py `Dataset` 补 `__eq__`（值元组
  逐字段、异类 NotImplemented）与 `__repr__`（可变故不设 `__hash__`——
  hash() 诚实 TypeError），08_auto_optimize / data_pipeline 双面同判；
  `_Sample` 故意不改（挂钟 avg_ms/times 非确定，值语义化无意义）。神经网络
  显式播种：src/ai_framework.py `seed_random`（同种子同权重 / 异种子异权重 /
  非 int 含 bool 诚实拒绝）+ src/domains/neural_network.py `随机种子` 柯里化
  内建与 `_nn_symtab_names` + src/domains/registry.py NeuralNetwork 模板
  functions 追加 + src/domains/manifest.json 重生成（`gen_domain_manifest.py
  --check` 绿——89 插件 / 2806 可载符号）+ 语料 examples/ai/neural_network.-
  matha 顶置 `随机种子(2026)`；`输出(随机种子(2026))` hi [2026] ↔ vm
  ([2026], None) 双面同判。
  **40c 判定面与旧锁收口**：Track B 快照重生成 225 = both_ok_equal **215**
  + both_ok_differ **0** + both_err_equal **10** + both_err 0 + timeout 0
  （原 211/3/11——differ 3 全转 equal，bootstrap_test 由 both_err_equal 转
  both_ok_equal），--write/--check 两跑一致；31-⑨ 登记锁改三语料双面同判真
  化锁、39c 三引号根因锁改真跑值锁。附带发现两处陈旧边界锁被 40a 意外真化
  ——裸 host 面 bootstrap_test 不再早停「不可调用的值」而跑通全程 [54, 3,
  57]（test_semantic_parity_phase19 边界锁 + test_use_compile_phase21 改锁
  test_bootstrap_test_both_faces_true）：自举链嵌套装载深栈，裸解释器面默认
  预算（run() 自抬 5000+len//10）在 pytest 进程下仍触发 RecursionError——
  限幅伪影非语义分歧，按 Track B worker 口径抬 20000 并退出还原后跑通；官方
  门面（exec_api + 完整 Interpreter）同判 [54, 3, 57]。裸 VM
  面无加载器注入仍诚实拒绝 未定义变量 '加载模块'。
  A 轨新档 test_selfhost_language_phase40 27 项（40a1 token parity 七形态 +
  单行串回归四形态 + 全流 parity / 40a2 多行值四面 + M3V 往返四形态 / 40a3
  未闭合串双面 + m3v 面 / 40b1 播种可复现与守卫 / 40b2 注册四面（BUILTINS /
  符号表 / registry 模板 / manifest）+ 双面值 / 40b3 Dataset 与 _OptResult·
  _GrowResult 值语义（含不可哈希）/ 40b4 打印双面 / 40c 登记锁两项）。
  **门禁全绿，首跑两红皆为 40a 意外真化的陈旧边界锁（改锁后定向复跑 46/46
  绿）**：tests lane 7899 过 + 1 平台 skip（4493.00s）+ kernel_purity 14 +
  ast_vm_gap 11（快照零扰动——无新 AST 节点与 opcode，指令码不变）+ golden
  39/39 + dep_audit 39 内核文件 189 import 边 0 违规 + native_parity 38/39
  （0 失败，native 已知未实现 1 例不计分母）+ Track B --write/--check 一致 +
  doc_facts 18 过。算术闭合：8003 条件 = 8002 过（tests 7899 + purity 14 +
  ast_vm_gap 11 + golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip
  承继）= 7976（39 条件）+ 27（test_selfhost_language_phase40）。doc 同步：
  README（阶段 40 段 + 测试文件 190 ×2）；ARCHITECTURE（本体量 33,452→
  33,480（+28 = 40a src/lexer.py +30−2；src/autonomous.py、src/domains/*、
  src/ai_framework.py、matha/*.matha 与新锁档均不在 core_py_lines 口径）+
  阶段 40 节 + 测试文件 190）；CHANGELOG 阶段 40 条目；KNOWN_ISSUES 阶段 40
  收官条目。
  登记不修四条（2026-11-24 收官实测，均有锁防漂移）：①interp.matha 四文件
  链面缺 机械单元/生成语句 执行臂——同 AST 形态 `#：[1 + 1]` 在 interp_matha
  （五文件 boot 链）真跑得 2，interp.matha 落「未知表达式类型: 机械单元」
  （29c 仅落 interp_matha.matha；test_40c_interp_matha_mech_unit_mirror_-
  registration 锁）②NEWLINE token 约定分歧——宿主推进到下一行后记 (行+1, 1)
  且值为两字符转义文本 `"\n"`，链面推进前记本行末列且值为真换行（其余
  token 值/行/列逐位同判，流级 parity 锁显式除外 NEWLINE；既有边界非本片
  引入，test_40c_newline_token_position_registration 锁）③未闭合串载体类名
  分歧——宿主 LexerError（消息带 `at L:col` 前缀）vs 链面 MathaRuntimeError
  「字符串未闭合」，文案同源而类型载体不同（test_40a3 双面锁各断本类与消
  息，m3v 面编译期即报不静默成 token）④bootstrap_test 裸解释器面（无 exec_
  api 注入）自举链嵌套装载深栈需递归预算高于 `Interpreter.run` 自适应抬升
  值（5000+len//10）——限幅伪影非语义分歧，两处边界锁按 Track B worker 口径
  显式抬 20000 并退出还原后跑通 [54, 3, 57]（官方门面 exec_api 面无需抬
  即同判）。判定面口径注记承继 39（`_ERR_TRUNC = 240` 截断比较）。
  退役两条：39-①（三引号字符串双端词法器均不支持）、31-⑨（对象身份 / 无
  种子致 differ 3）。承继 33-⑤（mb 词法器递归深度上限）+ 32-⑧⑫ + 28-⑧ +
  29-①⑥⑦ + 37-①②③ + 38-①② + 39-②③ 维持原登记不修。边界维持：pyproject
  dependencies=[] 不变。

- **2026-11 阶段 39 收官（Track B both_err 归因批：31-⑧ 退役——both_err 13
  → 0，11 条转 both_err_equal 双面同判诚实面 + 2 条转 both_ok_equal）**：
  方向拍板走推荐项「A：Track B both_err 归因批」；13 语料逐文件归因后按根因
  分四片真化 + 一片判定面细分，残留三根因如实登记为边界。
  **39a 链面应用分派补齐**：interp_matha.matha/interp.matha 应用函数/应用多
  参数函数 补裸 λ-AST 字典臂（`f["类型"] = "lambda"` → 求值lambda 折闭包重入
  __closure__ 机制，柯里化/多参语义同臂复用）——bootstrap_test 3.6/3.7/3.9
  直调链 API 形态双面 + VM² 同判；不可调用值渲染改 标准库.元素repr（CPython
  repr 规则——字符串加引号转义、其余同 str）对齐宿主 `f"{func!r}"`（载体位
  src/interp.py 与 src/mbc/vm.py 各一处），此前 str 丢字符串引号致双端消息
  不同（'' vs 空）——链面 8/4 处渲染点全改尽结构锁 + 六值形×四面文案锁；
  零参闭包守卫（`len(params) = 0 ? null : params[0]` + 空参数表直返 captured，
  29d 同口径）——此前 params[0] 落原生 IndexError。
  **39b 未定义变量异常类真化（31-⑧ 根因之一退役）**：新类型化抛错内建
  `未定义错误` → MathaUndefinedNameError（MathaRuntimeError + KeyError 双继
  承，消息逐字不变「未定义变量 '<名>'」），注册 src/interp.py BUILTINS +
  src/mbc/vm.py `_default_builtins` + vm.matha 内建名表，且三处保留内建面
  （28d 插口不可遮蔽）同步扩展；自举链 查找环境/查找环境链、interp.matha
  查找环境、vm.matha 查全局 缺名臂改裸名调用——vm/hi/mb/VM² 四面异常类归一
  （golden 13/31 双端逐字同判锁）。旧载体锁真化改锁五处（phase8pre ×1 +
  phase8a ×2 + bootstrap_host ×1 + formula29 ×1：MathaRuntimeError →
  MathaUndefinedNameError）。
  **39b-2 m3v 面**：vm.matha 内建特殊 补 未定义错误 带内臂（与 错误 同通道
  `抛错返回(参数[0])`）+ 是保留内建名/应用内建 特殊名守卫/内建名表 三处同族
  扩展；vm.matha 自身 查全局 缺名命中宿主内建故类型保留，唯目标码直调本内建
  后逃逸 运行M3V 边界经 `错误(结果[1])` 转宿主 MathaRuntimeError——带内通道
  无类型载体，登记不修③。
  **39c bootstrap_matha 语料刷新**：词法器.扫描 补现代柯里化 API 尾参
  `(0)(1)(1)([])` 三处——boot 面 Partial len TypeError vs host 面 属性访问失
  败 str.类型 双端异根因清零，双面 ok 且 4 输出前 3 项逐字同判（第 4 项
  加载模块 胶水返回形状，登记不修②）。
  **39d compiler_matha 源序 + 符号导入**：`let 不折叠 = " nofold"` 哨兵前移
  至模块顶（宿主闭包按定义序快照环境，后定义模块级 let 对先定义函数不可见）
  + `use 标准库` 补 dict_from_pairs/dict_get/dict_has/dict_put/int_of_num——
  boot 未定义变量 'dict_from_pairs' vs host 未定义变量 '不折叠' 双端异根因清
  零，bootstrap_full_test 22 输出逐字同判；boot 编译器发射面 stage2↔stage3
  逐位一致（parity 回归锁绿，指令码零漂移）。附带 hi 面 BUILTINS 补
  list_push（与 VM `_default_builtins`/`_curry2` 同构原语——自举编译器 `_发`
  构建器 O(1) 原地追加发射位）。phase21 两条陈旧边界锁真化改锁（bootstrap_-
  matha/bootstrap_full_test 双面 ok）。
  **39e 判定面细分**：scripts/selfhost_matrix.py `_classify` 双 err 条目按
  boot_err == host_err 逐字相等细分 both_err_equal（双面同判的诚实报错面），
  归因后仍存差异者维持 both_err；summary 分类键序扩至七键 + structure_check
  缺分类键诚实报错（旧快照需 --write 重生成，不静默漏计）；phase29 结构锁同
  步七键算术闭合。快照重生成 225 = both_ok_equal 211 / both_ok_differ 3 /
  boot_err_host_ok 0 / boot_ok_host_err 0 / both_err_equal 11 / both_err 0 /
  timeout 0（both_err_equal 11 = bootstrap_test + golden 12/13/14/24/25/26/
  27/28/29/31），--check 复跑 225/225 条目复现一致。
  A 轨新档 test_selfhost_language_phase39 31 项（39a λ-dict 四形态 + 元素repr
  六值形×四面 + 载体 wired 结构 + 零参 λ / 39b 载体四面×2 + 子类关系 + golden
  同判 + 双宿主注册 + 保留面 / 39b2 m3v 三态 + vm.matha 注册结构 / 39d 导入
  + 源序 / 39c 双面 ×3 / 39e 判定 ×3）。
  **门禁**：tests lane 7871 过 + 1 skip + 1 红 4260.29s（唯一红为 test_doc_-
  facts 本体量口径过期——39b src/mbc/vm.py +16 行未同步 ARCHITECTURE；
  33,436 → 33,452 后 doc_facts 18 绿复跑，tests 口径 7872）+ kernel_purity
  14 + ast_vm_gap 11（快照零扰动无需重生成——指令码不变）+ golden 39/39 +
  dep_audit 39 内核文件 189 import 边 0 违规 + native_parity 38/39（0 失败，
  native 已知未实现 1 例不计分母）+ Track B --write/--check 两跑一致。算术闭
  合：7976 条件 = 7975 过（tests 7872 + purity 14 + ast_vm_gap 11 + golden
  39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）= 7945（38 条件）
  + 31（test_selfhost_language_phase39）。doc 同步：README（阶段 39 段 + 测
  试文件 189 ×2）；ARCHITECTURE（本体量 33,436→33,452（+16 = 39b src/mbc/-
  vm.py `_builtin_undefined_error` + b.setdefault + 保留集与注释；src/interp.py
  与 matha/*.matha 镜像不在 core_py_lines 口径）+ 阶段 39 节 + 测试文件
  189）；CHANGELOG 阶段 39 条目；KNOWN_ISSUES 阶段 39 收官条目。
  登记不修三条（2026-11-24 收官实测，均有锁防漂移）：①三引号字符串——
  bootstrap_test 残留根因，宿主与 boot 词法器双双不支持 `"""…"""` 多行字符
  串（双端同形失败，如实分类 both_err_equal 而非修复项；
  test_39c_bootstrap_test_still_both_err_triple_quote 锁）②加载模块 胶水返
  回形状面差——hi 面 `加载模块_文件` → Bool（src/interp.py:4308
  `_b_load_matha_module`）vs VM 面 → list[str]（src/kernel/exec_api.py:171 注
  入 src/domains/capability.py:297 编译面胶水），bootstrap_matha 第 4 输出形
  状分歧（test_39c_bootstrap_matha_corpus_two_faces_ok 前 3 项逐字锁 + 长度
  锁；Track B boot↔host 面第 4 项同判 equal，boot 注入宿主真实现）③m3v 面直
  调 未定义错误 逃逸边界类转换（带内 "__抛错__" 通道无类型载体，
  test_39b2_m3v_undefined_error_builtin_in_band 锁——错误串
  「MathaRuntimeError: 手工」非本类）。判定面口径注记：both_err_equal 的逐字
  相等以 `_ERR_TRUNC = 240` 截断后的 boot_err/host_err 串比较为准，超长同根因
  消息不另设判据。
  退役一条：31-⑧（both_err 13 构成）。承继：33-⑤（mb 词法器递归深度上限）
  + 32-⑧⑫ + 31-⑨（differ 3 维持——08_auto_optimize/data_pipeline/
  neural_network 对象身份/未定种子如实分歧）+ 28-⑧ + 29-①⑥⑦ + 37-①②③ +
  38-①② 维持原登记不修。边界维持：pyproject dependencies=[] 不变。

- **2026-11 阶段 38 收官（m3v 异常帧机制：35-② 真化——编译态 try/catch 捕
  获运行期错误，载体不可知单点包裹）**：方向拍板走推荐项「A：m3v 异常帧机
  制」；修复形态拍板走推荐项「捕获闭包单点包裹」——不复制 vm.py 异常帧机
  制入 vm.matha（8 opcode × 三执行体爆炸），而在 vm.matha 两个分派位
  （捕获闭包/捕获内建）用 Matha 级 调用捕获 把子执行体/内建调用单点包裹成
  带内结果——载体（vm.py Python try/except / interp.py / native longjmp /
  VM² 同链）不可知，载体异常在捕获分派边界统一转带内 "__异常__" 标记。
  **38a 机制**：捕获闭包位 `调用捕获((p) => 执行(p[0],…,p[4]))`（实参双
  嵌套 [[…]]——invoke_value 按 fn(*args) 铺开，守卫 lambda 单参须绑整
  体）→ 守卫[0] = "__异常__" 时以 ["__异常__", 消息] 标记入顶帧（try/
  catch 正常接管），否则 子结果 = 守卫[1] 走既有 "__抛错__"/"__停机__"
  臂（带内路径零变化）；捕获内建位同形 `调用捕获((p) => 应用内建
  (p[0],p[1],p[2]))` → "__异常__" 转 ["__抛错__", 消息] 统一打标。载体
  派发家族（除零——宿主 VM ZeroDivisionError→领域文案 / 解构失败——
  UNPACK_SEQ 守卫 / 未定义变量）三面 + VM² 同判；带内错误内建（RAISE/
  错误 操作码）路径零扰动。锁档 38a1–38a8 八形态（四族捕获 parity / 带内
  回归 boom / finally 序 [1, 9, 消息] / catch 重抛逃逸 / 部分输出保序
  [1, 消息] / 既有名保序 [消息, 5] / 新建名登记锁 / 内层边界胜+无 try
  逃逸）。**35x 真化改锁**：test_35x_m3v_try_catch_registration →
  test_35x_m3v_try_catch_true（一函数三族内部循环：除零/下标越界/解构失
  败全捕获）。vm.matha +46−31 单文件改动；src/ 零改动、指令码不变。
  **门禁**：全量 tests lane 7841 过 + 1 平台 skip 4532.21s 首跑零红；
  kernel_purity 14 + ast_vm_gap 11（快照零扰动无需重生成——包裹仅用既
  有 AST 构造与 opcode，节点/发射映射零变化）+ golden 39/39 + dep_audit
  39 内核文件 189 import 边 0 违规 + native_parity 38/39（0 失败，native
  已知未实现 1 例不计分母）+ Track B selfhost_matrix --check 一致（快照
  零扰动——boot 链不含 vm.matha）。算术闭合：7945 条件 = 7944 过（tests
  7841 + purity 14 + ast_vm_gap 11 + golden 39 + native 38 + dep_audit
  1）+ 1 skip（平台 skip 承继）= 7933（37 条件）+ 12
  （test_selfhost_language_phase38）。doc 同步：README（阶段 38 段 + 测
  试文件 188 ×2）；ARCHITECTURE（本体量 33,436 不变——包裹全在
  matha/vm.matha 自举镜像不在 core_py_lines 口径，src/ 零改动指令码不
  变）+ 阶段 38 节 + 测试文件 188；CHANGELOG 阶段 38 条目。登记不修两条
  （2026-11-23 收官实测，均有登记锁防漂移）：①vm↔m3v 下标越界文案分歧
  （既有，非 38 引入）——vm/hi 面下标读越界透传 Python IndexError「list
  index out of range」（vm.py 0x5B c[idx] 直透 + interp.py IndexExpr
  container[index] 直透），m3v 面下标由 vm.matha 取下标 → list_get →
  stdlib get 域文案「列表索引越界: 5」经 错误 内建抛载体异常——同一载体
  守卫、不同检测点（38a1 badindex 双面各断正典文案防漂移）；消息统一属
  src/ 改动，登记不修 ②新建全局名捕获路径丢失（38a 窄分歧）——设全局
  对既有名原位对改（载体重入后存活），新名前插 [[名,值]] 结构脊（载体异
  常展开时丢）——try 体内新建全局在捕获路径不可见（38a7 登记锁：vm 面
  [消息, 5] vs m3v 面 未定义变量 'y'）；带内路径（RAISE）全保真无此分
  歧，宿主面无此分歧（vm.globals 真 dict 原地变异）。退役一条：35-②
  （m3v 编译态 try/catch 不捕获运行期错误）。承继：33-⑤（mb 词法器递归
  深度上限）+ 32-⑧⑫ + 31-⑧⑨ + 28-⑧ + 29-①⑥⑦ + 37-①②③ 维持原登记
  不修。

- **2026-11 阶段 37 收官（语言面清尾批：五项登记分歧退役——32-② 31-③ 协议一致
  锁 + 32-⑩ 36-① 36-② 真化，同族顺手真修）**：方向拍板走推荐项「A：语言面清尾
  批」（五项一批收官）。**37a 陈旧登记退役（协议一致锁——三面已收敛，无行为改
  动）**：32-② 空括号 () 解析——三面早已统一零参调用约定（() 降糖
  IntegerLit(0)，f() = f(0)，表达式位 () 即 0），登记「解析歧义」陈旧；
  31-③ VM 非容器切片异常载体——三面早已统一 MathaRuntimeError 同文案「切片操
  作不支持: int[1:2]」（31f 真化后编译面 raise_rt 与解释面同源），登记「VM 原
  生异常形态」陈旧；31f 旧锁同步加强（vm 面文案+类型同判）。**37b 块尾 Binding
  值模型收尾（36-② 退役 + 同族顺手真修）**：interp_matha 绑定求值let 无体臂
  (v, env)→(null, env) + interp.matha 同形（36-② 登记形态 { let x = 5 }）+
  表达式位块（求值程序/求值 程序 臂）尾值 `_块尾值` 映射（绑定/let绑定/
  let元组绑定尾不回传值——宿主 _BLOCK_TAIL_STMT_NODES 头三族；程序位顶层
  run_ast → 执行语句保持「程序值 = 尾表达式值」约定不映射——phase8pre gapfix
  程序值锁同源）——四形态三面 + VM² 同判 [None]；有体 let 尾 { let x = 10 in
  x * 12 } 与裸赋值尾 { x = 5 } 同族收敛（此前 mb/VM² 回传值 vs vm/hi None）。
  **37c 链式 let rec 互递归真化（32-⑩ 退役）**：interp.py 表达式位 LetBinding
  链头收集 body 链 rec 名建注册表压栈（`_rec_chain`）逐名预绑占位符，成员复用
  未填占位（_ref 未填守卫——32e 勘误保留：弹栈后同名恒新建、跨函数在途占位不串
  线）；块/程序入口预注册沿 body 链整链（`_preregister_rec_chain`——37c 前
  body is None 条件漏带体链，先定义闭包快照缺后定义名）；interp_matha/
  interp.matha 预绑链占位镜像 + 占位复用守卫——三面 + VM² 同判 [0]。
  **37d 字典自然键真化（36-① 退役）**：compiler.py `_literal_key`
  IntegerLit/FloatLit/BoolLit 原值入常量池（此前 int 键字符串化致 d[2] vm
  null）+ parser.matha `花括号种类` 数字/布尔首 token 冒号前瞻 → 字典（此前
  mb/VM² 误析集合）——int/float/bool/str 键 + d["2"] 反向 null 三面 + VM² 同
  判；boot 编译器/解释器/native 随既有路径自然同判零改动。
  **门禁**：全量 tests lane 两跑——run1 7825 过 + 4 红 + 1 skip 4363.42s（4 红
  全为 37b 首稿映射置 执行声明列表 尾泄漏程序位踩中的 phase8pre gapfix 程序值
  锁案——文件在修复前跑过；修复后定向复跑 gapfix+phase8a+bootstrap_host
  141/141 绿）→ 37b 收窄至表达式位 → run2 干净 7829 过 + 1 平台 skip
  4291.54s 零红；kernel_purity 14 + ast_vm_gap 11（快照零扰动无需重生成——
  指令码不变）+ golden 39/39 + dep_audit 39 内核文件 189 import 边 0 违规 +
  native_parity 38/39（0 失败，native 已知未实现 1 例不计分母）+ Track B
  selfhost_matrix --check 一致（快照零扰动——225 分类不变，语料不含四族真化形
  态）。算术闭合：7933 条件 = 7932 过（tests 7829 + purity 14 + ast_vm_gap 11
  + golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）= 7914
  （36 条件）+ 19（test_selfhost_language_phase37）。doc 同步：README（阶段 37
  段 + 测试文件 187 ×2）；ARCHITECTURE（本体量 33,433→33,436（+3 = 37d
  compiler.py `_literal_key` +6−3；interp.py 表达式位链注册与 matha/*.matha
  镜像不在 core_py_lines 口径）+ 阶段 37 节 + 测试文件 187）；CHANGELOG 阶段 37
  条目。登记不修三条（2026-11-22 收官实测，均有登记锁防漂移）：①vm/hi 输出尾
  块值 host 内部分歧（编译面语句尾 PUSH_NULL vs 解释面输出通道规则；
  test_37x_output_tail_block_value_registration 防漂移）②mb 面集合构造求值
  「未知表达式类型: 集合构造」（test_37x_mb_set_construct_eval_registration 防
  漂移）③37c 嵌套链同名成员 env 槽被内层占位覆写（注册表弹栈不还原 env——
  单调用形态三面同判锁 test_37c_nested_same_name_three_faces 防漂移）。退役五
  条：32-②（空括号 () 解析歧义）、31-③（VM 非容器切片原生异常形态）、32-⑩
  （链式 let-in 表达式互递归 vm [0] vs hi/mb 未定义变量）、36-①（vm 字典字面
  量非字符串键 d[2] null）、36-②（boot 块尾 Binding mb [5] vs vm/hi [None]）。
  承继：35-②（m3v 编译态 try/catch 不捕获运行期错误）+ 33-⑤（mb 词法器递归深
  度上限）+ 32-⑧⑫ + 31-⑧⑨ + 28-⑧ + 29-①⑥⑦ 维持原登记不修。

- **2026-11 阶段 36 收官（mb/boot 面收口批：四项登记分歧真化，35-① +
  34-②③⑤ 退役）**：方向拍板走推荐项「A：mb/boot 面收口批」（四项一
  批收官）。**36a 表达式位花括号 if**（34-② 退役）：boot parser.matha
  解析if表达式补花括号分支（宿主 _parse_if_expr_impl 语句形式分支同构：
  解析语句列表块体 + 期望右括号花；else 附着仅 否则 关键字，英文 else
  不消费；无 否则 假分支=null 33d 同形）+ interp.matha 求值 程序 臂
  （块执行取尾值，宿主 CodeBlock 块值模型同位）——六形态三面同判 +
  输出尾块值 [5, 6] + 语句位 if 花括号控制流中性维持。**36b mb 面块尾
  func 定义块值真化**（34-③ 退役）：interp_matha 执行语句/执行声明
  函数定义臂 (closure, env2) → (null, env2)（函数仍入 env 仅值面不回
  传，宿主 FuncDef 执行返 None 同构）+ interp.matha 双臂镜像——块值
  [None] 三面同判、blk_used `f()` [1] 维持。**36c boot 字典裸键真化**
  （34-⑤ 退役）：interp_matha/interp.matha 求值字典 `_字典键` helper
  （"变量" 键析为字符串键名，其余求值）——`{a: 1}` ≡ `{"a": 1}` 四面
  同判。**36d mb 表达式位 let 元组绑定真化**（35-① 退役）：
  interp_matha 求值let元组/绑定求值let元组 + `_解构绑定元组`（闭包
  标记 ["__closure__",参数,体,env] 跳参绑定镜像宿主，懒三元防 eager
  and/or 陷阱；错误「解构失败：期望 N 个元素，实际 <类型名>」四面同
  文案，FuncDef/Lambda → function 同判）+ 求值/执行语句/执行声明 三臂
  路由。boot 编译器零改动（_发射体 null/程序 臂与 _发射块末条 留值
  PUSH_NULL 宿主同构已具备；_发射字典键面已归一）。
  **门禁**：全量 tests lane 7810 过 + 1 平台 skip 4145.01s 首跑零红 +
  kernel_purity 14 + ast_vm_gap 11（快照零扰动无需重生成——src/ 零
  改动指令码不变）+ golden 39/39 + dep_audit 39 内核文件 189 import 边
  0 违规 + native_parity 38/39（0 失败，native 已知未实现 1 例不计
  分母）+ Track B selfhost_matrix --check 一致（快照零扰动——225 分类
  不变，语料不含四族真化形态）。算术闭合：7914 条件 = 7913 过（tests
  7810 + purity 14 + ast_vm_gap 11 + golden 39 + native 38 + dep_audit
  1）+ 1 skip（平台 skip 承继）= 7891（35 条件）+ 23
  （test_selfhost_language_phase36）。doc 同步：README（阶段 36 段 +
  测试文件 186 ×2）；ARCHITECTURE（本体量 33,433 不变——四片全在
  matha/{parser,interp_matha,interp}.matha 自举镜像不在 core_py_lines
  口径 + 阶段 36 节 + 测试文件 186）；CHANGELOG 阶段 36 条目。
  登记不修三条（2026-11-22 收官实测，均有登记锁防漂移）：
  ①vm 面编译路径字典字面量非字符串键（compiler `_literal_key`
  IntegerLit→"2" 字符串化 + INDEX_GET 缺键 null——`d[2]` vm null vs
  hi/mb "v"、`d["2"]` vm 命中；test_36x_vm_dict_intkey_registration
  防漂移）②boot 面块尾 Binding `{ let x = 5 }` 块值 mb [5] vs
  vm/hi [None]（34-③ 同族 Binding 尾未真化；
  test_36x_blk_tail_binding_registration 防漂移）③承继：35-②（m3v
  编译态 try/catch 不捕获运行期错误）+ 33-⑤（mb 词法器递归深度上限）+
  32-②⑧⑩⑫ + 31-③⑧⑨ + 28-⑧ + 29-①⑥⑦ 维持原登记不修。退役四条：
  35-①（mb 表达式位 let 元组绑定 honest reject）、34-②（mb 表达式位
  if 无 then 解析拒绝）、34-③（func 体块尾 mb 块值 '<function>'）、
  34-⑤（boot 字典裸键析为变量引用）。

- **2026-11 阶段 35 收官（自举解构贯穿：UNPACK_SEQ 长度守卫四执行体 + boot
  编译器 for 解构发射真化，34-①④ 同根退役）**：主线拍板走推荐项「自举
  解构贯穿」（32-② 受控切片模式延续——S1 运行时面先行、S2 发射面后切）。
  **35a S1 统一解构语义四执行体**（序列 = List/Tuple 且长度精确等于目标数，
  否则诚实报错「解构失败：期望 N 个元素，实际 <类型名>」，八族类型名
  list/tuple/int/float/bool/str/dict/NoneType/function）：①vm 面 0x57 处理器
  严格化（此前越界补 None、非序列漏出 Python len() TypeError；Closure →
  "function"——34-④ 退役）②hi interp.py let 元组绑定守卫（语句位此前非序列
  静默不绑定假成功→下游未定义变量、短元组补 None；表达式位此前仅 tuple、
  短元组补 None、异文案；扩 List/Tuple 同判；FuncDef/Lambda 节点与
  ("__closure__",…) 标记元组 → "function"）③vm.matha 解包守卫（懒三元 合长，
  防 eager and/or 陷阱）+ `_解构类型名`（VM² 闭包 ["__闭包__",…] 3 元列表
  标记 → "function"）④native unpack 严格化（si_n_* 静态类型名 + int_to_str
  运行期拼消息，try/catch 可捕获 + 未捕获 rc=1 stderr——旧 全 None/字符串
  逐字节解构/越界补 None 路径退役；test_native 解构节 3 宽松锁改 4 诚实锁）。
  **35b S2 boot 编译器 for 解构发射真化**（34-① 退役）：compiler_matha
  `_分配循环变量` 收窄单变量 + `_分配循环变量们`/`_分配循环位置们` 名单归一
  逐名折叠（宿主 _emit_for_stmt names 归一 + var_ts 镜像）+ `_for循环码`
  UNPACK_SEQ n 发射 + `_存解构逆序` 逆序存储（宿主 reversed(var_ts) 镜像，
  `_存储元组全局逆序` 同协议）；实现踩坑一记：UNPACK_SEQ 必须在调用位发射
  （首稿置于 _存解构逆序 内致 stage3 缺 87 指令、下游栈欠载 LOAD_GLOBAL 池
  越界——parity 探针抓获即修）；单变量 for 字节码零变化（parity 回归锁）；
  五语料（单变量/字典对/三变量/局部函数/元组对）stage2↔stage3 逐位一致 +
  M3V 运行面真跑。phase34 两锁按真化退役改锁：vm 宽松登记锁 →
  test_34e_for_pair_fail_vm_true、编译面诚实拒绝锁 →
  test_34e_boot_compiler_pair_emits_unpack_seq（UNPACK_SEQ 发射 + 逆序存储锁）。
  **门禁**：定向批次先行（mbc_vm_matha/tuple s1·s2/mbc_bootstrap/
  stage4_closure/phase32/33/bootstrap_host 996 过 2438.37s）+ 全量 tests lane
  7787 过 + 1 平台 skip 4233.55s 首跑零红（34 收官 run2 两红此跑即净：
  m5 tmpdir 伪影与 doc_facts 均已事后修复转绿）+ kernel_purity 14 +
  ast_vm_gap 11（快照零扰动无需重生成）+ golden 39/39 + dep_audit 39 内核
  文件 189 import 边 0 违规 + native_parity 38/39（0 失败，native 已知未实现
  1 例不计分母）+ Track B selfhost_matrix --check 一致（快照 225 分类零扰动
  ——语料无语句位 let 元组解构，35a hi 守卫不翻分类）。算术闭合：7891 条件
  = 7890 过（tests 7787 + purity 14 + ast_vm_gap 11 + golden 39 + native 38
  + dep_audit 1）+ 1 skip（平台 skip 承继）= 7846（34 条件）+ 45
  （test_selfhost_language_phase35 42 + test_native 解构节净 +1 + 34 收官
  run2 两红事后转绿 m5/doc_facts +2）。doc 同步：README（阶段 35 段 +
  测试文件 185 ×2）；ARCHITECTURE（本体量 33,417→33,433（+16 = 35a vm.py
  UNPACK_SEQ 守卫 +7 / native `_emit_unpack_seq` 严格化重写 +9 净；
  src/interp.py let 元组守卫 +43−26 与 boot 镜像 matha/{vm,compiler_matha}
  .matha、新锁档不在 core_py_lines 口径）+ 阶段 35 节 + 测试文件 185）；
  CHANGELOG 阶段 35 条目。登记不修三条（2026-11-22 收官实测，均有登记锁防
  漂移）：①mb 面表达式位 let 元组绑定 honest reject「未知表达式类型:
  let元组绑定」（boot 求值面暂不支持，不假编译——语句位 let 元组 boot 面
  32 已落地）②m3v 编译态 try/catch 不捕获运行期错误（除零/越界/未定义变量/
  解构失败全族一致上抛——vm.matha 解释器循环未实现异常帧机制，35b 探针踩中
  既有边界非本阶段引入；vm/hi/mb/native 四面 try/catch 捕获正常）③承继：
  34-②③⑤（mb 表达式位 if 无 then/func 体块尾 mb 块值/boot 字典裸键）+
  33-⑤（mb 词法器递归深度上限）+ 32-②⑧⑩⑫ + 31-③⑧⑨ + 28-⑧ +
  29-①⑥⑦ 维持原登记不修。退役两条：34-①（boot 编译器 for 解构目标暂未
  支持）、34-④（vm 编译路径 UNPACK_SEQ 宽松补 null）。

- **2026-11 阶段 34 收官（语言面继续收敛：六项登记分歧全族真化）**：两项
  拍板全走推荐项（①34c 统一 boot 中文文案 ②34f hi→None 对齐 vm）。
  **34a 尾逗号全族**（33-① 退役）：33a 单元素机制扩展——多元素 `(1, 2,)`
  与调用位 `f(1, 2,)` boot 面改发宿主精确文案「期望表达式
  (got PUNCT_RPAREN ')')」（解析括号消解 逗号分支全族守卫；boot 解析
  错误输出行呈现不上抛）；列表尾逗号 `[1, 2,]` 三面合法不误伤。
  **34b 语句位 if `[` 路由**（28-⑦/33-② 退役）：宿主 `_parse_if`/
  `_parse_while` 条件位加 `_in_cond_value` 值语境旗标（27f 同款先例）——
  `if [1] { … }` 条件析为列表字面量而非输出命令，vm 面此前漏出条件值
  `outs=[1,'x']` vs hi/mb `['x']` 三面分歧退役；boot 面既有正确零改动。
  **34c in 左侧四面同文案**（33-③ 退役）：字符串容器+非字符串左侧
  统一 boot 中文文案「in 左侧需为字符串，实际 int/list/NoneType」——
  vm `_op_in` + hi（interp.py 二元运算 in 臂）+ native（非零退出 +
  stderr 同文案，try/catch 可捕获）+ VM² 镜像（interp.matha 补
  `_类型名` 小写面 helper，30c 同构）。
  **34d slice 元组 vm 收敛对齐宿主**（33-④ 退役）：vm `_builtin_slice`
  容器守卫（仅 str/list 透传，其余「slice() 需要字符串或列表」）+
  native `fn:slice` 容器守卫（err_slice_dom，try/catch 可捕获）；
  str/list 透传与下标切片共用路径不受影响（元组切片返元组维持）。
  **34e boot for (k,v) 多变量目标真化**（32-⑨ 退役）：boot parser.matha
  解析for_stmt 括号解构目标（"变量" String=单变量 | List=名单，
  解析for目标_rest/解析for尾 共用尾段）+ interp_matha 执行for循环
  `_解构绑定/_解构绑定进`（宿主 `_exec_for_stmt` 镜像：Tuple/List
  且长度匹配逐位绑定，否则「解构失败：期望 N 个元素，实际 <类型名>」）
  + 28b parity conv 面 boot "变量" 名单归一；列表对/元组对/字典源
  三面+VM² 同判。boot 编译器发射面（_分配循环变量）List 目标诚实拒绝
  「boot 编译器 for 解构目标暂未支持」——UNPACK_SEQ 自举镜像未做，
  解释器面真化、编译面显式拒绝不假编译（登记①）。
  **34f hi 面 func 值求值真化**（32-⑪ 退役）：src/interp.py _eval 补
  FuncDef 臂 → None（vm 面同判；mb 面表达式位 if 无 then 解析拒绝
  维持登记②）；func 体块尾 func 定义 mb 块值 '<function>' vs vm/hi
  None 块值模型分歧维持登记③。
  **门禁**：tests lane 两跑——run1 7742 过/1 skip/3349.17s 2 红，全踩中
  34d `_builtin_slice` 开放端缺界 None 误杀（下标切片 l[1:] 发射面
  slice(c)(1)(None)：VM 面下标切片经 slice 内建而 hi 走解释器自身路径、
  BUILD_SLICE 直路原生容忍 None——test_mbc_vm_matha parity l[1:] +
  test_stage4b_embedded_vm_squared），修复为 None 放行按 Python 切片语义
  （vm.py `_builtin_slice` +3；修复后四形态探针 vm/hi/mb 三面一致：
  列表/字符串开放端、元组下标切片返元组、slice() 元组实参三面同报错），
  定向复跑 mbc_vm_matha/stage4/phase34/curried 197/197 绿；run2 干净
  7742 过 + 1 平台 skip 3856.83s 2 红：m5 tmpdir 伪影（write_file 父
  目录缺失，单跑 18.34s 绿，非产品缺陷）+ doc_facts 本体量过期（切片
  修复 vm.py +3 行，33,414→33,417 更新后 18/18 绿）；quick lanes：
  kernel_purity + ast_vm_gap 25 绿（快照零扰动无需重生成）+ golden 39/39
  + dep_audit 39 内核文件 189 import 边 0 违规 + native_parity 38/39
  （0 失败，native 已知未实现 1 例不计分母）+ Track B selfhost_matrix
  --check 一致 + doc 锁子集 434 绿。锁面漂移三处提前收口（tests lane
  前完成）：32-⑨ 旧锁 test_32a_dict_for_kv_boot_parser_honest_reject
  按真化退役惯例改锁 boot 面同判 'ab'；test_31g_snapshot_classes 按
  33 收官 timeout 3→0 改锁 all-ok〔33 门禁 tests lane 先于快照重生成，
  改锁滞后至此收口，非缺陷〕；phase33 33c/33h 登记锁改锁退役。
  test_selfhost_language_phase34 27 项新档：
  34a 尾逗号全族三面+列表正控 / 34b if[` 三面+VM² / 34c in 左侧
  四面+正控 / 34d slice 四面+透传+下标正控 / 34e 五形态三面+VM²+
  编译面诚实拒绝+vm 宽松登记锁 / 34f vm/hi None+mb 登记锁×2+
  语句位中性回归 / 34x 裸键登记锁；test_native in 节+slices 节改锁）。
  算术闭合：7846 条件 = 7845 过（tests 7742 + purity 14 + ast_vm_gap 11
  + golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）
  = 7819（33 条件）+ 27（test_selfhost_language_phase34）。
  doc 同步：README（阶段 34 段 + 测试文件 184 ×2）；ARCHITECTURE
  （本体量 33,290 → 33,417（+127 = 34b parser.py +17 / 34c vm `_op_in`
  +4 + native in 守卫与 err 串 / 34d vm `_builtin_slice` +14−1〔含
  开放端 None 放行 +3〕+ native fn:slice 容器守卫 + err_slice_dom；
  34c hi 臂与 34f FuncDef 臂 src/interp.py +8 与 matha/*.matha 镜像
  不在口径）+ 阶段 34 节 + 测试文件 184）；CHANGELOG 阶段 34 条目。
  登记不修五条（2026-11-21 收官快照实测，均有登记锁防漂移）：①boot
  编译器 for 解构目标暂未支持（UNPACK_SEQ 自举镜像未做——mb/VM² 解释
  面真化、stage3 编译面显式拒绝）；②mb 面表达式位 if 无 then（`if 1
  { … }` 花括号形态）解析拒绝「期望 then/:/elif/else，实际 {」（boot
  解析器表达式位 if 仅 then 形态）；③func 体块尾 func 定义 mb 块值
  '<function>' vs vm/hi None（宿主块值模型「输出入 outputs、块值
  None」vs boot 面块值函数值——32b 同族分歧）；④vm 面编译路径
  UNPACK_SEQ 长度不匹配宽松补 null（vm.py 31b 引入，解释面 hi/mb
  诚实报错 解构失败——编译面 vs 解释面解构语义分歧，修复需 UNPACK_SEQ
  长度守卫 + native unpack_rt 镜像，超出本切片）；⑤boot 字典字面量
  裸键 `{a: 1}` 析为变量引用（未定义变量 'a'）vs hi 面字符串键
  （34e 探针踩中附带发现；语料/文档约定引号键 `{"a": 1}` 三面一致）。
  退役六条：33-①（多元素/调用位尾逗号 boot 通用文案）、28-⑦/33-②
  （语句位 if `[` 条件析为输出命令）、33-③（in 左侧文案分歧）、
  33-④（slice() 元组 vm 宽松返元组）、32-⑨（boot for 多变量目标
  未支持）、32-⑪（hi 面 func 值 FuncDef 未实现求值）。
  承继：33-⑤（mb 词法器递归深度上限）+ 32-②⑧⑩⑫ + 31-③⑧⑨ +
  28-⑧（Dijkstra 距离桩）+ 29-①⑥⑦ 维持原登记不修。

- **2026-11 阶段 33 收官（mb 面分歧收敛：六项 mb↔宿主语义/文案分歧三面
  （vm/hi/mb）+ VM² 收口）**：四项拍板全走推荐项（①33a boot 诚实拒绝
  对齐宿主 ②33b 全族对齐 Bool ③33c 四面同文案 ④33d 顺手真修 hi）。
  **33a 单元素尾逗号 `(1,)` 诚实拒绝对齐宿主**：boot 解析括号消解 逗号
  分支补右括号守卫（宿主=SPEC 同文案带 L:C 前缀；boot 解析错误以输出行
  呈现不上抛）——32-① 退役。
  **33b mb 比较族九臂与 not 返 真/假 Bool + 条件路由真值归一**：应用运
  算全族改 真/假、求值 if/语句 if/while 经 真值 helper（空容器/零/null
  falsy）——32-④⑦ 退役；副产品 mb 面提速：golden 37/38/interp.matha
  三 timeout 档 600s 预算内真跑完成。
  **33c `in` 成员判断四面真化**：vm `_op_in` 容器守卫 + native 容器守卫
  （raise_rt 可捕获，旧锁 test_in_non_container_is_false 按真化退役惯例
  改锁诚实报错）+ mb `_成员判断` + VM² interp.matha 镜像；List/Tuple/
  Dict/Str 命中/未中 + 非容器右侧「in 右侧需为序列/集合/字典，实际 int」
  四面同文案——32-③ 退役。
  **33d hi 面 if 无 else 条件假 → null**：src/interp.py IfExpr/IfStmt
  else 缺失臂补 None（此前崩 NoneType；VM 面 None 同判）。
  **33e mb type_of/_to_tuple 注册真化 + sum 累加器 0 起**：应用内建委托
  宿主实现（闭包安全包装注册）+ stdlib list_sum 累加器 0 起（sum([])=0
  Int）——32-⑤⑥ 退役。
  **33h slice 内建字符串臂真化**（收官探针踩中顺手真修）：mb 应用内建实
  slice 臂此前无条件走 list_slice、字符串实参产出字符列表（split 块变
  ['a'] 形）；String 实参改走 31f `_切片值` 字符串臂（负回绕/端钳 Python
  语义）、List 维持 list_slice、Tuple/其他诚实报错「slice() 需要字符串
  或列表」（宿主=SPEC 同文案）；根因链：33b 提速后 golden 38 语料 600s
  预算内首次真跑完成、Track B timeout→differ 漂移显形此根因，修复归等。
  **门禁**：首跑 tests lane 因 mid-edit 状态 + tail 管道缓冲伪影（0 字
  节输出 + 孤儿进程滞留）作废，TaskStop 收拾后干净重跑——tests 7715 过
  + 1 平台 skip 3934.02s。quick lanes：kernel_purity 14 + ast_vm_gap 11
  + golden 39/39 + dep_audit 39 内核文件 189 import 边 0 违规 +
  native_parity 38/39（0 失败，native 已知未实现 1 例不计分母）+ Track B
  selfhost_matrix --write 重生成 --check 两跑一致（快照 225：双面一致
  209 / 诚实 differ 3（08_auto_optimize/data_pipeline/neural_network 对
  象身份/未定种子如实分歧）/ boot_err 0 / both_err 13 / timeout 3→0 清
  零——timeout 档全数真跑完成，分类面不复存在）。
  算术闭合：7819 条件 = 7818 过（tests 7715 + purity 14 + ast_vm_gap 11
  + golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）=
  7791（32 条件）+ 28（test_selfhost_language_phase33 24 + test_native
  in 节改锁+元组成员判断 1→5 面 +4）。
  doc 同步：README（阶段 33 段 + Track B 快照句 + 测试文件 183 ×2）；
  ARCHITECTURE（本体量 33,224 → 33,290（+66 = 33c native 容器守卫 +57 /
  vm `_op_in` 容器守卫 +10−1；33d src/interp.py +8 不在口径）+ 阶段 33
  节 + 测试文件 183）；CHANGELOG 阶段 33 条目；Track B 快照重生成。
  登记不修五条（2026-11-21 收官快照实测，均有登记锁防漂移）：①多元素尾
  逗号 `(1, 2,)` 与调用位 尾逗号 boot 维持通用文案「期望表达式，实际 ）」
  （33 只收单元素吞没位）；②语句位 if 以 `[` 开头的字面量条件被宿主解
  析器析为输出命令（IfStmt.cond=Output，vm 面旁路输出条件值 vs hi 面不
  求值——既有解析器形态分歧，与 33b 真值语义无关）；③字符串容器+非字符
  串左侧 in 文案分歧（vm/hi Python TypeError 形态 vs mb/VM²「in 左侧需
  为字符串」vs native 静默返 False——33c 只收非容器右侧）；④slice() 元
  组实参 vm 面宽松返元组 vs hi/mb 诚实报错（native 走 build_slice 共用
  路径）；⑤mb 词法器递归深度上限（matha_bootstrap harness 限制——库级
  boot 判据走 VM²，非产品分歧；33h 往返锁三面 vm/hi/VM² 口径）。
  退役七条：32-①（单元素尾逗号静默吞没）、32-③（mb in 未知运算符）、
  32-④（mb 比较返 1.0/0.0）、32-⑤（mb type_of/_to_tuple 未注册）、
  32-⑥（mb sum 返浮点）、32-⑦（mb 空元组真值为真）、31-⑦（timeout 3
  归因——三档全部真跑完成，分类面不复存在）。
  承继：32-②（空括号 ()）⑧⑨⑩⑪⑫ + 31-③（VM 非容器切片 TypeError vs
  hi/mb MathaRuntimeError 原生形态）⑧⑨（both_err 13 构成 / differ 3 维
  持）+ 28-⑦⑧（语句位 `[` 路由一致性 / Dijkstra 距离桩）+ 29-①⑥⑦
  （native dict_put 不可扩容 / 29e opt-in 中段跳过 / mb.interpret
  breaking 注记）维持原登记不修。

- **2026-11 阶段 32 收官（语言收敛与元组真化：五片语言收敛 + ② 元组真化受控
  切片 S1/S2）**：五片全落；② 拍板「以维持登记为基础，以切片真化的方式进行
  中心工程推进，必须拆分成可回滚受控切片，逐个验证与安全进行」。
  **32a VM 字典迭代四面归一**：宿主编译器 for/推导三发射位统一经
  `LOAD_GLOBAL "_迭代源"` + CALL 1（get/append 融合 CALL 2 守恒，B09 形状
  锁随之改锁：for [1,2,1]→[1,1,2,1]、推导 [1,2,2,1]→[1,1,2,2,1]、遮蔽
  [1,1,1,1]→[1,1,1,1,1]）+ vm.matha 镜像 + native iter_source（dict →
  ('k',v) 对）——31-①「VM 面字典源迭代 KeyError(0)」退役；BUILD_SLICE
  不可切片守卫三面同文案。
  **32b hi 面 ChainStmt 块尾链真化**（块值模型对齐，三面同判）——31-⑤
  退役。**32c boot 编译器推导发射真化**：单/多 for+if（31-⑥「boot 推导
  发射未支持」退役；28c parity 全语料逐位一致）。
  **32d mb 面 str 通用化**：Bool/null/容器/函数渲染 + 自举闭包守卫
  （28-⑨「stdlib str 数字专用」退役）——副产品真修：term_engine 显示值
  Bool 臂此前委托 str，CPython 对齐（True/False）击穿终端显示语言 12c
  真/假 产品约定，显示值 Bool 臂自持渲染（`if v then "真" else "假"`）
  修复（嵌套经 _列表文本/_键值文本 递归一并覆盖）。
  **32e let rec 互相递归三面贯穿**：hi 预注册占位 + VM 预发盒 + boot 待填
  盒镜像——29-②「boot 面互相递归 let rec 前向引用报未定义变量」退役。
  **32-② S1 BUILD_TUPLE 运行时指令面**：0x65=101（TYPE_TUPLE=13），vm/
  vm.matha/native 元组对象三执行体直注执行，零发射零行为变化。
  **32-② S2 发射面切换**：宿主+boot 编译器元组字面量 → BUILD_TUPLE
  （31-②「VM 元组切片返 List/元组按列表处理」退役）；native 消费面语料
  回归；stdlib/vm.matha str 元组渲染臂；`-` 容器守卫四面同文案。验证链：
  m4 元组锁 + stage4c 拼接编译双编译器 282 条目函数表逐位一致 + fixpoint
  763.66s + parity 定点 + 重档批次 1171 过（2670.41s）。
  配套根因修复：自举编译器同名函数重定义出口去重——宿主 mod.functions 为
  dict（同名重定义保首现序取末值），自举镜像逐次 append 列表，拼接编译
  （stdlib+vm.matha 千级函数表）逐次线性扫描致 MemoryError；出口一次性
  双遍完成（后向前 dict_put 收末值 → 前向按首现序发射）。实现踩坑两记：
  字面 `{}` 在 Matha 解析为空集合构造非空字典（空字典必须
  dict_from_pairs([])，compiler_matha 87-88 行注记早已警示，实现首稿仍
  踩）；倒序收末值会以早者覆盖晚者（末值表必须前向扫描）。
  **门禁两跑**：run1 全量 tests lane 7681 过 + 1 skip 3841.24s——6 红全
  为真缺陷/锁漂移（非 31 式车道并行伪影）：3 红 test_matha_term_12c
  显示值 = 产品缺陷（见 32d 副产品，修复）；3 红 test_curried_builtin_paths
  B09 = 32a 形状锁漂移（改锁）；定向复跑 434/434 绿（12c/curried/12e/
  13a/13b/13c/desktop/semantic_parity19 + parity 全语料 188 +
  ast_vm_gap 11）。run2 干净全量 tests lane 7687 过 + 1 平台 skip
  3857.42s。quick lanes：kernel_purity 14 绿 + ast_vm_gap 11 绿（快照
  重生成：指令码 35→36 ×2 行 + BUILD_TUPLE 行，78 节点/59 发射/19 无码/
  0 阻塞缺口/语料与节点类型零变化）+ golden 39/39 + dep_audit 39 内核
  文件 189 import 边 0 违规 + native_parity 38/39（0 失败，native 已知
  未实现 1 例不计分母）+ Track B selfhost_matrix --check 一致（快照 225：
  双面一致 206 / 诚实 differ 3 / boot_err 0 / both_err 13 / timeout 3
  维持）。
  算术闭合：7791 条件 = 7790 过（tests 7687 + purity 14 + ast_vm_gap 11 +
  golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）= 7716
  （31 条件）+ 75（test_tuple_instruction_s1_phase32 11 +
  test_tuple_emission_s2_phase32 44 + test_selfhost_language_phase32 20）。
  doc 同步：README（阶段 32 段 + Track B 快照句 + 测试文件 182 ×2）；
  ARCHITECTURE（本体量 32,951 → 33,224（+273 = mbc 四文件 compiler +42/
  native +207/opcodes +1/vm +23；32b/32e 宿主 interp.py +61−11 与自举镜像
  matha/*.matha、三新锁档不在口径）+ 阶段 32 节 + 测试文件 182 +
  指令码 36）；CHANGELOG 阶段 32 条目；ast_vm_gap 快照重生成。
  登记不修十二条（2026-11-21 收官快照实测，S2 元组真化探测取证）：①尾逗号
  元组 `(1,)` vm/hi ParseError vs mb 静默误析 1；②空括号 `()` 双面诚实
  0 解析维持；③mb 面 `in` 未知运算符（vm/hi 支持）；④mb 面 `==` 返回
  1.0/0.0（vm/hi 返布尔）；⑤mb 面用户域符号 type_of/_to_tuple 未定义
  （30e carve-out 承继）；⑥mb 面 sum 返回浮点（vm/hi 返整数）；⑦mb 面
  空元组真值为真（vm/hi 空容器为假）；⑧native 跨型 +/- 返 null（既有
  约定维持）；⑨boot 面 `for (k,v) in` 多变量目标未支持（诚实报错维持）；
  ⑩链式 let-in 表达式互递归 vm [0] vs hi/mb 未定义变量（形态分歧）；
  ⑪hi 面 func 值（FuncDef 节点）未实现求值；⑫use 标准库装载面走 sweep
  驱动器（裸 bootvm 边界维持）。
  退役七条：29-②（互相递归 let rec）、31-①（VM 字典迭代 KeyError）、
  31-②（元组按列表处理）、31-④（mb str []）、31-⑤（hi ChainStmt）、
  31-⑥（boot 推导发射）、28-⑨（stdlib str 数字专用）。
  承继：31-③（VM 非容器切片 TypeError vs hi/mb MathaRuntimeError 原生
  形态——BUILD_SLICE 守卫三面文案已同、异常载体形态维持登记）+ 31-⑦⑧⑨
  （timeout 3 归因 / both_err 13 构成 / differ 3 维持）+ 28-⑦⑧（语句位
  `[` 路由一致性 / Dijkstra 距离桩）+ 29-①⑥⑦（native dict_put 不可
  扩容 / 29e opt-in 中段跳过 / mb.interpret breaking 注记）。

- **2026-11 阶段 31 收官（语言完备与判定面收敛：func-> 简写 + 双 for 推导 +
  切片/守卫/字典迭代 + sweep 预装载装配）**：六片全落；31g 拍板维持 sweep
  单预算 600s 驱动器（不拆双面预算——快照类形不翻动，timeout 如实分类）。
  **31a func 定义 `->` 可选**：宿主/自举 parser `func 名(参) = 体` 无返回
  类型标注简写（带 `->` 形态不变，func_type=None 纯元数据），29-⑧「func
  必须写 `->`」退役；三面（vm/hi/mb）+ 双编译器字节码对拍。
  **31b 双 for 推导**：`[e for a in xs for b in ys if c...]` 宿主
  ListComp.gens + _parse_comp_tail 统一收口 + MBC 嵌套循环发射（零新
  opcode）+ boot 解析/求值面真化——30d 双 for 诚实报错分歧条退役（phase-30
  锁 test_double_for_boot_honest_error → test_double_for_boot_truthified
  真化退役，双面 [[11,12]] 同值；VM 面由 phase-31 锁）。
  **31c 语句位括号链**：块体位 `[x] >> [y]` 链收集 vm/mb 面真化（boot
  解析输出语句镜像宿主 _parse_mech_stmt）；顶层双面语法拒绝维持。
  **31d 调用守卫 + 字典/字符串 for**：不可调用值（5/[]）三面诚实报错文案
  对齐「不可调用的值： N」；字典源迭代产出 ('k',v) 元组对（boot 面此前
  静默空跑假成功清除）+ 字符串逐字符迭代三面。
  **31f 切片求值真化**：列表/字符串/元组切片 12 形态三面同判——30-④
  「boot 切片表达式求值未支持」退役。
  **31e sweep 预装载装配 + 31g 判定面**：scripts/selfhost_matrix.py
  `_manifest_preloads`/`_assemble_source`（BOM 剥离 + 预装载 prepend）——
  golden manifest 双轨同源真跑资源装载 + warmup barrier
  `map_async(_warm, workers*2)` 预热 + 单文件预算 120→600s。
  **门禁**：tests lane 7612 过 + 1 skip 6895.89s（首跑 7 红：6 native 面
  PermissionError/OSError 22 = 与 native_parity 车道并行编译 exe 的争用
  伪影，隔离复跑 4 文件 909/909 绿；1 真锁漂移 = phase-30 双 for 诚实报错
  锁随 31b 真化退役更新，复跑 17/17 绿——非产品缺陷）；quick lanes：
  kernel_purity 14 绿 + ast_vm_gap 11 绿（快照重生成——唯一行变化
  DictLiteral used_in 21→22，totals 与 30 逐项一致：78 节点/59 发射/19
  无码/0 不认识/0 阻塞缺口/指令码 35/语料 230/解析失败 0）+ golden 39/39 +
  dep_audit 39 内核文件 189 import 边 0 违规 + native_parity 38/39（0
  失败，native 已知未实现 1 例不计分母）+ Track B selfhost_matrix --check
  一致（快照 206/3/0/0/13/3）。
  算术闭合：7716 条件 = 7715 过（tests 7612 + purity 14 + ast_vm_gap 11 +
  golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）= 7697
  （30 条件）+ 19（test_selfhost_language_phase31）。doc 同步：README
  （阶段 31 段 + 测试文件 179 ×2）；ARCHITECTURE（本体量 32,951 = 32,859 +
  92：31a-31f 宿主 parser/ast_nodes/mbc compiler/interp 四文件净增 interp
  计外；阶段 31 节 + 测试文件 179）；CHANGELOG 阶段 31 条目；ast_vm_gap +
  selfhost_matrix 快照重生成。
  登记不修十条（2026-11-20 收官快照实测）：①VM 面字典源迭代 KeyError(0)
  （for 语句 + 推导式同源；interp 双面产出 ('k',v) 元组对）——
  test_31b_comp_dict_pairs_interp_faces / test_31d_for_dict_pairs_interp_
  faces 锁形；②VM 面元组切片返 List（BUILD_LIST 发射；hi/mb 保 Tuple）——
  test_31f_slice_tuple_pairs_interp_faces；③VM 面非容器切片原生 TypeError
  （hi/mb MathaRuntimeError 切片操作不支持： int[1:2]）——
  test_31f_slice_noncontainer_honest 双面诚实形态锁；④mb 面 str([]) 渲染
  <?>?（28-⑨ stdlib str 数字专用同源）——test_31d_uncallable_empty_list_
  honest mb 面文案存在性锁；⑤宿主解释器面 ChainStmt 暂不支持求值（块值
  模型分歧；vm/mb 面块体位链真化对照，顶层双面语法拒绝维持）；⑥boot 编译器
  推导发射未支持（诚实报错「未支持的表达式类型 列表推导」——VM 面推导经
  宿主编译器发射、boot 面推导求值经 interp_matha）——
  test_31b_boot_compiler_honest_reject 锁；⑦timeout 3 归因（拍板维持单
  预算 600s）：matha/interp.matha boot 面真重档——探针不设预算 >3.1h CPU
  仍未完成（实测 CPU 11395s 仍在算），host 面单跑 1.2s，共享预算 boot 先
  耗尽 host 未及跑 → timeout/timeout 如实分类；golden 37/38 装载真跑后
  双面真算 >600s 同判（30 时 both_err「未定义变量」→ 31e 装配后真跑转
  timeout，诚实分类非退步）；stdlib_symbols 120→600s 预算内 ok（30-②
  退役）；⑧both_err 13 构成：错误语料 10（golden 12/13/14/24/25/26/27/
  28/29/31 双端如实报错）+ bootstrap_full_test（boot 未定义变量
  'dict_from_pairs' vs host 未定义变量 '不折叠'）+ bootstrap_matha（boot
  Partial len TypeError vs host 属性访问失败 str.类型）+ bootstrap_test
  （双端同文案 不可调用的值： <?>?）——bootstrap 三档维持 30 形态；
  ⑨differ 3 维持（08_auto_optimize/data_pipeline/neural_network——对象
  身份/未定种子如实分歧）；⑩承继：29-①②⑥⑦ + 28-⑦⑧⑨ + 29e opt-in
  中段跳过维持原登记。
  退役五条：29-⑧（func-> 简写）、30d 双 for 诚实报错分歧条、30-④（boot
  切片未支持）、30-② timeout 2 之 stdlib_symbols（37/38 由 both_err 转
  timeout 如实重分类）、both_err golden 36-39（31e 预装载装配——36/39
  →equal、37/38 →timeout 真跑）。

- **2026-11 阶段 30 收官（自举执行面收口：Track B boot_err_host_ok 61 → 清零
  + 驱动器级域符号注入）**：五片全落，30e 拍板①驱动器级注入（宿主真实现经
  28d register_builtin 端口，非桩件；判定语义 = 同一内建面下 boot 解释器 ≡
  宿主解释器）。
  **30a 执行分派收口**：interp_matha.matha 求值/执行语句分发表扩（读取块/
  设值/跳出/继续/返回语句真化 + 结构体/枚举/属性路由 + 下标/切片求值支）——
  29-④「boot 未支持节点组」退役。
  **30b use 跨模块收口**：导入绑定 模块名表扩 + 非函数符号合并——29-③
  「Token 跨模块未找到」（bootstrap_test/interp/nl_lexer 三语料）退役。
  **30c 双面错误文案对齐**：除零/取模/整除/不可调用/类型名大小写 boot 面
  与宿主逐字一致。
  **30d 语法缺口真化**：列表推导 `[e for t in it if c...]` boot 解析/求值/
  编译三面（test_parser_parity_phase28 conv 面 +1 列表推导节点 + golden 35
  语料入对拍集；顶层裸 `[expr]` → 输出 宿主 _parse_output 镜像）+ 类型索引
  `list[类型]` + sqrt 一元前缀 + stdlib_symbols 构造（bootstrap_test_v2
  boot_err「索引操作不支持: list[类型]」释放）。
  **30e B 轨驱动器级域符号注入**：scripts/selfhost_matrix.py
  inject_domain_builtins——宿主 Interpreter().builtins 全表面 sorted 确定性
  经 28d register_builtin 端口入 boot env（可调用值 _adapt_callable 柯里化
  适配 n-arity、常量值仅绑 env、skip=boot 自有面名与宿主 defer_to_plugins
  「内核同名内核胜出」同口径、清单漂移符号诚实跳过保持 boot_err）+ 资源预
  装载（资源_加载/资源_成长 资源形态识别）+ 跨文件 use 依赖装载
  （_ensure_module）。关键根因修复：_CHAIN_CRITICAL 保留名 `type_of` 双面
  不覆盖——宿主同名 type_of 对 VM Closure 返 "Unknown" 会击穿链代码
  应用函数 的 "Function" 分支、use 导入的链命名空间函数全体不可调用
  （「不可调用的值： <?>?」，stdlib str 数字专用 28-⑨ 同源）——boot 语义
  = VM _builtin_type_of（Closure → Function 恰是 boot 面应有分类）。结果：
  61 boot_err_host_ok 全部释放（读取块 23/未找到模块 13/未定义变量 12/设值
  6/try 4/IndexError 3 + 域符号族 自主_调试/自主_优化/自主_成长/资源_加载/
  资源_成长/软件_构建）——29-⑤「B 轨登记不扩面」退役。
  **附带产品缺陷真修**：宿主 type_of(null) 返 "Unknown" → 补 None 分支返
  "Null"（src/interp.py builtin_type_of，对齐 VM _builtin_type_of——Track A
  锁面实测揭出的双面分歧）。
  **门禁**：tests lane 7593 过 + 1 skip 3696.86s 首跑零红（= 7535（29）+ 58：
  domain 29 + syntax 17 + errmsg 11 + parser parity 列表推导语料面 +1）；quick
  lanes：kernel_purity 14 绿 + ast_vm_gap 11 绿（快照无需重生成——30 链改无
  节点类型/发射位变化，78 节点/59 发射/19 无码/不认识 0/阻塞缺口 0/指令码 35/
  语料 230/解析失败 0 不变）+ golden 39/39 + dep_audit 39 内核文件 189 import
  边 0 违规 + native_parity 38/39（0 失败，native 已知未实现 1 例不计分母）
  + Track B selfhost_matrix --check 一致（快照按最终源 --write 重生成后复跑
  203/3/0/17/2 两跑稳定；type_of Null 分支修复前后分类零变化）。
  算术闭合：7697 条件 = 7696 过（tests 7593 + purity 14 + ast_vm_gap 11 +
  golden 39 + native 38 + dep_audit 1）+ 1 skip（平台 skip 承继）= 7639（29
  条件）+ 58。doc 同步：README（测试文件 175→178 ×2 + 执行面收口段）；
  ARCHITECTURE（本体量 32,859 不变——30 改动全在 matha/ 镜像与 scripts/
  selfhost_matrix.py，宿主 type_of null 分支 src/interp.py +2 行不在
  core_py_lines 口径；阶段 30 节 + 测试文件 178）；docs/CHANGELOG 阶段 30
  条目；selfhost_matrix 快照重生成。
  登记不修六条（2026-11-20 收官快照实测）：①3 语料 both_ok_differ 登记不扩
  面：08_auto_optimize（_OptResult 对象身份无 __eq__）/ data_pipeline
  （Dataset 元组身份）/ neural_network（TrainingResult 未定种子损失历史
  非确定）——双面数值语义同、打印表示与随机历史如实分歧，A 轨
  test_registered_differ_honest 锁形；②timeout 2：matha/interp.matha +
  matha/stdlib_symbols.matha 重档自检语料 >120s 双面未完成——29d 时为
  boot_err 快败，30 真化后双面真跑超预算，120s 门禁契约维持诚实分类
  timeout（非分歧）；③both_err 17 维持：错误语料 10 双端如实报错
  （golden 12/13/14/24/25/26/27/28/29/31）+ basics map/sorted/join_split/
  gcd 4 需显式装载 collections_core 双端诚实未找到 + bootstrap_full_test
  （boot 切片未知表达式类型 vs host 未定义变量 '不折叠'——双端错点不同均
  诚实）+ bootstrap_matha（boot Partial len TypeError vs host 属性访问失败
  str.类型）+ bootstrap_test（双端同文案 不可调用的值： <?>?——28-⑨ 同源）
  ；④boot 面切片表达式求值未支持（未知表达式类型: 切片——新可见缺口，
  30a 分派族边界；对应语料宿主面亦错故双端诚实）；⑤29-⑧ 承继：boot func
  定义仍必须 `->`（parser.matha 期望箭头——语言形态）；⑥29-①②⑥⑦ 与
  28-⑦⑧⑨ 承继（native dict_put 不可扩容/互相递归 let rec 前向引用/29e
  opt-in 中段跳过/mb.interpret breaking 注记；语句位 `[` 路由一致性已验证
  语言形态/Dijkstra 距离桩/stdlib str 数字专用）。附注：matha/library/core/
  计算球体积.matha 数据修复（自主成长生成的零参闭包自由变量 r 数据缺陷 →
  `(r) =>` 正参形态，双面球体积 ≈113.09724 A 轨锁）。

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

## 八、成长引擎验证通路（G-1 … G-5 全部已修）

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

### G-5（已修，阶段 19d）：`optimizations_applied` 与 G-4 同形的漏报

- 历史实测（`.trae/g5_probe.py`）：`grow("x = 3.0 + 4.0\\nprint(x)\\n")` 第 1 轮应用
  「常量折叠 × 1、常量传播 × 1」，第 2 轮空转退出；返回的正是第 2 轮的 report，
  于是 `optimizations_applied == []` 而 `improved_source` 已发生变化——三个用例全部
  自相矛盾（`y = 2 + 3`、`a = 7 / b = a + 1` 同样如此）。
- 与 G-4 区别：G-4 是**安全口径**错位（会把腐蚀说成一致），必须修；G-5 只曾使报告
  少报已应用的规则，不会把坏码说成好码，方向偏保守，故曾登记不修。
- **已修（阶段 19d）**：grow() 加 `applied_total` 累加器——闸门通过后 extend（回退轮
  改写未前传、不计入）、空转轮如实不加条目，返回报告聚合全部迭代规则。旧表征锁
  `TestG5AppliedRulesUnderReported` 改锁新形态 `TestG5AppliedRulesAggregated`
  （多迭代聚合：折叠/传播条目齐 + noop growth 仍空），旧锁名不得复活。

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
  【阶段 25 勘误：`cd-full.yml` / `docker_build_push.yml` / `multilang_benchmark.yml`
  三件已于阶段 25e git rm 删除（外部凭据面依赖，负存在由
  `tests/test_ci_hygiene_phase25.py::test_deleted_dormant_cd_family_absent` 上锁）；
  `benchmark.yml` / `stress_test.yml` 的钉钉通知步骤已改为 `$GITHUB_STEP_SUMMARY`
  写入（零 secrets 面）。本清单其余条目（riscv_baremetal / release /
  publish_matha_auth 的死路径）维持登记。】

### 9e. 登记但不修（诚实面，不在本 PR 范围）

- **仓库 secrets / variables 均为 0**（`gh api …/actions/secrets` 实测）。被引用但不存在的
  有 11 个：`DINGTALK_WEBHOOK`、`DINGTALK_SECRET`、`DOCKER_USERNAME`、`DOCKER_PASSWORD`、
  `PYPI_TOKEN`、`OVSX_PAT`、`VSCE_PAT`、`PROD_KUBECONFIG`、`STAGING_KUBECONFIG`、
  `JWT_SECRET` 等。凭据不就绪，全部通知/镜像/发布类步骤不可能成功——这是基础设施缺失，
  不是代码缺陷，也不该靠 mock 刷绿。
  【阶段 25 勘误：外部凭据依赖面已按「自生凭据」拍板整体删除——CI secrets 引用白名单
  收敛为 {GITHUB_TOKEN}（actions 自动注入），PyPI/VS Marketplace/Open VSX/钉钉通知等
  步骤改为 Release 附件 / upload-artifact / $GITHUB_STEP_SUMMARY，白名单由
  `tests/test_ci_hygiene_phase25.py::test_secrets_whitelist_github_token_only` 上锁。
  本条其余历史登记（镜像/K8s/JWT 等面的基础设施缺失）随之失效——对应工作流已删除
  或不再引用这些 secrets。】
- 两份 spec 里 3 处死 `hiddenimports`（`matha.spec` 的 `src.tree_sitter_backends` 与
  `src.domains.hal`、`matha-cc.spec` 的 `src.domains.hal`）仍会让 PyInstaller 打
  `ERROR: Hidden import … not found`，但实测**不阻断构建**（修完 `matha-cc.spec` 后本地重跑
  仍只有这一行 ERROR、exit 0）。这几行本身仍属登记不修：经批准修的只是 9c 里的 EXE 结构
  缺陷，没有顺手动 `hiddenimports`，因为它们需要单独的清理与全量产物实测。
  【阶段 17 勘误：三行已于阶段 17c 删除（三模块均不存在，探针 `ls` 坐实），两份 spec
  活条目不动（`src.domains.hardware` 等保留），文本锁入 `tests/test_phase17_sweep.py`。】
- `matha-ci.yml` 的 `benchmark` job 主体依赖已删除的 `src/vm.py`（`git ls-files src/vm.py`
  无输出）。首版改造降为仅 dispatch，但 run 42195342421 实测：一旦 dispatch 就会以
  `ModuleNotFoundError: No module named 'src.vm'` 失败，把整个验证 run 染红，反而失去「用
  dispatch 单独验 build 链路」的手段。故改为 `if: false`（保留定义、任何事件都不跑），要么
  重建基准入口、要么删除——本 PR 不背书本机不能跑的那一段。
  【阶段 17 勘误：该 job 已于阶段 17c 按「删除」选项移除（`if: false` + 死依赖一并清去，
  workflow YAML 实测解析通过，test_ci_hygiene 6/6 绿）；基准入口如需重建另立片。】
- 上述休眠工作流内部仍有可能的 GH 侧拒绝原因未逐个穷举（本地只能复现 YAML/结构层）；
  真正的判据是推分支后看 Actions 现场：休眠文件不应再产生任何 run。

