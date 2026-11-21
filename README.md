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
- **测试文件：** 183（`tests/`）
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
├── tests/                  # 测试套件（183 个文件）
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
