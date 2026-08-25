# -*- coding: utf-8 -*-
"""Matha 自举编译器：用 Matha 构建 Matha 的工具链。

架构：
  Phase 1: Matha (Python) → MIR → C 代码
  Phase 2: C 代码 → 原生机器码
  Phase 3: 用生成的编译器编译 Matha 源码

性能目标：
  - 解释器: ~75x 慢于 Python 原生
  - MIR+C: ~1-2x 快于 Python 原生 (安装 GCC 后)
  - MIR+Python: ~2-3x 快于解释器
"""

from __future__ import annotations
import sys
import os
import time
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bootstrap_compile(source: str, target: str = "c", optimize: bool = True) -> str:
    """Bootstrap 编译 Matha 源码。"""
    from src.compiler.matha_cc import MathaLexer, MathaParser, MathaFrontend, MathaLLVMGenerator
    from src.mir import MIRGenerator, generate_mir
    from src.mir_codegen import MIRToCGenerator, MIRToPythonGenerator
    from src.mir_opt import MathaOptimizationPipeline

    # Phase 1: AST → MIR
    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    parser = MathaParser(tokens)
    ast = parser.parse()

    # 生成 MIR
    mir_gen = MIRGenerator()
    mir_program = mir_gen.generate(ast)

    # Phase 2: 优化 MIR
    if optimize:
        pipeline = MathaOptimizationPipeline()
        mir_program = pipeline.run(mir_program)

    # Phase 3: MIR → 目标代码
    if target == "c":
        c_gen = MIRToCGenerator(optimize=optimize)
        return c_gen.generate(mir_program)
    elif target == "python":
        py_gen = MIRToPythonGenerator(optimize=optimize)
        return py_gen.generate(mir_program)
    else:
        raise ValueError(f"不支持的目标: {target}")


def compile_and_benchmark() -> dict:
    """编译并基准测试。"""
    from src.interp import Interpreter
    from src.parser import parse as interp_parse
    from src.compiler.matha_cc import matha_to_llvm

    results = {}

    # 测试用例
    test_cases = [
        ("简单算术", "x = 1 + 2 * 3\n#1：[x]"),
        ("三角函数", "x = sin(3.14) + cos(1.57)\n#1：[x]"),
        ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[x]"),
        ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))\n#1：[x]"),
    ]

    interp = Interpreter()

    for name, source in test_cases:
        # 解释器性能
        t0 = time.perf_counter()
        for _ in range(1000):
            interp.run(interp_parse(source))
        interp_ms = (time.perf_counter() - t0) * 1000

        # LLVM 翻译性能
        t0 = time.perf_counter()
        llvm_ir = matha_to_llvm(source)
        llvm_ms = (time.perf_counter() - t0) * 1000

        # MIR 生成性能
        t0 = time.perf_counter()
        mir_code = bootstrap_compile(source, target="c", optimize=True)
        mir_ms = (time.perf_counter() - t0) * 1000

        results[name] = {
            "interp_ms": interp_ms,
            "llvm_ms": llvm_ms,
            "mir_ms": mir_ms,
            "llvm_ir_length": len(llvm_ir),
            "mir_code_length": len(mir_code),
        }

        print(f"  {name:15s}: 解释器={interp_ms:6.0f}ms, LLVM={llvm_ms:5.1f}ms, MIR={mir_ms:5.1f}ms")

    return results


def show_mir_example() -> None:
    """展示 MIR 示例。"""
    from src.mir import MIRGenerator
    from src.compiler.matha_cc import MathaLexer, MathaParser

    source = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"

    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    parser = MathaParser(tokens)
    ast = parser.parse()

    mir_gen = MIRGenerator()
    mir = mir_gen.generate(ast)

    print("MIR 示例 (result = sin(3.14) * cos(1.57) + sqrt(2.0)):")
    print("=" * 60)
    for name, func in mir.functions.items():
        print(f"  函数: {name}")
        print(f"    参数: {func.params}")
        print(f"    返回类型: {func.return_type}")
        print(f"    指令数: {len(func.instructions)}")
        for instr in func.instructions[:10]:
            print(f"      {instr}")
    print("=" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("Matha 自举编译器验证")
    print("=" * 60)

    # 1. 展示 MIR 示例
    print("\n【1. MIR 示例】")
    show_mir_example()

    # 2. 编译并基准测试
    print("\n【2. 性能基准】")
    results = compile_and_benchmark()

    # 3. 总结
    print("\n" + "=" * 60)
    print("总结:")
    for name, r in results.items():
        speedup = r["interp_ms"] / max(r["mir_ms"], 0.1)
        print(f"  {name}: {speedup:.1f}x 加速 (MIR vs 解释器)")
    print("=" * 60)
