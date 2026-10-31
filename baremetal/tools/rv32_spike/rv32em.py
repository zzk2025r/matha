# -*- coding: utf-8 -*-
"""P6 SPIKE：M3V 字节码 → RV32IM 机器码直发后端（最小静态 ELF，QEMU virt 可跑）。

与 `src/mbc/native.py`（x86-64 → Windows PE64）同一输入口径：吃
`src.mbc.compiler.compile_source` 的 `MModule`，纯 Python 位级编码直接产出
RV32IM ELF32 —— 不经交叉工具链、不经汇编器，MMIO 直写 ns16550（连 OS ABI 都没有）。

诚实边界（SPIKE，非生产后端；完整设计见同目录 SPIKE_DESIGN.md）：
  - 字节码入口有两个：`compile_module_to_elf`（吃 MModule tuple 指令流）与
    `rv32bc.compile_bytes_to_elf`（吃 MBR1 序列化契约：1B OpCode + N×u32 操作数，
    纯指令/数据指令二分类，见 rv32bc.py）。两入口产物字节一致（runner roundtrip 断言）。
  - 值模型 = 裸 int32 + 编译期标记的堆列表指针/null/bool。字符串值/超 32 位 →
    显式 NotSupportedRV32（PUSH_CONST 指向字符串常量亦显式拒绝，绝不 KeyError）。
  - 正式覆盖 opcode：PUSH_CONST / BINOP(+ - * // % == != < > <=) / CALL /
    RET / OUTPUT / BUILD_LIST / INDEX_GET。静态模式/管道项（不计入正式数）：
    LOAD_GLOBAL/STORE_GLOBAL（全局单元完整语义：int/bool/list/null 均可存读，
    编译期跟踪槽类型）/ LOAD_LOCAL/STORE_LOCAL / JMP/JZ/JNZ（if/elif/else 链
    + while/for 后向回跳的分支全路径；JZ 空表判假与 Python 口径一致）/
    POP/PUSH_NULL（语句位丢弃形状；null 比较编译期静态折叠）/
    PUSH_TRUE/PUSH_FALSE / HALT；内建表 len/get（解锁 for 句型，静态融入发射）。
    集合之外（UNARYOP、MAKE_CLOSURE/间接调用、BUILD_DICT/DUP、字符串/浮点值、
    列表或 null 跨函数边界、arity>2 等）一律显式拒绝，绝不静默产错。
  - 溢出/除零 = 干净失败（非零退出，不伪造值；对齐 native 1a/1c 红线）。

运行约定（QEMU virt rv32, -bios none；见 run_rv32_spike.py）：
  RAM 基址 0x80000000（与 qemu_virt_demo/virt.ld 同）；ns16550 UART@0x10000000；
  退出 ecall(SBI srst, a7=0x6758)。表达式栈：SCRATCH 区向上增长，R_EBP 指针；
  调用栈：CALLSTACK 向下，R_FP 帧链。

门禁隔离：本目录不被 repo_facts / dep_audit / kernel_purity 扫描，不入门禁。
"""
from __future__ import annotations

import struct

from rvcoder import (
    ADD,
    ADDI,
    AND,
    ANDI,
    BEQ,
    BGE,
    BGEU,
    BLT,
    BNE,
    DIV,
    DIVU,
    E32,
    JALR,
    LBU,
    MUL,
    OR,
    RA,
    REM,
    REMU,
    SB,
    SLLI,
    SLT,
    SLTIU,
    SLTU,
    SP,
    SRAI,
    SUB,
    SW,
    XOR,
    XORI,
    ZERO,
    NotSupportedRV32,
)

from src.mbc import opcodes as OP

# ---- 运行态区域（全部固定地址，彼此留充足间距；build 时断言代码 < CODE_GAP） ----
BASE = 0x80000000
CODE_GAP = 0x10000              # 代码段到常量池的固定间距（64KB 字容量）
POOL = BASE + CODE_GAP
GLOB_SIZE = 0x1000
SCRATCH_SIZE = 0x10000
CALLSTACK_SIZE = 0x10000        # 调用栈（向下生长）预留区
HEAP_SIZE = 0x20000             # 列表堆区（bump 分配，首字为分配指针）
INT_MIN = -0x80000000
INT_MAX = 0x7FFFFFFF
TEST_DEV = 0x00100000        # QEMU virt sifive_test（dtb test@100000 实证）

# ---- SPIKE 寄存器分配（自定义 ABI，取互不冲突编号） ----
R_FP = 8
R_CPOOL = 9
R_GLOB = 14
R_UART = 15
R_EBP = 16
R_A0, R_A1 = 10, 11
R_T0, R_T1, R_T2, R_T3, R_T4, R_T5 = 5, 6, 7, 28, 29, 30
# R_CPOOL/R_GLOB/R_UART 为「保留全局寄存器」：用户函数与运行库只读不写。
# R_EBP 仅按 push/pop 调整，绝不整体改值（除 _start 初始化）。

# 正式计入覆盖集的 opcode（数据结构二条为 P6 扩展新增）
SUBSET_OPS = {OP.PUSH_CONST, OP.BINOP, OP.CALL, OP.RET, OP.OUTPUT,
              OP.BUILD_LIST, OP.INDEX_GET}
# 静态模式/管道项（不计入正式数，但 SPIKE 已支持）
PIPELINE_OPS = {OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.LOAD_LOCAL, OP.STORE_LOCAL,
                OP.JMP, OP.JZ, OP.JNZ, OP.PUSH_TRUE, OP.PUSH_FALSE, OP.HALT,
                OP.POP, OP.PUSH_NULL}

_INT_OPS = {"+": "add", "-": "sub", "*": "mul", "//": "fdiv", "%": "mod"}
_CMP_OPS = {"==", "!=", "<", ">", "<="}

# SPIKE 内建函数表（编译期静态分派，解锁 for 句型：len/get 融进发射序列，
# 不建运行时函数对象）。集合外的内建（如 str/dict 相关）仍走「未定义全局」拒绝。
BUILTINS = {"len": 1, "get": 2}


# ---------------------------------------------------------------- 表达式栈

def _push_reg(em, reg):
    em.sw(reg, R_EBP, 0)
    em.addi(R_EBP, R_EBP, 4)


def _push_imm(em, val: int):
    if not INT_MIN <= val <= INT_MAX:
        raise NotSupportedRV32(f"SPIKE 值模型仅 int32：立即数 {val} 越界")
    em.li(R_T0, val)
    _push_reg(em, R_T0)


def _push_at(em, base, off):
    em.lw(R_T0, base, off)
    _push_reg(em, R_T0)


def _pop_to(em, reg):
    em.addi(R_EBP, R_EBP, -4)
    em.lw(reg, R_EBP, 0)


# ---------------------------------------------------------------- 帧

def _local_off(slot: int) -> int:
    return -(24 + 4 * slot)


def _frame_alloc(nlocals: int) -> int:
    return (8 + 4 * nlocals + 15) & ~15


def _emit_frame_setup(em):
    em.addi(SP, SP, -16)
    em.sw(RA, SP, 12)
    em.sw(R_FP, SP, 8)
    em.addi(R_FP, SP, 16)


def _emit_epilogue(em):
    _pop_to(em, R_A0)
    em.lw(RA, R_FP, -4)
    em.lw(R_FP, R_FP, -8)
    em.addi(SP, R_FP, -16)
    em.emit(JALR(ZERO, RA, 0))


# ---------------------------------------------------------------- BINOP

def _emit_binop(em, sym):
    _pop_to(em, R_T1)                     # b（右）
    _pop_to(em, R_T0)                     # a（左）
    if sym in _CMP_OPS:
        _emit_cmp(em, sym)
        return
    kind = _INT_OPS.get(sym)
    if kind is None:
        raise NotSupportedRV32(f"SPIKE 不支持 BINOP 运算符 {sym!r}")
    if kind == "add":
        em.emit(ADD(R_T2, R_T0, R_T1))
        em.emit(XOR(R_T3, R_T0, R_T2))            # a ^ sum
        em.emit(XOR(R_T4, R_T1, R_T2))            # b ^ sum
        em.emit(AND(R_T3, R_T3, R_T4))
        _fail_if_neg(em, R_T3)
        _push_reg(em, R_T2)
    elif kind == "sub":
        em.emit(SUB(R_T2, R_T0, R_T1))
        em.emit(XOR(R_T3, R_T0, R_T1))            # a ^ b
        em.emit(XOR(R_T4, R_T0, R_T2))            # a ^ diff
        em.emit(AND(R_T3, R_T3, R_T4))
        _fail_if_neg(em, R_T3)
        _push_reg(em, R_T2)
    elif kind == "mul":
        em.emit(MUL(R_T2, R_T0, R_T1))
        _fail_if_mul_overflow(em)
        _push_reg(em, R_T2)
    elif kind == "fdiv":
        _fail_if_zero(em, R_T1)
        em.emit(DIV(R_T2, R_T0, R_T1))            # 截断商
        em.emit(REM(R_T4, R_T0, R_T1))            # 截断余
        _fix_floor(em)
        _push_reg(em, R_T2)
    elif kind == "mod":
        _fail_if_zero(em, R_T1)
        em.emit(REM(R_T2, R_T0, R_T1))
        _fix_pymod(em)
        _push_reg(em, R_T2)


def _fail_if_neg(em, reg):
    """reg<0（溢出/负标志）→ 跳 exit_err。"""
    em.emit(BLT(reg, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "exit_err"))


def _fail_if_zero(em, reg):
    """reg==0（除数）→ 跳 exit_err。"""
    em.emit(BEQ(reg, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "exit_err"))


def _fail_if_mul_overflow(em):
    """RV32M 无高位乘：用 (a*b)/a != b 判溢出（a==0 放行）。"""
    done = f"mul_done_{len(em.code)}"
    em.emit(BEQ(R_T0, ZERO, 0))                   # a==0 → done
    em._fix_br.append((len(em.code) - 1, done))
    em.emit(DIV(R_T3, R_T2, R_T0))                # q = (a*b)/a
    em.emit(BNE(R_T3, R_T1, 0))                   # q!=b → 溢出
    em._fix_br.append((len(em.code) - 1, "exit_err"))
    em.label_here(done)


def _fix_floor(em):
    """截断除 → 地板除：r≠0 且 sign(r)!=sign(b) 时 q-=1。"""
    done = f"fl_done_{len(em.code)}"
    em.emit(BEQ(R_T4, ZERO, 0))                   # r==0 → done
    em._fix_br.append((len(em.code) - 1, done))
    em.emit(SRAI(R_T3, R_T4, 31))                 # sign(r)
    em.emit(SRAI(R_T5, R_T1, 31))                 # sign(b)
    em.emit(BEQ(R_T3, R_T5, 0))                   # 同号 → done
    em._fix_br.append((len(em.code) - 1, done))
    em.addi(R_T2, R_T2, -1)
    em.label_here(done)


def _fix_pymod(em):
    """截断取余 → Python 口径：r≠0 且 sign(r)!=sign(b) 时 r+=b。"""
    done = f"pm_done_{len(em.code)}"
    em.emit(BEQ(R_T2, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, done))
    em.emit(SRAI(R_T3, R_T2, 31))
    em.emit(SRAI(R_T5, R_T1, 31))
    em.emit(BEQ(R_T3, R_T5, 0))
    em._fix_br.append((len(em.code) - 1, done))
    em.add(R_T2, R_T2, R_T1)
    em.label_here(done)


def _emit_cmp(em, sym):
    if sym == "==":
        em.emit(XOR(R_T2, R_T0, R_T1))
        em.emit(SLTIU(R_A0, R_T2, 1))
        _push_reg(em, R_A0)
    elif sym == "!=":
        em.emit(XOR(R_T2, R_T0, R_T1))
        em.emit(SLTIU(R_A0, R_T2, 1))
        em.emit(XORI(R_A0, R_A0, 1))
        _push_reg(em, R_A0)
    elif sym == "<":
        em.emit(SLT(R_A0, R_T0, R_T1))
        _push_reg(em, R_A0)
    elif sym == ">":
        em.emit(SLT(R_A0, R_T1, R_T0))
        _push_reg(em, R_A0)
    elif sym == "<=":
        em.emit(SLT(R_A0, R_T1, R_T0))
        em.emit(XORI(R_A0, R_A0, 1))
        _push_reg(em, R_A0)


# ---------------------------------------------------------------- 编译期上下文

class _Ctx:
    """单模块编译共享上下文：常量定位/全局槽/堆区/直调函数名集。"""

    def __init__(self, consts, idx_of, gmap, fnames, heap_base, heap_end):
        self.consts = consts
        self.idx_of = idx_of
        self.gmap = gmap
        self.gtype: dict[int, str] = {}     # 全局槽 → "v"/"bool"/"list"
        self.fnames = fnames
        self.heap_base = heap_base
        self.heap_end = heap_end


# ---------------------------------------------------------------- 列表/索引

def _emit_build_list(em, ctx, n: int):
    """BUILD_LIST n：弹 n 个已检查为标量的栈顶值 → 堆上 [len, e0..en-1]。

    bump 指针存 [heap_base]；容量越界 → exit_err（干净失败，不伪造）。"""
    sz = 4 + 4 * n
    if sz > 0x7FC or 4 * n > 0x7FC:
        raise NotSupportedRV32(f"SPIKE 列表过长（lw/sw 偏移 imm12 限制）：n={n}")
    em.li(R_T2, ctx.heap_base)
    em.lw(R_T0, R_T2, 0)                    # p = bump
    em.addi(R_T1, R_T0, sz)                 # newp
    em.li(R_T3, ctx.heap_end)
    em.emit(BGEU(R_T1, R_T3, 0))            # 堆满 → 干净失败
    em._fix_br.append((len(em.code) - 1, "exit_err"))
    em.li(R_T4, n)
    em.sw(R_T4, R_T0, 0)                    # [p] = len
    for i in range(n):                      # 展开写入：e0 在栈深 -4n，依次 +4
        em.lw(R_T4, R_EBP, -4 * (n - i))
        em.sw(R_T4, R_T0, 4 + 4 * i)
    em.sw(R_T1, R_T2, 0)                    # bump = newp
    em.addi(R_EBP, R_EBP, -4 * n)
    _push_reg(em, R_T0)                     # 列表指针 = 值


def _emit_index_get(em):
    """INDEX_GET：弹 idx(int/bool) + 列表指针 → 压元素。"""
    _pop_to(em, R_T1)                       # idx
    _pop_to(em, R_T0)                       # p
    _index_core(em)


def _index_core(em):
    """R_T0=列表指针, R_T1=下标 → 压入元素（含末步 push）。
    Python 负索引同口径；越界/空表索引 → exit_err（VM 端是 IndexError，同样非零退出）。"""
    pos = f"ig_pos_{len(em.code)}"
    em.lw(R_T2, R_T0, 0)                    # len
    em.emit(BGE(R_T1, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, pos))
    em.add(R_T1, R_T1, R_T2)                # idx<0 → idx += len
    em.emit(BLT(R_T1, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "exit_err"))
    em.label_here(pos)
    em.emit(SLTU(R_T3, R_T1, R_T2))         # 无符号界内：idx < len
    em.emit(BEQ(R_T3, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "exit_err"))
    em.emit(SLLI(R_T1, R_T1, 2))
    em.add(R_T0, R_T0, R_T1)
    em.lw(R_T0, R_T0, 4)
    _push_reg(em, R_T0)


# ---------------------------------------------------------------- 作用域发射

def _emit_null_cmp(em, sym, ta, tb):
    """null 参与比较：编译期静态折叠（值型已知）。
    None==None 真；null vs 非 null 恒假；</>/<= 在 VM 端是 TypeError → 拒绝。"""
    if sym not in ("==", "!="):
        raise NotSupportedRV32(f"SPIKE：null 参与 {sym!r} 排序比较（VM 端 TypeError）")
    both_null = (ta == "null" and tb == "null")
    eq = both_null if sym == "==" else not both_null
    _push_imm(em, 1 if eq else 0)


def _check_scalar(t, where):
    if isinstance(t, tuple):
        raise NotSupportedRV32(f"{where}：函数值不在 SPIKE 值模型（不参与运算/作元素）")
    if t == "list":
        raise NotSupportedRV32(
            f"{where}：列表参与算术/比较/作列表元素 —— 拼接与值相等语义不同于裸 int 运算，未覆盖")


def _check_storable(t, where):
    if isinstance(t, tuple):
        raise NotSupportedRV32(f"{where}：函数值绑定到变量不在 SPIKE 子集")


def _emit_body(em, ctx, code, nlocals, tag, ltype0=None):
    """发射一个作用域指令流。stk：编译期表达式栈值型标记（"v"/"bool"/"list"/
    ("fn",name)），与运行期 R_EBP 槽位同构；list/bool 只允许在单作用域内流转，
    跨函数边界在 CALL/RET 处显式拒绝。"""
    stk: list = []
    ltype: dict[int, str] = dict(ltype0 or {})   # 局部槽 → 值型（冲突拒绝）
    consts = ctx.consts
    for i, ins in enumerate(code):
        em.label_here(f"{tag}:{i}")
        op = ins[0]
        if op == OP.PUSH_CONST:
            c = ctx.consts[ins[1]]
            if isinstance(c, str):
                raise NotSupportedRV32(
                    f"PUSH_CONST 字符串值 {c!r}：SPIKE 值模型仅 int32/列表/bool/null")
            _push_at(em, R_CPOOL, 4 * ctx.idx_of[ins[1]])
            stk.append("v")
        elif op == OP.PUSH_TRUE:
            _push_imm(em, 1); stk.append("bool")
        elif op == OP.PUSH_FALSE:
            _push_imm(em, 0); stk.append("bool")
        elif op == OP.PUSH_NULL:
            _push_imm(em, 0); stk.append("null")   # 占位 0：真值性判自然一致
        elif op == OP.BINOP:
            sym = consts[ins[1]]
            if not isinstance(sym, str):
                raise NotSupportedRV32(f"BINOP 运算符非常量字符串：{sym!r}")
            _need(stk, 2, "BINOP")
            ta, tb = stk[-2], stk[-1]
            if ta == "null" or tb == "null":
                _emit_null_cmp(em, sym, ta, tb)
                del stk[-2:]; stk.append("bool")
                continue
            _check_scalar(ta, f"BINOP {sym!r}")
            _check_scalar(tb, f"BINOP {sym!r}")
            _emit_binop(em, sym)
            del stk[-2:]
            stk.append("bool" if sym in _CMP_OPS else "v")
        elif op == OP.UNARYOP:
            raise NotSupportedRV32("SPIKE 不支持 UNARYOP（负号请用 0 - x）")
        elif op in (OP.LOAD_LOCAL, OP.STORE_LOCAL):
            slot = ins[1]
            if slot >= nlocals:
                raise NotSupportedRV32(f"局部槽 {slot} 越出帧 {nlocals}")
            if op == OP.LOAD_LOCAL:
                _push_at(em, R_FP, _local_off(slot))
                stk.append(ltype.get(slot, "v"))
            else:
                _need(stk, 1, "STORE_LOCAL")
                t = stk[-1]
                _check_storable(t, "STORE_LOCAL")
                old = ltype.get(slot)
                if old is not None and old != t:
                    raise NotSupportedRV32(f"局部槽 {slot} 混型：{old} vs {t}（SPIKE 拒绝）")
                ltype[slot] = t
                _pop_to(em, R_T0); em.sw(R_T0, R_FP, _local_off(slot)); stk.pop()
        elif op in (OP.LOAD_GLOBAL, OP.STORE_GLOBAL):
            name = consts[ins[1]]
            if not isinstance(name, str):
                raise NotSupportedRV32(f"全局名非常量字符串：{name!r}")
            if op == OP.LOAD_GLOBAL:
                if name in ctx.fnames:
                    _push_imm(em, 1)            # 非零占位：真值性判与 VM 一致
                    stk.append(("fn", name))
                elif name in ctx.gmap:
                    _push_at(em, R_GLOB, 4 * ctx.gmap[name])
                    stk.append(ctx.gtype.get(ctx.gmap[name], "v"))
                elif name in BUILTINS:
                    _push_imm(em, 1)
                    stk.append(("bi", name))
                else:
                    raise NotSupportedRV32(
                        f"SPIKE：未定义全局 {name!r}（既非函数/内建也未被赋值，绝不静默读 0）")
            else:
                if name not in ctx.gmap:
                    raise NotSupportedRV32(f"SPIKE：写入未登记全局 {name!r}")
                _need(stk, 1, "STORE_GLOBAL")
                t = stk[-1]
                _check_storable(t, "STORE_GLOBAL")
                slot = ctx.gmap[name]
                old = ctx.gtype.get(slot)
                if old is not None and old != t:
                    raise NotSupportedRV32(f"全局 {name!r} 混型：{old} vs {t}（SPIKE 拒绝）")
                ctx.gtype[slot] = t
                _pop_to(em, R_T0); em.sw(R_T0, R_GLOB, 4 * slot); stk.pop()
        elif op == OP.CALL:
            _emit_call(em, ctx, stk, ins[1])
        elif op == OP.RET:
            _need(stk, 1, "RET")
            t = stk[-1]
            if isinstance(t, tuple):
                raise NotSupportedRV32("SPIKE 不支持返回函数（一阶值）")
            if t == "list":
                raise NotSupportedRV32("SPIKE 不支持列表跨函数边界（返回/传参/闭包）")
            if t == "null":
                raise NotSupportedRV32("SPIKE 不支持 null 跨函数边界（返回值型丢失）")
            _emit_epilogue(em)
        elif op in (OP.JMP, OP.JZ, OP.JNZ):
            target = f"{tag}:{ins[1]}"
            if op == OP.JMP:
                em.j(target)
            else:
                _need(stk, 1, "JZ/JNZ")
                t = stk.pop()
                _pop_to(em, R_T0)
                if t == "list":
                    em.lw(R_T0, R_T0, 0)    # 真值性：空列表=假（Python 口径）
                em.emit(BEQ(R_T0, ZERO, 0) if op == OP.JZ else BNE(R_T0, ZERO, 0))
                em._fix_br.append((len(em.code) - 1, target))
        elif op == OP.BUILD_LIST:
            n = ins[1]
            _need(stk, n, "BUILD_LIST")
            for t in (stk[-n:] if n else []):
                _check_scalar(t, "BUILD_LIST 元素")
            _emit_build_list(em, ctx, n)
            del stk[-n:]
            stk.append("list")
        elif op == OP.INDEX_GET:
            _need(stk, 2, "INDEX_GET")
            tc, ti = stk[-2], stk[-1]          # 容器先压、下标后压
            if isinstance(tc, tuple) or isinstance(ti, tuple):
                raise NotSupportedRV32("INDEX_GET：函数值不可索引")
            if ti == "list":
                raise NotSupportedRV32("INDEX_GET：SPIKE 索引仅支持整数下标（列表下标列表未覆盖）")
            if tc != "list":
                raise NotSupportedRV32("INDEX_GET：SPIKE 仅支持列表索引（int/dict 索引未覆盖）")
            _emit_index_get(em)
            del stk[-2:]
            stk.append("v")
        elif op == OP.POP:
            _need(stk, 1, "POP")
            em.addi(R_EBP, R_EBP, -4)
            stk.pop()
        elif op == OP.OUTPUT:
            _need(stk, 1, "OUTPUT")
            t = stk.pop()
            if isinstance(t, tuple):
                raise NotSupportedRV32("OUTPUT：不支持 <function> 值打印（VM 参考为字符串）")
            _pop_to(em, R_A0)
            em.call_abs({"bool": "print_bool", "list": "print_list",
                         "null": "print_null"}.get(t, "print_int"))
            em.call_abs("print_nl")
        elif op == OP.HALT:
            em.j("exit_ok")
        else:
            raise NotSupportedRV32(
                f"SPIKE 不支持 opcode 0x{op:02X}（{OP.name(op)}）")


def _need(stk, n, what):
    if len(stk) < n:
        raise NotSupportedRV32(f"{what}：编译期表达式栈欠深（不同构）")


def _emit_call(em, ctx, stk, argc):
    if argc < 0:
        raise NotSupportedRV32(f"负实参数 CALL {argc}")
    if argc > 2:
        raise NotSupportedRV32(f"SPIKE 实参数上限 2：CALL {argc}")
    if len(stk) < argc + 1:
        raise NotSupportedRV32("CALL：表达式栈欠深（编译期/运行期不同构）")
    marker = stk[-(argc + 1)]
    if isinstance(marker, tuple) and marker[0] == "bi":
        _emit_builtin(em, stk, argc, marker[1])
        return
    if not (isinstance(marker, tuple) and marker[0] == "fn"):
        raise NotSupportedRV32(
            "SPIKE 只支持直接调用已定义函数；间接调用/闭包/偏应用不在子集内")
    for t in (stk[-argc:] if argc else []):
        if isinstance(t, tuple):
            raise NotSupportedRV32("CALL：函数作实参（高阶）不在 SPIKE 子集")
        if t == "list":
            raise NotSupportedRV32("CALL：列表跨函数边界传参不在 SPIKE 子集")
        if t == "null":
            raise NotSupportedRV32("CALL：null 作实参（跨边界值型丢失）不在 SPIKE 子集")
    name = marker[1]
    if argc == 1:
        em.lw(R_A0, R_EBP, -4)
    elif argc == 2:
        em.lw(R_A0, R_EBP, -8)
        em.lw(R_A1, R_EBP, -4)
    em.addi(R_EBP, R_EBP, -4 * (argc + 1))
    del stk[-(argc + 1):]
    em.call_abs(f"fn:{name}")
    _push_reg(em, R_A0)
    stk.append("v")


def _emit_builtin(em, stk, argc, name):
    """内建调用发射：len(list) / get(list, idx) 直接融进指令序列。

    栈布局与直接调用一致：[fn 占位, arg0..argN]，占位在 deepest。"""
    if BUILTINS.get(name) != argc:
        raise NotSupportedRV32(f"SPIKE 内建 {name!r} 元数 {BUILTINS.get(name)}≠{argc}")
    args = stk[-argc:]
    if name == "len":
        if argc != 1 or args[0] != "list":
            raise NotSupportedRV32("SPIKE：len 仅支持列表（str/dict 值未覆盖）")
        em.lw(R_A0, R_EBP, -4)
        em.lw(R_A0, R_A0, 0)
        em.addi(R_EBP, R_EBP, -8)              # 弹 arg + fn 占位
        del stk[-2:]
        _push_reg(em, R_A0); stk.append("v")
    elif name == "get":
        if argc != 2 or args[0] != "list":
            raise NotSupportedRV32("SPIKE：get 仅支持 列表×整数下标")
        _check_scalar(args[1], "get 下标")
        if args[1] == "null":
            raise NotSupportedRV32("SPIKE：get 下标不可为 null")
        em.lw(R_T0, R_EBP, -8)                 # xs
        em.lw(R_T1, R_EBP, -4)                 # idx
        em.addi(R_EBP, R_EBP, -12)             # 弹 2 arg + fn 占位
        del stk[-3:]
        _index_core(em)
        stk.append("v")
    else:                                      # pragma: no cover - BUILTINS 新增时防漏
        raise NotSupportedRV32(f"SPIKE 内建 {name!r} 未实现分派")


# ---------------------------------------------------------------- 顶层

def _build_regions(pool_len: int):
    glob = POOL + ((pool_len * 4 + 15) & ~15)
    scratch = glob + GLOB_SIZE
    callstack_top = scratch + SCRATCH_SIZE + CALLSTACK_SIZE   # 向下生长预留带
    heap_base = callstack_top + 0x1000                        # 与调用栈带再隔一页
    heap_end = heap_base + HEAP_SIZE
    return glob, scratch, callstack_top, heap_base, heap_end


def compile_module_to_code(mod):
    """返回 (代码机器码 bytes, 常量池 int 列表)。"""
    em = E32()
    consts = mod.constants

    pool: list[int] = []
    idx_of: dict[int, int] = {}
    for i, c in enumerate(consts):
        if isinstance(c, str):
            continue
        if isinstance(c, bool) or not isinstance(c, int):
            raise NotSupportedRV32(
                f"SPIKE 值模型仅 int32：常量池[{i}] = {c!r}（{type(c).__name__}）")
        if not INT_MIN <= c <= INT_MAX:
            raise NotSupportedRV32(
                f"SPIKE 值模型仅 int32：常量池[{i}] = {c} 超 32 位")
        pool.append(c)
        idx_of[i] = len(pool) - 1

    gmap: dict[str, int] = {}
    for code in [mod.main_code] + [f.code for f in mod.functions.values()]:
        for ins in code:
            if len(ins) > 1 and ins[0] == OP.STORE_GLOBAL:
                nm = consts[ins[1]]
                if nm in mod.functions:
                    raise NotSupportedRV32(f"SPIKE：不支持把函数名 {nm!r} 重绑为变量")
                gmap.setdefault(nm, len(gmap))

    glob_base, scratch_base, callstack_top, heap_base, heap_end = _build_regions(len(pool))
    ctx = _Ctx(consts, idx_of, gmap, set(mod.functions), heap_base, heap_end)

    # ---- _start ----
    em.label_here("_start")
    em.li(SP, callstack_top)
    em.addi(SP, SP, -16)
    em.addi(R_FP, SP, 16)          # main 内联层也建伪帧：RET 恢复 FP/SP 才自洽
    em.li(R_EBP, scratch_base)
    em.li(R_CPOOL, POOL)
    em.li(R_GLOB, glob_base)
    em.li(R_UART, 0x10000000)
    em.li(R_T0, heap_base + 4)     # 堆 bump 指针初始化：首字即可分配起点
    em.li(R_T1, heap_base)
    em.sw(R_T0, R_T1, 0)
    _emit_body(em, ctx, mod.main_code, nlocals=0, tag="main")
    em.j("exit_ok")

    # ---- 用户函数 ----
    for name, fn in mod.functions.items():
        if fn.arity > 2:
            raise NotSupportedRV32(
                f"SPIKE 形参上限 2（a0/a1 传参）：{name} arity={fn.arity}")
        em.label_here(f"fn:{name}")
        _emit_frame_setup(em)
        alloc = _frame_alloc(fn.nlocals)
        if alloc:
            em.addi(SP, SP, -alloc)
        for i in range(fn.arity):
            em.sw((R_A0, R_A1)[i], R_FP, _local_off(i))
        _emit_body(em, ctx, fn.code, nlocals=fn.nlocals, tag=f"fn:{name}",
                   ltype0={i: "v" for i in range(fn.arity)})
        em.jabs("exit_err")

    _emit_runtime(em)

    if len(em.code) * 4 > CODE_GAP:
        raise NotSupportedRV32(f"SPIKE 代码段超 {CODE_GAP} 字节：{len(em.code) * 4}")

    abs_map = {lbl: BASE + em.off_of(lbl) for lbl in em.labels}
    text = em.resolve(BASE, abs_map)
    return text, pool


def compile_module_to_elf(mod) -> bytes:
    text, pool = compile_module_to_code(mod)
    pool_bytes = b"".join(struct.pack("<i", v) for v in pool)
    seg = bytearray()
    seg += text
    seg += b"\x00" * (CODE_GAP - len(text))
    seg += pool_bytes
    filesz = len(seg)
    _glob, _scr, _ctop, _hb, heap_end = _build_regions(len(pool))
    memsz = (heap_end + 0x1000) - BASE
    return _build_elf(BASE, bytes(seg), filesz, memsz)


def _build_elf(vaddr: int, seg: bytes, filesz: int, memsz: int) -> bytes:
    """RV32 ELF32 小端静态可执行，单 RWX PT_LOAD，入口 = vaddr。

    附最小 section 表（NULL + .shstrtab）：QEMU load_elf 对 shoff=0 的 ELF
    拒识别、退回 raw 整体加载（ELF 头当指令 → illegal instruction）。"""
    EHDR, PHDR = 52, 32
    off = EHDR + PHDR
    shstr = b"\x00.shstrtab\x00"                    # ".shstrtab" 在偏移 1
    shstr_off = off + len(seg)                       # len(seg) 恒 4 对齐
    shdr_off = (shstr_off + len(shstr) + 3) & ~3     # section 表须 4 对齐
    pad = b"\x00" * (shdr_off - shstr_off - len(shstr))
    e = bytearray()
    e += b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\x00" * 8
    # e_type=ET_EXEC(2) e_machine=EM_RISCV(0xF3) version entry phoff shoff flags
    # ehsize phentsize shentsize phnum shnum shstrndx
    e += struct.pack("<HHIIIIIHHHHHH",
                     2, 0xF3, 1, vaddr, EHDR, shdr_off, 0,
                     EHDR, PHDR, 40, 1, 2, 1)
    p = struct.pack("<IIIIIIII", 1, off, vaddr, vaddr, filesz, memsz, 7, 0x1000)
    s_null = struct.pack("<10I", *([0] * 10))
    s_str = struct.pack("<10I", 1, 3, 0, 0, shstr_off, len(shstr), 0, 0, 4, 0)
    return bytes(e) + p + seg + shstr + pad + s_null + s_str


def _emit_runtime(em):
    """exit / putc / print_nl / print_int / print_bool / print_list：
    ns16550 MMIO + sifive_test 退出。

    退出走 test@0x00100000 的 finish word（低 16 位 0x5555=finish，
    高 16 位=退出码）：代码跑在 M-mode（-bios none/OpenSBI payload 两可），
    ecall 无固件接管时是死路，MMIO 才与 demo 同口径。"""
    em.label_here("exit_ok")
    em.addi(R_T1, ZERO, 0)                            # 退出码 0
    em.j("do_exit")
    em.label_here("exit_err")
    em.li(R_T1, 1)                                    # 干净失败：非零退出不伪造
    em.label_here("do_exit")
    em.li(R_T0, 0x5555)
    em.emit(SLLI(R_T1, R_T1, 16))
    em.emit(OR(R_T0, R_T0, R_T1))
    em.li(R_T2, TEST_DEV)
    em.emit(SW(R_T0, R_T2, 0))
    em.label_here("trap_halt")
    em.j("trap_halt")                                 # 兜底：设备无响应则停转

    # putc：a0 低字节 → 轮询 LSR bit5 → 写 THR。仅毁 t1。
    # 注意：ns16550 寄存器是字节宽度 MMIO，必须 LBU/SB（32 位读 LSR 拿不到值）。
    em.label_here("putc")
    em.label_here("putc_wait")
    em.emit(LBU(R_T1, R_UART, 5))
    em.emit(ANDI(R_T1, R_T1, 0x20))
    em.emit(BEQ(R_T1, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "putc_wait"))
    em.emit(SB(R_A0, R_UART, 0))
    em.emit(JALR(ZERO, RA, 0))

    # print_nl：putc('\n')
    em.label_here("print_nl")
    em.addi(SP, SP, -16)
    em.sw(RA, SP, 12)
    em.li(R_A0, 0x0A)
    em.call_abs("putc")
    em.lw(RA, SP, 12)
    em.addi(SP, SP, 16)
    em.emit(JALR(ZERO, RA, 0))

    # print_int：a0 = int32 → 十进制。帧 48B：RA@SP+44，数字缓冲 [SP+8,SP+32)（
    #   逆序填、正序发）。工作值存 t4、写指针存 t3（putc 只毁 a0/t1，均存活）。
    em.label_here("print_int")
    em.addi(SP, SP, -48)
    em.sw(RA, SP, 44)
    em.addi(R_T4, R_A0, 0)                         # n（工作值）
    em.li(R_T3, 32)
    em.add(R_T3, SP, R_T3)                         # R_T3 = SP+32（写入终点，exclusive）
    em.emit(BGE(R_T4, ZERO, 0))                    # n>=0 → pi_abs
    em._fix_br.append((len(em.code) - 1, "pi_abs"))
    em.li(R_A0, 0x2D)                              # '-'
    em.call_abs("putc")                            # 只毁 a0/t1，t3/t4 存活
    em.emit(SUB(R_T4, ZERO, R_T4))                 # n = -n（INT_MIN 边界：未覆盖，见设计）
    em.label_here("pi_abs")
    em.label_here("pi_loop")
    em.li(R_T2, 10)
    em.emit(REMU(R_T1, R_T4, R_T2))                # digit = n % 10
    em.emit(DIVU(R_T4, R_T4, R_T2))                # n /= 10
    em.addi(R_T3, R_T3, -1)
    em.emit(ADDI(R_T1, R_T1, 0x30))                # '0'+digit
    em.emit(SB(R_T1, R_T3, 0))
    em.emit(BNE(R_T4, ZERO, 0))                    # n!=0 → 继续
    em._fix_br.append((len(em.code) - 1, "pi_loop"))
    # 正序输出 [R_T3, SP+32)
    em.li(R_T5, 32)
    em.add(R_T5, SP, R_T5)                         # R_T5 = buf 末（不变）
    em.label_here("pi_out")
    em.emit(BGEU(R_T3, R_T5, 0))                   # ptr>=末 → 结束
    em._fix_br.append((len(em.code) - 1, "pi_done"))
    em.emit(LBU(R_A0, R_T3, 0))
    em.call_abs("putc")                            # 毁 a0/t1
    em.addi(R_T3, R_T3, 1)                         # t3 存活
    em.j("pi_out")
    em.label_here("pi_done")
    em.lw(RA, SP, 44)
    em.addi(SP, SP, 48)
    em.emit(JALR(ZERO, RA, 0))

    # print_bool：a0 ∈ {0,1} → "False"/"True"（与 VM f"{bool}" 文本对齐）。
    em.label_here("print_bool")
    em.addi(SP, SP, -16)
    em.sw(RA, SP, 12)
    em.emit(BEQ(R_A0, ZERO, 0))
    em._fix_br.append((len(em.code) - 1, "pb_false"))
    for ch in b"True":
        em.li(R_A0, ch)
        em.call_abs("putc")
    em.j("pb_done")
    em.label_here("pb_false")
    for ch in b"False":
        em.li(R_A0, ch)
        em.call_abs("putc")
    em.label_here("pb_done")
    em.lw(RA, SP, 12)
    em.addi(SP, SP, 16)
    em.emit(JALR(ZERO, RA, 0))

    # print_null：无条件输出 "None"（与 VM f"{None}" 文本对齐）。
    em.label_here("print_null")
    em.addi(SP, SP, -16)
    em.sw(RA, SP, 12)
    for ch in b"None":
        em.li(R_A0, ch)
        em.call_abs("putc")
    em.lw(RA, SP, 12)
    em.addi(SP, SP, 16)
    em.emit(JALR(ZERO, RA, 0))

    # print_list：a0 = 堆列表指针 → "[e0, e1, ...]"（Python repr 分隔口径）。
    # 状态（RA/p/i）全存自身帧：putc 毁 a0/t1，print_int 毁 a0/t1-t5，均不碰帧。
    em.label_here("print_list")
    em.addi(SP, SP, -32)
    em.sw(RA, SP, 28)
    em.sw(R_A0, SP, 24)                        # p
    em.li(R_T0, 0)
    em.sw(R_T0, SP, 16)                        # i = 0
    em.li(R_A0, 0x5B)                          # '['
    em.call_abs("putc")
    em.label_here("pl_cond")
    em.lw(R_T5, SP, 16)
    em.lw(R_T0, SP, 24)
    em.lw(R_T2, R_T0, 0)                       # len
    em.emit(BLT(R_T5, R_T2, 0))                # i < len → 循环体（均非负）
    em._fix_br.append((len(em.code) - 1, "pl_body"))
    em.j("pl_end")
    em.label_here("pl_body")
    em.lw(R_T5, SP, 16)
    em.emit(BEQ(R_T5, ZERO, 0))                # i==0 → 不加 ", " 分隔
    em._fix_br.append((len(em.code) - 1, "pl_item"))
    em.li(R_A0, 0x2C)                          # ','
    em.call_abs("putc")
    em.li(R_A0, 0x20)                          # ' '
    em.call_abs("putc")
    em.label_here("pl_item")
    em.lw(R_T5, SP, 16)
    em.emit(SLLI(R_T5, R_T5, 2))
    em.lw(R_T0, SP, 24)
    em.add(R_T0, R_T0, R_T5)
    em.lw(R_A0, R_T0, 4)                       # 元素
    em.call_abs("print_int")
    em.lw(R_T5, SP, 16)
    em.addi(R_T5, R_T5, 1)
    em.sw(R_T5, SP, 16)
    em.j("pl_cond")
    em.label_here("pl_end")
    em.li(R_A0, 0x5D)                          # ']'
    em.call_abs("putc")
    em.lw(RA, SP, 28)
    em.addi(SP, SP, 32)
    em.emit(JALR(ZERO, RA, 0))
