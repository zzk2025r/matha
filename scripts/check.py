#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 统一检查入口（阶段 5 第 2 项：`make check`）。

把散落的门禁串成一条链，**对外只产出一个通过率数字**：

  1. `tests/`        —— 单元测试（不含下面单列的两项门禁，避免重复计数）
  2. `kernel_purity` —— 内核 import 白名单 + 核心目录无子进程/线程（验收标准 1/2）
  3. `ast_vm_gap`    —— AST × VM 覆盖矩阵门禁（阶段 2 前置件）
  4. `golden`        —— 黄金用例 vm ↔ interp 基线逐字节比对
  5. `native_parity` —— 黄金用例 vm ↔ `mbc.native` 真 exe 对拍（唯一真实机器码路径）
  6. `dep_audit`     —— 依赖图审计（内核 import 白名单的取证件，产出 docs/DEP_BASELINE.md）

口径纪律（禁止静默假成功）：
  - 子进程非零退出、解析不到汇总行、命令根本起跑失败 —— 一律记 **失败**，不记跳过；
  - 工具链不可用导致的 native 未对拍 —— 记 **跳过**，从分母剔除但显式打印台数，
    并在最后打印 `SKIP` 摘要行；绝不把「没跑」算成「跑通」。
  - 通过率 = 通过数 / (通过数 + 失败数)，跳过不计入分母。

用法：
  python scripts/check.py                # 全量（含 native 对拍）
  python scripts/check.py --skip-native  # 快速口径（本机无 nasm/link 时用）
  python scripts/check.py --only golden  # 只跑名字含该子串的项
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

_NUM = lambda pat, text: (int(m.group(1)) if (m := re.search(pat, text)) else None)  # noqa: E731


@dataclass
class Item:
    """一个检查项：命令行 + 如何从输出里取出通过/失败/跳过计数。"""

    name: str
    argv: list[str]
    parser: str = "pytest"                       # pytest | golden | audit
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    detail: str = ""
    notes: list[str] = field(default_factory=list)
    seconds: float = 0.0
    ran: bool = True

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def ok(self) -> bool:
        return self.ran and self.failed == 0


def _run(item: Item) -> Item:
    t0 = time.time()
    try:
        proc = subprocess.run(item.argv, cwd=str(ROOT), capture_output=True,
                              timeout=3600, text=True, encoding="utf-8",
                              errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:      # 起跑失败 = 失败，不是跳过
        item.ran = False
        item.failed = 1
        item.detail = f"无法执行：{type(e).__name__}: {e}"
        item.seconds = time.time() - t0
        return item
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    item.seconds = time.time() - t0
    tail = [ln for ln in out.splitlines() if ln.strip()][-12:]

    if item.parser == "pytest":
        p = _NUM(r"(\d+) passed", out)
        f = _NUM(r"(\d+) (?:failed|error)", out)
        s = _NUM(r"(\d+) skipped", out)
        x = _NUM(r"(\d+) xfailed", out) or 0
        if p is None and f is None:
            item.ran = False
            item.failed = 1
            item.detail = "解析不到 pytest 汇总行（收集错误/崩溃？）"
        else:
            item.passed = (p or 0) + x
            item.failed = (f or 0) + (0 if proc.returncode in (0, 1) else 1)
            item.skipped = s or 0
            if proc.returncode not in (0, 1) and item.failed == 0:
                item.failed = 1
                item.notes.append(f"pytest 退出码 {proc.returncode}")
    elif item.parser == "golden":
        m = re.search(r"结果：(\d+)/(\d+) 通过，(\d+) 失败", out)
        sk = _NUM(r"native 未对拍 (\d+) 例", out)
        gp = _NUM(r"native 已知未实现 (\d+) 例", out)
        if not m:
            item.ran = False
            item.failed = 1
            item.detail = "解析不到黄金测试汇总行"
        else:
            item.passed = int(m.group(1))
            item.failed = int(m.group(3))
            item.skipped = sk or 0
            # 已知未实现项既不算通过也不算失败：显式作为「未覆盖」列出
            if gp:
                item.notes.append(f"native 已知未实现 {gp} 例（见 manifest.native_known_gaps）")
            item.skipped += gp or 0
    else:                                                     # dep_audit
        bad = _NUM(r"违规\s+(\d+)\s*条", out)
        oob = _NUM(r"插件越界\s+(\d+)\s*条", out)
        if bad is None:
            item.ran = False
            item.failed = 1
            item.detail = "解析不到 dep_audit 汇总行"
        else:
            item.failed = bad + (oob or 0) + (0 if proc.returncode == 0 else 1)
            item.passed = 1 if item.failed == 0 else 0
            item.detail = f"违规 {bad} 条 / 插件越界 {oob or 0} 条"

    if item.failed and not item.detail:
        item.detail = " | ".join(tail[-2:])[:200]
    return item


def build_items(skip_native: bool) -> list[Item]:
    pytest_base = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line"]
    items = [
        Item("tests",
             pytest_base + ["tests",
                            "--ignore=tests/test_kernel_purity.py",
                            "--ignore=tests/test_ast_vm_gap.py"],
             "pytest"),
        Item("kernel_purity", pytest_base + ["tests/test_kernel_purity.py"], "pytest"),
        Item("ast_vm_gap", pytest_base + ["tests/test_ast_vm_gap.py"], "pytest"),
        Item("golden", [PY, "golden_tests/run_golden_tests.py"], "golden"),
        Item("dep_audit", [PY, "scripts/dep_audit.py"], "audit"),
    ]
    if not skip_native:
        items.append(
            Item("native_parity",
                 [PY, "golden_tests/run_golden_tests.py", "--native"], "golden"))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Matha 统一检查（一个通过率数字）")
    ap.add_argument("--skip-native", action="store_true",
                    help="不跑 vm↔native 机器码对拍（本机无 nasm/link 时用）")
    ap.add_argument("--only", default="", help="只跑名字含该子串的项")
    args = ap.parse_args(argv)

    items = build_items(args.skip_native)
    if args.only:
        items = [i for i in items if args.only in i.name]
    if not items:
        print("没有匹配的检查项", file=sys.stderr)
        return 2

    print("=== Matha 统一检查 make check ===")
    for it in items:
        print(f"\n--- {it.name} ---")
        print("    " + " ".join(Path(a).name if a == PY else a for a in it.argv))
        _run(it)
        state = "PASS" if it.ok else ("SKIP" if not it.ran else "FAIL")
        print(f"    [{state}] 通过 {it.passed} / 失败 {it.failed} / 跳过 {it.skipped}"
              f"  ({it.seconds:.1f}s)")
        for n in it.notes:
            print(f"    注：{n}")
        if it.detail:
            print(f"    明细：{it.detail}")

    passed = sum(i.passed for i in items)
    failed = sum(i.failed for i in items)
    skipped = sum(i.skipped for i in items)
    total = passed + failed
    rate = (passed / total * 100) if total else 0.0

    print("\n" + "═" * 56)
    if failed:
        print("失败项：" + ", ".join(i.name for i in items if i.failed))
    if skipped:
        print(f"SKIP：未覆盖 {skipped} 项（工具链不可用 / 已知未实现），"
              f"未计入通过率，不代表通过")
    print(f"通过率：{rate:.2f}%（通过 {passed} / 计入 {total}，失败 {failed}）")
    print("═" * 56)
    return 0 if failed == 0 and total else 1


if __name__ == "__main__":
    raise SystemExit(main())
