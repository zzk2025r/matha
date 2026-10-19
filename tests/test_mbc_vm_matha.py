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


def _read_source(rel):
    with open(rel, encoding="utf-8") as f:
        return f.read()


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
    # dict 重复键去重：后值覆盖、键保首现位置、len=去重后数量（原生侧
    # 曾不去重致 dict_find 首匹配读旧值；matha VM 建字典对本就覆盖式合并）。
    "let e = {\"a\": 1, \"b\": 2, \"a\": 3} in\n输出(len(e))\n输出(e[\"a\"])\n输出(e[\"b\"])\n",
    "let f = {\"k\": 1, \"k\": 2, \"k\": 3} in\n输出(f[\"k\"])\n输出(len(f))\n",
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
    # 聚合前缀 ∑/∏（Phase ②）：委托宿主 _list_sum/_list_prod
    "输出(∑[1, 2, 3, 4])\n输出(∏[1, 2, 3, 4])\n输出(∑[])\n输出(∏[])\n",
    "输出(∑[1, 2.5, 3])\n输出(∏[1.5, 2])\n输出(∑[√9, √16])\n",
    "let s = [2, 3, 4] in\n输出(∑s)\n输出(∏s)\n",
    # 条件链
    "func 判断(n: Int) -> String =\n  if n > 10 then \"大\"\n  else if n > 5 then \"中\"\n  else \"小\"\n输出(判断(3))\n输出(判断(8))\n输出(判断(100))\n",
    # 调用捕获：异常路径与正常路径
    "func 提错() -> Int =\n  错误(\"boom\")\n输出(调用捕获(提错)([]))\n",
    "func 无事() -> Int = 7\n输出(调用捕获(无事)([]))\n",
    "func 嵌套() -> Int =\n  错误(\"里层\")\nfunc 外() -> Int =\n  错误(\"外层\")\n输出(调用捕获(嵌套)([]))\n输出(调用捕获(外)([]))\n",
    # 调用捕获：非空实参表（实参表 L 铺开为局部）。matha 侧曾多包一层
    # （[参数[0]]）：单参收到 x=[3] → [3]*2 列表重复；双参帧缺槽 IndexError。
    "func 单(x: Int) -> Int = x * 2\n输出(调用捕获(单)([3]))\n输出(调用捕获(单)([4]))\n",
    "func 双(a: Int, b: Int) -> Int = a + b\n输出(调用捕获(双)([1, 2]))\n",
    "func 也错(x: Int) -> Int = 错误(\"x爆\")\n输出(调用捕获(也错)([7]))\n",
    # 移位运算
    "输出(1 << 3)\n输出(16 >> 2)\n",
    # 多重输出
    "输出(1)\n输出(2)\n输出(3)\n",
    # === 内建覆盖：数学（反三角/双曲/数论/统计/组合） ===
    "输出(asin(1))\n输出(acos(1))\n输出(atan(1))\n",
    "输出(sinh(0))\n输出(cosh(0))\n输出(tanh(0))\n",
    "输出(素数判定(7))\n输出(素数判定(8))\n输出(素数筛(30))\n",
    "输出(杨辉三角(5))\n输出(中位数([3, 1, 2]))\n",
    "输出(方差([1, 2, 3]))\n输出(标准差([1, 2, 3]))\n",
    "输出(协方差([1, 2, 3])([2, 4, 6]))\n输出(相关系数([1, 2, 3])([2, 4, 6]))\n",
    "输出(排列数(5)(2))\n输出(组合数(5)(2))\n",
    "输出(最大公约数(12)(18))\n输出(最小公倍数(4)(6))\n",
    "输出(tau)\n输出(phi)\n",
    # === 集合运算符（自举 parser 解析集合层 + vm.matha 应用运算 委托 _set_*） ===
    "let s = [1, 2, 3] ∪ [3, 4] in\n输出(s)\n",
    "let s = [1, 2, 3] ∩ [2, 3, 4] in\n输出(s)\n",
    "let s = [1, 2, 3] ⊖ [2] in\n输出(s)\n",
    "let s = [1, 2] × [3, 4] in\n输出(s)\n",
    "let s = [1, 2] ⊆ [1, 2, 3] in\n输出(s)\n",
    "let s = [2, 3] ～ [1, 2, 3] in\n输出(s)\n",
    "let s = [1, 2] ＼ [2] ⊖ [1] in\n输出(s)\n",
    # === 内建覆盖：集合 ===
    "输出(集合并([1, 2])([2, 3]))\n输出(集合交([1, 2, 3])([2, 3, 4]))\n",
    "输出(集合差([1, 2, 3])([2]))\n输出(集合补([1, 2, 3])([1, 2]))\n输出(集合子集([1])([1, 2]))\n",
    "输出(集合幂集([1, 2]))\n输出(去重([1, 1, 2, 3, 3]))\n",
    "输出(构造集合(\"enumeration\")([1, 1, 2])([3]))\n",
    # === 内建覆盖：逻辑 ===
    "输出(逻辑蕴含(真)(假))\n输出(逻辑异或(真)(假))\n输出(逻辑双蕴含(真)(真))\n",
    # === 内建覆盖：正则 ===
    "输出(匹配(\"\\\\d+\")(\"abc123\"))\n输出(全匹配(\"\\\\d+\")(\"123\"))\n",
    "输出(查找正则(\"\\\\d+\")(\"a1b22\"))\n输出(查找全部(\"\\\\d+\")(\"a1b22\"))\n",
    "输出(分割正则(\",\")(\"a,b,c\"))\n输出(替换正则(\"a\")(\"b\")(\"aaa\"))\n",
    # === 内建覆盖：日期时间（确定性） ===
    "输出(闰年判断(2024))\n输出(闰年判断(2000))\n",
    "输出(月份天数(2020)(2))\n输出(月份天数(2021)(2))\n",
    "输出(星期几(\"2024-01-01\"))\n输出(时区偏移(8))\n",
    "输出(格式化时间(0)(\"%Y\"))\n",
    # === 内建覆盖：列表/安全访问/统计分布 ===
    "let l = list_push([1, 2])(3) in\n输出(len(l))\n输出(get(l)(2))\n",
    "输出(安全索引([1, 2, 3])(1))\n输出(安全索引([1, 2, 3])(9))\n",
    "输出(正态密度(0)(1)(0))\n",
    # === Phase ②：符号常量 / 前缀 √∛ / 中缀 ÷ / 单位后缀（自举链一致） ===
    "输出(π)\n输出(τ)\n输出(φ)\n",
    "输出(∞)\n",
    "输出(∅)\n",
    "输出(√9)\n输出(√16)\n输出(√2)\n",
    "输出(∛27)\n输出(∛8)\n输出(∛64)\n输出(∛2)\n",
    "输出(∛-8)\n",
    "输出(6 ÷ 2)\n输出(2 ÷ 4)\n输出(12 ÷ 2 ÷ 3)\n",
    "输出(90°)\n输出(30℃)\n输出(98℉)\n输出(100米)\n",
    "输出(90° + 10)\n",
]


@pytest.mark.parametrize("src", _CASES, ids=lambda s: s[:36].replace("\n", "\\n"))
def test_parity_host_vs_matha_vm(vm_boot_vm, src):
    host, matha = _run_both(vm_boot_vm, src)
    assert matha == host


def module_to_dict(mod):
    """宿主 MModule → 自举编译器同构 dict（喂给 运行M3V）。"""
    d = {"模块名": mod.module_name, "常量": list(mod.constants),
         "主码": [list(x) for x in mod.main_code], "函数": []}
    for name, fn in mod.functions.items():
        info = {"元数": fn.arity, "局部数": fn.nlocals,
                "码": [list(x) for x in fn.code], "参数": list(fn.params)}
        d["函数"].append([name, info])
    return d


# 用【宿主编译器】编译的用例：可覆盖自举编译器暂不支持的位运算符/角度前缀，
# 以及宿主 mathlib 常量。两 VM 仍需输出一致。
_OP_CASES = [
    "输出(6 & 3)\n输出(6 | 3)\n输出(6 ⊕ 3)\n",
    "输出(-6 & 3)\n输出(-6 | 3)\n输出(5 ⊕ 6)\n",
    "输出(~5)\n输出(~-1)\n",
    "let x = 5 in\n输出(++x)\n输出(--x)\n输出(x)\n",
    "输出(1 << 3)\n输出(16 >> 2)\n",
    "输出(<<90)\n输出(<<0)\n输出(<<180)\n",
    # 集合运算符（宿主编译 → 两 VM 执行；覆盖 vm.matha 应用运算 的 _set_* 分派）
    "let s = [1, 2] ∪ [5] in\n输出(s)\n",
    "let s = [1] ¬ [1, 2, 3] in\n输出(s)\n",
    "let s = [1, 2, 3] ＼ [2] in\n输出(s)\n",
    "输出(G)\n输出(c)\n输出(h_planck)\n输出(N_A)\n输出(R)\n",
]


@pytest.mark.parametrize("src", _OP_CASES, ids=lambda s: s[:36].replace("\n", "\\n"))
def test_operator_parity_host_compiled(vm_boot_vm, src):
    comp = Compiler()
    comp.compile_program(py_parse(src))
    host = VM(comp.mod)
    host.run()
    matha = vm_boot_vm.call("运行M3V", module_to_dict(comp.mod))
    assert matha == host.outputs


def test_bootstrap_compiles_vm_matha_identically(vm_boot_vm):
    """自举编译器（compiler_matha.matha）可编译 matha/vm.matha 自身，
    且产物与宿主编译逐位一致（函数/主码/常量池），锁定自解析闭环。"""
    with open("matha/vm.matha", encoding="utf-8") as f:
        src = f.read()

    self_dict = vm_boot_vm.call("编译", src)
    assert isinstance(self_dict, dict)

    host_dict = module_to_dict(_compile_files(["matha/vm.matha"]).mod)

    assert self_dict["模块名"] == host_dict["模块名"]
    assert self_dict["主码"] == host_dict["主码"]
    assert self_dict["常量"] == host_dict["常量"]
    assert {e[0] for e in self_dict["函数"]} == {e[0] for e in host_dict["函数"]}
    hmap = {e[0]: e[1] for e in host_dict["函数"]}
    smap = {e[0]: e[1] for e in self_dict["函数"]}
    assert smap == hmap


@pytest.mark.slow
def test_bootstrap_self_hosting_fixpoint(vm_boot_vm):
    """完全自举不动点（stage-2）：用自举编译器编译【整条引导链】
    （lexer/stdlib/parser/interp/compiler_matha 五文件拼接），得到由自举产物
    构建的 stage-2 编译器；再用它编译 vm.matha，产物必须与 stage-1（宿主编译
    的编译器）及宿主编译 gold 逐位一致。证明编译器自编译后行为不变。

    代价约 4 分钟（自举编译器解释执行 143KB 引导源码），故标 slow。
    """
    with open("matha/vm.matha", encoding="utf-8") as f:
        vm_src = f.read()
    stage1 = vm_boot_vm.call("编译", vm_src)

    joined = "\n".join(_read_source(p) for p in _COMPILER_BOOT_FILES)
    stage2_mod = vm_boot_vm.call("编译", joined)
    assert isinstance(stage2_mod, dict)

    vm2 = VM(dict_to_module(stage2_mod))
    vm2.run()
    stage2 = vm2.call("编译", vm_src)

    gold = module_to_dict(_compile_files(["matha/vm.matha"]).mod)
    assert stage2 == stage1 == gold
