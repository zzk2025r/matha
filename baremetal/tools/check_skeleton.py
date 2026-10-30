#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""baremetal HAL 骨架校验器（P5 第 1 步的「结构门禁 + 宿主语法门禁」）。

分两层，互不依赖交叉工具链：
  1. 结构校验（永远执行，缺文件即失败）：目录树、头文件契约、link.ld
     段/符号、crt0.S 对符号的引用、uart/mem/irq API 是否齐备。
  2. 语法校验（有宿主 gcc 才跑，无则如实 SKIP，不算失败）：对每个 .c 做
     `gcc -std=c11 -ffreestanding -Wall -Wextra -fsyntax-only -Iinclude`，
     证明 arch→mmio→uart/mem/irq 这套 freestanding 地基能被 C 编译器接受。

诚实口径：本校验器只证明「骨架可编译 / 契约自洽」，不代表已在实板或 QEMU 上
跑通——那分属第 2、3 步。它不在 scripts/check.py 的六项门禁作用域内（不位于
tests/），需显式 `python tools/check_skeleton.py` 或 `make check` 触发。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # baremetal/

# ── 1. 结构清单 ────────────────────────────────────────────────
REQUIRED_FILES = [
    "link.ld", "Makefile", "main.c",
    "include/hal/hal.h", "include/hal/types.h", "include/hal/mmio.h",
    "include/hal/arch.h", "include/hal/boot.h", "include/hal/uart.h",
    "include/hal/mem.h", "include/hal/irq.h",
    "boot/crt0.S", "boot/vector.S",
    "hal/drivers/uart.c", "hal/mem/allocator.c", "hal/trap/trap.c",
]

C_SOURCES = ["main.c", "hal/drivers/uart.c", "hal/mem/allocator.c", "hal/trap/trap.c"]

# link.ld 必须给出的段与符号契约。
LD_MUST_HAVE = ["FLASH", "RAM", ".text", ".data", ".bss",
                "_estack", "_sidata", "_sdata", "_edata", "_sbss", "_ebss",
                "_heap_start", "_heap_end"]

# crt0.S 必须消费的符号 + 入口。
CRT0_MUST_HAVE = ["_start", "_estack", "_sidata", "_sdata", "_ebss", "main"]

# 头文件应声明的 API（按分层契约存在性）。
API_DECLARATIONS = {
    "include/hal/uart.h": ["uart_init", "uart_putc", "uart_puts"],
    "include/hal/mem.h": ["hal_mem_init", "hal_malloc", "hal_free"],
    "include/hal/irq.h": ["hal_trap_handler", "hal_irq_enable", "hal_irq_disable"],
    "include/hal/arch.h": ["FE310_UART0_BASE", "FE310_CLINT_BASE", "FE310_PLIC_BASE"],
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_structure(fail: list[str]) -> None:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            fail.append(f"缺文件：{rel}")

    if (ROOT / "link.ld").exists():
        ld = _read("link.ld")
        for tok in LD_MUST_HAVE:
            if tok not in ld:
                fail.append(f"link.ld 缺段/符号：{tok}")

    if (ROOT / "boot" / "crt0.S").exists():
        crt = _read("boot/crt0.S")
        for tok in CRT0_MUST_HAVE:
            if tok not in crt:
                fail.append(f"crt0.S 缺引用：{tok}")

    for hdr, names in API_DECLARATIONS.items():
        if (ROOT / hdr).exists():
            text = _read(hdr)
            for nm in names:
                if nm not in text:
                    fail.append(f"{hdr} 缺 API 声明：{nm}")

    # 只增不改守卫：骨架不得把 libc/OS 依赖引进 freestanding C。
    # 用词边界匹配裸 libc 调用，避免把 HAL 自身的 hal_malloc/hal_free 误判。
    libc_call = re.compile(r"(?<![A-Za-z0-9_])(?:malloc|printf|fprintf|puts|exit)\s*\(")
    for rel in C_SOURCES:
        if (ROOT / rel).exists():
            text = _read(rel)
            for banned in ("<stdio.h>", "<stdlib.h>", "<unistd.h>"):
                if banned in text:
                    fail.append(f"{rel} 混入宿主/libc 头：{banned}")
            if libc_call.search(text):
                fail.append(f"{rel} 混入宿主/libc 调用：{libc_call.search(text).group(0)}")


def check_syntax(fail: list[str], notes: list[str]) -> None:
    cc = shutil.which(os.environ.get("HOST_CC", "gcc"))
    if not cc:
        notes.append("未检测到宿主 gcc：SKIP 语法校验（结构校验仍已执行）")
        return
    inc = str(ROOT / "include")
    for rel in C_SOURCES:
        path = ROOT / rel
        if not path.exists():
            continue  # 结构校验已就此报错
        cmd = [cc, "-std=c11", "-ffreestanding", "-Wall", "-Wextra",
               "-fsyntax-only", "-I", inc, str(path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()
            fail.append(f"语法校验失败 {rel}：" + " | ".join(tail[-4:]))
        else:
            notes.append(f"语法校验通过 {rel}")


def main() -> int:
    fail: list[str] = []
    notes: list[str] = []
    check_structure(fail)
    check_syntax(fail, notes)

    print("=== baremetal HAL 骨架校验 ===")
    for n in notes:
        print("  [ok  ] " + n)
    if fail:
        for f in fail:
            print("  [FAIL] " + f)
        print(f"结果：结构/语法校验 失败 {len(fail)} 项")
        return 1
    n_entries = sum(1 for _ in ROOT.rglob("*"))
    print(f"结果：骨架校验通过（{n_entries} 个条目，"
          f"{len(C_SOURCES)} 个 C 源）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
