# -*- coding: utf-8 -*-
"""阶段 26b 三锁：编译器框架域（src/domains/compiler_framework.py，五框架模块消费面）。

锁五面：
  A. 内置遍真化 —— 常量折叠（add/sub/mul/div 数值字面量→load_const；除零诚实
     保留）/死代码消除（纯运算无后继使用者删除）作用于程序描述 dict；
  B. 域符号双面 —— 内置遍_安装/优化遍_列表/后端_列表/后端_执行/任务_提交/
     任务_清单 在 host（legacy-interp）与 VM 双面同值；native 诚实拒绝；
  C. 清单形状 —— manifest 含 compiler_framework 条目与 12 个可加载符号；
     程序描述 _to_duck/_from_duck 校验面（缺 op/未知键诚实拒绝+往返一致）；
  D. Matha 回调遍 —— 清单物化面（宿主闭包经共享语境解释器）注册成功；
     官方入口注入面（VM 闭包经 setdefault 注入的运行本体 trampoline）注册
     并真执行（Python 面回调 + VM 面回调各一）；
  E. 分析/策略/增量/任务面 —— ProgramAnalyzer 八类特征、策略 dict、
     增量构建报告、任务 id 消费为真。

注：PassManager 为进程级单例——统计跨跑累积（登记口径），断言用
「转变发生」而非「计数恰好」；自定义遍名全档唯一防撞。
"""
import json
from pathlib import Path

import pytest

from src.compiler.pass_manager import get_pass_manager
from src.domains.compiler_framework import (
    analyze_program,
    install_builtin_passes,
    pass_list,
    register_pass_fn,
    register_pass_fn_plain,
    recommend_strategy,
    run_passes_on,
    task_list,
    submit_task,
    _to_duck,
    _from_duck,
    _context,
)

ROOT = Path(__file__).resolve().parent.parent

_FOLD_PROGRAM = {"主": {"指令": [
    {"op": "add", "operands": [2, 3], "result": "t0"},
    {"op": "load", "operands": ["t0"], "result": "t1"},
    {"op": "store", "operands": ["t1"], "result": None},
]}}

_DEAD_PROGRAM = {"主": {"指令": [
    {"op": "add", "operands": [1, 1], "result": "死值"},
    {"op": "mul", "operands": [2, 3], "result": "活值"},
    {"op": "store", "operands": ["活值"], "result": None},
]}}


# ============================================================
# A. 内置遍真化
# ============================================================

class TestBuiltinPasses:
    def test_install_idempotent_and_listed(self):
        first = install_builtin_passes()
        second = install_builtin_passes()
        names = [p["名"] for p in pass_list()]
        assert "常量折叠" in names and "死代码消除" in names
        # 幂等：已存在不动（第二次不重装）
        assert first["新装"] == second["新装"] or set(first["新装"]) <= set(names)
        for entry in pass_list():
            if entry["名"] in ("常量折叠", "死代码消除"):
                assert entry["启用"] is True

    def test_constant_folding_rewrites(self):
        result = run_passes_on(_FOLD_PROGRAM)
        instrs = result["程序"]["主"]["指令"]
        folded = [i for i in instrs if i["op"] == "load_const"]
        assert any(i["operands"] == [5] and i["result"] == "t0" for i in folded)
        assert result["统计"]["常量折叠"].get("折叠", 0) >= 1

    def test_division_by_zero_not_folded(self):
        prog = {"主": {"指令": [{"op": "div", "operands": [1, 0], "result": "t0"}]}}
        result = run_passes_on(prog)
        instrs = result["程序"]["主"]["指令"]
        # 除零诚实保留：不折叠（结果未被使用会被死代码消除删除，故只锁「无折叠」）
        assert not any(i["op"] == "load_const" for i in instrs)

    def test_dead_code_elimination(self):
        result = run_passes_on(_DEAD_PROGRAM)
        instrs = result["程序"]["主"]["指令"]
        results = {i.get("result") for i in instrs}
        assert "死值" not in results
        assert "活值" in results
        assert result["统计"]["死代码消除"].get("消除", 0) >= 1

    def test_pass_enable_disable_toggle(self):
        from src.domains.compiler_framework import set_pass_enabled
        assert set_pass_enabled("常量折叠", False) is True
        assert [p for p in pass_list() if p["名"] == "常量折叠"][0]["启用"] is False
        assert set_pass_enabled("常量折叠", True) is True
        assert [p for p in pass_list() if p["名"] == "常量折叠"][0]["启用"] is True
        with pytest.raises(ValueError, match="未注册"):
            set_pass_enabled("从未注册的遍", True)


# ============================================================
# B. 域符号双面（host = legacy-interp，vm 主线）
# ============================================================

from src.diag_backends import ensure_registered
ensure_registered("src.interp")
from src.kernel.exec_api import run_checked  # noqa: E402


def _both_faces(source):
    h, he = run_checked(source, mode="legacy-interp")
    v, ve = run_checked(source, mode="vm")
    return (h, he), (v, ve)


class TestDomainBothFaces:
    def test_backend_exec_cross_runtime(self):
        (h, he), (v, ve) = _both_faces('输出(后端_执行("输出(6*7)")("vm"))')
        assert he is None and ve is None
        assert h == v == [[42]]  # 内层 run 的输出列表被外层 输出 原样收集

    def test_backend_exec_native_honest_rejection(self):
        (h, he), (v, ve) = _both_faces('输出(后端_执行("输出(1)")("native"))')
        assert he is not None and ve is not None
        assert "机器码" in str(he) and "机器码" in str(ve)

    def test_backend_list_shape(self):
        (h, he), (v, ve) = _both_faces('输出(后端_列表())')
        assert he is None and ve is None
        # 可用（模式→描述）+ 登记（后端信息列表）整体可打印，vm 恒在
        assert "vm" in str(h[0]) and "vm" in str(v[0])

    def test_task_submit_and_list(self):
        (h, he), (v, ve) = _both_faces(
            '输出(任务_提交("双面任务_26b")(["前置"])(3))')
        assert he is None and ve is None
        assert isinstance(h[0], str) and h[0]  # 任务 id
        # 清单含该任务（全局调度器，双面各自登记各一条）
        (h2, he2), (v2, ve2) = _both_faces('输出(任务_清单())')
        assert he2 is None and ve2 is None
        for face in (h2, v2):
            assert any("双面任务_26b" in str(t) for t in face)

    def test_pass_list_contains_builtin_names(self):
        (h, he), (v, ve) = _both_faces('输出(优化遍_列表())')
        assert he is None and ve is None
        assert "常量折叠" in str(h) and "常量折叠" in str(v)


# ============================================================
# C. 清单形状 + 程序描述校验面
# ============================================================

class TestManifestAndProgramShape:
    def test_manifest_entry(self):
        manifest = json.loads(
            (ROOT / "src" / "domains" / "manifest.json").read_text(encoding="utf-8"))
        entries = [p for p in manifest["plugins"] if p["name"] == "compiler_framework"]
        assert len(entries) == 1
        entry = entries[0]
        assert set(entry["symbols"]) == {
            "程序_分析", "策略_推荐", "内置遍_安装", "优化遍_列表", "优化遍_启停",
            "优化遍_执行", "优化遍_注册", "后端_列表", "后端_执行", "增量_编译",
            "任务_提交", "任务_清单"}
        assert entry.get("display_name") == "编译器框架"

    def test_to_duck_rejections(self):
        with pytest.raises(ValueError):
            _to_duck("不是程序")
        with pytest.raises(ValueError):
            _to_duck({"主": {"指令": [{"operands": [1]}]}})  # 缺 op
        with pytest.raises(ValueError):
            _to_duck({"主": {"指令": [{"op": "add", "神秘": 1}]}})  # 未知键

    def test_duck_roundtrip(self):
        duck = _to_duck(_FOLD_PROGRAM)
        assert _from_duck(duck) == _FOLD_PROGRAM


# ============================================================
# D. Matha 回调遍（清单物化面 + 官方入口注入面）
# ============================================================

class TestMathaCallbackPasses:
    def test_plain_face_host_callable(self):
        # 宿主闭包/Python 可调用经共享语境解释器注册成功
        name = register_pass_fn_plain("py直通遍_26b", lambda data: data)
        assert name == "py直通遍_26b"
        result = run_passes_on(_FOLD_PROGRAM)
        assert result["统计"]["py直通遍_26b"].get("运行", 0) >= 1

    def test_plain_face_rejects_non_callable(self):
        with pytest.raises(ValueError, match="可调用"):
            register_pass_fn_plain("拒绝遍_26b", {"不是函数": True})

    def test_python_face_invoke_value_runtime(self):
        class _Runtime:
            def invoke_value(self, fn, args):
                return fn(*args)

        calls = []
        register_pass_fn("py回调遍_26b", lambda data: calls.append(data) or data,
                         _Runtime())
        result = run_passes_on(_FOLD_PROGRAM)
        assert result["统计"]["py回调遍_26b"].get("运行", 0) >= 1
        assert calls and isinstance(calls[0], dict)

    def test_vm_face_injected_trampoline_registers_and_runs(self):
        # VM 程序内经 setdefault 注入的 优化遍_注册（运行本体 trampoline）注册
        # VM 闭包遍；随后 Python 面对同一程序描述执行——该遍真运行。
        src = ('func 空遍(数据) -> Any = (数据) => 数据\n'
               '优化遍_注册("VM闭包遍_26b")(空遍)\n'
               '输出("已注册")')
        out, err = run_checked(src, mode="vm")
        assert err is None and out == ["已注册"]
        result = run_passes_on(_FOLD_PROGRAM)
        assert result["统计"]["VM闭包遍_26b"].get("运行", 0) >= 1
        # 数据经 VM 闭包恒等遍往返无损：折叠结果（先于本遍执行）保持原样
        assert result["程序"]["主"]["指令"][0]["op"] == "load_const"
        assert result["程序"]["主"]["指令"][0]["operands"] == [5]

    def test_shared_context_rejects_vm_closure_shape(self):
        class _FakeClosure:
            fn = object()
            frame = object()

        _FakeClosure.__name__ = "Closure"
        with pytest.raises(ValueError, match="官方入口"):
            register_pass_fn_plain("闭包拒绝遍_26b", _FakeClosure())


# ============================================================
# E. 分析/策略/增量/任务面
# ============================================================

class TestAnalyzeStrategyIncrementalTask:
    def test_analyze_features(self):
        features = analyze_program(_FOLD_PROGRAM)
        assert isinstance(features, dict) and features  # 八类特征非空
        assert all(isinstance(k, str) for k in features)

    def test_strategy_recommendation(self):
        strategy = recommend_strategy(_FOLD_PROGRAM)
        assert isinstance(strategy, dict) and strategy

    def test_incremental_compile_report(self, tmp_path):
        from src.domains.compiler_framework import incremental_compile
        target = tmp_path / "目标.matha"
        target.write_text("输出(1)", encoding="utf-8")
        report = incremental_compile(str(target))
        assert {"target", "sources", "output_files", "success", "error",
                "compile_time", "timestamp"} <= set(report)
        assert report["target"] == str(target)
        # 框架模拟桩边界（登记不修）：不产真目标码，报告如实
        assert isinstance(report["success"], bool)

    def test_incremental_compile_empty_target_rejected(self):
        from src.domains.compiler_framework import incremental_compile
        with pytest.raises(ValueError):
            incremental_compile("   ")

    def test_submit_task_validation(self):
        with pytest.raises(ValueError):
            submit_task("   ")
        with pytest.raises(ValueError):
            submit_task("合法名", dependencies=[1, 2])
        with pytest.raises(ValueError):
            submit_task("合法名", priority="高")

    def test_task_list_shape(self):
        submit_task("形状任务_26b")
        tasks = task_list()
        assert any(t["任务"] == "形状任务_26b" for t in tasks)
        entry = [t for t in tasks if t["任务"] == "形状任务_26b"][0]
        assert {"id", "任务", "状态", "依赖", "优先级"} <= set(entry)
