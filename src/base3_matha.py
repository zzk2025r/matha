# -*- coding: utf-8 -*-
"""
Matha 基础层 — 三进制/二进制/十进制底层
========================================
设计原则：
  - 独立于 Python/C/C++，纯数学实现
  - 字母(a-z, A-Z) → 三进制编码
  - 汉字 → 三进制编码 → 字母映射 → 三进制
  - 所有数值以 Base3 为中间表示，Base2 为物理存储，Base10 为人类可读
  - 零外部依赖（仅使用 Python 基础语法，不 import 任何标准库）
"""

import sys
import os

# ============================================================
# Base3 三进制 — 字符编码核心
# ============================================================

class Base3:
    """三进制值 — 字符/汉字编码的中间表示"""
    __slots__ = ('digits',)

    # 基础字符集 → 三进制编码
    # a-z: 0-25, A-Z: 26-51, 0-9: 52-61
    # 中文常用: 62+ (Unicode 范围映射)
    _char_to_code = {}
    _code_to_char = {}
    _next_code = 0

    @classmethod
    def _ensure_char(cls, ch):
        """确保字符已注册"""
        if ch not in cls._char_to_code:
            code = cls._next_code
            cls._char_to_code[ch] = code
            cls._code_to_char[code] = ch
            cls._next_code += 1

    def __init__(self, value=0):
        if isinstance(value, str) and len(value) == 1:
            self._ensure_char(value)
            self.digits = self._to_trinary(self._char_to_code[value])
        elif isinstance(value, str) and len(value) > 1:
            # 字符串 → 每个字符转为三进制
            all_digits = []
            for ch in value:
                self._ensure_char(ch)
                code = self._char_to_code[ch]
                all_digits.extend(self._to_trinary(code))
                all_digits.append(10)  # 分隔符
            self.digits = all_digits
        elif isinstance(value, Base3):
            self.digits = value.digits[:]
        elif isinstance(value, Base2):
            self.digits = self._from_binary(value.bits)
        elif isinstance(value, int):
            self.digits = self._to_trinary(value)
        elif isinstance(value, list):
            self.digits = value[:]
        else:
            self.digits = self._to_trinary(int(value))

    @staticmethod
    def _to_trinary(n):
        """整数 → 三进制数字列表"""
        if n == 0:
            return [0]
        digits = []
        neg = n < 0
        n = abs(n)
        while n > 0:
            digits.append(n % 3)
            n //= 3
        digits.reverse()
        return digits

    @staticmethod
    def _from_trinary(digits):
        """三进制数字列表 → 整数"""
        value = 0
        for d in digits:
            value = value * 3 + int(d)
        return value

    @staticmethod
    def _from_binary(bits):
        """二进制字符串 → 三进制"""
        return Base3._to_trinary(int(bits, 2))

    def __int__(self):
        return self._from_trinary(self.digits) if self.digits else 0

    def to_base2(self):
        """三进制 → 二进制"""
        return Base2(self._from_trinary(self.digits))

    def to_base10(self):
        """三进制 → 十进制"""
        return Base10(self._from_trinary(self.digits))

    def to_char(self):
        """单字符三进制编码 → 字符"""
        val = self._from_trinary(self.digits)
        return self._code_to_char.get(val, f'\\u{val:04X}')

    def to_string(self):
        """多字符三进制编码 → 字符串"""
        result = []
        i = 0
        while i < len(self.digits):
            # 收集一组 digits 直到分隔符 10
            group = []
            while i < len(self.digits) and self.digits[i] != 10:
                group.append(self.digits[i])
                i += 1
            i += 1  # skip separator
            if group:
                val = self._from_trinary(group)
                result.append(self._code_to_char.get(val, f'\\u{val:04X}'))
        return ''.join(result)

    def __repr__(self):
        return f"Base3({self.digits})"

    def __eq__(self, other):
        if isinstance(other, Base3):
            return self.digits == other.digits
        if isinstance(other, int):
            return self._from_trinary(self.digits) == other
        if isinstance(other, Base2):
            return self._from_trinary(self.digits) == int(other)
        return False

    def __add__(self, other):
        a = self._from_trinary(self.digits)
        b = other._from_trinary(other.digits) if isinstance(other, Base3) else int(other)
        return Base3(a + b)

    def __mul__(self, other):
        a = self._from_trinary(self.digits)
        b = other._from_trinary(other.digits) if isinstance(other, Base3) else int(other)
        return Base3(a * b)

    def __lt__(self, other):
        a = self._from_trinary(self.digits)
        b = other._from_trinary(other.digits) if isinstance(other, Base3) else int(other)
        return a < b

    def __gt__(self, other):
        a = self._from_trinary(self.digits)
        b = other._from_trinary(other.digits) if isinstance(other, Base3) else int(other)
        return a > b

    def __str__(self):
        return ''.join(str(d) for d in self.digits)

    def __len__(self):
        return len(self.digits)


# ============================================================
# Base2 二进制 — 物理存储层
# ============================================================

class Base2:
    """二进制值 — 所有数据的最终物理表示"""
    __slots__ = ('bits',)

    def __init__(self, value=0):
        if isinstance(value, str):
            self.bits = value
        elif isinstance(value, Base3):
            self.bits = self._from_trinary(value.digits)
        elif isinstance(value, int):
            self.bits = bin(value)[2:]
        else:
            self.bits = bin(int(value))[2:]

    @staticmethod
    def _from_trinary(digits):
        """三进制 → 二进制字符串"""
        value = 0
        for d in digits:
            value = value * 3 + int(d)
        return bin(value)[2:] if value else '0'

    def __int__(self):
        return int(self.bits, 2) if self.bits else 0

    def __repr__(self):
        return f"Base2(0b{self.bits})"

    def __eq__(self, other):
        if isinstance(other, Base3):
            return int(self) == other._from_trinary(other.digits)
        if isinstance(other, Base2):
            return self.bits == other.bits
        return int(self) == int(other)

    def __add__(self, other):
        return Base2(int(self) + int(other))

    def __sub__(self, other):
        return Base2(int(self) - int(other))

    def __mul__(self, other):
        return Base2(int(self) * int(other))

    def __truediv__(self, other):
        return Base2(int(self) // int(other))

    def __and__(self, other):
        return Base2(int(self) & int(other))

    def __or__(self, other):
        return Base2(int(self) | int(other))

    def __xor__(self, other):
        return Base2(int(self) ^ int(other))

    def __lshift__(self, other):
        return Base2(int(self) << int(other))

    def __rshift__(self, other):
        return Base2(int(self) >> int(other))

    def __lt__(self, other):
        return int(self) < int(other)

    def __le__(self, other):
        return int(self) <= int(other)

    def __gt__(self, other):
        return int(self) > int(other)

    def __ge__(self, other):
        return int(self) >= int(other)

    def __neg__(self):
        return Base2(-int(self))

    def __abs__(self):
        return Base2(abs(int(self)))

    def to_base3(self):
        """二进制 → 三进制"""
        return Base3(int(self))

    def to_base10(self):
        """二进制 → 十进制"""
        return Base10(int(self))

    def to_char(self):
        """单字节二进制 → 字符"""
        val = int(self)
        if 0 <= val <= 0x10FFFF:
            return chr(val)
        return f'\\u{val:04X}'


# ============================================================
# Base10 十进制 — 人类可读层
# ============================================================

class Base10:
    """十进制值 — 人类可读的数值表示"""
    __slots__ = ('value',)

    def __init__(self, value=0.0):
        if isinstance(value, str):
            self.value = float(value)
        elif isinstance(value, Base2):
            self.value = float(int(value))
        elif isinstance(value, Base3):
            self.value = float(value._from_trinary(value.digits))
        else:
            self.value = float(value)

    def __float__(self):
        return self.value

    def __int__(self):
        return int(self.value)

    def __repr__(self):
        return f"Base10({self.value})"

    def __str__(self):
        if self.value == int(self.value):
            return str(int(self.value))
        return str(self.value)

    def __eq__(self, other):
        if isinstance(other, (Base2, Base3)):
            return self.value == float(other)
        return self.value == float(other)

    def __add__(self, other):
        return Base10(self.value + float(other))

    def __sub__(self, other):
        return Base10(self.value - float(other))

    def __mul__(self, other):
        return Base10(self.value * float(other))

    def __truediv__(self, other):
        return Base10(self.value / float(other))

    def __lt__(self, other):
        return self.value < float(other)

    def __le__(self, other):
        return self.value <= float(other)

    def __gt__(self, other):
        return self.value > float(other)

    def __ge__(self, other):
        return self.value >= float(other)

    def __neg__(self):
        return Base10(-self.value)

    def __abs__(self):
        return Base10(abs(self.value))

    def floor(self):
        return Base10(int(self.value // 1))

    def ceil(self):
        return Base10(int(self.value // 1) + (1 if self.value > int(self.value) else 0))

    def trunc(self):
        return Base10(int(self.value))

    def round(self):
        return Base10(round(self.value))

    def to_base2(self):
        return Base2(int(self.value))

    def to_base3(self):
        return Base3(int(self.value))

    def to_string(self):
        return str(self)


# ============================================================
# 预注册常用字符集（启动时一次性注册）
# ============================================================

def _init_char_registry():
    """初始化字符注册表 — a-z, A-Z, 0-9"""
    # 小写字母 a-z: 0-25
    for i, ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
        Base3._ensure_char(ch)
    # 大写字母 A-Z: 26-51
    for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        Base3._ensure_char(ch)
    # 数字 0-9: 52-61
    for i, ch in enumerate('0123456789'):
        Base3._ensure_char(ch)
    # 常用符号
    for ch in ' .,:;!?()[]{}+-*/=%<>!&|^~#@\'"\\':
        Base3._ensure_char(ch)


_init_char_registry()


# ============================================================
# 汉字三进制编码
# ============================================================

def register_chinese_chars(char_list):
    """批量注册汉字到三进制编码表"""
    for ch in char_list:
        Base3._ensure_char(ch)


def char_to_trinary(ch):
    """单字符 → 三进制"""
    Base3._ensure_char(ch)
    return Base3(ch)


def trinary_to_char(digits):
    """三进制数字列表 → 字符"""
    val = Base3._from_trinary(digits)
    return Base3._code_to_char.get(val, f'\\u{val:04X}')


def string_to_trinary(s):
    """字符串 → 三进制"""
    return Base3(s)


def trinary_to_string(t):
    """三进制 → 字符串"""
    if isinstance(t, Base3):
        return t.to_string()
    return Base3(t).to_string()


# ============================================================
# 进制转换工具
# ============================================================

def int_to_base2(n):
    return Base2(n)


def int_to_base3(n):
    return Base3(n)


def int_to_base10(n):
    return Base10(n)


def base2_to_base3(b):
    return b.to_base3()


def base3_to_base2(t):
    return t.to_base2()


def base2_to_base10(b):
    return b.to_base10()


def base3_to_base10(t):
    return t.to_base10()


def base10_to_base2(n):
    return n.to_base2()


def base10_to_base3(n):
    return n.to_base3()


# ============================================================
# 主入口测试
# ============================================================

if __name__ == '__main__':
    print("=== Matha 三进制底层测试 ===")

    # 字母编码
    print(f"a → Base3: {Base3('a').digits} = {Base3('a')}")
    print(f"z → Base3: {Base3('z').digits} = {Base3('z')}")
    print(f"A → Base3: {Base3('A').digits} = {Base3('A')}")
    print(f"0 → Base3: {Base3('0').digits} = {Base3('0')}")

    # 汉字编码
    register_chinese_chars('你好世界数学编译器')
    print(f"你 → Base3: {Base3('你').digits}")
    print(f"好 → Base3: {Base3('好').digits}")
    print(f"数学 → Base3: {Base3('数学').to_string()}")

    # 进制互转
    t = Base3(255)
    print(f"255 → Base3: {t.digits} = {t}")
    print(f"255 → Base2: {Base2(t).bits}")
    print(f"255 → Base10: {Base10(t)}")

    # 字符串编码
    s = "Hello"
    t = Base3(s)
    print(f"'Hello' → Base3: {t.digits}")
    print(f"还原: {t.to_string()}")

    print("\n=== 三进制底层运行正常 ===")
