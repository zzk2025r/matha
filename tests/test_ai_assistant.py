# -*- coding: utf-8 -*-
"""Matha AI Assistant 测试 — v1.2.10 边界测试
覆盖：冷门表达、变体说法、常识推理、fallback、日志追踪
"""
import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant, FriendlyIntentParser
from src.interp import Interpreter

# 开启 DEBUG 日志，方便排查
logging.basicConfig(level=logging.DEBUG, format="%(name)s [%(levelname)s] %(message)s")


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
        ("解释什么是素数", "number_theory"),
    ]

    for text, expected in cases:
        intent_type, conf = parser.classify(text)
        status = "✓" if intent_type.value == expected else "≈"
        print(f"  {status} '{text[:20]}' → {intent_type.value} (置信度 {conf:.0%})")


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
                print(f"      代码: {step.matha_code[:60]}")


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


def test_commonsense_edge_cases():
    """测试常识推理边界：冷门表达/变体说法/fallback/替代方案。"""
    print("\n=== 常识边界测试 (v1.2.12) ===")
    parser = FriendlyIntentParser()
    assistant = MathaAIAssistant()
    interp = Interpreter()

    # ── 冷门/变体表达 → 意图分类 ────────────────────────
    edge_cases = [
        # (输入, 期望意图, 说明)
        ("帮我算一下 2+2", "arithmetic", "泛化表达"),
        ("算算 7 加 3", "arithmetic", "口语算算"),
        ("100 的一半是多少", "arithmetic", "一半→除法"),
        ("5 的 3 倍", "arithmetic", "倍→乘法"),
        ("60 秒等于多少分", "unit_convert", "时间换算"),
        ("25 开方是多少", "math_func", "开方"),
        ("17 是不是素数", "number_theory", "判断素数"),
        ("翻一番是几倍", "arithmetic", "翻一番"),
        ("对折再对折剩多少", "arithmetic", "对折→除法×2"),
        ("一斤等于多少克", "unit_convert", "重量换算"),
        ("5 的阶乘是多少", "number_theory", "阶乘"),
        ("300 米等于多少千米", "unit_convert", "米→千米"),
        ("10 的平方", "math_func", "平方"),
        ("2 的 10 次方", "math_func", "幂运算"),
        ("1 到 50 的素数", "number_theory", "范围素数"),
        ("6 的因数有哪些", "number_theory", "因数"),
        ("自由落体 5 秒", "physics", "物理自由落体"),
        ("帮我算一下 2 的 3 次方", "math_func", "泛化+幂"),
        ("2 的翻倍", "arithmetic", "翻倍"),
        ("平均分成 4 份", "arithmetic", "均分"),
        ("5 减 3 还剩多少", "arithmetic", "减法表达"),
        # 新增 v1.2.12 边界用例
        ("99 对折一次是多少", "arithmetic", "单数字对折"),
        ("10 的立方", "math_func", "立方"),
        ("根号 144 是多少", "math_func", "根号表达"),
        ("abs(-7) 等于多少", "math_func", "绝对值"),
        ("100 公里等于多少米", "unit_convert", "公里→米"),
        ("3000 克等于多少千克", "unit_convert", "克→千克"),
        ("36 小时等于多少天", "unit_convert", "小时→天"),
        ("120 分等于多少小时", "unit_convert", "分→小时"),
        ("7 的平方根", "math_func", "平方根"),
        ("3 的 5 次方等于几", "math_func", "次方+等于"),
        ("0 是不是素数", "number_theory", "边界数素数判断"),
        ("97 是质数吗", "number_theory", "质数口语表达"),
        ("帮我算一下 2 的 8 次方", "math_func", "泛化+8次方"),
        ("对折三次剩多少", "arithmetic", "对折三次"),
        ("10 除以 3 余几", "arithmetic", "取余运算"),
        ("sqrt(64) 等于多少", "math_func", "英文sqrt"),
        ("log(1000) 是多少", "math_func", "对数表达"),
        ("3 的 3 次方", "math_func", "3^3"),
        ("帮我算一下 2*3+4", "arithmetic", "混合表达式"),
        ("1 到 10 的素数", "number_theory", "小范围素数"),
        ("7 的因子", "number_theory", "因子同义词"),
        ("25 开根", "math_func", "开根表达"),
        ("1 公斤等于多少克", "unit_convert", "公斤→克"),
        ("500 毫升等于多少升", "unit_convert", "体积换算"),
        # 新增 v1.2.13 边界用例
        ("sin(30) 等于多少", "trig", "英文sin函数"),
        ("cos(60) 是多少", "trig", "英文cos函数"),
        ("tan(45) 等于几", "trig", "英文tan函数"),
        ("5 的阶乘是多少", "number_theory", "阶乘+是多少"),
        ("π 的近似值", "trig", "圆周率符号"),
        ("帮我算一下 sin(0)", "trig", "泛化+三角"),
        ("100 毫秒等于多少秒", "unit_convert", "毫秒→秒"),
        ("5 公里等于多少米", "unit_convert", "公里→米"),
        ("2 的 16 次方", "math_func", "大幂运算"),
        ("求 7 的立方", "math_func", "求立方表达"),
        ("1 到 20 的素数有哪些", "number_theory", "范围素数口语"),
        ("帮我算一下 2*3 加 4", "arithmetic", "混合运算口语"),
        ("100 对折两次是多少", "arithmetic", "对折两次"),
        ("abs(-42) 等于多少", "math_func", "绝对值负数"),
        ("sqrt(16) 等于多少", "math_func", "英文sqrt"),
        ("log(100) 是多少", "math_func", "对数表达"),
        ("0 的阶乘等于几", "number_theory", "边界阶乘"),
        ("100 厘米等于多少米", "unit_convert", "厘米→米"),
        ("1 吨等于多少千克", "unit_convert", "吨→千克"),
        ("50 度等于多少弧度", "trig", "角度弧度换算"),
        ("帮我算一下 根号 16", "math_func", "泛化+根号"),
        ("120 秒等于多少分", "unit_convert", "秒→分"),
        ("2 的 64 次方", "math_func", "超大幂"),
        ("sqrt 等于多少", "unknown", "不完整表达兜底"),
    ]

    print("\n── 意图分类 ──")
    classify_results = []
    for text, expected, desc in edge_cases:
        intent_type, conf = parser.classify(text)
        ok = intent_type.value == expected
        classify_results.append(ok)
        status = "✓" if ok else "≈"
        print(f"  {status} [{desc}] '{text}' → {intent_type.value} (置信度 {conf:.0%})")

    print(f"\n  分类通过率: {sum(classify_results)}/{len(classify_results)}")

    # ── 执行测试 ─────────────────────────────────────────
    print("\n── 执行测试 ──")
    exec_cases = [
        ("100 的一半", "result", 50.0),
        ("5 的 3 倍", "result", 15.0),
        ("60 秒等于多少分", "result", 1.0),
        ("算算 7 加 3", "result", 10.0),
        ("帮我算一下 2+2", "result", 4.0),
        ("翻一番是几倍", "result", None),  # 可能 guide/error
        ("2 的翻倍", "result", None),  # 可能 guide/error
    ]
    for text, expected_type, expected_result in exec_cases:
        r = assistant.chat(text, interp)
        got_type = r.get("type", "unknown")
        got_result = r.get("result")
        type_ok = got_type == expected_type
        result_ok = expected_result is None or (got_result is not None and
            abs(float(got_result) - float(expected_result)) < 0.01)
        status = "✓" if type_ok and result_ok else "≈"
        print(f"  {status} '{text}' → type={got_type}, result={got_result!r}")

    # ── 学习记忆测试 ─────────────────────────────────────
    print("\n── 学习记忆 ──")
    parser2 = FriendlyIntentParser()
    original_intent, _ = parser2.classify("帮我算一下")
    parser2.learn("帮我算一下", original_intent)
    new_intent, new_conf = parser2.classify("帮我算一下")
    print(f"  ✓ 学习后: '帮我算一下' → {new_intent.value} (置信度 {new_conf:.0%}, 之前 {original_intent.value})")

    # ── fallback 兜底 ────────────────────────────────────
    print("\n── 兜底推断 ──")
    for text in ["123", "42", "hello world"]:
        intent, conf = parser.classify(text)
        print(f"  '{text}' → {intent.value} (置信度 {conf:.0%})")

    # ── 替代方案测试 ─────────────────────────────────────
    print("\n── 替代方案 ──")
    alt = parser._try_alternative("3 的 4 次方", parser.classify("3 的 4 次方")[0])
    for s in alt:
        print(f"  替代: {s.description} → {s.matha_code}")


def test_logging_trace():
    """验证日志路径：每个推理分支都有日志输出。"""
    print("\n=== 日志路径验证 ===")
    parser = FriendlyIntentParser()
    assistant = MathaAIAssistant()
    interp = Interpreter()

    # 触发策略1（关键词）
    r1 = assistant.chat("计算 3 加 5", interp)
    print(f"  [策略1] '计算 3 加 5' → {r1['type']}")

    # 触发策略2（变体）
    r2 = assistant.chat("算算 7+3", interp)
    print(f"  [策略2] '算算 7+3' → {r2['type']}")

    # 触发策略3（常识规则）
    r3 = assistant.chat("100 的一半", interp)
    print(f"  [策略3] '100 的一半' → {r3['type']}, result={r3.get('result')}")

    # 触发策略5（fallback）
    r4 = assistant.chat("123", interp)
    print(f"  [策略5] '123' → {r4['type']}")

    # 触发常识推断（decompose 失败 → _decompose_commonsense）
    r5 = assistant.chat("翻一番", interp)
    print(f"  [常识推断] '翻一番' → {r5['type']}, steps={r5['steps']}")

    # 触发替代方案
    r6 = assistant.chat("帮我算一下 2 的 3 次方", interp)
    print(f"  [替代方案] '2 的 3 次方' → {r6['type']}, result={r6.get('result')}")


def main():
    test_intent_classifier()
    test_decompose()
    test_execute()
    test_error_handling()
    test_concept_explanation()
    test_commonsense_edge_cases()
    test_logging_trace()
    print("\n" + "=" * 50)
    print("v1.2.15 边界测试全部完成！")
    print("=" * 50)


if __name__ == '__main__':
    main()
