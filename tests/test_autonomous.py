# -*- coding: utf-8 -*-
"""自主子系统测试：调试 / 优化 / 成长。

覆盖三个层次：
  1) AutoDebugger：未定义变量修复、未定义函数修复、不可修复错误
  2) PerformanceOptimizer：采样、热点识别、记忆化特化
  3) SelfGrower：从源码学习、从文件学习、特化
  4) Matha 侧内建：自主_调试 / 自主_优化 / 自主_成长

运行：python -m tests.test_autonomous
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.parser import parse
from src.interp import Interpreter, interpret
from src.autonomous import (
    AutoDebugger, PerformanceOptimizer, SelfGrower,
    auto_debug, auto_optimize_memoize, self_grow,
)


def _interp_with(src: str = '') -> Interpreter:
    i = Interpreter()
    if src:
        i.run(parse(src))
    return i


# ============================================================
# 1) AutoDebugger
# ============================================================

def test_debug_fix_undefined_var():
    """未定义变量 → 自动补 @：变量=0 → 修复成功。"""
    print("\n--- 自主调试: 修复未定义变量 ---")
    i = _interp_with()
    src = '#：{\n  #：[z]\n}'
    r = auto_debug(i, src, max_attempts=3)
    assert r['成功'] is True, r
    assert '@：z=0' in r['修复方案'], r
    print(f"  ✓ 修复方案: {r['修复方案'].strip()}")


def test_debug_fix_undefined_func():
    """未定义函数 → 自动补恒零函数 → 修复成功。"""
    print("\n--- 自主调试: 修复未定义函数 ---")
    i = _interp_with()
    src = '#：{\n  v = foo(5)\n  #：[v]\n}'
    r = auto_debug(i, src, max_attempts=3)
    assert r['成功'] is True, r
    assert 'foo' in (r['修复方案'] or ''), r
    print(f"  ✓ 修复方案含 foo 定义")


def test_debug_unfixable():
    """语法错误 → 无法自动修复 → 报告失败。"""
    print("\n--- 自主调试: 不可修复 ---")
    i = _interp_with()
    src = '#：{\n  v =\n}'  # 语法错误
    r = auto_debug(i, src, max_attempts=2)
    assert r['成功'] is False, r
    print(f"  ✓ 正确报告失败: {r['错误类型']}")


# ============================================================
# 2) PerformanceOptimizer
# ============================================================

def test_optimize_profile_and_hotspot():
    """采样 + 热点识别。"""
    print("\n--- 自主优化: 采样与热点 ---")
    i = _interp_with('func 平方(x: Int) -> Int = (x) => x * x')
    opt = PerformanceOptimizer(i)
    opt.profile('平方', [5], runs=5)
    hs = opt.hotspot()
    assert hs == '平方', hs
    s = opt.samples['平方']
    assert s.calls == 5
    print(f"  ✓ 热点={hs}, 调用={s.calls}次")


def test_optimize_memoize():
    """记忆化特化：生成特化函数并提交。"""
    print("\n--- 自主优化: 记忆化特化 ---")
    i = _interp_with('func 双倍(x: Int) -> Int = (x) => x * 2')
    opt = PerformanceOptimizer(i)
    opt.profile('双倍', [5], runs=3)
    r = opt.optimize_memoize('双倍')
    assert r.成功 is True, r
    assert '双倍_特化0' in r.变更.get('新函数', []), r
    assert i.probe().has('双倍_特化0') is True
    v = i.call('双倍_特化0', 0)
    assert v == 10, v  # 5*2=10
    print(f"  ✓ 特化函数 双倍_特化0(0)={v}")


# ============================================================
# 3) SelfGrower
# ============================================================

def test_grow_learn_from_source():
    """从源码学习新函数。"""
    print("\n--- 自主成长: 从源码学习 ---")
    i = _interp_with()
    grower = SelfGrower(i)
    src = 'func 立方(x: Int) -> Int = (x) => x * x * x'
    r = grower.learn(src, '学习立方')
    assert r.成功 is True, r
    assert '立方' in r.新能力, r
    assert i.probe().has('立方') is True
    assert i.call('立方', 3) == 27
    print(f"  ✓ 新能力={r.新能力}, 立方(3)={i.call('立方', 3)}")


def test_grow_learn_from_file():
    """从文件学习。"""
    print("\n--- 自主成长: 从文件学习 ---")
    import tempfile
    i = _interp_with()
    grower = SelfGrower(i)
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.matha', delete=False, encoding='utf-8'
    ) as f:
        f.write('func 四倍(x: Int) -> Int = (x) => x * 4')
        path = f.name
    try:
        r = grower.learn_from_file(path)
        assert r.成功 is True, r
        assert '四倍' in r.新能力, r
        assert i.call('四倍', 5) == 20
        print(f"  ✓ 从文件学习 四倍(5)={i.call('四倍', 5)}")
    finally:
        os.unlink(path)


def test_grow_specialize():
    """为常用参数特化。"""
    print("\n--- 自主成长: 参数特化 ---")
    i = _interp_with('func 加十(x: Int) -> Int = (x) => x + 10')
    grower = SelfGrower(i)
    r = grower.specialize('加十', [5])
    assert r.成功 is True, r
    assert '加十_特化' in r.新能力, r
    assert i.call('加十_特化', 0) == 15
    print(f"  ✓ 特化 加十_特化(0)={i.call('加十_特化', 0)}")


# ============================================================
# 4) Matha 侧内建
# ============================================================

def test_matha_auto_debug():
    """Matha 侧调用 自主_调试 内建。"""
    print("\n--- Matha 侧: 自主_调试 ---")
    src = '''#：{
  报告 = 自主_调试("#：{ #：[w] }")(3)
  #：[报告]
}'''
    out, _ = interpret(src)
    assert len(out) > 0
    r = out[-1]
    assert r['成功'] is True, r
    print(f"  ✓ Matha 调用自主调试: 成功={r['成功']}")


def test_matha_self_grow():
    """Matha 侧调用 自主_成长 内建。"""
    print("\n--- Matha 侧: 自主_成长 ---")
    src = '''#：{
  报告 = 自主_成长("func 五倍(x: Int) -> Int = (x) => x * 5")("学习五倍")
  #：[报告]
}'''
    out, _ = interpret(src)
    r = out[0]
    assert r['成功'] is True, r
    assert '五倍' in r['新能力'], r
    print(f"  ✓ Matha 调用自主成长: 新能力={r['新能力']}")


# ============================================================
# 主入口
# ============================================================

def main():
    tests = [
        test_debug_fix_undefined_var,
        test_debug_fix_undefined_func,
        test_debug_unfixable,
        test_optimize_profile_and_hotspot,
        test_optimize_memoize,
        test_grow_learn_from_source,
        test_grow_learn_from_file,
        test_grow_specialize,
        test_matha_auto_debug,
        test_matha_self_grow,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as ex:
            failed += 1
            print(f"  ✗ {t.__name__}: {type(ex).__name__}: {ex}")
    print(f"\n{'='*40}")
    print(f"自主子系统测试: {passed}/{passed+failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
