# -*- coding: utf-8 -*-
"""Matha 标准库 Core — v2.2

提供基础类型：Int, String, Bool, Array 的完整实现。
所有类型均支持 Matha 内建调用约定（函数式柯里化兼容）。
"""
from __future__ import annotations
import math
import statistics
from typing import Any, Optional


# ============================================================
# 类型注册接口
# ============================================================

def register_core_builtins(builtins: dict) -> None:
    """将 Core 标准库注册到 Matha 内建函数表。

    参数:
        builtins: 内建函数 dict，由 _build_domain_builtins 传入。
    """
    # ── Int ──────────────────────────────────────────────────────
    builtins["Int"] = lambda x: int(float(x))
    builtins["IsInt"] = lambda x: isinstance(x, int) or (isinstance(x, float) and x == int(x))
    builtins["IntMax"] = lambda a, b: max(int(a), int(b))
    builtins["IntMin"] = lambda a, b: min(int(a), int(b))
    builtins["IntAbs"] = lambda x: abs(int(x))
    builtins["IntDiv"] = lambda a, b: int(a) // int(b)
    builtins["IntMod"] = lambda a, b: int(a) % int(b)
    builtins["IntPow"] = lambda a, b: int(a) ** int(b)
    builtins["IntFromStr"] = lambda s: int(str(s))
    builtins["IntToRoman"] = _int_to_roman
    builtins["RomanToInt"] = _roman_to_int
    builtins["IntFactors"] = _int_factors
    builtins["IntIsPrime"] = _int_is_prime
    builtins["IntGCD"] = lambda a, b: math.gcd(int(a), int(b))
    builtins["IntLCM"] = lambda a, b: abs(int(a) * int(b)) // max(math.gcd(int(a), int(b)), 1)

    # ── String ───────────────────────────────────────────────────
    builtins["Str"] = lambda x: str(x)
    builtins["StrLen"] = lambda s: len(str(s))
    builtins["StrUpper"] = lambda s: str(s).upper()
    builtins["StrLower"] = lambda s: str(s).lower()
    builtins["StrTrim"] = lambda s: str(s).strip()
    builtins["StrSplit"] = lambda s, sep=" ": str(s).split(sep)
    builtins["StrJoin"] = lambda sep, items: sep.join(str(x) for x in items)
    builtins["StrContains"] = lambda substr, s: str(substr) in str(s)
    builtins["StrStartsWith"] = lambda prefix, s: str(s).startswith(str(prefix))
    builtins["StrEndsWith"] = lambda suffix, s: str(s).endswith(str(suffix))
    builtins["StrReplace"] = lambda old, new, s: str(s).replace(str(old), str(new))
    builtins["StrSlice"] = lambda s, start, end: str(s)[int(start):int(end)]
    builtins["StrReverse"] = lambda s: str(s)[::-1]
    builtins["StrRepeat"] = lambda s, n: str(s) * int(n)
    builtins["StrFormat"] = lambda fmt, *args: fmt.format(*args)
    builtins["StrPadLeft"] = _str_pad_left
    builtins["StrPadRight"] = _str_pad_right
    builtins["StrToInt"] = lambda s: int(float(str(s)))
    builtins["StrToFloat"] = lambda s: float(str(s))
    builtins["StrToBool"] = _str_to_bool
    builtins["StrChars"] = lambda s: list(str(s))
    builtins["StrWordCount"] = lambda s: len(str(s).split())
    builtins["StrLineCount"] = lambda s: len(str(s).splitlines())

    # ── Bool ─────────────────────────────────────────────────────
    builtins["Bool"] = lambda x: bool(x)
    builtins["BoolNot"] = lambda x: not bool(x)
    builtins["BoolAnd"] = lambda a, b: bool(a) and bool(b)
    builtins["BoolOr"] = lambda a, b: bool(a) or bool(b)
    builtins["BoolXor"] = lambda a, b: bool(a) != bool(b)
    builtins["BoolIf"] = lambda cond, then_val, else_val: then_val if bool(cond) else else_val
    builtins["IsTrue"] = lambda x: bool(x) is True
    builtins["IsFalse"] = lambda x: bool(x) is False

    # ── Array ────────────────────────────────────────────────────
    builtins["Array"] = lambda *args: list(args)
    builtins["ArrayNew"] = lambda size, initial=0: [initial] * int(size)
    builtins["ArrayLen"] = lambda arr: len(arr) if isinstance(arr, list) else len(str(arr))
    builtins["ArrayAppend"] = lambda arr, item: arr + [item] if isinstance(arr, list) else list(arr) + [item]
    builtins["ArrayPush"] = lambda arr, item: (arr.append(item), arr)[-1] if isinstance(arr, list) else None
    builtins["ArrayPop"] = lambda arr: arr.pop() if isinstance(arr, list) and arr else None
    builtins["ArrayGet"] = lambda arr, idx: arr[int(idx)] if isinstance(arr, list) and 0 <= int(idx) < len(arr) else None
    builtins["ArraySet"] = lambda arr, idx, val: (arr.__setitem__(int(idx), val), arr)[-1] if isinstance(arr, list) and 0 <= int(idx) < len(arr) else arr
    builtins["ArrayContains"] = lambda arr, item: item in arr if isinstance(arr, list) else False
    builtins["ArrayIndex"] = lambda arr, item: arr.index(item) if isinstance(arr, list) and item in arr else -1
    builtins["ArraySort"] = lambda arr: sorted(arr) if isinstance(arr, list) else arr
    builtins["ArrayReverse"] = lambda arr: list(reversed(arr)) if isinstance(arr, list) else arr
    builtins["ArraySum"] = lambda arr: sum(arr) if isinstance(arr, list) and all(isinstance(x, (int, float)) for x in arr) else 0
    builtins["ArrayAvg"] = lambda arr: statistics.mean(arr) if isinstance(arr, list) and arr else 0
    builtins["ArrayMin"] = lambda arr: min(arr) if isinstance(arr, list) and arr else None
    builtins["ArrayMax"] = lambda arr: max(arr) if isinstance(arr, list) and arr else None
    builtins["ArraySlice"] = lambda arr, start, end: arr[int(start):int(end)] if isinstance(arr, list) else []
    builtins["ArrayMap"] = lambda arr, fn: [fn(x) for x in arr] if isinstance(arr, list) else []
    builtins["ArrayFilter"] = lambda arr, fn: [x for x in arr if fn(x)] if isinstance(arr, list) else []
    builtins["ArrayReduce"] = lambda arr, fn, initial: _array_reduce(arr, fn, initial)
    builtins["ArrayFlatten"] = _array_flatten
    builtins["ArrayUnique"] = lambda arr: list(dict.fromkeys(arr)) if isinstance(arr, list) else arr
    builtins["ArrayRepeat"] = lambda item, n: [item] * int(n)
    builtins["ArrayRange"] = lambda start, end: list(range(int(start), int(end)))
    builtins["ArrayZip"] = lambda a, b: list(zip(a, b)) if isinstance(a, list) and isinstance(b, list) else []
    builtins["ArrayChunk"] = lambda arr, size: [arr[i:i+int(size)] for i in range(0, len(arr), int(size))] if isinstance(arr, list) else []
    builtins["ArrayFill"] = lambda size, val: [val] * int(size)
    builtins["ArrayFind"] = lambda arr, pred: next((x for x in arr if pred(x)), None) if isinstance(arr, list) else None
    builtins["ArrayEvery"] = lambda arr, pred: all(pred(x) for x in arr) if isinstance(arr, list) else True
    builtins["ArraySome"] = lambda arr, pred: any(pred(x) for x in arr) if isinstance(arr, list) else False

    # ── 数值工具（跨类型）─────────────────────────────────────────
    builtins["Round"] = lambda x, n=0: round(float(x), int(n))
    builtins["Ceil"] = lambda x: math.ceil(float(x))
    builtins["Floor"] = lambda x: math.floor(float(x))
    builtins["Sqrt"] = lambda x: math.sqrt(float(x))
    builtins["Abs"] = lambda x: abs(float(x))
    builtins["Max"] = lambda *args: max(float(a) for a in args)
    builtins["Min"] = lambda *args: min(float(a) for a in args)
    builtins["Clamp"] = lambda val, lo, hi: max(float(lo), min(float(hi), float(val)))
    builtins["Lerp"] = lambda a, b, t: float(a) + (float(b) - float(a)) * float(t)
    builtins["Percent"] = lambda part, total: (float(part) / float(total)) * 100 if float(total) != 0 else 0
    builtins["Average"] = lambda *args: sum(float(a) for a in args) / len(args) if args else 0


# ============================================================
# 辅助函数
# ============================================================

def _int_to_roman(n: int) -> str:
    """整数转罗马数字。"""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    n = int(n)
    result = ""
    for i in range(len(val)):
        while n >= val[i]:
            result += syms[i]
            n -= val[i]
    return result


def _roman_to_int(s: str) -> int:
    """罗马数字转整数。"""
    rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = str(s).upper()
    result = 0
    for i in range(len(s)):
        if i + 1 < len(s) and rom_val.get(s[i], 0) < rom_val.get(s[i+1], 0):
            result -= rom_val.get(s[i], 0)
        else:
            result += rom_val.get(s[i], 0)
    return result


def _int_factors(n: int) -> list:
    """返回 n 的所有正因数。"""
    n = abs(int(n))
    return [i for i in range(1, n + 1) if n % i == 0]


def _int_is_prime(n: int) -> bool:
    """判断 n 是否为素数。"""
    n = abs(int(n))
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def _str_pad_left(s: Any, width: int, char: str = " ") -> str:
    """左填充字符串。"""
    s = str(s)
    w = int(width)
    c = str(char)[0] if char else " "
    return s.rjust(w, c)


def _str_pad_right(s: Any, width: int, char: str = " ") -> str:
    """右填充字符串。"""
    s = str(s)
    w = int(width)
    c = str(char)[0] if char else " "
    return s.ljust(w, c)


def _str_to_bool(s: str) -> bool:
    """字符串转布尔。"""
    return str(s).lower() in ("true", "1", "yes", "是", "on")


def _array_reduce(arr: list, fn, initial: Any) -> Any:
    """数组归约。"""
    if not arr:
        return initial
    acc = initial if initial is not None else arr[0]
    start = 0 if initial is not None else 1
    for item in arr[start:]:
        acc = fn(acc, item)
    return acc


def _array_flatten(arr: list, depth: int = -1) -> list:
    """扁平化嵌套数组。"""
    result = []
    for item in arr:
        if isinstance(item, list) and (depth < 0 or depth > 0):
            result.extend(_array_flatten(item, depth - 1))
        else:
            result.append(item)
    return result


# ============================================================
# 运行时类型
# ============================================================

class MathaType:
    """Matha 运行时类型封装。"""

    @staticmethod
    def to_int(x: Any) -> int:
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        if isinstance(x, str):
            return int(float(x))
        return int(x) if x is not None else 0

    @staticmethod
    def to_float(x: Any) -> float:
        if isinstance(x, float):
            return x
        if isinstance(x, int):
            return float(x)
        if isinstance(x, str):
            return float(x)
        return float(x) if x is not None else 0.0

    @staticmethod
    def to_str(x: Any) -> str:
        if isinstance(x, str):
            return x
        if isinstance(x, bool):
            return "true" if x else "false"
        return str(x)

    @staticmethod
    def to_bool(x: Any) -> bool:
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return x != 0
        if isinstance(x, str):
            return x.lower() in ("true", "1", "yes", "是", "on")
        return bool(x)

    @staticmethod
    def to_array(x: Any) -> list:
        if isinstance(x, list):
            return x
        if isinstance(x, (int, float, str, bool)):
            return [x]
        return list(x) if hasattr(x, '__iter__') else [x]

    @staticmethod
    def coalesce(*args: Any) -> Any:
        """返回第一个非 None 值。"""
        for arg in args:
            if arg is not None:
                return arg
        return None
