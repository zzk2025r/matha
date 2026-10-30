#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 stock QEMU (riscv32 -machine virt) 上实跑「中断接管」常驻样例。

流程：用 RISC-V 交叉工具链把同目录 virt_start.S + uart.c + main.c 按 virt.ld 链成
ELF，再交给 qemu-system-riscv32 -machine virt -cpu rv32 跑固定秒数，抓串口输出，
断言这几件事都成立（证明真 RV32 指令把中断→UART 打印路径走通）：
  1. mie 读回含 MTIE（bit7）——csrs 用符号名确实置上了；
  2. 轮询阶段看到 MTIP?Y——CLINT mtimecmp 会把 mip.MTIP 拉起；
  3. 开全局 MIE 后 ISR 持续打印 "Hello RISC-V! tick=N"——mtvec→trap→mcause 分派→
     调 uart 版 C ISR→重装 mtimecmp→mret 全通。

诚实口径：这是 board-matched 变体（UART 换 ns16550、内存换 virt RAM），**非 FE310
产物**；证明的是中断路径可被真指令集在 QEMU 上执行，不等于在真 FE310 板实测。

可配置：交叉编译器与 QEMU 路径都能给；优先级 = CLI 参数 > 环境变量 > 自动探测。
  - CLI:  --cc <riscv-none-elf-gcc>   --qemu <qemu-system-riscv32>   --timeout <sec>
  - 环境: RISCV_CC / QEMU
退出码：0=通过，1=失败（编译/断言不过），2=SKIP（缺工具链或缺 QEMU，如实跳过不算失败）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # .../tools/qemu_virt_demo
ROOT = HERE.parent.parent                          # .../baremetal
OUTDIR = ROOT / "build" / "qemu_virt_demo"         # gitignored 产物区

MARCH, MABI = "rv32imac_zicsr", "ilp32"           # 与 Makefile/build.ps1 一致

# 自动探测用的候选名与常见安装根。
CC_NAMES = ["riscv-none-elf-gcc", "riscv64-unknown-elf-gcc", "riscv32-unknown-elf-gcc"]
QEMU_NAME = "qemu-system-riscv32"


def find_cc(explicit: str | None) -> str | None:
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        w = shutil.which(explicit)
        return w
    for name in CC_NAMES:
        w = shutil.which(name)
        if w:
            return w
    # 扫常见安装目录里的 bin/*gcc
    for root in ("C:\\Program Files", "C:\\Program Files (x86)", "D:\\", "C:\\"):
        if not os.path.isdir(root):
            continue
        for name in CC_NAMES:
            for exe in (name + ".exe", name):
                for hit in Path(root).rglob(exe):
                    if "\\bin\\" in str(hit).lower() or "/bin/" in str(hit):
                        return str(hit)
    return None


def find_qemu(explicit: str | None) -> str | None:
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        w = shutil.which(explicit)
        return w
    w = shutil.which(QEMU_NAME)
    if w:
        return w
    w64 = shutil.which("qemu-system-riscv64")  # 有的发行只装 64，含 rv32 目标
    if w64:
        return w64
    cand = Path(r"C:\\Program Files\\qemu") / (QEMU_NAME + ".exe")
    if cand.is_file():
        return str(cand)
    for root in ("C:\\Program Files", "C:\\Program Files (x86)", "D:\\", "C:\\"):
        if not os.path.isdir(root):
            continue
        for hit in Path(root).rglob(QEMU_NAME + ".exe"):
            return str(hit)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="QEMU virt 中断接管样例（可配置工具链/QEMU）")
    ap.add_argument("--cc", default=None, help="RISC-V 交叉 gcc（或设环境变量 RISCV_CC）")
    ap.add_argument("--qemu", default=None, help="qemu-system-riscv32（或设环境变量 QEMU）")
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("QEMU_DEMO_TIMEOUT", 5)),
                    help="QEMU 运行秒数（默认 5，之后超时终止属预期）")
    args = ap.parse_args()

    cc = find_cc(args.cc or os.environ.get("RISCV_CC"))
    qemu = find_qemu(args.qemu or os.environ.get("QEMU"))

    if not cc:
        print("[qemu_virt_demo] SKIP：未找到 RISC-V 交叉工具链。"
              "请装 xPack riscv-none-elf-gcc，或用 --cc / 环境变量 RISCV_CC 指定。")
        return 2
    if not qemu:
        print("[qemu_virt_demo] SKIP：未找到 qemu-system-riscv32。"
              "请安装 QEMU，或用 --qemu / 环境变量 QEMU 指定。")
        return 2

    OUTDIR.mkdir(parents=True, exist_ok=True)
    elf = OUTDIR / ("virt_demo.exe" if os.name == "nt" else "virt_demo")

    print(f"[qemu_virt_demo] cc   = {cc}")
    print(f"[qemu_virt_demo] qemu = {qemu}")

    # ── 编译链接 ──
    build = subprocess.run(
        [cc, f"-march={MARCH}", f"-mabi={MABI}", "-Os", "-ffreestanding", "-nostdlib",
         "-Wall", "-Wextra", "-I", str(HERE), "-T", str(HERE / "virt.ld"),
         "-o", str(elf),
         str(HERE / "virt_start.S"), str(HERE / "uart.c"), str(HERE / "main.c")],
        capture_output=True, text=True)
    if build.stdout:
        sys.stdout.write(build.stdout)
    if build.returncode != 0:
        sys.stderr.write(build.stderr or "")
        print("[qemu_virt_demo] 编译失败。")
        return 1
    print("[qemu_virt_demo] 编译链接 OK -> %s" % elf)

    # ── QEMU 运行（-nographic 把 UART 重定向到 stdio；到点超时终止属预期）──
    serial = ""
    early_rc = None
    try:
        run = subprocess.run(
            [qemu, "-machine", "virt", "-cpu", "rv32", "-nographic",
             "-bios", "none", "-kernel", str(elf)],
            capture_output=True, text=True, timeout=args.timeout)
        serial = run.stdout or ""
        early_rc = run.returncode
        print("[qemu_virt_demo] QEMU 提前退出 rc=%s（非预期：固件应持续被定时器打断）" % early_rc)
    except subprocess.TimeoutExpired as e:
        raw = e.stdout
        serial = raw.decode(errors="replace") if isinstance(raw, bytes) else (raw or "")
        print("[qemu_virt_demo] QEMU 运行 %.1fs 后被超时终止（预期：定时器持续触发）" % args.timeout)

    print("----- 串口输出 -----")
    print(serial[:2000])
    print("----- (结束) -----")

    # ── 断言：三个信号齐备才算中断接管在真指令集上跑通 ──
    fails = []
    if "MTIP?N" in serial:
        fails.append("MTIP 未拉起（CLINT 定时器没触发）")
    if "MTIP?Y" not in serial:
        fails.append("未见 MTIP?Y（轮询阶段定时器 pending 断言缺失）")
    if "tick" not in serial:
        fails.append("未见 ISR 打印 tick（中断投递/mret 路径未跑通）")
    if "Hello RISC-V!" not in serial:
        fails.append("未见 ISR 打印 'Hello RISC-V!'（uart 驱动 + 中断打印集成未跑通）")
    # mie 读回应含 MTIE bit7（低 8 位含 0x80）
    mie_ok = any(line.startswith("mie=") and (int(line[4:12], 16) & 0x80)
                 for line in serial.splitlines() if line.startswith("mie=") and len(line) >= 12)
    if not mie_ok:
        fails.append("mie 读回未见 MTIE(bit7)")

    if fails:
        for f in fails:
            print("[qemu_virt_demo] FAIL：" + f)
        return 1
    print("[qemu_virt_demo] PASS：uart 驱动 + mtvec→trap→mcause 分派→C ISR(打印 Hello RISC-V!+tick)→重装→mret 在 QEMU RV32 上跑通。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
