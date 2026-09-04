# -*- coding: utf-8 -*-
"""Matha v4.2 — 标准库统一入口

统一导入所有标准库模块。

用法：
  from src.stdlib import arithmetic, algebra, calculus, logic
  # 或
  from src.stdlib.arithmetic import add, sqrt, factorial
  from src.stdlib.algebra import solve_quadratic, factor_integer
  from src.stdlib.calculus import derivative, integral
  from src.stdlib.logic import AND, OR, NOT, truth_table
"""
from __future__ import annotations

# 算术运算
from src.stdlib.arithmetic import (
    PI, E, PHI,
    add, subtract, multiply, divide,
    power, sqrt, abs_value,
    floor, ceil, round_value, trunc,
    gcd, lcm, factorial, is_prime,
    prime_factors, sieve_of_eratosthenes,
    sin, cos, tan, asin, acos, atan, atan2,
    log, log2, log10,
    combination, permutation,
)

# 代数
from src.stdlib.algebra import (
    Polynomial,
    solve_linear, solve_quadratic, solve_system_linear,
    factor_integer, factor_polynomial_simple,
    simplify_expression, expand_expression,
    poly_add, poly_mul, poly_div,
    poly_derivative, poly_integral,
)

# 微积分
from src.stdlib.calculus import (
    derivative, second_derivative,
    integral, numerical_integral_trapezoid,
    limit_forward, limit_two_sided,
    taylor_series, infinite_sum,
    newton_method,
    gamma, beta,
)

# 逻辑与证明
from src.stdlib.logic import (
    AND, OR, NOT, IMPLIES, IFF, XOR, NAND, NOR,
    truth_table, print_truth_table,
    set_union, set_intersection, set_difference,
    set_complement, set_symmetric_difference,
    is_subset, is_proper_subset,
    prove_by_contradiction,
    check_tautology, check_contradiction,
    Predicate,
    InferenceEngine,
)

__all__ = [
    # 算术
    "arithmetic", "PI", "E", "PHI",
    "add", "subtract", "multiply", "divide",
    "power", "sqrt", "abs_value",
    "floor", "ceil", "round_value", "trunc",
    "gcd", "lcm", "factorial", "is_prime",
    "prime_factors", "sieve_of_eratosthenes",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "log", "log2", "log10",
    "combination", "permutation",
    # 代数
    "algebra", "Polynomial",
    "solve_linear", "solve_quadratic", "solve_system_linear",
    "factor_integer", "factor_polynomial_simple",
    "simplify_expression", "expand_expression",
    "poly_add", "poly_mul", "poly_div",
    "poly_derivative", "poly_integral",
    # 微积分
    "calculus", "derivative", "second_derivative",
    "integral", "numerical_integral_trapezoid",
    "limit_forward", "limit_two_sided",
    "taylor_series", "infinite_sum",
    "newton_method", "gamma", "beta",
    # 逻辑
    "logic", "AND", "OR", "NOT", "IMPLIES", "IFF", "XOR", "NAND", "NOR",
    "truth_table", "print_truth_table",
    "set_union", "set_intersection", "set_difference",
    "set_complement", "set_symmetric_difference",
    "is_subset", "is_proper_subset",
    "prove_by_contradiction",
    "check_tautology", "check_contradiction",
    "Predicate", "InferenceEngine",
    # ── KNP-006: 统一别名（中英双语、常见缩写）────────────────────────
    # 算术别名
    "square_root", "平方根", "开方",
    "jiecheng", "阶乘",
    "abs_val", "绝对值",
    "square", "平方",
    "cube", "立方",
    # 代数别名
    "解方程", "求根",
    "因式分解",
    # 微积分别名
    "求导", "微分",
    "积分", "原函数",
    # 逻辑别名
    "且", "或", "非",
    # 集合别名
    "交集", "并集", "差集",
]
