"""Matha 符号微积分标准库（门面：默认走 Matha 标准库，零第三方依赖）

本模块原先是 SymPy 绑定层（`from sympy import ...`）。阶段 3 起全部能力
下沉到纯标准库的内核符号引擎 :mod:`src.kernel.symbolic`（stage0 引导实现）；
阶段 4 再把求导 / 化简 / 极限 / 级数四项能力的**默认计算路径**改为 Matha 自己
的标准库 —— `matha/library/calculus_diff.matha`、`algebra_simplify.matha`、
`calculus_limit.matha`、`calculus_series.matha`，由核心主线 `mbc.compiler → mbc.vm`
编译执行（装载器见 :mod:`src.stdlib.matha_symbolic`）。本文件只做**门面**：
参数解析 → 后端路由 → 字符串发射，并保持原有的公开函数名与返回类型。

回退不是静默的：只有标准库显式抛 `不支持: …` 才转 stage0 引导实现，计数记入
:data:`BACKEND_STATS`（:func:`backend_stats` 读取）；`backend="matha"` 可强制不走
回退。覆盖范围、与 stage0 的逐位对拍结果及缺口清单见
``docs/matha_stdlib_symbolic.md``；与 sympy 的能力对照见 ``docs/symbolic_parity.md``。
**缺口一律显式报错并指向文档，不做静默降级、不返回「无法求解」这类假成功。**

用法：
  from src.stdlib.calculus_symbolic import (
      symbolic_derivative,
      symbolic_integral,
      taylor_series,
      limit,
      infinite_sum,
      solve_ode,
  )
"""
from __future__ import annotations

import logging
import math

from src.kernel.symbolic import (
    canonical,
    nth_derivative as _k_nth,
    partial_derivative as _k_partial,
    solve_ode as _k_ode,
    symbol_expr as _k_parse,
    to_latex as _k_latex,
    to_pretty as _k_pretty,
    to_str as _k_str,
)
# 与子模块同名的函数（integrate / limit）一律从子模块直接导入，避开包属性遮蔽
from src.kernel.symbolic.domain import accumulated_bounds as _k_bounds
from src.kernel.symbolic.domain import continuous_domain as _k_domain
from src.kernel.symbolic.diff import differentiate as _k_diff
from src.kernel.symbolic.integrate import definite as _k_definite
from src.kernel.symbolic.integrate import integrate as _k_integrate
from src.kernel.symbolic.limit import limit as _k_limit
from src.kernel.symbolic.series import sum_series as _k_sum
from src.kernel.symbolic.series import taylor as _k_taylor
from src.kernel.symbolic.expr import Expr  # noqa: F401  (公开类型注解用)
from src.kernel.symbolic.expr import Add, Mul, Neg, Num, Pow, Var
from src.stdlib import matha_symbolic as _ms

logger = logging.getLogger(__name__)

_PARITY = "docs/symbolic_parity.md"
_STDLIB_DOC = "docs/matha_stdlib_symbolic.md"

# 兼容名：内核不再依赖 sympy，该标志现在表示「内核符号引擎可用」。
# 旧的 demo/benchmark 用 `if not HAS_SYMPY: ...` 做能力门禁，语义保持成立。
HAS_KERNEL_SYMBOLIC = True
HAS_SYMPY = HAS_KERNEL_SYMBOLIC


def _parse(expr, var_hint: str = "") -> Expr:
    """字符串/Expr → 内核 Expr AST；不可解析时显式报错。"""
    if isinstance(expr, Expr):
        return expr
    text = str(expr).strip()
    if not text:
        raise ValueError(f"空表达式无法解析（var={var_hint}）")
    try:
        return _k_parse(text)
    except Exception as e:  # pragma: no cover - 解析器错误信息已足够
        raise ValueError(f"表达式解析失败: {expr} -> {e}") from e


def _fail(op: str, err: Exception):
    """统一错误出口：带上缺口文档指引，绝不返回占位字符串。"""
    raise ValueError(f"{op}失败: {err}（能力缺口对照见 {_PARITY}）") from err


# ============================================================
# 后端路由：Matha 标准库（默认）/ stage0 引导实现（显式回退）
# ============================================================

#: 阶段 4：符号微积分的默认计算路径是 Matha 自己的标准库
#: （`matha/library/*.matha`，由 `mbc.compiler → mbc.vm` 执行）。
#: Python 内核 :mod:`src.kernel.symbolic` 退为 stage0 引导实现 + 对拍基准。
#: `backend` 取值：
#:   "auto"（默认）先走标准库；只有当库显式抛 `不支持: …` 才回退 stage0
#:   "matha"  只走标准库，未覆盖即报错，绝不静默回退
#:   "stage0" 只走 Python 引导实现（对拍基准与诊断用）
BACKEND_STATS: dict[str, int] = {"matha": 0, "stage0": 0, "fallback": 0}


def backend_stats() -> dict[str, int]:
    """走了哪条路、各多少次：让「回退」可被测试与文档核对，不是静默行为。"""
    return dict(BACKEND_STATS)


def reset_backend_stats() -> None:
    for k in BACKEND_STATS:
        BACKEND_STATS[k] = 0


def _route(backend: str, matha_fn, stage0_fn, op: str):
    if backend not in ("auto", "matha", "stage0"):
        raise ValueError(f"未知 backend {backend!r}（auto | matha | stage0）")
    if backend == "stage0":
        BACKEND_STATS["stage0"] += 1
        return stage0_fn()
    if not _ms.available():
        if backend == "matha":
            raise ValueError(f"{op}失败: Matha 标准库不可用（{_ms.LIB_DIR}）")
        BACKEND_STATS["stage0"] += 1
        return stage0_fn()
    try:
        out = matha_fn()
    except _ms.MathaUnsupported as e:
        if backend == "matha":
            raise ValueError(f"{op}失败: {e}（标准库覆盖范围见 {_STDLIB_DOC}）") from e
        BACKEND_STATS["fallback"] += 1
        logger.debug("标准库未覆盖，回退 stage0 引导实现: %s: %s", op, e)
        BACKEND_STATS["stage0"] += 1
        return stage0_fn()
    BACKEND_STATS["matha"] += 1
    return out


def _stage0_num(v: float) -> Num:
    """与 `src.kernel.symbolic.series._num` 同式的常数归一（对拍需要逐位一致）。"""
    r = round(v)
    return Num(float(r)) if abs(v - r) < 1e-12 else Num(v)


def _ms_taylor(e: Expr, var: str, point: float, order: int) -> Expr:
    """把 Matha 标准库的 Maclaurin 系数对重建为 Expr。

    构造规则（`n==0` 取常数、`coef=±1` 省略系数、否则 `Mul(系数, x^n)`、
    左折求和）与 stage0 `series.taylor` 一致，因此两侧只有在系数本身
    不同时才会出现文本差异 —— 那正是对拍要抓的东西。
    非 0 点不在标准库范围内：显式抛 `不支持:`，由 `_route` 回退 stage0。
    """
    if point != 0:
        raise _ms.MathaUnsupported("不支持: 级数库只覆盖 point=0 的 Maclaurin 展开")
    terms = _ms.maclaurin_terms(e, var, order)
    if not terms:
        return canonical(Num(0))
    out: Expr | None = None
    for n, coef in terms:
        body = Var(var) if n == 1 else Pow(Var(var), Num(float(n)))
        if n == 0:
            t = _stage0_num(coef)
        elif coef == 1.0:
            t = body
        elif coef == -1.0:
            t = Neg(body)
        else:
            t = Mul(_stage0_num(coef), body)
        out = t if out is None else Add(out, t)
    return canonical(out)


# ============================================================
# 符号微分
# ============================================================

def symbolic_derivative(expr: str, var: str = "x", backend: str = "auto") -> str:
    """
    符号求导：f'(x) = d/dx(f(x))

    数学定义：
      f'(x) = lim(h→0) [f(x+h) - f(x)] / h

    Args:
        expr: 数学表达式字符串，如 "x**2 + 3*x + 1"
        var: 求导变量，默认为 "x"

    Returns:
        导数表达式字符串

    Examples:
        >>> symbolic_derivative("x**2", "x")
        '2*x'
        >>> symbolic_derivative("sin(x)", "x")
        'cos(x)'
        >>> symbolic_derivative("exp(x)*cos(x)", "x")
        'exp(x)*cos(x) - exp(x)*sin(x)'
    """
    e = _parse(expr, var)
    try:
        return _route(backend, lambda: _k_str(canonical(_ms.derivative(e, var))),
                      lambda: _k_str(_k_diff(e, var)), "符号求导")
    except ValueError:
        raise
    except Exception as ex:
        _fail("符号求导", ex)


def symbolic_partial_derivative(expr: str, var: str = "x") -> str:
    """
    符号偏导数：∂f/∂x

    Examples:
        >>> symbolic_partial_derivative("x**2 + y**2", "x")
        '2*x'
    """
    try:
        return _k_str(_k_partial(_parse(expr, var), var))
    except ValueError:
        raise
    except Exception as e:
        _fail("符号偏导数", e)


def nth_derivative(expr: str, var: str = "x", n: int = 1, *, backend: str = "auto") -> str:
    """
    n 阶导数：d^n f / dx^n

    Examples:
        >>> nth_derivative("sin(x)", "x", 2)
        '-sin(x)'
    """
    e = _parse(expr, var)
    k = int(n)
    try:
        return _route(backend, lambda: _k_str(canonical(_ms.derivative(e, var, k))),
                      lambda: _k_str(_k_nth(e, var, k)), "高阶导数")
    except ValueError:
        raise
    except Exception as ex:
        _fail("高阶导数", ex)


# ============================================================
# 符号积分
# ============================================================

def symbolic_integral(expr: str, var: str = "x") -> str:
    """
    符号积分：∫f(x)dx（不含积分常数，与 sympy 口径一致）

    数学定义：
      ∫f(x)dx = F(x) + C，其中 F'(x) = f(x)

    Args:
        expr: 数学表达式字符串
        var: 积分变量，默认为 "x"

    Returns:
        积分结果表达式字符串

    Examples:
        >>> symbolic_integral("x**2", "x")
        'x**3/3'
        >>> symbolic_integral("sin(x)", "x")
        '-cos(x)'
        >>> symbolic_integral("1/x", "x")
        'log(x)'
    """
    logger.debug(f"开始符号积分: expr={expr}, var={var}")
    try:
        out = _k_integrate(_parse(expr, var), var)
    except ValueError:
        raise
    except Exception as e:
        _fail("符号积分", e)
    if out is None:
        raise ValueError(
            f"符号积分失败：内核无对应闭合规则: {expr}（覆盖范围见 {_PARITY}；"
            f"定积分可用 definite_integral 走数值分支）")
    result_str = _k_str(out)
    logger.info(f"符号积分完成: ∫{expr}d{var} = {result_str}")
    return result_str


def definite_integral(expr: str, var: str, lower: float, upper: float) -> float:
    """
    定积分：∫[lower, upper] f(x)dx

    数学定义：
      ∫[a,b] f(x)dx = F(b) - F(a)；原函数不在闭合规则内时退自适应 Simpson 数值积分

    Args:
        expr: 数学表达式字符串
        var: 积分变量
        lower: 下界
        upper: 上界

    Returns:
        定积分数值结果

    Examples:
        >>> definite_integral("x**2", "x", 0, 1)
        0.3333333333333333
        >>> definite_integral("sin(x)", "x", 0, 3.141592653589793)
        2.0
    """
    try:
        val = _k_definite(_parse(expr, var), var, float(lower), float(upper))
    except ValueError:
        raise
    except Exception as e:
        _fail("定积分计算", e)
    if val is None:
        raise ValueError(f"定积分失败：表达式在积分区间上不可求值: {expr}")
    return float(val)


# ============================================================
# 泰勒展开
# ============================================================

def taylor_series(expr: str, var: str = "x", point: float = 0, order: int = 5,
                  *, backend: str = "auto") -> str:
    """
    泰勒展开：f(x) ≈ Σ f^(n)(a)/n! * (x-a)^n（丢弃余项，同 sympy removeO）

    数学定义：
      f(x) = f(a) + f'(a)(x-a) + f''(a)/2!(x-a)^2 + ...

    Args:
        expr: 数学表达式字符串
        var: 变量名
        point: 展开点，默认为 0（麦克劳林级数）
        order: 展开阶数

    Returns:
        泰勒展开表达式字符串

    Examples:
        >>> taylor_series("exp(x)", "x", 0, 5)
        'x**5/120 + x**4/24 + x**3/6 + x**2/2 + x + 1'
        >>> taylor_series("sin(x)", "x", 0, 5)
        'x**5/120 - x**3/6 + x'
    """
    e = _parse(expr, var)
    a, k = float(point), int(order)
    try:
        return _route(backend, lambda: _k_str(_ms_taylor(e, var, a, k)),
                      lambda: _k_str(_k_taylor(e, var, a, k)), "泰勒展开")
    except ValueError:
        raise
    except Exception as ex:
        _fail("泰勒展开", ex)


# ============================================================
# 极限计算
# ============================================================

def limit(expr: str, var: str = "x", point: float = 0, direction: str = "+",
          *, backend: str = "auto") -> float:
    """
    极限计算：lim(x→point) f(x)

    数学定义：
      lim(x→a) f(x) = L，当 x 趋近于 a 时 f(x) 趋近于 L

    Args:
        expr: 数学表达式字符串
        var: 变量名
        point: 趋近点（``float('inf')`` 表示无穷远）
        direction: "+" 右极限，"-" 左极限（内核按同一点两侧分别求值）

    Returns:
        极限值（float）

    Examples:
        >>> limit("sin(x)/x", "x", 0)
        1.0
        >>> limit("1/x", "x", 0, "+")
        inf
    """
    target = float(point)
    if math.isinf(target) and target < 0:
        point_arg = -math.inf
    else:
        point_arg = target
    dirn = "-" if direction == "-" else "+"
    e = _parse(expr, var)
    try:
        return float(_route(backend, lambda: _ms.limit_value(e, var, point_arg, dirn),
                            lambda: _k_limit(e, var, point_arg, direction=dirn),
                            "极限计算"))
    except ValueError:
        raise
    except Exception as ex:
        _fail("极限计算", ex)


# ============================================================
# 级数求和
# ============================================================

def infinite_sum(expr: str, var: str = "n", lower: int = 1, upper: int | None = None) -> str | float:
    """
    级数求和：Σ f(n)

    数学定义：
      Σ[n=lower, upper] f(n)；upper=None 表示上界 ∞

    Args:
        expr: 通项公式字符串
        var: 求和变量
        lower: 下界
        upper: 上界（None 表示无穷级数）

    Returns:
        闭式解（str）或数值（float）；无穷级数无数值加速可得的，其结果为
        截断求和 + 尾项估计，精度见 docs/symbolic_parity.md

    Examples:
        >>> infinite_sum("1/n**2", "n", 1, None)
        1.6449340668482262
        >>> infinite_sum("x**n/factorial(n)", "n", 0, None)
        'exp(x)'
    """
    try:
        out = _k_sum(_parse(expr, var), var, int(lower),
                     None if upper is None else int(upper))
    except ValueError:
        raise
    except Exception as e:
        _fail("级数求和", e)
    if isinstance(out, Expr):
        if not out.free_vars():
            try:
                return float(out.evaluate({}))
            except Exception:
                pass
        return _k_str(out)
    return float(out)


# ============================================================
# 微分方程求解
# ============================================================

def solve_ode(ode: str, func_name: str = "y", var: str = "x") -> str:
    """
    常微分方程求解（记号兼容 ``y'(x)`` / ``y'`` / ``dy/dx`` / ``y''`` / ``y(x)``）

    数学定义：
      求解 dy/dx = f(x, y) 的通解，积分常量为 C1（二阶为 C1/C2）

    Args:
        ode: 微分方程字符串，如 "y'(x) = x*y(x)"
        func_name: 函数名
        var: 自变量名

    Returns:
        解表达式字符串（``y = ...`` 的右端）

    Examples:
        >>> solve_ode("y'(x) = x*y(x)", "y", "x")
        'C1*exp(x**2/2)'
    """
    try:
        return _k_ode(str(ode), func_name, var)
    except ValueError:
        raise
    except Exception as e:
        _fail("微分方程求解", e)


# ============================================================
# 定义域 / 累值界
# ============================================================

def continuous_domain(expr: str, var: str = "x") -> list[str]:
    """
    连续域：使表达式关于 var 连续的区间并集（开区间串的升序列表）。

    Examples:
        >>> continuous_domain("1/x", "x")
        ['(-oo, 0)', '(0, oo)']
    """
    try:
        return [str(iv) for iv in _k_domain(_parse(expr, var), var)]
    except ValueError:
        raise
    except Exception as e:
        _fail("连续域计算", e)


def accumulated_bounds(expr: str, var: str = "x") -> tuple[float, float]:
    """
    累值界：``x→∞`` 处函数值聚点的上下界 (liminf, limsup)。

    Examples:
        >>> accumulated_bounds("sin(x)", "x")
        (-1.0, 1.0)
    """
    try:
        lo, hi = _k_bounds(_parse(expr, var), var)
        return (float(lo), float(hi))
    except ValueError:
        raise
    except Exception as e:
        _fail("累值界计算", e)


# ============================================================
# 辅助函数
# ============================================================

def sympy_parse(expr: str, namespace: dict | None = None) -> Expr:
    """
    解析数学表达式为内核符号对象（历史名保留，返回 ``src.kernel.symbolic.expr.Expr``）

    支持的运算符：
      +  -  *  /  **  （幂亦可写 ^，两者同义）

    Args:
        expr: 数学表达式字符串
        namespace: 兼容参数，内核解析器按名字直接建变量，故忽略其内容

    Returns:
        内核 Expr 表达式树
    """
    return _parse(expr)


def kernel_parse(expr: str) -> Expr:
    """显式命名的解析入口（等价于 ``sympy_parse``，不依赖任何第三方库）。"""
    return _parse(expr)


def latex_format(expr: str) -> str:
    """
    将表达式转换为 LaTeX 格式。

    Examples:
        >>> latex_format("x**2 + 2*x + 1")
        'x^{2} + 2 x + 1'
    """
    try:
        return _k_latex(_parse(expr))
    except ValueError:
        raise
    except Exception as e:
        _fail("LaTeX 转换", e)


def pretty_format(expr: str) -> str:
    """
    将表达式转换为美观的文本格式。

    Examples:
        >>> pretty_format("x**2 + 2*x + 1")
        'x² + 2x + 1'
    """
    try:
        return _k_pretty(_parse(expr))
    except ValueError:
        raise
    except Exception as e:
        _fail("格式化", e)


def simplify_format(expr: str, *, backend: str = "auto") -> str:
    """
    标准形文本（展开 + 合并同类项 + 稳定项序）。

    Examples:
        >>> simplify_format("(x+1)**2")
        'x**2 + 2*x + 1'
    """
    e = _parse(expr)
    return _route(backend, lambda: _k_str(canonical(_ms.expand(e))),
                  lambda: _k_str(canonical(e)), "标准形化简")


# ============================================================
# 批量计算工具
# ============================================================

def batch_derivative(expressions: list[str], var: str = "x") -> list[str]:
    """
    批量求导

    Args:
        expressions: 表达式列表
        var: 变量名

    Returns:
        导数表达式列表
    """
    return [symbolic_derivative(expr, var) for expr in expressions]


def batch_integral(expressions: list[str], var: str = "x") -> list[str]:
    """
    批量积分

    Args:
        expressions: 表达式列表
        var: 变量名

    Returns:
        积分表达式列表
    """
    return [symbolic_integral(expr, var) for expr in expressions]


def batch_taylor(expressions: list[str], var: str = "x", point: float = 0, order: int = 5) -> list[str]:
    """
    批量泰勒展开

    Args:
        expressions: 表达式列表
        var: 变量名
        point: 展开点
        order: 阶数

    Returns:
        泰勒展开表达式列表
    """
    return [taylor_series(expr, var, point, order) for expr in expressions]


# ============================================================
# 数学常量
# ============================================================

class SymbolicConstants:
    """符号数学常量（纯 float，不依赖 sympy）。"""

    PI = math.pi
    E = math.e
    I = complex(0.0, 1.0)
    INFINITY = math.inf
    NAN = math.nan

    @classmethod
    def list_all(cls) -> dict:
        """列出所有常量。"""
        return {
            name: getattr(cls, name)
            for name in dir(cls)
            if not name.startswith("_") and not callable(getattr(cls, name))
        }


# 便捷导入
PI = SymbolicConstants.PI
E = SymbolicConstants.E
I = SymbolicConstants.I
INFINITY = SymbolicConstants.INFINITY


__all__ = [
    "HAS_SYMPY", "HAS_KERNEL_SYMBOLIC",
    "symbolic_derivative", "symbolic_partial_derivative", "nth_derivative",
    "symbolic_integral", "definite_integral",
    "taylor_series", "limit", "infinite_sum", "solve_ode",
    "continuous_domain", "accumulated_bounds",
    "sympy_parse", "kernel_parse", "latex_format", "pretty_format",
    "simplify_format",
    "batch_derivative", "batch_integral", "batch_taylor",
    "backend_stats", "reset_backend_stats", "BACKEND_STATS",
    "SymbolicConstants", "PI", "E", "I", "INFINITY",
]


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 符号微积分标准库（内核实现，零第三方依赖）")
    print("=" * 60)

    print("\n【符号求导】")
    print(f"  d/dx(x²) = {symbolic_derivative('x**2')}")
    print(f"  d/dx(sin(x)) = {symbolic_derivative('sin(x)')}")
    print(f"  d/dx(exp(x)*cos(x)) = {symbolic_derivative('exp(x)*cos(x)')}")

    print("\n【符号积分】")
    print(f"  ∫x²dx = {symbolic_integral('x**2')}")
    print(f"  ∫sin(x)dx = {symbolic_integral('sin(x)')}")
    print(f"  ∫(1/x)dx = {symbolic_integral('1/x')}")

    print("\n【定积分】")
    print(f"  ∫[0,1] x²dx = {definite_integral('x**2', 'x', 0, 1):.6f}")
    print(f"  ∫[0,π] sin(x)dx = {definite_integral('sin(x)', 'x', 0, math.pi):.6f}")

    print("\n【泰勒展开】")
    print(f"  e^x ≈ {taylor_series('exp(x)', 'x', 0, 5)}")
    print(f"  sin(x) ≈ {taylor_series('sin(x)', 'x', 0, 5)}")

    print("\n【极限计算】")
    print(f"  lim(x→0) sin(x)/x = {limit('sin(x)/x', 'x', 0):.6f}")
    print(f"  lim(x→∞) 1/x = {limit('1/x', 'x', float('inf')):.6f}")

    print("\n【微分方程】")
    print(f"  y' = x·y → {solve_ode('y\'(x) = x*y(x)')}")

    print("\n【定义域 / 累值界】")
    print(f"  1/x 连续域 → {continuous_domain('1/x')}")
    print(f"  sin(x) 累值界 → {accumulated_bounds('sin(x)')}")

    print("\n【LaTeX 格式】")
    print(f"  x² + 2x + 1 → {latex_format('x**2 + 2*x + 1')}")

    print("\n" + "=" * 60)
    print("  符号微积分标准库测试完成")
    print("=" * 60)
