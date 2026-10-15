"""用户自定义运算符注册表（``@define_op`` 的运行时侧）。

语法（见 ``Parser._parse_define_op``）::

    @define_op: <符号> = <优先级> | <结合性>  [ => <函数名> ]

- ``<符号>``、``<优先级>``、``<结合性>``：注册一个可在表达式中**使用**的二元
  运算符；优先级 / 结合性决定多个自定义运算符并存时的结合方式。
- ``=> <函数名>``（可选）：把运算符**绑定到具名函数**——求值 ``a <符号> b``
  时调用该全局函数，传入左右操作数。未给出绑定时，使用该运算符会报
  ``运算符 <符号> 未绑定实现``。

本模块只做注册与查询，不改变内置运算符语义。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomOp:
    """一条自定义运算符定义。"""
    symbol: str
    precedence: int          # 越大越紧（仅在多个自定义运算符间比较）
    assoc: str               # "left" | "right"
    handler: str | None = None  # 绑定的全局函数名；None = 未绑定


#: symbol → CustomOp
REGISTRY: dict[str, CustomOp] = {}


def register(symbol: str, precedence: int, assoc: str,
             handler: str | None = None) -> CustomOp:
    """注册（或覆盖）一个自定义运算符。"""
    if assoc not in ("left", "right"):
        raise ValueError(f"结合性应为 left 或 right，实际: {assoc!r}")
    op = CustomOp(symbol=symbol, precedence=precedence, assoc=assoc,
                  handler=handler)
    REGISTRY[symbol] = op
    return op


def get(symbol: str) -> CustomOp | None:
    return REGISTRY.get(symbol)


def is_custom_op(symbol: str) -> bool:
    return symbol in REGISTRY


def clear() -> None:
    """清空注册表（主要用于测试隔离）。"""
    REGISTRY.clear()
