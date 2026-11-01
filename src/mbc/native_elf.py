"""M3V 字节码 → Linux x86-64 原生机器码（静态 ELF64 可执行文件）。

体检重构路线第 3 阶段 ④「native 跨平台」的 P-a 后端。设计见
`docs/spec/NATIVE_CROSS_PLATFORM.md`（总设计）与 `docs/spec/NATIVE_ELF_PA.md`（P-a 落地）。
与 `src/mbc/native.py`（Windows PE64）平行的独立发射器：**不 import native.py**，
只共享 `src.mbc.compiler.compile_source` 与 `src.mbc.opcodes`。

运行模型（Linux x86-64，静态非 PIE）：
  - 固定基址 BASE_ADDR=0x400000；无 libc/libm/动态链接器/GOT/PLT/重定位表。
  - 纯 syscall：write(rax=1) 输出、exit_group(rax=231) 退出。
  - 输出行尾统一 LF(`\\n`)，与 `exec_api.run_checked(mode="vm")` 逐字节对齐
    （native.py 的 Windows exe 用 CRLF，不参与对拍）。

里程碑进度（按 docs/spec/NATIVE_ELF_PA.md §三 自底向上）：
  M0  ELF64 链接器 `_build_elf64` + `_start` 硬编码 hello 壳。  ← 本文件当前
  M1  write_span/exit + print_int/print_bool 输出退出原语
  M2  字节码 dispatch + 整数算术 BINOP(+ - * // %)/UNARYOP(neg not)/比较/OUTPUT/HALT
  M3  标量局部/全局槽 + 控制流 JMP/JZ/JNZ
  M4  CALL/RET（直接/递归，argc≤2，标量）
集合之外的构造一律 `NativeNotSupported` 显式拒绝（不臆造、不数值伪造）。
"""
from __future__ import annotations

import struct

# ---------------------------------------------------------------- 固定地址布局

BASE_ADDR = 0x400000          # 非 PIE 加载基址
PAGE = 0x1000                 # 段对齐
EHDR_SIZE = 64                # ELF64 头
PHDR_SIZE = 56                # 单个 program header
PHNUM = 2                     # RX 段（头+phdr+text）+ RW 段（data/bss）
PHDR_TABLE = PHDR_SIZE * PHNUM
TEXT_FILE_OFF = EHDR_SIZE + PHDR_TABLE          # text 的文件偏移（=176）
TEXT_VADDR = BASE_ADDR + TEXT_FILE_OFF          # _start / e_entry
DATA_FILE_OFF = 0x10000                         # data 段文件偏移（预留 64KB 给 text）
DATA_VADDR = BASE_ADDR + DATA_FILE_OFF          # data 段虚拟地址

# ---------------------------------------------------------------- ELF64 常量

ELFCLASS64 = 2
ELFDATA2LSB = 1
EV_CURRENT = 1
ELFOSABI_SYSV = 0
ET_EXEC = 2
EM_X86_64 = 0x3E
PT_LOAD = 1
PF_X, PF_W, PF_R = 1, 2, 4

# 整数输出缓冲与操作数栈（M1+ 使用；M0 仅数据段占位）
NUMBUF_SIZE = 64
VSTACK_SIZE = 0x10000          # 64KB 操作数栈（P-a 标量足够）


class NativeNotSupported(Exception):
    """Linux ELF 后端 P-a 覆盖集之外的字节码/数据类型。"""


# ---------------------------------------------------------------- x86-64 发射工具

class _Buf:
    """机器码缓冲：追加字节 + label/rel32 回填（静态非 PIE，绝对地址固定）。"""

    def __init__(self) -> None:
        self.b = bytearray()
        self.labels: dict[str, int] = {}
        # (占位 rel32 起点的 code 偏移, 目标 label)；回填量 = target - (TEXT_VADDR + pos + 4)
        self.reloc: list[tuple[int, str]] = []

    def raw(self, *bs: int) -> None:
        self.b.extend(bs)

    def bytes_(self, data: bytes) -> None:
        self.b.extend(data)

    def imm32(self, v: int) -> None:
        self.b += struct.pack("<i", v)

    def imm64(self, v: int) -> None:
        self.b += struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF)

    def __len__(self) -> int:
        return len(self.b)

    def here(self, name: str) -> None:
        self.labels[name] = TEXT_VADDR + len(self.b)

    def _rel32(self, target: str) -> None:
        p = len(self.b)
        self.b += b"\x00\x00\x00\x00"
        self.reloc.append((p, target))

    def call(self, target: str) -> None:
        self.raw(0xE8)
        self._rel32(target)

    def jmp(self, target: str) -> None:
        self.raw(0xE9)
        self._rel32(target)

    def jcc(self, cond: int, target: str) -> None:
        self.raw(0x0F, cond)
        self._rel32(target)

    def finish(self) -> bytes:
        for p, target in self.reloc:
            rel = self.labels[target] - (TEXT_VADDR + p + 4)
            self.b[p:p + 4] = struct.pack("<i", rel)
        return bytes(self.b)

    def out(self) -> bytes:
        return bytes(self.b)


# 常用寄存器编码（REX.W + opcode）
_REG = {"rax": 0, "rcx": 1, "rdx": 2, "rbx": 3, "rsp": 4, "rbp": 5,
        "rsi": 6, "rdi": 7, "r8": 8, "r9": 9, "r10": 10, "r11": 11, "r12": 12}


def mov_imm32(buf: _Buf, reg: int, val: int) -> None:
    """mov r64, imm32（符号扩展）：REX.W[B] C7 /rm imm32。reg≥8 加 REX.B。"""
    rex = 0x48 | (0x01 if reg >= 8 else 0)
    buf.raw(rex, 0xC7, 0xC0 | (reg & 7))
    buf.imm32(val)


def mov_imm64(buf: _Buf, reg: int, val: int) -> None:
    """mov r64, imm64：REX.W B8+reg imm64。reg<8 时无需 REX.B。"""
    rex = 0x48 | (0x01 if reg >= 8 else 0)
    buf.raw(rex, 0xB8 | (reg & 7))
    buf.imm64(val)


def syscall(buf: _Buf) -> None:
    buf.raw(0x0F, 0x05)


# ---------------------------------------------------------------- ELF64 组装

def _elf64_header(entry: int, seg1_filesz: int, seg2_off: int,
                  seg2_filesz: int, seg2_memsz: int) -> bytes:
    ident = (b"\x7fELF" + bytes([ELFCLASS64, ELFDATA2LSB, EV_CURRENT,
                                  ELFOSABI_SYSV, 0]) + b"\x00" * 7)
    hdr = bytearray(ident)
    hdr += struct.pack("<HHI", ET_EXEC, EM_X86_64, 1)          # type, machine, version
    hdr += struct.pack("<Q", entry)                            # e_entry
    hdr += struct.pack("<Q", EHDR_SIZE)                        # e_phoff
    hdr += struct.pack("<Q", 0)                                # e_shoff（无 section 表）
    hdr += struct.pack("<I", 0)                                # e_flags
    hdr += struct.pack("<HHHHHH", EHDR_SIZE, PHDR_SIZE, PHNUM, 0, 0, 0)
    # e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx
    assert len(hdr) == EHDR_SIZE, f"ELF 头长度 {len(hdr)} != {EHDR_SIZE}"

    def phdr(flags: int, offset: int, vaddr: int, filesz: int, memsz: int) -> bytes:
        return struct.pack("<IIQQQQQ", PT_LOAD, flags, offset, vaddr, vaddr,
                           filesz, memsz) + struct.pack("<Q", PAGE)
    # 注：ELF64 Phdr = type(4) flags(4) offset(8) vaddr(8) paddr(8) filesz(8) memsz(8) align(8) = 56
    ph1 = phdr(PF_R | PF_X, 0, BASE_ADDR, seg1_filesz, seg1_filesz)
    ph2 = phdr(PF_R | PF_W, seg2_off, BASE_ADDR + seg2_off, seg2_filesz, seg2_memsz)
    return bytes(hdr) + ph1 + ph2


def _build_elf64(text: bytes, data: bytes, data_memsz: int = 0) -> bytes:
    """把 text 与 data 装进固定布局的静态 ELF64。

    - 段1（RX）：ELF 头 + program header 表 + text；文件 [0, TEXT_FILE_OFF+len(text))，
      映射到 vaddr [BASE_ADDR, ...)；入口 = _start = TEXT_VADDR。
    - 段2（RW）：data（含尾部零填充的 bss）；文件偏移 DATA_FILE_OFF，vaddr = BASE_ADDR+DATA_FILE_OFF。
      `data_memsz > len(data)` 时差额为 .bss（内核按需零页）。
    两段的 (vaddr - offset) 均为 BASE_ADDR（≡0 mod PAGE），满足 p_vaddr≡p_offset (mod p_align)。
    """
    if len(text) > DATA_FILE_OFF - TEXT_FILE_OFF:
        raise NativeNotSupported(
            f"text 段 {len(text)}B 超出预留区 {DATA_FILE_OFF - TEXT_FILE_OFF}B（P-a 应远小于此）")
    seg1_filesz = TEXT_FILE_OFF + len(text)
    memsz2 = max(data_memsz, len(data))
    headers_phdrs = _elf64_header(TEXT_VADDR, seg1_filesz, DATA_FILE_OFF,
                                  len(data), memsz2)
    file_ = bytearray()
    file_ += headers_phdrs                                    # ELF 头 + program header 表
    file_ += text                                             # 代码紧随其后（_start 落在 TEXT_VADDR）
    file_ += b"\x00" * (DATA_FILE_OFF - len(file_))            # 补零到 data 段文件偏移
    file_ += data
    return bytes(file_)


# ---------------------------------------------------------------- M0：hello 壳

def _hello_text() -> tuple[bytes, bytes]:
    """M0 硬编码：write(1, DATA_VADDR, len) hello 后 exit_group(0)。返回 (text, data)。"""
    msg = b"hello\n"
    buf = _Buf()
    mov_imm32(buf, _REG["rax"], 1)                    # syscall write
    mov_imm32(buf, _REG["rdi"], 1)                    # fd = stdout
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)           # buf = 绝对地址（静态非 PIE）
    mov_imm32(buf, _REG["rdx"], len(msg))             # len
    syscall(buf)
    mov_imm32(buf, _REG["rax"], 231)                  # exit_group
    mov_imm32(buf, _REG["rdi"], 0)                    # code 0
    syscall(buf)
    return buf.out(), msg


def hello_elf() -> bytes:
    text, data = _hello_text()
    return _build_elf64(text, data)


# ---------------------------------------------------------------- M1：输出/退出原语

# 条件跳转操作码（0F xx 的低位）
JZ, JNZ, JS, JNS, JLE = 0x84, 0x85, 0x88, 0x89, 0x8E


def _runtime_text(demo_value: int) -> tuple[bytes, bytes]:
    """发射 _start + write_span + print_int + print_bool（M1）。返回 (text, data)。

    data = numbuf(NUMBUF_SIZE 零) + '\\n' + 'True\\n' + 'False\\n' 静态串。
    _start 以 demo_value 演示 print_int→write_span→exit 的链接正确性。
    """
    NB = DATA_VADDR
    END = NB + NUMBUF_SIZE
    NL = END
    TRUE = NL + 1
    FALSE = TRUE + 5
    buf = _Buf()

    # ---- _start ----
    buf.here("_start")
    mov_imm32(buf, _REG["rax"], demo_value)
    buf.call("print_int")
    mov_imm64(buf, _REG["rsi"], NL)                # 追加换行
    mov_imm32(buf, _REG["rdx"], 1)
    buf.call("write_span")
    mov_imm32(buf, _REG["rax"], 231)               # exit_group
    mov_imm32(buf, _REG["rdi"], 0)
    syscall(buf)

    # ---- write_span：rsi=ptr, rdx=len（部分写续写；返回 <=0 结束）----
    buf.here("write_span")
    buf.here("ws_loop")
    buf.raw(0x48, 0x85, 0xD2)                        # test rdx,rdx
    buf.jcc(JZ, "ws_done")
    mov_imm32(buf, _REG["rax"], 1)                   # write
    mov_imm32(buf, _REG["rdi"], 1)                   # fd=stdout
    syscall(buf)
    buf.raw(0x48, 0x85, 0xC0)                        # test rax,rax
    buf.jcc(JLE, "ws_done")                          # <=0（错误或 0）停（P-a 小输出不重试 EINTR）
    buf.raw(0x48, 0x29, 0xC2)                        # sub rdx,rax
    buf.raw(0x48, 0x01, 0xC6)                        # add rsi,rax
    buf.jmp("ws_loop")
    buf.here("ws_done")
    buf.raw(0xC3)                                    # ret

    # ---- print_int：rax=整数 → 十进制写入 numbuf 再输出（不含换行）----
    buf.here("print_int")
    mov_imm32(buf, _REG["rbx"], 0)                   # 符号标志
    buf.raw(0x48, 0x85, 0xC0)                        # test rax,rax
    buf.jcc(JNS, "pi_nonneg")
    mov_imm32(buf, _REG["rbx"], 1)
    buf.raw(0x48, 0xF7, 0xD8)                        # neg rax
    buf.here("pi_nonneg")
    mov_imm64(buf, _REG["rsi"], NB)
    mov_imm64(buf, _REG["rdi"], END)
    buf.here("pi_loop")
    buf.raw(0x31, 0xD2)                              # xor edx,edx
    buf.raw(0xB9, 0x0A, 0x00, 0x00, 0x00)            # mov ecx,10
    buf.raw(0x48, 0xF7, 0xF1)                        # div rcx → rax=商, rdx=余
    buf.raw(0x83, 0xC2, 0x30)                        # add edx,'0'
    buf.raw(0x48, 0xFF, 0xCF)                        # dec rdi
    buf.raw(0x88, 0x17)                              # mov [rdi],dl
    buf.raw(0x48, 0x85, 0xC0)                        # test rax,rax
    buf.jcc(JNZ, "pi_loop")
    buf.raw(0x48, 0x85, 0xDB)                        # test rbx,rbx
    buf.jcc(JZ, "pi_nosign")
    buf.raw(0x48, 0xFF, 0xCF)                        # dec rdi
    buf.raw(0xC6, 0x07, 0x2D)                        # mov byte[rdi],'-'
    buf.here("pi_nosign")
    buf.raw(0x48, 0x89, 0xFE)                        # mov rsi,rdi（起点）
    mov_imm64(buf, _REG["rcx"], END)
    buf.raw(0x48, 0x29, 0xF9)                        # sub rcx,rdi（长度）
    buf.raw(0x48, 0x89, 0xCA)                        # mov rdx,rcx
    buf.call("write_span")
    buf.raw(0xC3)                                    # ret

    # ---- print_bool：rdi=0/1 → 'True\\n'/'False\\n' ----
    buf.here("print_bool")
    buf.raw(0x48, 0x85, 0xFF)                        # test rdi,rdi
    buf.jcc(JZ, "pb_false")
    mov_imm64(buf, _REG["rsi"], TRUE)
    mov_imm32(buf, _REG["rdx"], 5)
    buf.jmp("pb_out")
    buf.here("pb_false")
    mov_imm64(buf, _REG["rsi"], FALSE)
    mov_imm32(buf, _REG["rdx"], 6)
    buf.here("pb_out")
    buf.call("write_span")
    buf.raw(0xC3)

    data = b"\x00" * NUMBUF_SIZE + b"\n" + b"True\n" + b"False\n"
    return buf.finish(), data


def m1_elf(demo_value: int = 42) -> bytes:
    text, data = _runtime_text(demo_value)
    return _build_elf64(text, data)


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(prog="native_elf",
                                     description="M3V → Linux x86-64 静态 ELF64 发射器（P-a）")
    parser.add_argument("output", nargs="?", default=".trae/m1.elf",
                        help="输出 ELF 路径（M1 默认写打印 42 的演示程序）")
    parser.add_argument("--hello", action="store_true", help="仅发射 M0 hello 壳")
    args = parser.parse_args(argv)
    elf = hello_elf() if args.hello else m1_elf(42)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(elf)
    tag = "M0 hello" if args.hello else "M1 print_int(42)"
    print(f"{tag} ELF 已发射 → {out}（{len(elf)} 字节，entry=0x{TEXT_VADDR:x}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
