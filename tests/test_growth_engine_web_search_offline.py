# -*- coding: utf-8 -*-
"""A4 表征锁：growth_engine.web_search 必须默认离线·诚实拒绝（不主动联网）。

回归目标（Tier2·A4）：
  旧实现无条件尝试 MCP WebSearch + urllib(duckduckgo) 真实网络请求，违反核心纯净
  /离线口径。修复后默认 allow_network=False：不发起任何网络请求、如实返回 None
  （绝不伪造搜索结果）；仅当显式经 env MATHA_ALLOW_NETWORK_SEARCH 开启时才联网。

全程离线：打桩 run_mcp / urlopen 为哨兵，断言默认路径下从未被调用。
"""
import logging
import sys
import types
import urllib.request

import pytest

logging.disable(logging.CRITICAL)

from src.growth_engine import GrowthEngine

TRUTHY = ("1", "true", "yes", "on", "TRUE", "On")
FALSY = ("", "0", "false", "no", "off", "maybe")


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    """默认清除开关 env，保证用例互不干扰。"""
    monkeypatch.delenv("MATHA_ALLOW_NETWORK_SEARCH", raising=False)


@pytest.fixture
def sentinels(monkeypatch):
    """把网络出口都封成哨兵：一旦被调用即记帐并抛错，坐实'绝不联网'。"""
    calls = {"urlopen": 0, "mcp": 0}

    def _boom(*a, **k):
        calls["urlopen"] += 1
        raise AssertionError("默认离线路径不得发起 HTTP 请求")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    def _install_mcp(returns=None):
        mod = types.ModuleType("run_mcp")

        def _run(*a, **k):
            calls["mcp"] += 1
            return returns
        mod.run_mcp = _run
        monkeypatch.setitem(sys.modules, "run_mcp", mod)
    return calls, _install_mcp


# ── 默认离线：诚实返回 None，绝不触网 ──────────────────────────────────────────

def test_default_is_offline(sentinels):
    calls, install_mcp = sentinels
    install_mcp(returns="SHOULD-NOT-BE-USED")
    eng = GrowthEngine()
    assert eng.allow_network is False
    assert eng.web_search("some fix patch") is None
    # 关键：MCP 与 HTTP 均未被调用
    assert calls == {"urlopen": 0, "mcp": 0}, calls


def test_search_and_patch_degrades_honestly(sentinels):
    calls, install_mcp = sentinels
    install_mcp(returns="X")
    eng = GrowthEngine()

    class _D:
        defect_id = "D1"
        message = "某模块自检失败需要补丁"

    # 离线时 web_search 返回 None → search_and_patch 应诚实返回 None（不伪造补丁）
    assert eng.search_and_patch(_D()) is None
    assert calls == {"urlopen": 0, "mcp": 0}, calls


# ── 显式开启：才尝试网络（MCP 命中即返回、并写缓存）───────────────────────────

def test_optin_env_enables_flag(monkeypatch):
    for v in TRUTHY:
        monkeypatch.setenv("MATHA_ALLOW_NETWORK_SEARCH", v)
        assert GrowthEngine().allow_network is True, v
    for v in FALSY:
        monkeypatch.setenv("MATHA_ALLOW_NETWORK_SEARCH", v)
        assert GrowthEngine().allow_network is False, v


def test_optin_uses_mcp_and_caches(sentinels, monkeypatch):
    calls, install_mcp = sentinels
    install_mcp(returns="patch-from-mcp")
    monkeypatch.setenv("MATHA_ALLOW_NETWORK_SEARCH", "1")
    eng = GrowthEngine()
    assert eng.allow_network is True
    r = eng.web_search("q-hit")
    assert r == "patch-from-mcp"
    assert calls["mcp"] == 1
    assert eng._web_search_cache.get("q-hit") == "patch-from-mcp"
    # 命中缓存不再重复请求
    assert eng.web_search("q-hit") == "patch-from-mcp"
    assert calls["mcp"] == 1


def test_optin_no_result_returns_none(sentinels, monkeypatch):
    calls, install_mcp = sentinels
    install_mcp(returns=None)  # MCP 无果；随后 urllib 已被哨兵封死会抛错→被 except 吞→None
    monkeypatch.setenv("MATHA_ALLOW_NETWORK_SEARCH", "1")
    eng = GrowthEngine()
    assert eng.web_search("q-miss") is None
