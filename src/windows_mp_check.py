# -*- coding: utf-8 -*-
"""
Matha Windows Multiprocessing 检测与文档

KNP-007: Windows 下 multiprocessing spawn 模式限制
- Worker 函数必须定义在模块顶层
- 局部函数无法序列化

本模块提供检测工具。
"""
from __future__ import annotations
import inspect
import sys
import logging

logger = logging.getLogger("matha.windows_mp")


def check_spawn_compatible(func) -> dict:
    """检测函数是否符合 Windows spawn 模式要求。

    返回:
        {
            "compatible": bool,
            "reason": str,
            "warnings": list[str],
        }
    """
    result = {"compatible": True, "reason": "", "warnings": []}

    if not inspect.isfunction(func):
        result["compatible"] = False
        result["reason"] = "不是函数"
        return result

    # 检查是否定义在模块顶层
    module = inspect.getmodule(func)
    if module is None:
        result["compatible"] = False
        result["reason"] = "无法获取模块信息"
        return result

    # 检查是否是局部函数（在另一个函数内部定义）
    if func.__qualname__.count('.') > 0:
        result["compatible"] = False
        result["reason"] = f"局部函数 '{func.__qualname__}'，无法在 spawn 模式下序列化"
        result["warnings"].append(f"将 '{func.__name__}' 移到模块顶层")

    # 检查是否引用了闭包变量
    if func.__closure__:
        result["warnings"].append(f"函数 '{func.__name__}' 使用了闭包变量，spawn 模式下可能有问题")

    return result


def check_all_workers(module) -> dict:
    """检查模块中所有可能的 Worker 函数。

    返回所有不符合 spawn 兼容性的函数列表。
    """
    issues = []
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and name.startswith('_'):
            result = check_spawn_compatible(obj)
            if not result["compatible"]:
                issues.append({
                    "function": name,
                    "qualname": obj.__qualname__,
                    "reason": result["reason"],
                    "fix": result["warnings"][0] if result["warnings"] else "",
                })
    return {"total_checked": len(issues), "issues": issues}


def get_spawn_warnings() -> list[str]:
    """获取 Windows spawn 模式的通用警告信息。"""
    if sys.platform != 'win32':
        return []

    warnings = [
        "【KNP-007】Windows Multiprocessing 限制",
        "  - Worker 函数必须定义在模块顶层（不能用 lambda 或局部函数）",
        "  - 函数不能被嵌套定义",
        "  - 避免使用闭包变量",
        "  - 推荐：使用 ProcessPoolExecutor 的 map() 方法",
    ]
    return warnings
