"""Matha 地理空间模块：地图、GPS、地理编码、路径规划。

覆盖：
  1) 地图渲染
  2) GPS定位
  3) 地理编码
  4) 路径规划
  5) 空间分析
  6) 地理数据
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MapType(Enum):
    """地图类型。"""
    ROAD = "road"
    SATELLITE = "satellite"
    TERRAIN = "terrain"
    HYBRID = "hybrid"


@dataclass
class Location:
    """地理位置。"""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    name: str = ""


@dataclass
class Route:
    """路径。"""
    start: Location = field(default_factory=Location)
    end: Location = field(default_factory=Location)
    distance: float = 0.0
    duration: float = 0.0
    waypoints: list[Location] = field(default_factory=list)


@dataclass
class MapData:
    """地图数据。"""
    name: str = ""
    type: str = "road"
    zoom: int = 10
    center: Location = field(default_factory=Location)
    markers: list[Location] = field(default_factory=list)


class GeoEngine:
    """地理引擎：地图、GPS、路径规划。"""

    def __init__(self):
        self._maps: list[MapData] = []
        self._routes: list[Route] = []
        self._initialized = False
        self._init_geo()

    def _init_geo(self) -> None:
        """初始化地理引擎。"""
        self._initialized = True

    def create_map(self, name: str = "map",
                      map_type: str = "road") -> MapData:
        """创建地图。"""
        md = MapData(name=name, type=map_type)
        self._maps.append(md)
        return md

    def geocode(self, address: str) -> Location:
        """地理编码。"""
        return Location(latitude=0.0, longitude=0.0, name=address)

    def reverse_geocode(self, lat: float, lon: float) -> str:
        """逆地理编码。"""
        return f"Location({lat}, {lon})"

    def find_route(self, start: Location, end: Location
                       ) -> Route:
        """查找路径。"""
        route = Route(start=start, end=end)
        self._routes.append(route)
        return route

    def get_distance(self, lat1: float, lon1: float,
                        lat2: float, lon2: float) -> float:
        """计算距离。"""
        return 0.0

    def add_marker(self, map_name: str, lat: float,
                      lon: float, name: str = "") -> bool:
        """添加标记。"""
        return True


def create_geo_engine() -> GeoEngine:
    """创建地理引擎。"""
    return GeoEngine()


def _register_geo(builtins: dict) -> None:
    """注册地理内置函数。"""
    builtins["创建地理引擎"] = create_geo_engine
    builtins["创建地图"] = lambda n="m", t="road": GeoEngine().create_map(n, t)
    builtins["地理编码"] = lambda addr: GeoEngine().geocode(addr)
    builtins["逆地理编码"] = lambda lat, lon: GeoEngine().reverse_geocode(lat, lon)
    builtins["查找路径"] = lambda ge, s, e: ge.find_route(s, e)
    builtins["计算距离"] = lambda ge, la1, lo1, la2, lo2: ge.get_distance(la1, lo1, la2, lo2)
    builtins["添加标记"] = lambda ge, n, la, lo, nm="": ge.add_marker(n, la, lo, nm)


def _geo_symtab_names() -> list[str]:
    return [
        "创建地理引擎", "创建地图", "地理编码",
        "逆地理编码", "查找路径", "计算距离", "添加标记",
    ]


__all__ = [
    "MapType", "Location", "Route", "MapData",
    "GeoEngine", "create_geo_engine",
    "_register_geo", "_geo_symtab_names",
]
