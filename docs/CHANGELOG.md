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

### 三、插件联邦：82 个领域插件懒加载

- **82 个领域插件**（`src/domains/`，清单 `manifest.json` 0 不可用）零改写接入
  `MathaPlugin` 契约（`src/plugin_api.py`），另有 **14 个内核外工具插件**
  （`src/plugins/`：toolchain_msvc/llvm、numpy_accel、ffi、tree_sitter 等）。
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
- **stage-2 不动点**：用自举编译器编译【整条引导链】得到 stage-2 编译器，
  再用它编译 `matha/vm.matha`，产物与 stage-1 及宿主编译 gold **逐位一致**
  ——编译器自编译后行为不变（`tests/test_mbc_vm_matha.py`，标 slow）。
- 双重自举闭环：自产 lexer+parser 编译后照常 tokenize/parse。
- 旧「自举 65.4%」一次性报告已移入 `docs/history/`，不作为现状依据；
  现状以 tests/ 全绿为准。

### 五、VM ↔ native 机器码平价与静默失败清零

- AST×VM 覆盖矩阵：78 节点中 59 发射 / 19 有意无码 / **0 不认识、0 阻塞缺口**；
  202 份语料 **0 解析失败**（`docs/ast_vm_gap.md`，机器生成）。
- 指令码 33 条 VM 全分派、native 全发射；黄金用例 **39** 例 vm ↔ interp
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
