"""阶段 29c：0x62 公式模式自举贯穿锁（parser→interp→compiler→vm.matha 四面）。

29c 把宿主 `#N：？公式` 公式模式面（src/formula_schema.py +
src/mbc/compiler.py _emit_formula_schema + src/mbc/vm.py FORMULA_SCHEMA
0x62）逐层镜像进自举链四面，本档按五层锁定：

L1 stdlib helper 对拍：matha/stdlib.matha 公式_形状/公式_渲染/
  公式_收集槽位/公式_含槽（纯 Matha 镜像）与 src/formula_schema.py
  shape/render/collect_slots/has_slot 在同源公式文本上逐值相等
  （具名槽 / 匿名槽 / 具名跨出现三种形态）。
L2 stage2↔stage3 字节码对拍：公式源（登记 / 同形命中零码 / 异形求值
  编译 / 同形归并）宿主编译 ≡ compiler_matha.matha 编译（_canon 深归一
  逐位）；0x62 meta [段号, 文本, 形状, 槽位表] 双端逐项相等且槽位表与
  _fs.collect_slots 同构（宿主编译器每含槽 GenStmt 都发射一条 0x62，
  库内按形状归并——同形两条 → 2 条 0x62、除段号外逐项相等）。
L3 vm.matha 公式库槽：0x62 经 处理 98 分派登记进模块级单槽容器
  （Matha 编译器编译出的 VM 实例 + 宿主编译面同判）——同形归并计数 1
  （形状即身份，首个段号保留）、两形状计数 2、跨运行清零（运行M3V
  入口清零，宿主 VM() 每实例新库同构）。
L4 自举解释器面：interp_matha 执行语句 生成语句支——登记进 env
  __公式库__ / 命中不求值（异形才求值）/ 异形求值诚实错。直连 5 文件
  VM 驱动：matha_bootstrap.interpret 对执行异常静默回退宿主解释器
  （src/matha_bootstrap.py），直连面才看得到真实执行态。
L5 跨运行时公式库对拍：同一编译产物跑宿主 MBC VM（FormulaLibrary
  register_meta）vs Matha VM（公式库槽）——公式数相等、输出逐条相等、
  段号/形状逐项相等。

边界（登记不修 29f）：bootstrap 解释器面 注册内建/应用内建 不绑 输出
（print 经 stdlib.print 抛 "[Matha Print]"；宿主 interp.py 与 vm.py 面
均有真 输出，不受累）——故 L4 以登记/命中支的 null 返回值作哨兵、不依赖
输出面。另：顶层尾裸字面量/标识符的解析双端分歧（宿主 parser 产
GlobalIdStmt——跨文件绑定标记、语句语义 no-op、编译零码（interp.py:2439）；
bootstrap parser 产裸表达式节点——interp 求值返值 / 编译器求值+弹栈），
28b 语料零覆盖、L2/L4 源刻意不含该形态。
"""

import pytest

from src import formula_schema as _fs
from src import ast_nodes as ast
from src.kernel.errors import MathaRuntimeError, MathaUndefinedNameError
from src.mbc.compiler import Compiler, MFunction, MModule
from src.mbc.vm import VM
from src.parser import parse as py_parse

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read_source(rel):
    with open(_ROOT / rel, encoding="utf-8") as f:
        return f.read().lstrip("\ufeff")


def _compile_files(rels):
    comp = Compiler()
    decls = []
    for rel in rels:
        decls.extend(py_parse(_read_source(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


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


def _deep_list(x):
    if isinstance(x, (tuple, list)):
        return [_deep_list(v) for v in x]
    return x


def _canon(mod):
    """MModule 或自举 dict 归一为可逐位比较结构（与 28c 锁同规 +
    常量深归一——0x62 meta 宿主面为 tuple 嵌套，自举面为 list）。"""
    if isinstance(mod, MModule):
        module = mod.module_name
        constants = _deep_list(list(mod.constants))
        main = [list(i) for i in mod.main_code]
        fns = {n: [f.arity, f.nlocals, list(f.params), [list(i) for i in f.code]]
               for n, f in mod.functions.items()}
    else:
        module = mod.get("模块名", "主程序")
        constants = _deep_list(list(mod["常量"]))
        main = [list(i) for i in mod["主码"]]
        fns = {e[0]: [e[1]["元数"], e[1]["局部数"], list(e[1]["参数"]),
                      [list(i) for i in e[1]["码"]]]
               for e in mod["函数"]}
    return {"module": module, "constants": constants, "main": main, "fns": fns}


def _formula_metas(mod):
    """收集 0x62 指令引用的 meta 常量 [段号, 文本, 形状, 槽位表]。"""
    if isinstance(mod, MModule):
        consts = mod.constants
        codes = ([list(i) for i in mod.main_code]
                 + [list(i) for f in mod.functions.values() for i in f.code])
    else:
        consts = mod["常量"]
        codes = ([list(i) for i in mod["主码"]]
                 + [list(i) for e in mod["函数"] for i in e[1]["码"]])
    return [consts[i[1]] for i in codes if i[0] == 0x62]


_COMPILER_BOOT = ["matha/lexer.matha", "matha/stdlib.matha",
                  "matha/parser.matha", "matha/interp.matha",
                  "matha/compiler_matha.matha"]
_BOOTSTRAP_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
                    "matha/parser.matha", "matha/runtime/matha_runtime.matha",
                    "matha/interp_matha.matha"]
_JOINED_VM = ["matha/stdlib.matha", "matha/vm.matha"]


@pytest.fixture(scope="module")
def boot_vm():
    """bootstrap 链（interp_matha 面）+ MathaRuntimeError 注入（L1/L4）。"""
    vm = VM(_compile_files(_BOOTSTRAP_FILES).mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    return vm


@pytest.fixture(scope="module")
def cvm():
    """28c 编译链（compiler_matha 面，L2/L3/L5 的编译产物来源）。"""
    vm = VM(_compile_files(_COMPILER_BOOT).mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def vm_pair(cvm):
    """Matha 编译器编译出的 stdlib+vm.matha 实例 + 宿主编译同源实例（L3/L5）。"""
    joined = "\n".join(_read_source(p) for p in _JOINED_VM)
    inner = VM(dict_to_module(cvm.call("编译", joined)))
    inner.run()
    hostvm = VM(_compile_files(_JOINED_VM).mod)
    hostvm.run()
    return inner, hostvm


# ============================================================
# L1 stdlib helper 对拍（三种槽形态）
# ============================================================

_L1_SOURCES = [
    ("named", "#1：？单价 * ？数量 = ？总价\n1"),
    ("anon", "#1：？ * ？ = ？\n1"),
    ("named-repeat", "#1：？单价 + ？单价\n1"),
]


@pytest.mark.parametrize("label, src", _L1_SOURCES, ids=lambda x: x[0] if isinstance(x, tuple) else x)
def test_l1_stdlib_helper_parity(boot_vm, label, src):
    prog = boot_vm.call("扫描", src, 0, 1, 1, [])
    tree = boot_vm.call("parse", prog)
    d = tree["声明"][0]
    stmt = d["body"] if d["类型"] == "机械单元" else d
    content = stmt["content"]
    expr = _host_expr(src)
    assert boot_vm.call("公式_形状", content) == _fs.shape(expr)
    assert boot_vm.call("公式_渲染", content) == _fs.render(expr)
    assert (_deep_list(boot_vm.call("公式_收集槽位", content))
            == [[s.ordinal, s.name, s.display] for s in _fs.collect_slots(expr)])
    assert boot_vm.call("公式_含槽", content) == _fs.has_slot(expr)


def _host_expr(src):
    """宿主 parser 同源公式的表达式 AST（顶层 #N：？形态）。"""
    prog = py_parse(src)
    d = prog.decls[0]
    body = d.body if isinstance(d, ast.MechUnit) else d
    return body.content


# ============================================================
# L2 stage2↔stage3 字节码对拍（四面公式源）
# ============================================================

_L2_SOURCES = [
    ("register", "#1：？单价 * ？数量 = ？总价"),
    ("hit-zero-code", "#1：？单价 * ？数量 = ？总价\n#2：速度 * 时间 = 距离"),
    ("foreign-shape-eval", "#1：？单价 * ？数量 = ？总价\n#2：半径 + 补 = 圆"),
    ("same-shape-merge", "#1：？单价 * ？数量 = ？总价\n#2：？单价 * ？数量 = ？总价"),
]


@pytest.mark.parametrize("label, src", _L2_SOURCES, ids=lambda x: x[0] if isinstance(x, tuple) else x)
def test_l2_formula_bytecode_parity(cvm, label, src):
    stage3 = _canon(cvm.call("编译", src))
    stage2 = _canon(Compiler().compile_program(py_parse(src)))
    assert stage3 == stage2


def test_l2_formula_meta_fields(cvm):
    src = "#1：？单价 * ？数量 = ？总价"
    m3 = _formula_metas(cvm.call("编译", src))
    m2 = _formula_metas(Compiler().compile_program(py_parse(src)))
    assert len(m3) == 1 and len(m2) == 1
    assert _deep_list(m3[0]) == _deep_list(m2[0])
    assert m2[0][0] == 1  # 段号
    assert _deep_list(m2[0][3]) == [[s.ordinal, s.name, s.display]
                                    for s in _fs.collect_slots(_host_expr(src))]


def test_l2_same_shape_merge_two_emissions(cvm):
    src = "#1：？单价 * ？数量 = ？总价\n#2：？单价 * ？数量 = ？总价"
    m3 = _formula_metas(cvm.call("编译", src))
    m2 = _formula_metas(Compiler().compile_program(py_parse(src)))
    assert len(m3) == 2 and len(m2) == 2
    assert _deep_list(m3) == _deep_list(m2)
    assert m2[0][0] != m2[1][0]  # 段号随节点（1/2）
    assert _deep_list(m2[0][1:]) == _deep_list(m2[1][1:])  # 文本/形状/槽位逐项相等


# ============================================================
# L3 vm.matha 公式库槽（双编译面同判）
# ============================================================

_P_REG1 = "#1：？单价 * ？数量 = ？总价\n输出(41)\n"
_P_MERGE = "#1：？单价 * ？数量 = ？总价\n#2：？单价 * ？数量 = ？总价\n输出(7)\n"
_P_TWO = "#1：？a + ？b\n#2：？p * ？q\n输出(5)\n"
_P_CLEAR = "输出(42)\n"


def test_l3_vm_slot_register_dedup(cvm, vm_pair):
    d = cvm.call("编译", _P_MERGE)
    for vm in vm_pair:
        assert vm.call("运行M3V", d) == [7]
        assert vm.call("公式库计数") == 1  # 同形归并：2 条 0x62 → 1 条
        assert [m[0] for m in vm.globals["公式库槽"][0]] == [1]  # 首个段号保留


def test_l3_vm_slot_two_shapes(cvm, vm_pair):
    d = cvm.call("编译", _P_TWO)
    for vm in vm_pair:
        assert vm.call("运行M3V", d) == [5]
        assert vm.call("公式库计数") == 2
        assert [m[0] for m in vm.globals["公式库槽"][0]] == [1, 2]


def test_l3_vm_slot_clear_across_runs(cvm, vm_pair):
    d1 = cvm.call("编译", _P_REG1)
    d5 = cvm.call("编译", _P_CLEAR)
    for vm in vm_pair:
        assert vm.call("运行M3V", d1) == [41]
        assert vm.call("公式库计数") == 1
        assert vm.call("运行M3V", d5) == [42]
        assert vm.call("公式库计数") == 0  # 无公式程序：清零后无登记


# ============================================================
# L4 自举解释器面（直连 VM，绕过 matha_bootstrap 静默回退）
# ============================================================

def _run_boot(boot_vm, src):
    toks = boot_vm.call("扫描", src, 0, 1, 1, [])
    prog = boot_vm.call("parse", toks)
    env0 = boot_vm.call("注册内建", boot_vm.call("空环境"))
    return boot_vm.call("执行语句", prog, env0)


def _lib_from_env(env):
    for pair in env:
        if pair[0] == "__公式库__":
            return pair[1]
    return None


def test_l4_interp_register_and_merge(boot_vm):
    r, env = _run_boot(
        boot_vm, "#1：？单价 * ？数量 = ？总价\n#2：？单价 * ？数量 = ？总价")
    lib = _lib_from_env(env)
    assert r is None  # 登记支无值（不求值）
    assert lib is not None and len(lib) == 1  # 同形归并


def test_l4_interp_hit_no_eval(boot_vm):
    # 具体公式命中已登记模式：登记支无值且不求值——若误求值，
    # 速度/时间/距离 未定义立刻报错
    r, env = _run_boot(
        boot_vm, "#1：？单价 * ？数量 = ？总价\n#2：速度 * 时间 = 距离")
    assert r is None


def test_l4_interp_foreign_shape_honest_error(boot_vm):
    # 异形（+ 形状无 * 模式命中）→ 求值 → 未定义变量诚实错（39b 后同载体）
    with pytest.raises(MathaUndefinedNameError, match="半径"):
        _run_boot(
            boot_vm, "#1：？单价 * ？数量 = ？总价\n#2：半径 + 补 = 圆\n1")


# ============================================================
# L5 跨运行时公式库对拍（宿主 MBC VM vs Matha VM）
# ============================================================

def test_l5_cross_runtime_formula_count(cvm, vm_pair):
    inner, _ = vm_pair
    d = cvm.call("编译", _P_REG1)
    host_target = VM(dict_to_module(d))
    outs = host_target.run()
    r = inner.call("运行M3V", d)
    assert outs == r == [41]
    assert len(host_target.formulas) == inner.call("公式库计数") == 1
    sch = host_target.formulas.schemas[0]
    slot = inner.globals["公式库槽"][0][0]
    assert sch.seg_id == slot[0] and sch.shape == slot[2]


def test_l5_no_formula_zero(cvm, vm_pair):
    inner, _ = vm_pair
    d = cvm.call("编译", _P_CLEAR)
    host_target = VM(dict_to_module(d))
    outs = host_target.run()
    r = inner.call("运行M3V", d)
    assert outs == r == [42]
    assert len(host_target.formulas) == inner.call("公式库计数") == 0
