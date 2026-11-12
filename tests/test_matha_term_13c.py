# -*- coding: utf-8 -*-
"""阶段 13c：升级带名真安装入门禁（os 域 升级包 真盘重写 + 引擎带名接线）。

三锁纪律：
  ① 对拍：升级包 胶水合同（返回 [包名, 旧版本, 新版本] + 盘上 manifest 重写复核）
     ——宿主引擎与 M3V VM 引擎带名升级同一合同逐值一致（独立目录，盘上 manifest
     为共享事实，跨端共享后续验证）。
  ② 闭环：单目录全链 检查→带名安装→盘上 0.1.0→再检查无更新；宿主装毕后 VM
     同目录见「无该包」（盘面共享事实，不静默重装）；胶水直调返回三元组。
  ③ 拒绝：未安装/已最新 带名升级如实拒绝（升级 ≠ 全新安装，本地目录不下载）；
     manifest 损坏/缺字段如实上抛不静默跳过；升级 解释器 显式拒绝（12e 锁保持）。

诚实边界（登记）：真安装 = 本地目录升级（pkg_manager_v2.upgrade_package 重写
.matha_packages/<包>/manifest.json），不联网下载（RemotePackageClient 目标为
虚构端点）；无参升级保持 12e 只检查口径。零跳过，零失败。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.interp import Interpreter
from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]

sys.setrecursionlimit(max(30000, sys.getrecursionlimit()))

_FILES = ["matha/stdlib.matha", "matha/term_lexer.matha", "matha/term_parser.matha",
          "matha/term_engine.matha"]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_term():
    interp = Interpreter()
    assert interp.load_matha_module("终端执行器"), "加载 终端执行器 失败"
    return interp


@pytest.fixture(scope="module")
def vm_term():
    comp = Compiler()
    decls = []
    for rel in _FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    from src.plugin_api import get_resolver
    vm.domain_resolver = get_resolver()
    vm.run()
    return vm


def _host_line(interp, line):
    frame = interp._call_func_or_closure(interp.funcs["终端解析"], [line])
    return interp._call_func_or_closure(interp.funcs["终端执行"], [frame, line])


def _vm_line(vm, line):
    frame = vm.call("终端解析", line)
    return vm.call("终端执行", frame, line)


def _seed_pkg(d, version="0.0.1", name="intent"):
    pkg = d / ".matha_packages" / name
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"name": name, "version": version,
                    "dependencies": [], "installed_at": 0}, ensure_ascii=False),
        encoding="utf-8")
    return pkg


def _disk_version(pkg):
    return json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))["version"]


# ---------- ① 对拍：胶水合同 + 双端引擎带名升级同一合同 ----------

def test_parity_glue_upgrade_contract(tmp_path, monkeypatch):
    """胶水层：升级包 真盘安装 + 返回 [包名, 旧版本, 新版本]。"""
    from src.domains.os_module import upgrade_package_named
    monkeypatch.chdir(tmp_path)
    pkg = _seed_pkg(tmp_path)
    r = upgrade_package_named("intent")
    assert r == ["intent", "0.0.1", "0.1.0"]
    assert _disk_version(pkg) == "0.1.0"


def test_parity_engine_named_upgrade_same_contract(tmp_path, monkeypatch, host_term, vm_term):
    """双端引擎带名升级同一合同（独立目录逐端跑，盘上复核一致）。"""
    hdir = tmp_path / "H"
    hdir.mkdir()
    pkg_h = _seed_pkg(hdir)
    monkeypatch.chdir(hdir)
    h = _host_line(host_term, "升级 intent")
    assert h == {"输出": ["intent: 0.0.1 -> 0.1.0 (已真安装)"], "退出": False}
    assert _disk_version(pkg_h) == "0.1.0"

    vdir = tmp_path / "V"
    vdir.mkdir()
    pkg_v = _seed_pkg(vdir)
    monkeypatch.chdir(vdir)
    v = _vm_line(vm_term, "升级 intent")
    assert v == h, "双端带名升级同一合同逐值一致"
    assert _disk_version(pkg_v) == "0.1.0"


# ---------- ② 闭环：单目录全链 + 盘面共享事实 ----------

def test_loop_full_cycle_and_shared_disk(tmp_path, monkeypatch, host_term, vm_term):
    """宿主全链：检查→带名安装→再检查无更新；VM 同目录见共享盘面事实
    （已最新 → 无该包消息，不静默重装）；胶水直调对已最新如实拒绝。"""
    from src.domains.os_module import upgrade_package_named
    monkeypatch.chdir(tmp_path)
    pkg = _seed_pkg(tmp_path)

    assert _host_line(host_term, "升级") == {
        "输出": ["可用更新（本地检查，不下载不安装）",
                 "intent: 0.0.1 -> 0.1.0 (minor/patch)"], "退出": False}
    assert _host_line(host_term, "升级 intent") == {
        "输出": ["intent: 0.0.1 -> 0.1.0 (已真安装)"], "退出": False}
    assert _disk_version(pkg) == "0.1.0"
    assert _host_line(host_term, "升级") == {
        "输出": ["无可用更新（本地检查，不下载不安装）"], "退出": False}

    v_after = _vm_line(vm_term, "升级 intent")
    assert v_after == {"输出": ["无该包可用更新: intent（本地检查，不下载不安装）"],
                       "退出": False}
    assert _disk_version(pkg) == "0.1.0"
    with pytest.raises(RuntimeError, match="无可用更新"):
        upgrade_package_named("intent")


# ---------- ③ 拒绝：未安装/损坏 manifest/解释器自升级 ----------

def test_reject_glue_upgrade_unknown_package(tmp_path, monkeypatch):
    from src.domains.os_module import upgrade_package_named
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="无可用更新: 不存在的包"):
        upgrade_package_named("不存在的包")


def test_reject_glue_upgrade_not_installed_but_known(tmp_path, monkeypatch):
    """包名在本地 registry（src 模块扫描）但未安装：升级 ≠ 全新安装，如实拒绝。"""
    from src.domains.os_module import upgrade_package_named
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="无可用更新: intent"):
        upgrade_package_named("intent")


def test_reject_glue_corrupt_manifest(tmp_path, monkeypatch):
    """manifest 缺 version 如实上抛（与 检查包更新 同策略，不静默跳过损坏数据）。"""
    from src.domains.os_module import upgrade_package_named
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / ".matha_packages" / "坏包"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text('{"name": "坏包"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest 缺 name/version"):
        upgrade_package_named("intent")


def test_reject_engine_named_still_blocks_interpreter(tmp_path, monkeypatch, host_term, vm_term):
    """升级 解释器 显式拒绝（自举核心不可终端自升级）——13c 不放宽。"""
    monkeypatch.chdir(tmp_path)
    for line in ("升级 解释器", "升级 matha", "升级 interpreter"):
        with pytest.raises(RuntimeError, match="显式拒绝"):
            _host_line(host_term, line)
        with pytest.raises(RuntimeError, match="显式拒绝"):
            _vm_line(vm_term, line)


def test_help_lists_real_install(host_term, vm_term):
    h = _host_line(host_term, "帮助")["输出"]
    v = _vm_line(vm_term, "帮助")["输出"]
    assert h == v
    assert any("升级 [包名]" in ln and "真安装" in ln for ln in h)


# ---------- ④ 端到端：真 subprocess（独立终端入口）真盘安装 ----------

def test_e2e_subprocess_upgrade_real_install(tmp_path):
    import os
    import subprocess
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)}
    pkg = _seed_pkg(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "src.matha_term", "-c", "升级 intent"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=300, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "intent: 0.0.1 -> 0.1.0 (已真安装)" in r.stdout
    assert _disk_version(pkg) == "0.1.0"
