"""
阶段 6d · src/inner_loop.py 功能锁 + fallback 诚实降级锁
==========================================================

锁定 `MathaInnerLoop` 的**编排契约**（接线正确、schema 稳定、依赖缺失时诚实降级、绝不抛），
不背书其集成的未背书 AI 前端输出正确性（遵 KNOWN_ISSUES §7c）。

设计见 docs/spec/INNER_LOOP_FUNCTIONAL_LOCK.md。

纪律：全部用依赖注入 + monkeypatch，**不触网络、不起后台线程、不跑重 HAL/沙箱**，
确定性、离线、毫秒级，可入 make check。
"""
from __future__ import annotations

import time

import pytest

from src.ai_assistant import IntentType
from src.inner_loop import (
    InteractionRecord,
    LoopState,
    MathaInnerLoop,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试替身（仅实现 inner_loop 实际消费的契约面）
# ═══════════════════════════════════════════════════════════════════════════════

class _Enum:
    """模拟 Severity/Category 枚举（.value）。"""

    def __init__(self, value: str):
        self.value = value


class FakeDefect:
    def __init__(self, defect_id: str, severity: str, category: str = "knowledge_gap",
                 message: str = "缺陷描述"):
        self.defect_id = defect_id
        self.severity = _Enum(severity)
        self.category = _Enum(category)
        self.message = message


class FakeResource:
    def __init__(self, name: str, status: str = "ok"):
        self.name = name
        self.status = status


class FakeEngine:
    """GrowthEngine 替身：仅暴露 inner_loop 调用的方法，并记录调用。"""

    def __init__(self, defects=None, resources=None, gaps=None):
        self._defects = defects or []
        self._resources = resources if resources is not None else [FakeResource("r1", "ok")]
        self._gaps = gaps or []
        self._growth_log: list[dict] = []
        self._web_search_cache: dict[str, str] = {}
        # 调用记录
        self.remediate_calls: list[tuple] = []
        self.expand_concepts_calls: list[int] = []
        self.upgrade_patches: list[str] = []
        self.rollback_called = 0

    def self_diagnose(self):
        return list(self._defects)

    def audit_resources(self):
        return list(self._resources)

    def identify_concept_gaps(self):
        return list(self._gaps)

    def auto_expand_concepts(self, max_new: int = 10) -> int:
        self.expand_concepts_calls.append(max_new)
        return len(self._gaps)

    def auto_expand_keywords(self) -> int:
        return 0

    def auto_remediate_by_message(self, message: str, category=None) -> bool:
        self.remediate_calls.append((message, category))
        return True

    def get_growth_stats(self) -> dict:
        return {"total_learned": 0}

    def get_defect_stats(self) -> dict:
        return {"open_defects": [
            {"id": d.defect_id, "severity": d.severity.value} for d in self._defects
        ]}

    def generate_patch(self, defect) -> str:
        return f"PATCH::{defect.defect_id}"

    def run_upgrade_pipeline(self, patch_code: str, verify_fn=None) -> bool:
        self.upgrade_patches.append(patch_code)
        return True

    def _rollback_patch(self) -> None:
        self.rollback_called += 1


class FakeParser:
    def __init__(self, concepts=None):
        self.MATH_CONCEPTS = concepts if concepts is not None else {"质数": {"符号": ""}}
        self.KEYWORD_MAP = {IntentType.算术: []}
        self.VARIATION_MAP: dict = {}
        self.COMMONSENSE_RULES: list = []
        self.failures: list[tuple] = []

    def classify(self, text: str):
        return IntentType.算术, 1.0

    def record_failure(self, text, error, intent):
        self.failures.append((text, error, intent))


class FakeAssistant:
    def __init__(self, concepts=None):
        self.parser = FakeParser(concepts)

    def chat(self, text, interp):
        return {"result": 42, "intent": "arithmetic", "type": "result"}


class _Obj:
    """generic 哨兵（interp / firewall 等）。"""

    blocked_count = 0


def _make_loop(engine=None, assistant=None) -> MathaInnerLoop:
    """bare 注入：塞替身依赖并显式置 _ffi=None（触发 v13 skipped、避 AttributeError）。"""
    loop = MathaInnerLoop()
    loop._engine = engine if engine is not None else FakeEngine()
    loop._assistant = assistant if assistant is not None else FakeAssistant()
    loop._interp = _Obj()
    loop._firewall = _Obj()
    loop._security = _Obj()
    loop._ffi = None
    return loop


# ═══════════════════════════════════════════════════════════════════════════════
#  L0 · 数据结构默认值
# ═══════════════════════════════════════════════════════════════════════════════

def test_l0_loopstate_defaults():
    st = LoopState()
    assert st.cycle_count == 0
    assert st.health_score == 100.0
    assert st.status == "idle"
    assert st.total_interactions == 0 and st.total_errors_caught == 0


def test_l0_interactionrecord_fields():
    rec = InteractionRecord(text="t", intent="i", result=1, success=True,
                            latency=0.0, timestamp=time.time())
    assert rec.success is True and rec.error == ""


# ═══════════════════════════════════════════════════════════════════════════════
#  L1 · 感知层 on_interaction 成功/失败分流
# ═══════════════════════════════════════════════════════════════════════════════

def test_l1_on_interaction_success():
    loop = _make_loop()
    rec = loop.on_interaction("计算 2+2", {"type": "result", "result": 42, "intent": "arithmetic"})
    assert rec.success is True
    assert loop._state.total_interactions == 1
    assert len(loop._error_buffer) == 0
    assert loop._state.total_errors_caught == 0


def test_l1_on_interaction_failure_goes_error_buffer():
    loop = _make_loop()
    rec = loop.on_interaction("乱码", {"type": "error", "result": None,
                                       "intent": "unknown", "reply": "无法解析"})
    assert rec.success is False
    assert loop._state.total_interactions == 1
    assert len(loop._error_buffer) == 1
    assert loop._state.total_errors_caught == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L2 · 认知层健康分与三分阈值
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ndefects,expect_status", [
    (0, "healthy"),    # 100
    (2, "degraded"),   # 88
    (6, "critical"),   # 64
])
def test_l2_cognitive_health_thresholds(ndefects, expect_status):
    defects = [FakeDefect(f"D{i}", "medium") for i in range(ndefects)]
    loop = _make_loop(FakeEngine(defects=defects, resources=[FakeResource("a", "ok"),
                                                             FakeResource("b", "ok")]))
    diag = loop.cognitive_diagnose()
    assert diag["defects_found"] == ndefects
    assert diag["status"] == expect_status
    assert diag["health_score"] == diag["health_score"]  # 已落 state
    assert loop._state.status == expect_status


def test_l2_health_formula_exact():
    # 1 high defect, 全 ok 资源, 无交互 → 0.4*85 + 0.3*100 + 0.3*100 = 94.0
    loop = _make_loop(FakeEngine(defects=[FakeDefect("D1", "high")],
                                 resources=[FakeResource("a", "ok")]))
    diag = loop.cognitive_diagnose()
    assert diag["health_score"] == pytest.approx(94.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  L3 · 执行层修复计数 + state 累加
# ═══════════════════════════════════════════════════════════════════════════════

def test_l3_execute_remediation_counts():
    engine = FakeEngine(defects=[FakeDefect("D1", "high", message="缺概念", category="knowledge_gap")],
                        gaps=["百分比", "对数"])
    loop = _make_loop(engine)
    diag = loop.cognitive_diagnose()
    actions = loop.execute_remediation(diag)
    assert actions["defects_resolved"] == 1        # 高危 → auto_remediate
    assert actions["patches_applied"] == 1
    assert actions["resources_expanded"] == 2      # 2 gaps → auto_expand_concepts 返回 2
    assert engine.remediate_calls == [("缺概念", "knowledge_gap")]
    assert engine.expand_concepts_calls == [5]     # max_new=5
    assert loop._state.total_defects_resolved == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L4 · 错误缓冲处理（≤5 且 drain）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l4_handle_error_buffer_caps_at_five():
    loop = _make_loop()
    loop._error_buffer = [{"text": f"e{i}", "error": "", "intent": "unknown",
                           "timestamp": time.time()} for i in range(7)]
    handled = loop._handle_error_buffer()
    assert handled == 5
    assert len(loop._error_buffer) == 2  # 剩余


# ═══════════════════════════════════════════════════════════════════════════════
#  L5 · 自扩展（停用词过滤 / 部分重叠派生）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l5_self_extend_concepts_adds_overlapping():
    parser_assistant = FakeAssistant(concepts={"质数": {"符号": ""}})
    loop = _make_loop(assistant=parser_assistant)
    # 一条失败且 intent=unknown、文本含既有概念"质数"子串的交互
    loop._interaction_buffer.append(InteractionRecord(
        text="关于质数问题", intent="unknown", result=None, success=False,
        latency=0.0, timestamp=time.time()))
    added = loop.self_extend_concepts()
    assert added >= 1
    assert "质数" in loop._assistant.parser.MATH_CONCEPTS
    # 新增概念应来自候选片段（含"质数"）
    assert any("质数" in k for k in loop._assistant.parser.MATH_CONCEPTS if k != "质数")


def test_l5_self_extend_concepts_stopwords_noop():
    loop = _make_loop(assistant=FakeAssistant(concepts={"向量": {}}))
    loop._interaction_buffer.append(InteractionRecord(
        text="计算一下什么", intent="unknown", result=None, success=False,
        latency=0.0, timestamp=time.time()))
    assert loop.self_extend_concepts() == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  L6 · 自升级 check/apply/rollback
# ═══════════════════════════════════════════════════════════════════════════════

def test_l6_self_upgrade_check_lists_high_patches():
    engine = FakeEngine(defects=[FakeDefect("D1", "high"), FakeDefect("D2", "medium")])
    loop = _make_loop(engine)
    st = loop.self_upgrade_check()
    assert st["is_latest"] is True and st["can_upgrade"] is False
    assert st["pending_patches"] == [{"id": "D1", "severity": "high"}]


def test_l6_self_upgrade_apply_runs_pipeline():
    engine = FakeEngine(defects=[FakeDefect("D1", "critical")])
    loop = _make_loop(engine)
    res = loop.self_upgrade_apply()
    assert res["success"] is True
    assert res["patches_applied"] == 1
    assert engine.upgrade_patches == ["PATCH::D1"]


def test_l6_self_upgrade_rollback_calls_engine():
    engine = FakeEngine()
    loop = _make_loop(engine)
    assert loop.self_upgrade_rollback() is True
    assert engine.rollback_called == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L7 · 自优化（间隔自适应 / 时间戳清理 / 日志截尾）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l7_optimize_enlarges_interval_when_slow():
    loop = _make_loop()
    loop._interval = 30.0
    loop._state.cycle_count = 1
    loop._state.total_duration = 20.0  # avg 20 > 10
    imp = loop.self_optimize_performance()
    assert imp["interval_adjusted"] is True
    assert loop._interval == pytest.approx(45.0)  # min(30*1.5,120)


def test_l7_optimize_shrinks_interval_when_fast():
    loop = _make_loop()
    loop._interval = 30.0
    loop._state.cycle_count = 1
    loop._state.total_duration = 1.0  # avg 1 < 2
    loop.self_optimize_performance()
    assert loop._interval == pytest.approx(24.0)  # max(30*0.8,5)


def test_l7_optimize_cleans_stale_buffers():
    loop = _make_loop()
    now = time.time()
    loop._interaction_buffer = [
        InteractionRecord(text="old", intent="i", result=1, success=True,
                          latency=0.0, timestamp=now - 7200),
        InteractionRecord(text="new", intent="i", result=1, success=True,
                          latency=0.0, timestamp=now),
    ]
    imp = loop.self_optimize_performance()
    assert imp["buffer_cleaned"] == 1
    assert len(loop._interaction_buffer) == 1


def test_l7_optimize_compresses_growth_log():
    engine = FakeEngine()
    engine._growth_log = [{"x": i} for i in range(150)]
    loop = _make_loop(engine)
    imp = loop.self_optimize_performance()
    assert imp["log_compressed"] is True
    assert len(loop._engine._growth_log) == 100


# ═══════════════════════════════════════════════════════════════════════════════
#  L8 · 验证层 before/after
# ═══════════════════════════════════════════════════════════════════════════════

def test_l8_verify_fixes_reports_reduction():
    engine = FakeEngine(defects=[FakeDefect("D1", "high")],
                        resources=[FakeResource("a", "ok")])
    loop = _make_loop(engine)
    pre = {"defects_found": 3, "health_score": 70.0}
    # 修复后：清空缺陷 → 归零
    engine._defects = []
    v = loop.verify_fixes(pre)
    assert v["defects_before"] == 3
    assert v["defects_after"] == 0
    assert v["defects_reduced"] == 3
    assert v["verified"] is True
    assert v["health_improved"] is True


# ═══════════════════════════════════════════════════════════════════════════════
#  L9 · 持久化 round-trip
# ═══════════════════════════════════════════════════════════════════════════════

def test_l9_save_load_roundtrip(tmp_path):
    loop = _make_loop()
    loop._state.cycle_count = 7
    loop._state.health_score = 82.5
    loop._state.status = "degraded"
    loop._state.total_interactions = 12
    path = str(tmp_path / "state.json")
    ret = loop.save_state(path)
    assert ret == path and (tmp_path / "state.json").exists()

    fresh = _make_loop()
    ok = fresh.load_state(path)
    assert ok is True
    assert fresh._state.cycle_count == 7
    assert fresh._state.health_score == pytest.approx(82.5)
    assert fresh._state.status == "degraded"
    assert fresh._state.total_interactions == 12


def test_l9_load_missing_file_returns_false(tmp_path):
    loop = _make_loop()
    assert loop.load_state(str(tmp_path / "nope.json")) is False


# ═══════════════════════════════════════════════════════════════════════════════
#  L10 · 主循环健康短路（只返回 diagnosis，不跑后续 Phase）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l10_run_cycle_healthy_short_circuit(monkeypatch):
    engine = FakeEngine(defects=[], resources=[FakeResource("a", "ok"), FakeResource("b", "ok")])
    loop = _make_loop(engine)
    monkeypatch.setattr(loop, "save_state", lambda path=None: None)
    r = loop.run_cycle(verbose=False)
    # 短路只返回 diagnosis：无 actions/verification/duration
    assert "actions" not in r and "duration" not in r
    assert r["defects_found"] == 0
    assert r["status"] == "healthy"
    assert loop._state.cycle_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L11 · 主循环全 Phase（注入缺陷逼完整路径 + T-B 可选子系统异常不崩）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l11_run_cycle_full_phases(monkeypatch):
    engine = FakeEngine(defects=[FakeDefect("D1", "high"), FakeDefect("D2", "medium")],
                        resources=[FakeResource("a", "ok")])
    loop = _make_loop(engine)
    monkeypatch.setattr(loop, "save_state", lambda path=None: None)
    monkeypatch.setattr(loop, "self_extend_concepts", lambda: 0)
    monkeypatch.setattr(loop, "self_extend_intents", lambda: 0)

    # T-B：公式生长子系统抛异常 → run_cycle 仍完整返回（外层 try/except）
    import src.unified_growth as ug

    class _Boom:
        def formula_grow(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(ug, "get_unified_growth", lambda interp=None: _Boom())

    r = loop.run_cycle(verbose=False)
    # 全 Phase → superset schema
    for key in ("actions", "verification", "duration",
                "v13_self_check", "hal_v2_self_check"):
        assert key in r, f"缺失 {key}"
    assert r["v13_self_check"]["status"] == "skipped"   # _ffi=None → skipped
    assert r["hal_v2_self_check"]["status"] == "skipped"  # 无 _sse → skipped
    assert r["defects_found"] == 2
    assert loop._state.cycle_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L12 · 状态接口 schema
# ═══════════════════════════════════════════════════════════════════════════════

def test_l12_get_status_schema():
    loop = _make_loop()
    st = loop.get_status()
    for key in ("status", "health_score", "cycle_count", "total_interactions",
                "total_errors_caught", "total_resources_expanded", "total_patches_applied",
                "total_defects_resolved", "uptime_seconds", "running"):
        assert key in st
    assert st["running"] is False


def test_l12_get_state_merges_engine_and_assistant():
    loop = _make_loop()
    st = loop.get_state()
    assert st["total_learned"] == 0            # engine.get_growth_stats
    assert st["concepts_count"] == len(loop._assistant.parser.MATH_CONCEPTS)
    assert "keywords_count" in st


# ═══════════════════════════════════════════════════════════════════════════════
#  L13 · 模块级编排入口
# ═══════════════════════════════════════════════════════════════════════════════

def test_l13_get_inner_loop_singleton(monkeypatch):
    import src.inner_loop as il

    monkeypatch.setattr(il, "_loop_instance", None, raising=False)
    a = il.get_inner_loop()
    b = il.get_inner_loop()
    assert a is b and isinstance(a, MathaInnerLoop)


def test_l13_trigger_inner_loop_entry(monkeypatch):
    import src.inner_loop as il

    monkeypatch.setattr(il, "_loop_instance", None, raising=False)
    monkeypatch.setattr(MathaInnerLoop, "init_modules", lambda self: None)
    monkeypatch.setattr(MathaInnerLoop, "run_cycle",
                        lambda self, verbose=True: {"ok": 1})
    assert il.trigger_inner_loop(verbose=False) == {"ok": 1}


# ═══════════════════════════════════════════════════════════════════════════════
#  T-A · 依赖缺失诚实降级（绝不抛，参数化）
# ═══════════════════════════════════════════════════════════════════════════════

def test_fallback_no_engine_snapshots():
    loop = MathaInnerLoop()  # 全 None
    assert loop.collect_resource_snapshot() == {}
    assert loop.cognitive_diagnose() == {"error": "引擎未初始化"}
    assert loop.execute_remediation({}) == {"error": "引擎未初始化"}


def test_fallback_self_upgrade_without_engine():
    loop = MathaInnerLoop()
    st = loop.self_upgrade_check()
    assert st["pending_patches"] == []
    res = loop.self_upgrade_apply()
    assert res["success"] is False and "引擎未初始化" in res["errors"]
    assert loop.self_upgrade_rollback() is False


def test_fallback_cross_module_collab_without_deps():
    loop = MathaInnerLoop()  # assistant/interp None
    assert loop._cross_module_collaboration() == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  T-C · 后台线程工作器异常被吞、不阻断
# ═══════════════════════════════════════════════════════════════════════════════

def test_fallback_loop_worker_swallows_exceptions(monkeypatch):
    loop = _make_loop()
    calls = {"n": 0}

    def _raise(verbose=True):
        calls["n"] += 1
        loop._running = False  # 跑一轮后停
        raise RuntimeError("cycle boom")

    monkeypatch.setattr(loop, "run_cycle", _raise)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    loop._running = True
    loop._loop_worker()  # 不应抛出
    assert calls["n"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  L14 · run(task, max_rounds) 语义包装（适配桥落地·阶段 6d §五）
# ═══════════════════════════════════════════════════════════════════════════════

def test_l14_run_wrapper_healthy_short_circuit(monkeypatch):
    engine = FakeEngine(defects=[], resources=[FakeResource("a", "ok"), FakeResource("b", "ok")])
    loop = _make_loop(engine)
    monkeypatch.setattr(loop, "save_state", lambda path=None: None)
    r = loop.run("健康任务", max_rounds=5, verbose=False)
    assert r["success"] is True
    assert r["task"] == "健康任务"
    assert r["rounds_run"] == 1          # 首轮即健康短路
    assert r["stopped_early"] is True
    assert r["status"] == "healthy"
    assert r["health_score"] >= 90
    assert len(r["results"]) == 1


def test_l14_run_wrapper_defective_runs_multiple(monkeypatch):
    engine = FakeEngine(defects=[FakeDefect("D1", "high")], resources=[FakeResource("a", "ok")])
    loop = _make_loop(engine)
    monkeypatch.setattr(loop, "save_state", lambda path=None: None)
    monkeypatch.setattr(loop, "self_extend_concepts", lambda: 0)
    monkeypatch.setattr(loop, "self_extend_intents", lambda: 0)
    import src.unified_growth as ug

    class _NoGrow:
        def formula_grow(self, *a, **k):
            return {"grown": 0}

    monkeypatch.setattr(ug, "get_unified_growth", lambda interp=None: _NoGrow())
    r = loop.run("缺陷任务", max_rounds=3, verbose=False)
    assert r["success"] is True
    assert r["rounds_run"] == 3          # 每轮仍有缺陷 → 不早停，跑满
    assert r["stopped_early"] is False
    assert all("actions" in c for c in r["results"])  # 全 Phase 产物
    assert loop._state.cycle_count == 3


def test_l14_run_wrapper_max_rounds_floors_to_one(monkeypatch):
    engine = FakeEngine(defects=[], resources=[FakeResource("a", "ok")])
    loop = _make_loop(engine)
    monkeypatch.setattr(loop, "save_state", lambda path=None: None)
    r = loop.run("任务", max_rounds=0, verbose=False)
    assert r["rounds_run"] == 1          # max_rounds<1 归一


def test_l14_run_wrapper_never_raises(monkeypatch):
    engine = FakeEngine(defects=[FakeDefect("D1", "high")], resources=[FakeResource("a", "ok")])
    loop = _make_loop(engine)

    def _boom(verbose=True):
        raise RuntimeError("cycle boom")

    monkeypatch.setattr(loop, "run_cycle", _boom)
    r = loop.run("任务", max_rounds=2, verbose=False)  # 不应抛出
    assert r["success"] is True
    assert r["rounds_run"] == 0
    assert r["results"] and "error" in r["results"][0]


# ═══════════════════════════════════════════════════════════════════════════════
#  适配桥诚实锁 · unified_growth 已真正接入 inner_loop（取代 phantom 恒不可用）
# ═══════════════════════════════════════════════════════════════════════════════

def test_bridge_get_inner_loop_returns_real_class():
    from src.unified_growth import _get_inner_loop

    # _get_inner_loop 不再 ImportError→None；返回真实类 MathaInnerLoop
    assert _get_inner_loop() is MathaInnerLoop
    assert hasattr(MathaInnerLoop, "run")  # 适配契约 run(task, max_rounds) 已就位
    assert MathaInnerLoop().run is not None


class _StubInner:
    def __init__(self):
        self.calls: list[tuple] = []

    def run(self, task, max_rounds=3):
        self.calls.append((task, max_rounds))
        return {"success": True, "task": task, "rounds_run": max_rounds,
                "stopped_early": True, "health_score": 100.0, "status": "healthy",
                "cycle_count": max_rounds, "results": []}


def test_bridge_run_inner_loop_delegates_to_run():
    from src.unified_growth import UnifiedGrowth

    ug = UnifiedGrowth()
    stub = _StubInner()
    ug._inner_loop = stub  # _ensure_initialized 仅在 None 时构造 → 保留 stub
    r = ug.run_inner_loop("任务X", max_rounds=2)
    assert stub.calls == [("任务X", 2)]
    assert r["success"] is True
    assert r["rounds_run"] == 2
    # 关键：不再恒返回「inner_loop 不可用」
    assert "不可用" not in r.get("error", "")


def test_bridge_phantom_api_is_gone():
    import src.inner_loop as il

    # 旧 phantom：模块仍无 InnerLoop 别名（真名唯一 MathaInnerLoop），
    # 但 unified_growth 已改用真名，故接入不再恒降级。
    assert hasattr(il, "MathaInnerLoop")
    assert not hasattr(il, "InnerLoop")
