# -*- coding: utf-8 -*-
"""Matha Jupyter 集成 — Notebook 示例

演示如何在 Jupyter Notebook 中使用 Matha 意图分解引擎。
"""
from __future__ import annotations
import sys
import math
sys.path.insert(0, '.')

# ============================================================
# 1. 基本用法
# ============================================================

from src.intent.intent_decomposer import IntentDecomposer
from src.intent.llm_parser import LLMIntentParser
from src.intent.mir_generator import MIRGenerator
from src.stdlib.arithmetic import sieve_of_eratosthenes, factorial
from src.stdlib.algebra import solve_quadratic, factor_integer
from src.stdlib.calculus import derivative, integral, newton_method
from src.stdlib.logic import (
    AND, OR, NOT, IMPLIES, IFF, XOR,
    truth_table, print_truth_table,
    set_union, set_intersection, set_difference,
    check_tautology, check_contradiction
)

print("=" * 60)
print("  Matha Jupyter 集成示例")
print("=" * 60)

# ============================================================
# 2. 意图分解引擎测试
# ============================================================

print("\n【2. 意图分解引擎】")

ide = IntentDecomposer()

test_cases = [
    "计算 100 以内所有素数",
    "求解 x^2 - 3x + 2 = 0",
    "计算 sin(x) 在 [0, π] 上的积分",
    "验证 √2 是无理数",
]

for text in test_cases:
    root = ide.decompose(text)
    print(f"\n  输入: {text}")
    print(f"  类型: {root.node_type.name}")
    print(f"  置信度: {root.confidence:.2f}")
    print(f"  子意图数: {len(root.sub_intents)}")

# ============================================================
# 3. LLM 意图解析器测试
# ============================================================

print("\n【3. LLM 意图解析器】")

parser = LLMIntentParser()

intent = parser.parse("计算 100 以内所有素数")
print(f"  输入: 计算 100 以内所有素数")
print(f"  意图类型: {intent.intent_type.name}")
print(f"  置信度: {intent.confidence:.2f}")
print(f"  建议代码: {intent.suggested_code}")

# ============================================================
# 4. MIR 代码生成器测试
# ============================================================

print("\n【4. MIR 代码生成器】")

generator = MIRGenerator()
mir_node = generator.generate(intent)
print(f"  生成的 MIR 代码:")
print(mir_node.to_math_code())

# ============================================================
# 5. 标准库测试
# ============================================================

print("\n【5. 标准库测试】")

# 算术
print(f"  素数筛(100): {len(sieve_of_eratosthenes(100))} 个素数")
print(f"  5! = {factorial(5)}")

# 代数
print(f"  x²-3x+2=0 的解: {solve_quadratic(1, -3, 2)}")
print(f"  60 的因式分解: {factor_integer(60)}")

# 微积分
print(f"  d/dx(x²) at x=3: {derivative(lambda x: x**2, 3):.4f}")
print(f"  ∫[0,π] sin(x)dx = {integral(lambda x: math.sin(x), 0, math.pi):.4f}")

root, iters = newton_method(lambda x: x**2 - 2, 1.0)
print(f"  √2 ≈ {root:.10f} ({iters} 次迭代)")

# 逻辑
print(f"  P→Q 真值表:")
print_truth_table(2, lambda v: IMPLIES(v[0], v[1]), ["P", "Q"])

# ============================================================
# 6. 完整示例：计算 100 以内素数
# ============================================================

print("\n【6. 完整示例】")

text = "计算 100 以内所有素数"
print(f"  输入: {text}")

# 意图分解
root = ide.decompose(text)
print(f"  意图类型: {root.node_type.name}")

# LLM 解析
intent = parser.parse(text)
print(f"  置信度: {intent.confidence:.2f}")

# MIR 生成
mir = generator.generate(intent)
print(f"  MIR 代码: {mir.to_math_code()}")

# 执行
primes = sieve_of_eratosthenes(100)
print(f"  结果: {primes}")
print(f"  共 {len(primes)} 个素数")

print("\n" + "=" * 60)
print("  示例完成")
print("=" * 60)
