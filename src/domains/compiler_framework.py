# -*- coding: utf-8 -*-
"""Matha 领域扩展模块：编译器框架（Compiler Framework）。

把 src/compiler 五框架模块（pass_manager / backend_manager /
adaptive_optimizer / incremental_compiler / distributed_compiler）与
exec_api 运行时注册表暴露为 Matha 符号（阶段 26b：框架模块插件化的
消费面——此前零消费者，本域是它们的第一个真实调用方）：

  程序_分析(程序) → 特征 dict           （ProgramAnalyzer）
  策略_推荐(程序) → 策略 dict           （StrategySelector 规则路径）
  内置遍_安装() → {新装, 列表}          （PassManager 现零具体遍——本域补真遍）
  优化遍_列表() → [{名, 启用, 统计}]
  优化遍_启停(名)(启用)
  优化遍_执行(程序) → {报告, 统计, 程序}
  优化遍_注册(名)(函数)                 （Matha 函数经运行本体 invoke_value 回调）
  后端_列表() → {可用, 登记}            （exec_api 运行时注册表）
  后端_执行(源码)(模式) → 输出列表       （真跨运行时调用：vm/legacy-interp/自定义）
  增量_编译(目标) → 构建报告 dict        （IncrementalCompiler）
  任务_提交(名)(依赖)(优先级) → 任务 id  （DistributedCompiler/TaskScheduler）
  任务_清单() → [{id, 任务, 状态, 依赖, 优先级}]

程序描述形态（泛型 IR 的纯数据面，Matha dict 直接构造）：
  {"函数名": {"指令": [{"op": "add", "operands": [1, 2], "result": "t0"}, …]}}
指令键：op 必填；operands/result/iterations/func_name/address 可选。

内置遍实现（本域提供，操作泛型 IR）：
  常量折叠 —— add/sub/mul/div 两操作数均为数值字面量 → load_const（除零不折叠）
  死代码消除 —— 纯运算结果无后继使用者 → 删除

边界（诚实登记）：增量编译 _compile_file 为框架模拟桩（不产真目标码）；
任务执行面需事件循环（LocalCompilerNode 异步面），本域只提供提交/清单/状态；
VM 闭包只经官方入口（src.kernel.exec_api）注入面回调，清单物化面拒绝。
"""
from __future__ import annotations

from types import SimpleNamespace

from src.compiler.pass_manager import Pass, get_pass_manager
from src.compiler.adaptive_optimizer import ProgramAnalyzer, StrategySelector
from src.compiler.incremental_compiler import IncrementalCompiler
from src.compiler.distributed_compiler import CompilationTask, get_distributed_compiler
from src.kernel.exec_api import available_modes, backend_info, run as _exec_run

# ============================================================
# 泛型 IR 纯数据面 ⇄ 框架鸭子对象 适配
# ============================================================

_INSTR_ALLOWED = ("op", "operands", "result", "iterations", "func_name", "address")


def _to_duck(program) -> SimpleNamespace:
    """Matha 程序描述 dict → 框架鸭子对象（.functions/.instructions/.op…）。"""
    if not isinstance(program, dict) or not program:
        raise ValueError("程序_分析: 程序须为非空 dict {函数名: {指令: [...]}}")
    functions = {}
    for fname, body in program.items():
        if not isinstance(fname, str) or not isinstance(body, dict):
            raise ValueError(f"程序: 函数 {fname!r} 须为 {{指令: [...]}} dict")
        instrs = body.get("指令", body.get("instructions", []))
        if not isinstance(instrs, list):
            raise ValueError(f"程序: 函数 {fname} 的 指令 须为列表")
        conv = []
        for ins in instrs:
            if not isinstance(ins, dict) or not isinstance(ins.get("op"), str):
                raise ValueError(f"程序: 函数 {fname} 指令须为含 op 字符串键的 dict")
            unknown = set(ins) - set(_INSTR_ALLOWED)
            if unknown:
                raise ValueError(f"程序: 指令未知键 {sorted(unknown)}（允许：{_INSTR_ALLOWED}）")
            conv.append(SimpleNamespace(**ins))
        functions[fname] = SimpleNamespace(name=fname, instructions=conv)
    return SimpleNamespace(functions=functions)


def _from_duck(program) -> dict:
    """框架鸭子对象 → Matha 程序描述 dict（键按 op/operands/result 等顺序）。"""
    out = {}
    for fname, func in getattr(program, "functions", {}).items():
        instrs = []
        for ins in getattr(func, "instructions", []):
            d = {k: v for k, v in vars(ins).items() if k in _INSTR_ALLOWED}
            instrs.append(d)
        out[getattr(func, "name", fname)] = {"指令": instrs}
    return out


# ============================================================
# 内置遍（本域提供的真实现——PassManager 此前零具体遍）
# ============================================================

_FOLD_OPS = {"add": "+", "sub": "-", "mul": "*", "div": "/"}


class 常量折叠遍(Pass):
    """add/sub/mul/div 两操作数均为数值字面量 → load_const（除零不折叠，诚实保留）。"""

    def __init__(self) -> None:
        super().__init__("常量折叠")

    def run(self, program):
        for func in getattr(program, "functions", {}).values():
            kept = []
            for ins in getattr(func, "instructions", []):
                folded = self._try_fold(ins)
                if folded is not None:
                    self.increment_stat("折叠")
                    kept.append(folded)
                else:
                    kept.append(ins)
            func.instructions = kept
        return program

    def _try_fold(self, ins):
        op = getattr(ins, "op", "")
        if op not in _FOLD_OPS:
            return None
        operands = getattr(ins, "operands", None)
        result = getattr(ins, "result", None)
        if not isinstance(operands, list) or len(operands) != 2 or result is None:
            return None
        a, b = operands[0], operands[1]
        if isinstance(a, bool) or isinstance(b, bool) \
                or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return None
        if op == "div" and b == 0:
            return None
        value = {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b}[op]
        return SimpleNamespace(op="load_const", operands=[value], result=result)


_PURE_OPS = {"add", "sub", "mul", "div", "load", "load_const", "move", "mov"}


class 死代码消除遍(Pass):
    """纯运算指令的结果无后继使用者 → 删除（有副作用/无结果指令不动）。"""

    def __init__(self) -> None:
        super().__init__("死代码消除")

    def run(self, program):
        for func in getattr(program, "functions", {}).values():
            instrs = getattr(func, "instructions", [])
            used = set()
            for ins in instrs:
                ops = getattr(ins, "operands", None)
                if isinstance(ops, list):
                    used.update(str(o) for o in ops)
            kept = []
            for ins in instrs:
                if getattr(ins, "op", "") in _PURE_OPS:
                    result = getattr(ins, "result", None)
                    if result is not None and str(result) not in used:
                        self.increment_stat("消除")
                        continue
                kept.append(ins)
            func.instructions = kept
        return program


# ============================================================
# 优化遍面（PassManager 消费）
# ============================================================

def _ensure_order(manager) -> None:
    if not getattr(manager, "_pass_order", None):
        manager.auto_order_passes()


def _attach_order(manager, name: str) -> None:
    """新注册遍进入执行序：序空全量拓扑排序；非空追加尾（已有序不重排）。"""
    order = getattr(manager, "_pass_order", None)
    if not order:
        manager.auto_order_passes()
    elif name not in order:
        manager._pass_order.append(name)


def install_builtin_passes(_占位=None) -> dict:
    """内置遍_安装()：幂等登记常量折叠/死代码消除并启用（已存在不动保统计）。

    Matha 零参调用双面（host/VM）传一个占位实参（0），故收而不看。
    """
    manager = get_pass_manager()
    existing = getattr(manager, "_passes", {})
    installed = []
    for make in (常量折叠遍, 死代码消除遍):
        probe = make()
        if probe.name not in existing:
            manager.register_pass(make())
            manager.enable_pass(probe.name)
            installed.append(probe.name)
    for name in installed:
        _attach_order(manager, name)
    _ensure_order(manager)
    return {"新装": installed, "列表": pass_list()}


def pass_list(_占位=None) -> list:
    """优化遍_列表()：已注册遍 → [{名, 启用, 统计, 依赖}]（零参占位实参收而不看）。"""
    manager = get_pass_manager()
    passes = getattr(manager, "_passes", {})
    enabled = getattr(manager, "_enabled_passes", set())
    stats = manager.get_stats()
    return [{"名": name, "启用": name in enabled, "统计": stats.get(name, {}),
             "依赖": list(getattr(passes[name], "_required_passes", []))}
            for name in passes]


def set_pass_enabled(name, enabled) -> bool:
    """优化遍_启停(名, 启用)：未注册遍诚实拒绝。"""
    if not isinstance(name, str):
        raise ValueError("优化遍_启停: 名须为字符串")
    manager = get_pass_manager()
    if name not in getattr(manager, "_passes", {}):
        raise ValueError(f"优化遍_启停: 遍 {name!r} 未注册")
    if enabled:
        manager.enable_pass(name)
    else:
        manager.disable_pass(name)
    return True


def run_passes_on(program, run_all=False) -> dict:
    """优化遍_执行(程序)：对程序描述跑全部启用遍，返回报告+优化后程序。"""
    duck = _to_duck(program)
    manager = get_pass_manager()
    if not getattr(manager, "_passes", {}):
        raise ValueError("优化遍_执行: 无已注册遍——先调用 内置遍_安装() 或 优化遍_注册()")
    _ensure_order(manager)
    result = manager.run(duck, enabled_only=not run_all)
    return {"报告": manager.get_summary(), "统计": manager.get_stats(),
            "程序": _from_duck(result)}


# ============================================================
# 分析 / 策略面（ProgramAnalyzer + StrategySelector 消费）
# ============================================================

def analyze_program(program) -> dict:
    """程序_分析(程序)：八类特征 → {特征名: 值}。"""
    features = ProgramAnalyzer().analyze(_to_duck(program))
    return {f.name: f.value for f in features}


def recommend_strategy(program) -> dict:
    """策略_推荐(程序)：分析特征并按规则路径选策略（未训练 ML → 规则路径）。"""
    features = ProgramAnalyzer().analyze(_to_duck(program))
    strategy = StrategySelector().select_strategy(features)
    return strategy.to_dict()


# ============================================================
# 运行时注册表面（exec_api 消费——26a 泛化后的注册表）
# ============================================================

def backend_list(_占位=None) -> dict:
    """后端_列表()：可用模式 + 已登记后端描述面（零参占位实参收而不看）。"""
    return {"可用": available_modes(), "登记": backend_info()}


def backend_run(source, mode="vm") -> list:
    """后端_执行(源码, 模式)：真跨运行时调用（vm/legacy-interp/自定义注册后端）。"""
    if not isinstance(source, str):
        raise ValueError("后端_执行: 源码须为字符串")
    if not isinstance(mode, str):
        raise ValueError("后端_执行: 模式须为字符串")
    return _exec_run(source, mode=mode)


# ============================================================
# 增量编译面（IncrementalCompiler 消费）
# ============================================================

def incremental_compile(target, force=False) -> dict:
    """增量_编译(目标)：受影响面增量构建报告（_compile_file 为框架模拟桩，登记边界）。"""
    if not isinstance(target, str) or not target.strip():
        raise ValueError("增量_编译: 目标须为非空路径字符串")
    compiler = IncrementalCompiler()
    compiler.add_source_file(target)
    result = compiler.compile(target, force=bool(force))
    return result.to_dict()


# ============================================================
# 分布式任务面（TaskScheduler 消费）
# ============================================================

def submit_task(name, dependencies=None, priority=0) -> str:
    """任务_提交(名, 依赖, 优先级)：登记编译任务，返回任务 id。"""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("任务_提交: 名须为非空字符串")
    deps = list(dependencies) if dependencies is not None else []
    if not all(isinstance(d, str) for d in deps):
        raise ValueError("任务_提交: 依赖须为字符串列表")
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("任务_提交: 优先级须为整数")
    task = CompilationTask(program=name, dependencies=deps, priority=priority)
    return get_distributed_compiler().submit_task(task)


def task_list(_占位=None) -> list:
    """任务_清单()：全部任务 → [{id, 任务, 状态, 依赖, 优先级}]（零参占位实参收而不看）。"""
    out = []
    for t in get_distributed_compiler().list_tasks():
        out.append({"id": t.id, "任务": t.program, "状态": t.status,
                    "依赖": list(t.dependencies), "优先级": t.priority})
    return out


# ============================================================
# 回调绑定面（Matha 函数优化遍——运行本体 invoke_value 协议）
# ============================================================

class _MathaPass(Pass):
    """Matha 函数包装成 Pass：程序 dict 进 → invoke_value 回调 → 程序 dict 出。"""

    def __init__(self, name: str, fn, runtime) -> None:
        super().__init__(name)
        self._fn = fn
        self._runtime = runtime

    def run(self, program):
        data = _from_duck(program)
        out = self._runtime.invoke_value(self._fn, [data])
        if not isinstance(out, dict):
            raise ValueError(f"优化遍 {self.name}: Matha 遍函数须返回程序 dict")
        self.increment_stat("运行")
        return _to_duck(out)


def register_pass_fn(name, fn, runtime) -> str:
    """优化遍_注册(名, 函数)：重名诚实拒绝（PassManager 已存在 ValueError）。"""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("优化遍_注册: 名须为非空字符串")
    manager = get_pass_manager()
    manager.register_pass(_MathaPass(name, fn, runtime))
    manager.enable_pass(name)
    _attach_order(manager, name)
    return name


# ============================================================
# 清单物化面（共享语境解释器版本——与 simulation._context 同构）
# ============================================================

_shared_context = None


def _context():
    global _shared_context
    if _shared_context is None:
        from src.interp import Interpreter
        _shared_context = Interpreter()
    return _shared_context


def _reject_vm_closure(f) -> None:
    if type(f).__name__ == "Closure" and hasattr(f, "fn") and hasattr(f, "frame"):
        raise ValueError(
            "优化遍_注册: 函数为 VM 闭包——请经官方入口（src.kernel.exec_api）运行，"
            "注入面绑定运行本体回调；清单物化面只支持宿主闭包/Python 可调用")


def register_pass_fn_plain(name, fn) -> str:
    """清单物化面入口：共享语境解释器回调（VM 闭包显式拒绝）。"""
    if isinstance(fn, dict) or fn is None:
        raise ValueError("优化遍_注册: 函数须为可调用 Matha 函数")
    _reject_vm_closure(fn)
    return register_pass_fn(name, fn, _context())


def make_runtime(runtime):
    """官方入口注入面：返回绑定运行本体的 优化遍_注册（VM/宿主解释器同名协议）。

    逐参应用约定：内建经 VM/宿主逐参链式调用，多参符号须柯里化。
    """
    return {"优化遍_注册": lambda name: (lambda fn: register_pass_fn(name, fn, runtime))}


def _register_compiler_framework(builtins: dict) -> None:
    """领域插件登记钩子（scripts/gen_domain_manifest.py 发现）。

    回调符号 优化遍_注册 走共享语境解释器版本；VM 闭包经官方入口注入面
    （make_runtime 绑定运行本体）。多参符号均为柯里化链（逐参应用约定）。
    """
    builtins["程序_分析"] = analyze_program
    builtins["策略_推荐"] = recommend_strategy
    builtins["内置遍_安装"] = install_builtin_passes
    builtins["优化遍_列表"] = pass_list
    builtins["优化遍_启停"] = lambda name: (lambda enabled: set_pass_enabled(name, enabled))
    builtins["优化遍_执行"] = run_passes_on
    builtins["优化遍_注册"] = lambda name: (lambda fn: register_pass_fn_plain(name, fn))
    builtins["后端_列表"] = backend_list
    builtins["后端_执行"] = lambda source: (lambda mode: backend_run(source, mode))
    builtins["增量_编译"] = incremental_compile
    builtins["任务_提交"] = lambda name: (
        lambda dependencies: (lambda priority: submit_task(name, dependencies, priority)))
    builtins["任务_清单"] = task_list


def _compiler_framework_symtab_names() -> list[str]:
    return [
        "程序_分析", "策略_推荐", "内置遍_安装", "优化遍_列表", "优化遍_启停",
        "优化遍_执行", "优化遍_注册", "后端_列表", "后端_执行", "增量_编译",
        "任务_提交", "任务_清单",
    ]


__all__ = [
    "analyze_program", "recommend_strategy", "install_builtin_passes",
    "pass_list", "set_pass_enabled", "run_passes_on", "register_pass_fn",
    "register_pass_fn_plain", "backend_list", "backend_run",
    "incremental_compile", "submit_task", "task_list",
    "make_runtime", "_register_compiler_framework", "_compiler_framework_symtab_names",
    "常量折叠遍", "死代码消除遍",
]
