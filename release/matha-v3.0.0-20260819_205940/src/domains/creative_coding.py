# -*- coding: utf-8 -*-
"""
Matha 创意编程与艺术表达领域模块。

覆盖：
  1) Perlin / Simplex 噪声
  2) 流场
  3) 粒子系统
  4) 分形艺术
  5) 色彩系统
  6) 音频可视化
"""
from __future__ import annotations
import math
import random
from typing import Optional


# ============================================================
# Perlin 噪声
# ============================================================

class PerlinNoise:
    """Perlin 噪声生成器。"""

    def __init__(self, seed: int = 0):
        self.perm = self._shuffle(seed)

    def _shuffle(self, seed: int) -> list[int]:
        """生成排列。"""
        p = list(range(256))
        random_state = seed
        for i in range(255, 0, -1):
            random_state = (random_state * 1103515245 + 12345) & 0x7FFFFFFF
            j = random_state % (i + 1)
            p[i], p[j] = p[j], p[i]
        return p + p

    def _fade(self, t: float) -> float:
        """Fade 曲线：6t^5 - 15t^4 + 10t^3。"""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a: float, b: float, t: float) -> float:
        """线性插值。"""
        return a + t * (b - a)

    def _grad(self, hash_val: int, x: float, y: float) -> float:
        """梯度点积。"""
        h = hash_val & 3
        if h == 0: return x + y
        elif h == 1: return -x + y
        elif h == 2: return x - y
        else: return -x - y

    def noise_2d(self, x: float, y: float) -> float:
        """2D Perlin 噪声。"""
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255
        x -= math.floor(x)
        y -= math.floor(y)
        u = self._fade(x)
        v = self._fade(y)
        A = self.perm[X] + Y
        B = self.perm[X + 1] + Y
        return float(self._lerp(
            self._lerp(self._grad(self.perm[A], x, y), self._grad(self.perm[B], x - 1, y), u),
            self._lerp(self._grad(self.perm[A + 1], x, y - 1), self._grad(self.perm[B + 1], x - 1, y - 1), u),
            v
        ))

    def noise_3d(self, x: float, y: float, z: float) -> float:
        """3D Perlin 噪声。"""
        return self.noise_2d(x + z * 0.1, y + z * 0.1)  # 简化为 2.5D


# ============================================================
# Simplex 噪声（简化版）
# ============================================================

def simplex_noise_2d(x: float, y: float) -> float:
    """简化 Simplex 噪声。"""
    perlin = PerlinNoise(seed=42)
    return perlin.noise_2d(x, y)


# ============================================================
# 流场
# ============================================================

class FlowField:
    """流场。"""

    def __init__(self, width: int, height: int, scale: float = 10.0):
        self.width = width
        self.height = height
        self.scale = scale
        self.grid = [[(0.0, 0.0) for _ in range(height)] for _ in range(width)]
        self._generate()

    def _generate(self) -> None:
        """生成流场。"""
        perlin = PerlinNoise(seed=123)
        for x in range(self.width):
            for y in range(self.height):
                angle = perlin.noise_2d(x / self.scale, y / self.scale) * 2 * math.pi
                self.grid[x][y] = (math.cos(angle), math.sin(angle))

    def get_direction(self, x: int, y: int) -> tuple[float, float]:
        """获取指定位置的流向。"""
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        return self.grid[x][y]


# ============================================================
# 粒子系统
# ============================================================

def particle_system(n: int, width: float = 800.0, height: float = 600.0,
                    source_x: float = 400.0, source_y: float = 300.0) -> list[dict]:
    """初始化粒子系统。"""
    particles = []
    for i in range(n):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.0, 5.0)
        particles.append({
            "x": source_x, "y": source_y,
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": 1.0,
            "max_life": 1.0,
            "size": random.uniform(2.0, 5.0),
        })
    return particles


def particle_update(particles: list[dict], dt: float = 1/60, gravity: float = 0.0) -> list[dict]:
    """更新粒子。"""
    result = []
    for p in particles:
        p["x"] += p["vx"] * dt * 60
        p["y"] += p["vy"] * dt * 60
        p["vy"] += gravity * dt * 60
        p["life"] -= dt
        if p["life"] > 0:
            result.append(p)
    return result


# ============================================================
# 分形艺术
# ============================================================

def fractal_barnsley_fern(n: int = 10000) -> list[tuple[float, float]]:
    """Barnsley 蕨类分形。"""
    points = [(0.0, 0.0)]
    x, y = 0.0, 0.0
    for _ in range(n):
        r = random.random()
        if r < 0.01:
            xn = 0.0
            yn = 0.16 * y
        elif r < 0.86:
            xn = 0.85 * x + 0.04 * y
            yn = -0.04 * x + 0.85 * y + 1.6
        elif r < 0.93:
            xn = 0.2 * x - 0.26 * y
            yn = 0.23 * x + 0.22 * y + 1.6
        else:
            xn = -0.15 * x + 0.28 * y
            yn = 0.26 * x + 0.24 * y + 0.44
        x, y = xn, yn
        points.append((x, y))
    return points


def fractal_sierpinski(n: int = 10) -> list[tuple[float, float]]:
    """Sierpinski 三角形。"""
    points = [(0.0, 0.0), (1.0, 0.0), (0.5, math.sqrt(3)/2)]
    result = [points[0], points[1], points[2]]
    x, y = 0.5, 0.0
    for _ in range(n * 100):
        idx = random.randint(0, 2)
        mx = (x + points[idx][0]) / 2
        my = (y + points[idx][1]) / 2
        x, y = mx, my
        result.append((x, y))
    return result


# ============================================================
# 色彩系统
# ============================================================

def color_hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    """HSL 转 RGB。"""
    c = (1 - abs(2 * l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    m = l - c / 2
    if hp < 1:
        r, g, b = c, x, 0
    elif hp < 2:
        r, g, b = x, c, 0
    elif hp < 3:
        r, g, b = 0, c, x
    elif hp < 4:
        r, g, b = 0, x, c
    elif hp < 5:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (r + m, g + m, b + m)


def color_lerp(c1: tuple[float, float, float], c2: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    """颜色插值。"""
    return (
        c1[0] + t * (c2[0] - c1[0]),
        c1[1] + t * (c2[1] - c1[1]),
        c1[2] + t * (c2[2] - c1[2]),
    )


# ============================================================
# 音频可视化（简化）
# ============================================================

def audio_reactive(freq_bands: list[float], energy: float, sensitivity: float = 1.0) -> list[float]:
    """音频反应式可视化。"""
    return [b * energy * sensitivity for b in freq_bands]


def visual_midi(note: int, frequency: float = 440.0, duration: float = 0.5) -> dict:
    """MIDI 音符可视化。"""
    return {"note": note, "frequency": frequency, "duration": duration, "active": True}


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 噪声
    "PerlinNoise", "simplex_noise_2d",
    # 流场
    "FlowField",
    # 粒子
    "particle_system", "particle_update",
    # 分形
    "fractal_barnsley_fern", "fractal_sierpinski",
    # 色彩
    "color_hsl_to_rgb", "color_lerp",
    # 音频可视化
    "audio_reactive", "visual_midi",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_creative_coding(builtins: dict) -> None:
    """注册创意编程内建到解释器。"""
    perlin = PerlinNoise()
    builtins["Perlin噪声2D"] = perlin.noise_2d
    builtins["Simplex噪声2D"] = simplex_noise_2d
    builtins["流场"] = FlowField
    builtins["粒子系统"] = particle_system
    builtins["粒子更新"] = particle_update
    builtins["Barnsley蕨类"] = fractal_barnsley_fern
    builtins["Sierpinski三角形"] = fractal_sierpinski
    builtins["HSL转RGB"] = color_hsl_to_rgb
    builtins["颜色插值"] = color_lerp
    builtins["音频反应式"] = audio_reactive
    builtins["MIDI可视化"] = visual_midi


def _creative_coding_symtab_names() -> list[str]:
    return ["Perlin噪声2D", "Simplex噪声2D", "流场", "粒子系统",
            "粒子更新", "Barnsley蕨类", "Sierpinski三角形",
            "HSL转RGB", "颜色插值", "音频反应式", "MIDI可视化"]
