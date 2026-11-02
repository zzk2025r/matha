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
  S3a 保底 _dtoa（精度可声明的回退路线，非最短往返）：精确十进制域 floatq（double=整数×2^-d，浅档 d≤6、|v|<9e9）
     经静态打标（字面量谓词 + 对 + - neg 封闭，* / 及越域降级 float），运行期 dtoa 叶例定点展开（×1e6 精确成整
     → int/frac 拆分 → 去尾零）逐字节=str(v)；越域运行期哨兵 → exit1 如实失败
  S3b 保底 _dtoa 优化 + 精度声明登记（域与输出字节零变更）：小数串缓冲单次 write_span、POW10 定标表去 scale/=10
     除法、循环不变量外提；dtoa_precision_declaration() 显式登记域/soundness/边界（与 _floatq_domain 单一事实源）
  S4a not float/floatq 真值判定（零 _dtoa/零 SSE）：弹出 double 位型 → and 清符掩码 → test 判零 ⇔ ±0.0 为假、
     非零（含越域 0.1 类、NaN、inf）为真，逐字节对 VM 一致；产出 bool 可直接输出/驱动分支。值能否“被打印”与本
     判定无关（越域 float 可判不可印，边界不变）
  S4b 浮点取整除 `//` 与求余 `%`（限 int/bool/floatq 精确域）：divsd → cvttsd2si 向零截断 → comisd 比回
     降一档得 floor（向 -inf）；零商符号随 q、零余数符号随除数（逐字节对 VM 一致）；除零与 |a|/|b|≥9e9 运行期
     护栏 exit1 如实失败（VM 侧同为失败口径）；越域 float 操作数静态如实拒——CPython float `//` 取的是精确
     有理商的 floor（0.1//0.01 类），非 floor(fl(a/b))，faithful 实现属 S4c+
  S3c-1（零风险首刀，**不改本文件能力面**）最短往返的**语义规格已在纯 Python 侧坐实**：.trae/pc_s3c1_ref.py 以
     精确有理值 + 整数十进制展开 + half-even 正确舍入 + 真往返验证复现 CPython repr(float)，50156 例逐字节全等（差 0）；
     为 S3c-5（机器码移植）备好可信基准与差分扫描骨架。前置勘察 .trae/pc_s3c2_scoping.py 已定死 S3c-2 扩域判据
     （双档并存而非替换、逐档上界 2^53/10^k、新档域全走定点不依赖科学计数法）
  S3c-2 floatq 定点展开**双档并存**扩域：浅档 d≤6/|v|<9e9 一字不动，另开深档 d≤10/|v|<2^53/10^10（=900719.9254740992）；
     dtoa 叶例仅加一个选档比较（只看 |v|，前置勘察⑦已证与“先试浅档再回退”逐字节等价）+ POW10 表扩至 10^9..10^0（浅档
     从 10^5 档入表）；新增**整数性回检**（cvtsi2sd 比回 N==v·scale）封住 `+ -` 封闭产生的“档空洞”（d∈7..10 且
     |v|≥深档阈 ⇒ N 非整会被截断）：此类值不静默印错，运行期 exit1 如实失败（Gate HOLE_CASES 锁行为）
  S3c-4 运行期特殊位型直出：OUTPUT float 支接位型三分支（abs vs 0x7FF0…：< 有限 / == ±inf 看符位 / > nan），
     inf/-inf/nan/±0 静态串直出（±0 复用带符 "0.0"）；有限非零正规值走 S3c-5d/6a，次正规如实 exit1
  S3c-5d 最短往返 dtoa_shortest（机器码，运行期 float 输出主力）：POW10 double 表 ucomisd 二分定档 nd →
     k=1..15 逐位 mulsd 生 E + cvtsd2si 就近半偶 → 128 位整数严格判据 |P−Q| < rhs10<<sh（恰等 tie→veven）→
     定点/科学排版（阈值 dec≤−4 或 dec>16）+ 负号前置；放行子集（sig≤15 且判据/表跨/E<<κ≤128 全过）逐字节==repr(v)，
     越子集运行期 exit1 如实拒（绝不伪通过）。.trae 模型 pipeline(v,crit_strict) 为放行权威，668 例全域 WSL 实跑差 0
  S3c-6a 最短往返 κ>63 解禁（判据算术升位）：将 dtoa_shortest 判据里的 P=E·B（B=2^κ）从「物化 64 位 B + mul」
     改为「对 E 做 128 位左移 κ」（shift_E_by_kappa），κ≥64 先验 bits(E)+κ≤128、逾位 jmp ds_rej——E<<κ≤128 的
     κ>63 小数十进制（0.0001 类）入域，与模型 crit_strict 的 P>M128 守卫逐值等价；表跨（|u|>18）/次正规仍如实拒
（以上为运行期 float 输出面；`/` 真除越域产 ±inf 与 VM ZeroDivisionError 已登记分歧；越域运行期 float 的 `//`/`%` 仍静态拒——见 S4b）。
列表元素 P-b 限 int/bool（同质）；首期字符串限 ASCII（多字节拒）。str×数值连接（需 itoa）/运行期（非字面量）计算的 str/异构列表 repr（需运行期标签）属 P-c1 后续；字面量 str/异构列表经编译期折叠已支持。
集合之外的构造（非 ASCII 串 / 字典 / 闭包 / 异常，及越域运行期 float 的 `//`/`%` 算术）一律 `NativeNotSupported` 显式拒绝（不臆造、不数值伪造）；运行期 float 输出改由 dtoa_shortest 全接管——放行子集逐字节精确、越子集运行期 exit_group(1) 如实失败（不再编译期拒）。
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
JE, JNE, JZ, JNZ, JS, JNS, JL, JGE, JLE, JG, JB = (
    0x84, 0x85, 0x84, 0x85, 0x88, 0x89, 0x8C, 0x8D, 0x8E, 0x8F, 0x82)
# P-c2 S3c-5d dtoa_shortest 追加：无符号比较/JC（JB 与 JC 同码 0x82）
JBE, JA, JC, JAE = 0x86, 0x87, 0x82, 0x83

# 数据段（RW）内固定偏移：numbuf / '\n' / "True" / "False" 后接 .bss 操作数栈
NL_OFF = NUMBUF_SIZE                 # 64：单字节 '\n'（每条 OUTPUT 行尾）
TRUE_OFF = NL_OFF + 1                # 65："True"（4）
FALSE_OFF = TRUE_OFF + 4             # 69："False"（5）
# P-c1 N2：列表 repr 字面量（紧随 "False" 后，均处于 VSP_OFF=0x100 前的空洞）
LB_OFF = FALSE_OFF + 5               # 74：'['
RB_OFF = LB_OFF + 1                  # 75：']'
Q_OFF = RB_OFF + 1                   # 76："'"（str 元素引号）
CMA_OFF = Q_OFF + 1                  # 77：", "（逗号+空格，连续 2 字节供 write_span）
POW10_OFF = 80                        # P-c2 S3b：dtoa 定标表（8 字节对齐；[79,VSP_OFF) 空洞内）
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
POW10_ADDR = DATA_VADDR + POW10_OFF   # P-c2 S3b/S3c-2：10^9..10^0 定标档（末置 0 哨兵），逐档 +8 取，免 scale/=10 除法
VSP_ADDR = DATA_VADDR + VSP_OFF
GVARS_ADDR = DATA_VADDR + GVARS_OFF   # 每个全局名一个 8 字节槽（slot 索引 → +8*slot）
HEAP_ADDR = DATA_VADDR + HEAP_OFF     # bump 堆首地址（r12 初始值）

# ---- P-c2 S3c-5d：最短往返 dtoa_shortest 的静态数据节（落在操作数栈 VSP+VSTACK=0x10100 之上、
#      GVARS=0x20000 之下的空洞；文件映射区，非 .bss，运行时只读）。与旧 floatq 定标表 POW10_OFF 独立。
P10D_LO = -324                        # double(10^m) 表下标下界（10^-324 最近 double = DBL_MIN，覆盖次正规下界）
P10D_N = 633                          # double 表项数 m=-324..308（decpt 二分定位 + 逐位 scale 共用；正确舍入=参考 pow10_table）
P10I_N = 19                           # 精确整数 10^n 表 n=0..18（10^19>2^64 越界 ⇒ 判据 pow10_out 拒）
P10D_OFF = 0x11000                    # double 表基（段内偏移；.double，索引 (m - P10D_LO)，每项 +8）
P10I_OFF = P10D_OFF + P10D_N * 8 + 8  # +8 留 double 表末 0 哨兵；整数 10^n 表基（段内偏移；.quad，索引 n）
STR_OFF = (P10I_OFF + P10I_N * 8 + 7) & ~7     # 特殊值串起点（段内偏移，8 字节对齐）
STR_INF_OFF = STR_OFF                 # "inf"（3B）
STR_NINF_OFF = STR_OFF + 3            # "-inf"（4B）
STR_NAN_OFF = STR_OFF + 7             # "nan"（3B，VM 口径小写、无符号）
STR_ZERO_OFF = STR_OFF + 10           # "0.0"（3B；-0.0 先出 '-' 再复用本串）
SBUF_OFF = (STR_OFF + 16 + 7) & ~7    # dtoa_shortest 十进制输出缓冲（自低向上写字节，单次 write_span 刷出）
SBUF_SIZE = 64                        # 上限：数字区[0,17) + 输出区[24,54)（17 位 + "." + "e+3xx" + 符号 ≤ 30，留裕）
STR_DATA_END = SBUF_OFF + SBUF_SIZE   # 数据节文件尾（段内偏移，= _build_data 的 bytearray 长度）
P10D_ADDR = DATA_VADDR + P10D_OFF
P10I_ADDR = DATA_VADDR + P10I_OFF
STR_INF = DATA_VADDR + STR_INF_OFF
STR_NINF = DATA_VADDR + STR_NINF_OFF
STR_NAN = DATA_VADDR + STR_NAN_OFF
STR_ZERO = DATA_VADDR + STR_ZERO_OFF
SBUF_ADDR = DATA_VADDR + SBUF_OFF     # dtoa_shortest 输出缓冲首地址

# ---- P-c2 S3c-5d：dtoa_shortest 的 128 位判据暂存槽（.bss 零页，位于文件尾之后、GVARS 之前）----
#   GPR 不够同时持有 A/B/P/Q/D/T 的 hi:lo 与循环不变量 ⇒ 溢出到固定寻址槽（_load_abs_rax/_store_rax_abs）。
SCR_OFF = (STR_DATA_END + 0xFF) & ~0xFF     # 页对齐到 0x12500（> 文件尾，属 .bss）；< VSP 之上、GVARS(0x20000) 之下
S_ALO, S_AHI = 0, 8                         # A（reduced 分子，可 ≤128 位）lo/hi
S_KAP = 16                                  # κ（_exact 约简分母 2^κ 的指数；S3c-6a 起判据走 E<<κ 128 位移位，不再物化 B）
S_SH = 24                                   # sh = he + κ（阈值 2 的幂指数，可负）
S_VEVEN = 32                                # v 尾数最低位==0（half-even tie 归向 v）
S_ND = 40                                   # nd（decpt，二分定档结果，有符号）
S_K = 48                                    # k（当前位数 1..15）
S_E = 56                                    # E（候选整数基串，≤64 位）
S_PLO, S_PHI = 64, 72                       # P（判据左积）lo/hi
S_QLO, S_QHI = 80, 88                       # Q lo/hi
S_DLO, S_DHI = 96, 104                      # D = |P−Q| lo/hi
S_TLO, S_THI = 112, 120                     # T（阈值）lo/hi
S_SIGN = 128                                # 输出符号（0/1）
S_M = 136                                   # M（53 位含隐藏位尾数，判据前 A 的未约前体）
SCR_SIZE = 152
_SC = DATA_VADDR + SCR_OFF                  # dtoa_shortest 判据暂存区绝对基址
_SALO, _SAHI = _SC + S_ALO, _SC + S_AHI     # A lo/hi（128 位 reduced 分子）
_SKAP, _SSH, _SVEVEN = _SC + S_KAP, _SC + S_SH, _SC + S_VEVEN
_SND = _SC + S_ND
_SE, _SPLO, _SPHI = _SC + S_E, _SC + S_PLO, _SC + S_PHI
_SQLO, _SQHI = _SC + S_QLO, _SC + S_QHI
_SDLO, _SDHI = _SC + S_DLO, _SC + S_DHI
_STLO, _STHI = _SC + S_TLO, _SC + S_THI
_SSIGN, _SM = _SC + S_SIGN, _SC + S_M

_CMP_SETCC = {"==": 0x94, "!=" : 0x95, "<": 0x9C, ">": 0x9F, "<=": 0x9E, ">=": 0x9D}
_ARITH = {"+", "-", "*", "//", "%"}
# ---- P-c2 S3b：_dtoa 精度声明的单一事实源（域谓词、护栏阈、机器码定标环共读此组常量）----
# P-c2 S3c-2 双档并存：浅档 d≤6/|v|<9e9 一字不动，另开深档 d≤10/|v|<2^53/10^10（前置勘察
# .trae/pc_s3c2_scoping.py 坐实「单档替换有 222/1215 回归⇒必须并存」与「选档只看 |v|」）
DTOA_MAX_DENOM_EXP = 6                              # 浅档 floatq 域：既约分母 ≤ 2^6（= 定点 6 位小数足够）
DTOA_SCALE = 10 ** DTOA_MAX_DENOM_EXP               # 1_000_000：浅档定点放大因子（v×此值为精确整数）
DTOA_ABS_LIMIT = 9e9                                # |v| < 此阈 → N=v×1e6 < 9e15 < 2^53 无舍入（兼作两档并集的粗界）
DTOA_MAX_DENOM_EXP_DEEP = 10                        # S3c-2 深档：既约分母 ≤ 2^10（二进制第 7~10 位定标值）
DTOA_SCALE_DEEP = 10 ** DTOA_MAX_DENOM_EXP_DEEP     # 10_000_000_000：1e10 为整值 double 精确可表
DTOA_ABS_LIMIT_DEEP = 2.0 ** 53 / DTOA_SCALE_DEEP   # 900719.9254740992：深档逐档收紧上界（N=v×1e10 < 2^53）
_ONE_M = DTOA_SCALE                                 # S3a _dtoa 定点放大因子 10^6
_ONE_M_BITS = struct.unpack("<q", struct.pack("<d", float(DTOA_SCALE)))[0]      # 1e6 的 double 位型
_ONE_M10_BITS = struct.unpack("<q", struct.pack("<d", float(DTOA_SCALE_DEEP)))[0]  # 1e10 的 double 位型
_LIMIT_BITS = struct.unpack("<q", struct.pack("<d", DTOA_ABS_LIMIT))[0]        # 9e9 域宽阈位型（N=v×1e6<9e15<2^53 精确）
_LIMIT_DEEP_BITS = struct.unpack("<q", struct.pack("<d", DTOA_ABS_LIMIT_DEEP))[0]  # 深档选档阈位型
# 定标表 [10^9..10^0,0]：浅档从 10^5 档入表（偏移 4×8），深档从 10^9 档入表（偏移 0）
_POW10_BASE_DEEP = 0
_POW10_BASE_SHALLOW = (DTOA_MAX_DENOM_EXP_DEEP - DTOA_MAX_DENOM_EXP) * 8
_JAE, _JP = 0x83, 0x8A                                # 近跳条件码（buf.jcc 发 0F xx rel32）：JAE / JP（0x9A 是 SETPE 非 Jcc！）


def dtoa_precision_declaration() -> dict:
    """P-c2 S3b/S3c：_dtoa 运行期输出精度的编译期声明（单一事实源，与域谓词/护栏/机器码共读）。

    保底 _dtoa（floatq 双档定点展开）保证域内值逐字节=str(v)；最短往返已由 S3c-5d
    dtoa_shortest 机器码落地（放行子集逐字节==repr(v)，越子集运行期 exit1 如实拒），
    其递降拆解 S3c-1..S3c-6 登记于 docs/spec/NATIVE_ELF_PC.md §N2-拆解。
    与 _floatq_domain 严格一致：域内 → 逐字节=str(v)；域外 → 静态拒或运行期护栏 exit_group(1)。"""
    return {
        "domain": (f"double 精确值 = 整数×2^-d 且 |v| 有界（**双档并存**：浅档 d≤{DTOA_MAX_DENOM_EXP} 且 "
                   f"|v|<{DTOA_ABS_LIMIT:g}；深档 d≤{DTOA_MAX_DENOM_EXP_DEEP} 且 "
                   f"|v|<{DTOA_ABS_LIMIT_DEEP!r}）；±0.0 属双档"),
        "scale": DTOA_SCALE,                              # 浅档定点展开因子（v×scale 为精确整数）
        "scale_deep": DTOA_SCALE_DEEP,                    # S3c-2 深档定点展开因子
        "tiers": ((DTOA_MAX_DENOM_EXP, DTOA_ABS_LIMIT), (DTOA_MAX_DENOM_EXP_DEEP, DTOA_ABS_LIMIT_DEEP)),
        "guarantee": "域内运行期输出逐字节 == str(v)（定点展开+去尾零，非最短往返；选档只看 |v|）",
        "soundness": ("四层：静态打标（字面量双档谓词 + `+ - neg` 封闭，`* /` 降级）/乘法前 "
                      f"{DTOA_ABS_LIMIT:g} 粗界护栏/转换后 N<0 哨兵/S3c-2 **整数性回检**（cvtsi2sd 比回 "
                      "N==v·scale，不等即 dt_oob——兼封住“封闭后档降不回”的空洞档）"),
        "out_of_domain": ("静态即 NativeNotSupported 拒；越界运行期 exit_group(1) 如实失败，绝不瞎编；"
                           "档空洞（封闭产 d∈7..10 且 |v|≥深档阈）由整数性回检转运行期失败"),
        "shortest_roundtrip": ("已实现（S3c-5d dtoa_shortest 机器码 + S3c-6a κ>63 解禁）：最短往返管线（定档→逐位生 E→128 位严格判据→排版）"
                               "对放行子集（sig≤15 且判据/表跨/E<<κ≤128 全过）逐字节==repr(v)（含 0.1 类/×÷产 float/科学计数法/κ>63 小数）；"
                               "越子集（16-17 位、10^22 表跨、E<<κ 逾 128 位等）运行期 exit1 如实拒；语义权威由 .trae/pc_s3c1_ref.py 参考器"
                               "与 .trae/pc_s3c5d1d_gates.py::pipeline(v,crit_strict) 坐实（668 例全域 WSL 实跑差 0）"),
    }


def _floatq_domain(v: float) -> bool:
    """_dtoa 保底域（**双档并存**，S3c-2）：double 精确值 = 整数×2^-d 且 |v| 有界。

    浅档 d≤6 且 |v|<9e9（S3a/S3b 原样，一字不动）；深档 d≤10 且 |v|<2^53/10^10（新增）。
    选档的判据只看 |v|（前置勘察⑦：与「先试浅档再回退深档」逐字节等价）：|v| < 深档阈 ⇒
    取 scale=1e10（域内任一档均 d≤10，故 v·1e10 必为整数且 N<2^53）；否则属域 ⇒ 只能靠浅档 d≤6 ⇒ 取 scale=1e6。
    非零最小元 2^-10=0.0009765625 ≥ Python 定点阈值 1e-4 ⇒ 两档域均永不触发科学计数法（S3c-3 不依赖）。
    ±0.0 属双档（'-0.0'/'0.0' 对齐 Python）；非精确二进有理十进制值（0.1 等，分母 2^55 量级）仍拒。
    阈参 dtoa_precision_declaration()。"""
    if v == 0.0:
        return True                                  # +0.0 与 -0.0
    if v != v or v in (float("inf"), float("-inf")):
        return False
    bits = struct.unpack("<q", struct.pack("<d", v))[0]
    e = (bits >> 52) & 0x7FF
    if e == 0:                                       # 次正规：分母 2^1074 越域
        return False
    m = (bits & ((1 << 52) - 1)) | (1 << 52)         # 含隐藏位的 53 位整数尾数
    k = 1075 - e                                     # 未既约分母 2^k（k≤0 → 整值）
    if k > DTOA_MAX_DENOM_EXP:                       # 既约：尾数拖尾零可约掉分母的 2 因子
        k -= (m & -m).bit_length() - 1               #拖尾零计数 ctz(m)
    if k <= DTOA_MAX_DENOM_EXP and abs(v) < DTOA_ABS_LIMIT:
        return True                                  # 浅档（与 S3a/S3b 完全同口径）
    return k <= DTOA_MAX_DENOM_EXP_DEEP and abs(v) < DTOA_ABS_LIMIT_DEEP   # S3c-2 深档
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


# ------------------------------------------------ P-c2 S3c-5d：dtoa_shortest 逐指令编码辅助

def _and_reg_imm32(buf: _Buf, reg: int, val: int) -> None:     # and reg,imm32（81 /4）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0x81, 0xE0 | (reg & 7)); buf.imm32(val)


def _or_reg_imm32(buf: _Buf, reg: int, val: int) -> None:      # or reg,imm32（81 /1）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0x81, 0xC8 | (reg & 7)); buf.imm32(val)


def _sub_reg_imm32(buf: _Buf, reg: int, val: int) -> None:     # sub reg,imm32（81 /5）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0x81, 0xE8 | (reg & 7)); buf.imm32(val)


def _cmp_reg_imm32(buf: _Buf, reg: int, val: int) -> None:     # cmp reg,imm32（81 /7 imm32；非 83 那是 imm8）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0x81, 0xF8 | (reg & 7)); buf.imm32(val)


def _movzx_rax_bl(buf: _Buf) -> None:                          # movzx rax,bl（40 0F B6 C7）
    buf.raw(0x48, 0x0F, 0xB6, 0xC7)


def _shl_reg_cl(buf: _Buf, reg: int) -> None:                  # shl reg,cl（D3 /4）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xD3, 0xC0 | (4 << 3) | (reg & 7))


def _shr_reg_cl(buf: _Buf, reg: int) -> None:                  # shr reg,cl（D3 /5）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xD3, 0xC0 | (5 << 3) | (reg & 7))


def _sar_reg_cl(buf: _Buf, reg: int) -> None:                  # sar reg,cl（D3 /7，算术右移）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xD3, 0xC0 | (7 << 3) | (reg & 7))


def _shl_reg_imm(buf: _Buf, reg: int, n: int) -> None:         # shl reg,imm8（C1 /4）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xC1, 0xC0 | (4 << 3) | (reg & 7)); buf.raw(n & 0xFF)


def _shr_reg_imm(buf: _Buf, reg: int, n: int) -> None:         # shr reg,imm8（C1 /5）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xC1, 0xC0 | (5 << 3) | (reg & 7)); buf.raw(n & 0xFF)


def _bsr_reg_reg(buf: _Buf, dst: int, src: int) -> None:       # bsr dst,src（0F BD /r）：最高置位位索引（src=0 未定义，需先 test）
    rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if src >= 8 else 0)
    buf.raw(rex, 0x0F, 0xBD, 0xC0 | ((dst & 7) << 3) | (src & 7))


def _mul_rax_reg(buf: _Buf, reg: int) -> None:                 # mul rax,reg（F7 /4）：rdx:rax = rax * reg
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xF7, 0xC0 | (4 << 3) | (reg & 7))


def _div_rax_reg(buf: _Buf, reg: int) -> None:                 # div rax,reg（F7 /6）：rax=商 rdx=余（被除数 rdx:rax）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xF7, 0xC0 | (6 << 3) | (reg & 7))


def _dec_reg(buf: _Buf, reg: int) -> None:                     # dec reg（FF /1）
    rex = 0x49 if reg >= 8 else 0x48
    buf.raw(rex, 0xFF, 0xC8 | (reg & 7))


def _mov_byte_rdi_al(buf: _Buf) -> None:                       # mov byte[rdi],al（88 07）
    buf.raw(0x88, 0x07)


def _inc_rdi(buf: _Buf) -> None:                               # inc rdi（48 FF C7）
    buf.raw(0x48, 0xFF, 0xC7)


def _sbb_reg_reg(buf: _Buf, dst: int, src: int) -> None:       # sbb dst,src（19 /r：dst -= src - CF）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x19, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _movq_gpr_to_xmm(buf: _Buf, xmm: int, gpr: int) -> None:   # movq xmm,gpr（66 先于 REX.W：66 4[0x] 0F 6E /r）reg=xmm rm=gpr
    rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if gpr >= 8 else 0)
    buf.raw(0x66, rex, 0x0F, 0x6E, 0xC0 | ((xmm & 7) << 3) | (gpr & 7))


def _movq_xmm_to_gpr(buf: _Buf, gpr: int, xmm: int) -> None:   # movq gpr,xmm（66 先于 REX.W：66 4[0x] 0F 7E /r）reg=xmm rm=gpr
    rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if gpr >= 8 else 0)
    buf.raw(0x66, rex, 0x0F, 0x7E, 0xC0 | ((xmm & 7) << 3) | (gpr & 7))


def _mulsd(buf: _Buf, dst: int, src: int) -> None:             # mulsd dst,src（F2 0F 59 /r）
    rex = 0x04 if dst >= 8 else 0x00
    pre = [0xF2] if rex == 0 else [0xF2, 0x40 | rex]
    buf.raw(*pre, 0x0F, 0x59, 0xC0 | ((dst & 7) << 3) | (src & 7))


def _ucomisd(buf: _Buf, dst: int, src: int) -> None:           # ucomisd dst,src（66 0F 2E /r）
    rex = 0x04 if dst >= 8 else 0x00
    pre = [0x66] if rex == 0 else [0x66, 0x40 | rex]
    buf.raw(*pre, 0x0F, 0x2E, 0xC0 | ((dst & 7) << 3) | (src & 7))


def _cvtsi2sd(buf: _Buf, xmm: int, gpr: int) -> None:          # cvtsi2sd xmm,gpr（F2 先于 REX.W：F2 4[0x] 0F 2A /r）reg=xmm rm=gpr
    rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if gpr >= 8 else 0)
    buf.raw(0xF2, rex, 0x0F, 0x2A, 0xC0 | ((xmm & 7) << 3) | (gpr & 7))


def _cvtsd2si(buf: _Buf, gpr: int, xmm: int) -> None:          # cvtsd2si gpr,xmm（F2 先于 REX.W：F2 4[0x] 0F 2D /r）reg=gpr(目的 r64) rm=xmm；就近半偶（2D 非 2C 截断）
    rex = 0x48 | (0x04 if gpr >= 8 else 0) | (0x01 if xmm >= 8 else 0)
    buf.raw(0xF2, rex, 0x0F, 0x2D, 0xC0 | ((gpr & 7) << 3) | (xmm & 7))


def _movsd_xmm_abs(buf: _Buf, xmm: int, addr: int) -> None:    # movsd xmm,[abs]（F2 0F 10 /r ModRM=05 disp32）
    rex = 0x04 if xmm >= 8 else 0x00
    if rex:
        buf.raw(0xF2, rex)
    buf.raw(0x0F, 0x10, 0x05 | ((xmm & 7) << 3)); buf.imm32(addr)


def _load_abs_mem_reg(buf: _Buf, reg: int, addr: int) -> None:  # mov reg,[abs]（REX.W 8B /0 ModRM=04 25 disp32）
    rex = 0x48 | (0x04 if reg >= 8 else 0) | (0x01 if reg >= 8 else 0)
    buf.raw(rex, 0x8B, 0x04, 0x25); buf.imm32(addr)


def _store_abs_reg_mem(buf: _Buf, addr: int, reg: int) -> None:  # mov [abs],reg（REX.W 89 /0 ModRM=04 25 disp32）
    rex = 0x48 | (0x04 if reg >= 8 else 0) | (0x01 if reg >= 8 else 0)
    buf.raw(rex, 0x89, 0x04, 0x25); buf.imm32(addr)


def _sub_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # sub dst,src（29 /r：reg=src rm=dst）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x29, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _and_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # and dst,src（21 /r：reg=src rm=dst）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x21, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _neg_reg(buf: _Buf, reg: int) -> None:                  # neg reg（F7 /3）
    rex = 0x48 | (0x01 if reg >= 8 else 0)
    buf.raw(rex, 0xF7, 0xD8 | (reg & 7))


def _shld_reg_reg_cl(buf: _Buf, dst: int, src: int) -> None:  # shld dst,src,cl（0F A5 /r：rm=dst reg=src）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x0F, 0xA5, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _imul_reg_reg_imm(buf: _Buf, dst: int, src: int, imm: int) -> None:  # imul dst,src,imm32（69 /r）
    rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if src >= 8 else 0)
    buf.raw(rex, 0x69, 0xC0 | ((dst & 7) << 3) | (src & 7)); buf.imm32(imm)


def _movapd(buf: _Buf, dst: int, src: int) -> None:         # movapd dst,src（66[44] 0F 28 /r：reg=dst rm=src）
    rex = 0x04 if dst >= 8 else 0x00
    pre = [0x66] if rex == 0 else [0x66, 0x40 | rex]
    buf.raw(*pre, 0x0F, 0x28, 0xC0 | ((dst & 7) << 3) | (src & 7))


def _movsd_xmm_regmem(buf: _Buf, xmm: int, base: int) -> None:  # movsd xmm,[base]（F2[44] 0F 10 mod00 rm=base）
    rex = 0x04 if xmm >= 8 else 0x00
    pre = [0xF2] if rex == 0 else [0xF2, 0x40 | rex]
    rm = base & 7
    if rm == 4:                                            # rsp/r12 → SIB base=100 index=none
        buf.raw(*pre, 0x0F, 0x10, 0x00 | ((xmm & 7) << 3) | 4, 0x24)
    elif rm == 5:                                          # rbp/r13 → mod01 disp8=0
        buf.raw(*pre, 0x0F, 0x10, 0x40 | ((xmm & 7) << 3) | 5, 0x00)
    else:
        buf.raw(*pre, 0x0F, 0x10, ((xmm & 7) << 3) | rm)


def _adc_reg_reg(buf: _Buf, dst: int, src: int) -> None:    # adc dst,src（11 /r：reg=src rm=dst，dst+=src+CF）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x11, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _or_reg_reg(buf: _Buf, dst: int, src: int) -> None:     # or dst,src（09 /r：reg=src rm=dst）
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    buf.raw(rex, 0x09, 0xC0 | ((src & 7) << 3) | (dst & 7))


def _movzx_byte_to(buf: _Buf, dst: int, base: int) -> None:  # movzx dst64, byte[base]（0F B6 /r mod00）
    rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if base >= 8 else 0)
    buf.raw(rex, 0x0F, 0xB6, ((dst & 7) << 3) | (base & 7))


def _mov_byte_rdi_imm(buf: _Buf, val: int) -> None:        # mov byte[rdi],imm8（C6 07 ib）
    buf.raw(0xC6, 0x07, val & 0xFF)


def _mov_byte_abs_al(buf: _Buf, addr: int) -> None:        # mov byte[abs],al（88 05 disp32）
    buf.raw(0x88, 0x05); buf.imm32(addr)



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


def _emit_dtoa_shortest(buf: _Buf) -> None:
    """P-c2 S3c-5d：运行期 float 最短往返输出（dtoa_shortest）。逐指令镜像已定稿严门
    `.trae/pc_s3c5d1d_gates.py` 管线：特殊值判别 → POW10 double 表 ucomisd 二分定档 nd →
    k=1..15 mulsd+cvtsd2si 生候选基串 E → crit_strict 128 位整数判据（含真守卫）→ 去尾零/
    进位 → 定点/科学排版入 SBUF → 单次 write_span 刷出。S3c-6a 起判据里 P=E·B 改由 E<<κ 的
    128 位左移达成（不再物化 B=2^κ），故解禁 κ>63 小数十进制（0.0001 类）；E<<κ 逾 128 位、
    表跨（|u|>18）、16-17 位扫尽、次正规一律 jmp exit1（运行期如实失败，绝不伪通过）。

    寄存器纪律：全程无 syscall 直到末次 flush ⇒ rcx/rdx/r8..r15 自由；rbx/rbp/r12/rsp 不碰；
    xmm0=av 持久，xmm1=表档，xmm2=p。计算态循环不跨 syscall（无 print_int）。"""
    def L(reg: int, addr: int) -> None:      # reg ← [addr]（经 rax 摆渡；_load_abs 仅支持 rax/r8）
        _load_abs_mem_reg(buf, 0, addr)
        if reg != 0:
            _mov_reg_reg(buf, reg, 0)

    def SR(addr: int, reg: int) -> None:     # [addr] ← reg
        if reg != 0:
            _mov_reg_reg(buf, 0, reg)
        _store_abs_reg_mem(buf, addr, 0)

    def OUTC(ch: int) -> None:               # mov byte[rdi],imm8 ; inc rdi
        _mov_byte_rdi_imm(buf, ch)
        _inc_rdi(buf)

    def shift_E_by_kappa(tag: str) -> None:  # S3c-6a：rax:rdx = E<<κ（κ=_SKAP, E=_SE）；>128 位 ⇒ jmp ds_rej
        #   镜像 crit_strict 的 P=E·B（B=2^κ）：κ≤63 恒 ≤126 位（单支无溢），κ≥64 需先验 bits(E)+κ≤128。
        L(1, _SKAP)                          # rcx=κ（L 经 rax 摆渡后 mov rcx,rax）
        L(0, _SE)                            # rax=E（rcx 不动）
        _cmp_reg_imm32(buf, 1, 64)
        buf.jcc(JGE, f"_ebk{tag}_big")
        _zero_reg(buf, 2)                    # rdx=0（移位源高字）
        _test_reg_reg(buf, 1, 1)
        buf.jcc(JZ, f"_ebk{tag}_done")       # κ==0 ⇒ P=E（rax=E、rdx=0）
        _shld_reg_reg_cl(buf, 2, 0)          # 0<κ<64：rdx=hi=E>>(64-κ)，rax=lo=E<<κ（≤126 位恒不溢）
        _shl_reg_cl(buf, 0)
        buf.jmp(f"_ebk{tag}_done")
        buf.here(f"_ebk{tag}_big")           # κ≥64：lo=0、hi=E<<(κ-64)，须验 bits(E)+κ≤128
        _cmp_reg_imm32(buf, 1, 128)
        buf.jcc(JGE, "ds_rej")               # κ≥128 ⇒ E<<κ 必>128 位 ⇒ prod_gt128 如实拒
        _mov_reg_reg(buf, 9, 0)              # r9=E（bsr 副本；E>0 由上游 jle ds_rej 保证）
        _bsr_reg_reg(buf, 9, 9)              # r9=⌊log2 E⌋
        _add_reg_imm32(buf, 9, 1)            # r9=bits(E)
        _add_reg_reg(buf, 9, 1)              # r9=bits(E)+κ
        _cmp_reg_imm32(buf, 9, 128)
        buf.jcc(JG, "ds_rej")                # bits(E)+κ>128 ⇒ P>2^128 ⇒ prod_gt128 如实拒
        _sub_reg_imm32(buf, 1, 64)           # rcx=κ-64（∈[0,63]）
        _shl_reg_cl(buf, 0)                  # rax=E<<(κ-64)=hi
        _mov_reg_reg(buf, 2, 0)              # rdx=hi
        _zero_reg(buf, 0)                    # lo=0
        buf.here(f"_ebk{tag}_done")

    buf.here("dtoa_shortest")
    # ---------------- Phase A：分类（符号/inf/nan/±0/次正规）----------------
    # SR/L 经 rax 摆渡会毁 rax，故符号先经 r8 存出（不动 rax），全程以 rax=abs 位型派生 e/frac/mant。
    _mov_reg_reg(buf, 10, 0)                # r10=bits
    _shr_reg_imm(buf, 10, 63)               # r10=sign(0/1)
    _mov_reg_reg(buf, 8, 10)                # r8=sign（经 r8 存出，不 clobber rax）
    _store_abs_reg_mem(buf, _SSIGN, 8)      # [_SSIGN]=sign
    mov_imm64(buf, 11, 0x7FFFFFFFFFFFFFFF)
    _and_reg_reg(buf, 0, 11)                # rax=abs 位型
    _movq_gpr_to_xmm(buf, 0, 0)             # xmm0=av
    _mov_reg_reg(buf, 1, 0)
    _shr_reg_imm(buf, 1, 52)                # rcx=e（指数字段）
    mov_imm64(buf, 11, (1 << 52) - 1)
    _mov_reg_reg(buf, 8, 0)
    _and_reg_reg(buf, 8, 11)                # r8=frac
    _mov_reg_reg(buf, 15, 8)                # r15=frac（e==0 判零/次正规用）
    _mov_reg_reg(buf, 9, 0)
    _and_reg_imm32(buf, 9, 1)               # v 尾数最低位
    _zero_reg(buf, 10)
    _test_reg_reg(buf, 9, 9)
    buf.jcc(JNZ, "ds_veodd")
    mov_imm32(buf, 10, 1)                   # veven=（lsb==0）
    buf.here("ds_veodd")
    SR(_SVEVEN, 10)
    mov_imm64(buf, 11, 1 << 52)
    _or_reg_reg(buf, 8, 11)                 # r8=mant_int（正规：(1<<52)|frac）；rax 此后不再需要
    SR(_SM, 1)                              # 持久 e（次正规/大值后续判据复用；clobber rax 安全）
    _cmp_reg_imm32(buf, 1, 0x7FF)
    buf.jcc(JE, "ds_infnan")
    _test_reg_reg(buf, 1, 1)
    buf.jcc(JNZ, "ds_normal")
    _test_reg_reg(buf, 15, 15)              # e==0：frac==0→零，否则次正规
    buf.jcc(JNZ, "ds_rej")                  # 次正规 kap>63 ⇒ 运行期如实拒

    # 零：±0.0（对齐 Python str：负号先出 '-' 再复用 "0.0"）
    buf.here("ds_zero")
    L(0, _SSIGN)
    _test_reg_reg(buf, 0, 0)
    buf.jcc(JZ, "ds_zerop")
    mov_imm32(buf, 6, DATA_VADDR)
    buf.raw(0xC6, 0x06, 0x2D)               # mov byte[rsi],'-'
    mov_imm32(buf, 2, 1)
    buf.call("write_span")
    buf.here("ds_zerop")
    mov_imm32(buf, 6, STR_ZERO)
    mov_imm32(buf, 2, 3)
    buf.jmp("ds_static_out")
    # inf / nan：静态串直出
    buf.here("ds_infnan")
    _test_reg_reg(buf, 15, 15)
    buf.jcc(JNZ, "ds_nan")
    L(0, _SSIGN)
    _test_reg_reg(buf, 0, 0)
    buf.jcc(JZ, "ds_infpos")
    mov_imm32(buf, 6, STR_NINF); mov_imm32(buf, 2, 4); buf.jmp("ds_static_out")
    buf.here("ds_infpos")
    mov_imm32(buf, 6, STR_INF); mov_imm32(buf, 2, 3); buf.jmp("ds_static_out")
    buf.here("ds_nan")
    mov_imm32(buf, 6, STR_NAN); mov_imm32(buf, 2, 3)
    buf.here("ds_static_out")
    buf.call("write_span")
    buf.raw(0xC3)

    # ---------------- 精确值 A/B/κ/he/sh（_exact 镜像；存槽）----------------
    buf.here("ds_normal")
    L(0, _SM)                               # rax=e
    _mov_reg_reg(buf, 7, 0)                 # rdi=e
    _sub_reg_imm32(buf, 7, 1075)            # rdi=exp2=e-1075
    _test_reg_reg(buf, 7, 7)
    buf.jcc(JS, "ds_expneg")
    # exp2>=0（B=1，A=mant<<exp2 可达 128 位）：he=e-1076, kap=0, sh=he
    _cmp_reg_imm32(buf, 7, 75)              # 53+exp2>128 ⇒ A 越 128 位 ⇒ 如实拒
    buf.jcc(JG, "ds_rej")
    mov_imm32(buf, 0, 0); SR(_SKAP, 0)      # κ=0（clobbers rax，故 he 改由 rdi=exp2 派生）
    _mov_reg_reg(buf, 6, 7)                 # rsi=exp2（rdi 未被 874 覆写）
    _sub_reg_imm32(buf, 6, 1)               # he=exp2-1=e-1076
    SR(_SSH, 6)                             # sh=he（kap=0）
    _mov_reg_reg(buf, 0, 8)                 # rax=mant
    _zero_reg(buf, 2)                       # rdx=0
    _cmp_reg_imm32(buf, 7, 64)
    buf.jcc(JGE, "ds_ashift_big")
    _test_reg_reg(buf, 7, 7)                # exp2==0 → lo=mant,hi=0
    buf.jcc(JZ, "ds_apos_store")
    _mov_reg_reg(buf, 1, 7)                 # cl=exp2(0<..<64)
    _shld_reg_reg_cl(buf, 2, 0)             # rdx=mant>>(64-cl)
    _shl_reg_cl(buf, 0)                     # rax=mant<<cl
    buf.jmp("ds_apos_store")
    buf.here("ds_ashift_big")               # exp2 in [64,75]：hi=mant<<(exp2-64),lo=0
    _mov_reg_reg(buf, 0, 8)
    _sub_reg_imm32(buf, 7, 64)
    _mov_reg_reg(buf, 1, 7)
    _shl_reg_cl(buf, 0)                     # rax=hi
    _mov_reg_reg(buf, 2, 0)                 # rdx=hi
    _zero_reg(buf, 0)                       # lo=0
    buf.here("ds_apos_store")
    SR(_SALO, 0); SR(_SAHI, 2)
    buf.jmp("ds_after_exact")
    # exp2<0：shift=1075-e；tz=mant 尾零；common=min(tz,shift)；A=mant>>common；kap=shift-common
    buf.here("ds_expneg")
    mov_imm32(buf, 6, 1075)
    _sub_reg_reg(buf, 6, 0)                 # rsi=shift=1075-e
    _mov_reg_reg(buf, 11, 8); _neg_reg(buf, 11)   # r11=-mant
    _mov_reg_reg(buf, 0, 8)
    _and_reg_reg(buf, 11, 0)                # r11=lowbit
    _bsr_reg_reg(buf, 11, 11)               # tz
    _cmp_reg_reg(buf, 11, 6)                # tz vs shift（均非负，无符号可）
    buf.jcc(JBE, "ds_have_common")
    _mov_reg_reg(buf, 11, 6)                # common=shift
    buf.here("ds_have_common")
    _mov_reg_reg(buf, 0, 8); _mov_reg_reg(buf, 1, 11)   # rax=mant, cl=common
    _shr_reg_cl(buf, 0)                     # A=mant>>common（≤53 位）
    SR(_SALO, 0); _zero_reg(buf, 2); SR(_SAHI, 2)
    _mov_reg_reg(buf, 14, 6); _sub_reg_reg(buf, 14, 11)  # r14=kap
    SR(_SKAP, 14)                           # 存 κ（S3c-6a 起可>63）；判据走 E<<κ 移位，不再物化 B、不再 kap>63 拒
    L(0, _SM)                               # 重载 e
    _mov_reg_reg(buf, 13, 0); _sub_reg_imm32(buf, 13, 1076)   # he=e-1076
    _cmp_reg_imm32(buf, 0, 1)
    buf.jcc(JNE, "ds_he_done")
    mov_imm32(buf, 13, -1075)              # e==1（最小正规）：he=-1075
    buf.here("ds_he_done")
    _add_reg_reg(buf, 13, 14)               # sh=he+kap
    SR(_SSH, 13)
    buf.here("ds_after_exact")

    # ---------------- Phase B：POW10 double 表 ucomisd 二分定档 nd ----------------
    L(0, _SM)                               # rax=e
    _sub_reg_imm32(buf, 0, 1023)            # e-1023
    _imul_reg_reg_imm(buf, 0, 0, 301)       # (e-1023)*301
    mov_imm32(buf, 1, 1000)
    buf.raw(0x48, 0x99)                     # cqo
    buf.raw(0x48, 0xF7, 0xF9)               # idiv rcx（向零）
    _test_reg_reg(buf, 2, 2)                # 余<0 ⇒ 需向 -inf 补一位（floor）
    buf.jcc(JNS, "ds_est")
    _dec_reg(buf, 0)
    buf.here("ds_est")
    _add_reg_imm32(buf, 0, 1)               # n0
    _mov_reg_reg(buf, 13, 0)                # r13=n（上升游标）
    buf.here("ds_rise")
    _cmp_reg_imm32(buf, 13, 308)            # n>308 ⇒ 表外 notable ⇒ 如实拒
    buf.jcc(JG, "ds_rej")
    _mov_reg_reg(buf, 0, 13); _add_reg_imm32(buf, 0, 324); _shl_reg_imm(buf, 0, 3)
    _add_reg_imm32(buf, 0, P10D_ADDR)
    _movsd_xmm_regmem(buf, 1, 0)            # xmm1=double(10^n)
    _ucomisd(buf, 0, 1)                     # av vs t
    buf.jcc(JB, "ds_rise_found")            # av<t → 首个上界
    _add_reg_imm32(buf, 13, 1)
    buf.jmp("ds_rise")
    buf.here("ds_rise_found")
    mov_imm32(buf, 14, -324)                # lo
    _mov_reg_reg(buf, 15, 13)               # hi
    buf.here("ds_bs")
    _cmp_reg_reg(buf, 14, 15)
    buf.jcc(JGE, "ds_bs_done")
    _mov_reg_reg(buf, 1, 14); _add_reg_reg(buf, 1, 15)
    buf.raw(0x48, 0xD1, 0xF9)               # sar rcx,1（floor((lo+hi)/2)）
    _mov_reg_reg(buf, 0, 1); _add_reg_imm32(buf, 0, 324); _shl_reg_imm(buf, 0, 3)
    _add_reg_imm32(buf, 0, P10D_ADDR)
    _movsd_xmm_regmem(buf, 1, 0)
    _ucomisd(buf, 0, 1)
    buf.jcc(JB, "ds_bs_hi")                 # av<t → hi=mid
    _mov_reg_reg(buf, 14, 1); _add_reg_imm32(buf, 14, 1)   # lo=mid+1
    buf.jmp("ds_bs")
    buf.here("ds_bs_hi")
    _mov_reg_reg(buf, 15, 1); buf.jmp("ds_bs")
    buf.here("ds_bs_done")                  # nd=r15
    _cmp_reg_imm32(buf, 15, -323); buf.jcc(JL, "ds_rej")
    _cmp_reg_imm32(buf, 15, 309); buf.jcc(JG, "ds_rej")
    SR(_SND, 15)

    # ---------------- Phase C+D：k=1..15 逐位生 E + crit_strict 判据 ----------------
    mov_imm32(buf, 13, 1)                   # k=1
    buf.here("ds_kloop")
    _mov_reg_reg(buf, 14, 13)               # scale_exp=k-nd
    L(0, _SND)
    _sub_reg_reg(buf, 14, 0)
    _cmp_reg_imm32(buf, 14, 308); buf.jcc(JG, "ds_rej")     # scale_out
    _cmp_reg_imm32(buf, 14, -324); buf.jcc(JL, "ds_rej")
    _mov_reg_reg(buf, 0, 14); _add_reg_imm32(buf, 0, 324); _shl_reg_imm(buf, 0, 3)
    _add_reg_imm32(buf, 0, P10D_ADDR)
    _movsd_xmm_regmem(buf, 1, 0)            # scale
    _movapd(buf, 2, 0)
    _mulsd(buf, 2, 1)                       # p=av*scale
    _cvtsd2si(buf, 0, 2)                    # E=round(p)（半偶）
    _test_reg_reg(buf, 0, 0)                # E<=0（含 INDEFINITE/溢出/表跨致 p≥2^63）⇒ 拒
    buf.jcc(JLE, "ds_rej")
    SR(_SE, 0)
    # u=nd-k
    L(0, _SND)
    _mov_reg_reg(buf, 14, 0)
    _sub_reg_reg(buf, 14, 13)
    _test_reg_reg(buf, 14, 14)
    buf.jcc(JS, "ds_crit_neg")
    # ---- u>=0：P=EB·10^u, Q=A, rhs10=1 ----
    _cmp_reg_imm32(buf, 14, 18); buf.jcc(JG, "ds_rej")      # pow10_out
    shift_E_by_kappa("u")                   # rax:rdx=EB=E<<κ（>128 位则 jmp ds_rej）
    _test_reg_reg(buf, 2, 2)
    buf.jcc(JNZ, "ds_eb_big")
    _test_reg_reg(buf, 14, 14); buf.jcc(JZ, "ds_p_done")    # u==0 → P=EB
    _mov_reg_reg(buf, 9, 0)                 # EB lo
    _mov_reg_reg(buf, 0, 14); _shl_reg_imm(buf, 0, 3); _add_reg_imm32(buf, 0, P10I_ADDR)
    _mov_reg_mem(buf, 10, 0, 0)             # r10=10^u
    _mov_reg_reg(buf, 0, 9)
    _mul_rax_reg(buf, 10)                   # P=EB*10^u
    buf.jmp("ds_p_done")
    buf.here("ds_eb_big")
    _test_reg_reg(buf, 14, 14); buf.jcc(JNZ, "ds_rej")      # EB>64 且 u!=0 → mid_gt64 拒
    buf.here("ds_p_done")
    SR(_SPLO, 0); SR(_SPHI, 2)
    L(0, _SALO); SR(_SQLO, 0)               # Q=A
    L(0, _SAHI); SR(_SQHI, 0)
    mov_imm32(buf, 7, 1)                    # rdi=rhs10=1
    buf.jmp("ds_crit_cmp")
    # ---- u<0：t=-u, P=E*B, Q=A*10^t（guard ≤128）, rhs10=10^t ----
    buf.here("ds_crit_neg")
    _neg_reg(buf,14)                        # t=-u
    _cmp_reg_imm32(buf, 14, 18); buf.jcc(JG, "ds_rej")
    shift_E_by_kappa("d")                   # rax:rdx=P=E<<κ（>128 位则 jmp ds_rej）
    SR(_SPLO, 0); SR(_SPHI, 2)
    L(8, _SALO); L(9, _SAHI)                # A lo/hi
    _mov_reg_reg(buf, 0, 14); _shl_reg_imm(buf, 0, 3); _add_reg_imm32(buf, 0, P10I_ADDR)
    _mov_reg_mem(buf, 10, 0, 0)             # r10=10^t
    _mov_reg_reg(buf, 0, 8); _mul_rax_reg(buf, 10)          # r8*10^t
    _mov_reg_reg(buf, 11, 2)                # r11=hi(r8*10^t)
    _mov_reg_reg(buf, 1, 0)                 # rcx=lo(r8*10^t)=Qlo
    _mov_reg_reg(buf, 0, 9); _mul_rax_reg(buf, 10)          # r9*10^t
    _test_reg_reg(buf, 2, 2); buf.jcc(JNZ, "ds_rej")        # r9*10^t≥2^64 → prod_gt128 拒
    _add_reg_reg(buf, 11, 0); buf.jcc(JC, "ds_rej")         # Qhi 溢出 → 拒
    _mov_reg_reg(buf, 2, 11)                # rdx=Qhi
    SR(_SQLO, 1); SR(_SQHI, 2)
    _mov_reg_reg(buf, 7, 10)                # rdi=rhs10=10^t
    buf.here("ds_crit_cmp")
    # ---- D=|P-Q|（128）；T=rhs10<<sh 或 D<<=-sh ----
    L(0, _SPLO); _mov_reg_reg(buf, 8, 0)    # r8=Plo
    L(0, _SPHI); _mov_reg_reg(buf, 9, 0)    # r9=Phi
    L(0, _SQLO); _mov_reg_reg(buf, 10, 0)   # r10=Qlo
    L(0, _SQHI); _mov_reg_reg(buf, 11, 0)   # r11=Qhi
    _mov_reg_reg(buf, 0, 8); _sub_reg_reg(buf, 0, 10)       # Dlo
    _mov_reg_reg(buf, 2, 9); _sbb_reg_reg(buf, 2, 11)       # Dhi
    _test_reg_reg(buf, 2, 2)
    buf.jcc(JNS, "ds_dneg_done")
    buf.raw(0x48, 0xF7, 0xD0)               # not rax（~Dlo）
    buf.raw(0x48, 0xF7, 0xD2)               # not rdx（~Dhi）
    buf.raw(0x48, 0x83, 0xC0, 0x01)         # add rax,1（+1 低段）
    buf.raw(0x48, 0x83, 0xD2, 0x00)         # adc rdx,0（进位入高段）——128 位求负得 |D|
    buf.here("ds_dneg_done")
    SR(_SDLO, 0); SR(_SDHI, 2)
    L(0, _SSH); _mov_reg_reg(buf, 14, 0)    # r14=sh
    _test_reg_reg(buf, 14, 14)
    buf.jcc(JS, "ds_dshl")
    # ---- sh>=0：T=rhs10<<sh ----
    _cmp_reg_imm32(buf, 14, 68); buf.jcc(JG, "ds_rej")      # thr_gt128
    _mov_reg_reg(buf, 0, 7)                 # rax=rhs10
    _zero_reg(buf, 2)
    _cmp_reg_imm32(buf, 14, 64)
    buf.jcc(JGE, "ds_tshift_big")
    _test_reg_reg(buf, 14, 14); buf.jcc(JZ, "ds_t_done")    # sh==0 → T=rhs10
    _mov_reg_reg(buf, 1, 14)
    _shld_reg_reg_cl(buf, 2, 0)
    _shl_reg_cl(buf, 0)
    buf.jmp("ds_t_done")
    buf.here("ds_tshift_big")               # sh in [64,68]：lo=0,hi=rhs10<<(sh-64)
    _sub_reg_imm32(buf, 14, 64); _mov_reg_reg(buf, 1, 14)
    _shl_reg_cl(buf, 0)                     # rax=hi
    _mov_reg_reg(buf, 2, 0)                 # rdx=hi
    _zero_reg(buf, 0)                       # lo=0
    buf.here("ds_t_done")
    SR(_STLO, 0); SR(_STHI, 2)
    buf.jmp("ds_cmpdt")
    # ---- sh<0：s=-sh，D<<=s（守卫 ≤128）；T=rhs10 ----
    buf.here("ds_dshl")
    _neg_reg(buf, 14)                       # s
    _cmp_reg_imm32(buf, 14, 128); buf.jcc(JGE, "ds_rej")    # shl_gt128
    _cmp_reg_imm32(buf, 14, 64)
    buf.jcc(JGE, "ds_dsbig")
    L(2, _SDHI); L(0, _SDLO)               # 先取 Dhi→rdx（L 经 rax 摆渡），再取 Dlo→rax（否则会覆写 rax）
    _test_reg_reg(buf, 14, 14); buf.jcc(JZ, "ds_ds_done")
    _mov_reg_reg(buf, 1, 14)
    _shld_reg_reg_cl(buf, 2, 0)
    _shl_reg_cl(buf, 0)
    buf.jmp("ds_ds_done")
    buf.here("ds_dsbig")
    L(2, _SDHI); L(0, _SDLO)               # 同序：Dhi→rdx、Dlo→rax
    _test_reg_reg(buf, 2, 2); buf.jcc(JNZ, "ds_rej")
    _sub_reg_imm32(buf, 14, 64); _mov_reg_reg(buf, 1, 14)
    _shl_reg_cl(buf, 0)
    _mov_reg_reg(buf, 2, 0); _zero_reg(buf, 0)
    buf.here("ds_ds_done")
    SR(_SDLO, 0); SR(_SDHI, 2)
    _mov_reg_reg(buf, 0, 7); _zero_reg(buf, 2)              # T=rhs10
    SR(_STLO, 0); SR(_STHI, 2)
    # ---- 比较 D vs T（先 hi 后 lo；恰等 tie→veven）----
    buf.here("ds_cmpdt")
    L(0, _STHI); _mov_reg_reg(buf, 8, 0)    # r8=Thi
    L(0, _SDHI)
    _cmp_reg_reg(buf, 0, 8)
    buf.jcc(JB, "ds_hit")
    buf.jcc(JA, "ds_miss")
    L(0, _STLO); _mov_reg_reg(buf, 8, 0)    # r8=Tlo
    L(0, _SDLO)
    _cmp_reg_reg(buf, 0, 8)
    buf.jcc(JB, "ds_hit")
    buf.jcc(JA, "ds_miss")
    L(0, _SVEVEN); _test_reg_reg(buf, 0, 0); buf.jcc(JNZ, "ds_hit")
    buf.jmp("ds_miss")
    buf.here("ds_miss")
    _add_reg_imm32(buf, 13, 1)              # k++
    _cmp_reg_imm32(buf, 13, 15); buf.jcc(JLE, "ds_kloop")
    buf.jmp("ds_rej")                       # 15 位扫尽 ⇒ 如实拒

    # ---------------- Phase E：排版（E→数字→去尾零/进位→定点/科学）----------------
    buf.here("ds_hit")
    L(0, _SE)                               # rax=E
    mov_imm32(buf, 1, 10)                   # rcx=10
    mov_imm64(buf, 14, SBUF_ADDR)           # 数字区基
    _zero_reg(buf, 15)                      # ndigits=0
    buf.here("ds_dig")
    _zero_reg(buf, 2)
    _div_rax_reg(buf, 1)                    # quot=rax, rem=rdx
    _add_reg_imm32(buf, 2, 48)
    _mov_reg_reg(buf, 8, 14); _add_reg_reg(buf, 8, 15)
    buf.raw(0x41, 0x88, 0x10)               # mov byte[r8],dl
    _add_reg_imm32(buf, 15, 1)
    _test_reg_reg(buf, 0, 0)
    buf.jcc(JNZ, "ds_dig")
    _mov_reg_reg(buf, 10, 15)               # r10=orig ndigits（dec bump 用）
    L(0, _SND); _mov_reg_reg(buf, 9, 0)     # r9=nd
    _mov_reg_reg(buf, 8, 14)                # r8=SBUF 基（后复用为读游标）
    _zero_reg(buf, 15)                      # i=0
    buf.here("ds_copy")
    _cmp_reg_reg(buf, 15, 10); buf.jcc(JGE, "ds_copy_done")
    _mov_reg_reg(buf, 6, 8); _add_reg_reg(buf, 6, 10); _sub_reg_imm32(buf, 6, 1)  # rsi=base+orig-1（r10=orig，非立即数 9）
    _sub_reg_reg(buf, 6, 15)                # -i（r15=游标，非立即数 15）
    _movzx_byte_to(buf, 0, 6)               # al=cand MSB[i]
    mov_imm64(buf, 7, SBUF_ADDR + 40)
    _add_reg_reg(buf, 7, 15)
    buf.raw(0x88, 0x07)                     # mov byte[rdi],al
    _add_reg_imm32(buf, 15, 1)
    buf.jmp("ds_copy")
    buf.here("ds_copy_done")
    _mov_reg_reg(buf, 15, 10)               # cand_len=orig（E 无尾零）
    # bump=（orig>k）
    _cmp_reg_reg(buf, 10, 13)
    mov_imm32(buf, 0, 0)
    buf.jcc(JLE, "ds_bump0")
    mov_imm32(buf, 0, 1)
    buf.here("ds_bump0")
    _add_reg_reg(buf, 9, 0)                 # r9=dec
    # 输出游标 rdi=SBUF+24
    mov_imm64(buf, 7, SBUF_ADDR + 24)
    # 负号：正常有限值排版前置 '-'（[_SSIGN] 于 Phase A 存出；rax 此处空闲）
    L(0, _SSIGN)
    _test_reg_reg(buf, 0, 0)
    buf.jcc(JZ, "ds_sign_done")
    OUTC(0x2D)
    buf.here("ds_sign_done")
    # 阈值：dec<=-4 或 dec>16 → 科学；否则定点
    _cmp_reg_imm32(buf, 9, -4); buf.jcc(JLE, "ds_sci")
    _cmp_reg_imm32(buf, 9, 16); buf.jcc(JG, "ds_sci")
    _cmp_reg_imm32(buf, 9, 0); buf.jcc(JLE, "ds_fixed_nonpos")
    # dec>0
    _cmp_reg_reg(buf, 15, 9)                # cand_len vs dec
    buf.jcc(JG, "ds_fixed_split")           # cand_len>dec → d[0:dec].'d[dec:]
    # cand_len<=dec → cand + '0'*(dec-cand_len) + '.0'
    _mov_reg_reg(buf, 6, 15); _sub_reg_reg(buf, 6, 9)       # r6=orig-dec（pad 数）？ 需 dec-cand_len
    _mov_reg_reg(buf, 6, 9); _sub_reg_reg(buf, 6, 15)       # pad=dec-cand_len
    _zero_reg(buf, 15)                      # i=0
    _mov_reg_reg(buf, 8, 14); _add_reg_imm32(buf, 8, 40)   # r8=candbuf
    buf.here("ds_fp1")
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _add_reg_imm32(buf, 15, 1)
    _cmp_reg_reg(buf, 15, 10); buf.jcc(JL, "ds_fp1")
    _zero_reg(buf, 15)
    buf.here("ds_fp2")
    _cmp_reg_reg(buf, 15, 6); buf.jcc(JGE, "ds_fp3")
    OUTC(0x30)
    _add_reg_imm32(buf, 15, 1); buf.jmp("ds_fp2")
    buf.here("ds_fp3")
    OUTC(0x2E); OUTC(0x30)
    buf.jmp("ds_emit")
    # dec>0 ∧ cand_len>dec → cand[0:dec]+'.'+cand[dec:]
    buf.here("ds_fixed_split")
    _zero_reg(buf, 15)
    _mov_reg_reg(buf, 8, 14); _add_reg_imm32(buf, 8, 40)   # r8=candbuf
    buf.here("ds_fs1")
    _cmp_reg_reg(buf, 15, 9); buf.jcc(JGE, "ds_fs2")
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _add_reg_imm32(buf, 15, 1); buf.jmp("ds_fs1")
    buf.here("ds_fs2")
    OUTC(0x2E)
    buf.here("ds_fs3")
    _cmp_reg_reg(buf, 15, 10); buf.jcc(JGE, "ds_emit")
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _add_reg_imm32(buf, 15, 1); buf.jmp("ds_fs3")
    # dec<=0 → '0.' + '0'*(-dec) + cand
    buf.here("ds_fixed_nonpos")
    OUTC(0x30); OUTC(0x2E)
    _mov_reg_reg(buf, 6, 9); _neg_reg(buf, 6)              # r6=-dec（≥0）
    _zero_reg(buf, 15)
    buf.here("ds_fn1")
    _cmp_reg_reg(buf, 15, 6); buf.jcc(JGE, "ds_fn2")
    OUTC(0x30); _add_reg_imm32(buf, 15, 1); buf.jmp("ds_fn1")
    buf.here("ds_fn2")
    _zero_reg(buf, 15)
    _mov_reg_reg(buf, 8, 14); _add_reg_imm32(buf, 8, 40)   # r8=candbuf
    buf.here("ds_fn3")
    _cmp_reg_reg(buf, 15, 10); buf.jcc(JGE, "ds_emit")
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _add_reg_imm32(buf, 15, 1); buf.jmp("ds_fn3")
    # 科学：cand[0]['.'+cand[1:]]e{dec-1:+03d}（dec-1 可 3 位）
    buf.here("ds_sci")
    _mov_reg_reg(buf, 8, 14); _add_reg_imm32(buf, 8, 40)   # r8=candbuf
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _cmp_reg_imm32(buf, 10, 1); buf.jcc(JLE, "ds_sci_exp")
    OUTC(0x2E)
    _zero_reg(buf, 15)
    _mov_reg_reg(buf, 6, 10); _sub_reg_imm32(buf, 6, 1)    # r6=尾数位数 cand_len-1（尾循环上界）
    buf.here("ds_sc2")
    _cmp_reg_reg(buf, 15, 6); buf.jcc(JGE, "ds_sci_exp")
    _movzx_byte_to(buf, 0, 8); _mov_byte_rdi_al(buf); _inc_rdi(buf); _add_reg_imm32(buf, 8, 1)
    _add_reg_imm32(buf, 15, 1); buf.jmp("ds_sc2")
    buf.here("ds_sci_exp")
    OUTC(0x65)
    _sub_reg_imm32(buf, 9, 1)               # exp=dec-1
    _test_reg_reg(buf, 9, 9); buf.jcc(JNS, "ds_expp")
    OUTC(0x2D); _neg_reg(buf, 9); buf.jmp("ds_expn")
    buf.here("ds_expp")
    OUTC(0x2B)
    buf.here("ds_expn")
    # r9=mag（≥0）；百/十/个，最少 2 位（与 Python `{exp:+03d}` 同形）
    _mov_reg_reg(buf, 0, 9); _zero_reg(buf, 2)
    mov_imm32(buf, 1, 100)
    _div_rax_reg(buf, 1)                    # rax=hundreds, rdx=mag%100
    _mov_reg_reg(buf, 10, 2)                # r10=mag%100
    _test_reg_reg(buf, 0, 0); buf.jcc(JZ, "ds_exp_two")
    _add_reg_imm32(buf, 0, 48); _mov_byte_rdi_al(buf); _inc_rdi(buf)   # 百位
    buf.jmp("ds_exp_tens")
    buf.here("ds_exp_two")
    _mov_reg_reg(buf, 10, 10)               # 保持 r10
    buf.here("ds_exp_tens")
    _mov_reg_reg(buf, 0, 10); _zero_reg(buf, 2)
    mov_imm32(buf, 1, 10)
    _div_rax_reg(buf, 1)                    # rax=tens, rdx=ones
    _add_reg_imm32(buf, 0, 48); _mov_byte_rdi_al(buf); _inc_rdi(buf)   # 十位（允许 0）
    _add_reg_imm32(buf, 2, 48); _mov_reg_reg(buf, 0, 2); _mov_byte_rdi_al(buf); _inc_rdi(buf)   # 个位
    buf.jmp("ds_emit")
    buf.here("ds_emit")
    mov_imm64(buf, 6, SBUF_ADDR + 24)
    _mov_reg_reg(buf, 2, 7)
    _sub_reg_reg(buf, 2, 6)                 # rdx=长度
    buf.call("write_span")
    buf.raw(0xC3)
    buf.here("ds_rej")
    buf.jmp("exit1")


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

    # dtoa：rax=float 位型（双档保底域：浅档整数×2^-d，d≤6，|v|<9e9；深档 d≤10，|v|<2^53/10^10）→ 定点十进制输出（不含换行，OUTPUT 追加）。
    #   算法：翻 abs 位 → 选档（只看 |v|）→ mulsd ×scale（域内精确成整，<2^53 无舍入）→ cvttsd2si N →
    #   整数性回检（cvtsi2sd 比回）→ intpart=N//scale 走 print_int；frac=N%scale：去尾零（frac/=10）与定标档下移同步（保有效前导零，如 0.015625）。
    #   S3b 优化：小数串 '.<digits>' 逐位缓冲进 numbuf 低端后【单次 write_span】统一输出（每位不再
    #   一次 syscall + movabs 重置 rsi）；定标环以 POW10 表逐档 +8 取除数（每位除法由 2→ 1，去 scale/=10）；
    #   循环不变量 mov ecx,10 外提为一次。输出字节与 S3a 逐字节一致（全域扇描已验）。
    #   负数先出 '-'（-0.0 → '-0.0' 对齐 Python str）。越域哨兵（cvttsd2si INDEFINITE 致 N 负 或 |v|≥9e9）
    #   → dt_oob → exit1（如实失败，不瞎编输出）。
    #   寄存器：只用 rax/rcx/rdx/rsi/rdi/r9/r10/r11/r13/r14/r15 + xmm0/xmm1/xmm2/xmm3；不碰 rbx/rbp/r12；
    #   print_int/write_span 不触碰 r13/r14/r15（循环态安全）；但 **syscall 毁 rcx/r11**（内核 ABI：
    #   rcx=rip、r11=rflags），而负号的 '-' 要写（走 write_span→syscall），故本档定点因子由
    #   不被 syscall 破坏的 r9 携带，到 dt_ns（写完符号）后才 `mov rcx,r9` 供 div 用。
    buf.here("dtoa")
    _mov_reg_reg(buf, 10, 0)                          # mov r10,rax（存符号）
    buf.raw(0x49, 0xC1, 0xEA, 63)                     # shr r10,63（sign 0/1）
    mov_imm64(buf, 11, 0x7FFFFFFFFFFFFFFF)            # movabs r11,清符掩码
    buf.raw(0x4C, 0x21, 0xD8)                         # and rax,r11（REX.W+R：r11 在 ModRM reg 域需 REX.B——0x49；mod=11）
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC0)             # movq xmm0,rax（abs 位型）
    mov_imm64(buf, _REG["rax"], _LIMIT_BITS)          # movabs rax,9e9 位型（运行期域宽护栏：乘法前！）
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xD0)             # movq xmm2,rax
    buf.raw(0x66, 0x0F, 0x2E, 0xC2)                   # ucomisd xmm0,xmm2（|v| vs 9e9；reg=xmm0 rm=xmm2）
    buf.jcc(_JAE, "dt_oob")                           # ≥9e9 → 越域（含相等；两档并集的粗界）
    buf.jcc(_JP, "dt_oob")                            # 无序（NaN 类，静态域本不可达）→ 兜底拒
    # ---- P-c2 S3c-2 选档（只看 |v|，与前置勘察⑦的「先试浅档再回退」逐字节等价）----
    mov_imm64(buf, _REG["rax"], _LIMIT_DEEP_BITS)     # movabs rax,深档阈 900719.9254740992 位型
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xD8)             # movq xmm3,rax
    buf.raw(0x66, 0x0F, 0x2E, 0xC3)                   # ucomisd xmm0,xmm3（|v| vs 深档阈）
    buf.jcc(JB, "dt_tier_deep")                       # < 深档阈 → 深档 scale=1e10、从 10^9 档入表
    mov_imm64(buf, 9, _ONE_M)                         # r9=浅档定点因子 10^6（r9 不被 syscall 破坏，见上）
    mov_imm64(buf, _REG["rax"], _ONE_M_BITS)          # 1e6 的 double 位型
    mov_imm32(buf, 14, _POW10_BASE_SHALLOW)           # r14=定标表基偏移（10^5 档）
    buf.jmp("dt_tier_done")
    buf.here("dt_tier_deep")
    mov_imm64(buf, 9, DTOA_SCALE_DEEP)                # r9=深档定点因子 10^10
    mov_imm64(buf, _REG["rax"], _ONE_M10_BITS)        # 1e10 的 double 位型
    mov_imm32(buf, 14, _POW10_BASE_DEEP)              # r14=定标表基偏移（10^9 档）
    buf.here("dt_tier_done")
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC8)             # movq xmm1,rax（所选档定标因子）
    buf.raw(0xF2, 0x0F, 0x59, 0xC1)                   # mulsd xmm0,xmm1
    buf.raw(0xF2, 0x48, 0x0F, 0x2C, 0xC0)             # cvttsd2si rax,xmm0（N；66 48 0F 2C 是 cvttpd2pi 只写低 32 位——错！）
    buf.raw(0x48, 0x85, 0xC0)                         # test rax,rax
    buf.jcc(JNS, "dt_nn")
    buf.jmp("dt_oob")                                 # 负（含 INDEFINITE 哨兵）→ 越域如实失败
    buf.here("dt_nn")
    # ---- P-c2 S3c-2 整数性回检（双档引入的必需护栏）：double(N) 必须严格 == v·scale ----
    #   静态打标对 `+ -` 封闭，封闭后的值档（d）可能「降到浅档区间却 d∈7..10」的空洞，
    #   此时 N 非整数→被 cvttsd2si 截断→不回头检查就会「静默印错」。回检不过→dt_oob 如实失败（不瞎编）。
    buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0xC8)             # cvtsi2sd xmm1,rax（N 回转 double；整数转 double 是 0F 2A——0F 2C 是 cvttsd2si，误用会把 rcx 当目标毁掉定点因子）
    buf.raw(0x66, 0x0F, 0x2E, 0xC8)                   # ucomisd xmm1,xmm0（与 v·scale 比严格相等）
    buf.jcc(JNE, "dt_oob")                            # 不等 → 该值不属所选档
    buf.jcc(_JP, "dt_oob")                            # 无序（NaN 类）兜底
    _mov_reg_reg(buf, 15, 0)                          # mov r15,rax（N）
    _test_reg_reg(buf, 10, 10)                        # 符号位？
    buf.jcc(JZ, "dt_ns")
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)           # numbuf 低端单字符缓冲（print_int 自高位向下写，不冲突）
    buf.raw(0xC6, 0x06, 0x2D)                         # mov byte[rsi],'-'
    mov_imm32(buf, _REG["rdx"], 1); buf.call("write_span")
    buf.here("dt_ns")
    _mov_reg_reg(buf, 1, 9)                           # mov rcx,r9（本档定点因子；符号 write_span 的 syscall 已毁过 rcx）
    _mov_reg_reg(buf, 0, 15)                          # mov rax,r15
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx → rax=整部, rdx=frac（rcx=所选档定点因子）
    _mov_reg_reg(buf, 13, 2)                          # mov r13,rdx（frac；print_int 不碰 r13）
    buf.call("print_int")                             # 整部（为 0 时也出 '0'）
    # ---- S3b 优化：小数部分 '.<digits>' 一次性缓冲到 numbuf 低端后单次 write_span（免逐位 syscall/movabs）----
    mov_imm64(buf, _REG["rdi"], DATA_VADDR)           # 小数串缓冲游标（numbuf 低端；print_int 自顶向下写不冲突）
    buf.raw(0xC6, 0x07, 0x2E)                         # mov byte[rdi],'.'
    buf.raw(0x48, 0xFF, 0xC7)                         # inc rdi
    _test_reg_reg(buf, 13, 13)                        # frac==0 → 补单 '0'（整数值 → '3.0'）
    buf.jcc(JNZ, "dt_strip")
    buf.raw(0xC6, 0x07, 0x30)                         # mov byte[rdi],'0'
    buf.raw(0x48, 0xFF, 0xC7)                         # inc rdi
    buf.jmp("dt_frac_out")
    buf.here("dt_strip")                              # 去尾零（保留有效前导零，如 0.015625）：while frac%10==0: frac/=10, 定标档下移（r14 作表字节偏移）
    # r14 已由选档段置为本档入表基偏移（S3c-2：浅档 32 / 深档 0），不再重置
    mov_imm32(buf, _REG["rcx"], 10)                   # 循环不变量 mov ecx,10（外提，勿每轮重置）
    buf.here("dt_sloop")
    _mov_reg_reg(buf, 0, 13)                          # mov rax,r13（frac）
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    buf.raw(0x48, 0xF7, 0xF1)                         # div rcx → rax=frac/10, rdx=frac%10
    buf.raw(0x48, 0x85, 0xD2)                         # test rdx,rdx
    buf.jcc(JNZ, "dt_scale_init")                     # 余≠0 → 尾零剥尽（档位停在正确档），转定标输出
    _mov_reg_reg(buf, 13, 0)                          # mov r13,rax（frac/=10）
    _add_reg_imm32(buf, 14, 8)                        # add r14,8（定标档下移一档）
    buf.jmp("dt_sloop")
    buf.here("dt_scale_init")                         # 高位起逐位：divisor=POW10[off..]，digit=frac/divisor（免 scale/=10 除法）
    mov_imm64(buf, _REG["rsi"], POW10_ADDR)           # 定标表游标
    _add_reg_reg(buf, 6, 14)                          # add rsi,r14（游标 += 剥零后的档位偏移）
    buf.here("dt_o_loop")
    buf.raw(0x48, 0x8B, 0x06)                         # mov rax,[rsi]（divisor；末档 0 作哨兵）
    _test_reg_reg(buf, 0, 0)                          # test rax,rax
    buf.jcc(JZ, "dt_frac_out")                        # divisor==0 → 小数位输出完毕
    _mov_reg_reg(buf, 11, 0)                          # mov r11,rax（divisor）
    _mov_reg_reg(buf, 0, 13)                          # mov rax,r13（frac）
    buf.raw(0x31, 0xD2)                               # xor edx,edx
    buf.raw(0x49, 0xF7, 0xF3)                         # div r11（商=digit，余=frac）
    _mov_reg_reg(buf, 13, 2)                          # mov r13,rdx（frac%=divisor）
    buf.raw(0x83, 0xC0, 0x30)                         # add eax,'0'
    buf.raw(0x88, 0x07)                               # mov byte[rdi],al（数字入缓冲）
    buf.raw(0x48, 0xFF, 0xC7)                         # inc rdi
    buf.raw(0x48, 0x83, 0xC6, 0x08)                   # add rsi,8（下一定标档）
    buf.jmp("dt_o_loop")
    buf.here("dt_frac_out")                           # 单次 write_span：rsi=缓冲首(DATA_VADDR)，rdx=游标-首
    mov_imm64(buf, _REG["rsi"], DATA_VADDR)
    _mov_reg_reg(buf, 2, 7)                           # mov rdx,rdi
    buf.raw(0x48, 0x29, 0xF2)                         # sub rdx,rsi（长度）
    buf.call("write_span")
    buf.here("dt_ret")
    buf.raw(0xC3)
    buf.here("dt_oob")                                # 运行期越域哨兵：exit1（已登记行为，不瞎编）
    buf.jmp("exit1")

    # P-c2 S3c-5d：最短往返 dtoa_shortest（运行期 float 输出；接 OUTPUT "float" 支）
    _emit_dtoa_shortest(buf)


def _load_frac(buf: _Buf, xmm: int, typ: str, disp: int) -> None:
    """xmm ← 操作数栈槽 [rbx+disp] 的数值（P-c2 S2）：float/floatq 直载 64 位位型（movsd）；
    int/bool 符号扩展转双精度（cvtsi2sd REX.W）。movsd/cvtsi2sd m64 无 16B 对齐要求。"""
    if typ in ("float", "floatq"):
        buf.raw(0xF2, 0x0F, 0x10, 0x40 | (xmm << 3) | 3, disp & 0xFF)         # movsd xmm,[rbx+disp8]
    else:
        buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0x40 | (xmm << 3) | 3, disp & 0xFF)   # cvtsi2sd xmm,[rbx+disp8]


def _emit_fbinop(buf: _Buf, sym: str, ta: str, tb: str, is_cmp: bool, i: int) -> None:
    """P-c2 S2：SSE2 标量浮点算术（addsd/subsd/mulsd/divsd）与比较（ucomisd+setcc）。

    算术产运行期 float（输出需 _dtoa，未就绪按 Q1 如实拒）；比较产 bool（可直接输出），
    故 S2 的算术/比较以「比较消费 float」形态外部可验。NaN 护栏：ucomisd 无序时 ZF=CF=PF=1，
    故 <,<=,>,>=,== 需「无序→强制 0」、!= 需「无序→强制 1」（对齐 Python：除 != 外 NaN 比较均 False）。
    除零：divsd 产 ±inf，与 VM（ZeroDivisionError 参考失败）存在已登记分歧，不伪对齐。
    P-c2 S4b：`//` / `%` 取整除与求余转 `_emit_findiv`（商/余均可打印且逐字节对 VM 一致）。
    """
    if sym in ("//", "%"):
        _emit_findiv(buf, sym, ta, tb, i)
        return
    if sym not in _FCMP_SETCC and sym not in ("+", "-", "*", "/"):
        raise NativeNotSupported(f"BINOP {sym!r} 越 float/SSE 域（取整/求余由 S4b 接管）：{ta},{tb}")
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


def _f_abs_guard(buf: _Buf, xmm: int, oob: str) -> None:
    """S4b：运行域护栏 |xmm| < DTOA_ABS_LIMIT（与 _dtoa 乘法前护栏同口径）：越界/无序 → oob。

    暂存 xmm6（abs 值）/xmm7（阈），只借 rax/rcx，不碰 rbx/rbp/r12。"""
    mov_imm64(buf, _REG["rcx"], 0x7FFFFFFFFFFFFFFF)             # movabs rcx,清符掩码
    buf.raw(0x66, 0x48, 0x0F, 0x7E, 0xC0 | (xmm << 3))          # movq rax,xmm{xmm}（reg=xmm, rm=rax）
    buf.raw(0x48, 0x21, 0xC8)                                   # and rax,rcx（abs 位型）
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC0 | (6 << 3))            # movq xmm6,rax
    mov_imm64(buf, _REG["rax"], _LIMIT_BITS)                    # movabs rax,9e9 位型
    buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC0 | (7 << 3))            # movq xmm7,rax
    buf.raw(0x66, 0x0F, 0x2E, 0xF7)                             # ucomisd xmm6,xmm7
    buf.jcc(_JAE, oob)                                          # ≥9e9 → 越域如实失败
    buf.jcc(_JP, oob)                                           # 无序兜底


def _emit_findiv(buf: _Buf, sym: str, ta: str, tb: str, i: int) -> None:
    """P-c2 S4b：浮点取整除 `//` 与求余 `%` 的运行期 SSE2 机器码（逐字节对齐 VM/CPython）。

    口径（CPython：float_floor_div = floor(iv/fv)；float_mod = 精确余数且零余数符号随除数）：
      1) 除零护栏：xorpd 造 +0.0 → ucomisd b,0 → jp/je → oob。VM 对 x//0、x%0 抛 MathaRuntimeError，
         本侧 exit_group(1) 同为「如实失败」（不同于 S2 `/` 的 ±inf 分歧，此处两边皆失败）。
      2) 域护栏 `_f_abs_guard`：|a|、|b| 均须 <DTOA_ABS_LIMIT（与 _dtoa 同口径），因为 4) 的精确性证明依赖此界。
      3) q = divsd a,b（与 CPython 同一次正确舍入的 IEEE 除法）→ t = cvttsd2si q（向零截断）
         → INDEFINITE 哨兵（t==0x8000000000000000，覆盖 NaN 与超 int64）→ oob
         → 比回：comisd q,(double)t；若 q < t（负非整）→ dec t（向 -inf 修正，即 floor）。
      4) `//` 结果 = (double)t；若 t==0 → 或上 q 的符号位（floor(-0.0) = -0.0 对齐 Python）。
         `%` 结果 r = a - t·b：域内（a=m/2^d、b=n/2^e，d,e≤6，|a|<9e9）有 t·n ≤ |a|·2^e < 2^39
         → t·b 与 a - t·b 均无舍入精确，故与 CPython 的精确余数逐位相同；若 r 为 ±0.0（用 add rax,rax
         判零，丢符位后为 0 仅 ±0.0，连次正规也不误判）→ 强制取 b 的符号（Python 零余数随除数号）。
    域约束：`//` 与 `%` 均仅接受 int/bool/floatq 操作数。越域 float 的 `//` 必须静态如实拒——
    CPython 的 float_floor_div 取的是**精确有理商**的 floor，而非 floor(fl(a/b))：实测
    0.001/0.0001 == 10.0 而 0.001//0.0001 == 9.0、1.0//0.1 == 9.0、0.3//0.1 == 2.0，
    本侧 divsd 路径给 10.0/10.0/3.0 与之分歧（要 faithful 需有理数/多精度路线，属 S4c+）；
    越域 float 的 `%` 同理无法证明余数逐字节精确。域内 int 操作数经 cvtsi2sd 精确，语义与
    整数域一致，结果仍归 floatq。
    寄存器：rax/rcx/rdx + xmm0(q/结果)/xmm1(b)/xmm2/xmm3(仅 %: 存 a)/xmm6-xmm7(护栏)；不碰 rbx/rbp/r12。
    """
    oob = f"fd_oob{i}"
    if ta not in ("int", "bool", "float", "floatq") or tb not in ("int", "bool", "float", "floatq"):
        raise NativeNotSupported(f"BINOP {sym!r} 操作数需 int/bool/float：{ta},{tb}")
    if sym in ("//", "%") and (ta not in ("int", "bool", "floatq") or tb not in ("int", "bool", "floatq")):
        raise NativeNotSupported(
            f"{sym} 仅支持 int/bool/floatq 精确域操作数（越域 float 需精确有理商 floor 语义，"
            f"逐字节 faithful 属 S4c+）：{ta},{tb}")
    _load_frac(buf, 0, ta, -16)                                 # xmm0 ← a
    _load_frac(buf, 1, tb, -8)                                  # xmm1 ← b
    buf.raw(0x48, 0x83, 0xEB, 0x10)                             # sub rbx,16（弹二）
    if sym == "%":
        buf.raw(0x66, 0x0F, 0x28, 0xD8)                         # movapd xmm3,xmm0（存 a 备 r=a-t·b）
    buf.raw(0x66, 0x0F, 0x57, 0xD2)                             # xorpd xmm2,xmm2（+0.0）
    buf.raw(0x66, 0x0F, 0x2E, 0xCA)                             # ucomisd xmm1,xmm2（b vs 0）
    buf.jcc(_JP, oob)
    buf.jcc(JE, oob)
    _f_abs_guard(buf, 0, oob)                                   # |a| 域护栏（// 与 % 同需：结果须经 _dtoa 可印）
    _f_abs_guard(buf, 1, oob)                                   # |b| 域护栏
    buf.raw(0xF2, 0x0F, 0x5E, 0xC1)                             # divsd xmm0,xmm1 → q
    buf.raw(0x66, 0x48, 0x0F, 0x7E, 0xC1)                       # movq rcx,xmm0（q 位型：备零商符号）
    buf.raw(0xF2, 0x48, 0x0F, 0x2C, 0xC0)                       # cvttsd2si rax,xmm0（t=trunc(q)）
    mov_imm64(buf, _REG["rdx"], -0x8000000000000000)             # movabs rdx,0x8000000000000000（哨兵）
    buf.raw(0x48, 0x39, 0xD0)                                   # cmp rax,rdx（rm=rax, reg=rdx）
    buf.jcc(JE, oob)                                            # NaN/超 int64 → 如实失败
    buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0xD0)                       # cvtsi2sd xmm2,rax（(double)t）
    buf.raw(0x66, 0x0F, 0x2E, 0xC2)                             # comisd xmm0,xmm2（q vs t）
    buf.jcc(_JAE, f"fd_ok{i}")                                  # CF=0（q ≥ t，有序）→ 免修正；CF=1（q<t）落下 dec
    buf.raw(0x48, 0xFF, 0xC8)                                   # dec rax（负非整 → 向 -inf 降一档）
    buf.here(f"fd_ok{i}")
    if sym == "//":
        buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0xC0)                   # cvtsi2sd xmm0,rax（整值商回双）
        buf.raw(0x48, 0x85, 0xC0)                               # test rax,rax
        buf.jcc(JNZ, f"fd_st{i}")
        buf.raw(0x48, 0xC1, 0xE9, 63)                           # shr rcx,63（q 符号位）
        buf.raw(0x48, 0xC1, 0xE1, 63)                           # shl rcx,63（→ 0 或 0x8000…）
        buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xD1)                   # movq xmm2,rcx
        buf.raw(0x66, 0x0F, 0x56, 0xC2)                         # orpd xmm0,xmm2（零商随 q 号）
    else:
        buf.raw(0xF2, 0x48, 0x0F, 0x2A, 0xD0)                   # cvtsi2sd xmm2,rax（(double)n）
        buf.raw(0xF2, 0x0F, 0x59, 0xD1)                         # mulsd xmm2,xmm1（n·b：域内精确）
        buf.raw(0x66, 0x0F, 0x28, 0xC3)                         # movapd xmm0,xmm3（a）
        buf.raw(0xF2, 0x0F, 0x5C, 0xC2)                         # subsd xmm0,xmm2（r=a-n·b：精确）
        buf.raw(0x66, 0x48, 0x0F, 0x7E, 0xC0)                   # movq rax,xmm0（r 位型）
        buf.raw(0x48, 0x01, 0xC0)                               # add rax,rax（仅 ±0.0 归零）
        buf.jcc(JNZ, f"fd_st{i}")
        buf.raw(0x66, 0x48, 0x0F, 0x7E, 0xC9)                   # movq rcx,xmm1（b 位型）
        buf.raw(0x48, 0xC1, 0xE9, 63)                           # shr rcx,63
        buf.raw(0x48, 0xC1, 0xE1, 63)                           # shl rcx,63
        buf.raw(0x66, 0x48, 0x0F, 0x6E, 0xC1)                   # movq xmm0,rcx（零余数随除数号）
    buf.here(f"fd_st{i}")
    buf.raw(0x66, 0x0F, 0x11, 0x03)                             # movsd [rbx],xmm0（结果回栈）
    buf.raw(0x48, 0x83, 0xC3, 0x08)                             # add rbx,8
    buf.jmp(f"fd_end{i}")                                      # 跳过越域跳板（否则落下即 exit1）
    buf.here(oob)
    buf.jmp("exit1")                                            # 除零/越域：exit_group(1) 如实失败
    buf.here(f"fd_end{i}")


def _emit_binop(buf: _Buf, sym: str, typ: list, i: int) -> None:
    if len(typ) < 2:
        raise NativeNotSupported(f"BINOP {sym!r}：操作数栈不足")
    tb, ta = typ[-1], typ[-2]
    is_cmp = sym in _CMP_SETCC
    if sym == "/" or "float" in (ta, tb) or "floatq" in (ta, tb):   # P-c2 S2/S3a：'/' 真除与 float/floatq 域操作数走 SSE2
        _emit_fbinop(buf, sym, ta, tb, is_cmp, i)
        typ.pop(); typ.pop()
        if is_cmp:
            typ.append("bool")
        elif sym in ("//", "%"):
            # S4b：// 商为整值 double（既约分母 d=0）、% 余数 = a - n·b（分母 ≤2^6 且 |r|<|b|）→ 均属 floatq；
            #       |v|≥9e9 的越界由 _dtoa 乘法前护栏 exit1 如实失败（不瞎编）
            typ.append("floatq")
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
        if t in ("float", "floatq"):                             # P-c2 S4a：真值判定在位域上做，不涉 _dtoa/算术
            # |尾数+指数位| == 0 ⇔ ±0.0 ⇔ Python bool(v)==False；NaN/inf 位域非零 → 真 ✓（越域 float 也可判定）
            buf.raw(0x48, 0x83, 0xEB, 0x08); buf.raw(0x48, 0x8B, 0x03)   # sub rbx,8; mov rax,[rbx]（double 位型）
            mov_imm64(buf, _REG["rcx"], 0x7FFFFFFFFFFFFFFF)             # movabs rcx,清符掩码
            buf.raw(0x48, 0x21, 0xC8)                                   # and rax,rcx（abs 位型：mod=11 reg=rcx rm=rax）
            buf.raw(0x48, 0x85, 0xC0)                                   # test rax,rax
            buf.raw(0x0F, 0x94, 0xC0)                                   # sete al（±0.0 → 1）
            buf.raw(0x0F, 0xB6, 0xC0)                                   # movzx eax,al
            _push_rax(buf)
            typ.pop(); typ.append("bool")
            return
        if t not in ("int", "bool"):                            # 串等其它值型真值语义需额外机器，如实拒
            raise NativeNotSupported(f"not 操作数需 int/bool/float：{t!r}（串真值判定属后续）")
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
                    # P-c2 S3a/S3c-2：运行期精确十进制域（双档：d≤6/|v|<9e9 或 d≤10/|v|<2^53·10^-10）
                    #   → dtoa 叶例定点展开（域内天然=str(v)）
                    buf.raw(0x48, 0x8B, 0x43, 0xF8); buf.call("dtoa")     # mov rax,[rbx-8]
                else:
                    # P-c2 S3c-5d：任意运行期 float → dtoa_shortest（最短往返）。
                    #   域内逐字节==repr(v)；域外（次正规/kap>63/位宽超 128/表跨/15 位扫尽）
                    #   运行期 exit_group(1) 如实失败（与已登记越域输出代价口径一致，绝不伪通过）。
                    buf.raw(0x48, 0x8B, 0x43, 0xF8); buf.call("dtoa_shortest")   # mov rax,[rbx-8]
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
    seg = bytearray(STR_DATA_END)
    seg[NL_OFF] = 0x0A
    seg[TRUE_OFF:TRUE_OFF + 4] = b"True"
    seg[FALSE_OFF:FALSE_OFF + 5] = b"False"
    seg[LB_OFF] = 0x5B                         # '['
    seg[RB_OFF] = 0x5D                         # ']'
    seg[Q_OFF] = 0x27                          # "'"
    seg[CMA_OFF:CMA_OFF + 2] = b", "           # ', '
    # P-c2 S3b/S3c-2：dtoa 定标表 10^9..10^0（每项 8 字节小端），末尾多一个 0 作逐位输出哨兵
    #   浅档（k=6）从 10^5 档入表（偏移 _POW10_BASE_SHALLOW），深档（k=10）从 10^9 档入表（偏移 0）
    for _k in range(DTOA_MAX_DENOM_EXP_DEEP):          # 10^9,10^8,...,10^0（共 10 档）
        _v = 10 ** (DTOA_MAX_DENOM_EXP_DEEP - 1 - _k)
        seg[POW10_OFF + 8 * _k:POW10_OFF + 8 * _k + 8] = struct.pack("<Q", _v)
    seg[POW10_OFF + 8 * DTOA_MAX_DENOM_EXP_DEEP:POW10_OFF + 8 * DTOA_MAX_DENOM_EXP_DEEP + 8] = struct.pack("<Q", 0)  # 哨兵
    # P-c2 S3c-5d：最短往返 dtoa_shortest 数据节（正确舍入 double(10^m) 表 + 精确整数 10^n 表 + 特殊值串）。
    #   double 表逐档与参考器 pc_s3c5bc_dataflow.pow10_table 严格同值：10^m 仅 1 位有效数字 ⇒ float(10**m)
    #   与 1/10**(-m)（CPython int 真除正确舍入）均 = double(10^m)，与参考 Decimal 路径无精度差异 ⇒ 逐位一致。
    for _m in range(P10D_LO, P10D_LO + P10D_N):        # m=-324..308（覆盖全部有限值 decpt 定位与 scale）
        _d = float(10 ** _m) if _m >= 0 else 1 / (10 ** (-_m))
        _o = P10D_OFF + 8 * (_m - P10D_LO)
        seg[_o:_o + 8] = struct.pack("<d", _d)
    _o = P10D_OFF + 8 * P10D_N                          # double 表末 0 哨兵（定位越上界兜底，与参考 notable 同效）
    seg[_o:_o + 8] = struct.pack("<Q", 0)
    for _n in range(P10I_N):                            # 10^0..10^18 精确整数（判据 lhs/rhs 的 10 的幂乘子）
        _o = P10I_OFF + 8 * _n
        seg[_o:_o + 8] = struct.pack("<Q", 10 ** _n)
    seg[STR_INF_OFF:STR_INF_OFF + 3] = b"inf"          # 特殊值直出串（OUTPUT 统一追加 '\n'）
    seg[STR_NINF_OFF:STR_NINF_OFF + 4] = b"-inf"
    seg[STR_NAN_OFF:STR_NAN_OFF + 3] = b"nan"
    seg[STR_ZERO_OFF:STR_ZERO_OFF + 3] = b"0.0"
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
