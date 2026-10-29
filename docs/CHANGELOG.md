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
