# -*- coding: utf-8 -*-
"""M3V 自举闭环测试：Matha 词法器 + 语法器（编译为字节码）在 VM 上运行，
完成「Matha 源码 → token → AST」全流程——编译基础设施自举的关键里程碑。

验证要点：
  - lexer.matha / stdlib.matha / parser.matha 可共同编译为字节码
  - VM 上 Matha tokenize 产出正确 token（类型/文本/行列）
  - VM 上 Matha parse 产出正确 AST（运算符优先级、带类型标注函数定义等）
  - and/or 短路语义在字节码层正确（数字/空白判定依赖）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)
# 注意：不要在此提高 sys.setrecursionlimit——VM 使用显式帧栈，深递归不占
# Python C 栈；过高的递归限制会把其他模块的 RecursionError 放大成 C 栈崩溃。

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha"]


@pytest.fixture(scope="module")
def boot_vm():
    comp = Compiler()
    for rel in _BOOT_FILES:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        if src and src[0] == "﻿":
            src = src.lstrip("﻿")
        comp.compile_program(py_parse(src))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _parse_on_vm(vm, code):
    toks = vm.call("tokenize", code)
    tree = vm.call("parse", toks)
    return toks, tree


# ---------- 词法器 ----------

def test_lexer_tokens(boot_vm):
    toks = boot_vm.call("tokenize", "1 + 2 * 3")
    pairs = [(t["类型"], t["文本"]) for t in toks]
    assert pairs == [
        ("整数", "1"), ("加", "+"), ("整数", "2"),
        ("乘", "*"), ("整数", "3"), ("结束", ""),
    ]


def test_lexer_skips_whitespace_and_classifies_identifiers(boot_vm):
    toks = boot_vm.call("tokenize", "func add(a: Int) -> Int")
    types = [t["类型"] for t in toks]
    assert types[0] == "关键字" and types[0] is not None
    assert types[1] == "标识符"
    assert types[-1] == "结束"
    # 空白不得产出 token
    assert all(t["文本"] != " " for t in toks)


# ---------- 语法器：表达式与优先级 ----------

def test_parse_arith_precedence(boot_vm):
    _, tree = _parse_on_vm(boot_vm, "1 + 2 * 3")
    assert tree["类型"] == "程序"
    decls = tree["声明"]
    assert len(decls) == 1
    expr = decls[0]
    assert expr["类型"] == "二元运算"
    assert expr["运算符"] == "+"
    # 乘法应绑定更紧：右孩子是 2 * 3
    assert expr["右"]["类型"] == "二元运算"
    assert expr["右"]["运算符"] == "*"
    assert expr["左"]["值"] == 1


def test_parse_let_binding(boot_vm):
    _, tree = _parse_on_vm(boot_vm, "let x = 42")
    decls = tree["声明"]
    assert len(decls) == 1


# ---------- 语法器：带参数类型标注的函数定义 ----------

def test_parse_func_def_with_typed_params(boot_vm):
    _, tree = _parse_on_vm(
        boot_vm, "func add(a: Int, b: Int) -> Int = (a, b) => a + b"
    )
    decls = tree["声明"]
    assert len(decls) == 1
    fn = decls[0]
    assert fn["类型"] == "函数定义"
    assert fn.get("名") == "add" or fn.get("名称") == "add"


def test_parse_func_def_with_if_expr_body(boot_vm):
    _, tree = _parse_on_vm(
        boot_vm, "func f(x: Int) -> Int = (x) => if x > 0 then x else 0 - x"
    )
    decls = tree["声明"]
    assert len(decls) == 1
    assert decls[0]["类型"] == "函数定义"


# ---------- 字节码语义：and/or 短路 ----------

def test_short_circuit_and_or():
    from src.mbc import compile_source, run_module
    # 若 and/or 不短路，右侧 get("x")(99) 越界取值会直接抛 IndexError
    outs = run_module(compile_source(
        'result = (1 > 2) and (get("x")(99) = "y")\n#1：[result]'))
    assert outs[-1] is False

    outs = run_module(compile_source(
        'result = (1 < 2) or (get("x")(99) = "y")\n#1：[result]'))
    assert outs[-1] is True
