MEMORY
{
    /* SiFive FE310 外壳：片外 QSPI 闪存 + 片内 16KB SRAM。
       与仓库既有约定一致（代码/常量驻留 0x20000000，数据/栈驻留 0x80000000）；
       长度可按实板调整。 */
    FLASH (rx)  : ORIGIN = 0x20000000, LENGTH = 4M
    RAM   (rwx) : ORIGIN = 0x80000000, LENGTH = 128K
}

/* 栈顶：RAM 末端，向上 8 字节对齐。crt0 把 sp 装到此处。 */
_estack = ORIGIN(RAM) + LENGTH(RAM);

ENTRY(_start)

SECTIONS
{
    /* 代码 + 只读数据：从 FLASH 取指执行（XIP）。 */
    .text : {
        *(.text.entry)               /* crt0 的 _start 恒在段首 */
        *(.text .text.*)
        *(.rodata .rodata.*)
    } > FLASH

    /* .data 的加载镜像（LMA）落在 FLASH，运行镜像（VMA）落在 RAM，
       crt0 逐字把 load 地址拷到 run 地址。 */
    _sidata = LOADADDR(.data);
    .data : {
        . = ALIGN(4);
        _sdata = .;
        /* RISC-V gp 相对寻址基线：gp 指向 .sdata/.sbss 起点 +0x800，
           使 [-0x800, +0x7FF] 窗口覆盖本固件全部数据/小数据。crt0 装载 gp。 */
        PROVIDE(__global_pointer$ = . + 0x800);
        *(.data .data.*)
        *(.sdata .sdata.* .sdata2 .sdata2.*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH

    /* .bss 仅存在于 RAM，crt0 清零（含 .sbss 小数据）。 */
    .bss : {
        . = ALIGN(4);
        _sbss = .;
        *(.sbss .sbss.* .bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /* 堆：BSS 之后向上生长，与栈（自 _estack 向下）之间的空隙即增长空间。
       _heap_end 由 allocator 在接管内存时读取（见 hal/mem/allocator.c）。 */
    .heap (NOLOAD) : {
        . = ALIGN(8);
        _heap_start = .;
        _heap_end = ORIGIN(RAM) + LENGTH(RAM);
    } > RAM

    /DISCARD/ : {
        *(.comment)
        *(.note*)
        *(.eh_frame*)
        *(.riscv.attributes)
    }
}
