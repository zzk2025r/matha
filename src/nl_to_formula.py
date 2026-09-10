# -*- coding: utf-8 -*-
"""
Matha 自然语言定义 → 公式代码转换器（Definition-to-Formula Compiler）

职责：
  1. 接收 DefinitionResult（定义条目列表）
  2. 将每个条目的定义转化为 Matha 公式代码
  3. 处理参数映射与等价关系
  4. 输出可执行的 Matha 源码

转换规则：
  - 物理量 → 变量声明（let v = ?）
  - 运算关系 → 公式表达式（let S = a * b）
  - 集合运算 → Matha 集合语法（let A = {1,2,3}）
  - 函数关系 → 公式声明（def f(x) = ...）
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from src.nl_definition import DefinitionItem, DefinitionResult
from src.symbolic import to_expr, Expr, Var, Num, Add, Mul, Div, Pow, Sub, Neg


# ============================================================
#  公式代码节点
# ============================================================

@dataclass
class FormulaCode:
    """转换后的单个公式代码节点。"""
    name: str                    # 公式名（中文）
    params: list[str]            # 参数名列表
    expr: Optional[Expr]         # 符号表达式（None 表示仅声明）
    expr_text: str               # 表达式文本
    matha_code: str              # 生成的 Matha 源码行
    source_item: Optional[DefinitionItem]  # 来源条目
    category: str = "general"    # 分类


@dataclass
class FormulaTranslation:
    """完整转换结果。"""
    original_text: str
    era: str
    formula_codes: list[FormulaCode]
    # 参数等价关系（如 长=底, 宽=高）
    param_equivalences: list[tuple[str, str]]
    # Matha 完整源码
    matha_source: str
    # 转换说明
    notes: list[str] = field(default_factory=list)


# ============================================================
#  公式匹配库（预置常见公式模板）
# ============================================================

# 领域 → 公式模板 {领域关键词: (param_names, expr_text, category)}
_FORMULA_TEMPLATES: dict[str, list[tuple[list[str], str, str]]] = {
    "运动学": [
        (["v", "t", "s"], "v = s / t", "linear"),
        (["v0", "a", "t"], "v = v0 + a * t", "linear"),
        (["v0", "a", "t"], "s = v0 * t + 0.5 * a * t ^ 2", "linear"),
        (["v", "a", "s"], "v ^ 2 = v0 ^ 2 + 2 * a * s", "linear"),
    ],
    "动力学": [
        (["m", "a"], "F = m * a", "linear"),
        (["m", "v"], "p = m * v", "linear"),
        (["m", "v"], "Ek = 0.5 * m * v ^ 2", "linear"),
        (["m", "g", "h"], "Ep = m * g * h", "linear"),
        (["F", "s"], "W = F * s", "linear"),
    ],
    "几何": [
        (["a", "b"], "S = a * b", "area"),
        (["a", "h"], "S = a * h", "area"),
        (["a", "h"], "S = a * h / 2", "area"),
        (["r"], "C = 2 * pi * r", "perimeter"),
        (["r"], "S = pi * r ^ 2", "area"),
        (["a", "b", "c"], "V = a * b * c", "volume"),
        (["r"], "V = 4 / 3 * pi * r ^ 3", "volume"),
    ],
    "集合论": [
        (["A", "B"], "A ∪ B", "set_op"),
        (["A", "B"], "A ∩ B", "set_op"),
        (["A", "B"], "A ⊖ B", "set_op"),
        (["A", "B"], "A × B", "set_op"),
    ],
    "统计": [
        (["x_list"], "μ = sum(x_list) / len(x_list)", "stat"),
        (["x_list", "μ"], "σ = sqrt(sum((x - μ) ^ 2 for x in x_list) / n)", "stat"),
    ],
    "概率": [
        (["A", "Omega"], "P(A) = |A| / |Omega|", "prob"),
    ],
    "机器学习": [
        (["w", "x", "b"], "y = sum(w_i * x_i for i in range(n)) + b", "nn"),
        (["L", "θ", "η"], "θ := θ - η * grad(L)", "optim"),
        (["Q", "K", "V"], "Attn = softmax(Q * K^T / sqrt(d)) * V", "nn"),
    ],
}

# 词 → 直接公式映射（词典中 math_expr 的规范化版本）
_DIRECT_FORMULA_MAP: dict[str, str] = {
    "速度": "v = s / t",
    "加速度": "a = (v - v0) / t",
    "位移": "s = v * t",
    "力": "F = m * a",
    "质量": "m = F / a",
    "功": "W = F * s",
    "动能": "Ek = 0.5 * m * v ^ 2",
    "势能": "Ep = m * g * h",
    "动量": "p = m * v",
    "面积": "S = a * b",
    "周长": "C = 2 * pi * r",
    "体积": "V = a * b * c",
    "半径": "r = d / 2",
    "直径": "d = 2 * r",
    "并集": "A ∪ B",
    "交集": "A ∩ B",
    "差集": "A ⊖ B",
    "子集": "A ⊆ B",
    "笛卡尔积": "A × B",
    "平均": "μ = sum(x) / n",
    "标准差": "σ = sqrt(sum((x - μ) ^ 2) / n)",
    "概率": "P(A) = count(A) / count(Ω)",
}


# ============================================================
#  公式转换器
# ============================================================

class DefinitionToFormulaConverter:
    """
    将 DefinitionResult 中的定义条目转换为 Matha 公式代码。

    流程：
      1. 对每个 DefinitionItem，查找匹配的公式模板或直接映射
      2. 生成 Matha 源码行
      3. 收集参数等价关系
      4. 输出完整 FormulaTranslation
    """

    def __init__(self):
        self._known_formulas: dict[str, FormulaCode] = {}

    def convert(self, result: DefinitionResult) -> FormulaTranslation:
        """
        完整转换：DefinitionResult → FormulaTranslation。

        Args:
            result: DefinitionResult（定义构建器输出）

        Returns:
            FormulaTranslation
        """
        formula_codes = []
        equivalences = []
        notes = []

        for item in result.items:
            code = self._convert_item(item)
            if code:
                formula_codes.append(code)
                self._known_formulas[item.raw_word] = code

        # 检测参数等价（同名不同词的参数）
        equivalences = self._detect_param_equivalences(formula_codes)

        # 生成完整 Matha 源码
        matha_source = self._generate_source(formula_codes, equivalences)

        if not formula_codes:
            notes.append("未生成任何公式，可能原因：文本中无可识别的数学词汇")

        return FormulaTranslation(
            original_text=result.original_text,
            era=result.era,
            formula_codes=formula_codes,
            param_equivalences=equivalences,
            matha_source=matha_source,
            notes=notes,
        )

    def _convert_item(self, item: DefinitionItem) -> Optional[FormulaCode]:
        """将单个定义条目转换为公式代码节点。"""
        word = item.raw_word
        domain = item.domain
        expr_text = item.math_expr

        # 第1优先：直接公式映射
        if word in _DIRECT_FORMULA_MAP:
            ft = _DIRECT_FORMULA_MAP[word]
            return self._make_code(word, ft, item)

        # 第2优先：领域模板匹配
        if domain in _FORMULA_TEMPLATES:
            templates = _FORMULA_TEMPLATES[domain]
            # 取第一个匹配
            param_names, expr, cat = templates[0]
            return self._make_code(word, expr, item, params=param_names, category=cat)

        # 第3优先：尝试解析 math_expr
        if expr_text and expr_text != "—" and expr_text:
            # 尝试解析为表达式
            parsed = self._try_parse_expr(expr_text)
            if parsed:
                expr_str = self._expr_to_matha(parsed)
                return self._make_code(word, expr_str, item)

        # 第4优先：仅声明变量
        symbol = item.math_symbol
        if symbol and symbol not in ("—", "", "?"):
            code = f"let {symbol} = ?"
            return FormulaCode(
                name=word,
                params=[],
                expr=None,
                expr_text=symbol,
                matha_code=code,
                source_item=item,
                category="declaration",
            )

        return None

    def _make_code(
        self,
        name: str,
        expr_text: str,
        item: DefinitionItem,
        params: Optional[list[str]] = None,
        category: str = "general",
    ) -> FormulaCode:
        """创建 FormulaCode 节点。"""
        # 解析表达式
        expr = self._try_parse_expr(expr_text)
        # 生成 Matha 源码
        if params:
            param_str = ", ".join(params)
            matha_code = f"let {name}({param_str}) = {expr_text}"
        else:
            matha_code = f"let {name} = {expr_text}"

        return FormulaCode(
            name=name,
            params=params or [],
            expr=expr,
            expr_text=expr_text,
            matha_code=matha_code,
            source_item=item,
            category=category,
        )

    def _try_parse_expr(self, text: str) -> Optional[Expr]:
        """尝试将文本解析为 Expr。"""
        if not text or text in ("—", "", "?"):
            return None
        try:
            # 替换中文符号为数学符号
            normalized = text
            normalized = normalized.replace("×", "*").replace("÷", "/")
            normalized = normalized.replace("∪", "union").replace("∩", "intersect")
            normalized = normalized.replace("⊖", "diff").replace("⊆", "subset")
            # 尝试用 to_expr 解析
            return to_expr(normalized)
        except Exception:
            return None

    @staticmethod
    def _expr_to_matha(expr: Expr) -> str:
        """将 Expr 转换为 Matha 表达式文本。"""
        return str(expr)

    def _detect_param_equivalences(
        self, codes: list[FormulaCode]
    ) -> list[tuple[str, str]]:
        """
        检测同名不同词的参数等价关系。

        例如：长方形面积的"长"与平行四边形面积的"底"都映射为变量 a
        → 等价关系：长方形.长 = 平行四边形.底
        """
        eqs: list[tuple[str, str]] = []
        # 收集所有公式的参数绑定
        param_to_formulas: dict[str, list[str]] = {}
        for code in codes:
            for p in code.params:
                param_to_formulas.setdefault(p, []).append(code.name)

        # 找出被多个公式共享的参数
        for param, names in param_to_formulas.items():
            if len(names) >= 2:
                for i in range(len(names) - 1):
                    eqs.append((names[i], names[i + 1]))

        return eqs

    def _generate_source(
        self,
        codes: list[FormulaCode],
        equivalences: list[tuple[str, str]],
    ) -> str:
        """生成完整的 Matha 源码。"""
        lines = []
        lines.append(f"# 由自然语言自动生成的 Matha 代码")
        lines.append(f"# 原文：'{codes[0].source_item.raw_word if codes and codes[0].source_item else '—'}'")
        lines.append("")

        # 参数等价声明
        if equivalences:
            lines.append("# 参数等价关系")
            for lhs, rhs in equivalences:
                lines.append(f"# let {lhs} = {rhs}")
            lines.append("")

        # 公式声明
        lines.append("# 公式定义")
        for code in codes:
            lines.append(code.matha_code)

        return "\n".join(lines)


# ============================================================
#  便捷函数
# ============================================================

def convert_to_formula(result: DefinitionResult) -> FormulaTranslation:
    """便捷入口：DefinitionResult → FormulaTranslation"""
    converter = DefinitionToFormulaConverter()
    return converter.convert(result)


def translate(text: str, era: str = "当代") -> FormulaTranslation:
    """
    端到端翻译：自然语言 → Matha 公式代码。

    内部调用：
      DefinitionBuilder.build() → DefinitionToFormulaConverter.convert()
    """
    from src.nl_definition import DefinitionBuilder
    builder = DefinitionBuilder()
    def_result = builder.build(text, era=era)
    converter = DefinitionToFormulaConverter()
    return converter.convert(def_result)
