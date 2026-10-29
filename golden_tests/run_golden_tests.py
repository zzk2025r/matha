#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 黄金测试运行器（多后端逐字节比对）。

三个口径，一个数字：

1. **主链（vm）** —— `src.parser.parse → src.mbc.compiler.compile_source →
   src.mbc.vm.run_module`（经 `src.kernel.exec_api` 接入插件层）。基线在
   `golden_tests/vm/`，逐字节锁定「重构前 / 重构后」的 VM 输出一致（阶段 0 第 3 项）。
2. **遗留后端（interp）** —— `src.interp.Interpreter.run`。基线是仓库里既有的
   `golden_tests/expected/`（重构前的真相），用于验证主链没有丢能力。
3. **原生后端（native）** —— `src.mbc.native` 发射的 exe，真实跑一遍并逐字节
   比对 stdout（需本机可用 nasm/link；不可用时明确报 SKIPPED，绝不静默当通过）。

跨后端 stdout 必须一致；不一致即 FAIL。stderr 的**异常类名**在两后端确有差异
（解释器统一 `MathaRuntimeError`，VM 的部分路径仍是 Python 原生异常），差异被
如实列进报告表，不做静默抹平，也不放宽任何断言。

用法：
  python golden_tests/run_golden_tests.py             # 校验（vm + interp）
  python golden_tests/run_golden_tests.py --update     # 重写基线（改动 VM 语义后须显式做）
  python golden_tests/run_golden_tests.py --native     # 追加原生 exe 对拍

标准库预加载：manifest 的 `cases.<stem>` 可带 `"preload": ["matha/library/….matha"]`，
库源码**前置拼接**进用例文本后三端跑同一模块 —— 与 tests/test_mbc_bootstrap.py
多文件拼接同构，三端口径天然一致（库不是宿主内建，不需要单独注入）。
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import features
from src.kernel import exec_api

MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
CASES_DIR = HERE / "cases"
INTERP_DIR = HERE / "expected"        # 既有基线：`{stem}.out` / `{stem}.err`
VM_DIR = HERE / "vm"                   # 主链基线：同上命名

# 机器码后端的已知未实现项（用例名 -> 原因）。存在意义是让差异**可审计**：
# 命中名单的 native 差异报 KNOWN-GAP（不记作通过），不在名单的新差异直接 FAIL，
# 而对已修好却还挂在名单上的项报 STALE 并要求删除 —— 不允许静默长大也不允许静默缩小。
NATIVE_GAPS: dict[str, str] = MANIFEST.get("native_known_gaps", {})

# 已知的跨后端 stderr 差异：解释器把运行时错误统一包装成 MathaRuntimeError，
# VM 的部分路径仍透传 Python 原生异常。类名差异走上面的 `_err_body` 白名单，
# 消息主体则要求逐字一致（见 check_case），因此这里不需额外表项。


# ============================================================
# 值的黄金渲染（后端无关的规范形式）
# ============================================================

def render(value: object) -> str:
    """把一个 Matha 输出值渲染为基线文本。

    布尔按 Matha 字面量 `true/false`（Python 的 `True` 会泄露宿主语言），
    字符串加引号以区分 `"1"` 与 `1`，列表逐元素递归。
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(render(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{render(k)}: {render(v)}" for k, v in value.items()) + "}"
    return str(value)


def format_outputs(outputs: list) -> str:
    return "".join(f"[{i}] {render(v)}\n" for i, v in enumerate(outputs))


def format_plain(outputs: list) -> str:
    """宿主原生文本口径（与 `mbc.native` 发的 exe 一致）：bool 用 True/False，
    字符串不加引号，不带 `[i]` 序号。

    vm ↔ native 的对拍比的是**值文本**：机器码端只有 `print` 式输出，没带
    类型标签，把宿主基线格式（序号/引号）强加上去只会多出假差异，反而遮住
    真正的值不一致。因此比前先归一到同一口径。"""
    def plain(v: object) -> str:
        if isinstance(v, bool):
            return "True" if v else "False"
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(plain(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{plain(k)}: {plain(x)}" for k, x in v.items()) + "}"
        return str(v)

    return "".join(plain(v) + "\n" for v in outputs)


# ============================================================
# 三个后端
# ============================================================

def run_vm(source: str) -> tuple[str, str, str]:
    """主链：mbc 字节码 VM。返回 (基线输出文本, stderr 文本, 宿主原生口径文本)。

    错误之前的输出同样入账（`run_checked`），否则错误用例的
    `输出("before")` 会被弄成空文本，基线就锁不住真实可观察行为。"""
    outputs, err = exec_api.run_checked(source, mode="vm")
    return (format_outputs(list(outputs)),
            "" if err is None else f"{type(err).__name__}: {err}\n",
            format_plain(list(outputs)))


def run_interp(source: str) -> tuple[str, str]:
    """遗留后端：树走式解释器（仅作对照，不再是默认执行路径）。

    取 `Interpreter.outputs`（与历史基线同一口径），而非宿主 stdout。"""
    from src.interp import Interpreter
    from src.parser import parse

    interp = Interpreter(debug=False)
    buf = io.StringIO()
    err = ""
    old_out = sys.stdout
    try:
        with contextlib.redirect_stdout(buf):
            interp.run(parse(source))
    except BaseException as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}\n"
    finally:
        sys.stdout = old_out
    return format_outputs(list(interp.outputs)), err


def run_native(source: str, stem: str) -> tuple[str, str] | None:
    """原生后端：编成 exe 真跑。工具链不可用时返回 None（→ SKIPPED）。"""
    from src.mbc.native import NativeNotSupported, compile_to_exe

    exe = Path(tempfile.gettempdir()) / f"matha_golden_{stem}.exe"
    try:
        exe.write_bytes(compile_to_exe(source))
    except (NativeNotSupported, OSError) as e:
        print(f"    [SKIP] {stem}: 原生后端不可用（{type(e).__name__}: {e}）")
        return None
    except Exception as e:  # noqa: BLE001 — 语法/构造期失败：属用例本身问题，记为差异
        return "", f"{type(e).__name__}: {e}\n"
    proc = subprocess.run([str(exe)], capture_output=True, timeout=60)
    out = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    err = proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n")
    if proc.returncode != 0 and not err:
        err = f"exit={proc.returncode}\n"
    return out, err


def run_cli(stem: str, flags: list[str]) -> tuple[int, str, str]:  # noqa: E501
    """端到端口径：`matha run 用例`（真子进程、真入口）。

    验收标准 3 要求的是“matha run 跑通全部用例且执行路径为 mbc VM”，
    所以这里必须走 `src.matha_main` 而不是在进程内叫门面 —— 否则 CLI 里
    残留的转译/exec/自举路径会看不见。
    """
    cmd = [sys.executable, "-m", "src.matha_main"]
    for f in flags:
        cmd += ["--feature", f]
    cmd += ["run", str(CASES_DIR / f"{stem}.matha")]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, timeout=180)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
            proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n"))


def _apply_flags(flags: list[str]) -> None:
    features.clear_feature()
    for f in flags:
        features.set_feature(f, True)


# ============================================================
# 比对
# ============================================================

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _diff(a: str, b: str, fromfile: str, tofile: str) -> str:
    return "".join(difflib.unified_diff(
        a.splitlines(keepends=True), b.splitlines(keepends=True),
        fromfile=fromfile, tofile=tofile))


def _err_body(text: str) -> str:
    """去掉首行 `类名: ` 前缀，留下消息主体（跨后端比对用）。"""
    if not text:
        return ""
    first, nl, rest = text.partition("\n")
    _head, sep, tail = first.partition(": ")
    body = tail if sep else first
    return body + (nl + rest if nl else "")


def check_case(stem: str, source: str, flags: list[str], *, update: bool,
               native: bool, cli: bool) -> tuple[bool, bool, str, list[str], int]:
    """跑一个用例，返回 (硬失败, native 已知未实现, 报告文本, 备注, native 未对拍数)。

    最后一项让「工具链不可用所以没比」成为**可计数的显式跳过**，而不是
    被 `nv is None` 分支静静吃掉、混进通过率的分母里。"""
    lines: list[str] = []
    notes: list[str] = []
    ok = True
    gap = False
    nv_skip = 0

    _apply_flags(flags)
    vm_out, vm_err, vm_plain = run_vm(source)
    _apply_flags(flags)
    ip_out, ip_err = run_interp(source)
    nv: tuple[str, str] | None = None
    if native:
        # 领域插件符号只存在于宿主进程（懒加载 import），机器码 exe 里
        # 没有可寻的全局表。这类用例对 native 明确 SKIP，也不记作通过。
        if any(d in source for d in ("加载领域", "加载插件")):
            lines.append(f"[SKIP] {stem}：native 不承载领域插件符号")
            nv = None
            gap = True
        else:
            _apply_flags(flags)
            nv = run_native(source, stem)
            if nv is None:
                nv_skip += 1
    features.clear_feature()

    if update:
        _write(VM_DIR / f"{stem}.out", vm_out)
        _write(VM_DIR / f"{stem}.err", vm_err)
        # 新增用例：遗留基线不存在时一并建档，否则往后没人能发现
        # 解释器侧改了行为（既有 expected/ 文件一律不改写）。
        if not (INTERP_DIR / f"{stem}.out").exists():
            _write(INTERP_DIR / f"{stem}.out", ip_out)
            _write(INTERP_DIR / f"{stem}.err", ip_err)
        return True, gap, f"[UPDATED] {stem}", notes, nv_skip

    exp_out = _read(VM_DIR / f"{stem}.out")
    exp_err = _read(VM_DIR / f"{stem}.err")
    if vm_out != exp_out or vm_err != exp_err:
        ok = False
        lines.append(f"[FAIL] {stem}（主链 vm 偏离基线）")
        if vm_out != exp_out:
            lines.append(_diff(exp_out, vm_out, f"vm/{stem}.out", f"current/{stem}.out"))
        if vm_err != exp_err:
            lines.append(_diff(exp_err, vm_err, f"vm/{stem}.err", f"current/{stem}.err"))
    else:
        lines.append(f"[PASS] {stem}")

    # 跨后端 stdout：主链必须与遗留后端逐字节一致
    if vm_out != ip_out:
        ok = False
        lines.append(f"[FAIL] {stem}（vm ↔ interp stdout 不一致）")
        lines.append(_diff(ip_out, vm_out, f"interp/{stem}.out", f"vm/{stem}.out"))

    # 跨后端 stderr：消息主体必须一致；异常类名差异走白名单
    if _err_body(vm_err) != _err_body(ip_err):
        ok = False
        lines.append(f"[FAIL] {stem}（vm ↔ interp 错误消息主体不一致）")
        lines.append(_diff(ip_err, vm_err, "interp.stderr", "vm.stderr"))
    elif vm_err != ip_err:
        notes.append(f"{stem}: 异常类名不同 interp={ip_err.split(':')[0]} "
                     f"vm={vm_err.split(':')[0]}（消息主体一致）")

    # 既有 interp 基线同样必须保持逐字节不变（防止重构改动遗留后端行为）
    legacy_out = _read(INTERP_DIR / f"{stem}.out")
    legacy_err = _read(INTERP_DIR / f"{stem}.err")
    if legacy_out and (ip_out != legacy_out or ip_err != legacy_err):
        ok = False
        lines.append(f"[FAIL] {stem}（interp 偏离既有基线 expected/）")
        if ip_out != legacy_out:
            lines.append(_diff(legacy_out, ip_out, f"expected/{stem}.out", f"current/{stem}.out"))
        if ip_err != legacy_err:
            lines.append(_diff(legacy_err, ip_err, f"expected/{stem}.err", f"current/{stem}.err"))

    if nv is not None:
        if nv[0] != vm_plain:
            if stem in NATIVE_GAPS:
                lines.append(f"[KNOWN-GAP] {stem}：native 已知未实现 —— {NATIVE_GAPS[stem]}")
                gap = True
            else:
                ok = False
                lines.append(f"[FAIL] {stem}（vm ↔ native 值文本不一致）")
                lines.append(_diff(vm_plain, nv[0], "vm.plain", "native.stdout"))
        elif stem in NATIVE_GAPS:
            ok = False
            lines.append(f"[STALE] {stem}：native 已对拍一致，请从 manifest 的 "
                         f"native_known_gaps 删除该条")

    if cli:
        code, cout, cerr = run_cli(stem, flags)
        want_code = 1 if vm_err else 0
        if cout != vm_plain or code != want_code:
            ok = False
            lines.append(f"[FAIL] {stem}（`matha run` 端到端偏离主线：exit={code} 期望 {want_code}）")
            lines.append(_diff(vm_plain, cout, "vm.plain", "cli.stdout"))
            if cerr:
                lines.append(f"  stderr: {cerr.strip()[:200]}")
        else:
            lines.append(f"[PASS] {stem}（`matha run` 端到端）")

    return ok, gap, "\n".join(lines), notes, nv_skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matha 黄金测试（多后端逐字节比对）")
    parser.add_argument("--update", action="store_true", help="用当前 vm 输出重写主链基线")
    parser.add_argument("--native", action="store_true", help="追加原生 exe 对拍")
    parser.add_argument("--cli", action="store_true",
                        help="追加 `matha run` 子进程端到端对拍（验收标准 3）")
    parser.add_argument("--only", default="", help="只跑名字含该子串的用例")
    args = parser.parse_args(argv)

    stems = sorted(p.stem for p in CASES_DIR.glob("*.matha"))
    if args.only:
        stems = [s for s in stems if args.only in s]
    if not stems:
        print("未找到用例", file=sys.stderr)
        return 1

    passed = 0
    failed = 0
    gaps = 0
    nv_skips = 0
    notes: list[str] = []
    for stem in stems:
        source = (CASES_DIR / f"{stem}.matha").read_text(encoding="utf-8")
        entry = MANIFEST["cases"].get(stem, {})
        flags = entry.get("features", [])
        for rel in entry.get("preload", []):
            source = (ROOT / rel).read_text(encoding="utf-8") + "\n" + source
        ok, gap, text, n, sk = check_case(stem, source, flags,
                                          update=args.update, native=args.native,
                                          cli=args.cli)
        print(text)
        notes.extend(n)
        nv_skips += sk
        if not ok:
            failed += 1
        elif gap:
            gaps += 1
        else:
            passed += 1

    total = len(stems)
    if args.update:
        print(f"已重写 {total} 例主链基线 → {VM_DIR}")
        return 0
    tail = f"，native 已知未实现 {gaps} 例" if gaps else ""
    tail += f"，native 未对拍 {nv_skips} 例" if nv_skips else ""
    backends = "+".join(["vm"] + (["native"] if args.native else [])
                        + (["cli"] if args.cli else []))
    print(f"\n结果：{passed}/{total} 通过，{failed} 失败"
          f"（后端：{backends} ↔ interp 对照{tail}）")
    if nv_skips:
        print(f"注意：native 未对拍 {nv_skips} 例（工具链不可用）—— "
              f"这些例只验证了 vm 侧基线，不代表机器码路径通过。")
    if notes:
        print("跨后端 stderr 类名差异（如实记录，未静默抹平）：")
        for n in notes:
            print(f"  - {n}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
