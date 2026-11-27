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
- 阶段 34 语言面继续收敛（六项登记分歧真化收官，两项拍板全走推荐项——
  ①34c 统一 boot 中文文案 ②34f hi→None 对齐 vm）：**34a 尾逗号全族
  真化**——boot 解析器多元素尾逗号 `(1, 2,)`/调用位尾逗号 `f(1,)`/
  单元素尾逗号 `(1,)` 三形态同文案诚实拒绝「期望表达式 (got
  PUNCT_RPAREN ')')」（宿主=SPEC；列表尾逗号 `[1, 2,]` 三面合法维持
  ——33-① 全族退役）；**34b 语句位 if `[` 路由真化**——宿主 parser
  语句位语境分派 `_in_cond_value`（28-⑦「语句位 `[` 路由一致性」/
  33-② 退役：三面 `输出(if 1 { 输出(x) })` → [[x]]/[[y]] 同判 +
  while 空容器 falsy 零迭代 + VM²）；**34c `in` 左侧文案四面统一
  boot 中文**——「in 左侧需为字符串，实际 int」（vm `_op_in` 左臂
  守卫 + native err_in_left_prefix + hi interp.py 臂 + mb `_成员判断`
  ——33-③ 退役，正例 `"ell" in "hello"` 三面 真 维持）；**34d slice
  元组实参 vm 收敛对齐宿主**——`_builtin_slice` Tuple/其他诚实报错
  「slice() 需要字符串或列表」（native `fn:slice` err_slice_dom 同判
  ——33-④ 退役；下标 `(2, 3)[0]` 元组面维持）；**34e boot for (k,v)
  多变量目标真化**——matha/parser.matha for 目标二义分派（名单解构）
  + interp_matha `_解构绑定`/`_解构绑定进`（32-⑨ 退役；五形态 VM²
  sweep + boot 编译器发射面诚实拒绝「boot 编译器 for 解构目标暂未
  支持」维持登记）；**34f hi 面 func 值求值真化**——块尾 func 定义
  块值 → None（interp.py FuncDef 臂，vm 同判；mb 解析拒绝维持登记
  ——32-⑪ 退役）。A 轨新档
  test_selfhost_language_phase34（27 项：尾逗号三面/if 路由三面+VM²/
  in 左侧三面+VM²/slice 三面+VM²/for 解构五形态+编译器诚实拒绝/
  func 值三面/裸键登记锁）；旧锁退役三处——test_32a_dict_for_kv_
  boot_parser_honest_reject → test_32a_dict_for_kv_boot_true（真化
  改锁）+ test_31g_snapshot_classes timeout→all-ok（33 收官快照重
  生成后改锁滞后收口，非缺陷）+ phase33 33c/33h in·slice 锁随真化
  收敛改锁；登记不修清单见 KNOWN_ISSUES 阶段 34 收官条目。
- 阶段 35 自举解构贯穿（两项登记分歧同根退役 34-①④，主线拍板走推荐项
  「自举解构贯穿」）：**35a S1 UNPACK_SEQ 长度守卫四执行体真化**——
  统一解构语义（序列 = List/Tuple 且长度精确等于目标数，否则诚实报错
  「解构失败：期望 N 个元素，实际 <类型名>」list/tuple/int/float/bool/
  str/dict/NoneType/function 八族）：①vm 面 0x57 处理器严格化（此前
  越界补 None、非序列漏出 Python len() TypeError；Closure 映射
  "function"——34-④「编译路径宽松补 null」退役）；②hi interp.py let
  元组绑定守卫（语句位此前非序列静默不绑定假成功→下游未定义变量、
  短元组补 None；表达式位此前仅 tuple、短元组补 None、异文案；扩
  List/Tuple 同判，FuncDef/Lambda 节点与 ("__closure__",…) 标记元组
  → "function"）；③vm.matha 解包守卫（懒三元 合长，防 eager and/or
  陷阱）+ `_解构类型名` 映射（VM² 闭包 ["__闭包__",…] 3 元列表标记 →
  "function"）；④native unpack 严格化（si_n_* 静态类型名 + int_to_str
  运行期拼消息，try/catch 可捕获 + 未捕获 rc=1 stderr——旧 全 None/
  字符串逐字节解构/越界补 None 路径退役）。**35b S2 boot 编译器 for
  解构发射真化**——compiler_matha `_分配循环变量` 收窄单变量 +
  `_分配循环变量们`/`_分配循环位置们` 名单归一逐名折叠（宿主
  _emit_for_stmt names 归一 + var_ts 镜像）+ `_for循环码` UNPACK_SEQ n
  发射 + `_存解构逆序` 逆序存储（宿主 reversed(var_ts) 镜像）——
  34-①「boot 编译器 for 解构目标暂未支持」退役；单变量 for 字节码零
  变化（parity 回归锁）；多变量五语料（单变量/字典对/三变量/局部函数/
  元组对）stage2↔stage3 逐位一致 + M3V 运行面真跑。A 轨新档
  test_selfhost_language_phase35（42 项：let 元组 vm/hi 正控·错控·
  语句位·闭包映射·mb 登记锁 + for 三面 + VM² interp + M3V 正控·错控
  + 35b parity·M3V runs·try/catch 登记锁）+ test_native.py 解构节
  宽松锁改诚实锁（3→4）+ phase34 34e 编译面诚实拒绝锁按真化退役改锁
  UNPACK_SEQ 发射；登记不修清单见 KNOWN_ISSUES 阶段 35 收官条目。
- 阶段 36 mb/boot 面收口批（四项登记分歧真化收官，35-① + 34-②③⑤
  退役）：**36a 表达式位花括号 if 真化**——boot parser.matha 解析if
  表达式补花括号分支（宿主 _parse_if_expr_impl 语句形式分支同构：解析
  语句列表块体 + 期望右括号花；else 附着仅 否则 关键字，英文 else 不
  消费；无 否则 假分支=null 33d 同形）+ interp.matha 求值 程序 臂
  （块执行取尾值，宿主 CodeBlock 块值模型同位）——`let x = if 1 { 2 }
  in 输出(x)` 六形态三面同判 + 输出尾块值 [5, 6]（34-②「mb 表达式位
  if 无 then 解析拒绝」退役）；**36b mb 面块尾 func 定义块值真化**——
  interp_matha 执行语句/执行声明 函数定义臂 (closure, env2) →
  (null, env2)（函数仍入 env 仅值面不回传，宿主 FuncDef 执行返 None
  同构）+ interp.matha 双臂镜像——`{ func f() = 1 }` 块值 [None] 三面
  同判、blk_used `f()` [1] 维持（34-③ 退役）；**36c boot 字典裸键
  真化**——interp_matha/interp.matha 求值字典 `_字典键` helper
  （"变量" 键析为字符串键名，其余求值）——`{a: 1}` ≡ `{"a": 1}` 四面
  同判（34-⑤ 退役）；**36d mb 表达式位 let 元组绑定真化**——
  interp_matha 求值let元组/绑定求值let元组 + `_解构绑定元组`（闭包
  标记 ["__closure__",参数,体,env] 跳参绑定镜像宿主，懒三元防 eager
  and/or 陷阱；错误「解构失败：期望 N 个元素，实际 <类型名>」四面同
  文案）+ 求值/执行语句/执行声明 三臂路由——`let (a, b) = [1, 2] in
  a + b` 三面 [3]（35-① 退役）。A 轨新档 test_selfhost_language_
  phase36（23 项：36a 六形态三面+语句位中性+VM² / 36b 块值三面+VM² /
  36c 四形态三面+VM² / 36d 正控·错控四面+function 映射+VM²）+ phase34
  三锁按真化退役改锁（34f×2 + 34x 裸键）+ phase35 35a 登记锁改锁
  test_35a_let_tuple_mb_true；登记不修清单见 KNOWN_ISSUES 阶段 36
  收官条目。
- 阶段 37 语言面清尾批（五项登记分歧退役：32-② 31-③ 协议一致锁 +
  32-⑩ 36-① 36-② 真化，主线拍板走推荐项「A：语言面清尾批」）：
  **37a 陈旧登记退役**——32-② 空括号 () 三面早已统一零参调用约定
  （() 降糖 IntegerLit(0)，f() = f(0)，表达式位 () 即 0）与 31-③ 非
  容器切片三面早已统一 MathaRuntimeError 同文案「切片操作不支持:
  int[1:2]」（31f 真化后编译面 raise_rt 与解释面同源），均无行为改动，
  协议一致锁防漂移；**37b 块尾 Binding 值模型收尾（36-② 退役 + 同族
  顺手真修）**——interp_matha 绑定求值let 无体臂 (v, env)→(null, env)
  + interp.matha 同形 + 表达式位块（求值程序/求值 程序 臂）尾值
  `_块尾值` 映射（绑定/let绑定/let元组绑定尾不回传值，宿主
  _BLOCK_TAIL_STMT_NODES 头三族；程序位顶层 run_ast → 执行语句保持
  「程序值 = 尾表达式值」约定不映射——首稿映射置 执行声明列表 尾泄漏
  程序位，门禁 run1 phase8pre gapfix 四红抓获即修收窄至表达式位）
  ——四形态三面 + VM² 同判 [None]，有体 let 尾与裸赋值尾同族收敛；
  **37c 链式 let rec 互递归真化（32-⑩ 退役）**——interp.py 表达式位
  LetBinding 链头收集 body 链 rec 名建注册表压栈（`_rec_chain`）逐名
  预绑占位，成员复用未填占位（_ref 未填守卫——32e 勘误保留：弹栈后
  同名恒新建、跨函数在途占位不串线）+ 块/程序入口预注册沿 body 链整链
  （`_preregister_rec_chain`——37c 前 body is None 条件漏带体链）+
  interp_matha/interp.matha 预绑链占位镜像 + 占位复用守卫——三面 +
  VM² 同判 [0]；**37d 字典自然键真化（36-① 退役）**——compiler.py
  `_literal_key` IntegerLit/FloatLit/BoolLit 原值入常量池（此前 int 键
  字符串化致 d[2] vm null）+ parser.matha `花括号种类` 数字/布尔首
  token 冒号前瞻 → 字典（此前 mb/VM² 误析集合）——int/float/bool/str
  键 + d["2"] 反向 null 三面 + VM² 同判；boot 编译器/解释器/native 随
  既有路径自然同判零改动。附带发现登记：vm/hi 输出尾块值 host 内部
  分歧（编译面语句尾 PUSH_NULL vs 解释面输出通道规则）+ mb 面集合
  构造求值未知表达式类型 + 37c 嵌套链同名成员 env 槽覆写边界。A 轨
  新档 test_selfhost_language_phase37（19 项：37a 协议一致锁 ×4 +
  37b 四形态三面+VM²+中性 / 37c 四形态三面+VM²+回归 / 37d 三面+VM²+
  中性 / 37x 登记锁 ×2）+ 旧锁真化改锁四处（phase31 31f vm 面文案+
  类型加强、phase32 test_32e_chained_mutual_true、phase36
  test_36x_vm_dict_intkey_true / test_36x_blk_tail_binding_true）；
  登记不修清单见 KNOWN_ISSUES 阶段 37 收官条目。
- 阶段 38 m3v 异常帧机制（35-② 真化收官，载体不可知单点包裹）：方向拍板
  走推荐项「A：m3v 异常帧机制」+ 修复形态拍板走推荐项「捕获闭包单点包
  裹」。vm.matha 两个分派位用 Matha 级 调用捕获 单点包裹——**捕获闭包
  位** `调用捕获((p) => 执行(p[0],…,p[4]))`（实参双嵌套 [[…]] 配对
  invoke_value 的 fn(*args) 铺开）：守卫 "__异常__" 时以 ["__异常__",
  消息] 标记入顶帧（try/catch 正常接管），否则 子结果 = 守卫[1] 走既有
  "__抛错__"/"__停机__" 臂（带内路径零变化）；**捕获内建位**同形 →
  "__异常__" 转 ["__抛错__", 消息] 统一打标。载体派发家族（除零/解构失
  败/未定义变量）三面 + VM² 同判；带内 RAISE 路径零扰动。A 轨新档
  test_selfhost_language_phase38 12 项（38a1 四族 vm↔m3v 捕获 parity——
  badindex 双面各断正典文案 / 38a2 带内回归 / 38a3 finally 序 / 38a4
  catch 重抛逃逸 / 38a5 部分输出保序 / 38a6 既有名保序 / 38a7 新建名登
  记锁 / 38a8 内层边界胜+逃逸对齐）+ 35x 真化改锁
  （test_35x_m3v_try_catch_registration → test_35x_m3v_try_catch_true，
  一函数三族内部循环）。vm.matha +46−31 单文件改动；src/ 零改动、指令
  码不变；门禁全绿首跑零红（tests lane 7841 过 + 1 平台 skip 4532.21s +
  purity 14 + gap 11 快照零扰动 + golden 39/39 + dep_audit 0 违规 +
  native 38/39 + Track B --check 一致）。算术闭合：7945 条件 = 7944 过 +
  1 skip = 7933（37 条件）+ 12；登记不修清单见 KNOWN_ISSUES 阶段 38 收
  官条目（vm↔m3v 下标越界文案分歧① + 新建全局名捕获路径丢失②）。
- 阶段 39 Track B both_err 归因批（方向 A：逐个归因 13 both_err 语料——清零
  或如实登记为边界）：**39a 链面应用分派收口**——① λ-AST 字典应用臂（
  interp_matha/interp.matha 应用函数·应用多参数函数 Dict 臂此前只认
  "__builtin__"，`语法器.做Lambda` 裸节点字典落「不可调用的值」；现经
  `求值lambda` 折闭包重入 __closure__ 机制，柯里化/多参同臂复用）② 不可调用
  值渲染载体 `标准库.str` → `标准库.元素repr`（CPython repr 规则，str/空串/
  int/列表/CJK/转义六形态 vm/hi/mb/bootvm 四面消息逐字同判，既有 ': 5' /
  ': []' 锁零扰动）③ interp.matha 零参 λ 守卫（`做Lambda([], body)` 此前落
  原生 IndexError，镜像 interp_matha 29d 空参数表口径）；**39b/39b-2 未定义
  变量异常类真化（31-⑧ 退役）**——类型化抛错内建 `未定义错误` →
  `MathaUndefinedNameError`（hi BUILTINS + VM `_default_builtins` 同类抛错、
  消息逐字不变），链面 `查找环境`/`查找环境链`/`查全局` 缺名臂改走该内建，
  vm.matha `内建名表` 注册（防 查全局 自递归）+ `内建特殊` 带内臂 + `应用内建`
  专用名守卫补名，且同列宿主两侧 `_RESERVED_BUILTINS` 与 vm.matha `是保留
  内建名`（守卫先于插口分派——注册必被遮蔽，四面一致诚实拒绝）；**39c/39d
  语料与源序**——`bootstrap_matha` 刷新到现行柯里化 API（host 面旧错「属性
  访问失败: str.类型」退役为 4 输出双面 ok）+ `compiler_matha` 的 `不折叠`
  模块级 let 前移模块顶（宿主闭包按定义序快照环境——`bootstrap_full_test`
  host 面旧首错名退役，22 输出双面逐字相等）+ 本地 `dict_from_pairs` 十行
  副本退役为 `use 标准库` 导入；**39e 判定面细分**——`_classify` 双 err 且
  `boot_err == host_err` 逐字全等 → `both_err_equal`（双面同判的诚实边界与
  残留分歧分列）+ summary 七分类键 + `structure_check` 缺键诚实报「需 --write
  重生成」。A 轨新档 test_selfhost_language_phase39 31 项（39a λ-dict 四面+
  元素repr 六形态四面+零参三面+VM² / 39b 未定义变量四面同载体+类层级+golden
  逐字 / 39b-2 m3v 三锁+结构锁 / 39c/39d 语料双面+源序锁 / 39e 细分三锁）+
  陈旧边界锁改真化锁两处（phase21 `test_boundary_bootstrap_full_test` /
  `test_boundary_bootstrap_matha`）。门禁：tests lane 7871 过 + 1 skip
  4260.29s + 1 红（doc_facts 本体量过期——docs 同步后单跑全绿）+ purity 14 +
  gap 11（快照零扰动）+ golden 39/39 + dep_audit 39 内核文件 189 import 边
  0 违规 + native 38/39（0 失败）+ Track B --write 重生成 225 = 双面一致 211
  / 诚实 differ 3 / both_err_equal 11 / both_err 0 / timeout 0（both_err
  13→0）+ --check 复现一致。算术闭合：7976 条件 = 7975 过 + 1 skip = 7945
  （38 条件）+ 31；src/ 仅 vm.py +16 行（39b 类型化抛错内建 + 注册 + 插口保留
  名），boot 编译器 stage2↔stage3 逐位一致零扰动；登记不修清单见 KNOWN_ISSUES
  阶段 39 收官条目（三引号字符串 / 加载模块 胶水形状 / m3v 直调 未定义错误
  边界类）。
- 阶段 40 真缺陷批（方向 A：Track B 两类残留缺陷清零——三引号字符串 +
  differ 3 语料；40b 形态拍板「产品侧真修」；未闭合字符串同批真修）：
  **40a 三引号多行字符串双端词法器真化（39-① 退役）**——宿主 `src/lexer.py`
  新增 `_string_triple` 三态扫描（闭合三连 / 转义续行 / EOF 未闭合诚实报错）
  + `"` 与 `'` 首字符三连判定分派位（+30−2 → 本体量 33,480）；boot 镜像
  `matha/lexer.matha` `是三连`/`扫描三引号续`（+37−5）。七形态 token 值/行/
  列双端逐位 parity（`""""""` 空串、跨行串、`"""a\tb"""` 转义、`'''…'''`
  单引号三连…），多行值 vm/hi/mb/VM² 四面 + M3V 六文件链同判；未闭合串四形
  态双端同文案「字符串未闭合」（载体类名 LexerError↔MathaRuntimeError 登
  记③，225 语料零含未闭合串故判定面零漂移）；`matha/bootstrap_test.matha`
  测试 4 由诚实拒绝真化为跑通。**40b differ 3 语料收口（31-⑨ 退役，
  both_ok_differ 3 → 0）**——按登记根因产品侧真修而非放宽 `selfhost_matrix.-
  _norm`（不透明对象仍按身份比较）：宿主值语义 `__eq__`/`__repr__` 补
  `src/autonomous.py` `_OptResult`/`_GrowResult` 与 `src/domains/data_science.-
  py` `Dataset`（值元组逐字段、可变故不设 `__hash__`；`_Sample` 含挂钟耗时
  故意不改）；神经网络显式播种——`src/ai_framework.py` `seed_random`（同种
  子同权重 / 异种子异权重 / 非 int 含 bool 诚实拒绝）+ `src/domains/neural_-
  network.py` `随机种子` 柯里化内建 + `_nn_symtab_names` + registry 模板
  functions + `manifest.json` 重生成（`--check` 绿，89 插件 / 2806 符号）+
  语料 `examples/ai/neural_network.matha` 顶置 `随机种子(2026)`；
  `输出(随机种子(2026))` hi/vm 双面 [2026]。**40c 旧锁收口与判定面**——
  Track B 快照重生成 225 = 双面一致 215 / differ 0 / both_err_equal 10 /
  both_err 0 / timeout 0（bootstrap_test 由 both_err_equal 转 both_ok_equal）
  + --check 复现一致；真化改锁四处（phase30 differ 三语料、phase39 39c 三
  引号根因、phase19 与 phase21 bootstrap_test 边界锁——裸解释器面需按 Track
  B worker 口径抬递归预算方可跑通 [54, 3, 57]，登记④限幅伪影；官方门面
  exec_api 面同判）。新登记两条语言面边界：`matha/interp.matha` 缺 机械单元/
  生成语句 执行臂（29c 只落 interp_matha.matha）+ NEWLINE token 位置/值约定
  分歧（其余 token 逐位同判）。A 轨新档 test_selfhost_language_phase40 27
  项。门禁全绿首跑两红皆为 40a 意外真化的陈旧边界锁（改锁后定向复跑 46/46
  绿）：tests lane 7899 过 + 1 平台 skip 4493.00s + purity 14 + gap 11（快
  照零扰动，无新 AST 节点/opcode）+ golden 39/39 + dep_audit 0 违规 + native
  38/39（0 失败）+ doc_facts 18。算术闭合：8003 条件 = 8002 过 + 1 skip =
  7976（39 条件）+ 27；登记不修清单见 KNOWN_ISSUES 阶段 40 收官条目（interp.-
  matha 镜像臂缺口① / NEWLINE 约定② / 未闭合串载体类名③ / 裸解释器递归预
  算④；退役 39-①、31-⑨）。
- 阶段 41 资源库假成功清算批（方向 A：只动纯 Matha 资源库 `matha/resource/**`
  ——37 文件 +2611 −767 行，`src/` 零改动、本体量 33,480 与指令码 36 不变；
  范围口径「危险桩真化 + 合法近似补口径注」分层；验证深度三面 hi / vm / 五
  文件 boot 链调用面）：**41a/41b/41c 假通过真化**——`HMAC哈希` 旧体直接返回
  消息本身（假摘要）改两轮 131 进制滚动散列（密钥入内外两轮）；`死锁充分条件`
  / `银行家安全性`（旧恒返 真；现经典安全性算法逐轮扫 Need，维度不齐声明
  fail-closed 取保守答——`需要至多`/`加向量` 短表守卫，不越过末尾下标落
  IndexError）/ `资源分配图含环`（旧恒返 假；现等待图 DFS）/ `活锁检测` /
  `SSTF·SCAN·C_SCAN 总移动` / `LRU 缺页` / `FCFS·RR·HRRN 周转时间` 残形改
  可判定真实现；`Dijkstra距离` 旧桩恒返 `[999999…]`（28-⑧ 退役）真化为权重
  和+1 作无穷 + O(V²) 顺序松弛、不可达记 -1；`内部收益率近似` 恒返 0.1 改二分
  求根；`二阶极点` / `音频混音` / `直方图均衡化映射` / `sepia滤镜` 同批改真；
  顺手真修 `中位数`（偶数长度走 `//`——`/` 恒浮除旧式落「索引操作不支持:
  list[1.5]」）、`复制列表`·`排序`（不改入参）、`时间戳转日期`（小数年 →
  整除，合 `-> Int` 声明口径）。**41d-1 链面缺失内建家族**——boot
  `注册内建(空环境)` 只 47 名（宿主 3020），`exp/log10/log2/ln/π/组合数/asin/
  acos/atan/atan2` 在链面直接「未定义变量」即整个函数不可调用（三面皆假失败）；
  逐文件改走三面同判路径：指数 `2.718281828459045 ^ x`、对数换底
  `log(x)/log(10.0)`、反三角走二分、`atan2` 走 `象限角`、`组合数` 走本地
  `组合数按连乘`（不扩 `matha/stdlib.matha`——会扰动 Track B 225 语料快照，
  登记①）。**41d-2 无定义读数 → None**——分母为 0、空表、越界、负方差等 15
  形态不再伪造 `999.0`/`999999` 哨兵或 `0` 读数（`产率` 旧以 0 冒充无基准），
  改诚实 None 三面同判。**41d-3 合法近似补口径注（零语义改动）**——长度比文本
  相似度、固定 365 天日历差、非 softmax 的分类置信度、Zeller 同族周几相位等
  注释如实写明近似口径与适用域。新锁档 `tests/test_resource_algorithm_true_-
  phase41.py` 247 项（223 三面同判正典读数 + 52 资源文件零缺失内建/零哨兵
  静态锁 + hmac/dijkstra/排序不改入参/中位数/银行家 五条语义结构锁 + `√(9)`
  渲染与载体异常类两条登记锁 + 依赖边界锁）。门禁：Track B `--write` 快照
  逐字节零扰动 + `--check` 一致（225 = 双面一致 215 / differ 0 /
  both_err_equal 10 / both_err 0 / timeout 0，52 个资源语料全 both_ok_equal）；
  ast_vm_gap 快照重生成（`scripts/ast_vm_matrix.py --write` +39 −39——节点 78 /
  发射 59 / 无码 19 / 阻塞缺口 0 / 指令码 36 结构不变，13 节点 `used_in` 随
  资源语料构造变动：ListLiteral 79→92、IndexExpr 77→85、SliceExpr 25→31、
  CodeBlock 104→110、IfExpr 96→101、UnaryOp 65→63 等）；tests lane 8146 过 +
  1 平台 skip（5322.09s；首跑 8145 过 + 1 处 `test_native.exe` 固定临时文件
  Windows 占用 PermissionError，按 flake 协议复跑：参数化 20/20 + 全档
  `test_native.py` 628/628 绿，非产品缺陷）+ purity 14 + gap 11（重生成后
  25 绿）+ golden 39/39 + dep_audit 39 内核文件 189 import 边 0 违规 + native 38/39（0 失败）+
  doc_facts 18。算术闭合：8250 条件 = 8249 过 + 1 skip = 8003（40 条件）+ 247；
  登记不修清单见 KNOWN_ISSUES 阶段 41 收官条目（链面注册内建表差① / `√(9)`
  完全平方数渲染② / None 算术载体类名③；退役 28-⑧）。
- 阶段 42 纯 Matha 装载器 + 终端链面默认后端（方向拍板：收口「终端与全量使用
  都是 Python、不是 Matha 自身」这条缺陷；范围切片「只做纯 Matha 装载器」——
  自修复/生长面不在本阶段；载体接缝「逐名补 16 条 Matha 臂」；终端「链面直接
  设为默认」）：**42a** 新增 `matha/loader.matha`——装载模块这件事本身由 Matha
  完成，宿主 Python 仅作 OS 能力的载体：`名表` 22 条（宿主 `_CN2FILE` 逐条镜像）
  / 三级解析序 `主路径`→`包路径`（`.matha_packages/<名>/manifest.json` 的
  `entry`/`enabled`）→`库路径`（`matha/library/` 递归）/ `内声明`+`收集使用名`+
  `去机械`（模块节点降一层、`use` 依赖递归、`机械单元` 自测块不随装载执行）/
  `摊平`+`并内建`（模块函数并入 env 使跨模块裸名可达、`内建` 别名表并入 ns 镜像
  宿主「ns 缺名 → 内建表回退」一路）/ 报错文案与宿主 `load_matha_module` 逐字
  同判；`装载根` 由装配方注入仓库根绝对路径（非 cwd——`换目录` 后装载仍命中同一
  批源）；装配壳 `src/matha_chain.py` 把 boot 链五模块 + 装载器编为 level-1 M3V、
  模块体经 `解释器.执行语句` 以 level-2 数据闭包执行。**42b** `matha/interp_matha.matha`
  + `matha/interp.matha` 双镜像补 16 条载体原语逐名臂（执行命令/执行命令输入/管道输入/
  管道结束/输入行/列目录/建目录/删除路径/复制文件/改名/换目录/路径存在/执行Matha/
  调试Matha/升级包/检查包更新）+ 语言级 `错误` 名，链面固定面 47→59 名（缺臂名如实
  「未知内建函数」，不静默回落宿主）；二元柯里化载体入 `内建元数` 表（`复制文件(a)(b)`
  首参调用产 `["__内建部分__", 名, args]` 不触达宿主实现，故探测期零副作用）。
  **42c** `src/matha_term.py` 默认后端 `chain`、`MATHA_TERM_BACKEND=host` 保留为
  对拍/排障入口、未知取值显式拒绝；后端装配在 `_startup()` 单点收口为「错误: …」
  + 退出码 1（此前装配异常逃逸出薄壳成 traceback，与终端「错误如实打印」口径不符
  ——本批真修的诚实性缺陷）；`调试` 在链面显式拒绝（VM 编译链无逐节点轨迹与环境
  快照能力），`src/mbc/vm.py` 拒绝文案尾句改指宿主后端（+1 行，本阶段口径内唯一
  改动，本体量 33,480→33,481）。链面成本实测：boot 装配 ~1.8s、装载 `终端执行器`
  ~20s、逐行 0.1–1.2s。新锁档 `tests/test_selfhost_language_phase42.py` 33 项
  （42a 解析序/清单/依赖收集/摊平/装载与宿主逐条同判 + chdir 后绝对性 + 缺模块
  文案同判；42b 注册面 59 名与逐名臂/元数表静态锁 + level-2 真达宿主 + 偏应用零
  副作用 + 无臂名如实拒绝 + `错误` 显式拒绝文案；42c 后端默认值/显式拒绝/无静默
  回落 + `BOOT_FILES` 差异锁 + 9 行终端命令双面逐字同判 + 链面 `调试` 拒绝端到端）。
  Track B 快照 225→226 = 双面一致 216 / differ 0 / boot_err 0 / both_err_equal 10 /
  both_err 0 / timeout 0（唯一变动为新语料 `matha/loader.matha` 双面同判
  both_ok_equal，其余 225 语料分类零漂移——boot 链 `interp_matha.matha` 补臂不改
  判定面）+ `--check` 复现一致；ast_vm_gap 快照重生成（节点 78 / 发射 59 / 无码 19 /
  指令码 36 结构不变，语料 230→231 随装载器入语料，21 节点 `used_in` 各 +1）。
  门禁与算术闭合见 KNOWN_ISSUES 阶段 42 收官条目。
- 阶段 43 冻结 exe 进程映像 + 常驻监管真化（方向拍板：「先从进程映像开始，必须冻结
  exe 而且必须是 Matha 的 exe」，先冻结可执行批、再在此之上做常驻监管批；验证深度
  「全量门禁 + 真 CMD subprocess e2e」）。**43a-1** `matha.spec` 重写为单 `Analysis` +
  单 `EXE(name='matha', console=True)`、语料整树入包（`matha/**/*.matha` + 前端
  `.c/.go/.js/.rs` + `src/domains/manifest.json`）、插件 hiddenimports 由清单推导、
  路径从 `SPECPATH` 推导、入口统一 `src/matha_main.py`、三条装配口径写入头注；
  `scripts/build_exe.py` 产物落点改平铺 `dist/<名>.exe`，与 CI/`build.bat`/安装脚本
  同口径（旧 `dist/<名>/<名>.exe` 使按平铺路径取件的一方必然落空）。**43a-2** 冻结态
  根口径（`src/matha_chain.py`）：`_ASSET_ROOT`（`sys._MEIPASS`）与 `_EXE_DIR` 分列、
  `MATHA_HOME` 覆盖优先不静默回落、语料根序镜像宿主 `_matha_dir()` 候选、扩展包根序
  cwd 优先、缺源如实「装配源缺失: …（候选 …）」；`matha/loader.matha` 改由 `当前目录`
  自行发现 cwd 根，链面注册面 59→60 名（第 17 条载体原语，`interp_matha`/`interp`
  双镜像同步）——42-①（`装载根` 只在 level-1 注入）与 42-②（扩展包未镜像宿主 cwd
  根序）两条登记退役。**43b** `start_matha_server.bat` 死件清算：旧版调用的
  `src.matha_daemon` 阶段 11 已删除，脚本从此从未启动过服务，echo 宣称的守护/健康检查/
  自动重启/防火墙入站四项能力全仓无实现——改指统一 CLI 新命令位 `server`（委托
  `src/openai_compat_server.serve`，有 `dist\matha.exe` 即用冻结映像起），`serve()`
  收口为唯一启动面（`main()` = `sys.exit(serve(...))`，端口占用文案不再指向已删模块）；
  同批 `git rm` 根目录死件 `Matha-Setup.spec`（入口指向早已不存在的
  `scripts/_setup_wrapper.py` 且硬编 `D:/trae/` 绝对路径，全仓零功能引用）。
  **43c** `运行脚本` 真化：`src/domains/os_module.py` 新增 `_self_launcher`（冻结态
  argv[0] 即 matha.exe / 开发态 宿主解释器 + `matha_main.py`），`.matha`/`.msh` 交
  Matha 入口、其它后缀交宿主解释器，`shell=True` 去除（路径不再是命令注入面）。
  **43d** 常驻监管：重启策略入纯 Matha 内核 `matha/os/kernel.matha`（+102 行——
  `常驻单元须有主入口` 显式拒绝 / `_启动落地` 先 `_收旧进程` 再 `_派主进程` /
  `_可重启` 五条件 / 每 `_调度轮` 尾 `_监督轮` / `监督状态` 只读 / 重启不记 `步数`），
  宿主 `src/os_runtime.py` 只留 `self_launcher`、`register_external(常驻, 重启预算)`、
  `supervision`、`supervise(轮数, 间隔, 回报)` 墙钟薄壳，`src/matha_main.py` 新增 `监管`
  （别名 `supervise`）命令位。冻结态实测：`matha.exe 监管 … -- eval 1+1` 被监管子进程
  映像名集合 = `{matha.exe}`、树内无 `python.exe`、崩溃单元读数 `['重启', 'flaky', 2]`；
  onefile 每次冷启解包 ~5.5s，监管窗口须按 `轮数 × 间隔` 覆盖两次冷启。**43g** Windows
  安装入口产物落点口径收口（15 脚本）：平铺产物路径、版本取唯一版本源
  `src/__version__.py`（旧 `setup_workspace.ps1` 硬编旧版本号且 `if (Test-Path $X -and
  -not $Force)` 触发参数绑定错误 + `??` 运算符，在 Windows PowerShell 5.1 上一步都跑不
  动）、`setx PATH "%PATH%"` 改按条目追加（1024 字符截断）、卸载脚本改交接式自删
  （cmd.exe 逐行读盘 vs PowerShell 先整体解析的实测不对称入锁）、仓库根由脚本自身位置
  推导、内嵌模板按目标语言校验。新锁档 `tests/test_frozen_entry_phase43.py` 89 项
  （43a 26 / 43b 6 / 43c 9 / 43d 15 / 43f 10 / 43g 23，其中 4 项 `@_frozen_gate` 在
  `dist/matha.exe` 不在位时 skip、在位时真跑冻结 e2e + 真 CMD 子进程取证）；改锁
  `tests/test_phase17_sweep.py`（spec 死 hiddenimports 判定改执行 spec 后断言推导出的
  `HIDDEN`，不再正则扫字面量）与 `tests/test_selfhost_language_phase42.py`（注册面
  59→60 名 + 新载体名在位）。本体量口径内 `src/` 零改动（33,481 行不变、指令码 36 不变）。
  门禁与算术闭合见 KNOWN_ISSUES 阶段 43 收官条目。
- 阶段 44 原生 OS 派生面（方向拍板：「Matha 与 Python 共存，不再调用 Python 任何模块，
  直接调用系统 API……对标底层的 C 语言」，首批切片「原生 OS 派生面」，stage-0 允许
  Python 仅作种子而最终判定用无 Python 的 Matha 原生映像自证）。**44b-1** 新档
  `src/mbc/native_process.py`（578 行）：`派生映像`/`等候映像`/`映像退出码`/`终止映像`/
  `关闭映像` 五内建的 x86-64 发射器。触达点只有 kernel32 六导出（CreateProcessW /
  WaitForSingleObject / GetExitCodeProcess / TerminateProcess / CloseHandle /
  MultiByteToWideChar），地址在引导期 `k32_base` 之上经 `api_GetProcAddress` 惰性解析
  并写回槽位（每 API 只解析一次），故产物 **PE64 无导入表**（DataDirectory[1] RVA=0
  Size=0）、运行路径零 Python 模块零 CRT。口径：槽表 32 槽 × 40 字节，满槽诚实返回 −1
  且**不覆盖旧槽**；「无定义读数」一律 null／−1 不用哨兵数冒充（pid 不在表中、pid≤0、
  实参是堆对象而非整数、`GetExitCodeProcess` 报 STILL_ACTIVE(259)、API 解析失败）；
  `等候映像` 的 ms<0 映射 INFINITE；`终止映像` 用退出码 1（与 CPython
  `Popen.terminate` 在 Windows 上的返回值同值）并等待至多 5000ms 收殓，使
  `映像退出码` 立即可读；命令行 UTF-8→UTF-16 转换故中文路径与宽字符 CreateProcessW
  同行为，上限 2048 UTF-8 字节超限诚实判失败；槽表只存内核句柄与整数读数不含 Matha
  堆对象，故无需登记 GC 根。**44b-2** 原生独占面收口：宿主（`src/interp.py` +31）与
  VM（`src/mbc/vm.py` +24）面对同一批名**显式拒绝**，两处在各自文件独立写同文案
  （非静默降级、不返回假值），口径是核心主线红线「单线程确定、且不驱动外部进程」；
  链面（boot）固定注册名集不扩，映像族在链上即「未定义变量」诚实失败并静态锁住
  「无 `.matha` 语料提及五名」。**44b-3** 构建面真化：`src/matha_main.py` 新增
  `原生构建`（别名 `native-build`/`exe`）走 `src.mbc.native` 唯一真实机器码路径，
  发射失败如实非零退出且不留产物；`build` 旧文案声称「构建独立可执行文件」而
  `matha_compile` 从未产出过可执行文件——改为产真实 `.mbc` 字节码工件（MBC1，须 Matha
  载体执行）并把机器码指向 `原生构建`。同批宿主桥 `src/os_runtime.py`（+57−13）补
  `_终止载体`：纯 Matha 内核的 `收旧进程`/`停止进程` 只改簿记（内核面没有进程映像
  原语，也不该持有 OS 句柄），桥在内核判定**落地之后**才动 OS——被拒绝的 `停止`/`卸载`
  不再杀掉仍在运行的载体（旧行为把「拒绝」做成真伤害：簿记说还在运行，OS 侧进程已没），
  回收同时交还句柄格，否则再启动的主进程步会复用旧 Popen 句柄读到上一次运行的退出码。
  **44f** 进程树取证：CIM 查得派生子的 `ParentProcessId` 即原生映像自身 pid、父映像名
  是产物 `.exe` 而非 `python.exe`。新锁档 `tests/test_native_process_phase44.py` 37 项
  （44a 原生 e2e 10 / 44b CLI 6 / 44c 三面拒绝 9 / 44d 桥面回收 6 / 44e 静态结构 5 /
  44f 进程树取证 1，全用 `tmp_path` 唯一 exe 名避免阶段 41 的固定名占用伪影）。
  本体量 33,481→**34,099**（+618 = 新档 578 + `src/mbc/native.py` 挂载 +16 +
  `src/mbc/vm.py` 拒绝内建 +24；`src/interp.py`/`src/os_runtime.py`/`src/matha_main.py`
  /`src/domains/os_module.py`（类注口径 +5−1，零语义）不属内核五件不在口径）；指令码 36 不变（映像族是内建名不是新 opcode）、ast_vm_gap
  快照零扰动、Track B 快照零扰动（无 `.matha` 改动）、dep_audit 内核清单补入新档后
  内核文件 39→**40** 个 / import 边 189→**190**（`native.py → native_process.py` 一条）
  **0 违规**，并顺手重生成守门报告 `docs/DEP_BASELINE.md`（旧报告停在阶段早期的
  25 文件 / 68 边，与被它声称的现状无关）。门禁与算术闭合见
  KNOWN_ISSUES 阶段 44 收官条目。
- 阶段 45 原生映像承载 Matha 工具链首片（方向拍板：首批切片「A 原生映像承载 Matha 工具链
  首片」，范围边界全选「只做最小可编译片段（不扩 OS 载体）+ 补多模块链接（一次编入多个
  `.matha`）+ 一并处理原生栈上限 + 附带收口文档漂移与勘误」，验证深度「全量门禁 + 真原生
  exe e2e」）。**45a** `src/mbc/native.py` 的 `MAX_NATIVE_ARITY` 8→**15**——15 取调用点/
  序言 disp8 位移可达上界（`-8*(argc+1) ≥ -128`），`apply_rt` 按 rdx 动态 `rep movsq` 本身
  无 arity 假设；boot 链唯一越界真形 `扫描三引号续`(9)（全链另含 `_推导绑定`(9)）此前使
  **整个词法器**在原生面编译失败，即「原生面承载工具链」的编译期唯一硬阻塞；16 参的定义位
  与调用位取同一常量并显式拒绝（不静默错编），两处拒绝文案与常量同源入锁。**45b** 多模块
  链接：`src/mbc/compiler.py compile_sources` 逐源解析后并入**单个** `Program`（源序即顶层
  执行序；`use` 在编译面被忽略——符号本就落全局，故跨文件调用即同文件调用），
  `native.compile_sources_to_exe` 与门面 `exec_api.compile_modules` / `build_exe(list[str])`
  （+19）、CLI `原生构建` 多源位（`src/matha_main.py` +19−11）同批接线；产物一份映像、
  默认输出取首源、次源不可读不留半成品，单源路径逐字节零扰动。**45c** 原生栈模型：操作数栈
  迁 `.bss` 1MB（不花文件字节）+ `_stack_effect` 全操作码静态净增量表（无遗漏位入锁）+
  `_operand_peak` 峰值/汇合/夹住/不收敛四判据 + `_stack_budget` 链接期预算 + `_start` 真填
  `stack_floor` 与调用栈守卫标签 + PE StackReserve 与常量同源。旧形越界是**静默改写内存后
  退出码 0**，现给可捕获的诚实异常；2 万层薄帧递归真跑给正确读数，胖帧由调用栈守卫接住，
  `调用捕获` 接住后进程继续正常执行；全 `.matha` 语料与 boot 链在链接期零拒绝。**45d**
  承载实证：`matha/lexer.matha` + `matha/stdlib.matha` + `matha/parser.matha` 三片编进一份
  真 PE64——14 条输入的 token 流（类型|文本|行|列）与 9 条输入的 AST 流和宿主 hi/vm 两面
  **逐字同判**（含只经帧内解构产得的记号作可达性正向锁），5 条不可解析输入在 `调用捕获` 下
  三面同给同一句消息体、未捕获时 exe 非零退出且 stderr 同消息体；产物与阶段 44 同规格
  （无导入表、三节、PE32+，字节里无 python/Cpython/site-packages 标记）。同批真修三个原生
  发射缺陷：① `<`/`<=`/`>`/`>=` 在任一侧为指针时按 `.data` **地址序**判（`输出("b" > "a")`
  直接反号）→ `val_cmp` 深序比较助手（字符串/列表/元组/布尔四面同判，混合类型/字典/null
  各自诚实拒绝；`-1` 必走 REX.W 形 `48 C7 C0 FF FF FF FF` 的位形锁防 32 位零扩展把 -1 变成
  4294967295）；② 帧内解构把局部槽写回错基址（手拼 `mov rbp,r8` 漏 REX.W）→ 统一走 `mov_rr`
  并加编码表锁；③ 尾位置一元负返回 `is_bigint` 的 0/1 判定值而非结果 → 回读 rax。
  **45e** 文档口径收口（**代码零改动**）：勘误 `matha/interp_matha.matha` 宿主委托臂行号
  773-774→**777-778**（46a-1/入口绑名批后再顺移至 **783-784**）、`src/plugins/ffi_sdk.py`（阶段 22b 已删）行号引用标注为历史落点；
  统一链面固定注册面现值 **60 名**（47/59 为阶段 41/42 时点值）并登记 `module 解释器` 两套源
  （106/139 名、交集 53、固定面 60-vs-44 不等集；阶段 46b 时点 boot 侧 139→141，入口绑名批 +2）三套解析序与判定面/产品面的 struct 工厂
  不对称（`MathaChain().load("解释器")` 在产品链必失败）——两条登记不修见 KNOWN_ISSUES
  阶段 45 口径收口条。新锁档 `tests/test_native_selfhost_phase45.py` 112 项（45e 的四个计数
  ——boot 固定面 60 / 镜像固定面 44 / 宿主实例内建表 3025 / 原生面 `NATIVE_BUILTINS` 132（46a-3 后现值 134）——
  一律锁成「文档所写 == 当场实测」而非写死数字，另登记 `src/mbc/native.py`「当前无此类
  可达名字」断言已过时：`长度` 直调与 `use` 降级出的 `加载模块` 均为可达 latent 名），另把
  `tests/test_native.py` 的 arity 越界锁改为随常量伸缩并锁文案同源；诚实边界入锁：boot 全链
  25 个 latent 宿主注入名名集与重复读取次数表（**25 是阶段 45 时点值**，阶段 46 摸底归因后
  24、46a-3 异常名族落原生载体后现行 **22**，见 46b 段）、词法器单片 latent 归零、latent 名在原生
  运行期如实点名失败。本体量 34,099→**34,538**（+439 = `src/mbc/native.py` +398 +
  `src/mbc/compiler.py` +22 + `src/kernel/exec_api.py` +19；`src/matha_main.py` 与
  `src/interp.py` 不在 `core_py_lines` 口径）；指令码 36 不变（零新 opcode）、Track B 快照零扰动
  （无 `.matha` 改动）。门禁与算术闭合见 KNOWN_ISSUES 阶段 45 收官条目。
- 阶段 46-1 boot 链 latent 名逐项归因 + `stdlib.to_upper` 死函数真修（路线形态拍板：
  「有界清算循环——每轮一条可判定判据 + 一个可回滚提交」，本切片只做 45-① 登记项的归因与其中
  唯一的语料缺陷）。**归因判据**取名字的宿主载体归属三分：A 类 `build_boot_vm().globals`
  已有宿主 Python 载体（**20** 名 = terminal_builtin 的 fs/stdio 族 12（`输入行`/`管道输入`/
  `管道结束`/`列目录`/`建目录`/`删除路径`/`复制文件`/`改名`/`当前目录`/`换目录`/`路径存在`/
  `执行Matha`）+ `matha_chain` 注入 3（`装载根`/`装载根们`/`装载包根们`）+ 导出表异常类
  `MathaRuntimeError` 1 + 内核计算 3（`_to_tuple`/`未定义错误`/`解析_JSON`）+ 宿主内部能力
  `调试Matha` 1——后者在 VM 后端本就被**设计性拒绝**（`src/mbc/vm.py` 的显式拒绝分支，非静默降级），
  属「必须宿主或诚实拒绝」类而非可移植载体）、
  B 类 `PluginResolver.known_symbols()` 惰性物化（**4** 名，os 域 `执行命令`/`执行命令输入`/
  `升级包`/`检查包更新`）、C 类谁都没有（**1** 名 `acc`）。A/B 是 46a 的原生载体工作量；
  C 不是脱宿主缺口而是**语料真缺陷**——`matha/stdlib.matha` 的 `to_upper` 在
  `let rec _map(i, acc)` 的 `in` 体里把形参名当自由名读（`in _map(0, acc)` 而非种子 `""`），
  故该行必然未绑定，`to_upper` 是一臂任何调用都失败的死函数（修前 hi/vm/链面三面同判
  `未定义变量 'acc'`，此前被整体登记成「宿主注入缺口」掩盖了它）。改形与 `to_lower` 种子对称
  （`in _map(0, "")`，`matha/stdlib.matha` 一行）：修后链面经产品分派体 `应用内建实` 给
  'AB' / 'HELLO, WORLD! 123' / '' / 'ABC_é中'（非 ASCII 原样保留），同一语料编进**真原生
  PE64** 逐字同判，把旧行回注的反控给 rc≠0 + stderr「未定义变量」——证明收益来自这一行而非
  装载环境。latent 名集 25→**24**（总读位 33→32，C 类归零）。同批把**归因动作本身**固化成
  机器判定，防未来复现同类误登：46e 要求每个 latent 名都能在宿主 globals 或插件符号表里找到
  载体（找不到即红）；46h 锁「24 只是下界」——boot 链 831 个 LOAD_GLOBAL 名与编译期拒绝集合
  `native._UNRESOLVED_GLOBALS` 的交集只剩已按静态对象发射的 `None`/`_empty_dict`，即 latent 名
  不在拒绝集合内（链接期不报、运行期才炸）；另锁单文件片 stdlib 自身 latent 归零（46g）、
  `to_upper` 系链面独有注册名且 `src/**.py` 全仓零载体（46i，登记不修，41-① 表差族新成员）、
  四份文档的 latent 读数由 `_latent_reads` 实测值拼出锚点（46j——本轮 25 被写成现行值正是
  没有这类锁的结果，此后文档与机器脱钩即门禁红）。
  新锁档 `tests/test_native_selfhost_phase46.py` **22** 项（46a 静态形状 ×2 / 46b 三面真读数
  ×9 / 46c 真原生映像正控 / 46d 回注反控 / 46e 分类判据 / 46f 名集锁 / 46g 单片归零 /
  46h 下界口径 / 46i 表差登记 / 46j 文档口径 ×4），`tests/test_native_selfhost_phase45.py`
  同步改读数（`_BOOT_LATENT` 去 `acc` 并加「25 是阶段 45 时点」注 + 三处文案 25→24——该档
  本就把计数写成集合等值而非硬编码数字，故无数字断言需改）；本体量 **34,538 不变**（`src/` 零改动）、指令码 36
  不变、Track B 快照**逐字节零扰动**（改动落在 boot 文件 `matha/stdlib.matha` 上仍零扰动——
  226 语料无一调用 `to_upper`，与「both_err_equal 10 条与此无关」互为印证）、
  `docs/ast_vm_gap.json` 仅 `generated_at` 一行刷新（节点 78／VM 发射 59／无码 19／阻塞缺口 0／
  指令码 36 结构不变）。登记不修两条：①46i 的表差族（上）；②`dist/matha.exe` 内嵌语料副本按
  `matha.spec` 整树入包口径必滞后本行（构建于 11-25 13:27，早于本次改动），但其 `run` 面落 46i 的
  hi 缺口、`终端` 面走 CMD 命令表，两条入口都触不到链面分派臂 ⇒ 滞后**只有构建期证据、无运行期
  读数**，且门禁期间刻意不重建 `dist/`（它是 `tests/test_frozen_entry_phase43.py` 的活依赖，
  44-⑧/43-② 承继族）。门禁与算术闭合（**8544 条件 = 8543 过 + 1 skip = 8522（阶段 45）+ 22**）
  见 KNOWN_ISSUES 阶段 46 收官条目。
- 阶段 46c 判定面换形（「脱 Python 退役」的**前置**门禁，不是后置）：摸底结论——当前三面
  正确性判据的裁判**全是 Python**（Track B boot↔host、golden vm↔interp、native_parity
  host↔exe 都在同一个解释器里比），退役那一刻判据整面消失、只剩「没崩」，而阶段 41 清过的
  假成功温床正是这种状态。换成交付三形态，锁档 `tests/test_judgment_face_phase46c.py`
  **19** 项（Python 仅作构建种子，不作判定）：
  **① 自举双跑**在**编译面**已经成立——`matha/lexer.matha` + `stdlib.matha` + `parser.matha`
  + `compiler_matha.matha` 四片链进原生 PE64 后 `编译器.编译` 在映像里跑起来了；两个**独立
  构建**的映像（四片链接 vs 四片文本拼接，产物逐字节相同）各在自己的进程里编译同一批源，
  64 行字节码读数（常量池／主码／函数表／模块名）逐字相同，同一映像内重复编译同判；
  构建面另有三组源各两次独立发射逐字节相同、同一映像三跑 stdout 逐字相同（46c21–23）。
  **② 手算／规范对拍**：词法器 37 行 token 流、语法器 7 行 AST 流、编译面 64 行字节码逐行
  写死在锁档且依据指到 Matha 源行（46c24/25/27/36–38）；反控两批（词法面 46c26 的整表顺序
  置换／`关键字|Int`→`标识符|Int`／`大于等于`→`大于`，编译面 46c38 的操作码编号／折叠结果
  退回左操作数／常量池顺序置换）证明字面量承重。
  **③ 差分参照降为 dev-only**：`scripts/selfhost_matrix.AUTHORITY = "dev-only-differential"`
  ＋产品面 `src/**` 零 import 判定工具（46c29/30）。同批把差分面自身的**功率**换形：旧快照
  `equal=true` 里「两侧零输出」与「N 行逐字相同」同形（旧形只在有输出时记 `n_outs`，空输出
  表现为缺键＝与「没测」不可分），现无条件记录并分层进 `summary.power`——现值 **226 语料 /
  双面一致 216 = 有读数 71 + 空对空 145**，全量比对读数 270 行；此前被反复当作收益证据的
  52 条 `matha/resource/**` 语料**全为 silent**（资源库真证据在阶段 41 手算锁，46c32 把这条
  变成机器判定）。快照改动纯增量、七分类零漂移，两处键形锁随之改（`test_selfhost_matrix_phase29`
  ／`test_selfhost_language_phase39`）。诚实边界入锁（**46c 时点**）：boot **解释器面**（`interp_matha`／
  `loader`）链进映像当时实测在第一条驱动语句前以 `不可调用的值` 退出（rc=0x1），故「映像自己编译
  ＋自己运行」的全链双跑当时仍待 46a/46b——该边界已由下面的 46b/46b-3 推翻。本体量 **34,538 不变**（`src/` 零改动，改动只在
  `scripts/selfhost_matrix.py` 与测试）、指令码 36 不变、Track B 分类零扰动。附带收口本片自己
  造成的行号漂移（首跑 tests lane 唯一红，45e 行锚锁按设计报警）：镜像表行 484→**499**、
  `_augment_chain_ns` 509→**524**，锁参数表与两处文档行引用同步改指并留「45 时点」注。
  门禁与算术闭合见 KNOWN_ISSUES 阶段 46c 收官条目。
- 阶段 46a-3 + 46b + 46b-3 全链阻塞项跑通（承继用户指令「先把 #247 与 #248 全链阻塞项跑通」；
  46c 登记的那条边界从「解释器面进不了映像」推进到「一个映像内读完盘、自己编译、自己运行」）。
  **46a-3 原生未定义名带名抛错**：无参条目 `("err_undefined", "未定义变量")` 退役，LOAD_GLOBAL
  未定义位改走 `err_undef_pre` + `sob:{名}` + `str_concat` + `dk_q` 拼出 `未定义变量 'X'`，
  与 hi/vm/链面四面**逐字同判**（异常**类名**载体仍缺，承继 41-③ 同族登记）；同批把异常名族
  `未定义错误`/`MathaRuntimeError` 接入原生内建表（三名共用参数化后的 `_emit_builtin_error`
  消息体发射器）。latent 名集 25→**22**（总读位 33→28：46-1 去语料自由名 `acc` 得 24/32，
  本批去异常名族两名；现行分类 A 类宿主 `vm.globals` **18** + B 类插件惰性物化 **4** + C 类 **0**，
  名集/读位/分类三判据分别为 `test_46f`/`test_46e`/`test_46h`，文档读数由 `test_46j` 与
  `_latent_reads` 同源拼锚）。**46b 语料判定面从两端升三端**（新锁档
  `tests/test_corpus_face_phase46b.py` **13 项**）：boot 六片（`lexer`/`stdlib`/`parser`/
  `runtime/matha_runtime`/`interp_matha`/`loader`）链进**一个**无导入表 PE64，映像用 Matha
  自己写的解释器从盘读语料、自己解析、自己执行，Python 只喂源与跑产物；判据全手算——10 份语料
  逐份读数（7 条有判别力 + 3 条如实标退化）、A/B 双构建 PE 逐字节相同 + 读数逐字相同、同像三跑、
  改一字即分叉的承重反控、入口绑名正负两面（缺模块仍如实 `未找到模块 'X'`，不因预绑变假成功）。
  换行面另取证一条并补真：hi/vm 经 `Path.read_text` 的 universal-newlines **永远吃不到** `\r`，
  故「三面同判」在 CRLF 上本是空话——`matha/lexer.matha`（+20−1，新增 `是回车码`/`扫回车`
  CRLF 折叠，对齐宿主 `src/lexer.py:462-471`）打通 CR 通道后，由映像内现拼 `chr(13)`/`chr(10)`
  两份源同像自证 LF≡CRLF（46b10），再把 CR 守卫置恒假重链反控（46b11：CRLF 与 LF 分叉且 LF
  不受波及）。`matha/interp_matha.matha`（+92−64）补 `绑模块名(env)`/`绑名对(env, 对们)` 与
  顶层入口真形；宿主对位镜像 `matha/interp.matha`（+11−2）**刻意不同动**并锁住源行依据——
  镜像绑模块名反而把 `标准库.len(...)` 从正确读数打成 `不可调用的值: None`（46b6/46b7）。
  **46b-3 全链同像**（新锁档 `tests/test_fullchain_face_phase46b.py` **15 项**）：五片配方
  `matha/{lexer,stdlib,parser,compiler_matha,vm}.matha` 进**同一份**映像，在映像内完成
  `标准库.read_file`（`matha/stdlib.matha:574`）→ `编译器.编译` → `字节码虚拟机.运行M3V` → 读数，
  11 行手算表逐字对拍（含把 `matha/lexer.matha` 自身当语料编一遍：1590 常量／344 主码／49 函数）、
  A/B 双构建逐字节 + 同像三跑 + 盘上内容承重 + 抽片反控两条（断 `未定义变量 '编译器'` /
  `未定义变量 '字节码虚拟机'`）。这条路的前置阻塞是原生面 `is` 无载体（旧形直接
  「不支持二元运算 'is'」），本片补 BINOP `is` 发射：值为 tagged raw 逐位相同，
  **不追随 Python 的字符串/小整数 interning**（`"ab" is "ab"` 假、`1.5 is 1.5` 假），并把 `is`
  语料走「映像内编译 + 映像内运行」双路径同判。改动面 `src/mbc/native.py` +40−8 → 本体量
  34,538→**34,570**（`src/matha_chain.py` 装配壳与三片 `.matha` 镜像不在口径）；指令码 36 不变
  （`is` 走既有 BINOP 发射位，零新 opcode）。三条登记不修（均有锁或有取证）：①`is` 优先级双面
  分歧——`是中缀is` 在 boot 挂在 `解析移位_续`（`matha/parser.matha:628`）而非关系层，宿主实际在
  `_parse_rel_expr`（`src/parser.py:1876-1884`），且 `matha/parser.matha:600-602` 的注释把宿主
  落点写成 `_parse_set_expr` 本身即口径缺陷（实测 `1 + 1 is 2` 与 `1 + (1 is 2)` 的链面 AST
  逐字相同、读数 `[None]`，原生直接路给 `True`）；②共像模块符号作用域未收口——MBC 把各模块
  `func` 提升进同一张全局函数表，`matha/interp_matha.matha:508` 与 `matha/vm.matha:119` 的
  同名 `应用运算` 后者覆盖前者，故 boot 六片 + `vm.matha` 七片共像落 `未知运算符: =`（「一像装全
  工具链」的下一道收口项）；③原生 `_read_file` 读不到路径静默给 null，映像内读不存在的文件仍
  `__正常__|None`，属**假成功现状锁** + 反转条件，诚实化另立一批。`tests/test_judgment_face_phase46c.py`
  的边界段随之换形（19 项锁数不变）。门禁与算术闭合见 KNOWN_ISSUES 阶段 46b 收官条目。
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
