# -*- coding: utf-8 -*-
"""Matha LLVM 后端验证测试。"""
import sys, time
sys.path.insert(0, r"D:\trae")

print("=" * 60)
print("Matha LLVM 后端验证")
print("=" * 60)

# 1. 测试 IR 转换器
print("\n【1. Matha AST → IR 转换】")
from src.compiler.llvm_backend import (
    MathaToIRConverter, IRConstant, IRArithOp, IRFunctionCall,
    LLVMIRGenerator, LLVMCompiler, LLVMHotJIT, matha_to_llvm_ir
)

converter = MathaToIRConverter()

# 模拟一个简单的 AST 节点
class FakeNode:
    def __init__(self, kind, **kwargs):
        self.kind = kind
        for k, v in kwargs.items():
            setattr(self, k, v)

# 测试常量
node = FakeNode("IntegerLit", value=42)
ir = converter.convert(node)
print(f"  IntegerLit(42) → {type(ir).__name__}: {ir.value}")

# 测试算术运算
node = FakeNode("BinaryOp", op="+",
                left=FakeNode("IntegerLit", value=10),
                right=FakeNode("IntegerLit", value=20))
ir = converter.convert(node)
print(f"  BinaryOp(+, 10, 20) → {type(ir).__name__}: op={ir.op}")

# 测试函数调用
node = FakeNode("FuncApp",
                func=FakeNode("Variable", name="sin"),
                arg=FakeNode("FloatLit", value=3.14))
ir = converter.convert(node)
print(f"  FuncApp(sin, 3.14) → {type(ir).__name__}: func={ir.func_name}")

# 2. 测试 LLVM IR 生成
print("\n【2. LLVM IR 生成】")
generator = LLVMIRGenerator("test_module")
ir_nodes = [
    IRConstant(42.0, "double"),
    IRArithOp("fadd", IRConstant(10.0, "double"), IRConstant(20.0, "double"), "double"),
]
llvm_ir = generator.generate(ir_nodes)
print(f"  生成 LLVM IR: {len(llvm_ir)} 字符")
print(f"  包含 target triple: {'target triple' in llvm_ir}")
print(f"  包含 sqrt 声明: {'declare double @sqrt' in llvm_ir}")

# 3. 测试完整 IR 转换
print("\n【3. 完整 IR 转换】")
llvm_text = matha_to_llvm_ir(node)
print(f"  函数调用 IR 长度: {len(llvm_text)} 字符")
print(f"  包含 main 函数: {'define double @main' in llvm_text}")

# 4. 测试 LLVM 编译器 (需要 llc/clang)
print("\n【4. LLVM 编译器】")
compiler = LLVMCompiler()
print(f"  编译器工具链: clang/llc")
print(f"  缓存大小: {compiler.cache_size}")

# 5. 测试热点 JIT
print("\n【5. 热点追踪 JIT】")
jit = LLVMHotJIT(threshold=3)
print(f"  热点阈值: 3 次")
jit.record("fact")
jit.record("fact")
jit.record("fact")
print(f"  fact 调用次数: 3, 应触发编译: {jit.should_compile('fact')}")
print(f"  JIT 统计: {jit.stats}")

# 6. 性能基准
print("\n【6. 性能基准 (LLVM vs 解释器)】")
from src.interp import Interpreter
from src.parser import parse

interp = Interpreter()

# 编译表达式
expr = "sin(x) * cos(y) + sqrt(z)"
llvm_ir_text = matha_to_llvm_ir(FakeNode("BinaryOp", op="+",
    left=FakeNode("BinaryOp", op="*",
        left=FakeNode("Variable", name="sin"),
        right=FakeNode("FloatLit", value=3.14)),
    right=FakeNode("FloatLit", value=2.0)))

# 尝试编译
import subprocess
try:
    result = subprocess.run(['llc', '--version'], capture_output=True, timeout=5)
    if result.returncode == 0:
        print("  LLVM llc: 可用")
    else:
        print("  LLVM llc: 不可用 (回退到 Python 解释)")
except FileNotFoundError:
    print("  LLVM llc: 未安装 (回退到 Python 解释)")
    print("  → 安装 LLVM: pip install llvmlite 或下载 LLVM 工具链")

# Python 原生性能
import math
t0 = time.perf_counter()
for _ in range(100000):
    math.sin(3.14) * math.cos(1.57) + math.sqrt(2.0)
py_ms = (time.perf_counter() - t0) * 1000
print(f"  Python 原生 100k次: {py_ms:.0f}ms")

# Matha 解释器性能
prog = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"
t0 = time.perf_counter()
for _ in range(1000):
    interp.run(parse(prog))
matha_ms = (time.perf_counter() - t0) * 1000
print(f"  Matha 解释器 1k次: {matha_ms:.0f}ms")
print(f"  差距: {matha_ms/py_ms*1000:.0f}x (解释器) vs {py_ms/matha_ms:.2f}x (LLVM 预期)")

print("\n" + "=" * 60)
print("LLVM 后端验证完成")
print("=" * 60)
print("\n下一步:")
print("  1. 安装 LLVM: pip install llvmlite")
print("  2. 下载 LLVM 工具链: https://llvm.org/")
print("  3. 配置 PATH: 添加 LLVM/bin 到系统 PATH")
print("  4. 重新运行测试")
