# -*- coding: utf-8 -*-
"""Matha v4.4 — 符号微积分标准库（SymPy 集成版）

提供符号微积分核心功能：
  - 符号求导：d/dx(f(x))
  - 符号积分：∫f(x)dx
  - 泰勒展开：f(x) ≈ Σ f^(n)(a)/n! * (x-a)^n
  - 极限计算：lim(x→a) f(x)
  - 级数求和：Σ a_n
  - 微分方程求解

数学表达：
  所有函数遵循微积分定义，确保数学严谨性。
  使用 SymPy 进行符号计算，支持任意精度。

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
import math
import logging
from typing import Callable, List, Optional, Tuple, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from sympy import (
        symbols, diff, integrate, limit as sympy_limit,
        series, Sum, oo, solve, dsolve, Eq,
        sin, cos, tan, exp, log, sqrt,
        pi, E, I, nan,
        Symbol, Function, Derivative, Integral,
        factorial, gamma, beta,
        Poly, factor, expand, simplify,
        latex, pretty
    )
    # inf 在 SymPy 1.14+ 中已从主命名空间移除
    try:
        from sympy import inf
    except ImportError:
        from math import inf
    HAS_SYMPY = True
except ImportError as e:
    HAS_SYMPY = False
    # 定义占位常量
    class _DummySymbol:
        pass
    pi = _DummySymbol()
    E = _DummySymbol()
    I = _DummySymbol()
    oo = _DummySymbol()
    nan = _DummySymbol()
    inf = float('inf')

# 可选导入（SymPy 1.14+ 可能已移除）
try:
    from sympy.calculus.util import accumulated_bounds, continuous_domain
except ImportError:
    accumulated_bounds = None
    continuous_domain = None

try:
    from sympy.solvers.ode import ode_solve
except ImportError:
    ode_solve = None


# ============================================================
# 符号微分
# ============================================================

def symbolic_derivative(expr: str, var: str = "x") -> str:
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
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        result = diff(expr_sym, x)
        return str(simplify(result))
    except Exception as e:
        raise ValueError(f"符号求导失败: {e}")


def symbolic_partial_derivative(expr: str, var: str = "x") -> str:
    """
    符号偏导数：∂f/∂x

    Examples:
        >>> symbolic_partial_derivative("x**2 + y**2", "x")
        '2*x'
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        result = diff(expr_sym, x)
        return str(simplify(result))
    except Exception as e:
        raise ValueError(f"符号偏导数失败: {e}")


# ============================================================
# 符号积分
# ============================================================

def symbolic_integral(expr: str, var: str = "x") -> str:
    """
    符号积分：∫f(x)dx

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
    if not HAS_SYMPY:
        logger.error("SymPy 未安装，无法执行符号积分")
        raise ImportError("需要安装 SymPy: pip install sympy")

    logger.debug(f"开始符号积分: expr={expr}, var={var}")
    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        logger.debug(f"表达式解析成功: {expr_sym}")
        result = integrate(expr_sym, x)
        logger.debug(f"积分计算完成: {result}")
        result_str = str(result)
        logger.info(f"符号积分完成: ∫{expr}d{var} = {result_str}")
        return result_str
    except Exception as e:
        logger.error(f"符号积分失败: expr={expr}, error={e}")
        raise ValueError(f"符号积分失败: {e}")


def definite_integral(expr: str, var: str, lower: float, upper: float) -> float:
    """
    定积分：∫[lower, upper] f(x)dx

    数学定义：
      ∫[a,b] f(x)dx = F(b) - F(a)

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
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        result = integrate(expr_sym, (x, lower, upper))
        return float(result)
    except Exception as e:
        raise ValueError(f"定积分计算失败: {e}")


# ============================================================
# 泰勒展开
# ============================================================

def taylor_series(expr: str, var: str = "x", point: float = 0, order: int = 5) -> str:
    """
    泰勒展开：f(x) ≈ Σ f^(n)(a)/n! * (x-a)^n

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
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        result = series(expr_sym, x, point, order + 1)
        return str(result.removeO())
    except Exception as e:
        raise ValueError(f"泰勒展开失败: {e}")


# ============================================================
# 极限计算
# ============================================================

def limit(expr: str, var: str = "x", point: float = 0, direction: str = "+") -> float:
    """
    极限计算：lim(x→point) f(x)

    数学定义：
      lim(x→a) f(x) = L，当 x 趋近于 a 时 f(x) 趋近于 L

    Args:
        expr: 数学表达式字符串
        var: 变量名
        point: 趋近点
        direction: 方向（"+" 右极限，"-" 左极限）

    Returns:
        极限值

    Examples:
        >>> limit("sin(x)/x", "x", 0)
        1.0
        >>> limit("1/x", "x", 0, "+")
        inf
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        if direction == "+":
            result = sympy_limit(expr_sym, x, point, '+')
        else:
            result = sympy_limit(expr_sym, x, point, '-')
        return float(result)
    except Exception as e:
        raise ValueError(f"极限计算失败: {e}")


# ============================================================
# 级数求和
# ============================================================

def infinite_sum(expr: str, var: str = "n", lower: int = 1, upper: Optional[int] = None) -> Union[str, float]:
    """
    级数求和：Σ f(n)

    数学定义：
      Σ[n=lower, upper] f(n)

    Args:
        expr: 通项公式字符串
        var: 求和变量
        lower: 下界
        upper: 上界（None 表示无穷级数）

    Returns:
        求和结果

    Examples:
        >>> infinite_sum("1/n**2", "n", 1, None)
        1.6449340668482264  # π²/6
        >>> infinite_sum("x**n/factorial(n)", "n", 0, None)
        'exp(x)'
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    n = symbols(var)
    try:
        expr_sym = sympy_parse(expr)
        if upper is None:
            result = Sum(expr_sym, (n, lower, oo)).doit()
        else:
            result = Sum(expr_sym, (n, lower, upper)).doit()
        return float(result) if result.is_number else str(result)
    except Exception as e:
        raise ValueError(f"级数求和失败: {e}")


# ============================================================
# 微分方程求解
# ============================================================

def solve_ode(ode: str, func_name: str = "y", var: str = "x") -> str:
    """
    常微分方程求解

    数学定义：
      求解 dy/dx = f(x, y) 的通解或特解

    Args:
        ode: 微分方程字符串，如 "y'(x) = x*y(x)"
        func_name: 函数名
        var: 自变量名

    Returns:
        解表达式字符串

    Examples:
        >>> solve_ode("y'(x) = x*y(x)", "y", "x")
        'C1*exp(x**2/2)'
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    x = symbols(var)
    y = Function(func_name)(x)
    try:
        # 解析微分方程
        if "'(" in ode:
            # 处理 y'(x) = ... 格式
            eq_str = ode.replace(f"{func_name}'(", f"Derivative({func_name}(x), x) - ").replace(")", "")
            # 更简单的处理方式
            eq_str = ode.replace(f"{func_name}'(x)", f"Derivative({func_name}(x), x)")
        else:
            eq_str = ode

        eq = sympy_parse(eq_str)
        result = dsolve(eq, y)
        return str(result.rhs) if result else "无法求解"
    except Exception as e:
        raise ValueError(f"微分方程求解失败: {e}")


# ============================================================
# 辅助函数
# ============================================================

def sympy_parse(expr: str, namespace: Optional[dict] = None) -> any:
    """
    解析数学表达式为 SymPy 对象

    支持的运算符：
      +  -  *  /  **  (优先级与 Python 一致)
      ^  表示幂运算（会被替换为 **）

    Args:
        expr: 数学表达式字符串
        namespace: 可选的命名空间字典

    Returns:
        SymPy 表达式对象
    """
    # 将 ^ 替换为 **（幂运算）
    expr_clean = expr.replace('^', '**')
    # 移除空格
    expr_clean = expr_clean.replace(' ', '')

    if namespace is None:
        namespace = {
            'x': symbols('x'),
            'y': symbols('y'),
            'z': symbols('z'),
            'sin': sin,
            'cos': cos,
            'tan': tan,
            'exp': exp,
            'log': log,
            'sqrt': sqrt,
            'pi': pi,
            'E': E,
            'I': I,
            'inf': inf,
        }

    try:
        # 使用 sympy.parse_expr 替代 eval，更安全
        from sympy import parse_expr
        return parse_expr(expr_clean, local_dict=namespace)
    except Exception as e:
        raise ValueError(f"表达式解析失败: {expr} -> {e}")


def latex_format(expr: str) -> str:
    """
    将表达式转换为 LaTeX 格式。

    Examples:
        >>> latex_format("x**2 + 2*x + 1")
        'x^{2} + 2 x + 1'
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    try:
        expr_sym = sympy_parse(expr)
        return latex(expr_sym)
    except Exception as e:
        raise ValueError(f"LaTeX 转换失败: {e}")


def pretty_format(expr: str) -> str:
    """
    将表达式转换为美观的文本格式。

    Examples:
        >>> pretty_format("x**2 + 2*x + 1")
        'x² + 2x + 1'
    """
    if not HAS_SYMPY:
        raise ImportError("需要安装 SymPy: pip install sympy")

    try:
        expr_sym = sympy_parse(expr)
        return pretty(expr_sym)
    except Exception as e:
        raise ValueError(f"格式化失败: {e}")


# ============================================================
# 批量计算工具
# ============================================================

def batch_derivative(expressions: List[str], var: str = "x") -> List[str]:
    """
    批量求导

    Args:
        expressions: 表达式列表
        var: 变量名

    Returns:
        导数表达式列表
    """
    return [symbolic_derivative(expr, var) for expr in expressions]


def batch_integral(expressions: List[str], var: str = "x") -> List[str]:
    """
    批量积分

    Args:
        expressions: 表达式列表
        var: 变量名

    Returns:
        积分表达式列表
    """
    return [symbolic_integral(expr, var) for expr in expressions]


def batch_taylor(expressions: List[str], var: str = "x", point: float = 0, order: int = 5) -> List[str]:
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
    """符号数学常量。"""

    PI = pi
    E = E
    I = I
    INFINITY = oo
    NAN = nan

    @classmethod
    def list_all(cls) -> dict:
        """列出所有常量。"""
        return {
            name: getattr(cls, name)
            for name in dir(cls)
            if not name.startswith("_")
        }


# 便捷导入
PI = SymbolicConstants.PI
E = SymbolicConstants.E
I = SymbolicConstants.I
INFINITY = SymbolicConstants.INFINITY


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 符号微积分标准库（SymPy 集成版）")
    print("=" * 60)

    # 检查 SymPy
    if not HAS_SYMPY:
        print("\n⚠️  SymPy 未安装，请运行: pip install sympy")
        exit(1)

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

    print("\n【LaTeX 格式】")
    print(f"  x² + 2x + 1 → {latex_format('x**2 + 2*x + 1')}")

    print("\n" + "=" * 60)
    print("  符号微积分标准库测试完成")
    print("=" * 60)
