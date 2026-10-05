"""Matha 自托管 M3V 字节码虚拟机（matha/vm.matha）与宿主 Python VM 的奇偶测试。

每个用例：用自举编译器把源码编译为 M3V 产物 dict，分别交给
  (a) 宿主 Python VM（dict_to_module → VM）
  (b) Matha 编写的 运行M3V
跑出 输出 序列并逐条比对。
"""

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MFunction, MModule
from src.mbc.vm import VM
from src import ast_nodes as ast

import pytest


def _compile_files(rels):
    comp = Compiler()
    decls = []
    for rel in rels:
        with open(rel, encoding="utf-8") as f:
            src = f.read()
        decls.extend(py_parse(src).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


def dict_to_module(d):
    """自举编译器产物 dict → 宿主 MModule（指令 list 转 tuple，结构等价）。"""
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


_COMPILER_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
                        "matha/parser.matha", "matha/interp.matha",
                        "matha/compiler_matha.matha"]


@pytest.fixture(scope="module")
def vm_boot_vm():
    """自举链 + Matha 实现的 M3V 虚拟机。"""
    comp = _compile_files(_COMPILER_BOOT_FILES + ["matha/vm.matha"])
    vm = VM(comp.mod)
    vm.run()
    return vm


def _run_both(vm, src):
    """返回 (宿主输出, MathaVM 输出)。"""
    d = vm.call("编译", src)
    host = VM(dict_to_module(d))
    host.run()
    matha = vm.call("运行M3V", d)
    return host.outputs, matha


# 每例源码要求两侧输出一致（host 为基准）。
_CASES = [
    # 常量与基础运算
    "输出(1 + 2 * 3)\n",
    "输出(2 ** 10)\n输出(10 // 3)\n输出(10 % 3)\n",
    "输出(7 / 2)\n输出(-5 + -3)\n输出(8 - 2 * 3)\n",
    # 真值/短路
    "输出(0 and 5)\n输出(3 or 7)\n输出(1 and 0)\n输出(真 and 假)\n",
    "输出(not 假)\n输出(not 0)\n输出(not 真)\n",
    # 比较
    "输出(2 < 3)\n输出(3 <= 3)\n输出(4 > 5)\n输出(5 >= 5)\n输出(4 != 4)\n输出(4 = 4)\n",
    # 递归
    "func 阶乘(n: Int) -> Int =\n  n <= 1 ? 1 : n * 阶乘(n - 1)\n输出(阶乘(6))\n",
    "let rec 循环(i: Int, acc: Int) -> Int =\n  if i > 0 then 循环(i - 1, acc * 2) else acc\n输出(循环(5, 1))\n",
    # 元组解包
    "let (a, b) = (1, 2) in 输出(a + b)\n",
    "let (a, b) = ([1], [2]) in 输出(a[0] + b[0])\n",
    # 列表
    "let l = [1, 2, 3] in\n输出(l[2])\n输出(l[1:])\n输出(len(l))\n",
    "输出(append([1, 2])(3))\n",
    "输出(get([10, 20])(0))\n",
    "输出(slice([1, 2, 3, 4])(1)(3))\n",
    "let l = [1, 2, 3] in\nlet z = mut_set_at(l)(0)(9) in\n输出(z)\n",
    "输出([\"a\", \"b\"][0])\n",
    # 字典
    "let d = {\"a\": 1, \"b\": 2} in 输出(d[\"a\"] + d[\"b\"])\n",
    "let d = {\"k\": 42} in\n输出(d[\"k\"])\n",
    "let d = {\"a\": 1, \"a\": 2} in\n输出(d[\"a\"])\n",
    "let d = {\"x\": [1, 2], \"y\": {\"z\": 3}} in\n输出(d[\"x\"][1])\n输出(d[\"y\"][\"z\"])\n",
    "输出(get({\"a\": 9})(\"a\"))\n",
    # 字符串与索引
    "let s = \"abc\" in\n输出(len(s))\n输出(s[1])\n",
    "输出(ord(\"A\"))\n输出(chr(66))\n",
    # 类型转换内建（Matha 自写实现）
    "输出(str(123))\n输出(str(真))\n输出(str(null))\n",
    "输出(str(2.0))\n输出(str(0.5))\n输出(str([1, 2, 3]))\n输出(str(-7))\n",
    "输出(int(\"42\"))\n输出(int(-7))\n输出(float(3))\n输出(bool(0))\n输出(bool(2))\n",
    # 函数/闭包
    "let 加 = (y) => (x) => x + y in\n输出(加(3)(4))\n",
    "let a = 1 in\nlet b = 2 in\nlet f = () => (() => a + b) in\n输出(f()())\n",
    "let rec 槽 = 10 in\nlet 取值 = () => 槽 in\n输出(取值())\n",
    # 集合内建 / 数学内建
    "输出(abs(-7))\n输出(sum([1, 2, 3, 4]))\n输出(max([4, 9, 2]))\n输出(min([4, 9, 2]))\n",
    # 条件链
    "func 判断(n: Int) -> String =\n  if n > 10 then \"大\"\n  else if n > 5 then \"中\"\n  else \"小\"\n输出(判断(3))\n输出(判断(8))\n输出(判断(100))\n",
    # 调用捕获：异常路径与正常路径
    "func 提错() -> Int =\n  错误(\"boom\")\n输出(调用捕获(提错)([]))\n",
    "func 无事() -> Int = 7\n输出(调用捕获(无事)([]))\n",
    "func 嵌套() -> Int =\n  错误(\"里层\")\nfunc 外() -> Int =\n  错误(\"外层\")\n输出(调用捕获(嵌套)([]))\n输出(调用捕获(外)([]))\n",
    # 移位运算
    "输出(1 << 3)\n输出(16 >> 2)\n",
    # 多重输出
    "输出(1)\n输出(2)\n输出(3)\n",
]


@pytest.mark.parametrize("src", _CASES, ids=lambda s: s[:36].replace("\n", "\\n"))
def test_parity_host_vs_matha_vm(vm_boot_vm, src):
    host, matha = _run_both(vm_boot_vm, src)
    assert matha == host