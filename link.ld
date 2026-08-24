/*
 * Matha RISC-V 嵌入式项目 — 链接脚本
 * 目标: SiFive FE310 (RISC-V 32-bit)
 * Flash: 256KB @ 0x20000000
 * RAM:   128KB @ 0x80000000
 */

ENTRY(_start)

/* 内存布局 */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x20000000, LENGTH = 256K
    RAM  (rwx)  : ORIGIN = 0x80000000, LENGTH = 128K
}

/* 栈大小 */
_estack = 0x80000000 + 128K;

SECTIONS
{
    /* 代码段 */
    .text :
    {
        *(.text*)
        *(.rodata*)
        *(.eh_frame*)
    } > FLASH

    /* 全局/静态初始化数据 */
    .init_array :
    {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } > FLASH

    .fini_array :
    {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > FLASH

    /* 未初始化数据 (BSS) */
    .bss :
    {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        _ebss = .;
    } > RAM

    /* 数据段 */
    .data :
    {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > RAM AT > FLASH

    /* 堆 */
    .heap :
    {
        . = ALIGN(8);
        _heap_start = .;
        . += 8K;  /* 8KB 堆空间 */
        _heap_end = .;
    } > RAM

    /* 栈 */
    .stack :
    {
        . = ALIGN(8);
        . += 4K;  /* 4KB 栈空间 */
        _stack_end = .;
    } > RAM

    /* 调试信息 */
    /DISCARD/ :
    {
        *(.comment)
        *(.gnu*)
        *(.note*)
        *(.eh_frame*)
    }

    /* 确保输出有结束符号 */
    /DISCARD/ : { *(.eh_frame*) }
}

/* 汇编入口 */
SECTIONS
{
    .entry :
    {
        *(.entry)
    } > FLASH
}
