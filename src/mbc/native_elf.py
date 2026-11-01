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
  M0  ELF64 链接器 `_build_elf64` + `_start` 硬编码 hello 壳。
  M1  write_span/exit + print_int/print_bool 输出退出原语
  M2  字节码 dispatch + 整数算术 BINOP(+ - * // %)/UNARYOP(neg not)/比较/OUTPUT/HALT
  M3  标量局部/全局槽 + 控制流 JMP/JZ/JNZ
  M4  CALL/RET（直接/递归，argc≤2，标量）
P-b（列表 + bump 堆，见 docs/spec/NATIVE_ELF_PB.md）：
  N0  .bss bump 堆（r12 堆指针）+ BUILD_LIST + 内建 len
  N1  INDEX_GET（正/负索引，越界 exit_group(1)）
  N2  列表进全局/局部槽（typ 跟踪 (list,eltyp)）+ 混合/嵌套/字符串元素拒
  N3  列表 × 算术 × 控制流组合；N4 Gate 扩例（13 正 + 12 拒 + 3 越界行为）
P-c1（字符串垂直切片，见 docs/spec/NATIVE_ELF_PC.md）：
  N0  PUSH_CONST str（堆串对象 [len:8B][bytes]）+ OUTPUT print_str（裸串无引号）+ len(str)
  N1  str+str 连接（str_concat/rep movsb）+ str ==/!= 比较（str_eq/repe cmpsb）+ s[i] 取子串（正/负/越界 exit1）
  N2  同质 int/bool 整表 repr 输出（plr_int/plr_bool 运行期循环 `[e0, e1, …]`，无换行由 OUTPUT 追加）
  N3  字面量 str/异构整表 repr：发射器编译期用 Python str() 折叠精确字节（零转义/标签汇编）
P-c2（浮点垂直切片，见 docs/spec/NATIVE_ELF_PC.md §三 N2）：
  S1  IEEE-754 double 代栈位型 + 字面量/编译器已折叠(+ - *) float 的 str() 折叠输出（零 SSE/零 _dtoa）
  S2  SSE2 标量算术/比较框架：movsd/cvtsi2sd + addsd/subsd/mulsd/divsd + ucomisd（PF 无序 NaN 护栏）+ neg 翻符号位；比较消费 float 产 bool 可输出；'/' 真除（含 int/int→float）；float 字面量元素可入折叠 repr
  S3a 保底 _dtoa（精度可声明的回退路线，非最短往返）：精确十进制域 floatq（double=整数×2^-d，d≤6，|v|<9e9）
     经静态打标（字面量谓词 + 对 + - neg 封闭，* / 及越域降级 float），运行期 dtoa 叶例定点展开（×1e6 精确成整
     → int/frac 拆分 → 去尾零）逐字节=str(v)；越域运行期哨兵 → exit1 如实失败  ← 本文件当前
（越域运行期 float 输出（0.1 类/×÷产/科学计数法）需全量 _dtoa（最短往返，S3b+）按 Q1 如实拒；`//`/`%` 浮点取整、not float 真值判定同拒；divsd 除零产 ±inf，与 VM ZeroDivisionError 已登记分歧）。
列表元素 P-b 限 int/bool（同质）；首期字符串限 ASCII（多字节拒）。str×数值连接（需 itoa）/运行期（非字面量）计算的 str/异构列表 repr（需运行期标签）属 P-c1 后续；字面量 str/异构列表经编译期折叠已支持。
集合之外的构造（非 ASCII 串 / 字典 / 闭包 / 异常，及未就绪的运行期 float 算术·比较·输出）一律 `NativeNotSupported` 显式拒绝（不臆造、不数值伪造）。
"""
from __future__ import annotations

import struct

from src.mbc import opcodes as OP

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


# ---------------------------------------------------------------- 运行时子程序 + 字节码 dispatch（M1/M2）

# 条件跳转操作码（0F xx 的低位）
JE, JNE, JZ, JNZ, JS, JNS, JL, JGE, JLE, JG = (
    0x84, 0x85, 0x84, 0x85, 0x88, 0x89, 0x8C, 0x8D, 0x8E, 0x8F)

# 数据段（RW）内固定偏移：numbuf / '\n' / "True" / "False" 后接 .bss 操作数栈
NL_OFF = NUMBUF_SIZE                 # 64：单字节 '\n'（每条 OUTPUT 行尾）
TRUE_OFF = NL_OFF + 1                # 65："True"（4）
FALSE_OFF = TRUE_OFF + 4             # 69："False"（5）
# P-c1 N2：列表 repr 字面量（紧随 "False" 后，均处于 VSP_OFF=0x100 前的空洞）
LB_OFF = FALSE_OFF + 5               # 74：'['
RB_OFF = LB_OFF + 1                  # 75：']'
Q_OFF = RB_OFF + 1                   # 76："'"（str 元素引号）
CMA_OFF = Q_OFF + 1                  # 77：", "（逗号+空格，连续 2 字节供 write_span）
VSP_OFF = 0x100                       # 操作数栈起点（对齐，前面留空洞）
GVARS_OFF = 0x20000                   # 全局槽区起点（避开 64KB 操作数栈）；.bss 零页
HEAP_OFF = 0x30000                    # 堆起点（避开操作数栈/全局槽区）；.bss 零页，P-b 起用
HEAP_SIZE = 0x80000                   # 512KB bump 堆（P-b 只增不回收，GC 属 P-c）
NL_ADDR = DATA_VADDR + NL_OFF
TRUE_ADDR = DATA_VADDR + TRUE_OFF
FALSE_ADDR = DATA_VADDR + FALSE_OFF
LB_ADDR = DATA_VADDR + LB_OFF
RB_ADDR = DATA_VADDR + RB_OFF
Q_ADDR = DATA_VADDR + Q_OFF
CMA_ADDR = DATA_VADDR + CMA_OFF
VSP_ADDR = DATA_VADDR + VSP_OFF
GVARS_ADDR = DATA_VADDR + GVARS_OFF   # 每个全局名一个 8 字节槽（slot 索引 → +8*slot）
HEAP_ADDR = DATA_VADDR + HEAP_OFF     # bump 堆首地址（r12 初始值）

_CMP_SETCC = {"==": 0x94, "!=" : 0x95, "<": 0x9C, ">": 0x9F, "<=": 0x9E, ">=": 0x9D}
_ARITH = {"+", "-", "*", "//", "%"}
_ONE_M = 1_000_000                                   # S3a _dtoa 定点放大因子 10^6
_ONE_M_BITS = struct.unpack("<q", struct.pack("<d", 1_000_000.0))[0]   # 1e6 的 double 位型
_LIMIT_BITS = struct.unpack("<q", struct.pack("<d", 9e9))[0]           # 9e9 域宽阈位型（N=v×1e6<9e15<2^53 精确）
_JAE, _JP = 0x83, 0x8A                                # 近跳条件码（buf.jcc 发 0F xx rel32）：JAE / JP（0x9A 是 SETPE 非 Jcc！）


def _floatq_domain(v: float) -> bool:
    """S3a _dtoa 保底域：double 精确值 = 整数×2^-d（d≤6，即可写成 分母≤64 的既约二进有理）且 |v|<9e9。

    域内 v×1e6 为精确整数（<2^53 无舍入），定点展开+去尾零逐字节等于 Python str(v)；
    非零最小元 2^-6=0.015625 ≥ Python 定点阈值 1e-4 → 永不触发科学计数法。
    ±0.0 属域（'-0.0'/'0.0' 对齐 Python）；非精确十进制值（0.1 等）拒。"""
    if v == 0.0:
        return True                                  # +0.0 与 -0.0
    if v != v or v in (float("inf"), float("-inf")):
        return False
    bits = struct.unpack("<q", struct.pack("<d", v))[0]
    e = (bits >> 52) & 0x7FF
    if e == 0:                                       # 次正规：分母 2^1074 越域
        return False
    m = (bits & ((1 << 52) - 1)) | (1 << 52)         # 含隐藏位的 53 位整数尾数
    k = 1075 - e                                     # 未既约分母 2^k（k≤0 → 整数值）
    if k > 6:                                        # 既约：尾数拖尾零可约掉分母的 2 因子
        k -= (m & -m).bit_length() - 1               #拖尾零计数 ctz(m)
    return k <= 6 and abs(v) < 9e9
# P-c2 S2：ucomisd 后 setcc（无序由 PF 护栏另行处置，见 _emit_fbinop）与 SSE2 标量算术 opcode
_FCMP_SETCC = {"==": 0x94, "!=": 0x95, "<": 0x92, "<=": 0x96, ">": 0x97, ">=": 0x93}
_FARITH = {"+": 0x58, "-": 0x5C, "*": 0x59, "/": 0x5E}   # addsd/subsd/mulsd/divsd


def _push_rax(buf: _Buf) -> None:
    buf.raw(0x48, 0x89, 0x03)          # mov [rbx],rax（rbx=操作数栈指针，指向首个空闲槽）
    buf.raw(0x48, 0x83, 0xC3, 0x08)    # add rbx,8


def _load_imm_rax(buf: _Buf, v: int) -> None:
    if -0x80000000 <= v < 0x80000000:
        mov_imm32(buf, _REG["rax"], v)
    else:
        mov_imm64(buf, _REG["rax"], v)


def _load_abs_rax(buf: _Buf, addr: int) -> None:
    """mov rax, [abs]（静态绝对寻址：REX.W 8B 04 25 disp32，SIB base=101/index=100 无基址）。"""
    buf.raw(0x48, 0x8B, 0x04, 0x25); buf.imm32(addr)


def _store_rax_abs(buf: _Buf, addr: int) -> None:
    """mov [abs], rax（REX.W 89 04 25 disp32）。addr<2^31（固定基址 0x4xxxxx）作正数 disp。"""
    buf.raw(0x48, 0x89, 0x04, 0x25); buf.imm32(addr)


def _local_disp(slot: int) -> int:
    """局部槽 slot → rbp 相对偏移（参数/局部均为 8 字节槽，自 [rbp-8] 往下）。"""
    return -8 * (slot + 1)


def _mov_rax_rbp(buf: _Buf, disp: int) -> None:
    """mov rax,[rbp+disp]（mod=01/rm=101 disp8，超范围用 mod=10 disp32）。"""
    if -128 <= disp <= 127:
        buf.raw(0x48, 0x8B, 0x45, disp & 0xFF)
    else:
        buf.raw(0x48, 0x8B, 0x85); buf.imm32(disp)


def _mov_rbp_rax(buf: _Buf, disp: int) -> None:
    """mov [rbp+disp],rax。"""
    if -128 <= disp <= 127:
        buf.raw(0x48, 0x89, 0x45, disp & 0xFF)
    else:
        buf.raw(0x48, 0x89, 0x85); buf.imm32(disp)


def _mov_rax_rbx(buf: _Buf, disp: int) -> None:
    """mov rax,[rbx+disp]（操作数栈相对寻址；rbx 指向首个空闲槽，栈顶值在 [rbx-8]）。"""
    if -128 <= disp <= 127:
        buf.raw(0x48, 0x8B, 0x43, disp & 0xFF)
    else:
        buf.raw(0x48, 0x8B, 0x83); buf.imm32(disp)


def _store_rax_r12(buf: _Buf, disp: int) -> None:
    """mov [r12+disp32],rax（r12=堆 bump 指针，SIB base=100 需 REX.B 方为 r12：REX.W+B 89 84 24 disp32）。"""
    buf.raw(0x49, 0x89, 0x84, 0x24); buf.imm32(disp)


def _store_byte_r12(buf: _Buf, disp: int, val: int) -> None:
    """mov byte [r12+disp32],imm8（写字符串单字节入堆；REX.B C6 /0 ModRM=84 SIB=24 disp32 imm8）。"""
    buf.raw(0x49, 0xC6, 0x84, 0x24); buf.imm32(disp); buf.raw(val & 0xFF)


def _mov_rax_r12(buf: _Buf) -> None:
    """mov rax,r12（取 bump 指针当前值 = 刚建列表首地址；rm=100(r12) 需 REX.B）。"""
    buf.raw(0x49, 0x8B, 0xC4)


def _add_r12_imm32(buf: _Buf, val: int) -> None:
    """add r12,imm32（bump 分配：堆指针前移；REX.B.W 81 /0 rm=100 → 49 81 C4 imm32）。"""
    buf.raw(0x49, 0x81, 0xC4); buf.imm32(val)


def _sub_rbx_imm32(buf: _Buf, val: int) -> None:
    """sub rbx,imm32（一次弹出多个操作数栈槽；REX.W 81 /5 rm=011 → 48 81 EB imm32）。"""
    buf.raw(0x48, 0x81, 0xEB); buf.imm32(val)


# ------------------------------------------------ P-c1 N1：通用 ModRM/REX 编码辅助

def _mem_modrm(buf: _Buf, reg: int, base: int, disp: int, op_bytes: tuple) -> None:
    """emit REX + op_bytes + ModRM(+SIB)(+disp) 寻址 [base+disp]，reg 字段=reg。

    reg/base 为寄存器号（0-15）。rm=100(rsp/r12) 走 SIB（base=100 index=无 scale=1）；
    rm=101(rbp/r13) 且 disp=0 需 mod=01 disp8=0（否则变绝对寻址）。其余 mod01/10。"""
    rm = base & 7
    rf = reg & 7
    rex = 0x48 | (0x04 if reg >= 8 else 0) | (0x01 if base >= 8 else 0)
    if rm == 4:                                   # rsp/r12 → SIB
        if -0x80 <= disp <= 0x7F:
            buf.raw(rex, *op_bytes, 0x40 | (rf << 3) | 4, 0x24, disp & 0xFF)
        else:
            buf.raw(rex, *op_bytes, 0x80 | (rf << 3) | 4, 0x24); buf.imm32(disp)
    elif rm == 5 and disp == 0:                   # rbp/r13 + 0 → 强制 disp8=0
        buf.raw(rex, *op_bytes, 0x40 | (rf << 3) | 5, 0x00)
    elif -0x80 <= disp <= 0x7F:
        buf.raw(rex, *op_bytes, 0x40 | (rf << 3) | rm, disp & 0xFF)
    else:
        buf.raw(rex, *op_bytes, 0x80 | (rf << 3) | rm); buf.imm32(disp)


def _mov_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # mov dst,src（89 /r：reg=src rm=dst）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x89, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _add_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # add dst,src（01 /r）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x01, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _cmp_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # cmp dst,src（39 /r）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x39, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _mov_reg_mem(buf: _Buf, dst: int, base: int, disp: int) -> None:   # mov dst,[base+disp]
    _mem_modrm(buf, dst, base, disp, (0x8B,))


def _mov_mem_reg(buf: _Buf, base: int, disp: int, src: int) -> None:   # mov [base+disp],src
    _mem_modrm(buf, src, base, disp, (0x89,))


def _lea_reg_mem(buf: _Buf, dst: int, base: int, disp: int) -> None:   # lea dst,[base+disp]
    _mem_modrm(buf, dst, base, disp, (0x8D,))


def _add_reg_imm32(buf: _Buf, reg: int, val: int) -> None:  # add reg,imm32（81 /0）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0x81, 0xC0 | (reg & 7)); buf.imm32(val)


def _and_rax_imm32(buf: _Buf, val: int) -> None:  # and rax,imm32（81 /4）
    buf.raw(0x48, 0x81, 0xE0); buf.imm32(val)


def _xor_rax_rax(buf: _Buf) -> None:              # xor rax,rax
    buf.raw(0x48, 0x31, 0xC0)


def _cld(buf: _Buf) -> None:                      # cld（清方向标志，串指令前置）
    buf.raw(0xFC)


def _rep_movsb(buf: _Buf) -> None:                # rep movsb（[rsi]→[rdi]，rcx 计数）
    buf.raw(0xF3, 0xA4)


def _repe_cmpsb(buf: _Buf) -> None:               # repe cmpsb（[rsi]↔[rdi] 逐字节比较至不等或 rcx=0）
    buf.raw(0xF3, 0xA6)


def _pop2_rcx_rax(buf: _Buf) -> None:             # 弹栈顶二槽：b→rcx、a→rax（与 BINOP 弹序一致）
    buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x0B)    # sub rbx,8; mov rcx,[rbx]
    buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)    # sub rbx,8; mov rax,[rbx]


def _test_reg_reg(buf: _Buf, a: int, b: int) -> None:    # test a,b（85 /r：reg=b rm=a）
    rex = 0x48 | (0x04 if b >= 8 else 0) | (0x01 if a >= 8 else 0)
    buf.raw(rex, 0x85, 0xC0 | ((b & 7) << 3) | (a & 7))


def _zero_reg(buf: _Buf, r: int) -> None:                # xor r,r（31 /r mod=11）
    rex = 0x48 | (0x04 if r >= 8 else 0) | (0x01 if r >= 8 else 0)
    buf.raw(rex, 0x31, 0xC0 | ((r & 7) << 3) | (r & 7))


def _load_elem_rax(buf: _Buf, base: int, index: int) -> None:   # mov rax,[base+index*8+8]（表元素载入）
    # 与列表 INDEX_GET 同族 SIB：scale=8（bits 11<<6=0xC0）；base/index 高位需 REX.B/REX.X
    # ModRM=0x44（mod=01 disp8、reg=000=rax、rm=100=SIB），非 0x4C（那会把目的寄存器写成 rcx）
    rex = 0x48 | (0x02 if index >= 8 else 0) | (0x01 if base >= 8 else 0)
    buf.raw(rex, 0x8B, 0x44, 0xC0 | ((index & 7) << 3) | (base & 7), 0x08)


def _emit_runtime(buf: _Buf) -> None:
    """发射 write_span / print_int / print_bool 三个子程序（不触碰 rbx 栈指针）。"""
    # exit1：运行期越界（如 INDEX_GET 越界）退出码 1，镜像 VM 未捕获 IndexError
    buf.here("exit1")
    mov_imm32(buf, _REG["rax"], 231)                        # exit_group
    mov_imm32(buf, _REG["rdi"], 1)
    syscall(buf)

    # write_span：rsi=ptr, rdx=len（部分写续写；返回 <=0 结束）
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

    # print_int：rax=整数 → 十进制写入 numbuf 再输出（不含换行；用 r10d 存符号，不碰 rbx）
    buf.here("print_int")
    mov_imm32(buf, _REG["r10"], 0)
    buf.raw(0x48, 0x85, 0xC0)                        # test rax,rax
    buf.jcc(JNS, "pi_nn")
    mov_imm32(buf, _REG["r10"], 1)
    buf.raw(0x48, 0xF7, 0xD8)                        # neg rax
    buf.here("pi_nn")
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)          # numbuf 基
    mov_imm64(buf, _REG["rdi"], DATA_VADDR + NUMBUF_SIZE)   # 数字区上界（独占）
    buf.here("pi_loop")
    buf.raw(0x31, 0xD2)                              # xor edx,edx
    buf.raw(0xB9, 0x0A, 0x00, 0x00, 0x00)            # mov ecx,10
    buf.raw(0x48, 0xF7, 0xF1)                        # div rcx → rax=商, rdx=余
    buf.raw(0x83, 0xC2, 0x30)                        # add edx,'0'
    buf.raw(0x48, 0xFF, 0xCF)                        # dec rdi
    buf.raw(0x88, 0x17)                              # mov [rdi],dl
    buf.raw(0x48, 0x85, 0xC0)                        # test rax,rax
    buf.jcc(JNZ, "pi_loop")
    buf.raw(0x45, 0x85, 0xD2)                        # test r10d,r10d
    buf.jcc(JZ, "pi_ns")
    buf.raw(0x48, 0xFF, 0xCF)                        # dec rdi
    buf.raw(0xC6, 0x07, 0x2D)                        # mov byte[rdi],'-'
    buf.here("pi_ns")
    buf.raw(0x48, 0x89, 0xFE)                        # mov rsi,rdi（起点）
    mov_imm64(buf, _REG["rcx"], DATA_VADDR + NUMBUF_SIZE)
    buf.raw(0x48, 0x29, 0xF9)                        # sub rcx,rdi（长度）
    buf.raw(0x48, 0x89, 0xCA)                        # mov rdx,rcx
    buf.call("write_span")
    buf.raw(0xC3)

    # print_bool：rdi=0/1 → 'True'(4)/'False'(5)（换行由 OUTPUT 统一追加）
    buf.here("print_bool")
    buf.raw(0x48, 0x85, 0xFF)                        # test rdi,rdi
    buf.jcc(JZ, "pb_f")
    mov_imm64(buf, _REG["rsi"], TRUE_ADDR)
    mov_imm32(buf, _REG["rdx"], 4)
    buf.jmp("pb_o")
    buf.here("pb_f")
    mov_imm64(buf, _REG["rsi"], FALSE_ADDR)
    mov_imm32(buf, _REG["rdx"], 5)
    buf.here("pb_o")
    buf.call("write_span")
    buf.raw(0xC3)

    # print_str：rax=串指针 → write_span(sptr+8, [sptr])（裸串无引号；换行由 OUTPUT 统一追加）
    buf.here("print_str")
    buf.raw(0x48, 0x8B, 0x10)                        # mov rdx,[rax]（串长度字）
    buf.raw(0x48, 0x8D, 0x70, 0x08)                  # lea rsi,[rax+8]（字节首地址）
    buf.call("write_span")
    buf.raw(0xC3)

    # str_concat：rax=sptrA, rcx=sptrB → rax=新串指针（[r12]=lenA+lenB，双段 rep movsb）
    #   只用 rax/rcx/rdx?/rsi/rdi/r8/r9/r13/r14/r15 + r12 bump；不碰 rbx（不碰操作数栈）
    buf.here("str_concat")
    _cld(buf)
    _mov_reg_reg(buf, 13, 12)                        # mov r13,r12（新串基址）
    _mov_reg_mem(buf, 14, 0, 0)                      # mov r14,[rax]（lenA）
    _mov_reg_mem(buf, 15, 1, 0)                      # mov r15,[rcx]（lenB）
    _mov_reg_reg(buf, 8, 0)                          # mov r8,rax（save sptrA）
    _mov_reg_reg(buf, 9, 1)                          # mov r9,rcx（save sptrB）
    _mov_reg_reg(buf, 0, 14)                         # mov rax,r14
    _add_reg_reg(buf, 0, 15)                         # add rax,r15（total）
    _mov_mem_reg(buf, 13, 0, 0)                      # mov [r13],rax（新串长度字）
    _lea_reg_mem(buf, 6, 8, 8)                       # lea rsi,[r8+8]（srcA）
    _lea_reg_mem(buf, 7, 13, 8)                      # lea rdi,[r13+8]（dstA）
    _mov_reg_reg(buf, 1, 14)                         # mov rcx,r14（lenA）
    _rep_movsb(buf)                                  # 拷贝 A
    _lea_reg_mem(buf, 6, 9, 8)                       # lea rsi,[r9+8]（srcB；rdi 已前移）
    _mov_reg_reg(buf, 1, 15)                         # mov rcx,r15（lenB）
    _rep_movsb(buf)                                  # 拷贝 B
    _mov_reg_reg(buf, 0, 14)                         # mov rax,r14
    _add_reg_reg(buf, 0, 15)                         # add rax,r15（total）
    _add_reg_imm32(buf, 0, 15)                       # add rax,15（= 8+total+7）
    _and_rax_imm32(buf, -8)                          # and rax,-8（block=align8(8+total)）
    _add_reg_reg(buf, 12, 0)                         # add r12,rax（bump）
    _mov_reg_reg(buf, 0, 13)                         # mov rax,r13（结果=新串指针）
    buf.raw(0xC3)

    # str_eq：rax=sptrA, rcx=sptrB → rax=0/1（长度不等短路；否则 repe cmpsb 逐字节）
    buf.here("str_eq")
    _mov_reg_mem(buf, 14, 0, 0)                      # mov r14,[rax]（lenA）
    _mov_reg_mem(buf, 15, 1, 0)                      # mov r15,[rcx]（lenB）
    _cmp_reg_reg(buf, 14, 15)                        # cmp r14,r15
    buf.jcc(JNE, "se_neq")                           # 长度不等 → 0
    _lea_reg_mem(buf, 6, 0, 8)                       # lea rsi,[rax+8]
    _lea_reg_mem(buf, 7, 1, 8)                       # lea rdi,[rcx+8]
    _mov_reg_reg(buf, 1, 14)                         # mov rcx,r14（lenA）
    buf.raw(0x48, 0x85, 0xC9)                        # test rcx,rcx
    buf.jcc(JZ, "se_eq")                             # 空串 → 相等
    _cld(buf)
    _repe_cmpsb(buf)                                 # 逐字节比较：全等末次比较置 ZF=1（含 rcx 耗尽），失配置 ZF=0
    buf.jcc(JZ, "se_eq")                             # ZF=1 → 全等（不能用 test rcx：失配于末字节时 rcx 也归 0）
    buf.here("se_neq")
    _xor_rax_rax(buf)                                # mov rax,0
    buf.jmp("se_ret")
    buf.here("se_eq")
    mov_imm32(buf, _REG["rax"], 1)                   # mov rax,1
    buf.here("se_ret")
    buf.raw(0xC3)

    # plr_int：rax=listptr（int 元素）→ 输出 Python list repr `[e0, e1, …]`（无换行，OUTPUT 统一追加）
    #   循环态 r13=sptr/r14=n/r15=i 全程不被 print_int/write_span 触碰
    buf.here("plr_int")
    _mov_reg_reg(buf, 13, 0)                          # mov r13,rax
    _mov_reg_mem(buf, 14, 0, 0)                       # mov r14,[rax]（n）
    _zero_reg(buf, 15)                                # xor r15,r15（i=0）
    mov_imm64(buf, _REG["rsi"], LB_ADDR); mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")   # '['
    buf.here("pli_loop")
    _cmp_reg_reg(buf, 15, 14)                         # cmp r15,r14
    buf.jcc(JGE, "pli_end")
    _test_reg_reg(buf, 15, 15)                        # test r15,r15
    buf.jcc(JZ, "pli_nosep")
    mov_imm64(buf, _REG["rsi"], CMA_ADDR); mov_imm32(buf, _REG["rdx"], 2); buf.call("write_span")  # ", "
    buf.here("pli_nosep")
    _load_elem_rax(buf, 13, 15)                       # mov rax,[r13+r15*8+8]
    buf.call("print_int")
    _add_reg_imm32(buf, 15, 1)                        # add r15,1
    buf.jmp("pli_loop")
    buf.here("pli_end")
    mov_imm64(buf, _REG["rsi"], RB_ADDR); mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")   # ']'
    buf.raw(0xC3)

    # plr_bool：同上，元素 0/1 → print_bool（'True'/'False'）
    buf.here("plr_bool")
    _mov_reg_reg(buf, 13, 0)
    _mov_reg_mem(buf, 14, 0, 0)
    _zero_reg(buf, 15)
    mov_imm64(buf, _REG["rsi"], LB_ADDR); mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    buf.here("plb_loop")
    _cmp_reg_reg(buf, 15, 14)
    buf.jcc(JGE, "plb_end")
    _test_reg_reg(buf, 15, 15)
    buf.jcc(JZ, "plb_nosep")
    mov_imm64(buf, _REG["rsi"], CMA_ADDR); mov_imm32(buf, _REG["rdx"], 2); buf.call("write_span")
    buf.here("plb_nosep")
    _load_elem_rax(buf, 13, 15)
    _mov_reg_reg(buf, 7, 0)                           # mov rdi,rax
    buf.call("print_bool")
    _add_reg_imm32(buf, 15, 1)
    buf.jmp("plb_loop")
    buf.here("plb_end")
    mov_imm64(buf, _REG["rsi"], RB_ADDR); mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    buf.raw(0xC3)

    # dtoa：rax=float 位型（S3a 保底域：整数×2^-d，d≤6，|v|<9e9）→ 定点十进制输出（不含换行，OUTPUT 追加）。
    #   算法：翻 abs 位 → mulsd ×1e6（域内精确成整，<2^53 无舍入）→ cvttsd2si N → intpart=N//1e6 走
    #   print_int；'.'；frac=N%1e6：去尾零与降 scale(10^5→) 同步进行（保有效前导零，如 0.015625），再高位起
    #   逐位单字符 write_span。负数先出 '-'（-0.0 → '-0.0' 对齐 Python str）。越域哨兵（cvttsd2si INDEFINITE
    #   致 N 负 或 |v|≥9e9）→ dt_oob → exit1（如实失败，不瞎编输出）。
    #   寄存器：只用 rax/rcx/rdx/rsi/rdi/r10/r11/r13/r14/r15 + xmm0/xmm1；不碰 rbx/rbp/r12；
    #   print_int/write_span 不触碰 r13/r14/r15（循环态安全）。
    buf.here("dtoa")
    _mov_reg_reg(buf, 10, 0)                          # mov r10,rax（存符号）
    buf.raw(0x49, 0xC1, 0xEA, 63)                     # shr r10,63（sign 0/1）
    mov_imm64(buf, 11, 0x7FFFFFFFFFFFFFFF)            # movabs r11,清符掩码
    buf.raw(0x4C, 0x21, 0xD8)                         # and rax,r11（REX.W+R：r11 在 ModRM reg 域需 REX.B——0x49；mod=11）
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC0)             # movq xmm0,rax（abs 位型）
    mov_imm64(buf, _REG["rax"], _LIMIT_BITS)          # movabs rax,9e9 位型（运行期域宽护栏：乘法前！）
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xD0)             # movq xmm2,rax
    buf.raw(0x66, 0x0F, 0x2E, 0xC2)                   # ucomisd xmm0,xmm2（|v| vs 9e9；reg=xmm0 rm=xmm2）
    buf.jcc(_JAE, "dt_oob")                           # ≥9e9 → 越域（含相等；防 ×1e6 后 >2^53 舍入瞎编）
    buf.jcc(_JP, "dt_oob")                            # 无序（NaN 类，静态域本不可达）→ 兜底拒
    mov_imm64(buf, _REG["rax"], _ONE_M_BITS)          # movabs rax,1e6 位型
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC8)             # movq xmm1,rax
    buf.raw(0xF2, 0x0F, 0x59, 0xC1)                   # mulsd xmm0,xmm1
    buf.raw(0xF2, 0x48, 0x0F, 0x2C, 0xC0)             # cvttsd2si rax,xmm0（N；66 48 0F 2C 是 cvttpd2pi 只写低 32 位——错！）
    buf.raw(0x48, 0x85, 0xC0)                         # test rax,rax
    buf.jcc(JNS, "dt_nn")
    buf.jmp("dt_oob")                                 # 负（含 INDEFINITE 哨兵）→ 越域如实失败
    buf.here("dt_nn")
    _mov_reg_reg(buf, 15, 0)                          # mov r15,rax（N）
    _test_reg_reg(buf, 10, 10)                        # 符号位？
    buf.jcc(JZ, "dt_ns")
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)           # numbuf 低端单字符缓冲（print_int 自高位向下写，不冲突）
    buf.raw(0xC6, 0x06, 0x2D)                         # mov byte[rsi],'-'
    mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    buf.here("dt_ns")
    _mov_reg_reg(buf, 0, 15)                          # mov rax,r15
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    mov_imm32(buf, _REG["rcx"], _ONE_M)               # mov ecx,1000000
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx → rax=整部, rdx=frac
    _mov_reg_reg(buf, 13, 2)                          # mov r13,rdx（frac；print_int 不碰 r13）
    buf.call("print_int")                             # 整部（为 0 时也出 '0'）
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)
    buf.raw(0xC6, 0x06, 0x2E)                         # mov byte[rsi],'.'
    mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    _test_reg_reg(buf, 13, 13)                        # frac==0 → 出单 '0'（整数值 → '3.0'）
    buf.jcc(JNZ, "dt_strip")
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)
    buf.raw(0xC6, 0x06, 0x30)                         # mov byte[rsi],'0'
    mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    buf.jmp("dt_ret")
    buf.here("dt_strip")                              # 去尾零与降 scale 同步（保留有效前导零，如 0.015625）：while frac%10==0: frac/=10, scale/=10
    mov_imm32(buf, 14, 100000)                        # scale=10^5（定点 6 位小数，最高位档）
    buf.here("dt_sloop")
    _mov_reg_reg(buf, 0, 13)                          # mov rax,r13（frac）
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    buf.raw(0xB9, 0x0A, 0x00, 0x00, 0x00)             # mov ecx,10
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx → rax=frac/10, rdx=frac%10
    buf.raw(0x48, 0x85, 0xD2)                         # test rdx,rdx
    buf.jcc(JNZ, "dt_out")                            # 余≠0 → 尾零剥尽（scale 停在正确档位），转输出
    _mov_reg_reg(buf, 13, 0)                          # mov r13,rax（frac/=10）
    _mov_reg_reg(buf, 0, 14)                          # mov rax,r14（scale）
    buf.raw(0x31, 0xD2)
    buf.raw(0xB9, 0x0A, 0x00, 0x00, 0x00)             # mov ecx,10
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx
    _mov_reg_reg(buf, 14, 0)                          # mov r14,rax（scale/=10，与剥零同步）
    buf.jmp("dt_sloop")
    buf.here("dt_out")                                # 高位起逐位：while scale>0 { digit=frac/scale; frac%=scale; scale/=10 }
    buf.here("dt_o_loop")
    _test_reg_reg(buf, 14, 14)
    buf.jcc(JZ, "dt_ret")
    _mov_reg_reg(buf, 0, 13)                          # mov rax,r13
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    buf.raw(0x49, 0xF7, 0xF6)                         # div r14（商=digit，余=frac）
    _mov_reg_reg(buf, 13, 2)                          # mov r13,rdx
    buf.raw(0x83, 0xC0, 0x30)                         # add eax,'0'
    buf.raw(0x88, 0x04, 0x25)                         # mov [DATA_VADDR],al（无基址 disp32 绝对寻址）
    buf.b += struct.pack("<I", DATA_VADDR)
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)           # write_span 改 rsi → 每轮重置
    mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    _mov_reg_reg(buf, 0, 14)                          # mov rax,r14（scale/=10）
    buf.raw(0x31, 0xD2)
    buf.raw(0xB9, 0x0A, 0x00, 0x00, 0x00)             # mov ecx,10
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx
    _mov_reg_reg(buf, 14, 0)                          # mov r14,rax
    buf.jmp("dt_o_loop")
    buf.here("dt_ret")
    buf.raw(0xC3)
    buf.here("dt_oob")                                # 运行期越域哨兵：exit1（已登记行为，不瞎编）
    buf.jmp("exit1")


def _load_frac(buf: _Buf, xmm: int, typ: str, disp: int) -> None:
    """xmm ← 操作数栈槽 [rbx+disp] 的数值（P-c2 S2）：float/floatq 直载 64 位位型（movsd）；
    int/bool 符号扩展转双精度（cvtsi2sd REX.W）。movsd/cvtsi2sd m64 无 16B 对齐要求。"""
    if typ in ("float", "floatq"):
        buf.raw(0xF2, 0x0F, 0x10, 0x40 | (xmm << 3) | 3, disp & 0xFF)         # movsd xmm,[rbx+disp8]
    else:
        buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0x40 | (xmm << 3) | 3, disp & 0xFF)   # cvtsi2sd xmm,[rbx+disp8]


def _emit_fbinop(buf: _Buf, sym: str, ta: str, tb: str, is_cmp: bool) -> None:
    """P-c2 S2：SSE2 标量浮点算术（addsd/subsd/mulsd/divsd）与比较（ucomisd+setcc）。

    算术产运行期 float（输出需 _dtoa，未就绪按 Q1 如实拒）；比较产 bool（可直接输出），
    故 S2 的算术/比较以「比较消费 float」形态外部可验。NaN 护栏：ucomisd 无序时 ZF=CF=PF=1，
    故 <,<=,>,>=,== 需「无序→强制 0」、!= 需「无序→强制 1」（对齐 Python：除 != 外 NaN 比较均 False）。
    除零：divsd 产 ±inf，与 VM（ZeroDivisionError 参考失败）存在已登记分歧，不伪对齐。
    """
    if sym not in _FCMP_SETCC and sym not in ("+", "-", "*", "/"):
        raise NativeNotSupported(f"BINOP {sym!r} 越 float/SSE 域（// % 取整语义属 P-c2 后续）：{ta},{tb}")
    if ta not in ("int", "bool", "float", "floatq") or tb not in ("int", "bool", "float", "floatq"):
        raise NativeNotSupported(f"BINOP {sym!r} 操作数需 int/bool/float：{ta},{tb}")
    _load_frac(buf, 0, ta, -16)                                # xmm0 ← a（栈顶下槽）
    _load_frac(buf, 1, tb, -8)                                 # xmm1 ← b（栈顶）
    buf.raw(0x48, 0x83, 0xEB, 0x10)                            # sub rbx,16（弹二）
    if is_cmp:
        buf.raw(0x66, 0x0F, 0x2E, 0xC1)                        # ucomisd xmm0,xmm1
        buf.raw(0x0F, _FCMP_SETCC[sym], 0xC0)                  # setcc al
        buf.raw(0x0F, 0xB6, 0xC0)                              # movzx eax,al
        # jnp +5：有序（PF=0）跳过强制赋值；无序执行 mov eax,imm（!= → 1，余 → 0）
        buf.raw(0x7B, 0x05, 0xB8, 0x01 if sym == "!=" else 0x00, 0x00, 0x00, 0x00)
        _push_rax(buf)
    else:
        buf.raw(0xF2, 0x0F, _FARITH[sym], 0xC1)                # addsd/subsd/mulsd/divsd xmm0,xmm1
        buf.raw(0x66, 0x0F, 0x11, 0x03)                        # movsd [rbx],xmm0（结果回栈）
        buf.raw(0x48, 0x83, 0xC3, 0x08)                        # add rbx,8


def _emit_binop(buf: _Buf, sym: str, typ: list, i: int) -> None:
    if len(typ) < 2:
        raise NativeNotSupported(f"BINOP {sym!r}：操作数栈不足")
    tb, ta = typ[-1], typ[-2]
    is_cmp = sym in _CMP_SETCC
    if sym == "/" or "float" in (ta, tb) or "floatq" in (ta, tb):   # P-c2 S2/S3a：'/' 真除与 float/floatq 域操作数走 SSE2
        _emit_fbinop(buf, sym, ta, tb, is_cmp)
        typ.pop(); typ.pop()
        if is_cmp:
            typ.append("bool")
        elif (sym in ("+", "-") and all(x in ("int", "bool", "floatq") for x in (ta, tb))
                and any(x == "floatq" for x in (ta, tb))):
            typ.append("floatq")                       # S3a：精确十进制域对 + - 封闭（int 操作数分母 1）
        else:
            typ.append("float")                        # * / 及含越域操作数：保守降级（输出待全量 _dtoa）
        return
    if sym not in _CMP_SETCC and sym not in _ARITH:
        raise NativeNotSupported(f"M2 不支持 BINOP {sym!r}")
    if ta != "int" or tb != "int":
        raise NativeNotSupported(f"BINOP {sym!r} 操作数需 int：{ta},{tb}")
    # 弹 b→rcx（栈顶），再弹 a→rax
    buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x0B)   # sub rbx,8; mov rcx,[rbx]
    buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # sub rbx,8; mov rax,[rbx]
    if sym == "+":
        buf.raw(0x48, 0x01, 0xC8)                                # add rax,rcx
    elif sym == "-":
        buf.raw(0x48, 0x29, 0xC8)                                # sub rax,rcx
    elif sym == "*":
        buf.raw(0x48, 0x0F, 0xAF, 0xC1)                          # imul rax,rcx
    elif sym in ("//", "%"):
        buf.raw(0x48, 0x99)                                      # cqo（符号扩展 rax→rdx:rax）
        buf.raw(0x48, 0xF7, 0xF9)                                # idiv rcx（向零截断）
        buf.raw(0x48, 0x85, 0xD2)                                # test rdx,rdx（余数）
        buf.jcc(JZ, f"nd{i}")
        buf.raw(0x49, 0x89, 0xD0); buf.raw(0x49, 0x31, 0xC8)     # mov r8,rdx; xor r8,rcx
        buf.jcc(JS, f"fx{i}")                                    # 余数与除数异号→需修正
        buf.jmp(f"nd{i}")
        buf.here(f"fx{i}")
        if sym == "//":
            buf.raw(0x48, 0xFF, 0xC8)                            # dec rax（商向 -inf）
        else:
            buf.raw(0x48, 0x01, 0xCA)                            # add rdx,rcx（余数取除数号）
        buf.here(f"nd{i}")
        if sym == "%":
            buf.raw(0x48, 0x89, 0xD0)                            # mov rax,rdx（结果=余数）
    else:                                                        # 比较
        buf.raw(0x48, 0x39, 0xC8)                                # cmp rax,rcx（a-b）
        buf.raw(0x0F, _CMP_SETCC[sym], 0xC0)                     # setcc al
        buf.raw(0x0F, 0xB6, 0xC0)                                # movzx eax,al
    _push_rax(buf)
    typ.pop(); typ.pop()
    typ.append("bool" if is_cmp else "int")


def _emit_unop(buf: _Buf, sym: str, typ: list) -> None:
    if not typ:
        raise NativeNotSupported(f"UNARYOP {sym!r}：空操作数栈")
    t = typ[-1]
    if sym == "neg":
        if t in ("float", "floatq"):                             # P-c2 S2：IEEE 翻符号位（xorpd 掩码），保 NaN/-0 语义；S3a：域对 neg 封闭
            mov_imm64(buf, _REG["rax"], -0x8000000000000000)     # movabs rax,0x8000000000000000（符号位掩码）
            buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC8)                # movq xmm1,rax
            buf.raw(0xF2, 0x0F, 0x10, 0x43, 0xF8)                # movsd xmm0,[rbx-8]
            buf.raw(0x66, 0x0F, 0x57, 0xC1)                      # xorpd xmm0,xmm1
            buf.raw(0x66, 0x0F, 0x11, 0x43, 0xF8)                # movsd [rbx-8],xmm0（原地回栈）
            typ.pop(); typ.append(t)                             # floatq 保持 floatq
            return
        if t != "int":
            raise NativeNotSupported(f"neg 操作数需 int：{t}")
        buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # pop→rax
        buf.raw(0x48, 0xF7, 0xD8)                                    # neg rax
        _push_rax(buf)
        typ.pop(); typ.append("int")
    elif sym == "not":
        if t not in ("int", "bool"):                            # float/-0.0/串等真值语义需额外机器（属后续），如实拒
            raise NativeNotSupported(f"not 操作数需 int/bool：{t!r}（float 真值判定属 P-c2 后续）")
        buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # pop→rax
        buf.raw(0x48, 0x85, 0xC0)                                    # test rax,rax
        buf.raw(0x0F, 0x94, 0xC0)                                    # sete al（==0→1）
        buf.raw(0x0F, 0xB6, 0xC0)                                    # movzx eax,al
        _push_rax(buf)
        typ.pop(); typ.append("bool")
    else:
        raise NativeNotSupported(f"M2 不支持 UNARYOP {sym!r}（仅 neg/not）")


def _emit_fold_print(buf: _Buf, data: bytes) -> None:
    """编译期折叠字节 → 堆串对象 [len:8B][bytes] → print_str 发射（行尾 LF 由 OUTPUT 统一追加）。

    P-c2 S1 浮点折叠输出与 P-c1 N3 列表折叠输出共用此机制（发射器 Python str() = VM 输出基准）。"""
    for idx, byte in enumerate(data):
        _store_byte_r12(buf, 8 + idx, byte)             # mov byte[r12+8+idx],b
    _load_imm_rax(buf, len(data)); _store_rax_r12(buf, 0)   # 头=[len]
    _mov_rax_r12(buf); buf.call("print_str")           # 当作普通串发射
    _add_r12_imm32(buf, (8 + len(data) + 7) & ~7)      # bump


def _fold_list_repr(C: list, code: list, i: int, n: int):
    """P-c1 N3：若 BUILD_LIST 前 n 条指令全为字面量压栈，用【发射器(Python)】的
    str() 直接算出与 VM 输出基准逐字节一致的 ASCII repr 字节（零转义/标签汇编）。

    VM 对拍口径本就是 `str(value)`；发射器即真正的「格式核心层」。元素非全字面量
    （运行期计算）→ 返回 None，交回 N2 运行期路径（同质 int/bool）或拒绝（str/异构）。"""
    if i < n:
        return None
    vals: list = []
    for j in range(i - n, i):
        ins = code[j]
        op = ins[0]
        if op == OP.PUSH_CONST:
            v = C[ins[1]]
            if isinstance(v, bool) or isinstance(v, int):        # bool 是 int 子类，一并处理
                vals.append(v)
            elif isinstance(v, (str, float)):
                vals.append(v)
            else:
                return None                                       # null 等不折叠
            continue
        if op == OP.PUSH_TRUE:
            vals.append(True); continue
        if op == OP.PUSH_FALSE:
            vals.append(False); continue
        return None                                               # 非字面量压栈 → 不折叠
    try:
        return str(vals).encode("ascii")                          # 空表 [] → "[]"
    except UnicodeEncodeError:
        return None                                               # 非 ASCII 元素 → 不折叠


def _emit_code(buf: _Buf, code: list, C: list, gmap: dict, gtype: dict, tag: str,
               fninfo: dict, fntyp: dict, *, in_fn: bool = False,
               ltype: dict | None = None, ret_collector: list | None = None) -> None:
    """遍历 M3V 指令流发射机器码；typ 为编译期影子值型栈（int/bool/null/"fn"）。

    gmap：全局名→槽索引；gtype：槽→值型（冲突拒绝）。tag：本作用域 label 前缀
    （跳转目标 = 指令下标 → f"{tag}:{i}"）。fninfo：函数名→{arity,nlocals}；fntyp：
    函数返回型。in_fn=True 时支持 LOAD_LOCAL/STORE_LOCAL/RET（帧由 emit_elf 前置码建立）；
    ret_collector 收集每个 RET 的返回值型（供返回型不动点推断）。
    分支合并沿用 SPIKE 线性影子栈模型（同型分支 typ[-1] 对齐运行期栈顶）。
    """
    typ: list = []
    lt: dict[int, str] = ltype if ltype is not None else {}
    for i, ins in enumerate(code):
        buf.here(f"{tag}:{i}")
        op = ins[0]
        if op == OP.PUSH_CONST:
            v = C[ins[1]]
            if isinstance(v, bool):                     # 编译期常量折叠出的布尔（如 not 0 → True）
                _load_imm_rax(buf, 1 if v else 0); _push_rax(buf); typ.append("bool")
                continue
            if isinstance(v, str):                      # P-c1 N0：ASCII 串 → 堆串对象 [len:8B][bytes]
                try:
                    data = v.encode("ascii")
                except UnicodeEncodeError:
                    raise NativeNotSupported(f"PUSH_CONST 非 ASCII 字符串（多字节属 P-c1 后续，Q2）：{v!r}")
                n = len(data)
                for idx, byte in enumerate(data):
                    _store_byte_r12(buf, 8 + idx, byte)         # mov byte[r12+8+idx],b
                _load_imm_rax(buf, n)                           # mov rax,n（长度）
                _store_rax_r12(buf, 0)                          # mov [r12],rax
                _mov_rax_r12(buf); _push_rax(buf)               # 串指针 sptr 入操作数栈
                _add_r12_imm32(buf, (8 + n + 7) & ~7)           # bump：r12 += align8(8+n)
                typ.append("str"); continue
            if isinstance(v, float):                    # P-c2 S1：IEEE-754 double → 栈存 8B 原始位型
                bits = struct.unpack("<q", struct.pack("<d", v))[0]
                _load_imm_rax(buf, bits); _push_rax(buf)
                typ.append("floatq" if _floatq_domain(v) else "float")   # S3a：精确十进制域打标
                continue
            if not isinstance(v, int):
                raise NativeNotSupported(f"PUSH_CONST 非常量整数：{v!r}")
            if not (-0x8000000000000000 <= v < 0x8000000000000000):
                raise NativeNotSupported(f"常量超 int64：{v}")
            _load_imm_rax(buf, v); _push_rax(buf); typ.append("int")
        elif op == OP.PUSH_TRUE:
            _load_imm_rax(buf, 1); _push_rax(buf); typ.append("bool")
        elif op == OP.PUSH_FALSE:
            _load_imm_rax(buf, 0); _push_rax(buf); typ.append("bool")
        elif op == OP.PUSH_NULL:
            _load_imm_rax(buf, 0); _push_rax(buf); typ.append("null")
        elif op == OP.DUP:
            if not typ:
                raise NativeNotSupported("DUP 空栈")
            buf.raw(0x48, 0x8B, 0x43, 0xF8)                          # mov rax,[rbx-8]
            _push_rax(buf); typ.append(typ[-1])
        elif op == OP.POP:
            if not typ:
                raise NativeNotSupported("POP 空栈")
            buf.raw(0x48, 0x83, 0xEB, 0x08); typ.pop()               # sub rbx,8
        elif op == OP.BUILD_LIST:
            n = ins[1]
            if n < 0:
                raise NativeNotSupported(f"BUILD_LIST n={n} 非法")
            if len(typ) < n:
                raise NativeNotSupported("BUILD_LIST 操作数不足")
            if n == 0:
                eltyp = "int"                                        # 空表元素型无所谓（索引必越界）
            else:
                elems = typ[-n:]
                for t in elems:
                    if t not in ("int", "bool", "str", "float", "floatq"):
                        raise NativeNotSupported(
                            f"BUILD_LIST 元素类型越界（仅 int/bool/str/float(q)，无嵌套）：{t!r}")
                eltyp = elems[0] if len(set(elems)) == 1 else "mixed"
            # P-c1 N3：编译期折叠（字面量元素→发射器 Python str() 精确 repr）
            folded = _fold_list_repr(C, code, i, n)
            if folded is None and eltyp not in ("int", "bool"):
                raise NativeNotSupported(
                    f"BUILD_LIST {eltyp} 列表不可折叠（含非字面量元素）；运行期 str/异构/float 列表 repr 属后续（P-c1）")
            # 逐元素：heap[i] = 栈底起的第 i 个（写书序）；元素 i 位于 [rbx-8*(n-i)]
            for idx in range(n):
                _mov_rax_rbx(buf, -8 * (n - idx))                   # mov rax,[rbx-8*(n-idx)]
                _store_rax_r12(buf, 8 + 8 * idx)                    # mov [r12+8+8*idx],rax
            _load_imm_rax(buf, n)                                   # mov rax,n（长度）
            _store_rax_r12(buf, 0)                                  # mov [r12],rax
            if n:
                _sub_rbx_imm32(buf, 8 * n)                          # 弹出 n 个元素槽
            _mov_rax_r12(buf)                                       # mov rax,r12（listptr）
            _push_rax(buf)                                          # 压回表指针
            _add_r12_imm32(buf, 8 + 8 * n)                          # bump：r12 += 8+8n
            if n:
                del typ[-n:]
            typ.append(("list", eltyp, folded))
        elif op == OP.INDEX_GET:
            if len(typ) < 2:
                raise NativeNotSupported("INDEX_GET 操作数不足")
            tidx, tc = typ[-1], typ[-2]
            if tidx != "int":
                raise NativeNotSupported(f"INDEX_GET 下标需 int：{tidx!r}")
            is_list = isinstance(tc, tuple) and tc[0] == "list"
            if not (is_list or tc == "str"):
                raise NativeNotSupported(f"INDEX_GET 不可下标对象：{tc!r}（P-b 列表/P-c1 串）")
            _pop2_rcx_rax(buf)                                       # rcx=idx、rax=容器（与 BINOP 弹序一致）
            buf.raw(0x48, 0x8B, 0x10)                                # mov rdx,[rax]（长度字）
            buf.raw(0x48, 0x85, 0xC9)                                # test rcx,rcx
            buf.jcc(JNS, f"{tag}:{i}:sk")
            buf.raw(0x48, 0x01, 0xD1)                                # add rcx,rdx（负索引 += len）
            buf.here(f"{tag}:{i}:sk")
            buf.raw(0x48, 0x85, 0xC9)                                # test rcx,rcx
            buf.jcc(JS, "exit1")                                     # 仍负→越界
            buf.raw(0x48, 0x39, 0xD1)                                # cmp rcx,rdx
            buf.jcc(JGE, "exit1")                                    # idx>=len→越界
            if is_list:
                buf.raw(0x48, 0x8B, 0x44, 0xC8, 0x08)                # mov rax,[rax+rcx*8+8]（SIB=0xC8: scale11*index001*base000）
                _push_rax(buf)
                typ.pop(); typ.pop(); typ.append(tc[1])
            else:                                                    # str → 1 字节子串（新堆对象 [len=1][byte]）
                buf.raw(0x48, 0x8B, 0x44, 0x08, 0x08)                # mov rax,[rax+rcx*1+8]（SIB=0x08 scale=1；8B 非对齐载入取低字节）
                _store_rax_r12(buf, 8)                               # mov [r12+8],rax（字节入新串负载）
                _load_imm_rax(buf, 1); _store_rax_r12(buf, 0)        # mov [r12],1（新串长度）
                _mov_rax_r12(buf); _push_rax(buf)                    # 结果=新串指针入栈
                _add_r12_imm32(buf, 16)                              # bump：r12 += align8(8+1)=16
                typ.pop(); typ.pop(); typ.append("str")
        elif op == OP.BINOP:
            sym = C[ins[1]]
            tb = typ[-1] if typ else None
            ta = typ[-2] if len(typ) >= 2 else None
            if sym == "+" and ta == "str" and tb == "str":            # P-c1 N1：str+str 连接
                _pop2_rcx_rax(buf); buf.call("str_concat"); _push_rax(buf)
                typ.pop(); typ.pop(); typ.append("str")
            elif sym in ("==", "!=") and ta == "str" and tb == "str":  # P-c1 N1：str 逐字节比较
                _pop2_rcx_rax(buf); buf.call("str_eq")
                if sym == "!=":
                    buf.raw(0x48, 0x83, 0xF0, 0x01)                  # xor rax,1（0/1 翻转）
                _push_rax(buf)
                typ.pop(); typ.pop(); typ.append("bool")
            elif sym in ("+", "-", "*", "//", "%") and "str" in (ta, tb):
                raise NativeNotSupported(
                    f"BINOP {sym!r} 涉 str 于非 str+str 域（str×数值连接/算术属 P-c1 后续，需 itoa）：{ta},{tb}")
            else:
                _emit_binop(buf, sym, typ, i)
        elif op == OP.UNARYOP:
            _emit_unop(buf, C[ins[1]], typ)
        elif op == OP.OUTPUT:
            if not typ:
                raise NativeNotSupported("OUTPUT 空栈")
            t = typ.pop()
            if t == "int":
                buf.raw(0x48, 0x8B, 0x43, 0xF8); buf.call("print_int")    # mov rax,[rbx-8]
            elif t == "bool":
                buf.raw(0x48, 0x8B, 0x7B, 0xF8); buf.call("print_bool")    # mov rdi,[rbx-8]
            elif t == "str":
                buf.raw(0x48, 0x8B, 0x43, 0xF8); buf.call("print_str")     # mov rax,[rbx-8]（sptr）
            elif t in ("float", "floatq"):
                # P-c2 S1：编译期折叠——仅当 OUTPUT 紧前一条为 PUSH_CONST float（字面量/编译器已折叠的 +-*）
                # 时，用发射器 Python str(float) 精确输出（=VM 基准，零 _dtoa/零 SSE）。回看保证 soundness：
                # 不携带静态值过全局/控制流，故运行期计算的全局/循环/SSE float 一律不折叠。
                prev = code[i - 1] if i >= 1 else None
                if (prev is not None and prev[0] == OP.PUSH_CONST
                        and isinstance(C[prev[1]], float)):
                    _emit_fold_print(buf, str(C[prev[1]]).encode("ascii"))
                elif t == "floatq":
                    # P-c2 S3a：运行期精确十进制域（d≤6，|v|<9e9）→ dtoa 叶例定点展开（域内天然=str(v)）
                    buf.raw(0x48, 0x8B, 0x43, 0xF8); buf.call("dtoa")     # mov rax,[rbx-8]
                else:
                    raise NativeNotSupported(
                        "OUTPUT 越域运行期 float 需全量 _dtoa（最短往返，S3b+；未就绪按 Q1 如实 SKIP，绝不伪通过）："
                        "非精确十进制值（0.1 类）/×÷产 float/科学计数法范围")
            elif isinstance(t, tuple) and t[0] == "list" and len(t) >= 3 and t[2] is not None:
                # P-c1 N3：编译期折叠 repr（str/异构/字面量 int-bool 列表均走此，Python str() 逐字节精确）
                _emit_fold_print(buf, t[2])
            elif isinstance(t, tuple) and t[0] == "list" and t[1] in ("int", "bool"):
                buf.raw(0x48, 0x8B, 0x43, 0xF8)                         # mov rax,[rbx-8]（listptr）
                buf.call("plr_int" if t[1] == "int" else "plr_bool")   # P-c1 N2：运行期同质 int/bool 整表 repr
            else:
                raise NativeNotSupported(f"OUTPUT 不支持值型 {t!r}（null/运行期 str 列表/嵌套表属后续，P-c1）")
            buf.raw(0x48, 0x83, 0xEB, 0x08)                          # sub rbx,8（弹）
            mov_imm64(buf, _REG["rsi"], NL_ADDR); mov_imm32(buf, _REG["rdx"], 1)
            buf.call("write_span")                                   # 行尾 LF
        elif op in (OP.LOAD_GLOBAL, OP.STORE_GLOBAL):
            name = C[ins[1]]
            if not isinstance(name, str):
                raise NativeNotSupported(f"全局名非常量字符串：{name!r}")
            if op == OP.LOAD_GLOBAL and name in fninfo:     # 函数值：直调占位（dummy 操作数 + "fn" 标记）
                _load_imm_rax(buf, 0); _push_rax(buf); typ.append(("fn", name))
                continue
            if (op == OP.LOAD_GLOBAL and name == "len"
                    and name not in fninfo and name not in gmap):   # 内建 len（不入 gmap，取表头长）
                _load_imm_rax(buf, 0); _push_rax(buf); typ.append(("builtin", "len"))
                continue
            if name not in gmap:
                raise NativeNotSupported(
                    f"M3：全局 {name!r} 未登记（未赋值即读取/写入，绝不静默读 0）")
            addr = GVARS_ADDR + 8 * gmap[name]
            if op == OP.LOAD_GLOBAL:
                _load_abs_rax(buf, addr); _push_rax(buf)
                typ.append(gtype.get(gmap[name], "int"))
            else:
                if not typ:
                    raise NativeNotSupported("STORE_GLOBAL 空栈")
                t = typ[-1]
                if t == "null":
                    raise NativeNotSupported("STORE_GLOBAL null 暂不支持（P-a）")
                slot = gmap[name]
                old = gtype.get(slot)
                same_list = (isinstance(old, tuple) and isinstance(t, tuple)
                             and len(old) >= 2 and len(t) >= 2
                             and old[0] == t[0] == "list" and old[1] == t[1])
                if (old in ("float", "floatq") and t in ("float", "floatq")):
                    # S3a：float/floatq 同物理位型可共槽；保守合并——仅两次均 floatq 才保持 floatq，
                    # 否则槽降 "float"（可能收到越域值 → 输出侧如实拒，sound）
                    gtype[slot] = "floatq" if (old == t == "floatq") else "float"
                elif old is not None and old != t and not same_list:
                    raise NativeNotSupported(f"全局 {name!r} 混型：{old} vs {t}（P-a 拒绝）")
                else:
                    gtype[slot] = t
                buf.raw(0x48, 0x8B, 0x43, 0xF8)                      # mov rax,[rbx-8]
                _store_rax_abs(buf, addr)
                buf.raw(0x48, 0x83, 0xEB, 0x08); typ.pop()          # sub rbx,8
        elif op in (OP.JMP, OP.JZ, OP.JNZ):
            target = f"{tag}:{ins[1]}"
            if op == OP.JMP:
                buf.jmp(target)
            else:
                if not typ:
                    raise NativeNotSupported("JZ/JNZ 空栈")
                typ.pop()
                buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # sub rbx,8; mov rax,[rbx]
                buf.raw(0x48, 0x85, 0xC0)                            # test rax,rax
                buf.jcc(JZ if op == OP.JZ else JNZ, target)          # JZ=假跳，JNZ=真跳
        elif op in (OP.LOAD_LOCAL, OP.STORE_LOCAL):
            if not in_fn:
                raise NativeNotSupported("局部槽仅存在于函数帧内（P-a）")
            slot = ins[1]
            disp = _local_disp(slot)
            if op == OP.LOAD_LOCAL:
                _mov_rax_rbp(buf, disp); _push_rax(buf)
                typ.append(lt.get(slot, "int"))
            else:
                if not typ:
                    raise NativeNotSupported("STORE_LOCAL 空栈")
                t = typ[-1]
                if isinstance(t, tuple):
                    raise NativeNotSupported("STORE_LOCAL 函数值不在 P-a 子集")
                if t == "floatq":
                    t = "float"          # S3a：floatq 不跨函数边界（局部/返回保守降级，输出侧如实拒）
                old = lt.get(slot)
                if old is not None and old != t:
                    raise NativeNotSupported(f"局部槽 {slot} 混型：{old} vs {t}（P-a 拒绝）")
                lt[slot] = t
                buf.raw(0x48, 0x8B, 0x43, 0xF8)                      # mov rax,[rbx-8]
                _mov_rbp_rax(buf, disp)
                buf.raw(0x48, 0x83, 0xEB, 0x08); typ.pop()          # sub rbx,8
        elif op == OP.CALL:
            argc = ins[1]
            if argc > 2:
                raise NativeNotSupported(f"CALL argc={argc} 超出 P-a（仅 argc≤2 标量直调）")
            if len(typ) < argc + 1:
                raise NativeNotSupported("CALL 操作数不足")
            marker = typ[-(argc + 1)]
            if isinstance(marker, tuple) and marker[0] == "builtin" and marker[1] == "len":
                if argc != 1:
                    raise NativeNotSupported(f"len 需 1 参数，argc={argc}")
                if not ((isinstance(typ[-1], tuple) and typ[-1][0] == "list") or typ[-1] == "str"):
                    raise NativeNotSupported(f"len 作用于不可取长对象：{typ[-1]!r}（P-b 列表/P-c1 串）")
                buf.raw(0x48, 0x8B, 0x43, 0xF8)                     # mov rax,[rbx-8]（listptr）
                buf.raw(0x48, 0x8B, 0x00)                           # mov rax,[rax]（表头长度字）
                buf.raw(0x48, 0x83, 0xEB, 0x10)                     # sub rbx,16（弹 arg+dummy）
                _push_rax(buf)                                      # 压回长度 int
                del typ[-(argc + 1):]
                typ.append("int")
                continue
            if not (isinstance(marker, tuple) and marker[0] == "fn"):
                raise NativeNotSupported("CALL 非直接函数调用（间接/高阶不在 P-a）")
            fname = marker[1]
            info = fninfo.get(fname)
            if info is None:
                raise NativeNotSupported(f"调用内建/未知函数 {fname!r}（P-a 仅直接调用已定义函数）")
            if info["arity"] != argc:
                raise NativeNotSupported(f"调用 {fname!r}：arity={info['arity']} 与 argc={argc} 不符")
            argtys = typ[-argc:] if argc else []
            for at in argtys:
                if at not in ("int", "bool"):
                    raise NativeNotSupported(
                        f"调用 {fname!r} 实参类型 {at!r} 非 int/bool（串/列表跨函数边界属后续，P-c1）")
            buf.call(f"fn_{fname}")
            # 弹回传值→rax，弹掉 dummy 函数槽，重新压回结果（保持操作数栈与 typ 同步）
            buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # sub rbx,8; mov rax,[rbx]
            buf.raw(0x48, 0x83, 0xEB, 0x08)                             # sub rbx,8（弹 dummy）
            _push_rax(buf)
            del typ[-(argc + 1):]
            typ.append(fntyp.get(fname, "int"))
        elif op == OP.RET:
            if not in_fn:
                raise NativeNotSupported("RET 出现在主程序（P-a）")
            if not typ:
                raise NativeNotSupported("RET 空栈（返回值缺失）")
            t = typ[-1]
            if isinstance(t, tuple) or t in ("null", "str"):
                raise NativeNotSupported(f"RET 返回 {t!r}（仅 int/bool 标量；串/列表跨函数边界属后续，P-c1）")
            if ret_collector is not None:
                ret_collector.append(t)
            buf.raw(0x48, 0x89, 0xEC)                                # mov rsp,rbp
            buf.raw(0x5D)                                           # pop rbp
            buf.raw(0xC3)                                           # ret（返回值留在操作数栈顶）
        elif op == OP.HALT:
            break
        else:
            raise NativeNotSupported(f"M2 暂不支持 opcode {OP.name(op)}")


def _build_data() -> bytearray:
    seg = bytearray(VSP_OFF)
    seg[NL_OFF] = 0x0A
    seg[TRUE_OFF:TRUE_OFF + 4] = b"True"
    seg[FALSE_OFF:FALSE_OFF + 5] = b"False"
    seg[LB_OFF] = 0x5B                         # '['
    seg[RB_OFF] = 0x5D                         # ']'
    seg[Q_OFF] = 0x27                          # "'"
    seg[CMA_OFF:CMA_OFF + 2] = b", "           # ', '
    return seg


def _scan_globals(codes: list, C: list) -> dict:
    """预扫所有作用域（main + 各函数），按首次 STORE_GLOBAL 顺序为全局名分配槽索引。"""
    gmap: dict[str, int] = {}
    for code in codes:
        for ins in code:
            if ins[0] == OP.STORE_GLOBAL:
                name = C[ins[1]]
                if isinstance(name, str) and name not in gmap:
                    gmap[name] = len(gmap)
    return gmap


def _infer_fntyp(mod, C: list, gmap: dict, fninfo: dict) -> dict:
    """函数返回型不动点推断：对每个函数体跑一次 scratch 发射（仅收集 RET 值型）。

    递归自调用上一轮 fntyp（缺失时临时当作 int），迭代至稳定；多 RET 异型/无 RET
    一律 NativeNotSupported 拒绝。
    """
    fntyp: dict[str, str] = {}
    fnlist = list(mod.functions.items())
    for _ in range(len(fnlist) + 2):
        changed = False
        for name, f in fnlist:
            rc: list = []
            _emit_code(_Buf(), f.code, C, gmap, {}, f"inf:{name}", fninfo, fntyp,
                       in_fn=True, ltype={}, ret_collector=rc)
            if not rc:
                raise NativeNotSupported(f"函数 {name!r} 无可达 RET（P-a）")
            uniq = set(rc)
            if len(uniq) > 1:
                raise NativeNotSupported(f"函数 {name!r} 多 RET 混型 {sorted(uniq)}（P-a 拒绝）")
            nt = rc[0]
            if fntyp.get(name) != nt:
                fntyp[name] = nt
                changed = True
        if not changed:
            break
    return fntyp


def _emit_function(buf: _Buf, name: str, f, C: list, gmap: dict, gtype: dict,
                   fninfo: dict, fntyp: dict) -> None:
    """发射一个函数例程：帧前言（push rbp/mov rbp,rsp/sub rsp）+ 实参绑定 + 体。

    约定：调用方已把 argc 个实参压在共享操作数栈（rbx）顶部（argN 在顶）；前言
    依次弹出存入局部槽 arity-1..0（P-a 参数一律作 int 处理）；RET 把返回值留在
    操作数栈顶供调用方取用。机器栈（rsp/rbp）仅存帧，syscall 不破坏 rbp。
    """
    buf.here(f"fn_{name}")
    buf.raw(0x55)                                       # push rbp
    buf.raw(0x48, 0x89, 0xE5)                           # mov rbp,rsp
    frame = (8 * f.nlocals + 15) & ~15
    if frame:
        buf.raw(0x48, 0x81, 0xEC); buf.imm32(frame)     # sub rsp, frame
    lt: dict[int, str] = {}
    for k in range(f.arity - 1, -1, -1):               # argN→slot N-1 … arg1→slot0
        buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # sub rbx,8; mov rax,[rbx]
        _mov_rbp_rax(buf, _local_disp(k))
        lt[k] = "int"
    _emit_code(buf, f.code, C, gmap, gtype, f"fn_{name}", fninfo, fntyp,
               in_fn=True, ltype=lt)


def emit_elf(mod) -> bytes:
    """MModule → Linux x86-64 静态 ELF64 字节串（P-a 整数/布尔标量 + 直调/递归子集）。"""
    C = mod.constants
    fninfo = {name: {"arity": f.arity, "nlocals": f.nlocals}
              for name, f in mod.functions.items()}
    all_codes = [mod.main_code] + [f.code for f in mod.functions.values()]
    gmap = _scan_globals(all_codes, C)
    gtype: dict[int, str] = {}
    fntyp = _infer_fntyp(mod, C, gmap, fninfo)
    buf = _Buf()
    buf.here("_start")
    mov_imm64(buf, _REG["rbx"], VSP_ADDR)         # rbx = 操作数栈指针
    mov_imm64(buf, _REG["r12"], HEAP_ADDR)        # r12 = 堆 bump 指针（P-b 列表）
    _emit_code(buf, mod.main_code, C, gmap, gtype, "main", fninfo, fntyp)
    mov_imm32(buf, _REG["rax"], 231)              # exit_group
    mov_imm32(buf, _REG["rdi"], 0)
    syscall(buf)
    for name, f in mod.functions.items():
        _emit_function(buf, name, f, C, gmap, gtype, fninfo, fntyp)
    _emit_runtime(buf)
    text = buf.finish()
    data = bytes(_build_data())
    memsz = max(VSP_OFF + VSTACK_SIZE, GVARS_OFF + 8 * len(gmap), HEAP_OFF + HEAP_SIZE)
    return _build_elf64(text, data, data_memsz=memsz)


def compile_to_elf(source: str) -> bytes:
    from src.mbc.compiler import compile_source
    return emit_elf(compile_source(source))


DEFAULT_SAMPLE = ("#1：[2 + 3 * 4]\nlet x = 5\nlet y = if x > 3 then 10 else 20\n#1：[y]\n"
                  "#1：[-7 // 2]\n#1：[-7 % 3]\n#1：[1 < 2]\n#1：[not 0]\n")


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(prog="native_elf",
                                     description="M3V → Linux x86-64 静态 ELF64 发射器（P-a）")
    parser.add_argument("output", nargs="?", default=".trae/m2.elf", help="输出 ELF 路径")
    parser.add_argument("--hello", action="store_true", help="仅发射 M0 hello 壳")
    parser.add_argument("--src", help="从 .matha 源文件编译（缺省用内建整数样例）")
    args = parser.parse_args(argv)
    if args.hello:
        elf = hello_elf()
    elif args.src:
        elf = compile_to_elf(Path(args.src).read_text(encoding="utf-8"))
    else:
        elf = compile_to_elf(DEFAULT_SAMPLE)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(elf)
    print(f"native_elf 已发射 → {out}（{len(elf)} 字节，entry=0x{TEXT_VADDR:x}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
