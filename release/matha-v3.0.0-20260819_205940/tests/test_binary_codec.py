"""Matha 二进制/三进制转译与字面量测试。

验证三层能力：
  1. 进制字面量解析（lexer 0b/0t/0x 前缀 → parser 转 int）
  2. 基础转译（整数 ⇄ 二进制/三进制）
  3. 互转（二进制 ⇄ 三进制）
  4. Matha 专属编码（M2:/M3: 前缀，可与传统格式互译）
  5. Matha 代码中使用进制字面量

运行：python -m tests.test_binary_codec
"""

from src.parser import parse
from src.semantic import analyze_source
from src import ast_nodes as ast
from src.binary_codec import (
    to_binary, from_binary, to_ternary, from_ternary,
    binary_to_ternary, ternary_to_binary,
    to_matha_binary, to_matha_ternary, from_matha_code,
    matha_binary_to_ternary, matha_ternary_to_binary,
)


def _find_int_lit(node, results):
    """递归找 IntegerLit。"""
    if isinstance(node, ast.IntegerLit):
        results.append(node)
    if hasattr(node, "__dict__"):
        for v in vars(node).values():
            if isinstance(v, list):
                for item in v:
                    _find_int_lit(item, results)
            elif hasattr(v, "__dict__"):
                _find_int_lit(v, results)


# ============================================================
# 1. 进制字面量解析
# ============================================================

def test_radix_literal_parsing():
    """进制字面量解析：0b/0t/0x 前缀正确转换为十进制 int。"""
    print("\n=== test_radix_literal_parsing ===")
    cases = [
        ("#1：[0b1010]", 10, "二进制 0b1010"),
        ("#1：[0t210]", 21, "三进制 0t210"),
        ("#1：[0xFF]", 255, "十六进制 0xFF"),
        ("x = 0b1111", 15, "绑定 x=0b1111"),
        ("y = 0t222", 26, "绑定 y=0t222"),
        ("#1：[1010]", 1010, "十进制不受影响"),
        ("#1：[0b0]", 0, "二进制零"),
    ]
    for src, expected, label in cases:
        p = parse(src)
        lits = []
        for d in p.decls:
            _find_int_lit(d, lits)
        assert lits, f"{label}: 未找到 IntegerLit"
        assert lits[0].value == expected, f"{label}: 值={lits[0].value}, 期望 {expected}"
        print(f"  ✓ {label} → {lits[0].value}")
    print("  ✓ 进制字面量解析测试通过")


# ============================================================
# 2. 基础转译：整数 ⇄ 二进制
# ============================================================

def test_binary_conversion():
    """整数 ⇄ 二进制字符串互转。"""
    print("\n=== test_binary_conversion ===")
    cases = [(0, "0"), (1, "1"), (10, "1010"), (255, "11111111"), (42, "101010")]
    for n, expected in cases:
        b = to_binary(n)
        assert b == expected, f"to_binary({n})={b}, 期望 {expected}"
        assert from_binary(b) == n, f"from_binary({b})!={n}"
        print(f"  ✓ {n} ↔ {b}")
    # 负数
    assert to_binary(-5) == "-101"
    assert from_binary("-101") == -5
    print("  ✓ 负数 -5 ↔ -101")
    print("  ✓ 二进制转译测试通过")


# ============================================================
# 3. 基础转译：整数 ⇄ 三进制
# ============================================================

def test_ternary_conversion():
    """整数 ⇄ 三进制字符串互转。"""
    print("\n=== test_ternary_conversion ===")
    cases = [(0, "0"), (1, "1"), (2, "2"), (3, "10"), (5, "12"), (21, "210"), (42, "1120")]
    for n, expected in cases:
        t = to_ternary(n)
        assert t == expected, f"to_ternary({n})={t}, 期望 {expected}"
        assert from_ternary(t) == n, f"from_ternary({t})!={n}"
        print(f"  ✓ {n} ↔ {t}")
    print("  ✓ 三进制转译测试通过")


# ============================================================
# 4. 互转：二进制 ⇄ 三进制
# ============================================================

def test_cross_conversion():
    """二进制字符串 ⇄ 三进制字符串互转。"""
    print("\n=== test_cross_conversion ===")
    # 10 的二进制 1010 → 三进制 101
    assert binary_to_ternary("1010") == "101", f"binary_to_ternary(1010)={binary_to_ternary('1010')}"
    print("  ✓ 二进制 '1010'(=10) → 三进制 '101'")
    # 21 的三进制 210 → 二进制 10101
    assert ternary_to_binary("210") == "10101", f"ternary_to_binary(210)={ternary_to_binary('210')}"
    print("  ✓ 三进制 '210'(=21) → 二进制 '10101'")
    # 往返一致
    for n in [0, 1, 10, 21, 42, 255]:
        b = to_binary(n)
        t = binary_to_ternary(b)
        assert from_ternary(t) == n, f"往返失败: {n} → {b} → {t}"
        print(f"  ✓ 往返: {n} → 二进制 {b} → 三进制 {t} → {from_ternary(t)}")
    print("  ✓ 二进制↔三进制互转测试通过")


# ============================================================
# 5. Matha 专属编码
# ============================================================

def test_matha_encoding():
    """Matha 专属编码 M2:/M3: 与传统格式互译。"""
    print("\n=== test_matha_encoding ===")
    # 编码
    assert to_matha_binary(10) == "M2:1010"
    assert to_matha_ternary(21) == "M3:210"
    print("  ✓ 10 → M2:1010, 21 → M3:210")
    # 解码
    assert from_matha_code("M2:1010") == 10
    assert from_matha_code("M3:210") == 21
    print("  ✓ M2:1010 → 10, M3:210 → 21")
    # 专属编码互转
    assert matha_binary_to_ternary("M2:1010") == "M3:101"
    assert matha_ternary_to_binary("M3:210") == "M2:10101"
    print("  ✓ M2:1010 → M3:101, M3:210 → M2:10101")
    # 兼容传统格式
    assert from_matha_code("0b1010") == 10
    assert from_matha_code("0t210") == 21
    assert from_matha_code("255") == 255
    print("  ✓ 兼容传统 0b/0t/十进制")
    print("  ✓ Matha 专属编码测试通过")


# ============================================================
# 6. Matha 代码中使用进制字面量 + 转译
# ============================================================

def test_matha_code_with_radix():
    """Matha 代码中使用进制字面量，并验证可转译。"""
    print("\n=== test_matha_code_with_radix ===")
    src = (
        "#：{\n"
        "   #1：【加载二进制数据】\n"
        "   x = 0b1010\n"
        "   y = 0t210\n"
        "   #1：[x]\n"
        "   #2：[y]\n"
        "   #：【文件】\n"
        "}"
    )
    p = parse(src)
    _, errs = analyze_source(src, verbose=False)
    err_n = len([e for e in errs if e.severity == "error"])
    assert err_n == 0, f"进制字面量代码应无 error: {[e.msg for e in errs if e.severity=='error']}"
    # 提取字面量值并转译
    lits = []
    for d in p.decls:
        _find_int_lit(d, lits)
    values = [l.value for l in lits]
    assert 10 in values and 21 in values, f"应包含 10 和 21: {values}"
    # 转译验证
    assert to_matha_binary(10) == "M2:1010"
    assert to_matha_ternary(21) == "M3:210"
    print(f"  ✓ 代码解析 OK, 提取值 {values}")
    print(f"  ✓ 10 → {to_matha_binary(10)}, 21 → {to_matha_ternary(21)}")
    print("  ✓ Matha 代码进制字面量测试通过")


if __name__ == "__main__":
    test_radix_literal_parsing()
    test_binary_conversion()
    test_ternary_conversion()
    test_cross_conversion()
    test_matha_encoding()
    test_matha_code_with_radix()
    print("\n=== 全部二进制/三进制转译测试完成 ===")
