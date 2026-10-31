#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主编译并运行「可回收分配器」行为模拟（P5 第 3 步：接管内存）。

用宿主 gcc 把【真实 hal/mem/allocator.c】（-DHAL_MEM_SIM_HEAP）与测试驱动一起
编译链接并运行，证明 first-fit / 8 字节对齐 / 释放复用 / 相邻合并 / 超大返回 NULL。
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
        print("[sim:mem] 未找到宿主 gcc（可设 HOST_CC）。")
        return 2
    OUTDIR.mkdir(exist_ok=True)
    exe = OUTDIR / ("mem_sim.exe" if os.name == "nt" else "mem_sim")
    srcs = [str(ROOT / "hal" / "mem" / "allocator.c"), str(SIM / "allocator_sim_main.c")]
    cmd = [cc, "-std=c11", "-DHAL_MEM_SIM_HEAP", "-I", str(ROOT / "include"),
           "-Wall", "-Wextra", "-o", str(exe), *srcs]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        sys.stdout.write(build.stdout)
        sys.stderr.write(build.stderr)
        print("[sim:mem] 编译失败。")
        return 1
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    sys.stdout.write(run.stdout)
    if run.stderr:
        sys.stderr.write(run.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
