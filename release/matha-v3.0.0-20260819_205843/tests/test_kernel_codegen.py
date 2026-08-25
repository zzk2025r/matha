# -*- coding: utf-8 -*-
"""Kernel Codegen 测试用例。

覆盖：
  1. KernelGenerator 基本生成（boot.asm + kernel.asm + Makefile）
  2. 规格解析（系统调用列表、页大小、栈大小）
  3. 汇编代码正确性（包含必要指令）
  4. kernel_math 公式验证
"""
import sys
import os
sys.path.insert(0, r"D:\trae")

from src.codegen.kernel import KernelGenerator, KernelSpec, generate_kernel
from src.codegen.base import parse_app_spec, CodegenResult
from src.domains.kernel_math import (
    syscall_num, syscall_entry_size, syscall_latency_ns,
    pcb_size, pcb_alloc_cost, pcb_context_switch_cycles,
    page_table_entries, page_table_overhead_bytes,
    linear_address, virtual_to_physical,
    interrupt_latency_us, exception_vector,
    context_switch_overhead_us, throughput_max_tasks,
    kernel_mem_layout, total_kernel_mem,
)

PASS, FAIL = [], []


def test(name, ok, detail=""):
    if ok:
        PASS.append(name)
        print(f"  ✓ {name}{detail}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}: {detail}")


# ============================================================
# 1. KernelGenerator 基本生成
# ============================================================
print("\n【1. KernelGenerator 基本生成】")


def check_gen(name, spec, expected_files):
    try:
        app = parse_app_spec(spec)
        out_dir = f"D:/trae/_test_output/kernel_{name.replace(' ', '_')}"
        os.makedirs(out_dir, exist_ok=True)
        gen = KernelGenerator(app, out_dir)
        result = gen.generate()

        ok = result.成功 and len(result.文件) == len(expected_files)
        test(name, ok, f" (files={len(result.文件) if result.成功 else 0})")

        if result.成功:
            for ef in expected_files:
                path = os.path.join(out_dir, ef)
                exists = os.path.exists(path)
                size = os.path.getsize(path) if exists else 0
                test(f"  → {ef}", exists and size > 0, f" ({size}B)")
    except Exception as e:
        test(name, False, f": {type(e).__name__}: {e}")


check_gen("basic",
          ["内核", "BasicOS", "BasicOS", [
              ["系统名", "BasicOS", [], []],
              ["内核版本", "0.1", [], []],
          ]],
          ["boot.asm", "kernel.asm", "Makefile"])

check_gen("with_syscalls",
          ["内核", "SysOS", "SysOS", [
              ["系统名", "SysOS", [], []],
              ["系统调用", "write,read,exit,fork,mmap", [], []],
              ["页大小", "4096", [], []],
          ]],
          ["boot.asm", "kernel.asm", "Makefile"])

check_gen("full_spec",
          ["内核", "FullOS", "FullOS", [
              ["系统名", "FullOS", [], []],
              ["内核版本", "0.5", [], []],
              ["目标架构", "x86", [], []],
              ["系统调用", "write,read,exit,fork,mmap,munmap,brk", [], []],
              ["页大小", "4096", [], []],
              ["栈大小", "8192", [], []],
              ["最大任务数", "128", [], []],
          ]],
          ["boot.asm", "kernel.asm", "Makefile"])


# ============================================================
# 2. 汇编代码正确性
# ============================================================
print("\n【2. 汇编代码正确性】")


def check_asm_content(name, spec, checks):
    try:
        app = parse_app_spec(spec)
        out_dir = f"D:/trae/_test_output/check_{name}"
        os.makedirs(out_dir, exist_ok=True)
        gen = KernelGenerator(app, out_dir)
        result = gen.generate()

        if not result.成功:
            test(name, False, f"生成失败: {result.错误}")
            return

        all_ok = True
        for file_name, content_check in checks:
            path = os.path.join(out_dir, file_name)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for label, check_fn in content_check:
                ok = check_fn(content)
                if not ok:
                    all_ok = False
                    print(f"    ✗ {file_name}: {label}")
        test(name, all_ok)
    except Exception as e:
        test(name, False, f": {type(e).__name__}: {e}")


check_asm_content("boot_instructions",
                  ["内核", "TestOS", "TestOS", [["系统名", "TestOS", [], []]]],
                  [
                      ("boot.asm", [
                          ("cli", lambda c: "cli" in c),
                          ("lgdt", lambda c: "lgdt" in c),
                          ("mov cr0", lambda c: "mov cr0" in c),
                          ("jmp 0x08", lambda c: "jmp 0x08" in c),
                          ("0xAA55", lambda c: "0xAA55" in c),
                          ("gdt_start", lambda c: "gdt_start" in c),
                          ("gdt_descriptor", lambda c: "gdt_descriptor" in c),
                      ]),
                  ])

check_asm_content("kernel_instructions",
                  ["内核", "TestOS", "TestOS", [
                      ["系统名", "TestOS", [], []],
                      ["系统调用", "write,read,exit", [], []],
                  ]],
                  [
                      ("kernel.asm", [
                          ("kernel_main", lambda c: "kernel_main" in c),
                          ("syscall_handler", lambda c: "syscall_handler" in c),
                          ("init_idt_inline", lambda c: "init_idt_inline" in c),
                          ("irq0_handler", lambda c: "irq0_handler" in c),
                          ("irq1_handler", lambda c: "irq1_handler" in c),
                          ("syscall_table", lambda c: "syscall_table" in c),
                          ("idt_start", lambda c: "idt_start" in c),
                          ("task_table", lambda c: "task_table" in c),
                      ]),
                      ("Makefile", [
                          ("nasm", lambda c: "nasm" in c),
                          ("qemu", lambda c: "qemu" in c),
                          ("kernel.bin", lambda c: "kernel.bin" in c),
                      ]),
                  ])


# ============================================================
# 3. kernel_math 公式验证
# ============================================================
print("\n【3. kernel_math 公式验证】")


def check_math(name, result, expected, tolerance=0.0):
    if isinstance(expected, float) and isinstance(result, float):
        ok = abs(result - expected) < tolerance
    else:
        ok = result == expected
    test(name, ok, f" (got={result}, expected={expected})")


# syscall
check_math("syscall_num(write)", syscall_num("write"), 4)
check_math("syscall_num(fork)", syscall_num("fork"), 2)
check_math("syscall_num(read)", syscall_num("read"), 3)
check_math("syscall_num(exit)", syscall_num("exit"), 1)
check_math("syscall_num(notfound)", syscall_num("notfound"), -1)
check_math("syscall_entry_size(5)", syscall_entry_size(5), 40)
check_math("syscall_latency_user", syscall_latency_ns(kernel_mode=False), 300.0, 1.0)
check_math("syscall_latency_kernel", syscall_latency_ns(kernel_mode=True), 50.0, 1.0)

# PCB
check_math("pcb_size(18,4096)", pcb_size(18, 4096), 80 + 18 * 4 + 4096)
check_math("pcb_size(8,2048)", pcb_size(8, 2048), 80 + 8 * 4 + 2048)
check_math("pcb_alloc(64,500)", pcb_alloc_cost(64, 500), 32000)
check_math("pcb_switch_cycles(18)", pcb_context_switch_cycles(18), 18 * 2 + 5000 + 18 * 2)

# Memory
check_math("pt_entries(4096, 4MB)", page_table_entries(4096, 4 * 1024 * 1024), 2049)
check_math("pt_entries(4096, 64MB)", page_table_entries(4096, 64 * 1024 * 1024), 32769)
check_math("pt_overhead(4096, 4MB)", page_table_overhead_bytes(4096, 4 * 1024 * 1024), 8192)
check_math("linear_addr", linear_address(100, 64, 4096), 409600 + 64)
check_math("virt分解", virtual_to_physical(0x1234, 4096), (0x1234 // 4096, 0x1234 % 4096))

# Exception
check_math("exception_14", exception_vector(14), "Page Fault (#PF)")
check_math("exception_0", exception_vector(0), "Divide-by-zero (#DE)")
check_math("exception_128", exception_vector(128), "System Call (int 0x80)")

# Interrupt
check_math("irq0_latency", interrupt_latency_us(0, True), 2.0, 0.1)
check_math("irq8_latency", interrupt_latency_us(8, False), 6.0, 0.1)

# Context switch
cs_us = context_switch_overhead_us(3000, 18)
check_math("ctx_switch_us", cs_us, 29.0, 1.0)

# Kernel memory layout
layout = kernel_mem_layout()
check_math("text_addr", layout["text"][0], 0x100000)
total = total_kernel_mem(layout)
check_math("total_mem", total, 0x20000 + 0x8000 + 0x10000 + 0x1000)


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = len(PASS) + len(FAIL)
print(f"总计: {len(PASS)}/{total} 通过")
if FAIL:
    print(f"失败 ({len(FAIL)} 个):")
    for n in FAIL:
        print(f"  - {n}")
else:
    print("所有 kernel 测试通过 ✓")
print("=" * 60)

sys.exit(0 if not FAIL else 1)
