# -*- coding: utf-8 -*-
"""阶段 16 · 双端语义第二片 D3/D4/D5 真化 三锁。

阶段 15 登记不修的三处分歧，本轮用户拍板全部真化对齐：
  D3 host 删死兼容：let-in 列表体求值丢弃（副作用保留、值不发射）——
      与 VM「求值 + POP」同构。旧形态 host 发列表首元素（自测块兼容）删除；
      lexer.matha 语料因此从「双端 OK 但输出不同」转为双端一致 []。
  D4 host 顶层裸表达式求值丢弃：Variable/IntegerLit/FloatLit/StringLit/
      BoolLit/IsExpr/IndexExpr/SliceExpr/TypeOfExpr 语句走 _eval（值丢弃、
      未定义名报错）——与 VM 兜底同构；通道收发（SendExpr/ChanExpr）有
      副作用，维持静默跳过（KNOWN_ISSUES 登记）。配套根修：词法器剥文件首
      BOM（\ufeff 此前被标识符规则吞成裸未定义变量，D4 后 5 个带 BOM 语料
      文件会误报）。
  D5 三端严格值相等：`===` / `!==` = `(type(l) is type(r)) and (l == r)`
      ——host interp + interp_ic 内联缓存 + VM _BINOPS + 编译器 _BIN_OPS +
      自举镜像 matha/compiler_matha.matha 二元运算表。旧身份语义
      （"甲"==="甲" 因两个独立字面量对象恒 False）废除。

三锁封死：
  1. 对拍：D3 let-in 列表体（值丢弃/副作用保留/表达式位求值）+ D4 裸
     表达式矩阵（字面量/下标/切片/is/未定义名）+ D5 严格相等矩阵
     host ↔ vm 输出逐值一致。
  2. 闭环：`matha run` 文件面（真子进程）D3 丢弃不吐值、D4 未定义名
     退出码 1、D5 严格相等真吐 True；BOM 文件经产品面正常执行。
  3. 边界：`[1] === [1]` 语句位置（阶段 16 登记解析拒绝 → 阶段 18 真化为
     双端发射 True）；三端运算符表同名键存在（vm._BINOPS /
     compiler._BIN_OPS / 自举镜像）；let-in 表达式位求值语义不受影响。
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
from src.lexer import Lexer  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc import compiler as _mbc_compiler  # noqa: E402
from src.mbc import vm as _mbc_vm  # noqa: E402
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
# 1. 对拍：D3/D4/D5 真化后 host ↔ vm 输出逐值一致
# ============================================================

class TestParityD3LetIn:
    """let-in 列表体两端求值丢弃（副作用保留、值不发射）。"""

    @pytest.mark.parametrize("src,expected", [
        # 纯值列表体：两端丢弃，不发射
        ("let 甲 = 1 in [甲 + 2]", []),
        ("let 甲 = 1 in [甲, 甲 + 1]", []),
        # 副作用列表体：输出内建真执行，值本身不发射
        ("let 甲 = 1 in [输出(9)]", [9]),
        ("let 甲 = 1 in [输出(甲), 输出(甲 + 1)]", [1, 2]),
        # 非 let-in 列表表达式不受影响
        ("输出([1, 2, 3])", [[1, 2, 3]]),
        # let-in 表达式位求值语义保持（值参与外层表达式）
        ("输出(let 甲 = 2 in 甲 * 3)", [6]),
        # let-in 体为普通表达式：两端求值丢弃（表达式上下文不发射）
        ("let 甲 = 2 in 甲 * 3", []),
    ])
    def test_letin_body_parity(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    def test_letin_body_side_effect_order_both(self):
        src = "let 甲 = 1 in [输出(7), 输出(8)]"
        assert _run_host(src) == [7, 8]
        assert _run_vm(src) == [7, 8]


class TestParityD4BareExpressions:
    """顶层裸表达式两端求值丢弃；未定义名两端一致报错。"""

    @pytest.mark.parametrize("src", [
        "甲 = 3\n甲",                 # 裸变量（已定义）
        "1.5",                        # 裸浮点字面量
        "true",                       # 裸布尔字面量
        "真",                         # 裸布尔字面量（中文）
        '"字"',                       # 裸字符串字面量
        "甲 = [1, 2]\n甲[0]",         # 裸下标表达式
        "甲 = [1, 2, 3]\n甲[0:2]",    # 裸切片表达式
        "甲 = 3\n甲 is 甲",           # 裸 IsExpr
    ])
    def test_bare_expr_evaluated_discarded_both(self, src):
        assert _run_host(src) == []
        assert _run_vm(src) == []

    @pytest.mark.parametrize("src", [
        "乙",                         # 裸未定义变量
        "甲 = [1]\n乙[0]",            # 裸下标引用未定义名
        "乙 is 甲",                   # 裸 is 引用未定义名
    ])
    def test_bare_expr_undefined_name_both(self, src):
        with pytest.raises(MathaUndefinedNameError):
            _run_host(src)
        with pytest.raises(MathaUndefinedNameError):
            _run_vm(src)

    def test_bare_expr_no_undefined_shielding_by_bom(self):
        # BOM 剥除后不再是「名为 \ufeff 的裸变量」：合法程序不受影响，
        # 真未定义名不再被 BOM 挡住（两端一致报错）。
        bom_src = "\ufeff输出(1)"
        assert _run_host(bom_src) == [1]
        assert _run_vm(bom_src) == [1]
        with pytest.raises(MathaUndefinedNameError):
            _run_host("\ufeff乙")
        with pytest.raises(MathaUndefinedNameError):
            _run_vm("\ufeff乙")

    def test_bom_stripped_before_token_stream(self):
        toks = list(Lexer("\ufeff甲 = 1").tokenize())
        names = [t.type.name for t in toks]
        assert "IDENTIFIER" in names
        # 词法器不再产出名为 \ufeff 的标识符 token
        assert all(t.value != "\ufeff" for t in toks)


class TestParityD5StrictEquality:
    """=== / !== 三端严格值相等：类型完全相同且值相等。"""

    @pytest.mark.parametrize("src,expected", [
        ("1 === 1", [True]),
        ("1 !== 2", [True]),
        ("1 !== 1", [False]),
        ("1 === 2", [False]),
        # 严格：跨数值类型 False（宽松 == 为 True）
        ("1 === 1.0", [False]),
        ("1 !== 1.0", [True]),
        # 旧身份语义的病灶：同值同型独立字面量对象 → True
        ('"甲" === "甲"', [True]),
        ('"甲" !== "甲"', [False]),
        ('"甲" !== "乙"', [True]),
        # 布尔与整数严格分型
        ("true === true", [True]),
        ("1 === true", [False]),
        # 变量绑定值比较
        ("甲 = 1\n乙 = 1\n甲 === 乙", [True]),
        ("甲 = [1, 2]\n乙 = [1, 2]\n甲 === 乙", [True]),
        ("甲 = [1, 2]\n乙 = [1, 3]\n甲 === 乙", [False]),
    ])
    def test_strict_eq_matrix_both(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected


# ============================================================
# 2. 闭环：产品面真子进程
# ============================================================

class TestClosedLoopE2E:
    """matha run 文件面：D3 丢弃不吐值、D4 退出码 1、D5 真吐 True、BOM 正常。"""

    def _run_file(self, src: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "用例.matha"
            p.write_text(src, encoding="utf-8")
            return _matha_cli("run", str(p))

    def _run_file_bytes(self, data: bytes) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "用例.matha"
            p.write_bytes(data)
            return _matha_cli("run", str(p))

    def test_d3_discard_file_silent(self):
        proc = self._run_file("let 甲 = 1 in [甲 + 2]\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == []

    def test_d3_side_effect_file_emits(self):
        proc = self._run_file("let 甲 = 1 in [输出(9)]\n")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["9"]

    def test_d4_undefined_name_file_exit_1(self):
        proc = self._run_file("乙\n")
        assert proc.returncode != 0
        assert "未定义" in proc.stderr.decode("utf-8", errors="replace")

    def test_d5_strict_eq_file_emits_true(self):
        proc = self._run_file('"甲" === "甲"\n')
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["True"]

    def test_bom_file_runs_clean_via_product_face(self):
        proc = self._run_file_bytes("\ufeff输出(1)\n".encode("utf-8"))
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["1"]


# ============================================================
# 3. 边界：解析拒绝 / 三端运算符表 / 镜像同构
# ============================================================

class TestBoundaries:
    """语句位置列表与 === 组合的解析拒绝 + 三端运算符表登记。"""

    def test_list_statement_strict_eq_emit_true(self):
        # 阶段 18 真化（旧锁改锁新形态）：语句位 `[1] === [1]` 此前
        # `[1]` 落入输出行语法、`===` 悬空 ParseError；18d 全中缀回退后
        # 判为列表字面量表达式，D5 严格相等双端发射 True（独立字面量对象
        # 同值同型 → True，非身份语义）。
        assert _run_host("[1] === [1]") == [True]
        assert _run_vm("[1] === [1]") == [True]

    def test_vm_binops_registered(self):
        assert _mbc_vm._BINOPS["=="]("甲", "甲") is True
        assert _mbc_vm._BINOPS["==="]("甲", "甲") is True
        assert _mbc_vm._BINOPS["==="](1, 1.0) is False
        assert _mbc_vm._BINOPS["!=="](1, 1.0) is True

    def test_compiler_bin_ops_mapped(self):
        assert _mbc_compiler._BIN_OPS["==="] == "==="
        assert _mbc_compiler._BIN_OPS["!=="] == "!=="

    def test_selfhost_mirror_table_registered(self):
        # 自举镜像 matha/compiler_matha.matha 二元运算表登记同名键
        # （stage2↔stage3 定点：宿主 _BIN_OPS ↔ 自举 二元运算表）。
        text = (ROOT / "matha" / "compiler_matha.matha").read_bytes().decode("utf-8")
        assert '"===": "==="' in text
        assert '"!==": "!=="' in text
