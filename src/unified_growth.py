# -*- coding: utf-8 -*-
"""
Matha 增长/升级统一层（Unified Growth & Self-Upgrade）

合并：
  - growth.py: 原始增长系统（ExtensionRegistry, SelfDiagnostic, SelfModifier）
  - growth_engine.py: 生产级增长引擎 v1.2.18
  - matha_growth.py: 自成长系统 v2（递归内联、循环展开）
  - selfupgrade.py: 自我升级子系统（Probe, Sandbox, upgrade）
  - inner_loop.py: 闭环自改进系统

统一后：所有增长/升级功能通过 UnifiedGrowth 类访问。
"""
from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("matha.unified_growth")

# ── 懒导入各子系统 ──────────────────────────────────────────────────────────


def _get_growth_engine():
    from src.growth_engine import GrowthEngine
    return GrowthEngine


def _get_selfupgrade():
    from src.selfupgrade import Probe, Sandbox, UpgradeResult, upgrade
    return {"Probe": Probe, "Sandbox": Sandbox, "UpgradeResult": UpgradeResult, "upgrade": upgrade}


def _get_matha_growth():
    try:
        from src.matha_growth import MathaGrowth
        return MathaGrowth
    except ImportError:
        return None


def _get_inner_loop():
    try:
        from src.inner_loop import InnerLoop
        return InnerLoop
    except ImportError:
        return None


def _get_original_growth():
    try:
        from src.growth import ExtensionRegistry, SelfDiagnostic, SelfModifier
        return {"ExtensionRegistry": ExtensionRegistry, "SelfDiagnostic": SelfDiagnostic, "SelfModifier": SelfModifier}
    except ImportError:
        return None


def _get_formula_growth():
    try:
        from src.matha.growth import FormulaGrowthEngine
        from src.formula_system import FormulaRegistry
        return {"FormulaGrowthEngine": FormulaGrowthEngine, "FormulaRegistry": FormulaRegistry}
    except ImportError:
        return None


def _get_domain_formula():
    try:
        from src.domain_formula import DomainFormulaRegistry
        return {"DomainFormulaRegistry": DomainFormulaRegistry}
    except ImportError:
        return None


def _get_formula_compiler():
    try:
        from src.formula_compiler import FormulaCompiler, FormulaGrowthCompiler
        return {"FormulaCompiler": FormulaCompiler, "FormulaGrowthCompiler": FormulaGrowthCompiler}
    except ImportError:
        return None


# ── 统一增长/升级接口 ────────────────────────────────────────────────────────


class UnifiedGrowth:
    """统一增长与升级接口。

    整合：
      1. 探针/沙箱/升级（selfupgrade）
      2. 增长引擎（growth_engine）
      3. 自成长系统（matha_growth）
      4. 闭环自改进（inner_loop）
      5. 原始扩展注册（growth）
      6. 公式生长引擎（matha/growth）
      7. 领域公式注册（domain_formula）
      8. 公式编译器（formula_compiler）
    """

    def __init__(self, interp=None):
        self._interp = interp
        self._growth_engine = None
        self._su = None
        self._matha_growth = None
        self._inner_loop = None
        self._original = None
        self._formula_growth = None
        self._domain_formula = None
        self._formula_compiler = None

    def _ensure_initialized(self):
        if self._growth_engine is None:
            cls = _get_growth_engine()
            self._growth_engine = cls(self._interp) if self._interp else cls()
        if self._su is None:
            self._su = _get_selfupgrade()
        if self._matha_growth is None:
            cls = _get_matha_growth()
            self._matha_growth = cls(self._interp) if cls and self._interp else None
        if self._inner_loop is None:
            cls = _get_inner_loop()
            self._inner_loop = cls(self._interp) if cls and self._interp else None
        if self._original is None:
            self._original = _get_original_growth()
        if self._formula_growth is None:
            self._formula_growth = _get_formula_growth()
        if self._domain_formula is None:
            self._domain_formula = _get_domain_formula()
        if self._formula_compiler is None:
            self._formula_compiler = _get_formula_compiler()

    # ── 探针 ───────────────────────────────────────────────────────────────

    def probe(self) -> dict:
        """获取运行时探针数据。"""
        self._ensure_initialized()
        Probe = self._su["Probe"]
        if self._interp:
            return Probe(self._interp).state()
        return {}

    # ── 沙箱试运行 ─────────────────────────────────────────────────────────

    def sandbox_run(self, source: str) -> dict:
        """在沙箱中试运行 Matha 源码。"""
        self._ensure_initialized()
        Sandbox = self._su["Sandbox"]
        if self._interp:
            sb = Sandbox(self._interp)
            outputs, trace, err = sb.run(source)
            return {"outputs": outputs, "trace": trace, "error": err}
        return {"error": "需要 Interpreter 实例"}

    # ── 升级 ───────────────────────────────────────────────────────────────

    def upgrade(self, source: str, verify=None) -> dict:
        """沙箱试运行 → 校验 → 提交升级。"""
        self._ensure_initialized()
        upgrade_fn = self._su["upgrade"]
        if self._interp:
            result = upgrade_fn(self._interp, source, verify)
            return result.as_dict()
        return {"成功": False, "错误": "需要 Interpreter 实例"}

    # ── 增长引擎 ───────────────────────────────────────────────────────────

    def run_growth_pipeline(self, patch_code: str) -> bool:
        """运行增长管道。"""
        self._ensure_initialized()
        return self._growth_engine.run_upgrade_pipeline(patch_code)

    def get_growth_status(self) -> dict:
        """获取增长状态。"""
        self._ensure_initialized()
        return self._growth_engine.get_growth_stats()

    # ── 自成长 ─────────────────────────────────────────────────────────────

    def self_grow(self, source: str) -> dict:
        """自成长：自动优化和重构。"""
        self._ensure_initialized()
        if self._matha_growth:
            return self._matha_growth.grow(source)
        return {"success": False, "error": "matha_growth 不可用"}

    # ── 公式生长 ─────────────────────────────────────────────────────────────
    def formula_grow(self, op_type: str = "auto", **kwargs) -> dict:
        """公式生长：组合/推导/生成新公式。"""
        self._ensure_initialized()
        if not self._formula_growth:
            return {"success": False, "error": "公式成长引擎不可用"}
        try:
            FGE = self._formula_growth["FormulaGrowthEngine"]
            FR = self._formula_growth["FormulaRegistry"]
            reg = FR()
            # 注册领域公式
            from src.domain_formula import DomainFormulaRegistry
            domain_reg = DomainFormulaRegistry()
            domain_reg.register_all_domains()
            for name, f in domain_reg.registry._formulas.items():
                reg.register(f)

            engine = FGE(reg)
            if op_type == "auto":
                stats = engine.auto_grow(
                    max_combinations=kwargs.get("max_combinations", 5),
                    max_derivatives=kwargs.get("max_derivatives", 10),
                    generate_constraints=kwargs.get("generate_constraints"),
                )
                registered = engine.register_all_grown()
                return {"success": True, "stats": stats, "registered": registered}
            elif op_type == "compose":
                results = engine.compose(kwargs.get("names", []))
                return {"success": True, "results": [r.summary() for r in results]}
            elif op_type == "infer":
                results = engine.infer(
                    kwargs.get("formula_name", ""),
                    var=kwargs.get("var"),
                    elim_var=kwargs.get("elim_var"),
                )
                return {"success": True, "results": [r.summary() for r in results]}
            elif op_type == "generate":
                results = engine.generate(
                    kwargs.get("name", "新公式"),
                    kwargs.get("target", "F"),
                    kwargs.get("variables", ["x", "y"]),
                    constraints=kwargs.get("constraints"),
                )
                return {"success": True, "results": [r.summary() for r in results]}
            return {"success": False, "error": f"未知操作类型: {op_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def domain_formula_summary(self) -> dict:
        """获取领域公式总览。"""
        self._ensure_initialized()
        if not self._domain_formula:
            return {"error": "领域公式系统不可用"}
        try:
            reg = self._domain_formula["DomainFormulaRegistry"]()
            reg.register_all_domains()
            return {
                "loaded_domains": len(reg._loaded_domains),
                "total_formulas": len(reg.registry.list_formulas()),
                "summary": reg.summary(),
            }
        except Exception as e:
            return {"error": str(e)}

    def compile_formula(self, name: str, optimize: bool = True) -> dict:
        """编译单个公式为多语言代码。"""
        self._ensure_initialized()
        if not self._formula_compiler:
            return {"success": False, "error": "公式编译器不可用"}
        try:
            FC = self._formula_compiler["FormulaCompiler"]
            from src.formula_system import get_formula_registry
            reg = get_formula_registry()
            compiler = FC(reg)
            result = compiler.compile_formula(name, optimize)
            return {
                "success": result.success,
                "name": result.formula_name,
                "python": result.python_code,
                "c": result.c_code,
                "optimizations": result.optimizations,
                "error": result.error,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 闭环改进 ───────────────────────────────────────────────────────────

    def run_inner_loop(self, task: str, max_rounds: int = 3) -> dict:
        """运行闭环自改进循环。"""
        self._ensure_initialized()
        if self._inner_loop:
            return self._inner_loop.run(task, max_rounds)
        return {"success": False, "error": "inner_loop 不可用"}

    # ── 原始扩展注册 ───────────────────────────────────────────────────────

    def register_extension(self, name: str, func) -> bool:
        """注册扩展功能。"""
        self._ensure_initialized()
        if self._original and "ExtensionRegistry" in self._original:
            try:
                from src.growth import Extension
                registry = self._original["ExtensionRegistry"]()
                ext = Extension(
                    name=name, kind="generator", module="",
                    class_name="", description=f"Auto-registered: {name}",
                )
                registry.register(ext)
                return True
            except Exception:
                return False
        return False


# ── 单例 ────────────────────────────────────────────────────────────────────

_unified_growth: Optional[UnifiedGrowth] = None


def get_unified_growth(interp=None) -> UnifiedGrowth:
    global _unified_growth
    if _unified_growth is None or interp is not None:
        _unified_growth = UnifiedGrowth(interp)
    return _unified_growth


# ── 向后兼容导出 ────────────────────────────────────────────────────────────
__all__ = [
    "UnifiedGrowth",
    "get_unified_growth",
    # 子组件
    "Probe", "Sandbox", "UpgradeResult",
    "GrowthEngine", "MathaGrowth", "InnerLoop",
    # 公式生长
    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]

# 让常见导入路径仍然有效
try:
    from src.selfupgrade import Probe, Sandbox, UpgradeResult  # noqa: F401
    from src.growth_engine import GrowthEngine  # noqa: F401
    from src.matha.growth import FormulaGrowthEngine  # noqa: F401
    from src.domain_formula import DomainFormulaRegistry  # noqa: F401
    from src.formula_compiler import FormulaCompiler  # noqa: F401
except ImportError:
    pass
