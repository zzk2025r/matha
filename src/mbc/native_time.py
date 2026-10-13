r"""原生日期时间后端（阶段：纯函数）。

为 M3V 原生后端提供 time_module 中**纯函数**的原生实现（无副作用、输入决定
输出），与解释器（src/domains/time_module.py）逐一对齐：

  闰年判断(year) -> bool
  月份天数(year, month) -> int
  时区偏移(name) -> int            （小时，可为负）
  时区转换(ts, from, to) -> int     （UTC 时间戳按两时区差平移，返回秒）
  日期差(d1, d2) -> int             （d2 - d1 的天数）
  星期几(date) -> str               （中文「星期X」）
  日期加减(days, base) -> str       （base 日期平移 days 天，ISO 文本）

日期一律 ISO 8601「YYYY-MM-DD」，用 Howard Hinnant 的 days_from_civil /
civil_from_days 算法在儒略日序列号上运算，避免闰年/月末分支。

非纯函数（获取时间戳/当前日期/格式化时间/解析时间/计时器/任务调度等）依赖
系统时钟与全局状态，暂只由解释器与 VM 提供，原生后端后续补齐。

原生字符串布局：`[TYPE_STR][+8]=字节长][+16..]=UTF-8 字节`。
整数为未装箱立即数（rax 直接返回），布尔为 bool_true/bool_false 指针对象。
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


# 寄存器编号
_RAX, _RCX, _RDX, _RBX, _RSP, _RBP, _RSI, _RDI = range(8)
_R8, _R9, _R10, _R11 = 8, 9, 10, 11

# 中文星期名（索引：0=星期一 … 6=星期日，与 Python date.weekday() 一致）
_WEEKDAY_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

# 时区名 → UTC 偏移小时。同名异写共用偏移；顺序即匹配顺序。
_TZ_ENTRIES = (
    ("tm_tz_UTC", "UTC", 0),
    ("tm_tz_GMT", "GMT", 0),
    ("tm_tz_CST", "CST", 8),
    ("tm_tz_SH", "Asia/Shanghai", 8),
    ("tm_tz_EST", "EST", -5),
    ("tm_tz_NY", "America/New_York", -5),
    ("tm_tz_PST", "PST", -8),
    ("tm_tz_LA", "America/Los_Angeles", -8),
    ("tm_tz_JST", "JST", 9),
    ("tm_tz_TOKYO", "Asia/Tokyo", 9),
    ("tm_tz_CET", "CET", 1),
    ("tm_tz_BERLIN", "Europe/Berlin", 1),
)


# ------------------------------------------------------------ 寄存器保存
def _save(em):
    """压入 6 个字（48 字节）保持 16 字节栈对齐（raise_rt 依赖）。"""
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12;r13;r14;r15
    em.emit(b"\x55")                                # push rbp（占位凑偶）


def _restore(em):
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15;r14;r13;r12
    em.emit(b"\x5B")                                # pop rbx


# ------------------------------------------------------------ 底层字节助手
def _ret(em):
    em.emit(b"\xC3")                                # ret


def _cqo(em):
    em.emit(b"\x48\x99")                            # cqo（rax 符号扩展到 rdx:rax）


def _imul(em, dst, src):
    """imul dst, src（64 位有符号乘，低 64 位）。"""
    rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
    em.emit(bytes([rex, 0x0F, 0xAF, 0xC0 | ((dst & 7) << 3) | (src & 7)]))


def _idiv(em, src):
    """idiv src（64 位有符号除；商在 rax，余数在 rdx）。"""
    rex = 0x48 | (0x01 if src >= 8 else 0)
    em.emit(bytes([rex, 0xF7, 0xF8 | (src & 7)]))


def _ret_frame(em):
    """mov rsp,rbp; pop rbp; ret（结束一个自建栈帧的 helper）。"""
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp
    em.emit(b"\x5D\xC3")                            # pop rbp; ret


# ------------------------------------------------------------ 日历算法
def _emit_days_from_civil(em, y=_R8, m=_R9, d=_R10):
    """输入 y/m/d 三个寄存器，输出 rax = 儒略日序列号（1970-01-01 = 0）。

    对应 Howard Hinnant days_from_civil。除 y 外不改动输入寄存器；例程内使用
    rax/rcx/rdx/rdi/rsi/r11 作暂存。
    """
    # y' = y - (m <= 2)
    em.cmp_ri(m, 2)
    em.jcc_rel32(0x87, "tm_dfc_noadj")              # ja → m>2
    em.dec_r(y)
    em.label_here("tm_dfc_noadj")
    # era = (y>=0 ? y : y-399) / 146097
    em.mov_rr(_RAX, y)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "tm_cfd_pos")                # jns
    em.add_ri(_RAX, -399)
    em.label_here("tm_cfd_pos")
    em.emit(b"\x48\x99")                            # cqo
    em.mov_r_imm32(_RCX, 400)
    _idiv(em, _RCX)                                 # rax=era（400 年为一纪元）
    em.mov_rr(_R11, _RAX)                           # r11=era
    # yoe = y - era*400
    em.mov_rr(_RAX, _R11)
    em.mov_r_imm32(_RCX, 400)
    _imul(em, _RAX, _RCX)
    em.sub_rr(y, _RAX)                              # y = yoe
    # doy = (153*(m + (m>2 ? -3 : 9)) + 2)/5 + d - 1
    em.mov_rr(_RSI, m)
    em.cmp_ri(m, 2)
    em.jcc_rel32(0x86, "tm_dfc_add9")               # jbe → m<=2
    em.add_ri(_RSI, -3)
    em.jcc_rel32(None, "tm_dfc_dm")
    em.label_here("tm_dfc_add9")
    em.add_ri(_RSI, 9)
    em.label_here("tm_dfc_dm")
    em.mov_rr(_RAX, _RSI)
    em.mov_r_imm32(_RCX, 153)
    _imul(em, _RAX, _RCX)
    em.add_ri(_RAX, 2)
    em.emit(b"\x48\x99")                            # cqo
    em.mov_r_imm32(_RCX, 5)
    _idiv(em, _RCX)
    em.add_rr(_RAX, d)
    em.dec_r(_RAX)
    em.mov_rr(_RSI, _RAX)                           # rsi=doy
    # doe = yoe*365 + yoe/4 - yoe/100 + doy
    em.mov_rr(_RAX, y)
    em.mov_r_imm32(_RCX, 365)
    _imul(em, _RAX, _RCX)
    em.mov_rr(_RCX, _RAX)                           # rcx=acc
    em.mov_rr(_RAX, y)
    em.emit(b"\x48\x99")                            # cqo
    em.mov_r_imm32(_RDI, 4)
    _idiv(em, _RDI)
    em.add_rr(_RCX, _RAX)
    em.mov_rr(_RAX, y)
    em.emit(b"\x48\x99")                            # cqo
    em.mov_r_imm32(_RDI, 100)
    _idiv(em, _RDI)
    em.sub_rr(_RCX, _RAX)
    em.add_rr(_RCX, _RSI)                           # rcx = doe
    # serial = era*146097 + doe - 719468
    em.mov_rr(_RAX, _R11)
    em.mov_r_imm32(_RDI, 146097)
    _imul(em, _RAX, _RDI)
    em.add_rr(_RAX, _RCX)
    em.add_ri(_RAX, -719468)


def _emit_civil_from_days(em):
    """输入 rdi = 儒略日序列号，输出 r8=年, r9=月, r10=日。

    对应 Howard Hinnant civil_from_days。
    """
    em.add_ri(_RDI, 719468)                         # z' = z + 719468
    em.mov_rr(_RAX, _RDI)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "tm_cfd_pos2")               # jns
    em.add_ri(_RAX, -146096)
    em.label_here("tm_cfd_pos2")
    _cqo(em)
    em.mov_r_imm32(_RCX, 146097)
    _idiv(em, _RCX)                                 # rax = era
    em.mov_rr(_R11, _RAX)                           # r11 = era
    em.mov_r_imm32(_RCX, 146097)
    _imul(em, _RAX, _RCX)
    em.mov_rr(_R9, _RDI)
    em.sub_rr(_R9, _RAX)                            # r9 = doe
    # yoe = (doe - doe/1460 + doe/36524 - doe/146096) / 365
    em.mov_rr(_RAX, _R9)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 1460)
    _idiv(em, _RCX)
    em.mov_rr(_RSI, _R9)
    em.sub_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _R9)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 36524)
    _idiv(em, _RCX)
    em.add_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _R9)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 146096)
    _idiv(em, _RCX)
    em.sub_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _RSI)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 365)
    _idiv(em, _RCX)
    em.mov_rr(_R8, _RAX)                            # r8 = yoe
    # doy = doe - (365*yoe + yoe/4 - yoe/100)
    em.mov_rr(_RAX, _R8)
    em.mov_r_imm32(_RCX, 365)
    _imul(em, _RAX, _RCX)
    em.mov_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _R8)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 4)
    _idiv(em, _RCX)
    em.add_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _R8)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 100)
    _idiv(em, _RCX)
    em.sub_rr(_RSI, _RAX)
    em.mov_rr(_RAX, _R9)
    em.sub_rr(_RAX, _RSI)                           # rax = doy
    em.mov_rr(_RSI, _RAX)                           # rsi = doy
    # mp = (5*doy + 2) / 153
    em.mov_rr(_RAX, _RSI)
    em.mov_r_imm32(_RCX, 5)
    _imul(em, _RAX, _RCX)
    em.add_ri(_RAX, 2)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 153)
    _idiv(em, _RCX)
    em.mov_rr(_RDI, _RAX)                           # rdi = mp
    # d = doy - (153*mp + 2)/5 + 1
    em.mov_rr(_RAX, _RDI)
    em.mov_r_imm32(_RCX, 153)
    _imul(em, _RAX, _RCX)
    em.add_ri(_RAX, 2)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 5)
    _idiv(em, _RCX)
    em.mov_rr(_R10, _RSI)
    em.sub_rr(_R10, _RAX)
    em.inc_r(_R10)                                  # r10 = d
    # m = mp + (mp < 10 ? 3 : -9)
    em.mov_rr(_RAX, _RDI)
    em.cmp_ri(_RAX, 10)
    em.jcc_rel32(0x83, "tm_cfd_mg")                 # jae
    em.add_ri(_RAX, 3)
    em.jcc_rel32(None, "tm_cfd_md")
    em.label_here("tm_cfd_mg")
    em.add_ri(_RAX, -9)
    em.label_here("tm_cfd_md")
    em.mov_rr(_R9, _RAX)                            # r9 = m
    # y = yoe + era*400 + (m <= 2 ? 1 : 0)
    em.mov_rr(_RAX, _R11)
    em.mov_r_imm32(_RCX, 400)
    _imul(em, _RAX, _RCX)
    em.add_rr(_RAX, _R8)                            # + yoe
    em.cmp_ri(_R9, 2)
    em.jcc_rel32(0x87, "tm_cfd_y")                  # ja → m > 2
    em.inc_r(_RAX)
    em.label_here("tm_cfd_y")
    em.mov_rr(_R8, _RAX)                            # r8 = y


# ------------------------------------------------------------ 运行时 helper
def _emit_time_runtime(em):
    """发射原生时间运行时（纯函数 helper）。"""
    # ---- tm_is_leap(rdi=year) -> rax(0/1) ----
    em.label_here("tm_is_leap")
    em.mov_rr(_RAX, _RDI)
    _cqo(em)
    em.mov_r_imm32(_RCX, 4)
    _idiv(em, _RCX)
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x85, "tm_leap_no")
    em.mov_rr(_RAX, _RDI)
    _cqo(em)
    em.mov_r_imm32(_RCX, 100)
    _idiv(em, _RCX)
    em.emit(b"\x48\x85\xD2")
    em.jcc_rel32(0x85, "tm_leap_yes")
    em.mov_rr(_RAX, _RDI)
    _cqo(em)
    em.mov_r_imm32(_RCX, 400)
    _idiv(em, _RCX)
    em.emit(b"\x48\x85\xD2")
    em.jcc_rel32(0x85, "tm_leap_no")
    em.label_here("tm_leap_yes")
    em.mov_r_imm32(_RAX, 1)
    em.emit(b"\xC3")
    em.label_here("tm_leap_no")
    em.xor_rr32(_RAX, _RAX)
    em.emit(b"\xC3")

    # ---- tm_days_in_month(rdi=year, rsi=month) -> rax ----
    em.label_here("tm_days_in_month")
    em.cmp_ri(_RSI, 2)
    em.jcc_rel32(0x84, "tm_dim_feb")
    for _m in (1, 3, 5, 7, 8, 10, 12):
        em.cmp_ri(_RSI, _m)
        em.jcc_rel32(0x84, "tm_dim_31")
    em.mov_r_imm32(_RAX, 30)
    em.emit(b"\xC3")
    em.label_here("tm_dim_31")
    em.mov_r_imm32(_RAX, 31)
    em.emit(b"\xC3")
    em.label_here("tm_dim_feb")
    em.call_rel32("tm_is_leap")
    em.add_ri(_RAX, 28)
    em.emit(b"\xC3")

    # ---- tm_parse_date(rdi=STR「YYYY-MM-DD」) -> rax(serial) ----
    em.label_here("tm_parse_date")
    em.xor_rr32(_R8, _R8)                           # y=0
    for pos in (16, 17, 18, 19):
        em.mov_rr(_RAX, _R8)
        em.mov_r_imm32(_RCX, 10)
        _imul(em, _RAX, _RCX)
        em.movzx_r_m8(_R9, _RDI, pos)
        em.add_ri(_R9, -48)
        em.add_rr(_RAX, _R9)
        em.mov_rr(_R8, _RAX)
    em.movzx_r_m8(_R9, _RDI, 21)                    # 十位
    em.add_ri(_R9, -48)
    em.mov_rr(_RAX, _R9)
    em.mov_r_imm32(_RCX, 10)
    _imul(em, _RAX, _RCX)
    em.movzx_r_m8(_R10, _RDI, 22)                   # 个位
    em.add_ri(_R10, -48)
    em.add_rr(_RAX, _R10)
    em.mov_rr(_R9, _RAX)                            # r9 = month
    em.movzx_r_m8(_R10, _RDI, 24)
    em.add_ri(_R10, -48)
    em.mov_rr(_RAX, _R10)
    em.mov_r_imm32(_RCX, 10)
    _imul(em, _RAX, _RCX)
    em.movzx_r_m8(_R11, _RDI, 25)
    em.add_ri(_R11, -48)
    em.add_rr(_RAX, _R11)
    em.mov_rr(_R10, _RAX)                           # r10 = day
    _emit_days_from_civil(em)
    em.emit(b"\xC3")

    # ---- tm_streq(rdi=a, rsi=b) -> rax(0/1)：比较两个 STR 的字节载荷 ----
    em.label_here("tm_streq")
    em.mov_rd_mem(_RAX, _RDI, 8)                    # lenA
    em.mov_rd_mem(_RCX, _RSI, 8)                    # lenB
    em.cmp_rr(_RAX, _RCX)
    em.jcc_rel32(0x85, "tm_streq_ne")
    em.add_ri(_RDI, 16)
    em.add_ri(_RSI, 16)
    em.xor_rr32(_R8, _R8)
    em.label_here("tm_streq_loop")
    em.cmp_rr(_R8, _RAX)
    em.jcc_rel32(0x83, "tm_streq_eq")
    em.movzx_r_m8(_R9, _RDI, 0)
    em.movzx_r_m8(_R10, _RSI, 0)
    em.cmp_rr(_R9, _R10)
    em.jcc_rel32(0x85, "tm_streq_ne")
    em.inc_r(_RDI)
    em.inc_r(_RSI)
    em.inc_r(_R8)
    em.jcc_rel32(None, "tm_streq_loop")
    em.label_here("tm_streq_eq")
    em.mov_r_imm32(_RAX, 1)
    em.emit(b"\xC3")
    em.label_here("tm_streq_ne")
    em.xor_rr32(_RAX, _RAX)
    em.emit(b"\xC3")

    # ---- tm_tz_offset(rdi=STR 时区名) -> rax(小时偏移) ----
    em.label_here("tm_tz_offset")
    em.emit(b"\x53")                                # push rbx
    em.mov_rr(_RBX, _RDI)                           # rbx = name
    for i, (lab, _nm, _off) in enumerate(_TZ_ENTRIES):
        em.lea_rip(_RSI, lab)
        em.mov_rr(_RDI, _RBX)
        em.call_rel32("tm_streq")
        em.emit(b"\x48\x85\xC0")                    # test rax,rax
        em.jcc_rel32(0x85, f"tm_tz_o{i}")
    em.xor_rr32(_RAX, _RAX)                         # 未知名 → 0
    em.jcc_rel32(None, "tm_tz_end")
    for i, (_lab, _nm, off) in enumerate(_TZ_ENTRIES):
        em.label_here(f"tm_tz_o{i}")
        em.mov_rax_imm64(off & 0xFFFFFFFFFFFFFFFF)
        em.jcc_rel32(None, "tm_tz_end")
    em.label_here("tm_tz_end")
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")

    # ---- tm_format_date(rdi=serial) -> rax(STR「YYYY-MM-DD」) ----
    em.label_here("tm_format_date")
    em.emit(b"\x55")                                # push rbp
    em.mov_rr(_RBP, _RSP)                           # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    _emit_civil_from_days(em)                       # -> r8/r9/r10
    em.mov_mem_r(_RBP, -8, _R8)
    em.mov_mem_r(_RBP, -16, _R9)
    em.mov_mem_r(_RBP, -24, _R10)
    em.mov_r_imm32(_RDI, 26)                        # 16 头 + 10 字节
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_r_imm32(_RCX, 10)
    em.mov_mem_r(_RAX, 8, _RCX)
    em.lea_mem(_R11, _RAX, 16)                      # r11 = 载荷基址
    em.mov_rd_mem(_R8, _RBP, -8)
    em.mov_rd_mem(_R9, _RBP, -16)
    em.mov_rd_mem(_R10, _RBP, -24)
    # 年（4 位）
    em.mov_rr(_RAX, _R8)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 1000)
    _idiv(em, _RCX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 0, _RAX)
    em.mov_rr(_RAX, _RDX)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 100)
    _idiv(em, _RCX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 1, _RAX)
    em.mov_rr(_RAX, _RDX)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 10)
    _idiv(em, _RCX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 2, _RAX)
    em.mov_rr(_RAX, _RDX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 3, _RAX)
    em.mov_m8_ri(_R11, 4, 45)                       # '-'
    # 月（2 位）
    em.mov_rr(_RAX, _R9)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 10)
    _idiv(em, _RCX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 5, _RAX)
    em.mov_rr(_RAX, _RDX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 6, _RAX)
    em.mov_m8_ri(_R11, 7, 45)
    # 日（2 位）
    em.mov_rr(_RAX, _R10)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_RCX, 10)
    _idiv(em, _RCX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 8, _RAX)
    em.mov_rr(_RAX, _RDX)
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 9, _RAX)
    em.mov_rr(_RAX, _R11)
    em.add_ri(_RAX, -16)                            # 返回对象头
    _ret_frame(em)


# ------------------------------------------------------------ 内建发射器
def _emit_ret_int(em):
    _restore(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _emit_ret_bool(em, yes_lbl, done_lbl):
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, yes_lbl + "_n")
    em.lea_rip(_RAX, "bool_true")
    em.jcc_rel32(None, done_lbl)
    em.label_here(yes_lbl + "_n")
    em.lea_rip(_RAX, "bool_false")
    em.label_here(done_lbl)


def _emit_builtin_is_leap(em):
    """闰年判断(year) → bool。"""
    em.label_here("fn:闰年判断")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.call_rel32("tm_is_leap")
    _emit_ret_bool(em, "tm_bl", "tm_bldone")
    _emit_ret_int(em)


def _emit_builtin_days_in_month(em):
    """月份天数(year, month) → int。"""
    em.label_here("fn:月份天数")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -16)
    em.mov_rd_mem(_RSI, _RBP, -8)
    em.call_rel32("tm_days_in_month")
    _emit_ret_int(em)


def _emit_builtin_tz_offset(em):
    """时区偏移(name) → int。"""
    em.label_here("fn:时区偏移")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.call_rel32("tm_tz_offset")
    _emit_ret_int(em)


def _emit_builtin_tz_convert(em):
    """时区转换(ts, from, to) → int。"""
    em.label_here("fn:时区转换")
    _EMIT_PROLOGUE(em, 3, 3)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -16)                  # from
    em.call_rel32("tm_tz_offset")
    em.mov_rr(_RBX, _RAX)                           # 目标差 = to - from
    em.mov_rd_mem(_RDI, _RBP, -8)                   # to
    em.call_rel32("tm_tz_offset")
    em.sub_rr(_RAX, _RBX)
    em.mov_r_imm32(_RCX, 3600)
    _imul(em, _RAX, _RCX)
    em.mov_rd_mem(_RCX, _RBP, -24)                  # ts
    em.add_rr(_RAX, _RCX)
    _emit_ret_int(em)


def _emit_builtin_date_diff(em):
    """日期差(d1, d2) → int（d2 - d1 天数）。"""
    em.label_here("fn:日期差")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -16)
    em.call_rel32("tm_parse_date")
    em.mov_rr(_RBX, _RAX)
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.call_rel32("tm_parse_date")
    em.sub_rr(_RAX, _RBX)
    _emit_ret_int(em)


def _emit_builtin_weekday(em):
    """星期几(date) → str（中文「星期X」）。"""
    em.label_here("fn:星期几")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.call_rel32("tm_parse_date")                  # rax = serial
    em.mov_r_imm32(_RCX, 7)
    _cqo(em)
    _idiv(em, _RCX)                                 # rdx = serial % 7
    em.add_ri(_RDX, 3)                              # 1970-01-01 为星期四
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x89, "tm_wd_pos")                 # jns
    em.add_ri(_RDX, 7)
    em.label_here("tm_wd_pos")
    em.cmp_ri(_RDX, 7)
    em.jcc_rel32(0x82, "tm_wd_rd")                  # jb：已在 0..6
    em.add_ri(_RDX, -7)
    em.label_here("tm_wd_rd")
    for i in range(7):
        em.cmp_ri(_RDX, i)
        em.jcc_rel32(0x84, f"tm_wd_{i}")
    em.lea_rip(_RAX, "tm_wd_s0")                    # 兜底：星期一
    em.jcc_rel32(None, "tm_wd_end")
    for i in range(7):
        em.label_here(f"tm_wd_{i}")
        em.lea_rip(_RAX, f"tm_wd_s{i}")
        em.jcc_rel32(None, "tm_wd_end")
    em.label_here("tm_wd_end")
    _emit_ret_int(em)


def _emit_builtin_date_add(em):
    """日期加减(days, base) → str。"""
    em.label_here("fn:日期加减")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.mov_rd_mem(_RDI, _RBP, -8)                   # base
    em.call_rel32("tm_parse_date")
    em.mov_rr(_RBX, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -16)                  # days
    em.add_rr(_RAX, _RBX)
    em.mov_rr(_RDI, _RAX)
    em.call_rel32("tm_format_date")
    _emit_ret_int(em)


# ------------------------------------------------------------ 数据
def emit_time_data(ed):
    """在 .data（静态堆区）发射时区名与星期名 STR 对象。"""
    def _str(lab, s):
        b = s.encode("utf-8")
        ed.align(8)
        ed.label_here(lab)
        ed.emit(struct.pack("<Q", TYPE_STR))
        ed.emit(struct.pack("<Q", len(b)))
        ed.emit(b)
    for lab, nm, _off in _TZ_ENTRIES:
        _str(lab, nm)
    for i, nm in enumerate(_WEEKDAY_ZH):
        _str(f"tm_wd_s{i}", nm)
