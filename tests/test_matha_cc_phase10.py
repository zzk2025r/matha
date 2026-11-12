# -*- coding: utf-8 -*-
"""阶段 10 · matha_cc 委托化/诚实化 + 死代码清除 三锁。

背景：src/compiler/matha_cc.py 曾自带独立 legacy 词法/语法器 + 三地址 MathaIR +
"LLVM IR" 文本生成器——全部真实语言形态（func f(x) -> Int、#1：[expr]）一律
SyntaxError；唯一"编译成功"的产物是把三地址码贴进 LLVM 模板得到的无效 IR 文本；
bootstrap.MathaSelfCompiler 借道 hasattr 误判静默产出空字节码；
MathaSystem 的 matha_cc 版 _init_compiler 被同名后定义遮蔽（matha_compile /
compiler 从未绑定，matha2c / compile / eval 编译回退全部 AttributeError 死路）；
matha_cc_cli 与 matha_main 的 compile/run/llvm/optimize 把文件路径当源码文本
传给编译器；unified_parser.MathaParser 注入 token 写错字段（_tokens/_pos），
parse 恒空 Program；零消费死代码 src/quantum.py（2 量子门物理错误）已删除。

本轮三锁封死回退：
  1. 对拍：matha_cc.MathaLexer / MathaParser 与主实现 token/AST 逐项一致；
     matha_compile 摘要与 unified_parser 及 parse+compile_program 独立复算
     一致；MathaSelfCompiler 产物 = 真实 MBC1 字节码（反序列化往返 +
     serialize_mbc 与 write_mbc 文件布局逐字节一致）。
  2. 闭环：matha_run / MathaCompiler.run 真实执行（7/30/120 三源）；CLI 子进程
     compile/run/test/build 全真产物（.mbc 可被 read_mbc 读回）；MathaSystem /
     MathaEngine 门面真编译（含同名遮蔽回归锁）；mir_converter 三向转换走通。
  3. 显式拒绝：matha_to_llvm / MathaLLVMGenerator.generate / llvm_hybrid /
     bootstrap llvm 目标一律 NotImplementedError；坏输入 ParseError 如实抛出；
     MathaBackend 无 IR 可编 → ToolchainUnavailable；src/quantum.py 文件不存在
     且 import 拒绝；legacy MathaIR/MathaToken/AST 类已清除、src.MathaIR 导出移除。
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.compiler.matha_cc import (  # noqa: E402
    MathaBackend,
    MathaCompiler,
    MathaFrontend,
    MathaLexer,
    MathaLLVMGenerator,
    MathaParser,
    matha_compile,
    matha_run,
    matha_to_llvm,
)
from src.mbc.compiler import compile_program  # noqa: E402
from src.mbc.serial import deserialize_mbc, read_mbc, serialize_mbc, write_mbc  # noqa: E402
from src.parser import ParseError, parse  # noqa: E402
from src.plugins.toolchain_llvm import ToolchainUnavailable  # noqa: E402
from src.unified_parser import matha_compile as unified_matha_compile  # noqa: E402

_FUNC_SRC = "func 加倍(x) -> Int = (x) => x * 2"
_MIXED_SRC = "func 加倍(x) -> Int = (x) => x * 2\nlet a = 加倍(21)\n#1：[a]"


# ============================================================
# 1. 对拍（封死假解析/假计数/假字节码）
# ============================================================

class TestParityWithMainImplementation:
    """matha_cc 兼容层与主实现逐项一致。"""

    def test_lexer_tokens_identical_to_main_lexer(self):
        for src in ("x = 1 + 2", _FUNC_SRC, "#1：[1+1]", "result = sin(3.14)"):
            cc = [(t.type.name, t.value) for t in MathaLexer(src).tokenize()]
            main = [(t.type.name, t.value) for t in parse_tokens(src)]
            assert cc == main, src

    def test_parser_ast_shape_identical_to_main_parser(self):
        cc_prog = MathaParser(MathaLexer(_MIXED_SRC).tokenize()).parse()
        main_prog = parse(_MIXED_SRC)
        assert [type(d).__name__ for d in cc_prog.decls] == \
               [type(d).__name__ for d in main_prog.decls]
        fd_cc, fd_main = cc_prog.decls[0], main_prog.decls[0]
        assert fd_cc.name == fd_main.name == "加倍"

    def test_parser_token_injection_actually_parses(self):
        # 回归锁：unified/matha_cc 历史写法误设 _tokens/_pos（主 Parser 真实
        # 字段是 tokens/pos），注入静默失效 → parse 恒空 Program。
        prog = MathaParser(MathaLexer(_FUNC_SRC).tokenize()).parse()
        assert len(prog.decls) == 1
        assert type(prog.decls[0]).__name__ == "FuncDef"

    def test_matha_compile_matches_unified_and_independent_recompute(self):
        summary = matha_compile(_FUNC_SRC, "t")
        prog = parse(_FUNC_SRC)
        mod = compile_program(prog)
        expected = (f"# Compiled {len(prog.decls)} declarations to t: "
                    f"{len(mod.functions)} functions, {len(mod.main_code)} ops")
        assert summary == expected
        assert summary == "# Compiled 1 declarations to t: 1 functions, 1 ops"
        assert summary == unified_matha_compile(_FUNC_SRC, "t")

    def test_self_compiler_produces_real_mbc1_bytecode(self):
        from src.bootstrap import MathaSelfCompiler
        sc = MathaSelfCompiler()
        data = sc.compile(_MIXED_SRC)
        assert data[:4] == b"MBC1"
        mod = deserialize_mbc(data)
        direct = compile_program(parse(_MIXED_SRC))
        assert set(mod.functions.keys()) == set(direct.functions.keys())
        for name, fn in direct.functions.items():
            got = mod.functions[name]
            assert (got.arity, got.nlocals, got.params, got.code) == \
                   (fn.arity, fn.nlocals, fn.params, fn.code), name
        assert mod.main_code == direct.main_code
        assert mod.constants == direct.constants

    def test_serialize_mbc_matches_write_mbc_file_layout(self, tmp_path):
        mod = compile_program(parse(_FUNC_SRC))
        target = tmp_path / "m.mbc"
        write_mbc(mod, str(target))
        assert target.read_bytes() == serialize_mbc(mod)
        assert read_mbc(str(target)).main_code == mod.main_code


def parse_tokens(source: str):
    from src.lexer import Lexer
    return list(Lexer(source).tokenize())


# ============================================================
# 2. 闭环（真实执行 / 真实产物 / 门面接线）
# ============================================================

class TestClosedLoop:
    """委托后的编译/执行链端到端真实可用。"""

    def test_matha_run_real_execution(self):
        result = matha_run("x = 1 + 2\n#1：[x]")
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["3"]
        assert result.args == ["x = 1 + 2\n#1：[x]"]

    def test_matha_run_curried_call(self):
        result = matha_run("add = (a, b) => a + b\nresult = add(10)(20)\n#1：[result]")
        assert result.stdout.splitlines() == ["30"]

    def test_matha_compiler_run_recursive_func(self):
        src = ("func fact(n) -> Int = (n) => if n <= 1 then 1 else n * fact(n-1)\n"
               "result = fact(5)\n#1：[result]")
        result = MathaCompiler().run(src)
        assert result.returncode == 0
        assert result.stdout.splitlines() == ["120"]

    def test_matha_compiler_compile_source_real_summary_and_stats(self):
        compiler = MathaCompiler()
        summary = compiler.compile_source("x = 1 + 1", "out")
        assert summary == "# Compiled 1 declarations to out: 0 functions, 3 ops"
        assert compiler.stats["compile_count"] == 1

    def test_matha_compile_optimize_param_accepted(self):
        assert matha_compile("x = 1 + 1", "o", optimize=False) == \
               matha_compile("x = 1 + 1", "o", optimize=True)

    def test_frontend_accepts_source_and_program(self):
        ast_from_source = MathaFrontend().compile(_FUNC_SRC)
        ast_from_program = MathaFrontend().compile(ast_from_source)
        assert type(ast_from_source).__name__ == type(ast_from_program).__name__ == "Program"

    def test_cli_compile_and_run_subprocess(self, tmp_path):
        f = tmp_path / "t.matha"
        f.write_text("result = 1 + 2 * 3\n#1：[result]\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "-m", "src.compiler.matha_cc_cli", "compile", str(f),
             "-o", str(tmp_path / "out")],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=120)
        assert r.returncode == 0
        assert "# Compiled 2 declarations" in r.stdout

        r = subprocess.run(
            [sys.executable, "-m", "src.compiler.matha_cc_cli", "run", str(f)],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=120)
        assert r.returncode == 0
        assert "7" in r.stdout.splitlines()

    def test_cli_test_subcommand_all_pass(self):
        r = subprocess.run(
            [sys.executable, "-m", "src.compiler.matha_cc_cli", "test"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=180)
        assert r.returncode == 0
        assert "4 通过, 0 失败" in r.stdout

    def test_cli_build_produces_readable_mbc(self, tmp_path):
        f = tmp_path / "t.matha"
        f.write_text("x = 41 + 1\n#1：[x]\n", encoding="utf-8")
        target = tmp_path / "pkg.mbc"
        r = subprocess.run(
            [sys.executable, "-m", "src.matha_main", "build", str(f), "-o", str(target)],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=120)
        assert r.returncode == 0, r.stderr
        assert target.exists() and target.read_bytes()[:4] == b"MBC1"
        assert len(read_mbc(str(target)).main_code) > 0

    def test_matha_system_facade_real_compiler_after_initialize(self):
        # 同名遮蔽回归锁：matha_cc 版 _init_compiler 曾被 compiler_backend 版
        # 覆盖，matha_compile/compiler 从未绑定。
        from src.matha_system import MathaSystem
        s = MathaSystem()
        s.initialize()
        assert s.matha_compile("func 加倍(x) -> Int = (x) => x * 2", "o") == \
               "# Compiled 1 declarations to o: 1 functions, 1 ops"
        assert s.compiler_class is not None  # 后端链同样初始化
        assert "compile" in s.interpreter.builtins  # 互调通道真实接线
        assert s.eval("1 + 2 * 3") in (7, "7")
        assert "include" in s.matha2c("result = sin(3.14)")

    def test_matha_system_targeted_compiler_init(self):
        from src.matha_system import MathaSystem
        s = MathaSystem()
        s._init_compiler()
        assert s.matha_compile("x = 1", "o").startswith("# Compiled ")

    def test_matha_engine_facade_real_compiler(self):
        from src.matha_engine import MathaEngine
        e = MathaEngine()
        e.initialize()
        assert e.matha_compile("x = 5", "o").startswith("# Compiled ")
        assert e.eval("2 * 21") in (42, "42")

    def test_mir_converter_matha_to_c(self):
        from src.mir_converter import MathaConverter, MathaToMIRGenerator
        c = MathaConverter().convert("x = 1 + 2\n#1：[x]", "matha", "c")
        assert "main" in c
        text = MathaToMIRGenerator().generate_from_matha("x = 1 + 2")
        assert "函数" in text

    def test_bootstrap_targets_c_and_python_nontrivial(self):
        from src.bootstrap import matha_bootstrap_compile
        src = "result = sin(3.14) * cos(1.57)\n#1：[result]"
        assert "main" in matha_bootstrap_compile(src, target="c")
        assert len(matha_bootstrap_compile(src, target="python")) > 50


# ============================================================
# 3. 显式拒绝（封死假 IR / 假产物 / 死代码复活）
# ============================================================

class TestExplicitRejection:
    """假产物不再产出，坏输入如实报错。"""

    def test_matha_to_llvm_rejected(self):
        with pytest.raises(NotImplementedError):
            matha_to_llvm("x = 1 + 2")

    def test_llvm_generator_rejected(self):
        gen = MathaLLVMGenerator("m")
        with pytest.raises(NotImplementedError):
            gen.generate(None)

    def test_llvm_hybrid_delegates_rejection(self):
        from src.compiler.llvm_hybrid import matha_to_llvm as hybrid_to_llvm
        with pytest.raises(NotImplementedError):
            hybrid_to_llvm("x = 1")

    def test_bootstrap_llvm_target_rejected(self):
        from src.bootstrap import matha_bootstrap_compile
        with pytest.raises(NotImplementedError):
            matha_bootstrap_compile("x = 1", target="llvm")

    def test_cli_llvm_subcommand_honest_failure(self, tmp_path):
        f = tmp_path / "t.matha"
        f.write_text("x = 1\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "-m", "src.compiler.matha_cc_cli", "llvm", str(f)],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=120)
        assert r.returncode == 1
        assert "LLVM 生成失败" in r.stderr

    def test_broken_source_honest_parse_error(self):
        with pytest.raises(ParseError):
            matha_compile("x = 1 +")
        with pytest.raises(ParseError):
            matha_run("x = 1 +")

    def test_backend_without_ir_honest_toolchain_error(self):
        # 工具缺失 → ToolchainUnavailable（装指引）；工具在但 IR 无效 → 同样
        # ToolchainUnavailable（llc/clang 均编不过）。两环境语义一致。
        with pytest.raises(ToolchainUnavailable):
            MathaBackend().compile("this is not llvm ir", "reject_out")

    def test_dead_code_src_quantum_absent(self):
        assert not (ROOT / "src" / "quantum.py").exists()
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("src.quantum")

    def test_legacy_ir_and_ast_classes_purged(self):
        m = importlib.import_module("src.compiler.matha_cc")
        for name in ("MathaIR", "MathaToken", "Binding", "FuncDef", "BinaryOp",
                     "UnaryOp", "FuncApp", "Lambda", "IfExpr", "WhileStmt",
                     "ForStmt", "Literal", "Variable", "ListLiteral",
                     "DictLiteral", "TupleExpr", "Output"):
            assert not hasattr(m, name), name

    def test_src_matha_ir_export_removed(self):
        import src as pkg
        with pytest.raises(AttributeError):
            getattr(pkg, "MathaIR")

    def test_matha_main_compile_rejects_missing_file(self, tmp_path):
        r = subprocess.run(
            [sys.executable, "-m", "src.matha_main", "compile",
             str(tmp_path / "nope.matha"), "-o", str(tmp_path / "out")],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT), timeout=120)
        assert r.returncode == 1
        assert "编译失败" in r.stderr
