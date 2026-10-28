# -*- coding: utf-8 -*-
"""插件化取证：`级数求和` / `sum_series` 属领域插件「级数求和」，
sympy 只在内核级数引擎覆盖不到的那次调用（负整数幂/调和级数）才加载。

对齐 docs/symbolic_parity.md 第 5 节「负整数幂求和 Σ1/n → SeriesUndetermined，
sympy 给出 digamma」。口径与 tests/test_plugin_load.py / test_plugin_ode.py 一致。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATHA_SRC = ROOT / "tests" / "test_plugin_series.matha"

HAS_SYMPY = importlib.util.find_spec("sympy") is not None


def _probe(code: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"探针子进程失败：\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_cli_run_series_result():
    """`matha run`：内核 Σn=5050；sympy 回退 Σ1/n(1..5)=137/60。"""
    proc = subprocess.run(
        [sys.executable, "-m", "src.matha_main", "run", str(MATHA_SRC)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"运行失败：\n{proc.stderr}"
    lines = proc.stdout.strip().splitlines()
    assert lines[0] == "5050", f"内核 Faulhaber 结果不符：{lines!r}"
    if HAS_SYMPY:
        assert lines[1] == "137/60", f"sympy 回退结果不符：{lines!r}"


_LAZY_SNIPPET = f"""
import json, sys
import src.kernel.exec_api as E
from src.plugin_api import get_resolver

PLUG = 'src.domains.symbolic_series'
snap = {{}}
snap['sympy_at_start'] = 'sympy' in sys.modules
snap['plugin_at_start'] = PLUG in sys.modules

# ① 内核引擎能答：Σn, n=1..100（Faulhaber）
snap['kernel_out'] = [str(o) for o in E.run('print(级数求和("n", "n", 1, 100))')]
snap['plugin_after_kernel'] = PLUG in sys.modules
snap['sympy_after_kernel'] = 'sympy' in sys.modules
snap['loaded_plugins'] = get_resolver().loaded()

# ② 内核缺口（Σ1/n，负整数幂）：只有这一刻才允许 import sympy
snap['sympy_before_gap'] = 'sympy' in sys.modules
try:
    snap['gap_out'] = [str(o) for o in E.run('print(sum_series("1/n", "n", 1, 5))')]
    snap['gap_error'] = None
except Exception as e:
    snap['gap_out'] = []
    snap['gap_error'] = f'{{type(e).__name__}}: {{e}}'
snap['sympy_after_gap'] = 'sympy' in sys.modules
snap['has_sympy'] = {HAS_SYMPY!r}

print(json.dumps(snap))
"""


def _snapshot() -> dict:
    return _probe(_LAZY_SNIPPET)


def test_nothing_heavy_at_startup():
    snap = _snapshot()
    assert snap["sympy_at_start"] is False
    assert snap["plugin_at_start"] is False


def test_plugin_materialized_on_first_use():
    snap = _snapshot()
    assert snap["plugin_after_kernel"] is True
    assert snap["loaded_plugins"] == ["symbolic_series"]


def test_kernel_engine_answers_without_sympy():
    """Faulhaber 求和由纯标准库内核引擎作答：调用完成后 sympy 仍未被 import。"""
    snap = _snapshot()
    assert snap["kernel_out"] == ["5050"]
    assert snap["sympy_after_kernel"] is False


def test_sympy_imported_only_at_gap_call():
    """缺口求和（Σ1/n）才触发动态导入：调用前 sympy 不在、调用后在，且结果正确。"""
    snap = _snapshot()
    if not snap["has_sympy"]:
        assert "sympy" in (snap["gap_error"] or ""), snap
        return
    assert snap["sympy_before_gap"] is False
    assert snap["sympy_after_gap"] is True
    assert snap["gap_out"] == ["137/60"], snap["gap_out"]
