# -*- coding: utf-8 -*-
"""
递归与闭包复杂测试 — 验证自成长引擎深度嵌套场景下的优化能力
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.matha_growth import MathaGrowthEngine


# ============================================================
# 测试用例
# ============================================================

TEST_CASES = [
    {
        "name": "斐波那契递归（深度2内联）",
        "source": """def fib(n):
    if n <= 1:
        return float(n)
    return fib(n - 1) + fib(n - 2)

result = fib(5.0)
#1：[result]""",
    },
    {
        "name": "阶乘递归",
        "source": """def factorial(n):
    if n <= 1.0:
        return 1.0
    return n * factorial(n - 1.0)

result = factorial(5.0)
#1：[result]""",
    },
    {
        "name": "闭包风格（lambda）",
        "source": """make_adder = lambda x: lambda y: x + y
add_10 = make_adder(10.0)
result = add_10(5.0)
#1：[result]""",
    },
    {
        "name": "嵌套函数调用链",
        "source": """def double(x):
    return x * 2.0

def triple(x):
    return x * 3.0

def compute(x):
    return double(triple(x))

result = compute(5.0)
#1：[result]""",
    },
    {
        "name": "死代码 + 递归混合",
        "source": """unused_helper = 999.0

def square(x):
    return x * x

def sum_sq(a, b):
    return square(a) + square(b)

result = sum_sq(3.0, 4.0)
#1：[result]""",
    },
    {
        "name": "循环 + 常量折叠",
        "source": """s = 0.0
for i in range(4):
    s = s + float(i)

result = s * 2.0
#1：[result]""",
    },
    {
        "name": "深度嵌套常量传播",
        "source": """a = 10.0
b = a + 5.0
c = b * 2.0
d = c - 10.0
result = d + 1.0
#1：[result]""",
    },
    {
        "name": "多函数死代码",
        "source": """def helper1(x):
    return x + 1.0

def helper2(x):
    return x * 2.0

unused_result = helper1(5.0)

def main():
    return helper2(3.0)

result = main()
#1：[result]""",
    },
]


def test_all():
    print("=" * 70)
    print("递归与闭包复杂测试 — 自成长引擎深度嵌套场景验证")
    print("=" * 70)

    engine = MathaGrowthEngine(verbose=True)

    for case in TEST_CASES:
        name = case["name"]
        source = case["source"]
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"{'='*60}")
        print(f"原始源码 ({len(source)} 字符):")
        for line in source.split('\n'):
            print(f"  {line}")

        report = engine.grow(source, max_iterations=3)

        print(f"\n  成长报告:")
        print(f"    迭代次数: {report.iteration}")
        print(f"    诊断: {report.diagnostics if report.diagnostics else '无'}")
        print(f"    优化建议: {report.optimization_suggestions if report.optimization_suggestions else '无'}")
        print(f"    多语言一致性: {'✓' if report.cross_language_consistent else '✗'}")
        print(f"    已应用优化: {report.optimizations_applied if report.optimizations_applied else '无'}")
        print(f"    错误: {report.errors if report.errors else '无'}")
        if report.improved:
            print(f"    改进版本 ({len(report.improved_source)} 字符):")
            for line in report.improved_source.split('\n'):
                print(f"      {line}")
        print(f"    性能: {report.performance_before_ms:.2f}ms → {report.performance_after_ms:.2f}ms")

    # 汇总
    print(f"\n{'='*70}")
    print("测试汇总")
    print(f"{'='*70}")
    print(f"  测试用例数: {len(TEST_CASES)}")
    print(f"\n  {engine.get_summary()}")


if __name__ == "__main__":
    test_all()
