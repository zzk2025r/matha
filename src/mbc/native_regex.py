r"""原生正则引擎（阶段 B-1：运行时 NFA 编译器 + Pike/Thompson 集合模拟 VM）。

背景
====
解释器（src/interp.py）与 M3V VM（src/mbc/vm.py）复用 src/regexlib.py 的纯
Python 回溯引擎；原生后端（src/mbc/native.py）发射独立 PE，无法回调 Python，
故需自带引擎。完整 PCRE 风格原生引擎分多轮构建：

  阶段 A——**字面量模式**（已发布）。
  阶段 B-1（本模块当前范围）——**元字符 + 分组/交替/量词/锚点**：
    运行时在 exe 内完成「UTF-8 解码 → 模式解析为 NFA 字节码 → 集合模拟
    （Thompson/Pike NFA）」。因 匹配/全匹配 仅需「是否存在匹配」，贪婪/惰性/
    占有不影响存在性判定，故无需回溯 VM 与其空循环保护。
    支持：字面量、`.`、转义（\\n \\r \\t \\f \\v \\a \\e \\0 \\xHH \\uHHHH
    \\UXXXXXXXX）、简写类 \\d\\D\\w\\W\\s\\S、字符类 [...]（范围/取反/内嵌简写）、
    量词 * + ?（仅贪婪；惰性/占有后缀 → 明确错误）、分组 (...) 与 (?:…)、
    交替 |、锚点 ^ $ \\A \\Z \\z \\b \\B。
    暂不支持（遇到即抛「模式解析失败」）：{m,n}、惰性/占有量词、环视、反向
    引用、命名组、内联标志 —— 阶段 B-2 / C 补齐。
  阶段 C——环视 / 反向引用 / 命名组 / 内联标志 / 全部内建。

原生字符串布局：`[TYPE_STR][+8]=字节长][+16..]=UTF-8 字节`。
本阶段把 pattern 与 subject 都解码为**码点（u64）数组**再匹配；字符类/边界
的字母数字判定在非 ASCII 上采用 ASCII 语义（\d\w\s\b），与解释器在 ASCII
输入下一致（Unicode 全等价留待后续）。
"""
from __future__ import annotations

import struct

TYPE_STR = 1

# 由 native.py 在定义 _emit_prologue/_emit_epilogue 之后注入（避免循环导入）。
_EMIT_PROLOGUE = None
_EMIT_EPILOGUE = None


def configure(prologue, epilogue):
    """注入 native.py 的 _emit_prologue/_emit_epilogue（见 native.py 尾部调用）。"""
    global _EMIT_PROLOGUE, _EMIT_EPILOGUE
    _EMIT_PROLOGUE = prologue
    _EMIT_EPILOGUE = epilogue


# ------------------------------------------------------------ 容量与指令集
PAT_CP_MAX = 8192      # 模式码点上限（u64 元素）
SUBJ_CP_MAX = 1 << 18  # 主题码点上限
PROG_MAX = 4096        # NFA 指令数上限
CLASS_MAX = 16384      # 字符类表元素上限（u64）

# 指令：prog[pc*2]=op, prog[pc*2+1]=arg（u64）
OP_MATCH = 0
OP_CHAR = 1     # arg=码点
OP_ANY = 2
OP_CLASS = 3    # arg=类索引
OP_JMP = 4      # arg=目标
OP_SPLIT = 5    # arg=t1 | (t2<<32)
OP_BOL = 6      # arg=目标（epsilon 断言）
OP_EOL = 7
OP_BOS = 8
OP_EOS = 9
OP_WORDB = 10
OP_NWORDB = 11

ERR_NOTSTR = "原生正则：需要字符串参数"
ERR_BADPAT = "原生正则：模式解析失败或不支持该构造（原生引擎阶段 B）"


# ------------------------------------------------------------ 底层字节助手
def _or_rr(em, dst, src):
    """or dst, src（64 位）。"""
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    em.emit(bytes([rex, 0x09, 0xC0 | ((src & 7) << 3) | (dst & 7)]))


def _mov_ecx_esi(em):
    em.emit(b"\x89\xF1")                            # mov ecx,esi（零扩展）


def _mov_edx_ecx(em):
    em.emit(b"\x89\xCA")                            # mov edx,ecx（零扩展）


def _xor_eax_1(em):
    em.emit(b"\x83\xF0\x01")                        # xor eax,1


def _ud2(em):
    em.emit(b"\x0F\x0B")


# ---------------------------------------------------------------- 寄存器保存
def _save(em):
    """压入 6 个字（48 字节）保持 16 字节栈对齐（raise_rt 依赖）。"""
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12;r13;r14;r15
    em.emit(b"\x55")                                # push rbp（占位凑偶）


def _restore(em):
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15;r14;r13;r12
    em.emit(b"\x5B")                                # pop rbx


# ---------------------------------------------------------------- 发射助手
def _emit_inst(em):
    """把 rax=arg、rcx=op 写入 prog[re_pc]，re_pc++。"""
    em.load_rip_to(9, "re_pc")                      # r9=pc
    em.mov_rr(10, 9)
    em.add_rr(10, 9)                                # r10=pc*2
    em.lea_rip(11, "re_prog")
    em.mov_mem_r_idx(11, 1, 0, 10, 8)               # prog[pc*2]=rcx
    em.mov_mem_r_idx(11, 0, 8, 10, 8)               # prog[pc*2+1]=rax
    em.inc_r(9)
    em.store_rip_from("re_pc", 9)


def _emit_inst_imm(em, op, arg):
    em.mov_r_imm32(1, op)
    em.mov_rax_imm64(arg & 0xFFFFFFFFFFFFFFFF)
    _emit_inst(em)


def _emit_inst_reg(em, op, arg_reg):
    em.mov_r_imm32(1, op)
    em.mov_rr(0, arg_reg)
    _emit_inst(em)


def _emit_single(em, op):
    """发射一条 arg=pc+1 的指令（断言/单目标 epsilon）。"""
    em.load_rip_to(0, "re_pc")
    em.inc_r(0)
    _emit_inst_reg(em, op, 0)


def _emit_ph(em, op):
    """发射 op 的占位指令（arg=0），返回其索引于 rax。"""
    em.load_rip_to(0, "re_pc")
    em.emit(b"\x50")                                # push rax（原生栈）
    em.mov_r_imm32(1, op)
    em.xor_rr32(0, 0)
    _emit_inst(em)
    em.emit(b"\x58")                                # pop rax
    # rax=idx


def _patch1(em, idx_off, arg_off):
    em.mov_rd_mem(8, 5, idx_off)
    em.mov_rd_mem(9, 5, arg_off)
    em.mov_rr(10, 8)
    em.add_rr(10, 8)
    em.lea_rip(11, "re_prog")
    em.mov_mem_r_idx(11, 9, 8, 10, 8)


def _patch_split(em, idx_off, t1_off, t2_off):
    em.mov_rd_mem(8, 5, idx_off)
    em.mov_rd_mem(9, 5, t1_off)
    em.mov_rd_mem(10, 5, t2_off)
    em.shl_ri(10, 32)
    _or_rr(em, 10, 9)
    em.mov_rr(6, 8)
    em.add_rr(6, 8)                                 # rsi=idx*2
    em.lea_rip(7, "re_prog")
    em.mov_mem_r_idx(7, 10, 8, 6, 8)


def _badpat(em):
    em.lea_rip(0, "re_err_badpat")
    em.call_rel32("raise_rt")
    _ud2(em)


# ============================================================ 运行时：字符串
def _emit_re_check_str(em):
    """re_check_str(rdi=obj) → rax=payload, rdx=字节长；非 STR 抛错（不返回）。"""
    em.label_here("re_check_str")
    em.mov_rr(1, 7)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_heap_used(1)
    em.jcc_rel32(0x82, "rcs_ok")
    em.jcc_rel32(None, "rcs_bad")
    em.label_here("rcs_ok")
    em.mov_rd_mem(1, 7, 0)
    em.cmp_ri(1, 1)                                 # TYPE_STR
    em.jcc_rel32(0x85, "rcs_bad")
    em.mov_rd_mem(2, 7, 8)
    em.mov_rr(0, 7)
    em.add_ri(0, 16)
    em.emit(b"\xC3")
    em.label_here("rcs_bad")
    em.lea_rip(0, "re_err_notstr_msg")
    em.call_rel32("raise_rt")
    _ud2(em)


# ============================================================ 运行时：UTF-8
def _emit_re_utf8_decode(em):
    """re_utf8_decode(rdi=src, rsi=len, rdx=dst) → rax=码点数（上限 PAT/SUBJ 由调用方保证）。"""
    em.label_here("re_utf8_decode")
    em.emit(b"\x53")                                # push rbx（用 rbx 作 b3）
    em.xor_rr32(0, 0)
    em.xor_rr32(1, 1)
    em.label_here("u_loop")
    em.cmp_rr(1, 6)
    em.jcc_rel32(0x83, "u_done")
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.movzx_r_m8(8, 9, 0)                          # r8=b0
    em.inc_r(1)
    em.cmp_ri(8, 0x80)
    em.jcc_rel32(0x82, "u_emit1")
    em.cmp_ri(8, 0xC0)
    em.jcc_rel32(0x82, "u_bad")
    em.cmp_ri(8, 0xE0)
    em.jcc_rel32(0x82, "u_two")
    em.cmp_ri(8, 0xF0)
    em.jcc_rel32(0x82, "u_three")
    em.jcc_rel32(None, "u_four")

    em.label_here("u_emit1")
    em.mov_mem_r_idx(2, 8, 0, 0, 8)
    em.inc_r(0)
    em.jcc_rel32(None, "u_loop")

    em.label_here("u_bad")
    em.mov_r_imm32(10, 0xFFFD)
    em.mov_mem_r_idx(2, 10, 0, 0, 8)
    em.inc_r(0)
    em.jcc_rel32(None, "u_loop")

    em.label_here("u_two")
    em.cmp_rr(1, 6)
    em.jcc_rel32(0x83, "u_bad")
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.movzx_r_m8(10, 9, 0)                         # b1
    em.inc_r(1)
    em.and_ri(8, 0x1F)
    em.shl_ri(8, 6)
    em.and_ri(10, 0x3F)
    _or_rr(em, 8, 10)
    em.mov_mem_r_idx(2, 8, 0, 0, 8)
    em.inc_r(0)
    em.jcc_rel32(None, "u_loop")

    em.label_here("u_three")
    em.mov_rr(9, 1)
    em.add_ri(9, 1)
    em.cmp_rr(9, 6)
    em.jcc_rel32(0x83, "u_bad")
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.movzx_r_m8(10, 9, 0)                         # b1
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.add_ri(9, 1)
    em.movzx_r_m8(11, 9, 0)                         # b2
    em.add_ri(1, 2)
    em.and_ri(8, 0x0F)
    em.shl_ri(8, 12)
    em.and_ri(10, 0x3F)
    em.shl_ri(10, 6)
    em.and_ri(11, 0x3F)
    _or_rr(em, 8, 10)
    _or_rr(em, 8, 11)
    em.mov_mem_r_idx(2, 8, 0, 0, 8)
    em.inc_r(0)
    em.jcc_rel32(None, "u_loop")

    em.label_here("u_four")
    em.mov_rr(9, 1)
    em.add_ri(9, 2)
    em.cmp_rr(9, 6)
    em.jcc_rel32(0x83, "u_bad")
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.movzx_r_m8(10, 9, 0)                         # b1
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.add_ri(9, 1)
    em.movzx_r_m8(11, 9, 0)                         # b2
    em.mov_rr(9, 7)
    em.add_rr(9, 1)
    em.add_ri(9, 2)
    em.movzx_r_m8(3, 9, 0)                          # b3
    em.add_ri(1, 3)
    em.and_ri(8, 0x07)
    em.shl_ri(8, 18)
    em.and_ri(10, 0x3F)
    em.shl_ri(10, 12)
    em.and_ri(11, 0x3F)
    em.shl_ri(11, 6)
    em.and_ri(3, 0x3F)
    _or_rr(em, 8, 10)
    _or_rr(em, 8, 11)
    _or_rr(em, 8, 3)
    em.mov_mem_r_idx(2, 8, 0, 0, 8)
    em.inc_r(0)
    em.jcc_rel32(None, "u_loop")

    em.label_here("u_done")
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")


# ============================================================ 运行时：字符判定
def _emit_re_is_word(em):
    """re_is_word(rdi=cp) → eax=1/0（ASCII：[0-9A-Za-z_]）。"""
    em.label_here("re_is_word")
    em.xor_rr32(0, 0)
    em.cmp_ri(7, 48)
    em.jcc_rel32(0x82, "iw_ret")
    em.cmp_ri(7, 57)
    em.jcc_rel32(0x86, "iw_yes")
    em.cmp_ri(7, 65)
    em.jcc_rel32(0x82, "iw_ret")
    em.cmp_ri(7, 90)
    em.jcc_rel32(0x86, "iw_yes")
    em.cmp_ri(7, 95)
    em.jcc_rel32(0x84, "iw_yes")
    em.cmp_ri(7, 97)
    em.jcc_rel32(0x82, "iw_ret")
    em.cmp_ri(7, 122)
    em.jcc_rel32(0x86, "iw_yes")
    em.label_here("iw_ret")
    em.emit(b"\xC3")
    em.label_here("iw_yes")
    em.mov_r_imm32(0, 1)
    em.emit(b"\xC3")


def _emit_re_is_boundary(em):
    """re_is_boundary(rdi=pos) → eax=1/0。"""
    em.label_here("re_is_boundary")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_mem_r(5, -8, 7)                          # [rbp-8]=pos
    em.xor_rr32(8, 8)                               # left=0
    em.test_rr(7, 7)
    em.jcc_rel32(0x84, "ib_right")
    em.lea_rip(1, "re_subj_cp")
    em.mov_rr(2, 7)
    em.dec_r(2)
    em.mov_rd_mem(7, 1, 0, index=2, scale=8)
    em.call_rel32("re_is_word")
    em.mov_rr(8, 0)
    em.label_here("ib_right")
    em.xor_rr32(9, 9)
    em.mov_rd_mem(7, 5, -8)
    em.load_rip_to(1, "re_slen")
    em.cmp_rr(7, 1)
    em.jcc_rel32(0x83, "ib_after")
    em.lea_rip(1, "re_subj_cp")
    em.mov_rd_mem(7, 1, 0, index=7, scale=8)
    em.call_rel32("re_is_word")
    em.mov_rr(9, 0)
    em.label_here("ib_after")
    em.xor_rr32(0, 0)
    em.mov_rr(0, 8)
    em.xor_rr32(0, 9)
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret


def _emit_re_sh_match(em):
    """re_sh_match(rdi=kind(0=d,1=w,2=s), rsi=cp) → eax。"""
    em.label_here("re_sh_match")
    em.cmp_ri(7, 0)
    em.jcc_rel32(0x84, "sh_d")
    em.cmp_ri(7, 1)
    em.jcc_rel32(0x84, "sh_w")
    em.xor_rr32(0, 0)
    em.cmp_ri(6, 32)
    em.jcc_rel32(0x84, "sh_yes")
    em.cmp_ri(6, 9)
    em.jcc_rel32(0x82, "sh_ret")
    em.cmp_ri(6, 13)
    em.jcc_rel32(0x86, "sh_yes")
    em.label_here("sh_ret")
    em.emit(b"\xC3")
    em.label_here("sh_d")
    em.xor_rr32(0, 0)
    em.cmp_ri(6, 48)
    em.jcc_rel32(0x82, "sh_ret2")
    em.cmp_ri(6, 57)
    em.jcc_rel32(0x86, "sh_yes")
    em.label_here("sh_ret2")
    em.emit(b"\xC3")
    em.label_here("sh_w")
    em.mov_rr(7, 6)
    em.jcc_rel32(None, "re_is_word")
    em.label_here("sh_yes")
    em.mov_r_imm32(0, 1)
    em.emit(b"\xC3")


def _emit_re_class_match(em):
    """re_class_match(rdi=类索引, rsi=cp) → eax。"""
    em.label_here("re_class_match")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x48\x83\xEC\x38")                    # sub rsp,0x38
    em.mov_mem_r(5, -16, 7)                         # [rbp-16]=idx
    em.mov_mem_r(5, -24, 6)                         # [rbp-24]=cp
    em.mov_rr(11, 7)
    em.add_ri(11, 2)                                # r11=idx+2
    em.lea_rip(8, "re_class")
    em.mov_rd_mem(10, 8, 8, index=7, scale=8)       # r10=nitems
    em.mov_rd_mem(9, 8, 0, index=7, scale=8)        # r9=class_neg
    em.xor_rr32(3, 3)                               # j=0
    em.label_here("cm_loop")
    em.cmp_rr(3, 10)
    em.jcc_rel32(0x83, "cm_no")
    em.mov_rr(2, 3)
    em.add_rr(2, 3)
    em.add_rr(2, 11)                                # rdx=e+2j
    em.lea_rip(8, "re_class")
    em.mov_rd_mem(0, 8, 0, index=2, scale=8)        # tag
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "cm_sh")
    em.mov_rd_mem(1, 8, 8, index=2, scale=8)        # pack
    em.mov_rr(0, 1)
    em.shr_ri(0, 32)                                # hi
    _mov_edx_ecx(em)                                # lo
    em.mov_rd_mem(6, 5, -24)                        # cp
    em.cmp_rr(6, 2)
    em.jcc_rel32(0x82, "cm_next")
    em.cmp_rr(6, 0)
    em.jcc_rel32(0x87, "cm_next")
    em.jcc_rel32(None, "cm_match")
    em.label_here("cm_sh")
    em.mov_rd_mem(1, 8, 8, index=2, scale=8)        # payload
    em.mov_rr(0, 1)
    em.and_ri(0, 3)
    em.mov_mem_r(5, -40, 0)                         # kind
    em.mov_rr(0, 1)
    em.shr_ri(0, 2)
    em.and_ri(0, 1)
    em.mov_mem_r(5, -32, 0)                         # shneg
    em.mov_rd_mem(7, 5, -40)
    em.mov_rd_mem(6, 5, -24)
    em.call_rel32("re_sh_match")
    em.mov_rd_mem(1, 5, -32)
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, "cm_sh_t")
    _xor_eax_1(em)
    em.label_here("cm_sh_t")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "cm_match")
    em.label_here("cm_next")
    em.inc_r(3)
    em.jcc_rel32(None, "cm_loop")
    em.label_here("cm_no")
    em.xor_rr32(0, 0)
    em.jcc_rel32(None, "cm_done")
    em.label_here("cm_match")
    em.mov_r_imm32(0, 1)
    em.label_here("cm_done")
    em.test_rr(9, 9)
    em.jcc_rel32(0x84, "cm_ret")
    _xor_eax_1(em)
    em.label_here("cm_ret")
    em.emit(b"\x48\x83\xC4\x38\x5B\x5D\xC3")        # add rsp,0x38; pop rbx; pop rbp; ret


# ============================================================ 编译器：类表
def _emit_re_class_new(em):
    """re_class_new(rdi=class_neg) → rax=类索引。"""
    em.label_here("re_class_new")
    em.load_rip_to(0, "re_class_len")
    em.lea_rip(2, "re_class")
    em.mov_mem_r_idx(2, 7, 0, 0, 8)                 # re_class[idx]=neg
    em.xor_rr32(1, 1)
    em.mov_mem_r_idx(2, 1, 8, 0, 8)                 # re_class[idx+1]=0
    em.mov_rr(1, 0)
    em.add_ri(1, 2)
    em.store_rip_from("re_class_len", 1)
    em.emit(b"\xC3")


def _emit_re_class_add_range(em):
    """re_class_add_range(rdi=idx, rsi=lo, rdx=hi)。"""
    em.label_here("re_class_add_range")
    em.lea_rip(8, "re_class")
    em.mov_rd_mem(9, 8, 8, index=7, scale=8)        # nitems
    em.mov_rr(10, 9)
    em.add_rr(10, 9)                                # 2n
    em.mov_rr(11, 7)
    em.add_ri(11, 2)
    em.add_rr(11, 10)                               # e
    em.shl_ri(2, 32)
    _or_rr(em, 2, 6)                                # payload=hi<<32|lo
    em.xor_rr32(0, 0)
    em.mov_mem_r_idx(8, 0, 0, 11, 8)
    em.mov_mem_r_idx(8, 2, 8, 11, 8)
    em.mov_rr(0, 9)
    em.inc_r(0)
    em.mov_mem_r_idx(8, 0, 8, 7, 8)                 # nitems+1
    em.mov_rr(0, 11)
    em.add_ri(0, 2)
    em.store_rip_from("re_class_len", 0)
    em.emit(b"\xC3")


def _emit_re_class_add_sh(em):
    """re_class_add_sh(rdi=idx, rsi=kind, rdx=neg)。"""
    em.label_here("re_class_add_sh")
    em.lea_rip(8, "re_class")
    em.mov_rd_mem(9, 8, 8, index=7, scale=8)        # nitems
    em.mov_rr(10, 9)
    em.add_rr(10, 9)
    em.mov_rr(11, 7)
    em.add_ri(11, 2)
    em.add_rr(11, 10)                               # e
    em.shl_ri(2, 2)
    _or_rr(em, 2, 6)                                # payload=neg<<2|kind
    em.mov_r_imm32(0, 1)
    em.mov_mem_r_idx(8, 0, 0, 11, 8)                # tag=1
    em.mov_mem_r_idx(8, 2, 8, 11, 8)
    em.mov_rr(0, 9)
    em.inc_r(0)
    em.mov_mem_r_idx(8, 0, 8, 7, 8)
    em.mov_rr(0, 11)
    em.add_ri(0, 2)
    em.store_rip_from("re_class_len", 0)
    em.emit(b"\xC3")


# ============================================================ 编译器：游标
def _emit_re_peek(em):
    """re_peek() → rax=码点或 -1。"""
    em.label_here("re_peek")
    em.load_rip_to(0, "re_pat_i")
    em.load_rip_to(1, "re_plen")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x83, "pk_end")
    em.lea_rip(2, "re_pat_cp")
    em.mov_rd_mem(0, 2, 0, index=0, scale=8)
    em.emit(b"\xC3")
    em.label_here("pk_end")
    em.mov_rax_imm64(-1)
    em.emit(b"\xC3")


def _emit_re_peek2(em):
    """re_peek2() → rax=i+1 处码点或 -1。"""
    em.label_here("re_peek2")
    em.load_rip_to(0, "re_pat_i")
    em.inc_r(0)
    em.load_rip_to(1, "re_plen")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x83, "pk2_end")
    em.lea_rip(2, "re_pat_cp")
    em.mov_rd_mem(0, 2, 0, index=0, scale=8)
    em.emit(b"\xC3")
    em.label_here("pk2_end")
    em.mov_rax_imm64(-1)
    em.emit(b"\xC3")


def _emit_re_next(em):
    em.label_here("re_next")
    em.load_rip_to(0, "re_pat_i")
    em.inc_r(0)
    em.store_rip_from("re_pat_i", 0)
    em.emit(b"\xC3")


def _emit_re_read_hex(em):
    """re_read_hex(rdi=k) → rax=码点（不足或非十六进制抛错）。"""
    em.label_here("re_read_hex")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.mov_rr(11, 7)                                # k
    em.xor_rr32(8, 8)                               # acc
    em.xor_rr32(9, 9)                               # cnt
    em.label_here("rh_loop")
    em.cmp_rr(9, 11)
    em.jcc_rel32(0x83, "rh_done")
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "rh_bad")
    em.cmp_ri(0, 48)
    em.jcc_rel32(0x82, "rh_ua")
    em.cmp_ri(0, 57)
    em.jcc_rel32(0x87, "rh_ua")
    em.add_ri(0, -48)
    em.jcc_rel32(None, "rh_add")
    em.label_here("rh_ua")
    em.cmp_ri(0, 97)
    em.jcc_rel32(0x82, "rh_uu")
    em.cmp_ri(0, 102)
    em.jcc_rel32(0x87, "rh_bad")
    em.add_ri(0, -87)
    em.jcc_rel32(None, "rh_add")
    em.label_here("rh_uu")
    em.cmp_ri(0, 65)
    em.jcc_rel32(0x82, "rh_bad")
    em.cmp_ri(0, 70)
    em.jcc_rel32(0x87, "rh_bad")
    em.add_ri(0, -55)
    em.label_here("rh_add")
    em.shl_ri(8, 4)
    em.add_rr(8, 0)
    em.inc_r(9)
    em.call_rel32("re_next")
    em.jcc_rel32(None, "rh_loop")
    em.label_here("rh_bad")
    _badpat(em)
    em.label_here("rh_done")
    em.test_rr(9, 9)
    em.jcc_rel32(0x84, "rh_bad")
    em.mov_rr(0, 8)
    em.emit(b"\x48\x89\xEC\x5D\xC3")


# ============================================================ 编译器：语法
def _emit_re_p_alt(em):
    em.label_here("re_p_alt")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    _emit_ph(em, OP_SPLIT)
    em.mov_mem_r(5, -8, 0)                          # split idx
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # t1
    em.call_rel32("re_p_seq")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x7C)                              # '|'
    em.jcc_rel32(0x85, "pa_nomatch")
    em.call_rel32("re_next")
    _emit_ph(em, OP_JMP)
    em.mov_mem_r(5, -24, 0)                         # jmp idx
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -32, 0)                         # t2
    _patch_split(em, -8, -16, -32)
    em.call_rel32("re_p_alt")
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)                         # end
    _patch1(em, -24, -40)
    em.jcc_rel32(None, "pa_done")
    em.label_here("pa_nomatch")
    _patch_split(em, -8, -16, -16)                  # 单分支：pre -> SPLIT(body,body) 无条件
    em.label_here("pa_done")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_p_seq(em):
    em.label_here("re_p_seq")
    em.emit(b"\x55\x48\x89\xE5")
    em.label_here("ps_loop")
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "ps_done")
    em.cmp_ri(0, 0x7C)                              # '|'
    em.jcc_rel32(0x84, "ps_done")
    em.cmp_ri(0, 0x29)                              # ')'
    em.jcc_rel32(0x84, "ps_done")
    em.call_rel32("re_p_quant")
    em.jcc_rel32(None, "ps_loop")
    em.label_here("ps_done")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_p_quant(em):
    em.label_here("re_p_quant")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x40")
    _emit_ph(em, OP_SPLIT)
    em.mov_mem_r(5, -8, 0)                          # pre split idx
    em.call_rel32("re_p_atom")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x2A)                              # '*'
    em.jcc_rel32(0x84, "pq_star")
    em.cmp_ri(0, 0x2B)                              # '+'
    em.jcc_rel32(0x84, "pq_plus")
    em.cmp_ri(0, 0x3F)                              # '?'
    em.jcc_rel32(0x84, "pq_opt")
    em.cmp_ri(0, 0x7B)                              # '{'
    em.jcc_rel32(0x84, "pq_brace")
    em.jcc_rel32(None, "pq_none")

    em.label_here("pq_star")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)
    em.jcc_rel32(0x84, "pq_bad")
    em.cmp_ri(0, 0x2B)
    em.jcc_rel32(0x84, "pq_bad")
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # t1=body
    _emit_ph(em, OP_JMP)
    em.mov_mem_r(5, -24, 0)
    _patch1(em, -24, -8)                            # jmp -> pre
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)
    _patch_split(em, -8, -16, -40)
    em.jcc_rel32(None, "pq_done")

    em.label_here("pq_plus")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)
    em.jcc_rel32(0x84, "pq_bad")
    em.cmp_ri(0, 0x2B)
    em.jcc_rel32(0x84, "pq_bad")
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # body
    _patch_split(em, -8, -16, -16)                  # pre -> body
    _emit_ph(em, OP_SPLIT)
    em.mov_mem_r(5, -24, 0)
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)                         # end
    _patch_split(em, -24, -16, -40)
    em.jcc_rel32(None, "pq_done")

    em.label_here("pq_opt")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)
    em.jcc_rel32(0x84, "pq_bad")
    em.cmp_ri(0, 0x2B)
    em.jcc_rel32(0x84, "pq_bad")
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # body
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)                         # end
    _patch_split(em, -8, -16, -40)                  # pre -> SPLIT(body,end) 可选
    em.jcc_rel32(None, "pq_done")

    em.label_here("pq_brace")
    em.call_rel32("re_peek2")
    em.cmp_ri(0, 48)
    em.jcc_rel32(0x82, "pq_none")
    em.cmp_ri(0, 57)
    em.jcc_rel32(0x87, "pq_none")
    em.jcc_rel32(None, "pq_bad")

    em.label_here("pq_none")
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # body
    _patch_split(em, -8, -16, -16)                  # pre -> SPLIT(body,body) 无条件
    em.jcc_rel32(None, "pq_done")

    em.label_here("pq_bad")
    _badpat(em)
    em.label_here("pq_done")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_p_atom(em):
    em.label_here("re_p_atom")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x20")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x28)                              # '('
    em.jcc_rel32(0x84, "paa_group")
    em.cmp_ri(0, 0x5B)                              # '['
    em.jcc_rel32(0x84, "paa_class")
    em.cmp_ri(0, 0x2E)                              # '.'
    em.jcc_rel32(0x84, "paa_any")
    em.cmp_ri(0, 0x5E)                              # '^'
    em.jcc_rel32(0x84, "paa_bol")
    em.cmp_ri(0, 0x24)                              # '$'
    em.jcc_rel32(0x84, "paa_eol")
    em.cmp_ri(0, 0x5C)                              # '\\'
    em.jcc_rel32(0x84, "paa_esc")
    em.cmp_ri(0, 0x2A)
    em.jcc_rel32(0x84, "paa_bad")
    em.cmp_ri(0, 0x2B)
    em.jcc_rel32(0x84, "paa_bad")
    em.cmp_ri(0, 0x3F)
    em.jcc_rel32(0x84, "paa_bad")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "paa_bad")
    em.mov_mem_r(5, -8, 0)
    em.call_rel32("re_next")
    em.mov_rd_mem(0, 5, -8)
    _emit_inst_reg(em, OP_CHAR, 0)
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_any")
    em.call_rel32("re_next")
    _emit_single(em, OP_ANY)
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_bol")
    em.call_rel32("re_next")
    _emit_single(em, OP_BOL)
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_eol")
    em.call_rel32("re_next")
    _emit_single(em, OP_EOL)
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_esc")
    em.call_rel32("re_p_escape_top")
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_group")
    em.call_rel32("re_p_group")
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_class")
    em.call_rel32("re_p_class")
    em.jcc_rel32(None, "paa_done")
    em.label_here("paa_bad")
    _badpat(em)
    em.label_here("paa_done")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_p_group(em):
    em.label_here("re_p_group")
    em.emit(b"\x55\x48\x89\xE5")
    em.call_rel32("re_next")                        # 消耗 '('
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)                              # '?'
    em.jcc_rel32(0x85, "pg_plain")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3A)                              # ':'
    em.jcc_rel32(0x85, "pg_bad")
    em.call_rel32("re_next")
    em.label_here("pg_plain")
    em.call_rel32("re_p_alt")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x29)                              # ')'
    em.jcc_rel32(0x85, "pg_bad")
    em.call_rel32("re_next")
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("pg_bad")
    _badpat(em)


def _emit_re_p_escape_top(em):
    em.label_here("re_p_escape_top")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x30")
    em.call_rel32("re_next")                        # consume '\'
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "et_bad")
    em.cmp_ri(0, 0x64)
    em.jcc_rel32(0x84, "et_shd")
    em.cmp_ri(0, 0x44)
    em.jcc_rel32(0x84, "et_shD")
    em.cmp_ri(0, 0x77)
    em.jcc_rel32(0x84, "et_shw")
    em.cmp_ri(0, 0x57)
    em.jcc_rel32(0x84, "et_shW")
    em.cmp_ri(0, 0x73)
    em.jcc_rel32(0x84, "et_shs")
    em.cmp_ri(0, 0x53)
    em.jcc_rel32(0x84, "et_shS")
    em.cmp_ri(0, 0x62)                              # 'b'
    em.jcc_rel32(0x84, "et_wb")
    em.cmp_ri(0, 0x42)                              # 'B'
    em.jcc_rel32(0x84, "et_nwb")
    em.cmp_ri(0, 0x41)                              # 'A'
    em.jcc_rel32(0x84, "et_bos")
    em.cmp_ri(0, 0x5A)                              # 'Z'
    em.jcc_rel32(0x84, "et_eos")
    em.cmp_ri(0, 0x7A)                              # 'z'
    em.jcc_rel32(0x84, "et_eos")
    em.cmp_ri(0, 0x6E)
    em.jcc_rel32(0x84, "et_n")
    em.cmp_ri(0, 0x72)
    em.jcc_rel32(0x84, "et_r")
    em.cmp_ri(0, 0x74)
    em.jcc_rel32(0x84, "et_t")
    em.cmp_ri(0, 0x66)
    em.jcc_rel32(0x84, "et_f")
    em.cmp_ri(0, 0x76)
    em.jcc_rel32(0x84, "et_v")
    em.cmp_ri(0, 0x61)
    em.jcc_rel32(0x84, "et_a")
    em.cmp_ri(0, 0x65)
    em.jcc_rel32(0x84, "et_e")
    em.cmp_ri(0, 0x30)
    em.jcc_rel32(0x84, "et_zero")
    em.cmp_ri(0, 0x78)                              # 'x'
    em.jcc_rel32(0x84, "et_x")
    em.cmp_ri(0, 0x75)
    em.jcc_rel32(0x84, "et_u")
    em.cmp_ri(0, 0x55)
    em.jcc_rel32(0x84, "et_U")
    em.cmp_ri(0, 0x6B)                              # 'k'
    em.jcc_rel32(0x84, "et_bad")
    em.cmp_ri(0, 0x67)                              # 'g'
    em.jcc_rel32(0x84, "et_bad")
    em.cmp_ri(0, 0x31)                              # '1'
    em.jcc_rel32(0x82, "et_lit")
    em.cmp_ri(0, 0x39)                              # '9'
    em.jcc_rel32(0x86, "et_bad")
    em.jcc_rel32(None, "et_lit")

    for _ch, kind, neg, tag in (("et_shd", 0, 0, "et_shd"),
                               ("et_shD", 0, 1, "et_shD"),
                               ("et_shw", 1, 0, "et_shw"),
                               ("et_shW", 1, 1, "et_shW"),
                               ("et_shs", 2, 0, "et_shs"),
                               ("et_shS", 2, 1, "et_shS")):
        em.label_here(tag)
        em.mov_r_imm32(0, kind)
        em.mov_mem_r(5, -8, 0)
        em.mov_r_imm32(0, neg)
        em.mov_mem_r(5, -16, 0)
        em.jcc_rel32(None, "et_shc")
    em.label_here("et_shc")
    em.call_rel32("re_next")
    em.mov_rd_mem(7, 5, -16)
    em.call_rel32("re_class_new")
    em.mov_mem_r(5, -24, 0)
    em.mov_rd_mem(7, 5, -24)
    em.mov_rd_mem(6, 5, -8)
    em.xor_rr32(2, 2)
    em.call_rel32("re_class_add_sh")
    em.mov_rd_mem(0, 5, -24)
    _emit_inst_reg(em, OP_CLASS, 0)
    em.jcc_rel32(None, "et_done")

    em.label_here("et_wb")
    em.call_rel32("re_next")
    _emit_single(em, OP_WORDB)
    em.jcc_rel32(None, "et_done")
    em.label_here("et_nwb")
    em.call_rel32("re_next")
    _emit_single(em, OP_NWORDB)
    em.jcc_rel32(None, "et_done")
    em.label_here("et_bos")
    em.call_rel32("re_next")
    _emit_single(em, OP_BOS)
    em.jcc_rel32(None, "et_done")
    em.label_here("et_eos")
    em.call_rel32("re_next")
    _emit_single(em, OP_EOS)
    em.jcc_rel32(None, "et_done")

    for tag, cp in (("et_n", 10), ("et_r", 13), ("et_t", 9), ("et_f", 12),
                    ("et_v", 11), ("et_a", 7), ("et_e", 27), ("et_zero", 48)):
        em.label_here(tag)
        em.call_rel32("re_next")
        em.mov_r_imm32(0, cp)
        _emit_inst_reg(em, OP_CHAR, 0)
        em.jcc_rel32(None, "et_done")

    em.label_here("et_x")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 2)
    em.call_rel32("re_read_hex")
    _emit_inst_reg(em, OP_CHAR, 0)
    em.jcc_rel32(None, "et_done")
    em.label_here("et_u")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 4)
    em.call_rel32("re_read_hex")
    _emit_inst_reg(em, OP_CHAR, 0)
    em.jcc_rel32(None, "et_done")
    em.label_here("et_U")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 8)
    em.call_rel32("re_read_hex")
    _emit_inst_reg(em, OP_CHAR, 0)
    em.jcc_rel32(None, "et_done")

    em.label_here("et_lit")
    em.mov_mem_r(5, -8, 0)
    em.call_rel32("re_next")
    em.mov_rd_mem(0, 5, -8)
    _emit_inst_reg(em, OP_CHAR, 0)
    em.jcc_rel32(None, "et_done")

    em.label_here("et_bad")
    _badpat(em)
    em.label_here("et_done")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_p_class_atom(em):
    """re_p_class_atom() → rax=is_sh；char: rsi=cp；sh: rsi=kind, rdx=shneg。"""
    em.label_here("re_p_class_atom")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x10")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x5C)                              # '\\'
    em.jcc_rel32(0x85, "pca_char")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "pca_bad")
    em.cmp_ri(0, 0x64)
    em.jcc_rel32(0x84, "pca_d")
    em.cmp_ri(0, 0x44)
    em.jcc_rel32(0x84, "pca_D")
    em.cmp_ri(0, 0x77)
    em.jcc_rel32(0x84, "pca_w")
    em.cmp_ri(0, 0x57)
    em.jcc_rel32(0x84, "pca_W")
    em.cmp_ri(0, 0x73)
    em.jcc_rel32(0x84, "pca_s")
    em.cmp_ri(0, 0x53)
    em.jcc_rel32(0x84, "pca_S")
    em.cmp_ri(0, 0x6E)
    em.jcc_rel32(0x84, "pca_n")
    em.cmp_ri(0, 0x72)
    em.jcc_rel32(0x84, "pca_r")
    em.cmp_ri(0, 0x74)
    em.jcc_rel32(0x84, "pca_t")
    em.cmp_ri(0, 0x66)
    em.jcc_rel32(0x84, "pca_f")
    em.cmp_ri(0, 0x76)
    em.jcc_rel32(0x84, "pca_v")
    em.cmp_ri(0, 0x61)
    em.jcc_rel32(0x84, "pca_a")
    em.cmp_ri(0, 0x65)
    em.jcc_rel32(0x84, "pca_e")
    em.cmp_ri(0, 0x30)
    em.jcc_rel32(0x84, "pca_0")
    em.cmp_ri(0, 0x62)                              # '\b' in class -> \x08
    em.jcc_rel32(0x84, "pca_bs")
    em.cmp_ri(0, 0x78)
    em.jcc_rel32(0x84, "pca_x")
    em.cmp_ri(0, 0x75)
    em.jcc_rel32(0x84, "pca_u")
    em.cmp_ri(0, 0x55)
    em.jcc_rel32(0x84, "pca_U")
    em.jcc_rel32(None, "pca_lit")

    for tag, kind, neg in (("pca_d", 0, 0), ("pca_D", 0, 1),
                           ("pca_w", 1, 0), ("pca_W", 1, 1),
                           ("pca_s", 2, 0), ("pca_S", 2, 1)):
        em.label_here(tag)
        em.mov_r_imm32(6, kind)
        em.mov_r_imm32(2, neg)
        em.call_rel32("re_next")
        em.mov_r_imm32(0, 1)
        em.emit(b"\x48\x89\xEC\x5D\xC3")

    for tag, cp in (("pca_n", 10), ("pca_r", 13), ("pca_t", 9),
                    ("pca_f", 12), ("pca_v", 11), ("pca_a", 7),
                    ("pca_e", 27), ("pca_0", 0), ("pca_bs", 8)):
        em.label_here(tag)
        em.call_rel32("re_next")
        em.mov_r_imm32(0, cp)
        em.mov_rr(6, 0)
        em.xor_rr32(0, 0)
        em.emit(b"\x48\x89\xEC\x5D\xC3")

    em.label_here("pca_x")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 2)
    em.call_rel32("re_read_hex")
    em.mov_rr(6, 0)
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("pca_u")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 4)
    em.call_rel32("re_read_hex")
    em.mov_rr(6, 0)
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("pca_U")
    em.call_rel32("re_next")
    em.mov_r_imm32(7, 8)
    em.call_rel32("re_read_hex")
    em.mov_rr(6, 0)
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    em.label_here("pca_lit")
    em.mov_mem_r(5, -8, 0)
    em.call_rel32("re_next")
    em.mov_rd_mem(6, 5, -8)
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    em.label_here("pca_char")
    em.mov_rr(6, 0)
    em.call_rel32("re_next")
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    em.label_here("pca_bad")
    _badpat(em)


def _emit_re_p_class(em):
    em.label_here("re_p_class")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x30")
    em.call_rel32("re_next")                        # consume '['
    em.xor_rr32(8, 8)
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x5E)                              # '^'
    em.jcc_rel32(0x85, "pc_nonneg")
    em.call_rel32("re_next")
    em.mov_r_imm32(8, 1)
    em.label_here("pc_nonneg")
    em.mov_mem_r(5, -24, 8)                         # neg
    em.mov_rd_mem(7, 5, -24)
    em.call_rel32("re_class_new")
    em.mov_mem_r(5, -8, 0)                          # idx
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x5D)                              # ']'
    em.jcc_rel32(0x85, "pc_loop")
    em.mov_rd_mem(7, 5, -8)
    em.mov_r_imm32(6, 0x5D)
    em.mov_r_imm32(2, 0x5D)
    em.call_rel32("re_class_add_range")
    em.call_rel32("re_next")
    em.label_here("pc_loop")
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "pc_bad")
    em.cmp_ri(0, 0x5D)                              # ']'
    em.jcc_rel32(0x84, "pc_end")
    em.call_rel32("re_p_class_atom")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "pc_sh")
    em.mov_mem_r(5, -16, 6)                         # save cp
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x2D)                              # '-'
    em.jcc_rel32(0x85, "pc_single")
    em.call_rel32("re_peek2")
    em.cmp_ri(0, 0x5D)
    em.jcc_rel32(0x84, "pc_single")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "pc_single")
    em.call_rel32("re_next")
    em.call_rel32("re_p_class_atom")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "pc_bad")
    em.mov_rd_mem(7, 5, -8)
    em.mov_rr(2, 6)                                 # hi
    em.mov_rd_mem(6, 5, -16)                        # lo
    em.call_rel32("re_class_add_range")
    em.jcc_rel32(None, "pc_loop")
    em.label_here("pc_single")
    em.mov_rd_mem(7, 5, -8)
    em.mov_rd_mem(6, 5, -16)
    em.mov_rr(2, 6)
    em.call_rel32("re_class_add_range")
    em.jcc_rel32(None, "pc_loop")
    em.label_here("pc_sh")
    em.mov_rd_mem(7, 5, -8)
    em.call_rel32("re_class_add_sh")
    em.jcc_rel32(None, "pc_loop")
    em.label_here("pc_loop_done")
    em.jcc_rel32(None, "pc_loop")
    em.label_here("pc_end")
    em.call_rel32("re_next")
    em.mov_rd_mem(0, 5, -8)
    _emit_inst_reg(em, OP_CLASS, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("pc_bad")
    _badpat(em)


# ============================================================ 编译入口
def _emit_re_compile(em):
    em.label_here("re_compile")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x10")
    em.store_rip_from("re_plen", 7)
    em.xor_rr32(0, 0)
    em.store_rip_from("re_pat_i", 0)
    em.store_rip_from("re_pc", 0)
    em.store_rip_from("re_class_len", 0)
    em.call_rel32("re_p_alt")
    em.load_rip_to(0, "re_pat_i")
    em.load_rip_to(1, "re_plen")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x84, "rc_ok")
    _badpat(em)
    em.label_here("rc_ok")
    _emit_inst_imm(em, OP_MATCH, 0)
    em.load_rip_to(0, "re_pc")
    em.store_rip_from("re_prog_len", 0)
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")


# ============================================================ Pike VM
def _emit_re_closure(em):
    """re_closure(rdi=seed, rsi=pos, rdx=gen)；结果追加到 re_clist，re_cn 更新。"""
    em.label_here("re_closure")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x53\x41\x56\x41\x57")                # push rbx; push r14; push r15（r15=栈指针）
    em.emit(b"\x48\x83\xEC\x10")                    # sub rsp,0x10
    em.mov_rr(3, 2)                                 # rbx=gen
    em.mov_rr(14, 6)                                # r14=pos
    em.lea_rip(2, "re_stack")
    em.mov_mem_r(2, 0, 7)                           # stack[0]=seed
    em.mov_r_imm32(15, 1)                           # r15=sp=1
    em.label_here("c_loop")
    em.test_rr(15, 15)
    em.jcc_rel32(0x84, "c_done")
    em.lea_rip(2, "re_stack")
    em.mov_rd_mem(6, 2, -8, index=15, scale=8)      # rsi=stack[sp-1]
    em.dec_r(15)
    em.lea_rip(1, "re_visited")
    em.mov_rd_mem(7, 1, 0, index=6, scale=8)        # visited[s]
    em.cmp_rr(7, 3)
    em.jcc_rel32(0x84, "c_loop")
    em.mov_mem_r_idx(1, 3, 0, 6, 8)                 # visited[s]=gen
    em.mov_rr(9, 6)
    em.add_rr(9, 6)                                 # s*2
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(10, 8, 0, index=9, scale=8)       # op
    em.cmp_ri(10, OP_JMP)
    em.jcc_rel32(0x84, "c_jmp")
    em.cmp_ri(10, OP_SPLIT)
    em.jcc_rel32(0x84, "c_split")
    em.cmp_ri(10, OP_BOL)
    em.jcc_rel32(0x84, "c_bol")
    em.cmp_ri(10, OP_EOL)
    em.jcc_rel32(0x84, "c_eol")
    em.cmp_ri(10, OP_BOS)
    em.jcc_rel32(0x84, "c_bos")
    em.cmp_ri(10, OP_EOS)
    em.jcc_rel32(0x84, "c_eos")
    em.cmp_ri(10, OP_WORDB)
    em.jcc_rel32(0x84, "c_wb")
    em.cmp_ri(10, OP_NWORDB)
    em.jcc_rel32(0x84, "c_nwb")
    em.load_rip_to(11, "re_cn")
    em.lea_rip(2, "re_clist")
    em.mov_mem_r_idx(2, 6, 0, 11, 8)                # clist[cn]=s
    em.inc_r(11)
    em.store_rip_from("re_cn", 11)
    em.jcc_rel32(None, "c_loop")
    em.label_here("c_jmp")
    em.mov_rd_mem(6, 8, 8, index=9, scale=8)        # 目标
    em.jcc_rel32(None, "c_pusharg")
    em.label_here("c_split")
    em.mov_rd_mem(6, 8, 8, index=9, scale=8)        # packed
    em.mov_rr(7, 6)
    em.shr_ri(7, 32)                                # t2
    _mov_ecx_esi(em)                                # t1
    em.lea_rip(2, "re_stack")
    em.mov_mem_r_idx(2, 1, 0, 15, 8)
    em.inc_r(15)
    em.mov_mem_r_idx(2, 7, 0, 15, 8)
    em.inc_r(15)
    em.jcc_rel32(None, "c_loop")

    em.label_here("c_bol")
    em.test_rr(14, 14)
    em.jcc_rel32(0x85, "c_loop")
    em.jcc_rel32(None, "c_target")
    em.label_here("c_bos")
    em.test_rr(14, 14)
    em.jcc_rel32(0x85, "c_loop")
    em.jcc_rel32(None, "c_target")
    em.label_here("c_eol")
    em.load_rip_to(10, "re_slen")
    em.cmp_rr(14, 10)
    em.jcc_rel32(0x85, "c_loop")
    em.jcc_rel32(None, "c_target")
    em.label_here("c_eos")
    em.load_rip_to(10, "re_slen")
    em.cmp_rr(14, 10)
    em.jcc_rel32(0x85, "c_loop")
    em.jcc_rel32(None, "c_target")
    em.label_here("c_wb")
    em.mov_rr(7, 14)
    em.call_rel32("re_is_boundary")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "c_loop")
    em.jcc_rel32(None, "c_target")
    em.label_here("c_nwb")
    em.mov_rr(7, 14)
    em.call_rel32("re_is_boundary")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "c_loop")
    em.jcc_rel32(None, "c_target")

    em.label_here("c_target")
    # 断言通过：把后继（arg）压栈。r8/r9 可能被 re_is_boundary 破坏，故重算。
    em.mov_rr(9, 6)
    em.add_rr(9, 6)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(6, 8, 8, index=9, scale=8)        # arg
    em.label_here("c_pusharg")
    em.lea_rip(2, "re_stack")
    em.mov_mem_r_idx(2, 6, 0, 15, 8)
    em.inc_r(15)
    em.jcc_rel32(None, "c_loop")

    em.label_here("c_done")
    em.xor_rr32(0, 0)
    em.emit(b"\x48\x83\xC4\x10\x41\x5F\x41\x5E\x5B\x5D\xC3")  # add rsp,0x10; pop r15; pop r14; pop rbx; pop rbp; ret


def _emit_re_exec(em):
    """re_exec(edi=mode: 0=search,1=fullmatch) → rax=1/0。"""
    em.label_here("re_exec")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x20")
    em.store_rip_from("re_mode", 7)
    em.xor_rr32(0, 0)
    em.store_rip_from("re_pos", 0)
    em.lea_rip(2, "re_nlist")
    em.xor_rr32(0, 0)
    em.mov_mem_r(2, 0, 0)
    em.mov_r_imm32(0, 1)
    em.store_rip_from("re_nn", 0)
    em.label_here("ex_main")
    em.load_rip_to(0, "re_gen")
    em.inc_r(0)
    em.store_rip_from("re_gen", 0)
    em.xor_rr32(0, 0)
    em.store_rip_from("re_cn", 0)
    em.store_rip_from("re_k", 0)
    em.label_here("ex_cl")
    em.load_rip_to(0, "re_k")
    em.load_rip_to(1, "re_nn")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x83, "ex_cl_done")
    em.lea_rip(2, "re_nlist")
    em.mov_rd_mem(7, 2, 0, index=0, scale=8)
    em.load_rip_to(6, "re_pos")
    em.load_rip_to(2, "re_gen")
    em.call_rel32("re_closure")
    em.load_rip_to(0, "re_k")
    em.inc_r(0)
    em.store_rip_from("re_k", 0)
    em.jcc_rel32(None, "ex_cl")
    em.label_here("ex_cl_done")
    em.xor_rr32(0, 0)
    em.store_rip_from("re_k", 0)
    em.label_here("ex_chk")
    em.load_rip_to(0, "re_k")
    em.load_rip_to(1, "re_cn")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x83, "ex_chk_done")
    em.lea_rip(2, "re_clist")
    em.mov_rd_mem(6, 2, 0, index=0, scale=8)
    em.mov_rr(9, 6)
    em.add_rr(9, 6)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(10, 8, 0, index=9, scale=8)
    em.cmp_ri(10, OP_MATCH)
    em.jcc_rel32(0x85, "ex_chk_next")
    em.load_rip_to(1, "re_mode")
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, "ex_found")
    em.load_rip_to(1, "re_pos")
    em.load_rip_to(2, "re_slen")
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x84, "ex_found")
    em.label_here("ex_chk_next")
    em.load_rip_to(0, "re_k")
    em.inc_r(0)
    em.store_rip_from("re_k", 0)
    em.jcc_rel32(None, "ex_chk")
    em.label_here("ex_chk_done")
    em.load_rip_to(0, "re_pos")
    em.load_rip_to(1, "re_slen")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x84, "ex_false")
    em.xor_rr32(0, 0)
    em.store_rip_from("re_nn", 0)
    em.store_rip_from("re_k", 0)
    em.label_here("ex_step")
    em.load_rip_to(0, "re_k")
    em.load_rip_to(1, "re_cn")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x83, "ex_step_done")
    em.lea_rip(2, "re_clist")
    em.mov_rd_mem(6, 2, 0, index=0, scale=8)
    em.mov_rr(9, 6)
    em.add_rr(9, 6)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(10, 8, 0, index=9, scale=8)
    em.cmp_ri(10, OP_CHAR)
    em.jcc_rel32(0x84, "ex_char")
    em.cmp_ri(10, OP_ANY)
    em.jcc_rel32(0x84, "ex_any")
    em.cmp_ri(10, OP_CLASS)
    em.jcc_rel32(0x84, "ex_class")
    em.jcc_rel32(None, "ex_step_next")
    em.label_here("ex_char")
    em.mov_rd_mem(1, 8, 8, index=9, scale=8)        # arg
    em.load_rip_to(0, "re_pos")
    em.lea_rip(2, "re_subj_cp")
    em.mov_rd_mem(11, 2, 0, index=0, scale=8)       # subj[pos]
    em.cmp_rr(1, 11)
    em.jcc_rel32(0x85, "ex_step_next")
    em.jcc_rel32(None, "ex_add")
    em.label_here("ex_any")
    em.load_rip_to(0, "re_pos")
    em.lea_rip(2, "re_subj_cp")
    em.mov_rd_mem(11, 2, 0, index=0, scale=8)
    em.cmp_ri(11, 10)
    em.jcc_rel32(0x84, "ex_step_next")
    em.jcc_rel32(None, "ex_add")
    em.label_here("ex_class")
    em.mov_rd_mem(7, 8, 8, index=9, scale=8)        # class idx
    em.load_rip_to(0, "re_pos")
    em.lea_rip(2, "re_subj_cp")
    em.mov_rd_mem(6, 2, 0, index=0, scale=8)        # cp
    em.call_rel32("re_class_match")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "ex_step_next")
    em.jcc_rel32(None, "ex_add")
    em.label_here("ex_add")
    # re_class_match 可能破坏 r6(s)/r1，故从 re_k 重载当前状态
    em.load_rip_to(0, "re_k")
    em.lea_rip(2, "re_clist")
    em.mov_rd_mem(6, 2, 0, index=0, scale=8)        # s = clist[k]
    em.load_rip_to(0, "re_nn")
    em.lea_rip(2, "re_nlist")
    em.mov_rr(1, 6)
    em.inc_r(1)                                     # 目标 = s+1
    em.mov_mem_r_idx(2, 1, 0, 0, 8)
    em.inc_r(0)
    em.store_rip_from("re_nn", 0)
    em.label_here("ex_step_next")
    em.load_rip_to(0, "re_k")
    em.inc_r(0)
    em.store_rip_from("re_k", 0)
    em.jcc_rel32(None, "ex_step")
    em.label_here("ex_step_done")
    em.load_rip_to(0, "re_mode")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "ex_no_seed")
    em.load_rip_to(0, "re_nn")
    em.lea_rip(2, "re_nlist")
    em.xor_rr32(1, 1)
    em.mov_mem_r_idx(2, 1, 0, 0, 8)
    em.inc_r(0)
    em.store_rip_from("re_nn", 0)
    em.label_here("ex_no_seed")
    em.load_rip_to(0, "re_pos")
    em.inc_r(0)
    em.store_rip_from("re_pos", 0)
    em.jcc_rel32(None, "ex_main")
    em.label_here("ex_found")
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, "ex_ret")
    em.label_here("ex_false")
    em.xor_rr32(0, 0)
    em.label_here("ex_ret")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_re_runtime(em):
    """发射全部原生正则运行时。"""
    _emit_re_check_str(em)
    _emit_re_utf8_decode(em)
    _emit_re_is_word(em)
    _emit_re_is_boundary(em)
    _emit_re_sh_match(em)
    _emit_re_class_match(em)
    _emit_re_class_new(em)
    _emit_re_class_add_range(em)
    _emit_re_class_add_sh(em)
    _emit_re_peek(em)
    _emit_re_peek2(em)
    _emit_re_next(em)
    _emit_re_read_hex(em)
    _emit_re_p_alt(em)
    _emit_re_p_seq(em)
    _emit_re_p_quant(em)
    _emit_re_p_atom(em)
    _emit_re_p_group(em)
    _emit_re_p_escape_top(em)
    _emit_re_p_class_atom(em)
    _emit_re_p_class(em)
    _emit_re_compile(em)
    _emit_re_closure(em)
    _emit_re_exec(em)


# ---------------------------------------------------------------- 内建函数体
def _emit_regex_body(em, tag, mode):
    """公共：校验字符串 → 解码 → 编译 → 执行 → 布尔结果。mode 0=搜索,1=全匹配。"""
    em.label_here(f"fn:{tag}")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.emit(b"\x48\x8B\xBD\xF0\xFF\xFF\xFF")        # mov rdi,[rbp-16]（pat）
    em.call_rel32("re_check_str")
    em.mov_rr(6, 2)
    em.mov_rr(7, 0)
    em.lea_rip(2, "re_pat_cp")
    em.call_rel32("re_utf8_decode")
    em.store_rip_from("re_plen", 0)
    em.emit(b"\x48\x8B\xBD\xF8\xFF\xFF\xFF")        # mov rdi,[rbp-8]（subj）
    em.call_rel32("re_check_str")
    em.mov_rr(6, 2)
    em.mov_rr(7, 0)
    em.lea_rip(2, "re_subj_cp")
    em.call_rel32("re_utf8_decode")
    em.store_rip_from("re_slen", 0)
    em.load_rip_to(7, "re_plen")
    em.call_rel32("re_compile")
    em.mov_r_imm32(7, mode)
    em.call_rel32("re_exec")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, f"{tag}_false")
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, f"{tag}_done")
    em.label_here(f"{tag}_false")
    em.lea_rip(0, "bool_false")
    em.label_here(f"{tag}_done")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_builtin_regex_match(em):
    _emit_regex_body(em, "匹配", 0)


def _emit_builtin_regex_fullmatch(em):
    _emit_regex_body(em, "全匹配", 1)


# ---------------------------------------------------------------- 数据/BSS
_SCALARS = [
    "re_pat_i", "re_plen", "re_pc", "re_prog_len", "re_class_len",
    "re_gen", "re_pos", "re_cn", "re_nn", "re_k", "re_mode", "re_slen",
]


def emit_regex_bss(eb):
    """在 .bss 预留正则引擎 scratch（全零，纯虚拟，不物化）。"""
    for nm in _SCALARS:
        eb.align(8)
        eb.label_here(nm)
        eb.emit_virtual(8)
    for nm, cnt in (("re_prog", PROG_MAX * 2),
                    ("re_class", CLASS_MAX),
                    ("re_visited", PROG_MAX),
                    ("re_stack", PROG_MAX),
                    ("re_clist", PROG_MAX),
                    ("re_nlist", PROG_MAX),
                    ("re_pat_cp", PAT_CP_MAX),
                    ("re_subj_cp", SUBJ_CP_MAX)):
        eb.align(16)
        eb.label_here(nm)
        eb.emit_virtual(cnt * 8)


def emit_regex_data(ed):
    """在 .data（静态堆区）发射正则错误消息串对象。"""
    for lbl, text in (("re_err_notstr_msg", ERR_NOTSTR),
                      ("re_err_badpat", ERR_BADPAT)):
        raw = text.encode("utf-8")
        ed.align(8)
        ed.label_here(lbl)
        ed.emit(struct.pack("<Q", TYPE_STR))
        ed.emit(struct.pack("<Q", len(raw)))
        ed.emit(raw)
        ed.align(8)
