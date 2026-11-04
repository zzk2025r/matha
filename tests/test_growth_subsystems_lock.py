# -*- coding: utf-8 -*-
"""阶段 6f-D · selfupgrade / growth 子系统真实 API 面接线锁。

背景：6e 反复出现的 phantom 缺陷同族 =「包装↔子系统接线错配」（构造参数 / 名字当对象 /
幽灵导入 / 不存在属性 / 内部委派未接线），皆因这些面**只测 fallback、未跑真实路径**。
6f-D 对 `src/selfupgrade.py`、`src/growth.py` 两个**此前零直接测试**的子系统面做真实
离线冒烟，把「接线正确 + 诚实降级 + 绝不裸抛 + schema 稳定」固化成回归锁。

纪律（遵 KNOWN_ISSUES §7c）：只锁编排/接线/契约与诚实降级，**不背书**优化器/执行的输出
正确性（故不断言 Sandbox 执行结果数值、不断言 matha_growth 改写后的源码质量），只断言
接口形态、错误如实下沉、类型闭合。全离线、毫秒级、不写仓库文件。

`matha_growth.MathaGrowthEngine.grow` 已由 tests/test_matha_growth_engine.py 覆盖，本文件
只补其经 UnifiedGrowth.self_grow 的**四属性交接契约**（防属性改名把包装打回 phantom）。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.diag_backends import new_interpreter as Interpreter

VALID = "func 加(x, y) -> Int = (x, y) => x + y\n"
BAD = "func 坏(x -> Int = ===\n"          # 语法错误源码 → 应被如实报为 err，不裸抛


# ============================================================
# selfupgrade：Probe / Sandbox / upgrade
# ============================================================

class TestSelfUpgradeContract:
    def test_probe_state_schema(self):
        from src.selfupgrade import Probe
        st = Probe(Interpreter()).state()
        assert isinstance(st, dict)
        assert {"变量", "函数", "内建"} <= set(st), f"Probe.state schema 漂移：{set(st)}"
        assert isinstance(st["内建"], list)

    def test_probe_func_names_reflect_registered(self):
        from src.selfupgrade import Probe
        it = Interpreter()
        it.run(__import__("src.parser", fromlist=["parse"]).parse(VALID))
        assert "加" in Probe(it).func_names()

    def test_sandbox_run_valid_no_error(self):
        from src.selfupgrade import Sandbox
        outputs, trace, err = Sandbox(Interpreter()).run(VALID)
        assert isinstance(outputs, list) and isinstance(trace, list)
        assert err is None                      # 合法源码不应有错误

    def test_sandbox_run_bad_honest_error_not_raise(self):
        from src.selfupgrade import Sandbox
        outputs, trace, err = Sandbox(Interpreter()).run(BAD)  # 绝不裸抛
        assert isinstance(err, str) and err      # 错误如实下沉为字符串

    def test_upgrade_success_dict_schema(self):
        from src.selfupgrade import upgrade
        d = upgrade(Interpreter(), VALID).as_dict()
        assert {"成功", "错误", "输出", "变更"} <= set(d)
        assert d["成功"] is True and d["错误"] is None

    def test_upgrade_failure_honest_not_raise(self):
        from src.selfupgrade import upgrade
        d = upgrade(Interpreter(), BAD).as_dict()   # 绝不裸抛
        assert d["成功"] is False and isinstance(d["错误"], str) and d["错误"]

    def test_upgrade_verify_false_rolls_back(self):
        from src.selfupgrade import upgrade, Probe
        it = Interpreter()
        d = upgrade(it, VALID, verify=lambda sb: False).as_dict()
        assert d["成功"] is False and "校验" in d["错误"]
        assert "加" not in Probe(it).func_names()   # 校验未过 → 本体未被污染


# ============================================================
# growth（原始）：ExtensionRegistry / Self* / GrowthLoop
# ============================================================

class TestOriginalGrowthContract:
    def test_extension_registry_roundtrip(self):
        from src.growth import ExtensionRegistry, Extension
        reg = ExtensionRegistry()
        ext = Extension(name="e1", kind="generator", module="", class_name="", description="d")
        reg.register(ext)
        assert reg.get("e1") is ext
        listed = reg.list_extensions()
        assert any(e["name"] == "e1" and e["kind"] == "generator" for e in listed)
        assert reg.unregister("e1") is True and reg.get("e1") is None

    def test_self_diagnostic_returns_list_and_summary(self):
        from src.growth import ExtensionRegistry, SelfDiagnostic
        diag = SelfDiagnostic(ExtensionRegistry())
        assert isinstance(diag.diagnose(VALID), list)     # 不裸抛
        assert isinstance(diag.get_summary(), dict)

    def test_self_modifier_stats(self):
        from src.growth import ExtensionRegistry, SelfDiagnostic, SelfModifier
        reg = ExtensionRegistry()
        mod = SelfModifier(reg, SelfDiagnostic(reg))
        stats = mod.get_stats()
        assert isinstance(stats, dict) and stats            # 非空统计 dict

    def test_growth_loop_run_yields_state(self):
        from src.growth import create_growth_system
        loop = create_growth_system()
        out = loop.run(VALID, max_iterations=1)             # 不裸抛
        assert isinstance(out, dict) and "state" in out
        assert isinstance(loop.get_state(), dict)


# ============================================================
# UnifiedGrowth → matha_growth 四属性交接契约（防包装打回 phantom）
# ============================================================

class TestGrowthWrapperHandoff:
    def test_self_grow_carries_report_attrs(self):
        from src.unified_growth import UnifiedGrowth
        from src.matha_growth import GrowthReport
        r = UnifiedGrowth().self_grow(VALID)
        assert isinstance(r, dict)
        if r.get("success"):                               # matha_growth 可用时
            rep = r["report"]
            assert isinstance(rep, GrowthReport)
            # self_grow 直接读取这四个属性；任一被改名即回归 phantom
            for attr in ("improved_source", "optimizations_applied", "diagnostics", "iteration"):
                assert hasattr(rep, attr)
            assert r["iteration"] == rep.iteration
        else:
            assert "error" in r                            # 不可用时须诚实报告

    def test_register_extension_persistent_and_queryable(self):
        """6f-D B 修复：注册表持久化、可查，func 不再被丢弃（旧缺陷每次新建即弃）。"""
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        fn = lambda: 42
        assert ug.register_extension("myext", fn) is True
        listed = ug.list_extensions()
        assert any(e["name"] == "myext" and e["kind"] == "generator" for e in listed), \
            f"注册后应可查，实得 {listed}"
        assert ug.get_extension_callable("myext") is fn   # func 如实保留、可取回
        assert ug.get_extension_callable("__absent__") is None

    def test_list_extensions_empty_before_register(self):
        from src.unified_growth import UnifiedGrowth
        assert UnifiedGrowth().list_extensions() == []
