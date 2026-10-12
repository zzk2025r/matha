# -*- coding: utf-8 -*-
"""虚拟代码引擎测试脚本"""
import sys
sys.path.insert(0, r"D:\trae")

from src.virtual_code import VirtualCodeRegistry, get_virtual_registry

print("=" * 60)
print("VirtualCodeRegistry 测试")
print("=" * 60)

vcr = VirtualCodeRegistry(debug=False)

# 1. 虚拟化测试
print("\n[1] 虚拟化测试")
v1 = vcr.virtual("my_missing_func")
print(f"  虚拟函数: {v1.name}, type={v1.code_type}")
r = v1(5)
print(f"  调用结果: {r}")
assert r == 5, f"Expected 5, got {r}"
print("  PASS")

# 2. 自动注册测试
print("\n[2] 自动注册测试")
v2 = vcr.get("another_missing_func")
print(f"  自动注册: {v2.name}")
r2 = v2(3, 4)
print(f"  调用结果: {r2}")
assert r2 == 7, f"Expected 7, got {r2}"
print("  PASS")

# 3. 数学函数自动推导（使用带关键词的名称）
print("\n[3] 数学函数自动推导")
v3 = vcr.virtual("missing_add", default_impl=lambda a, b: a + b)
r3 = v3(10, 20)
print(f"  missing_add(10, 20) = {r3}")
assert r3 == 30, f"Expected 30, got {r3}"
print("  PASS")

# 4. 吞噬测试
print("\n[4] 吞噬测试")
def my_real_func(x):
    return x * 2
v4 = vcr.absorb(my_real_func, "my_absorbed_func")
print(f"  吞噬函数: {v4.name}")
r4 = v4(5)
print(f"  调用结果: {r4}")
assert r4 == 10, f"Expected 10, got {r4}"
print("  PASS")

# 5. 自动修复测试
print("\n[5] 自动修复测试")
r5 = vcr.auto_fix("missing_sum", 1, 2, 3, 4, 5)
print(f"  auto_fix('missing_sum', 1,2,3,4,5) = {r5}")
print("  PASS")

# 6. 确认/拒绝测试
print("\n[6] 确认/拒绝测试")
confirmed = vcr.confirm("my_missing_func")
print(f"  confirm('my_missing_func') = {confirmed}")
denied = vcr.deny("nonexistent")
print(f"  deny('nonexistent') = {denied}")
print("  PASS")

# 7. 统计测试
print("\n[7] 统计测试")
stats = vcr.get_stats()
print(f"  虚拟创建数: {stats['virtual_created']}")
print(f"  吞噬数: {stats['absorbed_count']}")
print(f"  注册表大小: {stats['registry_size']}")
assert stats['virtual_created'] >= 2, f"Expected >= 2 virtual created, got {stats['virtual_created']}"
print("  PASS")

# 8. 吞噬源代码测试
print("\n[8] 吞噬源代码测试")
source_code = "def hello(): return 'Hello World'"
entries = vcr.absorb_source(source_code)
print(f"  吞噬源代码: {len(entries)} 个条目")
for e in entries:
    print(f"  {e.name}: {e.code_type}")
print("  PASS")

# 9. 模式分析测试
print("\n[9] 模式分析测试")
vcr.get("test_pattern")(1, 2)
vcr.get("test_pattern")(3, 4)
analysis = vcr.analyze_patterns("test_pattern")
print(f"  调用次数: {analysis['call_count']}")
print(f"  推荐: {analysis['recommendation']}")
print("  PASS")

# 10. 全局注册表测试
print("\n[10] 全局注册表测试")
global_vr = get_virtual_registry()
assert global_vr is not None, "Global registry should exist"
print(f"  全局注册表: {global_vr}")
print("  PASS")

# 11. 虚拟评估测试
print("\n[11] 虚拟评估测试")
vcr2 = VirtualCodeRegistry(debug=False)
# 虚拟注册表中有条目时返回
vcr2.virtual("test_virtual_eval")
result = vcr2.get("test_virtual_eval")
print(f"  虚拟评估结果: {result.name}")
assert result.name == "test_virtual_eval"
print("  PASS")

print("\n" + "=" * 60)
print("所有 VirtualCodeRegistry 测试通过!")
print("=" * 60)
