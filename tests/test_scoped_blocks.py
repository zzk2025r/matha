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


# ---------- 四端一致：解释器 / MBC(VM) / 原生 exe ----------

def _vm(src):
    from src.mbc import compile_source, run_module
    return list(run_module(compile_source(src)))


def _parity(src: str) -> list[str]:
    """开启 SCOPED_BLOCKS 后，解释器与 MBC/VM 的输出必须逐项一致。"""
    features.set_feature(_ON, True)
    iv = [str(v) for v in interpret(src)[0]]
    vv = [str(v) for v in _vm(src)]
    assert iv == vv, f"解释器 {iv} != VM {vv}"
    return iv


def test_parity_top_level_bare_block():
    # 顶层裸块此前被解释器 _exec_decl 的兜底分支整块忽略（编译器照跑）
    assert _parity('y = 1\n{ y = 2 }\n[y]') == ["2"]


def test_parity_top_level_block_output_visible():
    assert _parity('y = 1\n{ 输出(9) }\n[y]') == ["9", "1"]


def test_parity_closure_sees_block_binding():
    # 闭包捕获 _matha_env，块内新建绑定此前不同步 → 解释器「未定义变量」
    src = ('func f() -> Int = () => {\n'
           '  base = 10\n'
           '  g = (x) => base + x\n'
           '  return g(5)\n'
           '}\n[f()]')
    assert _parity(src) == ["15"]


def test_parity_closure_sees_block_let():
    src = ('func f() -> Int = () => {\n'
           '  let base = 10\n'
           '  g = (x) => base + x\n'
           '  return g(5)\n'
           '}\n[f()]')
    assert _parity(src) == ["15"]


def test_parity_closure_sees_block_param():
    src = ('func f(b: Int) -> Int = (b) => {\n'
           '  g = (x) => b + x\n'
           '  return g(5)\n'
           '}\n[f(100)]')
    assert _parity(src) == ["105"]


def test_parity_block_tail_if_value():
    # 解释器此前「暂不支持求值: IfStmt」，MBC 侧 _emit_if_try_value 已支持
    src = ('func f(t: Int) -> Int = (t) => {\n'
           '  if t > 5 { 1 } else { 0 }\n'
           '}\n[f(10)]\n[f(1)]')
    assert _parity(src) == ["1", "0"]


def test_parity_if_else_branch_bindings():
    src = ('func g(k: Int) -> Int = (k) => '
           '{ if k == 1 { a = 100\n  return a } else { b = 200\n  return b } }\n'
           '[g(1)]\n[g(2)]')
    assert _parity(src) == ["100", "200"]


def test_parity_try_catch_binding():
    src = ('func f() -> Int = () => '
           '{ try { q = 1\n  throw("boom") } catch (e) { r = 2\n  return r } }\n[f()]')
    assert _parity(src) == ["2"]


def test_parity_double_nested_block():
    src = ('func f() -> Int = () => {\n'
           '  a = 1\n'
           '  {\n    b = 2\n    {\n      a = 99\n    }\n  }\n'
           '  return a\n}\n[f()]')
    assert _parity(src) == ["99"]


def test_parity_return_through_nested_block():
    src = 'func f() -> Int = () => {\n  {\n    return 42\n  }\n  return 0\n}\n[f()]'
    assert _parity(src) == ["42"]


def test_parity_break_through_nested_block():
    src = ('func f() -> Int = () => {\n'
           '  s = 0\n'
           '  while 真 {\n'
           '    s = s + 1\n'
           '    {\n      if s >= 3 { break }\n    }\n'
           '  }\n'
           '  return s\n'
           '}\n[f()]')
    assert _parity(src) == ["3"]


def test_parity_nested_lambda_capture():
    src = ('func f() -> Int = () => {\n'
           '  base = 10\n'
           '  g = (x) => { base + x }\n'
           '  return g(5)\n'
           '}\n[f()]')
    assert _parity(src) == ["15"]


def test_native_exe_parity(tmp_path):
    """原生 exe：同一源串产出与解释器一致的结果（第四端）。"""
    import subprocess

    from src.mbc import compile_source
    from src.mbc.native import emit_exe

    features.set_feature(_ON, True)
    src = ('func f(n: Int) -> Int = (n) => {\n'
           '  s = 0\n'
           '  while s < n { s = s + 1 }\n'
           '  return s\n'
           '}\n[f(5)]')
    iv = [str(v) for v in interpret(src)[0]]
    exe = tmp_path / "scoped_blocks.exe"
    exe.write_bytes(emit_exe(compile_source(src)))
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == iv


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
