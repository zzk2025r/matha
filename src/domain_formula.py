# -*- coding: utf-8 -*-
"""
Matha 领域公式注册系统（Domain Formula Registry）

将每个领域的核心公式注册到全局公式库，实现：
  1. 领域公式自动发现与注册
  2. 跨领域公式联动（共享变量自动推导）
  3. 公式版本管理与成长追踪
  4. 公式 → MIR 自动编译
"""
from __future__ import annotations
import importlib
import inspect
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.symbolic import Expr, Var, Num, Mul, Div, Add, Sub, Pow, Neg, FuncCall, symbol_expr
from src.formula_system import Formula, FormulaRegistry

logger = logging.getLogger("matha.domain_formula")


# ============================================================
#  领域公式元数据
# ============================================================

@dataclass
class DomainFormulaMeta:
    """领域公式元数据。"""
    domain: str                    # 领域名（如 "mechanics"）
    formula_name: str              # 公式名（如 "牛顿第二定律"）
    expr_str: str                  # 表达式字符串
    params: list[str]              # 参数名
    description: str = ""          # 描述
    category: str = "general"     # 分类
    unit: str = ""                 # 单位
    source_function: str = ""      # 源函数名
    version: str = "1.0"           # 公式版本


# ============================================================
#  领域公式注册表
# ============================================================

class DomainFormulaRegistry:
    """领域公式注册表：统一管理各领域公式。"""

    # 预定义领域 → 公式注册表
    _DOMAIN_FORMULAS: dict[str, list[dict]] = {
        "mechanics": [
            {"name": "牛顿第二定律", "expr": "m * a", "params": ["F", "m", "a"],
             "description": "力 = 质量 × 加速度", "category": "力", "unit": "N"},
            {"name": "动能", "expr": "0.5 * m * v^2", "params": ["Ek", "m", "v"],
             "description": "动能 = 1/2 × 质量 × 速度²", "category": "能量", "unit": "J"},
            {"name": "动量", "expr": "m * v", "params": ["p", "m", "v"],
             "description": "动量 = 质量 × 速度", "category": "动量", "unit": "kg·m/s"},
            {"name": "重力", "expr": "m * g", "params": ["G", "m", "g"],
             "description": "重力 = 质量 × 重力加速度", "category": "力", "unit": "N"},
            {"name": "功", "expr": "F * s * cos(theta)", "params": ["W", "F", "s", "theta"],
             "description": "功 = 力 × 位移 × cos(夹角)", "category": "功", "unit": "J"},
            {"name": "功率", "expr": "F * v", "params": ["P", "F", "v"],
             "description": "功率 = 力 × 速度", "category": "功率", "unit": "W"},
            {"name": "自由落体速度", "expr": "sqrt(2 * g * h)", "params": ["v", "g", "h"],
             "description": "自由落体末速度 = √(2gh)", "category": "运动学", "unit": "m/s"},
            {"name": "平抛射程", "expr": "v0 * sqrt(2 * h / g)", "params": ["R", "v0", "h", "g"],
             "description": "平抛射程 = 初速度 × √(2h/g)", "category": "运动学", "unit": "m"},
        ],
        "geometry": [
            {"name": "圆面积", "expr": "pi * r^2", "params": ["S", "r"],
             "description": "圆面积 = πr²", "category": "area", "unit": "m²"},
            {"name": "圆周长", "expr": "2 * pi * r", "params": ["C", "r"],
             "description": "圆周长 = 2πr", "category": "perimeter", "unit": "m"},
            {"name": "球体积", "expr": "4/3 * pi * r^3", "params": ["V", "r"],
             "description": "球体积 = 4/3πr³", "category": "volume", "unit": "m³"},
            {"name": "球表面积", "expr": "4 * pi * r^2", "params": ["A", "r"],
             "description": "球表面积 = 4πr²", "category": "area", "unit": "m²"},
            {"name": "圆柱体积", "expr": "pi * r^2 * h", "params": ["V", "r", "h"],
             "description": "圆柱体积 = πr²h", "category": "volume", "unit": "m³"},
            {"name": "圆锥体积", "expr": "1/3 * pi * r^2 * h", "params": ["V", "r", "h"],
             "description": "圆锥体积 = 1/3πr²h", "category": "volume", "unit": "m³"},
        ],
        "electromagnetism": [
            {"name": "欧姆定律", "expr": "V / R", "params": ["I", "V", "R"],
             "description": "电流 = 电压 / 电阻", "category": "电路", "unit": "A"},
            {"name": "电功率", "expr": "V * I", "params": ["P", "V", "I"],
             "description": "电功率 = 电压 × 电流", "category": "功率", "unit": "W"},
            {"name": "焦耳热", "expr": "I^2 * R * t", "params": ["Q", "I", "R", "t"],
             "description": "焦耳热 = I²Rt", "category": "热", "unit": "J"},
            {"name": "库仑力", "expr": "k * q1 * q2 / r^2", "params": ["F", "k", "q1", "q2", "r"],
             "description": "库仑力 = kq₁q₂/r²", "category": "力", "unit": "N"},
        ],
        "thermodynamics": [
            {"name": "理想气体状态方程", "expr": "P * V / (n * R)", "params": ["T", "P", "V", "n", "R"],
             "description": "T = PV/(nR)", "category": "状态方程", "unit": "K"},
            {"name": "热传递", "expr": "m * c * dT", "params": ["Q", "m", "c", "dT"],
             "description": "热量 = 质量 × 比热容 × 温升", "category": "热", "unit": "J"},
            {"name": "热机效率", "expr": "1 - Tc / Th", "params": ["eta", "Tc", "Th"],
             "description": "卡诺效率 = 1 - Tc/Th", "category": "效率", "unit": ""},
        ],
        "wave_optics": [
            {"name": "波长频率关系", "expr": "c / f", "params": ["lambda_", "c", "f"],
             "description": "λ = c/f", "category": "波动", "unit": "m"},
            {"name": "折射定律", "expr": "n1 * sin(theta1) / (n2 * sin(theta2))", "params": ["ratio", "n1", "theta1", "n2", "theta2"],
             "description": "n₁sinθ₁ = n₂sinθ₂", "category": "折射", "unit": ""},
        ],
        "nuclear": [
            {"name": "质能方程", "expr": "m * c^2", "params": ["E", "m", "c"],
             "description": "E = mc²", "category": "能量", "unit": "J"},
            {"name": "半衰期", "expr": "N0 * (1/2)^(t / T_half)", "params": ["N", "N0", "t", "T_half"],
             "description": "N = N₀ × (1/2)^(t/T½)", "category": "衰变", "unit": ""},
        ],
        "celestial": [
            {"name": "开普勒第三定律", "expr": "2 * pi * sqrt(r^3 / (G * M))", "params": ["T", "r", "G", "M"],
             "description": "T = 2π√(r³/GM)", "category": "轨道", "unit": "s"},
            {"name": "万有引力", "expr": "G * M * m / r^2", "params": ["F", "G", "M", "m", "r"],
             "description": "F = GMm/r²", "category": "力", "unit": "N"},
            {"name": "第一宇宙速度", "expr": "sqrt(G * M / R)", "params": ["v", "G", "M", "R"],
             "description": "v = √(GM/R)", "category": "速度", "unit": "m/s"},
        ],
        "chemistry": [
            {"name": "摩尔数", "expr": "m / M", "params": ["n", "m", "M"],
             "description": "n = m/M（质量/摩尔质量）", "category": "物质的量", "unit": "mol"},
            {"name": "浓度", "expr": "n / V", "params": ["c", "n", "V"],
             "description": "c = n/V", "category": "浓度", "unit": "mol/L"},
            {"name": "理想气体状态", "expr": "n * R * T / V", "params": ["P", "n", "R", "T", "V"],
             "description": "P = nRT/V", "category": "状态方程", "unit": "Pa"},
        ],
    }

    def __init__(self):
        self._registry: FormulaRegistry = FormulaRegistry()
        self._loaded_domains: set[str] = set()
        self._cross_domain_links: dict[str, list[str]] = {}

    def register_domain_formulas(self, domain: str) -> int:
        """注册指定领域的公式。"""
        if domain in self._loaded_domains:
            logger.debug(f"  [领域公式] 领域 {domain} 已加载")
            return 0

        formulas = self._DOMAIN_FORMULAS.get(domain, [])
        if not formulas:
            # 尝试从领域模块自动扫描
            formulas = self._scan_domain_module(domain)

        count = 0
        for fdata in formulas:
            try:
                expr = symbol_expr(fdata["expr"])
                formula = Formula(
                    name=fdata["name"],
                    expr=expr,
                    params=fdata["params"],
                    category=fdata.get("category", "general"),
                    notes=fdata.get("description", ""),
                    expr_text=f"{fdata['name']} = {fdata['expr']}",
                    domain=domain,
                )
                self._registry.register(formula)
                count += 1
                logger.debug(f"  [领域公式] 注册: {domain}/{fdata['name']}")
            except Exception as e:
                logger.warning(f"  [领域公式] 注册失败 {domain}/{fdata['name']}: {e}")

        self._loaded_domains.add(domain)
        logger.info(f"  [领域公式] 领域 {domain} 注册完成: +{count} 个公式")
        return count

    def _scan_domain_module(self, domain: str) -> list[dict]:
        """从领域 Python 模块扫描公式函数。"""
        formulas = []
        try:
            module = importlib.import_module(f"src.domains.{domain}")
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("_"):
                    continue
                doc = inspect.getdoc(func) or ""
                # 尝试从函数签名推断参数
                try:
                    sig = inspect.signature(func)
                    params = [p for p in sig.parameters if p not in ("self",)]
                except (ValueError, TypeError):
                    params = []

                # 尝试从函数体 AST 提取表达式
                expr_str = ""
                try:
                    source = inspect.getsource(func)
                    import ast
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name == name:
                            for stmt in node.body:
                                if isinstance(stmt, ast.Return) and stmt.value:
                                    expr_str = ast.unparse(stmt.value)
                                    break
                            break
                except (OSError, SyntaxError, Exception):
                    pass

                if expr_str:
                    formulas.append({
                        "name": name,
                        "expr": expr_str,
                        "params": params,
                        "description": doc.split("\n")[0] if doc else "",
                        "category": domain,
                    })
        except ImportError:
            pass
        return formulas

    def register_all_domains(self) -> int:
        """注册所有预定义领域的公式。"""
        total = 0
        for domain in self._DOMAIN_FORMULAS:
            total += self.register_domain_formulas(domain)
        # 也注册 geometry 默认公式（register_geometric_defaults 返回 None）
        self._registry.register_geometric_defaults()
        # 返回总公式数（包含几何默认公式）
        return len(self._registry.list_formulas())

    def get_cross_domain_links(self) -> dict[str, list[str]]:
        """找出跨领域共享变量的公式对。"""
        links: dict[str, list[str]] = {}
        formulas = list(self._registry.list_formulas())
        for i, f1 in enumerate(formulas):
            vars1 = f1.free_vars()
            for f2 in formulas[i + 1:]:
                vars2 = f2.free_vars()
                shared = vars1 & vars2
                if shared:
                    links.setdefault(f1.name, []).append(f2.name)
                    links.setdefault(f2.name, []).append(f1.name)
        self._cross_domain_links = links
        return links

    def get_linked_formulas(self, name: str) -> list[str]:
        """获取与指定公式有跨领域联动的公式名。"""
        return self._cross_domain_links.get(name, [])

    @property
    def registry(self) -> FormulaRegistry:
        """返回底层公式注册表。"""
        return self._registry

    def summary(self) -> str:
        """领域公式总览。"""
        lines = ["  ┌─ 领域公式注册总览 ────────────────────────"]
        lines.append(f"  │ 已加载领域: {len(self._loaded_domains)} 个")
        lines.append(f"  │ 总公式数: {len(self._registry.list_formulas())} 个")
        lines.append(f"  │ 跨领域联动: {len(self._cross_domain_links)} 对")
        by_domain: dict[str, int] = {}
        for f in self._registry.list_formulas():
            by_domain[f.domain] = by_domain.get(f.domain, 0) + 1
        for domain, count in sorted(by_domain.items()):
            lines.append(f"  │   {domain}: {count} 个公式")
        lines.append("  └───────────────────────────────────────────")
        return "\n".join(lines)


# ============================================================
#  跨领域公式联动
# ============================================================

@dataclass
class CrossDomainLink:
    """跨领域公式联动记录。"""
    formula_a: str
    formula_b: str
    shared_vars: list[str]
    derived_formulas: list[str] = field(default_factory=list)
    domain_a: str = ""
    domain_b: str = ""


class CrossDomainFormulaEngine:
    """跨领域公式联动引擎。

    功能：
      1. 自动识别跨领域共享变量
      2. 自动推导跨领域公式关系
      3. 生成跨领域知识图谱
    """

    def __init__(self, domain_registry: DomainFormulaRegistry):
        self._domain_reg = domain_registry
        self._links: list[CrossDomainLink] = []

    def analyze_links(self) -> list[CrossDomainLink]:
        """分析所有跨领域联动。"""
        registry = self._domain_reg.registry
        formulas = list(registry.list_formulas())
        self._links = []

        for i, f1 in enumerate(formulas):
            vars1 = f1.free_vars()
            for f2 in formulas[i + 1:]:
                vars2 = f2.free_vars()
                shared = vars1 & vars2
                if shared:
                    link = CrossDomainLink(
                        formula_a=f1.name,
                        formula_b=f2.name,
                        shared_vars=sorted(shared),
                        domain_a=f1.domain,
                        domain_b=f2.domain,
                    )
                    self._links.append(link)

        return self._links

    def get_knowledge_graph(self) -> dict:
        """生成跨领域知识图谱。"""
        self.analyze_links()
        graph: dict[str, dict] = {}
        for link in self._links:
            for name in [link.formula_a, link.formula_b]:
                if name not in graph:
                    graph[name] = {"domain": "", "links": [], "shared_with": []}
            graph[link.formula_a]["links"].append(link.formula_b)
            graph[link.formula_a]["shared_with"].extend(link.shared_vars)
            graph[link.formula_b]["links"].append(link.formula_a)
            graph[link.formula_b]["shared_with"].extend(link.shared_vars)
        return graph


# ============================================================
#  便捷函数
# ============================================================

def get_domain_formula_registry() -> DomainFormulaRegistry:
    """获取领域公式注册表（单例）。"""
    from src.formula_system import _formula_registry as main_reg
    reg = DomainFormulaRegistry()
    # 同步到全局注册表
    for domain in reg._DOMAIN_FORMULAS:
        reg.register_domain_formulas(domain)
    return reg


def register_all_domain_formulas(registry: FormulaRegistry = None) -> int:
    """注册所有领域公式到指定注册表。"""
    if registry is None:
        from src.formula_system import get_formula_registry
        registry = get_formula_registry()

    domain_reg = DomainFormulaRegistry()
    count = domain_reg.register_all_domains()
    # 同步到全局注册表
    for name, formula in domain_reg.registry._formulas.items():
        if name not in registry._formulas:
            registry.register(formula)
    return count
