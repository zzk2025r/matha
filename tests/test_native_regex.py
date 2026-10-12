"""原生后端正则（阶段 A：字面量）测试。

覆盖 匹配/全匹配 的字面量语义（子串/精确、空模式、UTF-8 多字节）、元字符与
非字符串的错误路径（可捕获 + 退出码），以及与解释器/VM 结果的 parity。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret
from src.mbc import compile_source, run_module
from src.mbc.native import compile_to_exe


def _run(src):
    exe = os.path.join(tempfile.gettempdir(), "pr_native_regex.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    lines = r.stdout.decode("utf-8", "replace").strip().splitlines()
    return r.returncode & 0xFFFFFFFF, "\n".join(lines)


def _host(src):
    """解释器与 VM 的输出（两者应一致），返回去尾的输出文本。"""
    iout = "\n".join(str(v) for v in interpret(src)[0])
    vout = "\n".join(str(v) for v in run_module(compile_source(src)))
    return iout, vout


LITERAL_CASES = [
    ('匹配("world")("hello world")', True),
    ('匹配("xyz")("hello world")', False),
    ('匹配("")("abc")', True),
    ('匹配("")("")', True),
    ('匹配("abc")("abc")', True),
    ('匹配("bc")("abcd")', True),
    ('匹配("abcd")("bc")', False),
    ('全匹配("hello")("hello")', True),
    ('全匹配("hell")("hello")', False),
    ('全匹配("")("")', True),
    ('全匹配("")("x")', False),
    ('匹配("世")("你好世界")', True),
    ('匹配("你好")("你好世界")', True),
    ('全匹配("你好")("你好")', True),
    ('全匹配("你好")("你好世界")', False),
]


@pytest.mark.parametrize("expr,expected", LITERAL_CASES)
def test_literal_match(expr, expected):
    rc, out = _run(f"输出({expr})")
    assert rc == 0 and out == str(expected)


def test_literal_parity_with_host():
    body = "\n".join(f"输出({e})" for e, _ in LITERAL_CASES)
    rc, out = _run(body)
    assert rc == 0
    iout, vout = _host(body)
    if iout is not None:
        assert iout.strip() == out
    assert vout.strip() == out


@pytest.mark.parametrize("pat,subj", [
    ("a.c", "abc"),
    ("a*", "aaa"),
    ("^ab", "ab"),
    ("[a-z]", "a"),
    ("a|b", "a"),
    ("a+", "a"),
    ("a?", "a"),
    ("(a)", "a"),
    ("a{2}", "aa"),
])
def test_meta_raises_catchable(pat, subj):
    src = (
        "func 试() -> Int =\n"
        f'  匹配("{pat}")("{subj}")\n'
        "输出(调用捕获(试)([]))\n"
    )
    rc, out = _run(src)
    assert rc == 0
    assert out.startswith('[\'__异常__\', \'原生正则：暂不支持元字符模式')


def test_meta_uncaught_exits_one():
    rc, out = _run('匹配("a.c")("abc")')
    assert rc == 1 and out == ""


def test_non_string_raises_catchable():
    src = (
        "func 试() -> Int =\n"
        "  匹配(1)(2)\n"
        "输出(调用捕获(试)([]))\n"
    )
    rc, out = _run(src)
    assert rc == 0
    assert out.startswith('[\'__异常__\', \'原生正则：需要字符串参数')


def test_non_string_uncaught_exits_one():
    rc, out = _run("匹配(1)(2)")
    assert rc == 1 and out == ""


def test_unresolved_global_rejected():
    from src.mbc.native import NativeNotSupported
    with pytest.raises(NativeNotSupported):
        compile_to_exe('输出(查找正则("a")("a"))')
