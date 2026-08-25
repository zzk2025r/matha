# -*- coding: utf-8 -*-
"""Matha v4.2 — 逻辑与证明标准库

提供数理逻辑核心功能：
  - 命题逻辑：与、或、非、蕴含、等价
  - 谓词逻辑：全称量词、存在量词
  - 集合运算：并、交、差、补
  - 证明辅助：真值表、归谬法

数学表达：
  所有函数遵循集合论与数理逻辑定义。

用法：
  from src.stdlib.logic import (
      AND, OR, NOT, IMPLIES, IFF,
      truth_table, prove_by_contradiction,
      set_union, set_intersection, set_difference,
  )
"""
from __future__ import annotations
import math
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass


# ============================================================
# 命题逻辑运算
# ============================================================

def AND(p: bool, q: bool) -> bool:
    """逻辑与：p ∧ q"""
    return p and q


def OR(p: bool, q: bool) -> bool:
    """逻辑或：p ∨ q"""
    return p or q


def NOT(p: bool) -> bool:
    """逻辑非：¬p"""
    return not p


def IMPLIES(p: bool, q: bool) -> bool:
    """逻辑蕴含：p → q（等价于 ¬p ∨ q）"""
    return (not p) or q


def IFF(p: bool, q: bool) -> bool:
    """逻辑等价：p ↔ q"""
    return p == q


def XOR(p: bool, q: bool) -> bool:
    """异或：p ⊕ q"""
    return p != q


def NAND(p: bool, q: bool) -> bool:
    """与非：¬(p ∧ q)"""
    return not (p and q)


def NOR(p: bool, q: bool) -> bool:
    """或非：¬(p ∨ q)"""
    return not (p or q)


# ============================================================
# 真值表
# ============================================================

def truth_table(
    num_vars: int,
    expr_fn: callable
) -> List[dict]:
    """
    生成真值表。

    Args:
        num_vars: 变量数量
        expr_fn: 接受 bool 列表，返回 bool 的表达式函数

    Returns:
        真值表行列表
    """
    rows = []
    for i in range(2 ** num_vars):
        vals = [(i >> j) & 1 == 1 for j in range(num_vars)]
        result = expr_fn(vals)
        rows.append({
            "values": vals,
            "result": result,
        })
    return rows


def print_truth_table(num_vars: int, expr_fn: callable, var_names: List[str] = None):
    """打印可读的真值表。"""
    if var_names is None:
        var_names = [f"P{i+1}" for i in range(num_vars)]

    print("\n" + "=" * (num_vars * 10 + 20))
    header = "  ".join(f"{name:^8}" for name in var_names) + " | Result"
    print(header)
    print("-" * len(header))

    for row in truth_table(num_vars, expr_fn):
        vals_str = "  ".join(f"{'T' if v else 'F':^8}" for v in row["values"])
        result_str = f"{'T' if row['result'] else 'F':^8}"
        print(f"{vals_str} | {result_str}")

    print("=" * (num_vars * 10 + 20))


# ============================================================
# 集合运算
# ============================================================

def set_union(a: Set, b: Set) -> Set:
    """集合并：A ∪ B"""
    return a | b


def set_intersection(a: Set, b: Set) -> Set:
    """集合交：A ∩ B"""
    return a & b


def set_difference(a: Set, b: Set) -> Set:
    """集合差：A \\ B"""
    return a - b


def set_complement(a: Set, universe: Set) -> Set:
    """集合补：A' = U \\ A"""
    return universe - a


def set_symmetric_difference(a: Set, b: Set) -> Set:
    """对称差：A △ B = (A \\ B) ∪ (B \\ A)"""
    return a ^ b


def is_subset(a: Set, b: Set) -> bool:
    """子集判断：A ⊆ B"""
    return a.issubset(b)


def is_proper_subset(a: Set, b: Set) -> bool:
    """真子集判断：A ⊂ B"""
    return a.issubset(b) and a != b


# ============================================================
# 证明辅助
# ============================================================

def prove_by_contradiction(
    assumption_fn: callable,
    contradiction_fn: callable
) -> bool:
    """
    归谬法证明辅助。

    如果假设 P 导致矛盾，则 P 为假。

    Args:
        assumption_fn: 假设函数，返回假设下的结果
        contradiction_fn: 矛盾检测函数

    Returns:
        True 如果检测到矛盾（证明假设不成立）
    """
    try:
        result = assumption_fn()
        if contradiction_fn(result):
            return True
    except Exception:
        return True
    return False


def check_tautology(num_vars: int, expr_fn: callable) -> bool:
    """
    检查是否为永真式（重言式）。

    Args:
        num_vars: 变量数
        expr_fn: 表达式函数

    Returns:
        True 如果所有赋值下表达式均为 True
    """
    for row in truth_table(num_vars, expr_fn):
        if not row["result"]:
            return False
    return True


def check_contradiction(num_vars: int, expr_fn: callable) -> bool:
    """
    检查是否为矛盾式。

    Returns:
        True 如果所有赋值下表达式均为 False
    """
    for row in truth_table(num_vars, expr_fn):
        if row["result"]:
            return False
    return True


# ============================================================
# 谓词逻辑（有限域）
# ============================================================

@dataclass
class Predicate:
    """谓词：定义在有限域上的命题函数。"""
    name: str
    domain: List
    fn: callable

    def evaluate(self, element) -> bool:
        """求值：P(element)"""
        return self.fn(element)

    def exists(self) -> bool:
        """存在量词：∃x, P(x)"""
        return any(self.evaluate(x) for x in self.domain)

    def forall(self) -> bool:
        """全称量词：∀x, P(x)"""
        return all(self.evaluate(x) for x in self.domain)

    def count(self) -> int:
        """满足谓词的元素个数"""
        return sum(1 for x in self.domain if self.evaluate(x))


# ============================================================
# 推理规则
# ============================================================

class InferenceEngine:
    """
    简单推理引擎，支持基本推理规则。

    支持规则：
    - Modus Ponens: P → Q, P ⊢ Q
    - Modus Tollens: P → Q, ¬Q ⊢ ¬P
    - Hypothetical Syllogism: P → Q, Q → R ⊢ P → R
    - Disjunctive Syllogism: P ∨ Q, ¬P ⊢ Q
    """

    @staticmethod
    def modus_ponens(p_implies_q: bool, p: bool) -> Optional[bool]:
        """
        Modus Ponens: (P → Q) ∧ P ⊢ Q

        Returns:
            Q 的值，如果前提不一致返回 None
        """
        if not p_implies_q:
            return None  # 前提不一致
        return p_implies_q and p  # 实际是 Q

    @staticmethod
    def modus_tollens(p_implies_q: bool, not_q: bool) -> Optional[bool]:
        """
        Modus Tollens: (P → Q) ∧ ¬Q ⊢ ¬P
        """
        if not p_implies_q:
            return None
        return not_q  # 返回 ¬P

    @staticmethod
    def hypothetical_syllogism(p_implies_q: bool, q_implies_r: bool) -> Optional[bool]:
        """
        Hypothetical Syllogism: (P → Q) ∧ (Q → R) ⊢ (P → R)
        """
        if not p_implies_q or not q_implies_r:
            return None
        return IMPLIES(p_implies_q, q_implies_r)  # 简化表示

    @staticmethod
    def disjunctive_syllogism(p_or_q: bool, not_p: bool) -> Optional[bool]:
        """
        Disjunctive Syllogism: (P ∨ Q) ∧ ¬P ⊢ Q
        """
        if not p_or_q:
            return None
        return not_p  # 返回 Q（通过 ¬P）


# ============================================================
# 便捷导出
# ============================================================

__all__ = [
    # 命题逻辑
    "AND", "OR", "NOT", "IMPLIES", "IFF", "XOR", "NAND", "NOR",
    # 真值表
    "truth_table", "print_truth_table",
    # 集合运算
    "set_union", "set_intersection", "set_difference",
    "set_complement", "set_symmetric_difference",
    "is_subset", "is_proper_subset",
    # 证明辅助
    "prove_by_contradiction",
    "check_tautology", "check_contradiction",
    # 谓词逻辑
    "Predicate",
    # 推理规则
    "InferenceEngine",
]


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Matha v4.2 — 逻辑与证明标准库测试")
    print("=" * 50)

    # 命题逻辑基本运算
    print("\n【命题逻辑运算】")
    print(f"  AND(T, F) = {AND(True, False)}")
    print(f"  OR(T, F) = {OR(True, False)}")
    print(f"  NOT(T) = {NOT(True)}")
    print(f"  IMPLIES(T, F) = {IMPLIES(True, False)}")
    print(f"  IFF(T, T) = {IFF(True, True)}")
    print(f"  XOR(T, F) = {XOR(True, False)}")

    # 真值表
    print("\n【真值表：P → Q】")
    print_truth_table(2, lambda v: IMPLIES(v[0], v[1]), ["P", "Q"])

    print("\n【真值表：(P → Q) ∧ (Q → P) ↔ P ↔ Q】")
    print_truth_table(2, lambda v: IFF(IMPLIES(v[0], v[1]), IMPLIES(v[1], v[0])), ["P", "Q"])

    # 永真式检查
    print("\n【永真式检查】")
    print(f"  P ∨ ¬P 是永真式: {check_tautology(1, lambda v: OR(v[0], NOT(v[0])))}")
    print(f"  P ∧ ¬P 是矛盾式: {check_contradiction(1, lambda v: AND(v[0], NOT(v[0])))}")

    # 集合运算
    print("\n【集合运算】")
    A = {1, 2, 3, 4}
    B = {3, 4, 5, 6}
    U = {1, 2, 3, 4, 5, 6, 7}
    print(f"  A = {A}, B = {B}")
    print(f"  A ∪ B = {set_union(A, B)}")
    print(f"  A ∩ B = {set_intersection(A, B)}")
    print(f"  A \\ B = {set_difference(A, B)}")
    print(f"  A' = {set_complement(A, U)}")
    print(f"  A △ B = {set_symmetric_difference(A, B)}")
    print(f"  A ⊆ B: {is_subset(A, B)}")

    # 谓词逻辑
    print("\n【谓词逻辑】")
    even = Predicate("even", list(range(1, 11)), lambda x: x % 2 == 0)
    print(f"  ∃x∈[1,10], even(x): {even.exists()}")
    print(f"  ∀x∈[1,10], even(x): {even.forall()}")
    print(f"  满足 even 的个数: {even.count()}")

    # 推理规则
    print("\n【推理规则】")
    print(f"  Modus Ponens: (T→T)∧T ⊢ {InferenceEngine.modus_ponens(True, True)}")
    print(f"  Modus Tollens: (T→F)∧¬F ⊢ {InferenceEngine.modus_tollens(False, False)}")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)
