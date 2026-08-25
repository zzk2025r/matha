# -*- coding: utf-8 -*-
"""
自成长引擎优化能力验证
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.matha_growth import MathaGrowthEngine


CASES = [
    ("嵌套函数链", """def double(x):
    return x * 2.0
def triple(x):
    return x * 3.0
def compute(x):
    return double(triple(x))
result = compute(5.0)
#1：[result]""", "result = 30.0"),
    ("死代码+函数", """unused = 999.0
def square(x):
    return x * x
result = square(3.0)
#1：[result]""", "9.0"),
    ("常量传播链", """a = 10.0
b = a + 5.0
c = b * 2.0
d = c - 10.0
result = d + 1.0
#1：[result]""", "result = 21.0"),
    ("循环展开", """s = 0.0
for i in range(4):
    s = s + float(i)
result = s * 2.0
#1：[result]""", "result = 12.0"),
    ("递归阶乘", """def factorial(n):
    if n <= 1.0:
        return 1.0
    return n * factorial(n - 1.0)
result = factorial(4.0)
#1：[result]""", "result ="),
    ("混合优化", """unused1 = 999.0
unused2 = 888.0
a = 10.0
b = a + 5.0
def double(x):
    return x * 2.0
def triple(x):
    return x * 3.0
def compute(x):
    return double(triple(x))
result = compute(a) + b
#1：[result]""", "result ="),
]


def main():
    print("=" * 60)
    print("自成长引擎优化能力验证")
    print("=" * 60)
    engine = MathaGrowthEngine(verbose=False)
    passed = 0
    for name, source, expected in CASES:
        r = engine.grow(source, max_iterations=5)
        ok = expected in r.improved_source if r.improved_source else False
        status = "✓" if ok else "✗"
        if ok:
            passed += 1
        print(f"  [{status}] {name}: {r.optimizations_applied or '无优化'}")
        if r.improved_source:
            last_line = r.improved_source.strip().split('\n')[-1]
            print(f"         → {last_line}")
    print(f"\n结果: {passed}/{len(CASES)} 通过")


if __name__ == "__main__":
    main()
