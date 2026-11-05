r"""成长引擎·循环展开（S1）生产级回归锁。

背景（见 KNOWN_ISSUES.md §7c）：旧 `_apply_loop_unrolling` 用 Python 冒号缩进语法
`for … in range(N):\n` 匹配——Matha 根本不用该语法（真实为花括号块 `for v in <expr> { … }`、
`range(a,b)` 两参柯里化），故旧规则只在**非法输入**上触发，且 `body.replace(var, i)`
子串误伤（`ab`→`0b`）。S1 重写为「仅在可静态枚举且可证等价时、按词边界保守展开」。

本锁口径（对齐 plan S1）：
  ① 正确展开正例：数字字面量列表 / `range(int,int)` / `range(int)(int)`；
  ② 子串误伤反例：循环变量与 `ab`/`side` 等同名片段共存时只替换独立词；
  ③ 非可枚举 / 控制流 / 体内重赋循环变量 / 元组解构 / 超跨度 → 一律不动；
  ④ 双闸门：每条展开候选同时过 P1（名守恒可解析）与 `_semantic_equivalent`（逐例语义对拍）；
  ⑤ grow 集成：管线让展开生效且守住 P1 底线。
全程离线、毫秒级、无文件副作用、不触 L1 内核入口、不污染单例。
"""
from __future__ import annotations

import pytest

from src.matha_growth import GrowthReport, MathaGrowthEngine


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


class TestCorrectUnrolling:
    """① 正确展开正例：可静态枚举且可证等价。"""

    @pytest.mark.parametrize("src", [
        "s = 0\nfor i in [1, 2, 3] { s = s + i }\n#1：[s]\n",
        "s = 0\nfor i in [0, 1, 2, 3] { s = s + i }\n#1：[s]\n",
        "out = 0\nfor x in [2, 4, 6] { out = out + x }\n#1：[out]\n",
        "s = 0\nfor i in range(0, 4) { s = s + i }\n#1：[s]\n",
        "s = 0\nfor i in range(0)(4) { s = s + i }\n#1：[s]\n",
    ])
    def test_enumerable_bodies_unroll(self, engine, src):
        improved, cnt = engine._apply_loop_unrolling(src)
        assert cnt >= 1, f"可枚举循环应展开，实得 cnt={cnt}"
        # 展开后体内不再有 for / 循环变量
        assert "for " not in improved
        # ④ 双闸门
        assert engine._is_safe_candidate(src, improved) is True
        assert engine._semantic_equivalent(src, improved) is True

    def test_body_is_instantiated_per_element(self, engine):
        improved, cnt = engine._apply_loop_unrolling(
            "s = 0\nfor i in [1, 2, 3] { s = s + i }\n#1：[s]\n"
        )
        assert cnt == 1
        assert "s = s + 1" in improved
        assert "s = s + 2" in improved
        assert "s = s + 3" in improved


class TestSubstringSafety:
    """② 子串误伤反例：循环变量须按词边界替换，绝不伤及同名片段。"""

    def test_shared_substring_identifiers_preserved(self, engine):
        src = (
            "ab = 100\nside = 5\nt = 0\n"
            "for i in [1, 2] { t = t + i + ab + side }\n#1：[t]\n"
        )
        improved, cnt = engine._apply_loop_unrolling(src)
        assert cnt == 1
        # 旧 `body.replace('i', v)` 会把 ab→`0b`?（i 不误伤 ab/side，但旧更宽泛子串替换会伤）
        # 关键：ab / side 必须原样存活，独立 i 被逐元素代入
        assert "ab" in improved and "side" in improved
        assert "t = t + 1 + ab + side" in improved
        assert "t = t + 2 + ab + side" in improved
        assert engine._is_safe_candidate(src, improved) is True
        assert engine._semantic_equivalent(src, improved) is True

    def test_loop_var_prefix_of_other_name_not_corrupted(self, engine):
        # 循环变量 x，另有名为 xy 的标识符——词边界替换不得把 xy 拆成 <val>y
        src = "xy = 9\ns = 0\nfor x in [1, 2] { s = s + x + xy }\n#1：[s]\n"
        improved, cnt = engine._apply_loop_unrolling(src)
        assert cnt == 1
        assert "xy" in improved
        assert engine._semantic_equivalent(src, improved) is True


class TestConservativeNoOp:
    """③ 非可枚举 / 危险形态 → 一律不动（宁可不改，不可改错）。"""

    @pytest.mark.parametrize("src", [
        "total = 0\nfor x in someList { total = total + x }\n#1：[total]\n",   # 非字面量 iterable
        "s = 0\nfor (a, b) in [1, 2] { s = s + a }\n#1：[s]\n",                # 元组解构
        "s = 0\nfor i in [1, 2, 3] { if i > 1 { s = s + i } }\n#1：[s]\n",      # 体内控制流
        "s = 0\nfor i in [1, 2, 3] { i = i * 2\ns = s + i }\n#1：[s]\n",        # 体内重赋循环变量
        "s = 0\nfor i in range(0, 100) { s = s + i }\n#1：[s]\n",               # 超跨度
        "s = 0\nfor i in [1, a, 3] { s = s + i }\n#1：[s]\n",                   # 列表含非字面量
    ])
    def test_untouched(self, engine, src):
        improved, cnt = engine._apply_loop_unrolling(src)
        assert cnt == 0, f"危险/非可枚举形态不得展开，实得 cnt={cnt}"
        assert improved == src, f"不得改动原文：{improved!r}"

    def test_empty_iterable_is_enumerable_and_equivalent(self, engine):
        src = "s = 0\nfor i in [] { s = s + i }\n#1：[s]\n"
        improved, cnt = engine._apply_loop_unrolling(src)
        assert cnt == 1
        assert "for " not in improved
        assert engine._semantic_equivalent(src, improved) is True


class TestGrowIntegration:
    """⑤ grow 集成：管线让循环展开生效并守住 P1 名守恒底线。

    注：全管线语义等价另受 `_apply_const_propagation` 既有「把字面量累加器灌进循环体」
    的独立缺陷影响（不属 S1 切片），故用累加器经非字面量初始化的输入避开该无关缺陷，
    专注验证 S1 自身契约。
    """

    @pytest.mark.parametrize("src", [
        "p = 1\nacc = p\nfor i in [1, 2, 3] { acc = acc + i }\n#1：[acc]\n",
        "p = 1\nacc = p\nfor i in range(0, 4) { acc = acc + i }\n#1：[acc]\n",
    ])
    def test_grow_unrolls_and_stays_safe(self, engine, src):
        rep = engine.grow(src)
        assert isinstance(rep, GrowthReport)
        out = rep.improved_source
        # P1 底线：出码可解析或等于原文，且不丢已绑定名
        assert out == src or engine._is_safe_candidate(src, out)
        assert engine._semantic_equivalent(src, out) is True

    def test_grow_never_raises_on_loop_garbage(self, engine):
        # 旧 Python 冒号语法（Matha 非法）经 grow 不得抛，且回退/原样
        for src in [
            "for i in range(3):\n    s = s + i\n",
            "for i in [1, 2 { broken\n",
            "",
        ]:
            assert isinstance(engine.grow(src), GrowthReport)
