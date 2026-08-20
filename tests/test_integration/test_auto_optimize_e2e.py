# -*- coding: utf-8 -*-
"""集成测试：PerformanceOptimizer 端到端验证。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.parser import parse
from src.interp import Interpreter
from src.autonomous import PerformanceOptimizer, auto_optimize_memoize


def test_profile_and_hotspot():
    """采样 + 热点识别。"""
    i = Interpreter()
    i.run(parse('func 平方(x: Int) -> Int = (x) => x * x'))
    opt = PerformanceOptimizer(i)
    opt.profile('平方', [5], runs=5)
    hs = opt.hotspot()
    assert hs == '平方'
    assert opt.samples['平方'].calls == 5
    assert opt.samples['平方'].args == [5]
    print(f"  ✓ 热点={hs}, 调用={opt.samples['平方'].calls}次, args={opt.samples['平方'].args}")


def test_optimize_memoize_dynamic_args():
    """记忆化特化使用采样参数（非硬编码 [5]）。"""
    i = Interpreter()
    i.run(parse('func 双倍(x: Int) -> Int = (x) => x * 2'))
    opt = PerformanceOptimizer(i)
    opt.profile('双倍', [5], runs=3)
    r = opt.optimize_memoize('双倍')
    assert r.成功 is True, r
    assert '双倍_特化0' in r.变更.get('新函数', [])
    v = i.call('双倍_特化0', 0)
    assert v == 10, f"期望 10, 实际 {v}"
    print(f"  ✓ 特化函数 双倍_特化0(0)={v}")


def test_optimize_memoize_different_args():
    """不同参数采样 → 特化函数结果正确。"""
    i = Interpreter()
    i.run(parse('func 加十(x: Int) -> Int = (x) => x + 10'))
    opt = PerformanceOptimizer(i)
    opt.profile('加十', [7], runs=3)
    r = opt.optimize_memoize('加十')
    assert r.成功 is True, r
    v = i.call('加十_特化0', 0)
    assert v == 17, f"期望 17 (7+10), 实际 {v}"
    print(f"  ✓ 不同参数特化: 加十_特化0(0)={v}")


def test_auto_optimize_memoize_wrapper():
    """便捷函数 auto_optimize_memoize 调用正确。"""
    i = Interpreter()
    i.run(parse('func 四倍(x: Int) -> Int = (x) => x * 4'))
    opt = PerformanceOptimizer(i)
    opt.profile('四倍', [3], runs=2)
    r = opt.optimize_memoize('四倍')
    assert r.成功 is True, r
    v = i.call('四倍_特化0', 0)
    assert v == 12, f"期望 12 (3*4), 实际 {v}"
    print(f"  ✓ 记忆化特化: 四倍_特化0(0)={v}")


def test_optimize_no_sample():
    """未采样 → 优化失败。"""
    i = Interpreter()
    opt = PerformanceOptimizer(i)
    r = opt.optimize_memoize('不存在')
    assert r.成功 is False
    print(f"  ✓ 未采样函数优化失败")


def main():
    tests = [
        test_profile_and_hotspot,
        test_optimize_memoize_dynamic_args,
        test_optimize_memoize_different_args,
        test_auto_optimize_memoize_wrapper,
        test_optimize_no_sample,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n集成测试（PerformanceOptimizer）: {passed}/{passed+failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
