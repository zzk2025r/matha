#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主编译并运行「中断接管」寄存器级模拟（P5 第 3 步：接管中断）。

用宿主 gcc 把【真实 hal/trap/trap.c】（-DHAL_MMIO_SIM -DHAL_CSR_SIM）与平台后端、
测试驱动一起编译链接并运行，验证 mtvec/mie/mstatus 配置、定时器重装 mtimecmp、
PLIC claim→路由→complete、未知源/软件中断不崩溃。vector.S 是纯汇编不在此执行。
诚实口径：行为级验证，不等于上板实测。退出码 0=通过，1=失败，2=无编译器。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "tools" / "sim"
OUTDIR = ROOT / "build"


def main() -> int:
    cc = os.environ.get("HOST_CC") or shutil.which("gcc")
    if not cc:
        print("[sim:trap] 未找到宿主 gcc（可设 HOST_CC）。")
        return 2
    OUTDIR.mkdir(exist_ok=True)
    exe = OUTDIR / ("trap_sim.exe" if os.name == "nt" else "trap_sim")
    srcs = [
        str(ROOT / "hal" / "trap" / "trap.c"),
        str(SIM / "hal_platform_sim.c"),
        str(SIM / "trap_sim_main.c"),
    ]
    cmd = [cc, "-std=c11", "-DHAL_MMIO_SIM", "-DHAL_CSR_SIM",
           "-I", str(ROOT / "include"), "-Wall", "-Wextra", "-o", str(exe), *srcs]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        sys.stdout.write(build.stdout)
        sys.stderr.write(build.stderr)
        print("[sim:trap] 编译失败。")
        return 1
    try:
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("[sim:trap] 运行超时（可能陷入死循环）。")
        return 1
    sys.stdout.write(run.stdout)
    if run.stderr:
        sys.stderr.write(run.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
