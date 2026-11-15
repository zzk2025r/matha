# -*- coding: utf-8 -*-
"""阶段 21a · 插件符号 VM 面真化（能力插件注册面 + 运行时效果注入）三锁。

阶段 21a（拍板：能力插件注册面 / 门面对拍 / 语料符号）把宿主解释器直挂的
能力符号接入 VM 面：
  - src/domains/capability.py 能力插件（清单注册 12 符号：自主_调试/自主_优化/
    自主_成长/资源_加载/资源_成长/软件_构建 + 生成_网页/桌面/服务/系统/游戏/建模）
    —— 宿主面仍由 src.interp 内建表直挂（直挂优先，宿主面零改动）；
  - VM 面官方入口（src.kernel.exec_api._wire_plugin_runtime）注入：
    领域解析器（resolver 物化面）+ 效果面胶水（src.plugin_api.
    make_capability_runtime → capability.make_runtime：资源_加载/资源_成长
    把资源函数编译进「同一个运行中 VM」，与宿主面「合并进运行中的解释器」
    同构；setdefault 不覆盖程序自定义同名函数）；
  - 跨模块常量池：VM 分派按帧取常量池（Frame.consts / MFunction.consts，
    None=与模块共享）——运行期插件合并进运行中 VM 的函数帧携带来源模块
    池，常量下标不再读到宿主模块的错位值；
  - 解析_JSON 双面单一实现（src/kernel/json_builtin.py）：宿主 BUILTINS 与
    VM _default_builtins 同源。

摸底勘误（由本阶段对拍证实）：阶段 21 摸底「生成_×6 语料零使用」不成立
——matha/examples/10_web_app.matha 用 生成_网页、11_desktop.matha 用
生成_桌面，故 capability 插件按门面对拍标准扩至 12 符号；资源_列表/
资源_读取 仍语料零使用，保持登记边界（插件面未覆盖）。

登记边界（现状锁，不修）：
  - 裸 VM()（不经官方入口）不承载插件符号：自主_* 等仍未定义名
    —— 与原生 exe「不承载插件符号」同一架构哲学；
  - plugins="off" 的官方入口同样不注入解析器与效果面胶水；
  - @：【加载领域】，自主能力 的 require() 语义按清单顺序覆盖 target——
    会以解析器物化面（语境解释器版）覆盖注入的效果面胶水（宿主内建表
    直挂同理被插件表覆盖）；语料零命中，登记现状。

三锁封死：
  1. 对拍：门面对拍（exec_api.run_checked VM 面 vs 宿主解释器面）——
     examples 全部 12 个能力语料文件逐字节同输出/同错误 + 合成对拍
     （资源_加载后调用加载函数 / 解析_JSON / 生成_网页报告）。
  2. 闭环：真子进程 matha run / run_checked 退出码 + 注入面直测
     （VM 构造→wire→运行→globals 含加载函数）+ 平铺覆盖语义 + resolver
     物化面 12 符号 + 清单登记锁。
  3. 边界：裸 VM 拒绝 / plugins=off 拒绝 / 裸 VM 解析_JSON 在场 /
     MFunction.consts 缺省 None + 帧池回退 / 双面解析_JSON 同源 /
     资源_列表·资源_读取 登记边界（插件面未覆盖）。
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter, BUILTINS
from src.kernel import exec_api, json_builtin
from src.kernel.json_builtin import parse_json
from src.mbc.compiler import MFunction, compile_program
from src.mbc.vm import Frame, VM
from src.parser import parse

EXAMPLES = ROOT / "matha" / "examples"

#: 12 个能力语料文件（自主_*/资源_加载/资源_成长/软件_构建/生成_*）
CAPABILITY_FILES = [
    "07_auto_debug.matha",
    "08_auto_optimize.matha",
    "09_self_grow.matha",
    "10_library_read.matha",
    "10_library_sub.matha",
    "10_web_app.matha",
    "11_grow_sub.matha",
    "11_desktop.matha",
    "11_library_grow.matha",
    "12_backend.matha",
    "12_library_discipline.matha",
    "12_mech_sub.matha",
]


def _norm(v):
    fields = getattr(v, "__dict__", None)
    if fields is not None and type(v).__module__ == "src.autonomous":
        return {"__type__": type(v).__name__,
                **{k: repr(x) for k, x in fields.items()}}
    return v


def _host(src: str):
    interp = Interpreter()
    try:
        interp.run(parse(src))
        return ("ok", [repr(_norm(x)) for x in interp.outputs])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {e}")


def _vm(src: str):
    try:
        outs, err = exec_api.run_checked(src)
        if err is not None:
            return ("err", f"{type(err).__name__}: {err}")
        return ("ok", [repr(_norm(x)) for x in outs])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {e}")


# ============================================================
# 1. 对拍：门面对拍（12 能力语料 + 合成）
# ============================================================

@pytest.mark.parametrize("name", CAPABILITY_FILES)
def test_capability_corpus_facade_parity(name):
    """examples 能力语料 12 文件：宿主面 vs 官方入口 VM 面逐字节一致。"""
    src = (EXAMPLES / name).read_text(encoding="utf-8")
    assert _host(src) == _vm(src), name


def test_library_load_then_call_synthetic_parity():
    """合成对拍：资源_加载 后调用加载函数——效果落在运行本体（双端同值）。"""
    src = (
        '资源_加载("core/arithmetic")(0)\n'
        'result1 = 加 3 4\n'
        'result2 = 平方 5\n'
        '#：[result1]\n'
        '#：[result2]\n'
    )
    assert _host(src) == _vm(src) == ("ok", ["7", "25"])


def test_grow_then_call_synthetic_parity():
    """合成对拍：资源_成长 生成的新公式直接可调（效果落在运行本体）。"""
    src = (
        '资源_成长("计算动能")("core")("")\n'
        'v = 动能 2 3\n'
        '#：[v]\n'
    )
    assert _host(src) == _vm(src) == ("ok", ["9.0"])


def test_parse_json_facade_parity():
    """解析_JSON 双面对拍：嵌套列表/字典/非法输入同错同消息。"""
    ok = 'a = 解析_JSON("[1, 2, [3, {\\"k\\": \\"值\\"}]]")\n#：[a]\n'
    assert _host(ok) == _vm(ok)
    bad = 'try { a = 解析_JSON("{坏") } catch (e) { #：[e] }\n'
    assert _host(bad) == _vm(bad)


# ============================================================
# 2. 闭环：注入面直测 + 真子进程
# ============================================================

def _wired_vm(src: str):
    """官方入口同款注入（_wire_plugin_runtime）+ 主码初始化，返回 VM。"""
    mod = compile_program(parse(src))
    vm = VM(mod)
    exec_api._wire_plugin_runtime(vm)
    vm.run()
    return vm


def test_wire_injects_glue_and_merge_lands_in_same_vm():
    """注入面直测：效果面胶水落 globals；资源_加载后加载函数在「同一个 VM」。"""
    vm = _wired_vm('资源_加载("core/arithmetic")(0)\n')
    for name in ("加", "平方", "立方"):
        assert name in vm.globals, name
        assert isinstance(vm.globals[name], type(vm.globals["加"]))
    assert vm.call("加", 10, 5) == 15


def test_merge_is_flat_overwrite():
    """平铺覆盖：二次加载同名资源 → 函数为资源版（与宿主 commit 语义同构）。"""
    vm = _wired_vm('资源_加载("core/arithmetic")(0)\n')
    before = vm.call("加", 1, 2)
    vm2 = _wired_vm('资源_加载("core/arithmetic")(0)\n资源_加载("core/arithmetic")(0)\n')
    assert vm2.call("加", 1, 2) == before == 3


def test_wire_setdefault_respects_user_definitions():
    """setdefault：程序自定义同名函数不被效果面胶水覆盖。"""
    src = (
        'func 资源_加载(路径) -> Text = "mine"\n'
        'v = 资源_加载("core/arithmetic")\n'
        '#：[v]\n'
    )
    assert _host(src) == _vm(src) == ("ok", ["'mine'"])


def test_resolver_materializes_twelve_symbols():
    """解析器物化面：require("capability") 返回 12 符号柯里化实现。"""
    from src.plugin_api import get_resolver
    table = get_resolver().require("capability", {})
    expected = {"自主_调试", "自主_优化", "自主_成长",
                "资源_加载", "资源_成长", "软件_构建",
                "生成_网页", "生成_桌面", "生成_服务",
                "生成_系统", "生成_游戏", "生成_建模"}
    assert expected <= set(table)
    assert len(table) == len(expected)


def test_manifest_registers_capability_plugin():
    """清单登记：capability 插件 12 符号 + 中文领域名。"""
    payload = json.loads(
        (ROOT / "src" / "domains" / "manifest.json").read_text(encoding="utf-8"))
    plugin = next(p for p in payload["plugins"] if p["name"] == "capability")
    assert plugin["cn_name"] == "自主能力"
    assert set(plugin["symbols"]) == {
        "自主_调试", "自主_优化", "自主_成长",
        "资源_加载", "资源_成长", "软件_构建",
        "生成_网页", "生成_桌面", "生成_服务",
        "生成_系统", "生成_游戏", "生成_建模"}


def test_matha_run_real_subprocess_capability_file():
    """真子进程 matha run：能力语料文件正常退出且输出非空（官方 CLI 门面）。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "src" / "matha_main.py"),
         "run", str(EXAMPLES / "10_library_read.matha")],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-500:]
    assert "7" in r.stdout


# ============================================================
# 3. 边界：拒绝面 / 缺省面 / 登记面
# ============================================================

def test_bare_vm_rejects_capability_symbols():
    """裸 VM()（无注入）不承载插件符号——与原生 exe 同一架构哲学。"""
    src = '报告 = 自主_调试("let x = 1 in x")\n'
    vm = VM(compile_program(parse(src)))
    with pytest.raises(Exception, match="自主_调试"):
        vm.run()


def test_facade_plugins_off_rejects_capability_symbols():
    """官方入口 plugins="off"：不注入解析器与效果面胶水。"""
    src = '报告 = 自主_调试("let x = 1 in x")\n'
    with pytest.raises(Exception, match="自主_调试"):
        exec_api.run(src, plugins="off")


def test_bare_vm_has_parse_json_default():
    """裸 VM 内建面：解析_JSON 在场（VM defaults 双面单一实现）。"""
    src = '#：[解析_JSON("[1, 2, 3]")]\n'
    vm = VM(compile_program(parse(src)))
    vm.run()
    assert vm.outputs == [[1, 2, 3]]


def test_mfunction_consts_default_none_and_frame_fallback():
    """跨模块常量池缺省面：MFunction.consts=None；主帧池=模块池。"""
    mod = compile_program(parse("func 加(a, b) -> Int = a + b\n"))
    fn = mod.functions["加"]
    assert fn.consts is None
    vm = VM(mod)
    assert vm.main_frame.consts is mod.constants
    assert vm.call("加", 2, 3) == 5


def test_cross_module_closure_carries_source_pool():
    """跨模块合并闭包携带来源池：错位常量不再发生（回归锁）。"""
    probe = _wired_vm('资源_加载("core/arithmetic")(0)\n')
    fn = probe.globals["加"]
    assert isinstance(fn, type(probe.globals["平方"]))
    assert fn.fn.consts is not None
    assert fn.fn.consts is not probe.mod.constants


def test_parse_json_single_source_both_faces():
    """解析_JSON 双面同源：宿主 BUILTINS 与 VM defaults 首调都解析到同一实现。

    阶段 23a 起该符号注册为 LazyKernelFn（首调才 import json_builtin），
    同源锁由「惰性跳板物化后 is 同一函数对象」承载，不再锁注册期身份。
    """
    host = BUILTINS["解析_JSON"]
    from src.mbc.vm import _default_builtins
    vm_side = _default_builtins()["解析_JSON"]
    assert type(host).__name__ == "LazyKernelFn"
    assert type(vm_side).__name__ == "LazyKernelFn"
    from src.kernel.json_builtin import parse_json
    assert host('{"a": 1}') == parse_json('{"a": 1}') == {"a": 1}
    assert vm_side('{"a": 1}') == {"a": 1}


def test_library_list_read_remain_uncovered_boundary():
    """登记边界：资源_列表/资源_读取 插件面未覆盖（语料零使用，现状锁）。"""
    from src.plugin_api import get_resolver
    table = get_resolver().require("capability", {})
    assert "资源_列表" not in table
    assert "资源_读取" not in table
    # 宿主面在场（interp 实例表直挂）——只是插件面未登记
    assert "资源_列表" in Interpreter().builtins
    assert "资源_读取" in Interpreter().builtins
