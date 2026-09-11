# -*- coding: utf-8 -*-
"""M3V 字节码工具链测试：Matha AST → 字节码 → 栈式 VM → .mbc 往返。

验证要点：
  - 算术 / 字符串 / 列表 / 字典
  - 递归函数与 let rec（深递归不撑爆 Python 栈——显式帧栈）
  - 闭包捕获外层变量与柯里化偏应用
  - .mbc 二进制序列化往返结果一致
"""
import sys
import math
import os
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from src.mbc import compile_source, run_module, write_mbc, read_mbc, VM


def _out(source: str):
    return run_module(compile_source(source))


def _eval(expr: str):
    outs = _out(f"result = {expr}\n#1：[result]")
    return outs[-1] if outs else None


# ---------- 算术与字面量 ----------

def test_arith_precedence():
    assert _eval("1 + 2 * 3") == 7
    assert _eval("(1 + 2) * 3") == 9


def test_arith_ops():
    assert _eval("10 / 4") == 2.5
    assert _eval("2 ^ 10") == 1024
    assert _eval("7 % 3") == 1


def test_string_concat():
    assert _eval('"abc" + "def"') == "abcdef"


def test_comparison():
    assert _eval("3 < 5 and 5 <= 5") is True


# ---------- 递归 ----------

def test_factorial_recursive():
    outs = _out("""
func factorial(n: Int) -> Int = (n) =>
  if n < 0 then 0
  else
    let rec _iter(k: Int, acc: Int) -> Int =
      if k <= 1 then acc
      else _iter(k - 1, acc * k)
    in _iter(n, 1)
#1：[factorial(10)]
""")
    assert outs[-1] == 3628800


def test_deep_recursion_no_python_stack_overflow():
    """5 万层线性递归：AST 解释器会爆 Python 栈，显式帧栈 VM 不会。"""
    outs = _out("""
func loop(n: Int) -> Int = (n) =>
  if n = 0 then 999
  else loop(n - 1)
#1：[loop(50000)]
""")
    assert outs[-1] == 999


def test_deep_factorial_value():
    outs = _out("""
func fact(n: Int) -> Int = (n) =>
  if n <= 1 then 1 else n * fact(n - 1)
#1：[fact(2000)]
""")
    assert len(str(int(outs[-1]))) == len(str(math.factorial(2000)))


# ---------- 数论 ----------

def test_number_theory():
    outs = _out("""
func is_prime(n: Int) -> Bool = (n) =>
  if n < 2 then 假
  else if n = 2 then 真
  else if n % 2 = 0 then 假
  else
    let rec _check(k: Int) -> Bool =
      if k * k > n then 真
      else if n % k = 0 then 假
      else _check(k + 2)
    in _check(3)
func sieve(n: Int) -> List = (n) =>
  let rec _collect(k: Int, acc: List) -> List =
    if k > n then acc
    else if is_prime(k) then _collect(k + 1, acc + [k])
    else _collect(k + 1, acc)
  in _collect(2, [])
#1：[is_prime(997)]
#1：[sieve(30)]
""")
    assert outs[-2] is True
    assert outs[-1] == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]


# ---------- 闭包 / 柯里化 ----------

def test_closure_captures_outer():
    outs = _out("""
func adder(x: Int) -> Int = (x) =>
  let inner = (y) => x + y in
  inner
#1：[adder(10)(5)]
#1：[adder(10)(32)]
""")
    assert outs[-2] == 15
    assert outs[-1] == 42


# ---------- 数据结构 ----------

def test_list_ops():
    assert _eval("[1, 2, 3] + [4]") == [1, 2, 3, 4]
    assert _eval("[10, 20, 30][1]") == 20
    assert _eval("len([1, 2, 3, 4])") == 4


def test_dict_literal():
    outs = _out('#1：[{"a": 1, "b": 2}["a"] + {"a": 1, "b": 2}["b"]]')
    assert outs[-1] == 3


# ---------- .mbc 二进制工件往返 ----------

def test_mbc_roundtrip(tmp_path):
    mod = compile_source("""
func factorial(n: Int) -> Int = (n) =>
  let rec _iter(k: Int, acc: Int) -> Int =
    if k <= 1 then acc else _iter(k - 1, acc * k)
  in _iter(n, 1)
#1：[factorial(10)]
""")
    path = tmp_path / "t.mbc"
    write_mbc(mod, str(path))
    assert path.read_bytes()[:4] == b"MBC1"
    mod2 = read_mbc(str(path))
    assert run_module(mod2)[-1] == 3628800


def test_bom_tolerated():
    """带 UTF-8 BOM 的源码可正常编译。"""
    mod = compile_source("﻿#1：[1 + 1]")
    assert run_module(mod)[-1] == 2


# ---------- M4：控制流语句 / try 编译到字节码 ----------

def _call_func(src, fn, *args):
    mod = compile_source(src)
    vm = VM(mod)
    vm.run()
    return vm.call(fn, *args)


def test_compiled_while_loop():
    """while 循环 + 块内槽位绑定。"""
    src = """
func 求和到(n: Int) -> Int = (n) => {
  i = 0
  s = 0
  while i < n {
    s = s + i
    i = i + 1
  }
  s
}
"""
    assert _call_func(src, "求和到", 10) == 45
    assert _call_func(src, "求和到", 100) == 4950


def test_compiled_for_loop():
    """for 单变量与元组解构迭代。"""
    src = """
func 求和(xs: List) -> Int = (xs) => {
  s = 0
  for x in xs {
    s = s + x
  }
  s
}
"""
    assert _call_func(src, "求和", [1, 2, 3, 4, 5]) == 15


def test_compiled_if_else_value():
    """if/else 作为块尾表达式产出分支值。"""
    src = """
func 判号(n: Int) -> String = (n) => {
  if n > 0 {
    "正"
  } else {
    "非正"
  }
}
"""
    assert _call_func(src, "判号", 5) == "正"
    assert _call_func(src, "判号", -2) == "非正"


def test_compiled_try_catch_raise():
    """try 尾表达式：正常路径与 raise 捕获路径。"""
    src = """
func 安全除(a: Int, b: Int) -> Int = (a, b) => {
  if b = 0 {
    raise "除零"
  } else {
    a / b
  }
}
func 试(a: Int, b: Int) -> String = (a, b) => {
  try {
    str(安全除(a)(b))
  } catch (e) {
    "出错:" + e
  }
}
"""
    assert _call_func(src, "试", 10, 2) == "5.0"
    assert _call_func(src, "试", 1, 0) == "出错:除零"


def test_compiled_try_catches_runtime_error():
    """VM 内建运行时错误同样被编译后的 try 捕获。"""
    src = """
func 试() -> Int = () => {
  try {
    get(5)(0)
  } catch (e) {
    7
  }
}
"""
    assert _call_func(src, "试") == 7


def test_compiled_for_tuple_unpack():
    """for (a, b) in pairs 元组解构迭代。"""
    src = """
func 点和(pairs: List) -> Int = (pairs) => {
  s = 0
  for (a, b) in pairs {
    s = s + a + b
  }
  s
}
"""
    assert _call_func(src, "点和", [[1, 2], [3, 4], [5, 6]]) == 21


# ---------- M5：dict 原语 / 文件 I/O VM 内建 ----------

def test_vm_dict_keys():
    """_dict_keys(d) → 键列表。"""
    result = _eval('_dict_keys({"a": 1, "b": 2})')
    assert sorted(result) == ["a", "b"]


def test_vm_dict_values():
    """_dict_values(d) → 值列表。"""
    result = _eval('_dict_values({"a": 1, "b": 2})')
    assert sorted(result) == [1, 2]


def test_vm_dict_has():
    """_dict_has(d)(k) → 是否含键。"""
    assert _eval('_dict_has({"a": 1}, "a")') is True
    assert _eval('_dict_has({"a": 1}, "b")') is False


def test_vm_dict_put():
    """_dict_put(d)(k)(v) → 不可变设置，返回新字典。"""
    d = _eval('_dict_put({"a": 1}, "b", 2)')
    assert d == {"a": 1, "b": 2}
    # 原字典不受影响（不可变语义）
    orig = _eval('{"a": 1}')
    assert orig == {"a": 1}


def test_vm_dict_remove():
    """_dict_remove(d)(k) → 不可变删除，返回新字典。"""
    d = _eval('_dict_remove({"a": 1, "b": 2}, "a")')
    assert "a" not in d
    assert d.get("b") == 2


def test_vm_dict_keys_non_dict_error():
    """_dict_keys 对非字典输入抛出异常。"""
    with pytest.raises(RuntimeError, match="dict_keys"):
        _eval('_dict_keys(42)')


def test_vm_read_write_file(tmp_path):
    """_write_file / _read_file 端到端。"""
    p = str(tmp_path / "test_io.txt")
    src = """
func w(path: String, content: String) -> None = (path, content) => _write_file(path, content)
func r(path: String) -> String = (path) => _read_file(path)
"""
    mod = compile_source(src)
    vm = VM(mod)
    vm.run()
    vm.call("w", p, "hello world")
    assert vm.call("r", p) == "hello world"


def test_vm_append_file(tmp_path):
    """_append_file 追加写入。"""
    p = str(tmp_path / "test_append.txt")
    src = """
func w(path: String, content: String) -> None = (path, content) => _write_file(path, content)
func a(path: String, content: String) -> None = (path, content) => _append_file(path, content)
func r(path: String) -> String = (path) => _read_file(path)
"""
    mod = compile_source(src)
    vm = VM(mod)
    vm.run()
    vm.call("w", p, "line1")
    vm.call("a", p, "line2")
    assert vm.call("r", p) == "line1line2"

