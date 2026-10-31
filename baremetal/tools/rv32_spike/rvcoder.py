# -*- coding: utf-8 -*-
"""P6 SPIKE：RV32IM 指令编码 + 最小发射器（M3V 字节码 → RV32 机器码）。

与 `src/mbc/native.py`（x86-64 → Windows PE64）同构的最小复刻：
  - 手工位级编码 RV32IM 指令（无汇编器、无交叉工具链）；
  - `E32` 发射器 = 标签表 + 两遍修复（分支偏移 / 绝对地址 li 对），
    范围越界与未定义标签一律显式抛 `NotSupportedRV32`，绝不静默截断。

本文件位于 baremetal/tools/ 下，与 Python 主线门禁完全隔离。
"""
from __future__ import annotations


class NotSupportedRV32(Exception):
    """SPIKE 子集之外的字节码/编码越界：显式拒绝，绝不静默产出错误机器码。"""


def _s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _u12(v: int) -> int:
    return v & 0xFFF


def _simm(v: int, bits: int) -> bool:
    half = 1 << (bits - 1)
    return -half <= v <= half - 1


# ---------------------------------------------------------------- 指令编码
# 标准 RV32IM 位域组装（R/I/S/B/U/J 六类格式）。

def _r(funct7: int, rs2: int, rs1: int, f3: int, rd: int, op: int) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _i(imm12: int, rs1: int, f3: int, rd: int, op: int) -> int:
    return (_u12(imm12) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _s(imm: int, rs2: int, rs1: int, f3: int) -> int:
    imm &= 0xFFF
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (f3 << 12) | ((imm & 0x1F) << 7) | 0x23


def _b(off: int, rs2: int, rs1: int, f3: int) -> int:
    off &= 0x1FFF
    return (((off >> 12) & 1) << 31) | (((off >> 11) & 1) << 7) | \
           (((off >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (f3 << 12) | (((off >> 1) & 0xF) << 8) | 0x63


def _u(imm20: int, rd: int, op: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | op


def _j(off: int, rd: int) -> int:
    off &= 0x1FFFFF
    return (((off >> 20) & 1) << 31) | (((off >> 1) & 0x3FF) << 21) | \
           (((off >> 11) & 1) << 20) | (((off >> 12) & 0xFF) << 12) | \
           (rd << 7) | 0x6F


# ---- R 型 ----
def ADD(rd, rs1, rs2):   return _r(0x00, rs2, rs1, 0x0, rd, 0x33)
def SUB(rd, rs1, rs2):   return _r(0x20, rs2, rs1, 0x0, rd, 0x33)
def SLT(rd, rs1, rs2):   return _r(0x00, rs2, rs1, 0x2, rd, 0x33)
def SLTU(rd, rs1, rs2):  return _r(0x00, rs2, rs1, 0x3, rd, 0x33)
def XOR(rd, rs1, rs2):   return _r(0x00, rs2, rs1, 0x4, rd, 0x33)
def OR(rd, rs1, rs2):    return _r(0x00, rs2, rs1, 0x6, rd, 0x33)
def AND(rd, rs1, rs2):   return _r(0x00, rs2, rs1, 0x7, rd, 0x33)
def SLL(rd, rs1, sh):    return _r(0x00, sh, rs1, 0x1, rd, 0x33)
def MUL(rd, rs1, rs2):   return _r(0x01, rs2, rs1, 0x0, rd, 0x33)
def DIV(rd, rs1, rs2):   return _r(0x01, rs2, rs1, 0x4, rd, 0x33)
def DIVU(rd, rs1, rs2):  return _r(0x01, rs2, rs1, 0x5, rd, 0x33)
def REM(rd, rs1, rs2):   return _r(0x01, rs2, rs1, 0x6, rd, 0x33)
def REMU(rd, rs1, rs2):  return _r(0x01, rs2, rs1, 0x7, rd, 0x33)

# ---- I 型 ----
def ADDI(rd, rs1, imm):  return _i(imm, rs1, 0x0, rd, 0x13)
def SLTI(rd, rs1, imm):  return _i(imm, rs1, 0x2, rd, 0x13)
def SLTIU(rd, rs1, imm): return _i(imm, rs1, 0x3, rd, 0x13)
def XORI(rd, rs1, imm):  return _i(imm, rs1, 0x4, rd, 0x13)
def ORI(rd, rs1, imm):   return _i(imm, rs1, 0x6, rd, 0x13)
def ANDI(rd, rs1, imm):  return _i(imm, rs1, 0x7, rd, 0x13)
def SLLI(rd, rs1, sh):   return _i(sh, rs1, 0x1, rd, 0x13)
def SRLI(rd, rs1, sh):   return _i(sh, rs1, 0x5, rd, 0x13)
def SRAI(rd, rs1, sh):   return _i(0x400 | sh, rs1, 0x5, rd, 0x13)   # funct6=010000 在 imm[11:10]
def LW(rd, rs1, off):    return _i(off, rs1, 0x2, rd, 0x03)
def LWU(rd, rs1, off):   return _i(off, rs1, 0x6, rd, 0x03)
def LB(rd, rs1, off):    return _i(off, rs1, 0x0, rd, 0x03)
def LBU(rd, rs1, off):   return _i(off, rs1, 0x4, rd, 0x03)
def SW(rs2, rs1, off):   return _s(off, rs2, rs1, 0x2)
def SB(rs2, rs1, off):   return _s(off, rs2, rs1, 0x0)

# ---- B / J / U / 系统 ----
def BEQ(rs1, rs2, off):  return _b(off, rs2, rs1, 0x0)
def BNE(rs1, rs2, off):  return _b(off, rs2, rs1, 0x1)
def BLT(rs1, rs2, off):  return _b(off, rs2, rs1, 0x4)
def BGE(rs1, rs2, off):  return _b(off, rs2, rs1, 0x5)
def BLTU(rs1, rs2, off): return _b(off, rs2, rs1, 0x6)
def BGEU(rs1, rs2, off): return _b(off, rs2, rs1, 0x7)
def JAL(rd, off):        return _j(off, rd)
def JALR(rd, rs1, off):  return _i(off, rs1, 0x0, rd, 0x67)
def LUI(rd, imm20):      return _u(imm20, rd, 0x37)
def AUIPC(rd, imm20):    return _u(imm20, rd, 0x17)
def NOP():               return ADDI(0, 0, 0)
def ECALL():             return 0x00000073

# ---- 寄存器约定 ----
ZERO, RA, SP = 0, 1, 2
T0, T1, T2 = 5, 6, 7
S0, S1, S2, S3, S4, S5 = 8, 9, 10, 11, 12, 13
A0, A1, A2, A3 = 10, 11, 12, 13
T3, T4, T5 = 28, 29, 30
# SPIKE 运行态专用寄存器（callee 不保存——SPIKE 内建例程只碰 t 系）：
SPOOL, SGLOB, SCPOOL, SUART, SEBP = S1, S2, S3, S4, 27
#   SPOOL=scratch 池基址  SGLOB=全局区基址  SCPOOL=常量池基址
#   SUART =ns16550 基址   SEBP=表达式栈指针（向上增长；栈顶值 = [SEBP-4]）


class E32:
    """最小两遍发射器：标签 → 指令下标；分支/绝对地址延后修复。

    修复点范围校验失败（B ±4KB / J ±2MB / 地址超 32 位 / li 序列外标签未定义）
    时抛 NotSupportedRV32 —— 与 native.py 的 NativeNotSupported 同一诚实纪律。
    """

    def __init__(self):
        self.code: list[int] = []
        self.labels: dict[str, int] = {}
        self._fix_br: list[tuple[int, str]] = []       # (字位, 标签) 分支/JAL
        self._fix_abs: list[tuple[int, str]] = []      # (li 首字位, 标签) 绝对地址

    # ---- 基础 ----
    def emit(self, word: int) -> None:
        self.code.append(word & 0xFFFFFFFF)

    def emit_pair(self, w1: int, w2: int) -> None:
        self.code.append(w1 & 0xFFFFFFFF)
        self.code.append(w2 & 0xFFFFFFFF)

    def label_here(self, name: str) -> None:
        if name in self.labels:
            raise NotSupportedRV32(f"重复标签 {name!r}")
        self.labels[name] = len(self.code)

    def off_of(self, label: str) -> int:
        if label not in self.labels:
            raise NotSupportedRV32(f"未定义标签 {label!r}")
        return self.labels[label] * 4

    # ---- li（定长 2 字：LUI+ADDI；low 符号扩展，高位按拆分补偿） ----
    def li(self, rd: int, val: int) -> None:
        val &= 0xFFFFFFFF
        lo = val & 0xFFF
        if lo >= 0x800:
            lo -= 0x1000                          # 当负数看待，高位 +1 补回
        hi = (val - lo) >> 12
        self.emit(LUI(rd, hi & 0xFFFFF))
        self.emit(ADDI(rd, rd, lo))

    # ---- 常用简写 ----
    def mv(self, rd, rs):        self.emit(ADDI(rd, rs, 0))
    def addi(self, rd, rs1, imm):
        if not _simm(imm, 12):
            raise NotSupportedRV32(f"ADDI 立即数越界 {imm}")
        self.emit(ADDI(rd, rs1, imm))
    def add(self, rd, rs1, rs2):  self.emit(ADD(rd, rs1, rs2))
    def sub(self, rd, rs1, rs2):  self.emit(SUB(rd, rs1, rs2))
    def mul(self, rd, rs1, rs2):  self.emit(MUL(rd, rs1, rs2))
    def slt(self, rd, rs1, rs2):  self.emit(SLT(rd, rs1, rs2))
    def sltu(self, rd, rs1, rs2): self.emit(SLTU(rd, rs1, rs2))
    def xor(self, rd, rs1, rs2):  self.emit(XOR(rd, rs1, rs2))
    def lw(self, rd, rs1, off):
        if not _simm(off, 12):
            raise NotSupportedRV32(f"LW 偏移越界 {off}")
        self.emit(LW(rd, rs1, off))
    def sw(self, rs2, rs1, off):
        if not _simm(off, 12):
            raise NotSupportedRV32(f"SW 偏移越界 {off}")
        self.emit(SW(rs2, rs1, off))
    def ecall(self):              self.emit(ECALL())
    def nop(self):                self.emit(NOP())

    # ---- 标签式控制流 ----
    def _branch(self, mk, rs1, rs2, label: str) -> None:
        pos = len(self.code)
        self.emit(mk(rs1, rs2, 0))
        self._fix_br.append((pos, label))

    def beqz(self, rs1, label):  self._branch(BEQ, rs1, ZERO, label)
    def bnez(self, rs1, label):  self._branch(BNE, rs1, ZERO, label)
    def bltz(self, rs1, label):  self._branch(BLT, rs1, ZERO, label)
    def bgez(self, rs1, label):  self._branch(BGE, rs1, ZERO, label)

    def j(self, label: str) -> None:
        pos = len(self.code)
        self.emit(JAL(0, 0))
        self._fix_br.append((pos, label))

    def jal(self, label: str) -> None:
        pos = len(self.code)
        self.emit(JAL(RA, 0))
        self._fix_br.append((pos, label))

    def jabs(self, label: str) -> None:      # li T0 + jalr x0（绝对跳转）
        pos = len(self.code)
        self.li(T0, 0)
        self._fix_abs.append((pos, label))
        self.emit(JALR(0, T0, 0))

    def call_abs(self, label: str) -> None:  # li T0 + jalr ra（绝对调用）
        pos = len(self.code)
        self.li(T0, 0)
        self._fix_abs.append((pos, label))
        self.emit(JALR(RA, T0, 0))

    # ---- 修复 ----
    def resolve(self, code_base: int, abs_map: dict[str, int]) -> bytes:
        """把分支偏移与绝对地址回填进指令流；返回小端机器码 bytes。"""
        for pos, label in self._fix_br:
            if label not in self.labels:
                raise NotSupportedRV32(f"未定义标签 {label!r}")
            off = (self.labels[label] - pos) * 4
            word = self.code[pos]
            op = word & 0x7F
            if op == 0x63:
                if not _simm(off, 13):
                    raise NotSupportedRV32(
                        f"分支越界（RV32I B ±4KB）：{label} 偏移 {off}")
                f3 = (word >> 12) & 0x7
                rs1 = (word >> 15) & 0x1F
                rs2 = (word >> 20) & 0x1F
                self.code[pos] = _b(off, rs2, rs1, f3)
            elif op == 0x6F:
                if not (-0x100000 <= off <= 0xFFFFF):
                    raise NotSupportedRV32(
                        f"JAL 越界（±2MB）：{label} 偏移 {off}")
                rd = (word >> 7) & 0x1F
                self.code[pos] = _j(off, rd)
            else:
                raise NotSupportedRV32(f"内部：未知分支槽 op=0x{op:02X}")
        for pos, label in self._fix_abs:
            if label not in abs_map:
                raise NotSupportedRV32(f"未定义绝对标签 {label!r}（数据段？）")
            addr = abs_map[label]
            if not 0 <= addr <= 0xFFFFFFFF:
                raise NotSupportedRV32(f"绝对地址超 32 位：{label} = {addr}")
            lo = addr & 0xFFF
            if lo >= 0x800:
                lo -= 0x1000
            hi = ((addr - lo) >> 12) & 0xFFFFF
            rd = (self.code[pos] >> 7) & 0x1F
            self.code[pos] = LUI(rd, hi)
            self.code[pos + 1] = ADDI(rd, rd, lo)
        import struct as _st
        return b"".join(_st.pack("<I", w) for w in self.code)
