# -*- coding: utf-8 -*-
"""阶段 35 语言收敛锁（自举解构贯穿 S1——统一解构语义四执行体真化，34-④ 退役）。

35a S1 统一解构语义：序列 = List/Tuple 且长度精确等于目标数，否则诚实报错
  「解构失败：期望 N 个元素，实际 <类型名>」（list/tuple/int/float/bool/
  str/dict/NoneType/function），四执行体同判：
  ① vm.py UNPACK_SEQ 守卫（此前越界补 None、非序列漏出 Python len()
    TypeError；闭包 Closure → "function"）——34-④ 退役
  ② interp.py 语句位 let 元组（此前非序列静默不绑定假成功→下游未定义变量、
    短元组补 None）+ 表达式位 let 元组（此前仅 tuple、短元组补 None、
    「元组解构期望元组」异文案；扩 List/Tuple 同判；("__closure__",…)
    4 元组标记跳过保留——仅真元组）；FuncDef/Lambda 节点与
    ("__closure__",…) 标记元组（hi lambda 闭包 3 元组）→ "function"
  ③ matha/vm.matha 解包守卫（懒三元 合长，防 eager and/or 陷阱）+
    _解构类型名 映射（VM² 闭包 ["__闭包__",…] 3 元列表标记 → "function"）
  ④ native unpack 严格化（si_n_* 静态类型名 + int_to_str 运行期拼消息，
    try/catch 可捕获 + 未捕获 rc=1 stderr；旧 全 None / 字符串逐字节解构 /
    越界补 None 路径退役）——锁在 tests/test_native.py
    test_unpack_*_honest_error ×3 + test_unpack_uncaught_exits_one

登记不修（KNOWN_ISSUES 阶段 35）：mb 表达式位 let 元组绑定 honest
  reject「未知表达式类型: let元组绑定」——boot 求值面暂不支持（不假
  编译），语句位 let 元组 boot 面 32 已落地。
  附带发现（35b 探针踩中）：m3v 面编译态 try/catch 不捕获运行期错误
  （除零/越界/未定义变量/解构失败全族一致上抛）——38a 捕获闭包单点
  包裹真化（35-② 退役），35x 锁真化改锁 test_35x_m3v_try_catch_true；
  vm/hi/mb/native 四面 try/catch 捕获正常（native/VM 面锁在
  test_native.py / phase34 _FAIL 三面锁）。

35b S2：boot 编译器 for 解构发射真化（34-① 退役）——_分配循环变量
  收窄单变量 + _分配循环变量们 逐名折叠（宿主 names 归一/var_ts 镜像）+
  _for循环码 UNPACK_SEQ n + _存解构逆序（宿主 reversed(var_ts) 镜像，
  _存储元组全局逆序 同协议）；单变量 for 字节码零变化（parity 回归锁）；
  多变量 stage2↔stage3 逐位一致 + M3V 运行面真跑（字典对/三元组/
  函数局部/元组对）；phase34 诚实拒绝锁真化退役（UNPACK_SEQ 发射锁）。
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
from src.kernel.errors import MathaRuntimeError
from src import matha_bootstrap
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_M3V_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
              "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]
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


def _boot_run(bootvm, src):
    """VM² 解释器面执行链（34e 同构）：输出清空 → 扫描 → parse →
    注册内建/空环境 → 绑定环境 链 ns → 执行语句 → 输出快照。"""
    bootvm.call("输出清空")
    toks = bootvm.call("扫描", src, 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    for nm, ns in bootvm._chain_nss.items():
        env0 = bootvm.call("绑定环境", env0, nm, ns)
    bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照"))


def _boot_err(bootvm, src):
    try:
        return _boot_run(bootvm, src), None
    except Exception as e:  # noqa: BLE001
        return None, e


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


@pytest.fixture(scope="module")
def m3v():
    """VM² M3V 运行面：五文件自举编译器 + vm.matha（test_mbc_vm_matha 同构）。

    编译（compiler_matha）→ 运行M3V（vm.matha 解包守卫执行面）。"""
    comp = Compiler()
    decls = []
    for rel in _M3V_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _m3v_run(m3v, src):
    d = m3v.call("编译", src)
    return list(m3v.call("运行M3V", d))


def _m3v_err(m3v, src):
    try:
        return _m3v_run(m3v, src), None
    except Exception as e:  # noqa: BLE001
        return None, e


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


def _stage2(src):
    return Compiler().compile_program(py_parse(_strip_bom(src)))


def _stage3(m3v, src):
    return dict_to_module(m3v.call("编译", _strip_bom(src)))


def _assert_parity(m3v, src):
    assert _canon_code(_stage2(src)) == _canon_code(_stage3(m3v, src)), src


def _vm_hi_err(tag, src, want):
    """vm/hi 两面同文案（let 元组六形态——mb 表达式位 honest reject，
    登记锁单独）。"""
    outs, err = exec_api.run_checked(src)
    assert err is not None and want in str(err), (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), (tag, "hi", hi, hi_err)


def _vm_hi_ok(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == want, (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == want, (tag, "hi", hi, hi_err)


# ============================================================
# 35a-1 let 元组解构（vm/hi 两面；mb 表达式位登记锁）
# ============================================================

_LET_OK = [
    ("let齐list", "let (a, b) = [1, 2] in 输出(a + b)\n", [3]),
    ("let齐tuple", "let (a, b) = (1, 2) in 输出(a + b)\n", [3]),
    ("let三元", "let (a, b, c) = [1, 2, 3] in 输出(a + b + c)\n", [6]),
    ("let语句位list", "let (a, b) = [10, 20]\n输出(a * 100 + b)\n", [1020]),
    ("let语句位tuple", "let (a, b) = (10, 20)\n输出(a * 100 + b)\n", [1020]),
]


@pytest.mark.parametrize("tag,src,want", _LET_OK, ids=[c[0] for c in _LET_OK])
def test_35a_let_ok_vm_hi(tag, src, want):
    """齐长 List/Tuple 语句位/表达式位解构 vm/hi 同判（hi 此前表达式位仅
    tuple、语句位非序列静默不绑定假成功——35a 统一退役）。"""
    _vm_hi_ok(tag, src, want)


_LET_BAD = [
    ("let短list", "let (a, b) = [1] in 输出(a)\n", "解构失败：期望 2 个元素，实际 list"),
    ("let字符串", "let (a, b) = \"hi\" in 输出(a)\n", "解构失败：期望 2 个元素，实际 str"),
    ("let整数", "let (a, b) = 5 in 输出(a)\n", "解构失败：期望 2 个元素，实际 int"),
    ("let空值", "let (a, b) = null in 输出(a)\n", "解构失败：期望 2 个元素，实际 NoneType"),
    ("let短元组", "let (a, b, c) = (1, 2) in 输出(a)\n",
     "解构失败：期望 3 个元素，实际 tuple"),
    ("let超长", "let (a) = [1, 2] in 输出(a)\n", "解构失败：期望 1 个元素，实际 list"),
]


@pytest.mark.parametrize("tag,src,want", _LET_BAD, ids=[c[0] for c in _LET_BAD])
def test_35a_let_mismatch_vm_hi(tag, src, want):
    """长度不匹配/非序列诚实报错同文案（vm 此前越界补 None、int 实参漏出
    Python len() TypeError；hi 此前语句位假成功——三案统一退役）。"""
    _vm_hi_err(tag, src, want)


def test_35a_let_stmt_mismatch_vm_hi():
    """语句位错形态同文案（语句位路径独立于表达式位路径）。"""
    _vm_hi_err("stmt_bad", "let (a, b) = 5\n输出(a)\n",
               "解构失败：期望 2 个元素，实际 int")


def test_35a_let_function_vm_hi():
    """函数值解构诚实报错，闭包形态归 "function"（vm Closure / hi FuncDef
    / hi lambda ("__closure__",…) 3 元组——对齐 native si_n_func 面）。"""
    _vm_hi_err("func", "func f(x) = x\nlet (a, b) = f in 输出(a)\n",
               "解构失败：期望 2 个元素，实际 function")
    _vm_hi_err("lambda", "let (a, b) = (x) => x * 2 in 输出(a)\n",
               "解构失败：期望 2 个元素，实际 function")


def test_35a_let_tuple_mb_true():
    """真化改锁（35-① 退役）：mb 表达式位 let 元组绑定真化（interp_matha
    求值let元组 臂 + _解构绑定元组 闭包标记同判，宿主 _eval 镜像）——
    「未知表达式类型: let元组绑定」诚实拒绝退役，三面同判；语句位
    维持 32 落地面。"""
    _three_faces("let_tuple_expr", "let (a, b) = [1, 2] in 输出(a + b)\n", [3])
    _three_faces("let_tuple_val", "let r = (let (a, b) = [1, 2] in a) in 输出(r)\n",
                 [1])


# ============================================================
# 35a-2 for 解构（三面 + VM² 解释器面）
# ============================================================

def test_35a_for_ok_three_faces():
    """齐长/字典对 for 解构三面同判（正控回归——35a 守卫不误伤）。"""
    _three_faces("for_list", "for (a, b) in [[1, 2]] { 输出(a + b)\n }\n", [3])
    _three_faces("for_dict", "for (k, v) in {\"x\": 1} { 输出(k)\n输出(v)\n }\n",
                 ["x", 1])


_FOR_BAD = [
    ("for超长", "for (a, b) in [[1, 2, 3]] { 输出(a)\n }\n",
     "解构失败：期望 2 个元素，实际 list"),
    ("for短", "for (a, b) in [[1]] { 输出(a)\n }\n",
     "解构失败：期望 2 个元素，实际 list"),
    ("for非序列", "for (a, b) in [5] { 输出(a)\n }\n",
     "解构失败：期望 2 个元素，实际 int"),
    ("for字符串项", "for (a, b) in [\"hi\"] { 输出(a)\n }\n",
     "解构失败：期望 2 个元素，实际 str"),
]


@pytest.mark.parametrize("tag,src,want", _FOR_BAD, ids=[c[0] for c in _FOR_BAD])
def test_35a_for_mismatch_three_faces(tag, src, want):
    """for 解构长度不匹配/非序列三面同文案（vm 此前静默产出 vs hi/mb
    解构失败——34-④ 分歧退役）。"""
    outs, err = exec_api.run_checked(src)
    assert err is not None and want in str(err), (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and want in str(mb_err), (tag, "mb", mb, mb_err)


def test_35a_for_fail_vm2_interp(bootvm):
    """VM² 解释器面（interp_matha _解构绑定）同文案（34e 既有行为镜像）。"""
    src = ('let xs = [[1, 2], [3]] in {\n'
           "  try {\n"
           "    for (k, v) in xs {\n"
           "      输出(k)\n"
           "    }\n"
           "  } catch (e) {\n"
           "    输出(e)\n"
           "  }\n"
           "}\n")
    outs, err = _boot_err(bootvm, src)
    assert err is None and outs == [1, "解构失败：期望 2 个元素，实际 list"], \
        (outs, err)


# ============================================================
# 35a-3 VM² M3V 运行面（自举编译器发射 + vm.matha 解包守卫）
# ============================================================

_M3V_OK = [
    ("m3v齐list", "let (a, b) = [1, 2] in 输出(a + b)\n", [3]),
    ("m3v齐tuple", "let (a, b) = (1, 2) in 输出(a + b)\n", [3]),
]


@pytest.mark.parametrize("tag,src,want", _M3V_OK, ids=[c[0] for c in _M3V_OK])
def test_35a_let_ok_m3v(m3v, tag, src, want):
    """VM² M3V 面：自举编译器 _编译顶层let元组 UNPACK_SEQ 发射 +
    vm.matha 解包守卫匹配路径（齐长解构正常）。"""
    assert _m3v_err(m3v, src) == (want, None)


_M3V_BAD = [
    ("m3v短list", "let (a, b) = [1] in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 list"),
    ("m3v字符串", "let (a, b) = \"hi\" in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 str"),
    ("m3v整数", "let (a, b) = 5 in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 int"),
    ("m3v空值", "let (a, b) = null in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 NoneType"),
    ("m3v浮点", "let (a, b) = 1.5 in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 float"),
    ("m3v布尔", "let (a, b) = true in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 bool"),
    ("m3v字典", "let (a, b) = {\"x\": 1} in 输出(a)\n",
     "解构失败：期望 2 个元素，实际 dict"),
    ("m3v短元组", "let (a, b, c) = (1, 2) in 输出(a)\n",
     "解构失败：期望 3 个元素，实际 tuple"),
]


@pytest.mark.parametrize("tag,src,want", _M3V_BAD, ids=[c[0] for c in _M3V_BAD])
def test_35a_let_mismatch_m3v(m3v, tag, src, want):
    """VM² M3V 面：vm.matha 解包守卫 + _解构类型名 映射同文案
    （list/tuple/int/float/bool/str/dict/NoneType 全族）。"""
    outs, err = _m3v_err(m3v, src)
    assert err is not None and want in str(err), (tag, outs, err)


def test_35a_let_function_m3v(m3v):
    """VM² M3V 面：boot 闭包 ["__闭包__",…] 3 元列表标记 → "function"
    （func 引用与 lambda 字面量两形态，对齐 vm/hi/native 同文案）。"""
    for tag, src in [("func", "func f(x) = x\nlet (a, b) = f in 输出(a)\n"),
                     ("lambda", "let (a, b) = (x) => x * 2 in 输出(a)\n")]:
        outs, err = _m3v_err(m3v, src)
        assert err is not None and \
            "解构失败：期望 2 个元素，实际 function" in str(err), (tag, outs, err)


# ============================================================
# 35b S2 boot 编译器 for 解构发射真化（34-① 退役）
# ============================================================

_FOR_PARITY = [
    ("single", "s = 0\nfor x in [1, 2, 3] {\n  s = s + x\n}\n输出(s)\n"),
    ("multi_dict",
     'd = {"a": 1, "b": 2}\ns = ""\nfor (k, v) in d {\n  s = s + k\n}\n输出(s)\n'),
    ("triple",
     "s = 0\nfor (a, b, c) in [[1, 2, 3], [4, 5, 6]] {\n"
     "  s = s + a * 100 + b * 10 + c\n}\n输出(s)\n"),
    ("fn_local",
     "func f(xs) = {\n  let t = 0\n  for (a, b) in xs {\n    t = t + a + b\n  }\n"
     "  t\n}\n输出(f([[1, 2], [3, 4]]))\n"),
    ("pair_tuples",
     "s = 0\nfor (a, b) in [(1, 2), (3, 4)] {\n  s = s + a + b\n}\n输出(s)\n"),
]


@pytest.mark.parametrize("tag,src", _FOR_PARITY, ids=[c[0] for c in _FOR_PARITY])
def test_35b_for_parity(m3v, tag, src):
    """stage2↔stage3 逐位一致（宿主 _emit_for_stmt reversed(var_ts) 镜像）。

    single 为零变化回归锁（UNPACK_SEQ 分支不触发既有发射路径）。"""
    _assert_parity(m3v, src)


_FOR_M3V_RUNS = [
    ("single", "s = 0\nfor x in [1, 2, 3] {\n  s = s + x\n}\n输出(s)\n", [6]),
    ("multi_dict",
     'd = {"a": 1, "b": 2}\ns = ""\nfor (k, v) in d {\n  s = s + k\n}\n输出(s)\n',
     ["ab"]),
    ("triple",
     "s = 0\nfor (a, b, c) in [[1, 2, 3], [4, 5, 6]] {\n"
     "  s = s + a * 100 + b * 10 + c\n}\n输出(s)\n",
     [579]),
    ("fn_local",
     "func f(xs) = {\n  let t = 0\n  for (a, b) in xs {\n    t = t + a + b\n  }\n"
     "  t\n}\n输出(f([[1, 2], [3, 4]]))\n",
     [10]),
    ("pair_tuples",
     "s = 0\nfor (a, b) in [(1, 2), (3, 4)] {\n  s = s + a + b\n}\n输出(s)\n",
     [10]),
]


@pytest.mark.parametrize("tag,src,want", _FOR_M3V_RUNS,
                         ids=[c[0] for c in _FOR_M3V_RUNS])
def test_35b_for_m3v_runs(m3v, tag, src, want):
    """M3V 运行面：boot 编译器 UNPACK_SEQ 发射 × vm.matha 解包守卫执行
    （正控——真跑产出，字典源 _迭代源 (k,v) 真元组对语义承继 31d）。"""
    assert _m3v_err(m3v, src) == (want, None)


def test_35x_m3v_try_catch_true(m3v):
    """真化锁（38a 捕获闭包单点包裹——35-② 退役）：m3v 面编译态 try/catch
    捕获运行期错误——除零/越界/解构失败三族消息=载体异常串，与宿主 vm
    面同源逐字一致（同一 _make_guarded_call 提供者）。未定义变量族扩锁
    与 finally/重抛/保序全族在 test_selfhost_language_phase38.py。"""
    for tag, src, want in [
        ("div0", 'try {\n  输出(1 / 0)\n} catch (e) {\n  输出(e)\n}\n',
         "除零错误: 1 / 0"),
        ("badindex", 'try {\n  let xs = [1]\n  输出(xs[5])\n} catch (e) {\n'
                     "  输出(e)\n}\n",
         "列表索引越界: 5"),
        ("unpack", 'try {\n  for (a, b) in [[1]] { 输出(a) }\n} catch (e) {\n'
                   "  输出(e)\n}\n",
         "解构失败：期望 2 个元素，实际 list"),
    ]:
        outs, err = _m3v_err(m3v, src)
        assert err is None and outs == [want], (tag, outs, err)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
