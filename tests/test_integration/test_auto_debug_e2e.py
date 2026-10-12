"""集成测试：AutoDebugger 端到端完整流程。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.autonomous import auto_debug
from src.interp import Interpreter


def test_auto_debug_undefined_var():
    """未定义变量 → 自动补 @：var=0 → 成功运行。"""
    i = Interpreter()
    src = '#：{\n  a = x + 1\n  #：[a]\n}'
    r = auto_debug(i, src)
    assert r['成功'] is True, r
    assert '@：x=0' in (r['修复方案'] or ''), r
    # 验证本体状态：x 已注入 env
    assert 'x' in i.env
    print(f"  ✓ 未定义变量修复: {r['修复方案'].strip()}")


def test_auto_debug_undefined_func():
    """未定义函数 → 自动补恒零函数 → 成功运行。"""
    i = Interpreter()
    src = '#：{\n  v = foo(5)\n  #：[v]\n}'
    r = auto_debug(i, src)
    assert r['成功'] is True, r
    assert 'foo' in (r['修复方案'] or ''), r
    assert 'foo' in i.funcs
    print(f"  ✓ 未定义函数修复: {r['修复方案'].strip()}")


def test_auto_debug_unchanged_by_default():
    """未修复源（无错误）→ 直接成功，修复方案为空。"""
    i = Interpreter()
    src = '#：{\n  v = 1 + 2\n  #：[v]\n}'
    r = auto_debug(i, src)
    assert r['成功'] is True, r
    assert r['修复方案'] == '', r
    print("  ✓ 无错误源直接成功")


def test_auto_debug_unfixable_syntax_error():
    """语法错误 → 返回失败。"""
    i = Interpreter()
    src = '#：{\n  v =\n}'
    r = auto_debug(i, src, max_attempts=2)
    assert r['成功'] is False, r
    assert r['错误类型'] is not None, r
    print(f"  ✓ 不可修复错误报告失败: {r['错误类型'][:30]}")


def test_auto_debug_multiple_rounds():
    """多轮修复：同时存在未定义变量和函数。"""
    i = Interpreter()
    # 同时有未定义函数 foo 和未定义变量 x
    src = '#：{\n  v = foo(x)\n  #：[v]\n}'
    r = auto_debug(i, src, max_attempts=3)
    assert r['成功'] is True, r
    print(f"  ✓ 多轮修复成功: {r['修复方案'].strip()}")


def test_auto_debug_returns_dict():
    """返回 dict 格式正确。"""
    i = Interpreter()
    src = '#：{\n  a = x + 1\n  #：[a]\n}'
    r = auto_debug(i, src)
    assert isinstance(r, dict)
    assert '成功' in r
    assert '修复方案' in r
    assert '错误类型' in r
    print("  ✓ 返回 dict 格式正确")


def test_auto_debug_full_program():
    """完整程序：已定义函数 + 未定义变量 → 自动修复整个程序。"""
    i = Interpreter()
    src = ('func 双倍(x: Int) -> Int = (x) => x * 2\n'
           '#：{\n  a = 双倍(y)\n  #：[a]\n}')
    r = auto_debug(i, src, max_attempts=4)
    assert r['成功'] is True, r
    assert 'y' in (r['修复方案'] or ''), r
    # 修复后原有函数仍可正常调用
    assert i.call('双倍', 2) == 4
    print(f"  ✓ 完整程序自动修复: {r['修复方案'].strip()}")


def test_auto_debug_nested_undefined_func():
    """嵌套未定义函数 foo(bar(5)) → 修复内层函数。"""
    i = Interpreter()
    src = '#：{\n  v = foo(bar(5))\n  #：[v]\n}'
    r = auto_debug(i, src, max_attempts=4)
    assert r['成功'] is True, r
    assert 'bar' in (r['修复方案'] or ''), r
    print(f"  ✓ 嵌套函数自动修复: {r['修复方案'].strip()}")


def test_auto_debug_multiple_undefined_vars():
    """多个未定义变量 → 全部注入 env 默认值。"""
    i = Interpreter()
    src = '#：{\n  a = x + 1\n  b = y + 2\n  #：[a + b]\n}'
    r = auto_debug(i, src, max_attempts=4)
    assert r['成功'] is True, r
    assert 'x' in i.env and i.env['x'] == 0
    assert 'y' in i.env and i.env['y'] == 0
    print(f"  ✓ 多变量自动修复: x={i.env['x']}, y={i.env['y']}")


def main():
    tests = [
        test_auto_debug_undefined_var,
        test_auto_debug_undefined_func,
        test_auto_debug_unchanged_by_default,
        test_auto_debug_unfixable_syntax_error,
        test_auto_debug_multiple_rounds,
        test_auto_debug_returns_dict,
        test_auto_debug_full_program,
        test_auto_debug_nested_undefined_func,
        test_auto_debug_multiple_undefined_vars,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n集成测试（AutoDebugger）: {passed}/{passed+failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
