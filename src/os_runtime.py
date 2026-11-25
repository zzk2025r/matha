"""共生体宿主桥（阶段 27d）——五形态 + 外部单元统一接入纯 Matha 内核。

内核（matha/os/kernel.matha，27c）是纯 Matha 的单元生命周期核心：装载/启动/
停止/卸载/升级/回滚/服务协商/调度/体检。本模块是宿主侧适配层——把五类原生
注册表与外部可执行单元统一转译为内核单元描述符（单一事实源仍是内核）：

    app      ← .matha/apps/<应用>/manifest.json（25d 安装面：应用/版本/入口）
    包       ← .matha_packages/<名>/manifest.json（24a：name/version/entry）
    域插件   ← PluginResolver（26a/26c：清单驱动 + requires）
    终端命令 ← matha_term_registry.txt（12e：名 处理器路径）
    服务     ← 单元描述符 服务 字段声明（内核原生，无独立发现源）
    外部     ← register_external 登记 argv → subprocess.Popen 真进程

关键机制：MBC VM 的调用指令支持 Python 可调用（vm._call_value 的 callable
分支），因此外部单元的 spawn/轮询步闭包与应用/命令/包的一次性执行闭包直接
作为描述符入口表携带，被纯 Matha 调度器（_步进/调度）统一驱动——「纯 Matha
内核调度宿主进程」由此成立。版本史（升级/回滚）随描述符携带闭包，旧版本
回滚即恢复旧动作。

诚实边界：
- app/终端命令/包 的启动是一次性批执行（宿主解释器真跑源码，产出即输出），
  非长驻守护；长驻交互面属 27e 桌面/终端接入。
- 域插件 停止 = PluginResolver.unregister（运行时注销，reload() 可回位）；
  持久启停面（.matha/extensions.json）属 23d matha ext，不经本桥。
- 外部单元 stdout 在退出步收集（communicate），运行中仅非阻塞轮询。
- 服务形态单元由 register_service 登记（步闭包长驻，每调度轮恰一步）。
- 载体进程回收由本桥 `_终止载体` 补上，粒度是「单元名一格」：句柄表每名一格，
  同单元多条就绪进程共用一格时无法按内核 pid 归属（早收会杀掉仍在跑的另一条）。
  内核只出簿记判定，OS 动作只在判定落地之后发生（被拒的 停止/卸载 不动进程）。

常驻监督（阶段 43d）：描述符可带 常驻 / 重启预算 两键，策略判定与重启动作
全在纯 Matha 内核（matha/os/kernel.matha 的 启动/_监督轮/调度）——本桥只提供
两件事：`register_external(..., 常驻=, 重启预算=)` 把参数写进描述符，
`supervise()` 把内核调度轮接上墙钟。被监管的进程由 `self_launcher()` 构造
argv：冻结态 argv[0] = matha.exe 自身（独立 Matha 进程映像，非 python 脚本），
开发态 = 宿主解释器 + src/matha_main.py 统一 CLI（同一命令面，不分叉语义）。
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

from src import ast_nodes as ast
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.parser import parse as py_parse

_REPO_ROOT = Path(__file__).resolve().parent.parent

_KERNEL_FILES = ["matha/stdlib.matha", "matha/os/kernel.matha"]

_BOOT_CHAIN_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
                     "matha/parser.matha", "matha/interp.matha",
                     "matha/compiler_matha.matha", "matha/vm.matha"]

_FORMS = ("app", "包", "域插件", "终端命令", "服务", "外部")


def _read_repo(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


def _build_kernel_vm() -> VM:
    """宿主编译 stdlib+kernel 拼接声明并实例化内核 VM（tier A 同源形态）。"""
    comp = Compiler()
    decls: list = []
    for rel in _KERNEL_FILES:
        decls.extend(py_parse(_read_repo(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    with contextlib.redirect_stdout(io.StringIO()):
        vm.run()
    return vm


def _run_source(source: str) -> tuple[list, str | None]:
    """宿主解释器一次性执行 Matha 源码 → (输出, 错误串)。"""
    from src.interp import Interpreter

    ip = Interpreter(debug=False)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ip.run(py_parse(source))
    except Exception as e:  # noqa: BLE001 — 一步闭包须把错误折进状态而非抛穿调度器
        return list(ip.outputs), f"{type(e).__name__}: {e}"
    return list(ip.outputs), None


def _int_or_one(raw) -> int:
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return 1


def self_launcher(*args: str) -> list[str]:
    """Matha 自身启动 argv（阶段 43d）——被监管进程的身份口径单一来源。

    冻结态（PyInstaller）`sys.executable` 就是 matha.exe 本身，进程映像名即
    Matha；开发态退回「宿主解释器 + 统一 CLI 入口」。两态都进同一个
    `src/matha_main.py` 命令面，被派生子进程不另找 PATH 上的裸名解释器。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, *[str(a) for a in args]]
    entry = str(_REPO_ROOT / "src" / "matha_main.py")
    return [sys.executable, entry, *[str(a) for a in args]]


class OsRuntime:
    """五形态 + 外部单元的统一运行时（内核持有唯一权威状态）。"""

    def __init__(self, root: str | Path | None = None):
        self._root = Path(root) if root else Path.cwd()
        self._vm = _build_kernel_vm()
        self._k = self._call("内核_新")
        self._external: dict[str, list] = {}
        self._handles: dict[str, dict] = {}
        self._ports: dict = {}
        self._toolchain: dict = {}
        self._boot_vm: VM | None = None

    # ---- 内核调用 ----
    def _call(self, name: str, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return self._vm.call(name, *args)

    # ============================================================
    # 发现（五类原生注册表 + 已登记外部单元）
    # ============================================================

    def discover(self) -> dict[str, list[dict]]:
        return {
            "app": self._discover_apps(),
            "包": self._discover_packages(),
            "域插件": self._discover_plugins(),
            "终端命令": self._discover_commands(),
            "服务": [],
            "外部": self._discover_external(),
        }

    def descriptors(self) -> list[dict]:
        rows: list[dict] = []
        for units in self.discover().values():
            rows.extend(units)
        return rows

    def _discover_apps(self) -> list[dict]:
        base = self._root / ".matha" / "apps"
        if not base.is_dir():
            return []
        units = []
        for manifest_path in sorted(base.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            name = str(manifest.get("应用") or manifest_path.parent.name)
            entry = str(manifest.get("入口") or "main.matha")
            src_path = manifest_path.parent / entry
            if not src_path.is_file():
                continue
            units.append({
                "名": name,
                "形态": "app",
                "版本": _int_or_one(manifest.get("版本")),
                "requires": [],
                "入口": [["主", self._make_source_step(name, src_path.read_text(encoding="utf-8"))]],
                "服务": [],
                "路径": str(src_path),
                "源版本": str(manifest.get("版本") or ""),
            })
        return units

    def _discover_packages(self) -> list[dict]:
        base = self._root / ".matha_packages"
        if not base.is_dir():
            return []
        units = []
        for manifest_path in sorted(base.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            name = str(manifest.get("name") or manifest_path.parent.name)
            entry = str(manifest.get("entry") or f"{name}.matha")
            src_path = manifest_path.parent / entry
            if not src_path.is_file():
                continue
            units.append({
                "名": name,
                "形态": "包",
                "版本": _int_or_one(manifest.get("version")),
                "requires": [str(d) for d in manifest.get("dependencies") or []],
                "入口": [["主", self._make_source_step(name, src_path.read_text(encoding="utf-8"))]],
                "服务": [],
                "路径": str(src_path),
                "源版本": str(manifest.get("version") or ""),
            })
        return units

    def _discover_plugins(self) -> list[dict]:
        from src.plugin_api import get_resolver

        resolver = get_resolver()
        units = []
        for name in resolver.names():
            plugin = resolver.plugin(name)
            if plugin is None:
                continue
            units.append({
                "名": name,
                "形态": "域插件",
                "版本": 1,
                "requires": list(plugin.requires),
                "入口": [["主", self._make_plugin_step(name)]],
                "服务": [],
                "符号数": len(plugin.symbols),
            })
        return units

    def _discover_commands(self) -> list[dict]:
        reg = self._root / "matha_term_registry.txt"
        if not reg.is_file():
            return []
        units = []
        for line in reg.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            name, rel = parts[0], " ".join(parts[1:])
            handler = self._root / rel
            if not handler.is_file():
                continue
            units.append({
                "名": name,
                "形态": "终端命令",
                "版本": 1,
                "requires": [],
                "入口": [["主", self._make_command_step(name, handler)]],
                "服务": [],
                "处理器": str(handler),
            })
        return units

    def _discover_external(self) -> list[dict]:
        units = []
        for name, spec in sorted(self._external.items()):
            argv, 版本, 常驻, 重启预算 = spec
            units.append({
                "名": name,
                "形态": "外部",
                "版本": 版本,
                "requires": [],
                "入口": [["主", self._make_external_step(name, list(argv))]],
                "服务": [],
                "argv": list(argv),
                "常驻": 常驻,
                "重启预算": 重启预算,
            })
        return units

    # ============================================================
    # 登记（程序化单元：外部 / 服务）
    # ============================================================

    def register_external(self, name: str, argv: list[str],
                          版本: int = 1, 常驻: bool = False,
                          重启预算: int = 0) -> dict:
        """登记外部可执行单元；`常驻=真` 交内核监督（阶段 43d）。

        两参数只写进描述符，判定与重启全在 matha/os/kernel.matha：本方法
        不 spawn、不数重启，`argv` 交给 `_make_external_step` 作进程载体。
        """
        self._external[name] = [list(argv), int(版本), bool(常驻),
                                int(重启预算)]
        return self._find_descriptor(name)

    def register_service(self, name: str, step, 服务名s=(),
                         版本: int = 1, requires=(), 常驻: bool = False,
                         重启预算: int = 0) -> dict:
        desc = {
            "名": name, "形态": "服务", "版本": int(版本),
            "requires": list(requires),
            "入口": [["主", step]], "服务": list(服务名s),
            "常驻": bool(常驻), "重启预算": int(重启预算),
        }
        self._call("装载", self._k, desc)
        return desc

    # ============================================================
    # 工具链单元（28e：六层五动作端口 × 内核服务单元）
    # ============================================================

    def register_toolchain_units(self) -> list[str]:
        """六工具链层注册为内核服务单元（单元名 工具链-<层名>）。

        每层一个五动作端口（src/extension_port.py）；装载 = 端口注册代表
        条目（内核层代表条目 = SCOPED_BLOCKS，其余层 = 单元名）+ 内核装载
        描述符。注册即启用（协议语义）——parser 注册表出现单元算子、宿主
        VM/interp 出现单元内建、boot 插口落名、编译器 pass 入表（该层既有
        语义：注册后默认未启用）、内核特性条目记当前实况。单元启动/停止经
        start/stop 派发端口启停（真实层效果），主步 = 端口健康探针（只读
        心跳）；单元升级/回滚走内核描述符版本史（27d）。
        注意：单元停止 = 端口注销/停用；内核层停止 = set_feature(假)
        （进程内覆盖面，clear_feature 可还原环境/默认态）。
        """
        from src.extension_port import LAYER_NAMES, make_port

        self._ports: dict = {}
        self._toolchain: dict = {}
        names = []
        for kind, 层名 in LAYER_NAMES.items():
            unit = f"工具链-{层名}"
            entry = "SCOPED_BLOCKS" if kind == "kernel" else unit
            port = make_port(kind, self._toolchain_target(kind))
            r = port.register(entry, 1, self._toolchain_impl(kind, entry))
            if not r[0]:
                raise RuntimeError(f"工具链端口注册失败 {unit}: {r[2]}")
            self._ports[kind] = port
            self._toolchain[unit] = (kind, entry)
            desc = {"名": unit, "形态": "服务", "版本": 1, "requires": [],
                    "入口": [["主", self._make_toolchain_step(kind)]],
                    "服务": [f"端口-{层名}"]}
            self._call("装载", self._k, desc)
            names.append(unit)
        return names

    def toolchain_port(self, kind):
        """按层取五动作端口（register_toolchain_units 之后可用）。"""
        return self._ports.get(kind)

    def _toolchain_target(self, kind):
        if kind == "interp_host":
            from src.interp import Interpreter
            return Interpreter(debug=False)
        if kind == "compiler":
            from src.compiler.pass_manager import PassManager
            return PassManager()
        if kind == "vm":
            return VM(Compiler().compile_program(ast.Program(decls=[])))
        if kind == "interp_boot":
            return self._get_boot_vm()
        return None  # parser / kernel 无运行时目标

    def _get_boot_vm(self) -> VM:
        if self._boot_vm is None:
            comp = Compiler()
            decls: list = []
            for rel in _BOOT_CHAIN_FILES:
                decls.extend(py_parse(_read_repo(rel)).decls)
            vm = VM(comp.compile_program(ast.Program(decls=decls)))
            with contextlib.redirect_stdout(io.StringIO()):
                vm.run()
            self._boot_vm = vm
        return self._boot_vm

    def _toolchain_impl(self, kind, entry):
        if kind == "parser":
            return (6, "left", None)
        if kind in ("interp_host", "vm"):
            return lambda x: x
        if kind == "interp_boot":
            return "(ps) => ps[0]"
        if kind == "compiler":
            from src.compiler.pass_manager import Pass

            class _PortPass(Pass):
                def run(self, program):
                    return program

            return _PortPass(entry)
        return None  # kernel

    def _make_toolchain_step(self, kind):
        port = self._ports[kind]

        def 步(状态):
            if 状态 is not None:
                return {"状态": 状态, "继续": False, "产出": []}
            st = port.state()
            return {"状态": "运行中", "继续": True,
                    "产出": [f"{st['层']} 条目{len(st['条目'])} 审计{len(st['审计'])}"]}
        步.__name__ = f"toolchain_step:{kind}"
        return 步

    def _toolchain_toggle(self, unit: str, on: bool) -> None:
        hit = self._toolchain.get(unit)
        if hit is not None:
            self._ports[hit[0]].toggle(hit[1], on)

    def _find_descriptor(self, name: str) -> dict | None:
        for d in self.descriptors():
            if d["名"] == name:
                return d
        return None

    # ============================================================
    # 形态特定步闭包（全部一次性/轮询式，契约 步(状态)→报）
    # ============================================================

    def _make_source_step(self, name: str, source: str):
        def 步(状态):
            if 状态 is not None:
                return {"状态": 状态, "继续": False, "产出": []}
            outs, err = _run_source(source)
            return {"状态": err or "完成", "继续": False, "产出": outs}
        步.__name__ = f"source_step:{name}"
        return 步

    def _make_command_step(self, name: str, handler: Path):
        def 步(状态):
            if 状态 is not None:
                return {"状态": 状态, "继续": False, "产出": []}
            src = handler.read_text(encoding="utf-8") + "\n处理([])"
            outs, err = _run_source(src)
            return {"状态": err or "完成", "继续": False, "产出": outs}
        步.__name__ = f"command_step:{name}"
        return 步

    def _make_plugin_step(self, name: str):
        def 步(状态):
            from src.plugin_api import get_resolver

            resolver = get_resolver()
            plugin = resolver.plugin(name)
            if plugin is None:
                resolver.reload()
                plugin = resolver.plugin(name)
            if plugin is None:
                return {"状态": "注册缺失", "继续": False, "产出": []}
            return {"状态": "已注册", "继续": False,
                    "产出": [f"符号数 {len(plugin.symbols)}"]}
        步.__name__ = f"plugin_step:{name}"
        return 步

    def _make_external_step(self, name: str, argv: list):
        def 步(状态):
            cell = self._handles.setdefault(name, {})
            proc = cell.get("proc")
            if proc is None:
                if 状态 is not None:
                    # 已被桥面终止：报告终态，不再重生
                    return {"状态": 状态, "继续": False, "产出": []}
                proc = subprocess.Popen(
                    argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(self._root))
                cell["proc"] = proc
                cell["argv"] = list(argv)
                return {"状态": "运行中", "继续": True, "产出": []}
            code = proc.poll()
            if code is None:
                return {"状态": "运行中", "继续": True, "产出": []}
            out = proc.communicate()[0] or ""
            cell.pop("proc", None)
            cell["退出码"] = code
            cell["输出"] = out.splitlines()
            return {"状态": code, "继续": False, "产出": out.splitlines()}
        步.__name__ = f"external_step:{name}"
        return 步

    # ============================================================
    # 生命周期（全部经内核协商；本桥只补形态特定动作）
    # ============================================================

    def load_all(self) -> list[dict]:
        results = []
        for d in self.descriptors():
            results.append(self._call("装载", self._k, d))
        return results

    def load_descriptor(self, desc: dict) -> dict:
        return self._call("装载", self._k, desc)

    def start(self, name: str) -> dict:
        日志起 = len(self._k[5])
        result = self._call("启动", self._k, name)
        if result.get("结果") == "运行中":
            if self._收旧发生(name, 日志起):
                self._终止载体(name)
            self._toolchain_toggle(name, True)
        return result

    def start_process(self, name: str, 入口: str = "主") -> dict:
        return self._call("启动进程", self._k, name, 入口)

    def stop(self, name: str) -> dict:
        result = self._call("停止", self._k, name)
        if result.get("结果") == "已停止":
            self._终止载体(name)
            from src.plugin_api import get_resolver

            resolver = get_resolver()
            d = self._find_descriptor(name)
            if d is not None and d["形态"] == "域插件":
                resolver.unregister(name)
            self._toolchain_toggle(name, False)
        return result

    def unload(self, name: str, 强制: bool = False) -> dict:
        result = self._call("卸载", self._k, name, bool(强制))
        if result.get("结果") == "已卸载":
            self._终止载体(name)
        return result

    # ---- 载体进程回收（44c）----
    #
    # 内核的 收旧进程/停止进程 只改簿记：它不持有 OS 句柄，也不该持有
    # （纯 Matha 内核面没有进程映像原语，见 src/interp.py 映像族拒绝口径）。
    # 簿记改判与 OS 回收分属两面，本桥在内核判定落地之后补那一步真终止；
    # 判定被拒时也收（如 卸载 一个运行中单元）会把「拒绝」做成真伤害——
    # 簿记说还在运行，OS 侧进程已经没了。回收同时交还句柄格，否则再启动的
    # 主进程步会复用旧 Popen 句柄读到上一次运行的退出码。

    def _终止载体(self, name: str) -> bool:
        """终止该单元名的载体进程并交还槽位（幂等：无载体即 假）。

        回收粒度是「单元」：句柄表每名一格，多条就绪进程共用一格时无法按
        内核 pid 归属——这是宿主桥的既有形状（模块诚实边界注）。
        """
        cell = self._handles.get(name)
        proc = cell.pop("proc", None) if cell is not None else None
        if proc is None:
            return False
        try:
            proc.terminate()
        except OSError:
            pass
        return True

    def _收旧发生(self, name: str, 日志起: int) -> bool:
        """本轮 启动 是否触发了内核 收旧进程 事件（日志条目 [事件, 名, pids]）。"""
        return any(e[0] == "收旧进程" and e[1] == name for e in self._k[5][日志起:])

    def _进程行of(self, pid: int):
        for row in self.process_list():
            if row[0] == pid:
                return row
        return None

    def _就绪数(self, 单元名: str) -> int:
        return sum(1 for row in self.process_list()
                   if row[1] == 单元名 and row[3] == "就绪")

    def upgrade(self, name: str, desc: dict) -> dict:
        return self._call("升级", self._k, name, desc)

    def rollback(self, name: str) -> dict:
        return self._call("回滚", self._k, name)

    def tick(self, 轮数: int = 1) -> dict:
        return self._call("调度", self._k, int(轮数))

    def supervision(self, name: str):
        """内核监督读数（常驻/预算/就绪主进程数/已退出次数）；未装载 → null。"""
        return self._call("监督状态", self._k, name)

    def supervise(self, 轮数: int = 1, 间隔: float = 0.0, 回报=None) -> list[dict]:
        """把内核调度轮接上墙钟——每轮 `调度(1)`，重启判定在内核轮尾发生。

        监督策略不在这里：本方法只数轮次、按 `间隔` 睡眠、把每轮读数交给
        `回报`（默认 None 不打印）。`轮数 <= 0` 即不限轮（Ctrl-C 由调用方
        收口——KeyboardInterrupt 原样上抛，本方法不吞中断）。
        """
        rounds: list[dict] = []
        i = 0
        while 轮数 <= 0 or i < int(轮数):
            i += 1
            r = self.tick(1)
            rounds.append(r)
            if 回报 is not None:
                回报(r)
            if 间隔 > 0:
                time.sleep(float(间隔))
        return rounds

    def stop_process(self, pid: int) -> dict:
        pid = int(pid)
        行 = self._进程行of(pid)
        单元名 = 行[1] if 行 is not None else None
        result = self._call("停止进程", self._k, pid)
        if result.get("结果") == "已停止" and 单元名 is not None \
                and self._就绪数(单元名) == 0:
            self._终止载体(单元名)
        return result

    # ============================================================
    # 查询
    # ============================================================

    def unit_info(self, name: str):
        info = self._call("查询单元", self._k, name)
        if isinstance(info, dict):
            cell = self._handles.get(name, {})
            info["桥"] = {
                "进程活": cell.get("proc") is not None,
                "退出码": cell.get("退出码"),
                "输出": cell.get("输出"),
            }
        return info

    def inspect(self) -> dict:
        report = self._call("体检", self._k)
        handles = {}
        for name, cell in self._handles.items():
            handles[name] = {
                "进程活": cell.get("proc") is not None,
                "退出码": cell.get("退出码"),
            }
        report["桥"] = {"根": str(self._root), "句柄": handles}
        return report

    def process_list(self) -> list:
        return self._call("进程列表", self._k)

    def resolve_service(self, name: str):
        return self._call("服务_解析", self._k, name)

    def log(self) -> list:
        return list(self._k[5])


def make_os_runtime(root: str | Path | None = None) -> OsRuntime:
    """宿主桥工厂（26a make_vm 命名约定同源）：共生体运行时统一入口。"""
    return OsRuntime(root=root)
