# -*- coding: utf-8 -*-
"""
Matha 统一命令行工具 — REPL + 编译器 + 调试 一体化
用法:
  matha                          # 启动交互式 REPL
  matha eval "sin(3.14)"         # 计算表达式
  matha run demo.matha           # 运行 Matha 源文件
  matha compile demo.matha -o c  # 编译到 C
  matha llvm demo.matha          # 生成 LLVM IR
  matha optimize demo.matha      # 优化编译
  matha test                     # 运行编译器测试
  matha info                     # 工具链信息
  matha debug demo.matha         # 调试模式
  matha --version                # 显示版本
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# 确保项目根目录在 PATH 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VERSION = "4.4"


# ============================================================
# REPL 模式
# ============================================================

def _cmd_repl(args) -> int:
    """启动交互式 REPL。"""
    from src.repl import MathaREPL
    repl = MathaREPL(debug=getattr(args, 'debug', False))
    repl.run()
    return 0


# ============================================================
# eval 模式 — 表达式计算
# ============================================================

def _cmd_eval(args) -> int:
    """计算单行表达式。"""
    from src.interp import interpret
    try:
        # 将表达式包装为完整 Matha 程序
        wrapped = f"result = {args.expr}\n#1：[result]"
        out, trace = interpret(wrapped)
        for item in out:
            print(item)
        return 0
    except Exception as e:
        print(f"计算失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# run 模式 — 运行 Matha 文件
# ============================================================

def _cmd_run(args) -> int:
    """运行 .matha 文件（解释模式）。"""
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
        from src.interp import interpret
        out, trace = interpret(source)
        for item in out:
            print(item)
        return 0
    except FileNotFoundError:
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"运行失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# compile 模式 — 编译到目标语言
# ============================================================

def _cmd_compile(args) -> int:
    """编译 Matha 源码。"""
    try:
        from src.compiler.matha_cc import matha_compile
        start = time.perf_counter()
        output = matha_compile(args.source, args.output, optimize=not getattr(args, 'no_opt', False))
        elapsed = (time.perf_counter() - start) * 1000
        print(f"编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"编译失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# llvm 模式 — 生成 LLVM IR
# ============================================================

def _cmd_llvm(args) -> int:
    """生成 LLVM IR。"""
    try:
        from src.compiler.matha_cc import matha_to_llvm
        llvm_ir = matha_to_llvm(args.source)
        if getattr(args, 'output', None):
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(llvm_ir)
            print(f"LLVM IR 已保存: {args.output}")
        else:
            print(llvm_ir)
        return 0
    except Exception as e:
        print(f"LLVM 生成失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# optimize 模式 — 优化编译
# ============================================================

def _cmd_optimize(args) -> int:
    """优化编译。"""
    try:
        from src.compiler.matha_cc import matha_compile
        start = time.perf_counter()
        output = matha_compile(args.source, args.output, optimize=True)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"优化编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"优化编译失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# test 模式 — 运行测试
# ============================================================

def _cmd_test(args) -> int:
    """运行解释器测试。"""
    from src.interp import interpret
    tests = [
        ("简单算术", "result = 1 + 2 * 3\n#1：[result]"),
        ("函数定义", "add = (a, b) => a + b\nresult = add(10)(20)\n#1：[result]"),
        ("递归阶乘", "func 阶乘(n) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#1：{[阶乘(6)]}"),
        ("三角函数", "result = sin(3.14159) + cos(1.57)\n#1：[result]"),
        ("条件表达式", "r = 5 > 3 ? 真 : 假\n#1：[r]"),
    ]
    print("运行解释器测试...")
    passed, failed = 0, 0
    for name, source in tests:
        try:
            out, trace = interpret(source)
            print(f"  PASS {name}: output={out}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 0 if failed == 0 else 1


# ============================================================
# info 模式 — 工具链信息
# ============================================================

def _cmd_info(args) -> int:
    """显示工具链信息。"""
    print("=" * 60)
    print("Matha v{} 统一工具链".format(VERSION))
    print("=" * 60)
    print(f"版本:     {VERSION}")
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


# ============================================================
# debug 模式 — 调试 Matha 程序
# ============================================================

def _cmd_debug(args) -> int:
    """调试模式：显示 AST + MIR + 代码生成。"""
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
        from src.compiler.matha_cc import MathaLexer, MathaParser, MathaFrontend
        from src.mir import MIRGenerator
        from src.mir_codegen import MIRToCGenerator, MIRToPythonGenerator

        # Step 1: 词法分析
        print("=" * 50)
        print("Step 1: 词法分析")
        print("=" * 50)
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        print(f"Token 数量: {len(tokens)}")
        for tok in tokens[:30]:
            print(f"  {tok.type.name:15s} {tok.value!r}")
        if len(tokens) > 30:
            print(f"  ... 还有 {len(tokens) - 30} 个 token")

        # Step 2: 语法分析
        print()
        print("=" * 50)
        print("Step 2: 语法分析 (AST)")
        print("=" * 50)
        parser = MathaParser(tokens)
        ast = parser.parse()
        print(f"AST 声明数量: {len(ast.decls)}")
        for decl in ast.decls[:5]:
            print(f"  {type(decl).__name__}")

        # Step 3: MIR
        print()
        print("=" * 50)
        print("Step 3: MIR 生成")
        print("=" * 50)
        mir_gen = MIRGenerator()
        mir_program = mir_gen.generate(ast)
        print(f"MIR 指令数量: {len(mir_program)}")
        for instr in mir_program[:10]:
            print(f"  {instr}")

        # Step 4: 代码生成
        print()
        print("=" * 50)
        print("Step 4: 代码生成 (Python)")
        print("=" * 50)
        py_gen = MIRToPythonGenerator()
        py_code = py_gen.generate(mir_program)
        print(py_code[:500])
        print("...")

        return 0
    except FileNotFoundError:
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"调试失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# build 模式 — 构建独立可执行文件
# ============================================================

def _cmd_build(args) -> int:
    """构建独立可执行文件。"""
    try:
        from src.compiler.matha_cc import matha_compile
        output = matha_compile(args.source, args.output, optimize=True)
        print(f"构建成功: {args.source} → {args.output}")
        return 0
    except Exception as e:
        print(f"构建失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# 主入口
# ============================================================

def main(argv=None) -> int:
    """统一 CLI 入口。"""
    parser = argparse.ArgumentParser(
        prog="matha",
        description="Matha 数学编程语言 — 解释器 + 编译器 + 调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令:
  matha                    启动交互式 REPL
  matha eval "expr"        计算表达式
  matha run file.matha     运行 Matha 源文件
  matha compile file -o c  编译到 C
  matha llvm file          生成 LLVM IR
  matha optimize file -o c 优化编译
  matha test               运行编译器测试
  matha info               工具链信息
  matha debug file         调试模式（显示 AST/MIR）
  matha build file -o exe  构建独立可执行文件

示例:
  matha
  matha eval "sin(3.14) + cos(1.57)"
  matha run demo.matha
  matha compile demo.matha -o output.c
  matha --version
        """,
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--version", action="version", version=f"Matha v{VERSION}")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # REPL（无命令）
    sub.add_parser("repl", help="启动交互式 REPL")

    # eval
    p_eval = sub.add_parser("eval", help="计算单行表达式")
    p_eval.add_argument("expr", help="Matha 表达式")
    p_eval.set_defaults(func=_cmd_eval)

    # run
    p_run = sub.add_parser("run", help="运行 Matha 源文件")
    p_run.add_argument("file", help=".matha 源文件路径")
    p_run.set_defaults(func=_cmd_run)

    # compile
    p_compile = sub.add_parser("compile", help="编译 Matha 源码")
    p_compile.add_argument("source", help="输入 .matha 文件")
    p_compile.add_argument("-o", "--output", default="out", help="输出文件名")
    p_compile.add_argument("--no-opt", action="store_true", help="禁用优化")
    p_compile.set_defaults(func=_cmd_compile)

    # llvm
    p_llvm = sub.add_parser("llvm", help="生成 LLVM IR")
    p_llvm.add_argument("source", help="输入 .matha 文件")
    p_llvm.add_argument("-o", "--output", help="输出 .ll 文件")
    p_llvm.set_defaults(func=_cmd_llvm)

    # optimize
    p_opt = sub.add_parser("optimize", help="优化编译")
    p_opt.add_argument("source", help="输入 .matha 文件")
    p_opt.add_argument("-o", "--output", default="out", help="输出文件名")
    p_opt.set_defaults(func=_cmd_optimize)

    # test
    sub.add_parser("test", help="运行编译器测试").set_defaults(func=_cmd_test)

    # info
    sub.add_parser("info", help="工具链信息").set_defaults(func=_cmd_info)

    # debug
    p_debug = sub.add_parser("debug", help="调试模式（显示 AST/MIR）")
    p_debug.add_argument("file", help=".matha 源文件路径")
    p_debug.set_defaults(func=_cmd_debug)

    # build
    p_build = sub.add_parser("build", help="构建独立可执行文件")
    p_build.add_argument("source", help="输入 .matha 文件")
    p_build.add_argument("-o", "--output", default="out", help="输出文件名")
    p_build.set_defaults(func=_cmd_build)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    else:
        # 无子命令 → REPL
        return _cmd_repl(args)


if __name__ == "__main__":
    sys.exit(main())
