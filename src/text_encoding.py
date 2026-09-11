# -*- coding: utf-8 -*-
"""Matha 文本编码模块：二进制 / 三进制 / 十进制 编解码。

将文本字符串编码为不同进制的数字序列表示，支持反向解码。
编码规则：每个字符的 Unicode 码点转为指定进制的字符串，字符间用空格分隔。

示例：
    >>> encode_binary("Hi")
    '1001000 1101001'
    >>> decode_binary('1001000 1101001')
    'Hi'
    >>> encode_ternary("Hi")
    '2012 2100'
    >>> decode_ternary('2012 2100')
    'Hi'
    >>> encode_decimal("Hi")
    '72 105'
    >>> decode_decimal('72 105')
    'Hi'
"""
from __future__ import annotations
from typing import Literal

Base = Literal[2, 3, 10]


# ============================================================
# 核心编码/解码
# ============================================================

def _encode(text: str, base: Base) -> str:
    """将文本编码为指定进制的数字序列（空格分隔）。"""
    if not text:
        return ""
    parts = []
    for ch in text:
        code = ord(ch)
        parts.append(_int_to_base(code, base))
    return " ".join(parts)


def _decode(encoded: str, base: Base) -> str:
    """将指定进制的数字序列解码为文本。"""
    if not encoded.strip():
        return ""
    chars = []
    for token in encoded.strip().split():
        code = _base_to_int(token, base)
        chars.append(chr(code))
    return "".join(chars)


def _int_to_base(n: int, base: Base) -> str:
    """正整数转指定进制字符串。"""
    if n == 0:
        return "0"
    digits = []
    while n > 0:
        digits.append(str(n % base))
        n //= base
    return "".join(reversed(digits))


def _base_to_int(s: str, base: Base) -> int:
    """指定进制字符串转整数。"""
    result = 0
    for ch in s:
        digit = int(ch)
        if digit >= base:
            raise ValueError(f"数字 {digit} 超出进制 {base} 的范围")
        result = result * base + digit
    return result


# ============================================================
# 公开 API
# ============================================================

def encode_binary(text: str) -> str:
    """文本 → 二进制编码（base-2）。"""
    return _encode(text, 2)


def decode_binary(encoded: str) -> str:
    """二进制编码 → 文本。"""
    return _decode(encoded, 2)


def encode_ternary(text: str) -> str:
    """文本 → 三进制编码（base-3）。"""
    return _encode(text, 3)


def decode_ternary(encoded: str) -> str:
    """三进制编码 → 文本。"""
    return _decode(encoded, 3)


def encode_decimal(text: str) -> str:
    """文本 → 十进制编码（base-10，即 Unicode 码点序列）。"""
    return _encode(text, 10)


def decode_decimal(encoded: str) -> str:
    """十进制编码 → 文本。"""
    return _decode(encoded, 10)


def encode(text: str, base: Base = 10) -> str:
    """通用编码：指定进制。"""
    if base not in (2, 3, 10):
        raise ValueError(f"不支持的进制 {base}，仅支持 2、3、10")
    return _encode(text, base)


def decode(encoded: str, base: Base = 10) -> str:
    """通用解码：指定进制。"""
    if base not in (2, 3, 10):
        raise ValueError(f"不支持的进制 {base}，仅支持 2、3、10")
    return _decode(encoded, base)


# ============================================================
# 工具函数
# ============================================================

def detect_base(encoded: str) -> Base | None:
    """尝试自动检测编码进制（根据出现的最大数字）。

    返回 2、3 或 10；无法确定时返回 None。
    """
    tokens = encoded.strip().split()
    if not tokens:
        return None
    max_digit = 0
    for token in tokens:
        for ch in token:
            if ch.isdigit():
                max_digit = max(max_digit, int(ch))
    if max_digit <= 1:
        return 2
    elif max_digit == 2:
        return 3
    else:
        return 10


def encode_file(input_path: str, output_path: str, base: Base = 10) -> None:
    """读取文本文件，编码后写入输出文件。"""
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    encoded = _encode(text, base)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(encoded)


def decode_file(input_path: str, output_path: str, base: Base = 10) -> None:
    """读取编码文件，解码后写入输出文件。"""
    with open(input_path, "r", encoding="utf-8") as f:
        encoded = f.read()
    text = _decode(encoded, base)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m src.text_encoding encode <text> [base=2|3|10]")
        print("  python -m src.text_encoding decode <encoded> [base=2|3|10]")
        print("  python -m src.text_encoding demo")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "demo":
        text = "Matha 你好"
        print(f"原文: {text}")
        print(f"二进制: {encode_binary(text)}")
        print(f"三进制: {encode_ternary(text)}")
        print(f"十进制: {encode_decimal(text)}")
        print()
        print(f"二进制解码: {decode_binary(encode_binary(text))}")
        print(f"三进制解码: {decode_ternary(encode_ternary(text))}")
        print(f"十进制解码: {decode_decimal(encode_decimal(text))}")
    elif cmd == "encode":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        base = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(encode(text, base))  # type: ignore[arg-type]
    elif cmd == "decode":
        encoded = sys.argv[2] if len(sys.argv) > 2 else ""
        base = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(decode(encoded, base))  # type: ignore[arg-type]
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
