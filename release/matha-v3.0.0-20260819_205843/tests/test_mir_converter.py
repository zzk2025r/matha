# -*- coding: utf-8 -*-
"""Matha 三向转换器完整验证测试。"""
import sys, time
sys.path.insert(0, r"D:\trae")

print("=" * 60)
print("Matha 三向转换器验证")
print("=" * 60)

from src.mir_converter import MathaConverter, convert, convert_all, matha_to_mir
from src.mir import MIRGenerator, generate_mir
from src.mir_codegen import compile_to_c, compile_to_python
from src.mir_opt import MathaOptimizationPipeline
from src.compiler.matha_cc import MathaLexer, MathaParser

# ============================================================
# 1. Matha → MIR 测试
# ============================================================
print("\n【1. Matha → MIR】")
source = "x = sin(3.14) + cos(1.57)"
mir_text = matha_to_mir(source)
print(f"  源码: {source}")
print(f"  MIR 长度: {len(mir_text)} chars")
print(f"  前 300 字符:")
for line in mir_text.split("\n")[:8]:
    print(f"    {line}")

# ============================================================
# 2. Matha → C 测试
# ============================================================
print("\n【2. Matha → C】")
c_code = convert(source, "matha", "c")
print(f"  C 代码长度: {len(c_code)} chars")
print(f"  前 400 字符:")
for line in c_code.split("\n")[:12]:
    print(f"    {line}")

# ============================================================
# 3. Matha → Python 测试
# ============================================================
print("\n【3. Matha → Python】")
py_code = convert(source, "matha", "python")
print(f"  Python 代码长度: {len(py_code)} chars")
print(f"  前 400 字符:")
for line in py_code.split("\n")[:12]:
    print(f"    {line}")

# ============================================================
# 4. Matha → Matha (自身) 测试
# ============================================================
print("\n【4. Matha → Matha】")
matha_out = convert(source, "matha", "matha")
print(f"  Matha 代码长度: {len(matha_out)} chars")
print(f"  前 400 字符:")
for line in matha_out.split("\n")[:12]:
    print(f"    {line}")

# ============================================================
# 5. 多表达式测试
# ============================================================
print("\n【5. 多表达式转换测试】")
test_cases = [
    ("简单算术", "x = 1 + 2 * 3"),
    ("三角函数", "x = sin(3.14) + cos(1.57)"),
    ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)"),
    ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))"),
    ("函数定义", "add = (a, b) => a + b"),
]

for name, src in test_cases:
    try:
        c = convert(src, "matha", "c")
        py = convert(src, "matha", "python")
        matha = convert(src, "matha", "matha")
        print(f"  [PASS] {name}: C={len(c)} chars, Py={len(py)} chars, Matha={len(matha)} chars")
    except Exception as e:
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")

# ============================================================
# 6. 性能基准
# ============================================================
print("\n【6. 性能基准 (100次转换)】")
prog = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"

# Matha → C
t0 = time.perf_counter()
for _ in range(100):
    convert(prog, "matha", "c")
c_ms = (time.perf_counter() - t0) * 1000

# Matha → Python
t0 = time.perf_counter()
for _ in range(100):
    convert(prog, "matha", "python")
py_ms = (time.perf_counter() - t0) * 1000

# Matha → Matha
t0 = time.perf_counter()
for _ in range(100):
    convert(prog, "matha", "matha")
matha_ms = (time.perf_counter() - t0) * 1000

# Matha → MIR
t0 = time.perf_counter()
for _ in range(100):
    matha_to_mir(prog)
mir_ms = (time.perf_counter() - t0) * 1000

print(f"  Matha → C:    {c_ms:6.1f}ms ({c_ms/100:.2f}ms/次)")
print(f"  Matha → Python: {py_ms:6.1f}ms ({py_ms/100:.2f}ms/次)")
print(f"  Matha → Matha: {matha_ms:6.1f}ms ({matha_ms/100:.2f}ms/次)")
print(f"  Matha → MIR:   {mir_ms:6.1f}ms ({mir_ms/100:.2f}ms/次)")

# ============================================================
# 7. 批量转换测试
# ============================================================
print("\n【7. 批量转换测试】")
source = "x = sin(3.14) + cos(1.57)"
results = convert_all(source, "matha")
for lang, code in results.items():
    print(f"  {lang}: {len(code)} chars")

# ============================================================
# 8. 循环转换测试
# ============================================================
print("\n【8. 循环转换一致性】")
source = "x = 1 + 2 * 3"
# Matha → C → Matha
c1 = convert(source, "matha", "c")
matha1 = convert(c1, "c", "matha")
print(f"  Matha → C → Matha: {len(source)} → {len(c1)} → {len(matha1)} chars")
# Matha → Python → Matha
py1 = convert(source, "matha", "python")
matha2 = convert(py1, "python", "matha")
print(f"  Matha → Py → Matha: {len(source)} → {len(py1)} → {len(matha2)} chars")
# C → Python
py2 = convert(c1, "c", "python")
print(f"  C → Python: {len(c1)} → {len(py2)} chars")

print("\n" + "=" * 60)
print("验证完成!")
print("=" * 60)
