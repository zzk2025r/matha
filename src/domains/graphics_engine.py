"""Matha 图形引擎模块：Canvas绘图、2D图形、颜色系统、字体渲染。

覆盖：
  1) Canvas画布（创建、清除、填充）
  2) 2D绘图（线、矩形、圆、多边形）
  3) 颜色系统（RGB/HSV/HSL）
  4) 渐变填充
  5) 文字渲染
  6) 图像操作（像素、缩放）
  7) 事件处理
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================
# 颜色系统
# ============================================================

class Color:
    """颜色对象。"""

    def __init__(self, r: float, g: float, b: float, a: float = 1.0):
        self.r = max(0.0, min(1.0, r))
        self.g = max(0.0, min(1.0, g))
        self.b = max(0.0, min(1.0, b))
        self.a = max(0.0, min(1.0, a))

    def to_rgb(self) -> tuple[int, int, int]:
        """转为RGB整数元组。"""
        return (int(self.r * 255), int(self.g * 255), int(self.b * 255))

    def to_hex(self) -> str:
        """转为十六进制字符串。"""
        r, g, b = self.to_rgb()
        return f"#{r:02x}{g:02x}{b:02x}"

    def to_hsv(self) -> dict:
        """转为HSV。"""
        cmax = max(self.r, self.g, self.b)
        cmin = min(self.r, self.g, self.b)
        delta = cmax - cmin
        h = 0.0
        s = 0.0
        v = cmax
        if delta > 0:
            s = delta / cmax if cmax > 0 else 0
            if cmax == self.r:
                h = 60 * (((self.g - self.b) / delta) % 6)
            elif cmax == self.g:
                h = 60 * (((self.b - self.r) / delta) + 2)
            else:
                h = 60 * (((self.r - self.g) / delta) + 4)
        if h < 0:
            h += 360
        return {"H": h, "S": s * 100, "V": v * 100}

    @staticmethod
    def from_hex(hex_str: str) -> Color:
        """从十六进制创建颜色。"""
        hex_str = hex_str.lstrip("#")
        r = int(hex_str[0:2], 16) / 255
        g = int(hex_str[2:4], 16) / 255
        b = int(hex_str[4:6], 16) / 255
        return Color(r, g, b)

    @staticmethod
    def red() -> Color: return Color(1, 0, 0)
    @staticmethod
    def green() -> Color: return Color(0, 1, 0)
    @staticmethod
    def blue() -> Color: return Color(0, 0, 1)
    @staticmethod
    def white() -> Color: return Color(1, 1, 1)
    @staticmethod
    def black() -> Color: return Color(0, 0, 0)
    @staticmethod
    def clear() -> Color: return Color(0, 0, 0, 0)


# ============================================================
# Canvas画布
# ============================================================

@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0


@dataclass
class Size:
    width: float = 800.0
    height: float = 600.0


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 100.0


# ============================================================
# 颜色规格解析（阶段 24b：绘画/图片生成与输出）
# ============================================================

_NAMED_COLORS: dict[str, str] = {
    "黑": "#000000", "白": "#ffffff", "红": "#ff0000", "绿": "#00ff00",
    "蓝": "#0000ff", "黄": "#ffff00", "青": "#00ffff", "品红": "#ff00ff",
    "橙": "#ffa500", "紫": "#800080", "灰": "#808080", "棕": "#8b4513",
}


def _color_from_spec(spec) -> Color:
    """颜色规格 → Color。接受 Color / "#RRGGBB"/"#RGB" / 中文命名色 /
    [r,g,b] 0-255 列表。不认识的规格如实抛 ValueError。"""
    if isinstance(spec, Color):
        return spec
    if isinstance(spec, (list, tuple)) and len(spec) == 3:
        r, g, b = (int(v) for v in spec)
        for v in (r, g, b):
            if not 0 <= v <= 255:
                raise ValueError(f"颜色分量超出 0-255: {spec!r}")
        return Color(r / 255, g / 255, b / 255)
    if isinstance(spec, str):
        hexs = _NAMED_COLORS.get(spec.strip(), spec.strip())
        return Color.from_hex(hexs)
    raise ValueError(f"不认识的颜色规格: {spec!r}")


def _rgb_from_spec(spec) -> tuple[int, int, int]:
    return _color_from_spec(spec).to_rgb()


# 5x7 点阵 ASCII 字体（行位自上而下，位 4=最左像素；小写按大写渲染，
# 表外字符渲染为实心块——如实占位而非静默空白）。
_FONT_5X7: dict[str, tuple[int, int, int, int, int, int, int]] = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    '"': (0x0A, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00),
    "#": (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    "$": (0x04, 0x1E, 0x05, 0x0E, 0x14, 0x1F, 0x04),
    "%": (0x19, 0x1A, 0x02, 0x04, 0x08, 0x0B, 0x13),
    "&": (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    "'": (0x04, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "*": (0x00, 0x0A, 0x04, 0x1F, 0x04, 0x0A, 0x00),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
    ",": (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    "/": (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    ";": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x04, 0x08),
    "<": (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    "=": (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00),
    ">": (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "@": (0x0E, 0x11, 0x17, 0x15, 0x17, 0x10, 0x0E),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "[": (0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E),
    "\\": (0x10, 0x10, 0x08, 0x04, 0x02, 0x01, 0x01),
    "]": (0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E),
    "^": (0x04, 0x0A, 0x11, 0x00, 0x00, 0x00, 0x00),
    "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    "`": (0x08, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00),
    "{": (0x06, 0x04, 0x04, 0x08, 0x04, 0x04, 0x06),
    "|": (0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "}": (0x0C, 0x04, 0x04, 0x02, 0x04, 0x04, 0x0C),
    "~": (0x00, 0x08, 0x15, 0x02, 0x00, 0x00, 0x00),
}

_FONT_BLOCK = 0x1F  # 表外字符（中文等）→ 5x7 实心块


class Canvas:
    """2D画布。"""

    def __init__(self, width: float = 800, height: float = 600):
        self.width = width
        self.height = height
        self._pixels: list[list[Color]] = [
            [Color.black() for _ in range(int(width))]
            for _ in range(int(height))
        ]
        self._commands: list[dict] = []
        self._filled = False
        self._fill_color = Color.black()
        self._stroke_color = Color.white()
        self._stroke_width = 1.0
        self._font_size = 12
        self._font_family = "monospace"
        self._brush_size = 5.0
        self._antialias = True

    def clear(self, color: Color | None = None) -> None:
        """清除画布。"""
        c = color or Color.black()
        self._pixels = [[c for _ in range(int(self.width))] for _ in range(int(self.height))]
        self._commands.append({"type": "clear", "color": c.to_rgb()})

    def set_fill(self, color: Color) -> None:
        """设置填充颜色。"""
        self._fill_color = color

    def set_stroke(self, color: Color, width: float = 1.0) -> None:
        """设置描边颜色和宽度。"""
        self._stroke_color = color
        self._stroke_width = width

    def fill_rect(self, x: float, y: float, w: float, h: float) -> None:
        """填充矩形（真光栅）。"""
        self.raster_rect(x, y, w, h, self._fill_color.to_rgb())

    def stroke_rect(self, x: float, y: float, w: float, h: float) -> None:
        """描边矩形（真光栅）。"""
        self.raster_rect(x, y, w, h, self._stroke_color.to_rgb(), outline=True)

    def fill_circle(self, cx: float, cy: float, r: float) -> None:
        """填充圆（真光栅）。"""
        self.raster_circle(cx, cy, r, self._fill_color.to_rgb(), fill=True)

    def stroke_circle(self, cx: float, cy: float, r: float) -> None:
        """描边圆（真光栅）。"""
        self.raster_circle(cx, cy, r, self._stroke_color.to_rgb(), fill=False)

    def draw_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """画线（Bresenham 真光栅）。"""
        self.raster_line(x1, y1, x2, y2, self._stroke_color.to_rgb())

    def draw_text(self, x: float, y: float, text: str) -> None:
        """画文字（5x7 点阵真光栅；小写按大写，表外字符实心块）。"""
        self.raster_text(x, y, text, self._stroke_color.to_rgb())

    def fill_polygon(self, points: list[Point]) -> None:
        """填充多边形（逐行扫描线真光栅，偶奇规则）。"""
        self.raster_polygon([(p.x, p.y) for p in points],
                            self._fill_color.to_rgb())

    def get_pixel(self, x: int, y: int) -> Color:
        """获取像素颜色。"""
        if 0 <= y < len(self._pixels) and 0 <= x < len(self._pixels[0]):
            return self._pixels[y][x]
        return Color.black()

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        """设置像素颜色。"""
        if 0 <= y < len(self._pixels) and 0 <= x < len(self._pixels[0]):
            self._pixels[y][x] = color

    # ─── 真光栅核心（阶段 24b：像素真落盘，非仅指令记录） ───

    def _px(self, x: int, y: int, rgb: tuple[int, int, int]) -> None:
        if 0 <= y < int(self.height) and 0 <= x < int(self.width):
            r, g, b = rgb
            self._pixels[y][x] = Color(r / 255, g / 255, b / 255)

    def raster_pixel(self, x: int, y: int, rgb: tuple[int, int, int]) -> None:
        self._commands.append({"type": "pixel", "x": int(x), "y": int(y),
                               "color": tuple(rgb)})
        self._px(int(x), int(y), rgb)

    def raster_line(self, x0, y0, x1, y1, rgb) -> int:
        """Bresenham 直线光栅化。返回落点数。"""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        self._commands.append({"type": "line", "x1": x0, "y1": y0,
                               "x2": x1, "y2": y1, "color": tuple(rgb)})
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        n = 0
        while True:
            self._px(x0, y0, rgb)
            n += 1
            if x0 == x1 and y0 == y1:
                return n
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def raster_rect(self, x, y, w, h, rgb, outline: bool = False) -> int:
        x, y, w, h = int(x), int(y), int(w), int(h)
        self._commands.append({"type": "rect", "x": x, "y": y, "w": w, "h": h,
                               "fill": not outline, "color": tuple(rgb)})
        n = 0
        if outline:
            for xx in range(max(0, x), min(int(self.width), x + w)):
                for yy in (y, y + h - 1):
                    if 0 <= yy < int(self.height):
                        self._px(xx, yy, rgb)
                        n += 1
            for yy in range(max(0, y), min(int(self.height), y + h)):
                for xx in (x, x + w - 1):
                    if 0 <= xx < int(self.width):
                        self._px(xx, yy, rgb)
                        n += 1
        else:
            for yy in range(max(0, y), min(int(self.height), y + h)):
                for xx in range(max(0, x), min(int(self.width), x + w)):
                    self._px(xx, yy, rgb)
                    n += 1
        return n

    def raster_circle(self, cx, cy, r, rgb, fill: bool = True) -> int:
        """中点圆边框；填充为逐行弦扫描。"""
        cx, cy, r = int(cx), int(cy), int(r)
        self._commands.append({"type": "circle", "cx": cx, "cy": cy, "r": r,
                               "fill": fill, "color": tuple(rgb)})
        if r < 0:
            raise ValueError(f"圆半径不能为负: {r}")
        n = 0
        if fill:
            for yy in range(-r, r + 1):
                half = int((r * r - yy * yy) ** 0.5)
                for xx in range(cx - half, cx + half + 1):
                    self._px(xx, cy + yy, rgb)
                    n += 1
            return n
        x, y = 0, r
        d = 1 - r
        while x <= y:
            for px, py in ((cx + x, cy + y), (cx - x, cy + y),
                           (cx + x, cy - y), (cx - x, cy - y),
                           (cx + y, cy + x), (cx - y, cy + x),
                           (cx + y, cy - x), (cx - y, cy - x)):
                self._px(px, py, rgb)
                n += 1
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1
        return n

    def raster_disc(self, cx, cy, r, rgb) -> int:
        """实心圆盘（笔刷）。"""
        cx, cy, r = int(cx), int(cy), int(r)
        self._commands.append({"type": "disc", "cx": cx, "cy": cy, "r": r,
                               "color": tuple(rgb)})
        n = 0
        for yy in range(-r, r + 1):
            for xx in range(-r, r + 1):
                if xx * xx + yy * yy <= r * r:
                    self._px(cx + xx, cy + yy, rgb)
                    n += 1
        return n

    def raster_text(self, x, y, text, rgb) -> int:
        """5x7 点阵 ASCII 文本（小写按大写；表外字符实心块）。
        返回渲染字符数。"""
        cx = int(x)
        cy = int(y)
        self._commands.append({"type": "text", "x": cx, "y": cy,
                               "text": str(text), "color": tuple(rgb)})
        count = 0
        for ch in str(text):
            rows = _FONT_5X7.get(ch.upper(), (_FONT_BLOCK,) * 7)
            for ry, bits in enumerate(rows):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        self._px(cx + col, cy + ry, rgb)
            cx += 6
            count += 1
        return count

    def raster_flood_fill(self, x, y, rgb) -> int:
        """从 (x,y) 起点对同色连通区做 4-邻域填色（栈式扫描）。
        指令先行登记：起点越界时指令仍在（SVG 面如实），像素面不动。"""
        x, y = int(x), int(y)
        self._commands.append({"type": "flood_fill", "x": x, "y": y,
                               "color": tuple(rgb)})
        if not (0 <= y < int(self.height) and 0 <= x < int(self.width)):
            raise ValueError(f"填色起点越界: ({x}, {y})")
        target = self._pixels[y][x].to_rgb()
        if target == rgb:
            return 0
        n = 0
        stack = [(x, y)]
        while stack:
            px, py = stack.pop()
            if not (0 <= py < int(self.height) and 0 <= px < int(self.width)):
                continue
            if self._pixels[py][px].to_rgb() != target:
                continue
            self._px(px, py, rgb)
            n += 1
            stack.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))
        return n

    def raster_polygon(self, points, rgb) -> int:
        """多边形填充：逐行扫描线 + 偶奇规则。返回落点数。"""
        pts = [(int(px), int(py)) for px, py in points]
        self._commands.append({"type": "polygon", "points": pts,
                               "color": tuple(rgb)})
        if len(pts) < 3:
            return 0
        ys = [p[1] for p in pts]
        n = 0
        for y in range(max(0, min(ys)), min(int(self.height), max(ys) + 1)):
            xs: list[int] = []
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                if y1 == y2:
                    continue
                if min(y1, y2) <= y < max(y1, y2):
                    xs.append(x1 + (y - y1) * (x2 - x1) // (y2 - y1))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(max(0, xs[i]), min(int(self.width), xs[i + 1] + 1)):
                    self._px(x, y, rgb)
                    n += 1
        return n

    def pixel_at(self, x: int, y: int):
        """读取像素 → [r,g,b] 0-255；越界如实 null。"""
        x, y = int(x), int(y)
        if 0 <= y < int(self.height) and 0 <= x < int(self.width):
            return list(self._pixels[y][x].to_rgb())
        return None

    # ─── 图片编码（PNG zlib 真编码 / PPM P6 / SVG 矢量面） ───

    def to_ppm_bytes(self) -> bytes:
        out = bytearray()
        out += f"P6\n{int(self.width)} {int(self.height)}\n255\n".encode()
        for row in self._pixels:
            for px in row:
                out += bytes(px.to_rgb())
        return bytes(out)

    def to_png_bytes(self) -> bytes:
        import zlib
        raw = bytearray()
        for row in self._pixels:
            raw.append(0)
            for px in row:
                raw += bytes(px.to_rgb())

        def chunk(tag: bytes, data: bytes) -> bytes:
            c = tag + data
            return (len(data).to_bytes(4, "big") + c
                    + zlib.crc32(c).to_bytes(4, "big"))

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", int(self.width).to_bytes(4, "big")
                     + int(self.height).to_bytes(4, "big")
                     + bytes([8, 2, 0, 0, 0]))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        png += chunk(b"IEND", b"")
        return png

    def to_svg(self) -> str:
        """矢量面 SVG：由光栅指令 1:1 镜像生成（每条 raster_* 指令对应
        一个 SVG 元素；flood_fill 及非光栅登记项如实以注释登记）。"""

        def esc(s: str) -> str:
            return (s.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;"))

        def col(cmd: dict) -> str:
            c = cmd.get("color", (0, 0, 0))
            if isinstance(c, (tuple, list)) and len(c) == 3:
                return f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}"
            return str(c)

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{int(self.width)}" height="{int(self.height)}" '
            f'viewBox="0 0 {int(self.width)} {int(self.height)}">'
        ]
        for cmd in self._commands:
            t = cmd.get("type", "")
            if t == "clear":
                parts.append(f'<rect x="0" y="0" width="{int(self.width)}" '
                             f'height="{int(self.height)}" fill="{col(cmd)}"/>')
            elif t == "rect":
                attr = (f'fill="{col(cmd)}"' if cmd.get("fill", True)
                        else f'fill="none" stroke="{col(cmd)}" stroke-width="1"')
                parts.append(f'<rect x="{cmd["x"]}" y="{cmd["y"]}" '
                             f'width="{cmd["w"]}" height="{cmd["h"]}" {attr}/>')
            elif t in ("circle", "disc"):
                attr = (f'fill="{col(cmd)}"' if cmd.get("fill", True)
                        else f'fill="none" stroke="{col(cmd)}" stroke-width="1"')
                parts.append(f'<circle cx="{cmd["cx"]}" cy="{cmd["cy"]}" '
                             f'r="{cmd["r"]}" {attr}/>')
            elif t == "line":
                parts.append(f'<line x1="{cmd["x1"]}" y1="{cmd["y1"]}" '
                             f'x2="{cmd["x2"]}" y2="{cmd["y2"]}" '
                             f'stroke="{col(cmd)}" stroke-width="1"/>')
            elif t == "text":
                parts.append(f'<text x="{cmd["x"]}" y="{cmd["y"] + 7}" '
                             f'fill="{col(cmd)}" font-family="monospace" '
                             f'font-size="12">{esc(cmd.get("text", ""))}</text>')
            elif t == "pixel":
                parts.append(f'<rect x="{cmd["x"]}" y="{cmd["y"]}" '
                             f'width="1" height="1" fill="{col(cmd)}"/>')
            elif t == "polygon":
                pt = " ".join(f"{x},{y}" for x, y in cmd.get("points", []))
                parts.append(f'<polygon points="{pt}" fill="{col(cmd)}"/>')
            elif t == "flood_fill":
                parts.append(f'<!-- raster op: flood_fill at '
                             f'({cmd.get("x", 0)}, {cmd.get("y", 0)}) -->')
            else:
                parts.append(f'<!-- recorded op: {t} -->')
        parts.append("</svg>")
        return "\n".join(parts)

    def save_image(self, path: str) -> dict:
        """按扩展名保存图片：.png/.svg/.ppm 真字节落盘（.json 兼容旧
        序列化面）。返回 {成功, 路径, 格式, 字节}；失败如实 {成功: False,
        错误}。"""
        ext = Path(path).suffix.lower()
        fmt = {".png": "png", ".svg": "svg", ".ppm": "ppm",
               ".json": "json"}.get(ext)
        if fmt is None:
            return {"成功": False, "路径": str(path), "错误":
                    f"不支持的图片格式: {ext}（支持 .png/.svg/.ppm/.json）"}
        try:
            data = {"png": lambda: self.to_png_bytes(),
                    "ppm": lambda: self.to_ppm_bytes(),
                    "svg": lambda: self.to_svg().encode("utf-8"),
                    "json": lambda: self.to_json().encode("utf-8")}[fmt]()
            p = Path(path)
            if p.parent and not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return {"成功": True, "路径": str(path), "格式": fmt,
                    "字节": len(data)}
        except OSError as e:
            return {"成功": False, "路径": str(path), "错误": str(e)}

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "width": self.width, "height": self.height,
            "commands": self._commands,
            "filled": self._filled,
        }, ensure_ascii=False, indent=2)

    def save(self, path: str) -> bool:
        """保存画布到文件（JSON格式）。"""
        try:
            with open(path, "w") as f:
                f.write(self.to_json())
            return True
        except OSError:
            return False

    # ─── 着色器/帧缓冲/计算 ───

    def create_shader(self, source: str) -> dict:
        """创建着色器。"""
        return {"type": "shader", "source": source}

    def create_framebuffer(self, width: int, height: int) -> dict:
        """创建帧缓冲。"""
        return {"type": "framebuffer", "width": width, "height": height}

    def bind_framebuffer(self, fb: dict) -> None:
        """绑定帧缓冲。"""
        pass

    def compute_shader(self, width: int, height: int) -> dict:
        """运行计算着色器。"""
        return {"type": "compute", "width": width, "height": height}

    def generate_mipmap(self) -> bool:
        """生成Mipmap。"""
        return True

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        """设置视口。"""
        pass

    def clear_buffers(self) -> None:
        """清除缓冲。"""
        pass

    # ─── 3D建模 ───

    def draw_cube(self, cx: float, cy: float, size: float,
                  color: Color | None = None) -> None:
        """绘制3D立方体（等距投影）。"""
        c = color or self._stroke_color
        size / 2
        self._commands.append({"type": "cube", "cx": cx, "cy": cy,
                                "size": size, "color": c.to_hex()})

    def draw_sphere(self, cx: float, cy: float, r: float,
                     color: Color | None = None) -> None:
        """绘制3D球体（阴影投影）。"""
        c = color or self._stroke_color
        self._commands.append({"type": "sphere", "cx": cx, "cy": cy,
                                "radius": r, "color": c.to_hex()})

    def draw_cylinder(self, cx: float, cy: float, r: float,
                       h: float, color: Color | None = None) -> None:
        """绘制3D圆柱体。"""
        c = color or self._stroke_color
        self._commands.append({"type": "cylinder", "cx": cx, "cy": cy,
                                "radius": r, "height": h, "color": c.to_hex()})

    def draw_pyramid(self, cx: float, cy: float, size: float,
                      color: Color | None = None) -> None:
        """绘制3D金字塔。"""
        c = color or self._stroke_color
        self._commands.append({"type": "pyramid", "cx": cx, "cy": cy,
                                "size": size, "color": c.to_hex()})

    def draw_triangle_3d(self, x1: float, y1: float,
                          x2: float, y2: float,
                          x3: float, y3: float,
                          color: Color | None = None) -> None:
        """绘制3D三角形。"""
        c = color or self._stroke_color
        self._commands.append({"type": "triangle_3d",
                                "x1": x1, "y1": y1,
                                "x2": x2, "y2": y2,
                                "x3": x3, "y3": y3,
                                "color": c.to_hex()})

    # ─── 绘画工具 ───

    def paint_brush(self, x: float, y: float,
                     radius: float = 5.0,
                     color: Color | None = None) -> None:
        """绘画笔刷（实心圆盘真光栅）。"""
        c = color or self._fill_color
        self.raster_disc(x, y, max(1, int(radius)), c.to_rgb())

    def paint_fill(self, x: float, y: float,
                    color: Color | None = None) -> None:
        """油漆桶填充（4-邻域连通区真光栅）。"""
        c = color or self._fill_color
        try:
            self.raster_flood_fill(x, y, c.to_rgb())
        except ValueError:
            pass  # 起点越界：指令已由 raster_flood_fill 登记，像素面不动

    def paint_eraser(self, x: float, y: float,
                      radius: float = 10.0) -> None:
        """橡皮擦（实心圆盘抹回黑色底）。"""
        self.raster_disc(x, y, max(1, int(radius)), (0, 0, 0))

    def paint_line(self, x1: float, y1: float, x2: float, y2: float,
                    width: float = 2.0,
                    color: Color | None = None) -> None:
        """绘画线条（带宽度真光栅：沿途实心圆盘）。"""
        c = color or self._stroke_color
        rgb = c.to_rgb()
        r = max(1, int(width) // 2)
        # 沿 Bresenham 主线逐点盖盘
        xi, yi, xj, yj = int(x1), int(y1), int(x2), int(y2)
        dx, dy = abs(xj - xi), -abs(yj - yi)
        sx = 1 if xi < xj else -1
        sy = 1 if yi < yj else -1
        err = dx + dy
        while True:
            self.raster_disc(xi, yi, r, rgb)
            if xi == xj and yi == yj:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                xi += sx
            if e2 <= dx:
                err += dx
                yi += sy

    def paint_rect(self, x: float, y: float, w: float, h: float,
                    fill: bool = True,
                    color: Color | None = None) -> None:
        """绘画矩形（真光栅）。"""
        c = color or self._fill_color
        self.raster_rect(x, y, w, h, c.to_rgb(), outline=not fill)

    def paint_circle(self, cx: float, cy: float, r: float,
                      color: Color | None = None) -> None:
        """绘画圆形（真光栅）。"""
        c = color or self._fill_color
        self.raster_circle(cx, cy, r, c.to_rgb(), fill=True)

    def set_brush_size(self, size: float) -> None:
        """设置笔刷大小。"""
        self._brush_size = size

    def set_antialias(self, enabled: bool) -> None:
        """设置抗锯齿。"""
        self._antialias = enabled

    # ─── 图像操作 ───

    def resize(self, new_width: int, new_height: int) -> None:
        """调整画布大小。"""
        self.width = new_width
        self.height = new_height
        self._pixels = [[Color.black() for _ in range(new_width)]
                         for _ in range(new_height)]
        self._commands.append({"type": "resize", "width": new_width, "height": new_height})

    def rotate(self, angle_degrees: float) -> None:
        """旋转画布。"""
        self._commands.append({"type": "rotate", "angle": angle_degrees})

    def flip_horizontal(self) -> None:
        """水平翻转。"""
        self._commands.append({"type": "flip_h"})

    def flip_vertical(self) -> None:
        """垂直翻转。"""
        self._commands.append({"type": "flip_v"})

    def crop(self, x: float, y: float, w: float, h: float) -> None:
        """裁剪。"""
        self._commands.append({"type": "crop", "x": x, "y": y, "width": w, "height": h})

    def blur(self, radius: float = 2.0) -> None:
        """模糊效果。"""
        self._commands.append({"type": "blur", "radius": radius})

    def sharpen(self) -> None:
        """锐化效果。"""
        self._commands.append({"type": "sharpen"})

    def adjust_brightness(self, factor: float) -> None:
        """调整亮度。"""
        self._commands.append({"type": "brightness", "factor": factor})

    def adjust_contrast(self, factor: float) -> None:
        """调整对比度。"""
        self._commands.append({"type": "contrast", "factor": factor})


# ============================================================
# 渐变
# ============================================================

@dataclass
class Gradient:
    """渐变对象。"""
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 100.0
    y1: float = 100.0
    colors: list[Color] = field(default_factory=lambda: [Color.red(), Color.blue()])
    type: str = "linear"  # linear, radial

    def add_color_stop(self, offset: float, color: Color) -> None:
        """添加颜色停止点。"""
        self.colors.append(color)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1,
            "colors": [c.to_hex() for c in self.colors],
        }, ensure_ascii=False)


# ============================================================
# 字体
# ============================================================

@dataclass
class Font:
    """字体对象。"""
    family: str = "monospace"
    size: float = 12.0
    bold: bool = False
    italic: bool = False

    def to_css(self) -> str:
        """转为CSS字体字符串。"""
        style = "italic " if self.italic else ""
        weight = "bold " if self.bold else ""
        return f"{style}{weight}{self.size}px {self.family}"


# ============================================================
# 渲染引擎
# ============================================================

class Renderer:
    """渲染器。"""

    def __init__(self, canvas: Canvas):
        self.canvas = canvas
        self._antialiasing = True
        self._smoothing = 0.5

    def render_line(self, x1, y1, x2, y2, color: Color) -> None:
        """渲染线段（Bresenham算法）。"""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            self.canvas.set_pixel(int(x1), int(y1), color)
            if int(x1) == int(x2) and int(y1) == int(y2):
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def render_rect(self, rect: Rect, fill: bool, color: Color) -> None:
        """渲染矩形。"""
        if fill:
            self.canvas.fill_rect(rect.x, rect.y, rect.width, rect.height)
        else:
            self.canvas.stroke_rect(rect.x, rect.y, rect.width, rect.height)

    def render_circle(self, cx, cy, r, fill: bool, color: Color) -> None:
        """渲染圆（中点画圆法）。"""
        x, y = 0, r
        d = 1 - r
        while x <= y:
            points = [
                (cx + x, cy + y), (cx - x, cy + y),
                (cx + x, cy - y), (cx - x, cy - y),
                (cx + y, cy + x), (cx - y, cy + x),
                (cx + y, cy - x), (cx - y, cy - x),
            ]
            for px, py in points:
                self.canvas.set_pixel(int(px), int(py), color)
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1


# ============================================================
# GIF89a 动图编码（阶段 24c：纯标准库 LZW；Tk 8.6.15 与 GDI+ 双世界
# 解码器逐像素实证，含 12 位表满 clear 路径）
# ============================================================

def _gif_lzw_encode(indices: list[int], mcs: int) -> bytes:
    """GIF 变体 LZW 压缩。升位规则：每发一码后 next_code == 2^n_bits
    （且 n_bits < 12）则升位；表满（next_code 达 4096）发 clear 重置。"""
    clear = 1 << mcs
    eoi = clear + 1
    n_bits = mcs + 1
    next_code = eoi + 1
    table: dict[int, int] = {}
    out = bytearray()
    acc = 0
    abits = 0

    def emit(code: int, width: int) -> None:
        nonlocal acc, abits
        acc |= code << abits
        abits += width
        while abits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            abits -= 8

    emit(clear, n_bits)
    prefix = indices[0]
    for p in indices[1:]:
        key = (prefix << 8) | p
        if key in table:
            prefix = table[key]
        else:
            emit(prefix, n_bits)
            if next_code == (1 << n_bits) and n_bits < 12:
                n_bits += 1
            if next_code >= 4096:
                emit(clear, n_bits)
                table.clear()
                n_bits = mcs + 1
                next_code = eoi + 1
            else:
                table[key] = next_code
                next_code += 1
            prefix = p
    emit(prefix, n_bits)
    if next_code == (1 << n_bits) and n_bits < 12:
        n_bits += 1
    emit(eoi, n_bits)
    if abits:
        out.append(acc & 0xFF)
    return bytes(out)


def _gif_frame_indices(canvas: "Canvas") -> tuple[list[int],
                                                  list[tuple[int, int, int]]]:
    """帧缓冲 → LZW 索引序列 + 首现序调色板。"""
    palette: dict[tuple[int, int, int], int] = {}
    order: list[tuple[int, int, int]] = []
    indices: list[int] = []
    for row in canvas._pixels:
        for px in row:
            rgb = px.to_rgb()
            i = palette.get(rgb)
            if i is None:
                i = len(order)
                palette[rgb] = i
                order.append(rgb)
            indices.append(i)
    return indices, order


def to_gif_bytes(canvases: list["Canvas"], delay_ms: float = 100) -> bytes:
    """多帧画布 → GIF89a 字节（每帧独立局部色表 + Netscape 无限循环）。"""
    if not canvases:
        raise ValueError("动图至少需要一帧画布")
    if not isinstance(delay_ms, (int, float)) or isinstance(delay_ms, bool) \
            or delay_ms < 0:
        raise ValueError(f"延时毫秒必须是非负数: {delay_ms!r}")
    delay_cs = int(delay_ms) // 10
    if delay_cs > 65535:
        raise ValueError(f"延时毫秒超过 GIF 上限 655350: {delay_ms!r}")
    for i, cv in enumerate(canvases):
        if not isinstance(cv, Canvas):
            raise ValueError(f"帧 {i} 不是画布对象")
    w = int(canvases[0].width)
    h = int(canvases[0].height)
    frames = []
    for i, cv in enumerate(canvases):
        if int(cv.width) != w or int(cv.height) != h:
            raise ValueError(
                f"帧 {i} 尺寸 {int(cv.width)}x{int(cv.height)} 与首帧 "
                f"{w}x{h} 不一致（GIF 逻辑屏统一）")
        indices, palette = _gif_frame_indices(cv)
        if len(palette) > 256:
            raise ValueError(
                f"帧 {i} 颜色数 {len(palette)} 超过 GIF 调色板上限 256")
        frames.append((w, h, indices, palette))

    buf = bytearray(b"GIF89a")
    buf += struct.pack("<HH", w, h)
    buf += bytes([0x70, 0, 0])
    buf += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", 0) + b"\x00"
    for (fw, fh, indices, palette) in frames:
        buf += (b"\x21\xF9\x04" + bytes([0]) + struct.pack("<H", delay_cs)
                + bytes([0, 0]))
        size_bits = max(1, (len(palette) - 1).bit_length())
        buf += (b"\x2C" + struct.pack("<HHHH", 0, 0, fw, fh)
                + bytes([0x80 | (size_bits - 1)]))
        for r, g, b in palette:
            buf += bytes([r, g, b])
        for _ in range((1 << size_bits) - len(palette)):
            buf += b"\x00\x00\x00"
        mcs = max(2, (len(palette) - 1).bit_length())
        buf += bytes([mcs])
        data = _gif_lzw_encode(indices, mcs)
        for i in range(0, len(data), 255):
            chunk = data[i:i + 255]
            buf += bytes([len(chunk)]) + chunk
        buf += b"\x00"
    buf += b"\x3B"
    return bytes(buf)


def save_gif(canvases: list["Canvas"], delay_ms: float, path: str) -> dict:
    """多帧画布保存为 .gif；视频容器格式（MP4 等）需要编解码器，如实拒绝。"""
    ext = Path(path).suffix.lower()
    if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
        return {"成功": False, "路径": str(path), "错误":
                f"视频编码（{ext[1:].upper()}）需要编解码器，纯标准库无法实现；"
                "支持 .gif"}
    if ext != ".gif":
        return {"成功": False, "路径": str(path), "错误":
                f"不支持的动图格式: {ext}（支持 .gif）"}
    try:
        data = to_gif_bytes(canvases, delay_ms)
    except ValueError as e:
        return {"成功": False, "路径": str(path), "错误": str(e)}
    try:
        p = Path(path)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    except OSError as e:
        return {"成功": False, "路径": str(path), "错误": str(e)}
    return {"成功": True, "路径": str(path), "格式": "gif",
            "字节": len(data), "帧数": len(canvases)}


# ============================================================
# 注册
# ============================================================

def _cur2(f):
    return lambda a: lambda b: f(a, b)


def _cur3(f):
    return lambda a: lambda b: lambda c: f(a, b, c)


def _cur4(f):
    return lambda a: lambda b: lambda c: lambda d: f(a, b, c, d)


def _cur5(f):
    return lambda a: lambda b: lambda c: lambda d: lambda e: f(a, b, c, d, e)


def _cur6(f):
    return (lambda a: lambda b: lambda c: lambda d: lambda e: lambda g:
            f(a, b, c, d, e, g))


def _cur8(f):
    return (lambda a: lambda b: lambda c: lambda d: lambda e: lambda g:
            lambda h: lambda i: f(a, b, c, d, e, g, h, i))


def _register_graphics(builtins: dict) -> None:
    # 多参符号一律柯里化链（与 data_science/quantum 同款）：
    # 宿主 _apply 单参逐级应用，VM CALL 逐参应用，三端布局一致。
    builtins["创建画布"] = _cur2(lambda w, h: Canvas(w, h))
    builtins["清除画布"] = _cur2(lambda cv, c: cv.clear(_color_from_spec(c)))
    builtins["设置填充"] = _cur2(lambda cv, c: cv.set_fill(_color_from_spec(c)))
    builtins["设置描边"] = _cur3(lambda cv, c, w: cv.set_stroke(_color_from_spec(c), w))
    builtins["填充矩形"] = _cur5(lambda cv, x, y, w, h: cv.fill_rect(x, y, w, h))
    builtins["描边矩形"] = _cur5(lambda cv, x, y, w, h: cv.stroke_rect(x, y, w, h))
    builtins["填充圆形"] = _cur4(lambda cv, cx, cy, r: cv.fill_circle(cx, cy, r))
    builtins["描边圆形"] = _cur4(lambda cv, cx, cy, r: cv.stroke_circle(cx, cy, r))
    builtins["画线"] = _cur5(lambda cv, x1, y1, x2, y2: cv.draw_line(x1, y1, x2, y2))
    builtins["画文字"] = _cur4(lambda cv, x, y, t: cv.draw_text(x, y, t))
    builtins["画布JSON"] = lambda cv: cv.to_json()
    builtins["保存画布"] = _cur2(lambda cv, p: cv.save(p))
    builtins["颜色红"] = Color.red
    builtins["颜色绿"] = Color.green
    builtins["颜色蓝"] = Color.blue
    builtins["颜色白"] = Color.white
    builtins["颜色黑"] = Color.black
    builtins["颜色从十六进制"] = Color.from_hex
    builtins["创建渐变"] = lambda spec: Gradient(**spec)
    builtins["创建字体"] = _cur4(lambda f, s, b, i: Font(f, s, b, i))
    builtins["创建渲染器"] = lambda cv: Renderer(cv)
    # 着色器/帧缓冲/计算
    builtins["创建着色器"] = _cur2(lambda cv, s: cv.create_shader(s))
    builtins["创建帧缓冲"] = _cur3(lambda cv, w, h: cv.create_framebuffer(w, h))
    builtins["绑定帧缓冲"] = _cur2(lambda cv, fb: cv.bind_framebuffer(fb))
    builtins["计算着色器"] = _cur3(lambda cv, w, h: cv.compute_shader(w, h))
    builtins["生成Mipmap"] = lambda cv: cv.generate_mipmap()
    builtins["设置视口"] = _cur5(lambda cv, x, y, w, h: cv.set_viewport(x, y, w, h))
    builtins["清除缓冲"] = lambda cv: cv.clear_buffers()
    # 3D建模（指令登记面；c 必填）
    builtins["绘制立方体"] = _cur5(lambda cv, cx, cy, s, c: cv.draw_cube(cx, cy, s, _color_from_spec(c)))
    builtins["绘制球体"] = _cur5(lambda cv, cx, cy, r, c: cv.draw_sphere(cx, cy, r, _color_from_spec(c)))
    builtins["绘制圆柱"] = _cur6(lambda cv, cx, cy, r, h, c: cv.draw_cylinder(cx, cy, r, h, _color_from_spec(c)))
    builtins["绘制金字塔"] = _cur5(lambda cv, cx, cy, s, c: cv.draw_pyramid(cx, cy, s, _color_from_spec(c)))
    builtins["绘制三角面"] = _cur8(lambda cv, x1, y1, x2, y2, x3, y3, c:
                                   cv.draw_triangle_3d(x1, y1, x2, y2, x3, y3, _color_from_spec(c)))
    # 绘画工具（状态色面：颜色来自 设置填充/设置描边）
    builtins["画笔"] = _cur4(lambda cv, x, y, r: cv.paint_brush(x, y, r))
    builtins["油漆桶"] = _cur3(lambda cv, x, y: cv.paint_fill(x, y))
    builtins["橡皮擦"] = _cur4(lambda cv, x, y, r: cv.paint_eraser(x, y, r))
    builtins["绘画线"] = _cur6(lambda cv, x1, y1, x2, y2, w: cv.paint_line(x1, y1, x2, y2, w))
    builtins["绘画矩形"] = _cur6(lambda cv, x, y, w, h, f: cv.paint_rect(x, y, w, h, f))
    builtins["绘画圆形"] = _cur4(lambda cv, cx, cy, r: cv.paint_circle(cx, cy, r))
    builtins["设置笔刷大小"] = _cur2(lambda cv, s: cv.set_brush_size(s))
    builtins["设置抗锯齿"] = _cur2(lambda cv, e: cv.set_antialias(e))
    # 显式颜色绘图（阶段 24b：像素真落盘 + 图片生成与输出）
    builtins["画点"] = _cur4(lambda cv, x, y, c: cv.raster_pixel(x, y, _rgb_from_spec(c)))
    builtins["画底色"] = _cur2(lambda cv, c: cv.raster_rect(0, 0, cv.width, cv.height, _rgb_from_spec(c)))
    builtins["画矩形"] = _cur6(lambda cv, x, y, w, h, c: cv.raster_rect(x, y, w, h, _rgb_from_spec(c)))
    builtins["画矩形边框"] = _cur6(lambda cv, x, y, w, h, c: cv.raster_rect(x, y, w, h, _rgb_from_spec(c), outline=True))
    builtins["画圆"] = _cur5(lambda cv, cx, cy, r, c: cv.raster_circle(cx, cy, r, _rgb_from_spec(c), fill=True))
    builtins["画圆边框"] = _cur5(lambda cv, cx, cy, r, c: cv.raster_circle(cx, cy, r, _rgb_from_spec(c), fill=False))
    builtins["画文本"] = _cur5(lambda cv, x, y, t, c: cv.raster_text(x, y, t, _rgb_from_spec(c)))
    builtins["填色"] = _cur4(lambda cv, x, y, c: cv.raster_flood_fill(x, y, _rgb_from_spec(c)))
    builtins["像素值"] = _cur3(lambda cv, x, y: cv.pixel_at(x, y))
    builtins["保存图片"] = _cur2(lambda cv, p: cv.save_image(p))
    builtins["图片PNG"] = lambda cv: cv.to_png_bytes()
    builtins["图片PPM"] = lambda cv: cv.to_ppm_bytes()
    builtins["图片SVG"] = lambda cv: cv.to_svg()
    builtins["图片尺寸"] = lambda cv: {"宽": int(cv.width), "高": int(cv.height)}
    # 图像操作
    builtins["调整大小"] = _cur3(lambda cv, w, h: cv.resize(w, h))
    builtins["旋转画布"] = _cur2(lambda cv, a: cv.rotate(a))
    builtins["水平翻转"] = lambda cv: cv.flip_horizontal()
    builtins["垂直翻转"] = lambda cv: cv.flip_vertical()
    builtins["裁剪"] = _cur5(lambda cv, x, y, w, h: cv.crop(x, y, w, h))
    builtins["模糊"] = _cur2(lambda cv, r: cv.blur(r))
    builtins["锐化"] = lambda cv: cv.sharpen()
    builtins["调整亮度"] = _cur2(lambda cv, f: cv.adjust_brightness(f))
    builtins["调整对比度"] = _cur2(lambda cv, f: cv.adjust_contrast(f))
    # 动图生成与输出（阶段 24c：GIF89a 纯标准库真编码）
    builtins["生成动图"] = _cur3(lambda frames, delay_ms, path:
                                 save_gif(frames, delay_ms, path))


def _graphics_symtab_names() -> list[str]:
    return [
        "创建画布", "清除画布", "设置填充", "设置描边",
        "填充矩形", "描边矩形", "填充圆形", "描边圆形",
        "画线", "画文字", "画布JSON", "保存画布",
        "颜色红", "颜色绿", "颜色蓝", "颜色白", "颜色黑",
        "颜色从十六进制", "创建渐变", "创建字体", "创建渲染器",
        "绘制立方体", "绘制球体", "绘制圆柱", "绘制金字塔", "绘制三角面",
        "画笔", "油漆桶", "橡皮擦", "绘画线", "绘画矩形", "绘画圆形",
        "设置笔刷大小", "设置抗锯齿",
        "画点", "画底色", "画矩形", "画矩形边框", "画圆", "画圆边框",
        "画文本", "填色", "像素值",
        "保存图片", "图片PNG", "图片PPM", "图片SVG", "图片尺寸",
        "调整大小", "旋转画布", "水平翻转", "垂直翻转", "裁剪",
        "模糊", "锐化", "调整亮度", "调整对比度", "生成动图",
        "创建着色器", "创建帧缓冲", "绑定帧缓冲", "计算着色器", "生成Mipmap", "设置视口", "清除缓冲",
    ]


__all__ = [
    "Color", "Canvas", "Point", "Size", "Rect",
    "Gradient", "Font", "Renderer",
    "_register_graphics", "_graphics_symtab_names",
]
