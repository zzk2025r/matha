#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在宿主上编译并运行 FE310 UART 寄存器级模拟测试（P5 第 2 步的行为验证）。

用宿主 gcc（非交叉）把【真实的 hal/drivers/uart.c】与 tools/sim 下的模拟后端、
测试驱动一起编译链接，再运行。证明分频校准 + 收发逻辑正确，无需真 FE310 硬件，
也不依赖交叉 QEMU。诚实口径：这是寄存器级行为验证，不等于上板实测。

用法：  python tools/run_uart_sim.py     （或 make sim）
退出码：0=通过；1=编译/断言失败；2=未找到宿主编译器。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent        # baremetal/
SIM = ROOT / "tools" / "sim"
OUTDIR = ROOT / "build"


def main() -> int:
    cc = os.environ.get("HOST_CC") or shutil.which("gcc")
    if not cc:
        print("[sim] 未找到宿主 gcc：无法运行 UART 模拟（可设环境变量 HOST_CC 指定）。")
        return 2

    OUTDIR.mkdir(exist_ok=True)
    exe = OUTDIR / ("uart_sim.exe" if os.name == "nt" else "uart_sim")
    srcs = [
        str(ROOT / "hal" / "drivers" / "uart.c"),
        str(SIM / "hal_mmio_sim.c"),
        str(SIM / "uart_sim_main.c"),
    ]
    inc = str(ROOT / "include")
    cmd = [cc, "-std=c11", "-DHAL_MMIO_SIM", "-I", inc,
           "-Wall", "-Wextra", "-o", str(exe), *srcs]

    print("[sim] 链接真实 uart.c + 模拟后端：", os.path.basename(cc),
          " ".join(Path(s).name for s in srcs))
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        sys.stdout.write(build.stdout)
        sys.stderr.write(build.stderr)
        print("[sim] 编译失败。")
        return 1

    run = subprocess.run([str(exe)], capture_output=True, text=True)
    sys.stdout.write(run.stdout)
    if run.stderr:
        sys.stderr.write(run.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
