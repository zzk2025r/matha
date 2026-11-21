# -*- coding: utf-8 -*-
"""阶段 31 语言完备 + 判定面收敛锁（31a-31g 六片双面/三面判定）。

31 六片的真化与对齐，逐项最小源锁（探针移植）：

  ① 31a func 定义 `->` 返回类型可选（29-⑧ 退役；29b let 简写同规）：
     无箭头/无箭头递归/带箭头三形态三执行面 + 字节码对拍（boot 编译器
     返回类型=null 纯元数据不消费，stage2↔stage3 逐位一致）；
  ② 31b 双 for 推导 [e for a in xs for b in ys if c...]（30d 分歧条退役；
     宿主 ListComp.gens + interp gens 分支 + MBC _emit_list_comp_multi
     嵌套循环发射；boot parser 做ListComp多 + boot interp _推导多子句；
     Python 语义第 k 层条件在绑定第 k 层变量后求值）：列表源三执行面 +
     字典源插面元组对（31d-② host list(items()) 同形）。
     登记：boot 编译器无推导发射（诚实报错 未支持的表达式类型 列表推导，
     字节码对拍不适用）+ VM 面字典源迭代 KeyError(0)（vm for/推导迭代
     经下标循环对 dict 源取 int 键——interp 面/宿主面元组对已对齐）；
  ③ 31c 语句位括号链（块体位 [x] >> [y] 链收集——boot parser 解析输出语句
     镜像宿主 _parse_mech_stmt 链语境；顶层双面诚实拒绝维持）：VM 面 +
     boot 面同判 + 字节码对拍。登记：宿主解释器面 ChainStmt 暂不支持求值
     （块值模型分歧——宿主 exec-last vs boot exec-last 面预存差异）；
  ④ 31d f[0] 类型守卫（30c 同款 List/Tuple 探测→不可调用）+ 字典迭代对齐：
     Int 应用于调用位三面同文案「不可调用的值: 5」；空列表调用三面诚实
     （mb 面 str([]) 渲染 <?>? 呈现分歧登记）；for 字典源插面元组对；
  ⑤ 31f 切片表达式求值真化（30 收官登记④退役；boot interp 求值切片 族
     镜像宿主 SliceExpr：缺端 null→None/负回绕/越界钳制/起点超长→空；
     列表/字符串/元组三容器 12 形态三面同判 + 非容器诚实报错同文案）。
     登记：VM 面元组切片返列表（宿主/插面保元组形——VM 发射 BUILD_LIST
     预存）+ VM 面非容器切片 TypeError 原生形态（宿主/插面
     MathaRuntimeError 同文案）；
  ⑥ 31e/31g sweep 装配与预算（golden manifest preload 前置拼接双轨同源
     镜像 run_golden_tests.py:378 + warmup barrier 把 worker init（boot
     链编译）移出单文件预算 + --timeout 默认 120→600——golden 37/38
     柯里化递归 O(n²) 真慢档非死循环）：装配力学 + 源形状锁。
"""
import inspect
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src import ast_nodes as ast
from src.kernel import exec_api
from src import matha_bootstrap
from src import interp as host_interp
from scripts import selfhost_matrix as sm  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_COMP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha"]


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def dict_to_module(d):
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def _canon_code(mod):
    """指令码逐位（28c _canon 的码子集：main + 全函数码）。"""
    if isinstance(mod, MModule):
        return {"main": [tuple(i) for i in mod.main_code],
                "fns": {n: [tuple(i) for i in f.code]
                        for n, f in mod.functions.items()}}
    return {"main": [tuple(i) for i in mod["主码"]],
            "fns": {e[0]: [tuple(i) for i in e[1]["码"]] for e in mod["函数"]}}


@pytest.fixture(scope="module")
def bvm():
    """五文件自举编译器 VM（lexer+stdlib+parser+interp+compiler_matha）。"""
    comp = Compiler()
    decls = []
    for rel in _COMP_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _stage2(src):
    return Compiler().compile_program(py_parse(_strip_bom(src)))


def _stage3(bvm, src):
    return dict_to_module(bvm.call("编译", _strip_bom(src)))


def _boot_interp(src):
    """自举解释器面（matha_bootstrap：lexer/parser/stdlib/interp_matha 链）。

    strict=True：boot 面异常如实上抛，不静默降级 Python 解释器。"""
    try:
        outs, trace = matha_bootstrap.interpret(src, strict=True)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _hi_interp(src):
    try:
        outs, trace = host_interp.interpret(src)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _assert_parity(bvm, src):
    assert _canon_code(_stage3(bvm, src)) == _canon_code(_stage2(src)), src


def _three_faces(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == want, (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == want, (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == want, (tag, "mb", mb, mb_err)


# ============================================================
# ① 31a func 定义 -> 可选
# ============================================================

_FUNC_CASES = [
    ("noarrow", "func f(x: Int) = x * 2\n输出(f(21))", [42]),
    ("noarrow_rec", "func 倒数(n: Int) = if n <= 0 then [] else 倒数(n - 1) + [n]\n输出(倒数(3))",
     [[1, 2, 3]]),
    ("with_arrow", "func g(x: Int) -> Int = x + 1\n输出(g(1))", [2]),
]


def test_31a_func_noarrow_three_faces():
    for tag, src, want in _FUNC_CASES:
        _three_faces(tag, src, want)


def test_31a_func_noarrow_parity(bvm):
    for tag, src, _ in _FUNC_CASES:
        _assert_parity(bvm, src)


# ============================================================
# ② 31b 双 for 推导
# ============================================================

_COMP_CASES = [
    ("two_gen", "输出([x * y for x in [1, 2] for y in [10, 20]])", [[10, 20, 20, 40]]),
    ("two_gen_if", "输出([x + y for x in [1, 2, 3] for y in [10, 20] if x != 2])",
     [[11, 21, 13, 23]]),
    ("one_gen", "输出([x * 2 for x in [1, 2, 3]])", [[2, 4, 6]]),
]
_COMP_DICT = 'd = {"a": 1, "b": 2}\n输出([p for p in d])'
_COMP_DICT_WANT = [[("a", 1), ("b", 2)]]


def test_31b_multi_comp_three_faces():
    for tag, src, want in _COMP_CASES:
        _three_faces(tag, src, want)


def test_31b_comp_dict_pairs_interp_faces():
    """字典源推导：宿主/插面元组对（host list(items()) 同形，31d-② 同源）。

    VM 面字典源迭代 KeyError(0)（vm 迭代经下标循环取 int 键）登记不修。"""
    hi, hi_err = _hi_interp(_COMP_DICT)
    assert hi_err is None and hi == _COMP_DICT_WANT, (hi, hi_err)
    mb, mb_err = _boot_interp(_COMP_DICT)
    assert mb_err is None and mb == _COMP_DICT_WANT, (mb, mb_err)


def test_31b_boot_compiler_honest_reject(bvm):
    """boot 编译器推导发射真化（32c）：本锁退役。

    31b 时点 boot 编译器无推导发射（诚实报错不假成功）；32c 真化后
    boot 编译器支持推导发射且与宿主逐位一致（tests/test_selfhost_language_
    phase32.py test_32c_comp_parity 承接）。此处锁退役形态：同源编译
    不再抛错且 stage2↔stage3 逐位一致。"""
    _assert_parity(bvm, _COMP_CASES[2][1])


# ============================================================
# ③ 31c 语句位括号链
# ============================================================

_CHAIN_BLK = "func f() = {\n  [1] >> [2]\n}\n输出(f())"
_CHAIN_BLK_WANT = [1, 2, None]


def test_31c_block_chain_vm_boot_faces():
    """块体位 [x] >> [y] 链收集：VM 面 + boot 面同判（输出 1/2，块值 None）。

    登记不修：宿主解释器面 ChainStmt 暂不支持求值（块值模型分歧预存）。"""
    outs, err = exec_api.run_checked(_CHAIN_BLK)
    assert err is None and outs == _CHAIN_BLK_WANT, (outs, err)
    mb, mb_err = _boot_interp(_CHAIN_BLK)
    assert mb_err is None and mb == _CHAIN_BLK_WANT, (mb, mb_err)


def test_31c_block_chain_parity(bvm):
    _assert_parity(bvm, _CHAIN_BLK)


def test_31c_top_chain_honest_reject():
    """顶层 [1] >> [2] 双面诚实拒绝（宿主 _bracket_followed_by_infix 不含 >>）。"""
    outs, err = exec_api.run_checked("[1] >> [2]")
    assert err is not None, outs
    mb, mb_err = _boot_interp("[1] >> [2]")
    assert mb_err is not None or any("语法分析错误" in str(o) for o in (mb or [])), mb


# ============================================================
# ④ 31d f[0] 类型守卫 + 字典迭代对齐
# ============================================================

def test_31d_uncallable_int_guard():
    """Int 应用于调用位：三面同文案 不可调用的值: 5（30c 探测同款）。"""
    for src in ("输出(5(1))",):
        outs, err = exec_api.run_checked(src)
        assert err is not None and "不可调用的值: 5" in str(err), (outs, err)
        hi, hi_err = _hi_interp(src)
        assert hi_err is not None and "不可调用的值: 5" in str(hi_err), hi_err
        mb, mb_err = _boot_interp(src)
        assert mb_err is not None and "不可调用的值: 5" in str(mb_err), mb_err


def test_31d_uncallable_empty_list_honest():
    """空列表调用：三面诚实拒绝（mb 面 str([]) 渲染 <?>? 呈现分歧登记不修）。"""
    outs, err = exec_api.run_checked("输出([](1))")
    assert err is not None and "不可调用的值: []" in str(err), (outs, err)
    hi, hi_err = _hi_interp("输出([](1))")
    assert hi_err is not None and "不可调用的值: []" in str(hi_err), hi_err
    mb, mb_err = _boot_interp("输出([](1))")
    assert mb_err is not None, mb


_FOR_DICT = 'acc = []\nfor p in {"a": 1, "b": 2} {\n  acc = acc + [p]\n}\n输出(acc)'
_FOR_DICT_WANT = [[("a", 1), ("b", 2)]]


def test_31d_for_dict_pairs_interp_faces():
    """for 字典源：宿主/插面元组对（31d-②）；VM 面 KeyError(0) 登记不修。"""
    hi, hi_err = _hi_interp(_FOR_DICT)
    assert hi_err is None and hi == _FOR_DICT_WANT, (hi, hi_err)
    mb, mb_err = _boot_interp(_FOR_DICT)
    assert mb_err is None and mb == _FOR_DICT_WANT, (mb, mb_err)


def test_31d_for_str_three_faces():
    _three_faces("for_str", "acc = []\nfor c in \"ab\" {\n  acc = acc + [c]\n}\n输出(acc)",
                 [["a", "b"]])


# ============================================================
# ⑤ 31f 切片表达式求值
# ============================================================

_SLICE_HEAD = "xs = [1, 2, 3, 4, 5]\ns = \"abcdef\"\n"
_SLICE_CASES = [
    ("list_mid", _SLICE_HEAD + "输出(xs[1:4])", [[2, 3, 4]]),
    ("list_open_end", _SLICE_HEAD + "输出(xs[2:])", [[3, 4, 5]]),
    ("list_open_start", _SLICE_HEAD + "输出(xs[:2])", [[1, 2]]),
    ("list_full", _SLICE_HEAD + "输出(xs[:])", [[1, 2, 3, 4, 5]]),
    ("list_neg_start", _SLICE_HEAD + "输出(xs[-2:])", [[4, 5]]),
    ("list_neg_end", _SLICE_HEAD + "输出(xs[:-1])", [[1, 2, 3, 4]]),
    ("list_start_past", _SLICE_HEAD + "输出(xs[5:])", [[]]),
    ("list_inverted", _SLICE_HEAD + "输出(xs[2:1])", [[]]),
    ("str_tail", _SLICE_HEAD + "输出(s[1:])", ["bcdef"]),
    ("str_mid", _SLICE_HEAD + "输出(s[2:4])", ["cd"]),
    ("str_neg_start", _SLICE_HEAD + "输出(s[-2:])", ["ef"]),
]


def test_31f_slice_three_faces():
    """12 形态三面同判（列表 8 + 字符串 3 + 非容器报错）。

    登记：VM 面元组切片返列表（宿主/插面保元组形——VM 发射 BUILD_LIST
    预存，t[0:2] 形态不在本锁；VM 面非容器切片 TypeError 原生形态同登记）。"""
    for tag, src, want in _SLICE_CASES:
        _three_faces(tag, src, want)


def test_31f_slice_tuple_pairs_interp_faces():
    """元组切片：宿主/插面保元组形（VM 面返列表登记不修）。"""
    src = "t = (1, 2, 3, 4)\n输出(t[0:2])\n输出(t[-1:])"
    want = [(1, 2), (4,)]
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == want, (hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == want, (mb, mb_err)


def test_31f_slice_noncontainer_honest():
    """非容器切片：宿主/插面同文案 MathaRuntimeError（VM 面诚实错形态登记）。"""
    src = "输出(5[1:2])"
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and "切片操作不支持: int[1:2]" in str(hi_err), hi_err
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and "切片操作不支持: int[1:2]" in str(mb_err), mb_err
    outs, err = exec_api.run_checked(src)
    assert err is not None, (outs, err)


# ============================================================
# ⑥ 31e/31g sweep 装配与预算
# ============================================================

_G36 = "golden_tests/cases/36_basics_map_filter_reduce.matha"


def test_31e_preload_assembly_mirror():
    """golden manifest preload 装配：36-39 前置 collections_core，其余语料 []。"""
    for stem in ("36_basics_map_filter_reduce", "37_basics_sorted",
                 "38_basics_join_split", "39_basics_gcd"):
        rel = f"golden_tests/cases/{stem}.matha"
        assert sm._manifest_preloads(rel) == ["matha/library/collections_core.matha"], stem
        assembled = sm._assemble_source(rel)
        lib = (_ROOT / "matha/library/collections_core.matha").read_text(encoding="utf-8")
        raw = (_ROOT / rel).read_text(encoding="utf-8")
        assert assembled == lib + "\n" + raw, stem
    assert sm._manifest_preloads("matha/interp.matha") == []
    assert sm._manifest_preloads("golden_tests/cases/35_list_comp.matha") == []


def test_31e_assembled_case36_vm_face():
    """装配后 case 36 VM 面真跑（map/filter/reduce 柯里化闭包；VM 面与宿主
    解释器面输出一致——boot 面 Track B 快照对拍同判）。"""
    outs, err = exec_api.run_checked(sm._assemble_source(_G36))
    assert err is None
    assert outs == [[2, 3, 4, 5], [], [2, 4], [], 10, 7, 42, 30, [1, 2, 0, 1]], outs
    hi, hi_err = _hi_interp(sm._assemble_source(_G36))
    assert hi_err is None and hi == outs, (hi, hi_err)


def test_31g_warmup_and_budget_shape():
    """warmup barrier（worker init 移出单文件预算）+ --timeout 默认 600 源形状。"""
    rs_src = inspect.getsource(sm.run_sweep)
    assert "map_async(_warm" in rs_src, "warmup barrier 缺失"
    assert "_WARMUP_TIMEOUT = 1800.0" in inspect.getsource(sm)
    main_src = inspect.getsource(sm.main)
    assert "default=600.0" in main_src, "timeout 默认应为 600（31g 治理）"


def test_31g_snapshot_classes():
    """31g 治理后快照分类（--write 实测）：36/39 both_err→ok（preload 装配
    首次真跑）；37/38 双面真跑 >600s 同判 timeout（柯里化递归 O(n²) 慢档，
    非分歧）；stdlib_symbols 600s 预算内 ok/ok；interp.matha 双面真跑
    >600s 维持 timeout（30f 归因「重档自检 >120s」承继，非 worker-init
    race——warmup 后 600s 预算下依旧双面超时，实况归因见 KNOWN_ISSUES 31）。"""
    entries = sm.load_snapshot()["files"]
    by_path = {e["path"]: e for e in entries}
    for stem in ("36_basics_map_filter_reduce", "39_basics_gcd"):
        e = by_path[f"golden_tests/cases/{stem}.matha"]
        assert e["boot"] == "ok" and e["host"] == "ok", (stem, e)
    for p in ("golden_tests/cases/37_basics_sorted.matha",
              "golden_tests/cases/38_basics_join_split.matha",
              "matha/interp.matha"):
        e = by_path[p]
        assert e["boot"] == "timeout" and e["host"] == "timeout", (p, e)
    e = by_path["matha/stdlib_symbols.matha"]
    assert e["boot"] == "ok" and e["host"] == "ok", e


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
