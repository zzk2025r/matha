# -*- coding: utf-8 -*-
"""
Matha 混沌理论与分型领域模块。

覆盖：
  1) Lorenz 吸引子
  2) Hénon 映射
  3) Logistic 映射
  4) Mandelbrot / Julia 集
  5) 分形维数
  6) Lyapunov 指数
"""
from __future__ import annotations
import math
from typing import Optional


# ============================================================
# Lorenz 吸引子
# ============================================================

def lorenz_deriv(x: float, y: float, z: float,
                  sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0/3.0) -> tuple[float, float, float]:
    """Lorenz 方程导数。"""
    dx = sigma * (y - x)
    dy = x * (rho - z) - y
    dz = x * y - beta * z
    return dx, dy, dz


def lorenz_attractor(x0: float = 0.1, y0: float = 1.0, z0: float = 1.0,
                     dt: float = 0.01, steps: int = 10000,
                     sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0/3.0) -> list[tuple[float, float, float]]:
    """计算 Lorenz 吸引子轨迹。"""
    points = [(x0, y0, z0)]
    x, y, z = x0, y0, z0
    for _ in range(steps):
        dx, dy, dz = lorenz_deriv(x, y, z, sigma, rho, beta)
        x += dx * dt
        y += dy * dt
        z += dz * dt
        points.append((x, y, z))
    return points


# ============================================================
# Hénon 映射
# ============================================================

def henon_map(x: float, y: float, a: float = 1.4, b: float = 0.3) -> tuple[float, float]:
    """Hénon 映射。"""
    x_new = 1.0 - a * x * x + y
    y_new = b * x
    return x_new, y_new


def henon_attractor(x0: float = 0.0, y0: float = 0.0,
                    a: float = 1.4, b: float = 0.3, steps: int = 10000) -> list[tuple[float, float]]:
    """Hénon 吸引子轨迹。"""
    points = []
    x, y = x0, y0
    for _ in range(steps):
        x, y = henon_map(x, y, a, b)
        points.append((x, y))
    return points


# ============================================================
# Logistic 映射
# ============================================================

def logistic_map(x: float, r: float = 3.5) -> float:
    """Logistic 映射：x_{n+1} = r * x_n * (1 - x_n)。"""
    return r * x * (1.0 - x)


def logistic_orbit(x0: float = 0.5, r: float = 3.5, steps: int = 100) -> list[float]:
    """Logistic 映射轨道。"""
    orbit = [x0]
    x = x0
    for _ in range(steps):
        x = logistic_map(x, r)
        orbit.append(x)
    return orbit


# ============================================================
# Mandelbrot 集
# ============================================================

def mandelbrot_iter(cx: float, cy: float, max_iter: int = 100) -> int:
    """Mandelbrot 迭代。"""
    x, y = 0.0, 0.0
    for i in range(max_iter):
        x_new = x * x - y * y + cx
        y_new = 2.0 * x * y + cy
        if x_new * x_new + y_new * y_new > 4.0:
            return i
        x, y = x_new, y_new
    return max_iter


def mandelbrot_set(width: int = 800, height: int = 600,
                   x_min: float = -2.5, x_max: float = 1.5,
                   y_min: float = -1.5, y_max: float = 1.5,
                   max_iter: int = 100) -> list[list[int]]:
    """生成 Mandelbrot 集图像数据。"""
    image = []
    for py in range(height):
        row = []
        for px in range(width):
            cx = x_min + (x_max - x_min) * px / width
            cy = y_min + (y_max - y_min) * py / height
            row.append(mandelbrot_iter(cx, cy, max_iter))
        image.append(row)
    return image


# ============================================================
# Julia 集
# ============================================================

def julia_iter(cx: float, cy: float, px: float, py: float, max_iter: int = 100) -> int:
    """Julia 集迭代。"""
    x, y = px, py
    for i in range(max_iter):
        x_new = x * x - y * y + cx
        y_new = 2.0 * x * y + cy
        if x_new * x_new + y_new * y_new > 4.0:
            return i
        x, y = x_new, y_new
    return max_iter


def julia_set(width: int = 800, height: int = 600,
              cx: float = -0.8, cy: float = 0.156,
              max_iter: int = 100) -> list[list[int]]:
    """生成 Julia 集图像数据。"""
    image = []
    for py in range(height):
        row = []
        for px in range(width):
            x = -2.0 + 4.0 * px / width
            y = -1.5 + 3.0 * py / height
            row.append(julia_iter(cx, cy, x, y, max_iter))
        image.append(row)
    return image


# ============================================================
# 分形维数
# ============================================================

def box_counting_dim(points: list[tuple[float, float]], min_scale: float = 0.01, max_scale: float = 1.0) -> float:
    """盒子计数法估算分形维数。"""
    scales = []
    counts = []
    scale = max_scale
    while scale >= min_scale:
        count = 0
        grid_size = scale
        seen = set()
        for x, y in points:
            gx = int(x / grid_size)
            gy = int(y / grid_size)
            key = (gx, gy)
            if key not in seen:
                seen.add(key)
                count += 1
        scales.append(math.log(scale))
        counts.append(math.log(count))
        scale /= 2
    if len(scales) < 2:
        return 1.0
    # 线性回归求斜率
    n = len(scales)
    sum_x = sum(scales)
    sum_y = sum(counts)
    sum_xy = sum(s * c for s, c in zip(scales, counts))
    sum_x2 = sum(s * s for s in scales)
    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 1.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    return -slope  # 负斜率即维数


# ============================================================
# Lyapunov 指数
# ============================================================

def lyapunov_exponent(logistic_r: float, x0: float = 0.5, steps: int = 10000) -> float:
    """计算 Logistic 映射的 Lyapunov 指数。"""
    x = x0
    sum_log = 0.0
    for _ in range(steps):
        fx = logistic_r * (1.0 - 2.0 * x)  # 导数
        if fx == 0:
            x = logistic_map(x, logistic_r)
            continue
        sum_log += math.log(abs(fx))
        x = logistic_map(x, logistic_r)
    return sum_log / steps


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # Lorenz
    "lorenz_deriv", "lorenz_attractor",
    # Hénon
    "henon_map", "henon_attractor",
    # Logistic
    "logistic_map", "logistic_orbit",
    # Mandelbrot
    "mandelbrot_iter", "mandelbrot_set",
    # Julia
    "julia_iter", "julia_set",
    # 分形
    "box_counting_dim",
    # Lyapunov
    "lyapunov_exponent",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_chaos_fractal(builtins: dict) -> None:
    """注册混沌理论与分型内建到解释器。"""
    builtins["Lorenz导数"] = lorenz_deriv
    builtins["Lorenz吸引子"] = lorenz_attractor
    builtins["Henon映射"] = henon_map
    builtins["Henon吸引子"] = henon_attractor
    builtins["Logistic映射"] = logistic_map
    builtins["Logistic轨道"] = logistic_orbit
    builtins["Mandelbrot迭代"] = mandelbrot_iter
    builtins["Mandelbrot集"] = mandelbrot_set
    builtins["Julia迭代"] = julia_iter
    builtins["Julia集"] = julia_set
    builtins["分形维数"] = box_counting_dim
    builtins["Lyapunov指数"] = lyapunov_exponent


def _chaos_fractal_symtab_names() -> list[str]:
    return ["Lorenz导数", "Lorenz吸引子", "Henon映射", "Henon吸引子",
            "Logistic映射", "Logistic轨道", "Mandelbrot迭代", "Mandelbrot集",
            "Julia迭代", "Julia集", "分形维数", "Lyapunov指数"]
