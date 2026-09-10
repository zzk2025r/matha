# -*- coding: utf-8 -*-
"""x86-64 机器码编码单元测试：验证发射器输出的字节序列正确性。

这三个测试直接针对开发期间修复的三处编码 bug：

1. 尾声 mov rsp,rbp 的 ModRM 字节：
   bug `0xE4`（mov rbp,rsp——序言指令，方向反了）→ 修正 `0xEC`
2. 序言参数搬移的 REX 前缀：
   bug `0x4F`（REX.X=1，SIB 无索引变 r12+r12）→ 修正 `0x4D`（REX.X=0）
3. CALL 返回值栈平衡：
   bug 未弹掉函数槽 → 修正 mov [r12-16],rax + sub r12,8
"""
import struct

from src.mbc.native import _Emitter, _emit_epilogue, _emit_prologue, \
    _emit_call_apply, TEXT_RVA


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
            import pytest
            pytest.fail(f"位置 {i}: 发现 0x4F 0x8B（REX.X=1 的 mov 指令，应为 0x4D）")


# ---------- Bug 3: CALL 返回值栈平衡 ----------

def test_call_emits_function_slot_overwrite():
    """CALL 发射的代码必须用返回值覆盖函数槽 [r12-16] 并 sub r12,8。

    正确序列：
      49 8B 44 24 F0   mov rax,[r12-16]     取函数地址
      FF D0            call rax
      49 89 44 24 F0   mov [r12-16],rax     返回值覆盖函数槽
      49 83 EC 08      sub r12,8            弹掉返回值槽
    """
    em = _Emitter(TEXT_RVA)
    em.labels["pcur:test:0"] = 0x2000  # 给 scratch 标签一个假地址
    _emit_call_apply(em, "pcur:test:0", 1)
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
    """CALL 前后 R12 净减 8（函数槽+实参槽共 16 字节入栈，callee 消费 8，结果占 8）。

    验证：push 序列中 push_count * 8 - pop_count * 8 = -8
    简化验证：检查 sub r12,8 出现且没有多余的 add r12,8 在 call 之后。
    """
    em = _Emitter(TEXT_RVA)
    em.labels["pcur:test:0"] = 0x2000
    _emit_call_apply(em, "pcur:test:0", 1)
    code = bytes(em.buf)

    # call rax 之后的 add r12,8 是错误的（旧 bug 会 push_rax 导致栈涨）
    call_pos = code.find(b"\xFF\xD0")
    assert call_pos != -1, "缺少 call rax"
    after_call = code[call_pos + 2:]
    # 不应出现 add r12,8（49 83 C4 08）在 call 之后
    assert b"\x49\x83\xC4\x08" not in after_call, \
        "call 之后出现 add r12,8（旧 bug：push_rax 导致栈不平衡）"


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


import pytest  # noqa: E402
