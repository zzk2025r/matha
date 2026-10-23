#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 黄金测试运行器（基线文件比对版）。

扫描 tests/ 目录选取的核心 .matha 用例，使用当前主线解释器
（src.parser.parse -> src.interp.Interpreter.run）重新运行，捕获 stdout/stderr，
并与 golden_tests/ 下对应的 .stdout/.stderr 基线文件进行严格文本比对。

仅当完全一致时输出 [PASS]，不一致时输出 [FAIL] 并打印具体差异。
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import io
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import features
from src.interp import Interpreter
from src.parser import parse

TESTS_DIR = ROOT / "tests"
GOLDEN_DIR = HERE

# 核心用例：从 tests/test_interpreter.py 等代表性场景提炼
CASES = [
    ("test_arith.matha", [], "#1：[2 + 3 * 4]\n#1：[10 >= 5]\n#1：[\"func\" = \"func\"]\n"),
    ("test_func.matha", [], "func 推进(c: Int) -> Int = (c) => c + 1\n输出(推进(5))\n输出(推进(10))\n"),
    ("test_curried_closure.matha", [], "func add(a: Int, b: Int) -> Int = (a, b) => a + b\n输出(add(3)(4))\nfunc mk(n: Int) -> Int = (n) => (x) => n + x\nlet f = mk(10)\n输出(f(5))\n"),
    ("test_block_tail.matha", [], "#：{\n  x = 5\n  y = x * 2\n  [y]\n}\n"),
    ("test_try_raise.matha", [], '#：{\n  try { raise "boom" } catch (e) { 结果 = e }\n  [结果]\n}\n'),
    ("test_try_runtime.matha", [], '#：{\n  try { 列表 = [1, 2]\n  get(列表)(9) } catch (e) { 结果 = "越界" }\n  [结果]\n}\n'),
    ("test_match.matha", [], 'match 3 {\n| 1 => 输出("a")\n| 3 => 输出("b")\n| _ => 输出("c")\n}\n'),
    ("test_scoped_block_tail_if.matha", ["SCOPED_BLOCKS"], "func f(t: Int) -> Int = (t) => {\n  if t > 5 { 1 } else { 0 }\n}\n[f(10)]\n[f(1)]\n"),
    ("test_scoped_multi.matha", ["SCOPED_BLOCKS"], "func f(x: Int) -> Int = (x) => {\n  a = x + 1\n  b = a * 2\n  b - a\n}\n[f(3)]\n"),
    ("test_loops.matha", [], "let i = 0\nlet s = 0\nwhile i < 5 {\n  s = s + i\n  i = i + 1\n}\n输出(s)\nlet t = 0\nfor x in [1, 2, 3, 4] {\n  t = t + x\n}\n输出(t)\n"),
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_case(source: str, flags: list[str]) -> tuple[str, str]:
    features.clear_feature()
    for f in flags:
        features.set_feature(f, True)

    out_buf: list[str] = []
    err_buf: list[str] = []

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    class _W:
        def __init__(self, buf: list[str]):
            self.buf = buf

        def write(self, s: str) -> int:
            self.buf.append(s)
            return len(s)

        def flush(self) -> None:
            pass

    try:
        sys.stdout = _W(out_buf)
        sys.stderr = _W(err_buf)
        interp = Interpreter(debug=False)
        interp.run(parse(source))
    except BaseException as e:  # noqa: BLE001
        err_buf.append(f"{type(e).__name__}: {e}\n")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        features.clear_feature()

    return "".join(out_buf), "".join(err_buf)


def _diff(a: str, b: str, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matha 黄金测试（基线 .stdout/.stderr 比对）")
    parser.add_argument("--update", action="store_true", help="用当前输出重写基线文件")
    args = parser.parse_args(argv)

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    all_pass = True

    for name, flags, source in CASES:
        stem = name.replace(".matha", "")
        out_path = GOLDEN_DIR / f"{stem}.stdout"
        err_path = GOLDEN_DIR / f"{stem}.stderr"

        actual_out, actual_err = run_case(source, flags)

        if args.update:
            _write(out_path, actual_out)
            _write(err_path, actual_err)
            print(f"[UPDATED] {stem}")
            continue

        exp_out = _read(out_path)
        exp_err = _read(err_path)

        if actual_out == exp_out and actual_err == exp_err:
            print(f"[PASS] {stem}")
            continue

        all_pass = False
        print(f"[FAIL] {stem}")
        if actual_out != exp_out:
            print(_diff(exp_out, actual_out, f"golden_tests/{stem}.stdout", f"current/{stem}.stdout"), end="")
        if actual_err != exp_err:
            print(_diff(exp_err, actual_err, f"golden_tests/{stem}.stderr", f"current/{stem}.stderr"), end="")

    if args.update:
        print(f"已更新 {len(CASES)} 个基线文件")
        return 0

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
