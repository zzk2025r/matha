"""可视化编程器增强功能测试：断点/缓存/错误恢复/撤销重做/新节点类型/性能分析。"""

import os
import sqlite3
import tempfile

import pytest

from src.visual_editor.node_executor import ExecutionStatus, NodeExecutor
from src.visual_editor.node_types import (
    NodeDefinition,
    NodeRegistry,
    NodeType,
    register_all_nodes,
)


@pytest.fixture
def executor():
    ex = NodeExecutor()
    ex.add_node("n1", {"type": "math_add", "id": "n1"})
    ex.add_node("n2", {"type": "math_multiply", "id": "n2"})
    ex.add_node("n3", {"type": "output", "id": "n3"})
    ex.add_connection("n1", "result", "n2", "a")
    ex.add_connection("n2", "result", "n3", "value")
    return ex


@pytest.fixture
def counter_executor(tmp_path):
    """带计数执行函数的执行器，用于验证缓存/断点行为。"""
    ex = NodeExecutor()
    calls = {"n1": 0}

    def counting(node_data, inputs, context):
        calls["n1"] += 1
        return {"result": inputs.get("a", 5) + 1}

    ex.add_node("n1", {"type": "math_add", "id": "n1"})
    ex.add_node("n2", {"type": "output", "id": "n2"})
    ex.add_connection("n1", "result", "n2", "value")
    ex._counting = calls
    ex._funcs = {"math_add": counting}
    return ex


# ── 断点 ────────────────────────────────────────────────────────────────────

class TestBreakpoints:
    def test_set_and_remove_breakpoint(self, executor):
        executor.set_breakpoint("n2")
        assert "n2" in executor.breakpoints
        assert executor.breakpoints["n2"]["enabled"] is True
        assert executor.remove_breakpoint("n2") is True
        assert executor.remove_breakpoint("n2") is False

    def test_set_breakpoint_unknown_node(self, executor):
        with pytest.raises(ValueError):
            executor.set_breakpoint("ghost")

    def test_pause_on_breakpoint(self, executor):
        executor.set_breakpoint("n3")
        result = executor.execute()
        assert result["status"] == "paused"
        assert result["paused_at"] == "n3"
        # n3 之前都不应执行
        statuses = {r["node_id"]: r["status"] for r in result["results"]}
        assert statuses["n3"] == ExecutionStatus.PAUSED.value

    def test_resume_after_pause(self, executor):
        executor.set_breakpoint("n3")
        executor.execute()
        result = executor.resume()
        assert result["status"] == "success"
        assert result["failed_nodes"] == 0

    def test_resume_with_no_failed(self, executor):
        executor.execute()
        resume = executor.resume()
        assert resume["status"] == "idle"

    def test_breakpoint_condition_on_input(self, executor):
        ex = NodeExecutor()
        ex.add_node("n1", {"type": "math_add", "id": "n1"})
        ex.add_node("n2", {"type": "output", "id": "n2"})
        ex.add_connection("n1", "result", "n2", "value")
        ex.add_connection("n1", "result", "n1", "a")  # 环路免责：条件用输入端口
        # 配置条件为输入端口名 b（默认 0 → 不暂停）
        # 重新搭一个不含回环的图
        ex2 = NodeExecutor()
        ex2.add_node("n1", {"type": "math_add", "id": "n1", "config": {"flag": 1}})
        ex2.add_node("n2", {"type": "output", "id": "n2"})
        ex2.add_connection("n1", "result", "n2", "value")
        ex2.set_breakpoint("n1", condition="b")
        result = ex2.execute(context={"inputs": {"b": False}})
        assert result["status"] == "success"
        result2 = ex2.execute(context={"inputs": {"b": True}})
        assert result2["status"] == "paused"


# ── 结果缓存 ────────────────────────────────────────────────────────────────

class TestCache:
    def test_cache_reuses_result(self, counter_executor):
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        assert counter_executor._counting["n1"] == 1
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        assert counter_executor._counting["n1"] == 1, "第二次执行应命中缓存"
        stats = counter_executor.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["size"] >= 2

    def test_cache_off_by_default(self, counter_executor):
        counter_executor.execute(counter_executor._funcs)
        assert counter_executor._counting["n1"] == 1
        counter_executor.execute(counter_executor._funcs)
        assert counter_executor._counting["n1"] == 2

    def test_clear_cache(self, counter_executor):
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        counter_executor.clear_cache()
        assert counter_executor.get_cache_stats()["size"] == 0
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        assert counter_executor._counting["n1"] == 2

    def test_cache_invalidation_on_mutation(self, counter_executor):
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        assert counter_executor._counting["n1"] == 1
        # 覆盖同名节点 → 该节点缓存失效 → 再次执行会重算
        counter_executor.add_node("n1", {"type": "math_add", "id": "n1"})
        counter_executor.execute(counter_executor._funcs, use_cache=True)
        assert counter_executor._counting["n1"] == 2


# ── 错误恢复 ────────────────────────────────────────────────────────────────

class TestErrorRecovery:
    def test_partial_success_and_resume(self):
        ex = NodeExecutor()
        ex.add_node("bad", {"type": "math_divide", "id": "bad"})  # a/0 → inf（不报错）
        ex.add_node("boom", {"type": "sequence", "id": "boom"})
        # 强制一个失败
        def _fail(node_data, inputs, context):
            raise RuntimeError("boom")

        ex.add_node("f1", {"type": "custom_fail", "id": "f1"})
        ex.add_node("out", {"type": "output", "id": "out"})
        ex.add_connection("f1", "result", "out", "value")
        result = ex.execute({"custom_fail": _fail})
        assert result["status"] == "partial_success"
        assert result["failed_nodes"] == 1

        # 修复后恢复
        def _ok(node_data, inputs, context):
            return {"result": 42}

        ex2 = NodeExecutor()
        ex2.add_node("f1", {"type": "custom", "id": "f1"})
        ex2.add_node("out", {"type": "output", "id": "out"})
        ex2.add_connection("f1", "result", "out", "value")
        ex2.execute({"custom": _fail})
        resume = ex2.resume({"custom": _ok})
        assert resume["status"] == "success"

    def test_resume_reuses_upstream_outputs(self):
        """下游失败节点恢复时,上游成功节点的输出应被复用。"""
        ex = NodeExecutor()
        ex.add_node("src", {"type": "input", "id": "src", "default_value": 7})
        ex.add_node("mid", {"type": "math_add", "id": "mid"})
        ex.add_node("leaf", {"type": "math_multiply", "id": "leaf"})
        ex.add_connection("src", "value", "mid", "a")
        ex.add_connection("mid", "result", "leaf", "b")

        def _fail(node_data, inputs, context):
            raise RuntimeError("boom")

        ex.add_connection("mid", "result", "leaf", "a")

        def _ok(node_data, inputs, context):
            if inputs.get("b") is None:
                raise RuntimeError("上游输入未复用")
            return {"result": inputs.get("a", 0) * inputs.get("b", 1)}

        # 让 leaf 失败
        ex.execute({"math_multiply": _fail})
        resume = ex.resume({"math_multiply": _ok})
        assert resume["status"] == "success"


# ── 撤销 / 重做 ─────────────────────────────────────────────────────────────

class TestUndoRedo:
    def test_snapshot_restore(self, executor):
        snap = executor.snapshot()
        executor.add_node("extra", {"type": "output"})
        assert "extra" in executor.nodes
        executor.restore(snap)
        assert "extra" not in executor.nodes
        assert len(executor.connections) == 2

    def test_undo_redo_flow(self, executor):
        executor.push_undo()
        executor.add_node("n4", {"type": "math_pi"})
        assert executor.undo() is True
        assert "n4" not in executor.nodes
        assert executor.redo() is True
        assert "n4" in executor.nodes

    def test_undo_empty(self, executor):
        assert executor.undo() is False
        assert executor.redo() is False
        assert executor.can_undo is False

    def test_push_undo_clears_redo(self, executor):
        executor.push_undo()
        executor.add_node("n4", {"type": "math_pi"})
        executor.undo()
        assert executor.can_redo
        executor.add_node("n5", {"type": "math_e"})
        assert executor.can_redo is False


# ── 性能分析 ────────────────────────────────────────────────────────────────

class TestPerfReport:
    def test_performance_report(self, executor):
        executor.execute()
        executor.execute()
        report = executor.get_performance_report()
        assert len(report) == 3
        n1 = next(r for r in report if r["node_id"] == "n1")
        assert n1["call_count"] == 2
        assert n1["total_ms"] >= 0
        assert n1["max_ms"] >= n1["avg_ms"]

    def test_clear_history(self, executor):
        executor.execute()
        executor.clear_history()
        assert executor.execution_history == []
        assert executor.get_performance_report() == []


# ── 新节点类型 ──────────────────────────────────────────────────────────────

class TestNewNodeTypes:
    def test_new_types_registered(self):
        register_all_nodes()
        assert NodeRegistry.get(NodeType.FILE_READ.value) is not None
        assert NodeRegistry.get(NodeType.NET_HTTP_GET.value) is not None
        assert NodeRegistry.get(NodeType.DB_QUERY.value) is not None
        assert NodeRegistry.get(NodeType.IMAGE_GRAYSCALE.value) is not None
        assert NodeRegistry.get(NodeType.AUDIO_SINE.value) is not None

    def test_new_categories_exist(self):
        for category in ("文件", "网络", "数据库", "图像", "音频"):
            assert len(NodeRegistry.get_by_category(category)) > 0, category

    def test_file_read_write_roundtrip(self, tmp_path):
        ex = NodeExecutor()
        f = tmp_path / "data.txt"
        ex.add_node("w", {"type": "file_write", "config": {"path": str(f)}})
        ex.add_node("r", {"type": "file_read", "config": {"path": str(f)}})
        ex.add_connection("w", "written", "r", "content")
        w_node = {"type": "file_write", "config": {"path": str(f)}}
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("")
        res = ex.execute()
        assert res["status"] == "success"
        # 直接调用执行函数
        out = ex._execute_file_node("file_write", w_node, {"content": "hello"})
        assert out == {"written": True}
        read = ex._execute_file_node("file_read", {"type": "file_read", "config": {"path": str(f)}}, {})
        assert read == {"content": "hello"}
        files = ex._execute_file_node("file_list", {"type": "file_list", "config": {"path": str(tmp_path)}}, {})
        assert "data.txt" in files["files"]

    def test_db_query_execute(self):
        from src.visual_editor.node_types import _db_query
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.db")
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE t (v INTEGER)")
            db.execute("INSERT INTO t VALUES (1),(2),(3)")
            db.commit()
            db.close()

            q = _db_query(path, "SELECT v FROM t")
            assert q["columns"] == ["v"]
            assert len(q["rows"]) == 3

            ex = NodeExecutor()
            q2 = ex._execute_db_node("db_query", {"config": {"path": path}}, {"sql": "SELECT v FROM t"})
            assert len(q2["rows"]) == 3

            w = ex._execute_db_node("db_execute", {"config": {"path": path}}, {"sql": "DELETE FROM t WHERE v=1"})
            assert w["rowcount"] == 1

    def test_image_ops(self):
        ex = NodeExecutor()
        img = {"width": 2, "height": 2, "pixels": [255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255]}
        gray = ex._execute_image_node("image_grayscale", {"image": img})
        assert gray["image"]["pixels"][0] == gray["image"]["pixels"][1] == gray["image"]["pixels"][2]
        invert = ex._execute_image_node("image_invert", {"image": img})
        assert invert["image"]["pixels"][0] == 0  # 255 → 0
        resized = ex._execute_image_node("image_resize", {"image": img, "width": 1, "height": 1})
        assert resized["image"]["width"] == 1 and resized["image"]["height"] == 1
        bright = ex._execute_image_node("image_brightness", {"image": img, "factor": 10})
        assert bright["image"]["pixels"][0] == 255

    def test_audio_ops(self):
        ex = NodeExecutor()
        sine = ex._execute_audio_node("audio_sine", {"freq": 440, "seconds": 1, "sample_rate": 16000})
        assert sine["audio"]["sample_rate"] == 16000
        assert len(sine["audio"]["samples"]) == 16000
        vol = ex._execute_audio_node("audio_volume", {"audio": sine["audio"], "level": 0.5})
        assert vol["audio"]["samples"][0] == sine["audio"]["samples"][0] * 0.5
        norm = ex._execute_audio_node("audio_normalize", {"audio": sine["audio"]})
        assert max(abs(s) for s in norm["audio"]["samples"]) <= 1.0
        fade = ex._execute_audio_node("audio_fade", {"audio": sine["audio"]})
        assert fade["audio"]["samples"][0] == 0.0 or abs(fade["audio"]["samples"][0]) < abs(sine["audio"]["samples"][0])

    def test_network_node_definition(self):
        d = NodeRegistry.get(NodeType.NET_HTTP_GET.value)
        assert isinstance(d, NodeDefinition)
        assert d.category == "网络"
