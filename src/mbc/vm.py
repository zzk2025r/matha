"""M3V 栈式字节码虚拟机。

性能墙的根本解法：
  - 显式帧栈（vm.frames）+ 单一指令循环：Python 调用栈深度恒定为 1，
    Matha 程序递归再深也不会撑爆 Python 栈；
  - 帧局部变量是定长数组、编译期槽位 O(1) 访问，无 AST 树走的环境快照；
  - 闭包经定义帧链（enclosing）访问外层，let rec 用 Box 共享。
"""
from __future__ import annotations

import math
import operator

from src import formula_schema as _fs
from src.kernel.errors import MathaRuntimeError, MathaUndefinedNameError
from src.mbc import opcodes as OP
from src.mbc.compiler import MFunction, MModule


class Box:
    __slots__ = ("value",)
    def __init__(self, value=None):
        self.value = value


class Closure:
    __slots__ = ("fn", "frame")
    def __init__(self, fn: MFunction, frame: Frame | None):
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


def _bitop(sym: str, fn):
    """位运算：强制两侧为整数，语义与解释器 src/interp.py:2376-2395 逐条一致。

    解释器在操作数非整数时报 `MathaRuntimeError("<sym> 操作数需为整数，…")`；
    VM 侧抛 RuntimeError（与本模块其余内建错误的类型一致），消息文本保持
    同样的定位信息，便于三端对照排错。bool 是 int 的子类，解释器按 Python
    语义接受（`~真` == -2、`6 & 真` == 0），此处同样接受以保持三端一致。
    """
    def apply(a, b):
        if not isinstance(a, int) or not isinstance(b, int):
            raise RuntimeError(f"{sym} 操作数需为整数，actual left={type(a).__name__}, right={type(b).__name__}")
        return fn(a, b)
    return apply


def _set_seq(v) -> list:
    """集合运算操作数 → 有序元素列表（保序）。与解释器 interp.py::_set_seq 一致。"""
    if isinstance(v, (list, tuple, str)):
        return list(v)
    if isinstance(v, set):
        return list(v)
    return [v]


def _dedup_ordered(values) -> list:
    """按 == 去重并保序，返回普通 list（与集合字面量 _builtin_make_set 一致）。"""
    seen: list = []
    for x in values:
        if x not in seen:
            seen.append(x)
    return seen


def _set_union(a, b) -> list:
    return _dedup_ordered(_set_seq(a) + _set_seq(b))


def _set_inter(a, b) -> list:
    rb = _dedup_ordered(_set_seq(b))
    return [x for x in _dedup_ordered(_set_seq(a)) if x in rb]


def _set_diff(a, b) -> list:
    rb = _dedup_ordered(_set_seq(b))
    return [x for x in _dedup_ordered(_set_seq(a)) if x not in rb]


def _set_comp(a, b) -> list:
    """补集：A 在 B（全集）中的补 —— B \\ A（对齐 docs/06 补集语义）。"""
    lb = _dedup_ordered(_set_seq(a))
    return [x for x in _dedup_ordered(_set_seq(b)) if x not in lb]


def _set_prod(a, b) -> list:
    return [(x, y) for x in _set_seq(a) for y in _set_seq(b)]


def _set_subset(a, b) -> bool:
    rb = _dedup_ordered(_set_seq(b))
    return all(x in rb for x in _dedup_ordered(_set_seq(a)))


def _op_add(a, b):
    """`+`：与解释器 interp.py::_eval_binary 逐条对齐（None 操作数报错、
    dict 当 items 序列拼接、字符串与数值自动转换）。此前 VM 直接 `a + b`，
    同一源串在解释器能跑、在 VM 招 TypeError（主链归一后属行为降级）。"""
    if a is None or b is None:
        raise MathaRuntimeError(f"+ 操作数含 None: left={a!r}, right={b!r}")
    if isinstance(b, dict):
        b = list(b.items())
    if isinstance(a, dict):
        a = list(a.items())
    if isinstance(a, str) and isinstance(b, (int, float)):
        b = str(b)
    elif isinstance(b, str) and isinstance(a, (int, float)):
        a = str(a)
    return a + b


def _op_sub(a, b):
    """"-"：字符串/列表不适用（消息与解释器逐字一致）。"""
    if isinstance(a, (str, list)) or isinstance(b, (str, list)):
        raise MathaRuntimeError("- 不适用于字符串/列表")
    return a - b


def _op_mul(a, b):
    """`*`：数值相乘 / 字符串重复 / 序列重复。

    类型不支持时的消息与解释器 interp.py::_eval_binary 逐字一致（golden 对拍
    比的是文本）。但**序列重复必须支持**：解释器不支持，而 mbc.native 与 VM
    旧路径都支持（`test_native_heap` 的 seq_repeat_* 依赖 `[0] * 1000`），收窄
    到这里会变成主线能力降级 —— 故取两者并集，而不是照抄最窄的那一个。"""
    if (isinstance(a, (int, float)) and isinstance(b, (int, float))
            or isinstance(a, str) and isinstance(b, int)
            or isinstance(a, int) and isinstance(b, str)):
        return a * b
    if isinstance(a, (list, tuple)) and isinstance(b, int) and not isinstance(b, bool):
        return a * b
    if isinstance(a, int) and not isinstance(a, bool) and isinstance(b, (list, tuple)):
        return a * b
    raise MathaRuntimeError(
        f"* 操作数类型不支持: left={a!r}({type(a).__name__}), "
        f"right={b!r}({type(b).__name__})")


def _op_div(a, b):
    """"/"：除零报「除零错误: l / 0」，消息与解释器逐字一致。

    不能直接交给 Python 的 ZeroDivisionError：try/catch 把它给用户的
    文本是 `division by zero`，两个后端下 `catch (e) { 输出(e) }` 结果不同。"""
    if b == 0:
        raise MathaRuntimeError(f"除零错误: {a!r} / 0")
    return a / b


def _op_mod(a, b):
    if b == 0:
        raise MathaRuntimeError(f"取模除零错误: {a!r} % 0")
    if a is None or b is None:
        raise MathaRuntimeError(f"% 操作数含 None: left={a!r}, right={b!r}")
    return a % b


def _op_fdiv(a, b):
    if b == 0:
        raise MathaRuntimeError(f"整除除零错误: {a!r} // 0")
    return a // b


_BINOPS = {
    "+": _op_add,
    "-": _op_sub,
    "*": _op_mul,
    "/": _op_div,
    "//": _op_fdiv,
    "%": _op_mod,
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
    "is": lambda a, b: a is b,
    # 位移：与解释器后端一致（1 << 3 == 8、16 >> 2 == 4）。
    # 右移对负数用算术右移，与 Python // 语义一致。
    "<<": lambda a, b: a << b,
    ">>": lambda a, b: a >> b,
    # 位运算：与解释器 src/interp.py:2376-2395 同语义（仅整数操作数）。
    # `^` 不在此表：按 docs/06 与 EBNF 2.1，`<power> = "^"`（中缀次方），
    # 编译器在 _BIN_OPS 里把 AST 的 `^` 归约为 `**`；异或用专用符号 `⊕`。
    "&": _bitop("&", operator.and_),
    "|": _bitop("|", operator.or_),
    "⊕": _bitop("⊕", operator.xor),
    # 集合运算：与集合字面量（list 承载）及解释器 interp.py 一致，
    # 返回有序去重列表。interp 参考实现见 src/interp.py:2771-2791。
    "∪": lambda a, b: _set_union(a, b),
    "∩": lambda a, b: _set_inter(a, b),
    "⊖": lambda a, b: _set_diff(a, b),
    "~": lambda a, b: _set_comp(a, b),
    "×": lambda a, b: _set_prod(a, b),
    "⊆": lambda a, b: _set_subset(a, b),
}

def _builtin_sqrt(a):
    """前缀 ^ 开方：^9 → 3，^16 → 4（完全平方回退为整数）。"""
    r = a ** 0.5
    return int(r) if isinstance(a, int) and r == int(r) else r


def _builtin_cbrt(a):
    """前缀 ∛ 立方根：∛27 → 3，∛8 → 2（整数完全立方回退为整数）。"""
    r = -((-a) ** (1 / 3)) if a < 0 else a ** (1 / 3)
    if isinstance(a, int):
        ri = round(r)
        if ri * ri * ri == a:
            return ri
    return r


def _builtin_list_sum(a):
    """聚合前缀 ∑：列表求和（空表 → 0）；非列表报错（对齐解释器 builtin_列表求和）。"""
    if not isinstance(a, (list, tuple)):
        raise RuntimeError("求和() 需要列表")
    return sum(a)


def _builtin_list_prod(a):
    """聚合前缀 ∏：列表求积（空表 → 1）；非列表报错（对齐解释器 builtin_列表求积）。"""
    if not isinstance(a, (list, tuple)):
        raise RuntimeError("求积() 需要列表")
    r = 1
    for x in a:
        r = r * x
    return r


def _builtin_bitnot(a):
    """一元 `~` 位取反：仅整数，语义对齐解释器 src/interp.py:1730。

    bool 按 Python 语义视为 int（`~真` == -2），与解释器一致。
    """
    if not isinstance(a, int):
        raise RuntimeError(f"~ 仅适用于整数，实际 {type(a).__name__}")
    return ~int(a)


def _builtin_angle(a):
    """`<<` 角度前缀：度数 → 弧度（docs/06 级 6、docs/17 §42）。

    三角函数（stdlib.arithmetic 的 sin/cos/tan）一律吃弧度，故归一化后
    sin(<<30) == 0.5，与文档示例一致。bool 不接受：角度不是真假值。
    """
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise RuntimeError(f"<< 角度仅适用于数值，实际 {type(a).__name__}")
    return math.radians(a)


def _builtin_incr(a):
    """前缀 `++`：v + 1（非原地，不改绑定，语义同解释器 src/interp.py:1708）。"""
    if not isinstance(a, (int, float)):
        raise RuntimeError(f"++ 仅适用于数值，实际 {type(a).__name__}")
    return a + 1


def _builtin_decr(a):
    """前缀 `--`：v - 1（非原地，语义同解释器 src/interp.py:1716）。"""
    if not isinstance(a, (int, float)):
        raise RuntimeError(f"-- 仅适用于数值，实际 {type(a).__name__}")
    return a - 1


def _builtin_range(start, end):
    """range(start)(end) → [start, start+1, …, end-1]。

    两参语义，对齐 `matha/stdlib.matha` 的 `range(start, end)` 与原生
    `_emit_builtin_range`（亦为两参返回列表）。此前这里挂的是 Python 原生
    `range`（不可部分应用）：单参 `range(3)` 返回 range 对象而非列表，
    双参 `range(1, 4)` 被逐参应用成 `range(1)` 后再调用 → 报
    「不可调用的值 range(0, 1)」，与原生早已正确的 [1, 2, 3] 相悖。
    单参 `range(n)` 四端一律不支持，由语言桥归一化为 `range(0, n)`。"""
    if not isinstance(start, int) or not isinstance(end, int):
        raise RuntimeError("range() 参数需整数")
    return list(range(start, end))


def _builtin_list(*args):
    """list(x) → 转换成列表：文本→码点、列表/元组/集合→浅拷贝、字典→键列表、
    标量与无参→null。与原生 `_emit_builtin_list`（ls_copy/ls_str/ls_dict/
    ls_fail→null）及解释器 `builtin_list` 一致。

    此前 `b.setdefault("list", list)` 挂 Python 内建：容器语义相同，但
    `list(5)`/`list()` 抛 `TypeError: 'int' object is not iterable`，
    而原生返回 null（`b16t_list` 对拍表只覆盖了 str/list/dict 路径）。"""
    if not args:
        return None
    x = args[0]
    if isinstance(x, str):
        return list(x)
    if isinstance(x, dict):
        return list(x)
    if isinstance(x, (list, tuple, set)):
        return list(x)
    return None


_UNARYOPS = {
    "neg": lambda a: -a,
    "not": lambda a: not a,
    "sqrt": _builtin_sqrt,
    "cbrt": _builtin_cbrt,
    "sum": _builtin_list_sum,
    "prod": _builtin_list_prod,
    "~": _builtin_bitnot,
    "angle": _builtin_angle,
    "++": _builtin_incr,
    "--": _builtin_decr,
}


def _curry2(fn):
    """两参函数柯里化：f(a)(b) 或 f(a,b) 均可用。"""
    return _Curried(fn, 2)


def _curry3(fn):
    """三参函数柯里化：f(a)(b)(c)。"""
    return _Curried(fn, 3)


class _Curried:
    """柯里化 VM 内建的包装对象（arity 个参可分步喂）。

    分步应用语义与原 `lambda a: (lambda b: fn(a, b))` 链逐字一致；多出来的信息只
    有一项：底层 `fn` 与 `arity` 可直接取。VM `_invoke` 在实参恰好齐 arity 时直接
    `fn(*args)`，不再逐层物化中间闭包（基准 scripts/bench.py 的 b06 显示链式
    `get(xs)(i)` 是最慢的内建调用形态）。齐 arity 的 CALL N 由编译器发出，其
    arity 表与 Matha 自举编译器严格同值（见 tests/test_curried_builtin_paths.py）。
    """
    __slots__ = ("fn", "arity")

    def __init__(self, fn, arity: int):
        self.fn = fn
        self.arity = arity

    def __call__(self, a):
        fn, ar = self.fn, self.arity
        if ar == 2:
            return lambda b: fn(a, b)
        return lambda b: (lambda c: fn(a, b, c))


def _raise_builtin(msg):
    raise RuntimeError(str(msg))


def _is_matha_function(v) -> bool:
    """Matha 可调用值判定：VM 闭包/部分应用记录，或任何 Python 可调用
    （内建函数/柯里化包装）。用于 type_of → "Function" 与 str/输出 →
    "<function>" 的四端统一（解释器为闭包元组/可调用，原生为
    TYPE_CLOSURE/TYPE_PARTIAL 记录与 .text 代码地址）。"""
    return isinstance(v, (Closure, Partial)) or callable(v)


def _builtin_str(v) -> str:
    """str(v)：可调用值统一为 "<function>"，其余沿用 Python str。
    与解释器 builtin_str_value / 原生 print 对齐。"""
    if _is_matha_function(v):
        return "<function>"
    return str(v)


def _norm_output(v):
    """输出流规范化：可调用值 → "<function>"，其余原样。"""
    return "<function>" if _is_matha_function(v) else v


def _builtin_type_of(v) -> str:
    """返回值类型名称（Matha 类型）——VM 内建，供自举代码使用。
    避免 stdlib 纯 Matha 实现的 type_of 与 str 互相调用死循环。"""
    if v is True or v is False or isinstance(v, bool):
        return "Bool"
    if isinstance(v, int):
        return "Int"
    if isinstance(v, float):
        return "Float"
    if isinstance(v, str):
        return "String"
    if isinstance(v, list):
        return "List"
    if isinstance(v, dict):
        return "Dict"
    if _is_matha_function(v):
        return "Function"
    if v is None:
        return "Null"
    return "Unknown"


def _builtin_mut_set_at(lst):
    """mut_set_at(lst)(idx)(v) → 原地把 lst[idx] 置为 v，返回 lst。

    唯一的列表可变原语：自举解释器用「占位符 + 原地更新」实现 let rec / and
    互递归绑定。env 为 CONS 共享的 [[name, value], ...] 结构，对共享 pair
    的原地修改对所有捕获该 env 的闭包同步可见。"""
    if not isinstance(lst, list):
        raise RuntimeError(f"mut_set_at() 需要列表，实际 {type(lst).__name__}")
    def at(idx):
        if not isinstance(idx, int):
            raise RuntimeError(f"mut_set_at() 索引需整数，实际 {idx!r}")
        def with_val(v):
            lst[idx] = v
            return lst
        return with_val
    return at


# ---------- dict 原语（纯 Matha 无法实现——无对应操作码） ----------

def _builtin_dict_keys(d):
    """dict_keys(d) → 键列表。无对应操作码，须 VM 原语。"""
    if not isinstance(d, dict):
        raise RuntimeError(f"dict_keys() 需要字典，实际 {type(d).__name__}")
    return list(d.keys())


def _builtin_dict_values(d):
    """dict_values(d) → 值列表。无对应操作码，须 VM 原语。"""
    if not isinstance(d, dict):
        raise RuntimeError(f"dict_values() 需要字典，实际 {type(d).__name__}")
    return list(d.values())


# ---------- 文本编码原语（二进制/三进制/十进制） ----------

def _builtin_encode_binary(text):
    """encode_binary(text) → 二进制编码字符串（base-2，空格分隔）。"""
    from src.text_encoding import encode_binary
    return encode_binary(text)


def _builtin_decode_binary(encoded):
    """decode_binary(encoded) → 从二进制编码还原文本。"""
    from src.text_encoding import decode_binary
    return decode_binary(encoded)


def _builtin_encode_ternary(text):
    """encode_ternary(text) → 三进制编码字符串（base-3，空格分隔）。"""
    from src.text_encoding import encode_ternary
    return encode_ternary(text)


def _builtin_decode_ternary(encoded):
    """decode_ternary(encoded) → 从三进制编码还原文本。"""
    from src.text_encoding import decode_ternary
    return decode_ternary(encoded)


def _builtin_encode_decimal(text):
    """encode_decimal(text) → 十进制编码字符串（Unicode 码点序列）。"""
    from src.text_encoding import encode_decimal
    return encode_decimal(text)


def _builtin_decode_decimal(encoded):
    """decode_decimal(encoded) → 从十进制编码还原文本。"""
    from src.text_encoding import decode_decimal
    return decode_decimal(encoded)


# ---------- 文件 I/O 原语（需 OS 访问，纯 Matha 无法实现） ----------
# 实现已下沉到内核 src.kernel.file_builtin（阶段 1：内核纯净），此处保留同名
# 别名以维持既有引用面与 `_default_builtins` 的注册顺序不变。
from src.kernel.file_builtin import (  # noqa: E402
    append_file as _builtin_append_file,
    read_file as _builtin_read_file,
    write_file as _builtin_write_file,
)


def _default_builtins() -> dict:
    """VM 内建：复用宿主 mathlib 注册的同一套数学/工具函数。"""
    from src.kernel.math_builtin import _register_math_builtins
    from src.kernel.regex_builtin import _register_regex_builtins
    from src.kernel.time_builtin import _register_time
    b: dict = {}
    _register_math_builtins(b)
    _register_regex_builtins(b)
    _register_time(b)
    # 正则内建 `匹配` 与引导文件 matha/parser.matha 的顶层 `func 匹配` 同名：二者
    # 合入同一模块时后者会遮蔽前者。故额外暴露一个不冲突的别名，供 matha/vm.matha
    # 委托正则匹配（其余内建名无此冲突，可直接按名委托）。
    b.setdefault("_bmatch", b["匹配"])
    # 基础原语（与宿主解释器一致）
    b.setdefault("len", len)
    b.setdefault("abs", abs)
    b.setdefault("int", int)
    b.setdefault("_to_int", int)  # 供 stdlib 增强版 int 分派到数值截断
    b.setdefault("float", float)
    b.setdefault("_to_float", float)  # 供 stdlib 增强版 float 分派到数值转换
    b.setdefault("str", _builtin_str)
    b.setdefault("bool", bool)
    b.setdefault("list", _builtin_list)
    b.setdefault("ord", ord)
    b.setdefault("chr", chr)
    b.setdefault("range", _curry2(_builtin_range))
    b.setdefault("type_of", _builtin_type_of)
    # 柯里化的序列工具（Matha 代码以 get(xs)(i) / append(xs)(x) 形式调用）
    b.setdefault("get", _curry2(lambda c, i: c[i]))
    b.setdefault("slice", _curry3(lambda c, s, e: c[s:e]))
    b.setdefault("append", _curry2(_builtin_append))
    b.setdefault("enumerate", lambda lst: [[i, v] for i, v in enumerate(lst)])
    # 原地追加（O(1) 摊还）：仅自举编译器 `_发` 等「构建器」在保证列表无别名
    # 共享时使用，语义上等价于 append 但避免整体复制导致的 O(n²)。
    b.setdefault("list_push", _curry2(_builtin_list_push))
    b.setdefault("mut_set_at", _builtin_mut_set_at)
    # dict 原语（纯 Matha 无法实现：无 keys/values/不可变更新操作码）
    b.setdefault("_dict_keys", _builtin_dict_keys)
    b.setdefault("_dict_values", _builtin_dict_values)
    b.setdefault("_dict_has", _curry2(lambda d, k: k in d))
    b.setdefault("_dict_put", _curry3(lambda d, k, v: {**d, k: v}))
    b.setdefault("_dict_remove", _curry2(lambda d, k: {kk: vv for kk, vv in d.items() if kk != k}))
    # 位运算原语（供自举 vm.matha 的 应用运算/应用一元 使用）：自举源码不宜书写
    # `&`/`|`/`⊕`/`~` 运算符（会与「解释自身字节码」形成自引用，并阻碍 vm.matha
    # 自解析），故以宿主原语暴露；语义逐条复用 _BINOPS / _UNARYOPS（含非整数操作数
    # 的报错定位），确保与宿主 VM 位运算逐字节一致。
    b.setdefault("_bit_and", _curry2(_BINOPS["&"]))
    b.setdefault("_bit_or", _curry2(_BINOPS["|"]))
    b.setdefault("_bit_xor", _curry2(_BINOPS["⊕"]))
    b.setdefault("_bit_not", _UNARYOPS["~"])
    # 集合运算原语（供自举 vm.matha 的 应用运算 使用）：自举源码不宜书写集合运算符
    # （会与「解释自身字节码」形成自引用，并阻碍 vm.matha 自解析），故以宿主原语
    # 暴露；语义逐条复用 _BINOPS 的 _set_*（有序去重列表），确保与宿主 VM 逐字节一致。
    b.setdefault("_set_union", _curry2(_BINOPS["∪"]))
    b.setdefault("_set_inter", _curry2(_BINOPS["∩"]))
    b.setdefault("_set_diff", _curry2(_BINOPS["⊖"]))
    b.setdefault("_set_comp", _curry2(_BINOPS["~"]))
    b.setdefault("_set_prod", _curry2(_BINOPS["×"]))
    b.setdefault("_set_subset", _curry2(_BINOPS["⊆"]))
    # 聚合原语（供自举 vm.matha 的 应用一元 使用）：∑/∏ 直接复用一元内建实现，
    # 确保与宿主 VM 逐字节一致（含非列表报错）。
    b.setdefault("_list_sum", _builtin_list_sum)
    b.setdefault("_list_prod", _builtin_list_prod)
    # 空字典常量（{} 在 Matha 语法中为空集合构造，故用 VM 值提供空字典）
    b.setdefault("_empty_dict", {})
    # 列表去重：与宿主解释器 builtin_列表去重 同语义（按 == 去重、保序），
    # 也是 _builtin_make_set 的基础操作，此前只有解释器后端提供。
    b.setdefault("去重", _builtin_dedup)
    # 文件 I/O 原语（需 OS 访问）
    b.setdefault("_read_file", _builtin_read_file)
    b.setdefault("_write_file", _curry2(_builtin_write_file))
    b.setdefault("_append_file", _curry2(_builtin_append_file))
    # 文本编码原语（二进制/三进制/十进制）
    b.setdefault("encode_binary", _builtin_encode_binary)
    b.setdefault("decode_binary", _builtin_decode_binary)
    b.setdefault("encode_ternary", _builtin_encode_ternary)
    b.setdefault("decode_ternary", _builtin_decode_ternary)
    b.setdefault("encode_decimal", _builtin_encode_decimal)
    b.setdefault("decode_decimal", _builtin_decode_decimal)
    b.setdefault("错误", _raise_builtin)
    b.setdefault("MathaIOError", lambda m: ["MathaIOError", m])
    b.setdefault("真", True)
    b.setdefault("假", False)
    b.setdefault("null", None)
    b.setdefault("None", None)
    return b


def _make_output(vm):
    """输出(value) → 记录到 VM 输出流，返回原值（可链式）。

    可调用值记为 "<function>"（与解释器/原生一致）；其余原样保留。"""
    def emit(value):
        vm.outputs.append(_norm_output(value))
        return value
    return emit


def _make_guarded_call(vm):
    """调用捕获(fn)(args) → 运行 fn(*args)，返回 tagged 结果：
    正常 ["__正常__", 值]；异常 ["__异常__", 消息字符串]。

    自举解释器 try/catch 的底层原语：VM 无异常帧机制，错误以 Python
    异常穿越 VM 帧，须在宿主层拦截后交还 Matha 层处理。"""
    def guarded(fn):
        def run(args):
            try:
                return ["__正常__", vm.invoke_value(fn, args)]
            except Exception as e:  # noqa: BLE001 — 捕获一切错误交 Matha 层
                return ["__异常__", str(e)]
        return run
    return guarded


def _builtin_typeof(value):
    """typeof(v) → Matha 类型名。"""
    if value is None:
        return "空"
    if isinstance(value, bool):
        return "布尔"
    if isinstance(value, int):
        return "整数"
    if isinstance(value, float):
        return "浮点"
    if isinstance(value, str):
        return "文本"
    if isinstance(value, list):
        return "列表"
    if isinstance(value, dict):
        return "字典"
    return "函数"


def _builtin_safe_index(container, key):
    """a.?b：容器为 None/缺失键时返回 None，不抛错。"""
    if container is None:
        return None
    try:
        return container[key]
    except (KeyError, IndexError, TypeError):
        return None


def _builtin_safe_attr(obj, name):
    """a.?b：obj 为 None 时返回 None。"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, str(name), None)


def _builtin_dedup(values):
    """去重(列表) → 按 == 去重并保序的 list。"""
    if not isinstance(values, (list, tuple)):
        raise RuntimeError(f"去重() 需要列表，实际 {type(values).__name__}")
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def _builtin_make_set(form, variables, elements):
    """构造集合(form, variables, elements) → list（去重、保序）。"""
    return _builtin_dedup(elements or [])


def _builtin_append(xs, x):
    """append(xs, x) → 新列表（非原地，保持纯函数语义）。"""
    if xs is None:
        return [x]
    r = list(xs)
    r.append(x)
    return r


def _builtin_list_push(lst, x):
    """list_push(lst, x) → 原地追加 x 并返回 lst（O(1) 摊还）。

    仅供**构建器**内部使用：调用方（自举编译器的 `_发`）保证该列表由单一的
    线性函数式链持有、不与其它绑定别名共享，故原地更新对外可观察结果与
    「返回新列表」等价，同时避免 `append` 的 O(n²) 整体复制——它曾让自举
    编译 parser.matha 多花约 15s（整体约减半）。"""
    lst.append(x)
    return lst


def _make_domain_loader(vm: "VM"):
    """`加载领域(name)` 内建：显式拉取一个领域插件的符号表入全局。"""
    def _load(name):
        key = name if isinstance(name, str) else str(name)
        resolver = vm.domain_resolver
        if resolver is None:
            raise RuntimeError(
                f"加载领域「{key}」失败：本次运行未接入插件层（domain_resolver 为 None）。"
                f"请经由宿主入口运行（src.kernel.exec_api.run），或先给 VM 注入 resolver。")
        table = resolver.require(key, vm.globals)
        if not table:
            cand = resolver.unknown(key)
            hint = "候选插件：" + " / ".join(cand) if cand else "清单中无同名插件"
            raise RuntimeError(f"未找到领域插件「{key}」（{hint}）")
        return key
    return _load


class _GlobalScope(dict):
    """VM 全局表：未命中的名字可交给宿主注入的插件解析器懒加载。

    `dict.__missing__` 只在真正缺失时被调用，因此热路径（已存在的内建/用户定义）
    零开销；解析器为 None 或认不得该符号时依旧报错。报错用
    `MathaUndefinedNameError`（既是 KeyError、消息又与解释器逐字一致），
    这样主链与遗留后端的 `catch (e) { 输出(e) }` 得到同一文本。
    这一机制是「静默全量注册」的代替品：只有被程序真正引用到的领域插件才会 import。
    """

    __slots__ = ("resolver",)

    def __init__(self, data=None, resolver=None):
        super().__init__(data or {})
        self.resolver = resolver

    def __missing__(self, key):
        resolver = self.resolver
        if resolver is not None:
            value = resolver.resolve_into(self, key)
            if value is not None:
                return value
        raise MathaUndefinedNameError(f"未定义变量 '{key}'")


class VM:
    def __init__(self, mod: MModule, builtins: dict | None = None, verbose: bool = False):
        self.mod = mod
        self.globals: _GlobalScope = _GlobalScope(
            builtins if builtins is not None else _default_builtins())
        # 领域插件加载器（阶段 1 第 4 项）：由宿主注入一个鸭子类型的 resolver
        # （见 src/plugin_api.py::PluginResolver），内核不 import 插件层，因此这里
        # 只依赖它的 `require(name, target)` / `unknown(name)` / `resolve_into(t, s)`。
        self.globals.setdefault("加载领域", _make_domain_loader(self))
        self.globals.setdefault("调用捕获", _make_guarded_call(self))
        self.globals.setdefault("输出", _make_output(self))
        self.globals.setdefault("print", _make_output(self))
        self.globals.setdefault("typeof", _builtin_typeof)
        self.globals.setdefault("安全索引", _curry2(_builtin_safe_index))
        self.globals.setdefault("安全取属性", _curry2(_builtin_safe_attr))
        self.globals.setdefault("构造集合", _curry3(_builtin_make_set))
        self.outputs: list = []
        # `？` 公式模式库（`#：？公式` 登记的模式）
        self.formulas = _fs.FormulaLibrary()
        self.verbose = verbose
        # 主帧（模块全局帧）
        self.main_frame = Frame("__main__", mod.main_code, [], None)
        self.halted = False
        # 全局函数注册为闭包（定义帧 = 主帧，使函数间互引可达）
        for name, fn in mod.functions.items():
            self.globals[name] = Closure(fn, self.main_frame)
        self.frames: list[Frame] = [self.main_frame]

    # ---------- 运行 ----------

    @property
    def domain_resolver(self):
        return self.globals.resolver

    @domain_resolver.setter
    def domain_resolver(self, resolver) -> None:
        self.globals.resolver = resolver

    def run(self):
        frames = self.frames
        dispatch = self._dispatch
        while frames and not self.halted:
            f = frames[-1]
            ins = f.code[f.pc]
            f.pc += 1
            dispatch(ins[0], ins, f, frames)
        return self.outputs

    def call(self, name: str, *args):
        """在已初始化的 VM 上调用全局函数（供外部驱动自举链路）。"""
        fn = self.globals[name]
        frames = self.frames
        base = len(frames)
        f = frames[-1]
        f.stack.append(fn)
        for a in args:
            f.stack.append(a)
        dispatch = self._dispatch
        dispatch(OP.CALL, (OP.CALL, len(args)), f, frames)
        while len(frames) > base:
            f = frames[-1]
            ins = f.code[f.pc]
            f.pc += 1
            dispatch(ins[0], ins, f, frames)
        # 返回值在调用帧（base-1，通常是主帧）栈顶
        return frames[base - 1].stack.pop()

    def invoke_value(self, fn, args: list | None = None):
        """调用任意 VM 可调用值（Closure/Partial/内建），返回结果。

        供 调用捕获 等捕获型内建回调 Matha 编译函数（如自举解释器的
        try/catch thunk）。异常传播时清掉未完成帧，保持帧栈整洁。"""
        args = list(args) if args else []
        base = len(self.frames)
        f = self.frames[-1]
        f.stack.append(fn)
        for a in args:
            f.stack.append(a)
        frames = self.frames
        dispatch = self._dispatch
        try:
            dispatch(OP.CALL, (OP.CALL, len(args)), f, frames)
            while len(frames) > base:
                f = frames[-1]
                ins = f.code[f.pc]
                f.pc += 1
                dispatch(ins[0], ins, f, frames)
            return frames[base - 1].stack.pop()
        finally:
            if len(self.frames) > base:
                del self.frames[base:]

    def _dispatch(self, op, ins, f: Frame, frames: list) -> None:
        # 分派链按操作码实测出现频率排序（自举编译负载：LOAD_LOCAL 23%、
        # CALL 10%、LOAD_GLOBAL/BINOP 各 10%、JZ 8%、PUSH_CONST 7%、GET_ATTR 7%…），
        # 高频指令靠前可将近半指令的比较次数砍半。判定顺序不影响语义。
        C = self.mod.constants
        st = f.stack

        if op == OP.LOAD_LOCAL:
            st.append(f.locals[ins[1]])
        elif op == OP.CALL:
            argc = ins[1]
            # 栈布局：[..., fn, arg1, ..., argN]（栈顶为最后一个参数）
            if argc:
                fn = st[-argc - 1]
                args = st[-argc:]
                del st[-argc - 1:]
            else:
                fn = st.pop()
                args = []
            self._invoke(fn, args, f, frames)
        elif op == OP.LOAD_GLOBAL:
            st.append(self.globals[C[ins[1]]])
        elif op == OP.BINOP:
            b = st.pop(); a = st.pop()
            st.append(_BINOPS[C[ins[1]]](a, b))
        elif op == OP.JZ:
            if not st.pop():
                f.pc = ins[1]
        elif op == OP.PUSH_CONST:
            st.append(C[ins[1]])
        elif op == OP.GET_ATTR:
            obj = st.pop()
            key = C[ins[1]]
            # dict 缺失字段返回 None（与宿主解释器 PathExpr 语义一致）
            if isinstance(obj, dict):
                st.append(obj.get(key))
            else:
                st.append(obj[key])
        elif op == OP.DUP:
            st.append(st[-1])
        elif op == OP.RET:
            val = st.pop() if st else None
            frames.pop()
            if frames:
                frames[-1].stack.append(val)
        elif op == OP.JNZ:
            if st.pop():
                f.pc = ins[1]
        elif op == OP.POP:
            st.pop()
        elif op == OP.STORE_LOCAL:
            f.locals[ins[1]] = st.pop()
        elif op == OP.JMP:
            f.pc = ins[1]
        elif op == OP.INDEX_GET:
            idx = st.pop(); c = st.pop()
            try:
                st.append(c[idx])
            except TypeError:
                # 不可下标对象（如 `5[0]`）：VM 历史上直接漏出 Python
                # `TypeError: 'int' object is not subscriptable`，而解释器给
                # 领域消息。归一到与 src/interp.py 逐字一致的文本（越界 IndexError
                # 不在此列：两端均透传 Python IndexError，已一致）。
                raise MathaRuntimeError(
                    f"索引操作不支持: {type(c).__name__}[{idx}]") from None
        elif op == OP.PUSH_TRUE:
            st.append(True)
        elif op == OP.PUSH_FALSE:
            st.append(False)
        elif op == OP.LOAD_OUTER:
            st.append(self._outer(f, ins[1]).locals[ins[2]])
        elif op == OP.BUILD_LIST:
            n = ins[1]
            # st[-n:] 为栈底→栈顶，即元素按书写顺序压入的顺序
            if n:
                items = list(st[-n:])
                del st[-n:]
            else:
                items = []
            st.append(items)
        elif op == OP.PUSH_NULL:
            st.append(None)
        elif op == OP.UNPACK_SEQ:
            seq = st.pop()
            seq = seq if seq is not None else []
            n = ins[1]
            for i in range(n):
                st.append(seq[i] if i < len(seq) else None)
        elif op == OP.LOAD_OUTER_BOX:
            st.append(self._outer(f, ins[1]).locals[ins[2]].value)
        elif op == OP.STORE_GLOBAL:
            self.globals[C[ins[1]]] = st.pop()
        elif op == OP.MAKE_CLOSURE:
            st.append(Closure(self.mod.functions[ins[1]], f))
        elif op == OP.UNARYOP:
            st.append(_UNARYOPS[C[ins[1]]](st.pop()))
        elif op == OP.BUILD_DICT:
            n = ins[1]
            pairs = []
            for _ in range(n):
                v = st.pop(); k = st.pop()
                pairs.append((k, v))
            d = {}
            for k, v in reversed(pairs):  # 栈顶=末对；按源码插入序重建
                d[k] = v
            st.append(d)
        elif op == OP.BUILD_SLICE:
            end = st.pop(); start = st.pop(); c = st.pop()
            st.append(c[start:end])
        elif op == OP.LOAD_BOX:
            st.append(f.locals[ins[1]].value)
        elif op == OP.MAKE_BOX:
            f.locals[ins[1]] = Box(None)
        elif op == OP.STORE_BOX:
            f.locals[ins[1]].value = st.pop()
        elif op == OP.OUTPUT:
            val = st.pop()
            self.outputs.append(_norm_output(val))
            if self.verbose:
                print(val)
        elif op == OP.RAISE:
            raise MathaRuntimeError(str(st.pop()))
        elif op == OP.FORMULA_SCHEMA:
            # `#N：？公式` 登记为模式：槽不可求值，只记静态规格。
            seg_id, text, shp, slots = C[ins[1]]
            self.formulas.register_meta(seg_id, text, shp, slots)
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
            # 柯里化内建：实参恰好齐 arity 时直接调底层 fn(*args)，不物化中间闭包；
            # 不足/超出时仍逐层应用，保持与原 lambda 链一致的偏应用值与错误行为。
            if type(fn) is _Curried and len(args) == fn.arity:
                caller.stack.append(fn.fn(*args))
                return
            # Python 内建：逐参应用以兼容柯里化包装（_curry2 等）
            r = fn
            for a in args:
                r = r(a) if callable(r) else r
            caller.stack.append(r)
            return

        raise MathaRuntimeError(f"不可调用的值: {fn!r}")


def run_module(mod: MModule, verbose: bool = False,
               builtins: dict | None = None,
               domain_resolver: object | None = None) -> list:
    """运行一个已编译模块。

    `domain_resolver` 为宿主注入的插件解析器（鸭子类型，见 `_make_domain_loader`），
    内核不依赖 `src.plugin_api`。不传时仍可运行，仅 `@：【加载领域】` 会给出明确报错。
    """
    vm = VM(mod, builtins=builtins, verbose=verbose)
    if domain_resolver is not None:
        vm.domain_resolver = domain_resolver
    return vm.run()


def run_source(source: str, verbose: bool = False) -> list:
    from src.mbc.compiler import compile_source
    return run_module(compile_source(source), verbose=verbose)
