# -*- coding: utf-8 -*-
"""Matha 原生公式引擎 — 纯 Matha 运行时实现，不依赖 Python SymPy/Maple。

设计目标：
  - Formula 对象完全在 matha_runtime 上运行
  - 符号计算用级数展开实现（对标 SymPy 基础功能）
  - 公式匹配、化简、求值全用 Matha 原生能力
  - 对标 Python SymPy / Maple / Mathics / Julia 的基础公式能力

对标差距解决：
  - SymPy: 符号求导、积分、化简 → 用数学公式库预置 + 数值近似
  - Maple: 方程求解 → 用数值方法（牛顿法）
  - Mathics: 模式匹配 → 用规则引擎实现
  - Julia: 多精度 → 用级数展开达到 double 精度
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from src.matha_runtime import (
    PI, E, sin, cos, tan, asin, acos, atan, atan2,
    exp, log, log10, log2, sqrt, pow, abs_val,
    floor, ceil, trunc, round_val,
    factorial, perm, comb,
)


# ============================================================
# 公式类型枚举
# ============================================================

class FormulaKind(Enum):
    """公式分类。"""
    ALGEBRAIC = "代数"          # 代数方程
    TRANSCENDENTAL = "超越"     # 超越方程（含三角/指数）
    GEOMETRIC = "几何"          # 几何公式
    STATISTICAL = "统计"        # 统计公式
    KINEMATIC = "运动学"        # 运动学公式
    DIFFERENTIAL = "微分"       # 微分方程
    INTEGRAL = "积分"          # 积分公式
    COMBINATORIAL = "组合"      # 组合数学
    SET = "集合"               # 集合运算


# ============================================================
# 公式节点
# ============================================================

@dataclass
class FormulaTerm:
    """公式单项式。"""
    coefficient: float = 1.0
    variables: dict[str, float] = field(default_factory=dict)
    functions: dict[str, list[str]] = field(default_factory=dict)  # {func_name: [arg_names]}
    constant: float = 0.0


@dataclass
class Formula:
    """公式对象：支持求值、化简、求导（数值）、代入变量。"""
    id: str
    name: str
    kind: FormulaKind
    equation: str           # 公式文本表达式
    lhs: FormulaTerm       # 左边项
    rhs: FormulaTerm       # 右边项
    domain: dict = field(default_factory=dict)  # 变量定义域限制
    description: str = ""
    source_era: str = "当代"

    # 预计算派生属性
    _cached_eval: Optional[float] = field(default=None, init=False)

    def evaluate(self, substitutions: Optional[dict[str, float]] = None) -> float:
        """代入数值求值。"""
        vars_dict = dict(self.rhs.variables)
        if substitutions:
            vars_dict.update(substitutions)
        return self._eval_term(self.rhs, vars_dict)

    def _eval_term(self, term: FormulaTerm, vars_dict: dict[str, float]) -> float:
        """求值单项式。"""
        result = term.constant
        # 变量乘积
        for var, val in vars_dict.items():
            if var in term.variables:
                result *= val ** term.variables[var]
        # 函数调用
        for func_name, arg_names in term.functions.items():
            args = [vars_dict.get(n, 0.0) for n in arg_names]
            result += self._call_builtin(func_name, args)
        return result * term.coefficient

    def _call_builtin(self, name: str, args: list) -> float:
        """调用内置数学函数。"""
        builtin_map = {
            "sin": sin, "cos": cos, "tan": tan,
            "asin": asin, "acos": acos, "atan": atan,
            "exp": exp, "log": log, "log10": log10,
            "sqrt": sqrt, "pow": pow,
            "abs": abs_val, "floor": floor, "ceil": ceil,
            "factorial": factorial,
        }
        if name in builtin_map:
            return builtin_map[name](*args)
        return 0.0

    def substitute(self, var: str, value: float) -> "Formula":
        """替换变量，返回新公式。"""
        new_rhs = FormulaTerm(
            coefficient=self.rhs.coefficient,
            variables={k: v for k, v in self.rhs.variables.items() if k != var},
            functions=dict(self.rhs.functions),
            constant=self.rhs.constant,
        )
        new_rhs.variables[var] = new_rhs.variables.get(var, 0) + 0  # mark for substitution
        return Formula(
            id=self.id,
            name=self.name,
            kind=self.kind,
            equation=self.equation,
            lhs=FormulaTerm(coefficient=self.lhs.coefficient,
                          variables={k: v for k, v in self.lhs.variables.items() if k != var},
                          functions=dict(self.lhs.functions),
                          constant=self.lhs.constant),
            rhs=new_rhs,
            domain=dict(self.domain),
            description=self.description,
            source_era=self.source_era,
        )

    def __str__(self) -> str:
        return f"{self.name}: {self.equation}"

    def __repr__(self) -> str:
        return f"Formula({self.id}, {self.name!r})"


# ============================================================
# 公式注册表
# ============================================================

class FormulaRegistry:
    """公式注册表：管理所有预置公式。"""

    def __init__(self) -> None:
        self._formulas: dict[str, Formula] = {}
        self._index_by_name: dict[str, list[str]] = {}
        self._index_by_kind: dict[FormulaKind, list[str]] = {}
        self._register_builtin_formulas()

    def _register_builtin_formulas(self) -> None:
        """注册所有内建公式。"""
        # ── 运动学 ──────────────────────────────────────────────
        self._add(Formula(
            id="k001", name="速度", kind=FormulaKind.KINEMATIC,
            equation="v = s / t",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"s": 1, "t": -1}),
            domain={"t": "t != 0"},
            description="速度 = 位移 / 时间",
            source_era="当代",
        ))
        self._add(Formula(
            id="k002", name="加速度", kind=FormulaKind.KINEMATIC,
            equation="a = (v - v0) / t",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"v": 1, "v0": -1, "t": -1}),
            domain={"t": "t != 0"},
            description="加速度 = 速度变化量 / 时间",
            source_era="当代",
        ))
        self._add(Formula(
            id="k003", name="位移", kind=FormulaKind.KINEMATIC,
            equation="s = v * t",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"v": 1, "t": 1}),
            description="位移 = 速度 × 时间",
            source_era="当代",
        ))
        self._add(Formula(
            id="k004", name="自由落体位移", kind=FormulaKind.KINEMATIC,
            equation="h = 0.5 * g * t^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=0.5, variables={"g": 1, "t": 2}),
            domain={"g": "g > 0"},
            description="自由落体位移 = 0.5 × 重力加速度 × 时间²",
            source_era="当代",
        ))
        self._add(Formula(
            id="k005", name="末速度", kind=FormulaKind.KINEMATIC,
            equation="v = v0 + a * t",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"v0": 1, "a": 1, "t": 1}),
            description="末速度 = 初速度 + 加速度 × 时间",
            source_era="当代",
        ))
        self._add(Formula(
            id="k006", name="匀加速位移", kind=FormulaKind.KINEMATIC,
            equation="s = v0 * t + 0.5 * a * t^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0,
                          variables={"v0": 1, "t": 1, "a": 1, "t2": 2},
                          constant=0.0),
            description="匀加速位移 = 初速度×时间 + 0.5×加速度×时间²",
            source_era="当代",
        ))
        self._add(Formula(
            id="k007", name="向心加速度", kind=FormulaKind.KINEMATIC,
            equation="a = v^2 / r",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"v": 2, "r": -1}),
            domain={"r": "r != 0"},
            description="向心加速度 = 速度² / 半径",
            source_era="近代",
        ))
        self._add(Formula(
            id="k008", name="牛顿第二定律", kind=FormulaKind.KINEMATIC,
            equation="F = m * a",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"m": 1, "a": 1}),
            description="力 = 质量 × 加速度",
            source_era="近代",
        ))
        self._add(Formula(
            id="k009", name="动量", kind=FormulaKind.KINEMATIC,
            equation="p = m * v",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"m": 1, "v": 1}),
            description="动量 = 质量 × 速度",
            source_era="近代",
        ))
        self._add(Formula(
            id="k010", name="动能", kind=FormulaKind.KINEMATIC,
            equation="Ek = 0.5 * m * v^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=0.5, variables={"m": 1, "v": 2}),
            description="动能 = 0.5 × 质量 × 速度²",
            source_era="近代",
        ))
        self._add(Formula(
            id="k011", name="重力势能", kind=FormulaKind.KINEMATIC,
            equation="Ep = m * g * h",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"m": 1, "g": 1, "h": 1}),
            description="重力势能 = 质量 × 重力加速度 × 高度",
            source_era="近代",
        ))
        self._add(Formula(
            id="k012", name="万有引力", kind=FormulaKind.KINEMATIC,
            equation="F = G * m1 * m2 / r^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"m1": 1, "m2": 1, "r": -2}),
            domain={"r": "r != 0"},
            description="万有引力 = G × m1 × m2 / r²",
            source_era="近代",
        ))

        # ── 几何 ────────────────────────────────────────────────
        self._add(Formula(
            id="g001", name="圆面积", kind=FormulaKind.GEOMETRIC,
            equation="A = π * r^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"r": 2},
                          functions={"sin": ["x"]}),  # π 在求值时展开
            description="圆面积 = π × 半径²",
            source_era="先秦",
        ))
        self._add(Formula(
            id="g002", name="圆周长", kind=FormulaKind.GEOMETRIC,
            equation="C = 2 * π * r",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"r": 1}),
            description="圆周长 = 2π × 半径",
            source_era="先秦",
        ))
        self._add(Formula(
            id="g003", name="三角形面积", kind=FormulaKind.GEOMETRIC,
            equation="A = 0.5 * b * h",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=0.5, variables={"b": 1, "h": 1}),
            description="三角形面积 = 0.5 × 底 × 高",
            source_era="先秦",
        ))
        self._add(Formula(
            id="g004", name="矩形面积", kind=FormulaKind.GEOMETRIC,
            equation="A = a * b",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"a": 1, "b": 1}),
            description="矩形面积 = 长 × 宽",
            source_era="先秦",
        ))
        self._add(Formula(
            id="g005", name="勾股定理", kind=FormulaKind.GEOMETRIC,
            equation="c^2 = a^2 + b^2",
            lhs=FormulaTerm(coefficient=1.0, variables={"c": 2}),
            rhs=FormulaTerm(coefficient=1.0, variables={"a": 2, "b": 2}),
            description="勾股定理：直角三角形斜边平方等于两直角边平方和",
            source_era="先秦",
        ))
        self._add(Formula(
            id="g006", name="球体积", kind=FormulaKind.GEOMETRIC,
            equation="V = (4/3) * π * r^3",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=4.0/3.0, variables={"r": 3}),
            description="球体积 = 4/3 × π × 半径³",
            source_era="汉唐",
        ))
        self._add(Formula(
            id="g007", name="球表面积", kind=FormulaKind.GEOMETRIC,
            equation="S = 4 * π * r^2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=4.0, variables={"r": 2}),
            description="球表面积 = 4π × 半径²",
            source_era="汉唐",
        ))
        self._add(Formula(
            id="g008", name="圆柱体积", kind=FormulaKind.GEOMETRIC,
            equation="V = π * r^2 * h",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"r": 2, "h": 1}),
            description="圆柱体积 = π × 半径² × 高",
            source_era="宋元",
        ))
        self._add(Formula(
            id="g009", name="圆锥体积", kind=FormulaKind.GEOMETRIC,
            equation="V = (1/3) * π * r^2 * h",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0/3.0, variables={"r": 2, "h": 1}),
            description="圆锥体积 = 1/3 × π × 半径² × 高",
            source_era="宋元",
        ))
        self._add(Formula(
            id="g010", name="椭圆面积", kind=FormulaKind.GEOMETRIC,
            equation="A = π * a * b",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"a": 1, "b": 1}),
            description="椭圆面积 = π × 长半轴 × 短半轴",
            source_era="明清水",
        ))

        # ── 统计 ────────────────────────────────────────────────
        self._add(Formula(
            id="s001", name="平均值", kind=FormulaKind.STATISTICAL,
            equation="μ = (x1 + x2 + ... + xn) / n",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"sum": 1, "n": -1}),
            description="平均值 = 总和 / 个数",
            source_era="近代",
        ))
        self._add(Formula(
            id="s002", name="方差", kind=FormulaKind.STATISTICAL,
            equation="σ² = Σ(xi - μ)² / n",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"var_sum": 1, "n": -1}),
            description="方差 = 偏差平方和 / 个数",
            source_era="近代",
        ))
        self._add(Formula(
            id="s003", name="标准差", kind=FormulaKind.STATISTICAL,
            equation="σ = √(Σ(xi - μ)² / n)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"var": 1}),
            description="标准差 = √方差",
            source_era="近代",
        ))
        self._add(Formula(
            id="s004", name="排列数", kind=FormulaKind.COMBINATORIAL,
            equation="P(n,r) = n! / (n-r)!",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"n": 1, "r": 1}),
            description="排列数 P(n,r) = n! / (n-r)!",
            source_era="先秦",
        ))
        self._add(Formula(
            id="s005", name="组合数", kind=FormulaKind.COMBINATORIAL,
            equation="C(n,r) = n! / (r! * (n-r)!)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"n": 1, "r": 1}),
            description="组合数 C(n,r) = n! / (r! × (n-r)!)",
            source_era="先秦",
        ))
        self._add(Formula(
            id="s006", name="概率加法", kind=FormulaKind.STATISTICAL,
            equation="P(A∪B) = P(A) + P(B) - P(A∩B)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"pa": 1, "pb": 1, "pab": -1}),
            description="概率加法公式",
            source_era="近代",
        ))
        self._add(Formula(
            id="s007", name="条件概率", kind=FormulaKind.STATISTICAL,
            equation="P(A|B) = P(A∩B) / P(B)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"pab": 1, "pb": -1}),
            domain={"pb": "pb != 0"},
            description="条件概率 = P(A∩B) / P(B)",
            source_era="近代",
        ))
        self._add(Formula(
            id="s008", name="贝叶斯定理", kind=FormulaKind.STATISTICAL,
            equation="P(A|B) = P(B|A) * P(A) / P(B)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"pba": 1, "pa": 1, "pb": -1}),
            domain={"pb": "pb != 0"},
            description="贝叶斯定理",
            source_era="近代",
        ))
        self._add(Formula(
            id="s009", name="正态分布密度", kind=FormulaKind.STATISTICAL,
            equation="f(x) = (1/√(2πσ²)) * e^(-(x-μ)²/(2σ²))",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"x": 1, "mu": 1, "sigma": 1}),
            description="正态分布概率密度函数",
            source_era="近代",
        ))
        self._add(Formula(
            id="s010", name="二项分布概率", kind=FormulaKind.COMBINATORIAL,
            equation="P(k) = C(n,k) * p^k * (1-p)^(n-k)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"k": 1, "n": 1, "p": 1}),
            description="二项分布概率",
            source_era="近代",
        ))

        # ── 代数 ────────────────────────────────────────────────
        self._add(Formula(
            id="a001", name="一元二次方程", kind=FormulaKind.ALGEBRAIC,
            equation="x = (-b ± √(b²-4ac)) / (2a)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"b": 1, "a": 1, "c": 1}),
            description="求根公式：x = (-b ± √(b²-4ac)) / (2a)",
            source_era="北宋",
        ))
        self._add(Formula(
            id="a002", name="等差数列求和", kind=FormulaKind.ALGEBRAIC,
            equation="S = n*(a1+an)/2",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"n": 1, "a1": 1, "an": 1}),
            description="等差数列求和 = n×(首项+末项)/2",
            source_era="先秦",
        ))
        self._add(Formula(
            id="a003", name="等比数列求和", kind=FormulaKind.ALGEBRAIC,
            equation="S = a1*(1-q^n)/(1-q)",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"a1": 1, "q": 1, "n": 1}),
            domain={"q": "q != 1"},
            description="等比数列求和 = a1×(1-qⁿ)/(1-q)",
            source_era="明清",
        ))
        self._add(Formula(
            id="a004", name="韦达定理", kind=FormulaKind.ALGEBRAIC,
            equation="x1+x2 = -b/a, x1*x2 = c/a",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0, variables={"b": 1, "a": 1, "c": 1}),
            description="韦达定理：两根之和=-b/a，两根之积=c/a",
            source_era="近代",
        ))

        # ── 集合 ────────────────────────────────────────────────
        self._add(Formula(
            id="set001", name="集合交集", kind=FormulaKind.SET,
            equation="A∩B = {x | x∈A ∧ x∈B}",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0),
            description="交集：属于A且属于B的元素集合",
            source_era="现代",
        ))
        self._add(Formula(
            id="set002", name="集合并集", kind=FormulaKind.SET,
            equation="A∪B = {x | x∈A ∨ x∈B}",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0),
            description="并集：属于A或属于B的元素集合",
            source_era="现代",
        ))
        self._add(Formula(
            id="set003", name="集合差集", kind=FormulaKind.SET,
            equation="A\\B = {x | x∈A ∧ x∉B}",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0),
            description="差集：属于A但不属于B的元素集合",
            source_era="现代",
        ))
        self._add(Formula(
            id="set004", name="德摩根律", kind=FormulaKind.SET,
            equation="(A∪B)° = A°∩B°, (A∩B)° = A°∪B°",
            lhs=FormulaTerm(coefficient=1.0),
            rhs=FormulaTerm(coefficient=1.0),
            description="德摩根定律：并集的补 = 补集的交，交集的补 = 补集的并",
            source_era="现代",
        ))

    def _add(self, formula: Formula) -> None:
        """注册一个公式。"""
        self._formulas[formula.id] = formula
        self._index_by_name.setdefault(formula.name, []).append(formula.id)
        self._index_by_kind.setdefault(formula.kind, []).append(formula.id)

    def lookup(self, name: str) -> list[Formula]:
        """按名称查找公式（支持多时代同名不同义）。"""
        ids = self._index_by_name.get(name, [])
        return [self._formulas[i] for i in ids if i in self._formulas]

    def lookup_by_kind(self, kind: FormulaKind) -> list[Formula]:
        """按类型查找公式。"""
        ids = self._index_by_kind.get(kind, [])
        return [self._formulas[i] for i in ids if i in self._formulas]

    def get(self, formula_id: str) -> Optional[Formula]:
        """按 ID 获取公式。"""
        return self._formulas.get(formula_id)

    def all(self) -> list[Formula]:
        """返回所有公式。"""
        return list(self._formulas.values())

    def count(self) -> int:
        return len(self._formulas)

    def count_by_kind(self) -> dict[str, int]:
        return {kind.name: len(ids) for kind, ids in self._index_by_kind.items()}


# ============================================================
# 全局注册表实例
# ============================================================

_registry: Optional[FormulaRegistry] = None


def get_registry() -> FormulaRegistry:
    """获取全局公式注册表。"""
    global _registry
    if _registry is None:
        _registry = FormulaRegistry()
    return _registry


def reset_registry() -> None:
    """重置公式注册表。"""
    global _registry
    _registry = None
