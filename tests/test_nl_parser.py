# -*- coding: utf-8 -*-
"""阶段 8b-2：NL 句法器（纯 Matha）入门禁。

验证：
1. 宿主加载 nl_parser.matha 模块成功。
2. 句式 → 语义框架（Matha 表达式 AST）：二元算术/数量短语/纯数词。
3. 把字句与命令前导（计算/算/求/把）正确跳过。
4. 程序 AST 包装（NL程序 = 程序[输出(表达式)]）。
5. 歧义与超控制子集显式拒绝（连续数词/缺数词/多运算符链/未知词类/空序列）。

零跳过，零失败。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import Interpreter
from src.parser import parse as py_parse
from src.kernel.errors import MathaRuntimeError

ROOT = Path(__file__).resolve().parents[1]


def _int(n: int) -> dict:
    return {"类型": "整数", "值": n}


def _bin(op: str, left: dict, right: dict) -> dict:
    return {"类型": "二元运算", "运算符": op, "左": left, "右": right}


def _compile(sentence: str) -> dict:
    """加载 nl_parser 模块并调用 NL编译（句子 → 语义框架）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言句法器"), "加载模块失败"
    # 模块加载期依赖模块的顶层表达式会产生输出，清掉以隔离被测调用
    interp.outputs.clear()
    prog = py_parse(f'输出(NL编译("{sentence}"))')
    outputs, errors = interp.run(prog)
    assert not errors, f"宿主解释器错误: {errors}"
    assert len(outputs) == 1, f"期望 1 个输出，实际 {len(outputs)}"
    return outputs[0]


def _reject(source: str, match: str) -> None:
    """加载模块后执行 source，断言抛出匹配 match 的 MathaRuntimeError。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言句法器")
    prog = py_parse(source)
    with pytest.raises(MathaRuntimeError, match=match):
        interp.run(prog)


def test_host_load_module():
    """宿主加载 nl_parser 模块成功。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言句法器")


def test_parse_basic_addition():
    """计算 三 加 五 → 3 + 5。"""
    assert _compile("计算 三 加 五") == _bin("+", _int(3), _int(5))


def test_parse_ba_construction():
    """把 三 加上 五 → 3 + 5（把字句前导跳过，加上 映射 +）。"""
    assert _compile("把 三 加上 五") == _bin("+", _int(3), _int(5))


def test_parse_subtraction():
    """五 减 三 → 5 - 3。"""
    assert _compile("五 减 三") == _bin("-", _int(5), _int(3))


def test_parse_multiplication():
    """三 乘以 四 → 3 * 4。"""
    assert _compile("三 乘以 四") == _bin("*", _int(3), _int(4))


def test_parse_division():
    """六 除以 二 → 6 / 2。"""
    assert _compile("六 除以 二") == _bin("/", _int(6), _int(2))


def test_parse_quantity_phrase():
    """计算 三十 个苹果 → 30（数量短语语义值为数词）。"""
    assert _compile("计算 三十 个苹果") == _int(30)


def test_parse_bare_number():
    """三 → 3（纯数词）。"""
    assert _compile("三") == _int(3)


def test_parse_compound_number_operands():
    """十五 加 二十 → 15 + 20（复合中文数字操作数）。"""
    assert _compile("十五 加 二十") == _bin("+", _int(15), _int(20))


def test_program_wrapper():
    """NL程序 把语义框架包成 程序[输出(表达式)]。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言句法器")
    interp.outputs.clear()
    prog = py_parse('输出(NL程序("计算 三 加 五"))')
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[0] == {
        "类型": "程序",
        "声明": [{"类型": "输出", "expr": _bin("+", _int(3), _int(5))}],
    }


def test_rejection_consecutive_numbers():
    """显式拒绝：连续数词缺少运算符（三 五）。"""
    _reject('NL编译("三 五")', "句式歧义：连续数词缺少运算符")


def test_rejection_operator_missing_operand():
    """显式拒绝：运算符缺少数词（三 加）。"""
    _reject('NL编译("三 加")', "句式不完整：运算符缺少数词")


def test_rejection_operator_chain():
    """显式拒绝：多运算符链超出控制子集（三 加 五 乘 二）。"""
    _reject('NL编译("三 加 五 乘 二")', "超出控制子集的句式")


def test_rejection_missing_number():
    """显式拒绝：仅命令前导缺少数词（计算）。"""
    _reject('NL编译("计算")', "句式不完整：缺少数词")


def test_rejection_expected_number():
    """显式拒绝：句首非数词（加 五）。"""
    _reject('NL编译("加 五")', "句式歧义：期望数词")


def test_rejection_non_number_after_operator():
    """显式拒绝：运算符后非数词（三 加 苹果）。"""
    _reject('NL编译("三 加 苹果")', "句式歧义：运算符后期望数词")


def test_rejection_empty_tokens():
    """显式拒绝：空 token 序列。"""
    _reject("NL句法分析([])", "空 token 序列，无法解析")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))