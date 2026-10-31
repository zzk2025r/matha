# -*- coding: utf-8 -*-
"""特化解释器：内联缓存（Inline Caching）与类型反馈。

对应 CPython 3.11+ 的 specializing adaptive interpreter：解释器不再为每个
二元运算反复「按运算符字符串逐条 if/elif 匹配 + 逐条 isinstance 类型检查」，
而是在**调用点**（AST 节点）上学习操作数的类型形状，形状稳定后直接走
**专用快速通道**（如整数加法直接 ``operator.add``）。

工作方式：

1. 每个调用点挂一个单态内联缓存 :class:`InlineCache`，记录最近观测到的
   ``(运算符, 左类型, 右类型)``。
2. 连续 :data:`IC_THRESHOLD` 次形状一致后，为该形状安装专用实现
   （``specialize`` 返回的可调用对象），跳过通用路径。
3. 形状一旦改变（多态调用点），缓存**重新武装**并退化为单态。

安全性：``specialize`` 只对**逐一核对过语义等价**的 (运算符, 类型) 组合
返回专用实现；无法保证等价的组合一律返回 ``None``（回落到通用路径）。
专用实现的启用条件是「两侧类型与缓存记录**完全一致**」，因此不会因为
类型变化而产生错误结果。
"""
from __future__ import annotations

import operator

#: 触发阈值：连续多少次形状一致后启用专用快速通道。
IC_THRESHOLD = 10

#: 数值类（bool 是 int 的子类，通用路径里同样按数值处理）。
_NUMERIC = frozenset({int, float, bool})
#: 整数类（通用路径里用 isinstance(x, int) 判定，bool 同样命中）。
_INTISH = frozenset({int, bool})
#: 通用路径里 ``in`` 右侧允许的容器类型。
_SEQUENCE = frozenset({list, tuple, str, dict, set})

#: 位运算：通用路径要求两侧都是 int（bool 亦命中 isinstance(int)）。
_BITOPS = {
    "&": operator.and_,
    "|": operator.or_,
    "⊕": operator.xor,
    "<<": operator.lshift,
    ">>": operator.rshift,
}


def _add_str_left(l, r):
    """``str + 数值``：通用路径会先把右操作数转成字符串。"""
    return l + str(r)


def _add_str_right(l, r):
    """``数值 + str``：通用路径会先把左操作数转成字符串。"""
    return str(l) + r


def _identity(l, r):
    return l is r


def _identity_strict(l, r):
    """``===``：同一对象且类型完全相同。"""
    return (l is r) and type(l) is type(r)


def _identity_strict_not(l, r):
    return not ((l is r) and type(l) is type(r))


def _null_coalesce(l, r):
    return l if l is not None else r


def _contains(l, r):
    return l in r


def _and(l, r):
    return l and r


def _or(l, r):
    return l or r


#: 比较类运算：通用路径没有任何类型检查，直接委托给 ``operator`` 即可
#: （``operator.lt(a, b)`` 与 ``a < b`` 语义完全一致）。
_COMPARISONS = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "=": operator.eq,
    "!=": operator.ne,
    "is": _identity,
    "===": _identity_strict,
    "!==": _identity_strict_not,
    "??": _null_coalesce,
}


def _is_virtual(cls: type) -> bool:
    """判断类型是否为宽容值 ``VirtualSymbol``。

    宽容值在通用路径里被**先行拦截**（运算结果仍是宽容值），绝不能进入
    专用通道，否则会丢失「宽容」语义。此处做纵深防御。
    """
    from src.interp import VirtualSymbol
    return cls is VirtualSymbol


def specialize(op: str, ltype: type, rtype: type):
    """为 ``(运算符, 左类型, 右类型)`` 生成语义等价的专用实现。

    返回 ``None`` 表示该形状不做特化（走通用路径）。
    """
    # 宽容值（VirtualSymbol）：通用路径先行拦截，语义完全不同 → 永不特化。
    if _is_virtual(ltype) or _is_virtual(rtype):
        return None
    # ---- 比较/逻辑：通用路径无类型检查，可对任意类型特化 ----
    fast = _COMPARISONS.get(op)
    if fast is not None:
        return fast

    if op == "+":
        if ltype in _NUMERIC and rtype in _NUMERIC:
            return operator.add
        if ltype is str and rtype is str:
            return operator.add
        if ltype is str and rtype in _NUMERIC:
            return _add_str_left
        if ltype in _NUMERIC and rtype is str:
            return _add_str_right
        if ltype is list and rtype is list:
            return operator.add
        if ltype is tuple and rtype is tuple:
            return operator.add
        return None

    if op == "-":
        # 通用路径对 str/list 操作数抛错，其余（含 float）直接相减
        if ltype in _NUMERIC and rtype in _NUMERIC:
            return operator.sub
        return None

    if op == "*":
        # 通用路径允许：数值×数值、str×int、int×str
        if ltype in _NUMERIC and rtype in _NUMERIC:
            return operator.mul
        if ltype is str and rtype is int:
            return operator.mul
        if ltype is int and rtype is str:
            return operator.mul
        return None

    if op in ("**", "^"):
        # 通用路径：非 None 的 l ** r（^ 与 ** 同义，均为次方）
        if ltype in _NUMERIC and rtype in _NUMERIC:
            return operator.pow
        return None

    if op in ("&", "|", "⊕", "<<", ">>"):
        # 通用路径要求两侧都是 int（bool 亦命中 isinstance(int)）
        if ltype in _INTISH and rtype in _INTISH:
            return _BITOPS[op]
        return None

    if op == "in":
        if rtype in _SEQUENCE:
            return _contains
        return None

    if op == "and":
        return _and
    if op == "or":
        return _or
    if op == "&&":
        return _and
    if op == "||":
        return _or

    # 其余运算（集合运算、→ 调用、/ % // 的除零检查等）不做特化：
    # 通用路径带有额外校验或副作用，必须原样保留。
    return None


class InlineCache:
    """单个调用点的单态内联缓存。

    字段：

    - ``op`` / ``ltype`` / ``rtype``：最近一次观测到的形状；
    - ``hits``：当前形状的连续命中次数；
    - ``fast``：该形状的专用实现（``None`` = 不可特化，走通用路径）。
    """

    __slots__ = ("op", "ltype", "rtype", "hits", "fast")

    def __init__(self):
        self.op = None
        self.ltype = None
        self.rtype = None
        self.hits = 0
        self.fast = None

    def fast_for(self, op: str, l: object, r: object):
        """返回该形状的专用实现；未达阈值或不可特化时返回 ``None``。

        热路径刻意写成「最少属性访问 + 身份比较」：调用点固定（同一 AST 节点），
        因此绝大多数调用都走第一层命中分支。
        """
        ltype = type(l)
        if ltype is self.ltype:
            rtype = type(r)
            if rtype is self.rtype and (self.op is op or self.op == op):
                self.hits += 1
                if self.hits >= IC_THRESHOLD:
                    return self.fast
                return None
        # 形状变化 → 重新武装（退化为单态，重新学习）
        rtype = type(r)
        self.op = op
        self.ltype = ltype
        self.rtype = rtype
        self.hits = 1
        self.fast = specialize(op, ltype, rtype)
        return None

    def reset(self) -> None:
        self.op = None
        self.ltype = None
        self.rtype = None
        self.hits = 0
        self.fast = None


__all__ = ["InlineCache", "specialize", "IC_THRESHOLD"]
