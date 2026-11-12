# -*- coding: utf-8 -*-
"""阶段 12a：终端词法器/句法器（纯 Matha）入门禁。

三锁纪律：
  ① 对拍：token 序列与命令帧，宿主加载 = M3V VM 编译（vm = host）。
  ② 闭环：终端解析（词法+句法全链）两端跑同一批 CMD 模板命令行。
  ③ 拒绝：引号未闭合/缺命令名/重定向残缺/重定向位置错等，双端同文本显式拒绝。

零跳过，零失败。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import Interpreter
from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]

# 终端词法器为字符级扫描递归，递归深度随行长增长 → 抬高栈上限
sys.setrecursionlimit(max(30000, sys.getrecursionlimit()))

_FILES = ["matha/stdlib.matha", "matha/term_lexer.matha", "matha/term_parser.matha"]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_term():
    """宿主：加载 终端句法器（经 use 传递加载 终端词法器/标准库）。"""
    interp = Interpreter()
    assert interp.load_matha_module("终端句法器"), "加载 终端句法器 失败"
    interp.outputs.clear()
    return interp


@pytest.fixture(scope="module")
def vm_term():
    """M3V VM：编译 标准库 + 终端词法器 + 终端句法器，函数全局可调用。"""
    comp = Compiler()
    decls = []
    for rel in _FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


import src.ast_nodes as ast  # noqa: E402  （fixture 上方引用需先建 Program）


def _host_call(interp, fn, *args):
    return interp._call_func_or_closure(interp.funcs[fn], list(args))


def _host_lex(host, line):
    return _host_call(host, "终端词法分析", line)


def _host_frame(host, line):
    return _host_call(host, "终端解析", line)


# ---------- ① 对拍：token 序列（vm = host） ----------

_LEX_LINES = [
    "目录",
    "回显 hello world",
    '回显 "hello world"',
    '回显 "a|b"',
    '回显 "hi"there',
    "运行 a.matha | 显示",
    "回显 hi > out.txt",
    "回显 hi >> log.txt",
    "目录>f",
    "目录>>f",
    "回显\t带制表符 参数",
    "  回显   多   空格  ",
    '运行 "C:\\my dir\\a.matha"',
    "换目录 C:\\Users\\郑志坤",
]


@pytest.mark.parametrize("line", _LEX_LINES)
def test_lex_parity(host_term, vm_term, line):
    host = _host_lex(host_term, line)
    vmtok = vm_term.call("终端词法分析", line)
    assert host == vmtok, line


def test_lex_blank_line_empty_both(host_term, vm_term):
    """空行/全空白 → []（终端无操作），双端一致。"""
    for blank in ["", "   ", "\t\t"]:
        assert _host_lex(host_term, blank) == []
        assert vm_term.call("终端词法分析", blank) == []


# ---------- ① 对拍：命令帧（vm = host） ----------

_FRAME_LINES = [
    "目录",
    "目录 C:\\Users",
    "回显 hi",
    "回显 hi | 大写",
    "回显 hi | 大写 | 显示",
    "回显 hi > out.txt",
    "回显 hi >> log.txt",
    "目录>f",
    '运行 "C:\\my dir\\a.matha" 参数',
    "换目录 C:\\Users\\郑志坤",
]


@pytest.mark.parametrize("line", _FRAME_LINES)
def test_frame_parity(host_term, vm_term, line):
    host = _host_frame(host_term, line)
    vmf = vm_term.call("终端解析", line)
    assert host == vmf, f"{line}\nhost={host}\nvm  ={vmf}"


# ---------- ② 闭环：帧结构语义断言（两端各跑全链） ----------

def test_frame_shape_host(host_term):
    f = _host_frame(host_term, "回显 hi | 大写 > out.txt")
    assert f["命令"] == "回显"
    assert f["参数"] == ["hi"]
    assert len(f["管道链"]) == 1
    assert f["管道链"][0]["命令"] == "大写"
    assert f["管道链"][0]["参数"] == []
    assert f["重定向"] == ">"
    assert f["重定向目标"] == "out.txt"


def test_frame_shape_vm(vm_term):
    f = vm_term.call("终端解析", "回显 hi | 大写 > out.txt")
    assert f["命令"] == "回显"
    assert f["参数"] == ["hi"]
    assert len(f["管道链"]) == 1
    assert f["管道链"][0]["命令"] == "大写"
    assert f["管道链"][0]["参数"] == []
    assert f["重定向"] == ">"
    assert f["重定向目标"] == "out.txt"


def test_frame_minimal_no_redirection_host(host_term):
    f = _host_frame(host_term, "目录")
    assert f["重定向"] == "" and f["重定向目标"] == "" and f["管道链"] == []


def test_frame_minimal_no_redirection_vm(vm_term):
    f = vm_term.call("终端解析", "目录")
    assert f["重定向"] == "" and f["重定向目标"] == "" and f["管道链"] == []


# ---------- ③ 拒绝：双端同文本显式拒绝 ----------

_REJECT_LINES = [
    ('回显 "未闭合', "引号未闭合"),
    ("| 目录", "缺少命令名"),
    ("目录 |", "命令段为空"),
    ("a | | b", "缺少命令名"),
    ("回显 >", "重定向缺少目标文件"),
    ("回显 > f > g", "重定向符重复"),
    ("回显 >> f >> g", "重定向符重复"),
    ("回显 > f | 大写", "重定向必须位于命令行末尾"),
    ("> f", "缺少命令名"),
    (">> log", "缺少命令名"),
]


@pytest.mark.parametrize("line,msg", _REJECT_LINES)
def test_rejection_host(host_term, line, msg):
    with pytest.raises(Exception) as ei:
        _host_frame(host_term, line)
    assert msg in str(ei.value), f"{line} → {ei.value}"


@pytest.mark.parametrize("line,msg", _REJECT_LINES)
def test_rejection_vm(vm_term, line, msg):
    with pytest.raises(Exception) as ei:
        vm_term.call("终端解析", line)
    assert msg in str(ei.value), f"{line} → {ei.value}"


def test_rejection_empty_frame_both(host_term, vm_term):
    """终端帧分析([])（句法层空 token）双端拒绝；词法层空行仍是 []。"""
    with pytest.raises(Exception) as ei:
        _host_call(host_term, "终端帧分析", [])
    assert "命令为空" in str(ei.value)
    with pytest.raises(Exception) as ei:
        vm_term.call("终端帧分析", [])
    assert "命令为空" in str(ei.value)
