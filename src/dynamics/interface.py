"""动态语义接口 —— 核心只声明契约，严禁硬编码任何具体执行实现。

对应「插件化彻底隔离风险」的四条要求在**执行语义**维度的落地：

1. **标准接口**：:class:`DynamicSemanticsBackend` 协议 + 中性 :class:`DecodedInstr`
   与 :class:`MachineView`。内核 / 执行器只依赖这三者；具体如何解码并执行一条
   RV32IM 指令，本层一概不知。
2. **核心保持纯净**：仅标准库，不 import 执行器内部（rv32sim / mbc.vm 等），
   与基础指令集、SPIKE MBR1 契约正交 —— 加载与否都不改执行器既有行为。
3. **外部插件实现**：插件（如 :mod:`src.dynamics.dynamic_semantics_plugin`）实现
   本协议并登记自身；执行器代码零改动。
4. **动态加载**：:func:`load_plugin` 显式加载并激活；未加载时
   :func:`active_backend` 返回 ``None``，:func:`execute_or_default` 走执行器原有
   分支 —— 核心仍是极简、极速、零风险的基础执行链。

``MachineView`` 刻意只暴露寄存器 / 访存 / 停机这些**最小动作面**，插件据此驱动
一台机器却拿不到执行器的任何私有成员（``ram`` 数组、``x`` 列表等），与
``PluginContext 不持有 VM 引用`` 的既有红线同构。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

# ============================================================
# 中性指令 / 机器视图（插件唯一可见的执行数据形状）
# ============================================================


@dataclass(frozen=True)
class DecodedInstr:
    """一条已解码指令的中性表示（覆盖 RV32IM 常规格式所需字段）。

    执行器在集成步把自身解码结果映射到这里；``op`` 为规范助记符（如 ``"add"``、
    ``"lw"``、``"beq"``），rd/rs1/rs2 为寄存器号，imm 为已符号扩展的立即数/偏移，
    pc 为本指令地址。本层不约束 op 取值集合 —— 由插件自行声明 ``supports``。
    """

    op: str
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: int = 0
    pc: int = 0


@runtime_checkable
class MachineView(Protocol):
    """插件驱动一台机器所能用的**最小动作面**（不暴露任何执行器私有成员）。"""

    def read_reg(self, idx: int) -> int: ...

    def write_reg(self, idx: int, value: int) -> None: ...

    def load(self, addr: int, width: int) -> int: ...

    def store(self, addr: int, value: int, width: int) -> None: ...

    def pc(self) -> int: ...

    def set_pc(self, value: int) -> None: ...

    def halt(self, exit_code: int) -> None: ...


@runtime_checkable
class DynamicSemanticsBackend(Protocol):
    """动态指令语义后端契约。

    实现方须保证：``supports`` 为纯判断、无副作用；``execute`` 只经
    :class:`MachineView` 动作面推进机器，对**不落地**的指令返回 ``False``
    （交回执行器原生分支或显式报错），绝不静默吞掉或伪造成功。
    """

    @property
    def name(self) -> str:
        ...

    def supports(self, instr: DecodedInstr) -> bool:
        ...

    def execute(self, instr: DecodedInstr, machine: MachineView) -> bool:
        """执行该指令；处理了返回 ``True``，未处理返回 ``False``（回退原生）。"""
        ...


class DynamicSemanticsNotWired(RuntimeError):
    """空壳插件对「被要求执行但语义尚未接线」的显式失败信号。

    诚实红线：预埋骨架宁可抛此显式异常，也绝不把未实现指令当 nop 静默放过。
    """


# ============================================================
# 注册表（进程内；默认空 → 零成本、零影响）
# ============================================================

_BACKENDS: dict[str, DynamicSemanticsBackend] = {}
_ACTIVE: str | None = None

#: 短名 -> 模块路径。load_plugin 优先查此表，也接受完整点分路径。
_BUILTIN_ALIASES: dict[str, str] = {
    "dynamic": "src.dynamics.dynamic_semantics_plugin",
    "dynamic_semantics": "src.dynamics.dynamic_semantics_plugin",
    "dynamic_semantics_plugin": "src.dynamics.dynamic_semantics_plugin",
}


def register_backend(backend: DynamicSemanticsBackend, *, activate: bool = False) -> None:
    global _ACTIVE
    if not isinstance(backend, DynamicSemanticsBackend):
        raise TypeError(
            f"对象未实现 DynamicSemanticsBackend 协议：{type(backend).__name__}")
    _BACKENDS[backend.name] = backend
    if activate or _ACTIVE is None:
        _ACTIVE = backend.name


def unregister_backend(name: str) -> bool:
    global _ACTIVE
    if name not in _BACKENDS:
        return False
    del _BACKENDS[name]
    if _ACTIVE == name:
        _ACTIVE = next(iter(_BACKENDS), None)
    return True


def set_active(name: str | None) -> None:
    if name is not None and name not in _BACKENDS:
        raise KeyError(f"未登记的后端：{name!r}（先 load_plugin 或 register_backend）")
    global _ACTIVE
    _ACTIVE = name


def active_backend() -> DynamicSemanticsBackend | None:
    """当前生效后端；未加载任何插件时为 ``None``（核心保持极简零风险）。"""
    return _BACKENDS.get(_ACTIVE) if _ACTIVE else None


def load_plugin(spec: str) -> DynamicSemanticsBackend:
    """动态加载并激活一个动态语义插件。

    ``spec`` 可为短名（见 :data:`_BUILTIN_ALIASES`，如 ``"dynamic"``）或完整点分
    模块路径。模块须暴露模块级 ``PLUGIN``（实现 :class:`DynamicSemanticsBackend`）。
    加载失败抛原异常，绝不静默降级为假成功。
    """
    module_path = _BUILTIN_ALIASES.get(spec, spec)
    module = importlib.import_module(module_path)
    backend = getattr(module, "PLUGIN", None)
    if backend is None:
        raise AttributeError(
            f"模块 {module_path} 未导出 PLUGIN（应为 DynamicSemanticsBackend 实例）")
    register_backend(backend, activate=True)
    return backend


def loaded_names() -> list[str]:
    return sorted(_BACKENDS)


# ============================================================
# 执行入口：执行器集成点（本步仅提供函数，尚未接入 SPIKE / mbc）
# ============================================================


def execute_or_default(instr: DecodedInstr, machine: MachineView,
                       native: Callable[[DecodedInstr, MachineView], None]) -> bool:
    """让当前生效后端尝试执行 ``instr``；不落地则调用执行器原生 ``native``。

    返回 ``True`` 表示由插件语义处理，``False`` 表示走了原生分支。未加载插件时
    （``active_backend() is None``）恒走原生，行为与未接入前完全一致。
    """
    backend = active_backend()
    if backend is not None and backend.supports(instr):
        if backend.execute(instr, machine):
            return True
    native(instr, machine)
    return False


__all__ = [
    "DecodedInstr", "MachineView", "DynamicSemanticsBackend",
    "DynamicSemanticsNotWired",
    "register_backend", "unregister_backend", "set_active", "active_backend",
    "load_plugin", "loaded_names",
    "execute_or_default",
]
