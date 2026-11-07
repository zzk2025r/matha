# -*- coding: utf-8 -*-
"""
Jupyter magic 行为锁（阶段 2 · MIR 交接断点修复）。

历史断点：%matha 把 MIRNode 对象传给只接受 str 的 execute_mir（必
AttributeError），回退 interpret 同样吃不下 MIRNode，从未算出过结果。
现契约：
  - intent.suggested_code 经 src.kernel.exec_api.run_checked 主链真算；
  - result 绑定且无输出指令时补 `#1：[result]`；
  - MIR 仅预览展示，execute_mir/compile_mir 不得被调用；
  - 分解器裸 `#` 兜底标记显式拒绝（主链会将其静默 NOOP 为外来声明）；
  - 执行错误下沉展示，保留错误前已产生的输出；
  - IPython 缺席时注册静默跳过，execute() 展示降级为 print。

IPython 本机未安装：注册路径用 fake-IPython 子进程注入锁（零 skip）。
LLM 一律离线（_call_llm 打桩），不触网、只用假 key。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.intent.llm_parser import Intent, IntentType, LLMIntentParser
from src.jupyter.matha_magic import MathaMagics

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def offline(monkeypatch):
    """LLM 离线 + 屏蔽 IPython（使展示确定性地降级为 print，跨环境稳定）。"""
    def _raise(self, text):
        raise RuntimeError("offline-test")
    monkeypatch.setattr(LLMIntentParser, "_call_llm", _raise)
    monkeypatch.setitem(sys.modules, "IPython", None)
    monkeypatch.setitem(sys.modules, "IPython.display", None)


# ============================================================
#  execute() 核心链
# ============================================================

class TestExecuteCore:
    def test_arithmetic_real_compute(self, offline, capsys):
        m = MathaMagics(shell=None)
        assert m.execute("计算 3 加 5") == 8
        out = capsys.readouterr().out
        assert "result = 3 + 5" in out
        assert "#1：[result]" in out
        assert "**输出**: [8]" in out

    def test_sqrt_real_compute(self, offline, capsys):
        assert MathaMagics(None).execute("求 16 的平方根") == 4.0
        assert "**输出**: [4.0]" in capsys.readouterr().out

    def test_unmapped_marker_rejected(self, offline, capsys):
        """范围语义分解器无法映射 → 显式拒绝，不静默假成功。"""
        assert MathaMagics(None).execute("计算 100 以内所有素数") is None
        out = capsys.readouterr().out
        assert "未执行" in out
        assert "裸 `#` 行" in out
        assert "**输出**" not in out

    def test_low_confidence_surfaced(self, offline, capsys):
        assert MathaMagics(None).execute("今天天气很好") is None
        out = capsys.readouterr().out
        assert "置信度太低" in out
        assert "未执行" in out

    def test_mir_is_display_only(self, offline, capsys, monkeypatch):
        """execute_mir/compile_mir 不得再被 magic 调用（历史断点防回归）。"""
        import src.compiler.ir as ir

        def boom(*a, **k):
            raise AssertionError("MIR 执行链不应被调用")
        monkeypatch.setattr(ir, "execute_mir", boom)
        monkeypatch.setattr(ir, "compile_mir", boom)
        assert MathaMagics(None).execute("计算 3 加 5") == 8
        out = capsys.readouterr().out
        assert "MIR 预览（仅展示，不参与执行）" in out
        assert "#：返回 result = 3 + 5" in out  # RETURN 序列化不再丢 value


# ============================================================
#  错误下沉
# ============================================================

def _intent_with_code(code: str) -> Intent:
    return Intent(
        intent_type=IntentType.ARITHMETIC,
        description="测试意图",
        confidence=0.9,
        suggested_code=code,
    )


class TestErrorSinking:
    def test_runtime_error_displayed_not_raised(self, offline, monkeypatch, capsys):
        intent = _intent_with_code("result = 1 / 0")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: intent)
        assert MathaMagics(None).execute("除零测试") is None
        out = capsys.readouterr().out
        assert "执行错误" in out
        assert "除零" in out

    def test_partial_outputs_preserved(self, offline, monkeypatch, capsys):
        intent = _intent_with_code("#1：[1]\nresult = 1 / 0")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: intent)
        assert MathaMagics(None).execute("部分输出测试") is None
        out = capsys.readouterr().out
        assert "**输出**: [1]" in out
        assert "执行错误" in out

    def test_empty_suggested_code(self, offline, monkeypatch, capsys):
        intent = _intent_with_code("")
        monkeypatch.setattr(LLMIntentParser, "_call_llm", lambda self, text: intent)
        assert MathaMagics(None).execute("空代码测试") is None
        assert "意图未产出代码" in capsys.readouterr().out


# ============================================================
#  _prepare_source 单元矩阵
# ============================================================

class TestPrepareSource:
    def setup_method(self):
        self.m = MathaMagics(shell=None)

    @pytest.mark.parametrize("suggested,expected,reason_frag", [
        ("", "", "意图未产出代码"),
        ("   ", "", "意图未产出代码"),
        ("result = 3 + 5", "result = 3 + 5\n#1：[result]", ""),
        ("result = 3 + 5\n#1：[result]", "result = 3 + 5\n#1：[result]", ""),
        ("result = 3 + 5\n#：[result]", "result = 3 + 5\n#：[result]", ""),
        ("#1：[7]", "#1：[7]", ""),
        ("x = 3", "x = 3", ""),
        ("# 无法映射: xyz", "", "裸 `#` 行"),
        ("result = 1\n# 无法解析: xyz", "", "裸 `#` 行"),
    ])
    def test_matrix(self, suggested, expected, reason_frag):
        source, reason = self.m._prepare_source(suggested)
        assert source == expected
        if reason_frag:
            assert reason_frag in reason
        else:
            assert reason == ""


# ============================================================
#  fake-IPython 子进程：注册 + line/cell 魔法 + Markdown 展示
# ============================================================

_FAKE_IPYTHON_SCRIPT = r'''
import sys, types

ipy = types.ModuleType("IPython"); ipy.__path__ = []
core = types.ModuleType("IPython.core"); core.__path__ = []
magic = types.ModuleType("IPython.core.magic")
magic._classes = []; magic._line = {}; magic._cell = {}

class Magics:
    def __init__(self, shell=None):
        self.shell = shell

def magics_class(cls):
    magic._classes.append(cls); return cls

def register_line_magic(f):
    magic._line[f.__name__] = f; return f

def register_cell_magic(f):
    magic._cell[f.__name__] = f; return f

magic.Magics = Magics
magic.magics_class = magics_class
magic.register_line_magic = register_line_magic
magic.register_cell_magic = register_cell_magic

disp = types.ModuleType("IPython.display")
disp._shown = []
disp.Markdown = lambda text: ("markdown", text)
disp.display = lambda obj: disp._shown.append(obj)

ipy.core = core; core.magic = magic; ipy.display = disp
sys.modules["IPython"] = ipy
sys.modules["IPython.core"] = core
sys.modules["IPython.core.magic"] = magic
sys.modules["IPython.display"] = disp

from src.intent.llm_parser import LLMIntentParser
def _offline(self, text):
    raise RuntimeError("offline-test")
LLMIntentParser._call_llm = _offline

import src.jupyter.matha_magic as mm

class FakeShell:
    def __init__(self):
        self.registered = []
    def register_magics(self, cls):
        self.registered.append(cls)

shell = FakeShell()
mm.load_ipython_extension(shell)
assert shell.registered, "register_magics 未被调用"
assert magic._classes, "magics_class 未注册"
inst = magic._classes[0](shell)
line_fn = magic._line["matha"]
cell_fn = magic._cell["matha"]

assert line_fn(inst, "计算 3 加 5") == 8
assert cell_fn(inst, "", "求 16 的平方根") == 4.0
assert len(disp._shown) == 2
kind, text = disp._shown[0]
assert kind == "markdown"
assert "Matha 计算结果" in text and "**输出**: [8]" in text
assert "MIR 预览（仅展示，不参与执行）" in text

assert line_fn(inst, "计算 100 以内所有素数") is None
_, text3 = disp._shown[2]
assert "未执行" in text3

assert "src.compiler.ir" not in sys.modules, "MIR 执行链不应被导入"
mm.unload_ipython_extension(shell)
print("MAGIC-SUBPROCESS-OK")
'''


class TestFakeIPythonRegistration:
    def test_registration_and_magics(self):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [sys.executable, "-c", _FAKE_IPYTHON_SCRIPT],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180, env=env,
        )
        assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        assert "MAGIC-SUBPROCESS-OK" in proc.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])