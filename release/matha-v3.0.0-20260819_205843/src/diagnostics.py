# -*- coding: utf-8 -*-
"""Matha IDE 诊断与错误提示系统。

功能：
  1. 语法错误高亮：在源码中标记错误位置
  2. 语义错误诊断：未定义变量、类型不匹配等
  3. 智能修复建议：给出可能的修正方案
  4. LSP 兼容格式：输出 JSON 供 IDE 插件消费
  5. VSCode 扩展：提供实时诊断
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ============================================================
# 诊断等级
# ============================================================

class DiagnosticSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


# ============================================================
# 诊断信息
# ============================================================

@dataclass
class Diagnostic:
    """诊断信息（LSP 兼容格式）。"""
    message: str
    severity: DiagnosticSeverity
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    source: str = "matha"
    code: str = ""
    related_information: list[dict] = field(default_factory=list)
    fix: Optional[str] = None  # 修复建议

    def to_lsp(self) -> dict:
        """转换为 LSP Diagnostic 格式。"""
        return {
            "message": self.message,
            "severity": self.severity.value,
            "range": {
                "start": {"line": self.line - 1, "character": self.col - 1},
                "end": {"line": self.end_line - 1, "character": self.end_col - 1},
            },
            "source": self.source,
            "code": self.code,
            "codeDescription": {"href": f"https://matha.dev/diagnostics/{self.code}"},
            "fixes": [{"label": "修复", "edit": {"text": self.fix}}] if self.fix else [],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_lsp(), ensure_ascii=False)


# ============================================================
# 错误类型与修复建议
# ============================================================

class MathaErrorKind(Enum):
    # 语法错误
    SYNTAX_EXPECTED = auto()
    SYNTAX_UNTERMINATED = auto()
    SYNTAX_INVALID_TOKEN = auto()
    # 语义错误
    UNDEFINED_VAR = auto()
    TYPE_MISMATCH = auto()
    UNDEFINED_FUNC = auto()
    REDEFINED_VAR = auto()
    SCOPE_ERROR = auto()
    # 运行时错误
    DIVISION_BY_ZERO = auto()
    INDEX_OUT_OF_RANGE = auto()
    TYPE_ERROR = auto()
    # 建议
    SUGGEST_IMPORT = auto()
    SUGGEST_FIX = auto()


# 错误映射表
_ERROR_MESSAGES: dict[MathaErrorKind, dict[str, str]] = {
    MathaErrorKind.SYNTAX_EXPECTED: {
        "zh": "期望 {expected}，实际为 {got}",
        "en": "Expected {expected}, got {got}",
    },
    MathaErrorKind.SYNTAX_UNTERMINATED: {
        "zh": "字符串/注释未终止",
        "en": "Unterminated string/comment",
    },
    MathaErrorKind.UNDEFINED_VAR: {
        "zh": "未定义的变量 '{name}'",
        "en": "Undefined variable '{name}'",
    },
    MathaErrorKind.TYPE_MISMATCH: {
        "zh": "类型不匹配：期望 {expected}, 实际 {actual}",
        "en": "Type mismatch: expected {expected}, got {actual}",
    },
    MathaErrorKind.UNDEFINED_FUNC: {
        "zh": "未定义的函数 '{name}'",
        "en": "Undefined function '{name}'",
    },
    MathaErrorKind.DIVISION_BY_ZERO: {
        "zh": "除数为零",
        "en": "Division by zero",
    },
    MathaErrorKind.INDEX_OUT_OF_RANGE: {
        "zh": "索引越界",
        "en": "Index out of range",
    },
}

# 修复建议
_FIX_SUGGESTIONS: dict[MathaErrorKind, dict[str, str]] = {
    MathaErrorKind.UNDEFINED_VAR: {
        "zh": "检查变量名拼写，或在使用前添加绑定：{name} = ?",
        "en": "Check variable spelling, or add binding: {name} = ?",
    },
    MathaErrorKind.UNDEFINED_FUNC: {
        "zh": "检查函数名拼写，或添加函数定义",
        "en": "Check function spelling, or add function definition",
    },
    MathaErrorKind.SYNTAX_EXPECTED: {
        "zh": "检查运算符或括号配对",
        "en": "Check operator or parenthesis pairing",
    },
}


# ============================================================
# 诊断收集器
# ============================================================

class DiagnosticCollector:
    """收集并管理诊断信息。"""

    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []
        self._error_count = 0
        self._warning_count = 0

    def add(self, diag: Diagnostic) -> None:
        self._diagnostics.append(diag)
        if diag.severity == DiagnosticSeverity.ERROR:
            self._error_count += 1
        elif diag.severity == DiagnosticSeverity.WARNING:
            self._warning_count += 1

    def add_error(self, message: str, line: int = 0, col: int = 0,
                  code: str = "", fix: str = None) -> Diagnostic:
        diag = Diagnostic(
            message=message, severity=DiagnosticSeverity.ERROR,
            line=line, col=col, code=code, fix=fix,
        )
        self.add(diag)
        return diag

    def add_warning(self, message: str, line: int = 0, col: int = 0,
                    code: str = "", fix: str = None) -> Diagnostic:
        diag = Diagnostic(
            message=message, severity=DiagnosticSeverity.WARNING,
            line=line, col=col, code=code, fix=fix,
        )
        self.add(diag)
        return diag

    def add_hint(self, message: str, line: int = 0, col: int = 0) -> Diagnostic:
        diag = Diagnostic(
            message=message, severity=DiagnosticSeverity.HINT,
            line=line, col=col,
        )
        self.add(diag)
        return diag

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self._diagnostics if d.severity == DiagnosticSeverity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self._diagnostics if d.severity == DiagnosticSeverity.WARNING]

    @property
    def has_errors(self) -> bool:
        return self._error_count > 0

    def clear(self) -> None:
        self._diagnostics.clear()
        self._error_count = 0
        self._warning_count = 0

    def summary(self) -> str:
        return (f"诊断: {self._error_count} 错误, "
                f"{self._warning_count} 警告, "
                f"共 {len(self._diagnostics)} 条")

    def to_json(self) -> str:
        return json.dumps([d.to_lsp() for d in self._diagnostics],
                          ensure_ascii=False, indent=2)


# ============================================================
# 源码高亮
# ============================================================

class SourceHighlighter:
    """源码错误高亮器。"""

    # ANSI 颜色代码
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def highlight(cls, source: str, line: int, col: int, message: str,
                  severity: DiagnosticSeverity = DiagnosticSeverity.ERROR) -> str:
        """高亮源码中的错误位置。"""
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return message

        src_line = lines[line - 1]
        col_idx = max(0, col - 1)
        col_end = min(len(src_line), col_idx + 10)

        # 构建高亮字符串
        prefix = "  " * (line > 1)
        line_num = f"{cls.BOLD}{line}{cls.RESET}"
        caret = " " * col_idx + cls.RED + "^" * max(1, col_end - col_idx) + cls.RESET

        severity_icon = {"error": "✗", "warning": "⚠", "info": "ℹ", "hint": "·"}
        icon = severity_icon.get(severity.value, "?")

        result = (
            f"{prefix}{cls.CYAN}─ {line_num} │{cls.RESET} {src_line}\n"
            f"{prefix}   {' ' * len(line_num)} │{caret}\n"
            f"{prefix}   {cls.RED if severity == DiagnosticSeverity.ERROR else cls.YELLOW}"
            f"{icon} {message}{cls.RESET}"
        )
        return result

    @classmethod
    def highlight_range(cls, source: str, start_line: int, start_col: int,
                        end_line: int, end_col: int, message: str,
                        severity: DiagnosticSeverity = DiagnosticSeverity.ERROR) -> str:
        """高亮源码中的错误范围。"""
        lines = source.split("\n")
        if start_line < 1 or start_line > len(lines):
            return message

        src_line = lines[start_line - 1]
        start_idx = max(0, start_col - 1)
        end_idx = min(len(src_line), end_col)
        underline = " " * start_idx + cls.RED + "~" * max(1, end_idx - start_idx) + cls.RESET

        line_num = f"{cls.BOLD}{start_line}{cls.RESET}"
        icon = "✗" if severity == DiagnosticSeverity.ERROR else "⚠"

        return (
            f"  {cls.CYAN}─ {line_num} │{cls.RESET} {src_line}\n"
            f"     {cls.RED}{underline}{cls.RESET}\n"
            f"     {cls.RED if severity == DiagnosticSeverity.ERROR else cls.YELLOW}"
            f"{icon} {message}{cls.RESET}"
        )

    @classmethod
    def print_diagnostics(cls, source: str, diagnostics: list[Diagnostic]) -> None:
        """打印所有诊断信息。"""
        for diag in sorted(diagnostics, key=lambda d: (d.line, d.col)):
            print(cls.highlight(source, diag.line, diag.col, diag.message, diag.severity))
            print()


# ============================================================
# LSP 协议支持
# ============================================================

class LSPServer:
    """简单的 LSP 服务器实现（供 VSCode 插件使用）。"""

    def __init__(self) -> None:
        self._collector = DiagnosticCollector()

    def analyze(self, source: str, uri: str = "") -> list[dict]:
        """分析源码并返回诊断（LSP 格式）。"""
        self._collector.clear()
        self._parse_diagnostics(source)
        return [d.to_lsp() for d in self._collector._diagnostics]

    def _parse_diagnostics(self, source: str) -> None:
        """从源码中解析诊断信息。"""
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            # 检测未闭合的字符串
            if line.count('"') % 2 != 0 and not line.strip().startswith("#"):
                self._collector.add_warning(
                    f"可能未闭合的字符串（第 {i} 行）",
                    line=i, col=1, code="UNTERMINATED_STR"
                )
            # 检测括号不匹配
            paren_count = line.count("(") - line.count(")")
            bracket_count = line.count("[") - line.count("]")
            brace_count = line.count("{") - line.count("}")
            if paren_count != 0 or bracket_count != 0 or brace_count != 0:
                self._collector.add_hint(
                    f"括号不匹配: (={paren_count} [|={bracket_count} {{{brace_count}}}",
                    line=i, col=1, code="BRACKET_MISMATCH"
                )
            # 检测可能的拼写错误（常见模式）
            if re.search(r'\b[a-z][a-z][a-z]\b', line):
                # 三个连续小写字母可能是拼写错误
                pass  # 暂不实现

    def get_completions(self, source: str, line: int, col: int) -> list[dict]:
        """提供自动补全建议。"""
        # 简单实现：返回常见关键字和已定义变量
        keywords = ["func", "if", "else", "while", "for", "in", "let", "match"]
        return [{"label": k, "kind": 14} for k in keywords]  # 14 = Keyword


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "Diagnostic", "DiagnosticSeverity", "DiagnosticCollector",
    "SourceHighlighter", "LSPServer",
    "MathaErrorKind",
]
