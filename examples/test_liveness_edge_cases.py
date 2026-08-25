# -*- coding: utf-8 -*-
"""变量存活分析边界情况测试"""
import sys
sys.path.insert(0, r"D:\trae")
from src.matha_growth import MathaGrowthEngine

engine = MathaGrowthEngine(verbose=False)

# 测试1: 嵌套作用域 — 同名变量在不同作用域应独立处理
source1 = """x = 1.0
def f(x):
    return x + 1.0
result = f(x)
#1：[result]"""

# 测试2: 跨作用域引用 — 外层变量不应被错误识别为可复用
source2 = """a = 10.0
def helper():
    return a + 5.0
result = helper()
#1：[result]"""

# 测试3: 循环内变量 — 循环变量与外部变量不应冲突
source3 = """s = 0.0
for i in range(3):
    s = s + float(i)
result = s * 2.0
#1：[result]"""

# 测试4: 多变量存活区间重叠 — 应使用不同槽位
source4 = """a = 1.0
b = 2.0
c = a + b
d = c * 2.0
result = d + 1.0
#1：[result]"""

# 测试5: 多变量存活区间不重叠 — 应复用槽位
source5 = """a = 1.0
x = a + 1.0
b = 2.0
y = b + 1.0
result = x + y
#1：[result]"""

print("=" * 60)
print("变量存活分析边界情况测试")
print("=" * 60)

test_cases = [
    ("嵌套作用域同名变量", source1),
    ("跨作用域引用", source2),
    ("循环内变量", source3),
    ("多变量区间重叠", source4),
    ("多变量区间不重叠", source5),
]

for name, source in test_cases:
    try:
        r = engine.grow(source, max_iterations=3)
        improved = r.improved_source.strip()
        last_line = improved.split('\n')[-1] if improved else "无"
        print(f"  [OK] {name}")
        print(f"        优化: {r.optimizations_applied or '无'}")
        print(f"        结果: {last_line}")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")

print()
print("测试完成")
