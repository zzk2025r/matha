# -*- coding: utf-8 -*-
"""
Matha 统一包入口（Unified Package Entry）

所有子模块的统一导入点，提供向后兼容的访问路径。

使用方式：
    from src.unified import (
        parse, Lexer, TokenType,           # 解析器
        Interpreter, MathaRuntimeError,    # 解释器
        UnifiedType, T_INT, T_FLOAT,       # 类型系统
        UnifiedMultiLang,                 # 多语言
        UnifiedGrowth,                    # 增长/升级
        UnifiedDiagnostics,               # 诊断
        UnifiedAsync,                     # 异步
        UnifiedREPL,                      # REPL
    )
"""
from __future__ import annotations

# ── 核心：解析器 + 解释器 ───────────────────────────────────────────────────
from src.parser import Parser, parse, ParseError  # noqa: F401
from src.lexer import Lexer, TokenType  # noqa: F401
from src.ast_nodes import *  # noqa: F401,F403
from src.interp import Interpreter, interpret, MathaRuntimeError  # noqa: F401
from src.tokens import TokenType as Token  # noqa: F401  # 别名兼容

# ── 类型系统 ────────────────────────────────────────────────────────────────
from src.typesystem_unified import (  # noqa: F401
    UnifiedType,
    Type,
    TypeKind,
    T_INT, T_FLOAT, T_STRING, T_BOOL, T_VOID, T_ANY, T_UNKNOWN,
    T_NUMERIC, T_COMPARABLE,
    Constraint, ConstraintSolver,
    SubtypeRegistry, RefinementChecker, EnhancedTypeInferencer,
    TypeConstraint,
)

# ── 多语言 ──────────────────────────────────────────────────────────────────
from src.unified_multilang import (  # noqa: F401
    UnifiedMultiLang,
    get_unified_multilang,
)

# ── 增长/升级 ───────────────────────────────────────────────────────────────
from src.unified_growth import (  # noqa: F401
    UnifiedGrowth,
    get_unified_growth,
)

# ── 诊断 ────────────────────────────────────────────────────────────────────
try:
    from src.unified_diagnostics import (  # noqa: F401
        DiagnosticSeverity,
        Diagnostic,
        get_diagnostics,
        diagnose_source,
    )
except ImportError:
    from src.diagnostics import (  # noqa: F401
        DiagnosticSeverity,
        Diagnostic,
    )

# ── 异步 ────────────────────────────────────────────────────────────────────
from src.unified_async import (  # noqa: F401
    AsyncRuntime,
    GoroutineScheduler,
    Channel,
    Actor,
    ThreadPool,
    EventLoop,
    Mutex,
    Semaphore,
    Condition,
)

# ── REPL ────────────────────────────────────────────────────────────────────
from src.unified_repl import (  # noqa: F401
    run_repl,
    REPLState,
    MathaREPL,
)

# ── 混合编译器 ──────────────────────────────────────────────────────────────
from src.hybrid_compiler import (  # noqa: F401
    HybridCompiler,
    LanguageBridge,
    AutoDiagnoser,
    MixedProjectBuilder,
    MathaRefactor,
    UpgradeSubmitter,
    Language,
    DefectKind,
    Severity,
    DefectReport,
    BuildResult,
    get_hybrid_compiler,
)

# ── 其他核心模块 ────────────────────────────────────────────────────────────
from src.result import Ok, Err, result  # noqa: F401
from src.errors import MathaError, ParseError  # noqa: F401
from src.semantic import SemanticAnalyzer  # noqa: F401
try:
    from src.symbolic import SymbolicParser  # noqa: F401
except ImportError:
    pass
try:
    from src.mathlib import MathLib  # noqa: F401
except ImportError:
    pass

# ── 包级导出 ────────────────────────────────────────────────────────────────
__all__ = [
    # 核心
    "parse", "Parser", "Lexer", "TokenType", "Token",
    "Interpreter", "interpret", "MathaRuntimeError",
    "ast_nodes",
    # 类型系统
    "UnifiedType", "Type", "TypeKind",
    "T_INT", "T_FLOAT", "T_STRING", "T_BOOL", "T_VOID", "T_ANY", "T_UNKNOWN",
    "T_NUMERIC", "T_COMPARABLE",
    "Constraint", "ConstraintSolver",
    "SubtypeRegistry", "RefinementChecker", "EnhancedTypeInferencer",
    "TypeConstraint",
    # 多语言
    "UnifiedMultiLang", "get_unified_multilang",
    # 增长/升级
    "UnifiedGrowth", "get_unified_growth",
    # 诊断
    "DiagnosticSeverity",
    "Diagnostic",
    "get_diagnostics", "diagnose_source",
    # 异步
    "AsyncRuntime", "GoroutineScheduler", "Channel", "Actor",
    "ThreadPool", "EventLoop", "Mutex", "Semaphore", "Condition",
    # REPL
    "run_repl",
    "REPLState",
    "MathaREPL",
    # 混合编译器
    "HybridCompiler", "LanguageBridge", "AutoDiagnoser",
    "MixedProjectBuilder", "MathaRefactor", "UpgradeSubmitter",
    "Language", "DefectKind", "Severity", "DefectReport", "BuildResult",
    "get_hybrid_compiler",
    # 其他
    "Ok", "Err", "result",
    "MathaError", "ParseError",
]
