# -*- coding: utf-8 -*-
"""集成测试：SelfGrower 端到端完整生命周期。"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.parser import parse
from src.interp import Interpreter
from src.autonomous import SelfGrower, self_grow


def test_learn_from_source():
    """从源码学习新函数。"""
    i = Interpreter()
    grower = SelfGrower(i)
    r = grower.learn('func 立方(x: Int) -> Int = (x) => x * x * x', '学习立方')
    assert r.成功 is True, r
    assert '立方' in r.新能力
    assert i.call('立方', 3) == 27
    print(f"  ✓ 从源码学习: 立方(3)={i.call('立方', 3)}")


def test_learn_from_file():
    """从文件学习。"""
    i = Interpreter()
    grower = SelfGrower(i)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.matha', delete=False, encoding='utf-8') as f:
        f.write('func 四倍(x: Int) -> Int = (x) => x * 4')
        path = f.name
    try:
        r = grower.learn_from_file(path)
        assert r.成功 is True, r
        assert '四倍' in r.新能力
        assert i.call('四倍', 5) == 20
        print(f"  ✓ 从文件学习: 四倍(5)={i.call('四倍', 5)}")
    finally:
        os.unlink(path)


def test_specialize():
    """参数特化。"""
    i = Interpreter()
    i.run(parse('func 加十(x: Int) -> Int = (x) => x + 10'))
    grower = SelfGrower(i)
    r = grower.specialize('加十', [5])
    assert r.成功 is True, r
    assert '加十_特化' in r.新能力
    assert i.call('加十_特化', 0) == 15
    print(f"  ✓ 参数特化: 加十_特化(0)={i.call('加十_特化', 0)}")


def test_self_grow_wrapper():
    """便捷函数 self_grow 调用正确。"""
    i = Interpreter()
    r = self_grow(i, 'func 五倍(x: Int) -> Int = (x) => x * 5', '学习五倍')
    assert r['成功'] is True, r
    assert '五倍' in r['新能力']
    assert i.call('五倍', 3) == 15
    print(f"  ✓ self_grow 便捷函数: 五倍(3)={i.call('五倍', 3)}")


def test_learn_invalid_source():
    """非法源码 → 学习失败。"""
    i = Interpreter()
    grower = SelfGrower(i)
    r = grower.learn('func 语法错误(', '非法源码')
    assert r.成功 is False
    print(f"  ✓ 非法源码学习失败")


def test_full_lifecycle():
    """完整生命周期：学习 → 调用 → 特化 → 再调用。"""
    i = Interpreter()
    grower = SelfGrower(i)

    # 1. 学习
    grower.learn('func 平方(x: Int) -> Int = (x) => x * x', '学习平方')
    assert i.call('平方', 4) == 16

    # 2. 特化
    r = grower.specialize('平方', [4])
    assert r.成功 is True
    assert i.call('平方_特化', 0) == 16

    print(f"  ✓ 完整生命周期: 学习→调用→特化→调用")


def main():
    tests = [
        test_learn_from_source,
        test_learn_from_file,
        test_specialize,
        test_self_grow_wrapper,
        test_learn_invalid_source,
        test_full_lifecycle,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n集成测试（SelfGrower）: {passed}/{passed+failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
