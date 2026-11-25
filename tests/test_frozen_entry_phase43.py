# -*- coding: utf-8 -*-
"""阶段 43 三锁：冻结可执行入口 + Matha 自身身份 + 纯 Matha 内核常驻监管。

阶段 43 的口径来自用户拍板原话——「先从进程映像开始，必须冻结 exe 而且必须是
Matha 的 exe，代办身份，正式从 python 脱离……并让 matha.exe 成为独立进程，非
python 的脚本」。本文件把这句话逐面钉住：

A 装配面（matha.spec，43a-1）：单一 Analysis + 单一 EXE、入口统一 CLI、语料入包、
  域插件 hiddenimports 由 manifest 派生且逐个真可导入（死条目锁）、零第三方运行时
  依赖边界（pyproject dependencies=[]）。
B 路径面（src/matha_chain.py + matha/loader.matha，43a-2）：解包根/MATHA_HOME/exe
  同级三态根序、`_read` 六件同源、诚实缺失报候选全集；链面装载器**自己**挑首个真含
  语料的根并把 cwd 现取位接进解析序——42-② 的根序分歧在此退役（双面同判锁）。
C Windows 入口面（43b）：全仓 .bat 活动行无 `src.matha_daemon` 死引用、服务包装器
  先冻结映像后模块面、`matha server` 命令位与 `serve()` 单一启动面、build.bat 产物
  平铺口径与 CI 同构。
D 身份面（43c）：src/ 零「裸 `python` 当命令启动」的 shell 注入位（AST 基 + 负控）、
  `运行脚本` 交回 Matha 自己的 run 子命令、`self_launcher` 两态（冻结 = matha.exe 自身）。
E 监督面（43d）：常驻/重启预算/收旧进程/重启判定全在纯 Matha 内核——同一 Matha 驱动
  host/vm 双面逐位同判；宿主桥只做 argv 与墙钟（AST 薄壳锁）。
F 真进程 e2e：统一 CLI 的 `监管` 子命令、真 cmd.exe 包装器与活动码页口径、冻结 exe 的
  被监管进程映像名取证（Win32 进程快照，非 python.exe）。
G 安装入口面（43g）：Windows 安装/卸载家族（.bat / .ps1 / .iss / .nsi）的产物落点统一
  为平铺 `dist/matha.exe` 口径、仓库根由脚本自身位置回推、版本唯一源、缺件守卫先于
  「安装完成」横幅、src 递归拷贝、用法文案只写真存在的子命令、开关真被读、PATH 逐条目
  双作用域、快捷方式落点走 Shell Folders、.bat 一律 CRLF + 码页切换；卸载入口住在待删
  目录之外，batch 走 TEMP 副本同行 exit 交接（cmd 逐行读盘，自删所在目录即断），
  PowerShell 侧不需要搬迁（先整体解析）——两条口径差用真跑钉住。

诚实边界（KNOWN_ISSUES 阶段 43 收官条目同源）：`.bat` 里的中文命令名按**控制台活动
码页**解字节（本机 OEM/ACP=65001 ⇒ UTF-8 编码的 .bat 可用、GBK 编码的 .bat 落到
argparse「未知子命令」）；PyInstaller onefile 的引导段会让 matha.exe 呈父子两映像。
"""
from __future__ import annotations

import ast
import codecs
import contextlib
import ctypes
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.set_int_max_str_digits(0)

from src import interp as host_interp  # noqa: E402
from src import matha_chain, os_runtime  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse as _py_parse  # noqa: E402
from src.os_runtime import OsRuntime, self_launcher  # noqa: E402

_SPEC = _ROOT / "matha.spec"
_EXE = _ROOT / "dist" / "matha.exe"
_MAIN = _ROOT / "src" / "matha_main.py"
_BAT_ROOTS_SKIP = {"mobile", "release", "build", "dist", "node_modules",
                   ".trae", ".git", "__pycache__", "scripts"}

_SUB_ENV = {k: v for k, v in os.environ.items() if k not in
            ("MATHA_TERM_BACKEND", "MATHA_HOME")}
_SUB_ENV.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(_ROOT)})

_frozen_gate = pytest.mark.skipif(not _EXE.is_file(),
                                  reason="dist/matha.exe 未构建（冻结面需先打包）")


def _read_py(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _strip_docstrings(text: str) -> str:
    """去掉模块/函数/类 docstring 后的正文。

    docstring 里记的是「既往怎么错的」（``exclude_binaries=True``、旧入口
    ``src/repl.py``、已删除的 ``src.matha_daemon``），文本级反面断言若把叙述算
    进来就永远红——口径说明不是装配指令，也不是可执行代码。
    """
    tree = ast.parse(text)
    spans = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            spans.add((body[0].lineno, body[0].end_lineno))
    lines = text.splitlines(keepends=True)
    for start, end in sorted(spans, reverse=True):
        del lines[start - 1:end]
    return "".join(lines)


def _spec_code() -> str:
    return _strip_docstrings(_SPEC.read_text(encoding="utf-8"))


def _norm(path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _call(vm, fn, *args):
    return vm.invoke_value(fn, list(args))


def _parse_src(text: str) -> ast.Module:
    return ast.parse(text)


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"未找到函数 {name}")


def _literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and
                       isinstance(v.value, str) else "{x}" for v in node.values)
    if isinstance(node, ast.List):
        return [_literal(e) for e in node.elts]
    return None


# ============================================================
# A 装配面：matha.spec（43a-1）
# ============================================================

@pytest.fixture(scope="module")
def spec_build():
    """以桩函数执行 matha.spec，取回真实装配参数（不启 PyInstaller）。"""
    calls: dict[str, tuple] = {}

    class _A:
        def __init__(self, scripts, kw):
            self.scripts = scripts
            self.pure = []
            self.binaries = []
            self.datas = kw.get("datas", [])

    def Analysis(scripts, **kw):
        calls["Analysis"] = (scripts, kw)
        return _A(scripts, kw)

    def PYZ(*a, **kw):
        calls["PYZ"] = (a, kw)
        return object()

    def EXE(*a, **kw):
        calls["EXE"] = (a, kw)
        return object()

    def COLLECT(*a, **kw):  # 出现即违反单产物口径
        calls["COLLECT"] = (a, kw)
        return object()

    ns = {"SPECPATH": str(_ROOT), "Analysis": Analysis, "PYZ": PYZ,
          "EXE": EXE, "COLLECT": COLLECT}
    exec(compile(_SPEC.read_text(encoding="utf-8"), "matha.spec", "exec"), ns)
    return calls


def test_43a1_spec_is_single_analysis_single_exe():
    """单一 Analysis + 单一 EXE，无 COLLECT / exclude_binaries（旧双份装配退役）。"""
    code = _spec_code()
    assert len(re.findall(r"\bAnalysis\(", code)) == 1
    assert len(re.findall(r"\bEXE\(", code)) == 1
    assert "COLLECT(" not in code
    assert "exclude_binaries" not in code


def test_43a1_spec_entry_is_unified_cli(spec_build):
    """入口 = src/matha_main.py 统一 CLI（旧首份以 src/repl.py 为入口，死装配）。"""
    scripts, kw = spec_build["Analysis"]
    assert [str(Path(s).as_posix()) for s in scripts] == \
           [(_ROOT / "src" / "matha_main.py").as_posix()]
    assert "repl.py" not in json.dumps([str(s) for s in scripts])
    assert kw["pathex"] == [str(_ROOT)]
    assert "src/repl.py" not in _spec_code()


def test_43a1_spec_exe_name_and_console(spec_build):
    kw = spec_build["EXE"][1]
    assert kw["name"] == "matha", "产物名即进程映像名——必须是 matha 不是 python"
    assert kw["console"] is True, "控制台保留——CMD 调用/管道/重定向的契约面"
    assert kw["upx"] is False and kw["debug"] is False


def test_43a1_spec_datas_contains_whole_corpus_same_shape(spec_build):
    """语料全量入包且**目录形状 = 仓库形状**（链面据 根()/matha/<名> 拼路径）。

    「同形状」是可判定的：每条 datas 的包内目标目录必须逐字等于该源文件的仓库
    相对父目录——解包根 ``sys._MEIPASS`` 下的树即仓库树，故 ``_ASSET_ROOT`` 拼
    ``matha/<名>.matha`` 在冻结态真命中。旧 ``datas=[]`` 时此断言整批落空。
    """
    datas = spec_build["Analysis"][1]["datas"]
    mapped = {}
    for src, dst in datas:
        rel = Path(src).resolve().relative_to(_ROOT.resolve()).as_posix()
        assert rel not in mapped, f"同一路径重复入包: {rel}"
        mapped[rel] = dst.replace("\\", "/")
    corpus = {p.resolve().relative_to(_ROOT.resolve()).as_posix()
              for p in (_ROOT / "matha").rglob("*.matha")
              if "__pycache__" not in p.parts}
    assert corpus <= set(mapped), sorted(corpus - set(mapped))
    stray = {r: mapped[r] for r in mapped if mapped[r] != PurePosixPath(r).parent.as_posix()}
    assert not stray, f"包内形状偏离仓库形状: {sorted(stray.items())[:5]}"
    assert "matha/lexer.matha" in mapped and "matha/os/kernel.matha" in mapped
    assert len(corpus) >= 60, f"语料集合异常小: {len(corpus)}"


def test_43a1_spec_packs_domain_manifest_for_dynamic_import(spec_build):
    """registry 走 importlib 动态导入 ⇒ manifest.json 必须入包（否则冻结态零插件）。"""
    datas = spec_build["Analysis"][1]["datas"]
    hits = [(s, d) for s, d in datas
            if Path(s).name == "manifest.json" and "domains" in Path(s).as_posix()]
    assert hits and hits[0][1] == "src/domains"


def test_43a1_spec_plugin_hiddenimports_derived_from_manifest(spec_build):
    """插件 hiddenimports 与 manifest 同源（旧手抄 57 名漏 32 个域）。"""
    hidden = set(spec_build["Analysis"][1]["hiddenimports"])
    manifest = json.loads((_ROOT / "src" / "domains" / "manifest.json")
                          .read_text(encoding="utf-8"))
    plugin_mods = {pl["module"] for pl in manifest["plugins"] if pl.get("module")}
    assert plugin_mods <= hidden
    assert "src.domains.registry" in hidden
    # 手抄面退役：装配正文不再逐个列域模块（派生函数只读一次 manifest）
    assert "'src.domains." not in _spec_code()


def test_43a1_spec_no_dead_hiddenimports(spec_build):
    """每个 hiddenimports 名字真可导入（17c 死条目清算的回归锁）。"""
    hidden = spec_build["Analysis"][1]["hiddenimports"]
    dead = [n for n in hidden if importlib.util.find_spec(n) is None]
    assert not dead, f"死 hiddenimports: {dead}"


def test_43a1_spec_excludes_third_party_host_sitepackages(spec_build):
    kw = spec_build["Analysis"][1]
    assert {"numpy", "matplotlib", "requests", "openai", "pytest"} <= set(kw["excludes"])


def test_43a1_zero_runtime_dependency_boundary_unchanged():
    """边界维持：pyproject dependencies=[]（PyInstaller 只在构建期）。"""
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies\s*=\s*\[\s*\]$", text, re.M), "零依赖边界变动"
    assert "pyinstaller" not in re.findall(r"^dependencies.*$", text, re.M)[0].lower()


def test_43a1_spec_paths_derive_from_specpath_not_absolute_literals():
    code = _spec_code()
    assert "SPECPATH" in code
    assert not re.search(r"[\"'][A-Za-z]:[\\/]", code), "spec 里不得硬编绝对路径"


def test_43a1_ci_and_spec_build_command_same_shape():
    """CI 与本地构建命令同源，产物平铺 dist/matha.exe。"""
    ci = (_ROOT / ".github" / "workflows" / "matha-ci.yml").read_text(encoding="utf-8")
    assert "python -m PyInstaller --noconfirm matha.spec" in ci
    assert "dist/matha.exe" in ci


# ============================================================
# B 路径面：冻结态根序与链面装载器（43a-2）
# ============================================================

@pytest.fixture(scope="module")
def chain():
    return matha_chain.MathaChain()


@pytest.fixture(scope="module")
def vm(chain):
    return chain.vm


@pytest.fixture(scope="module")
def loader(vm):
    return vm.globals["装载器"]


def test_43a2_override_roots_prefers_matha_home(monkeypatch, tmp_path):
    home = tmp_path / "home_corpus"
    monkeypatch.setenv("MATHA_HOME", f"  {home}  ")
    assert matha_chain._override_roots()[0] == Path(str(home).strip())
    monkeypatch.setenv("MATHA_HOME", "")
    assert Path(str(home).strip()) not in matha_chain._override_roots()


def test_43a2_roots_mirrors_host_matha_dir_candidates():
    """内置根序逐条镜像宿主 `_matha_dir` 的 _candidates（资产根 → cwd 上跳 → cwd）。"""
    tail = matha_chain._roots()[len(matha_chain._override_roots()):]
    assert tail == [matha_chain._ASSET_ROOT, Path.cwd().parent, Path.cwd()]
    # 开发态资产根 = 仓库根，且与宿主 `_matha_dir()` 的落点同源（冻结态另由
    # _MEIPASS 决定，测试进程非冻结，故此支是真断言不是恒等式）
    assert not matha_chain._FROZEN
    assert matha_chain._ASSET_ROOT == Path(host_interp.__file__).resolve().parent.parent
    assert matha_chain._EXE_DIR is None


def test_43a2_override_roots_order_is_home_then_exe_dir(monkeypatch, tmp_path):
    """覆盖根序 = MATHA_HOME 在前、exe 同级在后（外部漂移副本不敌包内快照）。"""
    home, exe = tmp_path / "home", tmp_path / "exedir"
    monkeypatch.setattr(matha_chain, "_EXE_DIR", exe)
    monkeypatch.setenv("MATHA_HOME", f" {home} ")
    assert matha_chain._override_roots() == [Path(f" {home} ".strip()), exe]
    monkeypatch.delenv("MATHA_HOME")
    assert matha_chain._override_roots() == [exe], "无 MATHA_HOME 时只剩 exe 同级"
    monkeypatch.setattr(matha_chain, "_EXE_DIR", None)
    assert matha_chain._override_roots() == [], "开发态无覆盖根"


def test_43a2_package_roots_put_cwd_first():
    """扩展包面 cwd 在前——宿主 `_package_module_path` 的 (cwd, 仓库根) 同序（42-②）。"""
    n = len(matha_chain._override_roots())
    assert matha_chain._package_roots()[n] == Path.cwd()
    assert matha_chain._package_roots()[n + 1] == matha_chain._ASSET_ROOT


def test_43a2_corpus_root_picks_first_hit_and_falls_back(monkeypatch, tmp_path):
    hit = tmp_path / "a"
    (hit / "matha").mkdir(parents=True)
    miss = tmp_path / "b"
    miss.mkdir()
    monkeypatch.setattr(matha_chain, "_roots", lambda: [miss, hit, tmp_path])
    assert matha_chain._corpus_root() == hit
    monkeypatch.setattr(matha_chain, "_roots", lambda: [miss, tmp_path / "zz"])
    assert matha_chain._corpus_root() == miss, "全不命中回落候选首位（宿主同落点）"


def test_43a2_read_reports_missing_file_with_candidate_list(monkeypatch, tmp_path):
    monkeypatch.setattr(matha_chain, "_corpus_root", lambda: tmp_path)
    with pytest.raises(FileNotFoundError) as ei:
        matha_chain._read("matha/lexer.matha")
    msg = str(ei.value)
    assert "装配源缺失" in msg and "matha/lexer.matha" in msg and "候选" in msg


def test_43a2_boot_files_read_from_one_corpus_root(monkeypatch, tmp_path):
    """六件一律同根：不同根混 pick 会让 boot 链自相矛盾（词法器 vs 解释器镜像）。"""
    root = tmp_path / "corpus"
    for rel in matha_chain.BOOT_FILES:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"SENTINEL::{rel}", encoding="utf-8")
    monkeypatch.setattr(matha_chain, "_corpus_root", lambda: root)
    for rel in matha_chain.BOOT_FILES:
        assert matha_chain._read(rel) == f"SENTINEL::{rel}"


def test_43a2_read_strips_bom(monkeypatch, tmp_path):
    root = tmp_path / "bom"
    (root / "matha").mkdir(parents=True)
    (root / "matha" / "x.matha").write_text("﻿module X {}", encoding="utf-8")
    monkeypatch.setattr(matha_chain, "_corpus_root", lambda: root)
    assert not matha_chain._read("matha/x.matha").startswith("﻿")


def test_43a2_boot_vm_injects_three_root_globals(vm):
    """装配方注入 装载根 / 装载根们 / 装载包根们——链面解析序的数据源。"""
    assert "装载根" in vm.globals and "装载根们" in vm.globals
    assert "装载包根们" in vm.globals
    root = vm.globals["装载根"]
    assert os.path.isabs(root) and (Path(root) / "matha").is_dir()
    assert all(os.path.isabs(str(r)) for r in vm.globals["装载根们"])
    assert all(os.path.isabs(str(r)) for r in vm.globals["装载包根们"])


def test_43a2_loader_root_matches_host_matha_dir(loader, vm):
    """`根()` 由 Matha 自己挑首个真含语料的根，与宿主 `_matha_dir()` 同判。"""
    assert _norm(_call(vm, loader["根"]) + "/matha") == _norm(host_interp._matha_dir())


def test_43a2_loader_root_uses_candidates_then_live_cwd(loader, vm):
    """候选序 = 装载根们 + 现取 cwd（装配期快照跟不上 换目录，现取位补此）。"""
    src = (_ROOT / "matha" / "loader.matha").read_text(encoding="utf-8")
    assert "func 根() -> String = 首个有语料(装载根们 + [当前目录()], 装载根)" in src
    assert _call(vm, loader["首个有语料"], [str(_ROOT)], "保底") == str(_ROOT)


def test_43a2_package_path_cwd_first_matches_host(loader, vm, tmp_path, monkeypatch):
    """42-② 退役锁：扩展包扫描双面同序、同结果（cwd 包优先于仓库根）。"""
    pkg = tmp_path / ".matha_packages" / "p43pkg"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps(
        {"entry": "main.matha", "enabled": True}, ensure_ascii=False),
        encoding="utf-8")
    (pkg / "main.matha").write_text("module p43pkg {}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    host = host_interp._package_module_path("p43pkg")
    got = _call(vm, loader["包路径"], "p43pkg")
    assert host is not None and got
    assert _norm(got) == _norm(host)


def test_43a2_disabled_package_terminates_scan_both_faces(loader, vm, tmp_path,
                                                          monkeypatch):
    """enabled=false → 宿主 return None（整包跳过且不续扫），链面 [真,""] 同判。"""
    pkg = tmp_path / ".matha_packages" / "p43off"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"enabled": False,
                                                  "entry": "main.matha"}),
                                       encoding="utf-8")
    (pkg / "main.matha").write_text("module x {}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert host_interp._package_module_path("p43off") is None
    assert _call(vm, loader["包路径"], "p43off") == ""


def test_43a2_empty_entry_not_treated_as_module_path(loader, vm, tmp_path, monkeypatch):
    """宿主 `if cand:` 跳过空 entry；链面 候选 只收非空入口名（43a-2 真化③）。"""
    pkg = tmp_path / ".matha_packages" / "p43empty"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"enabled": True, "entry": ""}),
                                       encoding="utf-8")
    (pkg / "p43empty.matha").write_text("module x {}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    host = host_interp._package_module_path("p43empty")
    assert host is not None and host.name == "p43empty.matha"
    assert _norm(_call(vm, loader["包路径"], "p43empty")) == _norm(host)


def test_43a2_cwd_carrier_arm_registered_both_images():
    """`当前目录` 臂双镜像同落（缺臂则链面装载器无法现取 cwd）。"""
    a = (_ROOT / "matha" / "interp_matha.matha").read_text(encoding="utf-8")
    b = (_ROOT / "matha" / "interp.matha").read_text(encoding="utf-8")
    assert 'name = "当前目录" ? 当前目录() :' in a
    assert '"当前目录", ("__builtin__", "当前目录")' in a
    assert '"当前目录", ["builtin", func_当前目录]' in b
    assert "func func_当前目录(v) -> Value = 当前目录()" in b


# ============================================================
# C Windows 入口面（43b）
# ============================================================

def _tracked_bats() -> list[Path]:
    out = []
    for p in _ROOT.rglob("*.bat"):
        parts = set(p.relative_to(_ROOT).parts)
        if parts & _BAT_ROOTS_SKIP:
            continue
        out.append(p)
    return out


def test_43b_no_dead_daemon_reference_in_active_lines():
    """全仓 .bat 活动行（去 REM/:: 注释）无 src.matha_daemon——阶段 11 已删的模块。"""
    bats = _tracked_bats()
    assert bats, "至少应扫到 scripts/build.bat 等入口脚本"
    offenders = []
    for p in bats:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.upper().startswith("REM") or s.startswith("::"):
                continue
            if "matha_daemon" in s:
                offenders.append(f"{p.name}: {s}")
    assert not offenders, offenders


def test_43b_daemon_module_stays_absent():
    assert not (_ROOT / "src" / "matha_daemon.py").exists()
    assert not (_ROOT / "src" / "matha_daemon").exists()


def test_43b_server_wrapper_prefers_frozen_image():
    text = (_ROOT / "start_matha_server.bat").read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines()
                     if l.strip() and not l.strip().upper().startswith("REM"))
    assert 'if exist "dist\\matha.exe"' in body
    assert '"dist\\matha.exe" server --port %PORT%' in body
    assert "python -m src.matha_main server --port %PORT%" in body
    assert "exit /b %RC%" in body
    assert "pause" in body, "失败路径仍给 pause——成功路径不阻塞（旧版无条件 pause）"


def test_43b_server_cli_command_delegates_to_serve():
    tree = _parse_src(_read_py("src/matha_main.py"))
    body = _func(tree, "_cmd_server")
    names = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
             for n in ast.walk(body) if isinstance(n, ast.Call)}
    assert "serve" in names
    text = _read_py("src/matha_main.py")
    assert 'sub.add_parser("server"' in text
    assert "from src.openai_compat_server import serve" in text


def test_43b_serve_is_the_single_startup_surface():
    """`serve()` 是唯一启动面；`main()` 只转发——端口全占用诚实返 1，不 sys.exit。"""
    text = _read_py("src/openai_compat_server.py")
    tree = _parse_src(text)
    serve_body = _func(tree, "serve")
    assert not any(isinstance(n, ast.Attribute) and n.attr == "exit"
                   for n in ast.walk(serve_body)), "serve 内不得 sys.exit（CLI 包装器负责退出码）"
    assert any(isinstance(n, ast.Return) for n in ast.walk(serve_body))
    main_body = _func(tree, "main")
    src_lines = ast.get_source_segment(text, main_body)
    assert "sys.exit(serve(args.host, args.port))" in src_lines
    # 死引用退役：已删除的 src.matha_daemon 不得再出现在任何可执行位（docstring
    # 里的历史叙述除外——那正是「为什么包装器曾指向它」的口径说明）
    assert "matha_daemon" not in _strip_docstrings(text)
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom))
                   and "matha_daemon" in ast.dump(n) for n in ast.walk(tree))


def test_43b_build_entries_flat_distpath_matches_ci():
    """三处构建入口（CI / build.bat / build_exe.py）产物形状同一：`dist/<名>.exe`。

    既往 `scripts/build_exe.py` 把 `--distpath` 设成 `dist/<名>`，本地产物落在
    `dist/<名>/<name>.exe`，而 CI 断言与 README 用的是平铺路径——冻结面的口径
    分歧会让「exe 是不是刚构建的那个」无法凭路径判定。
    """
    text = (_ROOT / "scripts" / "build.bat").read_text(encoding="utf-8")
    assert text.count('--distpath "%DIST_DIR%"') == 2
    assert '--distpath "%DIST_DIR%\\matha"' not in text
    assert 'dir "%DIST_DIR%\\%%T.exe"' in text

    py = (_ROOT / "scripts" / "build_exe.py").read_text(encoding="utf-8")
    tree = ast.parse(py)
    build_one = _func(tree, "build_one")
    body = ast.get_source_segment(py, build_one)
    assert '"--distpath", str(DIST_DIR)' in body
    assert "DIST_DIR / name" not in body            # 嵌套落点已退役
    assert '--onefile' in body                      # 单文件位仍在（打包口径可选）
    # workpath 仍按名分档——两次构建互撞会毁掉上一份 Analysis
    assert '"--workpath", str(BUILD_DIR / name)' in body


# ============================================================
# D 身份面：被启动的解释器 = Matha 自己（43c）
# ============================================================

_SHELL_FUNCS = {"shell_exec", "shell_exec_with_input", "system", "popen"}
_SUB_CALLS = {"run", "call", "check_output", "check_call", "Popen",
              "getoutput", "getstatusoutput"}
_BARE_PY = re.compile(r"^(python|py)\d?\s")


def _bare_python_shell_sites(text: str) -> list[str]:
    """src/ 里「以裸名 python 起 shell 命令」的调用位（43c 前的真缺陷形态）。"""
    hits = []
    for node in ast.walk(_parse_src(text)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else (
            f.id if isinstance(f, ast.Name) else "")
        if name in _SHELL_FUNCS:
            head = _literal(node.args[0])
            if isinstance(head, str) and _BARE_PY.match(head):
                hits.append(f"{name}: {head[:40]}")
        elif name in _SUB_CALLS:
            sh = next((k for k in node.keywords if k.arg == "shell"), None)
            if sh is not None and getattr(sh.value, "value", None) is True:
                head = _literal(node.args[0])
                if isinstance(head, str) and _BARE_PY.match(head):
                    hits.append(f"{name}(shell=True): {head[:40]}")
    return hits


def test_43c_src_has_zero_bare_python_shell_launch():
    sites = []
    for p in sorted((_ROOT / "src").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            sites += [f"{p.relative_to(_ROOT)} -> {h}"
                      for h in _bare_python_shell_sites(p.read_text(encoding="utf-8"))]
        except SyntaxError:
            continue
    assert sites == [], f"被启动解释器不得是 PATH 上的裸名 python: {sites}"


def test_43c_scanner_negative_control_not_vacuous():
    """负控：基线锁不是空扫——旧写法必须被同一扫描器抓到。"""
    assert _bare_python_shell_sites('def f(p):\n    return shell_exec(f"python {p}")\n')
    assert _bare_python_shell_sites('x = subprocess.run("python3 -c 1", shell=True)\n')
    assert _bare_python_shell_sites('x = subprocess.run([sys.executable, "a.py"])\n') == []


def test_43c_run_script_routes_matha_to_own_cli(tmp_path):
    from src.domains.os_module import shell_run_script

    src = tmp_path / "smoke.matha"
    src.write_text("输出(6 * 7)\n", encoding="utf-8")
    r = shell_run_script(str(src))
    assert r["success"] is True and r["returncode"] == 0, r
    assert r["stdout"].strip() == "42", r["stdout"]
    argv = r["command"].split()
    assert argv[0] == sys.executable
    assert argv[1].endswith("matha_main.py") and argv[2] == "run"


def test_43c_run_script_path_is_not_a_shell_injection_site(tmp_path):
    """路径作单个 argv 元素：`a & echo INJECTED.matha` 不被 shell 切开。"""
    from src.domains.os_module import shell_run_script

    r = shell_run_script(str(tmp_path / "a & echo INJECTED.matha"))
    assert r["success"] is False
    assert "INJECTED" not in (r["stdout"] or "")


def test_43c_run_script_non_matha_goes_to_sys_executable(tmp_path):
    from src.domains.os_module import shell_run_script

    p = tmp_path / "plain.py"
    p.write_text("print(5)\n", encoding="utf-8")
    r = shell_run_script(str(p))
    assert r["success"] is True and r["stdout"].strip() == "5", r
    assert r["command"] == f"{sys.executable} {p}"


def test_43c_run_script_registered_in_os_domain():
    """注册面闭环：`运行脚本` → `shell_run_script` → `_self_launcher`，且入符号表。"""
    tree = _parse_src(_read_py("src/domains/os_module.py"))
    assigned = {n.targets[0].slice.value: n.value for n in ast.walk(tree)
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript)
                and isinstance(getattr(n.targets[0], "slice", None), ast.Constant)}
    handler = assigned.get("运行脚本")
    assert isinstance(handler, ast.Name) and handler.id == "shell_run_script"
    body = _func(tree, "shell_run_script")
    called = {f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
              for f in (n.func for n in ast.walk(body) if isinstance(n, ast.Call))}
    assert {"_self_launcher", "run"} <= called, called
    assert not any(isinstance(k.value, ast.Constant) and k.value.value is True
                   for n in ast.walk(body) if isinstance(n, ast.Call)
                   for k in n.keywords if k.arg == "shell"), \
        "shell=True 使路径成为命令注入位"
    symtab = ast.get_source_segment(
        _read_py("src/domains/os_module.py"), _func(tree, "_os_symtab_names"))
    assert '"运行脚本"' in symtab.replace("'", '"'), "语言面可见名未登记"


def test_43c_self_launcher_two_states(monkeypatch, tmp_path):
    """冻结态 argv[0] = matha.exe 自身；开发态 = 宿主解释器 + 统一 CLI 入口。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "matha.exe"))
    assert self_launcher("终端", "a.msh") == [str(tmp_path / "matha.exe"), "终端", "a.msh"]
    monkeypatch.delattr(sys, "frozen", raising=False)
    got = self_launcher("eval", "1+1")
    assert got == [sys.executable, str(_ROOT / "src" / "matha_main.py"), "eval", "1+1"]


def test_43c_os_module_self_launcher_two_states(monkeypatch, tmp_path):
    from src.domains import os_module

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "matha.exe"))
    assert os_module._self_launcher("run") == [str(tmp_path / "matha.exe"), "run"]
    monkeypatch.delattr(sys, "frozen", raising=False)
    got = os_module._self_launcher("run")
    assert got[0] == sys.executable and got[1].endswith("matha_main.py") and got[2] == "run"


def test_43c_supervise_cli_builds_argv_via_self_launcher():
    """命令名不分叉：监管 argv 只由 self_launcher 产出，壳内不拼 PATH 裸名。"""
    text = _read_py("src/matha_main.py")
    assert "from src.os_runtime import OsRuntime, self_launcher" in text
    assert "argv = self_launcher(*cmd) if cmd else None" in text
    assert not re.search(r"argv\s*=\s*\[\s*[\"']python", text)


# ============================================================
# E 监督面：策略全在纯 Matha 内核（43d）
# ============================================================

_DRIVER = '''
use 内核

(* ---- 步函数：退步 = 一步即自然退出；长步 = 继续长驻 ---- *)
let 空列表 = []
let 退步 = (状态) => {
  let 报 = {"状态": null, "继续": false, "产出": 空列表}
  报
}
let 长步 = (状态) => {
  let 报 = {"状态": null, "继续": true, "产出": 空列表}
  报
}

(* ---- 描述符（列表值先 let 再入字典——字典值位裸列表是已登记解析缺陷面） ---- *)
let 空req = []
let 空服 = []
let 空入口 = []
let A入口 = [["主", 退步]]
let A = {"名": "A", "形态": "服务", "版本": 1, "requires": 空req,
         "入口": A入口, "服务": 空服, "常驻": 真, "重启预算": 2}
let B入口 = 空入口
let B = {"名": "B", "形态": "服务", "版本": 1, "requires": 空req,
         "入口": B入口, "服务": 空服, "常驻": 真, "重启预算": 3}
let C入口 = [["主", 退步]]
let C = {"名": "C", "形态": "服务", "版本": 1, "requires": 空req,
         "入口": C入口, "服务": 空服}
let D入口 = [["主", 长步]]
let D = {"名": "D", "形态": "服务", "版本": 1, "requires": 空req,
         "入口": D入口, "服务": 空服, "常驻": 真, "重启预算": 5}
let E入口 = [["主", 长步]]
let E = {"名": "E", "形态": "服务", "版本": 1, "requires": 空req,
         "入口": E入口, "服务": 空服, "常驻": 真, "重启预算": 1}

let k = 内核_新()

(* ---- 常驻 + 预算 2：启动自动派生主进程，退出即重启，预算耗尽即停 ---- *)
输出(装载(k, A)["结果"])
输出(启动(k, "A")["结果"])
输出(len(进程列表(k)))
输出(进程列表(k)[0][3])
let s0 = 监督状态(k, "A")
输出(s0["常驻"])
输出(s0["重启预算"])
输出(s0["就绪主进程数"])
输出(s0["已退出次数"])
let t1 = 调度(k, 1)
输出(t1["步数"])
输出(len(t1["事件"]))
输出(t1["事件"][0][0])
输出(t1["事件"][1][0])
输出(t1["事件"][1][2])
let t2 = 调度(k, 1)
输出(len(t2["事件"]))
let t3 = 调度(k, 1)
输出(len(t3["事件"]))
输出(t3["事件"][0][0])
let t4 = 调度(k, 1)
输出(t4["步数"])
输出(len(t4["事件"]))
let s1 = 监督状态(k, "A")
输出(s1["就绪主进程数"])
输出(s1["已退出次数"])
输出(len(进程列表(k)))

(* ---- 常驻无主入口：诚实拒绝，不静默造空转进程 ---- *)
输出(装载(k, B)["结果"])
let b = 启动(k, "B")
输出(b["结果"])
输出(b["原因"])
let q = 查询单元(k, "B")
输出(q["状态"])
输出(len(进程列表(k)))

(* ---- 非常驻：启动零扰动（不派生进程、监督读数全假/零） ---- *)
输出(装载(k, C)["结果"])
输出(启动(k, "C")["结果"])
输出(len(进程列表(k)))
let sc = 监督状态(k, "C")
输出(sc["常驻"])
输出(sc["重启预算"])

(* ---- 人工停止进程：落 已停止 不触发重启 ---- *)
输出(装载(k, D)["结果"])
输出(启动(k, "D")["结果"])
输出(进程列表(k)[len(进程列表(k)) - 1][3])
let dpid = 进程列表(k)[len(进程列表(k)) - 1][0]
输出(停止进程(k, dpid)["结果"])
let t5 = 调度(k, 1)
输出(len(t5["事件"]))
输出(停止(k, "D")["结果"])

(* ---- 收旧进程：常驻 停止→再启动 只留一条就绪主进程 ---- *)
输出(装载(k, E)["结果"])
输出(启动(k, "E")["结果"])
输出(停止(k, "E")["结果"])
输出(启动(k, "E")["结果"])
let se = 监督状态(k, "E")
输出(se["就绪主进程数"])
'''


def test_43d_kernel_supervision_policy_is_pure_matha_both_faces():
    """同一 Matha 驱动在 host / vm 双面逐位同判——监督策略不在 Python 里。"""
    ip = host_interp.Interpreter(debug=False)
    with _quiet():
        ip.run(_py_parse(_DRIVER))
    host_outs = list(ip.outputs)
    outs, err = exec_api.run_checked(_DRIVER, mode="vm")
    assert err is None, f"vm 面报错: {err}"
    assert outs == host_outs
    assert host_outs == _EXPECTED_SUPERVISION, json.dumps(
        {"got": host_outs}, ensure_ascii=False)


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


_EXPECTED_SUPERVISION = [
    "已装载", "运行中", 1, "就绪",          # A 启动自动派生主进程
    True, 2, 1, 0,                          # 监督读数：常驻/预算/就绪/退出
    1, 2, "退出", "重启", 2,                 # 第 1 轮：退出 → 重启 pid 2
    2,                                      # 第 2 轮：退出 → 重启 pid 3
    1, "退出",                              # 第 3 轮：退出（预算 2 已尽，不再重启）
    0, 0,                                   # 第 4 轮：空转（无就绪进程，步数 0）
    0, 3,                                   # 读数：就绪 0 / 已退出 3
    3,                                      # 进程表累计 3 条（重启不删旧行）
    "已装载", "拒绝", "常驻单元须有主入口", "已装载", 3,  # B：无主入口诚实拒绝
    "已装载", "运行中", 3, False, 0,         # C：非常驻零扰动（缺键 → 假/0）
    "已装载", "运行中", "就绪", "已停止", 0, "已停止",    # D：人工停止不重启
    "已装载", "运行中", "已停止", "运行中", 1,            # E：收旧进程后恰一条就绪
]


def test_43d_non_resident_start_zero_perturbation():
    rt = OsRuntime()
    rt.register_service("非常驻", lambda s: {"状态": None, "继续": False, "产出": []})
    assert rt.start("非常驻")["结果"] == "运行中"
    assert rt.process_list() == []
    got = rt.supervision("非常驻")
    assert got == {"常驻": False, "重启预算": 0, "就绪主进程数": 0, "已退出次数": 0}


def test_43d_resident_start_derives_main_process():
    rt = OsRuntime()
    rt.register_service("常驻", lambda s: {"状态": None, "继续": True, "产出": []},
                        常驻=True, 重启预算=3)
    assert rt.start("常驻")["结果"] == "运行中"
    procs = rt.process_list()
    assert len(procs) == 1 and procs[0][2] == "主" and procs[0][3] == "就绪"
    assert rt.supervision("常驻")["就绪主进程数"] == 1


def test_43d_resident_without_main_entry_honest_reject():
    rt = OsRuntime()
    desc = {"名": "无主", "形态": "服务", "版本": 1, "requires": [],
            "入口": [["健康", lambda s: {"状态": None, "继续": False, "产出": []}]],
            "服务": [], "常驻": True, "重启预算": 3}
    rt.load_descriptor(desc)
    r = rt.start("无主")
    assert r["结果"] == "拒绝" and r["原因"] == "常驻单元须有主入口", r
    assert rt.unit_info("无主")["状态"] == "已装载"
    assert rt.process_list() == []


def test_43d_restart_budget_zero_means_no_restart():
    rt = OsRuntime()
    rt.register_service("零预算", lambda s: {"状态": None, "继续": False,
                                             "产出": ["done"]},
                        常驻=True, 重启预算=0)
    rt.start("零预算")
    events = [rt.tick(1)["事件"] for _ in range(4)]
    assert events[0] == ["done", ["退出", 1]], events
    assert all(e == [] for e in events[1:])
    assert rt.supervision("零预算") == {"常驻": True, "重启预算": 0,
                                        "就绪主进程数": 0, "已退出次数": 1}


def test_43d_restart_budget_exact_count_and_event_shape():
    rt = OsRuntime()
    rt.register_service("计数", lambda s: {"状态": None, "继续": False, "产出": []},
                        常驻=True, 重启预算=2)
    rt.start("计数")
    rounds = [rt.tick(1) for _ in range(4)]
    assert [len(r["事件"]) for r in rounds] == [2, 2, 1, 0]
    assert [r["步数"] for r in rounds] == [1, 1, 1, 0], "重启不增步数（步数只计步进）"
    assert rounds[0]["事件"][1] == ["重启", "计数", 2]
    assert rounds[1]["事件"][1] == ["重启", "计数", 3]
    assert rt.supervision("计数") == {"常驻": True, "重启预算": 2,
                                      "就绪主进程数": 0, "已退出次数": 3}


def test_43d_stopped_unit_never_restarts():
    rt = OsRuntime()
    rt.register_service("停单", lambda s: {"状态": None, "继续": True, "产出": []},
                        常驻=True, 重启预算=5)
    rt.start("停单")
    rt.stop_process(rt.process_list()[0][0])
    assert [rt.tick(1)["事件"] for _ in range(2)] == [[], []]
    rt.stop("停单")
    assert all(rt.tick(1)["事件"] == [] for _ in range(2))
    assert rt.supervision("停单")["就绪主进程数"] == 0


def test_43d_resident_restart_reclaims_stale_ready_process():
    """收旧进程：常驻单元 停止→再启动 后仍只一条就绪主进程（桥面句柄按单元名索引）。"""
    rt = OsRuntime()
    d1 = rt.register_external("收旧", [sys.executable, "-c", "print('A')"],
                              常驻=True, 重启预算=1)
    rt.load_descriptor(d1)
    rt.start("收旧")
    rt.tick(1)
    rt.stop("收旧")
    d2 = rt.register_external("收旧", [sys.executable, "-c", "print('B')"],
                              版本=2, 常驻=True, 重启预算=1)
    rt.upgrade("收旧", d2)
    rt.start("收旧")
    rows = [p for p in rt.process_list() if p[1] == "收旧"]
    assert sum(1 for p in rows if p[3] == "就绪") == 1, rows
    assert rt.supervision("收旧")["就绪主进程数"] == 1
    assert ["收旧进程", "收旧", [1]] in rt._k[5], rt._k[5]


def test_43d_supervision_reading_absent_name_is_null():
    rt = OsRuntime()
    assert rt.supervision("不存在") is None


def test_43d_external_descriptor_carries_two_keys():
    rt = OsRuntime()
    desc = rt.register_external("外常", [sys.executable, "-c", "print(1)"],
                                常驻=True, 重启预算=7)
    assert desc["常驻"] is True and desc["重启预算"] == 7
    rt.load_descriptor(desc)
    assert rt.supervision("外常") == {"常驻": True, "重启预算": 7,
                                      "就绪主进程数": 0, "已退出次数": 0}


def test_43d_external_default_keys_off_by_default():
    rt = OsRuntime()
    desc = rt.register_external("外常2", [sys.executable, "-c", "print(1)"])
    assert desc["常驻"] is False and desc["重启预算"] == 0
    rt.load_descriptor(desc)
    assert rt.start("外常2")["结果"] == "运行中"
    assert rt.process_list() == []


def test_43d_kernel_zero_new_builtin_dependency():
    """内核仍只 use 标准库三符号——监督策略不得引入宿主专属内建。"""
    text = (_ROOT / "matha" / "os" / "kernel.matha").read_text(encoding="utf-8")
    line = next(l.strip() for l in text.splitlines()
                if l.strip().startswith("use 标准库"))
    assert line == "use 标准库 { len | 原地设置 | matha_type_of }", line
    assert not re.search(r"^use ", text.split("module 内核 {", 1)[1], re.M)


def test_43d_bridge_supervise_is_thin_wallclock_shell():
    """桥面 supervise 只数轮次 + 睡眠 + 转达读数——判定/重启不在 Python。"""
    tree = _parse_src(_read_py("src/os_runtime.py"))
    fn = _func(tree, "supervise")
    body = [n for n in fn.body if not (isinstance(n, ast.Expr)
                                       and isinstance(n.value, ast.Constant))]
    called = set()
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else
                       (f.id if isinstance(f, ast.Name) else ""))
    assert called <= {"tick", "sleep", "append", "int", "float", "回报"}, called
    assert "tick" in called and "sleep" in called
    src = ast.get_source_segment(_read_py("src/os_runtime.py"), fn)
    assert "while 轮数 <= 0 or i < int(轮数):" in src, "轮数<=0 即不限轮"
    assert "except" not in src, "不吞 KeyboardInterrupt（由调用方收口）"


def test_43d_supervision_call_flows_through_kernel_bridge():
    """桥面只调 内核 的 监督状态——读数来自纯 Matha，不是 Python 计算。"""
    src = ast.get_source_segment(_read_py("src/os_runtime.py"),
                                 _func(_parse_src(_read_py("src/os_runtime.py")),
                                       "supervision"))
    assert 'self._call("监督状态", self._k, name)' in src


def test_43d_self_launcher_is_the_only_argv_source_for_supervision():
    assert self_launcher() == [sys.executable, str(_ROOT / "src" / "matha_main.py")]


# ============================================================
# F 真进程 e2e：统一 CLI + 真 cmd.exe + 冻结映像
# ============================================================

def _py_cli(*args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(_MAIN), *args],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=_SUB_ENV, timeout=timeout)


def test_43f_supervise_cli_help_lists_all_four_knobs():
    for name in ("监管", "supervise"):
        r = _py_cli(name, "--help")
        assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
        out = r.stdout.decode("utf-8", "replace")
        assert all(k in out for k in ("预算", "轮数", "间隔", "单元")), out[:300]


def test_43f_supervise_cli_missing_command_honest_rc2():
    r = _py_cli("监管")
    assert r.returncode == 2, r.stdout.decode("utf-8", "replace")
    assert "缺少被监管命令" in r.stdout.decode("utf-8", "replace")


def test_43f_supervise_cli_dev_e2e_restarts_within_budget(tmp_path):
    """开发态真进程 e2e：被监管 = Matha 自己、退出即重启、预算尽即止。

    被监管命令取 `eval 1/0`（诚实失败，rc 1，~0.6s 起）——`轮数 × 间隔` 留出
    远超子进程启动的窗口，故 退出/重启 事件必落在轮次序列里。预算 1 ⇒ 恰好
    两次退出、不再第三次重启（就绪主进程数 0）。
    """
    r = _py_cli("监管", "--预算", "1", "--轮数", "12", "--间隔", "0.25",
                "--单元", "flaky", "--", "eval", "1/0", timeout=300)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, out
    assert "被监管 argv: [" in out and "matha_main.py" in out
    assert "事件 ['退出', 1]" in out and "事件 ['重启', 'flaky', 2]" in out, out
    assert "事件 ['退出', 2]" in out, out
    assert "计算失败: 除零错误" in out, "被监管进程 stdout 未作为产出事件转达"
    assert "监督读数: {'常驻': True, '重启预算': 1, '就绪主进程数': 0, '已退出次数': 2}" in out, out
    assert "停止: {'结果': '已停止'" in out, out
    assert "事件 ['重启', 'flaky', 3]" not in out, "预算已尽仍重启"


def _cmd_bat(body: str, encoding: str, tmp_path: Path) -> Path:
    p = tmp_path / "run.bat"
    p.write_bytes(body.replace("\n", "\r\n").encode(encoding, errors="replace"))
    return p


def test_43f_ascii_alias_works_through_real_cmd_exe(tmp_path):
    """ASCII 别名 supervise 与码页无关——任何控制台都能调用统一 CLI。"""
    bat = _cmd_bat(f'@echo off\ncd /d "{_ROOT}"\n"{sys.executable}" src\\matha_main.py'
                   f" supervise --help\n", "ascii", tmp_path)
    r = subprocess.run(["cmd.exe", "/c", str(bat)], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=180)
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")[:300]


def test_43f_chinese_command_name_bat_needs_active_codepage(tmp_path):
    """登记口径锁：.bat 的中文命令名按**控制台活动码页**解字节（本机 OEM=65001）。

    同序两跑：编码 == 活动码页 → 命中子命令；编码取另一侧 → argparse 落「未知子命令」。
    产品侧无缺陷（直接 CreateProcess 传 Unicode argv 一直可用），故只钉这一环境口径。
    """
    oem = ctypes.windll.kernel32.GetOEMCP()
    active = "utf-8" if oem == 65001 else f"cp{oem}"
    other = "gbk" if oem == 65001 else "utf-8"
    codecs.lookup(active) and codecs.lookup(other)
    body = (f'@echo off\ncd /d "{_ROOT}"\n"{sys.executable}" src\\matha_main.py'
            f" 监管 --help\n")
    ok = subprocess.run(["cmd.exe", "/c", str(_cmd_bat(body, active, tmp_path))],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    assert ok.returncode == 0, ok.stdout.decode("utf-8", "replace")[:300]
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad = subprocess.run(["cmd.exe", "/c", str(_cmd_bat(body, other, bad_dir))],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    assert bad.returncode != 0, bad.stdout.decode("utf-8", "replace")[:300]


def test_43f_repo_shipped_bats_are_ascii_or_utf8_decodable():
    """仓内 .bat 至少可按 UTF-8 解码——否则中文命令名在 UTF-8 码页控制台上不可用。"""
    for p in _tracked_bats():
        text = p.read_bytes()
        try:
            text.decode("utf-8")
        except UnicodeDecodeError as e:  # noqa: PERF203
            pytest.fail(f"{p.relative_to(_ROOT)} 非 UTF-8 可解码: {e}")
    for extra in (_ROOT / "start_matha_server.bat", _ROOT / "scripts" / "build.bat"):
        assert extra.read_bytes().decode("utf-8")


@_frozen_gate
def test_43f_frozen_exe_is_matha_image_not_python():
    r = subprocess.run([str(_EXE), "eval", "1+1"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=_SUB_ENV, timeout=180)
    assert r.returncode == 0
    assert r.stdout.decode("utf-8", "replace").strip() == "2"


@_frozen_gate
def test_43f_frozen_supervision_child_image_is_matha_exe(tmp_path):
    """matha.exe 监管 matha.exe：被监管进程映像名是 matha.exe，树内无 python.exe。

    窗口口径：onefile 引导段每次解包 ~5.5s（实测），故 `轮数 × 间隔` 必须覆盖
    「起 → 退 → 重启 → 再退」两次冷启，不能靠 CIM 轮询自身耗时凑窗口。
    """
    foreign = tmp_path / "no_matha_dir"
    foreign.mkdir()
    cmd = [str(_EXE), "监管", "--预算", "1", "--轮数", "120", "--间隔", "0.15",
           "--单元", "flaky", "--", "eval", "1+1"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=str(foreign), env=_SUB_ENV)
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='matha.exe' or "
          "Name='python.exe'\" | Select-Object ProcessId,ParentProcessId,Name "
          "| ConvertTo-Json -Compress")
    kids: set[str] = set()
    while proc.poll() is None:
        time.sleep(0.5)
        snap = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              stdout=subprocess.PIPE, timeout=120)
        txt = snap.stdout.decode("utf-8", "replace").strip()
        if txt:
            rows = json.loads(txt)
            rows = rows if isinstance(rows, list) else [rows]
            kids |= {r["Name"] for r in rows
                     if r.get("ParentProcessId") == proc.pid}
        assert time.time() - t0 < 180, "冻结监管 e2e 超时"
    out = proc.communicate()[0].decode("utf-8", "replace")
    assert proc.returncode == 0, out
    assert f"'{str(_EXE)}'" in out.replace("\\\\", "\\"), out
    assert "python.exe" not in out, out
    assert kids == {"matha.exe"}, f"被监管子进程映像名集: {kids}"
    assert "['重启', 'flaky', 2]" in out, out


@_frozen_gate
def test_43f_frozen_terminal_chain_backend_self_contained(tmp_path):
    """冻结态 + 外来 cwd（无 matha/）：终端 链面后端 装载 .msh 仍跑通（43a-1② + 42c）。"""
    foreign = tmp_path / "far"
    foreign.mkdir()
    (foreign / "s.msh").write_text('运行 "输出(6 * 7)"\n', encoding="utf-8")
    r = subprocess.run([str(_EXE), "终端", "s.msh"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, cwd=str(foreign), env=_SUB_ENV,
                       timeout=420)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, out
    assert out.strip().endswith("42"), out


@_frozen_gate
def test_43f_frozen_matha_home_missing_honest_error(tmp_path):
    """MATHA_HOME 覆盖生效且不静默回落：树缺件即如实报装配源缺失（非零退出）。"""
    broken = tmp_path / "broken_home"
    (broken / "matha").mkdir(parents=True)
    env = dict(_SUB_ENV)
    env["MATHA_HOME"] = str(broken)
    r = subprocess.run([str(_EXE), "终端", "-c", "回显 hi"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env, timeout=300)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode != 0, out
    assert "装配源缺失" in out, out
# ============================================================
# G 安装入口面：Windows 安装/卸载家族的产物落点与删除口径（43g）
# ============================================================
#
# 这一段判据全部来自**真跑**取证，不是静态阅读：
# * cmd.exe 逐行读盘——脚本删掉自己所在的目录就读不到后续行（实测 rc=1 +
#   「The system cannot find the path specified.」），删自己的文件更直接打
#   「The batch file cannot be found.」；
# * PowerShell 先把整脚本解析成管道再执行——自删目录后照样打印并回出口码（实测）。
# 两套载体边界不同，所以 batch 走「TEMP 副本 + 同行 exit 交接」，.ps1 不需要搬迁。

_SCRIPTS = _ROOT / "scripts"
_PS1_INSTALLERS = ("install.ps1", "uninstall.ps1", "matha_install.ps1",
                   "setup_matha.ps1", "setup_workspace.ps1")
_BAT_INSTALLERS = ("install.bat", "uninstall.bat", "build.bat", "install_flutter.bat")
_ISS_INSTALLERS = ("matha_installer.iss", "matha_installer.nsi")


def _inst(name: str) -> Path:
    p = _SCRIPTS / name
    assert p.is_file(), f"安装入口缺失: {p}"
    return p


def _inst_text(name: str) -> str:
    return _inst(name).read_text(encoding="utf-8")


def _is_comment(ln: str) -> bool:
    """bat 的 REM/::、ps1 的 #、iss/nsi 的 ; 与 # ——注释行不参与反面断言。"""
    s = ln.strip()
    return (not s) or s.lower().startswith(("rem", "::")) or s[0] in "#;'"


def _active_indexes(name: str, needle: str) -> list:
    """只数活动行里的命中——「安装完成」在勘误注释里也出现，按全文索引会误判先后。"""
    return [i for i, ln in enumerate(_inst_text(name).splitlines())
            if needle in ln and not _is_comment(ln)]


def _active_lines(name: str) -> list:
    """剥掉注释行——注释里记的是「既往怎么错的」，反面断言把叙述算进来就永远红。"""
    return [ln for ln in _inst_text(name).splitlines() if not _is_comment(ln)]


_ADVERTISE = re.compile(r"^\s*(echo\b|Log\b|Write-Host\b|Write-Output\b|print\()|"
                        r"Description\s*:", re.I)


def _usage_lines(name: str) -> list:
    """只取「对用户念一遍」的行：echo / Log / Write-Host / print / iss 的 Description。

    不加这层过滤会把 `if exist "…\\matha.exe" set …` 这类代码行当成用法文案，
    判据就变成「装脚本里任何一处 matha.exe 后面的词都得是子命令」——假红。
    """
    return [ln for ln in _active_lines(name) if _ADVERTISE.search(ln)]


def _cli_surface(rel: str) -> set:
    """从 argparse 源取真存在的子命令名（含 aliases）——判据来自源码，不来自抄写。"""
    tree = ast.parse(_read_py(rel))
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_parser" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
            for kw in node.keywords:
                if kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    names |= {e.value for e in kw.value.elts
                              if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return names


def _run_cmd(args, cwd=None, stdin=b"", extra_env=None, timeout=240):
    env = dict(os.environ)
    env.update(extra_env or {})
    r = subprocess.run(["cmd.exe", "/c", *args], input=stdin, cwd=cwd, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace")


_WIN = pytest.mark.skipif(sys.platform != "win32", reason="Windows 安装入口面需真 CMD/PowerShell")
_NOISE_MARKS = ("cannot be found", "cannot find the path", "not recognized",
                "系统找不到", "不是内部或外部命令")


def _noise_lines(out: str) -> list:
    return [ln.strip() for ln in out.splitlines()
            if any(n in ln.lower() for n in _NOISE_MARKS)]


def _sandbox_env(root: Path) -> dict:
    """把 APPDATA / LOCALAPPDATA / ProgramData / 桌面落点全收进 tmp——卸载流程可跑完
    而不触碰真实用户配置（MATHA_UNINST_DESKTOP 与 install.bat 共用同一开关）。"""
    for d in ("appdata", "localappdata", "programdata", "desktop"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return {"APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
            "ProgramData": str(root / "programdata"),
            "USERPROFILE": str(root / "userprofile"),
            "MATHA_UNINST_DESKTOP": str(root / "desktop")}


def _fake_install(root: Path, name: str, *, artifacts: bool = True,
                  with_bat: bool = True) -> Path:
    d = root / name
    (d / "src").mkdir(parents=True, exist_ok=True)
    if artifacts:
        (d / "matha.exe").write_bytes(b"MZ-fake")
    else:
        (d / "readme.txt").write_text("与 Matha 无关的同名目录\n", encoding="utf-8")
    if with_bat:
        (d / "uninstall.bat").write_bytes(_inst("uninstall.bat").read_bytes())
    return d


def _wait_gone(target: Path, seconds: float = 25.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline and target.exists():
        time.sleep(0.2)
    time.sleep(0.4)          # 副本的尾部 echo 也要落到父进程继承的管道里
    return not target.exists()


_REAL_INSTALL_MARKS = (Path(r"C:\Program Files\Matha\matha.exe"),
                       Path(os.path.expanduser(os.path.join("~", "Matha", "matha.exe"))))


def _skip_if_real_install():
    """带删除动作的卸载流程只在机器上确实没有真 Matha 安装时才跑。

    uninstall.bat 的 INSTALL_DIR 探测在沙盒里找不到产物时会回落到系统默认位置——
    那边真有安装就等于拿用户的安装目录做删除实验。
    """
    for p in _REAL_INSTALL_MARKS:
        if p.exists():
            pytest.skip(f"检测到真实 Matha 安装 {p}，卸载删除流程不在该机器上执行")


def test_43g_installers_reference_flat_dist_products_only():
    """六个安装入口的冻结产物口径统一为平铺 `dist\\matha.exe` / `dist\\matha-cc.exe`。

    已退役的 `matha-offline\\` 与嵌套 `dist\\<名>\\<名>.exe` 布局只允许作为勘误叙述
    出现在注释里——活动行里出现就是指向不存在的路径（iscc/makenss 直接编译失败）。
    """
    for name in ("install.bat", "install.ps1", "matha_install.ps1",
                 "setup_matha.ps1") + _ISS_INSTALLERS:
        text = _inst_text(name)
        assert "matha.exe" in text and "matha-cc.exe" in text, name
        for ln in _active_lines(name):
            assert "matha-offline" not in ln, f"{name}: 活动行仍指退役布局: {ln.strip()}"
            assert "dist\\matha\\" not in ln and "dist/matha/" not in ln, name
    assert 'if not exist "%REPO_ROOT%\\dist\\matha.exe"' in _inst_text("install.bat")
    assert 'Join-Path $RepoRoot "dist\\matha.exe"' in _inst_text("install.ps1")
    assert 'Join-Path $RepoRoot "dist\\matha.exe"' in _inst_text("matha_install.ps1")
    assert 'Source: "dist\\matha.exe"' in _inst_text("matha_installer.iss")
    assert 'File "dist\\matha.exe"' in _inst_text("matha_installer.nsi")
    assert re.search(r"^OutputDir=dist\s*$", _inst_text("matha_installer.iss"), re.M)
    assert '!define OUTPUT_DIR "dist"' in _inst_text("matha_installer.nsi")


def test_43g_repo_root_derived_from_script_location():
    """安装入口住在 scripts\\ 下：产物基准一律由自身位置回推仓库根。

    旧写法把 dist\\ src\\ docs\\ tests\\ pyproject.toml 拼在 scripts\\ 之后，所有存在性
    判定恒假，脚本却照样打印「安装完成！」——典型假成功。
    """
    bat = _inst_text("install.bat")
    assert 'set "SCRIPT_DIR=%~dp0"' in bat
    assert 'for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"' in bat
    for name in ("install.ps1", "matha_install.ps1", "setup_matha.ps1"):
        ps = _inst_text(name)
        assert "$RepoRoot = Split-Path -Parent $ScriptDir" in ps, name
        assert re.search(r"\$ScriptDir\s*=\s*Split-Path\s+-Parent\s+\$My", ps), name
    assert re.search(r"^SourceDir=\.\.\s*$", _inst_text("matha_installer.iss"), re.M), \
        "iss 缺 SourceDir=..（相对路径按 .iss 所在目录解析）"
    assert '!cdpath "${__FILEDIR__}\\.."' in _inst_text("matha_installer.nsi"), \
        "nsi 缺 !cdpath（File 按 makensis 当前目录解析）"


def test_43g_version_single_source_across_installers():
    """版本读数只来自 src\\__version__.py；iss/nsi 的回落字面值与唯一版本源同步。"""
    from src.__version__ import __version__ as real_version
    for name in ("install.bat", "install.ps1", "uninstall.ps1", "matha_install.ps1",
                 "setup_matha.ps1", "install.py"):
        assert "__version__.py" in _inst_text(name), f"{name} 未取唯一版本源"
    for name in ("install.ps1", "matha_install.ps1", "setup_matha.ps1", "uninstall.ps1"):
        assert re.search(r"Pattern\s+'\^__version__", _inst_text(name)), name
    iss_v = re.search(r'#define\s+Version\s+"([^"]+)"', _inst_text("matha_installer.iss"))
    nsi_v = re.search(r'!define\s+VERSION\s+"([^"]+)"', _inst_text("matha_installer.nsi"))
    assert iss_v.group(1) == real_version, "iss 回落版号与唯一版本源漂移"
    assert nsi_v.group(1) == real_version, "nsi 回落版号与唯一版本源漂移"
    for name in ("install.bat", "install.ps1", "uninstall.ps1", "matha_install.ps1",
                 "setup_matha.ps1"):
        for ln in _active_lines(name):
            assert not re.search(r"(VERSION|Version)\s*=\s*\"?4\.[0-5]\b", ln), \
                f"{name}: 活动行硬编旧版号: {ln.strip()}"


def test_43g_missing_product_guard_precedes_completion_banner():
    """缺件必须失败退出，且守卫位落在「安装完成」之前——否则横幅就是假成功。"""
    marks = {"install.bat": "缺少 dist\\matha.exe",
             "install.ps1": "缺少 $MathaExe",
             "matha_install.ps1": "[中止] 使用端为空",
             "setup_matha.ps1": "[错误] 缺少 $MathaExe"}
    for name, guard in marks.items():
        lines = _inst_text(name).splitlines()
        hits = _active_indexes(name, "安装完成")
        assert hits, f"{name} 活动行里没有完成横幅（口径变了要同步本锁）"
        guard_at = next((i for i, ln in enumerate(lines)
                         if guard in ln and not ln.strip().startswith(("#", "REM", "rem", "::"))),
                        None)
        assert guard_at is not None, f"{name} 缺件守卫文案变了（同步本锁）"
        assert guard_at < hits[0], f"{name}: 守卫在第 {guard_at} 行，完成横幅在第 {hits[0]} 行"
        tail = "\n".join(lines[guard_at:hits[0]])
        assert re.search(r"(exit\s+/b\s+\d|exit\s+\d|throw|Write-Error)", tail), \
            f"{name}: 守卫后没有失败退出位"
    # 卸载侧同样：产物校验先于任何删除
    for name in ("uninstall.ps1", "setup_matha.ps1", "install.ps1"):
        up = _inst_text(name)
        assert up.index("内没有 Matha 产物") < up.index("Remove-Item $InstallDir"), name


def test_43g_src_copy_is_recursive_in_every_installer():
    """src 整树递归拷贝——src\\kernel 与 src\\mbc 是解释器/VM 的必需件。

    旧写法只拷 compiler/domains/offline/stdlib 四片，装出来的树 import 不起来。
    """
    assert re.search(r"xcopy[^\r\n]*src[^\r\n]*/s", _inst_text("install.bat"))
    assert re.search(r'File\s+/r\s+"src\\\*\.py"', _inst_text("matha_installer.nsi"))
    assert re.search(r'Source:\s*"src\\\*\.py".*recursesubdirs', _inst_text("matha_installer.iss"))
    ps = _inst_text("install.ps1")
    assert re.search(r"Get-ChildItem[^\r\n]*-Recurse", ps), "install.ps1 未递归枚举 src 子包"
    assert "New-Item -ItemType Directory -Path $dir" in ps, "install.ps1 未重建子目录形状"
    mi = _inst_text("matha_install.ps1")
    assert re.search(r"Copy-Item[^\r\n]*-Recurse", mi), "matha_install.ps1 src 拷贝未递归"


def test_43g_usage_text_advertises_only_real_commands():
    """安装完成后的用法指引只能写真存在的子命令名。"""
    real = _cli_surface("src/matha_main.py") | _cli_surface("src/compiler/matha_cc_cli.py")
    assert {"repl", "eval", "run", "compile", "matha2c"} <= real
    seen = {}
    for name in _PS1_INSTALLERS + _BAT_INSTALLERS + _ISS_INSTALLERS + ("install.py",):
        toks = set()
        for ln in _usage_lines(name):
            for pat in (r"matha-cc\.exe\"?\s+([A-Za-z][\w-]*)",
                        r"(?<!-)matha\.exe\"?\s+([A-Za-z][\w-]*)",
                        r"Entry`?\"?\s+([A-Za-z][\w-]*)",
                        r"(?<![\w.\-])matha\s+([a-z][a-z0-9_-]{2,})\b"):
                for m in re.finditer(pat, ln):
                    toks.add(m.group(1))
        if toks:
            seen[name] = toks
    assert {"install.bat", "install.ps1", "matha_install.ps1", "build.bat"} <= set(seen), \
        f"用法文案采集面收窄（本锁会空转）: {sorted(seen)}"
    bad = sorted({t for toks in seen.values() for t in toks if t not in real})
    assert not bad, f"用法文案指向不存在的子命令: {bad}（真存在面: {sorted(real)}）"


def test_43g_declared_switches_are_actually_honored():
    """声明出来的开关必须真被读：-NoDesktop / -NoStartMenu / -AddToPath / -SkipIcons / -Force。

    旧写法把 New-Item 建开始菜单目录放在 -NoStartMenu 守卫之外，且「桌面快捷方式」
    摘要段无条件打印——-SkipIcons 传了也白传，尾部还声称建了图标。
    """
    ps = _inst_text("install.ps1")
    assert "if ($NoDesktop) { return }" in ps
    assert "if ($NoStartMenu) { return }" in ps
    assert "if ($AddToPath)" in ps
    assert "(-not $Force)" in ps
    mi = _inst_text("matha_install.ps1")
    assert mi.count("if (-not $SkipIcons) {") >= 3, "快捷方式/摘要段落未全按开关分支"
    un = _inst_text("uninstall.ps1")
    assert "param([switch]$Force)" in un and "if (-not $Force)" in un


def test_43g_path_editing_is_per_entry_and_admin_safe():
    """PATH 增删逐条目 + 双作用域 + 非管理员不炸。

    旧写法两处坑：① `$currentPath -replace ";$InstallDir"` 整串替换会误伤同名前缀
    目录，且只清 Machine 一侧——非管理员安装写进的是 User PATH，卸载后命令仍残留；
    ② `$ErrorActionPreference="Stop"` 下非管理员写 Machine PATH 抛 SecurityException，
    文件已拷完的安装直接中断。
    """
    for name in ("install.ps1", "uninstall.ps1"):
        ps = _inst_text(name)
        assert 'foreach ($scope in @("Machine", "User"))' in ps, name
        assert '-split ";"' in ps, name
        assert "Where-Object" in ps, name
    for name in ("install.ps1", "uninstall.ps1"):
        ps = _inst_text(name)
        seg = ps[ps.index('foreach ($scope in @("Machine", "User"))'):]
        assert "try {" in seg[:900] and "} catch {" in seg[:1100], f"{name}: 作用域写入未兜异常"
    assert '$ErrorActionPreference = "Stop"' in _inst_text("install.ps1")
    assert "SetEnvironmentVariable($Path" not in _inst_text("install.ps1")  # 无整串覆盖位
    for ln in _active_lines("uninstall.ps1"):
        assert "-replace [regex]::Escape(" not in ln, f"整串 PATH 正则替换: {ln.strip()}"


def test_43g_shell_folder_apis_used_not_profile_literals():
    """快捷方式落点走 Shell Folders（注册表 / GetFolderPath），不硬拼 %USERPROFILE%\\Desktop。

    桌面被 OneDrive 重定向时 %USERPROFILE%\\Desktop 是错路径：建出的图标桌面上看不见，
    卸载也删不到；开始菜单同理分「当前用户」与「所有用户」两处。
    """
    for name in ("install.ps1", "uninstall.ps1", "matha_install.ps1"):
        ps = _inst_text(name)
        assert 'GetFolderPath("Desktop")' in ps, name
    for name in ("install.ps1", "uninstall.ps1", "matha_install.ps1"):
        ps = _inst_text(name)
        assert 'GetFolderPath("Programs")' in ps or 'GetFolderPath("CommonPrograms")' in ps, name
    for name in ("install.bat", "uninstall.bat"):
        bat = _inst_text(name)
        assert "User Shell Folders\" /v Desktop" in bat, name
    # %APPDATA% 的 Start Menu 与注册表口径一致（当前用户程序组），并覆盖所有用户组
    both = _inst_text("uninstall.bat")
    assert "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Matha" in both
    assert "%ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs\\Matha" in both


def test_43g_windows_bats_are_crlf_and_codepage_guarded():
    """仓内 .bat 一律 CRLF + 第 2 行切 UTF-8 码页 + goto 标签闭合。

    LF-only 会让 cmd 的行读位置错位（for/标签首当其冲），GBK 控制台上 UTF-8 中文
    提示直接乱码——两者都是「装了但没人能看懂」级别的静默失败。
    """
    for name in _BAT_INSTALLERS:
        raw = _inst(name).read_bytes()
        assert raw.replace(b"\r\n", b"").count(b"\n") == 0, f"{name} 有裸 LF"
        assert b"\r\r\n" not in raw, f"{name} 有 \\r\\r\\n"
        raw.decode("utf-8")                      # 非 UTF-8 可解码 → 抛异常即红
        lines = raw.decode("utf-8").splitlines()
        assert lines[0].strip() == "@echo off", name
        assert "chcp 65001" in lines[1], f"{name} 第 2 行缺活动码页切换"
        body = "\n".join(lines)
        labels = {m.group(1).lower() for m in
                  re.finditer(r"^\s*:([A-Za-z_][\w-]*)", body, re.M)}
        for m in re.finditer(r"\bgoto\s+:?([A-Za-z_][\w-]*)", body, re.I):
            assert m.group(1).lower() in labels, f"{name}: goto :{m.group(1)} 无对应标签"
    assert any(ord(c) > 127 for c in _inst_text("uninstall.bat"))


def test_43g_uninstall_bat_locates_itself_and_proves_artifacts():
    """卸载入口自定位 + 删除前必须确认目录里真有 Matha 产物。

    旧写法恒为 C:\\Program Files\\Matha 硬编且不校验就 rmdir /s——把脚本拷到别处运行
    等于对着一个猜出来的路径执行递归删除。
    """
    text = _inst_text("uninstall.bat")
    assert 'set "SELF_DIR=%~dp0"' in text
    assert '"%SELF_DIR%matha.exe"' in text
    assert "!ARG_DIR!\\matha.exe" in text
    assert "!ARG_DIR!\\src\\matha_main.py" in text
    assert "[中止] 找不到 Matha 安装目录，未删除任何内容。" in text
    for ln in _active_lines("uninstall.bat"):
        assert "rmdir /s /q \"C:\\Program Files\\Matha\"" not in ln, "仍有硬编路径递归删除位"


def test_43g_uninstall_bat_confirms_before_recursive_delete():
    """递归删除不可逆：默认交互确认，/force 才静默。"""
    text = _inst_text("uninstall.bat")
    assert "set /p ANS=" in text
    assert 'if /i not "!ANS!"=="Y"' in text
    assert "已取消卸载，未删除任何内容。" in text
    assert 'if /i "%~1"=="/force" (set "ASSUME_YES=1"' in text
    assert "if not defined ASSUME_YES (" in text
    # 删除后如实报告，而不是无条件宣称「已完全卸载」
    assert "未删净（可能正被占用），请手动删除。" in text


def test_43g_uninstall_bat_hands_off_instead_of_self_deleting():
    """脚本住在待删目录里时走 TEMP 副本交接，且绝不自删自身文件。

    实测三件事：① 就地删所在目录 → rc=1 + 「The system cannot find the path
    specified.」；② 删自身文件 → 「The batch file cannot be found.」；③ 交接行不写
    同行 exit → 父脚本把卸载体再跑一遍（两遍横幅）。含空格路径当命令行入参经 start
    传递会被截断，故目标走环境变量 MATHA_UNINST_TARGET。
    """
    text = _inst_text("uninstall.bat")
    assert 'for %%I in ("!INSTALL_DIR!") do set "TARGET_FULL=%%~fI"' in text
    assert 'for %%I in ("%SELF_DIR%.") do set "SELF_FULL=%%~fI"' in text
    assert 'if /i not "!TARGET_FULL!"=="!SELF_FULL!" goto body' in text
    assert 'set "MATHA_UNINST_TARGET=!TARGET_FULL!"' in text
    assert 'start "" /b "!COPY!" --relocated & exit /b 0' in text
    assert 'if /i "%~1"=="--relocated"' in text
    assert 'set "INSTALL_DIR=%MATHA_UNINST_TARGET%"' in text
    assert 'if not exist "!COPY!" goto body' in text       # 副本失败也要能干活
    for ln in _active_lines("uninstall.bat"):
        assert not re.search(r"del\s+[^\r\n]*\"?%~f0", ln, re.I), f"删自身文件: {ln.strip()}"
        assert not re.search(r"del\s+[^\r\n]*\"?!COPY!\"?\s*$", ln, re.I), \
            f"副本自删（会打断 cmd 读盘）: {ln.strip()}"


def test_43g_install_bat_uninstall_entry_outside_deleted_tree():
    """卸载入口主落点 = %LOCALAPPDATA%\\Matha（安装目录之外），单一真源原样拷贝。

    旧写法开始菜单指向仓库 scripts\\uninstall.bat（仓库一挪就断），并用 echo 逐行
    另拼一套删除规则——两套规则必然漂移（一套有确认、一套没有）。
    """
    text = _inst_text("install.bat")
    assert 'set "UNINST_HOME=%LOCALAPPDATA%\\Matha"' in text
    assert 'set "UNINST=%UNINST_HOME%\\uninstall.bat"' in text
    assert 'set "UNINST=%INSTALL_DIR%\\uninstall.bat"' in text   # 兜底分支仍在
    assert text.index('set "UNINST=%UNINST_HOME%') < text.index("Matha 卸载.lnk")
    assert '"%STARTMENU%\\Matha 卸载.lnk" "%UNINST%"' in text
    assert 'copy /y "%REPO_ROOT%\\scripts\\uninstall.bat" "%UNINST%"' in text
    assert 'if not exist "%UNINST%"' in text                  # 没拷成即失败
    for ln in _active_lines("install.bat"):
        assert not re.match(r"\s*\(?\s*echo\s+.*rmdir", ln, re.I), \
            f"install.bat 又 echo 拼了一套删除规则: {ln.strip()}"
    assert not re.search(r"echo\s+.*rmdir", _inst_text("uninstall.bat"), re.I)


@_WIN
def test_43g_powershell_installers_pass_parser(tmp_path):
    """5 个 .ps1 安装入口必须能被 PowerShell 自己解析。"""
    harness = tmp_path / "g_tok.ps1"
    harness.write_text(
        "$ErrorActionPreference='Stop'\n$bad=0\n"
        "foreach ($p in $args) { $t=Get-Content -Raw -LiteralPath $p; $e=$null\n"
        "  [System.Management.Automation.PSParser]::Tokenize($t,[ref]$e)|Out-Null\n"
        "  if ($e.Count -gt 0) { $bad++; Write-Output ('FAIL '+$p+' L'+\n"
        "    $e[0].Token.StartScriptPositionLineNumber+' '+$e[0].Message) }\n"
        "}\nWrite-Output ('bad='+$bad)\nexit $bad\n", encoding="utf-8")
    rc, out = _run_cmd(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(harness)] + [str(_inst(n)) for n in _PS1_INSTALLERS])
    assert "bad=0" in out and rc == 0, out


@_WIN
def test_43g_embedded_templates_validated_in_destination_language(tmp_path):
    """here-string 模板按**产物类型**验证：外层能解析 ≠ 产物能解析，也不代表该按 PS 解析。

    setup_workspace.ps1 的三块模板写出去是 update.py / README.md / IDE README，拿
    PSParser 判它们只会得到假红；install.ps1 与 setup_matha.ps1 的卸载器模板写出去
    是 .ps1，就必须过 PS 解析——判据跟着产物走。
    """
    asg = re.compile(r"^[ \t]*\$(\w+)\s*=\s*@'\n(.*?)\n'@", re.S | re.M)
    exts = (".ps1", ".py", ".md", ".json")
    harness = tmp_path / "g_emb.ps1"
    harness.write_text(
        "$ErrorActionPreference='Stop'\n$bad=0\n"
        "foreach ($p in $args) { $t=Get-Content -Raw -LiteralPath $p; $e=$null\n"
        "  [System.Management.Automation.PSParser]::Tokenize($t,[ref]$e)|Out-Null\n"
        "  if ($e.Count -gt 0) { $bad++; Write-Output ('FAIL '+$p+' '+$e[0].Message) } }\n"
        "exit $bad\n", encoding="utf-8")
    ps_targets = []
    checked = 0
    for name in _PS1_INSTALLERS:
        text = _inst_text(name)
        for m in asg.finditer(text):
            var, body = m.group(1), m.group(2)
            tail = text[m.end():m.end() + 3000]
            w = (re.search(r"\$" + var + r"\s*\|\s*(Out-File|Set-Content)\b([^\r\n]*)", tail)
                 or re.search(r"(Out-File|Set-Content)\b([^\r\n]*?-Value\s+\$" + var + r")", tail))
            assert w, f"{name} 的 ${var} 找不到写盘目的地——模板产物类型无法判定"
            dest = w.group(2)
            ext = next((e for e in exts if e in dest), None)
            if ext is None:
                pm = re.search(r"\$(\w+)\b", dest)
                hop = (re.search(r"^\s*\$" + pm.group(1) +
                                 r"\s*=\s*[^\r\n]*?\.(ps1|py|md|json)", text, re.M)
                       if pm else None)
                assert hop, f"{name} 的 ${var} 目的地未定扩展名"
                ext = "." + hop.group(1)
            checked += 1
            if ext == ".py":
                ast.parse(body)
            elif ext == ".ps1":
                out = tmp_path / f"emb_{name}_{var}.ps1"
                out.write_text(body, encoding="utf-8-sig")
                ps_targets.append(out)
    assert checked >= 5, f"模板计数异常（{checked}）——here-string 形状变了要同步本锁"
    assert len(ps_targets) == 2, [p.name for p in ps_targets]
    rc, out = _run_cmd(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(harness)] + [str(p) for p in ps_targets])
    assert rc == 0, out


@_WIN
def test_43g_batch_and_powershell_self_deletion_asymmetry(tmp_path):
    """口径锁（真跑）：同一条「删掉自己所在的目录」，batch 断在删除行，PowerShell 跑完。

    实测：PS → rc=7 且删后仍打印尾行；cmd → rc=1、「The system cannot find the path
    specified.」、后续 echo/exit 全不执行。两套载体边界不同，所以 install.bat 要把
    卸载入口放在安装目录之外、uninstall.bat 需要 TEMP 交接，而 .ps1 侧不用搬迁——
    凭静态阅读很容易给两边套同一套规则。
    """
    ps_dir = tmp_path / "ps"
    bat_dir = tmp_path / "bat"
    ps_dir.mkdir()
    bat_dir.mkdir()
    (ps_dir / "self.ps1").write_text(
        "Remove-Item $PSScriptRoot -Recurse -Force\n"
        'Write-Output "PS-AFTER-DELETE"\nexit 7\n', encoding="utf-8")
    (bat_dir / "self.bat").write_bytes(
        b"@echo off\r\n"
        b'for %%I in ("%~dp0.") do set "TD=%%~fI"\r\n'
        b'cd /d "%TEMP%"\r\n'
        b'rmdir /s /q "%TD%"\r\n'
        b"echo BAT-AFTER-DELETE\r\n"
        b"exit /b 7\r\n")
    rc_ps, out_ps = _run_cmd(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", str(ps_dir / "self.ps1")])
    rc_bat, out_bat = _run_cmd([str(bat_dir / "self.bat")])
    assert rc_ps == 7 and "PS-AFTER-DELETE" in out_ps and not ps_dir.exists(), out_ps
    assert not bat_dir.exists(), out_bat
    assert rc_bat != 7 and "BAT-AFTER-DELETE" not in out_bat, out_bat
    assert _noise_lines(out_bat), f"预期 cmd 在删除行之后就读不到盘: {out_bat!r}"


@_WIN
def test_43g_uninstall_bat_flow_aborts_without_artifacts(tmp_path):
    """目录里没有 Matha 产物 → 中止、rc=1、什么都不删。"""
    _skip_if_real_install()
    env = _sandbox_env(tmp_path)
    d = _fake_install(tmp_path / "abort", "lookalike", artifacts=False)
    rc, out = _run_cmd([str(d / "uninstall.bat")], cwd=str(tmp_path), stdin=b"Y\n",
                       extra_env=env)
    assert rc == 1, out
    assert "[中止] 找不到 Matha 安装目录" in out, out
    assert d.exists() and (d / "readme.txt").exists(), out
    assert "Matha 卸载程序" not in out, out


@_WIN
def test_43g_uninstall_bat_flow_cancel_keeps_tree(tmp_path):
    """安装目录内运行 + 输入 N → rc=0、目录完整、只跑一遍（无第二遍横幅）。"""
    _skip_if_real_install()
    env = _sandbox_env(tmp_path)
    d = _fake_install(tmp_path / "cancel", "inst")
    rc, out = _run_cmd([str(d / "uninstall.bat")], cwd=str(tmp_path), stdin=b"N\n",
                       extra_env=env)
    assert rc == 0, out
    assert d.exists() and (d / "matha.exe").exists(), out
    assert "已取消卸载" in out, out
    assert out.count("Matha 卸载程序") == 1, out
    assert not _noise_lines(out), out


@_WIN
def test_43g_uninstall_bat_flow_in_dir_delete_relocates(tmp_path):
    """安装目录内运行 + 输入 Y → 交接给 TEMP 副本，rc=0、目录删净、零噪声。"""
    _skip_if_real_install()
    env = _sandbox_env(tmp_path)
    d = _fake_install(tmp_path / "del", "inst")
    rc, out = _run_cmd([str(d / "uninstall.bat")], cwd=str(tmp_path), stdin=b"Y\n",
                       extra_env=env)
    assert rc == 0, out
    assert out.count("Matha 卸载程序") == 1, out
    assert _wait_gone(d), f"目录未被删除: {out}"
    assert "Matha 已完全卸载" in out, out
    assert not _noise_lines(out), out


@_WIN
def test_43g_uninstall_bat_flow_external_arg_and_force(tmp_path):
    """外部副本：显式目录入参走交互确认；/force 无 stdin 也删（脚本化卸载）。"""
    _skip_if_real_install()
    env = _sandbox_env(tmp_path)
    ext = _fake_install(tmp_path / "ext", "uninstall_host", artifacts=False,
                        with_bat=False)
    (ext / "uninstall.bat").write_bytes(_inst("uninstall.bat").read_bytes())
    spaced = _fake_install(tmp_path / "target with space", "inst")   # 空格路径入参
    rc, out = _run_cmd([str(ext / "uninstall.bat"), str(spaced)], cwd=str(tmp_path),
                       stdin=b"Y\n", extra_env=env)
    assert rc == 0 and out.count("Matha 卸载程序") == 1, out
    assert _wait_gone(spaced), out
    forced = _fake_install(tmp_path / "forced", "inst")
    rc, out = _run_cmd([str(ext / "uninstall.bat"), "/force", str(forced)],
                       cwd=str(tmp_path), stdin=b"", extra_env=env)
    assert rc == 0, out
    assert _wait_gone(forced), out
    assert not _noise_lines(out), out


@_WIN
def test_43g_uninstall_bat_flow_relocated_copy_carries_spaced_target(tmp_path):
    """交接路径的含空格目标走环境变量：实测命令行入参经 start 会被截断成 "…\\p43"。"""
    _skip_if_real_install()
    env = _sandbox_env(tmp_path)
    d = _fake_install(tmp_path / "spaced handoff", "my matha")
    rc, out = _run_cmd([str(d / "uninstall.bat")], cwd=str(tmp_path), stdin=b"Y\n",
                       extra_env=env)
    assert rc == 0, out
    assert _wait_gone(d), out
    assert not _noise_lines(out), out


def test_43g_release_notes_title_takes_single_version_source():
    """发布说明标题的版号来自 src/__version__.py，不来自 pyproject 的 dynamic 表。

    旧写法回退读 `project.version`，而该字段是 dynamic 的 `{attr = "…"}` 表——取到的
    是 dict 而不是字符串，标题渲染成 `v{'attr': …}`。判据落到真跑：脚本 stdout 首行。
    """
    from src.__version__ import __version__ as real_version
    text = _read_py("scripts/generate_release_notes.py")
    # 剥 docstring：里面记的正是「既往怎么错的」（回退读 pyproject 的 dynamic 表）
    body = _strip_docstrings(text[text.index("def get_version")
                                  :text.index("def get_commits_since_last_tag")])
    assert "__version__.py" in body, "发布说明未取唯一版本源"
    assert "pyproject" not in body, "get_version 仍从 pyproject 取版号（dynamic 表拿到 dict）"
    r = subprocess.run([sys.executable, "scripts/generate_release_notes.py"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       cwd=str(_ROOT), timeout=180)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, out[-400:]
    assert f"# Matha v{real_version} 发布说明" in out, out.splitlines()[0]
    assert "{'attr'" not in out, out.splitlines()[0]
