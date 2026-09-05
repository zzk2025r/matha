# -*- coding: utf-8 -*-
"""安全除法工具

统一除零防护：当分母为零时返回 inf 或 0.0（由 caller 指定），
避免各 domain 模块重复写防御逻辑。
"""
from __future__ import annotations
import math


def safe_div(a: float, b: float, default: float = float('inf')) -> float:
    """安全除法：b==0 时返回 default，否则返回 a/b。"""
    if b == 0:
        return default
    return a / b


def safe_sqrt(x: float, default: float = 0.0) -> float:
    """安全平方根：x<0 时返回 default。"""
    if x < 0:
        return default
    return math.sqrt(x)


def safe_log(x: float, default: float = 0.0) -> float:
    """安全对数：x<=0 时返回 default。"""
    if x <= 0:
        return default
    return math.log(x)


def safe_asin(x: float, default: float = 0.0) -> float:
    """安全反正弦：|x|>1 时返回 default。"""
    if abs(x) > 1:
        return default
    return math.asin(x)
