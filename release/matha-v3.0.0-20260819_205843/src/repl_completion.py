# -*- coding: utf-8 -*-
"""Matha REPL 自动补全模块

提供 Tab 键自动补全功能：
  - 变量名补全
  - 函数名补全
  - 关键字补全
  - 历史记录导航（↑↓ 键）
  - 命令补全

使用方式：
  from src.repl_completion import REPLCompleter
  completer = REPLCompleter(state)
  readline.set_completer(completer.complete)
  readline.parse_and_bind("tab: complete")
"""
from __future__ import annotations
import re
import sys
from typing import List, Optional


class REPLCompleter:
    """REPL 自动补全器"""

    # Matha 关键字
    KEYWORDS = {
        # 控制流
        "if", "elif", "else", "for", "while", "return", "break", "continue",
        # 函数定义
        "def", "lambda", "func",
        # 类定义
        "class", "self",
        # 异常处理
        "try", "except", "finally", "raise", "throw",
        # 模块
        "import", "from", "as", "include",
        # 常量
        "true", "false", "null", "none",
        # 特殊
        "let", "var", "const", "in", "not", "and", "or", "is",
        # 数学
        "print", "input", "len", "abs", "min", "max", "sum", "range",
        "int", "float", "str", "list", "dict", "set", "tuple",
    }

    # 常用内置函数
    BUILTIN_FUNCTIONS = {
        # 数学函数
        "sin", "cos", "tan", "sqrt", "exp", "log", "pow", "floor", "ceil",
        "pi", "e", "inf", "nan",
        # 矩阵运算
        "zeros", "ones", "eye", "random", "matrix_multiply", "matrix_inverse",
        "matrix_determinant", "matrix_transpose", "matrix_trace", "matrix_norm",
        "svd_decompose", "lu_decompose", "cholesky_decompose",
        # 概率统计
        "NormalDistribution", "BinomialDistribution", "PoissonDistribution",
        "ExponentialDistribution", "UniformDistribution",
        "mean", "variance", "std", "correlation",
        "z_test", "t_test", "chi_square_test",
        "linear_regression", "polynomial_regression",
        # 符号计算
        "symbolic_derivative", "symbolic_integral", "taylor_series",
        "definite_integral", "limit", "infinite_sum", "solve_ode",
        "latex_format",
    }

    def __init__(self, state=None):
        """
        初始化补全器

        Args:
            state: REPLState 对象，包含 variables 和 history
        """
        self.state = state
        self._builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
        # 过滤掉双下划线的内置对象
        self._builtins = {b for b in self._builtins if not b.startswith('__')}

    def get_all_completions(self) -> List[str]:
        """获取所有可用的补全项"""
        completions = set()

        # 添加关键字
        completions.update(self.KEYWORDS)

        # 添加内置函数
        completions.update(self.BUILTIN_FUNCTIONS)

        # 添加内置对象
        completions.update(self._builtins)

        # 添加变量（如果 state 存在）
        if self.state and hasattr(self.state, 'variables'):
            completions.update(self.state.variables.keys())

        # 添加常用命令
        completions.update({"help", "mode", "history", "clear", "quit", "exit",
                           "explain", "intent", "recover", "debug"})

        return sorted(completions)

    def complete(self, text: str, state: int = 0) -> Optional[str]:
        """
        补全函数（供 readline 使用）

        Args:
            text: 当前输入的文本
            state: 补全结果索引

        Returns:
            第 state 个补全结果，或 None
        """
        # 获取所有补全项
        completions = self._get_completions(text)

        # 返回第 state 个
        if state < len(completions):
            return completions[state]
        return None

    def _get_completions(self, text: str) -> List[str]:
        """获取匹配的补全项列表"""
        completions = self.get_all_completions()

        if not text:
            return completions

        # 处理带点号的补全（如 np.array）
        if '.' in text:
            parts = text.split('.')
            prefix = parts[0]
            suffix = parts[1] if len(parts) > 1 else ''

            # 查找变量
            if self.state and hasattr(self.state, 'variables'):
                for var_name, var_value in self.state.variables.items():
                    if var_name.startswith(prefix):
                        # 尝试获取属性的补全
                        try:
                            attrs = dir(var_value)
                            for attr in attrs:
                                if attr.startswith(suffix) and not attr.startswith('__'):
                                    completions.append(f"{var_name}.{attr}")
                        except Exception:
                            pass

            return [c for c in completions if c.startswith(text)]

        # 普通补全
        return [c for c in completions if c.startswith(text)]

    def get_hint(self, text: str) -> str:
        """
        获取补全提示

        Args:
            text: 当前输入的文本

        Returns:
            补全提示字符串
        """
        completions = self._get_completions(text)

        if not completions:
            return ""

        if len(completions) == 1:
            return completions[0]

        # 显示前 5 个匹配项
        preview = ", ".join(completions[:5])
        if len(completions) > 5:
            preview += f" ... (还有 {len(completions) - 5} 个)"
        return f"可能的补全: {preview}"

    def get_context_hint(self, text: str) -> str:
        """
        上下文感知补全提示

        根据当前输入位置提供智能建议：
        - 函数调用后提示参数
        - 属性访问后提示可用方法
        - 运算符后提示操作数

        Args:
            text: 当前输入的文本

        Returns:
            上下文提示字符串
        """
        if not text:
            return ""

        # 检测函数调用上下文
        func_match = re.search(r'(\w+)\s*\(', text)
        if func_match:
            func_name = func_match.group(1)
            hints = self._get_function_hints(func_name)
            if hints:
                return f"函数 {func_name} 参数提示: {', '.join(hints)}"

        # 检测属性访问上下文
        if '.' in text and not text.endswith('.'):
            parts = text.rsplit('.', 1)
            if len(parts) == 2:
                prefix, suffix = parts
                hints = self._get_attribute_hints(prefix, suffix)
                if hints:
                    return f"{prefix} 的属性/方法: {', '.join(hints[:5])}"

        # 检测运算符上下文
        if text.strip().endswith(('+', '-', '*', '/', '%', '**')):
            return "运算符后期待操作数"

        return ""

    def _get_function_hints(self, func_name: str) -> List[str]:
        """获取函数参数提示"""
        hints = []
        # 常见函数参数提示
        func_hints = {
            'matrix_multiply': ['A', 'B'],
            'matrix_inverse': ['A'],
            'svd_decompose': ['A'],
            'mean': ['data'],
            'variance': ['data'],
            'std': ['data'],
            'z_test': ['sample', 'population_mean'],
            't_test': ['sample'],
            'linear_regression': ['x', 'y'],
        }
        return func_hints.get(func_name, [])

    def _get_attribute_hints(self, prefix: str, suffix: str) -> List[str]:
        """获取属性提示"""
        hints = []
        # 矩阵属性
        if prefix in ('matrix', 'mat', 'A'):
            matrix_attrs = ['shape', 'data', 'transpose', 'inverse', 'determinant', 'trace']
            hints = [a for a in matrix_attrs if a.startswith(suffix)]
        # 分布属性
        elif prefix in ('dist', 'normal', 'poisson', 'exponential', 'uniform'):
            dist_attrs = ['mean', 'variance', 'std', 'pdf', 'cdf', 'ppf', 'sample']
            hints = [a for a in dist_attrs if a.startswith(suffix)]
        return hints


class REPLHistoryManager:
    """REPL 历史记录管理器"""

    def __init__(self, max_history: int = 1000):
        """
        初始化历史管理器

        Args:
            max_history: 最大历史记录数
        """
        self._history: List[str] = []
        self._max_history = max_history
        self._index = -1

    def add(self, entry: str) -> None:
        """添加历史记录"""
        if entry.strip():
            self._history.append(entry)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        self._index = len(self._history)

    def previous(self) -> Optional[str]:
        """获取上一条历史记录"""
        if self._history and self._index > 0:
            self._index -= 1
            return self._history[self._index]
        return None

    def next(self) -> Optional[str]:
        """获取下一条历史记录"""
        if self._history and self._index < len(self._history) - 1:
            self._index += 1
            return self._history[self._index]
        elif self._index >= len(self._history):
            self._index = len(self._history)
            return ""
        return None

    def current(self) -> Optional[str]:
        """获取当前历史项"""
        if self._history and 0 <= self._index < len(self._history):
            return self._history[self._index]
        return None

    def __len__(self) -> int:
        return len(self._history)

    def __iter__(self):
        return iter(self._history)


# ============================================================
# 终端颜色支持
# ============================================================

class TerminalColors:
    """终端颜色支持"""

    # ANSI 颜色代码
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

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

    @classmethod
    def colored(cls, text: str, color: str) -> str:
        """生成带颜色的文本"""
        return f"{color}{text}{cls.RESET}"

    @classmethod
    def keyword(cls, text: str) -> str:
        """关键字颜色（蓝色）"""
        return cls.colored(text, cls.BLUE)

    @classmethod
    def builtin(cls, text: str) -> str:
        """内置函数颜色（绿色）"""
        return cls.colored(text, cls.GREEN)

    @classmethod
    def variable(cls, text: str) -> str:
        """变量颜色（黄色）"""
        return cls.colored(text, cls.YELLOW)

    @classmethod
    def command(cls, text: str) -> str:
        """命令颜色（红色）"""
        return cls.colored(text, cls.RED)

    @classmethod
    def hint(cls, text: str) -> str:
        """提示颜色（灰色）"""
        return cls.colored(text, cls.WHITE)


# ============================================================
# 快速使用示例
# ============================================================

def setup_readline_completion(repl_state=None, use_colors: bool = True):
    """
    设置 readline 补全

    Args:
        repl_state: REPLState 对象
        use_colors: 是否启用颜色

    使用示例：
        from src.repl_completion import setup_readline_completion
        setup_readline_completion(repl_state)
    """
    try:
        import readline
    except ImportError:
        print("  [WARN] readline 模块不可用，自动补全功能已禁用")
        return

    completer = REPLCompleter(repl_state)
    readline.set_completer(completer.complete)
    readline.parse_and_bind("tab: complete")

    # 启用颜色（如果终端支持）
    if use_colors:
        readline.set_pre_input_hook(lambda: None)  # 预留钩子

    print("  [INFO] 自动补全已启用 (Tab 键)")
    print("  [INFO] 历史记录导航 (↑↓ 键)")


def demo_completion():
    """演示自动补全功能"""
    print("\n" + "=" * 60)
    print("  Matha REPL 自动补全演示")
    print("=" * 60)

    # 创建补全器
    completer = REPLCompleter()

    # 测试补全
    test_cases = [
        "",           # 所有补全
        "if",         # 关键字
        "sin",        # 数学函数
        "matrix_",    # 矩阵函数
        "Normal",     # 分布类
        "test_",      # 测试函数
        "x",          # 变量前缀
    ]

    for text in test_cases:
        completions = completer._get_completions(text)
        print(f"\n  补全 '{text}': {len(completions)} 个匹配")
        if completions:
            preview = ", ".join(completions[:8])
            if len(completions) > 8:
                preview += f" ... (+{len(completions) - 8})"
            print(f"    {preview}")

    print("\n" + "=" * 60)
    print("  演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo_completion()
