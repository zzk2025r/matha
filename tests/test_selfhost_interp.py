"""Test Matha eval core concepts with correct syntax."""
import subprocess, sys

from src.interp import interpret

print("=== Testing Matha eval core concepts ===\n")

# Test 1: Basic expression eval (curried multi-param call)
print("--- Test 1: Basic expression eval ---")
src = """
func 做整数(n: Int) -> Int = (n) => n
func 做二元(op: String, left: Int, right: Int) -> Int = (op, left, right) =>
  op = "+" ? left + right :
  op = "-" ? left - right :
  op = "*" ? left * right :
  op = "/" ? left / right :
  0
#：{
  r1 = 做二元("+")(3)(5)
  r2 = 做二元("*")(2)(做二元("+")(3)(4))
  r3 = 做二元(">")(1)(2) ? 100 : 200
  [r1]
  [r2]
  [r3]
}
"""
try:
    out, _ = interpret(src)
    print(f"  outputs: {out}")
    assert out == [8, 14, 200], f"Expected [8, 14, 200], got {out}"
    print("  ✓ 基础表达式求值通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 2: Variable lookup (single set_up item)
print("\n--- Test 2: Variable lookup ---")
src2 = """
@:x = 10
@:y = 20
#：{
  [x + y]
  [x * y]
}
"""
try:
    out, _ = interpret(src2)
    print(f"  outputs: {out}")
    assert out == [30, 200], f"Expected [30, 200], got {out}"
    print("  ✓ 变量查找通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 3: Lambda closure capture
print("\n--- Test 3: Lambda closure capture ---")
src3 = """
func 做加法(base: Int) -> Int = (base) =>
  (n) => base + n
#：{
  add5 = 做加法(5)
  r = add5(3)
  [r]
}
"""
try:
    out, _ = interpret(src3)
    print(f"  outputs: {out}")
    assert out == [8], f"Expected [8], got {out}"
    print("  ✓ Lambda 闭包捕获通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 4: Nested ternary
print("\n--- Test 4: Nested ternary ---")
src4 = """
#：{
  r = 1 > 2 ? 10 : (3 > 4 ? 20 : 30)
  [r]
}
"""
try:
    out, _ = interpret(src4)
    print(f"  outputs: {out}")
    assert out == [30], f"Expected [30], got {out}"
    print("  ✓ 嵌套三元通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 5: Multi-param lambda currying
print("\n--- Test 5: Multi-param lambda currying ---")
src5 = """
func 乘(a: Int, b: Int) -> Int = (a, b) => a * b
#：{
  r = 乘(3)(4)
  [r]
}
"""
try:
    out, _ = interpret(src5)
    print(f"  outputs: {out}")
    assert out == [12], f"Expected [12], got {out}"
    print("  ✓ 多参柯里化通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 6: Function as argument
print("\n--- Test 6: Function as argument ---")
src6 = """
func 应用(f, x) -> Int = (f, x) => f(x)
func 双倍(n) -> Int = (n) => n * 2
func 平方(n) -> Int = (n) => n * n
#：{
  r1 = 应用(双倍)(5)
  r2 = 应用(平方)(5)
  [r1]
  [r2]
}
"""
try:
    out, _ = interpret(src6)
    print(f"  outputs: {out}")
    assert out == [10, 25], f"Expected [10, 25], got {out}"
    print("  ✓ 函数作为参数通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 7: Chained function composition
print("\n--- Test 7: Chained function composition ---")
src7 = """
func 双倍(n) -> Int = (n) => n * 2
func 平方(n) -> Int = (n) => n * n
#：{
  r = 平方(双倍(5))
  [r]
}
"""
try:
    out, _ = interpret(src7)
    print(f"  outputs: {out}")
    assert out == [100], f"Expected [100], got {out}"
    print("  ✓ 函数组合通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

# Test 8: Ternary in binding
print("\n--- Test 8: Ternary in binding ---")
src8 = """
#：{
  m = 3 > 2 ? 100 : 200
  [m]
}
"""
try:
    out, _ = interpret(src8)
    print(f"  outputs: {out}")
    assert out == [100], f"Expected [100], got {out}"
    print("  ✓ 三元在绑定通过")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

print("\n=== All concept tests completed ===")
