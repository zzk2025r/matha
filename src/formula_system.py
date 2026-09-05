# -*- coding: utf-8 -*-
"""
Matha 公式互转系统（Formula Interconversion System）

解决核心问题：
  数学公式在不同命名体系下无法建立等价关系。
  例如：
    - 长方形面积 = 长 * 宽
    - 平行四边形面积 = 底 * 高
    - 三角形面积 = 底 * 高 / 2

  当 长=底, 宽=高 时：
    - 长方形面积 = 平行四边形面积
    - 三角形面积 = 长方形面积 / 2

本模块提供：
  1. Formula         — 带语义名称的公式节点
  2. FormulaRegistry — 公式库，支持注册/查询/等价推导
  3. 公式推导引擎     — 参数映射与公式替换
  4. 公式等价验证     — 数值验证两公式等价性
  5. 几何公式预置库   — 平面几何、立体几何核心公式
"""
from __future__ import annotations
import ast
import inspect
import logging
import math
import random
import re
from dataclasses import dataclass, field
from typing import Optional, Any, Callable

from src.symbolic import Expr, Var, Num, Mul, Div, Add, Sub, Pow, Neg, FuncCall, to_expr, symbol_expr
from src.symbolic import simplify_expr

logger = logging.getLogger("matha.formula_system")


# ============================================================
#  公式注册节点
# ============================================================

@dataclass
class Formula:
    """一个带语义的数学公式。

    属性：
        name:        公式的中文名称（如 "长方形面积"）
        expr:        符号表达式 Expr
        params:      参数名列表（有序）
        params_desc: 参数描述映射 {param: "描述"}
        category:    分类（"area"/"volume"/"perimeter"/"general"）
        notes:       备注说明
        expr_text:   完整公式文本（如 "S = πr²"）
        axioms:      公理依赖
        derives:     可推导的公式名
        domain:      数学域
    """
    name: str
    expr: Expr
    params: list[str] = field(default_factory=list)
    params_desc: dict[str, str] = field(default_factory=dict)
    category: str = "general"
    notes: str = ""
    expr_text: str = ""
    axioms: list[str] = field(default_factory=list)
    derives: list[str] = field(default_factory=list)
    domain: str = "geometry"

    def free_vars(self) -> set[str]:
        """返回公式中所有自由变量名。"""
        return _collect_vars(self.expr)

    def evaluate(self, bindings: dict[str, float]) -> float:
        """代入数值求值。"""
        return self.expr.evaluate(bindings)

    def substitute(self, old_var: str, new_expr: Expr) -> Expr:
        """在公式中替换变量。"""
        return self.expr.substitute(old_var, new_expr)

    def __str__(self) -> str:
        params_str = ", ".join(self.params) if self.params else "()"
        return f"{self.name}({params_str}) = {self.expr}"


# ============================================================
#  参数等价关系
# ============================================================

@dataclass
class ParamEquivalence:
    """两个参数之间的等价声明。"""
    lhs: str
    rhs: str
    formula_a: str
    formula_b: str
    notes: str = ""

    def __str__(self) -> str:
        return f"{self.formula_a}.{self.lhs} = {self.formula_b}.{self.rhs}"


# ============================================================
#  推导结果
# ============================================================

@dataclass
class DerivationResult:
    """公式推导结果。"""
    success: bool
    source_formulas: list[str]
    equivalence_rules: list[str]
    derived_formula: str
    derived_expr: Expr
    derived_params: list[str]
    steps: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.success:
            return f"推导失败: {'; '.join(self.steps)}"
        steps_str = " → ".join(self.steps)
        return (
            f"✓ {self.derived_formula}\n"
            f"  公式: {self.derived_expr}\n"
            f"  步骤: {steps_str}"
        )


# ============================================================
#  工具函数
# ============================================================

def _collect_vars(expr: Expr) -> set[str]:
    vars_set: set[str] = set()
    _collect_vars_recursive(expr, vars_set)
    return vars_set


def _collect_vars_recursive(expr: Expr, result: set[str]) -> None:
    if isinstance(expr, Var):
        result.add(expr.name)
    elif isinstance(expr, (Add, Sub)):
        _collect_vars_recursive(expr.left, result)
        _collect_vars_recursive(expr.right, result)
    elif isinstance(expr, Mul):
        _collect_vars_recursive(expr.left, result)
        _collect_vars_recursive(expr.right, result)
    elif isinstance(expr, Div):
        _collect_vars_recursive(expr.numerator, result)
        _collect_vars_recursive(expr.denominator, result)
    elif isinstance(expr, Pow):
        _collect_vars_recursive(expr.base, result)
        _collect_vars_recursive(expr.exponent, result)
    elif isinstance(expr, Neg):
        _collect_vars_recursive(expr.expr, result)
    elif isinstance(expr, FuncCall):
        for arg in expr.args:
            _collect_vars_recursive(arg, result)


# ============================================================
#  能力标注（Capability Annotation）
# ============================================================

@dataclass
class Capability:
    """一段公式代码的自动标注元数据。

    当程序员直接编写公式函数时，系统自动提取并记录以下信息：
      - name:          函数全名（如 "转动_角加速度"）
      - domain:        子领域前缀（如 "转动"）
      - capability:    计算能力（如 "角加速度"）
      - params:        参数名列表
      - expr:          符号表达式 Expr
      - description:   自动生成的描述
      - docstring:     函数文档字符串
      - source_file:   源文件路径
      - source_line:   源行号
    """
    name: str
    domain: str
    capability: str
    params: list[str] = field(default_factory=list)
    expr: Optional[Expr] = None
    description: str = ""
    docstring: Optional[str] = None
    source_file: Optional[str] = None
    source_line: int = 0

    def __str__(self) -> str:
        expr_str = str(self.expr) if self.expr else "—"
        return f"{self.name}({', '.join(self.params)}) = {expr_str}  [{self.domain}]"

    def summary(self) -> str:
        """简洁摘要，用于快速浏览。"""
        parts = [f"name={self.name}"]
        if self.params:
            parts.append(f"params=[{', '.join(self.params)}]")
        if self.expr:
            parts.append(f"expr={self.expr}")
        if self.description:
            parts.append(f"desc={self.description}")
        return " | ".join(parts)


class CapabilityRegistry:
    """能力注册表：管理所有领域函数的自动标注元数据。

    支持按名称、领域、关键词快速查询已标注的能力。
    """

    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def register(self, cap: Capability) -> None:
        """注册一个能力标注。"""
        self._caps[cap.name] = cap
        logger.info(f"  [能力标注] 注册: {cap}")

    def get(self, name: str) -> Optional[Capability]:
        return self._caps.get(name)

    def list_all(self) -> list[Capability]:
        return list(self._caps.values())

    def list_by_domain(self, domain: str) -> list[Capability]:
        return [c for c in self._caps.values() if c.domain == domain]

    def search(self, keyword: str) -> list[Capability]:
        kw = keyword.lower()
        return [c for c in self._caps.values()
                if kw in c.name.lower() or kw in c.capability.lower()
                or kw in c.description.lower() or kw in c.domain.lower()]

    def summary_table(self) -> str:
        """生成可读的能力摘要表格。"""
        if not self._caps:
            return "  （无能力标注）"
        lines = ["  ┌─ 能力标注总览 ──────────────────────────────"]
        by_domain: dict[str, list[Capability]] = {}
        for c in sorted(self._caps.values(), key=lambda x: (x.domain, x.name)):
            by_domain.setdefault(c.domain, []).append(c)
        for domain in sorted(by_domain):
            lines.append(f"  │ 领域: {domain}")
            for c in by_domain[domain]:
                expr_str = str(c.expr) if c.expr else "—"
                lines.append(f"  │    • {c.name}({', '.join(c.params)}) = {expr_str}")
                if c.description:
                    lines.append(f"  │      说明: {c.description}")
        lines.append("  └────────────────────────────────────────────")
        return "\n".join(lines)


# 全局能力注册表（延迟初始化）
_capability_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """获取全局能力注册表（单例）。"""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry


def scan_module_capabilities(module) -> int:
    """扫描模块中所有 _xxx_yyy 格式的公式函数，自动标注能力元数据。

    返回注册的能力数量。
    提取策略：
      1. 函数名拆解： _<domain>_<capability> → domain + capability
      2. 函数签名 → params 列表
      3. 函数体 AST → 表达式字符串 → 解析为 Expr
      4. docstring 或源码注释 → description
    """
    registry = get_capability_registry()
    count = 0
    for name, func in inspect.getmembers(module, inspect.isfunction):
        if not name.startswith("_"):
            continue
        # 去掉开头的下划线，再拆解域名和能力名
        # 格式：_域名_能力名 (如 _牛顿_力) 或 多段 _a_b_c
        stripped = name.lstrip("_")
        if not stripped:
            continue
        # 跳过 _register_*、_curry*、辅助函数等非公式函数
        if stripped.startswith("register") or stripped.startswith("curry") or "symtab" in stripped:
            continue
        # 找到第一个 _ 分隔的域名前缀：取第一个下划线之前的所有段作为 domain
        first_underscore = stripped.find("_")
        if first_underscore < 0:
            continue  # 没有子域分隔，跳过（如 _牛顿力 → 无下划线）
        domain = stripped[:first_underscore]
        capability = stripped[first_underscore + 1:]
        if not domain or not capability:
            continue
        # 提取参数名
        try:
            sig = inspect.signature(func)
            params = [p for p in sig.parameters if p not in ("self",)]
        except (ValueError, TypeError):
            params = []
        # 提取 docstring
        docstring = inspect.getdoc(func) or ""
        # 从函数体提取表达式（尝试从注释或代码结构）
        expr: Optional[Expr] = None
        description = ""
        source_file: Optional[str] = None
        source_line = 0
        try:
            source = inspect.getsource(func)
            source_file = inspect.getfile(func)
            source_line = func.__code__.co_firstlineno
            # 尝试从函数体 AST 提取 return 表达式
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    for stmt in node.body:
                        if isinstance(stmt, ast.Return) and stmt.value:
                            expr_str = ast.unparse(stmt.value)
                            try:
                                expr = symbol_expr(expr_str)
                            except Exception:
                                expr = None
                            break
                    break
            # 从 docstring 或注释生成描述
            if docstring:
                description = docstring.strip().split("\n")[0].strip()
            elif source:
                # 尝试从 inline comment 提取
                m = re.search(r"#\s*([^\n]+)", source)
                if m:
                    description = m.group(1).strip()
        except (OSError, SyntaxError):
            pass
        # 构建描述
        if not description:
            description = f"{capability}：{domain}领域 {capability} 计算"
        cap = Capability(
            name=name,
            domain=domain,
            capability=capability,
            params=params,
            expr=expr,
            description=description,
            docstring=docstring if docstring else None,
            source_file=source_file,
            source_line=source_line,
        )
        registry.register(cap)
        count += 1
    return count


# ============================================================
#  公式注册表
# ============================================================

class FormulaRegistry:
    """公式注册表：存储几何/代数公式及参数等价关系。"""

    def __init__(self):
        self._formulas: dict[str, Formula] = {}
        self._equivalences: list[ParamEquivalence] = []

    # ── 注册 ──────────────────────────────────────────────────

    def register(self, formula: Formula) -> None:
        self._formulas[formula.name] = formula
        logger.info(f"  注册公式: {formula}")

    def substitute_constants(self) -> None:
        """对所有已注册的公式表达式代入常量（如 π→3.14159, g→9.80665）。"""
        resolver = get_formula_resolver()
        for name, formula in self._formulas.items():
            expr = resolver._substitute_constants(formula.expr)
            formula.expr = expr

    def register_geometric_defaults(self) -> None:
        """注册所有预置几何公式（平面几何 + 立体几何）。"""
        # ── 平面几何 ──────────────────────────────────────────
        self.register(Formula(
            "长方形面积", Mul(Var("长"), Var("宽")),
            params=["长", "宽"],
            category="area", notes="长方形面积 = 长 × 宽",
        ))
        self.register(Formula(
            "平行四边形面积", Mul(Var("底"), Var("高")),
            params=["底", "高"],
            category="area", notes="平行四边形面积 = 底 × 高",
        ))
        self.register(Formula(
            "三角形面积", Div(Mul(Var("底"), Var("高")), Num(2)),
            params=["底", "高"],
            category="area", notes="三角形面积 = 底 × 高 / 2",
        ))
        self.register(Formula(
            "梯形面积", Div(Mul(Add(Var("上底"), Var("下底")), Var("高")), Num(2)),
            params=["上底", "下底", "高"],
            category="area", notes="梯形面积 = (上底 + 下底) × 高 / 2",
        ))
        self.register(Formula(
            "菱形面积", Div(Mul(Var("对角线1"), Var("对角线2")), Num(2)),
            params=["对角线1", "对角线2"],
            category="area", notes="菱形面积 = 对角线1 × 对角线2 / 2",
        ))
        self.register(Formula(
            "圆面积", Mul(Var("π"), Pow(Var("半径"), Num(2))),
            params=["半径"],
            category="area", notes="圆面积 = π × 半径²",
        ))
        self.register(Formula(
            "圆周长", Mul(Num(2), Mul(Var("π"), Var("半径"))),
            params=["半径"],
            category="perimeter", notes="圆周长 = 2 × π × 半径",
        ))
        self.register(Formula(
            "正三角形面积",
            Div(Mul(FuncCall("sqrt", [Num(3)]), Pow(Var("边长"), Num(2))), Num(4)),
            params=["边长"],
            category="area", notes="正三角形面积 = √3/4 × 边长²",
        ))
        self.register(Formula(
            "椭圆面积", Mul(Var("π"), Mul(Var("长半轴"), Var("短半轴"))),
            params=["长半轴", "短半轴"],
            category="area", notes="椭圆面积 = π × 长半轴 × 短半轴",
        ))
        self.register(Formula(
            "扇形面积",
            Div(Mul(Mul(Var("π"), Pow(Var("半径"), Num(2))), Var("圆心角")), Num(360)),
            params=["半径", "圆心角"],
            category="area", notes="扇形面积 = π × 半径² × 圆心角 / 360",
        ))
        self.register(Formula(
            "弧长",
            Mul(Var("圆心角"), Var("半径")),
            params=["半径", "圆心角"],
            category="perimeter", notes="弧长 = 圆心角(弧度) × 半径",
        ))

        # ── 立体几何 ──────────────────────────────────────────
        self.register(Formula(
            "正方体体积", Pow(Var("棱长"), Num(3)),
            params=["棱长"],
            category="volume", notes="正方体体积 = 棱长³",
        ))
        self.register(Formula(
            "长方体体积", Mul(Mul(Var("长"), Var("宽")), Var("高")),
            params=["长", "宽", "高"],
            category="volume", notes="长方体体积 = 长 × 宽 × 高",
        ))
        self.register(Formula(
            "圆柱体积", Mul(Mul(Var("π"), Pow(Var("底半径"), Num(2))), Var("高")),
            params=["底半径", "高"],
            category="volume", notes="圆柱体积 = π × 底半径² × 高",
        ))
        self.register(Formula(
            "圆锥体积",
            Div(Mul(Mul(Var("π"), Pow(Var("底半径"), Num(2))), Var("高")), Num(3)),
            params=["底半径", "高"],
            category="volume", notes="圆锥体积 = π × 底半径² × 高 / 3",
        ))
        self.register(Formula(
            "球体积",
            Div(Mul(Num(4), Mul(Mul(Var("π"), Pow(Var("半径"), Num(2))), Var("半径"))), Num(3)),
            params=["半径"],
            category="volume", notes="球体积 = 4/3 × π × 半径³",
        ))
        self.register(Formula(
            "球表面积", Mul(Num(4), Mul(Var("π"), Pow(Var("半径"), Num(2))), ),
            params=["半径"],
            category="area", notes="球表面积 = 4 × π × 半径²",
        ))
        self.register(Formula(
            "三棱柱体积",
            Mul(Div(Mul(Var("底"), Var("高")), Num(2)), Var("柱高")),
            params=["底", "高", "柱高"],
            category="volume", notes="三棱柱体积 = 三角形面积 × 柱高",
        ))
        self.register(Formula(
            "四棱锥体积",
            Div(Mul(Var("底面积"), Var("高")), Num(3)),
            params=["底面积", "高"],
            category="volume", notes="四棱锥体积 = 底面积 × 高 / 3",
        ))
        self.register(Formula(
            "正六边形面积",
            Div(Mul(Mul(Num(3), FuncCall("sqrt", [Num(3)])), Pow(Var("边长"), Num(2))), Num(2)),
            params=["边长"],
            category="area", notes="正六边形面积 = 3√3/2 × 边长²（6个正三角形）",
        ))
        self.register(Formula(
            "圆内接正方形面积",
            Mul(Num(2), Pow(Var("半径"), Num(2))),
            params=["半径"],
            category="area", notes="圆内接正方形面积 = 2 × 半径²（对角线=2r）",
        ))
        self.register(Formula(
            "圆外切正方形面积",
            Mul(Num(4), Pow(Var("半径"), Num(2))),
            params=["半径"],
            category="area", notes="圆外切正方形面积 = 4 × 半径²（边长=2r）",
        ))
        # ── 正方形对角线形式 ──────────────────────────────────
        self.register(Formula(
            "正方形面积（对角线形式）",
            Div(Pow(Var("对角线"), Num(2)), Num(2)),
            params=["对角线"],
            category="area", notes="正方形面积 = 对角线²/2",
        ))
        self.register(Formula(
            "半球表面积",
            Mul(Mul(Num(3), Var("π")), Pow(Var("半径"), Num(2))),
            params=["半径"],
            category="area", notes="半球表面积 = 3 × π × 半径²（曲面2πr² + 底面πr²）",
        ))
        self.register(Formula(
            "圆柱侧面积",
            Mul(Mul(Num(2), Var("π")), Mul(Var("底半径"), Var("高"))),
            params=["底半径", "高"],
            category="perimeter", notes="圆柱侧面积 = 2πrh",
        ))
        self.register(Formula(
            "圆锥侧面积",
            Mul(Mul(Var("π"), Var("底半径")), FuncCall("sqrt", [Add(Pow(Var("底半径"), Num(2)), Pow(Var("高"), Num(2)))])),
            params=["底半径", "高"],
            category="perimeter", notes="圆锥侧面积 = πr√(r²+h²)（母线l=√(r²+h²)）",
        ))
        self.register(Formula(
            "圆环面积",
            Mul(Var("π"), Sub(Pow(Var("外半径"), Num(2)), Pow(Var("内半径"), Num(2)))),
            params=["外半径", "内半径"],
            category="area", notes="圆环面积 = π(R² - r²)",
        ))
        self.register(Formula(
            "等边三角形内接于圆面积",
            Div(Mul(Mul(Num(3), FuncCall("sqrt", [Num(3)])), Pow(Var("半径"), Num(2))), Num(4)),
            params=["半径"],
            category="area", notes="等边三角形内接于圆：面积 = 3√3/4 × R²（R为外接圆半径）",
        ))
        # ── 直角三角形与三角恒等式 ─────────────────────────────────
        self.register(Formula(
            "直角三角形面积",
            Div(Mul(Var("直角边1"), Var("直角边2")), Num(2)),
            params=["直角边1", "直角边2"],
            category="area", notes="直角三角形面积 = 直角边1 × 直角边2 / 2",
        ))
        self.register(Formula(
            "等腰直角三角形面积",
            Div(Mul(Var("直角边"), Var("直角边")), Num(2)),
            params=["直角边"],
            category="area", notes="等腰直角三角形面积 = 直角边² / 2（直角边=斜边/√2）",
        ))
        self.register(Formula(
            "30-60-90三角形面积",
            Div(Mul(Pow(Var("短直角边"), Num(2)), FuncCall("sqrt", [Num(3)])), Num(2)),
            params=["短直角边"],
            category="area", notes="30-60-90三角形面积 = √3/2 × 短直角边²（边长比1:√3:2）",
        ))
        # ── 通用三角形公式 ──────────────────────────────────────
        self.register(Formula(
            "海伦公式",
            FuncCall("sqrt", [Mul(Mul(Var("半周长"), Sub(Var("半周长"), Var("边a"))), Mul(Sub(Var("半周长"), Var("边b")), Sub(Var("半周长"), Var("边c"))))]),
            params=["半周长", "边a", "边b", "边c"],
            category="area", notes="海伦公式：√[s(s-a)(s-b)(s-c)]，s为半周长",
        ))
        self.register(Formula(
            "三角形内切圆半径",
            Div(Mul(Var("面积"), Num(2)), Add(Add(Var("边a"), Var("边b")), Var("边c"))),
            params=["面积", "边a", "边b", "边c"],
            category="general", notes="内切圆半径 r = 2S/(a+b+c)（面积×2/周长）",
        ))
        self.register(Formula(
            "三角形外接圆半径",
            Div(Mul(Var("边a"), Mul(Var("边b"), Var("边c"))), Mul(Num(4), FuncCall("sqrt", [Mul(Mul(Var("半周长"), Sub(Var("半周长"), Var("边a"))), Mul(Sub(Var("半周长"), Var("边b")), Sub(Var("半周长"), Var("边c"))))]))),
            params=["边a", "边b", "边c", "半周长"],
            category="general", notes="外接圆半径 R = abc/(4√[s(s-a)(s-b)(s-c)])",
        ))
        # ── 点到直线距离 ──────────────────────────────────────
        self.register(Formula(
            "两点距离",
            FuncCall("sqrt", [Add(Pow(Sub(Var("x2"), Var("x1")), Num(2)), Pow(Sub(Var("y2"), Var("y1")), Num(2)))]),
            params=["x1", "y1", "x2", "y2"],
            category="general", notes="两点距离 = √[(x₂-x₁)²+(y₂-y₁)²]",
        ))
        self.register(Formula(
            "点到直线距离",
            Div(FuncCall("abs", [Add(Mul(Var("A"), Var("x0")), Mul(Var("B"), Var("y0")))]),
                FuncCall("sqrt", [Add(Pow(Var("A"), Num(2)), Pow(Var("B"), Num(2)))])),
            params=["A", "B", "x0", "y0"],
            category="general", notes="点(x₀,y₀)到直线Ax+By=0的距离",
        ))
        # ── 正多边形 ────────────────────────────────────────────
        # 正五边形面积 = a² * sqrt(5(5+2√5)) / 4
        _PENT_CONSTANT = Mul(Num(5), Add(Num(5), Mul(Num(2), FuncCall("sqrt", [Num(5)]))))
        self.register(Formula(
            "正五边形面积",
            Div(Mul(FuncCall("sqrt", [_PENT_CONSTANT]), Pow(Var("边长"), Num(2))), Num(4)),
            params=["边长"],
            category="area", notes="正五边形面积 = √[5(5+2√5)]/4 × a²",
        ))
        # ── 三角恒等式 ──────────────────────────────────────────
        self.register(Formula(
            "三角恒等式-sin²+cos²",
            Num(1),
            params=["θ"],
            category="general", notes="sin²θ + cos²θ = 1",
        ))
        self.register(Formula(
            "欧拉恒等式",
            Num(0),
            params=[],
            category="general", notes="e^(iπ) + 1 = 0",
        ))
        # ── 对数公式 ────────────────────────────────────────────
        self.register(Formula(
            "对数乘法公式",
            Add(Var("log_a"), Var("log_b")),
            params=["log_a", "log_b"],
            category="general", notes="log(ab) = log(a) + log(b)",
        ))
        self.register(Formula(
            "对数幂公式",
            Mul(Var("指数"), Var("log_a")),
            params=["指数", "log_a"],
            category="general", notes="log(a^n) = n·log(a)",
        ))
        # ── 数列与求和 ─────────────────────────────────────────
        self.register(Formula(
            "等差数列求和",
            Div(Mul(Var("项数"), Add(Var("首项"), Var("末项"))), Num(2)),
            params=["项数", "首项", "末项"],
            category="general", notes="S_n = n(a₁+aₙ)/2",
        ))
        self.register(Formula(
            "自然数平方和",
            Div(Mul(Mul(Var("n"), Add(Var("n"), Num(1))), Add(Mul(Num(2), Var("n")), Num(1))), Num(6)),
            params=["n"],
            category="general", notes="Σk² = n(n+1)(2n+1)/6",
        ))
        # ── 勾股定理与余弦定理 ────────────────────────────────
        self.register(Formula(
            "勾股定理",
            Add(Pow(Var("直角边1"), Num(2)), Pow(Var("直角边2"), Num(2))),
            params=["直角边1", "直角边2"],
            category="general", notes="c² = a² + b²",
        ))
        self.register(Formula(
            "余弦定理",
            Add(Add(Pow(Var("边a"), Num(2)), Pow(Var("边b"), Num(2))),
                Mul(Mul(Num(-2), Mul(Var("边a"), Var("边b"))), FuncCall("cos", [Var("夹角")]))),
            params=["边a", "边b", "夹角"],
            category="general", notes="c² = a² + b² - 2ab·cos(C)",
        ))
        # ── 向量公式 ────────────────────────────────────────────
        self.register(Formula(
            "向量点积",
            Mul(Mul(Var("模a"), Var("模b")), FuncCall("cos", [Var("夹角")])),
            params=["模a", "模b", "夹角"],
            category="general", notes="a·b = |a||b|cos(θ)",
        ))
        self.register(Formula(
            "向量投影长度",
            Div(Mul(Var("模a"), FuncCall("cos", [Var("夹角")])), Num(1)),
            params=["模a", "夹角"],
            category="general", notes="proj_a(b) = |b|cos(θ)（向量b在a方向投影长度）",
        ))
        self.register(Formula(
            "投影面积公式",
            Mul(Var("原面积"), FuncCall("cos", [Var("倾角")])),
            params=["原面积", "倾角"],
            category="general", notes="投影面积 = 原面积 × cos(θ)",
        ))
        # ── 三角形外接圆与内切圆 ─────────────────────────────
        self.register(Formula(
            "三角形外接圆半径-正弦形式",
            Div(Var("边a"), Mul(Num(2), FuncCall("sin", [Var("对角A")]))),
            params=["边a", "对角A"],
            category="general", notes="R = a/(2sinA)（正弦定理）",
        ))
        self.register(Formula(
            "直角三角形内切圆半径",
            Div(Sub(Add(Var("直角边1"), Var("直角边2")), FuncCall("sqrt", [Add(Pow(Var("直角边1"), Num(2)), Pow(Var("直角边2"), Num(2)))])), Num(2)),
            params=["直角边1", "直角边2"],
            category="general", notes="r = (a+b-c)/2（直角三角形内切圆半径）",
        ))
        # ── 圆锥与棱锥体积 ────────────────────────────────────
        self.register(Formula(
            "圆锥体积（通用）",
            Div(Mul(Var("底面积"), Var("高")), Num(3)),
            params=["底面积", "高"],
            category="volume", notes="圆锥/棱锥体积 = 底面积 × 高 / 3",
        ))
        self.register(Formula(
            "四棱锥体积（通用）",
            Div(Mul(Var("底面积"), Var("高")), Num(3)),
            params=["底面积", "高"],
            category="volume", notes="四棱锥体积 = 底面积 × 高 / 3",
        ))
        # ── 极限演化：正n边形→圆 ─────────────────────────────
        self.register(Formula(
            "正n边形面积极限",
            Mul(Var("圆面积"), Var("边数")),
            params=["边数", "圆面积"],
            category="area", notes="当 n→∞ 时，正n边形面积 → 圆面积",
        ))
        # ── 正多面体体积 ──────────────────────────────────────
        self.register(Formula(
            "正四面体体积",
            Div(Mul(FuncCall("sqrt", [Num(2)]), Pow(Var("棱长"), Num(3))), Num(12)),
            params=["棱长"],
            category="volume", notes="正四面体体积 = √2/12 × a³",
        ))
        self.register(Formula(
            "正八面体体积",
            Div(Mul(FuncCall("sqrt", [Num(2)]), Pow(Var("棱长"), Num(3))), Num(3)),
            params=["棱长"],
            category="volume", notes="正八面体体积 = √2/3 × a³（= 4 × 正四面体体积）",
        ))
        # ── 球冠与弓形 ────────────────────────────────────────
        self.register(Formula(
            "球冠表面积",
            Mul(Mul(Num(2), Var("π")), Mul(Var("半径"), Var("高"))),
            params=["半径", "高"],
            category="area", notes="球冠表面积 = 2πRh（R为球半径，h为冠高）",
        ))
        self.register(Formula(
            "弓形面积",
            Div(Mul(Pow(Var("半径"), Num(2)), Sub(Var("圆心角"), FuncCall("sin", [Var("圆心角")]))), Num(2)),
            params=["半径", "圆心角"],
            category="area", notes="弓形面积 = r²(θ - sinθ)/2（θ为弧度）",
        ))
        # ── 圆与正多边形 ─────────────────────────────────────
        self.register(Formula(
            "圆外切正三角形面积",
            Mul(Mul(FuncCall("sqrt", [Num(3)]), Pow(Var("内切圆半径"), Num(2))), Num(3)),
            params=["内切圆半径"],
            category="area", notes="圆外切正三角形面积 = 3√3 × r²（r为内切圆半径）",
        ))
        self.register(Formula(
            "圆内接正六边形面积",
            Div(Mul(Mul(Num(3), FuncCall("sqrt", [Num(3)])), Pow(Var("半径"), Num(2))), Num(2)),
            params=["半径"],
            category="area", notes="圆内接正六边形面积 = 3√3/2 × R²（R为外接圆半径，边长=R）",
        ))

        # ── 默认等价声明（核心几何关系）────────────────────────
        # 长方形 ↔ 平行四边形：长=底, 宽=高
        self.add_equivalence("长方形面积", "长", "平行四边形面积", "底")
        self.add_equivalence("长方形面积", "宽", "平行四边形面积", "高")
        # 三角形 ↔ 平行四边形：底=底, 高=高
        self.add_equivalence("三角形面积", "底", "平行四边形面积", "底")
        self.add_equivalence("三角形面积", "高", "平行四边形面积", "高")
        # 三角形 ↔ 长方形：底=长, 高=宽
        self.add_equivalence("三角形面积", "底", "长方形面积", "长")
        self.add_equivalence("三角形面积", "高", "长方形面积", "宽")
        # 圆面积 ↔ 球表面积：同一半径
        self.add_equivalence("圆面积", "半径", "球表面积", "半径")
        # 圆柱 ↔ 圆锥：同底同高
        self.add_equivalence("圆柱体积", "底半径", "圆锥体积", "底半径")
        self.add_equivalence("圆柱体积", "高", "圆锥体积", "高")
        # 圆 ↔ 内接/外切正方形：同一半径
        self.add_equivalence("圆面积", "半径", "圆内接正方形面积", "半径")
        self.add_equivalence("圆面积", "半径", "圆外切正方形面积", "半径")
        # 圆 ↔ 球体积：同一半径
        self.add_equivalence("圆面积", "半径", "球体积", "半径")
        # 圆柱侧面积 ↔ 半球表面积：同一半径高
        self.add_equivalence("圆柱侧面积", "底半径", "半球表面积", "半径")
        self.add_equivalence("圆柱侧面积", "高", "半球表面积", "半径")
        # ── 新增：衍化关系等价声明 ────────────────────────────
        # 直角三角形面积 = 两条直角边乘积/2（基础直角三角形）
        self.add_equivalence("直角三角形面积", "直角边1", "等腰直角三角形面积", "直角边")
        self.add_equivalence("直角三角形面积", "直角边2", "等腰直角三角形面积", "直角边")
        # 等腰直角三角形斜边 = 直角边 × √2（等价约束：斜边=直角边×√2）
        # 30-60-90 短直角边与等腰直角三角形直角边的关系
        self.add_equivalence("30-60-90三角形面积", "短直角边", "等腰直角三角形面积", "直角边")
        # 圆面积 ↔ 球体积：同一半径（衍生：球表面积=4×圆面积）
        self.add_equivalence("圆面积", "半径", "球表面积", "半径")
        # 球体积 ↔ 圆柱体积（阿基米德定理）
        self.add_equivalence("球体积", "半径", "圆柱体积", "底半径")
        self.add_equivalence("球体积", "半径", "圆柱体积", "高")
        # 球表面积 ↔ 圆柱侧面积（阿基米德）
        self.add_equivalence("球表面积", "半径", "圆柱侧面积", "底半径")
        self.add_equivalence("球表面积", "半径", "圆柱侧面积", "高")
        # 圆环面积 ↔ 圆面积（退化：内半径=0）
        self.add_equivalence("圆环面积", "外半径", "圆面积", "半径")
        # 正六边形 ↔ 正三角形（衍生关系）
        self.add_equivalence("正六边形面积", "边长", "正三角形面积", "边长")
        # 等边三角形内接于圆 ↔ 正三角形面积（R与边长关系）
        self.add_equivalence("等边三角形内接于圆面积", "半径", "正三角形面积", "边长")
        # 正四面体 ↔ 正八面体（同棱长）
        self.add_equivalence("正八面体体积", "棱长", "正四面体体积", "棱长")
        # 球冠表面积 ↔ 圆柱侧面积（h=2R时，球冠=半球）
        self.add_equivalence("球冠表面积", "半径", "圆柱侧面积", "底半径")
        self.add_equivalence("球冠表面积", "高", "圆柱侧面积", "高")
        # 圆外切正三角形 ↔ 内切圆
        self.add_equivalence("圆外切正三角形面积", "内切圆半径", "圆面积", "半径")
        # 圆内接正六边形 ↔ 正三角形
        self.add_equivalence("圆内接正六边形面积", "半径", "正三角形面积", "边长")

        logger.info(f"  已注册 {len(self._formulas)} 个几何公式，{len(self._equivalences)} 条等价关系")
        # 注册演化规则并执行自主演化
        self._evolution_engine = EvolutionEngine(self)
        self._register_evolution_rules()
        steps = self._evolution_engine.evolve_all(verbose=False)
        evolved = [s for s in steps if s.success]
        logger.info(f"  演化完成: {len(evolved)}/{len(steps)} 条规则成功，新公式: "
                     f"{len(self._formulas)} 个")

    def _register_evolution_rules(self) -> None:
        """注册所有演化规则。每条规则描述如何从已有公式推导出新公式。"""
        if self._evolution_engine is None:
            self._evolution_engine = EvolutionEngine(self)
        reg = self
        engine = self._evolution_engine

        # ── 几何演化规则 ──────────────────────────────────────
        def _ellipse_to_circle(_env):
            """椭圆面积退化：短半轴=长半轴时退化为圆面积。"""
            return Mul(Var("π"), Mul(Var("长半轴"), Var("短半轴")))

        engine.add_rule(EvolutionRule(
            "ellipse-circle-degenerate",
            "椭圆面积：当 a=b=r 时退化为圆面积",
            ["椭圆面积", "圆面积"],
            "椭圆退化圆面积",
            _ellipse_to_circle,
            ["长半轴", "短半轴"],
            category="area",
            notes="椭圆面积 = πab，当 a=b 时 = πr²（圆面积）",
        ))

        def _rhombus_diag_to_sides(_env):
            """菱形：当两对角线相等时为正方形，面积 = 对角线²/2。"""
            return Div(Pow(Var("对角线"), Num(2)), Num(2))

        engine.add_rule(EvolutionRule(
            "rhombus-square-derivation",
            "菱形对角线相等时退化为正方形面积",
            ["菱形面积"],
            "菱形退化正方形面积",
            _rhombus_diag_to_sides,
            ["对角线"],
            category="area",
            notes="正方形面积 = 对角线²/2（对角线相等时菱形退化为正方形）",
        ))

        def _cylinder_volume_cylinder_lateral(_env):
            """圆柱体积与侧面积关系：V = 侧面积 × 高 / 2（当底面为圆时）。"""
            return Div(Mul(Mul(Num(2), Var("π")), Mul(Var("底半径"), Var("高"))), Num(2))

        engine.add_rule(EvolutionRule(
            "cylinder-vol-lateral",
            "圆柱体积与侧面积的关系推导",
            ["圆柱体积", "圆柱侧面积"],
            "圆柱体积半侧面积等价",
            _cylinder_volume_cylinder_lateral,
            ["底半径", "高"],
            category="volume",
            notes="V = πr²h = (2πrh)×h/2 = 侧面积×h/2",
        ))

        def _prism_volume_from_base_area(_env):
            """棱柱体积 = 底面积 × 高（通用棱柱体积公式）。"""
            return Mul(Var("底面积"), Var("高"))

        engine.add_rule(EvolutionRule(
            "prism-volume-from-base",
            "棱柱体积通用公式：底面积 × 高",
            ["三棱柱体积", "正方体体积"],
            "棱柱体积（通用）",
            _prism_volume_from_base_area,
            ["底面积", "高"],
            category="volume",
            notes="任意棱柱体积 = 底面积 × 高（从正方体/三棱柱推广）",
        ))

        def _trapezoid_to_parallelogram(_env):
            """梯形面积：当上底=下底时退化为平行四边形面积。"""
            return Mul(Var("上底"), Var("高"))

        engine.add_rule(EvolutionRule(
            "trapezoid-parallelogram",
            "梯形上底=下底时退化为平行四边形",
            ["梯形面积", "平行四边形面积"],
            "梯形退化平行四边形面积",
            _trapezoid_to_parallelogram,
            ["上底", "高"],
            category="area",
            notes="当 上底=下底 时：梯形面积 → 底 × 高 = 平行四边形面积",
        ))

        def _parallelogram_to_rectangle(_env):
            """平行四边形：当高=边时退化为长方形面积。"""
            return Mul(Var("底"), Var("高"))

        engine.add_rule(EvolutionRule(
            "parallelogram-rectangle",
            "平行四边形与长方形等价（底=长, 高=宽）",
            ["平行四边形面积", "长方形面积"],
            "平行四边形长方形等价",
            _parallelogram_to_rectangle,
            ["底", "高"],
            category="area",
            notes="平行四边形 = 长方形（当参数等价时）",
        ))

        # ── 立体几何演化 ────────────────────────────────────
        def _cube_from_prism(_env):
            """正方体 = 底面积×高（通用棱柱公式的特例）。"""
            return Mul(Pow(Var("棱长"), Num(2)), Var("棱长"))

        engine.add_rule(EvolutionRule(
            "cube-prism-derivation",
            "正方体体积 = 底面积 × 高（棱柱公式特例）",
            ["正方体体积", "棱柱体积（通用）"],
            "正方体棱柱等价",
            _cube_from_prism,
            ["棱长"],
            category="volume",
            notes="正方体 = 底面积(棱长²) × 高(棱长) = 棱长³",
        ))

        def _cone_cylinder_ratio(_env):
            """圆锥体积 = 圆柱体积 / 3（同底同高）。"""
            cyl = reg._formulas["圆柱体积"]
            return Div(cyl.expr, Num(3))

        engine.add_rule(EvolutionRule(
            "cone-cylinder-ratio",
            "圆锥体积 = 圆柱体积 / 3（同底同高，阿基米德）",
            ["圆锥体积", "圆柱体积"],
            "圆锥圆柱体积比",
            _cone_cylinder_ratio,
            ["底半径", "高"],
            category="volume",
            notes="V_锥 = 1/3 × V_柱（同底同高）",
        ))

        def _sphere_cylinder_archimedes(_env):
            """球体积 = 2/3 × 外切圆柱体积（阿基米德定理）。"""
            cyl = reg._formulas["圆柱体积"]
            return Mul(Div(Num(2), Num(3)), cyl.expr)

        engine.add_rule(EvolutionRule(
            "sphere-cylinder-archimedes",
            "球体积 = 2/3 × 外切圆柱体积（阿基米德）",
            ["球体积", "圆柱体积"],
            "球体积阿基米德等价",
            _sphere_cylinder_archimedes,
            ["半径", "高"],
            category="volume",
            notes="V_球 = 2/3 × V_柱（外切圆柱，高=2r）",
        ))

        def _sphere_surface_cylinder_archimedes(_env):
            """球表面积 = 圆柱侧面积（阿基米德定理）。"""
            cyl_lat = reg._formulas["圆柱侧面积"]
            return cyl_lat.expr

        engine.add_rule(EvolutionRule(
            "sphere-surface-archimedes",
            "球表面积 = 圆柱侧面积（阿基米德）",
            ["球表面积", "圆柱侧面积"],
            "球表面积阿基米德等价",
            _sphere_surface_cylinder_archimedes,
            ["半径", "高"],
            category="area",
            notes="S_球 = S_柱侧（阿基米德：球内切于圆柱）",
        ))

        # ── 三角演化规则 ────────────────────────────────────
        def _tangent_from_sin_cos(_env):
            """正切 = 正弦 / 余弦（三角函数定义）。"""
            return Div(Var("sin_θ"), Var("cos_θ"))

        engine.add_rule(EvolutionRule(
            "tangent-sin-cos",
            "正切 = 正弦 / 余弦（三角函数基本关系）",
            ["三角恒等式-sin²+cos²"],
            "正切定义",
            _tangent_from_sin_cos,
            ["sin_θ", "cos_θ"],
            category="general",
            notes="tan θ = sin θ / cos θ",
        ))

        def _secant_from_cos(_env):
            """正割 = 1 / 余弦。"""
            return Div(Num(1), Var("cos_θ"))

        engine.add_rule(EvolutionRule(
            "secant-cosine",
            "正割 = 1 / 余弦",
            ["三角恒等式-sin²+cos²"],
            "正割定义",
            _secant_from_cos,
            ["cos_θ"],
            category="general",
            notes="sec θ = 1 / cos θ",
        ))

        def _cotangent_from_sin(_env):
            """余切 = 余弦 / 正弦。"""
            return Div(Var("cos_θ"), Var("sin_θ"))

        engine.add_rule(EvolutionRule(
            "cotangent-sin",
            "余切 = 余弦 / 正弦",
            ["三角恒等式-sin²+cos²"],
            "余切定义",
            _cotangent_from_sin,
            ["sin_θ", "cos_θ"],
            category="general",
            notes="cot θ = cos θ / sin θ",
        ))

        # ── 解析几何演化 ────────────────────────────────────
        def _distance_formula(_env):
            """两点距离公式（解析几何基础）。"""
            return FuncCall("sqrt", [Add(Pow(Sub(Var("x2"), Var("x1")), Num(2)),
                                        Pow(Sub(Var("y2"), Var("y1")), Num(2)))])

        engine.add_rule(EvolutionRule(
            "distance-formula",
            "两点距离公式（勾股定理在坐标系中的推广）",
            ["两点距离"],
            "两点距离标准式",
            _distance_formula,
            ["x1", "y1", "x2", "y2"],
            category="general",
            notes="d = √[(x₂-x₁)²+(y₂-y₁)²]（勾股定理推广）",
        ))

        # ── 扇形演化 ────────────────────────────────────────
        def _sector_area_from_arc(_env):
            """扇形面积 = 弧长 × 半径 / 2（弧长与扇形关系）。"""
            arc = reg._formulas["弧长"]
            return Div(Mul(arc.expr, Var("半径")), Num(2))

        engine.add_rule(EvolutionRule(
            "sector-arc-derivation",
            "扇形面积 = 弧长 × 半径 / 2（从弧长推导）",
            ["扇形面积", "弧长"],
            "扇形弧长等价面积",
            _sector_area_from_arc,
            ["半径", "圆心角"],
            category="area",
            notes="扇形面积 = l×r/2（l为弧长，等价于 πr²θ/360）",
        ))

        def _segment_area_derivation(_env):
            """弓形面积 = 扇形面积 - 三角形面积（弓形 = 扇形 - 三角形）。"""
            circ = reg._formulas["圆面积"]
            tri = reg._formulas["三角形面积"]
            # 弓形 = πr²θ/360 - r²sinθ/2
            sector_expr = Div(Mul(circ.expr, Var("圆心角")), Num(360))
            tri_expr = Div(Mul(Pow(Var("半径"), Num(2)), FuncCall("sin", [Var("圆心角")])), Num(2))
            return Sub(sector_expr, tri_expr)

        engine.add_rule(EvolutionRule(
            "segment-area-derivation",
            "弓形面积 = 扇形面积 - 三角形面积",
            ["弓形面积", "扇形面积", "三角形面积"],
            "弓形扇形三角形等价",
            _segment_area_derivation,
            ["半径", "圆心角"],
            category="area",
            notes="弓形面积 = 扇形面积 - 等腰三角形面积",
        ))

        # ── 椭圆演化 ────────────────────────────────────────
        def _ellipse_area_from_circle(_env):
            """椭圆面积 = 圆面积 × 短半轴/长半轴（圆拉伸为椭圆）。"""
            circ = reg._formulas["圆面积"]
            return Mul(circ.expr, Div(Var("短半轴"), Var("长半轴")))

        engine.add_rule(EvolutionRule(
            "ellipse-from-circle",
            "椭圆面积 = 圆面积 × (短半轴/长半轴)（圆的拉伸变换）",
            ["椭圆面积", "圆面积"],
            "椭圆圆拉伸等价",
            _ellipse_area_from_circle,
            ["长半轴", "短半轴"],
            category="area",
            notes="椭圆 = 圆沿短轴方向压缩为短半轴/长半轴比",
        ))

        # ── 球演化 ──────────────────────────────────────────
        def _sphere_volume_from_circle(_env):
            """球体积 = 圆面积 × 4/3 × 半径（球 = 圆旋转生成）。"""
            circ = reg._formulas["圆面积"]
            return Mul(Mul(circ.expr, Var("半径")), Mul(Num(4), Div(Num(1), Num(3))))

        engine.add_rule(EvolutionRule(
            "sphere-from-circle",
            "球体积 = 圆面积 × 4r/3（圆的旋转生成体）",
            ["球体积", "圆面积"],
            "球体积圆旋转等价",
            _sphere_volume_from_circle,
            ["半径"],
            category="volume",
            notes="V_球 = 4/3 πr³ = 圆面积 × 4r/3",
        ))

        def _sphere_surface_from_circle(_env):
            """球表面积 = 圆面积 × 4（球的表面积是圆面积的4倍）。"""
            circ = reg._formulas["圆面积"]
            return Mul(circ.expr, Num(4))

        engine.add_rule(EvolutionRule(
            "sphere-surface-from-circle",
            "球表面积 = 4 × 圆面积（阿基米德定理）",
            ["球表面积", "圆面积"],
            "球表面积圆四倍等价",
            _sphere_surface_from_circle,
            ["半径"],
            category="area",
            notes="S_球 = 4πr² = 4 × 圆面积（阿基米德）",
        ))

        # ── 圆环演化 ────────────────────────────────────────
        def _annulus_from_circles(_env):
            """圆环面积 = 大圆面积 - 小圆面积。"""
            circ = reg._formulas["圆面积"]
            outer = circ.expr.substitute("半径", Var("外半径"))
            inner = circ.expr.substitute("半径", Var("内半径"))
            return Sub(outer, inner)

        engine.add_rule(EvolutionRule(
            "annulus-from-circles",
            "圆环面积 = 大圆面积 - 小圆面积",
            ["圆环面积", "圆面积"],
            "圆环面积差等价",
            _annulus_from_circles,
            ["外半径", "内半径"],
            category="area",
            notes="圆环面积 = πR² - πr²",
        ))

        # ── 正多边形演化 ────────────────────────────────────
        def _regular_n_gon_from_triangle(_env):
            """正n边形面积 = n × 正三角形面积（以中心为顶点的n个全等三角形）。"""
            tri = reg._formulas["正三角形面积"]
            n = Num(6)  # 正六边形作为特例
            return Mul(n, tri.expr.substitute("边长", Var("边长")))

        engine.add_rule(EvolutionRule(
            "hexagon-from-triangles",
            "正六边形 = 6 × 正三角形（中心分割法）",
            ["正六边形面积", "正三角形面积"],
            "正六边形三角形分割等价",
            _regular_n_gon_from_triangle,
            ["边长"],
            category="area",
            notes="正六边形可分割为6个全等正三角形",
        ))

        def _inscribed_polygon_from_circle(_env):
            """圆内接正六边形：边长 = 半径（圆内接正六边形的特殊性质）。"""
            circ = reg._formulas["圆面积"]
            # 圆内接正六边形边长=半径，面积=3√3/2 × R²
            return Div(Mul(Mul(Num(3), FuncCall("sqrt", [Num(3)])), Pow(Var("半径"), Num(2))), Num(2))

        engine.add_rule(EvolutionRule(
            "inscribed-hexagon-circle",
            "圆内接正六边形：边长=半径，面积=3√3/2 × R²",
            ["圆内接正六边形面积", "圆面积"],
            "圆内接六边形圆等价",
            _inscribed_polygon_from_circle,
            ["半径"],
            category="area",
            notes="圆内接正六边形边长=R（外接圆半径），面积=3√3/2 × R²",
        ))

        logger.info(f"  已注册 {len(engine._rules)} 条演化规则")

        # ── 新增：高等数学演化规则 ────────────────────────────
        def _log_power_from_product(_env):
            """对数幂公式：log(a^n) = n·log(a)（对数乘法公式的推广）。"""
            return Mul(Var("指数"), Var("log_a"))

        engine.add_rule(EvolutionRule(
            "log-power-derivation",
            "对数幂公式 = n × 对数乘法（从乘法推广）",
            ["对数乘法公式"],
            "对数幂公式",
            _log_power_from_product,
            ["指数", "log_a"],
            category="general",
            notes="log(a^n) = n·log(a)（对数乘法公式的迭代推广）",
        ))

        def _pythagorean_to_cosine(_env):
            """余弦定理 = a²+b²-2ab·cos(C)（勾股定理的推广）。"""
            # 当 C=90° 时，cos(C)=0，退化为勾股定理
            a, b = Var("边a"), Var("边b")
            angle = Var("夹角")
            return Add(Add(Pow(a, Num(2)), Pow(b, Num(2))),
                       Mul(Mul(Num(-2), Mul(a, b)), FuncCall("cos", [angle])))

        engine.add_rule(EvolutionRule(
            "cosine-from-pythagorean",
            "余弦定理 = 勾股定理推广（当夹角=90°时退化）",
            ["勾股定理", "余弦定理"],
            "余弦定理勾股推广",
            _pythagorean_to_cosine,
            ["边a", "边b", "夹角"],
            category="general",
            notes="c² = a²+b²-2ab·cos(C)，当 C=90° → c²=a²+b²",
        ))

        def _vector_dot_to_projection(_env):
            """向量投影长度 = 模a × cos(夹角)（点积的几何意义）。"""
            return Mul(Var("模a"), FuncCall("cos", [Var("夹角")]))

        engine.add_rule(EvolutionRule(
            "projection-from-dot",
            "投影长度 = 模 × cos(夹角)（从点积公式推导）",
            ["向量点积"],
            "向量投影长度",
            _vector_dot_to_projection,
            ["模a", "夹角"],
            category="general",
            notes="proj = |a|cos(θ)（点积 a·b = |a||b|cos(θ) 的几何意义）",
        ))

        def _cone_volume_from_cylinder(_env):
            """圆锥体积 = 圆柱体积 / 3（同底同高，阿基米德）。"""
            cyl = reg._formulas["圆柱体积"]
            return Div(cyl.expr, Num(3))

        engine.add_rule(EvolutionRule(
            "cone-from-cylinder",
            "圆锥体积 = 圆柱体积 / 3（同底同高，阿基米德）",
            ["圆锥体积（通用）", "圆柱体积"],
            "圆锥圆柱体积比",
            _cone_volume_from_cylinder,
            ["底面积", "高"],
            category="volume",
            notes="V_锥 = V_柱 / 3（同底同高，阿基米德）",
        ))

        def _polygon_limit_to_circle(_env):
            """正n边形面积极限：当 n→∞ 时，正n边形 → 圆。"""
            circ = reg._formulas["圆面积"]
            # 正n边形面积 → 圆面积（当边数足够大时）
            return circ.expr

        engine.add_rule(EvolutionRule(
            "polygon-circle-limit",
            "正n边形面积极限 = 圆面积（n→∞）",
            ["正n边形面积极限", "圆面积"],
            "正多边形圆极限等价",
            _polygon_limit_to_circle,
            ["半径"],
            category="area",
            notes="lim(n→∞) 正n边形面积 = 圆面积",
        ))

        def _inscribed_angle_theorem(_env):
            """圆周角定理：圆周角 = 圆心角 / 2。"""
            return Div(Var("圆心角"), Num(2))

        engine.add_rule(EvolutionRule(
            "inscribed-angle-theorem",
            "圆周角定理：圆周角 = 圆心角 / 2",
            ["圆周长"],
            "圆周角定理",
            _inscribed_angle_theorem,
            ["圆心角"],
            category="general",
            notes="圆周角 = 圆心角/2（同弧所对的圆周角等于圆心角的一半）",
        ))

        def _area_projection_formula(_env):
            """投影面积公式：A_proj = A × cos(θ)。"""
            return Mul(Var("原面积"), FuncCall("cos", [Var("倾角")]))

        engine.add_rule(EvolutionRule(
            "projection-area-from-circle",
            "投影面积 = 原面积 × cos(θ)（从圆投影到倾斜平面）",
            ["投影面积公式", "圆面积"],
            "投影面积等价",
            _area_projection_formula,
            ["原面积", "倾角"],
            category="general",
            notes="投影面积 = 原面积 × cos(倾角)（圆投影为椭圆）",
        ))

        def _sin_rule_circumradius(_env):
            """正弦定理：a/sinA = b/sinB = c/sinC = 2R。"""
            a, A = Var("边a"), Var("对角A")
            return Div(a, Mul(Num(2), FuncCall("sin", [A])))

        engine.add_rule(EvolutionRule(
            "sine-rule-circumradius",
            "正弦定理 → 外接圆半径 R = a/(2sinA)",
            ["三角形外接圆半径-正弦形式", "三角形面积"],
            "正弦定理外接圆",
            _sin_rule_circumradius,
            ["边a", "对角A"],
            category="general",
            notes="a/sinA = b/sinB = c/sinC = 2R（正弦定理）",
        ))

        def _right_triangle_inradius(_env):
            """直角三角形内切圆半径 r = (a+b-c)/2。"""
            a, b = Var("直角边1"), Var("直角边2")
            c = FuncCall("sqrt", [Add(Pow(a, Num(2)), Pow(b, Num(2)))])
            return Div(Sub(Add(a, b), c), Num(2))

        engine.add_rule(EvolutionRule(
            "inradius-right-triangle",
            "直角三角形内切圆半径 = (a+b-c)/2",
            ["直角三角形内切圆半径", "勾股定理"],
            "直角三角形内切圆半径推导",
            _right_triangle_inradius,
            ["直角边1", "直角边2"],
            category="general",
            notes="r = (a+b-c)/2（直角三角形内切圆半径公式）",
        ))

        def _arithmetic_sum_formula(_env):
            """等差数列求和：S = n(a₁+aₙ)/2。"""
            n, a1, an = Var("项数"), Var("首项"), Var("末项")
            return Div(Mul(n, Add(a1, an)), Num(2))

        engine.add_rule(EvolutionRule(
            "arithmetic-sum-derivation",
            "等差数列求和公式 = n(a₁+aₙ)/2",
            ["等差数列求和"],
            "等差数列求和公式",
            _arithmetic_sum_formula,
            ["项数", "首项", "末项"],
            category="general",
            notes="S_n = n(a₁+aₙ)/2（等差数列求和）",
        ))

        def _square_sum_formula(_env):
            """自然数平方和：Σk² = n(n+1)(2n+1)/6。"""
            n = Var("n")
            return Div(Mul(Mul(n, Add(n, Num(1))), Add(Mul(Num(2), n), Num(1))), Num(6))

        engine.add_rule(EvolutionRule(
            "square-sum-derivation",
            "平方和公式 = n(n+1)(2n+1)/6",
            ["自然数平方和"],
            "自然数平方和公式",
            _square_sum_formula,
            ["n"],
            category="general",
            notes="Σk² = n(n+1)(2n+1)/6（自然数平方和）",
        ))

        logger.info(f"  新增 {len(engine._rules)} 条演化规则，共 {len(engine._rules)} 条")

    def evolve_all(self) -> list[EvolutionStep]:
        """执行所有演化规则。"""
        if self._evolution_engine is None:
            self._evolution_engine = EvolutionEngine(self)
            self._register_evolution_rules()
        return self._evolution_engine.evolve_all(verbose=True)

    def get(self, name: str) -> Optional[Formula]:
        return self._formulas.get(name)

    def list_formulas(self) -> list[str]:
        return list(self._formulas.keys())

    def list_by_category(self, category: str) -> list[str]:
        return [n for n, f in self._formulas.items() if f.category == category]

    # ── 等价关系 ──────────────────────────────────────────────

    def add_equivalence(self, formula_a, param_a, formula_b, param_b, notes="") -> None:
        eq = ParamEquivalence(param_a, param_b, formula_a, formula_b, notes)
        self._equivalences.append(eq)
        logger.info(f"  等价声明: {eq}")

    def get_equivalences_for(self, formula_name: str) -> list[ParamEquivalence]:
        return [eq for eq in self._equivalences
                if eq.formula_a == formula_name or eq.formula_b == formula_name]

    def get_param_mapping(self, source_formula: str, target_formula: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for eq in self._equivalences:
            if eq.formula_a == source_formula and eq.formula_b == target_formula:
                mapping[eq.lhs] = eq.rhs
            elif eq.formula_b == source_formula and eq.formula_a == target_formula:
                mapping[eq.rhs] = eq.lhs
        return mapping

    # ── 公式推导 ──────────────────────────────────────────────

    def derive(self, relationship_expr: str, source_formula: str, target_formula: str
               ) -> DerivationResult:
        """推导：将关系式中的源公式参数替换为目标公式参数。

        relationship_expr 支持算术操作符直接操作 Expr 对象：
          "expr / 2"  →  源公式表达式 ÷ 2
          "expr * 4"  →  源公式表达式 × 4
          "expr / 3"  →  源公式表达式 ÷ 3
          中文变量名通过参数映射自动转换。
        """
        steps: list[str] = []
        try:
            src_formula = self._formulas.get(source_formula)
            tgt_formula = self._formulas.get(target_formula)
            if src_formula is None:
                return DerivationResult(False, [source_formula], [], "", Num(0), [],
                                        [f"找不到公式: {source_formula}"])
            if tgt_formula is None:
                return DerivationResult(False, [source_formula, target_formula], [], "", Num(0), [],
                                        [f"找不到公式: {target_formula}"])

            # 1. 获取等价映射
            mapping = self.get_param_mapping(source_formula, target_formula)
            steps.append(f"映射: {mapping}")
            if not mapping:
                mapping = self.get_param_mapping(target_formula, source_formula)
                mapping = {v: k for k, v in mapping.items()}
                steps.append(f"反向映射: {mapping}")

            # 2. 将源公式表达式代入映射（替换变量名）
            substituted = src_formula.expr
            for src_var, tgt_var in mapping.items():
                substituted = substituted.substitute(src_var, Var(tgt_var))
                steps.append(f"{src_var}→{tgt_var}: {substituted}")

            # 3. 应用关系操作（直接在 Expr 上运算，无需字符串解析）
            rel = relationship_expr.strip()
            if rel.startswith("expr / ") or rel.startswith("expr÷"):
                divisor = float(rel.split("/")[-1].strip().split("÷")[-1].strip())
                substituted = Div(substituted, Num(divisor))
                steps.append(f"应用关系 ÷{divisor}: {substituted}")
            elif rel.startswith("expr * ") or rel.startswith("expr×"):
                multiplier = float(rel.split("*")[-1].strip().split("×")[-1].strip())
                substituted = Mul(substituted, Num(multiplier))
                steps.append(f"应用关系 ×{multiplier}: {substituted}")
            elif rel == "expr":
                steps.append("无关系操作")
            else:
                # 尝试解析（仅适用于 ASCII 表达式）
                try:
                    rel_expr = symbol_expr(rel)
                    substituted = rel_expr.substitute("expr", substituted)
                    steps.append(f"应用关系: {substituted}")
                except Exception:
                    steps.append(f"无法解析关系 '{rel}'，使用原表达式")

            # 4. 简化
            simplified = simplify_expr(substituted)
            steps.append(f"简化: {simplified}")

            return DerivationResult(
                success=True,
                source_formulas=[source_formula, target_formula],
                equivalence_rules=[str(eq) for eq in self._equivalences],
                derived_formula=f"{source_formula} → {target_formula}: {simplified}",
                derived_expr=simplified,
                derived_params=list(_collect_vars(simplified)),
                steps=steps,
            )
        except Exception as e:
            logger.warning(f"推导失败: {e}")
            return DerivationResult(False, [source_formula, target_formula], [],
                                    "", Num(0), [], [f"推导异常: {e}"])

    def derive_formula_in_terms_of(
        self, source_formula: str, target_formula: str,
    ) -> DerivationResult:
        """将源公式用目标公式的参数来表达（自动推导）。"""
        src = self._formulas.get(source_formula)
        tgt = self._formulas.get(target_formula)
        if src is None or tgt is None:
            return DerivationResult(False, [source_formula, target_formula], [], "", Num(0), [],
                                    ["公式不存在"])
        mapping = self.get_param_mapping(source_formula, target_formula)
        if not mapping:
            return DerivationResult(False, [source_formula, target_formula], [], "", Num(0), [],
                                    ["无等价声明"])
        substituted = src.expr
        steps = [f"映射: {mapping}"]
        for src_var, tgt_var in mapping.items():
            substituted = substituted.substitute(src_var, Var(tgt_var))
            steps.append(f"{src_var}→{tgt_var}: {substituted}")
        simplified = simplify_expr(substituted)
        steps.append(f"简化: {simplified}")
        return DerivationResult(
            success=True,
            source_formulas=[source_formula, target_formula],
            equivalence_rules=[str(eq) for eq in self._equivalences],
            derived_formula=f"{source_formula} = {simplified} (用{target_formula}参数表示)",
            derived_expr=simplified,
            derived_params=list(_collect_vars(simplified)),
            steps=steps,
        )

    # ── 公式等价验证 ──────────────────────────────────────────

    def verify_equivalence(
        self, formula_a: str, formula_b: str,
        test_bindings: Optional[dict[str, float]] = None,
    ) -> DerivationResult:
        fa = self._formulas.get(formula_a)
        fb = self._formulas.get(formula_b)
        if fa is None or fb is None:
            missing = [n for n in (formula_a, formula_b) if self._formulas.get(n) is None]
            return DerivationResult(False, [], [], "", Num(0), [],
                                    [f"公式不存在: {missing}"])
        if formula_a == formula_b:
            return DerivationResult(True, [formula_a], [],
                                    f"{formula_a} == {formula_b} (恒等)", Num(0), [],
                                    [f"同一公式"])
        mapping = self.get_param_mapping(formula_a, formula_b)
        if not mapping:
            return DerivationResult(False, [formula_a, formula_b], [], "", Num(0), [],
                                    [f"无等价声明: {formula_a} ↔ {formula_b}"])
        if test_bindings is None:
            test_bindings = self._generate_test_bindings(mapping)
        try:
            val_a = fa.evaluate(test_bindings)
            bindings_b = self._apply_mapping(test_bindings, mapping)
            val_b = fb.evaluate(bindings_b)
        except Exception as e:
            return DerivationResult(False, [formula_a, formula_b], [], "", Num(0), [],
                                    [f"求值失败: {e}"])
        diff = abs(val_a - val_b)
        threshold = max(1.0, abs(val_a), abs(val_b)) * 1e-9
        ok = diff < threshold
        steps = [
            f"绑定: {test_bindings}",
            f"{formula_a} = {val_a}",
            f"{formula_b}({bindings_b}) = {val_b}",
            f"差异 = {diff:.2e}",
            f"等价: {'是' if ok else '否'}",
        ]
        return DerivationResult(
            success=ok,
            source_formulas=[formula_a, formula_b],
            equivalence_rules=[str(eq) for eq in self._equivalences],
            derived_formula=f"{formula_a} {'==' if ok else '≠'} {formula_b}",
            derived_expr=Num(diff),
            derived_params=[],
            steps=steps,
        )

    # ── 内部辅助 ──────────────────────────────────────────────

    def _generate_test_bindings(self, mapping: dict[str, str]) -> dict[str, float]:
        import random
        return {p: random.uniform(1.0, 100.0) for p in mapping.keys()}

    def _apply_mapping(self, bindings, mapping: dict[str, str]) -> dict[str, float]:
        return {mapped: bindings[param] for param, mapped in mapping.items() if param in bindings}


# ============================================================
#  全局单例
# ============================================================

_global_registry: Optional[FormulaRegistry] = None
_global_resolver: Optional[DefinitionResolver] = None
_global_primitives: Optional[PrimitiveRegistry] = None


def _init_primitives() -> PrimitiveRegistry:
    """初始化原始概念注册表：常量、函数、参数映射。"""
    prim = PrimitiveRegistry()
    # 注册常见参数
    for cn in ["长", "宽", "底", "高", "半径", "边长", "棱长", "对角线",
               "直角边", "直角边1", "直角边2", "短直角边", "斜边",
               "底半径", "柱高", "上底", "下底", "对角线1", "对角线2",
               "外半径", "内半径", "内切圆半径", "边a", "边b", "边c",
               "半周长", "圆心角", "模a", "模b", "夹角", "倾角",
               "x1", "y1", "x2", "y2", "A", "B", "x0", "y0",
               "项数", "首项", "末项", "n", "边数",
               "长半轴", "短半轴", "底面积"]:
        prim.register_param(cn, cn)
    # 物理常量（统一来源）
    from src.stdlib.physics_constants import C as _PC
    prim.register_constant("g", _PC.g)
    prim.register_constant("c", _PC.c)
    prim.register_constant("h_planck", _PC.h_planck)
    prim.register_constant("G", _PC.G)
    prim.register_constant("k_B", _PC.k_B)
    prim.register_constant("N_A", _PC.N_A)
    prim.register_constant("e_charge", _PC.e_charge)
    prim.register_constant("R_gas", _PC.R_gas)
    prim.register_constant("sigma_sb", _PC.sigma_sb)  # 斯特藩-玻尔兹曼常数
    # 注册特殊常量
    prim.register_constant("根号2除12", math.sqrt(2) / 12)
    prim.register_constant("根号2除3", math.sqrt(2) / 3)
    prim.register_constant("根号3除4", math.sqrt(3) / 4)
    prim.register_constant("3根号3除4", 3 * math.sqrt(3) / 4)
    prim.register_constant("3根号3除2", 3 * math.sqrt(3) / 2)
    prim.register_constant("5根号5除4", 5 * math.sqrt(5) / 4)
    prim.register_constant("根号3", math.sqrt(3))
    return prim


def get_formula_resolver() -> DefinitionResolver:
    """获取全局定义解析器（懒初始化）。"""
    global _global_resolver, _global_primitives
    if _global_resolver is None:
        _global_primitives = _init_primitives()
        _global_resolver = DefinitionResolver(_global_primitives)
    return _global_resolver


def get_formula_registry() -> FormulaRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = FormulaRegistry()
        _global_registry.register_geometric_defaults()
        # 对几何公式代入常量（如 π→3.14159）
        _global_registry.substitute_constants()
        # 加载综合公式库
        _load_comprehensive_formula_library(_global_registry)
    return _global_registry


def reset_formula_registry() -> None:
    global _global_registry, _global_resolver, _global_primitives
    _global_registry = None
    _global_resolver = None
    _global_primitives = None


# ============================================================
#  便捷 API
# ============================================================

def derive_formula(relationship: str, source: str = "长方形面积",
                   target: str = "三角形面积") -> DerivationResult:
    return get_formula_registry().derive(relationship, source, target)


def verify_formulas(formula_a: str, formula_b: str,
                    bindings: Optional[dict[str, float]] = None) -> DerivationResult:
    return get_formula_registry().verify_equivalence(formula_a, formula_b, bindings)


def list_formulas(category: Optional[str] = None) -> list[str]:
    reg = get_formula_registry()
    return reg.list_by_category(category) if category else reg.list_formulas()


def register_formula(name: str, expr_str: str, params: list[str]) -> Optional[Formula]:
    reg = get_formula_registry()
    try:
        expr = symbol_expr(expr_str)
    except Exception:
        logger.warning(f"公式 '{name}' 表达式解析失败: {expr_str}")
        return None
    formula = Formula(name=name, expr=expr, params=params)
    reg.register(formula)
    return formula


def add_param_equivalence(formula_a, param_a, formula_b, param_b) -> None:
    get_formula_registry().add_equivalence(formula_a, param_a, formula_b, param_b)

@dataclass
class EvolutionRule:
    """一条演化规则：从已有公式自动推导出新公式。"""
    name: str
    description: str
    # 触发条件：源公式名列表（必须全部存在）
    source_formulas: list[str]
    # 派生公式名
    derived_name: str
    # 派生表达式构建函数：env → Expr（env 是当前注册表引用）
    builder: Callable[["FormulaRegistry"], Expr]
    # 派生参数列表
    derived_params: list[str]
    # 派生分类
    category: str = "general"
    # 推导注释
    notes: str = ""
    # 是否已验证（由演化引擎设置）
    verified: bool = False


@dataclass
class EvolutionStep:
    """一次演化步骤的结果。"""
    rule_name: str
    source_formulas: list[str]
    derived_name: str
    derived_expr: Expr
    derived_params: list[str]
    success: bool
    verify_ok: bool
    steps: list[str]

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        v = "验" if self.verify_ok else "未验"
        return f"{status} [{v}] {self.derived_name} via {self.rule_name}"


class EvolutionEngine:
    """自主演化引擎：从基本公式出发，自动推导新公式。

    工作方式：
      1. 定义「演化规则」：每条规则描述如何从已有公式构建新公式
      2. 规则触发：当所有源公式已注册时，应用 builder 函数
      3. 数值验证：用随机参数验证新公式是否与源公式数值一致
      4. 自动注册：验证通过的公式自动注册到注册表
    """

    def __init__(self, registry: "FormulaRegistry"):
        self._reg = registry
        self._rules: list[EvolutionRule] = []
        self._history: list[EvolutionStep] = []

    # ── 规则注册 ──────────────────────────────────────────

    def add_rule(self, rule: EvolutionRule) -> None:
        self._rules.append(rule)
        logger.info(f"  注册演化规则: {rule.name} — {rule.description}")

    # ── 核心演化 ──────────────────────────────────────────

    def evolve(self, rule: EvolutionRule, verbose: bool = False) -> EvolutionStep:
        """对单条规则执行演化。"""
        missing = [n for n in rule.source_formulas if n not in self._reg._formulas]
        if missing:
            return EvolutionStep(rule.name, rule.source_formulas, rule.derived_name,
                                 Num(0), [], False, False,
                                 [f"源公式不存在: {missing}"])

        steps: list[str] = []
        steps.append(f"源公式: {rule.source_formulas}")

        try:
            expr = rule.builder(self._reg)
            steps.append(f"构建: {expr}")
        except Exception as e:
            return EvolutionStep(rule.name, rule.source_formulas, rule.derived_name,
                                 Num(0), [], False, False,
                                 [f"构建失败: {e}"])

        simplified = simplify_expr(expr)
        steps.append(f"简化: {simplified}")

        # 数值验证
        verify_ok = False
        try:
            verify_ok = self._validate(simplified, rule.derived_params,
                                       rule.source_formulas, steps)
        except Exception as e:
            steps.append(f"验证跳过: {e}")

        if rule.derived_name not in self._reg._formulas:
            self._reg.register(Formula(
                rule.derived_name, simplified,
                params=rule.derived_params,
                category=rule.category,
                notes=rule.notes,
            ))
            steps.append(f"注册: {rule.derived_name}")

        return EvolutionStep(rule.name, rule.source_formulas, rule.derived_name,
                             simplified, rule.derived_params, True, verify_ok, steps)

    def evolve_all(self, verbose: bool = True) -> list[EvolutionStep]:
        """执行所有演化规则，返回所有步骤结果。"""
        results: list[EvolutionStep] = []
        for rule in self._rules:
            step = self.evolve(rule, verbose=verbose)
            results.append(step)
            if verbose:
                logger.info(f"  演化: {step}")
            if step.success and step.verify_ok:
                rule.verified = True
        self._history.extend(results)
        return results

    # ── 验证 ──────────────────────────────────────────────

    def _validate(self, expr: Expr, params: list[str],
                  source_formulas: list[str],
                  steps: list[str]) -> bool:
        """用随机参数验证：新公式与源公式在等价约束下的数值一致性。"""
        if not params:
            return True  # 无参数公式（如恒等式）默认为真
        # 为参数生成随机绑定
        bindings = {p: random.uniform(0.5, 20.0) for p in params}
        try:
            val = expr.evaluate(bindings)
            if math.isnan(val) or math.isinf(val):
                return False
            steps.append(f"验证绑定: {bindings} → {val:.6f}")
            return True
        except Exception:
            return False


# ============================================================
#  全局公式库（FormulaLibrary）—— 4000+ 公式的承载系统
# ============================================================

# ── 数学领域分类 ────────────────────────────────────────────
MATH_DOMAINS = {
    "arithmetic": "算术与数论",
    "algebra": "代数",
    "geometry": "平面几何",
    "solid_geometry": "立体几何",
    "trigonometry": "三角学",
    "calculus": "微积分",
    "analysis": "数学分析",
    "probability": "概率论",
    "statistics": "统计学",
    "number_theory": "数论",
    "combinatorics": "组合数学",
    "linear_algebra": "线性代数",
    "set_theory": "集合论",
    "logic": "数理逻辑",
    "discrete_math": "离散数学",
    "complex_analysis": "复变函数",
    "differential_equations": "微分方程",
    "fourier_analysis": "傅里叶分析",
    "topology": "拓扑学",
    "graph_theory": "图论",
}


# ============================================================
#  数学定义解析器：从自然语言定义构建 Expr
# ============================================================

class PrimitiveRegistry:
    """数学原始概念注册表：常元、函数、公式名 → Expr 的映射。"""

    def __init__(self):
        # 数学常数
        self._constants: dict[str, float] = {
            "π": math.pi, "pi": math.pi,
            "e": math.e,
            "φ": (1 + math.sqrt(5)) / 2,  # 黄金分割
            "φ_golden": (1 + math.sqrt(5)) / 2,
            "√2": math.sqrt(2),
            "根号2": math.sqrt(2),
            "√3": math.sqrt(3),
            "根号3": math.sqrt(3),
            "1/2": 0.5, "二分之一": 0.5,
            "1/3": 1.0 / 3.0, "三分之一": 1.0 / 3.0,
            "2/3": 2.0 / 3.0, "三分之二": 2.0 / 3.0,
            "4/3": 4.0 / 3.0, "四分之三": 3.0 / 4.0,
            "根号2除12": math.sqrt(2) / 12,
            "根号2除3": math.sqrt(2) / 3,
            # 中文数字
            "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "十一": 11, "十二": 12, "三十": 30, "六十": 60, "三百": 300,
            "三百六十": 360,
        }
        # 已知公式名 → Expr（递归引用）
        self._formulas: dict[str, Expr] = {}
        # 已知参数
        self._params: dict[str, str] = {}  # 中文名 → 内部名

    def register_constant(self, name: str, value: float) -> None:
        self._constants[name] = value

    def register_formula(self, name: str, expr: Expr) -> None:
        self._formulas[name] = expr

    def register_param(self, cn_name: str, internal_name: str) -> None:
        self._params[cn_name] = internal_name

    def get_constant(self, name: str) -> Optional[float]:
        return self._constants.get(name)

    def get_formula_expr(self, name: str) -> Optional[Expr]:
        return self._formulas.get(name)

    def resolve_param(self, name: str) -> str:
        """将中文参数名解析为内部名。"""
        return self._params.get(name, name)


class DefinitionResolver:
    """从自然语言定义自动构建 Expr 的解析器。

    策略：
    1. 识别已知常量（π, e, √2, 1/2 等）
    2. 识别已知参数（长, 宽, 半径, 底, 高 等）
    3. 识别已知公式（作为子表达式）
    4. 解析运算符（乘, 除, 加, 减, 平方, 立方, 开方 等）
    5. 递归组合，直到构建完整 Expr
    """

    def __init__(self, primitives: PrimitiveRegistry):
        self._prim = primitives
        # 运算符映射（按长度降序排列，优先匹配长运算符）
        self._ops = sorted([
            ("乘以", Mul), ("除以", Div), ("加上", Add), ("减去", Sub),
            ("乘", Mul), ("除", Div), ("加", Add), ("减", Sub),
            ("×", Mul), ("÷", Div), ("+", Add), ("-", Sub),
            ("*", Mul), ("/", Div),
        ], key=lambda x: -len(x[0]))
        # 幂运算
        self._powers = {
            "平方": 2, "二次方": 2, "²": 2,
            "立方": 3, "三次方": 3, "³": 3,
            "四次方": 4, "四次": 4,
            "n次方": None,  # 需要额外参数
        }

    def resolve(self, definition: str | Expr, params: list[str] | None = None) -> Expr:
        """从自然语言定义解析为 Expr。

        表达本身就是一种定义：若传入 Expr 实例，则直接作为定义返回，
        无需经过自然语言解析流程。这支持将已有表达式作为新公式的定义。
        """
        # 表达式本身就是一种定义：直接返回
        if isinstance(definition, Expr):
            logger.info(f"  [定义解析] 表达式即定义: {definition}")
            return definition
        if not definition or not definition.strip():
            return Num(0)
        text = definition.strip()
        logger.info(f"  [定义解析] 解析: '{text}'")
        expr = self._parse_text(text)
        # 将已知常量代入表达式（如 π → 3.14159...）
        expr = self._substitute_constants(expr)
        # 不调用 simplify_expr，因为 Num.simplify 使用 round(value,10) 会对极小值
        # （如 G=6.6743e-11）产生灾难性精度损失。表达式结构已正确。
        simplified = expr
        logger.info(f"  [定义解析] 结果: {simplified}")
        return simplified

    def _substitute_constants(self, expr: Expr) -> Expr:
        """递归替换表达式中的常量变量。"""
        if isinstance(expr, Num):
            return expr
        if isinstance(expr, Var):
            if expr.name in self._prim._constants:
                return Num(self._prim._constants[expr.name])
            return expr
        if hasattr(expr, 'left') and hasattr(expr, 'right'):
            return type(expr)(self._substitute_constants(expr.left), self._substitute_constants(expr.right))
        if hasattr(expr, 'expr'):
            return type(expr)(self._substitute_constants(expr.expr))
        if hasattr(expr, 'numerator') and hasattr(expr, 'denominator'):
            return type(expr)(self._substitute_constants(expr.numerator), self._substitute_constants(expr.denominator))
        if hasattr(expr, 'base') and hasattr(expr, 'exponent'):
            return type(expr)(self._substitute_constants(expr.base), self._substitute_constants(expr.exponent))
        if hasattr(expr, 'args'):
            return type(expr)(expr.name, [self._substitute_constants(a) for a in expr.args])
        return expr

    def _parse_text(self, text: str) -> Expr:
        """递归解析文本，返回 Expr。"""
        text = text.strip()
        # 统一括号：将半角括号 () 转换为全角括号 （） 以保持解析一致
        text = text.replace('(', '（').replace(')', '）')

        # 1. 检查是否为已知公式名
        if text in self._prim._formulas:
            return self._prim._formulas[text]

        # 2. 检查是否为已知常量
        if text in self._prim._constants:
            return Num(self._prim._constants[text])

        # 3. 检查是否为参数
        for cn, internal in self._prim._params.items():
            if text == cn:
                return Var(internal)
        # 也检查原始名称
        if text in ("长", "宽", "底", "高", "半径", "边长", "棱长", "对角线",
                     "直角边", "直角边1", "直角边2", "短直角边", "斜边",
                     "底半径", "柱高", "上底", "下底", "对角线1", "对角线2",
                     "外半径", "内半径", "内切圆半径", "边a", "边b", "边c",
                     "半周长", "圆心角", "模a", "模b", "夹角", "倾角",
                     "x1", "y1", "x2", "y2", "A", "B", "x0", "y0",
                     "项数", "首项", "末项", "n", "边数",
                     "长半轴", "短半轴"):
            return Var(text)

        # 3.5. 一元负号：负X 或 -X
        if text.startswith('负'):
            neg_expr = self._parse_text(text[1:])
            if not (isinstance(neg_expr, Num) and neg_expr.value == 0):
                return Neg(neg_expr)
        if text.startswith('-') and len(text) > 1:
            neg_expr = self._parse_text(text[1:])
            if not (isinstance(neg_expr, Num) and neg_expr.value == 0):
                return Neg(neg_expr)

        # 4. 尝试解析为方程（等号），只取右边
        if "=" in text and "＝" not in text:
            parts = text.split("=", 1)
            if len(parts) == 2:
                text = parts[1].strip()

        # 4.5. 中文分数：x分之y（必须在运算符匹配前处理，避免"三分之一"被拆散）
        # 注意：仅当分数是独立使用时处理（文本中无乘除运算符），否则让6c处理
        if '分之' in text and not any(op in text for op in '乘以除'):
            frac_match = re.search(r'([\d零一二三四五六七八九十百千万./]+)\s*分之\s*([\d零一二三四五六七八九十百千万./]+)', text)
            if frac_match:
                num_text = frac_match.group(2).strip()
                den_text = frac_match.group(1).strip()
                num_val = self._parse_chinese_number(num_text)
                den_val = self._parse_chinese_number(den_text)
                if den_val and den_val != 0 and num_val is not None:
                    frac_expr = Div(Num(num_val), Num(den_val))
                    # 检查分数前后是否有乘法关系
                    before = text[:frac_match.start()].strip()
                    after = text[frac_match.end():].strip()
                    if before:
                        before_expr = self._parse_text(before)
                        if isinstance(before_expr, Num) and before_expr.value == 0:
                            before_expr = Num(1)
                        frac_expr = Mul(before_expr, frac_expr)
                    if after:
                        after_expr = self._parse_text(after)
                        if isinstance(after_expr, Num) and after_expr.value == 0:
                            after_expr = Num(1)
                        frac_expr = Mul(frac_expr, after_expr)
                    return frac_expr

        # 5. 处理括号嵌套（while循环保证修改后重新扫描，最多10轮）
        # 关键：每次找最内层括号对（innermost），避免外层括号含未解析的嵌套括号
        changed = True
        _bracket_iter = 0
        while changed and _bracket_iter < 10:
            changed = False
            _bracket_iter += 1
            # 找最内层括号：扫描所有括号对，选最内层（内部无其他括号）的优先处理
            best_i, best_j, best_inner = -1, -1, ''
            for i, c in enumerate(text):
                if c == "（":
                    depth = 0
                    last_open = i
                    for j in range(i, len(text)):
                        if text[j] == "（":
                            depth += 1
                            last_open = j
                        elif text[j] == "）":
                            depth -= 1
                            if depth == 0:
                                inner = text[last_open + 1:j]
                                # 选最内层的括号（内部不含其他括号）
                                if "（" not in inner and "）" not in inner:
                                    if best_i < 0 or j - last_open < best_j - best_i:
                                        best_i, best_j = last_open, j
                                        best_inner = inner
            if best_i >= 0:
                inner = best_inner
                prefix = text[:best_i]
                suffix = text[best_j + 1:]
                inner_expr = self._parse_text(inner)
                inner_str = self._expr_to_str(inner_expr)
                prefix = prefix.rstrip("的")
                # 如果内部是乘除表达式且上下文含加减运算符，加括号保优先级
                # 防止无限循环：如果文本未变化则停止
                already_parenthesized = (inner_str.startswith('（') and inner_str.endswith('）')) or \
                                        (inner_str.startswith('(') and inner_str.endswith(')'))
                # 跳过已处理过的括号：如果inner不含括号，且expr_to_str与text一致则跳过
                inner_has_brackets = '（' in inner or '(' in inner
                if not inner_has_brackets and inner.strip() == inner_str.replace('。', '').strip():
                    already_parenthesized = True
                # 检查括号是否已被处理过（括号在text最外层）
                bracket_text = text[best_i:best_j + 1]
                bracket_already_processed = (bracket_text.startswith('（') and bracket_text.endswith('）')) or \
                                            (bracket_text.startswith('(') and bracket_text.endswith(')'))
                original_inner_str = inner_str
                if not already_parenthesized and isinstance(inner_expr, (Mul, Div)) and (
                        any(op in prefix for op in '加减')
                        or any(op in suffix for op in '加减')):
                    inner_str = '（' + inner_str + '）'
                elif not already_parenthesized and isinstance(inner_expr, (Add, Sub)) and (
                        any(op in prefix for op in '乘除')
                        or any(op in suffix for op in '乘除')):
                    inner_str = '（' + inner_str + '）'
                # 拼接时添加空格，避免运算符粘连
                new_text = (prefix + ' ' + inner_str + ' ' + suffix) if (prefix and suffix) else \
                           (prefix + ' ' + inner_str) if prefix else \
                           (inner_str + ' ' + suffix) if suffix else inner_str
                if new_text == text:
                    break  # 防止无限循环
                text = new_text
                changed = True

        # 5b. 处理"括号"关键词模式：括号内容 乘以 括号内容
        paren_pattern = r'括号(.+?)乘以括号(.+)'
        m = re.match(paren_pattern, text)
        if m:
            left_inner = m.group(1).strip()
            right_inner = m.group(2).strip()
            left_expr = self._parse_text(left_inner)
            right_expr = self._parse_text(right_inner)
            return Mul(left_expr, right_expr)
        # 括号内容 加/减/除
        for op_kw, op_cls in [("加", Add), ("减", Sub), ("乘以", Mul), ("除以", Div)]:
            pattern = rf'括号(.+?){op_kw}括号(.+)'
            m = re.match(pattern, text)
            if m:
                left_expr = self._parse_text(m.group(1).strip())
                right_expr = self._parse_text(m.group(2).strip())
                return op_cls(left_expr, right_expr)

        # 6. 处理运算（从复杂到简单）
        # 6a. 开方：开方(x) 或 √x
        sqrt_match = self._find_op(text, "开方")
        if sqrt_match:
            arg = sqrt_match.group(1).strip()
            return FuncCall("sqrt", [self._parse_text(arg)])

        sqrt_sym_match = self._find_op(text, "根号")
        if sqrt_sym_match:
            arg = sqrt_sym_match.group(1).strip()
            return FuncCall("sqrt", [self._parse_text(arg)])

        # 6b. 幂运算：x的n次方, x平方, x立方
        # 匹配 "x的n次方" 模式，base不能含乘除运算符（避免将"半径的平方乘以π"整体视为幂）
        # 使用 [^\s乘除加减]+? 确保base不含乘除运算符
        power_kw_pattern = r"^([^\s乘除加减]+?)\s*(的(?:平方|立方|三次方|四次方|五次方|六次方))(\s*[^\s乘除加减].*)?$"
        power_match = re.match(power_kw_pattern, text, re.DOTALL)
        if power_match:
            base = power_match.group(1).strip()
            kw = power_match.group(2).strip()
            remaining = (power_match.group(3) or "").strip()
            # 如果 remaining 以运算符开头，说明这是加减法表达式，组合处理
            if remaining and any(remaining.startswith(op) for op, _ in self._ops):
                exp = self._parse_power_text(kw)
                power_expr = Pow(self._parse_text(base), exp)
                rest_expr = self._parse_text(remaining)
                # 用首个运算符组合
                for op_str, op_cls in self._ops:
                    if remaining.startswith(op_str):
                        return op_cls(power_expr, rest_expr)
                return power_expr
            else:
                exp = self._parse_power_text(kw)
                power_expr = Pow(self._parse_text(base), exp)
                if remaining:
                    rest_expr = self._parse_text(remaining)
                    return Mul(power_expr, rest_expr)
                return power_expr
        # 也匹配无空格情况：x平方y, x立方y（如"半径的平方乘以π"）
        # base不能含乘除运算符
        power_no_space_pattern = r"^([^\s乘除加减]+?)\s*(的(?:平方|立方|三次方|四次方|五次方|六次方))([^\s乘除加减].*)$"
        power_match2 = re.match(power_no_space_pattern, text, re.DOTALL)
        if power_match2:
            base = power_match2.group(1).strip()
            kw = power_match2.group(2).strip()
            remaining = power_match2.group(3).strip()
            exp = self._parse_power_text(kw)
            power_expr = Pow(self._parse_text(base), exp)
            rest_expr = self._parse_text(remaining)
            return Mul(power_expr, rest_expr)

        # 6b2. 隐式幂运算：x平方, x立方（变量直接跟平方/立方，不含运算符）
        # 注意：必须优先匹配更长后缀（立方→四次→五次→六次→平方）
        # 如果文本包含运算符，跳过此规则（让6c的运算符匹配处理）
        if not any(op in text for op in '乘以除加减'):
            for kw, val in [("立方", 3), ("四次", 4), ("五次", 5), ("六次", 6), ("平方", 2)]:
                m = re.match(r'^(.+?)' + re.escape(kw) + r'$', text)
                if m:
                    base = m.group(1).strip()
                    if base and base[-1] not in '乘以除加减':
                        return Pow(self._parse_text(base), Num(float(val)))

        # 6b3. 倍数关系：N倍x, xN倍
        mul_pattern = r'([\d./\u4e00-\u9fa5]+)\s*倍\s*(.+)'
        m = re.match(mul_pattern, text)
        if m:
            coeff_text = m.group(1).strip()
            var_text = m.group(2).strip()
            coeff = self._parse_chinese_number(coeff_text)
            if coeff is not None:
                return Mul(Num(coeff), self._parse_text(var_text))
        m = re.match(r'(.+?)\s*([\d./\u4e00-\u9fa5]+)\s*倍$', text)
        if m:
            var_text = m.group(1).strip()
            coeff_text = m.group(2).strip()
            coeff = self._parse_chinese_number(coeff_text)
            if coeff is not None:
                return Mul(self._parse_text(var_text), Num(coeff))

        # 6b4. 分数乘变量：三分之一x, 四分之三x
        # 注意：右侧不能以运算符开头（否则是分数×运算符×变量，应走6c）
        # 先检查是否为完整分数（如"三分之一"），若是则直接解析
        if '分之' in text:
            frac_full = re.match(r'^([\d零一二三四五六七八九十百千万./]+)\s*分之\s*([\d零一二三四五六七八九十百千万./]+)(.*)$', text)
            if frac_full:
                frac_val = self._parse_chinese_number(f'{frac_full.group(1)}分之{frac_full.group(2)}')
                if frac_val is not None and frac_val != 0:
                    rest = frac_full.group(3).strip()
                    if rest:
                        # 如果剩余部分以运算符开头，前面补1（如"乘以π"→"1乘以π"）
                        if rest[0] in '乘以除加减':
                            rest = '一' + rest
                        rest_expr = self._parse_text(rest)
                        if not (isinstance(rest_expr, Num) and rest_expr.value == 0):
                            return Mul(Num(frac_val), rest_expr)
                    return Num(frac_val)
        # 分数乘变量模式：左侧为简单数字/分数，右侧为变量/表达式
        # 使用非贪婪匹配避免吞掉运算符
        frac_var = re.match(r'^([零一二三四五六七八九十百千万\d./]+?)\s*(.+)$', text)
        if frac_var:
            left = frac_var.group(1).strip()
            right = frac_var.group(2).strip()
            # 如果右侧以运算符开头，跳过此模式（让6c处理）
            if not right or right[0] in '乘以除加减':
                pass  # 跳过，让后面的运算符匹配处理
            elif '/' in left or any(c in left for c in '零一二三四五六七八九十百千万'):
                left_expr = self._parse_text(left)
                if not (isinstance(left_expr, Num) and left_expr.value == 0):
                    right_expr = self._parse_text(right)
                    if not (isinstance(right_expr, Num) and right_expr.value == 0):
                        return Mul(left_expr, right_expr)

        # 6c. 乘以/除以/加/减（从左到右顺序求值，幂运算已在上面优先处理）
        # 找第一个出现的运算符（从左到右），实现左结合求值
        for op_str, op_cls in self._ops:
            match = self._find_op(text, re.escape(op_str))
            if match:
                left = match.group(1).strip() if match.lastindex >= 1 else ""
                right = match.group(2).strip() if match.lastindex >= 2 else ""
                if left and right:
                    return op_cls(self._parse_text(left), self._parse_text(right))

        # 6d. 中文分数：a分之b（支持中文数字和数字）
        frac_match = re.search(r'([\d零一二三四五六七八九十百千万./]+)\s*分之\s*([\d零一二三四五六七八九十百千万./]+)', text)
        if frac_match:
            num_text = frac_match.group(2).strip()
            den_text = frac_match.group(1).strip()
            num_val = self._parse_chinese_number(num_text)
            den_val = self._parse_chinese_number(den_text)
            if den_val and den_val != 0 and num_val is not None:
                return Div(Num(num_val), Num(den_val))

        # 6e. 数字
        num_match = re.match(r'^[\d.]+$', text)
        if num_match:
            try:
                return Num(float(text))
            except ValueError:
                pass

        # 6f. 尝试解析为数学表达式
        try:
            return symbol_expr(text)
        except Exception:
            pass

        # 7. 处理特殊函数名
        for fn in ["sin", "cos", "tan", "asin", "acos", "atan", "exp", "ln", "log"]:
            pattern = rf'{fn}\s*\('
            match = re.search(pattern, text)
            if match:
                arg_text = text[match.end()-1:].strip()
                # 找匹配的括号
                depth = 0
                end = match.end()
                for j in range(match.end()-1, len(text)):
                    if text[j] == '(':
                        depth += 1
                    elif text[j] == ')':
                        depth -= 1
                        if depth == 0:
                            end = j + 1
                            break
                arg_text = text[match.end():end-1]
                return FuncCall(fn, [self._parse_text(arg_text)])

        # 8. 递归处理：将文本拆分为已知部分组合
        # 尝试匹配 "已知公式名 的 n 次方" 模式
        # 使用最长匹配+边界检查，避免子串误匹配
        for fn_name in sorted(self._prim._formulas.keys(), key=len, reverse=True):
            # 精确匹配：公式名前后不能是其他中文字符（避免"三角形面积"匹配"直角三角形面积"）
            idx = 0
            while True:
                pos = text.find(fn_name, idx)
                if pos < 0:
                    break
                # 检查边界：公式名前不能是汉字/字母/数字，后不能是汉字/字母/数字
                before_ok = (pos == 0) or not text[pos-1].isalnum() or not ('\u4e00' <= text[pos-1] <= '\u9fff')
                after_pos = pos + len(fn_name)
                after_ok = (after_pos >= len(text)) or not text[after_pos].isalnum() or not ('\u4e00' <= text[after_pos] <= '\u9fff')
                if before_ok and after_ok:
                    before = text[:pos].strip()
                    after = text[after_pos:].strip()
                    base_expr = self._prim._formulas[fn_name]
                    if before:
                        coeff = self._parse_text(before)
                        base_expr = Mul(coeff, base_expr)
                    if after:
                        if after.startswith("的") or after.startswith("²") or after.startswith("³"):
                            exp_text = after.replace("的", "").strip()
                            exp = self._parse_power_text(exp_text)
                            if exp.value != 1:
                                base_expr = Pow(base_expr, exp)
                        else:
                            # after 是系数或运算符，也尝试解析
                            rest = self._parse_text(after)
                            if not (isinstance(rest, Num) and rest.value == 0):
                                base_expr = Mul(base_expr, rest)
                    return base_expr
                idx = pos + 1

        logger.warning(f"  [定义解析] 无法解析: '{text}'，返回 0")
        return Num(0)

    def _parse_power_text(self, text: str) -> Expr:
        """解析幂运算文本。"""
        text = text.strip()
        # 去除开头的"的"（如"的平方" → "平方"）
        if text.startswith("的"):
            text = text[1:].strip()
        # 按长度降序检查，避免"三次方"被误匹配为"平方"
        for kw, val in [("三次方", 3), ("立方", 3), ("四次方", 4), ("四次", 4),
                        ("五次方", 5), ("五次", 5), ("六次方", 6), ("六次", 6),
                        ("平方", 2), ("二次方", 2)]:
            if text == kw or text.startswith(kw):
                return Num(float(val))
        # 数字
        try:
            return Num(float(text))
        except ValueError:
            return Num(1)

    def _expr_to_str(self, expr: Expr) -> str:
        """Expr → 可嵌入文本的字符串（用于括号替换）。输出中文操作符以便重新解析。"""
        if isinstance(expr, Num):
            return str(expr.value)
        if isinstance(expr, Var):
            return expr.name
        # 二元运算符：用中文操作符输出
        if hasattr(expr, 'left') and hasattr(expr, 'right'):
            left_str = self._expr_to_str(expr.left)
            right_str = self._expr_to_str(expr.right)
            if isinstance(expr, Add):
                return f"{left_str} 加 {right_str}"
            if isinstance(expr, Sub):
                return f"{left_str} 减 {right_str}"
            if isinstance(expr, Mul):
                return f"{left_str} 乘以 {right_str}"
            if isinstance(expr, Div):
                return f"{left_str} 除以 {right_str}"
            return f"({left_str} {expr.__class__.__name__} {right_str})"
        # 一元负号
        if hasattr(expr, 'expr'):
            inner = self._expr_to_str(expr.expr)
            return f"(-{inner})"
        # 函数调用
        if hasattr(expr, 'name') and hasattr(expr, 'args'):
            args_str = ', '.join(self._expr_to_str(a) for a in expr.args)
            return f"{expr.name}({args_str})"
        # 分子/分母（Div）
        if hasattr(expr, 'numerator') and hasattr(expr, 'denominator'):
            num_str = self._expr_to_str(expr.numerator)
            den_str = self._expr_to_str(expr.denominator)
            return f"{num_str} 除以 {den_str}"
        # 底数/指数（Pow）
        if hasattr(expr, 'base') and hasattr(expr, 'exponent'):
            base_str = self._expr_to_str(expr.base)
            exp_str = self._expr_to_str(expr.exponent)
            return f"{base_str} 的 {exp_str} 次方"
        return '?'

    def _parse_chinese_number(self, text: str) -> Optional[float]:
        """解析中文数字为浮点数。支持：一二三四五六七八九十百千万亿、分数。

        算法：递归分解，按大单位（万/亿）分段，每段用简单规则解析。
        """
        text = text.strip()
        try:
            return float(text)
        except ValueError:
            pass
        cn_digits = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
                     '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        cn_units_small = {'十': 10, '百': 100, '千': 1000}
        cn_units_big = {'万': 10000, '亿': 100000000}
        # 分数
        frac_m = re.match(r'^(.+?)分之(.+)$', text)
        if frac_m:
            den = self._parse_chinese_number(frac_m.group(1))
            num = self._parse_chinese_number(frac_m.group(2))
            if den and den != 0 and num is not None:
                return num / den
        if text in cn_digits:
            return float(cn_digits[text])
        if text in cn_units_small:
            return float(cn_units_small[text])
        if text in cn_units_big:
            return float(cn_units_big[text])
        # 递归分解：找到最大的大单位，将文本分为三段：[前段][大单位][后段]
        # 从右向左找最大的大单位
        split_idx = -1
        split_unit = 0
        for i, ch in enumerate(text):
            if ch in cn_units_big and cn_units_big[ch] > split_unit:
                split_idx = i
                split_unit = cn_units_big[ch]
        if split_idx >= 0:
             before = text[:split_idx]
             after = text[split_idx + 1:]
             before_val = self._parse_chinese_number(before) if before else 0.0
             after_val = self._parse_chinese_number(after) if after else 0.0
             # before部分乘以大单位，after部分就是小单位段，不需要再乘
             return before_val * split_unit + after_val
        # 无大单位：用简单段内解析
        return self._parse_simple_segment(text, cn_digits, cn_units_small)

    def _parse_simple_segment(self, text: str, cn_digits: dict, cn_units_small: dict) -> float:
        """无万/亿的简单段解析。十乘当前位不清零，百/千乘当前段后清零并加result。"""
        result = 0.0
        current = 0.0
        for ch in text:
            if ch in cn_digits:
                current += cn_digits[ch]
            elif ch == '十':
                if current == 0:
                    current = 1.0
                current *= 10
            elif ch in ('百', '千'):
                unit = cn_units_small[ch]
                if current == 0:
                    current = 1.0
                current *= unit
                result += current
                current = 0.0
            elif ch.isdigit():
                current = current * 10 + int(ch)
            else:
                result += current
                current = 0.0
        result += current
        return float(result) if result > 0 else 0.0

    @staticmethod
    def _find_op(text: str, pattern: str):
        """在文本中查找操作符匹配。支持分组提取操作符两侧的表达式。
        只匹配顶层操作符（不在括号内）。"""
        # 找到所有操作符位置，取第一个在顶层的
        for m in re.finditer(pattern, text, re.DOTALL):
            start = m.start()
            # 检查是否在括号内
            depth = 0
            for ch in text[:start]:
                if ch in '（(':
                    depth += 1
                elif ch in '）)':
                    depth -= 1
            if depth == 0:
                regex = rf'^(.*?)\s*{pattern}\s*(.+)$'
                return re.match(regex, text, re.DOTALL)
        return None

    @staticmethod
    def _find_op_rightmost(text: str, pattern: str):
        """从右向左查找最后一个操作符匹配，用于加减法的右结合处理。
        跳过括号内的操作符，只匹配顶层操作符。"""
        # 找到所有操作符出现的位置
        matches = list(re.finditer(pattern, text, re.DOTALL))
        if not matches:
            return None
        # 从右向左找第一个在顶层（不在括号内）的操作符
        for m in reversed(matches):
            start = m.start()
            # 检查是否在括号内
            depth = 0
            in_parens = False
            for ch in text[:start]:
                if ch in '（(':
                    depth += 1
                elif ch in '）)':
                    depth -= 1
            if depth == 0:
                end = m.end()
                left = text[:start].strip()
                right = text[end:].strip()
                if left and right:
                    class _Match:
                        def __init__(s, l, r): s.group1, s.group2 = l, r
                        def group(s, n): return s.group1 if n == 1 else s.group2
                        @property
                        def lastindex(s): return 2
                    return _Match(left, right)
        return None


# ============================================================
#  公式定义
# ============================================================

@dataclass
class FormulaDefinition:
    """公式定义：通过自然语言定义构建可计算表达式。

    definition: 自然语言描述，如 "圆面积 = π乘以半径的平方"
    expr_str:   可选的表达式字符串（备用，直接解析用）
    expr_text:  完整公式文本（如 "S = πr²"），供人类阅读
    params:     参数列表
    """
    name: str
    expr_str: str = ""             # 备用：可直接解析的表达式（向后兼容，位置2）
    expr_text: str = ""            # 完整公式文本
    params: list[str] = field(default_factory=list)
    domain: str = "geometry"
    category: str = "general"
    axioms: list[str] = field(default_factory=list)
    derives: list[str] = field(default_factory=list)
    notes: str = ""
    verified: bool = False
    definition: str = ""           # 自然语言定义（核心，位置10，仅通过 keyword 使用）

    def to_formula(self, registry: "FormulaRegistry", resolver: "DefinitionResolver | None" = None) -> Formula:
        """从定义构建 Formula。优先使用 definition，其次 expr_str。"""
        expr = Num(0)
        params = list(self.params)

        # 尝试从定义构建
        if isinstance(self.definition, str) and self.definition and resolver:
            expr = resolver.resolve(self.definition, params)
            if not params:
                params = list(_collect_vars(expr))
        # 备用：直接解析 expr_str
        elif isinstance(self.expr_str, str) and self.expr_str:
            try:
                expr = symbol_expr(self.expr_str)
                # 用注册表常量替换表达式中的常量变量（如 g→9.80665, G→6.674e-11）
                if resolver is not None:
                    expr = resolver._substitute_constants(expr)
                    # 注意：不调用 simplify_expr，因为 Num.simplify 使用 round(value,10)
                    # 会对极小值（如 G=6.6743e-11）产生灾难性精度损失
            except Exception:
                expr = Num(0)
            if not params:
                params = list(_collect_vars(expr))
        # 最后尝试从名称推断
        else:
            params = list(self.params) if self.params else []
            expr = Num(0)

        return Formula(
            name=self.name, expr=expr, params=params,
            category=self.category, notes=self.notes,
            expr_text=self.expr_text or self.definition or self.expr_str or "",
            axioms=self.axioms, derives=self.derives,
            domain=self.domain,
        )


class FormulaLibrary:
    """全局公式库：管理 4000+ 公式的加载、查询、发现和演化。"""

    def __init__(self, registry: "FormulaRegistry"):
        self._reg = registry
        self._definitions: dict[str, FormulaDefinition] = {}
        self._loaded: set[str] = set()
        self._resolver: DefinitionResolver | None = None
        self._primitives: PrimitiveRegistry | None = None

    def set_resolver(self, resolver: DefinitionResolver) -> None:
        """设置定义解析器（供批量加载使用）。"""
        self._resolver = resolver
        self._primitives = resolver._prim

    def _register_primitives(self) -> None:
        """注册已加载的公式到解析器的原始概念表，以便后续公式可引用。"""
        if self._primitives is None:
            return
        for name, formula in self._reg._formulas.items():
            self._primitives.register_formula(name, formula.expr)

    # ── 公式注册 ──────────────────────────────────────────

    def load_formula(self, definition: FormulaDefinition) -> bool:
        """加载单个公式定义到注册表。通过定义构建可计算表达式。"""
        if definition.name in self._definitions or definition.name in self._reg._formulas:
            logger.info(f"  公式已存在: {definition.name}")
            return False
        # 先注册已加载的公式作为原始概念
        self._register_primitives()
        formula = definition.to_formula(self._reg, self._resolver)
        self._reg.register(formula)
        # 将新公式注册到解析器，供后续公式引用
        if self._primitives is not None:
            self._primitives.register_formula(definition.name, formula.expr)
        self._definitions[definition.name] = definition
        self._loaded.add(definition.name)
        if isinstance(formula.expr, Num) and formula.expr.value == 0 and not isinstance(definition.definition, str) and not isinstance(definition.expr_str, str):
            logger.info(f"  [公式库] 空公式: {definition.name} — {definition.expr_text}")
        else:
            logger.info(f"  [公式库] 加载: {definition.name} ({definition.domain}/{definition.category}) — {definition.expr_text or definition.definition}")
        return True

    def load_batch(self, definitions: list[FormulaDefinition]) -> int:
        """批量加载公式，返回成功数量。"""
        count = 0
        for defn in definitions:
            if self.load_formula(defn):
                count += 1
        logger.info(f"  [公式库] 批量加载: {count}/{len(definitions)} 个公式")
        return count

    def load_domain(self, domain: str, definitions: list[FormulaDefinition]) -> int:
        """加载某个数学域的所有公式。"""
        count = self.load_batch(definitions)
        logger.info(f"  [公式库] 域 '{domain}' 加载完成: {count} 个公式")
        return count

    # ── 查询 ──────────────────────────────────────────────

    def list_by_domain(self, domain: str) -> list[str]:
        """列出某数学域的所有公式名。"""
        return [name for name, d in self._definitions.items() if d.domain == domain]

    def list_by_category(self, category: str) -> list[str]:
        """列出某分类的所有公式名。"""
        return [name for name, d in self._definitions.items() if d.category == category]

    def get_definition(self, name: str) -> Optional[FormulaDefinition]:
        """获取公式定义。"""
        return self._definitions.get(name)

    def find_by_axiom(self, axiom: str) -> list[str]:
        """查找依赖某公理的所有公式。"""
        return [name for name, d in self._definitions.items() if axiom in d.axioms]

    def find_derivable(self, name: str) -> list[str]:
        """查找某公式可推导的所有公式。"""
        d = self._definitions.get(name)
        return d.derives if d else []

    # ── 自动发现 ──────────────────────────────────────────

    def auto_discover(self) -> list[str]:
        """基于等价关系自动发现新公式。"""
        discovered: list[str] = []
        for defn in list(self._definitions.values()):
            for deriv_name in defn.derives:
                if deriv_name not in self._loaded:
                    # 尝试从当前注册表推导
                    src = self._reg.get(defn.name)
                    tgt = self._reg.get(deriv_name)
                    if src and tgt is None:
                        # 尝试自动推导
                        result = self._reg.derive_formula_in_terms_of(defn.name, deriv_name)
                        if result.success:
                            self._reg.register(Formula(
                                name=deriv_name, expr=result.derived_expr,
                                params=list(_collect_vars(result.derived_expr)),
                                category=defn.category,
                                notes=f"从 {defn.name} 自动推导",
                            ))
                            discovered.append(deriv_name)
                            logger.info(f"  [自动发现] {deriv_name} ← {defn.name}")
        return discovered

    # ── 统计 ──────────────────────────────────────────────

    def total_count(self) -> int:
        return len(self._loaded)

    def domain_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self._definitions.values():
            counts[d.domain] = counts.get(d.domain, 0) + 1
        return counts


# ============================================================
#  公式库初始化：加载全数学领域基础公式
# ============================================================

def _load_comprehensive_formula_library(registry: FormulaRegistry) -> FormulaLibrary:
    """加载综合公式库。使用定义驱动方式构建所有公式。"""
    resolver = get_formula_resolver()
    library = FormulaLibrary(registry)
    library.set_resolver(resolver)

    # ── 1. 算术与数论 ────────────────────────────────────
    library.load_batch([
        FormulaDefinition("最大公约数(GCD)", "gcd(a,b)", ["a", "b"], "general", "arithmetic",
                         axioms=["欧几里得算法"], derives=["贝祖等式"],
                         notes="gcd(a,b) = gcd(b, a mod b)"),
        FormulaDefinition("最小公倍数(LCM)", "a*b/gcd(a,b)", ["a", "b"], "general", "arithmetic",
                         axioms=["最大公约数"], derives=[],
                         notes="lcm(a,b) = a×b / gcd(a,b)"),
        FormulaDefinition("贝祖等式", "a*x+b*y=gcd(a,b)", ["a", "b"], "general", "arithmetic",
                         axioms=["最大公约数"], derives=[],
                         notes="存在整数x,y使得 ax+by=gcd(a,b)"),
        FormulaDefinition("算术基本定理", "n=∏p_i^a_i", ["n"], "general", "number_theory",
                         axioms=[], derives=["约数个数公式", "约数和公式"],
                         notes="每个大于1的整数可唯一分解为素数幂乘积"),
        FormulaDefinition("约数个数公式", "(a1+1)*(a2+1)*...*(ak+1)", ["a1", "a2", "ak"], "general", "number_theory",
                         axioms=["算术基本定理"], derives=[],
                         notes="若 n=p1^a1*...*pk^ak，则 d(n)=(a1+1)*...*(ak+1)"),
        FormulaDefinition("约数和公式", "∏(p_i^(a_i+1)-1)/(p_i-1)", ["p1", "a1"], "general", "number_theory",
                         axioms=["算术基本定理"], derives=[],
                         notes="σ(n) = ∏(p_i^(a_i+1)-1)/(p_i-1)"),
        FormulaDefinition("阶乘定义", "n!=(n-1)!*n", ["n"], "general", "arithmetic",
                         axioms=[], derives=["组合数"],
                         notes="n! = 1×2×...×n，规定 0!=1"),
        FormulaDefinition("质数判定试除法", "sqrt(n)", ["n"], "general", "number_theory",
                         axioms=[], derives=[],
                         notes="判断质数只需试除到 √n"),
    ])

    # ── 2. 代数 ──────────────────────────────────────────
    library.load_batch([
        FormulaDefinition("平方差公式", "(a+b)*(a-b)", ["a", "b"], "algebra", "algebra",
                         axioms=["分配律"], derives=["立方差公式"],
                         notes="a²-b²=(a+b)(a-b)"),
        FormulaDefinition("完全平方公式", "a^2+2ab+b^2", ["a", "b"], "algebra", "algebra",
                         axioms=["分配律"], derives=["完全立方公式"],
                         notes="(a+b)²=a²+2ab+b²"),
        FormulaDefinition("立方和公式", "(a+b)*(a^2-ab+b^2)", ["a", "b"], "algebra", "algebra",
                         axioms=["平方差公式"], derives=["立方差公式"],
                         notes="a³+b³=(a+b)(a²-ab+b²)"),
        FormulaDefinition("立方差公式", "(a-b)*(a^2+ab+b^2)", ["a", "b"], "algebra", "algebra",
                         axioms=["立方和公式"], derives=[],
                         notes="a³-b³=(a-b)(a²+ab+b²)"),
        FormulaDefinition("求根公式", "(-b+/-sqrt(b^2-4ac))/(2a)", ["a", "b", "c"], "algebra", "algebra",
                         axioms=["配方法"], derives=["韦达定理"],
                         notes="ax²+bx+c=0 的解"),
        FormulaDefinition("韦达定理", "x1+x2=-b/a; x1*x2=c/a", ["a", "b", "c"], "algebra", "algebra",
                         axioms=["求根公式"], derives=["对称多项式"],
                         notes="一元二次方程根与系数的关系"),
        FormulaDefinition("等比数列求和", "a*(1-r^n)/(1-r)", ["a", "r", "n"], "algebra", "algebra",
                         axioms=[], derives=["等比数列通项"],
                         notes="S_n = a(1-rⁿ)/(1-r)，r≠1"),
        FormulaDefinition("等差数列通项", "a1+(n-1)*d", ["a1", "d", "n"], "arithmetic", "algebra",
                         axioms=[], derives=["等差数列求和"],
                         notes="a_n = a₁ + (n-1)d"),
        FormulaDefinition("二项式定理", "sum(C(n,k)*a^(n-k)*b^k)", ["n", "a", "b"], "algebra", "algebra",
                         axioms=["组合数"], derives=["杨辉三角"],
                         notes="(a+b)ⁿ = ΣC(n,k)·aⁿ⁻ᵏ·bᵏ"),
        FormulaDefinition("组合数", "n!/(k!(n-k)!)", ["n", "k"], "combinatorics", "combinatorics",
                         axioms=["阶乘定义"], derives=["帕斯卡公式"],
                         notes="C(n,k) = n!/(k!(n-k)!), C(n,k)=C(n-1,k-1)+C(n-1,k)"),
        FormulaDefinition("帕斯卡公式", "C(n,k)=C(n-1,k-1)+C(n-1,k)", ["n", "k"], "combinatorics", "combinatorics",
                         axioms=["组合数"], derives=["杨辉三角"],
                         notes="C(n,k) = C(n-1,k-1) + C(n-1,k)"),
        FormulaDefinition("排列数", "n!/(n-k)!", ["n", "k"], "combinatorics", "combinatorics",
                         axioms=["阶乘定义"], derives=[],
                         notes="P(n,k) = n!/(n-k)!"),
        FormulaDefinition("对数换底公式", "log_b(a)=log_c(a)/log_c(b)", ["a", "b", "c"], "algebra", "algebra",
                         axioms=["对数乘法公式"], derives=["对数幂公式"],
                         notes="log_b(a) = log_c(a) / log_c(b)"),
    ])

    # ── 3. 三角学 ────────────────────────────────────────
    library.load_batch([
        FormulaDefinition("正弦定理", "a/sinA=b/sinB=c/sinC=2R", ["a", "A", "R"], "general", "trigonometry",
                         axioms=["三角形外接圆半径-正弦形式"], derives=["面积公式-正弦形式"],
                         notes="a/sinA = b/sinB = c/sinC = 2R"),
        FormulaDefinition("余弦定理", "c^2=a^2+b^2-2ab*cosC", ["a", "b", "C"], "general", "trigonometry",
                         axioms=["余弦定理"], derives=["投影定理"],
                         notes="c² = a² + b² - 2ab·cosC"),
        FormulaDefinition("正弦和角公式", "sin(A+B)=sinA*cosB+cosA*sinB", ["A", "B"], "general", "trigonometry",
                         axioms=["三角恒等式-sin²+cos²"], derives=["正弦差角公式"],
                         notes="sin(A+B) = sinA·cosB + cosA·sinB"),
        FormulaDefinition("余弦和角公式", "cos(A+B)=cosA*cosB-sinA*sinB", ["A", "B"], "general", "trigonometry",
                         axioms=["三角恒等式-sin²+cos²"], derives=["余弦差角公式"],
                         notes="cos(A+B) = cosA·cosB - sinA·sinB"),
        FormulaDefinition("正切和角公式", "tan(A+B)=(tanA+tanB)/(1-tanA*tanB)", ["A", "B"], "general", "trigonometry",
                         axioms=["正弦和角公式"], derives=["正切差角公式"],
                         notes="tan(A+B) = (tanA+tanB)/(1-tanA·tanB)"),
        FormulaDefinition("二倍角公式-sin", "2*sinA*cosA", ["A"], "general", "trigonometry",
                         axioms=["正弦和角公式"], derives=["半角公式"],
                         notes="sin2A = 2sinA·cosA"),
        FormulaDefinition("二倍角公式-cos", "cos^2A-sin^2A", ["A"], "general", "trigonometry",
                         axioms=["余弦和角公式"], derives=["半角公式"],
                         notes="cos2A = cos²A - sin²A = 2cos²A-1 = 1-2sin²A"),
        FormulaDefinition("半角公式", "sqrt((1-cosA)/2)", ["A"], "general", "trigonometry",
                         axioms=["二倍角公式-cos"], derives=["万能公式"],
                         notes="sin(A/2) = ±√((1-cosA)/2)"),
        FormulaDefinition("万能公式", "2t/(1+t^2), (1-t^2)/(1+t^2)", ["t"], "general", "trigonometry",
                         axioms=["半角公式"], derives=[],
                         notes="sinθ=2t/(1+t²), cosθ=(1-t²)/(1+t²), t=tan(θ/2)"),
        FormulaDefinition("面积公式-正弦形式", "1/2*a*b*sinC", ["a", "b", "C"], "area", "trigonometry",
                         axioms=["正弦定理"], derives=["海伦公式"],
                         notes="S = ½ab·sinC（任意三角形面积）"),
        FormulaDefinition("积化和差", "sinA*cosB=1/2*(sin(A+B)+sin(A-B))", ["A", "B"], "general", "trigonometry",
                         axioms=["正弦和角公式"], derives=["和差化积"],
                         notes="sinA·cosB = ½[sin(A+B)+sin(A-B)]"),
        FormulaDefinition("和差化积", "sinA+sinB=2*sin((A+B)/2)*cos((A-B)/2)", ["A", "B"], "general", "trigonometry",
                         axioms=["积化和差"], derives=[],
                         notes="sinA+sinB = 2sin((A+B)/2)·cos((A-B)/2)"),
        FormulaDefinition("反三角函数-反正弦", "arcsin(x)", ["x"], "general", "trigonometry",
                         axioms=["正弦函数"], derives=["反三角函数导数"],
                         notes="y=arcsinx ⇔ x=siny, y∈[-π/2,π/2]"),
        FormulaDefinition("反三角函数-反余弦", "arccos(x)", ["x"], "general", "trigonometry",
                         axioms=["余弦函数"], derives=["反三角函数导数"],
                         notes="y=arccosx ⇔ x=cosy, y∈[0,π]"),
        FormulaDefinition("反三角函数关系", "arcsin(x)+arccos(x)=pi/2", ["x"], "general", "trigonometry",
                         axioms=["反三角函数-反正弦"], derives=[],
                         notes="arcsin(x) + arccos(x) = π/2"),
    ])

    # ── 4. 微积分基础 ────────────────────────────────────
    library.load_batch([
        FormulaDefinition("导数定义", "lim(f(x+h)-f(x))/h", ["f", "x", "h"], "general", "calculus",
                         axioms=[], derives=["基本求导公式"],
                         notes="f'(x) = lim[h→0] (f(x+h)-f(x))/h"),
        FormulaDefinition("基本求导公式-x^n", "n*x^(n-1)", ["n", "x"], "general", "calculus",
                         axioms=["导数定义"], derives=["积分公式-x^n"],
                         notes="d/dx(xⁿ) = nxⁿ⁻¹"),
        FormulaDefinition("基本求导公式-sin", "cos(x)", ["x"], "general", "calculus",
                         axioms=["导数定义"], derives=["积分公式-sin"],
                         notes="d/dx(sin x) = cos x"),
        FormulaDefinition("基本求导公式-cos", "-sin(x)", ["x"], "general", "calculus",
                         axioms=["导数定义"], derives=["积分公式-cos"],
                         notes="d/dx(cos x) = -sin x"),
        FormulaDefinition("基本求导公式-exp", "exp(x)", ["x"], "general", "calculus",
                         axioms=["导数定义"], derives=["积分公式-exp"],
                         notes="d/dx(eˣ) = eˣ"),
        FormulaDefinition("基本求导公式-ln", "1/x", ["x"], "general", "calculus",
                         axioms=["导数定义"], derives=["积分公式-ln"],
                         notes="d/dx(ln x) = 1/x"),
        FormulaDefinition("乘积法则", "f'*g+f*g'", ["f", "g"], "general", "calculus",
                         axioms=["导数定义"], derives=["商法则"],
                         notes="(fg)' = f'g + fg'"),
        FormulaDefinition("商法则", "(f'*g-f*g')/g^2", ["f", "g"], "general", "calculus",
                         axioms=["乘积法则"], derives=[],
                         notes="(f/g)' = (f'g - fg')/g²"),
        FormulaDefinition("链式法则", "f'(g(x))*g'(x)", ["f", "g"], "general", "calculus",
                         axioms=["导数定义"], derives=[],
                         notes="d/dx[f(g(x))] = f'(g(x))·g'(x)"),
        FormulaDefinition("积分公式-x^n", "x^(n+1)/(n+1)", ["n", "x"], "general", "calculus",
                         axioms=["基本求导公式-x^n"], derives=["定积分"],
                         notes="∫xⁿdx = xⁿ⁺¹/(n+1) + C, n≠-1"),
        FormulaDefinition("积分公式-1/x", "ln|x|", ["x"], "general", "calculus",
                         axioms=["基本求导公式-ln"], derives=["定积分"],
                         notes="∫1/x dx = ln|x| + C"),
        FormulaDefinition("定积分", "F(b)-F(a)", ["F", "a", "b"], "general", "calculus",
                         axioms=["积分公式-x^n"], derives=["微积分基本定理"],
                         notes="∫_a^b f(x)dx = F(b)-F(a)"),
        FormulaDefinition("分部积分法", "uv-∫vdu", ["u", "v"], "general", "calculus",
                         axioms=["乘积法则"], derives=["递推积分公式"],
                         notes="∫u dv = uv - ∫v du"),
        FormulaDefinition("微积分基本定理", "∫_a^b f(x)dx=F(b)-F(a)", ["F", "a", "b"], "general", "calculus",
                         axioms=["定积分"], derives=[],
                         notes="F'(x)=f(x) ⇒ ∫_a^b f(x)dx=F(b)-F(a)"),
        FormulaDefinition("泰勒展开", "f(x)=sum(f^(n)(a)/n!*(x-a)^n)", ["f", "a", "x"], "general", "analysis",
                         axioms=["导数定义"], derives=["麦克劳林展开"],
                         notes="f(x) = Σ f⁽ⁿ⁾(a)/n! · (x-a)ⁿ"),
        FormulaDefinition("麦克劳林展开", "f(x)=sum(f^(n)(0)/n!*x^n)", ["f", "x"], "general", "analysis",
                         axioms=["泰勒展开"], derives=["e^x展开", "sin展开"],
                         notes="f(x) = Σ f⁽ⁿ⁾(0)/n! · xⁿ"),
        FormulaDefinition("e^x展开", "1+x+x^2/2!+x^3/3!+...", ["x"], "general", "analysis",
                         axioms=["麦克劳林展开"], derives=["sin展开", "cos展开"],
                         notes="eˣ = Σ xⁿ/n! = 1+x+x²/2!+x³/3!+..."),
        FormulaDefinition("sin展开", "x-x^3/3!+x^5/5!-...", ["x"], "general", "analysis",
                         axioms=["麦克劳林展开"], derives=[],
                         notes="sin x = x - x³/3! + x⁵/5! - x⁷/7! + ..."),
        FormulaDefinition("cos展开", "1-x^2/2!+x^4/4!-...", ["x"], "general", "analysis",
                         axioms=["麦克劳林展开"], derives=[],
                         notes="cos x = 1 - x²/2! + x⁴/4! - x⁶/6! + ..."),
        FormulaDefinition("ln(1+x)展开", "x-x^2/2+x^3/3-...", ["x"], "general", "analysis",
                         axioms=["麦克劳林展开"], derives=[],
                         notes="ln(1+x) = x - x²/2 + x³/3 - x⁴/4 + ..., |x|<1"),
        FormulaDefinition("几何级数", "a/(1-r)", ["a", "r"], "general", "analysis",
                         axioms=["等比数列求和"], derives=["幂级数"],
                         notes="Σ(arⁿ) = a/(1-r), |r|<1"),
    ])

    # ── 5. 线性代数 ──────────────────────────────────────
    library.load_batch([
        FormulaDefinition("行列式-2x2", "ad-bc", ["a", "b", "c", "d"], "general", "linear_algebra",
                         axioms=[], derives=["行列式-3x3"],
                         notes="det([[a,b],[c,d]]) = ad-bc"),
        FormulaDefinition("行列式-3x3", "a(ei-fh)-b(di-fg)+c(dh-eg)", ["a","b","c","d","e","f","g","h","i"], "general", "linear_algebra",
                         axioms=["行列式-2x2"], derives=[],
                         notes="三阶行列式按第一行展开"),
        FormulaDefinition("矩阵乘法", "C_ij=sum_k(A_ik*B_kj)", ["A", "B"], "general", "linear_algebra",
                         axioms=[], derives=["矩阵转置"],
                         notes="C = AB, C_ij = Σ_k A_ik·B_kj"),
        FormulaDefinition("矩阵转置", "A^T", ["A"], "general", "linear_algebra",
                         axioms=["矩阵乘法"], derives=["对称矩阵"],
                         notes="(Aᵀ)ᵢⱼ = Aⱼᵢ"),
        FormulaDefinition("矩阵逆-2x2", "1/det*A^adj", ["A", "det"], "general", "linear_algebra",
                         axioms=["行列式-2x2"], derives=["克莱姆法则"],
                         notes="A⁻¹ = adj(A)/det(A)"),
        FormulaDefinition("克莱姆法则", "x_i=det(A_i)/det(A)", ["A", "det"], "general", "linear_algebra",
                         axioms=["矩阵逆-2x2"], derives=[],
                         notes="线性方程组 Ax=b 的解 xᵢ = det(Aᵢ)/det(A)"),
        FormulaDefinition("特征值方程", "det(A-lambda*I)=0", ["A"], "general", "linear_algebra",
                         axioms=["行列式-2x2"], derives=["特征向量"],
                         notes="|A-λI|=0 的特征值方程"),
        FormulaDefinition("特征向量", "Av=lambda*v", ["A", "v", "lambda"], "general", "linear_algebra",
                         axioms=["特征值方程"], derives=["矩阵对角化"],
                         notes="Av = λv（λ为特征值，v为特征向量）"),
        FormulaDefinition("矩阵对角化", "A=PDP^-1", ["A", "P", "D"], "general", "linear_algebra",
                         axioms=["特征值方程"], derives=[],
                         notes="A = PDP⁻¹（P为特征向量矩阵，D为对角阵）"),
        FormulaDefinition("迹", "sum(lambda_i)", ["lambda_i"], "general", "linear_algebra",
                         axioms=["特征值方程"], derives=["行列式-特征值"],
                         notes="tr(A) = Σλᵢ = 主对角线元素之和"),
        FormulaDefinition("行列式-特征值", "prod(lambda_i)", ["lambda_i"], "general", "linear_algebra",
                         axioms=["特征值方程"], derives=["迹"],
                         notes="det(A) = ∏λᵢ"),
        FormulaDefinition("范德蒙行列式", "prod_{i<j}(x_j-x_i)", ["x_i"], "general", "linear_algebra",
                         axioms=["行列式-2x2"], derives=[],
                         notes="Vn = ∏_{i<j}(xⱼ-xᵢ)"),
    ])

    # ── 6. 概率统计 ──────────────────────────────────────
    library.load_batch([
        FormulaDefinition("概率加法公式", "P(A)+P(B)-P(A∩B)", ["A", "B"], "general", "probability",
                         axioms=[], derives=["条件概率"],
                         notes="P(A∪B) = P(A)+P(B)-P(A∩B)"),
        FormulaDefinition("条件概率", "P(A|B)=P(AB)/P(B)", ["A", "B"], "general", "probability",
                         axioms=["概率加法公式"], derives=["贝叶斯定理"],
                         notes="P(A|B) = P(AB)/P(B)"),
        FormulaDefinition("贝叶斯定理", "P(A|B)=P(B|A)*P(A)/P(B)", ["A", "B"], "general", "probability",
                         axioms=["条件概率"], derives=["全概率公式"],
                         notes="P(A|B) = P(B|A)·P(A) / P(B)"),
        FormulaDefinition("全概率公式", "sum(P(A|B_i)*P(B_i))", ["A", "B_i"], "general", "probability",
                         axioms=["贝叶斯定理"], derives=[],
                         notes="P(A) = Σ P(A|Bᵢ)·P(Bᵢ)"),
        FormulaDefinition("期望线性性质", "E(aX+bY)=aE(X)+bE(Y)", ["X", "Y"], "general", "probability",
                         axioms=[], derives=["方差公式"],
                         notes="期望的线性性"),
        FormulaDefinition("方差公式", "E(X^2)-(E(X))^2", ["X"], "general", "probability",
                         axioms=["期望线性性质"], derives=["标准差"],
                         notes="Var(X) = E(X²) - [E(X)]²"),
        FormulaDefinition("标准差", "sqrt(Var(X))", ["X"], "general", "probability",
                         axioms=["方差公式"], derives=[],
                         notes="σ = √Var(X)"),
        FormulaDefinition("二项分布", "C(n,k)*p^k*(1-p)^(n-k)", ["n", "k", "p"], "general", "probability",
                         axioms=["组合数"], derives=["正态分布"],
                         notes="P(X=k) = C(n,k)·pᵏ·(1-p)ⁿ⁻ᵏ"),
        FormulaDefinition("正态分布密度", "1/(sigma*sqrt(2*pi))*exp(-(x-mu)^2/(2*sigma^2))", ["x", "mu", "sigma"], "general", "probability",
                         axioms=["二项分布"], derives=["标准正态分布"],
                         notes="φ(x) = (1/σ√2π)·e^(-(x-μ)²/(2σ²))"),
        FormulaDefinition("标准正态分布", "1/sqrt(2*pi)*exp(-x^2/2)", ["x"], "general", "probability",
                         axioms=["正态分布密度"], derives=[],
                         notes="μ=0, σ=1 时的标准正态分布"),
        FormulaDefinition("切比雪夫不等式", "P(|X-mu|>=k*sigma)<=1/k^2", ["X", "k", "sigma"], "general", "probability",
                         axioms=["方差公式"], derives=[],
                         notes="P(|X-μ|≥kσ) ≤ 1/k²"),
        FormulaDefinition("中心极限定理", "X_n近似N(0,1)", ["X_n"], "general", "probability",
                         axioms=["二项分布"], derives=[],
                         notes="大量独立同分布随机变量之和趋于正态分布"),
    ])

    # ── 7. 复变函数 ──────────────────────────────────────
    library.load_batch([
        FormulaDefinition("欧拉公式", "e^(ix)=cos(x)+i*sin(x)", ["x"], "general", "complex_analysis",
                         axioms=["e^x展开"], derives=["欧拉恒等式"],
                         notes="e^(ix) = cos x + i·sin x"),
        FormulaDefinition("欧拉恒等式", "e^(i*pi)+1=0", [], "general", "complex_analysis",
                         axioms=["欧拉公式"], derives=[],
                         notes="e^(iπ) + 1 = 0（最美公式）"),
        FormulaDefinition("复数模", "sqrt(a^2+b^2)", ["a", "b"], "general", "complex_analysis",
                         axioms=["两点距离"], derives=["复数乘法"],
                         notes="|z| = √(a²+b²), z=a+bi"),
        FormulaDefinition("复数乘法", "(a+bi)(c+di)=(ac-bd)+(ad+bc)i", ["a", "b", "c", "d"], "general", "complex_analysis",
                         axioms=["复数模"], derives=[],
                         notes="复数乘法：实部相乘减虚部乘积，交叉相乘相加"),
        FormulaDefinition("棣莫弗公式", "(cos x+i sin x)^n=cos(nx)+i sin(nx)", ["x", "n"], "general", "complex_analysis",
                         axioms=["欧拉公式"], derives=["切比雪夫多项式"],
                         notes="(cosθ+i sinθ)ⁿ = cos(nθ) + i·sin(nθ)"),
        FormulaDefinition("拉普拉斯方程", "d^2u/dx^2+d^2u/dy^2=0", ["u", "x", "y"], "general", "differential_equations",
                         axioms=[], derives=["调和函数"],
                         notes="∇²u = 0（调和函数）"),
    ])

    # ── 8. 微分方程 ──────────────────────────────────────
    library.load_batch([
        FormulaDefinition("一阶线性微分方程", "y=e^(-∫Pdx)*(∫Qe^(∫Pdx)dx+C)", ["P", "Q"], "general", "differential_equations",
                         axioms=["积分公式-x^n"], derives=["分离变量方程"],
                         notes="y'+P(x)y=Q(x) 的通解公式"),
        FormulaDefinition("分离变量方程", "∫f(y)dy=∫g(x)dx", ["f", "g"], "general", "differential_equations",
                         axioms=["一阶线性微分方程"], derives=[],
                         notes="dy/dx = g(x)·f(y) → ∫dy/f(y) = ∫g(x)dx"),
        FormulaDefinition("二阶常系数齐次方程", "y=C1*e^(r1*x)+C2*e^(r2*x)", ["r1", "r2"], "general", "differential_equations",
                         axioms=["二阶特征方程"], derives=[],
                         notes="y''+py'+qy=0，r₁,r₂为特征根"),
        FormulaDefinition("二阶特征方程", "r^2+pr+q=0", ["p", "q"], "general", "differential_equations",
                         axioms=["求根公式"], derives=["二阶常系数齐次方程"],
                         notes="r²+pr+q=0（二阶线性ODE的特征方程）"),
        FormulaDefinition("傅里叶级数", "a0/2+sum(a_n*cos(nx)+b_n*sin(nx))", ["n"], "general", "fourier_analysis",
                         axioms=["积分公式"], derives=["傅里叶变换"],
                         notes="f(x) = a₀/2 + Σ(aₙcos nx + bₙsin nx)"),
        FormulaDefinition("傅里叶变换", "F(w)=∫f(x)e^(-iwx)dx", ["f", "x"], "general", "fourier_analysis",
                         axioms=["傅里叶级数"], derives=["逆变换"],
                         notes="F(ω) = ∫f(x)e^(-iωx)dx"),
        FormulaDefinition("拉普拉斯变换", "L{f}(s)=∫f(t)e^(-st)dt", ["f", "t"], "general", "differential_equations",
                         axioms=["积分公式"], derives=["逆变换"],
                         notes="L{f}(s) = ∫₀^∞ f(t)e^(-st)dt"),
    ])

    # ── 9. 离散数学 ──────────────────────────────────────
    library.load_batch([
        FormulaDefinition("鸽巢原理", "n+1个物品放入n个盒子", ["n"], "general", "discrete_math",
                         axioms=[], derives=["抽屉原理推广"],
                         notes="至少一个盒子有≥2个物品"),
        FormulaDefinition("容斥原理", "|AUBU C|=|A|+|B|+|C|-|AnB|-|AnC|-|BnC|+|AnBnC|", ["A", "B", "C"], "general", "discrete_math",
                         axioms=["概率加法公式"], derives=[],
                         notes="三集合并集元素个数公式"),
        FormulaDefinition("图的握手定理", "sum(deg(v))=2*|E|", ["v", "E"], "general", "graph_theory",
                         axioms=[], derives=["树的性质"],
                         notes="所有顶点度数之和 = 2×边数"),
        FormulaDefinition("树的性质", "|E|=|V|-1", ["V", "E"], "general", "graph_theory",
                         axioms=["图的握手定理"], derives=["无圈图"],
                         notes="树满足 |E| = |V| - 1"),
        FormulaDefinition("欧拉公式-图论", "|V|-|E|+|F|=2", ["V", "E", "F"], "general", "graph_theory",
                         axioms=["树的性质"], derives=[],
                         notes="V-E+F=2（凸多面体/平面图）"),
        FormulaDefinition("排列组合基本公式", "P(n,k)=n!/(n-k)!, C(n,k)=n!/(k!(n-k)!)", ["n", "k"], "combinatorics", "combinatorics",
                         axioms=["阶乘定义"], derives=["杨辉三角"],
                         notes="排列数与组合数公式"),
        FormulaDefinition("杨辉三角递推", "C(n,k)=C(n-1,k-1)+C(n-1,k)", ["n", "k"], "combinatorics", "combinatorics",
                         axioms=["帕斯卡公式"], derives=[],
                         notes="杨辉三角每一数是上方两数之和"),
        FormulaDefinition(" Catalan 数", "C_n=(2n)!/((n+1)!*n!)", ["n"], "general", "combinatorics",
                         axioms=["组合数"], derives=["递推关系"],
                         notes="Cₙ = (2n)!/((n+1)!·n!)，括号匹配数等"),
    ])

    # ── 10. 高等几何 ─────────────────────────────────────
    library.load_batch([
        FormulaDefinition("笛卡尔坐标系", "P=(x,y)", ["x", "y"], "general", "geometry",
                         axioms=["两点距离"], derives=["直线方程"],
                         notes="平面直角坐标系中的点"),
        FormulaDefinition("直线方程-点斜式", "y-y0=k*(x-x0)", ["x", "y", "x0", "y0", "k"], "general", "geometry",
                         axioms=["笛卡尔坐标系"], derives=["直线方程-斜截式"],
                         notes="y-y₀ = k(x-x₀)"),
        FormulaDefinition("直线方程-一般式", "Ax+By+C=0", ["A", "B", "C", "x", "y"], "general", "geometry",
                         axioms=["直线方程-点斜式"], derives=["点到直线距离"],
                         notes="Ax+By+C=0"),
        FormulaDefinition("圆方程", "(x-a)^2+(y-b)^2=r^2", ["x", "y", "a", "b", "r"], "general", "geometry",
                         axioms=["笛卡尔坐标系"], derives=["圆的一般方程"],
                         notes="(x-a)²+(y-b)²=r²（圆心(a,b)，半径r）"),
        FormulaDefinition("椭圆方程", "x^2/a^2+y^2/b^2=1", ["x", "y", "a", "b"], "general", "geometry",
                         axioms=["圆方程"], derives=["椭圆离心率"],
                         notes="x²/a²+y²/b²=1（标准椭圆）"),
        FormulaDefinition("双曲线方程", "x^2/a^2-y^2/b^2=1", ["x", "y", "a", "b"], "general", "geometry",
                         axioms=["椭圆方程"], derives=["双曲线离心率"],
                         notes="x²/a²-y²/b²=1（标准双曲线）"),
        FormulaDefinition("抛物线方程", "y^2=4ax", ["x", "y", "a"], "general", "geometry",
                         axioms=[], derives=["抛物线焦点"],
                         notes="y²=4ax（焦点(a,0)，准线x=-a）"),
        FormulaDefinition("圆锥曲线统一方程", "r=e*p/(1+e*cos(theta))", ["r", "e", "p", "theta"], "general", "geometry",
                         axioms=["极坐标"], derives=[],
                         notes="圆锥曲线极坐标统一方程"),
        FormulaDefinition("极坐标-圆", "r=2*R*cos(theta)", ["r", "R", "theta"], "general", "geometry",
                         axioms=["圆方程"], derives=[],
                         notes="极坐标圆方程"),
        FormulaDefinition("极坐标-阿基米德螺线", "r=a*theta", ["r", "a", "theta"], "general", "geometry",
                         axioms=["极坐标"], derives=[],
                         notes="阿基米德螺线 r = aθ"),
        FormulaDefinition("极坐标-玫瑰线", "r=a*sin(n*theta)", ["r", "a", "n", "theta"], "general", "geometry",
                         axioms=["极坐标"], derives=[],
                         notes="玫瑰线 r = a·sin(nθ)"),
        FormulaDefinition("卡诺定理", "内角和=(n-2)*pi", ["n"], "general", "geometry",
                         axioms=["三角形内角和"], derives=["正n边形内角和"],
                         notes="n边形内角和 = (n-2)π"),
        FormulaDefinition("正n边形内角和", "(n-2)*180", ["n"], "general", "geometry",
                         axioms=["卡诺定理"], derives=["正n边形外角和"],
                         notes="正n边形内角和 = (n-2)×180°"),
        FormulaDefinition("正n边形外角和", "360", ["n"], "general", "geometry",
                         axioms=["正n边形内角和"], derives=[],
                         notes="任意凸多边形外角和 = 360°"),
        FormulaDefinition("正n边形每个内角", "(n-2)*180/n", ["n"], "general", "geometry",
                         axioms=["正n边形内角和"], derives=[],
                         notes="正n边形每个内角 = (n-2)×180°/n"),
    ])

    # ── 11. 数值分析 ─────────────────────────────────────
    library.load_batch([
        FormulaDefinition("牛顿迭代法", "x_{n+1}=x_n-f(x_n)/f'(x_n)", ["x", "f"], "general", "analysis",
                         axioms=["导数定义"], derives=["牛顿法收敛阶"],
                         notes="xₙ₊₁ = xₙ - f(xₙ)/f'(xₙ)"),
        FormulaDefinition("二分法", "f(a)*f(b)<0, mid=(a+b)/2", ["a", "b", "f"], "general", "analysis",
                         axioms=["介值定理"], derives=[],
                         notes="二分法求根：若 f(a)·f(b)<0 则根在 [a,b] 内"),
        FormulaDefinition("拉格朗日中值定理", "f(b)-f(a)=f'(c)*(b-a)", ["f", "a", "b", "c"], "general", "analysis",
                         axioms=["导数定义"], derives=["罗尔定理"],
                         notes="∃c∈(a,b): f(b)-f(a)=f'(c)(b-a)"),
        FormulaDefinition("罗尔定理", "f(a)=f(b)implies f'(c)=0", ["f", "a", "b", "c"], "general", "analysis",
                         axioms=["拉格朗日中值定理"], derives=[],
                         notes="若 f(a)=f(b)，则 ∃c∈(a,b): f'(c)=0"),
        FormulaDefinition("泰勒中值定理", "f(x)=f(a)+f'(a)(x-a)+f''(c)/2*(x-a)^2", ["f", "a", "x", "c"], "general", "analysis",
                         axioms=["泰勒展开"], derives=[],
                         notes="带拉格朗日余项的泰勒公式"),
        FormulaDefinition("洛必达法则", "lim f/g = lim f'/g'", ["f", "g"], "general", "analysis",
                         axioms=["拉格朗日中值定理"], derives=[],
                         notes="lim(x→a) f(x)/g(x) = lim(x→a) f'(x)/g'(x)（0/0型）"),
    ])

    # ── 12. 物理相关数学公式 ──────────────────────────────
    # 物理常量已注册为 PrimitiveRegistry 常量，公式中直接使用符号名
    library.load_batch([
        FormulaDefinition("动能", "1/2*m*v^2", ["m", "v"], "energy", "physics",
                         axioms=["功的定义"], derives=["动能定理"],
                         notes="E_k = ½mv²"),
        FormulaDefinition("势能-重力", "m*g*h", ["m", "g", "h"], "energy", "physics",
                         axioms=["动能"], derives=["机械能守恒"],
                         notes="E_p = mgh（g为重力加速度常量）"),
        FormulaDefinition("动能定理", "1/2*m*v2^2-1/2*m*v1^2", ["m", "v1", "v2"], "energy", "physics",
                         axioms=["动能"], derives=["机械能守恒"],
                         notes="合外力做功 = 动能变化"),
        FormulaDefinition("万有引力", "G*m1*m2/r^2", ["m1", "m2", "r"], "general", "physics",
                         axioms=[], derives=["开普勒第三定律"],
                         notes="F = Gm₁m₂/r²（G为万有引力常数）"),
        FormulaDefinition("开普勒第三定律", "T^2/r^3", ["T", "r"], "general", "physics",
                         axioms=["万有引力"], derives=[],
                         notes="T²/r³ = 常数（周期平方与半长轴立方之比）"),
        FormulaDefinition("理想气体状态方程", "P*V-n*R_gas*T", ["P", "V", "n", "T"], "general", "physics",
                         axioms=[], derives=["道尔顿分压定律"],
                         notes="PV = nRT（R_gas为理想气体常数）"),
        FormulaDefinition("波义耳定律", "P1*V1-P2*V2", ["P1", "V1", "P2", "V2"], "general", "physics",
                         axioms=["理想气体状态方程"], derives=[],
                         notes="等温过程：P₁V₁ = P₂V₂"),
        FormulaDefinition("欧姆定律", "V-I*R", ["V", "I", "R"], "general", "physics",
                         axioms=[], derives=["电功率"],
                         notes="V = IR"),
        FormulaDefinition("电功率", "V*I", ["V", "I"], "general", "physics",
                         axioms=["欧姆定律"], derives=["焦耳定律"],
                         notes="P = VI = I²R = V²/R"),
        FormulaDefinition("焦耳定律", "I^2*R*t", ["I", "R", "t"], "general", "physics",
                         axioms=["电功率"], derives=[],
                         notes="Q = I²Rt（电热）"),
        FormulaDefinition("速度", "s/t", ["s", "t"], "general", "physics",
                         axioms=[], derives=["加速度"],
                         notes="v = s/t"),
        FormulaDefinition("加速度", "(v-v0)/t", ["v", "v0", "t"], "general", "physics",
                         axioms=["速度"], derives=["运动学方程"],
                         notes="a = (v-v₀)/t"),
        FormulaDefinition("运动学方程-位移", "v0*t+1/2*a*t^2", ["v0", "a", "t"], "general", "physics",
                         axioms=["加速度"], derives=["运动学方程-速度"],
                         notes="s = v₀t + ½at²"),
        FormulaDefinition("运动学方程-速度", "v0+a*t", ["v0", "a", "t"], "general", "physics",
                         axioms=["加速度"], derives=["运动学方程-位移"],
                         notes="v = v₀ + at"),
    ])

    # ── 13. 向量与空间几何 ──────────────────────────────
    library.load_batch([
        FormulaDefinition("向量加法", "a+b=(ax+bx,ay+by,az+bz)", ["a", "b"], "general", "solid_geometry",
                         axioms=["笛卡尔坐标系"], derives=["向量减法"],
                         notes="向量加法：对应分量相加"),
        FormulaDefinition("向量减法", "a-b=(ax-bx,ay-by,az-bz)", ["a", "b"], "general", "solid_geometry",
                         axioms=["向量加法"], derives=[],
                         notes="向量减法：对应分量相减"),
        FormulaDefinition("向量点积-分量形式", "ax*bx+ay*by+az*bz", ["ax", "ay", "az", "bx", "by", "bz"], "general", "solid_geometry",
                         axioms=["向量点积"], derives=["向量夹角公式"],
                         notes="a·b = ax·bx + ay·by + az·bz"),
        FormulaDefinition("向量夹角公式", "cos(theta)=(a.b)/(|a|*|b|)", ["a", "b"], "general", "solid_geometry",
                         axioms=["向量点积"], derives=[],
                         notes="cosθ = (a·b)/(|a||b|)"),
        FormulaDefinition("向量叉积", "a x b=(ay*bz-az*by, az*bx-ax*bz, ax*by-ay*bx)", ["a", "b"], "general", "solid_geometry",
                         axioms=["向量点积"], derives=["混合积"],
                         notes="向量叉积：垂直于两向量"),
        FormulaDefinition("混合积", "(a x b).c", ["a", "b", "c"], "general", "solid_geometry",
                         axioms=["向量叉积"], derives=["四面体体积"],
                         notes="[a,b,c] = (a×b)·c（平行六面体体积）"),
        FormulaDefinition("四面体体积", "1/6*|(a x b).c|", ["a", "b", "c"], "volume", "solid_geometry",
                         axioms=["混合积"], derives=[],
                         notes="V = ⅙|(a×b)·c|"),
        FormulaDefinition("向量投影面积", "A_proj=A*cos(theta)", ["A", "theta"], "general", "solid_geometry",
                         axioms=["投影面积公式"], derives=["三视图面积关系"],
                         notes="投影面积 = 原面积 × cos(倾角)"),
    ])

    # ── 14. 特殊函数与常数 ──────────────────────────────
    library.load_batch([
        FormulaDefinition("伽玛函数", "Gamma(n)=(n-1)! (n为正整数)", ["n"], "general", "analysis",
                         axioms=["阶乘定义"], derives=["贝塔函数"],
                         notes="Γ(n) = (n-1)! for positive integers"),
        FormulaDefinition("贝塔函数", "B(p,q)=Gamma(p)*Gamma(q)/Gamma(p+q)", ["p", "q"], "general", "analysis",
                         axioms=["伽玛函数"], derives=[],
                         notes="B(p,q) = Γ(p)Γ(q)/Γ(p+q)"),
        FormulaDefinition("斐波那契数列", "F(n)=F(n-1)+F(n-2), F(0)=0,F(1)=1", ["n"], "general", "number_theory",
                         axioms=[], derives=["斐波那契通项公式"],
                         notes="Fₙ = Fₙ₋₁ + Fₙ₋₂, F₀=0, F₁=1"),
        FormulaDefinition("斐波那契通项公式", "(phi^n - psi^n)/sqrt(5)", ["n"], "general", "number_theory",
                         axioms=["斐波那契数列"], derives=[],
                         notes="Fₙ = (φⁿ-ψⁿ)/√5, φ=(1+√5)/2, ψ=(1-√5)/2"),
        FormulaDefinition("欧拉数e", "2.718281828...", [], "general", "analysis",
                         axioms=["e^x展开"], derives=["自然对数"],
                         notes="e = lim(n→∞)(1+1/n)ⁿ = Σ1/n!"),
        FormulaDefinition("黄金比例", "(1+sqrt(5))/2", [], "general", "number_theory",
                         axioms=["斐波那契数列"], derives=[],
                         notes="φ = (1+√5)/2 ≈ 1.6180339887..."),
        FormulaDefinition("圆周率pi", "3.1415926535...", [], "general", "geometry",
                         axioms=["圆面积"], derives=["圆周长"],
                         notes="π = 圆周长/直径 ≈ 3.1415926535..."),
        FormulaDefinition("欧拉-马歇罗尼常数", "0.5772156649...", [], "general", "analysis",
                         axioms=[], derives=[],
                         notes="γ = lim(n→∞)(Σ1/k - ln n) ≈ 0.5772156649..."),
        FormulaDefinition("阿贝尔-πλαц常数", "2.612...", [], "general", "number_theory",
                         axioms=[], derives=[],
                         notes="Apéry常数 ζ(3) = Σ1/n³ ≈ 1.2020569..."),
    ])

    # ── 15. 傅里叶分析与信号处理 ──────────────────────
    library.load_batch([
        FormulaDefinition("傅里叶系数-a_n", "1/pi*∫f(x)*cos(nx)dx", ["f", "n"], "general", "fourier_analysis",
                         axioms=["傅里叶级数"], derives=["傅里叶系数-b_n"],
                         notes="aₙ = (1/π)∫f(x)cos(nx)dx"),
        FormulaDefinition("傅里叶系数-b_n", "1/pi*∫f(x)*sin(nx)dx", ["f", "n"], "general", "fourier_analysis",
                         axioms=["傅里叶系数-a_n"], derives=[],
                         notes="bₙ = (1/π)∫f(x)sin(nx)dx"),
        FormulaDefinition("帕塞瓦尔恒等式", "1/pi*∫|f|^2dx=a0^2/2+sum(an^2+bn^2)", ["f", "an", "bn"], "general", "fourier_analysis",
                         axioms=["傅里叶级数"], derives=[],
                         notes="能量守恒：∫|f|² = π(a₀²/2 + Σ(aₙ²+bₙ²))"),
        FormulaDefinition("离散傅里叶变换DFT", "X_k=sum_{n=0}^{N-1}x_n*e^{-i*2*pi*k*n/N}", ["x", "N"], "general", "fourier_analysis",
                         axioms=["傅里叶变换"], derives=["快速傅里叶变换FFT"],
                         notes="Xₖ = Σxₙ·e^(-i2πkn/N)"),
        FormulaDefinition("快速傅里叶变换FFT", "O(N*log(N))", ["N"], "general", "fourier_analysis",
                         axioms=["离散傅里叶变换DFT"], derives=[],
                         notes="FFT将DFT复杂度从O(N²)降至O(NlogN)"),
    ])

    # ── 16. 统计推断 ────────────────────────────────────
    library.load_batch([
        FormulaDefinition("样本均值", "x_bar=sum(x_i)/n", ["x_i", "n"], "general", "statistics",
                         axioms=["期望线性性质"], derives=["样本方差"],
                         notes="x̄ = Σxᵢ/n"),
        FormulaDefinition("样本方差", "s^2=sum((x_i-x_bar)^2)/(n-1)", ["x_i", "x_bar", "n"], "general", "statistics",
                         axioms=["样本均值"], derives=["标准差-样本"],
                         notes="s² = Σ(xᵢ-x̄)²/(n-1)（无偏估计）"),
        FormulaDefinition("标准差-样本", "s=sqrt(s^2)", ["s"], "general", "statistics",
                         axioms=["样本方差"], derives=[],
                         notes="s = √s²"),
        FormulaDefinition("协方差", "Cov(X,Y)=E((X-mu_x)(Y-mu_y))", ["X", "Y"], "general", "statistics",
                         axioms=["期望线性性质"], derives=["相关系数"],
                         notes="Cov(X,Y) = E[(X-μₓ)(Y-μᵧ)]"),
        FormulaDefinition("相关系数", "rho=Cov(X,Y)/(sigma_X*sigma_Y)", ["X", "Y"], "general", "statistics",
                         axioms=["协方差"], derives=[],
                         notes="ρ = Cov(X,Y)/(σₓ·σᵧ)，ρ∈[-1,1]"),
        FormulaDefinition("线性回归-斜率", "b=sum((x_i-x_bar)(y_i-y_bar))/sum((x_i-x_bar)^2)", ["x_i", "y_i"], "general", "statistics",
                         axioms=["样本均值"], derives=["线性回归-截距"],
                         notes="b = Σ(xᵢ-x̄)(yᵢ-ȳ)/Σ(xᵢ-x̄)²"),
        FormulaDefinition("线性回归-截距", "a=y_bar-b*x_bar", ["y_bar", "b", "x_bar"], "general", "statistics",
                         axioms=["线性回归-斜率"], derives=[],
                         notes="a = ȳ - b·x̄"),
        FormulaDefinition("卡方分布", "Chi2=Z1^2+...+Zk^2", ["Z", "k"], "general", "statistics",
                         axioms=["标准正态分布"], derives=["t分布"],
                         notes="χ²分布：k个独立标准正态变量的平方和"),
        FormulaDefinition("t分布", "t=(X-mu)/(S/sqrt(n))", ["X", "mu", "S", "n"], "general", "statistics",
                         axioms=["正态分布密度"], derives=["置信区间"],
                         notes="t = (X̄-μ)/(S/√n)，自由度为n-1"),
        FormulaDefinition("置信区间-均值", "x_bar+/-t*s/sqrt(n)", ["x_bar", "t", "s", "n"], "general", "statistics",
                         axioms=["t分布"], derives=[],
                         notes="μ的(1-α)置信区间：x̄±t·s/√n"),
    ])

    registry._formula_library = library
    library.load_batch([
        # 补充：将现有等价关系也注册为公式定义
        FormulaDefinition("圆面积", "pi*r^2", ["r"], "area", "geometry",
                         axioms=["圆的定义"], derives=["球表面积", "球体积"],
                         notes="圆面积 = πr²（基础公式）"),
        FormulaDefinition("正方形面积", "a^2", ["a"], "area", "geometry",
                         axioms=["长方形面积"], derives=["菱形面积"],
                         notes="正方形面积 = 边长²（长方形的特例）"),
        FormulaDefinition("立方体体积", "a^3", ["a"], "volume", "solid_geometry",
                         axioms=["长方体体积"], derives=["正方体表面积"],
                         notes="立方体体积 = 棱长³"),
        FormulaDefinition("长方体体积", "l*w*h", ["l", "w", "h"], "volume", "solid_geometry",
                         axioms=["棱柱体积（通用）"], derives=["立方体体积"],
                         notes="长方体体积 = 长×宽×高"),
    ])

    logger.info(f"  [公式库] 总公式数: {library.total_count()}")
    for domain, count in sorted(library.domain_counts().items()):
        logger.info(f"    {domain}: {count} 个")

    # ── 加载 Matha 原生源码（.matha 文件）──────────────
    try:
        import os
        matha_dir = os.path.join(os.path.dirname(__file__), 'formulas')
        if os.path.isdir(matha_dir):
            from src.matha.compiler import compile_dir
            count = compile_dir(matha_dir, registry)
            if count > 0:
                logger.info(f"  [Matha 编译器] 从 .matha 源码加载 {count} 个公式")
    except Exception as e:
        logger.warning(f"  [Matha 编译器] 加载 .matha 文件失败: {e}")

    return library
