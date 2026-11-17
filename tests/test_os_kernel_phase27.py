"""阶段 27c：纯 Matha OS 内核三锁（matha/os/kernel.matha）。

内核形态：纯 Matha 模块 内核，仅 use 标准库 { len | 原地设置 | matha_type_of }
（与自举链同源，零第三方依赖、零宿主专属符号——自举编译逐位一致本身即纯度证明）。
数据模型全列表 + 原地设置：内核 = [名表, 记录表, 进程表, 服务表, 下一pid, 日志]；
记录 = [描述, 状态, 版本史]；进程 = [pid, 单元名, 入口名, 状态, 步函数, 进程状态, 步数]；
服务表 = [[服务名, 提供单元名]]；五形态 ∈ app|包|域插件|终端命令|服务。
单元状态机 已装载→运行中→已停止；步函数契约 步(状态) → {"状态","继续","产出"}。

本文件锁（host = Interpreter + use 内核；vm = exec_api.run_checked 双面对拍）：
A 全生命周期 51+5 输出逐位对拍（装载协商 6 分支/启动依赖协商/进程与调度/
  升级回滚版本史栈/卸载依赖方协商+服务自动注销/体检报告/k2 补充面）；
B Matha 编译器自举编译逐位一致（tier C：joined stdlib+kernel 产物 ≡ 宿主编译，
  模块名/主码/常量池/函数表 167 函数逐位）；
C 自举产物独立运行（tier A：Matha 编译产物 dict_to_module 实例化独立 VM，
  装载→启动→须先停止→停止→卸载→服务注销 全状态机真跑）。

27c 生命周期探针定位并修复的四处内核缺陷（此前从未被完整生命周期踩中）：
① _轮步表 空转轮累计翻倍——非就绪分支收 [事件, 实际] 作为增量对，调度轮
  累计 实际 + 收[1] = 实际 + 实际（探针取证：5 轮调度 步数=16 而非 1——
  进程退出后每空转轮步数翻倍）。修复：非就绪增量 [事件, 0]（test_
  process_and_scheduler 锁 r2 步数=1）。
② _卸载落地 经 名/记录 对偶表重建记录表——_配对 产 [名str, 记] 对、_滤对
  滤对后把对偶表整体写回 内核[1]，记录结构被破坏（探针取证：强制卸载后
  查询单元 MathaRuntimeError str["名"]——记录槽 0 变名字符串）。修复：
  直接滤记录 _滤记（描述["名"] != 名），名表由记录重建（test_unload_
  dependency_service_health 锁 卸载后 查询单元= null）。
③ _步进 返回对第二元素是「继续」旗标而非步数增量——退出步不计入调度步数
  （探针取证：r2 步数=0）。修复：步数增量恒 1（_步进 被调用即恰执行一步）。
④ 服务占用协商从未生效——_占用表 借 名索引 比对，而服务表条目是
  [服务名, 提供者] 对偶，对偶 ≠ 裸名恒 false（探针取证：双面 装载 同名服务
  第二单元均成功落地——占用协商被静默跳过，host/vm 同源缺陷）。修复：
  对偶感知 _占用名（服务表[0][0] = 名），装载协商矩阵锁 服务已被占用。

语言形态登记（27g KNOWN_ISSUES 收官条目，探针取证）：
· lambda/柯里块体内语句位条件赋值 var = cond ? a : b 静默折损为比较表达式
  （_in_lambda_rel 下 rel 级 = 走比较半面，IfExpr 包裹后语句被丢弃——括号
  包裹亦不可救：条件变 found = (xs[i]=target)）；内核全程递归式规避。
· 缺失字典键索引双面分歧：host 取值 null 宽容、vm 面 KeyError 抛错
  （探针取证：装载成功后 ["原因"] host=None / vm=KeyError）；内核驱动
  只索引存在键规避。

边界：内核为框架级单元管理核心（进程表/协作调度/服务注册/生命周期/版本史），
步函数由描述符入口表携带（24e 回调绑定同构）；外部单元 subprocess 胶水、
桌面/终端接入、资源库三分支属 27d/27e/27f 范围。
"""

import contextlib
import io
import re

import pytest

from src.interp import Interpreter
from src.kernel import exec_api
from src.mbc.compiler import Compiler, MFunction, MModule
from src.mbc.vm import VM
from src.parser import parse as py_parse
from src import ast_nodes as ast


# ============================================================
# 双面生命周期驱动（host / vm 共用同一源）
# ============================================================

_DRIVER = '''
use 内核

(* ---- 步函数工厂（描述符入口表携带闭包） ---- *)
let 产步 = ["步"]
func 计数步(上限) -> Value = (上限) => {
  let 步 = (状态) => {
    let n = 状态 = null ? 0 : 状态
    let 下一 = n + 1
    let 报 = {"状态": 下一, "继续": 下一 < 上限, "产出": 产步}
    报
  }
  步
}
let 退步 = (状态) => {
  let 空 = []
  let 报 = {"状态": null, "继续": false, "产出": 空}
  报
}

(* ---- 单元描述符（列表值先 let 变量再入字典） ---- *)
let app1入口 = [["主", 计数步(3)], ["退", 退步]]
let app1服务 = ["calc"]
let app1req = []
let app1 = {"名": "app1", "形态": "app", "版本": 1, "requires": app1req, "入口": app1入口, "服务": app1服务}

let app2入口 = [["主", 退步]]
let app2服务 = []
let app2req = ["app1"]
let app2 = {"名": "app2", "形态": "服务", "版本": 2, "requires": app2req, "入口": app2入口, "服务": app2服务}

let bad入口 = []
let bad服务 = []
let badreq = ["ghost"]
let bad = {"名": "bad", "形态": "包", "版本": 1, "requires": badreq, "入口": bad入口, "服务": bad服务}

let 坏形态 = {"名": "坏", "形态": "外星", "版本": 1, "requires": badreq, "入口": bad入口, "服务": bad服务}
let 坏版本 = {"名": "坏2", "形态": "app", "版本": 0, "requires": badreq, "入口": bad入口, "服务": bad服务}

let app3服务 = ["calc"]
let app3 = {"名": "app3", "形态": "app", "版本": 1, "requires": app1req, "入口": bad入口, "服务": app3服务}

(* ---- 内核 ---- *)
let k = 内核_新()

(* 装载协商 *)
输出(装载(k, app1)["结果"])
输出(装载(k, app2)["结果"])
输出(装载(k, bad)["结果"])
输出(装载(k, bad)["原因"])
输出(装载(k, 坏形态)["原因"])
输出(装载(k, 坏版本)["原因"])
输出(装载(k, app1)["原因"])

(* 服务解析 *)
输出(服务_解析(k, "calc"))
输出(服务_解析(k, "nope"))

(* 启动协商：app2 requires app1 运行中 *)
输出(启动(k, "app2")["原因"])
输出(启动(k, "app1")["结果"])
输出(启动(k, "app1")["原因"])
输出(启动(k, "app2")["结果"])

(* 进程 *)
输出(启动进程(k, "app1", "主")["pid"])
输出(启动进程(k, "app1", "不存在")["原因"])
输出(启动进程(k, "bad", "主")["原因"])

(* 调度：计数步 3 次后退出 *)
let r1 = 调度(k, 2)
输出(r1["步数"])
输出(进程列表(k)[0][4])
let r2 = 调度(k, 5)
输出(r2["步数"])
输出(进程列表(k)[0][3])
输出(len(r2["事件"]))
输出(r2["事件"][0][0])

(* 停止进程 + 重复停止 *)
输出(停止进程(k, 1)["结果"])
输出(停止进程(k, 1)["原因"])

(* 升级 / 回滚 *)
let app1v2入口 = [["主", 计数步(9)]]
let app1v2服务 = ["calc"]
let app1v2req = []
let app1v2 = {"名": "app1", "形态": "app", "版本": 2, "requires": app1v2req, "入口": app1v2入口, "服务": app1v2服务}
输出(升级(k, "app1", app1v2)["原因"])
输出(停止(k, "app1")["结果"])
输出(升级(k, "app1", app1v2)["结果"])
输出(查询单元(k, "app1")["历史版本数"])
输出(查询单元(k, "app1")["版本"])
输出(升级(k, "app1", app1v2)["原因"])
let app1v0 = {"名": "app1", "形态": "app", "版本": 1, "requires": app1req, "入口": app1入口, "服务": app1服务}
输出(升级(k, "app1", app1v0)["原因"])
输出(回滚(k, "app1")["结果"])
输出(查询单元(k, "app1")["版本"])
输出(查询单元(k, "app1")["历史版本数"])
输出(回滚(k, "app1")["原因"])
输出(回滚(k, "ghost")["原因"])

(* 卸载协商 *)
输出(卸载(k, "app1", false)["原因"])
输出(停止(k, "app2")["结果"])
输出(卸载(k, "app1", false)["原因"])
输出(卸载(k, "app1", true)["结果"])
输出(服务_解析(k, "calc"))
输出(查询单元(k, "app2")["状态"])

(* 体检 *)
let t = 体检(k)
输出(t["单元数"])
输出(t["运行中"])
输出(t["已停止"])
输出(t["服务数"])
输出(t["日志条数"])
输出(len(t["依赖缺失"]))
输出(t["依赖缺失"][0][0])
输出(t["依赖缺失"][0][1][0])
输出(t["就绪进程"])

(* k2 补充协商面：服务占用 / ghost 拒绝 / 卸载后查询 *)
let k2 = 内核_新()
输出(装载(k2, app1)["结果"])
输出(装载(k2, app3)["原因"])
输出(启动(k2, "ghost")["原因"])
输出(停止(k2, "ghost")["原因"])
输出(查询单元(k, "app1"))
'''

_EXPECTED = [
    # 装载协商（6 分支：落地/落地/缺依赖/缺依赖原因/形态/版本/已装载）
    "已装载", "已装载", "拒绝", "缺少依赖", "描述符不合法", "版本须为正整数", "已装载",
    # 服务解析
    "app1", None,
    # 启动依赖协商
    "依赖未运行", "运行中", "已运行", "运行中",
    # 进程 + 调度 + 停止进程
    1, "入口未定义", "未装载",
    2, 2, 1, "已退出", 2, "步",
    "拒绝", "进程已结束",
    # 升级 / 回滚（版本史栈）
    "须先停止", "已停止", "已升级", 1, 2, "版本须递增", "版本须递增",
    "已回滚", 1, 0, "无历史版本", "未装载",
    # 卸载协商 + 服务自动注销 + 查询
    "存在依赖方", "已停止", "存在依赖方", "已卸载", None, "已停止",
    # 体检
    1, 0, 1, 0, 10, 1, "app2", "app1", 0,
    # k2 补充面
    "已装载", "服务已被占用", "未装载", "未装载", None,
]


def _host_outputs(src):
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(py_parse(src))
    return list(ip.outputs)


def _vm_outputs(src):
    outs, err = exec_api.run_checked(src, mode="vm")
    assert err is None, f"vm 面报错: {err}"
    return outs


@pytest.fixture(scope="module")
def host_outs():
    return _host_outputs(_DRIVER)


@pytest.fixture(scope="module")
def vm_outs():
    return _vm_outputs(_DRIVER)


# ============================================================
# A 面：双面全生命周期对拍
# ============================================================

def test_double_face_full_lifecycle_parity(host_outs, vm_outs):
    """host 与 vm 双面跑同一驱动：56 条输出逐位一致（use 内核 双面可达）。"""
    assert len(host_outs) == 56
    assert len(vm_outs) == 56
    assert vm_outs == host_outs
    assert vm_outs == _EXPECTED


def test_load_negotiation_matrix(host_outs):
    """装载协商 6 分支：落地/缺依赖(细目)/形态不合法/版本非法/重复装载拒绝。"""
    got = host_outs[0:7]
    assert got == ["已装载", "已装载", "拒绝", "缺少依赖",
                   "描述符不合法", "版本须为正整数", "已装载"]


def test_service_resolution(host_outs):
    """服务注册表：calc→提供单元名；未注册→null。"""
    assert host_outs[7:9] == ["app1", None]


def test_start_dependency_negotiation(host_outs):
    """启动协商：依赖未运行拒绝→启动→重复启动拒绝→依赖就绪后放行。"""
    assert host_outs[9:13] == ["依赖未运行", "运行中", "已运行", "运行中"]


def test_process_and_scheduler(host_outs):
    """进程面：pid 分配/入口未定义/未装载；调度步数（缺陷①③ 锁：空转不翻倍、
    退出步计入）——r1 两轮两步、r2 五轮一步（第三步退出、后两轮空转）；进程行
    状态翻 已退出；事件 = 产出 + 退出。"""
    assert host_outs[13:24] == [1, "入口未定义", "未装载",
                                2, 2, 1, "已退出", 2, "步",
                                "拒绝", "进程已结束"]


def test_upgrade_rollback_stack(host_outs):
    """版本史栈：运行中升级拒绝→停止→升级（历史=1, 版本=2）→非递增拒绝×2→
    回滚（版本=1, 历史=0）→无历史拒绝→ghost 未装载。"""
    assert host_outs[24:36] == ["须先停止", "已停止", "已升级", 1, 2,
                                "版本须递增", "版本须递增",
                                "已回滚", 1, 0, "无历史版本", "未装载"]


def test_unload_dependency_service_health(host_outs):
    """卸载协商（缺陷② 锁）：依赖方存在拒绝→停止依赖方→仍拒绝（装载态即算）→
    强制卸载→calc 服务自动注销（null）→依赖方查询正常→体检报告
    （单元=1 停止/日志=10/依赖缺失 app2→app1）。"""
    assert host_outs[36:51] == ["存在依赖方", "已停止", "存在依赖方",
                                "已卸载", None, "已停止",
                                1, 0, 1, 0, 10, 1, "app2", "app1", 0]


def test_k2_occupancy_ghost_and_gone(host_outs):
    """k2 面：服务已被占用（app1 占 calc、app3 再声明）；ghost 启动/停止拒绝；
    卸载后查询单元 = null。"""
    assert host_outs[51:56] == ["已装载", "服务已被占用",
                                "未装载", "未装载", None]


# ============================================================
# 纯度 / 形态锁
# ============================================================

_KERNEL_REL = "matha/os/kernel.matha"
_USE_SYMBOLS = ["len", "原地设置", "matha_type_of"]


def test_kernel_module_shape_and_use_honesty():
    """内核单模块、use 清单与实际使用一致：声明的三个标准库符号均在体内出现。"""
    with open(_KERNEL_REL, encoding="utf-8") as f:
        src = f.read()
    prog = py_parse(src)
    assert len(prog.decls) == 1
    mod = prog.decls[0]
    assert getattr(mod, "name", None) == "内核"
    m = re.search(r"use\s+标准库\s*\{([^}]*)\}", src)
    assert m, "缺 use 标准库 声明"
    declared = [s.strip() for s in m.group(1).split("|")]
    assert declared == _USE_SYMBOLS
    body = src[m.end():]
    for sym in _USE_SYMBOLS:
        assert sym in body, f"use 清单符号 {sym} 未在体内使用（清单诚实性）"


# ============================================================
# B 面：Matha 编译器自举编译逐位一致（tier C）
# ============================================================

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]


def _read_source(rel):
    with open(rel, encoding="utf-8") as f:
        return f.read()


def _compile_files(rels):
    comp = Compiler()
    decls = []
    for rel in rels:
        decls.extend(py_parse(_read_source(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


def module_to_dict(mod):
    d = {"模块名": mod.module_name, "常量": list(mod.constants),
         "主码": [list(x) for x in mod.main_code], "函数": []}
    for name, fn in mod.functions.items():
        info = {"元数": fn.arity, "局部数": fn.nlocals,
                "码": [list(x) for x in fn.code], "参数": list(fn.params)}
        d["函数"].append([name, info])
    return d


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


@pytest.fixture(scope="module")
def matha_kernel_dict():
    """Matha 编译器编译 joined stdlib+kernel 拼接源（自举 VM 内编译）。"""
    vm = VM(_compile_files(_BOOT_FILES).mod)
    vm.run()
    joined = _read_source("matha/stdlib.matha") + "\n" + _read_source(_KERNEL_REL)
    md = vm.call("编译", joined)
    assert isinstance(md, dict)
    return md


def test_selfhost_compile_identical(matha_kernel_dict):
    """tier C：Matha 编译器编译 stdlib+kernel ≡ 宿主编译产物
    （模块名/主码/常量池/函数表逐位一致——内核纯度的可运行形态证明）。"""
    host = module_to_dict(_compile_files(
        ["matha/stdlib.matha", _KERNEL_REL]).mod)
    md = matha_kernel_dict
    assert md["模块名"] == host["模块名"]
    assert [list(x) for x in md["主码"]] == [list(x) for x in host["主码"]]
    assert list(md["常量"]) == list(host["常量"])
    mf = {e[0]: e[1] for e in md["函数"]}
    hf = {e[0]: e[1] for e in host["函数"]}
    assert set(mf) == set(hf)
    for name, info in hf.items():
        got = mf[name]
        assert got["元数"] == info["元数"], name
        assert got["局部数"] == info["局部数"], name
        assert [list(x) for x in got["码"]] == [list(x) for x in info["码"]], name
        assert list(got["参数"]) == list(info["参数"]), name


# ============================================================
# C 面：自举产物独立运行（tier A）
# ============================================================

def test_standalone_product_lifecycle(matha_kernel_dict):
    """tier A：Matha 编译产物实例化独立 VM，内核全状态机真跑
    （装载→启动→运行中卸载拒绝→停止→卸载→服务自动注销）。"""
    inner = VM(dict_to_module(matha_kernel_dict))
    inner.run()

    def call(name, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return inner.call(name, *args)

    k = call("内核_新")
    assert len(k) == 6
    desc = {"名": "app", "形态": "app", "版本": 1, "requires": [],
            "入口": [["主", None]], "服务": ["svc"]}
    assert call("装载", k, desc) == {"结果": "已装载", "名": "app", "版本": 1}
    assert call("启动", k, "app") == {"结果": "运行中", "名": "app"}
    assert call("服务_解析", k, "svc") == "app"
    assert call("卸载", k, "app", False) == {
        "结果": "拒绝", "原因": "须先停止", "名": "app"}
    assert call("停止", k, "app") == {"结果": "已停止", "名": "app"}
    assert call("卸载", k, "app", False) == {
        "结果": "已卸载", "名": "app", "依赖方": []}
    assert call("服务_解析", k, "svc") is None
