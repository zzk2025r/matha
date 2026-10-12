"""Matha 完整工具链：包管理、构建、测试、调试。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PackageManager(Enum):
    PIP = "pip"
    NPM = "npm"
    CARGO = "cargo"
    APT = "apt"
    YUM = "yum"
    MATHA = "matha"


class BuildType(Enum):
    DEBUG = "debug"
    RELEASE = "release"
    MIN_SIZE = "minsize"
    RELWITHDEBINFO = "relwithdebinfo"


class TestFramework(Enum):
    PYTEST = "pytest"
    UNITTEST = "unittest"
    MATHA_TEST = "matha_test"
    DOCTEST = "doctest"


@dataclass
class Package:
    name: str
    version: str = "1.0.0"
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    license: str = "MIT"
    author: str = "Anonymous"
    repository: str = ""
    installed: bool = False


@dataclass
class Dependency:
    name: str
    version: str = ">=1.0.0"
    optional: bool = False
    platform: str | None = None


@dataclass
class BuildConfig:
    project_name: str = "MathaProject"
    build_type: BuildType = BuildType.DEBUG
    compiler: str = "gcc"
    flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    libraries: list[str] = field(default_factory=list)
    include_dirs: list[str] = field(default_factory=list)
    link_dirs: list[str] = field(default_factory=list)
    output: str = "a.out"


@dataclass
class TestResult:
    test_name: str
    passed: bool = True
    duration: float = 0.0
    error: str = ""
    assertions: int = 0
    failures: int = 0


@dataclass
class TestSuite:
    name: str = "TestSuite"
    tests: list[TestResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0


class PackageManagerWrapper:
    """包管理器。"""

    def __init__(self, pm_type: PackageManager = PackageManager.MATHA):
        self.pm_type = pm_type
        self._packages: dict[str, Package] = {}
        self._registry: dict[str, str] = {}

    def install(self, name: str,
                   version: str = "latest") -> bool:
        pkg = Package(name=name, version=version,
                       installed=True)
        self._packages[name] = pkg
        return True

    def uninstall(self, name: str) -> bool:
        if name in self._packages:
            del self._packages[name]
            return True
        return False

    def update(self, name: str) -> bool:
        if name in self._packages:
            return True
        return False

    def list_installed(self) -> list[Package]:
        return [p for p in self._packages.values() if p.installed]

    def search(self, query: str) -> list[Package]:
        return []

    def add_repository(self, url: str) -> None:
        self._registry[url] = url


class BuildTool:
    """构建工具。"""

    def __init__(self, config: BuildConfig = None):
        self.config = config or BuildConfig()
        self._targets: dict[str, str] = {}
        self._dependencies: dict[str, list[str]] = {}

    def add_target(self, name: str,
                      source: str) -> None:
        self._targets[name] = source

    def build(self, target: str = "") -> bool:
        return True

    def clean(self) -> None:
        self._targets.clear()
        self._dependencies.clear()
        self.config.sources.clear()
        self.config.libraries.clear()

    def compile(self, source: str,
                   output: str) -> bool:
        return True

    def link(self, objects: list[str],
                output: str) -> bool:
        return True

    def configure(self, build_type: BuildType) -> None:
        self.config.build_type = build_type


class TestRunner:
    """测试运行器。"""

    def __init__(self, framework: TestFramework = TestFramework.MATHA_TEST):
        self.framework = framework
        self._suites: list[TestSuite] = []
        self._results: list[TestResult] = []
        self._coverage: dict[str, float] = {}
        self._test_funcs: dict[str, callable] = {}

    def add_test(self, name: str,
                    func: callable,
                    suite: str = "default") -> None:
        suite_obj = next((s for s in self._suites if s.name == suite), None)
        if suite_obj is None:
            suite_obj = TestSuite(name=suite)
            self._suites.append(suite_obj)
        self._test_funcs[name] = func
        result = TestResult(test_name=name)
        suite_obj.tests.append(result)
        suite_obj.total += 1
        self._results.append(result)

    def run(self, suite: str = "") -> TestSuite:
        targets = [s for s in self._suites
                   if not suite or s.name == suite]
        result_suite = TestSuite(name=suite or "test_suite")
        for s in targets:
            for t in s.tests:
                func = self._test_funcs.get(t.test_name)
                result_suite.total += 1
                if func is None:
                    t.passed = False
                    t.failures += 1
                    result_suite.failed += 1
                    t.error = "未登记的测试函数"
                    continue
                start = time.perf_counter()
                try:
                    func()
                    t.passed = True
                    result_suite.passed += 1
                except Exception as exc:
                    t.passed = False
                    t.failures += 1
                    result_suite.failed += 1
                    t.error = f"{type(exc).__name__}: {exc}"
                t.duration = (time.perf_counter() - start) * 1000.0
                t.assertions = 1
        return result_suite

    def run_all(self) -> list[TestSuite]:
        return self._suites

    def get_coverage(self) -> dict[str, float]:
        return self._coverage

    def report(self) -> str:
        return "Test report"


class Debugger:
    """调试器。"""

    def __init__(self):
        self._breakpoints: dict[int, str] = {}
        self._watchpoints: dict[str, Any] = {}
        self._call_stack: list[dict[str, Any]] = []
        self._running = False
        self._step_mode = "step"

    def set_breakpoint(self, line: int,
                          condition: str = "") -> None:
        self._breakpoints[line] = condition

    def remove_breakpoint(self, line: int) -> bool:
        if line in self._breakpoints:
            del self._breakpoints[line]
            return True
        return False

    def step_over(self) -> None:
        """单步跳过：同层向前一步，不进入调用。"""
        self._running = False
        if not self._call_stack:
            self._call_stack.append({"pc": 0, "depth": 1})
        frame = self._call_stack[-1]
        frame["pc"] = frame.get("pc", 0) + 1
        self._step_mode = "over"

    def step_into(self) -> None:
        """单步进入：进入调用帧。"""
        self._running = False
        if not self._call_stack:
            self._call_stack.append({"pc": 0, "depth": 1})
        frame = self._call_stack[-1]
        frame["pc"] = frame.get("pc", 0) + 1
        self._call_stack.append({"pc": -1,
                                 "depth": frame.get("depth", 1) + 1})
        self._step_mode = "into"

    def step_out(self) -> None:
        """单步跳出：返回到调用者帧。"""
        self._running = False
        if len(self._call_stack) > 1:
            self._call_stack.pop()
        frame = self._call_stack[-1]
        frame["pc"] = frame.get("pc", 0) + 1
        self._step_mode = "out"

    def continue_execution(self) -> None:
        self._running = True

    def evaluate(self, expression: str) -> Any:
        return None

    def get_stack_trace(self) -> list[dict[str, Any]]:
        return self._call_stack


class Profiler:
    """性能分析器。"""

    def __init__(self):
        self._profile_data: dict[str, dict[str, float]] = {}
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def profile_function(self, func: callable,
                            *args, **kwargs) -> Any:
        return func(*args, **kwargs)

    def get_report(self) -> str:
        return "Profiler report"

    def flame_graph(self) -> str:
        return "Flame graph"


class Linter:
    """代码检查器。"""

    def __init__(self):
        self._rules: list[str] = []
        self._config: dict[str, Any] = {}

    def lint(self, source: str) -> list[dict[str, Any]]:
        return []

    def add_rule(self, rule: str) -> None:
        self._rules.append(rule)

    def fix(self, source: str) -> str:
        return source


class Formatter:
    """代码格式化器。"""

    def __init__(self):
        self._style = {}

    def format(self, source: str) -> str:
        return source.strip()

    def format_file(self, path: str) -> bool:
        return True


def create_package_manager(
    pm_type: PackageManager = PackageManager.MATHA
) -> PackageManagerWrapper:
    return PackageManagerWrapper(pm_type=pm_type)


def create_build_tool(config: BuildConfig = None
                          ) -> BuildTool:
    return BuildTool(config=config)


def create_test_runner(
    framework: TestFramework = TestFramework.MATHA_TEST
) -> TestRunner:
    return TestRunner(framework=framework)


def create_debugger() -> Debugger:
    return Debugger()


def create_profiler() -> Profiler:
    return Profiler()


def create_linter() -> Linter:
    return Linter()


def create_formatter() -> Formatter:
    return Formatter()


# ============================================================
# 内置注册
# ============================================================

def _register_toolchain(builtins: dict) -> None:
    builtins["创建包管理器"] = create_package_manager
    builtins["创建构建工具"] = create_build_tool
    builtins["创建测试运行器"] = create_test_runner
    builtins["创建调试器"] = create_debugger
    builtins["创建性能分析器"] = create_profiler
    builtins["创建代码检查器"] = create_linter
    builtins["创建代码格式化器"] = create_formatter


def _toolchain_names() -> list[str]:
    return ["创建包管理器", "创建构建工具",
            "创建测试运行器", "创建调试器",
            "创建性能分析器", "创建代码检查器",
            "创建代码格式化器"]


__all__ = [
    "PackageManager", "BuildType", "TestFramework",
    "Package", "Dependency", "BuildConfig",
    "TestResult", "TestSuite",
    "PackageManagerWrapper", "BuildTool",
    "TestRunner", "Debugger", "Profiler",
    "Linter", "Formatter",
    "create_package_manager", "create_build_tool",
    "create_test_runner", "create_debugger",
    "create_profiler", "create_linter",
    "create_formatter",
    "_register_toolchain", "_toolchain_names",
]
