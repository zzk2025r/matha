# -*- coding: utf-8 -*-
"""插件化取证：`integrate` 属领域插件「符号微积分」，sympy 只在缺口调用那一刻加载。

四条判据（全部在子进程里做，避免污染同会话其它测试的 sys.modules）：

  1. `matha run tests/test_plugin_load.matha` 得到 `x**3/3`（结果正确）；
  2. 引用 `integrate` 之前插件未被 import，引用之后才物化（按需加载）；
     而内核纯标准库引擎能答的积分，全程 **不碰 sympy**；
  3. 只有当内核引擎覆盖不到（返回 None）时，才在调用点动态 import sympy
     —— 这是「重后端外移为可选插件」的实质证明点；
  4. 插件不导出裸 `x`：未绑定的 `x` 照旧报「未定义变量」（内核契约不被插件改写），
     符号变量须由用户自己 `x = 符号原子("x")` 绑定；数值内建不受影响（符号卫生）。

对应重构验收项「测插件加载」；口径见 docs/ARCHITECTURE.md「插件层（联邦式）」。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATHA_SRC = ROOT / "tests" / "test_plugin_load.matha"

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

def test_cli_run_integrate_result():
    """`matha run` 一句 integrate(x^2, x) 必须得到 ∫x²dx = x³/3。"""
    proc = subprocess.run(
        [sys.executable, "-m", "src.matha_main", "run", str(MATHA_SRC)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"运行失败：\n{proc.stderr}"
    assert proc.stdout.strip() == "x**3/3", f"积分结果不符：{proc.stdout!r}"


# ============================================================
# 2 + 3. 加载时机取证
# ============================================================

_LAZY_SNIPPET = f"""
import json, sys
from pathlib import Path
import src.kernel.exec_api as E
from src.plugin_api import get_resolver

PLUG = 'src.domains.symbolic_calculus'
snap = {{}}
snap['sympy_at_start'] = 'sympy' in sys.modules
snap['plugin_at_start'] = PLUG in sys.modules

# ① 内核引擎能答：x**2
snap['kernel_out'] = [str(o) for o in E.run_file(Path(r'{MATHA_SRC}'))]
snap['plugin_after_call'] = PLUG in sys.modules
snap['sympy_after_kernel'] = 'sympy' in sys.modules
snap['loaded_plugins'] = get_resolver().loaded()

# ② 内核缺口（exp(-x**2) 非初等）：只有这一刻才允许 import sympy
snap['sympy_before_gap'] = 'sympy' in sys.modules
try:
    snap['gap_out'] = [str(o) for o in E.run('print(integrate("exp(-x**2)", "x"))')]
    snap['gap_error'] = None
except Exception as e:
    snap['gap_out'] = []
    snap['gap_error'] = f'{{type(e).__name__}}: {{e}}'
snap['sympy_after_gap'] = 'sympy' in sys.modules
snap['has_sympy'] = {HAS_SYMPY!r}

print(json.dumps(snap))
"""


@pytest.fixture(scope="module")
def lazy_snapshot() -> dict:
    return _probe(_LAZY_SNIPPET)


def test_nothing_heavy_at_startup(lazy_snapshot):
    """进入 Matha 时 sympy 与领域插件都不在 sys.modules（核心安装零第三方依赖）。"""
    assert lazy_snapshot["sympy_at_start"] is False
    assert lazy_snapshot["plugin_at_start"] is False


def test_plugin_materialized_on_first_use(lazy_snapshot):
    """引用 integrate 才物化插件，且只物化这一个插件。"""
    assert lazy_snapshot["plugin_after_call"] is True
    assert lazy_snapshot["loaded_plugins"] == ["symbolic_calculus"]


def test_kernel_engine_answers_without_sympy(lazy_snapshot):
    """x² 由纯标准库内核引擎作答：调用完成后 sympy 仍未被 import。"""
    assert lazy_snapshot["kernel_out"] == ["x**3/3"]
    assert lazy_snapshot["sympy_after_kernel"] is False


def test_sympy_imported_only_at_gap_call(lazy_snapshot):
    """缺口积分才触发动态导入：调用前 sympy 不在、调用后在，且结果正确。"""
    if not lazy_snapshot["has_sympy"]:
        pytest.skip("sympy 未安装（属 optional-dependencies.accelerated），"
                    "缺口路径应给出显式错误而非假成功")
    assert lazy_snapshot["sympy_before_gap"] is False
    assert lazy_snapshot["sympy_after_gap"] is True
    assert len(lazy_snapshot["gap_out"]) == 1
    assert "erf" in lazy_snapshot["gap_out"][0], lazy_snapshot["gap_out"]


def test_gap_without_sympy_reports_explicitly(lazy_snapshot):
    """装了 sympy 时此条只验证不抛错；未装时须是显式错误文本。"""
    if lazy_snapshot["has_sympy"]:
        assert lazy_snapshot["gap_error"] is None
    else:
        assert "sympy" in (lazy_snapshot["gap_error"] or "")


# ============================================================
# 4. 符号卫生：插件不得改写「未定义名即报错」的内核契约
# ============================================================

_HYGIENE_SNIPPET = """
import json, sys
import src.kernel.exec_api as E

out = {}
out['bare_x_undefined'] = None
try:
    out['bare_x_undefined'] = [str(o) for o in E.run('print(x^2)')]
except Exception as e:
    out['bare_x_undefined'] = f'{type(e).__name__}: {e}'
out['user_binding_wins'] = [str(o) for o in E.run('x = 10\\nprint(x^2)')]
out['explicit_symbol_ok'] = [str(o) for o in E.run('u = 符号原子("u")\\nprint(integrate(u^2, u))')]
try:
    out['other_undefined'] = [str(o) for o in E.run('print(zz^2)')]
    out['other_undefined_error'] = None
except Exception as e:
    out['other_undefined'] = []
    out['other_undefined_error'] = f'{type(e).__name__}: {e}'
out['numeric_intact'] = [str(o) for o in E.run('print(sin(pi/2))')]
print(json.dumps(out))
"""


def test_plugin_does_not_shadow_undefined_name_contract():
    """插件不得把未定义名变成隐式符号：裸 `x` 必须报错，符号由用户显式绑定。

    反例教训：早期版本导出裸 `x`，`LazyBuiltinTable` 的成员判定使 `x` 在所有
    程序里都变成「已定义」，直接打挂 test_bootstrap_host 与 test_auto_debug_e2e。
    """
    got = _probe(_HYGIENE_SNIPPET)
    assert "未定义变量 'x'" in (got["bare_x_undefined"] or ""), got
    assert got["user_binding_wins"] == ["100"], got
    assert got["explicit_symbol_ok"] == ["u**3/3"], got
    assert "未定义变量 'zz'" in (got["other_undefined_error"] or ""), got
    assert got["numeric_intact"] == ["1.0"], got
