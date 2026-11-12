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
    """将 Matha 源码转换为 LLVM IR 文本。

    未实现——此前经 matha_cc 把三地址码贴进 LLVM 模板产出无效 IR 文本
    （llc 直接拒绝）；现显式拒绝，不再返回假产物。
    """
    from src.compiler.matha_cc import matha_to_llvm as _reject
    return _reject(source)


# ============================================================
# 自检 / 基准（无静默假成功：工具链缺失即如实报失败）
# ============================================================

def benchmark_compiler() -> dict:
    """编译性能基准：只测真实存在的链路（字节码 VM）。

    LLVM IR 生成未实现（matha_to_llvm 显式拒绝）——旧版对无效文本计时的
    「IR 生成基准」与依赖该文本的「LLVM 编译+执行基准」一并如实标注 skipped。
    """
    import time

    from src.kernel import exec_api

    results: dict = {}

    print("\n  LLVM IR 生成基准: skipped（matha_to_llvm 未实现，显式拒绝）")
    results["llvm_ir"] = "skipped"

    print("\n  字节码 VM 基准（主执行链）:")
    interp_prog = "result = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[result]"
    start = time.perf_counter()
    for _ in range(1000):
        exec_api.run(interp_prog, "vm")
    vm_ms = (time.perf_counter() - start) * 1000
    print(f"    VM 1000 次: {vm_ms:.0f}ms")
    results["vm_1000"] = vm_ms

    print("\n  LLVM 编译+执行基准: skipped（无真实 IR 生成器）")
    results["llvm_compile"] = "skipped"
    results["llvm_exec"] = "skipped"

    return results


def run_full_test() -> bool:
    """前端链路自检：词法/语法/真实编译计数/错误处理。

    IR 生成一栏如实标注未实现（matha_to_llvm 显式拒绝）；LLVM 后端一栏
    **如实**反映工具链可用性，不可用即记为失败。
    """
    from src.compiler.matha_cc import (MathaCompiler, MathaLexer, MathaParser,
                                       matha_compile, matha_to_llvm as _to_llvm)

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
        assert tokens[0].value == "result", f"期望 result，实际 {tokens[0].value!r}"
        assert tokens[1].type.name == "OP_ASSIGN", f"期望 OP_ASSIGN，实际 {tokens[1].type.name}"

    def _parse():
        ast = MathaParser(MathaLexer("x = 1 + 2 * 3").tokenize()).parse()
        assert len(ast.decls) == 1, f"期望 1 个声明，实际 {len(ast.decls)}"
        assert type(ast.decls[0]).__name__ == "Binding"

    def _compile():
        summary = matha_compile("func 加倍(x) -> Int = (x) => x * 2", "selftest")
        assert summary == "# Compiled 1 declarations to selftest: 1 functions, 1 ops", summary

    def _llvm_reject():
        try:
            _to_llvm("x = 1 + 2")
        except NotImplementedError:
            return
        raise AssertionError("matha_to_llvm 未显式拒绝（LLVM IR 生成未实现）")

    def _errors():
        from src.parser import ParseError
        for source in ("x = 1 +", "func 测试( = (x) => x + 1"):
            try:
                MathaParser(MathaLexer(source).tokenize()).parse()
            except ParseError:
                continue
            raise AssertionError(f"坏输入未报语法错误: {source!r}")

    def _compiler_run():
        result = MathaCompiler().run("result = 1 + 2 * 3\n#1：[result]")
        assert result.returncode == 0, f"退出码 {result.returncode}"
        assert result.stdout.splitlines() == ["7"], f"stdout={result.stdout!r}"

    def _backend():
        if not llvm_available():
            raise ToolchainUnavailable(describe_availability())
        # 工具链就绪但没有真实 IR 生成器——无 IR 可编译，如实跳过；
        # 真实端到端 LLVM 编译属 LLVM 主线工作（先实现 IR 生成）。
        print("  skipped：LLVM IR 生成未实现（matha_to_llvm 显式拒绝），无真实 IR 可编译")

    print("=" * 60)
    print("Matha LLVM 工具链 - 完整编译测试")
    print("=" * 60)
    _section("测试 1：词法分析", _lex)
    _section("测试 2：语法分析", _parse)
    _section("测试 3：真实编译计数", _compile)
    _section("测试 4：LLVM IR 显式拒绝", _llvm_reject)
    _section("测试 5：错误处理", _errors)
    _section("测试 6：统一编译器真实执行", _compiler_run)
    _section("测试 7：外部工具链（真实编译）", _backend)

    print("\n" + "=" * 60)
    print("全部通过" if ok else "存在失败项，请查看上述输出")
    print("=" * 60)
    if not llvm_available():
        print("\n提示：LLVM 工具链缺失，主链不受影响（mbc VM / mbc.native 才是真实路径）")
        print("  " + describe_availability())
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_full_test() else 1)
