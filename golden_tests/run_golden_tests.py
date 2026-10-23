#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 黄金测试运行器。

每个 *.matha 用例由当前主线解释器执行：
    src.parser.parse -> src.interp.Interpreter.run

Matha 的 stdout 是解释器的 outputs 缓冲区；本脚本把每个输出值按 JSON
序列化为一行，以同时冻结值与类型（14 与 "14" 不同）。未被捕获的异常
按 ``异常类型: 消息`` 写入 stderr 基准。用例可声明的特性开关写在
manifest.json 中，避免依赖进程环境。

用法：
    python golden_tests/run_golden_tests.py
    python golden_tests/run_golden_tests.py --update
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import io
import json
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

CASES_DIR = HERE / "cases"
EXPECTED_DIR = HERE / "expected"
MANIFEST_PATH = HERE / "manifest.json"

_ENV_KEYS = {"MATHA_FEATURES", "MATHA_DEBUG", "MATHA_AUTO_HEAL"}


def _sanitize_env() -> None:
    for key in list(os.environ):
        if key in _ENV_KEYS or key.startswith("MATHA_FEATURE_"):
            del os.environ[key]


def _json_value(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return repr(value)


def render_stdout(outputs: list) -> str:
    return "".join(f"[{index}] {_json_value(value)}\n"
                   for index, value in enumerate(outputs))


def render_stderr(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    return f"{type(exc).__name__}: {exc}\n"


def run_case(path: Path, defaults: dict, case_meta: dict) -> tuple[str, str]:
    source = path.read_text(encoding="utf-8")
    features.clear_feature()
    for name, enabled in defaults.items():
        features.set_feature(name, bool(enabled))
    for name in case_meta.get("features", []):
        features.set_feature(name, True)

    interp = Interpreter(debug=False)
    exc = None
    py_stdout = io.StringIO()
    py_stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(py_stdout), contextlib.redirect_stderr(py_stderr):
            interp.run(parse(source))
    except BaseException as error:  # noqa: BLE001 - 基准必须记录所有失败路径
        exc = error
    finally:
        features.clear_feature()

    stdout = render_stdout(interp.outputs)
    stderr = render_stderr(exc)
    raw_stdout = py_stdout.getvalue()
    raw_stderr = py_stderr.getvalue()
    if raw_stdout:
        stdout = f"[PY_STDOUT]\n{raw_stdout}{stdout}"
    if raw_stderr:
        stderr = f"[PY_STDERR]\n{raw_stderr}{stderr}"
    return stdout, stderr


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _diff(expected: str, actual: str, label: str, stem: str) -> str:
    return "".join(difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=f"golden/{stem}.{label}",
        tofile=f"actual/{stem}.{label}",
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 Matha 黄金测试")
    parser.add_argument("--update", action="store_true", help="用当前行为重写基准输出")
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    defaults = manifest.get("defaults", {})
    case_meta = manifest.get("cases", {})
    case_files = sorted(CASES_DIR.glob("*.matha"))

    stems = [path.stem for path in case_files]
    missing = sorted(set(case_meta) - set(stems))
    unlisted = sorted(set(stems) - set(case_meta))
    if missing or unlisted:
        if missing:
            print(f"manifest 中存在无源码的用例: {', '.join(missing)}", file=sys.stderr)
        if unlisted:
            print(f"cases 中存在未登记的用例: {', '.join(unlisted)}", file=sys.stderr)
        return 2

    _sanitize_env()
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    passed = 0
    failed = 0

    for path in case_files:
        stem = path.stem
        actual_stdout, actual_stderr = run_case(
            path, defaults, case_meta.get(stem, {})
        )
        stdout_path = EXPECTED_DIR / f"{stem}.out"
        stderr_path = EXPECTED_DIR / f"{stem}.err"

        if args.update:
            _write(stdout_path, actual_stdout)
            _write(stderr_path, actual_stderr)
            print(f"[UPDATED] {stem}")
            continue

        expected_stdout = _read(stdout_path)
        expected_stderr = _read(stderr_path)
        if expected_stdout == actual_stdout and expected_stderr == actual_stderr:
            print(f"[PASS] {stem}")
            passed += 1
            continue

        failed += 1
        print(f"[FAIL] {stem}")
        if expected_stdout != actual_stdout:
            print(_diff(expected_stdout, actual_stdout, "out", stem), end="")
        if expected_stderr != actual_stderr:
            print(_diff(expected_stderr, actual_stderr, "err", stem), end="")

    if args.update:
        print(f"已更新 {len(case_files)} 个基准用例")
        return 0

    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
