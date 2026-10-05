# -*- coding: utf-8 -*-
"""x86-64 机器码编码单元测试：验证发射器输出的字节序列正确性。

这三个测试直接针对开发期间修复的三处编码 bug：

1. 尾声 mov rsp,rbp 的 ModRM 字节：
   bug `0xE4`（mov rbp,rsp——序言指令，方向反了）→ 修正 `0xEC`
2. 序言参数搬移的 REX 前缀：
   bug `0x4F`（REX.X=1，SIB 无索引变 r12+r12）→ 修正 `0x4D`（REX.X=0）
 3. CALL 返回值栈平衡：
    bug 未弹掉函数槽 → 修正为 mov [r12-16],rax + sub r12,8
    （N 个实参槽由 callee 序言的 sub r12,8N 消费，该尾序列与 N 无关）
"""
import struct

import pytest

from src.mbc.native import _Emitter, _emit_epilogue, _emit_prologue, \
    _emit_call, MAX_NATIVE_ARITY, TEXT_RVA


# ---------- Bug 1: 尾声 mov rsp,rbp ModRM ----------

def test_epilogue_mov_rsp_rbp_modrm():
    """尾声首字节必须是 48 89 EC（mov rsp,rbp），不能是 48 89 E4（mov rbp,rsp）。

    ModRM 字段解析（Mod=11, reg, rm）：
      EC = 11_101_100 → reg=rbp(5), rm=rsp(4) → mov rsp,rbp  ✓
      E4 = 11_100_100 → reg=rsp(4), rm=rbp(5) → mov rbp,rsp  ✗（序言指令）
    """
    em = _Emitter(TEXT_RVA)
    _emit_epilogue(em)
    code = bytes(em.buf)
    # 完整尾声：48 89 EC 5D C3
    assert code == b"\x48\x89\xEC\x5D\xC3", \
        f"尾声字节错误：期望 48 89 EC 5D C3，实际 {code.hex(' ')}"
    # 逐字节检查 ModRM
    assert code[2] == 0xEC, \
        f"ModRM 字节应为 0xEC（mov rsp,rbp），实际 0x{code[2]:02X}（mov rbp,rsp）"


def test_epilogue_does_not_emit_prologue_instruction():
    """尾声不能误发射序言指令 mov rbp,rsp（48 89 E5）或 mov rbp,rsp（48 89 E4）。"""
    em = _Emitter(TEXT_RVA)
    _emit_epilogue(em)
    code = bytes(em.buf)
    assert b"\x48\x89\xE4" not in code, "尾声误含 48 89 E4（mov rbp,rsp——序言方向）"
    assert b"\x48\x89\xE5" not in code or code[:3] != b"\x48\x89\xE5", \
        "尾声误含 48 89 E5（mov rbp,rsp——序言指令）"


# ---------- Bug 2: 序言参数搬移 REX 前缀 ----------

def test_prologue_param_move_rex_prefix():
    """单参数函数序言的参数搬移指令 REX 前缀必须是 0x4D（W+R+B，X=0）。

    指令：mov r10,[r12+disp8]
    REX 位：W=1(64bit), R=1(reg=r10), X=0(无索引), B=1(base=r12)
    0x4D = 0100_1101 = W+R+B  ✓
    0x4F = 0100_1111 = W+R+X+B（X=1 会使 SIB 的 index 字段 100 变为 r12） ✗
    """
    em = _Emitter(TEXT_RVA)
    _emit_prologue(em, arity=1, nlocals=1)
    code = bytes(em.buf)

    # 序言：55 48 89 E5 48 83 EC 20 4D 8B 54 24 F8 4C 89 95 F8 FF FF FF 49 83 EC 08
    # 找参数搬移指令：REX + 8B + ModRM(54) + SIB(24) + disp8
    found = False
    for i in range(len(code) - 4):
        if code[i] == 0x4D and code[i+1] == 0x8B and code[i+2] == 0x54 \
                and code[i+3] == 0x24:
            found = True
            break
    assert found, "未找到 mov r10,[r12+disp8] 指令"

    # 确认不是 0x4F（旧的错误 REX 前缀）
    for i in range(len(code) - 4):
        if code[i] == 0x4F and code[i+1] == 0x8B and code[i+2] == 0x54 \
                and code[i+3] == 0x24:
            pytest.fail(f"REX 前缀仍为 0x4F（REX.X=1，会导致 r12+r12 双重基址）")


def test_prologue_rex_4f_not_present():
    """整个序言中不能出现 0x4F 作为 REX 前缀（任何 4F 8B 组合都是错误的）。"""
    em = _Emitter(TEXT_RVA)
    _emit_prologue(em, arity=2, nlocals=2)
    code = bytes(em.buf)
    for i in range(len(code) - 1):
        if code[i] == 0x4F and code[i+1] == 0x8B:
            pytest.fail(f"位置 {i}: 发现 0x4F 0x8B（REX.X=1 的 mov 指令，应为 0x4D）")


# ---------- Bug 3: CALL 返回值栈平衡 ----------

def test_call_emits_function_slot_overwrite():
    """CALL N 发射的代码必须用返回值落到 [r12-16] 并 sub r12,8。

    新契约：调用委托运行时 apply_rt（rdi=函数值, rsi=实参基址, rdx=实参数），
    调用点的尾序列对返回值统一：
      49 89 44 24 F0   mov [r12-16],rax     返回值覆盖函数槽
      49 83 EC 08      sub r12,8            弹掉返回值槽
    """
    em = _Emitter(TEXT_RVA)
    _emit_call(em, 1, "main", 0)
    code = bytes(em.buf)

    # 检查关键序列
    expected = b"\x49\x89\x44\x24\xF0"  # mov [r12-16],rax
    assert expected in code, \
        f"缺少 mov [r12-16],rax（返回值覆盖函数槽），实际：{code.hex(' ')}"

    # 检查 sub r12,8 在覆盖之后
    overwrite_pos = code.find(expected)
    sub_seq = b"\x49\x83\xEC\x08"
    sub_pos = code.find(sub_seq, overwrite_pos)
    assert sub_pos != -1, \
        "缺少 sub r12,8（弹掉返回值槽），或位置在覆盖之前"


def test_call_stack_net_decrease_8():
    """CALL N 委托 apply_rt，调用点尾序列与 N 无关且不出现 push/add r12,8。

    序言 sub r12,8N 消费实参；调用点 mov [r12-16],rax + sub r12,8 把
    「函数块 + N 实参」换成单个返回值槽。闭包/偏应用也经 apply_rt 保持该不变量。
    """
    em = _Emitter(TEXT_RVA)
    _emit_call(em, 1, "main", 0)
    code = bytes(em.buf)

    # 尾序列之后不应出现 add r12,8（旧 bug：push_rax 导致栈涨）
    assert b"\x49\x83\xC4\x08" not in code, \
        "CALL 中出现 add r12,8（旧 bug：push_rax 导致栈不平衡）"


def test_call_tail_is_arity_independent():
    """实参槽由 callee 序言消费，故 CALL N 的尾序列对所有 N 完全一致。"""
    tails = set()
    overwrite = b"\x49\x89\x44\x24\xF0"  # mov [r12-16],rax
    for argc in range(0, MAX_NATIVE_ARITY + 1):
        em = _Emitter(TEXT_RVA)
        _emit_call(em, argc, "main", 0)
        code = bytes(em.buf)
        pos = code.find(overwrite)
        assert pos != -1, f"argc={argc} 缺少返回值覆盖函数槽"
        tails.add(code[pos:])
    assert len(tails) == 1, \
        f"CALL 尾序列随实参数变化（应恒定）：{sorted(t.hex(' ') for t in tails)}"


def test_call_arity_scales_function_slot_offset():
    """CALL N 的函数槽位于 [r12-8*(N+1)]，随 N 左移。"""
    for argc in range(0, MAX_NATIVE_ARITY + 1):
        em = _Emitter(TEXT_RVA)
        _emit_call(em, argc, "main", 0)
        code = bytes(em.buf)
        # mov rax,[r12+disp8]，disp8 = (-8*(argc+1)) & 0xFF
        want = bytes([0x49, 0x8B, 0x44, 0x24, (-8 * (argc + 1)) & 0xFF])
        assert code.startswith(want), \
            f"argc={argc} 函数槽偏移不符：{code[:5].hex(' ')} != {want.hex(' ')}"


def test_call_rejects_arity_over_limit():
    """超过 MAX_NATIVE_ARITY 的实参数必须显式报错而非错编。"""
    from src.mbc.native import NativeNotSupported
    em = _Emitter(TEXT_RVA)
    try:
        _emit_call(em, MAX_NATIVE_ARITY + 1, "main", 0)
    except NativeNotSupported as exc:
        assert str(MAX_NATIVE_ARITY) in str(exc)
    else:
        raise AssertionError("超过上限的实参数未抛出 NativeNotSupported")


def test_call_moves_args_base_to_rsi():
    """实参基址 rsi = r12 - 8*argc（r12 指向栈顶之上），随 argc 缩放。"""
    for argc in range(1, MAX_NATIVE_ARITY + 1):
        em = _Emitter(TEXT_RVA)
        _emit_call(em, argc, "main", 0)
        code = bytes(em.buf)
        want = b"\x48\x81\xEE" + struct.pack("<i", 8 * argc)
        assert want in code, \
            f"argc={argc} 缺少 sub rsi,8*argc：{code.hex(' ')}"


def test_call_invokes_apply_runtime():
    """函数值入 rdi、实参数入 rdx，并尾调用运行时 apply_rt。"""
    em = _Emitter(TEXT_RVA)
    _emit_call(em, 2, "main", 0)
    code = bytes(em.buf)
    assert b"\x48\x89\xC7" in code, "缺少 mov rdi,rax（函数值 → rdi）"
    assert b"\x48\xC7\xC2" in code, "缺少 mov rdx,argc（实参数 → rdx）"
    assert b"\xE8" in code, "缺少 call apply_rt"


def test_prologue_reads_arguments_in_order():
    """序言第 i 个形参从 [r12-8*(arity-i)] 搬入局部槽，保证 a1 对应形参 0。

    栈上探：最后压入的 aN 在 [r12-8]，a1 在 [r12-8*arity]。
    """
    em = _Emitter(TEXT_RVA)
    _emit_prologue(em, arity=3, nlocals=3)
    code = bytes(em.buf)
    sub_pos = code.find(b"\x49\x83\xEC")
    assert sub_pos != -1, "缺少 sub r12, arity*8"
    for i in range(3):
        want = bytes([0x4D, 0x8B, 0x54, 0x24, (-8 * (3 - i)) & 0xFF])
        assert want in code[:sub_pos], \
            f"形参 {i} 源槽不符：{code[:sub_pos].hex(' ')} 缺 {want.hex(' ')}"


# ---------- 集成验证：字节反汇编一致性 ----------

def test_epilogue_byte_decoding():
    """将尾声字节反汇编验证语义：mov rsp,rbp; pop rbp; ret。"""
    em = _Emitter(TEXT_RVA)
    _emit_epilogue(em)
    code = bytes(em.buf)

    # 48 89 EC: REX.W + mov r/m64, r64, ModRM=EC
    #   Mod=11, reg=101(rbp), rm=100(rsp) → mov rsp, rbp
    assert code[0] == 0x48  # REX.W
    assert code[1] == 0x89  # mov r/m, r
    modrm = code[2]
    mod = (modrm >> 6) & 3
    reg = (modrm >> 3) & 7
    rm = modrm & 7
    assert mod == 3, f"Mod 应为 11（寄存器），实际 {mod}"
    assert reg == 5, f"reg 应为 5（rbp），实际 {reg}"
    assert rm == 4, f"rm 应为 4（rsp），实际 {rm}"
    # 语义：mov rm, reg → mov rsp, rbp ✓


# ---------- PE 节区布局：.data RVA 必须随 .text 大小浮动 ----------

def _pe_sections(pe: bytes) -> dict:
    """解析 PE64 节表，返回 {节名: {vsize, rva, rawsize, rawaddr}}。"""
    off = int.from_bytes(pe[0x3C:0x40], "little")
    nsec = int.from_bytes(pe[off + 6:off + 8], "little")
    optsz = int.from_bytes(pe[off + 20:off + 22], "little")
    base = off + 24 + optsz
    out = {}
    for i in range(nsec):
        b = base + i * 40
        name = pe[b:b + 8].rstrip(b"\x00").decode("latin1")
        vsz, va, rsz, ra = struct.unpack("<IIII", pe[b + 8:b + 24])
        out[name] = dict(vsize=vsz, rva=va, rawsize=rsz, rawaddr=ra)
    return out


@pytest.mark.parametrize("nrec", [1, 2, 3, 4, 5, 8])
def test_data_section_does_not_overlap_text(nrec):
    """.data 起始 RVA 必须按 .text 实际大小对齐，代码跨 4KB 时不得重叠。

    回归：DATA_RVA 曾是固定常量 0x2000，.text 增长到 4KB 以上时两节重叠，
    Windows 拒绝加载该映像（CreateProcess 报 WinError 193）。
    """
    from src.mbc.compiler import compile_source
    from src.mbc.native import compile_to_exe

    decls = "\n".join(
        f"let rec r{i} = (n) => if n == 0 then {i + 1} else r{(i + 1) % nrec}(n - 1) in"
        for i in range(nrec))
    outs = "".join(f"输出(r{i}(6))\n" for i in range(nrec))

    pe = compile_to_exe(decls + "\n" + outs)
    secs = _pe_sections(pe)
    text, data = secs[".text"], secs[".data"]

    text_va_end = text["rva"] + text["vsize"]
    assert data["rva"] >= text_va_end, (
        f".data (rva=0x{data['rva']:X}) 与 .text 末端 (0x{text_va_end:X}) 重叠")
    assert data["rva"] % 0x1000 == 0, \
        f".data RVA 应按 SectionAlignment 0x1000 对齐，实际 0x{data['rva']:X}"


# ---------- PE 节区布局：零填充尾段不得占文件体积 ----------

def test_zero_filled_runtime_state_is_not_file_backed():
    """.data 尾部的恒零运行时状态不得写进文件（回归：exe 曾膨胀到 17MB）。

    8MB 堆 free 区 + 64KB 异常栈 + 2×128KB GC 位图 + 8MB 标记栈共约 16.6MB 全是
    零，此前作为已初始化数据落盘（`.text` 仅 29KB 而 exe 17.2MB）。现改为
    VirtualSize 覆盖全长、SizeOfRawData 截到首个尾零之前，由加载器零填充；
    RVA 布局必须逐字节不变，否则所有 RIP 相对引用都会失效。
    """
    from src.mbc.native import compile_to_exe

    pe = compile_to_exe('输出("hi")\n')
    secs = _pe_sections(pe)
    data = secs[".data"]

    assert data["rawsize"] < 1 << 20, (
        f".data 原始数据仍有 {data['rawsize']} 字节，零填充回归")
    assert data["rawsize"] < data["vsize"], (
        ".data 必须存在不落盘的零填充尾段")
    assert data["vsize"] > 16 << 20, (
        f".data 虚拟跨度 {data['vsize']} 应覆盖堆/位图/标记栈")
    assert len(pe) < 1 << 20, f"exe 体积 {len(pe)} 字节异常（历史值 17.2MB）"

    # raw 尾部到 vsize 末尾必须全是「未初始化」区域：
    # 文件里最后一节数据的末尾即 data_rva + rawsize，之后无内容。
    tail_end = data["rawaddr"] + data["rawsize"]
    assert tail_end == len(pe), (
        f"文件应在 .data 原始数据末尾结束（{tail_end} vs {len(pe)}）")


# ---------- repr 的 C1 分支：SIB「无索引」与 cmp cl 的 ModRM ----------

def _text_bytes(src: str) -> bytes:
    """编译一段源码并返回其 .text 节的原始机器码。"""
    from src.mbc.native import compile_to_exe

    pe = compile_to_exe(src)
    sec = _pe_sections(pe)[".text"]
    return pe[sec["rawaddr"]:sec["rawaddr"] + sec["rawsize"]]


def test_sib_no_index_field_must_be_100_not_000():
    """`movzx ecx, byte [r15+1]` 的 SIB 必须是 0x27，不能是 0x07。

    SIB 字节布局：scale(2) | index(3) | base(3)。64 位模式下 index=100
    且 REX.X=0 表示「无索引」；index=000 表示**真的拿 RAX 当索引**。

      0x27 = 00_100_111 → index=100(无索引) + base=111+REX.B=r15 → [r15+1]   ✓
      0x07 = 00_000_111 → index=000=RAX       + base=r15      → [r15+rax+1] ✗

    回归：0x07 让 C1 repr 分支读到 [r15+rax+1]，rax 低字节混进地址，
    结果 U+0080 被判成任意码点，输出裸字节而非 \\x80。
    """
    code = _text_bytes('输出(["\\u4e2d"])')
    assert b"\x41\x0F\xB6\x4C\x27\x01" in code, (
        "缺少 movzx ecx,[r15+1] 的正确编码 41 0F B6 4C 27 01（SIB=0x27 无索引）")
    assert b"\x41\x0F\xB6\x4C\x07\x01" not in code, (
        "出现 41 0F B6 4C 07 01：SIB=0x07 的 index=000 会真取 RAX 当索引")


def test_cmp_cl_imm8_modrm_is_rcx_not_rdx():
    """`cmp cl, 0xNN` 的 ModRM 必须是 0xF9（rm=001），不能是 0xFA（rm=010）。

    80 /r ib 的 ModRM.rm 选操作数：F9 = 00_111_001 → rcx(cl)；
    FA = 00_111_010 → rdx(dl)。写错会让比较落到 dl，范围判断恒假，
    C1 控制码分支永远不进（或永远进）。
    """
    code = _text_bytes('输出(["\\u4e2d"])')
    assert b"\x80\xF9\x80" in code, "缺少 cmp cl,0x80（ModRM 应为 F9=rcx）"
    assert b"\x80\xF9\xA1" in code, "缺少 cmp cl,0xA1（ModRM 应为 F9=rcx）"
    # 只针对 C1 分支用到的两个立即数做反向断言：别处确有合法的 cmp dl,...
    assert b"\x80\xFA\x80" not in code, "出现 cmp dl,0x80：rm 字段错，应为 F9(rcx)"
    assert b"\x80\xFA\xA1" not in code, "出现 cmp dl,0xA1：rm 字段错，应为 F9(rcx)"


def test_repr_cmp_al_imm8_is_byte_form():
    """`cmp al, 0xC2` 必须是 3C C2（8 位 al），不是 48 3C C2。

    3C ib 在 64 位模式下依然比较 **al** 这一个字节；加 REX.W 变成
    48 3C C2 会比较整个 rax，低 8 位之外的高位也参与比较而恒不相等。
    """
    code = _text_bytes('输出(["\\u4e2d"])')
    assert b"\x3C\xC2" in code, "缺少 3C C2（cmp al,0xC2）"
    assert b"\x48\x3C\xC2" not in code, "出现 48 3C C2：应比较 al 而非整个 rax"
    assert b"\x80\xF8\xC2" not in code, "出现 80 F8 C2（cmp al 的 80 /r 形式）"
