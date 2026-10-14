"""原生后端正则（阶段 A 字面量 + 阶段 B-1 元字符）测试。

覆盖 匹配/全匹配 的字面量语义（子串/精确、空模式、UTF-8 多字节）、阶段 B-1
的元字符/字符类/量词/分组/交替/锚点语义、暂不支持构造与省略字符串参数的
错误路径（可捕获 + 退出码），以及与解释器/VM 结果的 parity。
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


META_CASES = [
    ('匹配("a.c")("abc")', True),
    ('匹配("a.c")("ac")', False),
    ('匹配("a.c")("a\\nc")', False),
    ('匹配("a*")("aaa")', True),
    ('全匹配("a*")("aaa")', True),
    ('全匹配("a*")("")', True),
    ('匹配("^ab")("ab")', True),
    ('匹配("^ab")("cab")', False),
    ('匹配("[a-z]")("a")', True),
    ('匹配("[a-z]")("A")', False),
    ('匹配("[^a-z]")("A")', True),
    ('匹配("a|b")("b")', True),
    ('匹配("a+")("a")', True),
    ('匹配("a?")("b")', True),
    ('全匹配("a?")("")', True),
    ('全匹配("(a|ab)c")("abc")', True),
    ('匹配("(a)")("a")', True),
    ('匹配("^a$")("a")', True),
    ('匹配("^a$")("ab")', False),
    ('匹配("\\\\d+")("abc123")', True),
    ('匹配("\\\\d+")("abc")', False),
    ('匹配("\\\\w+")("!!!")', False),
    ('匹配("\\\\s")("a b")', True),
    ('匹配("\\\\bfoo\\\\b")("a foo b")', True),
    ('匹配("\\\\bfoo\\\\b")("afoob")', False),
    ('全匹配("\\\\Aab\\\\Z")("ab")', True),
    ('匹配("ab\\\\z")("ab")', True),
    ('匹配("a\\\\x41")("aA")', True),
    ('匹配("a\\\\u0041")("aA")', True),
    ('匹配("\\\\U00000041")("A")', True),
    ('匹配("[a-cx]+")("xxcba")', True),
    ('匹配("(?:ab)+")("abab")', True),
    ('全匹配("(a*)*")("")', True),
    ('匹配("([a-z]+@[a-z]+\\\\.[a-z]+)")("mail foo@bar.com ok")', True),
    ('匹配("colou?r")("color")', True),
]


@pytest.mark.parametrize("expr,expected", META_CASES)
def test_meta_match(expr, expected):
    rc, out = _run(f"输出({expr})")
    assert rc == 0 and out == str(expected)


def test_meta_parity_with_host():
    body = "\n".join(f"输出({e})" for e, _ in META_CASES)
    rc, out = _run(body)
    assert rc == 0
    iout, vout = _host(body)
    if iout is not None:
        assert iout.strip() == out
    assert vout.strip() == out


BUILTIN_CASES = [
    r'输出(查找正则("a")("bab"))',
    r'输出(查找正则("(a)(b)")("zabz"))',
    r'输出(查找正则("(x)")("zabz"))',
    r'输出(查找正则("a")("zzz"))',
    r'输出(查找全部("a")("banana"))',
    r'输出(查找全部("")("ab"))',
    r'输出(查找全部("\\d+")("a12b345"))',
    r'输出(命名组("(?P<x>a)(?P<y>b)")("zab"))',
    r'输出(命名组("(?P<x>a)(?P<y>b)")("zzz"))',
    r'输出(命名组("(?P<x>a)(?P<y>b)")("za"))',
    r'输出(分割正则(",")("a,b,c"))',
    r'输出(分割正则("(,)")("a,b,c"))',
    r'输出(分割正则("x")("abc"))',
    r'输出(替换正则("a")("X")("banana"))',
    r'输出(替换正则("(a)")("[\\1]")("bab"))',
    r'输出(替换正则("(?P<x>a)")("<\\g<x>>")("ab"))',
    r'输出(替换正则("\\d")("#")("a1b2"))',
]


def test_builtin_parity_with_host():
    body = "\n".join(BUILTIN_CASES)
    rc, out = _run(body)
    assert rc == 0
    iout, vout = _host(body)
    if iout is not None:
        assert iout.strip() == out
    assert vout.strip() == out


@pytest.mark.parametrize("pat,subj", [
    ("a{2}", "aa"),
    ("a{2,3}", "aaa"),
    ("a??", "a"),
    ("(?=a)", "a"),
    ("(?<=a)b", "ab"),
    ('(a)\\\\1', "aa"),
    ("(?i)a", "A"),
])
def test_unsupported_meta_raises_catchable(pat, subj):
    src = (
        "func 试() -> Int =\n"
        f'  匹配("{pat}")("{subj}")\n'
        "输出(调用捕获(试)([]))\n"
    )
    rc, out = _run(src)
    assert rc == 0
    assert out.startswith('[\'__异常__\', \'原生正则：模式解析失败')


def test_unsupported_meta_uncaught_exits_one():
    rc, out = _run('匹配("a{2}")("aa")')
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


def test_unresolved_global_rejected(monkeypatch):
    """未实现的 VM 全局在编译期报 NativeNotSupported，而非运行期访问违例。

    MathaIOError / list_push 均已实现，真实名字再无未实现者；此处以
    monkeypatch 注入探针名，验证该防御分支仍然生效。"""
    from src.mbc import native as nat
    from src.mbc.native import NativeNotSupported
    probe = "__regex_unresolved_probe__"
    monkeypatch.setattr(nat, "_UNRESOLVED_GLOBALS",
                        nat._UNRESOLVED_GLOBALS | {probe})
    with pytest.raises(NativeNotSupported):
        compile_to_exe(f"输出({probe})")
