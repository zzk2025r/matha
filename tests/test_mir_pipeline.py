# -*- coding: utf-8 -*-
"""MIR 优化与代码生成管道的一致性测试。"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import mir, mir_codegen, mir_opt
from src.mir import (
    MIRArithInstr,
    MIRCallInstr,
    MIRCondBranchInstr,
    MIRConstInstr,
    MIRFunction,
    MIRInstrType,
    MIRLabelInstr,
    MIRProgram,
    MIRReturnInstr,
    MIRStoreInstr,
)
from src.parser import parse


def _compile(source: str):
    return mir.generate_mir(parse(source))


def _temps(instr) -> list[str]:
    return [
        str(op).lstrip("%")
        for op in getattr(instr, "operands", []) or []
        if str(op).lstrip("%").startswith("t")
    ]


def test_function_body_is_emitted_in_its_own_mir_function():
    program = _compile("func f(x: Int) -> Int = (x) => x * 2 + 1\n输出(f(3))")

    assert set(program.functions) == {"main", "f"}
    f = program.functions["f"]
    main = program.functions["main"]

    assert f.params == ["x"]
    assert f.param_types == ["double"]
    assert f.return_type == "double"

    defs = set(f.params)
    for instr in f.instructions:
        for temp in _temps(instr):
            assert temp in defs, f"函数 f 引用了未在 f 内定义的临时量 {temp}"
        if instr.result and not str(instr.result).startswith("t"):
            defs.add(str(instr.result))
        elif instr.result:
            defs.add(str(instr.result).lstrip("%"))

    assert any(isinstance(instr, MIRArithInstr) for instr in f.instructions)
    assert any(isinstance(instr, MIRReturnInstr) for instr in f.instructions)

    calls = [instr for instr in main.instructions if isinstance(instr, MIRCallInstr)]
    assert any(instr.func_name == "f" for instr in calls)
    assert any(instr.c_func == "printf" for instr in calls)
    assert not any(isinstance(instr, MIRArithInstr) for instr in main.instructions)


def test_call_fields_are_materialized_for_optimizer_and_backend():
    program = _compile("输出(sqrt(9))")
    calls = [
        instr
        for instr in program.functions["main"].instructions
        if isinstance(instr, MIRCallInstr)
    ]

    sqrt_call = next(instr for instr in calls if instr.func_name == "sqrt")
    assert sqrt_call.c_func == "sqrt"
    assert sqrt_call.lib == "math"
    assert sqrt_call.metadata == {}

    imports = program.functions["main"].c_imports
    assert any(getattr(item, "c_func", "") == "sqrt" for item in imports)


def test_block_tail_value_is_emitted_as_output():
    program = _compile("#：{1 + 2}")
    code = mir_codegen.MIRToCGenerator().generate(program)
    assert 'printf("%g\\n", 3.0);' in code


def test_if_expression_keeps_control_flow_fields_and_labels():
    program = _compile("#：{1 > 0 ? 2 : 3}")
    main = program.functions["main"]
    branch = next(
        instr for instr in main.instructions if isinstance(instr, MIRCondBranchInstr)
    )

    assert branch.cond
    assert branch.true_label
    assert branch.false_label
    assert branch.true_label != branch.false_label

    labels = {
        instr.label
        for instr in main.instructions
        if isinstance(instr, MIRLabelInstr)
    }
    assert branch.true_label in labels
    assert branch.false_label in labels

    cfg = mir_opt.MIRFunctionCFG(main)
    cfg.build()
    assert branch.true_label in cfg.label_to_block
    assert branch.false_label in cfg.label_to_block

    code = mir_codegen.MIRToCGenerator().generate(program)
    assert "if (" in code
    assert "goto" in code
    assert branch.true_label in code
    assert branch.false_label in code


def test_default_pipeline_does_not_remove_control_flow():
    program = _compile("#：{1 > 0 ? 2 : 3}")
    pipeline = mir_opt.MIRPassPipeline.create_default()
    optimized = pipeline.run(program)
    snapshot = pipeline._snapshot(optimized)

    assert any(
        isinstance(instr, MIRCondBranchInstr)
        for instr in optimized.functions["main"].instructions
    )
    assert pipeline.run(optimized) is optimized
    assert pipeline._snapshot(optimized) == snapshot


def test_c_backend_declares_each_temporary_once():
    program = _compile("func f(x: Int) -> Int = (x) => x * 2 + 1\n输出(f(3))")
    code = mir_codegen.MIRToCGenerator().generate(program)
    declared = re.findall(r"^\s*double (t\d+);$", code, flags=re.MULTILINE)

    assert declared
    assert len(declared) == len(set(declared))
    assert not re.search(r"^\s*double t\d+ =", code, flags=re.MULTILINE)


def test_python_backend_uses_function_local_values():
    program = _compile("func f(x: Int) -> Int = (x) => x * 2 + 1")
    code = mir_codegen.MIRToPythonGenerator().generate(program)
    namespace = {}
    exec(compile(code, "<mir-python>", "exec"), namespace)  # noqa: S102

    assert namespace["f"](3) == 7.0


def test_dce_keeps_store_and_return_semantics():
    program = MIRProgram()
    func = MIRFunction(name="f", params=[], return_type="double")
    func.instructions = [
        MIRStoreInstr(
            result="",
            instr_type=MIRInstrType.STORE,
            operands=["%t0"],
            target="answer",
        ),
        MIRConstInstr(result="%t0", instr_type=MIRInstrType.ADD, value=42.0),
        MIRReturnInstr(
            result="%r",
            instr_type=MIRInstrType.RETURN,
            operands=["%t0"],
            value="%t0",
        ),
    ]
    program.functions["f"] = func

    optimized = mir_opt.MIRPassPipeline().run(program, [mir_opt.MathaDCEPass()])
    instructions = optimized.functions["f"].instructions
    assert any(isinstance(instr, MIRStoreInstr) for instr in instructions)
    assert any(isinstance(instr, MIRReturnInstr) for instr in instructions)


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is required")
def test_generated_c_compiles_and_runs(tmp_path):
    program = _compile("func f(x: Int) -> Int = (x) => x * 2 + 1\n输出(f(3))")
    source = tmp_path / "mir_pipeline.c"
    executable = tmp_path / "mir_pipeline.exe"
    source.write_text(mir_codegen.MIRToCGenerator().generate(program), encoding="utf-8")

    build = subprocess.run(
        ["gcc", "-O2", str(source), "-o", str(executable), "-lm"],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run([str(executable)], capture_output=True, text=True)
    assert run.stdout.strip() == "7"
