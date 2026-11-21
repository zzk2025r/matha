# 更新日志（CHANGELOG）

> 规矩：**版本号唯一来源是 [`src/__version__.py`](../src/__version__.py)**，
> 本文件是当前条目的版本标题，以及文中关键数字（领域插件数、黄金用例数、
> 核心体量行数、native 已知缺口数），都由
> [`tests/test_doc_facts.py`](../tests/test_doc_facts.py) 与仓库现场实测值
> （`python scripts/repo_facts.py`）逐字核对——漂移即红。
> 历史条目标题里的旧版本号是唯一允许出现的例外（读者就是来查版本历史的）。
> 本文件不写任何自评评分与「加速 N 倍」类性能数字（口径见
> [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第六节）。

## 未发布（Unreleased，分支 `feature/kernel-plugin`）

P1 内建函数库补齐：纯 Matha 标准库，零新 opcode、零新宿主内建
（机器码平价先例同黄金用例 `35_list_comp`）。

- 新增 `matha/library/collections_core.matha`：`map/filter/reduce/sorted/
  join/split/gcd` 七函数，全部复用已三端平价面（curried func、lambda 传参、
  `let rec` 累加器递归、`len/get/append/slice/str/+`）。`sorted` 为稳定插入
  排序，只有 `sorted(xs, lt)` 双参形式（同名不同 arity 重载会被后定义覆盖，
  VM/interp 实测）；`split` 对齐 Python `str.split(sep)` 口径，空分隔符报错。
- 黄金 runner preload 机制：`manifest.json` 的 `cases.<stem>.preload` 把库源码
  前置拼接进用例文本，三端跑同一模块（与 `tests/test_mbc_bootstrap.py`
  多文件拼接同构）。
- 黄金用例新增 `36_basics_map_filter_reduce` / `37_basics_sorted` /
  `38_basics_join_split` / `39_basics_gcd`，vm ↔ interp ↔ native 逐字节锁。
- 行为单测 `tests/test_matha_library_basics.py`：对拍 Python 真相
  （`sorted/map/filter`、`math.gcd`、`str.split/join`），含排序稳定性等值类、
  空分隔符报错口径、库执行零 `src.domains.*` import 纯净断言。
- [ast_vm_gap.md](ast_vm_gap.md) 第九节「无 sorted/map/filter/join/gcd/split
  等内建」行改写为已由标准库提供（含 `scripts/ast_vm_matrix.py` 模板同步）。

P2 多端交付与 AI 前端定位（降级，不上锁）：口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节。

- `scripts/build_exe.py` 修复 4 处致命 bug（`global` 声明晚于使用、`args.matha-cc`
  非法属性名、`--specpath` 与 `.spec` 互斥、汇总解包元数不符）；当场实测重建
  `matha.spec` 成功，exe `--version`/`eval`/`run` 验证通过（不入 `make check`）。
- README 诚实化：方式 1 改本地自建口径（仓库不预构建发行版）；`matha-cc` 改
  `python -m src.compiler.matha_cc_cli` 口径；删「Pyodide WASM 运行时」现功能主张。
- git 索引移除：`release/`（早期版本时代快照共 1600 文件）与 `offline_package/`
  （构建产物）不再跟踪；顶层 10 个零引用一次性脚本脱离跟踪；均本地保留不删，
  前两者追加进 `.gitignore`。
- 降级标注：`mobile/README.md` 头部与 AI 前端 4 文件（`src/ai_assistant*.py`、
  `src/openai_compat_server.py`）docstring 如实登记「实验性/未背书、零门禁」。

P3 性能基准 + 内建调用优化 + native 并发边界（口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第六节与 1c）。

- 新增可复现基准量具 `scripts/bench.py` 与语料 `scripts/bench_cases/`（9 场景，
  `{N}` 参数化规模）：分 compile / vm / total 三段，`--native` 追加 exe 编译与
  子进程两段，`--parallel K` 量进程级并行吞吐；`--selftest` 做小规模确定性校验，
  `--json` 落 `docs/bench_baseline.json`（版本/Python/平台/CPU/repeats/每段
  min-median-max）。方法学约束（同机相邻两轮 A/B、只报实测值）写在第六节。
- 内建调用优化（实测幅度见第六节表）：编译器把**完全应用**的柯里化内建
  （`get`/`append`/`slice`/`range`）融成单条 `CALL N`；VM `_curry2/_curry3` 返回
  携带 `fn`/`arity` 的 `_Curried`，`_invoke` 在齐 arity 时直调 `fn(*args)`、不再
  逐层物化中间闭包。arity 表宿主侧 `_CURRIED_BUILTIN_ARITY` 与自举侧
  `matha/compiler_matha.matha` 的 `_预扫元数` **逐项同值**（否则 stage2↔stage3
  定点会红）；模块自有同名 `func` 声明以用户 arity 为准。
- 语义锁 `tests/test_curried_builtin_paths.py`：链式/二元/偏应用/三参、超量应用
  错误文本 vm↔interp 逐字一致、native exe 平价、CALL N 形状锁与**双侧 arity 表
  同值锁**（把「改这边要改那边」从约定变成可执行判据）。
- native 并发边界上锁 `tests/test_native_concurrency_contract.py`：API 面为封闭
  基线（不含线程/纤程/临界区/原子/TLS）、`src/mbc/` 不引入并发模块、并发域符号
  不入 VM 内建表、native 对并发源码必须非零退出且 stdout 不产值、同一枚 exe
  多进程输出逐字节一致；工具链缺失时 exe 类用例优雅 SKIP。
- 文档数字随现场刷新（README 测试文件数、ARCHITECTURE 核心体量），由
  `tests/test_doc_facts.py` 与 `scripts/repo_facts.py` 核对。

P4 转正·两枚发射器开关退役入门禁（口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第 6a 节）：

- **b09 for/列表推导语法糖融合（真双侧同步转正）**：`for`/列表推导里手写的
  `get(xs)(i)` / `append(res)(e)` 两步 `CALL 1` 融成单条 `CALL N`——宿主 `_emit_curried_builtin`
  恒融合、自举 `matha/compiler_matha.matha` 的 `_for循环码`（`_get齐参`/`_get逐步`）同判据同步
  发射（融合判据 `_fn_arities.get(name)==实参数` ⇔ 自举 `_查元数(元数表,name)==len`，遮蔽安全闸
  保留、`len` 变参内建不融合）。退役 `MATHA_B09_FUSE`；转正后 870 例定点全绿（原 ON 态唯一红项
  `test_m2_stage2_equals_stage3[for_loop]` 已随双侧同步转绿）；形状锁入
  `tests/test_curried_builtin_paths.py`（for→`[1,2,1]`、列表推导→`[1,2,2,1]`、遮蔽→`[1,1,1,1]`）。
- **sys_env 编译期折叠（宿主恒开）**：`sys_env("KEY", "默认")` 遇字面量键折成字符串常量；恒定条件
  剪枝**仅折叠驱动**（纯字面量比较不剪，与从不剪枝的自举侧逐字节一致），键非字面量编译期报错。
  退役 `MATHA_SYSENV_FOLD`。此为**宿主编译器独有能力**（纯 Matha 自举无 OS 环境入口，不可能双侧
  同步）：靠防呆守卫 `test_sysenv_never_appears_in_bootstrap_or_corpus`（断言定点/自举语料禁出现
  sys_env）+ 形状锁 `test_sysenv_host_fold_shape`（常量池无 sys_env 名、剪枝后 JZ 为 0、只剩 `输出`
  一条 CALL）保证折叠永不介入 stage2↔stage3 比对、以后不再破坏主线。
- 取证工件与验证报告：`.trae/p4_b09_preview/`（含 `B09_VERIFY_REPORT.md` 与字节码/值对照、定点
  漂移脚本），不入 tests/ 与 golden_tests/。

P5 骨架体检·零缺陷闭环（P0 诚实红线 + P3 覆盖闭环；口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）。

- **mobile 版本单一源落地**：`mobile/assets/pyodide/build_wasm.{bat,sh}` 与
  `mobile/assets/deploy.{bat,sh}` 不再硬编旧版本号，构建/部署时从唯一版本源
  `src/__version__.py` 解析（读不到即报错退出，拒绝以硬编版本继续）。
- **AI 前端未背书横幅补齐**：`src/ai_framework.py` 与既有 4 文件一致登记
  「未背书 / P2 降级」；三处 web 前端 README（`web/`、`mobile/web/`、`mobile/web_new/`）
  加降级横幅并删除指向不存在的 `tests/test_ai_assistant.py` 的失效指引。
- **MATHA_COMPARISON 虚假主张清除**：「验证结果」小节曾以 ✅ 声称
  `auto_web_framework`/`auto_async_io`/`auto_pattern_matching`/`auto_metaprogramming`/
  `auto_generate_source_compiler`/`auto_compile`/`register_natural_language`——这些方法
  全仓无定义；改为只列 `register_any`/`auto_fix`/`auto_generate_module(类型)`/`natural_to_code`
  真实 API（均为模板/正则驱动、非真实模型），并显式标注其余为「愿景·未实现」。
- **新增门禁锁**：`tests/test_unbacked_channel_honesty.py`（AI 前端横幅 + 内核链不得顶层
  import AI 模块 + mobile 脚本从版本源读取）与 `tests/test_domain_plugin_smoke.py`
  （全部领域插件物化无异常、导出非空、manifest 声明符号 ⊆ 实际导出）。
- **体检结论（如实）**：主线执行链无阻断性缺陷、代码内 `# TODO/FIXME` 标记 0；
  裸机 P5 栈式引擎 17 op 全覆盖（`baremetal/tools/check_skeleton.py` 全绿）、P6 SPIKE
  覆盖集逐字节对拍 + 越界语义 `NotSupportedRV32` 显式拒绝（`run_rv32_spike.py` 全绿），
  baremetal 保持独立门禁不并入主线；符号引擎缺口全部处于「一致 / 插件回退 / 显式失败」
  三态并有测试锁定（§9.6 精确代数数打印为已登记、数值正确的已知偏差）。

P6 插件化隔离风险·高级能力外置（代数数精确打印 opt-in + 动态语义空壳预埋；口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）。

- **接口与实现分离**：新增两个与纯内核正交的契约层 `src/algebra/`（中性代数项模型
  `Const/Symbol/BinOp/UnaryOp` + `AlgebraicNumberPrinter` 协议 + 注册表 + `load_plugin`）
  与 `src/dynamics/`（`DecodedInstr`/`MachineView` + `DynamicSemanticsBackend` 协议）。内核
  与门面只依赖接口，严禁硬编码具体实现；契约层仅用标准库，不 import 内核内部、不引
  sympy/numpy/scipy。
- **代数数精确打印插件**（`src/algebra/algebra_plugin.py`）：小高度整数极小多项式识别将
  落在二次域 ℚ(√d) 内的 double 系数还原为精确根式。门面 `calculus_symbolic.py` 发射统一
  过一层 `decorate_numeric`（默认关，`enable_exact_algebra()` 才启用），把§9.6 的
  `0.7071067811865475*atan(x/1.4142135624)` 还原为 `1/2*sqrt(2)*atan(x/sqrt(2))`。
  能力之外（多根式/高次根/超越数）诚实回退 double，绝不臆造；**未加载时输出逐字节不变**。
- **动态语义空壳预埋**（`src/dynamics/dynamic_semantics_plugin.py`）：P1-4 全动态 RV32IM
  语义的接口 + 注册 + 加载路径全部就位但不落地：`supports` 恒 False（不认领任何指令），
  `execute` 被显式调用即抛 `DynamicSemanticsNotWired`（显式失败，不伪造成功）。加载此
  骨架不改变任何现有执行行为。
- **内核零改动**：`src/kernel/**`、`src/mbc/**`、lexer/parser/ast_nodes 未新增/未修改；
  `dep_audit` 违规 0、`test_kernel_purity` 全绿。新增 `tests/test_plugin_algebra_dynamics.py`
  锁定无损回退/精确还原/诚实预埋 + 内核不得反向依赖插件契约层的隔离红线。

P6b 动态语义由空壳转实装·RV32IM 逐条落地（取代上方「空壳预埋」的不落地状态；口径见
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）：

- **`src/dynamics/dynamic_semantics_plugin.py` 的 `_HANDLERS` 逐条实现 RV32IM 语义**（R/I/S/B/U/J
  全格式 + M 扩展）：仅经 `MachineView` 的 read_reg/write_reg/load/store/set_pc/halt 动作面推进，
  不依赖任何执行器私有成员。`supports` 现为「op ∈ 已落地处理器」，未覆盖指令（CSR/FENCE/ECALL）
  仍返回 False 回退执行器原生，`execute` 被要求执行未接线语义仍抛 `DynamicSemanticsNotWired`，
  与 SPIKE「未知指令即抛错」的诚实纪律同构。**内核与执行器仍零改动**；未 `load_plugin` 时行为不变。
- **对 SPIKE 逐指令 对拍**：`tests/test_plugin_algebra_dynamics.py` 新增 462 项，把同一 32 位指令字
  分别喂给权威解释器 `baremetal/tools/rv32_spike/rv32sim.py` 与本插件，逐位比对 32 个寄存器与 pc；
  含移位取模、有/无符号比较、除零与 INT_MIN 溢出、jalr 清最低位、分支转移/未转移等边界。SPIKE
  未实现的 `lh/lhu/sh/mulh/mulhsu/mulhu` 另以规格黄金锁手算期望值直锁。全量门禁 4695/4695、失败 0。

P6c 代数数精确打印扩面·多根式域 + 高次纯根（扩展上方 P6 代数插件的能力上限，原仅二次域 ℚ(√d)；
口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）：

- **多根式域结构还原**（`src/algebra/algebra_plugin.py`）：新增 SurdVector（`dict[√D] → 有理系数`）表示
  ℚ(√d₁,…,√d_k)，在二次塌缩失败后按项树结构精确还原 `√2+√3`、`(1+√2)(1+√3)=1+√2+√3+√6`、`1/√2=√2/2`
  等度数 2^m 的代数数；仅当树中确有根式基且回代数值吻合才输出，否则回 None。
- **高次纯根**：识别结构化 `base^(1/n)`（n≥3、整数被开方数）化简为 `k·ⁿ√r`（规范串 `root(n,r)`，如
  `∛16 → 2*root(3,2)`）；扁平浮点无树形线索仍诚实回退 double，不过度臆测高次根。
- **修复实数域缺陷**：`_eval_float` 的 `^` 遇负数开非整数次幂（Python 返回 complex）现拒绝并回退，
  杜绝把非实值送进 `math.isfinite` 崩溃。
- **对 sympy 结构化对拍**：`tests/test_plugin_algebra_dynamics.py` 新增 25 项（多根式与高次纯根各按独立
  sympy 精确求值做符号相等 + 数值吻合对拍，另锁扁平浮点回归与诚实 None 边界）。门面 `decorate_numeric`
  仍只作用扁平 double，二次路径逐字节不变。**内核与 `src/algebra/interface.py` 零改动**。全量门禁 4720/4720、失败 0。

P6d 动态语义补全 SYSTEM 子集·CSR / FENCE / ECALL（在上方 P6b 的 RV32IM 之上，插件层新增系统类语义；
口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）：

- **CSR 读改写语义**（`src/dynamics/dynamic_semantics_plugin.py`）：落地 `csrrw/csrrs/csrrc` 与
  `csrrwi/csrrsi/csrrci` 六条（含 `csrr`＝`csrrs rd,csr,x0` 纯读特例）——rd 取旧值、按 swap/set/clear
  回写寄存器文件之外的独立 CSR 地址空间。CSR 不在 `MachineView` 最小动作面内，故经**鸭子类型可选
  探测**机器的 `csr_read`/`csr_write` 能力；机器未提供则该指令返回 False 回退原生，绝不假设机器有 CSR 而崩溃/伪造。
- **FENCE 语义**：`fence`/`fence.i` 在单 hart 顺序执行模型下无可观副作用，作为 nop 退休。rv32sim 未实现
  FENCE（遇 opcode 0x0F 直接抛错），无对拍基准→改由规格黄金锁断言不改寄存器/pc/内存。
- **ECALL 语义**：仅落地执行器实际建模的 system_reset ABI（`a7==0x6758 → halt`，退出码取 `a0`），与
  SPIKE 逐条对拍（两者收到该 a7 均停机）；其余 a7 无既定 ABI → 返回 False 交回原生，与 SPIKE「未知 ecall 抛错」同构。
- **诚实边界**：`mret`/`wfi`/`ebreak` 等仍未接线 → `supports` 返回 False 回退原生。`tests/test_plugin_algebra_dynamics.py`
  新增 9 项（6 条 CSR 读改写规格黄金 + csrr 纯读 + 立即数形态；fence 无副作用黄金；ecall 未知 a7 回退 + 机器无
  CSR 能力回退；ecall system_reset 对 SPIKE 停机逐位对拍），单文件 541 项全绿。**内核、执行器与
  `src/dynamics/interface.py` 零改动**。全量门禁 4729/4729、失败 0。

P6e 接入原生执行器试点·RV32I 端到端语义闭环（将上方插件语义接入真实执行器做试点，完成从逐指令到整程序的闭环；
口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第七节）：

- **执行器试点适配器**（`tests/test_plugin_algebra_dynamics.py`）：`SpikeMachine` 把权威解释器 `RV32Sim` 适配到
  `MachineView` 最小动作面，寄存器/内存/MMIO（UART、sifive_test 停机）全代理给 SPIKE 本体，使“插件驱动整程序”
  与“SPIKE 原生跑”只隔离**指令语义**一处变量。
- **端到端对拍**：`_run_plugin` 以 `execute_or_default` 把 4 段真实 RV32I 程序（算术/访存、blt 循环、jal/jalr 调用
  返回、UART 输出）逐条经插件语义驱动至停机，断言全程零回退原生，并与原生跑逐位比对最终 32 寄存器堆/串口
  输出/停机码；另锁循环程序 `acc=1+…+10=55` 且确实多轮转移。
- **界定内核↔执行器↔插件边界**：`test_native_executor_is_plugin_agnostic` 静态扫 `rv32sim` 源码，锁其不 import
  `src.dynamics`/`src.algebra`/`src.kernel`——执行器对插件事务无知，集成缝单向存在于试点适配器（它同时 import 两边）。
- **零改动红线**：本步为纯验证侧新增（适配器与测试），未改内核、未改执行器 `rv32sim`、未改插件与 `src/dynamics/interface.py`。
  `tests/test_plugin_algebra_dynamics.py` 新增 6 项，单文件 547 项全绿。**全量门禁 4735/4735、失败 0。**

成长闭环·编排契约与诚实降级锁（阶段 6d–6f；口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) §7c）：

- **溯源如实**：被编排的子系统（`src/unified_growth.py` 本体、`src/growth_engine.py`、
  `src/inner_loop.py`、`src/domain_formula.py`、`src/language_bridge.py`、`src/pkg_manager.py`）为**既有实现**，
  其历史提交未以「阶段 6a–6c」编号（全仓 `阶段6*` 标签最早只到 6d）；本轮可核实的交付是阶段 6d–6f——
  为上述顶层编排器补上 `make check` 级接线/降级锁并修四类 phantom，不把既有子系统冒称本轮新造。
- **定位**：把顶层编排器 `UnifiedGrowth`（串 selfupgrade / growth / matha_growth / inner_loop / 领域公式 /
  语言桥 / 插件市场）的**编排契约与诚实降级**纳入 `make check` 门禁；沿用 §7c 降级——**不背书**其 AI
  前端 / 市场 / HAL / 优化器的**输出正确性**，只锁接线正确、schema 稳定、子系统缺席时如实降级、绝不裸抛；
  成长链仍不经 L1 内核入口。
- **修复四类 phantom 接线缺陷**（阶段 6e）：① `get_growth_stats` 曾把 Interpreter 误当 assistant 传入
  `GrowthEngine` → 内部触 `.parser` 报错（改用工厂 `create_growth_engine()`）；② `FormulaRegistry.list_formulas()`
  返回名字 `list[str]` 却被当 `Formula` 对象迭代 `f.domain/f.free_vars()`（改迭代 `_registry._formulas.values()`）；
  ③ `fictionalize` 依赖全库不存在的幽灵导入 `src.matha.growth.FormulaFictionalizer`（改诚实拒绝、不伪造成功）；
  ④ `get_current_version` 读不存在的 `_growth_engine._registry`、被 `except` 吞而恒回退硬编码版本（改取唯一版本源
  `src.__version__`）。
- **inner_loop 适配桥落地**（阶段 6d）：`run_inner_loop` 真正接入闭环自改进，此前恒报「不可用」。
- **`register_extension` 最小诚实修复**（阶段 6f-D）：过去每次新建临时 `ExtensionRegistry` 后即弃、且完全忽略
  传入的 `func` 却返回成功；现持久化注册表、新增 `list_extensions()` / `get_extension_callable()` 可查、`func`
  如实保留（`Extension` 模型仍不支持可调用体，仅保留不加载）。
- **新增离线回归锁（均在 `make check` 的 `pytest tests` 内）**：`tests/test_ai_e2e_pipeline.py`（chat 编排契约 +
  chat→inner_loop 感知 E2E）、`test_growth_subsystems_lock.py`（selfupgrade / growth 直接 API 面，此前零测试）、
  `test_growth_loop_e2e.py`（单实例顺序驱动整链 + 把「仅断返回类型」的弱契约升级为桩引擎「真实委派发生 +
  参数/结果透传」强契约 + monkeypatch 可选子系统缺席的诚实降级）、`test_growth_delegation_audit.py`（24 公开
  包装→委派目标×锁落点审计表 + 完整性守卫：新增/改名公开包装不登记即红）。
- **如实登记未背书项**：`MathaGrowthEngine.grow` 对 `func` 源码做常量折叠/死代码消除会改写到语义破损
  （实测丢函数名），属未背书优化器输出正确性，仅锁其经 `self_grow` 的四属性交接契约与不裸抛，正确性修复
  另立轨道（§7c）。

P7 CI 面卫生·红 CI 收敛与「整文件被拒绝」修复（口径见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) 第九节）：

- 权威回归门收敛为 `matha-ci.yml`（lint + 零依赖核心执行链矩阵 + native ELF 实跑）与
  `ci.yml`（`packages/**` 冒烟）两份；其余 8 份工作流只保留 `workflow_dispatch`
  （`release.yml` / `publish_matha_auth.yml` 另留 tag 触发），并逐份写明休眠证据头。
- 修三类会让 GitHub 整文件拒绝的写法：`cd-full.yml` 的 `run:` 多行纯量（YAML 报
  `mapping values are not allowed here`）、`stress_test.yml` 把工作流顶层的
  `strategy:` 下放到 job、`release.yml` 同一步既 `uses:` 又 `run:`（并拆为两步、
  env 布尔默认值改字符串）。
- 直修参数/路径/shell 错：`matha-ci.yml` 的 `package_offline.py --output-dir` → `--out`、
  `verify_offline.py --package-dir` → 只传 `--quick`；PyInstaller 产物路径
  `dist/matha-offline/matha.exe` → `dist/matha.exe`（`matha-cc.exe` 同理，共四处），
  `mypy src/deps.py`（已于 082218c 删除）→ `scripts/dep_audit.py`；`build-exe` 两个构建步骤
  补 `shell: bash`（windows runner 默认 PowerShell，`ls -la` 会报「A parameter cannot be
  found that matches parameter name 'la'」）。
- 以上均经 `gh workflow run matha-ci.yml --ref chore/ci-hygiene`（run 42195342421）真实跑过：
  lint / test×2 / native ELF gate / `Offline Deployment Verify` 转绿；`Build Executables` 的
  失败点由此从「路径写错」收敛为「shell 不匹配」，已按新证据二次修复；`benchmark` job
  一旦 dispatch 必报 `No module named 'src.vm'`，故置 `if: false`。
- 二次 dispatch（run 42198963200）确认 `Build matha.exe` 已转绿，并暴露出最后一个红：
  `matha-cc.spec` 只有 `EXE(exclude_binaries=True)` 而无配套 `COLLECT`，产物落在
  `build/matha-cc/` 且启动即 `Failed to load Python DLL`，`dist/` 下根本没有 matha-cc。经批准
  扩一个文件范围修为 onefile（并入 `a.binaries` / `a.datas`，与该 spec 头部声明的
  `--onefile` 一致）；本地实测：重建 exit 0、`dist/matha-cc.exe` 11.3 MB、
  `matha-cc.exe info` exit 0（同时 `matha.spec` 重建 exit 0、`matha.exe --version` 报
  `Matha v4.6.0`）。
- 第三次 dispatch（run 42208252282）：两个构建步骤均 success、`matha.exe --version` 在 CI
  上正常输出，剩下的红跳到 `Test executables`：`matha-cc.exe info` 报
  `UnicodeEncodeError: 'charmap' codec can't encode …`（中文 print 撞上 windows runner
  的 cp1252 控制台）。根因在产品侧 CLI 无输出兜底，本轮不动 `src/`；只在 CI 步骤里
  显式把控制台与环境切到 UTF-8（`PYTHONUTF8` / `PYTHONIOENCODING` / `chcp 65001` /
  `[Console]::OutputEncoding`），并把真修法登记到 KNOWN_ISSUES 9c。
- 第四次 dispatch（run 42208958450）**证伪了上一条的 CI 侧方案**：`PYTHONUTF8=1` /
  `PYTHONIOENCODING=utf-8` 已在步骤 env 中给出，冻结 exe 仍按 cp1252 崩。本地 A/B 对照给出
  机制：冻结 exe 的 stdio 编码在**打包时**就固定，运行时的 `PYTHONIOENCODING` 对它无效（源码
  运行则尊重）。“本轮不动 `src/`”只是当时未获批准的边界，不是真修法。经第三次批准已落产品侧：
  `src/compiler/matha_cc_cli.py` 与 `src/matha_main.py` 各自内联 `_harden_std_streams()`
  （`reconfigure(errors="replace")`：保留原编码，只把不可编码字符降为 `?`，不再抛异常），
  在两个 `main()` 顶部调用；未新增 `src/` 模块（`core_py_lines` 被架构文档锁）。新增回归锁
  `tests/test_cli_encoding_fallback.py`（3 例）：去掉兜底调用后本地报出与 CI 日志逐字相同的
  `UnicodeEncodeError … position 11-13`，加回后 rc=0。
- 第五次 dispatch（run 42217545003）确认收尾：`Build Executables` job 内 `Test executables`
  步骤（之前唯一未转绿的环节）在 CI 的冻结 exe 上已 **success**，整个 `Matha CI` 权威门
  9 个 job 全绿（benchmark / publish 为预期 skipped）。
- 新增离线回归锁 `tests/test_ci_hygiene.py`（6 项，零第三方依赖的 YAML 结构扫描）：
  顶层键白名单、步骤不得 `uses`+`run` 共存、`run:` 不得为多行纯量、非权威门不得
  自动触发且必须带证据标记、权威门引用的仓库路径必须存在。反向对照实测：拿改动
  前的 10 份工作流跑，6 条锁各自精确命中对应旧伤，无「无牙齿」锁。

## v4.6.0（2026-10-29，分支 `feature/kernel-plugin`）

内核纯净化 + 插件化重构收官。区间提交 `f496009`（冻结主线）→ `673f983`，
领先 `mainline-frozen`（`082218c`）8 个提交。下列每条都附可执行判据，
未达成项如实留在 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

### 一、唯一核心主线归一（转译执行路径删除，interp 降级）

- 执行链归一为 `src/lexer.py → src/parser.py → src/ast_nodes.py →
  src/mbc/compiler.py → src/mbc/vm.py`；`repl.py` / `matha_main.py` /
  `exec_api` 统一走 `src/mbc/cli.py`，不再有第二条执行链。
- **删除** `convert(source,"matha","python") + exec()` 转译执行路径。
- `src/interp.py` 降级为**诊断后端**（执行轨迹 / 单步调试），经
  `src/kernel/exec_api.py::run(source, mode=...)` 显式选择，
  `--backend=legacy-interp` 仅测试与调试可见。
- 第三条 VM `src/vm.py`（MIR 栈式）归档为 `src/plugins/legacy_mir_vm.py`
  （只能显式 import，不在默认路径）；重复实现 `src/m3v_vm.py` 删除；
  `src/mir.py` / `src/mir_opt.py` 只作优化分析 IR，不承担执行。

### 二、L1 纯净内核：核心安装零第三方依赖

- 核心安装第三方依赖 **0**（`pyproject.toml` `dependencies = []`），
  sympy/numpy/scipy 降为 `optional-dependencies.accelerated`。
- 内核 import 白名单 + 核心目录无子进程/线程/套接字，由
  `tests/test_kernel_purity.py` AST 静态解析机器判定；依赖方向取证由
  `scripts/dep_audit.py` 产出 [DEP_BASELINE.md](DEP_BASELINE.md)。
- 内核内建收敛为五组纯标准库模块：`math_builtin`（数学 + 单位换算）、
  `regex_builtin`、`time_builtin`、`file_builtin`、`errors`；
  修复了 `vm.py` 反向 import 领域层（`domains.time_module`）的内核污染。

### 三、插件联邦：88 个领域插件懒加载

- **88 个领域插件**（`src/domains/`，清单 `manifest.json` 89 插件、0 不可用）零改写接入
  `MathaPlugin` 契约（`src/plugin_api.py`），另有 **7 个内核外工具插件**
  （`src/plugins/`：toolchain_msvc/llvm、numpy_accel、ffi、tree_sitter 等；
  原 9 个中的 ffi_sdk / legacy_mir_vm 已于阶段 22b 孤儿清算删除）。
- 阶段 25 自生凭据与应用中心：新增 `store` 插件（商店_签发令牌/校验令牌/
  吊销令牌，HMAC-SHA256 自签发，首发 secret 落 `.matha/store/secret.key`）；
  应用中心引擎 `matha/store_engine.matha` 为纯 Matha（HTTP 解析/路由/索引），
  Python 侧仅 socket 驱动 `src/app_cli.py`（`matha app` serve/token/publish/
  upgrade/list/search/install/import-release 八子命令）；socket 服务端域胶水
  （网络_服务/接受/收/发/关闭，真监听器句柄）替换旧无句柄假面（网络连接/
  绑定/监听/Socket发送/Socket接收）。CI 去外部凭据（25e）：secrets 白名单 =
  {GITHUB_TOKEN}（卫生锁 `tests/test_ci_hygiene_phase25.py`），PyPI/VS
  Marketplace/钉钉通知等外部凭据面删除，发行物一律 GitHub Release 附件，
  经 `matha app import-release` 导入本地应用中心；休眠 CD 家族
  （cd-full/docker_build_push/multilang_benchmark）与钉钉共享配置删除。
- 阶段 26 类插件化与设备/任务管理器（四片全落，四项拍板全走推荐项）：
  **26a 运行时注册表泛化**——exec_api 后端注册表条目化
  （unregister_backend / set_backend_enabled / backend_info 三面，停用后 run
  诚实拒绝；主线 vm/native 保留名不可注册），VM 构造收敛为唯一工厂
  `make_vm`（4 处构造点归一）；**26b 编译器框架域**——新增
  `compiler_framework` 插件（第 87 个 src.domains 域）：五框架模块
  （pass_manager/adaptive_optimizer/incremental_compiler/distributed_compiler
  + exec_api 注册表）首次获得真实消费者——内置优化遍真化（常量折叠/死代码
  消除，PassManager 此前零具体遍）、程序_分析/策略_推荐/增量_编译/任务_提交
  /后端_执行（真跨运行时调用）十二符号双面，Matha 回调遍经运行本体
  invoke_value 双面注册（清单物化面共享语境解释器、VM 面官方入口注入面）；
  **26c 插件兼容面**——清单声明 `requires` 依赖缺失注册诚实拒绝
  （注册被拒 + ERROR 诊断，绝不静默跳过），conflicts() 多属主符号冲突报告
  （取值语义维持清单最后声明者覆盖），report() 八键汇总 + 依赖事后被注销
  （ext disable）如实报告；**26d 设备/任务管理器**——`src/system_inventory.py`
  信息层（硬件与状况/自身状况/软件清单/模块清单四节，纯标准库 + 只读探测，
  psutil/nvidia-smi/烧录工具链缺失诚实降级「不可得」）+ `system_monitor`
  插件（第 88 个域，硬件_信息/自身_状况/软件_清单/模块_清单/插件_冲突
  五符号双面）+ `matha sys` CLI 六子节（hardware/self/plugins/software/
  modules/all，JSON 输出）；插件使用口径 = 物化时刻（plugin_usage）。
- 阶段 27 共生体（Matha 既是桌面软件又是操作系统，五片全落，四项拍板全走
  推荐项）：**27b stage-4 脱宿主闭环**——stdlib+vm.matha joined 闭包经
  boot 链 VM²（编译出的 VM 编译）与宿主编译逐字节一致（tier A 内层 VM /
  tier B VM² 跑编译码 / tier C joined 编译同一三层锁
  `tests/test_stage4_closure_phase27.py`）；附带真化 stdlib/vm.matha 五处
  `_to_float` 宿主依赖（×1.0 / String parse 委托 / ∞ 字面量）；**27c 纯
  Matha OS 内核**——`matha/os/kernel.matha`（单元生命周期状态机/进程表与
  协作调度/服务注册表 + 兼容协商），探针踩中即修四缺陷（空转轮步数翻倍、
  卸载落地记录表破坏、步进返回口径、服务占用协商），11 锁；**27d 单元管理
  器五形态统一**——`src/os_runtime.py` 宿主桥将 app（25d manifest）/包
  （24a）/域插件（PluginResolver）/终端命令（12e registry）/服务
  （register_service）翻译为内核描述符 + 外部单元（spawn/poll/stop/
  升级回滚/卸载）+ inspect 健康桥，12 锁；**27e TUI 桌面**——
  `matha/os/desktop.matha`（纯 Matha，`use 内核`，演示单元 时钟/回声/便签，
  j/k 焦点 s 启动 t 停止 u 卸载 p 进程 d 步进 q 退出，动作经内核协商面拒绝
  如实回传）+ 终端 `桌面` 命令（一次性确定性键序脚本，别名 desktop，至多
  16 键），13 锁；**27f 资源库三分支**——`matha/library/{os,desktop,compat}`
  六模块（进程管理/单元清单/单元工厂/桌面组件/包适配器/命令适配器）并入
  资源索引 21→27 条 + 宿主解析器字典值语境窄化修复（`_parse_dict_value`
  值位旗标：`{"k": [x]}` 值位 `[x]` 为列表字面量而非输出命令；boot 链六
  文件 AST 逐字节探针零扰动，唯一差异面 `matha/vm/matha_vm.matha:66` 帧栈
  构造修正为真列表），18 锁。
- 阶段 28 全工具链自举重建 + 统一扩展插口（三项拍板全走推荐项：①全语料
  三重公式判据 ②统一五动作端口协议 ③全链贯穿）：
  **28b parser/lexer 语法完备性 + AST 全语料对拍**——自举解析器
  （lexer.matha/stdlib.matha/parser.matha 编译为字节码跑在 VM）与宿主解析器
  对同一源码产出逐字段一致的 AST；自举侧补齐块体/顶层双轨分派、占位符、
  typeof、值结尾 token 集等分支镜像，`test_parser_parity_phase28` 22 项
  （13 固定 + 9 语料参数化）。
  **28c 编译完备性 + 字节码全语料对拍**——自举编译器（compiler_matha.matha
  编译入 host MBC 跑在 host VM，stage3）对全部 `matha/**/*.matha` 语料的
  编译产物与宿主编译器 stage2 `_canon` 逐位一致；五类根因最小源回归锁
  （R1 module X{func X} 同名冲突不发射命名空间绑定 / R2 函数体内 let rec
  盒协议 / R3 return 语句 / R4 `#N：`合并体裸 list / R5 lambda 体内 if-else
  挂链）；自定义算子消费 + 0x62 公式码（FORMULA_SCHEMA host-only 登记）；
  `test_compiler_parity_phase28` 188 项（5 固定 + 183 全语料参数化，随语料
  增减自适配）。VM 执行面维持阶段 27 stage-4 闭环锁（VM² ~10.5 min/文件
  不扩面）。
  **28d 自举层开放插口**——`matha/interp.matha` 解释器插口注册表（注册/
  注销/名表三动作，保留名诚实拒绝，注册即并入 `注册内建(空环境())`）+
  `src/mbc/vm.py` register_builtin/unregister_builtin（保留名/模块函数/
  非可调用诚实拒绝）；`test_open_ports_phase28` 26 项（双面对拍 + 解释器
  自举面经 24d 共享全局嵌套 VM 注入 lambda）。
  **28e 统一五动作端口协议**——注册/启停/升级/回滚/依赖协商覆盖六层
  （词法语法/解释器宿主/解释器自举/编译器/虚拟机/内核特性）：纯 Matha
  协议模块 `matha/library/os/端口协议.matha`（资源索引 27→28 条）与宿主
  适配层 `src/extension_port.py` 状态形状（{"层","条目","审计"} 六槽条目）/
  审计行同构，诚实拒绝时状态原样不动；配套注销面 src/custom_ops.py
  unregister + src/compiler/pass_manager.py unregister_pass；
  `test_port_protocol_phase28` 17 项（三面对拍 + 六后端效应 + 诚实拒绝
  矩阵 + os_runtime 工具链单元）；`os_runtime.register_toolchain_units()`
  把六层装载为内核服务单元（`工具链-<层名>`，装载=注册、启动/停止=启停、
  主步=只读健康探针）。跨 VM 调用他模块函数须按 24d 钉池纪律
  （fn.consts/fn.functions）——MBC `_invoke` 常量池回退逐 VM（已登记）。
- 阶段 29 执行面双轨判据 + 自举链缺陷真化 + 编译器框架接入 MBC 主线
  （四项拍板全走推荐项：①自举执行面全语料判据 ②自举链语言级缺陷真化
  ③0x62 公式模式自举贯穿 ④编译器框架接入 MBC 主线）：
  **29b 自举链语言级缺陷真化**——语句位下标赋值 `a[i]=v` STORE_SUBSCRIPT
  0x64 双面真化（VM 处理器列表原位写/越界透传/字典缺键新建/不可哈希键
  领域文案，编译器顶层+块位发射，native setitem_rt 五路错误）；lambda
  立即调用 `((x)=>x*2)(21)` 与链式；参数类型标注 `(y: Int) => …`；单 `=`
  右值悬空关系运算符回退；零参闭包 `f()` 自举面 IndexError 真修（解析器
  IntLit(0) 占位 arg，宿主/VM 忽略占位，自举 应用函数 补空参守卫）；
  缺失字典键双端对齐 vm→host（缺键返 null）；错误文案归一（变量未被定义
  ↔ 未定义变量）。
  **29c 0x62 公式模式自举贯穿**——FORMULA_SCHEMA 从宿主编译器专有贯穿
  自举链 parser→interp→compiler→vm.matha 四面（`test_selfhost_formula_
  phase29` 17 项）。
  **29d 执行面双轨判据**——A 轨 pytest 轻中档锁（自举语言 14 / 执行 31 /
  矩阵 3 / 公式 17 项入常规门禁）；B 轨 `scripts/selfhost_matrix.py`
  全语料 sweep（多进程 + boot 复用）+ 快照 `docs/selfhost_matrix.json`
  `--check` 重档通道（225 语料：双面一致 147 / 宿主独过 61 / 双败 17 /
  超时 0 / 双面分歧 0）；登记不修清单见 KNOWN_ISSUES 阶段 29 收官条目。
  **29e 编译器框架接入 MBC 主线**——`src/compiler/mbc_adapter.py` 两条
  MBC 字节码遍（常量折叠：调用 VM 同一 `_BINOPS/_UNARYOPS` 求值故结果
  与运行期逐位一致，除零/sqrt(-1) 等报错诚实保留运行期路径，仅折叠
  不可变结果，跳入模式中段保守跳过，折叠到定点 + 池类型严格去重；死代码
  消除：按 JMP/JZ/JNZ/RET/RAISE/RAISE_MATCH/HALT 语义可达性 BFS，删除
  不可达指令并重映射跳转目标）经专用 PassManager 调度（不与框架泛 IR 遍
  混跑同一 program）；接入方向反转——内核 `exec_api` 不 import
  src.compiler（dep_audit 棘轮遗留面），暴露纯编译后钩子槽
  set_compile_hook/get_compile_hook，适配器 import 即反向注册；双保险
  opt-in 默认关（未 import = 无钩子；import 而开关 features `MBC_PASSES`
  关 = 钩子自查原样返回），`compile_module`/`run_checked`/`build_exe`
  全编译管线同一钩子面；`test_mbc_passes_phase29` 30 项（接入面锁 /
  遍实效锁 / 开关 on-off 双态对拍 15 语料）+ features 五开关入册
  （`test_extension_system_phase23` known_states 4→5 键）。
- 阶段 30 自举执行面收口（五片全落，30e 拍板①驱动器级注入）：
  **30a 执行分派收口**——interp_matha.matha 求值/执行语句分发表扩
  （读取块/设值/跳出/继续/返回语句真化 + 结构体/枚举/属性路由 +
  下标/切片求值支，29-④ 未支持节点组退役）；**30b use 跨模块收口**——
  模块名表扩 + 非函数符号合并（Token 跨模块未找到 29-③ 退役）；
  **30c 双面错误文案对齐**——除零/取模/整除/不可调用/类型名大小写 boot
  面与宿主逐字一致；**30d 语法缺口真化**——列表推导
  `[e for t in it if c...]` boot 解析/求值/编译三面 + 类型索引
  `list[类型]` + sqrt 一元前缀 + stdlib_symbols 构造；**30e B 轨驱动器级
  域符号注入（拍板①）**——宿主 Interpreter 全表面内建经 28d
  register_builtin 端口入 boot env（可调用值柯里化适配、常量值仅绑 env、
  链判据关键名 type_of 双面不覆盖保留 VM 面、解析失败符号诚实跳过保持
  boot_err）+ 资源预装载（资源_加载/资源_成长）+ 跨文件 use 依赖装载。
  快照 225：双面一致 203 / 诚实 differ 3（对象身份/未定种子输出如实分歧）
  / boot_err_host_ok 0（29d 61→清零）/ both_err 17 / timeout 2（interp/
  stdlib_symbols 重档自检 >120s 双面未完成）；宿主 type_of(null) 补 Null
  分支对齐 VM 面（src/interp.py）。A 轨新档：test_selfhost_errmsg_
  phase30 + test_selfhost_syntax_phase30 + test_selfhost_domain_phase30
  （29 项）；登记不修清单见 KNOWN_ISSUES 阶段 30 收官条目。
- 阶段 31 语言完备与判定面收敛（六片全落，30e 域注入后判定面收口）：
  **31a func 定义 `->` 可选**——宿主/自举 parser `func 名(参) = 体` 无返回
  类型标注简写（带 `->` 形态不变），29-⑧「func 必须写 `->`」退役，三面
  （vm/hi/mb）+ 双编译器字节码对拍；**31b 双 for 推导**——`[e for a in …
  for b in …]` 与尾缀 `if` 组合 boot 解析/求值面真化 + 字典源迭代产出
  ('k',v) 对（vm 面字典源 KeyError(0) 登记）；**31c 块体链管道**——块体内
  `A >> B` 链求值真化（vm/mb 面；顶层链仍语法拒绝，宿主解释器面 ChainStmt
  暂不支持求值维持登记）；**31d 调用守卫 + 字典/字符串 for**——不可调用值
  （5/[]）双面诚实报错文案对齐 + 字典对产出（('k',v)）+ 字符串逐字符迭代；
  **31f 切片求值对齐**——列表/字符串/元组切片六形态 boot 解析/求值/编译
  三面（元组切片 vm 面返列表、hi/mb 保元组登记；非容器切片 vm TypeError /
  hi·mb MathaRuntimeError 原生形态）；**31e preload 装配 + 31g 判定面**——
  sweep `_manifest_preloads`/`_assemble_source`（BOM 剥离 + 预装载 prepend）
  真跑资源装载，warmup barrier `map_async(_warm, workers*2)` 预热 +
  `--timeout` 默认 600s；快照 225：双面一致 206 / 诚实 differ 3 /
  boot_err 0 / both_err 13 / timeout 3（golden 36-39 both_err 清零：36/39
  →equal、37/38 装载真跑 >600s 双面同判 timeout；interp.matha boot 面重档
  >600s、host 面单跑 1.2s——共享预算 boot 先耗尽 host 未及跑，如实归因见
  KNOWN_ISSUES 31；stdlib_symbols 600s 预算内 ok）。A 轨新档
  test_selfhost_language_phase31（19 项三面+字节码对拍）；登记不修清单见
  KNOWN_ISSUES 阶段 31 收官条目。
- 阶段 32 语言收敛与元组真化（五片语言收敛 + ② 元组真化受控切片，拍板
  「以维持登记为基础，以切片真化的方式推进，拆分可回滚受控切片逐个验证」）：
  **32a VM 字典迭代四面归一**——宿主编译器 for/推导三发射位统一经 `_迭代源`
  内建 + vm.matha 镜像 + native iter_source（dict → ('k',v) 对；31-①
  VM 字典源 KeyError 退役）+ BUILD_SLICE 不可切片守卫三面同文案；**32b hi
  面 ChainStmt 块尾链真化**（31-⑤ 退役，三面同判）；**32c boot 编译器推导
  发射真化**——单/多 for+if（31-⑥ 退役，28c parity 全语料）；**32d mb 面
  str 通用化**——Bool/null/容器/函数渲染 + 自举闭包守卫（28-⑨「stdlib str
  数字专用」退役）；**32e let rec 互相递归三面贯穿**——hi 预注册占位 +
  VM 预发盒 + boot 待填盒镜像（29-② 退役）。**32-② 元组真化受控切片**：
  S1 BUILD_TUPLE 运行时指令面（0x65=101，三执行体直注执行、零发射零行为
  变化）；S2 发射面切换——宿主+boot 编译器元组字面量 → BUILD_TUPLE
  （31-②「元组按列表处理」退役），native 消费面语料回归，stdlib/vm.matha
  str 元组渲染臂，`-` 容器守卫四面同文案；自举编译器同名函数重定义出口
  去重（宿主 dict 保首现序取末值语义镜像，拼接编译函数表千级规模出口
  一次性双遍完成）。A 轨新档 test_tuple_instruction_s1_phase32（11）+
  test_tuple_emission_s2_phase32（44）+ test_selfhost_language_phase32
  （20）；登记不修清单见 KNOWN_ISSUES 阶段 32 收官条目。
- 阶段 33 mb 面分歧收敛（六项 mb↔宿主语义/文案分歧三面 + VM² 收口）：
  **33a 单元素尾逗号 `(1,)` 诚实拒绝对齐宿主**——boot 解析括号消解 逗号
  分支补右括号守卫（此前经 解析实参列表 RPAREN-first 空参臂静默吞成分组
  (1)——32-① 退役；宿主=SPEC 同文案带 L:C 前缀）；**33b mb 比较族九臂
  与 not 返 真/假 Bool**（interp_matha 应用运算全族改 真/假——32-④
  退役）+ **条件路由真值归一**（求值 if/语句 if/while 经 真值 helper，
  空容器/零/null falsy——32-⑦ 退役）；**33c `in` 成员判断四面真化**——
  vm `_op_in` 容器守卫（vm.py）+ native 容器守卫（raise_rt 可捕获，旧锁
  test_in_non_container_is_false 按真化退役惯例改锁诚实报错）+ mb
  `_成员判断`（标准库.find/dict_has 委托）+ VM² interp.matha 镜像；
  List/Tuple/Dict/Str 命中/未中 + 非容器右侧「in 右侧需为序列/集合/字典，
  实际 int」四面同文案（32-③ 退役）；**33d hi 面 if 无 else 条件假 →
  null**（src/interp.py IfExpr/IfStmt else 缺失臂补 None，此前崩
  NoneType；VM 面 None 同判）；**33e mb type_of/_to_tuple 注册真化**
  （32-⑤ 退役）+ **sum 累加器 0 起**（stdlib list_sum，sum([])=0 Int
  ——32-⑥ 退役）。**33h slice 内建字符串臂真化**（收官探针踩中顺手真修）
  ——mb 应用内建实 slice 臂此前无条件走 list_slice，字符串实参产出字符
  列表（split 块变 ['a'] 形）；33b 提速后 golden 38 语料 600s 预算内
  首次真跑完成、timeout→differ 漂移显形此根因。String 实参改走 31f
  `_切片值` 字符串臂（负回绕/端钳 Python 语义）、List 维持 list_slice、
  Tuple/其他诚实报错「slice() 需要字符串或列表」（宿主=SPEC 同文案）。
  A 轨新档 test_selfhost_language_phase33（24 项：比较族/真值/in 三面
  +VM²+尾逗号诚实拒绝+hi 无 else+sum/type_of+slice 字符串臂/split 往返）
  + test_native.py in 节改锁+元组成员判断；登记不修清单见 KNOWN_ISSUES
  阶段 33 收官条目。
- 懒加载：`exec_api.compile_module(..., plugins="auto|strict|off")`；
  纯脚本运行时不 import 任何 `src.domains.*`；未加载即引用领域符号 →
  编译期诊断并列出候选插件名（`tests/test_plugin_contract.py` 含子进程取证）。
- **命名卫生门禁**：插件不得导出裸单字母符号、不得与 `.matha` 顶层声明同名
  ——防止插件污染内核「未定义名即报错」契约。
- 重型后端只在调用那一刻 import：`src/domains/symbolic_calculus.py` 为样板
  （内核引擎答不出的能力缺口才惰性 `import sympy`，顶层 import 一律禁止）。
- 消除静默假成功：外部工具链不可用 → 显式失败 + 诊断，不再 `mode:"simulated"` 冒充。

### 四、自举（bootstrap）推进到 stage-2 不动点

- 引导链 `lexer.matha / stdlib.matha / parser.matha / interp.matha /
  compiler_matha.matha` 五文件全部由自举编译器编译并在宿主 VM 上执行
  （`tests/test_mbc_bootstrap.py`，M3V 闭环）。
- **stage-4 脱宿主闭环（阶段 27b）**：vm.matha 加入 joined 闭包后，
  【stdlib + vm.matha】经 boot 链 VM²（编译出的编译器 + 编译出的 VM）编译
  与宿主编译逐字节一致；VM² 内可跑编译出的代码（tier B）并实例化独立 VM
  运行自举产物（tier A）——`tests/test_stage4_closure_phase27.py`。
- **stage-2 不动点**：用自举编译器编译【整条引导链】得到 stage-2 编译器，
  再用它编译 `matha/vm.matha`，产物与 stage-1 及宿主编译 gold **逐位一致**
  ——编译器自编译后行为不变（`tests/test_mbc_vm_matha.py`，标 slow）。
- 双重自举闭环：自产 lexer+parser 编译后照常 tokenize/parse。
- 旧「自举 65.4%」一次性报告已移入 `docs/history/`，不作为现状依据；
  现状以 tests/ 全绿为准。

### 五、VM ↔ native 机器码平价与静默失败清零

- AST×VM 覆盖矩阵：78 节点中 59 发射 / 19 有意无码 / **0 不认识、0 阻塞缺口**；
  202 份语料 **0 解析失败**（`docs/ast_vm_gap.md`，机器生成）。
- 指令码 34 条 VM 全分派、native 全发射；黄金用例 **39** 例 vm ↔ interp
  逐字节一致，`--native` 真 exe 对拍已知缺口 **0** 例
  （`golden_tests/manifest.json` `native_known_gaps`；
  `18_domain_lazy_load` 属设计内 SKIP——exe 无 Python 宿主，不承载领域符号，
  契约由 `tests/test_native_domain_contract.py` 上锁）。
- 修复三类「无声失败」：未定义变量静默读裸 0、字符串/列表参与 `-` 假减
  （NI-001/002 → `raise_rt` 可捕获异常）；闭包 env 稠密写入/原始槽读取的
  非连续捕获段错误（NI-009 → 按原始槽号打包，黄金用例
  `30_corpus_nested_rec_nocap` 三端锁定）。
- ListComp：先改显式报错杜绝静默返空（`d786e10`），再由 VM 编译为与 `for`
  同构的下标循环 + `append` 累加（`673f983`，零新 opcode；黄金用例
  `35_list_comp` 三端锁定）。
- 修复顶层 Output 表达式误用非 main 作用域致临时槽 STORE_LOCAL 越界。

### 六、错误语义跨后端归一

- 除零 / 取模除零 / 整除除零 / 类型不匹配 / 列表越界 / 字符串越界 /
  不可调用 / 不可下标对象取索引 / 未定义变量 / 未定义函数名——共 10 例错误
  黄金用例，vm ↔ interp ↔ native 抛**同一异常类**且消息主体逐字一致。
- 未定义变量类名统一为 `MathaUndefinedNameError`；未定义函数调用归一为
  「未定义变量」口径（VM 字节码 LOAD_GLOBAL 共用读取位），`AutoDebugger`
  相应改为从源码判定，自动修复行为不变。

### 七、数学与符号层

- 内核符号引擎 `src/kernel/symbolic/`（纯标准库）：±∞ 极限改**精确主部比**
  （对标 sympy 主导项法，含奇偶变号）；`ln` 归一为自然对数别名；
  任意点泰勒输出 sympy 的 `(x-a)ⁿ` 中心形式；`abs` 分段原函数。
- Matha 标准库 `matha/library/`（6 个 `.matha` 文件，mbc VM 执行）为 CLI
  默认符号路径，能力缺口显式「不支持」并回退内核 stage0（回退记账，非假成功）；
  与 sympy 的逐项能力对照见 [symbolic_parity.md](symbolic_parity.md)。

### 八、语法层窄修与语料合法化

- 曾经 19 个 `.matha` 语料文件过不了 parser（`？` 占位符误用、记录面 `#：{}`、
  后缀式条件等），已全部改写为合法 Matha（文件保留不删，兼容承诺），
  语料解析失败计数归 **0**。
- 语句位三元 `==` 优先级误析修复（黄金用例 `32_ternary_eq_precedence`）；
  科学计数法字面量 `1e-15` 三端锁定（`33_sci_notation`）；
  `return [x]` 归一为列表字面量不再既打印又返裸值（`34_return_list_literal`）。

### 九、治理与文档如实化

- **唯一版本源**建立：仓库只允许 `src/__version__.py` 出现版本字面量，
  `src/__init__.py` / `matha_main.py` / `pyproject.toml`（dynamic attr）/
  `matha --version` 全部取同源（`tests/test_single_version.py` 机器判定）。
- 文档数字全部改由 `scripts/repo_facts.py` 现场数出，`tests/test_doc_facts.py`
  核对文档与代码漂移（漂移即红）；旧自评评分表（各维度打满分的愿望数字）
  从本文件删除，118 份一次性报告归档 `docs/history/`。
- 门禁一条链：`make check`（`scripts/check.py`）串起 tests / kernel_purity /
  ast_vm_gap / golden / dep_audit / native_parity 六项，对外只产出**一个**
  通过率；口径纪律禁止静默假成功（起跑失败记失败、工具链缺失记跳过并显式打印）。
- 根目录与 `scripts/` 的一次性调试脚本集中移入 `scripts/scratch/`（NI-008）。

## v4.5 及更早（历史归档摘要）

### v4.5（2026-09-26）：领域模块大规模扩张

游戏、图形、Web、数据库、安全、神经网络、并发、区块链、量子、音视频、
化学、天文、音乐、机器人等领域模块入库；并发原语
（Future/Promise/Mutex/Semaphore/Work-Stealing）、LSP 增强、
物理引擎与标准库内置函数扩展；文档同步建立教程 / 示例 / 贡献指南。

### v4.4.x：手写 x86-64 机器码发射器与 mbc 主线成型

`src/mbc/native.py`（不依赖 LLVM/汇编器，产出 Windows PE64）与 mbc
字节码 VM 主线成型；黄金测试集基线落地。

### 旧口径清理

该时期的自评评分表（各维度打满分的愿望数字）与「缺陷已全部解决」类
计数口径无判据可复现，已于 v4.6.0 治理中全部从文档清除（含本文件旧版）；
细目见 [`history/`](history/)（不作为现状依据）。
