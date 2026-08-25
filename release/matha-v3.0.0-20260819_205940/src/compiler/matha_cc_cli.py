# -*- coding: utf-8 -*-
"""Matha LLVM 工具链 - matha-cc 编译器前端。

命令行接口：
  matha-cc compile input.matha -o output       # 编译为可执行文件
  matha-cc run input.matha [args...]            # 编译并运行
  matha-cc llvm input.matha -o output.ll       # 仅生成 LLVM IR
  matha-cc optimize input.matha -O2            # 编译并优化
  matha-cc info                                # 显示工具链信息
"""

from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time


def cmd_compile(args) -> int:
    """编译命令。"""
    from src.compiler.matha_cc import matha_compile
    start = time.perf_counter()
    try:
        output = matha_compile(args.source, args.output, optimize=not args.no_opt)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"编译失败: {e}", file=sys.stderr)
        return 1


def cmd_run(args) -> int:
    """运行命令。"""
    from src.compiler.matha_cc import matha_run
    start = time.perf_counter()
    try:
        result = matha_run(args.source, args.args)
        elapsed = (time.perf_counter() - start) * 1000
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"\n耗时: {elapsed:.0f}ms, 退出码: {result.returncode}")
        return result.returncode
    except Exception as e:
        print(f"运行失败: {e}", file=sys.stderr)
        return 1


def cmd_llvm(args) -> int:
    """生成 LLVM IR 命令。"""
    from src.compiler.matha_cc import matha_to_llvm
    try:
        llvm_ir = matha_to_llvm(args.source)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(llvm_ir)
            print(f"LLVM IR 已保存: {args.output}")
        else:
            print(llvm_ir)
        return 0
    except Exception as e:
        print(f"LLVM 生成失败: {e}", file=sys.stderr)
        return 1


def cmd_optimize(args) -> int:
    """优化编译命令。"""
    from src.compiler.matha_cc import matha_compile
    start = time.perf_counter()
    try:
        output = matha_compile(args.source, args.output, optimize=True)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"优化编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"优化编译失败: {e}", file=sys.stderr)
        return 1


def cmd_info(args) -> int:
    """显示工具链信息。"""
    print("=" * 60)
    print("Matha LLVM 工具链 (matha-cc)")
    print("=" * 60)
    print(f"版本:     1.0.0")
    print(f"前端:     MathaLexer → MathaParser → MathaFrontend")
    print(f"IR:       MathaIR (三地址码)")
    print(f"后端:     MathaLLVMGenerator → LLVM IR")
    print(f"代码生成: llc/clang → 原生机器码")
    print()
    print("支持的优化 Pass:")
    print("  • MathaConstFoldPass  - 常量折叠")
    print("  • MathaTailRecPass    - 尾递归消除")
    print("  • MathaLoopUnrollPass - 循环展开")
    print("  • MathaSIMDPass       - 自动向量化")
    print("  • MathaCurryFlatten   - 柯里化扁平化")
    print()
    print("LLVM 工具链状态:")
    for tool in ["llc", "clang", "opt", "llvm-as"]:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            version = result.stdout.decode().split("\n")[0] if result.returncode == 0 else "未找到"
        except FileNotFoundError:
            version = "未安装"
        print(f"  {tool:8s}: {version}")
    print("=" * 60)
    return 0


def cmd_test(args) -> int:
    """运行编译器测试。"""
    from src.compiler.matha_cc import MathaCompiler
    compiler = MathaCompiler(optimize=True)

    tests = [
        ("简单算术", "result = 1 + 2 * 3\n#1：[result]"),
        ("函数定义", "add = (a, b) => a + b\nresult = add(10)(20)\n#1：[result]"),
        ("递归阶乘", "fact = (n) => if n <= 1 then 1 else n * fact(n-1)\nresult = fact(5)\n#1：[result]"),
        ("三角函数", "result = sin(3.14159) + cos(1.57)\n#1：[result]"),
    ]

    print("运行编译器测试...")
    passed, failed = 0, 0
    for name, source in tests:
        try:
            result = compiler.run(source)
            if result.returncode == 0:
                print(f"  PASS {name}: stdout={result.stdout.strip()[:50]}")
                passed += 1
            else:
                print(f"  FAIL {name}: exit={result.returncode}, stderr={result.stderr.strip()[:50]}")
                failed += 1
        except Exception as e:
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        prog="matha-cc",
        description="Matha LLVM 编译器工具链",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # compile
    p_compile = subparsers.add_parser("compile", help="编译 Matha 源码")
    p_compile.add_argument("source", help="输入 .matha 文件")
    p_compile.add_argument("-o", "--output", default="out", help="输出文件名")
    p_compile.add_argument("--no-opt", action="store_true", help="禁用优化")
    p_compile.set_defaults(func=cmd_compile)

    # run
    p_run = subparsers.add_parser("run", help="编译并运行")
    p_run.add_argument("source", help="输入 .matha 文件")
    p_run.add_argument("args", nargs="*", help="运行时参数")
    p_run.set_defaults(func=cmd_run)

    # llvm
    p_llvm = subparsers.add_parser("llvm", help="生成 LLVM IR")
    p_llvm.add_argument("source", help="输入 .matha 文件")
    p_llvm.add_argument("-o", "--output", help="输出 .ll 文件")
    p_llvm.set_defaults(func=cmd_llvm)

    # optimize
    p_opt = subparsers.add_parser("optimize", help="优化编译")
    p_opt.add_argument("source", help="输入 .matha 文件")
    p_opt.add_argument("-o", "--output", default="out", help="输出文件名")
    p_opt.set_defaults(func=cmd_optimize)

    # info
    p_info = subparsers.add_parser("info", help="显示工具链信息")
    p_info.set_defaults(func=cmd_info)

    # test
    p_test = subparsers.add_parser("test", help="运行编译器测试")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
