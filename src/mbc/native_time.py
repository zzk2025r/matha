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

非纯函数（时钟采集族）原生实现：

  获取时间戳() -> float                     （Unix 秒，含微秒小数）
  获取日期() / 当前日期() -> str            （本地「YYYY-MM-DD」）
  当前时间() -> str                         （本地「HH:MM:SS」）
  获取日期时间() -> str                     （本地「YYYY-MM-DDTHH:MM:SS.ffffff」）
  获取UTC时间() -> str                      （UTC，同上并以 Z 结尾）
  格式化时间(ts, fmt) -> str                （localtime + CRT strftime）
  解析时间(text, fmt) -> float              （自实现 strptime 子集 + CRT _mktime64）

时钟来源为 kernel32!GetSystemTimeAsFileTime（经 k32_base 惰性 GetProcAddress），
日历字段由 CRT _localtime64_s / _gmtime64_s 产出，格式化交给 CRT strftime，
故与宿主解释器（同用 CRT）的格式码行为一致。微秒由 FILETIME 低 7 位十进制推出。

解析时间：Windows CRT 无 strptime，故按格式串自实现一个子集解析器
（%Y/%y/%m/%d/%H/%M/%S/%f 与字面量/%%），把结果填入 struct tm 后交
CRT _mktime64 按**本地时区**换算（与宿主 datetime.timestamp() 同语义）；
解析失败（含格式不符、字段越界）返回 0.0，与宿主捕获 ValueError 的行为一致。

仍暂缓：创建计时器（对象/方法）、注册任务/执行待办/待办列表（全局状态 +
回调）。这些名字在 native.py 的 _UNRESOLVED_GLOBALS 中显式拒绝，避免编译期
静默读 cell→0。

原生字符串布局：`[TYPE_STR][+8]=字节长][+16..]=UTF-8 字节`。
整数为未装箱立即数（rax 直接返回），布尔为 bool_true/bool_false 指针对象。
"""
from __future__ import annotations

import struct

TYPE_STR = 1
# 与 native.py 保持一致的局部标签（本模块不反向 import native，避免循环导入）。
TYPE_LIST = 2
TYPE_DICT = 3
TYPE_CLOSURE = 4
TYPE_TIMER = 12

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
_R12, _R13, _R14, _R15 = 12, 13, 14, 15

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
    """imul dst, src（64 位有符号乘，低 64 位）。

    两操作数形式 `imul r64, r/m64`：ModRM.reg=dst（其扩展位是 REX.R=0x04），
    ModRM.rm=src（其扩展位是 REX.B=0x01）。此前 REX.R/REX.B 判据写反，当
    dst 或 src ≥ r8 时会错误扩展，导致乘错寄存器。
    """
    rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if src >= 8 else 0)
    em.emit(bytes([rex, 0x0F, 0xAF, 0xC0 | ((dst & 7) << 3) | (src & 7)]))


def _idiv(em, src):
    """idiv src（64 位有符号除；商在 rax，余数在 rdx）。"""
    rex = 0x48 | (0x01 if src >= 8 else 0)
    em.emit(bytes([rex, 0xF7, 0xF8 | (src & 7)]))


def _div(em, src):
    """div src（64 位无符号除；商在 rax，余数在 rdx）。调用前需清零 rdx。"""
    rex = 0x48 | (0x01 if src >= 8 else 0)
    em.emit(bytes([rex, 0xF7, 0xF0 | (src & 7)]))


def _cvttsd2si(em, reg, xmm=0):
    """cvttsd2si reg, xmm（截断取整：double → int64）。"""
    rex = 0x48 | (0x04 if reg >= 8 else 0)
    em.emit(bytes([0xF2, rex, 0x0F, 0x2C,
                   0xC0 | ((reg & 7) << 3) | (xmm & 7)]))


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
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40（局部+影子空间）
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

    # ---- tm_gsftaf() -> rax(FILETIME)：kernel32!GetSystemTimeAsFileTime ----
    # 100ns 计数（自 1601-01-01 UTC）。k32_base 由 native.py 引导期写入。
    em.label_here("tm_gsftaf")
    em.emit(b"\x53")                                # push rbx（16 字节对齐）
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20（x64 影子空间）
    em.load_rip_to(_RCX, "k32_base")                # rcx=kernel32 HMODULE
    em.lea_rip(_RDX, "tm_name_gsftaf")
    em.call_rip_indirect("api_GetProcAddress")      # rax=proc
    em.lea_rip(_RCX, "tm_filetime")
    em.emit(b"\xFF\xD0")                            # call rax
    em.load_rip_to(_RAX, "tm_filetime")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")

    # ---- tm_pf_digits(rdi=指针, rsi=剩余, rcx=最多位数) -> rax=值, rdx=消费数 ----
    em.label_here("tm_pf_digits")
    em.xor_rr32(_RAX, _RAX)                         # value=0
    em.xor_rr32(_R8, _R8)                           # consumed=0
    em.mov_r_imm32(_R11, 10)
    em.label_here("tm_pf_d_loop")
    em.cmp_rr(_R8, _RCX)
    em.jcc_rel32(0x83, "tm_pf_d_done")              # jae：已达位数上限
    em.emit(b"\x48\x85\xF6")                        # test rsi,rsi
    em.jcc_rel32(0x84, "tm_pf_d_done")              # jz：输入耗尽
    em.movzx_r_m8(_R9, _RDI, 0)
    em.cmp_ri(_R9, 48)
    em.jcc_rel32(0x82, "tm_pf_d_done")              # jb：非数字
    em.cmp_ri(_R9, 57)
    em.jcc_rel32(0x87, "tm_pf_d_done")              # ja：非数字
    _imul(em, _RAX, _R11)
    em.add_ri(_R9, -48)
    em.add_rr(_RAX, _R9)
    em.inc_r(_RDI)
    em.emit(b"\x48\xFF\xCE")                        # dec rsi
    em.inc_r(_R8)
    em.jcc_rel32(None, "tm_pf_d_loop")
    em.label_here("tm_pf_d_done")
    em.mov_rr(_RDX, _R8)
    em.emit(b"\xC3")

    # ---- tm_parse_fmt(rdi=text载荷, rsi=fmt载荷, rdx=text长, rcx=fmt长,
    #                   r8=&tm) -> rax=1 成功 / 0 失败；失败不改 tm。
    # 支持 %Y %y %m %d %H %M %S %f %% 与字面量；字段默认 1900-01-01 00:00:00。
    # 微秒写入 tm_frac。用自建帧保存中间值（-48 年/-56 月/-64 日/-72 时/
    # -80 分/-88 秒/-96 微秒），故帧 0x60；本 helper 不外呼 CRT，无影子空间需求。
    em.label_here("tm_parse_fmt")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x60")                    # sub rsp,0x60
    em.mov_mem_r(_RBP, -8, _RDI)
    em.mov_mem_r(_RBP, -16, _RSI)
    em.mov_mem_r(_RBP, -24, _RDX)
    em.mov_mem_r(_RBP, -32, _RCX)
    em.mov_mem_r(_RBP, -40, _R8)
    em.mov_r_imm32(_RAX, 1900)
    em.mov_mem_r(_RBP, -48, _RAX)                   # 年默认 1900
    em.mov_r_imm32(_RAX, 1)
    em.mov_mem_r(_RBP, -56, _RAX)                   # 月默认 1
    em.mov_mem_r(_RBP, -64, _RAX)                   # 日默认 1
    em.xor_rr32(_RAX, _RAX)
    em.mov_mem_r(_RBP, -72, _RAX)
    em.mov_mem_r(_RBP, -80, _RAX)
    em.mov_mem_r(_RBP, -88, _RAX)
    em.mov_mem_r(_RBP, -96, _RAX)

    em.label_here("tm_pf_loop")
    em.mov_rd_mem(_RAX, _RBP, -32)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "tm_pf_fin")                 # 格式串耗尽 → 收尾
    em.mov_rd_mem(_RDI, _RBP, -16)                  # 取格式字节
    em.movzx_r_m8(_R10, _RDI, 0)
    em.inc_r(_RDI)
    em.mov_mem_r(_RBP, -16, _RDI)
    em.mov_rd_mem(_RAX, _RBP, -32)
    em.dec_r(_RAX)
    em.mov_mem_r(_RBP, -32, _RAX)
    em.cmp_ri(_R10, 37)                             # '%'
    em.jcc_rel32(0x84, "tm_pf_spec")
    # 字面量：文本需有剩余且逐字节相等
    em.mov_rd_mem(_RAX, _RBP, -24)
    em.emit(b"\x48\x85\xC0")
    em.jcc_rel32(0x84, "tm_pf_fail")
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.movzx_r_m8(_RAX, _RDI, 0)
    em.cmp_rr(_RAX, _R10)
    em.jcc_rel32(0x85, "tm_pf_fail")                # jne
    em.inc_r(_RDI)
    em.mov_mem_r(_RBP, -8, _RDI)
    em.mov_rd_mem(_RAX, _RBP, -24)
    em.dec_r(_RAX)
    em.mov_mem_r(_RBP, -24, _RAX)
    em.jcc_rel32(None, "tm_pf_loop")

    em.label_here("tm_pf_spec")
    em.mov_rd_mem(_RAX, _RBP, -32)
    em.emit(b"\x48\x85\xC0")
    em.jcc_rel32(0x84, "tm_pf_fail")                # '%' 后无字符
    em.mov_rd_mem(_RDI, _RBP, -16)
    em.movzx_r_m8(_R10, _RDI, 0)
    em.inc_r(_RDI)
    em.mov_mem_r(_RBP, -16, _RDI)
    em.mov_rd_mem(_RAX, _RBP, -32)
    em.dec_r(_RAX)
    em.mov_mem_r(_RBP, -32, _RAX)
    em.cmp_ri(_R10, 89)
    em.jcc_rel32(0x84, "tm_pf_Y")
    em.cmp_ri(_R10, 121)
    em.jcc_rel32(0x84, "tm_pf_y")
    em.cmp_ri(_R10, 109)
    em.jcc_rel32(0x84, "tm_pf_m")
    em.cmp_ri(_R10, 100)
    em.jcc_rel32(0x84, "tm_pf_d")
    em.cmp_ri(_R10, 72)
    em.jcc_rel32(0x84, "tm_pf_H")
    em.cmp_ri(_R10, 77)
    em.jcc_rel32(0x84, "tm_pf_M")
    em.cmp_ri(_R10, 83)
    em.jcc_rel32(0x84, "tm_pf_S")
    em.cmp_ri(_R10, 102)
    em.jcc_rel32(0x84, "tm_pf_f")
    em.cmp_ri(_R10, 37)
    em.jcc_rel32(0x84, "tm_pf_pct")
    em.jcc_rel32(None, "tm_pf_fail")                # 未知格式码

    def _take(dest_off, maxdigits):
        em.mov_rd_mem(_RDI, _RBP, -8)
        em.mov_rd_mem(_RSI, _RBP, -24)
        em.mov_r_imm32(_RCX, maxdigits)
        em.call_rel32("tm_pf_digits")
        em.emit(b"\x48\x85\xD2")                    # test rdx,rdx
        em.jcc_rel32(0x84, "tm_pf_fail")            # 未消费到数字
        em.mov_rd_mem(_R11, _RBP, -8)
        em.add_rr(_R11, _RDX)
        em.mov_mem_r(_RBP, -8, _R11)
        em.mov_rd_mem(_R11, _RBP, -24)
        em.sub_rr(_R11, _RDX)
        em.mov_mem_r(_RBP, -24, _R11)
        em.mov_mem_r(_RBP, dest_off, _RAX)

    for _cc, _lbl, _dest, _mx in (
            (89, "tm_pf_Y", -48, 4), (109, "tm_pf_m", -56, 2),
            (100, "tm_pf_d", -64, 2), (72, "tm_pf_H", -72, 2),
            (77, "tm_pf_M", -80, 2), (83, "tm_pf_S", -88, 2)):
        em.label_here(_lbl)
        _take(_dest, _mx)
        em.jcc_rel32(None, "tm_pf_loop")

    em.label_here("tm_pf_y")                        # 两位年：<69→20xx，否则 19xx
    _take(-48, 2)
    em.mov_rd_mem(_RAX, _RBP, -48)
    em.cmp_ri(_RAX, 69)
    em.jcc_rel32(0x83, "tm_pf_y_old")               # jae
    em.add_ri(_RAX, 2000)
    em.jcc_rel32(None, "tm_pf_y_set")
    em.label_here("tm_pf_y_old")
    em.add_ri(_RAX, 1900)
    em.label_here("tm_pf_y_set")
    em.mov_mem_r(_RBP, -48, _RAX)
    em.jcc_rel32(None, "tm_pf_loop")

    em.label_here("tm_pf_f")
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.mov_rd_mem(_RSI, _RBP, -24)
    em.mov_r_imm32(_RCX, 6)
    em.call_rel32("tm_pf_digits")                   # rax=值, rdx=消费位数
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x84, "tm_pf_fail")
    em.mov_rd_mem(_R11, _RBP, -8)
    em.add_rr(_R11, _RDX)
    em.mov_mem_r(_RBP, -8, _R11)
    em.mov_rd_mem(_R11, _RBP, -24)
    em.sub_rr(_R11, _RDX)
    em.mov_mem_r(_RBP, -24, _R11)
    em.mov_r_imm32(_R8, 6)
    em.sub_rr(_R8, _RDX)                            # 指数 = 6 - 位数
    em.mov_r_imm32(_R9, 1)
    em.label_here("tm_pf_fpow")
    em.test_rr(_R8, _R8)
    em.jcc_rel32(0x84, "tm_pf_fpow_done")
    em.mov_r_imm32(_R10, 10)
    _imul(em, _R9, _R10)
    em.dec_r(_R8)
    em.jcc_rel32(None, "tm_pf_fpow")
    em.label_here("tm_pf_fpow_done")
    _imul(em, _RAX, _R9)                            # 微秒 = 值 × 10^指数
    em.mov_mem_r(_RBP, -96, _RAX)
    em.jcc_rel32(None, "tm_pf_loop")

    em.label_here("tm_pf_pct")
    em.mov_rd_mem(_RAX, _RBP, -24)
    em.emit(b"\x48\x85\xC0")
    em.jcc_rel32(0x84, "tm_pf_fail")
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.movzx_r_m8(_RAX, _RDI, 0)
    em.cmp_ri(_RAX, 37)
    em.jcc_rel32(0x85, "tm_pf_fail")                # jne
    em.inc_r(_RDI)
    em.mov_mem_r(_RBP, -8, _RDI)
    em.mov_rd_mem(_RAX, _RBP, -24)
    em.dec_r(_RAX)
    em.mov_mem_r(_RBP, -24, _RAX)
    em.jcc_rel32(None, "tm_pf_loop")

    em.label_here("tm_pf_fin")
    em.mov_rd_mem(_RAX, _RBP, -24)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "tm_pf_fail")                # 输入有剩余 -> 失败
    # 字段范围校验（与 strptime 一致：月 1..12，日 1..当月天数，时 0..23 等）
    em.mov_rd_mem(_RAX, _RBP, -56)
    em.cmp_ri(_RAX, 1)
    em.jcc_rel32(0x8C, "tm_pf_fail")                # jl
    em.cmp_ri(_RAX, 12)
    em.jcc_rel32(0x8F, "tm_pf_fail")                # jg
    em.mov_rd_mem(_RAX, _RBP, -64)
    em.cmp_ri(_RAX, 1)
    em.jcc_rel32(0x8C, "tm_pf_fail")
    em.mov_rd_mem(_RDI, _RBP, -48)                  # tm_days_in_month(年, 月)
    em.mov_rd_mem(_RSI, _RBP, -56)
    em.call_rel32("tm_days_in_month")
    em.mov_rd_mem(_RCX, _RBP, -64)
    em.cmp_rr(_RCX, _RAX)
    em.jcc_rel32(0x8F, "tm_pf_fail")                # 日 > 当月天数 -> jg
    em.mov_rd_mem(_RAX, _RBP, -72)
    em.cmp_ri(_RAX, 23)
    em.jcc_rel32(0x8F, "tm_pf_fail")
    em.mov_rd_mem(_RAX, _RBP, -80)
    em.cmp_ri(_RAX, 59)
    em.jcc_rel32(0x8F, "tm_pf_fail")
    em.mov_rd_mem(_RAX, _RBP, -88)
    em.cmp_ri(_RAX, 59)
    em.jcc_rel32(0x8F, "tm_pf_fail")
    # 写入 struct tm（MSVC 布局：sec/min/hour/mday/mon[0基]/year-1900/.../isdst）
    em.mov_rd_mem(_R11, _RBP, -40)
    em.xor_rr32(_RAX, _RAX)
    for _off in (0, 4, 8, 12, 16, 20, 24, 28, 32):
        em.mov_mem_r32(_R11, _off, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -88)
    em.mov_mem_r32(_R11, 0, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -80)
    em.mov_mem_r32(_R11, 4, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -72)
    em.mov_mem_r32(_R11, 8, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -64)
    em.mov_mem_r32(_R11, 12, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -56)
    em.dec_r(_RAX)                                  # mon 0 基
    em.mov_mem_r32(_R11, 16, _RAX)
    em.mov_rd_mem(_RAX, _RBP, -48)
    em.add_ri(_RAX, -1900)
    em.mov_mem_r32(_R11, 20, _RAX)
    em.mov_r_imm32(_RAX, -1)
    em.mov_mem_r32(_R11, 32, _RAX)                  # tm_isdst=-1（按本地时区判定）
    em.mov_rd_mem(_RAX, _RBP, -96)
    em.store_rip_from("tm_frac", _RAX)
    em.mov_r_imm32(_RAX, 1)
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret
    em.label_here("tm_pf_fail")
    em.xor_rr32(_RAX, _RAX)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- tm_now_tm(rdi=0 本地/1 UTC) -> rax=微秒；填充 tm_timeval 与 tm_tm ----
    em.label_here("tm_now_tm")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40（局部+影子空间）
    em.mov_mem_r(_RBP, -8, _RDI)                    # [rbp-8]=mode
    em.call_rel32("tm_gsftaf")                      # rax=ft
    em.mov_mem_r(_RBP, -16, _RAX)                   # [rbp-16]=ft
    # time_t = ft/10000000 - 11644473600
    em.mov_r_imm64(_R8, 10000000)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)
    em.mov_r_imm64(_RCX, 11644473600)
    em.sub_rr(_RAX, _RCX)
    em.store_rip_from("tm_timeval", _RAX)
    # micros = (ft/10) % 1000000
    em.mov_rd_mem(_RAX, _RBP, -16)
    em.mov_r_imm32(_R8, 10)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)
    em.mov_r_imm64(_R8, 1000000)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)
    em.mov_mem_r(_RBP, -24, _RDX)                   # [rbp-24]=micros
    em.lea_rip(_RCX, "tm_tm")
    em.lea_rip(_RDX, "tm_timeval")
    em.mov_rd_mem(_R10, _RBP, -8)
    em.test_rr(_R10, _R10)
    em.jcc_rel32(0x85, "tm_now_utc")
    em.call_rip_indirect("crt__localtime64_s")
    em.jcc_rel32(None, "tm_now_fin")
    em.label_here("tm_now_utc")
    em.call_rip_indirect("crt__gmtime64_s")
    em.label_here("tm_now_fin")
    em.mov_rd_mem(_RAX, _RBP, -24)                  # rax=微秒
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret

    # ---- tm_strftime(rdi=格式串地址) -> rax=长度；写入 tm_strbuf ----
    em.label_here("tm_strftime")
    em.emit(b"\x48\x83\xEC\x28")                    # sub rsp,0x28（影子空间+对齐）
    em.lea_rip(_RCX, "tm_strbuf")
    em.mov_r_imm32(_RDX, 256)
    em.mov_rr(_R8, _RDI)
    em.lea_rip(_R9, "tm_tm")
    em.call_rip_indirect("crt_strftime")
    em.emit(b"\x48\x83\xC4\x28")                    # add rsp,0x28
    em.emit(b"\xC3")

    # ---- tm_newstr(rdi=字节源, rsi=长度) -> rax=STR 对象 ----
    em.label_here("tm_newstr")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40（局部+影子空间）
    em.mov_mem_r(_RBP, -8, _RSI)                    # len
    em.mov_mem_r(_RBP, -16, _RDI)                   # src
    em.mov_rr(_RDI, _RSI)
    em.add_ri(_RDI, 16)
    em.call_rel32("alloc")                          # rax=obj
    em.emit(b"\x48\xC7\x00" + struct.pack("<i", TYPE_STR))
    em.mov_rd_mem(_RCX, _RBP, -8)
    em.mov_mem_r(_RAX, 8, _RCX)                     # [rax+8]=len
    em.mov_rd_mem(_RSI, _RBP, -16)                  # rsi=src
    em.lea_mem(_RDI, _RAX, 16)                      # rdi=载荷
    em.mov_rd_mem(_RCX, _RBP, -8)                   # rcx=len
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret

    # ---- tm_build_dt(rdi=0 本地/1 UTC) -> rax=STR（含 .ffffff[Z]）----
    em.label_here("tm_build_dt")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40（局部+影子空间）
    em.mov_mem_r(_RBP, -8, _RDI)                    # mode
    em.call_rel32("tm_now_tm")                      # rax=微秒
    em.mov_mem_r(_RBP, -16, _RAX)                   # micros
    em.lea_rip(_RDI, "tm_fmt_dt")
    em.call_rel32("tm_strftime")                    # rax=长度
    em.mov_rr(_R15, _RAX)                           # r15=长度
    em.lea_rip(_R11, "tm_strbuf")
    em.add_rr(_R11, _R15)                           # buf+len
    em.mov_m8_ri(_R11, 0, 46)                       # '.'
    em.inc_r(_R11)
    em.mov_rd_mem(_RBX, _RBP, -16)                  # rbx=微秒
    em.mov_r_imm64(_R8, 100000)                     # 十进制权重
    em.xor_rr32(_R13, _R13)                         # i=0
    em.label_here("tm_dt_loop")
    em.mov_rr(_RAX, _RBX)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)                                   # rax=digit
    em.add_ri(_RAX, 48)
    em.mov_m8_r(_R11, 0, _RAX)
    em.mov_rr(_RBX, _RDX)                           # remainder
    em.mov_rr(_RAX, _R8)
    em.xor_rr32(_RDX, _RDX)
    em.mov_r_imm32(_R9, 10)
    _div(em, _R9)                                   # divisor/=10
    em.mov_rr(_R8, _RAX)
    em.inc_r(_R11)
    em.inc_r(_R13)
    em.cmp_ri(_R13, 6)
    em.jcc_rel32(0x82, "tm_dt_loop")                # jb
    em.mov_rd_mem(_RAX, _RBP, -8)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "tm_dt_noz")
    em.mov_m8_ri(_R11, 0, 90)                       # 'Z'
    em.inc_r(_R11)
    em.label_here("tm_dt_noz")
    em.lea_rip(_RAX, "tm_strbuf")
    em.sub_rr(_R11, _RAX)                           # 长度
    em.mov_rr(_RSI, _R11)
    em.mov_rr(_RDI, _RAX)
    em.call_rel32("tm_newstr")
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret

    _emit_timer_runtime(em)                         # 计时器对象方法函数
    _emit_sched_runtime(em)                         # 调度辅助（当前时刻，秒）


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
    """时区偏移(name) → int（非文本实参 → 0，对齐解释器默认时区）。

    解释器 time_module.timezone_offset(name) 对未知/非字符串名返回 0；此前原生端
    直接把实参当 STR 传给 tm_tz_offset，0 参归一化哨兵 0 会被当字符串读而崩溃。
    """
    l_zero, l_done = "tz_off_zero", "tz_off_done"
    em.label_here("fn:时区偏移")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RAX, _RBP, -8)
    em.mov_rr(_RCX, _RAX)
    em.lea_rip(_RDX, "heap_base")
    em.sub_rr(_RCX, _RDX)
    em.cmp_heap_used(_RCX)
    em.jcc_rel32(0x83, l_zero)                      # 非堆指针 → 0
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]（类型标签）
    em.cmp_ri(_RCX, TYPE_STR)
    em.jcc_rel32(0x85, l_zero)                      # 非文本 → 0
    em.mov_rd_mem(_RDI, _RBP, -8)
    em.call_rel32("tm_tz_offset")
    em.jcc_rel32(None, l_done)
    em.label_here(l_zero)
    em.xor_rr32(_RAX, _RAX)
    em.label_here(l_done)
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


def _emit_builtin_now(em):
    """获取时间戳() → float（Unix 秒，含微秒）。"""
    em.label_here("fn:获取时间戳")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.call_rel32("tm_gsftaf")
    em.mov_rr(_RBX, _RAX)
    em.mov_r_imm64(_R8, 10000000)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)
    em.mov_r_imm64(_RCX, 11644473600)
    em.sub_rr(_RAX, _RCX)
    em.cvtsi2sd(0, _RAX)                            # xmm0=(double)time_t
    em.mov_rr(_RAX, _RBX)
    em.mov_r_imm32(_R8, 10)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)
    em.mov_r_imm64(_R8, 1000000)
    em.xor_rr32(_RDX, _RDX)
    _div(em, _R8)                                   # rdx=微秒
    em.cvtsi2sd(1, _RDX)                            # xmm1=(double)微秒
    em.lea_rip(_R11, "tm_c_1e6")
    em.movsd_load(2, _R11, 0)                       # xmm2=1e-6
    em.mulsd(1, 2)
    em.addsd(0, 1)                                  # xmm0=time_t+微秒/1e6
    em.call_rel32("box_float")
    _emit_ret_int(em)


def _emit_builtin_today(em):
    """获取日期() → str（本地「YYYY-MM-DD」）。"""
    em.label_here("fn:获取日期")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.xor_rr32(_RDI, _RDI)
    em.call_rel32("tm_now_tm")
    em.lea_rip(_RDI, "tm_fmt_date")
    em.call_rel32("tm_strftime")
    em.mov_rr(_RSI, _RAX)
    em.lea_rip(_RDI, "tm_strbuf")
    em.call_rel32("tm_newstr")
    _emit_ret_int(em)


def _emit_builtin_date_str(em):
    """当前日期() → str（本地「YYYY-MM-DD」）。"""
    em.label_here("fn:当前日期")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.xor_rr32(_RDI, _RDI)
    em.call_rel32("tm_now_tm")
    em.lea_rip(_RDI, "tm_fmt_date")
    em.call_rel32("tm_strftime")
    em.mov_rr(_RSI, _RAX)
    em.lea_rip(_RDI, "tm_strbuf")
    em.call_rel32("tm_newstr")
    _emit_ret_int(em)


def _emit_builtin_time_str(em):
    """当前时间() → str（本地「HH:MM:SS」）。"""
    em.label_here("fn:当前时间")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.xor_rr32(_RDI, _RDI)
    em.call_rel32("tm_now_tm")
    em.lea_rip(_RDI, "tm_fmt_time")
    em.call_rel32("tm_strftime")
    em.mov_rr(_RSI, _RAX)
    em.lea_rip(_RDI, "tm_strbuf")
    em.call_rel32("tm_newstr")
    _emit_ret_int(em)


def _emit_builtin_now_datetime(em):
    """获取日期时间() → str（本地「…T..:..:..ffffff」）。"""
    em.label_here("fn:获取日期时间")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.xor_rr32(_RDI, _RDI)
    em.call_rel32("tm_build_dt")
    _emit_ret_int(em)


def _emit_builtin_now_utc(em):
    """获取UTC时间() → str（UTC，以 Z 结尾）。"""
    em.label_here("fn:获取UTC时间")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_r_imm32(_RDI, 1)
    em.call_rel32("tm_build_dt")
    _emit_ret_int(em)


def _emit_builtin_format_time(em):
    """格式化时间(ts, fmt) → str（localtime + strftime）。"""
    em.label_here("fn:格式化时间")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20（CRT 调用影子空间）
    em.mov_rd_mem(_RAX, _RBP, -16)                  # ts
    em.call_rel32("as_double")                      # xmm0=ts
    _cvttsd2si(em, _RAX)                            # rax=秒
    em.store_rip_from("tm_timeval", _RAX)
    em.lea_rip(_RCX, "tm_tm")
    em.lea_rip(_RDX, "tm_timeval")
    em.call_rip_indirect("crt__localtime64_s")
    em.mov_rd_mem(_RDI, _RBP, -8)                   # fmt STR
    em.add_ri(_RDI, 16)                             # 载荷地址
    em.call_rel32("tm_strftime")                    # rax=长度
    em.mov_rr(_RSI, _RAX)
    em.lea_rip(_RDI, "tm_strbuf")
    em.call_rel32("tm_newstr")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20（回收影子空间）
    _emit_ret_int(em)


def _emit_builtin_parse_time(em):
    """解析时间(text, fmt) → float（自实现 strptime 子集 + _mktime64）。"""
    em.label_here("fn:解析时间")
    _EMIT_PROLOGUE(em, 2, 2)
    _save(em)
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20（CRT 调用影子空间）
    em.mov_rd_mem(_RDI, _RBP, -16)                  # text STR 对象
    em.mov_rd_mem(_RSI, _RBP, -8)                   # fmt STR 对象
    em.mov_rd_mem(_RDX, _RDI, 8)                    # text 字节长
    em.mov_rd_mem(_RCX, _RSI, 8)                    # fmt 字节长
    em.add_ri(_RDI, 16)                             # text 载荷
    em.add_ri(_RSI, 16)                             # fmt 载荷
    em.lea_rip(_R8, "tm_tm")
    em.call_rel32("tm_parse_fmt")                   # rax=1 成功 / 0 失败
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "tm_pt_zero")                # 解析失败 -> 0.0
    em.lea_rip(_RCX, "tm_tm")
    em.call_rip_indirect("crt__mktime64")           # rax=本地时区秒
    em.cvtsi2sd(0, _RAX)                            # xmm0=秒
    em.load_rip_to(_R11, "tm_frac")
    em.cvtsi2sd(1, _R11)                            # xmm1=微秒
    em.lea_rip(_R11, "tm_c_1e6")
    em.movsd_load(2, _R11, 0)                       # xmm2=1e-6
    em.mulsd(1, 2)
    em.addsd(0, 1)
    em.jcc_rel32(None, "tm_pt_box")
    em.label_here("tm_pt_zero")
    em.emit(b"\x66\x0F\x57\xC0")                    # xorps xmm0,xmm0 -> 0.0
    em.label_here("tm_pt_box")
    em.call_rel32("box_float")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20（回收影子空间）
    _emit_ret_int(em)


# ============================================================
# 计时器（极简对象/方法模型）
# ============================================================
# 对象表示：字典 {方法名 -> 闭包记录}。闭包记录 = [TYPE_CLOSURE][fn][env=box][1]，
# 方法函数从参数帧的环境槽（[rbp-16]，由 apply_rt 的 ar_close 分支写入 r13）拿到
# 状态盒 box = [TYPE_TIMER][start(FILETIME 100ns)][elapsed(double)][running(0/1)]。
# 与宿主 time_module.make_timer（对象=dict、方法=共享 state 的闭包）逐一对齐。
#
# 方法名与宿主一致（英文 start/stop/reset/elapsed），键用静态 STR 对象发射，
# dict_get 经 val_eq 按内容比较，故与源码里 t.start 的 sob: 串匹配。

_TIMER_METHODS = (
    ("start", "tm_key_start", "tm_method_start"),
    ("stop", "tm_key_stop", "tm_method_stop"),
    ("reset", "tm_key_reset", "tm_method_reset"),
    ("elapsed", "tm_key_elapsed", "tm_method_elapsed"),
)


def _emit_timer_runtime(em):
    """发射计时器对象的四个方法函数（供 CREATE_TIMER 构造的闭包调用）。"""
    # ---- start(box)：box.start = gsftaf(); box.running = 1; 返回 null ----
    em.label_here("tm_method_start")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RBX, _RBP, -16)                  # rbx = box（环境槽）
    em.call_rel32("tm_gsftaf")                      # rax = now（FILETIME 100ns）
    em.mov_mem_r(_RBX, 8, _RAX)                     # box.start = now
    em.mov_r_imm32(_RDX, 1)
    em.mov_mem_r(_RBX, 24, _RDX)                    # box.running = 1
    em.lea_rip(_RAX, "null_obj")
    _emit_ret_int(em)

    # ---- reset(box)：清空三项；返回 null ----
    em.label_here("tm_method_reset")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RBX, _RBP, -16)
    em.xor_rr32(_RAX, _RAX)
    em.mov_mem_r(_RBX, 8, _RAX)
    em.mov_mem_r(_RBX, 16, _RAX)
    em.mov_mem_r(_RBX, 24, _RAX)
    em.lea_rip(_RAX, "null_obj")
    _emit_ret_int(em)

    # ---- elapsed(box)：运行中 → elapsed + (now-start)/1e7；否则 elapsed ----
    em.label_here("tm_method_elapsed")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RBX, _RBP, -16)
    em.mov_rd_mem(_RAX, _RBX, 24)                   # running
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "tm_el_notrun")
    em.call_rel32("tm_gsftaf")
    em.mov_rd_mem(_RCX, _RBX, 8)                    # start
    em.sub_rr(_RAX, _RCX)                           # delta（100ns）
    em.cvtsi2sd(0, _RAX)                            # xmm0 = delta
    em.lea_rip(_R11, "tm_c_1e7")
    em.movsd_load(1, _R11, 0)                       # xmm1 = 1e7
    em.divsd(0, 1)                                  # xmm0 = 秒
    em.movsd_load(1, _RBX, 16)                      # xmm1 = elapsed
    em.addsd(0, 1)                                  # xmm0 = 累计
    em.jcc_rel32(None, "tm_el_box")
    em.label_here("tm_el_notrun")
    em.movsd_load(0, _RBX, 16)
    em.label_here("tm_el_box")
    em.call_rel32("box_float")
    _emit_ret_int(em)

    # ---- stop(box)：运行中先结算并清零 running；返回累计秒（float）----
    em.label_here("tm_method_stop")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.mov_rd_mem(_RBX, _RBP, -16)
    em.mov_rd_mem(_RAX, _RBX, 24)                   # running
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "tm_st_notrun")
    em.call_rel32("tm_gsftaf")
    em.mov_rd_mem(_RCX, _RBX, 8)
    em.sub_rr(_RAX, _RCX)
    em.cvtsi2sd(0, _RAX)
    em.lea_rip(_R11, "tm_c_1e7")
    em.movsd_load(1, _R11, 0)
    em.divsd(0, 1)
    em.movsd_load(1, _RBX, 16)
    em.addsd(0, 1)                                  # 新 elapsed
    em.movsd_store(_RBX, 16, 0)                     # box.elapsed = xmm0
    em.xor_rr32(_RAX, _RAX)
    em.mov_mem_r(_RBX, 24, _RAX)                    # running = 0
    em.jcc_rel32(None, "tm_st_box")
    em.label_here("tm_st_notrun")
    em.movsd_load(0, _RBX, 16)
    em.label_here("tm_st_box")
    em.call_rel32("box_float")
    _emit_ret_int(em)


def _emit_builtin_create_timer(em):
    """创建计时器() → dict{start,stop,reset,elapsed}（方法闭包共享状态盒）。"""
    em.label_here("fn:创建计时器")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    # 状态盒 box = [TYPE_TIMER][start=0][elapsed=0][running=0]（32 字节）
    em.mov_r_imm32(_RDI, 32)
    em.call_rel32("alloc")
    em.mov_r_imm32(_RCX, TYPE_TIMER)
    em.mov_mem_r(_RAX, 0, _RCX)
    em.xor_rr32(_RCX, _RCX)
    em.mov_mem_r(_RAX, 8, _RCX)
    em.mov_mem_r(_RAX, 16, _RCX)
    em.mov_mem_r(_RAX, 24, _RCX)
    em.mov_rr(_RBX, _RAX)                           # rbx = box
    # 字典 d = [TYPE_DICT][4][(key,val)*4]
    em.mov_r_imm32(_RDI, 16 + 16 * 4)
    em.call_rel32("alloc")
    em.mov_r_imm32(_RCX, TYPE_DICT)
    em.mov_mem_r(_RAX, 0, _RCX)
    em.mov_r_imm32(_RCX, 4)
    em.mov_mem_r(_RAX, 8, _RCX)
    em.mov_rr(_R15, _RAX)                           # r15 = dict
    for i, (_name, key_lab, fn_lab) in enumerate(_TIMER_METHODS):
        # 闭包记录 [TYPE_CLOSURE][fn][env=box][arity=1]
        em.mov_r_imm32(_RDI, 32)
        em.call_rel32("alloc")
        em.mov_r_imm32(_RCX, TYPE_CLOSURE)
        em.mov_mem_r(_RAX, 0, _RCX)
        em.lea_rip(_R9, fn_lab)
        em.mov_mem_r(_RAX, 8, _R9)                  # fn
        em.mov_mem_r(_RAX, 16, _RBX)                # env = box
        em.mov_r_imm32(_RCX, 1)
        em.mov_mem_r(_RAX, 24, _RCX)                # arity
        # 写入字典 pair (key, val)
        em.lea_rip(_R9, key_lab)
        em.mov_mem_r(_R15, 16 + 16 * i, _R9)
        em.mov_mem_r(_R15, 16 + 16 * i + 8, _RAX)
    em.mov_rr(_RAX, _R15)
    _emit_ret_int(em)


# ============================================================
# 定时调度（严格对齐 interp/VM 现状）
# ============================================================
# 任务表：一个原生列表（元素为任务字典），挂到全局 GC 根槽 gc_extra_root。
# 任务字典键序（对齐宿主 dict 字面量）：interval / name / callback / next_run / id。
#
# 严格对齐说明：interp/VM 中回调值（闭包元组 / vm.Closure）不可调用，故宿主
# run_pending_tasks 里的 task["callback"]() 恒抛 TypeError 被吞，「执行待办」
# 实际从不触发回调、恒返回 []；但到期任务的 next_run 仍会前移（宿主在 except
# 之外更新）。本实现照此复现：执行待办不调用回调、返回空列表，仅前移到期项。

_SCHED_KEYS = (
    ("tm_k_interval", "interval"),
    ("tm_k_name", "name"),
    ("tm_k_callback", "callback"),
    ("tm_k_nextrun", "next_run"),
    ("tm_k_id", "id"),
)


def _emit_sched_runtime(em):
    """tm_now_sec() → xmm0：自 Unix 纪元的秒（含小数）。

    由 FILETIME（100ns 自 1601-01-01 UTC）换算：秒 = ticks/1e7 - 11644473600。
    """
    em.label_here("tm_now_sec")
    em.emit(b"\x48\x83\xEC\x08")                    # sub rsp,8（对齐调用）
    em.call_rel32("tm_gsftaf")                      # rax = FILETIME 100ns
    em.cvtsi2sd(0, _RAX)                            # xmm0 = ticks
    em.lea_rip(_R11, "tm_c_1e7")
    em.movsd_load(1, _R11, 0)
    em.divsd(0, 1)                                  # 秒（自 1601）
    em.lea_rip(_R11, "tm_c_unix_epoch")
    em.movsd_load(1, _R11, 0)
    em.subsd(0, 1)                                  # 减 1970 偏移 → 自 Unix
    em.emit(b"\x48\x83\xC4\x08")                    # add rsp,8
    em.emit(b"\xC3")


def _emit_now_box(em, dst):
    """dst = box_float(tm_now_sec())（Matha 浮点对象指针）。"""
    em.call_rel32("tm_now_sec")
    em.call_rel32("box_float")
    em.mov_rr(dst, _RAX)


def _emit_new_empty_list(em, dst):
    em.mov_r_imm32(_RDI, 16)
    em.call_rel32("alloc")
    em.mov_r_imm32(_RCX, TYPE_LIST)
    em.mov_mem_r(_RAX, 0, _RCX)
    em.mov_r_imm32(_RCX, 0)
    em.mov_mem_r(_RAX, 8, _RCX)
    em.mov_rr(dst, _RAX)


def _emit_dict_put_key(em, key_lab, val_reg):
    """就地 dict_put：r15=dict、rdx=值 → r15=新 dict（键为静态 STR）。"""
    em.mov_rr(_RDX, val_reg)
    em.lea_rip(_RCX, key_lab)
    em.mov_rr(_RAX, _R15)
    em.call_rel32("dict_put")
    em.mov_rr(_R15, _RAX)


def _emit_builtin_register_task(em):
    """注册任务(interval)(name)(callback) → int（任务 id = 追加前任务数）。

    interval=[rbp-24]、name=[rbp-16]、callback=[rbp-8]。
    """
    em.label_here("fn:注册任务")
    _EMIT_PROLOGUE(em, 3, 3)
    _save(em)
    # id = 现有任务数（表为空/0 → 0，否则 [list+8]）
    em.load_rip_to(_RBX, "gc_extra_root")           # rbx = 任务表（0 表示空）
    em.mov_r_imm32(_R14, 0)
    em.emit(b"\x48\x85\xDB")                        # test rbx,rbx
    em.jcc_rel32(0x84, "tsk_reg_id")
    em.mov_rd_mem(_R14, _RBX, 8)
    em.label_here("tsk_reg_id")                     # r14 = id
    # 新建空字典 → r15
    em.mov_r_imm32(_RDI, 16)
    em.call_rel32("alloc")
    em.mov_r_imm32(_RCX, TYPE_DICT)
    em.mov_mem_r(_RAX, 0, _RCX)
    em.mov_r_imm32(_RCX, 0)
    em.mov_mem_r(_RAX, 8, _RCX)
    em.mov_rr(_R15, _RAX)
    # interval（存原始实参值）
    em.mov_rd_mem(_RBX, _RBP, -24)
    _emit_dict_put_key(em, "tm_k_interval", _RBX)
    # name
    em.mov_rd_mem(_RBX, _RBP, -16)
    _emit_dict_put_key(em, "tm_k_name", _RBX)
    # callback（原样存值）
    em.mov_rd_mem(_RBX, _RBP, -8)
    _emit_dict_put_key(em, "tm_k_callback", _RBX)
    # next_run = now + interval（浮点）
    em.call_rel32("tm_now_sec")
    em.call_rel32("box_float")                      # rax = now_box
    em.mov_rd_mem(_RCX, _RBP, -24)                  # rcx = interval（int/float）
    em.call_rel32("f_add")                          # rax = boxed(now+interval)
    _emit_dict_put_key(em, "tm_k_nextrun", _RAX)
    # id
    _emit_dict_put_key(em, "tm_k_id", _R14)
    # 追加到任务表并写回根槽
    em.load_rip_to(_RAX, "gc_extra_root")
    em.mov_rr(_RCX, _R15)
    em.call_rel32("list_append")                    # rax = 新列表
    em.store_rip_from("gc_extra_root", _RAX)
    em.mov_rr(_RAX, _R14)                           # 返回 id
    _emit_ret_int(em)


def _emit_builtin_run_pending(em):
    """执行待办()（忽略占位实参）→ []（严格对齐：回调从不触发）。

    到期项（now >= next_run）的 next_run 前移为 now+interval；返回空列表。
    """
    em.label_here("fn:执行待办")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.emit(b"\x48\x83\xEC\x10")                    # sub rsp,0x10（存 now_box）
    _emit_now_box(em, _RAX)
    em.mov_mem_r(_RSP, 0, _RAX)                     # [rsp] = now_box
    _emit_new_empty_list(em, _R13)                  # r13 = 新任务表
    em.load_rip_to(_R15, "gc_extra_root")           # r15 = 旧任务表
    em.mov_r_imm32(_R12, 0)
    em.emit(b"\x4D\x85\xFF")                        # test r15,r15
    em.jcc_rel32(0x84, "tsk_rp_cnt")
    em.mov_rd_mem(_R12, _R15, 8)                    # r12 = count
    em.label_here("tsk_rp_cnt")
    em.mov_r_imm32(_R14, 0)                         # i = 0
    em.label_here("tsk_rp_loop")
    em.cmp_rr(_R14, _R12)
    em.jcc_rel32(0x83, "tsk_rp_end")                    # jae i>=count
    em.mov_rr(_RCX, _R14)
    em.shl_ri(_RCX, 3)
    em.mov_rd_mem(_RBX, _R15, 16, index=_RCX, scale=1)  # rbx = task
    # nr = task["next_run"]
    em.mov_rr(_RAX, _RBX)
    em.lea_rip(_RCX, "tm_k_nextrun")
    em.call_rel32("dict_get")                       # rax = next_run
    em.mov_rr(_RCX, _RAX)
    em.mov_rd_mem(_RAX, _RSP, 0)                    # l = now_box
    em.call_rel32("float_cmp2")                     # ucomisd(now, next_run)
    em.jcc_rel32(0x82, "tsk_rp_keep")                   # jb：now < next_run → 未到期
    # 到期：next_run = f_add(now_box, interval)
    em.mov_rr(_RAX, _RBX)
    em.lea_rip(_RCX, "tm_k_interval")
    em.call_rel32("dict_get")                       # rax = interval（原始值）
    em.mov_rr(_RCX, _RAX)
    em.mov_rd_mem(_RAX, _RSP, 0)                    # rax = now_box
    em.call_rel32("f_add")                          # rax = 新 next_run
    em.mov_rr(_RDX, _RAX)                           # val = 新 next_run
    em.lea_rip(_RCX, "tm_k_nextrun")                # key
    em.mov_rr(_RAX, _RBX)                           # dict = task
    em.call_rel32("dict_put")                       # rax = 新任务字典
    em.mov_rr(_RBX, _RAX)                           # rbx = 更新后的 task
    em.label_here("tsk_rp_keep")
    em.mov_rr(_RAX, _R13)
    em.mov_rr(_RCX, _RBX)
    em.call_rel32("list_append")
    em.mov_rr(_R13, _RAX)
    em.inc_r(_R14)
    em.jcc_rel32(None, "tsk_rp_loop")
    em.label_here("tsk_rp_end")
    em.store_rip_from("gc_extra_root", _R13)        # 写回新表
    _emit_new_empty_list(em, _RAX)                  # 返回 []
    em.emit(b"\x48\x83\xC4\x10")                    # add rsp,0x10
    _emit_ret_int(em)


def _emit_builtin_pending_list(em):
    """待办列表()（忽略占位实参）→ 未到期任务（now < next_run）的字典列表。"""
    em.label_here("fn:待办列表")
    _EMIT_PROLOGUE(em, 1, 1)
    _save(em)
    em.emit(b"\x48\x83\xEC\x10")                    # sub rsp,0x10
    _emit_now_box(em, _RAX)
    em.mov_mem_r(_RSP, 0, _RAX)                     # [rsp] = now_box
    _emit_new_empty_list(em, _R13)                  # r13 = 结果列表
    em.load_rip_to(_R15, "gc_extra_root")
    em.mov_r_imm32(_R12, 0)
    em.emit(b"\x4D\x85\xFF")                        # test r15,r15
    em.jcc_rel32(0x84, "tsk_pl_cnt")
    em.mov_rd_mem(_R12, _R15, 8)
    em.label_here("tsk_pl_cnt")
    em.mov_r_imm32(_R14, 0)
    em.label_here("tsk_pl_loop")
    em.cmp_rr(_R14, _R12)
    em.jcc_rel32(0x83, "tsk_pl_end")
    em.mov_rr(_RCX, _R14)
    em.shl_ri(_RCX, 3)
    em.mov_rd_mem(_RBX, _R15, 16, index=_RCX, scale=1)  # rbx = task
    em.mov_rr(_RAX, _RBX)
    em.lea_rip(_RCX, "tm_k_nextrun")
    em.call_rel32("dict_get")                       # rax = next_run
    em.mov_rr(_RCX, _RAX)
    em.mov_rd_mem(_RAX, _RSP, 0)                    # l = now_box
    em.call_rel32("float_cmp2")
    em.jcc_rel32(0x83, "tsk_pl_skip")                   # jae：now >= next_run → 已到期
    em.mov_rr(_RAX, _R13)
    em.mov_rr(_RCX, _RBX)
    em.call_rel32("list_append")
    em.mov_rr(_R13, _RAX)
    em.label_here("tsk_pl_skip")
    em.inc_r(_R14)
    em.jcc_rel32(None, "tsk_pl_loop")
    em.label_here("tsk_pl_end")
    em.mov_rr(_RAX, _R13)
    em.emit(b"\x48\x83\xC4\x10")
    _emit_ret_int(em)


def emit_time_bss(eb):
    """在 .bss 预留时钟 scratch（kernel32 基址 + FILETIME + tm + 格式化缓冲）。"""
    for nm in ("k32_base", "tm_filetime", "tm_timeval", "tm_frac"):
        eb.align(8)
        eb.label_here(nm)
        eb.emit_virtual(8)
    eb.align(16)
    eb.label_here("tm_tm")
    eb.emit_virtual(64)
    eb.align(16)
    eb.label_here("tm_strbuf")
    eb.emit_virtual(256)


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

    # 非纯时钟族所需常量：CRT 格式串、kernel32 导出名、浮点常量。
    for lab, s in (("tm_fmt_date", "%Y-%m-%d"),
                   ("tm_fmt_time", "%H:%M:%S"),
                   ("tm_fmt_dt", "%Y-%m-%dT%H:%M:%S"),
                   ("tm_name_gsftaf", "GetSystemTimeAsFileTime")):
        ed.align(8)
        ed.label_here(lab)
        ed.emit(s.encode("ascii") + b"\x00")
    ed.align(8)
    ed.label_here("tm_c_1e6")
    ed.emit(struct.pack("<d", 1e-6))
    ed.align(8)
    ed.label_here("tm_c_1e7")
    ed.emit(struct.pack("<d", 1e7))
    ed.align(8)
    ed.label_here("tm_c_unix_epoch")
    ed.emit(struct.pack("<d", 11644473600.0))

    # 计时器方法名 STR 对象（键），须与源码 t.start 的 sob: 串按内容相等。
    for lab, nm in (("tm_key_start", "start"), ("tm_key_stop", "stop"),
                    ("tm_key_reset", "reset"), ("tm_key_elapsed", "elapsed")):
        _str(lab, nm)
    # 调度任务字典的键（对齐宿主 dict 字面量键序）。
    for lab, nm in _SCHED_KEYS:
        _str(lab, nm)
