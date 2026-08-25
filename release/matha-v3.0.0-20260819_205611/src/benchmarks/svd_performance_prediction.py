# -*- coding: utf-8 -*-
"""Matha v4.4 — 稀疏 SVD 性能预测与可视化

本脚本基于现有性能数据，预测 1000x1000 规模矩阵的 SVD 耗时，
并生成可视化图表。

用法：
  python src/benchmarks/svd_performance_prediction.py
  python src/benchmarks/svd_performance_prediction.py --verbose
  python src/benchmarks/svd_performance_prediction.py --sizes 10 50 100 500 1000
"""
import sys
import logging
import math
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """设置日志级别。"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )


class SVDPerformancePredictor:
    """SVD 性能预测器。"""

    # 基于实际测试数据的基准点
    # 格式: (规模, 纯 Python 耗时 ms, NumPy 耗时 ms, 稀疏 SVD 耗时 ms)
    BASELINE_DATA = [
        (10, 44.58, 0.04, 30.00),
        (20, 162.38, 0.10, 100.00),
        (30, 570.00, 0.30, 47.00),
        (50, 1908.38, 1.00, 950.00),
    ]

    def __init__(self):
        """初始化预测器。"""
        self.baseline_sizes = [d[0] for d in self.BASELINE_DATA]
        self.baseline_python_times = [d[1] for d in self.BASELINE_DATA]
        self.baseline_numpy_times = [d[2] for d in self.BASELINE_DATA]
        self.baseline_sparse_times = [d[3] for d in self.BASELINE_DATA]

    def fit_power_law(self, sizes: List[int], times: List[float]) -> Dict:
        """
        拟合幂律模型: time = a * n^b

        使用最小二乘法拟合 log(time) = log(a) + b * log(n)

        Returns:
            拟合参数 {a, b, r_squared}
        """
        if len(sizes) < 2:
            return {'a': 0, 'b': 0, 'r_squared': 0}

        # 取对数
        log_sizes = [math.log(s) for s in sizes]
        log_times = [math.log(t) if t > 0 else 0 for t in times]

        n = len(log_sizes)
        sum_x = sum(log_sizes)
        sum_y = sum(log_times)
        sum_xy = sum(x * y for x, y in zip(log_sizes, log_times))
        sum_x2 = sum(x * x for x in log_sizes)

        # 线性回归
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return {'a': 0, 'b': 0, 'r_squared': 0}

        b = (n * sum_xy - sum_x * sum_y) / denominator
        a_log = (sum_y - b * sum_x) / n
        a = math.exp(a_log)

        # 计算 R²
        y_pred = [a * (s ** b) for s in sizes]
        y_mean = sum(times) / n
        ss_res = sum((t - p) ** 2 for t, p in zip(times, y_pred))
        ss_tot = sum((t - y_mean) ** 2 for t in times)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {'a': a, 'b': b, 'r_squared': r_squared}

    def predict_time(self, n: int, method: str = 'python', sparsity: float = 0.0) -> float:
        """
        预测指定规模矩阵的 SVD 耗时。

        Args:
            n: 矩阵规模
            method: 算法类型 ('python', 'numpy', 'sparse')
            sparsity: 稀疏度（0-1，仅对 sparse 方法有效）

        Returns:
            预测耗时（ms）
        """
        if method == 'python':
            params = self.fit_power_law(self.baseline_sizes, self.baseline_python_times)
            predicted = params['a'] * (n ** params['b'])
        elif method == 'numpy':
            params = self.fit_power_law(self.baseline_sizes, self.baseline_numpy_times)
            predicted = params['a'] * (n ** params['b'])
        elif method == 'sparse':
            # 稀疏矩阵：基于标准 Python 预测，然后应用稀疏加速因子
            params = self.fit_power_law(self.baseline_sizes, self.baseline_python_times)
            predicted = params['a'] * (n ** params['b'])

            # 应用稀疏加速因子
            if sparsity >= 0.95:
                sparse_factor = 5.0
            elif sparsity >= 0.90:
                sparse_factor = 2.0
            else:
                sparse_factor = 1.0

            predicted = predicted / sparse_factor
        else:
            raise ValueError(f"未知的方法: {method}")

        return max(predicted, 0.001)  # 避免零或负值

    def predict_all(self, target_sizes: List[int]) -> Dict:
        """
        预测多个规模的耗时。

        Args:
            target_sizes: 目标规模列表

        Returns:
            预测结果字典
        """
        results = {
            'python': [],
            'numpy': [],
            'sparse_90': [],
            'sparse_95': [],
            'sparse_99': [],
        }

        for n in target_sizes:
            results['python'].append({
                'size': n,
                'time_ms': self.predict_time(n, 'python'),
                'time_sec': self.predict_time(n, 'python') / 1000,
            })
            results['numpy'].append({
                'size': n,
                'time_ms': self.predict_time(n, 'numpy'),
                'time_sec': self.predict_time(n, 'numpy') / 1000,
            })
            results['sparse_90'].append({
                'size': n,
                'time_ms': self.predict_time(n, 'sparse', 0.90),
                'time_sec': self.predict_time(n, 'sparse', 0.90) / 1000,
            })
            results['sparse_95'].append({
                'size': n,
                'time_ms': self.predict_time(n, 'sparse', 0.95),
                'time_sec': self.predict_time(n, 'sparse', 0.95) / 1000,
            })
            results['sparse_99'].append({
                'size': n,
                'time_ms': self.predict_time(n, 'sparse', 0.99),
                'time_sec': self.predict_time(n, 'sparse', 0.99) / 1000,
            })

        return results

    def generate_chart(self, results: Dict, output_path: Optional[str] = None) -> str:
        """
        生成 ASCII 性能图表。

        Args:
            results: 预测结果
            output_path: 输出路径（可选）

        Returns:
            图表字符串
        """
        chart_lines = []
        chart_lines.append("\n" + "=" * 80)
        chart_lines.append("  SVD 性能预测图表（基于 O(n³) 复杂度模型）")
        chart_lines.append("=" * 80)

        # 找到最大时间用于缩放
        all_times = []
        for key in ['python', 'numpy', 'sparse_90', 'sparse_95', 'sparse_99']:
            for item in results[key]:
                all_times.append(item['time_ms'])

        max_time = max(all_times) if all_times else 1
        chart_width = 60

        # 表头
        chart_lines.append(f"\n  {'规模':<10s} {'纯Python':<15s} {'NumPy':<15s} {'稀疏90%':<15s} {'稀疏95%':<15s}")
        chart_lines.append(f"  {'-'*70}")

        # 生成每行数据
        if results['python']:
            n = results['python'][0]['size']
            python_time = results['python'][0]['time_ms']
            numpy_time = results['numpy'][0]['time_ms']
            sparse_90_time = results['sparse_90'][0]['time_ms']
            sparse_95_time = results['sparse_95'][0]['time_ms']

            # 纯 Python 柱状图
            python_bar_len = int(python_time / max_time * chart_width) if max_time > 0 else 0
            python_bar = '█' * max(1, python_bar_len)

            # NumPy 柱状图
            numpy_bar_len = int(numpy_time / max_time * chart_width) if max_time > 0 else 0
            numpy_bar = '░' * max(1, numpy_bar_len)

            # 稀疏 SVD 柱状图
            sparse_90_bar_len = int(sparse_90_time / max_time * chart_width) if max_time > 0 else 0
            sparse_90_bar = '▓' * max(1, sparse_90_bar_len)

            sparse_95_bar_len = int(sparse_95_time / max_time * chart_width) if max_time > 0 else 0
            sparse_95_bar = '▒' * max(1, sparse_95_bar_len)

            chart_lines.append(f"  {n}x{n:<6} {python_time:>10.1f}ms {numpy_time:>10.3f}ms {sparse_90_time:>10.1f}ms {sparse_95_time:>10.1f}ms")
            chart_lines.append(f"  {'':10s} {python_bar:<20s} {numpy_bar:<20s} {sparse_90_bar:<20s} {sparse_95_bar:<20s}")

        # 多规模对比
        if len(results['python']) > 1:
            chart_lines.append(f"\n  {'规模':<10s} {'纯Python':<12s} {'NumPy':<12s} {'稀疏90%':<12s} {'稀疏95%':<12s}")
            chart_lines.append(f"  {'-'*60}")

            for i in range(min(5, len(results['python']))):
                n = results['python'][i]['size']
                pt = results['python'][i]['time_ms']
                nt = results['numpy'][i]['time_ms']
                st90 = results['sparse_90'][i]['time_ms']
                st95 = results['sparse_95'][i]['time_ms']

                # 格式化时间显示
                if pt >= 1000:
                    pt_str = f"{pt/1000:.1f}s"
                else:
                    pt_str = f"{pt:.1f}ms"

                if nt >= 1000:
                    nt_str = f"{nt/1000:.1f}s"
                else:
                    nt_str = f"{nt:.3f}ms"

                if st90 >= 1000:
                    st90_str = f"{st90/1000:.1f}s"
                else:
                    st90_str = f"{st90:.1f}ms"

                if st95 >= 1000:
                    st95_str = f"{st95/1000:.1f}s"
                else:
                    st95_str = f"{st95:.1f}ms"

                chart_lines.append(f"  {n}x{n:<6} {pt_str:<12s} {nt_str:<12s} {st90_str:<12s} {st95_str:<12s}")

        chart_lines.append("\n" + "=" * 80)

        chart_text = "\n".join(chart_lines)

        # 保存图表
        if output_path:
            Path(output_path).write_text(chart_text, encoding='utf-8')
            logger.info(f"图表已保存: {output_path}")

        return chart_text

    def generate_csv_report(self, results: Dict, output_path: str):
        """生成 CSV 报告。"""
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['规模', '纯Python(ms)', 'NumPy(ms)', '稀疏90%(ms)', '稀疏95%(ms)', '稀疏99%(ms)'])

            if results['python']:
                for i in range(len(results['python'])):
                    n = results['python'][i]['size']
                    pt = results['python'][i]['time_ms']
                    nt = results['numpy'][i]['time_ms']
                    st90 = results['sparse_90'][i]['time_ms']
                    st95 = results['sparse_95'][i]['time_ms']
                    st99 = results['sparse_99'][i]['time_ms']

                    writer.writerow([f"{n}x{n}", f"{pt:.2f}", f"{nt:.4f}", f"{st90:.2f}", f"{st95:.2f}", f"{st99:.2f}"])

        logger.info(f"CSV 报告已保存: {output_path}")


def main():
    """主函数。"""
    import argparse
    parser = argparse.ArgumentParser(description="Matha v4.4 SVD 性能预测")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    parser.add_argument("--sizes", "-s", type=int, nargs='+', default=[10, 50, 100, 500, 1000],
                       help="预测规模列表（默认: 10 50 100 500 1000）")
    parser.add_argument("--output", "-o", default=None, help="输出文件路径")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 80)
    print("  Matha v4.4 SVD 性能预测分析")
    print("=" * 80)

    # 创建预测器
    predictor = SVDPerformancePredictor()

    # 显示基准数据
    print("\n  【基准数据】")
    print(f"  {'规模':<8s} {'纯Python(ms)':<15s} {'NumPy(ms)':<12s} {'稀疏SVD(ms)':<12s}")
    print(f"  {'-'*50}")
    for size, python_t, numpy_t, sparse_t in predictor.BASELINE_DATA:
        print(f"  {size}x{size:<4} {python_t:>12.2f}ms   {numpy_t:>8.4f}ms   {sparse_t:>10.2f}ms")

    # 预测性能
    print("\n  【性能预测】")
    results = predictor.predict_all(args.sizes)

    # 生成图表
    chart = predictor.generate_chart(results, args.output)
    print(chart)

    # 关键发现
    print("\n  【关键发现】")
    if results['python']:
        n_1000 = results['python'][0]['size'] if results['python'][0]['size'] == 1000 else args.sizes[-1]
        idx = next((i for i, r in enumerate(results['python']) if r['size'] == 1000), None)
        if idx is not None:
            pt = results['python'][idx]['time_sec']
            nt = results['numpy'][idx]['time_sec']
            st = results['sparse_95'][idx]['time_sec']

            print(f"\n  1000x1000 矩阵 SVD 预测耗时:")
            print(f"    - 纯 Python:  {pt:.1f} 秒 ({pt/60:.1f} 分钟)")
            print(f"    - NumPy:      {nt:.3f} 秒 ({nt*1000:.1f} 毫秒)")
            print(f"    - 稀疏 SVD:   {st:.1f} 秒 ({st/60:.1f} 分钟)")
            print(f"\n  加速比:")
            print(f"    - NumPy vs 纯 Python: {pt/nt:.0f}x")
            print(f"    - 稀疏 SVD vs 纯 Python: {pt/st:.1f}x")

    # 生成 CSV 报告
    csv_path = str(Path(__file__).parent / 'svd_performance_prediction.csv')
    predictor.generate_csv_report(results, csv_path)
    print(f"\n  CSV 报告已保存: {csv_path}")

    print("\n" + "=" * 80)
    print("  预测完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
