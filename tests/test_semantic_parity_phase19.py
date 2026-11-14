# -*- coding: utf-8 -*-
"""阶段 19 · 双端语义第四片（match/switch 表达式位 + MechUnit 组合 body）三锁。

残留 31 分歧归类（169 语料 sweep）后的 A 类 15 文件根因两件，本轮全修：
  19a match/switch 表达式位 VM 真化：src/mbc/compiler.py _emit_expr 新增
      MatchStmt/SwitchStmt 分支（leave_value=True 委托 _emit_match/_emit_switch）
      ——host _eval 早已支持（interp.py MatchStmt/SwitchStmt），语句/块尾位
      早已支持（_STMT_NODES/_VALUE_STMTS）；函数体 Lambda 值位的 match 此前
      掉进兜底报「暂不支持的节点 MatchStmt」（14 语料）——自举镜像
      compiler_matha.matha _发射表达式 早有此分支，本轮主侧补齐闭合
      主↔镜像反向差。switch 表达式位旧登记「解析器拒绝」已由阶段 21c 真化
      （主解析器 KW_SWITCH 表达式分支，本文件该锁改锁匹配形态双端同值）。
  19b MechUnit 裸 list body VM 真化：parser.py:626 `#N：命令` 后跟 `{ }`
      代码块时 body=[GenStmt, CodeBlock]（裸 Python list）——host
      _exec_stmt 链循环容忍，VM _compile_stmt 掉 _emit_expr 报
      「暂不支持的节点 list」（bootstrap_test/v2）。本轮 _compile_stmt
      新增 list 分支逐元素编译，与 host 容忍面同构。

登记边界（阶段 20 收口勘误后状态）：
  - match 无匹配分支 / 守卫求值序 / try-finally 无 catch 重抛三处旧登记
    分歧已由阶段 20 全部真化收口（编译面→解释面对齐 + 新 opcode
    RAISE_MATCH 值渲染 + finally 全链「先 finally 后重抛」同构）——专项
    锁在 test_semantic_parity_phase20.py，本文件保留收口后一致性轻锁。
  - bootstrap_test/v2 编译缺口修复后残留分歧转 C 类（自举链符号面）：
    〔勘误 2026-11 阶段 21b〕C 类已真化收口——编译面 use 解析为 CALL
    加载模块，裸 VM 面诚实拒绝边界前移至加载器名（错误形态改锁）；
    官方门面注入加载器后 vm 面跑通全程（专项锁 test_use_compile_phase21）。

三锁封死：
  1. 对拍：语料型 func 体 match/绑定 match/顶层 match 语句/变量绑定模式/
     字面守卫/switch 块尾值/switch 语句无 default/MechUnit 组合 body 单段
     双段——host ↔ vm 输出逐值一致；语料面 grammar.matha [] 与
     os_concepts.matha 错误传播同构（双端同错同消息）。
  2. 闭环：matha run 真子进程 func 体 match 输出、MechUnit 组合 body 输出、
     grammar.matha 语料运行 exit 0。
  3. 边界：switch 表达式位解析拒绝、MechUnit 纯块与裸 list AST 形态锁、
     bootstrap_test/v2 编译通过 + C 类边界现状锁、19c 收口后一致性轻锁。
  4. 19c 终端管道态修复：段内出错 catch 清态后重抛不泄漏（host 锁在
     test_matha_term_13a.py 旧锁改锁新形态、VM 面在此）+ 引擎 try 形态
     保值/重抛保真锁（引擎弃 finally 改 catch-清态-重抛，形态保留）。
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import ast_nodes  # noqa: E402
from src.interp import Interpreter  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.parser import ParseError, parse  # noqa: E402


def _run_host(src: str) -> list:
    interp = Interpreter(debug=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        interp.run(parse(src))
    return list(interp.outputs)


def _run_vm(src: str) -> list:
    mod = Compiler().compile_program(parse(src))
    vm = VM(mod)
    vm.run()
    return list(vm.outputs)


def _both(src: str, expected: list) -> None:
    assert _run_host(src) == expected, f"host: {_run_host(src)}"
    assert _run_vm(src) == expected, f"vm: {_run_vm(src)}"


def _run_raw(src: str, backend: str):
    """双端原始形态：成功返回 outputs 列表，失败返回 'ERR 类名: 消息'。"""
    try:
        if backend == "host":
            return _run_host(src)
        return _run_vm(src)
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {e}"


def _run_file(src: str, name: str = "用例19.matha") -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / name
        p.write_text(src, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "src.matha_main", "run", str(p)],
            capture_output=True, timeout=120,
        )


_FUNC_MATCH = (
    "func 词类(词: String) -> String =\n"
    "  (词) =>\n"
    "  match 词 {\n"
    "    | \"的\" => \"助词\"\n"
    "    | _ => \"名词\"\n"
    "  }\n"
    "输出(词类(\"的\"))\n输出(词类(\"跑\"))\n"
)


# ============================================================
# 1. 对拍：19a/19b 真化后 host ↔ vm 输出逐值一致
# ============================================================

class TestParity19aMatchExpr:
    """match 表达式位（函数体 Lambda 值位）双端一致（14 语料同型）。"""

    def test_func_body_match_corpus_form(self):
        _both(_FUNC_MATCH, ["助词", "名词"])

    def test_binding_rhs_match(self):
        _both(
            "甲 = match 5 {\n  | 1 => 10\n  | 5 => 50\n  | _ => 99\n}\n输出(甲)\n",
            [50],
        )

    def test_top_level_match_stmt_unchanged(self):
        # 语句位 match 本就双端支持（_STMT_NODES），回归锁
        _both("match 5 {\n  | 5 => 输出(\"中\")\n  | _ => 输出(\"偏\")\n}\n", ["中"])

    def test_variable_binding_pattern(self):
        _both(
            "func 首项(对: List) -> Int =\n"
            "  (对) =>\n"
            "  match 对 {\n"
            "    | 对 => 对[0]\n"
            "    | _ => 0\n"
            "  }\n"
            "输出(首项([7, 8]))\n",
            [7],
        )

    def test_no_wildcard_hit(self):
        _both("输出(match 2 {\n  | 1 => 10\n  | 2 => 20\n})\n", [20])

    def test_literal_guard_order_irrelevant(self):
        # 字面模式 + 常量守卫：求值序双端同构（阶段 20 收口：先守卫后模式）
        _both(
            "输出(match 7 {\n  | 7 if 1 > 0 => \"大\"\n  | _ => \"小\"\n})\n",
            ["大"],
        )

    def test_corpus_grammar_matha(self):
        src = (ROOT / "matha/knowledge/linguistics/grammar.matha").read_text(encoding="utf-8")
        assert _run_host(src) == _run_vm(src) == []

    def test_corpus_error_parity_os_concepts(self):
        # host/vm 双端同错同消息（错误传播同构；未定义名 'else' 为语料存量）
        src = (ROOT / "matha/resource/cs/os_concepts.matha").read_text(encoding="utf-8")
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "未定义变量 'else'" in ho


class TestParity19aSwitch:
    """switch 块尾值路径回归 + 表达式位解析拒绝登记。"""

    def test_switch_block_tail_value(self):
        # lambda 体 CodeBlock 尾 switch：块尾值位（_VALUE_STMTS 既有路径）
        _both(
            "func 拾(v: Int) -> Int =\n"
            "  (v) => {\n"
            "    switch v {\n"
            "      case 1: 10\n"
            "      case 2: 20\n"
            "      default: 30\n"
            "    }\n"
            "  }\n"
            "输出(拾(2))\n输出(拾(3))\n",
            [20, 30],
        )

    def test_switch_expr_position_parse_rejected(self):
        # 〔勘误 2026-11 阶段 21c〕switch 表达式位已真化（主解析器 _parse_primary
        # KW_SWITCH 分支落地，interp/_emit_expr 求值面 19a 早已就绪）——
        # 旧登记拒绝形态除名，改锁新形态：匹配形态表达式位双端同值
        # （无匹配+无 default → None 双端，专项锁见 test_semantic_parity_phase21）
        _both("输出(switch 2 { case 2: 10 })\n", [10])

    def test_switch_stmt_no_default_silent(self):
        _both("switch 9 { case 1: 输出(10) }\n输出(7)\n", [7])


class TestParity19bListBody:
    """MechUnit 组合 body（#N：命令 + { } 代码块）双端一致。"""

    def test_mech_combined_body_single(self):
        _both(
            "module 测试19 {\n#1：【段一】\n{\n甲 = 6 * 7\n[甲]\n}\n}\n",
            [42],
        )

    def test_mech_combined_body_two_segments(self):
        _both(
            "module 测试19 {\n"
            "#1：【段一】\n{\n甲 = 6 * 7\n[甲]\n}\n"
            "#2：【段二】\n{\n乙 = 甲 + 1\n[乙]\n}\n"
            "}\n",
            [42, 43],
        )

    def test_mech_pure_block_unchanged(self):
        _both("#：{ [8] }\n", [8])

    def test_parser_list_body_shape(self):
        # 解析器形态锁：组合 body 产出裸 list [GenStmt, CodeBlock]
        prog = parse("module 甲 {\n#1：【段】\n{\n[9]\n}\n}\n")
        mod = prog.decls[0]
        mech = mod.decls[0]
        assert type(mech).__name__ == "MechUnit"
        assert isinstance(mech.body, list) and len(mech.body) == 2
        assert isinstance(mech.body[0], ast_nodes.GenStmt)
        assert isinstance(mech.body[1], ast_nodes.CodeBlock)


# ============================================================
# 2. 闭环：matha run 真子进程
# ============================================================

class TestEndToEndPhase19:
    def test_e2e_func_match(self):
        proc = _run_file(_FUNC_MATCH)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["助词", "名词"]

    def test_e2e_mech_combined(self):
        proc = _run_file("module 甲 {\n#1：【段】\n{\n甲 = 6 * 7\n[甲]\n}\n}\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["42"]

    def test_e2e_corpus_grammar(self):
        proc = _run_file(
            (ROOT / "matha/knowledge/linguistics/grammar.matha").read_text(encoding="utf-8")
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == []


# ============================================================
# 3. 边界：阶段 20 收口后一致性轻锁（旧登记分歧已修，防回潮）
# ============================================================

class TestBoundariesPhase19:
    def test_match_no_match_expr_divergence(self):
        # 阶段 20 收口：无匹配双端同错「match 无匹配分支: 9」
        # （旧登记分歧 = host 报错 / VM 表达式位求值 None，已除名）
        src = "输出(match 9 {\n  | 1 => 10\n  | 2 => 20\n})\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: 9" in ho

    def test_match_stmt_no_match_silent_vm(self):
        # 阶段 20 收口：语句位无匹配双端同错，VM 不再静默继续
        # （旧登记分歧 = host 报错 / VM [5] 继续跑，已除名）
        src = "match 9 { | 1 => 输出(10) }\n输出(5)\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: 9" in ho

    def test_match_guard_binding_ref_divergence(self):
        # 阶段 20 收口：守卫先于模式求值（绑定名对守卫不可见）双端同构——
        # 守卫引用绑定名 → 未定义变量 'x'
        # （旧登记分歧 = host 报错 / VM 先绑定输出「大」，已除名）
        src = (
            "输出(match 7 {\n"
            "  | x if x > 5 => \"大\"\n"
            "  | _ => \"小\"\n"
            "})\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "未定义变量 'x'" in ho

    def test_bootstrap_test_v2_compiles_and_c_class_boundary(self):
        # 编译缺口已修（不再「暂不支持的节点 list」）；〔勘误 2026-11 阶段 21b〕
        # C 类符号面真化收口——编译面 use 解析为 CALL 加载模块，裸 VM 面诚实
        # 拒绝边界前移：错误名由首个 use 符号变为加载器内建名（官方门面
        # exec_api 注入加载器后 vm 面跑通全程，专项锁见 test_use_compile_phase21）
        src = (ROOT / "matha/bootstrap_test_v2.matha").read_text(encoding="utf-8")
        vo = _run_raw(src, "vm")
        assert isinstance(vo, str) and "暂不支持的节点" not in vo
        assert "未定义变量 '加载模块'" in vo
        ho = _run_raw(src, "host")
        assert isinstance(ho, list) and ho[0] == 7

    def test_bootstrap_test_compiles_and_c_class_boundary(self):
        # 〔勘误 2026-11 阶段 21b〕同上：裸 VM 诚实拒绝边界前移至加载器名
        src = (ROOT / "matha/bootstrap_test.matha").read_text(encoding="utf-8")
        vo = _run_raw(src, "vm")
        assert isinstance(vo, str) and "暂不支持的节点" not in vo
        assert "未定义变量 '加载模块'" in vo
        ho = _run_raw(src, "host")
        assert isinstance(ho, str) and "不可调用的值" in ho


# ============================================================
# 4. 19c：终端管道态修复——段内出错 catch 清态后重抛，不再泄漏
# ============================================================

_TERM_FILES = ["matha/stdlib.matha", "matha/term_lexer.matha",
               "matha/term_parser.matha", "matha/term_engine.matha"]


def _term_vm():
    comp = Compiler()
    decls = []
    for rel in _TERM_FILES:
        src = (ROOT / rel).read_text(encoding="utf-8")
        decls.extend(parse(src.lstrip("\ufeff")).decls)
    comp.compile_program(ast_nodes.Program(decls=decls))
    vm = VM(comp.mod)
    from src.plugin_api import get_resolver
    vm.domain_resolver = get_resolver()
    vm.run()
    return vm


class TestPipeState19c:
    """term_engine _执行段 try-清态-重抛（matha/term_engine.matha）。

    设计约束（形态探针证实，双端一致）：try 只能落块尾语句位（let 链尾接
    try 双端 ParseError）；try 体块尾若是 let-in 整体被当语句丢弃（值 None），
    清理与返回必须拆语句「let 绑定 + 裸 管道结束() 调用 + 块尾裸值」；
    不用 finally——块尾 let-in 值丢弃（D4）要求清理与返回拆语句，
    catch+throw 形态保值又保清理（阶段 20 已修 VM 重抛路径，形态保留）。"""

    def test_engine_form_value_survives_try_body(self):
        # 引擎形态回归锁：拆语句形态保值（若有人改回 let-in 块尾 → None 即红）
        src = (
            "func f() -> Int = {\n"
            "  try {\n"
            "    let r = 7 in\n"
            "    管道结束()\n"
            "    r\n"
            "  } catch (e) {\n"
            "    管道结束()\n"
            "    throw e\n"
            "  }\n"
            "}\n"
            "输出(f())\n"
        )
        _both(src, [7])

    def test_engine_rethrow_message_fidelity(self):
        # catch (e) { throw e } 原样重抛，消息逐字保真（双端）
        src = (
            "func f() -> Int = {\n"
            "  try {\n"
            "    let r = 错误(\"段内炸\") in\n"
            "    管道结束()\n"
            "    r\n"
            "  } catch (e) {\n"
            "    管道结束()\n"
            "    throw e\n"
            "  }\n"
            "}\n"
            "输出(f())\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert isinstance(ho, str) and "段内炸" in ho
        assert isinstance(vo, str) and "段内炸" in vo

    def test_vm_segment_error_cleans_pipe_state(self):
        # VM 面：段内错误 → catch 清态后重抛；胶水管道态立即复位（不再泄漏）
        from src.kernel import terminal_builtin as tb
        vm = _term_vm()
        tb.pipe_end()
        frame = vm.call("终端解析", "回显 a | 目录 a b")
        with pytest.raises(RuntimeError, match="目录: 至多"):
            vm.call("终端执行", frame, "回显 a | 目录 a b")
        assert tb._pipe_lines is None, "段内出错应立即清管道态（VM 面 catch 清态重抛）"

    def test_host_engine_pipe_still_works_after_form_change(self):
        # 形态改写后正常管道段语义不回归（host 面引擎直调）
        interp = Interpreter()
        assert interp.load_matha_module("终端执行器"), "加载 终端执行器 失败"
        frame = interp._call_func_or_closure(interp.funcs["终端解析"], ["回显 b | 查找 b"])
        r = interp._call_func_or_closure(interp.funcs["终端执行"], [frame, "回显 b | 查找 b"])
        assert r == {"输出": ["b"], "退出": False}


class TestFinallyBoundary19c:
    """try/finally 双端语义（阶段 20 全链同步后一致性锁）。"""

    def test_finally_normal_and_caught_paths_parity(self):
        # 正常路径 / 有 catch 路径：finally 双端一致执行
        _both("try { 输出(1) } finally { 输出(9) }\n输出(2)\n", [1, 9, 2])
        _both("try { 输出(1 / 0) } catch (e) { 输出(7) } finally { 输出(9) }\n", [7, 9])

    def test_try_finally_no_catch_divergence(self):
        # 阶段 20 全链同步：无 catch 重抛路径「先 finally 后重抛」双端同构
        # （旧登记分歧 = host 吞错继续 / VM 重抛跳过 finally，两形态均已除名）
        src = "try { 输出(1 / 0) } finally { 输出(9) }\n输出(2)\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "除零错误" in ho
        # finally 副作用双端都执行，且发生在 输出(2) 之前（异常传播终止）
        ho_interp = Interpreter()
        with pytest.raises(Exception, match="除零错误"):
            ho_interp.run(parse(src))
        assert ho_interp.outputs == [9]
        vm = VM(Compiler().compile_program(parse(src)))
        with pytest.raises(Exception, match="除零错误"):
            vm.run()
        assert vm.outputs == [9]

    # （阶段 20：catch 体再抛先 finally 后重抛、RAISE_MATCH 消息渲染两形态
    # 移入 test_semantic_parity_phase20.py 专项锁，此处不再重复）
