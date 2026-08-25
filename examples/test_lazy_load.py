# -*- coding: utf-8 -*-
"""启动流程优化对比测试"""
import sys, time
sys.path.insert(0, r"D:\trae")
from src.matha_growth import MathaGrowthEngine

print("=" * 60)
print("解释器启动流程优化对比")
print("=" * 60)

# 预热（强制触发懒加载）
eng = MathaGrowthEngine(verbose=False)
eng.grow("x = 1.0\n#1：[x]", max_iterations=1)

# 后续调用（缓存命中）
times = []
for i in range(5):
    t0 = time.perf_counter()
    eng.grow(f"y{i} = {i}.0 + {(i+1)}.0\n#1：[y{i}]", max_iterations=1)
    times.append((time.perf_counter() - t0) * 1000)

avg = sum(times) / len(times)
print(f"\n懒加载后 5 次调用: {[f'{t:.1f}ms' for t in times]}")
print(f"平均: {avg:.1f}ms")
print(f"相比首次 ~134ms, 加速比: {134/avg:.1f}x")
print(f"节省: ~{134-avg:.0f}ms/次 ({(1-avg/134)*100:.1f}%)")

# 跨实例测试
eng2 = MathaGrowthEngine(verbose=False)
t0 = time.perf_counter()
eng2.grow("z = 7.0 + 8.0\n#1：[z]", max_iterations=1)
cross = (time.perf_counter() - t0) * 1000
print(f"\n跨实例调用（类级缓存共享）: {cross:.1f}ms")
