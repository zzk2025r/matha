# -*- coding: utf-8 -*-
"""砖块 19：文本语义三后端回归（解释器 / VM / 原生）。

覆盖开发期修复的四类问题：

1. 词法器字符串转义解码（``\\xNN``/``\\uNNNN``/``\\UNNNNNNNN``/八进制/常用简写）
2. 解析器浮点指数（``1e20``/``1e-7``/``2E5``），此前指数被拆成尾随标识符
3. 原生 ``str_repr_body`` 的 ``\\xNN`` 分支跳过前置普通字节 run 冲刷
   （``["a\\x01b"]`` 曾退化成 ``['\\x01b']``，吃掉前导 'a'）
4. 原生字符串 ``len``/索引按 UTF-8 字节而非码点
   （``len("你好")`` 曾为 6，``"你好"[0]`` 曾返回半个字符）

外加 C1 控制码与 NBSP 的 repr：CPython ``str.isprintable()`` 对 Unicode
类别 Cc/Zs 一律为 False，故 ``U+0080..U+00A0`` 必须转义成 ``\\xNN``，
而 ``U+00A1``（¡）起原样透传。
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


_EXE = os.path.join(tempfile.gettempdir(), "test_brick19_text.exe")
_aot_cache: dict[str, str] = {}


def _aot(src: str) -> str:
    """编译成 exe 运行，返回 stdout（去掉结尾换行）。带缓存避免重复编译。"""
    if src not in _aot_cache:
        Path(_EXE).write_bytes(compile_to_exe(src))
        r = subprocess.run([_EXE], capture_output=True, timeout=60)
        assert r.returncode == 0, f"AOT 退出码 {r.returncode}"
        _aot_cache[src] = r.stdout.decode("utf-8", "replace").rstrip("\r\n")
    return _aot_cache[src]


def _vm(src: str) -> str:
    return "\n".join(str(v) for v in run_module(compile_source(src)))


def _interp(src: str) -> str:
    return "\n".join(str(v) for v in interpret(src)[0])


def _all(src: str) -> tuple[str, str, str]:
    return _aot(src), _vm(src), _interp(src)


# ---------- 转义解码 ----------

_ESCAPE_CASES = [
    ('输出(["a\\x41b"])', "['aAb']"),                      # \xNN → ASCII
    ('输出(["\\u4e2d"])', "['\u4e2d']"),                  # \uNNNN → CJK
    ('输出(["a\\U0001F600b"])', "['a\U0001F600b']"),      # \UNNNNNNNN → astral
    ('输出(["a\\012b"])', "['a\\nb']"),                   # 八进制 → LF
    ('输出(["a\\qb"])', "['a\\\\qb']"),                   # 未知转义保留反斜杠
    ('输出(["\\x41" == "A"])', '[True]'),                 # 解码后可比较
    ('输出(len("a\\rb"))', '3'),                           # \r 解码后长度
    ('输出(len("a\\tb"))', '3'),                           # \t 解码后长度
]


@pytest.mark.parametrize("src,expected", _ESCAPE_CASES)
def test_escape_decoding_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


# ---------- repr 普通字节 run 冲刷（回归：吃掉前导 run） ----------

_RUN_FLUSH_CASES = [
    ('输出(["a\\x01b"])', "['a\\x01b']"),
    ('输出(["ab\\x01cd"])', "['ab\\x01cd']"),
    ('输出(["ab\\x01\\x02cd"])', "['ab\\x01\\x02cd']"),
    ('输出(str(["a\\x01b"]))', "['a\\x01b']"),
    ('输出(len(str(["ab\\x01cd"])))', '12'),   # ['ab\x01cd'] 的 repr 文本长度
    ('输出([["a\\x01b"]])', "[['a\\x01b']]"),
    ('输出([{"k": "a\\x01b"}])', "[{'k': 'a\\x01b'}]"),
]


@pytest.mark.parametrize("src,expected", _RUN_FLUSH_CASES)
def test_repr_run_flush_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


# ---------- C1 控制码 / NBSP repr ----------

#          码点        CPython repr     原因
_REPR_C1_CASES = [
    ('输出(["\\x80"])', "['\\x80']"),      # U+0080 Cc → 转义
    ('输出(["\\x9f"])', "['\\x9f']"),      # U+009F Cc（最后一个 C1）→ 转义
    ('输出(["\\xa0"])', "['\\xa0']"),      # U+00A0 NBSP（Zs）→ 转义
    ('输出(["\\xe9"])', "['\xe9']"),       # U+00E9 é（Ll）→ 透传
    ('输出(["\\xa1"])', "['\xa1']"),       # U+00A1 ¡（Po）→ 透传
]


@pytest.mark.parametrize("src,expected", _REPR_C1_CASES)
def test_repr_c1_and_nbsp_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


def test_repr_never_emits_raw_c1_byte():
    """repr 不能吐裸 0x80..0x9F（非法 UTF-8），NBSP 也必须转义。

    注意顶层 `输出("...")` 走 print 语义、原样输出码点，只有包进列表
    才走 repr 语义，所以这里都用 `输出([...])`。
    """
    out = _aot('输出(["\\x80"])')
    assert "\\x80" in out and "\x80" not in out
    # U+00A0 的裸字节是 C2 A0（合法 UTF-8），但 CPython isprintable 仍为 False
    nbsp = _aot('输出(["\\xa0"])')
    assert "\\xa0" in nbsp and "\xa0" not in nbsp


# ---------- len 按码点 ----------

_LEN_CASES = [
    ('输出(len("你好"))', '2'),                    # 2×3 字节 = 6，但只有 2 码点
    ('输出(len("a\\U0001F600b"))', '3'),          # astral 占 4 字节
    ('输出(len("a\\xe9b"))', '3'),                # 2 字节字符
    ('输出(len(""))', '0'),
    ('输出(len("abc"))', '3'),
]


@pytest.mark.parametrize("src,expected", _LEN_CASES)
def test_len_by_codepoint_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


# ---------- 索引按码点 ----------

_INDEX_CASES = [
    ('输出(["你好"[0]])', "['\u4f60']"),           # 第 0 个码点 = 你
    ('输出(["你好"[1]])', "['\u597d']"),           # 第 1 个码点 = 好
    ('输出(["a\\U0001F600b"[1]])', "['\U0001F600']"),  # 跨过 1 字节前缀
    ('输出(["abc"[1]])', "['b']"),
]


@pytest.mark.parametrize("src,expected", _INDEX_CASES)
def test_index_by_codepoint_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


def test_index_never_splits_multibyte_char():
    """原生索引不得返回半个 UTF-8 字符（旧实现按字节切）。"""
    got = _aot('输出(["你好"[0]])')
    assert "\xe4" not in got and "\xbd" not in got, f"返回了半个字符：{got!r}"
    assert got == "['你']"


# ---------- list(文本) ----------

_LIST_CASES = [
    ('输出(list("你好"))', "['\u4f60', '\u597d']"),
    ('输出(list("abc"))', "['a', 'b', 'c']"),
]


@pytest.mark.parametrize("src,expected", _LIST_CASES)
def test_list_of_text_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


def test_list_of_text_astral():
    """astral 字符必须是一个列表元素，不是两个代理字节。"""
    expected = "['a', '\U0001F600', 'b']"
    assert _all('输出(list("a\\U0001F600b"))') == (expected, expected, expected)


# ---------- 浮点指数 ----------

_FLOAT_CASES = [
    ('输出(1e20)', '1e+20'),
    ('输出(1e-7)', '1e-07'),
    ('输出(1.5e3)', '1500.0'),
    ('输出(2E5)', '200000.0'),
    ('输出(1e+3)', '1000.0'),
    ('输出(1.5)', '1.5'),
]


@pytest.mark.parametrize("src,expected", _FLOAT_CASES)
def test_float_exponent_all_backends(src, expected):
    assert _all(src) == (expected, expected, expected)


def test_float_exponent_not_split_into_identifiers():
    """指数不得被拆成「浮点字面量 + 尾随标识符」。"""
    from src.lexer import Lexer

    toks = [t.value for t in Lexer("1e20 + 1e-7").tokenize() if t.type != "EOF"]
    assert "e20" not in toks and "e" not in toks, f"指数被拆开：{toks}"
    assert "1e20" in toks and "1e-7" in toks, f"字面量不对：{toks}"