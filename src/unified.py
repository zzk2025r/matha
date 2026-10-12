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

import src.ast_nodes as ast_nodes  # noqa: F401
from src.ast_nodes import *  # noqa: F401,F403
from src.interp import Interpreter, MathaRuntimeError, interpret  # noqa: F401
from src.lexer import Lexer, TokenType  # noqa: F401

# ── 核心：解析器 + 解释器 ───────────────────────────────────────────────────
from src.parser import Parser, parse  # noqa: F401
from src.tokens import TokenType as Token  # noqa: F401  # 别名兼容

# ── 类型系统 ────────────────────────────────────────────────────────────────
from src.typesystem_unified import (  # noqa: F401
    T_ANY,
    T_BOOL,
    T_COMPARABLE,
    T_FLOAT,
    T_INT,
    T_NUMERIC,
    T_STRING,
    T_UNKNOWN,
    T_VOID,
    Constraint,
    ConstraintSolver,
    EnhancedTypeInferencer,
    RefinementChecker,
    SubtypeRegistry,
    Type,
    TypeConstraint,
    TypeKind,
    UnifiedType,
)

# ── 增长/升级 ───────────────────────────────────────────────────────────────
from src.unified_growth import (  # noqa: F401
    UnifiedGrowth,
    get_unified_growth,
)

# ── 多语言 ──────────────────────────────────────────────────────────────────
from src.unified_multilang import (  # noqa: F401
    UnifiedMultiLang,
    get_unified_multilang,
)

# ── 诊断 ────────────────────────────────────────────────────────────────────
try:
    from src.unified_diagnostics import (  # noqa: F401
        Diagnostic,
        DiagnosticSeverity,
        diagnose_source,
        get_diagnostics,
    )
except ImportError:
    from src.diagnostics import (  # noqa: F401
        Diagnostic,
        DiagnosticSeverity,
    )

# ── 异步 ────────────────────────────────────────────────────────────────────
from src.errors import MathaError, ParseError  # noqa: F401

# ── 混合编译器 ──────────────────────────────────────────────────────────────
from src.hybrid_compiler import (  # noqa: F401
    AutoDiagnoser,
    BuildResult,
    DefectKind,
    DefectReport,
    HybridCompiler,
    Language,
    LanguageBridge,
    MathaRefactor,
    MixedProjectBuilder,
    Severity,
    UpgradeSubmitter,
    get_hybrid_compiler,
)

# ── 其他核心模块 ────────────────────────────────────────────────────────────
from src.result import Err, Ok, result  # noqa: F401
from src.semantic import SemanticAnalyzer  # noqa: F401
from src.unified_async import (  # noqa: F401
    Actor,
    AsyncRuntime,
    Channel,
    Condition,
    EventLoop,
    GoroutineScheduler,
    Mutex,
    Semaphore,
    ThreadPool,
)

# ── REPL ────────────────────────────────────────────────────────────────────
from src.unified_repl import (  # noqa: F401
    MathaREPL,
    REPLState,
    run_repl,
)

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
