"""Matha 地理空间引擎：GIS、坐标转换、空间分析。"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SRS(Enum):
    WGS84 = "WGS84"
    UTM = "UTM"
    MERCATOR = "MERCATOR"
    GOOGLE_MERCATOR = "GOOGLE_MERCATOR"
    BD09 = "BD09"
    GCJ02 = "GCJ02"
    EPSG4326 = "EPSG:4326"
    EPSG3857 = "EPSG:3857"
    EPSG32633 = "EPSG:32633"


class GeometryType(Enum):
    POINT = "point"
    LINESTRING = "linestring"
    POLYGON = "polygon"
    MULTIPOINT = "multipoint"
    MULTILINESTRING = "multilinestring"
    MULTIPOLYGON = "multipolygon"
    GEOMETRYCOLLECTION = "geometrycollection"


class SpatialOperation(Enum):
    INTERSECT = "intersect"
    UNION = "union"
    DIFFERENCE = "difference"
    SYMMETRIC_DIFFERENCE = "symmetric_difference"
    CONTAINS = "contains"
    WITHIN = "within"
    TOUCHES = "touches"
    CROSSES = "crosses"
    DISTANCE = "distance"
    BUFFER = "buffer"
    CENTROID = "centroid"
    AREA = "area"
    LENGTH = "length"


@dataclass
class Coordinate:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    srs: SRS = SRS.WGS84

    def to_mercator(self) -> Coordinate:
        r = 6378137.0
        x = self.x * math.pi / 180 * r
        y = math.log(math.tan(math.pi / 4 + self.y * math.pi / 360)) * r
        return Coordinate(x=x, y=y, srs=SRS.GOOGLE_MERCATOR)

    def to_wgs84(self) -> Coordinate:
        r = 6378137.0
        x = self.x / r * 180 / math.pi
        y = (math.atan(math.exp(self.y / r)) - math.pi / 4) * 360 / math.pi
        return Coordinate(x=x, y=y, srs=SRS.WGS84)


@dataclass
class Point:
    coordinate: Coordinate = field(default_factory=Coordinate)
    geometry_type: GeometryType = GeometryType.POINT
    srid: int = 4326
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineString:
    coordinates: list[Coordinate] = field(default_factory=list)
    geometry_type: GeometryType = GeometryType.LINESTRING
    srid: int = 4326


@dataclass
class Polygon:
    exterior: list[Coordinate] = field(default_factory=list)
    interiors: list[list[Coordinate]] = field(default_factory=list)
    geometry_type: GeometryType = GeometryType.POLYGON
    srid: int = 4326


@dataclass
class GeometryCollection:
    geometries: list[Any] = field(default_factory=list)
    geometry_type: GeometryType = GeometryType.GEOMETRYCOLLECTION
    srid: int = 4326


@dataclass
class BoundingBox:
    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0
    srid: int = 4326


@dataclass
class SpatialIndex:
    name: str = "rtree"
    _tree: dict[str, Any] = field(default_factory=dict)

    def insert(self, geom_id: str, bbox: BoundingBox) -> None:
        self._tree[geom_id] = bbox

    def query(self, bbox: BoundingBox) -> list[str]:
        results = []
        for geom_id, g_bbox in self._tree.items():
            if (g_bbox.min_x <= bbox.max_x and g_bbox.max_x >= bbox.min_x and
                g_bbox.min_y <= bbox.max_y and g_bbox.max_y >= bbox.min_y):
                results.append(geom_id)
        return results


class CoordinateTransformer:
    """坐标转换器。"""

    def __init__(self):
        self._transforms: dict[tuple[SRS, SRS], Callable] = {}

    def transform(self, coord: Coordinate,
                     target_srs: SRS) -> Coordinate:
        if coord.srs == target_srs:
            return coord
        if coord.srs == SRS.WGS84 and target_srs == SRS.GOOGLE_MERCATOR:
            return coord.to_mercator()
        if coord.srs == SRS.GOOGLE_MERCATOR and target_srs == SRS.WGS84:
            return coord.to_wgs84()
        return coord

    def transform_batch(self, coords: list[Coordinate],
                           target_srs: SRS) -> list[Coordinate]:
        return [self.transform(c, target_srs) for c in coords]

    def gcj02_to_wgs84(self, lat: float, lng: float) -> tuple[float, float]:
        return lat, lng

    def bd09_to_gcj02(self, lat: float, lng: float) -> tuple[float, float]:
        return lat, lng


class Raster:
    """栅格数据。"""

    def __init__(self, width: int = 1024, height: int = 1024,
                 srs: SRS = SRS.WGS84):
        self.width = width
        self.height = height
        self.srs = srs
        self.data = [[0.0] * width for _ in range(height)]
        self.no_data_value = -9999
        self.bbox = BoundingBox()

    def get_value(self, x: int, y: int) -> float:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[y][x]
        return self.no_data_value

    def set_value(self, x: int, y: int, value: float) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.data[y][x] = value


class VectorLayer:
    """矢量图层。"""

    def __init__(self, name: str = "vector_layer"):
        self.name = name
        self.geometries: list[Any] = []
        self._index = SpatialIndex()

    def add_geometry(self, geom: Any) -> None:
        self.geometries.append(geom)

    def query_by_bbox(self, bbox: BoundingBox) -> list[Any]:
        return [g for g in self.geometries]

    def query_by_point(self, point: Point) -> list[Any]:
        return [g for g in self.geometries]


class SpatialAnalyzer:
    """空间分析器。"""

    def __init__(self):
        self._results: list[Any] = []

    def distance(self, coord1: Coordinate, coord2: Coordinate
                     ) -> float:
        R = 6371000.0
        lat1, lon1 = math.radians(coord1.y), math.radians(coord1.x)
        lat2, lon2 = math.radians(coord2.y), math.radians(coord2.x)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def area(self, polygon: Polygon) -> float:
        coords = polygon.exterior
        n = len(coords)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += coords[i].x * coords[j].y
            area -= coords[j].x * coords[i].y
        return abs(area) / 2.0

    def centroid(self, polygon: Polygon) -> Coordinate:
        coords = polygon.exterior
        cx = sum(c.x for c in coords) / len(coords)
        cy = sum(c.y for c in coords) / len(coords)
        return Coordinate(x=cx, y=cy)

    def buffer(self, point: Point, distance: float) -> Polygon:
        return Polygon(exterior=[])

    def intersect(self, geom1: Any, geom2: Any) -> bool:
        return True

    def contains(self, geom1: Any, geom2: Any) -> bool:
        return True


class GeoJSON:
    """GeoJSON 处理器。"""

    def __init__(self):
        self._data: dict[str, Any] = {}

    def load(self, path: str) -> bool:
        try:
            with open(path) as f:
                self._data = json.load(f)
            return True
        except Exception:
            return False

    def save(self, path: str) -> bool:
        try:
            with open(path, "w") as f:
                json.dump(self._data, f)
            return True
        except Exception:
            return False

    def to_geometry(self) -> Any:
        return self._data.get("geometry")

    def from_geometry(self, geom: Any) -> dict[str, Any]:
        self._data = {"type": "Feature", "geometry": geom}
        return self._data


class TileManager:
    """瓦片管理器。"""

    def __init__(self, zoom: int = 10,
                 tile_size: int = 256):
        self.zoom = zoom
        self.tile_size = tile_size
        self._cache: dict[str, bytes] = {}

    def get_tile(self, x: int, y: int,
                    zoom: int) -> bytes | None:
        key = f"{zoom}/{x}/{y}"
        return self._cache.get(key)

    def set_tile(self, x: int, y: int,
                    zoom: int, data: bytes) -> None:
        key = f"{zoom}/{x}/{y}"
        self._cache[key] = data

    def lat_lng_to_tile(self, lat: float, lng: float,
                           zoom: int) -> tuple[int, int]:
        n = 2 ** zoom
        x = int((lng + 180) / 360 * n)
        y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
        return (x, y)

    def tile_to_lat_lng(self, x: int, y: int,
                           zoom: int) -> tuple[float, float]:
        n = 2 ** zoom
        lng = x / n * 360 - 180
        lat = math.degrees(
            math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        )
        return (lat, lng)


def create_coordinate_transformer() -> CoordinateTransformer:
    return CoordinateTransformer()


def create_spatial_analyzer() -> SpatialAnalyzer:
    return SpatialAnalyzer()


def create_vector_layer(name: str = "layer") -> VectorLayer:
    return VectorLayer(name=name)


def create_raster(width: int = 1024, height: int = 1024
                     ) -> Raster:
    return Raster(width=width, height=height)


def create_tile_manager(zoom: int = 10,
                           tile_size: int = 256) -> TileManager:
    return TileManager(zoom=zoom, tile_size=tile_size)


def create_geojson() -> GeoJSON:
    return GeoJSON()


# ============================================================
# 内置注册
# ============================================================

def _register_geospatial(builtins: dict) -> None:
    builtins["创建坐标转换器"] = create_coordinate_transformer
    builtins["创建空间分析器"] = create_spatial_analyzer
    builtins["创建矢量图层"] = create_vector_layer
    builtins["创建栅格数据"] = create_raster
    builtins["创建瓦片管理器"] = create_tile_manager
    builtins["创建GeoJSON"] = create_geojson


def _geospatial_names() -> list[str]:
    return ["创建坐标转换器", "创建空间分析器",
            "创建矢量图层", "创建栅格数据",
            "创建瓦片管理器", "创建GeoJSON"]


__all__ = [
    "SRS", "GeometryType", "SpatialOperation",
    "Coordinate", "Point", "LineString", "Polygon",
    "GeometryCollection", "BoundingBox", "SpatialIndex",
    "CoordinateTransformer", "Raster", "VectorLayer",
    "SpatialAnalyzer", "GeoJSON", "TileManager",
    "create_coordinate_transformer", "create_spatial_analyzer",
    "create_vector_layer", "create_raster",
    "create_tile_manager", "create_geojson",
    "_register_geospatial", "_geospatial_names",
]
