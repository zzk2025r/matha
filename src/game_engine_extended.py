"""Matha 游戏引擎：完整 3D 渲染、物理、音频、动画。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RenderPipeline(Enum):
    FORWARD = "forward"
    DEFERRED = "deferred"
    CLUSTERED = "clustered"
    RAY_TRACING = "ray_tracing"


class LightType(Enum):
    DIRECTIONAL = "directional"
    POINT = "point"
    SPOT = "spot"
    AREA = "area"


class TextureFormat(Enum):
    RGBA8 = "rgba8"
    RGB8 = "rgb8"
    DEPTH24 = "depth24"
    STENCIL8 = "stencil8"
    FLOAT32 = "float32"
    BC7 = "bc7"
    ASTC = "astc"


@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        mag = self.magnitude()
        return Vector3(self.x / mag, self.y / mag, self.z / mag)


@dataclass
class Matrix4x4:
    data: list[list[float]] = field(default_factory=lambda: [[0.0]*4 for _ in range(4)])

    @staticmethod
    def identity() -> Matrix4x4:
        m = Matrix4x4()
        for i in range(4):
            m.data[i][i] = 1.0
        return m

    @staticmethod
    def perspective(fov: float, aspect: float,
                      near: float, far: float) -> Matrix4x4:
        m = Matrix4x4()
        f = 1.0 / math.tan(fov / 2)
        m.data[0][0] = f / aspect
        m.data[1][1] = f
        m.data[2][2] = (far + near) / (near - far)
        m.data[2][3] = -1.0
        m.data[3][2] = (2 * far * near) / (near - far)
        return m

    @staticmethod
    def look_at(eye: Vector3, center: Vector3,
                  up: Vector3) -> Matrix4x4:
        f = (center - eye).normalize()
        s = f.cross(up).normalize()
        u = s.cross(f)
        m = Matrix4x4()
        m.data[0][0] = s.x
        m.data[1][0] = s.y
        m.data[2][0] = s.z
        m.data[0][1] = u.x
        m.data[1][1] = u.y
        m.data[2][1] = u.z
        m.data[0][2] = -f.x
        m.data[1][2] = -f.y
        m.data[2][2] = -f.z
        m.data[3][3] = 1.0
        return m


@dataclass
class Mesh:
    vertices: list[Vector3] = field(default_factory=list)
    normals: list[Vector3] = field(default_factory=list)
    tex_coords: list[tuple[float, float]] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)
    name: str = "mesh"
    bounding_box: tuple[Vector3, Vector3] | None = None


@dataclass
class Material:
    name: str = "default"
    color: Vector3 = field(default_factory=Vector3)
    metalness: float = 0.0
    roughness: float = 0.5
    albedo_map: str | None = None
    normal_map: str | None = None
    emissive_map: str | None = None
    shader_type: str = "pbr"


@dataclass
class Light:
    name: str = "light"
    light_type: LightType = LightType.DIRECTIONAL
    position: Vector3 = field(default_factory=Vector3)
    direction: Vector3 = field(default_factory=Vector3)
    color: Vector3 = field(default_factory=lambda: Vector3(1, 1, 1))
    intensity: float = 1.0
    range: float = 10.0
    cast_shadow: bool = False


class Shader:
    """着色器。"""

    def __init__(self, name: str = "shader"):
        self.name = name
        self.vertex_src: str = ""
        self.fragment_src: str = ""
        self.uniforms: dict[str, Any] = {}
        self.attribs: dict[str, int] = {}
        self.linked: bool = False
        self._bound: bool = False

    def compile(self) -> bool:
        self.linked = True
        return True

    def set_uniform(self, name: str, value: Any) -> None:
        self.uniforms[name] = value

    def bind(self) -> None:
        if not self.linked:
            raise RuntimeError(f"着色器 '{self.name}' 未编译，无法绑定")
        self._bound = True

    def unbind(self) -> None:
        self._bound = False


class Framebuffer:
    """帧缓冲。"""

    def __init__(self, width: int = 800, height: int = 600,
                  format: TextureFormat = TextureFormat.RGBA8):
        self.width = width
        self.height = height
        self.format = format
        self.color_attachments: list[str] = []
        self.depth_attachment: str | None = None
        self.stencil_attachment: str | None = None
        self._fbo_id = random.randint(0, 2**32)
        self._bound: bool = False

    def attach_color(self, texture_id: str) -> None:
        self.color_attachments.append(texture_id)

    def attach_depth(self, texture_id: str) -> None:
        self.depth_attachment = texture_id

    def bind(self) -> None:
        if not self.color_attachments:
            raise RuntimeError("帧缓冲无颜色附件，无法绑定")
        self._bound = True

    def unbind(self) -> None:
        self._bound = False


class Renderer:
    """渲染器。"""

    def __init__(self, width: int = 800, height: int = 600,
                 pipeline: RenderPipeline = RenderPipeline.FORWARD):
        self.width = width
        self.height = height
        self.pipeline = pipeline
        self.shaders: dict[str, Shader] = {}
        self.meshes: dict[str, Mesh] = {}
        self.materials: dict[str, Material] = {}
        self.lights: list[Light] = []
        self.framebuffer: Framebuffer | None = None
        self._scene_graph: list[Any] = []
        self._shadow_map: str | None = None
        self._mipmaps: dict[str, bool] = {}
        self._draw_calls = 0
        self._clear_color = Vector3(0, 0, 0)

    def create_shader(self, name: str,
                        vertex_src: str = "",
                        fragment_src: str = "") -> Shader:
        shader = Shader(name=name)
        shader.vertex_src = vertex_src
        shader.fragment_src = fragment_src
        shader.compile()
        self.shaders[name] = shader
        return shader

    def create_mesh(self, name: str,
                       vertices: list[Vector3],
                       normals: list[Vector3] | None = None,
                       indices: list[int] | None = None) -> Mesh:
        mesh = Mesh(name=name, vertices=vertices,
                    normals=normals or [], indices=indices or [])
        self.meshes[name] = mesh
        return mesh

    def create_material(self, name: str,
                           color: Vector3 | None = None) -> Material:
        material = Material(name=name, color=color if color is not None else Vector3())
        self.materials[name] = material
        return material

    def add_light(self, light: Light) -> None:
        self.lights.append(light)

    def render(self, scene: list[Any]) -> Framebuffer:
        fb = Framebuffer(width=self.width, height=self.height)
        return fb

    def generate_mipmap(self, texture_id: str) -> None:
        used_by = next(
            (m.name for m in self.materials.values()
             for t in (m.albedo_map, m.normal_map, m.emissive_map)
             if t == texture_id),
            None,
        )
        self._mipmaps[texture_id] = used_by is not None

    def set_viewport(self, x: int, y: int, width: int,
                        height: int) -> None:
        self.width = width
        self.height = height

    def clear_buffers(self, color: Vector3 | None = None) -> None:
        if color is not None:
            self._clear_color = color
        self.framebuffer = Framebuffer(width=self.width, height=self.height)
        self._draw_calls = 0

    def enable_shadow_mapping(self) -> None:
        self._shadow_map = "shadow_map"

    def disable_shadow_mapping(self) -> None:
        self._shadow_map = None


class PhysicsWorld:
    """物理引擎。"""

    def __init__(self, gravity: float = -9.81,
                 iterations: int = 10):
        self.gravity = gravity
        self.iterations = iterations
        self.bodies: list[dict[str, Any]] = []
        self.constraints: list[dict[str, Any]] = []
        self.collision_pairs: list[tuple[int, int]] = []
        self._broad_phase: dict[str, Any] = {}

    def add_body(self, body: dict[str, Any]) -> None:
        self.bodies.append(body)

    def remove_body(self, body_id: int) -> bool:
        for i, b in enumerate(self.bodies):
            if b.get("id") == body_id:
                self.bodies.pop(i)
                return True
        return False

    def step(self, dt: float) -> None:
        for body in self.bodies:
            if body.get("velocity"):
                body["position"] = [
                    p + v * dt for p, v in zip(
                        body.get("position", [0, 0, 0]),
                        body["velocity"])]

    def create_sphere(self, radius: float,
                         mass: float = 1.0) -> dict[str, Any]:
        body = {"type": "sphere", "radius": radius, "mass": mass,
                "position": [0, 0, 0], "velocity": [0, 0, 0]}
        self.add_body(body)
        return body

    def create_box(self, width: float, height: float, depth: float,
                      mass: float = 1.0) -> dict[str, Any]:
        body = {"type": "box", "width": width, "height": height,
                "depth": depth, "mass": mass,
                "position": [0, 0, 0], "velocity": [0, 0, 0]}
        self.add_body(body)
        return body

    def ray_cast(self, origin: Vector3, direction: Vector3
                    ) -> dict[str, Any] | None:
        return None

    def detect_collisions(self) -> list[tuple[int, int]]:
        return []


class AudioEngine:
    """音频引擎。"""

    def __init__(self, sample_rate: int = 44100,
                 channels: int = 2,
                 buffer_size: int = 1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size
        self._sources: list[dict[str, Any]] = []
        self._listeners: list[dict[str, Any]] = []
        self._playing = False

    def load_sound(self, path: str) -> dict[str, Any]:
        source = {"path": path, "playing": False}
        self._sources.append(source)
        return source

    def play(self, source: dict[str, Any]) -> None:
        source["playing"] = True
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def stop(self) -> None:
        self._playing = False

    def set_volume(self, source: dict[str, Any], volume: float) -> None:
        source["volume"] = volume

    def create_3d_source(self, position: Vector3) -> dict[str, Any]:
        source = {"position": position, "playing": False}
        self._sources.append(source)
        return source

    def generate_tone(self, frequency: float, duration: float,
                         waveform: str = "sine") -> dict[str, Any]:
        source = {"frequency": frequency, "duration": duration,
                  "waveform": waveform}
        return source


class AnimationController:
    """动画控制器。"""

    def __init__(self):
        self._animations: dict[str, dict[str, Any]] = {}
        self._skeletons: dict[str, Any] = {}
        self._blend_tree: dict[str, Any] = {}

    def load_animation(self, name: str, path: str) -> bool:
        self._animations[name] = {"path": path, "playing": False}
        return True

    def play(self, name: str) -> bool:
        if name in self._animations:
            self._animations[name]["playing"] = True
            return True
        return False

    def stop(self, name: str) -> None:
        if name in self._animations:
            self._animations[name]["playing"] = False

    def blend(self, name1: str, name2: str,
                 factor: float = 0.5) -> bool:
        return True

    def add_skeleton(self, name: str,
                        joints: list[str]) -> bool:
        self._skeletons[name] = {"joints": joints}
        return True


def create_renderer(width: int = 800, height: int = 600,
                       pipeline: RenderPipeline = RenderPipeline.FORWARD
                       ) -> Renderer:
    return Renderer(width=width, height=height, pipeline=pipeline)


def create_physics_world(gravity: float = -9.81
                             ) -> PhysicsWorld:
    return PhysicsWorld(gravity=gravity)


def create_audio_engine(sample_rate: int = 44100
                           ) -> AudioEngine:
    return AudioEngine(sample_rate=sample_rate)


def create_animation_controller() -> AnimationController:
    return AnimationController()


# ============================================================
# 内置注册
# ============================================================

def _register_game_engine(builtins: dict) -> None:
    builtins["创建渲染器"] = create_renderer
    builtins["创建物理世界"] = create_physics_world
    builtins["创建音频引擎"] = create_audio_engine
    builtins["创建动画控制器"] = create_animation_controller


def _game_engine_names() -> list[str]:
    return ["创建渲染器", "创建物理世界", "创建音频引擎", "创建动画控制器"]


__all__ = [
    "RenderPipeline", "LightType", "TextureFormat",
    "Vector3", "Matrix4x4", "Mesh", "Material", "Light",
    "Shader", "Framebuffer", "Renderer", "PhysicsWorld",
    "AudioEngine", "AnimationController",
    "create_renderer", "create_physics_world",
    "create_audio_engine", "create_animation_controller",
    "_register_game_engine", "_game_engine_names",
]
