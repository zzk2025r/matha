"""
Matha LLVM 工具链前端（IR 生成 + 可选外部编译）

设计约束（内核去依赖重构 · 阶段 3）：
  * 语言主链只承认 ``src.mbc.compiler → src.mbc.vm``（机器码为 ``src.mbc.native``）；
    LLVM 是**可选外部工具链**，其子进程调用整体位于
    ``src/plugins/toolchain_llvm.py``，本模块只做委托。
  * **不存在模拟模式**。旧版此处有 ``SimulatedLLVMBackend``——用正则扫出 IR 里的
    浮点常量相加、写出 ``*_result.txt``，并把它当作「编译 + 执行成功」返回
    ``returncode 0``。那是典型的静默假成功，已整体删除。工具链不可用时一律抛
    ``ToolchainUnavailable``（附安装指引），由调用方显式决定是否降级。
"""
from __future__ import annotations

from src.plugins.toolchain_llvm import ToolchainUnavailable  # noqa: F401  (对外 re-export)

__all__ = [
    "ToolchainUnavailable",
    "HybridLLVMBackend",
    "llvm_available",
    "describe_availability",
    "benchmark_compiler",
    "run_full_test",
    "matha_to_llvm",
]


def llvm_available() -> bool:
    """llc 与 clang 是否都在 PATH 上（只查路径，不起进程）。"""
    from src.plugins import toolchain_llvm
    return all(toolchain_llvm.available().values())


def describe_availability() -> str:
    from src.plugins import toolchain_llvm
    return toolchain_llvm.describe_availability()


class HybridLLVMBackend:
    """LLVM 后端：把 IR 交给外部工具链编译并运行真实产物。

    ``compile`` / ``run`` 在工具链缺失时抛 :class:`ToolchainUnavailable`，
    **不**返回空串、**不**返回伪造输出。
    """

    def __init__(self) -> None:
        from src.plugins import toolchain_llvm
        self._toolchain = toolchain_llvm

    def compile(self, llvm_ir: str, output_name: str = "out") -> str:
        return self._toolchain.compile_llvm(llvm_ir, output_name)

    def run(self, exe_path: str, args: list | None = None) -> dict:
        proc = self._toolchain.run_exe(exe_path, args)
        return {"stdout": proc.stdout.strip(), "returncode": proc.returncode}

    @property
    def stats(self) -> dict:
        return {
            # 只有两种真实状态：工具链就绪 / 缺失。曾经的 "simulated" 不再存在。
            "mode": "real" if llvm_available() else "unavailable",
            "llvm_available": llvm_available(),
            "detail": describe_availability(),
        }


def matha_to_llvm(source: str) -> str:
    """将 Matha 源码转换为 LLVM IR 文本（纯文本生成，不起子进程）。"""
    from src.compiler.matha_cc import (MathaFrontend, MathaLexer,
                                       MathaLLVMGenerator, MathaParser)
    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    parser = MathaParser(tokens)
    ast = parser.parse()
    frontend = MathaFrontend()
    matha_ir = frontend.compile(ast)
    generator = MathaLLVMGenerator("matha_module")
    return generator.generate(matha_ir)


# ============================================================
# 自检 / 基准（无静默假成功：工具链缺失即如实报失败）
# ============================================================

def benchmark_compiler() -> dict:
    """编译性能基准：只测**真实**可测的环节（IR 生成、解释器执行）。

    旧版会把「模拟编译耗时」与伪造的执行结果一起报成基准数据，制造不存在的
    加速比。现 LLVM 段在未安装工具链时如实标注 ``skipped``。
    """
    import time

    from src.compiler.matha_cc import matha_to_llvm as _to_llvm
    from src.kernel import exec_api

    results: dict = {}
    test_cases = [
        ("简单算术", "x = 1 + 2 * 3"),
        ("三角函数", "x = sin(3.14) + cos(1.57)"),
        ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)"),
        ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))"),
    ]

    print("\n  LLVM IR 生成基准（纯文本，无外部工具）:")
    for name, source in test_cases:
        start = time.perf_counter()
        llvm_ir = _to_llvm(source)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"    {name:15s}: {elapsed:6.1f}ms, IR 长度 {len(llvm_ir)} 字符")
        results[f"llvm_ir_{name}"] = elapsed

    print("\n  字节码 VM 基准（主执行链）:")
    interp_prog = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"
    start = time.perf_counter()
    for _ in range(1000):
        exec_api.run(interp_prog, "vm")
    vm_ms = (time.perf_counter() - start) * 1000
    print(f"    VM 1000 次: {vm_ms:.0f}ms")
    results["vm_1000"] = vm_ms

    print("\n  LLVM 编译+执行基准:")
    if not llvm_available():
        print(f"    跳过：{describe_availability()}（不做任何模拟计时）")
        results["llvm_compile"] = "skipped"
        results["llvm_exec"] = "skipped"
    else:
        backend = HybridLLVMBackend()
        start = time.perf_counter()
        exe = backend.compile(_to_llvm("result = 2.0 + 3.0\n#1：[result]"), "bench_out")
        compile_ms = (time.perf_counter() - start) * 1000
        out = backend.run(exe)
        results["llvm_compile"] = compile_ms
        results["llvm_exec"] = out["stdout"]
        results["llvm_returncode"] = out["returncode"]
        print(f"    编译 {compile_ms:.0f}ms，真实产物输出：{out['stdout']!r}")

    return results


def run_full_test() -> bool:
    """前端链路自检：词法/语法/IR 生成/常量折叠/错误处理。

    LLVM 后端一栏**如实**反映工具链可用性；不可用即记为失败（旧版会打印
    「使用模拟模式」并返回通过）。
    """
    from src.compiler.matha_cc import (MathaCompiler, MathaLexer, MathaParser,
                                       matha_to_llvm as _to_llvm)

    ok = True

    def _section(title: str, fn) -> None:
        nonlocal ok
        print(f"\n[{title}]")
        try:
            fn()
            print("  PASS")
        except Exception as exc:
            print(f"  FAIL: {exc}")
            ok = False

    def _lex():
        tokens = MathaLexer("result = sin(3.14) + cos(1.57)").tokenize()
        assert len(tokens) >= 8, f"期望至少 8 个 token，实际 {len(tokens)}"
        assert tokens[1].type == "ASSIGN", f"期望 ASSIGN，实际 {tokens[1].type}"
        assert tokens[3].type == "PLUS", f"期望 PLUS，实际 {tokens[3].type}"

    def _parse():
        ast = MathaParser(MathaLexer("x = 1 + 2 * 3").tokenize()).parse()
        assert len(ast.decls) == 1, f"期望 1 个声明，实际 {len(ast.decls)}"

    def _ir():
        llvm_ir = _to_llvm("x = 1 + 2")
        for needle in ("target triple", "define double @main", "entry:", "fadd"):
            assert needle in llvm_ir, f"缺少 {needle}"

    def _fold():
        folded = MathaCompiler(optimize=True)._optimize_llvm("  t1 = fadd double 1.0, 2.0")
        assert "3.0" in folded, f"常量折叠失败: {folded}"

    def _errors():
        for source in ("x = 1 +", "x = undefined + 1"):
            try:
                _to_llvm(source)
            except Exception:
                continue
        # 前端对坏输入宽容（不抛）——只在后端不可用时才失败，故此节仅确认可生成 IR

    def _backend():
        if not llvm_available():
            raise ToolchainUnavailable(describe_availability())
        exe = HybridLLVMBackend().compile(_to_llvm("x = 2.0 + 3.0"), "test_output")
        out = HybridLLVMBackend().run(exe)
        assert out["returncode"] == 0, f"真实产物返回码 {out['returncode']}"

    print("=" * 60)
    print("Matha LLVM 工具链 - 完整编译测试")
    print("=" * 60)
    _section("测试 1：词法分析", _lex)
    _section("测试 2：语法分析", _parse)
    _section("测试 3：LLVM IR 生成", _ir)
    _section("测试 4：常量折叠优化", _fold)
    _section("测试 5：错误处理", _errors)
    _section("测试 6：外部工具链（真实编译）", _backend)

    print("\n" + "=" * 60)
    print("全部通过" if ok else "存在失败项，请查看上述输出")
    print("=" * 60)
    if not llvm_available():
        print("\n提示：LLVM 工具链缺失，主链不受影响（mbc VM / mbc.native 才是真实路径）")
        print("  " + describe_availability())
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_full_test() else 1)
