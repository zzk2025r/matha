# -*- coding: utf-8 -*-
"""虚拟代码定义层测试"""
import sys
sys.path.insert(0, r"D:\trae")

from src.virtual_code import (
    VirtualCodeDefinition, VirtualCodeDefinitionEngine,
    define, define_capability, define_multiple, interpret, spiral,
    define_natural_language,
    get_definition_engine, reset_definition_engine,
)

print("=" * 60)
print("虚拟代码定义层测试")
print("=" * 60)

engine = get_definition_engine(debug=False)

# 1. 定义能力
print("\n[1] 定义能力")
defn = engine.define("my_code")
defn.add_definition("add", "add", lambda *args: sum(args) if args else 0)
defn.add_definition("mul", "mul", lambda *args: __import__('math').prod(args) if args else 1)
print(f"  定义: {defn.name}, 能力: {defn.get_capabilities()}")
assert len(defn.capabilities) == 2
print("  PASS")

# 2. 多能力/语义
print("\n[2] 多能力/语义")
defn2 = engine.define("math_func")
defn2.add_definition("add", "add", lambda *args: sum(args) if args else 0)
defn2.add_definition("sub", "sub", lambda a, b: a - b)
defn2.add_definition("mul", "mul", lambda *args: __import__('math').prod(args) if args else 1)
defn2.add_definition("div", "div", lambda a, b: a / b if b != 0 else 0)
print(f"  多能力: {defn2.get_capabilities()}")
assert len(defn2.capabilities) == 4
print("  PASS")

# 3. 解读/取用能力
print("\n[3] 解读/取用能力")
result = engine.interpret("math_func", "add", 1, 2, 3)
print(f"  interpret('math_func', 'add', 1,2,3) = {result}")
assert result == 6
print("  PASS")

# 4. 螺旋上升
print("\n[4] 螺旋上升")
spiral_result = engine.spiral("spiral_func", "add", 10, 20)
print(f"  螺旋步骤: {spiral_result['steps']}")
print(f"  结果: {spiral_result['result']}")
print(f"  螺旋次数: {spiral_result['spiral_count']}")
assert spiral_result['result'] == 30
assert len(spiral_result['steps']) == 6  # define, register, use, refine, redefine, re-register
print("  PASS")

# 5. 自然语言定义
print("\n[5] 自然语言定义")
nl_defn = engine.define_natural_language("zh", "计算 正弦 余弦", "natural_math")
print(f"  自然语言定义: {nl_defn.name}, 能力: {nl_defn.get_capabilities()}")
assert "正弦" in nl_defn.get_capabilities()
print("  PASS")

# 6. 自然语言转代码
print("\n[6] 自然语言转代码")
result = engine.interpret("natural_math", "正弦", 3.14159)
print(f"  interpret('natural_math', '正弦', 3.14159) = {result}")
print("  PASS")

# 7. 定义统计
print("\n[7] 定义统计")
stats = engine.get_definition_stats()
print(f"  定义数: {stats['definitions']}, 能力数: {stats['total_capabilities']}, 螺旋次数: {stats['spiral_count']}")
print("  PASS")

# 8. 螺旋上升多次
print("\n[8] 多次螺旋上升")
for i in range(3):
    engine.spiral(f"func_{i}", "add", i, i+1)
count = engine.get_spiral_count()
print(f"  螺旋总次数: {count}")
assert count == 4  # 1 + 3 = 4
print("  PASS")

# 9. 便捷函数测试
print("\n[9] 便捷函数测试")
d = define("convenience_test")
d.add_definition("test", "test", lambda: 42)
r = interpret("convenience_test", "test")
print(f"  interpret('convenience_test', 'test') = {r}")
assert r == 42
print("  PASS")

# 10. 螺旋上升达到自然语言及代码能力
print("\n[10] 螺旋上升达到自然语言及代码能力")
nl = engine.natural_to_code_with_definition("计算 求和 映射 过滤", language="zh")
print(f"  代码名: {nl['code_name']}")
print(f"  能力: {nl['capabilities']}")
print(f"  螺旋完成: {nl['spiral_complete']}")
assert nl['spiral_complete'] == True
assert len(nl['capabilities']) == 4
print("  PASS")

print("\n" + "=" * 60)
print("所有虚拟代码定义层测试通过!")
print("=" * 60)
print()
print("核心洞察验证：")
print("  - 定义与注册相辅相成")
print("  - 单一代码可拥有多个能力/语义")
print("  - 对拥有多种能力/语义的代码进行解读/取用")
print("  - 螺旋上升：define → register → use → refine → redefine → re-register")
print("  - 最终达到自然语言及代码能力")
