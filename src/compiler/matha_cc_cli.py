"""Matha 编译器前端 - matha-cc 命令行接口。

命令行接口：
  matha-cc compile input.matha -o output       # 真编译（parse + mbc，计数摘要）
  matha-cc run input.matha [args...]            # 主解释器真实执行
  matha-cc llvm input.matha -o output.ll       # LLVM IR（未实现，显式拒绝）
  matha-cc optimize input.matha -O2            # 优化编译（同 compile）
  matha-cc info                                # 显示工具链信息
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def _harden_std_streams() -> None:
    """输出编码兜底：保留当前控制台/locale 的首选编码，只把不可编码字符降级为占位符。

    Windows 上 stdout 一旦不是控制台（管道、重定向，或 CI runner 捕获输出），
    Python 会退回 locale 首选编码；英文镜像下即 cp1252，本模块的中文 print 会直接抛
    `UnicodeEncodeError: 'charmap' codec can't encode characters`（实测见 GitHub Actions
    dispatch run 42208252282 的 `Test executables` 步骤）。`errors="replace"` 只改变
    不可编码字符的表现形式，不改动编码本身，因此 UTF-8 环境输出完全不受影响。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # 老版本 Python / 流已被替换 / 非标准 IO：静默跳过，不影响主流程


def cmd_compile(args) -> int:
    """编译命令。"""
    from src.compiler.matha_cc import matha_compile
    start = time.perf_counter()
    try:
        with open(args.source, encoding="utf-8") as f:
            source = f.read()
        output = matha_compile(source, args.output, optimize=not args.no_opt)
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
        with open(args.source, encoding="utf-8") as f:
            source = f.read()
        result = matha_run(source, args.args)
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
        with open(args.source, encoding="utf-8") as f:
            source = f.read()
        llvm_ir = matha_to_llvm(source)
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
        with open(args.source, encoding="utf-8") as f:
            source = f.read()
        output = matha_compile(source, args.output, optimize=True)
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
    print("Matha 编译器前端 (matha-cc)")
    print("=" * 60)
    print("版本:     1.0.0")
    print("前端:     MathaLexer → MathaParser（委托主实现 src.lexer / src.parser）")
    print("编译:     matha_compile → parse + mbc compile_program（真实计数摘要）")
    print("执行:     matha_run → 主解释器真实执行")
    print("LLVM IR:  未实现——matha_to_llvm 显式拒绝（历史上产出无效 IR 文本）")
    print("机器码主链: src.mbc.compiler → src.mbc.vm（原生为 src.mbc.native）")
    print()
    print("外部 LLVM 工具链（可选，经 src/plugins/toolchain_llvm）:")
    for tool in ["llc", "clang", "opt", "llvm-as"]:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, timeout=10)
            version = result.stdout.decode().split("\n")[0] if result.returncode == 0 else "未找到"
        except FileNotFoundError:
            version = "未安装"
        except subprocess.TimeoutExpired:
            # 慢/负载高的机器上探测超时不应让 info 崩掉（曾致 Test executables 偶发红）。
            version = "超时"
        print(f"  {tool:8s}: {version}")
    print("=" * 60)
    return 0


def cmd_test(args) -> int:
    """运行编译器测试。"""
    from src.compiler.matha_cc import MathaCompiler
    compiler = MathaCompiler(optimize=True)

    tests = [
        ("简单算术", "result = 1 + 2 * 3\n#1：[result]"),
        ("柯里化加法", "add = (a, b) => a + b\nresult = add(10)(20)\n#1：[result]"),
        ("递归阶乘", "func fact(n) -> Int = (n) => if n <= 1 then 1 else n * fact(n-1)\nresult = fact(5)\n#1：[result]"),
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
    _harden_std_streams()
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
