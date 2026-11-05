r"""成长系统·常量折叠优先级腐蚀修复（阶段 7·P3-1）回归锁。

修复 `_apply_const_folding`：旧 `([\d.]+\s*[+\-*/%]\s*[\d.]+)` 只吃前两个操作数、不锚定整行，
把 `x = 1 + 2 * 3` 折成 `x = 3 * 3`（=9≠7，过 P1 却改坏值）。新实现逐行 `fullmatch`，要求整行
右端恰为「数字 op 数字」（无第三个运算符/操作数）才折叠。政策 A：本片只动算术折叠，不碰三角恒等式、
不碰 P1 核心评估。每条折叠经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent`
双验收。离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

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


# 正例：整行右端恰为 num op num → 折叠（含 int/float 类型保真）；均带 #1 输出标记供等价对拍
FOLD_OK = [
    ("x = 3.0 + 4.0\n#1：[x]\n", "x = 7.0\n#1：[x]\n"),
    ("x = 10 - 3\n#1：[x]\n", "x = 7\n#1：[x]\n"),
    ("x = 6 * 7\n#1：[x]\n", "x = 42\n#1：[x]\n"),
    ("x = 8.0 / 2.0\n#1：[x]\n", "x = 4.0\n#1：[x]\n"),
    ("x = 7 % 2\n#1：[x]\n", "x = 1\n#1：[x]\n"),
]

# 反例：不满足「整行 num op num」→ 一律原样不动、cnt==0
NO_FOLD = [
    "x = 1 + 2 * 3\n#1：[x]\n",   # 优先级：三个操作数，绝不部分折叠
    "x = 8 // 2\n#1：[x]\n",      # 整除（双运算符）
    "x = 2 + 3 + 4\n#1：[x]\n",   # 三操作数
    "y = x + 2.0\n#1：[y]\n",     # 左操作数是标识符
    "x = 5 / 0\n#1：[x]\n",       # 除零守卫
    "x = 5 % 0\n#1：[x]\n",       # 取模零守卫
    "x = 1.2.3 + 4\n#1：[x]\n",   # 非法字面量
]


class TestFoldsCompleteBinaryLiterals:
    @pytest.mark.parametrize("src,expected", FOLD_OK)
    def test_rule_output(self, engine, src, expected):
        improved, cnt = engine._apply_const_folding(src)
        assert improved == expected
        assert cnt == 1

    @pytest.mark.parametrize("src,expected", FOLD_OK)
    def test_safe_candidate_gate(self, engine, src, expected):
        assert engine._is_safe_candidate(src, expected) is True

    @pytest.mark.parametrize("src,expected", FOLD_OK)
    def test_semantic_equivalence_gate(self, engine, src, expected):
        assert engine._semantic_equivalent(src, expected) is True

    def test_lhs_name_preserved(self, engine):
        improved, _ = engine._apply_const_folding("x = 3.0 + 4.0\n#1：[x]\n")
        assert improved.startswith("x = 7.0")  # 左端绑定名保留
        assert "x" in MathaGrowthEngine._bound_names(parse("x = 7.0\n"))


class TestNeverPartialFoldPrecedence:
    def test_no_partial_fold_breaks_precedence(self, engine):
        src = "x = 1 + 2 * 3\n#1：[x]\n"
        improved, cnt = engine._apply_const_folding(src)
        assert improved == src                # 绝不改动
        assert "x = 3 * 3" not in improved     # 元凶形态绝迹
        assert cnt == 0


class TestRejectsUnfoldable:
    @pytest.mark.parametrize("src", NO_FOLD)
    def test_untouched(self, engine, src):
        improved, cnt = engine._apply_const_folding(src)
        assert improved == src
        assert cnt == 0


class TestGrowIntegration:
    def test_grow_folds_and_stays_equivalent(self, engine):
        prog = "x = 3.0 + 4.0\n#1：[x]\n"
        rep = engine.grow(prog)
        out = rep.improved_source
        assert out == prog or _parses(out)
        assert engine._semantic_equivalent(prog, out) is True
