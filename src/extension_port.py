"""统一五动作端口协议——宿主适配层（阶段 28e）。

纯 Matha 协议模块 matha/library/os/端口协议.matha 定义了端口状态形状与
五动作（注册 / 启停 / 升级 / 回滚 / 依赖协商）的纯函数语义（状态进出、
诚实拒绝、审计行追加、回滚弹最近一版）。本模块把同一协议适配到六个
宿主运行时面，状态形状与返回三元组 (结果, 端口, 原因) 与 Matha 面逐
字段同形，供 tests/test_port_protocol_phase28.py 双面对拍：

  parser       → src/custom_ops.py 注册表（unregister 为 28e 补齐）
  interp_host  → Interpreter.register_builtin/unregister_builtin（28d）
  interp_boot  → 自举 vm.matha 解释器插口（24d 共享全局嵌套 VM 注入 lambda）
  compiler     → src/compiler/pass_manager.PassManager（26b，unregister_pass 28e）
  vm           → VM.register_builtin/unregister_builtin（28d）
  kernel       → src/features.set_feature（23b 单源；预装特性，不可注销）

诚实口径：后端拒绝（保留名 / 模块函数 / 非可调用 / 未知内核特性）以
异常上抛，端口层归一为 (假, 状态原样, 原因文本)，与 Matha 面
结果=假 + 原因 的失败表达一致，不吞状态。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "LayerPort", "make_port",
    "ParserBackend", "InterpHostBackend", "InterpBootBackend",
    "CompilerBackend", "VMBackend", "KernelBackend",
    "LAYER_NAMES",
]

#: 六层规范层名（与 matha/library/os/端口协议.matha 文档口径一致）
LAYER_NAMES: dict[str, str] = {
    "parser": "词法语法",
    "interp_host": "解释器宿主",
    "interp_boot": "解释器自举",
    "compiler": "编译器",
    "vm": "虚拟机",
    "kernel": "内核特性",
}


class _Backend:
    """层适配器基类：六个面各自实现注册/注销/启停，端口层驱动协议语义。"""

    layer = "?"

    def register(self, name: str, impl: Any) -> None:
        """落名到运行时（拒绝以异常上抛）。"""
        raise NotImplementedError

    def unregister(self, name: str) -> bool:
        raise NotImplementedError

    def enable(self, name: str, impl: Any) -> None:
        self.register(name, impl)

    def disable(self, name: str) -> None:
        self.unregister(name)

    def is_enabled(self, name: str) -> bool | None:
        """注册后初始启用态；None → 端口层默认 真。"""
        return None


# ============================================================
# 六层后端
# ============================================================

class ParserBackend(_Backend):
    """词法语法层：自定义运算符注册表（@define_op 运行时侧）。

    impl = (优先级: int, 结合性: "left"|"right", 绑定函数名: str|None)。
    启停 = 注册表进出（停用后运算符未绑定，诚实报错）。
    """

    layer = LAYER_NAMES["parser"]

    def register(self, name, impl):
        from src import custom_ops as ops
        prec, assoc, handler = impl
        ops.register(name, prec, assoc, handler)

    def unregister(self, name):
        from src import custom_ops as ops
        return ops.unregister(name)


class InterpHostBackend(_Backend):
    """解释器宿主层：Interpreter.register_builtin/unregister_builtin（28d）。

    impl = Python 可调用；同名用户函数在 call() 中优先（funcs-first 既有
    语义），保留名 / 非可调用由宿主面诚实拒绝。
    """

    layer = LAYER_NAMES["interp_host"]

    def __init__(self, interp):
        self._interp = interp

    def register(self, name, impl):
        self._interp.register_builtin(name, impl)

    def unregister(self, name):
        return self._interp.unregister_builtin(name)


class InterpBootBackend(_Backend):
    """解释器自举层：vm.matha 解释器插口（interp.matha 注册表）。

    impl = Matha lambda **源码表达式文本**（如 "(ps) => ps[0] * 3"）——
    注册走 24d 钉池纪律：把 `func 注册Lambda() = 注册解释器插口("名", <impl>)`
    编译为伴生模块，模块全部函数钉 consts/functions（_invoke 对 fn.consts
    为 None 的帧回退 self.mod.constants，跨模块调用会拿错常量池），再经
    临时全局绑定在 boot VM 上 vm.call 执行——注册语义全部落在 boot 世界
    （解释器插口 注册表持久可见），lambda 落成真 M3V 闭包且常量池按伴生
    模块钉住，下一次 注册内建(空环境()) 时并入解释器环境。
    注销直接 vm.call 注销解释器插口（28d 面，返回 Bool）。
    """

    layer = LAYER_NAMES["interp_boot"]

    def __init__(self, boot_vm):
        self._vm = boot_vm

    def register(self, name, impl):
        if not isinstance(impl, str):
            raise TypeError(
                f"解释器自举层 impl 需 Matha lambda 源码文本，得到 {type(impl).__name__}")
        from src.parser import parse as py_parse
        from src.mbc.compiler import compile_program
        from src.mbc.vm import Closure
        prog = py_parse(
            f'func 注册Lambda() -> Bool = 注册解释器插口("{name}", {impl})\n')
        mod = compile_program(prog)
        for fn in mod.functions.values():
            fn.consts = mod.constants
            fn.functions = mod.functions
        g = self._vm.globals
        tmp = "__端口注册Lambda"
        g[tmp] = Closure(mod.functions["注册Lambda"], self._vm.main_frame)
        try:
            self._vm.call(tmp)
        finally:
            g.pop(tmp, None)

    def unregister(self, name):
        return bool(self._vm.call("注销解释器插口", name))

    def is_enabled(self, name):
        return name in self._vm.call("解释器插口名表")


class CompilerBackend(_Backend):
    """编译器层：PassManager（26b）。impl = Pass 实例。

    注册后默认未启用（与 PassManager 既有语义一致）；启用经 enable_pass，
    升级/回滚按 replace=True 覆盖注册（版本语义由端口层记账）。
    """

    layer = LAYER_NAMES["compiler"]

    def __init__(self, manager):
        self._pm = manager

    def register(self, name, impl):
        self._pm.register_pass(impl, replace=True)

    def unregister(self, name):
        return self._pm.unregister_pass(name)

    def enable(self, name, impl):
        self._pm.enable_pass(name)

    def disable(self, name):
        self._pm.disable_pass(name)

    def is_enabled(self, name):
        return name in self._pm._enabled_passes


class VMBackend(_Backend):
    """虚拟机层：VM.register_builtin/unregister_builtin（28d）。

    impl = Python 可调用（宿主 VM 逐参应用语义）；保留名 / 模块函数 /
    非可调用由宿主面诚实拒绝。
    """

    layer = LAYER_NAMES["vm"]

    def __init__(self, vm):
        self._vm = vm

    def register(self, name, impl):
        self._vm.register_builtin(name, impl)

    def unregister(self, name):
        return self._vm.unregister_builtin(name)


class KernelBackend(_Backend):
    """内核特性层：features.set_feature（23b 单源）。

    四特性（SCOPED_BLOCKS/STACK_ENGINE/INLINE_CACHE/PARSE_CACHE）预装——
    注册仅声明已知特性（未知特性诚实拒绝），初始启用态取运行时实况；
    注销不可（内核特性无卸载面，诚实边界）。
    """

    layer = LAYER_NAMES["kernel"]

    def register(self, name, impl):
        from src import features
        if name not in features.KNOWN_FEATURES:
            known = ", ".join(features.KNOWN_FEATURES)
            raise ValueError(f"'{name}' 不是内核特性（已知: {known}）")

    def unregister(self, name):
        return False

    def enable(self, name, impl):
        from src import features
        features.set_feature(name, True)

    def disable(self, name):
        from src import features
        features.set_feature(name, False)

    def is_enabled(self, name):
        from src import features
        return features.is_enabled(name)


# ============================================================
# 端口层：协议语义驱动（与 matha/library/os/端口协议.matha 同构）
# ============================================================

def make_port(kind: str, target: Any = None) -> "LayerPort":
    """按层类型构造端口；target 为该层运行时对象（见各类 docstring）。"""
    if kind == "parser":
        return LayerPort(ParserBackend())
    if kind == "interp_host":
        return LayerPort(InterpHostBackend(target))
    if kind == "interp_boot":
        return LayerPort(InterpBootBackend(target))
    if kind == "compiler":
        from src.compiler.pass_manager import get_pass_manager
        return LayerPort(CompilerBackend(target if target is not None
                                         else get_pass_manager()))
    if kind == "vm":
        return LayerPort(VMBackend(target))
    if kind == "kernel":
        return LayerPort(KernelBackend())
    raise ValueError(f"未知端口层: {kind}（已知: {', '.join(LAYER_NAMES)}）")


class LayerPort:
    """单层端口：五动作协议宿主驱动，状态形状与 Matha 协议同构。

    条目 = [名, 版本, 启用, 实现, 历史[[版本, 实现]], 依赖名们]；
    历史 = 升级压栈 / 回滚弹最近一版；审计行与 Matha 面同文案。
    """

    def __init__(self, backend: _Backend):
        self._backend = backend
        self.layer = backend.layer
        self._entries: list[list] = []
        self._audit: list[str] = []

    # ---------- 状态（与 Matha {"层","条目","审计"} 同形） ----------

    def state(self) -> dict:
        return {"层": self.layer,
                "条目": [list(e) for e in self._entries],
                "审计": list(self._audit)}

    def names(self) -> list:
        return [e[0] for e in self._entries]

    def enabled_names(self) -> list:
        return [e[0] for e in self._entries if e[2]]

    def entry(self, name):
        i = self._find(name)
        return list(self._entries[i]) if i >= 0 else None

    def audit(self) -> list:
        return list(self._audit)

    # ---------- 内部 ----------

    def _find(self, name: str) -> int:
        for i, e in enumerate(self._entries):
            if e[0] == name:
                return i
        return -1

    def _negotiate(self, deps) -> tuple[bool, str]:
        missing = [d for d in deps if self._find(d) < 0]
        disabled = [d for d in deps
                    if self._find(d) >= 0 and not self._entries[self._find(d)][2]]
        if not missing and not disabled:
            return True, "依赖满足"
        reason = "依赖未满足"
        if missing:
            reason += " 缺失[" + ",".join(missing) + "]"
        if disabled:
            reason += " 停用[" + ",".join(disabled) + "]"
        return False, reason

    def _try(self, fn, *args) -> tuple[bool, dict, str]:
        """后端拒绝归一：异常 → (假, 状态原样, 原因文本)——诚实不吞状态。"""
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 —— 后端拒绝面即异常
            return False, self.state(), str(e)
        return True, self.state(), ""

    # ---------- 五动作 ----------

    def register(self, name: str, version: int, impl: Any, deps=()) -> tuple:
        deps = list(deps) if deps else []
        if self._find(name) >= 0:
            return False, self.state(), "已注册"
        ok, reason = self._negotiate(deps)
        if not ok:
            return False, self.state(), reason
        good, _, fail_reason = self._try(self._backend.register, name, impl)
        if not good:
            return False, self.state(), fail_reason
        enabled = self._backend.is_enabled(name)
        self._entries.append([name, version, True if enabled is None else bool(enabled),
                              impl, [], list(deps)])
        self._audit.append(f"注册 {self.layer}/{name} v{version}")
        return True, self.state(), "注册完成"

    def toggle(self, name: str, on: bool) -> tuple:
        i = self._find(name)
        if i < 0:
            return False, self.state(), "未注册"
        entry = self._entries[i]
        if on and not entry[2]:
            ok, reason = self._negotiate(entry[5])
            if not ok:
                return False, self.state(), reason
            good, _, fail_reason = self._try(self._backend.enable, name, entry[3])
            if not good:
                return False, self.state(), fail_reason
            entry[2] = True
        elif entry[2] == bool(on):
            return True, self.state(), "无变化"
        else:
            good, _, fail_reason = self._try(self._backend.disable, name)
            if not good:
                return False, self.state(), fail_reason
            entry[2] = False
        self._audit.append(("启用 " if entry[2] else "停用 ") + self.layer + "/" + name)
        return True, self.state(), "启停完成"

    def upgrade(self, name: str, new_version: int, new_impl: Any) -> tuple:
        i = self._find(name)
        if i < 0:
            return False, self.state(), "未注册"
        entry = self._entries[i]
        good, _, fail_reason = self._try(self._backend.register, name, new_impl)
        if not good:
            return False, self.state(), fail_reason
        entry[4].append([entry[1], entry[3]])
        old_version = entry[1]
        entry[1] = new_version
        entry[3] = new_impl
        self._audit.append(
            f"升级 {self.layer}/{name} v{old_version}->v{new_version}")
        return True, self.state(), "升级完成"

    def rollback(self, name: str) -> tuple:
        i = self._find(name)
        if i < 0:
            return False, self.state(), "未注册"
        entry = self._entries[i]
        if not entry[4]:
            return False, self.state(), "无历史"
        prev_version, prev_impl = entry[4][-1]
        good, _, fail_reason = self._try(self._backend.register, name, prev_impl)
        if not good:
            return False, self.state(), fail_reason
        entry[4].pop()
        entry[1] = prev_version
        entry[3] = prev_impl
        self._audit.append(f"回滚 {self.layer}/{name}->v{prev_version}")
        return True, self.state(), "回滚完成"

    def negotiate(self, name: str, deps) -> tuple:
        """只读依赖协商（名参数与 Matha 面签名对齐，语义上不参与判定）。"""
        ok, reason = self._negotiate(deps)
        return ok, self.state(), reason
