# -*- coding: utf-8 -*-
"""阶段 26a 三锁：运行时注册表泛化 + make_vm 工厂收敛（src/kernel/exec_api.py）。

锁四面：
  A. 注册表泛化 —— unregister_backend / set_backend_enabled / backend_info /
     available_modes：自定义后端登记→执行→停用诚实拒绝→注销；主线名保留；
     主线（vm/native）不在注册表内、注销恒 False、不受启停面管辖；
  B. make_vm 工厂 —— 唯一 VM 构造入口：产物可执行、verbose 透传；
  C. 既有锁面不受扰动 —— test_plugin_contract 的可用模式描述锁定仍成立
     （本档只锁新增面，形状锁留在原档）；
  D. 停用后 run 诚实拒绝且 available_modes/runtimes 同步收缩。

注：注册表是进程级单例——自定义后端用 try/finally 注销清理，不污染门禁。
"""
from src.kernel import exec_api
from src.kernel.exec_api import (
    available_modes,
    backend_info,
    compile_module,
    make_vm,
    register_backend,
    run,
    set_backend_enabled,
    unregister_backend,
)
from src.mbc.vm import VM

import pytest


def _cleanup(name):
    unregister_backend(name)
    try:
        set_backend_enabled(name, True)
    except ValueError:
        pass


# ============================================================
# A. 注册表泛化
# ============================================================

class TestRegistryGeneralization:
    def test_register_run_unregister_roundtrip(self):
        calls = []

        def _backend(source):
            calls.append(source)
            return ["自定义后端:" + source]

        name = "测试后端_26a_roundtrip"
        register_backend(name, _backend, description="测试用自定义后端")
        try:
            assert name in available_modes()
            assert run("甲", mode=name) == ["自定义后端:甲"]
            assert calls == ["甲"]
            info = {e["mode"]: e for e in backend_info()}
            assert info[name]["description"] == "测试用自定义后端"
            assert info[name]["enabled"] is True
            assert info[name]["factory"].endswith("_backend")
        finally:
            assert unregister_backend(name) is True
        assert name not in available_modes()
        # 注销后执行诚实拒绝（不是静默回退主线）
        with pytest.raises(ValueError, match="未知执行后端"):
            run("甲", mode=name)
        # 再注销：主线名不在注册表内，恒 False
        assert unregister_backend(name) is False

    def test_reserved_mainline_names_rejected(self):
        for reserved in ("vm", "native"):
            with pytest.raises(ValueError, match="保留给核心主线"):
                register_backend(reserved, lambda s: [])
        assert unregister_backend("vm") is False
        assert unregister_backend("native") is False

    def test_disable_enable_honest_rejection(self):
        name = "测试后端_26a_toggle"

        def _backend(source):
            return [source]

        register_backend(name, _backend, description="启停面测试")
        try:
            set_backend_enabled(name, False)
            with pytest.raises(ValueError, match="已停用"):
                run("x", mode=name)
            # 停用后从可用面收缩
            assert name not in available_modes()
            # 停用态在 backend_info 中如实保留（enabled=False 可见）
            info = {e["mode"]: e for e in backend_info()}
            assert info[name]["enabled"] is False
            set_backend_enabled(name, True)
            assert name in available_modes()
            assert run("x", mode=name) == ["x"]
        finally:
            unregister_backend(name)

    def test_disable_unknown_mode_rejected(self):
        with pytest.raises(ValueError, match="未登记"):
            set_backend_enabled("从未登记的后端", False)

    def test_mainline_unaffected_by_registry_faces(self):
        # 主线 vm 不在注册表内：不受启停/注销面管辖，且始终可执行
        assert run("输出(6*7)", mode="vm") == [42]
        with pytest.raises(RuntimeError, match="build_exe"):
            run("x", mode="native")


# ============================================================
# B. make_vm 工厂
# ============================================================

class TestMakeVmFactory:
    def test_factory_produces_executable_vm(self):
        vm = make_vm(compile_module("输出(7)"))
        assert isinstance(vm, VM)
        assert vm.run() == [7]

    def test_factory_verbose_passthrough(self):
        vm = make_vm(compile_module("输出(1)"), verbose=True)
        assert isinstance(vm, VM)
        assert vm.run() == [1]

    def test_factory_matches_run_pipeline_shape(self):
        # run() 主线经 compile_module → make_vm → vm.run()，工厂产物与门面输出一致
        mod = compile_module("输出(41+1)")
        assert make_vm(mod).run() == run("输出(41+1)", mode="vm")


# ============================================================
# C. 主线描述面稳定（与 test_plugin_contract 互补的形状检查）
# ============================================================

class TestMainlineDescriptions:
    def test_mainline_entries_present_and_enabled(self):
        # 主线（vm/native）不在 _BACKENDS 注册表内——描述面在 available_modes
        modes = available_modes()
        assert "核心主线" in modes["vm"]
        # native 只产出 exe，描述必须诚实声明不可 run
        assert "exe" in modes["native"] and "不可" in modes["native"]

    def test_backend_info_lists_registered_only(self):
        # backend_info 只描述 _BACKENDS 注册表项；主线不在其中
        assert all(e["mode"] not in ("vm", "native") for e in backend_info())

    def test_available_modes_contains_vm_excludes_native_run(self):
        modes = available_modes()
        assert "vm" in modes
        # native 在登记面可见，但 run() 走 RuntimeError 诚实拒绝（不是 ValueError）
        assert "native" in modes
