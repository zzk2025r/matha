# -*- coding: utf-8 -*-
"""运算符映射 / 字典键 / 内建注册 缺陷修复回归测试。

覆盖本会话修复的缺陷：
  1. `∧`（逻辑与）、`∨`（逻辑或）、全角 `＆`（位与）此前一律被词法映射为
     OP_PIPE（位或），导致 `真 ∧ 假` → True、`真 ＆ 假` → True 等**静默错误结果**。
  2. `&&` / `||` 已由词法器产出 OP_LAND/OP_LOR，但解析器从不消费 →
     一律 ParseError。
  3. 字典字面量的非字符串键（整数/浮点/布尔）此前被误判为集合枚举，
     `{1: "一"}` 解析报错；且 `dict[整数键]` 求值不支持。
  4. 宿主内建缺失 `_to_int`/`_to_float`/`_to_str`（VM/原生后端有，
     自举 stdlib 依赖）；`matha_runtime` 的 `format` / `format_str` 注册不一致。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.interp import interpret, Interpreter
from src.matha_runtime import get_builtin, get_builtin_names


def val(src: str):
    """执行源码，返回最后一次输出值（标量）。"""
    out, _ = interpret(src)
    return out[-1] if out else None


def _assign(expr: str):
    return val('x = ' + expr + '\n输出(x)')


# ─── 1. ∧ / ∨ / ＆ 运算符映射 ────────────────────────────────────────────────

def test_logical_and_symbol():
    assert _assign('真 ∧ 假') is False
    assert _assign('真 ∧ 真') is True
    assert _assign('假 ∧ 假') is False
    print('  ✓ 真 ∧ 假 → False（此前错误为 True）')


def test_logical_or_symbol():
    assert _assign('真 ∨ 假') is True
    assert _assign('假 ∨ 假') is False
    print('  ✓ ∨ 逻辑或')


def test_bit_and_fullwidth_symbol():
    assert _assign('6 ＆ 3') == 2
    assert _assign('真 ＆ 假') is False
    print('  ✓ 全角 ＆ → 位与（6＆3=2）')


def test_bit_and_ascii_unchanged():
    assert _assign('6 & 3') == 2
    print('  ✓ ASCII & 位与不受影响')


def test_bit_or_ascii_still_bitwise():
    """回归保护：ASCII `|` 仍是位或，不是逻辑或，也不是集合分格。"""
    assert _assign('6 | 3') == 7
    print('  ✓ ASCII | 仍为位或（6|3=7）')


# ─── 2. && / || ─────────────────────────────────────────────────────────────

def test_double_amp_and():
    assert _assign('真 && 假') is False
    assert _assign('真 && 真') is True
    print('  ✓ && 逻辑与')


def test_double_pipe_or():
    assert _assign('真 || 假') is True
    assert _assign('假 || 真') is True
    assert _assign('假 || 假') is False
    print('  ✓ || 逻辑或')


def test_and_binds_tighter_than_or():
    # 假 && 假 = 假；真 || 假 = 真
    assert _assign('真 || 假 && 假') is True
    assert _assign('假 && 假 || 真') is True
    print('  ✓ && 优先级高于 ||')


# ─── 2b. 链式比较 ────────────────────────────────────────────────────────────

def test_chained_comparison():
    assert _assign('1 <= 5 <= 10') is True
    assert _assign('1 <= 5 <= 3') is False
    assert _assign('10 >= 5 > 1') is True
    assert _assign('1 < 2 < 3') is True
    assert _assign('1 < 2 > 3') is False
    print('  ✓ 链式比较 1 <= 5 <= 10 → True')


def test_chained_comparison_with_variable():
    assert val('x = 7\ny = 1 <= x <= 10\n输出(y)') is True
    print('  ✓ 链式比较中间的变量 x')


# ─── 3. 字典非字符串键 ───────────────────────────────────────────────────────

def test_dict_integer_key():
    assert val('d = {1: "一", 2: "二"}\nx = d[2]\n输出(x)') == '二'
    print('  ✓ 整数键字典 + d[2] 取值')


def test_dict_float_key():
    assert val('d = {1.5: "v"}\nx = d[1.5]\n输出(x)') == 'v'
    print('  ✓ 浮点键字典')


def test_dict_bool_key():
    assert val('d = {真: 1}\nx = d[真]\n输出(x)') == 1
    print('  ✓ 布尔键字典')


def test_dict_string_key_still_works():
    assert val('d = {"a": 5}\nx = d["a"]\n输出(x)') == 5
    print('  ✓ 字符串键字典不受影响')


def test_dict_missing_key_returns_none():
    assert val('d = {1: 2}\nx = d[9]\n输出(x)') is None
    print('  ✓ 缺键返回 None（与既有语义一致）')


def test_set_enumeration_still_works():
    assert val('x = {1, 2, 2, 3}\n输出(x)') == [1, 2, 3]
    print('  ✓ 集合枚举去重不受影响')


def test_set_comprehension_without_generator_fails_explicitly():
    """无法推断定义域的 {x | 条件}（如仅单侧界 x > 5）须显式报错，而非误导性的
    「未定义变量 'x'」。"""
    from src.parser import parse, ParseError
    try:
        parse('S = { x | x > 5 }')
    except ParseError as e:
        assert '集合理解' in str(e) and '生成子句' in str(e)
    else:
        raise AssertionError('无生成子句的集合理解应显式报 ParseError')
    print('  ✓ 无生成子句集合理解显式报错（不再静默/误导）')


# ─── 4. 元组字面量（修正陈旧 docstring 所声称的「暂未实现」） ──────────────────

def test_tuple_literal_supported():
    assert val('x = (1, 2, 3)\n输出(x)') == (1, 2, 3)
    print('  ✓ 元组字面量可用')


# ─── 5. 内建注册 ─────────────────────────────────────────────────────────────

def test_host_has_numeric_conversion_primitive_builtins():
    b = Interpreter().builtins
    for name in ('_to_int', '_to_float', '_to_str'):
        assert name in b, f'宿主内建缺少 {name}'
    assert b['_to_int'](3.9) == 3
    assert b['_to_float'](2) == 2.0
    print('  ✓ 宿主内建 _to_int/_to_float/_to_str 已注册')


def test_format_registry_consistent():
    names = get_builtin_names()
    assert 'format' in names and 'format_str' in names
    assert get_builtin('format') is not None
    assert get_builtin('format_str') is not None
    print('  ✓ format / format_str 注册一致')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
    print('全部通过')