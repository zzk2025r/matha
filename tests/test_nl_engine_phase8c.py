# -*- coding: utf-8 -*-
"""阶段 8c：NL 执行引擎（语义转换 + 执行）三锁 + 混合引擎零冲突锁。

三锁口径：
  ① 对拍：同一句子经 自然语言执行器 NL执行（宿主加载 ↔ M3V VM 编译两路）
     产出的结果逐值一致（vm = host）；内建 自然语言执行 两路亦一致。
  ② 闭环：句子 → 词法 → 句法（语义框架）→ 自举解释器 求值 → 结果值，
     宿主/VM 直接调用、宿主/VM 内建入口均等于手算期望值；
     Matha 源码层 输出(自然语言执行(...)) 亦可产出同一结果。
  ③ 显式拒绝：歧义/超控制子集句子，宿主/VM、直接/内建四条链均抛
     MathaRuntimeError 且错误文本一致；VM 链未编译时内建显式
     RuntimeError（永不静默回退）。
零冲突锁（阶段 8c 核心口径）：新内建为独立命名（自然语言执行），与既有
  混合编译/混合诊断/混合执行/转译语言 同解释器共存互不干扰（现有接口
  一字未动）；内建名 ≠ Matha 函数名（NL执行），无 VM 全局遮蔽；
  引擎调用本身零散输出、无环境泄漏。

fixture 模块级只建一次（真实加载/编译 Matha 核心 + NL 模块）。零跳过，零失败。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import Interpreter
from src.kernel.errors import MathaRuntimeError
from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/nl_lexer.matha", "matha/nl_parser.matha",
               "matha/nl_engine.matha"]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_engine():
    """宿主：加载 自然语言执行器（use 传递加载 词法/句法/解释器链）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言执行器"), "加载 自然语言执行器 失败"
    interp.outputs.clear()
    return interp


@pytest.fixture(scope="module")
def vm_engine():
    """M3V VM：编译 核心 + NL 词法/句法/执行器 模块并运行。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def vm_empty():
    """未编译 NL 链的空 VM（内建显式拒绝路径）。"""
    comp = Compiler()
    comp.compile_program(ast.Program(decls=[]))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _host_run(interp, sentence):
    return interp._call_func_or_closure(interp.funcs["NL执行"], [sentence])


# ---------- ① 对拍：引擎结果（vm = host，直接调用） ----------

_CLOSED_LOOP = [
    ("计算 三 加 五", 8),
    ("把 三 加上 五", 8),
    ("五 减 三", 2),
    ("三 乘以 四", 12),
    ("六 除以 二", 3.0),
    ("计算 三十 个苹果", 30),
    ("十五 加 二十", 35),
    ("三", 3),
]


@pytest.mark.parametrize("sentence,_want", _CLOSED_LOOP, ids=lambda v: v if isinstance(v, str) else "")
def test_engine_parity(host_engine, vm_engine, sentence, _want):
    assert _host_run(host_engine, sentence) == vm_engine.call("NL执行", sentence), sentence


# ---------- ① 对拍：内建入口（vm = host） ----------


@pytest.mark.parametrize("sentence,_want", _CLOSED_LOOP, ids=lambda v: v if isinstance(v, str) else "")
def test_builtin_parity(host_engine, vm_engine, sentence, _want):
    host_val = host_engine.call("自然语言执行", sentence)
    vm_val = vm_engine.call("自然语言执行", sentence)
    assert host_val == vm_val, sentence


# ---------- ② 闭环：手算值（直接调用两路） ----------


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_engine_closed_loop_host(host_engine, sentence, want):
    assert _host_run(host_engine, sentence) == want, sentence


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_engine_closed_loop_vm(vm_engine, sentence, want):
    assert vm_engine.call("NL执行", sentence) == want, sentence


# ---------- ② 闭环：内建入口（宿主/VM） + 源码层 ----------


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_builtin_closed_loop_host(host_engine, sentence, want):
    assert host_engine.call("自然语言执行", sentence) == want, sentence


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_builtin_closed_loop_vm(vm_engine, sentence, want):
    assert vm_engine.call("自然语言执行", sentence) == want, sentence


def test_builtin_lazy_load_host():
    """宿主内建无需预加载：首次调用自行加载 自然语言执行器 模块链。"""
    interp = Interpreter()
    assert "自然语言执行器" not in interp.modules
    assert interp.call("自然语言执行", "计算 三 加 五") == 8
    assert "自然语言执行器" in interp.modules


def test_source_level_host():
    """Matha 源码层 输出(自然语言执行(...)) → 输出流末位为结果值（宿主）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言执行器")
    interp.outputs.clear()
    interp.run(py_parse('输出(自然语言执行("计算 三 加 五"))'))
    assert interp.outputs[-1] == 8


def test_source_level_vm():
    """Matha 源码层 输出(自然语言执行(...)) → 输出流末位为结果值（VM）。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    decls.extend(py_parse('输出(自然语言执行("三 加 五"))').decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    assert vm.outputs[-1] == 8


# ---------- ③ 显式拒绝：歧义/超子集（四条链同文本） ----------

_REJECTIONS = [
    ("三 五", "句式歧义：连续数词缺少运算符"),
    ("三 加", "句式不完整：运算符缺少数词"),
    ("三 加 五 乘 二", "超出控制子集的句式"),
    ("计算", "句式不完整：缺少数词"),
    ("加 五", "句式歧义：期望数词"),
    ("三 加 苹果", "句式歧义：运算符后期望数词"),
    # 词法层拒绝（未知词）经 NL编译 传导
    ("计算 神经网络", "超出控制子集的词"),
]


@pytest.mark.parametrize("sentence,match", _REJECTIONS)
def test_rejection_parity(host_engine, vm_engine, sentence, match):
    """直接调用两路同抛 MathaRuntimeError 且错误文本一致。"""
    with pytest.raises(MathaRuntimeError) as he:
        _host_run(host_engine, sentence)
    with pytest.raises(MathaRuntimeError) as ve:
        vm_engine.call("NL执行", sentence)
    assert str(he.value) == str(ve.value), sentence
    assert match in str(he.value), sentence


@pytest.mark.parametrize("sentence,match", _REJECTIONS)
def test_rejection_builtin_host(host_engine, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        host_engine.call("自然语言执行", sentence)


@pytest.mark.parametrize("sentence,match", _REJECTIONS)
def test_rejection_builtin_vm(vm_engine, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        vm_engine.call("自然语言执行", sentence)


def test_rejection_vm_uncompiled(vm_empty):
    """VM 链未编译：内建显式 RuntimeError，永不静默回退。"""
    with pytest.raises(RuntimeError, match="未编译"):
        vm_empty.call("自然语言执行", "计算 三 加 五")


# ---------- ④ 零冲突锁：独立命名内建与既有混合接口共存 ----------


def test_zero_conflict_hybrid_builtins_coexist(host_engine):
    """NL 执行调用后，既有 混合编译/混合诊断/混合执行/转译语言 在同一
    解释器实例上行为不变（8c 未改任何既有混合接口）。"""
    assert host_engine.call("自然语言执行", "计算 三 加 五") == 8
    build = host_engine.call("混合编译", "测试任务", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(build, dict)
    diag = host_engine.call("混合诊断", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(diag, dict)
    trans = host_engine.call("转译语言", "func 加倍(x) -> Int = (x) => x * 2", "python")
    assert isinstance(trans, dict)


def test_zero_conflict_no_shadowing(host_engine):
    """内建名（自然语言执行）≠ Matha 函数名（NL执行）：宿主双表分离、
    VM 单全局表无重名遮蔽；两入口同句结果一致。"""
    assert "自然语言执行" in host_engine.builtins
    assert "NL执行" in host_engine.funcs
    assert "自然语言执行" not in host_engine.funcs
    assert host_engine.call("自然语言执行", "五 减 三") == _host_run(host_engine, "五 减 三") == 2


def test_zero_conflict_no_stray_output(host_engine):
    """引擎调用本身零散输出：预加载后清空输出流，调用不产生任何输出。"""
    before = len(host_engine.outputs)
    assert host_engine.call("自然语言执行", "三 乘以 四") == 12
    assert len(host_engine.outputs) == before


def test_zero_conflict_stateless(host_engine):
    """引擎无状态：连续调用互不泄漏（环境每次重建，结果只由句子决定）。"""
    assert host_engine.call("自然语言执行", "计算 三 加 五") == 8
    assert host_engine.call("自然语言执行", "五 减 三") == 2
    assert host_engine.call("自然语言执行", "计算 三 加 五") == 8


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
