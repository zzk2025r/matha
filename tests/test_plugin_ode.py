# -*- coding: utf-8 -*-
"""插件化取证：`解微分方程` / `ode` 属领域插件「常微分方程求解」，
sympy 只在内核 ODE 引擎覆盖不到的那次调用（非线性一阶）才加载。

三条判据（全部在子进程里做，避免污染同会话其它测试的 sys.modules）：

  1. `matha run tests/test_plugin_ode.matha` 得到内核解 + sympy 回退解（结果正确）；
  2. 引用 `解微分方程` 之前插件未被 import，引用之后才物化（按需加载）；
     而内核纯标准库引擎能答的方程（线性/可分离 y'=x*y），全程 **不碰 sympy**；
  3. 只有当内核引擎抛 `OdeUnsupported`（非线性缺口，y'=(x+y)/x）时，才在调用点
     动态 import sympy —— 这是「重后端外移为可选插件」的实质证明点。

对齐 docs/symbolic_parity.md 第 6 节「非线性一阶 → OdeUnsupported，sympy 可解」。
口径与 tests/test_plugin_load.py（integrate 样板件）一致。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATHA_SRC = ROOT / "tests" / "test_plugin_ode.matha"

HAS_SYMPY = importlib.util.find_spec("sympy") is not None


def _probe(code: str) -> dict:
    """在干净子进程里执行探针代码，取回最后一行 JSON。"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"探针子进程失败：\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ============================================================
# 1. 用户可见入口：matha run 的结果
# ============================================================

def test_cli_run_ode_result():
    """`matha run` 两条 ODE：内核解 y'=x·y → C1*exp(x²/2)；sympy 回退 y'=(x+y)/x。"""
    proc = subprocess.run(
        [sys.executable, "-m", "src.matha_main", "run", str(MATHA_SRC)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"运行失败：\n{proc.stderr}"
    lines = proc.stdout.strip().splitlines()
    assert lines[0] == "C1*exp(x**2/2)", f"内核 ODE 解不符：{lines!r}"
    if HAS_SYMPY:
        assert "log" in lines[1] and "C1" in lines[1], f"sympy 回退解不符：{lines!r}"


# ============================================================
# 2 + 3. 加载时机取证
# ============================================================

_LAZY_SNIPPET = f"""
import json, sys
import src.kernel.exec_api as E
from src.plugin_api import get_resolver

PLUG = 'src.domains.symbolic_ode'
snap = {{}}
snap['sympy_at_start'] = 'sympy' in sys.modules
snap['plugin_at_start'] = PLUG in sys.modules

# ① 内核引擎能答：y' = x*y（可分离）
snap['kernel_out'] = [str(o) for o in E.run('print(解微分方程("y\\'(x) = x*y(x)", "x"))')]
snap['plugin_after_kernel'] = PLUG in sys.modules
snap['sympy_after_kernel'] = 'sympy' in sys.modules
snap['loaded_plugins'] = get_resolver().loaded()

# ② 内核缺口（非线性 y' = (x+y)/x）：只有这一刻才允许 import sympy
snap['sympy_before_gap'] = 'sympy' in sys.modules
try:
    snap['gap_out'] = [str(o) for o in E.run('print(ode("y\\'(x) = (x+y(x))/x", "x"))')]
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
    """进入 Matha 时 sympy 与 ODE 插件都不在 sys.modules（核心安装零第三方依赖）。"""
    snap = _snapshot()
    assert snap["sympy_at_start"] is False
    assert snap["plugin_at_start"] is False


def test_plugin_materialized_on_first_use():
    """引用 解微分方程 才物化插件，且只物化这一个插件。"""
    snap = _snapshot()
    assert snap["plugin_after_kernel"] is True
    assert snap["loaded_plugins"] == ["symbolic_ode"]


def test_kernel_engine_answers_without_sympy():
    """线性/可分离 ODE 由纯标准库内核引擎作答：调用完成后 sympy 仍未被 import。"""
    snap = _snapshot()
    assert snap["kernel_out"] == ["C1*exp(x**2/2)"]
    assert snap["sympy_after_kernel"] is False


def test_sympy_imported_only_at_gap_call():
    """缺口 ODE（非线性）才触发动态导入：调用前 sympy 不在、调用后在，且结果正确。"""
    snap = _snapshot()
    if not snap["has_sympy"]:
        # 未装 sympy 时缺口路径应给出显式错误，而非假成功
        assert "sympy" in (snap["gap_error"] or ""), snap
        return
    assert snap["sympy_before_gap"] is False
    assert snap["sympy_after_gap"] is True
    assert len(snap["gap_out"]) == 1
    assert "log" in snap["gap_out"][0], snap["gap_out"]
