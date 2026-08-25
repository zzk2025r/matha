# -*- coding: utf-8 -*-
"""Matha 各模块性能基准测试 + 瓶颈分析。"""
import time
import sys
sys.path.insert(0, '.')

SIMPLE_CODE = '''
func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)
result = 阶乘(10)
'''

RECURSIVE_CODE = '''
func 阶乘(n: Int) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)
func 斐波那契(n: Int) -> Int = (n) => n <= 1 ? n : 斐波那契(n-1) + 斐波那契(n-2)
result = 阶乘(10)
result = 斐波那契(15)
result = (1 > 2 ? 100 : 200)
result = (3 > 4 ? (5 > 6 ? 1 : 2) : 3)
'''

WARMUP = 3
ITERATIONS = 50

def benchmark(name, fn):
    for _ in range(WARMUP):
        fn()
    times = []
    for _ in range(ITERATIONS):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    avg_ms = sum(times) / len(times) * 1000
    print(f"  {name:25s}  avg={avg_ms:8.3f}ms")
    return avg_ms


def main():
    print("=" * 60)
    print("Matha 模块性能基准测试")
    print(f"预热: {WARMUP}, 迭代: {ITERATIONS}")
    print("=" * 60)

    from src.lexer import Lexer
    from src.parser import Parser
    from src.interp import Interpreter

    # 预热
    tokens = list(Lexer(SIMPLE_CODE).tokenize())
    ast = Parser(SIMPLE_CODE).parse()
    interp = Interpreter(debug=False)
    interp.run(ast)

    # ── 简单测试：阶乘(10) ──────────────────────────────────
    print("\n═══ 简单测试：阶乘(10) ═══════════════════════════════")

    print("\n[1/3] Lexer 词法分析")
    avg_lex = benchmark("Lexer", lambda: list(Lexer(SIMPLE_CODE).tokenize()))
    print(f"  token 数: {len(tokens)}, 单 token: {avg_lex/max(len(tokens),1)*1000:.4f} ms")

    print("\n[2/3] Parser 语法分析（含内部 Lexer）")
    avg_parse = benchmark("Parser", lambda: Parser(SIMPLE_CODE).parse())
    print(f"  顶层声明: {len(ast.decls)}")

    print("\n[3/3] Interpreter 解释执行")
    avg_no_log = benchmark("Interpreter(debug=False)", lambda: Interpreter(debug=False).run(ast))
    avg_with_log = benchmark("Interpreter(debug=True)", lambda: Interpreter(debug=True).run(ast))
    ratio = avg_with_log / avg_no_log if avg_no_log > 0 else 0
    print(f"  输出: {Interpreter(debug=False).run(ast)[0]}")
    print(f"  日志开销: {ratio:.1f}x")

    # ── 递归测试：阶乘(10) + 斐波那契(15) ─────────────────
    print("\n═══ 递归测试：阶乘(10) + 斐波那契(15) ═══════════════")
    tokens2 = list(Lexer(RECURSIVE_CODE).tokenize())
    ast2 = Parser(RECURSIVE_CODE).parse()

    print("\n[1/2] Lexer + Parser")
    avg_lex2 = benchmark("Lexer", lambda: list(Lexer(RECURSIVE_CODE).tokenize()))
    avg_parse2 = benchmark("Parser", lambda: Parser(RECURSIVE_CODE).parse())
    print(f"  token 数: {len(tokens2)}")

    print("\n[2/2] Interpreter（debug=False）")
    avg_interp = benchmark("Interpreter(debug=False)", lambda: Interpreter(debug=False).run(ast2))
    interp2 = Interpreter(debug=False)
    out, trace = interp2.run(ast2)
    print(f"  输出: {out}")
    print(f"  Trace 条数: {len(trace)}")

    # ── 汇总 ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("性能瓶颈分析（简单测试：阶乘 10）")
    print("=" * 60)
    print(f"  Lexer:     {avg_lex:8.3f}ms  ({avg_lex/avg_parse*100:5.1f}% of parser)")
    print(f"  Parser:    {avg_parse:8.3f}ms  (含内部 Lexer)")
    print(f"  Interpreter(无日志): {avg_no_log:8.3f}ms")
    print(f"  Interpreter(有日志): {avg_with_log:8.3f}ms  ← 日志开销 {avg_with_log-avg_no_log:.3f}ms ({ratio:.1f}x)")
    print("=" * 60)
    print("\n结论：")
    print(f"  1. Lexer 最快 ({avg_lex*1000:.2f}μs/token)，不是瓶颈")
    print(f"  2. Parser 适中 ({avg_parse:.3f}ms)，正常")
    print(f"  3. Interpreter 是主要瓶颈：")
    print(f"     - debug=False: {avg_no_log:.3f}ms（递归计算本身）")
    print(f"     - debug=True:  {avg_with_log:.3f}ms（{ratio:.1f}x 慢）")
    print(f"  4. 优化方向：")
    print(f"     - 默认 debug=False（已实现）")
    print(f"     - 减少 _log_enter/_log_exit 调用频率")
    print(f"     - 考虑 JIT 编译递归函数")
    print("=" * 60)


if __name__ == "__main__":
    main()
