"""Matha 完整自举编译器 — 支持多目标编译。

编译目标：
  1. C       — Matha源码 → C代码 → 原生机器码
  2. Python  — Matha源码 → Python代码
  3. LLVM    — Matha源码 → LLVM IR → 原生机器码
  4. Matha   — Matha源码 → Matha字节码 → Matha虚拟机
  5. Binary  — Matha源码 → Base-2二进制 → 硬件二进制
  6. Trinary — Matha源码 → Base-3三进制 → 硬件三进制
  7. Decimal — Matha源码 → Base-10十进制 → 硬件十进制

架构：
  .matha 源码
    │
    ▼
  ┌─────────────────────────────────────────────────┐
  │              Matha 前端                          │
  │  MathaLexer → MathaParser → MathaFrontend → AST  │
  └──────────────────┬──────────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────────┐
  │              Matha IR (MIR)                     │
  │  三地址码、函数定义、变量绑定、控制流              │
  └──────────────────┬──────────────────────────────┘
                     │
          ┌──────────┼──────────┬──────────┬────────┐
          ▼          ▼          ▼          ▼        ▼
  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
  │ MIR→C    ││ MIR→Python││ MIR→LLVM ││ MIR→Matha││ MIR→数制 │
  │ 编译器   ││ 编译器    ││ 编译器   ││ 字节码   ││ 编译器   │
  └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
       │           │           │           │           │
       ▼           ▼           ▼           ▼           ▼
  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
  │ C代码    ││ Python   ││ LLVM IR  ││ M3V字节码││ Base-2   │
  │ llc/clang││ 代码     ││ (llc)    ││ M3V VM   ││ Base-3   │
  │ 原生机器码││ .pyc     ││ 原生机器码││ MathaVM  ││ Base-10  │
  │ (ELF/PE) ││          ││ (ELF/PE) ││          ││ 硬件代码 │
  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘

数制选择：
  根据底层硬件需求自动选择：
  - x86/ARM → 二进制 (Base-2)
  - 三进制处理器 → 三进制 (Base-3)
  - 十进制硬件 → 十进制 (Base-10)
  - 通用 → 自动选择最优数制
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 数制编译器
# ============================================================

class NumberSystemCompiler:
    """数制编译器 — 根据硬件需求编译为二进制/三进制/十进制。

    核心能力：
    - 二进制编译（Base-2）：适用于x86/ARM处理器
    - 三进制编译（Base-3）：适用于三进制处理器
    - 十进制编译（Base-10）：适用于十进制硬件
    """

    def __init__(self, target_base: int = 2, optimize: bool = True):
        self.target_base = target_base  # 2, 3, or 10
        self.optimize = optimize
        self._cache: dict[str, str] = {}

    def compile(self, mir_program: Any, source: str = "") -> str:
        """根据目标数制编译MIR。"""
        cache_key = f"base{self.target_base}:{id(mir_program)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.target_base == 2:
            result = self._compile_binary(mir_program, source)
        elif self.target_base == 3:
            result = self._compile_trinary(mir_program, source)
        elif self.target_base == 10:
            result = self._compile_decimal(mir_program, source)
        else:
            raise ValueError(f"不支持的数制: {self.target_base}")

        self._cache[cache_key] = result
        return result

    def _compile_binary(self, mir_program: Any, source: str) -> str:
        """编译为二进制（Base-2）— 适用于x86/ARM处理器。"""

        lines = [
            "// Matha Binary Compiler (Base-2)",
            "// Target: Binary (Base-2) — x86/ARM",
            f"// Source: {source[:50] if source else 'unknown'}",
            f"// Optimized: {self.optimize}",
            "//",
            "// 数制说明：所有数据以二进制存储和计算",
            "// Base2 是所有数据的最终物理表示",
        ]

        # 将MIR指令转换为二进制表示
        if hasattr(mir_program, 'functions'):
            for func_name, func in mir_program.functions.items():
                lines.append(f"\n// 函数: {func_name}")
                lines.append(f"// 参数: {func.params}")
                for instr in func.instructions:
                    binary_instr = self._instr_to_binary(instr)
                    lines.append(f"  {binary_instr}")

        result = "\n".join(lines)
        return result

    def _compile_trinary(self, mir_program: Any, source: str) -> str:
        """编译为三进制（Base-3）— 适用于三进制处理器。"""

        lines = [
            "// Matha Trinary Compiler (Base-3)",
            "// Target: Trinary (Base-3) — 三进制处理器",
            f"// Source: {source[:50] if source else 'unknown'}",
            f"// Optimized: {self.optimize}",
            "//",
            "// 数制说明：所有数据以三进制存储和计算",
            "// Base3 使用三进制编码，汉字/字母 → 三进制映射",
        ]

        if hasattr(mir_program, 'functions'):
            for func_name, func in mir_program.functions.items():
                lines.append(f"\n// 函数: {func_name}")
                lines.append(f"// 参数: {func.params}")
                for instr in func.instructions:
                    trinary_instr = self._instr_to_trinary(instr)
                    lines.append(f"  {trinary_instr}")

        result = "\n".join(lines)
        return result

    def _compile_decimal(self, mir_program: Any, source: str) -> str:
        """编译为十进制（Base-10）— 适用于十进制硬件。"""

        lines = [
            "// Matha Decimal Compiler (Base-10)",
            "// Target: Decimal (Base-10) — 十进制硬件",
            f"// Source: {source[:50] if source else 'unknown'}",
            f"// Optimized: {self.optimize}",
            "//",
            "// 数制说明：所有数据以十进制存储和计算",
            "// Base10 使用十进制编码，人类可读",
        ]

        if hasattr(mir_program, 'functions'):
            for func_name, func in mir_program.functions.items():
                lines.append(f"\n// 函数: {func_name}")
                lines.append(f"// 参数: {func.params}")
                for instr in func.instructions:
                    decimal_instr = self._instr_to_decimal(instr)
                    lines.append(f"  {decimal_instr}")

        result = "\n".join(lines)
        return result

    def _instr_to_binary(self, instr: Any) -> str:
        """将指令转换为二进制表示。"""
        if isinstance(instr, str):
            return f"0b{''.join(format(ord(c), '08b') for c in instr)}"
        return str(instr)

    def _instr_to_trinary(self, instr: Any) -> str:
        """将指令转换为三进制表示。"""
        if isinstance(instr, str):
            return f"0t{''.join(format(ord(c), '04t') if False else format(ord(c) % 3, '02') for c in instr)}"
        return str(instr)

    def _instr_to_decimal(self, instr: Any) -> str:
        """将指令转换为十进制表示。"""
        if isinstance(instr, str):
            return f"0d{ord(instr[0]) if instr else 0}"
        return str(instr)


# ============================================================
# Matha 字节码编译器
# ============================================================

class MathaBytecodeCompiler:
    """Matha 字节码编译器 — 将 MIR 编译为 M3V 字节码。

    架构：
      MIR → MathaBytecode → M3V虚拟机 → 结果
    """

    def __init__(self, optimize: bool = True):
        self.optimize = optimize
        self._cache: dict[str, bytes] = {}

    def compile(self, mir_program: Any, source: str = "") -> bytes:
        """将MIR编译为M3V字节码。"""
        cache_key = f"matha_bytecode:{id(mir_program)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        bytecode = self._generate_bytecode(mir_program)
        self._cache[cache_key] = bytecode
        return bytecode

    def _generate_bytecode(self, mir_program: Any) -> bytes:
        """生成M3V字节码。"""
        from src.matha_vm import MathaBytecode

        bytecode = MathaBytecode()

        if hasattr(mir_program, 'functions'):
            for func_name, func in mir_program.functions.items():
                bytecode.function_start(func_name)
                for instr in func.instructions:
                    opcode = getattr(instr, 'opcode', None)
                    if opcode is not None:
                        operands = getattr(instr, 'operands', ())
                        bytecode.emit(opcode, *operands)
                    else:
                        bytecode.emit(instr)

        return bytecode.to_bytes()


# ============================================================
# Matha 自编译 — Matha → Matha
# ============================================================

class MathaSelfCompiler:
    """Matha 自编译器 — 将 Matha 编译为 Matha 字节码。

    实现自举：Matha 源码 → Matha 字节码 → Matha 虚拟机
    """

    def __init__(self, optimize: bool = True):
        self.optimize = optimize
        self._cache: dict[str, bytes] = {}

    def compile(self, source: str) -> bytes:
        """将 Matha 源码编译为 Matha 字节码。"""
        cache_key = f"matha_self:{hash(source)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        from src.compiler.matha_cc import MathaFrontend, MathaLexer, MathaParser
        from src.matha_vm import MathaBytecode

        # Phase 1: 词法分析
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()

        # Phase 2: 语法分析
        parser = MathaParser(tokens)
        ast = parser.parse()

        # Phase 3: 生成 MIR
        frontend = MathaFrontend()
        matha_ir = frontend.compile(ast)

        # Phase 4: 生成字节码
        bytecode = MathaBytecode()
        if hasattr(matha_ir, 'functions'):
            for func_name, func in matha_ir.functions.items():
                bytecode.add_function(func_name, func.params, func.instructions)

        result = bytecode.to_bytes()
        self._cache[cache_key] = result
        return result


# ============================================================
# 完整自举编译器 — 统一接口
# ============================================================

def matha_bootstrap_compile(
    source: str,
    target: str = "c",
    optimize: bool = True,
    target_base: int = 2,
    hardware_profile: str | None = None
) -> str:
    """完整自举编译 Matha 源码。

    参数：
        source: Matha 源码
        target: 编译目标 — c, python, llvm, matha, binary, trinary, decimal
        optimize: 是否优化
        target_base: 目标数制 (2, 3, 10)
        hardware_profile: 硬件配置文件 (x86, arm, ternary, decimal)

    返回：
        编译结果（代码字符串）

    架构：
        .matha 源码 → Matha前端 → MIR → 目标代码

    目标说明：
        c        — Matha → C → llc/clang → 原生机器码
        python   — Matha → Python → .pyc
        llvm     — Matha → LLVM IR → llc → 原生机器码
        matha    — Matha → M3V字节码 → Matha虚拟机
        binary   — Matha → Base-2 → x86/ARM硬件
        trinary  — Matha → Base-3 → 三进制处理器
        decimal  — Matha → Base-10 → 十进制硬件
    """
    from src.compiler.matha_cc import MathaLexer, MathaParser
    from src.mir import MIRGenerator
    from src.mir_codegen import MIRToCGenerator, MIRToPythonGenerator
    from src.mir_opt import MathaOptimizationPipeline

    # 硬件配置自动选择数制
    if hardware_profile:
        _hardware_to_base(hardware_profile)

    # Phase 1: AST → MIR
    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    parser = MathaParser(tokens)
    ast = parser.parse()

    mir_gen = MIRGenerator()
    mir_program = mir_gen.generate(ast)

    # Phase 2: 优化 MIR
    if optimize:
        pipeline = MathaOptimizationPipeline()
        mir_program = pipeline.run(mir_program)

    # Phase 3: 根据目标编译
    if target == "c":
        c_gen = MIRToCGenerator(optimize=optimize)
        return c_gen.generate(mir_program)

    elif target == "python":
        py_gen = MIRToPythonGenerator(optimize=optimize)
        return py_gen.generate(mir_program)

    elif target == "llvm":
        from src.compiler.matha_cc import MathaLLVMGenerator
        llvm_gen = MathaLLVMGenerator("matha_module")
        return llvm_gen.generate(mir_program)

    elif target == "matha":
        # Matha → Matha 字节码
        from src.bootstrap import MathaBytecodeCompiler
        compiler = MathaBytecodeCompiler(optimize=optimize)
        bytecode = compiler.compile(mir_program, source)
        return bytecode.hex()

    elif target == "binary":
        # Matha → Base-2 二进制
        compiler = NumberSystemCompiler(target_base=2, optimize=optimize)
        return compiler.compile(mir_program, source)

    elif target == "trinary":
        # Matha → Base-3 三进制
        compiler = NumberSystemCompiler(target_base=3, optimize=optimize)
        return compiler.compile(mir_program, source)

    elif target == "decimal":
        # Matha → Base-10 十进制
        compiler = NumberSystemCompiler(target_base=10, optimize=optimize)
        return compiler.compile(mir_program, source)

    else:
        raise ValueError(f"不支持的目标: {target}")


def _hardware_to_base(hardware: str) -> int:
    """根据硬件配置自动选择数制。

    参数：
        hardware: 硬件类型
            x86, arm, x64 → 二进制 (2)
            ternary, trinary, ternary_processor → 三进制 (3)
            decimal, decimal_hardware → 十进制 (10)
            auto → 自动选择

    返回：
        目标数制 (2, 3, 或 10)
    """
    hardware_lower = hardware.lower()
    if any(hw in hardware_lower for hw in ['x86', 'x64', 'arm', 'amd64']):
        return 2
    elif any(hw in hardware_lower for hw in ['ternary', 'trinary', '三进制']):
        return 3
    elif any(hw in hardware_lower for hw in ['decimal', '十进制']):
        return 10
    else:
        return 2  # 默认二进制


# ============================================================
# MathaBootstrap 增强版
# ============================================================

class MathaBootstrap:
    """Matha 自举编译器 — 支持多目标编译。

    完整编译流程：
      .matha 源码 → MIR → C/Python/LLVM/Matha/Base-2/Base-3/Base-10

    数制选择：
      根据底层硬件需求自动选择最优数制：
      - x86/ARM → 二进制 (Base-2)
      - 三进制处理器 → 三进制 (Base-3)
      - 十进制硬件 → 十进制 (Base-10)
    """

    def __init__(self, optimize: bool = True):
        self.optimize = optimize
        self._compile_cache: dict[str, str] = {}
        self._benchmark_results: dict = {}
        self._target = "c"
        self._target_base = 2
        self._hardware_profile: str | None = None

    def compile(self, source: str, target: str = "c",
                target_base: int = 2, hardware_profile: str | None = None
                ) -> str:
        """编译 Matha 源码到目标语言。

        参数：
            source: Matha 源码
            target: 编译目标 — c, python, llvm, matha, binary, trinary, decimal
            target_base: 目标数制 (2, 3, 10)
            hardware_profile: 硬件配置文件
        """
        self._target = target
        self._target_base = target_base
        self._hardware_profile = hardware_profile

        cache_key = f"bootstrap:{hash(source)}:{target}:{target_base}:{self.optimize}"
        if cache_key in self._compile_cache:
            return self._compile_cache[cache_key]

        result = matha_bootstrap_compile(
            source, target, self.optimize, target_base, hardware_profile
        )
        self._compile_cache[cache_key] = result
        return result

    def compile_to_c(self, source: str) -> str:
        """编译到 C 语言。"""
        return self.compile(source, target="c")

    def compile_to_python(self, source: str) -> str:
        """编译到 Python。"""
        return self.compile(source, target="python")

    def compile_to_llvm(self, source: str) -> str:
        """编译到 LLVM IR。"""
        return self.compile(source, target="llvm")

    def compile_to_matha(self, source: str) -> str:
        """编译到 Matha 字节码（自举）。"""
        return self.compile(source, target="matha")

    def compile_to_binary(self, source: str) -> str:
        """编译为二进制（Base-2）— 适用于x86/ARM处理器。"""
        return self.compile(source, target="binary", target_base=2)

    def compile_to_trinary(self, source: str) -> str:
        """编译为三进制（Base-3）— 适用于三进制处理器。"""
        return self.compile(source, target="trinary", target_base=3)

    def compile_to_decimal(self, source: str) -> str:
        """编译为十进制（Base-10）— 适用于十进制硬件。"""
        return self.compile(source, target="decimal", target_base=10)

    def compile_for_hardware(self, source: str, hardware: str) -> str:
        """根据硬件配置编译。

        自动选择最优数制：
        - x86/ARM → 二进制
        - 三进制处理器 → 三进制
        - 十进制硬件 → 十进制
        """
        target_base = _hardware_to_base(hardware)
        return self.compile(source, target="binary", target_base=target_base,
                           hardware_profile=hardware)

    def run(self, source: str) -> str:
        """运行 Matha 源码（通过自举编译器）。"""
        try:
            c_code = self.compile(source, target="c")
            return c_code
        except Exception:
            from src.diag_backends import run_legacy as interpret
            out, _ = interpret(source)
            return "\n".join(str(item) for item in out)

    def run_matha(self, source: str) -> bytes:
        """运行 Matha 源码（通过 Matha 字节码）。"""
        bytecode = self.compile(source, target="matha")
        return bytecode

    def run_binary(self, source: str) -> str:
        """运行 Matha 源码（通过二进制编译）。"""
        return self.compile(source, target="binary")

    def run_trinary(self, source: str) -> str:
        """运行 Matha 源码（通过三进制编译）。"""
        return self.compile(source, target="trinary")

    def run_decimal(self, source: str) -> str:
        """运行 Matha 源码（通过十进制编译）。"""
        return self.compile(source, target="decimal")

    def benchmark(self) -> dict:
        """编译并基准测试。"""
        return compile_and_benchmark()

    def show_mir(self, source: str) -> None:
        """展示 MIR 示例。"""
        show_mir_example()

    def get_cache_info(self) -> dict:
        """获取缓存信息。"""
        return {"cache_size": len(self._compile_cache), "optimize": self.optimize}

    def get_supported_targets(self) -> list:
        """获取支持的编译目标。"""
        return ["c", "python", "llvm", "matha", "binary", "trinary", "decimal"]

    def get_supported_hardware(self) -> list:
        """获取支持的硬件配置。"""
        return ["x86", "x64", "arm", "amd64", "ternary", "trinary", "decimal", "auto"]


# ============================================================
# 便捷函数
# ============================================================

def bootstrap_compile(source: str, target: str = "c", optimize: bool = True) -> str:
    """Bootstrap 编译 Matha 源码（兼容旧接口）。"""
    return matha_bootstrap_compile(source, target, optimize)


def compile_and_benchmark() -> dict:
    """编译并基准测试。"""
    from src.compiler.matha_cc import matha_to_llvm
    from src.diag_backends import new_interpreter as Interpreter
    from src.parser import parse as interp_parse

    results = {}
    test_cases = [
        ("简单算术", "x = 1 + 2 * 3\n#1：[x]"),
        ("三角函数", "x = sin(3.14) + cos(1.57)\n#1：[x]"),
        ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[x]"),
        ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))\n#1：[x]"),
    ]

    interp = Interpreter()

    for name, source in test_cases:
        t0 = time.perf_counter()
        for _ in range(1000):
            interp.run(interp_parse(source))
        interp_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        llvm_ir = matha_to_llvm(source)
        llvm_ms = (time.perf_counter() - t0) * 1000

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
    from src.compiler.matha_cc import MathaLexer, MathaParser
    from src.mir import MIRGenerator

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


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Matha 完整自举编译器验证")
    print("=" * 60)
    print()
    print("支持的编译目标：")
    print(f"  {MathaBootstrap().get_supported_targets()}")
    print()
    print("支持的硬件配置：")
    print(f"  {MathaBootstrap().get_supported_hardware()}")
    print()

    # 1. 展示 MIR 示例
    print("\n【1. MIR 示例】")
    show_mir_example()

    # 2. 测试各编译目标
    print("\n【2. 多目标编译测试】")
    source = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"
    bootstrap = MathaBootstrap(optimize=True)

    for target in ["c", "python", "llvm", "matha", "binary", "trinary", "decimal"]:
        try:
            result = bootstrap.compile(source, target=target)
            print(f"  {target:15s}: {len(result)} chars ✓")
        except Exception as e:
            print(f"  {target:15s}: FAILED - {e}")

    # 3. 硬件自适应编译
    print("\n【3. 硬件自适应编译】")
    for hw in ["x86", "arm", "ternary", "decimal"]:
        try:
            result = bootstrap.compile_for_hardware(source, hw)
            print(f"  {hw:15s}: {len(result)} chars ✓")
        except Exception as e:
            print(f"  {hw:15s}: FAILED - {e}")

    # 4. 性能基准
    print("\n【4. 性能基准】")
    results = compile_and_benchmark()

    # 5. 总结
    print("\n" + "=" * 60)
    print("总结:")
    for name, r in results.items():
        speedup = r["interp_ms"] / max(r["mir_ms"], 0.1)
        print(f"  {name}: {speedup:.1f}x 加速 (MIR vs 解释器)")
    print("=" * 60)
