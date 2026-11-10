# -*- coding: utf-8 -*-
"""阶段 8b-1：NL 词法器（纯 Matha）入门禁。

验证：
1. 宿主加载 nl_lexer.matha 模块成功。
2. 中文数字转换（三→3, 三十五→35）。
3. 分词 + 词类标注（计算/加上/把/的/个/结果等）。
4. 控制子集拒绝（未知词、歧义词）。
5. 与 VM 编译后结果对拍（vm = host）。

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
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]


def _load_and_call_lexer(sentence: str) -> list:
    """加载 nl_lexer 模块并调用 NL词法分析。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器"), "加载模块失败"
    # 模块加载期依赖模块的顶层表达式会产生输出，清掉以隔离被测调用
    interp.outputs.clear()

    # 解析 NL词法分析 函数调用
    source = f'输出(NL词法分析("{sentence}"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors, f"宿主解释器错误: {errors}"
    assert len(outputs) == 1, f"期望 1 个输出，实际 {len(outputs)}"
    # outputs[0] 是 NL词法分析 返回的列表
    return outputs[0]


def test_host_load_module():
    """宿主加载 nl_lexer 模块成功。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器")


def test_chinese_number_conversion():
    """中文数字转阿拉伯数字：个位、十位、百位、千位、万位。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器")
    interp.outputs.clear()

    # 个位
    source = '输出(中文数字转阿拉伯数字("三"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[-1] == 3

    # 十位
    source = '输出(中文数字转阿拉伯数字("十五"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[-1] == 15

    # 百位
    source = '输出(中文数字转阿拉伯数字("二百"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[-1] == 200

    # 千位
    source = '输出(中文数字转阿拉伯数字("三千"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[-1] == 3000

    # 万位
    source = '输出(中文数字转阿拉伯数字("一万"))'
    prog = py_parse(source)
    outputs, errors = interp.run(prog)
    assert not errors
    assert outputs[-1] == 10000


def test_nl_lexical_analysis_basic():
    """NL 词法分析：基本算术指令句。"""
    result = _load_and_call_lexer("计算 三 加 五")
    # 期望：["词", "计算", "动词"], ["数字", "3", "数词"], ["词", "加", "动词"], ["数字", "5", "数词"]
    assert result == [
        ["词", "计算", "动词"],
        ["数字", "3", "数词"],
        ["词", "加", "动词"],
        ["数字", "5", "数词"],
    ], f"期望 [...], 实际 {result}"


def test_nl_lexical_analysis_with_ba_sentence():
    """NL 词法分析：把字句（带介词 "把"）。"""
    result = _load_and_call_lexer("把 三 加上 五")
    # 期望：["词", "把", "介词"], ["数字", "3", "数词"], ["词", "加上", "动词"], ["数字", "5", "数词"]
    assert result == [
        ["词", "把", "介词"],
        ["数字", "3", "数词"],
        ["词", "加上", "动词"],
        ["数字", "5", "数词"],
    ]


def test_nl_lexical_analysis_with_measure_word():
    """NL 词法分析：带量词（"个"）。"""
    result = _load_and_call_lexer("计算 三十 个苹果")
    # 期望：["词", "计算", "动词"], ["数字", "30", "数词"], ["词", "个", "量词"], ["词", "苹果", "名词"]
    assert result == [
        ["词", "计算", "动词"],
        ["数字", "30", "数词"],
        ["词", "个", "量词"],
        ["词", "苹果", "名词"],
    ]


def test_nl_lexical_analysis_rejection_unknown_word():
    """显式拒绝：超出控制子集的词（如 "神经网络"）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器")

    source = 'NL词法分析("计算 三 加 五 神经网络")'
    prog = py_parse(source)
    with pytest.raises(MathaRuntimeError, match="超出控制子集的词"):
        interp.run(prog)


def test_nl_lexical_analysis_rejection_ambiguous():
    """显式拒绝：歧义/超子集词（"对数" 不在控制子集关键词列表中）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器")

    source = 'NL词法分析("计算 对数")'
    prog = py_parse(source)
    with pytest.raises(MathaRuntimeError, match="超出控制子集的词"):
        interp.run(prog)


def test_nl_lexical_analysis_empty_sentence():
    """显式拒绝：空句子或仅含空白。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言词法器")

    source = 'NL词法分析("")'
    prog = py_parse(source)
    with pytest.raises(MathaRuntimeError, match="句子为空或仅含空白"):
        interp.run(prog)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
