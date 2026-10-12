"""原生正则引擎（阶段 A：字面量模式 + 元字符检测）。

背景
====
解释器（src/interp.py）与 M3V VM（src/mbc/vm.py）复用 src/regexlib.py 的纯
Python 回溯引擎；原生后端（src/mbc/native.py）发射独立 PE，无法回调 Python，
故需自带引擎。完整 PCRE 风格原生引擎分多轮构建：

  阶段 A（本模块当前范围）——**字面量模式**：
    - `匹配(re)(s)`：是否包含；`全匹配(re)(s)`：是否整体相等。
    - 模式若含元字符（. ^ $ * + ? { } [ ] ( ) | \\），运行期以明确错误中止，
      而非按字面量误匹配（避免静默错误答案）。
  阶段 B（后续）——模式解析 + 显式回溯 VM：元字符 / 字符类 / 量词 / 分组 /
    交替 / 锚点。阶段 C——环视 / 反向引用 / 命名组 / 内联标志 / 全部内建。

原生字符串布局：`[TYPE_STR][+8]=字节长][+16..]=UTF-8 字节`（见 native.py）。
本阶段的字面量匹配按**字节**比较（ASCII 下等价于码点）。
"""
from __future__ import annotations

import struct

TYPE_STR = 1
TYPE_LIST = 2

# 由 native.py 在定义 _emit_prologue/_emit_epilogue 之后注入（避免循环导入）。
_EMIT_PROLOGUE = None
_EMIT_EPILOGUE = None


def configure(prologue, epilogue):
    """注入 native.py 的 _emit_prologue/_emit_epilogue（见 native.py 尾部调用）。"""
    global _EMIT_PROLOGUE, _EMIT_EPILOGUE
    _EMIT_PROLOGUE = prologue
    _EMIT_EPILOGUE = epilogue


# 正则元字符（阶段 A 视为「引擎尚未支持的构造」）
RE_META_BYTES = b".^$*+?{}[]()|\\"

ERR_NOTSTR = "原生正则：需要字符串参数（阶段 A 仅支持字面量模式）"
ERR_META = "原生正则：暂不支持元字符模式（原生引擎构建中，仅字面量模式可用）"


# ---------------------------------------------------------------- 寄存器保存
def _save(em):
    """保存本内建用到的被调用者保存寄存器。

    压入 6 个字（rbx,r12,r13,r14,r15,rbp）共 48 字节，保持 16 字节栈对齐：
    本内建会在体内直接 `call raise_rt`（元字符错误），而 raise_rt 依赖入口
    rsp≡8(mod16) 才能让 value_to_str 的 SSE 对齐访问成立。若只压奇数个寄存器
    会破坏对齐，导致抛出时访问违例。
    """
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12;r13;r14;r15
    em.emit(b"\x55")                                # push rbp（凑偶，仅占位）


def _restore(em):
    em.emit(b"\x5D")                                # pop rbp（占位）
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15;r14;r13;r12
    em.emit(b"\x5B")                                # pop rbx


def _ud2(em):
    em.emit(b"\x0F\x0B")                            # ud2（不可达保险）


# ---------------------------------------------------------------- 运行时原语
def _emit_re_check_str(em):
    """re_check_str(rdi=obj) → rax=payload, rdx=字节长；非 STR 抛错（不返回）。"""
    em.label_here("re_check_str")
    em.mov_rr(1, 7)                                 # mov rcx,rdi
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.sub_rr(1, 2)                                 # rcx = obj - heap_base
    em.cmp_heap_used(1)                             # cmp rcx,[heap_used]
    em.jcc_rel32(0x82, "rcs_ok")                    # jb：落在堆区间内
    em.jcc_rel32(None, "rcs_bad")
    em.label_here("rcs_ok")
    em.mov_rd_mem(1, 7, 0)                           # rcx = [rdi]（类型）
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, "rcs_bad")                    # jne 非字符串
    em.mov_rd_mem(2, 7, 8)                           # rdx = [rdi+8]（长度）
    em.mov_rr(0, 7)
    em.add_ri(0, 16)                                 # rax = payload
    em.emit(b"\xC3")                                 # ret
    em.label_here("rcs_bad")
    em.lea_rip(0, "re_err_notstr_msg")
    em.call_rel32("raise_rt")                        # 永不返回
    _ud2(em)


def _emit_re_has_meta(em):
    """re_has_meta(rdi=pat payload, rsi=plen) → rax=1 含元字符 / 0 纯字面量。"""
    em.label_here("re_has_meta")
    em.lea_rip(8, "re_meta_tab")                     # r8 = 元字符查表
    em.xor_rr32(9, 9)                                # r9 = i = 0
    em.label_here("rhm_loop")
    em.cmp_rr(9, 6)                                  # cmp r9,rsi
    em.jcc_rel32(0x83, "rhm_none")                   # jae：越界 → 无
    em.mov_rr(10, 7)
    em.add_rr(10, 9)                                 # r10 = pat + i
    em.movzx_r_m8(11, 10, 0)                         # r11d = pat[i]
    em.mov_rr(10, 8)
    em.add_rr(10, 11)                                # r10 = tab + byte
    em.movzx_r_m8(10, 10, 0)                          # r10d = tab[byte]
    em.test_rr(10, 10)
    em.jcc_rel32(0x85, "rhm_yes")
    em.inc_r(9)
    em.jcc_rel32(None, "rhm_loop")
    em.label_here("rhm_none")
    em.xor_rr32(0, 0)
    em.emit(b"\xC3")
    em.label_here("rhm_yes")
    em.mov_r_imm32(0, 1)
    em.emit(b"\xC3")


def _emit_re_match_at(em):
    """re_lit_match_at(rdi=hay,rsi=hlen,rdx=nee,rcx=nlen,r8=idx) → rax=end/-1。

    若 hay[idx:idx+nlen] == nee[0:nlen] 返回 idx+nlen，否则 -1（nlen=0 时恒返回 idx）。
    """
    em.label_here("re_lit_match_at")
    em.mov_rr(0, 8)                                  # rax = idx
    em.add_rr(0, 1)                                  # rax = idx + nlen
    em.cmp_rr(0, 6)                                  # cmp rax,hlen
    em.jcc_rel32(0x87, "rma_fail")                   # ja：越界
    em.xor_rr32(9, 9)                                # r9 = k = 0
    em.label_here("rma_loop")
    em.cmp_rr(9, 1)                                  # cmp k,nlen
    em.jcc_rel32(0x83, "rma_ok")                     # jae：全部相等
    em.mov_rr(10, 7)                                 # r10 = hay
    em.add_rr(10, 8)                                 # + idx
    em.add_rr(10, 9)                                 # + k
    em.movzx_r_m8(11, 10, 0)                         # r11d = hay[idx+k]
    em.mov_rr(10, 2)
    em.add_rr(10, 9)                                 # r10 = nee+k
    em.movzx_r_m8(10, 10, 0)                         # r10d = nee[k]
    em.cmp_rr(11, 10)
    em.jcc_rel32(0x85, "rma_fail")                   # jne
    em.inc_r(9)
    em.jcc_rel32(None, "rma_loop")
    em.label_here("rma_ok")
    em.mov_rr(0, 8)
    em.add_rr(0, 1)                                  # rax = idx+nlen
    em.emit(b"\xC3")
    em.label_here("rma_fail")
    em.mov_rax_imm64(-1)
    em.emit(b"\xC3")


def _emit_re_search(em):
    """re_lit_search(rdi=hay,rsi=hlen,rdx=nee,rcx=nlen,r8=from) → rax=start/-1。"""
    em.label_here("re_lit_search")
    em.emit(b"\x53")                                 # push rbx
    em.mov_rr(3, 8)                                  # rbx = from
    em.label_here("rls_loop")
    em.cmp_rr(3, 6)                                  # cmp idx,hlen
    em.jcc_rel32(0x87, "rls_none")                   # ja
    em.mov_rr(8, 3)
    em.call_rel32("re_lit_match_at")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x85, "rls_found")                  # jne：命中
    em.inc_r(3)
    em.jcc_rel32(None, "rls_loop")
    em.label_here("rls_found")
    em.mov_rr(0, 3)
    em.emit(b"\x5B\xC3")                             # pop rbx; ret
    em.label_here("rls_none")
    em.mov_rax_imm64(-1)
    em.emit(b"\x5B\xC3")


def _emit_re_runtime(em):
    """发射全部原生正则运行时原语（阶段 A）。"""
    _emit_re_check_str(em)
    _emit_re_has_meta(em)
    _emit_re_match_at(em)
    _emit_re_search(em)


# ---------------------------------------------------------------- 内建函数体
def _emit_regex_common_prefix(em, tag):
    """公共前导：校验 pat/subj 为字符串、检测元字符。

    约定局部槽（nlocals=2）：pat=[rbp-16]，subj=[rbp-8]。
    成功返回：r14=pat payload，r15=plen，rbx=subj payload，r13=slen。
    元字符模式 → 抛出 ERR_META（不返回）。
    """
    em.emit(b"\x48\x8B\xBD\xF0\xFF\xFF\xFF")         # mov rdi,[rbp-16]（pat）
    em.call_rel32("re_check_str")
    em.mov_rr(14, 0)                                 # r14 = pat payload
    em.mov_rr(15, 2)                                 # r15 = plen
    em.emit(b"\x48\x8B\xBD\xF8\xFF\xFF\xFF")         # mov rdi,[rbp-8]（subj）
    em.call_rel32("re_check_str")
    em.mov_rr(3, 0)                                  # rbx = subj payload
    em.mov_rr(13, 2)                                 # r13 = slen
    em.mov_rr(7, 14)
    em.mov_rr(6, 15)
    em.call_rel32("re_has_meta")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, f"{tag}_meta")                # 含元字符 → 抛错
    return


def _emit_builtin_regex_match(em):
    """匹配(re)(s) → 布尔（字面量包含，阶段 A）。"""
    em.label_here("fn:匹配")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_regex_common_prefix(em, "reb_match")
    em.mov_rr(7, 3)                                  # rdi = subj
    em.mov_rr(6, 13)                                 # rsi = slen
    em.mov_rr(2, 14)                                 # rdx = pat
    em.mov_rr(1, 15)                                 # rcx = plen
    em.xor_rr32(8, 8)                                # from = 0
    em.call_rel32("re_lit_search")
    em.cmp_ri(0, -1)
    em.jcc_rel32(0x85, "reb_match_true")             # 命中 → true
    em.lea_rip(0, "bool_false")
    em.jcc_rel32(None, "reb_match_done")
    em.label_here("reb_match_true")
    em.lea_rip(0, "bool_true")
    em.label_here("reb_match_done")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)
    em.label_here("reb_match_meta")
    em.lea_rip(0, "re_err_meta_msg")
    em.call_rel32("raise_rt")
    _ud2(em)


def _emit_builtin_regex_fullmatch(em):
    """全匹配(re)(s) → 布尔（字面量整体相等，阶段 A）。"""
    em.label_here("fn:全匹配")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    _emit_regex_common_prefix(em, "reb_full")
    em.mov_rr(7, 3)                                  # rdi = subj
    em.mov_rr(6, 13)                                 # rsi = slen
    em.mov_rr(2, 14)                                 # rdx = pat
    em.mov_rr(1, 15)                                 # rcx = plen
    em.xor_rr32(8, 8)                                # idx = 0
    em.call_rel32("re_lit_match_at")
    em.cmp_rr(0, 13)                                 # end == slen ?
    em.jcc_rel32(0x85, "reb_full_false")             # 不等（含 -1）→ false
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, "reb_full_done")
    em.label_here("reb_full_false")
    em.lea_rip(0, "bool_false")
    em.label_here("reb_full_done")
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)
    em.label_here("reb_full_meta")
    em.lea_rip(0, "re_err_meta_msg")
    em.call_rel32("raise_rt")
    _ud2(em)


# ---------------------------------------------------------------- 数据节
def emit_regex_data(ed):
    """发射正则引擎的静态数据（元字符查表 + 错误消息串）。"""
    table = bytearray(256)
    for b in RE_META_BYTES:
        table[b] = 1
    ed.align(64)
    ed.label_here("re_meta_tab")
    ed.emit(bytes(table))
    for lbl, text in (("re_err_notstr_msg", ERR_NOTSTR),
                      ("re_err_meta_msg", ERR_META)):
        raw = text.encode("utf-8")
        ed.align(8)
        ed.label_here(lbl)
        ed.emit(struct.pack("<Q", TYPE_STR))
        ed.emit(struct.pack("<Q", len(raw)))
        ed.emit(raw)
        ed.align(8)
