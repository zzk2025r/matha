# -*- coding: utf-8 -*-
"""
Matha REPL 统一层（Unified REPL）

合并 repl.py 和 repl_v23.py：
  - repl.py: 基础 REPL（v2.2）
  - repl_v23.py: 增强 REPL（v2.3，使用 EnhancedIntentParser）

统一后：repl_v23 作为主实现，repl.py 作为 shim。
"""
from __future__ import annotations

# ── 从 repl_v23 导入增强实现 ────────────────────────────────────────────────
try:
    from src.repl_v23 import (  # noqa: F401
        run_repl,
        REPLState,
        MathaREPL,
    )
except ImportError:
    run_repl = None
    REPLState = None
    MathaREPL = None

# ── 从 repl 导入基础实现（向后兼容）─────────────────────────────────────────
try:
    from src.repl import (  # noqa: F401
        run_repl as run_repl_v22,
        REPLState as REPLStateV22,
        MathaREPL as MathaREPLV22,
    )
except ImportError:
    run_repl_v22 = None
    REPLStateV22 = None
    MathaREPLV22 = None

# ── 统一导出 ────────────────────────────────────────────────────────────────
__all__ = [
    "run_repl",
    "REPLState",
    "MathaREPL",
    "run_repl_v22",
    "REPLStateV22",
    "MathaREPLV22",
]
