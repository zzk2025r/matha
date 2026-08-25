# -*- coding: utf-8 -*-
"""Matha v4.4 异常处理优化模块

本模块提供统一的异常处理工具和最佳实践。
"""
from __future__ import annotations
import logging
from typing import Callable, Type, Any, Optional
from contextlib import contextmanager
import functools

logger = logging.getLogger(__name__)


class MathaError(Exception):
    """Matha 基础异常类。"""
    pass


class MatrixError(MathaError):
    """矩阵运算异常。"""
    pass


class DimensionMismatchError(MatrixError):
    """矩阵维度不匹配异常。"""
    pass


class SingularMatrixError(MatrixError):
    """奇异矩阵异常。"""
    pass


class SymbolicError(MathaError):
    """符号计算异常。"""
    pass


class ImportError(MathaError):
    """导入异常。"""
    pass


class ConfigurationError(MathaError):
    """配置异常。"""
    pass


@contextmanager
def safe_execute(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """
    安全执行函数，捕获并记录异常。

    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数

    Yields:
        函数返回值

    Raises:
        重新抛出异常（记录后）
    """
    try:
        yield func(*args, **kwargs)
    except (ValueError, TypeError) as e:
        logger.error(f"数据类型错误: {e}")
        raise
    except ImportError as e:
        logger.warning(f"导入失败: {e}")
        raise
    except MatrixError as e:
        logger.error(f"矩阵错误: {e}")
        raise
    except SymbolicError as e:
        logger.error(f"符号计算错误: {e}")
        raise
    except Exception as e:
        logger.error(f"未知错误: {e}")
        raise


def with_error_handling(func: Callable) -> Callable:
    """
    装饰器：为函数添加错误处理。

    用法:
        @with_error_handling
        def my_function(x):
            return x ** 2
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, TypeError) as e:
            logger.error(f"{func.__name__}: 数据类型错误 - {e}")
            raise
        except ImportError as e:
            logger.warning(f"{func.__name__}: 导入失败 - {e}")
            raise
        except Exception as e:
            logger.error(f"{func.__name__}: 未知错误 - {e}")
            raise
    return wrapper


def validate_matrix_shape(rows: int, cols: int) -> None:
    """
    验证矩阵维度。

    Args:
        rows: 行数
        cols: 列数

    Raises:
        ValueError: 维度无效
    """
    if not isinstance(rows, int) or not isinstance(cols, int):
        raise TypeError(f"矩阵维度必须为整数，收到: rows={type(rows)}, cols={type(cols)}")
    if rows <= 0 or cols <= 0:
        raise ValueError(f"矩阵维度必须为正整数，收到: rows={rows}, cols={cols}")


def validate_numeric(value: Any, name: str = "value") -> None:
    """
    验证数值类型。

    Args:
        value: 要验证的值
        name: 参数名称（用于错误消息）

    Raises:
        TypeError: 类型错误
    """
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} 必须是数值类型，收到: {type(value).__name__}")


def check_dependency(module_name: str, feature: str) -> bool:
    """
    检查依赖是否可用。

    Args:
        module_name: 模块名称
        feature: 功能描述

    Returns:
        是否可用
    """
    try:
        __import__(module_name)
        return True
    except ImportError as e:
        logger.warning(f"{feature} 需要 {module_name}: {e}")
        return False
