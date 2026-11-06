# -*- coding: utf-8 -*-
"""成长系统·改写等价验证通路锁（Tier 1·S4 → G-1 真修复）。

沿革：
  S4 坐实 `_verify` 不再是「恒 False 的 phantom」——按真实契约以 dict 调用验证器。
  G-1 审计发现更深层错配：S4 所走的 `CrossLanguageVerifier` `"python"` 通道实为
  `src/mir2_frontend.py::PythonFrontend`，其 `compile` 是 `ast.parse(source)`——**Python 子集**
  前端；而 `grow` 的输入域是 **Matha 源码**（P1 闸门用 `src.parser.parse`）。真实 Matha
  构造（`func` / `let` / 中文函数名）在该前端直接 SyntaxError → 两侧不可运行 → 字段对
  真实 Matha 程序结构性恒 False、不携带信息（见 docs/KNOWN_ISSUES.md §7c G-1）。
  本片（真修复）把 `_verify` 改走 Matha 主链，并把名不副实的
  `GrowthReport.cross_language_consistent` 如实改名为 `semantic_consistent`。

锁定判据（`_verify` 现口径：保守，只收紧不放松）：
  ① 通路正确：走主链 `_exec_outputs`（`src.parser` + `src.interp.Interpreter`），
     不再持有/依赖 `CrossLanguageVerifier`（死接线已移除，不残留误导依赖）。
  ② 真实通路对 **Matha** 程序可得 True：同文恒等、合法恒等元改写、交换律改写、let 等价。
  ③ 该判破：改写破坏可观测输出 → False（这是 G-1 修复的核心增益，旧通道连跑都跑不起来）。
  ④ 诚实降级：任一侧坏码 / 无输出对（G-2 空对空假阳性）/ 一侧有输出另一侧无 → False。
  ⑤ 反假阳性不变量（与用哪个通道无关，S4→G-1 修复前后均须成立）。
  ⑥ grow 集成：字段为真实 bool、对真实 Matha 程序有信息量；出码安全仍只靠 P1（不依赖此字段）。

全程离线、毫秒级、无文件副作用、不污染进程级单例（每个测试新建引擎 / 用局部替身）。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine

# ── python 子集写法（旧通道的适用面；主链同样能跑，故锁保留）──
VALID_ORIG = "x = 3.0 + 4.0\n#1：[x]\n"
VALID_IMPROVED = "x = 7.0\n#1：[x]\n"
BROKEN_UNCLOSED = "x = (3.0 + 4.0\n"  # 括号未闭合 → 解析失败
GARBAGE = "\x00 not matha @@@ ###\n"  # 含 null 字节 → 解析失败

# ── 真实 Matha 构造（G-1 前在该通道一律跑不到，故旧锁无从判破）──
MATHA_FUNC = "func f(x) -> Int = x + 1\nprint(f(2))\n"
MATHA_FUNC_SAME = "func f(x) -> Int = x + 1\nprint(f(2))\n"
MATHA_FUNC_IDENT = "func f(x) -> Int = x + 1 + 0\nprint(f(2))\n"   # 恒等元改写，值不变
MATHA_FUNC_DIFF = "func f(x) -> Int = x + 99\nprint(f(2))\n"       # 破坏输出
CJK_ORIG = "func 加(x, y) -> Int = x + y\nprint(加(1, 2))\n"
CJK_COMMUTED = "func 加(x, y) -> Int = y + x\nprint(加(1, 2))\n"    # 交换律，值不变
CJK_BROKEN = "func 加(x, y) -> Int = x - y\nprint(加(1, 2))\n"      # 破坏输出
LET_ORIG = "let a = 3\nlet b = a * 2\nprint(b)\n"
LET_REWRITE = "let a = 3\nlet b = a + a\nprint(b)\n"
MATHA_FUNC_NOOUT = "func f(x) -> Int = x + 1\n"                 # 无可观测输出
MATHA_FUNC_NOOUT_DIFF = "func f(x) -> Int = x + 99\n"


class TestMainChainWiring:
    """① 通路：改走 Matha 主链，旧验证器死接线已移除。"""

    def test_uses_main_chain_executor(self, monkeypatch):
        e = MathaGrowthEngine()
        seen: list[str] = []

        def fake_exec(source: str):
            seen.append(source)
            return [7.0], None

        monkeypatch.setattr(e, "_exec_outputs", fake_exec)
        assert e._verify(VALID_ORIG, VALID_IMPROVED) is True
        assert seen == [VALID_ORIG, VALID_IMPROVED], "两侧应各经主链执行一次"

    def test_no_stale_verifier_wiring(self):
        # 旧 `self._verifier` 属未使用的死接线（核心不该再拖归档 MIR 后端依赖）。
        assert not hasattr(MathaGrowthEngine(), "_verifier")

    def test_module_no_longer_imports_cross_language_verifier(self):
        import src.matha_growth as mg
        assert not hasattr(mg, "CrossLanguageVerifier")


class TestRealMathaEquivalence:
    """②③ 真修复增益：对真实 Matha 程序能真判等、也能真判破。"""

    def test_identical_matha_func_is_true(self):
        # 同文也走真实执行（无捷径）：两侧跑出 [3] → 判等。
        assert MathaGrowthEngine()._verify(MATHA_FUNC, MATHA_FUNC_SAME) is True

    def test_legal_identity_rewrite_stays_equivalent(self):
        # x + 1 → x + 1 + 0：可观测输出仍为 [3] → 判等。
        assert MathaGrowthEngine()._verify(MATHA_FUNC, MATHA_FUNC_IDENT) is True

    def test_behavior_breaking_rewrite_is_caught(self):
        # 旧通道对 func 无从执行 → 只能诚实 False；主链下这是「真判破」。
        assert MathaGrowthEngine()._verify(MATHA_FUNC, MATHA_FUNC_DIFF) is False

    def test_cjk_identifier_commutation_equivalent(self):
        assert MathaGrowthEngine()._verify(CJK_ORIG, CJK_COMMUTED) is True

    def test_cjk_broken_not_equivalent(self):
        assert MathaGrowthEngine()._verify(CJK_ORIG, CJK_BROKEN) is False

    def test_let_program_equivalence(self):
        assert MathaGrowthEngine()._verify(LET_ORIG, LET_REWRITE) is True

    def test_python_dialect_pair_still_true(self):
        # 旧通道的适用面（python 子集写法）在主链下结论不变，防回归。
        assert MathaGrowthEngine()._verify(VALID_ORIG, VALID_IMPROVED) is True


class TestHonestDegradation:
    """④ 任一侧坏码 / 无可见输出 / 输出数不对称 → 诚实 False，绝不信 `[] == []`。"""

    def test_improved_broken_is_false(self):
        assert MathaGrowthEngine()._verify(VALID_ORIG, BROKEN_UNCLOSED) is False

    def test_original_broken_is_false(self):
        assert MathaGrowthEngine()._verify(BROKEN_UNCLOSED, VALID_ORIG) is False

    def test_both_garbage_is_false(self):
        assert MathaGrowthEngine()._verify(GARBAGE, GARBAGE) is False

    def test_identical_but_unobservable_is_false(self):
        # 无同文捷径的两面：同文垃圾跑不起来 → False；同文合法但无可见输出 → 也无从证等价。
        assert MathaGrowthEngine()._verify(MATHA_FUNC_NOOUT, MATHA_FUNC_NOOUT) is False

    def test_matha_broken_body_is_false(self):
        assert MathaGrowthEngine()._verify(MATHA_FUNC, "func f(x) -> Int =\n") is False

    def test_vacuous_no_output_pair_is_false(self):
        # G-2：两侧都无可见输出、语义不同 → 不得因 `[] == []` 误报一致。
        assert MathaGrowthEngine()._verify(
            MATHA_FUNC_NOOUT, MATHA_FUNC_NOOUT_DIFF) is False

    def test_one_side_silent_is_false(self):
        assert MathaGrowthEngine()._verify("print(1)\n", "x = 1\n") is False


class TestAntiFalsePositiveInvariants:
    """⑤ 与验证通道实现无关的反假阳性不变量（S4→G-1 修复前后均须成立）。"""

    def test_differing_matha_func_never_claimed_consistent(self):
        assert MathaGrowthEngine()._verify(MATHA_FUNC, MATHA_FUNC_DIFF) is False

    def test_no_observed_output_is_not_vacuous_true(self):
        assert MathaGrowthEngine()._verify(
            MATHA_FUNC_NOOUT, MATHA_FUNC_NOOUT_DIFF) is False

    def test_grow_on_real_matha_returns_bool_not_crash(self):
        rep = MathaGrowthEngine().grow(MATHA_FUNC)
        assert isinstance(rep.semantic_consistent, bool)


class TestGrowIntegration:
    """⑥ grow 集成：字段真实且对 Matha 程序有信息量；安全仍只靠 P1。"""

    def test_report_field_is_real_bool(self):
        rep = MathaGrowthEngine().grow(VALID_ORIG)
        assert isinstance(rep.semantic_consistent, bool)

    def test_field_informative_on_real_matha(self):
        # G-1 前的核心症状是「对 func/let 结构性恒 False」；现应可为 True。
        assert MathaGrowthEngine().grow(MATHA_FUNC).semantic_consistent is True

    def test_old_misleading_field_name_gone(self):
        rep = MathaGrowthEngine().grow(VALID_ORIG)
        assert not hasattr(rep, "cross_language_consistent")

    def test_grow_safety_independent_of_verify(self):
        # 无论 semantic_consistent 取值，grow 出码恒可解析或不丢名（P1 兜底）。
        e = MathaGrowthEngine()
        for src in [VALID_ORIG, "x = temp_a\ny = x + 1\n", BROKEN_UNCLOSED]:
            rep = e.grow(src)
            assert rep.improved_source == src or e._is_safe_candidate(src, rep.improved_source)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
