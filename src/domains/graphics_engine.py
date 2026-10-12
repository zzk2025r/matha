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
from dataclasses import dataclass, field

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
        self._commands.append({"type": "clear", "color": c.to_hex()})

    def set_fill(self, color: Color) -> None:
        """设置填充颜色。"""
        self._fill_color = color

    def set_stroke(self, color: Color, width: float = 1.0) -> None:
        """设置描边颜色和宽度。"""
        self._stroke_color = color
        self._stroke_width = width

    def fill_rect(self, x: float, y: float, w: float, h: float) -> None:
        """填充矩形。"""
        self._commands.append({"type": "fill_rect", "x": x, "y": y, "width": w, "height": h,
                               "color": self._fill_color.to_hex()})

    def stroke_rect(self, x: float, y: float, w: float, h: float) -> None:
        """描边矩形。"""
        self._commands.append({"type": "stroke_rect", "x": x, "y": y, "width": w, "height": h,
                               "color": self._stroke_color.to_hex(), "stroke_width": self._stroke_width})

    def fill_circle(self, cx: float, cy: float, r: float) -> None:
        """填充圆。"""
        self._commands.append({"type": "fill_circle", "cx": cx, "cy": cy, "radius": r,
                               "color": self._fill_color.to_hex()})

    def stroke_circle(self, cx: float, cy: float, r: float) -> None:
        """描边圆。"""
        self._commands.append({"type": "stroke_circle", "cx": cx, "cy": cy, "radius": r,
                               "color": self._stroke_color.to_hex(), "width": self._stroke_width})

    def draw_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """画线。"""
        self._commands.append({"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                               "color": self._stroke_color.to_hex(), "width": self._stroke_width})

    def draw_text(self, x: float, y: float, text: str) -> None:
        """画文字。"""
        self._commands.append({"type": "text", "x": x, "y": y, "text": text,
                               "color": self._stroke_color.to_hex(), "font_size": self._font_size})

    def fill_polygon(self, points: list[Point]) -> None:
        """填充多边形。"""
        self._commands.append({"type": "fill_polygon", "points": [(p.x, p.y) for p in points],
                               "color": self._fill_color.to_hex()})

    def get_pixel(self, x: int, y: int) -> Color:
        """获取像素颜色。"""
        if 0 <= y < len(self._pixels) and 0 <= x < len(self._pixels[0]):
            return self._pixels[y][x]
        return Color.black()

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        """设置像素颜色。"""
        if 0 <= y < len(self._pixels) and 0 <= x < len(self._pixels[0]):
            self._pixels[y][x] = color

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
        """绘画笔刷。"""
        c = color or self._fill_color
        self._commands.append({"type": "brush", "x": x, "y": y,
                                "radius": radius, "color": c.to_hex()})

    def paint_fill(self, x: float, y: float,
                    color: Color | None = None) -> None:
        """油漆桶填充。"""
        c = color or self._fill_color
        self._commands.append({"type": "flood_fill", "x": x, "y": y,
                                "color": c.to_hex()})

    def paint_eraser(self, x: float, y: float,
                      radius: float = 10.0) -> None:
        """橡皮擦。"""
        self._commands.append({"type": "eraser", "x": x, "y": y,
                                "radius": radius})

    def paint_line(self, x1: float, y1: float, x2: float, y2: float,
                    width: float = 2.0,
                    color: Color | None = None) -> None:
        """绘画线条（带宽度）。"""
        c = color or self._stroke_color
        self._commands.append({"type": "paint_line", "x1": x1, "y1": y1,
                                "x2": x2, "y2": y2, "width": width,
                                "color": c.to_hex()})

    def paint_rect(self, x: float, y: float, w: float, h: float,
                    fill: bool = True,
                    color: Color | None = None) -> None:
        """绘画矩形。"""
        c = color or self._fill_color
        self._commands.append({"type": "paint_rect", "x": x, "y": y,
                                "width": w, "height": h, "fill": fill,
                                "color": c.to_hex()})

    def paint_circle(self, cx: float, cy: float, r: float,
                      color: Color | None = None) -> None:
        """绘画圆形。"""
        c = color or self._fill_color
        self._commands.append({"type": "paint_circle", "cx": cx, "cy": cy,
                                "radius": r, "color": c.to_hex()})

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
# 注册
# ============================================================

def _register_graphics(builtins: dict) -> None:
    builtins["创建画布"] = lambda w=800, h=600: Canvas(w, h)
    builtins["清除画布"] = lambda canvas, c=None: canvas.clear(c)
    builtins["设置填充"] = lambda canvas, c: canvas.set_fill(c)
    builtins["设置描边"] = lambda canvas, c, w=1.0: canvas.set_stroke(c, w)
    builtins["填充矩形"] = lambda canvas, x, y, w, h: canvas.fill_rect(x, y, w, h)
    builtins["描边矩形"] = lambda canvas, x, y, w, h: canvas.stroke_rect(x, y, w, h)
    builtins["填充圆形"] = lambda canvas, cx, cy, r: canvas.fill_circle(cx, cy, r)
    builtins["描边圆形"] = lambda canvas, cx, cy, r: canvas.stroke_circle(cx, cy, r)
    builtins["画线"] = lambda canvas, x1, y1, x2, y2: canvas.draw_line(x1, y1, x2, y2)
    builtins["画文字"] = lambda canvas, x, y, t: canvas.draw_text(x, y, t)
    builtins["画布JSON"] = lambda canvas: canvas.to_json()
    builtins["保存画布"] = lambda canvas, p: canvas.save(p)
    builtins["颜色红"] = Color.red
    builtins["颜色绿"] = Color.green
    builtins["颜色蓝"] = Color.blue
    builtins["颜色白"] = Color.white
    builtins["颜色黑"] = Color.black
    builtins["颜色从十六进制"] = Color.from_hex
    builtins["创建渐变"] = lambda **kw: Gradient(**kw)
    builtins["创建字体"] = lambda f="monospace", s=12, b=False, i=False: Font(f, s, b, i)
    builtins["创建渲染器"] = lambda canvas: Renderer(canvas)
    # 着色器/帧缓冲/计算
    builtins["创建着色器"] = lambda canvas, s: canvas.create_shader(s)
    builtins["创建帧缓冲"] = lambda canvas, w, h: canvas.create_framebuffer(w, h)
    builtins["绑定帧缓冲"] = lambda canvas, fb: canvas.bind_framebuffer(fb)
    builtins["计算着色器"] = lambda canvas, w, h: canvas.compute_shader(w, h)
    builtins["生成Mipmap"] = lambda canvas: canvas.generate_mipmap()
    builtins["设置视口"] = lambda canvas, x, y, w, h: canvas.set_viewport(x, y, w, h)
    builtins["清除缓冲"] = lambda canvas: canvas.clear_buffers()
    # 3D建模
    builtins["绘制立方体"] = lambda canvas, cx, cy, s, c=None: canvas.draw_cube(cx, cy, s, c)
    builtins["绘制球体"] = lambda canvas, cx, cy, r, c=None: canvas.draw_sphere(cx, cy, r, c)
    builtins["绘制圆柱"] = lambda canvas, cx, cy, r, h, c=None: canvas.draw_cylinder(cx, cy, r, h, c)
    builtins["绘制金字塔"] = lambda canvas, cx, cy, s, c=None: canvas.draw_pyramid(cx, cy, s, c)
    builtins["绘制三角面"] = lambda canvas, x1, y1, x2, y2, x3, y3, c=None: canvas.draw_triangle_3d(x1, y1, x2, y2, x3, y3, c)
    # 绘画工具
    builtins["画笔"] = lambda canvas, x, y, r=5.0, c=None: canvas.paint_brush(x, y, r, c)
    builtins["油漆桶"] = lambda canvas, x, y, c=None: canvas.paint_fill(x, y, c)
    builtins["橡皮擦"] = lambda canvas, x, y, r=10.0: canvas.paint_eraser(x, y, r)
    builtins["绘画线"] = lambda canvas, x1, y1, x2, y2, w=2.0, c=None: canvas.paint_line(x1, y1, x2, y2, w, c)
    builtins["绘画矩形"] = lambda canvas, x, y, w, h, f=True, c=None: canvas.paint_rect(x, y, w, h, f, c)
    builtins["绘画圆形"] = lambda canvas, cx, cy, r, c=None: canvas.paint_circle(cx, cy, r, c)
    builtins["设置笔刷大小"] = lambda canvas, s: canvas.set_brush_size(s)
    builtins["设置抗锯齿"] = lambda canvas, e: canvas.set_antialias(e)
    # 图像操作
    builtins["调整大小"] = lambda canvas, w, h: canvas.resize(w, h)
    builtins["旋转画布"] = lambda canvas, a: canvas.rotate(a)
    builtins["水平翻转"] = lambda canvas: canvas.flip_horizontal()
    builtins["垂直翻转"] = lambda canvas: canvas.flip_vertical()
    builtins["裁剪"] = lambda canvas, x, y, w, h: canvas.crop(x, y, w, h)
    builtins["模糊"] = lambda canvas, r=2.0: canvas.blur(r)
    builtins["锐化"] = lambda canvas: canvas.sharpen()
    builtins["调整亮度"] = lambda canvas, f: canvas.adjust_brightness(f)
    builtins["调整对比度"] = lambda canvas, f: canvas.adjust_contrast(f)
    # 着色器/帧缓冲/计算
    builtins["创建着色器"] = lambda canvas, s: canvas.create_shader(s)
    builtins["创建帧缓冲"] = lambda canvas, w, h: canvas.create_framebuffer(w, h)
    builtins["绑定帧缓冲"] = lambda canvas, fb: canvas.bind_framebuffer(fb)
    builtins["计算着色器"] = lambda canvas, w, h: canvas.compute_shader(w, h)
    builtins["生成Mipmap"] = lambda canvas: canvas.generate_mipmap()
    builtins["设置视口"] = lambda canvas, x, y, w, h: canvas.set_viewport(x, y, w, h)
    builtins["清除缓冲"] = lambda canvas: canvas.clear_buffers()


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
        "调整大小", "旋转画布", "水平翻转", "垂直翻转", "裁剪",
        "模糊", "锐化", "调整亮度", "调整对比度",
        "创建着色器", "创建帧缓冲", "绑定帧缓冲", "计算着色器", "生成Mipmap", "设置视口", "清除缓冲",
    ]


__all__ = [
    "Color", "Canvas", "Point", "Size", "Rect",
    "Gradient", "Font", "Renderer",
    "_register_graphics", "_graphics_symtab_names",
]
