"""Matha 标准库·符号微积分的 **.matha 实现**装载器（重构阶段 4）。

阶段 3 把符号微积分从 SymPy 迁到了纯标准库内核 :mod:`src.kernel.symbolic`
（下称 **stage0 引导实现**）。阶段 4 的要求是：这些能力最终由 Matha 自己的
标准库提供 —— 即 `matha/library/calculus_diff.matha`、`algebra_simplify.matha`、
`calculus_limit.matha`、`calculus_series.matha`，由核心主线
`mbc.compiler → mbc.vm` 编译执行；stage0 只保留为**引导实现 + 对拍基准**，
不再是默认计算路径。

本模块就是那条默认路径的宿主侧胶水：

  * :func:`source` / :func:`vm` —— 按依赖拓扑拼接四个库、一次编译、常驻一个 VM；
  * :func:`to_tagged` / :func:`from_tagged` —— stage0 的 :class:`Expr` 树与库内
    tagged-list 表示（``["num",v] ["var",s] ["add",a,b] …``）之间的无损转换；
  * :func:`derivative` / :func:`simplify` / :func:`limit_value` /
    :func:`maclaurin_coeffs` —— 各能力的库实现入口；
  * 覆盖不到时库内抛 ``不支持: …``，这里转成 :class:`MathaUnsupported`，
    **由调用方决定是否显式回退 stage0**，并计入 :data:`BACKEND_STATS`，
    使「走了哪条路、走了多少次」可被测试与文档核对，不存在静默降级。

口径说明：库内规范形是**完全化简**的（合并同类项、幂合并、常数归一），
返回给旧公开函数时统一经 :func:`from_tagged` 还原成 :class:`Expr`，
再由 stage0 的 `to_str` 发射，公开字符串格式不因切换后端而改变。
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from src.kernel import exec_api
from src.kernel.symbolic import (
    Add, Div, Expr, FuncCall, Log, Mul, Neg, Num, Pow, Sub, Var,
)

__all__ = [
    "LIB_FILES", "LIB_PATHS", "source", "vm", "reset_vm",
    "to_tagged", "from_tagged", "tagged_text",
    "derivative", "nth_derivative", "simplify", "expand",
    "limit_value", "maclaurin_terms", "maclaurin_coeffs",
    "BACKEND_STATS", "stats", "MathaUnsupported", "AVAILABLE", "available",
]

#: 依赖拓扑顺序：求导/规范形 → 代数化简（代入）→ 极限 → 级数。不可颠倒。
LIB_FILES = (
    "calculus_diff.matha",
    "algebra_simplify.matha",
    "calculus_limit.matha",
    "calculus_series.matha",
)

LIB_DIR = Path(__file__).resolve().parents[2] / "matha" / "library"
LIB_PATHS = [LIB_DIR / n for n in LIB_FILES]

#: 未就绪时（例如仓库被裁剪）门面直接走 stage0，但会在这里留痕，不假装跑过。
AVAILABLE: bool = all(p.is_file() for p in LIB_PATHS)

BACKEND_STATS: dict[str, int] = {"matha": 0, "stage0_fallback": 0, "unsupported": 0}


class MathaUnsupported(RuntimeError):
    """标准库显式声明「本能力未覆盖」——错误信息一律以 `不支持: ` 开头。"""


def stats() -> dict[str, int]:
    return dict(BACKEND_STATS)


def available() -> bool:
    return AVAILABLE


# ============================================================
# 装载
# ============================================================

_source: str | None = None
_vm = None


def source() -> str:
    """四个库拼接后的源码文本（含各自的注释头，便于逐行定位）。"""
    global _source
    if _source is None:
        if not AVAILABLE:
            raise MathaUnsupported("不支持: Matha 标准库文件缺失：" +
                                   ", ".join(str(p) for p in LIB_PATHS if not p.is_file()))
        _source = "\n".join(p.read_text(encoding="utf-8") for p in LIB_PATHS)
    return _source


def vm():
    """常驻 VM：编译一次标准库，后续按函数名直接调用（`mbc.vm.VM.call`）。"""
    global _vm
    if _vm is None:
        from src.mbc.vm import VM
        mod = exec_api.compile_module(source(), plugins="off")
        _vm = VM(mod)
        _vm.run()
    return _vm


def reset_vm() -> None:
    """丢弃常驻 VM（测试改库文件后用）。"""
    global _vm, _source
    _vm = None
    _source = None


def _call(fn: str, *args: Any) -> Any:
    """在常驻 VM 上调库函数；库内 `错误("不支持: …")` 一律升级为可判类型。

    只认 `不支持: ` 前缀，其它 RuntimeError 原样上抛 —— 避免把 VM 的真实
    缺陷（如 IndexError）误当成「能力未覆盖」而静默回退 stage0。
    """
    BACKEND_STATS["matha"] += 1
    try:
        return vm().call(fn, *args)
    except MathaUnsupported:
        BACKEND_STATS["unsupported"] += 1
        raise
    except RuntimeError as e:
        if str(e).startswith("不支持: "):
            BACKEND_STATS["unsupported"] += 1
            raise MathaUnsupported(str(e)) from e
        raise


# ============================================================
# Expr ↔ tagged list
# ============================================================

def to_tagged(e: Expr) -> list:
    """stage0 Expr 树 → 库内 tagged-list 表示（结构原样，不做化简）。"""
    if isinstance(e, Num):
        return ["num", float(e.value)]
    if isinstance(e, Var):
        return ["var", e.name]
    if isinstance(e, Neg):
        return ["neg", to_tagged(e.expr)]
    if isinstance(e, Add):
        return ["add", to_tagged(e.left), to_tagged(e.right)]
    if isinstance(e, Sub):
        return ["sub", to_tagged(e.left), to_tagged(e.right)]
    if isinstance(e, Mul):
        return ["mul", to_tagged(e.left), to_tagged(e.right)]
    if isinstance(e, Div):
        return ["div", to_tagged(e.numerator), to_tagged(e.denominator)]
    if isinstance(e, Pow):
        return ["pow", to_tagged(e.base), to_tagged(e.exponent)]
    if isinstance(e, Log):
        return ["ln", to_tagged(e.expr)]
    if isinstance(e, FuncCall):
        if len(e.args) != 1:
            raise MathaUnsupported(f"不支持: 标准库只处理一元函数调用，收到 {e.name}({len(e.args)} 参)")
        return ["fn", e.name, to_tagged(e.args[0])]
    raise MathaUnsupported(f"不支持: 未知表达式节点 {type(e).__name__}")


def from_tagged(node: Any) -> Expr:
    """库内规范形节点 → stage0 Expr（规范形只可能含 num/var/add/mul/pow/fn/ln）。"""
    if not isinstance(node, list) or not node:
        raise MathaUnsupported(f"不支持: 非法 tagged 节点 {node!r}")
    t = node[0]
    if t == "num":
        return Num(float(node[1]))
    if t == "var":
        return Var(str(node[1]))
    if t == "add":
        return Add(from_tagged(node[1]), from_tagged(node[2]))
    if t == "mul":
        return Mul(from_tagged(node[1]), from_tagged(node[2]))
    if t == "pow":
        底, 指 = from_tagged(node[1]), from_tagged(node[2])
        # stage0 的书写约定：负整数幂用倒数表示（`1/(x + 1)**2` 而非 `(x + 1)**-2`）。
        # 库内规范形统一用 pow（极限与项表运算依赖它），回发时在此还原；进 while
        # 展开与符号由 `latex._mul_body` 负责（已修：系数负号不得被 abs 吞掉）。
        if isinstance(指, Num) and float(指.value) < 0 and float(指.value) == int(指.value):
            k = int(-指.value)
            return Div(Num(1), Pow(底, Num(float(k))) if k != 1 else 底)
        return Pow(底, 指)
    if t == "neg":
        return Neg(from_tagged(node[1]))
    if t == "sub":
        return Sub(from_tagged(node[1]), from_tagged(node[2]))
    if t == "div":
        return Div(from_tagged(node[1]), from_tagged(node[2]))
    if t == "ln":
        return Log(from_tagged(node[1]))
    if t == "fn":
        return FuncCall(str(node[1]), [from_tagged(node[2])])
    raise MathaUnsupported(f"不支持: 规范形含未知节点 {t!r}")


def tagged_text(node: Any) -> str:
    """把库返回的规范形节点写成对拍用的确定文本（宿主侧只做递归，不做化简）。"""
    if isinstance(node, list):
        if not node:
            return "[]"
        t = node[0]
        if t == "num":
            return _num_text(node[1])
        if t == "var":
            return str(node[1])
        if t == "ln":
            return f"ln({tagged_text(node[1])})"
        if t == "fn":
            return f"{node[1]}({tagged_text(node[2])})"
        if t in ("add", "mul", "pow"):
            return f"({tagged_text(node[1])} {_OP[t]} {tagged_text(node[2])})"
        return f"[{t}, " + ", ".join(tagged_text(x) for x in node[1:]) + "]"
    return _num_text(node)


_OP = {"add": "+", "mul": "*", "pow": "^"}


def _num_text(v: Any) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    r = round(v)
    if abs(v - r) < 1e-12 and abs(v) < 1e15:
        return str(int(r))
    return repr(float(v))


# ============================================================
# 能力入口
# ============================================================

def derivative(e: Expr, var: str, n: int = 1) -> Expr:
    """n 阶导数：由 `calculus_diff.matha` 的 `n阶导` 计算，返回规范形 Expr。"""
    node = _call("n阶导", to_tagged(e), var, n)
    return from_tagged(node)


def nth_derivative(e: Expr, var: str, n: int) -> Expr:
    return derivative(e, var, n)


def simplify(e: Expr) -> Expr:
    """规范形化简：`algebra_simplify.matha` 的 `化简`。"""
    return from_tagged(_call("化简", to_tagged(e)))


def expand(e: Expr) -> Expr:
    """乘式分配展开后再取规范形：`algebra_simplify.matha` 的 `展开`。"""
    return from_tagged(_call("规范", _call("展开", to_tagged(e))))


def limit_value(e: Expr, var: str = "x", point: float = 0.0,
                direction: str = "+") -> float:
    """极限：`calculus_limit.matha` 的 `极限节点`，返回 float（无穷为 ±inf）。

    侧向参数与 stage0 同口径：`"+"` / `"-"` / 其它视为双侧（0）。
    """
    if not AVAILABLE:
        raise MathaUnsupported("不支持: Matha 标准库文件缺失")
    点: Any = point
    if math.isinf(point):
        点 = "+oo" if point > 0 else "-oo"
    侧 = 1 if direction == "+" else (-1 if direction == "-" else 0)
    r = _call("极限节点", to_tagged(e), var, 点, 侧)
    if not isinstance(r, list) or not r:
        raise MathaUnsupported(f"不支持: 极限结果形状异常 {r!r}")
    if r[0] == "数":
        return float(r[1])
    if r[0] == "比":
        return float(r[1]) / float(r[2])
    if r[0] == "无穷":
        return math.inf if r[1] == 1 else -math.inf
    raise MathaUnsupported(f"不支持: 未知极限结果节点 {r[0]!r}")


def maclaurin_terms(e: Expr, var: str = "x", order: int = 5) -> list[tuple[int, float]]:
    """Maclaurin 非零项 ``[(次数, 系数), ...]``。

    库内 `calculus_series.matha::系数对` 已按 stage0 同阈值（|c| < 1e-15）
    丢弃近似零项，次数随行一起返回，因此宿主侧重建幂级数时不会错位。
    """
    tbl = _call("系数对", to_tagged(e), var, order)
    if not isinstance(tbl, list):
        raise MathaUnsupported(f"不支持: 系数表形状异常 {tbl!r}")
    out: list[tuple[int, float]] = []
    for row in tbl:
        if not isinstance(row, list) or len(row) != 2:
            raise MathaUnsupported(f"不支持: 系数项形状异常 {row!r}")
        out.append((int(row[0]), float(row[1])))
    return out


def maclaurin_coeffs(e: Expr, var: str = "x", order: int = 5) -> list[float]:
    """仅系数（已丢弃近似零项），供对拍与旧调用方使用。"""
    return [c for _, c in maclaurin_terms(e, var, order)]
