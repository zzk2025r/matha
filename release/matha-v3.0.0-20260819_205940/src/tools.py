# -*- coding: utf-8 -*-
"""Matha 工程工具：格式化器、Linter、测试框架 stub。"""

from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
# 代码格式化器（类 black）
# ============================================================

@dataclass
class FormatConfig:
    line_length: int = 100
    indent: str = "  "  # 2空格缩进
    max_blank_lines: int = 2


class MathaFormatter:
    """Matha 代码格式化器。"""

    def __init__(self, config: FormatConfig = None) -> None:
        self._config = config or FormatConfig()

    def format(self, source: str) -> str:
        """格式化 Matha 源码。"""
        lines = source.split("\n")
        formatted = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("(*"):
                formatted.append(line)
                continue

            # 检测缩进变化
            if stripped.endswith("{"):
                formatted.append(self._config.indent * indent_level + stripped)
                indent_level += 1
                continue
            if stripped.endswith("}"):
                indent_level = max(0, indent_level - 1)
                formatted.append(self._config.indent * indent_level + stripped)
                continue

            # 普通行
            formatted.append(self._config.indent * indent_level + stripped)

        return "\n".join(formatted)

    def check_format(self, source: str) -> list[str]:
        """检查代码格式问题。"""
        issues = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            if "\t" in line:
                issues.append(f"L{i}: 使用制表符，应改为空格")
            if len(line) > self._config.line_length:
                issues.append(f"L{i}: 行过长 ({len(line)} > {self._config.line_length})")
        return issues


# ============================================================
# Linter（类 mypy/flake8）
# ============================================================

@dataclass
class LintIssue:
    line: int
    col: int
    code: str
    message: str
    severity: str = "error"


class MathaLinter:
    """Matha 代码检查器。"""

    RULES = {
        "M001": (r"\bundefined\b", "未定义变量"),
        "M002": (r"\bNone\b\s*\+\s*", "None 参与算术运算"),
        "M003": (r"if\s+\w+\s*==\s*True", "冗余 True 比较"),
        "M004": (r"len\(\w+\)\s*==\s*0", "应使用 not lst"),
        "M005": (r"\bnot\s+\w+\s+is\s+None", "应使用 is not"),
    }

    def __init__(self) -> None:
        self._compiled_rules: dict[str, tuple] = {
            code: (re.compile(pattern, re.IGNORECASE), msg)
            for code, (pattern, msg) in self.RULES.items()
        }

    def lint(self, source: str) -> list[LintIssue]:
        """对源码执行 lint 检查。"""
        issues = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            for code, (pattern, msg) in self._compiled_rules.items():
                match = pattern.search(line)
                if match:
                    issues.append(LintIssue(
                        line=i, col=match.start() + 1,
                        code=code, message=f"{code}: {msg}",
                    ))
        return issues

    def get_summary(self, issues: list[LintIssue]) -> str:
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        return f"{len(errors)} 错误, {len(warnings)} 警告"


# ============================================================
# 测试框架 stub
# ============================================================

class MathaTestCase:
    """Matha 测试用例基类。"""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._results: list[dict] = []

    def assert_equal(self, actual: Any, expected: Any, msg: str = "") -> bool:
        ok = actual == expected
        self._results.append({"test": self.name, "ok": ok, "msg": msg})
        if not ok:
            print(f"  FAIL {self.name}: {actual!r} != {expected!r} {msg}")
        return ok

    def assert_true(self, value: Any, msg: str = "") -> bool:
        return self.assert_equal(bool(value), True, msg)

    def assert_raises(self, exc_type: type, fn: callable, *args, **kwargs) -> bool:
        try:
            fn(*args, **kwargs)
            self._results.append({"test": self.name, "ok": False, "msg": "未抛出异常"})
            return False
        except exc_type:
            self._results.append({"test": self.name, "ok": True, "msg": ""})
            return True
        except Exception as e:
            self._results.append({"test": self.name, "ok": False, "msg": f"抛出 {type(e).__name__}: {e}"})
            return False

    def run_all(self) -> dict:
        total = len(self._results)
        passed = sum(1 for r in self._results if r["ok"])
        return {"total": total, "passed": passed, "failed": total - passed}


def test(name: str, fn: callable) -> MathaTestCase:
    """创建并运行测试用例。"""
    tc = MathaTestCase(name)
    fn(tc)
    result = tc.run_all()
    return tc


def run_tests(test_cases: list[MathaTestCase]) -> dict:
    """运行所有测试用例。"""
    all_results = []
    for tc in test_cases:
        all_results.extend(tc._results)
    total = len(all_results)
    passed = sum(1 for r in all_results if r["ok"])
    return {"total": total, "passed": passed, "failed": total - passed}


# ============================================================
# 性能 Profiler
# ============================================================

class MathaProfiler:
    """Matha 性能分析器。"""

    def __init__(self) -> None:
        self._calls: dict[str, list[float]] = {}
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def profile_call(self, name: str, fn: callable, *args, **kwargs) -> Any:
        if not self._enabled:
            return fn(*args, **kwargs)
        start = __import__("time").perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (__import__("time").perf_counter() - start) * 1000
        if name not in self._calls:
            self._calls[name] = []
        self._calls[name].append(elapsed)
        return result

    def report(self) -> str:
        lines = ["性能分析:", "-" * 40]
        for name, times in sorted(self._calls.items(), key=lambda x: -sum(x[1])/len(x[1])):
            avg = sum(times) / len(times)
            total = sum(times)
            lines.append(f"  {name}: avg={avg:.2f}ms, total={total:.1f}ms, calls={len(times)}")
        return "\n".join(lines)


# ============================================================
# REPL 交互环境 stub
# ============================================================

class MathaREPL:
    """Matha REPL 交互环境。"""

    def __init__(self) -> None:
        self._history: list[str] = []
        self._namespace: dict = {}

    def run(self, code: str) -> Any:
        """执行单行代码。"""
        self._history.append(code)
        try:
            # 简化：直接 eval
            return eval(code, {"__builtins__": __builtins__}, self._namespace)  # noqa: S307
        except Exception as e:
            return f"Error: {e}"

    def history(self, n: int = 10) -> list[str]:
        return self._history[-n:]

    def clear(self) -> None:
        self._history.clear()
        self._namespace.clear()


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "FormatConfig", "MathaFormatter",
    "LintIssue", "MathaLinter",
    "MathaTestCase", "test", "run_tests",
    "MathaProfiler",
    "MathaREPL",
]
