# -*- coding: utf-8 -*-
"""SCOPED_BLOCKS 特性开关测试（`{ }` 代码块作为语句上下文）。

默认关闭：现有行为保持不变；开启后 lambda 体 `{ }` 成为真正的语句块，
块内 `名 = 值` 解析为绑定并拥有独立子作用域，原生支持多语句与 for/while 循环累加。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features
from src.interp import MathaRuntimeError, interpret

_ON = "SCOPED_BLOCKS"


@pytest.fixture(autouse=True)
def _isolate_flags():
    """隔离：测试期间移除外部环境变量，保证「默认状态」可被确定地断言。"""
    keys = ("MATHA_FEATURE_SCOPED_BLOCKS", "MATHA_FEATURES")
    saved = {k: os.environ.pop(k, None) for k in keys}
    features.clear_feature()
    try:
        yield
    finally:
        features.clear_feature()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def _out(src):
    return interpret(src)[0]


# ---------- 开关解析 ----------

def test_default_off():
    assert features.scoped_blocks() is False


def test_env_var_enables(monkeypatch):
    monkeypatch.setenv("MATHA_FEATURE_SCOPED_BLOCKS", "1")
    assert features.scoped_blocks() is True
    monkeypatch.setenv("MATHA_FEATURE_SCOPED_BLOCKS", "off")
    assert features.scoped_blocks() is False


def test_features_listing_enables(monkeypatch):
    monkeypatch.setenv("MATHA_FEATURES", "foo, scoped_blocks")
    assert features.scoped_blocks() is True


def test_override_beats_env(monkeypatch):
    monkeypatch.setenv("MATHA_FEATURE_SCOPED_BLOCKS", "1")
    features.set_feature(_ON, False)
    assert features.scoped_blocks() is False


# ---------- 关闭：行为不变（旧语义） ----------

def test_off_block_binding_is_equality():
    # 关闭时 lambda 体内块语句 `y = x + 1` 为等于比较 → y 未定义
    with pytest.raises(MathaRuntimeError):
        interpret('func f(x: Int) -> Int = (x) => { y = x + 1\n y * 2 }\n[f(3)]')


# ---------- 开启：语句块语义 ----------

def test_on_block_binding():
    features.set_feature(_ON, True)
    assert _out('func f(x: Int) -> Int = (x) => { y = x + 1\n y * 2 }\n[f(3)]') == [8]


def test_on_for_loop_accumulation():
    features.set_feature(_ON, True)
    src = 'func f() -> Int = () => { s = 0\n for i in [1, 2, 3] { s = s + i }\n s }\n[f()]'
    assert _out(src) == [6]


def test_on_while_loop_accumulation():
    features.set_feature(_ON, True)
    src = 'func f(n: Int) -> Int = (n) => { s = 0\n while s < n { s = s + 1 }\n s }\n[f(5)]'
    assert _out(src) == [5]


def test_on_multi_statement():
    features.set_feature(_ON, True)
    src = 'func f(x: Int) -> Int = (x) => { a = x + 1\n b = a * 2\n b - a }\n[f(3)]'
    assert _out(src) == [4]


def test_on_block_isolation_no_leak():
    features.set_feature(_ON, True)
    src = ("var y = 1\n"
           "func g() -> Int = () => { y = 2\n y }\n"
           "[g()]\n"
           "[y]")
    assert _out(src) == [2, 1]


# ---------- return / break / continue（块内语句） ----------

def test_return_value():
    features.set_feature(_ON, True)
    assert _out('func f(x: Int) -> Int = (x) => { return x * 2 }\n[f(3)]') == [6]


def test_early_return():
    features.set_feature(_ON, True)
    src = ('func f(x: Int) -> Int = (x) => {\n'
           '  if x < 0 { return 0 }\n'
           '  return x * 2\n'
           '}\n[f(-5)]\n[f(5)]')
    assert _out(src) == [0, 10]


def test_break_in_while():
    features.set_feature(_ON, True)
    src = ('func f() -> Int = () => {\n'
           '  s = 0\n'
           '  while 真 {\n'
           '    s = s + 1\n'
           '    if s >= 3 { break }\n'
           '  }\n'
           '  return s\n'
           '}\n[f()]')
    assert _out(src) == [3]


def test_continue_in_for():
    features.set_feature(_ON, True)
    src = ('func f() -> Int = () => {\n'
           '  s = 0\n'
           '  for i in [1, 2, 3, 4] {\n'
           '    if i % 2 == 0 { continue }\n'
           '    s = s + i\n'
           '  }\n'
           '  return s\n'
           '}\n[f()]')
    assert _out(src) == [4]          # 1 + 3


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
