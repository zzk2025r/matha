# -*- coding: utf-8 -*-
"""A2 表征锁：inner_loop 自升级检查/应用必须用唯一版本源（非硬编码假版本）。

回归目标（Tier2·A2）：
  旧实现 self_upgrade_check 硬编码 current='1.2.22' / known=['1.2.21',…]，
  self_upgrade_apply 硬编码 from/to='1.3.0'，与真实版本源 src.__version__（4.6.0）
  自相矛盾（幻影·名不副实）。修复后一律取自唯一版本源。

全程离线/毫秒：MathaInnerLoop.__init__ 轻量（不触发 init_modules）；打桩引擎仅覆盖
纯逻辑路径，不触盘、不污染单例。
"""
import logging

import pytest

logging.disable(logging.CRITICAL)

from src.__version__ import get_version
from src.inner_loop import MathaInnerLoop, _version_tuple


@pytest.fixture
def il():
    return MathaInnerLoop()  # 轻量：_engine=None，不触发重型 init_modules


# ── self_upgrade_check：真实版本 + 诚实可得性 ──────────────────────────────────

def test_check_uses_real_version(il):
    r = il.self_upgrade_check()
    assert r["current_version"] == get_version()
    assert r["latest_version"] == get_version()
    # 离线无更新通道：当前源版本即最新可得，如实报告不可升级
    assert r["is_latest"] is True
    assert r["can_upgrade"] is False
    # 旧的硬编码假版本不得复现
    assert r["current_version"] != "1.2.22"
    assert "1.2.22" not in str(r) and "1.2.21" not in str(r)


def test_check_newer_channel_reports_upgrade(il):
    r = il.self_upgrade_check(known_latest="99.0.0")
    assert r["latest_version"] == "99.0.0"
    assert r["can_upgrade"] is True
    assert r["is_latest"] is False


def test_check_equal_channel_is_latest(il):
    r = il.self_upgrade_check(known_latest=get_version())
    assert r["is_latest"] is True and r["can_upgrade"] is False


def test_check_pending_patches_from_real_defects(il):
    class Stub:
        def get_defect_stats(self):
            return {"open_defects": [
                {"id": "D1", "severity": "critical"},
                {"id": "D2", "severity": "low"},
            ]}

    il._engine = Stub()
    r = il.self_upgrade_check()
    assert r["pending_patches"] == [{"id": "D1", "severity": "critical"}]
    assert r["current_version"] == get_version()


# ── self_upgrade_apply：from/to 取自真实版本 ───────────────────────────────────

def test_apply_no_engine_honest_early_return(il):
    a = il.self_upgrade_apply()
    assert a["success"] is False
    assert a["from_version"] is None and a["to_version"] is None
    assert any("引擎未初始化" in e for e in a["errors"])


def test_apply_versions_real_on_reached_path(il):
    class Stub:
        def self_diagnose(self):
            return []

    il._engine = Stub()
    a = il.self_upgrade_apply()
    assert a["from_version"] == get_version()
    assert a["to_version"] == get_version()
    assert a["success"] is True and a["patches_applied"] == 0
    assert "1.3.0" not in str(a)


def test_apply_target_version_reflected(il):
    class Stub:
        def self_diagnose(self):
            return []

    il._engine = Stub()
    b = il.self_upgrade_apply(target_version="5.0.0")
    assert b["from_version"] == get_version() and b["to_version"] == "5.0.0"


# ── 版本比较辅助 ───────────────────────────────────────────────────────────────

def test_version_tuple_helper():
    assert _version_tuple("4.6.0") == (4, 6, 0)
    assert _version_tuple("1.2") == (1, 2, 0)
    assert _version_tuple("v4.6.0") == (4, 6, 0)
