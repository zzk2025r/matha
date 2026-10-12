"""工具模块增强测试：性能回归 / LLM 密钥配置 / 文档 API 变更检测。"""

import json
import os
import time

import pytest

from src.tools.doc_generator import MathaDocGenerator
from src.tools.llm_config import LLMKeyConfig
from src.tools.perf_profiler import MathaProfiler

# ── 性能回归测试 ────────────────────────────────────────────────────────────

class TestPerformanceRegression:
    def test_run_performance_test_passes_within_threshold(self):
        profiler = MathaProfiler()
        ok = profiler.run_performance_test(
            "fast_add", lambda a, b: a + b, 1, 2, threshold_ms=1000.0
        )
        assert ok is True

    def test_run_performance_test_fails_over_threshold(self):
        profiler = MathaProfiler()
        ok = profiler.run_performance_test(
            "slow_sleep", time.sleep, 0.02, threshold_ms=1.0
        )
        assert ok is False

    def test_clear_results(self):
        profiler = MathaProfiler()
        profiler.run_performance_test("t1", lambda: 1, threshold_ms=1000.0)
        profiler.clear_results()
        assert len(profiler._results) == 0
        assert len(profiler._benchmark_data) == 0

    def test_generate_html_report(self, tmp_path):
        profiler = MathaProfiler()
        profiler.run_performance_test("t2", lambda: [None], threshold_ms=1000.0)
        out = str(tmp_path / "report.html")
        content = profiler.generate_html_report(out)
        assert isinstance(content, str)
        assert "性能" in content or "<html" in content.lower()
        assert os.path.exists(out), "报告应写入指定路径"

    def test_generate_json_report_valid(self, tmp_path):
        profiler = MathaProfiler()
        profiler.run_performance_test("t3", lambda: 42, threshold_ms=1000.0)
        out = str(tmp_path / "report.json")
        content = profiler.generate_json_report(out)
        assert isinstance(content, str)
        data = json.loads(content)
        assert isinstance(data, dict)


# ── LLM 密钥配置 ────────────────────────────────────────────────────────────

@pytest.fixture
def llm_cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("MATHA_CONFIG_DIR", str(tmp_path / "keys"))
    cfg = LLMKeyConfig(str(tmp_path / "cfg.json"))
    return cfg


class TestLLMKeyConfig:
    def test_add_key_encrypted_on_disk(self, llm_cfg, tmp_path):
        id1 = llm_cfg.add_key("gpt4", "sk-secret-123", label="prod")
        assert id1
        with open(tmp_path / "cfg.json", "rb") as f:
            raw = f.read()
        assert b"sk-secret-123" not in raw, "明文密钥不得落盘"

    def test_active_and_get_api_key(self, llm_cfg):
        llm_cfg.add_key("gpt4", "key-1")
        llm_cfg.add_key("gpt4", "key-2")
        assert llm_cfg.get_api_key("gpt4") == "key-1"
        assert llm_cfg.active_entry_id("gpt4") == llm_cfg.list_keys("gpt4")[0]["id"]

    def test_rotate(self, llm_cfg):
        llm_cfg.add_key("gpt4", "key-1")
        llm_cfg.add_key("gpt4", "key-2")
        llm_cfg.add_key("gpt4", "key-3")
        new_id = llm_cfg.rotate("gpt4")
        assert new_id == llm_cfg.list_keys("gpt4")[1]["id"]
        assert llm_cfg.get_api_key("gpt4") == "key-2"
        # 轮换一圈回到第一个
        llm_cfg.rotate("gpt4")
        assert llm_cfg.get_api_key("gpt4") == "key-3"
        llm_cfg.rotate("gpt4")
        assert llm_cfg.get_api_key("gpt4") == "key-1"

    def test_set_active_and_update(self, llm_cfg):
        id1 = llm_cfg.add_key("claude", "old-secret")
        llm_cfg.add_key("claude", "new-secret")
        assert llm_cfg.set_active("claude", id1) is True
        assert llm_cfg.get_api_key("claude") == "old-secret"
        assert llm_cfg.update_key("claude", id1, "rotated-secret") is True
        assert llm_cfg.get_api_key("claude") == "rotated-secret"
        assert llm_cfg.set_active("claude", "not-exist") is False

    def test_remove_key(self, llm_cfg):
        id1 = llm_cfg.add_key("gpt5", "k1")
        llm_cfg.add_key("gpt5", "k2")
        assert llm_cfg.remove_key("gpt5", id1) is True
        assert llm_cfg.list_keys("gpt5")[0]["id"] == llm_cfg.active_entry_id("gpt5")
        assert llm_cfg.total_keys == 1
        assert llm_cfg.remove_key("gpt5", "nope") is False

    def test_env_override(self, llm_cfg, monkeypatch):
        llm_cfg.add_key("gpt4", "file-key")
        monkeypatch.setenv("MATHA_LLM_API_KEY", "env-key")
        monkeypatch.setenv("MATHA_LLM_MODEL", "gpt4")
        assert llm_cfg.get_api_key("gpt4") == "env-key"
        assert llm_cfg.get_api_key() == "env-key"

    def test_empty_key_rejected(self, llm_cfg):
        with pytest.raises(ValueError):
            llm_cfg.add_key("gpt4", "   ")

    def test_models_and_config_file(self, llm_cfg):
        llm_cfg.add_key("gpt4", "k")
        llm_cfg.add_key("claude", "c")
        assert set(llm_cfg.models) == {"gpt4", "claude"}
        assert llm_cfg.total_keys == 2
        assert os.path.exists(llm_cfg.config_file)


# ── 文档生成器 API 变更检测 ─────────────────────────────────────────────────

BASE_SRC = {
    "base_mod.py": '''"""base module"""


def alpha(x: int) -> None:
    """计算 alpha"""


def beta(y: int, z: int) -> int:
    """计算 beta"""


class Foo:
    """Foo 类"""

    def m1(self, a: str) -> str:
        """方法一"""
''',
}

NEW_SRC = {
    "base_mod.py": '''"""base module"""


def alpha(x: int, w: int) -> None:
    """计算 alpha"""


def gamma(v: float) -> float:
    """新增函数"""


class Foo:
    """Foo 类"""

    def m1(self, a: str) -> str:
        """方法一"""

    def m2(self) -> None:
        """方法二"""
''',
}


def _write_modules(tmp_path, files):
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    for name, content in files.items():
        (src / name).write_text(content, encoding="utf-8")
    return src


class TestDocGeneratorDiff:
    def test_detects_added_removed_modified(self, tmp_path):
        src = _write_modules(tmp_path, BASE_SRC)
        gen = MathaDocGenerator([str(src)])
        base_docs = gen.generate()

        for name, content in NEW_SRC.items():
            (src / name).write_text(content, encoding="utf-8")

        gen2 = MathaDocGenerator([str(src)])
        new_docs = gen2.generate()
        changes = gen.compare_docs(base_docs, new_docs)

        by_key = {(c["module"], c["kind"], c["name"]): c for c in changes}

        alpha = by_key.get(("base_mod", "function", "alpha"))
        assert alpha is not None and alpha["change"] == "modified"
        assert "参数变化" in alpha["detail"]

        beta = by_key.get(("base_mod", "function", "beta"))
        assert beta is not None and beta["change"] == "removed"

        gamma = by_key.get(("base_mod", "function", "gamma"))
        assert gamma is not None and gamma["change"] == "added"

        m2 = by_key.get(("base_mod", "method", "Foo.m2"))
        assert m2 is not None and m2["change"] == "added"
