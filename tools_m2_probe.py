# -*- coding: utf-8 -*-
"""M2 定点探针：比较 Python 宿主编译器(stage2)与自举 Matha 编译器(stage3)的产物。

用法：
    python tools_m2_probe.py [目标.matha ...]
无参数时用内置小样例 + compiler_matha.matha 自身。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path('.').resolve()))

from src import ast_nodes as ast
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src.parser import parse as py_parse

ROOT = pathlib.Path('.').resolve()
BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
              "matha/parser.matha", "matha/interp.matha",
              "matha/compiler_matha.matha"]

SAMPLES = {
    "const": "#1：[42]",
    "arith": "func f(a: Int, b: Int) -> Int = (a, b) => a * b + 1\n#1：[f(6, 7)]",
    "recursion": ("func fact(n: Int) -> Int = (n) =>\n"
                  "  if n <= 1 then 1 else n * fact(n - 1)\n"
                  "#1：[fact(5)]"),
    "lambda": "let g = (x: Int) => x + 1\n#1：[g(41)]",
    "list": "#1：[[1, 2, 3]]",
    "dict": 'd = {"a": 1}\n#1：[d["a"]]',
}


def _read(rel: str) -> str:
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src and src[0] == "﻿" else src


def host_compile(src: str) -> MModule:
    return Compiler().compile_program(py_parse(src))


def self_dict_to_module(d) -> MModule:
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def canon(mod: MModule):
    """归一化为可比较的纯 python 结构。"""
    return {
        "module": mod.module_name,
        "constants": list(mod.constants),
        "main": [tuple(i) for i in mod.main_code],
        "functions": {
            name: (fn.arity, fn.nlocals, list(fn.params),
                   [tuple(i) for i in fn.code])
            for name, fn in mod.functions.items()
        },
    }


def first_diff(a, b, path="") -> str | None:
    """返回首个差异描述，无差异返回 None。"""
    if type(a) is not type(b) and not (
            isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return f"{path}: 类型 {type(a).__name__} != {type(b).__name__} | {a!r} vs {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return f"{path}[{k!r}]: 仅 stage3 存在 = {b[k]!r}"[:300]
            if k not in b:
                return f"{path}[{k!r}]: 仅 stage2 存在 = {a[k]!r}"[:300]
            d = first_diff(a[k], b[k], f"{path}[{k!r}]")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: 长度 {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def build_stage1():
    decls = []
    for rel in BOOT_FILES:
        decls.extend(py_parse(_read(rel)).decls)
    comp = Compiler()
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def main(argv):
    vm = build_stage1()
    print(f"stage1 自举编译器就绪（{' + '.join(BOOT_FILES)}）")

    targets = list(SAMPLES.items())
    for rel in argv:
        targets.append((rel, _read(rel)))

    ok = 0
    for name, src in targets:
        try:
            a = canon(host_compile(src))
        except Exception as e:  # noqa: BLE001
            print(f"  [SKIP] {name}: 宿主编译失败 {type(e).__name__}: {e}")
            continue
        try:
            d = vm.call("编译", src)
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] {name}: stage3 抛错 {type(e).__name__}: {e}")
            continue
        b = canon(self_dict_to_module(d))
        diff = first_diff(a, b)
        if diff is None:
            print(f"  [ OK ] {name}: 定点一致 "
                  f"({len(a['functions'])} 函数, {len(a['constants'])} 常量)")
            ok += 1
        else:
            print(f"  [DIFF] {name}: {diff}")
    print(f"\n一致 {ok}/{len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
