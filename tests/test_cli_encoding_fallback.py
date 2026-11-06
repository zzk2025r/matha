# -*- coding: utf-8 -*-
"""CLI 输出编码兜底测试（`_harden_std_streams`）。

背景：Windows 上 stdout 一旦不是控制台（管道/重定向/CI 捕获），Python 退回 locale
首选编码；英文镜像下即 cp1252，两个 CLI 的中文输出会直接抛 `UnicodeEncodeError`
（GitHub Actions dispatch run 42208252282 的 `Test executables` 步骤实测）。
兜底只把不可编码字符降级为占位符，不改动编码本身。
"""
import io
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.compiler.matha_cc_cli import _harden_std_streams as _harden_cc
from src.matha_main import _harden_std_streams as _harden_main

_CN = "Matha LLVM 工具链 (matha-cc)"


def _make_stream():
    """构造一个 cp1252 + strict 的文本流，模拟英文 Windows 控制台/管道。"""
    buf = io.BytesIO()
    return io.TextIOWrapper(buf, encoding="cp1252", errors="strict", newline="\n"), buf


def test_helper_is_callable_on_both_entry_points():
    """两个 CLI 的兜底函数都能安全调用（不抛异常）。"""
    _harden_cc()
    _harden_main()


def test_reconfigure_downgrades_unencodable_chars():
    """兜底后不可编码字符写成占位符而不是抛异常，ASCII 内容不受影响。"""
    stream, buf = _make_stream()
    with pytest.raises(UnicodeEncodeError):
        stream.write(_CN)
    stream.close()

    stream, buf = _make_stream()
    stream.reconfigure(errors="replace")
    stream.write(_CN)
    stream.flush()
    out = buf.getvalue().decode("cp1252")
    assert out.startswith("Matha LLVM ")
    assert "?" in out                       # 中文降级为占位符
    stream.close()


def test_matha_cc_info_survives_cp1252_stdout():
    """端到端：强制 PYTHONIOENCODING=cp1252 跑 `matha-cc info`，必须 exit 0 且不崩。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    for key in [k for k in env if k.startswith("PYTHON")]:
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "cp1252:strict"
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "src.compiler.matha_cc_cli", "info"],
        cwd=root, env=env, capture_output=True, text=True, encoding="cp1252",
        errors="replace", timeout=120,
    )
    assert "UnicodeEncodeError" not in (proc.stderr or "")
    assert proc.returncode == 0
