"""三进制运算测试用例（基于 M3.4 进制字面量定义）。

验证三进制字面量（0t 前缀）在 Matha 中的运算与转译：
  1. 三进制字面量解析（0t0 ~ 0t222）
  2. 三进制加法运算（0t210 + 0t111 = 34 → 三进制 1021）
  3. 三进制乘法运算（0t12 * 0t12 = 25 → 三进制 221）
  4. 混合进制运算（三进制 + 二进制 + 十六进制）
  5. 三进制 ↔ 二进制互转（模拟三进制计算机与二进制计算机数据交换）

三进制（base-3）使用数字 0/1/2，历史参考：Setun 三进制计算机（1958）。

运行：python -m tests.test_ternary_arithmetic
"""

from src.parser import parse
from src.semantic import analyze_ast
from src import ast_nodes as ast
from src.binary_codec import (
    to_ternary, from_ternary, to_binary, from_binary,
    to_matha_ternary, matha_ternary_to_binary, binary_to_ternary,
)


def _find_nodes(node, node_type, results):
    """递归找指定类型的 AST 节点。"""
    if isinstance(node, node_type):
        results.append(node)
    if hasattr(node, "__dict__"):
        for v in vars(node).values():
            if isinstance(v, list):
                for item in v:
                    _find_nodes(item, node_type, results)
            elif hasattr(v, "__dict__"):
                _find_nodes(v, node_type, results)


def _extract_binding_values(program):
    """从程序中提取所有 Binding 的变量名→整数值映射（仅字面量值）。"""
    values = {}
    bindings = []
    for d in program.decls:
        _find_nodes(d, ast.Binding, bindings)
    for b in bindings:
        if isinstance(b.value, ast.IntegerLit):
            values[b.target.name] = b.value.value
    return values


def _run_interpret(src: str) -> list:
    """运行 Matha 代码并返回输出。"""
    from src.interp import interpret
    out, _ = interpret(src)
    return out


# ============================================================
# 1. 三进制字面量解析
# ============================================================

def test_ternary_literal_parsing():
    """三进制字面量解析：0t 前缀正确转换为十进制 int。"""
    print("\n=== test_ternary_literal_parsing ===")
    cases = [
        ("0t0", 0), ("0t1", 1), ("0t2", 2), ("0t10", 3),
        ("0t12", 5), ("0t20", 6), ("0t210", 21), ("0t222", 26),
    ]
    for lit, expected in cases:
        src = f"#1：[{lit}]"
        p = parse(src)
        lits = []
        for d in p.decls:
            _find_nodes(d, ast.IntegerLit, lits)
        assert lits[0].value == expected, f"{lit} → {lits[0].value}, 期望 {expected}"
        print(f"  ✓ {lit} → {lits[0].value}")
    print("  ✓ 三进制字面量解析通过")


# ============================================================
# 2. 三进制加法运算
# ============================================================

def test_ternary_addition():
    """三进制加法：0t210(=21) + 0t111(=13) = 34 → 三进制 1021。"""
    print("\n=== test_ternary_addition ===")
    src = (
        "a = 0t210\n"
        "b = 0t111\n"
        "total = a + b\n"
        "#1：[a]\n"
        "#2：[b]\n"
        "#3：[total]"
    )
    p = parse(src)
    errs = analyze_ast(p, verbose=False)
    err_n = len([e for e in errs if e.severity == "error"])
    assert err_n == 0, f"三进制运算代码应无 error: {[e.msg for e in errs if e.severity=='error']}"

    values = _extract_binding_values(p)
    assert values["a"] == 21, f"a 应为 21, 实际 {values.get('a')}"
    assert values["b"] == 13, f"b 应为 13, 实际 {values.get('b')}"
    print(f"  ✓ a = 0t210 → {values['a']}")
    print(f"  ✓ b = 0t111 → {values['b']}")

    # 通过解释器验证运算结果
    out = _run_interpret(src)
    assert 34 in out, f"期望输出包含 34, 实际 {out}"
    print(f"  ✓ a + b = 34 → 三进制 {to_ternary(34)} / 二进制 {to_binary(34)}")
    print("  ✓ 三进制加法测试通过")


# ============================================================
# 3. 三进制乘法运算
# ============================================================

def test_ternary_multiplication():
    """三进制乘法：0t12(=5) * 0t12(=5) = 25 → 三进制 221。"""
    print("\n=== test_ternary_multiplication ===")
    src = "x = 0t12\ny = 0t12"
    p = parse(src)
    values = _extract_binding_values(p)
    x, y = values["x"], values["y"]
    assert x == 5 and y == 5

    product = x * y  # 25
    assert to_ternary(product) == "221", f"25 的三进制应为 221, 实际 {to_ternary(product)}"
    assert to_binary(product) == "11001", f"25 的二进制应为 11001, 实际 {to_binary(product)}"
    print(f"  ✓ 0t12({x}) × 0t12({y}) = {product} → 三进制 {to_ternary(product)} / 二进制 {to_binary(product)}")
    print("  ✓ 三进制乘法测试通过")


# ============================================================
# 4. 混合进制运算
# ============================================================

def test_mixed_radix_arithmetic():
    """混合进制运算：三进制 + 二进制 + 十六进制同表共存。"""
    print("\n=== test_mixed_radix_arithmetic ===")
    src = (
        "t = 0t210\n"
        "b = 0b1010\n"
        "h = 0xFF\n"
        "#1：[t]\n"
        "#2：[b]\n"
        "#3：[h]"
    )
    p = parse(src)
    errs = analyze_ast(p, verbose=False)
    err_n = len([e for e in errs if e.severity == "error"])
    assert err_n == 0, f"混合进制应无 error: {[e.msg for e in errs if e.severity=='error']}"

    values = _extract_binding_values(p)
    assert values["t"] == 21 and values["b"] == 10 and values["h"] == 255

    total = values["t"] + values["b"] + values["h"]  # 286
    assert total == 286
    print(f"  ✓ 0t210({values['t']}) + 0b1010({values['b']}) + 0xFF({values['h']}) = {total}")
    print(f"    → 三进制 {to_ternary(total)} / 二进制 {to_binary(total)} / {to_matha_ternary(total)}")
    print("  ✓ 混合进制运算测试通过")


# ============================================================
# 5. 三进制 ↔ 二进制互转（模拟三进制计算机数据交换）
# ============================================================

def test_ternary_binary_translation():
    """三进制 ↔ 二进制互转：模拟三进制计算机与二进制计算机的数据交换。"""
    print("\n=== test_ternary_binary_translation ===")
    # 三进制数据 → 二进制传输 → 转回三进制（往返一致）
    ternary_data = ["210", "111", "222", "1021", "101121"]
    for t in ternary_data:
        val = from_ternary(t)
        b = to_binary(val)
        t_back = binary_to_ternary(b)
        assert t_back == t, f"往返失败: {t} → {b} → {t_back}"
        print(f"  ✓ 三进制 {t}({val}) → 二进制 {b} → 三进制 {t_back}")

    # Matha 专属编码互转
    assert matha_ternary_to_binary("M3:210") == "M2:10101"
    print("  ✓ M3:210 → M2:10101 (Matha 专属编码互转)")
    print("  ✓ 三进制↔二进制互转测试通过")


if __name__ == "__main__":
    test_ternary_literal_parsing()
    test_ternary_addition()
    test_ternary_multiplication()
    test_mixed_radix_arithmetic()
    test_ternary_binary_translation()
    print("\n=== 全部三进制运算测试完成 ===")
