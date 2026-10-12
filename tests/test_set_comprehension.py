# -*- coding: utf-8 -*-
"""集合理解 `{ 输出 | 生成子句 | 条件 ... }` 支持回归测试。

语法（`|` 分隔）：
    生成子句 := <变量> >> <集合/可迭代表达式>
    条件子句 := 布尔表达式
    输出     := 任意表达式（逐满足绑定的元素求值）
   映射写法 := 生成子句后接 `, <输出表达式>`（末子句），覆盖头部输出
语义与集合枚举一致：结果按 == 去重且保序（普通 list 承载）。
多生成子句为笛卡尔积（自左向右嵌套）。

无生成子句的 {x | 条件} 若能由条件推断有界整数域（如 1 <= x <= 10、1 < x < 4、
或分开的 x >= 3 | x < 7），则展开为该整数区间迭代；否则显式报 ParseError。

后端覆盖：宿主解释器、字节码 VM、原生后端（native.py 消费同一 MMB 字节码）均支持。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.interp import interpret
from src.parser import parse, ParseError
from src.mbc.compiler import Compiler
from src.mbc.vm import VM


def val(src: str):
    out, _ = interpret(src)
    return out[-1] if out else None


def _set(expr: str):
    return val('输出(' + expr + ')')


def mbc(src: str):
    """经字节码后端编译执行，返回所有输出值。"""
    vm = VM(Compiler().compile_program(parse(src)))
    vm.run()
    return vm.outputs


def _mset(expr: str):
    outs = mbc('输出(' + expr + ')')
    return outs[-1] if outs else None


# ─── 基本形式 ────────────────────────────────────────────────────────────────

def test_generator_only():
    assert _set('{ x | x >> [1, 2, 3, 4] }') == [1, 2, 3, 4]
    print('  ✓ {x | x >> S} → S')


def test_single_filter():
    assert _set('{ x | x >> [1, 2, 3, 4] | x > 2 }') == [3, 4]
    print('  ✓ 过滤条件')


def test_multiple_filters():
    assert _set('{ n | n >> [1, 2, 3, 4, 5] | n > 2 | n < 5 }') == [3, 4]
    print('  ✓ 多条件（合取）')


def test_mapping_output():
    assert _set('{ x * 10 | x >> [1, 2, 3] }') == [10, 20, 30]
    print('  ✓ 输出映射表达式')


def test_dedup_and_order():
    assert _set('{ x | x >> [1, 1, 2, 3, 3, 1] }') == [1, 2, 3]
    assert _set('{ x % 2 | x >> [1, 2, 3, 4] }') == [1, 0]
    print('  ✓ 去重且保序（== 语义）')


def test_tuple_output_cartesian():
    assert _set('{ (x, y) | x >> [1, 2] | y >> [3, 4] | x < y }') == \
        [(1, 3), (1, 4), (2, 3), (2, 4)]
    print('  ✓ 元组输出 + 笛卡尔积')


def test_string_iteration():
    assert _set('{ c | c >> "abc" }') == ['a', 'b', 'c']
    print('  ✓ 字符串迭代')


def test_empty_iterable():
    assert _set('{ x | x >> [] }') == []
    print('  ✓ 空可迭代表达式')


def test_dict_iteration_yields_items():
    assert _set('{ k | k >> {1: "a", 2: "b"} }') == [(1, 'a'), (2, 'b')]
    print('  ✓ 字典迭代产出 (键, 值)')


def test_local_generator_binding_not_leaked():
    # 生成变量 x 不应污染外层同名变量
    assert val('x = 99\ns = { x | x >> [1, 2, 3] }\n输出(x)') == 99
    print('  ✓ 生成变量不泄漏到外层作用域')


def test_variable_iterable():
    assert val('S = [1, 2, 3, 4, 5]\n输出({ n | n >> S | n > 2 })') == [3, 4, 5]
    print('  ✓ 可迭代表达式引用变量')


# ─── 与既有语法共存 / 不受影响 ───────────────────────────────────────────────

def test_enumeration_unaffected():
    assert _set('{1, 2, 2, 3}') == [1, 2, 3]
    assert _set('{}') == []
    print('  ✓ 枚举形式 / 空集合不受影响')


def test_code_block_with_bitwise_or_unaffected():
    # 代码块 { a | b } 无生成子句，仍按代码块解析（位或）
    assert val('a = 1\nb = 2\n输出(a | b)') == 3
    print('  ✓ 代码块位或不受影响')


# ─── 有界整数域推断（无生成子句） ─────────────────────────────────────────────

def test_inferred_inclusive_range():
    assert _set('{ x | 1 <= x <= 10 }') == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    print('  ✓ 推断有界整数域 1 <= x <= 10')


def test_inferred_exclusive_range():
    assert _set('{ x | 1 < x < 4 }') == [2, 3]
    print('  ✓ 推断开区间 1 < x < 4')


def test_inferred_range_with_filter():
    assert _set('{ x | 1 <= x <= 10 | x % 2 == 0 }') == [2, 4, 6, 8, 10]
    print('  ✓ 推断定义域 + 过滤条件')


def test_inferred_range_separate_bounds():
    assert _set('{ x | x >= 3 | x < 7 }') == [3, 4, 5, 6]
    print('  ✓ 分列上下界 x >= 3 | x < 7')


def test_inferred_range_compound_output():
    assert _set('{ x * x | 1 <= x <= 5 }') == [1, 4, 9, 16, 25]
    print('  ✓ 推断定义域 + 复合输出表达式')


def test_inferred_empty_range():
    assert _set('{ x | 1 <= x <= 3 | x > 5 }') == []
    print('  ✓ 矛盾上下界 → 空集合')


def test_inferred_range_shadows_outer():
    assert val('x = 99\n输出({ x | 1 <= x <= 3 })') == [1, 2, 3]
    print('  ✓ 推断定义域变量遮蔽外层')


# ─── 映射写法 `, 输出` ───────────────────────────────────────────────────────

def test_comma_mapping_over_generator():
    assert _set('{ n | n >> [1, 2, 3] , n + n }') == [2, 4, 6]
    print('  ✓ `, 输出` 映射（生成子句）')


def test_comma_mapping_cartesian():
    assert _set('{ (x, y) | x >> [1, 2] | y >> [3, 4] , x * y }') == [3, 4, 6, 8]
    print('  ✓ `, 输出` 映射（笛卡尔积）')


def test_comma_mapping_matches_head_output():
    assert _set('{ n | n >> [1, 2, 3] , n * 10 }') == _set('{ n * 10 | n >> [1, 2, 3] }')
    print('  ✓ `, 输出` 等价于头部输出')


# ─── 后端覆盖：字节码 VM（原生后端消费同一 MMB 字节码） ──────────────────────

def test_bytecode_backend_supports_comprehension():
    assert _mset('{ x | x >> [1, 2, 3, 4] | x > 2 }') == [3, 4]
    assert _mset('{ x * 10 | x >> [1, 2, 3] }') == [10, 20, 30]
    assert _mset('{ x | x >> [1, 1, 2, 3, 3] }') == [1, 2, 3]
    print('  ✓ 字节码后端支持集合理解')


def test_bytecode_backend_supports_bounded_and_mapping():
    assert _mset('{ x | 1 <= x <= 5 }') == [1, 2, 3, 4, 5]
    assert _mset('{ n | n >> [1, 2, 3] , n + n }') == [2, 4, 6]
    print('  ✓ 字节码后端支持有界域与映射写法')


# ─── 明确的失败（不静默） ────────────────────────────────────────────────────

def test_unbounded_no_generator_raises_parse_error():
    try:
        parse('S = { x | x > 5 }')
    except ParseError as e:
        assert '集合理解' in str(e) and '生成子句' in str(e)
    else:
        raise AssertionError('无法推断定义域的集合理解应显式报 ParseError')
    print('  ✓ 无生成子句且无法推断定义域显式报错')


def test_inferred_range_exceeds_cap_raises():
    try:
        parse('S = { x | 1 <= x <= 100001 }')
    except ParseError as e:
        assert '集合理解' in str(e)
    else:
        raise AssertionError('超出跨度上限的推断定义域应显式报 ParseError')
    print('  ✓ 推断定义域超跨度上限显式报错')


def test_bad_iterable_raises_runtime_error():
    from src.interp import MathaRuntimeError
    try:
        interpret('输出({ x | x >> 5 })')
    except MathaRuntimeError as e:
        assert '集合理解生成子句' in str(e)
    else:
        raise AssertionError('非可迭代对象应报 MathaRuntimeError')
    print('  ✓ 非可迭代表达式显式报错')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
    print('全部通过')
