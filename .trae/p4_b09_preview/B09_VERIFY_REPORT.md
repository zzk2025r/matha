# 《b09 底层重构验证报告》（P4 预备资产）

> 定位：本报告与同目录工件是 **P4 预备资产**，不进入、也不修改 `make check` 六项主门禁。
> 主线提交 `9ed13d6`（P3）之后的工作树含一枚**默认休眠**的开关补丁
> （`b09_fuse_preview.patch`，仅动 `src/mbc/compiler.py`）；开关关闭时主线字节码
> 与提交态逐字节等价，开关开启时才启用 b09 语法糖融合发射。
> 诚实口径：本报告同时登记 b09 收益与**定点漂移的真实读数**，不掩盖任何红灯。

## 1. 任务与方案边界

- 目标：消除 P3 登记的 b09 欠账——`for` 语法糖与列表推导中**手写**的
  `get(xs)(i)` / `append(res)(e)` 两步 `CALL 1` 展开（发射器位置：
  `_emit_for_stmt` 750-754、`_emit_list_comp` 815-819/828-832，提交态行号）。
- 用户约束「不修改宿主侧与自举侧源码」与「改变字节码形状」在逻辑上不可同时成立
  （字节码只能由发射器决定），故本资产采用**休眠开关**形态：
  `MATHA_B09_FUSE=1` 显式开启，默认路径与历史发射逐字节等价；
  主线门禁不受该补丁存在的影响。
- 「绕过元数表」被修正为「走同一张元数表的安全闸」：硬编码 LOAD_GLOBAL 内建名
  必须让位于顶层 `func get/append` 的遮蔽语义（见 §4 安全闸证据）。
  `len(xs)` 不融合——`len` 是原生变参内建而非柯里化内建，`CALL 2` 会调用错误的函数。

## 2. 验证矩阵（全部实测，2026-10-30，同机）

| # | 判据 | 工具 | 结果 |
|---|------|------|------|
| 1 | OFF 态字节码 = HEAD 逐字节 | `b09_fuse_compare.py`（HEAD worktree `D:\trae_b09_ref` 导出参照） | 10 例语料 `byte_mismatch=无` |
| 2 | ON 态运行值 = HEAD | 同上 | 10 例 `value_mismatch=无` |
| 3 | ON 态形状确实融合 | `diff_shapes.py` | 9/10 例 `shape_diff=True`（`get`→`CALL 2`、`append`→`CALL 2`） |
| 4 | 遮蔽安全闸 | `shadow_get_funcdef` 例 | `shape_diff=False`——顶层 `func get` 存在时恒走历史路径 |
| 5 | b09 收益（紧邻 A/B，7 重复×4 轮，N=50000） | `fuse_ab.py` | OFF min 858.8/863.0ms，ON min 724.5/724.3ms → **−15.6% / −16.0%**（median −16.0/−15.9%） |
| 6 | 定点漂移真实读数（ON 态） | `drift_readout.py` | `test_mbc_bootstrap + test_mbc_vm_matha`：**869 passed / 1 failed**，唯一红项 `test_m2_stage2_equals_stage3[for_loop]`；**黄金 39/39 通过** |
| 7 | 主线门禁（OFF 态默认） | `python scripts/check.py` | 首轮 99.98%（唯一红项为 doc_facts 核心行数漂移，系补丁自身 +31 行所致，非开关语义问题）；已刷新 ARCHITECTURE 31,041→31,072 后复跑全量 `check.py`，读数见 `gate_off_final.log` 尾部汇总 |
| 8 | doc_facts 复验 | `pytest tests/test_doc_facts.py` | 18/18 通过（行数刷新后） |

## 3. 关键定性结论

- 融合是**纯形状优化**：值语义在 10 例语料与全部 39 个黄金用例上零漂移，
  ON 态黄金全绿证明 vm↔interp 对照不因新形状破功。
- 定点漂移**精确局限在 for 发射面**：ON 态 870 例定点测试只红 1 例
  （stage2 宿主发射 `CALL 2` vs stage3 自举发射 `CALL 1+CALL 1`），
  这正是 P3 预告的「单侧改发射器必然破定点」的直接证据，而非广泛坍塌。
- 收益量级与 b04（−10.0%）同档略高：b09 循环体同时吃 `get` 融合，
  且 50000 次迭代摊薄了 `range(0)(N)` 的固定开销。

## 4. 补丁内容清单（`b09_fuse_preview.patch`，仅 src/mbc/compiler.py）

1. `import os` + 模块级 `_B09_FUSE = os.environ.get("MATHA_B09_FUSE","")=="1"`（含休眠开关注释块）。
2. `compile_program` 新增 `self._user_fn_names = set(_scan_fn_arities(program))`（遮蔽安全闸数据）。
3. 新方法 `_emit_curried_builtin(name, temps, code, *, fuse, last_expr, last_expr_scope)`：
   `fuse=False` 分支逐字节复刻历史发射；`fuse=True` 且 `name not in _user_fn_names`
   时发单条 `CALL len(temps)`。
4. `_emit_for_stmt` 元素读取、`_emit_list_comp` 元素读取与 append 收集三处改走新方法。

## 5. P4 正式合并的前置条件（本报告不代办）

1. `matha/compiler_matha.matha` 的 for/listcomp 发射处同步产出 `CALL N`
   （双侧同序同形状），并同步 `_预扫元数` 相关注释口径。
2. `MATHA_B09_FUSE` 开关退役（默认常开），`tests/test_curried_builtin_paths.py`
   增补语法糖融合的形状锁与双侧同值锁。
3. 全量 `make check` 六项 100% + 黄金 39 + `bench.py --selftest` 复验。

## 6. 工件清单

- `b09_fuse_preview.patch` —— 独立变更补丁（上文 §4 清单，仅含 b09 融合发射）
- `sysenv_fold_preview.patch` —— sys_env 折叠与恒定条件剪枝的独立补丁（仅含 §7 实现，
  基线为 b09 开关已入库后的提交态）——两枚开关互相独立，可各自转正或各自删除
  （本次重生成同时修掉了旧补丁由 PowerShell 重定向引入的 UTF-8 BOM 产物）
- `b09_fuse_compare.py` —— OFF/ON 字节码+值对照工具（HEAD worktree 参照法）
- `ref_head.json` / `ws_off.json` / `ws_on.json` —— 10 例语料三份 dump 证据
  （`ref_head.json` 与 `ws_off.json` 逐字节相同属预期：前者由参照侧产出、后者由
  工作树 OFF 态产出，两值一致正是等价证据本身；曾有一份无效 attempt 的
  `ref_head2.json` 已删除）
- `diff_shapes.py`、`fuse_ab.py`、`drift_readout.py`、`drift_on_report.txt` —— 取证脚本与原始读数
- `gate_off_final.log` —— OFF 态主门禁日志
- `sysenv_verify.py` —— sys_env 编译期折叠与恒定条件剪枝验证（§7）
- `off_equiv_ref.py` —— OFF 态逐字节等价的可信对照（importlib 加载旧版模块，
  导出的 `compiler_ref.py` 及其模块缓存**用完自删**，不留生成物）
- `se_native.matha` / `sysenv_native_proof.py` —— native 端到端实证（§7 末，
  生成的三枚 exe 在 `finally` 中自删，不入库）
- `gate_sysenv.log` / `gate_sysenv_final.log` / `gate_sysenv_commit.log` —— 折叠落地后的
  门禁读数（99.98% 那份为文档滞后红；后两份为全绿终值与**待提交态**重跑，属两次
  独立运行：通过项逐行完全一致（4071/14/11/39/1/38），差异只在耗时数字）
- 上述门禁日志原由 PowerShell `>` 重定向产出为 **UTF-16**（git 视为二进制），
  已统一转存 UTF-8；旧补丁的 BOM 同属这一重定向产物，一并修掉
- 生成的 exe / `compiler_ref.py` / `__pycache__` 属可再生成物，**不入库**（实证脚本
  结束即清理，重跑可复现）

（本目录为工作区 `.trae` 预备资产，随 P4 决策转正或删除；不加入 tests/ 或 golden_tests/。）

## 7. sys_env 追加需求（编译期门控，同一休眠手法）

需求原形：在自举编译器底层硬编 `sys_env(key, default)` 对接 OS API、「完全切断宿主
依赖」，并用它写 b09 的快/慢路径分支。不可成立的两点（已实测根据）：

1. native 不拥有自己的编译器：`compile_to_exe(source) = emit_exe(compile_source(source))`
   （src/mbc/native.py:10577），它吃的是宿主编译器的字节码；「植入自举编译器底层、
   切断宿主依赖」在现有架构里指向一个不存在的层。
2. 「运行期按环境选字节码形状」在本架构下不存在：指令形状由发射器在编译期决定，
   运行期没有可切换的第二套形状；若把 `if sys_env(...)` 写成运行期分支，只会给
   热循环每次迭代多加一次全局查找+比较+跳转，性能为负。

**实际落地（`MATHA_SYSENV_FOLD=1`，默认关闭）**：

- `_fold_sys_env(callee, args)`：仅接受字面量键（与可选字面量默认值）→
  `os.environ.get` → `PUSH_CONST`；否则返回 None，绝不静默猜测。
- `_const_expr_value(node)`：常量求值（字面量 + 折叠命中的 sys_env），供剪枝判据用。
- `_emit_if_stmt` 恒定条件剪枝：命中则只发射选中分支（含带 `else` 的两臂形态，
  即用户伪代码的写法）；假分支且留值时发 `PUSH_NULL`，与历史「无 else 落空压 null」
  同指令。仅处理单比较，不递归布尔代数。
- 开关关闭时 `sys_env` 完全不存在（历史形状：LOAD_GLOBAL + CALL 1 + CALL 1，运行期报
  「未定义变量 'sys_env'」）。

**为何不注册成 VM 运行期内建**（定点与契约考虑）：运行期查 env 必经宿主 `os.environ`；
而新增内建会进 `_default_builtins` 全局表、改变自举编译器可见符号面 → 定点与
`test_native_concurrency_contract.py` 的 API 封闭基线一起红。编译期折叠把运行期查询
消灭在编译期，因此 **native 无需 `GetEnvironmentVariableW`，`_APIS` 一动不动**。

**实测读数（`python .trae/p4_b09_preview/sysenv_verify.py`，均带环境子进程）**：7/7 通过。

| 判据 | 读数 |
|---|---|
| A1 缺省取 default | `outputs=["dflt"]`、常量池无 `sys_env`、`call_argcs=[1]` |
| A2 命中环境变量 | `outputs=["hello"]`（真读 OS env，非脚本自说） |
| B1 未开启→原路径 | `outputs=["1"]`、**`n_jz=0`**、`call_argcs=[1]`（分支已剪） |
| B2 开启→快路径 | `outputs=["99"]`、**`n_jz=0`**、`call_argcs=[1]` |
| C1 非字面量键 | 编译期 `RuntimeError：…必须是字符串字面量…` |
| D1/D2 开关关闭 | 历史未定义变量路径，且**不读环境**（无副作用泄漏） |

**OFF 态逐字节等价（方法已修正）**：首轮用 `git worktree` 取参照的尝试有一次**无效**
（`cd` 到工作区外失败 → 参照其实来自工作树自身，等于自己对自己），已废弃该读数。
改用 `off_equiv_ref.py`：以 `git show 9b5606b:src/mbc/compiler.py` 导出旧版文件，用
importlib 在**同一 src 包环境**下加载为独立模块，与新编译器编译同一 10 例语料逐指令
对比 → `byte_mismatch=无 value_mismatch=无`（全程不改动工作树）。
§ 2 第 1 行（b09 开关那次）的 worktree 读数当时 `cd` 成功，仍然有效。

针对性回归：doc_facts + curried_builtin_paths + native_concurrency_contract +
kernel_purity = **88 passed**；全量 `make check` 最终轮 **100.00%（4174/4174，
失败 0，SKIP 1=工具链缺口 by-design）**，见 `gate_sysenv_final.log`。
中间一轮 `gate_sysenv.log` 读数 99.98%（唯一红项 doc_facts 核心行数），原因是
那轮 tests 阶段读到的是尚未刷新的 ARCHITECTURE 数字（文档滞后，非代码问题），
如实保留不删除。提交态另行复跑一次（`gate_sysenv_commit.log`）仍为 **100.00%**，
确认本次同时修改的预备资产未影响门禁结果。

**native 端到端实证（`python .trae/p4_b09_preview/sysenv_native_proof.py`）：4/4 通过**。
这是「折叠路线让 native 免扩 OS API」的直接证据，也钉死了门控的语义边界：

| # | 场景 | 实测 | 判据 |
|---|------|------|------|
| N1 | 折叠开 + 编译期无 env → 编 exe 并跑 | 编译 rc=0；exe rc=0，输出 `1` | 烘进原路径 |
| N2 | **同一枚 exe** 换运行期 env=1 再跑 | rc=0，输出仍 `1` | 门控属**编译期**，运行期不可选 |
| N3 | 折叠开 + 编译期 env=1 → 编 exe 并跑 | 编译 rc=0；exe rc=0，输出 `99` | 快路径烘进机器码，全程无 OS API |
| N4 | 折叠关（休眠态）→ 编 exe 并跑 | 编译 rc=0（字节码是 `LOAD_GLOBAL sys_env`）；**exe 运行期 rc=1**，报「未定义变量」，无合法输出 | 与 VM 口径一致，符合 P3「对未解析符号绝不静默造值」契约 |

N2 是与用户设想的关键差异，必须写实：用户伪代码里的 `else` 分支「保持门禁全绿」
在编译期折叠下成立（默认环境就走原路径），但「同一枚产物在运行期切快/慢」不成立——
分支在选择发射哪条路径时就已从字节码消失（`sysenv_verify.py` 的 B1/B2 读数 `n_jz=0`
即此证据）。N4 初版我曾把断言方向写错（预期休眠态 native **编译期**就拒绝），实测
证明它是编译过、运行期拒给值，遂按真实行为改写判据；这不是漏洞，而是与 VM 一致的
失败口径。
