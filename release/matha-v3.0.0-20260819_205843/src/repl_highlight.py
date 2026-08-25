# -*- coding: utf-8 -*-
"""Matha REPL 语法高亮模块

提供终端语法高亮功能：
  - 关键词着色（蓝色）
  - 字符串着色（绿色）
  - 注释着色（灰色）
  - 数字着色（黄色）
  - 函数调用着色（青色）
  - 运算符着色（红色）

使用方式：
  from src.repl_highlight import highlight_syntax
  highlighted = highlight_syntax("x = 3.14  # 设置值")
"""
from __future__ import annotations
import re
from typing import Optional


class SyntaxHighlighter:
    """语法高亮器"""

    # ANSI 颜色代码
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Matha 关键字
    KEYWORDS = {
        "if", "elif", "else", "for", "while", "return", "break", "continue",
        "def", "lambda", "func", "class", "self",
        "try", "except", "finally", "raise", "throw",
        "import", "from", "as", "include",
        "true", "false", "null", "none",
        "let", "var", "const", "in", "not", "and", "or", "is",
    }

    # Matha 内置函数
    BUILTIN_FUNCTIONS = {
        "print", "input", "len", "abs", "min", "max", "sum", "range",
        "int", "float", "str", "list", "dict", "set", "tuple",
        "sin", "cos", "tan", "sqrt", "exp", "log", "pow", "floor", "ceil",
        "zeros", "ones", "eye", "random",
        "matrix_multiply", "matrix_inverse", "matrix_determinant",
        "svd_decompose", "lu_decompose", "cholesky_decompose",
        "NormalDistribution", "PoissonDistribution", "ExponentialDistribution",
        "UniformDistribution", "linear_regression",
    }

    def __init__(self, enabled: bool = True):
        """
        初始化语法高亮器

        Args:
            enabled: 是否启用高亮
        """
        self.enabled = enabled
        self._supports_color = self._check_color_support()

    def _check_color_support(self) -> bool:
        """检查终端是否支持颜色"""
        import os
        # 检查 TERM 环境变量
        term = os.environ.get('TERM', '')
        if term in ('dumb', 'unknown', ''):
            return True  # Windows 默认启用
        # Windows 10+ 支持 ANSI
        if os.name == 'nt':
            return True  # 默认启用
        return True

    def highlight(self, text: str) -> str:
        """
        对输入文本进行语法高亮

        Args:
            text: 原始文本

        Returns:
            高亮后的文本
        """
        if not self.enabled or not self._supports_color:
            return text

        # 按顺序应用高亮规则
        result = text

        # 1. 注释（灰色）
        result = self._highlight_comments(result)

        # 2. 字符串（绿色）
        result = self._highlight_strings(result)

        # 3. 数字（黄色）
        result = self._highlight_numbers(result)

        # 4. 关键字（蓝色）
        result = self._highlight_keywords(result)

        # 5. 函数调用（青色）
        result = self._highlight_functions(result)

        # 6. 运算符（红色）
        result = self._highlight_operators(result)

        return result

    def _highlight_comments(self, text: str) -> str:
        """高亮注释"""
        # 匹配 # 开头的注释
        return re.sub(
            r'(#.*)$',
            f'{self.DIM}{self.WHITE}\\1{self.RESET}',
            text,
            flags=re.MULTILINE
        )

    def _highlight_strings(self, text: str) -> str:
        """高亮字符串"""
        # 匹配单引号字符串
        text = re.sub(
            r"'(?:[^'\\]|\\.)*'",
            f'{self.GREEN}\\g<0>{self.RESET}',
            text
        )
        # 匹配双引号字符串
        text = re.sub(
            r'"(?:[^"\\]|\\.)*"',
            f'{self.GREEN}\\g<0>{self.RESET}',
            text
        )
        # 匹配三引号字符串（简化处理）
        text = re.sub(
            r'"""[^\n]*"""',
            f'{self.GREEN}\\g<0>{self.RESET}',
            text
        )
        text = re.sub(
            r"'''[^\n]*'''",
            f'{self.GREEN}\\g<0>{self.RESET}',
            text
        )
        return text

    def _highlight_numbers(self, text: str) -> str:
        """高亮数字"""
        # 匹配整数和浮点数
        return re.sub(
            r'\b(\d+\.?\d*)\b',
            f'{self.YELLOW}\\1{self.RESET}',
            text
        )

    def _highlight_keywords(self, text: str) -> str:
        """高亮关键字"""
        for keyword in self.KEYWORDS:
            text = re.sub(
                r'\b' + keyword + r'\b',
                f'{self.BLUE}{keyword}{self.RESET}',
                text
            )
        return text

    def _highlight_functions(self, text: str) -> str:
        """高亮函数调用"""
        # 匹配函数调用 pattern: func_name(
        for func in self.BUILTIN_FUNCTIONS:
            text = re.sub(
                r'\b' + func + r'\s*\(',
                f'{self.CYAN}{func}({self.RESET}',
                text
            )
        return text

    def _highlight_operators(self, text: str) -> str:
        """高亮运算符"""
        # 匹配常见运算符
        operators = ['+', '-', '*', '/', '%', '**', '=', '==', '!=', '<', '>', '<=', '>=']
        for op in operators:
            text = re.sub(
                r'(?<!\w)' + re.escape(op) + r'(?!\w)',
                f'{self.RED}{op}{self.RESET}',
                text
            )
        return text


# 全局高亮器实例
_highlighter: Optional[SyntaxHighlighter] = None


def get_highlighter() -> SyntaxHighlighter:
    """获取全局语法高亮器实例"""
    global _highlighter
    if _highlighter is None:
        _highlighter = SyntaxHighlighter()
    return _highlighter


def highlight_syntax(text: str, enabled: bool = True) -> str:
    """
    快速高亮函数

    Args:
        text: 原始文本
        enabled: 是否启用高亮

    Returns:
        高亮后的文本
    """
    hl = SyntaxHighlighter(enabled=enabled)
    return hl.highlight(text)


def demo_highlight():
    """演示语法高亮"""
    hl = SyntaxHighlighter(enabled=True)

    test_cases = [
        "x = 3.14  # 圆周率",
        "if x > 0: print('正数')",
        "result = matrix_multiply(A, B)",
        "dist = NormalDistribution(mu=0, sigma=1)",
        "for i in range(10): print(i)",
        "def calculate(x, y): return x + y",
    ]

    print("\n" + "=" * 60)
    print("  Matha 语法高亮演示")
    print("=" * 60)

    for case in test_cases:
        print(f"\n  原始: {case}")
        print(f"  高亮: {hl.highlight(case)}")

    print("\n" + "=" * 60)
    print("  演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo_highlight()
