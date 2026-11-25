# -*- coding: utf-8 -*-
"""Matha 自举链会话 —— 用 Matha 自己的装载器/解释器装载并执行 Matha 模块（阶段 42c）。

薄壳纪律：本模块只做**装配与调用**，不含任何业务逻辑。装载、依赖解析、模块体
执行、函数应用全部由 Matha 完成：boot 链（词法器/语法器/标准库/运行时引擎/
解释器）+ 纯 Matha 装载器（matha/loader.matha）由宿主编译器编为 M3V、宿主 VM
执行（level-1），被装载的模块体经 ``解释器.执行语句`` 以 Matha 数据闭包执行
（level-2）。宿主 Python 仅作 OS 能力的载体（boot VM 全局的内建实现 + os 域
插件符号）。

诚实边界：与 Track B 对拍驱动器（``scripts/selfhost_matrix.py``）不同，本模块
**不注入宿主内建全表面**——链面能用什么，取决于 ``matha/interp_matha.matha``
的 ``应用内建实`` 逐名臂与 ``matha/loader.matha``；缺臂的名字如实报错，不静默
回落宿主实现。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: 冻结态（PyInstaller）判别：`sys._MEIPASS` 是本次运行的解包根，`sys.executable`
#: 是 matha.exe 自身。开发态两者皆无，资产根即仓库根。
_FROZEN = bool(getattr(sys, "frozen", False))
_ASSET_ROOT = (Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
               if _FROZEN else _REPO_ROOT)
_EXE_DIR = Path(sys.executable).resolve().parent if _FROZEN else None

#: boot 链五模块 + 纯 Matha 装载器（宿主编译面，level-1）
BOOT_FILES: tuple[str, ...] = (
    "matha/lexer.matha",
    "matha/stdlib.matha",
    "matha/parser.matha",
    "matha/runtime/matha_runtime.matha",
    "matha/interp_matha.matha",
    "matha/loader.matha",
)

#: 链面词法器是字符级扫描递归，成本随源长线性增长；库级源需要比默认更深的
#: 栈预算（与 Track B worker 同口径，非产品缺陷——见 KNOWN_ISSUES 阶段 40 ④）。
_RECURSION_FLOOR = 20000


def _override_roots() -> list[Path]:
    """用户显式指定的语料根（阶段 43a-2）——排在内置根之前。

    `MATHA_HOME` 指向一棵 `matha/` 语料树：改过 `.matha` 又不必重打包时用。
    同级目录（冻结态 `matha.exe` 旁的 `matha/`）排在它之后、包内快照之前，
    只作「包内没有的模块」的补充位——包内语料是**构建期快照**，与 exe 的
    解释器版本同源，优先级高于外部漂移副本；升级面（`.matha_packages/`）
    另走 `装载包根们`，见 `_package_roots()`。
    """
    out: list[Path] = []
    env = os.environ.get("MATHA_HOME", "").strip()
    if env:
        out.append(Path(env))
    if _EXE_DIR is not None:
        out.append(_EXE_DIR)
    return out


def _roots() -> list[Path]:
    """主/库面装载根候选序——逐条镜像宿主 `src/interp.py:_matha_dir()` 的
    `_candidates`（仓库根 → cwd 上跳 → cwd），前面插 `_override_roots()`。
    """
    return _override_roots() + [_ASSET_ROOT, Path.cwd().parent, Path.cwd()]


def _package_roots() -> list[Path]:
    """扩展包面根序——镜像宿主 `_package_module_path()` 的 `(cwd, 仓库根)`
    **cwd 在前**（42-② 的根序分歧即此：链面此前只有仓库根一根）。
    """
    return _override_roots() + [Path.cwd(), _ASSET_ROOT]


def _corpus_root() -> Path:
    """首个真正含 `matha/` 语料的根（宿主 `_matha_dir()` 的 exists 环同判）；
    全不命中时回落候选首位——与宿主「return candidates[0]」同一诚实落点。
    """
    for r in _roots():
        if (r / "matha").is_dir():
            return r
    return _roots()[0]


def _read(rel: str) -> str:
    """boot 链装配源读取——六件一律取自**同一个**语料根，不逐件跨根混 pick：
    词法器与解释器镜像不同源会让 boot 链自相矛盾（且难以后复现）。
    """
    p = _corpus_root() / rel
    if not p.is_file():
        raise FileNotFoundError(
            f"装配源缺失: {rel}（语料根 {p.parent}，候选 "
            f"{', '.join(str(r) for r in _roots())}）")
    text = p.read_text(encoding="utf-8")
    return text.lstrip("﻿") if text and text[0] == "﻿" else text


def build_boot_vm():
    """装配 boot 链 VM：宿主解析/编译 Matha 工具链源，宿主 VM 执行其字节码。"""
    from src import ast_nodes as ast
    from src.kernel.errors import MathaRuntimeError
    from src.mbc.compiler import Compiler
    from src.mbc.vm import VM
    from src.parser import parse as py_parse

    if sys.getrecursionlimit() < _RECURSION_FLOOR:
        sys.setrecursionlimit(_RECURSION_FLOOR)
    sys.set_int_max_str_digits(0)

    comp = Compiler()
    decls: list = []
    for rel in BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    # 装载根：matha/loader.matha 的 根() 读此名产绝对路径——宿主 _matha_dir()
    # 首候选即仓库根（非 cwd），终端 换目录 之后装载仍须命中同一批源。
    # 43a-2 起该名取「首个真含 matha/ 的根」（宿主 _matha_dir 的 exists 环同判），
    # 并额外注入候选全集 装载根们 / 扩展包面 装载包根们，使链面解析序与宿主
    # 逐条同构（42-② 的 cwd 根序分歧由此闭合）。
    vm.globals["装载根"] = str(_corpus_root())
    vm.globals["装载根们"] = [str(r) for r in _roots()]
    vm.globals["装载包根们"] = [str(r) for r in _package_roots()]
    # os 域插件符号（执行命令 / 升级包 / 检查包更新 等）经此懒物化入全局；
    # 链面 应用内建实 的裸名委托正是要命中这些载体实现。
    from src.plugin_api import get_resolver
    vm.domain_resolver = get_resolver()
    return vm


class MathaChain:
    """一次 boot 链会话（进程内复用；装载结果按模块名缓存）。"""

    def __init__(self):
        self._vm = None
        self._env = None
        self._nss: dict[str, dict] = {}

    @property
    def vm(self):
        if self._vm is None:
            self._vm = build_boot_vm()
            self._env = self._vm.call("注册内建", self._vm.call("空环境"))
        return self._vm

    @property
    def env(self):
        """链面固定环境（注册内建 产物）——应用函数的 call_env。"""
        self.vm  # 触发装配
        return self._env

    def load(self, module_name: str) -> dict:
        """装载器.装载：Matha 自身解析源、递归装依赖、执行模块体、产命名空间。"""
        if module_name not in self._nss:
            loader = self.vm.globals.get("装载器")
            if not isinstance(loader, dict) or "装载" not in loader:
                raise RuntimeError(
                    "boot 链缺少 装载器 模块（matha/loader.matha 未进 BOOT_FILES）")
            ns = self.vm.invoke_value(loader["装载"], [module_name])
            self.vm.outputs.clear()
            if not isinstance(ns, dict):
                raise RuntimeError(f"装载器.装载({module_name!r}) 未产生命空间: {ns!r}")
            self._nss[module_name] = ns
        return self._nss[module_name]


def make_term_runner(chain: MathaChain | None = None):
    """终端执行器的链面调用器：``run(line) -> {"输出": [...], "退出": bool}``。

    与宿主面 ``_make_host_runner`` 同契约（结果帧字段一致），差别只在执行体：
    命令逻辑跑在 Matha 装载出来的数据闭包上，而非宿主 Python 树遍历器。
    """
    session = chain or MathaChain()
    ns = session.load("终端执行器")
    if "终端运行一行" not in ns:
        raise RuntimeError(
            "终端执行器 命名空间缺 终端运行一行（matha/term_engine.matha 装载不完整）")
    vm = session.vm
    one_line = ns["终端运行一行"]
    env = session.env

    def run(line: str) -> dict:
        vm.outputs.clear()
        frame = vm.call("应用函数", one_line, line, env)
        if not isinstance(frame, dict):
            raise RuntimeError(f"终端运行一行 未返回结果帧: {frame!r}")
        return frame

    return run
