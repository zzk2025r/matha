"""Matha 显示器与显示管理模块：显示器配置、分辨率管理、多屏、渲染管线。

覆盖：
  1) 显示器配置（分辨率、刷新率、色深）
  2) 多屏管理
  3) 渲染管线
  4) 显示模式切换
  5) 屏幕截图
  6) 显示统计
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class DisplayMode(Enum):
    """显示模式。"""
    WINDOWED = "windowed"
    FULLSCREEN = "fullscreen"
    BORDERLESS = "borderless"
    HEADLESS = "headless"


class RefreshRate(Enum):
    """刷新率。"""
    R60 = 60
    R75 = 75
    R120 = 120
    R144 = 144
    R240 = 240
    R360 = 360


@dataclass
class Resolution:
    """分辨率。"""
    width: int
    height: int
    refresh_rate: int = 60
    bits_per_pixel: int = 32

    def to_string(self) -> str:
        """分辨率字符串。"""
        return f"{self.width}x{self.height} @{self.refresh_rate}Hz {self.bits_per_pixel}bit"

    @property
    def aspect_ratio(self) -> float:
        """宽高比。"""
        if self.height == 0:
            return 0.0
        return self.width / self.height


@dataclass
class MonitorInfo:
    """显示器信息。"""
    name: str
    resolution: Resolution
    is_primary: bool = False
    refresh_rate: int = 60
    bits_per_pixel: int = 32
    scale_factor: float = 1.0
    manufacturer: str = "Matha"
    model: str = "VirtualDisplay"


@dataclass
class DisplayStats:
    """显示统计。"""
    fps: float = 60.0
    frame_time_ms: float = 16.67
    gpu_usage: float = 0.0
    memory_used_mb: float = 0.0
    draw_calls: int = 0
    triangles: int = 0


class DisplayManager:
    """显示器管理器：管理所有显示器配置和状态。"""

    def __init__(self, width: int = 1920, height: int = 1080,
                 refresh_rate: int = 60):
        self.width = width
        self.height = height
        self.refresh_rate = refresh_rate
        self._monitors: list[MonitorInfo] = []
        self._primary: MonitorInfo | None = None
        self._mode: DisplayMode = DisplayMode.WINDOWED
        self._stats = DisplayStats()
        self._screenshots: list[str] = []
        self._frame_count: int = 0
        self._initialized: bool = False
        self._init_display()

    def _init_display(self) -> None:
        """初始化默认显示器。"""
        primary = MonitorInfo(
            name="Primary",
            resolution=Resolution(self.width, self.height, self.refresh_rate),
            is_primary=True,
            manufacturer="Matha",
            model="VirtualDisplay v4.5",
        )
        self._monitors.append(primary)
        self._primary = primary
        self._initialized = True

    def add_monitor(self, name: str, width: int, height: int,
                    refresh_rate: int = 60, is_primary: bool = False
                    ) -> MonitorInfo:
        """添加显示器。"""
        res = Resolution(width, height, refresh_rate)
        monitor = MonitorInfo(
            name=name,
            resolution=res,
            is_primary=is_primary,
            refresh_rate=refresh_rate,
        )
        self._monitors.append(monitor)
        if is_primary:
            self._primary = monitor
        return monitor

    def get_resolution(self, monitor_name: str = "") -> Resolution:
        """获取分辨率。"""
        if not monitor_name:
            if self._primary:
                return self._primary.resolution
            return Resolution(1920, 1080)
        for m in self._monitors:
            if m.name == monitor_name:
                return m.resolution
        return Resolution(1920, 1080)

    def set_resolution(self, width: int, height: int,
                       refresh_rate: int = 60) -> bool:
        """设置主显示器分辨率。"""
        if self._primary:
            self._primary.resolution = Resolution(width, height, refresh_rate)
            return True
        return False

    def set_mode(self, mode: DisplayMode) -> None:
        """设置显示模式。"""
        self._mode = mode

    def get_mode(self) -> DisplayMode:
        """获取显示模式。"""
        return self._mode

    def get_monitor_count(self) -> int:
        """获取显示器数量。"""
        return len(self._monitors)

    def list_monitors(self) -> list[MonitorInfo]:
        """列出所有显示器。"""
        return list(self._monitors)

    def screenshot(self) -> str:
        """截图。"""
        self._frame_count += 1
        screenshot_id = f"screenshot_{self._frame_count}_{int(math.time()) if hasattr(math, 'time') else 0}"
        self._screenshots.append(screenshot_id)
        return screenshot_id

    def get_stats(self) -> DisplayStats:
        """获取显示统计。"""
        self._stats.fps = 60.0 if self._mode != DisplayMode.HEADLESS else 0.0
        return self._stats

    def get_pipeline_stats(self) -> dict:
        """获取渲染管线统计。"""
        return {
            "mode": self._mode.value,
            "monitors": len(self._monitors),
            "fps": self._stats.fps,
            "frame_count": self._frame_count,
            "screenshots": len(self._screenshots),
            "gpu_usage": self._stats.gpu_usage,
            "draw_calls": self._stats.draw_calls,
        }


def create_display_manager(width: int = 1920, height: int = 1080,
                            refresh_rate: int = 60) -> DisplayManager:
    """创建显示器管理器。"""
    dm = DisplayManager()
    dm.set_resolution(width, height, refresh_rate)
    return dm


def create_resolution(width: int, height: int, refresh_rate: int = 60) -> Resolution:
    """创建分辨率对象。"""
    return Resolution(width, height, refresh_rate)


def _register_display(builtins: dict) -> None:
    """注册显示器内置函数。"""
    builtins["创建显示器管理器"] = lambda w=1920, h=1080, r=60: create_display_manager(w, h, r)
    builtins["创建分辨率"] = lambda w, h, r=60: create_resolution(w, h, r)
    builtins["添加显示器"] = lambda dm, name, w, h, r=60: dm.add_monitor(name, w, h, r)
    builtins["获取分辨率"] = lambda dm, name="": dm.get_resolution(name)
    builtins["设置分辨率"] = lambda dm, w, h, r=60: dm.set_resolution(w, h, r)
    builtins["设置显示模式"] = lambda dm, m: dm.set_mode(DisplayMode(m))
    builtins["获取显示器数量"] = lambda dm: dm.get_monitor_count()
    builtins["列出显示器"] = lambda dm: dm.list_monitors()
    builtins["截图"] = lambda dm: dm.screenshot()
    builtins["显示统计"] = lambda dm: dm.get_stats()
    builtins["管线统计"] = lambda dm: dm.get_pipeline_stats()


def _display_symtab_names() -> list[str]:
    return [
        "创建显示器管理器", "创建分辨率", "添加显示器",
        "获取分辨率", "设置分辨率", "设置显示模式",
        "获取显示器数量", "列出显示器", "截图",
        "显示统计", "管线统计",
    ]


__all__ = [
    "DisplayMode", "RefreshRate", "Resolution", "MonitorInfo",
    "DisplayStats", "DisplayManager",
    "create_display_manager", "create_resolution",
    "_register_display", "_display_symtab_names",
]
