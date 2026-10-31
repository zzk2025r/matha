"""全动态 RV32IM 语义插件 —— P1-4 的**空壳预埋**（opt-in，零依赖，尚未接线）。

本模块给出 :class:`src.dynamics.interface.DynamicSemanticsBackend` 的一个骨架实现:
接口、注册、加载路径全部就位,但**不落地任何真实指令语义**——

  * :meth:`supports` 恒返回 ``False``（不认领任何指令,故不会遮蔽执行器原生分支）;
  * :meth:`execute` 被显式调用时抛 :class:`DynamicSemanticsNotWired`（诚实:被要求
    执行未接线语义即显式失败,绝不把未知指令当 nop 静默放过、也不伪造成功）。

因此加载本骨架**不会改变任何现有执行行为**:SPIKE / mbc 仍走各自原生路径。它是
把 P1-4「全动态语义」能力**完美预埋**进插件框架的占位契约——待后续按下方扩展点
逐条填充,且填充过程同样关在本插件内,内核 / 执行器零改动。

扩展点（后续实现,均在插件层,不触碰核心）：
    1. 解码映射:把 RV32IM 各 opcode/funct3/funct7 归一为 ``DecodedInstr.op``。
    2. 指令语义:在 ``_HANDLERS`` 注册 add/sub/and/or/xor/sll/srl/sra/slt(u)/
       lui/auipc/jal/jalr/branch/lw/lh/lb/sw/sh/sb/mul(u)/div(u)/rem(u) 处理器,
       仅经 ``MachineView`` 的 read_reg/write_reg/load/store/set_pc/halt 动作面推进。
    3. 认领策略:``supports`` 改为「op ∈ 已注册处理器」,使未覆盖指令仍回退原生
       的显式报错纪律,保持与 SPIKE「未知指令即抛错」一致的诚实边界。
"""
from __future__ import annotations

from src.dynamics.interface import (
    DecodedInstr,
    DynamicSemanticsBackend,
    DynamicSemanticsNotWired,
    MachineView,
)

#: 已接线的指令助记符 -> 处理器。骨架阶段为空;填充后 supports 据此认领。
_HANDLERS: dict[str, "object"] = {}


class DynamicSemanticsPlugin(DynamicSemanticsBackend):
    """全动态 RV32IM 语义后端（当前为空壳预埋,不落地任何指令）。"""

    @property
    def name(self) -> str:
        return "dynamic_semantics_plugin"

    def supports(self, instr: DecodedInstr) -> bool:
        """骨架阶段恒 False:不认领任何指令,执行器原生分支不受影响。"""
        return instr.op in _HANDLERS  # 空表 → 永远 False

    def execute(self, instr: DecodedInstr, machine: MachineView) -> bool:
        """被显式要求执行未接线语义时,抛显式失败,绝不静默伪造成功。"""
        if instr.op not in _HANDLERS:
            raise DynamicSemanticsNotWired(
                f"动态语义尚未接线：{instr.op!r}（P1-4 空壳预埋,扩展点见模块 docstring）")
        handler = _HANDLERS[instr.op]
        return bool(handler(instr, machine))

    # ---- 供后续填充期自检的只读视图（不参与执行主路径）----
    def wired_ops(self) -> tuple[str, ...]:
        return tuple(sorted(_HANDLERS))


#: 模块级插件实例:供 load_plugin 读取并登记激活（骨架阶段激活后仍不改行为）。
PLUGIN = DynamicSemanticsPlugin()


__all__ = ["DynamicSemanticsPlugin", "PLUGIN", "DynamicSemanticsNotWired"]
