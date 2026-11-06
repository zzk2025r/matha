# -*- coding: utf-8 -*-
"""成长引擎·死代码消除 opt-in 扩展（S3）生产级回归锁。

背景（见 KNOWN_ISSUES.md §7c / Tier 1 计划 S3）：旧核心 `_apply_dead_code_elimination`
把赋值自身 LHS 也算进 `used` → 恒 no-op、从不删；且删未用绑定同样破 P1 名守恒（被删名字
正是它自身）。S3 处置：从 `_apply_optimizations` 核心序列**移除**、删除旧方法，真删除能力
重写为正确的「未用顶层绑定删除」并迁为 opt-in 扩展（`src/growth_extensions.py::optimize_dead_code`），
经 `UnifiedGrowth.register_extension / list_extensions / get_extension_callable` 可搜索/调用；
扩展**不走 P1**，改由 outputs 对拍自证等价，不等价（右端有副作用等）即原样返回。

本锁：① 从核心管线移除；② 正确识别 + 删除未用绑定；③ 不误删被引用者；④ 迭代收敛多删除；
⑤ 词边界安全；⑥ 副作用/运行错→对拍拒绝→原样返回；⑦ opt-in 注册可查可调用。
全程离线、毫秒级、无文件副作用、不污染单例（每例新建 UnifiedGrowth）。
"""
from __future__ import annotations

from src.growth_extensions import (
    remove_unused_top_bindings,
    optimize_dead_code,
    register_into,
    GROWTH_EXTENSIONS,
)
from src.matha_growth import MathaGrowthEngine
from src.unified_growth import UnifiedGrowth


class TestRemovedFromCorePipeline:
    def test_dead_code_method_gone(self):
        assert not hasattr(MathaGrowthEngine, "_apply_dead_code_elimination")

    def test_grow_never_lists_dead_code(self):
        engine = MathaGrowthEngine()
        rep = engine.grow("used = 3.0\ncpus = 999.0\n#1：[used]\n")
        assert not any("死代码消除" in s for s in rep.optimizations_applied)

    def test_apply_optimizations_has_no_dead_code(self):
        engine = MathaGrowthEngine()
        _improved, applied = engine._apply_optimizations("used = 3.0\ncpus = 999.0\n")
        assert not any("死代码消除" in s for s in applied)


class TestIdentifyAndDelete:
    """② 正确识别 + 删除未用绑定（旧恒 no-op 的反面）。"""

    def test_single_unused_dropped_and_equivalent(self):
        src = "used = 3.0\ncpus = 999.0\n#1：[used]\n"
        r = optimize_dead_code(src)
        assert r["applied"] == 1 and r["equivalent"] is True
        assert "cpus" not in r["improved_source"]
        assert "used = 3.0" in r["improved_source"]
        assert MathaGrowthEngine()._semantic_equivalent(src, r["improved_source"]) is True

    def test_multiple_unused_iterative(self):
        src = "dead1 = 5.0\ndead2 = 6.0\nlive = 7.0\n#1：[live]\n"
        _raw, n = remove_unused_top_bindings(src)
        assert n == 2
        r = optimize_dead_code(src)
        assert r["applied"] == 2 and r["equivalent"] is True
        assert "dead1" not in r["improved_source"] and "dead2" not in r["improved_source"]


class TestKeepReferenced:
    """③ 不误删被引用者。"""

    def test_all_referenced_noop(self):
        src = "a = 1.0\nb = 2.0\nc = a + b\n#1：[c]\n"
        r = optimize_dead_code(src)
        assert r["applied"] == 0 and r["improved_source"] == src

    def test_word_boundary_preserves_longer_name(self):
        # 删 dead（未用）不得误伤被引用的 deadend
        src = "dead = 1.0\ndeadend = 2.0\nout = deadend\n#1：[out]\n"
        r = optimize_dead_code(src)
        assert "deadend = 2.0" in r["improved_source"]
        assert r["equivalent"] is True


class TestSafetyRevert:
    """⑥ 删除改变可观测 outputs（原文运行错/右端有副作用）→ 对拍拒绝 → 原样返回。"""

    def test_run_error_source_returns_original(self):
        src = "unused = someUndefinedFn()\nused = 1.0\n#1：[used]\n"
        r = optimize_dead_code(src)
        assert r["applied"] == 0
        assert r["equivalent"] is False
        assert r["improved_source"] == src


class TestOptInRegistration:
    """⑦ 经既有 UnifiedGrowth 面：可注册 / 可搜索 / 可取回调用。"""

    def test_surface_declared(self):
        assert "dead_binding_elimination" in GROWTH_EXTENSIONS

    def test_register_queryable_callable(self):
        ug = UnifiedGrowth()
        assert ug.list_extensions() == []
        assert register_into(ug) is True
        assert any(e["name"] == "dead_binding_elimination" for e in ug.list_extensions())
        fn = ug.get_extension_callable("dead_binding_elimination")
        assert fn is optimize_dead_code
        out = fn("used = 3.0\ncpus = 999.0\n#1：[used]\n")
        assert out["applied"] == 1 and out["equivalent"] is True
