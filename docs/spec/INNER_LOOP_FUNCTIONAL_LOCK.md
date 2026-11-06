# Matha 阶段 6d · `src/inner_loop.py` 功能锁设计与 fallback 策略

> 本文是 [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) §7 定位纪律的接续。上一轮体检结论：
> `inner_loop.py`（1251 行，全功能内循环编排器）此前**只有 fallback 测**（`test_unified_layers.py::test_run_inner_loop_fallback`），
> **主闭环逻辑无功能锁**。本阶段（6d）为其补「功能锁 + 三档诚实降级」，使 `inner_loop` 从「休眠大模块」升为「编排层已上锁」。
>
> **纪律不变**：锁定的是**编排契约**（接线正确、schema 稳定、诚实降级、绝不抛），
> **不等于**背书其集成的未背书 AI 前端（`ai_assistant`/`hal_v2` 等）的输出正确性——
> 后者仍遵 §7c「不入 README 主张、要上锁先入门禁」。锁一律用**依赖注入 + monkeypatch**，
> 不触网络、不起后台线程、不跑重 HAL，保证确定性、秒级、可入 `make check`。

---

## 一、被测真实契约（勘察坐实）

`MathaInnerLoop` 生命周期 `感知 → 认知 → 执行 → 验证 → 持久化`，公开面：

| 层 | 入口 | 依赖 | 缺失时现况 |
|---|---|---|---|
| 感知 | `on_interaction(text,result)` | 仅内部 buffer/state | — |
| 感知 | `collect_resource_snapshot()` | `engine.audit_resources()` | `engine is None → {}` |
| 感知 | `collect_interaction_summary()` | 内部 buffer | 空摘要 |
| 认知 | `cognitive_diagnose()` | `engine.self_diagnose()` | `engine is None → {"error":"引擎未初始化"}` |
| 执行 | `execute_remediation(diag)` | `engine.auto_remediate_by_message/identify_concept_gaps/auto_expand_*` | `engine is None → {"error":...}` |
| 执行 | `_handle_error_buffer()` | `assistant.parser.record_failure` | 每次处理 ≤5 条并 drain |
| 自扩展 | `self_extend_concepts()/self_extend_intents()` | `assistant.parser.{MATH_CONCEPTS,KEYWORD_MAP,VARIATION_MAP,COMMONSENSE_RULES}` | 空 buffer → 0 |
| 自升级 | `self_upgrade_check()` | `engine.get_defect_stats()` | `engine` 假 → `pending_patches=[]` |
| 自升级 | `self_upgrade_apply()` | `engine.self_diagnose/generate_patch/run_upgrade_pipeline` | `engine is None → {success:False,errors:[...]}` |
| 自升级 | `self_upgrade_rollback()` | `engine._rollback_patch()` | `engine is None → False` |
| 自优化 | `self_optimize_performance()` | `engine._growth_log/_web_search_cache` | 自适应间隔/按时间戳清 buffer |
| 验证 | `verify_fixes(pre)` | `cognitive_diagnose()` | before/after diff |
| 持久化 | `save_state(path)/load_state(path)` | 文件系统 | round-trip |
| 主循环 | `run_cycle(verbose)` | 上述全部 + 可选 v13/HAL/formula | **见下·双路径** |
| 控制 | `trigger_once/start_loop/_loop_worker/stop_loop` | 后台线程 | 线程内 `try/except` |
| 状态 | `get_status()/get_state()` | state/engine/assistant | schema 稳定 |
| 模块级 | `get_inner_loop()` 单例、`trigger_inner_loop()`、`get_loop_status()` | 组合 | — |

**关键发现 A（双路径短路）**：`run_cycle` 在 `defects_found==0 ∧ health_score≥90` 时**提前 return 仅 `diagnosis`**（[inner_loop.py](../src/inner_loop.py) L814-820），
**不执行** 执行/验证/v13自检/HAL自检/自扩展/公式生长/自升级/自优化。只有存在缺陷（或健康<90）才走完整 Phase。
⇒ 功能锁必测**两条路径**：健康短路 vs 注入缺陷逼全 Phase。

**关键发现 B（bare 实例的可选属性缺省陷阱）**：`__init__` **不设** `_ffi/_driver_mgr/_symbolic_parser/_codegen/_sse/...`（仅 `init_modules` 设）。
`run_cycle` 的 v13 自检以 `if self._ffi and ...` 起头——若 `self._ffi` 从未设则 **AttributeError**。
⇒ 注入式测试须显式 `loop._ffi=None`（短路 → 走 `skipped` 分支，不崩），HAL 检查自带 `hasattr(self,'_sse')` 守卫。

**关键发现 C（集成 phantom API·本阶段已修复）**：`unified_growth.py` `_get_inner_loop()` 曾执行 `from src.inner_loop import InnerLoop`——
但真实类名是 **`MathaInnerLoop`**，且旧 `MathaInnerLoop` **无 `run(task, max_rounds)` 方法**（只有 `run_cycle`/`trigger_once`）；
且 `_ensure_initialized()` 误以 `cls(self._interp)` 构造（而 `MathaInnerLoop.__init__` 无参）。
⇒ 修复前 `_get_inner_loop()` 恒 `ImportError → None` ⇒ `UnifiedGrowth.run_inner_loop(...)` 恒返回 `{"success": False, "error": "inner_loop 不可用"}`。
**§五 适配桥已交付**：`_get_inner_loop()` 改导入 `MathaInnerLoop`、`_ensure_initialized()` 改 `cls()` 构造、并新增 `MathaInnerLoop.run(task,max_rounds)` 语义包装，
inner_loop 现被真正接入（实跑冒烟证 `run_inner_loop` 委派至真实 `.run`、不再恒「不可用」）。

---

## 二、分层功能锁（L0–L13）

| 锁 | 目标 | 断言要点 |
|---|---|---|
| **L0 数据结构** | `LoopState`/`InteractionRecord` 默认值 | `health_score=100.0`、`status="idle"`、`cycle_count=0` |
| **L1 感知-交互** | `on_interaction` 成功/失败分流 | 成功计数 `total_interactions+1`；失败进 `_error_buffer` 且 `total_errors_caught+1`、`success=False` |
| **L2 认知-健康分** | `cognitive_diagnose` 三分阈值 | 权重 `defect·0.4+resource·0.3+interaction·0.3`；≥90 `healthy`、≥70 `degraded`、<70 `critical`；缺陷越多分越低 |
| **L3 执行-修复** | `execute_remediation` 计数 | high/critical 缺陷触发 `auto_remediate_by_message`；`resources_expanded=gaps`；state 累加 |
| **L4 执行-错误缓冲** | `_handle_error_buffer` | 单轮最多处理 5 条、其余保留在 buffer |
| **L5 自扩展** | `self_extend_concepts` | 停用词过滤、汉字 2–5 连续片段、与已有概念部分重叠才派生；`added>0` 写 `MATH_CONCEPTS` |
| **L6 自升级** | `self_upgrade_check/apply/rollback` | `check` 汇总高危补丁；`apply` 走 `generate_patch→run_upgrade_pipeline` 计数；`rollback` 调 `_rollback_patch` |
| **L7 自优化** | `self_optimize_performance` | 平均周期 >10s 放大间隔(≤120)、<2s 缩小(≥5)；按 1h 时间戳清 buffer；日志>100 截尾 |
| **L8 验证** | `verify_fixes` | before/after 缺陷差、`health_improved`、`verified=(post==0)` |
| **L9 持久化** | `save_state/load_state` | tmp_path round-trip：cycle_count/health/status 还原 |
| **L10 主循环-短路** | `run_cycle` 健康路径 | `defects=0∧health≥90` → 返回 `diagnosis`（无 `actions`/`duration`）、`status=healthy`、落盘 |
| **L11 主循环-全量** | `run_cycle` 注入缺陷 | 走全 Phase，返回含 `actions`/`verification`/`duration`/`v13_self_check`/`hal_v2_self_check` 的 superset；不抛 |
| **L12 状态接口** | `get_status/get_state` | schema 键齐；`get_state` 合入 engine/assistant 统计 |
| **L13 编排单例/入口** | `get_inner_loop` 单例、`trigger_inner_loop` | 单例 identity；`trigger` monkeypatch 后返回 run_cycle 结果 |
| **L14 run 包装** | `MathaInnerLoop.run(task,max_rounds)` | 健康短路→`rounds_run=1/stopped_early=True`；有缺陷→跑满 `max_rounds`；`max_rounds<1` 归一；单轮崩不抛（记入 results） |
| **桥接 接入锁** | `_get_inner_loop`/`run_inner_loop` | 返回真实 `MathaInnerLoop`；`run_inner_loop` 委派至 `.run`（注入桩验 `calls`）、不再恒「不可用」；模块仍无 `InnerLoop` 别名 |

---

## 三、fallback 策略（三档诚实降级·锁死「绝不抛」）

inner_loop 的降级契约分三档，全部以参数化/独立测试锁住：

- **T-A 依赖缺失档**（`engine`/`assistant`/子系统 `None`）：入口**返回安全默认或带 `"error"` 的 dict，绝不 `raise`**。
  锁：`collect_resource_snapshot→{}`、`cognitive_diagnose/execute_remediation→{"error":...}`、`self_upgrade_apply→{success:False,...}`、
  `self_upgrade_rollback→False`、`self_upgrade_check→{pending_patches:[]}`、`_cross_module_collaboration→0`（assistant/interp 缺）。
- **T-B 可选子系统异常档**（公式生长/v13 自检/HAL 自检/沙箱）：外层 `try/except` 记录、`status` 标 `degraded|error|skipped`，
  **主循环不因单模块崩而整体失败**。锁：给 formula_grow 注入抛异常的桩，`run_cycle` 仍正常返回全量 schema。
- **T-C 后台线程档**（`_loop_worker`）：每轮 `try/except` 吞异常记 log，`while self._running` 不退出；`stop_loop` 置停 + `join(timeout)` + 落盘。
  锁：不起真线程——直接调 `_loop_worker` 逻辑片段或以可控 `_running` 标志单步验证异常被吞（不阻断）。

**统一不变量**：任何入口在依赖缺失/子模块异常时，都满足「返回可解析 dict / 布尔计数 + `state` 不被污染 + 无未捕获异常」。

---

## 四、确定性测试构造法（避免脆性与重依赖）

1. **假引擎 `FakeEngine`**：仅实现 inner_loop 实际调用的方法（`self_diagnose/audit_resources/identify_concept_gaps/`
   `auto_expand_concepts/auto_expand_keywords/auto_remediate_by_message/get_growth_stats/get_defect_stats/`
   `generate_patch/run_upgrade_pipeline/_rollback_patch` + `_growth_log/_web_search_cache` 属性），并记录被调用以供断言。
2. **假助手 `FakeAssistant`**：`.parser` 提供 `MATH_CONCEPTS/KEYWORD_MAP/VARIATION_MAP/COMMONSENSE_RULES/record_failure/classify`；`.chat` 返固定 dict。
3. **bare 注入** `_make_loop(...)`：直接给实例塞 fake、并 `loop._ffi=None`（触发 v13 `skipped`、避 AttributeError）。
4. **monkeypatch 隔离**：`trigger_inner_loop` 与「全量主循环」测试 monkeypatch 掉 `self_extend_*`、`src.unified_growth.get_unified_growth`、
   `self_upgrade_check` 等重/可选块，聚焦编排接线。
5. **文件系统**：`save/load` 用 pytest `tmp_path`，不写仓库 `.matha_cache/`。
6. **零网络/零线程**：绝不 `start_loop`；`_loop_worker` 逻辑用单步模拟。

---

## 五、适配桥（本阶段已交付）

将 phantom 通道改为真实接入，三处改动：

1. **`src/inner_loop.py`**：`MathaInnerLoop` 新增 `run(self, task, max_rounds=3, verbose=False)` 语义包装（见 L14）——
   惰性 `init_modules`（仅当 `_engine is None`，失败则诚实降级不抛）→ 至多跑 `max_rounds` 轮 `run_cycle` → 命中健康短路即提前收敛 →
   返回稳定 schema `{success, task, rounds_run, stopped_early, health_score, status, cycle_count, results}`。**不把 task 注入感知缓冲**（避免污染健康分而破坏短路）。
2. **`src/unified_growth.py` `_get_inner_loop()`**：`from src.inner_loop import MathaInnerLoop`（真实类名），不再恒 `ImportError→None`。
3. **`src/unified_growth.py` `_ensure_initialized()`**：`MathaInnerLoop.__init__` 无参→改 `cls()` 构造（不再 `cls(self._interp)`）；若有 interp 则作为共享属性注入。

`run_inner_loop` 本体不变（仍 `self._inner_loop.run(task,max_rounds)`，保留 `_inner_loop` 为 `None` 时的真降级分支），但现在 `_inner_loop` 为真实例，故不再恒「不可用」。

- **诚实锁**：`tests/test_inner_loop_lock.py::test_bridge_get_inner_loop_returns_real_class`、`test_bridge_run_inner_loop_delegates_to_run`、
  `test_bridge_phantom_api_is_gone` 钉新契约；`tests/test_unified_layers.py::test_run_inner_loop_wired`（原 `_fallback`）由「断不可用」改为「注入桩验委派」。
- **未改动边界**：本桥只接通“编排委派”，不背书 `init_modules` 所拉起的重型 AI 前端/HAL 输出正确性（§7c 不变）；真驱动完整循环仍遵 §三 T-A/T-B/T-C 诚实降级。

---

## 六、门禁接入与验收

- 新增 `tests/test_inner_loop_lock.py` 入常规 pytest 套件（`make check` 采集），全部确定性、离线、毫秒级。
- 验收：新测试全绿（含 L14 run 包装 + 适配桥接入锁）；`test_unified_layers.py`（含改造后的 `test_run_inner_loop_wired`）零回归；`dep_audit` 违规 0（`inner_loop` 属宿主侧、非 L1 内核链，
  其 `init_modules` 内**函数级懒 import** AI 前端合规，不违 L1 纯净锁；新增 `run` 包装不引入任何顶层依赖）；`test_unbacked_channel_honesty.py` 不受影响。
- 定位升格：体检报告中 `inner_loop.py` 由「⚠ 主循环无功能锁」改为「✅ 编排层已上锁；AI 前端/HAL 仍未背书（§7c 不变）」。
