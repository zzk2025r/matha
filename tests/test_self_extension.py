# -*- coding: utf-8 -*-
"""模拟失败交互场景，测试内循环自扩展功能（修复版）。"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inner_loop import MathaInnerLoop

loop = MathaInnerLoop()
loop.init_modules()

print("\n" + "=" * 60)
print("  模拟失败交互测试 — 自扩展功能验证")
print("=" * 60)

from src.ai_assistant import FriendlyIntentParser
p = FriendlyIntentParser()
before_concepts = len(p.MATH_CONCEPTS)
before_keywords = sum(len(v) for v in p.KEYWORD_MAP.values())
print(f"\n[初始状态]")
print(f"  数学概念: {before_concepts} 个")
print(f"  关键词总数: {before_keywords} 个")

# 模拟未知交互失败
print(f"\n[模拟失败交互]")
failure_scenarios = [
    ("帮我算一下质数有哪些", {"intent": "unknown", "type": "error", "reply": "无法识别意图"}),
    ("素数和质数有什么区别", {"intent": "unknown", "type": "error", "reply": "关键词未匹配"}),
    ("计算斐波那契数列第10项", {"intent": "unknown", "type": "error", "reply": "无法识别意图"}),
    ("费马大定理是什么", {"intent": "unknown", "type": "error", "reply": "未知概念"}),
    ("求勾股定理的证明", {"intent": "unknown", "type": "error", "reply": "无法匹配"}),
    ("帮我解微分方程", {"intent": "unknown", "type": "error", "reply": "超出范围"}),
    ("拉格朗日中值定理", {"intent": "unknown", "type": "error", "reply": "无法识别"}),
    ("泰勒展开怎么算", {"intent": "unknown", "type": "error", "reply": "关键词未找到"}),
    ("矩阵的行列式计算", {"intent": "unknown", "type": "error", "reply": "意图不匹配"}),
    ("黎曼几何基础概念", {"intent": "unknown", "type": "error", "reply": "无法分类"}),
]

for text, result in failure_scenarios:
    loop.on_interaction(text, result)
    print(f"  记录失败: '{text}'")

print(f"\n[触发自扩展]")
added_concepts = loop.self_extend_concepts()
added_intents = loop.self_extend_intents()
print(f"  新增概念: {added_concepts} 个")
print(f"  新增意图映射: {added_intents} 个")

# 验证结果
after_concepts = len(p.MATH_CONCEPTS)
after_keywords = sum(len(v) for v in p.KEYWORD_MAP.values())
print(f"\n[扩展后状态]")
print(f"  数学概念: {before_concepts} → {after_concepts} (新增 {after_concepts - before_concepts})")
print(f"  关键词总数: {before_keywords} → {after_keywords} (新增 {after_keywords - before_keywords})")

# 验证新功能
print(f"\n[验证扩展效果]")
from src.ai_assistant import MathaAIAssistant
assistant = MathaAIAssistant()
test_cases = [
    "帮我算一下质数",
    "素数分解",
    "斐波那契",
    "费马定理",
    "勾股定理",
    "微分方程",
    "拉格朗日",
    "泰勒展开",
    "矩阵行列式",
    "黎曼几何",
]
for tc in test_cases:
    intent, _ = assistant.parser.classify(tc)
    print(f"  '{tc}' → {intent.value}")

print("\n测试完成。")
