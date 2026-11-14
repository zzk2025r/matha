# -*- coding: utf-8 -*-
"""阶段 21c 三锁：镜像 parser catch{} 歧义消解 + switch 表达式位真化。

修复面（阶段 20/19 登记不修 → 21c 真化，用户拍板三件全选）：
  1. catch{} 歧义：镜像 parser 解析try语句 无 catch 产出哨兵 捕获体=null
     （显式空 catch 仍为 做Program([])，二者可区分）；
     镜像 interp.matha 执行try：null → 重抛（对齐宿主无 catch 路径）、
     空 catch → 吞错继续（对齐宿主 catch 空体语义）；
     镜像 compiler_matha.matha _发射try：null → 先 finally 后 RAISE、
     空 catch → 空体 thunk 照常编译走捕获路径（吞错）。
  2. switch 表达式位：宿主 _parse_primary 与镜像 解析主要 接受 switch
     （语句位分派不受影响）；interp._eval_switch_expr 与编译器 _emit_expr
     SwitchStmt 分支（阶段 19a）早已就绪，本轮只补双端解析。

登记边界（现状锁，不修）：
  - match 表达式位：宿主被字典花括号歧义劫持 ParseError「期望 }」，
    镜像 解析主要 接受 match——双解析器潜分歧维持登记。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter
from src.kernel import exec_api
from src.mbc.compiler import Compiler, compile_program
from src.mbc.vm import VM
from src.parser import parse

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha"]
_COMPILER_FILES = _BOOT_FILES + ["matha/compiler_matha.matha"]


def _boot_src(rels):
    src = ""
    for rel in rels:
        s = (ROOT / rel).read_text(encoding="utf-8")
        if s and s[0] == "﻿":
            s = s.lstrip("﻿")
        src += s
    return src


def _make_vm(rels):
    comp = Compiler()
    comp.compile_program(parse(_boot_src(rels)))
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def full_boot_vm():
    return _make_vm(_BOOT_FILES)


@pytest.fixture(scope="module")
def compiler_boot_vm():
    return _make_vm(_COMPILER_FILES)


# ============================================================
# 1. catch{} 歧义：镜像解析形状二分
# ============================================================

SRC_EMPTY = 'try { raise "炸" } catch(e) { } 输出("继续")'
SRC_NOCA = 'try { raise "炸" } 输出("不应到")'


def _parse_on_vm(vm, src):
    toks = vm.call("tokenize", src)
    return vm.call("parse", toks)


def test_mirror_parse_empty_catch_shape(full_boot_vm):
    """显式空 catch：捕获体 = Program([])（声明=[]）。"""
    tree = _parse_on_vm(full_boot_vm, SRC_EMPTY)
    cb = tree["声明"][0]["捕获体"]
    assert cb is not None and cb["声明"] == []


def test_mirror_parse_no_catch_sentinel(full_boot_vm):
    """无 catch：捕获体 = null 哨兵（与空 catch 可区分——21c 前同形歧义）。"""
    tree = _parse_on_vm(full_boot_vm, SRC_NOCA)
    assert tree["声明"][0]["捕获体"] is None


# ============================================================
# 2. catch{} 歧义：镜像解释器语义（执行try 二分）
# ============================================================

def _run_interp_src(vm, src):
    env = vm.call("注册内建", vm.call("空环境"))
    toks = vm.call("tokenize", src)
    tree = vm.call("parse", toks)
    return vm.call("执行语句列表", tree, env)


def test_mirror_interp_empty_catch_swallows(full_boot_vm):
    """空 catch 吞错继续：宿主 catch 空体语义同构（21c 前镜像误重抛）。"""
    v, _ = _run_interp_src(full_boot_vm, 'try { raise "x" } catch(e) { }')
    assert v is None


def test_mirror_interp_no_catch_rethrows(full_boot_vm):
    """无 catch 重抛：错误继续传播（finally 先执行语义属编译面锁）。"""
    with pytest.raises(Exception) as ei:
        _run_interp_src(full_boot_vm, 'try { raise "x" }')
    assert "x" in str(ei.value)


def test_mirror_interp_no_catch_finally_runs(full_boot_vm):
    """无 catch + finally：finally 先于重抛执行（阶段 20e 同构）。

    观测通道：finally 体自身抛错——若 finally 未先执行，外层 catch 收到
    原错误「原」；finally 先执行则其错误「fin」覆盖之（宿主同语义）。
    环境级观测不可达：镜像解释器重抛路径丢弃环境链（immutable env 经
    错误 通道不可携带）——登记不修；finally 内建调用（原地设置 等）在
    镜像解释器面亦存在协议缺口，登记不修。"""
    v, _ = _run_interp_src(
        full_boot_vm,
        'try { try { raise "原" } finally { raise "fin" } } catch(e) { e }')
    assert v == "fin"


# ============================================================
# 3. catch{} 歧义：镜像编译 → 真实 VM 执行 + stage2 ≡ stage3
# ============================================================

def _mirror_run(compiler_boot_vm, src):
    from tests.test_mbc_bootstrap import dict_to_module
    d = compiler_boot_vm.call("编译", src)
    sub = VM(dict_to_module(d))
    try:
        sub.run()
        return ("ok", [repr(o) for o in sub.outputs])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {e}")


def test_mirror_compile_empty_catch_swallows(compiler_boot_vm):
    """镜像编译空 catch → 真实 VM 吞错继续（对齐宿主面 [继续]）。"""
    assert _mirror_run(compiler_boot_vm, SRC_EMPTY) == ("ok", ["'继续'"])


def test_mirror_compile_no_catch_rethrows(compiler_boot_vm):
    """镜像编译无 catch → 真实 VM 重抛（对齐宿主 MathaRuntimeError 炸）。"""
    tag, msg = _mirror_run(compiler_boot_vm, SRC_NOCA)
    assert tag == "err" and "炸" in msg


def test_mirror_compile_no_catch_finally_rethrows(compiler_boot_vm):
    """镜像编译无 catch + finally → 真实 VM finally 后重抛（20e 同构）。"""
    tag, msg = _mirror_run(
        compiler_boot_vm,
        'try { raise "炸" } finally { 输出("fin") } 输出("不应到")')
    assert tag == "err" and "炸" in msg


@pytest.mark.parametrize("src", [SRC_EMPTY, SRC_NOCA,
                                 'try { raise "炸" } finally { 输出("fin") }'])
def test_mirror_try_stage2_stage3_identity(compiler_boot_vm, src):
    """宿主编译器（stage2）与镜像编译器（stage3）对 try 三形态产出逐位一致。"""
    from tests.test_mbc_bootstrap import _canon, _host_compile, dict_to_module
    h = _canon(_host_compile(src))
    m = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    assert h == m


# ============================================================
# 4. catch{} 歧义：官方门面对拍（宿主面 ≡ 官方 VM 面）
# ============================================================

def _host_out(src):
    it = Interpreter()
    it.run(parse(src))
    return [repr(o) for o in it.outputs]


def _vm_out(src):
    outs, err = exec_api.run_checked(src)
    if err is not None:
        raise err
    return [repr(o) for o in outs]


@pytest.mark.parametrize("src", [
    SRC_EMPTY,
    'try { 输出(1) } catch(e) { } 输出("继续")',
    'try { raise "x" } catch(e) { 5 }',
    'try { try { raise "原" } finally { raise "fin" } } catch(e) { 输出(e) }',
])
def test_empty_vs_no_catch_official_faces(src):
    """空 catch 吞错 / 无 catch 重抛双端对拍（官方门面，成功路径）。"""
    assert _host_out(src) == _vm_out(src)


def test_no_catch_official_faces_error():
    """无 catch / 无 catch+finally：双端一致报错（错误类别+消息）。"""
    with pytest.raises(Exception) as h:
        _host_out(SRC_NOCA)
    with pytest.raises(Exception) as v:
        _vm_out(SRC_NOCA)
    assert "炸" in str(h.value) and "炸" in str(v.value)
    fin_src = 'try { raise "炸" } finally { 输出("fin") } 输出("不应到")'
    with pytest.raises(Exception) as h2:
        _host_out(fin_src)
    with pytest.raises(Exception) as v2:
        _vm_out(fin_src)
    assert "炸" in str(h2.value) and "炸" in str(v2.value)


# ============================================================
# 5. switch 表达式位：双端对拍
# ============================================================

SW_SRC = ('func f(n: Int) -> Int = switch n { case 1: 100 default: 200 }\n'
          '输出(f(1))\n'
          '输出(f(5))\n'
          'let 乙 = switch "乙" { case "甲": 1 default: 2 }\n'
          '输出(乙)\n'
          '输出(switch 3 { case 1: 10 case 3: 30 default: 99 })\n'
          '输出(switch 9 { case 1: 10 })\n')


def test_switch_expr_official_faces_parity():
    """switch 表达式位：函数体尾/let 右值/实参/多 case/无 default=None 双端一致。"""
    assert _host_out(SW_SRC) == _vm_out(SW_SRC) == \
        ["100", "200", "2", "30", "None"]


def test_switch_stmt_position_unchanged():
    """语句位 switch 回归：分派路径不受 primary 新分支影响。"""
    src = "switch 1 { case 1: 输出(9) default: 输出(8) }"
    assert _host_out(src) == _vm_out(src) == ["9"]


def test_mirror_compile_switch_expr(compiler_boot_vm):
    """镜像编译 switch 表达式位 → 真实 VM 执行 [20]。"""
    tag, outs = _mirror_run(
        compiler_boot_vm,
        'let 甲 = switch 2 { case 1: 10 default: 20 }\n输出(甲)\n')
    assert (tag, outs) == ("ok", ["20"])


def test_mirror_parse_switch_expr_shape(full_boot_vm):
    """镜像 解析主要 接受 switch 表达式位（节点形状与语句位同型）。"""
    tree = _parse_on_vm(
        full_boot_vm,
        'let 甲 = switch 2 { case 1: 10 default: 20 }\n')
    node = tree["声明"][0]["值"]
    assert node["类型"] == "switch" and node["值"]["类型"] == "整数"


# ============================================================
# 6. 登记边界现状锁（不修）
# ============================================================

def test_match_expr_host_dict_hijack_registered():
    """match 表达式位：宿主被字典花括号歧义劫持（登记不修，现状锁）。"""
    with pytest.raises(Exception) as h:
        _host_out("let 甲 = match 1 { | 1 => 10 | _ => 20 } 输出(甲)")
    assert "期望 }" in str(h.value)


def test_match_expr_mirror_accepts_registered(full_boot_vm):
    """match 表达式位：镜像 解析主要 接受（双解析器潜分歧维持登记）。"""
    tree = _parse_on_vm(
        full_boot_vm, 'let 甲 = match 1 { | 1 => 10 | _ => 20 }\n')
    assert tree["声明"][0]["值"]["类型"] == "match"


# ============================================================
# 7. 防回潮文本锁
# ============================================================

def test_mirror_no_catch_sentinel_text_locks():
    """三镜像文件的哨兵/二分位点在位（防回潮）。"""
    assert '("", null, p4)' in (ROOT / "matha/parser.matha").read_text(
        encoding="utf-8")
    assert "stmt.捕获体 = null" in (ROOT / "matha/interp.matha").read_text(
        encoding="utf-8")
    assert 'e["捕获体"] = null' in (ROOT / "matha/compiler_matha.matha").read_text(
        encoding="utf-8")


def test_host_switch_primary_branch_lock():
    """宿主解析器 primary 位 KW_SWITCH 分支在位（21c 注释锚点）。"""
    assert "switch 表达式位（阶段 21c）" in (ROOT / "src/parser.py").read_text(
        encoding="utf-8")
