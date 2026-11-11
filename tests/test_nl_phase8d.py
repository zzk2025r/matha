# -*- coding: utf-8 -*-
"""阶段 8d：英语控制子集 + 用户词典 + LLM 可选路径边界 —— 三锁 + 零冲突锁。

三锁口径（与 8b/8c 同构，新增词典与 LLM 边界）：
  ① 对拍：同一英语句子经 自然语言英语执行器 NL英语执行（宿主加载 ↔ M3V VM
     编译两路）产出的结果逐值一致（vm = host）；内建 自然语言执行英语 两路亦一致。
  ② 闭环：句子 → 英语词法 → 英语句法（语义框架）→ 自举解释器 求值 → 结果值，
     宿主/VM 直接调用、宿主/VM 内建入口均等于手算期望值；
     Matha 源码层 输出(自然语言执行英语(...)) 亦可产出同一结果。
  ③ 显式拒绝：歧义/超控制子集英语句子（含空格分隔复合数词 "twenty five"
     边界——如实登记，不做静默猜测）宿主/VM、直接/内建四条链均抛
     MathaRuntimeError 且错误文本一致；VM 链未编译时内建显式 RuntimeError。
词典锁：用户词典为显式映射（默认空词典 = 行为与 8b/8c 完全一致）；替换发生在
  分词后、分类前；映射为**单层**（值不再二次查词典，英语侧值命中另一键也不
  再替换；中文侧值仍未知则词法器显式拒绝）——永不静默回退。
LLM 边界锁：确定性 NL 链（中文/英语）零 LLM 依赖——LLMIntentParser.parse 被
  monkeypatch 为必炸后，成功与拒绝路径均不触达；LLM 可选路径维持阶段 4 契约
  （MATHA_REPL_LLM 默认关 + 诚实降级，本阶段一字未改，由既有测试锁定）。
零冲突锁：自然语言执行 + 自然语言执行英语 两个独立命名内建于同一宿主/VM
  共存（VM 编译列表同时含中英两条执行链）；内建名 ≠ Matha 函数名（NL执行 /
  NL英语执行）无 VM 单全局表遮蔽；既有 混合编译/混合诊断/混合执行/转译语言
  行为不变；引擎调用零散输出、无状态。

fixture 模块级只建一次（真实加载/编译 Matha 核心 + 中英 NL 全链）。零跳过，零失败。
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

# 中英两条执行链全量编译（含 8b 词法/句法、8c 中文引擎、8d 词典/英语词法/
# 句法/引擎），保证两个 NL 内建在同一 VM 上同时可用。
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/nl_dict.matha", "matha/nl_lexer.matha",
               "matha/nl_parser.matha", "matha/nl_engine.matha",
               "matha/nl_lexer_en.matha", "matha/nl_parser_en.matha",
               "matha/nl_engine_en.matha"]

_EN_TOKENS_PLUS = [["词", "compute", "前导"], ["数字", "3", "数词"],
                   ["词", "plus", "动词"], ["数字", "5", "数词"]]


def _read(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def host_en():
    """宿主：加载 自然语言英语执行器（use 传递加载 中英词法/句法/解释器链）。"""
    interp = Interpreter()
    assert interp.load_matha_module("自然语言英语执行器"), "加载 自然语言英语执行器 失败"
    interp.outputs.clear()
    return interp


@pytest.fixture(scope="module")
def vm_en():
    """M3V VM：编译 核心 + 中英 NL 全链模块并运行。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.outputs.clear()
    return vm


@pytest.fixture(scope="module")
def vm_empty():
    """未编译 NL 链的空 VM（两个 NL 内建的显式拒绝路径）。"""
    comp = Compiler()
    comp.compile_program(ast.Program(decls=[]))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _host_run_en(interp, sentence):
    return interp._call_func_or_closure(interp.funcs["NL英语执行"], [sentence])


def _compile_vm(extra_src=None):
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    if extra_src:
        decls.extend(py_parse(extra_src).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


# ---------- ① 对拍：引擎结果（vm = host，直接调用） ----------

_EN_CLOSED = [
    ("compute three plus five", 8),
    ("what is twenty-one minus one", 20),
    ("3 plus 5", 8),
    ("calculate ten divided-by two", 5.0),
    ("five times four", 20),
    ("twenty minus thirty", -10),
    ("three-thousand-five-hundred plus one", 3501),
    ("seven", 7),
]


@pytest.mark.parametrize("sentence,_want", _EN_CLOSED, ids=lambda v: v if isinstance(v, str) else "")
def test_engine_parity(host_en, vm_en, sentence, _want):
    assert _host_run_en(host_en, sentence) == vm_en.call("NL英语执行", sentence), sentence


# ---------- ① 对拍：内建入口（vm = host） ----------


@pytest.mark.parametrize("sentence,_want", _EN_CLOSED, ids=lambda v: v if isinstance(v, str) else "")
def test_builtin_parity(host_en, vm_en, sentence, _want):
    host_val = host_en.call("自然语言执行英语", sentence)
    vm_val = vm_en.call("自然语言执行英语", sentence)
    assert host_val == vm_val, sentence


# ---------- ② 闭环：手算值（直接调用两路） ----------


@pytest.mark.parametrize("sentence,want", _EN_CLOSED)
def test_engine_closed_loop_host(host_en, sentence, want):
    assert _host_run_en(host_en, sentence) == want, sentence


@pytest.mark.parametrize("sentence,want", _EN_CLOSED)
def test_engine_closed_loop_vm(vm_en, sentence, want):
    assert vm_en.call("NL英语执行", sentence) == want, sentence


# ---------- ② 闭环：内建入口（宿主/VM） ----------


@pytest.mark.parametrize("sentence,want", _EN_CLOSED)
def test_builtin_closed_loop_host(host_en, sentence, want):
    assert host_en.call("自然语言执行英语", sentence) == want, sentence


@pytest.mark.parametrize("sentence,want", _EN_CLOSED)
def test_builtin_closed_loop_vm(vm_en, sentence, want):
    assert vm_en.call("自然语言执行英语", sentence) == want, sentence


# ---------- ② 闭环：token 形态（中英同构）+ 源码层 ----------


def test_en_tokens_shape_host(host_en):
    """英语 token 形态与中文词法器一致：关键词 ["词", 文本, 词类]、数词 ["数字", str, "数词"]。"""
    host_en.run(py_parse('输出(NL英语词法分析("compute three plus five"))'))
    assert host_en.outputs[-1] == _EN_TOKENS_PLUS
    host_en.run(py_parse('输出(NL英语词法分析("what is twenty-one minus one"))'))
    assert host_en.outputs[-1] == [["词", "what", "前导"], ["词", "is", "前导"],
                                   ["数字", "21", "数词"], ["词", "minus", "动词"],
                                   ["数字", "1", "数词"]]


def test_cn_tokens_shape_host(host_en):
    """中文 token 形态（8b 既有形态，默认空词典下不变）：计算 标注为动词，句法器按文本跳过。"""
    host_en.run(py_parse('输出(NL词法分析("计算 三 加 五"))'))
    assert host_en.outputs[-1] == [["词", "计算", "动词"], ["数字", "3", "数词"],
                                   ["词", "加", "动词"], ["数字", "5", "数词"]]


def test_en_tokens_shape_vm():
    """英语 token 形态（VM 编译路 = 宿主加载路）。"""
    vm = _compile_vm('输出(NL英语词法分析("compute three plus five"))')
    assert vm.outputs[-1] == _EN_TOKENS_PLUS


def test_source_level_host(host_en):
    """Matha 源码层 输出(自然语言执行英语(...)) → 输出流末位为结果值（宿主）。"""
    host_en.run(py_parse('输出(自然语言执行英语("compute three plus five"))'))
    assert host_en.outputs[-1] == 8


def test_source_level_vm():
    """Matha 源码层 输出(自然语言执行英语(...)) → 输出流末位为结果值（VM）。"""
    vm = _compile_vm('输出(自然语言执行英语("3 plus 5"))')
    assert vm.outputs[-1] == 8


# ---------- ③ 显式拒绝：歧义/超子集（四条链同文本） ----------

_EN_REJECTIONS = [
    # 空格分隔复合数词边界：如实拒绝，不做静默猜测（连字复合 twenty-one 才合法）
    ("twenty five", "句式歧义：连续数词缺少运算符"),
    ("three five", "句式歧义：连续数词缺少运算符"),
    # 复合数词序列不合法（百前必须个位）
    ("twenty-hundred", "超出控制子集的英语词"),
    ("hello world", "超出控制子集的英语词"),
    ("compute", "句式不完整：缺少数词"),
    ("plus five", "句式歧义：期望数词"),
    ("three plus", "句式不完整：运算符缺少数词"),
    ("three plus five times two", "超出控制子集的句式"),
    ("", "句子为空或仅含空白"),
]


@pytest.mark.parametrize("sentence,match", _EN_REJECTIONS)
def test_rejection_parity(host_en, vm_en, sentence, match):
    """直接调用两路同抛 MathaRuntimeError 且错误文本一致。"""
    with pytest.raises(MathaRuntimeError) as he:
        _host_run_en(host_en, sentence)
    with pytest.raises(MathaRuntimeError) as ve:
        vm_en.call("NL英语执行", sentence)
    assert str(he.value) == str(ve.value), sentence
    assert match in str(he.value), sentence


@pytest.mark.parametrize("sentence,match", _EN_REJECTIONS)
def test_rejection_builtin_host(host_en, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        host_en.call("自然语言执行英语", sentence)


@pytest.mark.parametrize("sentence,match", _EN_REJECTIONS)
def test_rejection_builtin_vm(vm_en, sentence, match):
    with pytest.raises(MathaRuntimeError, match=match):
        vm_en.call("自然语言执行英语", sentence)


def test_rejection_vm_uncompiled(vm_empty):
    """VM 链未编译：英语/中文两个内建均显式 RuntimeError，永不静默回退。"""
    with pytest.raises(RuntimeError, match="未编译"):
        vm_empty.call("自然语言执行英语", "compute three plus five")
    with pytest.raises(RuntimeError, match="未编译"):
        vm_empty.call("自然语言执行", "计算 三 加 五")


# ---------- ④ 词典锁：显式映射 / 默认空回归 / 单层不递归 ----------


def test_dict_default_empty_regression(host_en):
    """默认词典为空：未登记词（中英两侧）行为与 8b/8c 一致——显式拒绝，无静默回退。"""
    with pytest.raises(MathaRuntimeError, match="超出控制子集的英语词: quad"):
        host_en.call("自然语言执行英语", "compute quad plus five")
    with pytest.raises(MathaRuntimeError, match="超出控制子集的词"):
        host_en.call("自然语言执行", "计算 神经网络")


def test_dict_substitution_en_host(host_en):
    """英语侧显式词典：quad→four 进入分词后、分类前的替换点。"""
    host_en.run(py_parse('输出(NL英语词法分析带词典("compute quad plus five", '
                         'dict_from_pairs([["quad", "four"]])))'))
    assert host_en.outputs[-1] == [["词", "compute", "前导"], ["数字", "4", "数词"],
                                   ["词", "plus", "动词"], ["数字", "5", "数词"]]


def test_dict_substitution_cn_host(host_en):
    """中文侧显式词典：仨→三 进入分词后、分类前的替换点。"""
    host_en.run(py_parse('输出(NL词法分析带词典("计算 仨 加 五", '
                         'dict_from_pairs([["仨", "三"]])))'))
    assert host_en.outputs[-1] == [["词", "计算", "动词"], ["数字", "3", "数词"],
                                   ["词", "加", "动词"], ["数字", "5", "数词"]]


def test_dict_substitution_vm():
    """词典替换（VM 编译路 = 宿主加载路）：英语 quad→four 与中文 仨→三。"""
    vm = _compile_vm('输出(NL英语词法分析带词典("compute quad plus five", '
                     'dict_from_pairs([["quad", "four"]])))\n'
                     '输出(NL词法分析带词典("计算 仨 加 五", '
                     'dict_from_pairs([["仨", "三"]])))')
    # 自举模块装载期杂散输出（已知陷阱：词法/句法器漏 1）→ 本测试两个输出在流末
    assert vm.outputs[-2] == [["词", "compute", "前导"], ["数字", "4", "数词"],
                              ["词", "plus", "动词"], ["数字", "5", "数词"]]
    assert vm.outputs[-1] == [["词", "计算", "动词"], ["数字", "3", "数词"],
                              ["词", "加", "动词"], ["数字", "5", "数词"]]


def test_dict_frame_parity_host(host_en):
    """词典句的语义框架 = 直写合法词句的语义框架（替换发生在分类前，句法器无感知）。"""
    host_en.run(py_parse('输出(NL英语句法分析(NL英语词法分析带词典("compute quad plus five", '
                         'dict_from_pairs([["quad", "four"]]))))'))
    frame_sub = host_en.outputs[-1]
    host_en.run(py_parse('输出(NL英语编译("compute four plus five"))'))
    frame_direct = host_en.outputs[-1]
    assert frame_sub == frame_direct


def test_dict_one_level_en(host_en):
    """英语单层锁：quad→four 且 four→five 同典时，替换值 four 不再查典（结果 4 非 5）。"""
    host_en.run(py_parse('输出(NL英语词法分析带词典("compute quad plus five", '
                         'dict_from_pairs([["quad", "four"], ["four", "five"]])))'))
    assert host_en.outputs[-1] == [["词", "compute", "前导"], ["数字", "4", "数词"],
                                   ["词", "plus", "动词"], ["数字", "5", "数词"]]


def test_dict_one_level_cn(host_en):
    """中文单层锁：俩→仨 且 仨 仍未知 → 词法器显式拒绝（不二次查典、不静默回退）。"""
    with pytest.raises(MathaRuntimeError, match="超出控制子集的词: 仨"):
        host_en.run(py_parse('输出(NL词法分析带词典("计算 俩 加 五", '
                             'dict_from_pairs([["俩", "仨"]])))'))


# ---------- ⑤ LLM 边界锁：确定性链零 LLM 依赖 ----------


def test_llm_boundary_deterministic_chain_llm_free(host_en, monkeypatch):
    """LLMIntentParser.parse 被替换为必炸后：中文/英语确定性链的成功与拒绝
    路径均不触达 LLM（8d 未改任何 LLM 代码；可选路径契约由阶段 4 测试锁定）。"""

    def _boom(self, text):
        raise AssertionError("确定性 NL 链调用了 LLMIntentParser.parse")

    monkeypatch.setattr("src.intent.llm_parser.LLMIntentParser.parse", _boom)
    assert host_en.call("自然语言执行", "计算 三 加 五") == 8
    assert host_en.call("自然语言执行英语", "compute three plus five") == 8
    with pytest.raises(MathaRuntimeError):
        host_en.call("自然语言执行英语", "hello world")
    with pytest.raises(MathaRuntimeError):
        host_en.call("自然语言执行", "计算 神经网络")


# ---------- ⑥ 零冲突锁：两个独立命名内建共存 ----------


def test_zero_conflict_both_nl_builtins_host(host_en):
    """同一宿主解释器：中文 自然语言执行 与英语 自然语言执行英语 共存互不干扰。"""
    assert host_en.call("自然语言执行", "计算 三 加 五") == 8
    assert host_en.call("自然语言执行英语", "compute three plus five") == 8
    assert host_en.call("自然语言执行", "五 减 三") == 2
    assert host_en.call("自然语言执行英语", "five times four") == 20


def test_zero_conflict_both_nl_builtins_vm(vm_en):
    """同一 VM（中英两链全量编译）：两个 NL 内建共存互不干扰。"""
    assert vm_en.call("自然语言执行", "计算 三 加 五") == 8
    assert vm_en.call("自然语言执行英语", "compute three plus five") == 8
    assert vm_en.call("自然语言执行", "五 减 三") == 2
    assert vm_en.call("自然语言执行英语", "five times four") == 20


def test_zero_conflict_no_shadowing(host_en, vm_en):
    """内建名（自然语言执行/自然语言执行英语）≠ Matha 函数名（NL执行/NL英语执行）：
    宿主双表分离、VM 单全局表无重名遮蔽。"""
    assert "自然语言执行" in host_en.builtins
    assert "自然语言执行英语" in host_en.builtins
    assert "NL执行" in host_en.funcs
    assert "NL英语执行" in host_en.funcs
    assert "自然语言执行" not in host_en.funcs
    assert "自然语言执行英语" not in host_en.funcs
    assert "自然语言执行" in vm_en.globals
    assert "自然语言执行英语" in vm_en.globals
    assert "NL执行" in vm_en.globals
    assert "NL英语执行" in vm_en.globals


def test_zero_conflict_hybrid_builtins_coexist(host_en):
    """NL 调用后，既有 混合编译/混合诊断/混合执行/转译语言 在同一解释器上行为不变。"""
    assert host_en.call("自然语言执行英语", "compute three plus five") == 8
    build = host_en.call("混合编译", "测试任务", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(build, dict)
    diag = host_en.call("混合诊断", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(diag, dict)
    trans = host_en.call("转译语言", "func 加倍(x) -> Int = (x) => x * 2", "python")
    assert isinstance(trans, dict)


def test_zero_conflict_no_stray_output(host_en):
    """引擎调用本身零散输出：清空输出流后调用不产生任何输出。"""
    before = len(host_en.outputs)
    assert host_en.call("自然语言执行英语", "five times four") == 20
    assert len(host_en.outputs) == before


def test_zero_conflict_stateless(host_en):
    """引擎无状态：连续调用互不泄漏（环境每次重建，结果只由句子决定）。"""
    assert host_en.call("自然语言执行英语", "compute three plus five") == 8
    assert host_en.call("自然语言执行英语", "twenty minus thirty") == -10
    assert host_en.call("自然语言执行英语", "compute three plus five") == 8


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
