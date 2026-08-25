# -*- coding: utf-8 -*-
"""Matha 数字版权领域模块：水印技术、区块链存证、访问控制。

覆盖：
  1) 水印嵌入强度
  2) 版权保护指数
  3) 访问控制粒度
  4) 哈希碰撞概率
  5) 密钥轮换周期
  6) 数字指纹
"""

from __future__ import annotations
import math
import hashlib


def _curry1(func):
    def with_first(a): return func(a)
    return with_first

def _curry2(func):
    def with_first(a): return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b): return lambda c: func(a, b, c)
        return w2
    return w1


def _水印嵌入强度(载体大小_bytes, 水印比特数, 嵌入密度):
    """水印嵌入强度评估。"""
    if 载体大小_bytes <= 0:
        return 0.0
    return min(100.0, 水印比特数 / 载体大小_bytes * 8 * 嵌入密度 * 100)


def _版权保护指数(存证数, 验证通过率, 篡改检测数):
    """版权保护综合指数（0-100）。"""
    if 存证数 <= 0:
        return 0.0
    存证分 = min(40, 存证数 / 10)
    验证分 = 验证通过率 * 35
    检测分 = min(25, 篡改检测数 * 5)
    return 存证分 + 验证分 + 检测分


def _访问控制粒度(角色数, 权限数, 策略数):
    """访问控制粒度评估。"""
    if 角色数 <= 0:
        return 0.0
    return 权限数 / 角色数 * 策略数


def _哈希碰撞概率(哈希位数, 数据量):
    """生日攻击碰撞概率估算。P ≈ n² / 2^（b+1）。"""
    if 哈希位数 <= 0:
        return 0.0
    return min(1.0, (数据量 ** 2) / (2 ** (哈希位数 + 1)))


def _密钥轮换周期(密钥长度_bit, 计算能力_次秒):
    """密钥安全轮换周期（天）。"""
    if 计算能力_次秒 <= 0:
        return 0
    brute_force_sec = 2 ** 密钥长度_bit / 计算能力_次秒
    return max(1, int(brute_force_sec / 86400))


def _数字指纹(数据):
    """生成数据的SHA-256指纹（十六进制前16位）。"""
    if not 数据:
        return ""
    h = hashlib.sha256(数据.encode() if isinstance(数据, str) else 数据).hexdigest()
    return h[:16]


# ============================================================
# 注册
# ============================================================

def _register_digital_rights(builtins: dict) -> None:
    builtins["水印嵌入强度"] = _curry3(_水印嵌入强度)
    builtins["版权保护指数"] = _curry3(_版权保护指数)
    builtins["访问控制粒度"] = _curry3(_访问控制粒度)
    builtins["哈希碰撞概率"] = _curry2(_哈希碰撞概率)
    builtins["密钥轮换周期"] = _curry2(_密钥轮换周期)
    builtins["数字指纹"] = _curry1(_数字指纹)


def _digital_rights_symtab_names() -> list[str]:
    return ["水印嵌入强度", "版权保护指数", "访问控制粒度",
            "哈希碰撞概率", "密钥轮换周期", "数字指纹"]


__all__ = [
    "水印嵌入强度", "版权保护指数", "访问控制粒度",
    "哈希碰撞概率", "密钥轮换周期", "数字指纹",
    "_register_digital_rights", "_digital_rights_symtab_names",
]
