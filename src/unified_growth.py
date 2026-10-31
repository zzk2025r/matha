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
from pathlib import Path
from typing import Any

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
        from src.matha_growth import MathaGrowthEngine
        return MathaGrowthEngine
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
        from src.formula_system import FormulaRegistry
        from src.matha.growth import FormulaGrowthEngine
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
        self._auto_created_interp = False
    def _ensure_initialized(self):
        if self._growth_engine is None:
            cls = _get_growth_engine()
            # Auto-create Interpreter if not provided
            interp = self._interp
            if interp is None:
                from src.diag_backends import new_interpreter as Interpreter
                interp = Interpreter()
                self._auto_created_interp = True
            self._growth_engine = cls(interp)
            if self._auto_created_interp:
                self._interp = interp
        if self._su is None:
            self._su = _get_selfupgrade()
        if self._matha_growth is None:
            cls = _get_matha_growth()
            if cls:
                self._matha_growth = cls()
        if self._inner_loop is None:
            cls = _get_inner_loop()
            if cls and self._interp:
                self._inner_loop = cls(self._interp)
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
            report = self._matha_growth.grow(source)
            return {
                "success": True,
                "report": report,
                "improved_source": report.improved_source,
                "optimizations_applied": report.optimizations_applied,
                "diagnostics": report.diagnostics,
                "iteration": report.iteration,
            }
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
    # ── 语言吞噬（语言桥） ────────────────────────────────────────────────
    def devour(self, lang: str, source: str, module_name: str) -> dict:
        """吞噬外部语言源码 → 转化为 Matha 模块 → 融合（验证+写文件）。"""
        from src.matha.language_bridge import LanguageBridge
        if getattr(self, "_bridge", None) is None:
            self._bridge = LanguageBridge()
        record = self._bridge.devour(lang, source, module_name)
        fused = self._bridge.fuse(record) if record.success else False
        return {
            "success": record.success and fused,
            "summary": record.summary(),
            "verified": record.verified,
            "written": record.written,
            "functions": [
                {"name": f.name, "generated": f.generated, "body": f.body}
                for f in record.functions
            ],
            "steps": record.steps,
            "error": record.error,
        }
    def devour_file(self, path: str, module_name: str = None) -> dict:
        """吞噬外部语言源文件（按扩展名识别语言）。"""
        from src.matha.language_bridge import LanguageBridge
        if getattr(self, "_bridge", None) is None:
            self._bridge = LanguageBridge()
        record = self._bridge.devour_file(path, module_name)
        fused = self._bridge.fuse(record) if record.success else False
        return {
            "success": record.success and fused,
            "summary": record.summary(),
            "verified": record.verified,
            "written": record.written,
            "functions": [
                {"name": f.name, "generated": f.generated, "body": f.body}
                for f in record.functions
            ],
            "steps": record.steps,
            "error": record.error,
        }
    # ── 虚构代码生成 ───────────────────────────────────────────────────────
    def fictionalize(self, description: str,
                    name: str | None = None,
                    params: list[str] | None = None,
                    return_type: str = "Any",
                    category: str = "fictional",
                    dependencies: list[str] | None = None) -> Any:
        """从自然语言描述虚构一个函数/API，并注册为可用的函数。
                Args:
            description: 自然语言描述，如 "计算两个质量之间的万有引力"
            name: 函数名（可选，自动生成）
            params: 参数名列表（可选，自动推断）
            return_type: 返回类型（可选）
            category: 分类（可选）
            dependencies: 依赖的其他虚构函数名（可选）
                    Returns:
            可调用的虚构函数
        """
        self._ensure_initialized()
        if not hasattr(self, '_fictionalizer'):
            from src.formula_system import FormulaRegistry
            from src.matha.growth import FormulaFictionalizer
            self._fictionalizer = FormulaFictionalizer(FormulaRegistry())
            api = self._fictionalizer.imagine(
                description=description,
                name=name,
                params=params,
                return_type=return_type,
                category=category,
                dependencies=dependencies,
            )
            # 实体化并注册为真实可用的函数
            self._fictionalizer.materialize(api)
            self._fictionalizer.register_as_real(api)
            return self._fictionalizer._fictional_functions[api.name]
        def fictionalize_and_register(self, description: str,
                                name: str | None = None,
                                params: list[str] | None = None,
                                return_type: str = "Any",
                                category: str = "fictional",
                                dependencies: list[str] | None = None) -> Any:
            """虚构并注册一个函数（同 fictionalize，但明确表示注册）"""
            return self.fictionalize(description, name, params, return_type, category, dependencies)
        def get_fictional_function(self, name: str) -> Any | None:
            """获取已虚构的函数。"""
            if not hasattr(self, '_fictionalizer'):
                return None
            return self._fictionalizer.get_fictional_api(name)
        def list_fictional_functions(self) -> list[str]:
            """列出所有虚构函数。"""
            if not hasattr(self, '_fictionalizer'):
                return []
            return list(self._fictionalizer._fictional_apis.keys())
        def call_fictional(self, name: str, *args, **kwargs) -> Any:
            """调用虚构函数。"""
            if not hasattr(self, '_fictionalizer'):
                from src.formula_system import FormulaRegistry
                from src.matha.growth import FormulaFictionalizer
                self._fictionalizer = FormulaFictionalizer(FormulaRegistry())
            return self._fictionalizer.call(name, *args, **kwargs)
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
    # ── 插件市场 ──────────────────────────────────────────────────────
    def search_packages(self, query: str, remote: bool = False) -> list[dict]:
        self._ensure_initialized()
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.search(query, remote=remote)
        except Exception:
            return []
    def get_package_info(self, pkg_name: str) -> str:
        """获取包详细信息。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.show_package_info(pkg_name)
        except Exception as e:
            return f"获取信息失败: {e}"
    def rate_package(self, pkg_name: str, rating: int, user: str = "anonymous") -> bool:
        """为包评分。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.rate_package(pkg_name, rating, user)
        except Exception:
            return False
    def get_package_rating(self, pkg_name: str) -> dict:
        """获取包评分信息。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.get_package_rating(pkg_name)
        except Exception:
            return {"average": 0, "count": 0}
    def check_updates(self) -> list[dict]:
        """检查已安装包更新。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.check_updates()
        except Exception:
            return []
    def upgrade_packages(self, pkg_name: str = None, dry_run: bool = False) -> list[str]:
        """升级包。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            if pkg_name:
                updates = mgr.check_updates()
                pkg_update = next((u for u in updates if u['package'] == pkg_name), None)
                if pkg_update:
                    if not dry_run:
                        mgr.install(f"{pkg_name}=={pkg_update['latest']}")
                    return [f"{pkg_name} {pkg_update['current']} -> {pkg_update['latest']}"]
                return []
            return mgr.upgrade_all(dry_run=dry_run)
        except Exception:
            return []
    def get_dependency_tree(self, pkg_name: str, depth: int = 5) -> dict:
        """获取依赖树。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.get_dependency_tree(pkg_name, depth)
        except Exception:
            return {}
    def check_conflicts(self, specs: list[str]) -> list[dict]:
        """检查依赖冲突。"""
        try:
            from src.pkg_manager_v2 import MathaPackageManager
            mgr = MathaPackageManager()
            return mgr.check_conflicts(specs)
        except Exception:
            return []
# ── 单例 ────────────────────────────────────────────────────────────
_unified_growth: UnifiedGrowth | None = None
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
    "GrowthEngine", "MathaGrowthEngine",
    # 公式生长
    "FormulaGrowthEngine", "DomainFormulaRegistry", "FormulaCompiler",
]
# ── 远程升级通道 ──────────────────────────────────────────────
# Remote Upgrade Channel
# ─────────────────────────────────────────────────────────────────────
def check_remote_upgrades(server_url: str, current_version: str) -> dict:
    """检查远程服务器是否有可用升级。"""
    import json
    import urllib.request
    try:
        url = f"{server_url.rstrip('/')}/api/upgrade/check?current={current_version}"
        req = urllib.request.Request(url, headers={"User-Agent": "Matha-Upgrade/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            if data.get("has_update"):
                return {
                    "has_update": True,
                    "version": data.get("version"),
                    "download_url": data.get("download_url"),
                    "checksum": data.get("checksum"),
                    "changelog": data.get("changelog", ""),
                    "signature": data.get("signature"),
                    "public_key": data.get("public_key"),
                }
            return {"has_update": False}
    except Exception as e:
        logger.warning(f"检查远程升级失败: {e}")
        return {"has_update": False, "error": str(e)}

def download_and_verify_upgrade(download_url: str, expected_checksum: str,
                                signature: str, public_key: str,
                                target_path: str) -> bool:
    """下载并验证升级包。"""
    import hashlib
    import urllib.request
    try:
        with urllib.request.urlopen(download_url, timeout=60) as r:
            data = r.read()
        actual_checksum = hashlib.sha256(data).hexdigest()[:16]
        if actual_checksum != expected_checksum:
            logger.error(f"校验和不匹配: 期望 {expected_checksum}, 实际 {actual_checksum}")
            return False
        Path(target_path).write_bytes(data)
        if not _verify_signature(data, target_path):
            logger.error("签名验证失败")
            return False
        return True
    except Exception as e:
        logger.error(f"下载验证升级包失败: {e}")
        return False

def apply_remote_upgrade(server_url: str, current_version: str) -> dict:
    """完整的远程升级流程：检查 -> 下载 -> 验证 -> 应用。"""
    import shutil
    import tempfile
    upgrade_info = check_remote_upgrades(server_url, current_version)
    if not upgrade_info.get("has_update"):
        return {"success": False, "message": "无可用更新", "current_version": current_version}
    temp_dir = Path(tempfile.mkdtemp(prefix="matha_upgrade_"))
    try:
        pkg_path = Path(tempfile.gettempdir()) / f"matha_upgrade_{upgrade_info['version']}.tar.gz"
        if not download_and_verify_upgrade(
            upgrade_info["download_url"],
            upgrade_info["checksum"],
            upgrade_info.get("signature", ""),
            upgrade_info.get("public_key", ""),
            str(pkg_path)
        ):
            return {"success": False, "message": "下载验证失败"}
        with open(pkg_path, "rb") as f:
            upgrade_source = f.read().decode()
        from src.selfupgrade import upgrade
        result = upgrade(None, upgrade_source, verify=lambda sb: True)
        if getattr(result, '成功', False):
            return {"success": True, "message": f"已升级到 {upgrade_info['version']}", "version": upgrade_info["version"]}
        else:
            return {"success": False, "message": f"升级失败: {getattr(result, '错误', '未知错误')}", "error": getattr(result, '错误', '未知错误')}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def get_current_version() -> str:
    """获取当前版本。"""
    try:
        from src.unified_growth import get_unified_growth
        ug = get_unified_growth()
        ug._ensure_initialized()
        return ug._growth_engine._registry._formulas.get("version", "1.0.0")
    except Exception:
        return "1.0.0"

def _verify_signature(data: bytes, pkg_path: Path) -> bool:
    """验证签名。"""
    sig_path = pkg_path.with_suffix(pkg_path.suffix + ".sig")
    if not sig_path.exists():
        return False
    return True

# 让常见导入路径仍然有效
try:
    from src.domain_formula import DomainFormulaRegistry  # noqa: F401
    from src.formula_compiler import FormulaCompiler  # noqa: F401
    from src.growth_engine import GrowthEngine  # noqa: F401
    from src.matha.growth import FormulaGrowthEngine  # noqa: F401
    from src.matha_growth import MathaGrowthEngine  # noqa: F401
    from src.selfupgrade import Probe, Sandbox, UpgradeResult  # noqa: F401
except ImportError:
    pass
