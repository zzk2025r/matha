# -*- coding: utf-8 -*-
"""Matha v4.4 — 性能日志增强模块

本模块为线性代数核心函数添加详细的日志输出，方便调试和性能分析。
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def log_matrix_operation(func):
    """
    装饰器：为矩阵运算添加日志。

    用法:
        @log_matrix_operation
        def matrix_multiply(A, B):
            ...
    """
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        logger.info(f"开始矩阵运算: {func.__name__}")

        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_time) * 1000

            if hasattr(result, 'shape'):
                logger.info(f"矩阵运算完成: {func.__name__}, 耗时={elapsed:.2f}ms, 结果形状={result.shape}")
            else:
                logger.info(f"矩阵运算完成: {func.__name__}, 耗时={elapsed:.2f}ms")

            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(f"矩阵运算失败: {func.__name__}, 耗时={elapsed:.2f}ms, 错误={e}")
            raise
    return wrapper


def log_svd_operation(func):
    """
    装饰器：为 SVD 分解添加日志。

    用法:
        @log_svd_operation
        def svd_decompose(A):
            ...
    """
    def wrapper(*args, **kwargs):
        A = args[0] if args else kwargs.get('A')
        start_time = time.perf_counter()

        logger.info(f"开始 SVD 分解: 矩阵形状={A.shape if hasattr(A, 'shape') else 'unknown'}")

        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_time) * 1000

            if result and len(result) >= 3:
                U, S, Vt = result
                logger.info(f"SVD 分解完成: 耗时={elapsed:.2f}ms, U={U.shape}, S={S.shape}, Vt={Vt.shape}")
            else:
                logger.info(f"SVD 分解完成: 耗时={elapsed:.2f}ms")

            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(f"SVD 分解失败: 耗时={elapsed:.2f}ms, 错误={e}")
            raise
    return wrapper


def log_inverse_operation(func):
    """
    装饰器：为矩阵求逆添加日志。

    用法:
        @log_inverse_operation
        def matrix_inverse(A):
            ...
    """
    def wrapper(*args, **kwargs):
        A = args[0] if args else kwargs.get('A')
        start_time = time.perf_counter()

        logger.info(f"开始矩阵求逆: 矩阵形状={A.shape}")

        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_time) * 1000

            if result is not None:
                logger.info(f"矩阵求逆完成: 耗时={elapsed:.2f}ms, 结果形状={result.shape}")
            else:
                logger.warning(f"矩阵求逆失败: 矩阵奇异，无法求逆，耗时={elapsed:.2f}ms")

            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(f"矩阵求逆失败: 耗时={elapsed:.2f}ms, 错误={e}")
            raise
    return wrapper


def log_cache_operation(cache_name: str, cache: dict, key, result=None):
    """
    记录缓存操作日志。

    Args:
        cache_name: 缓存名称
        cache: 缓存字典
        key: 缓存键
        result: 缓存结果（可选）
    """
    if key in cache:
        logger.debug(f"缓存命中: {cache_name}, 缓存大小={len(cache)}")
    else:
        logger.debug(f"缓存未命中: {cache_name}, 缓存大小={len(cache)}")
        if result is not None:
            cache[key] = result
            logger.debug(f"缓存已更新: {cache_name}, 新缓存大小={len(cache)}")
