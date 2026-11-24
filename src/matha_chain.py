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

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

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


def _read(rel: str) -> str:
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
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
    vm.globals["装载根"] = str(_REPO_ROOT)
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
