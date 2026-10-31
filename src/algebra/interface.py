"""代数数处理接口 —— 核心层只声明契约，严禁硬编码任何具体实现。

契约要点（对应「插件化彻底隔离风险」的四条要求）：

1. **标准接口**：:class:`AlgebraicNumberPrinter` 协议 + 中性 :data:`Term` 项模型。
   内核与门面只依赖这两者；具体如何把 ``sqrt(2)`` 打印成精确根式，本层一概不知。
2. **核心保持纯净**：本模块仅用标准库，不 import 纯内核、不 import sympy，
   与 103 个符号锁正交 —— 加载与否都不改内核既有 double 打印行为。
3. **外部插件实现**：插件（如 :mod:`src.algebra.algebra_plugin`）实现本协议，
   在注册表登记自身；内核代码零改动。
4. **动态加载**：:func:`load_plugin` 显式加载并激活；未加载时
   :func:`active_printer` 返回 ``None``，:func:`render_with_plugin` 走默认渲染，
   Matha 仍是极简、极速、零风险的基础核心。

中性项模型刻意**不携带任何内核类型**：门面在集成步把内核表达式（其
``.op`` / ``.args`` / 有理叶子）映射为 ``Const`` / ``Symbol`` / ``BinOp`` /
``UnaryOp``，插件只见到这棵树，从而物理上无法耦合内核内部实现。
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol, Union, runtime_checkable

# ============================================================
# 中性代数项模型（插件唯一可见的数据形状）
# ============================================================


@dataclass(frozen=True)
class Const:
    """一个精确有理常数（含整数）。value 恒为 Fraction，避免浮点泄漏进契约。"""

    value: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.value, Fraction):
            object.__setattr__(self, "value", Fraction(self.value))


@dataclass(frozen=True)
class Symbol:
    """一个符号（如 x）。代数数打印只处理常数项，符号出现即视为不可渲染。"""

    name: str


@dataclass(frozen=True)
class BinOp:
    """二元运算节点。op ∈ {'+', '-', '*', '/', '^'}。"""

    op: str
    left: "Term"
    right: "Term"


@dataclass(frozen=True)
class UnaryOp:
    """一元运算节点。op ∈ {'sqrt', '-', '+'}。"""

    op: str
    operand: "Term"


Term = Union[Const, Symbol, BinOp, UnaryOp]

BIN_OPS = frozenset({"+", "-", "*", "/", "^"})
UNARY_OPS = frozenset({"sqrt", "-", "+"})


# ============================================================
# 打印器协议
# ============================================================


@runtime_checkable
class AlgebraicNumberPrinter(Protocol):
    """代数数精确打印器契约。

    实现方须保证 ``render`` 为纯函数、无副作用，且在无法给出**精确**表示时
    返回 ``None``（表示「交回默认渲染」），严禁臆造近似值冒充精确结果。
    """

    @property
    def name(self) -> str:
        ...

    def can_render(self, term: Term) -> bool:
        """快速判断该树是否落在本打印器的精确表示能力内。"""
        ...

    def render(self, term: Term, *, tol: float = 1e-9) -> str | None:
        """返回精确字符串表示；不适用时返回 ``None`` 让调用方回退默认。"""
        ...


# ============================================================
# 注册表（进程内；内核启动时默认空 → 零成本、零影响）
# ============================================================

_PRINTERS: dict[str, AlgebraicNumberPrinter] = {}
_ACTIVE: str | None = None

#: 短名 -> 模块路径。load_plugin 优先查此表，也接受完整点分路径。
_BUILTIN_ALIASES: dict[str, str] = {
    "algebra": "src.algebra.algebra_plugin",
    "algebra_plugin": "src.algebra.algebra_plugin",
}


def register_printer(printer: AlgebraicNumberPrinter, *, activate: bool = False) -> None:
    """登记一个打印器；同名覆盖。``activate=True`` 时同时设为当前生效打印器。"""
    global _ACTIVE
    if not isinstance(printer, AlgebraicNumberPrinter):
        raise TypeError(
            f"对象未实现 AlgebraicNumberPrinter 协议：{type(printer).__name__}")
    _PRINTERS[printer.name] = printer
    if activate or _ACTIVE is None:
        # 首个登记的打印器默认生效，省去调用方显式 set_active。
        _ACTIVE = printer.name


def unregister_printer(name: str) -> bool:
    global _ACTIVE
    if name not in _PRINTERS:
        return False
    del _PRINTERS[name]
    if _ACTIVE == name:
        _ACTIVE = next(iter(_PRINTERS), None)
    return True


def set_active(name: str | None) -> None:
    """切换当前生效打印器；``None`` 表示回到默认渲染。未登记名报错。"""
    if name is not None and name not in _PRINTERS:
        raise KeyError(f"未登记的打印器：{name!r}（先 load_plugin 或 register_printer）")
    global _ACTIVE
    _ACTIVE = name


def active_printer() -> AlgebraicNumberPrinter | None:
    """当前生效打印器；未加载任何插件时为 ``None``（核心保持极简零风险）。"""
    return _PRINTERS.get(_ACTIVE) if _ACTIVE else None


def load_plugin(spec: str) -> AlgebraicNumberPrinter:
    """动态加载并激活一个代数数打印插件。

    ``spec`` 可为短名（见 :data:`_BUILTIN_ALIASES`，如 ``"algebra"``）或完整
    点分模块路径。模块须暴露模块级 ``PLUGIN``（实现
    :class:`AlgebraicNumberPrinter`）。加载失败抛原异常，绝不静默降级为假成功。
    """
    module_path = _BUILTIN_ALIASES.get(spec, spec)
    module = importlib.import_module(module_path)
    printer = getattr(module, "PLUGIN", None)
    if printer is None:
        raise AttributeError(
            f"模块 {module_path} 未导出 PLUGIN（应为 AlgebraicNumberPrinter 实例）")
    register_printer(printer, activate=True)
    return printer


def loaded_names() -> list[str]:
    return sorted(_PRINTERS)


# ============================================================
# 渲染入口：门面集成点（本步仅提供函数，尚未接入门面）
# ============================================================


def render_default(term: Term) -> str:
    """默认渲染 —— 中性树的可读字符串，供无插件时回退。

    注意：门面**当前**用的是内核自带的 double 打印；本函数只在集成步替换内核
    打印时才会被调用。此处给出与内核 double 风格一致的基础实现，作为「未加载
    插件 = 行为不变」的锚点。数值以 Fraction 精确存储，展示时转 float 复现旧观感。
    """
    if isinstance(term, Const):
        v = float(term.value)
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(term, Symbol):
        return term.name
    if isinstance(term, UnaryOp):
        if term.op == "-":
            return f"(-{render_default(term.operand)})"
        if term.op == "sqrt":
            return f"sqrt({render_default(term.operand)})"
        return render_default(term.operand)
    if isinstance(term, BinOp):
        return f"({render_default(term.left)} {term.op} {render_default(term.right)})"
    raise TypeError(f"未知项类型：{type(term).__name__}")


def render_with_plugin(term: Term, *, tol: float = 1e-9) -> str:
    """先问当前生效插件要精确表示，拿不到就用 :func:`render_default`。

    这是插件化架构下门面对外渲染的**唯一**建议入口：加载插件后自动精确，
    未加载时（active_printer() is None）行为完全等同默认，核心零风险。
    """
    printer = active_printer()
    if printer is not None:
        out = printer.render(term, tol=tol)
        if out is not None:
            return out
    return render_default(term)


#: 浮点字面量：至少含一位小数（可带指数）。不匹配整数/分数，避开 `x**5/120` 等。
_FLOAT_LIT_RE = re.compile(r"\d+\.\d+(?:[eE][-+]?\d+)?")


def decorate_numeric(text: str, *, printer: AlgebraicNumberPrinter | None = None,
                     tol: float = 1e-9) -> str:
    """把 ``text`` 里的**浮点字面量**逐个交给精确打印器尝试还原为根式。

    这是门面（如 :mod:`src.stdlib.calculus_symbolic`）在发射内核 ``to_str`` 文本后的
    **唯一集成点**。设计保证无损：

      * 未加载任何打印器（``active_printer() is None``）时原样返回 ``text``，
        输出与未接入前逐字节相同 —— 103 个符号锁/黄金测试不受影响；
      * 仅替换打印器能**可证精确**命中的 token（``render`` 返回非 ``None``）；
        超越数/高次根等回不了的一律保留原 double 写法，绝不臆造；
      * 只碰带小数点的字面量，不碰整数/已为分数的有理系数（内核已还原）。
    """
    pr = printer if printer is not None else active_printer()
    if pr is None:
        return text

    def _repl(m: "re.Match[str]") -> str:
        tok = m.group(0)
        try:
            v = float(tok)
        except ValueError:
            return tok
        out = pr.render(Const(Fraction(v)), tol=tol)
        return out if (out is not None and out != tok) else tok

    return _FLOAT_LIT_RE.sub(_repl, text)


__all__ = [
    "Const", "Symbol", "BinOp", "UnaryOp", "Term",
    "BIN_OPS", "UNARY_OPS",
    "AlgebraicNumberPrinter",
    "register_printer", "unregister_printer", "set_active", "active_printer",
    "load_plugin", "loaded_names",
    "render_default", "render_with_plugin", "decorate_numeric",
]
