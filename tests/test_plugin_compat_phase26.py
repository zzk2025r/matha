# -*- coding: utf-8 -*-
"""阶段 26c 三锁：插件兼容/冲突/汇总面（src/plugin_api.py PluginResolver）。

锁四面：
  A. requires 依赖校验 —— 缺失依赖注册诚实拒绝（_rejected 记录 + ERROR 诊断，
     绝不静默跳过）；依赖满足后注册成功且 _rejected 撤销；from_spec 解析
     requires（str 归一 tuple）；
  B. 事后依赖缺失 —— 已注册插件的依赖被注销（ext 停用面）后，report()
     依赖缺失 如实报告，不自动注销；
  C. 冲突面 —— conflicts() 列出被 2+ 插件声明（可加载）的符号与属主序列；
     取值语义维持清单最后声明者覆盖；
  D. 汇总报告 + 零扰动 —— report() 八键形状；真实注册表 89 插件零被拒、
     零事后缺失、冲突面非空且含已知对（梁_弯曲正应力）；plugin_usage()
     覆盖全清单。

注：测试用独立 PluginResolver（tmp 清单路径），不污染真实注册表。
"""
import pytest

from src.plugin_api import (
    LegacyModulePlugin,
    LEVEL_ERROR,
    PluginDiagnostic,
    PluginResolver,
)


def _plugin(name, symbols=(), requires=(), **kw):
    return LegacyModulePlugin(
        name=name, module=f"tests.fake_modules.{name}",
        symbols=tuple(symbols), requires=tuple(requires), **kw)


# ============================================================
# A. requires 依赖校验
# ============================================================

class TestRequiresValidation:
    def test_missing_dependency_honest_rejection(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")  # 空注册表
        r.register(_plugin("孤儿插件", symbols=("甲符号",), requires=("不存在",)))
        # 不静默跳过：注册被拒有记录、有 ERROR 诊断
        assert "孤儿插件" not in r._plugins
        assert r.report()["注册被拒"] == {"孤儿插件": {"缺少依赖": ["不存在"]}}
        diags = [d for d in r.diagnostics() if isinstance(d, PluginDiagnostic)]
        assert any(d.level == LEVEL_ERROR and "注册被拒" in d.message
                   and "孤儿插件" in d.message for d in diags)

    def test_satisfied_dependency_registers(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        base = _plugin("基础插件", symbols=("乙符号",))
        dependent = _plugin("依赖插件", symbols=("丙符号",), requires=("基础插件",))
        r.register(base)
        r.register(dependent)
        assert "依赖插件" in r._plugins
        assert r.report()["注册被拒"] == {}

    def test_rejected_record_cleared_on_success(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        dependent = _plugin("后补插件", requires=("基础插件",))
        r.register(dependent)  # 此时缺依赖 → 拒
        assert r.report()["注册被拒"]
        r.register(_plugin("基础插件"))
        # 依赖满足后重新注册同一插件 → 成功且被拒记录撤销
        r.register(dependent)
        assert "后补插件" in r._plugins
        assert r.report()["注册被拒"] == {}

    def test_from_spec_requires_parsing(self):
        p = LegacyModulePlugin.from_spec(
            {"name": "甲", "module": "m.x", "requires": "单依赖"})
        assert p.requires == ("单依赖",)
        p2 = LegacyModulePlugin.from_spec(
            {"name": "乙", "module": "m.y", "requires": ["a", "b"]})
        assert p2.requires == ("a", "b")
        p3 = LegacyModulePlugin.from_spec({"name": "丙", "module": "m.z"})
        assert p3.requires == ()

    def test_dependency_must_precede_in_order(self, tmp_path):
        # 清单顺序内依赖在前：先注册依赖方再注册使用方（同清单语义）
        r = PluginResolver(tmp_path / "absent.json")
        dependent = _plugin("逆序插件", requires=("晚注册的基础",))
        base = _plugin("晚注册的基础")
        r.register(dependent)
        r.register(base)  # 顺序错误：注册时校验，逆序被拒
        assert "逆序插件" not in r._plugins


# ============================================================
# B. 事后依赖缺失
# ============================================================

class TestPostHocMissingDeps:
    def test_unregister_dependency_reported_not_autoprune(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        r.register(_plugin("地基", symbols=("地基符号",)))
        r.register(_plugin("上层", requires=("地基",)))
        assert r.report()["依赖缺失"] == {}
        assert r.unregister("地基") is True
        # 上层不自动注销，依赖缺失如实报告
        assert "上层" in r._plugins
        assert r.report()["依赖缺失"] == {"上层": ["地基"]}

    def test_unregister_unknown_plugin_false(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        assert r.unregister("从未注册") is False


# ============================================================
# C. 冲突面
# ============================================================

class TestConflicts:
    def test_multi_owner_symbol_reported(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        r.register(_plugin("甲域", symbols=("共享符号", "甲独有")))
        r.register(_plugin("乙域", symbols=("共享符号", "乙独有")))
        conflicts = {c["symbol"]: c["owners"] for c in r.conflicts()}
        assert conflicts["共享符号"] == ["甲域", "乙域"]
        assert "甲独有" not in conflicts and "乙独有" not in conflicts

    def test_last_owner_wins_semantics_preserved(self, tmp_path):
        # 报告只列冲突；解析语义维持清单最后声明者覆盖（owners[-1]）
        r = PluginResolver(tmp_path / "absent.json")
        r.register(_plugin("甲域", symbols=("同一符号",)))
        r.register(_plugin("乙域", symbols=("同一符号",)))
        owners = r.owners_of("同一符号") if hasattr(r, "owners_of") else None
        if owners is not None:
            assert owners[-1] == "乙域"
        conflicts = {c["symbol"]: c["owners"] for c in r.conflicts()}
        assert conflicts["同一符号"][-1] == "乙域"

    def test_unregister_removes_conflict(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        r.register(_plugin("甲域", symbols=("会消失的冲突",)))
        r.register(_plugin("乙域", symbols=("会消失的冲突",)))
        assert any(c["symbol"] == "会消失的冲突" for c in r.conflicts())
        r.unregister("乙域")
        assert not any(c["symbol"] == "会消失的冲突" for c in r.conflicts())


# ============================================================
# D. 汇总报告 + 真实注册表零扰动
# ============================================================

REPORT_KEYS = {"插件总数", "已加载", "符号总数", "可加载符号", "冲突",
               "注册被拒", "依赖缺失", "诊断数"}


class TestReportAndRealRegistry:
    def test_report_shape(self, tmp_path):
        r = PluginResolver(tmp_path / "absent.json")
        r.register(_plugin("甲域", symbols=("符一",)))
        report = r.report()
        assert REPORT_KEYS <= set(report)
        assert report["插件总数"] == 1
        assert report["符号总数"] == 1
        assert report["可加载符号"] == 1

    def test_real_registry_zero_disturbance(self):
        # 新鲜构造（同一真实清单）：不耦合全局注册表——扩展启停等生命周期
        # 测试会正当改动全局态，健康锁以清单单源为准。
        report = PluginResolver().report()
        assert REPORT_KEYS <= set(report)
        # 全清单注册面零被拒、零事后缺失（既有 88 域 + ai_framework 均兼容）
        assert report["注册被拒"] == {}
        assert report["依赖缺失"] == {}
        assert report["插件总数"] >= 89

    def test_real_registry_known_conflict_pair(self):
        conflicts = {c["symbol"]: c["owners"] for c in PluginResolver().conflicts()}
        # 清单顺序沿袭旧 eager 注册序——结构/内核类覆盖对是长期稳定冲突面
        assert conflicts.get("梁_弯曲正应力") == ["mechanics", "structural"]
        assert conflicts.get("c_光速") == ["optics", "celestial"]
        assert len(conflicts) >= 30

    def test_plugin_usage_covers_full_manifest(self):
        usage = PluginResolver().plugin_usage()
        assert len(usage) >= 89
        for entry in usage[:3]:
            assert {"名", "已加载", "物化时刻"} <= set(entry)
