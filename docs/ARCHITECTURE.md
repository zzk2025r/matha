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
共 **34,538 行**（`repo_facts.core_py_lines`，阶段 11 孤儿清算 −2,653 行；阶段 12b 终端 OS 胶水内建 +141 行；阶段 13 终端补全 os 域 升级包/执行命令输入 胶水 +29 行；阶段 14 解析器踩界真化 +113 行——词法器续行判定 + 主解析器 then 行首/参数跨行 skip；阶段 15 双端语义对齐 +8 行——VM 顶层裸表达式发射 + host 顶层 IfExpr 真执行；阶段 16 双端语义第二片 +10 行——let-in 列表体丢死兼容 + 顶层裸表达式求值丢弃 + 严格值相等三端登记 + 词法器剥 BOM；阶段 17 全面清算 +9 行——解析器 _CMP_ALIASES 归一化常量与三处 op 取值位点；阶段 18 双端语义第三片 +56 行——解释器删模块递归双执行 + use 加载自测块跳过标志 + 通道收发 host 求值 + 解析器全中缀回退与 `_bracket_followed_by_infix`；阶段 19 双端语义第四片 +16 行——VM 编译器 match/switch 表达式位 + MechUnit 裸 list body 逐元素编译 + 成长引擎规则聚合；阶段 20 match 收口 + finally 全链 +176 行——编译器 match 动态兜底/守卫先求值/try 三路径重抛、VM RAISE_MATCH 0x63 处理器、原生 RAISE_MATCH 与 repr 渲染运行时、解释器 match 无匹配口径对齐、opcode 登记；阶段 21 插件符号 VM 面 + use 编译解析 + catch 哨兵 +119 行——VM Frame functions 表与 MAKE_CLOSURE 逐帧函数表解析、GET_ATTR 内建名回退、解析器 switch 表达式位、capability/json_builtin 插件移植胶水与 exec_api use 加载器注入面（惰性跳板经解析器动态装入，eval/auto 零领域急切加载语义保真）；阶段 22 全面清算 +2 行——22a time_builtin 吞错日志清算诚实化（err 面全量记录不再静默吞）；22c 语句位裸赋值真化在解释器面（src/interp.py _exec_stmt），不计入本体量；阶段 23 臃肿优化 + 扩展面 +152 行——23a 惰性内核节（src/kernel/lazy_kernel.py LazyKernelFn + time/terminal make_* 工厂化、interp/vm 双面 lazy_section 注册、interp 删顶层 json/terminal_builtin import）；23b features 单源 DEFAULTS/known_states/state_tuple + matha_main features 查询面对齐；23c 解析缓存（parser parse PARSE_CACHE opt-in LRU 32 + custom_ops 版本计数 + features.state_tuple 键）；23d 统一扩展面（src/extensions.py 四面协议 + matha ext CLI + PluginResolver.reload 公开回位 + interp _load_matha_source 包回退 + matha_term autorun 扩展条目 + matha_main _build_parser 命令表化）；阶段 24a 资源库代码化 +3 行——VM 编译器模块同名冲突（module X { func X }）命名空间绑定不发射（平面函数可调用面优先，与宿主 env 同规则；资源_成长 资源形态）。资源库 use 解析面（interp _library_module_source + 解析序 matha/ → 安装包 → 资源库 + 资源索引 _CN2FILE 映射）在 src/interp.py，不计入本体量。阶段 24d 动态解析 +68 行——host `_DYNAMIC_VALUE_DECLS`/`_is_dynamic_value_decl` 尾值声明分离 + `_b_dynamic_eval`（parse→decls 依 run() 同序注册执行、尾值 `_eval`，绑定持久落共享 env）+ VM `_make_dynamic_eval`（尾值包装哨兵零参 FuncDef 编译进嵌套 VM、`nested.globals = vm.globals` 对象共享、跨模块 `fn.consts`/`fn.functions` 钉池、尾值经 `globals.pop` 哨兵 `invoke_value` 取回零污染）。阶段 24e 建模仿真 +4 行——exec_api._wire_plugin_runtime 增 make_simulation_runtime 注入面（仿真_欧拉/仿真_龙格库塔 导函数回调绑定运行本体 invoke_value，宿主解释器与 VM 同名协议；惰性跳板构造零 import）；仿真数值核心在 src/domains/simulation.py、宿主内建在 src/interp.py，均不计入本体量。阶段 24f 单片机面 +0 行——宿主内建 `_b_mcu` 统一分派与 6 符号柯里化注册均在 src/interp.py、领域实现在 src/domains/mcu.py（纯规格面：SVG 电路图纸 / Arduino C 真代码生成 / 控制载荷归一化 + 串口实时显式拒绝 / 工具链真检测真烧录（avrdude/st-flash/esptool/openocd 四族 argv，可注入测试面）/ GPIO-UART-I2C-SPI-PWM 五类驱动模板 / 文本真落盘），均不计入本体量。阶段 24g 热启动与运行 +5 行——exec_api._wire_plugin_runtime 增 make_hotreload_runtime 注入面（热启动 mtime 快照装载 / 热重载变更检测重合并绑定运行本体，惰性跳板同构；setdefault 不覆盖程序自定义）；解析 helpers（_matha_module_path/_package_module_path/_library_module_path/_hot_pair 三级路径解析）与宿主内建（_b_hot_start/_b_hot_reload）在 src/interp.py、VM 胶水在 src/domains/capability.py（消息常量同源），均不计入本体量。阶段 24h 资源库新能力模块 +0 行——建模仿真（simulation/建模仿真.matha：双法对比/步长扫描/轨迹抽样）与单片机（mcu/单片机.matha：闪灯程序/闪灯图纸/呼吸灯斜坡/控制载荷）两纯 Matha 组合层落 matha/library/ 并入资源索引（19→21 条），均不计入本体量。阶段 25 自生凭据与应用中心 +0 行——商店 HMAC 令牌域（src/domains/store.py 商店_签发令牌/校验令牌/吊销令牌）与 socket 服务端域胶水（src/domains/networking.py 网络_服务/接受/收/发/关闭）在领域层、应用中心引擎在 matha/store_engine.matha（纯 Matha：HTTP 解析/路由/索引）、CLI 驱动在 src/app_cli.py（matha app 八子命令 + Release 导入），均不计入本体量；解释器柯里化共享捕获表修复（src/interp.py 部分应用路径拷贝追加）+11 行不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 26a 运行时注册表泛化 +43 行——exec_api 后端注册表条目化（_BackendEntry dataclass）+ unregister_backend/set_backend_enabled/backend_info 三面 + make_vm 工厂（4 处 VM 构造收敛）+ _wire_plugin_runtime 增 make_compiler_framework_runtime 注入面；编译器框架域（src/domains/compiler_framework.py 五框架模块消费面）、设备管理器信息层（src/system_inventory.py）与 matha sys CLI（src/matha_main.py 命令族）均在领域层/CLI 层，不计入本体量。阶段 27f 解析器字典值语境 +16 行——_parse_dict_value 值位旗标（init/括号消解链字典值判位/字典字面量值位包装三处；{"k": [x]} 值位 [x] 为列表字面量而非输出命令，与三元分支/return 同口径；boot 链六文件 AST 逐字节探针零扰动，182 语料唯一差异面 matha/vm/matha_vm.matha:66 帧栈构造修正为真列表）。阶段 28d 自举层 VM 注册插口 +40 行——src/mbc/vm.py register_builtin/unregister_builtin（保留名/模块函数/非可调用诚实拒绝）；28 其余宿主面（src/extension_port.py 五动作端口层、src/custom_ops.py + src/compiler/pass_manager.py unregister 注销面、src/interp.py 解释器宿主注册注销 +39 行、src/os_runtime.py 工具链单元装载 +114 行）均不在 core_py_lines 口径（src/ 不属内核五件）。阶段 29b 自举链语言级缺陷真化 +209 行——29b-① 语句位下标赋值 STORE_SUBSCRIPT 0x64 双面真化（opcodes +1；vm 0x64 处理器 +20：容器[index]=val 原位写入、字典缺键新建〔对齐 host dict.get 29b-④〕、不可哈希键领域文案、越界 IndexError 透传、不可下标对象归一到 src/interp.py 逐字一致文案；compiler +30：顶层 _compile_stmt 与块位 _emit_block 下标赋值发射〔栈序 容器/下标/右值；块尾 leave_last 位保持比较语义，与宿主边界一致〕；native +131：setitem_rt 原生运行时——列表正/负回绕原位写、越界/字典缺键新增〔dict_put 函数式不可原位扩容，诚实拒绝〕/不可下标 五路领域错误，消息经 match_render 拼接）；29b-②③⑥ 解析器 lambda 面真化 +27 行——lambda 立即调用（((x)=>x*2)(21) 分组后缀应用）、参数类型标注（(y: Int) => … 走通用 _parse_lambda_param）、单 `=` 右值后悬空关系运算符回退改按赋值解析（右值 _parse_expr 整体纳入三元；右值后 `?` 语料惯用式保持比较语义，自举 解析比较_续 同规回退）。宿主面 src/interp.py 下标赋值/文案归一与镜像 matha/{parser,compiler_matha,vm}.matha 不计入本体量。阶段 29e 编译后钩子槽 +32 行——exec_api set_compile_hook/get_compile_hook/_apply_compile_hook 纯钩子槽与 compile_module/build_exe 统一接线（29c 宿主面在 src/interp.py 与 matha/ 镜像、29d scripts/selfhost_matrix.py 与快照、src/compiler/mbc_adapter.py 字节码遍适配层——均不在 core_py_lines 口径，src/compiler 属 LEGACY_PREFIXES）；阶段 30 执行面收口 +0 行——boot 链五片真化（30a 分派路由/30b use 跨模块/30c 文案对齐/30d 语法缺口）全在 matha/ 镜像与 scripts/selfhost_matrix.py，宿主 type_of null 分支（src/interp.py +2 行）不在 core_py_lines 口径。阶段 31 语言完备 + 判定面收敛 +92 行——31a func 定义 `->` 返回类型可选（src/parser.py _parse_func_def 箭头分支可选化 +15，29-⑧ 真化；boot 镜像 matha/parser.matha 解析函数定义同规不在口径）；31b 双 for 推导（src/parser.py _parse_comp_tail 多生成子句统一收口 + src/ast_nodes.py ListComp.gens 字段 +5；src/mbc/compiler.py _emit_list_comp_multi 嵌套下标循环发射 +72，零新 opcode；宿主解释器 gens 分支 src/interp.py +38/−32 不在 core_py_lines 口径；boot 镜像 做ListComp多/解析推导其余/_推导多子句 不在口径）；31f boot 切片求值、31c 语句位括号链、31d f[0] 守卫与字典迭代对齐、31e/31g sweep 装配与预算（scripts/selfhost_matrix.py）均不在 core_py_lines 口径）；阶段 32 语言收敛 + 元组真化 +273 行——32-② S1/S2 元组发射面切换（src/mbc/opcodes.py BUILD_TUPLE 0x65 +1〔指令码 35→36〕；src/mbc/compiler.py TupleExpr→BUILD_TUPLE 发射臂 +43；src/mbc/vm.py 0x65 处理器 + BUILD_SLICE 不可切片守卫 +26；src/mbc/native.py 元组对象与 ~29 消费面〔print/下标/切片/迭代/len/str/拼接/重复/真值/相等/iter_source〕+221）；宿主解释器面（src/interp.py `_迭代源`/ChainStmt 臂/let rec 预注册占位）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{compiler_matha,interp_matha,stdlib,vm}.matha 与三新锁档（test_tuple_instruction_s1/test_tuple_emission_s2/test_selfhost_language_phase32）均不在口径）。阶段 33 mb 面分歧收敛 +66 行——33c `in` 四面（src/mbc/native.py 容器守卫 +57〔六路类型 tag 分派 + err_in_prefix 池串 + raise_rt 可捕获〕；src/mbc/vm.py `_op_in` 容器守卫 +10−1）；33d hi 面 if 无 else（src/interp.py IfExpr/IfStmt else 缺失臂 +8）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{parser,stdlib,interp,interp_matha}.matha 与新锁档 test_selfhost_language_phase33 均不在口径。阶段 34 语言面继续收敛 +124 行——34b 语句位 if `[` 路由（src/parser.py `_in_cond_value` 值语境旗标 +17）；34c in 左侧四面（src/mbc/vm.py `_op_in` 守卫 +4；src/mbc/native.py in 守卫与 err_in_left_prefix 池串）；34d slice 元组（src/mbc/vm.py `_builtin_slice` +14−1〔含开放端缺界 None
  放行——下标切片 l[1:] 发射面 slice(c)(1)(None) 按 Python 切片语义
  容忍，VM 面下标切片经此内建而 BUILD_SLICE 直路原生容忍〕；src/mbc/native.py `fn:slice` 容器守卫 + err_slice_dom）；34c hi 臂与 34f FuncDef 臂（src/interp.py +8）不在 core_py_lines 口径（src/interp.py 不属内核五件）；boot 镜像 matha/{parser,interp,interp_matha,compiler_matha}.matha 与新锁档 test_selfhost_language_phase34 均不在口径。阶段 35 自举解构贯穿 +16 行——35a S1 UNPACK_SEQ 长度守卫（src/mbc/vm.py 0x57 处理器严格化 +7〔长度精确匹配逐位绑定，否则「解构失败：期望 N 个元素，实际 <类型名>」，Closure 映射 "function"——34-④ 宽松补 null 退役〕；src/mbc/native.py `_emit_unpack_seq` 严格化重写 +9 净〔err 池串 err_unpack_pre/err_unpack_mid，try/catch 可捕获〕）；src/interp.py let 元组绑定守卫（语句位+表达式位）与 boot 镜像 matha/{vm,compiler_matha}.matha（35b S2 `_分配循环变量们`/`_存解构逆序` UNPACK_SEQ 发射——34-① 退役）、新锁档 test_selfhost_language_phase35 均不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 36 mb/boot 面收口批 +0 行——四片真化全在 matha/{parser,interp_matha,interp}.matha 自举镜像（均不在 core_py_lines 口径），src/ 零改动、指令码不变，新锁档 test_selfhost_language_phase36 不在口径。阶段 37 语言面清尾批 +3 行——37d 字典自然键（src/mbc/compiler.py `_literal_key` IntegerLit/FloatLit/BoolLit 原值入常量池 +6−3——36-① vm 字符串化退役；boot 编译器 `_发射键`/boot 解释器 `_字典键`/native dict_get val_eq 扫描随既有路径自然同判零改动）；37c 链式 let rec 预绑注册表（src/interp.py `_rec_chain`）、37b 块尾 `_块尾值` 尾值映射与 37a 协议一致锁在 src/interp.py 与 matha/{parser,interp_matha,interp}.matha 自举镜像、新锁档 test_selfhost_language_phase37，均不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 38 m3v 异常帧机制 +0 行——38a 载体异常→带内转换（捕获闭包/捕获内建双点 调用捕获 载体守卫包裹）全在 matha/vm.matha 自举镜像（不在 core_py_lines 口径），src/ 零改动、指令码不变，新锁档 test_selfhost_language_phase38 不在口径。阶段 39 Track B both_err 归因批 +16 行——39b/39b-2 未定义变量类型化抛错（src/mbc/vm.py `_builtin_undefined_error` +10 与 `_default_builtins` 注册 +3、`_RESERVED_BUILTINS` 补 未定义错误 +4−1——31-⑧ 异常类分歧退役，插口遮蔽即类型载体漂移故同列保留）；39a 链面 λ-dict 应用臂与 元素repr 渲染载体、39c/39d 语料刷新与 不折叠 源序前移、39e 判定面 both_err_equal 细分全在 matha/{interp,interp_matha,parser,stdlib,compiler_matha,vm}.matha 自举镜像与 scripts/selfhost_matrix.py、宿主侧 src/interp.py（`builtin_undefined_error`/`builtin_list_push` 注册）、新锁档 test_selfhost_language_phase39 均不在 core_py_lines 口径（src/interp.py 不属内核五件）。阶段 40 真缺陷批 +28 行——40a 三引号多行字符串（src/lexer.py `_string_triple` 三态扫描 + `"`/`'` 双引号首字符分派位 +30−2——39-① 双端不支持退役；boot 镜像 matha/lexer.matha `是三连`/`扫描三引号续` 与未闭合串诚实抛「字符串未闭合」不在口径）；40b differ 3 语料收口（宿主对象值语义 `__eq__`/`__repr__`——src/autonomous.py `_OptResult`/`_GrowResult`、src/domains/data_science.py `Dataset`；神经网络显式播种 src/ai_framework.py `seed_random` + `随机种子` 域内建注册——均在 src/domains 与领域层，不属内核五件）；40c interp.matha 机械单元/生成语句 镜像臂缺口与 NEWLINE token 位置约定为登记不修（探针在 tests/test_selfhost_language_phase40.py，不在口径）。阶段 41 资源库假成功清算批 +0 行——37 个 `matha/resource/**`
纯 Matha 资源文件真化/补口径注（危险桩真实现 + 无定义读数改诚实 None +
链面缺失内建逐文件绕开），src/ 零改动、指令码与本体量 33,480 不变；
ast_vm_gap 快照重生成仅 13 节点 `used_in` 语料计数变动（节点 78 / 发射 59
/ 无码 19 / 指令码 36 结构不变）；新锁档 tests/test_resource_algorithm_-
true_phase41.py 不在口径。阶段 42 纯 Matha 装载器 + 终端链面默认后端 +1 行
——42 的装载/依赖解析/模块体执行全在新增 `matha/loader.matha` 与既有 boot
链镜像 `matha/interp_matha.matha` / `matha/interp.matha`（不在 core_py_lines
口径），`src/matha_chain.py` 装配壳与 `src/interp.py` 宿主对位实现不属内核五
件；口径内唯一改动是 `src/mbc/vm.py` 调试拒绝文案尾句改指宿主后端（+1），
指令码与新锁档 test_selfhost_language_phase42 不在口径。阶段 43 冻结 exe 与
常驻监管批 +0 行——43 的改动全在装配面与外围：`matha.spec`（PyInstaller 装配
脚本，非 src 五件）、`src/matha_chain.py` 冻结态根序（装配壳）、`src/os_runtime.py`
桥面薄壳（`self_launcher`/`supervise`/`supervision`）、`src/domains/os_module.py`
`运行脚本` 真化、`src/matha_main.py` 的 `server`/`监管` 命令位、
`src/openai_compat_server.py` 的 `serve()` 单一启动面、监督策略所在的纯 Matha
`matha/os/kernel.matha` 与镜像 `matha/{loader,interp,interp_matha}.matha`、
Windows 安装/卸载家族 `scripts/*.{bat,ps1,iss,nsi}`——内核五件 `src/lexer.py`
+`src/parser.py`+`src/ast_nodes.py`+`src/kernel/**`+`src/mbc/**` **零改动**，
本体量 **33,481 行不变**、指令码 36 不变；新锁档 test_frozen_entry_phase43 不在口径。
阶段 44 原生 OS 派生面 **+618 行**——44b 新档 `src/mbc/native_process.py`（578 行，
进程映像族五内生的 x86-64 发射器：kernel32 惰性解析 + 32 槽句柄表 + CreateProcessW/
WaitForSingleObject/GetExitCodeProcess/TerminateProcess/CloseHandle/MultiByteToWideChar
六 API，运行路径零 Python 模块）+ `src/mbc/native.py` 挂载（+16：NATIVE_BUILTINS/
`_BUILTIN_ARITY`/`_BUILTIN_EMITTERS` 三名表与 prologue/epilogue 注入）+ `src/mbc/vm.py`
映像族显式拒绝（+24：五名「需原生后端」拒绝内建，非静默降级）；宿主解释器面对位拒绝
（`src/interp.py` +31）、桥面载体回收（`src/os_runtime.py` +57−13）、领域 `停止进程` 回落桥面（`src/domains/os_module.py` +5−1）、CLI `原生构建`
命令位与 `构建` 假广告清算（`src/matha_main.py` +50−6）不属内核五件，不在口径；
指令码 36 不变（映像族是内建名而非新 opcode），新锁档 test_native_process_phase44
不在口径。
阶段 45 原生映像承载 Matha 工具链首片 **+439 行**——**45a** `MAX_NATIVE_ARITY` 8→15
（15 取调用点/序言 disp8 位移可达上界 `-8*(argc+1) ≥ -128`，`apply_rt` 按 rdx 动态
`rep movsq` 本身无 arity 假设；boot 链唯一越界真形 `扫描三引号续`(9) 旧上限使**整个词法器**
在原生面直接编译失败）；**45b** 多模块链接（`src/mbc/compiler.py compile_sources` +22
逐源解析并入单个 `Program`、`native.py compile_sources_to_exe`、`src/kernel/exec_api.py`
的 `compile_modules` 与 `build_exe(list[str])` +19）；**45c** 静态栈模型（`_stack_effect`
全操作码净增量表 + `_operand_peak` 峰值/汇合/夹住/不收敛四判据 + `_stack_budget` +
操作数栈落 `.bss` 1MB + `_start` 填 `stack_floor` 与调用栈守卫标签 + PE StackReserve 8MB）；
**45d** 原生序比较助手 `val_cmp`（字符串/列表/元组/布尔深序，替代旧的 `.data` 地址序判定）、
帧内解构写回真 `rbp`、尾位置一元负返回值回读修正（`src/mbc/native.py` +418−20 全部在此）。
CLI `原生构建` 多源位（`src/matha_main.py` +19−11）与宿主解释器面 `src/interp.py` 均不在
`core_py_lines` 口径；指令码 36 不变（零新 opcode），新锁档 test_native_selfhost_phase45（112 项）
与 test_native.py 改锁不在口径。
阶段 46-1（boot 链 latent 名归因 + `stdlib.to_upper` 死函数真修）**+0 行**——产品侧改动只有
`matha/stdlib.matha` 的 1 行（`in _map(0, acc)` → `in _map(0, "")`），`src/` 零改动故本体量
维持 34,538；新锁档 test_native_selfhost_phase46（22 项）与 test_native_selfhost_phase45
名集读数同步（25→24）不在口径；指令码 36 不变。
阶段 46c（判定面换形：原生自证 + 手算对拍取代 Python 差分 oracle）**+0 行**——`src/` 与
`matha/` 零改动（只换形判定面：`scripts/selfhost_matrix.py` 功率分层 + 新锁档
test_judgment_face_phase46c（19 项）+ phase29/phase39 两处快照键形改锁，均不在口径）；
本体量维持 34,538、指令码 36 不变、226 语料分类零漂移。

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
- **真缺陷批（阶段 40）**：方向 A 拍板——清零 Track B 两类残留缺陷（三引号
  字符串 + both_ok_differ 3），未闭合字符串同批真修；40b 形态拍板「产品侧真
  修」而非放宽判定面 `_norm`。40a 三引号多行字符串双端词法器真化（39-① 退
  役）：宿主 `src/lexer.py` 新 `_string_triple` 三态扫描（闭合三连/转义续行/
  EOF 未闭合）+ `"` 与 `'` 首字符三连判定分派（+30−2 → 本体量 33,480）；boot
  镜像 `matha/lexer.matha` `是三连`/`扫描三引号续`（+37−5）——`""""""` 空串、
  跨行串、`"""a\tb"""` 转义、`'''…'''` 四形态 token 三元组双端逐位 parity，
  多行值 vm/hi/mb/VM² 四面 + M3V 六文件链同判；未闭合串四形态双端诚实报错
  同文案「字符串未闭合」（载体类名 LexerError vs MathaRuntimeError 登记③）。
  40b differ 3 语料收口（31-⑨ 退役，both_ok_differ 3 → 0）：宿主值语义
  `__eq__`/`__repr__`——`src/autonomous.py` `_OptResult`/`_GrowResult`、
  `src/domains/data_science.py` `Dataset`（可变故不设 `__hash__`；`_Sample`
  含挂钟耗时故意不改），`selfhost_matrix._norm` 对不透明对象按身份比较的判
  定面零放宽；神经网络显式播种——`src/ai_framework.py` `seed_random` +
  `src/domains/neural_network.py` `随机种子` 柯里化内建 + registry 模板 +
  manifest.json 重生成（89 插件 / 2806 符号）+ 语料顶置 `随机种子(2026)`。
  40c 旧锁收口与判定面：快照重生成 225 = both_ok_equal 215 + both_ok_differ
  0 + both_err_equal 10 + both_err 0 + timeout 0（bootstrap_test 由
  both_err_equal 转 both_ok_equal）；phase30 differ 锁、phase39 39c 根因锁、
  phase19/phase21 bootstrap_test 边界锁四处真化改锁（裸解释器面递归预算需
  按 Track B worker 口径抬升——登记④限幅伪影）。新登记两条语言面边界：
  `matha/interp.matha` 缺 机械单元/生成语句 执行臂（29c 只落 interp_matha，
  登记①）+ NEWLINE token 位置/值约定分歧（登记②）。src/ 仅 lexer.py +28，
  指令码与 ast_vm_gap 快照零扰动。新锁档 test_selfhost_language_phase40
  27 项。
- **资源库假成功清算批（阶段 41）**：方向 A 拍板——只动纯 Matha 资源库
  `matha/resource/**`（37 文件、+2611 −767 行），`src/` 零改动、本体量
  33,480 与指令码 36 不变；判据为三面（hi 宿主解释 / vm 编译 VM / boot 链
  调用面）。41a/41b/41c 危险桩真化：`HMAC哈希`（旧体直接返回消息本身，现
  两轮 131 进制滚动散列、密钥入内外两轮）/ `死锁充分条件` / `银行家安全性`
  （旧恒返 真；现经典安全性算法逐轮扫 Need，维度不齐声明 fail-closed 取保
  守答「假」而非越过末尾下标落 Python IndexError）/ `资源分配图含环`（旧
  恒返 假，现等待图 DFS）/ `活锁检测` / `SSTF·SCAN·C_SCAN 总移动` / `LRU
  缺页` / `FCFS·RR·HRRN 周转时间` / `Dijkstra距离`（28-⑧ 退役——旧桩恒返
  [999999…]，现权重和+1 作无穷 + O(V²) 顺序松弛，不可达记 -1）/ `内部收益
  率近似`（恒返 0.1 → 二分求根）/ `二阶极点` / `音频混音` / `直方图均衡化
  映射` / `sepia滤镜` / `中位数`（偶数长度走 `//`）/ `复制列表`·`排序`（不
  改入参）/ `时间戳转日期`（小数年 → 整除，合 `-> Int` 声明口径）。41d-1
  链面缺失内建家族逐文件改走三面同判路径（boot `注册内建(空环境)` 47 名（阶段 41 时点，
  现行 60 名见第五节）vs
  宿主 3020 名（阶段 41 时点，现行 3025 名见第五节），`exp/log10/log2/ln/π/组合数/asin/acos/atan/atan2` 在链面
  恒「未定义变量」即函数不可调用）：指数 `2.718281828459045 ^ x`、对数换底
  `log(x)/log(10.0)`、反三角走二分、`atan2` 走 `象限角`、`组合数` 走本地
  `组合数按连乘`。41d-2 无定义读数（分母为 0、空表、越界、负方差）不再伪造
  `999.0`/`999999` 哨兵或 `0`，改诚实 None（15 形态三面同判）。41d-3 合法
  近似只补口径注、零语义改动。Track B 225 快照 --write/--check 逐字节零扰动
  （52 个资源语料全 both_ok_equal）；ast_vm_gap 快照重生成——节点 78 / 发射
  59 / 有意无码 19 / 指令码 36 结构不变，13 节点 `used_in` 随资源构造变动
  （ListLiteral 79→92、IndexExpr 77→85、SliceExpr 25→31、CodeBlock 104→110、
  IfExpr 96→101、BoolLit 45→49、FloatLit 88→90、LetBinding 103→105、
  StringLit 128→129；下调 UnaryOp 65→63、PathExpr 15→13、IfStmt 12→10、
  WhileStmt 10→9）。新锁档 test_resource_algorithm_true_phase41 247 项。
- **纯 Matha 装载器与终端链面默认（阶段 42）**：方向拍板——收口「终端与模块
  装载全由 Python 代劳」这条缺陷，本阶段只做装载器（自修复/生长面不在范围）、
  载体原语逐名补臂、链面直接设为终端默认。42a 新增 `matha/loader.matha`（装载
  这件事本身由 Matha 完成）：`名表` 22 条中文模块名→文件名（宿主 `_CN2FILE`
  逐条镜像）、三级解析序 `主路径`（`matha/` + 运行时引擎特例）→ `包路径`
  （`.matha_packages/<名>/manifest.json` 的 `entry`/`enabled`，无清单按 `<名>.matha`
  入口）→ `库路径`（`matha/library/` 递归）、`内声明`/`收集使用名`/`去机械`
  AST 形态工具（模块节点降一层取声明、`use` 依赖递归装载、`机械单元` 自测块
  不随装载执行）、`摊平`/`并内建`（模块函数并入 env 使跨模块裸名可达 + `内建`
  别名表并入 ns，镜像宿主「ns 缺名 → 内建表回退」一路）；`装载根` 由装配方
  注入仓库根绝对路径（宿主 `_matha_dir()` 首候选即 `src/..`，非 cwd——终端
  `换目录` 后装载仍命中同一批源）。装配壳 `src/matha_chain.py`（不在本体量口径）
  把 boot 链五模块 + 装载器编为 level-1 M3V 由宿主 VM 执行，被装载模块体经
  `解释器.执行语句` 以 level-2 Matha 数据闭包执行，并挂 `vm.domain_resolver`
  使 os 域插件符号可达。42b `matha/interp_matha.matha` + `matha/interp.matha`
  双镜像补 16 条载体原语逐名臂（执行命令/执行命令输入/管道输入/管道结束/输入行/
  列目录/建目录/删除路径/复制文件/改名/换目录/路径存在/执行Matha/调试Matha/
  升级包/检查包更新）与语言级 `错误` 名，`注册内建(空环境)` 固定面 47→59 名，
  二元柯里化载体（复制文件/改名/执行命令输入）入 内建元数 表使首参调用记偏应用；
  缺臂名如实报「未知内建函数」，无静默回落宿主实现。42c `src/matha_term.py`
  默认后端 `chain`（`MATHA_TERM_BACKEND=host` 保留对拍/排障入口，未知取值显式
  拒绝），后端装配在薄壳 `_startup()` 单点收口为「错误: …」+ 退出码 1（此前
  装配异常逃逸成 traceback）；`调试` 在链面显式拒绝（VM 编译链无逐节点轨迹
  能力），拒绝文案改指宿主后端（`src/mbc/vm.py` +1 行，本阶段口径内唯一改动）。
  链面成本实测：boot 装配 ~1.8s、装载 `终端执行器` ~20s、逐行 0.1–1.2s。新锁档
  test_selfhost_language_phase42 33 项。Track B 快照 225→226 = 双面一致 216 /
  differ 0 / both_err_equal 10 / both_err 0 / timeout 0（唯一变动为新语料
  `matha/loader.matha` 双面同判，其余 225 语料分类零漂移）+ `--check` 复现一致；
  ast_vm_gap 快照语料 230→231、21 节点 `used_in` 各 +1、节点 78 / 指令码 36 结构不变。
- **冻结 exe 进程映像与常驻监管（阶段 43）**：方向拍板——「先从进程映像开始，必须
  冻结 exe 而且必须是 Matha 的 exe，代理身份正式从 Python 脱离；监管者与解释器在冻结
  exe 基础上完全由 Matha 内核主导与实现，让 `matha.exe` 成为独立进程、非 python 脚本」，
  节奏「先完成冻结可执行批，再在其上完成常驻监管真化批」，验证「全量门禁 + 真 CMD
  subprocess e2e」。**43a-1** `matha.spec` 重写为单一 Analysis + 单一 EXE（旧两份同名
  Analysis 首份以 `src/repl.py` 为入口且 `exclude_binaries=True` 无 COLLECT，半成品
  必被第二份覆写），入口统一 CLI `src/matha_main.py`，语料 `matha/**/*.matha` +
  多语言前端源 + `src/domains/manifest.json` 按**仓库同构相对路径**入解包根（冻结态
  `Path(__file__).parent.parent` 即 `sys._MEIPASS`，目录形状必须等于仓库形状），域插件
  hiddenimports 由 manifest 派生（手抄 57 名漏 32 个域）。**43a-2** 冻结态路径口径：
  `src/matha_chain.py` 加 `_ASSET_ROOT`/`_EXE_DIR`、`_override_roots()`（`MATHA_HOME` →
  exe 同级）、`_roots()`/`_package_roots()` 逐条镜像宿主 `_matha_dir`/`_package_module_path`
  候选序并注入 boot 全局 `装载根们`/`装载包根们`，`_read` 六件一律同一语料根 + 缺失报
  候选全集；`matha/loader.matha` 的 `根()` 改「Matha 自己挑首个真含 `matha/` 的根」并尾追
  现取 `当前目录()`，`包路径` 改逐根扫且以 `包择` 产 `[终止?, 命中]` 判定帧区分宿主
  `return None`（enabled 假 → 整包跳过不再扫后续根）与 `continue`（本根无此包 → 续扫）两态，
  双镜像补第 17 条 `当前目录` 载体臂（链面固定面 59→**60** 名，42-② 退役）。**43b**
  Windows 入口真化：死引用 `src.matha_daemon` 清算、`matha server` 命令位 +
  `serve()` 单一启动面（`main()` 仅转发）、包装器优先冻结映像、构建入口产物平铺
  `dist/<名>.exe` 与 CI 同形。**43c** 被启动解释器 = Matha 自己：`运行脚本` 旧写法
  `shell_exec(f"python {path}")` 的两处真缺陷（PATH 裸名 `python` 而非 Matha 自身、
  `shell=True` 使路径成命令注入位）改 `_self_launcher("run")` + argv/shell=False。**43d**
  常驻监管真化：`常驻`/`重启预算` 两键入描述符，**策略全在纯 Matha 内核**
  （`matha/os/kernel.matha` 的 `启动`→`_派主进程`、`_收旧进程`、`调度` 轮尾 `_监督轮`
  重启判定〔运行中 ∧ 常驻 ∧ 就绪主进程数=0 ∧ 已退出数>0 ∧ ≤ 预算〕、`监督状态` 读数；
  停止态与人工 `停止进程` 不重启、重启不增步数），宿主桥 `src/os_runtime.py` 只提供
  `self_launcher()` argv 构造（冻结态 `argv[0]` 即 `matha.exe` 自身）与 `supervise()`
  墙钟薄壳（数轮/睡眠/回报，`轮数<=0` 不限轮，KeyboardInterrupt 不吞）。**43g** Windows
  安装/卸载家族产物落点口径收口。新锁档 `tests/test_frozen_entry_phase43.py` 89 项
  （43a 26 / 43b 6 / 43c 9 / 43d 15 / 43f 冻结+真 CMD 取证 10 / 43g 安装入口面 23）。
- **原生 OS 派生面（阶段 44）**：方向拍板——「Matha 与 Python 共存但不再调用 Python
  任何模块，直接调用系统 API……对标底层的 C 语言」，首批切片「原生 OS 派生面」，
  stage-0 「允许 Python 仅作种子，最终判定用无 Python 的 Matha 原生映像自证」。
  **44b-1** `src/mbc/native_process.py`：原生映像自派的机器码实现——`派生映像(cmd)`
  走 CreateProcessW（命令行 UTF-8→UTF-16 经 MultiByteToWideChar，中文路径与 CPython
  宽字符路径同行为；`shell=False` 语义，无命令注入位），`等候映像(pid)(ms)` /
  `映像退出码(pid)` / `终止映像(pid)` / `关闭映像(pid)` 走同一条 32 槽 × 40 字节
  内核句柄表。API 地址全部由引导期取得的 `k32_base` + `api_GetProcAddress` 惰性解析
  并写回槽位（只解析一次），运行路径不含任何 Python 模块、不含 CRT；PE64 产物
  **无导入表**（DataDirectory[1] RVA=0 Size=0），入口先走 PEB `gs:[0x60]` →
  `Ldr.InMemoryOrderModuleList` 取 kernel32 基址。「无定义读数」一律 null / −1，不用
  哨兵数冒充（pid 不在表中、pid<=0、实参是堆对象、STILL_ACTIVE(259)、API 解析失败）。
  **44b-2** 原生独占面收口：hi/vm 两面对五名**显式拒绝**（同文案独立写于两处，非静默
  降级、非返回假值）——核心主线红线「单线程确定、不驱动外部进程」，要进程映像必须
  走原生后端。**44b-3** 原生构建面真化：`matha 原生构建`（aliases `native-build`/`exe`）
  命令位产真实 PE64 机器码；`matha build` 旧「构建独立可执行文件」假广告（`matha_compile`
  从未产出可执行文件）改为产真实 `.mbc` 字节码工件并指向 `原生构建`。宿主桥
  `src/os_runtime.py` 补 `_终止载体`：纯 Matha 内核的 `收旧进程`/`停止进程` 只改簿记
  （它不持有 OS 句柄），桥在内核判定**落地之后**才动 OS——被拒绝的 `停止`/`卸载`
  不再杀掉仍在运行的载体。**44f** 进程树取证：CIM 查得派生子的 `ParentProcessId`
  就是原生映像 pid、父映像名是产物 `.exe` 本身而非 `python.exe`。
  新锁档 `tests/test_native_process_phase44.py` 37 项（44a 原生 e2e 10 / 44b CLI 6 /
  44c 三面拒绝 9 / 44d 桥面回收 6 / 44e 静态结构 5 / 44f 进程树取证 1）。
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
- **原生 OS 派生面（阶段 44）**：`src/mbc/native_process.py` 让 Matha 原生映像自己
  派生/等候/取退出码/终止/关闭子进程映像——五内建全为机器码，触达点只有 kernel32
  导出，地址在引导期 `k32_base` 之上经 `GetProcAddress` 惰性解析并缓存回槽位，
  运行路径零 Python、零 CRT、零 PE 导入表。这是「不借用任何宿主模块直接调用系统
  API」的第一片。口径边界：**只派生直接子进程，不建作业对象**，故 `cmd.exe /c …`
  外壳的孙进程不随 `终止映像` 回收（与 C 的裸 `TerminateProcess` 同语义）；句柄
  生命周期由调用方负责（`关闭映像` 之前一直可查，不自动回收）；表容量 32 槽，
  满槽诚实返回 −1。原生独占，宿主/VM 面对同一批名**显式拒绝**。
  验证：`tests/test_native_process_phase44.py`（含 CIM 进程树取证——子的
  `ParentProcessId` 即产物映像 pid）。
- **原生映像承载 Matha 工具链首片（阶段 45）**：阶段 44 让原生映像能自己派生进程，
  本阶段让它**装得下工具链**——`matha/lexer.matha` + `matha/stdlib.matha` +
  `matha/parser.matha` 三片一次编入**一份** PE64，token 流与 AST 流和宿主 hi/vm 两面
  **逐字同判**（`tests/test_native_selfhost_phase45.py` 45d-3/45d-4）。三件前置真化：
  **45a** arity 上限 8→15（disp8 位移可达上界；旧上限使词法器片整体编译失败，
  16 参定义与调用位同一常量、显式拒绝不静默错编）；**45b** 多模块链接
  （`compile_sources` 并源为单 `Program`——源序即顶层执行序，跨文件调用退化为同文件
  调用，产物仍是一份映像，单源路径逐字节零扰动）；**45c** 原生栈口径（操作数栈迁 `.bss`
  1MB + 全操作码静态净增量表求峰值 + 调用栈底守卫，越界给可捕获的诚实异常而非静默改写
  内存后退出码 0）。**45d-0** 顺带收口原生序比较：`<` 一族此前按 `.data` **地址序**判，
  `输出("b" > "a")` 直接反号，现走 `val_cmp` 深序比较。
  口径边界（诚实面）：**「能编」≠「已脱宿主」**——boot 全链仍有 latent 宿主注入名
  （阶段 45 登记 25 名，阶段 46 摸底后现行 **24** 名，见下条），它们中绝大多数是
  `装载根`/`执行命令`/`解析_JSON` 一类宿主 Python 载体注入的名，
  在原生运行期如实点名失败而非静默给假值；
  `use 标准库 { 名 }` 在原生面降级为一个 latent 的 `加载模块` 调用（链接期不报、运行期才炸），
  这正是 45b 多源链接的存在理由；原生错误
  文案取自发射器错误表，与宿主 Python 文案不同源（登记不修）。文档口径同阶段收口：
  链面固定注册面现值 **60 名**、宿主对位镜像固定面 44 名、宿主实例内建表 3025 名、
  `module 解释器` 两套源三套解析序，见第五节与 KNOWN_ISSUES 阶段 45 口径收口条。
- **boot 链 latent 名逐项归因 + 一臂死函数真修（阶段 46-1）**：45-① 只登记了「有 25 个 latent
  名」，本切片把每个名**归因到载体归属**，判据是机器可跑的：`build_boot_vm().vm.globals` 有
  宿主 Python 载体（A 类 **20** 名）／`PluginResolver.known_symbols()` 惰性物化（B 类 **4** 名，
  os 域）／**谁都没有**（C 类 **1** 名）。A/B 是 46a 的原生载体工作量，C 不是「脱宿主缺口」而是
  语料自身缺陷——`matha/stdlib.matha` 的 `to_upper` 在 `let rec _map(i, acc)` 的 `in` 体里把
  形参名当自由名读（`in _map(0, acc)`），故 `acc` 必然未绑定，`to_upper` 是一臂**任何调用都失败**
  的死函数（修前 hi/vm/链面三面同判 `未定义变量 'acc'`）。改形与 `to_lower` 种子对称
  （`in _map(0, "")`）：修后链面经产品分派体 `应用内建实` 给 'AB' / 'HELLO, WORLD! 123' / '' /
  'ABC_é中'，同一语料编进真原生 PE64 逐字同判（`tests/test_native_selfhost_phase46.py` 46c），
  把旧行回注的反控给 rc≠0 + stderr「未定义变量」（46d）——收益来自这一行而非装载环境。
  latent 名集 25→**24**（总读位 33→32，C 类归零）。两条**判据锁**防止口径被读歪：46e 要求每个
  latent 名都能在宿主 globals 或插件符号表里找到载体（找不到即红，即「语料自由名冒充宿主缺口」
  不可再现）；46h 锁「24 只是下界」——boot 链 831 个 LOAD_GLOBAL 名与编译期拒绝集合
  `native._UNRESOLVED_GLOBALS` 的交集只剩已按静态对象发射的 `None`/`_empty_dict`，说明 latent
  名根本不在拒绝集合里（链接期不报、运行期才炸）；46j 再把四份文档里写的名数/读位数锚点交给
  `_latent_reads` 的实测值拼出（「25 是时点读数」必须带归因指针），文档与机器脱钩即红。
  `to_upper` 自身属链面独有注册名，`src/**.py` 全仓零载体（41-① 表差族新成员，登记不修）。
- **判定面换形：脱 Python 前先把裁判换掉（阶段 46c）**：三面正确性判据（Track B
  boot↔host、golden vm↔interp、native_parity host↔exe）的裁判都是 Python，退役那一刻
  正确性判据整面消失、只剩「没崩」——阶段 41 清过的假成功温床正是这种状态，所以 46c 是
  **退役的前置**门禁。交付三条形态（锁档 `tests/test_judgment_face_phase46c.py` 19 项，
  Python 仅作构建种子、不作判定）：**① 自举双跑**在编译面已经成立——`matha/lexer.matha` +
  `stdlib.matha` + `parser.matha` + `compiler_matha.matha` 四片链进原生 PE64 后
  `编译器.编译` 在映像里跑起来了，两个**独立构建**的映像（四片链接 vs 四片文本拼接，
  产物逐字节相同）各在自己的进程里编译同一批源，产出的 64 行字节码读数
  （常量池／主码／函数表／模块名）逐字相同，同一映像内重复编译同判；构建面另有三组源各两次
  独立发射逐字节相同、同一映像三跑 stdout 逐字相同。**② 手算／规范对拍**：词法器 37 行 token 流、
  语法器 7 行 AST 流、编译面 64 行字节码逐行写死在锁档，依据指到 Matha 源行；反控两批
  （词法面 46c26：整表顺序置换／`关键字|Int`→`标识符|Int`／`大于等于`→`大于`；编译面 46c38：
  操作码编号／折叠结果退回左操作数／常量池顺序置换）证明字面量承重。**③ 差分面降为 dev-only**：
  `scripts/selfhost_matrix.AUTHORITY = "dev-only-differential"` + 产品面 `src/**` 零 import
  判定工具（有锁）。同批把差分面自身的**功率**换形：旧快照 `equal=true` 里「两侧零输出」
  与「N 行逐字相同」同形（旧形只在有输出时写 `n_outs`，空输出表现为缺键＝与「没测」不可分），
  现无条件记录并按其分层进 `summary.power`——快照现值 226 语料，其中
  **双面一致 216 = 有读数 71 + 空对空 145**，全量比对读数 270 行；此前被反复当作收益证据的 52 条 `matha/resource/**`
  语料**全为 silent**（资源库真证据在阶段 41 手算锁）。七分类对 files 的闭合与条目分类
  零漂移，`--check` 一致，快照改动纯增量（新增 `power` 内嵌节不参与对 files 求和，
  `test_selfhost_matrix_phase29`／`test_selfhost_language_phase39` 两处键形锁随之改）。
  边界如实登记：boot **解释器面**（`interp_matha`/`loader`）链进映像实测在第一条驱动语句前
  以 `不可调用的值` 退出（rc=0x1），故「映像自己编译 + 自己运行」的全链双跑仍待 46a/46b。
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
| `tests/` | 197 个测试文件（全量见最近一次 `make check`） |
| `kernel_purity` | 白名单 + 核心无逃逸模块 + 插件不得碰 VM 私有面 |
| `ast_vm_gap` | 78 个 AST 节点、59 发射 / 19 有意无码 / **0 不认识**（ListComp 已由 VM 编译为下标循环 + `append` 累加，不再静默返空）、**0 阻塞缺口**；指令码 36/36/36 |
| `golden` | 39 例 vm ↔ interp 逐字节；`--native` 追加真 exe 对拍（已知未实现项列在 `golden_tests/manifest.json` 的 `native_known_gaps`，当前为 0） |
| `dep_audit` | 违规 0 条、插件越界 0 条 |
| `matha_stdlib_symbolic` | 阶段 4 逐位对拍 + 偏差双向锁定 + 缺口显式失败（107 项） |

```bash
make check          # 含 vm↔native 机器码对拍
make check-lite     # 本机无 nasm/link 时用
```

**链面注册面现行口径**（历史条目里的计数按此对齐，勿读作现值）：boot 链固定注册面 =
`matha/interp_matha.matha` 的 `注册内建(空环境)` 逐条 **60 名**（阶段 41 时点 47 → 42b 后 59
→ 43a-2 后 60；运行时 `MathaChain().env` 同数，phase42 `test_42b_carriers_registered_in_chain_surface`
锁死），对照宿主 `Interpreter` 实例内建表 **3025 名**（阶段 41 时点 3020 → 阶段 44 映像族
显式拒绝内建 +5，`src/interp.py:614 PROCESS_IMAGE_BUILTINS`）与原生面 `NATIVE_BUILTINS`
132 名（`src/mbc/native.py`，另计）。
`matha/interp.matha` 是**宿主对位镜像**，其 `注册内建` 静态只绑 44 名、余由 28d 运行期
`解释器插口` 补——两个固定面**不等集**：交集 43 名，boot 独有 17 名（`输出`/`print`/`int`/`log`
等 stdlib 家族臂），镜像独有 1 名（`原地设置`）。「双镜像」指 17 条载体原语（含 43a-2 的
`当前目录`）+ `错误` 逐名臂齐全，**不是**固定面等集，
也**不是**整个 `module 解释器` 等集（两套源 106/139 名、交集 53 名；三套解析序见
`src/matha_chain.py:37` / `src/interp.py:946` + `scripts/selfhost_matrix.py:499` +
`matha/loader.matha:23` / `src/os_runtime.py:58-60`）。逐条取证与两条登记不修（产品链
`装载("解释器")` 的 struct 工厂缺口）见 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) 阶段 45 口径收口条。

## 六、兼容承诺（未被重构破坏）

- 符号体系不删：`？ #： 【*/ */ @： >> []`（语句位单元素 `[x]` 是**打印括号**，
  列表字面量请用两元素形式或 `包(x)`，详见 [`ast_vm_gap.md`](ast_vm_gap.md) 第九节）。
- `matha/**/*.matha`（182 个）、`examples/` 全部保留；
  `matha/library|knowledge|resource/` 属标准库/扩展包，不内置内核。
- 88 个领域插件全部保留为插件，未加载时不产生 import 成本。
