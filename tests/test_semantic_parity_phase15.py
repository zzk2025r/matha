# -*- coding: utf-8 -*-
"""阶段 15 · 双端语义对齐 三锁。

背景：顶层裸表达式语句的 host/VM 发射语义长期分叉——
  D1 顶层 BinaryOp/UnaryOp（如 `1 + 2`、`-3`、`~5`）：host 发射其值，
      VM 编译为「求值 + POP 丢弃」，`matha run` 文件面静默吞输出；
  D2 顶层 IfExpr：host `_exec_decl` 整段静默跳过（代码根本不跑、分支内
      输出/报错全丢），VM 真执行；
  D3 `let x = ... in [...]`：host 发列表首元素（自测块兼容）、VM 丢弃；
  D4 顶层裸 Variable/字面量：host 静默跳过（不求值）、VM 求值（未定义名报错）；
  D5 `===`：host 支持（严格语义）、VM 编译期拒绝。

本轮拍板（2026-11-13）：D1 → VM 补发射（compiler `_compile_top_decl` 显式
BinaryOp/UnaryOp 分支 → OUTPUT）；D2 → host `_exec_decl` 显式 IfExpr 分支
（求值执行、丢弃值）；D3/D4/D5 → 登记不修（怪兼容不扩散 / 语义本身待修）。

【阶段 16 追记（2026-11-13）】D3/D4/D5 已在阶段 16 全部真化对齐（用户拍板
「双端语义第二片 D3/D4/D5」）：D3 host 删死兼容（let-in 列表体求值丢弃，
两端 []）；D4 host 顶层裸表达式求值丢弃（未定义名两端一致报错）+ 词法器
剥 BOM 根修；D5 三端严格值相等 `(type(l) is type(r)) and (l == r)`
（host interp / interp_ic / VM _BINOPS / 编译器 _BIN_OPS / 自举镜像）。
完整三锁见 tests/test_semantic_parity_phase16.py；本文件第三组锁改为
「真化后一致性轻锁」，防止旧分歧形态回潮。

三锁封死：
  1. 对拍：顶层裸算术/一元/绑定后表达式 host ↔ vm 输出逐值一致；
     顶层 IfExpr 副作用（输出分支/else 分支/错误传播）双端一致。
  2. 闭环：`matha run` 文件面（真子进程）顶层裸表达式真吐输出；
     `matha eval` 包装契约回归（不受本轮影响）；既有合法程序零扰动
     （while {} / Output 自动包装 / MechUnit / GlobalIdStmt）。
  3. 真化后一致性：D3 两端 []、D4 两端报未定义名、D5 两端严格值相等——
     阶段 15 旧分歧形态（host 发首元素 / host 静默 / vm 拒绝）不得回潮。
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

from src.interp import Interpreter  # noqa: E402
from src.kernel.errors import MathaUndefinedNameError  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.parser import parse  # noqa: E402


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


def _matha_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "src.matha_main", *args],
        capture_output=True, timeout=120,
    )


# ============================================================
# 1. 对拍：顶层裸表达式 host ↔ vm 输出逐值一致
# ============================================================

class TestParityTopExpressions:
    """D1/D2 修复后双端输出一致。"""

    @pytest.mark.parametrize("src,expected", [
        ("1 + 2", [3]),
        ("5 - 3", [2]),
        ("2 * 3", [6]),
        ("7 / 2", [3.5]),
        ("7 % 3", [1]),
        ("1 < 2", [True]),
        ("2 >= 2", [True]),
        ("1 == 2", [False]),
        ("-3", [-3]),
        ("~5", [-6]),
        ("-(2 + 3)", [-5]),
        ("甲 = 3\n甲 + 1", [4]),
        ("输出(1) + 2", [1, 3]),  # 副作用内建发射 [1] + 语句值发射 [3]
    ])
    def test_top_expr_host_vm_parity(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    def test_top_ifexpr_then_branch_outputs_both(self):
        src = "if 1 > 0 then 输出(9) else 0"
        assert _run_host(src) == [9]
        assert _run_vm(src) == [9]

    def test_top_ifexpr_else_branch_outputs_both(self):
        src = "if 0 > 1 then 输出(9) else 输出(8)"
        assert _run_host(src) == [8]
        assert _run_vm(src) == [8]

    def test_top_ifexpr_value_discarded_not_emitted(self):
        # if 表达式的值本身丢弃（then 分支裸 1+2 不发射），只执行副作用
        src = "if 1 > 0 then\n  1 + 2\nelse\n  0"
        assert _run_host(src) == []
        assert _run_vm(src) == []

    def test_top_ifexpr_error_propagates_both(self):
        src = "if 1 > 0 then 输出(甲) else 0"
        with pytest.raises(MathaUndefinedNameError):
            _run_host(src)
        with pytest.raises(MathaUndefinedNameError):
            _run_vm(src)


# ============================================================
# 2. 闭环：产品面真子进程 + 既有合法程序零扰动
# ============================================================

class TestClosedLoopE2E:
    """matha run / matha eval 真子进程 + 语料零扰动回归。"""

    def _run_file(self, src: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "用例.matha"
            p.write_text(src, encoding="utf-8")
            return _matha_cli("run", str(p))

    def test_matha_run_top_binop_file_emits(self):
        proc = self._run_file("1 + 2\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["3"]

    def test_matha_run_top_ifexpr_file_emits(self):
        proc = self._run_file("if 1 > 0 then 输出(9) else 0\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["9"]

    def test_matha_eval_bare_expr_unchanged(self):
        proc = _matha_cli("eval", "1+2")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["3"]

    def test_matha_eval_output_wrap_contract_unchanged(self):
        # eval 包装 `result = 输出(1+2)\n#1：[result]`：内建发射 [3] + 机械段发射 [3]
        proc = _matha_cli("eval", "输出(1+2)")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["3", "3"]

    def test_while_block_form_unchanged(self):
        src = "甲 = 0\nwhile 甲 < 2 {\n  输出(甲)\n  甲 = 甲 + 1\n}"
        assert _run_host(src) == [0, 1]
        assert _run_vm(src) == [0, 1]

    def test_top_bare_list_auto_wraps_to_output_both(self):
        assert _run_host("[1, 2, 3]") == [[1, 2, 3]]
        assert _run_vm("[1, 2, 3]") == [[1, 2, 3]]

    def test_top_mech_unit_unchanged(self):
        assert _run_host("#1：[1+1]") == [2]
        assert _run_vm("#1：[1+1]") == [2]

    def test_top_integer_parses_as_global_id_both_silent(self):
        # 顶层 `42` 解析为 GlobalIdStmt（结构性标记）：双端均静默
        assert _run_host("42") == []
        assert _run_vm("42") == []


# ============================================================
# 3. 真化后一致性：D3/D4/D5 阶段 15 旧分歧形态不得回潮
#    （完整三锁矩阵在 tests/test_semantic_parity_phase16.py）
# ============================================================

class TestResolvedBoundaries:
    """阶段 15 登记不修的 D3/D4/D5 已于阶段 16 真化——此处锁旧形态不回潮。"""

    def test_d3_letin_listlit_both_discard(self):
        # 旧形态：host 发首元素 [3] / vm []。真化后两端求值丢弃 → []。
        src = "let 甲 = 1 in [甲 + 2]"
        assert _run_host(src) == []
        assert _run_vm(src) == []

    def test_d4_top_bare_variable_both_raise(self):
        # 旧形态：host 静默跳过 / vm 报错。真化后两端一致报未定义名。
        with pytest.raises(MathaUndefinedNameError):
            _run_host("甲")
        with pytest.raises(MathaUndefinedNameError):
            _run_vm("甲")

    def test_d4_top_bare_string_literal_both_silent(self):
        # 求值无副作用、值丢弃 → 双端仍无输出。
        assert _run_host('"字"') == []
        assert _run_vm('"字"') == []

    def test_d5_strict_eq_both_supported(self):
        # 旧形态：vm RuntimeError「不支持的二元运算符 '==='」。真化后双端支持。
        assert _run_host("1 === 1") == [True]
        assert _run_vm("1 === 1") == [True]

    def test_d5_strict_eq_type_sensitive_both(self):
        # 严格值相等：跨数值类型 False（宽松 == 仍 True）。
        assert _run_host("1 === 1.0") == [False]
        assert _run_vm("1 === 1.0") == [False]

    def test_d5_strict_eq_string_both_true(self):
        # 旧形态：同值同型字符串 host === 也 False（身份比较）。
        # 真化后严格值相等 → True。
        assert _run_host('"甲" === "甲"') == [True]
        assert _run_vm('"甲" === "甲"') == [True]
