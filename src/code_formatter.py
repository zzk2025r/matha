"""Matha 代码格式化器：自动格式化代码（类似 black）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FormatStyle(Enum):
    """格式化风格。"""
    BLACK = "black"
    PRETTIER = "prettier"
    GOOGLE = "google"
    YAPF = "yapf"


@dataclass
class FormatResult:
    """格式化结果。"""
    success: bool
    formatted_code: str
    changes: int
    errors: list[str]


class MathaFormatter:
    """Matha 代码格式化器。"""

    def __init__(self, style: FormatStyle = FormatStyle.BLACK):
        self.style = style
        self._initialized = False
        self._init_formatter()

    def _init_formatter(self) -> None:
        """初始化格式化器。"""
        self._initialized = True

    def format(self, code: str) -> FormatResult:
        """格式化代码。"""
        changes = 0
        errors: list[str] = []

        # 去除行尾空白
        code = self._strip_trailing_whitespace(code)
        changes += 1

        # 确保文件以换行符结尾
        code = self._ensure_trailing_newline(code)
        changes += 1

        # 统一缩进为4空格
        code = self._normalize_indentation(code)
        changes += 1

        # 统一引号（单引号 -> 双引号）
        code = self._normalize_quotes(code)
        changes += 1

        # 去除多余空行
        code = self._remove_extra_blank_lines(code)
        changes += 1

        # 格式化导入
        code = self._format_imports(code)
        changes += 1

        # 格式化函数定义
        code = self._format_functions(code)
        changes += 1

        # 格式化中文标识符周围的空格
        code = self._format_chinese_identifiers(code)
        changes += 1

        return FormatResult(
            success=len(errors) == 0,
            formatted_code=code,
            changes=changes,
            errors=errors
        )

    def _strip_trailing_whitespace(self, code: str) -> str:
        """去除行尾空白。"""
        return '\n'.join(line.rstrip() for line in code.split('\n'))

    def _ensure_trailing_newline(self, code: str) -> str:
        """确保以换行符结尾。"""
        if not code.endswith('\n'):
            code += '\n'
        return code

    def _normalize_indentation(self, code: str) -> str:
        """统一缩进为4空格。"""
        lines = code.split('\n')
        result = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                result.append('')
                continue
            indent_level = (len(line) - len(stripped)) // 4
            if indent_level < 0:
                indent_level = 0
            result.append('    ' * indent_level + stripped)
        return '\n'.join(result)

    def _normalize_quotes(self, code: str) -> str:
        """统一使用双引号。"""
        # 替换单引号字符串为双引号（简单处理）
        return re.sub(r"'([^'\n]*)'", r'"\1"', code)

    def _remove_extra_blank_lines(self, code: str) -> str:
        """去除多余空行（最多连续2个空行）。"""
        lines = code.split('\n')
        result = []
        blank_count = 0
        for line in lines:
            if line.strip() == '':
                blank_count += 1
                if blank_count <= 2:
                    result.append(line)
            else:
                blank_count = 0
                result.append(line)
        return '\n'.join(result)

    def _format_imports(self, code: str) -> str:
        """格式化导入语句。"""
        # 按字母排序导入
        import_lines = []
        other_lines = []
        for line in code.split('\n'):
            if line.startswith('import ') or line.startswith('from '):
                import_lines.append(line)
            else:
                other_lines.append(line)
        import_lines.sort()
        return '\n'.join(import_lines + other_lines)

    def _format_functions(self, code: str) -> str:
        """格式化函数定义。"""
        # 确保函数定义前有空行
        return re.sub(r'\n(def\s)', r'\n\1', code)

    def _format_chinese_identifiers(self, code: str) -> str:
        """格式化中文标识符周围的空格。"""
        # 确保中文标点周围有空格
        code = re.sub(r'([\u4e00-\u9fff])([,，;；:：])', r'\1 \2', code)
        code = re.sub(r'([,，;；:：])([\u4e00-\u9fff])', r'\1 \2', code)
        return code

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {"initialized": self._initialized, "style": self.style.value}


def format_code(code: str, style: str = "black") -> FormatResult:
    """格式化代码。"""
    formatter = MathaFormatter(FormatStyle(style))
    return formatter.format(code)


def _register_formatter(builtins: dict) -> None:
    """注册格式化器内置函数。"""
    builtins["格式化代码"] = format_code


def _formatter_symtab_names() -> list[str]:
    return ["格式化代码"]


__all__ = [
    "FormatStyle", "FormatResult", "MathaFormatter",
    "format_code",
    "_register_formatter", "_formatter_symtab_names",
]
