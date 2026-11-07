# -*- coding: utf-8 -*-
"""
nl_pipeline 阶段4（执行段）行为锁。

口径（KNOWN_ISSUES §7c 编排锁的延伸）：
  - 只背书「纯算术等式 → func 定义 → 经主链 exec_api 真算」这一窄路径；
  - 探针全参数=1.0，仅验证可执行性，不是用户语义答案；
  - 不可翻译的公式（集合/统计/概率/声明）如实跳过并留痕；
  - 执行错误下沉到 execution_error，不抛穿 run()。
"""
from __future__ import annotations

import math

import pytest

from src.nl_pipeline import NLPipeline, run
from src.nl_to_formula import FormulaCode


# ============================================================
#  执行段端到端：真算结果锁
# ============================================================

class TestExecutionEndToEnd:
    def test_velocity_definition_executes(self):
        r = run("速度的定义是位移除以时间")
        assert r.is_complete()
        assert r.execution_error is None
        # 速度 v=s/t、位移 s=v*t，探针(1.0,1.0)均得 1.0
        assert r.outputs == [1.0, 1.0]
        # func 定义行形态锁：只取等式 RHS 作函数体，LHS 变量不进参数列
        assert "func 速度(s, t) -> Float = s / t" in r.executable_code

    def test_force_family_executes(self):
        r = run("力等于质量乘以加速度")
        assert r.execution_error is None
        # 力 F=m*a →1；质量 m=F/a →1；加速度 a=(v-v0)/t →0
        assert r.outputs == [1.0, 1.0, 0.0]

    def test_leading_paren_normalized(self):
        """func 直expr体以 `(` 开头会被解析为 lambda 参数列，须乘单位元规避。"""
        r = run("力等于质量乘以加速度")
        assert "1.0 * (v - v0) / t" in r.executable_code
        assert r.execution_error is None

    def test_power_caret_translated(self):
        r = run("动能等于二分之一乘以质量乘以速度的平方")
        assert r.execution_error is None
        assert r.outputs == [0.5, 1.0, 1.0]
        assert "^" not in r.executable_code
        assert "v ** 2" in r.executable_code

    def test_area_executes(self):
        r = run("长方形面积等于长乘以宽")
        assert r.execution_error is None
        assert r.outputs == [1.0]

    def test_circumference_uses_kernel_pi(self):
        r = run("周长")
        assert r.execution_error is None
        assert len(r.outputs) == 1
        assert math.isclose(r.outputs[0], 2 * math.pi)
        # pi 是内核常量，不应被当成探针参数
        assert "func 周长(r) -> Float = 2 * pi * r" in r.executable_code

    def test_no_math_text_empty_execution(self):
        r = run("今天天气很好")
        assert r.executable_code == ""
        assert r.outputs == []
        assert r.execution_error is None


# ============================================================
#  诚实降级：不可翻译公式跳过留痕
# ============================================================

class TestHonestSkip:
    def test_set_union_skipped_with_note(self):
        r = run("并集的定义是两个集合所有元素的合集")
        assert r.executable_code == ""
        assert r.execution_error is None
        assert any("跳过" in n and "并集" in n for n in r.execution_notes)

    def test_probability_skipped_with_note(self):
        r = run("概率等于事件发生次数除以总次数")
        assert r.executable_code == ""
        assert any("跳过" in n and "概率" in n for n in r.execution_notes)

    def test_mixed_skips_and_executes(self):
        """可执行与不可执行混合：只执行可执行部分，跳过部分留痕。"""
        r = run("力和并集")
        assert r.execution_error is None
        assert r.outputs  # 力可执行
        assert any("跳过" in n for n in r.execution_notes)


# ============================================================
#  _translate_formula 单元拒绝矩阵
# ============================================================

def _code(name: str, expr_text: str, category: str) -> FormulaCode:
    return FormulaCode(
        name=name, params=[], expr=None, expr_text=expr_text,
        matha_code=f"let {name} = {expr_text}", source_item=None,
        category=category,
    )


class TestTranslateFormula:
    def setup_method(self):
        self.pipeline = NLPipeline()

    @pytest.mark.parametrize("name,expr_text,category", [
        ("声明", "x", "declaration"),
        ("并集", "A ∪ B", "set_op"),
        ("标准差", "sigma = sqrt(x)", "general"),   # RHS 含调用 → 拒绝
        ("神经元", "y = sum(w_i * x_i for i in range(n)) + b", "nn"),
        ("优化", "θ := θ - η * grad(L)", "optim"),
        ("概率", "P(A) = |A| / |Omega|", "prob"),
        ("面积", "S = π * r", "area"),               # 非 ASCII RHS → 拒绝
    ])
    def test_rejection_matrix(self, name, expr_text, category):
        assert self.pipeline._translate_formula(_code(name, expr_text, category)) is None

    def test_valid_translation_shape(self):
        func_line, probe = self.pipeline._translate_formula(
            _code("动能", "Ek = 0.5 * m * v ^ 2", "general"))
        assert func_line == "func 动能(m, v) -> Float = 0.5 * m * v ** 2"
        assert probe == "#1：[动能(1.0, 1.0)]"

    def test_category_gate(self):
        # stat/prob/nn/optim/set_op/declaration 类别一律不翻译
        for cat in ("stat", "prob", "nn", "optim", "set_op", "declaration"):
            assert self.pipeline._translate_formula(
                _code("测试", "y = a * b", cat)) is None


# ============================================================
#  错误下沉：执行失败不抛穿 run()
# ============================================================

class TestErrorSinking:
    def test_runtime_error_recorded_not_raised(self, monkeypatch):
        def broken_build(self, trans):
            return ("func 除零式(x) -> Float = x / 0\n#1：[除零式(1.0)]", [])
        monkeypatch.setattr(NLPipeline, "_build_executable", broken_build)
        r = NLPipeline().run("速度")
        assert r.execution_error is not None
        assert "除零" in r.execution_error
        assert r.is_complete()  # 前3阶段不受执行段失败影响


# ============================================================
#  生成代码卫生 & 报告 & 多时代
# ============================================================

class TestCodeHygieneAndReport:
    def test_no_bare_hash_comments(self):
        """Matha 注释只有 (* *)；生成的代码不得出现裸 # 行。"""
        r = run("速度的定义是位移除以时间")
        for line in r.executable_code.splitlines():
            if line.lstrip().startswith("#"):
                assert line.lstrip().startswith("#1：[")

    def test_report_contains_stage4(self):
        p = NLPipeline()
        r = p.run("速度")
        text = p.format_report(r)
        assert "阶段4：执行段" in text
        assert "探针输出" in text

    @pytest.mark.parametrize("word", ["速度", "面积"])
    def test_multi_era_execution_stable(self, word):
        p = NLPipeline()
        results = p.run_multi_era(word)
        assert len(results) == 7
        for era, r in results.items():
            assert r.execution_error is None, era
            assert r.outputs, era


if __name__ == "__main__":
    pytest.main([__file__, "-v"])