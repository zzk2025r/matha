# -*- coding: utf-8 -*-
"""x86-64 原生发射器端到端测试：编译 → 运行 exe → 校验 stdout / 退出码。"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.mbc import compile_source, run_module
from src.mbc import opcodes as OP
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.mbc.native import compile_to_exe, NativeNotSupported, MAX_NATIVE_ARITY
from src.parser import parse


def name_of(op_name: str):
    return getattr(OP, op_name)


def _run(src: str) -> tuple[int, str]:
    """编译源码为 exe 并运行，返回 (exit_code, stdout)。"""
    exe = os.path.join(tempfile.gettempdir(), "test_native.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    # splitlines 归一化 CRLF/LF，多行期望值直接用 "\n" 书写
    lines = r.stdout.decode("utf-8", "replace").strip().splitlines()
    return r.returncode & 0xFFFFFFFF, "\n".join(lines)


# ---------- 整数算术 ----------

def test_const_42():
    rc, out = _run("#1：[42]")
    assert rc == 0 and out == "42"


def test_neg7():
    rc, out = _run("#1：[-7]")
    assert rc == 0 and out == "-7"


def test_neg_paren():
    rc, out = _run("#1：[-(2+5)]")
    assert rc == 0 and out == "-7"


def test_add():
    rc, out = _run("#1：[1+2]")
    assert rc == 0 and out == "3"


def test_mul():
    rc, out = _run("#1：[6*7]")
    assert rc == 0 and out == "42"


def test_mod():
    rc, out = _run("a=17\nb=5\n#1：[a % b]")
    assert rc == 0 and out == "2"


# ---------- 整除 / 取模：Python floor 语义 + 除零抛错 ----------

@pytest.mark.parametrize("expr,expected", [
    # x86 idiv 向零截断，Python 向下取整：符号相异且整除不尽时差 1
    ("7 // 2", "3"), ("-7 // 2", "-4"), ("7 // -2", "-4"), ("-7 // -2", "3"),
    ("8 // 4", "2"), ("-8 // 4", "-2"), ("1 // 2", "0"), ("-1 // 2", "-1"),
    # Python 的 % 取除数的符号，idiv 的余数取被除数的符号
    ("7 % 2", "1"), ("-7 % 2", "1"), ("7 % -2", "-1"), ("-7 % -2", "-1"),
    ("8 % 4", "0"), ("-8 % 4", "0"),
    # 浮点路径同样要对齐（f_floordiv / f_mod）
    ("7.0 // 2.0", "3.0"), ("-7.0 // 2.0", "-4.0"), ("7.0 // -2.0", "-4.0"),
    ("7.5 % 2.0", "1.5"), ("-7.5 % 2.0", "0.5"), ("7.5 % -2.0", "-0.5"),
])
def test_floor_division_and_modulo(expr, expected):
    assert _run("#1：[%s]" % expr) == (0, expected)


def test_modulo_by_minus_one_avoids_overflow():
    """除数为 -1 短路：INT64_MIN / -1 会让 idiv 触发 #DE 溢出。"""
    rc, out = _run("a = -9223372036854775807 - 1\n"
                   "#1：[a // -1]\n#2：[a // 1]\n#3：[a % -1]\n")
    assert rc == 0 and out == "-9223372036854775808\n-9223372036854775808\n0"


@pytest.mark.parametrize("expr", [
    "1 // 0", "1 % 0", "0 // 0", "0 % 0", "1 // (2 - 2)", "1 % (2 - 2)",
    "-7 // 0", "-7 % 0",
    "1.0 // 0.0", "1.0 % 0.0", "2.5 // 0.0", "2.5 % 0.0",
])
def test_division_by_zero_is_catchable(expr):
    """除零须是可捕获的异常，而非 #DE / 静默 inf、NaN。"""
    assert _run('try {\n  #1：[%s]\n} catch (e) {\n  输出("零")\n}\n输出("后")\n' % expr) \
        == (0, "零\n后")


def test_division_by_zero_uncaught_exits_one():
    rc, out = _run('输出("前")\n#1：[1 // 0]\n')
    assert rc == 1 and out == "前"


# ---------- 比较运算 ----------

def test_eq_true():
    rc, out = _run("#1：[3==3]")
    assert rc == 0 and out == "True"


def test_ne_true():
    rc, out = _run("#1：[3!=4]")
    assert rc == 0 and out == "True"


def test_lt_true():
    rc, out = _run("#1：[2<5]")
    assert rc == 0 and out == "True"


# ---------- 全局变量 ----------

def test_assign_only():
    rc, out = _run("x=1\n")
    assert rc == 0


# ---------- 单参数函数 ----------

def test_idfn():
    rc, out = _run("func f(a: Int) -> Int = (a) => a\n#1：[f(99)]")
    assert rc == 0 and out == "99"


def test_sqfn():
    rc, out = _run("func f(a: Int) -> Int = (a) => a*a\n#1：[f(9)]")
    assert rc == 0 and out == "81"


# ---------- 递归 ----------

def test_factorial():
    rc, out = _run(
        "func fact(n: Int) -> Int = (n) =>\n"
        "  if n <= 1 then 1 else n * fact(n - 1)\n"
        "#1：[fact(10)]")
    assert rc == 0 and out == "3628800"


def test_fib():
    rc, out = _run(
        "func fib(n: Int) -> Int = (n) =>\n"
        "  if n < 2 then n else fib(n - 1) + fib(n - 2)\n"
        "#1：[fib(20)]")
    assert rc == 0 and out == "6765"


# ---------- 多参数函数 ----------

def test_zero_arity():
    rc, out = _run("func 五() -> Int = () => 5\n#1：[五()]")
    assert rc == 0 and out == "5"


def test_two_args_order_sensitive():
    """形参顺序敏感：10-3=7，3-10=-7。"""
    rc, out = _run(
        "func sub2(a: Int, b: Int) -> Int = (a, b) => a - b\n"
        "#1：[sub2(10, 3)]\n"
        "#2：[sub2(3, 10)]")
    assert rc == 0 and out.splitlines() == ["7", "-7"]


def test_three_args_order_sensitive():
    """三个形参各自取不同权重，顺序错乱会立刻显现。"""
    rc, out = _run(
        "func mix3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a*100 + b*10 + c\n"
        "#1：[mix3(1, 2, 3)]\n"
        "#2：[mix3(3, 2, 1)]")
    assert rc == 0 and out.splitlines() == ["123", "321"]


def test_max_arity():
    rc, out = _run(
        "func s8(a1: Int, a2: Int, a3: Int, a4: Int,"
        " a5: Int, a6: Int, a7: Int, a8: Int) -> Int ="
        " (a1, a2, a3, a4, a5, a6, a7, a8) =>"
        " a1*10000000 + a2*1000000 + a3*100000 + a4*10000"
        " + a5*1000 + a6*100 + a7*10 + a8\n"
        "#1：[s8(1,2,3,4,5,6,7,8)]")
    assert rc == 0 and out == "12345678"


def test_nested_multi_arg_call():
    """嵌套：内层 2 参调用作为外层 2 参调用的实参。"""
    rc, out = _run(
        "func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
        "func mul2(a: Int, b: Int) -> Int = (a, b) => a * b\n"
        "#1：[mul2(add2(2, 3), add2(4, 5))]")
    assert rc == 0 and out == "45"


def test_multi_arg_as_operand_of_multi_arg():
    rc, out = _run(
        "func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
        "func sub2(a: Int, b: Int) -> Int = (a, b) => a - b\n"
        "#1：[sub2(add2(10, 4), add2(1, 1))]")
    assert rc == 0 and out == "12"


def test_multi_arg_in_expression():
    """多参调用结果参与普通表达式运算。"""
    rc, out = _run(
        "func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
        "#1：[add2(3, 4) * 10 + add2(1, 1)]")
    assert rc == 0 and out == "72"


def test_multi_arg_recursive():
    """多参数递归（类 Ackermann 递减）：a1*10+a2 递减到 0。"""
    rc, out = _run(
        "func f(n: Int, acc: Int) -> Int = (n, acc) =>\n"
        "  if n <= 0 then acc else f(n - 1, acc + n)\n"
        "#1：[f(4, 0)]")
    assert rc == 0 and out == "10"


def test_multi_arg_forward_reference():
    """先调用的函数 arity 预扫描与声明顺序无关。"""
    rc, out = _run(
        "#1：[late(20, 22)]\n"
        "func late(a: Int, b: Int) -> Int = (a, b) => a + b")
    assert rc == 0 and out == "42"


def test_mixed_arity_calls():
    """单参与多参调用混合。"""
    rc, out = _run(
        "func dbl(x: Int) -> Int = (x) => x * 2\n"
        "func add3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a + b + c\n"
        "#1：[add3(dbl(2), 3, dbl(4))]")
    assert rc == 0 and out == "15"


def test_partial_application_still_works():
    """未完全应用的调用保持 CALL 1 柯里化语义（VM 与原生均支持）。"""
    mod = compile_source("func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
                         "#1：[add2(1)]")
    calls = [ins for ins in mod.main_code if ins[0] == name_of("CALL")]
    assert calls == [(OP.CALL, 1)]


def test_func_declaration_value_is_curriable():
    """顶层 func 值必须以闭包记录暴露，支持偏应用/柯里化与一等使用。

    回归：func 名默认发射为 .text 纯代码地址，apply_rt 对堆外值走 ar_plain
    直接 tail-jmp、忽略实参数；`g(1)(2)`、`let h = g(1)` 后再调用、或把 g
    放进列表再经运行时值调用，都会访问违例崩溃（0xC0000005）。"""
    src = ("func g(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a*100 + b*10 + c\n"
           "let h = g(1)(2)\n"
           "输出(h(3))\n"
           "let fns = [g]\n"
           "输出(fns[0](4)(5)(6))\n")
    rc, out = _run(src)
    assert rc == 0 and out == "123\n456"


def test_func_declaration_first_class_in_list():
    """把顶层 func 放入列表后经运行时值完全应用，也必须走柯里化分派。"""
    src = ("func add3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a + b + c\n"
           "let fns = [add3]\n"
           "输出(fns[0](1)(2)(3))\n")
    rc, out = _run(src)
    assert rc == 0 and out == "6"


@pytest.mark.parametrize("name", [
    "__native_unresolved_probe__",
])
def test_unimplemented_builtin_rejected_at_compile_time(name, monkeypatch):
    """引用「VM 能解析、原生未实现」的全局必须在编译期报错，而非运行期崩溃。

    回归：LOAD_GLOBAL 对未注册名字载入 0 值，调用时经 apply_rt → ar_plain
    跳到 rax=0，表现为无堆栈的访问违例（0xC0000005），极难定位。
    已实现 MathaIOError 后真实名字无未实现者，故以 monkeypatch 注入探针名，
    直接验证该防御分支仍然有效。
    """
    from src.mbc import native as nat
    monkeypatch.setattr(nat, "_UNRESOLVED_GLOBALS",
                        nat._UNRESOLVED_GLOBALS | {name})
    src = f"输出({name}(1))\n"
    with pytest.raises(NativeNotSupported) as ei:
        compile_to_exe(src)
    msg = str(ei.value)
    assert repr(name) in msg, f"错误消息应点名 {name!r}，实际：{msg}"
    assert "未实现全局" in msg


@pytest.mark.parametrize("src", [
    "let get = 5 in 输出(get)\n",                    # 普通变量与内建同名
    "let sqrt = 7 in 输出(sqrt)\n",
    "func abs(x: Int) -> Int = (x) => x + 1\n输出(abs(1))\n",   # 用户函数覆盖
    "func append(x: Int) -> Int = (x) => x * 2\n输出(append(3))\n",
    'let s = "get" in 输出(1)\n',                    # 仅作文本常量出现
    "let f = (x) => let abs = x + 1 in abs in 输出(f(1))\n",  # 局部闭包捕获
    "func get(x: Int) -> Int = (x) => x * 10\n输出(get(4))\n",  # 用户函数覆盖 get
])
def test_same_name_as_builtin_still_compiles(src):
    """同名但确实是普通变量/用户函数/字符串常量的场景不得误报。"""
    compile_to_exe(src)


def test_shadowed_builtin_name_resolves_to_variable():
    """`let get = 5` 读全局单元，不得被同名内建 get 的闭包记录劫持。"""
    assert _run("let get = 5 in 输出(get)\n") == (0, "5")


def test_user_function_overrides_builtin_get():
    """`func get` 是用户函数，读 fn:get 代码地址而非内建闭包槽。"""
    assert _run("func get(x: Int) -> Int = (x) => x * 10\n输出(get(4))\n") == (0, "40")


# ---------- 砖块 10：异常（raise / 错误 / try-catch-finally）----------

def test_try_catch_captures_raise_message():
    assert _run('try { raise "boom" } catch (e) { 输出(e) }\n') == (0, "boom")


def test_try_normal_path_skips_catch():
    assert _run('try { 输出("A") } catch (e) { 输出("B") }\n') == (0, "A")


def test_try_finally_runs_both_paths():
    assert _run('try { 输出("T") } finally { 输出("F") }\n') == (0, "T\nF")
    assert _run('try { raise "x" } catch (e) { 输出("C") } finally { 输出("F") }\n'
                ) == (0, "C\nF")


def test_error_builtin_raises_and_is_caught():
    assert _run('try { 错误("bad") } catch (e) { 输出(e) }\n') == (0, "bad")


def test_raise_unwinds_across_nested_frames():
    src = ("func boom(n: Int) -> Int = (n) =>\n"
           "  if n <= 0 then 错误(\"deep\") else boom(n - 1)\n"
           "try { boom(5) } catch (e) { 输出(e) }\n")
    assert _run(src) == (0, "deep")


def test_catch_reraise_reaches_outer_handler():
    assert _run(
        'try { try { raise "in" } catch (e) { raise "out" } }'
        ' catch (e) { 输出(e) }\n') == (0, "out")


def test_raise_int_uses_decimal_string():
    assert _run('try { raise 42 } catch (e) { 输出(e) }\n') == (0, "42")


def test_uncaught_raise_exits_one():
    rc, out = _run('输出("before")\nraise "unhandled"\n')
    assert rc == 1 and out == "before"


def test_handler_stack_balanced_across_many_calls():
    """连续 1728 次 raise/catch 不泄漏处理器栈（>1638 条 40 字节记录即溢出 64KB）。"""
    src = ("let xs = [0,0,0,0,0,0,0,0,0,0,0,0]\n"
           "for a in xs { for b in xs { for c in xs {"
           ' try { 错误("x") } catch (e) { 输出(1) } } } }\n'
           '输出("done")\n')
    rc, out = _run(src)
    lines = out.split("\n")
    assert rc == 0 and lines[-1] == "done" and set(lines[:-1]) == {"1"}
    assert len(lines) == 1728 + 1


# ---------- 砖块 9：UNPACK_SEQ 解构 ----------

_UNPACK_CASES = [
    # (说明, 源码, 期望 stdout)
    ("二元解构求和", "let (a, b) = [1, 2] in 输出(a + b)\n", "3"),
    ("三元解构求和", "let (a, b, c) = [1, 2, 3] in 输出(a + b + c)\n", "6"),
    ("解构单项", "let (a) = [7] in 输出(a)\n", "7"),
    ("顺序敏感", "let (a, b) = [10, 20] in 输出(a * 100 + b)\n", "1020"),
    ("解构后分别读", "let (a, b) = [1, 2] in 输出(a)\n输出(b)\n", "1\n2"),
    ("嵌套解构", "let (a, b) = [1, 2] in let (c, d) = [3, 4] in 输出(a + b + c + d)\n", "10"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _UNPACK_CASES],
                         ids=[c[0] for c in _UNPACK_CASES])
def test_unpack_seq_list(src, expected):
    """列表解构：压栈顺序须与 vm.py:515 一致（e0 在 e(n-1) 之下）。"""
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _UNPACK_CASES],
                         ids=[c[0] for c in _UNPACK_CASES])
def test_unpack_seq_matches_vm(src, expected):
    """解构结果与 VM 逐案对齐。"""
    assert [str(v) for v in run_module(compile_source(src))] == expected.split("\n")


def test_unpack_short_sequence_fills_none():
    """长度不足的解构：缺项为 None（vm.py:520 的 `else None`）。"""
    rc, out = _run("let (a, b) = [1] in 输出(a)\n输出(b)\n")
    assert rc == 0 and out.split("\n") == ["1", "None"]


def test_unpack_from_string_yields_chars():
    """字符串解构按字节取，与 VM 的 seq[i] 单字符语义一致。"""
    rc, out = _run("let (a, b) = \"hi\" in 输出(a)\n输出(b)\n")
    assert rc == 0 and out.split("\n") == ["h", "i"]


def test_unpack_non_sequence_yields_all_none():
    """非序列解构：全部为 None（VM 侧同样不抛错的路径之外，原生端取 None）。"""
    rc, out = _run("let (a, b) = 5 in 输出(a)\n输出(b)\n")
    assert rc == 0 and out.split("\n") == ["None", "None"]


# ---------- for 循环（依赖内建 get） ----------

_FOR_CASES = [
    ("for 顶层", "for i in [1, 2, 3] {\n输出(i)\n}\n", "1\n2\n3"),
    ("for 累加", "let s = 0\nfor i in [1, 2, 3] {\n  s = s + i\n}\n输出(s)\n", "6"),
    ("for 临时累加", "let s = 0\nfor i in [1, 2, 3] {\n  let t = i * 2\n  s = s + t\n}\n输出(s)\n", "12"),
    ("for 字符串", "for c in \"abc\" {\n输出(c)\n}\n", "a\nb\nc"),
    ("for 双变量", "for (i, j) in [[1, 2], [3, 4]] {\n输出(i + j)\n}\n", "3\n7"),
    ("嵌套 for", "for i in [1, 2] {\nfor j in [10, 20] {\n输出(i + j)\n}\n}\n", "11\n21\n12\n22"),
    ("循环变量遮蔽外层", "let i = 99\nfor i in [1, 2] {\n输出(i)\n}\n输出(i)\n", "1\n2\n2"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _FOR_CASES],
                         ids=[c[0] for c in _FOR_CASES])
def test_for_loop(src, expected):
    """for 循环经 `get(xs)(i)` 驱动，内建 get 缺失时整类循环无法编译。"""
    assert _run(src) == (0, expected)


# ---------- 砖块 8：BUILD_SLICE 切片 ----------

_SLICE_CASES = [
    ("基本列表切片", "let y = [0,1,2,3,4] in 输出(y[1:3])\n", "[1, 2]"),
    ("字符串切片", 'let s = "hello" in 输出(s[1:3])\n', "el"),
    ("省略 stop", "let y = [0,1,2,3,4] in 输出(y[2:])\n", "[2, 3, 4]"),
    ("省略 start", "let y = [0,1,2,3,4] in 输出(y[:2])\n", "[0, 1]"),
    ("两端省略", "let y = [0,1,2] in 输出(y[:])\n", "[0, 1, 2]"),
    ("负 start", "let y = [0,1,2,3,4] in 输出(y[-2:])\n", "[3, 4]"),
    ("负 stop", "let y = [0,1,2,3,4] in 输出(y[:-1])\n", "[0, 1, 2, 3]"),
    ("两端为负", "let y = [0,1,2,3,4] in 输出(y[-4:-2])\n", "[1, 2]"),
    ("stop 越界", "let y = [0,1] in 输出(y[0:99])\n", "[0, 1]"),
    ("start 越界", "let y = [0,1] in 输出(y[9:99])\n", "[]"),
    ("空区间", "let y = [0,1] in 输出(y[1:1])\n", "[]"),
    ("反向区间", "let y = [0,1,2] in 输出(y[3:1])\n", "[]"),
    ("极端负值", "let y = [0,1,2] in 输出(y[-99:99])\n", "[0, 1, 2]"),
    ("变量边界", "let y = [0,1,2,3,4] in let a = 1 in let b = 3 in 输出(y[a:b])\n", "[1, 2]"),
    ("变量负边界", "let y = [0,1,2,3,4] in let a = -3 in let b = -1 in 输出(y[a:b])\n", "[2, 3]"),
    ("嵌套切片", "let y = [0,1,2,3,4,5] in 输出(y[1:5][1:3])\n", "[2, 3]"),
    ("切片取 len", "let y = [0,1,2,3,4] in 输出(len(y[1:3]))\n", "2"),
    ("空列表切片", "let y = [] in 输出(y[0:2])\n", "[]"),
    ("空字符串切片", 'let s = "" in 输出(s[0:2])\n', ""),
    ("整串切片", 'let s = "hello" in 输出(s[0:5])\n', "hello"),
    ("字符串负边界", 'let s = "hello" in 输出(s[-3:])\n', "llo"),
    ("切片元素可变", "let y = [1,2,3,4] in let z = y[0:2] in 输出(z[0])\n", "1"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SLICE_CASES],
                         ids=[c[0] for c in _SLICE_CASES])
def test_build_slice(src, expected):
    """切片须复刻 vm.py:504 的 `c[start:end]` 宿主 Python 语义。

    回归：钳制比较曾误用 `48 39 C8`（实为 cmp rax,rcx），使 start≤len
    判断反向，任何非空区间都被钳到 len 而得到空列表。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SLICE_CASES],
                         ids=[c[0] for c in _SLICE_CASES])
def test_build_slice_matches_vm(src, expected):
    """切片结果与 VM 逐案对齐。"""
    assert _vm(src) == expected.split("\n") or _vm(src) == [expected]


def test_slice_non_sequence_returns_none():
    """非序列容器：原生端返回 None（VM 侧对 dict/int/None 抛异常，属既有偏差）。"""
    assert _run("let z = 5 in 输出(z[1:2])\n") == (0, "None")


# ---------- 列表下标：负下标 + 越界不得读到相邻堆字节 ----------

_LIST_INDEX_CASES = [
    ("正下标首项", "#1：[[10, 20, 30][0]]\n", "10"),
    ("正下标末项", "#1：[[10, 20, 30][2]]\n", "30"),
    # 回归：此前 `[1,2,3][-1]` 走越界路径后读到相邻堆字节，静默返回 0
    ("负下标 -1", "#1：[[10, 20, 30][-1]]\n", "30"),
    ("负下标 -2", "#1：[[10, 20, 30][-2]]\n", "20"),
    # 回归：`-n` 必须等于 a[0]（边界含端点），此前误判为越界返回 None
    ("负下标 -3", "#1：[[10, 20, 30][-3]]\n", "10"),
    ("变量负下标", "let i = -2\n#1：[[10, 20, 30][i]]\n", "20"),
    ("变量负下标端点", "let i = -3\n#1：[[10, 20, 30][i]]\n", "10"),
    ("负下标表达式", "#1：[[10, 20, 30][0 - 2]]\n", "20"),
    # 回归：此前 `[1,2][9]` 直接 `mov rax,[rax+rcx*8+16]`，读到相邻堆字节返回 0
    ("None 容器下标返回 None", "let z = None\n#1：[z[0]]\n", "None"),
]


@pytest.mark.parametrize("name,src,expected", _LIST_INDEX_CASES,
                         ids=[c[0] for c in _LIST_INDEX_CASES])
def test_list_index_bounds(name, src, expected):
    assert _run(src) == (0, expected)


def test_list_index_negative_agrees_with_vm():
    """负下标在 VM 与原生须逐行一致（仅取双方都不越界的下标）。"""
    src = ("let xs = [7, 8, 9, 10]\n"
           "for i in [0, 3, -1, -4] { 输出(xs[i]) }\n")
    rc, out = _run(src)
    assert (rc, out.split("\n")) == (0, _vm(src))


def test_list_index_oob_raises_catchable():
    """列表索引越界抛可捕获异常（对齐 VM 的 IndexError），不再静默返回 None。"""
    for expr in ("[10, 20, 30][9]", "[10, 20, 30][-4]", "[][0]"):
        src = ('try {\n  #1：[%s]\n} catch (e) {\n  输出("越界")\n}\n输出("后")\n'
               % expr)
        assert _run(src) == (0, "越界\n后"), expr


def test_string_index_oob_raises_catchable():
    """字符串索引越界抛可捕获异常（对齐 VM）。"""
    src = 'try {\n  #1：["abc"[9]]\n} catch (e) {\n  输出("越界")\n}\n输出("后")\n'
    assert _run(src) == (0, "越界\n后")


def test_uncaught_index_oob_exits_one():
    """未捕获的越界索引 → 非零退出，而非静默继续。"""
    assert _run('输出("前")\n#1：[[1, 2][9]]\n') == (1, "前")


def test_non_dict_attr_raises_catchable():
    """非字典属性访问抛可捕获异常（对齐 VM 的 TypeError），不再返回 None。"""
    for expr in ("3.z", "None.z"):
        src = ('try {\n  #1：[%s]\n} catch (e) {\n  输出("属性")\n}\n输出("后")\n'
               % expr)
        assert _run(src) == (0, "属性\n后"), expr


def test_dict_attr_semantics_unchanged():
    """字典属性访问：命中取值、缺失仍返回 None（与 VM 的 obj.get 一致）。"""
    assert _run('#1：[{"a": 1}.a]\n') == (0, "1")
    assert _run('#1：[{"a": 1}.z]\n') == (0, "None")


# ---------- 幂：负指数提升为浮点，0 的负幂抛错 ----------

_POW_CASES = [
    ("正指数", "#1：[2 ** 10]\n", "1024"),
    ("零指数", "#1：[0 ** 0]\n#2：[5 ** 0]\n", "1\n1"),
    # 回归：此前整数幂的连乘循环对负指数只能给 0
    ("负指数 -1", "#1：[2 ** -1]\n", "0.5"),
    ("负指数 -2", "#1：[2 ** -2]\n", "0.25"),
    ("负底数负指数", "#1：[(-8) ** -1]\n", "-0.125"),
    ("负指数下溢", "#1：[2 ** -100]\n", "7.888609052210118e-31"),
    ("浮点底数", "#1：[2.0 ** -1]\n", "0.5"),
    ("浮点指数", "#1：[2 ** -0.5]\n", "0.7071067811865476"),
    ("负底数正指数", "#1：[(-2) ** 3]\n", "-8"),
    ("大指数", "#1：[2 ** 62]\n", "4611686018427387904"),
]


@pytest.mark.parametrize("name,src,expected", _POW_CASES,
                         ids=[c[0] for c in _POW_CASES])
def test_power(name, src, expected):
    assert _run(src) == (0, expected)


def test_zero_to_negative_power_raises():
    """0 的负幂：VM 抛 ZeroDivisionError，原生须走异常运行时而非静默 inf。"""
    assert _run('try {\n  #1：[0 ** -1]\n} catch (e) {\n  输出("幂")\n}\n输出("后")\n') \
        == (0, "幂\n后")
    rc, out = _run('输出("前")\n#1：[0 ** -1]\n')
    assert rc == 1 and out == "前"


# ---------- 砖块 13：位移 ------

_SHIFT_CASES = [
    ("左移基本", "#1：[1 << 3]\n", "8"),
    ("左移放大", "#1：[5 << 1]\n", "10"),
    ("右移基本", "#1：[16 >> 2]\n", "4"),
    ("右移截断", "#1：[7 >> 1]\n", "3"),
    ("零移位", "#1：[5 << 0]\n#2：[5 >> 0]\n", "5\n5"),
    ("移位恰为 32", "#1：[1 << 32]\n", "4294967296"),
    ("移位 61", "#1：[1 << 61]\n", "2305843009213693952"),
    ("移位 62", "#1：[2 << 61]\n", "4611686018427387904"),
    ("负数右移", "#1：[-8 >> 1]\n", "-4"),
    ("负数右移向下取整", "#1：[-1 >> 3]\n", "-1"),
    ("负数超宽右移", "#1：[-1 >> 100]\n", "-1"),
    ("非负超宽右移", "#1：[1024 >> 64]\n", "0"),
    ("超宽右移清位", "#1：[(-1 >> 100) + (8 >> 3)]\n", "0"),
    ("移位表达式", "let n = 4\n#1：[3 << n]\n#2：[64 >> n]\n", "48\n4"),
    ("移位与加法混合", "#1：[(1 << 4) + (16 >> 2)]\n", "20"),
    ("移位结果相等", "#1：[(2 << 3) == 16]\n", "True"),
    ("移位结果比较", "#1：[(1 << 10) > 1000]\n", "True"),
    ("函数内移位", "func f(x: Int) -> Int = (x) => x << 2\n#1：[f(5)]\n", "20"),
    ("连续左移", "#1：[1 << 2 << 3]\n", "32"),
    ("移位传参", "func s(x: Int) -> Int = (x) => x >> 1\n#1：[s(-9)]\n", "-5"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SHIFT_CASES],
                         ids=[c[0] for c in _SHIFT_CASES])
def test_shift_ops(src, expected):
    """位移须与 vm._BINOPS 的 Python `a << b` / `a >> b` 一致。

    两处易错点：
    1. `>>` 必须用 SAR（算术右移），SHR 会把 -8>>1 算成 +4。
    2. x86「按 cl 移位」只取计数低 6 位（0..63），Python 对 b>=64 直接给
       结果，故超范围须单独处理，不能交给硬件。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SHIFT_CASES],
                         ids=[c[0] for c in _SHIFT_CASES])
def test_shift_ops_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


# ---------- 位运算 `&` `|` `⊕` `~` 与中缀次方 `^` ----------

_BITWISE_CASES = [
    ("位与", "输出(6 & 3)\n", "2"),
    ("位或", "输出(6 | 3)\n", "7"),
    ("异或", "输出(6 ⊕ 3)\n", "5"),
    ("异或零", "输出(0 ⊕ 0)\n", "0"),
    ("位与大数", "输出(255 & 15)\n", "15"),
    ("位或复合", "输出((6 & 3) | (1 << 2))\n", "6"),
    ("取反", "输出(~5)\n", "-6"),
    ("取反零", "输出(~0)\n", "-1"),
    ("次方", "输出(2 ^ 3)\n", "8"),
    ("次方右结合", "输出(2 ^ 3 ^ 2)\n", "512"),
    ("次方优先于乘", "输出(2 ^ 3 * 2)\n", "16"),
    ("前缀开方", "输出(^9)\n", "3"),
    ("函数内位与", "func f(a: Int, b: Int) -> Int = (a, b) => a & b\n"
                "输出(f(12, 10))\n", "8"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _BITWISE_CASES],
                         ids=[c[0] for c in _BITWISE_CASES])
def test_bitwise_ops(src, expected):
    """位运算族须与 vm._BINOPS/_UNARYOPS 及解释器三方一致。

    易错点：
    1. 中缀 `^` 是**次方**（EBNF 2.1 <power>="^"，右结合、优先级高于 *），
       异或的专用符号是 `⊕`；原生与 VM 都经编译器把 AST `^` 归约为 `**`。
    2. 原生后端的整数是裸 int64，不是堆对象，故位运算必须用
       「(ptr-heap_base) < HEAP_SIZE」判据拒绝容器，不能按类型标签解引用。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _BITWISE_CASES],
                         ids=[c[0] for c in _BITWISE_CASES])
def test_bitwise_ops_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


_BITWISE_ERR_CASES = [
    ("字符串位或", '输出("a" | 1)\n'),
    ("字符串位与", '输出("a" & 1)\n'),
    ("字符串异或", '输出("a" ⊕ 1)\n'),
    ("列表位或", "输出([1,2] | 1)\n"),
    ("浮点位与", "输出(1.5 & 1)\n"),
    ("字符串取反", '输出(~"a")\n'),
    ("列表取反", "输出(~[1,2])\n"),
]


# ---------- `<<` 角度前缀 ----------

_ANGLE_CASES = [
    ("角度 90", "输出(<<90)\n", "1.5707963267948966"),
    ("角度 0", "输出(<<0)\n", "0.0"),
    ("角度 180", "输出(<<180)\n", "3.141592653589793"),
    ("角度负值", "输出(<<-90)\n", "-1.5707963267948966"),
    ("角度浮点", "输出(<<30.0)\n", "0.5235987755982988"),
    ("角度变量", "let a = 45\n输出(<<a)\n", "0.7853981633974483"),
    ("角度喂 sin", "输出(sin(<<30))\n", "0.49999999999999994"),
    ("角度喂 cos", "输出(cos(<<90))\n", "6.123233995736766e-17"),
    ("角度括号", "输出(<<(30 + 15))\n", "0.7853981633974483"),
    ("角度优先级", "输出(<<90 + 1)\n", "2.5707963267948966"),
    ("角度吃紧操作数", "let a = 30\n输出(<<a * 2)\n", "1.0471975511965976"),
    ("一元负号叠加", "输出(-<<90)\n", "-1.5707963267948966"),
    ("中缀位移不受影响", "输出(5 << 2)\n", "20"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _ANGLE_CASES],
                         ids=[c[0] for c in _ANGLE_CASES])
def test_angle_prefix(src, expected):
    """`<<n` 把度数归一化成弧度，故结果可直接喂给只吃弧度的 sin/cos。

    易错点（均为本次实际踩到的）：
    1. f_deg 的 epilogue 必须 `mov rsp,rbp; pop rbp; ret`。写成 `pop rbp; ret`
       在 box_float 返回后会让进程以 0xC0000005 崩掉——本文件其余 helper
       （f_sqrt/f_neg/f_pow）一律用前者。
    2. 判定「是否浮点对象」不能用 is_float：它把返回值放在 eax
       （mov eax,1 / xor eax,eax），rax 会被整个清掉。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _ANGLE_CASES],
                         ids=[c[0] for c in _ANGLE_CASES])
def test_angle_prefix_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


_ANGLE_ERR_CASES = [
    ("bool 角度", "输出(<<真)\n"),
    ("字符串角度", '输出(<<"90")\n'),
    ("列表角度", "输出(<<[1,2])\n"),
]


@pytest.mark.parametrize("src", [c[1] for c in _ANGLE_ERR_CASES],
                         ids=[c[0] for c in _ANGLE_ERR_CASES])
def test_angle_rejects_non_numeric(src):
    """非数值做角度必须抛错，不能静默返回 null（解释器/VM 都是 raise）。"""
    rc, _ = _run(src)
    assert rc != 0


@pytest.mark.parametrize("src", [c[1] for c in _ANGLE_ERR_CASES],
                         ids=[c[0] for c in _ANGLE_ERR_CASES])
def test_angle_rejects_non_numeric_catchable(src):
    body = src.strip()
    wrapped = 'try { %s } catch (e) { 输出("已捕获") }\n' % body
    assert _run(wrapped) == (0, "已捕获")


# ---------- `？` 公式模式：登记为模式，不求值 ----------

_SCHEMA_PROGRAMS = [
    ("匿名槽模式", "#1：？+？=？\n", ""),
    ("具名槽模式", "#2：？a + ？a = ？b\n", ""),
    ("多槽嵌套", "#3：？x * ？y = ？z\n", ""),
    ("模式与普通输出共存", "#1：？+？=？\n#1：[1 + 1]\n", "2"),
    ("多个模式", "#1：？+？=？\n#2：？*？=？\n", ""),
    # 命中模式的具体公式：编译器须**不发**求值代码，否则 VM `KeyError '单价'`、
    # AOT 同样撞未定义全局。
    ("命中匿名槽的具体公式", "#1：？+？=？\n#2：单价 + 运费 = 总价\n#1：[1 + 1]\n", "2"),
    ("命中具名槽的具体公式", "#1：？a + ？a = ？b\n#2：面积 + 面积 = 周长\n#1：[9]\n", "9"),
    ("多条公式命中同一模式", "#1：？+？=？\n#2：a + b = c\n#3：x + y = z\n#1：[5]\n", "5"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SCHEMA_PROGRAMS],
                         ids=[c[0] for c in _SCHEMA_PROGRAMS])
def test_formula_schema_is_noop_runtime(src, expected):
    """`#：？公式` 是**规格登记**，不产生输出、不触碰栈。

    槽（`？`）没有可求值的值，故不得走表达式求值路径——解释器/VM 登记进公式库，
    原生后端发空实现，可观察行为（stdout）三者一致。此前 VM 会在查变量表时
    `KeyError '？'`，AOT 直接抛 NativeNotSupported。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _SCHEMA_PROGRAMS],
                         ids=[c[0] for c in _SCHEMA_PROGRAMS])
def test_formula_schema_no_output_match_vm(src, expected):
    assert _vm(src) == ([expected] if expected else [])


@pytest.mark.parametrize("src", ["#1：？+？=？\n#2：？a + ？a = ？b\n"])
def test_formula_schema_registered_in_vm_library(src):
    """VM 侧公式库应登记全部模式，且保留 `？` 前缀以区别于具体公式。"""
    mod = compile_source(src)
    vm = VM(mod)
    vm.run()
    assert [s.display for s in vm.formulas] == ["#1：？ + ？ = ？", "#2：？a + ？a = ？b"]


def test_concrete_formula_matched_not_evaluated():
    """命中模式的具体公式在**编译期**判定：不发求值代码。

    此前 VM 把 `单价 + 运费 = 总价` 当表达式求值 → `KeyError '单价'`，
    AOT 撞未定义全局。编译器与解释器**同源同序**地建同一套公式库，故静态
    判定结果与解释器运行期判定一致，三端 stdout 一致。
    """
    c = Compiler()
    c.compile_program(parse("#1：？+？=？\n#2：单价 + 运费 = 总价\n"))
    assert len(c.formulas) == 1
    assert c.formula_matches
    assert "单价" in c.formula_matches[0]


def test_unmatched_formula_compiles_as_expression():
    """未命中（运算符不同）→ 仍走表达式求值，行为与改动前一致。"""
    c = Compiler()
    c.compile_program(parse("#1：？+？=？\n#2：单价 * 数量 = 总价\n"))
    assert c.formula_matches == []


# ---------- 运行期浮点取反 ----------

_NEG_FLOAT_CASES = [
    ("变量浮点", "let a = 1.5\n输出(-a)\n", "-1.5"),
    ("表达式结果", "输出(-(2 + 0.5))\n", "-2.5"),
    ("除法结果", "输出(-(90 / 1))\n", "-90.0"),
    ("乘法结果", "输出(-(2.0 * 2.0))\n", "-4.0"),
    ("内建返回值", "输出(-deg2rad(90))\n", "-1.5707963267948966"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _NEG_FLOAT_CASES],
                         ids=[c[0] for c in _NEG_FLOAT_CASES])
def test_neg_runtime_float(src, expected):
    """运行期浮点取反：原生端曾把 is_float 的返回值（走 eax）当成操作数，
    于是 f_neg 收到 0/1，`-1.5` 被算成 -1.0。字面量 `-1.5` 因常量折叠看不出问题。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _NEG_FLOAT_CASES],
                         ids=[c[0] for c in _NEG_FLOAT_CASES])
def test_neg_runtime_float_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


# ---------- 前缀自增自减 ----------

_INCRDECR_CASES = [
    ("自增整数字面量", "输出(++3)\n", "4"),
    ("自减整数字面量", "输出(--3)\n", "2"),
    ("自增浮点字面量", "输出(++2.5)\n", "3.5"),
    ("自减浮点字面量", "输出(--2.5)\n", "1.5"),
    ("自增整型变量", "let x = 5\n输出(++x)\n", "6"),
    ("自减整型变量", "let x = 5\n输出(--x)\n", "4"),
    ("自增运行期浮点", "let a = 2.5\n输出(++a)\n", "3.5"),
    ("自减运行期浮点", "let a = 2.5\n输出(--a)\n", "1.5"),
    ("自减表达式结果", "输出(--(2 + 0.5))\n", "1.5"),
    ("自减除法结果", "输出(--(90 / 1))\n", "89.0"),
    ("自减嵌套角度", "输出(--<<90)\n", "0.5707963267948966"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _INCRDECR_CASES],
                         ids=[c[0] for c in _INCRDECR_CASES])
def test_prefix_incr_decr(src, expected):
    """前缀 ++/-- 是**非原地**的 v±1。

    浮点路径曾把 subsd 结果留在 xmm1，而 box_float 只读 xmm0，于是运行期
    浮点自减恒为 1.0；SSE 标量指令的 ModRM.reg 是**目的**操作数，结果必须
    回到 xmm0。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _INCRDECR_CASES],
                         ids=[c[0] for c in _INCRDECR_CASES])
def test_prefix_incr_decr_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


@pytest.mark.parametrize("src", ['输出(++"a")\n', "输出(--[1,2])\n"])
def test_prefix_incr_decr_rejects_non_numeric(src):
    rc, _ = _run(src)
    assert rc != 0


@pytest.mark.parametrize("src", ['输出(--"x")\n'])
def test_prefix_incr_decr_rejects_non_numeric_catchable(src):
    body = src.strip()
    assert _run('try { %s } catch (e) { 输出("已捕获") }\n' % body) == (0, "已捕获")


# ---------- `？` 占位符等价于具名变量 ----------

_PLACEHOLDER_CASES = [
    ("绑定后读具名", "？sum = 0\n输出(sum)\n", "0"),
    ("绑定后读占位名", "？sum = 0\n输出(？sum)\n", "0"),
    ("读既有具名变量", "sum = 5\n输出(？sum)\n", "5"),
    ("两个占位名运算", "？a = 1\n？b = 2\n输出(？a + ？b)\n", "3"),
    ("占位名参与算术", "？a = 1\n输出(？a * 3)\n", "3"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _PLACEHOLDER_CASES],
                         ids=[c[0] for c in _PLACEHOLDER_CASES])
def test_placeholder_equals_named_variable(src, expected):
    """`？sum` 等价于 `sum`（docs/00 L135、docs/02 占位符条）。

    解析器此前只让**绑定**位置遵守该规则，表达式位置把 `？sum` 读成「万能占位
    符当作函数作用于 sum」，报「未定义函数 FuncApp(...)」。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _PLACEHOLDER_CASES],
                         ids=[c[0] for c in _PLACEHOLDER_CASES])
def test_placeholder_equals_named_variable_match_vm(src, expected):
    assert _vm(src) == expected.split("\n")


_BOOL_NOT_CASES = [
    ("取反真", "输出(~真)\n", "-2"),
    ("取反假", "输出(~假)\n", "-1"),
    ("取反布尔变量", "let b = 真\n输出(~b)\n", "-2"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _BOOL_NOT_CASES],
                         ids=[c[0] for c in _BOOL_NOT_CASES])
def test_bitnot_bool_value(src, expected):
    """bool 在原生端是 bool_true/bool_false 的**指针**，取反须先按指针还原成
    0/1；直接 `not rax` 会把堆地址当整数，输出 -(ptr+1)。
    """
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src", [c[1] for c in _BITWISE_ERR_CASES],
                         ids=[c[0] for c in _BITWISE_ERR_CASES])
def test_bitwise_rejects_non_integer(src):
    """非整数操作数必须抛可捕获异常，而不是按堆地址算出垃圾值。

    原生端走 raise_rt（异常运行时），VM 侧抛 RuntimeError。
    """
    rc, _ = _run(src)
    assert rc != 0


@pytest.mark.parametrize("src", [c[1] for c in _BITWISE_ERR_CASES],
                         ids=[c[0] for c in _BITWISE_ERR_CASES])
def test_bitwise_rejects_non_integer_catchable(src):
    """同一错误在 try/catch 内应被捕获，程序正常退出。"""
    body = src.strip()
    wrapped = 'try { %s } catch (e) { 输出("已捕获") }\n' % body
    assert _run(wrapped) == (0, "已捕获")


# ---------- 砖块 12：成员判断 in / ∈ ----------

_IN_CASES = [
    ("列表命中", "输出(2 in [1, 2, 3])\n", "True"),
    ("列表未命中", "输出(5 in [1, 2, 3])\n", "False"),
    ("列表首元素", "输出(1 in [1, 2, 3])\n", "True"),
    ("列表末元素", "输出(3 in [1, 2, 3])\n", "True"),
    ("空列表", "输出(1 in [])\n", "False"),
    ("列表含 0", "输出(0 in [0, 1])\n", "True"),
    ("列表含负数", "输出(-1 in [1, -1])\n", "True"),
    ("列表含字符串", '输出("b" in ["a", "b"])\n', "True"),
    ("列表字符串未命中", '输出("z" in ["a", "b"])\n', "False"),
    ("字符串子串", '输出("bc" in "abcd")\n', "True"),
    ("字符串单字符", '输出("b" in "abc")\n', "True"),
    ("字符串未命中", '输出("z" in "abc")\n', "False"),
    ("字符串空 needle", '输出("" in "abc")\n', "True"),
    ("字符串整串", '输出("abc" in "abc")\n', "True"),
    ("字符串尾部", '输出("cd" in "abcd")\n', "True"),
    ("字符串 needle 更长", '输出("abcdx" in "abcd")\n', "False"),
    ("空字符串容器", '输出("a" in "")\n', "False"),
    ("字典键命中", '输出("甲" in {"甲": 1})\n', "True"),
    ("字典键未命中", '输出("乙" in {"甲": 1})\n', "False"),
    ("多键字典", '输出("b" in {"a": 1, "b": 2})\n', "True"),
    ("字典值不算命中", '输出(1 in {"a": 1})\n', "False"),
    ("切片结果成员判断", "let z = [1, 2, 3][0:2] in 输出(2 in z)\n", "True"),
    ("切片结果未命中", "let z = [1, 2, 3][0:2] in 输出(3 in z)\n", "False"),
    ("成员判断进条件", "if 2 in [1, 2] then 输出(\"y\") else 输出(\"n\")\n", "y"),
    ("成员判断入函数", "func has(x: Int) -> Int = (x) => if x in [1, 2] then 10 else 20\n"
                       "输出(has(2))\n输出(has(9))\n", "10\n20"),
    ("in 取反", '输出(not ("a" in "abc"))\n', "False"),
    ("in 与 and 组合", '输出(("a" in "abc") and (3 in [1, 2, 3]))\n', "True"),
    ("in 结果相等", '输出(("a" in "abc") == (1 == 1))\n', "True"),
    ("in 结果为真值对象", '输出(1 in [1])\n', "True"),
    ("成员判断在 let 值括号内", "let b = (1 in [1, 2]) in 输出(b)\n", "True"),
    ("字符串成员判断在 let 值括号内", 'let b = ("b" in "abc") in 输出(b)\n', "True"),
    ("成员判断在嵌套括号内", "let b = ((2 in [1, 2])) in 输出(b)\n", "True"),
]


@pytest.mark.parametrize("src,expected", [c[1:] for c in _IN_CASES],
                         ids=[c[0] for c in _IN_CASES])
def test_in_operator(src, expected):
    """`in` 须对齐 vm._BINOPS 的宿主 Python 成员判断（list/dict/str）。"""
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [c[1:] for c in _IN_CASES],
                         ids=[c[0] for c in _IN_CASES])
def test_in_operator_matches_vm(src, expected):
    assert _vm(src) == expected.split("\n")


@pytest.mark.parametrize("src", ["输出(1 in 5)\n", '输出("a" in 3)\n'])
def test_in_non_container_is_false(src):
    """非容器类型：VM 抛 TypeError，原生取 False（不崩溃优先）。"""
    assert _run(src) == (0, "False")


# 原生整数是 int64，VM 是任意精度 Python int；左移溢出宽度属已知固有偏差。

@pytest.mark.parametrize("src,expected", [
    ("#1：[1 << 64]\n", "0"),
    ("#1：[-1 << 100]\n", "0"),
    ("#1：[1 << 65]\n", "0"),
    ("#1：[1 << 63]\n", "-9223372036854775808"),   # 2^63 回绕到 INT64_MIN
])
def test_left_shift_overflow_is_int64_semantics(src, expected):
    """左移溢出：VM 给任意精度大数，原生按 int64 语义（0 或回绕）处理。"""
    assert _run(src) == (0, expected)


def test_negative_shift_count_returns_zero():
    """负移位数 VM 抛 ValueError，原生取 0 以免运行期崩溃。"""
    assert _run("#1：[8 << -1]\n") == (0, "0")


def test_arity_over_limit_rejected():
    """超出 MAX_NATIVE_ARITY 的实参数显式报错。"""
    sig = ", ".join(f"a{i}: Int" for i in range(9))
    params = ", ".join(f"a{i}" for i in range(9))
    args = ", ".join(str(i + 1) for i in range(9))
    with pytest.raises(NativeNotSupported):
        compile_to_exe(f"func f9({sig}) -> Int = ({params}) => a0\n"
                       f"#1：[f9({args})]")


# ---------- 任意精度整数（BigInt 运行期） ----------

@pytest.mark.parametrize("src,expected", [
    ("a=2\nb=63\n输出(a**b)", "9223372036854775808"),
    ("a=2\nb=64\n输出(a**b)", "18446744073709551616"),
    ("a=2\nb=100\n输出(a**b)", str(2 ** 100)),
    ("a=3\nb=40\n输出(a**b)", str(3 ** 40)),
    ("a=10\nb=30\n输出(a**b)", str(10 ** 30)),
    ("a=2\nb=100\n输出(-(a**b))", str(-(2 ** 100))),
    ("a=2\nb=100\n输出(type_of(a**b))", "Int"),
    ("a=2\nb=100\n输出(str(a**b))", str(2 ** 100)),
    ("a=100000000000\nb=100000000000\n输出(a*b)", str(100000000000 ** 2)),
    ("x=9223372036854775807\n输出(x + 1)", str(9223372036854775807 + 1)),
    ("x=9223372036854775807\n输出(x * x)", str(9223372036854775807 ** 2)),
    # 超出 int64 的**字面量常量**：静态 BigInt 对象，不能在编译期回绕。
    ("a=12345678901234567890\nb=2\n输出(a+b)", str(12345678901234567890 + 2)),
    ("a=10000000000000000000\nb=3\n输出(a-b)", str(10000000000000000000 - 3)),
    ("a=2\nb=100\nc=2**100\n输出(a**b - c)", "0"),
    ("a=2\nb=100\n输出(a**b - a**b + 1)", "1"),
])
def test_bigint_arithmetic(src, expected):
    """超出 int64 的整数（常量或运行期溢出）以任意精度计算与打印。"""
    assert _run(src) == (0, expected)


@pytest.mark.parametrize("src,expected", [
    ("a=2\nb=100\n输出(a**b == a**b)", "True"),
    ("a=2\nb=100\n输出(a**b != a**b)", "False"),
    ("a=2\nb=100\n输出(a**b > a**b - 1)", "True"),
    ("a=2\nb=100\n输出(a**b <= a**b)", "True"),
    ("a=2\nb=100\n输出(a**b < 0)", "False"),
    ("a=2\nb=100\n输出(a**b > 1)", "True"),
    ("a=2\nb=100\n输出(1 < a**b)", "True"),
    ("a=2\nb=100\n输出(a**b == 1)", "False"),
    ("a=2\nb=100\n输出(a**b < 1)", "False"),
])
def test_bigint_comparisons(src, expected):
    """BigInt 比较/相等：须用 setCC 操作码（0F 9x），误用 Jcc（0F 8x）会 AV/错值。"""
    assert _run(src) == (0, expected)


def test_bigint_in_containers_and_gc():
    """容器内 BigInt 渲染 + for 循环反复分配触发 GC 不崩溃。"""
    rc, out = _run("a=2\nb=100\n输出([a**b, 1, -(a**b)])")
    assert rc == 0 and out == f"[{2 ** 100}, 1, {-(2 ** 100)}]"
    rc, out = _run(
        "r = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]\n"
        "a=2\nb=64\ns=0\nfor i in r {\n  s = s + a**b - a**b\n}\n输出(s)")
    assert rc == 0 and out == "0"


def test_bigint_mod_shift_rejected():
    """`// %` 位运算对 BigInt 仍走 int64 边界：显式抛 err_bigintop，不崩溃。"""
    exe = os.path.join(tempfile.gettempdir(), "test_native.exe")
    Path(exe).write_bytes(compile_to_exe("a=2\nb=100\nc=a**b\n输出(c % 10)"))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert (r.returncode & 0xFFFFFFFF) == 1
    assert "大整数" in r.stderr.decode("utf-8", "replace")


# ---------- VM / AOT 定点一致 ----------

def _vm(source: str) -> list[str]:
    return [str(v) for v in run_module(compile_source(source))]


def _aot(source: str) -> list[str]:
    exe = os.path.join(tempfile.gettempdir(), "test_native_parity.exe")
    Path(exe).write_bytes(compile_to_exe(source))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert r.returncode == 0, f"AOT 退出码 {r.returncode}"
    return r.stdout.decode("utf-8", "replace").splitlines()


_PARITY_CASES = {
    "two_args": "func sub2(a: Int, b: Int) -> Int = (a, b) => a - b\n"
                "#1：[sub2(10, 3)]\n#2：[sub2(3, 10)]",
    "three_args": "func mix3(a: Int, b: Int, c: Int) -> Int ="
                  " (a, b, c) => a*100 + b*10 + c\n"
                  "#1：[mix3(1, 2, 3)]\n#2：[mix3(3, 2, 1)]",
    "zero_arity": "func 五() -> Int = () => 5\n#1：[五()]",
    "nested": "func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
              "func mul2(a: Int, b: Int) -> Int = (a, b) => a * b\n"
              "#1：[mul2(add2(2, 3), add2(4, 5))]",
    "recursion": "func f(n: Int, acc: Int) -> Int = (n, acc) =>\n"
                 "  if n <= 0 then acc else f(n - 1, acc + n)\n"
                 "#1：[f(4, 0)]\n#2：[f(10, 0)]",
    "mixed_arity": "func dbl(x: Int) -> Int = (x) => x * 2\n"
                   "func add3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a + b + c\n"
                   "#1：[add3(dbl(2), 3, dbl(4))]",
    "in_expression": "func add2(a: Int, b: Int) -> Int = (a, b) => a + b\n"
                     "#1：[add2(3, 4) * 10 + add2(1, 1)]",
    "max_arity": "func s8(a1: Int, a2: Int, a3: Int, a4: Int,"
                 " a5: Int, a6: Int, a7: Int, a8: Int) -> Int ="
                 " (a1, a2, a3, a4, a5, a6, a7, a8) =>"
                 " a1*10000000 + a2*1000000 + a3*100000 + a4*10000"
                 " + a5*1000 + a6*100 + a7*10 + a8\n"
                 "#1：[s8(1,2,3,4,5,6,7,8)]",
    # ---- 闭包 / 柯里化 / 偏应用（let 绑定经 MAKE_CLOSURE + apply_rt）----
    "closure_curry2": "let g = (a, b) => a*100 + b in\n输出(g(3)(4))\n",
    "closure_curry3": "let g = (a, b, c) => a+b+c in\n输出(g(1)(2)(3))\n",
    "closure_ret": "let g = (x) => (y) => x + y in\n输出(g(5)(7))\n",
    "closure_zero": "let f = () => 42 in\n输出(f())\n",
    "closure_capture": "let a = 10 in\nlet b = 20 in\n"
                      "let f = (x) => a + b + x in\n输出(f(5))\n",
    "closure_arity1": "let f = (x) => x + 1 in\n输出(f(41))\n",
    "closure_rec": "let rec f = (k, acc) => if k <= 0 then acc else f(k-1, acc+k) in\n"
                  "输出(f(3, 0))\n",
    "closure_rec10": "let rec f = (k, acc) => if k <= 0 then acc else f(k-1, acc+k) in\n"
                    "输出(f(10, 0))\n",
    "closure_partial_store": "let g = (a, b, c) => a*100 + b*10 + c in\n"
                            "let h = g(1)(2) in\n输出(h(3))\n",
    "closure_deep_rec": "let rec fib = (n) => if n <= 1 then n else fib(n-1) + fib(n-2) in\n"
                       "输出(fib(10))\n",
    # ---- 外域捕获（LOAD_OUTER 多层）/ 盒（let rec 自引用）----
    "outer2": "let a = 7 in\nlet f = (x) => (y) => x + y + a in\n输出(f(2)(3))\n",
    "outer3": "let a = 1 in\nlet f = (x) => (y) => (z) => x + y + z + a in\n"
              "输出(f(2)(3)(4))\n",
    "outer_mixed": "let a = 5 in\nlet b = 6 in\nlet f = (x) => (y) => x * y + a + b in\n"
                  "输出(f(2)(3))\n",
    "box_rec_read": "let rec c = 1 in\nlet get = () => c in\n输出(get())\n",
    "closure_8arg": "let s = (a, b, c, d, e, f, g, h) => a+b+c+d+e+f+g+h in\n"
                    "输出(s(1)(2)(3)(4)(5)(6)(7)(8))\n",
    "closure_in_list": "let l = [(x) => x + 1, (x) => x * 2] in\n"
                       "输出(l[0](10))\n输出(l[1](10))\n",
    "closure_repeat_call": "let a = 4 in\nlet f = (x) => x * a in\n"
                           "输出(f(3))\n输出(f(5))\n",
    "closure_rec_acc": "let rec f = (k, acc) => if k <= 0 then acc else f(k-1, acc+k) in\n"
                       "输出(f(5)(0))\n",
    "closure_rec_order": "let rec fact = (n) => if n <= 1 then 1 else n * fact(n-1) in\n"
                         "输出(fact(6))\n",
    # ---- lambda 体内的 let 绑定链（含局部闭包捕获外层局部变量）----
    "lambda_inner_let": "func f(x: Int) -> Int = (x) => let y = 10 in x + y\n输出(f(5))\n",
    "lambda_inner_let2": "func g(x: Int) -> Int = (x) => let y = 2 in let z = 3 in x * y * z\n"
                         "输出(g(4))\n",
    "lambda_let_capture": "func h(x: Int) -> Int = (x) => let a = 1 in"
                          " let f = (y) => x + y + a in f(10)\n输出(h(5))\n",
    # ---- let 体边界：`in` 不被 lambda 体当作成员运算符吞掉 ----
    "in_after_lambda_body": "let f = (x) => let y = 10 in x + y in\n输出(f(5))\n",
    "in_after_letrec_body": "let rec f = (x) => let y = 10 in x + y in\n输出(f(5))\n",
    "in_nested_let_chained": "let g = 1 in let f = (x) => let y = 2 in x+y in"
                             " let h = 3 in 输出(f(5) + g + h)\n",
    # ---- 顶层同级多个 let rec（曾因 MAKE_BOX 越界抛 IndexError）----
    "letrec_two_siblings": "let rec a = (n) => n in\nlet rec b = (n) => n in\n"
                           "输出(a(1) + b(2))\n",
    "letrec_mutual_even_odd": "let rec even = (n) => if n == 0 then true else odd(n-1) in\n"
                              "let rec odd = (n) => if n == 0 then false else even(n-1) in\n"
                              "输出(even(4))\n输出(odd(4))\n输出(even(5))\n",
    "letrec_mutual_pair": "let rec e = (n) => if n <= 1 then n else o(n-1) in\n"
                          "let rec o = (n) => if n <= 1 then n else e(n-1) in\n"
                          "输出(e(6))\n输出(o(7))\n",
    "letrec_three_siblings": "let rec a = (n) => if n == 0 then 1 else b(n-1) in\n"
                             "let rec b = (n) => if n == 0 then 2 else a(n-1) in\n"
                             "let rec c = (n) => if n == 0 then 3 else a(n) in\n"
                             "输出(a(4))\n输出(b(4))\n输出(c(0))\n",
    # ---- 浮点 repr 精确对齐（砖块 11：CRT _ecvt + 最短往返）----
    "float_repr_basic": "#1：[3.5]\n#2：[0.1]\n#3：[100.0]\n#4：[0.0001]\n#5：[-1.5]\n",
    "float_repr_sci": "#1：[0.00001]\n#2：[10000000000000000.0]\n"
                      "#3：[1.0/100000.0]\n#4：[50000000000000000.0]\n",
    "float_repr_div": "#1：[1.0/3.0]\n#2：[2.0/3.0]\n#3：[7.0/2.0]\n#4：[7/2]\n",
    "float_repr_carry": "#1：[9999999999999998.0]\n#2：[999999999999999.5]\n"
                        "#3：[9007199254740993.0]\n",
    "float_repr_arith": "#1：[1.5+2]\n#2：[7.0//2]\n#3：[7.5%2]\n#4：[2.0**3]\n",
    # ---- 浮点分派必须两侧都判（回归：is_float2 曾只判右操作数）----
    # 修复前 `mov rax,r9`（查右值容器）后未改回 r8 就 call is_float，
    # 于是「左浮右整」被判成非浮点，1.5 + 2 走整数路径把堆指针当整数相加。
    "float_left_operand": "let b = 2 in\n输出(1.5 + b)\n输出(1.5 - b)\n"
                          "输出(1.5 * b)\n输出(1.5 / b)\n输出(1.5 // b)\n"
                          "输出(1.5 % b)\n输出(1.5 ** b)\n输出(b + 1.5)\n"
                          "输出(b * 1.5)\n输出(sin(0.5) // b)\n输出(cos(0.0) + b)\n",
    # ---- 前缀开方 sqrt（砖块 14：整数完全平方回退整数，否则浮点）----
    "sqrt_int_perfect": "let x = 9 in\n输出(^x)\n输出(^(x+7))\n",
    "sqrt_int_irrational": "let x = 2 in\n输出(^x)\n输出(^(x+3))\n",
    "sqrt_float": "let x = 2.25 in\n输出(^x)\n输出(^(x+1.75))\n",
    "sqrt_zero_and_big": "let x = 0 in\n输出(^x)\n"
                         "let y = 1000000000000 in\n输出(^y)\n"
                         "let z = 999999999999 in\n输出(^z)\n",
    "sqrt_expr_and_func": "func f(a: Int) -> Int = (a) => ^a\n"
                          "let x = 3 in\nlet y = 4 in\n"
                          "输出(^(x*x + y*y))\n输出(f(49))\n",
    # ---- 砖块 16 阶段一：数值 + 转换核心 ----
    "b16_math_unary": "输出(sin(1.0))\n输出(cos(0.0))\n输出(tan(1.0))\n"
                      "输出(asin(0.5))\n输出(atan(1.0))\n",
    "b16_math_hyper": "输出(sinh(1.0))\n输出(cosh(1.0))\n输出(tanh(1.0))\n"
                      "输出(exp(1.0))\n输出(log(2.718281828459045))\n"
                      "输出(log10(1000.0))\n输出(log2(8.0))\n",
    "b16_round": "输出(floor(2.7))\n输出(ceil(-2.7))\n输出(trunc(-2.9))\n"
                 "输出(round(2.5))\n输出(round(3.5))\n输出(round(-2.5))\n",
    "b16_abs_sign": "输出(abs(-5))\n输出(abs(-2.5))\n输出(sign(-3))\n"
                    "输出(sign(2.5))\n输出(sign(0.0))\n",
    "b16_angle": "输出(deg2rad(180.0))\n输出(rad2deg(3.141592653589793))\n",
    "b16_sqrt_call": "输出(sqrt(2.0))\n输出(sqrt(9))\n输出(^9)\n",
    "b16_pow_atan2_hypot": "输出(pow(2)(10))\n输出(pow(2.0)(0.5))\n"
                           "输出(atan2(1.0)(1.0))\n输出(hypot(3.0)(4.0))\n",
    "b16_int": "输出(int(3.7))\n输出(int(-3.7))\n输出(int(5))\n输出(int(1 < 2))\n",
    "b16_float": "输出(float(3))\n输出(float(2.5))\n输出(float(1 < 2))\n",
    "b16_str": "输出(str(123))\n输出(str(-45))\n输出(str(1.5))\n"
               '输出(str("hi"))\n输出(str(1 < 2))\n输出(str(1 > 2))\n',
    "b16_bool": "输出(bool(0))\n输出(bool(3))\n"
                '输出(bool(""))\n输出(bool("x"))\n'
                "输出(bool([]))\n输出(bool([1]))\n",
    "b16_type_of": "输出(type_of(1))\n输出(type_of(1.5))\n"
                   '输出(type_of("a"))\n输出(type_of([1, 2]))\n'
                   "输出(type_of(1 < 2))\n"
                   "let f = (x) => x in\n输出(type_of(f))\n",
    "b16_typeof": "输出(typeof 1)\n输出(typeof 2.0)\n"
                  '输出(typeof "x")\n输出(typeof [1, 2])\n'
                  "输出(typeof (1 < 2))\n",
    "b16_combos": "输出(str(sqrt(2.0)))\n输出(int(sin(0.5) * 10))\n"
                  "输出(floor(exp(0.0)) + sign(-2))\n",
    # ---- 砖块 16 阶段二：序列 / 字典原语 ----
    # 注：_dict_keys 返回文本列表；原生端嵌套文本打印不带引号（既有打印限制，
    # 非本阶段语义），故取元素后经顶层输出比较，避免混淆该差异。
    "b16s_dict_keys": 'let d = {"a": 1, "b": 2, "c": 3} in\n'
                      "输出(get(_dict_keys(d))(0))\n"
                      "输出(get(_dict_keys(d))(1))\n"
                      "输出(get(_dict_keys(d))(2))\n"
                      "输出(_dict_values(d))\n",
    "b16s_dict_keys_empty": "输出(_dict_keys(_empty_dict))\n",
    "b16s_dict_has": 'let d = {"a": 1, "b": 2} in\n'
                     '输出(_dict_has(d)("a"))\n输出(_dict_has(d)("z"))\n',
    "b16s_dict_put": 'let d = {"a": 1, "b": 2} in\n'
                     'let e = _dict_put(d)("z")(9) in\n'
                     "输出(d)\n输出(e)\n"
                     '输出(_dict_put(d)("b")(7))\n',
    "b16s_dict_put_empty": '输出(_dict_put(_empty_dict)("k")(1))\n',
    "b16s_dict_remove": 'let d = {"a": 1, "b": 2, "c": 3} in\n'
                        '输出(_dict_remove(d)("b"))\n'
                        '输出(_dict_remove(d)("a"))\n'
                        '输出(_dict_remove(d)("c"))\n'
                        '输出(_dict_remove(d)("z"))\n',
    "b16s_empty_dict": "输出(_empty_dict)\n输出(type_of(_empty_dict))\n",
    # MathaIOError：三端统一为 2 元素列表（VM 原返回 Python 元组）。
    # 结构访问（len/get/typeof）规避嵌套字符串打印差异。
    "ioerror_list": ('let e = MathaIOError("boom") in\n'
                     "输出(len(e))\n输出(get(e)(0))\n输出(get(e)(1))\n"
                     "输出(typeof(e))\n"),
    "b16s_append": "输出(append([1, 2])(3))\n输出(append([])(7))\n"
                   "输出(append([[1], [2]])([3]))\n",
    # list_push 为 VM 端原地追加；原生列表不可变，按线性构建器契约
    # （单链持有、无别名观察）返回新列表，可观测量与 VM 一致。
    "b16s_list_push": "let s0 = [] in\n"
                      "let s1 = list_push(s0)(1) in\n"
                      "let s2 = list_push(s1)(2) in\n"
                      "let s3 = list_push(s2)(3) in\n"
                      "输出(s3)\n输出(len(s3))\n"
                      '输出(list_push(["a"])("b"))\n',
    "b16s_slice": "输出(slice([1, 2, 3, 4])(1)(3))\n"
                  "输出(slice([1, 2, 3, 4])(1)(9))\n"
                  "输出(slice([1, 2, 3, 4])(-2)(4))\n"
                  '输出(slice("abcdef")(1)(4))\n',
    "b16s_mut_set_at": "let l = [1, 2, 3] in\n"
                       "输出(mut_set_at(l, 1, 99))\n输出(l)\n"
                       "let m = [1, 2, 3] in\n输出(mut_set_at(m)(0)(8))\n",
    "b16s_combo": 'let d = {"a": 1, "b": 2} in\n'
                  "输出(get(_dict_keys(_dict_put(d)(\"c\")(3)))(0))\n"
                  "输出(len(_dict_keys(d)))\n"
                  '输出(_dict_has(_dict_put(d)("a")(0))("b"))\n',
    # ---- 砖块 16 阶段三：常量 / 基础原语 / 序列构造 / 编解码 ----
    # 注：list("…") 原生端已按 Unicode 码点切分（对齐 VM），此处以 ASCII 覆盖基础路径。
    "b16t_consts": "输出(真)\n输出(假)\n输出(null)\n输出(None)\n",
    "b16t_ord_chr": '输出(ord("A"))\n输出(chr(65))\n'
                    '输出(ord("中"))\n输出(chr(20013))\n'
                    '输出(ord("😀"))\n输出(chr(128512))\n',
    "b16t_list": "输出(list([1, 2, 3]))\n输出(list([]))\n"
                 '输出(len(list("abcd")))\n输出(get(list([7, 8, 9]))(1))\n',
    "b16t_list_dict": 'let d = {"a": 1, "b": 2, "c": 3} in\n'
                      "输出(len(list(d)))\n",
    "b16t_encode_decode": '输出(encode_binary("Hi"))\n'
                          '输出(decode_binary("1001000 1101001"))\n'
                          '输出(encode_ternary("Hi"))\n'
                          '输出(decode_ternary("2200 10220"))\n'
                          '输出(encode_decimal("Hi"))\n'
                          '输出(decode_decimal("72 105"))\n',
    "b16t_encode_utf8": '输出(encode_decimal("中"))\n'
                        '输出(decode_decimal("20013"))\n'
                        '输出(encode_binary(""))\n'
                        '输出(decode_binary(""))\n',
    # ---- 砖块 17 阶段一：mathlib 数论 / 聚合 ----
    "b17_number_theory": "输出(阶乘(0))\n输出(阶乘(5))\n输出(阶乘(10))\n"
                         "输出(最大公约数(12)(18))\n输出(最大公约数(0)(0))\n"
                         "输出(最小公倍数(4)(6))\n输出(最小公倍数(0)(5))\n"
                         "输出(排列数(5)(2))\n输出(排列数(5)(6))\n"
                         "输出(组合数(5)(2))\n输出(组合数(5)(6))\n",
    "b17_prime_check": "输出(素数判定(1))\n输出(素数判定(2))\n"
                       "输出(素数判定(17))\n输出(素数判定(18))\n"
                       "输出(素数判定(97))\n输出(素数判定(1000003))\n",
    "b17_aggregate": "输出(sum([1, 2, 3, 4]))\n输出(sum([]))\n"
                     "输出(sum([1, 2.5, 3]))\n输出(sum([1.5, 2.5]))\n"
                     "输出(max([3, 1, 4, 1, 5, 9, 2, 6]))\n"
                     "输出(min([3, 1, 4, 1, 5, 9, 2, 6]))\n"
                     "输出(max([1.5, 2.5, 0.5]))\n输出(min([1, 2.5, 0]))\n"
                     "输出(max(7))\n输出(min(7))\n",
    "b17_sieve": "输出(素数筛(0))\n输出(素数筛(1))\n输出(素数筛(2))\n"
                 "输出(素数筛(30))\n输出(len(素数筛(100)))\n"
                 "输出(sum(素数筛(100)))\n",
    "b17_pascal": "输出(杨辉三角(0))\n输出(杨辉三角(2))\n"
                  "输出(杨辉三角(5))\n输出(杨辉三角(7))\n"
                  "输出(len(杨辉三角(7)))\n",
    # ---- 砖块 17 阶段二：mathlib 逻辑 / 集合 ----
    "b17_logic": "输出(逻辑非(true))\n输出(逻辑非(false))\n"
                 "输出(逻辑非(0))\n输出(逻辑非(5))\n"
                 "输出(逻辑与(true)(true))\n输出(逻辑与(true)(false))\n"
                 "输出(逻辑与(3)(4))\n输出(逻辑与(0)(4))\n"
                 "输出(逻辑或(false)(5))\n输出(逻辑或(2)(5))\n"
                 "输出(逻辑蕴含(true)(7))\n输出(逻辑蕴含(false)(7))\n"
                 "输出(逻辑蕴含(true)(false))\n"
                 "输出(逻辑异或(true)(false))\n输出(逻辑异或(true)(true))\n"
                 "输出(逻辑异或(false)(false))\n"
                 "输出(逻辑双蕴含(true)(true))\n"
                 "输出(逻辑双蕴含(true)(false))\n",
    "b17_set": "输出(集合并([3, 1, 2])([2, 3, 4]))\n"
               "输出(集合并([1, 1, 2])([2, 3]))\n输出(集合并([])([]))\n"
               "输出(集合交([1, 2, 3])([2, 3, 4]))\n输出(集合交([1, 2])([3, 4]))\n"
               "输出(集合差([1, 2, 3])([2, 3, 4]))\n输出(集合差([1, 2])([1, 2]))\n"
               "输出(集合补([1, 2, 3, 4])([2, 4]))\n"
               "输出(集合子集([1, 2])([1, 2, 3]))\n"
               "输出(集合子集([1, 4])([1, 2, 3]))\n"
               "输出(集合子集([])([1]))\n"
               "输出(集合基数([1, 1, 2, 3, 3]))\n输出(集合基数([]))\n"
               "输出(集合幂集([]))\n输出(集合幂集([1, 2]))\n"
               "输出(集合幂集([1, 2, 3]))\n输出(len(集合幂集([1, 2, 3, 4])))\n",
    # ---- 砖块 17 阶段三：mathlib 统计（随机为非确定性，另测）----
    "b17_stats": (
        "输出(平均值([]))\n输出(平均值([1, 2, 3]))\n"
        "输出(平均值([0.1, 0.2, 0.3]))\n"
        "输出(中位数([]))\n输出(中位数([3, 1, 2]))\n"
        "输出(中位数([4, 2, 1, 3]))\n输出(中位数([5, 3, 8, 1, 9, 2, 7]))\n"
        "输出(中位数([1.5, 2.5, 3.5]))\n"
        "输出(方差([]))\n输出(方差([1, 2, 3]))\n输出(方差([1, 1, 1]))\n"
        "输出(标准差([]))\n输出(标准差([1, 2, 3]))\n"
        "输出(协方差([1, 2, 3])([1, 2, 3]))\n"
        "输出(协方差([1, 2, 3])([3, 2, 1]))\n"
        "输出(协方差([1, 2])([1, 2, 3]))\n"
        "输出(相关系数([1, 2, 3])([1, 2, 3]))\n"
        "输出(相关系数([1, 2, 3])([3, 2, 1]))\n"
        "输出(相关系数([1, 1])([1, 2, 3]))\n"
        "输出(正态密度(0)(0)(1))\n输出(正态密度(1)(0)(1))\n"
        "输出(正态密度(0)(0)(0))\n"
    ),
    # ---- 补齐的 native 内建：print 别名 / 去重 / 安全索引 / 安全取属性 ----
    "new_builtins": (
        'print("hi")\n'
        '输出(去重([1, 2, 2, 3]))\n'
        '输出(去重([]))\n'
        '输出(去重([[1, 2], [1, 2], [3]]))\n'
        '输出(安全索引([10, 20], 1))\n'
        '输出(安全索引([10, 20], 9))\n'
        '输出(安全索引([10, 20, 30], -1))\n'
        '输出(安全索引("ab", 1))\n'
        '输出(安全索引("ab", 5))\n'
        '输出(安全索引(3, 0))\n'
        '输出(安全索引(null, "z"))\n'
        '输出(安全取属性({"a": 7}, "a"))\n'
        '输出(安全取属性({"a": 7}, "z"))\n'
        '输出(安全取属性(3, "z"))\n'
        '输出(安全取属性(null, "z"))\n'
    ),
    # ---- 任意精度整数（BigInt 运行期；VM 用任意精度 Python int，须一致）----
    "bigint_pow": "a=2\nb=100\n输出(a**b)\n输出(a**b - a**b)\n",
    "bigint_literal": "a=12345678901234567890\nb=2\n输出(a+b)\n输出(a*b)\n",
    "bigint_compare": "a=2\nb=100\n输出(a**b == a**b)\n输出(a**b > 1)\n"
                      "输出(1 < a**b)\n输出(a**b == 1)\n输出(a**b < 1)\n",
    "bigint_str_type": "a=2\nb=100\n输出(str(a**b))\n输出(type_of(a**b))\n",
    "bigint_neg": "a=2\nb=100\n输出(-(a**b))\n",
}


@pytest.mark.parametrize("case", sorted(_PARITY_CASES))
def test_vm_aot_parity_multi_arg(case):
    """多参调用的 VM 语义与原生 AOT 必须逐行一致。"""
    src = _PARITY_CASES[case]
    assert _aot(src) == _vm(src), f"{case} 的 VM/AOT 输出不一致"


def test_list_push_builder_matches_append():
    """list_push 在单链构建器下与 append 结果一致（原生按不可变实现）。

    原生列表为定长对象，list_push 发射为返回新列表；只要不与其它绑定
    别名共享，可观察结果与 VM 的原地追加一致。此处对原生端做定点断言，
    并确认逐层构建与等价 append 链产生相同列表。
    """
    src = (
        "let p0 = [] in\n"
        "let p1 = list_push(p0)(1) in\n"
        "let p2 = list_push(p1)(2) in\n"
        "let p3 = list_push(p2)(3) in\n"
        "输出(p3)\n"
        "let a0 = [] in\n"
        "let a1 = append(a0)(1) in\n"
        "let a2 = append(a1)(2) in\n"
        "let a3 = append(a2)(3) in\n"
        "输出(a3)\n"
    )
    out = _aot(src)
    out = _aot(src)
    assert out == ["[1, 2, 3]", "[1, 2, 3]"]
    assert out[0] == out[1]


def test_matha_io_error_is_two_element_list():
    """MathaIOError 原生返回 ["MathaIOError", msg] 列表（与 VM/解释器统一）。

    原 VM 返回 Python 元组 ("MathaIOError", str(m))；统一为列表后原生可直接
    承载。此处对原生端做定点断言（长度/标签/负载/类型名）。
    """
    out = _aot('let e = MathaIOError("boom") in\n'
               "输出(len(e))\n"
               "输出(get(e)(0))\n"
               "输出(get(e)(1))\n"
               "输出(typeof(e))\n")
    assert out == ["2", "MathaIOError", "boom", "列表"]


def test_file_io_roundtrip(tmp_path):
    """砖块 16 阶段三：文件 I/O 原生与 VM 行为一致（往返、追加、覆盖）。"""
    ps = (tmp_path / "io.txt").as_posix()
    src = (
        f'输出(_write_file("{ps}")("hello"))\n'
        f'输出(_read_file("{ps}"))\n'
        f'输出(_append_file("{ps}")(" world"))\n'
        f'输出(_read_file("{ps}"))\n'
        f'输出(_write_file("{ps}")(""))\n'
        f'输出(_read_file("{ps}"))\n'
    )
    assert _aot(src) == _vm(src)


def test_range_native_only():
    """range 在 VM 2 参调用报错，故仅对原生端做定点断言。"""
    src = ("输出(range(0, 5))\n输出(range(2, 7))\n输出(range(3, 3))\n"
           "输出(list(range(0, 4)))\n"
           "let s = 0\nfor i in range(0, 5) {\n  s = s + i\n}\n输出(s)\n")
    assert _aot(src) == [
        "[0, 1, 2, 3, 4]", "[2, 3, 4, 5, 6]", "[]",
        "[0, 1, 2, 3]", "10",
    ]


def test_random_native_only():
    """随机内建非确定性，仅对原生端做定点断言（类型/范围/多次不同）。"""
    out = _aot("输出(均匀随机(0)(1))\n输出(均匀随机(5)(10))\n"
               "输出(正态随机(0)(1))\n")
    assert len(out) == 3
    u0, u1, g = float(out[0]), float(out[1]), float(out[2])
    assert 0.0 <= u0 < 1.0
    assert 5.0 <= u1 < 10.0
    assert g == g and abs(g) < 1e9
    out2 = _aot("输出(均匀随机(0)(1))\n输出(均匀随机(0)(1))\n"
                "输出(均匀随机(0)(1))\n")
    assert len(set(out2)) > 1


def test_set_comprehension_native():
    """集合理解生成子句/过滤/去重算法在原生端与 VM 一致（同一 MMB 字节码）。

    去重按 val_eq 结构相等；原生 val_eq 已支持嵌套列表逐元素递归（见
    test_native_deep_equality）。
    """
    assert _aot("输出({ x | x >> [1, 2, 3, 4] | x > 2 })\n") == ["[3, 4]"]
    assert _aot("输出({ x * 10 | x >> [1, 2, 3] })\n") == ["[10, 20, 30]"]
    assert _aot("输出({ x | x >> [1, 1, 2, 3, 3] })\n") == ["[1, 2, 3]"]
    assert _aot("输出({ x * y | x >> [1, 2] | y >> [3, 4] | x < y })\n") == [
        "[3, 4, 6, 8]"]


def test_set_comprehension_bounded_and_mapping_native():
    """原生端支持有界整数域推断与 `, 输出` 映射写法。"""
    assert _aot("输出({ x | 1 <= x <= 5 })\n") == ["[1, 2, 3, 4, 5]"]
    assert _aot("输出({ x | 1 <= x <= 5 | x % 2 == 0 })\n") == ["[2, 4]"]
    assert _aot("输出({ n | n >> [1, 2, 3] , n + n })\n") == ["[2, 4, 6]"]


def test_native_deep_equality():
    """原生 val_eq 结构相等：列表/嵌套列表/字典/字符串逐元素递归。

    回归：此前原生 `==` 对指针只按长度逐字节比（列表=元素个数），导致
    `[1,3]==[1,4]` 误判为真、`[[1,3]]==[[1,3]]` 误判为假。
    """
    assert _aot("输出([1, 3] == [1, 4])\n") == ["False"]
    assert _aot("输出([1, 3] == [1, 3])\n") == ["True"]
    assert _aot("输出([[1, 3]] == [[1, 3]])\n") == ["True"]
    assert _aot("输出([[1, 3]] == [[1, 4]])\n") == ["False"]
    assert _aot("输出([1, 2] != [1, 3])\n") == ["True"]
    assert _aot("输出([1, 2, 3] == [1, 2, 3, 4])\n") == ["False"]
    assert _aot('输出("ab" == "ab")\n') == ["True"]
    assert _aot('输出("ab" == "ac")\n') == ["False"]
    assert _aot("输出({1: 2, 3: 4} == {1: 2, 3: 4})\n") == ["True"]
    assert _aot("输出({1: 2} == {1: 3})\n") == ["False"]
    # 跨类型数值：布尔=0/1、整数与浮点在元素级也按数值比较
    assert _aot("输出(真 == 1)\n") == ["True"]
    assert _aot("输出(假 == 0)\n") == ["True"]
    assert _aot("输出(1.0 == 1)\n") == ["True"]
    assert _aot("输出([1, 2.0] == [1, 2])\n") == ["True"]


def test_native_nested_set_dedup():
    """集合构造对嵌套列表按结构相等去重（此前只比首元素会误删）。"""
    assert _aot('输出(构造集合("enumeration", [], [[10, 3], [10, 3], [10, 4]]))\n') \
        == ["[[10, 3], [10, 4]]"]
    assert _aot('输出(构造集合("enumeration", [], [[1, 2], [1, 2, 3], [1, 2]]))\n') \
        == ["[[1, 2], [1, 2, 3]]"]


def test_native_print_alias():
    """print 是 输出 的别名（此前原生未实现，调用即访问违例崩溃）。"""
    assert _run('print("hi")\nprint(1 + 2)\n') == (0, "hi\n3")


def test_native_dedup_raises_on_non_list():
    """去重(非列表) 抛可捕获异常（对齐 VM 的 RuntimeError），可被 try 捕获。"""
    src = ('try {\n  去重(3)\n} catch (e) {\n  输出("需要列表")\n}\n输出("后")\n')
    assert _run(src) == (0, "需要列表\n后")


def test_native_safe_index_and_attr_never_raise():
    """安全索引 / 安全取属性 越界、缺键、不可下标一律返回 None，不抛错。"""
    assert _run('输出(安全索引([10, 20], 9))\n') == (0, "None")
    assert _run('输出(安全索引("ab", 9))\n') == (0, "None")
    assert _run('输出(安全索引(3, 0))\n') == (0, "None")
    assert _run('输出(安全取属性(3, "z"))\n') == (0, "None")
    assert _run('输出(安全取属性({"a": 7}, "a"))\n') == (0, "7")


def test_native_optional_chaining():
    """可选链 `?.` / `?.[]` 脱糖到 安全取属性/安全索引，原生端此前会崩溃。"""
    assert _run('let d = {"a": {"b": 5}} in\n输出(d?.a?.b)\n') == (0, "5")
    assert _run('let d = null in\n输出(d?.a)\n') == (0, "None")
    assert _run('let d = {"a": 1} in\n输出(d?.z)\n') == (0, "None")
    assert _run('let l = [10, 20] in\n输出(l?.[1])\n') == (0, "20")
    assert _run('let l = [10, 20] in\n输出(l?.[9])\n') == (0, "None")
    assert _run('let l = null in\n输出(l?.[0])\n') == (0, "None")
