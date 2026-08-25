# -*- coding: utf-8 -*-
"""v2.3 异常处理系统 — 完整测试报告生成器

运行方式:
  python tests/generate_test_report.py
"""
import sys
import unittest
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r"D:\trae")

# 导入所有测试套件
from tests.test_v23_errors import (
    TestMathaError, TestStageErrors, TestErrorChain,
    TestRecoveryStrategy, TestEnhancedParser,
    TestMapErrors, TestIntentParseContext, TestExplainIntentSafe,
)
from tests.test_v22_core import (
    TestCoreStdlib, TestResult, TestOption,
    TestIntentParser, TestMathaType,
)


def run_tests():
    """运行所有测试并生成报告。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试套件
    test_classes = [
        TestMathaError, TestStageErrors, TestErrorChain,
        TestRecoveryStrategy, TestEnhancedParser,
        TestMapErrors, TestIntentParseContext, TestExplainIntentSafe,
        TestCoreStdlib, TestResult, TestOption,
        TestIntentParser, TestMathaType,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=1)
    start = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - start

    return result, elapsed


def generate_report(result, elapsed: float) -> str:
    """生成 Markdown 测试报告。"""
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    lines = [
        "# Matha v2.3 异常处理系统 — 测试报告",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 运行耗时: {elapsed:.3f}s",
        "",
        "## 测试统计",
        "",
        "| 指标 | 数量 |",
        "|---|---|",
        f"| 总用例数 | {total} |",
        f"| 通过 | {passed} |",
        f"| 失败 | {failures} |",
        f"| 错误 | {errors} |",
        f"| 通过率 | {passed/total*100:.1f}% |",
        "",
    ]

    if failures:
        lines.append("## 失败用例")
        lines.append("")
        for test, trace in result.failures:
            lines.append(f"### {test}")
            lines.append("```")
            lines.append(trace)
            lines.append("```")
            lines.append("")

    if errors:
        lines.append("## 错误用例")
        lines.append("")
        for test, trace in result.errors:
            lines.append(f"### {test}")
            lines.append("```")
            lines.append(trace)
            lines.append("```")
            lines.append("")

    # 按类别统计
    lines.append("## 分模块统计")
    lines.append("")
    lines.append("| 模块 | 用例数 | 通过 | 失败 | 错误 |")
    lines.append("|---|---|---|---|---|")

    modules = {
        "ParseError": (TestMathaError, TestStageErrors),
        "ClassifyError": (TestStageErrors,),
        "ParamExtractError": (TestStageErrors,),
        "CodeGenError": (TestStageErrors,),
        "ExecError": (TestStageErrors,),
        "CompositeError": (TestStageErrors, TestErrorChain),
        "RecoveryStrategies": (TestRecoveryStrategy,),
        "map_errors": (TestMapErrors,),
        "ErrorChain": (TestErrorChain,),
        "ErrorAggregator": (TestErrorAggregator,),
        "EnhancedParser": (TestEnhancedParser,),
        "REPL_Context": (TestIntentParseContext, TestExplainIntentSafe),
        "v2.2 回归": (TestCoreStdlib, TestResult, TestOption, TestIntentParser, TestMathaType),
    }

    for module_name, classes in modules.items():
        mod_total = mod_passed = mod_failures = mod_errors = 0
        for cls in classes:
            for test in loader.loadTestsFromTestCase(cls):
                mod_total += 1
                # 检查是否在 failures/errors 中
                test_id = str(test)
                is_fail = any(test_id in str(f) for f, _ in result.failures)
                is_error = any(test_id in str(e) for e, _ in result.errors)
                if is_fail:
                    mod_failures += 1
                elif is_error:
                    mod_errors += 1
                else:
                    mod_passed += 1
        lines.append(f"| {module_name} | {mod_total} | {mod_passed} | {mod_failures} | {mod_errors} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    if failures == 0 and errors == 0:
        lines.append("## ✅ 全部测试通过！")
    else:
        lines.append(f"## ⚠️ 存在 {failures} 个失败，{errors} 个错误")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    result, elapsed = run_tests()
    report = generate_report(result, elapsed)

    # 输出到文件
    output_path = Path(r"D:\trae\release\v2.0.0\docs\v2.3_test_report.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"报告已生成: {output_path}")
    print(f"总用例: {result.testsRun}, 通过: {result.testsRun - len(result.failures) - len(result.errors)}, "
          f"失败: {len(result.failures)}, 错误: {len(result.errors)}")
