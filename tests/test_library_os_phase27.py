# -*- coding: utf-8 -*-
"""阶段 27f：资源库三分支双面锁（library/os + desktop + compat 六模块）。

27c 内核 / 27e 桌面之上的「资源库当代码用」组合层三分支：
  os       进程管理（调度编排）+ 单元清单（内核状态可读面）+ 单元工厂（五形态描述符构造）
  desktop  桌面组件（进度条/表格/消息框/键位栏——帧内容绘制件）
  compat   包适配器（25c/25d 商店清单 → 内核描述符）+ 命令适配器（12e 终端注册命令 → 内核单元）

本文件锁（host = Interpreter，vm = exec_api.run_checked 双面对拍）：
  A. 模块形态/use 诚实 + index.matha 注册面（27 条目、六路径落盘可达）；
  B. 解析器收口锁：dict 值位单元素 [x] 双面列表语义（27f 产品缺陷真修——
     src/parser.py 值位冒号加入右值上下文清单，host 与自举镜像一致）；
  C. 工厂+清单+进程管理 21 输出逐位（装载×5 + 带依赖/带服务幂等 + 清单行/
     服务目录/依赖表/清单报告 8 行 + 批量启动/运行到退出/批量停止/进程快照）；
  D. 依赖表非空场景（装载后强制卸载依赖 → "联件 缺: 时钟" + 缺失区 5 行报告）；
  E. 桌面组件 16 输出逐字符（进度条三态 + 表格列宽 + 消息框 + 键位栏）+ 上限非正双面如实报错；
  F. 包适配器 12 输出（适配成功/0.x 拒/非数字拒/融合装载回环）；
  G. 命令适配器 12 输出（处理器文件真跑 e2e：装载→启动→调度→事件取回"滴"；
     缺文件/坏行诚实拒绝）；
  H. tier C：Matha 编译器自举编译 joined stdlib+kernel+六模块 ≡ 宿主编译逐位一致。

登记不修（27g 收官条目，探针取证）：本文件驱动全程使用 27c 已证柯里块形态
（let 绑定 lambda 语句位条件赋值折损为比较的语言缺陷绕行，见 27c 锁登记）。
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.mbc.compiler import Compiler, MFunction, MModule  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.parser import parse as py_parse  # noqa: E402
from src import ast_nodes as ast  # noqa: E402

_MODS = {
    "进程管理": "matha/library/os/进程管理.matha",
    "单元清单": "matha/library/os/单元清单.matha",
    "单元工厂": "matha/library/os/单元工厂.matha",
    "桌面组件": "matha/library/desktop/桌面组件.matha",
    "包适配器": "matha/library/compat/包适配器.matha",
    "命令适配器": "matha/library/compat/命令适配器.matha",
}

_USE_LOCKS = {
    "单元工厂": [],
    "进程管理": ["use 标准库 { len | str }", "use 内核"],
    "单元清单": ["use 标准库 { len | str }", "use 内核"],
    "桌面组件": ["use 标准库 { len | str | int }"],
    "包适配器": ["use 标准库 { len | split | int | ord_matha | dict_get }", "use 内核"],
    "命令适配器": ["use 标准库 { len | split | read_file }", "use 内核"],
}


def _read_source(rel: str) -> str:
    with open(ROOT / rel, encoding="utf-8") as f:
        return f.read()


def _host_run(source: str) -> list:
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(py_parse(source))
    return list(ip.outputs)


def _vm_run(source: str) -> list:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is None, f"vm 面不应报错: {type(err).__name__}: {err}"
    return list(outs)


def _run(face: str, source: str) -> list:
    return _host_run(source) if face == "host" else _vm_run(source)


# ============================================================
# A. 模块形态 / use 诚实 / 注册面
# ============================================================

class TestModuleShape:

    def test_six_modules_shape_and_use_honesty(self):
        for name, rel in _MODS.items():
            src = _read_source(rel)
            assert src.startswith(f"module {name} {{"), name
            lines = [ln.strip() for ln in src.splitlines() if ln.strip().startswith("use ")]
            assert lines == _USE_LOCKS[name], name

    def test_index_registers_six_paths(self):
        src = _read_source("matha/library/index.matha")
        entries = [ln.strip().strip('",') for ln in src.splitlines()
                   if ln.strip().startswith('"')]
        assert len(entries) == 27
        for rel in _MODS.values():
            assert rel[len("matha/library/"):-len(".matha")] in entries, rel

    def test_index_paths_resolve_to_files(self):
        src = _read_source("matha/library/index.matha")
        entries = [ln.strip().strip('",') for ln in src.splitlines()
                   if ln.strip().startswith('"')]
        for e in entries:
            assert (ROOT / "matha/library" / (e + ".matha")).exists(), e


# ============================================================
# B. 解析器收口锁：dict 值位单元素 [x]
# ============================================================

_DICTVAL_SRC = (
    'let m = {"入口": ["x.matha"]}\n'
    '输出(len(m["入口"]))\n'
    '输出(m["入口"][0])\n'
    'let n = {"名": "计算器", "服务": ["加", "减"]}\n'
    '输出(len(n["服务"]))\n'
    '输出(n["服务"][1])\n'
)


class TestDictValueListLiteral:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_single_element_list_in_dict_value(self, face):
        outs = _run(face, _DICTVAL_SRC)
        assert outs == [1, "x.matha", 2, "减"]


# ============================================================
# C. 工厂 + 清单 + 进程管理（DRIVER_OS 21 输出逐位）
# ============================================================

_DRIVER_OS = (
    "use 标准库 { len | str }\n"
    "use 内核\n"
    "use 进程管理\n"
    "use 单元工厂\n"
    "use 单元清单\n"
    "\n"
    "func 计数步(上限) -> Value = (上限) => {\n"
    "  let 步 = (状态) => {\n"
    "    let n = 状态 = null ? 0 : 状态\n"
    "    let 下一 = n + 1\n"
    "    let 空 = []\n"
    "    let 报 = {\"状态\": 下一, \"继续\": 下一 < 上限, \"产出\": 空}\n"
    "    报\n"
    "  }\n"
    "  步\n"
    "}\n"
    "let k = 内核_新()\n"
    "let d1 = 应用描述(\"app1\", \"主\", 计数步(3))\n"
    "输出(装载(k, d1)[\"结果\"])\n"
    "let svc = 服务描述(\"时钟\", [\"钟\"])\n"
    "输出(装载(k, svc)[\"结果\"])\n"
    "let pkg = 包描述(\"基础包\")\n"
    "输出(装载(k, pkg)[\"结果\"])\n"
    "let 插 = 插件描述(\"绘图\", [\"画点\", \"画线\"])\n"
    "输出(装载(k, 插)[\"结果\"])\n"
    "let d1b = 带依赖(d1, [\"时钟\"])\n"
    "输出(装载(k, d1b)[\"原因\"])\n"
    "let d1c = 带服务(d1, [\"算\"])\n"
    "输出(装载(k, d1c)[\"原因\"])\n"
    "\n"
    "输出(清单行(k, \"app1\"))\n"
    "输出(清单行(k, \"幽灵\"))\n"
    "输出(服务目录行(k))\n"
    "输出(依赖表(k))\n"
    "let 缺 = 内核_新()\n"
    "let need = 带依赖(应用描述(\"孤件\", \"主\", 计数步), [\"鬼依赖\"])\n"
    "装载(缺, need)\n"
    "输出(依赖表(缺))\n"
    "输出(清单报告(k))\n"
    "\n"
    "let 批 = 批量启动(k, [\"app1\", \"时钟\", \"幽灵\"])\n"
    "输出(批[\"成功\"])\n"
    "输出(批[\"拒绝\"])\n"
    "输出(启动进程(k, \"app1\", \"主\")[\"pid\"])\n"
    "let rr = 运行到退出(k, 1, 10)\n"
    "输出(rr[\"轮数\"])\n"
    "输出(rr[\"步数\"])\n"
    "输出(rr[\"已退出\"])\n"
    "输出(len(rr[\"事件\"]))\n"
    "输出(批量停止(k, [\"时钟\", \"app1\"])[\"成功\"])\n"
    "输出(进程快照(k))\n"
)

_EXPECT_OS = [
    "已装载", "已装载", "已装载", "已装载", "已装载", "已装载",
    "app1 app v1 已装载 历史=0",
    "未装载 幽灵",
    ["服务 钟 ← 时钟"],
    [],
    [],
    ["单元 4  运行中 0  已停止 0", "进程 0  就绪 0",
     "app1 app v1 已装载 历史=0", "时钟 服务 v1 已装载 历史=0",
     "基础包 包 v1 已装载 历史=0", "绘图 域插件 v1 已装载 历史=0",
     "服务 钟 ← 时钟", "依赖: 完整"],
    ["app1", "时钟"],
    [["幽灵", "未装载"]],
    1, 3, 3, True, 1,
    ["时钟", "app1"],
    ["pid 1 app1/主 已退出 步数 3"],
]


class TestFactoryManifestProcess:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_driver_os_exact(self, face):
        outs = _run(face, _DRIVER_OS)
        assert outs == _EXPECT_OS


# ============================================================
# D. 依赖表非空场景（装载后强制卸载依赖）
# ============================================================

_DRIVER_DEP = (
    "use 标准库 { len | str }\n"
    "use 内核\n"
    "use 单元工厂\n"
    "use 单元清单\n"
    "\n"
    "func 计数步(上限) -> Value = (上限) => {\n"
    "  let 步 = (状态) => {\n"
    "    let n = 状态 = null ? 0 : 状态\n"
    "    let 下一 = n + 1\n"
    "    let 空 = []\n"
    "    let 报 = {\"状态\": 下一, \"继续\": 下一 < 上限, \"产出\": 空}\n"
    "    报\n"
    "  }\n"
    "  步\n"
    "}\n"
    "let k5 = 内核_新()\n"
    "输出(装载(k5, 服务描述(\"时钟\", [\"钟\"]))[\"结果\"])\n"
    "let d5 = 带依赖(应用描述(\"联件\", \"主\", 计数步(2)), [\"时钟\"])\n"
    "输出(装载(k5, d5)[\"结果\"])\n"
    "输出(卸载(k5, \"时钟\", true)[\"结果\"])\n"
    "输出(依赖表(k5))\n"
    "输出(len(清单报告(k5)))\n"
    "输出(清单报告(k5)[4])\n"
)

_EXPECT_DEP = [
    "已装载", "已装载", "已卸载",
    ["联件 缺: 时钟"],
    5,
    "联件 缺: 时钟",
]


class TestDepTableScenario:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_force_unload_dep_table(self, face):
        outs = _run(face, _DRIVER_DEP)
        assert outs == _EXPECT_DEP


# ============================================================
# E. 桌面组件（16 输出逐字符 + 上限非正如实报错）
# ============================================================

_DRIVER_DESKTOP = (
    "use 标准库 { len | str | int }\n"
    "use 桌面组件\n"
    "\n"
    "输出(进度条(6, 10, 10))\n"
    "输出(进度条(3, 10, 8))\n"
    "输出(进度条(10, 10, 5))\n"
    "let 表 = 表格([\"名\", \"状态\"], [[\"app1\", \"运行中\"], [\"时钟\", \"已停止\"]])\n"
    "输出(len(表))\n"
    "输出(表[0])\n"
    "输出(表[1])\n"
    "输出(表[2])\n"
    "输出(表[3])\n"
    "let 框 = 消息框(\"提示\", [\"装载完成\", \"服务就绪\"])\n"
    "输出(len(框))\n"
    "输出(框[0])\n"
    "输出(框[1])\n"
    "输出(框[2])\n"
    "输出(框[3])\n"
    "输出(框[4])\n"
    "输出(框[5])\n"
    "输出(键位栏([[\"j\", \"焦点\"], [\"d\", \"步进\"], [\"q\", \"退出\"]]))\n"
)

_EXPECT_DESKTOP = [
    "[######----] 6/10", "[##------] 3/10", "[#####] 10/10",
    4, "名    | 状态 ", "-----+----", "app1 | 运行中", "时钟   | 已停止",
    6, "========", "  提示", "--------", "装载完成", "服务就绪", "========",
    "j 焦点  d 步进  q 退出",
]


class TestDesktopWidgets:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_widgets_exact(self, face):
        outs = _run(face, _DRIVER_DESKTOP)
        assert outs == _EXPECT_DESKTOP

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_progressbar_nonpositive_limit_honest_error(self, face):
        src = "use 桌面组件\n进度条(6, 0, 10)\n"
        if face == "host":
            with pytest.raises(RuntimeError, match="进度条: 上限须为正, 实得 0"):
                _host_run(src)
        else:
            outs, err = exec_api.run_checked(src, mode="vm")
            assert outs == []
            assert isinstance(err, RuntimeError)
            assert "进度条: 上限须为正, 实得 0" in str(err)


# ============================================================
# F. 包适配器（12 输出）
# ============================================================

_DRIVER_COMPAT = (
    "use 标准库 { len | str }\n"
    "use 内核\n"
    "use 包适配器\n"
    "\n"
    "let m1 = {\"名\": \"计算器\", \"版本\": \"1.4.2\", \"入口\": [\"main.matha\", \"cli.matha\"]}\n"
    "let a1 = 包描述符(m1)\n"
    "输出(a1[\"已适配\"])\n"
    "输出(a1[\"描述\"][\"形态\"])\n"
    "输出(a1[\"描述\"][\"版本\"])\n"
    "输出(a1[\"描述\"][\"服务\"])\n"
    "输出(len(a1[\"描述\"][\"入口\"]))\n"
    "输出(len(a1[\"描述\"][\"入口\"][0]))\n"
    "let m2 = {\"名\": \"试验品\", \"版本\": \"0.3.1\", \"入口\": [\"x.matha\"]}\n"
    "输出(包描述符(m2)[\"已适配\"])\n"
    "输出(包描述符(m2)[\"原因\"])\n"
    "let m3 = {\"名\": \"坏名\", \"版本\": \"alpha.2\", \"入口\": []}\n"
    "输出(包描述符(m3)[\"原因\"])\n"
    "let k2 = 内核_新()\n"
    "输出(融合(k2, m1)[\"结果\"])\n"
    "输出(查询单元(k2, \"计算器\")[\"版本\"])\n"
    "输出(融合(k2, m2)[\"原因\"])\n"
)

_EXPECT_COMPAT = [
    True, "包", 1, [], 2, 2,
    False, "预发布包 0.x 不受内核版本栈支持",
    "版本主段非数字",
    "已装载", 1,
    "预发布包 0.x 不受内核版本栈支持",
]


class TestPackageAdapter:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_driver_compat_exact(self, face):
        outs = _run(face, _DRIVER_COMPAT)
        assert outs == _EXPECT_COMPAT


# ============================================================
# G. 命令适配器（处理器文件真跑 e2e + 拒绝面）
# ============================================================

_HANDLER = (
    "func 处理(参数们: List) -> List = (参数们) => {\n"
    "  输出(\"滴答\")\n"
    "  let 空 = []\n"
    "  空\n"
    "}\n"
)


def _command_driver(handler_path: str) -> str:
    return (
        "use 标准库 { len | str }\n"
        "use 内核\n"
        "use 命令适配器\n"
        "\n"
        f"let 路径 = \"{handler_path}\"\n"
        "let k3 = 内核_新()\n"
        "let h = 命令描述符(\"报时\", 路径)\n"
        "输出(h[\"可装载\"])\n"
        "输出(装载(k3, h[\"描述\"])[\"结果\"])\n"
        "输出(启动(k3, \"报时\")[\"结果\"])\n"
        "输出(启动进程(k3, \"报时\", \"主\")[\"pid\"])\n"
        "let 轮 = 调度(k3, 1)\n"
        "输出(len(轮[\"事件\"]))\n"
        "输出(轮[\"事件\"][0][0])\n"
        "let bad = 命令描述符(\"缺件\", \"no_such_handler.matha\")\n"
        "输出(bad[\"可装载\"])\n"
        "输出(bad[\"原因\"])\n"
        f"let 表2 = 注册表描述符们(\"报时 {handler_path}\\n坏行\\n\")\n"
        "输出(len(表2))\n"
        "输出(表2[0][\"可装载\"])\n"
        "输出(表2[1][\"可装载\"])\n"
        "输出(表2[1][\"原因\"])\n"
    )


_EXPECT_COMMAND = [
    True, "已装载", "运行中", 1, 2, "滴",
    False, "命令文件不存在: no_such_handler.matha",
    2, True, False,
    "坏行（须为『名字 路径』单空格行）: 坏行",
]


class TestCommandAdapter:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_driver_command_exact(self, face, tmp_path):
        handler = tmp_path / "handler.matha"
        handler.write_text(_HANDLER, encoding="utf-8")
        outs = _run(face, _command_driver(handler.as_posix()))
        assert outs == _EXPECT_COMMAND


# ============================================================
# H. tier C：Matha 编译器自举编译 joined ≡ 宿主编译
# ============================================================

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha", "matha/vm.matha"]

_JOINED_FILES = (["matha/stdlib.matha", "matha/os/kernel.matha"]
                 + [_MODS[n] for n in
                    ("进程管理", "单元清单", "单元工厂", "桌面组件", "包适配器", "命令适配器")])


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


@pytest.fixture(scope="module")
def joined_dict():
    """Matha 编译器编译 joined stdlib+kernel+六模块（自举 VM 内编译）。"""
    vm = VM(_compile_files(_BOOT_FILES).mod)
    vm.run()
    joined = "\n".join(_read_source(rel) for rel in _JOINED_FILES)
    md = vm.call("编译", joined)
    assert isinstance(md, dict)
    return md


def test_selfhost_compile_six_modules_identical(joined_dict):
    """tier C：Matha 编译器编译 stdlib+kernel+六资源库模块 ≡ 宿主编译产物
    （模块名/主码/常量池/函数表逐位一致——组合层纯 Matha 的可运行形态证明）。"""
    host = module_to_dict(_compile_files(_JOINED_FILES).mod)
    md = joined_dict
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
