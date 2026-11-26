# -*- coding: utf-8 -*-
"""阶段 39 语言收敛锁（Track B both_err 归因批——31-⑧ 退役 + 判定面细分）。

方向 A 拍板：逐个归因 Track B 13 both_err 语料，清零或如实登记为边界。
本片落地面：

39a 链面应用分派收口（boot 面 bootstrap_test 根因族）：
  ① λ-AST 字典应用臂——interp_matha.matha/interp.matha 应用函数·应用多参数函数
     的 Dict 臂此前只认 "__builtin__"，裸 λ 节点字典（语法器.做Lambda 产物，
     bootstrap_test 3.6/3.7/3.9 直调链 API 形态）落「不可调用的值」——现经
     求值lambda 折闭包重入 __closure__ 机制（柯里化/多参同臂复用）。
  ② 不可调用值渲染载体——宿主 f"{func!r}"（src/interp.py、src/mbc/vm.py）vs
     链面 标准库.str（字符串无引号）→ 双端消息不同。改用 标准库.元素repr
     （CPython repr 规则，非字符串委托 str）：str/空串/int/列表/CJK/转义六形态
     vm/hi/mb/bootvm 四面逐字同判；闭包与既有锁（': 5' / ': []'）零扰动。
  ③ interp.matha 零参闭包守卫——做Lambda([], body) 的 params[0] 无守卫落原生
     IndexError；镜像 interp_matha 29d 同口径（空参数表忽略 IntLit(0) 占位）。

39b 未定义变量异常类真化（31-⑧ 退役）：链面 查找环境/查找环境链/查找环境 缺名
  臂此前经 错误 抛 MathaRuntimeError，宿主 _eval_variable / _GlobalScope.__missing__
  抛 MathaUndefinedNameError——双端 boot_err/host_err 串首差即类名。新增类型化
  抛错内建 未定义错误（src/interp.py BUILTINS + src/mbc/vm.py _default_builtins
  同类抛错，消息逐字不变），链面缺名臂裸名调用改走该内建。39b-2 延伸到
  vm.matha 查全局：内建名表补注册（防 查全局 自递归）+ 内建特殊 带内臂 +
  应用内建 专用名守卫补名——m3v 面未定义变量边界异常类归一
  MathaUndefinedNameError，捕获面带内消息不变。

39c/39d 语料与源序：bootstrap_matha.matha 刷新到现行柯里化 API（词法器.扫描(s)(0)
  (1)(1)([])）；compiler_matha.matha 的 不折叠 模块级 let 前移至模块顶（宿主闭包
  按定义序快照环境，后定义模块级 let 对先定义函数不可见——bootstrap_full_test
  host 面首错名 '不折叠' 根因），本地 dict_from_pairs 十行副本退役为
  use 标准库 导入（消除双源漂移面）。

39e 判定面细分：_classify 双 err 条目 boot_err == host_err（类名+消息逐字全等）
  → both_err_equal（双面同判的诚实边界，与"分歧残留" both_err 分列）；
  summary 七分类键；structure_check 缺键诚实报「需 --write 重生成」。

登记不修（KNOWN_ISSUES 阶段 39）：加载模块 胶水返回形状
  （hi bool vs VM 面 list[str]，boot/host 面同源不进 Track B）、
  m3v 面直接调用 未定义错误 逃逸边界经 运行M3V 的 错误 转宿主
  MathaRuntimeError（带内通道无类型载体）。
  （原「三引号字符串双端词法器均不支持」条由阶段 40a 真化退役，
  39c 根因锁相应改锁为真跑值锁。）
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src import interp as host_interp
from src import matha_bootstrap
from src.interp import Interpreter
from src.kernel import exec_api
from src.kernel.errors import MathaRuntimeError, MathaUndefinedNameError

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_INTERP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
                 "matha/interp.matha"]
_M3V_FILES = _INTERP_FILES + ["matha/compiler_matha.matha", "matha/vm.matha"]
_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _compile_chain(files):
    comp = Compiler()
    decls = []
    for rel in files:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    return vm


@pytest.fixture(scope="module")
def bootvm():
    """VM² 解释器面（interp_matha 五文件链）——λ-dict 臂宿主面。"""
    vm = _compile_chain(_BOOT_FILES)
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


@pytest.fixture(scope="module")
def interpvm():
    """interp.matha 镜像面（四文件链宿主编译为 M3V）——双臂镜像锁宿主。"""
    return _compile_chain(_INTERP_FILES)


@pytest.fixture(scope="module")
def freshchain():
    """fresh 链（宿主 hi 面装载 interp.matha）——镜像臂的 hi 面锁。"""
    it = Interpreter()
    assert it.load_matha_module("解释器")
    return it


@pytest.fixture(scope="module")
def m3v():
    """M3V 运行面（六文件链）：自举编译器 编译 + vm.matha 运行M3V。"""
    return _compile_chain(_M3V_FILES)


def _boot_run(vm, src):
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env = vm.call("注册内建", vm.call("空环境"))
    for nm, ns in vm._chain_nss.items():
        env = vm.call("绑定环境", env, nm, ns)
    vm.call("执行语句", prog, env)
    return list(vm.call("输出快照"))


def _boot_err(vm, src):
    try:
        return _boot_run(vm, src), None
    except Exception as e:  # noqa: BLE001
        return None, e


def _hi_run(src):
    try:
        outs, _ = host_interp.interpret(src)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _mb_run(src):
    try:
        outs, _ = matha_bootstrap.interpret(src, strict=True)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _err_str(exc):
    return f"{type(exc).__name__}: {exc}"


def _m3v_run(vm, src):
    d = vm.call("编译", src)
    return list(vm.call("运行M3V", d))


# ============================================================
# 39a-1 λ-AST 字典应用臂（interp_matha 面 + interp.matha 双臂镜像）
# ============================================================

_LAM_DICT = '''
env = 解释器.注册内建(解释器.空环境())
lam = 语法器.做Lambda([语法器.做Variable("x")],
  语法器.做BinaryOp("+", 语法器.做Variable("x"), 语法器.做IntLit(1)))
env1 = 解释器.绑定环境(env, "加一", lam)
输出(解释器.求值(语法器.做FuncApp(语法器.做Variable("加一"), 语法器.做IntLit(5)), env1))
curry = 语法器.做Lambda([语法器.做Variable("a"), 语法器.做Variable("b")],
  语法器.做BinaryOp("+", 语法器.做Variable("a"), 语法器.做Variable("b")))
env2 = 解释器.绑定环境(env, "加", curry)
输出(解释器.求值(语法器.做FuncApp(语法器.做FuncApp(语法器.做Variable("加"), 语法器.做IntLit(3)), 语法器.做IntLit(5)), env2))
'''

_LAM_NEG = '''
env = 解释器.注册内建(解释器.空环境())
bad = 语法器.做IntLit(7)
输出(解释器.求值(语法器.做FuncApp(bad, 语法器.做IntLit(1)), env))
'''


def test_39a1_lam_dict_apply_bootvm(bootvm):
    """裸 λ 节点字典直调链 API：单参 λ → 6、柯里化双参 λ → 8（此前
    「不可调用的值: {...}」——bootstrap_test 3.6/3.7/3.9 形态根因）。"""
    outs, err = _boot_err(bootvm, _LAM_DICT)
    assert err is None and outs == [6, 8], (outs, err)


def test_39a1_lam_dict_negative_bootvm(bootvm):
    """负控：非 λ 字典（整数节点）仍诚实拒绝——整数节点渲染为 7。"""
    outs, err = _boot_err(bootvm, _LAM_NEG)
    assert err is not None and "不可调用的值: 7" in str(err), (outs, err)


def interp_app(vm, name, arg):
    """AST 应用节点构造子（interp.matha 面直调）。"""
    return vm.call("做FuncApp", vm.call("做Variable", name),
                   vm.call("做IntLit", arg))


def test_39a1_lam_dict_mirror_faces(interpvm):
    """interp.matha 双臂镜像（VM² 面）：单参 6 / 柯里化 8 / 零参 42 同判；
    负控整数节点字典仍诚实拒绝。"""
    vm = interpvm
    env = vm.call("注册内建", vm.call("空环境"))
    var_x = vm.call("做Variable", "x")
    lam = vm.call("做Lambda", [var_x],
                  vm.call("做BinaryOp", "+", var_x, vm.call("做IntLit", 1)))
    one = vm.call("求值", interp_app(vm, "加一", 5),
                  vm.call("绑定环境", env, "加一", lam))
    va, vb = vm.call("做Variable", "a"), vm.call("做Variable", "b")
    curry = vm.call("做Lambda", [va, vb], vm.call("做BinaryOp", "+", va, vb))
    two = vm.call("求值",
                  vm.call("做FuncApp", interp_app(vm, "加", 3),
                          vm.call("做IntLit", 5)),
                  vm.call("绑定环境", env, "加", curry))
    zero = vm.call("做Lambda", [], vm.call("做IntLit", 42))
    thr = vm.call("求值", interp_app(vm, "四二", 0),
                  vm.call("绑定环境", env, "四二", zero))
    assert (one, two, thr) == (6, 8, 42), (one, two, thr)
    env_bad = vm.call("绑定环境", env, "坏", vm.call("做IntLit", 7))
    with pytest.raises(MathaRuntimeError, match="不可调用的值"):
        vm.call("求值", interp_app(vm, "坏", 1), env_bad)


def _ast_lam_forms_fresh(it):
    """宿主装载链（hi 面 interp.matha 镜像臂）：单参 λ → 6、零参 λ → 42，
    整数节点直调诚实拒绝捕获 err。"""
    mod = it.modules["解释器"]
    pmod = it.modules["语法器"]

    def c(m, fn, *a):
        return it._call_func_or_closure(m[fn], list(a))

    env = c(mod, "注册内建", [])
    var_x = c(pmod, "做Variable", "x")
    lam = c(pmod, "做Lambda", [var_x],
            c(pmod, "做BinaryOp", "+", var_x, c(pmod, "做IntLit", 1)))
    env1 = c(mod, "绑定环境", env, "加一", lam)
    one = c(mod, "求值", c(pmod, "做FuncApp", c(pmod, "做Variable", "加一"),
                          c(pmod, "做IntLit", 5)), env1)
    zero = c(pmod, "做Lambda", [], c(pmod, "做IntLit", 42))
    env2 = c(mod, "绑定环境", env, "四二", zero)
    thr = c(mod, "求值", c(pmod, "做FuncApp", c(pmod, "做Variable", "四二"),
                          c(pmod, "做IntLit", 0)), env2)
    bad = c(mod, "绑定环境", env, "坏", c(pmod, "做IntLit", 7))
    err = None
    try:
        c(mod, "求值", c(pmod, "做FuncApp", c(pmod, "做Variable", "坏"),
                        c(pmod, "做IntLit", 1)), bad)
    except Exception as e:  # noqa: BLE001
        err = e
    return one, thr, err


def test_39a1_lam_dict_fresh_chain(freshchain):
    """interp.matha 镜像臂 hi 面（宿主装载链）：单参 6 + 零参 42 +
    负控诚实拒绝——与 VM² 面同判。"""
    one, thr, err = _ast_lam_forms_fresh(freshchain)
    assert (one, thr) == (6, 42), (one, thr)
    assert err is not None and "不可调用的值" in str(err), err


def test_39a1_lam_dict_interpmatha_arm_present():
    """结构锁：双链文件 λ-dict 臂在场（"lambda" 判定 + 求值lambda 重入）。"""
    for rel in ("matha/interp_matha.matha", "matha/interp.matha"):
        text = (_ROOT / rel).read_bytes().decode("utf-8")
        assert '"lambda" then' in text or "= \"lambda\"" in text, rel
        assert "求值lambda" in text, rel


# ============================================================
# 39a-2 不可调用值渲染载体对齐（元素repr ↔ 宿主 {func!r}）
# ============================================================

_REPR_FORMS = [
    ("str", 'let s = "abc" in 输出(s(1))', "不可调用的值: 'abc'"),
    ("empty_str", 'let s = "" in 输出(s(1))', "不可调用的值: ''"),
    ("int", "输出(5(1))", "不可调用的值: 5"),
    ("list", "输出([](1))", "不可调用的值: []"),
    ("cjk", 'let s = "中" in 输出(s(1))', "不可调用的值: '中'"),
    ("escaped", 'let s = "a\\nb" in 输出(s(1))', "不可调用的值: 'a\\nb'"),
]


@pytest.mark.parametrize("tag,src,want", _REPR_FORMS,
                         ids=[c[0] for c in _REPR_FORMS])
def test_39a2_uncallable_repr_four_faces(bootvm, tag, src, want):
    """六形态 vm/hi/mb/bootvm 四面消息逐字同判——字符串带引号、容器/整数
    不带（既有锁 ': 5' / ': []' 零扰动）。"""
    _, verr = exec_api.run_checked(src)
    assert verr is not None and str(verr) == want, (tag, "vm", verr)
    _, hi_err = _hi_run(src)
    assert hi_err is not None and _err_str(hi_err) == \
        f"MathaRuntimeError: {want}", (tag, "hi", hi_err)
    _, mb_err = _mb_run(src)
    assert mb_err is not None and _err_str(mb_err) == \
        f"MathaRuntimeError: {want}", (tag, "mb", mb_err)
    _, b_err = _boot_err(bootvm, src)
    assert b_err is not None and _err_str(b_err) == \
        f"MathaRuntimeError: {want}", (tag, "bootvm", b_err)


def test_39a2_element_repr_wired_in_chain_sources():
    """结构锁：链面渲染载体改尽——interp_matha 8 处、interp.matha 4 处
    元素repr(f)，且 interp.matha use 标准库 行含 元素repr。"""
    im = (_ROOT / "matha/interp_matha.matha").read_text(encoding="utf-8")
    ip = (_ROOT / "matha/interp.matha").read_text(encoding="utf-8")
    assert im.count("标准库.元素repr(f)") == 8, im.count("标准库.元素repr(f)")
    assert ip.count("元素repr(f)") == 4, ip.count("元素repr(f)")
    use_line = [ln for ln in ip.splitlines() if "use 标准库 {" in ln][0]
    assert "元素repr" in use_line, use_line
    assert "标准库.str(f)" not in im and "str(f)" not in ip.split("func 应用函数")[1]


# ============================================================
# 39a-3 零参闭包守卫（interp.matha 镜像补齐）
# ============================================================

def test_39a3_zero_param_lambda_three_faces():
    """源级零参 λ 三面同判（() => 5 折 IntLit(0) 占位调用约定）。"""
    src = "let f = () => 5 in 输出(f())"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [5], ("vm", outs, err)
    hi, hi_err = _hi_run(src)
    assert hi_err is None and hi == [5], ("hi", hi, hi_err)
    mb, mb_err = _mb_run(src)
    assert mb_err is None and mb == [5], ("mb", mb, mb_err)


def test_39a3_zero_param_lambda_interp_mirror_vm2(interpvm):
    """interp.matha 面零参守卫（VM²）：做Lambda([], 42) 应用 → 42，
    此前 params[0] 落原生 IndexError。"""
    env = interpvm.call("注册内建", interpvm.call("空环境"))
    zero = interpvm.call("做Lambda", [], interpvm.call("做IntLit", 42))
    env1 = interpvm.call("绑定环境", env, "四二", zero)
    got = interpvm.call("求值", interpvm.call(
        "做FuncApp", interpvm.call("做Variable", "四二"),
        interpvm.call("做IntLit", 0)), env1)
    assert got == 42, got


# ============================================================
# 39b 未定义变量类型化抛错（31-⑧ 退役）
# ============================================================

_UNDEF_FORMS = [
    ("undef_name", "输出(缺失变量名)", "未定义变量 '缺失变量名'"),
    ("undef_func", "未知函数(1)", "未定义变量 '未知函数'"),
]


@pytest.mark.parametrize("tag,src,want", _UNDEF_FORMS,
                         ids=[c[0] for c in _UNDEF_FORMS])
def test_39b1_undefined_name_carrier_four_faces(bootvm, tag, src, want):
    """未定义变量四面同载体 MathaUndefinedNameError + 同消息（31-⑧ 退役）——
    此前 mb/bootvm 抛 MathaRuntimeError，Track B boot_err/host_err 首差即类名。"""
    _, verr = exec_api.run_checked(src)
    assert isinstance(verr, MathaUndefinedNameError) and str(verr) == want, \
        (tag, "vm", verr)
    for face, (outs, err) in (("hi", _hi_run(src + "\n")),
                              ("mb", _mb_run(src + "\n")),
                              ("bootvm", _boot_err(bootvm, src + "\n"))):
        assert isinstance(err, MathaUndefinedNameError), (tag, face, type(err), err)
        assert _err_str(err) == f"MathaUndefinedNameError: {want}", (tag, face, err)
        assert outs is None, (tag, face, outs)


def test_39b1_undefined_name_is_runtime_subclass():
    """异常类层级锁：MathaUndefinedNameError ⊂ MathaRuntimeError——既有按父类
    断言的锁（phase8a/8pre/formula29）继续成立，改锁仅收紧不放宽。"""
    assert issubclass(MathaUndefinedNameError, MathaRuntimeError)
    assert issubclass(MathaUndefinedNameError, KeyError)


def test_39b1_golden_undef_cases_same_string(bootvm):
    """golden 13/31（未定义变量/未定义函数）hi 面与 bootvm 面错误串逐字相等
    ——Track B 该两条目由 both_err 转 both_err_equal 的直接语言级锁。"""
    for rel in ("golden_tests/cases/13_error_undefined.matha",
                "golden_tests/cases/31_error_undef_func.matha"):
        src = (_ROOT / rel).read_text(encoding="utf-8")
        _, hi_err = _hi_run(src)
        _, b_err = _boot_err(bootvm, src)
        assert hi_err is not None and b_err is not None, rel
        assert _err_str(hi_err) == _err_str(b_err), (rel, _err_str(hi_err),
                                                     _err_str(b_err))


def test_39b_builtin_registered_both_hosts():
    """注册锁：未定义错误 内建在 hi BUILTINS 与 VM 默认内建表在场（裸名调用
    经 builtins 回退 / LOAD_GLOBAL 命中），且同列 28d 插口保留名——插件注册
    遮蔽即异常类口径漂移，四面（hi/VM/vm.matha）一致诚实拒绝。"""
    from src.interp import BUILTINS, Interpreter
    from src.mbc.vm import VM, _default_builtins
    assert "未定义错误" in BUILTINS
    assert "未定义错误" in _default_builtins()
    assert "未定义错误" in Interpreter._RESERVED_BUILTINS
    assert "未定义错误" in VM._RESERVED_BUILTINS
    with pytest.raises(MathaUndefinedNameError, match="手工"):
        BUILTINS["未定义错误"]("手工")


# ---------- 39b-2 m3v 面（vm.matha 查全局 + 带内通道） ----------

def test_39b2_m3v_undefined_name_carrier(m3v):
    """m3v 面未定义变量边界异常类归一（39b-2）：未捕获 → 宿主面同载体
    MathaUndefinedNameError + 同消息。"""
    for src, want in (("输出(缺失变量名)\n", "未定义变量 '缺失变量名'"),
                      ("未知函数(3)\n", "未定义变量 '未知函数'")):
        with pytest.raises(MathaUndefinedNameError) as ei:
            _m3v_run(m3v, src)
        assert str(ei.value) == want, (src, _err_str(ei.value))


def test_39b2_m3v_undefined_name_caught_in_band(m3v):
    """m3v 面 try/catch 捕获未定义变量：带内消息逐字不变（38a 载体守卫
    家族），捕获面输出 [消息]。"""
    src = 'try {\n  输出(缺失变量名)\n} catch (e) {\n  输出(e)\n}\n'
    assert _m3v_run(m3v, src) == ["未定义变量 '缺失变量名'"], src


def test_39b2_m3v_undefined_error_builtin_in_band(m3v):
    """带内通道锁：目标源码直调 未定义错误 → vm.matha 内建特殊 臂命中
    （应用内建 专用名守卫含 未定义错误），抛错带内传播后 运行M3V 边界转
    宿主 错误（登记边界：边界类为 MathaRuntimeError，消息逐字不变）。"""
    with pytest.raises(MathaRuntimeError) as ei:
        _m3v_run(m3v, '输出(未定义错误("手工"))\n')
    assert str(ei.value) == "手工", _err_str(ei.value)
    assert not isinstance(ei.value, MathaUndefinedNameError)


def test_39b2_vm_matha_registration_present():
    """结构锁：未定义错误 进 vm.matha 内建名表（防 查全局 缺名臂自递归）、
    查全局 缺名臂走 未定义错误，且 应用内建 专用名守卫与 是保留内建名
    插口保留名单同判含该名（守卫先于插口分派，注册必被遮蔽——诚实拒绝）。"""
    text = (_ROOT / "matha/vm.matha").read_text(encoding="utf-8")
    assert '"未定义错误",' in text, "内建名表未注册"
    app_body = text.split("func 应用内建")[1].split("func ")[0]
    guard = [ln for ln in app_body.splitlines() if '内建特殊(名, 参数' in ln]
    assert guard and "未定义错误" in guard[0], app_body
    keep_body = text.split("func 是保留内建名")[1].split("func ")[0]
    assert "未定义错误" in keep_body, keep_body
    body = text.split("func 查全局")[1].split("func ")[0]
    # 每条「未定义变量 …」消息都经类型化抛错内建构造，无裸 错误() 残留臂
    assert body.count('错误("未定义变量') == \
        body.count('未定义错误("未定义变量') == 1, body


# ============================================================
# 39c/39d 语料刷新 + compiler_matha 源序
# ============================================================

def test_39d_compiler_matha_dict_from_pairs_imported():
    """39d：本地 dict_from_pairs 十行副本退役——改由 use 标准库 导入
    （消除 stdlib/compiler_matha 双源漂移面）。"""
    text = (_ROOT / "matha/compiler_matha.matha").read_bytes().decode("utf-8")
    assert "func dict_from_pairs" not in text, "副本仍在（应导入 stdlib 版）"
    use_line = [ln for ln in text.splitlines() if "use 标准库 {" in ln][0]
    assert "dict_from_pairs" in use_line, use_line
    assert "dict_from_pairs(" in text, "调用点缺失"


def test_39d_nofold_hoist_precedes_first_func():
    """39d 根因锁：不折叠 模块级 let 前移至首个 func 之前——宿主闭包按
    定义序快照环境，后定义的模块级 let 对先定义函数不可见
    （bootstrap_full_test host 面首错名 '不折叠'）。"""
    text = (_ROOT / "matha/compiler_matha.matha").read_bytes().decode("utf-8")
    hoist = text.index('let 不折叠 = "')
    first_func = text.index("func ")
    assert hoist < first_func, (hoist, first_func)


def test_39c_bootstrap_matha_corpus_two_faces_ok():
    """39c：bootstrap_matha 语料刷新到现行柯里化 API——hi/官方门面双跑通，
    四输出前 3 项同源（第 4 项为 加载模块 胶水形状，见登记锁）。"""
    rel = "matha/bootstrap_matha.matha"
    src = (_ROOT / rel).read_text(encoding="utf-8")
    hi, hi_err = _hi_run(src)
    vo, verr = exec_api.run_file_checked(_ROOT / rel)
    assert hi_err is None and verr is None, (hi_err, verr)
    assert len(hi) == len(vo) == 4, (hi, vo)
    assert hi[:3] == vo[:3], (hi, vo)


def test_39c_bootstrap_full_test_corpus_two_faces_equal():
    """39d 效果锁：bootstrap_full_test 宿主面不再首错 不折叠——hi/官方门面
    双面 22 输出逐字相等（此前 host 面首错名 '不折叠'）。"""
    rel = "matha/bootstrap_full_test.matha"
    src = (_ROOT / rel).read_text(encoding="utf-8")
    hi, hi_err = _hi_run(src)
    vo, verr = exec_api.run_file_checked(_ROOT / rel)
    assert hi_err is None and verr is None, (hi_err, verr)
    assert len(hi) == len(vo) == 22, (len(hi), len(vo))
    assert [repr(x) for x in hi] == [repr(x) for x in vo], (hi, vo)


def test_39c_bootstrap_test_triple_quote_true():
    """39-① 真化（阶段 40a）：三引号字符串双端词法器落地——同形源双面
    真跑得值（此前双端同判「不可调用的值: ''」登记不修）。"""
    src = 'let s = """a""" in 输出(s)\n'
    vo, verr = exec_api.run_checked(src)
    hi, hi_err = _hi_run(src)
    assert (vo, verr) == (["a"], None) and hi == ["a"], (vo, verr, hi)


# ============================================================
# 39e 判定面细分（both_err_equal vs both_err）
# ============================================================

def _sm():
    from scripts import selfhost_matrix as sm
    return sm


def test_39e_classify_both_err_equal_and_differ():
    """_classify 细分：双 err 且 boot_err == host_err → both_err_equal；
    类名/消息任一不同 → both_err（残留分歧面）。"""
    sm = _sm()
    same = {"boot": "err", "host": "err",
            "boot_err": "MathaUndefinedNameError: 未定义变量 'x'",
            "host_err": "MathaUndefinedNameError: 未定义变量 'x'"}
    diff = {"boot": "err", "host": "err",
            "boot_err": "MathaRuntimeError: 未定义变量 'x'",
            "host_err": "MathaUndefinedNameError: 未定义变量 'x'"}
    assert sm._classify(same) == "both_err_equal", same
    assert sm._classify(diff) == "both_err", diff


def test_39e_summary_seven_keys_arithmetic_closed():
    """summary 键形：七分类键（含 both_err_equal）+ 计数算术闭合。

    46c 起 summarize 另带**内嵌** `power` 节（both_ok_equal 的 obs/silent 分层）：
    它不参与对 files 的闭合求和，只与 both_ok_equal 自身闭合。
    """
    sm = _sm()
    entries = [
        {"boot": "ok", "host": "ok", "equal": True},
        {"boot": "ok", "host": "ok", "equal": False},
        {"boot": "err", "host": "err", "boot_err": "E", "host_err": "E"},
        {"boot": "err", "host": "err", "boot_err": "A", "host_err": "B"},
        {"boot": "err", "host": "ok"},
        {"boot": "ok", "host": "err"},
        {"boot": "timeout", "host": "timeout"},
    ]
    s = sm.summarize(entries)
    assert set(s.keys()) == {"files"} | set(sm._SUMMARY_KEYS) | {"power"}, s
    assert s["files"] == len(entries)
    scalar = {k: v for k, v in s.items() if not isinstance(v, dict)}
    assert sum(v for k, v in scalar.items() if k != "files") == s["files"], s
    assert s["both_err_equal"] == 1 and s["both_err"] == 1, s
    # entries 里那条 both_ok_equal 无 n_outs（=0）→ 全计 silent
    assert s["power"] == {"both_ok_equal_obs": 0, "both_ok_equal_silent": 1}, s


def test_39e_structure_check_honest_on_stale_keys(monkeypatch, tmp_path):
    """structure_check 缺键诚实：39e 细分后旧快照（无 both_err_equal）不再
    KeyError，而是报「需 --write 重生成」。"""
    sm = _sm()

    class _Exists:
        def exists(self):
            return True

    snap = {"enumerated": 1,
            "files": [{"path": "a.matha", "boot": "err", "host": "err",
                       "boot_err": "X", "host_err": "X"}],
            "summary": {"files": 1, "both_ok_equal": 0, "both_ok_differ": 0,
                        "boot_err_host_ok": 0, "boot_ok_host_err": 0,
                        "both_err": 1, "timeout": 0}}
    monkeypatch.setattr(sm, "SNAPSHOT", _Exists())
    monkeypatch.setattr(sm, "load_snapshot", lambda: snap)
    monkeypatch.setattr(sm, "corpus_files", lambda: ["a.matha"])
    ok, msg = sm.structure_check()
    assert ok is False and "缺分类键" in msg and "--write" in msg, (ok, msg)
