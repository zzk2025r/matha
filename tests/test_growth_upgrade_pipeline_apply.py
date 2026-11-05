# -*- coding: utf-8 -*-
"""成长系统·升级管道真实应用锁（Tier 2·A1）。

坐实 `GrowthEngine.run_upgrade_pipeline` 不再是「`_apply_patch` 恒模拟成功」的 phantom：
  ① 无显式目标 → 诚实拒绝（False），history 如实标 applied=False（绝不谎称已应用）；
  ② 合法补丁 + 显式目标 → **确实改写目标文件**，history 记 applied/verified/success 皆 True
     且含 hash_before/after（完整性审计）；
  ③ 语法错误补丁 → **写前拒绝**，原文件字节保持不变（异常熔断·禁止强制应用）；
  ④ verify_fn 判假 → 写入后**按快照回滚到原文**，history.rolled_back=True；
  ⑤ 内核纯净度闸门：目标落在 `src/` 树内 → 拒绝且文件不被创建；
  ⑥ 新建文件（原不存在）成功后无参 `_rollback_patch()` 删除之（inner_loop 依赖无参签名）；
  ⑦ 委派契约不破：`_apply_patch` 透传管道、返回值仍为 bool。

全程离线、毫秒级、只在 pytest `tmp_path` 受控临时目录内写文件、绝不触碰仓库/内核文件、
不污染进程级单例（每测新建独立 GrowthEngine）。
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def eng():
    from src.growth_engine import GrowthEngine
    return GrowthEngine(assistant=None)


class TestHonestNoTarget:
    def test_no_target_returns_false(self, eng):
        assert eng.run_upgrade_pipeline("x = 1\n") is False

    def test_no_target_records_applied_false(self, eng):
        eng.run_upgrade_pipeline("x = 1\n")
        last = eng._upgrade_history[-1]
        assert last["applied"] is False and last["success"] is False

    def test_no_target_does_not_fabricate_success(self, eng):
        # 关键回归：旧 phantom 对任意字符串恒 True。
        for junk in ["print('hi')", "@@@乱码@@", "def f(:"]:
            assert eng.run_upgrade_pipeline(junk) is False


class TestRealApplication:
    def test_valid_patch_actually_writes(self, eng, tmp_path):
        t = tmp_path / "mod.py"
        t.write_text("ORIGINAL = 1\n", encoding="utf-8")
        assert eng.run_upgrade_pipeline("PATCHED = 2\n", target_path=str(t)) is True
        assert "PATCHED" in t.read_text(encoding="utf-8")

    def test_history_full_success_audit(self, eng, tmp_path):
        t = tmp_path / "a.py"
        t.write_text("x = 1\n", encoding="utf-8")
        eng.run_upgrade_pipeline("y = 2\n", target_path=str(t))
        h = eng._upgrade_history[-1]
        assert h["applied"] is True and h["verified"] is True and h["success"] is True
        assert h["hash_before"] and h["hash_after"]
        assert h["hash_before"] != h["hash_after"]

    def test_new_file_created(self, eng, tmp_path):
        t = tmp_path / "new.py"
        assert eng.run_upgrade_pipeline("CREATED = 1\n", target_path=str(t)) is True
        assert t.exists() and "CREATED" in t.read_text(encoding="utf-8")


class TestIntegrityPreCheck:
    def test_syntax_error_patch_refused_before_write(self, eng, tmp_path):
        t = tmp_path / "keep.py"
        t.write_text("KEEP = 1\n", encoding="utf-8")
        assert eng.run_upgrade_pipeline("def broken(:\n", target_path=str(t)) is False
        # 原文件字节分毫未动（写前熔断）
        assert t.read_text(encoding="utf-8") == "KEEP = 1\n"

    def test_syntax_error_history_not_applied(self, eng, tmp_path):
        t = tmp_path / "keep.py"
        t.write_text("KEEP = 1\n", encoding="utf-8")
        eng.run_upgrade_pipeline("def broken(:\n", target_path=str(t))
        assert eng._upgrade_history[-1]["applied"] is False


class TestRollbackOnVerifyFail:
    def test_verify_false_rolls_back_original(self, eng, tmp_path):
        t = tmp_path / "roll.py"
        t.write_text("BEFORE = 1\n", encoding="utf-8")
        assert eng.run_upgrade_pipeline("AFTER = 2\n", verify_fn=lambda c: False,
                                        target_path=str(t)) is False
        assert t.read_text(encoding="utf-8") == "BEFORE = 1\n"

    def test_verify_false_records_rolled_back(self, eng, tmp_path):
        t = tmp_path / "roll.py"
        t.write_text("BEFORE = 1\n", encoding="utf-8")
        eng.run_upgrade_pipeline("AFTER = 2\n", verify_fn=lambda c: False, target_path=str(t))
        h = eng._upgrade_history[-1]
        assert h["applied"] is True and h["verified"] is False and h["rolled_back"] is True

    def test_verify_raise_treated_as_fail_and_rolls_back(self, eng, tmp_path):
        t = tmp_path / "roll.py"
        t.write_text("BEFORE = 1\n", encoding="utf-8")

        def boom(_c):
            raise RuntimeError("校验炸")

        assert eng.run_upgrade_pipeline("AFTER = 2\n", verify_fn=boom, target_path=str(t)) is False
        assert t.read_text(encoding="utf-8") == "BEFORE = 1\n"


class TestKernelPurityGuard:
    def test_refuse_target_inside_src(self, eng):
        from pathlib import Path
        inside = Path(__file__).resolve().parents[1] / "src" / "_a1_never_written.py"
        assert eng.run_upgrade_pipeline("x = 1\n", target_path=str(inside)) is False
        assert not inside.exists()  # 内核/源码树未被创建/污染

    def test_refuse_directory_target(self, eng, tmp_path):
        assert eng.run_upgrade_pipeline("x = 1\n", target_path=str(tmp_path)) is False


class TestRollbackHelperContract:
    def test_noarg_rollback_removes_created_file(self, eng, tmp_path):
        t = tmp_path / "gone.py"
        assert eng.run_upgrade_pipeline("CREATED = 1\n", target_path=str(t)) is True
        eng._rollback_patch()  # 无参签名（inner_loop.self_upgrade_rollback 依赖）
        assert not t.exists()

    def test_noarg_rollback_restores_original(self, eng, tmp_path):
        t = tmp_path / "back.py"
        t.write_text("ORIG = 1\n", encoding="utf-8")
        eng.run_upgrade_pipeline("NEW = 2\n", target_path=str(t))
        eng._rollback_patch()
        assert t.read_text(encoding="utf-8") == "ORIG = 1\n"

    def test_rollback_with_no_snapshot_is_safe(self, eng):
        eng._rollback_patch()  # 无可回滚快照 → 不抛


class TestDelegationContract:
    def test_apply_patch_no_target_false(self, eng):
        assert eng._apply_patch("x = 1\n") is False

    def test_apply_patch_with_target_applies(self, eng, tmp_path):
        t = tmp_path / "d.py"
        t.write_text("a = 1\n", encoding="utf-8")
        assert eng._apply_patch("b = 2\n", target_path=str(t)) is True
        assert "b = 2" in t.read_text(encoding="utf-8")

    def test_return_is_bool(self, eng, tmp_path):
        t = tmp_path / "b.py"
        t.write_text("a = 1\n", encoding="utf-8")
        assert isinstance(eng.run_upgrade_pipeline("c = 3\n", target_path=str(t)), bool)
        assert isinstance(eng.run_upgrade_pipeline("c = 3\n"), bool)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
