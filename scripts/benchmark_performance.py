#!/usr/bin/env python3
"""Matha 性能基准测试：对比优化前后各核心组件执行时间。

用法:
    python scripts/benchmark_performance.py [--runs 5]

输出:
    每个组件的 mean / median / min / max 耗时
"""
from __future__ import annotations
import os
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================
# 测试数据
# ============================================================

LONG_IDENTIFIER = "这是一个非常长的中文标识符用于测试词法分析器性能" * 50
MEDIUM_CODE = """
func 斐波那契(n: Int) -> Int = (n) =>
  n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)

func 阶乘(n: Int) -> Int = (n) =>
  n <= 1 ? 1 : n * 阶乘(n-1)

let result = 斐波那契(20)
output result
"""

COMPLEX_EXPR = "let a = 1 + 2 * 3 - 4 / 2 ^ 3 + (5 - 3) * (7 + 1)" * 100

MIR_CODE = """
func 测试(x: Float, y: Float) -> Float = (x, y) =>
  let a = x + y
  let b = x * y
  let c = a - b
  c * 2.0
output 测试(3.14, 2.71)
"""

# ============================================================
# 组件基准
# ============================================================

def bench_lexer(run_count: int) -> dict:
    from src.lexer import Lexer
    times = []
    for _ in range(run_count):
        t0 = time.perf_counter()
        lexer = Lexer(LONG_IDENTIFIER)
        tokens = lexer.tokenize()
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "组件": "Lexer",
        "输入": f"长标识符 ({len(LONG_IDENTIFIER)} 字符)",
        "times": times,
        "结果数": len(tokens),
    }


def bench_parser(run_count: int) -> dict:
    from src.lexer import Lexer
    from src.parser import Parser
    times = []
    for _ in range(run_count):
        lexer = Lexer(COMPLEX_EXPR)
        tokens = lexer.tokenize()
        t0 = time.perf_counter()
        parser = Parser(tokens)
        ast = parser.parse()
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "组件": "Parser",
        "输入": f"复杂表达式 ({len(COMPLEX_EXPR)} 字符)",
        "times": times,
        "结果数": len(ast) if ast else 0,
    }


def bench_interpreter(run_count: int) -> dict:
    from src.interp import Interpreter
    times = []
    for _ in range(run_count):
        interp = Interpreter()
        t0 = time.perf_counter()
        interp.exec(MEDIUM_CODE)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "组件": "Interpreter",
        "输入": f"递归函数 (fib(20), 阶乘)",
        "times": times,
        "结果数": len(interp.outputs),
    }


def bench_codegen(run_count: int) -> dict:
    from src.compiler.matha_cc import MathaParser
    from src.mir import MIRGenerator
    from src.codegen.c import CCodeGenerator

    times = []
    for _ in range(run_count):
        parser = MathaParser(MIR_CODE)
        ast = parser.parse()

        t0 = time.perf_counter()
        gen = MIRGenerator()
        mir = gen.compile(ast)
        c_code = CCodeGenerator().generate(mir)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "组件": "Codegen (MIR→C)",
        "输入": f"函数编译 (测试函数)",
        "times": times,
        "结果数": len(c_code) if c_code else 0,
    }


# ============================================================
# 报告生成
# ============================================================

def format_time(ns: float) -> str:
    if ns < 1e-6:
        return f"{ns * 1e9:.1f} ns"
    elif ns < 1e-3:
        return f"{ns * 1e6:.1f} µs"
    elif ns < 1:
        return f"{ns * 1e3:.1f} ms"
    else:
        return f"{ns:.3f} s"


def print_report(results: list[dict]) -> None:
    print("=" * 72)
    print("  Matha 性能基准测试报告")
    print("=" * 72)
    print()
    print(f"  {'组件':<20} {'输入':<30} {'mean':>10} {'median':>10} {'min':>10} {'max':>10} {'结果'}")
    print("-" * 72)
    for r in results:
        t = r["times"]
        mean_t = statistics.mean(t)
        median_t = statistics.median(t)
        min_t = min(t)
        max_t = max(t)
        print(
            f"  {r['组件']:<20} {r['输入']:<30} "
            f"{format_time(mean_t):>10} {format_time(median_t):>10} "
            f"{format_time(min_t):>10} {format_time(max_t):>10} "
            f"({r['结果数']})"
        )
    print("=" * 72)
    print()

    # 总体统计
    all_times = []
    for r in results:
        all_times.extend(r["times"])
    print(f"  总运行次数: {len(all_times)}")
    print(f"  总耗时:     {format_time(sum(all_times))}")
    print(f"  平均单次:   {format_time(statistics.mean(all_times))}")
    print()


# ============================================================
# 主入口
# ============================================================

def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"Matha 性能基准测试 (runs={runs})")
    print()

    results = []
    for bench_fn in [bench_lexer, bench_parser, bench_interpreter, bench_codegen]:
        r = bench_fn(runs)
        results.append(r)
        # 首次运行预热
        if r["times"]:
            print(f"  ✓ {r['组件']}: {format_time(r['times'][0])}")

    print()
    print_report(results)


if __name__ == "__main__":
    main()
