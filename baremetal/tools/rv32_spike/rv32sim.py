# -*- coding: utf-8 -*-
"""P6 SPIKE：最小 RV32IM 指令级模拟器（宿主可跑，无需 QEMU/交叉工具链）。

只解码/执行 rv32em.py **实际发射**的指令子集，配 FE310/virt 的地址模型：
  - RAM 稀疏窗口（BASE 起）承载 code/常量池/全局/表达式栈/调用栈；
  - ns16550 UART@0x10000000：写 THR(.transmit) 收集字符，读 LSR(.status) 恒 0x60；
  - sifive_test@0x00100000：写 finish word（低 16 位 0x5555）→ 停机，
    退出码 = 高 16 位（与 QEMU virt 同一约定）；兼容旧约定 ecall(a7=0x6758)。
遇到未实现指令立即抛错（诚实：绝不静默把未知指令当 nop）。

与 qemu_virt_demo 里 tools/sim/* 的「宿主寄存器级模拟」同一纪律；产出的串口文本
再与 mbc VM 逐字节对拍（见 run_rv32_spike.py）。
"""
from __future__ import annotations

BASE = 0x80000000
RAM_SIZE = 0x400000
UART = 0x10000000
TEST = 0x00100000
SRST = 0x6758


def _s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _u32(v):
    return v & 0xFFFFFFFF


class Trap(Exception):
    pass


class RV32Sim:
    def __init__(self, elf_bytes: bytes, max_steps: int = 5_000_000):
        self.ram = bytearray(RAM_SIZE)
        self.out: list[str] = []
        self.max_steps = max_steps
        self._load_elf(elf_bytes)
        self.x = [0] * 32
        self.done = False
        self.exit_code = 0

    # ---- ELF32 载入：单 PT_LOAD ----
    def _load_elf(self, blob: bytes):
        import struct
        assert blob[:4] == b"\x7fELF", "非 ELF"
        (phoff,) = struct.unpack_from("<I", blob, 28)
        phentsize = struct.unpack_from("<H", blob, 42)[0]
        phnum = struct.unpack_from("<H", blob, 46)[0]
        self.entry = struct.unpack_from("<I", blob, 24)[0]
        for i in range(phnum):
            p = phoff + i * phentsize
            ptype, off, vaddr, _pa, filesz, memsz, _fl, _al = struct.unpack_from(
                "<IIIIIIII", blob, p)
            if ptype != 1:                       # PT_LOAD
                continue
            self.entry = vaddr
            delta = vaddr - BASE
            self.ram[delta:delta + filesz] = blob[off:off + filesz]

    # ---- 访存 ----
    def _r32(self, addr):
        import struct
        addr = _u32(addr)
        if UART <= addr < UART + 0x1000:
            return 0x60 if (addr - UART) == 5 else 0    # LSR ready
        return struct.unpack_from("<I", self.ram, addr - BASE)[0]

    def _w32(self, addr, val):
        import struct
        addr = _u32(addr)
        if UART <= addr < UART + 0x1000:
            if (addr - UART) == 0:                       # THR
                self.out.append(chr(val & 0xFF))
            return
        if TEST <= addr < TEST + 0x1000:                 # sifive_test finish
            v = _u32(val)
            if (v & 0xFFFF) in (0x5555, 0x7777):
                self.done = True
                self.exit_code = v >> 16
            return
        struct.pack_into("<I", self.ram, addr - BASE, _u32(val))

    def _r8(self, addr):
        addr = _u32(addr)
        if UART <= addr < UART + 0x1000:
            return 0x60 if (addr - UART) == 5 else 0
        return self.ram[addr - BASE]

    def _w8(self, addr, val):
        addr = _u32(addr)
        if UART <= addr < UART + 0x1000:
            if (addr - UART) == 0:
                self.out.append(chr(val & 0xFF))
            return
        self.ram[addr - BASE] = val & 0xFF

    # ---- 运行 ----
    def run(self) -> str:
        self.x[2] = 0  # SP 由 _start 的 li 显式设置
        self.x[1] = 0
        pc = self.entry
        steps = 0
        while not self.done:
            if steps > self.max_steps:
                raise Trap("步数上限（疑似死循环）")
            instr = self._r32(pc)
            pc = _u32(pc + 4)
            pc = self._step(instr, pc)
            steps += 1
        return "".join(self.out)

    def _rd(self):
        return self._rd_

    def _step(self, instr, pc):
        op = instr & 0x7F
        rd = (instr >> 7) & 0x1F
        f3 = (instr >> 12) & 0x7
        rs1 = (instr >> 15) & 0x1F
        rs2 = (instr >> 20) & 0x1F
        f7 = (instr >> 25) & 0x7F
        x = self.x

        def imm_i():
            v = (instr >> 20) & 0xFFF          # 12 位字段，须符号扩展
            return v - 0x1000 if v >= 0x800 else v

        def imm_s():
            v = ((f7 << 5) | ((instr >> 7) & 0x1F)) & 0xFFF
            return v - 0x1000 if v >= 0x800 else v

        def imm_b():
            v = (((instr >> 31) & 1) << 12) | (((instr >> 7) & 1) << 11) | \
                (((instr >> 25) & 0x3F) << 5) | (((instr >> 8) & 0xF) << 1)
            return _s32(v << 19) >> 19 if v & 0x1000 else v

        def imm_u():
            return _s32(instr & 0xFFFFF000)

        def imm_j():
            v = (((instr >> 31) & 1) << 20) | (((instr >> 12) & 0xFF) << 12) | \
                (((instr >> 20) & 1) << 11) | (((instr >> 21) & 0x3FF) << 1)
            return _s32(v << 11) >> 11 if v & 0x100000 else v

        def setrd(val):
            if rd:
                x[rd] = _s32(val)

        if op == 0x37:                                   # LUI
            setrd(imm_u())
        elif op == 0x17:                                 # AUIPC
            setrd(imm_u() + pc - 4)
        elif op == 0x33:                                 # R 型
            a, b = x[rs1], x[rs2]
            if f7 == 0x00:
                if f3 == 0x0: setrd(a + b)
                elif f3 == 0x2: setrd(1 if _s32(a) < _s32(b) else 0)    # SLT
                elif f3 == 0x3: setrd(1 if _u32(a) < _u32(b) else 0)    # SLTU
                elif f3 == 0x4: setrd(a ^ b)
                elif f3 == 0x6: setrd(a | b)
                elif f3 == 0x7: setrd(a & b)
                elif f3 == 0x1: setrd(a << (b & 31))
                elif f3 == 0x5: setrd(_u32(a) >> (b & 31))   # SRL
                else: raise Trap(f"R/0 f3={f3}")
            elif f7 == 0x20:
                if f3 == 0x0: setrd(a - b)
                elif f3 == 0x5: setrd(_s32(a) >> (b & 31))  # SRA
                else: raise Trap(f"R/32 f3={f3}")
            elif f7 == 0x01:                             # M 扩展
                if f3 == 0x0: setrd(a * b)
                elif f3 == 0x4: setrd(_trunc_div(a, b))
                elif f3 == 0x5:
                    au, bu = _u32(a), _u32(b)
                    setrd(0xFFFFFFFF if bu == 0 else au // bu)
                elif f3 == 0x6:
                    setrd(_trunc_rem(a, b))
                elif f3 == 0x7:
                    au, bu = _u32(a), _u32(b)
                    setrd(au if bu == 0 else au % bu)
                else: raise Trap(f"M f3={f3}")
            else:
                raise Trap(f"未知 R 型 funct7=0x{f7:02X}")
        elif op == 0x13:                                 # I 型 ALU
            a, imm = x[rs1], imm_i()
            if f3 == 0x0: setrd(a + imm)
            elif f3 == 0x1: setrd(a << (imm & 31))
            elif f3 == 0x2: setrd(1 if a < imm else 0)
            elif f3 == 0x3: setrd(1 if _u32(a) < _u32(imm) else 0)
            elif f3 == 0x4: setrd(a ^ imm)
            elif f3 == 0x5:
                sh = imm & 31
                sub = ((instr >> 20) & 0xFFF) >> 6          # funct6（imm[11:6]）
                if sub == 0x00:
                    setrd(_u32(a) >> sh)                    # SRLI
                elif sub == 0x10:
                    setrd(_s32(a) >> sh)                    # SRAI
                else:
                    raise Trap(f"I/shift funct6=0x{sub:02X}")
            elif f3 == 0x6: setrd(a | imm)
            elif f3 == 0x7: setrd(a & imm)
        elif op == 0x03:                                 # LOAD
            addr = x[rs1] + imm_i()
            if f3 == 0x2: setrd(_s32(self._r32(addr)))
            elif f3 == 0x0:
                b = self._r8(addr); setrd(b - 256 if b & 0x80 else b)
            elif f3 == 0x4: setrd(self._r8(addr))
            elif f3 == 0x6: setrd(self._r32(addr))
            else: raise Trap(f"LOAD f3={f3}")
        elif op == 0x23:                                 # STORE
            addr = x[rs1] + imm_s()
            if f3 == 0x2: self._w32(addr, x[rs2])
            elif f3 == 0x0: self._w8(addr, x[rs2])
            else: raise Trap(f"STORE f3={f3}")
        elif op == 0x63:                                 # BRANCH
            a, b = x[rs1], x[rs2]
            taken = {0x0: a == b, 0x1: a != b, 0x4: a < b, 0x5: a >= b,
                     0x6: _u32(a) < _u32(b), 0x7: _u32(a) >= _u32(b)}[f3]
            if taken:
                return _u32(pc - 4 + imm_b())
        elif op == 0x6F:                                 # JAL
            if rd: setrd(pc)
            return _u32(pc - 4 + imm_j())
        elif op == 0x67:                                 # JALR
            if rd: setrd(pc)
            t = _u32((x[rs1] + imm_i()) & ~1)
            return t
        elif op == 0x73:                                 # SYSTEM / ECALL
            if _u32(x[17]) == SRST:                      # a7 = SBI system_reset
                self.done = True
            else:
                raise Trap(f"未知 ecall a7=0x{_u32(x[17]):08X}")
        else:
            raise Trap(f"未知 opcode 0x{op:02X} @pc=0x{pc - 4:08X}")
        if rd == 0:
            x[0] = 0
        return pc


def _trunc_div(a, b):
    if b == 0:
        return -1
    if a == -0x80000000 and b == -1:
        return a
    q = abs(a) // abs(b)
    return _s32(q if (a < 0) == (b < 0) else -q)


def _trunc_rem(a, b):
    if b == 0:
        return a
    r = abs(a) % abs(b)
    return _s32(r if a >= 0 else -r)
