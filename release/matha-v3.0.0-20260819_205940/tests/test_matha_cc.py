# -*- coding: utf-8 -*-
"""Matha LLVM 工具链验证测试。"""
import sys, time
sys.path.insert(0, r"D:\trae")

print("=" * 60)
print("Matha LLVM 工具链验证")
print("=" * 60)

from src.compiler.matha_cc import (
    MathaLexer, MathaParser, MathaFrontend,
    MathaLLVMGenerator, MathaCompiler,
    matha_compile, matha_run, matha_to_llvm,
)

# ============================================================
# 1. 词法分析测试
# ============================================================
print("\n【1. 词法分析】")
lexer = MathaLexer('result = sin(3.14) + cos(1.57)')
tokens = lexer.tokenize()
print(f"  Token 数量: {len(tokens)}")
for i, tok in enumerate(tokens):
    print(f"    [{i:2d}] {tok}")

# ============================================================
# 2. 语法分析测试 (简单表达式)
# ============================================================
print("\n【2. 语法分析 - 简单表达式】")
simple = "result = 1 + 2"
lexer2 = MathaLexer(simple)
tokens2 = lexer2.tokenize()
print(f"  源码: {simple!r}")
for i, tok in enumerate(tokens2):
    print(f"    [{i:2d}] {tok}")
parser2 = MathaParser(tokens2)
ast2 = parser2.parse()
print(f"  AST: {len(ast2.decls)} 声明")
for decl in ast2.decls:
    print(f"    - {type(decl).__name__}")

# ============================================================
# 3. 语法分析测试 (函数调用)
# ============================================================
print("\n【3. 语法分析 - 函数调用】")
func_src = "x = sin(3.14)"
lexer3 = MathaLexer(func_src)
tokens3 = lexer3.tokenize()
print(f"  源码: {func_src!r}")
for i, tok in enumerate(tokens3):
    print(f"    [{i:2d}] {tok}")
parser3 = MathaParser(tokens3)
ast3 = parser3.parse()
print(f"  AST: {len(ast3.decls)} 声明")
for decl in ast3.decls:
    print(f"    - {type(decl).__name__}")

# ============================================================
# 4. 语法分析测试 (带 + 的表达式)
# ============================================================
print("\n【4. 语法分析 - 带 + 的表达式】")
add_src = "x = sin(3.14) + cos(1.57)"
lexer4 = MathaLexer(add_src)
tokens4 = lexer4.tokenize()
print(f"  源码: {add_src!r}")
for i, tok in enumerate(tokens4):
    print(f"    [{i:2d}] {tok}")
try:
    parser4 = MathaParser(tokens4)
    ast4 = parser4.parse()
    print(f"  AST: {len(ast4.decls)} 声明")
    for decl in ast4.decls:
        print(f"    - {type(decl).__name__}")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 5. LLVM IR 生成测试
# ============================================================
print("\n【5. LLVM IR 生成】")
frontend = MathaFrontend()
matha_ir = frontend.compile(ast2)
generator = MathaLLVMGenerator("test_module")
llvm_ir = generator.generate(matha_ir)
print(f"  LLVM IR 长度: {len(llvm_ir)} 字符")
print(f"  包含 target triple: {'target triple' in llvm_ir}")
print(f"  包含 main 函数: {'define double @main' in llvm_ir}")

# ============================================================
# 6. 完整编译测试
# ============================================================
print("\n【6. 完整编译】")
compiler = MathaCompiler(optimize=True)
test_cases = [
    ("简单算术", "x = 1 + 2 * 3"),
    ("三角函数", "x = sin(3.14)"),
    ("函数定义", "add = (a, b) => a + b"),
]
for name, source in test_cases:
    try:
        llvm = matha_to_llvm(source)
        print(f"  OK {name}: LLVM IR {len(llvm)} 字符")
    except Exception as e:
        print(f"  FAIL {name}: {type(e).__name__}: {e}")

# ============================================================
# 7. 性能基准
# ============================================================
print("\n【7. 性能基准】")
from src.interp import Interpreter
from src.parser import parse as interp_parse
interp = Interpreter()

prog = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"
t0 = time.perf_counter()
for _ in range(1000):
    interp.run(interp_parse(prog))
interp_ms = (time.perf_counter() - t0) * 1000
print(f"  解释器 1000次: {interp_ms:.0f}ms")

t0 = time.perf_counter()
for _ in range(100):
    matha_to_llvm(prog)
compile_ms = (time.perf_counter() - t0) * 1000
print(f"  LLVM 翻译 100次: {compile_ms:.0f}ms")
print(f"  单次翻译: {compile_ms/100:.1f}ms")

# ============================================================
# 8. 工具链信息
# ============================================================
print("\n【8. 工具链信息】")
try:
    import subprocess
    result = subprocess.run(['llc', '--version'], capture_output=True, timeout=5)
    if result.returncode == 0:
        print("  LLVM llc: 可用")
    else:
        print("  LLVM llc: 不可用 (回退到 Python 解释)")
except FileNotFoundError:
    print("  LLVM llc: 未安装")

print(f"  编译器统计: {compiler.stats}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
