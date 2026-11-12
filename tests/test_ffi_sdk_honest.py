"""ffi_sdk compile 分派诚实化三锁（阶段 10 补充）。

修复内容（src/plugins/ffi_sdk.py）：
- llvm 分支 import 不存在的 mir_codegen.MathaLLVMGenerator → 恒 ImportError 死分支；
- python/rust/c/cpp/go/java/js 路由到 src/codegen 七个原型后端（rust 输出源码无关
  固定模板；其余六个对常量指令 IndexError——MIRConstInstr operands 为空）；
- compile_and_execute 对非 VM 目标返回 {"compiled": True} 假成功 dict；
- matha_eval 单表达式执行两次。

锁定面：
- 真实面：ast/mir/optimized_mir 真产物；python/c 委托真 mir_codegen 生成器且
  生成代码可真执行（exec 对拍）；execute/matha_eval/文件执行真值；
  run_pipeline 逐目标诚实报告。
- 闭环：compile_and_execute 对 mir 走 MIR VM（纯输出源返回空 = MIR 原型层不表示
  顶层 Output 的登记边界）；其余目标返回编译工件本身。
- 显式拒绝：llvm/rust/cpp/go/java/js NotImplementedError；未知目标 ValueError；
  坏源 ParseError；动态库缺失 load() 如实 False；不再路由 src/codegen 原型后端。
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ast_nodes import Program  # noqa: E402
from src.parser import ParseError  # noqa: E402
from src.plugins.ffi_sdk import (  # noqa: E402
    MathaLibrary,
    compile_source,
    execute_source,
    get_engine,
    matha_eval,
    matha_run_file,
    run_pipeline,
)

_FN_SRC = "func 加一(x) -> Int = (x) => x + 1"


@pytest.fixture
def engine():
    eng = get_engine()
    eng.initialize()
    return eng


class TestRealFaces:
    def test_execute_real_math(self, engine):
        assert execute_source("#1：[1 + 2]") == [3]
        assert execute_source("#1：[6 * 7]") == [42]

    def test_matha_eval_real_value(self, engine):
        assert matha_eval("1 + 2 * 3") == 7
        assert matha_eval("10 / 4") == 2.5

    def test_matha_eval_executes_exactly_once(self, engine, monkeypatch):
        calls = []

        def _fake(source, inputs=None):
            calls.append(source)
            return [42]

        monkeypatch.setattr("src.plugins.ffi_sdk.execute_source", _fake)
        assert matha_eval("anything") == 42
        assert len(calls) == 1  # 修复前：同一表达式执行两次

    def test_compile_ast_mir_optimized_real_types(self, engine):
        from src.mir import MIRProgram

        ast = compile_source(_FN_SRC, "ast")
        assert isinstance(ast, Program)
        mir = compile_source(_FN_SRC, "mir")
        assert isinstance(mir, MIRProgram)
        assert "main" in mir.functions
        opt = compile_source(_FN_SRC, "optimized_mir")
        assert isinstance(opt, MIRProgram)

    def test_compile_python_target_real_exec(self, engine):
        code = compile_source(_FN_SRC, "python")
        assert isinstance(code, str)
        assert "def 加一(" in code
        ns = {}
        exec(compile(code, "<ffi-python>", "exec"), ns)  # noqa: S102
        assert ns["加一"](3) == 4
        assert ns["加一"](10) == 11

    def test_compile_c_target_real(self, engine):
        code = compile_source(_FN_SRC, "c")
        assert isinstance(code, str)
        assert "double 加一(" in code
        assert "return" in code

    def test_matha_run_file_real(self, engine, tmp_path):
        p = tmp_path / "m.matha"
        p.write_text("#1：[6 * 7]\n", encoding="utf-8")
        assert matha_run_file(str(p)) == [42]


class TestClosedLoop:
    def test_compile_and_execute_mir_output_preserved(self, engine):
        # 阶段 11：mir.py 已真化顶层 Output（printf），VM 输出真实值 5.0
        assert engine.compile_and_execute("#1：[2 + 3]", "mir") == [5.0]

    def test_compile_and_execute_python_returns_artifact(self, engine):
        artifact = engine.compile_and_execute(_FN_SRC, "python")
        assert artifact == compile_source(_FN_SRC, "python")

    def test_compile_and_execute_ast_returns_program(self, engine):
        out = engine.compile_and_execute(_FN_SRC, "ast")
        assert isinstance(out, Program)

    def test_run_pipeline_honest_report(self, engine):
        result = run_pipeline(_FN_SRC, ["python", "rust", "c"])
        assert result["targets"]["python"]["success"] is True
        assert result["targets"]["c"]["success"] is True
        assert result["targets"]["rust"]["success"] is False
        assert "未实现" in result["targets"]["rust"]["error"]
        assert result["execution"]["success"] is True


class TestExplicitRejection:
    def test_llvm_rejected(self, engine):
        with pytest.raises(NotImplementedError) as exc:
            compile_source(_FN_SRC, "llvm")
        assert "llvm" in str(exc.value)

    @pytest.mark.parametrize("target", ["rust", "cpp", "go", "java", "js"])
    def test_prototype_targets_rejected(self, engine, target):
        with pytest.raises(NotImplementedError):
            compile_source(_FN_SRC, target)

    def test_unknown_target_valueerror(self, engine):
        with pytest.raises(ValueError) as exc:
            compile_source(_FN_SRC, "wasm")
        assert "不支持的目标" in str(exc.value)

    def test_broken_source_honest_parse_error(self, engine):
        with pytest.raises(ParseError):
            compile_source("x = 1 +", "mir")
        with pytest.raises(ParseError):
            compile_source("func 测试( = (x) => x + 1", "python")

    def test_library_missing_honest_false(self, engine):
        assert MathaLibrary().load("__no_such_matha_lib__.dll") is False

    def test_no_codegen_backend_route(self, engine):
        # 修复前 compile() 路由到 src/codegen 七个原型后端；修复后不再出现
        src_text = inspect.getsource(sys.modules["src.plugins.ffi_sdk"])
        for name in ("python_backend", "rust_backend", "c_backend",
                     "cpp_backend", "go_backend", "java_backend", "js_backend"):
            assert name not in src_text
