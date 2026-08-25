# -*- coding: utf-8 -*-
"""Matha 多行输入支持测试"""
import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from repl import MathaREPL, REPLState


class TestMultiLineInput(unittest.TestCase):
    """测试多行输入支持"""

    def setUp(self):
        """设置测试环境"""
        self.repl = MathaREPL(debug=False)

    def test_needs_continuation_open_paren(self):
        """测试未闭合括号"""
        self.assertTrue(self.repl._needs_continuation("x = (1 + 2"))

    def test_needs_continuation_open_bracket(self):
        """测试未闭合方括号"""
        self.assertTrue(self.repl._needs_continuation("x = [1, 2, 3"))

    def test_needs_continuation_open_brace(self):
        """测试未闭合花括号"""
        self.assertTrue(self.repl._needs_continuation("x = {1: 2"))

    def test_needs_continuation_colon(self):
        """测试冒号结尾"""
        self.assertTrue(self.repl._needs_continuation("if x > 0:"))

    def test_needs_continuation_comma(self):
        """测试逗号结尾"""
        self.assertTrue(self.repl._needs_continuation("func(a, b,"))

    def test_needs_continuation_def(self):
        """测试 def 语句"""
        self.assertTrue(self.repl._needs_continuation("def my_func(x):"))

    def test_needs_continuation_for(self):
        """测试 for 语句"""
        self.assertTrue(self.repl._needs_continuation("for i in range(10):"))

    def test_needs_continuation_if(self):
        """测试 if 语句"""
        self.assertTrue(self.repl._needs_continuation("if x > 0:"))

    def test_needs_continuation_class(self):
        """测试 class 语句"""
        self.assertTrue(self.repl._needs_continuation("class MyClass:"))

    def test_needs_continuation_try(self):
        """测试 try 语句"""
        self.assertTrue(self.repl._needs_continuation("try:"))

    def test_no_continuation_complete(self):
        """测试完整表达式"""
        self.assertFalse(self.repl._needs_continuation("x = 1 + 2"))

    def test_no_continuation_complete_func(self):
        """测试完整函数定义"""
        code = "def foo(x):\n    return x + 1"
        self.assertFalse(self.repl._needs_continuation(code))

    def test_no_continuation_complete_if(self):
        """测试完整 if 语句"""
        code = "if x > 0:\n    y = 1"
        self.assertFalse(self.repl._needs_continuation(code))

    def test_no_continuation_empty(self):
        """测试空输入"""
        self.assertFalse(self.repl._needs_continuation(""))

    def test_no_continuation_comment(self):
        """测试注释行"""
        self.assertFalse(self.repl._needs_continuation("# 这是一个注释"))

    def test_multi_line_function(self):
        """测试多行函数定义"""
        code = "def add(a, b):\n    return a + b"
        lines = code.split('\n')
        # 第一行需要继续
        self.assertTrue(self.repl._needs_continuation(lines[0]))
        # 完整代码不需要继续
        self.assertFalse(self.repl._needs_continuation(code))

    def test_multi_line_class(self):
        """测试多行类定义"""
        code = "class MyList:\n    def __init__(self):\n        self.data = []"
        lines = code.split('\n')
        self.assertTrue(self.repl._needs_continuation(lines[0]))
        self.assertFalse(self.repl._needs_continuation(code))


class TestREPLState(unittest.TestCase):
    """测试 REPL 状态"""

    def test_default_state(self):
        """测试默认状态"""
        state = REPLState()
        self.assertEqual(state.mode, "matha")
        self.assertTrue(state.continue_loop)
        self.assertEqual(state.error_count, 0)
        self.assertEqual(state.success_count, 0)


if __name__ == '__main__':
    unittest.main()
