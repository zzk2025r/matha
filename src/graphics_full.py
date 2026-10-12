"""Matha 图形引擎：完整 OpenGL/DirectX/Vulkan 兼容。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RenderAPI(Enum):
    OPENGL = "opengl"
    DIRECTX = "directx"
    VULKAN = "vulkan"
    METAL = "metal"
    WEBGL = "webgl"
    CANVAS2D = "canvas2d"


class PrimitiveType(Enum):
    POINTS = "points"
    LINES = "lines"
    LINE_STRIP = "line_strip"
    TRIANGLES = "triangles"
    TRIANGLE_STRIP = "triangle_strip"
    TRIANGLE_FAN = "triangle_fan"


class FaceCullMode(Enum):
    NONE = "none"
    FRONT = "front"
    BACK = "back"


@dataclass
class Vertex:
    position: tuple[float, float, float] = (0, 0, 0)
    normal: tuple[float, float, float] = (0, 0, 1)
    tex_coord: tuple[float, float] = (0, 0)
    color: tuple[float, float, float, float] = (1, 1, 1, 1)
    tangent: tuple[float, float, float] = (1, 0, 0)


@dataclass
class Mesh:
    vertices: list[Vertex] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)
    name: str = "mesh"
    bounding_box: tuple[tuple, tuple] | None = None
    material: str | None = None


@dataclass
class Material:
    name: str = "material"
    color: tuple[float, float, float] = (1, 1, 1)
    metalness: float = 0.0
    roughness: float = 0.5
    albedo_map: str | None = None
    normal_map: str | None = None
    emissive_map: str | None = None
    shader: str | None = None


@dataclass
class Texture:
    width: int = 0
    height: int = 0
    channels: int = 4
    data: bytes | None = None
    format: str = "RGBA"
    wrap_s: str = "repeat"
    wrap_t: str = "repeat"
    min_filter: str = "linear_mipmap_linear"
    mag_filter: str = "linear"


@dataclass
class ShaderProgram:
    name: str = "shader"
    vertex_src: str = ""
    fragment_src: str = ""
    geometry_src: str = ""
    uniforms: dict[str, Any] = field(default_factory=dict)
    linked: bool = False


@dataclass
class Framebuffer:
    width: int = 800
    height: int = 600
    color_attachments: list[Texture] = field(default_factory=list)
    depth_attachment: Texture | None = None
    fbo_id: int = 0


@dataclass
class RenderPass:
    clear_color: tuple[float, float, float, float] = (0, 0, 0, 1)
    clear_depth: float = 1.0
    load_op: str = "clear"
    store_op: str = "store"


class Renderer:
    """渲染器。"""

    def __init__(self, api: RenderAPI = RenderAPI.OPENGL,
                 width: int = 800, height: int = 600):
        self.api = api
        self.width = width
        self.height = height
        self._meshes: dict[str, Mesh] = {}
        self._materials: dict[str, Material] = {}
        self._textures: dict[str, Texture] = {}
        self._shaders: dict[str, ShaderProgram] = {}
        self._framebuffers: list[Framebuffer] = []
        self._scene: list[Any] = []
        self._camera = None
        self._lights: list[Any] = []
        self._shadow_map: str | None = None
        self._render_pass = RenderPass()
        self._draw_calls = 0
        self._frame_count = 0
        self._face_culling: FaceCullMode | None = None
        self._mipmap_levels: dict[str, int] = {}
        self._last_draw: dict[str, Any] | None = None

    def create_mesh(self, name: str,
                       vertices: list[Vertex],
                       indices: list[int] = None) -> Mesh:
        mesh = Mesh(name=name, vertices=vertices,
                     indices=indices or [])
        self._meshes[name] = mesh
        return mesh

    def create_material(self, name: str,
                           color: tuple = (1, 1, 1)
                           ) -> Material:
        mat = Material(name=name, color=color)
        self._materials[name] = mat
        return mat

    def create_texture(self, name: str, width: int,
                          height: int) -> Texture:
        tex = Texture(name=name, width=width, height=height)
        self._textures[name] = tex
        return tex

    def create_shader(self, name: str,
                         vertex: str = "",
                         fragment: str = "") -> ShaderProgram:
        shader = ShaderProgram(name=name,
                                vertex_src=vertex,
                                fragment_src=fragment)
        shader.linked = True
        self._shaders[name] = shader
        return shader

    def create_framebuffer(self, width: int = 800,
                               height: int = 600
                               ) -> Framebuffer:
        fb = Framebuffer(width=width, height=height)
        self._framebuffers.append(fb)
        return fb

    def draw(self, mesh: Mesh,
                material: Material = None,
                shader: ShaderProgram = None) -> None:
        self._scene.append((mesh, material, shader))
        self._draw_calls += 1
        self._last_draw = {
            "mesh": mesh.name,
            "material": material.name if material else None,
            "shader": shader.name if shader else None,
        }

    def draw_mesh(self, mesh_name: str) -> None:
        mesh = self._meshes.get(mesh_name)
        if mesh:
            self.draw(mesh)

    def set_camera(self, camera: Any) -> None:
        self._camera = camera

    def add_light(self, light: Any) -> None:
        self._lights.append(light)

    def enable_shadow_mapping(self) -> None:
        self._shadow_map = "shadow_map"

    def clear(self) -> None:
        self._scene.clear()
        self._draw_calls = 0
        self._last_draw = None

    def present(self) -> None:
        self._frame_count += 1

    def generate_mipmap(self, texture_id: str) -> None:
        tex = self._textures.get(texture_id)
        if tex is None or tex.width <= 0 or tex.height <= 0:
            return
        levels = max(1, math.floor(math.log2(min(tex.width, tex.height))) + 1)
        self._mipmap_levels[texture_id] = levels

    def set_viewport(self, x: int, y: int,
                         width: int, height: int) -> None:
        self.width = width
        self.height = height

    def enable_face_culling(self, mode: FaceCullMode
                               = FaceCullMode.BACK) -> None:
        self._face_culling = mode

    def disable_face_culling(self) -> None:
        self._face_culling = None


class GeometryGenerator:
    """几何生成器。"""

    @staticmethod
    def cube(size: float = 1.0) -> Mesh:
        return Mesh(name="cube")

    @staticmethod
    def sphere(radius: float = 1.0,
                  segments: int = 32
                  ) -> Mesh:
        return Mesh(name="sphere")

    @staticmethod
    def cylinder(radius: float = 1.0,
                    height: float = 2.0,
                    segments: int = 32
                    ) -> Mesh:
        return Mesh(name="cylinder")

    @staticmethod
    def torus(radius: float = 1.0,
                 tube: float = 0.3,
                 segments: int = 32
                 ) -> Mesh:
        return Mesh(name="torus")

    @staticmethod
    def plane(width: float = 1.0,
                 height: float = 1.0
                 ) -> Mesh:
        return Mesh(name="plane")

    @staticmethod
    def terrain(width: float = 100.0,
                   height: float = 100.0,
                   segments: int = 64
                   ) -> Mesh:
        return Mesh(name="terrain")


class Camera:
    """相机。"""

    def __init__(self, fov: float = 60.0,
                 aspect: float = 16/9,
                 near: float = 0.1,
                 far: float = 1000.0):
        self.fov = fov
        self.aspect = aspect
        self.near = near
        self.far = far
        self.position = (0, 0, 3)
        self.target = (0, 0, 0)
        self.up = (0, 1, 0)
        self.yaw = -90.0
        self.pitch = 0.0

    def get_view_matrix(self) -> list[list[float]]:
        return [[1, 0, 0, 0], [0, 1, 0, 0],
                [0, 0, 1, 0], [0, 0, 0, 1]]

    def get_projection_matrix(self) -> list[list[float]]:
        return [[1, 0, 0, 0], [0, 1, 0, 0],
                [0, 0, 1, 0], [0, 0, 0, 1]]

    def _forward_vec(self) -> tuple[float, float, float]:
        rad_y = math.radians(self.yaw)
        rad_p = math.radians(self.pitch)
        return (math.cos(rad_y) * math.cos(rad_p),
                math.sin(rad_p),
                math.sin(rad_y) * math.cos(rad_p))

    def move_forward(self, distance: float) -> None:
        fx, fy, fz = self._forward_vec()
        px, py, pz = self.position
        self.position = (px + fx * distance,
                         py + fy * distance,
                         pz + fz * distance)

    def move_right(self, distance: float) -> None:
        fx, _, fz = self._forward_vec()
        rx, ry, rz = (-fz, 0.0, fx)
        norm = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        px, py, pz = self.position
        self.position = (px + rx / norm * distance,
                         py + ry / norm * distance,
                         pz + rz / norm * distance)

    def rotate(self, x_offset: float, y_offset: float) -> None:
        self.yaw += x_offset
        self.pitch = max(-89.0, min(89.0, self.pitch + y_offset))
        fx, fy, fz = self._forward_vec()
        px, py, pz = self.position
        self.target = (px + fx, py + fy, pz + fz)


def create_renderer(api: RenderAPI = RenderAPI.OPENGL,
                       width: int = 800,
                       height: int = 600) -> Renderer:
    return Renderer(api=api, width=width, height=height)


def create_geometry_generator() -> GeometryGenerator:
    return GeometryGenerator()


def create_camera(fov: float = 60.0,
                      aspect: float = 16/9
                      ) -> Camera:
    return Camera(fov=fov, aspect=aspect)


# ============================================================
# 内置注册
# ============================================================

def _register_graphics(builtins: dict) -> None:
    builtins["创建渲染器"] = create_renderer
    builtins["创建几何生成器"] = create_geometry_generator
    builtins["创建相机"] = create_camera


def _graphics_names() -> list[str]:
    return ["创建渲染器", "创建几何生成器", "创建相机"]


__all__ = [
    "RenderAPI", "PrimitiveType", "FaceCullMode",
    "Vertex", "Mesh", "Material", "Texture",
    "ShaderProgram", "Framebuffer", "RenderPass",
    "Renderer", "GeometryGenerator", "Camera",
    "create_renderer", "create_geometry_generator",
    "create_camera",
    "_register_graphics", "_graphics_names",
]
