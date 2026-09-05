# -*- coding: utf-8 -*-
"""Matha 联动引擎（LinkageEngine）

职责：
  1. 检测所有模块/功能的兼容性与可用性
  2. 提供跨模块公式调用接口
  3. 维护模块间依赖关系图
  4. 辅助自主升级功能进行各功能升级
  5. 防止各功能脱节

设计原则：
  - 不修改各模块的内部实现
  - 通过注册表机制发现所有模块
  - 通过接口一致性检查兼容性
  - 提供统一的跨模块调用入口
"""
from __future__ import annotations
import logging
import importlib
import inspect
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List, Set

logger = logging.getLogger("matha.linkage")


@dataclass
class ModuleInfo:
    """模块信息。"""
    name: str
    path: str
    category: str = "unknown"
    status: str = "unknown"           # "ok" | "error" | "deprecated"
    functions: List[str] = field(default_factory=list)
    formulas: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class LinkageResult:
    """联动检测结果。"""
    success: bool
    message: str
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class LinkageEngine:
    """联动引擎：检测、协调、连接所有 Matha 功能模块。"""

    def __init__(self):
        self._modules: Dict[str, ModuleInfo] = {}
        self._formula_registry = None
        self._domain_builtins: Dict[str, dict] = {}

    def _get_registry(self):
        """延迟获取公式注册表。"""
        if self._formula_registry is None:
            from src.formula_system import get_formula_registry
            self._formula_registry = get_formula_registry()
        return self._formula_registry

    # ── 模块发现 ──────────────────────────────────────────

    def discover_modules(self, paths: List[str] | None = None) -> Dict[str, ModuleInfo]:
        """发现所有已加载的模块并生成信息。"""
        modules = {}

        # 1. 发现 domains 模块
        try:
            import src.domains
            domain_dir = inspect.getfile(src.domains)
            import os
            domain_pkg = os.path.dirname(domain_dir)
            for fname in os.listdir(domain_pkg):
                if fname.endswith(".py") and not fname.startswith("_"):
                    mod_name = fname[:-3]
                    modules[f"domain.{mod_name}"] = ModuleInfo(
                        name=mod_name, path=f"src.domains.{mod_name}",
                        category="domain",
                    )
        except Exception as e:
            logger.warning(f"发现 domains 模块失败: {e}")

        # 2. 发现 stdlib 模块
        try:
            import src.stdlib
            stdlib_dir = inspect.getfile(src.stdlib)
            import os
            stdlib_pkg = os.path.dirname(stdlib_dir)
            for fname in os.listdir(stdlib_pkg):
                if fname.endswith(".py") and not fname.startswith("_"):
                    mod_name = fname[:-3]
                    if mod_name == "__init__":
                        continue
                    modules[f"stdlib.{mod_name}"] = ModuleInfo(
                        name=mod_name, path=f"src.stdlib.{mod_name}",
                        category="stdlib",
                    )
        except Exception as e:
            logger.warning(f"发现 stdlib 模块失败: {e}")

        # 3. 发现 formula_system
        modules["formula_system"] = ModuleInfo(
            name="formula_system", path="src.formula_system",
            category="core",
        )

        # 4. 发现 symbolic
        modules["symbolic"] = ModuleInfo(
            name="symbolic", path="src.symbolic",
            category="core",
        )

        # 5. 加载各模块信息
        for mod_key, info in list(modules.items()):
            self._load_module_info(info)

        self._modules = modules
        return modules

    def _load_module_info(self, info: ModuleInfo) -> None:
        """加载模块的函数列表、公式列表和依赖关系。"""
        try:
            mod = importlib.import_module(info.path)
            # 收集所有公开函数
            for name, obj in inspect.getmembers(mod, inspect.isfunction):
                if not name.startswith("_"):
                    info.functions.append(name)
            # 收集所有公开类
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if not name.startswith("_") and obj.__module__ == info.path:
                    info.functions.append(f"{name}（类）")
            # 检测错误
            info.status = "ok"
        except Exception as e:
            info.status = "error"
            info.errors.append(str(e))

    # ── 公式系统互通 ─────────────────────────────────────

    def get_formula(self, name: str):
        """跨模块获取公式。"""
        return self._get_registry().get(name)

    def evaluate_formula(self, name: str, bindings: dict[str, float]) -> float:
        """跨模块计算公式。"""
        formula = self.get_formula(name)
        if formula is None:
            raise ValueError(f"未找到公式: {name}")
        return formula.evaluate(bindings)

    def derive_formula(self, relationship: str, source: str = "长方形面积",
                       target: str = "三角形面积"):
        """跨模块公式推导。"""
        return self._get_registry().derive(relationship, source, target)

    def verify_equivalence(self, formula_a: str, formula_b: str,
                           bindings: Optional[dict[str, float]] = None):
        """跨模块验证公式等价。"""
        return self._get_registry().verify_equivalence(formula_a, formula_b, bindings)

    # ── 兼容性检测 ───────────────────────────────────────

    def check_compatibility(self) -> LinkageResult:
        """全面检测各模块兼容性。"""
        issues = []
        suggestions = []

        # 1. 检查公式系统中所有物理公式是否正常
        reg = self._get_registry()
        physics_names = ["动能", "势能-重力", "万有引力", "速度", "加速度",
                         "电功率", "焦耳定律", "运动学方程-位移", "运动学方程-速度"]
        for name in physics_names:
            f = reg.get(name)
            if f is None:
                issues.append(f"公式 '{name}' 未注册")
            elif f.expr is None or str(f.expr) == "0":
                issues.append(f"公式 '{name}' 表达式为空")

        # 2. 检查几何公式
        geo_names = ["圆面积", "球体积", "球表面积", "圆柱体积", "圆锥体积"]
        for name in geo_names:
            f = reg.get(name)
            if f is None:
                issues.append(f"公式 '{name}' 未注册")

        # 3. 检查 domains 模块能否导入
        domains_to_check = ["celestial", "thermo", "quantum", "optics", "mechanics", "chemistry"]
        for dom in domains_to_check:
            try:
                importlib.import_module(f"src.domains.{dom}")
            except Exception as e:
                issues.append(f"domain '{dom}' 导入失败: {e}")

        # 4. 检查物理常量一致性
        try:
            from src.stdlib.physics_constants import C as PC
            from src.formula_system import get_formula_resolver
            resolver = get_formula_resolver()
            # 检查 formula_system 的常量是否与物理常量库一致
            for const_name, expected in [
                ("G", PC.G), ("c", PC.c), ("g", PC.g),
                ("h_planck", PC.h_planck), ("k_B", PC.k_B),
                ("N_A", PC.N_A), ("e_charge", PC.e_charge),
                ("R_gas", PC.R_gas), ("sigma_sb", PC.sigma_sb),
            ]:
                actual = resolver._prim._constants.get(const_name)
                if actual is not None and abs(actual - expected) > 1e-20:
                    issues.append(f"常量 '{const_name}' 不一致: formula_system={actual}, stdlib={expected}")
        except Exception as e:
            suggestions.append(f"常量一致性检查失败: {e}")

        # 5. 检查 domains 模块是否引用了物理常量
        for dom in domains_to_check:
            try:
                mod = importlib.import_module(f"src.domains.{dom}")
                src = inspect.getsource(mod)
                # 检查是否有硬编码的物理常量（应引用 stdlib）
                if "6.67430e-11" in src and "physics_constants" not in src:
                    suggestions.append(f"domain '{dom}' 硬编码了万有引力常数，应引用 stdlib.physics_constants")
                if "299792458" in src and "physics_constants" not in src:
                    suggestions.append(f"domain '{dom}' 硬编码了光速，应引用 stdlib.physics_constants")
            except Exception:
                pass

        # 6. 检查符号引擎基础功能
        from src.symbolic import symbol_expr
        test_exprs = ["x+y", "x*y", "(x+y)*z", "x^2", "sin(x)", "sqrt(x)", "(v-v0)/t"]
        for expr_str in test_exprs:
            try:
                e = symbol_expr(expr_str)
                e.evaluate({"x": 1.0, "y": 2.0, "z": 3.0, "v": 5.0, "v0": 2.0, "t": 1.0})
            except Exception as ex:
                issues.append(f"符号引擎解析失败 '{expr_str}': {ex}")

        # 7. 检查测试覆盖
        suggestions.append("建议补充以下测试用例：")
        suggestions.append("  - 物理公式跨模块调用测试")
        suggestions.append("  - 符号引擎 simplify 规则完整性测试")
        suggestions.append("  - 常量一致性回归测试")

        success = len(issues) == 0
        return LinkageResult(
            success=success,
            message="联动检测通过" if success else f"发现 {len(issues)} 个问题",
            issues=issues,
            suggestions=suggestions,
        )

    # ── 模块信息输出 ─────────────────────────────────────

    def summary(self) -> str:
        """输出联动系统摘要。"""
        if not self._modules:
            self.discover_modules()

        lines = ["=== Matha 联动引擎报告 ===", ""]

        # 核心模块
        core = {k: v for k, v in self._modules.items() if v.category == "core"}
        lines.append(f"核心模块 ({len(core)} 个):")
        for k, v in sorted(core.items()):
            lines.append(f"  {'✓' if v.status == 'ok' else '✗'} {k} — {len(v.functions)} 个函数")

        # 领域模块
        domains = {k: v for k, v in self._modules.items() if v.category == "domain"}
        lines.append(f"\n领域模块 ({len(domains)} 个):")
        for k, v in sorted(domains.items()):
            icon = "✓" if v.status == "ok" else "✗"
            lines.append(f"  {icon} {k} — {len(v.functions)} 个函数")

        # 标准库
        stdlib = {k: v for k, v in self._modules.items() if v.category == "stdlib"}
        lines.append(f"\n标准库 ({len(stdlib)} 个):")
        for k, v in sorted(stdlib.items()):
            icon = "✓" if v.status == "ok" else "✗"
            lines.append(f"  {icon} {k} — {len(v.functions)} 个函数")

        # 公式系统
        fs = self._modules.get("formula_system")
        if fs:
            reg = self._get_registry()
            lines.append(f"\n公式系统:")
            lines.append(f"  ✓ formula_system — {len(reg._formulas)} 个公式")

        lines.append("")
        return "\n".join(lines)

    # ── 辅助升级 ─────────────────────────────────────────

    def suggest_upgrades(self) -> List[str]:
        """生成升级建议。"""
        suggestions = []

        # 检查缺失的物理常量
        from src.stdlib.physics_constants import C as PC
        missing_in_formula = []
        for attr_name in dir(PC):
            if attr_name.startswith("_"):
                continue
            val = getattr(PC, attr_name)
            if isinstance(val, (int, float)):
                formula_name = attr_name.replace("_", "")
                if formula_name not in self._get_registry()._get_resolver()._prim._constants:
                    # 检查是否需要在 formula_system 中注册
                    pass

        # 检查 domains 模块的导入
        for dom in ["celestial", "thermo", "quantum", "optics"]:
            try:
                mod = importlib.import_module(f"src.domains.{dom}")
                src = inspect.getsource(mod)
                if "import math" in src:
                    suggestions.append(f"domain '{dom}' 可直接使用 stdlib.physics_constants 替代部分 math 调用")
            except Exception:
                suggestions.append(f"domain '{dom}' 导入失败，需要修复")

        # 检查符号引擎
        from src.symbolic import symbol_expr
        # 测试新简化规则
        tests = [
            ("x-x", "0", "Sub simplify x-x=0"),
            ("x/x", "1", "Div simplify x/x=1"),
            ("x+(-x)", "0", "Add simplify x+(-x)=0"),
        ]
        for expr, expected, desc in tests:
            try:
                result = symbol_expr(expr).simplify()
                if str(result) != expected:
                    suggestions.append(f"{desc}: 期望 '{expected}' 实际 '{result}'")
            except Exception as e:
                suggestions.append(f"{desc}: 异常 {e}")

        return suggestions

    # ── 跨模块公式调用 ───────────────────────────────────

    def call_formula(self, formula_name: str, **bindings) -> float:
        """统一跨模块公式调用入口。"""
        return self.evaluate_formula(formula_name, bindings)

    def cross_module_derive(self, source: str, target: str,
                            mappings: dict[str, str]) -> dict:
        """跨模块公式推导。"""
        result = self._get_registry().derive(f"{source}→{target}", source, target)
        return {
            "source": source,
            "target": target,
            "success": result.success,
            "expr": str(result.expr) if result.expr else None,
        }


# 全局单例
_linkage_engine: Optional[LinkageEngine] = None


def get_linkage_engine() -> LinkageEngine:
    """获取全局联动引擎单例。"""
    global _linkage_engine
    if _linkage_engine is None:
        _linkage_engine = LinkageEngine()
    return _linkage_engine


def linkage_summary() -> str:
    """便捷函数：输出联动摘要。"""
    return get_linkage_engine().summary()


def linkage_check() -> LinkageResult:
    """便捷函数：执行联动检测。"""
    return get_linkage_engine().check_compatibility()


def call_formula(formula_name: str, **bindings) -> float:
    """便捷函数：跨模块调用公式。"""
    return get_linkage_engine().call_formula(formula_name, **bindings)
