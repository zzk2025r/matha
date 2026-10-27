# Matha 已知问题与未达成项（v4.6.0）

> 这份文件只列**当前可复现**的问题，每条都给出可执行判据。
> 旧版的清单已整份移入 [`history/KNOWN_ISSUES.md`](history/KNOWN_ISSUES.md)。
> 规矩：不允许写「已全部解决」；解决一条就删一条，删不掉就留在这里。

## 一、机器码后端（`src/mbc/native.py`）

| 编号 | 问题 | 判据 |
|---|---|---|
| NI-001 | 从未 `STORE_GLOBAL` 的名字在机器码端被读成静态 `0`（**静默错值**），而 VM/解释器抛「未定义变量」 | `golden_tests/manifest.json` → `native_known_gaps["13_error_undefined"]`；`python golden_tests/run_golden_tests.py --native` 报 KNOWN-GAP |
| NI-002 | 字符串参与 `-` 时机器码端缺类型校验，把字符串对象指针当数减（输出假值） | 同上 `["14_error_type"]` |

这两例在 `make check` 里记为「未覆盖」并从通过率分母剔除，**不计作通过**。
修好后必须从 `native_known_gaps` 删除，否则黄金运行器报 STALE。

## 二、语法层历史债务

19 个 `.matha` 语料文件连 parser 都过不了（`matha/knowledge/`、`matha/resource/`、
`matha/vm/` 下的旧写法：`？` 占位符误用、记录面 `#：{}`、`->` 位置错误等）。
文件**保留不删**（兼容承诺），但它们当前只能在遗留后端下按片段理解，不能进主线。

判据：[`ast_vm_gap.md`](ast_vm_gap.md) 第八节逐文件列出 `ParseError` 消息；
`python scripts/ast_vm_matrix.py --write` 输出的「语料解析失败」计数。

## 三、符号能力覆盖面

| 范围 | 现状 | 行为 |
|---|---|---|
| 极限 | `.matha` 标准库只覆盖有理式（多项式商）+ 洛必达≤8 层 | 超越式（如 `sin(x)/x` 在 0）显式 `不支持: …`，`backend="auto"` 回退 stage0 并计入 `BACKEND_STATS["fallback"]` |
| 泰勒/级数 | 只覆盖 `point=0` 的 Maclaurin | 非 0 点显式 `不支持`，回退 stage0 |
| ODE | 一阶可分离 + 一阶线性积分因子 + 常系数齐次特征方程 | 其余抛 `OdeUnsupported`，不返回「无法求解」这种假成功 |
| 与 sympy 对照 | 内核纯实现为**子集** | 逐函数标注见 [`symbolic_parity.md`](symbolic_parity.md) |
| stage0 已知不准 | ±∞ 极限用采样逼近，末位错（例：`(2x+1)/(3x-1) → 0.6666666666722222`）；`evaluate` 不认识 `ln` | 标准库在这两项上更准/更强，偏差双向锁定于 `tests/test_matha_stdlib_symbolic.py` |

## 四、跨后端差异（如实登记，不抹平）

`interp` 把运行时错误统一包装成 `MathaRuntimeError`，VM 的部分路径仍透传
Python 原生异常。黄金运行器对 stderr **异常类名**走白名单、消息主体逐字比对，
差异在报告里显式列出。

## 五、治理与工程噪声

| 编号 | 问题 | 说明 |
|---|---|---|
| NI-005 | `src/kernel/time_builtin.py` 仍用 `datetime.utcnow()` | Python 3.12+ 弃用告警；改成 timezone-aware 会改变输出串格式，需先重建黄金基线，故暂未动 |
| NI-006 | `src/__init__.py` 的惰性符号表把 `VERSION` 指向 `src.matha_main.VERSION` | 取值仍来自唯一版本源，但多绕一层；历史兼容写法（`tests/test_single_version.py` 保证不漂移） |
| NI-007 | `import src.kernel` 本身零成本，但 `src/matha_system.py` 等聚合入口仍会拉起大量模块 | 内核纯净性由 `test_kernel_purity.py` 限定在 `lexer/parser/ast_nodes/kernel/mbc`；聚合入口不属内核 |
| NI-008 | 仓库根与 `scripts/` 历史遗留的一次性调试脚本 | 已集中移入 `scripts/scratch/`；不再作为现状依据 |

## 六、性能声明的口径

本文档集**不写**任何「加速 N 倍」「快过 X 语言」的数字：当前没有可复现的基准脚本
与固定硬件口径。需要性能结论时，先补一个能被 `make check` 覆盖的基准，再写文档。
