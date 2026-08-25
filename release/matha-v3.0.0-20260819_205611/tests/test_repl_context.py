# -*- coding: utf-8 -*-
"""Matha REPL 上下文感知补全测试"""
import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from repl_completion import REPLCompleter


class TestContextAwareCompletion(unittest.TestCase):
    """测试上下文感知补全"""

    def setUp(self):
        """设置测试环境"""
        self.completer = REPLCompleter()

    def test_function_hint_matrix_multiply(self):
        """测试 matrix_multiply 函数提示"""
        hints = self.completer._get_function_hints("matrix_multiply")
        self.assertEqual(hints, ['A', 'B'])

    def test_function_hint_mean(self):
        """测试 mean 函数提示"""
        hints = self.completer._get_function_hints("mean")
        self.assertEqual(hints, ['data'])

    def test_function_hint_linear_regression(self):
        """测试 linear_regression 函数提示"""
        hints = self.completer._get_function_hints("linear_regression")
        self.assertEqual(hints, ['x', 'y'])

    def test_function_hint_unknown(self):
        """测试未知函数提示"""
        hints = self.completer._get_function_hints("unknown_function")
        self.assertEqual(hints, [])

    def test_attribute_hint_matrix(self):
        """测试矩阵属性提示"""
        hints = self.completer._get_attribute_hints("matrix", "t")
        self.assertIn("transpose", hints)

    def test_attribute_hint_distribution(self):
        """测试分布属性提示"""
        hints = self.completer._get_attribute_hints("dist", "m")
        self.assertIn("mean", hints)

    def test_context_hint_function_call(self):
        """测试函数调用上下文提示"""
        hint = self.completer.get_context_hint("matrix_multiply(")
        self.assertIn("matrix_multiply", hint)

    def test_context_hint_attribute_access(self):
        """测试属性访问上下文提示"""
        hint = self.completer.get_context_hint("matrix.")
        # 应该返回空字符串因为 matrix. 没有匹配的属性提示
        self.assertIn(hint, ["", "matrix 的属性/方法:"])

    def test_context_hint_operator(self):
        """测试运算符上下文提示"""
        hint = self.completer.get_context_hint("x + ")
        self.assertIn("操作数", hint)

    def test_context_hint_empty(self):
        """测试空输入"""
        hint = self.completer.get_context_hint("")
        self.assertEqual(hint, "")

    def test_context_hint_no_match(self):
        """测试无匹配"""
        hint = self.completer.get_context_hint("random_text")
        self.assertEqual(hint, "")


if __name__ == '__main__':
    unittest.main()
