# -*- coding: utf-8 -*-
"""阶段 17 · 全面清算 sweep（登记不修清单逐项复核）四项拍板的回归锁。

摸底结论（探针坐实，KNOWN_ISSUES 阶段 17 收官条目）：
  17a 运算符缺口真化：≠/≤/≥ 词法器早已映射（OP_NEQ/OP_LE/OP_GE）、
      stdlib_symbols.matha 早已注册为官方运算符，但三处求值面全拒
      （host「未知运算符」/ VM「不支持的二元运算符」）——语言表面声明
      了不存在的运算符。修复 = 解析器三处 op 取值位点归一化
      （_CMP_ALIASES：≤→<=、≥→>=、≠→!=，_parse_set_expr 集合运算符
      type→op 字典同先例），host interp / interp_ic / MBC VM / compiler /
      自举镜像共用 ASCII op 字符串集；compiler._BIN_OPS 与自举镜像的
      "<>" 死键删除（词法器无 "<>" token，三端求值面也无 "<>"）。
  17b codegen 七语言后端删除：python/rust/c/cpp/go/java/js_backend
      共 2,277 行不可达死代码——唯一工厂入口 codegen() 的 parse_app_spec
      按 kind 拒绝语言类（「未知应用类型」），工厂字典语言条目不可达；
      base.py 懒导入与条目同步清理。
  17c CI/spec 死件清理：matha-ci.yml benchmark 死 job（if:false + 引用
      已删除的 src/vm.py）；matha.spec / matha-cc.spec 三处死 hiddenimports
      （src.tree_sitter_backends、src.domains.hal ×2，模块均不存在）。
  17d 登记勘误（KNOWN_ISSUES 文档面）：Phase 10 的 bootstrap 字节码链 /
      vm_run 暂眠登记已在阶段 11 真修（MathaBytecodeCompiler 真 MBC1
      委托、vm_run 真执行）；「未跟踪 matha/generated/」实为 .gitignore
      忽略目录。

三锁封死：
  1. 对拍：≠/≤/≥ 全形态（输出/let 绑定/链式比较/布尔组合/函数体守卫）
     host ↔ vm 输出逐值一致；ASCII 比较符与集合/布尔/位运算符零回归。
  2. 闭环：`matha run` 文件面（真子进程）≠/≤ 真吐比较结果；codegen
     应用类 kind 真产物、语言类 kind 如实拒绝。
  3. 边界与防回潮：七后端文件缺席 + base.py 文本锁 + 死 hiddenimports /
     死 job 文本锁 + "<>" 键双面（compiler/镜像）缺席；stdlib_symbols
     元数据注册面不动（现由解析器归一化背书）；自举链下标边界维持登记。
"""
from __future__ import annotations

import contextlib
import importlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc import compiler as _mbc_compiler  # noqa: E402
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
# 1. 对拍：≠/≤/≥ 归一化后 host ↔ vm 输出逐值一致
# ============================================================

class TestParityUnicodeComparisonOps:
    """≠/≤/≥ 三件官方运算符真化（此前双端全拒）。"""

    @pytest.mark.parametrize("src,expected", [
        ("输出(1 ≠ 2)", [True]),
        ("输出(1 ≠ 1)", [False]),
        ("输出(3 ≤ 3)", [True]),
        ("输出(4 ≤ 3)", [False]),
        ("输出(3 ≥ 3)", [True]),
        ("输出(2 ≥ 3)", [False]),
    ])
    def test_output_form(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("let 甲 = 5 ≠ 6\n输出(甲)", [True]),
        ("let 乙 = 1 ≤ 2\n输出(乙)", [True]),
        ("let 丙 = 3 ≥ 4\n输出(丙)", [False]),
    ])
    def test_let_binding_form(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("输出(1 ≤ 2 ≤ 3)", [True]),
        ("输出(3 ≥ 2 ≥ 1)", [True]),
        ("输出(2 ≥ 3 ≥ 1)", [False]),
    ])
    def test_chained_comparison(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("输出(2 ≠ 2 and 1 ≤ 2)", [False]),
        ("输出(1 ≠ 1 or 2 ≥ 2)", [True]),
    ])
    def test_boolean_combination(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    def test_function_body_guard_form(self):
        """算术库.matha:85 同型：函数体守卫含 ≠（此前 VM 编译即拒）。"""
        src = ("func 对数(x: Float, base: Float) -> Float = "
               "(x, base) => (x > 0 and base > 0 and base ≠ 1) ? 1.0 : 0.0\n"
               "输出(对数(8, 2))")
        assert _run_host(src) == [1.0]
        assert _run_vm(src) == [1.0]


class TestAsciiAndOtherOpsNoRegression:
    """归一化不得扰动既有运算符（ASCII 比较/集合/布尔/位）。"""

    @pytest.mark.parametrize("src,expected", [
        ("输出(1 != 2)", [True]),
        ("输出(1 <= 2)", [True]),
        ("输出(3 >= 3)", [True]),
        ("输出(1 < 2)", [True]),
        ("输出(2 > 3)", [False]),
        ("输出(1 == 1)", [True]),
    ])
    def test_ascii_comparison(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("输出([1,2] ∪ [3])", [[1, 2, 3]]),
        ("输出([1,2] ∩ [2,3])", [[2]]),
        ("输出([1,2] ⊆ [1,2,3])", [True]),
        ("输出(true ∧ false)", [False]),
        ("输出(true ∨ true)", [True]),
        ("输出(6 ⊕ 3)", [5]),
    ])
    def test_set_bool_xor_ops(self, src, expected):
        assert _run_host(src) == expected
        assert _run_vm(src) == expected


def test_ast_op_strings_normalized():
    """AST 面锁：解析产物 op 字符串为 ASCII 等价形态（≤→<=、≠→!=）。"""
    mod = parse("let 甲 = 1 ≤ 2")
    binding = mod.decls[0]
    assert binding.value.op == "<="
    mod2 = parse("输出(1 ≠ 2)")
    output = mod2.decls[0]
    assert output.arg.op == "!="


# ============================================================
# 2. 闭环：产品面真执行 + codegen 真产物/真拒绝
# ============================================================

class TestClosedLoop:
    @pytest.mark.parametrize("expr,shown", [
        ("1 ≠ 2", "True"),
        ("3 ≤ 3", "True"),
        ("2 ≥ 3", "False"),
    ])
    def test_matha_run_unicode_cmp(self, tmp_path, expr, shown):
        f = tmp_path / "用例.matha"
        f.write_text(f"输出({expr})\n", encoding="utf-8")
        r = _matha_cli("run", str(f))
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        assert shown in r.stdout.decode("utf-8", "replace")

    def test_codegen_app_kinds_still_generate(self, tmp_path):
        from src.codegen import codegen
        r = codegen(["应用", "桌面", "冒烟应用", [["标题", "你好", [], []]]],
                    out_dir=str(tmp_path / "冒烟应用"))
        assert r.成功 is True

    @pytest.mark.parametrize("kind", [
        "C", "Rust", "JavaScript", "TypeScript", "Python", "Go",
        "C++", "Cpp", "Java",
    ])
    def test_codegen_language_kinds_rejected(self, kind):
        from src.codegen import codegen
        r = codegen(["应用", kind, "试", []])
        assert r.成功 is False
        assert "未知应用类型" in r.错误


# ============================================================
# 3. 边界与防回潮：死件缺席锁 + 注册面不动 + 自举链边界
# ============================================================

_SEVEN_BACKENDS = (
    "python_backend", "rust_backend", "c_backend", "cpp_backend",
    "go_backend", "java_backend", "js_backend",
)


class TestDeadArtifactsPurged:
    """17b/17c 死件缺席（防回潮）。"""

    @pytest.mark.parametrize("name", _SEVEN_BACKENDS)
    def test_backend_file_absent(self, name):
        assert not (ROOT / "src" / "codegen" / f"{name}.py").exists()

    def test_import_deleted_backend_fails(self):
        with pytest.raises(ImportError):
            importlib.import_module("src.codegen.python_backend")

    def test_base_py_no_backend_references(self):
        text = (ROOT / "src" / "codegen" / "base.py").read_text(encoding="utf-8")
        for name in _SEVEN_BACKENDS:
            assert name not in text
        for kind in ("C", "Rust", "Python", "Go", "Java"):
            assert f'"{kind}":' not in text

    def test_compiler_binops_no_diamond_key(self):
        assert "<>" not in _mbc_compiler._BIN_OPS
        assert _mbc_compiler._BIN_OPS["!="] == "!="

    def test_mirror_no_diamond_key(self):
        text = (ROOT / "matha" / "compiler_matha.matha").read_bytes().decode(
            "utf-8", errors="replace")
        assert '"<>"' not in text
        assert '"===": "==="' in text and '"!==": "!=="' in text

    def test_ci_workflow_no_benchmark_job(self):
        text = (ROOT / ".github" / "workflows" / "matha-ci.yml").read_text(
            encoding="utf-8")
        assert "Performance Benchmark" not in text
        assert "src.vm" not in text

    def test_spec_no_dead_hiddenimports(self):
        """死条目清零 + 活条目非空洞。

        阶段 43a-1 起 `matha.spec` 的域插件名改由 `src/domains/manifest.json`
        派生（不再手抄字面量），字面 grep 因此失去判据力——本锁改按「真跑一遍
        装配脚本，看派生出的 hiddenimports」判：manifest 读空即红。
        `matha-cc.spec` 未改派，字面检照旧。
        """
        ma = (ROOT / "matha.spec").read_text(encoding="utf-8")
        mcc = (ROOT / "matha-cc.spec").read_text(encoding="utf-8")
        assert "src.tree_sitter_backends" not in ma
        assert "src.domains.hal" not in ma
        assert "src.domains.hal" not in mcc
        # 非空洞检查：cc spec 字面活条目仍在
        assert "src.domains.hardware" in mcc

        class _Art:
            """PyInstaller 产物桩：只补足装配脚本后续读取的属性名。"""

            scripts = pure = binaries = datas = ()

        def _stub(*args, **kwargs):
            return _Art()

        # 单一命名空间：spec 自身 `import json` 与函数定义须共享 globals，
        # 拆成 globals/locals 两本会 NameError（装配脚本按 PyInstaller 语义写）。
        ns: dict = {
            "SPECPATH": str(ROOT), "__file__": str(ROOT / "matha.spec"),
            "Analysis": _stub, "PYZ": _stub, "EXE": _stub, "COLLECT": _stub,
        }
        exec(compile(ma, "matha.spec", "exec"), ns)
        hidden = ns["HIDDEN"]
        assert "src.domains.hardware" in hidden, hidden
        assert "src.domains.registry" in hidden, hidden
        assert "src.domains.hal" not in hidden, hidden

    def test_stdlib_symbols_registration_unchanged(self):
        """元数据注册面不动：≠/≤/≥ 仍注册为官方运算符（现由解析器归一化背书）。"""
        text = (ROOT / "matha" / "stdlib_symbols.matha").read_text(
            encoding="utf-8")
        for ch, name in (("≠", "不等于"), ("≤", "小于等于"), ("≥", "大于等于")):
            assert f'("{ch}", "{name}"' in text


class TestRegisteredBoundariesMaintained:
    """维持登记的良性边界（现状锁，防漂移）。"""

    def test_bootstrap_subscript_statement_read_dual_face(self):
        """语句位下标读 `xs[0]` = 表达式语句求值丢弃——自举/宿主双面静默一致。

        8a 旧登记「自举链语句位下标求值报错（主解析器 only 口径）」随 29b
        语句位下标面真化退役：boot 面不再抛错，与宿主面（run_checked 静默
        无错）同形；下标赋值 a[i]=v 由 29b STORE_SUBSCRIPT 真化（见 29b 锁）。
        """
        try:
            import src.matha_bootstrap as mb
            interp = mb._get_interp()
        except Exception:
            pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
        if not getattr(interp, "_matha_loaded", False):
            pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
        toks = interp.call("扫描", "let xs = [1, 2]\nxs[0]", 0, 1, 1, [])
        ast_d = interp.call("parse", toks)
        mod = interp.modules["解释器"]
        env = interp._call_func_or_closure(mod["注册内建"], [[]])
        r_env = interp._call_func_or_closure(mod["执行语句"], [ast_d, env])
        assert isinstance(r_env, tuple) and len(r_env) == 2  # 静默求值丢弃，不抛错
        from src.kernel import exec_api
        outs, err = exec_api.run_checked("let xs = [1, 2]\nxs[0]")
        assert err is None and outs == [], (outs, err)
