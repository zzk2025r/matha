# -*- coding: utf-8 -*-
"""Matha 测试报告生成器

生成详细的测试报告，包括：
  - 测试概述
  - 通过/失败/跳过统计
  - 失败详情
  - 覆盖率分析
"""
from __future__ import annotations
import sys
import unittest
import json
import time
from pathlib import Path
from typing import List, Dict, Any


class TestReportGenerator:
    """测试报告生成器"""

    def __init__(self, test_results: unittest.TestResult):
        """
        初始化报告生成器

        Args:
            test_results: unittest.TestResult 对象
        """
        self.results = test_results
        self.start_time = time.time()

    def generate_summary(self) -> Dict[str, Any]:
        """
        生成测试摘要

        Returns:
            摘要字典
        """
        summary = {
            'total': self.results.testsRun,
            'passed': self.results.testsRun - len(self.results.failures) - len(self.results.errors),
            'failed': len(self.results.failures),
            'errors': len(self.results.errors),
            'skipped': len(self.results.skipped) if hasattr(self.results, 'skipped') else 0,
            'duration_sec': round(time.time() - self.start_time, 3),
        }
        return summary

    def generate_markdown(self, output_path: str) -> str:
        """
        生成 Markdown 格式报告

        Args:
            output_path: 输出文件路径

        Returns:
            Markdown 内容
        """
        summary = self.generate_summary()
        lines = []

        lines.append("# Matha 测试报告\n")
        lines.append(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"> 总耗时：{summary['duration_sec']}s\n")

        lines.append("## 测试概览\n")
        lines.append("| 指标 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 总测试数 | {summary['total']} |")
        lines.append(f"| ✅ 通过 | {summary['passed']} |")
        lines.append(f"| ❌ 失败 | {summary['failed']} |")
        lines.append(f"| ⚠️ 错误 | {summary['errors']} |")
        lines.append(f"| ⏭️ 跳过 | {summary['skipped']} |")
        lines.append(f"| 耗时 | {summary['duration_sec']}s |")
        lines.append("")

        # 通过率
        if summary['total'] > 0:
            pass_rate = summary['passed'] / summary['total'] * 100
            lines.append(f"**通过率：{pass_rate:.1f}%**\n")

        # 失败详情
        if self.results.failures:
            lines.append("## 失败测试详情\n")
            for test, traceback in self.results.failures:
                lines.append(f"### {test}\n")
                lines.append("```\n")
                lines.append(traceback)
                lines.append("```\n")

        if self.results.errors:
            lines.append("## 错误测试详情\n")
            for test, traceback in self.results.errors:
                lines.append(f"### {test}\n")
                lines.append("```\n")
                lines.append(traceback)
                lines.append("```\n")

        # 测试列表
        lines.append("## 测试列表\n")
        for test in self.results.test_names if hasattr(self.results, 'test_names') else []:
            status = "✅" if (test, None) not in self.results.failures and (test, None) not in self.results.errors else "❌"
            lines.append(f"- {status} {test}")
        lines.append("")

        content = '\n'.join(lines)
        Path(output_path).write_text(content, encoding='utf-8')
        return content

    def generate_json(self, output_path: str) -> str:
        """
        生成 JSON 格式报告

        Args:
            output_path: 输出文件路径

        Returns:
            JSON 内容
        """
        summary = self.generate_summary()
        report = {
            'summary': summary,
            'failures': [
                {'test': str(test), 'traceback': tb}
                for test, tb in self.results.failures
            ],
            'errors': [
                {'test': str(test), 'traceback': tb}
                for test, tb in self.results.errors
            ],
        }
        content = json.dumps(report, ensure_ascii=False, indent=2)
        Path(output_path).write_text(content, encoding='utf-8')
        return content


def run_tests_and_generate_report(test_paths: List[str], report_dir: str = 'docs') -> Dict[str, Any]:
    """
    运行测试并生成报告

    Args:
        test_paths: 测试路径列表
        report_dir: 报告输出目录

    Returns:
        报告摘要
    """
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for test_path in test_paths:
        try:
            suite.addTests(loader.discover(test_path, pattern='test_*.py'))
        except Exception as e:
            print(f"警告：无法加载测试路径 {test_path}: {e}")

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    results = runner.run(suite)

    # 生成报告
    generator = TestReportGenerator(results)
    summary = generator.generate_summary()

    # 生成 Markdown 报告
    report_path = Path(report_dir) / 'TEST_REPORT.md'
    generator.generate_markdown(str(report_path))

    # 生成 JSON 报告
    json_path = Path(report_dir) / 'TEST_REPORT.json'
    generator.generate_json(str(json_path))

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成测试报告")
    parser.add_argument("tests", nargs="*", default=['tests'], help="测试路径")
    parser.add_argument("--output", "-o", default="docs", help="报告输出目录")
    args = parser.parse_args()

    summary = run_tests_and_generate_report(args.tests, args.output)
    print(f"\n测试完成：{summary['passed']}/{summary['total']} 通过")
