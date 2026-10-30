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
| ODE | 一阶可分离 + 一阶线性积分因子 + 常系数齐次特征方程 | 其余抛 `OdeUnsupported`，不返回「无法求解」这种假成功 |
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
`func range(...)`）。**b09 欠账与它的休眠开关**：`for` 的下标读取由发射器手写、
不经元数表，因此正式修复必须**宿主与自举两侧同时改**并保证定点一致。当前以
默认关闭的环境变量形式存在（下节 6a），开启仅供实测，不属于主门禁语义。

**已试但未采纳**：把 VM 柯里化偏应用的中间值换成 `__slots__` 轻对象（`_CurriedPart`），
紧邻 A/B 下无收益（b06 反而 +8%：tuple 拼接与 `__call__` 分发比闭包更贵），已回退。

进程级并行（native 的唯一 scale-out 路径，见 1c）实测：命令
`python scripts/bench.py --json --repeats 5 --native --parallel 3`（已落
`docs/bench_baseline.json`，九场景均能编译成 exe 并 `rc=0`）。同一枚 exe 跑
3 次串行 vs 3 进程并发，speedup 实测区间 **2.4–4.13**（最低 b08 字符串拼接
串行 708.3ms → 并发 294.8ms；最高 b03 while 累加 104.6ms → 25.4ms），退出码全 0。
这是本机单机的实测值，不外推到其他硬件，也不构成「线性扩展」结论。

### 6a. 两枚默认关闭的发射器开关（预备能力，非门禁语义）

`src/mbc/compiler.py` 里有两枚只在环境变量下生效的开关，**默认关闭时字节码与历史
路径逐字节等价**（b09 那枚用 HEAD worktree 导出参照语料对照；sys_env 那枚因 worktree
参照法一次 `cd` 失败改为 `git show` + importlib 在同包环境加载旧修订对照，见报告 §7），
故不影响 `make check`、定点与三端平价：

- `MATHA_B09_FUSE=1`：把 `for`/列表推导里手写的 `get(xs)(i)`、`append(res)(e)`
  两步 `CALL 1` 融成单条 `CALL N`。带**遮蔽安全闸**：模块顶层若声明同名
  `func get`/`func append`，恒走历史路径。`len(xs)` **不融合**——`len` 是原生变参
  内建而非柯里化内建，`CALL 2` 会调用错误的函数。开启态紧邻 A/B（同机、7 次
  重复×4 轮交替、N=50000、只取 VM 纯执行段）：OFF min 858.8/863.0ms → ON min
  724.5/724.3ms，即 **-15.6% / -16.0%**（median -16.0% / -15.9%）。开启态定点
  真实读数：`tests/test_mbc_bootstrap.py` + `tests/test_mbc_vm_matha.py` 共 870 例
  **869 绿 / 1 红**，唯一红项为 `test_m2_stage2_equals_stage3[for_loop]`——这就是
  「单侧改发射器必破定点」的直接证据，转正必须先同步 `matha/compiler_matha.matha`。
- `MATHA_SYSENV_FOLD=1`：启用 `sys_env("KEY", "默认")` 的**编译期常量折叠**（字面量
  键→读宿主环境→`PUSH_CONST`），并连带支持 `if sys_env(...) == "1" { 快 } else { 原 }`
  的恒定条件剪枝（只发射选中分支，实测残留 `JZ` 为 0、`CALL` 仅余 `输出` 一条）。
  键非字面量时在**编译期报错**，不退化成运行期未定义变量。

**为何不做成运行期内建**（设计边界，非偷懒）：VM 本身就是 Python 进程里的解释器，
运行期查环境变量必然经宿主 `os.environ` 中介；而把 `sys_env` 注册成 VM 内建会进
`_default_builtins` 全局表，改变自举编译器可见的符号面 → 定点与并发契约锁一起红。
编译期折叠把运行期查询彻底消灭，因此 **native 也无需 `GetEnvironmentVariableW`**，
`_APIS` 封闭基线（1c 节）可以一动不动。代价是该能力只认字面量键、且属编译期而非
运行期语义；「同一份字节码在运行期按环境自选快/慢路径」在本架构下不成立——指令
形状由发射器在编译期决定，运行期没有可切换的第二套形状。转正前还需与
`matha/compiler_matha.matha` 同步折叠逻辑（同 `MATHA_B09_FUSE` 的前置条件）。
取证工件与逐项读数见 `.trae/p4_b09_preview/B09_VERIFY_REPORT.md` 与 `sysenv_verify.py`。

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
- 工作目录里残留的 `dist/*.exe` 为主线收官前的旧构建，`dist/` 本就在 `.gitignore` 内、
  不受 git 跟踪，无定位效力。

### 7b. 其它交付端

- `mobile/`（Flutter）：仓库内实验性前端，零门禁；其 `assets/pyodide/build_wasm.{bat,sh}`
  硬编码版本 4.4.16，已漂移于主线 v4.6.0，仅作历史脚本保留。
- `matha_wasm/`：整目录在 `.gitignore` 内、git 零跟踪（实测 `git ls-files matha_wasm` = 0），
  磁盘内容为旧快照副本；README 原「Pyodide WASM 运行时」主张已删除。
- `extensions/vscode-matha`：仅语法高亮小插件，不受门禁，不作功能背书。

### 7c. AI 前端（`src/ai_assistant*.py`、`src/openai_compat_server.py`、`src/ai_framework.py`）

- 实测零 `tests/` 引用（grep 无命中），README 亦无 AI 助手功能主张——属仓库内
  未背书代码，保留不删，不入门禁。
- 已上锁的只有内核侧自动修复契约：`src/autonomous.py` 的 `AutoDebugger`/优化/自生长
  由 `tests/test_integration/test_auto_debug_e2e.py` 等 3 个 e2e 文件覆盖，不属本节降级范围。

判据：本节的实测命令（`python scripts/build_exe.py --matha --output <临时目录>`、
`git ls-files matha_wasm`）可随时复跑；若未来某通道要「上锁」，必须先入门禁再进 README。
