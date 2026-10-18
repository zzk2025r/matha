# -*- coding: utf-8 -*-
"""语言桥（src/matha/language_bridge.py）控制流函数体翻译测试。

覆盖：
  1. Python 路径 — if/return、elif、let 绑定、布尔/比较/整除翻译
  2. 外部语言路径（rust / go / js / c）— if/else、else if、提前 return、let
  3. 循环等未支持结构 → 保留无中生有骨架（默认行为）
  4. SCOPED_BLOCKS 开启 — 循环/多语句体译为 Matha 语句块 `{ ... }` 并可运行
  5. fuse：生成模块通过 Matha parser 自验证
"""
import os
import sys
sys.path.insert(0, r'D:\trae')

import pytest

from src import features
from src.interp import interpret
from src.matha.language_bridge import LanguageBridge, matha_expr


def _fn(record, name):
    for f in record.functions:
        if f.name == name:
            return f
    raise AssertionError(f"未找到函数 {name}: {[f.name for f in record.functions]}")


# ── Python 路径 ────────────────────────────────────────────────

_PY_SRC = '''
def divide(a, b):
    if b == 0:
        return None
    return a / b

def lcm(a, b):
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // gcd(a, b)

def sign3(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0

def emit(x):
    y = x * 2
    return y + 1

def loopy(n):
    s = 0
    for i in range(n):
        s = s + i
    return s
'''


@pytest.fixture(scope="module")
def py_record():
    return LanguageBridge().devour('python', _PY_SRC, 'py_test')


def test_python_if_return_null(py_record):
    f = _fn(py_record, 'divide')
    assert not f.generated, f.body
    assert 'null' in f.body and '?' in f.body


def test_python_or_and_floordiv(py_record):
    f = _fn(py_record, 'lcm')
    assert not f.generated, f.body
    assert ' or ' in f.body and '//' in f.body


def test_python_elif_chain(py_record):
    f = _fn(py_record, 'sign3')
    assert not f.generated, f.body
    assert f.body.count('?') == 2


def test_python_let_binding(py_record):
    f = _fn(py_record, 'emit')
    assert not f.generated, f.body
    assert f.body.startswith('let ')


def test_python_loop_stays_skeleton(py_record):
    f = _fn(py_record, 'loopy')
    assert f.generated
    assert '无中生有骨架' in f.body


def test_python_module_fuse(py_record):
    assert LanguageBridge().fuse(py_record, write=False) is True


# ── 外部语言路径 ───────────────────────────────────────────────

_FOREIGN = {
    'rust': 'fn clamp(v: i32, lo: i32, hi: i32) -> i32 '
            '{ if v < lo { return lo; } else if v > hi { return hi; } return v; }',
    'js': 'function max3(a, b, c) { if (a >= b && a >= c) { return a; } '
          'else if (b >= c) { return b; } return c; }',
    'go': 'func absInt(x int) int { if x < 0 { return -x } return x }',
    'c': 'int sign(int x) { if (x > 0) { return 1; } '
         'else if (x < 0) { return -1; } return 0; }',
}


@pytest.mark.parametrize("lang", sorted(_FOREIGN))
def test_foreign_control_flow_translated(lang):
    rec = LanguageBridge().devour(lang, _FOREIGN[lang], 'f_' + lang)
    assert rec.success, rec.error
    f = rec.functions[0]
    assert not f.generated, f.body
    assert '?' in f.body, f.body
    assert LanguageBridge().fuse(rec, write=False) is True


def test_foreign_logical_op_parses():
    rec = LanguageBridge().devour(
        'js', 'function both(a, b) { if (a && b) { return 1; } return 0; }', 'logic')
    f = rec.functions[0]
    assert 'and' in f.body, f.body          # 不可用 Matha 不识别的 且/或
    assert LanguageBridge().fuse(rec, write=False) is True


def test_foreign_loop_stays_skeleton():
    rec = LanguageBridge().devour(
        'rust', 'fn sum_to(n: i32) -> i32 { let mut s = 0; '
                'for i in 0..n { s += i; } return s; }', 'loops')
    assert rec.functions[0].generated


# ── 表达式翻译器回归 ───────────────────────────────────────────

@pytest.mark.parametrize("src,expect", [
    ('a && b', '(a and b)'),
    ('a || b', '(a or b)'),
    ('a != b', '(a ≠ b)'),
    ('a ** b', 'a ^ b'),
    ('a ? b : c', 'a ? b : c'),
])
def test_matha_expr_basics(src, expect):
    assert matha_expr(src) == expect


# ── SCOPED_BLOCKS 语句块直译（开关开启时） ──────────────────────

_BLOCK_PY_SRC = '''
def sum_list(xs: list) -> int:
    s = 0
    for x in xs:
        s += x
    return s

def sum_to(n: int) -> int:
    s = 0
    i = 1
    while i <= n:
        s += i
        i += 1
    return s

def clamp(v: int, lo: int, hi: int) -> int:
    if v < lo:
        v = lo
    if v > hi:
        v = hi
    return v

def not_prime_ish(n: int) -> bool:
    if n < 2:
        return False
    for i in range(3, 10):
        if n % i == 0:
            return False
    return True
'''


@pytest.fixture(autouse=True)
def _isolate_scoped_flag():
    """开关隔离：本文件测试之间互不污染，且结束后恢复现场。"""
    saved = os.environ.get("MATHA_FEATURE_SCOPED_BLOCKS")
    features.clear_feature()
    try:
        yield
    finally:
        features.clear_feature()
        if saved is None:
            os.environ.pop("MATHA_FEATURE_SCOPED_BLOCKS", None)
        else:
            os.environ["MATHA_FEATURE_SCOPED_BLOCKS"] = saved


@pytest.fixture
def block_record(_isolate_scoped_flag):
    features.set_feature("SCOPED_BLOCKS", True)
    return LanguageBridge().devour('python', _BLOCK_PY_SRC, 'block_test')


def test_for_loop_block_translates(block_record):
    f = _fn(block_record, 'sum_list')
    assert not f.generated, f.body
    assert f.body.strip().startswith('{')
    assert 'for x in xs' in f.body


def test_while_loop_block_translates(block_record):
    f = _fn(block_record, 'sum_to')
    assert not f.generated, f.body
    assert 'while i <= n' in f.body
    assert 'i = i + 1' in f.body


def test_if_statement_block_translates(block_record):
    f = _fn(block_record, 'clamp')
    assert not f.generated, f.body
    assert 'if v < lo' in f.body and 'if v > hi' in f.body


def test_early_return_in_loop_stays_skeleton(block_record):
    # 提前 return（块内非末尾 return）不支持 → 仍为无中生有骨架
    f = _fn(block_record, 'not_prime_ish')
    assert f.generated


def test_block_functions_run(block_record):
    sig = LanguageBridge()._sig_line
    for name, call, expect in [('sum_list', '[sum_list([1, 2, 3, 4])]', 10),
                               ('sum_to', '[sum_to(5)]', 15),
                               ('clamp', '[clamp(9, 1, 5)]', 5)]:
        f = _fn(block_record, name)
        assert interpret(sig(f) + '\n' + call)[0] == [expect], name


def test_block_module_fuse(block_record):
    assert LanguageBridge().fuse(block_record, write=False) is True


def test_flag_off_keeps_loop_skeleton():
    # 默认关闭 → 循环体仍走无中生有骨架（行为不变）
    rec = LanguageBridge().devour('python', _BLOCK_PY_SRC, 'flag_off_test')
    assert _fn(rec, 'sum_list').generated


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
