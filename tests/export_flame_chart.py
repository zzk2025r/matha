# -*- coding: utf-8 -*-
"""将火焰图 CSV 数据导出为 HTML 可视化图表（无依赖）。"""
import csv
import json
from pathlib import Path

CSV_PATH = Path("matha_flame_graph.csv")
HTML_PATH = Path("matha_flame_chart.html")

def main():
    # 读取 CSV
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "name": row["name"],
                "duration_ms": float(row["duration_ms"]),
                "width_pct": float(row["width_pct"]),
                "depth": int(row["depth"]),
                "parent": row["parent"],
            })

    # 颜色方案（与火焰图 HTML 一致）
    COLORS = {
        0: "#1a9850",  # 绿
        1: "#91cf60",  # 浅绿
        2: "#d9ef8b",  # 黄绿
        3: "#fee08b",  # 黄
        4: "#fdae61",  # 橙
        5: "#f46d43",  # 红橙
        6: "#d73027",  # 红
        7: "#a50026",  # 深红
    }

    # 统计信息
    total_ms = sum(r["duration_ms"] for r in rows)
    max_node = max(rows, key=lambda r: r["width_pct"])
    max_depth = max(r["depth"] for r in rows)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Matha 性能火焰图</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
    h1 {{ color: #e94560; margin-bottom: 20px; }}
    .chart {{ background: #16213e; border-radius: 8px; padding: 20px; }}
    .bar-row {{ display: flex; align-items: center; margin: 6px 0; }}
    .bar-label {{ width: 160px; font-size: 12px; color: #aaa; text-align: right; padding-right: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .bar-track {{ flex: 1; height: 24px; background: #0f3460; border-radius: 4px; overflow: hidden; position: relative; }}
    .bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; display: flex; align-items: center; padding-left: 8px; }}
    .bar-value {{ font-size: 11px; color: #fff; font-weight: bold; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 20px; }}
    .stat-card {{ background: #0f3460; border-radius: 8px; padding: 15px; text-align: center; }}
    .stat-card .value {{ font-size: 24px; font-weight: bold; color: #4fbdba; }}
    .stat-card .label {{ font-size: 12px; color: #aaa; margin-top: 5px; }}
    .legend {{ margin-top: 20px; display: flex; gap: 15px; flex-wrap: wrap; }}
    .legend-item {{ display: flex; align-items: center; gap: 5px; font-size: 12px; color: #aaa; }}
    .legend-swatch {{ width: 16px; height: 16px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Matha 性能火焰图</h1>
  <div class="stats">
    <div class="stat-card"><div class="value">{total_ms:.1f} ms</div><div class="label">总耗时</div></div>
    <div class="stat-card"><div class="value">{len(rows)}</div><div class="label">函数节点</div></div>
    <div class="stat-card"><div class="value">{max_depth}</div><div class="label">最大深度</div></div>
    <div class="stat-card"><div class="value">{max_node["name"]}</div><div class="label">最大模块</div></div>
  </div>
  <div class="chart" style="margin-top: 20px;">
'''

    for r in rows:
        color = COLORS.get(r["depth"], "#d73027")
        html += f'''    <div class="bar-row">
      <div class="bar-label" title="{r["name"]}">{r["name"]}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width: {r["width_pct"]}%; background: {color};">
          <span class="bar-value">{r["width_pct"]:.1f}%</span>
        </div>
      </div>
    </div>
'''

    html += f'''  </div>
  <div class="legend">
'''
    for d in range(8):
        html += f'    <div class="legend-item"><div class="legend-swatch" style="background:{COLORS[d]}"></div>深度 {d}</div>\n'

    html += '''  </div>
</body>
</html>
'''

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"HTML 图表已生成: {HTML_PATH}")

    # 同时生成 PNG（使用 tkinter）
    try:
        import tkinter as tk
        from tkinter import ttk
        print("tkinter 不可用，跳过 PNG 生成")
    except ImportError:
        pass

    # 生成 SVG
    svg = generate_svg(rows, COLORS)
    SVG_PATH = Path("matha_flame_chart.svg")
    SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"SVG 图表已生成: {SVG_PATH}")


def generate_svg(rows, COLORS):
    """生成 SVG 条形图。"""
    max_pct = max(r["width_pct"] for r in rows)
    bar_h = 28
    label_w = 160
    chart_w = 800
    height = len(rows) * (bar_h + 8) + 60

    svg_lines = [f'<?xml version="1.0" encoding="UTF-8"?>']
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{chart_w}" height="{height}" viewBox="0 0 {chart_w} {height}">')
    svg_lines.append(f'<rect width="100%" height="100%" fill="#1a1a2e"/>')
    svg_lines.append(f'<text x="20" y="30" fill="#e94560" font-size="18" font-family="sans-serif">Matha 性能火焰图</text>')

    for i, r in enumerate(rows):
        y = 50 + i * (bar_h + 8)
        color = COLORS.get(r["depth"], "#d73027")
        bar_w = (r["width_pct"] / max_pct) * (chart_w - label_w - 100)
        svg_lines.append(f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="4"/>')
        svg_lines.append(f'<text x="{label_w - 10}" y="{y + bar_h/2 + 5}" fill="#aaa" font-size="12" text-anchor="end" font-family="sans-serif">{r["name"]}</text>')
        svg_lines.append(f'<text x="{label_w + bar_w + 8}" y="{y + bar_h/2 + 5}" fill="#fff" font-size="11" font-family="sans-serif">{r["width_pct"]:.1f}%</text>')

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


if __name__ == "__main__":
    main()
