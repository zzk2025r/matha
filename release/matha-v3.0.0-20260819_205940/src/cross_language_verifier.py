# -*- coding: utf-8 -*-
"""
跨语言交叉验证框架

验证同一算法在不同语言前端中生成相同的 IR/MIR。

工作流程：
  1. 定义跨语言算法（Python/Rust/Go/JS/C 各一份）
  2. 各前端编译为 IR
  3. 各 IR 转换为 MIR
  4. 用 MathaVM 执行所有 MIR
  5. 对比输出结果 → 一致性验证

使用示例：
  from src.cross_language_verifier import CrossLanguageVerifier

  verifier = CrossLanguageVerifier()
  result = verifier.verify("sin(3.14) + cos(1.57)", {
      "python": "x = sin(3.14) + cos(1.57)",
      "rust": "fn main() -> f64 { sin(3.14) + cos(1.57) }",
      "go": "func main() float64 { return sin(3.14) + cos(1.57) }",
      "js": "const x = sin(3.14) + cos(1.57)",
      "c": "double main() { return sin(3.14) + cos(1.57); }",
  })
  print(result)
"""
from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.multi_lang_frontend import MultiLanguageFrontend, CompileResult, get_frontend
from src.vm import MathaVM
from src.mir import MIRProgram


# ============================================================
# 日志
# ============================================================

logger = logging.getLogger("matha.cross_verify")


# ============================================================
# 验证结果
# ============================================================

@dataclass
class LanguageResult:
    """单个语言的验证结果。"""
    language: str
    success: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ir_nodes_count: int = 0
    mir_functions: list[str] = field(default_factory=list)
    vm_outputs: list[float] = field(default_factory=list)
    vm_trace: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class CrossLanguageResult:
    """跨语言交叉验证结果。"""
    algorithm: str
    languages: dict[str, LanguageResult] = field(default_factory=dict)
    consistent: bool = True
    differences: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def passed(self) -> bool:
        all_success = all(r.success for r in self.languages.values())
        return all_success and len(self.differences) == 0


# ============================================================
# 跨语言验证器
# ============================================================

class CrossLanguageVerifier:
    """
    跨语言交叉验证器。

    功能：
    1. 编译多种语言的源码为统一 IR
    2. 将 IR 转换为 Matha MIR
    3. 用 MathaVM 执行所有 MIR
    4. 对比执行结果的一致性
    5. 报告差异和分析
    """

    def __init__(self, verbose: bool = False) -> None:
        self._frontend = get_frontend()
        self._vm = MathaVM(debug=verbose)
        self._verbose = verbose
        self._results: list[CrossLanguageResult] = []

    # ---------- 主入口 ----------

    def verify(self, algorithm: str, sources: dict[str, str]) -> CrossLanguageResult:
        """
        验证同一算法在多种语言中的执行一致性。

        Args:
            algorithm: 算法描述
            sources: {语言名: 源码}

        Returns:
            CrossLanguageResult
        """
        result = CrossLanguageResult(algorithm=algorithm)

        for lang, source in sources.items():
            lang_result = self._verify_language(lang, source)
            result.languages[lang] = lang_result
            if self._verbose:
                self._print_lang_result(lang, lang_result)

        # 对比所有成功语言的结果
        successes = {lang: r for lang, r in result.languages.items() if r.success}
        if len(successes) >= 2:
            outputs = list(successes.values())[0].vm_outputs
            for lang, lang_result in successes.items():
                if lang_result.vm_outputs != outputs:
                    result.consistent = False
                    result.differences.append(
                        f"{lang}: 输出不一致 (expected {outputs}, got {lang_result.vm_outputs})"
                    )

        result.summary = self._generate_summary(result)
        self._results.append(result)
        return result

    def batch_verify(self, test_cases: list[dict]) -> dict:
        """
        批量验证多个测试用例。

        test_cases: [
            {"algorithm": "sin_test", "sources": {"python": "...", "rust": "..."}},
            ...
        ]
        """
        results = []
        for case in test_cases:
            r = self.verify(case["algorithm"], case["sources"])
            results.append(r)

        passed = sum(1 for r in results if r.passed)
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": passed / len(results) if results else 0,
            "results": results,
        }

    # ---------- 单语言验证 ----------

    def _verify_language(self, language: str, source: str) -> LanguageResult:
        """验证单个语言的编译和执行。"""
        lang_result = LanguageResult(language=language)

        try:
            # Step 1: 编译为 IR
            compile_result = self._frontend.compile(source, language)
            if not compile_result.success:
                lang_result.errors.extend(compile_result.errors)
                return lang_result

            lang_result.ir_nodes_count = len(compile_result.ir_nodes)
            lang_result.warnings.extend(compile_result.warnings)

            # Step 2: 转换为 MIR
            mir_program = compile_result.to_mir()
            lang_result.mir_functions = list(mir_program.functions.keys())

            # Step 3: 执行 MIR
            import time
            t0 = time.perf_counter()
            outputs, trace = self._vm.run(mir_program)
            lang_result.execution_time_ms = (time.perf_counter() - t0) * 1000
            lang_result.vm_outputs = outputs
            lang_result.vm_trace = trace

            # Step 4: 检查执行错误
            if self._vm._state.error:
                lang_result.errors.append(self._vm._state.error)

        except Exception as e:
            lang_result.errors.append(f"{type(e).__name__}: {str(e)[:100]}")

        lang_result.success = len(lang_result.errors) == 0
        return lang_result

    # ---------- 报告 ----------

    def _print_lang_result(self, lang: str, result: LanguageResult) -> None:
        """打印单个语言的验证结果。"""
        status = "✓" if result.success else "✗"
        print(f"  [{status}] {lang}: "
              f"IR节点={result.ir_nodes_count}, "
              f"函数={result.mir_functions}, "
              f"输出={result.vm_outputs}, "
              f"耗时={result.execution_time_ms:.2f}ms")
        if result.errors:
            print(f"       错误: {result.errors}")
        if result.warnings:
            print(f"       警告: {result.warnings}")

    def _generate_summary(self, result: CrossLanguageResult) -> str:
        """生成验证摘要。"""
        langs = list(result.languages.keys())
        successes = [lang for lang, r in result.languages.items() if r.success]
        failures = [lang for lang, r in result.languages.items() if not r.success]

        summary = f"算法: {result.algorithm}\n"
        summary += f"语言: {', '.join(langs)}\n"
        summary += f"成功: {len(successes)}/{len(langs)} ({', '.join(successes) if successes else '无'})\n"
        if failures:
            summary += f"失败: {', '.join(failures)}\n"
        if result.differences:
            summary += f"差异:\n"
            for diff in result.differences:
                summary += f"  - {diff}\n"
        summary += f"一致性: {'✓ 通过' if result.consistent else '✗ 不通过'}"
        return summary

    def print_report(self, result: CrossLanguageResult) -> None:
        """打印完整报告。"""
        print("\n" + "=" * 60)
        print(result.summary)
        print("=" * 60)
        for lang, lang_result in result.languages.items():
            print(f"\n  [{lang}]")
            print(f"    状态: {'✓ 成功' if lang_result.success else '✗ 失败'}")
            print(f"    IR 节点数: {lang_result.ir_nodes_count}")
            print(f"    MIR 函数: {lang_result.mir_functions}")
            print(f"    VM 输出: {lang_result.vm_outputs}")
            print(f"    执行时间: {lang_result.execution_time_ms:.2f}ms")
            if lang_result.errors:
                print(f"    错误: {lang_result.errors}")
            if lang_result.warnings:
                print(f"    警告: {lang_result.warnings}")
        print()


# ============================================================
# 跨语言测试套件
# ============================================================

CROSS_LANGUAGE_TESTS = [
    {
        "algorithm": "sin_cos_sum",
        "description": "sin(π) + cos(π/2) 跨语言一致性",
        "sources": {
            "python": "x = sin(3.14159) + cos(1.5708)\n#1：[x]",
            "rust": "fn test() -> f64 { sin(3.14159) + cos(1.5708) }",
            "go": "func test() float64 { return sin(3.14159) + cos(1.5708) }",
            "js": "const x = sin(3.14159) + cos(1.5708)",
            "c": "double test() { return sin(3.14159) + cos(1.5708); }",
        },
    },
    {
        "algorithm": "arithmetic",
        "description": "基础算术运算跨语言一致性",
        "sources": {
            "python": "x = 3.0 + 4.0 * 2.0\n#1：[x]",
            "rust": "fn test() -> f64 { 3.0 + 4.0 * 2.0 }",
            "go": "func test() float64 { return 3.0 + 4.0 * 2.0 }",
            "js": "const x = 3.0 + 4.0 * 2.0",
            "c": "double test() { return 3.0 + 4.0 * 2.0; }",
        },
    },
    {
        "algorithm": "comparison",
        "description": "比较运算跨语言一致性",
        "sources": {
            "python": "x = 5.0 > 3.0\n#1：[x]",
            "rust": "fn test() -> f64 { if 5.0 > 3.0 { 1.0 } else { 0.0 } }",
            "go": "func test() float64 { if 5.0 > 3.0 { return 1.0 }; return 0.0 }",
            "js": "const x = 5.0 > 3.0",
            "c": "double test() { return 5.0 > 3.0 ? 1.0 : 0.0; }",
        },
    },
    {
        "algorithm": "sqrt_exp",
        "description": "sqrt 和 exp 跨语言一致性",
        "sources": {
            "python": "x = sqrt(16.0) + exp(1.0)\n#1：[x]",
            "rust": "fn test() -> f64 { sqrt(16.0) + exp(1.0) }",
            "go": "func test() float64 { return sqrt(16.0) + exp(1.0) }",
            "js": "const x = sqrt(16.0) + exp(1.0)",
            "c": "double test() { return sqrt(16.0) + exp(1.0); }",
        },
    },
    {
        "algorithm": "function_call",
        "description": "函数调用跨语言一致性",
        "sources": {
            "python": "f = (x) => x * 2\nx = f(5.0)\n#1：[x]",
            "rust": "fn f(x: f64) -> f64 { x * 2.0 }\nfn test() -> f64 { f(5.0) }",
            "go": "func f(x float64) float64 { return x * 2.0 }\nfunc test() float64 { return f(5.0) }",
            "js": "const f = (x) => x * 2;\nconst x = f(5.0)",
            "c": "double f(double x) { return x * 2.0; }\ndouble test() { return f(5.0); }",
        },
    },
]


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "CrossLanguageVerifier",
    "CrossLanguageResult",
    "LanguageResult",
    "CROSS_LANGUAGE_TESTS",
]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    verifier = CrossLanguageVerifier(verbose=True)
    summary = verifier.batch_verify(CROSS_LANGUAGE_TESTS)

    print("\n" + "=" * 60)
    print(f"跨语言交叉验证汇总: {summary['passed']}/{summary['total']} 通过")
    print(f"通过率: {summary['pass_rate']*100:.1f}%")
    print("=" * 60)
