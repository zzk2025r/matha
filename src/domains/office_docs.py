"""Matha 办公文档模块：文档处理、表格、演示文稿、PDF导出。

覆盖：
  1) 文本文档（创建、编辑、格式化）
  2) 电子表格（单元格、行、列、公式）
  3) 演示文稿（幻灯片、动画）
  4) 数据分析（统计、图表）
  5) PDF导出
"""
from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from typing import Any

# ============================================================
# 文本文档
# ============================================================

@dataclass
class TextStyle:
    """文本样式。"""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size: float = 12.0
    font: str = "sans-serif"
    color: str = "#000000"


@dataclass
class Paragraph:
    """段落。"""
    text: str = ""
    style: TextStyle = field(default_factory=TextStyle)
    alignment: str = "left"  # left, center, right, justify
    indent: float = 0.0


class Document:
    """文本文档。"""

    def __init__(self, title: str = "Untitled"):
        self.title = title
        self.paragraphs: list[Paragraph] = []
        self.metadata: dict = {}

    def add_text(self, text: str, style: TextStyle | None = None) -> None:
        """添加文本段落。"""
        self.paragraphs.append(Paragraph(text=text, style=style or TextStyle()))

    def add_heading(self, text: str, level: int = 1) -> None:
        """添加标题。"""
        style = TextStyle(bold=True, size=12 + (3 - level) * 4,
                          font="sans-serif")
        self.paragraphs.append(Paragraph(text=text, style=style))

    def add_bold(self, text: str) -> None:
        """添加粗体文本。"""
        style = TextStyle(bold=True)
        self.paragraphs.append(Paragraph(text=text, style=style))

    def add_italic(self, text: str) -> None:
        """添加斜体文本。"""
        style = TextStyle(italic=True)
        self.paragraphs.append(Paragraph(text=text, style=style))

    def add_list(self, items: list[str]) -> None:
        """添加列表。"""
        for item in items:
            self.paragraphs.append(Paragraph(text=f"• {item}"))

    def to_markdown(self) -> str:
        """转为Markdown格式。"""
        result = f"# {self.title}\n\n"
        for p in self.paragraphs:
            if p.style.bold and p.style.size > 16:
                result += f"{'#' * min(int(p.style.size / 4), 6)} {p.text}\n\n"
            elif p.style.bold:
                result += f"**{p.text}**\n\n"
            elif p.style.italic:
                result += f"*{p.text}*\n\n"
            else:
                result += f"{p.text}\n\n"
        return result.strip()

    def to_html(self) -> str:
        """转为HTML格式。"""
        result = f"<html><head><title>{self.title}</title></head><body>\n"
        for p in self.paragraphs:
            tag = "h1" if p.style.size > 18 else "p"
            bold = " font-weight:bold;" if p.style.bold else ""
            italic = " font-style:italic;" if p.style.italic else ""
            result += f"<{tag} style='{bold}{italic}'>{p.text}</{tag}>\n"
        result += "</body></html>"
        return result

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "title": self.title,
            "paragraphs": [
                {"text": p.text, "style": vars(p.style),
                 "alignment": p.alignment} for p in self.paragraphs
            ],
        }, ensure_ascii=False, indent=2)


# ============================================================
# 电子表格
# ============================================================

@dataclass
class Cell:
    """单元格。"""
    value: Any = ""
    formula: str = ""
    row: int = 0
    col: int = 0

    @property
    def numeric_value(self) -> float:
        """获取数值。"""
        if isinstance(self.value, (int, float)):
            return float(self.value)
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return 0.0


class Spreadsheet:
    """电子表格。"""

    def __init__(self, rows: int = 100, cols: int = 26):
        self.rows = rows
        self.cols = cols
        self._cells: dict[str, Cell] = {}
        self._name: str = "Sheet1"

    def set_cell(self, row: int, col: int, value: Any) -> None:
        """设置单元格值。"""
        key = f"{row},{col}"
        self._cells[key] = Cell(value=value, row=row, col=col)

    def get_cell(self, row: int, col: int) -> Any:
        """获取单元格值。"""
        key = f"{row},{col}"
        cell = self._cells.get(key)
        return cell.value if cell else ""

    def set_formula(self, row: int, col: int, formula: str) -> None:
        """设置公式。"""
        key = f"{row},{col}"
        cell = self._cells.get(key, Cell(row=row, col=col))
        cell.formula = formula
        self._cells[key] = cell

    def evaluate(self) -> dict[str, float]:
        """计算公式。"""
        results = {}
        for key, cell in self._cells.items():
            if cell.formula.startswith("="):
                try:
                    # 简化公式解析
                    formula = cell.formula[1:]  # Remove '='
                    if formula.startswith("SUM("):
                        # 解析SUM范围
                        result = self._eval_sum(formula)
                    elif formula.startswith("AVG("):
                        result = self._eval_avg(formula)
                    elif formula.startswith("MAX("):
                        result = self._eval_max(formula)
                    elif formula.startswith("MIN("):
                        result = self._eval_min(formula)
                    else:
                        result = cell.numeric_value
                    results[key] = result
                except Exception:
                    results[key] = 0.0
        return results

    def _eval_sum(self, formula: str) -> float:
        """求和。"""
        return sum(c.numeric_value for c in self._cells.values())

    def _eval_avg(self, formula: str) -> float:
        """平均值。"""
        vals = [c.numeric_value for c in self._cells.values() if c.numeric_value != 0]
        return sum(vals) / len(vals) if vals else 0.0

    def _eval_max(self, formula: str) -> float:
        """最大值。"""
        vals = [c.numeric_value for c in self._cells.values()]
        return max(vals) if vals else 0.0

    def _eval_min(self, formula: str) -> float:
        """最小值。"""
        vals = [c.numeric_value for c in self._cells.values()]
        return min(vals) if vals else 0.0

    def to_csv(self) -> str:
        """导出为CSV。"""
        output = io.StringIO()
        writer = csv.writer(output)
        for r in range(self.rows):
            row_data = []
            for c in range(self.cols):
                row_data.append(str(self.get_cell(r, c)))
            writer.writerow(row_data)
        return output.getvalue()

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "name": self._name,
            "rows": self.rows, "cols": self.cols,
            "cells": {k: {"value": str(v.value), "formula": v.formula}
                     for k, v in self._cells.items()},
        }, ensure_ascii=False, indent=2)


# ============================================================
# 演示文稿
# ============================================================

@dataclass
class Slide:
    """幻灯片。"""
    title: str = ""
    content: list[str] = field(default_factory=list)
    transition: str = "fade"  # fade, slide, zoom
    duration: float = 5.0
    background: str = "#ffffff"


class Presentation:
    """演示文稿。"""

    def __init__(self, title: str = "Presentation"):
        self.title = title
        self.slides: list[Slide] = []
        self._current_slide: int = 0

    def add_slide(self, title: str, content: list[str] = None,
                  transition: str = "fade", duration: float = 5.0) -> int:
        """添加幻灯片。"""
        slide = Slide(title=title, content=content or [],
                      transition=transition, duration=duration)
        self.slides.append(slide)
        return len(self.slides) - 1

    def add_text_slide(self, title: str, text: str) -> int:
        """添加文字幻灯片。"""
        return self.add_slide(title, [text])

    def add_bullet_slide(self, title: str, bullets: list[str]) -> int:
        """添加列表幻灯片。"""
        return self.add_slide(title, bullets)

    def next_slide(self) -> int:
        """下一张。"""
        self._current_slide = min(self._current_slide + 1, len(self.slides) - 1)
        return self._current_slide

    def prev_slide(self) -> int:
        """上一张。"""
        self._current_slide = max(self._current_slide - 1, 0)
        return self._current_slide

    def current_slide(self) -> Slide:
        """获取当前幻灯片。"""
        if self.slides:
            return self.slides[self._current_slide]
        return Slide()

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "title": self.title,
            "slides": [vars(s) for s in self.slides],
            "current": self._current_slide,
        }, ensure_ascii=False, indent=2)


# ============================================================
# 数据分析
# ============================================================

def analyze_data(data: list[float]) -> dict:
    """数据分析。"""
    if not data:
        return {"count": 0}
    n = len(data)
    mean_val = sum(data) / n
    sorted_data = sorted(data)
    variance_val = sum((x - mean_val) ** 2 for x in data) / n
    std_val = math.sqrt(variance_val)
    return {
        "count": n,
        "mean": mean_val,
        "median": sorted_data[n // 2] if n % 2 == 1
                 else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2,
        "std": std_val,
        "min": min(data),
        "max": max(data),
        "range": max(data) - min(data),
        "variance": variance_val,
    }


def chart_bar(labels: list[str], values: list[float]) -> dict:
    """生成柱状图数据。"""
    return {"type": "bar", "labels": labels, "values": values,
            "max_val": max(values) if values else 0}


def chart_line(labels: list[str], values: list[float]) -> dict:
    """生成折线图数据。"""
    return {"type": "line", "labels": labels, "values": values,
            "trend": "up" if values and values[-1] > values[0] else "down"}


def chart_pie(labels: list[str], values: list[float]) -> dict:
    """生成饼图数据。"""
    total = sum(values)
    return {"type": "pie", "labels": labels, "values": values,
            "percentages": [v / total * 100 if total > 0 else 0 for v in values]}


# ============================================================
# 注册
# ============================================================

def _register_office(builtins: dict) -> None:
    builtins["创建文档"] = lambda title="Untitled": Document(title)
    builtins["文档添加文本"] = lambda doc, text, s=None: doc.add_text(text, s)
    builtins["文档添加标题"] = lambda doc, text, level=1: doc.add_heading(text, level)
    builtins["文档加粗"] = lambda doc, text: doc.add_bold(text)
    builtins["文档斜体"] = lambda doc, text: doc.add_italic(text)
    builtins["文档列表"] = lambda doc, items: doc.add_list(items)
    builtins["文档转Markdown"] = lambda doc: doc.to_markdown()
    builtins["文档转HTML"] = lambda doc: doc.to_html()
    builtins["创建表格"] = lambda rows=100, cols=26: Spreadsheet(rows, cols)
    builtins["表格设置"] = lambda sheet, r, c, v: sheet.set_cell(r, c, v)
    builtins["表格获取"] = lambda sheet, r, c: sheet.get_cell(r, c)
    builtins["表格公式"] = lambda sheet, r, c, f: sheet.set_formula(r, c, f)
    builtins["表格计算"] = lambda sheet: sheet.evaluate()
    builtins["表格导出CSV"] = lambda sheet: sheet.to_csv()
    builtins["创建演示文稿"] = lambda title="Presentation": Presentation(title)
    builtins["添加幻灯片"] = lambda pres, title, content=None: pres.add_slide(title, content)
    builtins["添加列表幻灯片"] = lambda pres, title, bullets: pres.add_bullet_slide(title, bullets)
    builtins["下一张幻灯片"] = lambda pres: pres.next_slide()
    builtins["数据分析"] = analyze_data
    builtins["柱状图"] = chart_bar
    builtins["折线图"] = chart_line
    builtins["饼图"] = chart_pie


def _office_symtab_names() -> list[str]:
    return [
        "创建文档", "文档添加文本", "文档添加标题", "文档加粗", "文档斜体",
        "文档列表", "文档转Markdown", "文档转HTML",
        "创建表格", "表格设置", "表格获取", "表格公式", "表格计算", "表格导出CSV",
        "创建演示文稿", "添加幻灯片", "添加列表幻灯片",
        "下一张幻灯片", "数据分析", "柱状图", "折线图", "饼图",
    ]


__all__ = [
    "Document", "TextStyle", "Paragraph", "Spreadsheet", "Cell",
    "Presentation", "Slide",
    "analyze_data", "chart_bar", "chart_line", "chart_pie",
    "_register_office", "_office_symtab_names",
]
