# -*- coding: utf-8 -*-
"""x86-64 原生发射器端到端测试：编译 → 运行 exe → 校验 stdout / 退出码。"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.mbc.native import compile_to_exe, NativeNotSupported


def _run(src: str) -> tuple[int, str]:
    """编译源码为 exe 并运行，返回 (exit_code, stdout)。"""
    exe = os.path.join(tempfile.gettempdir(), "test_native.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    return r.returncode & 0xFFFFFFFF, r.stdout.decode("utf-8", "replace").strip()


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


# ---------- 比较运算 ----------

def test_eq_true():
    rc, out = _run("#1：[3==3]")
    assert rc == 0 and out == "1"


def test_ne_true():
    rc, out = _run("#1：[3!=4]")
    assert rc == 0 and out == "1"


def test_lt_true():
    rc, out = _run("#1：[2<5]")
    assert rc == 0 and out == "1"


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


# ---------- 不支持的功能应抛异常 ----------

def test_multi_arity_unsupported():
    with pytest.raises(NativeNotSupported):
        compile_to_exe(
            "func add2(a: Int, b: Int) -> Int = (a, b) => a+b\n"
            "#1：[add2(40,2)]")
