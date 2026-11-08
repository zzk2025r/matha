# -*- coding: utf-8 -*-
"""资源_成长恒零占位修复锁（阶段 5）。

背景（阶段 5 核查新发现，原未登记）：`src/library.py::_generate_candidate`
对未匹配需求静默生成 `(x) => 0` 恒零函数且 grow 返回 成功=True——
实测 `资源_成长("计算黑洞熵")` 成功入库恒零占位。本轮删除默认分支：
未匹配 → None → grow 走既有诚实失败路径（成功=False，不落盘不注册）。

本文件锁：
  1. 手算对拍：六个关键词模板生成的公式真算（圆/矩形面积、球/圆柱体积、
     牛顿力、动能），grow 提交后同解释器直接调用对拍手算值；
  2. 闭环：grow → 资源_加载 → 新解释器调用真算；保护隔离资源不被覆盖；
  3. 显式拒绝：未匹配需求 成功=False、不落盘、不注册、解释器不受污染；
  4. 活内建接线：资源_成长 柯里化三应用与 资源_加载 两应用（monkeypatch
     资源库根到 tmp_path，零仓库副作用）。
边界登记：关键词模板为窄路径（如「圆环面积」会误匹配圆面积模板），
语义级需求理解不背书——见 docs/KNOWN_ISSUES.md 阶段 5 条目。
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.library import Library, LibraryEntry  # noqa: E402
from src.parser import parse  # noqa: E402


def _call(ip: Interpreter, expr: str) -> list:
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse(f"#1：[{expr}]"))
    return list(ip.outputs)


@pytest.fixture()
def lib(tmp_path) -> Library:
    return Library(root=str(tmp_path))


# ============================================================
# 1. 手算对拍：六模板公式真算
# ============================================================

class TestTemplateParity:

    @pytest.mark.parametrize("requirement,call,expected", [
        ("计算圆面积", "圆面积(2)", 3.14159 * 2 * 2),
        ("计算矩形面积", "矩形面积(3, 4)", 12.0),
        ("计算球体积", "球体积(3)", 4 * 3.14159 * 27 / 3),
        ("计算圆柱体积", "圆柱体积(2, 5)", 3.14159 * 2 * 2 * 5),
        ("计算牛顿力", "牛顿力(2, 3)", 6.0),
        ("计算动能", "动能(2, 3)", 0.5 * 2 * 3 ** 2),
    ])
    def test_grown_formula_computes_hand_value(self, lib, requirement,
                                               call, expected):
        ip = Interpreter()
        r = lib.grow(ip, requirement, discipline="core")
        assert r.成功 is True and r.错误 is None
        assert _call(ip, call)[-1] == pytest.approx(expected)

    def test_file_content_has_exact_formula(self, lib, tmp_path):
        ip = Interpreter()
        r = lib.grow(ip, "计算球体积", discipline="core")
        assert r.新资源 == "core/计算球体积"
        content = (tmp_path / "core" / "计算球体积.matha").read_text(
            encoding="utf-8")
        assert "4 * 3.14159 * r ^ 3 / 3" in content


# ============================================================
# 2. 闭环：grow → 加载 → 新解释器真算；保护隔离不覆盖
# ============================================================

class TestGrowClosedLoop:

    def test_grow_load_call_on_fresh_interp(self, lib):
        ip1 = Interpreter()
        assert lib.grow(ip1, "计算球体积", discipline="core").成功 is True
        ip2 = Interpreter()
        r = lib.load("core/计算球体积", ip2)
        assert r["成功"] is True
        assert "球体积" in r["新函数"]
        assert _call(ip2, "球体积(3)")[-1] == pytest.approx(113.09724)

    def test_protected_resource_not_overwritten(self, lib, tmp_path):
        disc = tmp_path / "core"
        disc.mkdir()
        f = disc / "计算球体积.matha"
        f.write_text("(* 受保护原件 *)", encoding="utf-8")
        lib._cache["core/计算球体积"] = LibraryEntry(
            path="core/计算球体积", name="计算球体积", discipline="core",
            content="(* 受保护原件 *)", protected=True)
        lib._protected.add("core/计算球体积")
        ip = Interpreter()
        r = lib.grow(ip, "计算球体积", discipline="core")
        assert r.成功 is True
        assert f.read_text(encoding="utf-8") == "(* 受保护原件 *)"


# ============================================================
# 3. 显式拒绝：未匹配 → 成功=False，不落盘不注册不污染
# ============================================================

class TestUnmatchedRejection:

    @pytest.mark.parametrize("requirement", [
        "计算黑洞熵", "计算圆周率", "预测股票价格", "", "hello world",
    ])
    def test_unmatched_fails_honestly(self, lib, tmp_path, requirement):
        ip = Interpreter()
        r = lib.grow(ip, requirement, discipline="core")
        assert r.成功 is False
        assert r.新资源 is None
        assert "无法" in r.错误
        assert list(tmp_path.rglob("*.matha")) == []

    def test_failed_grow_does_not_pollute_interp(self, lib):
        from src.kernel.errors import MathaUndefinedNameError
        ip = Interpreter()
        lib.grow(ip, "计算黑洞熵", discipline="physics", name="黑洞熵")
        assert _call(ip, "1 + 1")[-1] == 2
        with pytest.raises(MathaUndefinedNameError, match="黑洞熵"):
            _call(ip, "黑洞熵(1)")

    def test_generate_candidate_returns_none(self, lib):
        assert lib._generate_candidate("计算黑洞熵", "core", "x") is None


# ============================================================
# 4. 活内建接线：资源_成长/资源_加载 柯里化形状（零仓库副作用）
# ============================================================

class TestBuiltinWiring:

    def test_builtin_grow_curried_matched(self, lib, monkeypatch):
        monkeypatch.setattr("src.library.get_library", lambda: lib)
        ip = Interpreter()
        r = ip.builtins["资源_成长"]("计算球体积")("core")("")
        assert r["成功"] is True
        assert _call(ip, "球体积(3)")[-1] == pytest.approx(113.09724)

    def test_builtin_grow_curried_unmatched(self, lib, monkeypatch):
        monkeypatch.setattr("src.library.get_library", lambda: lib)
        ip = Interpreter()
        r = ip.builtins["资源_成长"]("计算黑洞熵")("core")("")
        assert r["成功"] is False
        assert "无法" in r["错误"]

    def test_builtin_load_curried(self, lib, monkeypatch):
        monkeypatch.setattr("src.library.get_library", lambda: lib)
        ip1 = Interpreter()
        lib.grow(ip1, "计算球体积", discipline="core")
        ip2 = Interpreter()
        r = ip2.builtins["资源_加载"]("core/计算球体积")(0)
        assert r["成功"] is True
        assert _call(ip2, "球体积(3)")[-1] == pytest.approx(113.09724)