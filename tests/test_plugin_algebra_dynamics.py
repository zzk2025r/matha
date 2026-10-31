# -*- coding: utf-8 -*-
"""插件化隔离风险门禁：代数数精确打印（opt-in）与动态语义空壳预埋。

覆盖三件事（对应「内核只依赖接口 / 核心保持纯净 / 外部插件实现 / 动态加载」）：

1. **无损**：代数数插件默认不加载时，门面 ``to_str`` 发射逐字节不变；加载后仅
   把可证精确命中的 double 系数还原为根式；能力之外诚实回退。
2. **诚实预埋**：动态语义骨架加载后不认领任何指令（``supports`` 恒 False），
   被显式要求执行未接线语义时抛 ``DynamicSemanticsNotWired``，绝不伪造成功。
3. **隔离红线**：纯内核 / 执行器不得 import 插件契约层；契约层不得顶层依赖
   sympy / numpy / scipy（保持核心极简、零第三方成本）。
"""
from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from src.algebra import interface as alg  # noqa: E402
from src.algebra.algebra_plugin import PLUGIN as ALG_PLUGIN  # noqa: E402
from src.dynamics import interface as dyn  # noqa: E402
from src.dynamics.interface import DynamicSemanticsNotWired  # noqa: E402


def _sq(n: int):
    return alg.UnaryOp("sqrt", alg.Const(n))


# ============================================================
# 1. 代数数打印：无损 + 精确 + 诚实边界
# ============================================================


def test_algebra_default_inactive_facade_is_lossless():
    """未加载插件时门面输出必须等于内核 to_str 原样（含 double 系数）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()  # 确保关
    assert cs.exact_algebra_enabled() is False
    out = cs.symbolic_integral("1/(x**2+2)", "x")
    # 默认路径应保留 double 打印，绝不出现根式
    assert "sqrt" not in out
    assert "0.70" in out or "1.41" in out


def test_algebra_optin_renders_exact_and_restores():
    """同一条积分：关→开→关，关闭后必须与初始默认输出逐字节相同（无损）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()
    default_out = cs.symbolic_integral("1/(x**2+2)", "x")
    assert "sqrt" not in default_out
    try:
        cs.enable_exact_algebra()
        assert cs.exact_algebra_enabled() is True
        exact = cs.symbolic_integral("1/(x**2+2)", "x")
        assert "sqrt(2)" in exact          # 0.7071… → 1/2*sqrt(2)，1.4142… → sqrt(2)
        assert "0.70" not in exact
    finally:
        cs.use_kernel_printing()
    assert cs.symbolic_integral("1/(x**2+2)", "x") == default_out


@pytest.mark.parametrize("value,expect", [
    (math.sqrt(2), "sqrt(2)"),
    (Fraction(5, 7), "5/7"),
    (7, "7"),
    (-math.sqrt(3), "-sqrt(3)"),
    (0.5 + 3 * math.sqrt(2), "1/2 + 3*sqrt(2)"),
    (2 ** 0.5 * 2, "2*sqrt(2)"),          # sqrt(8) 化简
])
def test_algebra_recognizer_exact_forms(value, expect):
    got = ALG_PLUGIN.render(alg.Const(Fraction(value)) if not isinstance(value, Fraction) else alg.Const(value))
    assert got == expect


def test_algebra_honesty_defers_unknown():
    """高次 / 多根式 / 超越数不得被伪装成精确有理 —— render 必须回 None。"""
    # sqrt(2)+sqrt(3)：4 次代数数，超出本插件（度数<=2）能力
    s23 = alg.BinOp("+", _sq(2), _sq(3))
    assert ALG_PLUGIN.render(s23) is None
    # 圆周率型：直接以 double 近似入表，亦不得被判为精确
    assert ALG_PLUGIN.render(alg.Const(Fraction(math.pi))) is None


# ============================================================
# 2. 动态语义：诚实空壳预埋
# ============================================================


def test_dynamics_default_inactive():
    dyn.set_active(None)
    assert dyn.active_backend() is None


def test_dynamics_skeleton_claims_nothing_and_falls_back():
    calls: list[str] = []
    try:
        backend = dyn.load_plugin("dynamic")
        instr = dyn.DecodedInstr("add", rd=1, rs1=2, rs2=3)
        assert backend.supports(instr) is False           # 不认领
        assert backend.wired_ops() == ()                  # 空壳
        handled = dyn.execute_or_default(instr, object(), lambda i, m: calls.append(i.op))
        assert handled is False and calls == ["add"]      # 回退执行器原生
        with pytest.raises(DynamicSemanticsNotWired):     # 显式失败，不伪造成功
            backend.execute(instr, object())
    finally:
        dyn.set_active(None)


# ============================================================
# 3. 隔离红线：内核不依赖插件层；插件层零重型依赖
# ============================================================

_CORE_DIRS = ("src/kernel", "src/mbc")
_CORE_FILES = ("src/lexer.py", "src/parser.py", "src/ast_nodes.py")


def _core_sources() -> list[Path]:
    files: list[Path] = []
    for d in _CORE_DIRS:
        files += sorted((ROOT / d).rglob("*.py"))
    files += [ROOT / f for f in _CORE_FILES]
    return files


def _imported_roots(path: Path) -> set[str]:
    """静态解析模块真实 import 到的顶层名（避开注释/docstring 里的散文误判）。"""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def _imported_full(path: Path) -> list[str]:
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


@pytest.mark.parametrize("path", _core_sources(), ids=lambda p: str(p.relative_to(ROOT)))
def test_core_never_imports_plugin_contracts(path: Path):
    """纯内核 / 执行器不得 import 代数数或动态语义契约层（核心只依赖接口，接口在插件侧）。"""
    bad = [m for m in _imported_full(path)
           if m.startswith(("src.algebra", "src.dynamics"))]
    assert not bad, f"{path} 反向依赖插件契约层：{bad}"


@pytest.mark.parametrize("path", [
    ROOT / "src/algebra/interface.py",
    ROOT / "src/algebra/algebra_plugin.py",
    ROOT / "src/dynamics/interface.py",
    ROOT / "src/dynamics/dynamic_semantics_plugin.py",
], ids=lambda p: str(p.relative_to(ROOT)))
def test_plugin_contract_has_no_heavy_or_kernel_top_level_import(path: Path):
    """契约层只用标准库：不得 import sympy/numpy/scipy，也不得耦合内核内部。"""
    roots = _imported_roots(path)
    heavy = roots & {"sympy", "numpy", "scipy"}
    assert not heavy, f"{path.name} 引入重型依赖：{sorted(heavy)}"
    kernel = [m for m in _imported_full(path) if m.startswith("src.kernel")]
    assert not kernel, f"{path.name} 耦合内核内部：{kernel}"
