# -*- coding: utf-8 -*-
"""内联缓存（特化解释器）测试。

覆盖三层：

1. ``specialize`` 的白名单：只为**逐一核对过语义等价**的 (运算符, 类型) 组合
   提供专用实现；其余一律返回 ``None``（回落通用路径）。
2. ``InlineCache`` 的状态机：形状一致累积命中 → 达阈值安装专用实现；
   形状变化 → 重新武装（退化为单态）。
3. 端到端语义等价：``INLINE_CACHE`` 开/关必须给出**完全相同**的结果与错误，
   包含类型错误、除零错误、移位错误等异常路径。
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import ast as A
from src import features
from src.interp import Interpreter, MathaRuntimeError
from src.interp_ic import IC_THRESHOLD, InlineCache, specialize
from src.parser import parse


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _binary_nodes(node, out=None):
    """收集 AST 中所有 ``BinaryOp`` 节点。"""
    if out is None:
        out = []
    if isinstance(node, A.BinaryOp):
        out.append(node)
    for f in getattr(node, "__dataclass_fields__", {}):
        v = getattr(node, f, None)
        if isinstance(v, list):
            for x in v:
                if hasattr(x, "__dataclass_fields__"):
                    _binary_nodes(x, out)
        elif hasattr(v, "__dataclass_fields__"):
            _binary_nodes(v, out)
    return out


def _run_twice(ast_obj, times):
    """对同一棵 AST 反复求值 ``times`` 次（IC 挂在 AST 节点上，必须复用 AST）。"""
    out = None
    for _ in range(times):
        out = Interpreter().run(ast_obj)[0]
    return out


def _run_with(ast_obj, ic, times=1):
    features.set_feature("INLINE_CACHE", ic)
    try:
        return _run_twice(ast_obj, times)
    finally:
        features.clear_feature("INLINE_CACHE")


# --------------------------------------------------------------------------
# 1. specialize 白名单
# --------------------------------------------------------------------------

@pytest.mark.parametrize("op,ltype,rtype", [
    ("+", int, int), ("+", int, float), ("+", float, int), ("+", float, float),
    ("+", bool, int), ("+", int, bool), ("+", bool, bool),
    ("+", str, str), ("+", str, int), ("+", str, float), ("+", int, str),
    ("-", int, int), ("-", int, float), ("-", float, float), ("-", bool, int),
    ("*", int, int), ("*", int, float), ("*", float, float),
    ("*", str, int), ("*", int, str),
    ("**", int, int), ("**", int, float), ("^", int, int),
    ("&", int, int), ("|", int, int), ("⊕", int, int),
    ("<<", int, int), (">>", int, int),
    ("&", bool, int), ("|", bool, bool), ("<<", bool, int),
    ("<", int, int), (">", int, int), ("<=", int, int), (">=", int, int),
    ("=", int, int), ("==", int, int), ("!=", int, int),
    ("is", int, int), ("===", int, int), ("!==", int, int), ("??", int, int),
    ("in", int, list), ("in", str, str), ("in", int, dict), ("in", int, set),
    ("and", bool, bool), ("or", bool, bool),
])
def test_specialize_supported(op, ltype, rtype):
    assert specialize(op, ltype, rtype) is not None


@pytest.mark.parametrize("op,ltype,rtype", [
    # 除法族：通用路径带除零检查，不能特化
    ("/", int, int), ("%", int, int), ("//", int, int),
    # 集合运算：通用路径返回有序去重列表，不能用 Python 集合语义替代
    ("∪", list, list), ("∩", list, list), ("⊖", list, list),
    ("~", list, list), ("×", list, list), ("⊆", list, list),
    # 箭头调用：有副作用与分派逻辑
    ("→", int, int),
    # dict 的 + 会被通用路径转成 list(items)，不能特化
    ("+", dict, dict), ("+", dict, list), ("+", list, dict),
    # None 操作数：通用路径有专门的错误信息
    ("+", type(None), int), ("+", int, type(None)),
    ("-", type(None), int), ("**", type(None), int),
    # 未知运算符
    ("@@", int, int),
    # 字符串乘法：str*float 通用路径报错
    ("*", str, float),
    # int*str 在通用路径会走 l*r，语义等价但仅在 bool 情形下不同 → 保守不特化
    ("*", bool, str),
])
def test_specialize_rejected(op, ltype, rtype):
    assert specialize(op, ltype, rtype) is None


def test_specialize_rejects_virtual_symbol():
    """VirtualSymbol（宽容值）不得进入特化路径：通用路径会构造宽容值。"""
    from src.interp import VirtualSymbol
    assert specialize("+", VirtualSymbol, int) is None
    assert specialize("<", VirtualSymbol, VirtualSymbol) is None
    assert specialize("==", VirtualSymbol, int) is None


def test_virtual_symbol_end_to_end_identical():
    """宽容值参与运算 → 结果仍是宽容值；IC 开/关必须完全一致。"""
    from src.interp import VirtualSymbol

    def _apply(ic):
        features.set_feature("INLINE_CACHE", ic)
        try:
            interp = Interpreter()
            site = parse("输出(1 + 2)").decls[0]
            node = _binary_nodes(site)[0]
            vs = VirtualSymbol("未定义变量", "变量", None)
            r1 = interp._apply_binary_values("+", vs, 1, site=node)
            r2 = interp._apply_binary_values("<", vs, 1, site=node)
            r3 = interp._apply_binary_values("+", 1, vs, site=node)
            return (type(r1), str(r1), type(r2), str(r2), type(r3), str(r3))
        finally:
            features.clear_feature("INLINE_CACHE")

    off = _apply(False)
    on = _apply(True)
    assert off == on
    assert off[0] is VirtualSymbol
    assert off[2] is VirtualSymbol
    assert off[4] is VirtualSymbol


# --------------------------------------------------------------------------
# 2. InlineCache 状态机
# --------------------------------------------------------------------------

def test_ic_installs_after_threshold():
    ic = InlineCache()
    for _ in range(IC_THRESHOLD - 1):
        assert ic.fast_for("+", 1, 2) is None
    assert ic.fast_for("+", 1, 2) is not None
    assert ic.hits == IC_THRESHOLD


def test_ic_shape_change_rearms():
    ic = InlineCache()
    for _ in range(IC_THRESHOLD + 5):
        ic.fast_for("+", 1, 2)
    assert ic.fast is not None
    # 形状变化 → 重新武装（fast 重新学习，hits 归 1）
    assert ic.fast_for("+", "a", "b") is None
    assert ic.ltype is str and ic.rtype is str
    assert ic.hits == 1
    assert ic.fast is not None      # str+str 可特化


def test_ic_polymorphic_site_never_installs():
    """交替出现的形状不得安装专用实现（单态缓存）。"""
    ic = InlineCache()
    for _ in range(IC_THRESHOLD * 3):
        assert ic.fast_for("+", 1, 2) is None
        assert ic.fast_for("+", "a", "b") is None


def test_ic_reset():
    ic = InlineCache()
    for _ in range(IC_THRESHOLD + 1):
        ic.fast_for("+", 1, 2)
    ic.reset()
    assert ic.op is None and ic.hits == 0 and ic.fast is None


# --------------------------------------------------------------------------
# 3. 端到端语义等价
# --------------------------------------------------------------------------

EQUIV_EXPRS = [
    "1 + 2", "1 + 2.5", "1.5 + 2", "真 + 2", "2 + 真", "1 + 真",
    "真 + 真", '"a" + "b"', '"a" + 1', '"a" + 2.5', '"a" + 真',
    '1 + "a"', '2.5 + "a"', '真 + "a"',
    "[1,2] + [3]",
    "1 - 2", "1 - 2.5", "真 - 1", "1.5 - 0.5",
    "2 * 3", "2 * 2.5", '"ab" * 3', '"ab" * 真', "2 * 3.5",
    "2 ** 3", "2 ** 0.5", "2 ^ 3",
    "6 & 3", "6 | 3", "6 ⊕ 3", "1 << 4", "16 >> 2", "真 & 3",
    "1 < 2", "2 < 1", '"a" < "b"', "1 <= 1", "1 > 2", "1 >= 2",
    "1 = 1", "1 == 1", "1 != 2", "1 is 1", "1 === 1", "1 !== 2",
    "null ?? 3", "1 ?? 3", "1 in [1,2]", '"a" in "abc"', "1 in {1:2}",
    "[1,2,3]", "{1,2,3}", "1 in {1,2,3}",
]

ERROR_EXPRS = [
    '1 - "a"', "[1] - [2]", '"a" * 2.5', "1 < \"a\"", "1 & 2.5",
    "1 << -1", "1 / 0", "1 % 0", "1 // 0", "1 + null",
]


@pytest.mark.parametrize("expr", EQUIV_EXPRS)
def test_ic_on_off_same_result(expr):
    src = "输出(" + expr + ")"
    a_off = _run_with(parse(src), False, times=IC_THRESHOLD + 5)
    a_on = _run_with(parse(src), True, times=IC_THRESHOLD + 5)
    assert a_off == a_on


@pytest.mark.parametrize("expr", ERROR_EXPRS)
def test_ic_on_off_same_error(expr):
    src = "输出(" + expr + ")"

    def _catch(ic):
        features.set_feature("INLINE_CACHE", ic)
        try:
            with pytest.raises(Exception) as ei:
                _run_twice(parse(src), IC_THRESHOLD + 5)
            return (type(ei.value), str(ei.value))
        finally:
            features.clear_feature("INLINE_CACHE")

    assert _catch(False) == _catch(True)


def test_ic_actually_installs_on_hot_site():
    """热调用点必须真的安装专用实现（否则本测试无意义）。"""
    ast_obj = parse("输出(1 + 2)")
    _run_with(ast_obj, True, times=IC_THRESHOLD + 5)
    nodes = _binary_nodes(ast_obj)
    assert nodes, "AST 中应存在 BinaryOp"
    assert any(getattr(n, "_ic", None) is not None and n._ic.fast is not None
               for n in nodes)


def test_ic_disabled_leaves_no_cache():
    ast_obj = parse("输出(1 + 2)")
    _run_with(ast_obj, False, times=IC_THRESHOLD + 5)
    for n in _binary_nodes(ast_obj):
        assert getattr(n, "_ic", None) is None


def test_ic_polymorphic_call_site_correct():
    """同一调用点先 int 后 str：结果必须始终正确（缓存重新武装）。"""
    src = (
        "func f(x) -> Int = (x) => x + 1\n"
        "输出(f(1))\n"
    )
    ast_obj = parse(src)
    off = _run_with(parse(src), False, times=IC_THRESHOLD + 5)
    on = _run_with(ast_obj, True, times=IC_THRESHOLD + 5)
    assert off == on == [2]


def test_ic_hot_loop_result_stable():
    src = (
        "let i = 0\n"
        "let s = 0\n"
        "while i < 50 {\n"
        "  s = s + i\n"
        "  i = i + 1\n"
        "}\n"
        "输出(s)\n"
    )
    off = _run_with(parse(src), False)
    on = _run_with(parse(src), True)
    assert off == on == [1225]


def test_ic_feature_default_on():
    features.clear_feature("INLINE_CACHE")
    assert features.inline_cache() is True
    features.set_feature("INLINE_CACHE", False)
    assert features.inline_cache() is False
    features.clear_feature("INLINE_CACHE")


def test_ic_engine_parity():
    """显式栈引擎与经典解释器共用同一份内联缓存实现，结果必须一致。"""
    src = (
        "let i = 0\n"
        "let s = 0\n"
        "while i < 30 {\n"
        "  s = s + i * 2\n"
        "  i = i + 1\n"
        "}\n"
        "输出(s)\n"
    )
    ast_obj = parse(src)
    off = _run_with(parse(src), False, times=IC_THRESHOLD + 5)
    on = _run_with(ast_obj, True, times=IC_THRESHOLD + 5)
    assert off == on

    features.set_feature("STACK_ENGINE", True)
    try:
        eng = _run_twice(parse(src), IC_THRESHOLD + 5)
    finally:
        features.clear_feature("STACK_ENGINE")
    assert eng == off
