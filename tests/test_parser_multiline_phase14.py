# -*- coding: utf-8 -*-
"""阶段 14 · 解析器踩界真化 三锁（KNOWN_ISSUES 12c 登记三项：行首运算符续行 /
then 独立成行 / 调用参数跨行）。

背景：Matha 词法器按行发 NEWLINE（括号内不抑制），解析器中缀环只在当前 token
即运算符时进环——NEWLINE 在前即退出。由此三项踩界：① 行首运算符总是错误；
② `then` 行首总是错误（`else` 行首却已合法——不对称）；③ func/lambda 声明参数
括号内换行总是错误（调用参数早已合法）。

阶段 14 真化（主解析器 only，bootstrap matha/lexer·parser.matha 维持登记边界）：
  14a 词法器续行：行首 infix-only 运算符（+ * / % < > <= >= == !=）或行尾
      算术/比较运算符的紧邻换行 → 不发 INDENT/DEDENT/NEWLINE（并入上一逻辑行）。
      **排除 `-`**（行首 `-` 今天是一元负号语句）与 **`and`/`or`**（行首 `and`
      今天是互递归函数声明延续——func 体换行 + and 新行；行尾 and/or 本就合法）。
  14b 解析器：then/else 允许独立成行（三处 if 站点，与 else 行首现状对齐）。
  14c 解析器：声明参数/lambda 参数括号内跨行（LPAREN 后、逗号后、RPAREN 前）+
      -> 类型与 = 之间换行（E3）+ let rec 右括号与 -> 之间换行。

本轮三锁封死回退：
  1. 对拍：14a 续行 token 流与单行源逐 token 一致（续行零 token 残留）；
     求值用例 host ↔ vm 输出一致。
  2. 闭环：续行/then 行首/参数跨行全形态真实执行值（手算对拍）。
  3. 显式拒绝/边界：`-`、`and`、`or` 行首不续行（既有语义锁）；空行/注释行
     断开续行；`{` 块形式 if 换行仍拒绝；`=>` 独立成行仍拒绝；lambda 体参数
     带类型标注仍拒绝（既有边界）；互递归 and 声明回归锁。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.lexer import Lexer  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.parser import ParseError, parse  # noqa: E402


def _run_host(src: str) -> list:
    interp = Interpreter()
    interp.run(parse(src))
    return list(interp.outputs)


def _run_vm(src: str) -> list:
    comp = Compiler()
    comp.compile_program(parse(src))
    vm = VM(comp.mod)
    vm.run()
    return list(vm.outputs)


def _tokens(src: str) -> list:
    return [(t.type.name, t.value) for t in Lexer(src).tokenize()]


# ============================================================
# 1. 对拍（续行 token 流零残留 + host ↔ vm 输出一致）
# ============================================================

class TestParity:
    """14a 续行与单行源 token 流一致；求值用例双端输出一致。"""

    @pytest.mark.parametrize("multi,joined", [
        ("x = 1\n+ 2", "x = 1 + 2"),
        ("x = 1\n* 2", "x = 1 * 2"),
        ("x = 1\n/ 2", "x = 1 / 2"),
        ("x = 1 +\n2", "x = 1 + 2"),
        ("x = 1 <\n2", "x = 1 < 2"),
        ("x = 1\n!= 2", "x = 1 != 2"),
    ])
    def test_lead_trail_tokens_equal_joined_source(self, multi, joined):
        assert _tokens(multi) == _tokens(joined)

    @pytest.mark.parametrize("src,expect", [
        ("x = 1\n+ 2\n输出(x)", [3]),
        ("x = 1 *\n2\n输出(x)", [2]),
        ("x = 1\n< 2\n输出(x)", [True]),
        ("输出(1 <=\n2)", [True]),
        ("输出(if 1 > 0\nthen 11\nelse 22)", [11]),
        ("func 加(\n  a: Int,\n  b: Int\n) -> Int = a + b\n输出(加(3, 4))", [7]),
        ("func 加(a: Int,\n  b: Int) -> Int = a + b\n输出(加(3, 4))", [7]),
        ("func 加(a: Int) -> Int\n= a + 1\n输出(加(4))", [5]),
        ("let rec 阶(\n  n: Int\n) -> Int = if n < 2 then 1 else n * 阶(n - 1)\n输出(阶(5))", [120]),
        ("let 双 = (\n  x: Int\n) => x * 2\n输出(双(21))", [42]),
    ])
    def test_host_vm_outputs_equal(self, src, expect):
        assert _run_host(src) == expect
        assert _run_vm(src) == expect


# ============================================================
# 2. 闭环（全形态真实执行值）
# ============================================================

class TestClosedLoop:
    """续行 / then 行首 / 参数跨行全形态手算对拍。"""

    # ---- 14a 行首续行 ----
    def test_lead_ops_all_continue(self):
        assert _run_host("输出(1\n+ 2)") == [3]
        assert _run_host("输出(6\n* 7)") == [42]
        assert _run_host("输出(9\n/ 3)") == [3]
        assert _run_host("输出(7\n% 4)") == [3]
        assert _run_host("输出(1\n< 2)") == [True]
        assert _run_host("输出(2\n> 1)") == [True]
        assert _run_host("输出(2\n>= 2)") == [True]
        assert _run_host("输出(1\n== 1)") == [True]
        assert _run_host("输出(1\n!= 2)") == [True]

    # ---- 14a 行尾续行 ----
    def test_trail_ops_all_continue(self):
        assert _run_host("输出(1 +\n2)") == [3]
        assert _run_host("输出(6 *\n7)") == [42]
        assert _run_host("输出(9 /\n3)") == [3]
        assert _run_host("输出(1 <\n2)") == [True]
        assert _run_host("输出(1 <=\n2)") == [True]
        assert _run_host("输出(2 >\n1)") == [True]
        assert _run_host("输出(2 >=\n2)") == [True]
        assert _run_host("输出(1 ==\n1)") == [True]
        assert _run_host("输出(1 !=\n2)") == [True]

    # ---- 14b then/else 独立成行 ----
    def test_then_else_line_start_full_matrix(self):
        assert _run_host("输出(if 1 > 0\nthen 11\nelse 22)") == [11]
        assert _run_host("输出(if 1 > 0 then 11\nelse 22)") == [11]
        assert _run_host("x = if 1 > 0\nthen 1 else 0\n输出(x)") == [1]
        assert _run_host("输出(if 1 > 0\nthen if 2 > 1\nthen 10\nelse 20\nelse 0)") == [10]

    def test_then_line_start_inside_call_args(self):
        src = ("func 挑(c: Bool, a: Int, b: Int) -> Int = if c\nthen a\nelse b\n"
               "输出(挑(1 > 0, 7, 9))\n输出(挑(1 < 0, 7, 9))")
        assert _run_host(src) == [7, 9]
        assert _run_vm(src) == [7, 9]

    # ---- 14c 参数跨行 ----
    def test_func_decl_params_multiline_full(self):
        src = "func 加(\n  a: Int,\n  b: Int\n) -> Int = a + b\n输出(加(3, 4))"
        assert _run_host(src) == [7]
        assert _run_vm(src) == [7]

    def test_let_rec_decl_params_multiline_full(self):
        src = ("let rec 阶(\n  n: Int\n) -> Int = if n < 2 then 1 else n * 阶(n - 1)\n"
               "输出(阶(5))")
        assert _run_host(src) == [120]
        assert _run_vm(src) == [120]

    def test_let_rec_rparen_to_arrow_newline(self):
        src = "let rec 阶(n: Int)\n-> Int = if n < 2 then 1 else n * 阶(n - 1)\n输出(阶(4))"
        assert _run_host(src) == [24]

    def test_let_rec_lam_params_multiline(self):
        src = "let rec 加(a: Int) -> Int = (\n  b\n) => b * 2\n输出(加(4))"
        assert _run_host(src) == [8]
        assert _run_vm(src) == [8]

    def test_standalone_lambda_params_multiline(self):
        assert _run_host("let 双 = (\n  x: Int\n) => x * 2\n输出(双(21))") == [42]
        assert _run_host("let 和 = (a: Int,\n  b: Int) => a + b\n输出(和(3, 4))") == [7]

    def test_func_lam_body_params_multiline(self):
        src = "func 加(a: Int) -> Int = (\n  b\n) => b * 2\n输出(加(2))"
        assert _run_host(src) == [4]
        assert _run_vm(src) == [4]

    def test_empty_params_newline(self):
        src = "func 五(\n) -> Int = 5\n输出(五())"
        assert _run_host(src) == [5]
        assert _run_vm(src) == [5]

    def test_e3_assign_next_line(self):
        assert _run_host("func 加(a: Int) -> Int\n= a + 1\n输出(加(4))") == [5]

    def test_call_args_newline_regression(self):
        src = "func 加(a: Int, b: Int) -> Int = a + b\n输出(加(1,\n  2))"
        assert _run_host(src) == [3]
        assert _run_vm(src) == [3]

    # ---- and 互递归（14a 排除 and 行首续行的语义锁） ----
    def test_mutual_recursion_and_decl_regression(self):
        src = ("func 偶(n: Int) -> Int = if n == 0 then 0 else 奇(n - 1)\n"
               "and 奇(n: Int) -> Int = if n == 0 then 1 else 偶(n - 1)\n"
               "输出(偶(6))\n输出(偶(5))")
        assert _run_host(src) == [0, 1]
        assert _run_vm(src) == [0, 1]

    def test_and_decl_params_multiline(self):
        src = ("func 加(a: Int) -> Int = a\n"
               "and 倍(\n  b: Int\n) -> Int = b * 2\n"
               "输出(倍(5))")
        assert _run_host(src) == [10]
        assert _run_vm(src) == [10]


# ============================================================
# 3. 显式拒绝 / 边界（既有语义锁）
# ============================================================

class TestRejectionAndBoundaries:
    """排除项与保守边界显式锁死。"""

    def test_minus_not_lead_continuation_token_lock(self):
        # 行首 `-` 保持一元负号语句语义：NEWLINE 必须保留（对照 `+` 被抑制）
        assert [t.type.name for t in Lexer("x = 1\n- 2").tokenize()].count("NEWLINE") == 1
        assert [t.type.name for t in Lexer("x = 1\n+ 2").tokenize()].count("NEWLINE") == 0

    def test_and_not_lead_continuation_binding(self):
        # 行首 and 不是续行：绑定行首 and 落到语句层 → and-func-def 期望函数名
        with pytest.raises(ParseError):
            parse("x = 1\nand 2\nx")

    def test_or_not_lead_continuation_binding(self):
        # 行首 or 不是续行：不并入布尔表达式（并入则 x = 1 or 2 合法 → 仅 2 decls；
        # 实际 or 落到语句层 → 3 decls 且运行期未定义名错误）
        prog = parse("x = 1\nor 2\nx")
        assert len(prog.decls) == 3
        with pytest.raises(Exception):
            _run_host("x = 1\nor 2\nx")

    def test_blank_line_breaks_continuation(self):
        with pytest.raises(ParseError):
            parse("x = 1 +\n\n2")

    def test_comment_line_breaks_continuation(self):
        with pytest.raises(ParseError):
            parse("x = 1 +\n(* 注释 *)\n2")

    def test_block_form_if_newline_brace_still_rejected(self):
        with pytest.raises(ParseError):
            parse("if 1 > 0\n{ 输出(1) }")

    def test_fatarrow_own_line_still_rejected(self):
        with pytest.raises(ParseError):
            parse("let 双 = (x: Int)\n=> x * 2")

    def test_typed_lam_params_still_rejected(self):
        # 既有边界：lambda 体参数不支持类型标注（单行同错）
        with pytest.raises(ParseError):
            parse("func 加(a: Int) -> Int = (b: Int) => b + a")
        with pytest.raises(ParseError):
            parse("func 加(a: Int) -> Int = (\n  b: Int\n) => b + a")

    def test_indented_continuation_keeps_logical_line_level(self):
        # 续行缩进不参与缩进栈：续行不发 INDENT（顶层 0 个），
        # 后续边界相对原层级计算，块内续行同样可行
        src_top = "x = 1\n    + 2\n输出(x)"
        assert [t.type.name for t in Lexer(src_top).tokenize()].count("INDENT") == 0
        assert _run_host(src_top) == [3]
        src_block = "if 1 > 0 {\n  输出(1\n    + 2)\n}"
        assert _run_host(src_block) == [3]
