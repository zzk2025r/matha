# Matha 文档索引（现状 · v4.6.0）

这里是**权威文档的唯一入口**。`docs/` 顶层只保留下面这 10 份现状文档；
重构过程中产生的 118 份一次性报告已移入 [`history/`](history/)，
它们记录的是当时的状态，**不作为现状依据**。

语言规格（词法/语法/类型/语义/EBNF，00–21 共 22 份）在 [`spec/`](spec/)。

## 一、现状文档

| 文档 | 内容 | 由谁保证不过期 |
|------|------|----------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 唯一核心主线、内核白名单、插件层、门禁口径 | `tests/test_doc_facts.py`（主线串必须出现） |
| [DEP_BASELINE.md](DEP_BASELINE.md) | 依赖方向图 + 违规清单 | `scripts/dep_audit.py` 重新生成 |
| [ast_vm_gap.md](ast_vm_gap.md) | AST × VM 覆盖矩阵 + `.matha` 语言口径 | `scripts/ast_vm_matrix.py --write` + `tests/test_ast_vm_gap.py` |
| [symbolic_parity.md](symbolic_parity.md) | 内核符号实现 vs sympy（逐函数标注） | `tests/test_kernel_symbolic.py` |
| [matha_stdlib_symbolic.md](matha_stdlib_symbolic.md) | 阶段 4：符号微积分的 `.matha` 标准库 + 逐位对拍 + 偏差表 | `tests/test_matha_stdlib_symbolic.py` |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | 未达成项如实列表 | 手工维护，每条都有可执行判据 |
| [OFFLINE_GUIDE.md](OFFLINE_GUIDE.md) | 离线包部署与使用 | — |
| [BUILD_GUIDE.md](BUILD_GUIDE.md) | PyInstaller 独立可执行文件构建 | — |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史（旧版本号只允许出现在这里） | — |
| index.md | 本页 | `tests/test_doc_facts.py`（顶层文档数 ≤ 10） |

## 二、数字从哪里来

```bash
python scripts/repo_facts.py          # 人读
python scripts/repo_facts.py --json   # 机器读
```

文档与代码里的数字一旦漂移，`tests/test_doc_facts.py` 就红。
唯一版本源是 [`src/__version__.py`](../src/__version__.py)（守门：`tests/test_single_version.py`）。

## 三、质量口径

```bash
make check        # 六项串成一条链，对外只产出一个通过率数字
make check-lite   # 不跑需要 nasm/link 的机器码对拍
```

跑不成一律记失败，不记跳过；跳过项从分母剔除但显式打印台数。
