# -*- coding: utf-8 -*-
"""Matha 自成长引擎 v2.3 — 主入口

启动方式:
    python main.py              # 启动 REPL
    python main.py --test       # 运行全量测试
    python main.py --demo       # 运行演示
    python main.py --benchmark  # 性能基准测试
"""
from __future__ import annotations
import sys
import os
import argparse
import time

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.repl_v23 import run_repl
from src.stdlib.core import register_core_builtins
from src.result import Ok, Err
from src.enhanced_intent import parse_intent_safe, execute_intent
from src.intent_parser import IntentType


def run_demo() -> None:
    """运行 v2.3 功能演示。"""
    print("=" * 60)
    print("  Matha v2.3 异常处理系统演示")
    print("=" * 60)
    print()

    # 1. 标准库演示
    print("【1. 标准库 Core】")
    builtins = {}
    register_core_builtins(builtins)
    print(f"  IntMax(3, 7) = {builtins['IntMax'](3, 7)}")
    print(f"  StrReverse('hello') = {builtins['StrReverse']('hello')}")
    print(f"  ArraySort([3,1,2]) = {builtins['ArraySort']([3,1,2])}")
    print()

    # 2. Result 类型演示
    print("【2. Result 类型】")
    from src.result import Ok, Err, result
    r = result(lambda: 1 / 0)
    print(f"  result(1/0) = {type(r).__name__}: {str(r)[:60]}...")
    r2 = result(lambda: 42)
    print(f"  result(42) = {type(r2).__name__}: {r2.unwrap()}")
    print()

    # 3. 意图解析演示
    print("【3. 意图解析 + 异常处理】")
    cases = [
        ("计算 3 加 5", "成功"),
        ("对数组 [3,1,2] 排序", "成功"),
        ("xyz abc notreal", "分类失败"),
        ("求正弦值", "参数警告"),
    ]
    for text, desc in cases:
        result = parse_intent_safe(text)
        if result.is_ok():
            intent = result.unwrap()
            print(f"  [{desc}] {text!r} → {intent.intent_type.name} (conf={intent.confidence:.0%})")
            if intent.suggested_code:
                exec_result = execute_intent(text)
                if exec_result.is_ok():
                    print(f"    执行结果: {exec_result.unwrap()}")
        else:
            error = result.err()
            print(f"  [{desc}] {text!r} → {error.stage.name}: {error.message[:30]}...")
            print(f"    建议: {error.suggestions[0] if error.suggestions else '无'}")
    print()

    # 4. 错误报告演示
    print("【4. 结构化错误报告】")
    from src.errors import parse_error, classify_error, CompositeError
    err1 = parse_error("expected =", line=5, col=10)
    err2 = classify_error("unknown intent", candidates=["算术", "字符串"])
    composite = CompositeError("多步失败", [err1, err2])
    print(composite.report())
    print()
    print(composite.suggestions_text())
    print()


def run_tests() -> None:
    """运行全量测试。"""
    import unittest
    test_modules = [
        "tests.test_v23_comprehensive",
        "tests.test_v23_errors",
        "tests.test_v22_core",
        "tests.test_parser_boundaries",
        "tests.test_mir_generator",
        "tests.test_code_generator",
        "tests.test_mir_optimization",
        "tests.test_growth",
        "tests.test_domains",
        "tests.test_vm",
        "tests.test_superior_architecture",
        "tests.test_multi_lang_frontend",
        "tests.test_hardware_domain",
    ]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for mod in test_modules:
        suite.addTests(loader.discover("tests", pattern=f"test_*.py", top_level_dir="."))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Matha 自成长引擎 v2.3")
    parser.add_argument("--test", action="store_true", help="运行全量测试")
    parser.add_argument("--demo", action="store_true", help="运行功能演示")
    parser.add_argument("--debug", action="store_true", help="调试模式（详细日志）")
    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.demo:
        run_demo()
    else:
        run_repl(debug=args.debug)


if __name__ == "__main__":
    main()
