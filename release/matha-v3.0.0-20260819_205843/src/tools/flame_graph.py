# -*- coding: utf-8 -*-
"""性能分析器火焰图可视化组件

提供交互式火焰图（Flame Graph）渲染，
支持展开/收起调用栈、悬停查看详情、时间缩放。

依赖：
  pip install matplotlib seaborn

使用：
  from src.tools.flame_graph import FlameGraphRenderer
  renderer = FlameGraphRenderer()
  renderer.render(profiler_data, output_path="docs/flame_graph.html")
"""
from __future__ import annotations
import json
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# ============================================================
# 数据结构
# ============================================================

@dataclass
class CallFrame:
    """调用栈帧。"""
    name: str
    duration_ms: float
    depth: int
    children: List["CallFrame"] = field(default_factory=list)
    color: str = ""
    start_x: float = 0.0
    width_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 3),
            "depth": self.depth,
            "color": self.color,
            "start_x": round(self.start_x, 4),
            "width_pct": round(self.width_pct, 4),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class FlameGraphData:
    """火焰图数据。"""
    title: str = "性能火焰图"
    total_duration_ms: float = 0.0
    root_frame: Optional[CallFrame] = None
    frames: List[CallFrame] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


# ============================================================
# 颜色方案
#parameterized
_COLOR_PALETTES = {
    "fire": [
        "#1a9850", "#91cf60", "#d9ef8b", "#fee08b",
        "#fdae61", "#f46d43", "#d73027", "#a50026",
    ],
    "ocean": [
        "#0570b0", "#4292c6", "#7fbfde", "#c7e9f5",
        "#fee0d2", "#fdae9c", "#f46d5e", "#d73026",
    ],
    "purple": [
        "#7b3294", "#a661ff", "#dac0ff", "#f2f0ff",
        "#fff7bc", "#fec44f", "#fe9929", "#d95f0e",
    ],
    "mono": [
        "#2c7bb6", "#41b6c4", "#7fcdbb", "#c7e9b0",
        "#ffffd9", "#fed97e", "#feb24c", "#fd8d3c",
    ],
}


def _get_color(depth: int, palette: str = "fire") -> str:
    """根据深度获取颜色。"""
    colors = _COLOR_PALETTES.get(palette, _COLOR_PALETTES["fire"])
    return colors[depth % len(colors)]


# ============================================================
# 火焰图构建器
# ============================================================

class FlameGraphBuilder:
    """从调用栈数据构建火焰图。"""

    def __init__(self, palette: str = "fire", max_depth: int = 20):
        self.palette = palette
        self.max_depth = max_depth

    def build(self, call_stack: List[Tuple[str, float]], total_duration: float) -> FlameGraphData:
        """
        从线性调用栈构建火焰图树。

        Args:
            call_stack: [(函数名, 持续时间ms), ...] 深度优先遍历序列
            total_duration: 总执行时间（ms）

        Returns:
            FlameGraphData
        """
        root = CallFrame(name="__main__", duration_ms=total_duration, depth=0)
        stack: List[CallFrame] = [root]

        for name, duration in call_stack:
            frame = CallFrame(name=name, duration_ms=duration, depth=len(stack) - 1)
            frame.color = _get_color(frame.depth, self.palette)
            stack[-1].children.append(frame)
            stack.append(frame)

        # 计算布局
        self._layout(root, 0.0, 100.0)
        root.color = _get_color(0, self.palette)

        return FlameGraphData(
            title="Matha 性能火焰图",
            total_duration_ms=total_duration,
            root_frame=root,
            frames=self._flatten(root),
        )

    def _layout(self, frame: CallFrame, start: float, end: float):
        """递归设置火焰图布局（x 坐标和宽度百分比）。"""
        total_child = sum(c.duration_ms for c in frame.children)
        if total_child == 0:
            frame.start_x = start
            frame.width_pct = max((end - start) * frame.duration_ms / max(frame.duration_ms, 0.001), 0.5)
            return

        current = start
        for child in frame.children:
            child_start = current
            child_width = (child.duration_ms / frame.duration_ms) * (end - start)
            self._layout(child, current, current + child_width)
            current += child_width

        frame.start_x = start
        frame.width_pct = end - start

    def _flatten(self, frame: CallFrame) -> List[CallFrame]:
        """将树展平为列表（用于渲染）。"""
        result = [frame]
        for child in frame.children:
            result.extend(self._flatten(child))
        return result


# ============================================================
# HTML 渲染器
# ============================================================

class FlameGraphRenderer:
    """将火焰图数据渲染为交互式 HTML。"""

    # SVG/Canvas 渲染模板
    HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      overflow: hidden;
    }}
    #header {{
      position: fixed; top: 0; left: 0; right: 0;
      background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
      padding: 12px 24px;
      display: flex; justify-content: space-between; align-items: center;
      z-index: 100;
      border-bottom: 1px solid #2a2a4a;
    }}
    #header h1 {{ font-size: 18px; font-weight: 600; color: #e94560; }}
    #header .stats {{ font-size: 13px; color: #aaa; }}
    #header .stats span {{ color: #4fbdba; margin-left: 16px; }}
    #controls {{
      position: fixed; top: 56px; left: 0; right: 0;
      background: #16213e;
      padding: 8px 24px;
      display: flex; gap: 12px; align-items: center;
      z-index: 99;
      border-bottom: 1px solid #2a2a4a;
    }}
    #controls button {{
      background: #0f3460; color: #e0e0e0;
      border: 1px solid #2a2a4a; border-radius: 4px;
      padding: 4px 12px; font-size: 12px; cursor: pointer;
      transition: background 0.2s;
    }}
    #controls button:hover {{ background: #e94560; }}
    #controls label {{ font-size: 12px; color: #aaa; }}
    #controls input[type=range] {{ width: 120px; }}
    #canvas-container {{
      position: fixed; top: 96px; left: 0; right: 0; bottom: 0;
      overflow: auto;
    }}
    #flamegraph {{ display: block; }}
    #tooltip {{
      position: fixed; display: none;
      background: #16213e; border: 1px solid #e94560;
      border-radius: 6px; padding: 10px 14px;
      font-size: 12px; pointer-events: none;
      z-index: 200; max-width: 300px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}
    #tooltip .tt-name {{ color: #4fbdba; font-weight: 600; font-size: 14px; }}
    #tooltip .tt-meta {{ color: #aaa; margin-top: 4px; }}
    #tooltip .tt-bar {{
      height: 4px; border-radius: 2px; margin-top: 6px;
      background: linear-gradient(90deg, #e94560, #4fbdba);
    }}
    #legend {{
      position: fixed; bottom: 16px; right: 16px;
      background: #16213e; border: 1px solid #2a2a4a;
      border-radius: 8px; padding: 12px;
      font-size: 11px; z-index: 100;
    }}
    #legend h3 {{ color: #e94560; margin-bottom: 8px; font-size: 12px; }}
    #legend .item {{ display: flex; align-items: center; gap: 8px; margin: 3px 0; }}
    #legend .swatch {{ width: 14px; height: 14px; border-radius: 2px; }}
    #search-box {{
      background: #0f3460; border: 1px solid #2a2a4a;
      border-radius: 4px; color: #e0e0e0;
      padding: 4px 8px; font-size: 12px; width: 160px;
    }}
    .highlight {{ fill: #e94560 !important; }}
    .dimmed {{ opacity: 0.3; }}
  </style>
</head>
<body>
  <div id="header">
    <h1>🔥 {title}</h1>
    <div class="stats">
      <span>⏱ 总时长: {total_ms:.1f} ms</span>
      <span>📊 帧数: {frame_count}</span>
      <span>🕐 {gen_time}</span>
    </div>
  </div>
  <div id="controls">
    <button onclick="zoomIn()">🔍+ 放大</button>
    <button onclick="zoomOut()">🔍- 缩小</button>
    <button onclick="resetZoom()">↺ 重置</button>
    <label>缩放: <input type="range" id="zoom-slider" min="1" max="10" value="1" oninput="setZoom(this.value)"></label>
    <label>深度: <input type="range" id="depth-slider" min="1" max="15" value="10" oninput="setDepth(this.value)"></label>
    <input type="text" id="search-box" placeholder="搜索函数..." oninput="searchFunction(this.value)">
    <button onclick="togglePalette()">🎨 换色</button>
  </div>
  <div id="canvas-container">
    <canvas id="flamegraph"></canvas>
  </div>
  <div id="tooltip">
    <div class="tt-name"></div>
    <div class="tt-meta"></div>
    <div class="tt-bar"></div>
  </div>
  <div id="legend">
    <h3>图例</h3>
    <div id="legend-items"></div>
  </div>

<script>
// ===== 数据 =====
const DATA = {data_json};
const FRAME_H = 18;
const MIN_W = 2;
let zoom = 1;
let maxDepth = 10;
let paletteIdx = 0;
const PALETTES = ["fire", "ocean", "purple", "mono"];

// ===== Canvas 初始化 =====
const canvas = document.getElementById("flamegraph");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
let allRects = [];

function init() {
  const root = DATA.root_frame;
  const w = Math.max(1400, root.width_pct * 20);
  const h = calcHeight(root) + 40;
  canvas.width = w * 2;  // Retina
  canvas.height = h * 2;
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
  ctx.scale(2, 2);
  allRects = [];
  drawFrame(root, 0, 0, w, h - 40, 0);
  buildLegend();
}

function calcHeight(frame) {
  if (frame.depth >= maxDepth || frame.children.length === 0) return FRAME_H;
  return FRAME_H + Math.max(...frame.children.map(calcHeight));
}

function drawFrame(frame, x, y, totalW, totalH, depth) {
  if (frame.depth >= maxDepth) return;
  const w = Math.max(MIN_W, (frame.width_pct / 100) * totalW);
  const h = FRAME_H;
  const colors = _COLOR_PALETTES[PALETTES[paletteIdx]];
  const color = colors[frame.depth % colors.length];

  ctx.fillStyle = color;
  ctx.fillRect(x, y, w - 1, h - 2);

  // 文字
  if (w > 40) {
    ctx.fillStyle = "#fff";
    ctx.font = "10px sans-serif";
    ctx.fillText(truncate(frame.name, Math.floor(w / 6)), x + 4, y + 12);
  }

  allRects.push({ x, y, w, h, frame, color });
  frame._x = x; frame._y = y; frame._w = w;

  let cx = x;
  for (const child of frame.children) {
    const cw = Math.max(MIN_W, (child.width_pct / 100) * totalW);
    drawFrame(child, cx, y + h, totalW, totalH, depth + 1);
    cx += cw;
  }
}

function truncate(s, max) {
  return s.length <= max ? s : s.slice(0, max - 1) + "…";
}

function _COLOR_PALETTES = {palette_json};

// ===== 交互 =====
canvas.addEventListener("mousemove", (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  let hit = null;
  for (const r of allRects) {
    if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
      hit = r;
    }
  }
  if (hit) {
    tooltip.style.display = "block";
    tooltip.style.left = (e.clientX + 12) + "px";
    tooltip.style.top = (e.clientY - 10) + "px";
    tooltip.querySelector(".tt-name").textContent = hit.frame.name;
    tooltip.querySelector(".tt-meta").textContent =
      `耗时: ${hit.frame.duration_ms.toFixed(2)} ms | 占比: ${hit.frame.width_pct.toFixed(1)}% | 深度: ${hit.frame.depth}`;
    tooltip.querySelector(".tt-bar").style.width = hit.frame.width_pct + "%";
    tooltip.querySelector(".tt-bar").style.background = hit.color;
    canvas.style.cursor = "pointer";
  } else {
    tooltip.style.display = "none";
    canvas.style.cursor = "default";
  }
});

canvas.addEventListener("click", (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  for (const r of allRects) {
    if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
      if (r.frame.children.length > 0) {
        // 聚焦：重新绘制该子树
        focusOn(r.frame, r.x, r.y, r.w, r.h);
      }
      return;
    }
  }
});

function focusOn(frame, x, y, w, h) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  allRects = [];
  const rootCopy = { ...frame, children: frame.children };
  drawFrame(rootCopy, x, y, w, h, 0);
}

function zoomIn() { zoom = Math.min(5, zoom * 1.5); applyZoom(); }
function zoomOut() { zoom = Math.max(0.2, zoom / 1.5); applyZoom(); }
function resetZoom() { zoom = 1; document.getElementById("zoom-slider").value = 1; applyZoom(); }
function setZoom(v) { zoom = parseFloat(v); applyZoom(); }
function setDepth(v) { maxDepth = parseInt(v); init(); }
function togglePalette() { paletteIdx = (paletteIdx + 1) % PALETTES.length; init(); }
function searchFunction(query) {
  const q = query.toLowerCase();
  allRects.forEach(r => {
    const match = !q || r.frame.name.toLowerCase().includes(q);
    r.frame._hidden = !match;
  });
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  allRects = [];
  drawFrame(DATA.root_frame, 0, 0, canvas.width / 2, canvas.height / 2, 0);
}

function applyZoom() {
  const container = document.getElementById("canvas-container");
  container.style.transform = `scale(${zoom})`;
  container.style.transformOrigin = "top left";
}

function buildLegend() {
  const colors = _COLOR_PALETTES[PALETTES[paletteIdx]];
  const container = document.getElementById("legend-items");
  container.innerHTML = "";
  colors.forEach((c, i) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `<div class="swatch" style="background:${c}"></div><span>深度 ${i}</span>`;
    container.appendChild(item);
  });
}

// ===== 启动 =====
init();
</script>
</body>
</html>'''

    def render(self, data: FlameGraphData, output_path: str = "flame_graph.html") -> str:
        """渲染火焰图为 HTML 文件。"""
        palette_keys = list(_COLOR_PALETTES.keys())
        data_json = json.dumps(data.root_frame.to_dict(), ensure_ascii=False, indent=2)
        palette_json = json.dumps(
            {k: _COLOR_PALETTES[k] for k in palette_keys},
            ensure_ascii=False, indent=2,
        )
        gen_time = time.strftime("%Y-%m-%d %H:%M:%S")
        html = self._build_html(data.title, data.total_duration_ms, len(data.frames),
                                gen_time, data_json, palette_json)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        return str(out)

    def render_to_string(self, data: FlameGraphData) -> str:
        """渲染为 HTML 字符串。"""
        palette_keys = list(_COLOR_PALETTES.keys())
        data_json = json.dumps(data.root_frame.to_dict(), ensure_ascii=False, indent=2)
        palette_json = json.dumps(
            {k: _COLOR_PALETTES[k] for k in palette_keys},
            ensure_ascii=False, indent=2,
        )
        gen_time = time.strftime("%Y-%m-%d %H:%M:%S")
        return self._build_html(data.title, data.total_duration_ms, len(data.frames),
                                gen_time, data_json, palette_json)

    @staticmethod
    def _build_html(title: str, total_ms: float, frame_count: int,
                    gen_time: str, data_json: str, palette_json: str) -> str:
        """构建 HTML 内容（避免 .format() 与 JS 花括号冲突）。"""
        t = FlameGraphRenderer.HTML_TEMPLATE
        t = t.replace("{title}", title)
        t = t.replace("{total_ms}", f"{total_ms:.1f}")
        t = t.replace("{frame_count}", str(frame_count))
        t = t.replace("{gen_time}", gen_time)
        t = t.replace("{data_json}", data_json)
        t = t.replace("{palette_json}", palette_json)
        return t


# ============================================================
# 从 MathaProfiler 数据转换
# ============================================================

def build_flame_data_from_profiler(profiler_data: dict) -> FlameGraphData:
    """从 MathaProfiler 的统计数据结构构建火焰图数据。"""
    total_ms = profiler_data.get("total_duration_ms", 1.0)
    builder = FlameGraphBuilder()

    # 从函数调用统计重建调用栈（简化：按调用次数排序）
    call_stack = []
    for func_name, stats in profiler_data.get("functions", {}).items():
        dur = stats.get("total_ms", 0)
        call_stack.append((func_name, dur))

    return builder.build(call_stack, total_ms)


def build_flame_data_from_trace(trace: List[dict]) -> FlameGraphData:
    """从原始调用跟踪列表构建火焰图数据。

    trace 格式：
      [{"name": "func_a", "start": 0.0, "duration": 0.05},
       {"name": "func_b", "start": 0.01, "duration": 0.02},
       ...]
    """
    if not trace:
        return FlameGraphData(total_duration_ms=0.0)

    total_ms = max(t.get("start", 0) + t.get("duration", 0) for t in trace)
    # 按时间排序
    sorted_trace = sorted(trace, key=lambda t: (t.get("start", 0), -t.get("duration", 0)))
    builder = FlameGraphBuilder()
    call_stack = [(t["name"], t.get("duration", 0) * 1000) for t in sorted_trace]
    return builder.build(call_stack, total_ms)


# ============================================================
# 示例 / 测试
# ============================================================

if __name__ == "__main__":
    # 模拟 Profiler 数据
    import random
    random.seed(42)

    # 生成模拟调用栈
    def gen_call_stack(depth=0, remaining=100.0):
        if depth >= 8 or remaining < 2:
            return []
        name = f"func_{'_' .join([chr(97+i) for i in range(depth)])}"
        dur = remaining * random.uniform(0.3, 0.8)
        stack = [(name, dur)]
        children_count = random.randint(1, 3)
        for _ in range(children_count):
            stack.extend(gen_call_stack(depth + 1, remaining - dur))
        return stack

    mock_trace = gen_call_stack()
    total = sum(d for _, d in mock_trace)

    builder = FlameGraphBuilder()
    data = builder.build(mock_trace, total)

    renderer = FlameGraphRenderer()
    out = renderer.render(data, "matha_flame_graph.html")
    print(f"火焰图已生成: {out}")
    print(f"总帧数: {len(data.frames)}, 总时长: {data.total_duration_ms:.1f} ms")
