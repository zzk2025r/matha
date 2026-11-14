# -*- coding: utf-8 -*-
"""阶段 18 · 双端语义第三片 + 通道收发 + [1]===[1] 真化 三锁。

阶段 16 登记残留存量分歧的 10 文件，根因归约为两件 + 两件独立缺口，本轮全修：
  18a 双执行根修：host 解释器 _exec_with_deferreds 删 ModuleDecl 递归——
      模块内部声明此前被「_exec_decl(ModuleDecl) 内层循环 + 递归」双跑
      （parser.matha 自测块 [1,1]、test_compile/test_math 值 ×2）；
      VM 编译模块内声明仅一次，host 对齐单次执行。
  18b use 加载泄漏根修：load_matha_module 的嵌套 self.run 以
      _loading_module 标志跳过被载模块自测块（#：{ }/#N：{ } MechUnit，
      matha_bootstrap.py:59 同款边界）——VM 编译 use 模块从不执行其自测
      代码（compiler_matha/nl_* [1,1]/[]、interp.matha [1,1,...] 泄漏）。
  18c 通道收发 host 真化：_eval 新增 ChanExpr（降级三键 dict
      {"缓冲"/"容量"/"关闭"}）与 SendExpr（append 产新列表 + 写回具名
      变量 + 求值 true，无名通道写回退化）——与 VM ChanExpr/SendExpr
      逐语义同构；顶层裸收发求值丢弃（副作用保留、不发射）。
  18d [1]===[1] 语句位真化：全中缀回退——顶层命令单元与表达式位的
      `[...]` 配对 `]` 后紧跟中缀运算符 → 列表字面量（同逻辑行限定）；
      右值位补齐 ===/!==/and/or/&&/||/??/?/^ 等缺失前驱。`=`、`<-`、
      `>>`、`|` 刻意排除，跨行与自测块内维持既有 ParseError 形态。

三锁封死：
  1. 对拍：模块内自测块单次执行、use 加载零泄漏、通道收发矩阵、
     语句位 `[...] 中缀` 矩阵 host ↔ vm 输出逐值一致；语料面
     parser.matha/test_compile/compiler_matha 双端一致。
  2. 闭环：matha run 真子进程 `[1] === [1]` 吐 True、通道缓冲复核、
     use 语法器 不泄漏自测输出。
  3. 边界：`[1] = [1]`、自测块内 `[1] === [1]`、跨行 `===`、`|` 管道
     位维持 ParseError；发送列表值双端一致；语句位二元两侧均为
     ListLiteral（RHS 不再落入输出行 Output）。
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


def _run_file(src: str, name: str = "用例.matha") -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / name
        p.write_text(src, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "src.matha_main", "run", str(p)],
            capture_output=True, timeout=120,
        )


def _both(src: str, expected: list) -> None:
    assert _run_host(src) == expected, f"host: {_run_host(src)}"
    assert _run_vm(src) == expected, f"vm: {_run_vm(src)}"


# ============================================================
# 1. 对拍：18a/18b/18c/18d 真化后 host ↔ vm 输出逐值一致
# ============================================================

class TestParity18aSingleExec:
    """模块内自测块单次执行（内层循环唯一执行路径，删递归）。"""

    def test_module_inner_selftest_once(self):
        _both("module 甲 {\n  甲 = 1\n  #：{ [9] }\n}\n", [9])

    def test_top_level_selftest_unchanged(self):
        # 顶层（模块外）自测块本就单次执行，不受 18a 影响
        _both("#：{ [9] }\n", [9])

    def test_module_inner_binding_once(self):
        # 模块内绑定亦单次执行：自增副作用 ×1（此前 ×2）
        _both(
            "module 甲 {\n  计 = 0\n  计 = 计 + 1\n  #：{ 输出(计) }\n}\n",
            [1],
        )

    def test_corpus_parser_matha_single_emission(self):
        src = (ROOT / "matha" / "parser.matha").read_text(encoding="utf-8")
        assert _run_host(src) == [1]
        assert _run_vm(src) == [1]

    def test_corpus_test_compile_single_emission(self):
        src = (ROOT / "matha" / "runtime" / "test_compile.matha").read_text(encoding="utf-8")
        assert _run_host(src) == _run_vm(src)
        assert len(_run_host(src)) == 3


class TestParity18bLoadSkip:
    """use 加载跳过被载模块自测块（_loading_module 标志）。"""

    def test_use_module_no_selftest_leak(self):
        _both("use 语法器\n输出(7)\n", [7])

    def test_load_api_no_selftest_outputs(self):
        interp = Interpreter(debug=False)
        with contextlib.redirect_stdout(io.StringIO()):
            assert interp.load_matha_module("语法器") is True
        assert interp.outputs == []
        assert "语法器" in interp.modules

    def test_nested_use_flag_restored(self):
        # 载入完成后标志恢复 False：主文件自身自测块仍执行
        src = "use 语法器\n#：{ 输出(42) }\n"
        _both(src, [42])

    def test_corpus_compiler_matha_no_leak(self):
        src = (ROOT / "matha" / "compiler_matha.matha").read_text(encoding="utf-8")
        assert _run_host(src) == []
        assert _run_vm(src) == []


class TestParity18cChannel:
    """通道收发 host 真化（镜像 VM ChanExpr/SendExpr 语义）。"""

    def test_chan_dict_shape_capacity(self):
        _both('甲 = chan Int\n输出(甲["容量"])', [0])

    def test_chan_dict_shape_closed(self):
        _both('输出((chan Int)["关闭"])', [False])

    def test_send_evaluates_true(self):
        _both("乙 = (chan Int) <- 5\n输出(乙)", [True])

    def test_send_named_writeback_buffer(self):
        _both('甲 = chan Int\n甲 <- 5\n甲 <- 7\n输出(甲["缓冲"])', [[5, 7]])

    def test_send_unnamed_no_writeback(self):
        _both("输出((chan Int) <- 5)", [True])

    def test_bare_top_level_send_silent(self):
        # 顶层裸发送：执行副作用（缓冲追加+写回）但不发射，与 VM POP 同构
        _both('甲 = chan Int\n甲 <- 5', [])

    def test_bare_top_level_chan_silent(self):
        _both("chan Int", [])

    def test_send_list_value(self):
        _both('甲 = chan Int\n甲 <- [1]\n输出(甲["缓冲"])', [[[1]]])


class TestParity18dStatementInfix:
    """语句位 `[...]` 后跟中缀 → 列表字面量表达式（全中缀回退）。"""

    @pytest.mark.parametrize("src,expected", [
        ("[1] === [1]", [True]),
        ("[1] !== [2]", [True]),
        ("[1] + [2]", [[1, 2]]),
        ("[1] ∪ [2]", [[1, 2]]),
    ])
    def test_statement_infix_parity(self, src, expected):
        _both(src, expected)

    def test_expression_position_unchanged(self):
        _both("输出([1] === [1])", [True])

    def test_variable_position_unchanged(self):
        _both("甲 = [1]\n输出(甲 === [1])", [True])

    def test_rhs_is_list_literal_not_output(self):
        # 两侧同为 ListLiteral：RHS 此前落入输出行 Output（VM 表达式位
        # 对其 DUP+OUTPUT 发射而 host 静默），全中缀回退后对称
        node = parse("[1] === [1]").decls[-1]
        assert isinstance(node, ast_nodes.BinaryOp)
        assert node.op == "==="
        assert isinstance(node.left, ast_nodes.ListLiteral)
        assert isinstance(node.right, ast_nodes.ListLiteral)


# ============================================================
# 2. 闭环：matha run 文件面（真子进程）
# ============================================================

class TestEndToEndPhase18:
    """matha run 文件面：语句位 === 吐 True、通道缓冲、use 零泄漏。"""

    def test_strict_eq_file_emits_true(self):
        proc = _run_file("[1] === [1]\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["True"]

    def test_strict_neq_file_emits_true(self):
        proc = _run_file("[1] !== [2]\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["True"]

    def test_channel_buffer_file(self):
        proc = _run_file('甲 = chan Int\n甲 <- 5\n输出(甲["缓冲"])\n')
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["[5]"]

    def test_use_module_file_no_leak(self):
        proc = _run_file("use 语法器\n输出(7)\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["7"]

    def test_output_row_unchanged_file(self):
        # 输出行语法不受影响：`[1]` 仍为输出
        proc = _run_file("[1]\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["1"]


# ============================================================
# 3. 边界：刻意排除面 / 块面 / 跨行 / 防回潮
# ============================================================

class TestBoundariesPhase18:
    """`=`、`<-`、`|` 排除；自测块内与跨行维持 ParseError。"""

    def test_assign_still_parse_error(self):
        # `=` 是关系相等：`[1] = [1]` 刻意不回退，保持诚实 ParseError
        with pytest.raises(ParseError):
            parse("[1] = [1]")

    def test_selftest_block_face_still_parse_error(self):
        # 自测块（生成代码面）语句位 `[...]` 维持输出行语法，=== 悬空拒绝
        with pytest.raises(ParseError):
            parse("#：{ [1] === [1] }")

    def test_multiline_still_parse_error(self):
        # 同逻辑行限定：`]` 与中缀跨行不回退
        with pytest.raises(ParseError):
            parse("[1]\n=== [1]")

    def test_pipe_still_parse_error(self):
        with pytest.raises(ParseError):
            parse("[1] | 输出")

    def test_send_still_output_row(self):
        # `<-` 排除：`甲 <- [1]` 的 `[1]` 为发送值表达式（双端一致）
        _both('甲 = chan Int\n甲 <- [1]\n输出(甲["缓冲"])', [[[1]]])

    def test_phase16_corpus_locks_hold(self):
        # 阶段 16 文件锁重写后形态：lexer.matha（let-in 自测）双端零杂散
        src = (ROOT / "matha" / "lexer.matha").read_text(encoding="utf-8")
        assert _run_host(src) == []
        assert _run_vm(src) == []
