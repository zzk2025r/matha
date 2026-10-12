"""Matha 数据可视化：图表生成、数据可视化（类似 Matplotlib）。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class ChartType(Enum):
    """图表类型。"""
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    PIE = "pie"
    HEATMAP = "heatmap"
    BOX = "box"


@dataclass
class PlotData:
    """绘图数据。"""
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    label: str = ""
    color: str = "blue"


@dataclass
class Figure:
    """图表。"""
    title: str = ""
    chart_type: ChartType = ChartType.LINE
    data: list[PlotData] = field(default_factory=list)
    width: int = 800
    height: int = 600
    x_label: str = ""
    y_label: str = ""
    legend: bool = True

    def to_json(self) -> str:
        """转换为 JSON。"""
        return json.dumps({
            "title": self.title,
            "type": self.chart_type.value,
            "data": [{"x": d.x, "y": d.y, "label": d.label} for d in self.data],
            "width": self.width,
            "height": self.height,
            "x_label": self.x_label,
            "y_label": self.y_label,
        }, ensure_ascii=False)

    def save(self, path: str) -> bool:
        """保存图表到文件。"""
        try:
            with open(path, "w") as f:
                f.write(self.to_json())
            return True
        except Exception:
            return False


class MathaPlotter:
    """Matha 绘图器。"""

    def __init__(self):
        self._figures: list[Figure] = []
        self._initialized = False
        self._init_plotter()

    def _init_plotter(self) -> None:
        """初始化绘图器。"""
        self._initialized = True

    def line(self, x: list[float], y: list[float],
                title: str = "", label: str = "",
                color: str = "blue") -> Figure:
        """折线图。"""
        fig = Figure(title=title, chart_type=ChartType.LINE)
        fig.data.append(PlotData(x=x, y=y, label=label, color=color))
        self._figures.append(fig)
        return fig

    def bar(self, x: list[float], y: list[float],
               title: str = "", label: str = "",
               color: str = "blue") -> Figure:
        """柱状图。"""
        fig = Figure(title=title, chart_type=ChartType.BAR)
        fig.data.append(PlotData(x=x, y=y, label=label, color=color))
        self._figures.append(fig)
        return fig

    def scatter(self, x: list[float], y: list[float],
                   title: str = "", label: str = "",
                   color: str = "blue") -> Figure:
        """散点图。"""
        fig = Figure(title=title, chart_type=ChartType.SCATTER)
        fig.data.append(PlotData(x=x, y=y, label=label, color=color))
        self._figures.append(fig)
        return fig

    def histogram(self, data: list[float],
                     title: str = "", bins: int = 10,
                     color: str = "blue") -> Figure:
        """直方图。"""
        fig = Figure(title=title, chart_type=ChartType.HISTOGRAM)
        fig.data.append(PlotData(x=data, y=[], label=color))
        self._figures.append(fig)
        return fig

    def pie(self, data: list[float], labels: list[str],
               title: str = "") -> Figure:
        """饼图。"""
        fig = Figure(title=title, chart_type=ChartType.PIE)
        for i, val in enumerate(data):
            fig.data.append(PlotData(x=[i], y=[val], label=labels[i] if i < len(labels) else ""))
        self._figures.append(fig)
        return fig

    def heatmap(self, data: list[list[float]],
                   title: str = "") -> Figure:
        """热图。"""
        fig = Figure(title=title, chart_type=ChartType.HEATMAP)
        self._figures.append(fig)
        return fig

    def plot(self, data: PlotData) -> Figure:
        """绘制数据。"""
        fig = Figure(chart_type=ChartType.LINE)
        fig.data.append(data)
        self._figures.append(fig)
        return fig

    def save_all(self, prefix: str = "plot") -> int:
        """保存所有图表。"""
        count = 0
        for i, fig in enumerate(self._figures):
            path = f"{prefix}_{i}.json"
            if fig.save(path):
                count += 1
        return count

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "figures": len(self._figures),
        }


# ============================================================
# 内置注册
# ============================================================

def create_figure(title: str = "", chart_type: str = "line") -> Figure:
    """创建图表。"""
    return Figure(title=title, chart_type=ChartType(chart_type))


def plot_line(x: list[float], y: list[float],
                 title: str = "") -> Figure:
    """绘制折线图。"""
    plotter = MathaPlotter()
    return plotter.line(x, y, title)


def plot_bar(x: list[float], y: list[float],
                title: str = "") -> Figure:
    """绘制柱状图。"""
    plotter = MathaPlotter()
    return plotter.bar(x, y, title)


def plot_scatter(x: list[float], y: list[float],
                    title: str = "") -> Figure:
    """绘制散点图。"""
    plotter = MathaPlotter()
    return plotter.scatter(x, y, title)


def plot_histogram(data: list[float],
                      title: str = "") -> Figure:
    """绘制直方图。"""
    plotter = MathaPlotter()
    return plotter.histogram(data, title)


def _register_visualization(builtins: dict) -> None:
    """注册可视化内置函数。"""
    builtins["创建图表"] = create_figure
    builtins["折线图"] = plot_line
    builtins["柱状图"] = plot_bar
    builtins["散点图"] = plot_scatter
    builtins["直方图"] = plot_histogram


def _viz_symtab_names() -> list[str]:
    return [
        "创建图表", "折线图", "柱状图", "散点图", "直方图",
    ]


__all__ = [
    "ChartType", "PlotData", "Figure", "MathaPlotter",
    "create_figure", "plot_line", "plot_bar", "plot_scatter",
    "plot_histogram",
    "_register_visualization", "_viz_symtab_names",
]
