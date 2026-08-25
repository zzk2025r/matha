"""Matha 二进制/三进制转译模块。

提供数值与二进制/三进制字符串的互相转换，以及二进制↔三进制互转。
支持 Matha 专属编码格式（带 Matha 标记的进制编码），可与传统格式互译。

转译方向：
    整数 ⇄ 二进制字符串（"1010"）
    整数 ⇄ 三进制字符串（"210"）
    二进制字符串 ⇄ 三进制字符串
    整数 ⇄ Matha 专属二进制/三进制编码（"M2:1010" / "M3:210"）

运行时：python -m src.binary_codec  # 自测
"""

# Matha 专属编码前缀标记（可与传统 0b/0x 格式区分）
MATHA_BINARY_PREFIX = "M2:"    # Matha 专属二进制
MATHA_TERNARY_PREFIX = "M3:"   # Matha 专属三进制


# ============================================================
# 基础转译：整数 ⇄ 二进制 / 三进制
# ============================================================

def to_binary(n: int) -> str:
    """整数转二进制字符串（无前缀）。

    10 → "1010"，0 → "0"，-5 → "-101"
    """
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    bits = []
    while n > 0:
        bits.append(str(n & 1))
        n >>= 1
    return sign + "".join(reversed(bits))


def from_binary(s: str) -> int:
    """二进制字符串转整数。

    "1010" → 10，支持空格分隔（"1010 0011" → 163）
    """
    s = s.strip().replace(" ", "")
    if not s:
        return 0
    sign = -1 if s.startswith("-") else 1
    if s[0] in "+-":
        s = s[1:]
    return sign * int(s, 2)


def to_ternary(n: int) -> str:
    """整数转三进制字符串（无前缀）。

    21 → "210"，0 → "0"，-5 → "-12"
    """
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    digits = []
    while n > 0:
        digits.append(str(n % 3))
        n //= 3
    return sign + "".join(reversed(digits))


def from_ternary(s: str) -> int:
    """三进制字符串转整数。

    "210" → 21，支持空格分隔
    """
    s = s.strip().replace(" ", "")
    if not s:
        return 0
    sign = -1 if s.startswith("-") else 1
    if s[0] in "+-":
        s = s[1:]
    return sign * int(s, 3)


# ============================================================
# 互转：二进制 ⇄ 三进制
# ============================================================

def binary_to_ternary(s: str) -> str:
    """二进制字符串转三进制字符串。

    "1010"(=10) → "101"(=10)  即 10 的三进制表示
    """
    return to_ternary(from_binary(s))


def ternary_to_binary(s: str) -> str:
    """三进制字符串转二进制字符串。

    "210"(=21) → "10101"(=21)
    """
    return to_binary(from_ternary(s))


# ============================================================
# Matha 专属编码（带前缀标记，可与传统格式互译）
# ============================================================

def to_matha_binary(n: int) -> str:
    """整数转 Matha 专属二进制编码。

    10 → "M2:1010"
    """
    return MATHA_BINARY_PREFIX + to_binary(n)


def to_matha_ternary(n: int) -> str:
    """整数转 Matha 专属三进制编码。

    21 → "M3:210"
    """
    return MATHA_TERNARY_PREFIX + to_ternary(n)


def from_matha_code(code: str) -> int:
    """Matha 专属编码转整数。

    "M2:1010" → 10，"M3:210" → 21
    无前缀时按十进制解析（兼容传统格式）。
    """
    code = code.strip()
    if code.startswith(MATHA_BINARY_PREFIX):
        return from_binary(code[len(MATHA_BINARY_PREFIX):])
    if code.startswith(MATHA_TERNARY_PREFIX):
        return from_ternary(code[len(MATHA_TERNARY_PREFIX):])
    # 兼容传统 0b/0t/0x 前缀
    if len(code) >= 3 and code[0] == "0":
        p = code[1].lower()
        if p == "b":
            return int(code[2:], 2)
        if p == "t":
            return int(code[2:], 3)
        if p == "x":
            return int(code[2:], 16)
    # 纯十进制
    return int(code, 10)


def matha_binary_to_ternary(code: str) -> str:
    """Matha 二进制编码转三进制编码。

    "M2:1010" → "M3:101"
    """
    return to_matha_ternary(from_matha_code(code))


def matha_ternary_to_binary(code: str) -> str:
    """Matha 三进制编码转二进制编码。

    "M3:210" → "M2:10101"
    """
    return to_matha_binary(from_matha_code(code))


def encode(n: int, radix: str = "matha-binary") -> str:
    """便捷编码入口。

    radix: "matha-binary" / "matha-ternary" / "binary" / "ternary"
    """
    if radix == "matha-binary":
        return to_matha_binary(n)
    if radix == "matha-ternary":
        return to_matha_ternary(n)
    if radix == "binary":
        return to_binary(n)
    if radix == "ternary":
        return to_ternary(n)
    raise ValueError(f"未知进制: {radix}")


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print("=== binary_codec 自测 ===")
    # 基础转译
    assert to_binary(10) == "1010"
    assert from_binary("1010") == 10
    assert to_ternary(21) == "210"
    assert from_ternary("210") == 21
    assert to_binary(0) == "0"
    assert to_ternary(0) == "0"
    # 互转
    assert binary_to_ternary("1010") == "101"   # 10 → 三进制 101
    assert ternary_to_binary("210") == "10101"  # 21 → 二进制 10101
    # Matha 专属编码
    assert to_matha_binary(10) == "M2:1010"
    assert to_matha_ternary(21) == "M3:210"
    assert from_matha_code("M2:1010") == 10
    assert from_matha_code("M3:210") == 21
    assert matha_binary_to_ternary("M2:1010") == "M3:101"
    assert matha_ternary_to_binary("M3:210") == "M2:10101"
    # 兼容传统格式
    assert from_matha_code("0b1010") == 10
    assert from_matha_code("0t210") == 21
    assert from_matha_code("255") == 255
    print("  ✓ 全部转译断言通过")
    # 示例
    print(f"  示例: 42 → 二进制 {to_binary(42)} → 三进制 {to_ternary(42)}")
    print(f"  示例: 42 → {to_matha_binary(42)} ↔ {to_matha_ternary(42)}")
