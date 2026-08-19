#!/usr/bin/env python3
"""Matha 性能基准测试脚本。

用法:
    python scripts/benchmark_performance.py [--runs N]
"""
from __future__ import annotations
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================
# 测试数据
# ============================================================

LONG_IDENTIFIER = "这是一个非常长的中文标识符用于测试词法分析器性能" * 50

COMPLEX_EXPR = """
func 斐波那契(n: Int) -> Int = (n) =>
  n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)

func 阶乘(n: Int) -> Int = (n) =>
  n <= 1 ? 1 : n * 阶乘(n-1)

let result = 斐波那契(20)
output result
"""

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
        tokens = list(lexer.tokenize())
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {"组件": "Lexer", "输入": f"长标识符 ({len(LONG_IDENTIFIER)} 字符)", "times": times, "结果数": len(tokens)}


def bench_parser(run_count: int) -> dict:
    from src.parser import parse
    times = []
    for _ in range(run_count):
        t0 = time.perf_counter()
        ast = parse(COMPLEX_EXPR)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    stmts = getattr(ast, 'stmts', []) or getattr(ast, 'decls', [])
    return {"组件": "Parser", "输入": f"递归函数源码 ({len(COMPLEX_EXPR)} 字符)", "times": times, "结果数": len(stmts)}


def bench_interpreter(run_count: int) -> dict:
    from src.interp import interpret
    times = []
    for _ in range(run_count):
        t0 = time.perf_counter()
        outputs, _ = interpret(COMPLEX_EXPR)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {"组件": "Interpreter", "输入": "fib(20) + 阶乘", "times": times, "结果数": len(outputs)}


def bench_codegen(run_count: int) -> dict:
    from src.parser import parse
    from src.mir import MIRGenerator
    times = []
    for _ in range(run_count):
        ast = parse(MIR_CODE)
        t0 = time.perf_counter()
        gen = MIRGenerator()
        mir = gen.generate(ast)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    funcs = list(getattr(mir, 'functions', {}).keys()) if mir else []
    return {"组件": "Codegen (MIR)", "输入": "测试函数编译", "times": times, "结果数": len(funcs)}


# ============================================================
# 报告
# ============================================================

def fmt_time(s: float) -> str:
    if s < 1e-6: return f"{s*1e9:.0f} ns"
    if s < 1e-3: return f"{s*1e6:.1f} µs"
    if s < 1:    return f"{s*1e3:.2f} ms"
    return f"{s:.3f} s"


def report(results):
    print("\n" + "=" * 72)
    print("  Matha 性能基准测试报告")
    print("=" * 72)
    print(f"\n  {'组件':<20} {'输入':<28} {'mean':>10} {'median':>10} {'min':>10} {'max':>10}  结果")
    print("-" * 72)
    for r in results:
        t = r["times"]
        print(f"  {r['组件']:<20} {r['输入']:<28} "
              f"{fmt_time(statistics.mean(t)):>10} {fmt_time(statistics.median(t)):>10} "
              f"{fmt_time(min(t)):>10} {fmt_time(max(t)):>10}  {r['结果数']}")
    print("=" * 72)
    all_t = [x for r in results for x in r["times"]]
    print(f"\n  总计: {len(all_t)} 次运行, 总耗时 {fmt_time(sum(all_t))}, 平均 {fmt_time(statistics.mean(all_t))}\n")


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"Matha 性能基准测试 (runs={runs})")
    results = []
    for fn in [bench_lexer, bench_parser, bench_interpreter, bench_codegen]:
        r = fn(runs)
        results.append(r)
        t0 = r["times"][0]
        print(f"  ✓ {r['组件']}: {fmt_time(t0)}")
    report(results)


if __name__ == "__main__":
    main()
