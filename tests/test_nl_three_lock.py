# -*- coding: utf-8 -*-
"""阶段 8b-3：NL 词法器+句法器 三锁（宿主加载 ↔ M3V VM 两路）。

三锁口径：
  ① 对拍：同一句子，宿主加载 nl_lexer/nl_parser 产的 token/语义框架 与
     VM 编译执行产的逐值一致（vm = host）。
  ② 闭环：NL 句子 → 词法 → 句法（语义框架）→ 自举解释器 求值 → 数值结果，
     宿主与 VM 两路均等于手算期望值。
  ③ 显式拒绝：歧义/超控制子集句子，宿主与 VM 两路均抛 MathaRuntimeError，
     错误文本一致（永不静默回退）。

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
               "matha/interp.matha", "matha/nl_lexer.matha", "matha/nl_parser.matha"]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_nl():
    """宿主加载 解释器（自举求值）+ 自然语言句法器（含词法器）。"""
    interp = Interpreter()
    assert interp.load_matha_module("解释器"), "加载 解释器 失败"
    assert interp.load_matha_module("自然语言句法器"), "加载 自然语言句法器 失败"
    return interp


@pytest.fixture(scope="module")
def vm_nl():
    """M3V VM：编译 核心 + NL 模块并运行，函数全局可调用。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _host_frame(interp, sentence):
    return interp._call_func_or_closure(interp.funcs["NL编译"], [sentence])


def _vm_frame(vm, sentence):
    return vm.call("NL编译", sentence)


def _host_eval(interp, frame):
    mod = interp.modules["解释器"]
    env = interp._call_func_or_closure(mod["注册内建"], [[]])
    return interp._call_func_or_closure(mod["求值"], [frame, env])


def _vm_eval(vm, frame):
    env = vm.call("注册内建", vm.call("空环境"))
    return vm.call("求值", frame, env)


# ---------- ① 对拍：词法 token 序列（vm = host） ----------

_LEX_SENTENCES = [
    "计算 三 加 五",
    "把 三 加上 五",
    "计算 三十 个苹果",
    "十五 加 二十",
]


@pytest.mark.parametrize("sentence", _LEX_SENTENCES)
def test_lex_tokens_parity(host_nl, vm_nl, sentence):
    host_tokens = host_nl._call_func_or_closure(host_nl.funcs["NL词法分析"], [sentence])
    vm_tokens = vm_nl.call("NL词法分析", sentence)
    assert host_tokens == vm_tokens, sentence


# ---------- ① 对拍：语义框架（vm = host） ----------

_FRAME_SENTENCES = [
    "计算 三 加 五",
    "把 三 加上 五",
    "五 减 三",
    "三 乘以 四",
    "六 除以 二",
    "计算 三十 个苹果",
    "三",
    "十五 加 二十",
]


@pytest.mark.parametrize("sentence", _FRAME_SENTENCES)
def test_frame_parity(host_nl, vm_nl, sentence):
    assert _host_frame(host_nl, sentence) == _vm_frame(vm_nl, sentence), sentence


# ---------- ② 闭环：句子 → 框架 → 求值 → 手算值（两路） ----------

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


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_closed_loop_host(host_nl, sentence, want):
    assert _host_eval(host_nl, _host_frame(host_nl, sentence)) == want, sentence


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_closed_loop_vm(vm_nl, sentence, want):
    assert _vm_eval(vm_nl, _vm_frame(vm_nl, sentence)) == want, sentence


@pytest.mark.parametrize("sentence,want", _CLOSED_LOOP)
def test_closed_loop_parity(host_nl, vm_nl, sentence, want):
    host_val = _host_eval(host_nl, _host_frame(host_nl, sentence))
    vm_val = _vm_eval(vm_nl, _vm_frame(vm_nl, sentence))
    assert host_val == vm_val == want, sentence


# ---------- ③ 显式拒绝：句法歧义/超子集（两路同文本） ----------

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
def test_rejection_host(host_nl, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        _host_frame(host_nl, sentence)


@pytest.mark.parametrize("sentence,match", _REJECTIONS)
def test_rejection_vm(vm_nl, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        _vm_frame(vm_nl, sentence)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))