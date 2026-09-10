# -*- coding: utf-8 -*-
"""M3V 栈式字节码虚拟机。

性能墙的根本解法：
  - 显式帧栈（vm.frames）+ 单一指令循环：Python 调用栈深度恒定为 1，
    Matha 程序递归再深也不会撑爆 Python 栈；
  - 帧局部变量是定长数组、编译期槽位 O(1) 访问，无 AST 树走的环境快照；
  - 闭包经定义帧链（enclosing）访问外层，let rec 用 Box 共享。
"""
from __future__ import annotations

from src.mbc import opcodes as OP
from src.mbc.compiler import MModule, MFunction


class Box:
    __slots__ = ("value",)
    def __init__(self, value=None):
        self.value = value


class Closure:
    __slots__ = ("fn", "frame")
    def __init__(self, fn: MFunction, frame: "Frame | None"):
        self.fn = fn
        self.frame = frame


class Partial:
    """柯里化偏应用：已收集参数，等待剩余参数。"""
    __slots__ = ("fn", "args")
    def __init__(self, fn, args: list):
        self.fn = fn
        self.args = args


class Frame:
    __slots__ = ("fn_name", "code", "locals", "enclosing", "stack", "pc")
    def __init__(self, fn_name, code, locals_, enclosing):
        self.fn_name = fn_name
        self.code = code
        self.locals = locals_
        self.enclosing = enclosing   # 定义帧（闭包链）
        self.stack: list = []
        self.pc = 0


_BINOPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
    "//": lambda a, b: a // b,
    "%": lambda a, b: a % b,
    "**": lambda a, b: a ** b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "in": lambda a, b: a in b,
}

_UNARYOPS = {
    "neg": lambda a: -a,
    "not": lambda a: not a,
}


def _curry2(fn):
    """两参函数柯里化：f(a)(b) 或 f(a,b) 均可用。"""
    return lambda a: (lambda b: fn(a, b))


def _curry3(fn):
    """三参函数柯里化：f(a)(b)(c)。"""
    return lambda a: (lambda b: (lambda c: fn(a, b, c)))


def _raise_builtin(msg):
    raise RuntimeError(str(msg))


def _default_builtins() -> dict:
    """VM 内建：复用宿主 mathlib 注册的同一套数学/工具函数。"""
    from src.mathlib import _register_math_builtins
    b: dict = {}
    _register_math_builtins(b)
    # 基础原语（与宿主解释器一致）
    b.setdefault("len", len)
    b.setdefault("abs", abs)
    b.setdefault("int", int)
    b.setdefault("float", float)
    b.setdefault("str", str)
    b.setdefault("bool", bool)
    b.setdefault("list", list)
    b.setdefault("ord", ord)
    b.setdefault("chr", chr)
    b.setdefault("range", range)
    # 柯里化的序列工具（Matha 代码以 get(xs)(i) / append(xs)(x) 形式调用）
    b.setdefault("get", _curry2(lambda c, i: c[i]))
    b.setdefault("slice", _curry3(lambda c, s, e: c[s:e]))
    b.setdefault("append", _curry2(lambda xs, x: (list(xs) if xs is not None else []) + [x]))
    b.setdefault("错误", _raise_builtin)
    b.setdefault("MathaIOError", lambda m: ("MathaIOError", str(m)))
    b.setdefault("真", True)
    b.setdefault("假", False)
    b.setdefault("null", None)
    b.setdefault("None", None)
    return b


class VM:
    def __init__(self, mod: MModule, builtins: dict | None = None, verbose: bool = False):
        self.mod = mod
        self.globals: dict = dict(builtins if builtins is not None else _default_builtins())
        self.outputs: list = []
        self.verbose = verbose
        # 主帧（模块全局帧）
        self.main_frame = Frame("__main__", mod.main_code, [], None)
        self.halted = False
        # 全局函数注册为闭包（定义帧 = 主帧，使函数间互引可达）
        for name, fn in mod.functions.items():
            self.globals[name] = Closure(fn, self.main_frame)
        self.frames: list[Frame] = [self.main_frame]

    # ---------- 运行 ----------

    def run(self):
        frames = self.frames
        while frames and not self.halted:
            f = frames[-1]
            ins = f.code[f.pc]
            f.pc += 1
            op = ins[0]
            self._dispatch(op, ins, f, frames)
        return self.outputs

    def call(self, name: str, *args):
        """在已初始化的 VM 上调用全局函数（供外部驱动自举链路）。"""
        fn = self.globals[name]
        base = len(self.frames)
        f = self.frames[-1]
        f.stack.append(fn)
        for a in args:
            f.stack.append(a)
        self._dispatch(OP.CALL, (OP.CALL, len(args)), f, self.frames)
        frames = self.frames
        while len(frames) > base:
            f = frames[-1]
            ins = f.code[f.pc]
            f.pc += 1
            self._dispatch(ins[0], ins, f, frames)
        # 返回值在调用帧（base-1，通常是主帧）栈顶
        return frames[base - 1].stack.pop()

    def _dispatch(self, op, ins, f: Frame, frames: list) -> None:
        C = self.mod.constants
        st = f.stack

        if op == OP.PUSH_CONST:
            st.append(C[ins[1]])
        elif op == OP.PUSH_TRUE:
            st.append(True)
        elif op == OP.PUSH_FALSE:
            st.append(False)
        elif op == OP.PUSH_NULL:
            st.append(None)

        elif op == OP.LOAD_LOCAL:
            st.append(f.locals[ins[1]])
        elif op == OP.STORE_LOCAL:
            f.locals[ins[1]] = st.pop()
        elif op == OP.LOAD_BOX:
            st.append(f.locals[ins[1]].value)
        elif op == OP.MAKE_BOX:
            f.locals[ins[1]] = Box(None)
        elif op == OP.STORE_BOX:
            f.locals[ins[1]].value = st.pop()
        elif op == OP.LOAD_OUTER:
            st.append(self._outer(f, ins[1]).locals[ins[2]])
        elif op == OP.LOAD_OUTER_BOX:
            st.append(self._outer(f, ins[1]).locals[ins[2]].value)
        elif op == OP.LOAD_GLOBAL:
            st.append(self.globals[C[ins[1]]])
        elif op == OP.STORE_GLOBAL:
            self.globals[C[ins[1]]] = st.pop()

        elif op == OP.MAKE_CLOSURE:
            st.append(Closure(self.mod.functions[ins[1]], f))

        elif op == OP.CALL:
            argc = ins[1]
            # 栈布局：[..., fn, arg1, ..., argN]（栈顶为最后一个参数）
            args = list(st[len(st) - argc:]) if argc else []
            fn = st[len(st) - argc - 1]
            del st[len(st) - argc - 1:]
            self._invoke(fn, args, f, frames)

        elif op == OP.RET:
            val = st.pop() if st else None
            frames.pop()
            if frames:
                frames[-1].stack.append(val)

        elif op == OP.JMP:
            f.pc = ins[1]
        elif op == OP.JZ:
            if not st.pop():
                f.pc = ins[1]
        elif op == OP.JNZ:
            if st.pop():
                f.pc = ins[1]

        elif op == OP.BINOP:
            b = st.pop(); a = st.pop()
            st.append(_BINOPS[C[ins[1]]](a, b))
        elif op == OP.UNARYOP:
            st.append(_UNARYOPS[C[ins[1]]](st.pop()))

        elif op == OP.BUILD_LIST:
            n = ins[1]
            # st[-n:] 为栈底→栈顶，即元素按书写顺序压入的顺序
            items = list(st[-n:]) if n else []
            del st[len(st) - n:]
            st.append(items)
        elif op == OP.BUILD_DICT:
            n = ins[1]
            d = {}
            for _ in range(n):
                v = st.pop(); k = st.pop()
                d[k] = v
            st.append(d)
        elif op == OP.INDEX_GET:
            idx = st.pop(); c = st.pop()
            st.append(c[idx])
        elif op == OP.BUILD_SLICE:
            end = st.pop(); start = st.pop(); c = st.pop()
            st.append(c[start:end])
        elif op == OP.GET_ATTR:
            obj = st.pop()
            key = C[ins[1]]
            # dict 缺失字段返回 None（与宿主解释器 PathExpr 语义一致）
            if isinstance(obj, dict):
                st.append(obj.get(key))
            else:
                st.append(obj[key])
        elif op == OP.UNPACK_SEQ:
            seq = st.pop()
            seq = seq if seq is not None else []
            n = ins[1]
            for i in range(n):
                st.append(seq[i] if i < len(seq) else None)
        elif op == OP.DUP:
            st.append(st[-1])
        elif op == OP.POP:
            st.pop()

        elif op == OP.OUTPUT:
            val = st.pop()
            self.outputs.append(val)
            if self.verbose:
                print(val)
        elif op == OP.RAISE:
            raise RuntimeError(str(st.pop()))
        elif op == OP.HALT:
            # 顶层初始化结束：停止取指，但保留主帧供后续 call() 驱动
            self.halted = True
        else:
            raise RuntimeError(f"VM：未知操作码 0x{op:02X}")

    # ---------- 调用 ----------

    def _outer(self, f: Frame, depth: int) -> Frame:
        cur = f.enclosing
        for _ in range(depth - 1):
            cur = cur.enclosing
        return cur

    def _invoke(self, fn, args: list, caller: Frame, frames: list) -> None:
        # 展开偏应用
        while isinstance(fn, Partial):
            args = fn.args + args
            fn = fn.fn

        if isinstance(fn, Closure):
            arity = fn.fn.arity
            if len(args) < arity:
                caller.stack.append(Partial(fn, args))
                return
            locals_ = list(args[:arity]) + [None] * (fn.fn.nlocals - arity)
            frames.append(Frame(fn.fn.name, fn.fn.code, locals_, fn.frame))
            return

        if callable(fn):
            # Python 内建：逐参应用以兼容柯里化包装（_curry2 等）
            r = fn
            for a in args:
                r = r(a) if callable(r) else r
            caller.stack.append(r)
            return

        raise RuntimeError(f"VM：不可调用的值 {fn!r}")


def run_module(mod: MModule, verbose: bool = False) -> list:
    return VM(mod, verbose=verbose).run()


def run_source(source: str, verbose: bool = False) -> list:
    from src.mbc.compiler import compile_source
    return run_module(compile_source(source), verbose=verbose)
