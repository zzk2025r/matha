# Matha

自举式领域专用语言与独立可执行编程语言系统。

## 系统状态（实测，非自评）

下表每个数字都由 `python scripts/repo_facts.py` 从仓库现场数出来，
`tests/test_doc_facts.py` 会核对文档与代码是否漂移（漂移即红）。

- **版本：** v4.6.0（唯一版本源 [`src/__version__.py`](src/__version__.py)）
- **领域插件：** 88（`src/domains/` 共 90 个 `.py`，其中 `__init__.py` / `registry.py` 不是插件）
- **内核外工具插件：** 7（`src/plugins/`）
- **黄金用例：** 39（`golden_tests/cases/`，vm ↔ interp ↔ native 逐字节）
- **`.matha` 语料：** 183（历史遗留的旧写法已全部改写为合法 Matha，当前 0 个属语法层遗留，见 `docs/ast_vm_gap.md`）
- **测试文件：** 191（`tests/`）
- **核心安装第三方依赖：** 0（`pyproject.toml` `dependencies = []`）
- **通过率：** 见下一节「质量门禁」，唯一数字来自 `make check`
- **已知未达成项：** 如实列在 [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md)

**阶段结论（本轮重构）：** 内核纯净化 + 插件化重构完成 —— 核心安装零第三方依赖
（`dependencies = []`，sympy/numpy 已降为 `optional-dependencies.accelerated`），
第三方重后端只在插件函数体内按需 `import`（样板：`src/domains/symbolic_calculus.py`，
配套命名卫生门禁：插件不得导出裸单字母符号、也不得与 `.matha` 顶层声明同名）；
核心测试 100% 通过（唯一口径见下方「质量门禁」，数字随用例增减以 `make check` 实时输出为准）。

---

## 快速开始

### 方式 1：独立可执行文件（本地自建，仓库不预构建发行版）

```bash
# 需要 Python 3.10+ 与 PyInstaller；产物输出到 dist/（不随仓库分发）
python scripts/build_exe.py --matha       # 产出 dist/matha/matha.exe
python scripts/build_exe.py --matha-cc    # 产出 dist/matha-cc/matha-cc.exe

# 启动交互式 REPL
dist/matha/matha.exe

# 计算表达式
dist/matha/matha.exe eval "sin(3.14)"

# 运行 Matha 源文件
dist/matha/matha.exe run demo.matha

# 编译到 LLVM / 可执行文件
dist/matha-cc/matha-cc.exe compile demo.matha
```

### 方式 2：Python 包安装

```bash
# 核心零依赖：不装任何第三方包也能跑主执行链
pip install -e .

# 可选扩展（按需，不影响内核）
pip install -e ".[accelerated]"   # sympy 兼容后端
pip install -e ".[performance]"   # numpy/scipy/numba 数值后端

# 使用
matha                          # 启动 REPL
matha eval "sin(pi)"           # 计算表达式
matha run demo.matha           # 运行源文件
python -m src.compiler.matha_cc_cli compile demo.matha   # 编译器工具链
```

> 注：pip 安装只注册 `matha` 入口点；`matha-cc` 请以模块方式调用
> （`python -m src.compiler.matha_cc_cli`），或用 `matha-cc.spec` 自建独立可执行文件。

### 方式 3：离线部署（无网络环境）

```bash
# 在有网络机器上打包
python scripts/package_offline.py

# 拷贝到离线机器
# 运行部署
python deploy_offline.py

# 验证
python scripts/verify_offline.py
```

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **JIT 编译** | 函数级即时编译 + 自动 Memoization |
| **自动缓存优化** | LRU 缓存 + 尾递归转换（Fibonacci 19526x 加速） |
| **多语言代码生成** | C/Python/Rust/Go/Java/C++/JS/Matha 八语言转译 |
| **LSP 语言服务器** | 补全/悬停/定义跳转/诊断 |
| **类型系统** | 依赖类型/泛型/子类型/精炼类型 |
| **CSP 并发** | 进程级并发绕过 Python GIL |
| **离线存储** | SQLite 持久化 + 同步管理 |
| **88 领域插件** | 物理/工程/AI/金融/生物/化学等；按需显式加载，不加载零 import 成本 |

---

## 命令行工具

### matha（REPL 入口）
```bash
matha                          # 启动交互式 REPL
matha eval "sin(pi)"           # 计算单行表达式
matha run demo.matha           # 运行源文件
matha --version                # 显示版本
matha --debug                  # 调试模式
```

### matha-cc（编译器工具链，需自建 exe 或 `python -m src.compiler.matha_cc_cli`）
```bash
matha-cc compile demo.matha            # 编译（LLVM 工具链在位时产机器码）
matha-cc run demo.matha                # 编译并运行
matha-cc llvm demo.matha -o out.ll     # 生成 LLVM IR
matha-cc optimize demo.matha -O2       # 优化编译
matha-cc info                          # 工具链信息
```

### matha 终端（CMD 模板子集；别名 `term`）
```bash
matha 终端                              # 交互式 REPL（提示符 Matha>）
matha 终端 -c "回显 hi"                 # 单命令执行后退出（退出码 0/1 如实）
matha 终端 script.msh                   # 批处理：逐行执行，单行错误继续（CMD 风格）
python -m src.matha_term                # 独立入口（同一三种形态）
```

终端的全部命令逻辑（词法/句法/分发/执行/透传决策）为纯 Matha 模块
（`matha/term_lexer` / `term_parser` / `term_engine`），跑在 Matha 自身解释器/VM
上；Python 层只保留 IO 原语与进程入口。CMD 模板命令集（目录/换目录/显示文件/
复制/删除/建目录/改名/回显/清屏/帮助/退出，英文别名大小写不敏感）+ Matha 代码
命令（运行/加载/编写/调试）+ CMD 式透传（未知命令交系统 shell 真执行，失败如实
显示退出码）。扩展与升级（阶段 12e）：`注册命令/注销命令` 持久化当前目录
`matha_term_registry.txt`（注册名不可覆盖内建；参数含引号/反斜杠显式拒绝）；
REPL 启动自动执行当前目录 `matha_term_extensions.msh`（其中 `退出` 不结束会话）。
管道补全（阶段 13）：`左段 | 右段` 为 CMD 式 stdin 注入——左段显示行 → 右段
`输入行()` / 透传 stdin（新增 查找/排序 管道消费者，注册扩展命令同享）；重定向
`> 截断 / >> 追加` 将末段显示行落盘（CMD 式静默不回显；退出标志跳过落盘，段内
错误不落盘）；`升级 [包名]` 无参 = 本地检查，带名 = 真安装（真盘重写
`.matha_packages/<包>/manifest.json` 并复核版本；本地目录升级不联网；
`升级 解释器` 显式拒绝）。

### matha 桌面（纯 Matha TUI 桌面，阶段 27）
```bash
matha 桌面                              # 终端内一次性确定性 TUI（缺省键序 d s p d d d d t u q）
matha 桌面 j s d d q                    # 自定义键序（至多 16 键；别名 desktop）
python -m src.matha_term -c "桌面"       # 单命令形态（同一入口）
```

桌面本体为纯 Matha 模块（`matha/os/desktop.matha`，`use 标准库 { len | str }` +
`use 内核`），演示桌面预装载三单元（时钟/回声/便签）；按键集 `j/k` 焦点环绕、
`s` 启动、`t` 停止、`u` 卸载、`p` 进程、`d` 步进、`q` 退出，全部动作经 OS 内核
（`matha/os/kernel.matha`，单元生命周期/进程表/服务注册表 + 兼容协商）协商面，
拒绝如实回传消息行。终端命令为一次性确定性脚本；配套 `src/os_runtime.py`
单元管理器桥（app/包/域插件/终端命令/服务五形态统一 + 外部单元）与
`matha/library/{os,desktop,compat}` 资源库三分支（资源索引 21→28 条，
阶段 28 新增 `os/端口协议`）。

### matha ext（统一扩展管理，阶段 23）
```bash
matha ext list                              # 四面扩展一览（领域/特性/扩展包/终端）
matha ext enable  domain thermo             # 启用一个扩展（domain|feature|terminal）
matha ext disable domain thermo             # 停用一个扩展（下次 run/eval/repl 生效）
matha ext install 目录/                     # 安装用户 .matha 扩展包（真复制进 .matha_packages/）
matha ext install demo.msh                  # 注册终端扩展（REPL 自启动执行）
matha ext install arithmetic                # 按内置注册表安装
matha ext upgrade  包名                     # 升级一个扩展包（本地源重装 / 注册表升级）
```

四面同一协议（版本/启停/来源）：领域插件启停走 `PluginResolver`（停用 =
`unregister`，符号真实不可用；启用 = 清单 `reload` 回位）；特性开关即
`matha features` 五开关（`MBC_PASSES` 为编译器框架字节码遍 opt-in，
默认关，见下）；扩展包启停写在包自己的 `manifest.json "enabled"`
（`use 包名` 内核回退面如实尊重）；终端扩展条目持久化在
`.matha/extensions.json`。安装的用户扩展包直接 `use 包名` 加载。

### matha app（应用中心/商店，阶段 25）

自生凭据面：商店自签发 HMAC 令牌（首发随机 secret 落
`.matha/store/secret.key`，令牌三段式 `主体.到期戳.HMAC`，发布需令牌、
安装开放）；引擎是纯 Matha（`matha/store_engine.matha`：HTTP 请求解析/
路由/索引落盘），Python 只出 socket 驱动（`src/app_cli.py`）。

```bash
matha app serve --port 8080                  # 启动应用中心（默认 127.0.0.1:8787）
matha app token --subject 甲                 # 签发发布令牌（--ttl 秒，默认 3600）
matha app publish 应用 --file 应用.matha      # 发布（本地自动取令牌；远程须 --token）
matha app upgrade 应用 --file v2.matha       # 升级（应用不存在诚实拒绝）
matha app list                               # 全部应用（码点升序）
matha app search 关键词                       # 名称子串过滤
matha app install 应用 [--version 1.0]       # 安装到 .matha/apps/<应用>/<入口>
matha app import-release 组/仓库 --tag 发行标签 --asset 应用.matha
                                             # 从 GitHub Release 附件导入（CI 闭环）
# 远程操作加 --store http://127.0.0.1:8080
```

CI→商店闭环（阶段 25e）：CI 只用 actions 自动注入的 `GITHUB_TOKEN`
（PyPI/Marketplace/钉钉等外部凭据面已整体删除，发行物一律 Release 附件），
附件经 `matha app import-release` 导入本地应用中心；卫生锁
`tests/test_ci_hygiene_phase25.py` 钉住 secrets 白名单 = {GITHUB_TOKEN}。

### matha sys（设备/任务管理器，阶段 26）

只读盘点五节：硬件与状况 / Matha 自身 / 插件加载与使用 / 软件清单 /
模块清单（与领域符号 `硬件_信息` / `自身_状况` / `软件_清单` / `模块_清单` /
`插件_冲突` 共用同一信息层 `src/system_inventory.py`，输出 JSON）。

```bash
matha sys hardware                # 平台/CPU/内存/GPU(nvidia-smi)/单片机工具链（只读探测）
matha sys self                    # 版本/插件汇总/运行时后端/features/扩展状态/.matha 盘点/进程内存
matha sys plugins                 # 插件汇总（89 清单）/使用（物化时刻）/冲突（多属主符号）
matha sys software                # .matha/apps 安装应用 + .matha_packages 包
matha sys modules                 # 自定义运算符/终端注册命令/优化遍/插件使用
matha sys all                     # 五节一次盘点
# 缺失工具（psutil/nvidia-smi/烧录工具链）诚实降级为「不可得」，不伪装成功
```

插件兼容面（阶段 26c）：清单声明 `requires` 依赖的插件缺失则注册诚实拒绝
（`注册被拒` 可见、ERROR 诊断在案）；依赖事后被注销（`matha ext disable`）
则 `sys plugins` 的 `依赖缺失` 如实报告，不自动注销；多属主符号在 `冲突`
节如实列出（取值语义维持清单最后声明者覆盖）。

### 自定义扩展插口（五动作端口协议，阶段 28）

工具链六层（词法语法 / 解释器宿主 / 解释器自举 / 编译器 / 虚拟机 /
内核特性）开放同一套五动作插口：注册 / 启停 / 升级 / 回滚 / 依赖协商。
宿主适配层 `src/extension_port.py`（`make_port(层名, 运行时对象)`），
纯 Matha 协议模块 `matha/library/os/端口协议.matha`（`use os/端口协议`）
定义同一状态形状（`{"层", "条目", "审计"}`，条目六槽
`[名, 版本, 启用, 实现, 历史, 依赖名们]`）与同文案审计行；五动作返回
`(结果, 端口, 原因)`，诚实拒绝时状态原样不动。`os_runtime` 把六层装载为
内核服务单元（`工具链-<层名>`，装载=注册、启动/停止=启停）。

```python
from src.extension_port import make_port
port = make_port("parser")          # 词法语法层：自定义运算符注册表
port.register("⊗", 1, (6, "left", "双加"))
port.upgrade("⊗", 2, (7, "right", "双加"))   # 升级（旧版压栈）
port.rollback("⊗")                            # 回滚到上一版
```

自举重建判据（阶段 28 拍板①）：Matha 自举解析器（lexer/stdlib/parser.matha
编译跑在 VM）与宿主解析器全语料 AST 逐字段一致（`test_parser_parity_phase28`
）；自举编译器与宿主编译器全语料 `_canon` 字节码逐位一致
（`test_compiler_parity_phase28`）；VM 执行面维持阶段 27 stage-4 闭环锁。

执行面双轨判据（阶段 29）：A 轨 pytest 轻中档锁（自举语言/执行/矩阵/公式
四档入常规门禁）；B 轨 `scripts/selfhost_matrix.py` 全语料 sweep（多进程
+ boot 复用）+ 快照 `docs/selfhost_matrix.json` `--check` 重档通道。

执行面收口（阶段 30）：自举链执行面五片真化——执行分派路由（读取块/设值/
跳出/继续/返回/结构体/枚举/属性）、use 跨模块装载（模块名表扩 + 非函数符号
合并）、双面错误文案对齐（除零/取模/整除/不可调用/类型名）、语法缺口真化
（列表推导/类型索引/sqrt 一元/stdlib_symbols）+ B 轨驱动器级域符号注入
（宿主内建真实现经 28d register_builtin 端口入 boot 面，多参经柯里化适配；
链判据关键名 `type_of` 保留 VM 面——宿主同名符号不覆盖链分派内建）。快照
225：双面一致 203 / 诚实 differ 3（对象身份/未定种子输出如实分歧）/ boot_err
0（29d 61→清零）/ both_err 17（错误语料双端如实报错）/ timeout 2（interp/
stdlib_symbols 重档自检 >120s 双面未完成）。

语言完备与判定面收敛（阶段 31）：func 定义 `->` 返回类型可选（29-⑧ 退役）；
双 for 推导 `[e for a in xs for b in ys if c...]` 双端三面（宿主
`ListComp.gens` + MBC 嵌套循环发射零新 opcode；boot 编译器推导发射诚实
未支持登记）；语句位括号链块体位收集（顶层双面诚实拒绝维持）；f[0]
不可调用守卫三面同文案 + 字典迭代元组对齐（boot 面此前静默空跑假成功
清除）；boot 切片表达式求值真化（30 登记④退役，12 形态三面同判）；
sweep 装配镜像（golden manifest preload 双轨同源——golden 36/39
both_err→equal）+ warmup barrier + 单文件预算 120→600s。快照 225：
双面一致 206 / 诚实 differ 3 / boot_err 0 / both_err 13 / timeout 3
（37/38/interp.matha 双面真跑 >600s 同判；interp.matha host 面单跑
1.2s，共享预算 boot 先耗尽——如实归因见 KNOWN_ISSUES 31）。

语言收敛与元组真化（阶段 32）：五片语言收敛 + ② 元组真化中心工程（拍板
「以维持登记为基础，以切片真化的方式推进，拆分可回滚受控切片逐个验证」）。
VM 字典迭代四面归一（宿主编译器 for/推导三发射位统一经 `_迭代源` 内建 +
vm.matha 镜像 + native iter_source，dict → ('k',v) 对——31-① 退役）+
BUILD_SLICE 不可切片守卫三面同文案；hi 面 ChainStmt 块尾链真化（31-⑤
退役）；boot 编译器推导发射真化（单/多 for+if——31-⑥ 退役）；mb 面 str
通用化（Bool/null/容器/函数渲染 + 自举闭包守卫——28-⑨ 退役）；let rec
互相递归三面贯穿（hi 预注册占位 + VM 预发盒 + boot 待填盒镜像——29-②
退役）。② 元组真化受控切片：S1 BUILD_TUPLE 运行时指令面（0x65=101，
三执行体直注执行、零发射零行为变化）；S2 发射面切换（宿主+boot 编译器
元组字面量 → BUILD_TUPLE——31-②「元组按列表处理」退役；native 消费面
语料回归；stdlib/vm.matha str 元组渲染臂；`-` 容器守卫四面同文案）。
自举编译器同名函数重定义出口去重（宿主 dict 保首现序取末值语义镜像，
拼接编译函数表千级规模出口一次性双遍完成）。Track B 快照 225：双面一致
206 / 诚实 differ 3 / boot_err 0 / both_err 13 / timeout 3 维持，--check
两跑一致。

mb 面分歧收敛（阶段 33）：六项 mb↔宿主语义/文案分歧三面（vm/hi/mb）+
VM² 收口。单元素尾逗号 `(1,)` boot 面静默吞成分组 → 诚实拒绝对齐宿主
（「期望表达式 (got PUNCT_RPAREN ')')」——32 登记①退役）；mb 比较族
九臂 `=`/`==`/`!=`/`<`/`>`/`<=`/`>=` 与 `not` 返 真/假 Bool（此前
1.0/0.0 浮点——32 登记④退役）；`in` 成员判断四面真化（vm `_op_in`
容器守卫 + native 容器守卫可捕获 + mb `_成员判断` + VM² 镜像；
List/Tuple/Dict/Str 命中/未中 + 非容器右侧「in 右侧需为序列/集合/字典，
实际 int」四面同文案——32 登记③退役；native 旧锁
test_in_non_container_is_false 按 33c 真化退役惯例改锁诚实报错）；mb
条件路由真值归一（求值 if/语句 if/while 经 真值 helper——空容器/零/
null falsy，32 登记⑦退役）；hi 面 if 无 else 条件假 → null
（src/interp.py IfExpr/IfStmt else 缺失臂，此前崩 NoneType）；mb
type_of/_to_tuple 注册真化（32 登记⑤退役）+ sum 累加器 0 起
（sum([])=0 Int——32 登记⑥退役）。收官探针踩中顺手真修（33h）：
slice 内建字符串臂真化——mb 面 应用内建实 slice 臂此前无条件走
list_slice，字符串实参产出字符列表（split 块变 ['a'] 形）；33b 比较族
提速后 golden 38 语料 600s 预算内首次真跑完成、timeout→differ 漂移
显形此根因。String 实参改走 31f `_切片值` 字符串臂（负回绕/端钳
Python 语义）、List 维持 list_slice、Tuple/其他诚实报错
「slice() 需要字符串或列表」（宿主=SPEC 同文案）。Track B 快照 225
重生成（--check 两跑一致）：双面一致 209 / 诚实 differ 3
（08_auto_optimize/data_pipeline/neural_network 对象身份/未定种子如实
分歧）/ boot_err 0 / both_err 13 / timeout 3→0 清零
（37_basics_sorted/38_basics_join_split/interp.matha 三档 33b 提速后
600s 预算内真跑完成；38 语料新显形 differ 为 33h slice 字符串臂根因，
修复归等）。

语言面继续收敛（阶段 34）：六项登记分歧全族真化（33-①②③④ + 28-⑦ +
32-⑨⑪ 退役）。尾逗号全族：33a 单元素机制扩展到多元素 `(1, 2,)` 与
调用位 `f(1, 2,)`——boot 面改发宿主精确文案「期望表达式
(got PUNCT_RPAREN ')')」（解析括号消解逗号分支全族守卫）；列表尾逗号
`[1, 2,]` 三面合法。语句位 if `[` 路由：宿主 `_parse_if`/`_parse_while`
条件位加 `_in_cond_value` 值语境旗标（27f 同款先例）——`if [1] { … }`
条件析为列表字面量而非输出命令（vm 面此前漏出条件值 `outs=[1,'x']`
vs hi/mb `['x']` 三面分歧退役；boot 面既有正确零改动）。`in` 左侧
四面同文案：字符串容器+非字符串左侧统一 boot 中文文案「in 左侧需为
字符串，实际 int/list/NoneType」（vm `_op_in` + hi interp.py 二元运算
in 臂 + native 非零退出 stderr 同文案可捕获 + VM² interp.matha 补
`_类型名` 小写面镜像——33-③ 退役）。slice 元组 vm 收敛对齐宿主：
vm `_builtin_slice` 容器守卫 + native `fn:slice` 容器守卫（仅
str/list 透传，其余诚实报错「slice() 需要字符串或列表」——33-④
退役；下标切片共用路径不受影响）。boot for `(k, v)` 多变量目标真化：
boot parser.matha 括号解构目标（"变量" String=单变量 | List=名单）+
interp_matha `_解构绑定`（宿主 `_exec_for_stmt` 镜像，长度不匹配
「解构失败：期望 N 个元素，实际 <类型名>」同文案）——列表对/元组对/
字典源三面+VM² 同判（32-⑨ 退役）；boot 编译器发射面 List 目标诚实
拒绝「boot 编译器 for 解构目标暂未支持」（UNPACK_SEQ 自举镜像未做，
登记）。hi 面 func 值求值真化：块尾 func 定义块值 → None（src/
interp.py _eval 补 FuncDef 臂，vm 面同判——32-⑪ 退役；mb 面表达式位
if 无 then 解析拒绝与 func 体块尾 mb 块值 '<function>' 维持登记）。
附带发现登记：boot 字典字面量裸键 `{a: 1}` 析为变量引用 vs hi 面字符串
键（引号键三面一致）；vm 面编译路径 UNPACK_SEQ 长度不匹配宽松补 null
（解释面 hi/mb 诚实报错——编译面 vs 解释面解构语义分歧）。

自举解构贯穿（阶段 35）：两项登记分歧同根退役（34-①④）。35a S1
UNPACK_SEQ 长度守卫四执行体真化：vm 面 0x57 处理器严格化（List/Tuple
且长度精确匹配逐位绑定，否则「解构失败：期望 N 个元素，实际 <类型名>」，
Closure 映射 "function"——34-④ 宽松补 null 退役）+ native
`_emit_unpack_seq` 严格化重写（err 池串同文案，try/catch 可捕获）+
vm.matha `_解构类型名`（"__闭包__" 哨兵镜像）+ hi interp.py let 元组
绑定守卫（语句位+表达式位）。35b S2 boot 编译器 for 解构发射真化：
compiler_matha `_分配循环变量` 收窄单变量 + `_分配循环变量们`/
`_分配循环位置们` 名单归一逐名折叠 + `_for循环码` UNPACK_SEQ 发射 +
`_存解构逆序` 逆序存储（宿主 _emit_for_stmt 镜像，正序压栈存储逆序）
——34-①「boot 编译器 for 解构目标暂未支持」退役；单变量目标零字节码
变化回归；五语料 stage2↔stage3 逐位一致 + M3V 运行面真跑（字典对/
三变量/局部函数/元组对）。登记不修：mb 表达式位 let 元组绑定 honest
reject「未知表达式类型: let元组绑定」；m3v 编译态 try/catch 不捕获
运行期错误（全族，既有边界——vm.matha 解释循环无异常帧机制，登记锁
防漂移）。

mb/boot 面收口批（阶段 36）：四项登记分歧真化（35-① + 34-②③⑤ 退役）。
36a 表达式位花括号 if：boot parser.matha 解析if表达式补花括号分支（宿主
_parse_if_expr_impl 语句形式分支同构，否则 仅 否则 关键字、无则 假分支
=null——33d 同形）+ interp.matha 求值 程序 臂块执行取尾值——`let x =
if 1 { 2 } in …` 六形态三面同判、输出尾块值 [5, 6]（34-② 退役）。36b
mb 面块尾 func 定义块值真化：interp_matha 执行语句/执行声明 函数定义臂
(closure, env2) → (null, env2)（函数仍入 env，仅值面不回传，宿主 FuncDef
执行返 None 同构）+ interp.matha 双臂镜像——`{ func f() = 1 }` 块值
[None] 三面同判、blk_used `f()` [1] 维持（34-③ 退役）。36c boot 字典
裸键真化：interp_matha/interp.matha 求值字典 `_字典键` helper（"变量"
键析为字符串键名，其余求值）——`{a: 1}` ≡ `{"a": 1}` 四面同判（34-⑤
退役）。36d mb 表达式位 let 元组绑定真化：interp_matha 求值let元组/
绑定求值let元组 + `_解构绑定元组`（闭包标记 ["__closure__",参数,体,env]
跳参绑定镜像宿主，懒三元防 eager and/or 陷阱；错误「解构失败：期望 N 个
元素，实际 <类型名>」四面同文案）三臂路由（求值/执行语句/执行声明）——
`let (a, b) = [1, 2] in a + b` 三面 [3]（35-① 退役）。附带发现登记：
vm 面编译路径字典字面量非字符串键（compiler `_literal_key` IntegerLit
→ "2" 字符串化 + INDEX_GET 缺键 null——`d[2]` vm null vs hi/mb "v"；
`d["2"]` vm 命中）；boot 面块尾 Binding `{ let x = 5 }` 块值 mb [5] vs
vm/hi [None]（34-③ 同族 Binding 尾未真化）。

语言面清尾批（阶段 37）：五项登记分歧退役（32-② 31-③ 协议一致锁 +
32-⑩ 36-① 36-② 真化）+ 同族顺手真修。37a 陈旧登记退役：32-② 空括号
() 三面早已统一零参调用约定（() 降糖 IntegerLit(0)，f() = f(0)，表达式
位 () 即 0）与 31-③ 非容器切片三面早已统一 MathaRuntimeError 同文案
「切片操作不支持: int[1:2]」——协议一致锁防漂移。37b 块尾 Binding 值
模型收尾：interp_matha 绑定求值let 无体臂 (v, env)→(null, env) +
interp.matha 同形 + 表达式位块（求值程序/求值 程序 臂）尾值 `_块尾值`
映射（绑定/let绑定/let元组绑定尾不回传值；程序位顶层 run_ast → 执行
语句保持「程序值 = 尾表达式值」约定不映射——phase8pre gapfix 程序值
锁同源）——`{ let x = 5 }` 等四形态三面 + VM²
同判 [None]，有体 let 尾与裸赋值尾同族顺手真修（36-② 退役）。37c 链式
let rec 互递归真化：interp.py 表达式位 LetBinding 链头收集 body 链
rec 名建注册表压栈（`_rec_chain`）逐名预绑占位、成员复用未填占位
（_ref 未填守卫，32e 勘误保留）+ 块/程序入口预注册沿 body 链整链
（`_preregister_rec_chain`）+ interp_matha/interp.matha 预绑链占位镜像
——`let rec a = … b(n-1) … in let rec b = … a(n-1) …` 三面 + VM² 同判
[0]（32-⑩ 退役）。37d 字典自然键真化：compiler.py `_literal_key`
IntegerLit/FloatLit/BoolLit 原值入常量池（此前 int 键字符串化致 d[2]
vm null）+ parser.matha `花括号种类` 数字/布尔首 token 冒号前瞻 → 字典
（此前 mb/VM² 误析集合）——int/float/bool/str 键 + d["2"] 反向 null
三面 + VM² 同判（36-① 退役）。附带发现登记：vm/hi 输出尾块值 host
内部分歧（编译面语句尾 PUSH_NULL vs 解释面输出通道规则）+ mb 面集合
构造求值未知表达式类型 + 37c 嵌套链同名成员 env 槽覆写边界。

m3v 异常帧机制（阶段 38）：35-② 真化——编译态 try/catch 捕获运行期错误。
vm.matha 捕获闭包/捕获内建两个分派位用 Matha 级 调用捕获 单点包裹（实参
双嵌套 [[…]] 配对 invoke_value 的 fn(*args) 铺开），载体异常（宿主 VM
Python try/except / interp.py / native longjmp——载体不可知）在分派边界
统一转带内 "__异常__" 标记——载体派发家族（除零/解构失败/未定义变量）
try/catch 全捕获，三面 + VM² 同判；带内 "__抛错__"/"__停机__" 路径零变
化。八形态锁档 38a1–38a8 + 35x 真化改锁；vm.matha +46−31 单文件改动，
src/ 零改动、指令码不变。附带发现登记：vm↔m3v 下标越界文案分歧（vm/hi
透传 Python IndexError「list index out of range」vs m3v stdlib get 域文
案「列表索引越界: 5」——同一载体守卫、不同检测点，38a1 双面文案锁防漂
移）+ 38a 窄分歧新建全局名捕获路径丢失（结构脊展开，38a7 登记锁）。

Track B both_err 归因批（阶段 39）：逐个归因 13 both_err 语料，快照重生成
225 = 双面一致 211 / 诚实 differ 3 / both_err_equal 11 / both_err 0 /
boot_err 0 / timeout 0——残留错误条目全为双端逐字同判的诚实边界。39a 链面
应用分派收口：Dict 应用臂补 λ 节点识别（`求值lambda` 折闭包重入 __closure__
——柯里化/多参复用）+ 不可调用值渲染载体改 `标准库.元素repr`（CPython repr
规则，str/空串/int/列表/CJK/转义六形态 vm/hi/mb/bootvm 四面消息逐字同判）+
interp.matha 零参 λ 守卫（此前 `params[0]` 落原生 IndexError）。39b/39b-2
未定义变量异常类真化（31-⑧ 退役）：类型化抛错内建 `未定义错误` →
`MathaUndefinedNameError` 注册 hi/VM/vm.matha 三面且同列插口保留名，链面
`查找环境`/`查找环境链`/`查全局` 缺名臂改走该内建——四面 + m3v 面异常类与
宿主归一，消息逐字不变。39c/39d：`bootstrap_matha` 语料刷新到现行柯里化
API（host 面旧错「属性访问失败: str.类型」退役，4 输出双面 ok）+
`compiler_matha` 的 `不折叠` 模块级 let 前移模块顶（宿主闭包按定义序快照
环境——`bootstrap_full_test` host 面旧首错名退役，22 输出双面逐字相等）+
本地 `dict_from_pairs` 副本退役为 `use 标准库` 导入。39e 判定面细分：双 err
且 `boot_err == host_err` 逐字全等 → `both_err_equal`（与残留分歧分列）+
summary 七分类键 + `structure_check` 缺键诚实报需重生成。新锁档
test_selfhost_language_phase39 31 项；phase21 两条陈旧边界锁改真化锁；
boot 编译器 stage2↔stage3 逐位一致零扰动、src/ 仅 vm.py +16 行。残留登记
不修：三引号字符串双端词法器均不支持（同判「不可调用的值: ''」）/
`加载模块` 胶水返回形状（hi bool vs VM 面 list[str]）/ m3v 直调 `未定义错误`
逃逸边界经 `错误()` 转宿主 MathaRuntimeError（带内通道无类型载体）。

真缺陷批（阶段 40）：三引号多行字符串双端词法器真化（39-① 退役）+ Track B
differ 3 语料级收口（31-⑨ 退役）。40a 宿主 `src/lexer.py` 新增
`_string_triple` 三态扫描（闭合三连 / 转义续行 / EOF 未闭合诚实报错）+ `"`
与 `'` 首字符三连判定分派；boot 镜像 `matha/lexer.matha` `是三连`/
`扫描三引号续`——`""""""` 空串、跨行串、`"""a\tb"""` 转义、`'''…'''` 四形态
token 值/行/列双端逐位 parity，多行值 vm/hi/mb/VM² 四面 + M3V 六文件链同判；
`matha/bootstrap_test.matha` 测试 4 由诚实拒绝真化为跑通。未闭合串四形态
双端诚实报错同文案「字符串未闭合」（载体类名分歧登记）。40b 按登记根因产品
侧真修（判定面 `_norm` 零放宽）：宿主值语义 `__eq__`/`__repr__`——
`src/autonomous.py` `_OptResult`/`_GrowResult` 与 `src/domains/data_science.-
py` `Dataset`（可变故不可哈希；`_Sample` 含挂钟耗时故意不改）+ 神经网络显式
播种（`seed_random` → `随机种子` 域内建四面注册 + registry 模板 + manifest
重生成 + `examples/ai/neural_network.matha` 顶置 `随机种子(2026)`）。Track B
快照重生成 225 = 双面一致 215 / differ 0 / both_err_equal 10 / both_err 0 /
timeout 0；四处旧锁真化改锁（phase30 differ、phase39 39c 根因、phase19 与
phase21 bootstrap_test 边界）。新登记不修：`matha/interp.matha` 缺 机械单元/
生成语句 执行臂（29c 只落 interp_matha）/ NEWLINE token 位置与值约定分歧 /
未闭合串载体类名分歧 / 裸解释器面深栈递归预算（限幅伪影）。新锁档
test_selfhost_language_phase40 27 项；src/ 仅 lexer.py +28 行，指令码与
ast_vm_gap 快照零扰动。

资源库假成功清算批（阶段 41）：方向 A 拍板——只动纯 Matha 资源库
`matha/resource/**`（37 文件 +2611 −767 行），`src/` 零改动、本体量 33,480
与指令码 36 不变；判据为三面（宿主解释 hi / 编译 VM vm / 五文件 boot 链
调用面）。41a/41b/41c 危险桩真化：`HMAC哈希`（旧体直接返回消息本身——假
摘要，现两轮 131 进制滚动散列、密钥入内外两轮）/ `死锁充分条件` /
`银行家安全性`（旧恒返 真，现经典安全性算法逐轮扫 Need；维度不齐声明
fail-closed 取保守答，不越过末尾下标落 IndexError）/ `资源分配图含环`
（旧恒返 假，现等待图 DFS）/ `活锁检测` / `SSTF·SCAN·C_SCAN 总移动` /
`LRU 缺页` / `FCFS·RR·HRRN 周转时间` / `Dijkstra距离`（28-⑧ 退役——旧桩
恒返 [999999…]，现权重和+1 作无穷 + O(V²) 顺序松弛，不可达记 -1）/
`内部收益率近似`（恒返 0.1 → 二分求根）/ `二阶极点` / `音频混音` /
`直方图均衡化映射` / `sepia滤镜` / `中位数`（偶数长度走 `//`——`/` 恒浮除
旧式落「索引操作不支持: list[1.5]」）/ `复制列表`·`排序`（不改入参）/
`时间戳转日期`（小数年 → 整除，合 `-> Int` 声明口径）。41d-1 链面缺失
内建家族逐文件改走三面同判路径（`注册内建(空环境)` 只 47 名，
`exp/log10/log2/ln/π/组合数/asin/acos/atan/atan2` 在链面恒「未定义变量」
即整个函数不可调用）：指数写 `2.718281828459045 ^ x`、对数换底
`log(x)/log(10.0)`、反三角走二分、`atan2` 走 `象限角`、`组合数` 走本地
`组合数按连乘`。41d-2 无定义读数（分母为 0、空表、越界、负方差）不再伪造
`999.0`/`999999` 哨兵或 `0`，改诚实 None（15 形态三面同判）。41d-3 合法
近似只补口径注、零语义改动（长度比文本相似度、固定 365 天日历差、非
softmax 分类置信度、Zeller 同族周几相位）。新锁档
test_resource_algorithm_true_phase41 247 项（223 三面同判正典读数 + 52 资源
文件零缺失内建/零哨兵静态锁 + 语义结构锁 + 登记锁）；Track B 225 快照
--write/--check 逐字节零扰动（52 个资源语料全 both_ok_equal）；ast_vm_gap
快照重生成（节点 78 / 指令码 36 结构不变，13 节点 `used_in` 随资源构造
变动：ListLiteral 79→92、IndexExpr 77→85、SliceExpr 25→31、CodeBlock
104→110、IfExpr 96→101 等）。新登记不修见 KNOWN_ISSUES 阶段 41。

编译器框架接入 MBC 主线（阶段 29e，opt-in 默认关）：`src/compiler/
mbc_adapter.py` 两条 MBC 字节码遍（常量折叠调 VM 同一 `_BINOPS/_UNARYOPS`
求值、报错诚实保留运行期；死代码消除可达性 BFS + 跳转重映射）。内核
`exec_api` 不 import 框架（依赖棘轮），只暴露编译后钩子槽
`set_compile_hook`——适配器被显式 import 即反向注册，再叠
`features MBC_PASSES` 开关（默认关）双保险；不 import 即完全无钩子。

---

## 项目结构

```
matha/
├── src/                    # 核心源代码
│   ├── domains/           # 88 个领域插件（+ 包初始化/注册表）
│   ├── kernel/            # L1 纯净内核（纯标准库）
│   ├── plugins/           # 内核外工具插件
│   ├── compiler/          # JIT/AOT 编译器（LLVM 子过进程属可选插件）
│   ├── mbc/               # 主执行链：compiler → vm →（可选）native
│   ├── repl.py            # REPL 入口
│   └── ...
├── tests/                  # 测试套件（190 个文件）
├── golden_tests/           # 39 例逐字节黄金用例（vm/interp/native）
├── dist/                   # 可执行文件输出（由 build_exe.py 本地生成，不随仓库分发）
├── offline_package/        # 离线安装包
├── scripts/               # 工具脚本
│   ├── package_offline.py # 离线打包
│   ├── deploy_offline.py  # 离线部署
│   ├── verify_offline.py  # 环境验证
│   ├── build_exe.py       # 可执行文件构建
│   ├── build.bat          # Windows 构建脚本
│   └── build.sh           # Linux/macOS 构建脚本
├── matha.spec             # PyInstaller 配置（matha）
├── matha-cc.spec          # PyInstaller 配置（matha-cc）
├── docs/
│   ├── OFFLINE_GUIDE.md   # 离线使用完整指南
│   └── BUILD_GUIDE.md     # 可执行文件构建指南
└── pyproject.toml         # 包配置
```

---

## 离线可用功能

### ✅ 完全离线可用（无需网络）
- 解释器/编译器（Lexer → Parser → MIR → CodeGen）
- JIT 函数级编译 + 自动 Memoization
- C/Python/Rust/Go/Java/C++/JS/Matha 代码生成
- LSP 语言服务器
- API 文档生成
- 类型系统
- CSP 并发
- SQLite 离线存储
- 所有 88 个领域插件

### ⚠️ 需要网络（离线不可用）
- 远程包安装/搜索
- LLM 意图解析（自动降级到正则）
- Growth Engine 网络搜索
- 移动端 WebSocket 协作

---

## 文档

| 文档 | 说明 |
|------|------|
| [权威文档索引](docs/index.md) | 只有 10 份现状文档，其余已归档 |
| [架构现状](docs/ARCHITECTURE.md) | 主执行链、内核白名单、插件层 |
| [依赖基线](docs/DEP_BASELINE.md) | `scripts/dep_audit.py` 产出 |
| [AST × VM 覆盖矩阵](docs/ast_vm_gap.md) | 删转译路径的前置件 + 语言口径 |
| [符号能力对照](docs/symbolic_parity.md) | 内核纯实现 vs sympy |
| [Matha 符号标准库](docs/matha_stdlib_symbolic.md) | 阶段 4：`.matha` 重写 + 逐位对拍 |
| [已知问题](docs/KNOWN_ISSUES.md) | 未达成项如实列表 |
| [离线使用指南](docs/OFFLINE_GUIDE.md) | 离线包部署 + 可执行文件 |
| [构建指南](docs/BUILD_GUIDE.md) | PyInstaller 独立可执行文件 |
| [语言规格](docs/spec/) | 词法/语法/语义/EBNF（00–21 共 22 份） |

---

## 质量门禁

对外只有一个口径、**一个通过率数字**：

```bash
make check          # = python scripts/check.py（含 vm↔native 机器码对拍）
make check-lite     # 同上，不跑需要 nasm/link 的机器码对拍
```

它把六项串成一条链：`tests/` + `kernel_purity` + `ast_vm_gap` +
`golden`（逐字节）+ `dep_audit` + `native_parity`。口径纪律：跑不成
一律记失败，不记跳过；跳过项从分母剔除但显式打印台数，绝不把「没跑」
算成「跑通」。

```bash
# 离线环境验证
python scripts/verify_offline.py
```

**实测结果（最近一次 `make check`）：** 通过 6644 / 计入 6644，失败 0，**通过率 100.00%**
（含 `kernel_purity` 14 / `ast_vm_gap` 11 / `golden` 39 逐字节 / `dep_audit` 违规 0 条；
`native_parity` 38 过 + 1 例不计入分母（`18_domain_lazy_load`：native 不承载领域插件符号）；
原 2 个类型校验静默错值缺口 NI-001/NI-002 已修复（未定义名与字符串参与 `-` 均抛可捕获异常），
详见 `docs/KNOWN_ISSUES.md`。代数数打印插件
（`src/algebra/`）已从二次域 ℚ(√d) 扩面到多根式域 ℚ(√d₁,…,√d_k) 与高次纯根 ⁿ√d（`√2+√3 → sqrt(2) + sqrt(3)`、
`∛16 → 2*root(3,2)`），新增 25 项对 sympy 的结构化对拍锁与诚实边界锁（内核与接口零改动）。本轮全量跑零
DeprecationWarning。旧快照的绝对数字
会随用例增减漂移，以 `make check` 实时输出为准。）

---

## 构建独立可执行文件

```bash
# 安装 PyInstaller
pip install pyinstaller

# 构建 matha REPL
python -m PyInstaller --noconfirm matha.spec

# 构建 matha-cc 编译器
python -m PyInstaller --noconfirm matha-cc.spec

# 或使用脚本
python scripts/build_exe.py
```

生成的独立可执行文件：
- `dist/matha/matha.exe` — Matha REPL
- `dist/matha-cc/matha-cc.exe` — 编译器

> 仓库不预构建发行版：`dist/` 在 `.gitignore` 内，历史快照中的 exe 不代表现状；
> 构建链是否可用以本节命令当场实测为准（定位说明见 `docs/KNOWN_ISSUES.md`）。

---

## 版本信息

| 项目 | 值 |
|------|-----|
| 版本 | v4.6.0（单一来源 `src/__version__.py`） |
| 内核协议 | 1（`KERNEL_PROTOCOL`，与插件契约同步演进） |
| Python 要求 | >= 3.10 |
| 核心第三方依赖 | 0 |
| 许可证 | BSD-2-Clause |
| GitHub | https://github.com/zzk2025r/matha |
| 独立可执行文件 | 支持（本地自建，仓库不预构建发行版） |
| 领域插件 | 88（按需加载） |

历史文档（118 份一次性报告）已归档到 [`docs/history/`](docs/history/)，
不再作为现状依据；权威文档只有一张索引页：[`docs/index.md`](docs/index.md)。

---

## 社区

我们欢迎所有贡献者！

### 参与方式

- **报告问题** - [GitHub Issues](https://github.com/zzk2025r/matha/issues)
- **提交 PR** - Fork 并创建 Pull Request
- **文档改进** - 修复错别字、添加示例、翻译
- **领域模块** - 添加新的领域模块
- **测试贡献** - 添加测试用例

### 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

### 行为准则

详见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

---

*版本：v4.6.0（取自 `src/__version__.py`）*
