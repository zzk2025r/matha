# -*- coding: utf-8 -*-
"""
Matha 自然语言定义构建器（Definition Builder）

职责：
  1. 接收自然语言文本
  2. 调用 NLDictionary 提取每个词/短语的跨时代语义
  3. 列明条目：词、各时代语义、当前时代候选定义
  4. 根据当前时代语意确定最终定义
  5. 输出结构化定义列表，供下一阶段转为公式代码

系统架构：
  NL输入 → 语义提取 → 条目列明 → 定义赋予 → 输出DefinitionList
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from src.nl_semantic import NLDictionary, SemanticEntry


# ============================================================
#  定义条目
# ============================================================

@dataclass
class DefinitionItem:
    """一个自然语言条目的完整定义记录。"""
    # 原文
    raw_word: str
    # 各时代语义
    era_semantics: list[SemanticEntry]
    # 当前时代选定的语义（优先当代，次近代/现代，最后最早）
    current_entry: SemanticEntry
    # 根据当前时代语意赋予的定义（自然语言描述）
    definition: str
    # 数学符号
    math_symbol: str
    # 数学表达式（Matha语法）
    math_expr: str
    # 所属领域
    domain: str
    # 歧义标记（若该词有多个时代语义则标记）
    is_ambiguous: bool = False
    # 消歧说明
    disambiguation_note: str = ""


@dataclass
class DefinitionResult:
    """自然语言定义构建的完整结果。"""
    original_text: str
    era: str
    items: list[DefinitionItem]
    # 未识别的词（词典中无记录的词）
    unknown_words: list[str]
    # 整体理解摘要
    summary: str = ""


# ============================================================
#  定义构建器
# ============================================================

class DefinitionBuilder:
    """
    自然语言定义构建器。

    核心流程：
      1. extract() — 从文本提取已知词汇及位置
      2. list_items() — 列明每个词在各时代的语义
      3. assign_definitions() — 根据当前时代赋予定义
      4. build() — 完整管线：理解 → 列明 → 定义
    """

    # 领域关键词 → 默认定义模板（当词典无精确匹配时使用）
    _DOMAIN_TEMPLATES: dict[str, str] = {
        "运动学": "{word}：描述物体运动的快慢与方向变化",
        "几何": "{word}：描述空间图形的大小、形状与位置关系",
        "代数": "{word}：描述数量之间的运算关系",
        "集合论": "{word}：描述元素之间的归属与组合关系",
        "统计": "{word}：描述数据的分布与集中趋势",
        "概率": "{word}：描述事件发生的不确定性程度",
        "机器学习": "{word}：描述模型训练与优化的核心概念",
        "线性代数": "{word}：描述多维空间中的线性结构",
        "NLP": "{word}：描述自然语言处理中的信息表示",
        "逻辑": "{word}：描述概念的精确界定",
    }

    def __init__(self, dictionary: Optional[NLDictionary] = None):
        self.dict = dictionary or NLDictionary()

    # ── 第1步：提取 ──────────────────────────────────────────────

    def extract(self, text: str) -> dict[str, SemanticEntry]:
        """
        从自然语言文本中提取语义映射。

        Args:
            text: 自然语言文本
            era: 目标时代（默认"当代"）

        Returns:
            {词: SemanticEntry}
        """
        return self.dict.build_semantic_map(text)

    # ── 第2步：列明条目 ──────────────────────────────────────────

    def list_items(self, text: str, era: str = "当代") -> list[DefinitionItem]:
        """
        列明每个识别词汇在各时代的语义条目。

        Args:
            text: 自然语言文本
            era: 当前时代

        Returns:
            DefinitionItem 列表
        """
        semantic_map = self.dict.build_semantic_map(text, era=era)
        items = []

        for word, current_entry in semantic_map.items():
            # 获取该词所有时代的语义
            all_eras = self.dict.list_eras(word)

            # 判断是否有歧义（多个时代语义）
            is_ambiguous = len(all_eras) > 1

            # 构建各时代语义描述
            era_desc_lines = []
            for entry in sorted(all_eras, key=lambda e: self._era_order(e.era)):
                line = f"  · [{entry.era}] {entry.meaning}（{entry.math_expr}）"
                era_desc_lines.append(line)
            era_description = "\n".join(era_desc_lines)

            # 消歧说明
            disambiguation_note = ""
            if is_ambiguous:
                eras = [e.era for e in all_eras]
                disambiguation_note = f"该词在{eras}均有语义，当前选用[{current_entry.era}]定义"

            item = DefinitionItem(
                raw_word=word,
                era_semantics=all_eras,
                current_entry=current_entry,
                definition=current_entry.meaning,
                math_symbol=current_entry.math_symbol,
                math_expr=current_entry.math_expr,
                domain=current_entry.domain,
                is_ambiguous=is_ambiguous,
                disambiguation_note=disambiguation_note,
            )
            items.append(item)

        return items

    # ── 第3步：赋予定义 ──────────────────────────────────────────

    def assign_definitions(self, items: list[DefinitionItem]) -> list[DefinitionItem]:
        """
        对每个条目赋予精确的当前时代定义。

        规则：
          1. 若词典已有完整定义，直接使用
          2. 若为领域关键词但词典无精确匹配，使用模板生成
          3. 若词不在词典中，标记为"待定义"

        Args:
            items: DefinitionItem 列表

        Returns:
            赋予定义后的列表
        """
        for item in items:
            # 已有完整定义，直接使用
            if item.current_entry and item.current_entry.meaning:
                item.definition = item.current_entry.meaning
                item.math_symbol = item.current_entry.math_symbol
                item.math_expr = item.current_entry.math_expr
                continue

            # 尝试领域模板
            domain = item.domain
            if domain in self._DOMAIN_TEMPLATES:
                template = self._DOMAIN_TEMPLATES[domain]
                item.definition = template.format(word=item.raw_word)
                item.math_symbol = item.raw_word.lower()
                item.math_expr = f"{item.raw_word.lower()} = ?"
            else:
                # 无法确定定义
                item.definition = f"[待定义] 词'{item.raw_word}'未在词典中找到映射"
                item.math_symbol = ""
                item.math_expr = ""

        return items

    # ── 第4步：完整管线 ──────────────────────────────────────────

    def build(self, text: str, era: str = "当代") -> DefinitionResult:
        """
        完整管线：提取 → 列明 → 赋予定义。

        Args:
            text: 自然语言输入
            era: 目标时代（默认"当代"）

        Returns:
            DefinitionResult
        """
        # 提取语义
        semantic_map = self.dict.build_semantic_map(text, era=era)

        # 识别未理解的词（简单分词后检查）
        known_words = set(semantic_map.keys())
        unknown_words = self._find_unknown_words(text, known_words)

        # 列明条目
        items = self.list_items(text, era=era)

        # 赋予定义
        items = self.assign_definitions(items)

        # 生成摘要
        summary = self._generate_summary(text, items, era)

        return DefinitionResult(
            original_text=text,
            era=era,
            items=items,
            unknown_words=unknown_words,
            summary=summary,
        )

    # ── 辅助方法 ─────────────────────────────────────────────────

    def _find_unknown_words(self, text: str, known_words: set[str]) -> list[str]:
        """找出文本中未识别的词汇。"""
        import re
        # 中文分词：按2-4字连续词匹配，单字不单独计算
        pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}')
        candidates = pattern.findall(text)
        unknown = []
        for word in candidates:
            if word not in known_words and word not in unknown:
                unknown.append(word)
        return unknown

    def _generate_summary(self, text: str, items: list[DefinitionItem], era: str) -> str:
        """生成定义结果摘要。"""
        recognized = len(items)
        ambiguous = sum(1 for it in items if it.is_ambiguous)
        domains = list(set(it.domain for it in items))

        parts = [
            f"输入：'{text}'",
            f"时代：{era}",
            f"识别条目：{recognized}个",
            f"歧义词：{ambiguous}个",
            f"领域：{', '.join(domains)}",
        ]
        return " | ".join(parts)

    @staticmethod
    def _era_order(era: str) -> int:
        """时代排序：先秦 < 汉唐 < 宋元 < 明清 < 近代 < 现代 < 当代"""
        order = {
            "先秦": 0, "汉唐": 1, "宋元": 2, "明清": 3,
            "近代": 4, "现代": 5, "当代": 6,
        }
        return order.get(era, 99)

    def format_output(self, result: DefinitionResult) -> str:
        """
        将定义结果格式化为可读文本。

        输出格式：
          ╔══════════════════════════════════════╗
          │ 自然语言定义构建结果                  │
          ╠══════════════════════════════════════╣
          │ 原文：...                            │
          │ 时代：...                            │
          ╠══════════════════════════════════════╣
          │ 条目列表：                           │
          │ ───────────────────────────────────  │
          │ [1] 速度                             │
          │   ├─ 先秦：...                       │
          │   ├─ 近代：...                       │
          │   └─ 当代（选定）：...               │
          │   定义：...                          │
          │   符号：v                            │
          │   公式：v = ds/dt                    │
          ╚══════════════════════════════════════╝
        """
        lines = []
        lines.append("╔══════════════════════════════════════════════════════╗")
        lines.append(f"│ 自然语言定义构建结果                                  │")
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append(f"│ 原文：{result.original_text:<44}│")
        lines.append(f"│ 时代：{result.era:<46}│")
        lines.append(f"│ 摘要：{result.summary:<44}│")
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append("│ 条目列表：                                            │")

        for i, item in enumerate(result.items, 1):
            lines.append(f"│ ───────────────────────────────────────────────────  │")
            lines.append(f"│ [{i}] {item.raw_word}{' ★歧义' if item.is_ambiguous else ''}{' '*max(0,28-len(item.raw_word)-4)}│")
            lines.append(f"│   ├─ 各时代语义：")
            for entry in sorted(item.era_semantics, key=lambda e: self._era_order(e.era)):
                marker = " ← 选定" if entry == item.current_entry else ""
                lines.append(f"│   │   [{entry.era:4s}] {entry.meaning}{marker}")
            lines.append(f"│   ├─ 定义：{item.definition}")
            lines.append(f"│   ├─ 符号：{item.math_symbol}")
            lines.append(f"│   └─ 公式：{item.math_expr}")

        if result.unknown_words:
            lines.append(f"│ ───────────────────────────────────────────────────  │")
            lines.append(f"│ 未识别词：{', '.join(result.unknown_words)}{' '*max(0,20-len(str(result.unknown_words)))}│")

        lines.append("╚══════════════════════════════════════════════════════╝")
        return "\n".join(lines)


# ============================================================
#  便捷函数
# ============================================================

def build_definitions(text: str, era: str = "当代") -> DefinitionResult:
    """便捷入口：从自然语言构建定义。"""
    builder = DefinitionBuilder()
    return builder.build(text)


def format_definitions(text: str, era: str = "当代") -> str:
    """便捷入口：格式化输出定义结果。"""
    builder = DefinitionBuilder()
    result = builder.build(text, era=era)
    return builder.format_output(result)
