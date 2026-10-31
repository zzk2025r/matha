"""基准：用户函数深递归的调用开销（count(N)）。

对比两种调用环境策略：
  - copy : 每次调用 `dict(captured)` 全量拷贝 + 重建 matha_env 列表（O(n)/call → O(n²)）
  - ref  : 引用传递 + 作用域快照（overlay 链式查找 + 赋值隔离，O(1) 指针）

运行：python -m tests.bench_call_env
或：  MATHA_FEATURE_STACK_ENGINE=1 python tests/bench_call_env.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features
from src.parser import parse
from src.interp import Interpreter


def _src(n):
    return (
        "func count(n: Int) -> Int = (n) =>\n"
        "  if n <= 0 then 0\n"
        "  else count(n - 1)\n"
        f"输出(count({n}))\n"
    )


def run_case(n, engine=True, repeat=3):
    features.clear_feature()
    if engine:
        features.set_feature("STACK_ENGINE", True)
    # 只测引擎路径（引用传递只在引擎里生效）
    times = []
    try:
        for _ in range(repeat):
            t = time.perf_counter()
            out = Interpreter().run(parse(_src(n)))[0]
            times.append(time.perf_counter() - t)
            assert out == [0], out
    finally:
        features.clear_feature()
    return min(times)


def main():
    print("=" * 60)
    print("Benchmark: count(N) 深递归调用环境开销")
    print("=" * 60)
    sizes = [1000, 2000, 4000, 8000]
    print(f"{'N':>7} {'time(s)':>12} {'us/call':>10}")
    prev = None
    for n in sizes:
        dt = run_case(n, engine=True)
        per = dt / n * 1e6
        ratio = "" if prev is None else f"  (x{dt/prev:.2f} vs prev N)"
        print(f"{n:>7} {dt:>12.4f} {per:>10.2f}{ratio}")
        prev = dt
    print()
    print("若「us/call」基本恒定 → O(n) 总开销；若随 N 线性增长 → O(n²)。")


if __name__ == "__main__":
    main()
