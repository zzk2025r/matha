# -*- coding: utf-8 -*-
"""阶段 30c 双面错误文案对齐锁（boot 面 5 文件链 + 宿主面逐字对拍）。

Track B 摸底（#137）五组 boot_err 文案分歧收口：
  12 除零     「除零错误」→「除零错误: 1 / 0」（宿主 {l!r} / 0 同形）
  25 取模除零  boot % 落内层 / 误报「除零错误: 5 / 0」→「取模除零错误: 5 % 0」
  26 整除除零  boot 应用运算 无 // 路由「未知运算符: //」→「整除除零错误: 5 // 0」
              + 整除真化（Python floor 语义镜像：int/int→int、含浮点→float）
  28 不可调用  boot 应用函数 f[0] 直接探测对 Int 落 VM 下标错误
              「索引操作不支持: int[0]」→「不可调用的值: 5」（类型守卫前置）
  29 类型名    「索引操作不支持: Int[0]」→「int[0]」（host type().__name__
              小写面 _类型名 映射，读面/写面/父槽写三处同改）
判据：boot 面错误文案 == 宿主面错误文案 == golden expected 逐字；
附 % 负操作数语义对齐（截断→floor，Python 同语义）+ 整除值面双面相等。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src import ast_nodes as ast
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.kernel.errors import MathaRuntimeError
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]

_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


@pytest.fixture(scope="module")
def bootvm():
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


def _boot_err(bootvm, src):
    bootvm.call("输出清空")
    toks = bootvm.call("扫描", src, 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    for nm, ns in bootvm._chain_nss.items():
        env0 = bootvm.call("绑定环境", env0, nm, ns)
    try:
        bootvm.call("执行语句", prog, env0)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    raise AssertionError(f"期望报错但 boot 面通过: {src!r}")


def _host_err(src):
    try:
        host_interp.interpret(src)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    raise AssertionError(f"期望报错但宿主面通过: {src!r}")


# (golden 名, 源码, 期望文案) —— 期望取 golden_tests/expected/*.err 逐字
_ERRMSG_CASES = [
    ("12_error_div_zero", '输出("before")\n输出(1 / 0)',
     "MathaRuntimeError: 除零错误: 1 / 0"),
    ("25_error_mod_zero", '输出("before")\n输出(5 % 0)',
     "MathaRuntimeError: 取模除零错误: 5 % 0"),
    ("26_error_floordiv_zero", '输出("before")\n输出(5 // 0)',
     "MathaRuntimeError: 整除除零错误: 5 // 0"),
    ("28_error_call_noncallable", "x = 5\n输出(\"before\")\n输出(x())",
     "MathaRuntimeError: 不可调用的值: 5"),
    ("29_error_index_on_int", '输出("before")\n输出(5[0])',
     "MathaRuntimeError: 索引操作不支持: int[0]"),
]


@pytest.mark.parametrize("name,src,expected", _ERRMSG_CASES, ids=[c[0] for c in _ERRMSG_CASES])
def test_boot_err_text_matches_host_and_golden(bootvm, name, src, expected):
    b = _boot_err(bootvm, src)
    h = _host_err(src)
    assert b == expected, f"[{name}] boot 面文案分歧: {b!r}"
    assert h == expected, f"[{name}] 宿主面文案漂移: {h!r}"


def _boot_outs(bootvm, src):
    bootvm.call("输出清空")
    toks = bootvm.call("扫描", src, 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    for nm, ns in bootvm._chain_nss.items():
        env0 = bootvm.call("绑定环境", env0, nm, ns)
    r, _env1 = bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照"))


def _host_outs(src):
    outs, _trace = host_interp.interpret(src)
    return outs


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


# 整除真化值面（Python floor 语义镜像）+ % 负操作数语义对齐（截断→floor）
_FLOORDIV_MOD_CASES = [
    ("输出(7 // 2)", 3.0),
    ("输出(-7 // 2)", -4.0),
    ("输出(7.5 // 2)", 3.0),
    ("输出(7 % 3)", 1.0),
    ("输出(-7 % 2)", 1.0),
    ("输出(7 % -2)", -1.0),
]


@pytest.mark.parametrize("src,want", _FLOORDIV_MOD_CASES)
def test_floordiv_mod_value_parity(bootvm, src, want):
    b = _boot_outs(bootvm, src)
    h = _host_outs(src)
    assert _norm(b) == _norm(h) == [want], f"{src!r}: boot={b!r} host={h!r}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
