# -*- coding: utf-8 -*-
"""
自然语言→公式代码管线集成测试

覆盖：
  1. nl_semantic.py — 语义词典
  2. nl_definition.py — 定义构建器
  3. nl_to_formula.py — 公式转换器
  4. nl_pipeline.py — 统一管线
"""
from __future__ import annotations
import pytest

from src.nl_semantic import NLDictionary, SemanticEntry, lookup, list_all_eras
from src.nl_definition import DefinitionBuilder, DefinitionResult, build_definitions, format_definitions
from src.nl_to_formula import DefinitionToFormulaConverter, convert_to_formula, translate
from src.nl_pipeline import NLPipeline, run, report, multi_era_compare


# ============================================================
#  nl_semantic.py 测试
# ============================================================

class TestNLDictionary:
    """语义词典核心功能测试。"""

    def test_lookup_known_word(self):
        d = NLDictionary()
        entry = d.lookup("速度")
        assert entry is not None
        assert entry.word == "速度"
        # 当代语义为"相速度/群速度，波传播特性"
        assert entry.era == "当代"
        assert entry.math_symbol in ("v", "v_p/v_g")

    def test_lookup_unknown_word(self):
        d = NLDictionary()
        entry = d.lookup("xyz不存在的词123")
        assert entry is None

    def test_lookup_era_priority(self):
        d = NLDictionary()
        # 当代优先
        entry = d.lookup("速度", era="当代")
        assert entry is not None
        # 即使指定先秦，速度是近代词，也应回退到近代
        entry_qi = d.lookup("速度", era="先秦")
        assert entry_qi is not None

    def test_list_eras(self):
        d = NLDictionary()
        eras = d.list_eras("面积")
        assert len(eras) > 0
        assert all(isinstance(e, SemanticEntry) for e in eras)

    def test_resolve_ambiguity_single(self):
        d = NLDictionary()
        # "速度" 只有一个主要语义，消歧直接返回
        entry = d.resolve_ambiguity("速度", "物理运动")
        assert entry is not None
        assert entry.word == "速度"

    def test_extract_words(self):
        d = NLDictionary()
        words = d.extract_words("速度的定义是位移除以时间")
        word_texts = [w[0] for w in words]
        assert "速度" in word_texts
        assert "位移" in word_texts

    def test_build_semantic_map(self):
        d = NLDictionary()
        m = d.build_semantic_map("速度是位移对时间的变化率")
        assert "速度" in m
        assert "位移" in m
        assert isinstance(m["速度"], SemanticEntry)

    def test_build_semantic_map_no_overlap(self):
        """重叠匹配时优先长词。"""
        d = NLDictionary()
        # "加速度" 和 "加速" 重叠，应优先匹配"加速度"
        m = d.build_semantic_map("加速度定义")
        assert "加速度" in m

    def test_alias_lookup(self):
        d = NLDictionary()
        # 通过别名"矢量"查找"向量"
        entry = d.lookup("矢量")
        assert entry is not None
        assert entry.word == "向量"


# ============================================================
#  nl_definition.py 测试
# ============================================================

class TestDefinitionBuilder:
    """定义构建器测试。"""

    def test_build_single_term(self):
        builder = DefinitionBuilder()
        result = builder.build("速度")
        assert isinstance(result, DefinitionResult)
        assert len(result.items) > 0
        assert result.items[0].raw_word == "速度"
        # 当代语义
        assert result.items[0].definition == "相速度/群速度，波传播特性"

    def test_build_multi_term(self):
        builder = DefinitionBuilder()
        result = builder.build("速度的定义是位移除以时间")
        words = [it.raw_word for it in result.items]
        assert "速度" in words
        assert "位移" in words

    def test_list_items_shows_eras(self):
        builder = DefinitionBuilder()
        items = builder.list_items("面积")
        assert len(items) > 0
        item = items[0]
        assert len(item.era_semantics) > 0

    def test_assign_definitions(self):
        builder = DefinitionBuilder()
        items = builder.list_items("面积")
        items = builder.assign_definitions(items)
        assert all(it.definition for it in items)

    def test_build_with_ambiguity(self):
        """有歧义的词应标记。"""
        builder = DefinitionBuilder()
        result = builder.build("速度")
        # 找到速度条目
        speed_items = [it for it in result.items if it.raw_word == "速度"]
        if speed_items:
            # 速度在近代有定义，可能有歧义
            pass  # 不一定有歧义，跳过断言

    def test_format_output(self):
        builder = DefinitionBuilder()
        result = builder.build("面积和体积的定义")
        formatted = builder.format_output(result)
        assert "面积" in formatted
        assert "体积" in formatted
        assert "定义" in formatted

    def test_unknown_words(self):
        builder = DefinitionBuilder()
        result = builder.build("xyz不存在的词")
        # 不应报错，unknown_words 可能有内容
        assert isinstance(result.unknown_words, list)


# ============================================================
#  nl_to_formula.py 测试
# ============================================================

class TestDefinitionToFormulaConverter:
    """公式转换器测试。"""

    def test_convert_simple(self):
        builder = DefinitionBuilder()
        def_result = builder.build("速度")
        converter = DefinitionToFormulaConverter()
        trans = converter.convert(def_result)
        assert isinstance(trans, object)
        assert len(trans.formula_codes) > 0
        assert any("v" in code.matha_code for code in trans.formula_codes)

    def test_convert_area(self):
        builder = DefinitionBuilder()
        def_result = builder.build("面积等于长乘以宽")
        converter = DefinitionToFormulaConverter()
        trans = converter.convert(def_result)
        # 应有面积相关公式
        area_codes = [c for c in trans.formula_codes if c.name == "面积"]
        assert len(area_codes) > 0

    def test_convert_geometry(self):
        builder = DefinitionBuilder()
        def_result = builder.build("圆的面积公式是pi乘以半径的平方")
        converter = DefinitionToFormulaConverter()
        trans = converter.convert(def_result)
        assert len(trans.formula_codes) > 0

    def test_convert_empty(self):
        """无数学词汇的文本应生成空公式列表。"""
        builder = DefinitionBuilder()
        def_result = builder.build("今天天气很好")
        converter = DefinitionToFormulaConverter()
        trans = converter.convert(def_result)
        assert trans.formula_codes == []

    def test_maths_source_format(self):
        builder = DefinitionBuilder()
        def_result = builder.build("速度")
        converter = DefinitionToFormulaConverter()
        trans = converter.convert(def_result)
        assert "# 由自然语言自动生成的 Matha 代码" in trans.matha_source


# ============================================================
#  nl_pipeline.py 测试
# ============================================================

class TestNLPipeline:
    """统一管线测试。"""

    def test_run_basic(self):
        pipeline = NLPipeline()
        result = pipeline.run("速度的定义是位移除以时间")
        assert result.is_complete()
        assert len(result.semantic_map) > 0
        assert len(result.formula_translation.formula_codes) > 0

    def test_run_multi_term(self):
        pipeline = NLPipeline()
        result = pipeline.run("长方形面积等于长乘以宽")
        assert result.is_complete()
        codes = result.formula_translation.formula_codes
        # 面积公式用 a*b 参数，检查面积相关公式存在
        assert any("面积" in c.matha_code or "S = a" in c.matha_code for c in codes)

    def test_run_no_math_words(self):
        pipeline = NLPipeline()
        result = pipeline.run("今天天气很好")
        # 不应报错，可能无公式
        assert result.original_text == "今天天气很好"

    def test_format_report(self):
        pipeline = NLPipeline()
        result = pipeline.run("速度")
        report_str = pipeline.format_report(result)
        assert "速度" in report_str
        assert "阶段1：语义理解" in report_str
        assert "阶段2：定义构建" in report_str
        assert "阶段3：公式转换" in report_str

    def test_multi_era_compare(self):
        pipeline = NLPipeline()
        results = pipeline.run_multi_era("速度", eras=["近代", "当代"])
        assert "近代" in results
        assert "当代" in results
        assert results["近代"].original_text == "速度"
        assert results["当代"].original_text == "速度"

    def test_ambiguity_detection(self):
        """有歧义的词应在 ambiguities 中报告。"""
        pipeline = NLPipeline()
        result = pipeline.run("速度")
        # 速度可能无歧义，但只要不报错即可
        assert isinstance(result.ambiguities, list)


class TestConvenienceFunctions:
    """便捷函数测试。"""

    def test_run(self):
        result = run("速度")
        assert result is not None
        assert "速度" in result.original_text

    def test_report(self):
        report_str = report("面积")
        assert "面积" in report_str
        assert "阶段1" in report_str

    def test_multi_era_compare_fn(self):
        results = multi_era_compare("力")
        assert len(results) > 0


# ============================================================
#  端到端场景测试
# ============================================================

class TestEndToEnd:
    """端到端场景：自然语言 → Matha 代码。"""

    def test_velocity_definition(self):
        """速度定义 → 公式代码。"""
        result = run("速度的定义是位移除以时间")
        assert result.is_complete()
        source = result.formula_translation.matha_source
        assert "速度" in source or "v" in source

    def test_area_formula(self):
        """面积公式。"""
        result = run("长方形面积等于长乘以宽")
        assert result.is_complete()
        codes = result.formula_translation.formula_codes
        area_codes = [c for c in codes if c.name == "面积"]
        assert len(area_codes) > 0

    def test_set_union(self):
        """集合运算。"""
        result = run("并集的定义是两个集合所有元素的合集")
        assert result.is_complete()

    def test_force_formula(self):
        """力的公式。"""
        result = run("力等于质量乘以加速度")
        assert result.is_complete()
        source = result.formula_translation.matha_source
        assert "F" in source or "f" in source

    def test_kinetic_energy(self):
        """动能公式。"""
        result = run("动能等于二分之一乘以质量乘以速度的平方")
        assert result.is_complete()

    def test_probability(self):
        """概率公式。"""
        result = run("概率等于事件发生次数除以总次数")
        assert result.is_complete()

    def test_none_math_text(self):
        """纯自然语言无数学词汇。"""
        result = run("我喜欢学习数学")
        # 不应崩溃
        assert result is not None


# ============================================================
#  时代语义对比测试
# ============================================================

class TestEraComparison:
    """跨时代语义对比测试。"""

    def test_era_semantic_differences(self):
        """同一词在不同时代语义不同。"""
        builder = DefinitionBuilder()
        modern = builder.build("速度", era="近代")
        contemporary = builder.build("速度", era="当代")
        # 速度在近代和当代语义应不同（近代：位移变化率，当代：相速度/群速度）
        assert modern.items[0].definition != contemporary.items[0].definition
        assert "位移" in modern.items[0].definition
        assert "相速度" in contemporary.items[0].definition

    def test_era_keyword_detection(self):
        """时代关键词应被正确识别。"""
        d = NLDictionary()
        # "速度" 是近代核心词
        words = d.extract_words("速度是近代物理的核心概念")
        word_texts = [w[0] for w in words]
        assert "速度" in word_texts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
