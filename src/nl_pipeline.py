# -*- coding: utf-8 -*-
"""
Matha 自然语言 → 公式代码 统一管线（NL Pipeline）

整合全流程：
  NL输入
    ↓
  [nl_semantic.py]  时代语义词典 — 理解每个词的语义
    ↓
  [nl_definition.py] 定义构建器 — 列明条目 + 赋予当前时代定义
    ↓
  [nl_to_formula.py] 公式转换器 — 定义 → 公式代码
    ↓
  [compiler.py]     编译器 — 公式代码 → 可执行 Matha 代码
    ↓
  [interp.py]       解释器 — 执行代码，返回结果

同时提供：
  - 多时代对比（同一文本在不同时代的定义差异）
  - 歧义检测与报告
  - 公式代码预览
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from src.nl_semantic import NLDictionary
from src.nl_definition import DefinitionBuilder, DefinitionResult, DefinitionItem
from src.nl_to_formula import (
    DefinitionToFormulaConverter,
    FormulaTranslation,
    FormulaCode,
)


# ============================================================
#  管线结果
# ============================================================

@dataclass
class PipelineResult:
    """统一管线的最终输出。"""
    # 原始输入
    original_text: str
    era: str

    # 阶段1：语义理解
    semantic_map: dict[str, str]  # {词: 当前时代语义}

    # 阶段2：定义构建
    definition_result: Optional[DefinitionResult] = None

    # 阶段3：公式转换
    formula_translation: Optional[FormulaTranslation] = None

    # 阶段4：代码生成（占位，后续接入 compiler）
    executable_code: str = ""

    # 歧义报告
    ambiguities: list[dict] = field(default_factory=list)

    # 整体摘要
    summary: str = ""

    def is_complete(self) -> bool:
        """管线是否成功完成。"""
        return (
            self.definition_result is not None
            and self.formula_translation is not None
            and bool(self.formula_translation.formula_codes)
        )

    def has_ambiguities(self) -> bool:
        """是否存在歧义。"""
        return len(self.ambiguities) > 0


# ============================================================
#  统一管线
# ============================================================

class NLPipeline:
    """
    自然语言 → 公式代码 统一管线。

    用法：
      pipeline = NLPipeline()
      result = pipeline.run("速度的定义是位移除以时间")
      print(result.formula_translation.matha_source)
    """

    def __init__(self):
        self._dict = NLDictionary()
        self._builder = DefinitionBuilder(self._dict)
        self._converter = DefinitionToFormulaConverter()

    def run(self, text: str, era: str = "当代") -> PipelineResult:
        """
        执行完整管线。

        Args:
            text: 自然语言输入
            era: 目标时代（默认"当代"）

        Returns:
            PipelineResult
        """
        # ── 阶段1：语义理解 ──────────────────────────────────────
        semantic_map = self._dict.build_semantic_map(text, era=era)
        semantic_desc = {word: entry.meaning for word, entry in semantic_map.items()}

        # ── 阶段2：定义构建 ──────────────────────────────────────
        def_result = self._builder.build(text, era=era)

        # ── 阶段3：公式转换 ──────────────────────────────────────
        formula_trans = self._converter.convert(def_result)

        # ── 歧义检测 ─────────────────────────────────────────────
        ambiguities = self._detect_ambiguities(def_result.items)

        # ── 生成摘要 ─────────────────────────────────────────────
        summary = self._build_summary(text, era, def_result, formula_trans, ambiguities)

        return PipelineResult(
            original_text=text,
            era=era,
            semantic_map=semantic_desc,
            definition_result=def_result,
            formula_translation=formula_trans,
            ambiguities=ambiguities,
            summary=summary,
        )

    def run_multi_era(self, text: str, eras: Optional[list[str]] = None) -> dict[str, PipelineResult]:
        """
        多时代对比：同一文本在不同时代的定义差异。

        Args:
            text: 自然语言输入
            eras: 要对比的时代列表（默认全部）

        Returns:
            {era: PipelineResult}
        """
        if eras is None:
            eras = ["先秦", "汉唐", "宋元", "明清", "近代", "现代", "当代"]

        results = {}
        for era in eras:
            results[era] = self.run(text, era=era)
        return results

    def format_report(self, result: PipelineResult) -> str:
        """
        将管线结果格式化为可读报告。

        输出格式：
          ╔══════════════════════════════════════════════════╗
          │  自然语言 → 公式代码 转换报告                     │
          ╠══════════════════════════════════════════════════╣
          │  原文：...                                       │
          │  时代：...                                       │
          ╠══════════════════════════════════════════════════╣
          │  【阶段1：语义理解】                              │
          │    速度 → 位移对时间的变化率                      │
          │    时间 → ...                                    │
          ╠══════════════════════════════════════════════════╣
          │  【阶段2：定义构建】                              │
          │    [1] 速度                                      │
          │      各时代语义：                                 │
          │        [近代] 位移对时间的变化率 (v = ds/dt)      │
          │      当前定义：位移对时间的变化率                  │
          │      符号：v                                     │
          ╠══════════════════════════════════════════════════╣
          │  【阶段3：公式转换】                              │
          │    let 速度 = v = s / t                          │
          ╠══════════════════════════════════════════════════╣
          │  【歧义报告】                                     │
          │    无歧义                                        │
          ╚══════════════════════════════════════════════════╝
        """
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════╗")
        lines.append("║  自然语言 → 公式代码 转换报告                               ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")
        lines.append(f"║  原文：{result.original_text:<48}║")
        lines.append(f"║  时代：{result.era:<48}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段1：语义理解
        lines.append("║  【阶段1：语义理解】                                        ║")
        for word, meaning in result.semantic_map.items():
            lines.append(f"║    {word:<6} → {meaning:<40}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段2：定义构建
        lines.append("║  【阶段2：定义构建】                                        ║")
        if result.definition_result:
            for i, item in enumerate(result.definition_result.items, 1):
                flag = " ★歧义" if item.is_ambiguous else ""
                lines.append(f"║    [{i}] {item.raw_word}{flag}{' '*(38-len(item.raw_word)-len(flag))}║")
                lines.append(f"║        定义：{item.definition:<45}║")
                lines.append(f"║        符号：{item.math_symbol:<45}║")
                lines.append(f"║        公式：{item.math_expr:<45}║")
        else:
            lines.append("║    （无定义条目）                                            ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段3：公式转换
        lines.append("║  【阶段3：公式转换】                                        ║")
        if result.formula_translation:
            if result.formula_translation.formula_codes:
                for code in result.formula_translation.formula_codes:
                    lines.append(f"║    {code.matha_code:<48}║")
                if result.formula_translation.param_equivalences:
                    lines.append(f"║    参数等价：")
                    for lhs, rhs in result.formula_translation.param_equivalences:
                        lines.append(f"║      {lhs} = {rhs}")
            else:
                lines.append("║    （未生成公式，可能无可识别的数学词汇）                      ║")
            if result.formula_translation.notes:
                for note in result.formula_translation.notes:
                    lines.append(f"║    注：{note:<44}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 歧义报告
        lines.append("║  【歧义报告】                                               ║")
        if result.ambiguities:
            for amb in result.ambiguities:
                lines.append(f"║    ⚠ {amb['word']}: {amb['note']}")
        else:
            lines.append("║    无歧义                                                    ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 完整源码
        lines.append("║  【Matha 源码】                                             ║")
        if result.formula_translation:
            for line in result.formula_translation.matha_source.split("\n"):
                lines.append(f"║    {line:<48}║")
        else:
            lines.append("║    （暂无源码）                                              ║")
        lines.append("╚════════════════════════════════════════════════════════════╝")

        return "\n".join(lines)

    # ── 辅助方法 ──────────────────────────────────────────────────

    def _detect_ambiguities(self, items: list[DefinitionItem]) -> list[dict]:
        """检测定义条目中的歧义。"""
        ambiguities = []
        for item in items:
            if item.is_ambiguous:
                eras = [e.era for e in item.era_semantics]
                ambiguities.append({
                    "word": item.raw_word,
                    "eras": eras,
                    "note": f"在{len(eras)}个时代有不同语义，当前选用[{item.current_entry.era}]",
                })
        return ambiguities

    def _build_summary(
        self,
        text: str,
        era: str,
        def_result: DefinitionResult,
        formula_trans: FormulaTranslation,
        ambiguities: list[dict],
    ) -> str:
        """生成管线摘要。"""
        n_formulas = len(formula_trans.formula_codes)
        n_ambiguities = len(ambiguities)
        status = "成功" if n_formulas > 0 else "无公式生成"
        amb_str = f"，{n_ambiguities}个歧义" if n_ambiguities > 0 else ""
        return f"'{text}' → {era}时代 → {n_formulas}个公式{amb_str} → [{status}]"


# ============================================================
#  便捷函数
# ============================================================

_pipeline: Optional[NLPipeline] = None


def run(text: str, era: str = "当代") -> PipelineResult:
    """便捷入口：执行自然语言→公式代码管线。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    return _pipeline.run(text, era=era)


def report(text: str, era: str = "当代") -> str:
    """便捷入口：格式化输出转换报告。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    result = _pipeline.run(text, era=era)
    return _pipeline.format_report(result)


def multi_era_compare(text: str, eras: Optional[list[str]] = None) -> dict[str, PipelineResult]:
    """多时代对比。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    return _pipeline.run_multi_era(text, eras)
