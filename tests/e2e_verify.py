# -*- coding: utf-8 -*-
"""端到端验证测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant
from src.interp import Interpreter

a = MathaAIAssistant()
i = Interpreter()

cases = [
    "计算 3 加 5",
    "求 100 的平方根",
    "找出 1 到 50 的素数",
    "求 [10,20,30,40,50] 的平均值",
    "计算 6 的阶乘",
    "自由落体 2 秒",
    "解释什么是素数",
]

passed = 0
for text in cases:
    r = a.chat(text, i)
    t = r["type"]
    result = r.get("result")
    print(f"  [{'OK' if t != 'error' else 'ERR'}] {text} -> {t} / {result}")
    if t != "error":
        passed += 1

print(f"\n端到端验证: {passed}/{len(cases)} 通过")
