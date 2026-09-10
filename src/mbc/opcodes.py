# -*- coding: utf-8 -*-
"""M3V 字节码操作码定义。

指令流为 tuple 列表：(OP, *operands)。跳转目标为指令下标。
栈式虚拟机：除显式标注外，指令均在当前帧的操作数栈上工作。
"""
from __future__ import annotations

# ---- 常量 / 字面量 ----
PUSH_CONST   = 0x01  # PUSH_CONST const_idx        压入常量池元素
PUSH_TRUE    = 0x02
PUSH_FALSE   = 0x03
PUSH_NULL    = 0x04

# ---- 变量访问（编译期解析为槽位 / 外层深度，O(1)）----
LOAD_LOCAL       = 0x10  # LOAD_LOCAL slot          frame.locals[slot]
LOAD_BOX         = 0x11  # LOAD_BOX slot            let rec 递归盒解箱
STORE_LOCAL      = 0x12  # STORE_LOCAL slot         弹出 → frame.locals[slot]
MAKE_BOX         = 0x13  # MAKE_BOX slot            locals[slot] = Box(None)
STORE_BOX        = 0x14  # STORE_BOX slot           box.value = 弹出值
LOAD_OUTER       = 0x15  # LOAD_OUTER depth slot    沿 enclosing 链 depth 层取槽
LOAD_OUTER_BOX   = 0x16  # LOAD_OUTER_BOX depth slot 同上并解箱
LOAD_GLOBAL      = 0x17  # LOAD_GLOBAL name_idx     全局函数/常量/内建
STORE_GLOBAL     = 0x18  # STORE_GLOBAL name_idx    弹出 → globals[name]

# ---- 闭包 / 调用 ----
MAKE_CLOSURE = 0x20  # MAKE_CLOSURE fn_idx        压 Closure(fn, 当前帧)
CALL         = 0x21  # CALL argc                  弹出 argc 参数 + 函数，压结果
RET          = 0x22  # RET                        弹出返回值，弹帧

# ---- 控制流 ----
JMP  = 0x30
JZ   = 0x31  # 弹出条件，假值跳转
JNZ  = 0x32  # 弹出条件，真值跳转

# ---- 运算（操作符索引见 vm._BINOPS / _UNARYOPS）----
BINOP   = 0x40  # BINOP op_idx
UNARYOP = 0x41  # UNARYOP op_idx

# ---- 数据结构 ----
BUILD_LIST  = 0x50  # BUILD_LIST n     弹出 n 个元素 → 列表
BUILD_DICT  = 0x51  # BUILD_DICT n     弹出 n 个 (key,value)（交替压栈）→ dict
INDEX_GET   = 0x52  # 弹出 index，弹出 container，压 container[index]
BUILD_SLICE = 0x53  # 弹出 end,start,container → container[start:end]
GET_ATTR    = 0x54  # GET_ATTR name_idx  弹出对象，压 obj[name]（dict/模块）
UNPACK_SEQ  = 0x57  # UNPACK_SEQ n     弹出序列，依次压入第 0..n-1 个元素
DUP         = 0x58  # 复制栈顶
POP         = 0x59  # 弹出并丢弃栈顶

# ---- 系统 ----
OUTPUT = 0x60  # 弹出值 → 输出
RAISE  = 0x61  # 弹出消息 → 抛出
HALT   = 0xFF


def name(op: int) -> str:
    for k, v in globals().items():
        if isinstance(v, int) and v == op and k.isupper():
            return k
    return f"0x{op:02X}"
