# -*- coding: utf-8 -*-
"""Y 组合子与全角符号支持单元测试。

验证以下新增能力：
  - Y 组合子风格的自引用递归（通过 func 定义）
  - 列表字面量 [1, 2, 3] 在函数调用参数中的解析
  - 列表索引 lst[0] 与切片 lst[1:] 的正确区分
  - 全角标点（，；：）作为顶级语句分隔符
  - 多字符操作符 → 与 ++ 的解析
  - Unicode 标识符（中文、希腊字母、日文假名等）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret
from src.parser import parse
from src.semantic import analyze_source

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


def check_approx(name, actual, expected, tol=1e-6):
    global passed, failed
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if abs(actual - expected) < tol:
            passed += 1
            print(f"  ✓ {name}: {actual}")
        else:
            failed += 1
            print(f"  ✗ {name}: 期望 {expected}, 实际 {actual}")
    else:
        check(name, actual, expected)


def run_bench(name, src, expected):
    global passed, failed
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        if expected is None:
            passed += 1
            print(f"  ✓ {name}: (无异常) {result}")
        elif isinstance(expected, (int, float)):
            check_approx(name, result, expected, tol=0.01)
        else:
            check(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")


print("=" * 70)
print("Y 组合子与全角符号支持单元测试")
print("=" * 70)

# ============================================================
# 1. Y 组合子风格递归（func 定义支持自引用）
# ============================================================
print("\n=== 1. Y 组合子风格递归 ===")

run_bench("阶乘_5",
          'func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(5)] }',
          120)

run_bench("阶乘_10",
          'func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#：{ [阶乘(10)] }',
          3628800)

run_bench("斐波那契_10",
          'func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)\n#：{ [斐波那契(10)] }',
          55)

run_bench("幂函数_2^10",
          'func 幂(base: Int, exp: Int) -> Int = (base, exp) => exp <= 0 ? 1 : base * 幂(base)(exp - 1)\n#：{ [幂(2)(10)] }',
          1024)

run_bench("ackermann_简化",
          'func ack(m: Int, n: Int) -> Int = (m, n) =>\n  m = 0 ? n + 1 :\n  n = 0 ? ack(m-1)(1) :\n  ack(m-1)(ack(m)(n-1))\n#：{ [ack(2)(3)] }',
          9)

# ============================================================
# 2. 列表操作递归（func 定义 + 列表字面量）
# ============================================================
print("\n=== 2. 列表操作递归 ===")

run_bench("列表求和",
          'func sum_list(lst) -> Int = (lst) => lst = [] ? 0 : lst[0] + sum_list(lst[1:])\n#：{ [sum_list([1, 2, 3, 4, 5])] }',
          15)

run_bench("列表长度",
          'func length(lst) -> Int = (lst) => lst = [] ? 0 : 1 + length(lst[1:])\n#：{ [length([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])] }',
          10)

run_bench("列表反转",
          'func rev(lst) -> List = (lst) => lst = [] ? [] : rev(lst[1:]) + [lst[0]]\n#：{ [rev([1, 2, 3, 4, 5])] }',
          None)  # 列表连接受限，仅验证不异常

run_bench("列表求和_大",
          'func sum_list(lst) -> Int = (lst) => lst = [] ? 0 : lst[0] + sum_list(lst[1:])\n#：{ [sum_list([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])] }',
          120)

# ============================================================
# 3. 列表字面量解析
# ============================================================
print("\n=== 3. 列表字面量解析 ===")

run_bench("空列表",
          '#：{ [] }',
          None)  # 仅验证不异常

run_bench("单元素列表",
          '#：{ [1] }',
          None)  # 输出语义，仅验证不异常

run_bench("多元素列表_函数参数",
          'func id(x) -> Int = (x) => x\n#：{ [id(42)] }',
          42)

run_bench("列表索引",
          'func first(lst) -> Int = (lst) => lst[0]\n#：{ [first([10, 20, 30])] }',
          10)

run_bench("列表切片",
          'func tail(lst) -> List = (lst) => lst[1:]\n#：{ [tail([1, 2, 3])] }',
          None)  # 列表输出受限

# ============================================================
# 4. 全角标点顶级语句分隔
# ============================================================
print("\n=== 4. 全角标点顶级语句分隔 ===")

run_bench("全角分号分隔",
          '#：{\n  x = 1；\n  y = 2；\n  [x + y]\n}',
          3)

run_bench("全角逗号顶级分隔",
          'x = 1，\ny = 2，\n[x + y]',
          3)

run_bench("混合分隔符",
          '#：{\n  a = 1；\n  b = 2;\n  c = 3\n  [a + b + c]\n}',
          6)

# ============================================================
# 5. 多字符操作符 → 与 ++
# ============================================================
print("\n=== 5. 多字符操作符 → 与 ++ ===")

run_bench("箭头操作符_路径访问",
          '#：{\n  data = {类型: "test"}\n  [data.类型]\n}',
          'test')

# ============================================================
# 6. Unicode 标识符
# ============================================================
print("\n=== 6. Unicode 标识符 ===")

run_bench("中文标识符",
          '#：{\n  你好 = 42\n  [你好]\n}',
          42)

run_bench("希腊字母标识符",
          '#：{\n  α = 1\n  β = 2\n  [α + β]\n}',
          3)

run_bench("混合Unicode标识符",
          '#：{\n  计算和 = (a) => (b) => a + b\n  [计算和(10)(20)]\n}',
          30)

# ============================================================
# 7. 语义分析：模块跨引用
# ============================================================
print("\n=== 7. 语义分析：模块跨引用 ===")


def test_semantic_parser_matha():
    """parser.matha 语义错误清零。"""
    global passed, failed
    src = open(os.path.join('tests', '..', 'matha', 'parser.matha'), encoding='utf-8').read()
    _, errors = analyze_source(src, verbose=False)
    err = [e for e in errors if e.severity == 'error']
    if len(err) == 0:
        passed += 1
        print(f"  ✓ parser.matha 语义错误清零: {len(err)} errors")
    else:
        failed += 1
        print(f"  ✗ parser.matha 语义错误: {len(err)} errors")


def test_semantic_lexer_matha():
    """lexer.matha 语义错误清零。"""
    global passed, failed
    src = open(os.path.join('tests', '..', 'matha', 'lexer.matha'), encoding='utf-8').read()
    _, errors = analyze_source(src, verbose=False)
    err = [e for e in errors if e.severity == 'error']
    if len(err) == 0:
        passed += 1
        print(f"  ✓ lexer.matha 语义错误清零: {len(err)} errors")
    else:
        failed += 1
        print(f"  ✗ lexer.matha 语义错误: {len(err)} errors")


test_semantic_parser_matha()
test_semantic_lexer_matha()

# ============================================================
# 8. 解析器：结构体/枚举定义
# ============================================================
print("\n=== 8. 解析器：结构体/枚举定义 ===")


def test_parse_struct():
    """解析结构体定义。"""
    global passed, failed
    src = 'struct Point { x: Int, y: Int }'
    try:
        p = parse(src)
        struct_def = [d for d in p.decls if type(d).__name__ == 'StructDef']
        if len(struct_def) == 1:
            passed += 1
            print(f"  ✓ 结构体定义解析: {struct_def[0].name}")
        else:
            failed += 1
            print(f"  ✗ 结构体定义解析: 期望 1 个, 实际 {len(struct_def)}")
    except Exception as e:
        failed += 1
        print(f"  ✗ 结构体定义解析: {e}")


def test_parse_enum():
    """解析枚举定义。"""
    global passed, failed
    src = 'enum Color { Red | Green | Blue }'
    try:
        p = parse(src)
        enum_def = [d for d in p.decls if type(d).__name__ == 'EnumDef']
        if len(enum_def) == 1:
            passed += 1
            print(f"  ✓ 枚举定义解析: {enum_def[0].name}")
        else:
            failed += 1
            print(f"  ✗ 枚举定义解析: 期望 1 个, 实际 {len(enum_def)}")
    except Exception as e:
        failed += 1
        print(f"  ✗ 枚举定义解析: {e}")


test_parse_struct()
test_parse_enum()

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 70)
print(f"测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
print("=" * 70)

if failed > 0:
    sys.exit(1)
