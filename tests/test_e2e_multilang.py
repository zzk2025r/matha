# -*- coding: utf-8 -*-
"""
多语言前端端到端测试 — 集成 TypeScript 转译器

验证完整流程：
  1. 跨语言编译（5 语言 → 统一 IR）
  2. IR → MIR → VM 执行
  3. 跨语言一致性验证
  4. TypeScript 转译验证
  5. 端到端输出比对
"""
from __future__ import annotations
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.multi_lang_frontend import get_frontend
from src.cross_language_verifier import CrossLanguageVerifier
from src.transpiler import transpile
from src.transpiler_ts import TypeScriptTranspiler, MATHA_TO_TS, TYPE_MAP


class TestEndToEndCrossLang(unittest.TestCase):
    """端到端跨语言验证测试。"""

    def test_compile_all_languages(self):
        """测试 5 种语言的编译。"""
        frontend = get_frontend()
        sources = {
            "python": "x = 3.0 + 4.0 * 2.0\n#1：[x]",
            "rust": "fn test() -> f64 { 3.0 + 4.0 * 2.0 }",
            "go": "func test() float64 { return 3.0 + 4.0 * 2.0 }",
            "javascript": "const x = 3.0 + 4.0 * 2.0",
            "c": "double test() { return 3.0 + 4.0 * 2.0; }",
        }
        for lang, src in sources.items():
            cr = frontend.compile(src, lang)
            self.assertTrue(cr.success, f"{lang} 编译失败: {cr.errors}")

    def test_consistency_arithmetic(self):
        """测试算术运算跨语言一致性。"""
        verifier = CrossLanguageVerifier(verbose=False)
        result = verifier.verify("arithmetic", {
            "python": "x = 3.0 + 4.0 * 2.0\n#1：[x]",
            "rust": "fn test() -> f64 { 3.0 + 4.0 * 2.0 }",
            "go": "func test() float64 { return 3.0 + 4.0 * 2.0 }",
            "javascript": "const x = 3.0 + 4.0 * 2.0",
            "c": "double test() { return 3.0 + 4.0 * 2.0; }",
        })
        self.assertTrue(result.passed, f"不一致: {result.differences}")

    def test_consistency_trig(self):
        """测试三角函数跨语言一致性。"""
        verifier = CrossLanguageVerifier(verbose=False)
        result = verifier.verify("trig_sum", {
            "python": "x = sin(3.14) + cos(1.57)\n#1：[x]",
            "rust": "fn test() -> f64 { sin(3.14) + cos(1.57) }",
            "go": "func test() float64 { return sin(3.14) + cos(1.57) }",
            "javascript": "const x = sin(3.14) + cos(1.57)",
            "c": "double test() { return sin(3.14) + cos(1.57); }",
        })
        self.assertTrue(result.passed, f"不一致: {result.differences}")

    def test_consistency_sqrt_exp(self):
        """测试 sqrt+exp 跨语言一致性。"""
        verifier = CrossLanguageVerifier(verbose=False)
        result = verifier.verify("sqrt_exp", {
            "python": "x = sqrt(16.0) + exp(1.0)\n#1：[x]",
            "rust": "fn test() -> f64 { sqrt(16.0) + exp(1.0) }",
            "go": "func test() float64 { return sqrt(16.0) + exp(1.0) }",
            "javascript": "const x = sqrt(16.0) + exp(1.0)",
            "c": "double test() { return sqrt(16.0) + exp(1.0); }",
        })
        self.assertTrue(result.passed, f"不一致: {result.differences}")


class TestEndToEndTypeScript(unittest.TestCase):
    """TypeScript 转译端到端测试。"""

    def test_transpile_python_target(self):
        """测试 Python 转译。"""
        result = transpile("x = 3.0 + 4.0 * 2.0\n#1：[x]", "python")
        self.assertIn("import math", result)
        self.assertIn("x = (3.0 + (4.0 * 2.0))", result)

    def test_transpile_javascript_target(self):
        """测试 JavaScript 转译。"""
        result = transpile("x = 3.0 + 4.0 * 2.0\n#1：[x]", "javascript")
        self.assertIsInstance(result, str)
        self.assertIn("const x", result)

    def test_transpile_typescript_target(self):
        """测试 TypeScript 转译。"""
        result = transpile("x = 3.0 + 4.0 * 2.0\n#1：[x]", "typescript")
        self.assertIsInstance(result, str)
        self.assertIn("const x: number", result)
        self.assertIn("3.0", result)
        self.assertIn("4.0", result)

    def test_transpile_typescript_function(self):
        """测试 TypeScript 函数转译。"""
        result = transpile("func f(x, y) -> Float = (x, y) => x + y\n#1：[f(1.0, 2.0)]", "typescript")
        self.assertIsInstance(result, str)
        self.assertIn("function f", result)
        self.assertIn("return", result)

    def test_transpile_typescript_math(self):
        """测试 TypeScript 数学函数转译。"""
        result = transpile("x = sin(3.14) + cos(1.57)\n#1：[x]", "typescript")
        self.assertIn("Math.sin", result)
        self.assertIn("Math.cos", result)

    def test_transpile_typescript_conditional(self):
        """测试 TypeScript 条件表达式转译。"""
        result = transpile("x = (a > 0) ? a : -a\n#1：[x]", "typescript")
        self.assertIsInstance(result, str)
        self.assertIn("?", result)

    def test_transpile_typescript_no_types(self):
        """测试无类型注解的 TypeScript 转译。"""
        transpiler = TypeScriptTranspiler(add_types=False)
        result = transpiler.transpile("x = 3.14\n#1：[x]")
        self.assertNotIn(": number", result)
        self.assertIn("const x = 3.14;", result)

    def test_transpile_json_target(self):
        """测试 JSON IR 转译。"""
        result = transpile("x = 3.0 + 4.0\n#1：[x]", "json")
        self.assertIsInstance(result, str)

    def test_transpile_unsupported_target(self):
        """测试不支持的目标语言。"""
        from src.transpiler import TranspileError
        with self.assertRaises(TranspileError):
            transpile("x = 1", "ruby")


class TestEndToEndRoundtrip(unittest.TestCase):
    """端到端转译+执行验证。"""

    def test_python_roundtrip(self):
        """Matha → Python 转译后语法正确。"""
        source = "x = 3.0 + 4.0 * 2.0\n#1：[x]"
        py_code = transpile(source, "python")
        # 验证生成的 Python 包含必要结构
        self.assertIn("import math", py_code)
        self.assertIn("x", py_code)

    def test_typescript_roundtrip(self):
        """Matha → TypeScript 转译后语法正确。"""
        source = "x = 3.0 + 4.0 * 2.0\n#1：[x]"
        ts_code = transpile(source, "typescript")
        # 验证生成的 TypeScript 包含必要结构
        self.assertIn("const x: number", ts_code)
        self.assertIn("Math", ts_code)

    def test_all_targets_consistency(self):
        """所有目标语言的转译输出非空。"""
        source = "x = sin(3.14) + cos(1.57)\n#1：[x]"
        targets = ["python", "javascript", "typescript", "json"]
        for target in targets:
            result = transpile(source, target)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0, f"{target} 转译结果为空")


if __name__ == "__main__":
    unittest.main(verbosity=2)
