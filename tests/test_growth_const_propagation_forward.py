r"""成长系统·常量传播前向引用/重绑定腐蚀修复（阶段 7·P3-2）回归锁。

修复 `_apply_const_propagation`：旧 `def_re.findall(source)` 找到每个纯字面量定义后，
把名字回灌到**全文所有**使用点——既灌向定义**之前**的使用点（`x=2.0*3.0; y=x+1; x=10.0`
→ `y` 由 7.0 被改成 11.0，过 P1 却语义腐蚀），也无视同名重绑定。新实现逐行顺序扫描，
维护「当前活跃纯字面量」，每行先用「进入本行前」的活跃字面量替换本行使用点，再据本行更新
状态（纯字面量赋值→更新活跃值；非字面量赋值→失效）。政策 A：只动算术传播，不碰三角恒等式、
不碰 P1 核心评估。每条改写经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent`
双验收。离线、毫秒级、无文件副作用、不触 L1 内核入口。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine


@pytest.fixture()
def engine() -> MathaGrowthEngine:
    return MathaGrowthEngine()


# 正例：定义在使用之前 → 正常前向传播（含重绑定取「进入该行时的活跃值」）
FWD_OK = [
    ("a = 3.0\nb = a + 1\n#1：[b]\n",
     "a = 3.0\nb = 3.0 + 1\n#1：[b]\n", 1),
    ("x = 10\ny = x\n#1：[y]\n",
     "x = 10\ny = 10\n#1：[y]\n", 1),
    ("p = 2.0\nq = p + p\n#1：[q]\n",
     "p = 2.0\nq = 2.0 + 2.0\n#1：[q]\n", 2),
    # 重绑定：y 用「进入该行时」的活跃值 1，而非其后的 5
    ("x = 1\ny = x\nx = 5\n#1：[y]\n",
     "x = 1\ny = 1\nx = 5\n#1：[y]\n", 1),
    # 自引用行：先按旧值 2 替换 RHS，再判 x 重绑定失效
    ("x = 2\ny = x + 1\nx = 9\n#1：[y]\n",
     "x = 2\ny = 2 + 1\nx = 9\n#1：[y]\n", 1),
]

# 反例（元凶 C）：定义在使用之后 / 更早绑定为非字面量 → 绝不回灌、整段原样不动、cnt==0
NO_BACKWARD = [
    "x = 2.0 * 3.0\ny = x + 1\nx = 10.0\n#1：[y]\n",   # 元凶：旧版把 y 改成 10.0+1
    "y = x + 1\nx = 10\n#1：[y]\n",                     # 纯前向：x 使用前未绑定
    "m = n + 1\nn = 7\n#1：[m]\n",                      # 纯前向
    "s = t\nk = 5\n#1：[s]\n",                          # 前向：k 定义在 s 之后且 s 用未绑定的 t
]


class TestForwardPropagationStillWorks:
    @pytest.mark.parametrize("src,expected,cnt", FWD_OK)
    def test_rule_output(self, engine, src, expected, cnt):
        improved, c = engine._apply_const_propagation(src)
        assert improved == expected
        assert c == cnt

    @pytest.mark.parametrize("src,expected,cnt", FWD_OK)
    def test_safe_candidate_gate(self, engine, src, expected, cnt):
        assert engine._is_safe_candidate(src, expected) is True

    @pytest.mark.parametrize("src,expected,cnt", FWD_OK)
    def test_semantic_equivalence_gate(self, engine, src, expected, cnt):
        assert engine._semantic_equivalent(src, expected) is True

    def test_lhs_binding_never_rewritten(self, engine):
        # 传播只碰使用点：定义行左端与后续同名赋值左端均受 (?![ \t]*=) 保护
        improved, _ = engine._apply_const_propagation("x = 5.0\ny = x\n#1：[y]\n")
        assert improved.startswith("x = 5.0")


class TestNeverBackwardReference:
    @pytest.mark.parametrize("src", NO_BACKWARD)
    def test_untouched(self, engine, src):
        improved, cnt = engine._apply_const_propagation(src)
        assert improved == src
        assert cnt == 0

    def test_smoking_gun_precedence_case_stays_seven(self, engine):
        src = "x = 2.0 * 3.0\ny = x + 1\nx = 10.0\n#1：[y]\n"
        improved, _ = engine._apply_const_propagation(src)
        assert "y = 10.0 + 1" not in improved   # 元凶形态绝迹
        o_out, _ = engine._exec_outputs(src)
        i_out, _ = engine._exec_outputs(improved)
        assert o_out == i_out == [7.0]


class TestRebindingUsesActiveValue:
    def test_second_use_after_rebind_gets_new_value(self, engine):
        src = "x = 4\ny = x\nx = 5\nz = x\n#1：[z]\n"
        improved, cnt = engine._apply_const_propagation(src)
        assert "y = 4" in improved          # 旧活跃值
        assert "z = 5" in improved          # 重绑定后的新活跃值
        assert cnt == 2
        assert engine._semantic_equivalent(src, improved) is True

    def test_nonliteral_rebinding_invalidates(self, engine):
        # x 先=2（字面量），后被重绑定为非字面量表达式 → 其后的使用点不得再用旧值 2
        src = "x = 2\nx = 3.0 * 4.0\ny = x\n#1：[y]\n"
        improved, cnt = engine._apply_const_propagation(src)
        assert "y = x" in improved          # 第 3 行 x 已是非字面量绑定 → 不传播
        assert cnt == 0


class TestStringLiteralGuard:
    def test_identifier_inside_string_preserved(self, engine):
        src = 'a = 5.0\nb = "a a"\n#1：[b]\n'
        improved, cnt = engine._apply_const_propagation(src)
        assert 'b = "a a"' in improved       # 字符串内 a 不被替换
        assert cnt == 0


class TestGrowIntegration:
    @pytest.mark.parametrize("src,expected,cnt", FWD_OK)
    def test_grow_stays_equivalent(self, engine, src, expected, cnt):
        rep = engine.grow(src)
        out = rep.improved_source
        assert engine._semantic_equivalent(src, out) is True

    def test_grow_does_not_corrupt_forward_reference(self, engine):
        src = "x = 2.0 * 3.0\ny = x + 1\nx = 10.0\n#1：[y]\n"
        rep = engine.grow(src)
        assert engine._semantic_equivalent(src, rep.improved_source) is True
