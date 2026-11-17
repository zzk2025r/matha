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
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from pathlib import Path

from src import ast_nodes as ast
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.parser import parse as py_parse

_REPO_ROOT = Path(__file__).resolve().parent.parent

_KERNEL_FILES = ["matha/stdlib.matha", "matha/os/kernel.matha"]

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


class OsRuntime:
    """五形态 + 外部单元的统一运行时（内核持有唯一权威状态）。"""

    def __init__(self, root: str | Path | None = None):
        self._root = Path(root) if root else Path.cwd()
        self._vm = _build_kernel_vm()
        self._k = self._call("内核_新")
        self._external: dict[str, list] = {}
        self._handles: dict[str, dict] = {}

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
        for name, (argv, 版本) in sorted(self._external.items()):
            units.append({
                "名": name,
                "形态": "外部",
                "版本": 版本,
                "requires": [],
                "入口": [["主", self._make_external_step(name, list(argv))]],
                "服务": [],
                "argv": list(argv),
            })
        return units

    # ============================================================
    # 登记（程序化单元：外部 / 服务）
    # ============================================================

    def register_external(self, name: str, argv: list[str],
                          版本: int = 1) -> dict:
        self._external[name] = [list(argv), int(版本)]
        return self._find_descriptor(name)

    def register_service(self, name: str, step, 服务名s=(),
                         版本: int = 1, requires=()) -> dict:
        desc = {
            "名": name, "形态": "服务", "版本": int(版本),
            "requires": list(requires),
            "入口": [["主", step]], "服务": list(服务名s),
        }
        self._call("装载", self._k, desc)
        return desc

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
        return self._call("启动", self._k, name)

    def start_process(self, name: str, 入口: str = "主") -> dict:
        return self._call("启动进程", self._k, name, 入口)

    def stop(self, name: str) -> dict:
        cell = self._handles.get(name)
        if cell and cell.get("proc") is not None:
            try:
                cell["proc"].terminate()
            except OSError:
                pass
        result = self._call("停止", self._k, name)
        if result.get("结果") == "已停止":
            from src.plugin_api import get_resolver

            resolver = get_resolver()
            d = self._find_descriptor(name)
            if d is not None and d["形态"] == "域插件":
                resolver.unregister(name)
        return result

    def unload(self, name: str, 强制: bool = False) -> dict:
        cell = self._handles.get(name)
        if cell and cell.get("proc") is not None:
            try:
                cell["proc"].terminate()
            except OSError:
                pass
        return self._call("卸载", self._k, name, bool(强制))

    def upgrade(self, name: str, desc: dict) -> dict:
        return self._call("升级", self._k, name, desc)

    def rollback(self, name: str) -> dict:
        return self._call("回滚", self._k, name)

    def tick(self, 轮数: int = 1) -> dict:
        return self._call("调度", self._k, int(轮数))

    def stop_process(self, pid: int) -> dict:
        return self._call("停止进程", self._k, int(pid))

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
