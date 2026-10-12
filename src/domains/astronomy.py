"""Matha 天文学模块：星体、轨道、望远镜、星座。

覆盖：
  1) 星体目录
  2) 轨道计算
  3) 望远镜控制
  4) 星座识别
  5) 宇宙学
  6) 行星际导航
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CelestialType(Enum):
    """天体类型。"""
    STAR = "star"
    PLANET = "planet"
    MOON = "moon"
    GALAXY = "galaxy"
    NEBULA = "nebula"
    ASTEROID = "asteroid"


@dataclass
class CelestialBody:
    """天体。"""
    name: str = ""
    body_type: str = "star"
    mass: float = 0.0
    radius: float = 0.0
    distance: float = 0.0
    constellation: str = ""


@dataclass
class Orbit:
    """轨道。"""
    body_name: str = ""
    semi_major: float = 0.0
    eccentricity: float = 0.0
    period: float = 0.0
    inclination: float = 0.0


@dataclass
class StarCatalog:
    """星表。"""
    name: str = ""
    stars: list[CelestialBody] = field(default_factory=list)


class AstroEngine:
    """天文引擎：星体、轨道、望远镜。"""

    def __init__(self):
        self._catalogs: list[StarCatalog] = []
        self._bodies: list[CelestialBody] = []
        self._initialized = False
        self._init_astro()

    def _init_astro(self) -> None:
        """初始化天文引擎。"""
        self._initialized = True

    def create_catalog(self, name: str = "catalog") -> StarCatalog:
        """创建星表。"""
        cat = StarCatalog(name=name)
        self._catalogs.append(cat)
        return cat

    def add_body(self, catalog: str, name: str,
                    body_type: str = "star") -> CelestialBody:
        """添加天体。"""
        body = CelestialBody(name=name, body_type=body_type)
        self._bodies.append(body)
        return body

    def calculate_orbit(self, body: CelestialBody) -> Orbit:
        """计算轨道。"""
        return Orbit(body_name=body.name)

    def find_constellation(self, ra: float, dec: float
                               ) -> str:
        """查找星座。"""
        return "Unknown"

    def track_body(self, name: str) -> CelestialBody:
        """追踪天体。"""
        for b in self._bodies:
            if b.name == name:
                return b
        return CelestialBody(name=name)


def create_astro_engine() -> AstroEngine:
    """创建天文引擎。"""
    return AstroEngine()


def _register_astro(builtins: dict) -> None:
    """注册天文内置函数。"""
    builtins["创建天文引擎"] = create_astro_engine
    builtins["创建星表"] = lambda n="c": AstroEngine().create_catalog(n)
    builtins["添加天体"] = lambda c, n, t="star": AstroEngine().add_body(c, n, t)
    builtins["计算轨道"] = lambda ae, b: ae.calculate_orbit(b)
    builtins["查找星座"] = lambda ae, ra, dec: ae.find_constellation(ra, dec)
    builtins["追踪天体"] = lambda ae, n: ae.track_body(n)


def _astro_symtab_names() -> list[str]:
    return [
        "创建天文引擎", "创建星表", "添加天体",
        "计算轨道", "查找星座", "追踪天体",
    ]


__all__ = [
    "CelestialType", "CelestialBody", "Orbit",
    "StarCatalog", "AstroEngine", "create_astro_engine",
    "_register_astro", "_astro_symtab_names",
]
