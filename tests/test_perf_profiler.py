# -*- coding: utf-8 -*-
"""Matha 性能分析器测试"""
import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from src.tools.perf_profiler import MathaProfiler, profile, benchmark


class TestMathaProfiler(unittest.TestCase):
    """测试性能分析器"""

    def setUp(self):
        """设置测试环境"""
        self.profiler = MathaProfiler(enable_memory=False)

    def test_start_stop(self):
        """测试开始和停止"""
        self.profiler.start()
        self.profiler.stop()
        # 不应该抛出异常

    def test_profile_decorator(self):
        """测试 profile 装饰器"""
        @self.profiler.profile
        def test_func():
            return 42

        result = test_func()
        self.assertEqual(result, 42)
        self.assertIn('test_func', self.profiler._results)

    def test_benchmark(self):
        """测试基准测试"""
        def sample_func():
            return sum(range(100))

        result = self.profiler.benchmark("sample", sample_func, iterations=10)
        self.assertIn('avg_ms', result)
        self.assertGreater(result['avg_ms'], 0)

    def test_get_memory_usage(self):
        """测试内存使用获取"""
        memory = self.profiler.get_memory_usage()
        # 禁用内存时应该返回空字典
        self.assertEqual(memory, {})

    def test_generate_html_report(self):
        """测试 HTML 报告生成"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            path = f.name

        html = self.profiler.generate_html_report(path)
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 0)

        # 清理
        Path(path).unlink(missing_ok=True)

    def test_generate_json_report(self):
        """测试 JSON 报告生成"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name

        json_content = self.profiler.generate_json_report(path)
        self.assertIsInstance(json_content, str)
        self.assertGreater(len(json_content), 0)

        # 清理
        Path(path).unlink(missing_ok=True)

    def test_clear_results(self):
        """测试清除结果"""
        self.profiler._results['test'] = None
        self.profiler.clear_results()
        self.assertEqual(len(self.profiler._results), 0)

    def test_print_summary(self):
        """测试打印摘要"""
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        self.profiler.print_summary()

        sys.stdout = old_stdout
        output = buffer.getvalue()
        self.assertIn("Matha 性能分析摘要", output)


class TestPerformanceRegression(unittest.TestCase):
    """测试性能回归"""

    def setUp(self):
        """设置测试环境"""
        self.profiler = MathaProfiler(enable_memory=False)

    def test_simple_function_performance(self):
        """测试简单函数性能"""
        def simple_func():
            return sum(range(1000))

        passed = self.profiler.run_performance_test(
            "simple_sum",
            simple_func,
            threshold_ms=100.0
        )
        self.assertTrue(passed)

    def test_matrix_multiply_performance(self):
        """测试矩阵乘法性能"""
        from src.stdlib.linear_algebra import matrix_multiply, Matrix

        A = Matrix([[1.0, 2.0], [3.0, 4.0]])
        B = Matrix([[5.0, 6.0], [7.0, 8.0]])

        passed = self.profiler.run_performance_test(
            "matrix_multiply",
            matrix_multiply,
            A, B,
            threshold_ms=100.0
        )
        self.assertTrue(passed)


class TestDecorators(unittest.TestCase):
    """测试便捷函数"""

    def test_profile_decorator(self):
        """测试 profile 装饰器"""
        @profile
        def test_func():
            return 42

        result = test_func()
        self.assertEqual(result, 42)

    def test_benchmark_function(self):
        """测试 benchmark 函数"""
        def sample_func():
            return sum(range(100))

        result = benchmark("sample", sample_func, iterations=10)
        self.assertIn('avg_ms', result)


if __name__ == '__main__':
    unittest.main()
