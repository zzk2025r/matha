# -*- coding: utf-8 -*-
"""Matha v4.2 — 意图解析模块统一入口

统一导入所有意图解析组件。

用法：
  from src.intent import LLMIntentParser, IntentDecomposer, MIRGenerator
  from src.intent.mir_generator import generate_mir
"""
from __future__ import annotations

# LLM 意图解析器
from src.intent.llm_parser import (
    LLMIntentParser, Intent, IntentType,
    parse_intent, explain_intent,
)

# 意图分解引擎
from src.intent.intent_decomposer import (
    IntentDecomposer, IntentNode, IntentNodeType,
)

# MIR 代码生成器
from src.intent.mir_generator import (
    MIRGenerator, MIRNode, MIRNodeKind,
    generate_mir, explain_mir,
)

__all__ = [
    # LLM 解析器
    "LLMIntentParser", "Intent", "IntentType",
    "parse_intent", "explain_intent",
    # 意图分解
    "IntentDecomposer", "IntentNode", "IntentNodeType",
    # MIR 生成
    "MIRGenerator", "MIRNode", "MIRNodeKind",
    "generate_mir", "explain_mir",
]
