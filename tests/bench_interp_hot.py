# -*- coding: utf-8 -*-
"""基准：解释器热循环的开销（内联缓存 / 特化解释器前后对比）。

覆盖四类典型负载：

- **算术热循环**：`while` 循环里反复做整数比较与加减——每次迭代都会触发
  「按运算符字符串逐条 if/elif 匹配 + isinstance 类型检查」；
- **字符串热循环**：字符串拼接（通用路径每次都要做多次 isinstance 检查）；
- **多态调用点**：同一调用点交替看到 int / str——内联缓存必须退化为单态
  重新学习，用来观察缓存**不命中时**的额外开销；
- **递归热函数**：每次调用都有函数应用开销。

四组负载都在 ``INLINE_CACHE`` 开启/关闭下各跑若干次，取最小值（抗抖动），
并断言两种模式的结果**完全一致**（语义等价的硬约束）。

运行：python tests/bench_interp_hot.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features
from src.parser import parse
from src.interp import Interpreter

# 经典解释器按宿主 Python 递归执行用户函数，深递归需要更高的宿主递归上限
# （CPython 3.12+ 的纯 Python 调用不消耗 C 栈，调高上限是安全的）。
sys.setrecursionlimit(200000)


def _loop_src(n):
    return (
        "let i = 0\n"
        "let s = 0\n"
        "while i < " + str(n) + " {\n"
        "  s = s + i\n"
        "  i = i + 1\n"
        "}\n"
        "输出(s)\n"
    )


def _str_src(n):
    return (
        "let i = 0\n"
        "let s = \"\"\n"
        "while i < " + str(n) + " {\n"
        "  s = s + \"x\"\n"
        "  i = i + 1\n"
        "}\n"
        "输出(len(s))\n"
    )


def _poly_src(n):
    # pick 的返回值在 int / str 之间摆动 → 站点 `v + 1` 形状不断变化
    return (
        "let i = 0\n"
        "let cnt = 0\n"
        "while i < " + str(n) + " {\n"
        "  let v = if i % 2 == 0 then i else \"x\"\n"
        "  let w = v + 1\n"
        "  cnt = cnt + 1\n"
        "  i = i + 1\n"
        "}\n"
        "输出(cnt)\n"
    )


def _rec_src(n):
    return (
        "func count(n) -> Int = (n) =>\n"
        "  if n <= 0 then 0\n"
        "  else count(n - 1)\n"
        f"输出(count({n}))\n"
    )


def _run(src, ic, repeat=3):
    features.set_feature("INLINE_CACHE", bool(ic))
    times = []
    try:
        for _ in range(repeat):
            t = time.perf_counter()
            out = Interpreter().run(parse(src))[0]
            times.append(time.perf_counter() - t)
    finally:
        features.clear_feature("INLINE_CACHE")
    return min(times), out


def bench(name, src, unit):
    off_t, off_out = _run(src, False)
    on_t, on_out = _run(src, True)
    assert off_out == on_out, (name, off_out, on_out)
    speed = off_t / on_t if on_t else float("inf")
    print(f"{name:<12} 关闭 {off_t * 1e3:9.2f} ms | 开启 {on_t * 1e3:9.2f} ms | "
          f"加速 {speed:5.2f}x | {unit} {off_out}")
    return speed


def main():
    print("=" * 78)
    print("Benchmark: 解释器热路径（内联缓存 / 特化解释器）")
    print("=" * 78)
    print(f"{'负载':<12} {'INLINE_CACHE=0':<26} {'INLINE_CACHE=1':<26} {'结果':<10}")
    print("-" * 78)
    speeds = [
        bench("算术热循环", _loop_src(20000), "s ="),
        bench("字符串热循环", _str_src(20000), "len ="),
        bench("多态调用点", _poly_src(3000), "cnt ="),
        bench("递归热函数", _rec_src(3000), "count ="),
    ]
    print("-" * 78)
    print(f"平均加速 {sum(speeds) / len(speeds):.2f}x")


if __name__ == "__main__":
    main()
