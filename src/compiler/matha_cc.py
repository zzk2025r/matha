"""
matha-cc 编译器前端 — 主实现委托层（阶段 10 假实现清算）。

历史：本模块曾自带一套独立 legacy 词法/语法器 + 三地址 MathaIR + "LLVM IR"
文本生成器。实测全部真实语言形态（``func f(x) -> Int``、``#1：[expr]`` 输出行、
多参函数）一律 SyntaxError；唯一"编译成功"的产物是把三地址码贴进 LLVM 模板
得到的无效 IR 文本（llc 直接拒绝）；bootstrap.MathaSelfCompiler 借道 hasattr
误判静默产出空字节码。

阶段 10 起全部委托主实现（unified_parser 同款先例）：
  · MathaLexer / MathaParser          → src.lexer.Lexer / src.parser.Parser
  · MathaFrontend                     → 主 parse（接受源码字符串或 AST Program）
  · matha_compile                     → parse + mbc compile_program 真实计数摘要
  · matha_run                         → 主解释器真实执行（真实输出封入 CompletedProcess）
  · matha_to_llvm / MathaLLVMGenerator → 显式拒绝（无效 IR 文本不再产出）
  · MathaBackend                      → 维持真实工具链委托（src/plugins/toolchain_llvm）

机器码主链是 src.mbc.compiler → src.mbc.vm（原生为 src.mbc.native）；LLVM 是
可选外部工具链，见 src/compiler/llvm_hybrid.py。
"""

from __future__ import annotations

import subprocess

from src.bootstrap import (
    MathaBytecodeCompiler,
    MathaSelfCompiler,
    NumberSystemCompiler,
)

# ============================================================
# 1. 前端：主实现委托
# ============================================================

class MathaLexer:
    """matha_cc 兼容：委托主实现 src.lexer.Lexer。"""

    def __init__(self, source: str = ""):
        from src.lexer import Lexer
        self._lexer = Lexer(source)

    def tokenize(self):
        return list(self._lexer.tokenize())

    def next_token(self):
        return self._lexer.next_token()


class MathaParser:
    """matha_cc 兼容：委托主实现 src.parser.Parser。"""

    def __init__(self, tokens=None):
        from src.parser import Parser
        self._parser = Parser("")
        if tokens:
            # 主 Parser 的 token 序列/游标字段是 tokens/pos（unified_parser
            # 历史写法误设 _tokens/_pos，注入实际不生效——此处按真实字段注入）
            self._parser.tokens = list(tokens)
            self._parser.pos = 0

    def parse(self):
        return self._parser.parse()


class MathaFrontend:
    """matha_cc 兼容前端：compile 接受源码字符串或已解析 AST Program。"""

    def __init__(self):
        self._last_ast = None

    def compile(self, source_or_program):
        from src.parser import parse
        if isinstance(source_or_program, str):
            self._last_ast = parse(source_or_program)
        else:
            self._last_ast = source_or_program
        return self._last_ast


# ============================================================
# 2. LLVM 生成器：显式拒绝
# ============================================================

class MathaLLVMGenerator:
    """matha_cc 兼容 LLVM 生成器（未实现，显式拒绝而非无效 IR）。"""

    def __init__(self, module_name: str = "matha") -> None:
        self._module_name = module_name

    def generate(self, _ir) -> str:
        raise NotImplementedError(
            "LLVM 生成器未实现（此前把三地址码贴进 LLVM 模板产出无效 IR，现显式拒绝）")


def matha_to_llvm(source: str) -> str:
    """matha_cc 兼容：Matha → LLVM IR（未实现，显式拒绝）。"""
    raise NotImplementedError(
        "Matha → LLVM IR 未实现（此前返回无效 IR 文本，现显式拒绝）")


# ============================================================
# 3. 后端：真实工具链委托
# ============================================================

class MathaBackend:
    """LLVM 后端外壳：真实工具链调用住在 src/plugins/toolchain_llvm.py。

    工具缺失/编译失败直接抛 ToolchainUnavailable（附安装指引），不返回空串、
    不产出模拟产物。
    """

    def __init__(self, toolchain: str = "clang") -> None:
        self._toolchain = toolchain
        self._cache: dict = {}

    def compile(self, llvm_ir: str, output_name: str = "matha_out") -> str:
        import hashlib
        from src.plugins import toolchain_llvm
        cache_key = hashlib.sha256(llvm_ir.encode()).hexdigest()[:16]
        if cache_key in self._cache:
            return self._cache[cache_key]
        exe_file = toolchain_llvm.compile_llvm(llvm_ir, output_name)
        self._cache[cache_key] = exe_file
        return exe_file

    def run(self, exe_path: str, args: list = None) -> subprocess.CompletedProcess:
        from src.plugins.toolchain_llvm import run_exe
        return run_exe(exe_path, args)

    @property
    def cache_stats(self) -> dict:
        from src.plugins import toolchain_llvm
        return {"cached": len(self._cache), "toolchain": self._toolchain,
                "availability": toolchain_llvm.describe_availability()}


# ============================================================
# 4. 编译 / 运行入口（真实计数 + 真实执行）
# ============================================================

def matha_compile(source: str, output_name: str = "out", optimize: bool = True) -> str:
    """编译入口（真编译：parse + mbc compile_program）。

    返回携带真实计数的摘要：声明数 / 函数数 / 主代码 ops 数。
    optimize 仅为兼容签名保留——mbc 编译当前无优化开关。
    """
    from src.unified_parser import matha_compile as _real
    return _real(source, output_name)


def matha_run(source: str, args: list = None) -> subprocess.CompletedProcess:
    """运行入口（主解释器真实执行）。

    真实输出封入 subprocess.CompletedProcess（stdout = 各输出行拼接，
    returncode = 0）；运行期错误如实抛出。args 无解释器 argv 桥接，
    暂不参与执行。
    """
    from src.unified_parser import matha_run as _real
    outputs, _trace = _real(source)
    return subprocess.CompletedProcess(
        args=[source] + list(args or []),
        returncode=0,
        stdout="\n".join(str(item) for item in outputs),
        stderr="",
    )


class MathaCompiler:
    """matha-cc 统一编译器（真实 mbc 编译 + 真实执行的薄门面）。"""

    def __init__(self, optimize: bool = True) -> None:
        self._optimize = optimize
        self._stats = {"compile_count": 0}

    def compile_file(self, matha_file: str, output_name: str = "out") -> str:
        with open(matha_file, encoding="utf-8") as f:
            source = f.read()
        return self.compile_source(source, output_name)

    def compile_source(self, source: str, output_name: str = "out") -> str:
        self._stats["compile_count"] += 1
        return matha_compile(source, output_name)

    def run(self, source: str, args: list = None) -> subprocess.CompletedProcess:
        return matha_run(source, args)

    @property
    def stats(self) -> dict:
        return {**self._stats, "optimize": self._optimize}


# ============================================================
# 公共 API：C 转译与自举编译（委托 src.bootstrap 主链）
# ============================================================

def matha2c(source: str, optimize: bool = True) -> str:
    """将 Matha 源码转译为 C 代码。"""
    from src.bootstrap import bootstrap_compile
    return bootstrap_compile(source, target="c", optimize=optimize)


def matha_bootstrap_compile(source: str, target: str = "c",
                            optimize: bool = True,
                            target_base: int = 2,
                            hardware_profile: str | None = None
                            ) -> str:
    """完整自举编译 Matha 源码（委托 src.bootstrap 主实现）。"""
    from src.bootstrap import matha_bootstrap_compile as _real
    return _real(source, target, optimize, target_base, hardware_profile)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MathaLexer",
    "MathaParser",
    "MathaFrontend",
    "MathaLLVMGenerator",
    "MathaBackend",
    "MathaCompiler",
    "matha_compile",
    "matha_run",
    "matha_to_llvm",
    "matha2c",
    "matha_bootstrap_compile",
    "NumberSystemCompiler",
    "MathaBytecodeCompiler",
    "MathaSelfCompiler",
]
