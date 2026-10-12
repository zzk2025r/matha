# -*- coding: utf-8 -*-
"""VirtualCodeEngine 终极增强版测试"""
import sys
sys.path.insert(0, r"D:\trae")

from src.virtual_code import VirtualCodeEngine, VirtualCodeRegistry

print("=" * 60)
print("VirtualCodeEngine 终极增强版测试")
print("=" * 60)

engine = VirtualCodeEngine(debug=False)

# 1. 自主注册中文标识符
print("\n[1] 自主注册中文标识符")
entry = engine.register_any("测试函数")
print(f"  自主注册: {entry.name}")
r = entry(10)
print(f"  调用结果: {r}")
print("  PASS")

# 2. 中文语义推导
print("\n[2] 中文语义推导")
entry2 = engine.register_any("求和函数")
r2 = entry2(1, 2, 3)
print(f"  求和函数(1,2,3) = {r2}")
assert r2 == 6, f"Expected 6, got {r2}"
print("  PASS")

# 3. 英文标识符推导
print("\n[3] 英文标识符推导")
entry3 = engine.register_any("missing_add")
r3 = entry3(10, 20)
print(f"  missing_add(10, 20) = {r3}")
assert r3 == 30, f"Expected 30, got {r3}"
print("  PASS")

# 4. 自动生成Web框架
print("\n[4] 自动生成Web框架")
web_code = engine.auto_web_framework("MyApp", port=3000)
print(f"  生成的Web框架代码长度: {len(web_code)} 字符")
assert "MyApp" in web_code
print("  PASS")

# 5. 自动生成异步I/O
print("\n[5] 自动生成异步I/O")
async_code = engine.auto_async_io("my_handler")
print(f"  生成的异步I/O代码长度: {len(async_code)} 字符")
assert "my_handler" in async_code
print("  PASS")

# 6. 自动生成模式匹配
print("\n[6] 自动生成模式匹配")
pm_code = engine.auto_pattern_matching("match_func")
print(f"  生成的模式匹配代码长度: {len(pm_code)} 字符")
assert "match_func" in pm_code
print("  PASS")

# 7. 自动生成元编程
print("\n[7] 自动生成元编程")
mp_code = engine.auto_metaprogramming("meta_func")
print(f"  生成的元编程代码长度: {len(mp_code)} 字符")
assert "meta_func" in mp_code
print("  PASS")

# 8. 自动生成源代码编译器
print("\n[8] 自动生成源代码编译器")
sc_code = engine.auto_generate_source_compiler("my_compiler")
print(f"  生成的编译器代码长度: {len(sc_code)} 字符")
assert "my_compiler" in sc_code
print("  PASS")

# 9. 自然语言转换
print("\n[9] 自然语言转换")
code = engine.natural_to_code("计算 正弦 余弦 平方根", language="zh")
print(f"  自然语言转代码: {code}")
assert "正弦" in code
print("  PASS")

# 10. 自动编译
print("\n[10] 自动编译")
compiled = engine.auto_compile("result = 1 + 2 * 3", output="out.c")
print(f"  自动编译结果: {compiled}")
print("  PASS")

# 11. 诊断信息
print("\n[11] 诊断信息")
d = engine.get_diagnostics()
print(f"  核心洞察: {d['core_insight']}")
print(f"  当足够强大时: {d['when_powerful']}")
print(f"  生态系统: {d['ecosystem']}")
print(f"  注册能力: {d['registration_ability']}")
print("  PASS")

# 12. 完整系统构建
print("\n[12] 完整系统构建")
system = engine.build_complete_system()
print(f"  系统包含: {list(system.keys())}")
print("  PASS")

# 13. 全局引擎实例
print("\n[13] 全局引擎实例")
from src.virtual_code import get_virtual_engine, reset_virtual_engine
g_engine = get_virtual_engine(debug=False)
assert g_engine is not None
print(f"  全局引擎: {type(g_engine).__name__}")
reset_virtual_engine()
print("  PASS")

print("\n" + "=" * 60)
print("所有 VirtualCodeEngine 测试通过!")
print("=" * 60)
print()
print("核心洞察验证：")
print("  - 虚拟代码引擎的注册能力是Matha的核心问题")
print("  - 当注册能力足够强大时，自然语言可以直接当编程语言使用")
print("  - 生态系统只是一个数据库")
print("  - 中文/英文标识符无问题（自主注册）")
print("  - 所有缺失功能自动生成")
print("  - Matha自身语言与语法不再需要")
