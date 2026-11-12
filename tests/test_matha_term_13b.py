# -*- coding: utf-8 -*-
"""阶段 13b：终端重定向真执行入门禁（> 截断 / >> 追加 + 管道组合）。

三锁纪律：
  ① 对拍：同一重定向命令行，宿主执行器 = M3V VM 执行器（结果帧逐值一致 +
     落盘文件内容逐字节一致）——新建/截断/追加/管道组合/空输出/透传段边界。
  ② 闭环：文件状态机（> 新建 → >> 累加 → > 截断回位）走真磁盘；退出标志
     跳过落盘；段内错误不落盘且既有文件原样保留。
  ③ 拒绝：重定向缺目标 / 重定向符重复 / 重定向不在末尾（12a 句法层）；
     落盘目标为目录时 write_file 如实上抛（不伪装成功）。

诚实边界（登记，与 CMD 差异）：重定向接管末段**显示行**——透传段的 stderr/
命令退出码行同样落盘（同管道载荷口径）；CMD 式静默：落盘不回显；每行以 \n
结尾，空输出写空文件。零跳过，零失败。
"""
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


def _file(tmp_path, name):
    return (tmp_path / name).read_text(encoding="utf-8")


# ---------- ① 对拍：宿主 = VM（含落盘内容逐字节一致） ----------

@pytest.mark.parametrize("hname,vname", [("h1.txt", "v1.txt")])
def test_parity_redirect_truncate_new(tmp_path, monkeypatch, host_term, vm_term, hname, vname):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, f"回显 你好 重定向 > {hname}")
    v = _vm_line(vm_term, f"回显 你好 重定向 > {vname}")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, hname) == _file(tmp_path, vname) == "你好 重定向\n"


def test_parity_redirect_truncate_overwrites(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "o.txt").write_text("旧内容\n很长的旧内容\n", encoding="utf-8")
    h = _host_line(host_term, "回显 新 > o.txt")
    v = _vm_line(vm_term, "回显 新 > o.txt")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, "o.txt") == "新\n"


def test_parity_redirect_append_creates(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 首行 >> h新.txt")
    v = _vm_line(vm_term, "回显 首行 >> v新.txt")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, "h新.txt") == _file(tmp_path, "v新.txt") == "首行\n"


def test_parity_redirect_append_accumulates(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hlog.txt").write_text("已有\n", encoding="utf-8")
    (tmp_path / "vlog.txt").write_text("已有\n", encoding="utf-8")
    h = _host_line(host_term, "回显 第二行 >> hlog.txt")
    v = _vm_line(vm_term, "回显 第二行 >> vlog.txt")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, "hlog.txt") == _file(tmp_path, "vlog.txt") == "已有\n第二行\n"


def test_parity_redirect_pipe_compose(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 苹果 梨 | 查找 果 > h命中.txt")
    v = _vm_line(vm_term, "回显 苹果 梨 | 查找 果 > v命中.txt")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, "h命中.txt") == _file(tmp_path, "v命中.txt") == "苹果 梨\n"


def test_parity_redirect_empty_output_writes_empty(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 xy | 查找 z > h空.txt")
    v = _vm_line(vm_term, "回显 xy | 查找 z > v空.txt")
    assert h == v == {"输出": [], "退出": False}
    assert _file(tmp_path, "h空.txt") == _file(tmp_path, "v空.txt") == ""


def test_parity_redirect_passthrough_segment_boundary(tmp_path, monkeypatch, host_term, vm_term):
    """边界锁（与 CMD 差异，登记）：透传段的 stderr/退出码行同样落盘（显示行口径）。"""
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 hi | 大写 > h透.txt")
    v = _vm_line(vm_term, "回显 hi | 大写 > v透.txt")
    assert h == v == {"输出": [], "退出": False}
    hc = _file(tmp_path, "h透.txt")
    assert _file(tmp_path, "v透.txt") == hc
    assert "命令退出码: 1" in hc and "大写" in hc


# ---------- ② 闭环：文件状态机 / 退出跳过 / 错误不落盘 ----------

def test_loop_redirect_state_machine(tmp_path, monkeypatch, host_term):
    monkeypatch.chdir(tmp_path)
    assert _host_line(host_term, "回显 甲 > st.txt") == {"输出": [], "退出": False}
    assert _file(tmp_path, "st.txt") == "甲\n"
    assert _host_line(host_term, "回显 乙 >> st.txt") == {"输出": [], "退出": False}
    assert _file(tmp_path, "st.txt") == "甲\n乙\n"
    assert _host_line(host_term, "回显 丙 >> st.txt") == {"输出": [], "退出": False}
    assert _file(tmp_path, "st.txt") == "甲\n乙\n丙\n"
    assert _host_line(host_term, "回显 重置 > st.txt") == {"输出": [], "退出": False}
    assert _file(tmp_path, "st.txt") == "重置\n"


def test_loop_exit_flag_skips_redirect(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 a | 退出 > h跳.txt")
    v = _vm_line(vm_term, "回显 a | 退出 > v跳.txt")
    assert h == v == {"输出": [], "退出": True}
    assert not (tmp_path / "h跳.txt").exists()
    assert not (tmp_path / "v跳.txt").exists()


def test_loop_segment_error_no_write_preserves(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "保.txt").write_text("原样\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="目录: 至多"):
        _host_line(host_term, "目录 a b > 保.txt")
    assert _file(tmp_path, "保.txt") == "原样\n"
    with pytest.raises(RuntimeError, match="目录: 至多"):
        _vm_line(vm_term, "目录 a b > 保.txt")
    assert _file(tmp_path, "保.txt") == "原样\n"


# ---------- ③ 拒绝：句法层（12a 已锁）+ 落盘失败如实上抛 ----------

@pytest.mark.parametrize("line,frag", [
    ("回显 hi >", "重定向缺少目标文件"),
    ("回显 hi > a > b", "重定向符重复"),
    ("回显 hi > a | 查找 x", "重定向必须位于命令行末尾"),
])
def test_reject_parse_shape(host_term, vm_term, line, frag):
    with pytest.raises(RuntimeError, match=frag):
        _host_line(host_term, line)
    with pytest.raises(RuntimeError, match=frag):
        _vm_line(vm_term, line)


def test_reject_write_target_is_directory(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "是个目录").mkdir()
    with pytest.raises(RuntimeError, match="write_file 失败"):
        _host_line(host_term, "回显 x > 是个目录")
    with pytest.raises(RuntimeError, match="write_file 失败"):
        _vm_line(vm_term, "回显 x > 是个目录")


def test_help_lists_redirect_real(host_term, vm_term):
    h = _host_line(host_term, "帮助")["输出"]
    v = _vm_line(vm_term, "帮助")["输出"]
    assert h == v
    assert any("重定向" in ln and "13b 真化" in ln for ln in h)
    assert not any("显式拒绝（真实现属阶段 13b）" in ln for ln in h)
