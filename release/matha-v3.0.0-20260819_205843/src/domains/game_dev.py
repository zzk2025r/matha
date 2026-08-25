# -*- coding: utf-8 -*-
"""
Matha 游戏开发领域模块。

覆盖：
  1) 游戏循环控制
  2) 精灵管理（创建、移动、碰撞）
  3) 粒子系统
  4) 物理引擎（重力、力）
  5) 音频控制
  6) 输入处理
  7) 渲染（2D/3D 投影）
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 游戏状态
# ============================================================

@dataclass
class GameConfig:
    """游戏配置。"""
    width: int = 800
    height: int = 600
    fps: int = 60
    gravity: float = 9.81
    title: str = "Matha Game"


@dataclass
class Sprite:
    """游戏精灵。"""
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    width: float = 32.0
    height: float = 32.0
    active: bool = True


@dataclass
class Particle:
    """粒子。"""
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    life: float = 1.0
    max_life: float = 1.0
    color: tuple = (1.0, 1.0, 1.0)


# ============================================================
# 游戏循环
# ============================================================

def game_loop(dt: float, update_fn, render_fn) -> None:
    """游戏主循环（抽象接口）。"""
    # 抽象：实际由代码生成器实现
    pass


# ============================================================
# 精灵管理
# ============================================================

def sprite_create(x: float = 0.0, y: float = 0.0, w: float = 32.0, h: float = 32.0) -> dict:
    """创建精灵。"""
    return {"x": x, "y": y, "vx": 0.0, "vy": 0.0, "w": w, "h": h, "active": True}


def sprite_move(sprite: dict, dx: float, dy: float) -> dict:
    """移动精灵。"""
    sprite["x"] += dx
    sprite["y"] += dy
    return sprite


def sprite_apply_force(sprite: dict, fx: float, fy: float, mass: float = 1.0) -> dict:
    """对精灵施加力。"""
    sprite["vx"] += fx / mass
    sprite["vy"] += fy / mass
    return sprite


def sprite_collide(a: dict, b: dict) -> bool:
    """AABB 碰撞检测。"""
    return (abs(a["x"] - b["x"]) < (a["w"] + b["w"]) / 2 and
            abs(a["y"] - b["y"]) < (a["h"] + b["h"]) / 2)


def sprite_bounce(sprite: dict, width: float, height: float) -> dict:
    """边界反弹。"""
    if sprite["x"] < 0 or sprite["x"] > width:
        sprite["vx"] = -sprite["vx"]
    if sprite["y"] < 0 or sprite["y"] > height:
        sprite["vy"] = -sprite["vy"]
    return sprite


# ============================================================
# 粒子系统
# ============================================================

def particle_emitter(x: float, y: float, count: int = 10, speed: float = 100.0) -> list[dict]:
    """粒子发射器。"""
    particles = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        particles.append({
            "x": x, "y": y,
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": 1.0, "max_life": 1.0,
        })
    return particles


def particle_update(particles: list[dict], dt: float, gravity: float = 0.0) -> list[dict]:
    """更新粒子。"""
    result = []
    for p in particles:
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["vy"] += gravity * dt
        p["life"] -= dt
        if p["life"] > 0:
            result.append(p)
    return result


# ============================================================
# 物理引擎
# ============================================================

def physics_gravity(obj: dict, g: float = 9.81, dt: float = 1/60) -> dict:
    """应用重力。"""
    obj["vy"] += g * dt
    return obj


def physics_apply_force(obj: dict, fx: float, fy: float, mass: float = 1.0, dt: float = 1/60) -> dict:
    """施加力。"""
    obj["vx"] += fx / mass * dt
    obj["vy"] += fy / mass * dt
    return obj


def physics_solve_collision(a: dict, b: dict) -> tuple[dict, dict]:
    """弹性碰撞求解。"""
    # 简化为一维弹性碰撞
    va, vb = a.get("vx", 0), b.get("vx", 0)
    ma, mb = a.get("mass", 1), b.get("mass", 1)
    new_va = (va * (ma - mb) + 2 * mb * vb) / (ma + mb)
    new_vb = (vb * (mb - ma) + 2 * ma * va) / (ma + mb)
    a["vx"] = new_va
    b["vx"] = new_vb
    return a, b


# ============================================================
# 音频控制
# ============================================================

def audio_play(freq: float, duration: float = 0.5, volume: float = 0.5) -> dict:
    """播放音频（模拟）。"""
    return {"frequency": freq, "duration": duration, "volume": volume, "playing": True}


def audio_stop() -> None:
    """停止音频（模拟）。"""
    pass


def audio_volume(vol: float) -> None:
    """设置音量。"""
    pass


# ============================================================
# 输入处理
# ============================================================

def input_key(key: str) -> bool:
    """检测按键（模拟）。"""
    return False


def input_mouse() -> tuple[float, float]:
    """获取鼠标位置（模拟）。"""
    return (0.0, 0.0)


def input_gamepad(axis: str) -> float:
    """获取游戏杆输入（模拟）。"""
    return 0.0


# ============================================================
# 渲染
# ============================================================

def render_2d(sprite: dict, screen_x: float, screen_y: float) -> dict:
    """2D 渲染变换。"""
    return {**sprite, "screen_x": screen_x, "screen_y": screen_y}


def render_3d(point: tuple, camera_pos: tuple, target: tuple) -> tuple[float, float]:
    """3D 到 2D 投影。"""
    # 简化透视投影
    dx, dy, dz = point[0] - camera_pos[0], point[1] - camera_pos[1], point[2] - camera_pos[2]
    if dz == 0:
        return (0.0, 0.0)
    fov = 60.0 * math.pi / 180.0
    scale = 1.0 / math.tan(fov / 2)
    return (dx / dz * scale, dy / dz * scale)


def camera_look_at(eye: tuple, center: tuple, up: tuple = (0, 1, 0)) -> list[list[float]]:
    """生成视图矩阵。"""
    # 简化：返回 LookAt 矩阵元素
    zx = eye[0] - center[0]
    zy = eye[1] - center[1]
    zz = eye[2] - center[2]
    len_z = math.sqrt(zx**2 + zy**2 + zz**2)
    zx, zy, zz = zx/len_z, zy/len_z, zz/len_z
    xx = up[1]*zz - up[2]*zy
    xy = up[2]*zx - up[0]*zz
    xz = up[0]*zy - up[1]*zx
    len_x = math.sqrt(xx**2 + xy**2 + xz**2)
    xx, xy, xz = xx/len_x, xy/len_x, xz/len_x
    yx = zy*xz - zz*xy
    yy = zz*xx - zx*xz
    yz = zx*xy - zy*xx
    return [
        [xx, xy, xz, -(xx*eye[0]+xy*eye[1]+xz*eye[2])],
        [yx, yy, yz, -(yx*eye[0]+yy*eye[1]+yz*eye[2])],
        [zx, zy, zz, -(zx*eye[0]+zy*eye[1]+zz*eye[2])],
    ]


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 游戏状态
    "GameConfig", "Sprite", "Particle",
    # 游戏循环
    "game_loop",
    # 精灵
    "sprite_create", "sprite_move", "sprite_apply_force", "sprite_collide", "sprite_bounce",
    # 粒子
    "particle_emitter", "particle_update",
    # 物理
    "physics_gravity", "physics_apply_force", "physics_solve_collision",
    # 音频
    "audio_play", "audio_stop", "audio_volume",
    # 输入
    "input_key", "input_mouse", "input_gamepad",
    # 渲染
    "render_2d", "render_3d", "camera_look_at",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_game_dev(builtins: dict) -> None:
    """注册游戏开发内建到解释器。"""
    builtins["sprite_create"] = sprite_create
    builtins["sprite_move"] = sprite_move
    builtins["sprite_apply_force"] = sprite_apply_force
    builtins["sprite_collide"] = sprite_collide
    builtins["sprite_bounce"] = sprite_bounce
    builtins["particle_emitter"] = particle_emitter
    builtins["particle_update"] = particle_update
    builtins["physics_gravity"] = physics_gravity
    builtins["physics_apply_force"] = physics_apply_force
    builtins["physics_solve_collision"] = physics_solve_collision
    builtins["audio_play"] = audio_play
    builtins["audio_stop"] = audio_stop
    builtins["audio_volume"] = audio_volume
    builtins["input_key"] = input_key
    builtins["input_mouse"] = input_mouse
    builtins["render_2d"] = render_2d
    builtins["render_3d"] = render_3d
    builtins["camera_look_at"] = camera_look_at
    builtins["游戏_默认FPS"] = 60
    builtins["游戏_重力"] = 9.81


def _game_dev_symtab_names() -> list[str]:
    return [
        "sprite_create", "sprite_move", "sprite_apply_force", "sprite_collide",
        "sprite_bounce", "particle_emitter", "particle_update",
        "physics_gravity", "physics_apply_force", "physics_solve_collision",
        "audio_play", "audio_stop", "audio_volume",
        "input_key", "input_mouse",
        "render_2d", "render_3d", "camera_look_at",
    ]
