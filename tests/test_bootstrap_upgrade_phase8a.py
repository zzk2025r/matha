# -*- coding: utf-8 -*-
"""阶段 8a：Matha 自举能力真实升级的行为级三锁（手算对拍 / 闭环 / 显式拒绝）。

覆盖：
  8a-1  stdlib ord_matha/chr_matha 委托宿主/VM/原生三端共有的真实 Unicode
        原语（旧 ASCII 查表占位对非 ASCII 静默返回 -1，已清除）；
  8a-2  纯 Matha list_map/list_fold（不委托宿主 映射 内建，自举链可用）；
  8a-3  两条自举解释器链（mb=interp_matha.matha / fresh=interp.matha）与
        M3V VM（宿主编译 interp.matha）的 match 求值：守卫先于模式、
        通配符 _ 兜底、变量绑定不泄漏、构造子列表/字典两形态、
        无匹配显式拒绝。

源码级用例避开自举解释器预先存在的列表/字典字面量求值缺口
（docs/KNOWN_ISSUES.md 登记）；构造子用例走 AST 级 + 预绑定 env，
真实经过 求值match→匹配构造子 全链。

注：本文件真实加载/编译 Matha 核心模块（约数十秒），fixture 均为模块级只建一次。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.matha_bootstrap as mb
from src.interp import Interpreter, MathaRuntimeError
from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]


def _read_matha(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("﻿") if src.startswith("﻿") else src


@pytest.fixture(scope="module")
def mb_boot():
    interp = mb._get_interp()
    if not getattr(interp, "_matha_loaded", False):
        pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
    return interp


@pytest.fixture(scope="module")
def fresh_boot():
    interp = Interpreter()
    assert interp.load_matha_module("解释器")
    assert "预绑定函数" in interp.modules["解释器"], "应为 interp.matha 版"
    return interp


@pytest.fixture(scope="module")
def stdlib_vm():
    comp = Compiler()
    test_src = (
        "func 测试映射() -> List = list_map([1, 2, 3], (x) => x * 2)\n"
        "func 测试折叠() -> Int = list_fold([1, 2, 3, 4], 0, (a, b) => a + b)\n"
        "func 测试码点() -> Int = ord_matha(\"中\")\n"
        "func 测试字符() -> String = chr_matha(20013)\n"
        "func 测试表情码点() -> Int = ord_matha(\"🚀\")\n"
        "func 测试表情字符() -> String = chr_matha(128640)\n"
        "func 测试空映射() -> List = list_map([], (x) => x * 2)\n"
        "func 测试空折叠() -> Int = list_fold([], 42, (a, b) => a + b)\n"
        "func 测试映射折叠闭环() -> Int = list_fold(list_map([1, 2, 3], (x) => x * x), 0, (a, b) => a + b)\n"
        "func 测试折叠顺序() -> Int = list_fold([1, 2, 3], 0, (a, b) => a * 10 + b)\n"
        "func 测试多字符拒绝() -> Int = ord_matha(\"ab\")\n"
        "func 测试越界拒绝() -> String = chr_matha(-1)\n"
    )
    decls = list(py_parse(_read_matha("matha/stdlib.matha")).decls)
    decls += list(py_parse(test_src).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def interp_vm():
    comp = Compiler()
    decls = []
    for rel in ("matha/lexer.matha", "matha/stdlib.matha",
                "matha/parser.matha", "matha/interp.matha"):
        decls.extend(py_parse(_read_matha(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _run_source(interp, src):
    toks = interp.call("扫描", src, 0, 1, 1, [])
    ast_d = interp.call("parse", toks)
    mod = interp.modules["解释器"]
    env = interp._call_func_or_closure(mod["注册内建"], [[]])
    result, _ = interp._call_func_or_closure(mod["执行语句"], [ast_d, env])
    return result


def _call3(interp, mod, fn, *args):
    return interp._call_func_or_closure(mod[fn], list(args))


def _run_constructor_ast(interp, value):
    """AST 级构造子 match：scrutinee 为预绑定变量 v；Some(x) => x+1，_ => 99。"""
    mod = interp.modules["解释器"]
    env = _call3(interp, mod, "注册内建", [])
    env = _call3(interp, mod, "绑定环境", env, "v", value)
    pmod = interp.modules["语法器"]
    pat = _call3(interp, pmod, "做构造子模式", "Some",
                 [_call3(interp, pmod, "做Variable", "x")])
    body = _call3(interp, pmod, "做BinaryOp", "+",
                  _call3(interp, pmod, "做Variable", "x"),
                  _call3(interp, pmod, "做IntLit", 1))
    wild = _call3(interp, pmod, "做Variable", "_")
    dft = _call3(interp, pmod, "做IntLit", 99)
    m = _call3(interp, pmod, "做Match", _call3(interp, pmod, "做Variable", "v"),
               [[pat, None, body], [wild, None, dft]])
    return _call3(interp, mod, "求值", m, env)


def _run_host_outputs(src):
    interp = Interpreter()
    interp.run(py_parse(src))
    return interp.outputs


# ---------- 8a-1：ord/chr Unicode 真实接通（手算对拍 + 显式拒绝） ----------

def test_ord_chr_unicode_host():
    """宿主链：ord/chr 对中文/emoji 往返真实（手算：中=20013，🚀=128640）。"""
    out = _run_host_outputs(
        "use 标准库\n"
        "输出(标准库.ord_matha(\"中\"))\n"
        "输出(标准库.chr_matha(20013))\n"
        "输出(标准库.ord_matha(\"🚀\"))\n"
        "输出(标准库.chr_matha(128640))\n"
        "输出(len(\"中文abc\"))\n")
    assert out == [20013, "中", 128640, "🚀", 5], out


def test_ord_chr_unicode_vm(stdlib_vm):
    """M3V VM：同一 stdlib 源码编译后 ord/chr 结果与宿主手算一致。"""
    assert stdlib_vm.call("测试码点") == 20013
    assert stdlib_vm.call("测试字符") == "中"
    assert stdlib_vm.call("测试表情码点") == 128640
    assert stdlib_vm.call("测试表情字符") == "🚀"


def test_ord_rejects_non_single_char_host():
    """显式拒绝：多字符/空串不再静默返回 -1（旧 ASCII 占位行为）。"""
    for bad in ('"ab"', '""'):
        with pytest.raises(MathaRuntimeError, match="单字符"):
            _run_host_outputs("use 标准库\n输出(标准库.ord_matha(" + bad + "))")


def test_chr_rejects_out_of_range_host():
    """显式拒绝：码点越界抛 ValueError（Python chr 原语真实拒绝）。"""
    for bad in ("-1", "1114112"):
        with pytest.raises(ValueError, match="range"):
            _run_host_outputs("use 标准库\n输出(标准库.chr_matha(" + bad + "))")


def test_ord_chr_reject_vm(stdlib_vm):
    """显式拒绝（VM）：ord 多字符 TypeError、chr 越界 ValueError，均不静默。"""
    with pytest.raises(TypeError):
        stdlib_vm.call("测试多字符拒绝")
    with pytest.raises(ValueError, match="range"):
        stdlib_vm.call("测试越界拒绝")


# ---------- 8a-2：纯 Matha list_map/list_fold（对拍 + 闭环 + 边界） ----------

def test_list_map_fold_host():
    """宿主链：map 双倍 [2,4,6]、fold 求和 10、空表边界 []/42（手算）。"""
    out = _run_host_outputs(
        "use 标准库\n"
        "输出(标准库.list_map([1, 2, 3], (x) => x * 2))\n"
        "输出(标准库.list_fold([1, 2, 3, 4], 0, (a, b) => a + b))\n"
        "输出(标准库.list_map([], (x) => x * 2))\n"
        "输出(标准库.list_fold([], 42, (a, b) => a + b))\n")
    assert out == [[2, 4, 6], 10, [], 42], out


def test_list_map_fold_vm(stdlib_vm):
    """M3V VM：map/fold 与宿主手算一致，空表边界一致。"""
    assert stdlib_vm.call("测试映射") == [2, 4, 6]
    assert stdlib_vm.call("测试折叠") == 10
    assert stdlib_vm.call("测试空映射") == []
    assert stdlib_vm.call("测试空折叠") == 42


def test_list_map_fold_closed_loop_host():
    """闭环：map∘fold 组合（平方和 1²+2²+3²=14）；左折叠顺序锁 123。"""
    out = _run_host_outputs(
        "use 标准库\n"
        "输出(标准库.list_fold(标准库.list_map([1, 2, 3], (x) => x * x), 0, (a, b) => a + b))\n"
        "输出(标准库.list_fold([1, 2, 3], 0, (a, b) => a * 10 + b))\n")
    assert out == [14, 123], out


def test_list_map_fold_closed_loop_vm(stdlib_vm):
    """闭环（VM）：组合与折叠顺序同宿主手算。"""
    assert stdlib_vm.call("测试映射折叠闭环") == 14
    assert stdlib_vm.call("测试折叠顺序") == 123


# ---------- 8a-3：match 两自举链 + VM（对拍 / 闭环 / 显式拒绝） ----------

_MATCH_SRC_CASES = [
    ('match 3 {\n| 1 => 10\n| 3 => 30\n| _ => 99\n}', 30),
    ('match 9 {\n| 1 => 10\n| _ => 99\n}', 99),
    ('match 5 {\n| x => x + 1\n}', 6),
    ('match 5 {\n| 1 => 10\n| _ if 5 > 3 => 20\n| _ => 30\n}', 20),
    ('match 9 {\n| 1 => 10\n| _ if 假 => 20\n| _ => 30\n}', 30),
    ('match "中" {\n| "中" => 1\n| _ => 2\n}', 1),
    ('match 2.5 {\n| 2.5 => 7\n| _ => 0\n}', 7),
    ('match 真 {\n| 真 => 1\n| 假 => 0\n}', 1),
]


@pytest.mark.parametrize("src,want", _MATCH_SRC_CASES)
def test_match_source_mb_chain(mb_boot, src, want):
    """mb 链（interp_matha.matha）：字面量/兜底/绑定/守卫/Unicode/浮点/布尔。"""
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _MATCH_SRC_CASES)
def test_match_source_fresh_chain(fresh_boot, src, want):
    """fresh 链（interp.matha）：同上用例集，两链语义一致。"""
    assert _run_source(fresh_boot, src) == want, src


_CTOR_CASES = [
    (["Some", 5], 6),
    ({"Some": [5]}, 6),
    (["Other", 5], 99),
    ({"Other": [5]}, 99),
    (["Some", 5, 6], 99),   # 字段数不符
    ({"Some": 5}, 99),      # 字典值非列表
    ("Some", 99),           # 字符串不匹配构造子
]


@pytest.mark.parametrize("value,want", _CTOR_CASES)
def test_match_constructor_mb_chain(mb_boot, value, want):
    """mb 链构造子：列表/字典两形态命中与拒绝（AST 级全链）。"""
    assert _run_constructor_ast(mb_boot, value) == want, value


@pytest.mark.parametrize("value,want", _CTOR_CASES)
def test_match_constructor_fresh_chain(fresh_boot, value, want):
    """fresh 链构造子：同 mb 链用例集。"""
    assert _run_constructor_ast(fresh_boot, value) == want, value


def test_match_no_match_rejected_mb(mb_boot):
    """显式拒绝（mb）：无匹配分支抛错，不静默返回 null。"""
    with pytest.raises(MathaRuntimeError, match="match 无匹配分支"):
        _run_source(mb_boot, 'match 7 {\n| 1 => 10\n}')


def test_match_no_match_rejected_fresh(fresh_boot):
    """显式拒绝（fresh）：同上。"""
    with pytest.raises(MathaRuntimeError, match="match 无匹配分支"):
        _run_source(fresh_boot, 'match 7 {\n| 1 => 10\n}')


def test_match_binding_no_leak_mb(mb_boot):
    """绑定不泄漏（mb）：match 分支绑定的 x 在 match 外不可见。"""
    with pytest.raises(MathaRuntimeError, match="未定义变量 'x'"):
        _run_source(mb_boot, 'match 5 {\n| x => x + 1\n}\nx')


def test_match_binding_no_leak_fresh(fresh_boot):
    """绑定不泄漏（fresh）：同上。"""
    with pytest.raises(MathaRuntimeError, match="未定义变量 'x'"):
        _run_source(fresh_boot, 'match 5 {\n| x => x + 1\n}\nx')


def test_match_vm_literals_and_binding(interp_vm):
    """M3V VM（编译 interp.matha）：字面量命中 30、变量绑定 x+1=6。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    branches = [[interp_vm.call("做IntLit", 1), None, interp_vm.call("做IntLit", 10)],
                [interp_vm.call("做IntLit", 3), None, interp_vm.call("做IntLit", 30)],
                [interp_vm.call("做Variable", "_"), None, interp_vm.call("做IntLit", 99)]]
    m = interp_vm.call("做Match", interp_vm.call("做IntLit", 3), branches)
    assert interp_vm.call("求值", m, env) == 30
    body = interp_vm.call("做BinaryOp", "+", interp_vm.call("做Variable", "x"),
                          interp_vm.call("做IntLit", 1))
    m2 = interp_vm.call("做Match", interp_vm.call("做IntLit", 5),
                        [[interp_vm.call("做Variable", "x"), None, body]])
    assert interp_vm.call("求值", m2, env) == 6


def test_match_vm_constructor_list_and_dict(interp_vm):
    """M3V VM 构造子：列表 ['Some',5] 与字典 {'Some':[5]} 均命中 x+1=6，
    异名 {'Other':[5]} 落兜底 99（安全索引缺键路径）。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    body = interp_vm.call("做BinaryOp", "+", interp_vm.call("做Variable", "x"),
                          interp_vm.call("做IntLit", 1))
    pat = interp_vm.call("做构造子模式", "Some", [interp_vm.call("做Variable", "x")])
    branches = [[pat, None, body],
                [interp_vm.call("做Variable", "_"), None, interp_vm.call("做IntLit", 99)]]
    for value, want in ((["Some", 5], 6), ({"Some": [5]}, 6), ({"Other": [5]}, 99)):
        env_v = interp_vm.call("绑定环境", env, "v", value)
        m = interp_vm.call("做Match", interp_vm.call("做Variable", "v"), branches)
        assert interp_vm.call("求值", m, env_v) == want, value


def test_match_vm_no_match_rejected(interp_vm):
    """显式拒绝（VM）：无匹配分支抛 MathaRuntimeError。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    m = interp_vm.call("做Match", interp_vm.call("做IntLit", 7),
                       [[interp_vm.call("做IntLit", 1), None, interp_vm.call("做IntLit", 10)]])
    with pytest.raises(MathaRuntimeError, match="match 无匹配分支"):
        interp_vm.call("求值", m, env)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))