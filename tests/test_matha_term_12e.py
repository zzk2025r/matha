# -*- coding: utf-8 -*-
"""阶段 12e：终端扩展命令注册 + 启动自动加载 + 升级命令入门禁。

三锁纪律：
  ① 对拍：注册/调用/注销/升级 同一命令行，宿主执行器 = M3V VM 执行器（结果帧逐值一致）。
  ② 闭环：写处理器→注册→调用→重注册→注销 全链落盘状态逐步断言；注册表跨实例/跨后端共享。
  ③ 拒绝：内建冲突名/含空格名/缺处理器/注入参数（引号·反斜杠）/坏注册表行/缺 处理 导出/
     未注册注销/升级 解释器 显式拒绝/参数个数 双端同文本显式拒绝。

诚实边界（本片登记，不粉饰）：
  - 升级 = pkg_manager_v2 真本地检查（.matha_packages/*/manifest.json 还原已安装集合，
    无网络），只检查不下载不安装（真安装另立片）。
  - 扩展参数安全嵌入限制：含引号/反斜杠/换行显式拒绝（防拼接改写为任意代码）。
  - 启动自动加载仅 REPL；自启动中的 退出 不结束会话。

零跳过，零失败。
"""
import os
import subprocess
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

# 词法器为字符级扫描递归 → 抬高栈上限（与 12a 同口径）
sys.setrecursionlimit(max(30000, sys.getrecursionlimit()))

_FILES = ["matha/stdlib.matha", "matha/term_lexer.matha", "matha/term_parser.matha",
          "matha/term_engine.matha"]

PY = sys.executable

_HANDLER = ('module 你好扩展 {\n'
            '  func 处理(参数们: List) -> List =\n'
            '    输出("你好, " + 参数们[0] + "!")\n'
            '}\n')

_HANDLER2 = ('module 你好扩展 {\n'
             '  func 处理(参数们: List) -> List =\n'
             '    输出("改版, " + 参数们[0] + "?")\n'
             '}\n')


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


def _host_call(interp, fn, *args):
    return interp._call_func_or_closure(interp.funcs[fn], list(args))


def _host_line(interp, text):
    frame = _host_call(interp, "终端解析", text)
    return _host_call(interp, "终端执行", frame, text)


def _vm_line(vm, text):
    frame = vm.call("终端解析", text)
    return vm.call("终端执行", frame, text)


def _run(args, cwd, stdin=None):
    return subprocess.run(
        [PY, "-m"] + args,
        input=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)},
        cwd=str(cwd),
    )


# ---------- ① 对拍：注册/调用/注销/升级 vm=host ----------

def test_parity_register_invoke_unregister(tmp_path, monkeypatch, host_term, vm_term):
    d = tmp_path / "A"
    d.mkdir()
    (d / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    monkeypatch.chdir(d)
    h_reg = _host_line(host_term, "注册命令 你好 hello_ext.matha")
    v_reg = _vm_line(vm_term, "注册命令 你好 hello_ext.matha")
    assert h_reg == v_reg == {"输出": ["已注册扩展命令 你好 → hello_ext.matha"], "退出": False}
    assert (d / "matha_term_registry.txt").read_text(encoding="utf-8") == "你好 hello_ext.matha"
    h_call = _host_line(host_term, "你好 世界")
    v_call = _vm_line(vm_term, "你好 世界")
    assert h_call == v_call == {"输出": ["你好, 世界!"], "退出": False}
    h_un = _host_line(host_term, "注销命令 你好")
    assert h_un == {"输出": ["已注销扩展命令 你好"], "退出": False}
    assert (d / "matha_term_registry.txt").read_text(encoding="utf-8") == ""
    # 注册表 = 共享磁盘事实：宿主的注销对 VM 同样生效 → VM 再注销显式拒绝（非静默）
    with pytest.raises(RuntimeError, match="注销命令: 未注册"):
        _vm_line(vm_term, "注销命令 你好")


def test_parity_reregister_reflects_new_handler(tmp_path, monkeypatch, host_term, vm_term):
    d = tmp_path / "B"
    d.mkdir()
    (d / "v1.matha").write_text(_HANDLER, encoding="utf-8")
    (d / "v2.matha").write_text(_HANDLER2, encoding="utf-8")
    monkeypatch.chdir(d)
    _host_line(host_term, "注册命令 你好 v1.matha")
    _host_line(host_term, "注册命令 你好 v2.matha")  # 重注册 = 更新路径，不产生重复行
    assert (d / "matha_term_registry.txt").read_text(encoding="utf-8") == "你好 v2.matha"
    h = _host_line(host_term, "你好 世界")
    v = _vm_line(vm_term, "你好 世界")
    assert h == v == {"输出": ["改版, 世界?"], "退出": False}


def test_parity_unregister_falls_back_to_passthrough(tmp_path, monkeypatch, host_term, vm_term):
    d = tmp_path / "C"
    d.mkdir()
    (d / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    monkeypatch.chdir(d)
    _host_line(host_term, "注册命令 你好 hello_ext.matha")
    _host_line(host_term, "注销命令 你好")
    for line_fn in (_host_line, _vm_line):
        r = line_fn(host_term if line_fn is _host_line else vm_term, "你好 落透传")
        assert r["退出"] is False
        assert r["输出"], "透传应有系统输出"
        assert any(ln.startswith("命令退出码") for ln in r["输出"])


def test_parity_upgrade_no_updates(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "升级")
    v = _vm_line(vm_term, "升级")
    assert h == v == {"输出": ["无可用更新（本地检查，不下载不安装）"], "退出": False}


@pytest.mark.parametrize("name", ["解释器", "matha", "interpreter"])
def test_parity_upgrade_rejects_interpreter_self(tmp_path, monkeypatch, host_term, vm_term, name):
    monkeypatch.chdir(tmp_path)
    frag = "显式拒绝"
    with pytest.raises(RuntimeError, match=frag):
        _host_line(host_term, f"升级 {name}")
    with pytest.raises(RuntimeError, match=frag):
        _vm_line(vm_term, f"升级 {name}")


def test_parity_upgrade_no_such_package(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "升级 不存在的包")
    v = _vm_line(vm_term, "升级 不存在的包")
    assert h == v == {"输出": ["无该包可用更新: 不存在的包（本地检查，不下载不安装）"], "退出": False}


def test_parity_upgrade_with_real_manifest(tmp_path, monkeypatch, host_term, vm_term):
    """真本地检查：.matha_packages/intent/manifest.json 0.0.1 < 本地 registry 0.1.0 → 真更新。"""
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / ".matha_packages" / "intent"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        '{"name": "intent", "version": "0.0.1", "dependencies": [], "installed_at": 0}',
        encoding="utf-8")
    h = _host_line(host_term, "升级")
    v = _vm_line(vm_term, "升级")
    assert h == v == {"输出": ["可用更新（本地检查，不下载不安装）",
                              "intent: 0.0.1 -> 0.1.0 (minor/patch)"], "退出": False}
    h2 = _host_line(host_term, "升级 INTENT")
    v2 = _vm_line(vm_term, "升级 INTENT")
    assert h2 == v2 == {"输出": ["intent: 0.0.1 -> 0.1.0 (minor/patch)"], "退出": False}


def test_parity_help_lists_12e_commands(host_term, vm_term):
    h = _host_line(host_term, "帮助")["输出"]
    v = _vm_line(vm_term, "帮助")["输出"]
    assert h == v
    for frag in ("注册命令", "注销命令", "升级 [包名]", "扩展命令", "启动自动加载"):
        assert any(frag in ln for ln in h), f"帮助缺 {frag}"


# ---------- ② 闭环：注册表跨实例 / 跨后端共享 ----------

def test_loop_full_cycle_state_steps(tmp_path, monkeypatch, host_term):
    """写处理器→注册→调用→注销→再调用回落透传，注册表文件逐步断言。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    reg = tmp_path / "matha_term_registry.txt"
    assert not reg.exists()
    _host_line(host_term, "注册命令 你好 hello_ext.matha")
    assert reg.read_text(encoding="utf-8") == "你好 hello_ext.matha"
    assert _host_line(host_term, "你好 A")["输出"] == ["你好, A!"]
    _host_line(host_term, "注销命令 你好")
    assert reg.read_text(encoding="utf-8") == ""


def test_loop_registry_persists_across_instances(tmp_path, monkeypatch):
    """注册表为磁盘事实：第一个解释器注册，第二个全新解释器直接可调用。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    first = Interpreter()
    assert first.load_matha_module("终端执行器")
    _host_line(first, "注册命令 你好 hello_ext.matha")
    second = Interpreter()
    assert second.load_matha_module("终端执行器")
    assert _host_line(second, "你好 后继")["输出"] == ["你好, 后继!"]


def test_loop_host_registry_readable_by_vm(tmp_path, monkeypatch, vm_term):
    """宿主写入注册表，VM 执行器读同一文件并调用扩展（注册表 = 共享磁盘事实）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    host = Interpreter()
    assert host.load_matha_module("终端执行器")
    _host_line(host, "注册命令 你好 hello_ext.matha")
    assert _vm_line(vm_term, "你好 跨后端")["输出"] == ["你好, 跨后端!"]


# ---------- ③ 拒绝：冲突名/格式/缺文件/注入/坏注册表/缺导出/参数个数 ----------

def test_reject_builtin_conflict(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    for name in ("目录", "dir", "帮助", "升级"):
        with pytest.raises(RuntimeError, match="与内建命令冲突"):
            _host_line(host_term, f"注册命令 {name} hello_ext.matha")
        with pytest.raises(RuntimeError, match="与内建命令冲突"):
            _vm_line(vm_term, f"注册命令 {name} hello_ext.matha")


@pytest.mark.parametrize("line,frag", [
    ("注册命令 \"你 好\" hello_ext.matha", "名字不能含空格"),
    ("注册命令 只有名字", "注册命令: 需要 2 个参数"),
    ("注册命令 名 字 路径", "注册命令: 需要 2 个参数"),
    ("注册命令 缺失 no_such_file.matha", "处理器文件不存在"),
    ("注销命令", "注销命令: 需要 1 个参数"),
    ("注销命令 a b", "注销命令: 需要 1 个参数"),
    ("注销命令 从未注册", "注销命令: 未注册"),
    ("升级 a b", "升级: 至多 1 个参数"),
])
def test_reject_matrix_host(host_term, tmp_path, monkeypatch, line, frag):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    with pytest.raises(RuntimeError, match=frag):
        _host_line(host_term, line)


@pytest.mark.parametrize("line,frag", [
    ("注册命令 \"你 好\" hello_ext.matha", "名字不能含空格"),
    ("注册命令 只有名字", "注册命令: 需要 2 个参数"),
    ("注册命令 名 字 路径", "注册命令: 需要 2 个参数"),
    ("注册命令 缺失 no_such_file.matha", "处理器文件不存在"),
    ("注销命令", "注销命令: 需要 1 个参数"),
    ("注销命令 a b", "注销命令: 需要 1 个参数"),
    ("注销命令 从未注册", "注销命令: 未注册"),
    ("升级 a b", "升级: 至多 1 个参数"),
])
def test_reject_matrix_vm(vm_term, tmp_path, monkeypatch, line, frag):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    with pytest.raises(RuntimeError, match=frag):
        _vm_line(vm_term, line)


def test_reject_unsafe_extension_arg(tmp_path, monkeypatch, host_term, vm_term):
    """参数含反斜杠 → 安全嵌入限制显式拒绝（防拼接改写为任意代码）。

    含引号参数在 12a 终端词法层即被拒（引号未闭合/引号合并剥除，引号字符
    不可能进入参数），故引擎的引号防线经 _安全参 直锁（绕过词法构造参数）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello_ext.matha").write_text(_HANDLER, encoding="utf-8")
    _host_line(host_term, "注册命令 你好 hello_ext.matha")
    with pytest.raises(RuntimeError, match="安全嵌入限制"):
        _host_line(host_term, "你好 注\\入")
    with pytest.raises(RuntimeError, match="安全嵌入限制"):
        _vm_line(vm_term, "你好 注\\入")
    assert _host_call(host_term, "_安全参", ['引"号', "反\\斜杠", "含\n换行"], 0) is False
    assert _host_call(host_term, "_安全参", ["干净参数"], 0) is True
    assert vm_term.call("_安全参", ['引"号', "反\\斜杠", "含\n换行"], 0) is False
    assert vm_term.call("_安全参", ["干净参数"], 0) is True


def test_reject_bad_registry_line(tmp_path, monkeypatch, host_term, vm_term):
    """手改注册表坏行 → 任何未知命令派发时显式拒绝（不静默跳过用户数据）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "matha_term_registry.txt").write_text("只有一列\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="终端注册表存在坏行"):
        _host_line(host_term, "完全未知的命令")
    with pytest.raises(RuntimeError, match="终端注册表存在坏行"):
        _vm_line(vm_term, "完全未知的命令")


def test_reject_handler_without_processing(tmp_path, monkeypatch, host_term, vm_term):
    """处理器未导出 处理 → 调用时 执行Matha 如实上抛（注册只校验路径存在）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "空处理器.matha").write_text(
        'module 空处理器 {\n  func 别的() -> Int = 1\n}\n', encoding="utf-8")
    _host_line(host_term, "注册命令 空跑 空处理器.matha")
    with pytest.raises(RuntimeError, match="执行Matha 错误"):
        _host_line(host_term, "空跑 参数")
    with pytest.raises(RuntimeError, match="执行Matha 错误"):
        _vm_line(vm_term, "空跑 参数")


def test_reject_bad_glue_manifest_raises(tmp_path, monkeypatch):
    """胶水层：manifest 缺 version 如实上抛（不静默跳过损坏数据）。"""
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / ".matha_packages" / "坏包"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text('{"name": "坏包"}', encoding="utf-8")
    from src.domains.os_module import check_package_updates
    with pytest.raises(RuntimeError, match="manifest 缺 name/version"):
        check_package_updates()


# ---------- ④ 端到端：启动自动加载（仅 REPL；退出 标志不结束会话） ----------

_AUTORUN = ("# 自启动：注册扩展命令\n"
            "注册命令 你好 hello.matha\n")


def _write_ext_setup(d: Path, extra_lines=()):
    (d / "hello.matha").write_text(_HANDLER, encoding="utf-8")
    (d / "matha_term_extensions.msh").write_text(
        _AUTORUN + "".join(ln + "\n" for ln in extra_lines), encoding="utf-8")


def test_e2e_autorun_registers_and_invokes(tmp_path):
    _write_ext_setup(tmp_path)
    r = _run(["src.matha_term"], cwd=tmp_path, stdin="你好 终端\n退出\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "已注册扩展命令 你好" in r.stdout
    assert "你好, 终端!" in r.stdout
    assert "不应到达" not in r.stdout


def test_e2e_autorun_error_continues(tmp_path):
    _write_ext_setup(tmp_path, extra_lines=("换目录", "回显 自启动继续"))
    r = _run(["src.matha_term"], cwd=tmp_path, stdin="退出\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "自启动(第 3 行) 错误" in r.stdout  # 行号含首行 # 注释
    assert "自启动继续" in r.stdout


def test_e2e_autorun_exit_flag_ignored(tmp_path):
    _write_ext_setup(tmp_path, extra_lines=("退出",))
    r = _run(["src.matha_term"], cwd=tmp_path, stdin="回显 会话仍在\n退出\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "已注册扩展命令 你好" in r.stdout
    assert "会话仍在" in r.stdout


def test_e2e_autorun_absent_is_silent(tmp_path):
    (tmp_path / "hello.matha").write_text(_HANDLER, encoding="utf-8")
    r = _run(["src.matha_term"], cwd=tmp_path, stdin="退出\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "自启动" not in r.stdout
    assert "已注册扩展命令" not in r.stdout


def test_e2e_c_mode_skips_autorun(tmp_path):
    _write_ext_setup(tmp_path, extra_lines=("回显 自启动不该跑",))
    r = _run(["src.matha_term", "-c", "回显 直接命令"], cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "直接命令" in r.stdout
    assert "自启动不该跑" not in r.stdout
    assert "已注册扩展命令" not in r.stdout
