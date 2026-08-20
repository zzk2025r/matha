"""matha-auth tree-sitter 后端（无需外部依赖的内联 AST 解析器）"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

# 支持标记（tree-sitter C 扩展不可用时降级为内联解析器）
_TS_AVAILABLE = True
