"""成长系统·函数内联规则修正（阶段 7·P2-3·选项 1）回归锁。

修复元凶 A：旧 `_apply_function_inlining` ① 把函数定义声明头 `func n(...)` 误当调用点、
`replace` 全局删掉函数名致 PARSE-FAIL；② 内联体从不把形参替换成实参。新实现按构造保守正确：
只处理 curried 单表达式形态，仅在「形参皆标识符 ∧ 实参数==形参数 ∧ 每实参为简单 token ∧
body 自由标识符⊆形参」四条同时成立时就地内联，且以 `func\\s+$` 前缀识别并跳过定义头
（函数名绝不删）。每条改写经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent`
双验收。离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

import re

import pytest

from src.matha_growth import MathaGrowthEngine
from src.parser import parse


def _parses(src: str) -> bool:
    try:
        parse(src)
        return True
    except Exception:
        return False


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


# 正例：curried 定义 + 调用 → 就地内联（形参→实参替换），定义头原样保留；outvar 供等价对拍
INLINE_OK = [
    (
        "func 加(x, y) -> Int = (x, y) => x + y\nz = 加(2, 3)\n",
        "func 加(x, y) -> Int = (x, y) => x + y\nz = (2 + 3)\n",
        "z",
    ),
    (
        "func sq(x) -> Int = (x) => x * x\ny = sq(4)\n",
        "func sq(x) -> Int = (x) => x * x\ny = (4 * 4)\n",
        "y",
    ),
    (
        "func c() -> Int = () => 42\nx = c()\n",
        "func c() -> Int = () => 42\nx = (42)\n",
        "x",
    ),
    (
        "func c() -> Int = () => 42\nx = c() + c()\n",
        "func c() -> Int = () => 42\nx = (42) + (42)\n",
        "x",
    ),
]

# 反例：不满足可证等价四条件之一 → 一律原样不动、cnt==0
NO_INLINE = [
    "func f() -> Int = () => a\nx = f()\n",                       # body 含自由变量 a
    "func 加(x, y) -> Int = (x, y) => x + y\nz = 加(1 + 2, 3)\n",  # 实参非简单 token
    "func 加(x, y) -> Int = (x, y) => x + y\nz = 加(2)\n",          # arity 不符
    "func sq(x) -> Int = x * x\ny = sq(4)\n",                       # 非 curried 形态，不匹配
    "func 加(x, y) -> Int = (x, y) => x + y\n",                     # 只有定义、无调用
]


class TestCorrectInlining:
    @pytest.mark.parametrize("src,expected,outvar", INLINE_OK)
    def test_rule_output(self, engine, src, expected, outvar):
        improved, cnt = engine._apply_function_inlining(src)
        assert improved == expected
        assert cnt >= 1

    @pytest.mark.parametrize("src,expected,outvar", INLINE_OK)
    def test_definition_name_preserved(self, engine, src, expected, outvar):
        # 元凶 A 形态绝迹：从不出现无名 `func (`，函数名保留，且仍可解析
        improved, _ = engine._apply_function_inlining(src)
        assert re.search(r'func\s+\(', improved) is None
        assert _parses(improved)

    @pytest.mark.parametrize("src,expected,outvar", INLINE_OK)
    def test_safe_candidate_gate(self, engine, src, expected, outvar):
        assert engine._is_safe_candidate(src, expected) is True

    @pytest.mark.parametrize("src,expected,outvar", INLINE_OK)
    def test_semantic_equivalence_gate(self, engine, src, expected, outvar):
        o = src + f"#1：[{outvar}]\n"
        i = expected + f"#1：[{outvar}]\n"
        assert engine._semantic_equivalent(o, i) is True


class TestConservativeNoOp:
    @pytest.mark.parametrize("src", NO_INLINE)
    def test_untouched(self, engine, src):
        improved, cnt = engine._apply_function_inlining(src)
        assert improved == src
        assert cnt == 0


class TestGrowIntegration:
    def test_curry_cleanly_unoptimized(self, engine):
        # 修复后 CURRY_A 不再自造坏候选：grow 出码恒等于原文、可解析、函数名保留
        src = "func 加(x, y) -> Int = (x, y) => x + y\n"
        rep = engine.grow(src)
        assert rep.optimizations_applied == []
        assert rep.improved_source == src
        assert "加" in rep.improved_source
        assert _parses(rep.improved_source)
