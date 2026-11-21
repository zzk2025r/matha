# -*- coding: utf-8 -*-
"""阶段 32 语言收敛锁（32a 迭代源归一四面 + 切片文案对齐 + 32b 块尾链真化）。

32a（拍板「五片语言收敛」+「② 中心工程受控切片」）：

  ① 字典迭代四面（迭代源归一）：宿主编译器 for/推导三发射位统一经
     LOAD_GLOBAL "_迭代源" + CALL 1（fn 在下 arg 在上），VM 内建
     dict → ('k', v) 真元组对、其余容器恒等；native C iter_source
     dict → [键, 值] 2 元素列表对（②S1 前无元组对象，载体形态 ② 后
     归一）、其余恒等；boot 编译器 _编译for 镜像（28c parity 逐位一致）；
     vm.matha 迭代源归一 Matha 镜像（_dict_keys/_dict_values 平行序，
     2 元素列表对）。hi/mb 面 31d 既有元组对语义不受扰动。
     登记：boot 解析器 for (k, v) in 多变量目标未支持（诚实报错
     期望 关键字）——登记不修，②S2/后续补齐。
  ③ BUILD_SLICE 守卫（vm.py）：不可切片容器归一 MathaRuntimeError
     「切片操作不支持: int[0:1]」（裸值原样呈现），与宿主 interp.py /
     boot interp_matha（31f）逐字一致——VM 历史上漏出 Python TypeError。

32b：hi 面 ChainStmt 块尾值位真化（31c-③ 登记退役）——块体位
  [x] >> [y] 链作块尾时 vm/boot 面块值 None、宿主解释器面报「暂不支持
  求值: ChainStmt」预存分歧；hi 面 _eval 补 ChainStmt 臂（逐链执行、
  返回 None），三面同判 [1, 2, None]。

32d：mb 面 str 通用化（28-⑨「stdlib str 数字专用」退役）——stdlib.matha
  str 移植 vm.matha 函数str 渲染器（Bool→True/False、null→None、
  列表 [a, b]、字典 {'k': v}、容器内字符串 repr 引号转义、函数
  <function>）+ 自举闭包形态守卫（boot 闭包是 ["__closure__",...] 列表
  且捕获环境自引用——守卫先行杜绝 RecursionError，与 boot 输出归一
  同哨兵）；类型谓词 _is_number/_is_string/_is_list/_is_dict 改
  matha_type_of 直判（<?>? 哨兵启发式随 str 通用化失效）。
  boot 链常载 stdlib（无 use 时 mb 面 str 即 stdlib str）——三面无 use
  对拍即 mb↔宿主内建渲染对齐；use 标准库 装载面走 sweep 驱动器
  （裸 bootvm 不加载，登记维持）。hi 面 func 值是 FuncDef AST 节点
  （str→节点 repr / type_of→Unknown / 输出→裸节点）——既有分歧登记 32f。

32e：let rec 互相递归真化（29-②登记退役）——块/程序级语句位 let rec
  互递归三面贯穿。hi 面（interp.py）：块/程序入口 _preregister_rec_let
  预注册全部语句位 let rec 占位符（互相递归前向可见），LetBinding 语句臂
  复用入口占位符填充（复用窗口块内封闭）；表达式位 let-in 恒新建占位符
  （self.env 跨闭包调用持久——链代码异函数同名 let rec _go 族复用在途
  占位对会 _ref 串线，mb 面推导链 不可调用的值 实证；全局槽必须保持
  惰性，Matha 闭包名解析走捕获 _matha_env 列表）。VM 面（compiler.py）：
  _emit_block 预发（binds_global 无局部帧时跳过——顶层互递归经
  LOAD_GLOBAL 调用时晚绑定天然可用）+ _emit_let 填充臂（_rec_fill 待填
  集合）。boot 镜像（compiler_matha.matha）：_预发块盒/_收集rec名/
  _发块盒 + bc["待填盒"] 待填名单（六 _bc* 重建函数必须携带此键——
  初版遗漏致第二填充臂 _取待填盒 null，NoneType[0]）+ _编译let填充。
  29-②「boot 面互相递归 let rec 前向引用报未定义变量」退役。
  登记：链式 let-in 表达式互递归（let rec a=…in let rec b=…in）
  vm 面 [0] vs hi/mb 面未定义变量 'b'——编译面晚绑定 vs 解释面
  定义时刻捕获的本质分歧，登记 32f 不修。
"""
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
# ① 字典迭代四面（迭代源归一）
# ============================================================

_DICT_PAIRS = [("a", 1), ("b", 2)]

_DICT_COMP = 'd = {"a": 1, "b": 2}\n输出([p for p in d])'
_DICT_FOR = 'd = {"a": 1, "b": 2}\ns = 0\nfor p in d {\n  s = s + p[1]\n}\n输出(s)'
_DICT_FOR_KV = ('d = {"a": 1, "b": 2}\ns = ""\nfor (k, v) in d {\n'
                '  s = s + k\n}\n输出(s)')


def test_32a_dict_comp_pairs_three_faces():
    """字典源推导：三面 (键, 值) 对（VM 面经 _迭代源 真元组，此前 KeyError(0)）。"""
    _three_faces("comp_dict", _DICT_COMP, [_DICT_PAIRS])


def test_32a_dict_for_pairs_three_faces():
    """字典源 for 单变量：三面对值求和（p[1] 下标元组/对列表均可）。"""
    _three_faces("for_dict", _DICT_FOR, [3])


def test_32a_dict_for_kv_vm_hi_faces():
    """for (k, v) in 多变量目标 UNPACK_SEQ 解构：VM/hi 面真元组。

    登记：boot 解析器 for (k, v) in 多变量目标未支持（见下方诚实拒绝锁）。"""
    outs, err = exec_api.run_checked(_DICT_FOR_KV)
    assert err is None and outs == ["ab"], (outs, err)
    hi, hi_err = _hi_interp(_DICT_FOR_KV)
    assert hi_err is None and hi == ["ab"], (hi, hi_err)


def test_32a_dict_for_kv_boot_parser_honest_reject():
    """boot 解析器 for (k, v) in 诚实拒绝（登记不修：期望 关键字）。

    boot 面语法错误以输出行呈现（strict=True 不异常上抛），双形态同判
    （31c 顶层链诚实拒绝锁同款）。"""
    mb, mb_err = _boot_interp(_DICT_FOR_KV)
    assert mb_err is not None or any("语法分析错误" in str(o) for o in (mb or [])), \
        (mb, mb_err)


def test_32a_nondict_iterable_identity_vm_faces():
    """非字典源恒等透传（_迭代源 归一不改既有语义）：str for / 列表推导 /
    元组源 for——VM 面回归锁。"""
    for tag, src, want in [
        ("str_for", 's = 0\nfor ch in "abc" {\n  s = s + 1\n}\n输出(s)', [3]),
        ("list_comp", "输出([x * 2 for x in [1, 2, 3]])", [[2, 4, 6]]),
        ("tuple_for", "s = 0\nfor x in (10, 20, 30) {\n  s = s + x\n}\n输出(s)",
         [60]),
    ]:
        outs, err = exec_api.run_checked(src)
        assert err is None and outs == want, (tag, "vm", outs, err)


def test_32a_for_parity(bvm):
    """boot 编译器 _编译for 镜像：for 语料 stage2↔stage3 逐位一致。

    字典/元组/字符串源共享同一发射形状（迭代源 wrap 与源类型无关），
    一条字典源锁面即覆盖 wrap 位序 + 常量池序。推导 parity 归 32c。"""
    _assert_parity(bvm, _DICT_FOR)


# ============================================================
# ③ BUILD_SLICE 守卫 + 文案对齐
# ============================================================

_SLICE_CASES = [
    ("int", "x = 5\n输出(x[0:1])", "切片操作不支持: int[0:1]"),
    ("dict", 'd = {"a": 1}\n输出(d[0:1])', "切片操作不支持: dict[0:1]"),
]


def test_32a_slice_noncontainer_three_faces():
    """不可切片容器：VM 面 MathaRuntimeError 与宿主/boot 逐字一致。

    VM 面双通道漏出归一：int 切片 TypeError、dict 切片键 KeyError——
    BUILD_SLICE 臂 (TypeError, KeyError) 双接。"""
    from src.kernel.errors import MathaRuntimeError
    for tag, src, msg in _SLICE_CASES:
        outs, err = exec_api.run_checked(src)
        assert outs is None or outs == [], (tag, "vm", outs)
        assert isinstance(err, MathaRuntimeError) and str(err) == msg, \
            (tag, "vm", err)
        hi, hi_err = _hi_interp(src)
        assert hi is None and hi_err is not None
        assert str(hi_err) == msg, (tag, "hi", hi_err)
        mb, mb_err = _boot_interp(src)
        assert mb is None and mb_err is not None
        assert str(mb_err) == msg, (tag, "mb", mb_err)


# ============================================================
# ② 32b hi 面 ChainStmt 块尾值位真化（31c-③ 登记退役）
# ============================================================

_CHAIN_CASES = [
    ("blk_chain", "func f() = {\n  [1] >> [2]\n}\n输出(f())", [1, 2, None]),
    ("blk_chain_3", "func f() = {\n  [1] >> [2] >> [3]\n}\n输出(f())",
     [1, 2, 3, None]),
]


def test_32b_block_chain_tail_three_faces():
    """块尾值位链三面同判 [1, 2, None]（输出入 outputs、块值 None）。

    31c-③ 登记「宿主解释器面 ChainStmt 暂不支持求值（块值模型分歧）」
    退役：hi 面 _eval 补 ChainStmt 臂（逐链执行、返回 None），对齐
    vm/boot 面块值模型（宿主编译器逐链内联发射同形）。"""
    for tag, src, want in _CHAIN_CASES:
        _three_faces(tag, src, want)


# ============================================================
# 32c boot 编译器推导发射真化（30d 推导节点承接编译面）
# ============================================================

_COMP_CASES = [
    ("comp_noif", "输出([x * 2 for x in [1, 2, 3]])"),
    ("comp_if", "输出([x * 2 for x in [1, 2, 3] if x > 1])"),
    ("comp_if2", "输出([x for x in [1, 2, 3, 4] if x > 1 if x < 4])"),
    ("comp_multi", "输出([x + y for x in [1, 2] for y in [10, 20]])"),
    ("comp_multi_if",
     "输出([x * y for x in [1, 2, 3] for y in [10, 20] if x > 1])"),
    ("comp_dict", 'd = {"a": 1, "b": 2}\n输出([p for p in d])'),
    ("comp_str", '输出([ch for ch in "abc"])'),
    ("comp_nested", "func f(xs) = { [x * x for x in xs] }\n输出(f([1, 2, 3]))"),
]


def test_32c_comp_parity(bvm):
    """boot 编译器推导发射逐位对拍（_发射推导 单/多生成子句镜像宿主
    _emit_list_comp / _emit_list_comp_multi）：30d 推导节点此前仅解析/
    解释面真化，编译面落「未支持的表达式类型」——stage3 无法编译推导。
    发射形状与宿主逐条对齐：_迭代源 wrap、lc_xs/lc_i/lc_res 临时槽
    （分配序镜像）、len/get 下标循环、条件 JZ→inc 链、append 累加器
    （融合判据 _查元数 append==2）、多子句嵌套（子层耗尽 JZ 回填父层
    inc、最外层耗尽回填总出口）。"""
    for tag, src in _COMP_CASES:
        _assert_parity(bvm, src)


def test_32c_comp_exec_three_faces():
    """推导三面执行对拍：vm（stage2 字节码）/ hi（宿主解释器）/
    mb（自举解释器）同判。"""
    for tag, src, want in [
        ("comp_if", _COMP_CASES[1][1], [[4, 6]]),
        ("comp_if2", _COMP_CASES[2][1], [[2, 3]]),
        ("comp_multi_if", _COMP_CASES[4][1], [[20, 40, 30, 60]]),
        ("comp_dict", _COMP_CASES[5][1], [_DICT_PAIRS]),
        ("comp_str", _COMP_CASES[6][1], [["a", "b", "c"]]),
    ]:
        _three_faces(tag, src, want)


# ============================================================
# ③ 32d mb 面 str 通用化（28-⑨ 登记退役）
# ============================================================

_STR_CASES = [
    ("int", "输出(str(42))", ["42"]),
    ("negint", "输出(str(-7))", ["-7"]),
    ("float", "输出(str(2.5))", ["2.5"]),
    ("bool", "输出(str(真) + \",\" + str(假))", ["True,False"]),
    ("null", "输出(str(null))", ["None"]),
    ("string", '输出(str("abc"))', ["abc"]),
    ("empty_list", "输出(str([]))", ["[]"]),
    ("list", '输出(str([1, "a", 真]))', ["[1, 'a', True]"]),
    ("nested", "输出(str([[1], [2]]))", ["[[1], [2]]"]),
    ("dict", '输出(str({"k": 1}))', ["{'k': 1}"]),
    ("quote", '输出(str(["it\'s"]))', ['["it\'s"]']),
]


def test_32d_str_container_render_three_faces():
    """str 通用化三面对拍：boot 链常载 stdlib → mb 面 str 即 stdlib str，
    vm/hi 面走内建 str（Python str）——三面同判即 mb↔宿主渲染对齐。

    28-⑨「stdlib str 数字专用」退役：容器/布尔/null/字符串/引号转义
    （CPython repr 规则：仅含 ' 无 " 用双引号）全部真化。"""
    for tag, src, want in _STR_CASES:
        _three_faces(tag, src, want)


def test_32d_str_function_render_vm_mb_faces():
    """str(函数) → "<function>"：vm 内建与 boot stdlib 同形（宿主
    builtin_str_value 口径）。

    boot 闭包是 Matha 列表 ["__closure__",...] 且捕获环境自引用——
    stdlib str 闭包形态守卫先行（与 boot 输出归一同哨兵），杜绝遍历
    捕获环境 RecursionError；容器嵌套函数 mb 面 [<function>]（stdlib
    元素repr 递归守卫）。hi 面 func 值是 FuncDef AST 节点（str→节点
    repr / type_of→Unknown / 输出→裸节点）——既有分歧登记 32f。"""
    src = "func f() = 1\n输出(str(f))"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == ["<function>"], (outs, err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == ["<function>"], (mb, mb_err)
    mb2, mb_err2 = _boot_interp("func f() = 1\n输出(str([f]))")
    assert mb_err2 is None and mb2 == ["[<function>]"], (mb2, mb_err2)


def test_32d_str_numeric_regression_mb_faces():
    """数值渲染回归：str_safe/_is_number 族改 matha_type_of 直判后
    Bool/null 仍诚实拒绝（哨兵启发式退役不改语义）。vm/hi 面
    use 标准库 装载 stdlib str_safe（三面共享同一实现）。"""
    src = 'use 标准库\n输出(str_safe(真) + "," + str_safe(null) + "," + str_safe(7))'
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == ["<?>?,<?>?,7"], (outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == ["<?>?,<?>?,7"], (hi, hi_err)


# ============================================================
# ④ 32e let rec 互相递归真化（29-② 登记退役）
# ============================================================

_TOP_MUTUAL = ("let rec ev = (n) => if n = 0 then 真 else od(n - 1)\n"
               "let rec od = (n) => if n = 0 then 假 else ev(n - 1)\n"
               "输出(ev(10))\n输出(od(10))")

_BLK_MUTUAL = ("func f() = {\n"
               "  let rec ev = (n) => if n = 0 then 真 else od(n - 1)\n"
               "  let rec od = (n) => if n = 0 then 假 else ev(n - 1)\n"
               "  输出(ev(10))\n"
               "  输出(od(10))\n"
               "}\n输出(f())")

_BLK_SINGLE = ("func fact(n) = {\n"
               "  let rec f = (k) => if k = 0 then 1 else k * f(k - 1)\n"
               "  f(n)\n"
               "}\n输出(fact(5))")

_CHAINED_MUTUAL = ("let rec a = (n) => if n = 0 then 0 else b(n - 1) in "
                   "let rec b = (n) => if n = 0 then 1 else a(n - 1) in "
                   "输出(a(4))")


def test_32e_top_mutual_three_faces():
    """顶层互递归 let rec 三面同判 [True, False]：hi 面程序入口预注册
    （_preregister_rec_let）、vm 面 LOAD_GLOBAL 晚绑定、mb 面镜像。"""
    _three_faces("top_mutual", _TOP_MUTUAL, [True, False])


def test_32e_blk_mutual_three_faces():
    """块内互递归 let rec 三面同判 [True, False, False]：块体位
    输出(ev(10))、输出(od(10)) 各入一行，块尾 od(10) 值 False 经
    输出(f()) 落第三行。hi 面 CodeBlock 入口预注册 + 语句臂复用；
    vm 面 _emit_block 预发 + _emit_let 填充臂（LOAD_OUTER_BOX 沿帧链
    捕获后定义盒）；boot 镜像 _预发块盒 + _编译let填充。"""
    _three_faces("blk_mutual", _BLK_MUTUAL, [True, False, False])


def test_32e_blk_single_regression():
    """单函数块内 let rec 回归锁 [120]（28c-R2 盒协议不受预发重构扰动）。"""
    _three_faces("blk_single", _BLK_SINGLE, [120])


def test_32e_letin_regression():
    """表达式位 let-in 回归锁（32e 勘误后恒新建占位符，全局槽保持惰性）：
    letin_body [0]、letin_simple [5] 三面同判。"""
    _three_faces("letin_body",
                 "let rec f = (k) => if k = 0 then 0 else f(k - 1) in 输出(f(9))",
                 [0])
    _three_faces("letin_simple", "let x = 5 in 输出(x)", [5])


def test_32e_blk_mutual_parity(bvm):
    """blk_mutual/top_mutual stage2↔stage3 逐位一致：预发 MAKE_BOX 序、
    填充臂 STORE_BOX 槽位、__lam_N LOAD_OUTER_BOX 帧链深度逐位对齐
    （bc["待填盒"] 六 _bc* 重建函数携带初版遗漏回归锁）。"""
    _assert_parity(bvm, _BLK_MUTUAL)
    _assert_parity(bvm, _TOP_MUTUAL)


def test_32e_blk_mutual_stage3_run(bvm):
    """stage3 产物双 VM 执行：boot 编译器编译互递归源 → VM 跑出同值
    [True, False, False]（VM 面 MAKE_BOX/STORE_BOX/LOAD_OUTER_BOX
    三指令真消费自举编译器产物）。"""
    from src.mbc.vm import VM as _VM
    vm2 = _VM(_stage3(bvm, _BLK_MUTUAL))
    assert vm2.run() == [True, False, False]


def test_32e_chained_mutual_honest_divergence():
    """链式 let-in 表达式互递归：登记分歧锁（32f ③）。

    vm 面 [0]（编译面 LOAD_GLOBAL 晚绑定——b 调用时已在全局）vs
    hi/mb 面 未定义变量 'b'（解释面 lambda 定义时刻捕获 env——a 的
    闭包先于 b 定义物化）。本质分歧：编译面符号解析 vs 解释面
    词法捕获时刻。三面行为各自如实锁定。"""
    outs, err = exec_api.run_checked(_CHAINED_MUTUAL)
    assert err is None and outs == [0], (outs, err)
    hi, hi_err = _hi_interp(_CHAINED_MUTUAL)
    assert hi is None and hi_err is not None
    assert "未定义变量 'b'" in str(hi_err), hi_err
    mb, mb_err = _boot_interp(_CHAINED_MUTUAL)
    assert mb is None and mb_err is not None
    assert "未定义变量 'b'" in str(mb_err), mb_err
