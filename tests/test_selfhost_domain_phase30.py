# -*- coding: utf-8 -*-
"""阶段 30e Track A：域插件符号面注入锁（boot 注册内建注入 + 双面对拍）。

30e 拍板（驱动器级注入）：Track B 判据 = 同一内建面下 boot 解释器 ≡ 宿主
解释器。宿主面内建表 = 真实 Interpreter 实例 builtins 表（内核 + 懒内核节 +
_DOMAIN_BUILTINS + 解析器全导出清单），经 28d VM.register_builtin 端口 +
env 绑定注入 boot 面（真实现非桩；多参经 _adapt_callable 逐参收集链）。
资源库面（资源_加载/资源_成长）由驱动器按语料 AST 预执行同名资源到 boot env
（preload_resources——boot 解释器真执行资源源码 + grow 链 get_entry 预执行）。

锁面：
  ① type_of 链判据关键名：注入不得覆盖 VM globals 上的 type_of（链代码
     应用函数 经其分派 VM Closure → Function；宿主 type_of 对 VM Closure
     返 Unknown 会击穿 use 导入的链命名空间函数全体）+ 用户面 type_of
     与链判据同源（双面普通值同名同果）；
  ② 注入面诚实跳过（清单漂移符号 KeyError 如实跳过不造假成功）；
  ③ 语料子集双面 EQUAL（18 文件：use 跨模块/资源库/域符号/商店引擎/
     AI 域/插件域全形态，经驱动器 _run_one 全流程）；
  ④ 值锁：store_engine 五行回执 / 11_grow_sub 球体积 113.09724 /
     test_plugin_load 符号积分 x**3/3；
  ⑤ 登记不修对照：三文件对象身份/无种子分歧（08_auto_optimize/
     data_pipeline/neural_network）双面 both_ok_differ 如实分类。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

import scripts.selfhost_matrix as sm
from src.mbc.vm import _builtin_type_of

_ROOT = sm.ROOT

# ③ 语料子集（30e 探针 21 文件 − 3 登记分歧 = 18 EQUAL；驱动器 _run_one 全流程）
_EQUAL_CORPUS = [
    "matha/examples/07_auto_debug.matha",
    "matha/examples/09_self_grow.matha",
    "matha/examples/10_library_read.matha",
    "matha/examples/10_library_sub.matha",
    "matha/examples/10_web_app.matha",
    "matha/examples/11_desktop.matha",
    "matha/examples/11_grow_sub.matha",
    "matha/examples/11_library_grow.matha",
    "matha/examples/12_backend.matha",
    "matha/examples/12_library_discipline.matha",
    "matha/examples/12_mech_sub.matha",
    "matha/store_engine.matha",
    "examples/ai/ai_framework.matha",
    "examples/ai/genetic_algo.matha",
    "golden_tests/cases/18_domain_lazy_load.matha",
    "tests/test_plugin_load.matha",
    "tests/test_plugin_ode.matha",
    "tests/test_plugin_series.matha",
]

# ⑤ 阶段 40b 真化：宿主对象值语义 __eq__/__repr__ + 神经网络显式播种，
#    三语料双面同判（原登记不修「对象身份/无种子分歧」退役）。
_DIFFER_CORPUS = [
    "matha/examples/08_auto_optimize.matha",
    "examples/ai/data_pipeline.matha",
    "examples/ai/neural_network.matha",
]


@pytest.fixture(scope="module")
def driver():
    sys.setrecursionlimit(20000)
    sm._worker_init()
    return sm


def _boot_outs(driver, rel):
    """驱动器 boot 路径直取输出（值锁用；流程与 _run_one boot 块一致）。"""
    vm = driver._worker_vm
    src = (_ROOT / rel).read_text(encoding="utf-8")
    src = src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env0 = vm.call("注册内建", vm.call("空环境"))
    env0 = driver.inject_domain_builtins(vm, env0, skip=driver._boot_skip)
    env0 = driver.preload_resources(vm, prog, env0, skip=driver._boot_skip)
    for nm, ns in driver._worker_nss.items():
        env0 = vm.call("绑定环境", env0, nm, ns)
    vm.call("执行语句", prog, env0)
    outs = list(vm.call("输出快照"))
    vm.call("输出清空")
    return outs


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


# ① type_of 链判据关键名
def test_chain_critical_set():
    assert sm._CHAIN_CRITICAL == frozenset({"type_of"})


def test_type_of_vm_global_not_clobbered(driver):
    vm = driver._worker_vm
    host_to = driver._host_surface()["type_of"]
    assert vm.globals["type_of"] is not host_to, \
        "register_builtin 不得覆盖 VM globals 上的链分派判据 type_of"
    strip_cl = driver._worker_nss["标准库"]["strip"]
    assert vm.globals["type_of"](strip_cl) == "Function", \
        "链命名空间 VM Closure 须分类为 Function（应用函数 Function 分支可达）"


def test_type_of_user_env_dual_face(driver):
    src = '输出(type_of(41))\n输出(type_of("ab"))\n输出(type_of([1]))\n输出(type_of(null))'
    vm = driver._worker_vm
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env0 = vm.call("注册内建", vm.call("空环境"))
    env0 = driver.inject_domain_builtins(vm, env0, skip=driver._boot_skip)
    vm.call("执行语句", prog, env0)
    b_outs = list(vm.call("输出快照"))
    vm.call("输出清空")
    assert b_outs == ["Int", "String", "List", "Null"], f"boot type_of {b_outs!r}"
    from src import interp as host_interp
    h_outs, _ = host_interp.interpret(src)
    assert h_outs == ["Int", "String", "List", "Null"], f"宿主 type_of {h_outs!r}"


def test_use_chain_ns_callable_after_inject(driver):
    src = 'use 标准库 { strip | find }\n输出(strip("  ab  "))\n输出(find("b", "abc"))'
    vm = driver._worker_vm
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env0 = vm.call("注册内建", vm.call("空环境"))
    env0 = driver.inject_domain_builtins(vm, env0, skip=driver._boot_skip)
    for nm, ns in driver._worker_nss.items():
        env0 = vm.call("绑定环境", env0, nm, ns)
    vm.call("执行语句", prog, env0)
    b_outs = list(vm.call("输出快照"))
    vm.call("输出清空")
    assert b_outs == ["ab", 1], f"use 导入链函数应用 {b_outs!r}"
    assert vm.globals["type_of"] is _builtin_type_of


# ② 注入面诚实跳过（清单漂移）
def test_honest_skip_manifest_drift(driver, monkeypatch):
    class _DriftTable:
        def keys(self):
            return ["漂移符号", "平凡透传"]

        def __getitem__(self, k):
            if k == "漂移符号":
                raise KeyError(k)
            return lambda x: x

    monkeypatch.setattr(driver, "_inject_table", _DriftTable())
    vm = driver._worker_vm
    env0 = vm.call("注册内建", vm.call("空环境"))
    env1 = driver.inject_domain_builtins(vm, env0, skip=driver._boot_skip)
    names = [p[0] for p in env1]
    assert "漂移符号" not in names, "清单漂移符号须如实跳过"
    assert "平凡透传" in names, "正常符号须照常注入"


# ③ 语料子集双面 EQUAL（驱动器 _run_one 全流程）
@pytest.mark.parametrize("rel", _EQUAL_CORPUS, ids=[os.path.basename(p) for p in _EQUAL_CORPUS])
def test_corpus_equal(driver, rel):
    rec = driver._run_one(rel)
    assert rec.get("boot") == "ok", f"{rel} boot: {rec.get('boot_err', '')[:240]}"
    assert rec.get("host") == "ok", f"{rel} host: {rec.get('host_err', '')[:240]}"
    assert rec.get("equal") is True, \
        f"{rel} 输出分歧 first_div={rec.get('first_div')}"


# ④ 值锁
def test_store_engine_receipt(driver):
    rel = "matha/store_engine.matha"
    b_outs = _boot_outs(driver, rel)
    expect = ["方法=GET 路径=/health", "q=体积",
              "拒绝面=请求行须为 方法 路径 协议 三段", "未知路由码=404",
              "应用中心自测完成"]
    assert b_outs == expect, f"store_engine boot {b_outs!r}"
    from src import interp as host_interp
    src = (_ROOT / rel).read_text(encoding="utf-8")
    h_outs, _ = host_interp.interpret(src)
    assert h_outs == expect, f"store_engine host {h_outs!r}"


def test_grow_sub_sphere_volume(driver):
    b_outs = _boot_outs(driver, "matha/examples/11_grow_sub.matha")
    assert len(b_outs) == 1, f"输出数 {b_outs!r}"
    assert float(b_outs[0]) == pytest.approx(113.09724, abs=1e-4), f"球体积(3) {b_outs!r}"


def test_plugin_load_symbolic_integrate(driver):
    rel = "tests/test_plugin_load.matha"
    b_outs = _boot_outs(driver, rel)
    assert len(b_outs) == 1 and isinstance(b_outs[0], str), f"boot {b_outs!r}"
    assert "**3/3" in b_outs[0], f"∫x²dx = x**3/3，实际 {b_outs[0]!r}"
    from src import interp as host_interp
    src = (_ROOT / rel).read_text(encoding="utf-8")
    h_outs, _ = host_interp.interpret(src)
    assert _norm(b_outs) == _norm(h_outs), f"双面分歧 {b_outs!r} vs {h_outs!r}"


# ⑤ 真化对照（31-⑨ 退役：值语义 __eq__ + 显式播种后双面同判）
@pytest.mark.parametrize("rel", _DIFFER_CORPUS, ids=[os.path.basename(p) for p in _DIFFER_CORPUS])
def test_registered_differ_true(driver, rel):
    rec = driver._run_one(rel)
    assert rec.get("boot") == "ok", f"{rel} boot: {rec.get('boot_err', '')[:240]}"
    assert rec.get("host") == "ok", f"{rel} host: {rec.get('host_err', '')[:240]}"
    assert rec.get("equal") is True, \
        f"{rel} 值语义对象/播种后双面应同判，first_div={rec.get('first_div')}"
    assert driver._classify(rec) == "both_ok_equal"
