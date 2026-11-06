# -*- coding: utf-8 -*-
"""成长引擎·内存优化 opt-in 扩展（S2）生产级回归锁。

背景（见 KNOWN_ISSUES.md §7c / Tier 1 计划 S2）：旧 `_apply_memory_optimization` 删
`x = temp_*` 行会丢绑定名 → 恒被 P1 名守恒闸门拒 → 永不生效（且并非真「栈提升」）。
删绑定与 P1 契约结构性冲突，无法并入核心管线。S2 处置：从 `_apply_optimizations` 核心序列
**移除**，重写为正确的「临时变量内联」并迁为 **opt-in 扩展**（`src/growth_extensions.py`），
经 `UnifiedGrowth.register_extension / list_extensions / get_extension_callable` 可搜索/调用；
扩展**不走 P1**，改由 outputs 对拍自证等价，不等价即原样返回。

本锁：① 从核心管线移除（grow 不再产「内存优化」项）；② 扩展注册可查 + 调用产出；
③ 语义对拍（等价才改写）；④ 保守护栏（重绑定 / 复杂右端 / 前向引用不误改）；
⑤ 子串词边界安全。全程离线、毫秒级、无文件副作用、不污染单例（每例新建 UnifiedGrowth）。
"""
from __future__ import annotations

import pytest

from src.growth_extensions import (
    inline_single_use_temps,
    optimize_temp_inlining,
    register_into,
    GROWTH_EXTENSIONS,
)
from src.matha_growth import MathaGrowthEngine
from src.unified_growth import UnifiedGrowth


class TestRemovedFromCorePipeline:
    """① 内存优化不再出现在核心 grow 管线。"""

    def test_memory_optimization_method_gone(self):
        assert not hasattr(MathaGrowthEngine, "_apply_memory_optimization")

    def test_grow_never_lists_memory(self):
        engine = MathaGrowthEngine()
        # 旧会触发「内存优化」的输入：删 temp 行 → 现核心不动它
        rep = engine.grow("x = temp_a\ny = x + 1\n")
        assert not any("内存优化" in s for s in rep.optimizations_applied)

    def test_apply_optimizations_has_no_memory(self):
        engine = MathaGrowthEngine()
        _improved, applied = engine._apply_optimizations("x = temp_a\ny = x + 1\n")
        assert not any("内存优化" in s for s in applied)


class TestOptInRegistration:
    """② 经既有 UnifiedGrowth 面：可注册 / 可搜索 / 可取回调用（opt-in，不自动接线）。"""

    def test_list_empty_before_register(self):
        assert UnifiedGrowth().list_extensions() == []

    def test_register_then_queryable_and_callable(self):
        ug = UnifiedGrowth()
        assert register_into(ug) is True
        listed = ug.list_extensions()
        assert any(
            e["name"] == "temp_var_inline" and e["kind"] == "generator" for e in listed
        ), listed
        fn = ug.get_extension_callable("temp_var_inline")
        assert callable(fn)
        assert fn is optimize_temp_inlining

    def test_extension_surface_declared(self):
        assert "temp_var_inline" in GROWTH_EXTENSIONS


class TestSemanticInline:
    """③ 语义对拍：可证等价才改写；产出内联文。"""

    def test_clean_single_temp_inlined_and_equivalent(self):
        src = "t = 3.0\ny = t * 2.0\n#1：[y]\n"
        r = optimize_temp_inlining(src)
        assert r["applied"] == 1 and r["equivalent"] is True
        assert "y = 3.0 * 2.0" in r["improved_source"]
        assert "t = 3.0" not in r["improved_source"]
        # 改写前后逐字节 outputs 相等
        eng = MathaGrowthEngine()
        assert eng._semantic_equivalent(src, r["improved_source"]) is True

    def test_no_inlinable_temp_is_noop(self):
        # 右端全为表达式（非简单 token）→ 无可内联临时变量 → 原样不动
        src = "x = 1.0 + 2.0\ny = x * 3.0\n#1：[y]\n"
        r = optimize_temp_inlining(src)
        assert r["applied"] == 0 and r["improved_source"] == src


class TestConservativeGuards:
    """④ 保守护栏：重绑定 / 复杂右端 / 前向引用 → 不改写（宁可不改）。"""

    def test_rebound_temp_not_inlined(self):
        src = "t = 3.0\nt = t + 1.0\n#1：[t]\n"
        _improved, n = inline_single_use_temps(src)
        assert n == 0

    def test_complex_rhs_not_inlined(self):
        src = "t = 3.0 * 2.0\ny = t + 1.0\n#1：[y]\n"
        _improved, n = inline_single_use_temps(src)
        assert n == 0

    def test_forward_ref_candidate_rejected_by_outputs(self):
        # 原文本身引用未定义（a=b 时 b 未定义）→ 对拍判非等价 → 原样返回、绝不产坏码
        src = "a = b\nb = 5.0\n#1：[a]\n"
        r = optimize_temp_inlining(src)
        assert r["applied"] == 0
        assert r["equivalent"] is False
        assert r["improved_source"] == src


class TestSubstringWordBoundary:
    """⑤ 词边界安全：内联 tt 不得误伤同前缀的非内联绑定 tth。"""

    def test_prefix_temp_inline_preserves_longer_name(self):
        src = "tt = 4.0\ntth = 2.0 * 2.0\nv = tt + tth\n#1：[v]\n"
        r = optimize_temp_inlining(src)
        assert r["applied"] == 1 and r["equivalent"] is True
        assert "tth = 2.0 * 2.0" in r["improved_source"]
        assert "v = 4.0 + tth" in r["improved_source"]
