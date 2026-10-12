"""Matha 测试框架：单元测试、集成测试、测试覆盖率。"""
from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestStatus(Enum):
    """测试状态。"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class TestCase:
    """测试用例。"""
    name: str
    func: Callable
    tags: list[str] = field(default_factory=list)
    timeout: float = 30.0
    skip: bool = False


@dataclass
class TestResult:
    """测试结果。"""
    name: str
    status: TestStatus
    duration: float = 0.0
    error: str | None = None
    output: Any = None


@dataclass
class TestSuite:
    """测试套件。"""
    name: str
    tests: list[TestCase] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class MathaTestRunner:
    """Matha 测试运行器。"""

    def __init__(self):
        self._suites: list[TestSuite] = []
        self._current_suite: TestSuite | None = None
        self._initialized = False
        self._init_test_runner()

    def _init_test_runner(self) -> None:
        """初始化测试运行器。"""
        self._initialized = True

    def suite(self, name: str) -> TestSuite:
        """创建测试套件。"""
        suite = TestSuite(name=name)
        self._suites.append(suite)
        self._current_suite = suite
        return suite

    def test(self, name: str, func: Callable = None,
                tags: list[str] | None = None,
                skip: bool = False
                ) -> Callable:
        """添加测试用例（装饰器）。"""
        def decorator(f: Callable) -> Callable:
            t = TestCase(name=name, func=f, tags=tags or [], skip=skip)
            if self._current_suite:
                self._current_suite.tests.append(t)
            return f
        if func:
            return decorator(func)
        return decorator

    def run(self, suite_name: str | None = None
                ) -> tuple[int, int]:
        """运行测试套件。"""
        suites = [s for s in self._suites
                   if suite_name is None or s.name == suite_name]
        total_passed = 0
        total_failed = 0
        for suite in suites:
            self._run_suite(suite)
            total_passed += suite.passed
            total_failed += suite.failed
        return total_passed, total_failed

    def _run_suite(self, suite: TestSuite) -> None:
        """运行测试套件。"""
        for test_case in suite.tests:
            if test_case.skip:
                suite.skipped += 1
                continue
            start = time.perf_counter()
            try:
                result = test_case.func()
                duration = time.perf_counter() - start
                suite.results.append(TestResult(
                    name=test_case.name, status=TestStatus.PASS,
                    duration=duration, output=result
                ))
                suite.passed += 1
            except Exception:
                duration = time.perf_counter() - start
                error = traceback.format_exc()
                suite.results.append(TestResult(
                    name=test_case.name, status=TestStatus.FAIL,
                    duration=duration, error=error
                ))
                suite.failed += 1

    def assert_equal(self, a: Any, b: Any, msg: str = "") -> None:
        """断言相等。"""
        if a != b:
            raise AssertionError(msg or f"{a} != {b}")

    def assert_true(self, condition: bool,
                       msg: str = "") -> None:
        """断言为真。"""
        if not condition:
            raise AssertionError(msg or "期望 True, 实际 False")

    def assert_false(self, condition: bool,
                        msg: str = "") -> None:
        """断言为假。"""
        if condition:
            raise AssertionError(msg or "期望 False, 实际 True")

    def assert_raises(self, exc_type: type, func: Callable,
                         *args: Any, **kwargs: Any) -> None:
        """断言抛出异常。"""
        try:
            func(*args, **kwargs)
            raise AssertionError(f"期望 {exc_type.__name__} 但未抛出")
        except exc_type:
            pass

    def get_stats(self) -> dict:
        """获取统计信息。"""
        total_passed = sum(s.passed for s in self._suites)
        total_failed = sum(s.failed for s in self._suites)
        total_skipped = sum(s.skipped for s in self._suites)
        return {
            "initialized": self._initialized,
            "suites": len(self._suites),
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
        }


# ============================================================
# 内置注册
# ============================================================

def create_test_runner() -> MathaTestRunner:
    """创建测试运行器。"""
    return MathaTestRunner()


def assert_equal(a: Any, b: Any, msg: str = "") -> None:
    """断言相等。"""
    if a != b:
        raise AssertionError(msg or f"{a} != {b}")


def assert_true(condition: bool, msg: str = "") -> None:
    """断言为真。"""
    if not condition:
        raise AssertionError(msg or "期望 True")


def assert_false(condition: bool, msg: str = "") -> None:
    """断言为假。"""
    if condition:
        raise AssertionError(msg or "期望 False")


def _register_test_framework(builtins: dict) -> None:
    """注册测试框架内置函数。"""
    builtins["创建测试运行器"] = create_test_runner
    builtins["断言相等"] = assert_equal
    builtins["断言为真"] = assert_true
    builtins["断言为假"] = assert_false


def _test_framework_symtab_names() -> list[str]:
    return [
        "创建测试运行器", "断言相等", "断言为真", "断言为假",
    ]


__all__ = [
    "TestStatus", "TestCase", "TestResult", "TestSuite",
    "MathaTestRunner",
    "create_test_runner", "assert_equal", "assert_true", "assert_false",
    "_register_test_framework", "_test_framework_symtab_names",
]
