# -*- coding: utf-8 -*-
"""Matha 依赖层：全功能标准库实现 + 可选增强模块自动检测。

设计原则：
  - 无依赖可运行：所有功能均有纯 Python 标准库实现
  - 可选增强：检测到第三方库时自动切换高性能版本
  - 透明切换：上层代码无需修改，依赖层自动选择最佳实现

依赖分类：
  [S] Standalone - 仅用标准库，零外部依赖
  [O] Optional   - 可选增强，未安装时自动降级为标准库实现

包含模块：
  S: cache        - 内存缓存（LRU/TTL）
  S: serde        - 序列化/反序列化（JSON fallback）
  S: logging      - 结构化日志（logging fallback）
  S: platform     - 平台检测与路径处理
  S: io_utils     - 文件/目录操作增强
  S: timing       - 性能计时工具
  O: msgpack      - 高性能二进制序列化（降级为 json）
  O: ujson        - 极速 JSON（降级为 json）
  O: orjson       - 零拷贝 JSON（降级为 json）
  O: pyyaml       - YAML 支持（降级为 JSON）
  O: lz4         - 快速压缩（降级为无压缩）
"""

from __future__ import annotations

# ============================================================
# 平台检测与路径处理 [S]
# ============================================================

import os
import sys
import platform as _platform_module
from pathlib import Path as _Path


def get_platform() -> str:
    """获取当前平台标识。"""
    sys_name = _platform_module.system().lower()
    if sys_name == "windows":
        return "windows"
    elif sys_name == "linux":
        return "linux"
    elif sys_name == "darwin":
        return "macos"
    return sys_name


def get_arch() -> str:
    """获取 CPU 架构。"""
    return _platform_module.machine().lower()


def get_python_version() -> tuple[int, int, int]:
    """获取 Python 版本。"""
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def is_portable_env() -> bool:
    """检测是否为无 pip 的便携式环境（如 pyarmor、Nuitka 静态编译）。"""
    return "site-packages" not in sys.path


def resolve_matha_root() -> Path:
    """解析 Matha 项目根目录。"""
    return _Path(__file__).parent.parent


# ============================================================
# 内存缓存 [S]
# ============================================================

from collections import OrderedDict
from threading import Lock
import time as _time_mod


class LRUCache:
    """线程安全的 LRU 缓存，纯标准库实现。"""

    def __init__(self, maxsize: int = 256):
        self._maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key) -> object | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key, value) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def invalidate(self, key) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total else 0.0,
                "size": len(self._cache),
            }


class TTLCache:
    """带 TTL 的缓存，纯标准库实现。"""

    def __init__(self, default_ttl: float = 60.0, maxsize: int = 512):
        self._default_ttl = default_ttl
        self._cache: dict = {}  # key -> (value, expiry)
        self._lock = Lock()
        self._maxsize = maxsize

    def get(self, key, ttl: float = None) -> object | None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if _time_mod.time() < expiry:
                    return value
                del self._cache[key]
            return None

    def put(self, key, value, ttl: float = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            self._evict_if_needed()
            self._cache[key] = (value, _time_mod.time() + ttl)

    def invalidate(self, key) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _evict_if_needed(self) -> None:
        now = _time_mod.time()
        expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired:
            del self._cache[k]
        while len(self._cache) > self._maxsize:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]


# ============================================================
# 序列化/反序列化 [S + O]
# ============================================================

import json as _json_stdlib
import struct
import zlib
import base64
import hashlib
import pickle as _pickle_stdlib


def to_json(obj) -> str:
    """对象序列化为 JSON 字符串（纯标准库）。"""
    return _json_stdlib.dumps(obj, ensure_ascii=False, default=_json_default)


def from_json(text: str) -> object:
    """JSON 字符串反序列化为对象（纯标准库）。"""
    return _json_stdlib.loads(str(text))


def to_json_pretty(obj) -> str:
    """对象序列化为格式化 JSON 字符串。"""
    return _json_stdlib.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(obj):
    """JSON 默认序列化器。"""
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "__dict__") and obj.__dict__:
        return obj.__dict__
    if isinstance(obj, bytes):
        return {"__bytes__": base64.b64encode(obj).decode()}
    if isinstance(obj, set):
        return {"__set__": list(obj)}
    raise TypeError(f"对象不可序列化: {type(obj).__name__}")


def to_pickle(obj) -> bytes:
    """对象序列化为 pickle 字节（纯标准库）。"""
    return _pickle_stdlib.dumps(obj, protocol=4)


def from_pickle(data: bytes) -> object:
    """pickle 字节反序列化为对象（纯标准库）。"""
    return _pickle_stdlib.loads(data)


def to_b64(obj) -> str:
    """对象序列化为 Base64 字符串（JSON 兼容）。"""
    return base64.b64encode(to_pickle(obj)).decode("ascii")


def from_b64(text: str) -> object:
    """Base64 字符串反序列化为对象。"""
    return from_pickle(base64.b64decode(str(text)))


def hash_obj(obj) -> str:
    """计算对象的 SHA-256 哈希（用于缓存键）。"""
    data = to_json(obj).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


# ---- 可选增强：高性能序列化 ----

_msgpack = None
_ujson = None
_orjson = None
_lz4 = None


def _try_import_optional():
    """尝试导入可选依赖，失败则保持 None。"""
    global _msgpack, _ujson, _orjson, _lz4
    try:
        import msgpack as _m
        _msgpack = _m
    except ImportError:
        _msgpack = None
    try:
        import ujson as _u
        _ujson = _u
    except ImportError:
        _ujson = None
    try:
        import orjson as _o
        _orjson = _o
    except ImportError:
        _orjson = None
    try:
        import lz4.frame as _l
        _lz4 = _l
    except ImportError:
        _lz4 = None


_try_import_optional()


def fast_json_dumps(obj) -> str:
    """尝试使用最快的 JSON 实现。"""
    if _orjson:
        return _orjson.dumps(obj).decode("utf-8")
    if _ujson:
        return _ujson.dumps(obj)
    return to_json(obj)


def fast_json_loads(text: str) -> object:
    """尝试使用最快的 JSON 实现。"""
    if _orjson:
        return _orjson.loads(str(text).encode("utf-8"))
    if _ujson:
        return _ujson.loads(str(text))
    return from_json(text)


def fast_serialize(obj) -> bytes:
    """尝试使用最快的序列化。"""
    if _msgpack:
        return _msgpack.pack(obj, use_bin_type=True)
    return to_pickle(obj)


def fast_deserialize(data: bytes) -> object:
    """尝试使用最快的反序列化。"""
    if _msgpack:
        return _msgpack.unpackb(data, raw=False)
    return from_pickle(data)


def compress_data(data: bytes) -> bytes:
    """压缩数据（优先 lz4，降级 zlib）。"""
    if _lz4:
        return _lz4.compress(data, store_size=False)
    return zlib.compress(data, level=6)


def decompress_data(data: bytes) -> bytes:
    """解压缩数据。"""
    if _lz4:
        return _lz4.decompress(data)
    return zlib.decompress(data)


def serialize_for_storage(obj, use_compression: bool = True) -> bytes:
    """序列化为可存储格式（带压缩）。"""
    raw = fast_serialize(obj)
    if use_compression and len(raw) > 64:
        return compress_data(raw)
    return raw


def deserialize_from_storage(data: bytes) -> object:
    """从存储格式反序列化。"""
    if data and len(data) >= 2 and data[0] == 0x78:
        # zlib 压缩头 (0x78 9c / 0x78 da / 0x78 01)
        return fast_deserialize(decompress_data(data))
    return fast_deserialize(data)


# ============================================================
# 结构化日志 [S]
# ============================================================

import logging as _logging_stdlib


class MathaLogger:
    """轻量结构化日志器，纯标准库实现。"""

    def __init__(self, name: str = "matha", level: int = _logging_stdlib.WARNING):
        self.logger = _logging_stdlib.getLogger(name)
        self.logger.setLevel(level)
        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = _logging_stdlib.StreamHandler()
            handler.setFormatter(_logging_stdlib.Formatter(
                "[%(levelname).1s] %(message)s"
            ))
            self.logger.addHandler(handler)

    def info(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{msg} {extra}".strip())

    def debug(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"{msg} {extra}".strip())

    def warning(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.warning(f"{msg} {extra}".strip())

    def error(self, msg: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.error(f"{msg} {extra}".strip())

    def set_level(self, level: int) -> None:
        self.logger.setLevel(level)

    @property
    def is_debug(self) -> bool:
        return self.logger.isEnabledFor(_logging_stdlib.DEBUG)


# ============================================================
# IO 工具 [S]
# ============================================================

def safe_read_text(path: str, encoding: str = "utf-8") -> str:
    """安全读取文本文件。"""
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def safe_write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """安全写入文本文件（自动创建目录）。"""
    _Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def safe_append_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """安全追加文本文件（自动创建目录）。"""
    _Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding=encoding) as f:
        f.write(content)


def ensure_dir(path: str) -> Path:
    """确保目录存在。"""
    p = _Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_files(path: str, pattern: str = "*") -> list:
    """列出目录下匹配的文件。"""
    return sorted(str(p) for p in _Path(path).glob(pattern))


def file_age_seconds(path: str) -> float:
    """文件距今秒数。"""
    try:
        mtime = os.path.getmtime(path)
        return _time_mod.time() - mtime
    except OSError:
        return float("inf")


def atomic_write(path: str, content: str, encoding: str = "utf-8") -> None:
    """原子写入文件（先写临时文件再重命名）。"""
    tmp_path = path + ".tmp"
    safe_write_text(tmp_path, content, encoding)
    os.replace(tmp_path, path)


# ============================================================
# 性能计时 [S]
# ============================================================

import time as _time_mod


def timing(func, *args, **kwargs) -> tuple:
    """执行函数并返回 (结果, 耗时秒数)。"""
    start = _time_mod.perf_counter()
    result = func(*args, **kwargs)
    elapsed = _time_mod.perf_counter() - start
    return result, elapsed


def benchmark(func, *args, iterations: int = 1000, **kwargs) -> dict:
    """性能基准测试。"""
    times = []
    result = None
    for _ in range(iterations):
        start = _time_mod.perf_counter()
        result = func(*args, **kwargs)
        times.append(_time_mod.perf_counter() - start)
    return {
        "结果": result,
        "总耗时_ms": sum(times) * 1000,
        "平均耗时_us": (sum(times) / len(times)) * 1_000_000,
        "最快_us": min(times) * 1_000_000,
        "迭代次数": iterations,
    }


# ============================================================
# 依赖报告
# ============================================================

def get_dependency_status() -> dict:
    """返回当前依赖状态报告。"""
    return {
        "平台": get_platform(),
        "架构": get_arch(),
        "Python": f"{get_python_version()[0]}.{get_python_version()[1]}.{get_python_version()[2]}",
        "便携模式": is_portable_env(),
        "可选依赖": {
            "msgpack": "✓" if _msgpack else "✗",
            "ujson": "✓" if _ujson else "✗",
            "orjson": "✓" if _orjson else "✗",
            "pyyaml": "✓" if _try_import_yaml() else "✗",
            "lz4": "✓" if _lz4 else "✗",
        },
    }


def _try_import_yaml() -> bool:
    try:
        import yaml  # noqa
        return True
    except ImportError:
        return False


# ============================================================
# 公共 API 导出
# ============================================================

__all__ = [
    # 平台
    "get_platform", "get_arch", "get_python_version",
    "is_portable_env", "resolve_matha_root",
    # 缓存
    "LRUCache", "TTLCache",
    # 序列化
    "to_json", "from_json", "to_json_pretty",
    "to_pickle", "from_pickle", "to_b64", "from_b64",
    "hash_obj",
    "fast_json_dumps", "fast_json_loads",
    "fast_serialize", "fast_deserialize",
    "compress_data", "decompress_data",
    "serialize_for_storage", "deserialize_from_storage",
    # 日志
    "MathaLogger",
    # IO
    "safe_read_text", "safe_write_text", "safe_append_text",
    "ensure_dir", "list_files", "file_age_seconds", "atomic_write",
    # 性能
    "timing", "benchmark",
    # 依赖报告
    "get_dependency_status",
]
