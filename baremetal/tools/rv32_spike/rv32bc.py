# -*- coding: utf-8 -*-
"""P6 SPIKE：字节码契约 MBR1 —— 1 字节 OpCode + N×4 字节操作数的序列化流。

定位（与主线 `src/mbc/serial.py` 的 .mbc marshal 容器**互不替代**）：
  .mbc 是 VM 运行时自包含工件（marshal 负载）；MBR1 是 **SPIKE 发射器侧契约**，
  固定宽度、显式指令二分类、严格校验——供 RV32 发射管线以字节流为唯一输入。
  MBR1 不含函数 params 面（发射器不消费，roundtrip 断言以消费面为准）。

指令二分类（契约核心）：
  * 纯指令 PURE：操作数是 跳转目标/计数/槽位/实参数 等裸立即数，无间接数据引用
      JMP/JZ/JNZ(target) CALL(argc) BUILD_LIST/UNPACK_SEQ/BUILD_DICT(n)
      LOAD_LOCAL/STORE_LOCAL/MAKE_BOX/STORE_BOX/LOAD_BOX(slot)
      LOAD_OUTER/LOAD_OUTER_BOX(depth,slot) INDEX_GET/BUILD_SLICE/DUP/POP/RET/
      OUTPUT/RAISE/HALT/PUSH_TRUE/PUSH_FALSE/PUSH_NULL
  * 数据指令 DATA：操作数恒为 **常量池下标**，须经常量池间接解析
      PUSH_CONST BINOP UNARYOP LOAD_GLOBAL STORE_GLOBAL GET_ATTR MAKE_CLOSURE
      FORMULA_SCHEMA
  分类由 OPS 表钉死；任何未知 op、 arity 不符、操作数越界、跳转目标越界、数据
  截断、magic/version 不符 → NotSupportedRV32（显式拒绝，绝不静默修复）。

值面限制（对齐 SPIKE int32 值模型）：常量池仅允许 int32 与 UTF-8 字符串；
bool/float/tuple/None 在 encode 即拒（发射器本就不消费）。

布局（全小端）：
  "MBR1" | u8 version(=1)
  u32 n_const   每个常量: tag u8 {0=int(i32) | 1=str: u32 字节长 + utf8}
  u32 n_ins     每条指令: op u8 + arity×u32 操作数
  u32 n_fn      每个函数: name(str) u32 arity u32 nlocals u32 n_ins 指令流
  module_name(str)
"""
from __future__ import annotations

import struct

from rvcoder import NotSupportedRV32

from src.mbc import opcodes as OP
from src.mbc.compiler import MFunction, MModule

MAGIC = b"MBR1"
VERSION = 1
INT32_MIN = -0x80000000
INT32_MAX = 0x7FFFFFFF

_P, _D = "pure", "data"      # 指令二分类：纯指令 / 数据指令

# op → (名称, 操作数个数, 分类)。覆盖 opcodes.py 全部 33 条。
OPS: dict[int, tuple[str, int, str]] = {
    OP.PUSH_CONST:       ("PUSH_CONST", 1, _D),
    OP.PUSH_TRUE:        ("PUSH_TRUE", 0, _P),
    OP.PUSH_FALSE:       ("PUSH_FALSE", 0, _P),
    OP.PUSH_NULL:        ("PUSH_NULL", 0, _P),
    OP.LOAD_LOCAL:       ("LOAD_LOCAL", 1, _P),
    OP.LOAD_BOX:         ("LOAD_BOX", 1, _P),
    OP.STORE_LOCAL:      ("STORE_LOCAL", 1, _P),
    OP.MAKE_BOX:         ("MAKE_BOX", 1, _P),
    OP.STORE_BOX:        ("STORE_BOX", 1, _P),
    OP.LOAD_OUTER:       ("LOAD_OUTER", 2, _P),
    OP.LOAD_OUTER_BOX:   ("LOAD_OUTER_BOX", 2, _P),
    OP.LOAD_GLOBAL:      ("LOAD_GLOBAL", 1, _D),
    OP.STORE_GLOBAL:     ("STORE_GLOBAL", 1, _D),
    OP.MAKE_CLOSURE:     ("MAKE_CLOSURE", 1, _D),
    OP.CALL:             ("CALL", 1, _P),
    OP.RET:              ("RET", 0, _P),
    OP.JMP:              ("JMP", 1, _P),
    OP.JZ:               ("JZ", 1, _P),
    OP.JNZ:              ("JNZ", 1, _P),
    OP.BINOP:            ("BINOP", 1, _D),
    OP.UNARYOP:          ("UNARYOP", 1, _D),
    OP.BUILD_LIST:       ("BUILD_LIST", 1, _P),
    OP.BUILD_DICT:       ("BUILD_DICT", 1, _P),
    OP.INDEX_GET:        ("INDEX_GET", 0, _P),
    OP.BUILD_SLICE:      ("BUILD_SLICE", 0, _P),
    OP.GET_ATTR:         ("GET_ATTR", 1, _D),
    OP.UNPACK_SEQ:       ("UNPACK_SEQ", 1, _P),
    OP.DUP:              ("DUP", 0, _P),
    OP.POP:              ("POP", 0, _P),
    OP.OUTPUT:           ("OUTPUT", 0, _P),
    OP.RAISE:            ("RAISE", 0, _P),
    OP.FORMULA_SCHEMA:   ("FORMULA_SCHEMA", 1, _D),
    OP.HALT:             ("HALT", 0, _P),
}

JUMP_OPS = {OP.JMP, OP.JZ, OP.JNZ}     # 操作数 = 本段指令下标，需界内校验
PURE_OPS = frozenset(o for o, (_, _, c) in OPS.items() if c == _P)
DATA_OPS = frozenset(o for o, (_, _, c) in OPS.items() if c == _D)

assert PURE_OPS | DATA_OPS == set(OPS) and len(PURE_OPS) + len(DATA_OPS) == 33


def op_class(op: int) -> str:
    """"pure" / "data"；未知 op → NotSupportedRV32。"""
    if op not in OPS:
        raise NotSupportedRV32(f"MBR1：未知 opcode 0x{op:02X}")
    return OPS[op][2]


# ---------------------------------------------------------------- 写字节

class _W:
    def __init__(self):
        self.b = bytearray()

    def u8(self, v: int):
        self.b.append(v & 0xFF)

    def u32(self, v: int):
        if not 0 <= v <= 0xFFFFFFFF:
            raise NotSupportedRV32(f"MBR1：u32 字段越界 {v}")
        self.b += struct.pack("<I", v)

    def i32(self, v: int):
        if not INT32_MIN <= v <= INT32_MAX:
            raise NotSupportedRV32(f"MBR1：常量超 int32 {v}")
        self.b += struct.pack("<i", v)

    def s(self, v: str):
        raw = v.encode("utf-8")
        self.u32(len(raw))
        self.b += raw


class _R:
    def __init__(self, blob: bytes):
        self.b = blob
        self.i = 0

    def need(self, n: int):
        if self.i + n > len(self.b):
            raise NotSupportedRV32(f"MBR1：数据截断（需 {n} 字节 @ {self.i}）")
        j = self.i
        self.i += n
        return self.b[j:self.i]

    def u8(self) -> int:
        return self.need(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.need(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.need(4))[0]

    def s(self) -> str:
        return self.need(self.u32()).decode("utf-8")


# ---------------------------------------------------------------- 编码

def _w_const(w: _W, c) -> None:
    if isinstance(c, bool) or not isinstance(c, int):
        raise NotSupportedRV32(
            f"MBR1 值面仅 int32/字符串：常量 {c!r}（{type(c).__name__}）")
    if isinstance(c, int):
        w.u8(0)
        w.i32(c)
        return


def _w_code(w: _W, code, n_const: int) -> None:
    w.u32(len(code))
    for ins in code:
        op = ins[0]
        if op not in OPS:
            raise NotSupportedRV32(f"MBR1：未知 opcode 0x{op:02X}")
        name, arity, _cls = OPS[op]
        if len(ins) - 1 != arity:
            raise NotSupportedRV32(
                f"MBR1：{name} 契约 arity={arity}，实际操作数 {len(ins) - 1}")
        w.u8(op)
        for a in ins[1:]:
            if not isinstance(a, int) or not 0 <= a <= 0xFFFFFFFF:
                raise NotSupportedRV32(f"MBR1：{name} 操作数非 u32 {a!r}")
            if op in (OP.PUSH_CONST, OP.BINOP, OP.UNARYOP, OP.LOAD_GLOBAL,
                      OP.STORE_GLOBAL, OP.GET_ATTR, OP.MAKE_CLOSURE,
                      OP.FORMULA_SCHEMA) and a >= n_const:
                raise NotSupportedRV32(f"MBR1：{name} 常量下标越界 {a}")
            if op in JUMP_OPS and a >= len(code):
                raise NotSupportedRV32(f"MBR1：{name} 跳转目标越界 {a}")
            w.u32(a)


def encode(mod: MModule) -> bytes:
    """MModule → MBR1 字节流。任何契约越界显式抛 NotSupportedRV32。"""
    consts = mod.constants
    n_const = len(consts)
    w = _W()
    w.b += MAGIC
    w.u8(VERSION)
    w.u32(n_const)
    for c in consts:
        if isinstance(c, str):
            w.u8(1)
            w.s(c)
        else:
            _w_const(w, c)
    _w_code(w, mod.main_code, n_const)
    w.u32(len(mod.functions))
    for name, fn in mod.functions.items():
        w.s(name)
        w.u32(fn.arity)
        w.u32(fn.nlocals)
        _w_code(w, fn.code, n_const)
    w.s(mod.module_name)
    return bytes(w.b)


# ---------------------------------------------------------------- 解码

def _r_const(r: _R):
    tag = r.u8()
    if tag == 0:
        return r.i32()
    if tag == 1:
        return r.s()
    raise NotSupportedRV32(f"MBR1：非法常量 tag {tag}")


def _r_code(r: _R, n_const: int):
    n = r.u32()
    code = []
    for _ in range(n):
        op = r.u8()
        if op not in OPS:
            raise NotSupportedRV32(f"MBR1：未知 opcode 0x{op:02X}")
        name, arity, _cls = OPS[op]
        args = [r.u32() for _ in range(arity)]
        for a in args:
            if op in (OP.PUSH_CONST, OP.BINOP, OP.UNARYOP, OP.LOAD_GLOBAL,
                      OP.STORE_GLOBAL, OP.GET_ATTR, OP.MAKE_CLOSURE,
                      OP.FORMULA_SCHEMA) and a >= n_const:
                raise NotSupportedRV32(f"MBR1：{name} 常量下标越界 {a}")
            if op in JUMP_OPS and a >= n:
                raise NotSupportedRV32(f"MBR1：{name} 跳转目标越界 {a}")
        code.append((op, *args) if args else (op,))
    return code


def decode(blob: bytes) -> MModule:
    """MBR1 字节流 → MModule（发射器输入）。严格校验，坏数据必抛。"""
    r = _R(blob)
    if r.need(4) != MAGIC:
        raise NotSupportedRV32("MBR1：magic 不符")
    ver = r.u8()
    if ver != VERSION:
        raise NotSupportedRV32(f"MBR1：不支持的版本 {ver}")
    n_const = r.u32()
    consts = [_r_const(r) for _ in range(n_const)]
    main_code = _r_code(r, n_const)
    n_fn = r.u32()
    mod = MModule(module_name="")
    mod.constants = consts
    mod.main_code = main_code
    for _ in range(n_fn):
        name = r.s()
        arity = r.u32()
        nlocals = r.u32()
        code = _r_code(r, n_const)
        mod.functions[name] = MFunction(name=name, arity=arity,
                                        nlocals=nlocals, code=code)
    mod.module_name = r.s()
    if r.i != len(r.b):
        raise NotSupportedRV32(f"MBR1：尾部残留 {len(r.b) - r.i} 字节")
    return mod


def module_to_elf(mod: MModule) -> bytes:
    """契约面便捷出口：MBR1 解码产物 → RV32IM ELF（转 rv32em，避免顶层环依赖）。"""
    import rv32em
    return rv32em.compile_module_to_elf(mod)


def compile_bytes_to_elf(blob: bytes) -> bytes:
    """MBR1 字节流 → MModule → RV32IM ELF（SPIKE 全链新入口）。"""
    return module_to_elf(decode(blob))
