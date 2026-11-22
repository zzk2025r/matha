# -*- coding: utf-8 -*-
"""阶段 37 语言面清尾批锁（32-② + 31-③ 退役 + 32-⑩ + 36-① + 36-② 真化）。

37a 陈旧登记退役（协议一致锁——三面已收敛，无行为改动）：
  32-② 空括号 () 解析：三面早已统一零参调用约定——() 降糖 IntegerLit(0)，
    f() = f(0)，表达式位 () 即 0（32-② 登记「解析歧义」陈旧——后续阶段
    工作已使三面同判，协议一致锁防漂移）。
  31-③ VM 非容器切片异常载体：三面早已统一 MathaRuntimeError 同文案
    「切片操作不支持: int[1:2]」（31f 真化后编译面 raise_rt 同源）——
    登记「VM 原生异常形态」陈旧；31f 旧锁 vm 面仅 err-not-None，本档补齐
    三面文案+类型同判（31f 旧锁同步加强）。

37b 块尾 Binding 值模型收尾（36-② 退役 + 同族顺手真修）：
  interp_matha 绑定求值let 无体臂 (v, env)→(null, env) + interp.matha
  同形（36-② 登记形态 { let x = 5 }）；表达式位块（求值程序/求值 程序
  臂）尾值 _块尾值 映射（绑定/let绑定/let元组绑定尾不回传值——宿主
  _BLOCK_TAIL_STMT_NODES 头三族；函数定义臂 36b 已 null；程序位顶层
  run_ast → 执行语句保持「程序值 = 尾表达式值」约定不映射——
  phase8pre gapfix 程序值锁同源）——同族顺手真修：有体 let 尾
  { let x = 10 in x * 12 } 与裸赋值尾 { x = 5 } 此前 mb/VM² 回传值 vs
  vm/hi None。四形态三面 + VM² 同判。

37c 链式 let rec 互递归真化（32-⑩ 退役）：
  interp.py 表达式位 LetBinding 链头收集 body 链 rec 名建注册表压栈
  （_rec_chain）逐名预绑占位符，成员复用未填占位（_ref 未填守卫——
  32e 勘误保留：弹栈后同名恒新建、跨函数在途占位不串线）；未填占位
  复用块/程序入口预注册物（_exec_with_deferreds / CodeBlock 臂预注册
  沿 body 链整链——37c 前 body is None 条件漏带体链，先定义闭包快照缺
  后定义名）；interp_matha/interp.matha 预绑链占位镜像 + 占位复用守卫。
  三面 + VM² 同判 [0]；登记边界：嵌套链同名成员 env 槽被内层占位覆写
  （注册表弹栈不还原 env），单调用形态三面同判锁防漂移。

37d 字典自然键真化（36-① 退役）：
  compiler.py _literal_key IntegerLit/FloatLit/BoolLit → 原值入常量池
  （此前 IntegerLit 字符串化致 d[2] vm null / d["2"] vm 反向命中）+
  parser.matha 花括号种类 整数/浮点/布尔首 token 冒号前瞻 → 字典（宿主
  _parse_brace_dispatch 同判；此前 mb/VM² 误析集合）；boot 编译器
  _发射键 非变量键发射表达式既有自然值零改动、boot 解释器 _字典键 既有
  求值零改动、native dict_get val_eq 扫描随字节码自动同判。
  int/float/bool/str 键 + d["2"] 反向 null 三面 + VM² 同判。

37x 附带发现登记锁（登记不修）：
  vm/hi 输出尾块值 host 内部分歧：编译面语句尾 PUSH_NULL vs 解释面输出
  通道规则（_eval_block_value 尾语句执行后 outputs[-1]）——
  { let y = 7 in 输出(y) } vm None vs hi 7（输出尾经输出通道回值）；
  boot 解释面已随 37b 尾值映射收敛 vm 面（boot 编译面 _是语句类型
  输出 PUSH_NULL 自洽），登记防漂移。
  mb 面集合构造求值未知表达式类型（boot 求值无 集合构造 臂——vm/hi
  正常枚举 vs mb MathaRuntimeError；既有边界，登记防漂移）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src.kernel import exec_api
from src.kernel.errors import MathaRuntimeError
from src import matha_bootstrap
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _hi_interp(src):
    try:
        outs, _ = host_interp.interpret(src)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _boot_interp(src):
    """自举解释器面（matha_bootstrap：lexer/parser/stdlib/interp_matha 链）。

    strict=True：执行面异常如实上抛；解析面错误以输出行呈现（32 约定）。"""
    try:
        outs, _ = matha_bootstrap.interpret(src, strict=True)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _three_faces(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == want, (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == want, (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == want, (tag, "mb", mb, mb_err)


def _three_err(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is not None and isinstance(err, MathaRuntimeError) \
        and want in str(err), (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and isinstance(hi_err, MathaRuntimeError) \
        and want in str(hi_err), (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and isinstance(mb_err, MathaRuntimeError) \
        and want in str(mb_err), (tag, "mb", mb, mb_err)


@pytest.fixture(scope="module")
def bootvm():
    """VM² 解释器面：宿主编译 interp_matha 链 → VM 运行（29d 同构）。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


def _boot_run(bootvm, src):
    bootvm.call("输出清空")
    toks = bootvm.call("扫描", src, 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    for nm, ns in bootvm._chain_nss.items():
        env0 = bootvm.call("绑定环境", env0, nm, ns)
    r, env1 = bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照")), r, env1


# ============================================================
# 37a 陈旧登记退役：32-② 空括号协议一致锁
# ============================================================

def test_37a_zero_arg_call_three_faces():
    """零参调用 f() 三面同判 [1]：() 降糖 IntegerLit(0)（32-② 退役——
    三面早已统一零参调用约定，协议一致锁防漂移）。"""
    _three_faces("zero_arg_call", "let f = (x) => x + 1 in 输出(f())", [1])


def test_37a_empty_parens_literal_three_faces():
    """表达式位 () 三面同判 [0]（32-② 退役——() 即 IntegerLit(0)）。"""
    _three_faces("empty_parens", "输出(())", [0])


def test_37a_zero_arg_vm2(bootvm):
    """VM² 面 () 零参约定同判（boot 解析器/解释器镜像）。"""
    outs, _, _ = _boot_run(bootvm, "let f = (x) => x + 1 in 输出(f())")
    assert outs == [1], outs
    outs, _, _ = _boot_run(bootvm, "输出(())")
    assert outs == [0], outs


# ============================================================
# 37a 陈旧登记退役：31-③ 非容器切片异常载体协议一致锁
# ============================================================

def test_37a_slice_noncontainer_three_faces():
    """非容器切片三面 MathaRuntimeError 同文案（31-③ 退役——31f 真化后
    编译面 raise_rt 与解释面同源；本档文案+类型双判）。"""
    _three_err("slice_int", "输出(5[1:2])", "切片操作不支持: int[1:2]")
    _three_err("slice_none", "输出(null[0:1])", "切片操作不支持: NoneType[0:1]")


# ============================================================
# 37b 块尾 Binding 值模型收尾（36-② 退役 + 同族顺手真修）
# ============================================================

_BLK_SHAPES = [
    ("blk_let", "let r = { let x = 5 } in 输出(r)", [None]),
    ("blk_letrec", "let r = { let rec f = (k) => k } in 输出(r)", [None]),
    ("blk_single", "let r = { let x = 10 in x * 12 } in 输出(r)", [None]),
    ("blk_assign", "let r = { x = 5 } in 输出(r)", [None]),
]


@pytest.mark.parametrize("tag,src,want", _BLK_SHAPES, ids=[c[0] for c in _BLK_SHAPES])
def test_37b_blk_tail_shapes_three_faces(tag, src, want):
    """块尾 Binding 族四形态三面同判 [None]（36-② 退役 + 同族顺手真修：
    无体 let / 无体 let rec / 有体 let / 裸赋值——宿主
    _BLOCK_TAIL_STMT_NODES 头三族面）。"""
    _three_faces(tag, src, want)


def test_37b_blk_tail_vm2(bootvm):
    """块尾 Binding 族 VM² 同判（interp.matha 绑定求值let + _块尾值 镜像）。"""
    for tag, src, want in _BLK_SHAPES:
        outs, _, _ = _boot_run(bootvm, src)
        assert outs == want, (tag, outs)


def test_37b_blk_value_neutrals_three_faces():
    """块值中性回归：尾表达式块三面 + 有体尾表达式值 + 语句位 let rec
    无输出中性（输出尾块值分歧另见 37x 登记锁）。"""
    _three_faces("blk_tail_expr",
                 "let r = { let x = 3 in x + 1 } in 输出(r)", [None])
    _three_faces("blk_tail_two_stmt",
                 "let r = { let x = 3\n  x + 1 } in 输出(r)", [4])
    _three_faces("stmt_letrec_tail", "let rec f = (k) => k\n输出(1)", [1])


# ============================================================
# 37c 链式 let rec 互递归真化（32-⑩ 退役）
# ============================================================

_CHAIN_MUTUAL = ("let rec a = (n) => if n = 0 then 0 else b(n - 1) in "
                 "let rec b = (n) => if n = 0 then 1 else a(n - 1) in "
                 "输出(a(4))")
_CHAIN_MUTUAL_REV = ("let rec a = (n) => if n = 0 then 0 else b(n - 1) in "
                     "let rec b = (n) => if n = 0 then 1 else a(n - 1) in "
                     "输出(b(4))")
_CHAIN_THREE = ("let rec a = (n) => b(n - 1) in let rec b = (n) => c(n - 1) in "
                "let rec c = (n) => if n <= 0 then 9 else a(n - 1) in 输出(a(5))")
_CROSS_NONREC = ("let rec a = (n) => if n = 0 then 0 else b(n - 1) in "
                 "let x = 5 in "
                 "let rec b = (n) => if n = 0 then 1 else a(n - 1) in 输出(a(4))")


def test_37c_chained_mutual_three_faces():
    """链式 let rec 互递归三面同判（32-⑩ 退役——hi/mb 未定义变量 'b'
    退役；链头收集整链 rec 名预绑，成员复用未填占位）。"""
    _three_faces("chain_mutual", _CHAIN_MUTUAL, [0])
    _three_faces("chain_mutual_rev", _CHAIN_MUTUAL_REV, [1])
    _three_faces("chain_three", _CHAIN_THREE, [9])
    _three_faces("cross_nonrec", _CROSS_NONREC, [0])


def test_37c_chained_mutual_vm2(bootvm):
    """链式 let rec 互递归 VM² 同判（预绑链占位 镜像）。"""
    for tag, src, want in (("mutual", _CHAIN_MUTUAL, [0]),
                           ("rev", _CHAIN_MUTUAL_REV, [1]),
                           ("three", _CHAIN_THREE, [9]),
                           ("cross_nonrec", _CROSS_NONREC, [0])):
        outs, _, _ = _boot_run(bootvm, src)
        assert outs == want, (tag, outs)


def test_37c_rec_regressions_three_faces():
    """37c 回归锁：单 rec / 链式非 rec / 块序列同名链独立 / 嵌套异名值 /
    FuncDef 互递归 / rec 值位急切调用——32e 盒协议与勘误不扰动。"""
    _three_faces("single_rec",
                 "let rec f = (k) => if k = 0 then 0 else f(k - 1) in 输出(f(3))",
                 [0])
    _three_faces("chained_nonrec", "let x = 5 in let y = x + 1 in 输出(y)", [6])
    _three_faces("seq_blocks",
                 "let r1 = (let rec f = (k) => k + 1 in f(1)) in "
                 "let r2 = (let rec f = (k) => k * 3 in f(2)) in 输出([r1, r2])",
                 [[2, 6]])
    _three_faces("nested_value",
                 "let rec f = (k) => (let rec g = (j) => j + 100 in g(k)) in 输出(f(1))",
                 [101])
    _three_faces("letrec_func_mix",
                 "func g(n) = if n = 0 then 7 else h(n - 1)\n"
                 "func h(n) = if n = 0 then 8 else g(n - 1)\n输出(g(2))",
                 [7])
    _three_faces("eager_call_chain",
                 "func id(x) = x\nlet r = (let rec f = id(5) in f) in 输出(r)",
                 [5])


def test_37c_nested_same_name_three_faces():
    """嵌套链同名成员（登记边界：内层 env 槽覆写外层——注册表弹栈不还原
    env；单调用形态三面同判 [101] 锁防漂移）。"""
    _three_faces("nested_same_name",
                 "let rec f = (k) => (let rec f = (j) => j + 100 in f(k)) in 输出(f(1))",
                 [101])


# ============================================================
# 37d 字典自然键真化（36-① 退役）
# ============================================================

def test_37d_dict_natural_keys_three_faces():
    """字典 int/float/bool/str 自然键三面同判（36-① 退役——vm 字符串化
    退役、mb/VM² 集合误析退役）；d["2"] 反向缺键 null 四面同判。"""
    _three_faces("dict_int", 'let d = {2: "v"} in 输出(d[2])', ["v"])
    _three_faces("dict_float", 'let d = {3.5: "f"} in 输出(d[3.5])', ["f"])
    _three_faces("dict_bool", 'let d = {真: "b"} in 输出(d[真])', ["b"])
    _three_faces("dict_mixed",
                 'let d = {2: "v", 3.5: "f", 真: "b", "s": "str"} in '
                 '输出([d[2], d[3.5], d[真], d["s"], d["2"]])',
                 [["v", "f", "b", "str", None]])
    _three_faces("dict_int_str_miss", 'let d = {2: "v"} in 输出(d["2"])', [None])


def test_37d_dict_natural_keys_vm2(bootvm):
    """字典自然键 VM² 同判（parser.matha 花括号种类 冒号前瞻镜像）。"""
    outs, _, _ = _boot_run(bootvm, 'let d = {2: "v"} in 输出(d[2])')
    assert outs == ["v"], outs
    outs, _, _ = _boot_run(bootvm, 'let d = {2: "v"} in 输出(d["2"])')
    assert outs == [None], outs
    outs, _, _ = _boot_run(
        bootvm,
        'let d = {2: "v", 3.5: "f", 真: "b", "s": "str"} in '
        '输出([d[2], d[3.5], d[真], d["s"], d["2"]])')
    assert outs == [["v", "f", "b", "str", None]], outs


def test_37d_dict_neutrals_three_faces():
    """字典中性回归：字符串键 / 浮点键往返三面同判（集合枚举与管道理解
    路由面 mb 求值边界另见 37x 登记锁）。"""
    _three_faces("dict_str_neutral", 'let d = {"a": 1} in 输出(d["a"])', [1])
    _three_faces("dict_float_key_round",
                 'let d = {2.0: "f"} in 输出(d[2.0])', ["f"])


# ============================================================
# 37x 附带发现登记锁（登记不修）
# ============================================================

def test_37x_output_tail_block_value_registration():
    """登记锁（维持）：vm/hi 输出尾块值 host 内部分歧——编译面语句尾
    PUSH_NULL vs 解释面输出通道规则（_eval_block_value 尾语句执行后
    outputs[-1]）。boot 解释面已随 37b 尾值映射收敛 vm 面（boot 编译面
    _是语句类型 输出 PUSH_NULL 自洽）。登记不修。"""
    src = "let r = { let y = 7 in 输出(y) } in 输出(r)"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [7, None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [7, 7], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == [7, None], ("mb", mb, mb_err)
    src2 = "let r = { let rec f = (k) => if k = 0 then 3 else f(k - 1) in 输出(f(2)) } in 输出(r)"
    outs, err = exec_api.run_checked(src2)
    assert err is None and outs == [3, None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src2)
    assert hi_err is None and hi == [3, 3], ("hi", hi, hi_err)


def test_37x_mb_set_construct_eval_registration():
    """登记锁（维持）：mb 面集合构造求值未知表达式类型（boot 求值无
    集合构造 臂——vm/hi 正常枚举；既有边界，登记防漂移；37d 花括号
    种类改动不扰动集合路由）。"""
    src = "输出({1, 2, 3})"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [[1, 2, 3]], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [[1, 2, 3]], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and "未知表达式类型: 集合构造" in str(mb_err), \
        (mb, mb_err)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
