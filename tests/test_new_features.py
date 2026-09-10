# -*- coding: utf-8 -*-
"""Matha 新功能集成测试：位运算、集合运算、严格比较、空值合并、可选链、Struct 字段访问。"""
import sys
sys.path.insert(0, r'D:\trae')

from src.interp import interpret


def get_out(src: str):
    """执行 Matha 源码，返回最后一次输出。"""
    out, _ = interpret(src)
    return out[-1] if out else None


# ─── 位运算 ─────────────────────────────────────────────────────────────────

def test_bit_and():
    assert get_out('12 & 10') == 8
    print('  ✓ 位与: 12 & 10 = 8')

def test_bit_or():
    assert get_out('12 | 10') == 14
    print('  ✓ 位或: 12 | 10 = 14')

def test_bit_xor():
    assert get_out('12 ^ 10') == 6
    print('  ✓ 位异或: 12 ^ 10 = 6')

def test_bit_lshift():
    assert get_out('1 << 3') == 8
    print('  ✓ 左移: 1 << 3 = 8')

def test_bit_rshift():
    assert get_out('16 >> 2') == 4
    print('  ✓ 右移: 16 >> 2 = 4')

def test_bit_not():
    assert get_out('~5') == -6
    print('  ✓ 位取反: ~5 = -6')

def test_bit_xor_unicode():
    # ⊕ → OP_BIT_XOR（Lexer 修复）
    assert get_out('12 ⊕ 10') == 6
    print('  ✓ 位异或(Unicode): 12 ⊕ 10 = 6')

# ─── 集合运算 ────────────────────────────────────────────────────────────────

def test_set_union():
    assert get_out('#1：[1,2,3] ∪ [3,4,5]') == {1, 2, 3, 4, 5}
    print('  ✓ 集合并: [1,2,3] ∪ [3,4,5]')

def test_set_inter():
    assert get_out('#1：[1,2,3] ∩ [2,3,4]') == {2, 3}
    print('  ✓ 集合交: [1,2,3] ∩ [2,3,4]')

def test_set_diff():
    assert get_out('#1：[1,2,3] ⊖ [2,3,4]') == {1}
    print('  ✓ 集合差: [1,2,3] ⊖ [2,3,4]')

def test_set_subset():
    assert get_out('#1：[1,2] ⊆ [1,2,3]') is True
    assert get_out('#1：[1,2,4] ⊆ [1,2,3]') is False
    print('  ✓ 子集: [1,2] ⊆ [1,2,3] = True')

def test_set_prod():
    result = get_out('#1：[1,2] × ["a","b"]')
    assert sorted(result) == [(1, 'a'), (1, 'b'), (2, 'a'), (2, 'b')]
    print('  ✓ 笛卡尔积: [1,2] × [a,b]')

# ─── 严格比较 ───────────────────────────────────────────────────────────────

def test_strict_eq():
    assert get_out('1 === 1') is True
    assert get_out('1 === "1"') is False
    assert get_out('null === null') is True
    print('  ✓ 严格相等: 1 === 1, 1 === "1", null === null')

def test_strict_neq():
    assert get_out('1 !== "1"') is True
    assert get_out('1 !== 1') is False
    print('  ✓ 严格不等: 1 !== "1" = True')

# ─── 空值合并 ───────────────────────────────────────────────────────────────

def test_null_coal_basic():
    out, _ = interpret('let x = null; #1：[x ?? 42]')
    assert out[-1] == 42, out
    print('  ✓ 空值合并: null ?? 42 = 42')

def test_null_coal_value():
    out, _ = interpret('let x = 7; #1：[x ?? 42]')
    assert out[-1] == 7
    print('  ✓ 空值合并: 7 ?? 42 = 7')

# ─── 可选链 ────────────────────────────────────────────────────────────────

def test_optional_chain_attr():
    src = '''
struct Point{x: Int, y: Int}
let p = Point(3, 4)
#1：[p.x]
'''
    assert get_out(src) == 3
    print('  ✓ 可选链属性: Point(3,4).x = 3')

def test_optional_chain_attr_missing():
    src = '''
struct Empty{}
let e = Empty()
#1：[e.missing ?? "none"]
'''
    assert get_out(src) == "none"
    print('  ✓ 可选链缺失属性: e.missing ?? "none"')

def test_safe_path_expr_none():
    src = '''
let p = null
#1：[p?.field]
'''
    assert get_out(src) is None
    print('  ✓ SafePathExpr None: null?.field = None')

def test_safe_path_expr_attr():
    src = '''
struct Person{name: Str}
let p = Person("Alice")
#1：[p?.name]
'''
    assert get_out(src) == "Alice"
    print('  ✓ SafePathExpr 属性: Person("Alice")?.name = Alice')

# ─── Struct 字段访问 ────────────────────────────────────────────────────────

def test_struct_field_access():
    src = '''
struct Point{x: Int, y: Int}
let p = Point(1, 2)
#1：[p.x + p.y]
'''
    assert get_out(src) == 3
    print('  ✓ Struct 字段访问: Point(1,2).x + Point(1,2).y = 3')

def test_struct_dict_access():
    src = '''
struct Person{name: Str, age: Int}
let p = Person("Bob", 30)
#1：[p["name"] + " is " + p["age"]]
'''
    assert get_out(src) == "Bob is 30"
    print('  ✓ Struct 下标访问: Person("Bob",30)["name"]')

# ─── 组合测试 ───────────────────────────────────────────────────────────────

def test_bit_in_expr_context():
    assert get_out('let x = 1; #1：[x * 2 & 3]') == 2
    print('  ✓ 位与优先级: 1*2 & 3 = 2')

def test_set_union_in_expr():
    assert get_out('let s = [1,2]; #1：[s ∪ [3,4]]') == {1, 2, 3, 4}
    print('  ✓ 集合并在变量表达式中')


# ─── 主入口 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== Matha 新功能集成测试 ===')
    tests = [
        test_bit_and, test_bit_or, test_bit_xor,
        test_bit_lshift, test_bit_rshift, test_bit_not, test_bit_xor_unicode,
        test_set_union, test_set_inter, test_set_diff,
        test_set_subset, test_set_prod,
        test_strict_eq, test_strict_neq,
        test_null_coal_basic, test_null_coal_value,
        test_optional_chain_attr, test_optional_chain_attr_missing,
        test_safe_path_expr_none, test_safe_path_expr_attr,
        test_struct_field_access, test_struct_dict_access,
        test_bit_in_expr_context, test_set_union_in_expr,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'  ✗ {t.__name__}: {e}')
            failed += 1
    print(f'\n结果: {passed} 通过, {failed} 失败')
    if failed:
        sys.exit(1)
