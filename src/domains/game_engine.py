"""Matha 游戏引擎模块：游戏循环、场景管理、实体系统、物理引擎。

覆盖：
  1) 游戏循环与帧率控制
  2) 场景管理（加载/切换/卸载）
  3) 实体组件系统
  4) 物理引擎（碰撞、重力、刚体）
  5) 粒子系统
  6) 音频引擎
  7) 输入系统
  8) 关卡管理
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================
# 游戏状态枚举
# ============================================================

class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


# ============================================================
# 向量与数学
# ============================================================

@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self) -> Vec2:
        l = self.length()
        if l > 0:
            return Vec2(self.x / l, self.y / l)
        return Vec2(0, 0)

    def distance_to(self, other: Vec2) -> float:
        return (self - other).length()

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalize(self) -> Vec3:
        l = self.length()
        if l > 0:
            return Vec3(self.x / l, self.y / l, self.z / l)
        return Vec3(0, 0, 0)


# ============================================================
# 实体与组件
# ============================================================

@dataclass
class Transform:
    """变换组件。"""
    position: Vec2 = field(default_factory=Vec2)
    rotation: float = 0.0
    scale: Vec2 = field(default_factory=lambda: Vec2(1, 1))


@dataclass
class RigidBody:
    """刚体组件。"""
    velocity: Vec2 = field(default_factory=Vec2)
    mass: float = 1.0
    gravity: bool = True
    friction: float = 0.1
    grounded: bool = False


class PhysicsWorld:
    """物理世界：管理刚体、碰撞检测、重力模拟。"""

    def __init__(self, gravity: Vec2 | None = None):
        self.gravity = gravity if gravity is not None else Vec2(0, -9.8)
        self.bodies: list[RigidBody] = []
        self._initialized = False
        self._init_physics()

    def _init_physics(self) -> None:
        """初始化物理世界。"""
        self._initialized = True

    def add_body(self, body: RigidBody) -> None:
        """添加刚体。"""
        self.bodies.append(body)

    def remove_body(self, body: RigidBody) -> None:
        """移除刚体。"""
        if body in self.bodies:
            self.bodies.remove(body)

    def step(self, dt: float) -> None:
        """物理步进。"""
        for body in self.bodies:
            if body.gravity:
                body.velocity.y += self.gravity.y * dt
                body.velocity.x += self.gravity.x * dt
            body.velocity.x *= (1 - body.friction)
            body.velocity.y *= (1 - body.friction)

    def check_collisions(self) -> list[tuple]:
        """检测碰撞。"""
        collisions = []
        for i, a in enumerate(self.bodies):
            for b in self.bodies[i+1:]:
                if physics_check_collision(a, b):
                    collisions.append((a, b))
        return collisions

    def get_stats(self) -> dict:
        """获取物理统计。"""
        return {
            "bodies": len(self.bodies),
            "gravity": {"x": self.gravity.x, "y": self.gravity.y},
            "initialized": self._initialized,
        }


@dataclass
class Collider:
    """碰撞体组件。"""
    width: float = 32.0
    height: float = 32.0
    is_trigger: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class Sprite:
    """精灵组件。"""
    texture: str = ""
    frame: int = 0
    animation_speed: float = 0.1
    visible: bool = True
    color: str = "#ffffff"


@dataclass
class Entity:
    """游戏实体。"""
    name: str = "Entity"
    tag: str = "Untagged"
    active: bool = True
    transform: Transform = field(default_factory=Transform)
    rigidbody: RigidBody | None = None
    collider: Collider | None = None
    sprite: Sprite | None = None
    components: dict[str, Any] = field(default_factory=dict)


# ============================================================
# 场景管理
# ============================================================

class Scene:
    """游戏场景。"""

    def __init__(self, name: str = "Scene"):
        self.name = name
        self.entities: list[Entity] = []
        self.background_color: str = "#000000"
        _gravity: float = 9.81
        self.gravity: float = _gravity

    def add_entity(self, entity: Entity) -> Entity:
        """添加实体。"""
        self.entities.append(entity)
        return entity

    def remove_entity(self, entity: Entity) -> None:
        """移除实体。"""
        if entity in self.entities:
            self.entities.remove(entity)

    def find_by_tag(self, tag: str) -> list[Entity]:
        """按标签查找实体。"""
        return [e for e in self.entities if e.tag == tag]

    def find_by_name(self, name: str) -> Entity | None:
        """按名称查找实体。"""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def update(self, dt: float) -> None:
        """更新场景。"""
        for entity in self.entities:
            if not entity.active:
                continue
            if entity.rigidbody and entity.rigidbody.gravity:
                entity.rigidbody.velocity.y -= self.gravity * dt
            if entity.transform:
                entity.transform.position.x += entity.rigidbody.velocity.x * dt if entity.rigidbody else 0
                entity.transform.position.y += entity.rigidbody.velocity.y * dt if entity.rigidbody else 0

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "name": self.name,
            "entities": len(self.entities),
            "gravity": self.gravity,
            "background": self.background_color,
        }, ensure_ascii=False, indent=2)


# ============================================================
# 游戏引擎核心
# ============================================================

class GameEngine:
    """游戏引擎。"""

    def __init__(self, width: int = 800, height: int = 600, title: str = "Matha Game"):
        self.width = width
        self.height = height
        self.title = title
        self.state = GameState.MENU
        self.fps: float = 60.0
        self.target_fps: float = 60.0
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Scene | None = None
        self._running: bool = False
        self._last_time: float = 0.0
        self._delta_time: float = 0.0
        self._frame_count: int = 0
        self._entities: list[Entity] = []
        self._input_buffer: list[str] = []
        self._physics_enabled: bool = True
        self._gravity: float = 9.81

    def create_scene(self, name: str) -> Scene:
        """创建场景。"""
        scene = Scene(name)
        self.scenes[name] = scene
        if not self.current_scene:
            self.current_scene = scene
        return scene

    def create_entity(self, name: str = "Entity",
                        tag: str = "Untagged") -> Entity:
        """创建实体并添加到场景。"""
        entity = Entity(name=name, tag=tag)
        self.add_entity(entity)
        return entity

    def switch_scene(self, name: str) -> bool:
        """切换场景。"""
        if name in self.scenes:
            self.current_scene = self.scenes[name]
            self.state = GameState.PLAYING
            return True
        return False

    def add_entity(self, entity: Entity) -> None:
        """添加实体到当前场景。"""
        if self.current_scene:
            self.current_scene.add_entity(entity)
        self._entities.append(entity)

    def start(self) -> None:
        """启动游戏循环。"""
        self._running = True
        self.state = GameState.PLAYING
        self._last_time = time.perf_counter()

    def update(self) -> None:
        """更新一帧。"""
        if not self._running:
            return
        current_time = time.perf_counter()
        self._delta_time = current_time - self._last_time
        self._last_time = current_time
        self._frame_count += 1
        if self.current_scene:
            self.current_scene.update(self._delta_time)
        self._process_input()

    def _process_input(self) -> None:
        """处理输入。"""
        self._input_buffer.clear()

    def get_delta_time(self) -> float:
        """获取帧间隔。"""
        return self._delta_time

    def get_fps(self) -> float:
        """获取当前FPS。"""
        if self._delta_time > 0:
            return 1.0 / self._delta_time
        return 0.0

    def is_running(self) -> bool:
        """是否运行中。"""
        return self._running

    def pause(self) -> None:
        """暂停。"""
        self.state = GameState.PAUSED

    def resume(self) -> None:
        """恢复。"""
        self.state = GameState.PLAYING

    def stop(self) -> None:
        """停止。"""
        self._running = False
        self.state = GameState.GAME_OVER

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps({
            "title": self.title,
            "width": self.width, "height": self.height,
            "fps": self.get_fps(),
            "state": self.state.value,
            "scenes": list(self.scenes.keys()),
            "entities": len(self._entities),
            "frame_count": self._frame_count,
        }, ensure_ascii=False, indent=2)


# ============================================================
# 物理引擎
# ============================================================

def physics_check_collision(a: Entity, b: Entity) -> bool:
    """AABB碰撞检测。"""
    if not a.collider or not b.collider:
        return False
    pa = a.transform.position
    pb = b.transform.position
    return (abs(pa.x - pb.x) < (a.collider.width + b.collider.width) / 2 and
            abs(pa.y - pb.y) < (a.collider.height + b.collider.height) / 2)


def physics_apply_force(entity: Entity, fx: float, fy: float) -> None:
    """施加力。"""
    if entity.rigidbody:
        entity.rigidbody.velocity.x += fx / entity.rigidbody.mass
        entity.rigidbody.velocity.y += fy / entity.rigidbody.mass


def physics_gravity_step(entity: Entity, dt: float, g: float = 9.81) -> None:
    """重力步进。"""
    if entity.rigidbody and entity.rigidbody.gravity:
        entity.rigidbody.velocity.y -= g * dt


def physics_solve_collision(a: Entity, b: Entity) -> tuple[Entity, Entity]:
    """弹性碰撞求解。"""
    if not a.rigidbody or not b.rigidbody:
        return a, b
    va, vb = a.rigidbody.velocity, b.rigidbody.velocity
    ma, mb = a.rigidbody.mass, b.rigidbody.mass
    new_va_x = (va.x * (ma - mb) + 2 * mb * vb.x) / (ma + mb)
    new_va_y = (va.y * (ma - mb) + 2 * mb * vb.y) / (ma + mb)
    new_vb_x = (vb.x * (mb - ma) + 2 * ma * va.x) / (ma + mb)
    new_vb_y = (vb.y * (mb - ma) + 2 * ma * va.y) / (ma + mb)
    a.rigidbody.velocity = Vec2(new_va_x, new_va_y)
    b.rigidbody.velocity = Vec2(new_vb_x, new_vb_y)
    return a, b


# ============================================================
# 粒子系统
# ============================================================

@dataclass
class Particle:
    """粒子。"""
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    life: float = 1.0
    max_life: float = 1.0
    size: float = 2.0
    color: str = "#ffffff"


class ParticleSystem:
    """粒子系统。"""

    def __init__(self, max_particles: int = 1000):
        self.particles: list[Particle] = []
        self.max_particles = max_particles
        self.gravity: float = 0.0
        self.emitter_x: float = 0.0
        self.emitter_y: float = 0.0

    def emit(self, count: int, speed: float = 100.0,
             spread: float = math.pi * 2) -> None:
        """发射粒子。"""
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break
            angle = 2.0 * math.pi * len(self.particles) / count
            p = Particle(
                x=self.emitter_x, y=self.emitter_y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=1.0, max_life=1.0,
            )
            self.particles.append(p)

    def update(self, dt: float) -> None:
        """更新粒子。"""
        result = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy -= self.gravity * dt
            p.life -= dt
            if p.life > 0:
                result.append(p)
        self.particles = result

    def get_active_count(self) -> int:
        """活跃粒子数。"""
        return len(self.particles)

    def clear(self) -> None:
        """清除所有粒子。"""
        self.particles.clear()


# ============================================================
# 音频引擎
# ============================================================

@dataclass
class Sound:
    """音频资源。"""
    name: str = ""
    frequency: float = 440.0
    duration: float = 1.0
    volume: float = 0.5
    loop: bool = False
    playing: bool = False


class AudioEngine:
    """音频引擎。"""

    def __init__(self):
        self.sounds: dict[str, Sound] = {}
        self.master_volume: float = 1.0
        self._playing_sounds: list[Sound] = []

    def load(self, name: str, frequency: float = 440.0,
             duration: float = 1.0, volume: float = 0.5) -> Sound:
        """加载音频。"""
        sound = Sound(name=name, frequency=frequency,
                      duration=duration, volume=volume)
        self.sounds[name] = sound
        return sound

    def play(self, name: str) -> bool:
        """播放音频。"""
        sound = self.sounds.get(name)
        if sound:
            sound.playing = True
            self._playing_sounds.append(sound)
            return True
        return False

    def stop(self, name: str = "") -> None:
        """停止播放。"""
        if name:
            sound = self.sounds.get(name)
            if sound:
                sound.playing = False
        else:
            for s in self._playing_sounds:
                s.playing = False
            self._playing_sounds.clear()

    def set_volume(self, name: str, volume: float) -> None:
        """设置音量。"""
        sound = self.sounds.get(name)
        if sound:
            sound.volume = max(0.0, min(1.0, volume))

    def get_active_count(self) -> int:
        """活跃音频数。"""
        return len([s for s in self._playing_sounds if s.playing])


# ============================================================
# 输入系统
# ============================================================

@dataclass
class InputState:
    """输入状态。"""
    keys_down: list[str] = field(default_factory=list)
    mouse_x: float = 0.0
    mouse_y: float = 0.0
    mouse_button: int = 0
    gamepad_axis: dict[str, float] = field(default_factory=dict)


def input_is_key_down(keys: list[str], key: str) -> bool:
    """检测按键是否按下。"""
    return key in keys


def input_get_mouse() -> tuple[float, float]:
    """获取鼠标位置。"""
    return (0.0, 0.0)


def input_get_axis(axis: str) -> float:
    """获取游戏杆轴值。"""
    return 0.0


# ============================================================
# 关卡管理
# ============================================================

@dataclass
class Level:
    """关卡。"""
    name: str = "Level1"
    entities: list[Entity] = field(default_factory=list)
    spawn_points: list[Vec2] = field(default_factory=list)
    music: str = ""
    difficulty: float = 1.0
    completed: bool = False


class LevelManager:
    """关卡管理器。"""

    def __init__(self):
        self.levels: dict[str, Level] = {}
        self.current_level: Level | None = None
        self._level_index: int = 0

    def add_level(self, level: Level) -> None:
        """添加关卡。"""
        self.levels[level.name] = level

    def load_level(self, name: str) -> bool:
        """加载关卡。"""
        if name in self.levels:
            self.current_level = self.levels[name]
            self._level_index += 1
            return True
        return False

    def next_level(self) -> bool:
        """下一关。"""
        keys = list(self.levels.keys())
        if self._level_index < len(keys) - 1:
            self._level_index += 1
            return self.load_level(keys[self._level_index])
        return False

    def previous_level(self) -> bool:
        """上一关。"""
        keys = list(self.levels.keys())
        if self._level_index > 0:
            self._level_index -= 1
            return self.load_level(keys[self._level_index])
        return False


# ============================================================
# 注册
# ============================================================

def _register_game(builtins: dict) -> None:
    builtins["创建游戏引擎"] = lambda w=800, h=600, t="Matha Game": GameEngine(w, h, t)
    builtins["引擎启动"] = lambda engine: engine.start()
    builtins["引擎更新"] = lambda engine: engine.update()
    builtins["引擎暂停"] = lambda engine: engine.pause()
    builtins["引擎恢复"] = lambda engine: engine.resume()
    builtins["引擎停止"] = lambda engine: engine.stop()
    builtins["创建场景"] = lambda engine, n: engine.create_scene(n)
    builtins["切换场景"] = lambda engine, n: engine.switch_scene(n)
    builtins["添加实体"] = lambda engine, e: engine.add_entity(e)
    builtins["创建实体"] = lambda name, tag="": Entity(name=name, tag=tag)
    builtins["添加碰撞体"] = lambda e, w, h, tags=None: setattr(e, 'collider', Collider(width=w, height=h, tags=tags or [])) or e
    builtins["添加刚体"] = lambda e, mass=1.0: setattr(e, 'rigidbody', RigidBody(mass=mass)) or e
    builtins["添加精灵"] = lambda e, tex="": setattr(e, 'sprite', Sprite(texture=tex)) or e
    builtins["物理碰撞检测"] = physics_check_collision
    builtins["物理施加力"] = physics_apply_force
    builtins["物理重力"] = physics_gravity_step
    builtins["物理碰撞解决"] = physics_solve_collision
    builtins["创建粒子系统"] = lambda: ParticleSystem()
    builtins["粒子发射"] = lambda ps, c, s=100.0: ps.emit(c, s)
    builtins["粒子更新"] = lambda ps, dt: ps.update(dt)
    builtins["创建音频"] = lambda engine: AudioEngine()
    builtins["音频加载"] = lambda a, n, f=440.0, d=1.0, v=0.5: a.load(n, f, d, v)
    builtins["音频播放"] = lambda a, n: a.play(n)
    builtins["音频停止"] = lambda a, n="": a.stop(n)
    builtins["创建关卡管理器"] = lambda: LevelManager()
    builtins["加载关卡"] = lambda lm, n: lm.load_level(n)
    builtins["下一关"] = lambda lm: lm.next_level()
    builtins["检测按键"] = input_is_key_down
    builtins["获取鼠标"] = input_get_mouse
    builtins["Vec2"] = Vec2
    builtins["Vec3"] = Vec3
    builtins["创建物理世界"] = lambda g=None: PhysicsWorld(g or Vec2(0, -9.8))
    builtins["物理世界步进"] = lambda w, dt: w.step(dt)


def _game_symtab_names() -> list[str]:
    return [
        "创建游戏引擎", "引擎启动", "引擎更新", "引擎暂停",
        "引擎恢复", "引擎停止", "创建场景", "切换场景",
        "添加实体", "创建实体", "添加碰撞体", "添加刚体", "添加精灵",
        "物理碰撞检测", "物理施加力", "物理重力", "物理碰撞解决",
        "创建粒子系统", "粒子发射", "粒子更新",
        "创建音频", "音频加载", "音频播放", "音频停止",
        "创建关卡管理器", "加载关卡", "下一关",
        "检测按键", "获取鼠标", "Vec2", "Vec3",
        "创建物理世界", "物理世界步进",
    ]


__all__ = [
    "GameState", "Vec2", "Vec3", "Transform", "RigidBody",
    "PhysicsWorld", "Collider", "Sprite", "Entity", "Scene",
    "GameEngine", "Particle", "ParticleSystem", "Sound",
    "AudioEngine", "InputState", "Level", "LevelManager",
    "physics_check_collision", "physics_apply_force",
    "physics_gravity_step", "physics_solve_collision",
    "_register_game", "_game_symtab_names",
]
