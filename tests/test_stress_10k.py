# -*- coding: utf-8 -*-
"""压力测试：10000 次算法一致性验证。"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.interp import Interpreter
from src.parser import parse
from src.autonomous import auto_debug, PerformanceOptimizer


ITERATIONS = 10000
# 使用简单有效的 Matha 代码片段
SIMPLE_OPS = [
    ('常量加法', '#：{\n  a = 1 + 2\n  #：[a]\n}'),
    ('常量乘法', '#：{\n  a = 3 * 4\n  #：[a]\n}'),
    ('变量绑定', '#：{\n  @：x=5\n  a = x + 1\n  #：[a]\n}'),
    ('输出测试', '#：{\n  #：[10]\n}'),
]


def run_stress_test():
    """10000 次重复运行，验证解释器一致性。"""
    total_start = time.perf_counter()
    passed = failed = 0
    errors = {}

    for i in range(ITERATIONS):
        op_name, src = SIMPLE_OPS[i % len(SIMPLE_OPS)]
        i_inst = Interpreter()
        try:
            i_inst.run(parse(src))
            passed += 1
        except Exception as e:
            failed += 1
            key = str(e)[:50]
            errors[key] = errors.get(key, 0) + 1

    total_time = (time.perf_counter() - total_start) * 1000

    print(f"\n=== 压力测试: {ITERATIONS} 次迭代 ===")
    print(f"  通过: {passed}/{ITERATIONS} ({passed/ITERATIONS*100:.2f}%)")
    print(f"  失败: {failed}/{ITERATIONS}")
    print(f"  总耗时: {total_time:.0f}ms ({total_time/ITERATIONS:.3f}ms/次)")
    if errors:
        print(f"  错误分布:")
        for k, v in sorted(errors.items(), key=lambda x: -x[1])[:5]:
            print(f"    [{v}次] {k}")

    report = {
        "iterations": ITERATIONS,
        "passed": passed,
        "failed": failed,
        "total_ms": round(total_time, 0),
        "per_iter_ms": round(total_time / ITERATIONS, 3),
        "pass_rate": round(passed / ITERATIONS * 100, 2),
    }
    print(f"\n  报告: {report}")
    return failed == 0


def test_auto_debug_stability():
    """AutoDebugger 在大量运行中保持稳定性。"""
    print("\n=== AutoDebugger 稳定性测试 (1000 次) ===")
    total = 1000
    passed = 0
    for i in range(total):
        i_inst = Interpreter()
        r = auto_debug(i_inst, '#：{\n  a = x + 1\n  #：[a]\n}')
        if r['成功']:
            passed += 1
    rate = passed / total * 100
    print(f"  通过: {passed}/{total} ({rate:.1f}%)")
    return passed == total


def test_perf_profile_stability():
    """性能采样在重复运行中保持稳定。"""
    print("\n=== 性能采样稳定性测试 (100 次) ===")
    i = Interpreter()
    i.run(parse('func 平方(x: Int) -> Int = (x) => x * x'))
    opt = PerformanceOptimizer(i)
    times = []
    for _ in range(100):
        opt.profile('平方', [5], runs=1)
        times.append(opt.samples['平方'].avg_ms)
    avg = sum(times) / len(times)
    std = (sum((t - avg) ** 2 for t in times) / len(times)) ** 0.5
    cv = std / avg * 100 if avg else 0
    print(f"  平均: {avg:.3f}ms, 标准差: {std:.3f}ms, CV: {cv:.1f}%")
    return cv < 100  # CV < 100% 视为可接受


def main():
    results = []
    results.append(run_stress_test())
    results.append(test_auto_debug_stability())
    results.append(test_perf_profile_stability())

    print(f"\n{'='*40}")
    print(f"压力测试总结果: {'全部通过' if all(results) else '存在失败'}")
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
