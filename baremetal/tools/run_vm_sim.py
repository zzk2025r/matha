#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主编译并运行「栈式引擎」行为模拟（极简契约优先）。

用宿主 gcc 把【真实 hal/vm/stack_vm.c】（经 -DHAL_VM_SIM 宏缝）与测试驱动一起
编译链接并运行，证明 17 条 op 正常语义（含 LOAD/STORE mem 往返）、CALL/RET 平衡、
分支全路径，以及全部
显式拒绝路径（栈溢出/栈空/除零/溢出对/代码越界/非法 op/环满）与看门狗 cap。
诚实口径：行为级验证，不等于 RV32 固件实跑（固件侧由 build.ps1 + main.c 的
vm_selfcheck 承担）。退出码 0=通过，1=失败，2=无编译器。
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
        print("[sim:vm] 未找到宿主 gcc（可设 HOST_CC）。")
        return 2
    OUTDIR.mkdir(exist_ok=True)
    exe = OUTDIR / ("vm_sim.exe" if os.name == "nt" else "vm_sim")
    srcs = [str(ROOT / "hal" / "vm" / "stack_vm.c"), str(SIM / "stack_vm_sim_main.c")]
    cmd = [cc, "-std=c11", "-DHAL_VM_SIM", "-fwrapv", "-I", str(ROOT / "include"),
           "-Wall", "-Wextra", "-o", str(exe), *srcs]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        sys.stdout.write(build.stdout)
        sys.stderr.write(build.stderr)
        print("[sim:vm] 编译失败。")
        return 1
    try:
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("[sim:vm] 运行超时（30s）：疑似用例挂死，请检查 panic 守护。")
        return 1
    sys.stdout.write(run.stdout)
    if run.stderr:
        sys.stderr.write(run.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
