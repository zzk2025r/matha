# -*- coding: utf-8 -*-
"""阶段 28e 锁：统一五动作端口协议（注册/启停/升级/回滚/依赖协商）。

三面同判：
  A. 纯 Matha 协议 matha/library/os/端口协议.matha（宿主 interp 面 + VM 面）
     与宿主适配层 src/extension_port.py::LayerPort 对同一五动作序列逐值
     对拍（返回三元组、条目结构、审计行、诚实拒绝文案）。
  B. 六层后端实效：parser（自定义算子被源码真消费）/ interp_host /
     vm / compiler（PassManager 启停实况）/ kernel（features 真翻转）/
     interp_boot（自举解释器插口 63→84→63 升级回滚回环）。
  C. 诚实拒绝矩阵：保留名 / 非可调用 / 模块函数冲突 / 未知内核特性 /
     非法结合性 / 未知层——全部 (假, 状态原样, 原因)，不吞状态。
"""

import pytest

from src import custom_ops as ops
from src import features
from src.parser import parse as py_parse
from src.interp import Interpreter
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src.compiler.pass_manager import PassManager, Pass
from src.extension_port import make_port, LAYER_NAMES
from src.kernel import exec_api

# ============ 公共：五动作基准序列（三面同一序列） ============

# 序列：注册甲op v1 → 重注册（已注册）→ 依赖缺失注册（鬼依赖）→ 停用甲op →
# 停用依赖注册（丙op 依赖甲op）→ 启用甲op → 重复启用（无变化）→ 升级 v3 →
# 回滚 → 回滚未注册（丙op）→ 回滚无历史 → 依赖协商 ×2 → 启停未注册。
# 输出序 = 三元组结果/原因、条目版本/历史长度、名表/审计长、审计行、终态。

_EXPECTED = [
    True, "注册完成",                        # 1-2   注册甲op v1
    False, "已注册",                         # 3-4   重注册
    False, "依赖未满足 缺失[鬼依赖]",         # 5-6   依赖缺失注册
    True,                                    # 7     停用甲op
    False, "依赖未满足 停用[甲op]",           # 8-9   停用依赖注册
    True, "启停完成",                        # 10-11 启用甲op
    True, "无变化",                          # 12-13 重复启用
    True, "升级完成", 3, 1,                  # 14-17 升级 v3（历史 1 条）
    True, "回滚完成", 1, 0,                  # 18-21 回滚 v1（历史清空）
    "未注册",                                # 22    回滚未注册
    "无历史",                                # 23    回滚无历史
    True, "依赖满足",                        # 24-25 协商已注册依赖
    False, "依赖未满足 缺失[鬼依赖]",         # 26-27 协商缺失依赖
    "未注册",                                # 28    启停未注册
    1, 5,                                    # 29-30 名表长 / 审计长
    "注册 词法语法/甲op v1",                  # 31
    "停用 词法语法/甲op",                     # 32
    "启用 词法语法/甲op",                     # 33
    "升级 词法语法/甲op v1->v3",              # 34
    "回滚 词法语法/甲op->v1",                 # 35
    True, 0,                                 # 36-37 终态：启用真 / 依赖空
]

_MATHA_DRIVER = """use 标准库 { len }
use 端口协议
let p = 新端口("词法语法")
let r1 = 端口注册(p, "甲op", 1, "implA", [])
p = r1[1]
输出(r1[0])
输出(r1[2])
输出(端口注册(p, "甲op", 2, "implB", [])[0])
输出(端口注册(p, "甲op", 2, "implB", [])[2])
输出(端口注册(p, "乙op", 1, "implC", ["鬼依赖"])[0])
输出(端口注册(p, "乙op", 1, "implC", ["鬼依赖"])[2])
let s1 = 端口启停(p, "甲op", 假)
p = s1[1]
输出(s1[0])
输出(端口注册(p, "丙op", 1, "implD", ["甲op"])[0])
输出(端口注册(p, "丙op", 1, "implD", ["甲op"])[2])
let s2 = 端口启停(p, "甲op", 真)
p = s2[1]
输出(s2[0])
输出(s2[2])
let s3 = 端口启停(p, "甲op", 真)
输出(s3[0])
输出(s3[2])
let u1 = 端口升级(p, "甲op", 3, "implE")
p = u1[1]
输出(u1[0])
输出(u1[2])
输出(端口条目(p, "甲op")[1])
输出(len(端口条目(p, "甲op")[4]))
let b1 = 端口回滚(p, "甲op")
p = b1[1]
输出(b1[0])
输出(b1[2])
输出(端口条目(p, "甲op")[1])
输出(len(端口条目(p, "甲op")[4]))
输出(端口回滚(p, "丙op")[2])
输出(端口回滚(p, "甲op")[2])
输出(端口依赖协商(p, "丁op", ["甲op"])[0])
输出(端口依赖协商(p, "丁op", ["甲op"])[2])
输出(端口依赖协商(p, "丁op", ["鬼依赖"])[0])
输出(端口依赖协商(p, "丁op", ["鬼依赖"])[2])
输出(端口启停(p, "鬼op", 假)[2])
输出(len(端口名表(p)))
输出(len(端口审计(p)))
输出(端口审计(p)[0])
输出(端口审计(p)[1])
输出(端口审计(p)[2])
输出(端口审计(p)[3])
输出(端口审计(p)[4])
输出(端口条目(p, "甲op")[2])
输出(len(端口条目(p, "甲op")[5]))
"""


def _host_port_mirror():
    """宿主 LayerPort 走同一五动作序列，产出与 _EXPECTED 同序的值表。"""
    p = make_port("parser")
    vals = []
    r = p.register("甲op", 1, (1, "left", None))
    vals += [r[0], r[2]]
    r = p.register("甲op", 2, (2, "left", None))
    vals += [r[0], r[2]]
    r = p.register("乙op", 1, (1, "left", None), deps=["鬼依赖"])
    vals += [r[0], r[2]]
    r = p.toggle("甲op", False)
    vals.append(r[0])
    r = p.register("丙op", 1, (1, "left", None), deps=["甲op"])
    vals += [r[0], r[2]]
    r = p.toggle("甲op", True)
    vals += [r[0], r[2]]
    r = p.toggle("甲op", True)
    vals += [r[0], r[2]]
    r = p.upgrade("甲op", 3, (3, "right", None))
    vals += [r[0], r[2], p.entry("甲op")[1], len(p.entry("甲op")[4])]
    r = p.rollback("甲op")
    vals += [r[0], r[2], p.entry("甲op")[1], len(p.entry("甲op")[4])]
    vals.append(p.rollback("丙op")[2])
    vals.append(p.rollback("甲op")[2])
    r = p.negotiate("丁op", ["甲op"])
    vals += [r[0], r[2]]
    r = p.negotiate("丁op", ["鬼依赖"])
    vals += [r[0], r[2]]
    vals.append(p.toggle("鬼op", False)[2])
    vals.append(len(p.names()))
    vals.append(len(p.audit()))
    vals += p.audit()
    vals += [p.entry("甲op")[2], len(p.entry("甲op")[5])]
    return vals


# ============ A. 三面同判 ============

def test_matha_face_five_actions():
    ip = Interpreter()
    ip.run(py_parse(_MATHA_DRIVER))
    assert ip.outputs == _EXPECTED


def test_vm_face_five_actions():
    outs, err = exec_api.run_checked(_MATHA_DRIVER, mode="vm")
    assert err is None
    assert outs == _EXPECTED


def test_host_port_five_actions():
    assert _host_port_mirror() == _EXPECTED


@pytest.fixture(autouse=True)
def _clean_custom_ops():
    """parser 层后端写 custom_ops 全局注册表——每测前后清，测试间零泄漏。"""
    ops.clear()
    yield
    ops.clear()


# ============ B. 六层后端实效 ============

def test_parser_backend_end_to_end():
    """注册的算子被源码真消费：1 ⊗ 2 → 双加 → 6；停用后解析器诚实拒绝。"""
    p = make_port("parser")
    src = "func 双加(a: Int, b: Int) -> Int = a + b + a + b\n输出(1 ⊗ 2)\n"
    assert p.register("⊗", 1, (6, "left", "双加"))[0] is True
    ip = Interpreter()
    outs, _ = ip.run(py_parse(src))
    assert outs == [6]
    p.upgrade("⊗", 2, (7, "right", "双加"))
    assert (ops.REGISTRY["⊗"].precedence, ops.REGISTRY["⊗"].assoc) == (7, "right")
    p.rollback("⊗")
    assert (ops.REGISTRY["⊗"].precedence, ops.REGISTRY["⊗"].assoc) == (6, "left")
    p.toggle("⊗", False)
    with pytest.raises(Exception, match="⊗"):
        py_parse("输出(1 ⊗ 2)\n")
    p.toggle("⊗", True)
    outs, _ = Interpreter().run(py_parse(src))
    assert outs == [6]


def test_interp_host_backend_effect():
    ip = Interpreter()
    p = make_port("interp_host", ip)
    assert p.register("双倍", 1, lambda x: x * 2)[0] is True
    ip.outputs.clear()
    ip.run(py_parse("输出(双倍(21))\n"))
    assert ip.outputs == [42]
    p.upgrade("双倍", 2, lambda x: x * 3)
    ip.outputs.clear()
    ip.run(py_parse("输出(双倍(21))\n"))
    assert ip.outputs == [63]
    p.rollback("双倍")
    ip.outputs.clear()
    ip.run(py_parse("输出(双倍(21))\n"))
    assert ip.outputs == [42]
    p.toggle("双倍", False)
    with pytest.raises(Exception, match="双倍"):
        ip.run(py_parse("输出(双倍(21))\n"))
    p.toggle("双倍", True)
    ip.outputs.clear()
    ip.run(py_parse("输出(双倍(21))\n"))
    assert ip.outputs == [42]


def test_vm_backend_effect():
    mod = Compiler().compile_program(py_parse(
        "func 取双倍(x: Int) -> Int = 双倍(x)\n输出(取双倍(21))\n"))
    vm = VM(mod)
    p = make_port("vm", vm)
    assert p.register("双倍", 1, lambda x: x * 2)[0] is True
    vm.run()
    assert vm.outputs == [42]
    p.upgrade("双倍", 2, lambda x: x * 3)
    assert vm.call("取双倍", 21) == 63
    p.rollback("双倍")
    assert vm.call("取双倍", 21) == 42


class _TagPass(Pass):
    def __init__(self, name, tag):
        super().__init__(name)
        self.tag = tag

    def run(self, program):
        return program


def test_compiler_backend_effect():
    pm = PassManager()
    p = make_port("compiler", pm)
    r = p.register("双倍遍", 1, _TagPass("双倍遍", "v1"))
    assert (r[0], r[2]) == (True, "注册完成")
    assert "双倍遍" in pm._passes
    assert p.entry("双倍遍")[2] is False  # 编译器层注册后默认未启用（既有语义）
    p.toggle("双倍遍", True)
    assert "双倍遍" in pm._enabled_passes
    p.toggle("双倍遍", False)
    assert "双倍遍" not in pm._enabled_passes
    p.upgrade("双倍遍", 2, _TagPass("双倍遍", "v2"))
    assert pm._passes["双倍遍"].tag == "v2"
    p.rollback("双倍遍")
    assert pm._passes["双倍遍"].tag == "v1"


def test_kernel_backend_effect():
    p = make_port("kernel")
    prev = features.scoped_blocks()
    try:
        r = p.register("SCOPED_BLOCKS", 1, None)
        assert (r[0], r[2]) == (True, "注册完成")
        assert p.entry("SCOPED_BLOCKS")[2] == features.is_enabled("SCOPED_BLOCKS")
        p.toggle("SCOPED_BLOCKS", True)
        assert features.scoped_blocks() is True
        p.toggle("SCOPED_BLOCKS", False)
        assert features.scoped_blocks() is False
        r = p.toggle("SCOPED_BLOCKS", False)
        assert (r[0], r[2]) == (True, "无变化")
        p.upgrade("SCOPED_BLOCKS", 2, None)
        assert p.entry("SCOPED_BLOCKS")[1] == 2
        p.rollback("SCOPED_BLOCKS")
        assert p.entry("SCOPED_BLOCKS")[1] == 1
    finally:
        features.clear_feature("SCOPED_BLOCKS")
    assert features.scoped_blocks() == prev


_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]

_BOOT_PREAMBLE = """
func 解释器求值名(名: String, 值们: List) -> Value =
  let env = 注册内建(空环境()) in
  let f = 查找环境(env, 名) in
  f(值们)
"""


@pytest.fixture(scope="module")
def boot_vm():
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        with open(rel, encoding="utf-8") as f:
            decls.extend(py_parse(f.read()).decls)
    decls.extend(py_parse(_BOOT_PREAMBLE).decls)
    vm = VM(comp.compile_program(ast.Program(decls=decls)))
    vm.run()
    return vm


def test_interp_boot_backend_effect(boot_vm):
    p = make_port("interp_boot", boot_vm)
    r = p.register("三倍", 1, "(ps) => ps[0] * 3")
    assert (r[0], r[2]) == (True, "注册完成")
    assert boot_vm.call("解释器求值名", "三倍", [21]) == 63
    p.upgrade("三倍", 2, "(ps) => ps[0] * 4")
    assert boot_vm.call("解释器求值名", "三倍", [21]) == 84
    p.rollback("三倍")
    assert boot_vm.call("解释器求值名", "三倍", [21]) == 63
    p.toggle("三倍", False)
    with pytest.raises(Exception, match="三倍"):
        boot_vm.call("解释器求值名", "三倍", [21])
    p.toggle("三倍", True)
    assert boot_vm.call("解释器求值名", "三倍", [21]) == 63
    boot_vm.call("注销解释器插口", "三倍")


# ============ C. 诚实拒绝矩阵（假 + 状态原样 + 原因） ============

def test_refusal_parser_bad_assoc():
    p = make_port("parser")
    before = p.state()
    r = p.register("新符号", 1, (5, "sideways", None))
    assert r[0] is False and "结合性" in r[2] and p.state() == before


def test_refusal_interp_host_reserve_and_noncall():
    p = make_port("interp_host", Interpreter())
    before = p.state()
    r = p.register("输出", 1, lambda ps: ps)
    assert r[0] is False and "保留" in r[2] and p.state() == before
    r = p.register("坏值", 1, "不是函数")
    assert r[0] is False and "可调用" in r[2] and p.state() == before


def test_refusal_vm_reserve_and_module_fn():
    mod = Compiler().compile_program(py_parse(
        "func 取双倍(x: Int) -> Int = 双倍(x)\n输出(取双倍(21))\n"))
    p = make_port("vm", VM(mod))
    before = p.state()
    r = p.register("输出", 1, print)
    assert r[0] is False and "保留" in r[2] and p.state() == before
    r = p.register("取双倍", 1, lambda x: x)
    assert r[0] is False and "模块函数" in r[2] and p.state() == before


def test_refusal_kernel_unknown_and_no_history():
    p = make_port("kernel")
    before = p.state()
    r = p.register("鬼特性", 1, None)
    assert r[0] is False and "不是内核特性" in r[2] and p.state() == before
    p.register("STACK_ENGINE", 1, None)
    r = p.rollback("STACK_ENGINE")
    assert (r[0], r[2]) == (False, "无历史")


def test_refusal_interp_boot_reserve(boot_vm):
    p = make_port("interp_boot", boot_vm)
    before = p.state()
    r = p.register("输出", 1, "(ps) => ps[0]")
    assert r[0] is False and "保留" in r[2] and p.state() == before


def test_refusal_unknown_layer():
    with pytest.raises(ValueError, match="未知端口层"):
        make_port("鬼层")


# ============ E. os_runtime 工具链单元装载（28e-3） ============

def test_os_runtime_toolchain_units():
    """六工具链层注册为内核服务单元：装载=端口注册（注册即启用）、
    单元启动/停止派发端口启停（真实层效果）、主步=端口健康探针心跳。"""
    from src.os_runtime import OsRuntime

    features.set_feature("SCOPED_BLOCKS", False)  # 内核层条目实况归零
    rt = OsRuntime()
    names = rt.register_toolchain_units()
    assert names == ["工具链-词法语法", "工具链-解释器宿主", "工具链-解释器自举",
                     "工具链-编译器", "工具链-虚拟机", "工具链-内核特性"]
    p = rt.toolchain_port("parser")
    assert p.entry("工具链-词法语法")[2] is True
    assert p.audit() == ["注册 词法语法/工具链-词法语法 v1"]
    # parser 层：装载即注册（注册表有算子）→ 启动（已启用，无变化）→
    # 停止注销 → 重启动重注册（内核允许重启已停止单元）
    assert "工具链-词法语法" in ops.REGISTRY
    assert rt.start("工具链-词法语法")["结果"] == "运行中"
    assert "工具链-词法语法" in ops.REGISTRY
    assert rt.stop("工具链-词法语法")["结果"] == "已停止"
    assert "工具链-词法语法" not in ops.REGISTRY
    assert p.entry("工具链-词法语法")[2] is False
    assert rt.start("工具链-词法语法")["结果"] == "运行中"
    assert "工具链-词法语法" in ops.REGISTRY
    # 内核特性层：启停真翻转 SCOPED_BLOCKS
    try:
        assert rt.start("工具链-内核特性")["结果"] == "运行中"
        assert features.is_enabled("SCOPED_BLOCKS") is True
        assert rt.stop("工具链-内核特性")["结果"] == "已停止"
        assert features.is_enabled("SCOPED_BLOCKS") is False
    finally:
        features.clear_feature("SCOPED_BLOCKS")
    # 编译器层：注册入表未启用 → 启动启用 → 停止停用
    cport = rt.toolchain_port("compiler")
    assert cport.entry("工具链-编译器")[2] is False
    assert rt.start("工具链-编译器")["结果"] == "运行中"
    assert cport.entry("工具链-编译器")[2] is True
    assert rt.stop("工具链-编译器")["结果"] == "已停止"
    assert cport.entry("工具链-编译器")[2] is False
    # 自举层：boot VM 已建、插口随装载落名 → 启动（覆盖）→ 停止注销 →
    # 重启动重注册
    bport = rt.toolchain_port("interp_boot")
    assert rt.start("工具链-解释器自举")["结果"] == "运行中"
    assert bport.entry("工具链-解释器自举")[2] is True
    assert rt.stop("工具链-解释器自举")["结果"] == "已停止"
    assert bport.entry("工具链-解释器自举")[2] is False
    assert rt.start("工具链-解释器自举")["结果"] == "运行中"
    assert bport.entry("工具链-解释器自举")[2] is True
    # 服务步健康探针：启动进程 + 调度一轮收心跳
    assert rt.start("工具链-虚拟机")["结果"] == "运行中"
    assert rt.start_process("工具链-虚拟机")["结果"] == "已启动"
    r = rt.tick(1)
    assert any(isinstance(ev, str) and "虚拟机 条目" in ev for ev in r["事件"])


# ============ F. 状态形状与层名 ============

def test_state_shape_and_layer_names():
    assert set(LAYER_NAMES) == {"parser", "interp_host", "interp_boot",
                                "compiler", "vm", "kernel"}
    assert set(LAYER_NAMES.values()) == {"词法语法", "解释器宿主", "解释器自举",
                                         "编译器", "虚拟机", "内核特性"}
    p = make_port("parser")
    st = p.state()
    assert set(st) == {"层", "条目", "审计"} and st["层"] == "词法语法"
    p.register("甲op", 1, (1, "left", None))
    e = p.state()["条目"][0]
    assert len(e) == 6 and e[:3] == ["甲op", 1, True] and e[4] == [] and e[5] == []
    # Matha 面条目同形（六槽）
    ip = Interpreter()
    ip.run(py_parse(
        "use 标准库 { len }\n"
        "use 端口协议\n"
        "let r = 端口注册(新端口(\"编译器\"), \"内联\", 1, \"impl\", [])\n"
        "输出(len(r[1][\"条目\"][0]))\n"
        "输出(r[1][\"条目\"][0][5])\n"))
    assert ip.outputs == [6, []]
