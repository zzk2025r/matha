# -*- coding: utf-8 -*-
"""阶段 6f-B · UnifiedGrowth 包装真实委派覆盖审计 + 门禁归属证据。

【B1 门禁归属（证据，非迁移）】
`make check` → `scripts/check.py` 的 `tests` 项命令为：
    pytest -q -p no:cacheprovider --tb=line tests \
        --ignore=tests/test_kernel_purity.py --ignore=tests/test_ast_vm_gap.py
即对**整个 tests/ 目录**跑 pytest，故本目录内所有 pytest 风格成长锁
（test_unified_layers.py / test_growth_subsystems_lock.py / test_growth_loop_e2e.py / 本文件）
都已在 `make check` 门禁内。注：run_all.py 与 CI 用 `unittest discover`，只收 TestCase 类、
收不到这些 pytest 风格锁——这是"证实已由 make check 纳入"，而非"需迁就 unittest"。

【B4 覆盖审计（完整性守卫）】
下表把 UnifiedGrowth 每个公开包装方法映射到其**委派目标子系统**与**证明真实委派的锁落点**。
`test_all_public_wrappers_are_audited` 断言实际公开方法集 == 审计表集：任何人新增/改名公开
包装而未在此登记（并补对应委派锁），本锁即失败——把"6e 各包装只测 fallback、真实委派漏网"
这一类缺陷，升级为门禁级完整性约束。

纪律（遵 KNOWN_ISSUES §7c）：审计表只登记**接线落点**，不背书任何子系统输出正确性。
本文件为纯 introspection，离线、瞬时、无副作用、不触网、不写文件。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.unified_growth import UnifiedGrowth

# method -> (委派目标, 真实委派锁落点)
AUDIT = {
    "probe":                   ("selfupgrade.Probe", "test_unified_layers / test_growth_subsystems_lock"),
    "sandbox_run":             ("selfupgrade.Sandbox", "test_unified_layers / test_growth_subsystems_lock"),
    "upgrade":                 ("selfupgrade.upgrade", "test_unified_layers / test_growth_subsystems_lock"),
    "run_growth_pipeline":     ("growth_engine.run_upgrade_pipeline", "test_growth_loop_e2e::TestRealDelegationStrengthening (B2 桩透传)"),
    "get_growth_status":       ("growth_engine.get_growth_stats", "test_growth_loop_e2e::TestRealDelegationStrengthening (B2 桩透传)"),
    "self_grow":               ("matha_growth.MathaGrowthEngine.grow", "test_growth_subsystems_lock::TestGrowthWrapperHandoff / test_growth_loop_e2e (B3 schema)"),
    "formula_grow":            ("formula_growth.FormulaGrowthEngine", "test_unified_layers / test_growth_loop_e2e"),
    "domain_formula_summary":  ("domain_formula.DomainFormulaRegistry", "test_growth_loop_e2e (chain + degrade)"),
    "compile_formula":         ("formula_compiler", "test_unified_layers::TestUnifiedGrowthWrapperLocks"),
    "run_inner_loop":          ("inner_loop.MathaInnerLoop.run", "test_growth_loop_e2e (chain + degrade)"),
    "devour":                  ("language_bridge.LanguageBridge.devour", "test_unified_layers"),
    "devour_file":             ("language_bridge.LanguageBridge (record→dict)", "test_unified_layers::TestUnifiedGrowthWrapperLocks (桩映射)"),
    "fictionalize":            ("(幽灵导入 → 诚实拒绝)", "test_unified_layers"),
    "register_extension":      ("growth.ExtensionRegistry (持久化)", "test_growth_subsystems_lock::TestGrowthWrapperHandoff (B 修复)"),
    "list_extensions":         ("growth registry 查询", "test_growth_subsystems_lock (B 修复可查)"),
    "get_extension_callable":  ("实例保留的 callables", "test_growth_subsystems_lock (B 修复可查)"),
    "search_packages":         ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "get_package_info":        ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "rate_package":            ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "get_package_rating":      ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "check_updates":           ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "upgrade_packages":        ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "get_dependency_tree":     ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
    "check_conflicts":         ("pkg 市场", "test_unified_layers::test_market_wrappers_honest_types"),
}


def _public_methods():
    return {m for m in dir(UnifiedGrowth)
            if not m.startswith("_") and callable(getattr(UnifiedGrowth, m))}


class TestWrapperDelegationAudit:
    def test_all_public_wrappers_are_audited(self):
        """完整性守卫：实际公开方法集必须与审计表逐一对应。"""
        actual = _public_methods()
        audited = set(AUDIT)
        assert actual == audited, (
            f"公开包装与审计表漂移：未登记 {sorted(actual - audited)}；"
            f"已失效条目 {sorted(audited - actual)}")

    def test_every_audited_wrapper_is_callable(self):
        for name in AUDIT:
            assert callable(getattr(UnifiedGrowth, name)), name

    def test_audit_has_two_layers_per_entry(self):
        """每条审计须同时给出委派目标与锁落点（防空表）。"""
        for name, (delegate, lock) in AUDIT.items():
            assert delegate and lock, name

    def test_lazy_import_factories_wired(self):
        """懒导入接线工厂齐备（缺失则相应子系统不可达 = 6e phantom 温床）。"""
        import src.unified_growth as ug
        for factory in ("_get_selfupgrade", "_get_matha_growth", "_get_inner_loop",
                        "_get_original_growth", "_get_formula_growth",
                        "_get_domain_formula", "_get_formula_compiler"):
            assert callable(getattr(ug, factory)), factory
