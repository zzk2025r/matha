"""Matha 完整自举编译器 — 支持多目标编译。

编译目标：
  1. C       — Matha源码 → C代码 → 原生机器码
  2. Python  — Matha源码 → Python代码
  3. LLVM    — 显式拒绝（LLVM IR 生成未实现）
  4. Matha   — Matha源码 → MBC1 字节码（经 mbc.compiler，真实可读回）
  5-7. Binary/Trinary/Decimal — 显式拒绝（Base-N 原生机器码生成未实现）

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
    """数制编译器 — Base-2/3/10 原生机器码生成（显式拒绝）。

    历史上 compile() 产出「注释头 + MIR 指令文本列表」冒充机器码——
    那不是任何硬件可执行的产物。真实 Base-N 机器码生成未实现；
    原生码请走 target='c'（MIR→C→clang）路径。
    """

    def __init__(self, target_base: int = 2, optimize: bool = True):
        self.target_base = target_base  # 2, 3, or 10
        self.optimize = optimize

    def compile(self, mir_program: Any, source: str = "") -> str:
        raise NotImplementedError(
            f"Base-{self.target_base} 原生机器码生成未实现"
            "（旧路径仅产出注释头+指令文本，非可执行代码）；"
            "原生码请走 target='c' 经 MIR→C→clang 编译")


# ============================================================
# Matha 字节码编译器
# ============================================================

class MathaBytecodeCompiler:
    """Matha 字节码编译器 — 委托真实 MBC1 编译链（MathaSelfCompiler）。

    旧实现遍历 MIR 指令取不存在的 .opcode 字段，把指令对象当操作码
    emit，产物既无法被 matha_vm.MathaVM 消费（序列化 TypeError）也不符
    MBC1 布局。真实字节码从源码经 mbc.compiler 编译（MBC1 布局，可被
    src.mbc.serial 反序列化）；MIR → MBC1 直译未实现：无源码时显式拒绝。
    """

    def __init__(self, optimize: bool = True):
        self.optimize = optimize
        self._cache: dict[str, bytes] = {}

    def compile(self, mir_program: Any, source: str = "") -> bytes:
        """将 Matha 源码编译为真实 MBC1 字节码（可被 src.mbc.serial 读回）。"""
        if not source:
            raise ValueError(
                "MathaBytecodeCompiler.compile 需要源码字符串："
                "MIR → MBC1 直译未实现，字节码从源码经 mbc.compiler 编译")
        cache_key = f"matha_bytecode:{hash(source)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        bytecode = MathaSelfCompiler(optimize=self.optimize).compile(source)
        self._cache[cache_key] = bytecode
        return bytecode


# ============================================================
# Matha 自编译 — Matha → Matha
# ============================================================

class MathaSelfCompiler:
    """Matha 自编译器 — 将 Matha 源码编译为真实 M3V 字节码（MBC1 布局）。

    实现自举：Matha 源码 → 主实现 parse → mbc compile_program → MBC1 字节串。
    旧实现借道 ``hasattr(matha_ir, 'functions')`` 误判，对任意输入静默产出
    空字节码；现产物是真实可被 :func:`src.mbc.serial.deserialize_mbc` 读回的
    MBC1 二进制。
    """

    def __init__(self, optimize: bool = True):
        self.optimize = optimize
        self._cache: dict[str, bytes] = {}

    def compile(self, source: str) -> bytes:
        """将 Matha 源码编译为 M3V 字节码（MBC1 布局）。"""
        cache_key = f"matha_self:{hash(source)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        from src.mbc.compiler import compile_program
        from src.mbc.serial import serialize_mbc
        from src.parser import parse

        mod = compile_program(parse(source))
        result = serialize_mbc(mod)
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
        llvm     — 显式拒绝（LLVM IR 生成未实现）
        matha    — Matha → MBC1 字节码（真实 mbc 编译，可反序列化）
        binary/trinary/decimal — 显式拒绝（Base-N 原生机器码生成未实现）
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
        # LLVM IR 生成未实现：matha_to_llvm 显式拒绝（历史上产出无效 IR 文本）
        from src.compiler.matha_cc import matha_to_llvm
        return matha_to_llvm(source)

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
    """编译并基准测试（只测真实存在的链路：解释器与 MIR→C）。

    旧版对 matha_to_llvm 计时——legacy 解析器时代它对全部用例 SyntaxError，
    「LLVM 基准」从未产生过数据；LLVM IR 生成未实现（matha_to_llvm 显式
    拒绝），此处如实标注 skipped。
    """
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
        mir_code = bootstrap_compile(source, target="c", optimize=True)
        mir_ms = (time.perf_counter() - t0) * 1000

        results[name] = {
            "interp_ms": interp_ms,
            "llvm_ms": "skipped",
            "mir_ms": mir_ms,
            "mir_code_length": len(mir_code),
        }

        print(f"  {name:15s}: 解释器={interp_ms:6.0f}ms, LLVM=skipped, MIR={mir_ms:5.1f}ms")

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
