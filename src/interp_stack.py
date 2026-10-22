"""显式栈协议（Contract First）——Trampoline 求值机。

本模块**只定义协议与不依赖业务语义的执行内核**，不触碰 ``interp.py`` 的
现有递归实现。它是「契约优先 + 增量绞杀」重构的第一块地基：先把 Frame /
Instruction / ControlSignal 的数据结构与 trampoline 状态机固定下来，再用
影子执行器（shadow executor）在深嵌套 Lambda / 尾递归等最苛刻场景上验证
协议闭环，最后按「表达式 → 语句 → 函数调用」逐模块替换 interp.py 的递归。

设计目标
--------
1. **消除解释器自身宿主递归**：``_eval`` / ``_exec_stmt`` / ``_call_lambda``
   之间的 Python 互递归（223 处调用点）改为「显式帧栈 + trampoline 主循环」。
2. **用户程序级调用栈独立**：Matha 函数的深递归落在堆内存帧栈上，完全绕开
   CPython 的 ``sys.setrecursionlimit``，实现「无限深」递归。
3. **控制流信号显式化**：break / continue / return / throw 不再借用 Python
   异常穿越宿主栈，而是作为 ``ControlSignal`` 在帧栈上显式传播。

核心抽象
--------
``Machine``
    trampoline 主循环与帧栈宿主。``run(root)`` 驱动执行直到栈空。

``Frame``
    一个待恢复的计算上下文。子表达式/子语句求值完成后，结果通过
    ``resume(machine, value)`` 回填到父帧，父帧据此继续推进。

``Instruction``
    一个「推进指令」：``step(machine) -> None``。它要么直接产生值
    （``machine.return_value``），要么压入一个 ``Frame`` 并请求继续
    （``machine.eval(child, frame)``）。

``ControlSignal``
    break/continue/return/throw 的显式载体。帧可选择「处理」或「透传」它，
    从而实现与 Python 异常等价但无栈依赖的控制流。

契约约定
--------
- 帧栈是**唯一**的执行状态载体；machine 不递归调用任何 ``step``/``resume``。
- ``eval`` / ``exec`` 只**压栈**，绝不直接调用子节点的求值——保证 trampoline
  回到主循环，宿主栈深度恒为 O(1)。
- ``return_value`` 是「当前帧已完成」的载荷；主循环每轮把载荷喂给栈顶帧。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ============================================================
# 控制流信号
# ============================================================

class ControlSignal:
    """控制流信号的基类（显式传播，不依赖 Python 异常穿越宿主栈）。

    子类：
      - ``BreakSignal``    —— 中断最近一层循环
      - ``ContinueSignal`` —— 跳到最近一层循环的下一次迭代
      - ``ReturnSignal``   —— 从最近一层函数返回（携带 value）
      - ``ThrowSignal``    —— 抛出运行时错误（携带 exc）
    """

    __slots__ = ()


class BreakSignal(ControlSignal):
    __slots__ = ()


class ContinueSignal(ControlSignal):
    __slots__ = ()


@dataclass
class ReturnSignal(ControlSignal):
    value: Any = None


@dataclass
class ThrowSignal(ControlSignal):
    exc: BaseException = None


# 单例：break / continue 无载荷，复用实例省分配。
BREAK = BreakSignal()
CONTINUE = ContinueSignal()


# ============================================================
# Frame —— 可恢复的计算上下文
# ============================================================

class Frame:
    """帧：一个等待子结果回填的计算上下文。

    子类须覆写 :meth:`resume`，``value`` 是子求值/子执行产生的结果载荷。
    若帧处理了控制流信号（例如循环帧消费 BREAK），不再向父帧传播。
    未处理的控制流信号由 :meth:`handle` 的默认实现向上抛出（``raise``
    语义由 Machine 捕获并转交下一帧）。
    """

    __slots__ = ("machine",)

    def __init__(self, machine: "Machine"):
        self.machine = machine

    def resume(self, value: Any) -> None:
        """子结果 ``value`` 回填到本帧；帧据此压入后续指令或弹出并回填父帧。"""
        raise NotImplementedError

    def handle(self, signal: ControlSignal) -> bool:
        """处理控制流信号。返回 True 表示已消费（停止传播），False 表示继续向上抛。

        默认不处理；循环帧 / 函数帧覆写以消费 BREAK / CONTINUE / RETURN。
        """
        return False

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<{type(self).__name__}>"


# 一个「续体」：把子结果映射为父帧的推进。用于把 `eval(child, k)` 编译成帧。
ValueCont = Callable[[Any], None]


class CallbackFrame(Frame):
    """由普通 Python 回调构造的帧（轻量续体包装）。

    ``on_value(value)`` 在子结果回填时被调用，内部可再次 ``machine.eval/exec``。
    存在意义：让业务侧能用一个闭包表达「拿到子值后做什么」，而无需为每个
    组合子手写 Frame 子类。
    """

    __slots__ = ("on_value", "on_signal")

    def __init__(self, machine: "Machine", on_value: ValueCont,
                 on_signal: Optional[Callable[[ControlSignal], bool]] = None):
        super().__init__(machine)
        self.on_value = on_value
        self.on_signal = on_signal

    def resume(self, value: Any) -> None:
        self.on_value(value)

    def handle(self, signal: ControlSignal) -> bool:
        if self.on_signal is not None:
            return self.on_signal(signal)
        return False


# ============================================================
# Instruction —— 推进指令
# ============================================================

class Instruction:
    """推进指令：``step(machine)`` 推进执行一步。

    约定见模块 docstring：要么直接产生值，要么压帧请求继续。
    """

    __slots__ = ()

    def step(self, machine: "Machine") -> None:
        raise NotImplementedError


class Thunk(Instruction):
    """由普通 Python 回调包装的指令（业务侧常用入口）。"""

    __slots__ = ("fn",)

    def __init__(self, fn: Callable[["Machine"], None]):
        self.fn = fn

    def step(self, machine: "Machine") -> None:
        self.fn(machine)


# ============================================================
# Machine —— trampoline 主循环与帧栈宿主
# ============================================================

class Machine:
    """显式帧栈执行机。

    执行状态全部落在 ``self.frames``（列表即栈）与 ``self.return_value``。
    ``step`` / ``eval`` / ``exec`` 均**只压栈**，绝不递归调用，宿主栈深度
    恒为 O(1)（与 Matha 程序嵌套深度无关）。
    """

    def __init__(self, max_steps: Optional[int] = None):
        self.frames: list[Frame] = []
        self.return_value: Any = None
        # _pending：本步希望执行的指令（主循环下一轮消费），保证不递归。
        self._pending: Optional[Instruction] = None
        # 防死循环护栏（None = 不限；用于测试/调试）。
        self.max_steps = max_steps
        self.steps = 0
        self._current_signal: Optional[ControlSignal] = None
        self._dispatcher = None

    # ---------- 指令投递 ----------

    def push_instruction(self, instr: Instruction) -> None:
        """投递一个指令，主循环下一轮执行（不递归）。"""
        self._pending = instr

    def call(self, fn: Callable[["Machine"], None]) -> None:
        """投递一个 Python 回调作为指令。"""
        self._pending = Thunk(fn)

    # ---------- 求值/执行（只压栈） ----------

    def eval(self, node: Any, frame: Frame) -> None:
        """求值 ``node``，结果回填到 ``frame``。

        默认实现：压入 ``frame``，投递一个「经 dispatcher 求值 node」的指令。
        dispatcher 由 :meth:`bind` 注入（业务侧 AST 分派器）。
        """
        self.frames.append(frame)
        if self._dispatcher is None:
            raise RuntimeError("Machine 未绑定 dispatcher")
        self.push_instruction(_EvalDispatch(node, self._dispatcher))

    def exec(self, node: Any, frame: Frame) -> None:
        """执行语句 ``node``，完成后以 ``None`` 回填 ``frame``。"""
        self.frames.append(frame)
        if self._dispatcher is None:
            raise RuntimeError("Machine 未绑定 dispatcher")
        self.push_instruction(_ExecDispatch(node, self._dispatcher))

    # ---------- 返回值 ----------

    def return_value_now(self, value: Any) -> None:
        """当前指令直接产出一个值（主循环下一轮喂给栈顶帧）。"""
        self.return_value = value

    # ---------- 主循环 ----------

    def run(self, root: Instruction) -> Any:
        """驱动 trampoline 直到帧栈空，返回根结果。"""
        self._pending = root
        while self._pending is not None or self.frames:
            if self.max_steps is not None and self.steps > self.max_steps:
                raise RuntimeError("Machine 步数超限（疑似死循环）")
            self.steps += 1
            if self._pending is not None:
                instr = self._pending
                self._pending = None
                try:
                    instr.step(self)
                except ControlSignal as sig:
                    # 指令直接抛出的控制流：交给帧栈处理
                    self._propagate_signal(sig)
                continue
            # 无待执行指令 → 有子结果需回填栈顶帧
            if self.frames:
                self._resume_top()

    def _resume_top(self) -> None:
        frame = self.frames.pop()
        if self._current_signal is not None:
            sig = self._current_signal
            self._current_signal = None
            if not frame.handle(sig):
                # 帧不处理 → 继续向上传播
                self._propagate_signal(sig)
                return
            # 帧消费了信号：不再回填普通值
            return
        value = self.return_value
        self.return_value = None
        frame.resume(value)

    # ---------- 信号传播 ----------

    def raise_signal(self, signal: ControlSignal) -> None:
        """从当前指令抛出信号（模拟 raise）。"""
        self._propagate_signal(signal)

    def _propagate_signal(self, signal: ControlSignal) -> None:
        """把信号交给最近的帧处理；无人处理则作为未捕获错误终止。"""
        while self.frames:
            frame = self.frames.pop()
            if frame.handle(signal):
                return
        # 无帧可处理
        if isinstance(signal, ThrowSignal):
            raise signal.exc
        if isinstance(signal, ReturnSignal):
            # 顶层 return：trampoline 视为正常结束，记录返回值
            self.return_value = signal.value
            return
        # 顶层 break/continue：忽略（或视为无操作）
        return

    # ---------- dispatcher 绑定 ----------

    def bind(self, dispatcher: "Dispatcher") -> None:
        self._dispatcher = dispatcher


class _EvalDispatch(Instruction):
    __slots__ = ("node", "dispatcher")

    def __init__(self, node, dispatcher):
        self.node = node
        self.dispatcher = dispatcher

    def step(self, machine):
        self.dispatcher.eval(self.node, machine)


class _ExecDispatch(Instruction):
    __slots__ = ("node", "dispatcher")

    def __init__(self, node, dispatcher):
        self.node = node
        self.dispatcher = dispatcher

    def step(self, machine):
        self.dispatcher.exec(self.node, machine)


# ============================================================
# Dispatcher —— AST 节点 → 帧/指令 的分派协议
# ============================================================

class Dispatcher:
    """AST 分派器协议：把节点求值/执行编译为帧栈操作。

    实现者（interp.py 侧的适配器）按节点类型注册处理器：

        dispatcher.on_eval(ast.IntegerLit, handler)
        dispatcher.on_exec(ast.Output, handler)

    ``handler(machine, node)`` 内部只允许调用 ``machine.eval`` / ``machine.exec``
    / ``machine.return_value_now`` / ``machine.raise_signal``，不得递归。
    """

    __slots__ = ("_eval_handlers", "_exec_handlers", "fallback_eval", "fallback_exec")

    def __init__(self):
        self._eval_handlers: dict[type, Callable] = {}
        self._exec_handlers: dict[type, Callable] = {}
        self.fallback_eval: Optional[Callable] = None
        self.fallback_exec: Optional[Callable] = None

    def on_eval(self, node_type: type, handler: Callable) -> "Dispatcher":
        self._eval_handlers[node_type] = handler
        return self

    def on_exec(self, node_type: type, handler: Callable) -> "Dispatcher":
        self._exec_handlers[node_type] = handler
        return self

    def eval(self, node, machine: "Machine") -> None:
        handler = self._eval_handlers.get(type(node), self.fallback_eval)
        if handler is None:
            raise RuntimeError(f"无求值处理器: {type(node).__name__}")
        handler(machine, node)

    def exec(self, node, machine: "Machine") -> None:
        handler = self._exec_handlers.get(type(node), self.fallback_exec)
        if handler is None:
            raise RuntimeError(f"无执行处理器: {type(node).__name__}")
        handler(machine, node)


__all__ = [
    "Machine",
    "Frame",
    "CallbackFrame",
    "Instruction",
    "Thunk",
    "Dispatcher",
    "ControlSignal",
    "BreakSignal",
    "ContinueSignal",
    "ReturnSignal",
    "ThrowSignal",
    "BREAK",
    "CONTINUE",
]
