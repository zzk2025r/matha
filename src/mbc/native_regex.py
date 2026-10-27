r"""原生正则引擎（阶段 B-1：运行时 NFA 编译器 + Pike/Thompson 集合模拟 VM）。

背景
====
解释器（src/interp.py）与 M3V VM（src/mbc/vm.py）复用 src/kernel/regex_builtin.py 的纯
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
TYPE_LIST = 2
TYPE_DICT = 3

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
# 捕获扩展（阶段 B-2）：前进式回溯 VM 专用。Pike VM（匹配/全匹配）把它们
# 视为 epsilon（SAVE）、SPLIT（LOOPHEAD/PLUSHEAD）、JMP（LOOPEND）。
OP_SAVE = 12     # arg=slot（写入 caps[slot]=pos，旧值入 undo 日志）
OP_LOOPHEAD = 13  # arg=body | exit<<32（推 exit 回溯帧 + lstack 项；可跳过）
OP_PLUSHEAD = 14  # arg=body | exit<<32（仅推 lstack 项，首迭代必执行）
OP_LOOPEND = 15   # arg=head pc（空迭代提交 exit；否则回 body 并推 exit 帧）

# 容量（全在 .bss，虚拟内存廉价）
CAP_GROUPS_MAX = 32
CAPS = 2 * (CAP_GROUPS_MAX + 1)   # 每组占 2 槽（起/止），槽 0/1 为整体
BT_MAX = 1 << 20      # 回溯栈深度
UNDO_MAX = 1 << 20    # 捕获 undo 日志深度
LOOP_MAX = 1 << 16    # 循环守卫栈深度
NAME_MAX = 64         # 命名组个数上限
NAME_CP_MAX = 256     # 命名组名码点总长度上限


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


def _patch_op(em, idx_off, op):
    """覆盖某个占位指令的操作码（idx 存于 [rbp+idx_off]，arg 保持原值）。"""
    em.mov_rd_mem(11, 5, idx_off)
    em.mov_rr(9, 11)
    em.add_rr(9, 11)
    em.mov_r_imm32(10, op)
    em.lea_rip(8, "re_prog")
    em.mov_mem_r_idx(8, 10, 0, 9, 8)


def _emit_inst_stack(em, op, arg_off):
    """发射一条 op，其 arg 取自 [rbp+arg_off]。"""
    em.mov_rd_mem(0, 5, arg_off)
    em.mov_r_imm32(1, op)
    _emit_inst(em)


def _badpat(em):
    em.lea_rip(0, "re_err_badpat")
    em.call_rel32("raise_rt")
    _ud2(em)


# ---------------------------------------------------- 回溯 VM 发射助手
# 寄存器约定（re_bt_try 内）：rbx=pc，r12=pos，r13=bt_sp，r14=undo_n，
# r15=lsp。局部 [rbp-0x48]=start、[rbp-0x50]=require_end。
_LBL = [0]


def _uid(prefix):
    _LBL[0] += 1
    return f"{prefix}_{_LBL[0]}"


def _bt_op_to(em, dst):
    """dst = prog[rbx*2]（操作码）。"""
    em.mov_rr(9, 3)
    em.add_rr(9, 3)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(dst, 8, 0, index=9, scale=8)


def _bt_arg_to(em, dst):
    """dst = prog[rbx*2+1]（当前指令参数）。"""
    em.mov_rr(9, 3)
    em.add_rr(9, 3)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(dst, 8, 8, index=9, scale=8)


def _bt_arg_at(em, idx_reg, dst):
    """dst = prog[idx_reg*2+1]。"""
    em.mov_rr(9, idx_reg)
    em.add_rr(9, idx_reg)
    em.lea_rip(8, "re_prog")
    em.mov_rd_mem(dst, 8, 8, index=9, scale=8)


def _bt_push(em, pcreg):
    """把 (pcreg, pos, undo_n, lsp) 压入回溯栈（先校验容量）。"""
    l_ovf = "bt_overflow"
    em.cmp_ri(13, BT_MAX)
    em.jcc_rel32(0x83, l_ovf)
    em.lea_rip(8, "re_bt_pc")
    em.mov_mem_r_idx(8, pcreg, 0, 13, 8)
    em.lea_rip(8, "re_bt_pos")
    em.mov_mem_r_idx(8, 12, 0, 13, 8)
    em.lea_rip(8, "re_bt_ul")
    em.mov_mem_r_idx(8, 14, 0, 13, 8)
    em.lea_rip(8, "re_bt_lsp")
    em.mov_mem_r_idx(8, 15, 0, 13, 8)
    em.inc_r(13)


def _bt_pop(em):
    """回溯：弹帧恢复 pc/pos/lsp，并把 undo 日志回放到该帧的 undo_n。"""
    l_loop = _uid("bt_ud")
    l_done = _uid("bt_udd")
    em.dec_r(13)
    em.lea_rip(8, "re_bt_pc")
    em.mov_rd_mem(3, 8, 0, index=13, scale=8)
    em.lea_rip(8, "re_bt_pos")
    em.mov_rd_mem(12, 8, 0, index=13, scale=8)
    em.lea_rip(8, "re_bt_ul")
    em.mov_rd_mem(9, 8, 0, index=13, scale=8)       # r9=目标 undo_n
    em.lea_rip(8, "re_bt_lsp")
    em.mov_rd_mem(15, 8, 0, index=13, scale=8)
    em.label_here(l_loop)
    em.cmp_rr(14, 9)
    em.jcc_rel32(0x86, l_done)                       # jbe（r14<=r9）
    em.dec_r(14)
    em.lea_rip(8, "re_undo_slot")
    em.mov_rd_mem(1, 8, 0, index=14, scale=8)        # rcx=slot
    em.lea_rip(8, "re_undo_val")
    em.mov_rd_mem(2, 8, 0, index=14, scale=8)        # rdx=old
    em.lea_rip(8, "re_caps")
    em.mov_mem_r_idx(8, 2, 0, 1, 8)                  # caps[slot]=old
    em.jcc_rel32(None, l_loop)
    em.label_here(l_done)
    em.mov_rr(14, 9)



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
    _patch_op(em, -8, OP_LOOPHEAD)
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # body = head+1
    _emit_inst_stack(em, OP_LOOPEND, -8)
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)                         # exit
    _patch_split(em, -8, -16, -40)
    em.jcc_rel32(None, "pq_done")

    em.label_here("pq_plus")
    em.call_rel32("re_next")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)
    em.jcc_rel32(0x84, "pq_bad")
    em.cmp_ri(0, 0x2B)
    em.jcc_rel32(0x84, "pq_bad")
    _patch_op(em, -8, OP_PLUSHEAD)
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)                         # body
    _emit_inst_stack(em, OP_LOOPEND, -8)
    em.load_rip_to(0, "re_pc")
    em.mov_mem_r(5, -40, 0)                         # exit
    _patch_split(em, -8, -16, -40)
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
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x30")                    # sub rsp,0x30
    em.call_rel32("re_next")                        # 消耗 '('
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3F)                              # '?'
    em.jcc_rel32(0x85, "pg_plain")
    em.call_rel32("re_next")                        # 消耗 '?'
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3A)                              # ':'
    em.jcc_rel32(0x84, "pg_noncap")
    em.cmp_ri(0, 0x50)                              # 'P'
    em.jcc_rel32(0x84, "pg_P")
    em.cmp_ri(0, 0x3C)                              # '<'
    em.jcc_rel32(0x84, "pg_lt")
    em.cmp_ri(0, 0x27)                              # "'"
    em.jcc_rel32(0x84, "pg_quote")
    em.jcc_rel32(None, "pg_bad")

    em.label_here("pg_noncap")
    em.call_rel32("re_next")                        # 消耗 ':'
    em.call_rel32("re_p_alt")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x29)                              # ')'
    em.jcc_rel32(0x85, "pg_bad")
    em.call_rel32("re_next")
    em.jcc_rel32(None, "pg_done")

    em.label_here("pg_P")
    em.call_rel32("re_next")                        # 消耗 'P'
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3C)                              # '<'
    em.jcc_rel32(0x85, "pg_bad")                    # (?P=…) 反向引用：不支持
    em.label_here("pg_lt")
    em.call_rel32("re_next")                        # 消耗 '<'
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x3D)                              # '='
    em.jcc_rel32(0x84, "pg_bad")
    em.cmp_ri(0, 0x21)                              # '!'
    em.jcc_rel32(0x84, "pg_bad")
    em.mov_r_imm32(0, 0x3E)                         # 结束符 '>'
    em.mov_mem_r(5, -32, 0)
    em.jcc_rel32(None, "pg_nameread")

    em.label_here("pg_quote")
    em.call_rel32("re_next")                        # 消耗 "'"
    em.mov_r_imm32(0, 0x27)                         # 结束符 '
    em.mov_mem_r(5, -32, 0)

    em.label_here("pg_nameread")
    em.load_rip_to(0, "re_pat_i")
    em.mov_mem_r(5, -16, 0)                          # b
    em.label_here("pg_nloop")
    em.call_rel32("re_peek")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x84, "pg_bad")
    em.mov_rd_mem(6, 5, -32)
    em.cmp_rr(0, 6)
    em.jcc_rel32(0x84, "pg_nend")
    em.call_rel32("re_next")
    em.jcc_rel32(None, "pg_nloop")
    em.label_here("pg_nend")
    em.load_rip_to(0, "re_pat_i")
    em.mov_mem_r(5, -24, 0)                          # e
    em.call_rel32("re_next")                        # 消耗结束符
    em.load_rip_to(0, "re_ngroups")
    em.inc_r(0)
    em.store_rip_from("re_ngroups", 0)
    em.mov_mem_r(5, -8, 0)                           # gi
    em.cmp_ri(0, CAP_GROUPS_MAX)
    em.jcc_rel32(0x87, "pg_bad")                     # 捕获组过多
    em.load_rip_to(10, "re_name_n")
    em.cmp_ri(10, NAME_MAX)
    em.jcc_rel32(0x83, "pg_bad")                     # 命名组过多
    em.mov_rd_mem(0, 5, -8)
    em.lea_rip(8, "re_name_gi")
    em.mov_mem_r_idx(8, 0, 0, 10, 8)
    em.mov_rd_mem(0, 5, -16)
    em.lea_rip(8, "re_name_b")
    em.mov_mem_r_idx(8, 0, 0, 10, 8)
    em.mov_rd_mem(0, 5, -24)
    em.lea_rip(8, "re_name_e")
    em.mov_mem_r_idx(8, 0, 0, 10, 8)
    em.inc_r(10)
    em.store_rip_from("re_name_n", 10)
    em.jcc_rel32(None, "pg_cap_open")

    em.label_here("pg_plain")
    em.load_rip_to(0, "re_ngroups")
    em.inc_r(0)
    em.store_rip_from("re_ngroups", 0)
    em.mov_mem_r(5, -8, 0)                          # gi
    em.cmp_ri(0, CAP_GROUPS_MAX)
    em.jcc_rel32(0x87, "pg_bad")

    em.label_here("pg_cap_open")
    em.mov_rd_mem(0, 5, -8)
    em.shl_ri(0, 1)                                 # 槽 = 2*gi
    _emit_inst_reg(em, OP_SAVE, 0)
    em.call_rel32("re_p_alt")
    em.call_rel32("re_peek")
    em.cmp_ri(0, 0x29)                              # ')'
    em.jcc_rel32(0x85, "pg_bad")
    em.call_rel32("re_next")
    em.mov_rd_mem(0, 5, -8)
    em.shl_ri(0, 1)
    em.inc_r(0)                                     # 槽 = 2*gi+1
    _emit_inst_reg(em, OP_SAVE, 0)
    em.label_here("pg_done")
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
    em.xor_rr32(0, 0)
    em.store_rip_from("re_ngroups", 0)
    em.store_rip_from("re_name_n", 0)
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
    em.cmp_ri(10, OP_SAVE)
    em.jcc_rel32(0x84, "c_save")
    em.cmp_ri(10, OP_LOOPHEAD)
    em.jcc_rel32(0x84, "c_split")
    em.cmp_ri(10, OP_PLUSHEAD)
    em.jcc_rel32(0x84, "c_split")
    em.cmp_ri(10, OP_LOOPEND)
    em.jcc_rel32(0x84, "c_jmp")
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
    em.label_here("c_save")
    em.inc_r(6)                                     # 后继 = s+1（忽略槽号）
    em.jcc_rel32(None, "c_pusharg")

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


# ============================================================ 回溯 VM
def _emit_re_bt_try(em):
    """re_bt_try(rdi=start, rsi=require_end) → rax=1/0；成功时填 re_caps。

    显式回溯 VM，对齐 regexlib 的 leftmost-first 语义。寄存器：
     rbx=pc、r12=pos、r13=bt_sp、r14=undo_n、r15=lsp。
     局部：[rbp-0x48]=start、[rbp-0x50]=require_end。
    """
    em.label_here("re_bt_try")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")  # push rbx,r12,r13,r14,r15
    em.emit(b"\x48\x83\xEC\x48")                    # sub rsp,0x48
    em.mov_mem_r(5, -0x48, 7)                       # start
    em.mov_mem_r(5, -0x50, 6)                       # require_end
    em.mov_rax_imm64(-1)                            # caps[*] = -1
    em.load_rip_to(6, "re_ngroups")
    em.inc_r(6)
    em.shl_ri(6, 1)                                 # m = 2*(ngroups+1)
    em.xor_rr32(1, 1)
    lbl_fill = _uid("bt_fill")
    lbl_filld = _uid("bt_filld")
    em.label_here(lbl_fill)
    em.cmp_rr(1, 6)
    em.jcc_rel32(0x83, lbl_filld)
    em.lea_rip(8, "re_caps")
    em.mov_mem_r_idx(8, 0, 0, 1, 8)
    em.inc_r(1)
    em.jcc_rel32(None, lbl_fill)
    em.label_here(lbl_filld)
    em.mov_rd_mem(12, 5, -0x48)                     # pos = start
    em.xor_rr32(13, 13)
    em.xor_rr32(14, 14)
    em.xor_rr32(15, 15)
    em.xor_rr32(3, 3)                               # pc = 0
    em.label_here("rg_bt_loop")
    _bt_op_to(em, 10)
    em.cmp_ri(10, OP_MATCH)
    em.jcc_rel32(0x84, "bt_match")
    em.cmp_ri(10, OP_CHAR)
    em.jcc_rel32(0x84, "bt_char")
    em.cmp_ri(10, OP_ANY)
    em.jcc_rel32(0x84, "bt_any")
    em.cmp_ri(10, OP_CLASS)
    em.jcc_rel32(0x84, "bt_class")
    em.cmp_ri(10, OP_JMP)
    em.jcc_rel32(0x84, "bt_jmp")
    em.cmp_ri(10, OP_SPLIT)
    em.jcc_rel32(0x84, "bt_split")
    em.cmp_ri(10, OP_BOL)
    em.jcc_rel32(0x84, "bt_bol")
    em.cmp_ri(10, OP_EOL)
    em.jcc_rel32(0x84, "bt_eolend")
    em.cmp_ri(10, OP_BOS)
    em.jcc_rel32(0x84, "bt_bol")                    # \A：要求 pos==0
    em.cmp_ri(10, OP_EOS)
    em.jcc_rel32(0x84, "bt_eolend")                 # \Z\z：要求 pos==slen

    em.cmp_ri(10, OP_WORDB)
    em.jcc_rel32(0x84, "bt_wordb")
    em.cmp_ri(10, OP_NWORDB)
    em.jcc_rel32(0x84, "bt_nwordb")
    em.cmp_ri(10, OP_SAVE)
    em.jcc_rel32(0x84, "bt_save")
    em.cmp_ri(10, OP_LOOPHEAD)
    em.jcc_rel32(0x84, "bt_loophead")
    em.cmp_ri(10, OP_PLUSHEAD)
    em.jcc_rel32(0x84, "bt_plushead")
    em.cmp_ri(10, OP_LOOPEND)
    em.jcc_rel32(0x84, "bt_loopend")
    em.jcc_rel32(None, "bt_fail")

    em.label_here("bt_match")
    em.mov_rd_mem(10, 5, -0x50)                     # require_end
    em.test_rr(10, 10)
    em.jcc_rel32(0x84, "bt_match_ok")
    em.load_rip_to(11, "re_slen")
    em.cmp_rr(12, 11)
    em.jcc_rel32(0x85, "bt_fail")
    em.label_here("bt_match_ok")
    em.mov_rd_mem(8, 5, -0x48)                      # start
    em.lea_rip(9, "re_caps")
    em.mov_mem_r(9, 0, 8)                           # caps[0]=start
    em.mov_mem_r(9, 8, 12)                          # caps[1]=pos
    em.jcc_rel32(None, "bt_ret_yes")

    em.label_here("bt_char")
    em.load_rip_to(11, "re_slen")
    em.cmp_rr(12, 11)
    em.jcc_rel32(0x83, "bt_fail")
    _bt_arg_to(em, 10)
    em.lea_rip(8, "re_subj_cp")
    em.mov_rd_mem(11, 8, 0, index=12, scale=8)
    em.cmp_rr(10, 11)
    em.jcc_rel32(0x85, "bt_fail")
    em.inc_r(12)
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_any")
    em.load_rip_to(11, "re_slen")
    em.cmp_rr(12, 11)
    em.jcc_rel32(0x83, "bt_fail")
    em.lea_rip(8, "re_subj_cp")
    em.mov_rd_mem(11, 8, 0, index=12, scale=8)
    em.cmp_ri(11, 10)                               # '\n'
    em.jcc_rel32(0x84, "bt_fail")
    em.inc_r(12)
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_class")
    em.load_rip_to(11, "re_slen")
    em.cmp_rr(12, 11)
    em.jcc_rel32(0x83, "bt_fail")
    _bt_arg_to(em, 7)
    em.lea_rip(8, "re_subj_cp")
    em.mov_rd_mem(6, 8, 0, index=12, scale=8)
    em.call_rel32("re_class_match")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "bt_fail")
    em.inc_r(12)
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_jmp")
    _bt_arg_to(em, 3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_split")
    _bt_arg_to(em, 10)
    em.mov_rr(11, 10)
    em.shr_ri(11, 32)
    _bt_push(em, 11)
    em.mov_rr(3, 10)
    em.shl_ri(3, 32)
    em.shr_ri(3, 32)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_bol")
    em.test_rr(12, 12)
    em.jcc_rel32(0x85, "bt_fail")
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_eolend")
    em.load_rip_to(11, "re_slen")
    em.cmp_rr(12, 11)
    em.jcc_rel32(0x85, "bt_fail")
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_wordb")
    em.mov_rr(7, 12)
    em.call_rel32("re_is_boundary")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "bt_fail")
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_nwordb")
    em.mov_rr(7, 12)
    em.call_rel32("re_is_boundary")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "bt_fail")
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_save")
    em.cmp_ri(14, UNDO_MAX)
    em.jcc_rel32(0x83, "bt_overflow")
    _bt_arg_to(em, 10)                              # slot
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(11, 8, 0, index=10, scale=8)      # 旧值
    em.lea_rip(8, "re_undo_slot")
    em.mov_mem_r_idx(8, 10, 0, 14, 8)
    em.lea_rip(8, "re_undo_val")
    em.mov_mem_r_idx(8, 11, 0, 14, 8)
    em.inc_r(14)
    em.lea_rip(8, "re_caps")
    em.mov_mem_r_idx(8, 12, 0, 10, 8)               # caps[slot]=pos
    em.inc_r(3)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_loophead")
    em.cmp_ri(15, LOOP_MAX)
    em.jcc_rel32(0x83, "bt_overflow")
    _bt_arg_to(em, 10)
    em.mov_rr(11, 10)
    em.shr_ri(11, 32)                               # exit
    _bt_push(em, 11)
    em.lea_rip(8, "re_lstack")
    em.mov_mem_r_idx(8, 12, 0, 15, 8)
    em.inc_r(15)
    em.mov_rr(3, 10)
    em.shl_ri(3, 32)
    em.shr_ri(3, 32)                                # body
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_plushead")
    em.cmp_ri(15, LOOP_MAX)
    em.jcc_rel32(0x83, "bt_overflow")
    _bt_arg_to(em, 10)
    em.lea_rip(8, "re_lstack")
    em.mov_mem_r_idx(8, 12, 0, 15, 8)
    em.inc_r(15)
    em.mov_rr(3, 10)
    em.shl_ri(3, 32)
    em.shr_ri(3, 32)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_loopend")
    _bt_arg_to(em, 10)                              # head pc
    _bt_arg_at(em, 10, 11)                          # head 的 arg（body|exit<<32）
    em.mov_rr(9, 15)
    em.dec_r(9)
    em.lea_rip(8, "re_lstack")
    em.mov_rd_mem(2, 8, 0, index=9, scale=8)        # entry
    em.cmp_rr(12, 2)
    em.jcc_rel32(0x85, "bt_loopend_cont")
    em.dec_r(15)                                    # 空迭代：提交 exit
    em.mov_rr(3, 11)
    em.shr_ri(3, 32)
    em.jcc_rel32(None, "rg_bt_loop")
    em.label_here("bt_loopend_cont")
    em.mov_rr(2, 11)
    em.shl_ri(2, 32)
    em.shr_ri(2, 32)                                # body
    em.mov_rr(1, 11)
    em.shr_ri(1, 32)                                # exit
    em.mov_rr(9, 15)
    em.dec_r(9)
    em.lea_rip(8, "re_lstack")
    em.mov_mem_r_idx(8, 12, 0, 9, 8)                # lstack[lsp-1]=pos
    _bt_push(em, 1)
    em.mov_rr(3, 2)
    em.jcc_rel32(None, "rg_bt_loop")

    em.label_here("bt_ret_yes")
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, "bt_ret")
    em.label_here("bt_overflow")
    em.xor_rr32(0, 0)
    em.jcc_rel32(None, "bt_ret")
    em.label_here("bt_fail")
    em.test_rr(13, 13)
    em.jcc_rel32(0x84, "bt_nomatch")
    _bt_pop(em)
    em.jcc_rel32(None, "rg_bt_loop")
    em.label_here("bt_nomatch")
    em.xor_rr32(0, 0)
    em.label_here("bt_ret")
    em.emit(b"\x48\x83\xC4\x48")                    # add rsp,0x48
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")  # pop r15,r14,r13,r12,rbx
    em.emit(b"\x5D\xC3")                            # pop rbp; ret


def _emit_re_search(em):
    """re_search(rdi=from, rsi=require_end) → rax=1/0；成功时写 re_caps。

    require_end=0：从 from 起逐起点搜索，返回首个成功；require_end=1：仅试 from
    且要求匹配到末尾（from 必须为 0）。
    """
    em.label_here("re_search")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x53\x41\x54")                        # push rbx; push r12
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_mem_r(5, -0x28, 7)                       # from
    em.mov_mem_r(5, -0x30, 6)                       # require_end
    em.mov_rr(3, 7)                                 # rbx=from
    em.mov_rr(12, 6)                                # r12=require_end
    em.label_here("rs_loop")
    em.test_rr(12, 12)
    em.jcc_rel32(0x84, "rs_run")
    em.test_rr(3, 3)
    em.jcc_rel32(0x85, "rg_rs_fail")                   # require_end 且 from!=0
    em.label_here("rs_run")
    em.mov_rr(7, 3)
    em.mov_rr(6, 12)
    em.call_rel32("re_bt_try")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "rs_found")
    em.test_rr(12, 12)
    em.jcc_rel32(0x85, "rg_rs_fail")                   # require_end：仅一次
    em.load_rip_to(1, "re_slen")
    em.cmp_rr(3, 1)
    em.jcc_rel32(0x83, "rg_rs_fail")
    em.inc_r(3)
    em.jcc_rel32(None, "rs_loop")
    em.label_here("rs_found")
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, "rs_ret")
    em.label_here("rg_rs_fail")
    em.xor_rr32(0, 0)
    em.label_here("rs_ret")
    em.emit(b"\x48\x83\xC4\x20\x41\x5C\x5B\x5D\xC3")  # add rsp,0x20; pop r12; pop rbx; pop rbp; ret


def _emit_re_enc_cp(em):
    """re_enc_cp(rdi=out, rax=cp)：把码点写为 UTF-8，前进 rdi。"""
    em.label_here("re_enc_cp")
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x83, "ec_2")
    em.mov_m8_r(7, 0, 0)
    em.inc_r(7)
    em.emit(b"\xC3")
    em.label_here("ec_2")
    em.cmp_ri(0, 0x800)
    em.jcc_rel32(0x83, "ec_3")
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.emit(b"\x48\x83\xC9\xC0")
    em.mov_m8_r(7, 0, 1)
    em.mov_rr(1, 0)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 1, 1)
    em.add_ri(7, 2)
    em.emit(b"\xC3")
    em.label_here("ec_3")
    em.cmp_ri(0, 0x10000)
    em.jcc_rel32(0x83, "ec_4")
    em.mov_rr(1, 0)
    em.shr_ri(1, 12)
    em.emit(b"\x48\x83\xC9\xE0")
    em.mov_m8_r(7, 0, 1)
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 1, 1)
    em.mov_rr(1, 0)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 2, 1)
    em.add_ri(7, 3)
    em.emit(b"\xC3")
    em.label_here("ec_4")
    em.mov_rr(1, 0)
    em.shr_ri(1, 18)
    em.emit(b"\x48\x83\xC9\xF0")
    em.mov_m8_r(7, 0, 1)
    em.mov_rr(1, 0)
    em.shr_ri(1, 12)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 1, 1)
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 2, 1)
    em.mov_rr(1, 0)
    em.and_ri(1, 0x3F)
    em.emit(b"\x48\x83\xC9\x80")
    em.mov_m8_r(7, 3, 1)
    em.add_ri(7, 4)
    em.emit(b"\xC3")


def _emit_re_cp_slice(em):
    """re_cp_slice(rdi=cpbase, rsi=start, rdx=end) → rax=TYPE_STR（新建）。"""
    em.label_here("re_cp_slice")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")  # push rbx,r12,r13,r14,r15
    em.emit(b"\x48\x83\xEC\x28")
    em.mov_rr(3, 7)                                 # rbx=cpbase
    em.mov_rr(13, 2)                                # r13=end
    em.mov_rr(14, 6)                                # r14=start(k)
    em.mov_rr(0, 2)
    em.sub_rr(0, 6)                                 # n=end-start
    em.mov_rr(7, 0)
    em.shl_ri(7, 2)
    em.add_ri(7, 24)
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_rr(15, 0)                                # r15=obj
    em.lea_mem(7, 15, 16)                           # rdi=out
    em.mov_mem_r(5, -0x48, 7)                       # 保存 out 基址
    em.label_here("cs_loop")
    em.cmp_rr(14, 13)
    em.jcc_rel32(0x83, "cs_done")
    em.mov_rd_mem(0, 3, 0, index=14, scale=8)       # rax=cp
    em.call_rel32("re_enc_cp")
    em.inc_r(14)
    em.jcc_rel32(None, "cs_loop")
    em.label_here("cs_done")
    em.mov_rr(0, 7)
    em.mov_rd_mem(1, 5, -0x48)
    em.sub_rr(0, 1)                                 # 字节长
    em.mov_mem_r(15, 8, 0)
    em.mov_rr(0, 15)
    em.emit(b"\x48\x83\xC4\x28")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")
    em.emit(b"\x5D\xC3")


def _emit_re_cap_slice(em):
    """re_cap_slice(rdi=组号 gi) → rax=该组文本（未参与为 null_obj）。"""
    em.label_here("re_cap_slice")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53")
    em.emit(b"\x48\x83\xEC\x18")
    em.mov_rr(3, 7)                                 # rbx=gi
    em.mov_rr(1, 3)
    em.add_rr(1, 3)                                 # 2*gi
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(6, 8, 0, index=1, scale=8)        # start
    em.cmp_ri(6, -1)
    em.jcc_rel32(0x84, "cps_null")
    em.mov_rd_mem(2, 8, 8, index=1, scale=8)        # end
    em.lea_rip(7, "re_subj_cp")
    em.call_rel32("re_cp_slice")
    em.jcc_rel32(None, "cps_ret")
    em.label_here("cps_null")
    em.lea_rip(0, "null_obj")
    em.label_here("cps_ret")
    em.emit(b"\x48\x83\xC4\x18\x5B\x5D\xC3")


def _emit_re_mk_match_list(em):
    """re_mk_match_list() → rax=[g0,g1,...,gn]（未参与为 null_obj）。"""
    em.label_here("re_mk_match_list")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")
    em.emit(b"\x48\x83\xEC\x28")
    em.load_rip_to(14, "re_ngroups")
    em.inc_r(14)                                    # n
    em.mov_rr(7, 14)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_mem_r(0, 8, 14)
    em.mov_rr(15, 0)                                # r15=list
    em.xor_rr32(13, 13)                             # k=0
    em.label_here("mm_loop")
    em.cmp_rr(13, 14)
    em.jcc_rel32(0x83, "mm_done")
    em.mov_rr(7, 13)
    em.call_rel32("re_cap_slice")
    em.mov_mem_r_idx(15, 0, 16, 13, 8)              # list[16+8k]=rax
    em.inc_r(13)
    em.jcc_rel32(None, "mm_loop")
    em.label_here("mm_done")
    em.mov_rr(0, 15)
    em.emit(b"\x48\x83\xC4\x28")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")
    em.emit(b"\x5D\xC3")


def _emit_re_join(em):
    """re_join(rdi=list of str) → rax=拼接后的 str。"""
    em.label_here("re_join")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")
    em.emit(b"\x48\x83\xEC\x28")
    em.mov_rr(3, 7)                                 # rbx=list
    em.mov_rd_mem(12, 3, 8)                         # r12=n
    em.xor_rr32(13, 13)
    em.xor_rr32(14, 14)
    em.label_here("rj_l1")
    em.cmp_rr(13, 12)
    em.jcc_rel32(0x83, "rj_l1d")
    em.mov_rd_mem(0, 3, 16, index=13, scale=8)      # elem
    em.mov_rd_mem(1, 0, 8)
    em.add_rr(14, 1)
    em.inc_r(13)
    em.jcc_rel32(None, "rj_l1")
    em.label_here("rj_l1d")
    em.mov_rr(7, 14)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_mem_r(0, 8, 14)
    em.mov_rr(15, 0)                                # r15=obj
    em.lea_mem(7, 15, 16)
    em.xor_rr32(13, 13)
    em.label_here("rj_l2")
    em.cmp_rr(13, 12)
    em.jcc_rel32(0x83, "rj_l2d")
    em.mov_rd_mem(0, 3, 16, index=13, scale=8)
    em.mov_rd_mem(1, 0, 8)
    em.lea_mem(6, 0, 16)
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.inc_r(13)
    em.jcc_rel32(None, "rj_l2")
    em.label_here("rj_l2d")
    em.mov_rr(0, 15)
    em.emit(b"\x48\x83\xC4\x28")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")
    em.emit(b"\x5D\xC3")


def _emit_re_append_cp(em):
    """re_append_cp(rdi=list, rax=cp) → rax=list'（把单码点文本追加到 list）。"""
    em.label_here("re_append_cp")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")
    em.emit(b"\x48\x83\xEC\x28")
    em.mov_rr(12, 7)                                # list
    em.mov_rr(13, 0)                                # cp
    em.mov_r_imm32(7, 24)
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_rr(3, 0)                                 # obj
    em.lea_mem(7, 3, 16)
    em.mov_rr(0, 13)
    em.call_rel32("re_enc_cp")
    em.mov_rr(0, 7)
    em.lea_mem(1, 3, 16)
    em.sub_rr(0, 1)
    em.mov_mem_r(3, 8, 0)                           # [obj+8]=len
    em.mov_rr(0, 12)
    em.mov_rr(1, 3)
    em.call_rel32("list_append")
    em.emit(b"\x48\x83\xC4\x28")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")
    em.emit(b"\x5D\xC3")


def _emit_re_expand_into(em):
    """re_expand_into(rdi=out list) → rax=out'：把替换串展开后追加到 list。

    对齐 regexlib._expand_repl：\\1..\\99、\\0、\\g<名>、\\k<名>、$1..、\\n\\r\\t\\\\，
    未识别转义去反斜杠保留字符。寄存器：rbx=i、r12=out、r13=runstart、r14=rlen、
    r15=num/gi。局部：-0x58=j、-0x60=cnt、-0x68=ns、-0x70=ne、-0x78=next_i、
    -0x80=t、-0x88=k、-0x90=close。
    """
    L_j = -0x58
    L_cnt = -0x60
    L_ns = -0x68
    L_ne = -0x70
    L_nxt = -0x78
    L_t = -0x80
    L_k = -0x88
    L_close = -0x90

    def flush():
        l_done = _uid("xe_fd")
        em.cmp_rr(13, 3)
        em.jcc_rel32(0x83, l_done)
        em.mov_rr(6, 13)
        em.mov_rr(2, 3)
        em.lea_rip(7, "re_repl_cp")
        em.call_rel32("re_cp_slice")
        em.mov_rr(1, 0)
        em.mov_rr(0, 12)
        em.call_rel32("list_append")
        em.mov_rr(12, 0)
        em.label_here(l_done)
        em.mov_rr(13, 3)

    def app_group():
        l_zero = _uid("xe_az")
        l_nn = _uid("xe_ann")
        l_done = _uid("xe_ad")
        em.load_rip_to(0, "re_ngroups")
        em.cmp_rr(15, 0)
        em.jcc_rel32(0x87, l_zero)
        em.mov_rr(1, 15)
        em.add_rr(1, 15)
        em.lea_rip(8, "re_caps")
        em.mov_rd_mem(6, 8, 0, index=1, scale=8)
        em.mov_rd_mem(2, 8, 8, index=1, scale=8)
        em.cmp_ri(6, -1)
        em.jcc_rel32(0x85, l_nn)
        em.xor_rr32(6, 6)
        em.xor_rr32(2, 2)
        em.label_here(l_nn)
        em.lea_rip(7, "re_subj_cp")
        em.call_rel32("re_cp_slice")
        em.jcc_rel32(None, l_done)
        em.label_here(l_zero)
        em.xor_rr32(6, 6)
        em.xor_rr32(2, 2)
        em.lea_rip(7, "re_subj_cp")
        em.call_rel32("re_cp_slice")
        em.label_here(l_done)
        em.mov_rr(1, 0)
        em.mov_rr(0, 12)
        em.call_rel32("list_append")
        em.mov_rr(12, 0)

    em.label_here("re_expand_into")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")
    em.emit(b"\x48\x83\xEC\x78")
    em.mov_rr(12, 7)
    em.xor_rr32(3, 3)
    em.xor_rr32(13, 13)
    em.load_rip_to(14, "re_rlen")

    em.label_here("xe_loop")
    em.cmp_rr(3, 14)
    em.jcc_rel32(0x83, "xe_tail")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=3, scale=8)        # c
    em.cmp_ri(0, 0x5C)                              # '\\'
    em.jcc_rel32(0x85, "xe_dollar")
    em.mov_rr(1, 3)
    em.inc_r(1)
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x83, "xe_plain")                  # 结尾反斜杠：当字面
    em.mov_rd_mem(15, 8, 0, index=1, scale=8)       # nx
    em.cmp_ri(15, 0x30)
    em.jcc_rel32(0x82, "xe_gk")
    em.cmp_ri(15, 0x39)
    em.jcc_rel32(0x87, "xe_gk")
    em.jcc_rel32(None, "xe_num")

    em.label_here("xe_dollar")
    em.cmp_ri(0, 0x24)                              # '$'
    em.jcc_rel32(0x85, "xe_plain")
    em.mov_rr(1, 3)
    em.inc_r(1)
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x83, "xe_plain")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)
    em.cmp_ri(0, 0x30)
    em.jcc_rel32(0x82, "xe_plain")
    em.cmp_ri(0, 0x39)
    em.jcc_rel32(0x87, "xe_plain")

    em.label_here("xe_num")
    flush()
    em.xor_rr32(15, 15)
    em.mov_rr(1, 3)
    em.inc_r(1)
    em.mov_mem_r(5, L_j, 1)
    em.mov_r_imm32(0, 0)
    em.mov_mem_r(5, L_cnt, 0)
    l_dig = _uid("xe_dg")
    l_digd = _uid("xe_dgd")
    em.label_here(l_dig)
    em.mov_rd_mem(1, 5, L_j)
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x83, l_digd)
    em.mov_rd_mem(0, 5, L_cnt)
    em.cmp_ri(0, 2)
    em.jcc_rel32(0x83, l_digd)
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)
    em.cmp_ri(0, 0x30)
    em.jcc_rel32(0x82, l_digd)
    em.cmp_ri(0, 0x39)
    em.jcc_rel32(0x87, l_digd)
    em.mov_rr(2, 15)
    em.shl_ri(15, 3)
    em.add_rr(15, 2)
    em.add_rr(15, 2)
    em.and_ri(0, 0x0F)
    em.add_rr(15, 0)
    em.mov_rd_mem(1, 5, L_j)
    em.inc_r(1)
    em.mov_mem_r(5, L_j, 1)
    em.mov_rd_mem(0, 5, L_cnt)
    em.inc_r(0)
    em.mov_mem_r(5, L_cnt, 0)
    em.jcc_rel32(None, l_dig)
    em.label_here(l_digd)
    em.mov_rd_mem(3, 5, L_j)
    app_group()
    em.mov_rr(13, 3)
    em.jcc_rel32(None, "xe_loop")

    em.label_here("xe_gk")
    em.cmp_ri(15, 0x67)                             # 'g'
    em.jcc_rel32(0x84, "xe_gk2")
    em.cmp_ri(15, 0x6B)                             # 'k'
    em.jcc_rel32(0x85, "xe_simple")
    em.label_here("xe_gk2")
    em.mov_rr(1, 3)
    em.add_ri(1, 2)
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x83, "xe_simple")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)        # op
    em.cmp_ri(0, 0x3C)                              # '<'
    em.jcc_rel32(0x84, "xe_gk_open")
    em.cmp_ri(0, 0x7B)                              # '{'
    em.jcc_rel32(0x84, "xe_gk_open")
    em.cmp_ri(0, 0x27)                              # '\''
    em.jcc_rel32(0x85, "xe_simple")
    em.label_here("xe_gk_open")
    em.mov_mem_r(5, L_close, 0)
    em.cmp_ri(0, 0x3C)
    em.jcc_rel32(0x84, "xe_gk_open_lt")
    em.cmp_ri(0, 0x7B)
    em.jcc_rel32(0x84, "xe_gk_open_br")
    em.jcc_rel32(None, "xe_gk_scan")
    em.label_here("xe_gk_open_lt")
    em.mov_r_imm32(1, 0x3E)
    em.mov_mem_r(5, L_close, 1)
    em.jcc_rel32(None, "xe_gk_scan")
    em.label_here("xe_gk_open_br")
    em.mov_r_imm32(1, 0x7D)
    em.mov_mem_r(5, L_close, 1)
    em.label_here("xe_gk_scan")
    em.mov_rr(1, 3)
    em.add_ri(1, 3)
    em.mov_mem_r(5, L_ns, 1)
    em.label_here("xe_gk_sloop")
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x83, "xe_gk_sdone")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)
    em.mov_rd_mem(2, 5, L_close)
    em.cmp_rr(0, 2)
    em.jcc_rel32(0x84, "xe_gk_sdone")
    em.inc_r(1)
    em.jcc_rel32(None, "xe_gk_sloop")
    em.label_here("xe_gk_sdone")
    em.mov_mem_r(5, L_ne, 1)
    em.mov_rr(0, 1)
    em.cmp_rr(1, 14)
    em.jcc_rel32(0x82, "xe_gk_consume")
    em.jcc_rel32(None, "xe_gk_noconsume")
    em.label_here("xe_gk_consume")
    em.inc_r(0)
    em.label_here("xe_gk_noconsume")
    em.mov_mem_r(5, L_nxt, 0)
    # 判定 name 是否全数字
    em.mov_rd_mem(1, 5, L_ns)
    em.mov_rd_mem(2, 5, L_ne)
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x83, "xe_gk_lookup")
    em.label_here("xe_gk_ndloop")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)
    em.cmp_ri(0, 0x30)
    em.jcc_rel32(0x82, "xe_gk_lookup")
    em.cmp_ri(0, 0x39)
    em.jcc_rel32(0x87, "xe_gk_lookup")
    em.inc_r(1)
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x82, "xe_gk_ndloop")
    em.xor_rr32(15, 15)
    em.mov_rd_mem(1, 5, L_ns)
    em.label_here("xe_gk_idloop")
    em.mov_rd_mem(2, 5, L_ne)
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x83, "xe_gk_gotgi")
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(0, 8, 0, index=1, scale=8)
    em.and_ri(0, 0x0F)
    em.mov_rr(2, 15)
    em.shl_ri(15, 3)
    em.add_rr(15, 2)
    em.add_rr(15, 2)
    em.add_rr(15, 0)
    em.inc_r(1)
    em.jcc_rel32(None, "xe_gk_idloop")
    em.label_here("xe_gk_lookup")
    em.mov_r_imm32(15, 0x7FFFFFFF)
    em.mov_r_imm32(0, 0)
    em.mov_mem_r(5, L_t, 0)
    em.label_here("xe_gk_tloop")
    em.load_rip_to(0, "re_name_n")
    em.mov_rd_mem(1, 5, L_t)
    em.cmp_rr(1, 0)
    em.jcc_rel32(0x83, "xe_gk_gotgi")
    em.lea_rip(8, "re_name_b")
    em.mov_rd_mem(2, 8, 0, index=1, scale=8)
    em.lea_rip(8, "re_name_e")
    em.mov_rd_mem(9, 8, 0, index=1, scale=8)
    em.mov_rr(0, 9)
    em.sub_rr(0, 2)
    em.mov_rd_mem(6, 5, L_ne)
    em.mov_rd_mem(7, 5, L_ns)
    em.sub_rr(6, 7)
    em.cmp_rr(0, 6)
    em.jcc_rel32(0x85, "xe_gk_tnext")
    em.mov_r_imm32(0, 0)
    em.mov_mem_r(5, L_k, 0)
    em.label_here("xe_gk_cmp")
    em.mov_rd_mem(1, 5, L_k)
    em.mov_rd_mem(2, 5, L_ne)
    em.mov_rd_mem(7, 5, L_ns)
    em.sub_rr(2, 7)
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x83, "xe_gk_found")
    em.mov_rd_mem(0, 5, L_ns)
    em.add_rr(0, 1)
    em.lea_rip(8, "re_repl_cp")
    em.mov_rd_mem(9, 8, 0, index=0, scale=8)
    em.mov_rd_mem(0, 5, L_t)
    em.lea_rip(8, "re_name_b")
    em.mov_rd_mem(6, 8, 0, index=0, scale=8)
    em.add_rr(6, 1)
    em.lea_rip(8, "re_pat_cp")
    em.mov_rd_mem(7, 8, 0, index=6, scale=8)
    em.cmp_rr(9, 7)
    em.jcc_rel32(0x85, "xe_gk_tnext")
    em.mov_rd_mem(1, 5, L_k)
    em.inc_r(1)
    em.mov_mem_r(5, L_k, 1)
    em.jcc_rel32(None, "xe_gk_cmp")
    em.label_here("xe_gk_found")
    em.mov_rd_mem(0, 5, L_t)
    em.lea_rip(8, "re_name_gi")
    em.mov_rd_mem(15, 8, 0, index=0, scale=8)
    em.jcc_rel32(None, "xe_gk_gotgi")
    em.label_here("xe_gk_tnext")
    em.mov_rd_mem(0, 5, L_t)
    em.inc_r(0)
    em.mov_mem_r(5, L_t, 0)
    em.jcc_rel32(None, "xe_gk_tloop")
    em.label_here("xe_gk_gotgi")
    flush()
    app_group()
    em.mov_rd_mem(3, 5, L_nxt)
    em.mov_rr(13, 3)
    em.jcc_rel32(None, "xe_loop")

    em.label_here("xe_plain")
    em.inc_r(3)
    em.jcc_rel32(None, "xe_loop")

    em.label_here("xe_simple")
    em.cmp_ri(15, 0x6E)
    em.jcc_rel32(0x84, "xe_sn")
    em.cmp_ri(15, 0x72)
    em.jcc_rel32(0x84, "xe_sr")
    em.cmp_ri(15, 0x74)
    em.jcc_rel32(0x84, "xe_st")
    em.cmp_ri(15, 0x5C)
    em.jcc_rel32(0x84, "xe_sb")
    em.jcc_rel32(None, "xe_sflush")
    em.label_here("xe_sn")
    em.mov_r_imm32(15, 10)
    em.jcc_rel32(None, "xe_sflush")
    em.label_here("xe_sr")
    em.mov_r_imm32(15, 13)
    em.jcc_rel32(None, "xe_sflush")
    em.label_here("xe_st")
    em.mov_r_imm32(15, 9)
    em.jcc_rel32(None, "xe_sflush")
    em.label_here("xe_sb")
    em.mov_r_imm32(15, 0x5C)
    em.label_here("xe_sflush")
    flush()
    em.mov_rr(0, 15)
    em.mov_rr(7, 12)
    em.call_rel32("re_append_cp")
    em.mov_rr(12, 0)
    em.add_ri(3, 2)
    em.mov_rr(13, 3)
    em.jcc_rel32(None, "xe_loop")

    em.label_here("xe_tail")
    flush()
    em.mov_rr(0, 12)
    em.emit(b"\x48\x83\xC4\x78")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")
    em.emit(b"\x5D\xC3")
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
    _emit_re_bt_try(em)
    _emit_re_search(em)
    _emit_re_enc_cp(em)
    _emit_re_cp_slice(em)
    _emit_re_cap_slice(em)
    _emit_re_mk_match_list(em)
    _emit_re_join(em)
    _emit_re_append_cp(em)
    _emit_re_expand_into(em)


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
    em.xor_rr32(7, 7)                               # from=0
    em.mov_r_imm32(6, mode)                         # require_end = mode
    em.call_rel32("re_search")
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


def _emit_re_prelude(em, re_off=-16, s_off=-8):
    """公共：解码 pattern→re_pat_cp/re_plen、subject→re_subj_cp/re_slen 并编译。

    形参偏移由调用方按 nlocals 给出（arity2：-16/-8；arity3：-24/-8）。
    """
    em.mov_rd_mem(7, 5, re_off)                     # rdi=[rbp+re_off]（pat）
    em.call_rel32("re_check_str")                   # rax=payload, rdx=字节长
    em.mov_rr(6, 2)
    em.mov_rr(7, 0)
    em.lea_rip(2, "re_pat_cp")
    em.call_rel32("re_utf8_decode")
    em.store_rip_from("re_plen", 0)
    em.mov_rd_mem(7, 5, s_off)                      # rdi=[rbp+s_off]（subj）
    em.call_rel32("re_check_str")
    em.mov_rr(6, 2)
    em.mov_rr(7, 0)
    em.lea_rip(2, "re_subj_cp")
    em.call_rel32("re_utf8_decode")
    em.store_rip_from("re_slen", 0)
    em.load_rip_to(7, "re_plen")
    em.call_rel32("re_compile")


def _emit_new_list(em, dst):
    """dst = 新建空列表（rax 为返回对象）。"""
    em.mov_r_imm32(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_r_imm32(1, 0)
    em.mov_mem_r(0, 8, 1)
    em.mov_rr(dst, 0)


def _emit_builtin_regex_find(em):
    """查找正则(pat)(s) → [g0..gn] 或 null。"""
    em.label_here("fn:查找正则")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_re_prelude(em)
    em.xor_rr32(7, 7)
    em.xor_rr32(6, 6)
    em.call_rel32("re_search")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "rg_fd_null")
    em.call_rel32("re_mk_match_list")
    em.jcc_rel32(None, "rg_fd_done")
    em.label_here("rg_fd_null")
    em.lea_rip(0, "null_obj")
    em.label_here("rg_fd_done")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_builtin_regex_findall(em):
    """查找全部(pat)(s) → [[g0..gn], ...]。"""
    em.label_here("fn:查找全部")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_re_prelude(em)
    _emit_new_list(em, 3)                           # rbx=out
    em.xor_rr32(13, 13)                             # r13=i
    em.label_here("rg_fa_loop")
    em.load_rip_to(14, "re_slen")
    em.cmp_rr(13, 14)
    em.jcc_rel32(0x87, "rg_fa_done")                   # i > slen
    em.mov_rr(7, 13)
    em.xor_rr32(6, 6)
    em.call_rel32("re_search")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "rg_fa_done")
    em.call_rel32("re_mk_match_list")
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    em.mov_rr(3, 0)                                 # out=rax
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(15, 8, 8)                          # end=caps[1]
    em.cmp_rr(15, 13)
    em.jcc_rel32(0x85, "rg_fa_next")                   # end != i：i=end
    em.inc_r(15)                                    # 空匹配：i=end+1
    em.label_here("rg_fa_next")
    em.mov_rr(13, 15)
    em.jcc_rel32(None, "rg_fa_loop")
    em.label_here("rg_fa_done")
    em.mov_rr(0, 3)
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_builtin_regex_named(em):
    """命名组(pat)(s) → {名: 文本或 null} 或 null。"""
    em.label_here("fn:命名组")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_re_prelude(em)
    em.xor_rr32(7, 7)
    em.xor_rr32(6, 6)
    em.call_rel32("re_search")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "rg_nm_null")
    em.lea_rip(3, "empty_dict")                     # rbx=dict
    em.xor_rr32(13, 13)                             # r13=t
    em.label_here("rg_nm_loop")
    em.load_rip_to(14, "re_name_n")
    em.cmp_rr(13, 14)
    em.jcc_rel32(0x83, "rg_nm_done")
    em.lea_rip(8, "re_name_b")
    em.mov_rd_mem(6, 8, 0, index=13, scale=8)        # b
    em.lea_rip(8, "re_name_e")
    em.mov_rd_mem(2, 8, 0, index=13, scale=8)        # e
    em.lea_rip(7, "re_pat_cp")
    em.call_rel32("re_cp_slice")                     # rax=key
    em.mov_rr(15, 0)                                 # r15=key
    em.lea_rip(8, "re_name_gi")
    em.mov_rd_mem(7, 8, 0, index=13, scale=8)        # gi
    em.call_rel32("re_cap_slice")                    # rax=val
    em.mov_rr(2, 0)                                  # rdx=val
    em.mov_rr(1, 15)                                 # rcx=key
    em.mov_rr(0, 3)                                  # rax=dict
    em.call_rel32("dict_put")
    em.mov_rr(3, 0)                                  # dict=rax
    em.inc_r(13)
    em.jcc_rel32(None, "rg_nm_loop")
    em.label_here("rg_nm_done")
    em.mov_rr(0, 3)
    em.jcc_rel32(None, "rg_nm_ret")
    em.label_here("rg_nm_null")
    em.lea_rip(0, "null_obj")
    em.label_here("rg_nm_ret")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_builtin_regex_split(em):
    """分割正则(pat)(s) → [文本, 组1, ..., 组n, 文本, ...]。"""
    em.label_here("fn:分割正则")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_re_prelude(em)
    _emit_new_list(em, 3)                           # rbx=parts
    em.xor_rr32(13, 13)                             # r13=i
    em.xor_rr32(14, 14)                             # r14=last
    em.label_here("rg_sp_loop")
    em.load_rip_to(15, "re_slen")
    em.cmp_rr(13, 15)
    em.jcc_rel32(0x87, "rg_sp_tail")
    em.mov_rr(7, 13)
    em.xor_rr32(6, 6)
    em.call_rel32("re_search")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "rg_sp_tail")
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(6, 8, 0)                           # start=caps[0]
    em.mov_rr(2, 6)                                  # rdx=start
    em.mov_rr(6, 14)                                 # rsi=last
    em.lea_rip(7, "re_subj_cp")
    em.call_rel32("re_cp_slice")
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    em.mov_rr(3, 0)
    em.mov_r_imm32(15, 1)                            # gi=1
    em.label_here("rg_sp_grp")
    em.load_rip_to(0, "re_ngroups")
    em.cmp_rr(15, 0)
    em.jcc_rel32(0x87, "rg_sp_grpd")                    # gi > ngroups
    em.mov_rr(7, 15)
    em.call_rel32("re_cap_slice")                    # str 或 null
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    em.mov_rr(3, 0)
    em.inc_r(15)
    em.jcc_rel32(None, "rg_sp_grp")
    em.label_here("rg_sp_grpd")
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(15, 8, 8)                          # end
    em.mov_rr(14, 15)                                # last=end
    em.cmp_rr(15, 13)
    em.jcc_rel32(0x85, "rg_sp_next")
    em.inc_r(15)
    em.label_here("rg_sp_next")
    em.mov_rr(13, 15)
    em.jcc_rel32(None, "rg_sp_loop")
    em.label_here("rg_sp_tail")
    em.load_rip_to(2, "re_slen")
    em.mov_rr(6, 14)
    em.lea_rip(7, "re_subj_cp")
    em.call_rel32("re_cp_slice")
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_builtin_regex_sub(em):
    """替换正则(pat)(repl)(s) → 文本。"""
    em.label_here("fn:替换正则")
    _EMIT_PROLOGUE(em, 3, 3)
    _save(em)
    _emit_re_prelude(em, re_off=-24, s_off=-8)
    em.mov_rd_mem(7, 5, -16)                         # rdi=repl
    em.call_rel32("re_check_str")
    em.mov_rr(6, 2)
    em.mov_rr(7, 0)
    em.lea_rip(2, "re_repl_cp")
    em.call_rel32("re_utf8_decode")
    em.store_rip_from("re_rlen", 0)
    _emit_new_list(em, 3)                            # rbx=out
    em.xor_rr32(13, 13)                              # r13=i
    em.xor_rr32(14, 14)                              # r14=last
    em.label_here("rg_sb_loop")
    em.load_rip_to(15, "re_slen")
    em.cmp_rr(13, 15)
    em.jcc_rel32(0x87, "rg_sb_tail")
    em.mov_rr(7, 13)
    em.xor_rr32(6, 6)
    em.call_rel32("re_search")
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "rg_sb_tail")
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(6, 8, 0)                           # start
    em.mov_rr(2, 6)                                  # rdx=start
    em.mov_rr(6, 14)                                 # rsi=last
    em.lea_rip(7, "re_subj_cp")
    em.call_rel32("re_cp_slice")
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    em.mov_rr(3, 0)
    em.mov_rr(7, 3)
    em.call_rel32("re_expand_into")                  # rax=out'
    em.mov_rr(3, 0)
    em.lea_rip(8, "re_caps")
    em.mov_rd_mem(15, 8, 8)                          # end
    em.mov_rr(14, 15)                                # last=end
    em.cmp_rr(15, 13)
    em.jcc_rel32(0x85, "rg_sb_next")
    em.inc_r(15)
    em.label_here("rg_sb_next")
    em.mov_rr(13, 15)
    em.jcc_rel32(None, "rg_sb_loop")
    em.label_here("rg_sb_tail")
    em.load_rip_to(2, "re_slen")
    em.mov_rr(6, 14)
    em.lea_rip(7, "re_subj_cp")
    em.call_rel32("re_cp_slice")
    em.mov_rr(1, 0)
    em.mov_rr(0, 3)
    em.call_rel32("list_append")
    em.mov_rr(7, 0)
    em.call_rel32("re_join")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


# ---------------------------------------------------------------- 数据/BSS
_SCALARS = [
    "re_pat_i", "re_plen", "re_pc", "re_prog_len", "re_class_len",
    "re_gen", "re_pos", "re_cn", "re_nn", "re_k", "re_mode", "re_slen",
    "re_ngroups", "re_name_n", "re_rlen",
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
                    ("re_subj_cp", SUBJ_CP_MAX),
                    ("re_repl_cp", PAT_CP_MAX),
                    ("re_caps", CAPS),
                    ("re_undo_slot", UNDO_MAX),
                    ("re_undo_val", UNDO_MAX),
                    ("re_bt_pc", BT_MAX),
                    ("re_bt_pos", BT_MAX),
                    ("re_bt_ul", BT_MAX),
                    ("re_bt_lsp", BT_MAX),
                    ("re_lstack", LOOP_MAX),
                    ("re_name_gi", NAME_MAX),
                    ("re_name_b", NAME_MAX),
                    ("re_name_e", NAME_MAX)):
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
