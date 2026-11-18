# -*- coding: utf-8 -*-
"""阶段 24a：Matha 资源库可以当代码使用/调用/编程（缺陷修复三锁）。

修复前缺陷（探针实证）：matha/library/ 全部 19 个资源文件不带 module 声明、
不在任何 use 解析路径上——`use collections_core` 报「找不到 Matha 模块」，
资源库只是 资源_加载 沙箱的单文件读取面，不能当代码 use/调用/编程。

修复面：
  1. 19 个资源文件全量包裹 `module <stem> { ... }`（verbatim 保形，
     MechUnit 自测块与全部内部声明保留；index.matha → 资源索引）；
  2. use 解析序扩展：matha/ 内置 → .matha_packages/ 安装包 →
     matha/library/ 资源库（安装包可覆盖同名内置资源 = 可升级语义）；
  3. index.matha 资源目录补全（9 → 18 条，与文件系统一一对应；
     阶段 24b/24h 增补绘画辅助/建模仿真/单片机后共 21 条）；
  4. .matha_packages/arithmetic 坏包重装（原包只有 manifest 无源码 = 假成功）；
  5. 资源_成长 生成的资源出生即带 module 声明（声明名 = 资源名）；
  6. 同名冲突规则（module X { func X }，成长资源形态）：平面函数可调用面
     优先，命名空间绑定跳过——宿主 env 与 VM STORE_GLOBAL 同规则。

本文件锁（host = Interpreter，vm = exec_api.run_checked 双面对拍）：
  A. 解析面：18 stem 全量带声明可解析 + 资源索引映射 + 目录完备性；
  B. 执行面：use collections_core / use 计算动能 真调用双面 + 缺失报错如实；
  C. 同名冲突规则双面 + 无冲突 点号面保留双面；
  D. 包面：安装包覆盖资源库 + 停用回退 + 坏包重装真实性；
  E. 成长面：grow 出生带声明 + 成长资源 use 可用。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import interp as interp_mod  # noqa: E402
from src.interp import Interpreter, _load_matha_source  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.library import Library  # noqa: E402
from src.parser import parse  # noqa: E402

LIB = ROOT / "matha" / "library"


def _host_run(source: str) -> list:
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse(source))
    return list(ip.outputs)


def _vm_run(source: str) -> list:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is None, f"vm 面不应报错: {type(err).__name__}: {err}"
    return list(outs)


def _library_stems() -> list[str]:
    return sorted(p.stem for p in LIB.rglob("*.matha") if p.stem != "index")


# ============================================================
# A. 解析面：全量 stem 带声明可解析
# ============================================================

class TestResolution:

    @pytest.mark.parametrize("stem", _library_stems())
    def test_stem_resolves_with_module_decl(self, stem):
        src = _load_matha_source(stem)
        assert src is not None
        assert src.lstrip().startswith(f"module {stem} "), \
            f"{stem}.matha 缺 module <stem> 声明"

    def test_index_via_cn2file_mapping(self):
        src = _load_matha_source("资源索引")
        assert src.lstrip().startswith("module 资源索引 ")

    def test_index_catalog_matches_filesystem(self):
        text = (LIB / "index.matha").read_text(encoding="utf-8")
        import re
        body = text.split("资源目录", 1)[1]
        entries = re.findall(r'"([^"]+)"', body)
        assert len(entries) == 28
        assert sorted(e.rsplit("/", 1)[-1] for e in entries) == _library_stems()

    def test_missing_module_error_lists_all_three_roots(self):
        with pytest.raises(FileNotFoundError) as ei:
            _load_matha_source("不存在的资源xyz")
        msg = str(ei.value)
        assert "找不到 Matha 模块" in msg
        for root in ("matha/", ".matha_packages/", "matha/library/ 资源库"):
            assert root in msg


# ============================================================
# B. 执行面：use 真调用（host ↔ vm 双面）
# ============================================================

class TestUseExecutes:

    def test_use_collections_core_host(self):
        outs = _host_run(
            "use collections_core\n"
            "输出(map((x) => x * x, [1, 2, 3]))\n"
            "输出(join(\",\", filter((x) => x > 1, [1, 2, 3, 4])))\n")
        assert outs == [[1, 4, 9], "2,3,4"]

    def test_use_collections_core_vm(self):
        outs = _vm_run(
            "use collections_core\n"
            "输出(map((x) => x * x, [1, 2, 3]))\n"
            "输出(join(\",\", filter((x) => x > 1, [1, 2, 3, 4])))\n")
        assert outs == [[1, 4, 9], "2,3,4"]

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_use_compute_kinetic_energy(self, face):
        run = _host_run if face == "host" else _vm_run
        outs = run("use 计算动能\n输出(动能(2.0, 3.0))\n")
        assert outs == [0.5 * 2.0 * 3.0 ** 2]

    def test_use_missing_module_host_raises(self):
        with pytest.raises(Exception) as ei:
            _host_run("use 不存在的资源xyz\n")
        assert "未找到模块" in str(ei.value)

    def test_use_missing_module_vm_honest_error(self):
        outs, err = exec_api.run_checked("use 不存在的资源xyz\n", mode="vm")
        assert err is not None
        assert "找不到 Matha 模块" in str(err)


# ============================================================
# C. 同名冲突规则：module X { func X } 平面可调用面优先
# ============================================================

_COLLIDE = (
    "module 圆面积 {\n"
    "  func 圆面积(r) -> Float = (r) => 3.14159 * r * r\n"
    "}\n"
    "输出(圆面积(2))\n"
)
_NO_COLLIDE = (
    "module 数学 {\n"
    "  func 加一(x) -> Int = (x) => x + 1\n"
    "}\n"
    "输出(数学.加一(1))\n"
    "输出(加一(41))\n"
)


class TestNameCollisionRule:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_collision_callable_wins(self, face):
        run = _host_run if face == "host" else _vm_run
        assert run(_COLLIDE) == [3.14159 * 2 * 2]

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_no_collision_namespace_and_flat_both_work(self, face):
        run = _host_run if face == "host" else _vm_run
        assert run(_NO_COLLIDE) == [2, 42]


# ============================================================
# D. 包面：安装包覆盖资源库 + 停用回退 + 坏包重装
# ============================================================

class TestPackageFace:

    def test_package_arithmetic_resolves_from_installed_pkg(self):
        pkg = ROOT / ".matha_packages" / "arithmetic" / "arithmetic.matha"
        assert pkg.exists()
        assert _load_matha_source("arithmetic") == pkg.read_text(encoding="utf-8")

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_use_arithmetic_callable(self, face):
        run = _host_run if face == "host" else _vm_run
        outs = run("use arithmetic\n输出(平方(4))\n输出(幂(2, 10))\n")
        assert outs == [16, 1024]

    def test_manifest_entry_and_no_self_dependency(self):
        meta = json.loads((ROOT / ".matha_packages" / "arithmetic" / "manifest.json")
                          .read_text(encoding="utf-8"))
        assert meta["entry"] == "arithmetic.matha"
        assert meta["dependencies"] == []
        assert (ROOT / ".matha_packages" / "arithmetic" / "arithmetic.matha").exists()

    def test_package_overrides_library(self, tmp_path, monkeypatch):
        monkeypatch.setattr(interp_mod, "_matha_dir", lambda: tmp_path)
        (tmp_path / "library").mkdir()
        (tmp_path / "library" / "dupres.matha").write_text(
            "module dupres {\n  func 标记() -> Int = () => 1\n}\n",
            encoding="utf-8")
        monkeypatch.setattr(interp_mod, "_package_module_source",
                            lambda name: "module dupres {\n  func 包版() -> Int = () => 2\n}\n")
        src = _load_matha_source("dupres")
        assert "包版" in src
        assert "标记" not in src

    def test_disabled_package_falls_back_to_library(self, tmp_path, monkeypatch):
        monkeypatch.setattr(interp_mod, "_matha_dir", lambda: tmp_path)
        (tmp_path / "library").mkdir()
        (tmp_path / "library" / "dupres.matha").write_text(
            "module dupres {\n  func 标记() -> Int = () => 1\n}\n",
            encoding="utf-8")
        monkeypatch.setattr(interp_mod, "_package_module_source", lambda name: None)
        src = _load_matha_source("dupres")
        assert "标记" in src


# ============================================================
# E. 成长面：grow 出生带声明 + 成长资源 use 可用
# ============================================================

class TestGrowEmitsModule:

    def test_grow_file_has_module_decl(self, tmp_path):
        lib = Library(root=str(tmp_path / "library"))
        ip = Interpreter(debug=False)
        assert lib.grow(ip, "计算球体积", discipline="core").成功 is True
        # 成长资源按学科子目录落盘（matha/library/core/… 同构），资源名 = 需求规范名
        text = (tmp_path / "library" / "core" / "计算球体积.matha").read_text(encoding="utf-8")
        assert "module 计算球体积 {" in text

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_grown_resource_usable_via_use(self, tmp_path, monkeypatch, face):
        lib = Library(root=str(tmp_path / "library"))
        ip = Interpreter(debug=False)
        assert lib.grow(ip, "计算球体积", discipline="core").成功 is True
        monkeypatch.setattr(interp_mod, "_matha_dir", lambda: tmp_path)
        run = _host_run if face == "host" else _vm_run
        outs = run("use 计算球体积\n输出(球体积(3))\n")
        assert outs == [4 * 3.14159 * 27 / 3]
