"""阶段 27d：单元管理器五形态统一三锁（src/os_runtime.py 宿主桥）。

27c 内核（matha/os/kernel.matha）是纯 Matha 的单元生命周期核心；27d 宿主桥
把五类原生注册表与外部可执行单元统一转译为内核单元描述符——装载/启动/停止/
卸载/升级/回滚/调度全部经内核协商（单一事实源），形态特定动作由桥执行：

    app      ← .matha/apps/<应用>/manifest.json（25d）→ 一次性批执行闭包
    包       ← .matha_packages/<名>/manifest.json（24a）→ 入口源真执行
    域插件   ← PluginResolver（26a/26c）→ 启动=注册确保；停止=unregister
    终端命令 ← matha_term_registry.txt（12e）→ 处理器源 + 处理([]) 真执行
    服务     ← register_service 步闭包（长驻，每调度轮恰一步）
    外部     ← register_external argv → subprocess.Popen 真进程
              spawn/poll 步闭包经 MBC VM callable 分支被纯 Matha 调度器驱动
              ——「纯 Matha 内核调度宿主进程」；版本史随闭包回滚即恢复旧动作。

内核形态面扩展：_是形态 增 外部（27c 锁面不变——外星形态仍拒绝）。

诚实边界（桥 docstring 同源）：app/命令/包 为一次性批执行非长驻守护；
域插件停止为运行时注销（reload 可回位，持久面属 23d matha ext）；
外部 stdout 退出步收集、运行中非阻塞轮询。
"""

import json
import sys
import time

import pytest

from src.os_runtime import OsRuntime
from src.plugin_api import LegacyModulePlugin, get_resolver


@pytest.fixture()
def scratch_root(tmp_path):
    """五形态 scratch 注册表根（app/包/终端命令 各一件）。"""
    app_dir = tmp_path / ".matha" / "apps" / "demoapp"
    app_dir.mkdir(parents=True)
    (app_dir / "manifest.json").write_text(json.dumps({
        "应用": "demoapp", "版本": "1", "说明": "scratch", "入口": "main.matha",
    }, ensure_ascii=False), encoding="utf-8")
    (app_dir / "main.matha").write_text("输出(40 + 2)\n", encoding="utf-8")

    pkg_dir = tmp_path / ".matha_packages" / "scratchpkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "manifest.json").write_text(json.dumps({
        "name": "scratchpkg", "version": "0.2.0", "entry": "scratchpkg.matha",
        "description": "scratch", "dependencies": [],
    }, ensure_ascii=False), encoding="utf-8")
    (pkg_dir / "scratchpkg.matha").write_text('输出("包就绪")\n', encoding="utf-8")

    (tmp_path / "matha_term_registry.txt").write_text(
        "你好 cmdext.matha\n", encoding="utf-8")
    (tmp_path / "cmdext.matha").write_text(
        'func 处理(参数们) -> Value = (参数们) => {\n'
        '  输出("你好命令真执行")\n'
        '  参数们\n'
        '}\n', encoding="utf-8")
    return tmp_path


@pytest.fixture()
def rt(scratch_root):
    return OsRuntime(root=scratch_root)


def _drive_once(rt, name):
    """装载→启动→建进程→单轮调度的公共序列（返回调度事件）。"""
    desc = rt._find_descriptor(name)
    assert desc is not None, f"发现面缺单元 {name}"
    assert rt.load_descriptor(desc)["结果"] == "已装载"
    assert rt.start(name)["结果"] == "运行中"
    assert rt.start_process(name)["结果"] == "已启动"
    return rt.tick(1)["事件"]


# ============================================================
# 发现面
# ============================================================

def test_discovery_covers_six_forms_and_native_registries(rt):
    """scratch 根：app/包/终端命令 各 1；域插件来自真清单（≥80 且含 mechanics）；
    服务无独立发现源恒空；外部未登记恒空；形态键集 = 五形态 + 外部。"""
    d = rt.discover()
    assert set(d) == {"app", "包", "域插件", "终端命令", "服务", "外部"}
    assert [u["名"] for u in d["app"]] == ["demoapp"]
    assert [u["名"] for u in d["包"]] == ["scratchpkg"]
    assert [u["名"] for u in d["终端命令"]] == ["你好"]
    names = [u["名"] for u in d["域插件"]]
    assert len(names) >= 80 and "mechanics" in names
    assert d["服务"] == []
    assert d["外部"] == []


def test_descriptor_version_normalization(rt):
    """非整数版本串归一为 1（manifest 语义版本串→内核正整数版本）；app 整数串
    直取；描述符携带源版本溯源。"""
    d = rt.discover()
    app = d["app"][0]
    pkg = d["包"][0]
    cmd = d["终端命令"][0]
    assert app["版本"] == 1 and app["源版本"] == "1"
    assert pkg["版本"] == 1 and pkg["源版本"] == "0.2.0"
    assert cmd["版本"] == 1


# ============================================================
# 一次性批执行形态（app / 包 / 终端命令）
# ============================================================

def test_app_unit_one_shot_execution(rt):
    """app 单元真执行：调度单步产出 40+2=42，进程随即退出（一次性批语义）。"""
    events = _drive_once(rt, "demoapp")
    assert 42 in events
    rows = rt.process_list()
    assert rows[0][1] == "demoapp" and rows[0][3] == "已退出"


def test_package_unit_entry_execution(rt):
    """包单元真执行：入口源 装载→启动→调度 产出「包就绪」。"""
    events = _drive_once(rt, "scratchpkg")
    assert "包就绪" in [e for e in events if isinstance(e, str)]


def test_terminal_command_unit_handler_execution(rt):
    """终端命令单元真执行：处理器源 + 处理([]) 调用面产出「你好命令真执行」。"""
    events = _drive_once(rt, "你好")
    assert "你好命令真执行" in [e for e in events if isinstance(e, str)]


# ============================================================
# 域插件形态（真 resolver + 合成插件）
# ============================================================

def test_domain_plugin_start_ensure_stop_unregister():
    """域插件：合成插件经桥装载/启动（符号数产出）/停止——停止即
    PluginResolver.unregister 真注销（清单 reload 可回位，合成件不回）。"""
    resolver = get_resolver()
    resolver.register(LegacyModulePlugin(
        name="桥测试插件", module="src.domains.terminal",
        registers=(), symbols=("测试符号甲",)))
    rt = OsRuntime()
    try:
        names = [u["名"] for u in rt.discover()["域插件"]]
        assert "桥测试插件" in names
        events = _drive_once(rt, "桥测试插件")
        assert "符号数 1" in [e for e in events if isinstance(e, str)]
        assert rt.stop("桥测试插件")["结果"] == "已停止"
        assert resolver.plugin("桥测试插件") is None
    finally:
        resolver.unregister("桥测试插件")


# ============================================================
# 外部单元（subprocess × 纯 Matha 调度器）
# ============================================================

def test_external_unit_spawn_poll_exit():
    """外部单元全生命周期：登记→装载→启动→建进程→tick spawn→settled 后
    tick 轮询收 stdout 事件 + 退出事件 + 退出码 0（宿主真进程被纯 Matha
    调度器驱动）。"""
    rt = OsRuntime()
    desc = rt.register_external(
        "hello", [sys.executable, "-c", "print('hello from ext')"])
    assert rt.load_descriptor(desc)["结果"] == "已装载"
    assert rt.start("hello")["结果"] == "运行中"
    assert rt.start_process("hello")["结果"] == "已启动"
    first = rt.tick(1)
    assert first["步数"] == 1
    time.sleep(0.5)
    rest = rt.tick(5)
    assert "hello from ext" in [e for e in rest["事件"] if isinstance(e, str)]
    assert ["退出", 1] in rest["事件"]
    info = rt.unit_info("hello")
    assert info["桥"]["退出码"] == 0
    assert info["桥"]["输出"] == ["hello from ext"]
    assert info["桥"]["进程活"] is False


def test_external_unit_upgrade_rollback_versions():
    """外部单元升级/回滚：停止→v2 升级（版本 2、历史 1）→回滚（版本 1、
    历史 0）→再回滚无历史拒绝——版本史随描述符闭包，回滚即恢复旧动作。"""
    rt = OsRuntime()
    rt.register_external("hello", [sys.executable, "-c", "print('v1')"], 版本=1)
    rt.load_descriptor(rt._find_descriptor("hello"))
    rt.start("hello")
    rt.stop("hello")
    v2 = rt.register_external(
        "hello", [sys.executable, "-c", "print('v2')"], 版本=2)
    assert rt.upgrade("hello", v2)["结果"] == "已升级"
    info = rt.unit_info("hello")
    assert info["版本"] == 2 and info["历史版本数"] == 1
    assert rt.rollback("hello")["结果"] == "已回滚"
    info = rt.unit_info("hello")
    assert info["版本"] == 1 and info["历史版本数"] == 0
    assert rt.rollback("hello")["原因"] == "无历史版本"


def test_external_unit_stop_terminates_live_process():
    """桥停止正在运行的外部单元：terminate 真生效，下一轮轮询收退出，
    内核单元状态 已停止。"""
    rt = OsRuntime()
    rt.register_external(
        "slow", [sys.executable, "-c", "import time; time.sleep(30)"])
    rt.load_descriptor(rt._find_descriptor("slow"))
    rt.start("slow")
    rt.start_process("slow")
    rt.tick(1)
    assert rt.unit_info("slow")["桥"]["进程活"] is True
    assert rt.stop("slow")["结果"] == "已停止"
    time.sleep(0.3)
    rt.tick(3)
    info = rt.unit_info("slow")
    assert info["桥"]["进程活"] is False
    assert info["状态"] == "已停止"


def test_external_unit_unload_after_stop():
    """外部单元停止后卸载（运行中卸载诚实拒绝语义由 27c 锁面覆盖）；
    卸载后查询单元为 null。"""
    rt = OsRuntime()
    rt.register_external(
        "slow2", [sys.executable, "-c", "import time; time.sleep(30)"])
    rt.load_descriptor(rt._find_descriptor("slow2"))
    rt.start("slow2")
    rt.start_process("slow2")
    rt.tick(1)
    assert rt.stop("slow2")["结果"] == "已停止"
    assert rt.unload("slow2")["结果"] == "已卸载"
    assert rt.unit_info("slow2") is None


# ============================================================
# 服务形态（长驻步闭包）+ 汇总面
# ============================================================

def test_service_unit_schedulable_and_resolvable():
    """服务单元：register_service 步闭包长驻——每轮恰一步、继续期事件累积、
    第三步退出；服务名经 服务_解析 可解析。"""
    rt = OsRuntime()
    state = {"n": 0}

    def 步(s):
        state["n"] += 1
        return {"状态": state["n"], "继续": state["n"] < 3,
                "产出": [f"第{state['n']}步"]}

    desc = rt.register_service("计数服务", 步, 服务名s=["计数"])
    assert rt.start("计数服务")["结果"] == "运行中"
    assert rt.start_process("计数服务")["结果"] == "已启动"
    r1 = rt.tick(2)
    assert r1["步数"] == 2
    assert "第1步" in r1["事件"] and "第2步" in r1["事件"]
    r2 = rt.tick(2)
    assert r2["步数"] == 1
    assert ["退出", 1] in r2["事件"]
    assert rt.resolve_service("计数") == "计数服务"
    assert rt.resolve_service("没有") is None


def test_inspect_health_with_bridge_summary():
    """体检汇总：内核 体检 字段 + 桥摘要（根/句柄）；句柄状态随进程生死翻转。"""
    rt = OsRuntime()
    rt.register_external(
        "tiny", [sys.executable, "-c", "print('tiny')"])
    rt.load_descriptor(rt._find_descriptor("tiny"))
    rt.start("tiny")
    rt.start_process("tiny")
    rt.tick(1)
    report = rt.inspect()
    assert report["单元数"] == 1
    assert set(report["桥"]) == {"根", "句柄"}
    assert report["桥"]["句柄"]["tiny"]["进程活"] is True
    time.sleep(0.5)
    rt.tick(5)
    report = rt.inspect()
    assert report["桥"]["句柄"]["tiny"]["进程活"] is False
    assert report["桥"]["句柄"]["tiny"]["退出码"] == 0
