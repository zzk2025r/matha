# -*- coding: utf-8 -*-
"""阶段 12c：纯 Matha 终端执行器入门禁（命令注册表/CMD 命令集/CMD 式透传/显式拒绝）。

三锁纪律：
  ① 对拍：同一命令行，宿主执行器 = M3V VM 执行器（结果帧逐值一致，含透传）。
  ② 闭环：编写→加载→运行 全链、换目录→列目录 进程级真状态、调试 轨迹+快照全链。
  ③ 拒绝：参数个数逐命令校验双端同文本；管道已于阶段 13a 真化（锁见
     test_matha_term_13a.py）；重定向已于阶段 13b 真化（锁见
     test_matha_term_13b.py）；非空目录递归删除显式拒绝且目录原样保留；
     VM 调试Matha 拒绝穿透引擎如实上抛。

零跳过，零失败。
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

# 词法器为字符级扫描递归 → 抬高栈上限（与 12a 同口径）
sys.setrecursionlimit(max(30000, sys.getrecursionlimit()))

_FILES = ["matha/stdlib.matha", "matha/term_lexer.matha", "matha/term_parser.matha",
          "matha/term_engine.matha"]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_term():
    """宿主：加载 终端执行器（经 use 传递加载 终端句法器/词法器/标准库）。"""
    interp = Interpreter()
    assert interp.load_matha_module("终端执行器"), "加载 终端执行器 失败"
    return interp


@pytest.fixture(scope="module")
def vm_term():
    """M3V VM：编译 标准库+终端三模块，接线插件解析器（透传需要 领域内建 执行命令）。"""
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


# ---------- ① 对拍：注册表分发 / 别名 / 结果帧（vm = host） ----------

_PARITY_LINES = [
    "回显 hello world",
    "echo 别名一致",
    "ECHO ABC",           # 英文别名大小写不敏感
    "回显",
    "退出",
    "帮助",
    "清屏",
    '运行 "输出(1+2)"',
    '运行 "let x = 5 in 输出([x, 真, null])"',
]


@pytest.mark.parametrize("line", _PARITY_LINES)
def test_parity_host_vm(host_term, vm_term, line):
    h = _host_line(host_term, line)
    v = _vm_line(vm_term, line)
    assert h == v, f"{line}\nhost={h}\nvm  ={v}"


def test_parity_exit_flag(host_term, vm_term):
    h = _host_line(host_term, "退出")
    v = _vm_line(vm_term, "退出")
    assert h == v == {"输出": [], "退出": True}


def test_parity_help_shape(host_term, vm_term):
    h = _host_line(host_term, "帮助")["输出"]
    v = _vm_line(vm_term, "帮助")["输出"]
    assert h == v and h[0].startswith("Matha 终端") and len(h) >= 15
    assert any("透传" in ln for ln in h) and any("重定向" in ln for ln in h)


@pytest.mark.parametrize("value,expect", [
    ("文本", "文本"),
    (42, "42"),
    (2.5, "2.5"),
    (True, "真"),
    (False, "假"),
    (None, "null"),
    ([1, "a", True], "[1, a, 真]"),
    ({"x": 1}, "{x: 1}"),
    ([1, [2, 3]], "[1, [2, 3]]"),
])
def test_parity_display_renderer(host_term, vm_term, value, expect):
    assert _host_call(host_term, "显示值", value) == expect
    assert vm_term.call("显示值", value) == expect


def test_parity_one_liner_entry(host_term, vm_term):
    h = _host_call(host_term, "终端运行一行", "回显 一行式")
    v = vm_term.call("终端运行一行", "回显 一行式")
    assert h == v == {"输出": ["一行式"], "退出": False}


# ---------- ① 对拍：文件系统命令（同一操作序列，A 宿主 / B VM 镜像） ----------

def _mirror_dirs(tmp_path):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    for side in ("A", "B"):
        (tmp_path / side / "内含").mkdir()
        (tmp_path / side / "f.txt").write_text("第一行\n第二行\n", encoding="utf-8")


def test_fs_parity_listing_and_read(tmp_path, host_term, vm_term):
    _mirror_dirs(tmp_path)
    h = _host_line(host_term, f'目录 "{(tmp_path / "A").as_posix()}"')
    v = _vm_line(vm_term, f'目录 "{(tmp_path / "B").as_posix()}"')
    assert h == v
    assert ["f.txt\t22"] == [ln for ln in v["输出"] if ln.startswith("f.txt")]
    assert "内含\t<目录>" in v["输出"]
    h = _host_line(host_term, f'显示文件 "{(tmp_path / "A" / "f.txt").as_posix()}"')
    v = _vm_line(vm_term, f'显示文件 "{(tmp_path / "B" / "f.txt").as_posix()}"')
    assert h == v == {"输出": ["第一行", "第二行"], "退出": False}


def test_fs_parity_copy_rename_delete(tmp_path, host_term, vm_term):
    _mirror_dirs(tmp_path)
    h = _host_line(host_term, f'复制 "{(tmp_path / "A" / "f.txt").as_posix()}"'
                              f' "{(tmp_path / "A" / "g.txt").as_posix()}"')
    v = _vm_line(vm_term, f'复制 "{(tmp_path / "B" / "f.txt").as_posix()}"'
                          f' "{(tmp_path / "B" / "g.txt").as_posix()}"')
    assert h == v == {"输出": ["已复制 1 个文件。"], "退出": False}
    assert (tmp_path / "A" / "g.txt").exists() and (tmp_path / "B" / "g.txt").exists()
    h = _host_line(host_term, f'改名 "{(tmp_path / "A" / "g.txt").as_posix()}"'
                              f' "{(tmp_path / "A" / "h.txt").as_posix()}"')
    v = _vm_line(vm_term, f'改名 "{(tmp_path / "B" / "g.txt").as_posix()}"'
                          f' "{(tmp_path / "B" / "h.txt").as_posix()}"')
    assert h == v == {"输出": [], "退出": False}
    assert (tmp_path / "A" / "h.txt").exists() and not (tmp_path / "A" / "g.txt").exists()
    h = _host_line(host_term, f'删除 "{(tmp_path / "A" / "h.txt").as_posix()}"')
    v = _vm_line(vm_term, f'删除 "{(tmp_path / "B" / "h.txt").as_posix()}"')
    assert h == v == {"输出": [], "退出": False}
    assert not (tmp_path / "A" / "h.txt").exists()
    assert not (tmp_path / "B" / "h.txt").exists()


def test_fs_mkdir_listing_empty(tmp_path, host_term, vm_term):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    h = _host_line(host_term, f'建目录 "{(tmp_path / "A" / "新").as_posix()}"')
    v = _vm_line(vm_term, f'建目录 "{(tmp_path / "B" / "新").as_posix()}"')
    assert h == v == {"输出": [], "退出": False}
    assert (tmp_path / "A" / "新").is_dir()
    h = _host_line(host_term, f'目录 "{(tmp_path / "A").as_posix()}"')
    v = _vm_line(vm_term, f'目录 "{(tmp_path / "B").as_posix()}"')
    assert h == v == {"输出": ["新\t<目录>"], "退出": False}


# ---------- ① 对拍：CMD 式透传（未知命令 → 系统 shell 真执行） ----------

def test_passthrough_parity(host_term, vm_term):
    h = _host_line(host_term, "python --version")
    v = _vm_line(vm_term, "python --version")
    assert h == v
    assert h["退出"] is False
    assert any("Python" in ln for ln in h["输出"])
    assert not any("退出码" in ln for ln in h["输出"])


def test_passthrough_exit_code_honest_both(host_term, vm_term):
    line = 'python -c "import sys; sys.exit(3)"'
    h = _host_line(host_term, line)
    v = _vm_line(vm_term, line)
    assert h == v
    assert "命令退出码: 3" in h["输出"]


def test_passthrough_frame_reconstruction(host_term, vm_term):
    """原行="" 时按帧重建（命令 + 空格拼接参数），两端一致。"""
    hf = _host_call(host_term, "终端解析", "python --version")
    vf = vm_term.call("终端解析", "python --version")
    h = _host_call(host_term, "终端执行", hf, "")
    v = vm_term.call("终端执行", vf, "")
    assert h == v
    assert any("Python" in ln for ln in h["输出"])


# ---------- ② 闭环：编写 → 加载 → 运行 / 换目录 → 列目录 / 调试 ----------

def test_loop_write_load_run(tmp_path, host_term, vm_term):
    src_a = (tmp_path / "A.matha").as_posix()
    h = _host_line(host_term, f'编写 "{src_a}" "输出(40+2)"')
    assert h["输出"] == [f"已编写 {src_a}"]
    assert (tmp_path / "A.matha").read_text(encoding="utf-8") == "输出(40+2)"
    h = _host_line(host_term, f'加载 "{src_a}"')
    assert h == {"输出": ["42"], "退出": False}
    src_b = (tmp_path / "B.matha").as_posix()
    v = _vm_line(vm_term, f'编写 "{src_b}" "输出(40+2)"')
    assert v["输出"] == [f"已编写 {src_b}"]
    assert (tmp_path / "B.matha").read_text(encoding="utf-8") == "输出(40+2)"
    v = _vm_line(vm_term, f'加载 "{src_b}"')
    assert v == {"输出": ["42"], "退出": False}


def test_loop_cd_and_listing(tmp_path, host_term, vm_term):
    """换目录进程级真状态：宿主切 A、VM 切 B，各自 列目录 反映当前目录。"""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    (tmp_path / "A" / "仅A.txt").write_text("a", encoding="utf-8")
    (tmp_path / "B" / "仅B.txt").write_text("b", encoding="utf-8")
    old = os.getcwd()
    try:
        h = _host_line(host_term, f'换目录 "{(tmp_path / "A").as_posix()}"')
        assert h == {"输出": [], "退出": False}
        assert os.getcwd() == str(tmp_path / "A")
        h = _host_line(host_term, "目录")
        assert h["输出"] == ["仅A.txt\t1"]
        v = _vm_line(vm_term, f'换目录 "{(tmp_path / "B").as_posix()}"')
        assert v == {"输出": [], "退出": False}
        assert os.getcwd() == str(tmp_path / "B")
        v = _vm_line(vm_term, "目录")
        assert v["输出"] == ["仅B.txt\t1"]
    finally:
        os.chdir(old)


def test_loop_debug_host(host_term):
    r = _host_line(host_term, '调试 "let 值 = 5 in 输出(值 + 1)"')
    lines = r["输出"]
    assert r["退出"] is False
    ti, oi, vi = lines.index("== 轨迹 =="), lines.index("== 输出 =="), lines.index("== 变量 ==")
    assert ti < oi < vi
    assert lines[ti + 1:oi], "轨迹段为空"
    assert lines[oi + 1:vi] == ["6"]
    assert any(ln.startswith("值 = ") and "5" in ln for ln in lines[vi + 1:])


def test_loop_debug_error_section(host_term):
    r = _host_line(host_term, '调试 "输出(1/0)"')
    assert any(ln.startswith("== 错误: ") for ln in r["输出"])
    assert any("ZeroDivision" in ln or "除" in ln for ln in r["输出"])


# ---------- ③ 拒绝：参数个数 / 安全边界（重定向/管道真化锁各归 13b/13a） ----------

_REJECT_LINES = [
    ("目录 a b", "目录: 至多"),
    ("换目录", "换目录: 需要"),
    ("换目录 a b", "换目录: 需要"),
    ("显示文件", "显示文件: 需要"),
    ("复制 只有一个", "复制: 需要"),
    ("复制 a b c", "复制: 需要"),
    ("删除", "删除: 需要"),
    ("建目录", "建目录: 需要"),
    ("改名 一个", "改名: 需要"),
    ("运行", "运行: 需要"),
    ("运行 a b", "运行: 需要"),
    ("加载", "加载: 需要"),
    ("编写 只有路径", "编写: 需要"),
    ("调试", "调试: 需要"),
    ("清屏 多余", "清屏: 不需要"),
]


@pytest.mark.parametrize("line,frag", _REJECT_LINES)
def test_reject_host(host_term, line, frag):
    with pytest.raises(RuntimeError, match=frag):
        _host_line(host_term, line)


@pytest.mark.parametrize("line,frag", _REJECT_LINES)
def test_reject_vm(vm_term, line, frag):
    with pytest.raises(RuntimeError, match=frag):
        _vm_line(vm_term, line)


def test_reject_nonempty_dir_both_preserved(tmp_path, host_term, vm_term):
    for side in ("A", "B"):
        (tmp_path / side).mkdir()
        (tmp_path / side / "内容.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="递归删除不受支持"):
        _host_line(host_term, f'删除 "{(tmp_path / "A").as_posix()}"')
    with pytest.raises(RuntimeError, match="递归删除不受支持"):
        _vm_line(vm_term, f'删除 "{(tmp_path / "B").as_posix()}"')
    assert (tmp_path / "A" / "内容.txt").exists()
    assert (tmp_path / "B" / "内容.txt").exists()


def test_reject_missing_file_propagates(tmp_path, host_term, vm_term):
    with pytest.raises(RuntimeError):
        _host_line(host_term, f'显示文件 "{(tmp_path / "无此物").as_posix()}"')
    with pytest.raises(RuntimeError):
        _vm_line(vm_term, f'显示文件 "{(tmp_path / "无此物").as_posix()}"')


def test_reject_vm_debug_through_engine(vm_term):
    """VM 调试Matha 显式拒绝穿透引擎（非静默降级）。"""
    with pytest.raises(RuntimeError, match="宿主解释器"):
        _vm_line(vm_term, '调试 "输出(1)"')
    with pytest.raises(RuntimeError, match="显式拒绝"):
        _vm_line(vm_term, '调试 "输出(1)"')
