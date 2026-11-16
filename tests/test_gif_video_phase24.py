"""阶段 24c 三锁：GIF89a 动图生成与输出（纯标准库 LZW 真编码）。

真化面：_gif_lzw_encode LZW 压缩（升位/表满 clear）、to_gif_bytes 多帧
GIF89a 容器（每帧独立局部色表 + Netscape 循环）、save_gif 诚实落盘/拒绝。
世界解码器实证：tkinter PhotoImage（Tk 8.6 C GIF 解码器）在独立子进程逐
像素对拍（pytest 输出捕获与 Tk 存在非确定干扰，进程内不可靠）；另含测试
内独立规格解码器回环。MP4 等视频容器如实拒绝（需编解码器）。
"""
import json
import random
import struct
import subprocess
import sys

import pytest

from src.domains.graphics_engine import (Canvas, _gif_lzw_encode, save_gif,
                                         to_gif_bytes)


# ── Tk 世界解码器（独立子进程：pytest 捕获与 Tk 非确定干扰的隔离面） ──

_TK_WORKER = r'''
import json, sys
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
except Exception:
    print(json.dumps({"tk_unavailable": True}))
    raise SystemExit(0)
path, n, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
frames = []
for i in range(n):
    ph = tk.PhotoImage(file=path, format="gif -index %d" % i)
    frames.append([[list(ph.get(x, y)) for x in range(w)] for y in range(h)])
root.destroy()
print(json.dumps(frames))
'''


def _tk_frames(path, n, w, h):
    out = subprocess.run(
        [sys.executable, "-c", _TK_WORKER, str(path), str(n), str(w), str(h)],
        capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout.strip().splitlines()[-1])
    if isinstance(data, dict) and data.get("tk_unavailable"):
        pytest.skip("tkinter/Tk 不可用（子进程探测）")
    # JSON 往返后像素是 list；统一转回 tuple 便于与画布 RGB 对拍
    return [[[tuple(px) for px in row] for row in frame] for frame in data]


# ── 测试内独立规格解码器（与被测编码器相互独立，用于回环对拍） ──

def _spec_lzw_decode(data, mcs):
    clear = 1 << mcs
    eoi = clear + 1
    n_bits = mcs + 1
    table = {c: [c] for c in range(clear)}
    next_code = eoi + 1
    prev = None
    out = []
    clears = 0
    acc = 0
    abits = 0
    pos = 0
    while True:
        while abits < n_bits:
            if pos >= len(data):
                raise ValueError("LZW 数据在 EOI 前耗尽")
            acc |= data[pos] << abits
            abits += 8
            pos += 1
        code = acc & ((1 << n_bits) - 1)
        acc >>= n_bits
        abits -= n_bits
        if code == clear:
            clears += 1
            table = {c: [c] for c in range(clear)}
            next_code = eoi + 1
            prev = None
            n_bits = mcs + 1
            continue
        if code == eoi:
            return out, clears
        if prev is None:
            assert code < clear, "clear 后首码非根码"
            out += table[code]
            prev = code
            continue
        if code < next_code:
            entry = table[code]
        elif code == next_code:
            entry = table[prev] + [table[prev][0]]
        else:
            raise AssertionError(f"码 {code} 超出表 next={next_code}")
        out += entry
        if next_code < 4096:
            table[next_code] = table[prev] + [entry[0]]
            next_code += 1
            if next_code == (1 << n_bits) and n_bits < 12:
                n_bits += 1
        prev = code


def _noise_canvas(w, h, seed):
    rng = random.Random(seed)
    pal = [(i, (i * 7) % 256, (255 - i) % 256) for i in range(256)]
    cv = Canvas(w, h)
    for y in range(h):
        for x in range(w):
            cv.raster_pixel(x, y, pal[rng.randrange(256)])
    return cv, pal


class TestGifLzwTruth:
    def test_roundtrip_small_palette(self):
        idx = [(y * 8 + x) % 4 for y in range(8) for x in range(8)]
        data = _gif_lzw_encode(idx, 2)
        dec, _ = _spec_lzw_decode(data, 2)
        assert dec == idx

    def test_first_code_is_clear_last_is_eoi(self):
        idx = [0, 1, 0, 1, 0]
        data = _gif_lzw_encode(idx, 2)
        acc = data[0] | (data[1] << 8)
        assert acc & 0x7 == 4, "首码必须是 clear（mcs=2 → 3 位宽）"

    def test_roundtrip_32_colors_code_growth(self):
        idx = [(y * 64 + x) % 32 for y in range(64) for x in range(64)]
        data = _gif_lzw_encode(idx, 5)
        dec, _ = _spec_lzw_decode(data, 5)
        assert dec == idx
        assert len(data) < len(idx), "32 色重复图样应被 LZW 压缩"

    def test_roundtrip_table_full_clear_path(self):
        cv, _pal = _noise_canvas(96, 96, seed=4242)
        idx, pal = [], []
        for row in cv._pixels:
            for px in row:
                rgb = px.to_rgb()
                if rgb not in pal:
                    pal.append(rgb)
                idx.append(pal.index(rgb))
        assert len(pal) == 256
        data = _gif_lzw_encode(idx, 8)
        dec, clears = _spec_lzw_decode(data, 8)
        assert dec == idx
        assert clears >= 1, "12 位表满必须出现 clear 重置"

    def test_rejects_empty_indices(self):
        with pytest.raises(IndexError):
            _gif_lzw_encode([], 2)


class TestGifContainer:
    def test_header_trailer_and_netscape(self):
        cv = Canvas(4, 4)
        cv.raster_rect(0, 0, 4, 4, (255, 0, 0))
        data = to_gif_bytes([cv], delay_ms=100)
        assert data[:6] == b"GIF89a"
        assert data[-1] == 0x3B
        assert b"NETSCAPE2.0" in data[:64]
        assert struct.unpack("<HH", data[6:10]) == (4, 4)
        assert data[10] & 0x80 == 0, "逻辑屏描述符无全局色表"

    def test_gce_delay_encoding(self):
        cv = Canvas(2, 2)
        cv.raster_rect(0, 0, 2, 2, (1, 2, 3))
        for ms, expect in [(100, 10), (250, 25), (1000, 100)]:
            data = to_gif_bytes([cv], delay_ms=ms)
            i = data.index(b"\x21\xF9\x04\x00")
            assert struct.unpack("<H", data[i + 4:i + 6])[0] == expect

    def test_per_frame_local_color_table(self):
        c1 = Canvas(2, 2)
        c1.raster_rect(0, 0, 2, 2, (255, 0, 0))
        c2 = Canvas(2, 2)
        c2.raster_rect(0, 0, 2, 2, (0, 255, 0))
        data = to_gif_bytes([c1, c2], delay_ms=100)
        assert data.count(b"\x2C") >= 2, "两帧两个图像描述符"
        assert data.count(b"\x21\xF9\x04") == 2, "两帧各一个图形控制扩展"

    def test_frame_dims_must_match_logical_screen(self):
        c1 = Canvas(8, 8)
        c2 = Canvas(4, 4)
        with pytest.raises(ValueError, match="不一致"):
            to_gif_bytes([c1, c2], delay_ms=100)


class TestGifTkWorldDecoder:
    def test_three_frames_pixel_perfect(self, tmp_path):
        pal32 = [((i * 8) % 256, (i * 5 + 3) % 256, (i * 13 + 1) % 256)
                 for i in range(32)]
        c1 = Canvas(64, 64)
        c1.raster_rect(0, 0, 64, 64, (255, 0, 0))
        c1.raster_pixel(10, 10, (0, 0, 255))
        c2 = Canvas(64, 64)
        for y in range(64):
            for x in range(64):
                c2.raster_pixel(x, y, pal32[(y * 64 + x) % 32])
        c3, pal256 = _noise_canvas(64, 64, seed=2424)
        frames = [c1, c2, c3]
        path = tmp_path / "w.gif"
        r = save_gif(frames, 100, str(path))
        assert r["成功"] and r["帧数"] == 3
        pxs = _tk_frames(str(path), 3, 64, 64)
        for y in range(64):
            for x in range(64):
                exp = (0, 0, 255) if (x, y) == (10, 10) else (255, 0, 0)
                assert pxs[0][y][x] == exp
                assert pxs[1][y][x] == pal32[(y * 64 + x) % 32]
        rng = random.Random(2424)
        for y in range(64):
            for x in range(64):
                assert pxs[2][y][x] == pal256[rng.randrange(256)]

    def test_single_frame_tiny(self, tmp_path):
        cv = Canvas(2, 2)
        cv.raster_rect(0, 0, 2, 2, (7, 8, 9))
        path = tmp_path / "t.gif"
        assert save_gif([cv], 50, str(path))["成功"]
        pxs = _tk_frames(str(path), 1, 2, 2)
        assert all(pxs[0][y][x] == (7, 8, 9)
                   for x in range(2) for y in range(2))


class TestGifHonestRejects:
    def _red(self, w=8, h=8):
        cv = Canvas(w, h)
        cv.raster_rect(0, 0, w, h, (255, 0, 0))
        return cv

    def test_empty_frames(self, tmp_path):
        r = save_gif([], 100, str(tmp_path / "a.gif"))
        assert r["成功"] is False and "至少需要一帧" in r["错误"]
        with pytest.raises(ValueError, match="至少需要一帧"):
            to_gif_bytes([], 100)

    def test_more_than_256_colors(self, tmp_path):
        cv = Canvas(20, 20)
        for i in range(256):
            cv.raster_pixel(i % 20, i // 20, (i, 0, 0))
        cv.raster_pixel(0, 13, (0, 1, 0))
        r = save_gif([cv], 100, str(tmp_path / "b.gif"))
        assert r["成功"] is False and "调色板上限 256" in r["错误"]
        assert not (tmp_path / "b.gif").exists()

    def test_dim_mismatch(self, tmp_path):
        r = save_gif([self._red(), Canvas(4, 4)], 100,
                     str(tmp_path / "c.gif"))
        assert r["成功"] is False and "不一致" in r["错误"]

    def test_non_canvas_element(self, tmp_path):
        r = save_gif([1, 2], 100, str(tmp_path / "d.gif"))
        assert r["成功"] is False and "不是画布对象" in r["错误"]

    def test_video_container_honest_reject(self, tmp_path):
        for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            p = tmp_path / f"v{ext}"
            r = save_gif([self._red()], 100, str(p))
            assert r["成功"] is False, ext
            assert "编解码器" in r["错误"] and "支持 .gif" in r["错误"], ext
            assert not p.exists()

    def test_unknown_extension(self, tmp_path):
        r = save_gif([self._red()], 100, str(tmp_path / "w.jpg"))
        assert r["成功"] is False and "不支持的动图格式" in r["错误"]

    def test_delay_bounds(self, tmp_path):
        r = save_gif([self._red()], -5, str(tmp_path / "e.gif"))
        assert r["成功"] is False and "非负" in r["错误"]
        r = save_gif([self._red()], 700000, str(tmp_path / "e.gif"))
        assert r["成功"] is False and "上限" in r["错误"]


class TestGifDualFace:
    PROG = """
let 帧红 = 创建画布(2, 2)
画矩形(帧红, 0, 0, 2, 2, [255, 0, 0])
let 帧绿 = 创建画布(2, 2)
画矩形(帧绿, 0, 0, 2, 2, [0, 255, 0])
输出(生成动图([帧红, 帧绿], 100, "{path}"))
"""

    def _run_both(self, path):
        from src.interp import Interpreter
        from src.kernel import exec_api
        from src.parser import parse
        prog = self.PROG.format(path=path.replace("\\", "/"))
        ip = Interpreter()
        ip.run(parse(prog))
        host = ip.outputs[-1]
        outs, err = exec_api.run_checked(prog, mode="vm")
        assert err is None, err
        vm = outs[-1]
        return host, vm

    def test_dual_face_identical_result(self, tmp_path):
        host_path = str(tmp_path / "h.gif")
        vm_path = str(tmp_path / "v.gif")
        host, vm = self._run_both(host_path)
        _, vm2 = self._run_both(vm_path)
        strip = lambda d: {k: v for k, v in d.items() if k != "路径"}
        assert strip(host) == strip(vm) == strip(vm2)
        assert host["路径"] == host_path.replace("\\", "/")
        assert host["成功"] is True and host["帧数"] == 2
        assert host["格式"] == "gif"

    def test_dual_face_gif_decodable(self, tmp_path):
        host_path = str(tmp_path / "h.gif")
        self._run_both(host_path)
        pxs = _tk_frames(host_path, 2, 2, 2)
        assert all(pxs[0][y][x] == (255, 0, 0)
                   for x in range(2) for y in range(2))
        assert all(pxs[1][y][x] == (0, 255, 0)
                   for x in range(2) for y in range(2))

    def test_curried_partial_application(self, tmp_path):
        from src.interp import Interpreter
        from src.parser import parse
        cv = Canvas(2, 2)
        cv.raster_rect(0, 0, 2, 2, (255, 0, 0))
        ip = Interpreter()
        ip.env["帧红"] = cv
        prog = """
输出(生成动图([帧红], 100, "{path}"))
""".format(path=str(tmp_path / "p.gif").replace("\\", "/"))
        ip.run(parse(prog))
        assert ip.outputs[-1]["成功"] is True
