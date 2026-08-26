# -*- coding: utf-8 -*-
"""Matha 性能 Profiler — 火焰图 + 调用统计

解决 Matha 性能瓶颈可观测性不足的问题。

功能：
  1. 函数级调用计时
  2. 调用次数统计
  3. 火焰图数据生成（Chrome/Edge 格式）
  4. 性能报告生成（Markdown/JSON）
  5. 与 JIT/Memoization 集成

用法：
  from src.profiler import MathaProfiler, profile

  # 方式1: 装饰器
  @profile
  def fib(n):
      if n <= 1: return n
      return fib(n-1) + fib(n-2)

  # 方式2: 上下文管理器
  with MathaProfiler() as prof:
      result = fib(30)

  # 查看报告
  print(prof.report())
  prof.save_flamegraph("fib_flamegraph.html")
"""
from __future__ import annotations
import cProfile
import functools
import json
import pstats
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 调用统计
# ============================================================

@dataclass
class CallStats:
    """单次函数调用的统计。"""
    func_name: str
    file: str
    line: int
    call_count: int = 0
    total_time_ms: float = 0.0
    cumulative_time_ms: float = 0.0
    args_signature: str = ""
    children: Dict[str, 'CallStats'] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "func_name": self.func_name,
            "file": self.file,
            "line": self.line,
            "call_count": self.call_count,
            "total_time_ms": round(self.total_time_ms, 4),
            "cumulative_time_ms": round(self.cumulative_time_ms, 4),
            "args_signature": self.args_signature,
            "children": {k: v.to_dict() for k, v in self.children.items()},
        }


# ============================================================
# Profiler 核心
# ============================================================

class MathaProfiler:
    """
    Matha 性能分析器。

    提供：
      1. cProfile 集成（底层）
      2. 调用树统计
      3. 火焰图生成
      4. Markdown/JSON 报告
    """

    def __init__(self, sort_by: str = "cumulative", top_n: int = 50):
        self._sort_by = sort_by
        self._top_n = top_n
        self._profiler: Optional[cProfile.Profile] = None
        self._call_tree: Dict[str, CallStats] = {}
        self._start_time = 0.0
        self._end_time = 0.0
        self._active = False

    def __enter__(self) -> 'MathaProfiler':
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def start(self) -> None:
        """启动 profiling。"""
        self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._start_time = time.perf_counter()
        self._active = True

    def stop(self) -> None:
        """停止 profiling。"""
        if self._profiler and self._active:
            self._profiler.disable()
            self._end_time = time.perf_counter()
            self._active = False
            self._parse_stats()

    def _parse_stats(self) -> None:
        """解析 cProfile 统计结果。"""
        if not self._profiler:
            return

        stream = StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats(self._sort_by)

        # 提取调用统计
        self._call_tree = {}
        for (filename, line_no, func_name), (cc, nc, tt, ct, callers) in stats.stats.items():
            key = f"{func_name}@{filename}:{line_no}"
            self._call_tree[key] = CallStats(
                func_name=func_name,
                file=filename,
                line=line_no,
                call_count=nc,
                total_time_ms=tt * 1000,
                cumulative_time_ms=ct * 1000,
            )

    def report(self, format: str = "markdown") -> str:
        """生成性能报告。"""
        if not self._call_tree:
            return "# Matha 性能分析报告\n\n无 profiling 数据。\n"

        total_time = (self._end_time - self._start_time) * 1000

        if format == "markdown":
            return self._report_markdown(total_time)
        elif format == "json":
            return self._report_json(total_time)
        else:
            return self._report_markdown(total_time)

    def _report_markdown(self, total_time: float) -> str:
        """生成 Markdown 格式报告。"""
        lines = [
            "# Matha 性能分析报告",
            "",
            f"**总耗时**: {total_time:.2f} ms",
            f"**分析函数数**: {len(self._call_tree)}",
            f"**排序方式**: {self._sort_by}",
            "",
            "## Top 调用统计",
            "",
            "| 函数 | 调用次数 | 总耗时(ms) | 累计耗时(ms) | 占比 |",
            "|------|---------|-----------|-------------|------|",
        ]

        # 按累计耗时排序
        sorted_stats = sorted(
            self._call_tree.values(),
            key=lambda x: x.cumulative_time_ms,
            reverse=True
        )[:self._top_n]

        for stat in sorted_stats:
            pct = stat.cumulative_time_ms / max(total_time, 0.001) * 100
            lines.append(
                f"| {stat.func_name} | {stat.call_count} | "
                f"{stat.total_time_ms:.4f} | {stat.cumulative_time_ms:.4f} | {pct:.1f}% |"
            )

        lines.extend([
            "",
            "## 火焰图数据 (Chrome Tracing)",
            "",
            "查看 `profiler.save_flamegraph()` 生成的 HTML 文件。",
            "",
        ])

        return "\n".join(lines)

    def _report_json(self, total_time: float) -> str:
        """生成 JSON 格式报告。"""
        sorted_stats = sorted(
            self._call_tree.values(),
            key=lambda x: x.cumulative_time_ms,
            reverse=True
        )[:self._top_n]

        report = {
            "total_time_ms": round(total_time, 4),
            "function_count": len(self._call_tree),
            "sort_by": self._sort_by,
            "top_functions": [s.to_dict() for s in sorted_stats],
        }
        return json.dumps(report, ensure_ascii=False, indent=2)

    def save_flamegraph(self, filepath: str = "flamegraph.html") -> str:
        """
        生成 Chrome/Edge 兼容的火焰图 HTML 文件。

        Args:
            filepath: 输出文件路径

        Returns:
            生成的文件路径
        """
        sorted_stats = sorted(
            self._call_tree.values(),
            key=lambda x: x.cumulative_time_ms,
            reverse=True
        )[:self._top_n]

        total_time = (self._end_time - self._start_time) * 1000 if self._end_time > 0 else 1.0

        # 生成 Chrome Tracing 格式
        events = []
        for stat in sorted_stats:
            events.append({
                "name": stat.func_name,
                "ph": "X",
                "cat": "matha",
                "ts": stat.total_time_ms,
                "dur": stat.cumulative_time_ms,
                "args": {
                    "file": stat.file,
                    "line": stat.line,
                    "calls": stat.call_count,
                    "args": stat.args_signature,
                },
            })

        trace = {
            "traceEvents": events,
            "meta": {
                "total_time_ms": round(total_time, 4),
                "functions": len(sorted_stats),
                "sort_by": self._sort_by,
            }
        }

        trace_json = json.dumps(trace, ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Matha 性能火焰图</title>
  <style>
    body {{ font-family: sans-serif; padding: 20px; background: #1a1a2e; color: #eee; }}
    h1 {{ color: #00d4ff; }}
    .stats {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 10px 0; }}
    .stat-item {{ display: inline-block; margin-right: 30px; }}
    .stat-value {{ font-size: 24px; color: #00d4ff; font-weight: bold; }}
    .stat-label {{ font-size: 12px; color: #888; }}
    pre {{ background: #0f0f23; padding: 15px; border-radius: 8px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }}
    th {{ background: #16213e; color: #00d4ff; }}
    tr:hover {{ background: #16213e; }}
  </style>
</head>
<body>
  <h1>Matha 性能火焰图</h1>
  <div class="stats">
    <div class="stat-item">
      <div class="stat-value">{total_time:.2f}ms</div>
      <div class="stat-label">总耗时</div>
    </div>
    <div class="stat-item">
      <div class="stat-value">{len(sorted_stats)}</div>
      <div class="stat-label">分析函数</div>
    </div>
    <div class="stat-item">
      <div class="stat-value">{self._sort_by}</div>
      <div class="stat-label">排序方式</div>
    </div>
  </div>

  <h2>调用统计</h2>
  <table>
    <tr><th>函数</th><th>调用次数</th><th>总耗时(ms)</th><th>累计耗时(ms)</th><th>占比</th></tr>
"""

        for stat in sorted_stats:
            pct = stat.cumulative_time_ms / max(total_time, 0.001) * 100
            html += f'<tr><td>{stat.func_name}</td><td>{stat.call_count}</td>'
            html += f'<td>{stat.total_time_ms:.4f}</td><td>{stat.cumulative_time_ms:.4f}</td>'
            html += f'<td>{pct:.1f}%</td></tr>\n'

        html += f"""
  </table>

  <h2>Trace 数据 (Chrome://tracing)</h2>
  <p>复制以下数据到 <a href="chrome://tracing" target="_blank">chrome://tracing</a> 查看火焰图:</p>
  <pre id="trace-data">{trace_json[:2000]}...</pre>

  <script>
    document.getElementById('trace-data').textContent = JSON.stringify({trace_json}, null, 2);
    document.getElementById('trace-data').select();
    document.execCommand('copy');
    alert('Trace 数据已复制到剪贴板！粘贴到 chrome://tracing 查看火焰图');
  </script>
</body>
</html>"""

        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return str(output_path)

    def get_call_tree(self) -> Dict[str, CallStats]:
        """获取调用树。"""
        return dict(self._call_tree)

    def reset(self) -> None:
        """重置 profiler。"""
        self._call_tree = {}
        self._start_time = 0.0
        self._end_time = 0.0
        self._active = False
        self._profiler = None


# ============================================================
# 装饰器
# ============================================================

_profiled_functions: Dict[str, MathaProfiler] = {}

def profile(func: Optional[Callable] = None, *, name: Optional[str] = None,
            sort_by: str = "cumulative", top_n: int = 20) -> Callable:
    """
    函数级 Profiler 装饰器。

    用法:
        @profile
        def fib(n):
            if n <= 1: return n
            return fib(n-1) + fib(n-2)

        result = fib(30)
        print(fib.__profile_report__)  # 查看报告
    """
    def decorator(fn: Callable) -> Callable:
        func_key = name or fn.__name__
        profiler = MathaProfiler(sort_by=sort_by, top_n=top_n)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with profiler:
                return fn(*args, **kwargs)

        wrapper._profiler = profiler
        wrapper._func_key = func_key
        _profiled_functions[func_key] = profiler
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def get_profile_report(func_name: str) -> str:
    """获取指定函数的性能报告。"""
    if func_name in _profiled_functions:
        profiler = _profiled_functions[func_name]
        if profiler._call_tree:
            total_time = (profiler._end_time - profiler._start_time) * 1000
            return profiler.report("markdown")
    return f"函数 '{func_name}' 无 profiling 数据。请先调用该函数。"


def all_reports() -> Dict[str, str]:
    """获取所有已 profiled 函数的报告。"""
    return {
        name: p.report("markdown")
        for name, p in _profiled_functions.items()
        if p._call_tree
    }


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 性能 Profiler 测试")
    print("=" * 60)

    # 测试1: Fibonacci profiling
    @profile(name="fibonacci")
    def fib(n: int) -> int:
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)

    print("\n【Fibonacci F(25) Profiling】")
    result = fib(25)
    print(f"  fib(25) = {result}")

    report = fib.__wrapped__.__profile_report__ if hasattr(fib, '__wrapped__') else ""
    profiler = fib._profiler
    if profiler._call_tree:
        print("\n" + profiler.report("markdown"))

    # 测试2: 对比优化前后的性能
    print("\n【优化前后对比】")
    from src.compiler.memoize import MemoizeOptimizer
    optimizer = MemoizeOptimizer()

    # 原始
    def fib_raw(n: int) -> int:
        if n <= 1: return n
        return fib_raw(n - 1) + fib_raw(n - 2)

    # Memoized
    fib_memo = optimizer.memoize(fib_raw)

    # 基准测试
    import time
    iterations = 10

    start = time.perf_counter()
    for _ in range(iterations):
        fib_raw(25)
    raw_time = (time.perf_counter() - start) / iterations * 1000

    start = time.perf_counter()
    for _ in range(iterations):
        fib_memo(25)
    memo_time = (time.perf_counter() - start) / iterations * 1000

    print(f"  原始 Fibonacci(25): {raw_time:.2f}ms")
    print(f"  Memoized Fibonacci: {memo_time:.4f}ms")
    print(f"  加速比: {raw_time / max(memo_time, 0.001):.1f}x")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
