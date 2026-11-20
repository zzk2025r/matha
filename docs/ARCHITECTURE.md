# Matha 架构现状（v4.6.0）

> 本文件描述**代码现在长什么样**，不是路线图，也不是成绩单。
> 所有数字来自 `python scripts/repo_facts.py`；所有门禁由 `make check`
> （= `python scripts/check.py`）判定，对外只产出**一个**通过率。
> 历史文档（118 份一次性报告）在 [`history/`](history/)，不作为现状依据。

## 一、唯一核心主线

```
src/lexer.py → src/parser.py → src/ast_nodes.py
      → src/mbc/compiler.py → src/mbc/vm.py        ← 默认执行
                                  └→ src/mbc/native.py → plugins/toolchain_msvc → 真实 exe ← 唯一机器码路径
```

- `src/mbc/opcodes.py`：指令码定义（33 条，VM 全分派、native 全发射）。
- `src/mbc/cli.py`：`compile_source → run_module` 统一入口，`repl.py` /
  `matha_main.py` / `exec_api` 都走它，不再有第二条执行链。
- **已删除的转译执行路径**：`convert(source,"matha","python") + exec()`。
- **已归档的第三条 VM**：`src/vm.py`（MIR 栈式 VM）经阶段 11 移入
  `src/plugins/legacy_mir_vm.py`，阶段 22b 孤儿清算确认全仓零引用后删除；
  `src/m3v_vm.py`（重复实现，内含坏导入
  `import compiler_matha`）已删除。
- `src/mir.py` / `src/mir_opt.py` 只作优化分析 IR，**不承担执行**。
- `src/interp.py`（4k+ 行）降级为诊断后端：执行轨迹 / 单步调试，
  经 `src/kernel/exec_api.py::run(source, mode=...)` 显式选择（`--backend=legacy-interp`
  仅测试与调试可见）。全仓库 `src.interp` 的引用已改指门面。

核心体量：`src/lexer.py + src/parser.py + src/ast_nodes.py + src/kernel/ + src/mbc/`
共 **32,859 行**（`repo_facts.core_py_lines`，阶段 11 孤儿清算 −2,653 行；阶段 12b 终端 OS 胶水内建 +141 行；阶段 13 终端补全 os 域 升级包/执行命令输入 胶水 +29 行；阶段 14 解析器踩界真化 +113 行——词法器续行判定 + 主解析器 then 行首/参数跨行 skip；阶段 15 双端语义对齐 +8 行——VM 顶层裸表达式发射 + host 顶层 IfExpr 真执行；阶段 16 双端语义第二片 +10 行——let-in 列表体丢死兼容 + 顶层裸表达式求值丢弃 + 严格值相等三端登记 + 词法器剥 BOM；阶段 17 全面清算 +9 行——解析器 _CMP_ALIASES 归一化常量与三处 op 取值位点；阶段 18 双端语义第三片 +56 行——解释器删模块递归双执行 + use 加载自测块跳过标志 + 通道收发 host 求值 + 解析器全中缀回退与 `_bracket_followed_by_infix`；阶段 19 双端语义第四片 +16 行——VM 编译器 match/switch 表达式位 + MechUnit 裸 list body 逐元素编译 + 成长引擎规则聚合；阶段 20 match 收口 + finally 全链 +176 行——编译器 match 动态兜底/守卫先求值/try 三路径重抛、VM RAISE_MATCH 0x63 处理器、原生 RAISE_MATCH 与 repr 渲染运行时、解释器 match 无匹配口径对齐、opcode 登记；阶段 21 插件符号 VM 面 + use 编译解析 + catch 哨兵 +119 行——VM Frame functions 表与 MAKE_CLOSURE 逐帧函数表解析、GET_ATTR 内建名回退、解析器 switch 表达式位、capability/json_builtin 插件移植胶水与 exec_api use 加载器注入面（惰性跳板经解析器动态装入，eval/auto 零领域急切加载语义保真）；阶段 22 全面清算 +2 行——22a time_builtin 吞错日志清算诚实化（err 面全量记录不再静默吞）；22c 语句位裸赋值真化在解释器面（src/interp.py _exec_stmt），不计入本体量；阶段 23 臃肿优化 + 扩展面 +152 行——23a 惰性内核节（src/kernel/lazy_kernel.py LazyKernelFn + time/terminal make_* 工厂化、interp/vm 双面 lazy_section 注册、interp 删顶层 json/terminal_builtin import）；23b features 单源 DEFAULTS/known_states/state_tuple + matha_main features 查询面对齐；23c 解析缓存（parser parse PARSE_CACHE opt-in LRU 32 + custom_ops 版本计数 + features.state_tuple 键）；23d 统一扩展面（src/extensions.py 四面协议 + matha ext CLI + PluginResolver.reload 公开回位 + interp _load_matha_source 包回退 + matha_term autorun 扩展条目 + matha_main _build_parser 命令表化）；阶段 24a 资源库代码化 +3 行——VM 编译器模块同名冲突（module X { func X }）命名空间绑定不发射（平面函数可调用面优先，与宿主 env 同规则；资源_成长 资源形态）。资源库 use 解析面（interp _library_module_source + 解析序 matha/ → 安装包 → 资源库 + 资源索引 _CN2FILE 映射）在 src/interp.py，不计入本体量。阶段 24d 动态解析 +68 行——host `_DYNAMIC_VALUE_DECLS`/`_is_dynamic_value_decl` 尾值声明分离 + `_b_dynamic_eval`（parse→decls 依 run() 同序注册执行、尾值 `_eval`，绑定持久落共享 env）+ VM `_make_dynamic_eval`（尾值包装哨兵零参 FuncDef 编译进嵌套 VM、`nested.globals = vm.globals` 对象共享、跨模块 `fn.consts`/`fn.functions` 钉池、尾值经 `globals.pop` 哨兵 `invoke_value` 取回零污染）。阶段 24e 建模仿真 +4 行——exec_api._wire_plugin_runtime 增 make_simulation_runtime 注入面（仿真_欧拉/仿真_龙格库塔 导函数回调绑定运行本体 invoke_value，宿主解释器与 VM 同名协议；惰性跳板构造零 import）；仿真数值核心在 src/domains/simulation.py、宿主内建在 src/interp.py，均不计入本体量。阶段 24f 单片机面 +0 行——宿主内建 `_b_mcu` 统一分派与 6 符号柯里化注册均在 src/interp.py、领域实现在 src/domains/mcu.py（纯规格面：SVG 电路图纸 / Arduino C 真代码生成 / 控制载荷归一化 + 串口实时显式拒绝 / 工具链真检测真烧录（avrdude/st-flash/esptool/openocd 四族 argv，可注入测试面）/ GPIO-UART-I2C-SPI-PWM 五类驱动模板 / 文本真落盘），均不计入本体量。阶段 24g 热启动与运行 +5 行——exec_api._wire_plugin_runtime 增 make_hotreload_runtime 注入面（热启动 mtime 快照装载 / 热重载变更检测重合并绑定运行本体，惰性跳板同构；setdefault 不覆盖程序自定义）；解析 helpers（_matha_module_path/_package_module_path/_library_module_path/_hot_pair 三级路径解析）与宿主内建（_b_hot_start/_b_hot_reload）在 src/interp.py、VM 胶水在 src/domains/capability.py（消息常量同源），均不计入本体量。阶段 24h 资源库新能力模块 +0 行——建模仿真（simulation/建模仿真.matha：双法对比/步长扫描/轨迹抽样）与单片机（mcu/单片机.matha：闪灯程序/闪灯图纸/呼吸灯斜坡/控制载荷）两纯 Matha 组合层落 matha/library/ 并入资源索引（19→21 条），均不计入本体量。阶段 25 自生凭据与应用中心 +0 行——商店 HMAC 令牌域（src/domains/store.py 商店_签发令牌/校验令牌/吊销令牌）与 socket 服务端域胶水（src/domains/networking.py 网络_服务/接受/收/发/关闭）在领域层、应用中心引擎在 matha/store_engine.matha（纯 Matha：HTTP 解析/路由/索引）、CLI 驱动在 src/app_cli.py（matha app 八子命令 + Release 导入），均不计入本体量；解释器柯里化共享捕获表修复（src/interp.py 部分应用路径拷贝追加）+11 行不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 26a 运行时注册表泛化 +43 行——exec_api 后端注册表条目化（_BackendEntry dataclass）+ unregister_backend/set_backend_enabled/backend_info 三面 + make_vm 工厂（4 处 VM 构造收敛）+ _wire_plugin_runtime 增 make_compiler_framework_runtime 注入面；编译器框架域（src/domains/compiler_framework.py 五框架模块消费面）、设备管理器信息层（src/system_inventory.py）与 matha sys CLI（src/matha_main.py 命令族）均在领域层/CLI 层，不计入本体量。阶段 27f 解析器字典值语境 +16 行——_parse_dict_value 值位旗标（init/括号消解链字典值判位/字典字面量值位包装三处；{"k": [x]} 值位 [x] 为列表字面量而非输出命令，与三元分支/return 同口径；boot 链六文件 AST 逐字节探针零扰动，182 语料唯一差异面 matha/vm/matha_vm.matha:66 帧栈构造修正为真列表）。阶段 28d 自举层 VM 注册插口 +40 行——src/mbc/vm.py register_builtin/unregister_builtin（保留名/模块函数/非可调用诚实拒绝）；28 其余宿主面（src/extension_port.py 五动作端口层、src/custom_ops.py + src/compiler/pass_manager.py unregister 注销面、src/interp.py 解释器宿主注册注销 +39 行、src/os_runtime.py 工具链单元装载 +114 行）均不在 core_py_lines 口径（src/ 不属内核五件）。阶段 29b 自举链语言级缺陷真化 +209 行——29b-① 语句位下标赋值 STORE_SUBSCRIPT 0x64 双面真化（opcodes +1；vm 0x64 处理器 +20：容器[index]=val 原位写入、字典缺键新建〔对齐 host dict.get 29b-④〕、不可哈希键领域文案、越界 IndexError 透传、不可下标对象归一到 src/interp.py 逐字一致文案；compiler +30：顶层 _compile_stmt 与块位 _emit_block 下标赋值发射〔栈序 容器/下标/右值；块尾 leave_last 位保持比较语义，与宿主边界一致〕；native +131：setitem_rt 原生运行时——列表正/负回绕原位写、越界/字典缺键新增〔dict_put 函数式不可原位扩容，诚实拒绝〕/不可下标 五路领域错误，消息经 match_render 拼接）；29b-②③⑥ 解析器 lambda 面真化 +27 行——lambda 立即调用（((x)=>x*2)(21) 分组后缀应用）、参数类型标注（(y: Int) => … 走通用 _parse_lambda_param）、单 `=` 右值后悬空关系运算符回退改按赋值解析（右值 _parse_expr 整体纳入三元；右值后 `?` 语料惯用式保持比较语义，自举 解析比较_续 同规回退）。宿主面 src/interp.py 下标赋值/文案归一与镜像 matha/{parser,compiler_matha,vm}.matha 不计入本体量。阶段 29e 编译后钩子槽 +32 行——exec_api set_compile_hook/get_compile_hook/_apply_compile_hook 纯钩子槽与 compile_module/build_exe 统一接线（29c 宿主面在 src/interp.py 与 matha/ 镜像、29d scripts/selfhost_matrix.py 与快照、src/compiler/mbc_adapter.py 字节码遍适配层——均不在 core_py_lines 口径，src/compiler 属 LEGACY_PREFIXES）；阶段 30 执行面收口 +0 行——boot 链五片真化（30a 分派路由/30b use 跨模块/30c 文案对齐/30d 语法缺口）全在 matha/ 镜像与 scripts/selfhost_matrix.py，宿主 type_of null 分支（src/interp.py +2 行）不在 core_py_lines 口径）。

## 二、L1 纯净内核与 import 白名单

内核 = `src/lexer.py`、`src/parser.py`、`src/ast_nodes.py`、`src/kernel/`、`src/mbc/`。

**允许**（标准库）：`math struct json re os sys io enum dataclasses typing logging
functools unicodedata textwrap heapq datetime importlib`。

**禁止**：`sympy numpy scipy numba tree_sitter ctypes cffi subprocess`、
`threading concurrent socket multiprocessing`，以及 `src.domains.*`、
`src.interp`、`src.stdlib.*`。

`mbc/native.py` 生成的 exe 调用 CRT（`_ecvt/rint/pow/fopen`）属 OS ABI 依赖，
不是 Python 依赖，明确不计为违规。

机器强制：
- [`tests/test_kernel_purity.py`](../tests/test_kernel_purity.py) —— AST 静态解析核心文件，白名单外 import 即 fail；
  并检查核心目录 `subprocess/threading/concurrent/socket/ctypes` 出现次数为 0（验收标准 1/2）。
- [`scripts/dep_audit.py`](../scripts/dep_audit.py) → 产出 [`DEP_BASELINE.md`](DEP_BASELINE.md)（依赖方向图 + 违规清单 + 插件越界）。

内核内建（`src/kernel/register_kernel_builtins()`）只有五组，全部纯标准库：
`src/kernel/math_builtin.py`（数学 + 单位换算，原 `src/mathlib.py`）、
`src/kernel/regex_builtin.py`（原 `src/regexlib.py`）、
`src/kernel/time_builtin.py`、`src/kernel/file_builtin.py`、`src/kernel/errors.py`。
> 修复点：原先 `src/mbc/vm.py` 的 `_default_builtins()` 里有一句
> `from src.domains.time_module import _register_time` —— 内核反向依赖领域层，
> 现由 `src/kernel/time_builtin.py` 承担。

## 三、符号能力：内核纯实现 + Matha 标准库

| 层 | 位置 | 角色 |
|---|---|---|
| stage0 引导实现 | `src/kernel/symbolic/`（expr/diff/integrate/simplify/limit/ode/series/domain/latex） | 纯标准库；CLI 不再默认走它，只作对拍基准 |
| Matha 标准库 | [`matha/library/*.matha`](../matha/library/)（calculus_diff → algebra_simplify → calculus_limit → calculus_series） | **CLI 默认路径**，由 mbc VM 编译执行 |
| 装载器 / 门面 | `src/stdlib/matha_symbolic.py` + `src/stdlib/calculus_symbolic.py` | Expr↔tagged 互转、`backend=auto|matha|stage0` 路由与回退记账 |

能力对照与缺口：[`symbolic_parity.md`](symbolic_parity.md)、
[`matha_stdlib_symbolic.md`](matha_stdlib_symbolic.md)。
`sympy` 已降为 `optional-dependencies.accelerated`，核心安装零第三方依赖。

## 四、插件层（联邦式）

- 契约：[`src/plugin_api.py`](../src/plugin_api.py) —— `MathaPlugin`（`name` /
  `exports()` / `arities` / `on_load(ctx)`）+ `PluginContext`（只暴露
  `register_builtin` / `register_formula` / `emit_diagnostic`，**禁止访问
  `vm.frames`/`vm.globals`/`_stack`**，由 `test_kernel_purity.py` 同思路静态守卫）。
- 适配层把历史 `_register_xxx(builtins: dict)` 签名统一包成 `exports()`，
  90 个 `src/domains/*.py` 中的 **88 个领域插件**零改写接入
  （`__init__.py` / `registry.py` 不是插件）。
- 清单：`src/domains/manifest.json`（`protocol_version = 1`，89 插件、0 不可用）。
  `src/semantic.py` 已改为读该静态清单，不再 import 6 个领域模块。
- **应用中心/商店**（阶段 25）：`src/domains/store.py` 三符号
  （商店_签发令牌/校验令牌/吊销令牌，HMAC-SHA256 自签发，首发 secret 落
  `.matha/store/secret.key`）；引擎 `matha/store_engine.matha` 为纯 Matha
  （HTTP 请求解析/路由/索引落盘），Python 侧 `src/app_cli.py` 只出 socket
  驱动与 `matha app` 八子命令（serve/token/publish/upgrade/list/search/
  install/import-release）；CI 发行物经 `matha app import-release` 从
  GitHub Release 附件导入，形成零外部凭据闭环。socket 服务端域胶水
  （`src/domains/networking.py` 网络_服务/接受/收/发/关闭，真监听器句柄）
  替换旧无句柄假面（网络连接/绑定/监听/Socket发送/Socket接收，22a 同类清算）。
- **共生体 OS 面（阶段 27）**：纯 Matha OS 内核 `matha/os/kernel.matha`
  （单元生命周期状态机/进程表与协作调度/服务注册表 + 兼容协商，探针踩中即修
  四缺陷：空转轮步数翻倍、卸载落地记录表破坏、步进返回口径、服务占用协商）；
  TUI 桌面 `matha/os/desktop.matha`（`use 内核`，演示单元 时钟/回声/便签，
  j/k/s/t/u/p/d/q 按键集，动作经内核协商面拒绝如实回传）+ 终端 `桌面` 命令
  （term_engine ⑤b，一次性确定性键序脚本）；单元管理器桥 `src/os_runtime.py`
  （app/包/域插件/终端命令/服务五形态翻译为内核描述符 + 外部单元
  subprocess 面与升级回滚）；资源库三分支 `matha/library/{os,desktop,compat}`
  六模块并入资源索引（21→27 条）。stage-4 脱宿主闭环：stdlib+vm.matha
  joined 闭包经 boot 链 VM² 编译与宿主编译逐字节一致（tier A/B/C 三层锁）。
- **全工具链自举重建 + 五动作端口协议（阶段 28）**：自举解析器
  （lexer/stdlib/parser.matha 编译跑在 VM）与宿主解析器全语料 AST 逐字段
  一致、自举编译器与宿主编译器全语料 `_canon` 字节码逐位一致
  （`test_parser_parity_phase28` / `test_compiler_parity_phase28` 参数化
  全语料锁；VM 执行面维持阶段 27 stage-4 闭环锁，VM² ~10.5 min/文件不扩面）；
  自举层开放注册插口——`matha/interp.matha` 解释器插口注册表（注册/注销/
  名表，保留名诚实拒绝）+ `src/mbc/vm.py` register_builtin/unregister_builtin
  （28d，双面对拍 `test_open_ports_phase28`）；统一五动作端口协议（注册/
  启停/升级/回滚/依赖协商）覆盖六层（词法语法/解释器宿主/解释器自举/
  编译器/虚拟机/内核特性）——纯 Matha 协议模块 `matha/library/os/端口协议.matha`
  （资源索引 →28 条）与宿主适配层 `src/extension_port.py` 状态形状/审计行
  同构（`test_port_protocol_phase28` 三面对拍 + 六后端效应 + 诚实拒绝矩阵）；
  `os_runtime.register_toolchain_units()` 把六层装载为内核服务单元
  （`工具链-<层名>`，装载=注册、启动/停止=启停、主步=只读健康探针）；
  跨 VM 调用他模块函数须按 24d 钉池纪律（`fn.consts`/`fn.functions`）——
  MBC `_invoke` 常量池回退是逐 VM 的（InterpBootBackend 文档在案）。
- **执行面双轨判据 + 自举链缺陷真化 + 框架接入 MBC 主线（阶段 29）**：
  执行面判据双轨制——A 轨 pytest 轻中档锁（自举语言/执行/矩阵/公式四档入
  常规门禁）、B 轨 `scripts/selfhost_matrix.py` 全语料 sweep（多进程 +
  boot 复用）+ 快照 `docs/selfhost_matrix.json` `--check` 重档通道
  （225 语料：双面一致 147 / 宿主独过 61 / 双败 17 / 超时 0 / 双面分歧 0）；
  自举链语言级缺陷真化（语句位下标赋值 STORE_SUBSCRIPT 0x64 双面、lambda
  立即调用与链式、参数类型标注、单 = 右值悬空关系回退、零参闭包 `f()`
  自举面 IndexError、缺失字典键 vm→host 对齐缺键返 null、错误文案归一）；
  0x62 公式模式自举贯穿（宿主编译器专有 → parser/interp/compiler/vm.matha
  四面）；编译器框架接入 MBC 主线——`src/compiler/mbc_adapter.py` 两条
  MBC 字节码遍（常量折叠调 VM 同一 `_BINOPS`/`_UNARYOPS` 求值，除零等
  报错诚实保留运行期路径，仅折叠不可变结果，跳入模式中段保守跳过；死代码
  消除可达性 BFS + 跳转重映射）经专用 PassManager 调度（不与框架泛 IR 遍
  混跑同一 program）；接入方向反转：内核 `exec_api` 不 import src.compiler
  （dep_audit 棘轮遗留面），纯编译后钩子槽 `set_compile_hook`/
  `get_compile_hook`，`compile_module`/`run_checked`/`build_exe` 统一接线，
  适配器 import 即反向注册 + features `MBC_PASSES` 双保险 opt-in 默认关
  （`test_mbc_passes_phase29` 30 项：接入面锁 / 遍实效锁 / on-off 双态
  对拍）。
- **执行面收口（阶段 30）**：自举链执行面五片真化——30a 执行分派路由
  （读取块/设值/跳出/继续/返回/结构体/枚举/属性：interp_matha.matha 求值/
  执行语句 分发表扩 + 求值 补 下标/属性/切片支）；30b use 跨模块装载
  （导入绑定 模块名表扩 + 非函数符号合并——Token 跨模块未找到 29-③ 退役）；
  30c 双面错误文案对齐（除零/取模/整除/不可调用/类型名大小写，boot 面与
  宿主 _exec_use 逐字一致）；30d 语法缺口真化（列表推导 `[e for t in it
  if c...]` boot 解析/求值/编译三面 + 类型索引 `list[类型]` + sqrt 一元
  前缀 + stdlib_symbols 构造支持）；30e B 轨驱动器级域符号注入（宿主
  `Interpreter().builtins` 全表面经 28d `register_builtin` 端口入 boot
  env，可调用值柯里化适配 n-arity，常量值仅绑 env；`_CHAIN_CRITICAL`
  保留名 `type_of` 双面不覆盖——宿主同名符号不得改写链分派判据内建，
  boot 语义 = VM `_builtin_type_of`；解析失败符号诚实跳过保持 boot_err）。
  快照 225：双面一致 203 / 诚实 differ 3 / boot_err 0（29d 61→清零）/
  both_err 17 / timeout 2。宿主 `type_of(null)` 补 Null 分支对齐 VM 面
  （src/interp.py，不在本体量口径）。
- **懒加载**：`exec_api.compile_module(..., plugins="auto|strict|off")`；
  未 `@：【加载领域】` 就引用领域符号 → 编译期诊断并列出候选插件名。
  验证：`tests/test_plugin_contract.py`（含子进程取证「只加载需要的那个」）。
- **第三方重后端只在调用那一刻 import**：`src/domains/symbolic_calculus.py`
  是这条纪律的样板 —— `integrate` 先问纯标准库内核引擎 `src/kernel/symbolic/`，
  只有内核返回 None（能力缺口，如 ∫e^(-x²)dx）才在函数体内 `import sympy`；
  顶层 import 一律禁止。验证：`tests/test_plugin_load.py` +
  `tests/test_plugin_load.matha`（`x = 符号原子("x")` 后 `integrate(x^2, x)` →
  `x**3/3`，这一条内核引擎就能答，全程不碰 sympy）。
- **插件命名卫生**（机器强制，见 `tests/test_plugin_contract.py` 第六节）：插件
  不得导出裸单字母符号，也不得与 `matha/*.matha`、`matha/library/**` 的顶层声明
  同名。原因：物化插件执行 `target.update(table)`（同名即覆盖），而清单符号名会经
  `LazyBuiltinTable.__contains__` 在全进程生效 —— 导出 `x` 会改掉「未定义名即报错」
  的内核契约，导出 `符号` 会抬掉 `stdlib_symbols.matha` 的自举符号表构造函数。
- 重型/逃逸能力全部外移：`src/plugins/`（12 个）——
  `numpy_accel` / `deps_probe` / `ffi` / `interop` / `device_config` /
  `tree_sitter_backends` / `tree_sitter_cext` / `parallel_parser` /
  `toolchain_llvm` / `toolchain_msvc` / `toolchain_signature`（`ffi_sdk` /
  `legacy_mir_vm` 于阶段 22b 孤儿清算确认全仓零引用后删除）。
  核心解析单线程确定（`threading`/`concurrent.futures` 已移出 `src/parser.py`）。
- **消除静默假成功**：外部工具链不可用 → 显式失败 + 诊断，不再 `mode:"simulated"`
  冒充成功（`src/compiler/llvm_hybrid.py`；原 `src/mbc/native_link.py` 已移出内核
  删除，职责由 `src/plugins/toolchain_msvc.py` 承接，它无论环境如何都落一个 exe
  的旧行为已改为真失败）。

## 五、门禁与唯一口径

| 门禁 | 判据 |
|---|---|
| `tests/` | 178 个测试文件（全量见最近一次 `make check`） |
| `kernel_purity` | 白名单 + 核心无逃逸模块 + 插件不得碰 VM 私有面 |
| `ast_vm_gap` | 78 个 AST 节点、59 发射 / 19 有意无码 / **0 不认识**（ListComp 已由 VM 编译为下标循环 + `append` 累加，不再静默返空）、**0 阻塞缺口**；指令码 34/34/34 |
| `golden` | 39 例 vm ↔ interp 逐字节；`--native` 追加真 exe 对拍（已知未实现项列在 `golden_tests/manifest.json` 的 `native_known_gaps`，当前为 0） |
| `dep_audit` | 违规 0 条、插件越界 0 条 |
| `matha_stdlib_symbolic` | 阶段 4 逐位对拍 + 偏差双向锁定 + 缺口显式失败（107 项） |

```bash
make check          # 含 vm↔native 机器码对拍
make check-lite     # 本机无 nasm/link 时用
```

## 六、兼容承诺（未被重构破坏）

- 符号体系不删：`？ #： 【*/ */ @： >> []`（语句位单元素 `[x]` 是**打印括号**，
  列表字面量请用两元素形式或 `包(x)`，详见 [`ast_vm_gap.md`](ast_vm_gap.md) 第九节）。
- `matha/**/*.matha`（182 个）、`examples/` 全部保留；
  `matha/library|knowledge|resource/` 属标准库/扩展包，不内置内核。
- 88 个领域插件全部保留为插件，未加载时不产生 import 成本。
