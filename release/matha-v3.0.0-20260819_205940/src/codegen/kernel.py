# -*- coding: utf-8 -*-
"""KernelGenerator：把 Matha 规格编译为 x86 操作系统内核汇编代码。

输出文件（NASM 汇编，可用 nasm + ld 构建为 ISO/磁盘镜像）：
  - boot.asm       引导扇区（512 字节，MBR 兼容）
  - kernel.asm     内核核心（GDT/IDT/Syscall/VFS 骨架）
  - Makefile       构建脚本（nasm + ld）

Matha 规格示例：
  ["内核", "MyOS", "MyOS", [
    ["系统名", "MyOS", [], []],
    ["内核版本", "0.1", [], []],
    ["目标架构", "x86", [], []],
    ["系统调用", ["write", "exit", "read"], [], []],
    ["页大小", "4096", [], []],
  ]]
"""

from __future__ import annotations
import logging
import os
from src.codegen.base import Generator, CodegenResult

logger = logging.getLogger(__name__)


class KernelSpec:
    """内核规格解析。"""

    def __init__(self, spec: list):
        self.name = "kernel"
        self.version = "0.1"
        self.arch = "x86"
        self.syscalls: list = ["write", "exit", "read"]
        self.page_size = 4096
        self.stack_size = 4096
        self.max_tasks = 64
        self._parse(spec)

    def _parse(self, spec: list) -> None:
        """解析规格树，提取内核参数。

        规格格式：
          ["内核", "名称", "名称", [元素...], {额外字段}]
          或 ["应用", "内核", "名称", [元素...]]
        """
        # 找到元素列表：跳过类型和名称
        idx = 0
        if len(spec) > 0 and str(spec[0]) == "应用":
            idx = 1
        # spec[idx] = 类型, spec[idx+1] = 名称
        elements = spec[idx + 2] if idx + 2 < len(spec) and isinstance(spec[idx + 2], (list, tuple)) else []
        for elem in elements:
            if not isinstance(elem, list) or len(elem) < 2:
                continue
            tag = str(elem[0])
            value = str(elem[1]) if len(elem) > 1 else ""
            if tag == "系统名":
                self.name = value
            elif tag == "内核版本":
                self.version = value
            elif tag == "目标架构":
                self.arch = value.lower()
            elif tag == "系统调用":
                if isinstance(value, str):
                    self.syscalls = [v.strip() for v in value.split(",") if v.strip()]
                elif isinstance(value, list):
                    self.syscalls = [str(v) for v in value]
            elif tag == "页大小":
                try:
                    self.page_size = int(value)
                except ValueError:
                    pass
            elif tag == "栈大小":
                try:
                    self.stack_size = int(value)
                except ValueError:
                    pass
            elif tag == "最大任务数":
                try:
                    self.max_tasks = int(value)
                except ValueError:
                    pass


class KernelGenerator(Generator):
    """x86 操作系统内核生成器。"""

    # 键盘环形缓冲区配置
    KBD_BUF_SIZE = 256

    def generate(self) -> CodegenResult:
        files = []
        try:
            # 尝试从 app.meta 获取原始规格，或从 elements 重建
            raw = self.app.meta.get("raw_spec", [])
            spec = KernelSpec(raw)
            # 若 spec 未解析出有效名称，从 elements 补充
            if spec.name == "kernel" and self.app.elements:
                for el in self.app.elements:
                    if el.tag == "系统名":
                        spec.name = el.text
                    elif el.tag == "内核版本":
                        spec.version = el.text
                    elif el.tag == "目标架构":
                        spec.arch = el.text.lower()
                    elif el.tag == "系统调用":
                        spec.syscalls = [v.strip() for v in el.text.split(",") if v.strip()]
                    elif el.tag == "页大小":
                        try:
                            spec.page_size = int(el.text)
                        except ValueError:
                            pass
                    elif el.tag == "栈大小":
                        try:
                            spec.stack_size = int(el.text)
                        except ValueError:
                            pass
                    elif el.tag == "最大任务数":
                        try:
                            spec.max_tasks = int(el.text)
                        except ValueError:
                            pass
            boot = self._gen_boot_asm(spec)
            kernel = self._gen_kernel_asm(spec)
            makefile = self._gen_makefile(spec)

            files.append(self._write("boot.asm", boot))
            files.append(self._write("kernel.asm", kernel))
            files.append(self._write("Makefile", makefile))
        except Exception as e:
            return CodegenResult(成功=False, 类型="内核", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="内核", 名称=self.app.name,
            文件=files, 入口=files[0],
        )

    # ============================================================
    # 引导扇区汇编
    # ============================================================
    def _gen_boot_asm(self, spec: KernelSpec) -> str:
        """生成 512 字节引导扇区（MBR 兼容，实模式 → 保护模式）。"""
        lines = [
            "; ============================================================",
            "; Matha Kernel Generator — Boot Sector",
            "; 规格: %s v%s (x86)" % (spec.name, spec.version),
            "; 用 nasm -f bin boot.asm -o boot.bin 汇编",
            "; ============================================================",
            "global start",
            "extern kernel_main",
            "",
            "; ── 引导扇区入口（必须恰好 510 字节 + 0xAA55）───────────────",
            "section .boot align=16",
            "start:",
            "    ; 1. 关闭中断，设置安全段寄存器",
            "    cli",
            "    xor ax, ax",
            "    mov ds, ax",
            "    mov es, ax",
            "    mov ss, ax",
            "    mov fs, ax",
            "    mov gs, ax",
            "",
            "    ; 2. 切换到保护模式",
            "    ; 2a. 关闭可屏蔽中断",
            "    cli",
            "",
            "    ; 2b. 加载 GDT（位于 kernel 段之后）",
            "    lgdt [gdt_descriptor]",
            "",
            "    ; 2c. 开启 A20 地址线",
            "    .a20_wait:",
            "        in al, 0x92",
            "        test al, 2",
            "        jnz .a20_done",
            "        mov al, 0x2",
            "        out 0x92, al",
            "        jmp .a20_wait",
            "    .a20_done:",
            "",
            "    ; 2d. 设置 CR0.PE = 1（进入保护模式）",
            "    mov eax, cr0",
            "    or eax, 1",
            "    mov cr0, eax",
            "",
            "    ; 2e. 远跳转到 32 位代码段",
            "    jmp 0x08:.pm_start",
            "",
            "section .text",
            ".pm_start:",
            "    ; 3. 设置 32 位段寄存器",
            "    mov ax, 0x10        ; 数据段选择子",
            "    mov ds, ax",
            "    mov es, ax",
            "    mov fs, ax",
            "    mov gs, ax",
            "    mov ss, ax",
            "",
            "    ; 4. 设置栈指针",
            "    mov esp, kernel_stack_top",
            "",
            "    ; 5. 开启中断（GDT 已就绪）",
            "    sti",
            "",
            "    ; 6. 调用内核入口",
            "    call kernel_main",
            "",
            "    ; 7. 内核返回后停机",
            "    hlt",
            "",
            "; ── GDT（Global Descriptor Table）─────────────────────────────",
            "gdt_start:",
            "    ; 0x00: 空描述符",
            "    dq 0x0000000000000000",
            "",
            "    ; 0x08: 代码段（基址 0，限长 4GB，执行/读取，DPL=0）",
            "    dw 0xFFFF           ; 限长低 16 位",
            "    dw 0x0000           ; 基址低 16 位",
            "    db 0x00             ; 基址中 8 位",
            "    db 10011010b        ; 存在/代码段/允许访问/DPL=0/非对齐",
            "    db 11110000b        ; 限长高 4 位/页粒度/32 位",
            "    db 0x00             ; 基址高 8 位",
            "",
            "    ; 0x10: 数据段（基址 0，限长 4GB，读取/写入，DPL=0）",
            "    dw 0xFFFF",
            "    dw 0x0000",
            "    db 0x00",
            "    db 10010010b        ; 存在/数据段/允许访问/DPL=0/增长方向↑",
            "    db 11110000b",
            "    db 0x00",
            "",
            "gdt_end:",
            "gdt_descriptor:",
            "    dw gdt_end - gdt_start - 1",
            "    dd gdt_start",
            "",
            "; ── 栈空间（8KB）─────────────────────────────────────────────",
            "section .bss align=16",
            "    resb %d             ; kernel_stack" % spec.stack_size,
            "kernel_stack_top:",
            "",
            "; ── 引导扇区签名（MBR 兼容，填充到 510 字节）────────────────",
            "section .boot2 align=16",
            "    times 510-($-$$) db 0",
            "    dw 0xAA55",
        ]
        return "\n".join(lines) + "\n"

    # ============================================================
    # 内核汇编
    # ============================================================
    def _gen_kernel_asm(self, spec: KernelSpec) -> str:
        """生成内核核心（IDT + Syscall + 简单 VFS 骨架）。"""
        syscall_names = spec.syscalls
        syscall_count = len(syscall_names)
        max_inodes = spec.max_tasks * 4
        inode_size = 64
        tcb_size = 256

        # 构建 syscall 跳转表
        syscall_table_items = ", ".join("syscall_%s" % s for s in syscall_names)

        lines = [
            "; ============================================================",
            "; Matha Kernel Generator — Kernel Core",
            "; 规格: %s v%s" % (spec.name, spec.version),
            "; 架构: %s  |  页大小: %dB  |  最大任务: %d" % (spec.arch, spec.page_size, spec.max_tasks),
            "; 系统调用数: %d" % syscall_count,
            "; 用 nasm -f elf32 kernel.asm -o kernel.o",
            "; 用 ld -m elf_i386 -Ttext 0x10000 kernel.o -o kernel.bin",
            "; ============================================================",
            "global kernel_main",
            "global %s_entry" % spec.name,
            "extern _start_kernel",
            "",
            "section .text",
            "",
            "; ── 入口点（由 boot.asm 调用）────────────────────────────────",
            "%s_entry:" % spec.name,
            "    push eax          ; 保存 boot 参数",
            "    jmp kernel_main",
            "",
            "; ── 内核主入口────────────────────────────────────────────────",
            "kernel_main:",
            "    ; 1. 初始化 IDT（中断描述符表）",
            "    call _init_idt",
            "",
            "    ; 2. 初始化中断控制器（PIC）",
            "    call _init_pic",
            "",
            "    ; 3. 初始化页表（若页大小 > 0）",
            "    cmp eax, 0",
            "    jz .skip_page_init",
            "    call _init_page_table",
            ".skip_page_init:",
            "",
            "    ; 4. 初始化 VFS（虚拟文件系统）",
            "    call _init_vfs",
            "",
            "    ; 5. 创建初始任务（进程）",
            "    call _create_init_task",
            "",
            "    ; 6. 启用中断并进入调度循环",
            "    sti",
            "    jmp _scheduler_loop",
            "",
            "; ── 中断处理程序模板──────────────────────────────────────────",
            "; IRQ0: 定时器中断（系统时钟）",
            "global irq0_handler",
            "irq0_handler:",
            "    pusha",
            "    ; 发送 EOI 给 PIC",
            "    mov al, 0x20",
            "    out 0x20, al",
            "    popa",
            "    iret",
            "",
            "; IRQ1: 键盘中断",
            "global irq1_handler",
            "irq1_handler:",
            "    pusha",
            "    in al, 0x60       ; 读取键盘扫描码",
            "    ; 写入键盘环形缓冲区",
            "    mov cl, [kbd_buf_tail]",
            "    mov [kbd_buf + ecx], al",
            "    inc cl",
            "    cmp cl, %d" % KernelGenerator.KBD_BUF_SIZE,
            "    jne .kbd_no_wrap",
            "    xor cl, cl",
            ".kbd_no_wrap:",
            "    mov [kbd_buf_tail], cl",
            "    ; 发送 EOI 给 PIC",
            "    mov al, 0x20",
            "    out 0x20, al",
            "    popa",
            "    iret",
            "",
            "; 系统调用处理程序",
            "global syscall_handler",
            "syscall_handler:",
            "    pusha",
            "    ; eax = syscall number, ebx/ecx/edx = 参数",
            "    cmp eax, %d" % syscall_count,
            "    jae .invalid_syscall",
            "    ; 跳转表（inline 展开）",
            "    ; syscall_dispatch:",
            "    jmp [syscall_table]",
            ".invalid_syscall:",
            "    mov eax, -2       ; SYS_ENOSYS",
            "    popa",
            "    iret",
            "",
            "; ============================================================",
            "; 内核数据段",
            "; ============================================================",
            "section .data align=16",
            "",
            "; ── IDT（256 项 × 8 字节 = 2KB）─────────────────────────────",
            "idt_start:",
            "    resb 256 * 8      ; IDT 条目（每项 8 字节）",
            "idt_end:",
            "idt_descriptor:",
            "    dw idt_end - idt_start - 1",
            "    dd idt_start",
            "",
            "; ── 系统调用表────────────────────────────────────────────────",
            "syscall_table dd %s" % syscall_table_items,
            "syscall_count equ %d" % syscall_count,
            "",
            "; ── VFS 根目录结构────────────────────────────────────────────",
            "vfs_root:",
            '    db "root", 0',
            "    dd vfs_inodes     ; 指向 inode 表",
            "",
            "vfs_inodes:",
            "    resb %d * %d" % (max_inodes, inode_size),
            "",
            "; ── 任务控制块（TCB）数组─────────────────────────────────────",
            "task_table resb %d * %d" % (spec.max_tasks, tcb_size),
            "task_count equ %d" % spec.max_tasks,
            "",
            "; ── 日志缓冲区────────────────────────────────────────────────",
            "kernel_log resb 4096",
            "",
            "; ── 键盘环形缓冲区─────────────────────────────────────────────",
            "kbd_buf resb %d" % KernelGenerator.KBD_BUF_SIZE,
            "kbd_buf_head resb 1",
            "kbd_buf_tail resb 1",
            "",
            "; ── 错误消息───────────────────────────────────────────────────",
            'div_error_msg db "Error: Divide by Zero!", 0xA, 0',
            "log_ptr equ kernel_log",
            "",
            "; ============================================================",
            "; 内核 BSS（未初始化数据）",
            "; ============================================================",
            "section .bss align=16",
            "kernel_stack resb %d" % spec.stack_size,
            "stack_top:",
            "",
            "; ============================================================",
            "; 函数声明",
            "; ============================================================",
            "extern _init_idt",
            "extern _init_pic",
            "extern _init_page_table",
            "extern _init_vfs",
            "extern _create_init_task",
            "extern _scheduler_loop",
            "",
            "; ============================================================",
            "; 内联 IDT 初始化（自包含，避免依赖外部）",
            "; ============================================================",
            "init_idt_inline:",
            "    ; 清空 IDT",
            "    mov ecx, 256",
            "    xor edi, edi",
            "    rep stosd",
            "",
            "    ; 安装中断 0x00（除零异常）",
            "    lea eax, [div_by_zero_handler]",
            "    mov [idt_start + 0 * 8], ax",
            "    shr eax, 16",
            "    mov [idt_start + 0 * 8 + 6], ax",
            "    mov word [idt_start + 0 * 8 + 2], 0x0008",
            "    mov byte [idt_start + 0 * 8 + 4], 0x8E    ; 中断门，DPL=0",
            "    mov byte [idt_start + 0 * 8 + 5], 0x00",
            "",
            "    ; 安装定时器中断 IRQ0（系统调用 0）",
            "    lea eax, [irq0_handler]",
            "    mov [idt_start + 32 * 8], ax",
            "    shr eax, 16",
            "    mov [idt_start + 32 * 8 + 6], ax",
            "    mov word [idt_start + 32 * 8 + 2], 0x0008",
            "    mov byte [idt_start + 32 * 8 + 4], 0x8E",
            "    mov byte [idt_start + 32 * 8 + 5], 0x00",
            "",
            "    ; 安装键盘中断 IRQ1（系统调用 1）",
            "    lea eax, [irq1_handler]",
            "    mov [idt_start + 33 * 8], ax",
            "    shr eax, 16",
            "    mov [idt_start + 33 * 8 + 6], ax",
            "    mov word [idt_start + 33 * 8 + 2], 0x0008",
            "    mov byte [idt_start + 33 * 8 + 4], 0x8E",
            "    mov byte [idt_start + 33 * 8 + 5], 0x00",
            "",
            "    ; 安装系统调用门（int 0x80）",
            "    lea eax, [syscall_handler]",
            "    mov [idt_start + 128 * 8], ax",
            "    shr eax, 16",
            "    mov [idt_start + 128 * 8 + 6], ax",
            "    mov word [idt_start + 128 * 8 + 2], 0x0008",
            "    mov byte [idt_start + 128 * 8 + 4], 0xEF    ; 系统调用门，DPL=3",
            "    mov byte [idt_start + 128 * 8 + 5], 0x00",
            "",
            "    ; 加载 IDT",
            "    lgdt [idt_descriptor]",
            "    ret",
            "",
            "div_by_zero_handler:",
            "    pusha",
            "    ; 打印除零错误信息到控制台",
            "    mov eax, [div_error_msg]",
            "    call _puts",
            "    popa",
            "    ; 停机（避免进入死循环）",
            "    hlt",
        ]
        return "\n".join(lines) + "\n"

    # ============================================================
    # Makefile
    # ============================================================
    def _gen_makefile(self, spec: KernelSpec) -> str:
        """生成构建脚本。"""
        lines = [
            "# ============================================================",
            "# Matha Kernel Build Script — %s v%s" % (spec.name, spec.version),
            "# 需要: nasm (Netwide Assembler) + ld (GNU linker)",
            "# ============================================================",
            "NAME = %s" % spec.name,
            "VERSION = %s" % spec.version,
            "NASM = nasm",
            "LD = ld",
            "FLAGS_NASM = -f elf32",
            "FLAGS_LD = -m elf_i386 -Ttext 0x10000 --oformat binary",
            "",
            "all: kernel.bin boot.bin iso",
            "",
            "kernel.bin: kernel.asm",
            "\t$(NASM) $(FLAGS_NASM) kernel.asm -o kernel.o",
            "\t$(LD) $(FLAGS_LD) kernel.o -o kernel.bin",
            "",
            "boot.bin: boot.asm",
            "\t$(NASM) -f bin boot.asm -o boot.bin",
            "",
            "iso: boot.bin kernel.bin",
            "\tmkdir -p iso/boot/grub",
            '\techo "default 0" > iso/boot/grub/grub.cfg',
            '\techo \'menuentry "%s" {\' >> iso/boot/grub/grub.cfg' % spec.name,
            '\techo \'    multiboot /boot/%s.bin\' >> iso/boot/grub/grub.cfg' % spec.name,
            '\techo \'}}\' >> iso/boot/grub/grub.cfg',
            "\tgenisoimage -o %s.iso -b boot.bin -c boot/grub/boot.cat iso/" % spec.name,
            '\t@echo "=== %s v%s 构建完成 ==="' % (spec.name, spec.version),
            '\t@echo "  kernel.bin: $$(wc -c < kernel.bin) bytes"',
            '\t@echo "  boot.bin:   $$(wc -c < boot.bin) bytes"',
            '\t@echo "  ISO:        %s.iso"' % spec.name,
            "",
            "run: iso",
            "\tqemu-system-i386 -cdrom %s.iso -m 64M" % spec.name,
            "",
            "clean:",
            "\trm -f *.bin *.o *.iso",
            "\trm -rf iso/",
            "",
            ".PHONY: all kernel.bin boot.bin iso run clean",
        ]
        return "\n".join(lines) + "\n"

    # ============================================================
    # 辅助方法
    # ============================================================
    def _build_syscall_table(self, spec: KernelSpec) -> list:
        """根据规格中的系统调用列表生成 syscall 名称。"""
        return spec.syscalls


def generate_kernel(spec, out_dir=None):
    """快捷函数：生成内核代码。

    spec: Matha 列表规格（同 AppSpec 格式）
    out_dir: 输出目录（默认: D:/trae/matha/output/内核/<名称>/）
    """
    from src.codegen.base import parse_app_spec, OUTPUT_ROOT
    import os
    app = parse_app_spec(spec)
    if out_dir is None:
        out_dir = os.path.join(OUTPUT_ROOT, "内核", app.name)
    os.makedirs(out_dir, exist_ok=True)
    gen = KernelGenerator(app, out_dir)
    return gen.generate()
