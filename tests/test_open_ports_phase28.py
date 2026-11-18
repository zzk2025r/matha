# -*- coding: utf-8 -*-
"""阶段 28d 锁：四运行时开放插口（vm.matha 内建插口 / 宿主 VM / interp.matha
解释器插口 / 宿主 interp）。

四面同构协议：
  注册   重注册同名 = 覆盖（升级语义）；保留名（输出类）/非可调用值诚实拒绝
  注销   仅还原经注册的名字（无记录 → False；保留名诚实拒绝）
  回落   注销后回落内建链 / 全局查找 → 诚实「未定义变量」报错
  优先级 模块函数/用户函数胜过注册内建（host VM 拒绝覆盖模块函数；interp funcs-first）
  还原面 host 两面注销还原注册前全局/内建表值（vm.matha 面注册表是独立覆盖层）
"""

import pytest

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src.interp import Interpreter
from src import ast_nodes as ast

_COMPILER_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
                        "matha/parser.matha", "matha/interp.matha",
                        "matha/compiler_matha.matha", "matha/vm.matha"]

# 注册预置：闭包在 boot VM 上创建（编译进同一程序），调用时落注册表
_REG_PREAMBLE = """
func 注册双倍() -> Bool = 注册内建插口("双倍", (ps) => ps[0] * 2)
func 注册双倍x3() -> Bool = 注册内建插口("双倍", (ps) => ps[0] * 3)
func 注册保留输出() -> Bool = 注册内建插口("输出", (ps) => ps[0])
func 注销保留输出() -> Bool = 注销内建插口("输出")
func 解释器三倍值() -> Int =
  let env = 注册内建(空环境()) in
  let 三 = 查找环境(env, "三倍") in
  三([21])
func 注册解释器三倍() -> Bool = 注册解释器插口("三倍", (ps) => ps[0] * 3)
func 注册解释器四倍() -> Bool = 注册解释器插口("三倍", (ps) => ps[0] * 4)
func 注册解释器保留输出() -> Bool = 注册解释器插口("输出", (ps) => ps[0])
"""

_SRC = "输出(双倍(21))\n"
_SRC_FN = "func 双倍(x: Int) -> Int = x * 10\n输出(双倍(21))\n"
_SRC_ABS = "输出(abs(-5))\n"


def _compile_boot():
    comp = Compiler()
    decls = []
    for rel in _COMPILER_BOOT_FILES:
        with open(rel, encoding="utf-8") as f:
            decls.extend(py_parse(f.read()).decls)
    decls.extend(py_parse(_REG_PREAMBLE).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp.mod


def dict_to_module(d):
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


@pytest.fixture(scope="module")
def vm_boot():
    vm = VM(_compile_boot())
    vm.run()
    return vm


@pytest.fixture()
def clean_ports(vm_boot):
    vm_boot.call("注销内建插口", "双倍")
    vm_boot.call("注销解释器插口", "三倍")
    yield vm_boot
    vm_boot.call("注销内建插口", "双倍")
    vm_boot.call("注销解释器插口", "三倍")


# ============ A. vm.matha 内建插口（M3V 面）============

def test_vm_matha_register_and_run(clean_ports):
    vm = clean_ports
    assert vm.call("注册双倍") is True
    d = vm.call("编译", _SRC)
    assert vm.call("运行M3V", d) == [42]


def test_vm_matha_override_upgrade(clean_ports):
    vm = clean_ports
    vm.call("注册双倍")
    d = vm.call("编译", _SRC)
    assert vm.call("运行M3V", d) == [42]
    vm.call("注册双倍x3")
    assert vm.call("运行M3V", d) == [63]


def test_vm_matha_name_table(clean_ports):
    vm = clean_ports
    vm.call("注册双倍")
    assert "双倍" in vm.call("内建插口名表")


def test_vm_matha_unregister_fallback(clean_ports):
    vm = clean_ports
    vm.call("注册双倍")
    d = vm.call("编译", _SRC)
    assert vm.call("注销内建插口", "双倍") is True
    with pytest.raises(Exception, match="双倍"):
        vm.call("运行M3V", d)


def test_vm_matha_unregister_unregistered_false(clean_ports):
    assert clean_ports.call("注销内建插口", "双倍") is False


def test_vm_matha_reserved_refuse(clean_ports):
    vm = clean_ports
    with pytest.raises(Exception, match="保留内建"):
        vm.call("注册保留输出")
    with pytest.raises(Exception, match="保留内建"):
        vm.call("注销保留输出")


def test_vm_matha_output_exclusive_regression(clean_ports):
    vm = clean_ports
    vm.call("注册双倍")
    d = vm.call("编译", "输出(1 + 1)\n")
    assert vm.call("运行M3V", d) == [2]


# ============ B. 宿主 VM 插口 ============

def test_host_vm_register_run(vm_boot):
    d = vm_boot.call("编译", _SRC)
    host = VM(dict_to_module(d))
    host.register_builtin("双倍", lambda x: x * 2)
    host.run()
    assert host.outputs == [42]


def test_host_vm_override(vm_boot):
    d = vm_boot.call("编译", _SRC)
    host = VM(dict_to_module(d))
    host.register_builtin("双倍", lambda x: x * 2)
    host.register_builtin("双倍", lambda x: x * 3)
    host.run()
    assert host.outputs == [63]


def test_host_vm_reserved_refuse(vm_boot):
    host = VM(dict_to_module(vm_boot.call("编译", _SRC)))
    with pytest.raises(ValueError, match="保留内建"):
        host.register_builtin("输出", lambda x: x)
    with pytest.raises(ValueError, match="保留内建"):
        host.unregister_builtin("输出")


def test_host_vm_non_callable_refuse(vm_boot):
    host = VM(dict_to_module(vm_boot.call("编译", _SRC)))
    with pytest.raises(TypeError, match="可调用"):
        host.register_builtin("双倍", "not-callable")


def test_host_vm_module_func_refuse_and_native(vm_boot):
    d = vm_boot.call("编译", _SRC_FN)
    host = VM(dict_to_module(d))
    assert host.run() == [210]
    with pytest.raises(ValueError, match="模块函数"):
        host.register_builtin("双倍", lambda x: x * 2)


def test_host_vm_unregister_fallback(vm_boot):
    d = vm_boot.call("编译", _SRC)
    host = VM(dict_to_module(d))
    host.register_builtin("双倍", lambda x: x * 2)
    assert host.unregister_builtin("双倍") is True
    with pytest.raises(Exception, match="双倍"):
        host.run()


def test_host_vm_unregister_unregistered_false(vm_boot):
    host = VM(dict_to_module(vm_boot.call("编译", _SRC)))
    assert host.unregister_builtin("双倍") is False


def test_host_vm_restore_default_builtin(vm_boot):
    assert "abs" in vm_boot.globals
    d = vm_boot.call("编译", _SRC_ABS)
    upgraded = VM(dict_to_module(d))
    upgraded.register_builtin("abs", lambda x: 999)
    assert upgraded.run() == [999]
    restored = VM(dict_to_module(d))
    restored.register_builtin("abs", lambda x: 999)
    assert restored.unregister_builtin("abs") is True
    assert restored.run() == [5]


# ============ C. 宿主 interp 插口 ============

def test_host_interp_register_run():
    it = Interpreter()
    it.register_builtin("双倍", lambda x: x * 2)
    it.run(py_parse(_SRC))
    assert it.outputs == [42]


def test_host_interp_override():
    it = Interpreter()
    it.register_builtin("双倍", lambda x: x * 2)
    it.register_builtin("双倍", lambda x: x * 3)
    it.run(py_parse(_SRC))
    assert it.outputs == [63]


def test_host_interp_funcs_priority():
    it = Interpreter()
    it.register_builtin("双倍", lambda x: x * 2)
    it.run(py_parse(_SRC_FN))
    assert it.outputs == [210]


def test_host_interp_unregister_fallback():
    it = Interpreter()
    it.register_builtin("双倍", lambda x: x * 2)
    assert it.unregister_builtin("双倍") is True
    with pytest.raises(Exception, match="双倍"):
        it.run(py_parse(_SRC))


def test_host_interp_refusals():
    it = Interpreter()
    with pytest.raises(ValueError, match="保留内建"):
        it.register_builtin("输出", lambda x: x)
    with pytest.raises(TypeError, match="可调用"):
        it.register_builtin("双倍", 123)
    assert it.unregister_builtin("双倍") is False


# ============ D. interp.matha 解释器插口（自举解释器面）============

def test_interp_matha_register_eval(clean_ports):
    vm = clean_ports
    assert vm.call("注册解释器三倍") is True
    assert vm.call("解释器三倍值") == 63


def test_interp_matha_override(clean_ports):
    vm = clean_ports
    vm.call("注册解释器三倍")
    assert vm.call("解释器三倍值") == 63
    vm.call("注册解释器四倍")
    assert vm.call("解释器三倍值") == 84


def test_interp_matha_name_table(clean_ports):
    vm = clean_ports
    vm.call("注册解释器三倍")
    assert "三倍" in vm.call("解释器插口名表")


def test_interp_matha_unregister_fallback(clean_ports):
    vm = clean_ports
    vm.call("注册解释器三倍")
    assert vm.call("注销解释器插口", "三倍") is True
    with pytest.raises(Exception, match="三倍"):
        vm.call("解释器三倍值")


def test_interp_matha_reserved_refuse(clean_ports):
    with pytest.raises(Exception, match="保留内建"):
        clean_ports.call("注册解释器保留输出")


# ============ E. 跨面对拍 ============

def test_cross_face_parity(vm_boot):
    vm = vm_boot
    vm.call("注销内建插口", "双倍")
    vm.call("注册双倍")
    d = vm.call("编译", _SRC)
    matha_face = vm.call("运行M3V", d)
    host_vm = VM(dict_to_module(d))
    host_vm.register_builtin("双倍", lambda x: x * 2)
    host_outputs = host_vm.run()
    host_interp = Interpreter()
    host_interp.register_builtin("双倍", lambda x: x * 2)
    host_interp.run(py_parse(_SRC))
    vm.call("注销内建插口", "双倍")
    assert matha_face == [42]
    assert host_outputs == [42]
    assert host_interp.outputs == [42]
    assert matha_face == host_outputs == host_interp.outputs
