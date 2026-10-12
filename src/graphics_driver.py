"""Matha 图形驱动：OpenGL/Vulkan/DirectX 兼容层。"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GLEnum(Enum):
    """OpenGL 枚举。"""
    POINTS = 0x0000
    LINES = 0x0001
    LINE_STRIP = 0x0003
    TRIANGLES = 0x0004
    TRIANGLE_STRIP = 0x0005
    TRIANGLE_FAN = 0x0006
    DEPTH_TEST = 0x0B71
    CULL_FACE = 0x0B44
    BLEND = 0x0BE2
    SRC_ALPHA = 0x0302
    ONE_MINUS_SRC_ALPHA = 0x0303
    ARRAY_BUFFER = 0x8892
    ELEMENT_ARRAY_BUFFER = 0x8893
    STATIC_DRAW = 0x88E4
    DYNAMIC_DRAW = 0x88E8
    FRAGMENT_SHADER = 0x8B30
    VERTEX_SHADER = 0x8B31
    COMPILE_STATUS = 0x8B81
    LINK_STATUS = 0x8B82
    TEXTURE_2D = 0x0DE1
    RGBA = 0x1908
    UNSIGNED_BYTE = 0x1401
    FLOAT = 0x1406
    COLOR_BUFFER_BIT = 0x00004000
    DEPTH_BUFFER_BIT = 0x00000100


class VKEnum(Enum):
    """Vulkan 枚举。"""
    VK_STRUCTURE_TYPE_APPLICATION_INFO = 0
    VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO = 1
    VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU = 2
    VK_FORMAT_R8G8B8A8_UNORM = 37
    VK_FORMAT_B8G8R8A8_UNORM = 44
    VK_IMAGE_LAYOUT_UNDEFINED = 0
    VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL = 2
    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL = 7
    VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT = 0x00000001
    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT = 0x00000080
    VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT = 0x00000010
    VK_QUEUE_FAMILY_IGNORED = -1
    VK_SAMPLE_COUNT_1_BIT = 0x01
    VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT = 0x01


class DXGIFormat(Enum):
    """DXGI 格式。"""
    UNKNOWN = 0
    R32G32B32A32_FLOAT = 2
    R8G8B8A8_UNORM = 28
    B8G8R8A8_UNORM = 87
    D32_FLOAT = 40
    D24_UNORM_S8_UINT = 45
    R16G16B16A16_FLOAT = 10


class BlendState(Enum):
    DISABLED = "disabled"
    ALPHA = "alpha"
    ADDITIVE = "additive"
    MULTIPLY = "multiply"


class PrimitiveTopology(Enum):
    TRIANGLE_LIST = "triangle_list"
    TRIANGLE_STRIP = "triangle_strip"
    LINE_LIST = "line_list"
    POINT_LIST = "point_list"


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: Vec2) -> Vec2:
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: Vec2) -> Vec2:
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self) -> Vec2:
        l = self.length()
        return Vec2(self.x / l, self.y / l) if l else self

    def dot(self, o: Vec2) -> float:
        return self.x * o.x + self.y * o.y

    def rotate(self, angle: float) -> Vec2:
        c, s = math.cos(angle), math.sin(angle)
        return Vec2(self.x * c - self.y * s,
                    self.x * s + self.y * c)

    @property
    def xy(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: Vec3) -> Vec3:
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: Vec3) -> Vec3:
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> Vec3:
        return Vec3(self.x * k, self.y * k, self.z * k)

    def dot(self, o: Vec3) -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: Vec3) -> Vec3:
        return Vec3(self.y * o.z - self.z * o.y,
                    self.z * o.x - self.x * o.z,
                    self.x * o.y - self.y * o.x)

    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def normalize(self) -> Vec3:
        l = self.length()
        return Vec3(self.x / l, self.y / l, self.z / l) if l else self

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class Vec4:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def __add__(self, o: Vec4) -> Vec4:
        return Vec4(self.x + o.x, self.y + o.y,
                    self.z + o.z, self.w + o.w)

    def dot(self, o: Vec4) -> float:
        return (self.x * o.x + self.y * o.y
                + self.z * o.z + self.w * o.w)

    @property
    def xyzw(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.z, self.w)

    def perspective(fov: float, aspect: float,
                    near: float, far: float) -> Vec4:
        f = 1.0 / math.tan(fov / 2)
        return Vec4(f / aspect, f,
                    (far + near) / (near - far),
                    (far * near) / (near - far))


@dataclass
class Mat4:
    """4x4 矩阵（行主序）。"""
    m: list[list[float]] = field(default_factory=lambda:
        [[1.0, 0, 0, 0], [0, 1.0, 0, 0],
         [0, 0, 1.0, 0], [0, 0, 0, 1.0]])

    @staticmethod
    def identity() -> Mat4:
        return Mat4()

    @staticmethod
    def translate(x: float, y: float, z: float) -> Mat4:
        return Mat4([[1, 0, 0, x], [0, 1, 0, y],
                     [0, 0, 1, z], [0, 0, 0, 1]])

    @staticmethod
    def scale(x: float, y: float, z: float) -> Mat4:
        return Mat4([[x, 0, 0, 0], [0, y, 0, 0],
                     [0, 0, z, 0], [0, 0, 0, 1]])

    @staticmethod
    def rotate_x(angle: float) -> Mat4:
        c, s = math.cos(angle), math.sin(angle)
        return Mat4([[1, 0, 0, 0], [0, c, -s, 0],
                     [0, s, c, 0], [0, 0, 0, 1]])

    @staticmethod
    def rotate_y(angle: float) -> Mat4:
        c, s = math.cos(angle), math.sin(angle)
        return Mat4([[c, 0, s, 0], [0, 1, 0, 0],
                     [-s, 0, c, 0], [0, 0, 0, 1]])

    @staticmethod
    def rotate_z(angle: float) -> Mat4:
        c, s = math.cos(angle), math.sin(angle)
        return Mat4([[c, -s, 0, 0], [s, c, 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])

    def multiply(self, o: Mat4) -> Mat4:
        return Mat4([[sum(self.m[r][k] * o.m[k][c]
                          for k in range(4))
                      for c in range(4)]
                     for r in range(4)])

    def transform(self, v: Vec4) -> Vec4:
        return Vec4(*[sum(self.m[r][c] * getattr(v, "xyzw"[c])
                        for c in range(4)) for r in range(4)])

    def transpose(self) -> Mat4:
        return Mat4([[self.m[c][r] for c in range(4)]
                     for r in range(4)])

    def determinant(self) -> float:
        m = self.m
        return (m[0][0] * (m[1][1] * (m[2][2] * m[3][3]
                                       - m[2][3] * m[3][2])
                           - m[1][2] * (m[2][1] * m[3][3]
                                        - m[2][3] * m[3][1])
                           + m[1][3] * (m[2][1] * m[3][2]
                                        - m[2][2] * m[3][1]))
                - m[0][1] * (m[1][0] * (m[2][2] * m[3][3]
                                        - m[2][3] * m[3][2])
                             - m[1][2] * (m[2][0] * m[3][3]
                                          - m[2][3] * m[3][0])
                             + m[1][3] * (m[2][0] * m[3][2]
                                          - m[2][2] * m[3][0]))
                + m[0][2] * (m[1][0] * (m[2][1] * m[3][3]
                                        - m[2][3] * m[3][1])
                             - m[1][1] * (m[2][0] * m[3][3]
                                          - m[2][3] * m[3][0])
                             + m[1][3] * (m[2][0] * m[3][1]
                                          - m[2][1] * m[3][0]))
                - m[0][3] * (m[1][0] * (m[2][1] * m[3][2]
                                        - m[2][2] * m[3][1])
                             - m[1][1] * (m[2][0] * m[3][2]
                                          - m[2][2] * m[3][0])
                             + m[1][2] * (m[2][0] * m[3][1]
                                          - m[2][1] * m[3][0])))

    def inverse(self) -> Mat4:
        det = self.determinant()
        if abs(det) < 1e-12:
            return Mat4.identity()
        m = self.m
        inv = [[0.0] * 4 for _ in range(4)]
        inv[0][0] = (m[1][1]*(m[2][2]*m[3][3]-m[2][3]*m[3][2])
                     - m[1][2]*(m[2][1]*m[3][3]-m[2][3]*m[3][1])
                     + m[1][3]*(m[2][1]*m[3][2]-m[2][2]*m[3][1]))/det
        inv[0][1] = (-m[0][1]*(m[2][2]*m[3][3]-m[2][3]*m[3][2])
                     + m[0][2]*(m[2][1]*m[3][3]-m[2][3]*m[3][1])
                     - m[0][3]*(m[2][1]*m[3][2]-m[2][2]*m[3][1]))/det
        inv[0][2] = (m[0][1]*(m[1][2]*m[3][3]-m[1][3]*m[3][2])
                     - m[0][2]*(m[1][1]*m[3][3]-m[1][3]*m[3][1])
                     + m[0][3]*(m[1][1]*m[3][2]-m[1][2]*m[3][1]))/det
        inv[0][3] = (-m[0][1]*(m[1][2]*m[2][3]-m[1][3]*m[2][2])
                     + m[0][2]*(m[1][1]*m[2][3]-m[1][3]*m[2][1])
                     - m[0][3]*(m[1][1]*m[2][2]-m[1][2]*m[2][1]))/det
        inv[1][0] = (-m[1][0]*(m[2][2]*m[3][3]-m[2][3]*m[3][2])
                     + m[1][2]*(m[2][0]*m[3][3]-m[2][3]*m[3][0])
                     - m[1][3]*(m[2][0]*m[3][2]-m[2][2]*m[3][0]))/det
        inv[1][1] = (m[0][0]*(m[2][2]*m[3][3]-m[2][3]*m[3][2])
                     - m[0][2]*(m[2][0]*m[3][3]-m[2][3]*m[3][0])
                     + m[0][3]*(m[2][0]*m[3][2]-m[2][2]*m[3][0]))/det
        inv[1][2] = (-m[0][0]*(m[1][2]*m[3][3]-m[1][3]*m[3][2])
                     + m[0][2]*(m[1][0]*m[3][3]-m[1][3]*m[3][0])
                     - m[0][3]*(m[1][0]*m[3][2]-m[1][2]*m[3][0]))/det
        inv[1][3] = (m[0][0]*(m[1][2]*m[2][3]-m[1][3]*m[2][2])
                     - m[0][2]*(m[1][0]*m[2][3]-m[1][3]*m[2][0])
                     + m[0][3]*(m[1][0]*m[2][2]-m[1][2]*m[2][0]))/det
        inv[2][0] = (m[1][0]*(m[2][1]*m[3][3]-m[2][3]*m[3][1])
                     - m[1][1]*(m[2][0]*m[3][3]-m[2][3]*m[3][0])
                     + m[1][3]*(m[2][0]*m[3][1]-m[2][1]*m[3][0]))/det
        inv[2][1] = (-m[0][0]*(m[2][1]*m[3][3]-m[2][3]*m[3][1])
                     + m[0][1]*(m[2][0]*m[3][3]-m[2][3]*m[3][0])
                     - m[0][3]*(m[2][0]*m[3][1]-m[2][1]*m[3][0]))/det
        inv[2][2] = (m[0][0]*(m[1][1]*m[3][3]-m[1][3]*m[3][1])
                     - m[0][1]*(m[1][0]*m[3][3]-m[1][3]*m[3][0])
                     + m[0][3]*(m[1][0]*m[3][1]-m[1][1]*m[3][0]))/det
        inv[2][3] = (-m[0][0]*(m[1][1]*m[2][3]-m[1][3]*m[2][1])
                     + m[0][1]*(m[1][0]*m[2][3]-m[1][3]*m[2][0])
                     - m[0][3]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))/det
        inv[3][0] = (-m[1][0]*(m[2][1]*m[3][2]-m[2][2]*m[3][1])
                     + m[1][1]*(m[2][0]*m[3][2]-m[2][2]*m[3][0])
                     - m[1][2]*(m[2][0]*m[3][1]-m[2][1]*m[3][0]))/det
        inv[3][1] = (m[0][0]*(m[2][1]*m[3][2]-m[2][2]*m[3][1])
                     - m[0][1]*(m[2][0]*m[3][2]-m[2][2]*m[3][0])
                     + m[0][2]*(m[2][0]*m[3][1]-m[2][1]*m[3][0]))/det
        inv[3][2] = (-m[0][0]*(m[1][1]*m[3][2]-m[1][2]*m[3][1])
                     + m[0][1]*(m[1][0]*m[3][2]-m[1][2]*m[3][0])
                     - m[0][2]*(m[1][0]*m[3][1]-m[1][1]*m[3][0]))/det
        inv[3][3] = (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
                     - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
                     + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))/det
        return Mat4(inv)


@dataclass
class ShaderProgram:
    program_id: int = 0
    vertex_source: str = ""
    fragment_source: str = ""
    vertex_compiled: bool = False
    fragment_compiled: bool = False
    linked: bool = False
    log: str = ""


@dataclass
class VertexBuffer:
    vbo_id: int = 0
    data: list[float] = field(default_factory=list)
    usage: GLEnum = GLEnum.STATIC_DRAW
    size: int = 0


@dataclass
class Framebuffer:
    fbo_id: int = 0
    width: int = 0
    height: int = 0
    color_attachment: str = ""
    depth_attachment: str = ""
    has_depth: bool = False
    has_stencil: bool = False


class GraphicsContext:
    """图形上下文（OpenGL 兼容）。"""

    def __init__(self, version: str = "4.6"):
        self.version = version
        self._programs: dict[int, ShaderProgram] = {}
        self._shaders: dict[int, tuple[GLEnum, str]] = {}
        self._buffers: dict[int, VertexBuffer] = {}
        self._framebuffers: dict[int, Framebuffer] = {}
        self._textures: dict[int, dict[str, Any]] = {}
        self._state: dict[str, Any] = {
            "depth_test": False,
            "cull_face": False,
            "blend": BlendState.DISABLED,
            "topology": PrimitiveTopology.TRIANGLE_LIST,
            "viewport": [0, 0, 1280, 720],
            "clear_color": [0.0, 0.0, 0.0, 1.0],
        }
        self._uniforms: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._draw_calls = 0
        self._vertices = 0
        self._current_program = 0
        self._current_vbo = 0
        self._lock = threading.Lock()

    def gen_buffers(self, count: int = 1) -> list[int]:
        with self._lock:
            start = self._next_id
            self._next_id += count
            return list(range(start, start + count))

    def compile_shader(self, stage: GLEnum,
                       source: str) -> int:
        sid = self._next_id
        self._next_id += 1
        self._shaders[sid] = (stage, source)
        return sid

    def create_program(self, vertex_shader: int,
                       fragment_shader: int) -> int:
        pid = self._next_id
        self._next_id += 1
        prog = ShaderProgram(program_id=pid)
        if vertex_shader in self._shaders:
            stage, src = self._shaders[vertex_shader]
            prog.vertex_source = src
            prog.vertex_compiled = (stage == GLEnum.VERTEX_SHADER)
        if fragment_shader in self._shaders:
            stage, src = self._shaders[fragment_shader]
            prog.fragment_source = src
            prog.fragment_compiled = (
                stage == GLEnum.FRAGMENT_SHADER)
        self._programs[pid] = prog
        return pid

    def link_program(self, pid: int) -> bool:
        prog = self._programs.get(pid)
        if prog and prog.vertex_compiled and prog.fragment_compiled:
            prog.linked = True
            self._uniforms[pid] = {}
            return True
        return False

    def use_program(self, pid: int) -> bool:
        if pid in self._programs:
            self._current_program = pid
            return True
        return False

    def set_uniform(self, name: str, value: Any) -> bool:
        self._uniforms.setdefault(
            self._current_program, {})[name] = value
        return True

    def buffer_data(self, vbo_id: int, data: list[float],
                    usage: GLEnum = GLEnum.STATIC_DRAW) -> int:
        vb = self._buffers.get(vbo_id)
        if vb is None:
            vb = VertexBuffer(vbo_id=vbo_id)
            self._buffers[vbo_id] = vb
        vb.data = list(data)
        vb.usage = usage
        vb.size = len(data) * 4
        self._current_vbo = vbo_id
        return vb.size

    def bind_buffer(self, vbo_id: int) -> bool:
        if vbo_id in self._buffers:
            self._current_vbo = vbo_id
            return True
        return False

    def create_texture(self, width: int, height: int,
                       internal_format: GLEnum = GLEnum.RGBA,
                       data: bytes | None = None) -> int:
        tid = self._next_id
        self._next_id += 1
        self._textures[tid] = {
            "width": width, "height": height,
            "format": internal_format,
            "data": data or b"\x00" * (width * height * 4),
        }
        return tid

    def bind_texture(self, tid: int, unit: int = 0) -> bool:
        return tid in self._textures

    def gen_framebuffer(self) -> int:
        fid = self._next_id
        self._next_id += 1
        self._framebuffers[fid] = Framebuffer(fbo_id=fid)
        return fid

    def bind_framebuffer(self, fid: int) -> bool:
        return fid in self._framebuffers

    def framebuffer_texture(self, fid: int, tid: int,
                            attachment: str = "color") -> bool:
        fb = self._framebuffers.get(fid)
        if fb and tid in self._textures:
            setattr(fb, f"{attachment}_attachment", str(tid))
            if attachment == "depth":
                fb.has_depth = True
            return True
        return False

    def enable(self, cap: GLEnum) -> bool:
        mapping = {
            GLEnum.DEPTH_TEST: "depth_test",
            GLEnum.CULL_FACE: "cull_face",
        }
        key = mapping.get(cap)
        if key:
            self._state[key] = True
            return True
        return False

    def disable(self, cap: GLEnum) -> bool:
        mapping = {
            GLEnum.DEPTH_TEST: "depth_test",
            GLEnum.CULL_FACE: "cull_face",
        }
        key = mapping.get(cap)
        if key:
            self._state[key] = False
            return True
        return False

    def set_blend(self, mode: BlendState) -> bool:
        self._state["blend"] = mode
        return True

    def set_topology(self, t: PrimitiveTopology) -> bool:
        self._state["topology"] = t
        return True

    def viewport(self, x: int, y: int, w: int, h: int) -> bool:
        self._state["viewport"] = [x, y, w, h]
        return True

    def clear_color(self, r: float, g: float,
                    b: float, a: float = 1.0) -> bool:
        self._state["clear_color"] = [r, g, b, a]
        return True

    def draw_arrays(self, mode: GLEnum, first: int,
                    count: int) -> int:
        self._draw_calls += 1
        self._vertices += count
        return count

    def draw_elements(self, mode: GLEnum,
                      count: int) -> int:
        self._draw_calls += 1
        self._vertices += count
        return count

    def get_stats(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "programs": len(self._programs),
            "buffers": len(self._buffers),
            "textures": len(self._textures),
            "framebuffers": len(self._framebuffers),
            "draw_calls": self._draw_calls,
            "vertices": self._vertices,
        }


class VulkanInstance:
    """Vulkan 实例。"""

    def __init__(self, app_name: str = "Matha",
                 engine: str = "MathaVK"):
        self.app_name = app_name
        self.engine = engine
        self.api_version = "1.3.296"
        self.instance: int | None = None
        self.physical_devices: list[dict[str, Any]] = []
        self._next_id = 1

    def create_instance(self) -> int:
        self.instance = self._next_id
        self._next_id += 1
        self.physical_devices = [{
            "name": "Matha Virtual GPU",
            "type": VKEnum.VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU,
            "api_version": "1.3.296",
            "driver_version": "1.0.0",
            "memory_bytes": 8 * 1024 ** 3,
            "features": {
                "geometry_shader": True,
                "compute_shader": True,
                "ray_tracing": True,
                "tessellation": True,
            },
        }]
        return self.instance

    def enumerate_physical_devices(self) -> list[dict[str, Any]]:
        return self.physical_devices

    def create_device(self, idx: int = 0) -> int:
        did = self._next_id
        self._next_id += 1
        return did

    def get_device_features(self, idx: int = 0) -> dict[str, bool]:
        if self.physical_devices:
            return self.physical_devices[idx]["features"]
        return {}


class D3D12Device:
    """Direct3D 12 设备。"""

    def __init__(self):
        self.feature_levels = [
            "12_2", "12_1", "12_0", "11_1", "11_0",
        ]
        self.device: int | None = None
        self.command_queue: int | None = None
        self._fence_value = 0
        self._next_id = 1

    def create_device(self) -> int:
        self.device = self._next_id
        self._next_id += 1
        return self.device

    def create_command_queue(self, name: str = "Graphics") -> int:
        self.command_queue = self._next_id
        self._next_id += 1
        return self.command_queue

    def create_fence(self, initial: int = 0) -> int:
        self._fence_value = initial
        return self._next_id

    def signal_fence(self) -> int:
        self._fence_value += 1
        return self._fence_value

    def get_info(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "queue": self.command_queue,
            "feature_levels": self.feature_levels,
            "fence": self._fence_value,
        }


def create_graphics_context(version: str = "4.6") -> GraphicsContext:
    return GraphicsContext(version)


def create_vulkan_instance(app: str = "Matha") -> VulkanInstance:
    vk = VulkanInstance(app)
    vk.create_instance()
    return vk


def create_d3d12_device() -> D3D12Device:
    d = D3D12Device()
    d.create_device()
    d.create_command_queue()
    return d


def create_vec3(x: float = 0, y: float = 0, z: float = 0) -> Vec3:
    return Vec3(x, y, z)


def create_mat4_identity() -> Mat4:
    return Mat4.identity()


# ============================================================
# 内置注册
# ============================================================

def _register_graphics_driver(builtins: dict) -> None:
    builtins["创建图形上下文"] = create_graphics_context
    builtins["创建Vulkan实例"] = create_vulkan_instance
    builtins["创建D3D12设备"] = create_d3d12_device
    builtins["创建三维向量"] = create_vec3
    builtins["创建四阶矩阵"] = create_mat4_identity


def _graphics_driver_names() -> list[str]:
    return ["创建图形上下文", "创建Vulkan实例",
            "创建D3D12设备", "创建三维向量", "创建四阶矩阵"]


__all__ = [
    "GLEnum", "VKEnum", "DXGIFormat",
    "BlendState", "PrimitiveTopology",
    "Vec2", "Vec3", "Vec4", "Mat4",
    "ShaderProgram", "VertexBuffer", "Framebuffer",
    "GraphicsContext", "VulkanInstance", "D3D12Device",
    "create_graphics_context", "create_vulkan_instance",
    "create_d3d12_device", "create_vec3",
    "create_mat4_identity",
    "_register_graphics_driver", "_graphics_driver_names",
]
