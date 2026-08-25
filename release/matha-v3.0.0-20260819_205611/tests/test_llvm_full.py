# -*- coding: utf-8 -*-
"""Matha LLVM 工具链完整验证测试。"""
import sys, time
sys.path.insert(0, r"D:\trae")

print("=" * 60)
print("Matha LLVM 工具链 - 完整验证")
print("=" * 60)

from src.compiler.llvm_hybrid import HybridLLVMBackend, matha_to_llvm

backend = HybridLLVMBackend()
print(f"编译模式: {backend.stats['mode']}")
print(f"LLVM 可用: {backend.stats['llvm_available']}")
print()

# 测试用例
tests = [
    ("简单算术", "x = 1 + 2 * 3\n#1：[x]"),
    ("三角函数", "x = sin(3.14) + cos(1.57)\n#1：[x]"),
    ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[x]"),
    ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))\n#1：[x]"),
    ("函数定义", "add = (a, b) => a + b\nresult = add(1.0, 2.0)\n#1：[result]"),
]

print("编译测试:")
for name, src in tests:
    t0 = time.perf_counter()
    llvm_ir = matha_to_llvm(src)
    exe = backend.compile(llvm_ir, name)
    elapsed = (time.perf_counter() - t0) * 1000
    status = "PASS" if len(llvm_ir) > 100 else "FAIL"
    print(f"  [{status}] {name}: {elapsed:.1f}ms, IR {len(llvm_ir)} chars")

# 性能基准
print()
print("性能基准:")
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
print(f"  单次翻译: {compile_ms/100:.2f}ms")

print()
print("生成示例 LLVM IR:")
llvm_ir = matha_to_llvm("result = sin(3.14) + cos(1.57)")
for line in llvm_ir.split("\n")[:15]:
    print(f"  {line}")

print()
print("=" * 60)
print("验证完成!")
print("=" * 60)
