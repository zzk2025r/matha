r"""原生进程映像后端（阶段 44：原生 OS 派生面）。

为 M3V 原生后端提供**进程映像**族的原生实现。全部触达点为 kernel32 导出，经
native.py 引导期取得的 k32_base + api_GetProcAddress 惰性解析，故运行路径
不含任何 Python 模块（也无 CRT 依赖）：

  派生映像(cmd)          -> Int    成功=子进程 pid，失败=-1
  等候映像(pid)(ms)      -> Bool   时限内退出=真，仍在跑=假，无记录/失败=null
  映像退出码(pid)        -> Int    已退出=退出码，仍在跑或无记录=null
  终止映像(pid)          -> Bool   终止成功=真，已退出=假，无记录/失败=null
  关闭映像(pid)          -> Bool   释放槽位成功=真，无记录=null

口径（三面同判须逐字照此实现）：

1. 句柄生命周期由调用方负责：`关闭映像` 之前 pid 一直可查（映像退出码 可反复
   读）。这与 C 的 CreateProcessW/CloseHandle 契约一致，不自动回收。
2. 表容量 32 槽（每槽 40 字节），满槽时 `派生映像` 诚实返回 -1，不覆盖旧槽。
3. 「无定义读数」一律 null，不用哨兵数冒充：pid 不在表中、pid<=0、实参是堆
   对象而非整数、`GetExitCodeProcess` 报 STILL_ACTIVE(259)、API 解析失败，
   全部返回 null（`派生映像` 的对应形态是 -1）。
4. `等候映像` 的 ms<0 映射为 INFINITE；`终止映像` 用退出码 1（与 CPython
   subprocess.Popen.terminate 在 Windows 上的 _TERMINATE_PROCESS_RETURN 同值），
   并在终止后等待至多 5000ms 收殓，使 `映像退出码` 立即可读到 1。
5. 只派生直接子进程，不建作业对象：`终止映像` 终止的是 CreateProcessW 返回的
   那个映像本身。若命令行是 `cmd.exe /c ...` 这类外壳，其孙进程（如 ping.exe）
   不随外壳终止——与 C 的裸 TerminateProcess 同语义，需要整树回收时应在后续片
   以 CreateJobObjectW + AssignProcessToJobObject 补齐（登记不修）。

实现细节：命令行 UTF-8 → UTF-16 经 MultiByteToWideChar(CP_UTF8) 转换，故中文
路径与 CPython 的宽字符 CreateProcessW 路径同行为；命令行缓冲上限 2048 UTF-8
字节，超限诚实判失败。STARTUPINFOW.cb=104（x64 布局），dwFlags/hStd* 全零
（继承父控制台，子进程输出直接进入本映像 stdout 流）。

GC 无关：槽表只存内核句柄（值远小于 heap_base）与整数读数，不含任何 Matha 堆
对象指针，故无需登记 GC 根，也不会被 mark_candidate 误判为堆指针。

Win64 ABI：实参 rcx/rdx/r8/r9，第 5 个起 [rsp+0x20]…；调用点 rsp≡0 (mod 16)。
每个内建体在寄存器保存之后一次性 sub rsp,0x60 作为 API 栈参区（0x20 影子 +
最多 6 个栈参 0x40），所有出口统一走 _ps_ret（add rsp,0x60 → 恢复寄存器 →
push_rax → 尾声），避免分支上漏还栈。M3V 活寄存器 r12/r13 由保存区保护，体内
scratch 只用已保存的 rbx/r13/r14/r15 与易失寄存器。

原生值模型：整数未装箱（rax 直接返回），布尔为 bool_true/bool_false 指针对象，
null 为 null_obj；STR 布局 [TYPE_STR][+8]=字节长][+16..]=UTF-8 字节。
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
_R12, _R13, _R14, _R15 = 12, 13, 14, 15

# ---- Win32 常量 ----
_CP_UTF8 = 65001                # MultiByteToWideChar 的代码页
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_STILL_ACTIVE = 259             # GetExitCodeProcess 的「仍在运行」读数
_INFINITE = 0xFFFFFFFF
_KILL_CODE = 1                  # TerminateProcess 的退出码（对齐 CPython）
_REAP_MS = 5000                 # 终止后收殓等待上限

# STARTUPINFOW(x64)=104 字节，按 8 对齐预留 112；PROCESS_INFORMATION=24，留 32。
_SI_CB = 104
_SI_SIZE = 112
_PI_SIZE = 32

# 槽表：pid / hProcess / hThread / 退出码 / 状态（0 空槽，1 运行，2 已退出）
_SLOTS = 32
_SLOT = 40
_O_PID = 0
_O_HPROC = 8
_O_HTHREAD = 16
_O_CODE = 24
_O_STATE = 32

_CMD_MAX = 2048                 # 命令行 UTF-8 字节上限
_W_MAX = _CMD_MAX + 1           # UTF-16 单元上限（含终止 NUL）

# 每个内建体在寄存器保存区之后再 sub 出的 API 栈参区（含 0x20 影子空间）。
_FRAME = 0x60

# (槽标签, 名称标签, 导出名)：全部 kernel32 导出，k32_base 引导期已就位。
_APIS = (
    ("ps_p_cpw", "ps_n_cpw", "CreateProcessW"),
    ("ps_p_wfso", "ps_n_wfso", "WaitForSingleObject"),
    ("ps_p_gecp", "ps_n_gecp", "GetExitCodeProcess"),
    ("ps_p_tp", "ps_n_tp", "TerminateProcess"),
    ("ps_p_ch", "ps_n_ch", "CloseHandle"),
    ("ps_p_mbtw", "ps_n_mbtw", "MultiByteToWideChar"),
)


# ------------------------------------------------------------ 帧/取值助手
def _enter(em):
    """保存被调用者寄存器（6 字=48 字节）+ 开 0x60 栈参区，rsp 恒 ≡0 (mod 16)。"""
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12;r13;r14;r15
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x81\xEC" + struct.pack("<i", _FRAME))   # sub rsp,0x60


def _leave(em):
    """还栈参区并恢复寄存器（不返回，供统一出口前奏复用）。"""
    em.emit(b"\x48\x81\xC4" + struct.pack("<i", _FRAME))   # add rsp,0x60
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15;r14;r13;r12
    em.emit(b"\x5B")                                # pop rbx


def _ret(em):
    """统一出口：还栈 → 恢复寄存器 → 结果推入操作数栈 → 尾声。"""
    _leave(em)
    em.push_rax()
    _EMIT_EPILOGUE(em)


def _zext32(em, reg: int):
    """mov r{reg}d, r{reg}d：截断为 32 位并零扩展（and imm32 无法表达 0xFFFFFFFF）。"""
    rex = 0x40 | (0x05 if reg >= 8 else 0)          # REX.R|REX.B 同时扩展 reg 与 rm 字段
    em.emit(bytes([rex, 0x89, 0xC0 | ((reg & 7) << 3) | (reg & 7)]))


def _is_heap(em, reg: int, fail_lbl: str):
    """reg 必须是堆对象指针（落在 [heap_base, heap_base+heap_used)）。"""
    em.mov_rr(_R11, reg)
    em.lea_rip(_RCX, "heap_base")
    em.sub_rr(_R11, _RCX)
    em.cmp_heap_used(_R11)
    em.jcc_rel32(0x83, fail_lbl)                    # jae：不在堆内 → 不是对象


def _is_plain_int(em, reg: int, fail_lbl: str):
    """reg 必须是未装箱整数（= 不落在堆区间内）。"""
    em.mov_rr(_R11, reg)
    em.lea_rip(_RCX, "heap_base")
    em.sub_rr(_R11, _RCX)
    em.cmp_heap_used(_R11)
    em.jcc_rel32(0x82, fail_lbl)                    # jb：在堆内 → 是对象不是整数


def _resolve(em, slot_lbl: str, name_lbl: str, fail_lbl: str):
    """把 slot_lbl 解析出的函数地址留在 rax；解析失败跳 fail_lbl。"""
    em.lea_rip(_RDI, slot_lbl)
    em.lea_rip(_RSI, name_lbl)
    em.call_rel32("ps_api")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, fail_lbl)                    # jz


# ------------------------------------------------------------ 运行时子程序
def _emit_process_runtime(em):
    """ps_* 子程序：API 惰性解析、槽表查找/分配/释放、字节拷贝、退出码缓存。

    这些是内部 helper，不进 NATIVE_BUILTINS、不可被 Matha 源直接调用。跨调用
    只保证 rbx/rbp/r12-r15 由各自的 push/pop 保护；rax/rcx/rdx/rsi/rdi/r8-r11
    视为会被改写。
    """
    # ---- ps_api(rdi=&槽位, rsi=ANSI 导出名) -> rax=函数地址（0 表示解析失败） ----
    # 结果写回槽位，故每个 API 只解析一次。
    em.label_here("ps_api")
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_rr(_RBX, _RDI)
    em.mov_rd_mem(_RAX, _RBX, 0)
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x85, "ps_api_done")               # jne：已解析
    em.load_rip_to(_RCX, "k32_base")                # rcx=kernel32 HMODULE
    em.mov_rr(_RDX, _RSI)
    em.call_rip_indirect("api_GetProcAddress")      # rax=proc|0
    em.mov_mem_r(_RBX, 0, _RAX)
    em.label_here("ps_api_done")
    em.mov_rd_mem(_RAX, _RBX, 0)
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")

    # ---- ps_copy(rdi=dst, rsi=src, rdx=n)：rep movsb（不追加 NUL） ----
    em.label_here("ps_copy")
    em.mov_rr(_RCX, _RDX)
    em.emit(b"\xF3\x48\xA4")                        # rep movsb（64 位计数）
    em.emit(b"\xC3")

    # ---- ps_alloc() -> rax=&空槽（state==0），满表 → 0 ----
    em.label_here("ps_alloc")
    em.lea_rip(_RAX, "ps_slots")
    em.mov_r_imm32(_R8, _SLOTS)
    em.label_here("ps_alloc_loop")
    em.mov_rd_mem(_R10, _RAX, _O_STATE)
    em.test_rr(_R10, _R10)
    em.jcc_rel32(0x84, "ps_alloc_hit")              # jz：本槽空闲
    em.add_ri(_RAX, _SLOT)
    em.dec_r(_R8)
    em.jcc_rel32(0x85, "ps_alloc_loop")             # jne：还有槽位未扫
    em.xor_rr32(_RAX, _RAX)
    em.label_here("ps_alloc_hit")
    em.emit(b"\xC3")

    # ---- ps_find(rdi=pid) -> rax=&槽，无记录 → 0 ----
    # 空闲槽的 pid 恒为 0，调用方先排除 pid<=0，故命中即活记录。
    em.label_here("ps_find")
    em.lea_rip(_RAX, "ps_slots")
    em.mov_r_imm32(_R8, _SLOTS)
    em.label_here("ps_find_loop")
    em.mov_rd_mem(_R10, _RAX, _O_PID)
    em.cmp_rr(_R10, _RDI)
    em.jcc_rel32(0x84, "ps_find_hit")               # jz：命中
    em.add_ri(_RAX, _SLOT)
    em.dec_r(_R8)
    em.jcc_rel32(0x85, "ps_find_loop")
    em.xor_rr32(_RAX, _RAX)
    em.label_here("ps_find_hit")
    em.emit(b"\xC3")

    # ---- ps_close(rdi=句柄)：CloseHandle（0 句柄 no-op，解析失败静默跳过） ----
    em.label_here("ps_close")
    em.test_rr(_RDI, _RDI)
    em.jcc_rel32(0x84, "ps_close_ret")
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_rr(_RBX, _RDI)
    _resolve(em, "ps_p_ch", "ps_n_ch", "ps_close_out")
    em.mov_rr(_R11, _RAX)                           # r11=CloseHandle
    em.mov_rr(_RCX, _RBX)
    em.emit(b"\x41\xFF\xD3")                        # call r11
    em.label_here("ps_close_out")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x5B")                                # pop rbx
    em.label_here("ps_close_ret")
    em.emit(b"\xC3")

    # ---- ps_free(rdi=&槽)：关两个句柄并把槽位清零（pid 亦清，记录随之消失） ----
    em.label_here("ps_free")
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_rr(_RBX, _RDI)
    em.mov_rd_mem(_RDI, _RBX, _O_HPROC)
    em.call_rel32("ps_close")
    em.mov_rd_mem(_RDI, _RBX, _O_HTHREAD)
    em.call_rel32("ps_close")
    em.xor_rr32(_RAX, _RAX)
    for off in (_O_PID, _O_HPROC, _O_HTHREAD, _O_CODE, _O_STATE):
        em.mov_mem_r(_RBX, off, _RAX)
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")

    # ---- ps_note_exit(rdi=&槽)：读退出码；真退出则缓存并置 state=2 ----
    # STILL_ACTIVE 视为「仍在运行」，不改状态、不写缓存（读数口径由内建返回 null）。
    em.label_here("ps_note_exit")
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_rr(_RBX, _RDI)
    _resolve(em, "ps_p_gecp", "ps_n_gecp", "ps_note_out")
    em.mov_rr(_R11, _RAX)                           # r11=GetExitCodeProcess
    em.mov_rd_mem(_RCX, _RBX, _O_HPROC)
    em.test_rr(_RCX, _RCX)
    em.jcc_rel32(0x84, "ps_note_out")               # 句柄已关 → 无从判定
    em.lea_rip(_RDX, "ps_code")
    em.emit(b"\x41\xFF\xD3")                        # call r11（GetExitCodeProcess）
    _zext32(em, _RAX)                               # BOOL 返回：高位未定义，先截断
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, "ps_note_out")               # 调用失败 → 无从判定
    em.load_rip_to(_R10, "ps_code")
    _zext32(em, _R10)                               # 只取低 32 位 DWORD
    em.cmp_ri(_R10, _STILL_ACTIVE)
    em.jcc_rel32(0x84, "ps_note_out")               # 仍在运行 → 不缓存
    em.mov_mem_r(_RBX, _O_CODE, _R10)
    em.mov_r_imm32(_R10, 2)
    em.mov_mem_r(_RBX, _O_STATE, _R10)
    em.label_here("ps_note_out")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")


# ------------------------------------------------------------ 内建发射器
def _emit_builtin_spawn(em):
    """派生映像(cmd) → Int：CreateProcessW 派生子进程，返回 pid；失败 -1。"""
    bad = "ps_sp_bad"
    done = "ps_sp_done"
    em.label_here("fn:派生映像")
    _EMIT_PROLOGUE(em, 1, 1)                        # cmd=[rbp-8]
    _enter(em)
    em.mov_rd_mem(_R15, _RBP, -8)                   # r15=cmd
    _is_heap(em, _R15, bad)                         # 必须是堆对象
    em.mov_rd_mem(_R11, _R15, 0)
    em.cmp_ri(_R11, TYPE_STR)
    em.jcc_rel32(0x85, bad)                         # 且必须是 STR
    em.mov_rd_mem(_R14, _R15, 8)                    # r14=字节长
    em.test_rr(_R14, _R14)
    em.jcc_rel32(0x84, bad)                         # 空串 → 失败
    em.cmp_ri(_R14, _CMD_MAX)
    em.jcc_rel32(0x87, bad)                         # ja：超缓冲上限
    em.call_rel32("ps_alloc")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, bad)                         # 满表 → 失败
    em.mov_rr(_R13, _RAX)                           # r13=&slot
    # UTF-8 → ps_mbuf（补 NUL）→ MultiByteToWideChar → ps_wbuf
    em.lea_rip(_RDI, "ps_mbuf")
    em.lea_mem(_RSI, _R15, 16)
    em.mov_rr(_RDX, _R14)
    em.call_rel32("ps_copy")
    em.lea_rip(_RAX, "ps_mbuf")
    em.add_rr(_RAX, _R14)
    em.mov_m8_ri(_RAX, 0, 0)                        # 终止 NUL
    _resolve(em, "ps_p_mbtw", "ps_n_mbtw", "ps_sp_free")
    em.mov_r_imm32(_RCX, _CP_UTF8)
    em.xor_rr32(_RDX, _RDX)                         # dwFlags=0
    em.lea_rip(_R8, "ps_mbuf")
    em.mov_r_imm64(_R9, -1)                         # cbMultiByte=-1（NUL 结尾）
    em.lea_rip(_R10, "ps_wbuf")
    em.mov_mem_r(_RSP, 0x20, _R10)                  # lpWideCharStr
    em.mov_r_imm32(_R10, _W_MAX)
    em.mov_mem_r(_RSP, 0x28, _R10)                  # cWideCharLen
    em.emit(b"\xFF\xD0")                            # call rax（MultiByteToWideChar）
    _zext32(em, _RAX)                               # 返回 cWideCharLen（DWORD，高位未定义）
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, "ps_sp_free")                # 转换失败 → 释放槽位
    # STARTUPINFOW：全零 + cb=104（bss 载入即零，仍显式清零以免跨调用残留）
    em.lea_rip(_RDI, "ps_si")
    em.xor_rr32(_RAX, _RAX)
    for off in range(0, _SI_SIZE, 8):
        em.mov_mem_r(_RDI, off, _RAX)
    em.emit(b"\x48\xC7\x07" + struct.pack("<i", _SI_CB))   # mov qword[rdi],104
    _resolve(em, "ps_p_cpw", "ps_n_cpw", "ps_sp_free")
    em.mov_rr(_R11, _RAX)                           # r11=CreateProcessW
    em.xor_rr32(_RCX, _RCX)                         # lpApplicationName=NULL
    em.lea_rip(_RDX, "ps_wbuf")                     # lpCommandLine
    em.xor_rr32(_R8, _R8)                           # pProcessAttributes=NULL
    em.xor_rr32(_R9, _R9)                           # pThreadAttributes=NULL
    em.mov_r_imm32(_R10, 1)
    em.mov_mem_r(_RSP, 0x20, _R10)                  # bInheritHandles=TRUE
    em.xor_rr32(_RSI, _RSI)
    em.mov_mem_r(_RSP, 0x28, _RSI)                  # dwCreationFlags=0（继承控制台）
    em.mov_mem_r(_RSP, 0x30, _RSI)                  # lpEnvironment=NULL
    em.mov_mem_r(_RSP, 0x38, _RSI)                  # lpCurrentDirectory=NULL
    em.lea_rip(_R10, "ps_si")
    em.mov_mem_r(_RSP, 0x40, _R10)                  # lpStartupInfo
    em.lea_rip(_R10, "ps_pi")
    em.mov_mem_r(_RSP, 0x48, _R10)                  # lpProcessInformation
    em.emit(b"\x41\xFF\xD3")                        # call r11（CreateProcessW）
    _zext32(em, _RAX)                               # BOOL 返回：高位未定义，先截断
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, "ps_sp_free")                # BOOL 0 → 失败
    # 成功：pi=[hProcess, hThread, pid|tid, ...]，槽位记 pid 与两个句柄
    em.lea_rip(_R10, "ps_pi")
    em.mov_rd_mem(_R11, _R10, 0)
    em.mov_mem_r(_R13, _O_HPROC, _R11)
    em.mov_rd_mem(_R11, _R10, 8)
    em.mov_mem_r(_R13, _O_HTHREAD, _R11)
    em.mov_rd_mem(_R11, _R10, 16)
    _zext32(em, _R11)                             # 低 32 位=dwProcessId
    em.mov_mem_r(_R13, _O_PID, _R11)
    em.mov_rr(_RAX, _R11)                           # 返回值 = pid
    em.mov_r_imm32(_R11, 1)
    em.mov_mem_r(_R13, _O_STATE, _R11)              # state=运行
    em.jcc_rel32(None, done)
    em.label_here("ps_sp_free")
    em.mov_rr(_RDI, _R13)
    em.call_rel32("ps_free")                        # 撤销半开槽位
    em.label_here(bad)
    em.mov_r_imm64(_RAX, -1)
    em.label_here(done)
    _ret(em)


def _emit_builtin_wait(em):
    """等候映像(pid)(ms) → Bool：时限内退出=真，仍在跑=假，无记录=null。"""
    none_lbl = "ps_wt_none"
    done = "ps_wt_done"
    em.label_here("fn:等候映像")
    _EMIT_PROLOGUE(em, 2, 2)                        # pid=[rbp-16] ms=[rbp-8]
    _enter(em)
    em.mov_rd_mem(_R15, _RBP, -16)
    em.mov_rd_mem(_R14, _RBP, -8)
    _is_plain_int(em, _R15, none_lbl)
    _is_plain_int(em, _R14, none_lbl)
    em.cmp_ri(_R15, 1)
    em.jcc_rel32(0x8C, none_lbl)                    # jl：pid<=0 无记录
    em.mov_rr(_RDI, _R15)
    em.call_rel32("ps_find")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, none_lbl)
    em.mov_rr(_R13, _RAX)
    em.mov_rd_mem(_R15, _R13, _O_HPROC)
    em.test_rr(_R15, _R15)
    em.jcc_rel32(0x84, none_lbl)                    # 句柄已关 → 无定义
    _resolve(em, "ps_p_wfso", "ps_n_wfso", none_lbl)
    em.mov_rr(_R11, _RAX)                           # r11=WaitForSingleObject
    em.mov_rr(_RCX, _R15)                           # hProcess
    em.mov_rr(_RDX, _R14)
    em.cmp_ri(_RDX, 0)
    em.jcc_rel32(0x89, "ps_wt_to")                  # jns：非负按时限用
    em.mov_r_imm32(_RDX, _INFINITE)                 # ms<0 → INFINITE
    em.label_here("ps_wt_to")
    _zext32(em, _RDX)                             # DWORD 时限
    em.emit(b"\x41\xFF\xD3")                        # call r11（WaitForSingleObject）
    _zext32(em, _RAX)                               # DWORD 返回：高位未定义，先截断
    em.cmp_ri(_RAX, _WAIT_OBJECT_0)
    em.jcc_rel32(0x85, "ps_wt_timeout")
    em.mov_rr(_RDI, _R13)
    em.call_rel32("ps_note_exit")                   # 已退出 → 缓存退出码
    em.lea_rip(_RAX, "bool_true")
    em.jcc_rel32(None, done)
    em.label_here("ps_wt_timeout")
    em.cmp_ri(_RAX, _WAIT_TIMEOUT)
    em.jcc_rel32(0x85, none_lbl)                    # WAIT_FAILED 等 → null
    em.lea_rip(_RAX, "bool_false")
    em.jcc_rel32(None, done)
    em.label_here(none_lbl)
    em.lea_rip(_RAX, "null_obj")
    em.label_here(done)
    _ret(em)


def _emit_builtin_exit_code(em):
    """映像退出码(pid) → Int：已退出给码，仍在跑/无记录给 null（不哨兵冒充）。"""
    none_lbl = "ps_ec_none"
    done = "ps_ec_done"
    em.label_here("fn:映像退出码")
    _EMIT_PROLOGUE(em, 1, 1)                        # pid=[rbp-8]
    _enter(em)
    em.mov_rd_mem(_R15, _RBP, -8)
    _is_plain_int(em, _R15, none_lbl)
    em.cmp_ri(_R15, 1)
    em.jcc_rel32(0x8C, none_lbl)                    # jl：pid<=0 无记录
    em.mov_rr(_RDI, _R15)
    em.call_rel32("ps_find")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, none_lbl)
    em.mov_rr(_R13, _RAX)
    em.mov_rd_mem(_R11, _R13, _O_STATE)
    em.cmp_ri(_R11, 2)
    em.jcc_rel32(0x85, "ps_ec_probe")               # jne：未标记退出 → 现查
    em.mov_rd_mem(_RAX, _R13, _O_CODE)              # 已缓存 → 直接给读数
    em.jcc_rel32(None, done)
    em.label_here("ps_ec_probe")
    em.mov_rd_mem(_R11, _R13, _O_HPROC)
    em.test_rr(_R11, _R11)
    em.jcc_rel32(0x84, none_lbl)                    # 句柄已关且未缓存 → 无定义
    em.mov_rr(_RDI, _R13)
    em.call_rel32("ps_note_exit")                   # 可能把 state 推到 2
    em.mov_rd_mem(_R11, _R13, _O_STATE)
    em.cmp_ri(_R11, 2)
    em.jcc_rel32(0x85, none_lbl)                    # 仍在运行 → 读数无定义
    em.mov_rd_mem(_RAX, _R13, _O_CODE)
    em.jcc_rel32(None, done)
    em.label_here(none_lbl)
    em.lea_rip(_RAX, "null_obj")
    em.label_here(done)
    _ret(em)


def _emit_builtin_kill(em):
    """终止映像(pid) → Bool：TerminateProcess(1) + 收殓等待，成功=真。"""
    none_lbl = "ps_kl_none"
    done = "ps_kl_done"
    em.label_here("fn:终止映像")
    _EMIT_PROLOGUE(em, 1, 1)                        # pid=[rbp-8]
    _enter(em)
    em.mov_rd_mem(_R15, _RBP, -8)
    _is_plain_int(em, _R15, none_lbl)
    em.cmp_ri(_R15, 1)
    em.jcc_rel32(0x8C, none_lbl)
    em.mov_rr(_RDI, _R15)
    em.call_rel32("ps_find")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, none_lbl)
    em.mov_rr(_R13, _RAX)
    em.mov_rd_mem(_R11, _R13, _O_STATE)
    em.cmp_ri(_R11, 2)
    em.jcc_rel32(0x84, "ps_kl_gone")                 # 已退出 → 假（无可终止对象）
    em.mov_rd_mem(_R15, _R13, _O_HPROC)
    em.test_rr(_R15, _R15)
    em.jcc_rel32(0x84, none_lbl)
    _resolve(em, "ps_p_tp", "ps_n_tp", none_lbl)
    em.mov_rr(_R11, _RAX)                           # r11=TerminateProcess
    em.mov_rr(_RCX, _R15)
    em.mov_r_imm32(_RDX, _KILL_CODE)
    em.emit(b"\x41\xFF\xD3")                        # call r11（TerminateProcess）
    _zext32(em, _RAX)                               # BOOL 返回：高位未定义，先截断
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, none_lbl)
    # 收殓：等子进程真正结束（最多 5s），使 映像退出码 立即可读到 1
    _resolve(em, "ps_p_wfso", "ps_n_wfso", "ps_kl_exit")
    em.mov_rr(_R11, _RAX)
    em.mov_rd_mem(_RCX, _R13, _O_HPROC)
    em.mov_r_imm32(_RDX, _REAP_MS)
    em.emit(b"\x41\xFF\xD3")                        # call r11
    em.label_here("ps_kl_exit")
    em.mov_rr(_RDI, _R13)
    em.call_rel32("ps_note_exit")
    em.lea_rip(_RAX, "bool_true")
    em.jcc_rel32(None, done)
    em.label_here("ps_kl_gone")
    em.lea_rip(_RAX, "bool_false")                  # 已退出：无「可终止」这件事发生
    em.jcc_rel32(None, done)
    em.label_here(none_lbl)
    em.lea_rip(_RAX, "null_obj")
    em.label_here(done)
    _ret(em)


def _emit_builtin_close(em):
    """关闭映像(pid) → Bool：关句柄并释放槽位；无记录 → null。"""
    none_lbl = "ps_cl_none"
    done = "ps_cl_done"
    em.label_here("fn:关闭映像")
    _EMIT_PROLOGUE(em, 1, 1)                        # pid=[rbp-8]
    _enter(em)
    em.mov_rd_mem(_R15, _RBP, -8)
    _is_plain_int(em, _R15, none_lbl)
    em.cmp_ri(_R15, 1)
    em.jcc_rel32(0x8C, none_lbl)
    em.mov_rr(_RDI, _R15)
    em.call_rel32("ps_find")
    em.test_rr(_RAX, _RAX)
    em.jcc_rel32(0x84, none_lbl)
    em.mov_rr(_R13, _RAX)
    em.mov_rr(_RDI, _R13)
    em.call_rel32("ps_free")
    em.lea_rip(_RAX, "bool_true")
    em.jcc_rel32(None, done)
    em.label_here(none_lbl)
    em.lea_rip(_RAX, "null_obj")
    em.label_here(done)
    _ret(em)


# ------------------------------------------------------------ 静态区
def emit_process_bss(eb):
    """在 .bss 预留 API 槽、句柄槽表、命令行缓冲与 STARTUPINFO/PROCESS_INFORMATION。"""
    eb.align(8)
    for slot_lbl, _name_lbl, _api in _APIS:
        eb.label_here(slot_lbl)
        eb.emit_virtual(8)
    eb.align(8)
    eb.label_here("ps_code")                        # GetExitCodeProcess 出参
    eb.emit_virtual(8)
    eb.align(8)
    eb.label_here("ps_slots")
    eb.emit_virtual(_SLOTS * _SLOT)
    eb.align(8)
    eb.label_here("ps_mbuf")                        # UTF-8 命令行（含 NUL）
    eb.emit_virtual(_CMD_MAX + 1)
    eb.align(8)
    eb.label_here("ps_wbuf")                        # UTF-16 命令行（含 NUL）
    eb.emit_virtual(2 * _W_MAX)
    eb.align(16)
    eb.label_here("ps_si")                          # STARTUPINFOW
    eb.emit_virtual(_SI_SIZE)
    eb.align(8)
    eb.label_here("ps_pi")                          # PROCESS_INFORMATION
    eb.emit_virtual(_PI_SIZE)


def emit_process_data(ed):
    """在 .data 发射 kernel32 导出名（ANSI，供 GetProcAddress）。"""
    for _slot_lbl, name_lbl, api in _APIS:
        ed.align(8)
        ed.label_here(name_lbl)
        ed.emit(api.encode("ascii") + b"\x00")
