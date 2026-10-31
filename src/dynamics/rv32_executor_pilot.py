"""RV32 执行器试点 —— 可选的**生产集成入口**（执行器中立驱动器）。

第四步「端到端试点」把插件逐条驱动 RV32I 程序的能力落在了测试里。本模块把
那段**驱动逻辑**沉淀为一个可复用的生产入口，同时严守 :mod:`src.dynamics.interface`
声明的隔离红线：

- **执行器无关**：本模块只认中性契约（:class:`DecodedInstr` / :class:`MachineView`
  与 :func:`execute_or_default`），**绝不 import 任何具体执行器**（``rv32sim`` /
  ``mbc.vm`` / ``baremetal/**`` 等）。知道 SPIKE 长什么样的适配器留在调用方
  （工具 / 测试侧），耦合方向单向：适配器同时 import 执行器与本入口，本入口却
  不知道执行器存在 —— 与「原生执行器对插件零感知」红线同构。
- **插件生命周期不外溢**：本入口未激活任何后端时才会 ``load_plugin`` 并在返回时
  复位为 ``None``，绝不把插件停在调用方的进程里造成隐性副作用；若调用方已自行
  激活后端，则本入口原样复用、不做复位。
- **诚实覆盖**：默认要求每条取到的指令都被当前后端 ``supports`` **且真正落地**；
  无论后端不认领（``supports`` 为假），还是认领却未落地（``supports`` 真而
  ``execute`` 假，如 CSR 若机器未探测到 ``csr_read/csr_write``、非复位 ``ecall``），
  都显式抛 :class:`PilotUnsupported`，绝不静默当 nop 放过（与契约的
  ``DynamicSemanticsNotWired`` 精神一致）。确需回退原生时，须显式传
  ``require_plugin_coverage=False`` 并提供 ``native`` 回调，其回退指令会被记入
  返回报告，绝不隐藏。若同时把后端置为 ``None``，即构成**纯原生跑法**（不加载任何
  插件的基准对照，与契约 ``execute_or_default``「未插件恒走原生」同义）。

PC 推进约定（顺序执行模型）：插件仅在控制转移时调用 ``set_pc``；本入口经可选的
``next_pc()`` 能力探测读取跳转后地址（与插件对机器 ``csr_read/csr_write`` 的鸭子
类型可选探测同构），未提供者按 ``pc + step_over``（RV32 定宽 4）顺序推进。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.dynamics.interface import (
    DecodedInstr,
    MachineView,
    active_backend,
    execute_or_default,
    load_plugin,
    set_active,
)

__all__ = [
    "PilotReport", "PilotRunaway", "PilotUnsupported", "drive_program",
]

_M32 = 0xFFFFFFFF


def _u32(value: int) -> int:
    return value & _M32


class PilotRunaway(RuntimeError):
    """程序在步数预算内未停机（疑似死循环）—— 显式失败，绝不无限自旋。"""


class PilotUnsupported(RuntimeError):
    """取到一条当前后端 ``supports`` 为假的指令（要求全覆盖时的诚实护栏）。"""


@dataclass(frozen=True)
class PilotReport:
    """一次驱动运行的结果摘要。"""

    steps: int
    end_pc: int
    halted: bool
    native_fallback_ops: tuple[str, ...] = ()

    @property
    def fully_plugin_driven(self) -> bool:
        return not self.native_fallback_ops


# 回调协议（调用方用具体执行器把它们喂进来；本模块不认识任何执行器类型）。
FetchFn = Callable[[int], int]                                   # pc -> 指令字
DecodeFn = Callable[[int, int], DecodedInstr]                   # (word, pc) -> 中性指令
ViewFactory = Callable[[int], MachineView]                      # pc -> 本步 MachineView
HaltedFn = Callable[[], bool]                                   # -> 机器是否已停机
NativeFn = Callable[[DecodedInstr, MachineView], None]          # 未落地指令的原生兜底


def _next_pc(view: MachineView, pc: int, step_over: int) -> int:
    """可选能力探测：适配器实现 ``next_pc()`` 则用其返回的下一地址（None=顺序）。"""
    probe = getattr(view, "next_pc", None)
    if callable(probe):
        value = probe()
        if value is not None:
            return _u32(value)
    return _u32(pc + step_over)


def drive_program(
    *,
    entry_pc: int,
    fetch: FetchFn,
    decode: DecodeFn,
    view_factory: ViewFactory,
    is_halted: HaltedFn,
    native: NativeFn | None = None,
    max_steps: int = 1_000_000,
    step_over: int = 4,
    ensure_backend: str | None = "dynamic",
    require_plugin_coverage: bool = True,
) -> PilotReport:
    """逐条驱动一台机器直到停机，指令语义交由当前生效的动态语义后端处理。

    参数（全部为回调，本入口不持有任何执行器对象）：

    - ``entry_pc``：程序起始地址。
    - ``fetch(pc)`` -> 指令字（32 位）。
    - ``decode(word, pc)`` -> :class:`DecodedInstr`。
    - ``view_factory(pc)`` -> 本步的 :class:`MachineView`（适配器把寄存器 / 访存 /
      MMIO / 停机代理给真实执行器；可选实现 ``next_pc()`` 回报跳转后地址）。
    - ``is_halted()`` -> 机器是否已停机（循环退出条件）。
    - ``native``：``require_plugin_coverage=False`` 时，未落地指令的兜底处理。
    - ``ensure_backend``：无生效后端时自动加载该插件（默认 ``"dynamic"``）；运行
      结束若后端由本次调用激活，则复位为 ``None``，不留副作用。传 ``None`` 且不
      要求插件全覆盖时，即为**纯原生跑法**（不激活任何插件的基准对照）。

    返回 :class:`PilotReport`（步数 / 结束 pc / 是否停机 / 回退原生的指令序列）。
    停机那一步之后不再推进 pc，故 ``end_pc`` 即 halt 现场的指令地址。
    """
    backend = active_backend()
    activated_here = False
    if backend is None and ensure_backend is not None:
        backend = load_plugin(ensure_backend)
        activated_here = True
    if backend is None and require_plugin_coverage:
        raise ValueError(
            "无生效的动态语义后端：请传入 ensure_backend 或先 load_plugin/register_backend，"
            "或显式置 require_plugin_coverage=False 走纯原生跑法")
    if backend is None and native is None:
        raise ValueError("纯原生跑法（无后端）必须提供 native 兜底回调")

    fallbacks: list[str] = []

    def _native(instr: DecodedInstr, view: MachineView) -> None:
        fallbacks.append(instr.op)
        if native is not None:
            native(instr, view)

    pc = _u32(entry_pc)
    steps = 0
    try:
        while not is_halted():
            if steps >= max_steps:
                raise PilotRunaway(f"试点：疑似死循环（超过 {max_steps} 步仍未停机）")
            instr = decode(fetch(pc), pc)
            view = view_factory(pc)
            if require_plugin_coverage:
                # 上面已保证：要求全覆盖时 backend 必非 None（否则已 ValueError）
                assert backend is not None
                if not backend.supports(instr):
                    raise PilotUnsupported(
                        f"未接线的指令 {instr.op!r} @pc=0x{pc:08X}（当前后端不覆盖）")
                if not execute_or_default(instr, view, _native):
                    # 后端认领却未落地（supports=True/execute=False，如 CSR 未探测到
                    # csr_read/write、非复位 ecall）：同样显式失败，绝不静默当 nop。
                    raise PilotUnsupported(
                        f"后端认领但未落地的指令 {instr.op!r} @pc=0x{pc:08X}")
            else:
                execute_or_default(instr, view, _native)
            if is_halted():
                break                        # 停机步不再推进 PC：end_pc 停在 halt 现场
            pc = _next_pc(view, pc, step_over)
            steps += 1
    finally:
        if activated_here:
            set_active(None)

    return PilotReport(
        steps=steps,
        end_pc=pc,
        halted=bool(is_halted()),
        native_fallback_ops=tuple(fallbacks),
    )
