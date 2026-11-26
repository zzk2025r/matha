# Matha

自举式领域专用语言与独立可执行编程语言系统。

## 系统状态（实测，非自评）

下表每个数字都由 `python scripts/repo_facts.py` 从仓库现场数出来，
`tests/test_doc_facts.py` 会核对文档与代码是否漂移（漂移即红）。

- **版本：** v4.6.0（唯一版本源 [`src/__version__.py`](src/__version__.py)）
- **领域插件：** 88（`src/domains/` 共 90 个 `.py`，其中 `__init__.py` / `registry.py` 不是插件）
- **内核外工具插件：** 7（`src/plugins/`）
- **黄金用例：** 39（`golden_tests/cases/`，vm ↔ interp ↔ native 逐字节）
- **`.matha` 语料：** 184（历史遗留的旧写法已全部改写为合法 Matha，当前 0 个属语法层遗留，见 `docs/ast_vm_gap.md`）
- **测试文件：** 197（`tests/`）
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
python scripts/build_exe.py --matha       # 产出 dist/matha.exe
python scripts/build_exe.py --matha-cc    # 产出 dist/matha-cc.exe

# 启动交互式 REPL
dist/matha.exe

# 计算表达式
dist/matha.exe eval "sin(3.14)"

# 运行 Matha 源文件
dist/matha.exe run demo.matha

# 启动链面终端（纯 Matha 装载器 + 纯 Matha 命令执行器）
dist/matha.exe term

# 常驻监管一个 Matha 进程（重启策略在纯 Matha 内核，阶段 43d）
dist/matha.exe 监管 --预算 2 -- server --port 8787

# 编译到 LLVM / 可执行文件
dist/matha-cc.exe compile demo.matha
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
上；Python 层只保留 IO 原语与进程入口。执行体（阶段 42c）：默认 `chain` 后端——
boot 链 + 纯 Matha 装载器（`matha/loader.matha`）装载 `终端执行器`，命令逻辑跑在
Matha 自己装载出来的数据闭包上；`MATHA_TERM_BACKEND=host` 切回宿主 Python 树遍历器
面（对拍/排障用，`调试` 命令需要它）。两面无静默回落：链面装配或执行失败如实报
「错误: …」并以退出码 1 结束，不偷换执行体。CMD 模板命令集（目录/换目录/显示文件/
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
内建家族逐文件改走三面同判路径（`注册内建(空环境)` 只 47 名——阶段 41
时点值，现行固定面 60 名，见 ARCHITECTURE 第五节，
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

纯 Matha 装载器与终端链面默认（阶段 42）：方向拍板——「终端与装载全由
Python 代劳」这条缺陷收口，本阶段只做**纯 Matha 装载器**（自修复/生长面不在
本阶段），载体原语按**逐名补 16 条 Matha 臂**，终端**链面直接设为默认**。
42a 新增 `matha/loader.matha`：模块名表（22 条）、三级解析序（`matha/` 主路径
→ `.matha_packages/` 扩展包 `manifest.json` 的 `entry`/`enabled` → `matha/library/`
资源库递归）、`use` 依赖递归装载、模块函数摊平、`内建` 别名表并入、`机械单元`
自测块剔除、命名空间产出——解析序与报错文案逐条镜像宿主
`src/interp.py` 的 `load_matha_module`，装载这件事本身由 Matha 完成，宿主 Python
仅作 OS 能力的载体；装配壳 `src/matha_chain.py` 把 boot 链五模块 + 装载器编为
level-1 M3V，被装载模块体经 `解释器.执行语句` 以 level-2 数据闭包执行，`装载根`
注入仓库根绝对路径使 `换目录` 之后装载仍命中同一批源。42b `matha/interp_matha.matha`
/ `matha/interp.matha` 双镜像补 16 条载体原语逐名臂（执行命令/执行命令输入/管道输入/
管道结束/输入行/列目录/建目录/删除路径/复制文件/改名/换目录/路径存在/执行Matha/
调试Matha/升级包/检查包更新）+ 语言级 `错误` 名，链面固定面 47→59 名，缺臂名如实
报「未知内建函数」不静默回落宿主实现。42c `MATHA_TERM_BACKEND` 默认 `chain`
（`host` 保留为对拍/排障入口，未知取值显式拒绝），两面无静默回落；后端装配失败
在薄壳单点收口为「错误: …」+ 退出码 1（此前异常逃逸成 traceback）。链面冷启动
成本实测 boot 装配 ~1.8s、装载 `终端执行器` ~20s、逐行 0.1–1.2s（诚实标价，非缺陷）。
新锁档 `tests/test_selfhost_language_phase42.py` 33 项（42a 解析序/清单/依赖/摊平
对宿主逐条同判 + 42b 注册面 59 名与逐名臂静态锁、level-2 真达宿主、偏应用零副作用
+ 42c 后端默认值、无静默回落、双面 9 行命令逐字同判、`调试` 显式拒绝端到端）；
ast_vm_gap 快照重生成（节点 78 / 指令码 36 结构不变，语料 230→231 随 `loader.matha`
入语料，21 节点 `used_in` 各 +1）；Track B 快照 225→226 = 双面一致 216 / differ 0 /
both_err_equal 10 / both_err 0 / timeout 0（唯一变动是新语料 `loader.matha` 双面
同判 both_ok_equal，其余 225 语料分类零漂移——boot 链 `interp_matha.matha` 补臂
不改判定面），`--write`/`--check` 两跑一致；本体量口径（`src/lexer.py`+`parser.py`
+`ast_nodes.py`+`kernel/`+`mbc/`）内改动仅 `src/mbc/vm.py` 拒绝文案 +1 行（本体量
33,481），新增装配壳 `src/matha_chain.py` 与 `src/interp.py` 的 `_CN2FILE` 装载器
条目不属内核五件、不在口径。新登记不修见 KNOWN_ISSUES 阶段 42。

冻结 exe 进程映像与常驻监管（阶段 43）：方向拍板「先从进程映像开始，必须冻结 exe
而且必须是 Matha 的 exe」——先做冻结可执行批，再在其上做常驻监管真化批；验证深度
走「全量门禁 + 真 CMD subprocess e2e」。**43a-1** `matha.spec` 重写：语料入包
（`matha/**/*.matha` + 前端 `.c/.go/.js/.rs` + `src/domains/manifest.json`，动态导入
面靠清单而非逐个 hiddenimport）、入口统一指向 `src/matha_main.py`、单 `Analysis` +
单 `EXE(name='matha', console=True)`、路径全部从 `SPECPATH` 推导（不再有绝对字面量）、
三条装配口径写进 spec 头注；`scripts/build_exe.py` 产物落点改平铺 `dist/<名>.exe`，
与 `.github/workflows/matha-ci.yml`、`scripts/build.bat`、各安装脚本同一口径（旧写法
落 `dist/<名>/<名>.exe`，按平铺路径取件的 CI/脚本必然落空）。**43a-2** 冻结态根口径
（`src/matha_chain.py`）：区分 onefile 解包根 `sys._MEIPASS` 与 exe 所在目录，`MATHA_HOME`
覆盖优先且不静默回落，语料根序「覆盖 → 解包根 → cwd.parent → cwd」逐条镜像宿主
`_matha_dir()`，扩展包根序「覆盖 → cwd → 解包根」镜像宿主 cwd 优先，读不到源如实报
「装配源缺失: …（候选 …）」；`matha/loader.matha` 改由 `当前目录` 自行发现 cwd 根，
链面固定注册面 59→**60 名**（第 17 条载体原语 `当前目录`，双镜像同步），42-①② 两条
登记随之退役。**43b** Windows 入口真化：`start_matha_server.bat` 旧版调用的
`src.matha_daemon` 在阶段 11 已删除（脚本因此从未启动过服务，echo 宣称的守护/健康检查/
自动重启/防火墙入站四项能力全仓无实现），现指向统一 CLI 新命令位 `server`（委托
`src/openai_compat_server.serve`，端口占用在 +1..+10 内自动切换），有 `dist\matha.exe`
即用冻结进程映像启动；`serve()` 成为唯一启动面。**43c** 被启动的解释器 = Matha 自己：
`src/domains/os_module.py` 的 `运行脚本` 实现改走 `_self_launcher`（冻结态
`sys.executable` 即 matha.exe，开发态宿主解释器 + 统一 CLI 入口，命令面不分叉），
`.matha`/`.msh` 交 Matha 入口、其它后缀交宿主解释器，`shell=True` 去除——路径不再是
命令注入面。**43d** 常驻监管真化：重启策略住在纯 Matha 内核 `matha/os/kernel.matha`
（+102 行：`常驻单元须有主入口` 显式拒绝、`_启动落地` 先 `_收旧进程` 再 `_派主进程`、
`_可重启` 五条件、每 `_调度轮` 尾跑 `_监督轮`、`监督状态` 只读、重启不记 `步数`），
宿主 `src/os_runtime.py` 只留 `self_launcher` / `register_external(常驻, 重启预算)` /
`supervision` / `supervise(轮数, 间隔, 回报)` 墙钟薄壳，CLI 新增 `监管`（别名
`supervise`）命令位；冻结态实测被监管子进程映像名集合 = `{matha.exe}`、进程树内无
`python.exe`，崩溃单元读数 `['重启', 'flaky', 2]`（onefile 每次冷启解包 ~5.5s，故监管
窗口须按 `轮数 × 间隔` 覆盖两次冷启）。**43g** Windows 安装入口产物落点收口：15 个
安装/卸载/打包脚本对齐平铺产物、版本改取唯一版本源 `src/__version__.py`（旧 `setup_workspace.ps1`
硬编 4.4.57 与 `matha --version` 打架，且 `if (Test-Path $X -and -not $Force)` 被当成
参数绑定错误使脚本在 WinPS 5.1 上一启动即停、`??` 运算符同为 5.1 不支持）、
`setx PATH "%PATH%"` 改按条目追加（1024 字符截断）、卸载脚本改交接式自删（cmd.exe
逐行读盘 vs PowerShell 先整体解析的不对称已实测入锁）。新锁档
`tests/test_frozen_entry_phase43.py` 89 项 = 43a 26（spec 静态锁 11 恒跑 + 根口径 15）
/ 43b 6 / 43c 9 / 43d 15 / 43f 10（其中 4 项 `@_frozen_gate`：`dist/matha.exe` 不在位
即 skip，在位即真跑冻结 e2e 与真 CMD 取证）/ 43g 23。本体量口径内 `src/` 零改动
（33,481 不变、指令码 36 不变）——改动全在装配壳、CLI 薄壳、域胶水、桥面、被委托服务、
内核语料与打包/安装脚本。新登记不修见 KNOWN_ISSUES 阶段 43。

原生 OS 派生面（阶段 44）：方向拍板——「Matha 与 Python 共存，不再调用 Python 任何模块，
直接调用系统 API……对标底层的 C 语言」，首批切片选「原生 OS 派生面」，stage-0 允许
Python 仅作种子而最终判定用无 Python 的 Matha 原生映像自证。**44b-1** 新增
`src/mbc/native_process.py`（578 行）：`派生映像` / `等候映像` / `映像退出码` /
`终止映像` / `关闭映像` 五条内建的 x86-64 发射器，触达点只有 kernel32 六个导出
（CreateProcessW / WaitForSingleObject / GetExitCodeProcess / TerminateProcess /
CloseHandle / MultiByteToWideChar），地址在引导期 `k32_base` 之上经 `GetProcAddress`
惰性解析并缓存回槽位——产物 **PE64 无导入表**（DataDirectory[1] RVA=0 Size=0），
运行路径不含任何 Python 模块也不含 CRT。「无定义读数」一律 null／−1，不用哨兵数冒充
（pid 不在表中、pid≤0、实参是堆对象、`GetExitCodeProcess` 报 STILL_ACTIVE(259)、
API 解析失败）；槽表 32 槽 × 40 字节，满槽诚实返回 −1 且不覆盖旧槽；命令行 UTF-8 →
UTF-16 转换，故中文路径与宽字符 CreateProcessW 同行为。**44b-2** 原生独占面收口：
宿主/VM 面对同一批名**显式拒绝**（两面对独立写同文案，非静默降级、不返回假值）——
核心主线红线是「单线程确定、不驱动外部进程」，要进程映像就得走原生后端；链面（boot）
固定注册名集不扩，五名在链上即诚实「未定义变量」，`src/domains/os_module.py` 的
`ProcessManager` 类注同步改口径为「进程簿记模型（模拟），不派生也不触碰任何 OS
进程」。**44b-3**
构建面真化：新增 `matha 原生构建`（别名 `native-build`/`exe`）产出真实 PE64 机器码，
`matha build` 旧文案声称「构建独立可执行文件」而 `matha_compile` 从未产出过可执行
文件，现改为产真实 `.mbc` 字节码工件并把机器码指向 `原生构建`；同批宿主桥
`src/os_runtime.py` 补 `_终止载体`——纯 Matha 内核的 `收旧进程`/`停止进程` 只改簿记
（内核面没有进程映像原语，也不该持有 OS 句柄），桥在内核判定**落地之后**才动 OS，
被拒绝的 `停止`/`卸载` 不再杀掉仍在运行的载体（此前「拒绝」会被做成真伤害：簿记说
还在运行，OS 侧进程已经没了）。**44f** 进程树取证：CIM 查得派生子的
`ParentProcessId` 就是原生映像自身 pid、父映像名是产物 `.exe` 而非 `python.exe`。
新锁档 `tests/test_native_process_phase44.py` 37 项（44a 原生 e2e 10 / 44b CLI 6 /
44c 三面拒绝 9 / 44d 桥面回收 6 / 44e 静态结构 5 / 44f 进程树取证 1）；本体量
33,481→**34,099**（+618 = 新档 578 + `src/mbc/native.py` 挂载 +16 + `src/mbc/vm.py`
拒绝内建 +24），指令码 36 不变（映像族是内建名，不是新 opcode），Track B 快照零扰动
（无 `.matha` 改动）。新登记不修见 KNOWN_ISSUES 阶段 44。

原生映像承载 Matha 工具链首片（阶段 45）：首批切片拍板「A 原生映像承载 Matha 工具链首片」，
范围边界全选「只做最小可编译片段（不扩 OS 载体）+ 补多模块链接（一次编入多个 `.matha`）+
一并处理原生栈上限 + 附带收口文档漂移与勘误」，验证深度「全量门禁 + 真原生 exe e2e」。
**45a** `MAX_NATIVE_ARITY` 8→15——15 不是经验值而是 disp8 编码可达上界
（`-8*(argc+1) ≥ -128` ⇒ argc ≤ 15），`apply_rt` 按 rdx 动态 `rep movsq` 本身无 arity
假设；boot 链唯一越界真形 `扫描三引号续`(9) 使**整个词法器**在原生面直接编译失败，旧上限
即「原生面承载工具链」的编译期唯一硬阻塞；16 参的定义位与调用位取同一常量并显式拒绝，
不静默错编。**45b** 多模块链接：`src/mbc/compiler.py compile_sources` 逐源解析后并入
**单个** `Program`（源序即顶层执行序；`use` 在编译面被忽略——符号本就落全局，跨文件调用
即同文件调用），门面 `exec_api.compile_modules` 与 `build_exe(list[str])`、CLI `原生构建`
多源位同批接线，产物仍是一份 PE64，单源路径逐字节零扰动。**45c** 原生栈口径：操作数栈迁
`.bss` 1MB（不花文件字节）+ 全操作码静态净增量表与峰值/汇合/夹住/不收敛四判据预算 +
`_start` 真填 `stack_floor` + 调用栈底守卫 + PE StackReserve 与常量同源；越界给**可捕获的
诚实异常**而非旧形「静默改写内存后退出码 0」，2 万层薄帧递归跑通并给正确读数。**45d**
承载实证：`matha/lexer.matha` + `matha/stdlib.matha` + `matha/parser.matha` 三片编进一份
真 PE64，14 条输入的 token 流（类型|文本|行|列）与 9 条输入的 AST 流和宿主 hi/vm 两面
**逐字同判**，5 条不可解析输入在 `调用捕获` 下三面同给同一句消息体（不是崩溃），产物与
阶段 44 同规格（无导入表、三节、PE32+，字节里无 python/Cpython/site-packages 标记）。
同批真修三个原生发射缺陷：序比较按 `.data` **地址序**判（`输出("b" > "a")` 直接反号）→
`val_cmp` 深序比较；帧内解构写错基址（手拼 `mov rbp,r8` 漏 REX.W）→ 统一走 `mov_rr`；
尾位置一元负把 `is_bigint` 的 0/1 判定值当结果返回 → 回读 rax。**诚实边界**：「能编」≠
「已脱宿主」——boot 全链当时仍有 25 个 latent 宿主注入名（`装载根`/`执行命令`/`解析_JSON` 等；
阶段 46 摸底后现行 **24**，见下一段），
在原生运行期如实点名失败而不静默给假值；原生错误文案取自发射器错误表，与宿主 Python 文案
不同源（登记不修）。**45e** 文档口径收口（代码零改动）：链面固定注册面现值 **60 名**
（历史条目的 47/59 为时点值）、宿主对位镜像固定面静态只 44 名（不等集，余由 28d 运行期
插口补名）、宿主 `Interpreter` **实例**内建表 3025 名（阶段 41 时点 3020 + 阶段 44 映像族
拒绝内建 5；与模块级 `src.interp.BUILTINS` 82 名不是一张表）、`module 解释器` 两套源
（106/139 名、交集 53）三套解析序、判定面补 struct 工厂而产品链未补致 `装载("解释器")`
必失败，另勘误两条行号/已删文件引用——
均登记不修，见 KNOWN_ISSUES 阶段 45 口径收口条与 ARCHITECTURE 第五节。新锁档
`tests/test_native_selfhost_phase45.py` 112 项（45e 的四个计数一律锁成「文档所写 == 当场
实测」而非写死数字；另把 `tests/test_native.py` 的 arity 越界锁
改成随 `MAX_NATIVE_ARITY` 伸缩并锁拒绝文案与常量同源）；
本体量 34,099→**34,538**（+439 = `src/mbc/native.py` +398 + `src/mbc/compiler.py` +22 +
`src/kernel/exec_api.py` +19），指令码 36 不变（零新 opcode），Track B 快照零扰动
（无 `.matha` 改动）。

46 系列首片：boot 链 latent 名逐项归因 + 一臂死函数真修（阶段 46-1）。路线形态按
「有界清算循环——每轮一条可判定判据 + 一个可回滚提交」推进，本片只做 45 登记项的归因与
其中唯一的语料缺陷。**摸底分类判据**取「名字的宿主载体归属」三分：A 类在
`build_boot_vm().vm.globals` 已有 Python 载体（20 名，`装载根`/`列目录`/`解析_JSON`…）、
B 类由 `PluginResolver` 惰性物化（4 名，os 域 `执行命令`/`升级包`…）、C 类**谁都没有**
（1 名 `acc`）——A/B 是 46a 的原生载体工作量，C 是语料自身缺陷。`acc` 落点
`matha/stdlib.matha` 的 `to_upper`：`let rec _map(i, acc)` 的形参被在 `in` 体里当自由名读
（`in _map(0, acc)` 而非种子 `""`），使 `to_upper` 是一臂**必然失败的死函数**——修前三面
（hi/vm/链面）同判 `未定义变量 'acc'`，任何调用都得不到值。改形与 `to_lower` 种子对称
（`in _map(0, "")`），修后链面经产品分派体 `应用内建实` 给 'AB' / 'HELLO, WORLD! 123' / ''
/ 'ABC_é中'（非 ASCII 原样保留），同一语料编进真原生 PE64 逐字同判；把旧行回注的反控
（`test_46d`）证明失败来自该行本身而非装载环境。latent 名集 25→**24**（总读位 33→32，
C 类归零）。同批把**分类动作本身**固化成机器判定：`test_46e` 要求每个 latent 名都能在宿主
globals 或插件 `known_symbols()` 里找到载体，找不到即红——防止未来把语料自由名登记成
「脱宿主缺口」；`test_46h` 另锁「24 是下界」的口径（boot 链 831 个 LOAD_GLOBAL 名与
`_UNRESOLVED_GLOBALS` 编译期拒绝集合的交集只剩已按静态对象发射的 `None`/`_empty_dict`，
latent 名不在其中——链接期不报、运行期才炸）；`test_46j` 把四份文档里写的名数/读位数直接由
`_latent_reads` 的实测值拼出锚点，文档与机器读数脱钩即红。附带登记不修两条：`to_upper` 是链面独有注册名，
`src/**.py` 全仓零载体（41-① 表差族新成员，锁成「实测 == 所写」）；`dist/matha.exe`（11-25 13:27 构建）
的内嵌语料副本按 `matha.spec` 的整树入包口径必滞后本行，但其 `run` 面落 46i 的 hi 缺口、`终端` 面走
CMD 命令表，两条入口都到不了链面分派臂，故该滞后只有构建期证据而无运行期读数——门禁期间不重建
`dist/`（44-⑧/43-② 承继族）。新锁档
`tests/test_native_selfhost_phase46.py` 22 项；本体量 **34,538 不变**（`src/` 零改动，
产品侧改动只有 `matha/stdlib.matha` 一行）。

46c 判定面换形：退役 Python 之前先把裁判换掉。现役三面正确性判据（Track B
boot↔host、golden vm↔interp、native_parity host↔exe）的裁判**都是 Python**——退役那一刻
只剩「没崩」，正是阶段 41 清过的那一类假成功温床，所以这片是「Python 退役」的**前置**
门禁而不是后置。三条形态各自落地并有锁（`tests/test_judgment_face_phase46c.py` 19 项）：

- **形态①（自举双跑）已在编译面成立**：`matha/compiler_matha.matha` 连同词法/标准库/语法
  四片链进原生映像后，编译器在映像里跑起来了。两个**独立构建**的映像（四片链接 vs 四片
  文本拼接）各在自己的进程里编译同一批源，64 行字节码读数（常量池／主码／函数表／模块名）
  逐字相同，并与仓库里手写的字面量同判；同一映像内重复编译同判；构建面另有三组源各两次
  独立发射逐字节相同 + 同一映像三跑 stdout 逐字相同。解释器面（`interp_matha`/`loader`）
  仍进不了映像——boot 全链 + 编译器实测在第一条驱动语句前以 `不可调用的值` 退出（rc=0x1），
  即 46a/46b 的边界。
- **形态②（手算／规范对拍）**：词法器 37 行 token 流、语法器 7 行 AST 流、编译面 64 行
  字节码全部逐行写死在锁档里，依据指到 `matha/*.matha` 的源行（`Int` 归 关键字 而非
  标识符——`matha/lexer.matha:188` 推翻手算直觉的那一条正是这类锁的价值）；三刀反控
  （置换顺序／改类型名／改操作码编号）证明字面量承重，不是「有输出就行」。
- **形态③（差分面降为 dev-only）**：`scripts/selfhost_matrix.AUTHORITY =
  "dev-only-differential"`，产品面 `src/**` 零 import 判定工具（有锁，防止退役时拆不掉）。
  差分面自身的功率同时如实分层：旧快照里「两侧都没产输出」与「N 行逐字相同」同形，
  现按 `n_outs` 拆成 obs／silent 进 `summary.power`——实测 **226 语料**，其中
  **双面一致 216 = 有读数 71 + 空对空 145**，即「双面一致 216」这句口径里只有 71 条真的
  比过内容（共 270 行读数）；被反复引用的 52 条 `matha/resource/**` 语料**全为 silent**
  （资源库的真证据在阶段 41 的手算锁里）。七分类对 files 的闭合不变、226 条目分类
  零漂移、`--check` 一致，快照改动纯增量。

本体量 **34,538 不变**、指令码 36 不变（本片零 `src/`、零 `matha/` 改动，只换形判定面）。

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

**实测结果（最近一次全量门禁：tests lane 独立跑 + 五轻 lane 顺序跑 + Track B `--check`，2026-11-25）：** 通过 8409 / 计入 8409，失败 0，**通过率 100.00%**
（另有 1 项平台 skip 不计入分母；含 `kernel_purity` 14 / `ast_vm_gap` 11 / `golden` 39 逐字节 /
`dep_audit` 40 内核文件 190 import 边 违规 0 条；
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

生成的独立可执行文件（平铺在 `dist/` 下，与 `scripts/build_exe.py` 和
`.github/workflows/matha-ci.yml` 同一口径）：
- `dist/matha.exe` — Matha 统一 CLI 入口（repl / 终端 / run / eval / server / 监管 …）
- `dist/matha-cc.exe` — 编译器工具链

> 仓库不预构建发行版：`dist/` 在 `.gitignore` 内，历史快照中的 exe 不代表现状；
> 构建链是否可用以本节命令当场实测为准（定位说明见 `docs/KNOWN_ISSUES.md`）。

### 原生机器码映像（不经 Python，阶段 44）

上面两个 `.exe` 是 **PyInstaller 装配壳**：进程仍是 Python 引导后跑 Matha，用于交付
完整 CLI 与领域插件。要得到**不含 Python 的 Matha 专属映像**，走 `原生构建`——
`src/mbc/native` 直接把 M3V 字节码发射成 x86-64 PE64 机器码：

```bash
# Matha 源码 → 原生 PE64（无导入表：运行期由 PEB 走表解析 kernel32）
python -m src.matha_main 原生构建 demo.matha -o demo.exe
# 等价别名：matha native-build / matha exe
```

产物可直接被 Windows 的 CMD/PowerShell 调用，并且**自己派生自己的子进程**：原生映像
内的 `派生映像`/`等候映像`/`映像退出码`/`终止映像`/`关闭映像` 五内建经 kernel32 直接
工作（进程树中父映像就是产物本身，无 `python.exe` 中转，实测取证见
`tests/test_native_process_phase44.py`）。超出原生子集的语言构造（未支持的二元/一元
运算符等）在编译期抛 `NativeNotSupported`、命令如实非零退出且**不留产物**；领域插件
符号不被原生面承载，产物运行时诚实报「未定义变量」而不是给出假值。

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
