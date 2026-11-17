"""阶段 27e：纯 Matha TUI 桌面三锁（matha/os/desktop.matha + 终端 桌面 命令）。

桌面形态：纯 Matha 模块 桌面，use 标准库 { len | str } + use 内核（共生体
桌面软件面，运行在 27c 内核之上）。桌面 = [内核, 焦点, 消息, 退出]；帧 =
[行, ...]（头两行固定：标题 + 消息）。按键集 j/k 焦点（环绕）s 启动 t 停止
u 卸载 p 进程 d 步进 q 退出；动作经内核协商面，拒绝如实回传消息行。
演示单元（演示桌面 预装载，终端命令与测试共用）：时钟 服务 v1（步计数器
3 步退出，提供服务「钟」）、回声 app v1（一次性步）、便签 包 v1（无入口）。

终端命令（matha/term_engine.matha ⑤b）：桌面 [键们...] 一次性确定性 TUI
脚本——主循环折叠键序列，输出键迹（每键消息行）+ 终态帧；缺省键序演示
完整单元生命周期。无全局状态面（设全局/读全局为 VM 内部函数不暴露）→
命令为无状态一次性脚本，真交互逐键会话属终端 face 范围外。

本文件锁（host = Interpreter + use 桌面/内核；vm = exec_api.run_checked
双面对拍）：
A 驱动 39 输出逐位对拍：帧结构（标题/消息固定下标、单元/进程/服务行）/
  焦点环绕（j 末尾→开头、k 开头→末尾）/ 生命周期协商消息（启动成功、
  已运行拒绝、进程启动+pid 行、须先停止）/ 调度步进（1/1/2 事件含退出、
  空转 0 步）/ 停止卸载（服务自动注销→服务行消失帧 9→8 行）/ 未知键 /
  主循环折叠（10 帧、q 收口、早退 1 帧）；
B 桌面模块纯度锁：单模块、use 清单与实际使用一致（len/str）、裸 use 内核；
C Matha 编译器自举编译逐位一致（tier C：joined stdlib+kernel+desktop 产物
  ≡ 宿主编译——桌面纯度的可运行形态证明）；
D 自举产物独立运行（tier A：Matha 编译产物实例化独立 VM，演示桌面→按键
  启动→q 置位退出旗标）；
E 终端 桌面 命令 e2e（终端执行器 6 文件编译链双面）：缺省键序 22 行逐位
  对拍 / 协商拒绝键序（焦点移动 + 进程拒绝 + 焦点标记）/ 未知键序列 /
  17 键超限双面同文显式拒绝。

边界：桌面为纯 Matha 框架级 TUI（事件注入式按键脚本）；真交互逐键会话、
外部单元桌面接入（os_runtime 桥 27d）、资源库三分支（27f）属后续范围。
"""

import contextlib
import io
import re

import pytest

from src.interp import Interpreter
from src.kernel import exec_api
from src.mbc.compiler import Compiler, MFunction, MModule
from src.mbc.vm import VM
from src.parser import parse as py_parse
from src import ast_nodes as ast


# ============================================================
# 双面驱动（host / vm 共用同一源）
# ============================================================

_DRIVER = '''
use 桌面
use 内核

let 桌 = 演示桌面()

(* 初始帧结构 *)
输出(渲染帧(桌)[0])
输出(渲染帧(桌)[1])
输出(渲染帧(桌)[2])
输出(渲染帧(桌)[3])
输出(渲染帧(桌)[4])
输出(渲染帧(桌)[6])
输出(len(渲染帧(桌)))
输出(len(桌[0][1]))
输出(服务_解析(桌[0], "钟"))

(* 焦点环绕 *)
let 桌2 = 按键(桌, "j")
输出(渲染帧(桌2)[1])
let 桌3 = 按键(桌2, "j")
输出(渲染帧(桌3)[1])
let 桌4 = 按键(桌3, "j")
输出(渲染帧(桌4)[1])
let 桌5 = 按键(桌4, "k")
输出(渲染帧(桌5)[1])
let 桌6 = 按键(桌5, "k")
输出(渲染帧(桌6)[1])
let 桌7 = 按键(桌6, "k")
输出(渲染帧(桌7)[1])

(* 生命周期动作面（焦点 0 = 时钟） *)
let 桌8 = 按键(桌7, "s")
输出(渲染帧(桌8)[1])
let 桌9 = 按键(桌8, "s")
输出(渲染帧(桌9)[1])
let 桌10 = 按键(桌9, "p")
输出(渲染帧(桌10)[1])
输出(渲染帧(桌10)[5])
let 桌11 = 按键(桌10, "u")
输出(渲染帧(桌11)[1])

(* 调度面 *)
let 桌12 = 按键(桌11, "d")
输出(渲染帧(桌12)[1])
let 桌13 = 按键(桌12, "d")
输出(渲染帧(桌13)[1])
let 桌14 = 按键(桌13, "d")
输出(渲染帧(桌14)[1])
输出(渲染帧(桌14)[5])
let 桌15 = 按键(桌14, "d")
输出(渲染帧(桌15)[1])

(* 停止 / 卸载 *)
let 桌16 = 按键(桌15, "t")
输出(渲染帧(桌16)[1])
let 桌17 = 按键(桌16, "t")
输出(渲染帧(桌17)[1])
let 桌18 = 按键(桌17, "u")
输出(渲染帧(桌18)[1])
输出(len(渲染帧(桌18)))
输出(服务_解析(桌18[0], "钟"))
输出(渲染帧(桌18)[2])

(* 未知键 + 退出 *)
let 桌19 = 按键(桌18, "x")
输出(渲染帧(桌19)[1])
let 桌20 = 按键(桌19, "q")
输出(渲染帧(桌20)[1])
输出(桌20[3])

(* 主循环折叠 *)
let 回 = 主循环(演示桌面(), ["d", "s", "p", "d", "d", "d", "d", "t", "u", "q"])
输出(len(回[1]))
输出(回[0][2])
输出(len(回[0][0][1]))
let 回2 = 主循环(演示桌面(), ["q", "d", "d"])
输出(len(回2[1]))
输出(回2[0][2])
'''

_EXPECTED = [
    # 初始帧结构（无进程帧 9 行：头 2 + 单元 3 + 服务 1 + 尾 3）
    "== Matha 桌面共生体 ==", "消息: 演示就绪 3 单元",
    "> [1] 时钟 服务 v1 已装载", "  [2] 回声 app v1 已装载",
    "  [3] 便签 包 v1 已装载", "--", 9, 3, "时钟",
    # 焦点环绕（j 末尾→开头 / k 开头→末尾）
    "消息: 焦点 2/3", "消息: 焦点 3/3", "消息: 焦点 1/3",
    "消息: 焦点 3/3", "消息: 焦点 2/3", "消息: 焦点 1/3",
    # 生命周期协商（启动成功 / 重复启动拒绝 / 进程 / pid 行 / 运行中卸载拒绝）
    "消息: 启动成功: 运行中", "消息: 启动拒绝: 已运行",
    "消息: 进程成功: 已启动", "  pid 1 时钟/主 就绪 步数 0",
    "消息: 卸载拒绝: 须先停止",
    # 调度（步数/事件：1/1/2 含退出事件、空转 0 步、进程行翻已退出）
    "消息: 步进 1 步 事件 1", "消息: 步进 1 步 事件 1",
    "消息: 步进 1 步 事件 2", "  pid 1 时钟/主 已退出 步数 3",
    "消息: 步进 0 步 事件 0",
    # 停止 / 卸载（服务自动注销 → 服务行消失，帧 9→8 行）
    "消息: 停止成功: 已停止", "消息: 停止拒绝: 未运行",
    "消息: 卸载成功: 已卸载", 8, None, "> [1] 回声 app v1 已装载",
    # 未知键 + q 置位退出旗标
    "消息: 未知键 x", "消息: 桌面退出", True,
    # 主循环折叠（10 帧 / 收口消息 / 卸载后余 2 单元 / 早退 1 帧）
    10, "桌面退出", 2, 1, "桌面退出",
]


def _host_outputs(src):
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(py_parse(src))
    return list(ip.outputs)


def _vm_outputs(src):
    outs, err = exec_api.run_checked(src, mode="vm")
    assert err is None, f"vm 面报错: {err}"
    return outs


@pytest.fixture(scope="module")
def host_outs():
    return _host_outputs(_DRIVER)


@pytest.fixture(scope="module")
def vm_outs():
    return _vm_outputs(_DRIVER)


# ============================================================
# A 面：双面全按键矩阵对拍
# ============================================================

def test_double_face_full_key_matrix_parity(host_outs, vm_outs):
    """host 与 vm 双面跑同一驱动：39 条输出逐位一致（use 桌面 双面可达）。"""
    assert len(host_outs) == 39
    assert len(vm_outs) == 39
    assert vm_outs == host_outs
    assert vm_outs == _EXPECTED


def test_initial_frame_structure(host_outs):
    """初始帧：标题/消息固定头两行、焦点标记在时钟、无进程帧 9 行、
    单元数 3、服务「钟」解析到提供单元。"""
    assert host_outs[0:9] == _EXPECTED[0:9]


def test_focus_wrap(host_outs):
    """焦点环绕：j 三次末尾→开头（3/3 后 1/3）、k 三次开头→末尾再回。"""
    assert host_outs[9:15] == ["消息: 焦点 2/3", "消息: 焦点 3/3", "消息: 焦点 1/3",
                               "消息: 焦点 3/3", "消息: 焦点 2/3", "消息: 焦点 1/3"]


def test_lifecycle_negotiation_messages(host_outs):
    """生命周期协商：启动成功/重复启动拒绝/进程启动（pid 行入帧）/运行中卸载拒绝。"""
    assert host_outs[15:20] == ["消息: 启动成功: 运行中", "消息: 启动拒绝: 已运行",
                                "消息: 进程成功: 已启动",
                                "  pid 1 时钟/主 就绪 步数 0",
                                "消息: 卸载拒绝: 须先停止"]


def test_scheduler_steps(host_outs):
    """调度步进：三轮 1/1/2 事件（第三轮含退出事件）、进程行翻已退出、
    空转轮 0 步 0 事件。"""
    assert host_outs[20:25] == ["消息: 步进 1 步 事件 1", "消息: 步进 1 步 事件 1",
                                "消息: 步进 1 步 事件 2",
                                "  pid 1 时钟/主 已退出 步数 3",
                                "消息: 步进 0 步 事件 0"]


def test_stop_unload_service_gone(host_outs):
    """停止/卸载：未运行停止拒绝、卸载成功、服务「钟」自动注销（null）、
    服务行消失（帧 9→8 行）、焦点标记落回声。"""
    assert host_outs[25:31] == ["消息: 停止成功: 已停止", "消息: 停止拒绝: 未运行",
                                "消息: 卸载成功: 已卸载", 8, None,
                                "> [1] 回声 app v1 已装载"]


def test_unknown_key_quit_and_fold(host_outs):
    """未知键如实入消息；q 置位退出旗标；主循环折叠 10 帧、卸载后余 2 单元、
    q 后余键不应用（早退 1 帧）。"""
    assert host_outs[31:39] == ["消息: 未知键 x", "消息: 桌面退出", True,
                                10, "桌面退出", 2, 1, "桌面退出"]


# ============================================================
# 纯度 / 形态锁
# ============================================================

_DESKTOP_REL = "matha/os/desktop.matha"
_USE_SYMBOLS = ["len", "str"]


def test_desktop_module_shape_and_use_honesty():
    """桌面单模块、use 清单与实际使用一致（len/str 均在体内出现）、裸 use 内核。"""
    with open(_DESKTOP_REL, encoding="utf-8") as f:
        src = f.read()
    prog = py_parse(src)
    assert len(prog.decls) == 1
    mod = prog.decls[0]
    assert getattr(mod, "name", None) == "桌面"
    m = re.search(r"use\s+标准库\s*\{([^}]*)\}", src)
    assert m, "缺 use 标准库 声明"
    declared = [s.strip() for s in m.group(1).split("|")]
    assert declared == _USE_SYMBOLS
    body = src[m.end():]
    for sym in _USE_SYMBOLS:
        assert sym + "(" in body, f"use 清单符号 {sym} 未在体内使用（清单诚实性）"
    assert re.search(r"^  use 内核\s*$", src, re.M), "缺裸 use 内核（内核协商面）"


# ============================================================
# C 面：Matha 编译器自举编译逐位一致（tier C）
# ============================================================

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]


def _read_source(rel):
    with open(rel, encoding="utf-8") as f:
        return f.read()


def _compile_files(rels):
    comp = Compiler()
    decls = []
    for rel in rels:
        decls.extend(py_parse(_read_source(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


def module_to_dict(mod):
    d = {"模块名": mod.module_name, "常量": list(mod.constants),
         "主码": [list(x) for x in mod.main_code], "函数": []}
    for name, fn in mod.functions.items():
        info = {"元数": fn.arity, "局部数": fn.nlocals,
                "码": [list(x) for x in fn.code], "参数": list(fn.params)}
        d["函数"].append([name, info])
    return d


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


_OSCONCAT_FILES = ["matha/stdlib.matha", "matha/os/kernel.matha", _DESKTOP_REL]


@pytest.fixture(scope="module")
def matha_desktop_dict():
    """Matha 编译器编译 joined stdlib+kernel+desktop 拼接源（自举 VM 内编译）。"""
    vm = VM(_compile_files(_BOOT_FILES).mod)
    vm.run()
    joined = "\n".join(_read_source(rel) for rel in _OSCONCAT_FILES)
    md = vm.call("编译", joined)
    assert isinstance(md, dict)
    return md


def test_selfhost_compile_identical(matha_desktop_dict):
    """tier C：Matha 编译器编译 stdlib+kernel+desktop ≡ 宿主编译产物
    （模块名/主码/常量池/函数表逐位一致）。"""
    host = module_to_dict(_compile_files(_OSCONCAT_FILES).mod)
    md = matha_desktop_dict
    assert md["模块名"] == host["模块名"]
    assert [list(x) for x in md["主码"]] == [list(x) for x in host["主码"]]
    assert list(md["常量"]) == list(host["常量"])
    mf = {e[0]: e[1] for e in md["函数"]}
    hf = {e[0]: e[1] for e in host["函数"]}
    assert set(mf) == set(hf)
    for name, info in hf.items():
        got = mf[name]
        assert got["元数"] == info["元数"], name
        assert got["局部数"] == info["局部数"], name
        assert [list(x) for x in got["码"]] == [list(x) for x in info["码"]], name
        assert list(got["参数"]) == list(info["参数"]), name


# ============================================================
# D 面：自举产物独立运行（tier A）
# ============================================================

def test_standalone_product_desktop(matha_desktop_dict):
    """tier A：Matha 编译产物实例化独立 VM，桌面真跑
    （演示桌面→按键启动→帧消息→q 置位退出旗标）。"""
    inner = VM(dict_to_module(matha_desktop_dict))
    inner.run()

    def call(name, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return inner.call(name, *args)

    d0 = call("演示桌面")
    assert len(d0) == 4
    assert len(d0[0][1]) == 3
    d1 = call("按键", d0, "s")
    assert call("渲染帧", d1)[1] == "消息: 启动成功: 运行中"
    d2 = call("按键", d1, "q")
    assert d2[3] is True
    assert call("渲染帧", d2)[1] == "消息: 桌面退出"


# ============================================================
# E 面：终端 桌面 命令 e2e（终端执行器 6 文件编译链）
# ============================================================

_TERM_FILES = ["matha/stdlib.matha", "matha/os/kernel.matha", "matha/os/desktop.matha",
               "matha/term_lexer.matha", "matha/term_parser.matha",
               "matha/term_engine.matha"]


@pytest.fixture(scope="module")
def host_term():
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        assert ip.load_matha_module("终端执行器"), "加载 终端执行器 失败"
    return ip


@pytest.fixture(scope="module")
def vm_term():
    comp = Compiler()
    decls = []
    for rel in _TERM_FILES:
        decls.extend(py_parse(_read_source(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    from src.plugin_api import get_resolver
    vm.domain_resolver = get_resolver()
    with contextlib.redirect_stdout(io.StringIO()):
        vm.run()
    return vm


def _host_line(ip, line):
    with contextlib.redirect_stdout(io.StringIO()):
        frame = ip._call_func_or_closure(ip.funcs["终端解析"], [line])
        return ip._call_func_or_closure(ip.funcs["终端执行"], [frame, line])


def _vm_line(vm, line):
    with contextlib.redirect_stdout(io.StringIO()):
        frame = vm.call("终端解析", line)
        return vm.call("终端执行", frame, line)


_DEFAULT_EXPECTED = [
    "桌面演示 键序 [d s p d d d d t u q]",
    "[1] 消息: 步进 0 步 事件 0",
    "[2] 消息: 启动成功: 运行中",
    "[3] 消息: 进程成功: 已启动",
    "[4] 消息: 步进 1 步 事件 1",
    "[5] 消息: 步进 1 步 事件 1",
    "[6] 消息: 步进 1 步 事件 2",
    "[7] 消息: 步进 0 步 事件 0",
    "[8] 消息: 停止成功: 已停止",
    "[9] 消息: 卸载成功: 已卸载",
    "[10] 消息: 桌面退出",
    "== 终态帧 ==",
    "== Matha 桌面共生体 ==", "消息: 桌面退出",
    "> [1] 回声 app v1 已装载", "  [2] 便签 包 v1 已装载",
    "  pid 1 时钟/主 已退出 步数 3",
    "--",
    "键位: j/k 焦点  s 启动  t 停止  u 卸载  p 进程  d 步进  q 退出",
    "==",
]


def test_terminal_desktop_default_sequence(host_term, vm_term):
    """终端 桌面（缺省键序）：完整单元生命周期 22 行，双面逐位一致。"""
    host = _host_line(host_term, "桌面")
    vm = _vm_line(vm_term, "桌面")
    assert host["退出"] is False
    assert list(host["输出"]) == _DEFAULT_EXPECTED
    assert list(vm["输出"]) == _DEFAULT_EXPECTED


def test_terminal_desktop_negotiation_and_unknown(host_term, vm_term):
    """终端 桌面 j j p / 桌面 x y：焦点移动+进程协商拒绝（焦点标记落便签）/
    未知键如实入迹；双面逐位一致。"""
    host = _host_line(host_term, "桌面 j j p")
    vm = _vm_line(vm_term, "桌面 j j p")
    assert list(host["输出"]) == [
        "桌面演示 键序 [j j p]",
        "[1] 消息: 焦点 2/3",
        "[2] 消息: 焦点 3/3",
        "[3] 消息: 进程拒绝: 单元未运行",
        "== 终态帧 ==",
        "== Matha 桌面共生体 ==", "消息: 进程拒绝: 单元未运行",
        "  [1] 时钟 服务 v1 已装载", "  [2] 回声 app v1 已装载",
        "> [3] 便签 包 v1 已装载",
        "  钟 <- 时钟",
        "--",
        "键位: j/k 焦点  s 启动  t 停止  u 卸载  p 进程  d 步进  q 退出",
        "==",
    ]
    assert list(vm["输出"]) == list(host["输出"])

    host2 = _host_line(host_term, "桌面 x y")
    vm2 = _vm_line(vm_term, "桌面 x y")
    outs = list(host2["输出"])
    assert outs[0] == "桌面演示 键序 [x y]"
    assert outs[1:3] == ["[1] 消息: 未知键 x", "[2] 消息: 未知键 y"]
    assert outs[3] == "== 终态帧 =="
    assert outs[4] == "== Matha 桌面共生体 =="
    assert outs[5] == "消息: 未知键 y"
    assert len(outs) == 13
    assert list(vm2["输出"]) == outs


def test_terminal_desktop_key_cap_error(host_term, vm_term):
    """终端 桌面 17 键：双面同文显式拒绝（至多 16 键；错误 为 12b 胶水内建
    RuntimeError 通道，双端一致）。"""
    line = "桌面 " + " ".join(["d"] * 17)
    with pytest.raises(RuntimeError, match="桌面: 至多 16 个键, 实得 17"):
        _host_line(host_term, line)
    with pytest.raises(RuntimeError, match="桌面: 至多 16 个键, 实得 17"):
        _vm_line(vm_term, line)
