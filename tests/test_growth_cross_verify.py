# -*- coding: utf-8 -*-
"""成长系统·交叉验证真实通路锁（Tier 1·S4）。

坐实 `_verify` / `cross_language_consistent` 不再是「恒 False 的 phantom」：
  ① 契约正确：以 `{'python': <源码>}` dict（而非裸 str）调用 CrossLanguageVerifier.verify；
  ② 真实通路：改写前后两侧均能经前端编译执行且输出相等 → True（非恒 False）；
  ③ 诚实降级：任一侧坏码 / 前端不可用 / 调用抛异常 → False（绝不误报为一致）；
  ④ 不读假阳性字段 `result.consistent`（其默认 True、单语言场景不可信）；
  ⑤ grow 出码的 cross_language_consistent 是真实 bool，且 grow 安全仍只靠 P1（不依赖此字段）。

另附加锁（G-1/G-2 审计后补）：只锁定**与验证通道实现无关**的反假阳性不变量（见
TestG1G2AntiFalsePositive），故无论 `_verify` 走当前 python 子集前端（G-1 未修）还是改走
Matha 主链（真修复切片），这几条必须恒成立。

全程离线、毫秒级、无文件副作用、不污染进程级单例（每个测试新建引擎 / 用局部替身）。
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine

VALID_ORIG = "x = 3.0 + 4.0\n#1：[x]\n"
VALID_IMPROVED = "x = 7.0\n#1：[x]\n"
BROKEN_UNCLOSED = "x = (3.0 + 4.0\n"  # 括号未闭合 → python 前端 SyntaxError → success=False
GARBAGE = "\x00 not matha @@@ ###\n"  # 含 null 字节 → 前端失败

# ── 真实 Matha 构造（当前 python 子集前端吃不下：G-1）──
MATHA_FUNC = "func f(x) -> Int = x + 1\nprint(f(2))\n"
MATHA_FUNC_DIFF = "func f(x) -> Int = x + 99\nprint(f(2))\n"
MATHA_FUNC_NOOUT = "func f(x) -> Int = x + 1\n"
MATHA_FUNC_NOOUT_DIFF = "func f(x) -> Int = x + 99\n"


class _RecordingVerifier:
    """替身：记录 verify 收到的入参，用于锁死「按 dict 契约调用」这一根因。"""

    def __init__(self, consistent_flag=True):
        self.calls = []

    def verify(self, algorithm, sources):
        self.calls.append((algorithm, sources))

        class _LR:
            success = True
            vm_outputs = []

        class _Res:
            consistent = consistent_flag  # 陷阱字段：单语言默认 True

            def __init__(self):
                self.languages = {"python": _LR()}

        return _Res()


class TestContract:
    """① 契约：传入语言→源码 dict，algorithm 为 str，绝不再传裸 str 当 sources。"""

    def test_sources_is_dict_not_str(self):
        e = MathaGrowthEngine()
        rec = _RecordingVerifier()
        e._verifier = rec  # 仅替换本实例私有成员，不触全局单例
        e._verify(VALID_ORIG, VALID_IMPROVED)
        assert rec.calls, "verify 应被调用"
        for algorithm, sources in rec.calls:
            assert isinstance(algorithm, str)
            assert isinstance(sources, dict), "sources 必须是 dict（旧 phantom 传 str 触发 .items() 抛错）"
            assert all(isinstance(v, str) for v in sources.values())

    def test_no_longer_raises_on_bare_str(self):
        # 旧实现把 improved(str) 当 sources → sources.items() 抛错被吞 → 恒 False。
        # 新实现不抛，且真实通路可得 True。
        e = MathaGrowthEngine()
        assert e._verify(VALID_ORIG, VALID_IMPROVED) is True


class TestRealPathAndDegradation:
    """②③④ 真实通路可得 True；坏码/不可用诚实 False；不读 consistent 假阳性。"""

    def test_both_valid_is_true(self):
        assert MathaGrowthEngine()._verify(VALID_ORIG, VALID_IMPROVED) is True

    def test_improved_broken_is_false(self):
        assert MathaGrowthEngine()._verify(VALID_ORIG, BROKEN_UNCLOSED) is False

    def test_original_broken_is_false(self):
        assert MathaGrowthEngine()._verify(BROKEN_UNCLOSED, VALID_ORIG) is False

    def test_both_garbage_is_false(self):
        assert MathaGrowthEngine()._verify(GARBAGE, GARBAGE) is False

    def test_does_not_trust_consistent_default_true(self):
        # 真实判据基于 per-language success + vm_outputs；
        # 若坏码一侧前端失败，即便 result.consistent 默认 True 也必须判 False。
        e = MathaGrowthEngine()
        assert e._verify(VALID_ORIG, BROKEN_UNCLOSED) is False


class TestGrowIntegration:
    """⑤ grow 出码的 cross_language_consistent 为真实 bool；grow 安全不依赖它。"""

    def test_report_field_is_real_bool(self):
        rep = MathaGrowthEngine().grow(VALID_ORIG)
        assert isinstance(rep.cross_language_consistent, bool)

    def test_report_no_longer_phantom_always_false(self):
        # 至少存在一个真实输入使 well-formed 改写判定为 True（旧版恒 False）。
        found_true = False
        for src in [VALID_ORIG, "x = 2.0 * 3.0\n#1：[x]\n", "a = 5.0\nb = a\n#1：[b]\n"]:
            if MathaGrowthEngine()._verify(src, src):
                found_true = True
                break
        assert found_true, "真实通路应可使一致判定为 True，不能退回恒 False phantom"

    def test_grow_safety_independent_of_verify(self):
        # 无论 cross_language_consistent 取值，grow 出码恒可解析或不丢名（P1 兜底）。
        e = MathaGrowthEngine()
        for src in [VALID_ORIG, "x = temp_a\ny = x + 1\n", BROKEN_UNCLOSED]:
            rep = e.grow(src)
            assert rep.improved_source == src or e._is_safe_candidate(src, rep.improved_source)


class TestG1G2AntiFalsePositive:
    """G-1/G-2 反假阳性不变量锁：与「用哪个通道验证」无关，修复前后均须成立。"""

    def test_differing_matha_func_never_claimed_consistent(self):
        # ① 语义不同的真实 Matha 程序，无论如何不得判 True。
        #    当前通道：两侧不可运行 → False；主链修复后：输出 [3] vs [101] → 仍 False。
        assert MathaGrowthEngine()._verify(MATHA_FUNC, MATHA_FUNC_DIFF) is False

    def test_no_observed_output_is_not_vacuous_true(self):
        # ② G-2：两侧都无可观测输出且语义不同时，不得因 `[] == []` 而误报一致。
        assert MathaGrowthEngine()._verify(MATHA_FUNC_NOOUT, MATHA_FUNC_NOOUT_DIFF) is False

    def test_python_dialect_valid_pair_still_true(self):
        # ③ 当前通道的实际适用边界佐证：python 子集写法可得 True（缺口仅在 Matha 构造）。
        assert MathaGrowthEngine()._verify(VALID_ORIG, VALID_IMPROVED) is True

    def test_grow_on_real_matha_returns_bool_not_crash(self):
        # ④ grow 真实 Matha 源码时，该字段必为 bool（诚实降级）且不裸抛。
        rep = MathaGrowthEngine().grow(MATHA_FUNC)
        assert isinstance(rep.cross_language_consistent, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
