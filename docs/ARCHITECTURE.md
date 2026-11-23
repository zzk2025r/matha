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

- `src/mbc/opcodes.py`：指令码定义（36 条，VM 全分派、native 全发射）。
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
共 **33,452 行**（`repo_facts.core_py_lines`，阶段 11 孤儿清算 −2,653 行；阶段 12b 终端 OS 胶水内建 +141 行；阶段 13 终端补全 os 域 升级包/执行命令输入 胶水 +29 行；阶段 14 解析器踩界真化 +113 行——词法器续行判定 + 主解析器 then 行首/参数跨行 skip；阶段 15 双端语义对齐 +8 行——VM 顶层裸表达式发射 + host 顶层 IfExpr 真执行；阶段 16 双端语义第二片 +10 行——let-in 列表体丢死兼容 + 顶层裸表达式求值丢弃 + 严格值相等三端登记 + 词法器剥 BOM；阶段 17 全面清算 +9 行——解析器 _CMP_ALIASES 归一化常量与三处 op 取值位点；阶段 18 双端语义第三片 +56 行——解释器删模块递归双执行 + use 加载自测块跳过标志 + 通道收发 host 求值 + 解析器全中缀回退与 `_bracket_followed_by_infix`；阶段 19 双端语义第四片 +16 行——VM 编译器 match/switch 表达式位 + MechUnit 裸 list body 逐元素编译 + 成长引擎规则聚合；阶段 20 match 收口 + finally 全链 +176 行——编译器 match 动态兜底/守卫先求值/try 三路径重抛、VM RAISE_MATCH 0x63 处理器、原生 RAISE_MATCH 与 repr 渲染运行时、解释器 match 无匹配口径对齐、opcode 登记；阶段 21 插件符号 VM 面 + use 编译解析 + catch 哨兵 +119 行——VM Frame functions 表与 MAKE_CLOSURE 逐帧函数表解析、GET_ATTR 内建名回退、解析器 switch 表达式位、capability/json_builtin 插件移植胶水与 exec_api use 加载器注入面（惰性跳板经解析器动态装入，eval/auto 零领域急切加载语义保真）；阶段 22 全面清算 +2 行——22a time_builtin 吞错日志清算诚实化（err 面全量记录不再静默吞）；22c 语句位裸赋值真化在解释器面（src/interp.py _exec_stmt），不计入本体量；阶段 23 臃肿优化 + 扩展面 +152 行——23a 惰性内核节（src/kernel/lazy_kernel.py LazyKernelFn + time/terminal make_* 工厂化、interp/vm 双面 lazy_section 注册、interp 删顶层 json/terminal_builtin import）；23b features 单源 DEFAULTS/known_states/state_tuple + matha_main features 查询面对齐；23c 解析缓存（parser parse PARSE_CACHE opt-in LRU 32 + custom_ops 版本计数 + features.state_tuple 键）；23d 统一扩展面（src/extensions.py 四面协议 + matha ext CLI + PluginResolver.reload 公开回位 + interp _load_matha_source 包回退 + matha_term autorun 扩展条目 + matha_main _build_parser 命令表化）；阶段 24a 资源库代码化 +3 行——VM 编译器模块同名冲突（module X { func X }）命名空间绑定不发射（平面函数可调用面优先，与宿主 env 同规则；资源_成长 资源形态）。资源库 use 解析面（interp _library_module_source + 解析序 matha/ → 安装包 → 资源库 + 资源索引 _CN2FILE 映射）在 src/interp.py，不计入本体量。阶段 24d 动态解析 +68 行——host `_DYNAMIC_VALUE_DECLS`/`_is_dynamic_value_decl` 尾值声明分离 + `_b_dynamic_eval`（parse→decls 依 run() 同序注册执行、尾值 `_eval`，绑定持久落共享 env）+ VM `_make_dynamic_eval`（尾值包装哨兵零参 FuncDef 编译进嵌套 VM、`nested.globals = vm.globals` 对象共享、跨模块 `fn.consts`/`fn.functions` 钉池、尾值经 `globals.pop` 哨兵 `invoke_value` 取回零污染）。阶段 24e 建模仿真 +4 行——exec_api._wire_plugin_runtime 增 make_simulation_runtime 注入面（仿真_欧拉/仿真_龙格库塔 导函数回调绑定运行本体 invoke_value，宿主解释器与 VM 同名协议；惰性跳板构造零 import）；仿真数值核心在 src/domains/simulation.py、宿主内建在 src/interp.py，均不计入本体量。阶段 24f 单片机面 +0 行——宿主内建 `_b_mcu` 统一分派与 6 符号柯里化注册均在 src/interp.py、领域实现在 src/domains/mcu.py（纯规格面：SVG 电路图纸 / Arduino C 真代码生成 / 控制载荷归一化 + 串口实时显式拒绝 / 工具链真检测真烧录（avrdude/st-flash/esptool/openocd 四族 argv，可注入测试面）/ GPIO-UART-I2C-SPI-PWM 五类驱动模板 / 文本真落盘），均不计入本体量。阶段 24g 热启动与运行 +5 行——exec_api._wire_plugin_runtime 增 make_hotreload_runtime 注入面（热启动 mtime 快照装载 / 热重载变更检测重合并绑定运行本体，惰性跳板同构；setdefault 不覆盖程序自定义）；解析 helpers（_matha_module_path/_package_module_path/_library_module_path/_hot_pair 三级路径解析）与宿主内建（_b_hot_start/_b_hot_reload）在 src/interp.py、VM 胶水在 src/domains/capability.py（消息常量同源），均不计入本体量。阶段 24h 资源库新能力模块 +0 行——建模仿真（simulation/建模仿真.matha：双法对比/步长扫描/轨迹抽样）与单片机（mcu/单片机.matha：闪灯程序/闪灯图纸/呼吸灯斜坡/控制载荷）两纯 Matha 组合层落 matha/library/ 并入资源索引（19→21 条），均不计入本体量。阶段 25 自生凭据与应用中心 +0 行——商店 HMAC 令牌域（src/domains/store.py 商店_签发令牌/校验令牌/吊销令牌）与 socket 服务端域胶水（src/domains/networking.py 网络_服务/接受/收/发/关闭）在领域层、应用中心引擎在 matha/store_engine.matha（纯 Matha：HTTP 解析/路由/索引）、CLI 驱动在 src/app_cli.py（matha app 八子命令 + Release 导入），均不计入本体量；解释器柯里化共享捕获表修复（src/interp.py 部分应用路径拷贝追加）+11 行不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 26a 运行时注册表泛化 +43 行——exec_api 后端注册表条目化（_BackendEntry dataclass）+ unregister_backend/set_backend_enabled/backend_info 三面 + make_vm 工厂（4 处 VM 构造收敛）+ _wire_plugin_runtime 增 make_compiler_framework_runtime 注入面；编译器框架域（src/domains/compiler_framework.py 五框架模块消费面）、设备管理器信息层（src/system_inventory.py）与 matha sys CLI（src/matha_main.py 命令族）均在领域层/CLI 层，不计入本体量。阶段 27f 解析器字典值语境 +16 行——_parse_dict_value 值位旗标（init/括号消解链字典值判位/字典字面量值位包装三处；{"k": [x]} 值位 [x] 为列表字面量而非输出命令，与三元分支/return 同口径；boot 链六文件 AST 逐字节探针零扰动，182 语料唯一差异面 matha/vm/matha_vm.matha:66 帧栈构造修正为真列表）。阶段 28d 自举层 VM 注册插口 +40 行——src/mbc/vm.py register_builtin/unregister_builtin（保留名/模块函数/非可调用诚实拒绝）；28 其余宿主面（src/extension_port.py 五动作端口层、src/custom_ops.py + src/compiler/pass_manager.py unregister 注销面、src/interp.py 解释器宿主注册注销 +39 行、src/os_runtime.py 工具链单元装载 +114 行）均不在 core_py_lines 口径（src/ 不属内核五件）。阶段 29b 自举链语言级缺陷真化 +209 行——29b-① 语句位下标赋值 STORE_SUBSCRIPT 0x64 双面真化（opcodes +1；vm 0x64 处理器 +20：容器[index]=val 原位写入、字典缺键新建〔对齐 host dict.get 29b-④〕、不可哈希键领域文案、越界 IndexError 透传、不可下标对象归一到 src/interp.py 逐字一致文案；compiler +30：顶层 _compile_stmt 与块位 _emit_block 下标赋值发射〔栈序 容器/下标/右值；块尾 leave_last 位保持比较语义，与宿主边界一致〕；native +131：setitem_rt 原生运行时——列表正/负回绕原位写、越界/字典缺键新增〔dict_put 函数式不可原位扩容，诚实拒绝〕/不可下标 五路领域错误，消息经 match_render 拼接）；29b-②③⑥ 解析器 lambda 面真化 +27 行——lambda 立即调用（((x)=>x*2)(21) 分组后缀应用）、参数类型标注（(y: Int) => … 走通用 _parse_lambda_param）、单 `=` 右值后悬空关系运算符回退改按赋值解析（右值 _parse_expr 整体纳入三元；右值后 `?` 语料惯用式保持比较语义，自举 解析比较_续 同规回退）。宿主面 src/interp.py 下标赋值/文案归一与镜像 matha/{parser,compiler_matha,vm}.matha 不计入本体量。阶段 29e 编译后钩子槽 +32 行——exec_api set_compile_hook/get_compile_hook/_apply_compile_hook 纯钩子槽与 compile_module/build_exe 统一接线（29c 宿主面在 src/interp.py 与 matha/ 镜像、29d scripts/selfhost_matrix.py 与快照、src/compiler/mbc_adapter.py 字节码遍适配层——均不在 core_py_lines 口径，src/compiler 属 LEGACY_PREFIXES）；阶段 30 执行面收口 +0 行——boot 链五片真化（30a 分派路由/30b use 跨模块/30c 文案对齐/30d 语法缺口）全在 matha/ 镜像与 scripts/selfhost_matrix.py，宿主 type_of null 分支（src/interp.py +2 行）不在 core_py_lines 口径。阶段 31 语言完备 + 判定面收敛 +92 行——31a func 定义 `->` 返回类型可选（src/parser.py _parse_func_def 箭头分支可选化 +15，29-⑧ 真化；boot 镜像 matha/parser.matha 解析函数定义同规不在口径）；31b 双 for 推导（src/parser.py _parse_comp_tail 多生成子句统一收口 + src/ast_nodes.py ListComp.gens 字段 +5；src/mbc/compiler.py _emit_list_comp_multi 嵌套下标循环发射 +72，零新 opcode；宿主解释器 gens 分支 src/interp.py +38/−32 不在 core_py_lines 口径；boot 镜像 做ListComp多/解析推导其余/_推导多子句 不在口径）；31f boot 切片求值、31c 语句位括号链、31d f[0] 守卫与字典迭代对齐、31e/31g sweep 装配与预算（scripts/selfhost_matrix.py）均不在 core_py_lines 口径）；阶段 32 语言收敛 + 元组真化 +273 行——32-② S1/S2 元组发射面切换（src/mbc/opcodes.py BUILD_TUPLE 0x65 +1〔指令码 35→36〕；src/mbc/compiler.py TupleExpr→BUILD_TUPLE 发射臂 +43；src/mbc/vm.py 0x65 处理器 + BUILD_SLICE 不可切片守卫 +26；src/mbc/native.py 元组对象与 ~29 消费面〔print/下标/切片/迭代/len/str/拼接/重复/真值/相等/iter_source〕+221）；宿主解释器面（src/interp.py `_迭代源`/ChainStmt 臂/let rec 预注册占位）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{compiler_matha,interp_matha,stdlib,vm}.matha 与三新锁档（test_tuple_instruction_s1/test_tuple_emission_s2/test_selfhost_language_phase32）均不在口径）。阶段 33 mb 面分歧收敛 +66 行——33c `in` 四面（src/mbc/native.py 容器守卫 +57〔六路类型 tag 分派 + err_in_prefix 池串 + raise_rt 可捕获〕；src/mbc/vm.py `_op_in` 容器守卫 +10−1）；33d hi 面 if 无 else（src/interp.py IfExpr/IfStmt else 缺失臂 +8）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{parser,stdlib,interp,interp_matha}.matha 与新锁档 test_selfhost_language_phase33 均不在口径。阶段 34 语言面继续收敛 +124 行——34b 语句位 if `[` 路由（src/parser.py `_in_cond_value` 值语境旗标 +17）；34c in 左侧四面（src/mbc/vm.py `_op_in` 守卫 +4；src/mbc/native.py in 守卫与 err_in_left_prefix 池串）；34d slice 元组（src/mbc/vm.py `_builtin_slice` +14−1〔含开放端缺界 None
  放行——下标切片 l[1:] 发射面 slice(c)(1)(None) 按 Python 切片语义
  容忍，VM 面下标切片经此内建而 BUILD_SLICE 直路原生容忍〕；src/mbc/native.py `fn:slice` 容器守卫 + err_slice_dom）；34c hi 臂与 34f FuncDef 臂（src/interp.py +8）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{parser,interp,interp_matha,compiler_matha}.matha 与新锁档 test_selfhost_language_phase34 均不在口径。阶段 35 自举解构贯穿 +16 行——35a S1 UNPACK_SEQ 长度守卫（src/mbc/vm.py 0x57 处理器严格化 +7〔长度精确匹配逐位绑定，否则「解构失败：期望 N 个元素，实际 <类型名>」，Closure 映射 "function"——34-④ 宽松补 null 退役〕；src/mbc/native.py `_emit_unpack_seq` 严格化重写 +9 净〔err 池串 err_unpack_pre/err_unpack_mid，try/catch 可捕获〕）；src/interp.py let 元组绑定守卫（语句位+表达式位）与 boot 镜像 matha/{vm,compiler_matha}.matha（35b S2 `_分配循环变量们`/`_存解构逆序` UNPACK_SEQ 发射——34-① 退役）、新锁档 test_selfhost_language_phase35 均不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 36 mb/boot 面收口批 +0 行——四片真化全在 matha/{parser,interp_matha,interp}.matha 自举镜像（均不在 core_py_lines 口径），src/ 零改动、指令码不变，新锁档 test_selfhost_language_phase36 不在口径。阶段 37 语言面清尾批 +3 行——37d 字典自然键（src/mbc/compiler.py `_literal_key` IntegerLit/FloatLit/BoolLit 原值入常量池 +6−3——36-① vm 字符串化退役；boot 编译器 `_发射键`/boot 解释器 `_字典键`/native dict_get val_eq 扫描随既有路径自然同判零改动）；37c 链式 let rec 预绑注册表（src/interp.py `_rec_chain`）、37b 块尾 `_块尾值` 尾值映射与 37a 协议一致锁在 src/interp.py 与 matha/{parser,interp_matha,interp}.matha 自举镜像、新锁档 test_selfhost_language_phase37，均不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 38 m3v 异常帧机制 +0 行——38a 载体异常→带内转换（捕获闭包/捕获内建双点 调用捕获 载体守卫包裹）全在 matha/vm.matha 自举镜像（不在 core_py_lines 口径），src/ 零改动、指令码不变，新锁档 test_selfhost_language_phase38 不在口径。阶段 39 Track B both_err 归因批 +16 行——39b/39b-2 未定义变量类型化抛错（src/mbc/vm.py `_builtin_undefined_error` +10 与 `_default_builtins` 注册 +3、`_RESERVED_BUILTINS` 补 未定义错误 +4−1——31-⑧ 异常类分歧退役，插口遮蔽即类型载体漂移故同列保留）；39a 链面 λ-dict 应用臂与 元素repr 渲染载体、39c/39d 语料刷新与 不折叠 源序前移、39e 判定面 both_err_equal 细分全在 matha/{interp,interp_matha,parser,stdlib,compiler_matha,vm}.matha 自举镜像与 scripts/selfhost_matrix.py、宿主侧 src/interp.py（`builtin_undefined_error`/`builtin_list_push` 注册）、新锁档 test_selfhost_language_phase39 均不在 core_py_lines 口径（src/interp.py 不属内核五件）。

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
- **语言完备与判定面收敛（阶段 31）**：31a func 定义 `->` 返回类型可选
  （29-⑧ 退役；无箭头 func_type=None 纯元数据，boot 解析函数定义同规，
  stage2↔stage3 字节码逐位一致）；31b 双 for 推导
  `[e for a in xs for b in ys if c...]`（30d 分歧条退役；宿主
  `ListComp.gens` + `_parse_comp_tail` 统一收口 + 解释器 gens 分支 +
  MBC `_emit_list_comp_multi` 嵌套下标循环发射〔零新 opcode，第 k 层
  条件绑定该层变量后求值，Python 语义〕；boot 做ListComp多/解析推导
  其余/_推导多子句；boot 编译器推导发射未支持——诚实报错登记）；
  31c 语句位括号链（块体位 `[x] >> [y]` 链收集，boot 解析输出语句镜像
  宿主 _parse_mech_stmt；顶层双面诚实拒绝维持）；31d f[0] 类型守卫
  （List/Tuple 前置探测→不可调用，30c 同款三面同文案）+ 字典迭代对齐
  （推导/for 字典源 host `list(items())` 同形元组对——此前 boot 静默
  空跑假成功清除）；31f 切片表达式求值 boot 真化（30 收官登记④退役；
  求值切片 族 Python 切片语义——缺端/负回绕/越界钳制，12 形态三面
  同判）；31e/31g sweep 装配与预算（golden manifest preload 前置拼接
  双轨同源，镜像 run_golden_tests.py:378——golden 36/39 both_err→equal；
  warmup barrier 把 worker init 移出单文件预算；`--timeout` 120→600——
  stdlib_symbols 600s 内 ok/ok）。快照 225：双面一致 206 / 诚实 differ 3 /
  boot_err 0 / both_err 13 / timeout 3（37/38 双面真跑 >600s 同判；
  interp.matha boot 面重档 >600s、host 面单跑 1.2s——共享预算 boot 先
  耗尽 host 未及跑，如实归因见 KNOWN_ISSUES 31）。
- **mb 面分歧收敛（阶段 33）**：六项 mb↔宿主语义/文案分歧三面（vm/hi/mb）
  + VM² 收口。33a 单元素尾逗号 `(1,)` boot 面静默吞成分组 → 诚实拒绝对齐
  宿主（boot 解析括号消解 逗号分支补右括号守卫，「期望表达式 (got
  PUNCT_RPAREN ')')」——32-① 退役；多元素/调用位尾逗号维持 boot 通用
  文案登记）；33b mb 比较族九臂与 `not` 返 真/假 Bool（此前 1.0/0.0
  浮点——32-④ 退役）+ 条件路由真值归一（求值 if/语句 if/while 经 真值
  helper，空容器/零/null falsy——32-⑦ 退役）；33c `in` 成员判断四面真化
  （vm `_op_in` 容器守卫 + native 容器守卫 raise_rt 可捕获 + mb
  `_成员判断` + VM² interp.matha 镜像；List/Tuple/Dict/Str 命中/未中 +
  非容器右侧「in 右侧需为序列/集合/字典，实际 int」四面同文案——32-③
  退役；native 旧锁 test_in_non_container_is_false 按真化退役惯例改锁
  诚实报错）；33d hi 面 if 无 else 条件假 → null（src/interp.py
  IfExpr/IfStmt else 缺失臂补 None，此前崩 NoneType；VM 面 None 同判）；
  33e mb type_of/_to_tuple 注册真化（注册内建尾部绑定 + 应用内建委托宿主
  BUILTINS——32-⑤ 退役）+ sum 累加器 0 起（stdlib list_sum，sum([])=0
  Int——32-⑥ 退役）；33h slice 内建字符串臂真化（收官探针踩中顺手真修
  ——mb 应用内建实 slice 臂 String 实参改走 31f `_切片值` 字符串臂
  （负回绕/端钳 Python 语义）、List 维持 list_slice、Tuple/其他诚实报
  错「slice() 需要字符串或列表」；33b 提速后 golden 38 语料 600s 内
  首次真跑完成、timeout→differ 漂移显形的根因；slice() 元组实参 vm 面
  宽松返元组 vs hi/mb 报错登记）。
- **语言面继续收敛（阶段 34）**：六项登记分歧全族真化（33-①②③④ +
  28-⑦ + 32-⑨⑪ 退役）。34a 尾逗号全族（多元素 `(1, 2,)` 与调用位
  `f(1, 2,)` boot 面改发宿主精确文案——33-① 退役；列表尾逗号三面合法）；
  34b 语句位 if `[` 路由（宿主 `_parse_if`/`_parse_while` 条件位
  `_in_cond_value` 值语境旗标，27f 同款先例——vm 漏出条件值三面分歧
  退役，28-⑦/33-② 退役）；34c in 左侧四面同文案（统一 boot 中文文案
  「in 左侧需为字符串，实际 int/list/NoneType」——vm `_op_in` + hi
  interp.py 二元运算 in 臂 + native 非零退出 stderr 同文案可捕获 +
  VM² interp.matha `_类型名` 小写面镜像——33-③ 退役）；34d slice
  元组 vm 收敛对齐宿主（vm `_builtin_slice` 容器守卫 + native
  `fn:slice` 容器守卫 err_slice_dom 可捕获——33-④ 退役；str/list
  透传与下标切片共用路径不受影响）；34e boot for `(k, v)` 多变量目标
  真化（boot parser.matha 括号解构目标 "变量" String|List 双形态 +
  interp_matha `_解构绑定/_解构绑定进` 宿主 `_exec_for_stmt` 镜像 +
  28b parity conv 面名单归一——32-⑨ 退役；boot 编译器发射面 List
  目标诚实拒绝「boot 编译器 for 解构目标暂未支持」登记）；34f hi 面
  func 值求值真化（src/interp.py _eval 补 FuncDef 臂 → None，vm 面同判
  ——32-⑪ 退役；mb 面表达式位 if 无 then 解析拒绝与 func 体块尾
  mb 块值 '<function>' 登记维持）。附带发现登记：boot 字典字面量裸键
  `{a: 1}` 析为变量引用（引号键三面一致）；vm 面编译路径 UNPACK_SEQ
  长度不匹配宽松补 null（解释面 hi/mb 诚实报错——编译面 vs 解释面
  解构语义分歧）。新锁档 test_selfhost_language_phase34 27 项。
- **自举解构贯穿（阶段 35）**：两项登记分歧同根退役（34-①④）。
  35a S1 UNPACK_SEQ 长度守卫四执行体：vm 0x57 严格化（List/Tuple 且
  长度精确匹配逐位绑定，否则「解构失败：期望 N 个元素，实际 <类型名>」，
  Closure→"function"——34-④ 宽松补 null 退役）+ native
  `_emit_unpack_seq` 严格化重写（err 池串同文案，try/catch 可捕获）+
  vm.matha `_解构类型名`（"__闭包__" 哨兵镜像）+ hi interp.py let 元组
  绑定守卫（语句位+表达式位，vm/hi/native/VM² 同文案）；35b S2 boot
  编译器 for 解构发射真化（compiler_matha `_分配循环变量` 收窄单变量 +
  `_分配循环变量们`/`_分配循环位置们` 名单归一逐名折叠 + `_for循环码`
  UNPACK_SEQ 发射 + `_存解构逆序` 逆序存储，宿主 _emit_for_stmt 镜像
  ——34-①「boot 编译器 for 解构目标暂未支持」退役；单变量目标零
  字节码回归 + 五语料 stage2↔stage3 逐位一致 + M3V 运行面真跑）。
  新锁档 test_selfhost_language_phase35 42 项。登记不修：mb 表达式位
  let 元组绑定 honest reject「未知表达式类型: let元组绑定」；m3v
  编译态 try/catch 不捕获运行期错误（全族，既有边界——vm.matha 解释
  循环无异常帧机制，登记锁防漂移）。
- **mb/boot 面收口批（阶段 36）**：四项登记分歧真化（35-① + 34-②③⑤
  退役）。36a 表达式位花括号 if（boot parser.matha 解析if表达式补花括号
  分支宿主 `_parse_if_expr_impl` 同构 + interp.matha 求值 程序 臂块执行
  取尾值——34-② 退役；六形态三面同判 + 输出尾块值 [5, 6]）；36b mb
  块尾 func 定义块值 → null（interp_matha 执行语句/执行声明 函数定义臂
  (closure, env2) → (null, env2) + interp.matha 双臂镜像——34-③ 退役；
  块值 [None] 三面同判、blk_used [1] 维持）；36c boot 字典裸键（求值字典
  `_字典键` helper："变量" 键析为字符串键名——34-⑤ 退役；`{a: 1}` ≡
  `{"a": 1}` 四面同判）；36d mb 表达式位 let 元组绑定（求值let元组/
  绑定求值let元组 + `_解构绑定元组` 闭包标记跳参绑定 + 求值/执行语句/
  执行声明 三臂路由——35-① 退役；错误「解构失败：期望 N 个元素，实际
  <类型名>」四面同文案，function 映射同判）。附带发现登记：vm 编译路径
  字典字面量非字符串键（`_literal_key` IntegerLit 字符串化 + INDEX_GET
  缺键 null）；boot 块尾 Binding 块值 mb [5] vs vm/hi [None]（34-③
  同族）。新锁档 test_selfhost_language_phase36 23 项。
- **语言面清尾批（阶段 37）**：五项登记分歧退役（32-② 31-③ 协议一致
  锁 + 32-⑩ 36-① 36-② 真化）+ 同族顺手真修。37a 陈旧登记退役：
  32-② 空括号 () 三面早已统一零参调用约定（() 降糖 IntegerLit(0)，
  f() = f(0)）与 31-③ 非容器切片三面早已统一 MathaRuntimeError 同文案
  「切片操作不支持: int[1:2]」（31f 真化后编译面 raise_rt 与解释面同源）
  ——协议一致锁防漂移。37b 块尾 Binding 值模型收尾（36-② 退役 +
  同族顺手真修）：interp_matha 绑定求值let 无体臂 (v, env)→(null, env)
  + interp.matha 同形；表达式位块（求值程序/求值 程序 臂）尾值
  `_块尾值` 映射（绑定/let绑定/let元组绑定尾不回传值——宿主
  _BLOCK_TAIL_STMT_NODES 头三族；程序位顶层 run_ast → 执行语句保持
  「程序值 = 尾表达式值」约定不映射——phase8pre gapfix 程序值锁同源）
  ——四形态三面 + VM² 同判 [None]；有体 let 尾与裸赋值尾同族收敛。
  37c 链式 let rec 互递归真化（32-⑩ 退役）：interp.py 表达式位
  LetBinding 链头收集 body 链 rec 名建注册表压栈（`_rec_chain`）逐名
  预绑占位，成员复用未填占位（_ref 未填守卫——32e 勘误保留：弹栈后
  同名恒新建、跨函数在途占位不串线）；块/程序入口预注册沿 body 链整链
  （`_preregister_rec_chain`——37c 前 body is None 条件漏带体链）；
  interp_matha/interp.matha 预绑链占位镜像 + 占位复用守卫——三面 +
  VM² 同判 [0]。37d 字典自然键真化（36-① 退役）：compiler.py
  `_literal_key` IntegerLit/FloatLit/BoolLit 原值入常量池 + parser.matha
  `花括号种类` 整数/浮点/布尔首 token 冒号前瞻 → 字典（宿主
  _parse_brace_dispatch 同判）——int/float/bool/str 键 + d["2"] 反向
  null 三面 + VM² 同判；boot 编译器/解释器/native 随既有路径自然同判。
  附带发现登记：vm/hi 输出尾块值 host 内部分歧（编译面语句尾 PUSH_NULL
  vs 解释面输出通道规则 _eval_block_value outputs[-1]；boot 解释面已随
  37b 收敛 vm 面）+ mb 面集合构造求值未知表达式类型（boot 求值无
  集合构造 臂）+ 37c 嵌套链同名成员 env 槽覆写边界。旧锁真化改锁四处：
  phase31 31f vm 面文案+类型加强、phase32 test_32e_chained_mutual_true、
  phase36 test_36x_vm_dict_intkey_true / test_36x_blk_tail_binding_true。
  新锁档 test_selfhost_language_phase37。
- **m3v 异常帧机制（阶段 38）**：35-② 真化（编译态 try/catch 捕获运行期
  错误）——拍板走推荐项「捕获闭包单点包裹」：不复制 vm.py 异常帧机制入
  vm.matha，而在 捕获闭包/捕获内建 两个分派位用 Matha 级 调用捕获 把子
  执行体/内建调用单点包裹成带内结果——载体（vm.py Python try/except /
  interp.py / native longjmp / VM² 同链）不可知，异常在分派边界统一转带
  内 "__异常__" 标记。捕获闭包位 守卫 "__异常__" → ["__异常__", 消息]
  入顶帧（try/catch 接管），否则透传既有 "__抛错__"/"__停机__" 臂；捕获
  内建位同形转 ["__抛错__", 消息]。载体派发家族（除零/解构失败/未定义变
  量）三面 + VM² 同判；带内 RAISE 路径零扰动；实参表双嵌套 [[…]] 配对
  invoke_value 的 fn(*args) 铺开。附带发现登记：vm↔m3v 下标越界文案分歧
  （vm/hi 透传 Python IndexError vs m3v stdlib get 域文案「列表索引越
  界: 5」——同一载体守卫、不同检测点，38a1 双面文案锁防漂移）+ 38a 窄
  分歧新建全局名捕获路径丢失（结构脊展开，38a7 登记锁）。vm.matha
  +46−31；src/ 零改动、指令码不变；ast_vm_gap 快照零扰动。新锁档
  test_selfhost_language_phase38 12 项。
- **Track B both_err 归因批（阶段 39）**：方向 A 拍板——逐个归因 13 both_err
  语料，清零或如实登记为边界。39a 链面应用分派收口（bootstrap_test 根因
  族）：① λ-AST 字典应用臂——interp_matha/interp.matha 应用函数·应用多参数
  函数的 Dict 臂此前只认 "__builtin__"，语法器.做Lambda 产物裸节点字典落
  「不可调用的值」，现经 求值lambda 折闭包重入 __closure__ 机制（柯里化/多参
  同臂复用——链 API 直调 3.6/3.7/3.9 形态）；② 不可调用值渲染载体——链面
  标准库.str 改 标准库.元素repr（CPython repr 规则，非字符串委托 str），
  str/空串/int/列表/CJK/转义六形态 vm/hi/mb/bootvm 四面消息逐字同判（既有
  ': 5' / ': []' 锁零扰动）；③ interp.matha 零参闭包守卫（做Lambda([], body)
  此前落原生 IndexError，镜像 interp_matha 29d 空参数表口径）。39b/39b-2
  未定义变量异常类真化（31-⑧ 退役）：新增类型化抛错内建 未定义错误 →
  MathaUndefinedNameError（src/interp.py BUILTINS + src/mbc/vm.py
  _default_builtins 同类抛错、消息逐字不变），链面 查找环境/查找环境链/
  查全局 缺名臂改走该内建；vm.matha 侧 内建名表 注册（防 查全局 自递归）+
  内建特殊 带内臂 + 应用内建 专用名守卫补名，未定义错误 同列宿主两侧
  _RESERVED_BUILTINS 与 vm.matha 是保留内建名（守卫先于插口分派，注册必被
  遮蔽——四面一致诚实拒绝）。Track B golden 13/31 两条目转 both_err_equal。
  39c/39d：bootstrap_matha 语料刷新到现行柯里化 API（host 面旧错「属性访问
  失败: str.类型」退役为 4 输出双面 ok）+ compiler_matha 的 不折叠 模块级
  let 前移模块顶（宿主闭包按定义序快照环境——bootstrap_full_test host 面旧
  首错名 不折叠 退役，22 输出双面逐字相等）+ 本地 dict_from_pairs 十行副本
  退役为 use 标准库 导入（双源漂移面消除）。39e 判定面细分：_classify 双 err
  且 boot_err == host_err 逐字全等 → both_err_equal（双面同判的诚实边界与
  残留分歧分列）+ summary 七分类键 + structure_check 缺键诚实报「需 --write
  重生成」。快照重生成 225 = both_ok_equal 211 + both_ok_differ 3 +
  both_err_equal 11 + both_err 0 + timeout 0；boot 编译器 stage2↔stage3
  逐位一致零扰动（39d de-clone 不改指令码），src/ 仅 vm.py +16 行。新锁档
  test_selfhost_language_phase39 31 项 + phase21 两条陈旧边界锁改真化锁。
- **语言收敛与元组真化（阶段 32）**：五片语言收敛 + ② 元组真化受控切片
  （拍板「以维持登记为基础，以切片真化的方式推进，拆分可回滚受控切片逐个
  验证」）。32a VM 字典迭代四面归一（宿主编译器 for/推导三发射位统一经
  `_迭代源` 内建 + vm.matha 镜像 + native iter_source，dict → ('k',v) 对
  ——31-① 退役）+ BUILD_SLICE 不可切片守卫三面同文案；32b hi 面
  ChainStmt 块尾链真化（31-⑤ 退役）；32c boot 编译器推导发射真化（单/多
  for+if——31-⑥ 退役）；32d mb 面 str 通用化（Bool/null/容器/函数渲染 +
  自举闭包守卫——28-⑨ 退役）；32e let rec 互相递归三面贯穿（hi 预注册
  占位 + VM 预发盒 + boot 待填盒镜像——29-② 退役）。32-② S1 BUILD_TUPLE
  运行时指令面（0x65=101，三执行体直注执行、零发射零行为变化）；S2 发射面
  切换（宿主+boot 编译器元组字面量 → BUILD_TUPLE——31-②「元组按列表处理」
  退役；native 消费面语料回归；stdlib/vm.matha str 元组渲染臂；`-` 容器
  守卫四面同文案）；自举编译器同名函数重定义出口去重（宿主 dict 保首现序
  取末值语义镜像，拼接编译函数表千级规模出口一次性双遍完成）。
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
| `tests/` | 189 个测试文件（全量见最近一次 `make check`） |
| `kernel_purity` | 白名单 + 核心无逃逸模块 + 插件不得碰 VM 私有面 |
| `ast_vm_gap` | 78 个 AST 节点、59 发射 / 19 有意无码 / **0 不认识**（ListComp 已由 VM 编译为下标循环 + `append` 累加，不再静默返空）、**0 阻塞缺口**；指令码 36/36/36 |
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
