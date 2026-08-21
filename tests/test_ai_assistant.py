# -*- coding: utf-8 -*-
"""Matha AI Assistant 测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant, FriendlyIntentParser
from src.interp import Interpreter


def test_intent_classifier():
    """测试意图分类。"""
    print("\n=== 意图分类测试 ===")
    parser = FriendlyIntentParser()

    cases = [
        ("计算 3 加 5", "arithmetic"),
        ("找出 1 到 100 的素数", "number_theory"),
        ("求 [1,2,3,4,5] 的平均值", "statistics"),
        ("自由落体 3 秒", "physics"),
        ("计算 5 的阶乘", "math_func"),
        ("sin(3.14) 等于多少", "trig"),
        ("解释什么是素数", "unknown"),
    ]

    for text, expected in cases:
        intent_type, conf = parser.classify(text)
        status = "✓" if intent_type.value == expected or expected == "unknown" else "≈"
        print(f"  {status} '{text[:20]}...' → {intent_type.value} (置信度 {conf:.0%})")


def test_decompose():
    """测试步骤分解。"""
    print("\n=== 步骤分解测试 ===")
    parser = FriendlyIntentParser()

    cases = [
        "计算 3 加 5",
        "找出 1 到 100 的素数",
        "求 [1,2,3,4,5] 的平均值",
        "自由落体 3 秒",
        "计算 5 的阶乘",
    ]

    for text in cases:
        steps = parser.decompose(text)
        print(f"\n  输入: '{text}'")
        for i, step in enumerate(steps):
            print(f"    步骤 {i+1}: {step.description}")
            if step.matha_code:
                print(f"      代码: {step.matha_code[:60]}...")


def test_execute():
    """测试执行。"""
    print("\n=== 执行测试 ===")
    assistant = MathaAIAssistant()
    interp = Interpreter()

    cases = [
        "计算 3 加 5",
        "求 10 的阶乘",
        "求 [1,2,3,4,5] 的平均值",
    ]

    for text in cases:
        result = assistant.chat(text, interp)
        print(f"\n  输入: '{text}'")
        print(f"  结果: {result.get('result')}")
        print(f"  类型: {result.get('type')}")


def test_error_handling():
    """测试错误处理。"""
    print("\n=== 错误处理测试 ===")
    assistant = MathaAIAssistant()
    interp = Interpreter()

    # 测试无效输入
    result = assistant.chat("xyz abc notreal", interp)
    print(f"  无效输入 → 类型: {result.get('type')}")

    # 测试概念解释
    result = assistant.chat("解释什么是素数", interp)
    print(f"  概念解释 → 回复长度: {len(result.get('reply', ''))}")


def test_concept_explanation():
    """测试数学概念讲解。"""
    print("\n=== 概念讲解测试 ===")
    parser = FriendlyIntentParser()

    concepts = ["加法", "乘法", "除法", "平方", "开方", "平均值", "素数"]
    for c in concepts:
        info = parser.explain_concept(c)
        print(f"  {c}: {info.get('是什么', 'N/A')[:30]}...")


def test_commonsense():
    """测试常识逻辑增强：变体表达/冷门方式/数字推断/fallback。"""
    print("\n=== 常识逻辑增强测试 ===")
    parser = FriendlyIntentParser()
    assistant = MathaAIAssistant()
    interp = Interpreter()

    cases = [
        # (输入, 期望意图关键词, 说明)
        ("帮我算一下", "arithmetic", "变体表达"),
        ("算算 7 加 3", "arithmetic", "变体算算"),
        ("100 的一半", "arithmetic", "一半→除法"),
        ("5 的 3 倍", "arithmetic", "倍→乘法"),
        ("1000 米等于多少千米", "unit_convert", "单位换算"),
        ("25 开方是多少", "math_func", "开方"),
        ("60 秒等于多少分", "unit_convert", "时间换算"),
        ("17 是不是素数", "number_theory", "判断素数"),
        ("60 秒是多少分钟", "unit_convert", "时间单位"),
    ]

    for text, expected_intent, desc in cases:
        intent_type, conf = parser.classify(text)
        status = "✓" if intent_type.value == expected_intent or expected_intent in intent_type.value.lower() else "≈"
        print(f"  {status} [{desc}] '{text}' → {intent_type.value} (置信度 {conf:.0%})")

    # 执行测试：常见表达
    for text, _, desc in cases:
        result = assistant.chat(text, interp)
        result_type = result.get("type", "unknown")
        output = result.get("output", result.get("reply", ""))
        output_str = repr(output)[:40]
        status = "✓" if result_type not in ("unknown", "error") else "✗"
        print(f"  {status} [{desc}] '{text}' → type={result_type}, 结果={output_str}")

    # 学习记忆测试
    parser.learn("帮我算一下", parser.classify("帮我算一下")[0])
    intent2, conf2 = parser.classify("帮我算一下")
    print(f"  ✓ 学习记忆: '帮我算一下' 重新分类 → {intent2.value} (置信度 {conf2:.0%})")

    # 兜底推断
    intent3, conf3 = parser.classify("123")
    print(f"  ✓ 兜底推断: '123' → {intent3.value} (置信度 {conf3:.0%})")


def main():
    test_intent_classifier()
    test_decompose()
    test_execute()
    test_error_handling()
    test_concept_explanation()
    test_commonsense()
    print("\n" + "="*50)
    print("所有测试完成！")


if __name__ == '__main__':
    main()
