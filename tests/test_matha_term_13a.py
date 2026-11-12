# -*- coding: utf-8 -*-
"""阶段 13a：终端管道真执行入门禁（CMD 式 stdin 注入 + 查找/排序 消费者）。

三锁纪律：
  ① 对拍：同一管道命令行，宿主执行器 = M3V VM 执行器（结果帧逐值一致）——
     引擎消费者 查找/排序、透传段 执行命令输入、Matha 代码段 输入行 消费、
     退出中断链。
  ② 闭环：胶水 管道输入/输入行/管道结束 状态机（耗尽即 EOF 不回落交互
     stdin）；终端执行 入口清陈旧态；段内出错管道态泄漏 → 下一入口清除兜底；
     扩展处理器经注册表消费管道行（盘面共享事实）。
  ③ 拒绝：查找/排序 参数个数；管道输入 非 List 拒绝。重定向 > >> 已于
     阶段 13b 真化（此处仅留最小落盘对拍，详锁见 test_matha_term_13b.py）。

诚实边界（登记）：管道载荷 = 左段显示行（透传段含 stderr/退出码行，与 CMD
仅 stdout 有差异）；管道段透传按段帧重建命令行（12a 词法已剥引号）；管道行
中的空行与 EOF 不可区分。零跳过，零失败。
"""
import os
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

_MULTI_HANDLER = ('module 多行处理器 {\n'
                  '  func 处理(参数们: List) -> List =\n'
                  '    let u = 输出("pear") in 输出("apple")\n'
                  '}\n')

_PIPE_HANDLER = ('module 管道处理器 {\n'
                 '  func 处理(参数们: List) -> List =\n'
                 '    输出(输入行() + " 收到")\n'
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


def _host_line(interp, line):
    frame = _host_call(interp, "终端解析", line)
    return _host_call(interp, "终端执行", frame, line)


def _vm_line(vm, line):
    frame = vm.call("终端解析", line)
    return vm.call("终端执行", frame, line)


# ---------- ① 对拍：宿主 = VM ----------

@pytest.mark.parametrize("line,expect", [
    ("回显 hi | 查找 h", ["hi"]),
    ("回显 abc | 查找 z", []),
    ("回显 hello world | 查找 wor", ["hello world"]),
    ("回显 hi | 查找 h | 排序", ["hi"]),
])
def test_parity_pipe_find_sort(host_term, vm_term, line, expect):
    h = _host_line(host_term, line)
    v = _vm_line(vm_term, line)
    assert h == v == {"输出": expect, "退出": False}


def test_parity_pipe_exit_stops_chain(host_term, vm_term):
    h = _host_line(host_term, "回显 a | 退出 | 回显 b")
    v = _vm_line(vm_term, "回显 a | 退出 | 回显 b")
    assert h == v == {"输出": [], "退出": True}


def test_parity_pipe_to_matha_run(host_term, vm_term):
    line = '回显 hello | 运行 "let 行 = 输入行() in 输出(行)"'
    h = _host_line(host_term, line)
    v = _vm_line(vm_term, line)
    assert h == v == {"输出": ["hello"], "退出": False}


def test_parity_pipe_to_passthrough(host_term, vm_term):
    line = '回显 5 | python -c "print(int(input())*2)"'
    h = _host_line(host_term, line)
    v = _vm_line(vm_term, line)
    assert h == v and h["输出"] == ["10"] and h["退出"] is False


def test_parity_pipe_to_unknown_passthrough(host_term, vm_term):
    """管道右段未知命令 → 透传真执行，失败显示退出码（stdin 已注入）。"""
    h = _host_line(host_term, "回显 hi | 大写")
    v = _vm_line(vm_term, "回显 hi | 大写")
    assert h == v
    assert h["退出"] is False
    assert h["输出"], "透传段输出不应为空"
    assert h["输出"][-1].startswith("命令退出码: ")


def test_parity_find_sort_arity_reject(host_term, vm_term):
    for line, frag in [("查找", "查找: 需要"), ("查找 a b", "查找: 需要"),
                       ("排序 x", "排序: 不需要")]:
        with pytest.raises(RuntimeError, match=frag):
            _host_line(host_term, line)
        with pytest.raises(RuntimeError, match=frag):
            _vm_line(vm_term, line)


def test_parity_redirect_real_minimal(tmp_path, monkeypatch, host_term, vm_term):
    """13b 真化后的最小落盘对拍（详锁见 test_matha_term_13b.py）。"""
    monkeypatch.chdir(tmp_path)
    h = _host_line(host_term, "回显 hi > h1.txt")
    v = _vm_line(vm_term, "回显 hi > v1.txt")
    assert h == v == {"输出": [], "退出": False}
    assert (tmp_path / "h1.txt").read_text(encoding="utf-8") == "hi\n"
    assert (tmp_path / "v1.txt").read_text(encoding="utf-8") == "hi\n"


def test_parity_help_lists_pipe_commands(host_term, vm_term):
    h = _host_line(host_term, "帮助")["输出"]
    v = _vm_line(vm_term, "帮助")["输出"]
    assert h == v
    assert any("查找" in ln and "findstr" in ln for ln in h)
    assert any("排序" in ln and "sort" in ln for ln in h)
    assert any("13a 真化" in ln for ln in h)
    assert any("13b" in ln for ln in h)


# ---------- ② 闭环：胶水状态机 / 泄漏兜底 / 注册表扩展 ----------

def test_loop_glue_pipe_mode_machine():
    from src.kernel import terminal_builtin as tb
    tb.pipe_end()
    assert tb.pipe_feed(["行一", "行二"]) is True
    assert tb.read_line() == "行一"
    assert tb.read_line() == "行二"
    assert tb.read_line() == "", "管道耗尽应返回 EOF 空串"
    assert tb.read_line() == "", "耗尽后持续 EOF，不回落交互 stdin"
    assert tb.pipe_end() is True
    assert tb._pipe_lines is None
    with pytest.raises(RuntimeError, match="管道输入"):
        tb.pipe_feed("文本")


def test_loop_entry_clears_stale_pipe(host_term):
    from src.kernel import terminal_builtin as tb
    tb.pipe_feed(["stale"])
    r = _host_line(host_term, "回显 ok")
    assert r == {"输出": ["ok"], "退出": False}
    assert tb._pipe_lines is None, "终端执行 入口应清除陈旧管道态"


def test_loop_segment_error_leaks_then_next_entry_clears(host_term):
    from src.kernel import terminal_builtin as tb
    tb.pipe_end()
    with pytest.raises(RuntimeError, match="目录: 至多"):
        _host_line(host_term, "回显 a | 目录 a b")
    assert tb._pipe_lines == ["a"], "段内出错时管道态泄漏（登记边界）"
    r = _host_line(host_term, "回显 ok")
    assert r["输出"] == ["ok"]
    assert tb._pipe_lines is None, "下一条 终端执行 入口清除兜底"


def test_loop_extension_consumes_pipe(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    handler = tmp_path / "pipe_handler.matha"
    handler.write_text(_PIPE_HANDLER, encoding="utf-8")
    reg = _host_line(host_term, f'注册命令 管收 "{handler.as_posix()}"')
    assert reg["输出"] == [f"已注册扩展命令 管收 → {handler.as_posix()}"]
    h = _host_line(host_term, "回显 管到扩展 | 管收")
    assert h == {"输出": ["管到扩展 收到"], "退出": False}
    v = _vm_line(vm_term, "回显 管到扩展 | 管收")
    assert v == h, "注册表为共享盘面事实，VM 派发同处理器同结果"
    un = _host_line(host_term, "注销命令 管收")
    assert un == {"输出": ["已注销扩展命令 管收"], "退出": False}


def test_loop_sort_multi_line_via_extension(tmp_path, monkeypatch, host_term, vm_term):
    monkeypatch.chdir(tmp_path)
    handler = tmp_path / "multi.matha"
    handler.write_text(_MULTI_HANDLER, encoding="utf-8")
    _host_line(host_term, f'注册命令 多行 "{handler.as_posix()}"')
    h = _host_line(host_term, "回显 x | 多行 | 排序")
    v = _vm_line(vm_term, "回显 x | 多行 | 排序")
    assert h == v == {"输出": ["apple", "pear"], "退出": False}
    _host_line(host_term, "注销命令 多行")


def test_loop_shell_exec_with_input_direct():
    from src.domains.os_module import shell_exec_with_input
    r = shell_exec_with_input('python -c "print(int(input())*2)"', "21")
    assert r["returncode"] == 0 and r["success"] is True
    assert r["stdout"].strip() == "42"


def test_loop_matha_consumes_glue_pipe(host_term, vm_term):
    """Matha 代码经 _运行（命令表「运行」的实现体）直接消费胶水管道行：
    绕过 终端执行 入口清态（入口清陈旧态已由 test_loop_entry_clears_stale_pipe 锁定），
    故此处先喂后调、逐端独立供行。"""
    from src.kernel import terminal_builtin as tb
    src = "输出(输入行())"
    tb.pipe_feed(["host 管道值"])
    h = _host_call(host_term, "_运行", [src])
    tb.pipe_end()
    tb.pipe_feed(["vm 管道值"])
    v = vm_term.call("_运行", [src])
    tb.pipe_end()
    assert h == {"输出": ["host 管道值"], "退出": False}
    assert v == {"输出": ["vm 管道值"], "退出": False}


# ---------- ③ 拒绝（胶水层） ----------

def test_reject_pipe_feed_non_list():
    from src.kernel import terminal_builtin as tb
    tb.pipe_end()
    with pytest.raises(RuntimeError, match="需要 List"):
        tb.pipe_feed({"x": 1})
