# -*- coding: utf-8 -*-
"""
Matha 诊断系统统一层（Unified Diagnostics）

合并 diagnostics.py 和 diagnostics_v2.py：
  - diagnostics.py: 基础 IDE 诊断（DiagnosticSeverity, DiagnosticCollector）
  - diagnostics_v2.py: 增强版（Severity, Diagnostic, ContextAnalyzer, ErrorHistory）

统一后：diagnostics_v2 的功能完全覆盖 diagnostics，diagnostics.py 作为 shim。
"""
from __future__ import annotations

# ── 从 diagnostics_v2 导入增强实现 ──────────────────────────────────────────
try:
    from src.diagnostics_v2 import (  # noqa: F401
        Severity,
        Diagnostic,
        ContextAnalyzer,
        ErrorHistory,
        EnhancedDiagnosticCollector,
        SourceHighlighter,
    )
except ImportError:
    Severity = None
    Diagnostic = None
    ContextAnalyzer = None
    ErrorHistory = None
    EnhancedDiagnosticCollector = None
    SourceHighlighter = None

# ── 从 diagnostics 导入基础实现（向后兼容）───────────────────────────────────
try:
    from src.diagnostics import (  # noqa: F401
        DiagnosticSeverity,
        Diagnostic as BaseDiagnostic,
        DiagnosticCollector,
        MathaErrorKind,
        SourceHighlighter as BaseSourceHighlighter,
        LSPServer,
    )
except ImportError:
    DiagnosticSeverity = None
    BaseDiagnostic = None
    DiagnosticCollector = None
    MathaErrorKind = None
    BaseSourceHighlighter = None
    LSPServer = None

# ── 统一别名（让两种 API 都能访问）───────────────────────────────────────────
# Severity 和 DiagnosticSeverity 是同义的
if Severity is not None:
    DiagnosticSeverity = Severity  # noqa: F811

# ── 统一导出函数 ────────────────────────────────────────────────────────────

def get_diagnostics(source: str) -> list:
    """获取源码诊断结果（统一接口）。"""
    try:
        from src.diagnostics import DiagnosticCollector
        collector = DiagnosticCollector()
        return collector.collect(source)
    except Exception:
        return []


def diagnose_source(source: str, path: str = "") -> list:
    """诊断源码（统一接口）。"""
    return get_diagnostics(source)


# ── 导出 ────────────────────────────────────────────────────────────────────
__all__ = [
    # v2 增强
    "Severity", "Diagnostic", "ContextAnalyzer", "ErrorHistory",
    "EnhancedDiagnosticCollector", "SourceHighlighter",
    # v1 基础（兼容别名）
    "DiagnosticSeverity", "BaseDiagnostic", "DiagnosticCollector",
    "MathaErrorKind", "BaseSourceHighlighter", "LSPServer",
    # 统一接口
    "get_diagnostics", "diagnose_source",
]
