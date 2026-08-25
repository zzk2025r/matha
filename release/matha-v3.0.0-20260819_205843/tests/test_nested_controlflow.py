# -*- coding: utf-8 -*-
"""Matha 控制流与 Lambda 嵌套逻辑测试。

覆盖：
  1. 嵌套 if-else 语句
  2. Lambda 闭包与变量捕获
  3. Lambda 递归（阶乘、斐波那契）
  4. 高阶函数组合（compose、apply）
  5. for 循环 + Lambda 过滤
  6. while 循环 + if-else 嵌套
  7. Lambda 柯里化链式调用
  8. 多参数 Lambda 嵌套
  9. Match 模式匹配 + Lambda
 10. 组合：函数式 + 命令式混合

Matha 函数应用：f(arg)。Match 语法：match expr { | pattern => result }。
多输出：多个 #N：[expr] 语句，取全部输出为列表。
列表：result + [n] 拼接构建。

运行：python -m tests.test_nested_controlflow
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import interpret

passed = 0
failed = 0


def check(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  ✓ {name}: {actual}")
    else:
        failed += 1
        print(f"  ✗ {name}: 期望 {expected}, 实际 {actual}")


def run(name, src, expected):
    """单输出测试。"""
    global passed, failed
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        check(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")


def run_multi(name, src, expected_list):
    """多输出测试：所有 #N：[expr] 输出拼接为列表。"""
    global passed, failed
    try:
        out, trace = interpret(src)
        check(name, out, expected_list)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")


print("=" * 60)
print("Matha 控制流与 Lambda 嵌套逻辑测试")
print("=" * 60)

# ================================================================
# 1. 嵌套 if-else 语句
# ================================================================
print("\n=== 1. 嵌套 if-else 语句 ===")

run(
    "双层 if-else（真路径）",
    """#：{
  x = 5
  if x > 3 {
    if x > 4 {
      [100]
    } 否则 {
      [200]
    }
  } 否则 {
    [300]
  }
}""",
    100,
)

run(
    "双层 if-else（假路径外层）",
    """#：{
  x = 2
  if x > 3 {
    [100]
  } 否则 {
    if x > 0 {
      [300]
    } 否则 {
      [400]
    }
  }
}""",
    300,
)

run(
    "双层 if-else（假路径内层）",
    """#：{
  x = -1
  if x > 3 {
    [100]
  } 否则 {
    if x > 0 {
      [300]
    } 否则 {
      [400]
    }
  }
}""",
    400,
)

run(
    "三元嵌套",
    """#：{
  a = 3
  b = 5
  c = 2
  r = a > b ? a : (b > c ? b : c)
  [r]
}""",
    5,
)

# ================================================================
# 2. Lambda 闭包与变量捕获
# ================================================================
print("\n=== 2. Lambda 闭包与变量捕获 ===")

run(
    "闭包捕获外层变量",
    """#：{
  x = 10
  f = (y) => x + y
  [f(5)]
}""",
    15,
)

run_multi(
    "多重闭包捕获",
    """#：{
  base = 100
  add = (n) => base + n
  mul = (n) => base * n
  [add(1)]
  [mul(2)]
}""",
    [101, 200],
)

run(
    "闭包延迟求值",
    """#：{
  val = 5
  f = () => val
  val = 99
  [f()]
}""",
    5,  # Matha 闭包为值捕获语义（捕获声明时的值），非引用捕获
)

# ================================================================
# 3. Lambda 递归
# ================================================================
print("\n=== 3. Lambda 递归 ===")

run(
    "阶乘",
    """func 阶乘(n: Int) -> Int = (n) =>
  n <= 1 ? 1 : n * 阶乘(n - 1)
#：{
  [阶乘(6)]
}""",
    720,
)

run(
    "斐波那契",
    """func 斐波那契(n: Int) -> Int = (n) =>
  n <= 1 ? n : 斐波那契(n - 1) + 斐波那契(n - 2)
#：{
  [斐波那契(10)]
}""",
    55,
)

run(
    "幂函数递归",
    """func 幂(base: Int, exp: Int) -> Int = (base, exp) =>
  exp <= 0 ? 1 : base * 幂(base)(exp - 1)
#：{
  [幂(2)(10)]
}""",
    1024,
)

run_multi(
    "阶乘 + 斐波那契",
    """func 阶乘(n: Int) -> Int = (n) =>
  n <= 1 ? 1 : n * 阶乘(n - 1)
func 斐波那契(n: Int) -> Int = (n) =>
  n <= 1 ? n : 斐波那契(n - 1) + 斐波那契(n - 2)
#：{
  [阶乘(7)]
  [斐波那契(8)]
}""",
    [5040, 21],
)

# ================================================================
# 4. 高阶函数组合
# ================================================================
print("\n=== 4. 高阶函数组合 ===")

run(
    "compose 组合函数",
    """func 加一(x: Int) -> Int = (x) => x + 1
func 加倍(x: Int) -> Int = (x) => x * 2
#：{
  h = (f, g) => (x) => f(g(x))
  r = h(加一)(加倍)(5)
  [r]
}""",
    11,
)

run(
    "apply 应用函数",
    """func 应用(f, x) -> Int = (f, x) => f(x)
func 平方(x) -> Int = (x) => x * x
func 加十(x) -> Int = (x) => x + 10
#：{
  r1 = 应用(平方)(3)
  r2 = 应用(加十)(r1)
  [r2]
}""",
    19,
)

run(
    "双重 compose",
    """func 加一(x: Int) -> Int = (x) => x + 1
func 加倍(x: Int) -> Int = (x) => x * 2
#：{
  h = (f, g) => (x) => f(g(x))
  r = h(加倍)(加一)(5)
  [r]
}""",
    12,
)

# ================================================================
# 5. for 循环 + Lambda 过滤
# ================================================================
print("\n=== 5. for 循环 + Lambda 过滤 ===")

run(
    "for 循环求和",
    """#：{
  sum = 0
  for i in [1, 2, 3, 4, 5] {
    sum = sum + i
  }
  [sum]
}""",
    15,
)

run(
    "for 循环求积",
    """#：{
  prod = 1
  for i in [1, 2, 3, 4, 5] {
    prod = prod * i
  }
  [prod]
}""",
    120,
)

run(
    "for + lambda 过滤求和（偶数）",
    """func 是偶数(n) -> Bool = (n) => n % 2 = 0
#：{
  sum = 0
  for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] {
    if 是偶数(i) { sum = sum + i }
  }
  [sum]
}""",
    30,
)

run(
    "for + lambda 过滤求和（奇数）",
    """func 是奇数(n) -> Bool = (n) => n % 2 != 0
#：{
  sum = 0
  for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] {
    if 是奇数(i) { sum = sum + i }
  }
  [sum]
}""",
    25,
)

# ================================================================
# 6. while 循环 + if-else 嵌套
# ================================================================
print("\n=== 6. while 循环 + if-else 嵌套 ===")

run(
    "while 倒计时",
    """#：{
  n = 5
  result = []
  while n > 0 {
    result = result + [n]
    n = n - 1
  }
  [result]
}""",
    [5, 4, 3, 2, 1],
)

run_multi(
    "while + if-else 奇偶分类",
    """#：{
  n = 10
  odd = 0
  even = 0
  i = 1
  while i <= n {
    if i % 2 = 0 { even = even + 1 } 否则 { odd = odd + 1 }
    i = i + 1
  }
  [odd]
  [even]
}""",
    [5, 5],
)

run_multi(
    "while 累乘直到超过阈值",
    """#：{
  prod = 1
  n = 1
  while prod <= 100 {
    n = n + 1
    prod = prod * n
  }
  [n]
  [prod]
}""",
    [5, 120],
)

run(
    "while 累加 + lambda 条件",
    """func 大于十(n) -> Bool = (n) => n > 10
#：{
  result = []
  i = 1
  while i <= 20 {
    if 大于十(i) { result = result + [i] }
    i = i + 1
  }
  [result]
}""",
    [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
)

# ================================================================
# 7. Lambda 柯里化链式调用
# ================================================================
print("\n=== 7. Lambda 柯里化链式调用 ===")

run_multi(
    "柯里化加法",
    """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
#：{
  r1 = 加(3)(5)
  r2 = 加(10)(20)
  [r1]
  [r2]
}""",
    [8, 30],
)

run(
    "柯里化减法",
    """func 减(a: Int, b: Int) -> Int = (a, b) => a - b
#：{
  [减(100)(30)]
}""",
    70,
)

run_multi(
    "柯里化三元条件",
    """func 选择(cond: Bool, a: Int, b: Int) -> Int = (cond, a, b) =>
  cond ? a : b
#：{
  r1 = 选择(true)(100)(200)
  r2 = 选择(false)(100)(200)
  [r1]
  [r2]
}""",
    [100, 200],
)

run(
    "柯里化矩阵坐标",
    """func 矩阵索引(row: Int, col: Int, size: Int) -> Int = (row, col, size) =>
  row * size + col
#：{
  [矩阵索引(2)(3)(5)]
}""",
    13,
)

# ================================================================
# 8. 多参数 Lambda 嵌套
# ================================================================
print("\n=== 8. 多参数 Lambda 嵌套 ===")

run_multi(
    "嵌套 Lambda 二元运算",
    """func 二元运算(op: String, a: Int, b: Int) -> Int = (op, a, b) =>
  op = "+" ? a + b :
  op = "-" ? a - b :
  op = "*" ? a * b :
  op = "/" ? a / b :
  0
#：{
  r1 = 二元运算("+")(3)(4)
  r2 = 二元运算("*")(5)(6)
  r3 = 二元运算("-")(100)(37)
  [r1]
  [r2]
  [r3]
}""",
    [7, 30, 63],
)

run_multi(
    "嵌套 Lambda 最大最小",
    """func 最大(a: Int, b: Int) -> Int = (a, b) => a >= b ? a : b
func 最小(a: Int, b: Int) -> Int = (a, b) => a <= b ? a : b
#：{
  r1 = 最大(3)(7)
  r2 = 最小(3)(7)
  r3 = 最大(最大(1)(5))(3)
  [r1]
  [r2]
  [r3]
}""",
    [7, 3, 5],
)

# ================================================================
# 9. Match 模式匹配 + Lambda
# ================================================================
print("\n=== 9. Match 模式匹配 + Lambda ===")

run(
    "match 基础",
    """#：{
  match 2 {
    | 1 => 10
    | 2 => 20
    | 3 => 30
    | _ => 99
  }
}""",
    20,
)

run(
    "match 通配符",
    """#：{
  match 99 {
    | 1 => 10
    | 2 => 20
    | _ => 0
  }
}""",
    0,
)

run(
    "match 与 lambda 组合",
    """func 平方(x) -> Int = (x) => x * x
func 立方(x) -> Int = (x) => x * x * x
#：{
  fn = match 2 {
    | 1 => 平方
    | 2 => 立方
    | _ => (x) => x
  }
  [fn(5)]
}""",
    125,
)

run(
    "match 嵌套条件",
    """#：{
  n = 15
  match n {
    | 0 => 0
    | _ => if n > 10 { [100] } 否则 { [0] }
  }
}""",
    100,
)

run(
    "match 负数通配",
    """#：{
  match -1 {
    | 0 => 0
    | _ => 1
  }
}""",
    1,
)

# ================================================================
# 10. 组合：函数式 + 命令式混合
# ================================================================
print("\n=== 10. 组合：函数式 + 命令式混合 ===")

run(
    "累加器模式（for + lambda + 闭包）",
    """#：{
  total = 0
  multiplier = 3
  for i in [1, 2, 3, 4, 5] {
    total = total + i * multiplier
  }
  [total]
}""",
    45,
)

run(
    "链式柯里化：三个参数",
    """func 三参数(a: Int, b: Int, c: Int) -> Int = (a, b, c) =>
  a + b * c
#：{
  [三参数(2)(3)(4)]
}""",
    14,
)

run_multi(
    "嵌套 Lambda 返回函数（工厂模式）",
    """#：{
  factory = (multiplier) => (x) => x * multiplier
  double = factory(2)
  triple = factory(3)
  r1 = double(10)
  r2 = triple(10)
  [r1]
  [r2]
}""",
    [20, 30],
)

run(
    "递归 Lambda + while 循环",
    """func 幂(base: Int, exp: Int) -> Int = (base, exp) =>
  exp <= 0 ? 1 : base * 幂(base)(exp - 1)
#：{
  result = 1
  n = 0
  while n < 5 {
    result = 幂(2)(n)
    n = n + 1
  }
  [result]
}""",
    16,
)

run_multi(
    "Y组合子风格的递归",
    """func 阶乘(n: Int) -> Int = (n) =>
  n <= 1 ? 1 : n * 阶乘(n - 1)
func 斐波那契(n: Int) -> Int = (n) =>
  n <= 1 ? n : 斐波那契(n - 1) + 斐波那契(n - 2)
#：{
  [阶乘(7)]
  [斐波那契(8)]
}""",
    [5040, 21],
)

run(
    "嵌套代码块作用域",
    """#：{
  x = 1
  {
    y = x + 1
    {
      z = y + 1
      [z]
    }
  }
}""",
    3,
)

run(
    "复杂组合：while + lambda + if-else",
    """func 累加(start: Int, end: Int) -> Int = (start, end) =>
  start > end ? 0 : start + 累加(start + 1)(end)
#：{
  [累加(1)(10)]
}""",
    55,
)

run(
    "Match + if 嵌套",
    """#：{
  n = 5
  match n {
    | 0 => 0
    | _ => if n > 3 { [10] } 否则 { [20] }
  }
}""",
    10,
)

run(
    "Match + 函数选择",
    """func 平方(x) -> Int = (x) => x * x
func 立方(x) -> Int = (x) => x * x * x
func 恒等(x) -> Int = (x) => x
#：{
  op = 2
  fn = match op {
    | 0 => 恒等
    | 1 => 平方
    | 2 => 立方
    | _ => 恒等
  }
  r = fn(4)
  [r]
}""",
    64,
)

# ================================================================
# 总结
# ================================================================
print("\n" + "=" * 60)
print(f"测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
print("=" * 60)

if failed > 0:
    sys.exit(1)
