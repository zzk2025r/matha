# -*- coding: utf-8 -*-
"""阶段 22c 三锁：语句位裸赋值真化（host ↔ VM ↔ 自举镜像三面）。

修复面（用户拍板 22c，对齐 VM _emit_block 宽容消解边界）：
  1. 宿主 src/interp.py _exec_stmt：语句位 BinaryOp("=") 且左为 Variable →
     求值右侧并绑定（env + _sync_matha_env，首现即声明）。此前按相等比较
     求值 → 读未绑定名报 MathaUndefinedNameError。
  2. 自举镜像同步：matha/interp.matha 与 matha/interp_matha.matha 新增
     语句位赋值或表达式——同一分支形状（运算符="=" 且左为变量 → 绑定，
     已有名更新、未有名新绑定；其余二元语句仍按表达式求值）。
边界（对齐 VM `is_assign and not (last and leave_last)`）：
  - 块尾留值位的 `x = e` 不经赋值分支，仍为相等比较（双端逐字节一致）。
登记边界（现状锁，不修）：
  - src/formulas/dynamics.matha 为公式注册表 DSL（消费方 compile_file，
    tests/test_matha_compiler.py TestRealMathaFile 锁定），解释面运行
    '公式' 未定义变量为登记形态。
  - matha/bootstrap_full_test.matha 宿主面闭包快照作用域边界：镜像 编译
    快照不含后续 let（不折叠），fold 助手经 FuncDef 节点求值 → 宿主面
    首错名 '不折叠'（VM 面 make_module_loader 平铺合并无此边界）。
  - 17_try_block_binding 黄金用例挂 SCOPED_BLOCKS 特性位（manifest
    features），探针裸跑该面不适用——黄金链（39 用例）为权威路径。
"""
import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter, MathaRuntimeError  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402
from src import ast_nodes as ast  # noqa: E402


def _host(prog: str) -> list:
    it = Interpreter(debug=False)
    it.run(parse(prog))
    return list(it.outputs)


def _vm(prog: str) -> list:
    outs, err = exec_api.run_checked(prog, mode="vm")
    assert err is None, repr(err)
    return [repr(o) for o in outs]


# ---------- 对拍：语句位裸赋值 host ↔ VM（四形态） ----------

_ASSIGN_CASES = [
    ("try 块内裸赋值 + 块外可读",
     "try {\n  内部 = 42\n} catch (e) {\n  内部 = 0\n}\n输出(内部)",
     [42]),
    ("lambda 块体裸赋值 + 块尾表达式",
     "f = (x) => { t = x + 1\nt * 2 }\n输出(f(20))",
     [42]),
    ("while 体裸赋值累加",
     "t = 0\nwhile t < 3 { t = t + 1 }\n输出(t)",
     [3]),
    ("if 体裸赋值",
     "x = 0\nif 真 { x = 42 }\n输出(x)",
     [42]),
]


@pytest.mark.parametrize("name,prog,want", _ASSIGN_CASES, ids=[c[0] for c in _ASSIGN_CASES])
def test_bare_assign_host(name, prog, want):
    assert _host(prog) == want, prog


@pytest.mark.parametrize("name,prog,want", _ASSIGN_CASES, ids=[c[0] for c in _ASSIGN_CASES])
def test_bare_assign_vm(name, prog, want):
    assert _vm(prog) == [repr(v) for v in want], prog


def test_reassign_updates_host():
    assert _host("t = 5\nt = t + 1\n输出(t)") == [6]


def test_reassign_updates_vm():
    assert _vm("t = 5\nt = t + 1\n输出(t)") == ["6"]


def test_block_tail_value_stays_comparison_both_faces():
    """边界锁：块尾留值位 `x = e` 仍为相等比较（对齐 VM leave_last 豁免）。"""
    prog = "f = (a, b) => { y = 2\nx = a\nx = y + b }\n输出(f(1, 10))"
    assert _host(prog) == [False]
    assert _vm(prog) == ["False"]


def test_bare_cmp_expr_unchanged():
    """非赋值二元语句（语句位比较表达式）语义不变。"""
    assert _host("输出(3 = 3)") == [True]
    assert _vm("输出(3 = 3)") == ["True"]


# ---------- AST 形状防回潮：lambda 块体仍产 BinaryOp("=")（非 Binding） ----------


def test_parser_emits_binaryop_assign_in_lambda_body_try():
    """lambda 块体内 try/catch 的 `名 = 值` 产 BinaryOp("=")（17_try 形态，
    修复前按比较求值 → 未定义名）；顶层 try 同形态产 Binding（另一路径）。"""
    src = ("func 包(t: Int) -> Int = (t) => {\n"
           "  try { 内部 = t + 1 } catch (e) { 内部 = 0 }\n"
           "  内部\n"
           "}")
    p = parse(src)
    lam = p.decls[0].body
    try_stmt = lam.body.stmts[0]
    assert isinstance(try_stmt, ast.TryStmt)
    n = 0
    for blk in (try_stmt.try_block, try_stmt.catch_block):
        if blk is None:
            continue
        for s in blk.stmts:
            if (isinstance(s, ast.BinaryOp) and s.op == "="
                    and isinstance(s.left, ast.Variable)):
                n += 1
    assert n == 2, n


def test_parser_emits_binaryop_assign_in_lambda_block():
    src = "f = (x) => { t = x + 1\nt * 2 }"
    p = parse(src)
    body = p.decls[0].value.body
    s0 = body.stmts[0]
    assert isinstance(s0, ast.BinaryOp) and s0.op == "=", type(s0).__name__
    assert isinstance(s0.left, ast.Variable) and s0.left.name == "t"


# ---------- 闭环：自举镜像双解释器直驱（与 phase8pre 同一调用约定） ----------

def _mirror_interp():
    """加载 matha/interp.matha（模块名 解释器，预绑定函数 标记区分）。"""
    it = Interpreter()
    assert it.load_matha_module("解释器")
    assert "预绑定函数" in it.modules["解释器"], "应为 interp.matha 版"
    return it


def _mirror_run(it, src):
    toks = it.call("扫描", src, 0, 1, 1, [])
    ast_d = it.call("parse", toks)
    mod = it.modules["解释器"]
    env = it._call_func_or_closure(mod["注册内建"], [[]])
    result, _ = it._call_func_or_closure(mod["执行语句"], [ast_d, env])
    return result


def test_mirror_interp_matha_bare_assign_try():
    it = _mirror_interp()
    assert _mirror_run(it, "try {\n  内部 = 42\n} catch (e) {\n  内部 = 0\n}\n内部") == 42


def test_mirror_interp_matha_bare_assign_rebind():
    it = _mirror_interp()
    assert _mirror_run(it, "t = 5\nt = t + 1\nt") == 6


def test_mirror_interp_matha_bare_cmp_unchanged():
    it = _mirror_interp()
    assert _mirror_run(it, "3 = 3") is True


def _interp_matha_modules():
    """加载自举核心模块（interp_matha.matha 以模块名 解释器 注册）。"""
    import src.matha_bootstrap as mb

    it = mb._get_interp()
    if not getattr(it, "_matha_loaded", False):
        pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
    mod = it.modules["解释器"]
    assert "语句位赋值或表达式" in mod, "镜像 语句位赋值或表达式 缺失"
    assert "预绑定函数" not in mod, "应为 interp_matha.matha 版"
    return it, mod


def _interp_matha_run(it, mod, src):
    lex = it.modules["词法器"]
    syn = it.modules["语法器"]
    toks = it._call_func_or_closure(lex["扫描"], [src, 0, 1, 1, []])
    ast_d = it._call_func_or_closure(syn["parse"], [toks])
    env = it._call_func_or_closure(mod["注册内建"], [[]])
    result, _ = it._call_func_or_closure(mod["执行语句"], [ast_d, env])
    return result


def test_mirror_interp_matha_matha_bare_assign_while():
    it, mod = _interp_matha_modules()
    assert _interp_matha_run(it, mod, "t = 0\nwhile t < 3 { t = t + 1 }\nt") == 3


def test_mirror_interp_matha_matha_bare_assign_if():
    it, mod = _interp_matha_modules()
    assert _interp_matha_run(it, mod, "x = 0\nif 真 { x = 42 }\nx") == 42


def test_mirror_interp_matha_matha_bare_cmp_unchanged():
    it, mod = _interp_matha_modules()
    assert _interp_matha_run(it, mod, "3 = 3") == 1.0


# ---------- 登记边界（现状锁） ----------

def test_formula_dsl_interp_boundary():
    """dynamics.matha 公式注册表 DSL：解释面运行 '公式' 登记边界。"""
    src = (ROOT / "src" / "formulas" / "dynamics.matha").read_text(encoding="utf-8")
    with pytest.raises(MathaRuntimeError, match="公式"):
        Interpreter(debug=False).run(parse(src))


def test_formula_dsl_parse_clean():
    """元数据文本修复后公式注册表可被 host 解析（消费方 compile_file 见
    tests/test_matha_compiler.py::TestRealMathaFile）。"""
    src = (ROOT / "src" / "formulas" / "dynamics.matha").read_text(encoding="utf-8")
    parse(src)


# ---------- 语料修复面 parse-clean 参数化（36 文件防回潮） ----------

_REPAIRED = [
    "matha/examples/04_pipeline.matha",
    "matha/knowledge/chemistry/elements.matha",
    "matha/knowledge/cs/data_structures.matha",
    "matha/knowledge/cs/discrete_math.matha",
    "matha/knowledge/math/calculus.matha",
    "matha/knowledge/math/number_theory.matha",
    "matha/knowledge/math/statistics.matha",
    "matha/resource/apps/education_news.matha",
    "matha/resource/apps/media_math.matha",
    "matha/resource/apps/social_ecommerce.matha",
    "matha/resource/cs/data_structures.matha",
    "matha/resource/cs/os_concepts.matha",
    "matha/resource/embedded/industrial_math.matha",
    "matha/resource/finance/advanced.matha",
    "matha/resource/finance/math.matha",
    "matha/resource/linguistics/basics.matha",
    "matha/resource/logic/advanced_math.matha",
    "matha/resource/math/3d_transform.matha",
    "matha/resource/math/algebra_advanced.matha",
    "matha/resource/os/boot_sector.matha",
    "matha/resource/os/deadlock_sync_math.matha",
    "matha/resource/os/filesystem_math.matha",
    "matha/resource/os/kernel_memory.matha",
    "matha/resource/os/kernel_process.matha",
    "matha/resource/os/memory_math.matha",
    "matha/resource/os/os_concepts_math.matha",
    "matha/resource/os/process_math.matha",
    "matha/resource/os/scheduling_math.matha",
    "matha/resource/platforms/emerging_math.matha",
    "matha/resource/security/crypto_math.matha",
    "matha/resource/statistics/analysis.matha",
    "matha/resource/statistics/probability.matha",
    "matha/resource/tools/utility_math.matha",
    "matha/resource/web/network_math.matha",
    "matha/resource/web/web_math.matha",
    "src/formulas/dynamics.matha",
]


@pytest.mark.parametrize("rel", _REPAIRED)
def test_repaired_corpus_parses_clean(rel):
    """阶段 22c 修复面语料：host 解析零 ParseError（修复前多数在此崩溃）。"""
    src = (ROOT / rel).read_text(encoding="utf-8")
    parse(src)


def test_pipeline_quoted_directive_values():
    """04_pipeline @：指令 value 含点号需引号（裸 source.csv 被急切求值）。"""
    src = (ROOT / "matha" / "examples" / "04_pipeline.matha").read_text(encoding="utf-8")
    it = Interpreter(debug=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        it.run(parse(src))
    assert it.outputs == [0], it.outputs
