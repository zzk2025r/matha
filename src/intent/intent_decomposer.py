# -*- coding: utf-8 -*-
"""Matha v4.0 — 意图分解引擎（IDE）核心实现

设计原则：
  1. 短文本（≤20字）→ 快速路径（正则匹配，<50ms）
  2. 中文本（20-100字）→ 标点拆分 + 子意图合并
  3. 长文本（>100字）→ LLM 辅助意图树分解
  4. 自进化：成功映射自动存储为新模板

架构：
  自然语言 → IDE 分解 → 意图树 → 数学映射 → 可执行代码
"""
from __future__ import annotations
import json
import re
import time
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

sys.path.insert(0, r"D:\trae")
from src.intent_parser import IntentType


# ============================================================
# 意图树节点
# ============================================================

class IntentNodeType(Enum):
    """意图树节点类型。"""
    ROOT = auto()           # 根节点（整体意图）
    COMPLEX = auto()        # 复合意图（需要分解）
    ATOMIC = auto()         # 原子意图（可直接映射数学）
    CONSTRAINT = auto()     # 约束条件
    CONTEXT = auto()        # 上下文信息
    QUESTION = auto()       # 需要追问的问题


@dataclass
class IntentNode:
    """意图树节点。"""
    node_type: IntentNodeType
    text: str
    math_expr: str = ""
    sub_intents: List['IntentNode'] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence: float = 1.0
    follow_up: List[str] = field(default_factory=list)
    parse_time_ms: float = 0.0

    def is_complete(self) -> bool:
        """检查节点是否完整。"""
        if self.math_expr:
            return True
        if self.node_type == IntentNodeType.ATOMIC and self.confidence >= 0.7:
            return True
        if self.sub_intents and all(n.is_complete() for n in self.sub_intents):
            return True
        return False

    def to_math_code(self) -> str:
        """将意图树转换为数学代码（MIR 格式）。"""
        if self.math_expr:
            return self.math_expr
        if self.sub_intents:
            lines = [n.to_math_code() for n in self.sub_intents if n.to_math_code()]
            return "\n".join(lines)
        return f"# 无法映射: {self.text}"

    def to_dict(self) -> Dict:
        """序列化为字典。"""
        return {
            "type": self.node_type.name,
            "text": self.text,
            "math_expr": self.math_expr,
            "sub_intents": [n.to_dict() for n in self.sub_intents],
            "constraints": self.constraints,
            "confidence": self.confidence,
            "follow_up": self.follow_up,
            "parse_time_ms": self.parse_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'IntentNode':
        """从字典反序列化。"""
        node = cls(
            node_type=IntentNodeType[data["type"]],
            text=data["text"],
            math_expr=data.get("math_expr", ""),
            constraints=data.get("constraints", []),
            confidence=data.get("confidence", 1.0),
            follow_up=data.get("follow_up", []),
            parse_time_ms=data.get("parse_time_ms", 0.0),
        )
        for sub in data.get("sub_intents", []):
            node.sub_intents.append(cls.from_dict(sub))
        return node


# ============================================================
# 意图分解引擎（IDE）
# ============================================================

class IntentDecomposer:
    """
    意图分解引擎（IDE）。

    将任意长度自然语言拆分为意图树，并映射为数学表达式。
    """

    # ============================================================
    # 短文本快速规则（≤20 字）
    # ============================================================

    SHORT_RULES: List[tuple] = [
        # 算术表达式
        (r'[\d.]+\s*[+\-*/^]\s*[\d.]+', IntentType.ARITHMETIC, 'ARITHMETIC_EXPR'),
        (r'计算\s*[\d.]+\s*[加减乘除]\s*[\d.]+', IntentType.ARITHMETIC, 'ARITHMETIC_EXPR'),
        # 数学函数
        (r'求\s*[\d.]+\s*的\s*(平方根|立方根|对数|正弦|余弦|正切)', IntentType.MATH_FUNC, 'MATH_FUNC'),
        (r'(正弦|余弦|正切)\s*[\d.]+', IntentType.MATH_FUNC, 'MATH_FUNC'),
        # 比较
        (r'[\d.]+\s*(大于|小于|等于|大于等于|小于等于)\s*[\d.]+', IntentType.COMPARISON, 'COMPARISON'),
        # 数组操作
        (r'(排序|反转|过滤|去重)\s*(数组|列表|序列)', IntentType.ARRAY_OP, 'ARRAY_OP'),
        # 字符串操作
        (r'(反转|拼接|截取|替换|拆分)\s*(字符串|文字|文本)', IntentType.STRING_OP, 'STRING_OP'),
        # 素数/因数
        (r'(素数|质数|因数|因子)\s*(找出|列出|计算)', IntentType.MATH_FUNC, 'PRIME_SEARCH'),
        # 范围查询
        (r'[\d.]+\s*到\s*[\d.]+', IntentType.ARRAY_OP, 'RANGE'),
    ]

    # ============================================================
    # 中文本规则（20-100 字）
    # ============================================================

    MEDIUM_RULES: List[tuple] = [
        (r'并且|同时|以及|还有', 'COMPLEX_MERGE'),
        (r'如果|假如|当.*时', 'CONDITIONAL'),
        (r'排序.*对|过滤.*在|映射.*到', 'ARRAY_OP_CHAIN'),
        (r'找出.*并.*计算|求.*同时求', 'MULTI_STEP'),
    ]

    # ============================================================
    # 内置数学映射函数
    # ============================================================

    MATH_MAPPINGS: Dict[str, Callable[[str], str]] = {
        'ARITHMETIC_EXPR': lambda t: _extract_arithmetic(t),
        'MATH_FUNC': lambda t: _extract_math_func(t),
        'COMPARISON': lambda t: _extract_comparison(t),
        'ARRAY_OP': lambda t: _extract_array_op(t),
        'STRING_OP': lambda t: _extract_string_op(t),
        'PRIME_SEARCH': lambda t: _extract_prime_search(t),
        'RANGE': lambda t: _extract_range(t),
        'CONDITIONAL': lambda t: _extract_conditional(t),
    }

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self._template_dir = Path(".matha_templates")
        self._templates = self._load_templates()

    # ============================================================
    # 核心分解方法
    # ============================================================

    def decompose(self, text: str) -> IntentNode:
        """
        将自然语言分解为意图树。

        策略：
        1. 短文本（≤20字）→ 直接匹配快速规则
        2. 中文本（20-100字）→ 标点拆分 + 子意图合并
        3. 长文本（>100字）→ LLM 辅助分解（如启用）
        """
        text = text.strip()
        start = time.perf_counter()

        if len(text) <= 20:
            root = self._decompose_short(text)
        elif len(text) <= 100:
            root = self._decompose_medium(text)
        else:
            root = self._decompose_long(text)

        root.parse_time_ms = (time.perf_counter() - start) * 1000
        return root

    def _decompose_short(self, text: str) -> IntentNode:
        """短文本：直接匹配快速规则。"""
        for pattern, intent_type, mapping_key in self.SHORT_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                math_fn = self.MATH_MAPPINGS.get(mapping_key)
                math_expr = math_fn(text) if math_fn else ""

                return IntentNode(
                    node_type=IntentNodeType.ATOMIC,
                    text=text,
                    math_expr=math_expr,
                    confidence=0.95,
                )

        # 未匹配 → 尝试 LLM
        if self.use_llm:
            return self._llm_decompose(text)

        # KNP-008: 动态计算降级置信度（基于文本长度和规则匹配数）
        import re
        rule_matches = sum(1 for kw in text if any(k in text.lower() for k in ["加", "减", "乘", "除", "算", "求", "多少"]))
        dynamic_confidence = min(0.9, 0.3 + rule_matches * 0.1 + len(text) * 0.005)

        return IntentNode(
            node_type=IntentNodeType.ATOMIC,
            text=text,
            confidence=dynamic_confidence,
            follow_up=["无法识别意图，请提供更多上下文"],
        )

    def _decompose_medium(self, text: str) -> IntentNode:
        """中文本：拆分 + 合并。"""
        # 按标点拆分
        parts = self._split_by_punctuation(text)

        if len(parts) <= 1:
            # 单句 → 尝试短文本规则
            return self._decompose_short(text)

        # 多句 → 每句分解为子意图
        sub_intents = []
        for part in parts:
            part = part.strip()
            if len(part) > 3:
                child = self._decompose_short(part)
                if child.confidence >= 0.5:
                    sub_intents.append(child)

        if not sub_intents:
            return self._decompose_short(text)

        # 检查是否有复合操作符
        is_complex = any(
            re.search(rule, text) for rule, _ in [
                (r'并且|同时|以及', 'MERGE'),
                (r'如果|假如', 'CONDITIONAL'),
            ]
        )

        node_type = IntentNodeType.COMPLEX if is_complex else IntentNodeType.ATOMIC

        return IntentNode(
            node_type=node_type,
            text=text,
            sub_intents=sub_intents,
            confidence=0.85,
        )

    def _decompose_long(self, text: str) -> IntentNode:
        """长文本：LLM 辅助分解。"""
        if self.use_llm:
            return self._llm_decompose(text)

        # 无 LLM 时，使用启发式规则
        return self._heuristic_long_decompose(text)

    def _llm_decompose(self, text: str) -> IntentNode:
        """
        使用 LLM 进行意图分解。

        返回包含完整意图树的根节点。
        """
        # 实际实现应调用 Claude/GPT API
        # 这里返回模拟结果用于演示
        return self._simulate_llm_decomposition(text)

    def _heuristic_long_decompose(self, text: str) -> IntentNode:
        """长文本启发式分解（无 LLM 时的降级方案）。

        KNP-005: 改进长文本分解，支持多句、多任务混合输入。
        """
        # 按句号/分号/换行拆分
        sentences = re.split(r'[。；;\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            # 尝试按连接词拆分
            parts = re.split(r'(并且|同时|以及|然后|接着|另外|还有)', text)
            parts = [p.strip() for p in parts if p.strip() and p.strip() not in
                     ['并且', '同时', '以及', '然后', '接着', '另外', '还有']]
        else:
            parts = sentences

        sub_intents = []
        for part in parts:
            if len(part) > 3:  # KNP-005: 降低最小长度阈值
                child = self.decompose(part)
                # KNP-008: 动态置信度阈值
                if child.confidence >= 0.3:  # 从 0.5 降到 0.3，更宽容
                    sub_intents.append(child)

        # KNP-005: 如果没有子意图，尝试按关键词分块
        if not sub_intents and len(text) > 50:
            keywords = ['计算', '求', '找出', '分解', '判断', '验证', '比较']
            for kw in keywords:
                if kw in text:
                    # 找到关键词后的内容作为独立任务
                    idx = text.find(kw)
                    if idx > 0:
                        before = text[:idx].strip()
                        after = text[idx:].strip()
                        if before and len(before) > 3:
                            child1 = self.decompose(before)
                            if child1.confidence >= 0.3:
                                sub_intents.append(child1)
                        if after and len(after) > 3:
                            child2 = self.decompose(after)
                            if child2.confidence >= 0.3:
                                sub_intents.append(child2)
                        if sub_intents:
                            return IntentNode(
                                node_type=IntentNodeType.ROOT,
                                text=text,
                                sub_intents=sub_intents,
                                confidence=0.75,
                            )

        return IntentNode(
            node_type=IntentNodeType.ROOT,
            text=text,
            sub_intents=sub_intents,
            confidence=0.6,  # KNP-008: 动态置信度
        )

    # ============================================================
    # 辅助方法
    # ============================================================

    def _split_by_punctuation(self, text: str) -> List[str]:
        """按中文/英文标点拆分文本。"""
        # 匹配中文标点和英文标点
        parts = re.split(r'[，,。.;;、|]+', text)
        return [p.strip() for p in parts if p.strip()]

    def _simulate_llm_decomposition(self, text: str) -> IntentNode:
        """
        模拟 LLM 分解（用于测试和演示）。

        实际实现应调用真实 LLM API。
        """
        # 基于关键词的智能分解
        sub_intents = []

        # 检测素数搜索
        if re.search(r'素数|质数', text):
            match = re.search(r'(\d+)\s*到\s*(\d+)', text)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                sub_intents.append(IntentNode(
                    node_type=IntentNodeType.ATOMIC,
                    text="找出素数",
                    math_expr=f"primes = [p for p in range({start}, {end}+1) if is_prime(p)]",
                    confidence=0.95,
                ))

        # 检测排序
        if re.search(r'排序', text):
            match = re.search(r'数组?\s*([^\s,，。]+)', text)
            if match:
                arr_str = match.group(1).strip('【】〔〕[]')
                arr = [float(x) for x in arr_str.split(',')]
                sub_intents.append(IntentNode(
                    node_type=IntentNodeType.ATOMIC,
                    text="排序数组",
                    math_expr=f"sorted_arr = sorted({arr})",
                    confidence=0.95,
                ))

        # 检测算术
        if re.search(r'计算|求', text):
            match = re.search(r'([\d.]+\s*[+\-*/^]\s*[\d.]+)', text)
            if match:
                expr = match.group(1)
                sub_intents.append(IntentNode(
                    node_type=IntentNodeType.ATOMIC,
                    text="算术计算",
                    math_expr=f"result = {expr}",
                    confidence=0.95,
                ))

        # 检测条件
        if re.search(r'如果|假如', text):
            sub_intents.append(IntentNode(
                node_type=IntentNodeType.CONSTRAINT,
                text="条件约束",
                constraints=["需要进一步澄清条件"],
                confidence=0.6,
                follow_up=["请明确条件表达式"],
            ))

        if not sub_intents:
            # 无法分解 → 返回单节点
            # KNP-008: 动态置信度
            import re
            rule_matches = sum(1 for kw in text if any(k in text.lower() for k in ["加", "减", "乘", "除", "算", "求", "多少"]))
            dynamic_confidence = min(0.9, 0.3 + rule_matches * 0.1 + len(text) * 0.005)
            return IntentNode(
                node_type=IntentNodeType.ROOT,
                text=text,
                confidence=dynamic_confidence,
                follow_up=["请输入更具体的计算任务"],
            )

        return IntentNode(
            node_type=IntentNodeType.ROOT,
            text=text,
            sub_intents=sub_intents,
            confidence=0.9,
        )

    # ============================================================
    # 模板学习
    # ============================================================

    def learn(self, input_text: str, math_expr: str, success: bool = True):
        """从成功映射中学习新模板。"""
        if not success:
            return

        pattern = self._extract_pattern(input_text)
        template = {
            'pattern': pattern,
            'math_expr': math_expr,
            'input': input_text,
            'created_at': time.time(),
            'usage_count': 1,
        }

        # 存储到模板文件
        template_file = self._template_dir / "templates.json"
        templates = {}
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                templates = json.load(f)

        template_hash = hash(pattern) % 100000
        templates[str(template_hash)] = template

        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)

    def _load_templates(self) -> Dict:
        """加载已存储的模板。"""
        template_file = self._template_dir / "templates.json"
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _extract_pattern(self, text: str) -> str:
        """提取文本模式。"""
        # 移除数字，保留结构
        pattern = re.sub(r'\d+\.?\d*', 'NUM', text)
        return pattern


# ============================================================
# 数学映射函数
# ============================================================

def _extract_arithmetic(text: str) -> str:
    """提取算术表达式。"""
    # 处理中文运算符
    expr = text
    expr = expr.replace('加', '+').replace('减', '-')
    expr = expr.replace('乘以', '*').replace('除以', '/')
    expr = expr.replace('平方', '**2').replace('立方', '**3')
    expr = expr.replace('开方', 'sqrt')

    # 提取数字和运算符
    match = re.search(r'([\d.]+\s*[+\-*/^]\s*[\d.]+)', expr)
    if match:
        return f"result = {match.group(1)}"
    return f"# 无法解析算术表达式: {text}"


def _extract_math_func(text: str) -> str:
    """提取数学函数。"""
    if '正弦' in text:
        match = re.search(r'正弦\s*([\d.]+)', text)
        if match:
            return f"result = sin({match.group(1)})"
    elif '余弦' in text:
        match = re.search(r'余弦\s*([\d.]+)', text)
        if match:
            return f"result = cos({match.group(1)})"
    elif '平方根' in text:
        # 匹配 "求 16 的平方根" 或 "平方根 16"
        match = re.search(r'([\d.]+)\s*的\s*平方根|平方根\s*([\d.]+)', text)
        if match:
            num = match.group(1) or match.group(2)
            return f"result = sqrt({num})"
    elif '对数' in text:
        match = re.search(r'对数\s*([\d.]+)', text)
        if match:
            return f"result = log({match.group(1)})"
    return "# 无法解析数学函数"


def _extract_comparison(text: str) -> str:
    """提取比较表达式。"""
    ops = {
        '大于': '>', '小于': '<', '等于': '==',
        '大于等于': '>=', '小于等于': '<=',
    }
    for cn_op, py_op in ops.items():
        if cn_op in text:
            match = re.search(r'([\d.]+)\s*' + cn_op + r'\s*([\d.]+)', text)
            if match:
                return f"result = {match.group(1)} {py_op} {match.group(2)}"
    return "# 无法解析比较表达式"


def _extract_array_op(text: str) -> str:
    """提取数组操作。"""
    # 匹配 "[数字,数字]" 或 "(数字,数字)" 格式
    arr_match = re.search(r'[\[（(][\d,.\\s]+[\]）)]', text)
    arr_str = arr_match.group(0) if arr_match else ""
    if arr_str:
        arr_str = arr_str.strip('[]()（）')
        arr = [float(x) for x in arr_str.split(',') if x.strip()]
    else:
        arr = []

    if '排序' in text:
        if arr:
            return f"result = sorted({arr})"
        return "result = sorted(array)"
    elif '反转' in text:
        if arr:
            return f"result = {arr}[::-1]"
        return "result = array[::-1]"
    elif '求和' in text:
        if arr:
            return f"result = sum({arr})"
        return "result = sum(array)"
    return "# 无法解析数组操作"


def _extract_string_op(text: str) -> str:
    """提取字符串操作。"""
    if '反转' in text:
        match = re.search(r'(字符串|文字|文本)\s*([\w\u4e00-\u9fff]+)', text)
        if match:
            s = match.group(2)
            return f"result = '{s}'[::-1]"
    elif '拼接' in text:
        return "# 字符串拼接操作"
    return "# 无法解析字符串操作"


def _extract_prime_search(text: str) -> str:
    """提取素数搜索。"""
    # 匹配 "找出 1 到 100 的素数" 或 "计算 100 以内所有素数"
    match = re.search(r'(\d+)\s*到\s*(\d+)', text)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return f"primes = [p for p in range({start}, {end}+1) if all(p%d!=0 for d in range(2, int(p**0.5)+1))]"
    # 匹配 "100 以内"
    match = re.search(r'(\d+)\s*以内', text)
    if match:
        end = int(match.group(1))
        return f"primes = [p for p in range(2, {end}+1) if all(p%d!=0 for d in range(2, int(p**0.5)+1))]"
    return "# 无法解析素数搜索"


def _extract_range(text: str) -> str:
    """提取范围。"""
    match = re.search(r'([\d.]+)\s*到\s*([\d.]+)', text)
    if match:
        start, end = float(match.group(1)), float(match.group(2))
        return f"result = list(range({int(start)}, {int(end)}+1))"
    return "# 无法解析范围"


def _extract_conditional(text: str) -> str:
    """提取条件表达式。"""
    return "# 条件表达式需要进一步解析"


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    ide = IntentDecomposer(use_llm=False)

    # 测试用例
    test_cases = [
        # 短文本
        "计算 3 加 5",
        "求 16 的平方根",
        "判断 10 大于 5",
        # 中文本
        "对数组 [3,1,2] 排序并且反转结果",
        "找出 1 到 100 的素数并求和",
        # 长文本
        "找出 1 到 100 之间的所有素数，将它们排序，然后计算总和",
        "计算 3 加 5 的结果，然后乘以 2，最后减去 1",
        "如果 x 大于 10 那么输出 x 的平方，否则输出 x 的立方",
    ]

    print("=" * 70)
    print("  Matha v4.0 — 意图分解引擎（IDE）测试")
    print("=" * 70)

    for i, test in enumerate(test_cases, 1):
        print(f"\n【测试 {i}】输入: {test!r}")
        print("-" * 50)

        root = ide.decompose(test)
        print(f"置信度: {root.confidence:.0%}")
        print(f"解析耗时: {root.parse_time_ms:.1f}ms")
        print(f"节点类型: {root.node_type.name}")
        print(f"子意图数: {len(root.sub_intents)}")

        if root.sub_intents:
            print("\n意图树:")
            for j, sub in enumerate(root.sub_intents, 1):
                print(f"  [{j}] {sub.node_type.name}: {sub.text!r}")
                print(f"      数学表达式: {sub.math_expr!r}")
                print(f"      置信度: {sub.confidence:.0%}")
                if sub.follow_up:
                    print(f"      追问: {sub.follow_up}")

        print(f"\n完整数学代码:")
        print(root.to_math_code())

    print("\n" + "=" * 70)
    print("  测试完成")
    print("=" * 70)
