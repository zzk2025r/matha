# -*- coding: utf-8 -*-
"""Matha REPL 语法高亮测试"""
import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from repl_highlight import SyntaxHighlighter, highlight_syntax


class TestSyntaxHighlighter(unittest.TestCase):
    """测试语法高亮器"""

    def setUp(self):
        """设置测试环境"""
        self.hl = SyntaxHighlighter(enabled=True)

    def test_highlight_keywords(self):
        """测试关键字高亮"""
        text = "if x > 0: return True"
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_numbers(self):
        """测试数字高亮"""
        text = "x = 3.14"
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_strings(self):
        """测试字符串高亮"""
        text = 'print("hello")'
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_comments(self):
        """测试注释高亮"""
        text = "# 这是一个注释"
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_functions(self):
        """测试函数高亮"""
        text = "matrix_multiply(A, B)"
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_operators(self):
        """测试运算符高亮"""
        text = "x + y - z"
        result = self.hl.highlight(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_disabled_highlight(self):
        """测试禁用高亮"""
        hl = SyntaxHighlighter(enabled=False)
        text = "if x > 0: return True"
        result = hl.highlight(text)
        # 禁用时应该原样返回
        self.assertEqual(result, text)

    def test_empty_text(self):
        """测试空文本"""
        result = self.hl.highlight("")
        self.assertEqual(result, "")

    def test_no_color_output(self):
        """测试输出不包含非法颜色码"""
        text = "x = 1"
        result = self.hl.highlight(text)
        # 应该只包含有效的 ANSI 颜色码
        import re
        color_codes = re.findall(r'\033\[\d+m', result)
        for code in color_codes:
            self.assertTrue(code in [
                '\033[0m', '\033[1m', '\033[2m',
                '\033[30m', '\033[31m', '\033[32m', '\033[33m',
                '\033[34m', '\033[35m', '\033[36m', '\033[37m',
            ])


class TestHighlightFunctions(unittest.TestCase):
    """测试高亮函数"""

    def test_highlight_syntax_function(self):
        """测试 highlight_syntax 函数"""
        text = "x = 3.14"
        result = highlight_syntax(text)
        # 只要输出不等于输入就说明有处理
        self.assertNotEqual(result, text)

    def test_highlight_syntax_disabled(self):
        """测试禁用高亮"""
        text = "x = 3.14"
        result = highlight_syntax(text, enabled=False)
        # 禁用时应该原样返回
        self.assertEqual(result, text)


if __name__ == '__main__':
    unittest.main()
