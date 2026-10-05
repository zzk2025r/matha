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
from src.mbc.native import compile_to_exe, NativeNotSupported, MAX_NATIVE_ARITY


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


@pytest.mark.parametrize("name", [
    "MathaIOError",
])
def test_unimplemented_builtin_rejected_at_compile_time(name):
    """调用未实现的 VM 内建必须在编译期报错，而非运行期无提示崩溃。

    回归：LOAD_GLOBAL 对未注册名字载入 0 值，调用时经 apply_rt → ar_plain
    跳到 rax=0，表现为无堆栈的访问违例（0xC0000005），极难定位。
    """
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
    ("越界返回 None", "#1：[[10, 20, 30][9]]\n", "None"),
    ("负下标越界返回 None", "#1：[[10, 20, 30][-4]]\n", "None"),
    ("空列表下标返回 None", "#1：[[][0]]\n", "None"),
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
    "b16s_append": "输出(append([1, 2])(3))\n输出(append([])(7))\n"
                   "输出(append([[1], [2]])([3]))\n",
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
}


@pytest.mark.parametrize("case", sorted(_PARITY_CASES))
def test_vm_aot_parity_multi_arg(case):
    """多参调用的 VM 语义与原生 AOT 必须逐行一致。"""
    src = _PARITY_CASES[case]
    assert _aot(src) == _vm(src), f"{case} 的 VM/AOT 输出不一致"


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
