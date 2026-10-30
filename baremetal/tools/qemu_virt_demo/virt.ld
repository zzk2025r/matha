/* tools/qemu_virt_demo/virt.ld — QEMU virt (rv32) 内存映射：整块从 RAM 取指执行。
 * 与生产 link.ld（FE310：FLASH@0x20000000 + RAM@0x80000000，含 .data LMA 拷贝）不同，
 * 这里是最简 board-matched 变体：text/data/bss 全落 RAM，栈顶 0x80100000。 */
ENTRY(_start)
SECTIONS
{
    . = 0x80000000;
    .text  : { *(.text*) *(.rodata*) *(.rodata.*) }
    .data  : { *(.data*) *(.sdata*) }
    .bss   : { *(.bss*) *(.sbss*) *(COMMON) }
    _estack = 0x80100000;
}
