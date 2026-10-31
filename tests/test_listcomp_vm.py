# -*- coding: utf-8 -*-
"""A 方案：列表推导 VM 编译补全的功能 + 边界 + 三端平价锁。

承接 B+C（此前 ListComp 在 VM 编译期显式报错）。本文件把语义反转回「支持」，
并以 **interp 引擎为预言机**逐值对拍，边界覆盖：空迭代、单 if、多 if(AND)、
全滤除、字符串迭代、range 迭代、嵌套推导、表达式内含函数调用、函数返回位、
作实参位。黄金用例 `35_list_comp` 另锁 vm ↔ interp ↔ native 逐字节。
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import features  # noqa: E402
from src.kernel import exec_api  # noqa: E402


def _vm(src: str) -> list:
    features.set_feature("SCOPED_BLOCKS", True)
    outs, err = exec_api.run_checked(src, mode="vm")
    features.clear_feature()
    if err is not None:
        raise err
    return list(outs)


def _interp(src: str) -> list:
    """预言机：树走式解释器（黄金 expected 同源），已实现 _eval_list_comprehension。"""
    from src.interp import Interpreter
    from src.parser import parse
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse(src))
    return list(ip.outputs)


# 每种形态：源码 + interp 预言机给定的正确值（[[...]] 外层为输出命令收集）
CASES = {
    "basic":      ("nums = [1, 2, 3, 4]\n[ [x * x for x in nums] ]", [[1, 4, 9, 16]]),
    "empty_iter": ("nums = []\n[ [x * x for x in nums] ]", [[]]),
    "single_if":  ("nums = [1, 2, 3, 4, 5]\n[ [x for x in nums if x > 3] ]", [[4, 5]]),
    "multi_if_and": ("nums = [1, 2, 3, 4, 5, 6]\n[ [x for x in nums if x > 2 if x < 5] ]", [[3, 4]]),
    "no_match":   ("nums = [1, 2, 3]\n[ [x for x in nums if x > 99] ]", [[]]),
    "str_iter":   ('w = "abc"\n[ [c for c in w] ]', [["a", "b", "c"]]),
    "range_iter": ("[ [x * 10 for x in range(1, 4)] ]", [[10, 20, 30]]),
    "nested":     ("m = [[1, 2], [3, 4]]\n[ [[y * 2 for y in row] for row in m] ]", [[[2, 4], [6, 8]]]),
    "funcall_expr": ("nums = [1, 2, 3]\n[ [abs(0 - x) for x in nums] ]", [[1, 2, 3]]),
}


@pytest.mark.parametrize("key", list(CASES))
def test_vm_listcomp_values(key):
    """VM 编译补全：各形态输出等于预言机确定的正确值。"""
    src, expected = CASES[key]
    assert _vm(src) == expected, key


@pytest.mark.parametrize("key", list(CASES))
def test_vm_matches_interp_oracle(key):
    """跨后端值平价：VM ↔ interp 逐值一致（补全不得偏离遗留语义）。"""
    src, _ = CASES[key]
    assert _vm(src) == _interp(src), key


def test_listcomp_in_function_return():
    """边界：推导作函数返回表达式（局部槽绑定 target，非全局泄漏）。"""
    src = ("func 平方表(n: Int) -> List = (n) => { return [x * x for x in range(1, n + 1)] }\n"
           "[ 平方表(5) ]")
    assert _vm(src) == [[1, 4, 9, 16, 25]]
    assert _vm(src) == _interp(src)


def test_listcomp_as_argument():
    """边界：推导作实参传入函数（表达式位置留栈平衡）。"""
    src = ("nums = [1, 2, 3]\n"
           "func 首(e: List) -> Any = (e) => { return e[0] }\n"
           "[ 首([x * 100 for x in nums]) ]")
    assert _vm(src) == [100]
    assert _vm(src) == _interp(src)


def test_two_comps_same_scope_temp_no_clash():
    """边界：同一作用域内两次推导，临时槽/目标变量不互相串味。"""
    src = ("a = [1, 2, 3]\n"
           "b = [10, 20]\n"
           "[ [x + 1 for x in a] ]\n"
           "[ [y * 2 for y in b] ]")
    assert _vm(src) == [[2, 3, 4], [20, 40]]
    assert _vm(src) == _interp(src)
