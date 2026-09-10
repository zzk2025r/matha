# -*- coding: utf-8 -*-
"""M3V 命令行工具：编译 / 运行字节码 / 表达式求值 / 原生编译。

用法：
  python -m src.mbc.cli compile 源文件.matha [-o 输出.mbc]
  python -m src.mbc.cli run     程序.mbc | 程序.matha
  python -m src.mbc.cli eval    "表达式"
  python -m src.mbc.cli native  源文件.matha -o 输出.exe
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.mbc import compile_source, run_module, write_mbc, read_mbc


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_compile(args) -> int:
    source = _read(args.source)
    mod = compile_source(source)
    out = args.output or (Path(args.source).with_suffix(".mbc"))
    write_mbc(mod, str(out))
    n_fn = len(mod.functions)
    n_ins = sum(len(fn.code) for fn in mod.functions.values()) + len(mod.main_code)
    print(f"已编译 {args.source} → {out}")
    print(f"  模块 '{mod.module_name}'：{n_fn} 个函数，{n_ins} 条指令，"
          f"{len(mod.constants)} 个常量")
    return 0


def cmd_run(args) -> int:
    path = Path(args.target)
    if path.suffix == ".mbc":
        mod = read_mbc(str(path))
    else:
        mod = compile_source(_read(str(path)))
    outputs = run_module(mod, verbose=True)
    if not outputs:
        print("（无输出）")
    return 0


def cmd_eval(args) -> int:
    source = f"result = {args.expr}\n#1：[result]"
    outputs = run_module(compile_source(source))
    if outputs:
        print(outputs[-1])
    return 0


def cmd_native(args) -> int:
    from src.mbc.native import compile_to_exe
    source = _read(args.source)
    out = args.output or (Path(args.source).with_suffix(".exe"))
    exe = compile_to_exe(source)
    Path(out).write_bytes(exe)
    print(f"已编译 {args.source} → {out}（{len(exe)} 字节）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mbc", description="M3V 字节码工具链")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("compile", help="编译 .matha → .mbc")
    p_c.add_argument("source", help=".matha 源文件")
    p_c.add_argument("-o", "--output", help="输出 .mbc 路径")
    p_c.set_defaults(func=cmd_compile)

    p_r = sub.add_parser("run", help="运行 .mbc 或 .matha")
    p_r.add_argument("target", help=".mbc 字节码或 .matha 源文件")
    p_r.set_defaults(func=cmd_run)

    p_e = sub.add_parser("eval", help="求值单个表达式")
    p_e.add_argument("expr", help="Matha 表达式")
    p_e.set_defaults(func=cmd_eval)

    p_n = sub.add_parser("native", help="编译 .matha → .exe（x86-64 原生）")
    p_n.add_argument("source", help=".matha 源文件")
    p_n.add_argument("-o", "--output", help="输出 .exe 路径")
    p_n.set_defaults(func=cmd_native)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
