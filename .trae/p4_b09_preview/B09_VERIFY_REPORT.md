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

- `b09_fuse_preview.patch` —— 独立变更补丁（上文 §4 清单）
- `b09_fuse_compare.py` —— OFF/ON 字节码+值对照工具（HEAD worktree 参照法）
- `ref_head.json` / `ws_off.json` / `ws_on.json` —— 10 例语料三份 dump 证据
- `diff_shapes.py`、`fuse_ab.py`、`drift_readout.py`、`drift_on_report.txt` —— 取证脚本与原始读数
- `gate_off.log` —— OFF 态主门禁日志

（本目录为工作区 `.trae` 预备资产，随 P4 决策转正或删除；不加入 tests/ 或 golden_tests/。）
