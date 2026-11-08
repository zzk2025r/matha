# -*- coding: utf-8 -*-
"""LLM 链接入 REPL/CLI 契约锁（阶段 4-1 · AI 修复，离线 mock，不触网）。

背景：两个活 REPL（src/repl.py 经 matha_main repl 入口、src/repl_v23.py 经根
main.py 入口）的 nl 模式历史上只有正则轨；LLMIntentParser 只产 MIR 预览
（不可执行）。本轮：LLMIntentParser 增 target_lang="matha" 可执行轨（提示词
约束内核 builtin + result 绑定/#1 输出指令约定），降级走正则 Matha 轨；
REPL nl 模式经 MATHA_REPL_LLM=1 / --llm 显式启用，默认正则轨不变。

本文件锁（全部假客户端/假 SDK，零网络、密钥全假）：
  1. Matha 轨请求形状（Claude/OpenAI 兼容/Gemini 三分支提示词与 matha_code 字段）；
  2. 降级契约（LLM 失败/坏 JSON → 正则 Matha 轨可执行代码 + 兜底留痕）；
  3. 双 REPL 接线（默认关不触 LLM、启用后真执行、低置信度不执行、执行失败诚实下沉）；
  4. CLI 开关（matha_main --llm / 根 main.py --llm 置 env）；
  5. 干净子进程端到端（假 SDK Blocker + LLM 启用 → 降级真算）。
口径：LLM 真实 API 的回答正确性不背书（KNOWN_ISSUES §7c），本锁只固定接线与降级契约。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.intent.llm_parser as llm_parser  # noqa: E402
from src.intent.llm_parser import (  # noqa: E402
    Intent,
    IntentType,
    LLMIntentParser,
    llm_nl_enabled,
)
from src.kernel import exec_api  # noqa: E402
from src.repl import MathaREPL as ReplClassic  # noqa: E402
from src.repl_v23 import MathaREPL as ReplV23  # noqa: E402

MATHA_JSON = json.dumps({
    "intent_type": "ARITHMETIC",
    "description": "计算 6 乘 7",
    "params": {"a": 6, "b": 7},
    "confidence": 0.9,
    "matha_code": "result = 6 * 7\n#1：[result]",
})

MIR_JSON = json.dumps({
    "intent_type": "ARITHMETIC",
    "description": "计算 1+2",
    "params": {"a": 1, "b": 2},
    "confidence": 0.9,
    "mir_code": "1 + 2",
})


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """屏蔽 .env/真实密钥、重试零等待、单例复位、缓存目录隔离到 tmp。"""
    monkeypatch.setattr(LLMIntentParser, "_load_dotenv", staticmethod(lambda: None))
    monkeypatch.setenv("MATHA_LLM_RETRY_DELAY", "0")
    monkeypatch.setenv("MATHA_LLM_MAX_RETRIES", "3")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY",
                "MATHA_LLM_MODEL", "MATHA_REPL_LLM"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(llm_parser, "_MATHA_PARSER", None)
    from src.tools import llm_config as lc
    monkeypatch.setenv("MATHA_CONFIG_DIR", str(tmp_path / "matha-config"))
    monkeypatch.setattr(lc, "_LLM_CONFIG", None)
    monkeypatch.chdir(tmp_path)


def _matha_parser(tmp_path, model="claude-3-5-sonnet"):
    return LLMIntentParser(api_key="test-key", model=model,
                           cache_dir=str(tmp_path / "cache"), target_lang="matha")


def _fake_anthropic(record, payload=MATHA_JSON):
    def create(**kwargs):
        record.append(kwargs)
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=payload)])
    return types.SimpleNamespace(
        messages=types.SimpleNamespace(create=create))


def _fake_openai(record, payload=MATHA_JSON):
    def create(**kwargs):
        record.append(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=payload))])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)))


def _nl_output(repl_cls, line):
    """构造 REPL 走一次 nl 处理，返回 (stdout, success_count, error_count)。"""
    repl = repl_cls()
    repl.state.mode = "nl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        repl._process_natural_language(line)
    return buf.getvalue(), repl.state.success_count, repl.state.error_count


# ============================================================
# 1. Matha 轨请求形状与字段选择
# ============================================================

class TestMathaTrackContract:

    def test_target_lang_validation(self, tmp_path):
        for bad in ("python", "MIR", "", None):
            with pytest.raises(ValueError, match="target_lang"):
                LLMIntentParser(api_key="test-key", target_lang=bad,
                                cache_dir=str(tmp_path / "c"))
        assert LLMIntentParser(api_key="test-key",
                               cache_dir=str(tmp_path / "c")).target_lang == "mir"

    def test_claude_branch_matha_prompt_and_field(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path)
        record = []
        monkeypatch.setattr(p, "_get_client", lambda: _fake_anthropic(record))
        intent = p.parse("计算 6 乘 7")
        assert len(record) == 1
        assert "Matha" in record[0]["system"]
        assert "#1：[result]" in record[0]["system"]
        assert "matha_code" in record[0]["messages"][0]["content"]
        assert "response_format" not in record[0]
        assert intent.target_lang == "matha"
        assert intent.suggested_code == "result = 6 * 7\n#1：[result]"
        assert exec_api.run(intent.suggested_code) == [42]

    def test_openai_compat_branch_matha_prompt(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path, model="deepseek-chat")
        record = []
        monkeypatch.setattr(p, "_get_client", lambda: _fake_openai(record))
        intent = p.parse("计算 6 乘 7")
        assert len(record) == 1
        assert record[0]["messages"][0]["content"] == LLMIntentParser.SYSTEM_PROMPT_MATHA
        assert "matha_code" in record[0]["messages"][1]["content"]
        assert intent.target_lang == "matha"
        assert intent.suggested_code == "result = 6 * 7\n#1：[result]"

    def test_gemini_branch_matha_prompt(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path, model="gemini-1.5-flash")
        record = []

        def generate_content(text, generation_config=None):
            record.append(text)
            return types.SimpleNamespace(text=MATHA_JSON)

        fake_genai = types.SimpleNamespace(
            GenerativeModel=lambda model: types.SimpleNamespace(
                generate_content=generate_content))
        monkeypatch.setattr(
            p, "_get_client",
            lambda: setattr(p, "_gemini_client", fake_genai))
        intent = p.parse("计算 6 乘 7")
        assert len(record) == 1
        assert LLMIntentParser.SYSTEM_PROMPT_MATHA in record[0]
        assert "matha_code" in record[0]
        assert intent.target_lang == "matha"
        assert intent.suggested_code == "result = 6 * 7\n#1：[result]"

    def test_mir_default_field_unchanged(self, tmp_path, monkeypatch):
        p = LLMIntentParser(api_key="test-key", model="claude-3-5-sonnet",
                            cache_dir=str(tmp_path / "c"))
        record = []
        monkeypatch.setattr(p, "_get_client",
                            lambda: _fake_anthropic(record, payload=MIR_JSON))
        intent = p.parse("计算 1 加 2")
        assert intent.target_lang == "mir"
        assert intent.suggested_code == "1 + 2"
        assert record[0]["system"] == LLMIntentParser.SYSTEM_PROMPT

    def test_cache_key_separates_tracks(self, tmp_path):
        p_mir = LLMIntentParser(api_key="test-key",
                                cache_dir=str(tmp_path / "c1"))
        p_matha = _matha_parser(tmp_path)
        assert p_mir._cache_key("计算 6 乘 7") != p_matha._cache_key("计算 6 乘 7")

    def test_bad_json_falls_back_to_executable_matha(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path)
        monkeypatch.setattr(p, "_get_client",
                            lambda: _fake_anthropic([], payload="不是 JSON"))
        intent = p.parse("计算 3 加 5")
        assert intent.target_lang == "matha"
        assert intent.suggested_code == "result = 3 + 5\n#1：[result]"
        assert exec_api.run(intent.suggested_code) == [8]
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions


# ============================================================
# 2. Matha 轨降级契约（兜底代码必须可执行，不产 MIR 预览）
# ============================================================

class TestMathaDegradation:

    def test_llm_failure_falls_back_to_regex_matha_track(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path)

        def boom(text):
            raise RuntimeError("网络断开")
        monkeypatch.setattr(p, "_call_llm", boom)
        intent = p.parse("计算 3 加 5")
        assert intent.target_lang == "matha"
        assert intent.suggested_code == "result = 3 + 5\n#1：[result]"
        assert exec_api.run(intent.suggested_code) == [8]
        assert intent.intent_type == IntentType.ARITHMETIC
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions
        assert any("正则兜底" in str(e) for e in intent.errors)

    def test_fallback_rejection_is_honest(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path)
        monkeypatch.setattr(p, "_call_llm", lambda text: (_ for _ in ()).throw(RuntimeError("down")))
        intent = p.parse("xyz abc notreal")
        assert intent.suggested_code == ""
        assert intent.confidence <= 0.5
        assert "LLM 解析失败，使用正则兜底" in intent.follow_up_questions

    def test_fallback_matha_function_real_compute(self, tmp_path, monkeypatch):
        p = _matha_parser(tmp_path)
        monkeypatch.setattr(p, "_call_llm", lambda text: (_ for _ in ()).throw(RuntimeError("down")))
        intent = p.parse("求 16 的平方根")
        assert intent.suggested_code
        assert exec_api.run(intent.suggested_code) == [4.0]


# ============================================================
# 3. 双 REPL 接线（默认关 / 启用真执行 / 门控与失败下沉）
# ============================================================

class TestReplLink:

    @pytest.mark.parametrize("repl_cls", [ReplClassic, ReplV23],
                             ids=["repl", "repl_v23"])
    def test_default_off_never_touches_llm(self, repl_cls, monkeypatch):
        def forbidden(text):
            raise AssertionError("默认关竟触 LLM 链")
        monkeypatch.setattr(llm_parser, "parse_nl_matha", forbidden)
        out, success, errors = _nl_output(repl_cls, "计算 3 加 5")
        assert any("结果" in l and "8" in l for l in out.splitlines())
        assert success == 1 and errors == 0

    @pytest.mark.parametrize("repl_cls", [ReplClassic, ReplV23],
                             ids=["repl", "repl_v23"])
    def test_enabled_executes_llm_matha_code(self, repl_cls, monkeypatch):
        monkeypatch.setenv("MATHA_REPL_LLM", "1")
        fake = Intent(
            intent_type=IntentType.ARITHMETIC, description="计算 6 乘 7",
            target_lang="matha", confidence=0.9,
            suggested_code="result = 6 * 7\n#1：[result]")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: fake)
        out, success, errors = _nl_output(repl_cls, "计算 6 乘 7")
        assert any("结果" in l and "42" in l for l in out.splitlines())
        assert success == 1 and errors == 0

    @pytest.mark.parametrize("repl_cls", [ReplClassic, ReplV23],
                             ids=["repl", "repl_v23"])
    def test_enabled_llm_down_degrades_visibly(self, repl_cls, monkeypatch):
        monkeypatch.setenv("MATHA_REPL_LLM", "1")

        def boom(self, text):
            raise RuntimeError("网络断开")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", boom)
        out, success, errors = _nl_output(repl_cls, "计算 3 加 5")
        assert any("结果" in l and "8" in l for l in out.splitlines())
        assert "正则兜底" in out
        assert success == 1 and errors == 0

    @pytest.mark.parametrize("repl_cls", [ReplClassic, ReplV23],
                             ids=["repl", "repl_v23"])
    def test_low_confidence_code_not_executed(self, repl_cls, monkeypatch):
        monkeypatch.setenv("MATHA_REPL_LLM", "1")
        fake = Intent(
            intent_type=IntentType.ARITHMETIC, description="低置信度",
            target_lang="matha", confidence=0.2,
            suggested_code="result = 1/0\n#1：[result]")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: fake)
        out, success, errors = _nl_output(repl_cls, "计算 1 除以 0")
        assert not any("结果" in l for l in out.splitlines())
        assert success == 0 and errors == 0

    @pytest.mark.parametrize("repl_cls", [ReplClassic, ReplV23],
                             ids=["repl", "repl_v23"])
    def test_execution_failure_sinks_honestly(self, repl_cls, monkeypatch):
        monkeypatch.setenv("MATHA_REPL_LLM", "1")
        fake = Intent(
            intent_type=IntentType.ARITHMETIC, description="除零",
            target_lang="matha", confidence=0.9,
            suggested_code="result = 1/0\n#1：[result]")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: fake)
        out, success, errors = _nl_output(repl_cls, "计算 1 除以 0")
        assert success == 0 and errors == 1
        assert "执行" in out and ("失败" in out or "错误" in out)

    @pytest.mark.parametrize("value,expected", [
        ("1", True), ("on", True), ("true", True), ("yes", True), ("YES", True),
        ("", False), ("0", False), ("off", False), ("no", False),
    ])
    def test_llm_nl_enabled_truth_table(self, monkeypatch, value, expected):
        monkeypatch.setenv("MATHA_REPL_LLM", value)
        assert llm_nl_enabled() is expected

    def test_llm_nl_enabled_unset_default_off(self):
        assert llm_nl_enabled() is False


# ============================================================
# 4. CLI 开关接线
# ============================================================

class TestCliWiring:

    def test_matha_main_llm_flag_sets_env(self, monkeypatch):
        import importlib
        matha_main = importlib.import_module("src.matha_main")
        import src.repl as repl_mod
        seen = {}

        class FakeRepl:
            def __init__(self, debug=False, backend="vm"):
                seen["env"] = os.environ.get("MATHA_REPL_LLM")

            def run(self):
                seen["ran"] = True

        monkeypatch.setattr(repl_mod, "MathaREPL", FakeRepl)
        assert matha_main.main(["--llm"]) == 0
        assert seen == {"env": "1", "ran": True}

    def test_matha_main_default_no_env(self, monkeypatch):
        import importlib
        matha_main = importlib.import_module("src.matha_main")
        import src.repl as repl_mod
        seen = {}

        class FakeRepl:
            def __init__(self, debug=False, backend="vm"):
                seen["env"] = os.environ.get("MATHA_REPL_LLM")

            def run(self):
                pass

        monkeypatch.setattr(repl_mod, "MathaREPL", FakeRepl)
        assert matha_main.main([]) == 0
        assert seen["env"] is None

    def test_root_main_llm_flag_sets_env(self, monkeypatch):
        import main as root_main
        seen = {}

        def fake_run_repl(debug=False):
            seen["env"] = os.environ.get("MATHA_REPL_LLM")

        monkeypatch.setattr(root_main, "run_repl", fake_run_repl)
        monkeypatch.setattr(sys, "argv", ["main.py", "--llm"])
        root_main.main()
        assert seen["env"] == "1"

    def test_root_main_default_no_env(self, monkeypatch):
        import main as root_main
        seen = {}

        def fake_run_repl(debug=False):
            seen["env"] = os.environ.get("MATHA_REPL_LLM")

        monkeypatch.setattr(root_main, "run_repl", fake_run_repl)
        monkeypatch.setattr(sys, "argv", ["main.py"])
        root_main.main()
        assert seen["env"] is None


# ============================================================
# 5. 干净子进程端到端：LLM 启用 + SDK 缺席 → 降级真算（零 monkeypatch）
# ============================================================

_E2E_SNIPPET = """
import contextlib, importlib.abc, io, json, os, sys, tempfile
sys.path.insert(0, %r)
os.chdir(tempfile.mkdtemp())  # 缓存目录隔离，.env 查找远离仓库

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in ("anthropic", "openai", "google"):
            raise ModuleNotFoundError("blocked: %%s" %% fullname)
        return None

sys.meta_path.insert(0, Blocker())
os.environ["MATHA_REPL_LLM"] = "1"
os.environ["MATHA_LLM_RETRY_DELAY"] = "0"
os.environ["MATHA_CONFIG_DIR"] = os.path.join(os.getcwd(), "matha-config")
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
            "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY",
            "MATHA_LLM_MODEL"):
    os.environ.pop(key, None)

from src.repl import MathaREPL as R1
from src.repl_v23 import MathaREPL as R2
report = {}
for name, cls in (("repl", R1), ("repl_v23", R2)):
    r = cls()
    r.state.mode = "nl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r._process_natural_language("计算 3 加 5")
    out = buf.getvalue()
    report[name] = {
        "result_8": any("结果" in l and "8" in l for l in out.splitlines()),
        "marker": "正则兜底" in out,
        "success": r.state.success_count,
        "errors": r.state.error_count,
    }
print(json.dumps(report))
""" % str(ROOT)


def test_llm_enabled_sdk_absent_degrades_end_to_end():
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    for name, payload in report.items():
        assert payload["result_8"], f"{name} 降级后未真算：{payload}"
        assert payload["marker"], f"{name} 降级未留痕：{payload}"
        assert payload["success"] == 1 and payload["errors"] == 0, payload