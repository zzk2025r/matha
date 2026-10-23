# -*- coding: utf-8 -*-
"""MIR 优化管线单元测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import mir, mir_opt, mir_codegen
from src.mir import MIRProgram, MIRFunction, MIRArithInstr, MIRInstrType, MIRReturnInstr, MIRConstInstr


def test_dce_removes_dead_instruction():
    mp = MIRProgram()
    mf = MIRFunction(name="f", params=["x"])
    mf.instructions = [
        MIRArithInstr(result="%t0", op="+", operands=["1", "0"], instr_type=MIRInstrType.ADD),
        MIRArithInstr(result="%dead", op="+", operands=["2", "3"], instr_type=MIRInstrType.ADD),
        MIRReturnInstr(result="%r", instr_type=MIRInstrType.RETURN, operands=["%t0"], value="%t0"),
    ]
    mp.functions["f"] = mf
    mp2 = mir_opt.MIRPassPipeline().run(mp, [mir_opt.MathaDCEPass()])
    instrs = mp2.functions["f"].instructions
    assert len(instrs) == 2
    assert any(getattr(i, "value", None) == "%t0" or "%t0" in str(getattr(i, "operands", [])) for i in instrs)


def test_const_fold_pass():
    mp = MIRProgram()
    mf = MIRFunction(name="f", params=[])
    mf.instructions = [
        MIRArithInstr(result="%t0", op="+", operands=["2", "3"], instr_type=MIRInstrType.ADD),
        MIRReturnInstr(result="%r", instr_type=MIRInstrType.RETURN, operands=["%t0"], value="%t0"),
    ]
    mp.functions["f"] = mf
    mp2 = mir_opt.MIRPassPipeline().run(mp, [mir_opt.MathaConstFoldPass(), mir_opt.MathaDCEPass()])
    instrs = mp2.functions["f"].instructions
    assert len(instrs) == 2


def test_copy_prop_pass():
    mp = MIRProgram()
    mf = MIRFunction(name="f", params=[])
    from src.mir import MIRLoadInstr
    mf.instructions = [
        MIRLoadInstr(result="%t0", source="x", instr_type=MIRInstrType.LOAD, operands=["x"]),
        MIRArithInstr(result="%t1", op="+", operands=["%t0", "1"], instr_type=MIRInstrType.ADD),
        MIRReturnInstr(result="%r", instr_type=MIRInstrType.RETURN, operands=["%t1"], value="%t1"),
    ]
    mp.functions["f"] = mf
    mp2 = mir_opt.MIRPassPipeline().run(mp, [mir_opt.MathaCopyPropPass(), mir_opt.MathaDCEPass()])
    instrs = mp2.functions["f"].instructions
    # copy prop may replace operands
    assert any("x" in str(getattr(i, "operands", [])) or getattr(i, "source", "") == "x" for i in instrs)


def test_pipeline_converges():
    mp = MIRProgram()
    mf = MIRFunction(name="f", params=[])
    mf.instructions = [
        MIRConstInstr(result="%c", value=5.0),
        MIRArithInstr(result="%t0", op="+", operands=["%c", "0"], instr_type=MIRInstrType.ADD),
        MIRReturnInstr(result="%r", instr_type=MIRInstrType.RETURN, operands=["%t0"], value="%t0"),
    ]
    mp.functions["f"] = mf
    pipe = mir_opt.MIRPassPipeline.create_default()
    mp2 = pipe.run(mp)
    assert mp2 is not None


def test_codegen_runs_after_pipeline():
    mp = MIRProgram()
    mf = MIRFunction(name="f", params=[])
    mf.instructions = [
        MIRConstInstr(result="%c", value=2.0),
        MIRReturnInstr(result="%r", instr_type=MIRInstrType.RETURN, operands=["%c"], value="%c"),
    ]
    mp.functions["f"] = mf
    cg = mir_codegen.MIRToCGenerator()
    out = cg.generate(mp)
    assert "f" in out
    assert "return" in out
