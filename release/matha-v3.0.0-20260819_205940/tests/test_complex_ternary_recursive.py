# -*- coding: utf-8 -*-
"""Matha 复杂嵌套三元表达式 + 递归调用综合测试。

验证修复后以下特性正常工作：
  1. 三元表达式基本形式：cond ? then : else
  2. 嵌套三元：a ? b : (c ? d : e)
  3. 三元作为函数定义体中的核心逻辑
  4. 递归函数（阶乘、斐波那契、幂函数）
  5. 多参数柯里化函数 + 三元分发
  6. 闭包捕获 + 三元组合
  7. 函数作为参数传递 + 三元条件返回值
"""
import sys
import time

sys.path.insert(0, '.')
from src.interp import interpret


def run_test(name: str, src: str, expected) -> bool:
    """运行单个测试用例，返回是否通过。"""
    start = time.perf_counter()
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        ok = result == expected
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = 'OK' if ok else 'FAIL'
        print(f"  {status} {name}: got={result!r} expected={expected!r}  ({elapsed_ms:.1f}ms)")
        return ok
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"  FAIL {name}: {type(e).__name__}: {e}  ({elapsed_ms:.1f}ms)")
        return False


def main():
    print("=" * 70)
    print("Matha 复杂嵌套三元 + 递归调用 综合测试")
    print("=" * 70)

    passed = 0
    failed = 0

    # ================================================================
    # 1. 基础三元表达式
    # ================================================================
    print("\n【1. 基础三元表达式】")
    cases = [
        ("三元假路径",      "#：{ [1 > 2 ? 100 : 200] }",          200),
        ("三元真路径",      "#：{ [2 > 1 ? 100 : 200] }",          100),
        ("三元嵌套外层真",  "#：{ [1 < 2 ? (3 > 4 ? 10 : 20) : 30] }", 20),
        ("三元嵌套外层假",  "#：{ [1 > 2 ? 10 : (3 > 4 ? 20 : 30)] }", 30),
        ("三元嵌套双假",    "#：{ [1 > 2 ? 10 : (3 > 4 ? 20 : 30)] }", 30),
        ("三元三层层叠",    "#：{ [1>2?1:(3>4?2:(5>6?3:4))] }",     4),
        ("三元含算术",      "#：{ [(3+2) > 4 ? (3*2) : (3+2)] }",   6),
        ("三元含比较链",    "#：{ [10 > 5 ? (5 > 3 ? 1 : 0) : 0] }", 1),
    ]
    for name, src, expected in cases:
        if run_test(name, src, expected):
            passed += 1
        else:
            failed += 1

    # ================================================================
    # 2. 递归函数（三元作为核心条件）
    # ================================================================
    print("\n【2. 递归函数（三元条件）】")
    rec_cases = [
        ("阶乘(5)",
         "func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(5)] }",
         120),
        ("阶乘(6)",
         "func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(6)] }",
         720),
        ("阶乘(10)",
         "func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(10)] }",
         3628800),
        ("斐波那契(5)",
         "func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)\n#：{ [斐波那契(5)] }",
         5),
        ("斐波那契(10)",
         "func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)\n#：{ [斐波那契(10)] }",
         55),
        ("幂函数(2,10)",
         "func 幂(base: Int, exp: Int) -> Int = (base, exp) => exp <= 0 ? 1 : base * 幂(base)(exp - 1)\n#：{ [幂(2)(10)] }",
         1024),
        ("幂函数(3,5)",
         "func 幂(base: Int, exp: Int) -> Int = (base, exp) => exp <= 0 ? 1 : base * 幂(base)(exp - 1)\n#：{ [幂(3)(5)] }",
         243),
        ("二元运算分发",
         "func 二元运算(op: String, a: Int, b: Int) -> Int = (op, a, b) =>\n  op = \"+\" ? a + b :\n  op = \"-\" ? a - b :\n  op = \"*\" ? a * b :\n  op = \"/\" ? a / b :\n  0\n#：{ [二元运算(\"+\")(3)(4)] }",
         7),
        ("最大函数",
         "func 最大(a: Int, b: Int) -> Int = (a, b) => a >= b ? a : b\n#：{ [最大(3)(7)] }",
         7),
        ("最小函数",
         "func 最小(a: Int, b: Int) -> Int = (a, b) => a <= b ? a : b\n#：{ [最小(3)(7)] }",
         3),
    ]
    for name, src, expected in rec_cases:
        if run_test(name, src, expected):
            passed += 1
        else:
            failed += 1

    # ================================================================
    # 3. 柯里化 + 三元组合
    # ================================================================
    print("\n【3. 柯里化 + 三元组合】")
    curry_cases = [
        ("柯里化加法",
         "func 加(a: Int, b: Int) -> Int = (a, b) => a + b\n#：{ [加(3)(5)] }",
         8),
        ("柯里化减法",
         "func 减(a: Int, b: Int) -> Int = (a, b) => a - b\n#：{ [减(10)(3)] }",
         7),
        ("柯里化三元条件",
         "func 条件值(条件: Bool, 真值: Int, 假值: Int) -> Int = (条件, 真值, 假值) => 条件 ? 真值 : 假值\n#：{ [条件值(真)(99)(0)] }",
         99),
        ("柯里化三元条件假",
         "func 条件值(条件: Bool, 真值: Int, 假值: Int) -> Int = (条件, 真值, 假值) => 条件 ? 真值 : 假值\n#：{ [条件值(假)(99)(0)] }",
         0),
    ]
    for name, src, expected in curry_cases:
        if run_test(name, src, expected):
            passed += 1
        else:
            failed += 1

    # ================================================================
    # 4. 高阶函数 + 递归 + 三元
    # ================================================================
    print("\n【4. 高阶函数 + 递归 + 三元】")
    high_cases = [
        ("compose_2层",
         "func 加一(x: Int) -> Int = (x) => x + 1\n"
         "func 加倍(x: Int) -> Int = (x) => x * 2\n"
         "#：{\n"
         "  h = (f, g) => (x) => f(g(x))\n"
         "  r = h(加一)(加倍)(5)\n"
         "  [r]\n"
         "}",
         11),
        ("函数作为参数_三元返回",
         "func 选择(f, g, cond: Bool) -> Int = (f, g, cond) => cond ? f(3) : g(3)\n"
         "func 平方(x) -> Int = (x) => x * x\n"
         "func 立方(x) -> Int = (x) => x * x * x\n"
         "#：{ [选择(平方)(立方)(真)] }",
         9),
        ("函数作为参数_三元返回假",
         "func 选择(f, g, cond: Bool) -> Int = (f, g, cond) => cond ? f(3) : g(3)\n"
         "func 平方(x) -> Int = (x) => x * x\n"
         "func 立方(x) -> Int = (x) => x * x * x\n"
         "#：{ [选择(平方)(立方)(假)] }",
         27),
        ("闭包捕获变量",
         "#：{\n"
         "  x = 10\n"
         "  r = (n) => n + x\n"
         "  [r(5)]\n"
         "}",
         15),
        ("嵌套闭包三元",
         "#：{\n"
         "  base = 5\n"
         "  makeAdder = (b) => (n) => n + b\n"
         "  adder = makeAdder(base)\n"
         "  r = adder(3)\n"
         "  [r]\n"
         "}",
         8),
    ]
    for name, src, expected in high_cases:
        if run_test(name, src, expected):
            passed += 1
        else:
            failed += 1

    # ================================================================
    # 5. 边界：深嵌套三元 + 深递归
    # ================================================================
    print("\n【5. 边界测试：深嵌套 + 深递归】")
    edge_cases = [
        ("5层嵌套三元",
         "#：{ [1>2?1:(2>3?2:(3>4?3:(4>5?4:5)))] }",
         5),
        ("7层嵌套三元",
         "#：{ [1>2?1:(2>3?2:(3>4?3:(4>5?4:(5>6?5:(6>7?6:7)))))] }",
         7),
        ("阶乘(12)",
         "func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(12)] }",
         479001600),
        ("斐波那契(15)",
         "func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)\n#：{ [斐波那契(15)] }",
         610),
        ("三元赋值",
         "#：{\n"
         "  m = 3 > 2 ? 100 : 200\n"
         "  [m]\n"
         "}",
         100),
        ("三元在for循环条件",
         "#：{\n"
         "  sum = 0\n"
         "  for i in [1, 2, 3, 4, 5] {\n"
         "    sum = sum + (i > 3 ? 10 : i)\n"
         "  }\n"
         "  [sum]\n"
         "}",
         26),
    ]
    for name, src, expected in edge_cases:
        if run_test(name, src, expected):
            passed += 1
        else:
            failed += 1

    # ================================================================
    # 总结
    # ================================================================
    total = passed + failed
    print("\n" + "=" * 70)
    print(f"测试结果：{passed} 通过, {failed} 失败 (共 {total})")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
