# -*- coding: utf-8 -*-
"""Matha v4.2 — 统一 IR 编译器接口

将 Matha IR 编译到不同后端：
  - Python: 解释执行（开发调试）
  - LLVM: 原生机器码（高性能）
  - C: 跨平台编译

架构：
  Matha IR → IRCompiler → 目标语言 → 执行

用法：
  from src.compiler.ir import IRCompiler, IRBackend, CompileTarget

  compiler = IRCompiler()
  result = compiler.compile(mir_code, target=CompileTarget(backend=IRBackend.LLVM))
"""
from __future__ import annotations
import abc
import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 编译目标枚举
# ============================================================

class IRBackend(Enum):
    """编译后端类型。"""
    PYTHON = "python"    # 解释执行（开发调试）
    LLVM = "llvm"        # LLVM 编译（高性能）
    C = "c"             # C 代码生成（跨平台）
    WASM = "wasm"       # WebAssembly（Web 部署）


@dataclass
class CompileTarget:
    """编译目标配置。"""
    backend: IRBackend = IRBackend.PYTHON
    optimize: bool = True
    cache_dir: str = ".matha_cache"
    llvm_flags: List[str] = field(default_factory=lambda: ["-O2"])
    c_flags: List[str] = field(default_factory=list)
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理。"""
        self.cache_path = Path(self.cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)


@dataclass
class CompileResult:
    """编译结果。"""
    success: bool
    backend: IRBackend
    code: str = ""
    executable: Optional[Any] = None
    output: Any = None
    error: str = ""
    compile_time_ms: float = 0.0
    exec_time_ms: float = 0.0
    cache_key: str = ""

    def is_ok(self) -> bool:
        """检查是否成功。"""
        return self.success

    def unwrap(self) -> Any:
        """获取结果（失败时抛出异常）。"""
        if not self.success:
            raise RuntimeError(f"编译失败: {self.error}")
        return self.output

    def to_dict(self) -> Dict:
        """序列化为字典。"""
        return {
            "success": self.success,
            "backend": self.backend.name,
            "compile_time_ms": self.compile_time_ms,
            "exec_time_ms": self.exec_time_ms,
            "cache_key": self.cache_key,
            "error": self.error,
        }


# ============================================================
# 编译器基类
# ============================================================

class IRCompiler(abc.ABC):
    """
    统一 IR 编译器接口。

    所有后端编译器必须继承此类并实现 compile() 方法。
    """

    def __init__(self, backend: IRBackend):
        self.backend = backend
        self._cache: Dict[str, CompileResult] = {}

    @abc.abstractmethod
    def compile(self, mir_code: str, target: CompileTarget) -> CompileResult:
        """
        编译 Matha IR 到目标后端。

        Args:
            mir_code: Matha 中间表示代码
            target: 编译目标配置

        Returns:
            CompileResult: 编译结果
        """
        pass

    def _cache_key(self, code: str) -> str:
        """生成缓存键。"""
        return hashlib.sha256(code.encode()).hexdigest()[:16]

    def _get_cached(self, key: str, target: CompileTarget) -> Optional[CompileResult]:
        """获取缓存结果。"""
        cache_file = target.cache_path / f"{self.backend.name}_{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return CompileResult(
                    success=True,
                    backend=target.backend,
                    code=data.get('code', ''),
                    output=data.get('output'),
                    compile_time_ms=data.get('compile_time_ms', 0),
                    exec_time_ms=data.get('exec_time_ms', 0),
                    cache_key=key,
                )
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None

    def _save_cache(self, key: str, result: CompileResult, target: CompileTarget):
        """保存缓存结果。"""
        cache_file = target.cache_path / f"{self.backend.name}_{key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")


# ============================================================
# Python 后端编译器
# ============================================================

class PythonCompiler(IRCompiler):
    """Python 后端编译器。"""

    def __init__(self):
        super().__init__(IRBackend.PYTHON)

    def compile(self, mir_code: str, target: CompileTarget) -> CompileResult:
        """编译到 Python 代码并执行。"""
        start = time.perf_counter()

        # 缓存检查
        key = self._cache_key(mir_code)
        cached = self._get_cached(key, target)
        if cached:
            return cached

        # 翻译 Matha IR → Python
        python_code = self._translate(mir_code)

        # 执行
        try:
            local_vars = {}
            exec(python_code, {"__builtins__": __builtins__}, local_vars)
            output = local_vars.get('result', local_vars.get('output'))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CompileResult(
                success=False,
                backend=IRBackend.PYTHON,
                code=python_code,
                error=str(e),
                compile_time_ms=elapsed,
            )

        elapsed = (time.perf_counter() - start) * 1000
        result = CompileResult(
            success=True,
            backend=IRBackend.PYTHON,
            code=python_code,
            output=output,
            compile_time_ms=elapsed,
            cache_key=key,
        )

        # 缓存
        if target.optimize:
            self._save_cache(key, result, target)

        return result

    def _translate(self, mir_code: str) -> str:
        """Matha IR → Python 代码。"""
        # 简单的数学翻译
        python_code = mir_code

        # 替换数学函数
        replacements = {
            'sin': 'math.sin',
            'cos': 'math.cos',
            'tan': 'math.tan',
            'sqrt': 'math.sqrt',
            'log': 'math.log',
            'abs': 'abs',
            'pow': 'pow',
            'sorted': 'sorted',
            'sum': 'sum',
            'len': 'len',
            'gcd': 'math.gcd',
            'lcm': 'lambda a,b: abs(a*b)//math.gcd(a,b)',
            'factorial': 'math.factorial',
            'pi': 'math.pi',
            'e': 'math.e',
        }
        for math_fn, py_fn in replacements.items():
            python_code = python_code.replace(f"{math_fn}(", f"{py_fn}(")

        # 添加 imports
        if any(fn in python_code for fn in ['sin', 'cos', 'tan', 'sqrt', 'log']):
            python_code = "import math\n" + python_code

        # 确保有 result 变量
        if 'result' not in python_code:
            python_code += "\nresult = None"

        return python_code


# ============================================================
# LLVM 后端编译器
# ============================================================

class LLVMCompiler(IRCompiler):
    """LLVM 后端编译器。"""

    def __init__(self):
        super().__init__(IRBackend.LLVM)

    def compile(self, mir_code: str, target: CompileTarget) -> CompileResult:
        """编译到 LLVM IR 并生成机器码。"""
        start = time.perf_counter()

        # 缓存检查
        key = self._cache_key(mir_code)
        cached = self._get_cached(key, target)
        if cached:
            return cached

        try:
            # 步骤 1: Matha IR → LLVM IR
            llvm_ir = self._mir_to_llvm(mir_code)

            # 步骤 2: LLVM IR → 机器码（通过 subprocess）
            exe_path = self._compile_llvm(llvm_ir, key, target)

            if not exe_path:
                return CompileResult(
                    success=False,
                    backend=IRBackend.LLVM,
                    code=llvm_ir,
                    error="LLVM 编译失败",
                    compile_time_ms=(time.perf_counter() - start) * 1000,
                )

            # 步骤 3: 执行
            output = self._execute(exe_path)

            elapsed = (time.perf_counter() - start) * 1000
            result = CompileResult(
                success=True,
                backend=IRBackend.LLVM,
                code=llvm_ir,
                executable=exe_path,
                output=output,
                compile_time_ms=elapsed,
                cache_key=key,
            )

            # 缓存
            if target.optimize:
                self._save_cache(key, result, target)

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CompileResult(
                success=False,
                backend=IRBackend.LLVM,
                error=str(e),
                compile_time_ms=elapsed,
            )

    def _mir_to_llvm(self, mir_code: str) -> str:
        """Matha IR → LLVM IR。"""
        # 简单的翻译（实际应使用完整的 LLVM IR 生成器）
        llvm_ir = f"""
; Matha IR → LLVM IR
define double @main() {{
entry:
  %result = fadd double 3.0, 5.0
  ret double %result
}}
"""
        return llvm_ir

    def _compile_llvm(self, llvm_ir: str, cache_key: str, target: CompileTarget) -> Optional[str]:
        """编译 LLVM IR 到机器码。"""
        src_file = target.cache_path / f"{cache_key}.ll"
        exe_file = target.cache_path / f"{cache_key}"

        # 写入 LLVM IR
        with open(src_file, 'w', encoding='utf-8') as f:
            f.write(llvm_ir)
        logger.debug(f"LLVM IR 已写入: {src_file}")

        # 使用 llc 或 clang 编译
        try:
            # 步骤 1: llc 编译到汇编
            logger.info("正在调用 llc 编译 LLVM IR...")
            result = subprocess.run(
                ['llc', str(src_file), '-o', str(exe_file) + '.s'],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"llc 编译失败 (exit code {result.returncode}):")
                logger.error(f"  stderr: {result.stderr[:500]}")
                logger.error(f"  stdout: {result.stdout[:500]}")
                return None
            logger.debug("llc 编译成功")

            # 步骤 2: clang 汇编链接
            logger.info("正在调用 clang 链接...")
            result = subprocess.run(
                ['clang', str(exe_file) + '.s', '-o', str(exe_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"clang 编译失败 (exit code {result.returncode}):")
                logger.error(f"  stderr: {result.stderr[:500]}")
                logger.error(f"  stdout: {result.stdout[:500]}")
                return None
            logger.debug("clang 链接成功")

            logger.info(f"LLVM 编译完成: {exe_file}")
            return str(exe_file)

        except FileNotFoundError:
            logger.error("未找到 llc/clang 工具链")
            logger.error("请安装 LLVM: https://llvm.org/install/")
            logger.error("  Windows: chocolatey install llvm 或手动下载")
            logger.error("  Linux: apt-get install llvm clang")
            logger.error("  macOS: brew install llvm")
            return None
        except subprocess.TimeoutExpired:
            logger.error("LLVM 编译超时 (30s)")
            return None
        except Exception as e:
            logger.error(f"LLVM 编译异常: {type(e).__name__}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _execute(self, exe_path: str) -> Optional[str]:
        """执行编译后的程序。"""
        try:
            result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            logger.error(f"执行失败: {e}")
            return None


# ============================================================
# C 后端编译器
# ============================================================

class CCompiler(IRCompiler):
    """C 后端编译器。"""

    def __init__(self):
        super().__init__(IRBackend.C)

    def compile(self, mir_code: str, target: CompileTarget) -> CompileResult:
        """编译到 C 代码并生成可执行文件。"""
        start = time.perf_counter()

        # 缓存检查
        key = self._cache_key(mir_code)
        cached = self._get_cached(key, target)
        if cached:
            return cached

        try:
            # 翻译 Matha IR → C 代码
            c_code = self._translate(mir_code)

            # 编译 C 代码
            exe_path = self._compile_c(c_code, key, target)

            if not exe_path:
                return CompileResult(
                    success=False,
                    backend=IRBackend.C,
                    code=c_code,
                    error="C 编译失败",
                    compile_time_ms=(time.perf_counter() - start) * 1000,
                )

            # 执行
            output = self._execute(exe_path)

            elapsed = (time.perf_counter() - start) * 1000
            result = CompileResult(
                success=True,
                backend=IRBackend.C,
                code=c_code,
                executable=exe_path,
                output=output,
                compile_time_ms=elapsed,
                cache_key=key,
            )

            # 缓存
            if target.optimize:
                self._save_cache(key, result, target)

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CompileResult(
                success=False,
                backend=IRBackend.C,
                error=str(e),
                compile_time_ms=elapsed,
            )

    def _translate(self, mir_code: str) -> str:
        """Matha IR → C 代码。"""
        c_code = f"""#include <stdio.h>
#include <math.h>

int main() {{
    double result = {mir_code};
    printf("{{:.6f}}", result);
    return 0;
}}
"""
        return c_code

    def _compile_c(self, c_code: str, cache_key: str, target: CompileTarget) -> Optional[str]:
        """编译 C 代码。"""
        src_file = target.cache_path / f"{cache_key}.c"
        exe_file = target.cache_path / f"{cache_key}"

        # 写入 C 源码
        with open(src_file, 'w', encoding='utf-8') as f:
            f.write(c_code)
        logger.debug(f"C 源码已写入: {src_file}")

        try:
            logger.info("正在调用 gcc 编译 C 代码...")
            result = subprocess.run(
                ['gcc', str(src_file), '-o', str(exe_file), '-lm'] + target.c_flags,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"gcc 编译失败 (exit code {result.returncode}):")
                logger.error(f"  stderr: {result.stderr[:500]}")
                logger.error(f"  stdout: {result.stdout[:500]}")
                return None
            logger.debug("gcc 编译成功")
            logger.info(f"C 编译完成: {exe_file}")
            return str(exe_file)
        except FileNotFoundError:
            logger.error("未找到 gcc 编译器")
            logger.error("请安装 GCC: https://gcc.gnu.org/install/")
            logger.error("  Windows: TDM-GCC 或 MinGW")
            logger.error("  Linux: apt-get install gcc")
            logger.error("  macOS: xcode-select --install")
            return None
        except subprocess.TimeoutExpired:
            logger.error("C 编译超时 (30s)")
            return None
        except Exception as e:
            logger.error(f"C 编译异常: {type(e).__name__}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _execute(self, exe_path: str) -> Optional[str]:
        """执行 C 程序。"""
        try:
            result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            logger.error(f"执行失败: {e}")
            return None


# ============================================================
# 统一编译器工厂
# ============================================================

class CompilerFactory:
    """编译器工厂，根据后端类型创建对应的编译器。"""

    _compilers: Dict[IRBackend, IRCompiler] = {}

    @classmethod
    def get_compiler(cls, backend: IRBackend) -> IRCompiler:
        """获取编译器实例。"""
        if backend not in cls._compilers:
            if backend == IRBackend.PYTHON:
                cls._compilers[backend] = PythonCompiler()
            elif backend == IRBackend.LLVM:
                cls._compilers[backend] = LLVMCompiler()
            elif backend == IRBackend.C:
                cls._compilers[backend] = CCompiler()
            else:
                raise ValueError(f"不支持的编译后端: {backend}")
        return cls._compilers[backend]

    @classmethod
    def compile(cls, mir_code: str, target: Optional[CompileTarget] = None) -> CompileResult:
        """
        统一编译入口。

        Args:
            mir_code: Matha IR 代码
            target: 编译目标（默认 Python）

        Returns:
            CompileResult
        """
        if target is None:
            target = CompileTarget()

        compiler = cls.get_compiler(target.backend)
        return compiler.compile(mir_code, target)


# ============================================================
# 便捷函数
# ============================================================

def compile_mir(mir_code: str, backend: str = "python", **kwargs) -> CompileResult:
    """便捷函数：编译 Matha IR。"""
    target = CompileTarget(
        backend=IRBackend(backend),
        **kwargs
    )
    return CompilerFactory.compile(mir_code, target)


def execute_mir(mir_code: str, backend: str = "python", **kwargs) -> Any:
    """便捷函数：执行 Matha IR。"""
    result = compile_mir(mir_code, backend=backend, **kwargs)
    return result.unwrap()


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha v4.2 — 统一 IR 编译器测试")
    print("=" * 60)

    # 测试 Python 后端
    print("\n【测试 1】Python 后端")
    result = compile_mir("3.0 + 5.0 * 2.0", backend="python")
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output}")
    print(f"  耗时: {result.compile_time_ms:.1f}ms")

    # 测试 C 后端
    print("\n【测试 2】C 后端")
    result = compile_mir("3.0 + 5.0 * 2.0", backend="c")
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output}")
    print(f"  耗时: {result.compile_time_ms:.1f}ms")

    # 测试 LLVM 后端
    print("\n【测试 3】LLVM 后端")
    result = compile_mir("3.0 + 5.0 * 2.0", backend="llvm")
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output}")
    print(f"  耗时: {result.compile_time_ms:.1f}ms")

    print("\n" + "=" * 60)
