# -*- coding: utf-8 -*-
"""阶段 38 语言收敛锁（m3v 异常帧机制——35-② 真化收官）。

38a S1 载体异常→带内（捕获闭包单点包裹）：vm.matha 调用捕获器 家族此前只
  处理带内 "__抛错__"（RAISE/错误 操作码——探针取证 try{错误("boom")}
  catch → ["boom"] 现状正常），四族运行期错误（除零/越界/解构失败/
  未定义变量）以宿主 Python 异常穿透 捕获闭包 的裸 子执行调用、从
  不到达打标（35-② 登记分歧）。现 子执行经 Matha 级 调用捕获 派发到
  载体守卫（m3v 载体=宿主 VM _make_guarded_call；boot 链跑 vm.matha 时
  即 interp.py 守卫——载体无关），tagged ["__异常__", 载体异常串] 落
  带内——载体派发家族（除零/解构失败/未定义变量）消息与宿主面同源。
  捕获内建 同款守卫（应用内建 委托宿主全局可抛载体异常，合成带内
  "__抛错__" 走既有 else 臂统一打标）。带内 RAISE 路径零扰动（boom 锁
  维持）。badindex 例外——同为载体捕获，但检测点不同致文案分歧：
  m3v 下标由 vm.matha 取下标 → list_get（stdlib get 域文案「列表索引
  越界: 5」经 错误 内建抛载体异常）；vm/hi 由 INDEX_GET IndexError
  透传（「list index out of range」）——既有文案分歧见文末登记。
  实参表双包 [[…]]：invoke_value(fn, args) 按 fn(*args) 铺开实参，
  守卫 lambda 单参 p 须绑整体（首稿踩界探针抓获即修）。

窄分歧登记（KNOWN_ISSUES 阶段 38）：try 体【新建】全局名（vm.matha 设全局
  prepend 结构性）随载体异常帧丢失——catch 体读新建名报 未定义变量；
  既有名经 pair 原地变异保序（38a-6 形态锁）。带内路径（RAISE）
  子结果[3] 全保真无此分歧。宿主面无此分歧（vm.globals 真 dict 原地
  变异）。test_38a7_new_global_binding_registration 防漂移。

锁清单：38a-1 四族 vm↔m3v 捕获 parity（含 未定义变量 族扩锁；badindex
  双面各自正典文案——既有 vm↔m3v 文案分歧，见下）/ 38a-2 带内回归 boom /
  38a-3 finally 序（函数内 try/finally + 外层 catch → [1, 9, 消息]） /
  38a-4 catch 重抛（先 finally 后重抛逃逸，对齐 19c/20b 宿主形态） /
  38a-5 部分输出保序 [1, 消息] / 38a-6 既有名保序 [消息, 5] /
  38a-7 新建名分歧登记锁（m3v err vs vm [消息, 5]） / 38a-8 内层边界胜 +
  无 try 逃逸对齐（35b parity/M3V runs + 27b 边界锁在原档维持）。

badindex 文案分歧（既有，非 38 引入；KNOWN_ISSUES 阶段 38 ①）：vm/hi 面
  下标读越界透传 Python IndexError（vm.py 0x5B c[idx] 直透 + interp.py
  _eval IndexExpr container[index] 直透——「list index out of range」），
  m3v 面下标由 vm.matha 取下标 → list_get（stdlib get 域文案「列表索引
  越界: 5」经 错误 内建抛载体异常）——同一载体守卫、不同检测点。
  38a1 双面各断正典文案即防漂移锁；消息统一属 src/ 改动，登记不修。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src import ast_nodes as ast
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.kernel import exec_api

_ROOT = Path(__file__).resolve().parent.parent
_M3V_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
              "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


@pytest.fixture(scope="module")
def m3v():
    """VM² M3V 运行面（phase35 同构）：五文件自举编译器 + vm.matha。

    编译（compiler_matha）→ 运行M3V（vm.matha 捕获闭包 载体守卫执行面）。"""
    comp = Compiler()
    decls = []
    for rel in _M3V_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _m3v_err(m3v, src):
    try:
        d = m3v.call("编译", src)
        return list(m3v.call("运行M3V", d)), None
    except Exception as e:  # noqa: BLE001
        return None, e


# 四族源 + 双面期望 catch 消息。除 badindex 外 vm/m3v 同文案（载体派发
# 家族消息与宿主面同源）；badindex 既有分歧见模块 docstring 与 KNOWN_ISSUES ①。
_FAMILIES = [
    ("div0", 'try {\n  输出(1 / 0)\n} catch (e) {\n  输出(e)\n}\n',
     "除零错误: 1 / 0", "除零错误: 1 / 0"),
    ("badindex", 'try {\n  let xs = [1]\n  输出(xs[5])\n} catch (e) {\n'
                 '  输出(e)\n}\n',
     "list index out of range", "列表索引越界: 5"),
    ("unpack", 'try {\n  for (a, b) in [[1]] { 输出(a) }\n} catch (e) {\n'
               "  输出(e)\n}\n",
     "解构失败：期望 2 个元素，实际 list", "解构失败：期望 2 个元素，实际 list"),
    ("undef", "try {\n  输出(不存在的名字)\n} catch (e) {\n  输出(e)\n}\n",
     "未定义变量 '不存在的名字'", "未定义变量 '不存在的名字'"),
]


# ============================================================
# 38a-1 四族 vm↔m3v 捕获 parity（35-② 退役主锁）
# ============================================================

@pytest.mark.parametrize("tag,src,vm_want,m3v_want", _FAMILIES,
                         ids=[c[0] for c in _FAMILIES])
def test_38a1_family_vm_m3v_parity(m3v, tag, src, vm_want, m3v_want):
    """四族运行期错误 m3v 编译态捕获 + 输出 [消息]；vm 面同捕获。除
    badindex（既有文案分歧，双面各断正典文案即防漂移）外消息同源
    （除零/解构失败经宿主 VM 运算与 UNPACK_SEQ、未定义变量经载体守卫）。"""
    vo, verr = exec_api.run_checked(src)
    assert verr is None and vo == [vm_want], (tag, "vm", vo, verr)
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == [m3v_want], (tag, "m3v", outs, err)


# ============================================================
# 38a-2 带内回归：RAISE（错误()）原路径零扰动
# ============================================================

def test_38a2_raise_in_band_regression(m3v):
    """带内 "__抛错__"（RAISE 操作码）在载体守卫包裹下原路径不变——
    捕获闭包 分支 子结果 = 守卫[1] 透传（探针取证修复前已绿）。"""
    src = 'try {\n  错误("boom")\n} catch (e) {\n  输出(e)\n}\n'
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == ["boom"], (outs, err)


# ============================================================
# 38a-3 finally 序：函数内 try/finally + 外层 catch → [1, 9, 消息]
# ============================================================

def test_38a3_finally_order_through_function(m3v):
    """无 catch try/finally 先 finally 后重抛（19c/20b 宿主同构）：重抛
    越函数帧被外层 调用捕获 边界捕获——输出 [1, 9, 消息] 保序。"""
    src = ('func f() = {\n  try {\n    输出(1)\n    1 / 0\n  } finally {\n'
           '    输出(9)\n  }\n}\n'
           'try {\n  f()\n} catch (e) {\n  输出(e)\n}\n')
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == [1, 9, "除零错误: 1 / 0"], (outs, err)


# ============================================================
# 38a-4 catch 重抛：先 finally 后重抛逃逸（宿主 uncaught 面对齐）
# ============================================================

def test_38a4_catch_reraise_escapes(m3v):
    """catch 体 错误("re: "+e) → 先 finally（输出 2 已发射至输出指针）
    后重抛——重抛消息逃逸至边界（27b 运行M3V 真抛面对齐宿主）。"""
    src = ('try {\n  1 / 0\n} catch (e) {\n  错误("re: " + e)\n} finally {\n'
           '  输出(2)\n}\n')
    outs, err = _m3v_err(m3v, src)
    assert err is not None and "re: 除零错误: 1 / 0" in str(err), (outs, err)


# ============================================================
# 38a-5 部分输出保序：错误前已发射输出在 catch 面可见
# ============================================================

def test_38a5_partial_outputs_preserved(m3v):
    """try 体 输出(1) 先落输出指针（共享可变），错误后 catch 面保序
    [1, 消息]——对齐宿主 _partial_outputs 语义（20b 锁同形）。"""
    src = 'try {\n  输出(1)\n  输出(1 / 0)\n} catch (e) {\n  输出(e)\n}\n'
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == [1, "除零错误: 1 / 0"], (outs, err)


# ============================================================
# 38a-6 既有名保序：设全局 pair 原地变异穿透载体异常帧
# ============================================================

def test_38a6_existing_global_update_survives(m3v):
    """try 体更新【既有】全局名（x = 5）——设全局 命中 pair 原地变异
    （vm.matha 原地设置(全局[0], 1, 值)），载体异常帧不影响入口 全局
    所持同一 pair 对象——catch 面 [消息, 5] 保序。"""
    src = ('x = 0\ntry {\n  x = 5\n  输出(1 / 0)\n} catch (e) {\n'
           "  输出(e)\n  输出(x)\n}\n")
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == ["除零错误: 1 / 0", 5], (outs, err)


# ============================================================
# 38a-7 新建名分歧登记锁（登记不修——KNOWN_ISSUES 阶段 38 ①）
# ============================================================

def test_38a7_new_global_binding_registration(m3v):
    """登记锁（38a 单点包裹窄分歧）：try 体【新建】全局名（设全局
    prepend 结构性建链）随载体异常帧丢失——catch 体读 y 报 未定义变量
    'y'（经 catch 体自身载体守卫 → 先 finally 后重抛逃逸）；vm 面同源
    无此分歧（[消息, 5]）。修复需 全局 表共享可变槽化（输出指针 同款
    原地协议），登记不修。"""
    src = ('try {\n  y = 5\n  输出(1 / 0)\n} catch (e) {\n  输出(e)\n'
           "  输出(y)\n}\n")
    vo, verr = exec_api.run_checked(src)
    assert verr is None and vo == ["除零错误: 1 / 0", 5], ("vm", vo, verr)
    outs, err = _m3v_err(m3v, src)
    assert err is not None and "未定义变量 'y'" in str(err), ("m3v", outs, err)


# ============================================================
# 38a-8 内层边界胜 + 无 try 逃逸对齐
# ============================================================

def test_38a8_nested_try_inner_boundary_wins(m3v):
    """嵌套 try：内层 调用捕获 边界先捕（内层子执行在守卫 lambda 内层
    invoke_value）——外层 catch 不触发。"""
    src = ('try {\n  try {\n    输出(1 / 0)\n  } catch (e) {\n'
           '    输出("inner:" + e)\n  }\n} catch (e2) {\n'
           '  输出("outer:" + e2)\n}\n')
    outs, err = _m3v_err(m3v, src)
    assert err is None and outs == ["inner:除零错误: 1 / 0"], (outs, err)


def test_38a8_uncaught_still_escapes(m3v):
    """无 try 直跑错误照逃逸（27b 运行M3V 真抛面不变——捕获守卫只在
    调用捕获 边界生效，不吞顶层错误）。"""
    outs, err = _m3v_err(m3v, "输出(1 / 0)\n")
    assert err is not None and "除零错误: 1 / 0" in str(err), (outs, err)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
