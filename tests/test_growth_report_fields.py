# -*- coding: utf-8 -*-
"""成长系统·GrowthReport 幻影字段清理锁（Tier 1·S5）。

坐实三个恒默认、grow 全程不写的幻影字段已从 GrowthReport **移除**（而非伪填）：
  performance_before_ms / performance_after_ms / languages_analyzed。
并确认真实字段（含 S4 保留的 cross_language_consistent）仍在位、grow 不复活这些属性。

全程离线、毫秒级、无文件副作用。
"""
from __future__ import annotations

import dataclasses

import pytest

from src.matha_growth import GrowthReport, MathaGrowthEngine

PHANTOM = {"performance_before_ms", "performance_after_ms", "languages_analyzed"}
REAL_FIELDS = {
    "iteration", "source", "diagnostics", "optimization_suggestions",
    "improved_source", "optimizations_applied", "cross_language_consistent", "errors",
}


class TestPhantomFieldsRemoved:
    def test_not_in_dataclass_fields(self):
        names = {f.name for f in dataclasses.fields(GrowthReport)}
        assert PHANTOM.isdisjoint(names), f"幻影字段仍残留: {PHANTOM & names}"

    def test_real_fields_retained(self):
        names = {f.name for f in dataclasses.fields(GrowthReport)}
        assert REAL_FIELDS <= names, f"真实字段缺失: {REAL_FIELDS - names}"

    def test_construct_without_phantom_kwargs(self):
        rep = GrowthReport(iteration=1, source="x = 1.0\n")
        for g in PHANTOM:
            assert not hasattr(rep, g), f"{g} 不应再存在"

    def test_construct_with_phantom_kwarg_rejected(self):
        # 传幻影字段应报错 → 杜绝旧调用点静默复活误导字段。
        with pytest.raises(TypeError):
            GrowthReport(iteration=1, source="x", performance_before_ms=0.0)


class TestGrowHasNoPhantomAttrs:
    def test_grow_report_lacks_phantom(self):
        rep = MathaGrowthEngine().grow("x = 3.0 + 4.0\n#1：[x]\n")
        for g in PHANTOM:
            assert not hasattr(rep, g), f"grow 结果不应带幻影字段 {g}"

    def test_no_fabricated_performance_numbers(self):
        # 本轨道「不承诺更快」：结果里不得有伪装的毫秒性能数（字段已彻底移除）。
        rep = MathaGrowthEngine().grow("x = 2.0 * 3.0\n#1：[x]\n")
        d = {f.name for f in dataclasses.fields(GrowthReport)}
        assert not any("performance" in name for name in d)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
