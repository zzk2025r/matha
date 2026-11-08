# -*- coding: utf-8 -*-
"""密钥管理统一走 llm_config 契约锁（阶段 4-2 · AI 修复）。

背景：llm_parser 的密钥读取散在 __init__ env 扫描、Gemini、ChatGLM 三处，
全部绕过 llm_config 加密存储；CLI 无任何密钥管理入口。本轮：优先级固定为
显式参数 > 环境变量 > llm_config 加密 store；matha_main 新增 llm-config
子命令（add-key/list/remove/rotate/set-active），任何输出不含明文。

本文件锁（密钥全假，MATHA_CONFIG_DIR 隔离到 tmp_path）：
  1. 解析器密钥解析优先级（显式 > env > config store > None）；
  2. Gemini/ChatGLM 分支同样回退 config store；
  3. config 读取失败不炸构造（走无 key → 降级链）；
  4. CLI 各动作行为与退出码、密文落盘无明文、getpass 隐藏输入；
  5. 干净子进程闭环：CLI 写入 → LLMIntentParser 构造读回。
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intent.llm_parser import LLMIntentParser  # noqa: E402
from src.tools import llm_config as lc  # noqa: E402

matha_main = importlib.import_module("src.matha_main")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("MATHA_CONFIG_DIR", str(tmp_path / "matha-config"))
    monkeypatch.setattr(lc, "_LLM_CONFIG", None)
    monkeypatch.setattr(LLMIntentParser, "_load_dotenv", staticmethod(lambda: None))
    monkeypatch.setenv("MATHA_LLM_RETRY_DELAY", "0")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY",
                "MATHA_LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)


def _parser(tmp_path, **kw):
    return LLMIntentParser(cache_dir=str(tmp_path / "cache"), **kw)


def _store(model, key):
    return lc.get_llm_config().add_key(model, key)


# ============================================================
# 1. 解析器密钥解析优先级
# ============================================================

class TestParserKeyResolution:

    def test_explicit_param_wins_over_env_and_store(self, tmp_path, monkeypatch):
        _store("claude-3-5-sonnet", "fake-key-store")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-env")
        p = _parser(tmp_path, api_key="fake-key-explicit", model="claude-3-5-sonnet")
        assert p._api_key == "fake-key-explicit"

    def test_env_wins_over_store(self, tmp_path, monkeypatch):
        _store("claude-3-5-sonnet", "fake-key-store")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-env")
        p = _parser(tmp_path, model="claude-3-5-sonnet")
        assert p._api_key == "fake-key-env"

    def test_store_fallback_when_env_absent(self, tmp_path):
        _store("claude-3-5-sonnet", "fake-key-store")
        p = _parser(tmp_path, model="claude-3-5-sonnet")
        assert p._api_key == "fake-key-store"

    def test_no_key_anywhere_is_none_without_side_effects(self, tmp_path):
        p = _parser(tmp_path, model="claude-3-5-sonnet")
        assert p._api_key is None
        cfg_dir = tmp_path / "matha-config"
        assert not (cfg_dir / "llm_master.key").exists()

    def test_store_failure_does_not_crash_constructor(self, tmp_path, monkeypatch):
        _store("claude-3-5-sonnet", "fake-key-store")

        def no_crypto():
            raise ImportError("blocked: cryptography")
        monkeypatch.setattr(lc, "_fernet_class", no_crypto)
        p = _parser(tmp_path, model="claude-3-5-sonnet")
        assert p._api_key is None

    def test_gemini_branch_falls_back_to_store(self, tmp_path, monkeypatch):
        _store("gemini-1.5-pro", "fake-key-gemini")
        seen = {}
        fake = types.ModuleType("google.generativeai")
        fake.configure = lambda **kw: seen.update(kw)
        monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
        monkeypatch.setitem(sys.modules, "google.generativeai", fake)
        p = _parser(tmp_path, model="gemini-1.5-pro")
        p._get_gemini_client()
        assert seen["api_key"] == "fake-key-gemini"

    def test_chatglm_branch_falls_back_to_store(self, tmp_path, monkeypatch):
        _store("glm-4-flash", "fake-key-glm")
        seen = {}
        fake = types.ModuleType("openai")
        fake.OpenAI = lambda **kw: seen.update(kw) or object()
        monkeypatch.setitem(sys.modules, "openai", fake)
        p = _parser(tmp_path, model="glm-4-flash")
        p._get_chatglm_client()
        assert seen["api_key"] == "fake-key-glm"


# ============================================================
# 2. CLI llm-config 子命令
# ============================================================

class TestCliLlmConfig:

    def test_add_key_hidden_input_encrypts_at_rest(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("getpass.getpass", lambda prompt: "fake-key-abc")
        rc = matha_main.main(["llm-config", "add-key", "--model", "claude-3-5-sonnet",
                              "--label", "主密钥"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "已添加" in out and "fake-key-abc" not in out
        cfg_file = tmp_path / "matha-config" / "llm_config.json"
        assert cfg_file.exists()
        assert "fake-key-abc" not in cfg_file.read_text(encoding="utf-8")
        assert lc.get_llm_config().get_api_key("claude-3-5-sonnet") == "fake-key-abc"

    def test_add_key_scripting_flag(self, tmp_path, capsys):
        rc = matha_main.main(["llm-config", "add-key", "--model", "gpt-4o",
                              "--key", "fake-key-abc", "--active"])
        assert rc == 0
        assert "fake-key-abc" not in capsys.readouterr().out
        entries = lc.get_llm_config().list_keys("gpt-4o")
        assert len(entries) == 1 and entries[0]["active"] is True

    def test_add_key_empty_honest_error(self, monkeypatch, capsys):
        monkeypatch.setattr("getpass.getpass", lambda prompt: "")
        rc = matha_main.main(["llm-config", "add-key", "--model", "claude-3-5-sonnet"])
        assert rc == 1
        assert "输入错误" in capsys.readouterr().err

    def test_list_empty_store(self, capsys):
        rc = matha_main.main(["llm-config", "list"])
        assert rc == 0
        assert "未存储任何密钥" in capsys.readouterr().out

    def test_list_shows_label_and_active_never_plaintext(self, tmp_path, capsys):
        _store("claude-3-5-sonnet", "fake-key-abc")
        rc = matha_main.main(["llm-config", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "claude-3-5-sonnet" in out and "[生效]" in out
        assert "fake-key-abc" not in out

    def test_remove_and_missing(self, capsys):
        entry_id = _store("claude-3-5-sonnet", "fake-key-abc")
        assert matha_main.main(["llm-config", "remove", "--model", "claude-3-5-sonnet",
                                "--id", entry_id]) == 0
        assert lc.get_llm_config().list_keys("claude-3-5-sonnet") == []
        assert matha_main.main(["llm-config", "remove", "--model", "claude-3-5-sonnet",
                                "--id", "nonexistent"]) == 1

    def test_rotate_cycles_active(self, capsys):
        id1 = _store("claude-3-5-sonnet", "fake-key-1")
        id2 = _store("claude-3-5-sonnet", "fake-key-2")
        assert lc.get_llm_config().active_entry_id("claude-3-5-sonnet") == id1
        assert matha_main.main(["llm-config", "rotate", "--model", "claude-3-5-sonnet"]) == 0
        assert lc.get_llm_config().active_entry_id("claude-3-5-sonnet") == id2
        assert matha_main.main(["llm-config", "rotate", "--model", "empty-model"]) == 1

    def test_set_active_valid_and_invalid(self):
        id1 = _store("claude-3-5-sonnet", "fake-key-1")
        id2 = _store("claude-3-5-sonnet", "fake-key-2")
        assert matha_main.main(["llm-config", "set-active", "--model", "claude-3-5-sonnet",
                                "--id", id1]) == 0
        assert lc.get_llm_config().active_entry_id("claude-3-5-sonnet") == id1
        assert matha_main.main(["llm-config", "set-active", "--model", "claude-3-5-sonnet",
                                "--id", "nonexistent"]) == 1

    def test_missing_cryptography_honest_exit(self, monkeypatch, capsys):
        def no_crypto():
            raise ImportError("请安装 cryptography")
        monkeypatch.setattr(lc, "_fernet_class", no_crypto)
        rc = matha_main.main(["llm-config", "add-key", "--model", "claude-3-5-sonnet",
                              "--key", "fake-key-abc"])
        assert rc == 1
        assert "不可用" in capsys.readouterr().err


# ============================================================
# 3. 干净子进程闭环：CLI 写入 → 解析器构造读回（零 monkeypatch）
# ============================================================

_E2E_SNIPPET = """
import json, os, sys
sys.path.insert(0, %r)
from src.tools import llm_config as lc
from src.intent.llm_parser import LLMIntentParser

# 子进程内 CLI 已由父进程调用写入；此处锁读取闭环
cfg = lc.get_llm_config()
assert cfg.get_api_key("claude-3-5-sonnet") == "fake-key-abc"
p = LLMIntentParser(model="claude-3-5-sonnet", cache_dir=os.path.join(os.getcwd(), "cache"))
assert p._api_key == "fake-key-abc", "解析器未从加密 store 读回密钥"
print("LOOP_OK")
""" % str(ROOT)


def test_cli_write_then_parser_read_end_to_end(tmp_path):
    cfg_dir = tmp_path / "matha-config"
    env = {**os.environ, "MATHA_CONFIG_DIR": str(cfg_dir)}
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY",
                "MATHA_LLM_MODEL"):
        env.pop(key, None)
    add = subprocess.run(
        [sys.executable, "-m", "src.matha_main", "llm-config", "add-key",
         "--model", "claude-3-5-sonnet", "--key", "fake-key-abc", "--label", "e2e"],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert add.returncode == 0, add.stderr[-800:]
    assert "fake-key-abc" not in add.stdout
    assert "fake-key-abc" not in (cfg_dir / "llm_config.json").read_text(encoding="utf-8")
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(tmp_path), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "LOOP_OK" in proc.stdout