# -*- coding: utf-8 -*-
"""Matha 增强诊断系统：代码高亮 + 修复建议 + 上下文分析 + 历史追踪。"""

from __future__ import annotations
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ============================================================
# 诊断等级
# ============================================================

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


# ============================================================
# 诊断信息
# ============================================================

@dataclass
class Diagnostic:
    """LSP 兼容诊断。"""
    message: str
    severity: Severity
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    source: str = "matha"
    code: str = ""
    fix: Optional[str] = None
    related: list[dict] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)

    def to_lsp(self) -> dict:
        return {
            "message": self.message,
            "severity": self.severity.value,
            "range": {
                "start": {"line": max(0, self.line - 1), "character": max(0, self.col - 1)},
                "end": {"line": max(0, self.end_line - 1), "character": max(0, self.end_col - 1)},
            },
            "source": self.source,
            "code": self.code,
            "fix": self.fix,
            "related": self.related,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_lsp(), ensure_ascii=False, indent=2)


# ============================================================
# 错误模式匹配
# ============================================================

_ERROR_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # 未定义变量
    (r"未定义变量\s+'(\w+)'", re.compile(r"未定义变量\s+'(\w+)"),
     "检查变量名拼写，或在使用前添加绑定: {0} = ?"),
    # 类型错误
    (r"类型错误.*期望\s+(\w+),\s+实际\s+(\w+)",
     re.compile(r"类型错误.*期望\s+(\w+),\s+实际\s+(\w+)"),
     "类型不匹配：期望 {0}, 实际 {1}。尝试类型转换或检查表达式类型。"),
    # 括号不匹配
    (r"期望\s+(\S+)\s+\(got\s+(\S+)\s+'?(\w+)'?\)",
     re.compile(r"期望\s+(\S+)\s+\(got\s+(\S+)\s+'?(\w+)'?\)"),
     "语法错误：期望 {0}, 实际 {2}。检查运算符或括号配对。"),
    # 除零
    (r"除数为零", re.compile(r"除数为零"), "检查除数表达式，确保不为零。"),
    # 索引越界
    (r"索引越界", re.compile(r"索引越界"), "检查索引范围，确保在列表/字符串长度内。"),
]


# ============================================================
# 上下文分析
# ============================================================

class ContextAnalyzer:
    """分析错误上下文，提供更有意义的错误信息。"""

    def __init__(self, source: str, line: int, col: int) -> None:
        self._source = source
        self._line = line
        self._col = col
        self._lines = source.split("\n")

    def get_context(self, radius: int = 3) -> list[str]:
        """获取错误位置的上下文代码。"""
        start = max(0, self._line - radius)
        end = min(len(self._lines), self._line + radius)
        return self._lines[start:end]

    def find_similar_vars(self, name: str) -> list[str]:
        """查找相似名称的已定义变量。"""
        similar = []
        for line in self._lines:
            for word in re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', line):
                if word != name and self._levenshtein(word, name) <= 2:
                    similar.append(word)
        return list(set(similar))[:5]

    def find_similar_funcs(self, name: str, known_funcs: list[str]) -> list[str]:
        """查找相似名称的已知函数。"""
        return [f for f in known_funcs
                if self._levenshtein(f, name) <= 2][:5]

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        """计算编辑距离。"""
        if len(s1) < len(s2):
            return ContextAnalyzer._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]


# ============================================================
# 历史追踪
# ============================================================

class ErrorHistory:
    """错误历史追踪。"""

    def __init__(self, max_entries: int = 100) -> None:
        self._history: list[dict] = []
        self._max = max_entries
        self._stats: dict[str, int] = defaultdict(int)

    def record(self, diagnostic: Diagnostic) -> None:
        self._history.append({
            "message": diagnostic.message,
            "code": diagnostic.code,
            "line": diagnostic.line,
            "severity": diagnostic.severity.value,
            "timestamp": __import__("time").time(),
        })
        self._stats[diagnostic.code] += 1
        if len(self._history) > self._max:
            self._history.pop(0)

    def get_duplicates(self) -> list[dict]:
        """返回重复出现的错误。"""
        return [{"code": code, "count": count}
                for code, count in self._stats.items() if count > 1]

    def get_recent(self, n: int = 10) -> list[dict]:
        return self._history[-n:]

    def clear(self) -> None:
        self._history.clear()
        self._stats.clear()


# ============================================================
# 增强诊断收集器
# ============================================================

class EnhancedDiagnosticCollector:
    """增强诊断收集器。"""

    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []
        self._history = ErrorHistory()
        self._error_count = 0
        self._warning_count = 0

    def add(self, diag: Diagnostic) -> None:
        self._diagnostics.append(diag)
        self._history.record(diag)
        if diag.severity == Severity.ERROR:
            self._error_count += 1
        elif diag.severity == Severity.WARNING:
            self._warning_count += 1

    def add_error(self, message: str, line: int = 0, col: int = 0,
                  code: str = "", fix: str = None,
                  context: list[str] = None) -> Diagnostic:
        diag = Diagnostic(
            message=message, severity=Severity.ERROR,
            line=line, col=col, code=code, fix=fix,
            context_lines=context or [],
        )
        self.add(diag)
        return diag

    def add_warning(self, message: str, line: int = 0, col: int = 0,
                    code: str = "", fix: str = None) -> Diagnostic:
        diag = Diagnostic(
            message=message, severity=Severity.WARNING,
            line=line, col=col, code=code, fix=fix,
        )
        self.add(diag)
        return diag

    def analyze_source(self, source: str, errors: list[str]) -> list[Diagnostic]:
        """从源码和错误列表分析诊断。"""
        diagnostics = []
        lines = source.split("\n")

        for err_msg in errors:
            # 匹配已知模式
            matched = False
            for pattern_name, pattern, suggestion in _ERROR_PATTERNS:
                m = pattern.search(err_msg)
                if m:
                    line_num = self._find_line(lines, err_msg)
                    diag = self.add_error(
                        message=err_msg,
                        line=line_num,
                        code=pattern_name,
                        fix=suggestion.format(*m.groups()) if m.groups() else None,
                    )
                    # 添加上下文
                    ctx = ContextAnalyzer(source, line_num, 0)
                    diag.context_lines = ctx.get_context()
                    # 添加相似变量建议
                    if "未定义变量" in err_msg:
                        var_name = m.group(1) if m.groups() else ""
                        similar = ctx.find_similar_vars(var_name)
                        if similar:
                            diag.fix = f"{diag.fix} 相似变量: {', '.join(similar)}"
                    matched = True
                    break
            if not matched:
                self.add_error(err_msg, code="UNKNOWN")

        return diagnostics

    def _find_line(self, lines: list[str], message: str) -> int:
        """在源码中查找错误行。"""
        for i, line in enumerate(lines):
            # 简单启发式：查找包含错误关键词的行
            for keyword in ["未定义", "期望", "类型", "除数", "索引"]:
                if keyword in message and keyword in line:
                    return i + 1
        return 1

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self._diagnostics if d.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self._diagnostics if d.severity == Severity.WARNING]

    @property
    def has_errors(self) -> bool:
        return self._error_count > 0

    def summary(self) -> str:
        return (f"诊断: {self._error_count} 错误, "
                f"{self._warning_count} 警告, "
                f"重复错误 {len(self._history.get_duplicates())} 种")

    def to_json(self) -> str:
        return json.dumps([d.to_lsp() for d in self._diagnostics],
                          ensure_ascii=False, indent=2)

    def clear(self) -> None:
        self._diagnostics.clear()
        self._error_count = 0
        self._warning_count = 0
        self._history.clear()


# ============================================================
# 源码高亮器
# ============================================================

class SourceHighlighter:
    """源码错误高亮器。"""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    BG_RED = "\033[41m"

    @classmethod
    def highlight(cls, source: str, line: int, col: int, message: str,
                  severity: Severity = Severity.ERROR) -> str:
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return f"{cls.RED}{message}{cls.RESET}"

        src_line = lines[line - 1]
        col_idx = max(0, col - 1)
        underline = " " * col_idx + cls.RED + "^" * max(1, min(20, len(src_line) - col_idx)) + cls.RESET

        line_num = f"{cls.BOLD}{line}{cls.RESET}"
        icon = "✗" if severity == Severity.ERROR else "⚠"
        color = cls.RED if severity == Severity.ERROR else cls.YELLOW

        return (
            f"{cls.CYAN}─ {line_num} │{cls.RESET} {src_line}\n"
            f"     {cls.BOLD}  │{cls.RESET}{underline}\n"
            f"     {color}{icon} {message}{cls.RESET}"
        )

    @classmethod
    def print_diagnostics(cls, source: str, diagnostics: list[Diagnostic]) -> None:
        for diag in sorted(diagnostics, key=lambda d: (d.line, d.col)):
            print(cls.highlight(source, diag.line, diag.col, diag.message, diag.severity))
            if diag.context_lines:
                for i, ctx_line in enumerate(diag.context_lines):
                    offset = diag.line - len(diag.context_lines) // 2 + i
                    if offset > 0 and offset <= len(source.split("\n")):
                        print(f"     {cls.CYAN}│{cls.RESET} {ctx_line}")
            if diag.fix:
                print(f"     {cls.GREEN}💡 建议: {diag.fix}{cls.RESET}")
            print()


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "Severity", "Diagnostic",
    "ContextAnalyzer", "ErrorHistory",
    "EnhancedDiagnosticCollector", "SourceHighlighter",
]
