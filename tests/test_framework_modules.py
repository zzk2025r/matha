# -*- coding: utf-8 -*-
"""架构框架批次三锁：src/compiler 五框架模块 + LLVM 委托面（.zcode 方案融合）。

批次现状（2026-11 融合）：pass_manager / backend_manager / adaptive_optimizer /
distributed_compiler / incremental_compiler 五模块为**框架级实现，未接入 MBC
编译/执行主线**——pass 操作鸭子类型泛型 IR 而非 MBC 字节码；Cranelift/WASM/
EVM/Native 四后端为诚实 NotImplementedError stub；sklearn/aiohttp/joblib 为
可选惰性依赖，import 面零第三方。本文件只锁框架自身的注册/调度/选择/依赖图
行为与诚实边界，不背书「接入主线」（独立工程项，见 KNOWN_ISSUES）。

.zcode 方案引用的伴生包（hal_drivers/conflict_resolution/security/
pkg_manager_v3、ConstFold/DeadCodeElim 框架 pass）不在场，属方案过时引用，
无锁可写。
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from src.compiler.pass_manager import (  # noqa: E402
    Pass,
    PassManager,
    get_pass_manager,
)
from src.compiler.backend_manager import (  # noqa: E402
    BackendManager,
    LLVMBackend,
    auto_select_backend,
    discover_and_register_backends,
)
from src.compiler.adaptive_optimizer import (  # noqa: E402
    AdaptiveOptimizer,
    OptimizationStrategy,
    ProgramAnalyzer,
    ProgramFeature,
    StrategySelector,
)
from src.compiler.distributed_compiler import (  # noqa: E402
    CompilationTask,
    LocalCompilerNode,
    NodeInfo,
    RemoteCompilerNode,
    TaskScheduler,
    _DiGraph,
)
from src.compiler.incremental_compiler import (  # noqa: E402
    DependencyGraph,
    FileInfo,
    IncrementalCompiler,
)
from src.compiler.llvm_backend import (  # noqa: E402
    IRConstant,
    LLVMIRGenerator,
    MathaToIRConverter,
    matha_to_llvm_ir,
)
from src.parser import parse  # noqa: E402


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _instr(op, operands, result=None):
    return SimpleNamespace(op=op, operands=operands, result=result)


def _duck_program():
    """鸭子 IR：functions→instructions（op/operands/result），框架与特征分析共用。"""
    return SimpleNamespace(functions={
        "f": SimpleNamespace(name="f", instructions=[
            _instr("add", (5, 3), "t1"),
            _instr("store", ("t1",)),
        ]),
        "g": SimpleNamespace(name="g", instructions=[
            _instr("mul", (2, 6), "t2"),
            _instr("loop", ()),
        ]),
    })


class _FoldPass(Pass):
    """测试用折叠 pass：operands 全数值的 add/mul 折叠为 load_const。"""

    def run(self, program):
        folded = 0
        for func in program.functions.values():
            new_instrs = []
            for ins in func.instructions:
                if ins.op in ("add", "mul") and all(
                    isinstance(o, (int, float)) for o in ins.operands
                ):
                    val = (ins.operands[0] + ins.operands[1] if ins.op == "add"
                           else ins.operands[0] * ins.operands[1])
                    new_instrs.append(_instr("load_const", (val,), ins.result))
                    folded += 1
                else:
                    new_instrs.append(ins)
            func.instructions = new_instrs
        self.increment_stat("folded", folded)
        return program


class _TracePass(Pass):
    """测试用记录 pass：把执行名追加进共享 log。"""

    def __init__(self, name, log):
        super().__init__(name)
        self._log = log

    def run(self, program):
        self._log.append(self.name)
        return program


# ==== Pass 框架 ====

def test_pass_base_name_and_stats():
    class 无名(Pass):
        def run(self, program):
            return program

    assert 无名().name == "无名"
    named = _TracePass("显式名", [])
    assert named.name == "显式名"
    named.increment_stat("hits", 2)
    named.increment_stat("hits")
    assert named.get_stat("hits") == 3
    assert named.get_stat("缺省", 7) == 7
    stats = named.stats
    stats["hits"] = 99  # stats 返回拷贝，外部改写不穿透
    assert named.get_stat("hits") == 3


def test_register_duplicate_rejected_replace_allowed():
    pm = PassManager()
    log = []
    pm.register_pass(_TracePass("A", log))
    with pytest.raises(ValueError, match="已存在"):
        pm.register_pass(_TracePass("A", log))
    pm.register_pass(_TracePass("A", log), replace=True)  # 显式替换放行


def test_register_missing_dependency_rejected():
    pm = PassManager()
    p = _TracePass("后继", [])
    p.add_required_pass("前置")
    with pytest.raises(ValueError, match="缺少依赖"):
        pm.register_pass(p)


def test_auto_order_topological():
    pm = PassManager()
    log = []
    a, b, c = _TracePass("A", log), _TracePass("B", log), _TracePass("C", log)
    b.add_dependency("C")
    a.add_dependency("B")
    pm.register_pass(a)
    pm.register_pass(b)
    pm.register_pass(c)
    pm.auto_order_passes()
    for p in (a, b, c):
        pm.enable_pass(p.name)
    log.clear()
    assert pm.run("prog") == "prog"
    assert log == ["C", "B", "A"]


def test_auto_order_cycle_raises():
    pm = PassManager()
    log = []
    a, b = _TracePass("A", log), _TracePass("B", log)
    a.add_dependency("B")
    b.add_dependency("A")
    pm.register_pass(a)
    pm.register_pass(b)
    with pytest.raises(ValueError, match="循环"):
        pm.auto_order_passes()


def test_run_enabled_only_and_disable():
    pm = PassManager()
    log = []
    pm.register_pass(_TracePass("A", log))
    pm.register_pass(_TracePass("B", log))
    pm.auto_order_passes()
    # 未启用任何 pass：enabled_only 默认全跳过
    assert pm.run("prog") == "prog"
    assert log == []
    pm.enable_pass("A")
    pm.enable_pass("B")
    assert pm.run("prog") == "prog"
    assert log == ["A", "B"]
    pm.disable_pass("B")
    log.clear()
    assert pm.run("prog") == "prog"
    assert log == ["A"]
    # enabled_only=False：禁用的也跑
    log.clear()
    assert pm.run("prog", enabled_only=False) == "prog"
    assert log == ["A", "B"]


def test_fold_pass_transforms_duck_ir_and_stats():
    pm = PassManager()
    prog = _duck_program()
    fold = _FoldPass("折叠")
    pm.register_pass(fold)
    pm.enable_pass("折叠")
    pm.auto_order_passes()
    out = pm.run(prog)
    assert out is prog
    f, g = out.functions["f"], out.functions["g"]
    assert f.instructions[0].op == "load_const" and f.instructions[0].operands[0] == 8
    assert f.instructions[1].op == "store"  # 非折叠指令原样保留
    assert g.instructions[0].operands[0] == 12
    assert g.instructions[1].op == "loop"
    assert pm.get_stats()["折叠"]["folded"] == 2
    assert "总计: 2" in pm.get_summary()


def test_set_pass_order_unknown_rejected():
    pm = PassManager()
    with pytest.raises(ValueError, match="未注册"):
        pm.set_pass_order(["幽灵"])


# ==== 后端框架 ====

def test_builtin_backends_registered():
    names = set(BackendManager().list_backends())
    assert names == {"LLVM", "Cranelift", "WASM", "EVM", "Native"}


def test_llvm_backend_compile_delegates_to_matha_to_llvm_ir():
    program = parse("x = 1 + 2")
    expr = program.decls[0].value
    backend = LLVMBackend()
    ir = backend.compile(expr)
    assert "define double @main()" in ir
    assert "fadd" in ir
    assert backend.target == "x86_64-pc-linux-gnu"
    # 委托等价：与直调官方导出逐字节一致
    assert ir == matha_to_llvm_ir(expr)


def test_four_stub_backends_honest_not_implemented():
    mgr = BackendManager()
    for name in ("Cranelift", "WASM", "EVM", "Native"):
        with pytest.raises(NotImplementedError, match="尚未实现"):
            mgr.get_backend(name).compile("prog")


def test_auto_select_backend_mapping():
    assert auto_select_backend(None, "wasm32-wasi") == "WASM"
    assert auto_select_backend(None, "wasm") == "WASM"
    assert auto_select_backend(None, "evm") == "EVM"
    assert auto_select_backend(None, "native") == "Native"
    assert auto_select_backend(None, "x86_64-pc-windows-msvc") == "LLVM"
    assert auto_select_backend(None, "随便什么") == "LLVM"


def test_backend_register_duplicate_and_missing():
    mgr = BackendManager()
    from src.compiler.backend_manager import LLVMBackend as L
    with pytest.raises(ValueError, match="已存在"):
        mgr.register_backend(L())
    mgr.register_backend(L(), replace=True)
    with pytest.raises(ValueError, match="不存在"):
        mgr.get_backend("幽灵后端")
    with pytest.raises(ValueError, match="不存在"):
        mgr.compile("prog", backend="幽灵后端")


def test_discover_missing_package_warns_not_crashes():
    # 缺包只告警不崩溃（诚实跳过），全局面不受影响
    discover_and_register_backends("src.compiler.__no_such_backends__")
    from src.compiler.backend_manager import list_backends
    assert set(list_backends()) == {"LLVM", "Cranelift", "WASM", "EVM", "Native"}


# ==== 自适应优化器 ====

def test_analyzer_features_on_duck_ir():
    feats = {f.name: f.value for f in ProgramAnalyzer().analyze(_duck_program())}
    assert feats["函数数量"] == 2.0
    assert feats["循环数量"] == 1.0
    # 圈复杂度按「末函数 decisions+1」对函数数取平均：两函数各 1 → 1/2
    assert feats["平均圈复杂度"] == 0.5
    assert feats["函数调用次数"] == 0.0


def test_analyzer_no_functions_no_crash():
    """除零防御锁：无 functions 属性的程序分析不崩溃、特征诚实记 0。"""
    feats = {f.name: f.value for f in ProgramAnalyzer().analyze(SimpleNamespace())}
    assert feats["函数数量"] == 0.0
    assert feats["平均圈复杂度"] == 0.0
    assert feats["平均认知复杂度"] == 0.0


def test_rule_path_selection_deterministic():
    sel = StrategySelector()
    assert sel.is_trained is False and sel.model is None
    hi_compute = [ProgramFeature("内存访问密度", 0.05),
                  ProgramFeature("并行指令比例", 0.5)]
    assert sel.select_strategy(hi_compute).name == "高计算密集型"
    memory = [ProgramFeature("内存访问密度", 0.3),
              ProgramFeature("并行指令比例", 0.1)]
    assert sel.select_strategy(memory).name == "内存密集型"
    control = [ProgramFeature("内存访问密度", 0.05),
               ProgramFeature("平均圈复杂度", 12.0)]
    assert sel.select_strategy(control).name == "控制流密集型"
    generic = [ProgramFeature("内存访问密度", 0.15),
               ProgramFeature("并行指令比例", 0.2),
               ProgramFeature("平均圈复杂度", 3.0)]
    assert sel.select_strategy(generic).name == "通用优化"


def test_strategy_add_remove_list():
    sel = StrategySelector()
    n_default = len(sel.list_strategies())
    extra = OptimizationStrategy(name="自定义策略", passes=["窥孔优化"])
    sel.add_strategy(extra)
    assert len(sel.list_strategies()) == n_default + 1
    assert sel.remove_strategy("自定义策略") is True
    assert sel.remove_strategy("自定义策略") is False  # 重复删除诚实 False
    assert len(sel.list_strategies()) == n_default


def test_train_without_sklearn_honest_import_error():
    if _has_module("sklearn"):
        pytest.skip("sklearn 在场：诚实 ImportError 路径不适用（ML 可选面）")
    sel = StrategySelector()
    with pytest.raises(ImportError, match="scikit-learn"):
        sel.train([])


def test_adaptive_optimizer_records_history():
    opt = AdaptiveOptimizer()
    prog = _duck_program()
    out = opt.optimize(prog)
    assert out is prog  # 框架级：不改写程序本体
    history = opt.get_optimization_history()
    assert len(history) == 1
    features, strategy, improvement = history[0]
    assert any(f.name == "函数数量" for f in features)
    assert strategy.name in ("高计算密集型", "内存密集型", "控制流密集型", "通用优化")
    assert improvement >= 0.0


def test_save_model_untrained_honest_noop():
    # 未训练时保存 = 诚实不动作（不落假模型文件）
    opt = AdaptiveOptimizer()
    opt.save_model("unused_model_path_should_not_exist.pkl")
    assert not Path("unused_model_path_should_not_exist.pkl").exists()


# ==== 分布式编译 ====

def test_digraph_add_edge_successors():
    g = _DiGraph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    assert sorted(g.successors("a")) == ["b", "c"]
    assert g.successors("b") == []
    assert g.successors("不存在") == []


def test_compilation_task_roundtrip():
    task = CompilationTask(program="p", priority=3, dependencies=["t0"], timeout=60)
    assert task.status == "pending"
    clone = CompilationTask.from_dict(task.to_dict())
    assert clone.id == task.id
    assert clone.priority == 3 and clone.dependencies == ["t0"]
    assert clone.timeout == 60 and clone.status == "pending"


def test_scheduler_inactive_node_task_stays_pending():
    sched = TaskScheduler()
    node = LocalCompilerNode(NodeInfo(name="n1"))
    node.node_info.status = "inactive"
    sched.add_node(node)
    task = CompilationTask(program="p")
    sched.submit_task(task)
    assert sched.get_task_status(task.id) == "pending"
    assert task.assigned_node is None


def test_scheduler_missing_dependency_task_stays_pending():
    sched = TaskScheduler()
    node = LocalCompilerNode(NodeInfo(name="n1"))
    sched.add_node(node)
    node.node_info.status = "inactive"  # 防止真调度进事件循环（无循环面）
    task = CompilationTask(program="p", dependencies=["幽灵任务"])
    sched.submit_task(task)
    assert sched.get_task_status(task.id) == "pending"


def test_scheduler_strategy_validation():
    sched = TaskScheduler()
    assert sched.load_balancing_strategy == "round_robin"
    sched.set_load_balancing_strategy("bogus策略")
    assert sched.load_balancing_strategy == "round_robin"  # 非法策略拒绝不改值
    sched.set_load_balancing_strategy("least_loaded")
    assert sched.load_balancing_strategy == "least_loaded"


def test_local_node_compile_produces_result():
    node = LocalCompilerNode(NodeInfo(name="local"))
    task = CompilationTask(program="x = 1")
    result = asyncio.run(node.execute_task(task))
    assert result["status"] == "success"
    assert task.status == "completed"
    assert task.result is result
    assert task.id not in node.node_info.current_tasks


def test_remote_node_without_aiohttp_honest_import_error():
    if _has_module("aiohttp"):
        pytest.skip("aiohttp 在场：诚实 ImportError 边界不适用")
    node = RemoteCompilerNode(NodeInfo(name="r", address="127.0.0.1", port=9))
    task = CompilationTask(program="x")
    with pytest.raises(ImportError, match="aiohttp"):
        asyncio.run(node.compile(task))
    with pytest.raises(ImportError, match="aiohttp"):
        asyncio.run(node.heartbeat())


# ==== 增量编译 ====

def test_dependency_graph_transitive_and_dependents(tmp_path):
    a = tmp_path / "a.matha"; a.write_text("x = 1", encoding="utf-8")
    b = tmp_path / "b.matha"; b.write_text("use 文件", encoding="utf-8")
    c = tmp_path / "c.matha"; c.write_text("use 更多", encoding="utf-8")
    g = DependencyGraph()
    g.add_dependency(str(a), str(b))  # a 依赖 b
    g.add_dependency(str(b), str(c))  # b 依赖 c
    assert g.get_dependencies(str(a)) == {str(b)}
    assert g.get_all_dependencies(str(a)) == {str(b), str(c)}
    assert g.get_all_dependents(str(c)) == {str(b), str(a)}
    affected = g.get_affected_files({str(c)})
    assert affected == {str(c), str(b), str(a)}


def test_dependency_graph_topological_sort_order(tmp_path):
    a = tmp_path / "a.matha"; a.write_text("x = 1", encoding="utf-8")
    b = tmp_path / "b.matha"; b.write_text("y = 2", encoding="utf-8")
    c = tmp_path / "c.matha"; c.write_text("z = 3", encoding="utf-8")
    g = DependencyGraph()
    g.add_dependency(str(a), str(b))
    g.add_dependency(str(b), str(c))
    order = g.topological_sort()
    assert order == [str(c), str(b), str(a)]


def test_file_info_has_changed(tmp_path):
    p = tmp_path / "a.matha"
    p.write_text("x = 1", encoding="utf-8")
    info = FileInfo(path=str(p))
    first_hash = info.compute_hash()
    assert first_hash != ""
    assert info.has_changed() is False
    # 改写内容 + 显式推后 mtime（避开 Windows 同刻度量化竞态）
    p.write_text("x = 2", encoding="utf-8")
    future = time.time() + 10
    os.utime(str(p), (future, future))
    assert info.has_changed() is True
    assert info.hash != first_hash  # 哈希随内容更新
    # 文件被删 = 诚实判变
    p.unlink()
    assert info.has_changed() is True


def test_incremental_only_recompiles_affected(tmp_path):
    a = tmp_path / "a.matha"; a.write_text("x = 1", encoding="utf-8")
    b = tmp_path / "b.matha"; b.write_text("y = 2", encoding="utf-8")
    c = tmp_path / "c.matha"; c.write_text("z = 3", encoding="utf-8")
    comp = IncrementalCompiler(cache_dir=str(tmp_path / "cache"))
    for p in (a, b, c):
        comp.add_source_file(str(p))
    comp.add_dependency(str(b), str(a))  # b 依赖 a
    # 变更 a（内容 + mtime 推后）
    a.write_text("x = 99", encoding="utf-8")
    future = time.time() + 10
    os.utime(str(a), (future, future))
    result_b = comp.compile(str(b), force=False)
    assert result_b.success is True
    assert result_b.sources == [str(a), str(b)]  # 拓扑序：被依赖者先编
    assert comp.get_build_status(str(a)) is not None
    assert comp.get_build_status(str(b)) is not None
    # c 与变更无关：不受影响 → 不编译（增量语义锁）
    result_c = comp.compile(str(c), force=False)
    assert result_c.sources == []
    assert comp.get_build_status(str(c)) is None
    assert comp.get_build_status(str(c)) is None  # 重复查询幂等


def test_dependency_graph_save_load_roundtrip(tmp_path):
    a = tmp_path / "a.matha"; a.write_text("x = 1", encoding="utf-8")
    b = tmp_path / "b.matha"; b.write_text("y = 2", encoding="utf-8")
    g = DependencyGraph()
    g.add_dependency(str(a), str(b))
    dump = tmp_path / "graph.json"
    g.save(str(dump))
    g2 = DependencyGraph()
    g2.load(str(dump))
    assert set(g2.files) == {str(a), str(b)}
    assert g2.get_dependencies(str(a)) == {str(b)}


# ==== LLVM 面 ====

def test_matha_to_llvm_ir_fake_node_seam():
    """llvm_backend 显式测试面：.kind 假节点契约。"""
    node = MathaToIRConverter().convert(SimpleNamespace(kind="FloatLit", value=7.5))
    assert isinstance(node, IRConstant)
    assert node.value == 7.5 and node.lltype == "double"


def test_llvm_ir_generator_module_name():
    ir = LLVMIRGenerator("我的模块").generate([])
    assert "; 模块: 我的模块" in ir
    assert 'target triple = "x86_64-pc-windows-msvc"' in ir
    assert "declare double @sqrt(double)" in ir
    assert ir.rstrip().endswith("}")


# ==== 全局面与纪律 ====

def test_global_singletons_identity(tmp_path):
    assert get_pass_manager() is get_pass_manager()
    from src.compiler.backend_manager import get_backend_manager
    from src.compiler.adaptive_optimizer import get_adaptive_optimizer
    from src.compiler.distributed_compiler import get_distributed_compiler
    from src.compiler.incremental_compiler import get_incremental_compiler
    assert get_backend_manager() is get_backend_manager()
    assert get_adaptive_optimizer() is get_adaptive_optimizer()
    assert get_distributed_compiler() is get_distributed_compiler()
    comp = get_incremental_compiler(str(tmp_path / "cache"))
    assert get_incremental_compiler(str(tmp_path / "cache")) is comp


def test_import_face_pure_stdlib():
    """import 面零第三方：子进程取证（sklearn/aiohttp/networkx 等绝不随 import 触发）。"""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import src.compiler\n"
        "third = {'sklearn', 'aiohttp', 'networkx', 'numpy', 'pandas', "
        "'joblib', 'scipy', 'llvmlite'}\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in third)\n"
        "assert not bad, f'import src.compiler 触发第三方: {bad}'\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True,
                   capture_output=True, timeout=180)
