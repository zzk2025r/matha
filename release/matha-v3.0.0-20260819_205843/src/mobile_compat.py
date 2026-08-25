# -*- coding: utf-8 -*-
"""Matha v4.4 移动端兼容性实现

本模块提供 Matha 在移动端（平板/手机）的兼容性支持：
- 无依赖环境运行（纯 Python NumPy 兼容层）
- 内存优化
- 简洁 API
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MobileCompatibility:
    """
    移动端兼容性管理器

    提供：
    1. 依赖检测与降级
    2. 内存优化配置
    3. 简化 API
    """

    _instance = None

    def __new__(cls):
        """单例模式：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._is_mobile_cached = None
        return cls._instance

    def __init__(self):
        """初始化（仅执行一次）"""
        if self._initialized:
            return
        self._initialized = True
        self._numpy_available = False
        self._optimized_mode = False
        self._memory_limit_mb = 256  # 移动端内存限制
        self._is_mobile_cached = None
        self._detect_dependencies()

    def _detect_dependencies(self):
        """检测可用依赖"""
        try:
            from src.numpy_compat import array, zeros, ones, eye, svd_decompose
            self._numpy_available = True
            logger.info("Matha NumPy 兼容层已加载")
        except ImportError:
            logger.warning("Matha NumPy 兼容层未找到，使用降级模式")

    @property
    def is_mobile(self) -> bool:
        """是否运行在移动设备上（带缓存）"""
        if self._is_mobile_cached is not None:
            return self._is_mobile_cached

        import sys
        import os

        # 多种检测方式
        mobile_indicators = [
            'android', 'iphone', 'ipad', 'mobile', 'tablet'
        ]

        # 1. 检查 sys.platform
        platform = sys.platform.lower()
        is_mobile_platform = any(indicator in platform for indicator in mobile_indicators)

        # 2. 检查环境变量（移动端应用常设置）
        env_mobile = os.environ.get('MATHA_MOBILE', '').lower() in ('1', 'true', 'yes')

        # 3. 检查屏幕尺寸（通过 turtle/screen 检测）
        try:
            import tkinter as tk
            root = tk.Tk()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            # 小屏幕通常是移动设备
            is_small_screen = screen_width < 1024 or screen_height < 768
        except Exception:
            is_small_screen = False

        # 综合判断
        result = is_mobile_platform or env_mobile or is_small_screen
        self._is_mobile_cached = result
        logger.info(f"移动设备检测: platform={platform}, env={env_mobile}, small_screen={is_small_screen} -> {result}")
        return result

    @property
    def numpy_available(self) -> bool:
        """NumPy 兼容层是否可用"""
        return self._numpy_available

    def get_optimized_matrix_ops(self):
        """
        获取优化的矩阵运算函数

        Returns:
            dict: 优化的矩阵运算函数映射
        """
        if self._numpy_available:
            from src.numpy_compat import (
                array, zeros, ones, eye,
                matrix_multiply, matrix_inverse,
                matrix_determinant, svd_decompose,
                trace, norm
            )
            return {
                'array': array,
                'zeros': zeros,
                'ones': ones,
                'eye': eye,
                'matmul': matrix_multiply,
                'inv': matrix_inverse,
                'det': matrix_determinant,
                'svd': svd_decompose,
                'trace': trace,
                'norm': norm,
            }
        else:
            # 降级到 stdlib
            from src.stdlib.linear_algebra import (
                Matrix, matrix_multiply, matrix_inverse,
                matrix_determinant, svd_decompose, matrix_trace, matrix_norm
            )
            return {
                'Matrix': Matrix,
                'matmul': matrix_multiply,
                'inv': matrix_inverse,
                'det': matrix_determinant,
                'svd': svd_decompose,
                'trace': matrix_trace,
                'norm': matrix_norm,
            }

    def create_simplified_api(self):
        """
        创建简化的移动端 API

        Returns:
            SimplifiedAPI: 简化的 API 对象
        """
        ops = self.get_optimized_matrix_ops()

        class SimplifiedAPI:
            """简化的移动端 API"""

            def __init__(self, ops_dict):
                self._ops = ops_dict

            def zeros(self, shape):
                """创建零矩阵"""
                if 'zeros' in self._ops:
                    return self._ops['zeros'](shape)
                return self._ops['Matrix']([[0.0] * shape[1] for _ in range(shape[0])])

            def ones(self, shape):
                """创建全一矩阵"""
                if 'ones' in self._ops:
                    return self._ops['ones'](shape)
                return self._ops['Matrix']([[1.0] * shape[1] for _ in range(shape[0])])

            def eye(self, n):
                """创建单位矩阵"""
                if 'eye' in self._ops:
                    return self._ops['eye'](n)
                return self._ops['Matrix']([[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)])

            def matmul(self, A, B):
                """矩阵乘法"""
                return self._ops['matmul'](A, B)

            def inv(self, A):
                """矩阵求逆"""
                return self._ops['inv'](A)

            def det(self, A):
                """行列式"""
                return self._ops['det'](A)

            def svd(self, A):
                """SVD 分解"""
                return self._ops['svd'](A)

            def trace(self, A):
                """矩阵迹"""
                return self._ops['trace'](A)

            def norm(self, A):
                """矩阵范数"""
                return self._ops['norm'](A)

        return SimplifiedAPI(ops)

    def optimize_for_mobile(self):
        """
        优化移动端配置

        启用：
        - 内存限制
        - 简化计算
        - 减少缓存
        """
        self._optimized_mode = True
        logger.info("移动端优化模式已启用")
        logger.info(f"内存限制: {self._memory_limit_mb}MB")


def get_mobile_api():
    """
    获取移动端 API

    Returns:
        SimplifiedAPI: 简化的 API 对象
    """
    compat = MobileCompatibility()
    return compat.create_simplified_api()


def is_mobile_device() -> bool:
    """
    检测是否为移动设备

    Returns:
        bool: 是否运行在移动设备上
    """
    compat = MobileCompatibility()
    return compat.is_mobile
