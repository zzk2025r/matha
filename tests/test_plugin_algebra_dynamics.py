# -*- coding: utf-8 -*-
"""插件化隔离风险门禁：代数数精确打印（opt-in）。

覆盖（对应「内核只依赖接口 / 核心保持纯净 / 外部插件实现 / 动态加载」）：

1. **无损**：代数数插件默认不加载时，门面 ``to_str`` 发射逐字节不变；加载后仅
   把可证精确命中的 double 系数还原为根式；能力之外诚实回退。
2. **隔离红线**：纯内核 / 执行器不得 import 插件契约层；契约层不得顶层依赖
   sympy / numpy / scipy（保持核心极简、零第三方成本）。

（动态语义段随 src/dynamics/ 一起退役——阶段 22b 孤儿清算，该插件全仓
零消费、无活加载方，RV32IM 对拍锁随 git 历史保留。）
"""
from __future__ import annotations

import importlib.util
import math
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from src.algebra import interface as alg  # noqa: E402
from src.algebra.algebra_plugin import PLUGIN as ALG_PLUGIN  # noqa: E402


def _sq(n: int):
    return alg.UnaryOp("sqrt", alg.Const(n))


def _c(n):
    return alg.Const(Fraction(n))


def _add(a, b):
    return alg.BinOp("+", a, b)


def _sub(a, b):
    return alg.BinOp("-", a, b)


def _mul(a, b):
    return alg.BinOp("*", a, b)


def _div(a, b):
    return alg.BinOp("/", a, b)


def _root(d, n):
    return alg.BinOp("^", alg.Const(Fraction(d)), alg.Const(Fraction(1, n)))


def _canon_to_sympy(s: str):
    """把插件规范串（sqrt(n)/root(n,d)/分数/+-*）解析回 sympy 精确表达式。"""
    import re

    import sympy as sp
    s2 = re.sub(r"root\((\d+),(\d+)\)", r"root(\2,\1)", s)
    return sp.sympify(s2)


def _canon_to_sympy_complex(s: str):
    """同上，但先把独立的虚单位 `i` 映为 sympy 的 `I`（否则会被当作符号）。"""
    import re

    import sympy as sp
    s2 = re.sub(r"root\((\d+),(\d+)\)", r"root(\2,\1)", s)
    s2 = re.sub(r"(?<![A-Za-z0-9_])i(?![A-Za-z0-9_])", "I", s2)
    return sp.sympify(s2)


def _tree_to_sympy(t):
    """独立地用 sympy 精确求值中性项树（与插件完全无关的第二实现，作对拍基准）。"""
    import sympy as sp
    if isinstance(t, alg.Const):
        return sp.Rational(t.value)
    if isinstance(t, alg.Symbol):
        return sp.Symbol(t.name)
    if isinstance(t, alg.UnaryOp):
        inner = _tree_to_sympy(t.operand)
        if t.op == "sqrt":
            return sp.sqrt(inner)
        if t.op == "-":
            return -inner
        if t.op == "+":
            return inner
    if isinstance(t, alg.BinOp):
        L = _tree_to_sympy(t.left)
        R = _tree_to_sympy(t.right)
        return {"+": L + R, "-": L - R, "*": L * R, "/": L / R, "^": sp.Pow(L, R)}[t.op]
    raise TypeError(f"未知项类型：{type(t).__name__}")


# ============================================================
# 1. 代数数打印：无损 + 精确 + 诚实边界
# ============================================================


def test_algebra_default_inactive_facade_is_lossless():
    """未加载插件时门面输出必须等于内核 to_str 原样（含 double 系数）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()  # 确保关
    assert cs.exact_algebra_enabled() is False
    out = cs.symbolic_integral("1/(x**2+2)", "x")
    # 默认路径应保留 double 打印，绝不出现根式
    assert "sqrt" not in out
    assert "0.70" in out or "1.41" in out


def test_algebra_optin_renders_exact_and_restores():
    """同一条积分：关→开→关，关闭后必须与初始默认输出逐字节相同（无损）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()
    default_out = cs.symbolic_integral("1/(x**2+2)", "x")
    assert "sqrt" not in default_out
    try:
        cs.enable_exact_algebra()
        assert cs.exact_algebra_enabled() is True
        exact = cs.symbolic_integral("1/(x**2+2)", "x")
        assert "sqrt(2)" in exact          # 0.7071… → 1/2*sqrt(2)，1.4142… → sqrt(2)
        assert "0.70" not in exact
    finally:
        cs.use_kernel_printing()
    assert cs.symbolic_integral("1/(x**2+2)", "x") == default_out


@pytest.mark.parametrize("value,expect", [
    (math.sqrt(2), "sqrt(2)"),
    (Fraction(5, 7), "5/7"),
    (7, "7"),
    (-math.sqrt(3), "-sqrt(3)"),
    (0.5 + 3 * math.sqrt(2), "1/2 + 3*sqrt(2)"),
    (2 ** 0.5 * 2, "2*sqrt(2)"),          # sqrt(8) 化简
])
def test_algebra_recognizer_exact_forms(value, expect):
    got = ALG_PLUGIN.render(alg.Const(Fraction(value)) if not isinstance(value, Fraction) else alg.Const(value))
    assert got == expect


def test_algebra_honesty_defers_unknown():
    """能力边界诚实回退：无结构线索的扁平浮点 / 超越数 / 嵌套根 / 混合高次 → render 回 None。"""
    # 扁平 double（来自门面 decorate 路径）：√2+√3 无数树形线索 → 不过度猜测，回 None
    assert ALG_PLUGIN.render(alg.Const(Fraction(math.sqrt(2) + math.sqrt(3)))) is None
    # 超越数 π
    assert ALG_PLUGIN.render(alg.Const(Fraction(math.pi))) is None
    # 嵌套根式 √(√2)：本框架不做 denest → None
    assert ALG_PLUGIN.render(alg.UnaryOp("sqrt", _sq(2))) is None
    # 多根式 + 高次混合 √2 + ∛2：超出 ℚ(√…) 且非纯根 → None
    assert ALG_PLUGIN.render(_add(_sq(2), _root(2, 3))) is None
    # 含符号：不可作为常数精确还原 → None
    assert ALG_PLUGIN.render(_add(_sq(2), alg.Symbol("x"))) is None
    # 复代数数越界：双虚基 √(-1)+√(-2) 非单根式 a+b√d → None（单 √(-1) 已可精确为 i）
    assert ALG_PLUGIN.render(_add(_sq(-1), _sq(-2))) is None
    # 复数开方 √(i)：本框架不做复极坐标/嵌套 → None
    assert ALG_PLUGIN.render(alg.UnaryOp("sqrt", _sq(-1))) is None


@pytest.mark.parametrize("tree,expect", [
    (_add(_sq(2), _sq(3)), "sqrt(2) + sqrt(3)"),
    (_sub(_sq(5), _sq(2)), "-sqrt(2) + sqrt(5)"),
    (_mul(_add(_c(1), _sq(2)), _add(_c(1), _sq(3))), "1 + sqrt(2) + sqrt(3) + sqrt(6)"),
    (_div(_c(1), _sq(2)), "1/2*sqrt(2)"),
    (_add(_sq(2), _add(_sq(3), _sq(5))), "sqrt(2) + sqrt(3) + sqrt(5)"),
    (_sub(_mul(_c(3), _sq(2)), _sq(3)), "3*sqrt(2) - sqrt(3)"),
    (_mul(_sq(2), _sq(3)), "sqrt(6)"),
    (_add(_c(1), _sq(2)), "1 + sqrt(2)"),
])
def test_algebra_multiquadratic_exact(tree, expect):
    """多根式域 ℚ(√d1,…,√dk) 结构还原：与既有 double 塌缩不重合的高次代数数现在可精确打印。"""
    got = ALG_PLUGIN.render(tree)
    assert got == expect


@pytest.mark.parametrize("tree", [
    _add(_sq(2), _sq(3)),
    _sub(_sq(5), _sq(2)),
    _mul(_add(_c(1), _sq(2)), _add(_c(1), _sq(3))),
    _div(_c(1), _sq(2)),
    _add(_sq(2), _add(_sq(3), _sq(5))),
    _sub(_mul(_c(3), _sq(2)), _sq(3)),
])
def test_algebra_multiquadratic_differential_vs_sympy(tree):
    """对拍 sympy：插件输出的规范串解析回 sympy 后，与树的独立 sympy 精确求值符号相等。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    diff = sp.simplify(_canon_to_sympy(got) - _tree_to_sympy(tree))
    assert diff == 0, f"{got!r} vs sympy 不吻合: {diff}"


@pytest.mark.parametrize("tree,expect", [
    (_root(2, 3), "root(3,2)"),
    (_root(16, 3), "2*root(3,2)"),
    (_root(4, 3), "root(3,4)"),
    (_root(3, 4), "root(4,3)"),
    (_root(7, 5), "root(5,7)"),
    (_root(32, 5), "2"),                 # 纯整数次根 → 有理路径
])
def test_algebra_nthroot_exact(tree, expect):
    """高次纯根 base^(1/n)（n>=3）化简为 k·ⁿ√r，规范串 root(n,r)。"""
    assert ALG_PLUGIN.render(tree) == expect


@pytest.mark.parametrize("tree", [
    _root(2, 3), _root(16, 3), _root(4, 3), _root(3, 4),
])
def test_algebra_nthroot_differential_vs_sympy(tree):
    """对拍 sympy：纯高次根的插件输出与 sympy 实根数值、符号均吻合。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    assert sp.simplify(_canon_to_sympy(got) - _tree_to_sympy(tree)) == 0
    assert abs(float(_canon_to_sympy(got)) - ALG_PLUGIN._eval_float(tree)) < 1e-9


def test_algebra_flat_float_regression_still_quadratic_only():
    """回归锁：扁平浮点（无树形）仍仅走二次/有理识别，不得因扩面而误命中高次。"""
    assert ALG_PLUGIN.render(alg.Const(Fraction(2 ** 0.5))) == "sqrt(2)"   # 二次仍精确
    assert ALG_PLUGIN.render(alg.Const(Fraction(2 ** (1 / 3)))) is None     # 扁平 ∛2 无结构→诚实 None


# ============================================================
# 1b. 复代数数 a+b√d（d<0）：按虚部 i 拆分精确渲染
# ============================================================


@pytest.mark.parametrize("tree,expect", [
    (_sq(-1), "i"),
    (_sq(-2), "sqrt(2)*i"),
    (_sq(-4), "2*i"),                       # √(-4)=2i（完全平方虚根→纯虚有理）
    (_sub(_c(0), _sq(-3)), "-sqrt(3)*i"),
    (_mul(_c(3), _sq(-2)), "3*sqrt(2)*i"),
    (_add(_c(1), _sq(-3)), "1 + sqrt(3)*i"),
    (_add(_c(5), _mul(_c(2), _sq(-7))), "5 + 2*sqrt(7)*i"),
    (_div(_add(_c(1), _sq(-3)), _c(2)), "1/2 + 1/2*sqrt(3)*i"),
])
def test_algebra_complex_quadratic_exact(tree, expect):
    """复二次数精确渲染：实部纯有理 + 虚部单一实二次根式，虚单位以 `*i` 表出。"""
    assert ALG_PLUGIN.render(tree) == expect


@pytest.mark.parametrize("tree", [
    _sq(-1), _sq(-2), _sq(-4), _mul(_c(3), _sq(-2)),
    _add(_c(1), _sq(-3)), _add(_c(5), _mul(_c(2), _sq(-7))),
    _div(_add(_c(1), _sq(-3)), _c(2)),
])
def test_algebra_complex_quadratic_differential_vs_sympy(tree):
    """对拍 sympy：复代数数插件串解析回 sympy 应与树的独立 sympy 复数求值相等。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    assert sp.simplify(_canon_to_sympy_complex(got) - _tree_to_sympy(tree)) == 0


def test_algebra_complex_real_regression_untouched():
    """回归锁：接入复数分支后，既有实数路径（二次/多根式）输出逐字不变。"""
    assert ALG_PLUGIN.render(_sq(2)) == "sqrt(2)"
    assert ALG_PLUGIN.render(_add(_sq(2), _sq(3))) == "sqrt(2) + sqrt(3)"
    assert ALG_PLUGIN.render(_div(_c(1), _sq(2))) == "1/2*sqrt(2)"


# ============================================================
# 1c. 高次代数数：单一纯根式域 ℚ(ⁿ√m) 内线性组合精确渲染
# ============================================================


@pytest.mark.parametrize("tree,expect", [
    (_add(_root(2, 3), _root(4, 3)), "root(3,2) + root(3,4)"),
    (_sub(_mul(_c(3), _root(2, 3)), _root(4, 3)), "3*root(3,2) - root(3,4)"),
    (_mul(_root(2, 3), _root(2, 3)), "root(3,4)"),
    (_add(_c(5), _root(2, 3)), "5 + root(3,2)"),
    (_div(_root(2, 3), _c(2)), "1/2*root(3,2)"),
    (_mul(_c(2), _root(2, 3)), "2*root(3,2)"),
    (_add(_root(2, 3), _root(16, 3)), "3*root(3,2)"),   # ∛16 = 2∛2 → 合并同类基
    (_root(2, 5), "root(5,2)"),                          # 五次纯根（单一，仍精确）
])
def test_algebra_higher_degree_exact(tree, expect):
    """高次代数数：同域 ℚ(ⁿ√m) 的加/乘/整幂/有理除，逐基向量精确化简。"""
    assert ALG_PLUGIN.render(tree) == expect


@pytest.mark.parametrize("tree", [
    _add(_root(2, 3), _root(4, 3)),
    _sub(_mul(_c(3), _root(2, 3)), _root(4, 3)),
    _mul(_root(2, 3), _root(2, 3)),
    _add(_c(5), _root(2, 3)),
    _div(_root(2, 3), _c(2)),
    _add(_root(2, 3), _root(16, 3)),
])
def test_algebra_higher_degree_differential_vs_sympy(tree):
    """对拍 sympy：高阶根式域插件串解析回 sympy 应与树的独立 sympy 求值相等。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    assert sp.simplify(_canon_to_sympy(got) - _tree_to_sympy(tree)) == 0


def test_algebra_higher_degree_out_of_scope_defers():
    """越界诚实：多生成元(∛2+∛3)/混合根(√2+∛2)/域内一般除法(1/(1+∛2)) → None。"""
    assert ALG_PLUGIN.render(_add(_root(2, 3), _root(3, 3))) is None
    assert ALG_PLUGIN.render(_add(_sq(2), _root(2, 3))) is None
    assert ALG_PLUGIN.render(_div(_c(1), _add(_c(1), _root(2, 3)))) is None


def test_algebra_higher_degree_single_root_regression():
    """回归锁：单一纯根仍走 _mc_nthroot；扁平 ∛2(无树) 仍诚实 None；多根式不受影响。"""
    assert ALG_PLUGIN.render(_root(2, 3)) == "root(3,2)"
    assert ALG_PLUGIN.render(alg.Const(Fraction(2 ** (1 / 3)))) is None
    assert ALG_PLUGIN.render(_add(_sq(2), _sq(3))) == "sqrt(2) + sqrt(3)"


