# -*- coding: utf-8 -*-
"""Kernel Math: 操作系统内核数学模型与计算公式。

覆盖：系统调用表、PCB 内存布局、页表开销、中断延迟、进程调度内核开销。
所有函数均为数学公式/估算，不生成实际可执行代码（代码生成由 codegen.kernel 负责）。
"""

from __future__ import annotations


# ============================================================
# 系统调用（syscall）相关
# ============================================================

def syscall_num(syscall_name: str) -> int:
    """返回系统调用号（基于 Linux x86 32-bit 约定）。

    常用 syscall 号：
        write=4, read=3, exit=1, fork=2, open=5, close=6,
        mmap=192, brk=45, ioctl=54, kill=37
    """
    table: dict[str, int] = {
        "exit": 1,
        "fork": 2,
        "read": 3,
        "write": 4,
        "open": 5,
        "close": 6,
        "wait4": 7,
        "kill": 37,
        "fstat": 5,
        "mmap": 192,
        "mprotect": 125,
        "munmap": 91,
        "brk": 45,
        "ioctl": 54,
        "fcntl": 33,
        "pipe": 42,
        "dup": 32,
        "execve": 11,
        "chdir": 12,
        "mkdir": 39,
        "rmdir": 40,
        "uname": 127,
        "getpid": 39,
        "getuid": 102,
        "getgid": 104,
        "setuid": 105,
        "setgid": 106,
        "select": 115,
        "socket": 102,
        "connect": 98,
        "accept": 99,
        "sendto": 88,
        "recvfrom": 89,
        "sigaction": 67,
        "sigprocmask": 70,
        "rt_sigreturn": 15,
        "set_robust_list": 173,
        "get_robust_list": 174,
        "arch_prctl": 158,
        "clone": 120,
        "unshare": 272,
        "set_tid_address": 186,
        "set_tls": 160,
        "futex": 202,
        "clock_gettime": 228,
        "nanosleep": 101,
        "sysinfo": 116,
        "sysctl": 149,
    }
    return table.get(syscall_name.lower(), -1)


def syscall_entry_size(syscall_count: int) -> int:
    """系统调用表入口总大小（字节）。

    每项 8 字节（32 位系统）：跳转目标(4B) + padding(4B)
    """
    return syscall_count * 8


def syscall_latency_ns(kernel_mode: bool = True) -> float:
    """系统调用开销（纳秒估算）。

    kernel_mode=True: 纯内核路径（无用户态切换）
    kernel_mode=False: 含用户态→内核态切换
    """
    if kernel_mode:
        return 50.0   # 纯内核函数调用 ~50ns
    # 用户态 syscall: 压栈 + 模式切换 + IDT 查表 + 返回
    return 200.0 + 100.0  # ~300ns


# ============================================================
# PCB（进程控制块）内存布局
# ============================================================

def pcb_size(num_registers: int = 18, stack_size: int = 4096) -> int:
    """计算 PCB 结构体大小（字节）。

    典型 x86 32-bit PCB 组成：
        - 进程状态 (4B)
        - PID / PPID (8B)
        - 寄存器快照 (num_registers × 4B)
        - 栈指针 + 栈大小 (8B)
        - 内存映射指针 (4B)
        - 文件描述符表指针 (4B)
        - 信号处理表 (32B)
        - 调度信息 (16B)
        - 对齐填充
    """
    base = 80           # 固定头部
    regs = num_registers * 4
    return base + regs + stack_size


def pcb_alloc_cost(num_tasks: int, pcb_size: int) -> int:
    """分配 num_tasks 个 PCB 所需的总内存（字节）。"""
    return num_tasks * pcb_size


def pcb_context_switch_cycles(num_registers: int = 18) -> int:
    """上下文切换开销（时钟周期估算）。

    包括：保存当前寄存器 → 切换页表 → 加载新寄存器
    """
    save_cycles = num_registers * 2       # 每寄存器 ~2 周期保存
    switch_mm = 5000                       # TLB flush ~5000 cycles
    load_cycles = num_registers * 2       # 每寄存器 ~2 周期加载
    return save_cycles + switch_mm + load_cycles


# ============================================================
# 页表与虚拟内存
# ============================================================

def page_table_entries(page_size: int, memory_size: int, page_table_entries_per_table: int = 1024) -> int:
    """计算需要的页表项总数（含多级页表）。

    x86 32-bit 使用两级页表：
        - PML4 不存在（32-bit 无 PAE）
        - PD（页目录）：1024 项 × 4B = 4KB
        - PT（页表）：1024 项 × 4B = 4KB
    """
    if page_size <= 0:
        return 0
    pages = memory_size // page_size
    # 单级页表
    pt_entries = (pages + page_table_entries_per_table - 1) // page_table_entries_per_table
    # 加上页目录自身
    pd_entries = (pt_entries + page_table_entries_per_table - 1) // page_table_entries_per_table
    total = pages + pt_entries * page_table_entries_per_table + pd_entries
    return total


def page_table_overhead_bytes(page_size: int, memory_size: int) -> int:
    """页表结构本身占用的内存（字节）。

    每级页表固定 4KB（1024 项 × 4B）。
    """
    if page_size <= 0:
        return 0
    pages = memory_size // page_size
    pt_entries = (pages + 1023) // 1024
    pd_entries = (pt_entries + 1023) // 1024
    # 每级页表 4KB
    return (pd_entries + pt_entries) * 4096


def linear_address(page_table: int, page_offset: int, page_size: int) -> int:
    """物理地址 = page_table * page_size + page_offset。"""
    return page_table * page_size + page_offset


def virtual_to_physical(vaddr: int, page_size: int = 4096) -> tuple[int, int]:
    """虚拟地址 → (页号, 页内偏移)。"""
    return vaddr // page_size, vaddr % page_size


# ============================================================
# 中断与异常
# ============================================================

def interrupt_latency_us(irq_number: int, pic_master: bool = True) -> float:
    """中断响应延迟估算（微秒）。

    IRQ0-7: 主 PIC（8259A）
    IRQ8-15: 从 PIC（级联）
    """
    base_latency = 2.0    # 基础延迟 2μs
    cascade_penalty = 4.0 if not pic_master else 0.0  # 从 PIC 额外级联延迟
    return base_latency + cascade_penalty


def exception_vector(vector: int) -> str:
    """返回异常向量名称。"""
    names = {
        0: "Divide-by-zero (#DE)",
        1: "Debug (#DB)",
        2: "NMI",
        3: "Breakpoint (#BP)",
        4: "Overflow (#OF)",
        5: "Bound Range Exceeded (#BR)",
        6: "Invalid Opcode (#UD)",
        7: "Device Not Available (#NM)",
        8: "Double Fault (#DF)",
        9: "Coprocessor Segment Overrun",
        10: "Invalid TSS (#TS)",
        11: "Segment Not Present (#NP)",
        12: "Stack Exception (#SS)",
        13: "General Protection Fault (#GP)",
        14: "Page Fault (#PF)",
        16: "x87 FPU Error (#MF)",
        17: "Alignment Check (#AC)",
        18: "Machine Check (#MC)",
        19: "SIMD FPU Error (#XM)",
        20: "Virtualization Exception (#VE)",
        32: "IRQ0: Timer (定时中断)",
        33: "IRQ1: Keyboard (键盘中断)",
        128: "System Call (int 0x80)",
    }
    return names.get(vector, f"Unknown vector {vector}")


# ============================================================
# 进程调度内核开销
# ============================================================

def scheduler_tick_latency_us(tsc_mhz: int = 3000) -> float:
    """调度器时钟滴答开销（微秒）。

    TSC (Time Stamp Counter) 频率 MHz。
    """
    # 典型滴答率：100Hz → 10ms/tick，内核路径 ~10μs
    return 10.0


def context_switch_overhead_us(tsc_mhz: int = 3000, num_regs: int = 18) -> float:
    """上下文切换总开销（微秒）。

    包括：TLB flush + 寄存器保存/加载 + 栈切换 + 页表切换
    """
    tlb_flush_us = 5.0 / tsc_mhz * 1000       # TLB shootdown
    reg_save_us = num_regs * 2 / tsc_mhz * 1000  # 寄存器压栈
    reg_load_us = num_regs * 2 / tsc_mhz * 1000  # 寄存器出栈
    mm_switch_us = 10.0 / tsc_mhz * 1000      # 页表切换
    return tlb_flush_us + reg_save_us + reg_load_us + mm_switch_us


def throughput_max_tasks(num_tasks: int, switch_us: float) -> float:
    """最大吞吐任务数估算（基于上下文切换开销）。"""
    if switch_us <= 0:
        return 0
    # 每秒可完成的切换次数
    swaps_per_sec = 1_000_000 / switch_us
    # 每个任务至少需要 1 次切换
    return min(num_tasks, swaps_per_sec)


# ============================================================
# 内核内存布局估算
# ============================================================

def kernel_mem_layout(
    text_size: int = 0x20000,
    data_size: int = 0x8000,
    bss_size: int = 0x10000,
    stack_size: int = 0x1000,
    page_size: int = 4096,
) -> dict:
    """计算内核内存布局各段地址（x86 32-bit 传统布局）。

    返回 dict: {段名: (起始地址, 大小)}
    """
    # 内核加载基址（传统 Linux 内核）
    base = 0x100000  # 1MB

    text_start = base
    text_end = text_start + text_size
    data_start = text_end
    data_end = data_start + data_size
    bss_start = data_end
    bss_end = bss_start + bss_size
    stack_start = bss_end
    stack_end = stack_start + stack_size

    return {
        "text":  (text_start, text_size),
        "data":  (data_start, data_size),
        "bss":   (bss_start, bss_size),
        "stack": (stack_start, stack_size),
    }


def total_kernel_mem(layout: dict) -> int:
    """计算内核总内存占用（字节）。"""
    return sum(size for _, size in layout.values())


# ============================================================
# 注册为内建（供 Matha 脚本调用）
# ============================================================

def _register_kernel_builtins(builtins: dict) -> None:
    """将 kernel math 函数注册到解释器 builtins。"""
    builtins["syscall_号"] = lambda name: syscall_num(name)
    builtins["syscall_表大小"] = lambda n: syscall_entry_size(n)
    builtins["syscall_开销"] = lambda kernel_mode=True: syscall_latency_ns(bool(kernel_mode))
    builtins["pcb_大小"] = lambda regs=18, stack=4096: pcb_size(regs, stack)
    builtins["pcb_分配"] = lambda tasks, size: pcb_alloc_cost(tasks, size)
    builtins["pcb_切换周期"] = lambda regs=18: pcb_context_switch_cycles(regs)
    builtins["页表项数"] = lambda ps, mem: page_table_entries(ps, mem)
    builtins["页表开销"] = lambda ps, mem: page_table_overhead_bytes(ps, mem)
    builtins["线性地址"] = lambda pt, off, ps: linear_address(pt, off, ps)
    builtins["虚拟到物理"] = lambda va, ps=4096: virtual_to_physical(va, ps)
    builtins["中断延迟"] = lambda irq, master=True: interrupt_latency_us(irq, bool(master))
    builtins["异常向量"] = lambda v: exception_vector(v)
    builtins["调度滴答"] = lambda tsc=3000: scheduler_tick_latency_us(tsc)
    builtins["切换开销"] = lambda tsc=3000, regs=18: context_switch_overhead_us(tsc, regs)
    builtins["吞吐任务数"] = lambda n, us: throughput_max_tasks(n, us)
    builtins["内核内存布局"] = lambda: kernel_mem_layout()
    builtins["内核总内存"] = lambda layout: total_kernel_mem(layout)


def kernel_symtab_names() -> list[str]:
    """返回 kernel math 模块的符号表名列表。"""
    return [
        "syscall_号", "syscall_表大小", "syscall_开销",
        "pcb_大小", "pcb_分配", "pcb_切换周期",
        "页表项数", "页表开销", "线性地址", "虚拟到物理",
        "中断延迟", "异常向量",
        "调度滴答", "切换开销", "吞吐任务数",
        "内核内存布局", "内核总内存",
    ]
