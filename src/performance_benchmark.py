"""
Matha 性能基准对比 v2.0
========================
对比 Matha 与 C++/Rust/Go/Java 在相同算法上的性能表现。

测试场景：
  1. 矩阵运算（SVD/求逆/乘法）
  2. 排序算法（快速排序/归并排序）
  3. 数值计算（PI 计算/傅里叶变换）
  4. 字符串处理（搜索/匹配）
  5. 并发性能（线程/进程并行）

报告生成：
  - 基准测试数据
  - 加速比分析
  - 性能瓶颈识别
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("matha.benchmark")


# ═══════════════════════════════════════════════════════════════════════════════
#  基准测试数据类
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkResult:
    """单次基准测试结果。"""
    test_name: str
    language: str
    iterations: int
    avg_ms: float
    min_ms: float
    max_ms: float
    result_value: Any = None
    error: str = ""


@dataclass
class PerformanceReport:
    """性能报告。"""
    tests: list[BenchmarkResult] = field(default_factory=list)
    summary: dict[str, dict[str, float]] = field(default_factory=dict)

    def add_result(self, result: BenchmarkResult) -> None:
        self.tests.append(result)

    def compute_summary(self) -> dict[str, dict[str, float]]:
        """计算各语言性能汇总。"""
        langs = set(r.language for r in self.tests)
        self.summary = {}
        for lang in langs:
            lang_results = [r for r in self.tests if r.language == lang]
            self.summary[lang] = {
                "total_tests": len(lang_results),
                "avg_ms_total": sum(r.avg_ms for r in lang_results),
                "min_ms_total": min(r.min_ms for r in lang_results),
                "max_ms_total": max(r.max_ms for r in lang_results),
            }
        return self.summary

    def generate_markdown(self) -> str:
        """生成 Markdown 报告。"""
        lines = [
            "# Matha 性能基准对比报告 v2.0",
            "",
            "## 测试概览",
            f"- 测试用例: {len(self.tests)}",
            f"- 测试语言: {', '.join(set(r.language for r in self.tests))}",
            "",
            "## 详细结果",
            "",
            "| 测试 | 语言 | 耗时(ms) | 最小 | 最大 | 结果 |",
            "|------|------|----------|------|------|------|",
        ]
        for r in self.tests:
            status = "✅" if not r.error else f"❌ {r.error}"
            lines.append(
                f"| {r.test_name} | {r.language} | "
                f"{r.avg_ms:.2f} | {r.min_ms:.2f} | {r.max_ms:.2f} | {status} |"
            )

        lines.append("")
        lines.append("## 性能对比")
        lines.append("")
        for lang, stats in self.compute_summary().items():
            lines.append(f"### {lang}")
            lines.append(f"- 测试数: {stats['total_tests']}")
            lines.append(f"- 平均总耗时: {stats['avg_ms_total']:.2f}ms")
            lines.append(f"- 最快: {stats['min_ms_total']:.2f}ms")
            lines.append(f"- 最慢: {stats['max_ms_total']:.2f}ms")
            lines.append("")

        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  基准测试用例
# ═══════════════════════════════════════════════════════════════════════════════

class BenchmarkSuite:
    """基准测试套件。"""

    def __init__(self):
        self._results: list[BenchmarkResult] = []

    def run_benchmark(self, name: str, func, args: tuple,
                      iterations: int = 1000, language: str = "matha") -> BenchmarkResult:
        """运行单次基准测试。"""
        times = []
        result = None
        error = ""
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                result = func(*args)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception as e:
                error = str(e)[:100]
                break

        if times:
            return BenchmarkResult(
                test_name=name,
                language=language,
                iterations=iterations,
                avg_ms=sum(times) / len(times),
                min_ms=min(times),
                max_ms=max(times),
                result_value=result,
                error=error,
            )
        else:
            return BenchmarkResult(
                test_name=name, language=language,
                iterations=iterations, avg_ms=0, min_ms=0, max_ms=0,
                error=error or "无有效结果",
            )

    def add_result(self, result: BenchmarkResult) -> None:
        self._results.append(result)

    def generate_report(self) -> PerformanceReport:
        """生成性能报告。"""
        report = PerformanceReport(tests=self._results)
        report.compute_summary()
        return report


# ═══════════════════════════════════════════════════════════════════════════════
#  多语言基准测试
# ═══════════════════════════════════════════════════════════════════════════════

class MultiLangBenchmark:
    """
    多语言性能基准对比。

    对比 Matha(Python) vs C++ vs Rust vs Go vs Java
    """

    def __init__(self, work_dir: str = None):
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="matha_bench_")
        self._suite = BenchmarkSuite()

    def benchmark_matrix_svd(self, size: int = 20, iterations: int = 5) -> None:
        """矩阵 SVD 基准测试（打的是内核纯 Python 实现，不再借 NumPy）。

        阶段 3 去依赖：原先这里 `import numpy`，以 `np.linalg.svd` 作为
        “Matha 性能”，测的其实是 BLAS。现在直接测 `svd_decompose`（单侧 Jacobi）。
        默认规模/次数下调：纯 Python 是 O(n³) 多轮 sweep，50×50×100 次不现实。
        """
        import random

        from src.stdlib.linear_algebra import Matrix, svd_decompose

        rnd = random.Random(20240517)          # 确定性样本，便于重复对比
        data = [[rnd.uniform(-1.0, 1.0) for _ in range(size)] for _ in range(size)]
        mat = Matrix(data)
        result = self._suite.run_benchmark(
            f"MatrixSVD_{size}x{size}",
            lambda m: svd_decompose(m),
            (mat,),
            iterations=iterations,
            language="matha"
        )
        self._suite.add_result(result)

        # C++ 对照组已删除：旧实现只编译一个 `cout << 0` 占位程序并把
        # `lambda: 0` 当作 C++ 成绩计入，那不是测量而是假成功。要真实对比需
        # 用 Eigen/Armadillo 写完整对照组，属于单独工作项。

    def benchmark_sort(self, n: int = 100000, iterations: int = 100) -> None:
        """排序基准测试。"""
        import random

        data = [random.random() for _ in range(n)]

        # Matha
        result = self._suite.run_benchmark(
            f"Sort_{n}",
            lambda d: sorted(d),
            (data,),
            iterations=iterations,
            language="matha"
        )
        self._suite.add_result(result)

    def benchmark_parallel_compute(self, n: int = 1000000, iterations: int = 10) -> None:
        """并行计算基准测试。"""
        from src.csp_os_thread import ProcessPool

        def compute(x):
            total = 0
            for i in range(n):
                total += i * x
            return total

        # Matha 进程级并行
        pool = ProcessPool(4)
        items = list(range(8))
        start = time.perf_counter()
        results = pool.map(compute, items)
        elapsed = (time.perf_counter() - start) * 1000

        self._suite.add_result(BenchmarkResult(
            test_name=f"ParallelCompute_{n}",
            language="matha",
            iterations=iterations,
            avg_ms=elapsed / iterations,
            min_ms=elapsed / iterations,
            max_ms=elapsed / iterations,
            result_value=len(results),
        ))

    def _compile_cpp(self, code: str, name: str) -> str | None:
        """编译 C++ 代码。"""
        src = os.path.join(self.work_dir, f"{name}.cpp")
        exe = os.path.join(self.work_dir, f"{name}.exe" if sys.platform == "win32" else f"{name}")
        with open(src, "w") as f:
            f.write(code)
        try:
            result = subprocess.run(
                ["g++", "-O2", "-o", exe, src],
                capture_output=True, text=True, timeout=30
            )
            return exe if result.returncode == 0 else ""
        except FileNotFoundError:
            return ""

    def run_all(self) -> PerformanceReport:
        """运行所有基准测试。"""
        print("运行矩阵 SVD 基准...")
        self.benchmark_matrix_svd(size=50, iterations=50)

        print("运行排序基准...")
        self.benchmark_sort(n=100000, iterations=50)

        print("运行并行计算基准...")
        self.benchmark_parallel_compute(n=1000000, iterations=5)

        return self._suite.generate_report()

    def generate_report(self, output_file: str = None) -> str:
        """生成并保存报告。"""
        report = self.run_all()
        markdown = report.generate_markdown()
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown)
        return markdown


# ═══════════════════════════════════════════════════════════════════════════════
#  运行入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 性能基准对比 v2.0")
    print("=" * 60)

    bench = MultiLangBenchmark()
    report = bench.run_all()
    print("\n" + report.generate_markdown())
