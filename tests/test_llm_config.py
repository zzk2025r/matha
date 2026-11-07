# -*- coding: utf-8 -*-
"""LLM 密钥配置契约锁（阶段 1 · AI 修复）。

背景：`src/tools/llm_config.py` 历史上顶层 import cryptography 但任何
依赖清单都未声明——缺包时 import 即 ModuleNotFoundError，且核心零依赖
纪律被破坏。本轮：懒导入（用到加密才检查，缺包诚实 ImportError 带安装
指引），pyproject 声明 llm extra。

本文件锁：
  1. 缺 cryptography 子进程内 import/构造/纯查询不崩，加密操作诚实拒绝；
  2. 加密往返真算（本机有 cryptography：写入→密文非明文→读回 plaintext）；
  3. 多密钥切换/轮换/移除/更新行为手算对拍；
  4. 环境变量优先契约；list_keys 永不泄明文。
测试密钥全为假值；主密钥/配置经 MATHA_CONFIG_DIR 隔离到 tmp_path。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tools import llm_config as lc  # noqa: E402
from src.tools.llm_config import LLMKeyConfig  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("MATHA_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MATHA_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MATHA_LLM_MODEL", raising=False)
    monkeypatch.setattr(lc, "_LLM_CONFIG", None)


def _cfg(tmp_path) -> LLMKeyConfig:
    return LLMKeyConfig(config_path=str(tmp_path / "llm_config.json"))


# ============================================================
# 1. 缺 cryptography 诚实面（干净子进程 + import 拦截）
# ============================================================

_NO_CRYPTO_SNIPPET = """
import importlib.abc, sys
sys.path.insert(0, %r)

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "cryptography" or fullname.startswith("cryptography."):
            raise ModuleNotFoundError("blocked: %%s" %% fullname)
        return None

sys.meta_path.insert(0, Blocker())
from src.tools.llm_config import LLMKeyConfig  # 历史：顶层 import 即崩
c = LLMKeyConfig(config_path=%r)
assert c.models == [] and c.total_keys == 0  # 纯查询不触加密
try:
    c.add_key("m", "fake-key")
except ImportError as e:
    assert "cryptography" in str(e)
    print("NO_CRYPTO_OK")
else:
    raise AssertionError("缺包假成功复活：add_key 未拒绝")
"""


def test_import_and_queries_work_without_cryptography(tmp_path):
    snippet = _NO_CRYPTO_SNIPPET % (str(ROOT), str(tmp_path / "cfg.json"))
    proc = subprocess.run([sys.executable, "-c", snippet],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "NO_CRYPTO_OK" in proc.stdout


# ============================================================
# 2. 加密往返真算（cryptography 为本机已装的可选依赖）
# ============================================================

class TestEncryptedRoundTrip:

    def test_add_then_get_returns_plaintext(self, tmp_path):
        c = _cfg(tmp_path)
        eid = c.add_key("gpt-4o", "fake-key-abc")
        assert c.get_api_key("gpt-4o") == "fake-key-abc"
        # 落盘必须是密文，绝不明文
        raw = Path(c.config_file).read_text(encoding="utf-8")
        assert "fake-key-abc" not in raw
        assert json.loads(raw)["models"]["gpt-4o"]["entries"][0]["id"] == eid

    def test_reload_from_disk_decrypts(self, tmp_path):
        c = _cfg(tmp_path)
        c.add_key("m", "fake-key-xyz")
        c2 = _cfg(tmp_path)  # 同目录主密钥 + 同配置路径
        assert c2.get_api_key("m") == "fake-key-xyz"

    def test_list_keys_never_leaks_plaintext(self, tmp_path):
        c = _cfg(tmp_path)
        c.add_key("m", "fake-secret", label="主用")
        entries = c.list_keys("m")
        assert entries[0]["label"] == "主用" and entries[0]["active"] is True
        assert "fake-secret" not in json.dumps(entries)
        assert "cipher" not in entries[0]

    def test_empty_key_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="不能为空"):
            _cfg(tmp_path).add_key("m", "   ")


# ============================================================
# 3. 多密钥管理行为对拍
# ============================================================

class TestKeyManagement:

    def test_active_switch_and_rotate(self, tmp_path):
        c = _cfg(tmp_path)
        e1 = c.add_key("m", "key-1")
        e2 = c.add_key("m", "key-2")
        assert c.active_entry_id("m") == e1  # 首个自动激活
        assert c.get_api_key("m") == "key-1"
        assert c.set_active("m", e2) is True
        assert c.get_api_key("m") == "key-2"
        assert c.rotate("m") == e1  # 环形轮换回 e1
        assert c.get_api_key("m") == "key-1"
        assert c.set_active("m", "nonexistent") is False

    def test_remove_active_falls_back(self, tmp_path):
        c = _cfg(tmp_path)
        e1 = c.add_key("m", "key-1")
        e2 = c.add_key("m", "key-2")
        assert c.remove_key("m", e1) is True
        assert c.active_entry_id("m") == e2
        assert c.remove_key("m", "nonexistent") is False
        assert c.remove_key("absent-model", e2) is False
        assert c.remove_key("m", e2) is True
        assert c.active_entry_id("m") is None
        assert c.get_api_key("m") is None

    def test_update_key_reencrypts(self, tmp_path):
        c = _cfg(tmp_path)
        eid = c.add_key("m", "old-key")
        assert c.update_key("m", eid, "new-key") is True
        assert c.get_api_key("m") == "new-key"
        assert c.update_key("m", "nonexistent", "k") is False
        assert c.update_key("absent", eid, "k") is False

    def test_rotate_empty_returns_none(self, tmp_path):
        assert _cfg(tmp_path).rotate("absent") is None

    def test_models_and_total_counts(self, tmp_path):
        c = _cfg(tmp_path)
        c.add_key("m1", "k1")
        c.add_key("m1", "k2")
        c.add_key("m2", "k3")
        assert set(c.models) == {"m1", "m2"}
        assert c.total_keys == 3


# ============================================================
# 4. 环境变量优先契约
# ============================================================

class TestEnvPriority:

    def test_env_key_wins_for_matching_model(self, tmp_path, monkeypatch):
        c = _cfg(tmp_path)
        c.add_key("m", "stored-key")
        monkeypatch.setenv("MATHA_LLM_API_KEY", "env-key")
        monkeypatch.setenv("MATHA_LLM_MODEL", "m")
        assert c.get_api_key("m") == "env-key"
        assert c.get_api_key() == "env-key"
        # 模型不匹配时不越权返回 env key
        assert c.get_api_key("other") is None

    def test_singleton_accessor(self, tmp_path):
        a = lc.get_llm_config()
        b = lc.get_llm_config()
        assert a is b