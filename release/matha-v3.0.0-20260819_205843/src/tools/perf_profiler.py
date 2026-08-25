# -*- coding: utf-8 -*-
"""Matha 性能分析器模块

提供性能分析功能：
  - 函数执行时间追踪
  - JIT 编译效果对比
  - 内存使用分析
  - HTML/JSON 报告生成
  - 性能回归测试

使用方式：
  from src.tools.perf_profiler import MathaProfiler
  profiler = MathaProfiler()
  profiler.start()
  # 执行代码...
  profiler.stop()
  profiler.generate_report('docs/performance_report.html')
"""
from __future__ import annotations
import time
import sys
import os
import json
import tracemalloc
import functools
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """性能分析结果"""
    function_name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    memory_delta_mb: float = 0.0
    jit_speedup: float = 0.0  # JIT 编译加速比


@dataclass
class PerformanceReport:
    """性能报告"""
    timestamp: str
    results: List[ProfileResult]
    summary: Dict[str, Any]
    html_content: Optional[str] = None
    json_content: Optional[str] = None


class MathaProfiler:
    """Matha 性能分析器"""

    def __init__(self, enable_memory: bool = True, enable_jit: bool = True):
        """
        初始化性能分析器

        Args:
            enable_memory: 是否启用内存分析
            enable_jit: 是否启用 JIT 效果对比
        """
        self._results: Dict[str, ProfileResult] = {}
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._enable_memory = enable_memory
        self._enable_jit = enable_jit
        self._jit_cache: Dict[str, Tuple[float, Callable]] = {}
        self._benchmark_data: Dict[str, Dict[str, float]] = {}

        if enable_memory:
            tracemalloc.start()

    def start(self) -> None:
        """开始性能分析"""
        self._start_time = time.perf_counter()
        if self._enable_memory:
            tracemalloc.start()
        logger.info("性能分析器已启动")

    def stop(self) -> None:
        """停止性能分析"""
        self._end_time = time.perf_counter()
        if self._enable_memory:
            tracemalloc.stop()
        logger.info("性能分析器已停止")

    def profile(self, func: Callable) -> Callable:
        """
        装饰器：分析函数性能

        Args:
            func: 要分析的函数

        Returns:
            包装后的函数
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000  # 转换为毫秒

            if func.__name__ not in self._results:
                self._results[func.__name__] = ProfileResult(
                    function_name=func.__name__
                )

            profile = self._results[func.__name__]
            profile.call_count += 1
            profile.total_time_ms += elapsed
            profile.avg_time_ms = profile.total_time_ms / profile.call_count
            profile.min_time_ms = min(profile.min_time_ms, elapsed)
            profile.max_time_ms = max(profile.max_time_ms, elapsed)

            return result
        return wrapper

    def benchmark(self, name: str, func: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, float]:
        """
        运行基准测试

        Args:
            name: 测试名称
            func: 要测试的函数
            *args: 位置参数
            iterations: 迭代次数
            **kwargs: 关键字参数

        Returns:
            基准测试结果
        """
        # 预热
        for _ in range(10):
            func(*args, **kwargs)

        # 正式测试
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = {
            'name': name,
            'iterations': iterations,
            'avg_ms': sum(times) / len(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'total_ms': sum(times),
        }

        self._benchmark_data[name] = result
        return result

    def compare_jit(self, name: str, func: Callable, *args, **kwargs) -> Dict[str, float]:
        """
        比较 JIT 编译效果

        Args:
            name: 函数名称
            func: 函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            JIT 效果对比结果
        """
        if not self._enable_jit:
            return {}

        # 记录原始执行时间
        start = time.perf_counter()
        func(*args, **kwargs)
        original_time = (time.perf_counter() - start) * 1000

        # 如果有 JIT 缓存，获取编译后执行时间
        if name in self._jit_cache:
            _, compiled_func = self._jit_cache[name]
            start = time.perf_counter()
            compiled_func(*args, **kwargs)
            compiled_time = (time.perf_counter() - start) * 1000

            speedup = original_time / compiled_time if compiled_time > 0 else 1.0
        else:
            compiled_time = original_time
            speedup = 1.0

        result = {
            'name': name,
            'original_time_ms': original_time,
            'compiled_time_ms': compiled_time,
            'speedup': speedup,
        }

        if name in self._results:
            self._results[name].jit_speedup = speedup

        return result

    def get_memory_usage(self) -> Dict[str, float]:
        """获取当前内存使用情况"""
        if not self._enable_memory:
            return {}

        current, peak = tracemalloc.get_traced_memory()
        return {
            'current_mb': current / 1024 / 1024,
            'peak_mb': peak / 1024 / 1024,
        }

    def generate_html_report(self, output_path: str) -> str:
        """
        生成 HTML 格式性能报告

        Args:
            output_path: 输出文件路径

        Returns:
            HTML 内容
        """
        summary = self._generate_summary()
        results_html = self._generate_results_html()
        benchmarks_html = self._generate_benchmarks_html()

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Matha 性能分析报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f4f4f4; }}
        .summary {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .metric {{ display: inline-block; margin-right: 20px; padding: 10px 20px; background: #e8f4f8; border-radius: 5px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        .speedup {{ color: green; }}
        .slow {{ color: red; }}
    </style>
</head>
<body>
    <h1>Matha 性能分析报告</h1>
    <p>生成时间：{summary['timestamp']}</p>

    <div class="summary">
        <h2>执行摘要</h2>
        <div class="metric">
            <div class="metric-value">{summary['total_time_ms']:.2f}ms</div>
            <div class="metric-label">总执行时间</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary['total_calls']}</div>
            <div class="metric-label">总调用次数</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary['avg_time_ms']:.3f}ms</div>
            <div class="metric-label">平均每次调用</div>
        </div>
    </div>

    <h2>函数性能分析</h2>
    {results_html}

    <h2>基准测试结果</h2>
    {benchmarks_html}

    <h2>内存使用情况</h2>
    <table>
        <tr><th>指标</th><th>值 (MB)</th></tr>
        <tr><td>当前内存</td><td>{summary.get('current_memory_mb', 'N/A')}</td></tr>
        <tr><td>峰值内存</td><td>{summary.get('peak_memory_mb', 'N/A')}</td></tr>
    </table>

    <h2>JIT 编译效果对比</h2>
    <table>
        <tr><th>函数</th><th>原始时间 (ms)</th><th>编译后时间 (ms)</th><th>加速比</th></tr>
        {self._generate_jit_html()}
    </table>

    <footer>
        <p>Matha v4.4.3 - 性能分析器报告</p>
    </footer>
</body>
</html>"""

        Path(output_path).write_text(html, encoding='utf-8')
        return html

    def generate_json_report(self, output_path: str) -> str:
        """
        生成 JSON 格式性能报告

        Args:
            output_path: 输出文件路径

        Returns:
            JSON 内容
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': self._generate_summary(),
            'results': [
                {
                    'function_name': r.function_name,
                    'call_count': r.call_count,
                    'total_time_ms': r.total_time_ms,
                    'avg_time_ms': r.avg_time_ms,
                    'min_time_ms': r.min_time_ms if r.min_time_ms != float('inf') else 0,
                    'max_time_ms': r.max_time_ms,
                    'jit_speedup': r.jit_speedup,
                }
                for r in self._results.values()
            ],
            'benchmarks': self._benchmark_data,
            'memory': self.get_memory_usage(),
        }

        content = json.dumps(report, ensure_ascii=False, indent=2)
        Path(output_path).write_text(content, encoding='utf-8')
        return content

    def _generate_summary(self) -> Dict[str, Any]:
        """生成执行摘要"""
        total_time = self._end_time - self._start_time if self._end_time > 0 else 0
        total_calls = sum(r.call_count for r in self._results.values())
        total_time_ms = total_time * 1000

        avg_time = total_time_ms / total_calls if total_calls > 0 else 0

        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_time_ms': total_time_ms,
            'total_calls': total_calls,
            'avg_time_ms': avg_time,
            'functions_tracked': len(self._results),
        }

        if self._enable_memory:
            memory = self.get_memory_usage()
            summary.update(memory)

        return summary

    def _generate_results_html(self) -> str:
        """生成结果 HTML 表格"""
        if not self._results:
            return "<p>暂无分析数据</p>"

        rows = []
        for name, result in sorted(self._results.items(), key=lambda x: x[1].total_time_ms, reverse=True):
            speedup_class = 'speedup' if result.jit_speedup > 1.5 else ('slow' if result.jit_speedup < 0.5 else '')
            speedup_str = f"{result.jit_speedup:.2f}x" if result.jit_speedup > 0 else "N/A"

            rows.append(f"""
            <tr>
                <td>{name}</td>
                <td>{result.call_count}</td>
                <td>{result.total_time_ms:.3f}</td>
                <td>{result.avg_time_ms:.3f}</td>
                <td>{result.min_time_ms:.3f}</td>
                <td>{result.max_time_ms:.3f}</td>
                <td class="{speedup_class}">{speedup_str}</td>
            </tr>""")

        return f"""
        <table>
            <tr>
                <th>函数名</th>
                <th>调用次数</th>
                <th>总时间 (ms)</th>
                <th>平均时间 (ms)</th>
                <th>最小时间 (ms)</th>
                <th>最大时间 (ms)</th>
                <th>JIT 加速比</th>
            </tr>
            {''.join(rows)}
        </table>"""

    def _generate_benchmarks_html(self) -> str:
        """生成基准测试 HTML"""
        if not self._benchmark_data:
            return "<p>暂无基准测试结果</p>"

        rows = []
        for name, data in self._benchmark_data.items():
            rows.append(f"""
            <tr>
                <td>{name}</td>
                <td>{data.get('iterations', 0)}</td>
                <td>{data.get('avg_ms', 0):.3f}</td>
                <td>{data.get('min_ms', 0):.3f}</td>
                <td>{data.get('max_ms', 0):.3f}</td>
                <td>{data.get('total_ms', 0):.3f}</td>
            </tr>""")

        return f"""
        <table>
            <tr>
                <th>测试名称</th>
                <th>迭代次数</th>
                <th>平均时间 (ms)</th>
                <th>最小时间 (ms)</th>
                <th>最大时间 (ms)</th>
                <th>总时间 (ms)</th>
            </tr>
            {''.join(rows)}
        </table>"""

    def _generate_jit_html(self) -> str:
        """生成 JIT 效果 HTML 表格"""
        rows = []
        for name, result in self._results.items():
            if result.jit_speedup > 0:
                speedup_class = 'speedup' if result.jit_speedup > 1.5 else 'slow'
                rows.append(f"""
                <tr>
                    <td>{name}</td>
                    <td>{result.avg_time_ms * result.jit_speedup:.3f}</td>
                    <td>{result.avg_time_ms:.3f}</td>
                    <td class="{speedup_class}">{result.jit_speedup:.2f}x</td>
                </tr>""")

        return ''.join(rows) if rows else "<tr><td colspan='4'>暂无 JIT 数据</td></tr>"

    def run_performance_test(self, test_name: str, func: Callable, *args, **kwargs) -> bool:
        """
        运行性能回归测试

        Args:
            test_name: 测试名称
            func: 测试函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            测试是否通过（性能在阈值内）
        """
        # 运行测试
        result = self.benchmark(test_name, func, *args, iterations=50)

        # 检查性能阈值（默认 100ms）
        threshold_ms = kwargs.get('threshold_ms', 100.0)
        passed = result['avg_ms'] < threshold_ms

        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"性能测试 [{test_name}]: {status} (平均: {result['avg_ms']:.3f}ms)")

        return passed

    def clear_results(self) -> None:
        """清除分析结果"""
        self._results.clear()
        self._benchmark_data.clear()
        logger.info("性能分析结果已清除")

    def print_summary(self) -> None:
        """打印性能摘要"""
        summary = self._generate_summary()
        print("\n" + "=" * 60)
        print("  Matha 性能分析摘要")
        print("=" * 60)
        print(f"  总执行时间: {summary['total_time_ms']:.2f}ms")
        print(f"  总调用次数: {summary['total_calls']}")
        print(f"  平均每次调用: {summary['avg_time_ms']:.3f}ms")
        print(f"  跟踪函数数: {summary['functions_tracked']}")
        if 'current_mb' in summary:
            print(f"  当前内存: {summary['current_mb']:.2f}MB")
            print(f"  峰值内存: {summary['peak_mb']:.2f}MB")
        print("=" * 60 + "\n")


# ============================================================
# 便捷函数
# ============================================================

def profile(func: Callable) -> Callable:
    """简化的 profile 装饰器"""
    profiler = MathaProfiler()
    return profiler.profile(func)


def benchmark(name: str, func: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, float]:
    """简化的 benchmark 函数"""
    profiler = MathaProfiler()
    return profiler.benchmark(name, func, *args, iterations=iterations, **kwargs)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  Matha 性能分析器演示")
    print("=" * 60)

    profiler = MathaProfiler()
    profiler.start()

    # 演示基准测试
    def sample_function(n: int = 1000) -> int:
        return sum(range(n))

    result = profiler.benchmark("sum_range", sample_function, 1000, iterations=100)
    print(f"\n基准测试结果: {result}")

    # 演示内存使用
    memory = profiler.get_memory_usage()
    print(f"内存使用: {memory}")

    profiler.stop()
    profiler.print_summary()

    # 生成报告
    report_path = "docs/performance_report.html"
    profiler.generate_html_report(report_path)
    print(f"\nHTML 报告已生成: {report_path}")

    json_path = "docs/performance_report.json"
    profiler.generate_json_report(json_path)
    print(f"JSON 报告已生成: {json_path}")

    print("\n" + "=" * 60)
    print("  演示完成")
    print("=" * 60)
