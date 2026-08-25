# -*- coding: utf-8 -*-
"""Matha v4.2 — MIR 代码生成器

将结构化意图转换为可执行的机械语言（MIR）代码。

架构：
  结构化意图 → MIR Generator → MIR AST → 代码生成

用法：
  from src.intent.mir_generator import MIRGenerator

  generator = MIRGenerator()
  mir_code = generator.generate(intent)
"""
from __future__ import annotations
import json
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.intent.llm_parser import Intent, IntentType

logger = logging.getLogger(__name__)


# ============================================================
# MIR AST 节点
# ============================================================

class MIRNodeKind(Enum):
    """MIR 节点类型。"""
    # 算术
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    POWER = auto()
    SQRT = auto()
    # 函数
    SIN = auto()
    COS = auto()
    TAN = auto()
    LOG = auto()
    ABS = auto()
    # 逻辑
    AND = auto()
    OR = auto()
    NOT = auto()
    # 控制流
    IF = auto()
    LOOP = auto()
    FUNCTION = auto()
    # 数据
    ARRAY = auto()
    MAP = auto()
    REDUCE = auto()
    SORT = auto()
    # 常量
    CONSTANT = auto()
    VARIABLE = auto()
    # 输出
    PRINT = auto()
    RETURN = auto()


@dataclass
class MIRNode:
    """MIR AST 节点。"""
    kind: MIRNodeKind
    value: Any = None
    children: List['MIRNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_math_code(self, indent: int = 0) -> str:
        """序列化为可读的机械语言代码。"""
        prefix = "  " * indent
        if self.kind == MIRNodeKind.CONSTANT:
            return f"{prefix}{self.value}"
        elif self.kind == MIRNodeKind.VARIABLE:
            return f"{prefix}【{self.value}】"
        elif self.kind == MIRNodeKind.ADD:
            left = self.children[0].to_math_code(indent) if self.children else "0"
            right = self.children[1].to_math_code(indent) if len(self.children) > 1 else "0"
            return f"{prefix}（{left} + {right}）"
        elif self.kind == MIRNodeKind.MULTIPLY:
            left = self.children[0].to_math_code(indent) if self.children else "1"
            right = self.children[1].to_math_code(indent) if len(self.children) > 1 else "1"
            return f"{prefix}（{left} × {right}）"
        elif self.kind == MIRNodeKind.SQRT:
            child = self.children[0].to_math_code(indent) if self.children else "0"
            return f"{prefix}√{child}"
        elif self.kind == MIRNodeKind.FUNCTION:
            name = self.value or "f"
            params = self.metadata.get("params", [])
            body = self.children[0].to_math_code(indent + 1) if self.children else ""
            return f"{prefix}函数 {name}({', '.join(params)}):\n{body}"
        elif self.kind == MIRNodeKind.ARRAY:
            items = ", ".join(c.to_math_code(indent + 1) for c in self.children)
            return f"{prefix}@[{items}]"
        elif self.kind == MIRNodeKind.RETURN:
            child = self.children[0].to_math_code(indent) if self.children else "None"
            return f"{prefix}#：返回 {child}"
        else:
            return f"{prefix}/* {self.kind.name} */"


# ============================================================
# MIR 代码生成器
# ============================================================

class MIRGenerator:
    """
    MIR 代码生成器。

    将结构化意图转换为可执行的机械语言代码。
    """

    # 意图类型到 MIR 操作的映射
    _INTENT_MIR_MAP: Dict[IntentType, MIRNodeKind] = {
        IntentType.ARITHMETIC: MIRNodeKind.ADD,
        IntentType.MATH_FUNC: MIRNodeKind.SQRT,
        IntentType.ALGORITHM: MIRNodeKind.FUNCTION,
        IntentType.ARRAY_OP: MIRNodeKind.ARRAY,
        IntentType.COMPARISON: MIRNodeKind.IF,
        IntentType.CONDITIONAL: MIRNodeKind.IF,
        IntentType.LOOP: MIRNodeKind.LOOP,
        IntentType.FUNCTION: MIRNodeKind.FUNCTION,
        IntentType.GEOMETRY: MIRNodeKind.SQRT,
        IntentType.STATISTICS: MIRNodeKind.REDUCE,
    }

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._generation_count = 0

    def generate(self, intent: Intent) -> MIRNode:
        """
        根据意图生成 MIR AST。

        Args:
            intent: 结构化意图

        Returns:
            MIRNode: 机械语言 AST
        """
        if not intent.is_valid():
            return MIRNode(kind=MIRNodeKind.CONSTANT, value="/* 意图无效 */")

        # 检查缓存
        cache_key = self._cache_key(intent)
        if cache_key in self._cache:
            return self._parse_mir_ast(self._cache[cache_key])

        # 生成 MIR
        mir_node = self._generate_from_intent(intent)
        self._cache[cache_key] = mir_node.to_math_code()
        self._generation_count += 1

        return mir_node

    def _generate_from_intent(self, intent: Intent) -> MIRNode:
        """根据意图类型生成 MIR 节点。"""
        kind = self._INTENT_MIR_MAP.get(intent.intent_type, MIRNodeKind.CONSTANT)

        node = MIRNode(kind=kind, value=intent.description)

        # 根据参数生成子节点
        params = intent.params
        if params:
            for key, value in params.items():
                if isinstance(value, (int, float)):
                    node.children.append(MIRNode(kind=MIRNodeKind.CONSTANT, value=value))
                elif isinstance(value, str):
                    node.children.append(MIRNode(kind=MIRNodeKind.VARIABLE, value=value))
                elif isinstance(value, list):
                    arr_node = MIRNode(kind=MIRNodeKind.ARRAY)
                    for item in value:
                        arr_node.children.append(MIRNode(kind=MIRNodeKind.CONSTANT, value=item))
                    node.children.append(arr_node)

        # 添加返回节点
        if intent.suggested_code:
            node.children.append(MIRNode(kind=MIRNodeKind.RETURN, value=intent.suggested_code))

        return node

    def generate_from_text(self, text: str, intent: Optional[Intent] = None) -> str:
        """
        便捷方法：根据文本生成 MIR 代码。

        Args:
            text: 自然语言文本
            intent: 可选的意图对象（如已解析）

        Returns:
            str: 机械语言代码
        """
        if intent is None:
            from src.intent.intent_decomposer import IntentDecomposer
            ide = IntentDecomposer()
            root = ide.decompose(text)
            intent = Intent(
                intent_type=IntentType.ARITHMETIC,
                description=text,
                confidence=0.5,
                suggested_code=root.to_math_code(),
            )

        mir_node = self.generate(intent)
        return mir_node.to_math_code()

    def _cache_key(self, intent: Intent) -> str:
        """生成缓存键。"""
        import hashlib
        key_data = json.dumps({
            "type": intent.intent_type.name,
            "desc": intent.description,
            "params": intent.params,
        }, ensure_ascii=False)
        return hashlib.md5(key_data.encode()).hexdigest()[:16]

    def _parse_mir_ast(self, mir_code: str) -> MIRNode:
        """解析已缓存的 MIR 代码为 AST（简化版）。"""
        return MIRNode(kind=MIRNodeKind.CONSTANT, value=mir_code)

    def clear_cache(self):
        """清空缓存。"""
        self._cache.clear()

    def get_stats(self) -> Dict:
        """获取生成器统计。"""
        return {
            "generation_count": self._generation_count,
            "cache_size": len(self._cache),
        }


# ============================================================
# 便捷函数
# ============================================================

def generate_mir(text: str, intent: Optional[Intent] = None) -> str:
    """便捷函数：生成 MIR 代码。"""
    generator = MIRGenerator()
    return generator.generate_from_text(text, intent)


def explain_mir(mir_code: str) -> str:
    """解释 MIR 代码的数学含义。"""
    return f"""
MIR 代码解释:
{'='*40}
{mir_code}
{'='*40}
该代码表示一个数学表达式，
可通过 MIR 解释器执行或转换为其他语言。
"""


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MIR 代码生成器")
    parser.add_argument("text", help="自然语言输入")
    parser.add_argument("--intent-type", choices=[it.name for it in IntentType],
                       default="ARITHMETIC", help="意图类型")
    args = parser.parse_args()

    print("=" * 50)
    print("  Matha v4.2 — MIR 代码生成器")
    print("=" * 50)
    print(f"\n输入: {args.text!r}")

    # 创建模拟意图
    intent = Intent(
        intent_type=IntentType[args.intent_type],
        description=args.text,
        confidence=0.8,
        params={"value": 42},
        suggested_code=f"result = compute({args.text})",
    )

    # 生成 MIR
    generator = MIRGenerator()
    mir_node = generator.generate(intent)
    mir_code = mir_node.to_math_code()

    print(f"\n生成的 MIR 代码:")
    print(mir_code)

    # 解释
    print(explain_mir(mir_code))

    # 统计
    stats = generator.get_stats()
    print(f"\n生成统计: 次数={stats['generation_count']}, 缓存={stats['cache_size']}")
