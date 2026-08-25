# -*- coding: utf-8 -*-
"""Matha 复杂数学运算 - 三向转换器实际输出测试"""
import sys, time
sys.path.insert(0, r"D:\trae")

from src.mir_converter import convert, convert_all, matha_to_mir

print("=" * 70)
print("Matha 复杂数学运算 - 三向转换器实际输出")
print("=" * 70)

# ============================================================
# 测试用例：复杂数学运算
# ============================================================
test_cases = [
    ("基础三角函数",
     "x = sin(π) + cos(π/2) + tan(π/4)\n#1：[x]"),

    ("对数与指数",
     "x = log(e) + log10(100) + exp(1) + ln(e)\n#1：[x]"),

    ("根式运算",
     "x = sqrt(2) + sqrt(3) + sqrt(5) + cbrt(8)\n#1：[x]"),

    ("幂运算",
     "x = 2^3 + 3^2 + 10^2 + sqrt(144)\n#1：[x]"),

    ("复合三角",
     "x = sin(π/6) * cos(π/3) + tan(π/4) * sin(π/2)\n#1：[x]"),

    ("超几何函数",
     "x = hypot(3, 4) + expm1(1) + log1p(e)\n#1：[x]"),

    ("取整运算",
     "x = floor(3.7) + ceil(3.2) + round(3.5) + trunc(3.9)\n#1：[x]"),

    ("数值常量",
     "x = π + τ + e + √2 + √3 + ln2 + ln10\n#1：[x]"),

    ("复杂表达式",
     "a = sin(π/4)\nb = cos(π/3)\nc = sqrt(2)\nresult = a * b + c * c - tan(π/4)\n#1：[result]"),

    ("函数定义与调用",
     "add = (a, b) → a + b\nmul = (a, b) → a * b\nx = add(sin(π), cos(π/2)) * mul(2, 3)\n#1：[x]"),
]

for name, source in test_cases:
    print(f"\n{'='*70}")
    print(f"测试: {name}")
    print(f"{'='*70}")
    print(f"\n【Matha 源码】")
    print(source)

    # Matha → MIR
    try:
        mir_text = matha_to_mir(source)
        print(f"\n【MIR 中间表示】({len(mir_text)} 字符)")
        print("-" * 50)
        for line in mir_text.split("\n")[:20]:
            print(f"  {line}")
        if len(mir_text.split("\n")) > 20:
            print(f"  ... (共 {len(mir_text.split(chr(10)))} 行)")
    except Exception as e:
        print(f"\n【MIR】错误: {e}")

    # Matha → C
    try:
        c_code = convert(source, "matha", "c")
        print(f"\n【C 代码】({len(c_code)} 字符)")
        print("-" * 50)
        for line in c_code.split("\n")[:25]:
            print(f"  {line}")
        if len(c_code.split("\n")) > 25:
            print(f"  ... (共 {len(c_code.split(chr(10)))} 行)")
    except Exception as e:
        print(f"\n【C 代码】错误: {e}")

    # Matha → Python
    try:
        py_code = convert(source, "matha", "python")
        print(f"\n【Python 代码】({len(py_code)} 字符)")
        print("-" * 50)
        for line in py_code.split("\n")[:20]:
            print(f"  {line}")
        if len(py_code.split("\n")) > 20:
            print(f"  ... (共 {len(py_code.split(chr(10)))} 行)")
    except Exception as e:
        print(f"\n【Python 代码】错误: {e}")

    # Matha → Matha (自举)
    try:
        matha_out = convert(source, "matha", "matha")
        print(f"\n【Matha 自举】({len(matha_out)} 字符)")
        print("-" * 50)
        print(matha_out)
    except Exception as e:
        print(f"\n【Matha 自举】错误: {e}")

# ============================================================
# 批量转换性能测试
# ============================================================
print(f"\n\n{'='*70}")
print("批量转换性能测试")
print(f"{'='*70}")

complex_source = """
# 复杂数学运算测试
a = sin(π/4)
b = cos(π/3)
c = tan(π/6)
d = sqrt(2)
e = exp(1)
f = log(e)
g = hypot(3, 4)
h = floor(3.7) + ceil(3.2)
result = a * b + c * d + e * f + g + h
#1：[result]
"""

# 批量转换
results = convert_all(complex_source, "matha")
print(f"\n批量转换结果:")
for lang, code in results.items():
    print(f"  {lang:8s}: {len(code):5d} 字符")

# 性能基准
print(f"\n性能基准 (100次转换):")
t0 = time.perf_counter()
for _ in range(100):
    convert(complex_source, "matha", "c")
c_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for _ in range(100):
    convert(complex_source, "matha", "python")
py_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for _ in range(100):
    convert(complex_source, "matha", "matha")
matha_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for _ in range(100):
    matha_to_mir(complex_source)
mir_ms = (time.perf_counter() - t0) * 1000

print(f"  Matha → C:    {c_ms:8.1f}ms ({c_ms/100:.2f}ms/次)")
print(f"  Matha → Python: {py_ms:8.1f}ms ({py_ms/100:.2f}ms/次)")
print(f"  Matha → Matha: {matha_ms:8.1f}ms ({matha_ms/100:.2f}ms/次)")
print(f"  Matha → MIR:   {mir_ms:8.1f}ms ({mir_ms/100:.2f}ms/次)")

# 对比 LLVM IR
from src.compiler.matha_cc import matha_to_llvm
t0 = time.perf_counter()
for _ in range(100):
    matha_to_llvm(complex_source)
llvm_ms = (time.perf_counter() - t0) * 1000
llvm_ir = matha_to_llvm(complex_source)
print(f"  Matha → LLVM:  {llvm_ms:8.1f}ms ({llvm_ms/100:.2f}ms/次), {len(llvm_ir)} chars")

print(f"\n{'='*70}")
print("测试完成!")
print(f"{'='*70}")
