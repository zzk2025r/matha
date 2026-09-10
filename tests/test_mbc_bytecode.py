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

from src.mbc import compile_source, run_module, write_mbc, read_mbc


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
    mod = compile_source("\ufeff#1：[1 + 1]")
    assert run_module(mod)[-1] == 2
