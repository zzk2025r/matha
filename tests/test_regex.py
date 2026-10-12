"""正则库测试：引擎单元 + 解释器/VM 双端一致。

引擎为 src/regexlib.py（可移植回溯实现），解释器（src/interp.py）与
M3V VM（src/mbc/vm.py）复用同一注册函数 `_register_regex_builtins`，
故两端语义必须完全一致——本文件对每条用例同时跑两端并比对。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import regexlib as rx
from src.interp import interpret
from src.mbc.compiler import compile_source
from src.mbc.vm import run_module


def _both(src):
    out_i, _ = interpret(src)
    out_v = run_module(compile_source(src))
    assert out_i == out_v, f"解释器 {out_i!r} != VM {out_v!r}"
    return out_i


# ---------------- 引擎单元（直接调用 regexlib） ----------------

def test_engine_basic_search():
    assert rx.compile_regex(r"\d+").search("abc123").group(0) == "123"
    assert rx.compile_regex(r"\d+").search("abc") is None


def test_engine_groups_and_optional():
    m = rx.compile_regex(r"(a)(b)?c").search("ac")
    assert m.group(0) == "ac"
    assert m.group(1) == "a"
    assert m.group(2) is None


def test_engine_backreference():
    assert rx.compile_regex(r"(\w)\1").search("abba").group(0) == "bb"


def test_engine_lookahead():
    m = rx.compile_regex(r"\d+(?=px)").search("12px 34em")
    assert m.group(0) == "12"


def test_engine_lookbehind():
    m = rx.compile_regex(r"(?<=\$)\d+").search("$42 and $7")
    assert m.group(0) == "42"


def test_engine_greedy_vs_lazy():
    assert rx.compile_regex(r"<(.+)>").search("<a><b>").group(1) == "a><b"
    assert rx.compile_regex(r"<(.+?)>").search("<a><b>").group(1) == "a"


def test_engine_char_class_escapes():
    assert rx.compile_regex(r"[\]]").search("x]y").group(0) == "]"
    assert rx.compile_regex(r"[\n]").search("a\nb").group(0) == "\n"
    assert rx.compile_regex(r"[a-c]+").search("xxabcyy").group(0) == "abc"
    assert rx.compile_regex(r"[^0-9]+").search("12ab3").group(0) == "ab"


def test_engine_flags():
    assert rx.compile_regex(r"abc", rx._I).search("ABC") is not None
    assert rx.compile_regex(r"a.b", rx._S).search("a\nb") is not None
    assert rx.compile_regex(r"a.b").search("a\nb") is None
    assert rx.compile_regex(r"^b", rx._M).search("a\nb") is not None


def test_engine_sub_and_split():
    assert rx.compile_regex(r"(\d)(\w)").sub(r"\2\1", "1a 2b") == "a1 b2"
    assert rx.compile_regex(r"\s+").split("a b  c") == ["a", "b", "c"]


def test_engine_named_group_dict():
    m = rx.compile_regex(r"(?P<y>\d{4})-(?P<m>\d{2})").search("2026-10")
    assert m.group(m.pat.names["y"]) == "2026"
    assert m.group(2) == "10"


def test_engine_inline_verbose_scope():
    assert rx.compile_regex(r"(?x) a b  # comment\n c").search("abc") is not None


# ---------------- 解释器 / VM 双端一致 ----------------

@pytest.mark.parametrize("src,expected", [
    (r'输出(匹配("\d+")("abc123"))', [True]),
    (r'输出(匹配("\d+")("abc"))', [False]),
    (r'输出(全匹配("\d+")("123"))', [True]),
    (r'输出(全匹配("\d+")("12a"))', [False]),
    (r'输出(查找正则("(\w+)\s+(\w+)")("hi there"))', [["hi there", "hi", "there"]]),
    (r'输出(查找正则("(a)(b)?c")("ac"))', [["ac", "a", None]]),
    (r'输出(查找正则("z")("abc"))', [None]),
    (r'输出(查找全部("\d+")("a1b22c333"))', [[["1"], ["22"], ["333"]]]),
    (r'输出(命名组("(?P<y>\d{4})-(?P<m>\d{2})")("2026-10"))',
     [{"y": "2026", "m": "10"}]),
    (r'输出(命名组("(?P<y>\d{4})")("none"))', [None]),
    (r'输出(替换正则("\d")("#")("a1b2"))', ["a#b#"]),
    (r'输出(替换正则("(\w+)@(\w+)")("$2.$1")("user@host"))', ["host.user"]),
    (r'输出(分割正则("\s+")("a b  c"))', [["a", "b", "c"]]),
    (r'输出(分割正则(",(\d)")("a,1b,2"))', [["a", "1", "b", "2", ""]]),
    (r'输出(匹配("(?i)abc")("ABC"))', [True]),
    (r'输出(匹配("(?m)^a")("b\na"))', [True]),
    (r'输出(匹配("^a")("b\na"))', [False]),
    (r'输出(匹配("(?s)a.b")("a\nb"))', [True]),
    (r'输出(匹配("[a-c]+")("xxabcyy"))', [True]),
    (r'输出(查找正则("([a-z]+)(\d+)")("abc123"))', [["abc123", "abc", "123"]]),
    (r'输出(查找全部("\w+")("one two three"))',
     [[["one"], ["two"], ["three"]]]),
    (r'输出(匹配("(\w)\\1")("abba"))', [True]),
    (r'输出(查找正则("\d+(?=px)")("12px 34em"))', [["12"]]),
    (r'输出(查找正则("(?<=\$)\d+")("$42 and $7"))', [["42"]]),
])
def test_regex_parity(src, expected):
    assert _both(src) == expected


def test_regex_named_backref_in_pattern():
    assert _both(r'输出(匹配("(?P<d>\d)(?P=d)")("55"))') == [True]
    assert _both(r'输出(匹配("(?P<d>\d)(?P=d)")("56"))') == [False]


def test_regex_is_callable_as_first_class_value():
    src = (
        'let f = 替换正则("o")("0")\n'
        '输出(f("foo"))\n'
    )
    assert _both(src) == ["f00"]
