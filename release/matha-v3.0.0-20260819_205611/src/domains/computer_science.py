# -*- coding: utf-8 -*-
"""Matha 计算机科学领域模块：算法复杂度、数据结构、信息论、图论。

覆盖：
  1) 算法复杂度：大O计算、递归方程求解
  2) 数据结构：栈/队列/链表操作模拟
  3) 信息论：熵、互信息、编码效率
  4) 图论：遍历计数、最短路径估算
  5) 离散数学：布尔代数、集合运算、逻辑电路
"""

from __future__ import annotations
import math
from typing import Any

# ============================================================
# 柯里化工具
# ============================================================
def _curry1(func):
    def with_first(a):
        return func(a)
    return with_first

def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1

def _curry4(func):
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: func(a, b, c, d)
            return w3
        return w2
    return w1


# ============================================================
# 算法复杂度
# ============================================================

def _大O比较(n, threshold=1000000):
    """根据 n 的大小估算可用算法复杂度等级。

    n ≤ 10:      O(n!) 可行
    n ≤ 20:      O(2^n) 可行
    n ≤ 1000:    O(n³)  可行
    n ≤ 100000:  O(n²)  可行
    更大:        O(n log n) 或 O(n) 必须
    """
    if n <= 0:
        return "O(1)"
    if n <= 10:
        return "O(n!) 可行"
    if n <= 20:
        return "O(2^n) 可行"
    if n <= 100:
        return "O(n³) 可行"
    if n <= 10000:
        return "O(n²) 可行"
    if n <= 1000000:
        return "O(n log n) 推荐"
    return "O(n) 必需"


def _递归深度估算(T_n, n):
    """估算递归算法的调用次数（简化版）。

    T(n) = T(n-1) + O(1)  →  O(n)
    T(n) = 2·T(n-1) + O(1) →  O(2^n)
    T(n) = T(n-1) + T(n-2)  →  O(φ^n)  斐波那契
    """
    if n <= 0:
        return 1
    # 简单线性递归
    return n + 1


# ============================================================
# 信息论
# ============================================================

def _香农熵(probabilities):
    """计算离散随机变量的香农熵 H = -Σ p·log2(p)。"""
    if not isinstance(probabilities, (list, tuple)):
        probabilities = list(probabilities)
    H = 0.0
    for p in probabilities:
        if p > 0:
            H -= p * math.log2(p)
    return H


def _信息量(probability):
    """单个事件的自信息 I = -log2(p)。"""
    if probability <= 0:
        return float('inf')
    return -math.log2(probability)


def _编码效率(熵, 平均码长):
    """编码效率 η = H/L，衡量编码接近理论极限的程度。"""
    if 平均码长 <= 0:
        return 0.0
    return 熵 / 平均码长


# ============================================================
# 图论
# ============================================================

def _完全图边数(n):
    """n 个顶点的完全图边数：n(n-1)/2。"""
    return n * (n - 1) // 2


def _树边数(n):
    """n 个顶点的树边数：n-1。"""
    return n - 1


def _dfs遍历数(n, branching=2):
    """DFS 遍历节点数上界估算。"""
    return n


def _最短路径估算(n, m):
    """Dijkstra 最短路径复杂度估算。"""
    return n * math.log(n) + m if n > 0 else 0


# ============================================================
# 离散数学
# ============================================================

def _德摩根定律_not_and(a, b):
    """¬(a ∧ b) ≡ ¬a ∨ ¬b。"""
    return not (a and b)


def _德摩根定律_not_or(a, b):
    """¬(a ∨ b) ≡ ¬a ∧ ¬b。"""
    return not (a or b)


def _蕴含等价(p, q):
    """p → q ≡ ¬p ∨ q。"""
    return (not p) or q


def _双蕴含等价(p, q):
    """p ↔ q ≡ (p → q) ∧ (q → p)。"""
    return ((not p) or q) and ((not q) or p)


def _真值表行数(n):
    """n 个命题变元的真值表行数：2^n。"""
    return 2 ** n


# ============================================================
# 数据结构模拟
# ============================================================

def _栈操作操作(操作序列):
    """模拟栈操作序列，返回最终栈状态和错误次数。

    操作序列：["push", 1, "push", 2, "pop", ...]
    """
    stack = []
    errors = 0
    i = 0
    while i < len(操作序列):
        op = 操作序列[i]
        if op == "push":
            if i + 1 < len(操作序列):
                stack.append(操作序列[i + 1])
                i += 2
            else:
                errors += 1
                i += 1
        elif op == "pop":
            if stack:
                stack.pop()
            else:
                errors += 1
            i += 1
        elif op == "peek":
            if not stack:
                errors += 1
            i += 1
        else:
            i += 1
    return {"栈": stack, "错误数": errors}


def _队列操作操作(操作序列):
    """模拟队列操作序列，返回最终队列状态和错误次数。"""
    queue = []
    errors = 0
    i = 0
    while i < len(操作序列):
        op = 操作序列[i]
        if op == "enqueue":
            if i + 1 < len(操作序列):
                queue.append(操作序列[i + 1])
                i += 2
            else:
                errors += 1
                i += 1
        elif op == "dequeue":
            if queue:
                queue.pop(0)
            else:
                errors += 1
            i += 1
        elif op == "front":
            if not queue:
                errors += 1
            i += 1
        else:
            i += 1
    return {"队列": queue, "错误数": errors}


# ============================================================
# 注册
# ============================================================

def _register_computer_science(builtins: dict) -> None:
    """将计算机科学领域内建注册到解释器 builtins。"""
    # 算法复杂度
    builtins["大O估算"] = _curry2(_大O比较)
    builtins["递归深度估算"] = _curry2(_递归深度估算)

    # 信息论
    builtins["香农熵"] = _curry1(_香农熵)
    builtins["信息量"] = _curry1(_信息量)
    builtins["编码效率"] = _curry2(_编码效率)

    # 图论
    builtins["完全图边数"] = _curry1(_完全图边数)
    builtins["树边数"] = _curry1(_树边数)
    builtins["DFS节点数"] = _curry2(_dfs遍历数)
    builtins["最短路径复杂度"] = _curry2(_最短路径估算)

    # 离散数学
    builtins["德摩根_与"] = _curry2(_德摩根定律_not_and)
    builtins["德摩根_或"] = _curry2(_德摩根定律_not_or)
    builtins["蕴含等价"] = _curry2(_蕴含等价)
    builtins["双蕴含等价"] = _curry2(_双蕴含等价)
    builtins["真值表行数"] = _curry1(_真值表行数)

    # 数据结构
    builtins["栈模拟"] = _curry1(_栈操作操作)
    builtins["队列模拟"] = _curry1(_队列操作操作)


def _register_computer_science_symtab_names() -> list[str]:
    """返回计算机科学领域所有内建名。"""
    return [
        "大O估算", "递归深度估算",
        "香农熵", "信息量", "编码效率",
        "完全图边数", "树边数", "DFS节点数", "最短路径复杂度",
        "德摩根_与", "德摩根_或", "蕴含等价", "双蕴含等价", "真值表行数",
        "栈模拟", "队列模拟",
    ]
