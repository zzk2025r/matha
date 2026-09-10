# -*- coding: utf-8 -*-
"""M3V 字节码 → x86-64 原生机器码（Windows PE64 可执行文件）。

不经过 C 中转：Matha 源码 → AST → M3V 字节码（src.mbc.compiler）
→ 本模块直接发射 x86-64 机器码 → 手写 PE64 链接为 .exe。

运行时模型（Win64 Microsoft ABI）：
  - R12 为操作数栈指针（栈体在数据段，向上增长；push: [r12]=v; add r12,8）
  - 局部变量在原生 RBP 帧上：local i ↔ [rbp - 8*(nlocals-i)]
  - 函数参数经操作数栈传递，callee 序言搬入局部槽
  - call 前 RSP 16 字节对齐，callee 至少保留 32 字节影子空间

里程碑支持：
  int/bool 常量、LOAD/STORE_LOCAL、LOAD/STORE_GLOBAL（含全局函数地址）、
  CALL/RET（顶层函数/递归）、JMP/JZ/JNZ、BINOP(+ - * // % == != < > <= >=)、
  UNARYOP(neg not)、DUP、POP、OUTPUT（十进制整数+换行）、HALT
明确不支持（抛 NativeNotSupported）：
  字符串/列表/dict/切片/属性/闭包/BOX/OUTER 访问、浮点 '/'、'**'、'in'。
"""
from __future__ import annotations

import struct
from pathlib import Path

from src.mbc import opcodes as OP

# ---- 节区布局常量 ----
TEXT_RVA = 0x1000             # .text 节 RVA（代码）
DATA_RVA = 0x2000            # .data 节 RVA（可写数据：API槽/单元/栈/缓冲）
HEADERS_SIZE = 0x200
IMAGE_BASE = 0x140000000

# 运行时自行解析的 kernel32 API（经 PEB 遍历 + 导出表，不依赖 PE 导入表）
_APIS = ["GetStdHandle", "WriteFile", "ExitProcess"]

VSTACK_SIZE = 0x10000         # 64KB 操作数栈
NUMBUF_SIZE = 64              # 整数输出缓冲


class NativeNotSupported(Exception):
    """原生后端暂不支持的字节码/数据类型。"""


# ---------------------------------------------------------------- 发射工具

class _Emitter:
    """在节区载荷中发射机器码并管理重定位。"""

    def __init__(self, base_rva: int, labels: dict | None = None):
        self.buf = bytearray()
        self.base_rva = base_rva
        self.labels: dict[str, int] = labels if labels is not None else {}
        # (载荷偏移, 标签)：RIP 相对 rel32（代码用）
        self.rip_relocs: list[tuple[int, str]] = []
        # (载荷偏移, 标签)：rel8 短跳
        self.rel8_relocs: list[tuple[int, str]] = []
        # (载荷偏移, 标签)：绝对 RVA dword（数据结构用：ILT/描述符）
        self.abs_relocs: list[tuple[int, str]] = []

    @property
    def off(self) -> int:
        return len(self.buf)

    @property
    def rva(self) -> int:
        return self.base_rva + len(self.buf)

    def label_here(self, name: str):
        if name in self.labels:
            raise AssertionError(f"标签重复: {name}")
        self.labels[name] = self.rva

    def emit(self, data: bytes):
        self.buf.extend(data)

    def align(self, n: int):
        while len(self.buf) % n:
            self.buf.append(0)

    def rel32_to(self, label: str):
        """RIP 相对：补 4 字节占位，patch 阶段填 (target - next_rva)。"""
        self.rip_relocs.append((len(self.buf), label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def rel8_to(self, label: str):
        """短跳：补 1 字节占位，patch 阶段填 (target - next_off)。"""
        self.rel8_relocs.append((len(self.buf), label))
        self.buf.append(0)

    def abs_dword(self, label: str):
        """绝对 RVA 槽（导入表数据用）：补 4 字节占位。"""
        self.abs_relocs.append((len(self.buf), label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def patch(self):
        for off, label in self.rip_relocs:
            disp = self.labels[label] - (self.base_rva + off + 4)
            self.buf[off:off + 4] = struct.pack("<i", disp)
        for off, label in self.rel8_relocs:
            disp = self.labels[label] - (self.base_rva + off + 1)
            if not -128 <= disp <= 127:
                raise AssertionError(f"rel8 越界: {label} disp={disp}")
            self.buf[off] = disp & 0xFF
        for off, label in self.abs_relocs:
            self.buf[off:off + 4] = struct.pack("<I", self.labels[label])

    # ---- 操作数栈（R12）----
    def push_rax(self):
        self.emit(b"\x49\x89\x04\x24")               # mov [r12], rax
        self.emit(b"\x49\x83\xC4\x08")               # add r12, 8

    def pop_to(self, reg: int):
        self.emit(b"\x49\x83\xEC\x08")               # sub r12, 8
        self.emit(bytes([0x49, 0x8B, 0x04 | (reg << 3), 0x24]))  # mov reg,[r12]

    def read_top_to(self, reg: int):
        # push 后 r12 指向栈顶之上：读 [r12-8]
        self.emit(bytes([0x49, 0x8B, 0x44 | ((reg & 7) << 3), 0x24, 0xF8]))  # mov reg,[r12-8]

    def discard(self):
        self.emit(b"\x49\x83\xEC\x08")               # sub r12, 8

    # ---- 寻址片段 ----
    def mov_rax_imm64(self, v: int):
        self.emit(b"\x48\xB8" + struct.pack("<q", v))

    def load_local(self, slot: int, nlocals: int):
        disp = -8 * (nlocals - slot)
        self.emit(b"\x48\x8B\x85" + struct.pack("<i", disp))  # mov rax,[rbp+disp]
        self.push_rax()

    def store_local(self, slot: int, nlocals: int):
        self.pop_to(0)
        disp = -8 * (nlocals - slot)
        self.emit(b"\x48\x89\x85" + struct.pack("<i", disp))  # mov [rbp+disp],rax

    def lea_rip(self, reg: int, label: str):
        rex = 0x48 | (0x04 if reg >= 8 else 0)       # lea r64,[rip+disp]
        self.emit(bytes([rex, 0x8D, 0x05 | ((reg & 7) << 3)]))
        self.rel32_to(label)

    def load_global(self, label: str):
        self.emit(b"\x48\x8B\x05")                   # mov rax,[rip+disp]
        self.rel32_to(label)
        self.push_rax()

    def store_global(self, label: str):
        self.pop_to(0)
        self.emit(b"\x48\x89\x05")                   # mov [rip+disp],rax
        self.rel32_to(label)

    def call_rip_indirect(self, label: str):
        self.emit(b"\xFF\x15")                       # call [rip+disp]
        self.rel32_to(label)

    def call_rel32(self, label: str):
        self.emit(b"\xE8")                           # call rel32
        self.rel32_to(label)

    def jcc_rel32(self, cc: int | None, label: str):
        if cc is None:
            self.emit(b"\xE9")                       # jmp rel32
        else:
            self.emit(bytes([0x0F, cc]))             # Jcc rel32
        self.rel32_to(label)


# ---------------------------------------------------------------- 指令发射

_CC = {"==": 0x94, "!=": 0x95, "<": 0x9C,
       ">": 0x9F, "<=": 0x9E, ">=": 0x9D}


def _emit_prologue(em: _Emitter, arity: int, nlocals: int):
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    frame = max(0x20, (nlocals * 8 + 15) & ~15)
    if frame < 128:
        em.emit(b"\x48\x83\xEC" + bytes([frame]))   # sub rsp,imm8
    else:
        em.emit(b"\x48\x81\xEC" + struct.pack("<i", frame))
    for i in range(arity):
        src_disp = -8 * (arity - i)                 # arg0 在栈中最低处
        dst_disp = -8 * (nlocals - i)
        em.emit(bytes([0x4D, 0x8B, 0x54, 0x24, src_disp & 0xFF]))  # mov r10,[r12+d8]（REX=WRB=0x4D：r10 目标、r12 基址、无索引）
        em.emit(b"\x4C\x89\x95" + struct.pack("<i", dst_disp))      # mov [rbp+d32],r10
    if arity:
        em.emit(b"\x49\x83\xEC" + bytes([arity * 8]))  # sub r12, arity*8


def _emit_epilogue(em: _Emitter):
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp (ModRM EC: rsp<-rbp)
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret


MAX_NATIVE_ARITY = 8


def _emit_call_apply(em: _Emitter, scratch: str, fn_arity: int):
    """M3V CALL 1：栈顶为 1 个实参，其下为函数块。

    arity==1（常见递归场景）：直接调用，返回值覆盖函数槽，弹掉实参槽。
    arity>1：暂不支持柯里化（抛 NativeNotSupported）。
    """
    if fn_arity > 1:
        raise NativeNotSupported(
            f"原生后端暂不支持多参数函数的柯里化调用（arity={fn_arity}）")
    # arity==1：栈布局 [函数, arg1]
    # callee 序言 sub r12,8 后：返回值在 [r12-8]，函数槽在 [r12-16]
    em.emit(b"\x49\x8B\x44\x24\xF0")   # mov rax,[r12-16]  函数地址
    em.emit(b"\xFF\xD0")                # call rax
    em.emit(b"\x49\x89\x44\x24\xF0")   # mov [r12-16],rax  返回值覆盖函数槽
    em.emit(b"\x49\x83\xEC\x08")       # sub r12,8


def _emit_resolve_apis(em: _Emitter):
    """引导：PEB 遍历找 kernel32 基址，解析导出表，填充 api_* 槽。

    不依赖 PE 导入表（手写 PE 的数据目录导入在部分加载器上被静默忽略，
    故采用运行时自解析）。寄存器约定：rbx=k32 基址，r9=名称表，
    r10=序号表，r11=函数地址表，rcx=倒计数，rax/rdx/rdi/rsi 临时。
    """
    em.emit(b"\x65\x48\x8B\x04\x25\x60\x00\x00\x00")   # mov rax, gs:[0x60] PEB
    em.emit(b"\x48\x8B\x40\x18")                        # mov rax,[rax+0x18] Ldr
    em.emit(b"\x48\x8D\x50\x20")                        # lea rdx,[rax+0x20] 链表头
    em.label_here("rs_mod")
    em.emit(b"\x48\x8B\x12")                            # mov rdx,[rdx]（→条目+0x10）
    em.emit(b"\x48\x8D\x48\x20")                        # lea rcx,[rax+0x20] 表头
    em.emit(b"\x48\x39\xCA")                            # cmp rdx,rcx
    em.jcc_rel32(0x84, "rs_fail")                       # 回到表头=未找到
    # rdx 指向条目.InMemoryOrderLinks（条目基址+0x10）：
    # DllBase = 条目+0x30 = rdx+0x20；BaseDllName.Length = rdx+0x48；Buffer = rdx+0x50
    em.emit(b"\x66\x81\x7A\x48\x18\x00")                # cmp word[rdx+0x48],24
    em.jcc_rel32(0x85, "rs_mod")
    em.emit(b"\x48\x8B\x7A\x50")                        # mov rdi,[rdx+0x50] 名称缓冲
    for i, dw in enumerate([0x0045004B, 0x004E0052, 0x004C0045,
                            0x00320033, 0x0044002E, 0x004C004C]):
        em.emit(b"\x81\x3F" + struct.pack("<I", dw))    # cmp dword[rdi],"KE"..
        em.jcc_rel32(0x85, "rs_mod")
        if i < 5:
            em.emit(b"\x48\x83\xC7\x04")                # add rdi,4
    em.emit(b"\x48\x8B\x5A\x20")                        # mov rbx,[rdx+0x20] DllBase

    # 定位导出表（r8=导出目录 VA）
    em.emit(b"\x8B\x43\x3C")                            # mov eax,[rbx+0x3C]
    em.emit(b"\x48\x8D\x04\x03")                        # lea rax,[rbx+rax] NT头
    em.emit(b"\x8B\x80\x88\x00\x00\x00")                # mov eax,[rax+0x88] 导出目录RVA
    em.emit(b"\x4C\x8D\x04\x03")                        # lea r8,[rbx+rax]
    em.emit(b"\x45\x8B\x48\x20")                        # mov r9d,[r8+0x20] 名称表RVA
    em.emit(b"\x45\x8B\x50\x24")                        # mov r10d,[r8+0x24] 序号表RVA
    em.emit(b"\x45\x8B\x58\x1C")                        # mov r11d,[r8+0x1C] 函数表RVA
    em.emit(b"\x41\x8B\x48\x18")                        # mov ecx,[r8+0x18] 名称数
    em.emit(b"\x49\x01\xD9")                            # add r9,rbx
    em.emit(b"\x49\x01\xDA")                            # add r10,rbx
    em.emit(b"\x49\x01\xDB")                            # add r11,rbx

    def resolve_common(slot: str):
        """当前 rcx=名称下标：取序号 → 取函数地址 → 存 api 槽。"""
        em.emit(b"\x41\x0F\xB7\x04\x4A")                # movzx eax,word[r10+rcx*2]
        em.emit(b"\x41\x8B\x04\x83")                    # mov eax,[r11+rax*4]
        em.emit(b"\x48\x8D\x04\x03")                    # lea rax,[rbx+rax]
        em.emit(b"\x48\x89\x05")                        # mov [rip+slot],rax
        em.rel32_to(slot)

    em.label_here("rs_exp")
    em.emit(b"\xFF\xC9")                                # dec ecx
    em.emit(b"\x41\x8B\x14\x89")                        # mov edx,[r9+rcx*4] 名称RVA(32位)
    em.emit(b"\x48\x8D\x14\x13")                        # lea rdx,[rbx+rdx]
    em.emit(b"\x8B\x02")                                # mov eax,[rdx]
    em.emit(b"\x3D" + struct.pack("<I", 0x53746547))    # cmp eax,"GetS"
    em.jcc_rel32(0x85, "rs_writ")
    em.emit(b"\x48\x8B\x7A\x04")                        # mov rdi,[rdx+4]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x656C646E61486474))  # "tdHandle"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0C\x00")                        # cmp byte[rdx+12],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_GetStdHandle")
    em.jcc_rel32(None, "rs_next")

    em.label_here("rs_writ")
    em.emit(b"\x3D" + struct.pack("<I", 0x74697257))    # cmp eax,"Writ"
    em.jcc_rel32(0x85, "rs_exit")
    em.emit(b"\x48\x8B\x3A")                            # mov rdi,[rdx]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x6C69466574697257))  # "WriteFil"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x08\x65")                        # cmp byte[rdx+8],'e'
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x09\x00")                        # cmp byte[rdx+9],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_WriteFile")
    em.jcc_rel32(None, "rs_next")

    em.label_here("rs_exit")
    em.emit(b"\x3D" + struct.pack("<I", 0x74697845))    # cmp eax,"Exit"
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x48\x8B\x3A")                            # mov rdi,[rdx]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x636F725074697845))  # "ExitProc"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x81\x7A\x08" + struct.pack("<I", 0x00737365))  # cmp dword[rdx+8],"ess\0"
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_ExitProcess")

    em.label_here("rs_next")
    em.emit(b"\x85\xC9")                                # test ecx,ecx
    em.jcc_rel32(0x85, "rs_exp")
    em.jcc_rel32(None, "rs_done")                       # 遍历结束 → 主代码
    em.label_here("rs_fail")
    em.emit(b"\x0F\x0B")                                # ud2（未找到 kernel32）
    em.label_here("rs_done")


def _emit_print_int(em: _Emitter):
    """print_int：弹栈一个 int，十进制+CRLF 写入 stdout。"""
    em.label_here("print_int")
    em.read_top_to(0)                               # mov rax,[r12]
    em.discard()
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x45\x31\xD2")                        # xor r10d,r10d（符号标志）
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "pi_nonneg")                 # jns nonneg
    em.emit(b"\x41\xBA\x01\x00\x00\x00")            # mov r10d,1
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("pi_nonneg")
    em.lea_rip(6, "numbuf")                         # lea rsi,[numbuf]
    em.emit(b"\x48\x8D\x7E\x3E")                    # lea rdi,[rsi+62]
    em.label_here("pi_loop")
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\xB9\x0A\x00\x00\x00")                # mov ecx,10
    em.emit(b"\x48\xF7\xF1")                        # div rcx
    em.emit(b"\x80\xC2\x30")                        # add dl,'0'
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\x88\x17")                            # mov [rdi],dl
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "pi_loop")                   # jnz loop
    em.emit(b"\x45\x85\xD2")                        # test r10d,r10d
    em.jcc_rel32(0x84, "pi_nosign")                 # jz nosign
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\xC6\x07\x2D")                        # mov byte[rdi],'-'
    em.label_here("pi_nosign")
    em.emit(b"\xB9\xF5\xFF\xFF\xFF")                # mov ecx,-11 (STD_OUTPUT_HANDLE)
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax（句柄）
    em.emit(b"\x48\x89\xFA")                        # mov rdx,rdi（缓冲）
    em.emit(b"\x4C\x8D\x46\x3E")                    # lea r8,[rsi+62]
    em.emit(b"\x41\x29\xF8")                        # sub r8,rdi（长度）
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    _emit_epilogue(em)


def _emit_one(em: _Emitter, ins: tuple, consts: list, fn_names: set[str],
              tag: str, nlocals: int, idx: int = 0):
    op = ins[0]
    if op == OP.PUSH_CONST:
        v = consts[ins[1]]
        if isinstance(v, bool):
            em.emit(b"\xB8" + struct.pack("<I", 1 if v else 0))
            em.push_rax()
        elif isinstance(v, int):
            em.mov_rax_imm64(v)
            em.push_rax()
        else:
            raise NativeNotSupported(
                f"原生后端暂不支持常量 {type(v).__name__}: {v!r}（仅 int/bool）")
    elif op == OP.PUSH_TRUE:
        em.emit(b"\xB8\x01\x00\x00\x00")
        em.push_rax()
    elif op in (OP.PUSH_FALSE, OP.PUSH_NULL):
        em.emit(b"\x31\xC0")                         # xor eax,eax
        em.push_rax()
    elif op == OP.LOAD_LOCAL:
        em.load_local(ins[1], nlocals)
    elif op == OP.STORE_LOCAL:
        em.store_local(ins[1], nlocals)
    elif op == OP.LOAD_GLOBAL:
        name = consts[ins[1]]
        if name in fn_names:
            em.lea_rip(0, f"fn:{name}")             # 函数代码地址
            em.push_rax()
        else:
            em.load_global(f"cell:{name}")
    elif op == OP.STORE_GLOBAL:
        em.store_global(f"cell:{consts[ins[1]]}")
    elif op == OP.CALL:
        _emit_call_apply(em, f"pcur:{tag}:{idx}", 1)
    elif op == OP.RET:
        _emit_epilogue(em)
    elif op == OP.JMP:
        em.jcc_rel32(None, f"{tag}:{ins[1]}")
    elif op == OP.JZ:
        em.pop_to(0)
        em.emit(b"\x48\x85\xC0")                    # test rax,rax
        em.jcc_rel32(0x84, f"{tag}:{ins[1]}")      # jz
    elif op == OP.JNZ:
        em.pop_to(0)
        em.emit(b"\x48\x85\xC0")
        em.jcc_rel32(0x85, f"{tag}:{ins[1]}")      # jnz
    elif op == OP.BINOP:
        sym = consts[ins[1]]
        em.pop_to(1)                                # rcx = 右
        em.pop_to(0)                                # rax = 左
        if sym == "+":
            em.emit(b"\x48\x01\xC8")                # add rax,rcx
        elif sym == "-":
            em.emit(b"\x48\x29\xC8")                # sub rax,rcx
        elif sym == "*":
            em.emit(b"\x48\x0F\xAF\xC1")            # imul rax,rcx
        elif sym == "//":
            em.emit(b"\x48\x99")                    # cqo
            em.emit(b"\x48\xF7\xF9")                # idiv rcx
        elif sym == "%":
            em.emit(b"\x48\x99")
            em.emit(b"\x48\xF7\xF9")
            em.emit(b"\x48\x89\xD0")                # mov rax,rdx
        elif sym in _CC:
            em.emit(b"\x48\x39\xC8")                # cmp rax,rcx
            em.emit(bytes([0x0F, _CC[sym], 0xC0])) # setCC al
            em.emit(b"\x0F\xB6\xC0")                # movzx eax,al
        else:
            raise NativeNotSupported(f"原生后端暂不支持二元运算 {sym!r}")
        em.push_rax()
    elif op == OP.UNARYOP:
        sym = consts[ins[1]]
        if sym == "neg":
            em.emit(b"\x49\xF7\x5C\x24\xF8")        # neg qword [r12-8]（栈顶）
        elif sym == "not":
            em.pop_to(0)
            em.emit(b"\x48\x85\xC0")
            em.emit(b"\x0F\x94\xC0")                # sete al
            em.emit(b"\x0F\xB6\xC0")
            em.push_rax()
        else:
            raise NativeNotSupported(f"原生后端暂不支持一元运算 {sym!r}")
    elif op == OP.DUP:
        em.read_top_to(0)
        em.push_rax()
    elif op == OP.POP:
        em.discard()
    elif op == OP.OUTPUT:
        em.call_rel32("print_int")
    elif op == OP.HALT:
        em.emit(b"\x31\xC9")                        # xor ecx,ecx
        em.call_rip_indirect("api_ExitProcess")
        em.emit(b"\x0F\x0B")                        # ud2
    else:
        raise NativeNotSupported(
            f"原生后端暂不支持操作码 0x{op:02X}（{OP.name(op)}）@ {tag}")


def _emit_code(em: _Emitter, code: list, consts: list, fn_names: set[str],
               tag: str, nlocals: int):
    for i, ins in enumerate(code):
        em.label_here(f"{tag}:{i}")
        _emit_one(em, ins, consts, fn_names, tag, nlocals, i)


# ---------------------------------------------------------------- 载荷

def _build_emitters(mod) -> tuple["_Emitter", "_Emitter", dict]:
    """构建代码/数据发射器（未 patch），供 _build_payload 与调试工具复用。"""
    labels: dict[str, int] = {}
    ec = _Emitter(TEXT_RVA, labels)    # 代码节
    ed = _Emitter(DATA_RVA, labels)    # 数据节
    fn_names = set(mod.functions.keys())

    for name, fn in mod.functions.items():
        if fn.arity > MAX_NATIVE_ARITY:
            raise NativeNotSupported(
                f"原生后端函数参数上限 {MAX_NATIVE_ARITY}：{name} 有 {fn.arity} 个参数")
        if fn.arity > 1:
            raise NativeNotSupported(
                f"原生后端暂不支持多参数函数柯里化：{name} 有 {fn.arity} 个参数")

    # ---- 代码：_start（模块初始化）----
    ec.label_here("_start")
    ec.lea_rip(12, "vstack")                        # lea r12,[vstack]
    # 入口 RSP=16n+8；sub rsp,0x28 使 CALL 时 RSP 16 字节对齐并留影子空间
    ec.emit(b"\x48\x83\xEC\x28")
    _emit_resolve_apis(ec)                          # PEB 遍历解析 kernel32 API
    ec.label_here("main_entry")
    _emit_code(ec, mod.main_code, mod.constants, fn_names, "main", 0)

    # ---- 代码：各用户函数 ----
    for name, fn in mod.functions.items():
        ec.label_here(f"fn:{name}")
        _emit_prologue(ec, fn.arity, fn.nlocals)
        _emit_code(ec, fn.code, mod.constants, fn_names, f"fn:{name}",
                   fn.nlocals)
        ec.emit(b"\x0F\x0B")                        # 保险（RET 后不可达）

    # ---- 代码：print_int ----
    _emit_print_int(ec)

    # ---- 数据：运行时解析出的 API 地址槽（PEB 引导填充）----
    ed.align(8)
    for fn in _APIS:
        ed.label_here(f"api_{fn}")
        ed.emit(b"\x00" * 8)

    # ---- 数据：全局变量单元 ----
    cell_names = set()
    all_code = [("main", mod.main_code)] + \
        [(f"fn:{n}", f.code) for n, f in mod.functions.items()]
    for _tag, code in all_code:
        for ins in code:
            if ins[0] in (OP.LOAD_GLOBAL, OP.STORE_GLOBAL):
                nm = mod.constants[ins[1]]
                if nm not in fn_names:
                    cell_names.add(nm)
    ed.align(8)
    for nm in sorted(cell_names):
        ed.label_here(f"cell:{nm}")
        ed.emit(b"\x00" * 8)

    # ---- 数据：操作数栈 / 输出缓冲 / 写字数 ----
    ed.align(16)
    ed.label_here("vstack")
    ed.emit(b"\x00" * VSTACK_SIZE)
    ed.label_here("numbuf")
    ed.emit(b"\x00" * NUMBUF_SIZE)
    ed.label_here("written")
    ed.emit(b"\x00" * 8)
    return ec, ed, labels


def label_rvas(mod) -> dict[str, int]:
    """返回各静态标签 RVA（调试/测试锚点用）。"""
    _ec, _ed, labels = _build_emitters(mod)
    return dict(labels)


def _build_payload(mod) -> tuple[bytes, bytes]:
    """发射代码节与数据节，返回 (text_bytes, data_bytes)。"""
    ec, ed, _labels = _build_emitters(mod)
    ec.patch()
    ed.patch()
    return bytes(ec.buf), bytes(ed.buf)


# ---------------------------------------------------------------- PE64 链接

def _build_pe(text: bytes, data: bytes) -> bytes:
    def align(v: int, n: int) -> int:
        return (v + n - 1) & ~(n - 1)

    # 节表（RVA 顺序）：name, rva, 内容, chars
    secs = [
        (b".text\x00\x00\x00", TEXT_RVA, text, 0x60000020),   # CODE|EXEC|READ
        (b".data\x00\x00\x00", DATA_RVA, data, 0xC0000040),   # INIT_DATA|READ|WRITE
    ]

    data_va_end = DATA_RVA + align(len(data), 0x1000)
    size_of_image = data_va_end

    hdr = bytearray(HEADERS_SIZE)
    hdr[0:2] = b"MZ"
    struct.pack_into("<I", hdr, 0x3C, 0x80)         # e_lfanew
    hdr[0x80:0x84] = b"PE\x00\x00"
    # COFF 头 @0x84
    hdr[0x84:0x98] = struct.pack(
        "<HHIIIHH",
        0x8664,                                     # Machine: AMD64
        len(secs),                                  # NumberOfSections
        0, 0, 0,
        0xF0,                                       # SizeOfOptionalHeader
        0x0226)                                     # EXEC|LARGE_ADDR|LINE_NUMS|DEBUG_STRIPPED
    # 可选头 PE32+ @0x98（无导入表/无异常目录：API 由 PEB 引导自解析）
    opt = bytearray(0xF0)
    struct.pack_into("<H", opt, 0, 0x020B)          # Magic
    opt[2] = 14                                     # Linker 版本
    struct.pack_into("<I", opt, 4, align(len(text), 0x200))   # SizeOfCode
    struct.pack_into("<I", opt, 8, align(len(data), 0x200))   # SizeOfInitializedData
    struct.pack_into("<I", opt, 16, TEXT_RVA)       # AddressOfEntryPoint
    struct.pack_into("<I", opt, 20, TEXT_RVA)       # BaseOfCode
    struct.pack_into("<Q", opt, 24, IMAGE_BASE)
    struct.pack_into("<I", opt, 32, 0x1000)         # SectionAlignment
    struct.pack_into("<I", opt, 36, 0x200)          # FileAlignment
    struct.pack_into("<H", opt, 40, 6)              # MajorOSVersion
    struct.pack_into("<H", opt, 48, 6)              # MajorSubsystemVersion
    struct.pack_into("<I", opt, 52, 0)              # Win32VersionValue
    struct.pack_into("<I", opt, 56, size_of_image)
    struct.pack_into("<I", opt, 60, HEADERS_SIZE)
    struct.pack_into("<I", opt, 64, 0)              # CheckSum
    struct.pack_into("<H", opt, 68, 3)              # Subsystem: WINDOWS_CUI
    struct.pack_into("<H", opt, 70, 0x0160)         # DYNAMIC_BASE|HIGH_ENTROPY|NX_COMPAT
    struct.pack_into("<Q", opt, 72, 0x100000)       # StackReserve
    struct.pack_into("<Q", opt, 80, 0x1000)         # StackCommit
    struct.pack_into("<Q", opt, 88, 0x100000)       # HeapReserve
    struct.pack_into("<Q", opt, 96, 0x1000)         # HeapCommit
    struct.pack_into("<I", opt, 104, 0)             # LoaderFlags
    struct.pack_into("<I", opt, 108, 16)            # NumberOfRvaAndSizes
    hdr[0x98:0x188] = opt
    # 节表 @0x188
    raw_off = HEADERS_SIZE
    parts = [bytes(hdr)]
    for i, (name, rva, content, chars) in enumerate(secs):
        raw_size = align(len(content), 0x200)
        sh = name
        sh += struct.pack("<I", len(content))       # VirtualSize
        sh += struct.pack("<I", rva)                # VirtualAddress
        sh += struct.pack("<I", raw_size)           # SizeOfRawData
        sh += struct.pack("<I", raw_off)            # PointerToRawData
        sh += struct.pack("<IIHH", 0, 0, 0, 0)
        sh += struct.pack("<I", chars)
        hdr[0x188 + i * 40:0x188 + (i + 1) * 40] = sh
        parts.append(content + b"\x00" * (raw_size - len(content)))
        raw_off += raw_size
    parts[0] = bytes(hdr)                           # 回填含节表的 hdr
    return b"".join(parts)


# ---------------------------------------------------------------- 入口

def emit_exe(mod) -> bytes:
    """MModule → PE64 exe 字节串。"""
    text, data = _build_payload(mod)
    return _build_pe(text, data)


def compile_to_exe(source: str) -> bytes:
    from src.mbc.compiler import compile_source
    return emit_exe(compile_source(source))


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="mbc-native",
                                     description="M3V → x86-64 PE64 原生编译器")
    parser.add_argument("source", help=".matha 源文件")
    parser.add_argument("-o", "--output", help="输出 .exe 路径")
    args = parser.parse_args(argv)

    from src.mbc.compiler import compile_source
    src = Path(args.source).read_text(encoding="utf-8")
    exe = emit_exe(compile_source(src))
    out = args.output or str(Path(args.source).with_suffix(".exe"))
    Path(out).write_bytes(exe)
    print(f"原生编译 {args.source} → {out}（{len(exe)} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
