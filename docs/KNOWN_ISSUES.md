# Matha 已知问题与未达成项（v4.6.0）

> 这份文件只列**当前可复现**的问题，每条都给出可执行判据。
> 旧版的清单已整份移入 [`history/KNOWN_ISSUES.md`](history/KNOWN_ISSUES.md)。
> 规矩：不允许写「已全部解决」；解决一条就删一条，删不掉就留在这里。

## 一、机器码后端（`src/mbc/native.py`）

> NI-001、NI-002 已修复：未定义变量与字符串/列表参与 `-` 均经 `raise_rt` 抛
> 可捕获异常，不再静默读成裸 0 / 拿对象指针做假减。已从 `manifest.json` 的
> `native_known_gaps` 清空，`make check`（`--native`）22/23 通过（唯一 gap 为
> `18_domain_lazy_load`：native 不承载领域插件符号，属设计内 SKIP）。

### 1a. 领域插件符号的设计边界（已上锁，非缺陷）

机器码 exe 是**独立**产物，运行时没有 Python 宿主、没有懒加载全局表，因此
`@：【加载领域】` 引入的符号（如 `公差系数_IT10`）在 native 侧不存在。已确证的
真实行为：带或不带加载指令，native 均把该符号当作未定义变量 → 运行期 `raise_rt`
以非零码干净退出、**不产出任何伪造值**（而非静默读成裸 0）。此边界由
`tests/test_native_domain_contract.py` 锁定：一旦退化回「静默造值」即红。工具链
缺失时该测试优雅 SKIP（只约束真实机器码路径）。

### 1b. NI-009（未修）：函数块内「递减」`let rec` 累加器令 native 访问违例

- **Bug 类**：合法程序在 native 编译成功却运行期崩溃（`rc=0xC0000005` 访问违例）、
  静默无任何输出——属 NI-001/002 同类「无声失败」。
- **根因定位**：仅当 `let rec` 自累加器**在函数 `{}` 语句块内**且**递归用减法
  `step(i-1, …)`** 时触发。等价的递增 `step(i+1, …)`、或把同一 `let rec` 放**顶层**（不在
  函数块内）、或直接递归 `if…then…else` 均正常（已逐一探针取证）。VM 与解释器对以上
  全部形式均正确。
- **可复现判据**：`compile_to_exe` + 子进程跑
  `func 阶乘(n)->Int = (n)=>{ let rec step(i,acc)= (i,acc)=>(i<=1)?acc:step(i-1,acc*i); step(6,1) }\n[阶乘(6)]`
  → rc 非 0、stdout 为空（应输出 `720`）。
- **当前规避**：黄金用例 `19_corpus_recursion` 采用递增累加器等价写法，已三端逐字节一致；
  本项保留待 native 代码生成修复（涉及块内闭包槽位/寄存器分配与递减归纳的交互）。

## 二、语法层历史债务

曾经有 19 个 `.matha` 语料文件连 parser 都过不了（`matha/knowledge/`、`matha/resource/`、
`matha/vm/` 下的 Python 风格草稿：`？` 占位符误用、记录面 `#：{}`、`->` 位置错误、
`X if COND else Y` 后缀式、`(OP,)` 单元组尾逗号、空格标识符等）。本轮已把它们**改写为合法
Matha**（仅动语料内容，未改 parser/VM），文件**保留不删**（兼容承诺）并已进入主线解析。
当前「语料解析失败」计数为 **0**。

判据：`python scripts/ast_vm_matrix.py --write` 输出的「语料解析失败」计数应为 0；
[`ast_vm_gap.md`](ast_vm_gap.md) 与 `ast_vm_gap.json` 的 `unparseable` 字段为空。

## 三、符号能力覆盖面

| 范围 | 现状 | 行为 |
|---|---|---|
| 极限 | `.matha` 标准库只覆盖有理式（多项式商）+ 洛必达≤8 层 | 超越式（如 `sin(x)/x` 在 0）时标准库路径显式 `不支持: …`，`backend="auto"` **回退内核引擎 stage0 求解**并计入 `BACKEND_STATS["fallback"]`（非“不能算”：内核给与 sympy 一致的正确值，见 parity 第 4 节） |
| 泰勒/级数 | `.matha` 标准库只覆盖 `point=0` 的 Maclaurin | 非 0 点时标准库路径显式 `不支持`，**回退内核 stage0：`src/kernel/symbolic/series.taylor` 已覆盖任意点**（与 sympy `series` 同式，值正确）；现由 `tests/test_kernel_symbolic.py` 以数值一致性锁定。输出为 `x` 的展开幂形式（sympy 保留 `(x-a)ⁿ`），属代数等价变形（见 parity 第 5 节） |
| ODE | 一阶可分离 + 一阶线性积分因子 + 常系数齐次特征方程 | 其余抛 `OdeUnsupported`，不返回「无法求解」这种假成功 |
| 与 sympy 对照 | 内核纯实现为**子集** | 逐函数标注见 [`symbolic_parity.md`](symbolic_parity.md) |
| stage0 已知不准 | ±∞ 极限用采样逼近，末位错（例：`(2x+1)/(3x-1) → 0.6666666666722222`）；`evaluate` 不认识 `ln` | 标准库在这两项上更准/更强，偏差双向锁定于 `tests/test_matha_stdlib_symbolic.py` |

## 四、跨后端差异（如实登记，不抹平）

运行时错误主体已大幅归一，并由 9 例错误黄金用例锁定（vm ↔ interp ↔ native）：
除零 / 取模除零 / 整除除零 / 类型不匹配 / 列表越界 / 字符串越界 / 不可调用 /
对不可下标对象取索引——两端抛**同一异常类**且消息主体逐字一致。

本轮修掉了 VM 两处「漏出 Python 原生异常」的跨后端分歧，归一到解释器的领域消息：

- 调用非函数值：VM 原报 `RuntimeError: VM：不可调用的值 5` → 现 `MathaRuntimeError: 不可调用的值: 5`（与 interp 逐字一致）；
- 对不可下标对象取索引（如 `5[0]`）：VM 原漏 `TypeError: 'int' object is not subscriptable` → 现 `MathaRuntimeError: 索引操作不支持: int[0]`。
（越界索引的 `IndexError` 两端本就一致，保持透传，不在改写列。）

未定义变量类名分歧（interp 抛基类 `MathaRuntimeError`、VM 抛更精确的
`MathaUndefinedNameError`）也已闭合——interp 现也抛 `MathaUndefinedNameError`（它是
`MathaRuntimeError` 子类，`except MathaRuntimeError` 与宿主 `except KeyError` 均不变）。

**仍存在的残留分歧（未修，如实登记）**：调用一个**未定义的名字**（如 `foo(1)`，foo 未定义）：
解释器把它当函数调用报 `未定义函数 'foo'`；VM 先在全局查找阶段报
`未定义变量 'foo'`（`MathaUndefinedNameError`）。两者消息主体不同（“变量” vs “函数”）。
根因：VM 字节码里「读变量」与「调函数」共用 `LOAD_GLOBAL`，未命中即抛，无法在加载
位置区分调用意图；要归一需编译器为调用位置的名称加载发专用操作码，属侵入式改动，
本轮未做。因主体不同，此路径**未进错误黄金用例**（否则 `run_golden_tests.py` 会硬失败）。

判据：`python golden_tests/run_golden_tests.py` 末尾「跨后端 stderr 类名差异」报告为空。
黄金运行器仍保留 stderr **异常类名**白名单与消息主体逐字比对，防止未来重新引入差异。

## 五、治理与工程噪声

| 编号 | 问题 | 说明 |
|---|---|---|
| NI-007 | `import src.kernel` 本身零成本，但 `src/matha_system.py` 等聚合入口仍会拉起大量模块 | 内核纯净性由 `test_kernel_purity.py` 限定在 `lexer/parser/ast_nodes/kernel/mbc`；聚合入口不属内核 |
| NI-008 | 仓库根与 `scripts/` 历史遗留的一次性调试脚本 | 已集中移入 `scripts/scratch/`；不再作为现状依据 |

## 六、性能声明的口径

本文档集**不写**任何「加速 N 倍」「快过 X 语言」的数字：当前没有可复现的基准脚本
与固定硬件口径。需要性能结论时，先补一个能被 `make check` 覆盖的基准，再写文档。
