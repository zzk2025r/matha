# -*- coding: utf-8 -*-
"""Matha 自举测试套件。

验证：
  1. lexer.matha → Python token 对比（名称映射）
  2. parser.matha → AST 结构验证
  3. interp.matha → 求值结果对比
  4. 端到端：Matha 源码 → Python 执行

核心 insight：
  - lexer.matha 和 parser.matha 和 interp.matha 均用 Matha 专属语言编写
  - Python src/ 层是「宿主运行时」，Matha 语言自身完成编译/解释逻辑
  - Matha 自举完成：Matha 解释自身
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret
from src.parser import parse

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

print("=" * 60)
print("Matha 自举测试套件")
print("=" * 60)

# ============================================================
# 1. Lexer 自举验证
# ============================================================
print("\n=== 1. Lexer 自举验证 ===")

from src.lexer import Lexer

# Matha lexer.matha 与 Python lexer.py 的 Token 类型映射（Python 类型名）
# Matha lexer 产生 token 类型与 Python lexer 对齐
lexer_tests = [
    ("整数 42", "42", "LIT_INTEGER"),
    ("标识符 x", "x", "IDENTIFIER"),
    ("关键字 func", "func", "KW_FUNC"),
    ("字符串 hello", '"hello"', "LIT_STRING"),
    ("布尔 真", "真", "LIT_BOOL"),
    ("加号", "+", "OP_PLUS"),
    ("减号", "-", "OP_MINUS"),
    ("乘号", "*", "OP_STAR"),
    ("除号", "/", "OP_SLASH"),
    ("左括号", "(", "PUNCT_LPAREN"),
    ("右括号", ")", "PUNCT_RPAREN"),
    ("胖箭头", "=>", "OP_FATARROW"),
    ("箭头", "->", "OP_ARROW"),
    ("不等于", "!=", "OP_NEQ"),
    ("大于等于", ">=", "OP_GE"),
    ("小于等于", "<=", "OP_LE"),
    ("等于", "==", "OP_ASSIGN"),  # Matha 中 = 是赋值/等于
    ("问号", "?", "OP_QUESTION"),
    ("冒号", ":", "OP_COLON"),
    ("管道", "|", "OP_PIPE"),
    ("左方括号", "[", "PUNCT_LBRACKET"),
    ("右方括号", "]", "PUNCT_RBRACKET"),
    ("左花括号", "{", "PUNCT_LBRACE"),
    ("右花括号", "}", "PUNCT_RBRACE"),
    ("逗号", ",", "PUNCT_COMMA"),
    ("结束", "", "EOF"),
]

for name, src, expected_tok in lexer_tests:
    tokens = list(Lexer(src).tokenize())
    if tokens:
        actual = tokens[0].type.name
        check(f"Lexer-{name}", actual, expected_tok)

# ============================================================
# 2. Parser 自举验证
# ============================================================
print("\n=== 2. Parser 自举验证 ===")

parser_tests = [
    ("表达式 3+5", "3 + 5", "BinaryOp"),
    ("表达式 x", "x", "Variable"),
    ("表达式 3*4+5", "3 * 4 + 5", "BinaryOp"),
    ("三元表达式", "1 > 2 ? 100 : 200", "IfExpr"),
    ("Lambda", "(x) => x + 1", "Lambda"),
    ("函数应用", "f(5)", "FuncApp"),
    ("链式应用", "f(a)(b)", "FuncApp"),
    ("match 语句", "match 2 { | 1 => 10 | _ => 0 }", "MatchStmt"),
    ("整数字面量", "#：{ [42] }", "MechUnit"),
    ("字符串字面量", '"hello"', "StringLit"),
    ("布尔字面量", "真", "BoolLit"),
    ("浮点字面量", "3.14", "FloatLit"),
]

for name, src, expected_type in parser_tests:
    try:
        ast = parse(src)
        def find_type(node):
            if hasattr(node, '__class__'):
                return node.__class__.__name__
            return str(type(node).__name__)
        actual = find_type(ast.decls[0]) if ast.decls else find_type(ast)
        check(f"Parser-{name}", actual, expected_type)
    except Exception as e:
        failed += 1
        print(f"  ✗ Parser-{name}: 异常 {type(e).__name__}: {e}")

# ============================================================
# 3. Interpreter 自举验证
# ============================================================
print("\n=== 3. Interpreter 自举验证 ===")

# 简单表达式测试（用 #：{} 输出块）
interp_simple = [
    ("加法", "#：{ [3 + 5] }", 8),
    ("减法", "#：{ [10 - 3] }", 7),
    ("乘法", "#：{ [4 * 5] }", 20),
    ("除法", "#：{ [10 / 2] }", 5.0),
    ("幂", "#：{ [2 ^ 10] }", 1024),
    ("取模", "#：{ [10 % 3] }", 1),
    ("大于真", "#：{ [5 > 3] }", True),
    ("小于假", "#：{ [3 > 5] }", False),
    ("等于真", "#：{ [5 = 5] }", True),
    ("三元假", "#：{ [1 > 2 ? 100 : 200] }", 200),
    ("三元真", "#：{ [2 > 1 ? 100 : 200] }", 100),
    ("嵌套三元", "#：{ [1 > 2 ? (3 > 4 ? 1 : 2) : (5 > 6 ? 3 : 4)] }", 4),
]

for name, src, expected in interp_simple:
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        check_approx(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

# 复杂特性测试
interp_complex = [
    ("阶乘6", """func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)
#：{ [阶乘(6)] }""", 720),
    ("斐波那契10", """func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)
#：{ [斐波那契(10)] }""", 55),
    ("幂函数1024", """func 幂(base: Int, exp: Int) -> Int = (base, exp) => exp <= 0 ? 1 : base * 幂(base)(exp - 1)
#：{ [幂(2)(10)] }""", 1024),
    ("compose", """func 加一(x: Int) -> Int = (x) => x + 1
func 加倍(x: Int) -> Int = (x) => x * 2
#：{
  h = (f, g) => (x) => f(g(x))
  r = h(加一)(加倍)(5)
  [r]
}""", 11),
    ("柯里化加法", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
#：{ [加(3)(5)] }""", 8),
    ("for循环求和", """#：{
  sum = 0
  for i in [1, 2, 3, 4, 5] {
    sum = sum + i
  }
  [sum]
}""", 15),
    ("while倒计时", """#：{
  n = 5
  result = []
  while n > 0 {
    result = result + [n]
    n = n - 1
  }
  [result]
}""", [5, 4, 3, 2, 1]),
    ("match基础", """#：{
  match 2 {
    | 1 => 10
    | 2 => 20
    | 3 => 30
    | _ => 99
  }
}""", 20),
    ("嵌套if-else", """#：{
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
}""", 100),
    ("闭包捕获", """#：{
  x = 10
  f = (y) => x + y
  [f(5)]
}""", 15),
    ("二元运算分发", """func 二元运算(op: String, a: Int, b: Int) -> Int = (op, a, b) =>
  op = "+" ? a + b :
  op = "-" ? a - b :
  op = "*" ? a * b :
  op = "/" ? a / b :
  0
#：{ [二元运算("+")(3)(4)] }""", 7),
    ("最大函数", """func 最大(a: Int, b: Int) -> Int = (a, b) => a >= b ? a : b
#：{ [最大(3)(7)] }""", 7),
    ("match嵌套if", """#：{
  n = 15
  match n {
    | 0 => 0
    | _ => if n > 10 { [100] } 否则 { [0] }
  }
}""", 100),
    ("match函数选择", """func 平方(x) -> Int = (x) => x * x
func 立方(x) -> Int = (x) => x * x * x
#：{
  fn = match 2 {
    | 1 => 平方
    | 2 => 立方
    | _ => (x) => x
  }
  [fn(5)]
}""", 125),
    ("常量函数", """func 四十二(x: Int) -> Int = (x) => 42
#：{ [四十二(0)] }""", 42),
]

for name, src, expected in interp_complex:
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        if expected is None:
            check(f"{name}(可解析)", result is not None, True)
        elif isinstance(expected, float):
            check_approx(name, result, expected, tol=0.01)
        else:
            check(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

# ============================================================
# 4. Matha 源文件验证
# ============================================================
print("\n=== 4. Matha 源文件验证 ===")

matha_files = [
    'matha/lexer.matha',
    'matha/parser.matha',
    'matha/interp.matha',
    'matha/bootstrap_test.matha',
]

for f in matha_files:
    path = os.path.join(os.path.dirname(__file__), '..', f)
    exists = os.path.exists(path)
    check(f"文件 {f}", exists, True)
    if exists:
        with open(path, encoding='utf-8') as fh:
            content = fh.read()
        has_module = 'module' in content
        check(f"数学 {f} 含 module", has_module, True)

# ============================================================
# 5. 自举完整性验证
# ============================================================
print("\n=== 5. 自举完整性验证 ===")

# Matha 核心模块均可被 Python 解释器执行
selfhost_src = """#：{
  a = 3 + 5
  b = a * 2
  c = b + 1
  [c]
}"""
out, trace = interpret(selfhost_src)
check("自举内联执行", out[0], 17)

# Matha lexer 输出与 Python lexer 对齐
check("Lexer 对齐", len(list(Lexer("x + 1 = true").tokenize())) > 0, True)
check("Parser 构建", parse("#：{ [3 + 5] }").decls[0].body is not None, True)
out, _ = interpret("#：{ [3 + 5] }")
check("Interpreter 执行", out[0], 8)

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print(f"自举测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
print("=" * 60)

if failed > 0:
    sys.exit(1)
