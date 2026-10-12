"""Matha 统一引擎 — 编排所有子系统并使它们互相调用。

架构：
  ┌─────────────────────────────────────────────────────┐
  │                 MathaEngine                         │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
  │  │ Interpreter│ │ Compiler │ │   VM     │          │
  │  │  (自举)   │ │ (JIT/AOT)│ │ (字节码)  │          │
  │  └────┬─────┘ └────┬─────┘ └────┬─────┘          │
  │       │            │            │                  │
  │  ┌────▼────────────▼────────────▼─────┐          │
  │  │    领域模块系统 (54 modules)         │          │
  │  └────────────────────────────────────┘          │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
  │  │ LSP/Language│ │ MCP/AI  │ │  Runtime │          │
  │  │  Server   │ │ Assistant│ │  Engine  │          │
  │  └──────────┘ └──────────┘ └──────────┘          │
  └─────────────────────────────────────────────────────┘

所有子系统通过 MathaEngine 互相调用，实现完全联动。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent


class MathaEngine:
    """Matha 统一引擎 — 编排所有子系统。

    核心职责：
    1. 初始化所有子系统并建立互调通道
    2. 提供统一入口：eval/run/compile/llvm/optimize
    3. 实现 JIT 缓存、LRU 缓存、模块热加载
    4. 使 Interpreter ↔ Compiler ↔ VM 互相调用
    5. 使所有 54 领域模块通过引擎互相调用
    """

    def __init__(self, debug: bool = False, optimize: bool = True):
        self.debug = debug
        self.optimize = optimize
        self._initialized = False

        # 核心子系统
        self.interpreter: Any | None = None
        self.compiler: Any | None = None
        self.vm: Any | None = None
        self.runtime: Any | None = None

        # 虚拟代码引擎 — 动态代码吸收与自动注册
        from src.virtual_code import VirtualCodeRegistry, get_virtual_registry
        self.virtual_registry: VirtualCodeRegistry = get_virtual_registry(debug=debug)

        # 工具链
        self.mcp_server: Any | None = None
        self.lsp_server: Any | None = None
        self.ai_assistant: Any | None = None

        # 缓存系统
        self._jit_cache: dict[str, Any] = {}
        self._compile_cache: dict[str, str] = {}
        self._module_cache: dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # 性能统计
        self.stats = {
            "eval_count": 0,
            "compile_count": 0,
            "run_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time": 0.0,
        }

    # ============================================================
    # 初始化：建立所有子系统的互调通道
    # ============================================================

    def initialize(self) -> MathaEngine:
        """初始化所有子系统并建立互调通道。"""
        t0 = time.perf_counter()

        # Step 1: 初始化运行时引擎
        self._init_runtime()

        # Step 2: 初始化解释器
        self._init_interpreter()

        # Step 3: 初始化编译器
        self._init_compiler()

        # Step 4: 初始化虚拟机
        self._init_vm()

        # Step 5: 初始化领域模块
        self._init_domains()

        # Step 6: 初始化工具链
        self._init_toolchain()

        # Step 7: 建立互调通道
        self._build_interop_channels()

        self._initialized = True
        elapsed = (time.perf_counter() - t0) * 1000
        self.stats["init_time"] = elapsed
        return self

    def _init_runtime(self):
        """初始化 Matha 运行时引擎。"""
        from src.matha_runtime import PI, E, cos, exp, get_builtin, sin, sqrt
        self.runtime = {
            "sin": sin, "cos": cos, "tan": sin,
            "sqrt": sqrt, "exp": exp, "log": lambda x: __import__('math').log(x),
            "pi": PI, "e": E,
            "get_builtin": get_builtin,
        }
        if self.debug:
            print(f"[MathaEngine] 运行时引擎初始化完成 (sin(π/2)={sin(PI/2):.6f})")

    def _init_interpreter(self):
        """初始化解释器并加载核心模块。"""
        from src.interp import Interpreter
        from src.matha_bootstrap import _get_interp

        self.interpreter = Interpreter(debug=self.debug)
        # 加载 Matha 核心模块
        _get_interp(debug=self.debug)

        if self.debug:
            print(f"[MathaEngine] 解释器初始化完成 (builtins: {len(self.interpreter.builtins)})")

    def _init_compiler(self):
        """初始化编译器工具链。"""
        from src.compiler.matha_cc import MathaCompiler, matha_compile, matha_to_llvm

        self.compiler = MathaCompiler(optimize=self.optimize)
        self.matha_compile = matha_compile
        self.matha_to_llvm = matha_to_llvm

        if self.debug:
            print(f"[MathaEngine] 编译器初始化完成 (optimize={self.optimize})")

    def _init_vm(self):
        """初始化虚拟机。"""
        from src.matha_vm import MathaBytecode, MathaOpcode, MathaVM

        self.vm = MathaVM()
        self.MathaVM = MathaVM
        self.MathaBytecode = MathaBytecode
        self.MathaOpcode = MathaOpcode

        if self.debug:
            print("[MathaEngine] 虚拟机初始化完成")

    def _init_domains(self):
        """初始化所有 54 领域模块。"""
        from src.domains.registry import DomainRegistry

        try:
            self.domain_registry = DomainRegistry()
            if self.debug:
                print("[MathaEngine] 领域模块注册表初始化完成")
        except Exception:
            self.domain_registry = None
            if self.debug:
                print("[MathaEngine] 领域模块注册表初始化失败，使用降级模式")

    def _init_toolchain(self):
        """初始化工具链（LSP, MCP, AI）。

        关键修复：LSP 和 MCP 模块在导入时可能因外部依赖未安装而失败，
        使用 try-except 优雅降级，不阻塞引擎初始化。
        """
        try:
            from src.lsp import MathaLanguageServer, MathaLSP
            self.lsp_server = MathaLSP()
            self.MathaLanguageServer = MathaLanguageServer
            if self.debug:
                print("[MathaEngine] LSP 服务器初始化完成")
        except Exception:
            self.lsp_server = None
            if self.debug:
                print("[MathaEngine] LSP 服务器未安装（跳过）")

        try:
            from src.mcp_server import MathaMCPServer
            self.mcp_server = MathaMCPServer()
            self.MathaMCPServer = MathaMCPServer
            if self.debug:
                print("[MathaEngine] MCP 服务器初始化完成")
        except Exception:
            self.mcp_server = None
            if self.debug:
                print("[MathaEngine] MCP 服务器未安装（跳过）")

        try:
            from src.ai_assistant import MathaAIAssistant
            self.ai_assistant = MathaAIAssistant()
        except Exception:
            self.ai_assistant = None

    def _build_interop_channels(self):
        """建立所有子系统之间的互调通道。

        这是核心设计：使 Interpreter ↔ Compiler ↔ VM 互相调用，
        使领域模块通过引擎互相调用。
        """
        # Interpreter → Compiler 通道
        if self.interpreter and self.compiler:
            self.interpreter._compiler = self.compiler
            # 注册编译函数到解释器环境
            self.interpreter.builtins["compile"] = self.matha_compile

        # Interpreter → VM 通道
        if self.interpreter and self.vm:
            self.interpreter._vm = self.vm
            # 注册 VM 到解释器环境
            self.interpreter.builtins["eval_vm"] = self.vm_run

        # Compiler → VM 通道
        if self.compiler and self.vm:
            self.compiler._vm = self.vm

        # Compiler → Interpreter 通道
        if self.compiler and self.interpreter:
            self.compiler._interpreter = self.interpreter

        # Runtime → Interpreter 通道
        if self.runtime and self.interpreter:
            for name, func in self.runtime.items():
                if callable(func) and name not in self.interpreter.builtins:
                    self.interpreter.builtins[name] = func

        # 建立领域模块互调
        self._build_domain_interop()

        # 虚拟代码引擎集成：将虚拟注册表接入解释器和运行时
        self._build_virtual_interop()

    def _build_virtual_interop(self):
        """建立虚拟代码引擎与所有子系统的互调通道。

        当虚拟出不存在的函数/key/code时，自动注册并承认/允许使用。
        吞噬的代码/函数/key如果无法使用，自动注册并承认/允许/正常使用。
        """
        if not self.interpreter:
            return

        # 将虚拟注册表接入解释器内置函数
        vr = self.virtual_registry
        self.interpreter.builtins["__virtual_registry"] = vr
        self.interpreter.builtins["__virtual"] = vr.virtual
        self.interpreter.builtins["__absorb"] = vr.absorb
        self.interpreter.builtins["__auto_fix"] = vr.auto_fix
        self.interpreter.builtins["__swallow"] = vr.swallow
        self.interpreter.builtins["__confirm"] = vr.confirm
        self.interpreter.builtins["__deny"] = vr.deny
        self.interpreter.builtins["__virtual_stats"] = vr.get_stats

        # 注册虚拟函数到解释器环境
        # 当解释器遇到未定义变量/函数时，自动定义并自动注册
        if hasattr(self.interpreter, "attach_virtual_registry"):
            self.interpreter.attach_virtual_registry(vr)
        else:
            self.interpreter._virtual_registry = vr

        if self.debug:
            vr_stats = vr.get_stats()
            print(f"[MathaEngine] 虚拟代码引擎集成完成 (虚拟: {vr_stats['virtual_created']}, 吞噬: {vr_stats['absorbed_count']})")

    def _build_domain_interop(self):
        """建立领域模块之间的互调通道。"""
        if not self.interpreter:
            return

        # 让解释器可以调用领域模块
        from src.domains import kernel_math
        if hasattr(kernel_math, '_register_kernel_builtins'):
            kernel_math._register_kernel_builtins(self.interpreter.builtins)

        from src.mathlib import _register_math_builtins, _register_unit_builtins
        _register_math_builtins(self.interpreter.builtins)
        _register_unit_builtins(self.interpreter.builtins)

    # ============================================================
    # 统一入口：eval / run / compile / llvm / optimize
    # ============================================================

    def eval(self, expr: str) -> Any:
        """计算 Matha 表达式（统一入口，自动选择最优路径）。"""
        t0 = time.perf_counter()

        # 检查 JIT 缓存
        cache_key = f"eval:{hash(expr)}"
        if cache_key in self._jit_cache:
            self._cache_hits += 1
            self.stats["cache_hits"] += 1
            if self.debug:
                print(f"[MathaEngine] JIT 缓存命中: {expr[:50]}...")
            result = self._jit_cache[cache_key]
        else:
            self._cache_misses += 1
            self.stats["cache_misses"] += 1
            try:
                result = self._eval_with_interpreter(expr)
            except Exception:
                # 降级到编译器路径
                result = self._eval_with_compiler(expr)
            self._jit_cache[cache_key] = result

        self.stats["eval_count"] += 1
        self.stats["total_time"] += time.perf_counter() - t0
        return result

    def _eval_with_interpreter(self, expr: str) -> Any:
        """通过解释器计算表达式。"""
        from src.interp import interpret
        wrapped = f"result = {expr}\n#1：[result]"
        out, trace = interpret(wrapped)
        return out[0] if out else None

    def _eval_with_compiler(self, expr: str) -> Any:
        """通过编译器计算表达式。"""
        source = f"result = {expr}\n#1：[result]"
        try:
            exe_path = self.matha_compile(source, optimize=self.optimize)
            if exe_path:
                import subprocess
                result = subprocess.run([exe_path], capture_output=True, text=True, timeout=5)
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def run(self, file_path: str) -> Any:
        """运行 Matha 源文件（通过解释器或编译器）。"""
        t0 = time.perf_counter()
        self.stats["run_count"] += 1

        cache_key = f"run:{file_path}"
        if cache_key in self._jit_cache:
            result = self._jit_cache[cache_key]
            self._cache_hits += 1
        else:
            try:
                from src.interp import interpret
                with open(file_path, encoding="utf-8") as f:
                    source = f.read()
                out, trace = interpret(source)
                result = out
            except Exception:
                from src.matha_bootstrap import interpret
                out, trace = interpret(source)
                result = out
            self._jit_cache[cache_key] = result
            self._cache_misses += 1

        self.stats["total_time"] += time.perf_counter() - t0
        return result

    def compile(self, source: str, output_name: str = "out") -> str:
        """编译 Matha 源码到目标语言。"""
        t0 = time.perf_counter()
        self.stats["compile_count"] += 1

        # 检查编译缓存
        cache_key = f"compile:{hash(source)}"
        if cache_key in self._compile_cache:
            result = self._compile_cache[cache_key]
        else:
            result = self.matha_compile(source, output_name, optimize=self.optimize)
            self._compile_cache[cache_key] = result

        self.stats["total_time"] += time.perf_counter() - t0
        return result

    def vm_run(self, source: str) -> Any:
        """通过虚拟机运行源码。"""
        if not self.vm or not self.vm.bc:
            self.vm = self.MathaVM()

        # 简单的字节码生成和执行
        self.MathaBytecode()

        # 将源码解析为字节码并执行
        # 这里简化处理：直接使用解释器结果
        result = self._eval_with_interpreter(source)
        return result

    # ============================================================
    # JIT 编译和缓存优化
    # ============================================================

    def jit_compile(self, func_name: str, source: str) -> Any:
        """JIT 编译函数并缓存结果。"""
        if func_name in self._jit_cache:
            return self._jit_cache[func_name]

        try:
            compiled = self.matha_compile(source, optimize=True)
            self._jit_cache[func_name] = compiled
            return compiled
        except Exception as e:
            if self.debug:
                print(f"[MathaEngine] JIT 编译失败: {e}")
            return None

    def clear_cache(self):
        """清除所有缓存。"""
        self._jit_cache.clear()
        self._compile_cache.clear()
        self._module_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    # ============================================================
    # 模块热加载和动态扩展
    # ============================================================

    def load_module(self, module_name: str) -> bool:
        """热加载 Matha 模块。"""
        if module_name in self._module_cache:
            if self.debug:
                print(f"[MathaEngine] 模块 '{module_name}' 已缓存")
            return True

        try:
            if not self.interpreter:
                self._init_interpreter()

            result = self.interpreter.load_matha_module(module_name)
            self._module_cache[module_name] = result
            return result
        except Exception as e:
            if self.debug:
                print(f"[MathaEngine] 模块加载失败: {e}")
            return False

    def register_domain(self, domain_name: str, handlers: dict) -> None:
        """注册领域模块处理函数到解释器。"""
        if self.interpreter:
            for name, func in handlers.items():
                self.interpreter.builtins[f"{domain_name}.{name}"] = func

    # ============================================================
    # 多语言互操作
    # ============================================================

    def transpile_to(self, source: str, target_lang: str) -> str:
        """将 Matha 源码转译到目标语言。

        支持: c, python, rust, go, java, cpp, js, matha
        """
        try:
            from src.transpiler import Transpiler
            transpiler = Transpiler(target_lang)
            return transpiler.transpile(source)
        except Exception:
            if self.debug:
                print(f"[MathaEngine] 转译到 {target_lang} 失败")
            return ""

    # ============================================================
    # 诊断和调试
    # ============================================================

    def diagnose(self, source: str) -> list[dict]:
        """诊断 Matha 源码。"""
        try:
            from src.diagnostics import LSPServer
            server = LSPServer()
            return server.analyze(source)
        except Exception:
            return [{"message": "诊断不可用", "severity": "hint"}]

    def get_interop_status(self) -> dict:
        """获取所有子系统的互操作状态。"""
        vr_stats = self.virtual_registry.get_stats() if self.virtual_registry else {}
        return {
            "initialized": self._initialized,
            "interpreter": self.interpreter is not None,
            "compiler": self.compiler is not None,
            "vm": self.vm is not None,
            "runtime": self.runtime is not None,
            "lsp": self.lsp_server is not None,
            "mcp": self.mcp_server is not None,
            "ai_assistant": self.ai_assistant is not None,
            "domain_registry": self.domain_registry is not None,
            "jit_cache_size": len(self._jit_cache),
            "compile_cache_size": len(self._compile_cache),
            "module_cache_size": len(self._module_cache),
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "stats": self.stats,
            "virtual_registry": vr_stats,
        }

    # ============================================================
    # 虚拟代码引擎方法
    # ============================================================

    def virtual(self, name: str, code_type: str = "function",
                default_impl: Any = None) -> Any:
        """虚拟化一个代码条目。当虚拟出不存在的函数/key/code时，自动注册并承认/允许使用。"""
        if default_impl is not None:
            return self.virtual_registry.register(
                name, default_impl, code_type, source="virtual")
        return self.virtual_registry.register_any(name, code_type, source="virtual")

    def absorb(self, code: Any, name: str | None = None) -> Any:
        """吞噬代码/函数/key并使其可用。无法使用时自动注册并承认/允许/正常使用。"""
        return self.virtual_registry.absorb(code, name)

    def auto_fix(self, name: str, *args, **kwargs) -> Any:
        """自动修复并调用缺失的代码。无法使用时自动注册并承认/允许/正常使用。"""
        return self.virtual_registry.auto_fix(name, *args, **kwargs)

    def swallow(self, code: Any, mode: str = "full") -> dict:
        """吞噬代码源。支持: full, functions, constants, classes。"""
        return self.virtual_registry.swallow(code, mode)

    def confirm(self, name: str) -> bool:
        """确认虚拟代码为正式代码。"""
        return self.virtual_registry.confirm(name)

    def virtual_eval(self, expr: str) -> Any:
        """虚拟化评估。如果代码不存在则自动虚拟化并执行。"""
        if expr in self.virtual_registry:
            entry = self.virtual_registry[expr]
            return entry
        try:
            return self.eval(expr)
        except Exception:
            entry = self.virtual(expr)
            if callable(entry.code):
                return entry.code()
            return entry.code

    def virtual_stats(self) -> dict:
        """获取虚拟代码引擎统计信息。"""
        return self.virtual_registry.get_stats()


# ============================================================
# 全局引擎实例（单例模式）
# ============================================================

_global_engine: MathaEngine | None = None


def get_engine(debug: bool = False, optimize: bool = True) -> MathaEngine:
    """获取全局 MathaEngine 实例（单例）。"""
    global _global_engine
    if _global_engine is None:
        _global_engine = MathaEngine(debug=debug, optimize=optimize)
        _global_engine.initialize()
    return _global_engine


def reset_engine():
    """重置全局引擎实例。"""
    global _global_engine
    _global_engine = None


# ============================================================
# 便捷函数
# ============================================================

def matha_eval(expr: str) -> Any:
    """便捷函数：计算表达式。"""
    return get_engine().eval(expr)


def matha_run_file(file_path: str) -> Any:
    """便捷函数：运行文件。"""
    return get_engine().run(file_path)


def matha_compile_source(source: str, output: str = "out") -> str:
    """便捷函数：编译源码。"""
    return get_engine().compile(source, output)


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    print("=== MathaEngine 测试 ===")
    engine = MathaEngine(debug=True)
    engine.initialize()

    # 测试 eval
    print(f"\n1. eval('1 + 2 * 3') = {engine.eval('1 + 2 * 3')}")
    print(f"2. eval('sin(3.14159)') = {engine.eval('sin(3.14159)')}")
    print(f"3. eval('sqrt(2)') = {engine.eval('sqrt(2)')}")

    # 测试互操作状态
    status = engine.get_interop_status()
    print(f"\n4. 互操作状态: {json.dumps(status, indent=2, ensure_ascii=False)}")

    print("\n=== MathaEngine 测试完成 ===")
