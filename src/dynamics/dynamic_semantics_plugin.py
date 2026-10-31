"""全动态 RV32IM 语义插件 —— P1-4 的**插件层实现**（opt-in，零依赖，内核零改动）。

本模块实现 :class:`src.dynamics.interface.DynamicSemanticsBackend`：把 RV32IM 各条
指令的**语义**逐条落地到 ``_HANDLERS``，且**只经** :class:`MachineView` 的最小动作面
（read_reg / write_reg / load / store / pc / set_pc / halt）推进机器，绝不触碰任何
执行器私有成员，也不 import ``src.kernel`` / ``sympy`` / ``numpy`` / ``scipy``。

诚实与隔离边界（与 SPIKE「未知指令即抛错」同构）：
  * :meth:`supports` 为 ``op ∈ _HANDLERS`` —— 只有**已落地语义**的指令才被认领；
    未覆盖的指令（如 ``mret`` / ``wfi`` / ``ebreak`` / 其余系统操作码）仍返回
    ``False``，交回执行器原生分支。
  * :meth:`execute` 对未落地指令抛 :class:`DynamicSemanticsNotWired`，绝不静默当
    nop、也不伪造成功。
  * SYSTEM 子集（本轮落地）：``fence``/``fence.i`` 在单 hart 顺序模型下作为无副
    作用 nop 退休；``ecall`` 仅落地执行器建模的 system_reset ABI（a7==0x6758 → halt），
    其余 a7 返回 ``False`` 交回原生（与 SPIKE「未知 ecall 抛错」同构）；CSR 读写位于寄存
    器文件之外的独立地址空间，经鸭子类型**可选**探测机器的 ``csr_read``/``csr_write``
    能力，机器未提供则该指令返回 ``False`` 回退原生（绝不假设机器有 CSR 而崩溃/伪造）。
  * 未 ``load_plugin`` 时 ``active_backend()`` 为 ``None``，``execute_or_default``
    恒走原生 —— 加载本插件与否都不改变任何现有执行行为（内核零改动）。

指令语义严格遵循 RISC-V RV32IM 规格（含以下易错边界，均有对拍/黄金锁覆盖）：
  * 32 位回绕（``_u`` / ``_s``）；移位量取 ``& 31``；
  * 有符号 / 无符号比较（slt/sltu、blt/bge vs bltu/bgeu）；
  * ``lb``/``lh`` 按位宽符号扩展，``lbu``/``lhu`` 零扩展；
  * 乘高 ``mulh``/``mulhsu``/``mulhu`` 取 64 位积的高 32 位；
  * 除零与溢出：``div``→-1、``divu``→全 1、``rem``→被除数、``remu``→被除数，
    且 ``INT_MIN / -1`` → ``INT_MIN``、``INT_MIN % -1`` → ``0``；
  * ``jalr`` 目标清最低位；分支 / 跳转仅在**发生转移**时 ``set_pc``，否则留给
    执行器顺序推进（约定：``DecodedInstr.pc`` 为**本指令地址**，链接值 = pc+4）。
"""
from __future__ import annotations

from typing import Callable

from src.dynamics.interface import (
    DecodedInstr,
    DynamicSemanticsBackend,
    DynamicSemanticsNotWired,
    MachineView,
)

_M32 = 0xFFFFFFFF


def _u(x: int) -> int:
    """低 32 位（无符号视图）。"""
    return x & _M32


def _s(x: int) -> int:
    """按 32 位补码解释为有符号整数。"""
    x &= _M32
    return x - 0x100000000 if x >= 0x80000000 else x


def _sext(v: int, bits: int) -> int:
    """把 ``bits`` 位宽的取值按补码符号扩展。"""
    mask = (1 << bits) - 1
    v &= mask
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


#: 已接线的指令助记符 -> 处理器（签名 ``(instr, machine) -> bool``）。
_HANDLERS: dict[str, Callable[[DecodedInstr, MachineView], bool]] = {}


def _op(*names: str) -> Callable:
    def deco(fn: Callable[[DecodedInstr, MachineView], bool]) -> Callable:
        for nm in names:
            _HANDLERS[nm] = fn
        return fn
    return deco


def _ra(m: MachineView, i: DecodedInstr) -> int:
    return m.read_reg(i.rs1) & _M32


def _rb(m: MachineView, i: DecodedInstr) -> int:
    return m.read_reg(i.rs2) & _M32


def _put(m: MachineView, i: DecodedInstr, val: int) -> None:
    """写回 rd；x0 恒零（写 x0 丢弃）。"""
    if i.rd:
        m.write_reg(i.rd, val & _M32)


# ============================================================
# RV32I —— R 型算术 / 逻辑
# ============================================================

@_op("add")
def _add(i, m):
    _put(m, i, _ra(m, i) + _rb(m, i)); return True


@_op("sub")
def _sub(i, m):
    _put(m, i, _s(_ra(m, i)) - _s(_rb(m, i))); return True


@_op("and")
def _and(i, m):
    _put(m, i, _ra(m, i) & _rb(m, i)); return True


@_op("or")
def _or(i, m):
    _put(m, i, _ra(m, i) | _rb(m, i)); return True


@_op("xor")
def _xor(i, m):
    _put(m, i, _ra(m, i) ^ _rb(m, i)); return True


@_op("sll")
def _sll(i, m):
    _put(m, i, _ra(m, i) << (_rb(m, i) & 31)); return True


@_op("srl")
def _srl(i, m):
    _put(m, i, _ra(m, i) >> (_rb(m, i) & 31)); return True


@_op("sra")
def _sra(i, m):
    _put(m, i, _s(_ra(m, i)) >> (_rb(m, i) & 31)); return True


@_op("slt")
def _slt(i, m):
    _put(m, i, 1 if _s(_ra(m, i)) < _s(_rb(m, i)) else 0); return True


@_op("sltu")
def _sltu(i, m):
    _put(m, i, 1 if _ra(m, i) < _rb(m, i) else 0); return True


# ============================================================
# RV32I —— I 型算术 / 逻辑（立即数）
# ============================================================

@_op("addi")
def _addi(i, m):
    _put(m, i, _ra(m, i) + _s(i.imm)); return True


@_op("andi")
def _andi(i, m):
    _put(m, i, _ra(m, i) & _s(i.imm)); return True


@_op("ori")
def _ori(i, m):
    _put(m, i, _ra(m, i) | _s(i.imm)); return True


@_op("xori")
def _xori(i, m):
    _put(m, i, _ra(m, i) ^ _s(i.imm)); return True


@_op("slli")
def _slli(i, m):
    _put(m, i, _ra(m, i) << (i.imm & 31)); return True


@_op("srli")
def _srli(i, m):
    _put(m, i, _ra(m, i) >> (i.imm & 31)); return True


@_op("srai")
def _srai(i, m):
    _put(m, i, _s(_ra(m, i)) >> (i.imm & 31)); return True


@_op("slti")
def _slti(i, m):
    _put(m, i, 1 if _s(_ra(m, i)) < _s(i.imm) else 0); return True


@_op("sltiu")
def _sltiu(i, m):
    _put(m, i, 1 if _ra(m, i) < _u(_s(i.imm)) else 0); return True


# ============================================================
# RV32I —— 上立即 / 跳转
# ============================================================

@_op("lui")
def _lui(i, m):
    _put(m, i, i.imm); return True


@_op("auipc")
def _auipc(i, m):
    _put(m, i, i.pc + i.imm); return True


@_op("jal")
def _jal(i, m):
    if i.rd:
        m.write_reg(i.rd, _u(i.pc + 4))
    m.set_pc(_u(i.pc + i.imm)); return True


@_op("jalr")
def _jalr(i, m):
    if i.rd:
        m.write_reg(i.rd, _u(i.pc + 4))
    m.set_pc(_u((_ra(m, i) + _s(i.imm)) & ~1)); return True


# ============================================================
# RV32I —— 条件分支（仅在**转移**时改写 pc）
# ============================================================

def _branch(i, m, cond: bool) -> bool:
    if cond:
        m.set_pc(_u(i.pc + i.imm))
    return True


@_op("beq")
def _beq(i, m):
    return _branch(i, m, _ra(m, i) == _rb(m, i))


@_op("bne")
def _bne(i, m):
    return _branch(i, m, _ra(m, i) != _rb(m, i))


@_op("blt")
def _blt(i, m):
    return _branch(i, m, _s(_ra(m, i)) < _s(_rb(m, i)))


@_op("bge")
def _bge(i, m):
    return _branch(i, m, _s(_ra(m, i)) >= _s(_rb(m, i)))


@_op("bltu")
def _bltu(i, m):
    return _branch(i, m, _ra(m, i) < _rb(m, i))


@_op("bgeu")
def _bgeu(i, m):
    return _branch(i, m, _ra(m, i) >= _rb(m, i))


# ============================================================
# RV32I —— load / store（地址 = rs1 + 符号扩展偏移）
# ============================================================

def _effaddr(m: MachineView, i: DecodedInstr) -> int:
    return _u(_ra(m, i) + _s(i.imm))


@_op("lw")
def _lw(i, m):
    _put(m, i, m.load(_effaddr(m, i), 4)); return True


@_op("lh")
def _lh(i, m):
    _put(m, i, _sext(m.load(_effaddr(m, i), 2), 16)); return True


@_op("lb")
def _lb(i, m):
    _put(m, i, _sext(m.load(_effaddr(m, i), 1), 8)); return True


@_op("lbu")
def _lbu(i, m):
    _put(m, i, m.load(_effaddr(m, i), 1) & 0xFF); return True


@_op("lhu")
def _lhu(i, m):
    _put(m, i, m.load(_effaddr(m, i), 2) & 0xFFFF); return True


@_op("lwu")
def _lwu(i, m):
    _put(m, i, m.load(_effaddr(m, i), 4)); return True


@_op("sb")
def _sb(i, m):
    m.store(_effaddr(m, i), _rb(m, i) & 0xFF, 1); return True


@_op("sh")
def _sh(i, m):
    m.store(_effaddr(m, i), _rb(m, i) & 0xFFFF, 2); return True


@_op("sw")
def _sw(i, m):
    m.store(_effaddr(m, i), _rb(m, i) & _M32, 4); return True


# ============================================================
# RV32M —— 乘 / 除
# ============================================================

@_op("mul")
def _mul(i, m):
    _put(m, i, _u(_ra(m, i)) * _u(_rb(m, i))); return True


@_op("mulh")
def _mulh(i, m):
    _put(m, i, (_s(_ra(m, i)) * _s(_rb(m, i))) >> 32); return True


@_op("mulhsu")
def _mulhsu(i, m):
    _put(m, i, (_s(_ra(m, i)) * _u(_rb(m, i))) >> 32); return True


@_op("mulhu")
def _mulhu(i, m):
    _put(m, i, (_u(_ra(m, i)) * _u(_rb(m, i))) >> 32); return True


@_op("div")
def _div(i, m):
    a, b = _s(_ra(m, i)), _s(_rb(m, i))
    if b == 0:
        val = -1
    elif a == -0x80000000 and b == -1:
        val = a
    else:
        q = abs(a) // abs(b)
        val = q if (a < 0) == (b < 0) else -q
    _put(m, i, val); return True


@_op("divu")
def _divu(i, m):
    a, b = _u(_ra(m, i)), _u(_rb(m, i))
    _put(m, i, 0xFFFFFFFF if b == 0 else a // b); return True


@_op("rem")
def _rem(i, m):
    a, b = _s(_ra(m, i)), _s(_rb(m, i))
    if b == 0:
        val = a
    else:
        r = abs(a) % abs(b)
        val = r if a >= 0 else -r
    _put(m, i, val); return True


@_op("remu")
def _remu(i, m):
    a, b = _u(_ra(m, i)), _u(_rb(m, i))
    _put(m, i, a if b == 0 else a % b); return True


# ============================================================
# RV32I —— SYSTEM 类：FENCE / ECALL / CSR（诚实边界见各处理器注释）
# ============================================================

#: sifive/QEMU 关停约定的 ecall ABI：a7 == 0x6758（SBI system_reset）。
_SRST = 0x6758


def _csr_io(m: MachineView):
    """探测机器的 CSR 动作面；不提供则返回 ``None``（该 CSR 指令回退原生）。

    CSR 是寄存器文件之外的独立地址空间，``MachineView`` 的最小动作面不含它，故经
    鸭子类型**可选**探测：具备 ``csr_read``/``csr_write`` 的机器才由本插件执行 CSR
    指令，否则返回 ``False`` 交回执行器原生（与隔离红线同构，不耦合任何执行器私有成员）。
    """
    rd = getattr(m, "csr_read", None)
    wr = getattr(m, "csr_write", None)
    if rd is None or wr is None:
        return None
    return rd, wr


@_op("fence", "fence.i")
def _fence(i, m):
    """内存序提示：在单 hart、顺序执行的模型下无可观测副作用 → 作为 nop 退休。

    注意：权威解释器 rv32sim 并**未实现** FENCE（遇 opcode 0x0F 直接抛错），故此指令
    无 SPIKE 对拍基准，改由规格黄金锁断言「不改动任何寄存器 / pc / 内存」。"""
    return True


@_op("ecall")
def _ecall(i, m):
    """环境调用：仅落地执行器实际建模的 system_reset ABI（a7==0x6758 → halt）。

    其余 a7 无既定 ABI → 返回 ``False`` 交回原生（与 SPIKE「未知 ecall 抛错」的显式
    失败同构），绝不把未知 ecall 当 nop 静默吞掉。"""
    if m.read_reg(17) & _M32 == _SRST:
        m.halt(m.read_reg(10))
        return True
    return False


@_op("csrrw")
def _csrrw(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    wrc(i.imm, _ra(m, i) & _M32)
    return True


@_op("csrrs")
def _csrrs(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    if i.rs1:                                  # rs1==x0 → 纯读（csrr），不写回
        wrc(i.imm, (old | _ra(m, i)) & _M32)
    return True


@_op("csrrc")
def _csrrc(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    if i.rs1:
        wrc(i.imm, (old & ~_ra(m, i)) & _M32)
    return True


@_op("csrrwi")
def _csrrwi(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    wrc(i.imm, i.rs1 & 0x1F)                    # uimm 在 rs1 字段（5 位）
    return True


@_op("csrrsi")
def _csrrsi(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    uimm = i.rs1 & 0x1F
    if uimm:
        wrc(i.imm, (old | uimm) & _M32)
    return True


@_op("csrrci")
def _csrrci(i, m):
    io = _csr_io(m)
    if io is None:
        return False
    rdc, wrc = io
    old = rdc(i.imm) & _M32
    _put(m, i, old)
    uimm = i.rs1 & 0x1F
    if uimm:
        wrc(i.imm, (old & ~uimm) & _M32)
    return True


class DynamicSemanticsPlugin(DynamicSemanticsBackend):
    """全动态 RV32IM 语义后端（语义关在本插件内，内核 / 执行器零改动）。"""

    @property
    def name(self) -> str:
        return "dynamic_semantics_plugin"

    def supports(self, instr: DecodedInstr) -> bool:
        """仅认领**已落地语义**的指令；未覆盖者回退执行器原生（诚实边界）。"""
        return instr.op in _HANDLERS

    def execute(self, instr: DecodedInstr, machine: MachineView) -> bool:
        """经 ``MachineView`` 动作面执行；未落地指令抛显式失败，绝不伪造成功。"""
        handler = _HANDLERS.get(instr.op)
        if handler is None:
            raise DynamicSemanticsNotWired(
                f"动态语义尚未接线：{instr.op!r}（未覆盖指令应经 supports=False 回退原生）")
        return bool(handler(instr, machine))

    # ---- 供自检 / 门禁使用的只读视图（不参与执行主路径）----
    def wired_ops(self) -> tuple[str, ...]:
        return tuple(sorted(_HANDLERS))


#: 模块级插件实例：供 load_plugin 读取并登记激活。
PLUGIN = DynamicSemanticsPlugin()


__all__ = ["DynamicSemanticsPlugin", "PLUGIN", "DynamicSemanticsNotWired"]
