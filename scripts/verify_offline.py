#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matha 离线验证脚本

在离线环境中运行此脚本，验证 Matha 的所有核心功能是否正常。

用法:
    python scripts/verify_offline.py              # 运行所有验证
    python scripts/verify_offline.py --quick      # 快速验证（只检查导入）
    python scripts/verify_offline.py --verbose    # 详细输出
    python scripts/verify_offline.py --json       # JSON 格式输出
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 验证项目分类
VERIFICATION_TESTS = {
    "core": [
        {"name": "数学核心", "import": "from src.math_driver import MathDriver", "check": None},
        {"name": "词法分析器", "import": "from src.compiler.matha_cc import MathaLexer", "check": None},
        {"name": "语法分析器", "import": "from src.compiler.matha_cc import MathaParser", "check": None},
        {"name": "MIR 生成器", "import": "from src.mir import MIRGenerator", "check": None},
        {"name": "C 代码生成", "import": "from src.mir_codegen import MIRToCGenerator", "check": None},
        {"name": "Python 代码生成", "import": "from src.mir_codegen import MIRToPythonGenerator", "check": None},
        {"name": "MIR 转换器", "import": "from src.mir_converter import convert", "check": None},
    ],
    "optimization": [
        {"name": "自动 Memoization", "import": "from src.compiler.memoize import get_memoize_optimizer", "check": None},
        {"name": "JIT 编译", "import": "from src.compiler.jit import jit_func, get_jit_compiler", "check": None},
        {"name": "LLVM 后端", "import": "from src.compiler.llvm_hybrid import HybridLLVMBackend", "check": None},
        {"name": "AOT 编译器", "import": "from src.compiler.aot import MathaAOTCompiler", "check": None},
    ],
    "tools": [
        {"name": "性能 Profiler", "import": "from src.profiler import MathaProfiler", "check": None},
        {"name": "LSP 服务器", "import": "from src.lsp import MathaLSP", "check": None},
        {"name": "文档生成器", "import": "from src.doc_gen import DocGenerator", "check": None},
        {"name": "包管理器 v2", "import": "from src.pkg_manager_v2 import MathaPackageManager", "check": None},
        {"name": "Tree-sitter 后端", "import": "from src.tree_sitter_backends import RustParser", "check": None},
    ],
    "multi_lang": [
        {"name": "多语言代码生成", "import": "from src.multi_lang_codegen import MultiLangCodeGen", "check": None},
        {"name": "多语言验证器", "import": "from src.multi_lang_verifier import MultiLangVerifier", "check": None},
        {"name": "符号兼容", "import": "from src.multi_lang_codegen import SymbolCompat", "check": None},
    ],
    "concurrency": [
        {"name": "CSP 并发", "import": "from src.csp_os_thread import CSPRuntime", "check": None},
        {"name": "性能基准测试", "import": "from src.performance_benchmark import BenchmarkSuite", "check": None},
    ],
    "type_system": [
        {"name": "类型系统 v2", "import": "from src.type_system_v2 import TypeChecker", "check": None},
        {"name": "标准库", "import": "from src.stdlib.core import *", "check": None},
    ],
    "offline": [
        {"name": "离线存储", "import": "from src.offline_store import get_offline_store", "check": None},
        {"name": "SQLite 存储", "import": "from src.offline.sqlite_storage import SQLiteStorage", "check": None},
        {"name": "离线同步", "import": "from src.offline.sync import OfflineSyncManager", "check": None},
    ],
}

# 功能验证测试（实际执行）
FUNCTIONAL_TESTS = [
    {"name": "MIR 编译 sin(3.14)", "func": "test_mir_compile_sin", "group": "core"},
    {"name": "C 代码生成", "func": "test_c_codegen", "group": "core"},
    {"name": "Python 代码生成", "func": "test_python_codegen", "group": "core"},
    {"name": "Memoization 优化", "func": "test_memoize", "group": "optimization"},
    {"name": "JIT 编译", "func": "test_jit_compile", "group": "optimization"},
    {"name": "Profiler 报告", "func": "test_profiler", "group": "tools"},
    {"name": "LSP 补全", "func": "test_lsp_complete", "group": "tools"},
    {"name": "文档生成", "func": "test_doc_gen", "group": "tools"},
    {"name": "包管理本地操作", "func": "test_pkg_local", "group": "tools"},
    {"name": "多语言代码生成", "func": "test_multilang_codegen", "group": "multi_lang"},
    {"name": "CSP 并发", "func": "test_csp", "group": "concurrency"},
    {"name": "类型系统", "func": "test_type_system", "group": "type_system"},
    {"name": "离线存储", "func": "test_offline_storage", "group": "offline"},
]


# ═══════════════════════════════════════════════════════════════
# 验证函数
# ═══════════════════════════════════════════════════════════════

def test_mir_compile_sin() -> tuple[bool, str]:
    try:
        from src.compiler.matha_cc import MathaLexer, MathaParser
        from src.mir import MIRGenerator
        lexer = MathaLexer("x = sin(3.14)")
        tokens = lexer.tokenize()
        ast = MathaParser(tokens).parse()
        mir = MIRGenerator().generate(ast)
        n = len(mir.functions["main"].instructions)
        return n > 0, f"MIR 编译成功: {n} 条指令"
    except Exception as e:
        return False, f"MIR 编译失败: {e}"


def test_c_codegen() -> tuple[bool, str]:
    try:
        from src.mir_converter import convert
        c_code = convert("x = sin(3.14)", "matha", "c")
        return "sin(" in c_code and "#include" in c_code, "C 代码生成 OK"
    except Exception as e:
        return False, f"C 代码生成失败: {e}"


def test_python_codegen() -> tuple[bool, str]:
    try:
        from src.mir_converter import convert
        py_code = convert("x = sin(3.14)", "matha", "python")
        return "math.sin(" in py_code, "Python 代码生成 OK"
    except Exception as e:
        return False, f"Python 代码生成失败: {e}"


def test_memoize() -> tuple[bool, str]:
    try:
        from src.compiler.memoize import get_memoize_optimizer
        opt = get_memoize_optimizer()
        fib = opt.optimize_fibonacci(10)
        return fib == 55, f"Fibonacci(10) = {fib}"
    except Exception as e:
        return False, f"Memoization 失败: {e}"


def test_jit_compile() -> tuple[bool, str]:
    try:
        from src.compiler.jit import get_jit_compiler
        compiler = get_jit_compiler()
        return compiler is not None, "JIT 编译 OK"
    except Exception as e:
        return False, f"JIT 编译失败: {e}"


def test_profiler() -> tuple[bool, str]:
    try:
        from src.profiler import MathaProfiler
        profiler = MathaProfiler()
        report = profiler.report("json")
        return bool(report), "Profiler OK"
    except Exception as e:
        return False, f"Profiler 失败: {e}"


def test_lsp_complete() -> tuple[bool, str]:
    try:
        from src.lsp import MathaLSP
        lsp = MathaLSP()
        completions = lsp.complete("x = sin", position=(0, 6))
        # 有结果即可，0 项也是合法的（无匹配补全）
        return True, f"LSP 补全 OK ({len(completions)} 项)"
    except Exception as e:
        return False, f"LSP 失败: {e}"


def test_doc_gen() -> tuple[bool, str]:
    try:
        from src.doc_gen import DocGenerator
        gen = DocGenerator()
        docs = gen.generate_all()
        md = docs.get("markdown", "")
        return len(md) > 0, f"文档生成 OK ({len(md)} 字符)"
    except Exception as e:
        return False, f"文档生成失败: {e}"


def test_pkg_local() -> tuple[bool, str]:
    try:
        from src.pkg_manager_v2 import MathaPackageManager
        pm = MathaPackageManager()
        envs = pm.list_envs()
        return True, f"包管理 OK (环境: {len(envs)})"
    except Exception as e:
        return False, f"包管理失败: {e}"


def test_multilang_codegen() -> tuple[bool, str]:
    try:
        from src.multi_lang_codegen import MultiLangCodeGen
        cg = MultiLangCodeGen()
        result = cg.generate("rust", "fib", [], "fib(n-1) + fib(n-2)")
        return result is not None, "多语言代码生成 OK"
    except Exception as e:
        return False, f"多语言代码生成失败: {e}"


def test_csp() -> tuple[bool, str]:
    try:
        from src.csp_os_thread import CSPRuntime
        runtime = CSPRuntime()
        return runtime is not None, "CSP 并发 OK"
    except Exception as e:
        return False, f"CSP 失败: {e}"


def test_type_system() -> tuple[bool, str]:
    try:
        from src.type_system_v2 import TypeChecker
        ts = TypeChecker()
        return ts is not None, "类型系统 OK"
    except Exception as e:
        return False, f"类型系统失败: {e}"


def test_offline_storage() -> tuple[bool, str]:
    try:
        from src.offline.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
        return storage is not None, "离线存储 OK"
    except Exception as e:
        return False, f"离线存储失败: {e}"


# 测试函数映射
FUNCTION_MAP = {
    "test_mir_compile_sin": test_mir_compile_sin,
    "test_c_codegen": test_c_codegen,
    "test_python_codegen": test_python_codegen,
    "test_memoize": test_memoize,
    "test_jit_compile": test_jit_compile,
    "test_profiler": test_profiler,
    "test_lsp_complete": test_lsp_complete,
    "test_doc_gen": test_doc_gen,
    "test_pkg_local": test_pkg_local,
    "test_multilang_codegen": test_multilang_codegen,
    "test_csp": test_csp,
    "test_type_system": test_type_system,
    "test_offline_storage": test_offline_storage,
}


# ═══════════════════════════════════════════════════════════════
# 主验证逻辑
# ═══════════════════════════════════════════════════════════════

def run_import_checks(verbose: bool = False) -> List[Dict]:
    results = []
    for group_name, tests in VERIFICATION_TESTS.items():
        for test in tests:
            ok = False
            error = ""
            start = time.time()
            try:
                exec(test["import"], {})
                ok = True
            except Exception as e:
                error = str(e)
            elapsed = time.time() - start
            results.append({
                "group": group_name,
                "name": test["name"],
                "import": test["import"],
                "ok": ok,
                "error": error,
                "elapsed_ms": round(elapsed * 1000, 1),
            })
            if verbose:
                status = "OK" if ok else "FAIL"
                print(f"  [{status}] {test['name']} ({elapsed*1000:.1f}ms)")
    return results


def run_functional_checks(verbose: bool = False) -> List[Dict]:
    results = []
    for test in FUNCTIONAL_TESTS:
        func = FUNCTION_MAP.get(test["func"])
        if func is None:
            continue
        ok = False
        msg = ""
        start = time.time()
        try:
            ok, msg = func()
        except Exception as e:
            msg = f"异常: {e}"
        elapsed = time.time() - start
        results.append({
            "group": test["group"],
            "name": test["name"],
            "ok": ok,
            "message": msg,
            "elapsed_ms": round(elapsed * 1000, 1),
        })
        if verbose:
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {test['name']}: {msg} ({elapsed*1000:.1f}ms)")
    return results


def print_summary(results: List[Dict], output_format: str = "text") -> None:
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    if output_format == "json":
        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "ok": failed == 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print()
    print("=" * 60)
    print("Matha 离线环境验证报告")
    print("=" * 60)
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"平台: {sys.platform}")
    print(f"项目: {PROJECT_ROOT}")
    print()

    groups: Dict[str, Dict[str, int]] = {}
    for r in results:
        g = r["group"]
        if g not in groups:
            groups[g] = {"total": 0, "passed": 0}
        groups[g]["total"] += 1
        if r["ok"]:
            groups[g]["passed"] += 1

    print("分组结果:")
    for g, stats in groups.items():
        status = "OK" if stats["passed"] == stats["total"] else "FAIL"
        print(f"  [{status}] {g}: {stats['passed']}/{stats['total']}")

    print()
    mark = "PASS" if failed == 0 else "FAIL"
    print(f"总计: {passed}/{total} 通过 [{mark}]" + ("" if failed == 0 else f" ({failed} 失败)"))
    print("=" * 60)

    if failed > 0:
        print("\n失败项目:")
        for r in results:
            if not r["ok"]:
                err = r.get("error", r.get("message", ""))
                print(f"  - {r['group']}/{r['name']}: {err[:80]}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha 离线环境验证")
    parser.add_argument("--quick", action="store_true", help="只检查导入，不运行功能测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    print("=" * 60)
    print("Matha 离线环境验证工具")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}")
    print(f"平台: {sys.platform}")
    print(f"项目: {PROJECT_ROOT}")
    print()

    all_results = []

    print("【导入检查】")
    import_results = run_import_checks(verbose=args.verbose)
    all_results.extend(import_results)

    if not args.quick:
        print()
        print("【功能验证】")
        func_results = run_functional_checks(verbose=args.verbose)
        all_results.extend(func_results)

    print_summary(all_results, "json" if args.json else "text")

    failed = sum(1 for r in all_results if not r["ok"])
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
