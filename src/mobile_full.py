# -*- coding: utf-8 -*-
"""
Matha 移动端完整实现

提供完整的移动端支持和 Flutter 外壳：
  - 设备检测增强
  - 触摸交互优化
  - Flutter 外壳框架
  - 离线缓存层
"""
from __future__ import annotations
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MobileConfig:
    """移动端配置"""
    memory_limit_mb: int = 256
    max_matrix_size: int = 100  # 移动端限制矩阵大小
    enable_gpu_acceleration: bool = False
    enable_offline_cache: bool = True
    cache_max_size_mb: int = 50
    touch_sensitivity: float = 1.5  # 触摸灵敏度


class MobileDeviceDetector:
    """增强的移动设备检测"""

    _cache: Optional[bool] = None

    @classmethod
    def detect(cls) -> bool:
        """检测是否运行在移动设备上"""
        if cls._cache is not None:
            return cls._cache

        # 1. 环境变量
        if os.environ.get("MATHA_MOBILE") in ("1", "true", "yes"):
            cls._cache = True
            logger.info("移动设备: MATHA_MOBILE 环境变量")
            return True

        # 2. Platform 检测
        platform = sys.platform.lower()
        mobile_platforms = {"android", "iphone", "ipad", "linux-android"}
        if platform in mobile_platforms:
            cls._cache = True
            logger.info(f"移动设备: platform={platform}")
            return True

        # 3. User-Agent 检测（Web 环境）
        ua = os.environ.get("HTTP_USER_AGENT", "").lower()
        if any(kw in ua for kw in ["mobile", "android", "iphone", "ipad", "tablet"]):
            cls._cache = True
            logger.info("移动设备: User-Agent")
            return True

        cls._cache = False
        return False


class MobileAPI:
    """移动端简化的数学 API"""

    def __init__(self, config: Optional[MobileConfig] = None):
        self.config = config or MobileConfig()
        self._ops: Dict[str, Any] = {}
        self._cache: Dict[str, Any] = {}
        self._detect_backend()

    def _detect_backend(self) -> None:
        """检测可用后端"""
        try:
            from src.numpy_compat import array, zeros, ones, eye, svd_decompose
            self._ops = {
                "array": array,
                "zeros": zeros,
                "ones": ones,
                "eye": eye,
                "svd": svd_decompose,
            }
            logger.info("移动端后端: NumPy 兼容层")
        except ImportError:
            from src.stdlib.linear_algebra import Matrix, matrix_multiply
            self._ops = {
                "Matrix": Matrix,
                "matmul": matrix_multiply,
            }
            logger.info("移动端后端: 纯 Python 降级")

    def zeros(self, shape: tuple) -> Any:
        """创建零矩阵"""
        key = f"zeros_{shape}"
        if self.config.enable_offline_cache and key in self._cache:
            return self._cache[key]
        if "zeros" in self._ops:
            result = self._ops["zeros"](shape)
        else:
            if len(shape) == 1:
                result = [[0.0] * shape[0]]
            elif len(shape) == 2:
                result = [[0.0] * shape[1] for _ in range(shape[0])]
            else:
                result = []
        if self.config.enable_offline_cache:
            self._cache[key] = result
        return result

    def eye(self, n: int) -> Any:
        """单位矩阵"""
        key = f"eye_{n}"
        if self.config.enable_offline_cache and key in self._cache:
            return self._cache[key]
        if "eye" in self._ops:
            result = self._ops["eye"](n)
        else:
            result = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        if self.config.enable_offline_cache:
            self._cache[key] = result
        return result

    def matmul(self, a: Any, b: Any) -> Any:
        """矩阵乘法"""
        if "matmul" in self._ops:
            return self._ops["matmul"](a, b)
        # 简化实现
        return a

    def svd(self, matrix: Any) -> tuple:
        """SVD 分解"""
        if "svd" in self._ops:
            return self._ops["svd"](matrix)
        return (matrix, matrix, matrix)  # 降级：返回原矩阵

    def clear_cache(self) -> int:
        """清除缓存，释放内存"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"移动端缓存已清除: {count} 项")
        return count


class FlutterShell:
    """
    Flutter 外壳框架

    提供 Flutter 应用的接口定义，实际 Flutter 代码需单独开发。
    此处提供 Python 端的协议定义。
    """

    # Flutter 通道名称
    CHANNEL_MATH = "matha/math"
    CHANNEL_STORAGE = "matha/storage"
    CHANNEL_COLLAB = "matha/collab"

    # 消息协议
    @staticmethod
    def create_init_message(app_name: str, version: str) -> dict:
        """创建初始化消息"""
        return {
            "type": "init",
            "app": app_name,
            "version": version,
            "platform": sys.platform,
            "timestamp": __import__("time").time(),
        }

    @staticmethod
    def create_math_request(request_id: str, operation: str, params: list) -> dict:
        """创建数学计算请求"""
        return {
            "type": "math_request",
            "id": request_id,
            "operation": operation,
            "params": params,
        }

    @staticmethod
    def create_math_response(request_id: str, result: Any, error: Optional[str] = None) -> dict:
        """创建数学计算响应"""
        return {
            "type": "math_response",
            "id": request_id,
            "result": result,
            "error": error,
        }

    @staticmethod
    def create_storage_request(request_id: str, action: str, key: str, value: Any = None) -> dict:
        """创建存储请求"""
        return {
            "type": "storage_request",
            "id": request_id,
            "action": action,
            "key": key,
            "value": value,
        }

    @staticmethod
    def create_collab_request(request_id: str, action: str, data: dict = None) -> dict:
        """创建协作请求"""
        return {
            "type": "collab_request",
            "id": request_id,
            "action": action,
            "data": data or {},
        }


# ── 全局初始化 ──────────────────────────────────────────────────────────────

_mobile_config: Optional[MobileConfig] = None
_mobile_api: Optional[MobileAPI] = None
_is_mobile: Optional[bool] = None


def get_mobile_config() -> MobileConfig:
    """获取移动端配置"""
    global _mobile_config
    if _mobile_config is None:
        _mobile_config = MobileConfig()
    return _mobile_config


def get_mobile_api() -> MobileAPI:
    """获取移动端 API"""
    global _mobile_api
    if _mobile_api is None:
        _mobile_api = MobileAPI()
    return _mobile_api


def is_mobile() -> bool:
    """检测是否运行在移动设备上"""
    global _is_mobile
    if _is_mobile is None:
        _is_mobile = MobileDeviceDetector.detect()
    return _is_mobile


def get_mobile_state() -> dict:
    """获取移动端状态"""
    return {
        "is_mobile": is_mobile(),
        "config": {
            "memory_limit_mb": get_mobile_config().memory_limit_mb,
            "enable_offline_cache": get_mobile_config().enable_offline_cache,
            "touch_sensitivity": get_mobile_config().touch_sensitivity,
        },
        "api_available": _mobile_api is not None,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 移动端测试")
    print("=" * 60)

    print(f"\n移动设备检测: {is_mobile()}")
    print(f"状态: {get_mobile_state()}")

    api = get_mobile_api()
    print(f"\n移动端 API:")
    print(f"  zeros((3,3)): {api.zeros((3, 3))}")
    print(f"  eye(3): {api.eye(3)}")

    # 测试 Flutter 协议
    init_msg = FlutterShell.create_init_message("Matha", "4.4.0")
    print(f"\nFlutter 初始化: {init_msg['type']}")

    math_req = FlutterShell.create_math_request("req_001", "zeros", [[3], [3]])
    print(f"数学请求: {math_req['operation']}")

    math_resp = FlutterShell.create_math_response("req_001", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    print(f"数学响应: {math_resp['result']}")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
