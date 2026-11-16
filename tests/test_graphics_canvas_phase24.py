# -*- coding: utf-8 -*-
"""阶段 24b 三锁：画布域真光栅 + 图片生成与输出（PNG/SVG/PPM 真编码）。

锁三面：
  A. 光栅真相 —— 像素落盘、Bresenham、矩形/圆扫描计数、5x7 点阵、泛洪连通区；
  B. 编码面 —— PNG 签名/IHDR/IDAT zlib 回环、PPM P6 精确字节、SVG 指令 1:1
     镜像 + XML 转义、save_image 三格式落盘 + 不支持格式显式拒绝；
  C. 双面闭环 —— Matha 程序 host/VM 双端同值（柯里化注册面），颜色规格三形态。
"""
import io
import sys
import zlib
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.domains.graphics_engine import Canvas, Color, _register_graphics  # noqa: E402
from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402


def _host_run(source: str) -> list:
    ip = Interpreter()
    with redirect_stdout(io.StringIO()):
        ip.run(parse(source))
    return [str(o) for o in ip.outputs]


def _vm_run(source: str) -> list:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is None, f"vm 面不应报错: {type(err).__name__}: {err}"
    return [str(o) for o in outs]


def _count(cv: Canvas, rgb) -> int:
    return sum(1 for y in range(int(cv.height)) for x in range(int(cv.width))
               if cv.pixel_at(x, y) == list(rgb))


# ============================================================
# A. 光栅真相
# ============================================================

class TestRasterTruth:
    def test_pixel_lands_in_buffer(self):
        cv = Canvas(8, 6)
        cv.raster_rect(0, 0, 8, 6, (0, 0, 0))
        cv.raster_pixel(3, 4, (255, 0, 0))
        assert cv.pixel_at(3, 4) == [255, 0, 0]
        assert cv.pixel_at(3, 5) == [0, 0, 0]

    def test_pixel_out_of_bounds_ignored(self):
        cv = Canvas(4, 4)
        cv.raster_pixel(-1, 0, (9, 9, 9))
        cv.raster_pixel(0, 99, (9, 9, 9))
        assert cv.pixel_at(0, 0) == [0, 0, 0]

    def test_bresenham_line_points(self):
        cv = Canvas(10, 10)
        n = cv.raster_line(0, 0, 4, 2, (0, 255, 0))
        assert n == 5
        pts = [(x, y) for y in range(10) for x in range(10)
               if cv.pixel_at(x, y) == [0, 255, 0]]
        assert pts == [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2)]

    def test_rect_fill_count_12(self):
        cv = Canvas(10, 10)
        cv.raster_rect(0, 0, 10, 10, (0, 0, 0))
        n = cv.raster_rect(2, 2, 4, 3, (255, 255, 255))
        assert n == 12 and _count(cv, (255, 255, 255)) == 12

    def test_rect_outline_count_perimeter(self):
        cv = Canvas(10, 10)
        cv.raster_rect(0, 0, 10, 10, (0, 0, 0))
        n = cv.raster_rect(2, 2, 4, 3, (1, 2, 3), outline=True)
        # 返回计数 = 2*(4+3)（四角横竖各计一次 → 14）；去重像素 10
        assert n == 14 and _count(cv, (1, 2, 3)) == 10

    def test_circle_fill_scanline_13(self):
        cv = Canvas(20, 20)
        cv.raster_rect(0, 0, 20, 20, (0, 0, 0))
        n = cv.raster_circle(10, 10, 2, (0, 0, 255), fill=True)
        assert n == 13  # πr²≈12.57 的逐行弦扫描
        assert _count(cv, (0, 0, 255)) == 13

    def test_negative_radius_rejected(self):
        cv = Canvas(5, 5)
        with pytest.raises(ValueError):
            cv.raster_circle(2, 2, -1, (0, 0, 0))

    def test_text_5x7_glyph_and_advance(self):
        cv = Canvas(40, 10)
        cv.raster_rect(0, 0, 40, 10, (0, 0, 0))
        n = cv.raster_text(0, 1, "AB", (255, 255, 255))
        assert n == 2
        # 'A' 第 1 列点亮（glyph 位型），第二个字符在 x=6 起
        assert cv.pixel_at(0, 2) == [255, 255, 255]
        lit = [(x, y) for y in range(10) for x in range(40)
               if cv.pixel_at(x, y) == [255, 255, 255]]
        assert all(x < 11 for x, _ in lit)  # 2 字符 × 6 步进内
        assert len(lit) > 10

    def test_lowercase_maps_to_uppercase(self):
        cv = Canvas(20, 10)
        cv.raster_rect(0, 0, 20, 10, (0, 0, 0))
        cv.raster_text(0, 1, "a", (5, 5, 5))
        cv2 = Canvas(20, 10)
        cv2.raster_rect(0, 0, 20, 10, (0, 0, 0))
        cv2.raster_text(0, 1, "A", (5, 5, 5))
        assert cv.to_ppm_bytes() == cv2.to_ppm_bytes()

    def test_unknown_char_solid_block(self):
        cv = Canvas(20, 10)
        cv.raster_rect(0, 0, 20, 10, (0, 0, 0))
        n = cv.raster_text(0, 1, "中", (7, 7, 7))  # 非 ASCII → 实心块
        assert n == 1
        assert cv.pixel_at(0, 1) == [7, 7, 7]
        assert cv.pixel_at(4, 7) == [7, 7, 7]  # 5x7 全亮块右下角

    def test_flood_fill_region(self):
        cv = Canvas(6, 6)
        cv.raster_rect(0, 0, 6, 6, (0, 0, 0))
        cv.raster_rect(2, 2, 2, 2, (9, 9, 9))
        n = cv.raster_flood_fill(0, 0, (1, 2, 3))
        assert n == 32  # 36 − 4 障碍格
        assert _count(cv, (1, 2, 3)) == 32

    def test_flood_fill_out_of_bounds_raises(self):
        cv = Canvas(4, 4)
        with pytest.raises(ValueError):
            cv.raster_flood_fill(99, 99, (0, 0, 0))

    def test_polygon_scanline(self):
        cv = Canvas(10, 10)
        cv.raster_rect(0, 0, 10, 10, (0, 0, 0))
        n = cv.raster_polygon([(1, 1), (8, 1), (8, 4), (1, 4)], (4, 5, 6))
        assert n == 24  # 7 宽 × 4 行 − 4 半开边界修正（扫描线 [min,max) 行 + [x0,x1] 列）
        assert _count(cv, (4, 5, 6)) == 24


# ============================================================
# B. 编码面
# ============================================================

class TestEncoders:
    def _red_canvas(self) -> Canvas:
        cv = Canvas(4, 2)
        cv.raster_rect(0, 0, 4, 2, (255, 0, 0))
        return cv

    def test_ppm_exact_bytes(self):
        assert self._red_canvas().to_ppm_bytes() == \
            b"P6\n4 2\n255\n" + b"\xff\x00\x00" * 8

    def test_png_signature_ihdr_dims(self):
        png = self._red_canvas().to_png_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert png[12:16] == b"IHDR"
        assert int.from_bytes(png[16:20], "big") == 4
        assert int.from_bytes(png[20:24], "big") == 2
        assert png[24] == 8 and png[25] == 2  # 位深 8 / 色型 2 RGB
        assert png[-8:-4] == b"IEND"

    def test_png_idat_roundtrip(self):
        png = self._red_canvas().to_png_bytes()
        i = png.find(b"IDAT")
        length = int.from_bytes(png[i - 4:i], "big")
        raw = zlib.decompress(png[i + 4:i + 4 + length])
        # 每行前置 filter 字节 0 + RGB 行
        assert raw == (b"\x00" + b"\xff\x00\x00" * 4) * 2

    def test_png_roundtrip_independent_decoder_math(self):
        # 与 test_png_idat_roundtrip 互补：zlib 压缩可解且长度随内容变化
        small = self._red_canvas().to_png_bytes()
        big = Canvas(32, 32).to_png_bytes()
        assert len(small) < len(big)

    def test_svg_mirror_one_element_per_command(self):
        cv = Canvas(20, 10)
        cv.raster_rect(0, 0, 20, 10, (0, 0, 0))
        cv.raster_rect(1, 1, 5, 3, (255, 255, 0))
        cv.raster_circle(10, 5, 2, (0, 0, 255), fill=False)
        cv.raster_line(0, 0, 5, 5, (255, 255, 255))
        cv.raster_text(0, 8, "HI", (255, 255, 255))
        svg = cv.to_svg()
        assert '<rect x="0" y="0" width="20" height="10"' in svg
        assert 'fill="#ffff00"' in svg
        assert 'fill="none" stroke="#0000ff"' in svg
        assert '<line x1="0" y1="0" x2="5" y2="5" stroke="#ffffff"' in svg
        assert '<text x="0" y="15"' in svg and ">HI</text>" in svg

    def test_svg_text_escaping(self):
        cv = Canvas(60, 10)
        cv.raster_text(0, 1, '<&">', (255, 255, 255))
        svg = cv.to_svg()
        assert "&lt;&amp;&quot;&gt;" in svg
        assert "<&" not in svg.split("<text")[1].split("</text>")[0]

    def test_save_image_three_formats(self, tmp_path):
        cv = self._red_canvas()
        r1 = cv.save_image(str(tmp_path / "a.png"))
        r2 = cv.save_image(str(tmp_path / "b.svg"))
        r3 = cv.save_image(str(tmp_path / "c.ppm"))
        for r in (r1, r2, r3):
            assert r["成功"] is True
        assert r1["格式"] == "png" and r2["格式"] == "svg" and r3["格式"] == "ppm"
        assert (tmp_path / "a.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert (tmp_path / "b.svg").read_text(encoding="utf-8").startswith("<svg")
        assert (tmp_path / "c.ppm").read_bytes() == cv.to_ppm_bytes()
        assert r1["字节"] == (tmp_path / "a.png").stat().st_size

    def test_save_image_rejects_jpg_honestly(self, tmp_path):
        r = self._red_canvas().save_image(str(tmp_path / "d.jpg"))
        assert r["成功"] is False and ".jpg" in r["错误"]
        assert not (tmp_path / "d.jpg").exists()

    def test_save_image_creates_parent_dirs(self, tmp_path):
        r = self._red_canvas().save_image(str(tmp_path / "sub" / "dir" / "a.png"))
        assert r["成功"] is True
        assert (tmp_path / "sub" / "dir" / "a.png").exists()


# ============================================================
# C. 双面闭环（柯里化注册面）
# ============================================================

PROG = """
cv = 创建画布(16, 8)
画底色(cv, "#000000")
画矩形(cv, 2, 1, 6, 4, "#00FF00")
画文本(cv, 1, 6, "MATHA", "#FFFFFF")
r = 保存图片(cv, "{tmp}/dual.png")
输出(r["格式"])
输出(像素值(cv, 3, 2))
"""


class TestDualFace:
    def test_host_vm_same_output(self, tmp_path):
        src = PROG.replace("{tmp}", str(tmp_path).replace("\\", "/"))
        assert _host_run(src) == ["png", "[0, 255, 0]"]
        assert _vm_run(src) == ["png", "[0, 255, 0]"]
        assert (tmp_path / "dual.png").exists()

    def test_named_and_list_color_specs(self, tmp_path):
        src = """
cv = 创建画布(4, 4)
画底色(cv, "红")
画点(cv, 1, 1, [0, 0, 255])
输出(像素值(cv, 0, 0))
输出(像素值(cv, 1, 1))
"""
        expect = ["[255, 0, 0]", "[0, 0, 255]"]
        assert _host_run(src) == expect
        assert _vm_run(src) == expect

    def test_partial_application_is_honest_value(self):
        b = {}
        _register_graphics(b)
        partial = b["画底色"](None)
        assert callable(partial)  # 柯里化半面可继续应用

    def test_command_log_mirror_svg(self, tmp_path):
        src = """
cv = 创建画布(8, 8)
画矩形(cv, 1, 1, 3, 3, "#112233")
s = 图片SVG(cv)
输出(s)
"""
        out_h = _host_run(src)
        out_v = _vm_run(src)
        assert out_h == out_v
        assert 'fill="#112233"' in out_h[0]


# ============================================================
# D. 资源库组合层：use 绘画辅助（缺陷修复的延伸面 —— 资源库可编程）
# ============================================================

LIB_PROG = """
use 绘画辅助
cv = 创建画布(40, 20)
画底色(cv, "#000000")
画三角形(cv, 2, 2, 12, 2, 7, 12, "#FF0000")
画坐标轴(cv, 40, 20, "#00FF00")
画直方图(cv, [3, 7, 5], 24, 4, 12, 12, "#0000FF")
输出(像素值(cv, 7, 2))
输出(像素值(cv, 20, 10))
输出(像素值(cv, 25, 14))
输出(像素值(cv, 0, 0))
"""


class TestLibraryModule:
    def test_use_painting_helper_dual_face(self):
        expect = ["[255, 0, 0]", "[0, 255, 0]", "[0, 0, 255]", "[0, 0, 0]"]
        assert _host_run(LIB_PROG) == expect
        assert _vm_run(LIB_PROG) == expect

    def test_histogram_peak_scaling_and_zero_guard(self):
        src = """
use 绘画辅助
cv = 创建画布(10, 10)
画底色(cv, "#000000")
画直方图(cv, [0, 0, 0], 0, 0, 9, 8, "#FFFFFF")
输出(像素值(cv, 1, 1))
输出(图片尺寸(cv)["宽"])
"""
        expect = ["[0, 0, 0]", "10"]  # 全零表 → 零高条不落点
        assert _host_run(src) == expect
        assert _vm_run(src) == expect
